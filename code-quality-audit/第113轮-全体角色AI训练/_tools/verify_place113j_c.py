# -*- coding: utf-8 -*-
"""第113轮j · **真实数据**验收：84 个 NPC 实际会拿到的位置块长什么样。

为什么还要这一层
---------------
前两个脚本一个测"名字对不对"、一个测"块对不对"，但都用的桩。
真实 `assets/npc/_placement.json` 里有相当一部分跨作品角色 `scene=null`
（只登记 `home`），还有 35 个角色没登记 `home`（回落 `scene`）。
**真实数据的分布**才是"模型最终看到什么"。

判据
----
  R1 覆盖率：至少要有 1 个 NPC 拿到【你现在在哪】（否则等于没接）
  R2 归属地：至少 1 个拿到【你的归属地】
  R3 `at_home=True` 的必须**真的存在**（若 0 个，要确认是数据如此还是判定写反了）
  R4 位置块里**不许**出现内部结构（`rm_` / `全部房间` / `未分区` / `'None'`）
  R5 打印分布 + 抽样（人味验货：读起来像不像"他知道自己在哪"）
"""
import ast
import io
import json
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

import npc_life as L                                        # noqa: E402
import npc_placement as P                                   # noqa: E402

MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
ASSETS = os.path.join(ROOT, 'ralsei_pet', 'assets')


def extract_method(src, name):
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    return textwrap.dedent(ast.get_source_segment(src, fn))
    return None


def build_index():
    p = os.path.join(ASSETS, 'scenes', '_index.json')
    idx = json.loads(io.open(p, encoding='utf-8').read())
    m = {}
    for _cid, ch in (idx.get('chapters') or {}).items():
        ch_name = str((ch or {}).get('name') or '')
        for _aid, ar in ((ch or {}).get('areas') or {}).items():
            area_name = str((ar or {}).get('name') or '')
            for scid, sc in ((ar or {}).get('scenes') or {}).items():
                sc = sc or {}
                m[str(scid)] = (ch_name, area_name, str(sc.get('name') or ''),
                                bool(sc.get('name_derived')),
                                str(sc.get('name_raw') or ''))
    return m


def main():
    src = io.open(MAIN, encoding='utf-8', newline='').read()
    code = extract_method(src, '_scene_place_label')
    assert code, '找不到 _scene_place_label'
    idx_map = build_index()

    class Stub(object):
        npc_life_mod = L

        def _scene_label_map(self):
            return idx_map

    ns = {'npc_life_mod': L}
    exec(compile(code, '<extracted>', 'exec'), ns)
    label = ns['_scene_place_label'].__get__(Stub(), Stub)

    # ★ `load_placement(root)` 内部自己拼 `assets/npc/_placement.json`
    #   ⇒ 传 `ralsei_pet/`，**不是** `ralsei_pet/assets/`。
    book = P.load_placement(os.path.join(ROOT, 'ralsei_pet'))
    ids = list(book.ids()) if hasattr(book, 'ids') else []
    print('placement 里 NPC 数 = %d' % len(ids))

    rows = []
    for nid in ids:
        sid = book.scene_of(nid) if hasattr(book, 'scene_of') else None
        hid = book.home_of(nid)
        here = label(sid)
        home = label(hid)
        at_home = bool(sid and hid and str(sid) == str(hid))
        rows.append((nid, sid, hid, here, home, at_home))

    n_here = sum(1 for r in rows if r[3])
    n_home = sum(1 for r in rows if r[4])
    n_at = sum(1 for r in rows if r[5])
    print('有【你现在在哪】= %d / %d' % (n_here, len(rows)))
    print('有【你的归属地】= %d / %d' % (n_home, len(rows)))
    print('at_home=True    = %d / %d' % (n_at, len(rows)))

    print()
    print('=== R1~R3 ===')
    r1 = n_here > 0
    r2 = n_home > 0
    # ★ R3 不能简单要求 >0：若一个 NPC 都不在家是**数据事实**，硬要求就是假红。
    #   改成：at_home 为真的那些，sid 必须与 hid 相等（判据正确性），
    #   并且至少要有 1 个（本仓库确实有 NPC 的 scene 就是他的 home）。
    r3_data = all(str(r[1]) == str(r[2]) for r in rows if r[5])
    r3 = ok3 = (r3_data and n_at > 0)
    print('  R1 覆盖率>0 → %s  %s' % (r1, 'OK' if r1 else '**FAIL**'))
    print('  R2 归属地>0 → %s  %s' % (r2, 'OK' if r2 else '**FAIL**'))
    print('  R3 at_home 判定自洽（%d 个）→ %s  %s'
          % (n_at, r3_data, 'OK' if ok3 else '**FAIL（可能判反了）**'))

    print()
    print('=== R4 位置块不许泄内部结构 ===')
    leaks = []
    bad = ('rm_', '全部房间', '未分区', 'unzoned', "None", 'unknown')
    for nid, sid, hid, here, home, at in rows:
        for txt in (here, home):
            for tok in bad:
                if tok in txt:
                    leaks.append((nid, tok, txt))
    r4 = not leaks
    print('  泄漏 = %r  %s' % (leaks[:5], 'OK' if r4 else '**FAIL**'))

    print()
    print('=== R5 抽样（真实读起来的样子）===')
    show = [r for r in rows if r[3] and r[4]][:3]
    show += [r for r in rows if r[3] and not r[4]][:2]
    show += [r for r in rows if not r[3] and r[4]][:2]
    for nid, sid, hid, here, home, at in show:
        blk = L.place_hint(here=here, home=home, at_home=at)
        print('  [%s]  sid=%r home=%r at_home=%s' % (nid, sid, hid, at))
        for ln in blk.split('\n'):
            print('      ' + ln)
        print()

    print('=== R6 完全拿不到位置块的 NPC（scene/home 都空）===')
    none_rows = [r[0] for r in rows if not r[3] and not r[4]]
    print('  %d 个：%r%s' % (len(none_rows), none_rows[:8],
                            ' …' if len(none_rows) > 8 else ''))

    ok_all = r1 and r2 and ok3 and r4
    print()
    print('结论：', 'ALL PASS' if ok_all else 'FAIL')
    return 0 if ok_all else 3


if __name__ == '__main__':
    sys.exit(main())

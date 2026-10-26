# -*- coding: utf-8 -*-
"""第113轮j · 验证 `_scene_place_label`：**真用产品源码**，不另写一份然后"自己测自己"。

做法
----
从 `src/main.py` 里用 AST **取出**这个方法体的源码（`ast.get_source_segment`），
`dedent` 后 `exec` 成模块级函数，再挂到一个只提供 `_scene_label_map()` 的桩对象上。
⇒ 被测的是**产品里那段代码本身**，不是它的复刻版。

判据（正/负成对）
---------------
  A 有真名的地方：`ch1.castle_town.castle_town` 必须含「城堡镇」
  B 内部 id 的地方：`uty.rooms.rm_steamworks_29` 必须含 `steamworks 29`
  C ★★ **任何输出都不许出现 `rm_` 前缀，也不许出现「全部房间」**
     —— 这两样是"把内部结构泄给模型"，正是第一版的真错误
  D 负控制：空串 / None ⇒ `''`（不产块，而不是"你在未知地点"）
  E 负控制：`章名 == 位置名`（desktop）不许出现 `桌面（桌面）`
"""
import ast
import io
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

import npc_life as L                                        # noqa: E402

MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

CASES = [
    ('ch1.castle_town.castle_town', '城堡镇'),
    ('uty.rooms.rm_steamworks_29', 'steamworks 29'),
    ('uty.rooms.rm_steamworks_27', 'steamworks 27'),
    ('oneshot.mainline.FINALE', 'FINALE'),
    # ★ `desktop` 章里 scenes 的 key 就是 `'desktop'` 本身（实测），不是三段式
    ('desktop', '桌面'),
    ('ch2.ralsei_room.dw_ralsei_castle_front', ''),
]


def extract_method(src, name):
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    seg = ast.get_source_segment(src, fn)
                    return textwrap.dedent(seg)
    return None


def build_index():
    """与 `_scene_label_map()` **同口径**地读一遍索引（**只为喂桩**）。

    ★ 必须保持一致：产品代码已改成 **5 元组**
      `(章名, 区名, 场景名, name_derived, name_raw)`。
      桩给 3 元组会 `ValueError` —— 这类"桩比产品旧"是本项目反复踩的假红源
      （见详版 §107.7），所以这里显式对齐字段顺序，不靠记忆。
    """
    import json
    path = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_index.json')
    idx = json.loads(io.open(path, encoding='utf-8').read())
    m = {}
    for _cid, ch in (idx.get('chapters') or {}).items():
        ch_name = str((ch or {}).get('name') or '')
        for _aid, ar in ((ch or {}).get('areas') or {}).items():
            area_name = str((ar or {}).get('name') or '')
            for scid, sc in ((ar or {}).get('scenes') or {}).items():
                sc = sc or {}
                m[str(scid)] = (ch_name, area_name,
                                str(sc.get('name') or ''),
                                bool(sc.get('name_derived')),
                                str(sc.get('name_raw') or ''))
    return m


def main():
    src = io.open(MAIN, encoding='utf-8', newline='').read()
    code = extract_method(src, '_scene_place_label')
    if not code:
        print('FAIL: 源码里找不到 _scene_place_label')
        return 3
    idx_map = build_index()

    class Stub(object):
        npc_life_mod = L

        def _scene_label_map(self):
            return idx_map

    ns = {'npc_life_mod': L}
    exec(compile(code, '<extracted>', 'exec'), ns)
    fn = ns['_scene_place_label']
    stub = Stub()

    print('=== A/B 真实场景标签 ===')
    bad = []
    for sid, must in CASES:
        got = fn(stub, sid)
        ok = (must in got) if must else True
        print('  %-42s → %-40r %s' % (sid, got, 'OK' if ok else 'FAIL(需含 %r)' % must))
        if not ok:
            bad.append(sid)

    print()
    print('=== C ★★ 不许泄内部结构（`rm_` 前缀 / 「全部房间」）===')
    leak = []
    for sid, _m in CASES:
        got = fn(stub, sid)
        for tok in ('rm_', '全部房间', 'uty.rooms', 'ch1.castle_town'):
            if tok in got:
                leak.append((sid, tok, got))
    print('  泄漏 = %r  %s' % (leak, 'OK' if not leak else '**FAIL**'))

    print()
    print('=== D 负控制：空 / None ⇒ 空串 ===')
    d_ok = (fn(stub, '') == '' and fn(stub, None) == '')
    print('  空串→%r  None→%r  %s' % (fn(stub, ''), fn(stub, None), 'OK' if d_ok else 'FAIL'))

    print()
    print('=== E 负控制：章名 == 位置名时不加括注 ===')
    got_desktop = fn(stub, 'desktop')
    e_ok = ('桌面（桌面）' not in got_desktop)
    print('  desktop → %r  %s' % (got_desktop, 'OK' if e_ok else 'FAIL'))

    print()
    print('=== F 正控制：判据对"坏数据"必须报红 ===')
    # 手工塞一条"name 就是内部 id"的记录给桩，确认 C 的判据不是恒真
    # ★ 5 元组，与产品解包顺序一致；`name_raw` 也刻意塞 id，把两条退路都堵死
    idx_map['zz.bad.rm_bad_thing'] = ('黄魂', '全部房间', 'rm_bad_thing', False, 'rm_bad_thing')
    got_bad = fn(stub, 'zz.bad.rm_bad_thing')
    f_ok = ('rm_' not in got_bad and '全部房间' not in got_bad)
    print('  坏数据 → %r  %s' % (got_bad, 'OK' if f_ok else '**FAIL（判据没拦住）**'))

    ok_all = not bad and not leak and d_ok and e_ok and f_ok
    print()
    print('结论：', 'ALL PASS' if ok_all else 'FAIL')
    return 0 if ok_all else 3


if __name__ == '__main__':
    sys.exit(main())

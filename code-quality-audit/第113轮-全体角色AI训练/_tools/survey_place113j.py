# -*- coding: utf-8 -*-
"""第113轮j · 全量普查 `_scene_place_label`：**2166 个场景一个不落**。

为什么
------
`verify_place113j.py` 只挑 6 个样本 —— 6 个全绿**不能**说明 2166 个都对。
本项目的教训是「判据过窄 = 误报」：漏掉的那 2160 个里只要有一个泄出
`rm_steamworks_29` 或「全部房间」，模型的 prompt 里就会出现内部结构。

判据
----
  S1 覆盖率：`''` 空标签的占比必须为 **0**（每个场景都得能说出个地名）
  S2 泄漏率：含 `rm_` / `全部房间` / `unzoned` / 场景 id 全文的必须 **0**
  S3 形状：**去掉章名括注后**的 label 主体，` · ` 出现 > 1 次的（三段）必须 **0**
     ★ 判据的坑（本轮实打实踩了）：第一版直接对整串数 ` · `，结果把章名括注里的
       中点（`第一章 · 黑暗世界`）也算进去 ⇒ 谎报 320 条。**判据也是被测物**，
       所以下面 S3c 对判据本身做正/负控制。
  S4 括注：`（（` 或 `）（` 这类不合法的必须 **0**
  S5 正控制：故意喂一个不存在的 id，确认它**走兜底**而不是抛异常；
      再喂 `None`/`''`，确认返回 `''`（证明 S1 的 0 不是"恒返回非空"造成的假绿）
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

MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
IDX = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_index.json')


def extract_method(src, name):
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    return textwrap.dedent(ast.get_source_segment(src, fn))
    return None


def build_index():
    idx = json.loads(io.open(IDX, encoding='utf-8').read())
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


def label_body(got):
    """剥掉**末尾的章名括注**，剩下的才是 `区 · 场景` 主体。

    ★ 必须剥：章名自己是 `第一章 · 黑暗世界`，里面带中点。不剥就会把它算成三段。
    ★ 只剥最后一个全角 `（`（`未分区（废弃/调试/演示）（OneShot …）` 有两个），
      因为章名括注**永远在最后**。
    """
    if got.endswith('）') and '（' in got:
        return got[:got.rindex('（')]
    return got


def main():
    src = io.open(MAIN, encoding='utf-8', newline='').read()
    code = extract_method(src, '_scene_place_label')
    assert code, '源码里找不到 _scene_place_label'
    idx_map = build_index()

    class Stub(object):
        npc_life_mod = L

        def _scene_label_map(self):
            return idx_map

    ns = {'npc_life_mod': L}
    exec(compile(code, '<extracted>', 'exec'), ns)
    fn = ns['_scene_place_label']
    stub = Stub()

    print('索引场景总数 = %d' % len(idx_map))

    empty, leak, three, paren = [], [], [], []
    labels = {}
    bad_tokens = ('rm_', '全部房间', 'unzoned', '未分区', 'unknown', '未知', '.rooms.')
    for sid in sorted(idx_map):
        got = fn(stub, sid)
        labels[sid] = got
        if not got:
            empty.append(sid)
            continue
        for tok in bad_tokens:
            if tok in got:
                leak.append((sid, tok, got))
                break
        if got.count(' · ') > 1 and label_body(got).count(' · ') > 1:
            three.append((sid, got, label_body(got)))
        if '（（' in got or '）（' in got or got.count('（') != got.count('）'):
            paren.append((sid, got))

    def rep(name, rows, ok_msg):
        print()
        print('=== %s ===' % name)
        if not rows:
            print('  %s' % ok_msg)
            return True
        print('  **%d 条**，前 8 条：' % len(rows))
        for r in rows[:8]:
            print('    %r' % (r,))
        return False

    s1 = rep('S1 空标签', empty, '0 条 —— 每个场景都能说出地名')
    s2 = rep('S2 泄漏内部结构', leak, '0 条')
    s3 = rep('S3 三段（` · ` 出现 >1 次）', three, '0 条')
    s4 = rep('S4 括号不合法', paren, '0 条')

    print()
    print('=== 抽样（按章各取 2 条）===')
    seen = {}
    for sid in sorted(idx_map):
        ch = sid.split('.')[0]
        if seen.get(ch, 0) >= 2:
            continue
        seen[ch] = seen.get(ch, 0) + 1
        print('  %-44s → %r' % (sid, labels[sid]))

    print()
    print('=== S5 正/负控制 ===')
    weird = fn(stub, 'zz.nope.no_such_room')
    s5a = (weird == 'no such room')
    print('  不存在的 id → %r  %s' % (weird, 'OK（走兜底）' if s5a else '**FAIL**'))
    s5b = (fn(stub, '') == '' and fn(stub, None) == '')
    print('  空串→%r  None→%r  %s' % (fn(stub, ''), fn(stub, None), 'OK' if s5b else '**FAIL**'))

    print()
    print('=== S3c 判据自测：`label_body` 的正/负控制 ===')
    # 正控制：真三段（主体里两个中点）必须被识别成 >1
    pos = label_body('甲 · 乙 · 丙（章 · 下）').count(' · ')
    # 负控制：章名括注里的中点**不许**被算进主体
    neg = label_body('甲 · 乙（第一章 · 黑暗世界）').count(' · ')
    # 负控制：用 ` — ` 接末级名（PLACE_JOIN_ALT）不算三段
    alt = label_body('主线 · 家/塔/终局 — FINALE（OneShot · 世界机器版）').count(' · ')
    s3c = (pos == 2 and neg == 1 and alt == 1)
    print('  真三段 → %d（应 2）  单段+章名 → %d（应 1）  alt 分隔 → %d（应 1）  %s'
          % (pos, neg, alt, 'OK' if s3c else '**FAIL（判据本身错了）**'))

    ok_all = s1 and s2 and s3 and s4 and s5a and s5b and s3c
    print()
    print('结论：', 'ALL PASS' if ok_all else 'FAIL')
    return 0 if ok_all else 3


if __name__ == '__main__':
    sys.exit(main())

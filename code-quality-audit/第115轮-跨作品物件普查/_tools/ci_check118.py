# -*- coding: utf-8 -*-
u"""第118轮：校验 GML 解析结果与第117轮的指令流绑定表**互相对得上**。

为什么必须有这一步
------------------
`conds118.py` 是**文本解析**（读 UTMT 反编译出来的 GML），而第117轮的
`readable_bind.tsv` 是**指令流反射**（`PushBltn{room}; PushI N; Cmp`）。
两条完全不同的取证路径。若两者的 (房间, 键) 集合基本一致，才说明
解析器没有漏读/串行；若差得远，先怀疑解析器，别急着用它的产物。

★ 分母闸：两边都为空 / 一边全空 ⇒ 直接 FAIL（否则"零差异"是恒真）。

用法：python ci_check118.py --game ut
"""
import argparse
import collections
import io
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.dirname(HERE)
RAW = os.path.join(ROUND, '_evidence', 'raw')
CONDS = os.path.join(ROUND, '_evidence', 'readable_conds118.tsv')

RE_ROOM = re.compile(r'^room == (\w+)$')


def read_tsv(path):
    with io.open(path, encoding='utf-8', errors='replace', newline='') as f:
        lines = f.read().splitlines()
    if not lines:
        return []
    return [ln.split('\t') for ln in lines[1:] if ln.strip()]


def room_names(game):
    """room 下标 → 名字（inst_full.tsv 的 R 行）"""
    p = os.path.join(RAW, game, 'inst_full.tsv')
    out = {}
    if not os.path.isfile(p):
        return out
    for row in read_tsv(p):
        if len(row) >= 3 and row[0] == 'R':
            try:
                out[int(row[1])] = row[2]
            except ValueError:
                pass
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', default='ut')
    a = ap.parse_args(argv)

    idx2name = room_names(a.game)
    name2idx = {}
    for i, n in idx2name.items():
        name2idx.setdefault(n, i)
    if not idx2name:
        print('[FAIL] 拿不到房间表（%s/inst_full.tsv 的 R 行）' % a.game)
        return 2

    # ---- 解析侧：(room 下标, 键) ----
    parsed = set()
    no_room = 0
    unknown_room = collections.Counter()
    for row in read_tsv(CONDS):
        if len(row) != 5:
            continue
        _alarm, _depth, cond, _target, key = row
        if key.startswith('MSC_'):
            continue
        room = None
        for atom in cond.split(' && '):
            m = RE_ROOM.match(atom)
            if m:
                room = m.group(1)
                break
        if room is None:
            no_room += 1
            continue
        idx = name2idx.get(room)
        if idx is None:
            unknown_room[room] += 1
            continue
        parsed.add((idx, key))

    # ---- 指令流侧：(room 下标, 键) ----
    bound = set()
    p = os.path.join(RAW, a.game, 'readable_bind.tsv')
    for row in read_tsv(p):
        if len(row) != 4:
            continue
        _alarm, _obj, ri, key = row
        try:
            ri = int(ri)
        except ValueError:
            continue
        if ri < 0:
            continue
        bound.add((ri, key))

    if not parsed or not bound:
        print('[FAIL] 分母为空：parsed=%d bound=%d —— 本脚本什么也没证明'
              % (len(parsed), len(bound)))
        return 1

    only_parsed = parsed - bound
    only_bound = bound - parsed
    both = parsed & bound
    print('[%s] 解析侧 %d 对 / 指令流侧 %d 对 / 交集 %d'
          % (a.game, len(parsed), len(bound), len(both)))
    print('     仅解析侧（指令流没有）%d' % len(only_parsed))
    for x in sorted(only_parsed)[:5]:
        print('         %s  %s' % (idx2name.get(x[0], x[0]), x[1]))
    print('     仅指令流侧（解析漏了）%d' % len(only_bound))
    for x in sorted(only_bound)[:5]:
        print('         %s  %s' % (idx2name.get(x[0], x[0]), x[1]))
    print('     无 room 条件的赋值 %d 条；认不出的房间名 %d 个：%s'
          % (no_room, len(unknown_room), dict(unknown_room.most_common(5))))

    # ---- 判据：交集必须覆盖指令流侧的大头 ----
    cover = len(both) / float(len(bound))
    ok = cover >= 0.95 and not unknown_room
    print('')
    print('[%s] 覆盖率 %.1f%%（指令流侧被解析结果覆盖；下界 95%%）'
          % ('PASS' if cover >= 0.95 else 'FAIL', cover * 100))
    print('[%s] 房间名全部能对上（认不出 %d 个）'
          % ('PASS' if not unknown_room else 'FAIL', len(unknown_room)))
    return 0 if ok else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))

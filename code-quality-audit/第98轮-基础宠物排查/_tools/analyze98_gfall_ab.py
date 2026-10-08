# -*- coding: utf-8 -*-
u"""第98轮：重力坠落动画 A/B 对账（修复前 vs 修复后，同一注入）。

判据：`is_gravity_falling=True` 的帧里，`current_animation` 必须是**坠落家族**
      （`fall` / `fall_mad`；落地瞬间允许 `splat` / `land`），
      **不许是 `idle` / `walk_*` / `run_*`** —— 那是"站姿下坠"。

用法：
    python analyze98_gfall_ab.py <evidence_dir> [runA runB ...]
    （不带参数时用本仓库 `_evidence/` 下已知的 4 次录制）
"""
import io
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
EVD = os.path.normpath(os.path.join(HERE, '..', '_evidence'))

FALL_FAMILY = ('fall', 'fall_mad', 'splat', 'splat_mad', 'fall_back', 'land')
BAD = ('idle',)


def load(name):
    p = os.path.join(EVD, name, 'rec97_frames.csv')
    if not os.path.exists(p):
        return None
    lines = io.open(p, encoding='utf-8', newline='').read().split('\n')
    hdr = lines[0].split(',')
    return [dict(zip(hdr, x.split(','))) for x in lines[1:] if x.strip()]


def report(name):
    rows = load(name)
    if rows is None:
        print('  !! 缺 %s/rec97_frames.csv' % name)
        return None
    g = [r for r in rows if r['gfall'] == 'True']
    if not g:
        print('  %-24s 帧=%3d  重力坠落帧= 0（本次没触发）' % (name, len(rows)))
        return (name, len(rows), 0, 0.0, {})
    cnt = Counter(r['anim'] for r in g)
    bad = sum(v for k, v in cnt.items() if k in BAD or k.startswith(('walk_', 'run_')))
    good = sum(v for k, v in cnt.items() if k in FALL_FAMILY)
    # 连续段
    idx = [int(r['frame']) for r in g]
    segs = []
    for i in idx:
        if segs and i == segs[-1][1] + 1:
            segs[-1][1] = i
        else:
            segs.append([i, i])
    print('  %-24s 帧=%3d  坠落帧=%3d  坠落家族=%-3d 站姿/走路=%3d  段数=%d'
          % (name, len(rows), len(g), good, bad, len(segs)))
    print('      动画分布 = %s' % dict(cnt))
    for a, b in segs:
        anims = sorted(set(r['anim'] for r in rows
                           if a <= int(r['frame']) <= b))
        ya = [r for r in rows if int(r['frame']) == a][0]['wy']
        yb = [r for r in rows if int(r['frame']) == b][0]['wy']
        print('        f%03d-f%03d dy=%+5d anims=%s' % (a, b, int(yb) - int(ya), anims))
    return (name, len(rows), len(g), float(bad), dict(cnt))


DEFAULT = ['run_natural', 'run_natural_postfix',
           'run_inj_gfall_before', 'run_inj_gfall_after']
runs = sys.argv[2:] if len(sys.argv) > 2 else DEFAULT
if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
    EVD = sys.argv[1]

print('=' * 78)
print(u'# 第98轮：重力坠落"播什么动画" A/B 对账（EVD=%s）' % EVD)
print('=' * 78)
out = []
for r in runs:
    print('')
    print('-- %s' % r)
    out.append(report(r))

print('')
print('#' * 78)
print(u'# 汇总：`站姿/走路` 帧数 = 0 才算"重力坠落期间真的在播坠落动画"')
print('#' * 78)
for o in out:
    if o:
        print('  %-24s 坠落帧=%-3d 站姿/走路=%-4d' % (o[0], o[2], int(o[3])))

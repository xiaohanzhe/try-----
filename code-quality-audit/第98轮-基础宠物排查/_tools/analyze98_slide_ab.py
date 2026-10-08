# -*- coding: utf-8 -*-
u"""第98轮：**真滑步** A/B 对账（修复前 vs 修复后）。

真滑步 = 窗口**容器尺寸不变**（⇒ 排除"容器重定心"）+ 窗口**持续位移**
        + 当前动画是**地面静态动画**（idle / look_up / pose / act …）
        + 不是重力坠落帧（那属另一个缺陷，见 `analyze98_gfall_ab.py`）。
持续段判据取 **>=3 帧**（≈1.0 s）：2 帧（≈0.5 s）是 idle↔walk 的**过渡毛刺**，
不构成用户可感知的"站着平移"。

★ 为什么必须带"容器尺寸不变"：
  `walk_*` 容器 38x80 → `idle` 容器 138x94 时，为保**可见中心**不变，
  窗口左上角**必然**位移 `(-(138-38)/2, -(94-80)/2) = (-50,-7)`
  （`_compose_anchored_sprite` 把 alpha 包围盒中心钉在画布中心）——
  **可见宠物不动**，只看窗口坐标会**误报**。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EVD = os.path.normpath(os.path.join(HERE, '..', '_evidence'))
MIN_FRAMES = 3

SKIP_PREFIX = ('walk_', 'run_', 'jump', 'splat', 'land')


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
    segs, cur = [], None
    for i in range(1, len(rows)):
        p, c = rows[i - 1], rows[i]
        same_size = (p['ww'], p['wh']) == (c['ww'], c['wh'])
        moved = (p['wx'], p['wy']) != (c['wx'], c['wy'])
        ok = (same_size and moved
              and not c['anim'].startswith(SKIP_PREFIX)
              and c['anim'] != 'fall'
              and c['gfall'] != 'True')
        if ok:
            cur = [i - 1, i] if cur is None else [cur[0], i]
        else:
            if cur is not None:
                segs.append(cur)
                cur = None
    if cur is not None:
        segs.append(cur)

    sustain = [(a, b) for a, b in segs if b - a + 1 >= MIN_FRAMES]
    tot = sum(b - a + 1 for a, b in segs)
    tot_s = sum(float(rows[b]['t']) - float(rows[a]['t']) for a, b in segs)
    tot2 = sum(b - a + 1 for a, b in sustain)
    tot2_s = sum(float(rows[b]['t']) - float(rows[a]['t']) for a, b in sustain)
    print('  %-24s 帧=%3d  滑步段=%2d(帧=%-3d %.2fs)  **持续段(>=%d帧)**=%d(帧=%-3d %.2fs)'
          % (name, len(rows), len(segs), tot, tot_s, MIN_FRAMES,
             len(sustain), tot2, tot2_s))
    for a, b in sustain:
        anims = sorted(set(rows[i]['anim'] for i in range(a, b + 1)))
        print('        ★ f%03d-f%03d n=%d %.2fs Δ=(%+d,%+d) size=%sx%s anims=%s'
              % (a, b, b - a + 1,
                 float(rows[b]['t']) - float(rows[a]['t']),
                 int(rows[b]['wx']) - int(rows[a]['wx']),
                 int(rows[b]['wy']) - int(rows[a]['wy']),
                 rows[a]['ww'], rows[a]['wh'], anims))
    return (name, len(sustain), tot2, tot2_s)


runs = sys.argv[1:] or ['run_natural', 'run_natural_postfix']
print('=' * 78)
print(u'# 第98轮：真滑步 A/B 对账（EVD=%s；持续段阈值=%d 帧）' % (EVD, MIN_FRAMES))
print('=' * 78)
out = []
for r in runs:
    out.append(report(r))
print('')
print('-' * 78)
for o in out:
    if o:
        print('  %-24s 持续滑步段=%-3d 帧=%-3d %.2fs' % (o[0], o[1], o[2], o[3]))

# -*- coding: utf-8 -*-
u"""第92轮：位移取证 TSV 的量化（"修前 / 修后"同一把尺）。

判据全部来自**真实产物**（探针落盘的 TSV），不读源码字面量：

  A. `move()` 调用次数；
  B. ★★★ **零位移调用占比** —— `delta == (0,0)` 的次数 / 调用次数
     （= `int(round())` 取整丢失、且余量不结转的**直接签名**）；
  C. 行走段数（`is_moving` 0→1 的次数）与每段「目标距离 / 用时 / 实走距离」；
  D. 总位移 / 总时长 = 平均速度（px/s）；
  E. 移动占空比（`is_moving==1` 的采样占比）。
     ⚠️ 这个数**单独看会骗人**：修前实测 `duty=94.9%`（一直在"走"）却只有 3.9px/s
     —— "占空比高 + 速度低"正是"站桩"的指纹，必须和 D 一起读。

用法:
    C:/Python311/python.exe analyze92.py <tsv> [<tsv> ...]
"""
import statistics
import sys

paths = sys.argv[1:]
if not paths:
    print(__doc__)
    raise SystemExit(2)


def _load(path):
    rows = []
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line or line.startswith('t\t') or line.startswith('#'):
            continue
        c = line.split('\t')
        if len(c) < 16 or c[0] == 'ERR':
            continue
        try:
            rows.append({
                't': float(c[0]), 'moving': int(c[1]),
                'x': int(c[2]), 'y': int(c[3]),
                'tx': int(c[4]), 'ty': int(c[5]),
                'speed': float(c[6]),
                'anim': c[9], 'locked': int(c[11]),
                'calls': int(c[13]), 'dx': int(c[14]), 'dy': int(c[15]),
            })
        except (ValueError, IndexError):
            continue
    return rows


for path in paths:
    rows = _load(path)
    print('=' * 72)
    print('文件: %s' % path)
    if not rows:
        print('  NO DATA')
        continue
    span = rows[-1]['t'] - rows[0]['t']
    print('samples=%d span=%.1fs' % (len(rows), span))

    calls = rows[-1]['calls'] - rows[0]['calls']
    zero = sum(1 for r in rows if r['calls'] > 0 and r['dx'] == 0 and r['dy'] == 0)
    moved = sum(1 for r in rows if r['calls'] > 0 and (r['dx'] or r['dy']))
    print('  move_calls=%d  zero_delta_ticks=%d  nonzero_ticks=%d  zero_ratio=%.1f%%'
          % (calls, zero, moved, 100.0 * zero / max(1, zero + moved)))

    segs, cur = [], None
    for r in rows:
        if r['moving'] == 1:
            if cur is None:
                cur = {'t0': r['t'], 'x0': r['x'], 'y0': r['y'],
                       'tx': r['tx'], 'ty': r['ty'], 'spd': [],
                       't1': r['t'], 'x1': r['x'], 'y1': r['y']}
            cur['t1'] = r['t']
            cur['x1'], cur['y1'] = r['x'], r['y']
            cur['spd'].append(r['speed'])
        elif cur is not None:
            segs.append(cur)
            cur = None
    if cur is not None:
        segs.append(cur)

    print('  walk_segments=%d' % len(segs))
    if segs:
        dur = [s['t1'] - s['t0'] for s in segs]
        walked = [abs(s['x1'] - s['x0']) + abs(s['y1'] - s['y0']) for s in segs]
        tdist = [((s['tx'] - s['x0']) ** 2 + (s['ty'] - s['y0']) ** 2) ** 0.5
                 for s in segs]
        spd_all = [x for s in segs for x in s['spd']]
        print('  seg_duration  med=%.3fs min=%.3f max=%.3f'
              % (statistics.median(dur), min(dur), max(dur)))
        print('  seg_walked_px med=%.1f min=%d max=%d'
              % (statistics.median(walked), min(walked), max(walked)))
        print('  seg_target_px med=%.1f min=%.0f max=%.0f'
              % (statistics.median(tdist), min(tdist), max(tdist)))
        print('  speed(px/frame) med=%.2f min=%.2f max=%.2f'
              % (statistics.median(spd_all), min(spd_all), max(spd_all)))
        print('  speed(px/s @30ms tick) med=%.0f min=%.0f max=%.0f'
              % (statistics.median(spd_all) * 1000 / 30,
                 min(spd_all) * 1000 / 30, max(spd_all) * 1000 / 30))

    tot = 0
    for a, b in zip(rows, rows[1:]):
        if b['t'] - a['t'] < 0.5:
            tot += abs(b['x'] - a['x']) + abs(b['y'] - a['y'])
    print('  total_manhattan_px=%d  avg_px_per_s=%.1f' % (tot, tot / span))
    print('  duty(moving)=%.1f%%  locked_ticks=%d'
          % (100.0 * sum(1 for r in rows if r['moving'] == 1) / len(rows),
             sum(1 for r in rows if r['locked'] == 1)))
    print('  spot_pos_unique=%d  first=(%d,%d) last=(%d,%d)'
          % (len({(r['x'], r['y']) for r in rows}),
             rows[0]['x'], rows[0]['y'], rows[-1]['x'], rows[-1]['y']))
print('=' * 72)

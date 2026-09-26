# -*- coding: utf-8 -*-
"""第51轮 · 穿模定位 —— 75 处穿模到底出在哪一层。

背景：第45轮把 `plan_walk` 的穿模修到 0（17/2376 全出自 `simplify_collinear`），
第47轮又加了"人味化"两兄弟 `_monotone_forward` / `_despike`。
第51轮巡行实测：2244 成功 / **75 穿模** ⇒ 回归。

诊断手法（**先怀疑判据，再怀疑实现**）
--------------------------------------
对每个穿模样例，跑三档：
  ① `smooth=False`        —— 只走 simplify_collinear
  ② `smooth=True`（默认）  —— 再走 smooth_keep_walkable（含 monotone + despike）
  ③ 手工把 ①②的 path 都逐段密集采样（1px，比产品的 step*0.5 更密）
如果 ① 不穿、② 穿 ⇒ 罪在 smooth 链；若 ① 也穿 ⇒ 罪在 simplify/A* 层。

另外打印每次穿模的**段序号/总段数** + 命中的障碍矩形，用于判断"是首尾段还是中间段"。
"""
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, PET)
_MOD = os.path.join(PET, 'modules')
if _MOD not in sys.path:
    sys.path.append(_MOD)

import scene_system as SS      # noqa: E402
import scene_walk as SW        # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print('scene_walk 源文件: %s' % SW.__file__)

geo_raw = SS._read_json(os.path.join(SS.scenes_dir(), '_room_geometry.json')) or {}
GEO = geo_raw.get('rooms') or {}

CAND = 6
MAX_PAIRS = 8


def scan_penetration(path, items):
    """返回 (第一个穿模段下标, 段起, 段终, 命中矩形) 或 None。每 1px 采样。"""
    for k in range(len(path) - 1):
        x0, y0 = path[k]
        x1, y1 = path[k + 1]
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(d / 1.0))
        for q in range(n + 1):
            tt = q / float(n)
            px, py = x0 + (x1 - x0) * tt, y0 + (y1 - y0) * tt
            hit = SW.hit_obstacle(items, px, py)
            if hit is not None:
                return (k, (x0, y0), (x1, y1), (round(px, 1), round(py, 1)),
                        tuple(round(float(v), 1) for v in hit[:4]))
    return None


cases = []
for ch in ('ch1', 'ch2', 'ch4', 'ch5'):
    num = int(ch[2:])
    obs = SW.load_obstacles(num)
    if not obs.get('ok'):
        continue
    for rid_s, rec in sorted((obs.get('rooms') or {}).items(),
                             key=lambda kv: int(kv[0])):
        rid = int(rid_s)
        items = rec.get('items') or []
        if not items:
            continue
        geo = GEO.get('%s:%d' % (ch, rid))
        if not (isinstance(geo, dict) and isinstance(geo.get('w'), int)):
            continue
        w, h = int(geo['w']), int(geo['h'])
        room_rect = (0.0, 0.0, float(w), float(h))
        cand = []
        for iy in range(CAND):
            for ix in range(CAND):
                x = 20.0 + (w - 40.0) * ix / float(CAND - 1)
                y = 20.0 + (h - 40.0) * iy / float(CAND - 1)
                if not SW.blocks_at(items, x, y):
                    cand.append((x, y))
        pairs = 0
        for i in range(len(cand)):
            if pairs >= MAX_PAIRS:
                break
            for j in range(i + 1, len(cand)):
                if pairs >= MAX_PAIRS:
                    break
                a, b = cand[i], cand[j]
                if math.hypot(b[0] - a[0], b[1] - a[1]) < 60:
                    continue
                pairs += 1
                r_smooth = SW.plan_walk(num, rid, room_rect, a, b, obstacles=items)
                if not r_smooth.get('ok'):
                    continue
                pen = scan_penetration(r_smooth['path'], items)
                if pen is None:
                    continue
                # ★ 命中：跑 smooth=False 对照
                r_raw = SW.plan_walk(num, rid, room_rect, a, b, obstacles=items,
                                     smooth=False)
                pen_raw = (scan_penetration(r_raw['path'], items)
                           if r_raw.get('ok') else 'walk_fail')
                cases.append((ch, rid, a, b, pen, pen_raw,
                              len(r_smooth['path']), r_smooth.get('smoothed'),
                              len(r_raw.get('path') or [])))

print('\n命中 %d 例穿模（前 25 例详列）' % len(cases))
print('%-4s %-5s %-16s %-16s %-22s %-10s %s'
      % ('章', 'room', '起', '终', '穿模段', 'smooth=F穿?', '点数'))
n_raw_clean = 0
n_raw_dirty = 0
for c in cases[:25]:
    ch, rid, a, b, pen, pen_raw, npts, sm, nraw = c
    tag = '穿模' if pen_raw else ('不穿' if pen_raw is None else pen_raw)
    if pen_raw is None:
        n_raw_clean += 1
    elif pen_raw != 'walk_fail':
        n_raw_dirty += 1
    print('%-4s %-5d (%.0f,%.0f)      (%.0f,%.0f)      seg %d/%d → %s  %-10s n=%d/%d'
          % (ch, rid, a[0], a[1], b[0], b[1], pen[0], npts - 1,
             pen[3], tag, npts, nraw))
print('\n汇总（全部 %d 例）：' % len(cases))
print('  smooth=False 就穿（罪在 simplify/A*）: %d' % n_raw_dirty)
print('  仅 smooth=True 穿（罪在单调/去尖刺）  : %d' % n_raw_clean)
print('  另有 smooth=False 走不到              : %d'
      % (len(cases) - n_raw_clean - n_raw_dirty))
# 段位置分布
front = sum(1 for c in cases if c[4][0] == 0)
back = sum(1 for c in cases if c[4][0] >= (c[6] - 2))
print('  穿模段在**首段**: %d，在**末段**: %d，中间: %d'
      % (front, back, len(cases) - front - back))

out = os.path.join(ROUND, '_evidence', 'penetrate51.json')
os.makedirs(os.path.dirname(out), exist_ok=True)
with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
    json.dump([{'chapter': c[0], 'room': c[1], 'start': c[2], 'goal': c[3],
                'penetration': c[4],
                'raw_penetration': c[5] if c[5] != 'walk_fail' else 'walk_fail',
                'n_points': c[6], 'smoothed': c[7], 'n_points_raw': c[8]}
               for c in cases], fh, ensure_ascii=False, indent=1)
print('明细落盘: %s' % out)

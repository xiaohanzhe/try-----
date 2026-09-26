# -*- coding: utf-8 -*-
"""第51轮 · 分层剥离归因 —— 穿模到底是 `_monotone_forward` 还是 `_despike`。

手法：**只把某一层替换成恒等函数**（其余全真），跑同一个 `plan_walk` 调用，
看穿模数怎么变。这是最保真的归因法 —— 不重写任何算法、不改输入。

  档 0  原样
  档 1  `_monotone_forward` → 恒等
  档 2  `_despike`          → 恒等
  档 3  两者都 → 恒等
  档 4  `smooth_keep_walkable` → 恒等（= 只走 simplify_collinear）

对照矩阵：某层恒等后穿模归零 ⇒ 该层是罪魁。
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

geo_raw = SS._read_json(os.path.join(SS.scenes_dir(), '_room_geometry.json')) or {}
GEO = geo_raw.get('rooms') or {}

# ---- 先收集全部穿模案例（与 patrol51 同一采样口径） ----
def penetrates(path, items):
    """逐段 1px 密集采样，返回第一个穿模段 `(k, p0, p1)` 或 None。"""
    for k in range(len(path) - 1):
        x0, y0 = path[k]
        x1, y1 = path[k + 1]
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(d / 1.0))
        for q in range(n + 1):
            tt = q / float(n)
            if SW.hit_obstacle(items, x0 + (x1 - x0) * tt, y0 + (y1 - y0) * tt):
                return (k, path[k], path[k + 1])
    return None


CAND, MAX_PAIRS = 6, 8
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
                r = SW.plan_walk(num, rid, room_rect, a, b, obstacles=items)
                if not r.get('ok'):
                    continue
                if penetrates(r['path'], items):
                    cases.append((num, rid, room_rect, a, b, items))
print('收集到穿模案例 %d 例' % len(cases))


_OM = SW._monotone_forward
_OD = SW._despike
_OS = SW.smooth_keep_walkable


def ident_mono(out, points, obstacles, bbox_w, bbox_h, step, tol):
    return list(out)


def ident_desp(points, obstacles, bbox_w, bbox_h, step,
               min_turn=SW.DESPIKE_MIN_TURN, passes=SW.DESPIKE_PASSES):
    return list(points)


def ident_smooth(points, obstacles, iterations=3,
                 bbox_w=SW.PLAYER_BBOX_W, bbox_h=SW.PLAYER_BBOX_H,
                 step=SW.GRID_STEP):
    return list(points)


VARIANTS = [
    ('0 原样', lambda: None),
    ('1 monotone=恒等', lambda: setattr(SW, '_monotone_forward', ident_mono)),
    ('2 despike=恒等', lambda: setattr(SW, '_despike', ident_desp)),
    ('3 两者=恒等', lambda: (setattr(SW, '_monotone_forward', ident_mono),
                            setattr(SW, '_despike', ident_desp))),
    ('4 smooth链=恒等', lambda: setattr(SW, 'smooth_keep_walkable', ident_smooth)),
    ('5 simplify=恒等', None),      # 特殊：需要替换 simplify_collinear
]
_OSIM = SW.simplify_collinear


def ident_simplify(points, align=1.0, obstacles=None, bbox_w=SW.PLAYER_BBOX_W,
                   bbox_h=SW.PLAYER_BBOX_H, step=SW.GRID_STEP):
    return list(points)


results = {}
for name, patch in VARIANTS:
    SW._monotone_forward = _OM
    SW._despike = _OD
    SW.smooth_keep_walkable = _OS
    SW.simplify_collinear = _OSIM
    if patch:
        patch()
    if name.startswith('5'):
        SW.simplify_collinear = ident_simplify
    n_pen = 0
    n_ok = 0
    for (num, rid, room_rect, a, b, items) in cases:
        r = SW.plan_walk(num, rid, room_rect, a, b, obstacles=items)
        if not r.get('ok'):
            continue
        n_ok += 1
        if penetrates(r['path'], items):
            n_pen += 1
    results[name] = {'ok': n_ok, 'penetrate': n_pen}
    print('  %-16s 成功 %3d / 仍穿模 %3d' % (name, n_ok, n_pen))

SW._monotone_forward = _OM
SW._despike = _OD
SW.smooth_keep_walkable = _OS
SW.simplify_collinear = _OSIM

print('\n判据（某层恒等后穿模归零 ⇒ 罪在该层）：')
for name in results:
    if name.startswith('0'):
        continue
    if results[name]['penetrate'] == 0 and results[name]['ok'] > 0:
        print('  ★ %s ⇒ 穿模归零' % name)

out = os.path.join(ROUND, '_evidence', 'layer51.json')
os.makedirs(os.path.dirname(out), exist_ok=True)
with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
    json.dump({'n_cases': len(cases), 'variants': results}, fh,
              ensure_ascii=False, indent=1)
print('落盘: %s' % out)

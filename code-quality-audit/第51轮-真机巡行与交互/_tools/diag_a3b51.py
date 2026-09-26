# -*- coding: utf-8 -*-
"""第51轮诊断：`A3b` 报的 1 对劣化（ch1 idx105）到底是产品问题还是判据问题。

对照三份：
  raw   = plan_walk(..., smooth=False)   原折线
  now   = plan_walk(...)                 第47轮平滑（含 monotone+despike）
  head  = 改前版本（HEAD47 证据）
逐点打印 + 逐拐角打印（转角 / 两腿长度 / 是否计入 visible_hard）。
"""
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MOD = os.path.join(PET, 'modules', 'scene_walk.py')
SCENES = os.path.join(PET, 'assets', 'scenes')
HEAD_EV = os.path.join(ROOT, 'code-quality-audit', '第47轮-房间全量与寻路人味化',
                       '_evidence', '_scene_walk_HEAD47.py')

HARD_DEG = 80.0
MIN_LEG = 5.0


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def turn_deg(a, b, c):
    v1 = (b[0] - a[0], b[1] - a[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 < 1e-9 or n2 < 1e-9:
        return 0.0
    c_ = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c_))))


def dump(tag, path):
    n = 0
    print('  --- %s：%d 点 ---' % (tag, len(path)))
    for i in range(len(path)):
        mark = ''
        if 0 < i < len(path) - 1:
            a, b, c = path[i - 1], path[i], path[i + 1]
            l1 = math.hypot(b[0] - a[0], b[1] - a[1])
            l2 = math.hypot(c[0] - b[0], c[1] - b[1])
            t = turn_deg(a, b, c)
            hard = (l1 >= MIN_LEG and l2 >= MIN_LEG and t >= HARD_DEG)
            if hard:
                n += 1
            mark = '  转角=%6.1f° 腿=(%6.2f,%6.2f) %s' % (
                t, l1, l2, '★硬' if hard else '')
        print('    [%2d] (%8.2f, %8.2f)%s' % (i, path[i][0], path[i][1], mark))
    print('  => visible_hard(%s) = %d' % (tag, n))
    return n


def main():
    W = load(MOD, 'walk_now51d')
    H = load(HEAD_EV, 'walk_head51d')
    ch, idx = 1, 105
    geo = json.load(open(os.path.join(SCENES, '_room_geometry.json'),
                         encoding='utf-8'))['rooms']
    g = geo.get('ch%d:%d' % (ch, idx))
    d = W.load_obstacles(ch, SCENES)
    obs = d['rooms'][idx]['items']
    rect = (0.0, 0.0, float(g['w']), float(g['h']))
    pts = []
    for i in range(4):
        for j in range(4):
            x, y = (i + .5) * rect[2] / 4.0, (j + .5) * rect[3] / 4.0
            if not W.blocks_at(obs, x, y):
                pts.append((x, y))
    far = None
    for a in range(len(pts)):
        for b in range(a + 1, len(pts)):
            dd = math.hypot(pts[b][0] - pts[a][0], pts[b][1] - pts[a][1])
            if far is None or dd > far[0]:
                far = (dd, pts[a], pts[b])
    s, t = far[1], far[2]
    print('房间 ch%d:%d  rect=%r  起 %r → 止 %r  障碍 %d 条'
          % (ch, idx, rect, s, t, len(obs)))
    print('障碍明细: %r' % (obs[:12],))
    raw = W.plan_walk(ch, idx, rect, s, t, obstacles=obs, smooth=False)
    now = W.plan_walk(ch, idx, rect, s, t, obstacles=obs)
    head = H.plan_walk(ch, idx, rect, s, t, obstacles=obs)
    a = dump('raw', raw['path'])
    b = dump('now', now['path'])
    c = dump('head', head['path'])
    print()
    print('=== raw=%d  now=%d  head=%d ===' % (a, b, c))
    # 逐段穿模复核
    for tag, p in (('raw', raw['path']), ('now', now['path'])):
        bad = []
        for i in range(len(p) - 1):
            if not W._segment_clear(obs, p[i][0], p[i][1], p[i + 1][0],
                                    p[i + 1][1], W.PLAYER_BBOX_W,
                                    W.PLAYER_BBOX_H, W.GRID_STEP):
                bad.append(i)
        print('  %s 穿模段=%r' % (tag, bad))
    return 0


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""第51轮：为 A3b 找一条**更精确**的判据（不是简单放宽）。

背景：改动后 `visible_hard(now) > visible_hard(raw)` 出现 1 对（ch1:105，2 vs 1）。
先问"这 2 个 81° 拐角是不是**删了会穿墙**的" —— 若是，它们与 A2b 认的
"残留倒走点必须不可删"属同一类正当保留；若否，则是真缺陷，必须去修产品。

本脚本对 193 组配对逐个算：
  visible_hard(p)       —— 现有口径（只看转角 + 腿长）
  removable_hard(p)     —— 新增口径：那些**删掉顶点也不穿墙**的硬拐角数
两者之差就是"必须保留的硬拐角"。
"""
import importlib.util
import io
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


def hard_idx(path):
    out = []
    for i in range(1, len(path) - 1):
        a, b, c = path[i - 1], path[i], path[i + 1]
        l1 = math.hypot(b[0] - a[0], b[1] - a[1])
        l2 = math.hypot(c[0] - b[0], c[1] - b[1])
        if l1 >= MIN_LEG and l2 >= MIN_LEG and turn_deg(a, b, c) >= HARD_DEG:
            out.append(i)
    return out


def seg_clear(W, obs, a, b):
    return W._segment_clear(obs, a[0], a[1], b[0], b[1],
                            W.PLAYER_BBOX_W, W.PLAYER_BBOX_H, W.GRID_STEP)


def removable_hard(W, obs, path):
    """硬拐角里"删掉该顶点也不穿墙"的个数（= 本可以更顺却没顺）。"""
    n = 0
    for i in hard_idx(path):
        if seg_clear(W, obs, path[i - 1], path[i + 1]):
            n += 1
    return n


def build_samples(W):
    geo = json.load(io.open(os.path.join(SCENES, '_room_geometry.json'),
                            'r', encoding='utf-8')).get('rooms') or {}
    out = []
    for ch in (1, 2, 4, 5):
        d = W.load_obstacles(ch, SCENES)
        if not d.get('ok'):
            continue
        for idx in sorted(d['rooms']):
            g = geo.get('ch%d:%d' % (ch, idx))
            obs = d['rooms'][idx]['items']
            if not g or not obs or not g.get('w'):
                continue
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
            if far is None:
                continue
            out.append((ch, idx, rect, far[1], far[2], obs))
    return out


def main():
    W = load(MOD, 'walk_now51r')
    samples = build_samples(W)
    tot = {'raw_hard': 0, 'now_hard': 0, 'raw_rem': 0, 'now_rem': 0}
    worse = []
    for ch, idx, rect, s, t, obs in samples:
        raw = W.plan_walk(ch, idx, rect, s, t, obstacles=obs, smooth=False)
        now = W.plan_walk(ch, idx, rect, s, t, obstacles=obs)
        if not (raw.get('ok') and now.get('ok')):
            continue
        if len(now['path']) < 3 or len(raw['path']) < 3:
            continue
        rh, nh = hard_idx(raw['path']), hard_idx(now['path'])
        rr, nr = removable_hard(W, obs, raw['path']), removable_hard(W, obs, now['path'])
        tot['raw_hard'] += len(rh)
        tot['now_hard'] += len(nh)
        tot['raw_rem'] += rr
        tot['now_rem'] += nr
        if nr > rr:
            worse.append((ch, idx, rr, nr, len(rh), len(nh)))
    print('193 组配对：')
    print('  visible_hard : raw %d → now %d （净 %+d）'
          % (tot['raw_hard'], tot['now_hard'], tot['now_hard'] - tot['raw_hard']))
    print('  removable    : raw %d → now %d （净 %+d）'
          % (tot['raw_rem'], tot['now_rem'], tot['now_rem'] - tot['raw_rem']))
    print()
    print('按新口径"本可删的硬拐角逐对不劣化"的劣化对：%d 组 %r'
          % (len(worse), worse[:6]))
    print()
    print('逐对明细（ch, idx, raw_rem, now_rem, raw_hard, now_hard）：')
    for ch, idx, rect, s, t, obs in samples:
        raw = W.plan_walk(ch, idx, rect, s, t, obstacles=obs, smooth=False)
        now = W.plan_walk(ch, idx, rect, s, t, obstacles=obs)
        if not (raw.get('ok') and now.get('ok')):
            continue
        if len(now['path']) < 3 or len(raw['path']) < 3:
            continue
        rh, nh = hard_idx(raw['path']), hard_idx(now['path'])
        if len(nh) > len(rh):
            print('   ch%d:%-4d raw_rem=%d now_rem=%d raw_hard=%d now_hard=%d'
                  % (ch, idx, removable_hard(W, obs, raw['path']),
                     removable_hard(W, obs, now['path']), len(rh), len(nh)))
            for i in nh:
                a, b, c = now['path'][i - 1], now['path'][i], now['path'][i + 1]
                clr = seg_clear(W, obs, a, c)
                print('      顶点[%d] (%7.2f,%7.2f) 转角=%5.1f° 抄近路可走=%s'
                      % (i, b[0], b[1], turn_deg(a, b, c), clr))
    return 0


if __name__ == '__main__':
    sys.exit(main())

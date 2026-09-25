# -*- coding: utf-8 -*-
"""第47轮探针②：平滑到底让路径**更顺**还是**更楞**（逐对对照 + 拐角画像）。

为什么需要这一份
--------------
探针①给出的"硬拐角总数 355 → 366"**不能直接当结论**：平滑后点数翻了近 10 倍
（Chaikin 三次细分），绝对个数本来就会被放大。必须**逐对**比：

  · 有多少对**变好**（硬拐角变少）；
  · 有多少对**变坏**（硬拐角变多）；
  · 变坏的那些，硬拐角出现在**哪里**（起点/终点附近，还是回退插入点）。

并且把最坏的一例的**转角序列**打出来 —— 直接看"像不像机器人"。
"""
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
sys.path.insert(0, MOD)

import scene_walk as SW      # noqa: E402

HARD = 80.0


def turn_deg(a, b, c):
    v1 = (b[0] - a[0], b[1] - a[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 < 1e-9 or n2 < 1e-9:
        return 0.0
    c_ = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c_))))


def hard_idx(path, thr=HARD):
    return [i for i in range(1, len(path) - 1)
            if turn_deg(path[i - 1], path[i], path[i + 1]) >= thr]


def main():
    out = []
    w = out.append
    w('第47轮探针② · 平滑 vs 原折线：逐对对照（真实房间 / 真实障碍）')
    w('=' * 78)
    geo = json.load(io.open(os.path.join(SCENES, '_room_geometry.json'),
                            'r', encoding='utf-8')).get('rooms') or {}
    tot_pairs = better = worse = same = 0
    worst = None
    for ch in (1, 2, 4, 5):
        data = SW.load_obstacles(ch)
        if not data.get('ok'):
            continue
        rooms = data['rooms']
        for idx in sorted(rooms):
            g = geo.get('ch%d:%d' % (ch, idx))
            obs = rooms[idx]['items']
            if not g or not obs or not g.get('w'):
                continue
            rect = (0.0, 0.0, float(g['w']), float(g['h']))
            pts = [((i + .5) * rect[2] / 4.0, (j + .5) * rect[3] / 4.0)
                   for i in range(4) for j in range(4)
                   if not SW.blocks_at(obs, (i + .5) * rect[2] / 4.0, (j + .5) * rect[3] / 4.0)]
            far = None
            for a in range(len(pts)):
                for b in range(a + 1, len(pts)):
                    d = math.hypot(pts[b][0] - pts[a][0], pts[b][1] - pts[a][1])
                    if far is None or d > far[0]:
                        far = (d, pts[a], pts[b])
            if far is None:
                continue
            s, t = far[1], far[2]
            r_sm = SW.plan_walk(ch, idx, rect, s, t, obstacles=obs)
            r_ra = SW.plan_walk(ch, idx, rect, s, t, obstacles=obs, smooth=False)
            if not r_sm.get('ok') or not r_ra.get('ok'):
                continue
            p_sm, p_ra = r_sm['path'], r_ra['path']
            if len(p_ra) < 3:
                continue
            ns, nr = len(hard_idx(p_sm)), len(hard_idx(p_ra))
            tot_pairs += 1
            if ns < nr:
                better += 1
            elif ns > nr:
                worse += 1
                if worst is None or ns - nr > worst[0]:
                    worst = (ns - nr, ch, idx, nr, ns, p_ra, p_sm)
            else:
                same += 1
    w('可比配对 %d：平滑后更顺 %d / 不变 %d / ★更楞 %d'
      % (tot_pairs, better, same, worse))
    w('判据：若"更楞"占比很高 ⇒ 平滑在**帮倒忙**，必须改。')
    if worst:
        d, ch, idx, nr, ns, p_ra, p_sm = worst
        w('')
        w('★ 最坏一例：ch%d 房%d  原折线硬拐角=%d → 平滑后=%d' % (ch, idx, nr, ns))
        w('  原折线（%d 点）:' % len(p_ra))
        for p in p_ra:
            w('    (%.1f, %.1f)' % p)
        hi = hard_idx(p_sm)
        w('  平滑后（%d 点）硬拐角出现在下标 %r :' % (len(p_sm), hi))
        for i in hi[:12]:
            w('    idx=%-4d 点=%s  转角=%.1f°'
              % (i, ('(%.1f, %.1f)' % p_sm[i]),
                 turn_deg(p_sm[i - 1], p_sm[i], p_sm[i + 1])))
        w('  这些点是否为原折线顶点：%r'
          % [p_sm[i] in [tuple(x) for x in p_ra] for i in hi[:12]])
    text = '\n'.join(out)
    print(text)
    with io.open(os.path.join(HERE, '..', '_evidence', '平滑优劣逐对47.txt'),
                 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())

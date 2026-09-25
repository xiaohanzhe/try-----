# -*- coding: utf-8 -*-
"""第47轮探针：**房间内行走的"机器人感"量化**。

用户口径：「那个寻路要符合真人逻辑，别和机器人一样」。

为什么先量再改
--------------
第45轮已经把「别直角拐弯」做了一轮（Chaikin 平滑 + 保行走简化）。但
**"做了平滑"不等于"看着自然"**：`smooth_keep_walkable` 在修不干净时会
**整条退回原折线**（设计律 3），那时路径就是 A* 的格心锯齿 —— 直角拐弯
原样露出来。所以必须先量：

  · 有多少比例的房间内路径**平滑失败/退回原折线**（= 露出锯齿）；
  · 平滑后还剩多少个「硬拐角」（转角 ≥ 80°）；
  · 格心锯齿的特征（10px 台阶）。

测法（用真实数据、真实量级）
--------------------------
取**有障碍表**的真实房间，在房间矩形内按 4×4 采样出可走点，两两配对，
用 `plan_walk()` 真实规划，统计拐角。**不用手搓夹具当主证据**。

拐角定义：三个连续航点 A→B→C 的方向夹角 ≥ 80° 记一次"硬拐角"。

不联网、不调 Ollama、不需要显示器。
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

HARD_TURN_DEG = 80.0


def turn_deg(a, b, c):
    """A→B→C 在 B 处的转角（0 = 直行，180 = 原路折返）。"""
    v1 = (b[0] - a[0], b[1] - a[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 < 1e-9 or n2 < 1e-9:
        return 0.0
    cosv = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    cosv = max(-1.0, min(1.0, cosv))
    return math.degrees(math.acos(cosv))


def count_hard(path, thr=HARD_TURN_DEG):
    n = 0
    for i in range(1, len(path) - 1):
        if turn_deg(path[i - 1], path[i], path[i + 1]) >= thr:
            n += 1
    return n


def main():
    out = []
    w = out.append
    w('第47轮探针 · 房间内行走"机器人感"量化（真实障碍表 + 真实房间尺寸）')
    w('=' * 74)

    total_rooms = 0
    planned = 0
    bailed_or_unsmoothed = 0
    raw_hard_total = 0
    out_hard_total = 0
    worst = []

    for ch in (1, 2, 4, 5):
        data = SW.load_obstacles(ch)
        if not data.get('ok'):
            w('ch%d 障碍表不可用：%s' % (ch, data.get('error')))
            continue
        rooms = data['rooms']
        geo_path = os.path.join(SCENES, '_room_geometry.json')
        geo = json.load(io.open(geo_path, 'r', encoding='utf-8')).get('rooms') or {}
        ch_rooms = 0
        ch_pairs = 0
        ch_bail = 0
        ch_raw = 0
        ch_out = 0
        for idx in sorted(rooms):
            gkey = 'ch%d:%d' % (ch, idx)
            g = geo.get(gkey)
            if not g or g.get('w') is None:
                continue
            rect = (0.0, 0.0, float(g['w']), float(g['h']))
            obs = rooms[idx]['items']
            if not obs:
                continue                 # 无障碍的房间全是直线，没有拐角可谈
            total_rooms += 1
            ch_rooms += 1
            # 4×4 采样
            pts = []
            for i in range(4):
                for j in range(4):
                    x = rect[2] * (i + 0.5) / 4.0
                    y = rect[3] * (j + 0.5) / 4.0
                    if not SW.blocks_at(obs, x, y):
                        pts.append((x, y))
            # ★ 只取"最远的一对"：房间越远越能暴露绕障碍的锯齿；
            #   每房 120 对 × 两趟规划会跑到天荒地老（实测被 SIGTERM）。
            far = None
            for a_i in range(len(pts)):
                for b_i in range(a_i + 1, len(pts)):
                    s, t = pts[a_i], pts[b_i]
                    d = math.hypot(t[0] - s[0], t[1] - s[1])
                    if far is None or d > far[0]:
                        far = (d, s, t)
            for s, t in ([] if far is None else [(far[1], far[2])]):
                r = SW.plan_walk(ch, idx, rect, s, t, obstacles=obs)
                if not r.get('ok') or len(r.get('path') or []) < 3:
                    continue
                planned += 1
                ch_pairs += 1
                if not r.get('smoothed'):
                    bailed_or_unsmoothed += 1
                    ch_bail += 1
                nh = count_hard(r['path'])
                out_hard_total += nh
                ch_out += nh
                r0 = SW.plan_walk(ch, idx, rect, s, t, obstacles=obs, smooth=False)
                n0 = count_hard(r0.get('path') or []) if r0.get('ok') else 0
                raw_hard_total += n0
                ch_raw += n0
                if nh >= 2:
                    worst.append((nh, ch, idx, len(r['path']), nh == n0))
        w('ch%-2d 有障碍房间 %3d  可规划配对 %4d  未平滑(=露出锯齿) %4d (%.1f%%)  '
          '硬拐角 原折线 %4d → 平滑后 %4d'
          % (ch, ch_rooms, ch_pairs, ch_bail,
             (100.0 * ch_bail / ch_pairs) if ch_pairs else 0.0, ch_raw, ch_out))

    w('-' * 74)
    w('合计：有障碍房间 %d  可规划配对 %d' % (total_rooms, planned))
    w('      平滑退化为原折线 %d (%.1f%%)'
      % (bailed_or_unsmoothed,
         (100.0 * bailed_or_unsmoothed / planned) if planned else 0.0))
    w('      硬拐角(≥%.0f°)：原折线 %d → 平滑后 %d' % (HARD_TURN_DEG, raw_hard_total, out_hard_total))
    if planned:
        w('      平均每对：原 %.3f → 平滑后 %.3f 个硬拐角'
          % (raw_hard_total / float(planned), out_hard_total / float(planned)))
    worst.sort(reverse=True)
    w('')
    w('★ 平滑后仍有 ≥2 个硬拐角的样例（前 10 条）—— 这就是"机器人感"的残留：')
    for nh, ch, idx, npts, same in worst[:10]:
        w('  ch%d 房%d  硬拐角=%d  航点=%d  与原折线相同=%s' % (ch, idx, nh, npts, same))
    if not worst:
        w('  （无 —— 平滑后所有可比配对都不再有 ≥2 个硬拐角）')

    text = '\n'.join(out)
    print(text)
    dest = os.path.join(HERE, '..', '_evidence', '房内行走机器人感量化47.txt')
    with io.open(dest, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())

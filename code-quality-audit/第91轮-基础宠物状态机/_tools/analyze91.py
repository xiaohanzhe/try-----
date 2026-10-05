# -*- coding: utf-8 -*-
"""第91轮：把 monitor91.py 的产物转成「用户视角」判据。

输入 = monitor91.py 的 outdir（timeline.tsv + f####.png）。
输出 = 两组判据：
  A. **轨迹**（几何，Win32 矩形为准；透明分层窗口下这是唯一可信的运动判据）
     · 采样数 / 窗口丢失次数 / 唯一位置数 / 位移次数 / 总路程 / 最大单步
     · 判据 M1「窗口在整个监控期内一直存在」（丢失 0 次）
     · 判据 M2「宠物确实动过」（唯一位置数 > 1 或 总路程 > 0）
  B. **外观**（裁剪帧的相邻差分；用户提的「对比前后帧判定移动」）
     · 帧数 / 平均差分 / 显著变化的帧对数 / 最大差分
     · 判据 V1「画面有变化」（显著帧对 > 0）
说明：帧是按窗口矩形裁剪并放大 2 倍的，所以**位置一变，整帧都会不同** ——
      这不是缺陷，而是"动过"的独立证据（与 M2 互为交叉验证）。
"""
import glob
import os
import sys

import numpy as np
import cv2


def imread_u(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\23002\Downloads\_tmp\mon91'
    ts = os.path.join(d, 'timeline.tsv')
    print('产物目录: %s' % d)
    if not os.path.exists(ts):
        print('★ 找不到 timeline.tsv，监控没跑成'); return 1

    ts_rows, lost, n = [], 0, 0
    with open(ts, encoding='utf-8') as f:
        f.readline()
        for ln in f:
            parts = ln.rstrip('\n').split('\t')
            if len(parts) < 11:
                continue
            n += 1
            if parts[1] == '-':
                lost += 1
                continue
            ts_rows.append((float(parts[0]), int(parts[5]), int(parts[6]),
                            int(parts[7]), int(parts[8]), parts[3], parts[4]))

    print('\n===== A. 轨迹（几何） =====')
    print('采样 %d 次 · 窗口不存在 %d 次 · 有效矩形 %d 条' % (n, lost, len(ts_rows)))
    if ts_rows:
        pos = [(r[1], r[2]) for r in ts_rows]
        uniq = len(set(pos))
        moves, dist, mx = 0, 0.0, 0.0
        for (x0, y0), (x1, y1) in zip(pos, pos[1:]):
            dx, dy = x1 - x0, y1 - y0
            if dx or dy:
                moves += 1
                s = (dx * dx + dy * dy) ** 0.5
                dist += s
                mx = max(mx, s)
        print('唯一位置 %d 个 · 位移次数 %d · 总路程 %.0f px · 最大单步 %.0f px'
              % (uniq, moves, dist, mx))
        print('X 范围 %d..%d  Y 范围 %d..%d'
              % (min(p[0] for p in pos), max(p[0] for p in pos),
                 min(p[1] for p in pos), max(p[1] for p in pos)))
        print('[判据 M1] 窗口全程存在（丢失=0）        : %s' % ('PASS' if lost == 0 else 'FAIL 丢 %d 次' % lost))
        print('[判据 M2] 宠物确实动过（唯一位置>1）    : %s' % ('PASS' if uniq > 1 else 'FAIL 全程静止=站桩'))
    else:
        print('★ 没有任何有效矩形 ⇒ 宠物窗口从未出现')

    print('\n===== B. 外观（相邻帧差分） =====')
    frames = sorted(glob.glob(os.path.join(d, 'f*.png')))
    print('裁剪帧 %d 张' % len(frames))
    if len(frames) >= 2:
        diffs = []
        for a, b in zip(frames, frames[1:]):
            ia, ib = imread_u(a), imread_u(b)
            if ia is None or ib is None:
                continue
            if ia.shape != ib.shape:
                diffs.append(255.0)
                continue
            diffs.append(float(np.abs(ia.astype(np.int16) - ib.astype(np.int16)).mean()))
        if diffs:
            sig = sum(1 for x in diffs if x > 6.0)
            print('平均差分 %.2f · 显著变化的帧对 %d/%d · 最大 %.2f'
                  % (np.mean(diffs), sig, len(diffs), max(diffs)))
            print('[判据 V1] 画面有变化（显著帧对>0）     : %s' % ('PASS' if sig > 0 else 'FAIL 帧全同'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

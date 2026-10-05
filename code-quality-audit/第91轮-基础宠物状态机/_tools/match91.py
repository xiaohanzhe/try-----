# -*- coding: utf-8 -*-
"""第91轮：把监控帧缩回原始尺寸，与 deltarune_ralsei/ 下的精灵逐一做像素匹配，
判出监控期宠物到底在播**哪个**动画（sleep? idle? walk?）—— 这是「睡眠动画是否生效」的硬判据。

注意：
  · 监控帧是 PrintWindow 抓的窗口内容（BGRA），已放大 5 倍 ⇒ 先 NEAREST 缩回。
  · 只比较精灵**非透明**像素（透明区域抓屏为黑，不可比）。
  · 尺寸先过滤（±2px），避免拿姿态完全不同的帧去比。
"""
import glob
import os
import sys

import cv2
import numpy as np

D = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\deltarune_ralsei'
M = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\23002\Downloads\_tmp\mon91c'
SCALE = int(sys.argv[2]) if len(sys.argv) > 2 else 5


def rd(p):
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_UNCHANGED)


cands = {}
for n in sorted(os.listdir(D)):
    if n.startswith('spr_ralsei_') and n.endswith('.png'):
        im = rd(os.path.join(D, n))
        if im is not None and im.ndim == 3 and im.shape[2] == 4:
            cands[n] = im
print('候选精灵 %d 张' % len(cands))


def match(fp):
    im = rd(fp)
    h, w = im.shape[0] // SCALE, im.shape[1] // SCALE
    small = cv2.resize(im, (w, h), interpolation=cv2.INTER_NEAREST)
    if small.shape[2] == 4:
        small = small[:, :, :3]
    res = []
    for n, c in cands.items():
        ch, cw = c.shape[0], c.shape[1]
        if abs(cw - w) > 2 or abs(ch - h) > 2:
            continue
        cimg = cv2.resize(c[:, :, :3], (w, h), interpolation=cv2.INTER_NEAREST)
        mask = cv2.resize(c[:, :, 3], (w, h), interpolation=cv2.INTER_NEAREST) > 0
        if mask.sum() < 10:
            continue
        d = float(np.abs(small.astype(np.int16)[mask] - cimg.astype(np.int16)[mask]).mean())
        res.append((d, n))
    res.sort()
    return res[:3]


frames = sorted(glob.glob(os.path.join(M, 'f*.png')))
print('监控帧 %d 张' % len(frames))
print('%-10s %-9s %s' % ('frame', 'size', 'best 3 (差异, 精灵名)'))
pick = [0, 1, len(frames) // 2, len(frames) - 2, len(frames) - 1]
for i in pick:
    f = frames[i]
    im = rd(f)
    w, h = im.shape[1] // SCALE, im.shape[0] // SCALE
    print('%-10s %-9s %s' % (os.path.basename(f), '%dx%d' % (w, h), match(f)))

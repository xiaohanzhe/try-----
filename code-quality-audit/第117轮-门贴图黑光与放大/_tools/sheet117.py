# -*- coding: utf-8 -*-
u"""sheet117.py —— 把 `rec117.avi` 变成**能一眼看懂的逐帧拼图**（用户：「录屏逐帧检查」）。

产物（两类，去向不同）
----------------------
  · `doors117_track_A~D.png` —— **只含门自己那块矩形**的逐帧竖条（194×129 一格）。
    不含桌面/壁纸/图标 ⇒ 可以直接入库给人看。每格下面标帧号与时刻。
  · `shot117_rec_full_track.png` —— 全屏缩略四联（看整体：桌宠/对话框/四门同时在场）。
    ★ 文件名带 `_full` ⇒ 命中 `.gitignore` 的 `shot*_full*.png`，**只在本地留**
      （公开仓库 + 整屏含桌面隐私，理由同 §90/§96/§98）。

为什么不是"随便截两张"
----------------------
用户要的是**逐帧**。所以拼图按**等间隔时间轴**取格，而不是挑好看的：
  门 A 轨道取第 0 帧（门还没画上）+ 之后每隔若干帧 ⇒ 能直接看出"门是在第 1 帧出现的，
  之后再没变"；门 B 轨道跨 P1/P2 ⇒ 能直接看出"P1 被对话框盖、P2 露出本体"。
"""
import io
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROUND, '_evidence', 'rec117')
AVI = os.path.join(OUT, 'rec117.avi')

RECT = {'A': (1183, 0, 194, 129), 'B': (1183, 1399, 194, 129),
        'C': (0, 714, 45, 100), 'D': (2378, 685, 182, 157)}

cap = cv2.VideoCapture(AVI)
frames = []
while True:
    got, f = cap.read()
    if not got:
        break
    frames.append(f[:, :, ::-1])          # BGR -> RGB
cap.release()
N = len(frames)
print('[sheet117] 帧数 %d' % N)

PICK = [0, 1, 3, 8, 14, 20, 30, 45]
PICK = [i for i in PICK if i < N]
LABEL = {0: 't0 (门未画上)', 1: 't1 门出现', 20: 'P2 起(对话框已收)'}


def strip(letter, path):
    x, y, w, h = RECT[letter]
    pad, cap_h = 6, 16
    W = len(PICK) * (w + pad) + pad
    H = h + cap_h + pad * 2
    canvas = Image.new('RGB', (W, H), (24, 24, 28))
    dr = ImageDraw.Draw(canvas)
    for k, i in enumerate(PICK):
        sub = frames[i][max(0, y):y + h, max(0, x):x + w]
        im = Image.fromarray(sub.astype(np.uint8))
        canvas.paste(im, (pad + k * (w + pad), pad))
        dr.text((pad + k * (w + pad), pad + h + 2),
                '#%d' % i, fill=(200, 200, 200))
    canvas.save(path)
    print('[sheet117] -> %s (%dx%d)' % (os.path.basename(path), W, H))


for Lt in 'ABCD':
    strip(Lt, os.path.join(OUT, 'doors117_track_%s.png' % Lt))

# 全屏四联（缩到 1/4，仅本地）
sel = [i for i in (1, 6, 12, 21) if i < N]
tw = frames[0].shape[1] // 4
th = frames[0].shape[0] // 4
sheet = Image.new('RGB', (tw * 2 + 12, th * 2 + 12), (16, 16, 18))
for k, i in enumerate(sel):
    im = Image.fromarray(frames[i].astype(np.uint8)).resize((tw, th), Image.LANCZOS)
    sheet.paste(im, (4 + (k % 2) * (tw + 4), 4 + (k // 2) * (th + 4)))
sp = os.path.join(OUT, 'shot117_rec_full_track.png')
sheet.save(sp)
print('[sheet117] -> %s（整屏，仅本地不入库）' % os.path.basename(sp))

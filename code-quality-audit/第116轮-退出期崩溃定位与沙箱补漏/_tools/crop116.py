# -*- coding: utf-8 -*-
u"""crop116.py —— 按给定帧号裁**对话框区域**（2 倍放大，纵向叠一张长图）供人眼比对。

跑法： set FRAMES=0,9,51,52,73,108,109,135
        C:\\Python311\\python.exe crop116.py
"""
import os
import shutil
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROUND, '_evidence', 'rec116')
ANA = os.path.join(OUT, 'analysis')
os.makedirs(ANA, exist_ok=True)
TMP = r'E:\Download\_tmp\rec116_ascii'
os.makedirs(TMP, exist_ok=True)
src = os.path.join(TMP, 'rec116.avi')
if not os.path.exists(src):
    shutil.copy2(os.path.join(OUT, 'rec116.avi'), src)

FR = [int(x) for x in (os.environ.get('FRAMES') or
                       '0,2,9,51,52,73,108,109,135').split(',')]
PAD = int(os.environ.get('PAD') or '40')
SCALE = float(os.environ.get('SCALE') or '2')
# 对话框矩形（并集）(970,1341,620,261)
DX, DY, DW, DH = 970, 1341, 620, 261

cap = cv2.VideoCapture(src)
tiles = []
i = 0
while True:
    ok, f = cap.read()
    if not ok:
        break
    if i in FR:
        H, W = f.shape[:2]
        x0, y0 = max(0, DX - PAD), max(0, DY - PAD)
        x1, y1 = min(W, DX + DW + PAD), min(H, DY + DH + PAD)
        c = np.ascontiguousarray(f[y0:y1, x0:x1])
        c = cv2.resize(c, (int(c.shape[1] * SCALE), int(c.shape[0] * SCALE)),
                       interpolation=cv2.INTER_NEAREST)
        cv2.putText(c, 'f%d  op=? ' % i, (8, 26), cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (0, 0, 255), 2, cv2.LINE_AA)
        tiles.append(c)
    i += 1
cap.release()
if not tiles:
    sys.stdout.write('no frames\n')
    sys.exit(1)
wmax = max(t.shape[1] for t in tiles)
tiles = [cv2.copyMakeBorder(t, 0, 0, 0, wmax - t.shape[1],
                            cv2.BORDER_CONSTANT, value=(60, 60, 60))
         for t in tiles]
sheet = np.vstack(tiles)
p = os.path.join(ANA, 'dlg_zoom.png')
ok, buf = cv2.imencode('.png', sheet)
if ok:
    with open(p, 'wb') as fh:
        fh.write(buf.tobytes())
if os.path.exists(p):
    sys.stdout.write('written %s  %dx%d  %d bytes\n'
                     % (p, sheet.shape[1], sheet.shape[0],
                        os.path.getsize(p)))
else:
    sys.stdout.write('WRITE-FAIL %s\n' % p)

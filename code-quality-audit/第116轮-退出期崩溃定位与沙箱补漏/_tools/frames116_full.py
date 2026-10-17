# -*- coding: utf-8 -*-
u"""frames116_full.py —— 从 rec116.avi 抽**整屏**帧（供人眼判"黑底/门形式/闪"）。"""
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

PICK = [int(x) for x in (os.environ.get('PICK') or
                         '0,9,51,52,73,80,82,108,109,120,135').split(',')]
cap = cv2.VideoCapture(src)
i = 0
saved = []
while True:
    ok, f = cap.read()
    if not ok:
        break
    if i in PICK:
        small = cv2.resize(f, (1280, 800), interpolation=cv2.INTER_AREA)
        p = os.path.join(ANA, 'full_f%03d.png' % i)
        # ★ cv2.imwrite 在中文路径下静默失败 ⇒ imencode + 手动写盘 + 查盘
        ok, buf = cv2.imencode('.png', small)
        if ok:
            with open(p, 'wb') as fh:
                fh.write(buf.tobytes())
        if os.path.exists(p) and os.path.getsize(p) > 0:
            saved.append((p, os.path.getsize(p)))
        else:
            sys.stdout.write('WRITE-FAIL f%03d\n' % i)
    i += 1
cap.release()
sys.stdout.write('saved %d: %s\n' % (len(saved), ', '.join(
    '%s(%d)' % (os.path.basename(x), s) for x, s in saved)))

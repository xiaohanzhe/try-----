# -*- coding: utf-8 -*-
u"""ab116_dlg.py —— **改前 / 改后**两版录像的同判据定量对照（回答"是不是我改出来的"）。

判据
----
  P1 对话框**下半截**（输入框那一行）的黑占比逐帧序列：
     · 框完整 ⇒ 该带基本是黑的（输入框黑底 + 白框线）
     · 框被截断 ⇒ 露出**浅色任务栏** ⇒ 黑占比骤降
     ⇒ 用"低于阈值"的帧数衡量"截断/闪"的频率。
  P2 门 C 矩形黑占比（改后应≈0：alpha=0.14 虚化；改前≈0.73 实心黑）。
  P3 门 D 矩形黑占比（改后仍应≈0.72：alpha 恒 1.0 ⇒ **本轮未解决**）。

★ 两版录像都用 ASCII 路径（FFmpeg；中文路径不可靠）。
"""
import os
import shutil
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROUND, '_evidence', 'rec116')
TMP = r'E:\Download\_tmp\rec116_ab'
os.makedirs(TMP, exist_ok=True)

SRC = {
    'BEFORE': r'E:\Download\_tmp\rec116_before.avi',
    'AFTER': os.path.join(OUT, 'rec116.avi'),
}
# 对话框矩形（改前/改后都是 (970,1360,620,236)；下半截取输入行那一条）
DLG = (970, 1360, 620, 236)
BOT = (990, 1500, 580, 90)          # 输入框那一带
DOORS = {'C': (0, 762, 33, 75), 'D': (2423, 741, 137, 118),
         'A': (1263, 0, 33, 42)}


def _black(region, thr=16):
    if region is None or region.size == 0:
        return None
    return float((region.max(axis=2) < thr).mean())


def _crop(a, r):
    x, y, w, h = r
    H, W = a.shape[:2]
    return np.ascontiguousarray(a[max(0, y):min(H, y + h),
                                  max(0, x):min(W, x + w)])


def main():
    out = []

    def w(s=''):
        out.append(s)

    for tag, p in SRC.items():
        if not os.path.exists(p):
            w(u'%s 录像不在：%s' % (tag, p))
            continue
        dst = os.path.join(TMP, tag + '.avi')
        shutil.copy2(p, dst)
        cap = cv2.VideoCapture(dst)
        bot, doorC, doorD, doorA = [], [], [], []
        n = 0
        while True:
            ok, f = cap.read()
            if not ok:
                break
            bot.append(_black(_crop(f, BOT)))
            doorC.append(_black(_crop(f, DOORS['C'])))
            doorD.append(_black(_crop(f, DOORS['D'])))
            doorA.append(_black(_crop(f, DOORS['A'])))
            n += 1
        cap.release()
        b = np.array([v for v in bot if v is not None], dtype=float)
        # 判"截断"：该带黑占比明显低于本段中位 ⇒ 下半截没画出来
        med = float(np.median(b))
        cut = int((b < max(0.05, med * 0.5)).sum())
        # 帧间摆动次数（>0.3 视为一次跳）
        d = np.abs(np.diff(b))
        flips = int((d > 0.3).sum())
        w(u'\n=== %s  n=%d ===' % (tag, n))
        w(u'  P1 下半截黑占比: 中位=%.3f  min=%.3f  max=%.3f'
          % (med, b.min(), b.max()))
        w(u'     <中位一半 的帧数 = %d/%d（= 下半截没画出来）' % (cut, len(b)))
        w(u'     帧间摆动 >0.3 次数 = %d' % flips)
        for L, arr in (('A', doorA), ('C', doorC), ('D', doorD)):
            a2 = np.array([v for v in arr if v is not None], dtype=float)
            w(u'  P2/P3 门%s 黑占比: 中位=%.3f  min=%.3f  max=%.3f'
              % (L, float(np.median(a2)), a2.min(), a2.max()))
        # 前 12 帧的下半截序列（看摆动形态）
        w(u'     前 12 帧下半截 = %s' % ['%.2f' % v for v in b[:12]])

    txt = u'\n'.join(out) + u'\n'
    sp = os.path.join(OUT, 'analysis', 'ab_report.txt')
    with open(sp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    sys.stdout.write(txt.encode('utf-8', 'replace').decode('utf-8', 'replace'))
    return 0


if __name__ == '__main__':
    sys.exit(main())

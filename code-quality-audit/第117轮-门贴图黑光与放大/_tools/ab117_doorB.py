# -*- coding: utf-8 -*-
u"""ab117_doorB.py —— 门 B（Niko 的家）在**对话框开着/关着**时的 1:1 对照。

为什么
------
录屏判据 V13 只用**矩形包含**算出"对话框盖住门 B 的 100%"。矩形包含是几何事实，
但它**证明不了"看不见"** —— 如果对话框是半透明面板，门 B 仍会透出来。
⇒ 把两种状态各裁一张**不缩放、带 60 px 上下文**的图并排看，才是"看不看得见"的事实。

产出：`_evidence/rec117/ab117_doorB.png`（上=对话框开 / 下=对话框关）

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第117轮-门贴图黑光与放大\\_tools\\ab117_doorB.py
"""
import csv
import io
import os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROUND, '_evidence', 'rec117')
AVI = os.path.join(OUT, 'rec117.avi')
CSV_F = os.path.join(OUT, 'rec117_frames.csv')
PAD = 60


def main():
    rows = list(csv.DictReader(io.open(CSV_F, 'r', encoding='utf-8')))
    import cv2
    cap = cv2.VideoCapture(AVI)
    frames = []
    while True:
        got, f = cap.read()
        if not got:
            break
        frames.append(f[:, :, ::-1])
    cap.release()
    if len(frames) != len(rows):
        raise SystemExit('帧数与 CSV 不等 ⇒ 停止（不猜）')

    on = [i for i, r in enumerate(rows) if r.get('dlg_vis') == '1' and float(r.get('dlg_op') or 0) > 0.9]
    off = [i for i, r in enumerate(rows) if r.get('phase') == 'P2' and r.get('dlg_vis') == '0']
    if not on or not off:
        raise SystemExit('找不到"对话框开/关"各一帧（on=%s off=%s）' % (on[:3], off[:3]))
    picks = [(on[-1], 'dialogue VISIBLE'), (off[-1], 'dialogue hidden')]

    x, y, w, h = (int(rows[0]['B_x']), int(rows[0]['B_y']),
                  int(rows[0]['B_w']), int(rows[0]['B_h']))
    f0 = frames[0]
    y0, y1 = max(0, y - PAD), min(f0.shape[0], y + h + PAD)
    x0, x1 = max(0, x - PAD), min(f0.shape[1], x + w + PAD)
    tw, th = x1 - x0, y1 - y0

    canvas = Image.new('RGB', (tw, (th + 26) * len(picks)), (20, 20, 24))
    dr = ImageDraw.Draw(canvas)
    for i, (idx, label) in enumerate(picks):
        yy = i * (th + 26)
        crop = frames[idx][y0:y1, x0:x1]
        canvas.paste(Image.fromarray(crop.astype(np.uint8)), (0, yy + 26))
        dr.text((6, yy + 7),
                'door B  %s  (frame %d, canvas %dx%d, 1:1 no rescale)'
                % (label, idx, x, y), fill=(230, 230, 230))
    p = os.path.join(OUT, 'ab117_doorB.png')
    canvas.save(p)
    print('written %s  %dx%d  (on=%d off=%d)' % (p, canvas.width, canvas.height, on[-1], off[-1]))


if __name__ == '__main__':
    main()

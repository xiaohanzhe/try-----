# -*- coding: utf-8 -*-
u"""把 2560x1600 全屏截图裁成"能看清"的小图（用户要看成品）。

★ 为什么必须裁：全屏 PNG 3.6MB，注入给模型会被压缩到看不清。
  目标是**人眼可核对**：桌宠本体 + 场景画布两块。
"""
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
SH = os.path.join(HERE, '..', '_evidence', 'shots')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QImage

app = QApplication.instance() or QApplication([])

name = sys.argv[1] if len(sys.argv) > 1 else 'mon89_10_204006.png'
src = os.path.join(SH, name)
img = QImage(src)
print('src', img.width(), img.height())

# ---- 1. 右下角区域（桌宠默认落点附近）----
W, H = img.width(), img.height()
regions = {
    'r_bottomright': QRect(int(W * 0.60), int(H * 0.62), int(W * 0.40), int(H * 0.38)),
    'r_center': QRect(int(W * 0.30), int(H * 0.25), int(W * 0.45), int(H * 0.50)),
}
for tag, r in regions.items():
    crop = img.copy(r)
    # 缩放到宽 900（保持可读）
    tgt_w = 900
    crop = crop.scaledToWidth(tgt_w)
    out = os.path.join(SH, '%s_%s.png' % (os.path.splitext(name)[0], tag))
    crop.save(out, 'PNG')
    print('crop ->', out, crop.width(), crop.height())

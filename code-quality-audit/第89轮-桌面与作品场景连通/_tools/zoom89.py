# -*- coding: utf-8 -*-
u"""放大对话框的名字区域，核对拼写（第89轮：RALSEI vs RALSEI 一字之差看不出来）。"""
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
SH = os.path.join(HERE, '..', '_evidence', 'shots')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QImage

app = QApplication.instance() or QApplication([])
name = sys.argv[1]
img = QImage(os.path.join(SH, name))
print('src', img.width(), img.height())
# 名字区域：对话框 620x255 里，名字约在 x 110..400, y 40..90
r = QRect(100, 30, 320, 70)
crop = img.copy(r)
crop = crop.scaled(crop.width() * 4, crop.height() * 4)
out = os.path.join(SH, 'zoom_name.png')
crop.save(out, 'PNG')
print('->', out, crop.width(), crop.height())

# 台词区域
r2 = QRect(100, 90, 520, 100)
c2 = img.copy(r2)
c2 = c2.scaled(c2.width() * 2, c2.height() * 2)
o2 = os.path.join(SH, 'zoom_line.png')
c2.save(o2, 'PNG')
print('->', o2)

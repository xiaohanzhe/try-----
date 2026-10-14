# -*- coding: utf-8 -*-
"""第114轮 · 录像整理（**给用户"一眼看录像"用**）。三件事，按顺序做：

  ① **桌宠特写**：从报告里读 `pet_geo`（窗口几何），按它裁一块放大 4 倍
     ⇒ `dbg114_pet_zoom.png`。★ 为什么必须用**几何**裁而不是靠眼睛找：
       桌宠是**透明分层窗口**，抓屏里"看不出它在哪"（本项目 §73.8 已裁定：
       可见面积失效、几何仍准）。
  ② **等比缩小**：真机抓的是主屏物理尺寸（本机 2560x1600），每帧 PNG 8.6 MB、
     6 帧 52 MB；历史惯例（第109/111轮）是每轮证据 15~18 MB ⇒ 缩到宽 1280
     （信息量不变：本轮的帧只用于看"桌面上没有多出窗口 / 没有切场景 / 没有崩"）。
  ③ **联系表**：6 帧拼 3x2 一张图，便于一眼扫完。
★ 只缩放/裁切，**不修图**；所有变换在 EVIDENCE.md 里如实写明。
"""
import json
import os
import sys

from PyQt5.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtGui import QImage, QPainter, QColor, QFont  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.abspath(os.path.join(HERE, '..', '_evidence'))
FR = os.path.join(EV, 'frames114')
RPT = os.path.join(EV, 'rec114_report.json')
TARGET_W = 1280
CELL_W = 620
COLS, PAD, LABEL_H = 3, 12, 26

# ---------------------------------------------------------------- ① 桌宠特写
print('== ① 桌宠特写（按报告里的窗口几何裁）==')
geo, tag = None, None
try:
    with open(RPT, encoding='utf-8') as fh:
        rpt = json.load(fh)
    for s in rpt.get('snaps') or []:
        if s.get('pet_geo') and s.get('png'):
            geo, tag = s['pet_geo'], s.get('tag')
            if s.get('tag') == 'k004_working':
                break
except Exception as e:
    print('   [warn] 读报告失败: %r' % (e,))

if geo and tag:
    src = os.path.join(FR, '%s.png' % tag)
    if os.path.isfile(src):
        im = QImage(src)
        m = 50                      # 四周各留 50px 余量（看得见"站在桌面上"）
        x = max(0, geo[0] - m)
        y = max(0, geo[1] - m)
        w = min(im.width() - x, geo[2] + 2 * m)
        h = min(im.height() - y, geo[3] + 2 * m)
        k = max(1, min(4, 560 // max(1, w)))
        c = im.copy(x, y, w, h)
        c = c.scaled(c.width() * k, c.height() * k,
                     Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        out = os.path.join(FR, 'dbg114_pet_zoom.png')
        c.save(out, 'PNG')
        print('   源帧 %s  几何=%s  裁 (%d,%d,%d,%d) x%d  -> %s  %dx%d  %.1f KB'
              % (tag, geo, x, y, w, h, k, os.path.basename(out),
                 c.width(), c.height(), os.path.getsize(out) / 1024.0))
    else:
        print('   [skip] 源帧不存在: %s' % src)
else:
    print('   [skip] 报告里没有 pet_geo')

# ---------------------------------------------------------------- ② 等比缩小
print('\n== ② 等比缩小到宽 %d ==' % TARGET_W)
files = sorted(f for f in os.listdir(FR)
               if f.lower().endswith('.png')
               and not f.startswith('contact_')
               and not f.startswith('dbg'))
if not files:
    print('[FATAL] 没有帧可整理: %s' % FR)
    sys.exit(2)
kept = []
for f in files:
    p = os.path.join(FR, f)
    img = QImage(p)
    if img.isNull():
        print('   [skip] 读不出: %s' % f)
        continue
    b0 = os.path.getsize(p)
    out = img.scaledToWidth(TARGET_W, Qt.SmoothTransformation) \
        if img.width() > TARGET_W else img
    okk = out.save(p, 'PNG')
    b1 = os.path.getsize(p)
    kept.append((f, out.width(), out.height()))
    print('   %-34s %dx%d  %5.2f MB -> %5.2f MB  saved=%s'
          % (f, out.width(), out.height(), b0 / 1048576.0,
             b1 / 1048576.0, okk))

# ---------------------------------------------------------------- ③ 联系表
rows = (len(kept) + COLS - 1) // COLS
cell_h = int(round(CELL_W * kept[0][2] / float(kept[0][1])))
W = COLS * CELL_W + (COLS + 1) * PAD
H = rows * (cell_h + LABEL_H) + (rows + 1) * PAD
sheet = QImage(W, H, QImage.Format_RGB32)
sheet.fill(QColor('#101014'))
pt = QPainter(sheet)
try:
    pt.setFont(QFont('Microsoft YaHei', 11))
    for i, (f, fw, fh) in enumerate(kept):
        r, c = divmod(i, COLS)
        x = PAD + c * (CELL_W + PAD)
        y = PAD + r * (cell_h + LABEL_H + PAD)
        thumb = QImage(os.path.join(FR, f)).scaled(
            CELL_W, cell_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pt.drawImage(x + (CELL_W - thumb.width()) // 2,
                     y + (cell_h - thumb.height()) // 2, thumb)
        pt.setPen(QColor('#e8e8f0'))
        pt.drawText(x, y + cell_h + 4, CELL_W, LABEL_H,
                    int(Qt.AlignLeft | Qt.AlignVCenter), f)
finally:
    pt.end()
sp = os.path.join(FR, 'contact_114.png')
sheet.save(sp, 'PNG')
print('\n== ③ 联系表 ==\n   %s  %dx%d  %.2f MB'
      % (sp, sheet.width(), sheet.height(), os.path.getsize(sp) / 1048576.0))
tot = sum(os.path.getsize(os.path.join(FR, f)) for f in os.listdir(FR))
print('frames114 目录合计 %.2f MB' % (tot / 1048576.0))

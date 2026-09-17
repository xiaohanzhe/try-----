# -*- coding: utf-8 -*-
"""第十八轮证据：把三组攀爬素材**用真 loader 渲染**成一张对照图。

为什么值得单独做一张图：
  「加进动画表」与「运行时真的能画出这几张图」是两件事 —— 素材名打错、PNG 不在
  磁盘上、或组名没被登记，`change_animation` 都会退回占位图（灰底"?"），而**断言
  一个字符串是搜不出来的**。这里直接把 `SpriteLoader` 加载出来的 QPixmap 画出来：
  是灰块还是攀爬姿势，一眼就能看出来（用户口径里的"别切灰块"）。

同时把 `jump` / `idle` 放进同一张图当**标尺**：攀爬帧比 idle(69x47) 小一圈是正常的
（20x40~27x44），但如果是灰块占位图，尺寸会等于占位尺寸、内容也一眼可辨。

产出：code-quality-audit/第十八轮/_evidence/climb_frames_preview.png

用法：& C:\\Python311\\python.exe make_climb_preview.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
for _p in (os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if _p not in sys.path:
        sys.path.append(_p)

from PyQt5.QtCore import Qt, QRect                      # noqa: E402
from PyQt5.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402
from PyQt5.QtWidgets import QApplication                 # noqa: E402

_app = QApplication.instance() or QApplication([])

from sprite_loader import SpriteLoader                    # noqa: E402

EV = os.path.join(HERE, '_evidence')
os.makedirs(EV, exist_ok=True)

loader = SpriteLoader()
loader.load_sprites()

GROUPS = ['climb_right', 'climb_left', 'climb_front', 'jump', 'idle']
# 每行的色带颜色（见 Legend，写在同名 .txt 里）。
# ⚠️ 离屏环境**没有字体**：Qt 会打 "QFontDatabase: Cannot find font directory /
# Note that Qt no longer ships fonts."，`QPainter.drawText` **静默不画** ——
# 所以这里不能用文字当图例（试过两版，图上一个字都没有）。改用色带 + txt 图例。
BAND_COLORS = {
    'climb_right': QColor(210, 226, 244),
    'climb_left':  QColor(210, 240, 214),
    'climb_front': QColor(246, 240, 205),
    'jump':        QColor(246, 214, 220),
    'idle':        QColor(226, 226, 226),
}
CELL_W, CELL_H = 90, 90
BAND_H = 16
COLS = max(len(loader.sprites.get(g) or []) for g in GROUPS)

W = COLS * CELL_W
H = 8 + len(GROUPS) * (BAND_H + CELL_H)
img = QImage(W, H, QImage.Format_ARGB32)
# 浅灰底（透明像素看得见）+ 每格描边，便于判断"是不是整格空白/灰块"
img.fill(QColor(236, 236, 236))
painter = QPainter(img)

missing = []
for row, name in enumerate(GROUPS):
    frames = loader.sprites.get(name) or []
    if not frames:
        missing.append(name)
    band_y = 8 + row * (BAND_H + CELL_H)
    painter.fillRect(QRect(0, band_y, W, BAND_H), BAND_COLORS[name])
    painter.setPen(QColor(120, 120, 120))
    painter.drawLine(0, band_y + BAND_H - 1, W, band_y + BAND_H - 1)
    for col, pm in enumerate(frames):
        x = col * CELL_W
        y = band_y + BAND_H
        painter.setPen(QColor(160, 160, 160))
        painter.drawRect(QRect(x, y, CELL_W - 1, CELL_H - 1))
        if pm is None or pm.isNull():
            # 画不出字，就用"红色实心块"表示空帧（比空白更醒目，扫一眼就能发现）
            painter.fillRect(QRect(x + 20, y + 30, 50, 30), QColor(220, 40, 40))
            missing.append('%s[%d]' % (name, col))
            continue
        # 原尺寸居中放（不做缩放 —— 缩放会掩盖"灰块占位"这种尺寸异常）
        px = x + (CELL_W - pm.width()) // 2
        py = y + (CELL_H - pm.height()) // 2
        painter.drawPixmap(px, py, pm)

painter.end()

OUT = os.path.join(EV, 'climb_frames_preview.png')
img.save(OUT, 'PNG')

sizes = {g: [(p.width(), p.height()) for p in (loader.sprites.get(g) or [])] for g in GROUPS}
LEGEND = ['图例（自上而下，色带颜色 → 动画组）：',
          '  1. 浅蓝   climb_right  ← 用户素材 spr_ralsei_climb_1_*（朝右）',
          '  2. 浅绿   climb_left   ← 由上一组水平镜像落盘的 spr_ralsei_climb_left_*',
          '  3. 浅黄   climb_front  ← 用户素材 spr_ralsei_climb_0_degrees_*（朝前）',
          '  4. 浅粉   jump         ← 既有跳跃素材（跨度 ≤ 一层时用它，当标尺）',
          '  5. 灰     idle         ← 既有待机（当尺寸标尺：69x47）',
          '（红色实心块 = 该帧取到空 QPixmap，正常不该出现）',
          '（离屏环境无字体，QPainter.drawText 静默不画，所以图例只能写在这里）',
          '']
lines = ['OUT = %s' % OUT] + LEGEND + [
         'missing_or_null = %s' % (missing or '无'),
         'climb_right = %s' % (sizes['climb_right'],),
         'climb_left  = %s' % (sizes['climb_left'],),
         'climb_front = %s' % (sizes['climb_front'],),
         'frame_container_size = %s' % (loader.frame_container_size,),
         'anim_miss_report = %s' % (loader.get_animation_miss_report(),)]
with open(os.path.join(EV, 'climb_frames_preview.txt'), 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(lines) + '\n')

sys.stdout.write('\n'.join(lines) + '\n')
sys.exit(1 if missing else 0)

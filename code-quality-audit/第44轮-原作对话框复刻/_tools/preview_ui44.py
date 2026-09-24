# -*- coding: utf-8 -*-
"""第44轮 · 离屏渲染验证

产出（落 _evidence/）：
  ui44_full.png     DialogueUI 整体外观（含 8 帧角之一）
  ui44_sizes.png    同一 DrTextboxFrame 在 4 种尺寸下的 9-slice 表现
  ui44_corner.png   8 帧角动画 ×4 放大横向对照（灰底看透明区）

用法：C:\\Python311\\python.exe preview_ui44.py
"""
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MODS = os.path.join(REPO, 'ralsei_pet', 'modules')
SRC = os.path.join(REPO, 'ralsei_pet', 'src')
EVID = os.path.abspath(os.path.join(HERE, '..', '_evidence'))
for p in (MODS, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from PyQt5.QtCore import Qt                                   # noqa: E402
from PyQt5.QtGui import QColor, QImage, QPainter, QPixmap      # noqa: E402
from PyQt5.QtWidgets import QApplication, QWidget              # noqa: E402

import dr_textbox as drb                                       # noqa: E402


class MockParent(QWidget):
    """只为让 DialogueUI.__init__ 里的 set_face() 拿到 sprite_loader。"""

    def __init__(self):
        super().__init__()
        from sprite_loader import SpriteLoader
        self.sprite_loader = SpriteLoader()


def save(widget, path):
    pm = widget.grab()
    ok = pm.save(path)
    print('[save] %-16s %sx%s  ok=%s' % (os.path.basename(path),
                                         pm.width(), pm.height(), ok))
    return pm


def main():
    if not os.path.isdir(EVID):
        os.makedirs(EVID)
    app = QApplication.instance() or QApplication(sys.argv)

    from dialogue_ui import DialogueUI

    # ---- 1. DialogueUI 整体外观 -------------------------------------------
    parent = MockParent()
    dlg = DialogueUI(parent)
    dlg.setWindowOpacity(1.0)
    dlg._history_html = (
        '<span style="color:#ffffff;">Ralsei: 你好呀，我是 Ralsei！'
        '今天是个好天气呢，要不要一起出去走走？</span><br>'
        '<span style="color:#ffffff;">Ralsei: 咦……你在看什么呢？</span>'
    )
    try:
        dlg._refresh_display()
    except Exception as e:
        print('[warn] _refresh_display: %s' % e)
    try:
        dlg._recalc_size_to_content()
    except Exception as e:
        print('[warn] _recalc_size_to_content: %s' % e)
    dlg.show()
    app.processEvents()
    full = save(dlg, os.path.join(EVID, 'ui44_full.png'))

    # ---- 2. 同一 DrTextboxFrame 多种尺寸 ----------------------------------
    sizes = [(620, 220), (620, 320), (460, 200), (760, 180)]
    gap = 16
    W = max(s[0] for s in sizes) + 2 * gap
    H = sum(s[1] for s in sizes) + gap * (len(sizes) + 1)
    canvas = QImage(W, H, QImage.Format_ARGB32)
    canvas.fill(QColor(70, 70, 78))
    pt = QPainter(canvas)
    y = gap
    for (w, h) in sizes:
        frm = drb.DrTextboxFrame()
        frm.resize(w, h)
        frm._frame = 0
        sub = frm.grab()
        pt.drawPixmap(gap, y, sub)
        pt.setPen(QColor(255, 255, 0))
        pt.drawText(gap + 4, y + 14, '%dx%d' % (w, h))
        y += h + gap
    pt.end()
    canvas.save(os.path.join(EVID, 'ui44_sizes.png'))
    print('[save] ui44_sizes.png      %sx%s' % (W, H))

    # ---- 3. 8 帧角 ×4 放大对照 -------------------------------------------
    sp = drb.default_sprites()
    scale = 4
    cell = drb.CORNER_SIZE * scale
    pad = 12
    W2 = (cell + pad) * drb.CORNER_FRAMES + pad
    H2 = cell + 2 * pad
    c2 = QImage(W2, H2, QImage.Format_ARGB32)
    c2.fill(QColor(70, 70, 78))
    p2 = QPainter(c2)
    for i in range(drb.CORNER_FRAMES):
        pm = sp.corner(i)
        big = pm.scaled(pm.width() * scale, pm.height() * scale,
                        Qt.IgnoreAspectRatio, Qt.FastTransformation)
        x = pad + i * (cell + pad)
        p2.drawPixmap(x, pad, big)
        p2.setPen(QColor(255, 255, 0))
        p2.drawText(x, pad - 2, 'f%d' % i)
    p2.end()
    c2.save(os.path.join(EVID, 'ui44_corner.png'))
    print('[save] ui44_corner.png     %sx%s' % (W2, H2))

    # ---- 4. 常量自检（写进日志） -----------------------------------------
    print('--- dr_textbox 常量 ---')
    for k in ('BAND', 'STRETCH_GAP', 'CORNER_SIZE', 'BLACK_INSET',
              'CORNER_FRAMES', 'JEWEL_TICKS_PER_FRAME', 'ENGINE_FPS',
              'TYPE_INTERVAL_MS', 'CONTENT_INSET'):
        print('  %-22s = %s' % (k, getattr(drb, k)))
    print('  jewel_frame(0,9,10,79,80) =',
          [drb.jewel_frame(t) for t in (0, 9, 10, 79, 80)])
    print('  missing 素材 =', sp.missing)
    print('[done]')


if __name__ == '__main__':
    main()

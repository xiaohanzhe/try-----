# -*- coding: utf-8 -*-
"""第44轮 · 几何诊断：DialogueUI 与 DrTextboxFrame 的尺寸/位置关系。"""
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
for p in (os.path.join(REPO, 'ralsei_pet', 'modules'),
          os.path.join(REPO, 'ralsei_pet', 'src')):
    if p not in sys.path:
        sys.path.insert(0, p)

from PyQt5.QtWidgets import QApplication, QWidget   # noqa: E402


class MockParent(QWidget):
    def __init__(self):
        super().__init__()
        from sprite_loader import SpriteLoader
        self.sprite_loader = SpriteLoader()


def dump(tag, dlg):
    f = dlg._frame
    print('[%s]' % tag)
    print('  dlg.size            = %sx%s' % (dlg.width(), dlg.height()))
    print('  frame.geometry      = %s' % f.geometry())
    print('  frame.size          = %sx%s' % (f.width(), f.height()))
    print('  frame.minimumHeight = %s' % f.minimumHeight())
    print('  frame.maximumHeight = %s' % f.maximumHeight())
    lay = dlg.layout()
    print('  layout.geometry     = %s' % lay.geometry())
    print('  layout.contentsRect = %s' % lay.contentsRect())


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    from dialogue_ui import DialogueUI

    dlg = DialogueUI(MockParent())
    dlg.setWindowOpacity(1.0)
    dlg.show()
    app.processEvents()
    dump('初始（空内容）', dlg)

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
        print('[warn] _recalc: %s' % e)
    app.processEvents()
    dump('有内容', dlg)

    pm = dlg.grab()
    print('  grab                = %sx%s' % (pm.width(), pm.height()))
    img = pm.toImage()
    print('  img dpr             = %s' % img.devicePixelRatio())
    for y in (0, 10, 40, 300, pm.height() // 2, pm.height() - 10, pm.height() - 1):
        if 0 <= y < img.height():
            c = img.pixelColor(pm.width() // 2, y)
            c2 = img.pixelColor(2, y)
            print('    y=%-4s  mid=(%3d,%3d,%3d,a=%3d)  x2=(%3d,%3d,%3d,a=%3d)'
                  % (y, c.red(), c.green(), c.blue(), c.alpha(),
                     c2.red(), c2.green(), c2.blue(), c2.alpha()))


if __name__ == '__main__':
    main()

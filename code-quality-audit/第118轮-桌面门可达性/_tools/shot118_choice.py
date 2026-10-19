# -*- coding: utf-8 -*-
u"""shot118_choice.py —— 把**三角符文风格选择框**单独截出来看（1:1，不缩放）。

为什么
------
用户 10-19：「你要按照**三角符文的那选择**来啊，**不是干巴巴的弹窗**」。
改完之后必须**亲眼看**：框是不是原作那块（黑底 + 圆角金边 + 角上宝石）、
灵魂红心是不是停在选中行、换行时红心会不会跟着走。
⇒ 本脚本不启动整只桌宠，只把 `DrChoiceBox` 摆出来、`grab()` 存盘。

产出：`_evidence/choice118_default.png`、`choice118_moved.png`

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\shot118_choice.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
OUT = os.path.join(ROUND, '_evidence')
os.makedirs(OUT, exist_ok=True)

sys.path.insert(0, PKG)
os.environ.setdefault('QT_QPA_PLATFORM', 'windows')

from PyQt5 import QtCore, QtGui, QtWidgets                          # noqa: E402

from modules import dr_choice                                 # noqa: E402


def main():
    app = QtWidgets.QApplication(sys.argv)
    opts = ['我确定！！！', '我再考虑考虑']
    box = dr_choice.DrChoiceBox(None, opts, scale=1.0, default_index=1,
                               cancel_index=1, prompt='（门纹丝不动。）')
    box.show()
    box.raise_()
    for _ in range(10):
        app.processEvents()
    p1 = os.path.join(OUT, 'choice118_default.png')
    box.grab().save(p1)
    print('written %s  %dx%d' % (p1, box.width(), box.height()))

    # 按一下"上" ⇒ 红心应该移到第一行（证明光标是**跟着选中行**的）
    QtWidgets.QApplication.sendEvent(
        box, QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Up,
                              QtCore.Qt.NoModifier))
    for _ in range(6):
        app.processEvents()
    p2 = os.path.join(OUT, 'choice118_moved.png')
    box.grab().save(p2)
    print('written %s（选中行 = %d）' % (p2, box._sel))
    # 再按回车 ⇒ 应该 accepted 且 picked==0（"确定"）
    QtWidgets.QApplication.sendEvent(
        box, QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Return,
                              QtCore.Qt.NoModifier))
    app.processEvents()
    print('确认键 ⇒ picked=%r（期望 0）' % (box.picked,))
    box.close()


if __name__ == '__main__':
    main()

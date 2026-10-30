# -*- coding: utf-8 -*-
u"""probe118_modal.py —— 隔离实验：**模态 `exec_()` 期间，另一个 QTimer 还跑不跑？**

为什么要单独做这个实验
----------------------
`rec118.py` 第一版录出来（`_evidence/rec118/rec118_frames.csv`）：

  · 帧 120：`step=P4_B_ask`，`t=25.917`，`modal=0`
  · 帧 121：`step=P5_end`，  `t=34.234`
  ⇒ 中间 **8.3 s 一帧都没有**，`choice_1to1_*.png` 一张没生成，
     但日志里「第 1 轮选了『我再考虑考虑』」**正常出现**（说明框真的弹了、也真的被关了）。

两个候选解释，必须分清（否则改夹具 = 用假夹具骗自己）：
  (a) 模态期间**定时器不触发** ⇒ 我的 `_modal()` 驱动逻辑根本没机会跑；
  (b) 定时器跑了，但 `QApplication.activeModalWidget()` 返回 **None**
      ⇒ 逻辑跑了却找不到框；那 8 s 是别的阻塞（例如主线程上的 AI 重试 4×~2 s）。
  ★ 这两条对策完全不同：(a) 要换驱动方式，(b) 只要换"找框"的方式。

本实验就 4 件事
--------------
  ① 记 tick 计数：`exec_()` 期间有没有涨；
  ② 记 `activeModalWidget()` 的类型；
  ③ 记 `topLevelWidgets()` 里有没有 `DrChoiceBox`（**不依赖 Qt 的模态簿记**）；
  ④ 用后台线程按时间表往框上 post 真按键（↑ / Esc），看能不能关掉。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\probe118_modal.py
"""
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
# ★ `modules/` 是 `ralsei_pet` 下的包 ⇒ 两个路径都要给（与 `main.py` 里
#   `from modules import dr_choice` 同一套解析）。
for _p in (SRC, PKG):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.chdir(PKG)

from PyQt5.QtCore import Qt, QTimer, QObject                    # noqa: E402
from PyQt5.QtGui import QKeyEvent                                # noqa: E402
from PyQt5.QtWidgets import QApplication, QWidget                # noqa: E402

from modules import dr_choice                                     # noqa: E402

OUT = []
T = {'n': 0, 't0': time.time()}


def say(m):
    s = '[modal] %s' % m
    OUT.append(s)
    sys.stdout.write(s + '\n')
    sys.stdout.flush()


app = QApplication(sys.argv)
top = QWidget()
top.resize(200, 120)
top.show()


def _find_box():
    u"""**不看 `activeModalWidget()`**，直接扫 topLevelWidgets（判据与 Qt 簿记解耦）。"""
    for w in QApplication.topLevelWidgets():
        if type(w).__name__ == 'DrChoiceBox':
            return w
    return None


def tick():
    T['n'] += 1
    el = time.time() - T['t0']
    mw = QApplication.activeModalWidget()
    box = _find_box()
    if T['n'] % 5 == 0 or el < 2.0:
        say('t=%5.2f tick#%d activeModal=%s box=%s vis=%s'
            % (el, T['n'], type(mw).__name__ if mw else None,
               type(box).__name__ if box else None,
               bool(box.isVisible()) if box else None))


_tm = QTimer()
_tm.timeout.connect(tick)
_tm.start(100)


def _driver():
    u"""后台线程按时间表 post 按键（**按键只用 postEvent，不碰 GUI 状态**）。"""
    time.sleep(1.4)
    box = _find_box()
    say('driver t=1.4 找框 ⇒ %s' % (type(box).__name__ if box else None))
    if box is not None:
        try:
            say('  box 几何 = %r 可见=%s' % (box.frameGeometry(), box.isVisible()))
            QApplication.postEvent(
                box, QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Up, Qt.NoModifier))
            say('  已 post ↑')
        except Exception as e:                                   # noqa: BLE001
            say('  post ↑ 失败 %r' % (e,))
    time.sleep(1.2)
    box = _find_box()
    if box is not None:
        try:
            QApplication.postEvent(
                box, QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
            say('  已 post Esc')
        except Exception as e:                                   # noqa: BLE001
            say('  post Esc 失败 %r' % (e,))


def kickoff():
    threading.Thread(target=_driver, daemon=True).start()
    say('=== 调 dr_choice.choose（会阻塞在 exec_）===')
    t0 = time.time()
    idx = dr_choice.choose(top, ['我确定', '我再考虑考虑'], scale=1.0,
                           default_index=1, cancel_index=1,
                           prompt='（门纹丝不动。）')
    say('=== choose 返回 idx=%r，阻塞 %.2f s ===' % (idx, time.time() - t0))
    say('exec_ 期间 tick 从 %d 涨到 %d（涨了 %d 次）'
        % (T['n_at_open'], T['n'], T['n'] - T['n_at_open']))
    app.quit()


QTimer.singleShot(1000, kickoff)


def _mark():
    T['n_at_open'] = T['n']


T['n_at_open'] = 0
QTimer.singleShot(900, _mark)

app.exec_()
say('done')

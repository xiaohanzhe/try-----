# -*- coding: utf-8 -*-
u"""probe118_egg4.py —— 量：**选择框开着的时候，`update_movement` 到底占了多少 CPU？**

已有事实链（不是猜）
--------------------
1. `probe118_modal.py`（隔离）：`exec_()` 里 100 ms 定时器照跑（2.6 s 涨 21 次）
   ⇒ 模态本身**不**饿死定时器。
2. `probe118_egg3.py`（真 App，`singleShot` 派发）：框弹出后 **13 s 我的定时器一次没响**，
   `faulthandler` 三次 dump 的主线程栈**全在**
   `update_movement → self.move() → dialogue_ui.eventFilter`。
3. 所以问题不是"模态"，是**主线程被 `update_movement` 霸占**。

⇒ 本文件只量一件事：框开着的那 5 秒里，`update_movement`
   **被调了多少次、每次多久、总共占了多少墙钟**。
   如果"次数×单次"≈ 5 s，就是它把主线程吃干了（真 bug，用户会觉得框按不动）；
   如果远小于 5 s，那我的"饿死"判断就是错的，得另找。

★ 只做这一件事：站到门 B → 开框 → 量 5 s → Esc 关框 → 退。
  不再做四门巡游（用户已经在屏幕上看见"闹鬼"了）。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\probe118_egg4.py
"""
import ctypes
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')

_SB = tempfile.mkdtemp(prefix='probe118egg4_')
for _s in ('vault', 'staging', 'desktop'):
    os.makedirs(os.path.join(_SB, _s), exist_ok=True)
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(_SB, 'vault')
os.environ['RALSEI_DATA_DIR'] = os.path.join(_SB, 'staging')
os.environ['RALSEI_DESKTOP'] = os.path.join(_SB, 'desktop')
os.environ.setdefault('QT_QPA_PLATFORM', 'windows')

os.chdir(PKG)
for _p in (SRC, PKG):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

import main as M                                                 # noqa: E402
from PyQt5.QtCore import Qt, QTimer                              # noqa: E402
from PyQt5.QtGui import QKeyEvent                                # noqa: E402
from PyQt5.QtWidgets import QApplication                         # noqa: E402

T0 = time.time()
CALLS = []          # [(t_start, dur)]


def say(m):
    sys.stdout.write('[egg4 %6.2f] %s\n' % (time.time() - T0, m))
    sys.stdout.flush()


M.check_single_instance()
M.install_crash_guard()
try:
    import data_store
    data_store.vault_root = lambda create=True: None
    data_store.migrate_from_staging()
except Exception:
    pass

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass
_W, _H = window._desktop_layer_size()

# ---- 计时 update_movement（★ 注意它是 `monitor_performance` 包过的）----
_orig_um = window.update_movement


def _um(*a, **kw):
    t = time.time()
    try:
        return _orig_um(*a, **kw)
    finally:
        CALLS.append((t, time.time() - t))


window.update_movement = _um
try:
    window.movement_timer.timeout.disconnect()
except Exception as e:                                           # noqa: BLE001
    say('disconnect 失败（照旧连两遍会双跑，留意）%r' % (e,))
window.movement_timer.timeout.connect(_um)
say('movement_timer 间隔 = %d ms' % window.movement_timer.interval())


def _box():
    for w in QApplication.topLevelWidgets():
        if type(w).__name__ == 'DrChoiceBox':
            return w
    return None


S = {'step': 'wait', 't0': time.time()}


def _kick():
    say('=== 开框（singleShot 派发）===')
    S['step'] = 'in'
    QTimer.singleShot(0, lambda: window.interact_scene_prop())


def _measure():
    u"""后台线程量 5 s：**不碰 GUI 状态**，只读时间戳列表。"""
    time.sleep(0.6)
    b = _box()
    say('框 = %s 可见=%s 几何=%s'
        % (type(b).__name__ if b else None,
           b.isVisible() if b else None,
           b.frameGeometry() if b else None))
    t_a = time.time()
    base = len(CALLS)
    time.sleep(1.0)
    # ① 发 ↑，随后读 `_sel`（读属性，不改）
    if b is not None:
        QApplication.postEvent(
            b, QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Up, Qt.NoModifier))
        say('已 post ↑')
    time.sleep(1.0)
    if b is not None:
        say('↑ 之后 `_sel` = %r（默认 1 ⇒ 应变成 0）' % getattr(b, '_sel', None))
    time.sleep(1.5)
    t_b = time.time()
    sub = CALLS[base:]
    tot = sum(d for _t, d in sub)
    n = len(sub)
    say('---- 框开着 %.1f s 内 ----' % (t_b - t_a))
    say('update_movement 调用 %d 次；单次 均 %.2f ms / 最大 %.1f ms；'
        '**合计占墙钟 %.2f s（%.0f%%）**'
        % (n, 1000.0 * tot / max(1, n),
           1000.0 * max([d for _t, d in sub] or [0]),
           tot, 100.0 * tot / max(1e-6, (t_b - t_a))))
    if b is not None:
        QApplication.postEvent(
            b, QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        say('已 post Esc')
    time.sleep(1.2)
    say('Esc 后框 = %r' % (type(_box()).__name__ if _box() else None))
    say('watchdog：退')
    os._exit(0)


def _main_seq():
    r = None
    for it in (window._desktop_screen_doors(int(_W), int(_H)) or []):
        if 'niko_door_portal' in str(it[0]):
            r = tuple(it[1])
    if r:
        fg = window.frameGeometry()
        window.move(int(r[0] + r[2] // 2) - fg.width() // 2,
                    int(r[1] + r[3] // 2) - fg.height() // 2)
        try:
            window._interact_facing = 'down'
        except Exception:                                        # noqa: BLE001
            pass
        say('站到门 B %r' % (r,))
    threading.Thread(target=_measure, daemon=True).start()
    QTimer.singleShot(500, _kick)


QTimer.singleShot(1500, _main_seq)

tm = QTimer()
tm.timeout.connect(lambda: None)
tm.start(100)
app.exec_()

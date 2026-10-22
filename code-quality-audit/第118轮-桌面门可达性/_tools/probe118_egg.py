# -*- coding: utf-8 -*-
u"""probe118_egg.py —— 只测「Niko 的家」那一下：**谁把主线程卡了 8 秒？**

起因（`_evidence/rec118/rec118_frames.csv` 第一版）
----------------------------------------------------
帧 120 `step=P4_B_ask` / 帧 121 `step=P5_end`，中间 **8.3 s 一帧都没有**；
`choice_1to1_*.png` 一张没生成（我的模态驱动**一次都没跑**）；
但日志「第 1 轮选了『我再考虑考虑』」正常出现 —— 框确实弹了、也确实被关了。

隔离实验 `probe118_modal.py` 已经排除"模态不让定时器跑"：
  `exec_()` 期间 100 ms 定时器照跑（2.6 s 涨了 21 次），
  `activeModalWidget()` 也能正常返回 `DrChoiceBox`。

⇒ 剩下的唯一解释：**真实 App 里那 8 秒是主线程被同步调用堵死**
  （堵的时候连 `exec_()` 的嵌套循环都不转 ⇒ 一帧都录不到）。
  本文件要在真 App 里把它**抓现行**：谁进去的、堵了多久、出来时框还在不在。

只做三件事，不做四门巡游（用户已经在屏幕上看见"闹鬼"了，别再折腾一遍）
--------------------------------------------------------------------------
  ① 站到门 B；
  ② 给三个嫌疑调用各套一层**计时器**：
       `interact_scene_prop` / `_item_prop_present` / `_menu_message` / `dr_choice.choose`
  ③ 主循环 tick 记"帧间隔"，**> 0.4 s 就报 GAP**，并打印"此刻框在不在"。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\probe118_egg.py
"""
import ctypes
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')

_SB = tempfile.mkdtemp(prefix='probe118egg_')
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
from modules import dr_choice                                    # noqa: E402


def say(m):
    sys.stdout.write('[egg] %s\n' % m)
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
say('沙箱=%s 画布=%dx%d' % (_SB, int(_W), int(_H)))


# ------------------------------------------------------- ① 给嫌疑调用套计时器
def _wrap(obj, name, label):
    orig = getattr(obj, name, None)
    if orig is None:
        say('!! %s 上没有 %s，跳过计时' % (label, name))
        return

    def f(*a, **kw):
        t = time.time()
        say('  ▸ %s(%s) 进入' % (name, 'B' if label == 'dr_choice' else ''))
        try:
            return orig(*a, **kw)
        finally:
            say('  ◂ %s 退出（%.2f s）' % (name, time.time() - t))
    try:
        setattr(obj, name, f)
    except Exception as e:                                       # noqa: BLE001
        say('!! 包 %s.%s 失败 %r' % (label, name, e))


_wrap(window, 'interact_scene_prop', 'window')
_wrap(window, '_item_prop_present', 'window')
_wrap(window, '_item_menu_message', 'window')
_wrap(dr_choice, 'choose', 'dr_choice')

# ------------------------------------------------------- ② tick 帧间隔
T = {'n': 0, 'last': 0.0, 't0': time.time(), 'step': 'wait', 'asked': False}


def _box():
    for w in QApplication.topLevelWidgets():
        if type(w).__name__ == 'DrChoiceBox' and w.isVisible():
            return w
    return None


def _post(k):
    b = _box()
    if b is None:
        say('  !! 想发 %r 但没找到框' % (k,))
        return False
    QApplication.postEvent(b, QKeyEvent(QKeyEvent.KeyPress, k, Qt.NoModifier))
    return True


def tick():
    now = time.time()
    if T['n'] == 0:
        T['last'] = now
    gap = now - T['last']
    T['last'] = now
    T['n'] += 1
    if gap > 0.4:
        say('**GAP %.2f s**（上一帧到这一帧）step=%s 框在不在=%s'
            % (gap, T['step'], bool(_box())))
    b = _box()
    if b is not None:
        if not T['asked']:
            T['asked'] = True
            say('框出现 t=%.2f 几何=%r' % (now - T['t0'], b.frameGeometry()))
            threading.Timer(1.2, lambda: _post(Qt.Key_Up)).start()
            threading.Timer(2.4, lambda: _post(Qt.Key_Escape)).start()

    if T['step'] == 'wait' and now - T['t0'] > 1.2:
        rects = {}
        for it in (window._desktop_screen_doors(int(_W), int(_H)) or []):
            if 'niko_door_portal' in str(it[0]):
                rects['B'] = tuple(it[1])
        r = rects.get('B')
        if not r:
            say('!! 找不到门 B')
            return app.quit()
        fg = window.frameGeometry()
        window.move(int(r[0] + r[2] // 2) - fg.width() // 2,
                    int(r[1] + r[3] // 2) - fg.height() // 2)
        try:
            window._interact_facing = 'down'
        except Exception:                                        # noqa: BLE001
            pass
        app.processEvents()
        say('站到门 B %r' % (r,))
        T['step'] = 'go'
        T['t0'] = now
        return
    if T['step'] == 'go' and now - T['t0'] > 0.8:
        T['step'] = 'in'
        say('=== 调 interact_scene_prop() ===')
        t = time.time()
        ok = window.interact_scene_prop()
        say('=== 返回 %r（阻塞 %.2f s）场景=%s ==='
            % (ok, time.time() - t, getattr(window, 'current_scene', '')))
        T['step'] = 'done'
        T['t0'] = now
        return
    if T['step'] == 'done' and now - T['t0'] > 1.0:
        say('收尾：tick 总数=%d' % T['n'])
        try:
            window.close()
        except Exception:                                        # noqa: BLE001
            pass
        return app.quit()


_tm = QTimer()
_tm.timeout.connect(tick)
_tm.start(100)
app.exec_()
say('done')

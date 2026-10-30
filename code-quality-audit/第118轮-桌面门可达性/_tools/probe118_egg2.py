# -*- coding: utf-8 -*-
u"""probe118_egg2.py —— **把堵住主线程的那一行栈抓出来**。

上一轮结论（`probe118_egg.py`）
------------------------------
```
[egg]   ▸ choose(B) 进入
[egg]   ◂ choose 退出（89.90 s）      ← 中间一个 [egg] tick 都没有
```
⇒ 90 秒里主线程**完全没跑 Qt 事件循环**（否则 100 ms 的定时器必然会触发）。
而 `probe118_modal.py` 已经排除"模态不让定时器跑"（`exec_()` 里 2.6 s 涨了 21 次 tick）。
⇒ 只剩两种可能，且**对策完全不同**：
   (a) 卡在 **`exec_()` 之外**（构造函数 / `availableGeometry()` / 字体加载）——
       那是产品在真机上会**冻住整只桌宠**的真问题；
   (b) 卡在 **别的同步调用**（比如主线程上跑 AI，一跑就是冷载入 77 s + 4 次重试）——
       那是性能线的老账（详版 §78.11 三铁律），不是第118轮的。
猜不出来，所以用 `faulthandler` **每 10 秒把主线程栈打一次**，25 秒后强杀进程。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\probe118_egg2.py
"""
import ctypes
import faulthandler
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')

_SB = tempfile.mkdtemp(prefix='probe118egg2_')
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
from PyQt5.QtWidgets import QApplication                         # noqa: E402
from modules import dr_choice                                    # noqa: E402


def say(m):
    sys.stdout.write('[egg2] %s\n' % m)
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

# ---------------------------------------------------------------- 计时 + 栈
_T = {'choose': [None, None]}


def _wrap(obj, name, label):
    orig = getattr(obj, name, None)
    if orig is None:
        say('!! 没有 %s.%s' % (label, name))
        return

    def f(*a, **kw):
        t = time.time()
        say('  ▸ %s 进入' % name)
        _T['t_in'] = t
        try:
            return orig(*a, **kw)
        finally:
            say('  ◂ %s 退出（%.2f s）' % (name, time.time() - t))
    setattr(obj, name, f)


_wrap(window, 'interact_scene_prop', 'window')
# ★ 只包 `choose` 与 `DrChoiceBox.exec_`：这样能分开"构造慢"还是"事件循环慢"
_wrap(dr_choice, 'choose', 'dr_choice')
_wrap(dr_choice.DrChoiceBox, 'exec_', 'DrChoiceBox')


def _dump():
    u"""主线程栈（`faulthandler` 打全线程；主线程在最上面那段）。"""
    say('===== 主线程栈（%s）=====' % time.strftime('%H:%M:%S'))
    try:
        faulthandler.dump_traceback(all_threads=False)
    except Exception as e:                                       # noqa: BLE001
        say('dump 失败 %r' % (e,))
    sys.stdout.flush()


def _watchdog():
    u"""25 s 后强杀：不让进程在屏幕上挂着 90 秒，也不让用户再看一遍"闹鬼"。"""
    time.sleep(10)
    _dump()
    time.sleep(4)
    _dump()
    time.sleep(4)
    _dump()
    say('watchdog：强杀（已在上面打出 3 次主线程栈）')
    os._exit(0)


threading.Thread(target=_watchdog, daemon=True).start()

T = {'n': 0, 't0': time.time(), 'step': 'wait', 'last': time.time()}


def tick():
    now = time.time()
    gap = now - T['last']
    T['last'] = now
    T['n'] += 1
    if gap > 0.4:
        say('**GAP %.2f s**（主线程定时器停了这么久）step=%s' % (gap, T['step']))
    if T['step'] == 'wait' and now - T['t0'] > 1.0:
        r = None
        for it in (window._desktop_screen_doors(int(_W), int(_H)) or []):
            if 'niko_door_portal' in str(it[0]):
                r = tuple(it[1])
        if not r:
            say('!! 没找到门 B')
            return app.quit()
        fg = window.frameGeometry()
        window.move(int(r[0] + r[2] // 2) - fg.width() // 2,
                    int(r[1] + r[3] // 2) - fg.height() // 2)
        try:
            window._interact_facing = 'down'
        except Exception:                                        # noqa: BLE001
            pass
        app.processEvents()
        say('站到门 B %r（tick=%d）' % (r, T['n']))
        T['step'] = 'go'
        T['t0'] = now
        return
    if T['step'] == 'go' and now - T['t0'] > 0.8:
        T['step'] = 'in'
        say('=== interact_scene_prop()（tick=%d）===' % T['n'])
        ok = window.interact_scene_prop()
        say('=== 返回 %r（tick=%d）===' % (ok, T['n']))
        T['step'] = 'close'
        return


_tm = QTimer()
_tm.timeout.connect(tick)
_tm.start(100)
app.exec_()
say('done')

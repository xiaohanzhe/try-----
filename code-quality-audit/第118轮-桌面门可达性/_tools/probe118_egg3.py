# -*- coding: utf-8 -*-
u"""probe118_egg3.py —— **谁在替用户按确认 / 谁在关框？**（给框子的每个入口装记录器）

前情（`probe118_egg2.py`）
--------------------------
```
[egg2]   ▸ choose 进入 / ▸ exec_ 进入
[egg2]   ◂ exec_ 退出（9.22 s）    ← 第一轮
[egg2]   ◂ exec_ 退出（2.18 s）    ← 第二轮
[egg2]   ◂ exec_ 退出（2.30 s）    ← 第三轮
… Niko 的家彩蛋：三轮都选了「我确定！！！」⇒ 爆炸特效
```
★ 我一次按键都没发（`_key` 根本没被调用）⇒ **有第三方在替用户按确认**。
★ 而且第一轮 9.22 s、后两轮 2.2 s —— 第一轮多出来的 ~7 s 得单独查。

本文件把"所有可能结束一个 QDialog 的路"全装上记录器
-----------------------------------------------------
  `keyPressEvent` / `mousePressEvent` / `mouseDoubleClickEvent` /
  `accept` / `reject` / `done` / `closeEvent` / `focusInEvent`
每条都记：**时间、事件类型、按键码、鼠标坐标、当时 `_sel`**。
⇒ 是"真按键"还是"代码里 done()"还是"窗口被关"，一眼分开。

外加 `faulthandler.dump_traceback(all_threads=True)`（上一版忘了 `all_threads`，
只打出了 watchdog 自己的栈，主线程根本没出现在 dump 里）。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\probe118_egg3.py
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

_SB = tempfile.mkdtemp(prefix='probe118egg3_')
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

T0 = time.time()


def say(m):
    sys.stdout.write('[egg3 %6.2f] %s\n' % (time.time() - T0, m))
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

# ------------------------------------------------------------ 装记录器
_KEYS = {getattr(Qt, k): k for k in dir(Qt) if k.startswith('Key_')}


def _kname(k):
    return _KEYS.get(k, str(k))


def _wrap(obj, name, lab, fmt=None):
    orig = getattr(obj, name, None)
    if orig is None:
        say('!! 没有 %s' % name)
        return

    def f(*a, **kw):
        extra = fmt(*a, **kw) if fmt else ''
        say('  ● %s  %s' % (name, extra))
        return orig(*a, **kw)
    setattr(obj, name, f)


def _fmt_key(self, ev):
    return ('key=%s type=%s sel=%r picked=%r focus=%s'
            % (_kname(ev.key()), ev.type(), getattr(self, '_sel', None),
               getattr(self, 'picked', None),
               type(QApplication.focusWidget()).__name__))


def _fmt_mouse(self, ev):
    return ('pos=%r button=%s sel=%r'
            % (ev.pos(), ev.button(), getattr(self, '_sel', None)))


def _fmt_plain(self, *a):
    return 'sel=%r picked=%r' % (getattr(self, '_sel', None),
                                 getattr(self, 'picked', None))


_wrap(dr_choice.DrChoiceBox, 'keyPressEvent', 'box', _fmt_key)
_wrap(dr_choice.DrChoiceBox, 'mousePressEvent', 'box', _fmt_mouse)
_wrap(dr_choice.DrChoiceBox, 'mouseDoubleClickEvent', 'box', _fmt_mouse)
_wrap(dr_choice.DrChoiceBox, 'accept', 'box', _fmt_plain)
_wrap(dr_choice.DrChoiceBox, 'reject', 'box', _fmt_plain)
_wrap(dr_choice.DrChoiceBox, 'done', 'box', _fmt_plain)
_wrap(dr_choice.DrChoiceBox, 'closeEvent', 'box', _fmt_plain)
_wrap(dr_choice.DrChoiceBox, 'focusInEvent', 'box', _fmt_plain)

_orig_exec = dr_choice.DrChoiceBox.exec_


def _exec_wrap(self):
    t = time.time()
    say('  ▸ exec_ 进入（几何=%r 可见=%s 焦点=%s）'
        % (self.frameGeometry(), self.isVisible(),
           type(QApplication.focusWidget()).__name__))
    try:
        rc = _orig_exec(self)
    finally:
        say('  ◂ exec_ 退出 rc=%r picked=%r 耗时 %.2f s'
            % (locals().get('rc'), self.picked, time.time() - t))
    return rc


dr_choice.DrChoiceBox.exec_ = _exec_wrap

# ------------------------------------------------------------ 主线程栈
_DUMPS = [0]


def _dump():
    _DUMPS[0] += 1
    say('===== 全线程栈 #%d（%s）=====' % (_DUMPS[0], time.strftime('%H:%M:%S')))
    # ★ 上一版写成 all_threads=False ⇒ 只打出 watchdog 自己，主线程根本没出现
    faulthandler.dump_traceback(all_threads=True)
    sys.stdout.flush()


def _watchdog():
    time.sleep(9)
    _dump()
    time.sleep(4)
    _dump()
    time.sleep(4)
    _dump()
    say('watchdog：强杀')
    os._exit(0)


threading.Thread(target=_watchdog, daemon=True).start()

# ------------------------------------------------------------ 主流程
S = {'n': 0, 't0': time.time(), 'step': 'wait', 'last': time.time()}


def tick():
    now = time.time()
    gap = now - S['last']
    S['last'] = now
    S['n'] += 1
    if gap > 0.4:
        say('**GAP %.2f s** step=%s' % (gap, S['step']))
    if S['step'] == 'wait' and now - S['t0'] > 1.0:
        r = None
        for it in (window._desktop_screen_doors(int(_W), int(_H)) or []):
            if 'niko_door_portal' in str(it[0]):
                r = tuple(it[1])
        fg = window.frameGeometry()
        window.move(int(r[0] + r[2] // 2) - fg.width() // 2,
                    int(r[1] + r[3] // 2) - fg.height() // 2)
        try:
            window._interact_facing = 'down'
        except Exception:                                        # noqa: BLE001
            pass
        app.processEvents()
        say('站到门 B %r（tick=%d）' % (r, S['n']))
        S['step'] = 'go'
        S['t0'] = now
        return
    if S['step'] == 'go' and now - S['t0'] > 0.8:
        # ★★★ 关键改动（第118轮取证）：**不要在自己的 tick 里直接调**
        #   `interact_scene_prop()`。`choose()` 会开 `exec_()` 嵌套事件循环，
        #   而 Qt **不会让同一个 QTimer 在自己槽函数还在执行时再次触发**
        #   （`QTimerInfo::activateRef`）⇒ 那段时间我一帧都录不到、也发不出按键，
        #   但**别的**定时器照跑（faulthandler 的栈里 `update_movement` 就在跑）。
        #   ⇒ 改用 `singleShot(0)` 派发到**另一个**定时器，tick 就能继续呼吸。
        S['step'] = 'dispatch'
        QTimer.singleShot(0, _do_interact)
        return


def _do_interact():
    if S['step'] != 'dispatch':
        return
    S['step'] = 'in'
    say('=== interact_scene_prop()（在 singleShot 里，tick 仍可呼吸）===')
    ok = window.interact_scene_prop()
    say('=== 返回 %r，场景=%s ===' % (ok, getattr(window, 'current_scene', '')))
    S['step'] = 'close'


_tm = QTimer()
_tm.timeout.connect(tick)
_tm.start(100)
app.exec_()
say('done')

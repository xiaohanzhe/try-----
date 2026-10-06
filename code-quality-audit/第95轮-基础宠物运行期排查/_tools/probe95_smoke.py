# -*- coding: utf-8 -*-
u"""probe95_smoke.py —— 第95轮**改后真机冒烟**（用户视角：改完还起得来、还走得像不像）。

做什么
------
复刻 `main.py` 的 `__main__` 启动序列起一次真机，然后：
  · 劫持 `window.move` 逐帧记 `(t,x,y,anim,dir,moving,spd,tgt,sz)`；
  · 记 `change_animation` 被拒的调用；
  · **stdout/stderr 全量落盘** ⇒ 用来数产品日志里的 `[anim-miss]`；
  · **硬超时自动退出**（`QTimer.singleShot(LIFE_MS, quit)`）⇒ 不会留残留进程。

★ 为什么要自己起：`main.py` 的 `__main__` 里 `window` 是局部名，黑盒观测不到
  内部状态（`current_direction` / `is_sleeping_walk` / `target_pos`）。
★ 启动序列必须与 `__main__` **逐条一致**，否则不是真机语义（第94/95轮同款纪律）。
★ 输出一律落 UTF-8 文件，不走 shell 管道（PS 会按 ANSI 解码致乱码）。

跑法（会起图形界面；沙箱/无桌面会话里可能起不来）
------------------------------------------------
  C:\\Python311\\python.exe code-quality-audit\\第95轮-基础宠物运行期排查\\_tools\\probe95_smoke.py
"""
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
EV = os.path.join(ROOT, 'code-quality-audit', '第95轮-基础宠物运行期排查', '_evidence')

LIFE_MS = int(os.environ.get('PROBE95_LIFE_MS', '150000'))      # 默认 150s 自动退
MOV = os.path.join(EV, 'live95_moves.txt')
ANI = os.path.join(EV, 'live95_anim.txt')
STA = os.path.join(EV, 'live95_state.txt')

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import main as M                                            # noqa: E402
import traceback                                            # noqa: E402
from PyQt5.QtCore import QPoint, QTimer                     # noqa: E402
from PyQt5.QtWidgets import QApplication                    # noqa: E402

# ---- 复刻 __main__ 启动序列（顺序逐条一致）----
M.check_single_instance()
M.install_crash_guard()
try:
    import text_segmenter
    text_segmenter.install()
except Exception as e:
    print('text_segmenter fail: %r' % (e,))
try:
    import data_store
    data_store.migrate_from_staging()
except Exception as e:
    print('data_store fail: %r' % (e,))

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()
print('[probe95] shown pid=%d title=%r' % (os.getpid(), window.windowTitle()))
sys.stdout.flush()

_t0 = time.time()
_fmov = io.open(MOV, 'w', encoding='utf-8', newline='\n')
_fani = io.open(ANI, 'w', encoding='utf-8', newline='\n')
_fsta = io.open(STA, 'w', encoding='utf-8', newline='\n')


def _g(o, n, d=None):
    try:
        return getattr(o, n, d)
    except Exception:
        return d


_orig_move = window.move
_last = [None]


def _move_wrap(x, y=None):
    if y is None:
        pt = x
        x, y = pt.x(), pt.y()
    if (x, y) != _last[0]:
        _last[0] = (x, y)
        _fmov.write('t=%.3f x=%d y=%d anim=%r dir=%r moving=%r spd=%r tgt=%r sz=%dx%d\n'
                    % (time.time() - _t0, x, y,
                       _g(window, 'current_animation'), _g(window, 'current_direction'),
                       _g(window, 'is_moving'), _g(window, 'speed'),
                       _g(window, 'target_pos'),
                       window.width(), window.height()))
        _fmov.flush()
    return _orig_move(x, y)


window.move = _move_wrap

_orig_change = window.change_animation


def _change_wrap(name, *a, **kw):
    r = _orig_change(name, *a, **kw)
    if not r:
        _fani.write('t=%.3f REJECT %r (cur=%r) args=%r kw=%r\n'
                    % (time.time() - _t0, name, _g(window, 'current_animation'), a, kw))
        _fani.flush()
    return r


window.change_animation = _change_wrap


def snap():
    try:
        p = window.pos()
        _fsta.write('t=%.1f pos=(%d,%d) sz=%dx%d anim=%r dir=%r mv=%r fall=%r '
                    'swalk=%r sleep=%r tgt=%r\n'
                    % (time.time() - _t0, p.x(), p.y(), window.width(), window.height(),
                       _g(window, 'current_animation'), _g(window, 'current_direction'),
                       _g(window, 'is_moving'), _g(window, 'is_falling'),
                       _g(window, 'is_sleeping_walk'), _g(window, 'is_sleeping'),
                       _g(window, 'target_pos')))
        _fsta.flush()
    except Exception:
        _fsta.write('ERR\n' + traceback.format_exc() + '\n')
        _fsta.flush()


tm = QTimer()
tm.timeout.connect(snap)
tm.start(1000)


def _bye():
    print('[probe95] life=%dms reached, quitting' % LIFE_MS)
    sys.stdout.flush()
    app.quit()


QTimer.singleShot(LIFE_MS, _bye)

if __name__ == '__main__':
    rc = app.exec_()
    for f in (_fmov, _fani, _fsta):
        f.close()
    print('[probe95] exit rc=%d' % rc)
    sys.exit(rc)

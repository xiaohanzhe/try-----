# -*- coding: utf-8 -*-
u"""diag116_windows.py —— 列出**全部可见顶层窗口**并逐帧跟踪几何，找出"谁在跳"。

背景：shot116 里 `dialogue_ui.frameGeometry()` 24 帧不变，可像素上那个黑框在
上下跳 ~65px ⇒ 我盯错了对象。⇒ 改成枚举 `QApplication.topLevelWidgets()`，
逐帧记录每个可见窗口的 `geometry` / `frameGeometry` / flags / 透明度属性，
再对比帧间差异，直接指出**哪个窗口在动、动多少**。

沙箱：四闸（`RALSEI_MEMORY_DIR`/`RALSEI_DATA_DIR`/`RALSEI_DESKTOP`/`vault_root`）。
"""
import io
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
N = int(os.environ.get('DIAG116_N', '14'))
STEP_MS = int(os.environ.get('DIAG116_STEP_MS', '120'))
OUT = os.environ.get('DIAG116_OUT', r'E:\Download\_tmp\shot116')

import tempfile                                                  # noqa: E402
_SB = tempfile.mkdtemp(prefix='diag116w_')
for _s in ('vault', 'staging', 'desktop'):
    os.makedirs(os.path.join(_SB, _s), exist_ok=True)
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(_SB, 'vault')
os.environ['RALSEI_DATA_DIR'] = os.path.join(_SB, 'staging')
os.environ['RALSEI_DESKTOP'] = os.path.join(_SB, 'desktop')
os.environ.setdefault('QT_QPA_PLATFORM', 'windows')

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import main as M                                                 # noqa: E402
from PyQt5.QtWidgets import QApplication                         # noqa: E402
from PyQt5.QtCore import QTimer, Qt                              # noqa: E402


def say(m):
    sys.stdout.write('[win116] %s\n' % m)
    sys.stdout.flush()


M.check_single_instance()
M.install_crash_guard()
try:
    import text_segmenter
    text_segmenter.install()
    import jieba
    jieba.initialize()
except Exception:
    pass
try:
    import data_store
    data_store.vault_root = lambda create=True: None
    data_store.migrate_from_staging()
except Exception:
    pass

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()
_scr = app.primaryScreen()
_W, _H = _scr.geometry().width(), _scr.geometry().height()
say('screen=%dx%d' % (_W, _H))

_frames = []


def snap():
    rows = []
    for w in QApplication.topLevelWidgets():
        try:
            if not w.isVisible():
                continue
            g = w.geometry()
            fg = w.frameGeometry()
            rows.append((
                w.__class__.__name__,
                (g.x(), g.y(), g.width(), g.height()),
                (fg.x(), fg.y(), fg.width(), fg.height()),
                bool(w.testAttribute(Qt.WA_TranslucentBackground)),
                bool(w.testAttribute(Qt.WA_NoSystemBackground)),
                bool(w.windowFlags() & Qt.Tool),
                bool(w.windowFlags() & Qt.FramelessWindowHint),
                (w.windowTitle() or '')[:22],
            ))
        except Exception:
            continue
    rows.sort(key=lambda r: (r[0], r[1]))
    _frames.append(rows)
    if len(_frames) >= N:
        _finish()


def _finish():
    tm.stop()
    say('抓到 %d 帧；每帧可见顶层窗口数 = %r'
        % (len(_frames), [len(r) for r in _frames]))
    # 以"类名+标题"为身份，逐帧跟踪几何
    ident = {}
    for fr in _frames:
        for r in fr:
            ident.setdefault((r[0], r[7]), []).append(r)
    say('\n=== 各顶层窗口：几何是否逐帧变化 ===')
    for key, rows in sorted(ident.items(), key=lambda kv: -len(kv[1])):
        pos = [r[1] for r in rows]
        fpos = [r[2] for r in rows]
        uniq = []
        for p in pos:
            if p not in uniq:
                uniq.append(p)
        funiq = []
        for p in fpos:
            if p not in funiq:
                funiq.append(p)
        flag = '★ 在动' if len(uniq) > 1 or len(funiq) > 1 else '静止'
        say('  %-22s x%-2d  %s' % (key[0] + '|' + key[1], len(rows), flag))
        say('       geo 取值 %r' % (uniq[:6],))
        if len(funiq) > 1:
            say('       frameGeo 取值 %r' % (funiq[:6],))
    r0 = _frames[0]
    say('\n=== 第 0 帧窗口清单 ===')
    for r in r0:
        say('  %-20s geo=%r translucent=%s noSysBg=%s tool=%s frameless=%s %r'
            % (r[0], r[1], r[3], r[4], r[5], r[6], r[7]))
    app.quit()


tm = QTimer()
tm.timeout.connect(snap)
QTimer.singleShot(9000, lambda: tm.start(STEP_MS))
QTimer.singleShot(9000 + N * STEP_MS + 20000, _finish)

if __name__ == '__main__':
    rc = app.exec_()
    tm.stop()
    say('exit rc=%d' % rc)
    sys.exit(rc)

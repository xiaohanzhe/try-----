# -*- coding: utf-8 -*-
u"""shot116.py —— 真机抓帧 + **逐帧内省**（看用户到底看到了什么）。

用户报告（逐字）
----------------
「你要不要自己看看他啥情况啊，**门在闪现**，**黑底也没去干净**，并且
  **对话框也是闪现**，而且，**你门的形式也没用对**」

本脚本要一次性回答四件事
------------------------
  Q1 门是不是真的在闪？   → 逐帧抓屏 + 逐帧记 `_screen_doors` 四元组；
                            若四元组逐帧变化 ⇒ 门在跳。
  Q2 黑底哪来的？         → 逐帧记 `canvas._opaque_bg` 与 `_scene_state.bg`；
                            `_opaque_bg=True` 就是整屏不透明黑。
  Q3 对话框闪不闪？       → 逐帧记 `dialogue_ui` 的几何 / `isVisible()`；
                            同时抓屏里能看到。
  Q4 门的形式对不对？     → 把四扇门逐个裁出来存成小图，肉眼比对。

产物（DIAG116_OUT，默认 `E:\\Download\\_tmp\\shot116\\`）
-------------------------------------------------------
  s000.png …            整屏抓帧（缩半 + 全尺寸各一份的只有首帧）
  doors_now.png         四扇门按当前屏幕矩形裁出来的拼图
  introspect.txt        逐帧内省数值（一行一帧）
  meta.txt              环境/几何

★★ 沙箱用**四闸**（第116轮修正版）：`RALSEI_MEMORY_DIR` / `RALSEI_DATA_DIR` /
   `RALSEI_DESKTOP` / `vault_root` 猴补丁 —— 一个字节都不碰用户记忆库。
   跑完请用 `_shared/vault_guard.py diff` 独立复核（**不许自称**）。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第116轮-退出期崩溃定位与沙箱补漏\\_tools\\shot116.py
"""
import io
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')

N_FRAMES = int(os.environ.get('DIAG116_N', '30'))
STEP_MS = int(os.environ.get('DIAG116_STEP_MS', '150'))
WARM_S = float(os.environ.get('DIAG116_WARM_S', '9'))
OUT = os.environ.get('DIAG116_OUT', r'E:\Download\_tmp\shot116')
os.makedirs(OUT, exist_ok=True)

# ---- ★★★ 沙箱四闸（必须在 import main 之前）----
import tempfile
_SB = tempfile.mkdtemp(prefix='diag116_')
for _sub in ('vault', 'staging', 'desktop'):
    os.makedirs(os.path.join(_SB, _sub), exist_ok=True)
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(_SB, 'vault')
os.environ['RALSEI_DATA_DIR'] = os.path.join(_SB, 'staging')
os.environ['RALSEI_DESKTOP'] = os.path.join(_SB, 'desktop')
os.environ.setdefault('QT_QPA_PLATFORM', 'windows')

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import cv2                                                    # noqa: E402
import numpy as np                                            # noqa: E402
import main as M                                              # noqa: E402
from PyQt5.QtWidgets import QApplication                      # noqa: E402
from PyQt5.QtCore import QTimer                               # noqa: E402


def say(m):
    sys.stdout.write('[shot116] %s\n' % m)
    sys.stdout.flush()


say('沙箱 = %s' % _SB)

M.check_single_instance()
M.install_crash_guard()
try:
    import text_segmenter
    text_segmenter.install()
    import jieba
    jieba.initialize()
    say('jieba 预建完成')
except Exception as e:
    say('jieba/segmenter: %r' % (e,))
try:
    import data_store
    data_store.vault_root = lambda create=True: None
    data_store.migrate_from_staging()
    say('data_store: %s' % (data_store.describe(),))
except Exception as e:
    say('data_store: %r' % (e,))
try:
    import memory_store as _ms
    say('memory_store.default_memory_dir() = %r' % (_ms.default_memory_dir(),))
except Exception as e:
    say('memory_store 探针失败: %r' % (e,))

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()
try:
    import ctypes
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass
_scr = app.primaryScreen()
_geo = _scr.geometry()
_W, _H = _geo.width(), _geo.height()
say('shown pid=%d  screen=%dx%d' % (os.getpid(), _W, _H))
for _t in list(window.__dict__.keys()):
    pass

_HANDLES = {}


def _gg(o, n, d=None):
    try:
        return getattr(o, n, d)
    except Exception:
        return d


def introspect():
    w = window
    cv_ = getattr(w, 'scene_canvas', None)
    st = w.__dict__.get('_scene_state')
    dlg = None
    for _nm in ('dialogue_ui', 'dialog_ui', 'dr_textbox', '_dr_textbox',
                'dialogue_box', '_dialogue_box', 'speech_bubble'):
        if getattr(w, _nm, None) is not None:
            dlg = (getattr(w, _nm), _nm)
            break
    row = {
        'scene_id': _gg(st, 'scene_id'),
        'bg': _gg(st, 'bg'),
        'opaque_bg': _gg(cv_, '_opaque_bg'),
        'canvas_vis': bool(cv_.isVisible()) if cv_ is not None else None,
        'canvas_geo': None,
        'off': (_gg(cv_, '_offset_x'), _gg(cv_, '_offset_y')),
        'scale': (_gg(cv_, '_scale_x'), _gg(cv_, '_scale_y')),
        'plan_len': len(_gg(cv_, 'plan', lambda: [])() or []),
        'last_drawn': _gg(cv_, 'last_drawn'),
        'n_doors': len(_gg(cv_, '_screen_doors', []) or []),
        'doors': list(_gg(cv_, '_screen_doors', []) or []),
        'pet_k': _gg(w, '_cached_scale_factor'),
        'pet_scale': _gg(w, 'pet_scale'),
        't_alpha': _gg(cv_, '_transition_alpha'),
        'pet_geo': (_gg(w, 'x'), _gg(w, 'y'), _gg(w, 'width'), _gg(w, 'height')),
        'pet_vis': bool(w.isVisible()),
        'dlg_name': dlg[1] if dlg else None,
        'dlg_vis': None,
        'dlg_geo': None,
    }
    if cv_ is not None:
        cg = cv_.geometry()
        row['canvas_geo'] = (cg.x(), cg.y(), cg.width(), cg.height())
    if dlg is not None:
        d = dlg[0]
        row['dlg_vis'] = bool(_gg(d, 'isVisible', lambda: None)())
        f = _gg(d, 'frameGeometry', None)
        if callable(f):
            try:
                fg = f()
                row['dlg_geo'] = (fg.x(), fg.y(), fg.width(), fg.height())
            except Exception:
                pass
    return row, cv_


_t0 = time.time()
_lines = []


def _grab_full():
    pm = _scr.grabWindow(0)
    img = pm.toImage()
    ptr = img.bits()
    ptr.setsize(img.byteCount())
    raw = bytes(ptr)
    arr = np.frombuffer(raw, np.uint8).reshape(img.height(),
                                               img.bytesPerLine() // 4, 4)
    return np.ascontiguousarray(arr[:, :img.width(), :3])


def _save_png(path, arr):
    ok, buf = cv2.imencode('.png', np.ascontiguousarray(arr))
    if ok:
        with open(path, 'wb') as fh:
            fh.write(buf.tobytes())
    return bool(ok)


def shoot():
    i = len(_lines)
    try:
        arr = _grab_full()
        half = cv2.resize(arr, (arr.shape[1] // 2, arr.shape[0] // 2),
                          interpolation=cv2.INTER_AREA)
        _save_png(os.path.join(OUT, 's%03d.png' % i), half)
        if i == 0:
            _save_png(os.path.join(OUT, 'full000.png'), arr)
            # 四扇门按当前屏幕矩形裁出来，拼成一张
            row, cv_ = introspect()
            tiles = []
            for sid, (x, y, w, h) in row['doors']:
                pad = 12
                x0 = max(0, x - pad)
                y0 = max(0, y - pad)
                x1 = min(arr.shape[1], x + w + pad)
                y1 = min(arr.shape[0], y + h + pad)
                tiles.append((sid, (x, y, w, h), cv2.resize(
                    arr[y0:y1, x0:x1], None, fx=1.0, fy=1.0,
                    interpolation=cv2.INTER_NEAREST)))
            if tiles:
                _ts = []
                _maxh = 220
                for sid, rect, t in tiles:
                    sc = min(1.0, float(_maxh) / max(1, t.shape[0]))
                    tt = cv2.resize(t, (max(1, int(t.shape[1] * sc)),
                                        max(1, int(t.shape[0] * sc))),
                                    interpolation=cv2.INTER_NEAREST)
                    _ts.append(tt)
                _hh = max(t.shape[0] for t in _ts)
                _pad = [cv2.copyMakeBorder(
                    t, 0, _hh - t.shape[0], 0, 14,
                    cv2.BORDER_CONSTANT, value=(255, 0, 255)) for t in _ts]
                _save_png(os.path.join(OUT, 'doors_now.png'),
                          cv2.hconcat(_pad))
        row, _ = introspect()
        row['t'] = '%.3f' % (time.time() - _t0)
        _lines.append(row)
        if len(_lines) >= N_FRAMES:
            _finish()
    except Exception:
        say('TICK-ERR\n' + traceback.format_exc())


def _finish():
    tm.stop()
    with io.open(os.path.join(OUT, 'introspect.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        for r in _lines:
            fh.write(u'%s\n' % (r,))
    with io.open(os.path.join(OUT, 'meta.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(u'sandbox=%s\nscreen=%dx%d\nframes=%d step_ms=%d\n'
                 % (_SB, _W, _H, len(_lines), STEP_MS))
    say('done: %d 帧' % len(_lines))
    # 汇总"哪些量在逐帧变"
    keys = ['scene_id', 'bg', 'opaque_bg', 'canvas_vis', 'canvas_geo',
            'off', 'scale', 'plan_len', 'last_drawn', 'n_doors', 'doors',
            'pet_k', 'pet_scale', 't_alpha', 'pet_geo', 'dlg_vis', 'dlg_geo']
    for k in keys:
        vals = []
        for r in _lines:
            v = r.get(k)
            if not vals or vals[-1] != v:
                vals.append(v)
        say('  %-12s 变 %2d 次: %s' % (k, len(vals) - 1,
                                    (u'%r' % (vals[:6],))[:220]))
    app.quit()


tm = QTimer()
tm.timeout.connect(shoot)
QTimer.singleShot(int(WARM_S * 1000), lambda: tm.start(STEP_MS))
QTimer.singleShot(int((WARM_S + N_FRAMES * (STEP_MS / 1000.0) + 25) * 1000),
                  _finish)

if __name__ == '__main__':
    rc = app.exec_()
    tm.stop()
    say('exit rc=%d' % rc)
    sys.exit(rc)

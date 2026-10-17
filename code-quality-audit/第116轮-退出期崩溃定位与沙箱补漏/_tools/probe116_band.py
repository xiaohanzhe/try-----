# -*- coding: utf-8 -*-
u"""probe116_band.py —— 以 **~50 Hz** 只抓对话框那一条，测"下半截消失"的**真实频率**。

为什么要另起一个探针
--------------------
`rec116.py` 是 4.5 fps（抓整屏 2560×1600 要 ~85 ms）⇒ 面对一个 ~2~10 Hz 的
振荡会**混叠**，看到的"每隔一帧一翻"到底是 2 Hz 还是 10 Hz **分不出来**。
本探针只抓 `QW=`620×`QH`=300 的子矩形（快 ~20 倍），把真实波形拿到手。

判据
----
  W1 波形频率：把 black 序列过零计数 ⇒ `f = 过零数 / (2 * 时长)`。
     · `f ≳ 20 Hz` ⇒ 人眼看到的是**稳定**（不会称"闪"）
     · `1 ~ 15 Hz` ⇒ **人眼可见的闪** —— 与用户口径「对话框也是闪现」吻合
  W2 同刻一致性（**artifact 判别**）：同一 tick 内**连抓两次**（相隔 ~几 ms），
     若两次几乎一样、却与上一 tick 差别很大 ⇒ 是**真实**的慢变化；
     若两次**本身就差很多** ⇒ 屏幕在几毫秒内真的在变（或抓取被 DWM 撕裂）。
  W3 与产品状态对照：同刻记录 `windowOpacity()` / `height()` / `_cursor_visible`，
     看振荡是否与其中某一个同步（同步 = 找到驱动源）。
"""
import ctypes
import io
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
PKG = os.path.abspath(os.path.join(ROUND, '..', '..', 'ralsei_pet'))
SRC = os.path.join(PKG, 'src')
OUT = os.path.join(ROUND, '_evidence', 'rec116')
os.makedirs(OUT, exist_ok=True)

SECS = float(os.environ.get('PROBE_SECS') or '8')
HZ = float(os.environ.get('PROBE_HZ') or '50')
DOUBLE = os.environ.get('PROBE_DOUBLE', '1') == '1'
# ★ 驱动器开关：**只差这一个变量**就能隔离"摆动是不是宠物移动触发的"
DRIVE = os.environ.get('PROBE_DRIVE', '0') == '1'

# ---- 沙箱四闸（必须在 import main 之前）----
_SB = tempfile.mkdtemp(prefix='probe116_')
for _s in ('vault', 'staging', 'desktop'):
    os.makedirs(os.path.join(_SB, _s), exist_ok=True)
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(_SB, 'vault')
os.environ['RALSEI_DATA_DIR'] = os.path.join(_SB, 'staging')
os.environ['RALSEI_DESKTOP'] = os.path.join(_SB, 'desktop')
os.environ.setdefault('QT_QPA_PLATFORM', 'windows')
os.chdir(PKG)
sys.path.insert(0, SRC)

import numpy as np                                            # noqa: E402
import main as M                                              # noqa: E402
from PyQt5.QtWidgets import QApplication                      # noqa: E402
from PyQt5.QtCore import QTimer                               # noqa: E402


def say(m):
    sys.stdout.write('[probe116] %s\n' % m)
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
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass
_scr = app.primaryScreen()
_W, _H = _scr.geometry().width(), _scr.geometry().height()
dlg = getattr(window, 'dialogue_ui', None)
say('pid=%d screen=%dx%d dlg=%r sandbox=%s'
    % (os.getpid(), _W, _H, type(dlg).__name__ if dlg else None, _SB))

# 抓两个条：TOP（标题/正文，应当稳定）与 BOT（输入行那一带，本轮要查的）
BANDS = [('TOP', 970, 1350, 620, 110), ('BOT', 970, 1460, 620, 140)]
_rows = []
_t0 = time.perf_counter()
_N = [0]


def _frac(px):
    img = px.toImage()
    ptr = img.bits()
    ptr.setsize(img.byteCount())
    a = np.frombuffer(bytes(ptr), np.uint8).reshape(
        img.height(), img.bytesPerLine() // 4, 4)
    a = np.ascontiguousarray(a[:, :img.width(), :3])
    return float((a.max(axis=2) < 16).mean()), float(a.mean())


def tick():
    i = _N[0]
    t = time.perf_counter() - _t0
    row = {'i': i, 't': t}
    try:
        for nm, x, y, w, h in BANDS:
            b, m = _frac(_scr.grabWindow(0, x, y, w, h))
            row[nm + '_b'] = b
            row[nm + '_m'] = m
            if DOUBLE:
                b2, m2 = _frac(_scr.grabWindow(0, x, y, w, h))
                row[nm + '_b2'] = b2
        if dlg is not None:
            row['op'] = float(dlg.windowOpacity())
            row['w'] = dlg.width()
            row['h'] = dlg.height()
            row['y'] = dlg.y()
            row['cur'] = int(bool(getattr(dlg, '_cursor_visible', False)))
            row['anim'] = int(getattr(dlg, '_fade_anim', None) is not None)
            row['typing'] = int(bool(getattr(dlg, 'is_typing', False)))
        row['petx'] = window.x()
        row['pety'] = window.y()
    except Exception as e:
        row['err'] = repr(e)
    _rows.append(row)
    _N[0] = i + 1


tm = QTimer()
tm.timeout.connect(tick)
tm.start(max(1, int(1000.0 / HZ)))

if DRIVE:
    from PyQt5.QtCore import QPoint
    _POS = [(120, 120), (_W - 300, 120), (_W - 300, _H - 420),
            (120, _H - 420)]
    _stt = {'i': -1}

    def _drive():
        _stt['i'] = (_stt['i'] + 1) % len(_POS)
        tx, ty = _POS[_stt['i']]
        try:
            window.target_pos = QPoint(int(tx), int(ty))
            window.is_moving = True
            window.is_sleeping = False
            say('DRIVE => (%d,%d) from=(%d,%d)'
                % (tx, ty, window.x(), window.y()))
        except Exception as e:
            say('DRIVE fail %r' % (e,))

    _tm2 = QTimer()
    _tm2.timeout.connect(_drive)
    _tm2.start(5000)
    QTimer.singleShot(600, _drive)


def _finish():
    tm.stop()
    csvp = os.path.join(OUT, 'probe116_band.csv')
    keys = ['i', 't']
    for k in ('TOP_b', 'TOP_m', 'TOP_b2', 'BOT_b', 'BOT_m', 'BOT_b2',
              'op', 'w', 'h', 'y', 'cur', 'anim', 'typing', 'petx', 'pety',
              'err'):
        if any(k in r for r in _rows):
            keys.append(k)
    with io.open(csvp, 'w', encoding='utf-8', newline='') as fh:
        fh.write(u','.join(keys) + u'\n')
        for r in _rows:
            fh.write(u','.join(
                ('%.4f' % r[k]) if isinstance(r.get(k), float) else
                (u'' if r.get(k) is None else unicode_str(r.get(k)))
                for k in keys) + u'\n')
    # 波形摘要
    rep = [u'# probe116_band  n=%d  目标 %.0f Hz  实测 %.1f Hz'
           % (len(_rows), HZ, len(_rows) / max(1e-9, _rows[-1]['t']))]
    for nm in ('TOP_b', 'BOT_b'):
        v = [r[nm] for r in _rows if nm in r]
        if not v:
            continue
        a = np.array(v, dtype=float)
        thr = 0.5 * (float(a.min()) + float(a.max()))
        z = int(np.sum(np.abs(np.diff((a > thr).astype(int))) > 0))
        dur = _rows[-1]['t'] - _rows[0]['t']
        rep.append(u'%s: min=%.3f max=%.3f 中位=%.3f  过零=%d ⇒ f≈%.2f Hz'
                   % (nm, a.min(), a.max(), float(np.median(a)), z,
                      (z / 2.0) / max(1e-9, dur)))
        # 同刻两次抓取的差异（artifact 判别）
        k2 = nm[:-1] + 'b2'
        if any(k2 in r for r in _rows):
            d = np.array([abs(r[nm] - r[k2]) for r in _rows if k2 in r],
                         dtype=float)
            rep.append(u'    同刻两次 |Δ|= 中位 %.4f  最大 %.4f'
                       % (float(np.median(d)), float(d.max())))
            dc = np.array([abs(_rows[j][nm] - _rows[j - 1][nm])
                           for j in range(1, len(_rows))], dtype=float)
            rep.append(u'    相邻 tick |Δ|= 中位 %.4f  最大 %.4f'
                       % (float(np.median(dc)), float(dc.max())))
    for nm in ('op', 'h', 'cur', 'anim', 'typing'):
        v = sorted(set(r.get(nm) for r in _rows if nm in r))
        rep.append(u'%s 取值集合 = %s' % (nm, v[:10]))
    txt = u'\n'.join(rep) + u'\n'
    with io.open(os.path.join(OUT, 'probe116_band.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    say(txt)
    app.quit()


def unicode_str(x):
    try:
        return u'%s' % (x,)
    except Exception:
        return u''


QTimer.singleShot(int(SECS * 1000), _finish)
rc = app.exec_()
say('exit rc=%d rows=%d' % (rc, len(_rows)))
sys.exit(rc)

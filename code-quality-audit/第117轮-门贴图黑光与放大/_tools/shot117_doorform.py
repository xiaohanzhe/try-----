# -*- coding: utf-8 -*-
u"""shot117_doorform.py —— 把宠物**逐个挪到 4 扇门正中**，各取一张"贴门"证据图。

为什么要它（第117轮）
---------------------
`probe116_doors.py` 的收尾截图是在**扫屏结束那一刻**抓的 ⇒ 宠物多半离门很远
⇒ 渐显 alpha ≈ 0.140 ⇒ 图上几乎看不到门（只剩 WPS 的界面）⇒ **证不了"门长什么样"**。
而用户的两条口径（「黑底也没去干净」「你门的形式也没用用对」）恰恰**只有在
alpha = 1.0（宠物贴着门）时**才看得清。

★ 本脚本只做一件事：`window.move()` 把宠物窗口**中心**压到门矩形**中心**上，
  等 `door_reveal` 的渐显收敛（贴门 ⇒ alpha 应到 1.0），再抓：
    · 该门矩形外扩一圈的裁剪（看门本体）
    · 整屏（看门与壁纸/对话框/任务栏的关系）
★ 判据不掺假：抓完**回读 alpha**（`window._desktop_screen_doors()`）一并写进报告，
  这样"这张图是不是在 alpha=1.0 下拍的"**有据可查**，不靠脚本自称。

跑法
----
  set PROBE_DWELL=1.6
  C:\\Python311\\python.exe "...\\_tools\\shot117_doorform.py"
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
OUT = os.environ.get('PROBE_OUT', os.path.join(ROUND, '_evidence', 'rec117'))
os.makedirs(OUT, exist_ok=True)

DWELL = float(os.environ.get('PROBE_DWELL') or '1.6')
TAG = os.environ.get('PROBE_TAG') or 'doorform117'
#: ★★ 第117轮补录：把宠物窗口**调成全透明**再取图。
#  为什么必须这样：`doorform1` 那批图里宠物**压在门上**（如门 D 只在
#  门框边上露出一圈），"门长什么样"看不全。而 `_pet_screen_rect()` 只读
#  **窗口几何**（`self.x()/y()/width()/height()`）、**不看可见性**
#  ⇒ 把窗口设成全透明**不会**改变门的 alpha，纯粹去掉遮挡。
#  ★ 注意：**不能用 `window.hide()`** —— 那可能连带停掉场景层的重绘。
GHOST = (os.environ.get('PROBE_GHOST') or '1') not in ('0', 'false', 'False')
#: ★★ 第117轮新增：取图前**先把对话框收起来**。
#  为什么：门 B（Niko 的家）贴在**工作区底边**（y=1399），而对话框常驻屏幕底部
#  ⇒ `doorform117_doorB` 那批图里门被对话框整块盖住，**证不了门长什么样**。
#  ★ 收起对话框**不会**改变门的 alpha（`_pet_screen_rect()` 只读窗口几何），
#    纯属去掉遮挡 —— 与 GHOST 同一个理由。
HIDE_DLG = (os.environ.get('PROBE_HIDE_DLG') or '1') not in ('0', 'false', 'False')

# ---- 沙箱四闸（必须在 import main 之前）----
_SB = tempfile.mkdtemp(prefix='shot117df_')
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
    sys.stdout.write('[shot117df] %s\n' % m)
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
_scr = app.primaryScreen()
_W, _H = _scr.geometry().width(), _scr.geometry().height()
say('pid=%d screen=%dx%d sandbox=%s' % (os.getpid(), _W, _H, _SB))


def _grab_full():
    pm = _scr.grabWindow(0)
    im = pm.toImage()
    ptr = im.bits()
    ptr.setsize(im.byteCount())
    a = np.frombuffer(bytes(ptr), np.uint8).reshape(
        im.height(), im.bytesPerLine() // 4, 4)[:, :im.width(), :3]
    return np.ascontiguousarray(a)


def _wr(path, arr):
    import cv2
    ok, buf = cv2.imencode('.png', arr)
    if not ok:
        return -1
    with open(path, 'wb') as fh:        # ★ 中文路径 ⇒ cv2.imwrite 会静默 False
        fh.write(buf.tobytes())
    return os.path.getsize(path)


def _layer_size():
    u"""★★★ 门摆位用的**画布尺寸** —— 必须**问产品自己**，不能拿整屏。

    ★ 真教训（`doorform1/2` 都踩了）：本脚本原来调
      `window._desktop_screen_doors(_W, _H)`，而 `_W/_H` 取自
      `primaryScreen().geometry()` = **2560×1600（整屏）**。
      但产品在 `_update_scene_layer` 里传的是 `_desktop_layer_size()`
      = **2560×1528（工作区，扣掉任务栏那 72px）**（第117轮为治"任务栏反复
      收放"改的）。而 `desk_doors.door_screen_rect` 的摆位**吃 screen_h**：
        · bottom: `y = sh - h - margin`
        · left/right: `y = (sh - h) // 2`
      ⇒ 两套口径差 **72px** ⇒ `doorform1/2` 的 B/C/D 三张裁剪图**整体偏位**
      （B 偏 72px、C/D 偏 36px），门不在裁剪框中心。
      ⇒ 现在**直接问产品**：优先 `_desktop_layer_size()`，取不到才退化到整屏。
    """
    try:
        sz = window._desktop_layer_size()
        if sz and len(sz) == 2 and int(sz[0]) > 0 and int(sz[1]) > 0:
            return (int(sz[0]), int(sz[1]))
    except Exception as e:
        say('_desktop_layer_size 失败（退化为整屏）: %r' % (e,))
    return (_W, _H)


def _doors():
    u"""`{letter: (rect, alpha)}` + 字母表（现读 `desktop.json`，不写死）。"""
    import json
    m = {}
    try:
        d = json.load(io.open(os.path.join(PKG, 'assets', 'scenes',
                                           'desktop.json'), encoding='utf-8'))
        for o in d.get('objects', []):
            if not isinstance(o, dict):
                continue
            src = o.get('src') or ''
            nm = (o.get('sprite') or o.get('image') or '')
            if isinstance(src, str) and src.lower().startswith('obj_door'):
                head = src[len('obj_door'):].split('_', 1)[0]
                if len(head) == 1 and nm:
                    m[nm] = head.upper()
    except Exception as e:
        say('建字母表失败: %r' % (e,))
    d = {}
    _lw, _lh = _layer_size()
    try:
        got = window._desktop_screen_doors(_lw, _lh)
    except Exception as e:
        say('_desktop_screen_doors 失败: %r' % (e,))
        got = []
    for it in (got or []):
        sid = str(it[0])
        d[m.get(sid, sid)] = (tuple(int(v) for v in it[1]),
                              float(it[2]) if len(it) >= 3 else 1.0)
    return d


rep = [u'# shot117_doorform tag=%s  dwell=%.1fs  ghost=%s' % (TAG, DWELL, GHOST)]
_STEPS = []          # (letter, rect, alpha) —— 依次取图

_d0 = _doors()
rep.append(u'门摆位口径（画布尺寸）= %r  ← 产品 `_desktop_layer_size()`；'
           u'整屏 = %r' % (_layer_size(), (_W, _H)))
rep.append(u'发现的门 = %r' % ({k: v[0] for k, v in _d0.items()},))
_order = ['A', 'B', 'C', 'D']
#: 字母 → 方位（与 `desk_doors.SIDE_LETTERS` 同源：上A/下B/左C/右D）。
_SIDE = {'A': 'top', 'B': 'bottom', 'C': 'left', 'D': 'right'}
#: ★★★ 宠物站位：**贴门但别压住门**。
#   为什么必须偏开：第一版把宠物窗口中心**正压在门中心**上 ⇒ 宠物精灵
#   整个盖住门 ⇒ 取到的图里只有 Ralsei、看不到门（等于没取）。
#   为什么取 110px：`door_reveal` 的口径是"间距 ≤ 128px 即 alpha=1.0"
#   ⇒ 110px 仍在**满显**区间，同时让门完整露出来。
#   ★ 这个数字**不是猜的**：`probe116_doors` 实测门 C/D 贴门(≤220px) alpha 中位
#     = 1.000，与 `door_reveal.FAR_FRAC×1600=128` 一致。
_OFF = 110.0


def _pet_topleft_for(side, r):
    u"""把宠物放在门的**外侧偏下/偏内**，与门边留 `_OFF` 像素。"""
    px = r[0] + r[2] // 2 - window.width() // 2
    py = r[1] + r[3] // 2 - window.height() // 2
    if side == 'top':            # 门在屏幕正上 ⇒ 宠物往**下**站
        py = int(r[1] + r[3] + _OFF)
    elif side == 'bottom':       # 门在正下 ⇒ 宠物往上站
        py = int(r[1] - _OFF - window.height())
    elif side == 'left':         # 门在正左 ⇒ 宠物往右站
        px = int(r[0] + r[2] + _OFF)
    else:                        # right ⇒ 宠物往左站
        px = int(r[0] - _OFF - window.width())
    return px, py


def _step(i):
    if i >= len(_order):
        _finish()
        return
    L = _order[i]
    ds = _doors()
    if L not in ds:
        rep.append(u'门%s 未出现在屏幕层清单里 ⇒ 跳过' % L)
        QTimer.singleShot(50, lambda: _step(i + 1))
        return
    r, _a = ds[L]
    # ---- 把宠物放到门**旁边**（贴门但不遮门）----
    side = _SIDE.get(L, 'top')
    px, py = _pet_topleft_for(side, r)
    try:
        window.target_pos = None
    except Exception:
        pass
    for _attr, _val in (('is_moving', False), ('is_sleeping', False),
                        ('is_dragging', False)):
        try:
            setattr(window, _attr, _val)
        except Exception:
            pass
    try:
        window.move(px, py)
    except Exception as e:
        rep.append(u'门%s move 失败 %r' % (L, e))
    if GHOST:
        # ★ 只改**窗口不透明度**，不改几何 ⇒ 门 alpha 不变（见 GHOST 注释）。
        try:
            window.setWindowOpacity(0.0)
        except Exception as e:
            rep.append(u'门%s setWindowOpacity(0) 失败 %r' % (L, e))
    say('门%s rect=%r ⇒ 宠物窗口移到 (%d,%d)  ghost=%s  等 %.1fs'
        % (L, r, px, py, GHOST, DWELL))
    QTimer.singleShot(int(DWELL * 1000), lambda: _shot(i, L))


def _shot(i, L):
    if HIDE_DLG:
        try:
            window.dialogue_ui.hide()
            app.processEvents()          # ★ 先让"隐藏"真的落到屏上，再抓
        except Exception as e:
            rep.append(u'门%s 收对话框失败 %r' % (L, e))
    ds = _doors()
    r, a = ds.get(L, ((0, 0, 0, 0), -1.0))
    full = _grab_full()
    pad = max(48, r[2] // 2)
    x0 = max(0, r[0] - pad)
    y0 = max(0, r[1] - pad)
    x1 = min(_W, r[0] + r[2] + pad)
    y1 = min(_H, r[1] + r[3] + pad)
    crop = np.ascontiguousarray(full[y0:y1, x0:x1])
    n1 = _wr(os.path.join(OUT, 'shot117_%s_door%s.png' % (TAG, L)), crop)
    n2 = _wr(os.path.join(OUT, 'shot117_%s_full%s.png' % (TAG, L)), full)
    pet = (window.x(), window.y(), window.width(), window.height())
    _STEPS.append((L, r, a, pet))
    rep.append(u'门%s 贴门取图：rect=%r alpha=%.4f 宠物窗口=%r  '
               u'裁剪=%dB 整屏=%dB' % (L, r, a, pet, n1, n2))
    QTimer.singleShot(80, lambda: _step(i + 1))


def _finish():
    try:
        window.setWindowOpacity(1.0)          # 还原（本进程即将退出，仍做干净）
    except Exception:
        pass
    rep.append(u'')
    rep.append(u'★ 贴门时 alpha 一览（判"这是 alpha=1.0 下拍的"用）:')
    for L, r, a, pet in _STEPS:
        rep.append(u'   门%s rect=%r alpha=%.4f pet=%r' % (L, r, a, pet))
    txt = u'\n'.join(rep) + u'\n'
    with io.open(os.path.join(OUT, 'shot117_%s.txt' % TAG), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    say(txt)
    app.quit()


QTimer.singleShot(1200, lambda: _step(0))
QTimer.singleShot(60000, _finish)       # 兜底：1 分钟必退
rc = app.exec_()
say('exit rc=%d steps=%d' % (rc, len(_STEPS)))
sys.exit(rc)

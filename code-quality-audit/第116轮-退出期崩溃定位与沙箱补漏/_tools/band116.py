# -*- coding: utf-8 -*-
u"""band116.py —— 以 ~30 Hz 采**对话框下沿那一条带**，拍成"瀑布图"看究竟是什么在闪。

为什么需要它（第116轮）
-----------------------
`probe116_doors`（8.2 Hz）在**门 B 那条带**上量到黑占比在 **0.80 ↔ 0.99**
之间来回跳 ⇒ 用户说的「对话框也是闪现」确实存在。但 8.2 Hz 太慢，
**分不清是"光标闪烁"还是"整框在跳"**（混叠）。⇒ 本脚本：
  · 采得**快**（~30 Hz，一次只抓 140×27 的小区域，`grabWindow` 只要几毫秒）
  · 输出**瀑布图**（每一帧一行像素，纵向堆叠）—— 一眼看出"哪一段在变"
  · 同时落**逐帧黑占比 CSV**，并把静态像素（永不变化的部分）标出来

判据
----
  · 若变化只集中在**输入框左侧一小块**（宽度 ~4px）⇒ 是**光标闪烁**
  · 若整条带的**边框/底色**都在变 ⇒ 是**整框在闪**
  · 若"变化像素"只在**某一 x 区间** ⇒ 该区间的 x 范围会直接打印出来
"""
import ctypes
import csv
import io
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
PKG = os.path.abspath(os.path.join(ROUND, '..', '..', 'ralsei_pet'))
SRC = os.path.join(PKG, 'src')
OUT = os.environ.get('PROBE_OUT', os.path.join(ROUND, '_evidence', 'rec116'))
os.makedirs(OUT, exist_ok=True)

SECS = float(os.environ.get('BAND_SECS') or '8')
HZ = float(os.environ.get('BAND_HZ') or '30')
TAG = os.environ.get('BAND_TAG') or 'band'

_SB = tempfile.mkdtemp(prefix='band116_')
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
    sys.stdout.write('[band116] %s\n' % m)
    sys.stdout.flush()


def _spans(cols):
    u"""把升序列号合并成连续区间 `[(a,b), ...]`（用于"变的是哪几段"）。"""
    cols = [int(c) for c in cols]
    if not cols:
        return []
    out = []
    s = p = cols[0]
    for c in cols[1:]:
        if c > p + 1:
            out.append((s, p))
            s = c
        p = c
    out.append((s, p))
    return out


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

#: 采样区：默认取**对话框下半截 + 输入框那一行**（含门 B 的整条），
#: 这样"变的是光标 / 输入框 / 门的像素"能从图里直接看出来。
#: 可用 `BAND_REGION=x,y,w,h` 覆盖。
R = (960, 1470, 660, 120)
_env_R = os.environ.get('BAND_REGION')
if _env_R:
    try:
        R = tuple(int(v) for v in _env_R.split(','))
    except Exception:
        pass
say('pid=%d screen=%dx%d 采样区=%r %.1fHz %.0fs'
    % (os.getpid(), _W, _H, R, HZ, SECS))

_t0 = time.perf_counter()
_frames = []
_ts = []


def grab():
    pm = _scr.grabWindow(0, R[0], R[1], R[2], R[3])
    im = pm.toImage()
    ptr = im.bits()
    ptr.setsize(im.byteCount())
    a = np.frombuffer(bytes(ptr), np.uint8).reshape(
        im.height(), im.bytesPerLine() // 4, 4)[:, :im.width(), :3]
    return np.ascontiguousarray(a)


def tick():
    try:
        a = grab()
    except Exception:
        return
    _frames.append(a)
    _ts.append(time.perf_counter() - _t0)
    if _ts[-1] >= SECS:
        tm.stop()
        _finish()


tm = QTimer()
tm.timeout.connect(tick)
tm.start(max(1, int(1000.0 / HZ)))
QTimer.singleShot(int((SECS + 12) * 1000), lambda: (tm.stop(), _finish()))


def _finish():
    if getattr(_finish, '_done', False):
        return
    _finish._done = True
    rep = [u'# band116 tag=%s  区=%r  帧数=%d  时长=%.2fs  ⇒ %.1f Hz'
           % (TAG, R, len(_frames), _ts[-1] if _ts else 0,
              len(_frames) / max(1e-9, _ts[-1] if _ts else 1))]
    if not _frames:
        rep.append(u'✗ 一帧都没采到')
        _write(rep)
        return
    n = min(len(_frames), len(_ts))
    arr = np.stack([_frames[i].astype(np.int16) for i in range(n)])
    ts = np.array(_ts[:n], dtype=float)

    # ---- 逐帧黑占比 ----
    blk = (arr.max(axis=3) < 16).mean(axis=(1, 2))
    rep.append(u'黑占比 min=%.3f max=%.3f 中位=%.3f  极差=%.3f'
               % (blk.min(), blk.max(), float(np.median(blk)),
                  blk.max() - blk.min()))
    seq = (blk > 0.5 * (blk.min() + blk.max())).astype(int)
    flips = int(np.sum(np.abs(np.diff(seq)) > 0))
    rep.append(u'阈值翻转次数=%d  ⇒ 平均周期 %.3f s'
               % (flips, 2.0 * (ts[-1] - ts[0]) / max(1, flips)))

    # ---- 逐**像素**：哪些位置在变 ----
    var = arr.std(axis=0).max(axis=2)          # (h, w)
    changing = var > 12
    rep.append(u'变化像素数 = %d / %d' % (int(changing.sum()), changing.size))
    cols = np.where(changing.any(axis=0))[0]
    rows = np.where(changing.any(axis=1))[0]
    if len(cols):
        # 把连续 x 区间合并，直接告诉"变的是哪几块"
        spans = []
        s = cols[0]
        p = cols[0]
        for c in cols[1:]:
            if c > p + 1:
                spans.append((int(s), int(p)))
                s = c
            p = c
        spans.append((int(s), int(p)))
        rep.append(u'变化列区间（相对采样区 x，共 %d 宽） = %s'
                   % (R[2], spans))
        rep.append(u'变化行区间 = %d..%d（共 %d 行 / %d）'
                   % (int(rows.min()), int(rows.max()), len(rows), R[3]))
    else:
        rep.append(u'★ 没有任何像素在变 ⇒ 这一带完全静止')

    # ---- 瀑布图：每帧一行（对 y 取均值），放大成图 ----
    try:
        import cv2
        wf = np.stack([_frames[i][:, :, ::-1] for i in range(n)])  # 保持 RGB
        # 竖向堆叠（每帧一张），横向裁到 140
        big = np.concatenate([wf[i] for i in range(n)], axis=0)
        big = np.repeat(big, 3, axis=1)             # 横向放大 3 倍便于看
        p1 = os.path.join(OUT, 'band116_%s_stack.png' % TAG)
        ok, buf = cv2.imencode('.png', big[:, :, ::-1])
        if ok:
            with open(p1, 'wb') as fh:
                fh.write(buf.tobytes())
            rep.append(u'★ 堆叠图（每帧一条，共 %d 条）=%s (%d B)'
                       % (n, os.path.basename(p1), os.path.getsize(p1)))
        # 差异图：相对"中位帧"的绝对差（放大 4 倍）
        med = np.median(arr, axis=0)
        d = np.abs(arr - med).mean(axis=3)          # (n, h, w)
        # ★ 取**时间上**的均值（axis=0）才是"哪些像素在变"的热图。
        #   第一版写成 `np.stack([d]*3, axis=2)` ⇒ 形状变 (n,h,3,w) ⇒
        #   `cv2.imencode` 报 `Invalid image width in IHDR`（**我以为出图成功**）。
        d = np.clip(d.mean(axis=0) * 4, 0, 255).astype(np.uint8)
        d = np.stack([d] * 3, axis=2)
        d = np.repeat(d, 2, axis=0)
        p2 = os.path.join(OUT, 'band116_%s_diff.png' % TAG)
        ok, buf = cv2.imencode('.png', d[:, :, ::-1])
        if ok:
            with open(p2, 'wb') as fh:
                fh.write(buf.tobytes())
            rep.append(u'★ 差异热图（亮=变化大）= %s (%d B)'
                       % (os.path.basename(p2), os.path.getsize(p2)))
        # ★ 代表性单帧：挑"黑占比最低"和"最高"各 3 帧原样落盘，肉眼对照。
        order = np.argsort(blk)
        picks = list(order[:3]) + list(order[-3:])
        for j, idx in enumerate(picks):
            idx = int(idx)
            fp = os.path.join(OUT, 'band116_%s_f%02d_b%.2f.png'
                              % (TAG, idx, blk[idx]))
            ok, buf = cv2.imencode('.png', _frames[idx][:, :, ::-1])
            if ok:
                with open(fp, 'wb') as fh:
                    fh.write(buf.tobytes())
        rep.append(u'★ 代表性单帧已落盘 6 张（黑占比最低 3 + 最高 3）')
        # ★ 二态分解：把"高频振荡窗口"内的帧按黑占比分成高/低两态，
        #   逐行/逐列比较 ⇒ 用**数字**指出"是哪几行哪几列在闪"，
        #   不再靠看图猜（同一轮里我已经在 27px 的窄条上猜错过好几次）。
        t0 = 2.0
        win = [i for i in range(n) if ts[i] >= t0]
        if len(win) >= 8:
            b = blk[win]
            hi = [i for i in win if b[i - win[0]] >= 0.93]
            lo = [i for i in win if b[i - win[0]] <= 0.88]
            rep.append(u'二态分解（t≥%.1fs）：高态帧=%d（黑占比≈%.2f）'
                       u' 低态帧=%d'
                       % (t0, len(hi),
                          float(np.mean([blk[i] for i in hi])) if hi else -1,
                          len(lo)))
            if hi and lo:
                A = arr[hi].astype(np.float32).mean(axis=0)
                B = arr[lo].astype(np.float32).mean(axis=0)
                drow = np.abs(A - B).mean(axis=(1, 2))     # 每行差异
                dcol = np.abs(A - B).mean(axis=(0, 2))     # 每列差异
                rep.append(u'逐行差异（>8 的行） = %s'
                           % ([(int(y), round(float(drow[y]), 1))
                               for y in np.where(drow > 8)[0]],))
                rep.append(u'逐行差异最大 = %.1f @ 行 %d'
                           % (float(drow.max()), int(drow.argmax())))
                rep.append(u'逐列差异（>8 的列，合并区间） = %s'
                           % (_spans(list(np.where(dcol > 8)[0]))))
                rep.append(u'逐列差异最大 = %.1f @ 列 %d（采样区 x=%d）'
                           % (float(dcol.max()), int(dcol.argmax()),
                              R[0] + int(dcol.argmax())))
                # ★ 两态各存一张"平均图"（放大 6 倍 + 纵向放大 6 倍），
                #   这样那条 5px 的横带到底是什么，一眼能看出。
                try:
                    import cv2
                    for nm, M_ in ((u'Hi(黑多)', A), (u'Lo(黑少)', B)):
                        img = np.clip(M_, 0, 255).astype(np.uint8)
                        img = np.repeat(np.repeat(img, 6, axis=0), 6, axis=1)
                        fp = os.path.join(OUT, 'band116_%s_state%s.png'
                                          % (TAG, 'Hi' if M_ is A else 'Lo'))
                        ok, buf = cv2.imencode('.png', img[:, :, ::-1])
                        if ok:
                            with open(fp, 'wb') as fh:
                                fh.write(buf.tobytes())
                            rep.append(u'   ★ 状态图 %s = %s (%d B)'
                                       % (nm, os.path.basename(fp),
                                          os.path.getsize(fp)))
                except Exception as e:
                    rep.append(u'   状态图失败 %r' % (e,))

        # ★ 蒙太奇：把"振荡窗口"内**每一帧**竖着拼起来（帧间加 2px 白分隔），
        #   这样"到底是哪一列/哪一行在闪"能从一张图里直接读出来，
        #   不需要再去猜"哪两张帧代表两个状态"。
        if os.environ.get('BAND_MONTAGE', '1') == '1':
            t0 = 2.0
            idx0 = next((i for i in range(n) if ts[i] >= t0), 0)
            sel = list(range(idx0, min(n, idx0 + 48)))
            if sel:
                sep = np.full((2, _frames[0].shape[1], 3), 255, np.uint8)
                parts = []
                for i in sel:
                    parts.append(_frames[i][:, :, ::-1])
                    parts.append(sep)
                mon = np.concatenate(parts, axis=0)
                mon = np.repeat(mon, 3, axis=1)
                p3 = os.path.join(OUT, 'band116_%s_montage.png' % TAG)
                ok, buf = cv2.imencode('.png', mon[:, :, ::-1])
                if ok:
                    with open(p3, 'wb') as fh:
                        fh.write(buf.tobytes())
                    rep.append(u'★ 振荡窗口蒙太奇（%d 帧，每帧 %d 行 + 2px 分隔）'
                               u'= %s (%d B)'
                               % (len(sel), _frames[0].shape[0],
                                  os.path.basename(p3), os.path.getsize(p3)))
                    rep.append(u'   蒙太奇对应 t = %.2f … %.2f s'
                               % (ts[sel[0]], ts[sel[-1]]))
                    rep.append(u'   蒙太奇各帧黑占比 = %s'
                               % ([round(float(blk[i]), 2) for i in sel[:24]],))
    except Exception as e:
        rep.append(u'出图失败 %r' % (e,))

    p = os.path.join(OUT, 'band116_%s.csv' % TAG)
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['i', 't', 'black', 'mean'])
        for i in range(n):
            w.writerow([i, round(float(ts[i]), 4), round(float(blk[i]), 4),
                        round(float(arr[i].mean()), 2)])
    _write(rep)


def _write(rep):
    txt = u'\n'.join(rep) + u'\n'
    with io.open(os.path.join(OUT, 'band116_%s.txt' % TAG), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    say(txt)
    app.quit()


rc = app.exec_()
sys.exit(rc)

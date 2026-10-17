# -*- coding: utf-8 -*-
u"""analyze116.py —— 对 `rec116.avi` 做**逐帧分析**（回应「你自己录屏然后逐帧分析去」）。

判据（全部**先量后说**，不许"看着像"）
------------------------------------
  D1 门的**帧间稳定性**：每个门矩形内 `mean|Δ|`；> 8 记一次"跳"。
     ⇒ 用户说「门在闪现」；若这里恒 0，则"闪"不在门上（回到对话框/任务栏）。
  D2 门的**黑底占比**：门矩形内 `max(R,G,B) < 16` 的像素比例。
     ⇒ 用户说「黑底也没去干净」；这个数就是"没去干净"的**量**。
        ★ 贴图自身带黑（`spr_giantdarkdoor_0` 实测 82.6% 纯黑）与"程序没抠黑"
          是两件事，本判据只量**屏幕上**的黑，能否区分见 D4。
  D3 门的**可见性**：门矩形是否真被别的窗口盖住（用整帧与"只有门"的差异无法判，
     改判：门矩形内若出现**大面积与门无关的亮像素**，说明有窗口压在上面）。
  D4 对话框区域：`mean` 时序 + 帧间 `Δ`；用户说「对话框也是闪现」。
  D5 门**贴图自身**的 alpha/黑占比（直接读 PNG，与屏幕值对照）。

产物：`_evidence/rec116/analysis/` 下的接触表 PNG + `report.txt`。
★ 中文路径：`cv2.VideoCapture` 走 FFmpeg，路径先复制到 ASCII 临时区（本项目已知坑）。
"""
import csv
import io
import os
import shutil
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROUND, '_evidence', 'rec116')
ANA = os.path.join(OUT, 'analysis')
os.makedirs(ANA, exist_ok=True)
TMP = r'E:\Download\_tmp\rec116_ascii'

# ---- 权威矩形（由 desk_doors 口径确定性算出，不猜）----
# k = min(1.2*144/192, 1.2*98/155) = min(0.9, 0.758709..) = 0.758709..
K = min(1.2 * 144.0 / 192.0, 1.2 * 98.0 / 155.0)
DOOR_SPRITE = {                       # 字母 -> (贴图, 原始尺寸)
    'A': ('spr_darkdoor_0.png', (44, 56)),
    'B': ('niko_door_portal.png', (192, 128)),
    'C': ('ut_castle_realdoor_0.png', (44, 99)),
    'D': ('spr_giantdarkdoor_0.png', (180, 155)),
}
ASSET_DIR = os.path.abspath(os.path.join(
    ROUND, '..', '..', 'ralsei_pet', 'assets', 'scenes', 'objs'))


def _rects(W, H):
    out = {}
    for letter, (_nm, (w0, h0)) in DOOR_SPRITE.items():
        w = max(1, int(round(w0 * K)))
        h = max(1, int(round(h0 * K)))
        if letter == 'A':
            x, y = (W - w) // 2, 0
        elif letter == 'B':
            x, y = (W - w) // 2, H - h
        elif letter == 'C':
            x, y = 0, (H - h) // 2
        else:
            x, y = W - w, (H - h) // 2
        out[letter] = (x, y, w, h)
    return out


def _load_ascii(path):
    u"""把录像复制到 ASCII 临时路径（`cv2.VideoCapture` 走 FFmpeg，中文路径不可靠）。

    ★★ 教训（本轮踩到，**必须每次覆盖**）：原来写成"不存在才复制" ⇒
      改后复录时，分析器**读的还是上一次的旧录像**（136 帧 vs 新 CSV 130 帧），
      于是 D1/D2/D3 打出的像素数全是**改前**的值 —— 一份看起来完全正常的
      假报告。**取证工具读的必须是本次产物**，故无条件覆盖。
    """
    os.makedirs(TMP, exist_ok=True)
    dst = os.path.join(TMP, 'rec116.avi')
    shutil.copy2(path, dst)
    src_sz = os.path.getsize(path)
    if os.path.getsize(dst) != src_sz:
        raise IOError('复制后尺寸不符: %d != %d' % (os.path.getsize(dst), src_sz))
    return dst


def _png_size_ascii(p):
    """读 PNG 尺寸（中文路径安全）。"""
    buf = np.fromfile(p, dtype=np.uint8)
    im = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    return None if im is None else (im.shape[1], im.shape[0], im)


def _black_frac(region, thr=16):
    if region is None or region.size == 0:
        return None
    return float((region.max(axis=2) < thr).mean())


def _mean(region):
    if region is None or region.size == 0:
        return None
    return float(region.mean())


def _crop(arr, r, pad=0, W=None, H=None):
    x, y, w, h = r
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = x + w + pad
    y1 = y + h + pad
    if W is not None:
        x1 = min(W, x1)
    if H is not None:
        y1 = min(H, y1)
    return np.ascontiguousarray(arr[y0:y1, x0:x1])


def _write_png(path, img):
    u"""★ 必须用 imencode + 手动写盘 —— `cv2.imwrite` 在中文路径下**静默失败**
    （返回 False，不抛异常；本轮实测：报告写了、图全没了）。
    写完**查盘核实**（不信自己的返回值）。"""
    ok, buf = cv2.imencode('.png', img)
    if not ok:
        raise IOError('imencode 失败: %s' % path)
    with open(path, 'wb') as fh:
        fh.write(buf.tobytes())
    if not os.path.exists(path) or os.path.getsize(path) <= 0:
        raise IOError('写盘后文件不存在/为空: %s' % path)
    return os.path.getsize(path)


def _label(img, text, x=4, y=20, scale=0.6):
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                scale, (0, 0, 255), 2, cv2.LINE_AA)


def main():
    rep = io.StringIO()

    def w(s=''):
        rep.write(s + u'\n')

    # ---- 读 CSV ----
    rows = []
    with io.open(os.path.join(OUT, 'rec116_frames.csv'), 'r',
                 encoding='utf-8', newline='') as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    w(u'# rec116 逐帧分析  frames=%d' % len(rows))

    # ---- 读录像 ----
    avi = _load_ascii(os.path.join(OUT, 'rec116.avi'))
    cap = cv2.VideoCapture(avi)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    if not frames:
        w(u'★ 致命：录像读不出帧')
        print(rep.getvalue())
        return 3
    H, W = frames[0].shape[:2]
    w(u'录像 %d 帧  %dx%d' % (len(frames), W, H))

    RECT = _rects(W, H)
    w(u'\n## 门矩形（确定性口径 k=%.6f）' % K)
    for l in 'ABCD':
        w(u'  %s %s %r' % (l, DOOR_SPRITE[l][0], RECT[l]))

    # 对话框矩形（CSV 里出现过两种，取并集）
    # ★ 只取 `dlg_vis==1` 的行：窗口**还没 show** 时 `geometry()` 是默认值
    #   `(0,0,620,230)`，混进来会把并集拉成"从屏幕左上角开始"（本轮踩到过）。
    _drows = [r for r in rows if (r.get('dlg_vis') or '0') == '1'
              and r.get('dlg_x') and r.get('dlg_w')]
    dlgx = [int(r['dlg_x']) for r in _drows]
    dlgy = [int(r['dlg_y']) for r in _drows]
    dlgw = [int(r['dlg_w']) for r in _drows]
    dlgh = [int(r['dlg_h']) for r in _drows]
    if dlgx:
        DX0 = min(dlgx)
        DY0 = min(dlgy)
        DX1 = max(a + b for a, b in zip(dlgx, dlgw))
        DY1 = max(a + b for a, b in zip(dlgy, dlgh))
        DLG = (DX0, DY0, DX1 - DX0, DY1 - DY0)
    else:
        DLG = None
    w(u'\n## 对话框矩形（并集） %r' % (DLG,))

    n = min(len(frames), len(rows))

    # ---- D1/D2/D3：门 ----
    w(u'\n## D1/D2 门：帧间 stability + 黑底占比')
    w(u'%4s %8s %8s %8s %8s %8s %8s' % ('L', 'mean整段', 'maxΔ', '跳次数',
                                        '黑%中位', '黑%最大', '亮%最大'))
    stats = {}
    _pairs = list(range(1, n))          # 帧对 (i-1, i)，与字母无关 ⇒ 先建好
    for l in 'ABCD':
        diffs, blacks, means = [], [], []
        r = RECT[l]
        for i in range(n):
            c = _crop(frames[i], r, W=W, H=H)
            blacks.append(_black_frac(c))
            means.append(_mean(c))
        for i in _pairs:
            c = _crop(frames[i], r, W=W, H=H)
            p = _crop(frames[i - 1], r, W=W, H=H)
            if c.shape == p.shape:
                diffs.append(float(np.abs(c.astype(np.int16) -
                                          p.astype(np.int16)).mean()))
        if not diffs:
            diffs = [0.0]
        jumps = sum(1 for d in diffs if d > 8.0)
        bm = float(np.median([b for b in blacks if b is not None]))
        bx = float(np.max([b for b in blacks if b is not None]))
        bright = float(np.max([1.0 - b for b in blacks if b is not None]))
        stats[l] = dict(mean=float(np.mean(means)), maxd=float(np.max(diffs)),
                        jumps=jumps, black_med=bm, black_max=bx,
                        bright_max=bright, means=means, blacks=blacks)
        w(u'%4s %8.2f %8.2f %8d %7.3f %8.3f %8.3f'
          % (l, stats[l]['mean'], stats[l]['maxd'], jumps, bm, bx, bright))
    w(u'  ⇒ "maxΔ≈0 且跳次数=0" ⇒ 这扇门在屏幕上**没动**。')

    # 门矩形内 mean 的时序突变（另一种"闪"：内容变了但几何没变）
    w(u'\n## D3 门矩形内 mean 的异常帧（偏离中位 > 6）')
    for l in 'ABCD':
        ms = np.array(stats[l]['means'], dtype=float)
        med = float(np.median(ms))
        bad = [i for i, v in enumerate(ms) if abs(v - med) > 6.0]
        w(u'  门%s 中位=%.2f  异常帧(%d): %s'
          % (l, med, len(bad), bad[:40]))

    # ---- D4：对话框 ----
    w(u'\n## D4 对话框区域')
    if DLG:
        dmeans, ddiffs = [], []
        prevc = None
        for i in range(n):
            c = _crop(frames[i], DLG, W=W, H=H)
            dmeans.append(_mean(c))
            if prevc is not None and c.shape == prevc.shape:
                ddiffs.append(float(np.abs(c.astype(np.int16) -
                                           prevc.astype(np.int16)).mean()))
            else:
                ddiffs.append(0.0)
            prevc = c
        dm = np.array(dmeans, dtype=float)
        med = float(np.median(dm))
        w(u'  mean 中位=%.2f  min=%.2f  max=%.2f' % (med, dm.min(), dm.max()))
        diffs = np.array(ddiffs, dtype=float)
        w(u'  帧间Δ: 中位=%.2f  最大=%.2f  >8 的帧数=%d/%d'
          % (float(np.median(diffs)), float(diffs.max()),
             int((diffs > 8).sum()), len(diffs)))
        # opacity（CSV）与区域 mean 的关系
        ops = [float(r['dlg_op'] or 0) for r in rows[:n]]
        w(u'  windowOpacity 序列 min=%.3f  低于 0.9 的帧: %s'
          % (min(ops), [i for i, v in enumerate(ops) if v < 0.9]))
        # 找"整段最亮的连续区间"（= 有东西压上来 / 或在上面）
        order = np.argsort(-dm)
        w(u'  最亮 12 帧: %s' % sorted(order[:12].tolist()))
        w(u'  最暗 12 帧: %s' % sorted(order[-12:].tolist()))

    # ---- D5：门贴图自身 ----
    w(u'\n## D5 门贴图自身（alpha / 纯黑）')
    for l, (nm, sz) in DOOR_SPRITE.items():
        p = os.path.join(ASSET_DIR, nm)
        got = _png_size_ascii(p)
        if got is None:
            w(u'  门%s %s ⇒ 读不出' % (l, nm))
            continue
        sw, sh, im = got
        rgb = im[:, :, :3]
        black = float((rgb.max(axis=2) < 16).mean())
        if im.shape[2] == 4:
            a = im[:, :, 3]
            op = float((a >= 250).mean())
            tr = float((a <= 5).mean())
        else:
            op, tr = 1.0, 0.0
        w(u'  门%s %-26s %dx%d  不透明=%.3f 全透=%.3f 纯黑=%.3f'
          % (l, nm, sw, sh, op, tr, black))

    # ---- D6：屏幕层门的 alpha（第116轮核心判据）----
    w(u'\n## D6 屏幕层门 alpha（A/B 应恒 1.0；C/D 应随距离变虚）')
    for l in 'ABCD':
        vals = []
        for r in rows[:n]:
            try:
                vals.append(float(r.get('d' + l) or ''))
            except (TypeError, ValueError):
                pass
        if not vals:
            w(u'  门%s 无数据（该列缺失或全空）' % l)
            continue
        arr = np.array(vals, dtype=float)
        w(u'  门%s n=%3d  min=%.3f  max=%.3f  mean=%.3f  <0.999 的帧数=%d/%d'
          % (l, len(arr), float(arr.min()), float(arr.max()), float(arr.mean()),
             int((arr < 0.999).sum()), len(arr)))
    w(u'  dN 取值集合 = %s' % sorted(set((r.get('dN') or '') for r in rows[:n])))

    # ---- D7：z 序（谁在谁上面）----
    w(u'\n## D7 z 序（对话框 vs 任务栏）')
    from collections import Counter

    def _col(name):
        return [r.get(name, '') for r in rows[:n]]

    _dz, _tz = _col('dlg_z'), _col('taskbar_z')
    w(u'  dlg_z 取值集合 = %s' % sorted(set(_dz)))
    w(u'  taskbar_z 取值集合 = %s' % sorted(set(_tz)))
    _ab = _col('dlg_above_tb')
    w(u'  dlg_above_tb 计数: 1(对话框在上)=%d  0(任务栏在上)=%d  空=%d'
      % (_ab.count('1'), _ab.count('0'), _ab.count('')))
    _flip = sum(1 for i in range(1, len(_ab))
                if _ab[i] != '' and _ab[i - 1] != '' and _ab[i] != _ab[i - 1])
    w(u'  dlg_above_tb ★翻转次数 = %d（>0 ⇒ 这半截**在闪**）' % _flip)
    for nm in ('above_dlg', 'above_tb'):
        w(u'  %-10s 分布 = %s' % (nm, Counter(_col(nm)).most_common(8)))
    w(u'  dlg_wv 集合=%s  dlg_vis 集合=%s'
      % (sorted(set(_col('dlg_wv'))), sorted(set(_col('dlg_vis')))))

    # ---- 接触表 ----
    make = max(1, n // 12)
    picks = list(range(0, n, make))[:12]
    for l in 'ABCD':
        r = RECT[l]
        tiles = []
        for i in picks:
            t = _crop(frames[i], r, pad=max(40, r[2] // 2), W=W, H=H)
            t = cv2.resize(t, (max(120, t.shape[1] * 2),
                               max(120, t.shape[0] * 2)),
                           interpolation=cv2.INTER_NEAREST)
            _label(t, u'f%d' % i, 4, 18, 0.5)
            tiles.append(t)
        th = max(t.shape[0] for t in tiles)
        tiles = [cv2.copyMakeBorder(t, 0, th - t.shape[0], 0, 0,
                                    cv2.BORDER_CONSTANT, value=(40, 40, 40))
                 for t in tiles]
        sheet = np.hstack(tiles[:6]) if len(tiles) >= 6 else np.hstack(tiles)
        sheet2 = np.hstack(tiles[6:]) if len(tiles) > 6 else None
        if sheet2 is not None and sheet2.shape[0] == sheet.shape[0]:
            sheet = np.vstack([sheet, sheet2])
        _write_png(os.path.join(ANA, 'door_%s.png' % l), sheet)
    w(u'\n接触表已写 %s' % ANA)

    # 对话框整段缩略接触表（8/行）
    if DLG:
        thumb = []
        for i in range(n):
            t = cv2.resize(_crop(frames[i], DLG, W=W, H=H), (320, 132),
                           interpolation=cv2.INTER_AREA)
            _label(t, u'f%d' % i, 4, 16, 0.45)
            thumb.append(t)
        per = 8
        while len(thumb) % per:
            thumb.append(np.zeros_like(thumb[0]))
        rowsimg = [np.hstack(thumb[k:k + per]) for k in range(0, len(thumb), per)]
        _write_png(os.path.join(ANA, 'dlg_strip.png'), np.vstack(rowsimg))
        w(u'对话框接触表 dlg_strip.png（%d 行 x %d 列）' % (len(rowsimg), per))

    # ★ 查盘核实（"写了 N 个文件"必须 os.listdir 对账）
    on_disk = sorted(x for x in os.listdir(ANA) if x.endswith('.png'))
    w(u'\n## 落盘核实：%d 个 PNG ⇒ %s' % (len(on_disk), on_disk))

    txt = rep.getvalue()
    with io.open(os.path.join(ANA, 'report.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    sys.stdout.write(txt.encode('utf-8', 'replace').decode('utf-8', 'replace'))
    return 0


if __name__ == '__main__':
    sys.exit(main())

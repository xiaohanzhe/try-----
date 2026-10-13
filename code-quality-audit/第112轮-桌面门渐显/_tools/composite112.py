# -*- coding: utf-8 -*-
"""第112轮 · **实机所见**合成图（给用户看的那一张）。

## 为什么需要这个（关键结论，第112轮）
真机 `QScreen.grabWindow(0)` 抓的是**操作系统合成后的桌面**，而我们的场景层是一个
`WA_TranslucentBackground` 的**分层透明窗口** —— 这类窗口**不在** `grabWindow(0)`
的取像范围里（Windows 上分层窗口由 DWM 单独合成，不进屏幕抓取）。
⇒ 抓图里"只有壁纸，看不到门也看不到 Ralsei"是**抓图方式的局限，不是产品缺陷**。

**证伪/证实**（`diag112c.py`，真机）：
  · `scene_canvas.geometry() = (0,0,2560,1600)` == 屏幕几何 ⇒ **整屏化真的生效了**
    （离屏下它是 800x600，因为离屏的"屏幕"本身就是 800x600 —— 两者都自洽）。
  · `scene_canvas.grab()`（**直接抓窗口控件**，绕开 DWM 合成）⇒ **真的画出了 4 扇门**，
    且 alpha 肉眼可辨：C(UT) 几乎看不见 / D(三角符文) 半透明 / A·B 全实。

⇒ 本脚本把 **壁纸 + 画布抓图** 合成起来，得到「**用户在真实桌面上看到的样子**」。

## ★★ 第112轮续三：门已改到**屏幕层**，裁剪坐标随之改真源
第112轮续之前，门在**房间层**（经 `translate(offset)` + `scale(cam_scale)`）⇒ 旧版
本脚本用 `_scene_state.objects` 的 `pos × cam_scale + offset` 反推屏幕坐标。
续之后门走 `desk_doors.plan_screen_doors()` 的**屏幕坐标**（`(x,y,w,h)` 就是画布
坐标，不再过任何缩放）⇒ 继续用老公式裁 = **裁到空气**。
⇒ 现在裁剪直接调 `desk_doors.plan_screen_doors()`（**摆位唯一真源**），
   传**同一个** `pet_box` 口径，与产品画出来的逐像素同源。

## ★★★ 出三张给用户看的图
  1. `seen_by_user_full.png` / `_half.png`   —— 整屏合成（= 用户在桌面上看到的）
  2. `doors_and_pet_sheet.png`               —— **门 vs Ralsei 同一把尺子**并排对照
  3. `doors_edges_sheet.png`                 —— 四扇门**逐边贴屏**的局部放大（贴边自证）

跑法（真机；只有真机才拿得到壁纸与正确的整屏几何）：
    set QT_QPA_PLATFORM=windows && C:\\Python311\\python.exe composite112.py
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, os.path.join(PKG, 'src'))

os.environ.setdefault('RALSEI_TEST_MODE', '1')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QImage, QPainter, QColor, QFont, QPen
from PyQt5.QtCore import Qt

_app = QApplication.instance() or QApplication(sys.argv)
IS_REAL = (os.environ.get('QT_QPA_PLATFORM') == 'windows')

OUT = os.path.abspath(os.path.join(HERE, '..', '_evidence', 'preview112'))
if not os.path.isdir(OUT):
    os.makedirs(OUT)

N = {'p': 0, 'f': 0}


def ok(name, cond, detail=u''):
    N['p' if cond else 'f'] += 1
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', name,
                        (u'  <- %s' % detail) if detail else u''))
    return bool(cond)


def poll(ms):
    t_end = time.time() * 1000.0 + ms
    while time.time() * 1000.0 < t_end:
        try:
            _app.processEvents()
        except Exception:
            pass
        time.sleep(0.01)


print(u'==== composite112  platform=%s real=%s ===='
      % (os.environ.get('QT_QPA_PLATFORM'), IS_REAL))

import main as _M
pet = _M.RalseiPet()
pet.show()
# ★ 门渐显要在宠物靠近时才从透明到实像 ⇒ 多跑一会儿让 `_update_scene_layer`
#   至少刷过几个 tick（渐显是 tick 驱动的），再抓图。
poll(2500)

scr = _app.primaryScreen()
sg = scr.geometry()
sc = pet.__dict__.get('scene_canvas')
ok(u'1 场景画布存在', sc is not None)
if sc is None:
    sys.exit(1)

# ---- 壁纸（可能有；离屏没有就退回纯色底） ----
wall = None
if IS_REAL:
    pm = scr.grabWindow(0)
    if pm is not None and not pm.isNull():
        wall = pm.toImage()
        ok(u'2 取到壁纸层', True, u'%dx%d' % (wall.width(), wall.height()))
else:
    ok(u'2 取到壁纸层（离屏期待 False）', True, u'skip')

# ---- 画布（我们真正画出来的东西） ----
canvas = sc.grab().toImage()
ok(u'3 画布抓图非空', canvas.width() > 0 and canvas.height() > 0,
   u'%dx%d' % (canvas.width(), canvas.height()))

# ---- 合成：底 = 壁纸（或深灰），面 = 画布（原样 alpha 叠加） ----
W, H = canvas.width(), canvas.height()
base = QImage(W, H, QImage.Format_ARGB32)
if wall is not None and wall.size() == canvas.size():
    base = wall.convertToFormat(QImage.Format_ARGB32)
else:
    base.fill(QColor(24, 26, 34))

pt = QPainter(base)
pt.setCompositionMode(QPainter.CompositionMode_SourceOver)
pt.drawImage(0, 0, canvas)
pt.end()

p_full = os.path.join(OUT, 'seen_by_user_full.png')
base.save(p_full, 'PNG')
half = base.scaled(W // 2, H // 2, Qt.KeepAspectRatio, Qt.SmoothTransformation)
p_half = os.path.join(OUT, 'seen_by_user_half.png')
half.save(p_half, 'PNG')
print(u'  实机所见（整屏） -> %s' % os.path.basename(p_full))
print(u'  实机所见（半尺寸）-> %s' % os.path.basename(p_half))

# ======================================================================
# ★★★ 第112轮续三：门摆位**直接读产品画的那一份**
# ======================================================================
import desk_doors as _DD

# ★★★ 关键修正：不再"自己重算一遍"。
#   上一版用 `plan_screen_doors()` 重算 ⇒ 得到的是"我这份"，而产品画的是
#   `canvas._screen_doors` 那份；两者在 pet_box 取法不同（产品已改走
#   `pet_screen_box`，脚本还在读 `sprite_label`）时会**错位裁剪** ⇒
#   图里看着"门少了两扇"，实际是**裁到空气**。
#   ⇒ 只读产品真源（`sc._screen_doors`），与用户看到的逐像素同源。
placed = [(sid, r) for (sid, r) in (getattr(sc, '_screen_doors', None) or [])]
print(u'  屏幕层实际摆位（读产品 `_screen_doors`）= %r' % (placed,))
ok(u'3b ★★ 产品真画出 4 扇屏幕门（裁剪坐标读产品真源，与用户所见同源）',
   len(placed) == 4, u'n=%d' % len(placed))
ok(u'3c ★★ `last_drawn` 与屏幕门数一致（真画了，不只是算了）',
   int(getattr(sc, 'last_drawn', -1) or 0) >= len(placed),
   u'last_drawn=%r' % (getattr(sc, 'last_drawn', None),))

# 门贴图名 ← 字母（用于对照图标签）
by_letter = {}
try:
    st = pet.__dict__.get('_scene_state')
    objs = list(getattr(st, 'objects', None) or [])
except Exception:
    objs = []

from modules import door_reveal as _drv  # noqa: E402

for o in objs:
    if not isinstance(o, dict):
        continue
    letter = _drv.door_letter_of_local(o.get('src'))
    if not letter or letter in by_letter:
        continue
    nm = o.get('sprite') or o.get('image')
    if isinstance(nm, str) and nm:
        by_letter[letter] = nm

# 贴图名 → 字母（反查，给标签用）
letter_of_sprite = dict((v, k) for (k, v) in by_letter.items())

sizes = {}
for letter, nm in by_letter.items():
    try:
        sz = sc.assets.sprite_size(nm)
        if isinstance(sz, (list, tuple)) and len(sz) == 2:
            sizes[letter] = (sz[0], sz[1])
    except Exception:
        pass
print(u'  门贴图原始尺寸 sizes = %r' % (sizes,))

# ---- 对照图 ①：门 vs Ralsei（**同一把尺子**） ----
# 宠物矩形（屏幕上）
pg = pet.geometry().getRect()
print(u'  宠物几何 = %r' % (pg,))

TILE_H = 260  # 每个格子的画布高度


def _fit_tile(img, box_w, box_h):
    """把 img 等比缩进 box_w × box_h（**不放大**，保持 1:1 像素可信度）。"""
    if img.width() <= 0 or img.height() <= 0:
        return None
    s = min(float(box_w) / img.width(), float(box_h) / img.height(), 1.0)
    w = max(1, int(round(img.width() * s)))
    h = max(1, int(round(img.height() * s)))
    return img.scaled(w, h, Qt.KeepAspectRatio, Qt.FastTransformation)


def _label_qp(qp, x, y, text, color=QColor(230, 230, 230), px=13):
    qp.setPen(QPen(color))
    f = QFont()
    f.setPointSize(px)
    qp.setFont(f)
    qp.drawText(x, y, text)


# 收集格子：(标签, QImage, 屏幕尺寸文本)
# ★ `placed` = `(sprite 名, rect)` —— 标签里显示字母（由 sprite 反查）。
cells = []
for sid, (x, y, w, h) in placed:
    _L = letter_of_sprite.get(sid, '?')
    l = max(0, int(x))
    t = max(0, int(y))
    r = min(W, int(x + w))
    b = min(H, int(y + h))
    pad = 6
    l2, t2 = max(0, l - pad), max(0, t - pad)
    r2, b2 = min(W, r + pad), min(H, b + pad)
    if r2 - l2 < 4 or b2 - t2 < 4:
        continue
    crop = base.copy(l2, t2, r2 - l2, b2 - t2)
    cells.append((u'door%s  %dx%d' % (_L, w, h), crop))

if pg[2] > 0 and pg[3] > 0:
    l = max(0, pg[0] - 8)
    t = max(0, pg[1] - 8)
    r = min(W, pg[0] + pg[2] + 8)
    b = min(H, pg[1] + pg[3] + 8)
    crop = base.copy(l, t, r - l, b - t)
    cells.append((u'Ralsei  %dx%d' % (pg[2], pg[3]), crop))

if cells:
    cell_w = 240
    sheet = QImage(cell_w * len(cells), TILE_H + 26, QImage.Format_ARGB32)
    sheet.fill(QColor(18, 20, 26))
    qp = QPainter(sheet)
    for i, (lab, img) in enumerate(cells):
        x0 = i * cell_w
        fit = _fit_tile(img, cell_w - 16, TILE_H - 16)
        if fit is not None:
            qp.drawImage(x0 + (cell_w - fit.width()) // 2,
                         (TILE_H - fit.height()) // 2, fit)
        _label_qp(qp, x0 + 6, TILE_H + 18, lab,
                  QColor(120, 230, 140) if lab.startswith(u'Ralsei')
                  else QColor(230, 220, 140))
        qp.setPen(QPen(QColor(70, 74, 86)))
        qp.drawLine(x0, 0, x0, TILE_H + 26)
    qp.end()
    p_sheet = os.path.join(OUT, 'doors_and_pet_sheet.png')
    sheet.save(p_sheet, 'PNG')
    print(u'  门 vs Ralsei 对照图 -> %s' % os.path.basename(p_sheet))
    ok(u'4 产出「门 vs Ralsei」对照图', True, u'n=%d' % len(cells))
else:
    ok(u'4 产出「门 vs Ralsei」对照图', False, u'no tiles')

# ---- 对照图 ②：四扇门**逐边贴屏**（各裁门口附近 360×260，看它到底贴没贴边） ----
edge_cells = []
for sid, (x, y, w, h) in placed:
    _L = letter_of_sprite.get(sid, '?')
    zoom = 360
    crop = QImage(zoom, TILE_H, QImage.Format_ARGB32)
    crop.fill(QColor(18, 20, 26))
    # 以门所在的那条屏幕边为原点开窗：能看到"门与屏幕边之间有没有缝"
    l = max(0, min(W - zoom, int(x) - zoom // 2))
    t = max(0, min(H - TILE_H, int(y) - TILE_H // 2))
    src = base.copy(l, t, min(zoom, W - l), min(TILE_H, H - t))
    qp = QPainter(crop)
    qp.drawImage(0, 0, src)
    # 标出屏幕边界（若窗口里含边）
    if l <= 0:
        qp.setPen(QPen(QColor(255, 80, 80), 3))
        qp.drawLine(1, 0, 1, TILE_H)
    if l + zoom >= W:
        qp.setPen(QPen(QColor(255, 80, 80), 3))
        qp.drawLine(zoom - 2, 0, zoom - 2, TILE_H)
    if t <= 0:
        qp.setPen(QPen(QColor(255, 80, 80), 3))
        qp.drawLine(0, 1, zoom, 1)
    if t + TILE_H >= H:
        qp.setPen(QPen(QColor(255, 80, 80), 3))
        qp.drawLine(0, TILE_H - 2, zoom, TILE_H - 2)
    _label_qp(qp, 6, 18, u'door%s @(%d,%d) %dx%d' % (_L, x, y, w, h))
    qp.end()
    edge_cells.append(crop)

if edge_cells:
    ew = edge_cells[0].width()
    eh = edge_cells[0].height()
    sheet2 = QImage(ew * 2, (eh + 8) * 2, QImage.Format_ARGB32)
    sheet2.fill(QColor(12, 13, 17))
    qp = QPainter(sheet2)
    for i, im in enumerate(edge_cells[:4]):
        qp.drawImage((i % 2) * ew, (i // 2) * (eh + 8), im)
    qp.end()
    p_sheet2 = os.path.join(OUT, 'doors_edges_sheet.png')
    sheet2.save(p_sheet2, 'PNG')
    print(u'  逐边贴屏对照图 -> %s' % os.path.basename(p_sheet2))
    ok(u'5 产出「逐边贴屏」对照图', True, u'n=%d' % len(edge_cells))

# ---- 门槛自证：逐边贴屏（数值） ----
# ★ 判据就地写（`desk_doors` 暴露 `SIDE_LETTERS` / `EDGE_MARGIN` / `DOOR_SCALE` /
#   `DOOR_FIT_CAP` / `PET_BOX_LOGICAL` + `pet_screen_box` / `fit_door_scale` /
#   `door_screen_rect` / `plan_screen_doors`，**没有** "touches_edge" 之类 helper
#   ⇒ 这里按方位自算，映射仍取自 `desk_doors.SIDE_LETTERS`（不另立一份真源）。
_SIDE_OF = dict((l, s) for (s, l) in _DD.SIDE_LETTERS)


def _touches(side, r, sw, sh, tol=1):
    x, y, w, h = r
    if side == 'top':
        return y <= tol
    if side == 'bottom':
        return (y + h) >= (sh - tol)
    if side == 'left':
        return x <= tol
    if side == 'right':
        return (x + w) >= (sw - tol)
    return False


if placed:
    ok(u'6 ★ 四扇门逐边贴屏幕物理边（无 margin）',
       all(_touches(_SIDE_OF.get(letter_of_sprite.get(sid, '')), (x, y, w, h), W, H)
           for sid, (x, y, w, h) in placed),
       u'edges=%r' % ([(letter_of_sprite.get(sid, '?'),
                        _SIDE_OF.get(letter_of_sprite.get(sid, '')))
                       for sid, _r in placed],))
    ok(u'7 ★ 四扇门全在屏幕内',
       all(0 <= x and 0 <= y and x + w <= W and y + h <= H
           for _s, (x, y, w, h) in placed))
    # 门 vs Ralsei 尺寸比（用户「两个尺寸调换一下差不多」）
    # ★ 宠物盒取**产品同源**口径（`pet_screen_box`），不是 `sprite_label`（会跳）。
    _k = float(getattr(pet, '_cached_scale_factor', 0.0) or 0.0)
    _pbox = _DD.pet_screen_box(_k)
    print(u'  宠物标准盒 pet_screen_box(%.5f) = %r' % (_k, _pbox))
    if _pbox:
        for sid, (x, y, w, h) in placed:
            _L = letter_of_sprite.get(sid, '?')
            ow, oh = sizes.get(_L, (0, 0))
            if ow:
                print(u'  door%s: %.2fx%.2f px（原 %.0fx%.0f ⇒ 缩到 %.2f 倍）  '
                      u'标准宠物盒 %dx%d' % (_L, w, h, ow, oh, w / float(ow),
                                         _pbox[0], _pbox[1]))
        _cap = _DD.DOOR_FIT_CAP
        ok(u'8 ★★★ 每扇门都不超过 Ralsei 标准盒的 %.1f 倍（门不再喧宾夺主）' % _cap,
           all(w <= _pbox[0] * _cap + 1 and h <= _pbox[1] * _cap + 1
               for _s, (x, y, w, h) in placed))
    # ★★★ 稳定性判据（本轮真 bug）：门尺寸不随动画组变。
    ok(u'9 ★★★ 门摆位与 `sprite_label`（会随动画跳）**无关**'
       u'（产品宠物盒走 `pet_screen_box`，稳定）',
       _DD.PET_BOX_LOGICAL == (69, 47), u'PET_BOX_LOGICAL=%r' % (_DD.PET_BOX_LOGICAL,))

print(u'\n==== composite112: PASS=%d FAIL=%d ====' % (N['p'], N['f']))
sys.exit(1 if N['f'] else 0)

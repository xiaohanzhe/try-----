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

⇒ 本脚本把 **壁纸 + 画布抓图** 合成起来，得到「**用户在真实桌面上看到的样子**」，
   并按快门速度无关的方式裁剪 4 扇门区域拼成对照表。

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
from PyQt5.QtGui import QImage, QPainter, QColor
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

# ---- 按"屏幕像素"裁 4 扇门 + 宠物，拼成一排对照 ----
# 门的世界坐标 → 屏幕像素：scale=canvas_w/320，另有居中偏移
try:
    from modules import scene_controller as _scm  # noqa
except Exception:
    _scm = None

try:
    st = pet.__dict__.get('_scene_state')
    objs = list(getattr(st, 'objects', None) or [])
except Exception:
    objs = []

# 画面（房间）在屏幕上的矩形。
# ★★ 真源两处（第112轮实测）：
#   · 倍率 = `pet._scene_camera.scale`（**不是** `pet.camera`；后者根本不存在 ⇒ getattr 静默 0.0）
#   · 居中偏移 = `pet._scene_output_offset`（由 `fit_camera_to_screen` 写）
# 画面逻辑尺寸恒 320×240 ⇒ 输出像素 = 320*scale × 240*scale。
cam = pet.__dict__.get('_scene_camera')
cam_scale = float(getattr(cam, 'scale', 0.0) or 0.0)
_pet_scale = float(getattr(pet, 'pet_scale', 1.0) or 1.0)
_cached_scale = float(getattr(pet, '_cached_scale_factor', 0.0) or 0.0)
print(u'  _scene_camera.scale = %r  pet_scale = %r  _cached_scale_factor = %r'
      % (cam_scale, _pet_scale, _cached_scale))

_out_off = pet.__dict__.get('_scene_output_offset') or (None, None)
print(u'  _scene_output_offset = %r' % (_out_off,))
if not cam_scale:
    # 退化：用日志口径 out_w = min(sw, sh*4/3)*0.5 反推（真机 2560x1600 ⇒ 1066/320=3.331）
    import scene_camera as _scm2
    _fr = _scm2.fit_fraction(sg.width(), sg.height(), 4.0 / 3.0,
                             _scm2.SCENE_FIT_FRACTION)
    cam_scale = max(0.0, _fr) * 320.0 / 320.0
    print(u'  [warn] camera.scale 读不到，退化用 fit_fraction 反推 ≈ %.4f' % cam_scale)

out_w = cam_scale * 320.0
out_h = cam_scale * 240.0
off_x = _out_off[0] if _out_off[0] is not None else (W - out_w) / 2.0
off_y = _out_off[1] if _out_off[1] is not None else (H - out_h) / 2.0
print(u'  画面矩形 = x%.0f y%.0f %.0fx%.0f' % (off_x, off_y, out_w, out_h))

tiles = []


def grab_at(cx, cy, hw, hh, label):
    l = max(0, int(cx - hw))
    t = max(0, int(cy - hh))
    r = min(W, int(cx + hw))
    b = min(H, int(cy + hh))
    if r - l < 4 or b - t < 4:
        return None
    crop = base.copy(l, t, r - l, b - t)
    p = os.path.join(OUT, u'crop_%s.png' % label)
    crop.save(p, 'PNG')
    return p


_sp = {}
try:
    _sp = pet.__dict__.get('assets') or getattr(sc, 'assets', None)
except Exception:
    _sp = None


def sprite_hw(name):
    try:
        if _sp is not None and hasattr(_sp, 'sprite_size'):
            s = _sp.sprite_size(name)
            if s:
                return float(s[0]), float(s[1])
    except Exception:
        pass
    return None


for o in objs:
    if not isinstance(o, dict):
        continue
    src = str(o.get('src') or '')
    if not src.startswith('obj_door'):
        continue
    letter = src[len('obj_door'):]
    pos = o.get('pos') or [0, 0]
    spr = o.get('sprite')
    wh = sprite_hw(spr) or (44.0, 56.0)
    cx = off_x + (float(pos[0]) + wh[0] / 2.0) * cam_scale
    cy = off_y + (float(pos[1]) + wh[1] / 2.0) * cam_scale
    hw = wh[0] * cam_scale / 2.0 + 30
    hh = wh[1] * cam_scale / 2.0 + 30
    p = grab_at(cx, cy, hw, hh, u'door%s' % letter)
    tiles.append((u'door%s' % letter, p, o.get('alpha')))
    print(u'  [crop] door%s  alpha=%s  screen=(%.0f,%.0f)  %s'
          % (letter, o.get('alpha'), cx, cy, os.path.basename(p) if p else None))

# 宠物（Ralsei）本体
pg = pet.geometry().getRect()
if pg[2] > 0 and pg[3] > 0:
    pcx = pg[0] + pg[2] / 2.0
    pcy = pg[1] + pg[3] / 2.0
    p = grab_at(pcx, pcy, pg[2] / 2.0 + 40, pg[3] / 2.0 + 40, 'pet')
    tiles.append((u'pet', p, None))
    print(u'  [crop] pet  geom=%r' % (pg,))

# ---- 拼一张门对照图（上面：门区域；下面不拼，简单横向排） ----
good = [t for t in tiles if t[1]]
if good:
    imgs = [QImage(p) for (_l, p, _a) in good]
    rowH = max(i.height() for i in imgs)
    rowW = sum(i.width() for i in imgs) + 8 * (len(imgs) - 1)
    sheet = QImage(rowW, rowH, QImage.Format_ARGB32)
    sheet.fill(QColor(18, 20, 26))
    qp = QPainter(sheet)
    x = 0
    for i in imgs:
        qp.drawImage(x, 0, i)
        x += i.width() + 8
    qp.end()
    p_sheet = os.path.join(OUT, 'doors_and_pet_sheet.png')
    sheet.save(p_sheet, 'PNG')
    print(u'  对照图 -> %s  (%s)' % (os.path.basename(p_sheet),
                                  u' | '.join(t[0] for t in good)))
    ok(u'4 产出对照图', True, u'n=%d' % len(good))
else:
    ok(u'4 产出对照图', False, u'no tiles')

print(u'\n==== composite112: PASS=%d FAIL=%d ====' % (N['p'], N['f']))
sys.exit(1 if N['f'] else 0)

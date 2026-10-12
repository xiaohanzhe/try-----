# -*- coding: utf-8 -*-
"""第112轮诊断 3：**真机**下 `scene_canvas` 的真几何 + 画布内容 + 桌面场景门像素取证。

背景（待定位问题）：
  真机 `rec112` 抓整屏 `grabWindow(0)` 出来的 PNG **只有壁纸**，看不到 4 扇门也看不到
  Ralsei。离屏 `diag112b` 里 `scene_canvas` 是 800x600（不是整屏 2560x1600），
  `_cached_scale_factor=1.25`（真机日志里是 3.33）。两个平台的**全屏化路径不同**。

本支要回答的三件事：
  ① **真机**下 `scene_canvas` 的 `geometry()` / `size()` 到底是整屏还是 800x600？
     （`800x600` = `_place_scene_layer` 没生效 ⇒ **真缺陷**；整屏 ⇒ 抓图方式问题。）
  ② `scene_canvas.grab()` 的画布里**有没有 4 扇门 + Ralsei**？（绕开"是否上屏"）
  ③ 桌面场景的 `plan_frame` 计划里，4 扇门的 `alpha` / `rect` 各是多少？

跑法：
    # 真机
    set QT_QPA_PLATFORM=windows  && C:\\Python311\\python.exe diag112c.py
    # 离屏（对照）
    set QT_QPA_PLATFORM=offscreen && C:\\Python311\\python.exe diag112c.py
"""
import json
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
from PyQt5.QtGui import QImage, QColor, QPainter

_app = QApplication.instance() or QApplication(sys.argv)
IS_REAL = (os.environ.get('QT_QPA_PLATFORM') == 'windows')

OUT = os.path.abspath(os.path.join(HERE, '..', '_evidence', 'canvas112'))
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


def dump(tag, img):
    """把 QImage 存原图 + 洋红底图（便于肉眼看透明区），并返回非透明像素统计。"""
    p = os.path.join(OUT, u'%s_raw.png' % tag)
    img.save(p, 'PNG')
    nz = 0
    tot = 0
    for y in range(0, img.height(), 3):
        for x in range(0, img.width(), 3):
            tot += 1
            if ((img.pixel(x, y) >> 24) & 0xFF) > 8:
                nz += 1
    bg = QImage(img.size(), QImage.Format_ARGB32)
    bg.fill(QColor(255, 0, 255))
    pt = QPainter(bg)
    pt.drawImage(0, 0, img)
    pt.end()
    bg.save(os.path.join(OUT, u'%s_magenta.png' % tag), 'PNG')
    return nz, tot


print(u'==== diag112c  platform=%s real=%s ===='
      % (os.environ.get('QT_QPA_PLATFORM'), IS_REAL))

import main as _M
pet = _M.RalseiPet()
pet.show()
poll(2500)

# ---------- ① screen / canvas 几何 ----------
print(u'\n-- ① 几何 --')
scr = _app.primaryScreen()
sg = scr.geometry()
print(u'  screen.geometry()      = %r' % (sg.getRect(),))
try:
    print(u'  screen.availableGeometry = %r' % (scr.availableGeometry().getRect(),))
except Exception as e:
    print(u'  availableGeometry err: %s' % e)

sc = pet.__dict__.get('scene_canvas')
ok(u'1 scene_canvas 存在', sc is not None,
   u'%r' % (type(sc).__name__ if sc else None))
if sc is not None:
    g = sc.geometry().getRect()
    s = (sc.size().width(), sc.size().height())
    print(u'  scene_canvas.geometry  = %r' % (g,))
    print(u'  scene_canvas.size      = %rx%r' % s)
    print(u'  scene_canvas.pos       = (%r, %r)' % (sc.pos().x(), sc.pos().y()))
    print(u'  scene_canvas.isVisible = %r' % sc.isVisible())
    print(u'  scene_canvas.windowFlags= %r' % hex(int(sc.windowFlags())))
    print(u'  _scene_layer_visible   = %r' % pet.__dict__.get('_scene_layer_visible'))
    print(u'  _cached_scale_factor   = %r' % pet.__dict__.get('_cached_scale_factor'))
    print(u'  pet.geometry()         = %r' % (pet.geometry().getRect(),))
    ok(u'2 ★ 画布几何 == 屏幕几何（整屏化生效）',
       (sc.size().width(), sc.size().height()) == (sg.width(), sg.height()),
       u'canvas=%rx%r screen=%rx%r' % (s[0], s[1], sg.width(), sg.height()))

# ---------- ② 画布自抓图 ----------
print(u'\n-- ② 画布内容（canvas.grab()） --')
if sc is not None:
    pm = sc.grab()
    img_Canvas = pm.toImage()
    nz, tot = dump('diagc_canvas', img_Canvas)
    print(u'  canvas.grab() = %dx%d  非透明 %.2f%% (%d/%d)'
          % (img_Canvas.width(), img_Canvas.height(), 100.0 * nz / max(1, tot), nz, tot))
    ok(u'3 画布抓图有内容', nz > 100, u'nz=%d/%d' % (nz, tot))

# ---------- ③ 桌面场景 plan 里的门 ----------
print(u'\n-- ③ 桌面场景 objects 里的门 --')
try:
    st = pet.__dict__.get('_scene_state')
    objs = list(getattr(st, 'objects', None) or [])
    print(u'  _scene_state = %r  objects=%d  scene_id=%r'
          % (type(st).__name__ if st else None, len(objs),
             getattr(st, 'scene_id', None)))
    doors = []
    for o in objs:
        if not isinstance(o, dict):
            continue
        src = str(o.get('src') or '')
        if src.startswith('obj_door'):
            doors.append({'letter': src[len('obj_door'):],
                          'sprite': o.get('sprite'),
                          'alpha': o.get('alpha'),
                          'pos': o.get('pos')})
    print(u'  doors = %s' % json.dumps(doors, ensure_ascii=False, indent=1))
    ok(u'4 桌面 objects 里 4 扇门', len(doors) == 4, u'n=%d' % len(doors))
except Exception as e:
    ok(u'4 读 objects 异常 %s' % e, False)

# ---------- ④ 整屏抓图（对照"是否上屏"） ----------
print(u'\n-- ④ 整屏抓图对照 --')
if IS_REAL:
    pm2 = scr.grabWindow(0)
    if pm2 is not None and not pm2.isNull():
        i2 = pm2.toImage()
        nz2, tot2 = dump('diagc_full', i2)
        print(u'  grabWindow(0) = %dx%d  非透明 %.2f%%'
              % (i2.width(), i2.height(), 100.0 * nz2 / max(1, tot2)))
        ok(u'5 整屏抓图非空', nz2 > 100, u'nz=%d' % nz2)
else:
    print(u'  （离屏：跳过整屏抓图）')

# ---------- ⑤ 桌面场景是否真的"在场景层里" ----------
print(u'\n-- ⑤ 桌面场景状态 --')
try:
    print(u'  _soul_scene_id      = %r' % pet.__dict__.get('_soul_scene_id'))
    print(u'  _desktop_scene_mode = %r' % pet.__dict__.get('_desktop_scene_mode'))
    fn = pet.__dict__.get('_scene_is_desktop_scene')
    if callable(fn):
        print(u'  _scene_is_desktop_scene() = %r' % bool(fn()))
    cam = pet.__dict__.get('camera')
    if cam is not None:
        print(u'  camera.scale = %r' % getattr(cam, 'scale', None))
        print(u'  camera.x/y   = %r / %r'
              % (getattr(cam, 'x', None), getattr(cam, 'y', None)))
except Exception as e:
    print(u'  err: %s' % e)

print(u'\n==== diag112c: PASS=%d FAIL=%d ====' % (N['p'], N['f']))
sys.exit(1 if N['f'] else 0)

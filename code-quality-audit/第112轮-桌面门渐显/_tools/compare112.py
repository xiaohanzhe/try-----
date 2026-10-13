# -*- coding: utf-8 -*-
"""第112轮续三 · **门 vs Ralsei 尺寸对照图**（给用户看的那一张，1:1 像素）。

## 为什么单独做一张
`doors_and_pet_sheet.png` 是"从实机合成图里裁格子"，格子会被缩到 240 宽 ⇒
**看不出真实尺寸差**。用户这次的要求核心就是**尺寸关系**（「两个尺寸调换一下
差不多」+「门的稍微大一点」）⇒ 必须 1:1、同一把尺子并排。

做法：
  1. 起真机 App（拿正确的 `_cached_scale_factor` 与整屏几何），拿到
     `canvas._screen_doors`（产品**真实**摆位，唯一真源）；
  2. 从**画布抓图**（`canvas.grab()`，绕开 DWM 分层合成）里按 rect **1:1** 裁出
     四扇门；
  3. 从**宠物截图**里 1:1 裁出 Ralsei；
  4. 底下画一条**像素标尺**（每 50px 一格）⇒ 肉眼直接读尺寸。
  ⇒ 顺带把每扇门的 `(w,h)` / 原尺寸 / 缩放倍率 / 占宠物盒比例**画在标签上**。

跑法：
    set QT_QPA_PLATFORM=windows && C:\\Python311\\python.exe compare112.py
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

_app = QApplication.instance() or QApplication(sys.argv)

OUT = os.path.abspath(os.path.join(HERE, '..', '_evidence', 'preview112'))
if not os.path.isdir(OUT):
    os.makedirs(OUT)


def poll(ms):
    t_end = time.time() * 1000.0 + ms
    while time.time() * 1000.0 < t_end:
        try:
            _app.processEvents()
        except Exception:
            pass
        time.sleep(0.01)


print(u'==== compare112 ====')

import main as _M
import desk_doors as _DD

pet = _M.RalseiPet()
pet.show()
poll(2500)

scr = _app.primaryScreen()
sg = scr.geometry()
sc = pet.__dict__.get('scene_canvas')
canvas_img = sc.grab().toImage()

# 门 ↔ 字母（从 desktop.json 的 objects 反查）
from modules import door_reveal as _drv  # noqa: E402
by_letter = {}
try:
    st = pet.__dict__.get('_scene_state')
    for _o in (getattr(st, 'objects', None) or []):
        if not isinstance(_o, dict):
            continue
        _L = _drv.door_letter_of_local(_o.get('src'))
        if _L and _L not in by_letter:
            _nm = _o.get('sprite') or _o.get('image')
            if isinstance(_nm, str) and _nm:
                by_letter[_L] = _nm
except Exception:
    pass
letter_of_sprite = dict((v, k) for (k, v) in by_letter.items())

placed = list(getattr(sc, '_screen_doors', None) or [])
_k = float(getattr(pet, '_cached_scale_factor', 0.0) or 0.0)
pbox = _DD.pet_screen_box(_k)
print(u'  _cached_scale_factor = %r  ⇒ 标准宠物盒 = %r' % (_k, pbox))
print(u'  屏幕门 = %r' % (placed,))

# ---- 宠物 1:1 截图 ----
pg = pet.geometry().getRect()
pet_img = None
if pg[2] > 0 and pg[3] > 0:
    pet_img = sc.parentWidget().grab() if False else None
# ★ 宠物由 `sprite_label` 画（同级兄弟控件）⇒ 直接抓主窗口对应区域
try:
    win_img = pet.grab().toImage()
    # 主窗口坐标 → 主窗口内 sprite_label 的矩形
    _sl = pet.sprite_label
    _sl_rect = _sl.geometry().getRect()
    if _sl_rect[2] > 2 and _sl_rect[3] > 2:
        pet_img = win_img.copy(_sl_rect[0], _sl_rect[1], _sl_rect[2], _sl_rect[3])
except Exception as _e:
    print(u'  [warn] 抓宠物失败: %s' % _e)

# ---- 拼图：每格 1:1（不缩放），高度取最大者 + 标尺 + 标签 ----
PAD = 18
LABEL_H = 58
RULER_H = 34


def _cell_size(img, rect):
    w = max(img.width() if img else 0, rect[2] if rect else 0)
    h = max(img.height() if img else 0, rect[3] if rect else 0)
    return w, h


cells = []   # (title, sub, QImage)
for sid, (x, y, w, h) in placed:
    _L = letter_of_sprite.get(sid, '?')
    _src = by_letter.get(_L, '')
    crop = None
    l, t = max(0, int(x)), max(0, int(y))
    r, b = min(canvas_img.width(), int(x + w)), min(canvas_img.height(), int(y + h))
    if r - l > 2 and b - t > 2:
        crop = canvas_img.copy(l, t, r - l, b - t)
    # 原尺寸（从素材尺寸表反推：w / scale ⇒ 但我们没有 scale；用 assets 查）
    _ow, _oh = 0, 0
    try:
        _sz = sc.assets.sprite_size(_src)
        if _sz:
            _ow, _oh = int(_sz[0]), int(_sz[1])
    except Exception:
        pass
    _ratio = (u'原 %dx%d · 缩 %.2f×' % (_ow, _oh, (w / float(_ow)) if _ow else 0)
              if _ow else u'')
    _vs = (u'占宠物宽 %.0f%% · 高 %.0f%%'
           % (100.0 * w / pbox[0], 100.0 * h / pbox[1]) if pbox else u'')
    cells.append((u'door%s  %dx%d' % (_L, w, h), _ratio + u'\n' + _vs, crop))
if pet_img is not None:
    cells.append((u'Ralsei  %dx%d' % (pet_img.width(), pet_img.height()),
                  u'标准宠物盒 %dx%d' % (pbox if pbox else (0, 0)), pet_img))

if cells:
    cw = max(PAD * 2 + c[2].width() if c[2] is not None else 80 for c in cells)
    ch = max(c[2].height() if c[2] is not None else 0 for c in cells)
    W = cw * len(cells)
    H = ch + LABEL_H + RULER_H
    sheet = QImage(W, H, QImage.Format_ARGB32)
    sheet.fill(QColor(20, 22, 28))
    qp = QPainter(sheet)
    for i, (title, sub, img) in enumerate(cells):
        x0 = i * cw
        # 内容（1:1，水平居中，贴底）
        if img is not None:
            qp.drawImage(x0 + (cw - img.width()) // 2, ch - img.height(), img)
        # 标尺（每 50px 一格；与 1:1 内容同一原点）
        _rx = x0 + (cw - (img.width() if img is not None else cw)) // 2
        qp.setPen(QPen(QColor(150, 156, 170)))
        _f = QFont()
        _f.setPointSize(8)
        qp.setFont(_f)
        for _px in range(0, (img.width() if img is not None else cw) + 1, 50):
            qp.drawLine(_rx + _px, ch, _rx + _px, ch + 6)
            qp.setPen(QPen(QColor(120, 126, 140)))
            qp.drawText(_rx + _px + 2, ch + 16, u'%d' % _px)
            qp.setPen(QPen(QColor(150, 156, 170)))
        # 标签
        qp.setPen(QPen(QColor(230, 230, 230)))
        _fb = QFont()
        _fb.setPointSize(11)
        _fb.setBold(True)
        qp.setFont(_fb)
        qp.drawText(x0 + 8, ch + RULER_H + 20, title)
        _f2 = QFont()
        _f2.setPointSize(9)
        qp.setFont(_f2)
        qp.setPen(QPen(QColor(170, 176, 190)))
        qp.drawText(x0 + 8, ch + RULER_H + 38, sub.replace(u'\n', u'  '))
        qp.setPen(QPen(QColor(70, 74, 86)))
        qp.drawLine(x0, 0, x0, H)
    qp.end()
    p = os.path.join(OUT, 'doors_vs_ralsei_1to1.png')
    sheet.save(p, 'PNG')
    print(u'  1:1 对照图 -> %s  (%dx%d)' % (os.path.basename(p), W, H))
else:
    print(u'  [warn] 没有可拼的格子')

print(u'==== compare112 完成 ====')

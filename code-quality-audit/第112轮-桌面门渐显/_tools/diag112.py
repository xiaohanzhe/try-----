# -*- coding: utf-8 -*-
"""第112轮：诊断"真机抓帧里看不到门也看不到宠物"。

做法：把整屏按 4 个象限缩小拼一张，肉眼看有没有任何**非壁纸**内容；
再对 `_scene_layer` 的可见性/几何做内省断言。
"""
import io
import os
import sys
import json
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, os.path.join(PKG, 'src'))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('RALSEI_TEST_MODE', '1')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QImage
from PyQt5.QtCore import Qt

_app = QApplication.instance() or QApplication(sys.argv)

# ---- 1) 全屏图里有没有"非壁纸"的显著色块？----
FR = os.path.join(HERE, '..', '_evidence', 'frames112', 'k000_boot.png')
img = QImage(FR)
print('frame=%dx%d' % (img.width(), img.height()))

# 采样每条边中点 ± 200px 的条带，找"不同于周围壁纸"的像素
import collections
cnt = collections.Counter()
step = 4
for y in range(0, img.height(), step):
    for x in range(0, img.width(), step):
        c = img.pixel(x, y)
        # 量化到 16 级，找是否有纯色块（UI 常是纯色/近纯色）
        r = (c >> 16) & 0xFF
        g = (c >> 8) & 0xFF
        b = c & 0xFF
        cnt[(r // 32, g // 32, b // 32)] += 1
print('top 色桶（量化 32 级）:')
for k, v in cnt.most_common(6):
    print('   bucket=%s  n=%d  (%.1f%%)' % (k, v, 100.0 * v / (img.width() * img.height() / (step * step))))
# 黑色占比（全屏化会画黑边 + 门上黑框）
blk = sum(v for k, v in cnt.items() if k == (0, 0, 0))
print('近黑像素占比 = %.2f%%' % (100.0 * blk / (img.width() * img.height() / (step * step))))

# ---- 2) 内省：场景层可见性 / 几何 ----
print('\n-- 内省 scene layer --')
try:
    import main as _M
    pet = _M.RalseiPet()
    pet.show()
    t_end = time.time() * 1000 + 1500
    while time.time() * 1000 < t_end:
        _app.processEvents()
        time.sleep(0.01)

    sl = pet.__dict__.get('scene_layer')
    print('scene_layer 对象 = %r' % (type(sl).__name__ if sl else None))
    if sl is not None:
        print('  isVisible = %r' % sl.isVisible())
        print('  geometry  = %r' % (sl.geometry().getRect(),))
        print('  size      = %r' % (sl.size().width(), sl.size().height()))
        try:
            c = sl.__dict__.get('canvas') or getattr(sl, 'canvas', None)
            print('  canvas    = %r' % (type(c).__name__ if c else None))
            if c is not None:
                print('    canvas.isVisible = %r' % c.isVisible())
                print('    canvas.geometry  = %r' % (c.geometry().getRect(),))
                pl = c.__dict__.get('_plan')
                print('    _plan 条数 = %r' % (len(pl) if pl else None))
        except Exception as e:
            print('    canvas 内省异常 %s' % e)
    # 宠物窗口
    print('  pet.isVisible = %r  geom=%r' % (pet.isVisible(), pet.geometry().getRect()))
    # 场景状态
    st = pet.__dict__.get('_scene_state')
    print('  _scene_state.scene_id = %r' % getattr(st, 'scene_id', None))
    objs = getattr(st, 'objects', None) or []
    print('  objects n=%d  门=%d' % (len(objs),
          sum(1 for o in objs if isinstance(o, dict)
              and str(o.get('src') or '').startswith('obj_door'))))
    # 画布可见性判定函数
    try:
        print('  _scene_is_transparent() = %r' % pet._scene_is_transparent())
    except Exception as e:
        print('  _scene_is_transparent 异常 %s' % e)
except Exception as e:
    import traceback
    traceback.print_exc()

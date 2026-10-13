# -*- coding: utf-8 -*-
"""第112轮续三 · 诊断：门到底有没有被画出来（屏幕层）。"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, os.path.join(PKG, 'src'))
os.environ.setdefault('RALSEI_TEST_MODE', '1')
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QImage, QColor
_app = QApplication.instance() or QApplication(sys.argv)

def poll(ms):
    t = time.time()*1000.0 + ms
    while time.time()*1000.0 < t:
        try: _app.processEvents()
        except Exception: pass
        time.sleep(0.01)

import main as _M
pet = _M.RalseiPet(); pet.show(); poll(2500)
sc = pet.__dict__.get('scene_canvas')
print('canvas=', sc)
print('canvas_visible=', sc.isVisible() if sc else None)
print('canvas.geometry=', sc.geometry().getRect() if sc else None)
print('_screen_doors=', getattr(sc, '_screen_doors', None))
print('has_screen_doors=', getattr(sc, 'has_screen_doors', None))
print('last_drawn=', getattr(sc, 'last_drawn', None))
print('_plan len=', len(getattr(sc, '_plan', None) or []))
print('_opaque_bg=', getattr(sc, '_opaque_bg', None))
print('_offset=', getattr(sc,'_offset_x',None), getattr(sc,'_offset_y',None))
print('_scale=', getattr(sc,'_scale_x',None), getattr(sc,'_scale_y',None))
print('is_desktop=', pet._scene_is_desktop_scene())
print('current_scene=', pet.__dict__.get('current_scene'))
# 直接试抓
img = sc.grab().toImage()
img.save(os.path.join(HERE,'..','_evidence','preview112','diag_direct_grab.png'),'PNG')
# 统计非透明像素
cnt=0; tot=0
for y in range(0, img.height(), 20):
    for x in range(0, img.width(), 20):
        tot+=1
        c=img.pixelColor(x,y)
        if c.alpha()>8: cnt+=1
print('direct grab: %dx%d  nontransparent(sample)=%d/%d' % (img.width(), img.height(), cnt, tot))

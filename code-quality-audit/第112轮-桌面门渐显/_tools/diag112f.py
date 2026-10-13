# -*- coding: utf-8 -*-
"""诊断：sprite_label 尺寸稳定性 + last_drawn 随时间变化。"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, os.path.join(PKG, 'src'))
os.environ.setdefault('RALSEI_TEST_MODE', '1')
from PyQt5.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)
def poll(ms):
    t=time.time()*1000.0+ms
    while time.time()*1000.0<t:
        try: _app.processEvents()
        except Exception: pass
        time.sleep(0.01)
import main as _M
pet=_M.RalseiPet(); pet.show()
sc=pet.__dict__.get('scene_canvas')
for i in range(12):
    poll(400)
    sl=pet.sprite_label
    print('t=%4dms  sprite_label=%dx%d  pet_scale=%r  cached=%r  last_drawn=%s  nscreen=%d  plan=%d  SD0raw=%r'
          % ((i+1)*400, sl.width(), sl.height(), getattr(pet,'pet_scale',None),
             getattr(pet,'_cached_scale_factor',None),
             getattr(sc,'last_drawn',None), len(getattr(sc,'_screen_doors',[])),
             len(getattr(sc,'_plan',[]) or []),
             (getattr(sc,'_screen_doors',None) or [None])[0]))

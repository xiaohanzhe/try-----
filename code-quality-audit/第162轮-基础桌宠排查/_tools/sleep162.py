# -*- coding: utf-8 -*-
"""第162轮 · 就寝/待机窝点落到哪（任务栏上沿还是屏幕底）。"""
import os, sys, time
SANDBOX = r"D:/_tmp/pet162"
os.environ['RALSEI_DATA_DIR'] = r'D:/_tmp/pet162_data'
os.environ.pop('QT_QPA_PLATFORM', None)
sys.path.insert(0, os.path.join(SANDBOX, 'modules'))
sys.path.insert(0, os.path.join(SANDBOX, 'src'))
try:
    import memory_store as _ms
    _ms.find_device_dir = lambda create=True: None
except Exception:
    pass
try:
    import data_store as _ds
    _ds.vault_root = lambda create=True: None
except Exception:
    pass
from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)
from main import RalseiPet
w = RalseiPet(); w.show()
def pump(ms):
    end = time.time() + ms/1000.0
    while time.time() < end:
        app.processEvents(); time.sleep(0.005)
pump(2500)
wa = app.primaryScreen().availableGeometry(); wb = wa.y()+wa.height()
print('[BASE] work_bottom=%d  taskbar_top_y=%d  floor_y=%d  ground_y=%d'
      % (wb, w._taskbar_top_y(), w._desktop_floor_y(), w._desktop_ground_y()), flush=True)
print('[PERCH] %s' % (w._lounge_perch_point(),), flush=True)
try:
    r = w.go_to_bed()
    pump(2500)
    g = w.frameGeometry()
    print('[BED] ret=%s pos=(%d,%d) %dx%d bottom=%d 越界=%s anim=%s sleeping=%s'
          % (r, g.x(), g.y(), g.width(), g.height(), g.y()+g.height(),
             g.y()+g.height() > wb, getattr(w,'current_animation',''),
             getattr(w,'is_sleeping',None)), flush=True)
except Exception as e:
    print('[BED] 异常 %r' % (e,), flush=True)
try:
    w.wake_up(); pump(1500)
    g = w.frameGeometry()
    print('[WAKE] bottom=%d 越界=%s anim=%s' % (g.y()+g.height(), g.y()+g.height()>wb,
          getattr(w,'current_animation','')), flush=True)
except Exception as e:
    print('[WAKE] 异常 %r' % (e,), flush=True)
try:
    w.cleanup_on_exit()
except Exception:
    pass
app.quit()
print('[DONE]', flush=True)

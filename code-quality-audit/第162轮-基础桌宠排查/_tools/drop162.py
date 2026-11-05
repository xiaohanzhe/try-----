# -*- coding: utf-8 -*-
"""第162轮 · 确定性落地：把宠物抬到高处、按"甩飞"路径掉下来，看落在哪条线。

这是本轮 ② 的**正控制**：改前应落在 1600（整屏底），改后落在 1528（任务栏上沿）。
"""
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
_gy = getattr(w, '_desktop_ground_y', None)
print('[BASE] work_bottom=%d floor_y=%d ground_y=%s h=%d' %
      (wb, w._desktop_floor_y(), (_gy() if _gy else 'N/A'), w.height()), flush=True)
w.move(1200, 200)
pump(200)
try:
    w.start_falling(fall_velocity=1200, is_thrown=True, reason='probe162')
except Exception as e:
    print('[ERR] start_falling %r' % (e,), flush=True)
for i in range(8):
    pump(500)
    g = w.frameGeometry()
    print('[T] +%.1fs y=%d h=%d bottom=%d 越界=%s anim=%s' %
          ((i+1)*0.5, g.y(), g.height(), g.y()+g.height(), g.y()+g.height() > wb,
           getattr(w,'current_animation','')), flush=True)
try:
    w.cleanup_on_exit()
except Exception:
    pass
app.quit()
print('[DONE]', flush=True)

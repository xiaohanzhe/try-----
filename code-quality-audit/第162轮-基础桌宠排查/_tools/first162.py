# -*- coding: utf-8 -*-
"""首帧落点：启动后头 12 秒逐 200ms 记录位置，看它是不是先站在整屏底（被任务栏压）。"""
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
wa = app.primaryScreen().availableGeometry()
wb = wa.y() + wa.height()
sh = app.primaryScreen().geometry().height()
print('[BASE] work_bottom=%d screen_h=%d' % (wb, sh), flush=True)
w = RalseiPet()
print('[PRE-SHOW] pos=%s size=%dx%d' % (w.pos(), w.width(), w.height()), flush=True)
w.show()
t0 = time.time()
last = None
while time.time() - t0 < 12.0:
    app.processEvents()
    g = w.frameGeometry()
    key = (g.x(), g.y(), g.width(), g.height())
    if key != last:
        print('[MOVE] t=%4.1f pos=(%d,%d) %dx%d bottom=%d%s nom=%s' % (
            time.time() - t0, g.x(), g.y(), g.width(), g.height(),
            g.y() + g.height(),
            '  <<被任务栏压' if g.y() + g.height() > wb else '',
            getattr(w, 'current_animation', '')), flush=True)
        last = key
    time.sleep(0.05)
try:
    w.cleanup_on_exit()
except Exception:
    pass
app.quit()
print('[DONE]', flush=True)

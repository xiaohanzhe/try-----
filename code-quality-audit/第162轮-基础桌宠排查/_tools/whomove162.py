# -*- coding: utf-8 -*-
"""第162轮 · 谁把宠物放到任务栏后面：给 `move()` 挂钩抓调用栈。

只记录"窗口底边越过工作区底"的那次调用，打印 3 层栈帧 + 当时状态。
"""
import os
import sys
import time
import traceback

SANDBOX = r"D:\_tmp\pet162"
os.environ['RALSEI_DATA_DIR'] = r'D:\_tmp\pet162_data'
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

w = RalseiPet()
pump_end = time.time() + 2
while time.time() < pump_end:
    app.processEvents()
    time.sleep(0.01)

wa = app.primaryScreen().availableGeometry()
wb = wa.y() + wa.height()
print('[BASE] work_bottom=%d' % wb, flush=True)

_orig_move = w.move
SEEN = {}


def _move(x, y=None):
    if y is None:
        pos = x
        nx, ny = pos.x(), pos.y()
    else:
        nx, ny = int(x), int(y)
    bottom = ny + w.height()
    if bottom > wb:
        st = traceback.extract_stack()[:-1]
        frames = ['%s:%d %s' % (os.path.basename(f.filename), f.lineno, f.name)
                  for f in st[-4:]]
        key = ' | '.join(frames)
        if key not in SEEN:
            SEEN[key] = 0
            print('[OVER] bottom=%d y=%d h=%d anim=%s floor=%s'
                  % (bottom, ny, w.height(), getattr(w, 'current_animation', ''),
                     (getattr(w, 'current_floor', None) or {}).get('type')), flush=True)
            for f in frames:
                print('     <- %s' % f, flush=True)
        SEEN[key] += 1
    return _orig_move(x) if y is None else _orig_move(nx, ny)


w.move = _move

t0 = time.time()
while time.time() - t0 < 150:
    app.processEvents()
    time.sleep(0.01)

print('[SUM] 越界调用点 %d 种' % len(SEEN), flush=True)
for k, v in sorted(SEEN.items(), key=lambda kv: -kv[1])[:6]:
    print('  x%-5d %s' % (v, k), flush=True)

try:
    w.cleanup_on_exit()
except Exception:
    pass
app.quit()
print('[DONE]', flush=True)

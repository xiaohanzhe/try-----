# -*- coding: utf-8 -*-
"""第162轮 · 60 秒位置采样：宠物底边有多少时间落在任务栏那条下面。

判据（先写死，避免"看着像"）：
  · 工作区底边 = availableGeometry().bottom()+1（本例 1528）
  · `overlap` = 窗口底边 > 工作区底边  ⇒ 那几帧脚被任务栏压住
  · `at_screen_bottom` = 窗口底边 >= 屏高-2 ⇒ 明确贴着**整屏**底边（老地面）
只统计、不下结论；另外记录窗口尺寸（看它是不是随帧变）。
"""
import os
import sys
import time
import json

SANDBOX = r"D:\_tmp\pet162"
os.environ['RALSEI_DATA_DIR'] = r"D:\_tmp\pet162_data"
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
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)
from main import RalseiPet

w = RalseiPet()
w.show()

wa = app.primaryScreen().availableGeometry()
work_bottom = wa.y() + wa.height()
scr_h = app.primaryScreen().geometry().height()
print('[BASE] work_bottom=%d screen_h=%d' % (work_bottom, scr_h), flush=True)

SAMPLES = []
DUR = 60.0
t0 = time.time()
while time.time() - t0 < DUR:
    app.processEvents()
    g = w.frameGeometry()
    SAMPLES.append({
        't': round(time.time() - t0, 1),
        'y': g.y(), 'h': g.height(), 'bottom': g.y() + g.height(),
        'w': g.width(),
        'anim': getattr(w, 'current_animation', ''),
    })
    time.sleep(0.2)

n = len(SAMPLES)
over = [s for s in SAMPLES if s['bottom'] > work_bottom]
atbed = [s for s in SAMPLES if s['bottom'] >= scr_h - 2]
sizes = {}
for s in SAMPLES:
    k = '%dx%d' % (s['w'], s['h'])
    sizes[k] = sizes.get(k, 0) + 1

print('[STAT] 采样 %d 帧 / %.0f 秒' % (n, DUR), flush=True)
print('[STAT] 底边越过工作区（被任务栏压）%d 帧 = %.1f%%' % (len(over), 100.0 * len(over) / n), flush=True)
print('[STAT] 底边贴整屏底(>=%d) %d 帧 = %.1f%%' % (scr_h - 2, len(atbed), 100.0 * len(atbed) / n), flush=True)
print('[STAT] 窗口尺寸种数 = %d' % len(sizes), flush=True)
for k, v in sorted(sizes.items(), key=lambda kv: -kv[1])[:6]:
    print('[SIZE] %-10s %d 帧' % (k, v), flush=True)
print('[STAT] y 范围 %d..%d' % (min(s['y'] for s in SAMPLES), max(s['y'] for s in SAMPLES)), flush=True)
print('[STAT] 动画集合 %s' % sorted(set(s['anim'] for s in SAMPLES)), flush=True)

with open(r'D:\_tmp\pet162_samples.json', 'w', encoding='utf-8') as f:
    json.dump(SAMPLES, f, ensure_ascii=False)

try:
    w.cleanup_on_exit()
except Exception:
    pass
app.quit()
print('[DONE]', flush=True)

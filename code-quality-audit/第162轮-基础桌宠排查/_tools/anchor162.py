# -*- coding: utf-8 -*-
"""第162轮 · 换动画时"锚点"在哪：中心还是脚底？

产品的 `update_animation` 在尺寸变化时**保窗口中心**（第94轮注释写明：
"角色中心 = 窗口中心"）。角色站在"地面"上时，正确的不变量应该是**脚底**不动。
本支量：每次尺寸变化的 Δ(中心) 与 Δ(脚底)，看哪个是 0。
"""
import os
import sys
import time

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
w.show()

wa = app.primaryScreen().availableGeometry()
work_bottom = wa.y() + wa.height()

recs = []
t0 = time.time()
while time.time() - t0 < 30.0:
    app.processEvents()
    g = w.frameGeometry()
    recs.append((round(time.time() - t0, 2), g.x(), g.y(), g.width(), g.height(),
                 getattr(w, 'current_animation', '')))
    time.sleep(0.03)

print('[BASE] work_bottom=%d  采样 %d' % (work_bottom, len(recs)), flush=True)

changes = []
for i in range(1, len(recs)):
    t, x, y, ww, hh, a = recs[i]
    _, px, py, pw, ph, pa = recs[i - 1]
    if (ww, hh) == (pw, ph):
        continue
    old_feet = (px + pw / 2.0, py + ph)
    new_feet = (x + ww / 2.0, y + hh)
    old_c = (px + pw / 2.0, py + ph / 2.0)
    new_c = (x + ww / 2.0, y + hh / 2.0)
    changes.append({
        't': t, 'from': '%dx%d' % (pw, ph), 'to': '%dx%d' % (ww, hh),
        'anim': '%s->%s' % (pa, a),
        'd_feet_x': round(new_feet[0] - old_feet[0], 1),
        'd_feet_y': round(new_feet[1] - old_feet[1], 1),
        'd_center_x': round(new_c[0] - old_c[0], 1),
        'd_center_y': round(new_c[1] - old_c[1], 1),
        'dh': hh - ph,
        'bottom': y + hh,
    })

print('[STAT] 尺寸变化 %d 次' % len(changes), flush=True)
print('%-6s %-12s %-12s %-22s %7s %7s %7s %7s %7s' % (
    't', 'from', 'to', 'anim', 'dFeetX', 'dFeetY', 'dCtrX', 'dCtrY', 'bottom'), flush=True)
for c in changes[:22]:
    print('%-6.2f %-12s %-12s %-22s %7.1f %7.1f %7.1f %7.1f %7d' % (
        c['t'], c['from'], c['to'], c['anim'], c['d_feet_x'], c['d_feet_y'],
        c['d_center_x'], c['d_center_y'], c['bottom']), flush=True)

import statistics
if changes:
    fy = [abs(c['d_feet_y']) for c in changes]
    cy = [abs(c['d_center_y']) for c in changes]
    print('[SUM] |Δ脚底y| 中位 %.1f 最大 %.1f' % (statistics.median(fy), max(fy)), flush=True)
    print('[SUM] |Δ中心y| 中位 %.1f 最大 %.1f' % (statistics.median(cy), max(cy)), flush=True)
    over = [c for c in changes if c['bottom'] > work_bottom]
    print('[SUM] 变更后底边越过工作区 %d/%d 次，最大越界 %d px' % (
        len(over), len(changes), max([c['bottom'] - work_bottom for c in over] or [0])), flush=True)

try:
    w.cleanup_on_exit()
except Exception:
    pass
app.quit()
print('[DONE]', flush=True)

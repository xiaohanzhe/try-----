# -*- coding: utf-8 -*-
"""第 34 轮：《楼层实现》审查 —— 让 get_drop_destination 真正出现差异的受控取证。

关键：真实桌面上的窗口**互相重叠**。只有当高名次窗口的矩形**也覆盖宠物位置**时，
「从 index 0 起扫」才会先命中它 → 落点被抬到更高的层。

布局（模拟真实重叠）：
    h=10 层  y = 300..699   ← 与 h=5 重叠
    h=5  层  y = 500..899
    宠物 (200, 600) 同时落在**两块板**内
      · 正控制（idx=0）→ 从 index 1 起扫 → 命中 h=5 ✅
      · 被测（idx=-1）→ 从 index 0 起扫 → 命中 h=10（更高的层）❌
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'ralsei_pet')

from PyQt5.QtWidgets import QApplication           # noqa: E402
from PyQt5.QtCore import QRect, QPoint             # noqa: E402

app = QApplication([])
from modules.floor_manager import FloorManager      # noqa: E402

W, H = 400, 400


def mk(h, hw, y):
    r = QRect(0, y, W, H)
    return {
        'type': 'window', 'window': {'hwnd': hw, 'rect': r},
        'rect': r, 'visible_rects': [r], 'visible_area': r.width() * r.height(),
        'z_order': h, 'platform_height': h, 'window_hwnd': hw,
    }


def build():
    fm = FloorManager()
    fm.desktop_floor = {
        'type': 'desktop', 'rect': QRect(0, 0, 2000, 2000),
        'visible_rects': [QRect(0, 0, 2000, 2000)],
        'platform_height': 0, 'z_order': 0,
    }
    # h=10 与 h=5 的矩形重叠（真实桌面的常态）
    fm.floors = [mk(10, 102, 300), mk(5, 103, 500)]
    fm.underlying_windows = [{'hwnd': w['window_hwnd'], 'class_name': 'Test'}
                             for w in fm.floors]
    return fm


POS = QPoint(200, 600)   # 同时落在 h=10(y300..699) 与 h=5(y500..899) 内

print('=' * 78)
print('受控取证 v4（重叠布局）：宠物 = (%d, %d)' % (POS.x(), POS.y()))
print('  h=10 层 y300..699 与 h=5 层 y500..899 **重叠**，宠物同时落在两块板内')
print('=' * 78)

fm = build()
allf = sorted(fm.floors + [fm.desktop_floor], key=lambda x: x['platform_height'], reverse=True)
live10 = [f for f in fm.floors if f['platform_height'] == 10][0]
i1 = fm._index_of_floor(allf, live10)
d1, _ = fm.get_drop_destination(POS, live10)
l1 = fm.adjacent_lower_floor(live10)
print()
print('【正控制】current_floor = 活楼层 h=10（index=%d）' % i1)
print('   get_drop_destination = h', d1['platform_height'], '  <-- 从 index1 起扫 → h=5 ✅')
print('   adjacent_lower_floor = h', l1['platform_height'] if l1 else None, ' ✅')

stale = {'type': 'window', 'hwnd': 999999, 'platform_height': 15,
         'rect': QRect(0, 0, W, H), 'visible_rects': [QRect(0, 0, W, H)]}
fm2 = build()
allf2 = sorted(fm2.floors + [fm2.desktop_floor], key=lambda x: x['platform_height'], reverse=True)
i2 = fm2._index_of_floor(allf2, stale)
d2, _ = fm2.get_drop_destination(POS, stale)
l2 = fm2.adjacent_lower_floor(stale)
print()
print('【被测】current_floor = 已消失的 stale h=15（退化 index=%d）' % i2)
print('   get_drop_destination = h', d2['platform_height'], '  <-- 从 index0 起扫 → h=10（被抬高层）❌')
print('   adjacent_lower_floor = h', l2['platform_height'] if l2 else None, '  <-- 期望 h=5 ❌')

print()
print('=' * 78)
print('判读（两项都有差异，可证伪）：')
print('  ① get_drop_destination：h=%s → h=%s（+%d 名次，即「落到更上面那层」）'
      % (d1['platform_height'], d2['platform_height'],
         d2['platform_height'] - d1['platform_height']))
print('  ② adjacent_lower_floor：h=%s → %s'
      % (l1['platform_height'] if l1 else None, l2['platform_height'] if l2 else None))
print()
print('对照语义：正控制 = 「向下落到下面第一块板(h=5)」；')
print('         被测   = 「向上吸到更高那层(h=10)」，正是 _floor_identity 注释里')
print('                  描述的「凭空被上吸」历史缺陷的同型复现。')
print('=' * 78)

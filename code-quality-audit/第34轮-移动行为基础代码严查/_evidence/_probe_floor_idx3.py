# -*- coding: utf-8 -*-
"""第 34 轮：《楼层实现》审查 —— `_index_of_floor` 退化分支受控取证（第三版）。

前两版几何都选错了：`get_drop_destination` 要求候选层的**可见区域包含宠物位置**，
所以宠物必须落在某块板的矩形**之内**，扫描起点才会改变结果。

几何（屏幕 y 增大方向向下）：
    h=10 层   y = 100..399   （名次更高）
    h=5  层   y = 500..799   （名次更低，但屏幕上更靠下）
    h=1  层   y = 900..1199  （最低的窗口层）
    桌面 0    全屏

宠物位置 y = 600 → 落在 h=5 那块板的矩形内。
  · 正确：current_floor = h=10 → 从 index 1 起扫 → 第一块接住的是 h=5 ✅
  · 退化：current_index = -1 → 从 index 0 起扫 → 先命中 h=10 → 「向上吸一层」❌
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'ralsei_pet')

from PyQt5.QtWidgets import QApplication           # noqa: E402
from PyQt5.QtCore import QRect, QPoint             # noqa: E402

app = QApplication([])
from modules.floor_manager import FloorManager      # noqa: E402

W, H = 400, 300


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
    fm.floors = [mk(10, 102, 100), mk(5, 103, 500), mk(1, 104, 900)]
    fm.underlying_windows = [{'hwnd': w['window_hwnd'], 'class_name': 'Test'}
                             for w in fm.floors]
    return fm


POS = QPoint(200, 600)   # 落在 h=5 那块板矩形内

print('=' * 76)
print('受控取证 v3：宠物 = (%d, %d)，落在 h=5 板内' % (POS.x(), POS.y()))
print('  活楼层：h=10 (y100..399) / h=5 (y500..799) / h=1 (y900..1199) / 桌面0')
print('=' * 76)

fm = build()
allf = sorted(fm.floors + [fm.desktop_floor], key=lambda x: x['platform_height'], reverse=True)
live10 = [f for f in fm.floors if f['platform_height'] == 10][0]
i1 = fm._index_of_floor(allf, live10)
d1, _ = fm.get_drop_destination(POS, live10)
l1 = fm.adjacent_lower_floor(live10)
print()
print('【正控制】current_floor = 活楼层 h=10（在列表里，index=%d）' % i1)
print('   get_drop_destination = h', d1['platform_height'], '  <-- 从 index+1 起扫，先命中 h=5 ✅')
print('   adjacent_lower_floor = h', l1['platform_height'] if l1 else None, ' ✅')

stale = {'type': 'window', 'hwnd': 999999, 'platform_height': 15,
         'rect': QRect(0, 0, W, H), 'visible_rects': [QRect(0, 0, W, H)]}
fm2 = build()
allf2 = sorted(fm2.floors + [fm2.desktop_floor], key=lambda x: x['platform_height'], reverse=True)
i2 = fm2._index_of_floor(allf2, stale)
d2, _ = fm2.get_drop_destination(POS, stale)
l2 = fm2.adjacent_lower_floor(stale)
print()
print('【被测】current_floor = 已消失的 stale h=15（不在列表里，退化 index=%d）' % i2)
print('   get_drop_destination = h', d2['platform_height'], '  <-- -1 ⇒ 从 index 0 起扫 ⇒ 命中 h=10 ❌')
print('   adjacent_lower_floor = h', l2['platform_height'] if l2 else None, '  <-- 期望 h=5 ❌')

print()
print('=' * 76)
print('判读（只看真正有差异的两项）：')
print('  ① 落点：正确 h=%s → 被测 h=%s，差 %d 个名次；且被测值是**更高**的层'
      % (d1['platform_height'], d2['platform_height'],
         d2['platform_height'] - d1['platform_height']))
print('  ② adjacent_lower_floor：正确 h=%s → 被测 %s（None = 「下面没楼板了」）'
      % (l1['platform_height'] if l1 else None, l2['platform_height'] if l2 else None))
print('=' * 76)

# -*- coding: utf-8 -*-
"""第 34 轮：《楼层实现》审查 —— `_index_of_floor` 退化分支的**受控**取证。

上一版探针的几何选得不好（宠物 y 落在没有任何楼板覆盖处，两种情形都得桌面 0，
对照不出差异）。本版把宠物放在**两块板之下**（y 比两块板都低），这样
「从哪一层开始向下扫」才会真正决定落点。

几何（屏幕 y 向下增大）：
    h=10 层  y = 100..399      （最高名次）
    h=5  层  y = 500..799
    桌面     全屏
    宠物 y = 850  → 在**两块板之下**，向下扫时第一块能接住的应是 h=5；若从
    index 0（h=10）开始扫，而宠物 x 又落在 h=10 的横向范围内，
    就会被判到 h=10 → 「向上吸一层」。
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
    fm.floors = [mk(10, 102, 100), mk(5, 103, 500)]
    fm.underlying_windows = [{'hwnd': w['window_hwnd'], 'class_name': 'Test'}
                             for w in fm.floors]
    return fm


POS = QPoint(200, 850)   # 横向落在两块板的 x 范围内；纵向在两块板之下

print('=' * 74)
print('受控取证：宠物位置 = (%d, %d)，在两块板之下' % (POS.x(), POS.y()))
print('  活楼层： h=10 (y 100..399) / h=5 (y 500..799) / 桌面 0 (全屏)')
print('=' * 74)

fm = build()
live = [f for f in fm.floors if f['platform_height'] == 10][0]
allf = sorted(fm.floors + [fm.desktop_floor], key=lambda x: x['platform_height'], reverse=True)
d, _ = fm.get_drop_destination(POS, live)
lo = fm.adjacent_lower_floor(live)
print()
print('【正控制】current_floor = 活楼层 h=10（hwnd 在列表里）')
print('   _index_of_floor      =', fm._index_of_floor(allf, live))
print('   get_drop_destination = h', d['platform_height'], '  <-- 期望 h=5（下面第一块）')
print('   adjacent_lower_floor = h', lo['platform_height'] if lo else None, '  <-- 期望 h=5')

stale = {'type': 'window', 'hwnd': 999999, 'platform_height': 15,
         'rect': QRect(0, 0, W, H), 'visible_rects': [QRect(0, 0, W, H)]}
fm2 = build()
allf2 = sorted(fm2.floors + [fm2.desktop_floor], key=lambda x: x['platform_height'], reverse=True)
d2, _ = fm2.get_drop_destination(POS, stale)
lo2 = fm2.adjacent_lower_floor(stale)
print()
print('【被测】current_floor = 已消失的 stale h=15（hwnd 不在列表里）')
print('   _index_of_floor      =', fm2._index_of_floor(allf2, stale), '  (退化分支)')
print('   get_drop_destination = h', d2['platform_height'], '  <-- 期望 h=5，若得 h=10 即「向上吸一层」')
print('   adjacent_lower_floor = h', lo2['platform_height'] if lo2 else None, '  <-- 期望 h=5')

print()
print('=' * 74)
gap_a = d2['platform_height'] - d['platform_height']
print('落点差 = %s 个楼层名次差（正确 h=%s vs 错误 h=%s）'
      % (gap_a, d['platform_height'], d2['platform_height']))
print('adjacent_lower_floor：正控制 %s vs 被测 %s'
      % (lo['platform_height'] if lo else None, lo2['platform_height'] if lo2 else None))
print('=' * 74)

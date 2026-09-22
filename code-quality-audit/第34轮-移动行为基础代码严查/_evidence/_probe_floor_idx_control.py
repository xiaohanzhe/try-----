# -*- coding: utf-8 -*-
"""对照片（正控制）：同一个位置/同一批活楼层，只把 `current_floor` 换成
   **仍在列表里的**那一层，看 get_drop_destination / adjacent_lower_floor 的
   正确输出应该是什么 —— 用来证明 `-1` 那个结果是**错的**而不是「另一种合理」。
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'ralsei_pet')

from PyQt5.QtWidgets import QApplication           # noqa: E402
from PyQt5.QtCore import QRect, QPoint             # noqa: E402

app = QApplication([])
from modules.floor_manager import FloorManager      # noqa: E402


def mk(h, hw, y, w=400, hgt=300):
    r = QRect(0, y, w, hgt)
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
    fm.floors = [mk(10, 102, 500), mk(5, 103, 900)]
    fm.underlying_windows = [{'hwnd': w['window_hwnd'], 'class_name': 'Test'}
                             for w in fm.floors]
    return fm


POS = QPoint(200, 400)

print('=' * 70)
print('对照实验：位置与活楼层完全相同，只改 current_floor 的取值')
print('活楼层高度 = [10, 5, 0(桌面)]，宠物位置 =', POS.x(), POS.y())
print('=' * 70)

fh = 10
fm = build()
live = [f for f in fm.floors if f['platform_height'] == fh][0]
idx = fm._index_of_floor(sorted(fm.floors + [fm.desktop_floor],
                                key=lambda x: x['platform_height'], reverse=True), live)
d, dp = fm.get_drop_destination(POS, live)
lo = fm.adjacent_lower_floor(live)
cands = fm.get_jump_destinations(live, POS)
print()
print('【正控制】current_floor = 活楼层 h=10')
print('   _index_of_floor      =', idx, '(在列表里 → 正常路径)')
print('   get_drop_destination =', d['platform_height'], '<-- 正确：向下应落 h=5')
print('   adjacent_lower_floor =', lo['platform_height'] if lo else None, '<-- 正确：h=5')
print('   jump 候选高度        =', [f['platform_height'] for f, _ in cands])

stale = {'type': 'window', 'hwnd': 999999, 'platform_height': 15,
         'rect': QRect(0, 0, 10, 10), 'visible_rects': [QRect(0, 0, 10, 10)]}
fm2 = build()
idx2 = fm2._index_of_floor(sorted(fm2.floors + [fm2.desktop_floor],
                                  key=lambda x: x['platform_height'], reverse=True), stale)
d2, _ = fm2.get_drop_destination(POS, stale)
lo2 = fm2.adjacent_lower_floor(stale)
cands2 = fm2.get_jump_destinations(stale, POS)
print()
print('【被测】current_floor = 已消失的 stale h=15（列表里没有）')
print('   _index_of_floor      =', idx2, '(退化分支)')
print('   get_drop_destination =', d2['platform_height'], '<-- 实际：h=10，跳过了 h=5')
print('   adjacent_lower_floor =', lo2['platform_height'] if lo2 else None, '<-- 实际：None')
print('   jump 候选高度        =', [f['platform_height'] for f, _ in cands2])

print()
print('=' * 70)
print('判读：')
print('  ① get_drop_destination —— 从「向下落一层」变成「落到更高的一层」，'
      '差 1 个楼层名次；')
print('     而正确解 0/5 与错误解 10 之间隔着整整一层，说明这不是「量纲差 1px」级别。')
print('  ② adjacent_lower_floor —— 从「有下一层(h=5)」变成 None，'
      '直接被判「到底了、下面没楼板」。')
print('  ③ get_jump_destinations —— 桌面(h=0) 从候选里消失。')
print('=' * 70)

# -*- coding: utf-8 -*-
"""一次性探针：核对 floor_manager 的可见区域/楼层判定是否与"建楼"要求原文一致。

场景直接照抄要求文档里的比方：
  窗口A：很大的浏览器，在左边；
  窗口B：很小的记事本，在右边，并且被拖到了浏览器A的上面。
"""
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PET = os.path.join(BASE, 'ralsei_pet')
for _p in (os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if _p not in sys.path:
        sys.path.append(_p)

from PyQt5.QtCore import QPoint, QRect                       # noqa: E402
from floor_manager import FloorManager, visible_subrects, _rect_tuple, _area  # noqa: E402

OUT = []


def say(s):
    OUT.append(s)


def mk_window(hwnd, x, y, w, h, z):
    return {'hwnd': hwnd, 'title': 'w%d' % hwnd, 'class_name': 'C',
            'rect': QRect(x, y, w, h), 'z_order': z}


# --- 纯几何：矩形相减 ---
A = (0, 0, 1000, 800)
B = (600, 100, 900, 400)
pieces = visible_subrects(A, [B])
say('A-B pieces = %s' % pieces)
say('sum area = %d   expect = %d' % (sum(_area(p) for p in pieces), 1000 * 800 - 300 * 300))
say('overlap check = %s (all should be False)' % [
    (pieces[i][0] < pieces[j][2] and pieces[j][0] < pieces[i][2] and
     pieces[i][1] < pieces[j][3] and pieces[j][1] < pieces[i][3])
    for i in range(len(pieces)) for j in range(i + 1, len(pieces))])
say('covered point (700,150) in pieces? %s (expect False)' % [
    (p[0] <= 700 < p[2] and p[1] <= 150 < p[3]) for p in pieces])

# --- 楼层表 ---
fm = FloorManager(parent=None)
fm.underlying_windows = [mk_window(2001, 600, 100, 300, 300, 0),   # B 最前
                         mk_window(2002, 0, 0, 1000, 800, 1)]      # A 在后
fm._generate_floors()
say('')
say('floors = %d (expect 2)' % len(fm.floors))
for f in fm.floors:
    say('  hwnd=%s ph=%s visible_area=%s rects=%s' % (
        f['window_hwnd'], f['platform_height'], f['visible_area'],
        [ (r.left(), r.top(), r.right(), r.bottom()) for r in f['visible_rects'] ]))

say('')
say('get_current_floor(700,150) -> hwnd=%s (expect 2001 = 记事本)' %
    fm.get_current_floor(QPoint(700, 150)).get('window_hwnd'))
say('get_current_floor(100,400) -> hwnd=%s (expect 2002 = 浏览器)' %
    fm.get_current_floor(QPoint(100, 400)).get('window_hwnd'))
say('get_current_floor(50,50)   -> hwnd=%s (expect 2002 = 浏览器)' %
    fm.get_current_floor(QPoint(50, 50)).get('window_hwnd'))

b_floor = fm.get_floor_by_window(2001)
a_floor = fm.get_floor_by_window(2002)
dest, _ = fm.get_drop_destination(QPoint(700, 150), b_floor)
say('drop from 记事本@(700,150) -> %s (expect desktop：A 在那里被盖住)' % dest.get('type'))
dest2, _ = fm.get_drop_destination(QPoint(700, 700), b_floor)
say('drop from 记事本@(700,700) -> hwnd=%s (expect 2002：A 在那里可见)' % dest2.get('window_hwnd'))

# --- 完全被盖住 → 不存在 ---
fm2 = FloorManager(parent=None)
fm2.underlying_windows = [mk_window(3001, 0, 0, 1920, 1080, 0),    # 全屏在最前
                          mk_window(3002, 100, 100, 400, 300, 1)]  # 完全被盖住
fm2._generate_floors()
say('')
say('covered-by-fullscreen: floors = %d (expect 1，被完全盖住的不存在)' % len(fm2.floors))
say('get_current_floor(200,200) -> hwnd=%s (expect 3001)' %
    fm2.get_current_floor(QPoint(200, 200)).get('window_hwnd'))

# --- 部分遮挡到不足以站：只剩细缝（< MIN_FLOOR_VISIBLE_AREA=1600） ---
# 被遮的窗口本身只有 200 高，前面的窗口盖到 199 → 只剩 1000x1 = 1000 px²
fm3 = FloorManager(parent=None)
fm3.underlying_windows = [mk_window(4001, 0, 0, 1000, 199, 0),
                          mk_window(4002, 0, 0, 1000, 200, 1)]
fm3._generate_floors()
say('')
say('sliver(1000x1=1000px2): floors = %d (expect 1，细缝站不住，不算楼层)' % len(fm3.floors))
for f in fm3.floors:
    say('  hwnd=%s visible_area=%s' % (f['window_hwnd'], f['visible_area']))

# --- 同一条缝放宽到 4px（4000px2 > 1600）→ 应当恢复成楼层 ---
fm4 = FloorManager(parent=None)
fm4.underlying_windows = [mk_window(4001, 0, 0, 1000, 196, 0),
                          mk_window(4002, 0, 0, 1000, 200, 1)]
fm4._generate_floors()
say('sliver(1000x4=4000px2): floors = %d (expect 2，够站就恢复)' % len(fm4.floors))
for f in fm4.floors:
    say('  hwnd=%s visible_area=%s' % (f['window_hwnd'], f['visible_area']))

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_out_geom.txt'), 'w',
          encoding='utf-8') as fh:
    fh.write('\n'.join(OUT))
print('\n'.join(OUT))

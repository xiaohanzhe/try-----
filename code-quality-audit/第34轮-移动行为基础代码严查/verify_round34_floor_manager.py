# -*- coding: utf-8 -*-
"""第三十四轮 · 楼层实现审查 回归锁（floor_manager 部分）

锁住第 34 轮从《楼层实现》审查中坐实并修复的缺陷：
    `_index_of_floor` 退化分支在 `i == 0` 时返回 **-1**，而 -1 被两个消费方
    误读成"比最高活楼层还高"，导致
      · `get_drop_destination` 从最高的活楼层开始向下扫 → 宠物被"上吸"一层；
      · `adjacent_lower_floor` 返回 None（语义 =「下面没楼板了」）→ 明明有下层却报"到底了"。

判据纪律（§5）：
  · 全部走**产品真函数**（`floor_manager.FloorManager`），不重写被测逻辑；
  · 先建 `QApplication` 再读任何坐标（DPI 量纲铁律，§4.10）；
  · 断言**行为**（返回值），不断言写法；
  · 正/负控制成对：既要有"修复后必须成立"的断言，也要有"修复不许伤到
    正常路径（i>=1 的 i-1 语义）"的反向控制。

输出格式必须是字面量 `[PASS]` / `[FAIL]` —— `run_all.py` 用
`re.findall(r'\[PASS\]|\[\s*OK\s*\]')` 计数（第 34 轮踩过：写成 "  PASS  " 会恒为 0）。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))

from PyQt5.QtWidgets import QApplication           # noqa: E402
from PyQt5.QtCore import QRect, QPoint             # noqa: E402

_app = QApplication.instance() or QApplication([])

from modules.floor_manager import FloorManager      # noqa: E402

_results = []


def check(cond, msg):
    _results.append(bool(cond))
    print('[PASS] %s' % msg if cond else '[FAIL] %s' % msg)


W, H = 400, 400


def _mk_window_floor(platform_height, hwnd, y, w=W, h=H):
    r = QRect(0, y, w, h)
    return {
        'type': 'window',
        'window': {'hwnd': hwnd, 'rect': r},
        'rect': r,
        'visible_rects': [r],
        'visible_area': r.width() * r.height(),
        'z_order': platform_height,
        'platform_height': platform_height,
        'window_hwnd': hwnd,
    }


def _mk_desktop():
    r = QRect(0, 0, 2000, 2000)
    return {
        'type': 'desktop', 'rect': r, 'visible_rects': [r],
        'platform_height': 0, 'z_order': 0,
    }


def _fm_with(floors):
    fm = FloorManager()
    fm.desktop_floor = _mk_desktop()
    fm.floors = list(floors)
    fm.underlying_windows = [
        {'hwnd': f['window_hwnd'], 'class_name': 'Test'} for f in floors]
    return fm


def _sorted_all(fm):
    return sorted(fm.floors + [fm.desktop_floor],
                  key=lambda x: x['platform_height'], reverse=True)


# ======================================================================
# [A] 核心缺陷：stale 楼层高于所有活楼层时，退化下标**不许**是 -1
# ======================================================================
print('--- [A] _index_of_floor 退化分支不得返回 -1（第 34 轮修复点）---')

fm = _fm_with([_mk_window_floor(10, 102, 300), _mk_window_floor(5, 103, 500)])
stale_highest = _mk_window_floor(15, 999999, 0)
idx = fm._index_of_floor(_sorted_all(fm), stale_highest)

check(idx != -1,
      '[A1] stale 楼层(h=15)高于所有活楼层(10/5/0) → 下标不得为 -1（实测 %s）' % idx)
check(idx == 0,
      '[A2] 该情形必须规范成 0（=「高于最高活楼层」，留出向下扫的起点；实测 %s）' % idx)

neg = _mk_window_floor(-5, 888888, 0)
idx_lo = fm._index_of_floor(_sorted_all(fm), neg)
check(idx_lo == len(_sorted_all(fm)) - 1,
      '[A3] 反向控制：stale 比所有活楼层都低 → 仍返回末位（实测 %s）' % idx_lo)

# ======================================================================
# [B] 下游行为：get_drop_destination 不许把宠物"上吸"到更高的楼层
# ======================================================================
print('--- [B] get_drop_destination 落点不得高于正确解 ---')

# 重叠布局：h=10 (y300..699) 与 h=5 (y500..899) 同时覆盖 y=600
fm = _fm_with([_mk_window_floor(10, 102, 300), _mk_window_floor(5, 103, 500)])
pos = QPoint(200, 600)

live10 = [f for f in fm.floors if f['platform_height'] == 10][0]
d_live, _ = fm.get_drop_destination(pos, live10)
check(d_live['platform_height'] == 5,
      '[B1] 正控制：current_floor=活楼层 h=10 → 向下落到 h=5（实测 h=%s）'
      % d_live['platform_height'])

stale = _mk_window_floor(15, 999999, 0)
d_stale, _ = fm.get_drop_destination(pos, stale)
check(d_stale['platform_height'] == 5,
      '[B2] 修复：current_floor=已消失的 h=15 → 落点仍为 h=5，不得被抬到 h=10'
      '（实测 h=%s）' % d_stale['platform_height'])
check(d_stale['platform_height'] <= d_live['platform_height'],
      '[B3] 落点单调性：退化路径的落点不得**高于**正常路径的落点')

# ======================================================================
# [C] 下游行为：adjacent_lower_floor 不许把"有下层"报成 None
# ======================================================================
print('--- [C] adjacent_lower_floor 不得误报「下面没楼板了」---')

fm = _fm_with([_mk_window_floor(10, 102, 300), _mk_window_floor(5, 103, 500)])
live10 = [f for f in fm.floors if f['platform_height'] == 10][0]
a_live = fm.adjacent_lower_floor(live10)
check(a_live is not None and a_live['platform_height'] == 5,
      '[C1] 正控制：活楼层 h=10 的下一层是 h=5（实测 %s）'
      % (a_live['platform_height'] if a_live else None))

stale = _mk_window_floor(15, 999999, 0)
a_stale = fm.adjacent_lower_floor(stale)
check(a_stale is not None,
      '[C2] 修复：已消失的 h=15 之下**确实还有活楼层** → 不得返回 None'
      '（None 的语义是「已在最底层」；实测 %s）'
      % (a_stale['platform_height'] if a_stale else None))

# ======================================================================
# [D] 反向控制：正常路径（hwnd 在列表里）必须完全不受影响
# ======================================================================
print('--- [D] 反向控制：正常路径不受修复影响（i>=1 的 i-1 语义保持）---')

fm = _fm_with([_mk_window_floor(15, 101, 100), _mk_window_floor(10, 102, 300),
               _mk_window_floor(5, 103, 500)])
allf = _sorted_all(fm)
for h in (15, 10, 5):
    f = [x for x in fm.floors if x['platform_height'] == h][0]
    got = fm._index_of_floor(allf, f)
    want = [x['platform_height'] for x in allf].index(h)
    check(got == want,
          '[D] 活楼层 h=%s → 下标 %s（期望 %s，走正常路径不受影响）'
          % (h, got, want))

# 退化路径中 i>=1 的分支：stale 高度落在活楼层之间 → 必须仍是 i-1
fm = _fm_with([_mk_window_floor(15, 101, 100), _mk_window_floor(10, 102, 300),
               _mk_window_floor(5, 103, 500)])
mid = _mk_window_floor(12, 777777, 0)   # 介于 15 与 10 之间，列表里没有
got = fm._index_of_floor(_sorted_all(fm), mid)
check(got == 0,
      '[D2] 反向控制：stale h=12 落在 15 与 10 之间 → 退回"不高于它"的最近项 = 下标 0'
      '（i-1 语义保持；实测 %s）' % got)

# ======================================================================
# [E] 桌面层与空列表的健全性
# ======================================================================
print('--- [E] 健全性：桌面层 / 单个桌面 ---')

fm = _fm_with([])
only_desktop = _sorted_all(fm)
check(fm._index_of_floor(only_desktop, fm.desktop_floor) == 0,
      '[E1] 只有桌面时，桌面下标 = 0')

stale2 = _mk_window_floor(50, 555555, 0)
check(fm._index_of_floor(only_desktop, stale2) != -1,
      '[E2] 只有桌面 + stale 高于一切 → 下标不得为 -1')
check(fm.adjacent_lower_floor(fm.desktop_floor) is None,
      '[E3] 桌面是最底层 → adjacent_lower_floor 必须返回 None（口径保持）')

# ======================================================================
print()
n_pass = sum(1 for r in _results if r)
n_total = len(_results)
print('[SUMMARY] round34_floor_manager: %d/%d PASS' % (n_pass, n_total))
sys.exit(0 if n_pass == n_total else 1)

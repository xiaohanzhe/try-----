# -*- coding: utf-8 -*-
"""第 34 轮：《楼层实现》审查 —— 用产品真函数复现 `_index_of_floor` 退化分支 `-1`
   在真实序列（站在最高窗口上 → 关掉它 → 重力坠落）下的实际后果。

判据纪律（§5）：能从源码拿的别 import；能用产品函数的**绝不重写**。
故这里直接调用 floor_manager 的产品实现，只手工构造 floors 状态。
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'ralsei_pet')

from PyQt5.QtWidgets import QApplication           # noqa: E402
from PyQt5.QtCore import QRect, QPoint             # noqa: E402

app = QApplication([])                              # 必须先建 QApplication（DPI 量纲铁律）
from modules.floor_manager import FloorManager      # noqa: E402


def mk(h, hw, y, w=400, hgt=300):
    r = QRect(0, y, w, hgt)
    return {
        'type': 'window', 'window': {'hwnd': hw, 'rect': r},
        'rect': r, 'visible_rects': [r], 'visible_area': r.width() * r.height(),
        'z_order': h, 'platform_height': h, 'window_hwnd': hw,
    }


print('=' * 68)
print('场景：宠物站在「最高的那个窗口」上 → 用户把它关掉 → 重力坠落')
print('=' * 68)

fm = FloorManager()
fm.desktop_floor = {
    'type': 'desktop', 'rect': QRect(0, 0, 2000, 2000),
    'visible_rects': [QRect(0, 0, 2000, 2000)],
    'platform_height': 0, 'z_order': 0,
}

# ── 关闭前：三个窗口 15 / 10 / 5，宠物站 15 层 ──────────────────────
before = [mk(15, 101, 100), mk(10, 102, 500), mk(5, 103, 900)]
fm.floors = list(before)
fm.underlying_windows = [{'hwnd': w['window_hwnd'], 'class_name': 'Test'} for w in before]
pet_floor = fm.get_current_floor(QPoint(200, 110))
print('[关闭前] 活楼层高度:', sorted([f['platform_height'] for f in fm.floors], reverse=True))
print('         宠物所在层 h =', pet_floor['platform_height'])
print('         is_floor_valid =', fm.is_floor_valid(pet_floor))

# ── 关闭后：那个窗口从 underlying_windows 里消失，floors 重建 ────────
after = [mk(10, 102, 500), mk(5, 103, 900)]
fm.floors = list(after)
fm.underlying_windows = [{'hwnd': w['window_hwnd'], 'class_name': 'Test'} for w in after]
# 此刻 current_floor 仍是那只已消失窗口的**旧 dict**（产品里由 self.current_floor 持有）
stale = pet_floor

print()
print('[关闭后] 活楼层高度:', sorted([f['platform_height'] for f in fm.floors], reverse=True))
print('         stale platform_height =', stale['platform_height'],
      '（窗口已不在 underlying_windows）')
print('         is_floor_valid(stale) =', fm.is_floor_valid(stale))

allf_live = sorted(fm.floors + [fm.desktop_floor],
                   key=lambda x: x['platform_height'], reverse=True)
print('         sorted(floors+desktop) 高度 =', [f['platform_height'] for f in allf_live])
idx = fm._index_of_floor(allf_live, stale)
print('         _index_of_floor(stale) =', idx, '  <== 期望「指向不高于当前楼层的位置」')
print('              但 -1 会被 range(idx+1, n) 当成「从第 0 个（最高的活楼层）开始」')

pos = QPoint(200, 400)
dest, dpos = fm.get_drop_destination(pos, stale)
print('         get_drop_destination -> h =', dest['platform_height'],
      '（正确应为 0=桌面；宠物会落到它**上方**那块板）')

print()
print('--- 影响面 2：adjacent_lower_floor 误报「无处可下」 ---')
low = fm.adjacent_lower_floor(stale)
print('         adjacent_lower_floor(stale) =', low,
      '  <== None 的语义是「已在最底层，下面没有楼板」')
print('              但桌面(h=0)明明在下面 → 宠物无法用「向下跳」离开，只能等重力')

print()
print('--- 影响面 3：get_jump_destinations 把「存在的层」漏掉 ---')
cands = fm.get_jump_destinations(stale, pos)
print('         候选高度 =', [f['platform_height'] for f, _p in cands])
print('         含 0（桌面）?', any(f['platform_height'] == 0 for f, _p in cands),
      ' <== 桌面 h=0 被 current_index+1 的边界漏掉')
print()
print('=' * 68)
print('结论：退化分支不是「不可达」，而是「stale 高于所有活楼层时必达」；')
print('     返回 -1 不是安全的「未找到」哨兵，而是「比最高层还高」的语义。')
print('=' * 68)

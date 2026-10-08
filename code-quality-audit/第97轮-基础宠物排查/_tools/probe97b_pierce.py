# -*- coding: utf-8 -*-
"""第97轮补证：`handle_jump` 的"穿透检查"是否把**桌面**误判成障碍。

## 被测对象（**原文出处**：`ralsei_pet/src/main.py:8260-8272`）

    cur_fid = self._floor_identity_key(getattr(self, 'current_floor', None))
    tgt_fid = self._floor_identity_key(getattr(self, 'jump_target_floor', None))
    all_floors = self.floor_manager.get_all_floors()
    for floor in all_floors:
        if self._floor_identity_key(floor) in (cur_fid, tgt_fid):
            continue
        if floor['rect'].intersects(current_rect):
            # 检测到穿透，取消跳跃，启动重力掉落
            self.start_falling()
            return

## 为什么怀疑它

`get_all_floors()`（`floor_manager.py:675`）= `self.floors + [self.desktop_floor]`：
桌面层**总是**在列表里，而 `desktop_floor['rect']` 恒等于**整个虚拟屏幕**
（`update_floors`，`floor_manager.py:178`）。

排除条件只有 `_floor_identity_key(floor) in (cur_fid, tgt_fid)` —— 即"起点/终点"。
桌面层的 key 是 `'desktop'`，因此**只有当起点或终点本身是桌面时才被排除**。

⇒ 当**起点和终点都是窗口**时，桌面层留在循环里，而宠物矩形恒在屏幕内
（`_clamp_pos_to_desktop` 保证）⇒ `desktop_floor['rect'].intersects(current_rect)`
**恒为 True** ⇒ 判"穿透"⇒ `start_falling()`。

## 本脚本口径

- `FloorManager` 用**真实模块**（`ralsei_pet/modules/floor_manager.py`）。
- `_floor_identity_key` 用 `main.py:8406-8419` 的**等价复写**（staticmethod，无隐藏状态）。
- 循环**照抄**上面那段（只把 `start_falling()` 换成记录，便于一次跑完所有场景）。
- 不引入任何本脚本自造的判据。
"""
import os
import sys

REPO = r"C:\Users\23002\WorkBuddy\Worktrees\try - 副本\main-a7556e9c"
PET = os.path.join(REPO, "ralsei_pet")
sys.path.insert(0, os.path.join(PET, "modules"))
sys.path.insert(0, os.path.join(PET, "src"))

# DPI 契约：先建 QApplication 再量屏幕 / 用 QRect（本项目 §3-③）
from PyQt5.QtWidgets import QApplication  # noqa: E402
from PyQt5.QtCore import QRect  # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv)

from floor_manager import FloorManager  # noqa: E402


# ---- main.py:8406-8419 的等价复写 --------------------------------------
def identity_key(floor):
    if floor is None:
        return None
    if floor.get('type') == 'desktop':
        return 'desktop'
    return ('window', floor.get('window_hwnd'))


# ---- main.py:8260-8272 的等价复写 --------------------------------------
def pierce_hits(fm, current_floor, jump_target_floor, current_rect):
    """返回"被判穿透"的楼层列表（原代码命中即 start_falling + return）。"""
    cur_fid = identity_key(current_floor)
    tgt_fid = identity_key(jump_target_floor)
    hits = []
    for floor in fm.get_all_floors():
        if identity_key(floor) in (cur_fid, tgt_fid):
            continue
        if floor['rect'].intersects(current_rect):
            hits.append(floor)
    return hits


def label(floor):
    if floor is None:
        return 'None'
    return '%s(h=%s)' % (floor.get('type'), floor.get('platform_height'))


# ---- 构造一个真实 FloorManager -----------------------------------------
SCREEN = QRect(0, 0, 1920, 1080)


def make_fm(windows):
    """windows: [(hwnd, QRect)]，按给定顺序视为 z 序（越前越'高'）。"""
    fm = FloorManager(parent=None)
    fm.desktop_floor['rect'] = QRect(SCREEN)
    fm.underlying_windows = [
        {'hwnd': h, 'title': 'w%d' % h, 'class_name': 'Notepad',
         'rect': QRect(r), 'z_order': i}
        for i, (h, r) in enumerate(windows)
    ]
    fm._generate_floors()
    return fm


W_A = (1001, QRect(200, 200, 800, 600))    # 窗口 A
W_B = (1002, QRect(300, 250, 700, 500))    # 窗口 B（压在 A 前面 ⇒ 更高）


def main():
    print('=' * 72)
    print('第97轮补证：handle_jump 穿透检查 × desktop_floor')
    print('=' * 72)

    # ---- 场景 1：只有桌面（没有任何窗口）----
    fm0 = make_fm([])
    print('\n[场 1] floors=%d（无窗口）' % len(fm0.floors))
    for case, (cur, tgt, rect) in {
        '桌面→桌面(移动)': (fm0.desktop_floor, fm0.desktop_floor,
                        QRect(500, 800, 36, 76)),
    }.items():
        hits = pierce_hits(fm0, cur, tgt, rect)
        print('  %-16s → 穿透命中: %s' % (case, [label(f) for f in hits] or '无'))

    # ---- 场景 2：一个窗口（A）----
    fm1 = make_fm([W_A])
    fA = fm1.get_floor_by_window(W_A[0])
    print('\n[场 2] floors=%d  A: %s' % (len(fm1.floors), label(fA)))
    cases = [
        ('桌面→桌面(移动)', fm1.desktop_floor, fm1.desktop_floor, QRect(1500, 900, 36, 76)),
        ('桌面→窗口A', fm1.desktop_floor, fA, QRect(1500, 900, 36, 76)),
        ('窗口A→桌面(下)', fA, fm1.desktop_floor, QRect(400, 400, 36, 76)),
        ('窗口A→窗口A(原地)', fA, fA, QRect(400, 400, 36, 76)),
    ]
    for case, cur, tgt, rect in cases:
        hits = pierce_hits(fm1, cur, tgt, rect)
        verdict = '★ 触发 start_falling' if hits else 'ok'
        print('  %-18s 起点=%-10s 终点=%-10s → 命中 %-22s %s'
              % (case, label(cur), label(tgt),
                 str([label(f) for f in hits]) or '无', verdict))

    # ---- 场景 3：两个窗口（B 压在 A 前面 ⇒ B 更高）----
    # z 序：列表里 z_order 越小越靠前 = 越高（_generate_floors 口径）。
    fm2 = make_fm([W_B, W_A])
    fA2 = fm2.get_floor_by_window(W_A[0])
    fB2 = fm2.get_floor_by_window(W_B[0])
    print('\n[场 3] floors=%d  A=%s  B=%s' % (len(fm2.floors), label(fA2), label(fB2)))
    # 站在 A 的**下边缘**（B 的正下方、A 的可见区里）：这是"向上跳 B"的真实起点。
    stand_on_A_below_B = QRect(500, 760, 36, 76)
    cases2 = [
        ('窗口A→窗口B(上跳)', fA2, fB2, stand_on_A_below_B),
        ('窗口A→桌面(下跳)', fA2, fm2.desktop_floor, stand_on_A_below_B),
        ('窗口B→窗口A(下跳)', fB2, fA2, QRect(500, 350, 36, 76)),
    ]
    for case, cur, tgt, rect in cases2:
        hits = pierce_hits(fm2, cur, tgt, rect)
        verdict = '★ 触发 start_falling' if hits else 'ok'
        print('  %-20s 起点=%-10s 终点=%-10s → 命中 %-22s %s'
              % (case, label(cur), label(tgt),
                 str([label(f) for f in hits]) or '无', verdict))
    # 可达性：get_jump_destinations 是否真的会给出"跳 B"这个候选
    try:
        cands = fm2.get_jump_destinations(fA2, stand_on_A_below_B.topLeft())
        print('  ↳ get_jump_destinations(A, 站位) = %s'
              % [(label(f), (p.x(), p.y())) for f, p in cands])
    except Exception as e:
        print('  ↳ get_jump_destinations 异常: %s' % e)

    # ---- 结论 ----
    print('\n' + '=' * 72)
    print('判读：只要"起点与终点都不是桌面"，desktop_floor 就落在循环里，')
    print('     而它在屏幕内恒 intersects ⇒ 判穿透 ⇒ start_falling。')
    print('=' * 72)


if __name__ == '__main__':
    main()

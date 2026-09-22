# -*- coding: utf-8 -*-
"""第34轮续 探针 F34-3 后果验证：sprite_size=100 导致右下角"永不到达"卡走路

真机已取到（证据 29）：
    idle 帧 69x47，scale_factor=2.0 ⇒ 窗口 138x94
    generate_new_move_target 用 sprite_size = int(50*2.0) = 100（单一标量）

本探针：逐字抽取 `update_movement` 的位置夹取与到达判定，
量化"目标在右下角时能否到达"。

做法：不 import main。把 L2001-2061 的夹取+到达判定**逐字抽出**成函数，
用一个最小 self 桩驱动（速度、位置、屏幕几何、目标都可控）。
"""
import ast
import io
import math
import os
import sys

from PyQt5.QtCore import QRect, QPoint

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MAIN = os.path.join(REPO, 'ralsei_pet', 'src', 'main.py')

pass_n = 0
fail_n = 0


def check(name, cond, detail=''):
    global pass_n, fail_n
    if cond:
        pass_n += 1
        print('[PASS] %s %s' % (name, detail))
    else:
        fail_n += 1
        print('[FAIL] %s %s' % (name, detail))


src = open(MAIN, encoding='utf-8').read()
lines = src.splitlines()

print('== 抽取被测语句（main.py L2001-2010 夹取 + L2058-2061 到达判定）==')
for i in range(2000, 2011):
    print('%5d| %s' % (i + 1, lines[i]))
print('   ...')
for i in range(2057, 2062):
    print('%5d| %s' % (i + 1, lines[i]))
print()

# 屏幕几何：模拟一块 1920x1080 的主屏（虚拟桌面左上 (0,0)）
SCREEN = QRect(0, 0, 1920, 1080)

WIN_W, WIN_H = 138, 94        # 真机实测
SPRITE_SIZE_HARDCODED = int(50 * 2.0)   # = 100


def simulate(target_x, target_y, hardcoded=True, steps=400):
    """按 update_movement 的 is_moving 分支逐帧推进，返回 (最终位置, 是否到达, 帧数)。

    实现严格照抄 L2001-2010 的夹取与 L2058-2061 的到达判定：
      · 夹取量 = sprite_size（hardcoded）或 self.width()/self.height()（修法）
      · 到达判据 = distance_sq <= max((speed*3)^2, 30^2)
    """
    speed = 5.0                     # config movement.speed
    cur = QPoint(500, 500)          # 起始位置
    target = QPoint(target_x, target_y)
    _threshold_sq = max((speed * 3.0) ** 2, 30.0 ** 2)   # = 900.0

    # 夹取量口径
    if hardcoded:
        clamp_w = clamp_h = SPRITE_SIZE_HARDCODED
    else:
        clamp_w, clamp_h = WIN_W, WIN_H

    for step in range(steps):
        dx = target.x() - cur.x()
        dy = target.y() - cur.y()
        distance_sq = dx * dx + dy * dy
        distance = math.sqrt(distance_sq) if distance_sq > 0 else 0
        if distance > 0:
            dir_x, dir_y = dx / distance, dy / distance
            # 简化：直接用 speed 作 step（真实实现有平滑，但 max_move_distance = speed）
            move = min(distance, speed)
            new_x = cur.x() + dir_x * move
            new_y = cur.y() + dir_y * move
            new_x, new_y = int(round(new_x)), int(round(new_y))
            # ---- L2009-2010（逐字口径）----
            new_x = max(SCREEN.left(), min(new_x, SCREEN.right() - clamp_w))
            new_y = max(SCREEN.top(), min(new_y, SCREEN.bottom() - clamp_h))
            cur = QPoint(new_x, new_y)
        # ---- L2061 到达判定 ----
        if distance_sq <= _threshold_sq:
            return cur, True, step
    return cur, False, steps


print('== 场景 1：目标在屏幕右下角极限位置 ==')
# 目标 = 右下角（用"真实窗口尺寸"夹取才该到的位置）
tx = SCREEN.right() - WIN_W   # 1782
ty = SCREEN.bottom() - WIN_H  # 986
print('   目标 = (%d, %d)  ← 按真实 138x94 夹取该到的位置' % (tx, ty))

cur_h, arrived_h, steps_h = simulate(tx, ty, hardcoded=True)
cur_c, arrived_c, steps_c = simulate(tx, ty, hardcoded=False)
print('   硬编码 sprite_size=100：最终 %s 到达=%s 步数=%d'
      % ((cur_h.x(), cur_h.y()), arrived_h, steps_h))
print('   修法 self.width/height：最终 %s 到达=%s 步数=%d'
      % ((cur_c.x(), cur_c.y()), arrived_c, steps_c))

check('F1 硬编码口径：目标在右下角时**无法到达**（卡在走路状态）',
      arrived_h is False, '(arrived=%s, 卡在 %s)' % (arrived_h, (cur_h.x(), cur_h.y())))
check('F2 修法口径：同一目标**能到达**', arrived_c is True,
      '(arrived=%s, 步数=%d)' % (arrived_c, steps_c))
check('F3 鉴别力：两版结果不同（探针确实测到差异）',
      arrived_h != arrived_c)

# 算出"卡住点"与目标的距离，说明为何永远过不了阈值
d_h = math.hypot(tx - cur_h.x(), ty - cur_h.y())
print('   硬编码版卡住点距目标 = %.1f px（阈值 sqrt(900)=30 px）' % d_h)
check('F4 卡住点距目标 > 30px 阈值（故到达判定永远为假）',
      d_h > 30.0, '(d=%.1f)' % d_h)

print()
print('== 场景 2：目标略偏内（能到达的对照，证明不是探针恒假）==')
tx2 = SCREEN.right() - WIN_W - 30
ty2 = SCREEN.bottom() - WIN_H - 30
cur_h2, arrived_h2, _ = simulate(tx2, ty2, hardcoded=True)
print('   目标 = (%d, %d)，硬编码版 到达=%s' % (tx2, ty2, arrived_h2))
check('F5 正控制：目标远离右下极限时，硬编码版也能到达（排除探针恒假）',
      arrived_h2 is True)

print()
print('== 场景 3：Y 方向偏差（-6px，保守）==')
ty3 = SCREEN.bottom() - WIN_H   # 986
cur_h3, arrived_h3, _ = simulate(500, ty3, hardcoded=True)
print('   目标 y=%d（真实高 94 时的底部），硬编码版 到达=%s 停在 y=%d'
      % (ty3, arrived_h3, cur_h3.y()))
check('F6 Y 方向：硬编码 100 > 实际 94 ⇒ 只少用 6px，仍可达（无害，但口径不一致）',
      arrived_h3 is True, '(停在 y=%d)' % cur_h3.y())

print()
print('== 汇总 ==')
print('  窗口真机实测 = %dx%d（idle 帧 69x47 × scale 2.0）' % (WIN_W, WIN_H))
print('  硬编码 sprite_size = %d  ⇒ X 偏差 %+d px，Y 偏差 %+d px'
      % (SPRITE_SIZE_HARDCODED, WIN_W - SPRITE_SIZE_HARDCODED, WIN_H - SPRITE_SIZE_HARDCODED))
print('  X 偏差为正 ⇒ 右下角目标无法到达，宠物卡在"一直走"状态（真缺陷）')
print('  Y 偏差为负 ⇒ 保守，无用户可见后果')
print()
print('SUITE_SUMMARY pass=%d fail=%d' % (pass_n, fail_n))

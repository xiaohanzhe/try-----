# -*- coding: utf-8 -*-
"""第34轮续 探针 F34-3 边界精算：38px 偏差 vs 30px 到达容差 —— 是否存在"卡住"的临界区？

前一个探针（证据 30）推翻了"必然卡住"，但暴露一个临界点：
    X 夹取偏差 = 38px（硬编码 100 vs 实际 138）
    到达容差   = 30px（max((speed*3)^2, 30^2) 开方）
    ⇒ 38 > 30，**理论上存在一个"偏差未被容差吸收"的窄带**

本探针穷举目标 x，找是否存在"硬编码版到不了、修法版到得了"的 x 区间。
若存在 → 是缺陷（窄带，偶发）；若不存在 → 彻底排除。
"""
import io
import math
import sys

from PyQt5.QtCore import QRect, QPoint

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

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


SCREEN = QRect(0, 0, 1920, 1080)
WIN_W, WIN_H = 138, 94
HARD = 100
SPEED = 5.0
THRESH_SQ = max((SPEED * 3.0) ** 2, 30.0 ** 2)   # 900
THRESH = math.sqrt(THRESH_SQ)                    # 30.0


def simulate(target, clamp_w, clamp_h, max_steps=2000):
    cur = QPoint(500, 500)
    for step in range(max_steps):
        dx = target.x() - cur.x()
        dy = target.y() - cur.y()
        dsq = dx * dx + dy * dy
        dist = math.sqrt(dsq) if dsq > 0 else 0
        if dist > 0:
            mx = min(dist, SPEED)
            nx = int(round(cur.x() + dx / dist * mx))
            ny = int(round(cur.y() + dy / dist * mx))
            nx = max(SCREEN.left(), min(nx, SCREEN.right() - clamp_w))
            ny = max(SCREEN.top(), min(ny, SCREEN.bottom() - clamp_h))
            cur = QPoint(nx, ny)
        if dsq <= THRESH_SQ:
            return True, step, cur
    return False, max_steps, cur


print('== 参数 ==')
print('  屏幕 %s' % (SCREEN,))
print('  窗口 %dx%d ；硬编码 clamp = %d' % (WIN_W, WIN_H, HARD))
print('  X 夹取偏差 = %d px ；到达容差 = %.1f px' % (WIN_W - HARD, THRESH))
print()

print('== 穷举：目标 x 从 1500 到 1920，y 固定为中部（避开 Y 干扰）==')
bad_x = []
for tx in range(1500, 1921):
    ty = 500
    ok_h, _, _ = simulate(QPoint(tx, ty), HARD, HARD)
    ok_c, _, _ = simulate(QPoint(tx, ty), WIN_W, WIN_H)
    if ok_c and not ok_h:
        bad_x.append(tx)

print('  "修法能到、硬编码到不了"的 x 个数 = %d' % len(bad_x))
if bad_x:
    print('  x 区间 = [%d, %d]（共 %d 个）' % (bad_x[0], bad_x[-1], len(bad_x)))
    # 关键：该区间是否落在"目标生成实际可达的范围"内？
    # generate_new_move_target 自己就用同一 clamp ⇒ 目标上限 = right - HARD = 1820
    print('  ⚠ 目标生成自身也用 sprite_size 夹取 ⇒ 目标上限 = %d' % (SCREEN.right() - HARD))
    in_range = [x for x in bad_x if x <= SCREEN.right() - HARD]
    print('  落在"目标生成可达范围(<= %d)"内的 x 个数 = %d'
          % (SCREEN.right() - HARD, len(in_range)))
    if in_range:
        print('  ⇒ 这些 x 区间 = [%d, %d]' % (in_range[0], in_range[-1]))
else:
    print('  ⇒ 不存在这样的 x（硬编码偏差被容差完全吸收）')

print()
print('== 结论判据 ==')
in_range = [x for x in bad_x if x <= SCREEN.right() - HARD]
check('G1 存在"硬编码到不了"的 x 区间', len(bad_x) > 0)
check('G2 该区间**落在目标生成可达范围内**（否则目标永远不会生成在那里 → 无实际影响）',
      len(in_range) > 0, '(in_range n=%d)' % len(in_range))

if in_range:
    print()
    print('  ⚠ 结论：存在实际可达的"卡住窗" x∈[%d,%d]，宽度 %d px'
          % (in_range[0], in_range[-1], len(in_range)))
    # 再核验：这些 x 的目标，宠物会卡在哪、离目标多远
    tx = in_range[len(in_range) // 2]
    ok_h, _, cur_h = simulate(QPoint(tx, 500), HARD, HARD)
    d = math.hypot(tx - cur_h.x(), 500 - cur_h.y())
    print('  样本 x=%d：硬编码版 2000 步后停在 %s，距目标 %.1f px（>%.1f 阈值）'
          % (tx, (cur_h.x(), cur_h.y()), d, THRESH))
    check('G3 样本点确实卡住（2000 步未到达）', ok_h is False)
    check('G4 卡住距离确实 > 阈值', d > THRESH, '(d=%.1f)' % d)

print()
print('SUITE_SUMMARY pass=%d fail=%d' % (pass_n, fail_n))

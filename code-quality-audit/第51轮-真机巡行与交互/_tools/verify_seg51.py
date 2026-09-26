# -*- coding: utf-8 -*-
"""第51轮 · `_seg_intersects_rect` 锚点自检 + 随机对拍。

为什么必须有这个脚本（本轮的真教训）
------------------------------------
第一次写 Liang-Barsky 时把 `p` 的符号配错了（`(dx, x0-rx)` 而非 `(-dx, x0-rx)`），
`plan_walk` 的穿模数**从 75 暴涨到 907** —— 判据整体变松，本该死路绕行的点对
被判成"直线可走"。**教训：能用锚点自检的判据，必须先过锚点再用。**

本脚本两层证据
--------------
① **锚点**（4 组，正/负控制成对，手算真值）
② **对拍**（3000 组随机段 vs 矩形，与"0.05px 极密采样"逐组比）
   · 若解析说"撞"而采样说"不撞" ⇒ 采样漏判（解析更严，可接受）
   · 若解析说"不撞"而采样说"撞" ⇒ **解析漏判（不可接受，必须为 0）**
"""
import io
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, PET)
_MOD = os.path.join(PET, 'modules')
if _MOD not in sys.path:
    sys.path.append(_MOD)

import scene_walk as SW       # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

F = SW._seg_intersects_rect
fails = []

print('=' * 70)
print('① 锚点（手算真值，正/负控制成对）')
print('=' * 70)
ANCHORS = [
    # (x0,y0,x1,y1, rx,ry,rw,rh, expect, 说明)
    (0, 0, 10, 0, 5, -1, 2, 2, True, '水平线穿过矩形中部 → 相交'),
    (0, 0, 10, 0, 5, 5, 2, 2, False, '水平线在矩形下方 → 不相交（负控制）'),
    (0, 0, 10, 10, 4, 4, 2, 2, True, '对角线穿过矩形角 → 相交'),
    (0, 0, 10, 0, 20, 0, 5, 5, False, '线段整体在矩形左侧 → 不相交（负控制）'),
    (0, 0, 100, 0, 40, 0, 20, 10, False, '线段沿矩形上边界滑 → 只点/线接触不算撞'),
    (0, 0, 100, 0, 40, -5, 20, 10, True, '线段 y=0 落在矩形 y∈[-5,5) 内部 → 相交'),
    (0, 0, 0, 100, 5, 5, 10, 10, False, '竖直线在矩形左侧 → 不相交（负控制）'),
    (0, 0, 0, 100, -5, 5, 10, 10, True, '竖直线穿过矩形 → 相交'),
]
for (a, b, c, d, rx, ry, rw, rh, exp, desc) in ANCHORS:
    got = bool(F(a, b, c, d, rx, ry, rw, rh))
    ok = (got == exp)
    if not ok:
        fails.append(desc)
    print('  [%s] %-40s 期望=%-5s 实得=%-5s'
          % ('PASS' if ok else 'FAIL', desc, exp, got))


def ref(x0, y0, x1, y1, rx, ry, rw, rh, res=0.05):
    """参考真值：0.05px 极密采样，点落在矩形**内部**（开区间）即算相交。

    开区间与 `blocks_at()` 的 `(bx+bw > ox) and (bx < ox+ow)` 同语义。
    """
    d = math.hypot(x1 - x0, y1 - y0)
    n = max(1, int(d / res))
    for i in range(n + 1):
        t = i / float(n)
        px = x0 + (x1 - x0) * t
        py = y0 + (y1 - y0) * t
        if rx < px < rx + rw and ry < py < ry + rh:
            return True
    return False


print()
print('=' * 70)
print('② 随机对拍（3000 组）')
print('=' * 70)
random.seed(51)
miss = 0            # 解析漏判（不可接受）
over = 0            # 解析多判（采样漏判 —— 解析更严，可接受）
agree = 0
worst = []
for _ in range(3000):
    x0 = random.uniform(0, 200)
    y0 = random.uniform(0, 200)
    x1 = x0 + random.uniform(-60, 60)
    y1 = y0 + random.uniform(-60, 60)
    rx = random.uniform(0, 200)
    ry = random.uniform(0, 200)
    rw = random.uniform(1, 40)
    rh = random.uniform(1, 40)
    g = bool(F(x0, y0, x1, y1, rx, ry, rw, rh))
    r = ref(x0, y0, x1, y1, rx, ry, rw, rh)
    if g == r:
        agree += 1
    elif g and not r:
        over += 1
        if len(worst) < 3:
            worst.append(('解析撞/采样不撞', round(x0, 1), round(y0, 1),
                          round(x1, 1), round(y1, 1), rx, ry, rw, rh))
    else:
        miss += 1
        if len(worst) < 3:
            worst.append(('★解析漏判', round(x0, 1), round(y0, 1),
                          round(x1, 1), round(y1, 1), rx, ry, rw, rh))
print('一致 %d / 3000' % agree)
print('解析多说"撞"（采样漏判，可接受）: %d' % over)
print('★解析漏判（**必须为 0**）        : %d' % miss)
for w in worst:
    print('   ', w)
if miss:
    fails.append('随机对拍出现解析漏判 %d 例' % miss)


def my_blocks(obstacles, x, y, bw=SW.PLAYER_BBOX_W, bh=SW.PLAYER_BBOX_H,
              ox=SW.PLAYER_BBOX_OFF_X, oy=SW.PLAYER_BBOX_OFF_Y):
    """按**几何定义**独立复刻"点-盒重叠"（作参考真值，不看产品实现写）。"""
    bx = x + ox
    by = y + oy
    for r in obstacles:
        rx, ry, rw, rh = r[0], r[1], r[2], r[3]
        if (bx + bw > rx) and (bx < rx + rw) and (by + bh > ry) and (by < ry + rh):
            return True
    return False


def ref_clear(obstacles, x0, y0, x1, y1, res=0.02):
    """参考真值：0.02px 极密采样"盒是否撞"。"""
    d = math.hypot(x1 - x0, y1 - y0)
    n = max(1, int(d / res))
    for i in range(n + 1):
        t = i / float(n)
        if my_blocks(obstacles, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t):
            return False
    return True


print()
print('=' * 70)
print('③ `_segment_clear` 对拍（vs 独立点-盒密采样参考）—— 抓"漏盒尺寸"这类错')
print('=' * 70)
random.seed(511)
n_over = n_strict = n_agree3 = 0
for _ in range(400):
    obs = []
    for _k in range(random.randint(1, 6)):
        obs.append((round(random.uniform(-20, 200), 1),
                    round(random.uniform(-20, 200), 1),
                    round(random.uniform(5, 60), 1),
                    round(random.uniform(5, 60), 1), 'solid'))
    x0 = random.uniform(0, 150)
    y0 = random.uniform(0, 150)
    x1 = x0 + random.uniform(-50, 50)
    y1 = y0 + random.uniform(-50, 50)
    g = bool(SW._segment_clear(obs, x0, y0, x1, y1, SW.PLAYER_BBOX_W,
                               SW.PLAYER_BBOX_H, SW.GRID_STEP))
    r = ref_clear(obs, x0, y0, x1, y1)
    if g == r:
        n_agree3 += 1
    elif g and not r:
        n_over += 1          # 产品说"可走"、参考说"撞" ⇒ ★漏判（不可接受）
    else:
        n_strict += 1        # 产品说"撞"、参考说"可走" ⇒ 参考采样漏 ⇒ 可接受
print('一致 %d / 400' % n_agree3)
print('★产品漏判（说可走、实际撞）: %d（**必须为 0**）' % n_over)
print('产品更严（说撞、实际可走）  : %d（参考采样漏判，方向安全）' % n_strict)
if n_over:
    fails.append('_segment_clear 对拍漏判 %d 例' % n_over)

print()
print('=' * 70)
if fails:
    print('结论：FAIL %d 项 %s' % (len(fails), fails))
    sys.exit(1)
print('结论：全 PASS（锚点 %d 组 + 对拍 3000 组）' % len(ANCHORS))

# -*- coding: utf-8 -*-
"""探针 22 号：真实鼠标轨迹里"主轴翻转"有多常见（C 缺陷严重性取证）。

思路
----
C 缺陷成立的前提是：**相邻两次采样点的主轴方向会频繁翻转**。
如果不翻转（人总是画很平的横线/很直的竖线），C 就是个理论缺陷、优先级低。
如果频繁翻转（人手抖动），C 就是"抚摸基本不工作"的高优先级缺陷。

取证方式（不靠想象）：
  用几条**典型撸猫轨迹**做数值模拟 —— 圆弧往返 + 抖动 + 圆弧往返，
  采样率按 Windows 鼠标事件约 60~125 Hz、人手移动速度约 300~800 px/s 折算，
  逐点算出 (dx,dy)，统计相邻步的主轴翻转率，并把序列喂给**产品原函数**
  （从 main.py 抽取，同探针 21）看真实 direction_changes。

注意：这是**数值模拟**，不是真机采样。所以本探针的结论只用于
"判断缺陷优先级"，不作为"真机实测"。真机结论另见报告。
"""
import io
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

with io.open(MAIN, 'r', encoding='utf-8', errors='replace') as f:
    LINES = f.read().splitlines()


def extract_block(start_ln, end_ln):
    chunk = LINES[start_ln - 1:end_ln]
    indents = [len(l) - len(l.lstrip()) for l in chunk if l.strip()]
    base = min(indents) if indents else 0
    return '\n'.join(l[base:] if len(l) >= base else l for l in chunk)


block = extract_block(5367, 5389)
FUNC_SRC = (
    'def direction_changes_of(history):\n'
    '    class _S:\n'
    '        pass\n'
    '    self = _S()\n'
    "    self._pet_detection_state = {'movement_history': history}\n"
    '    direction_changes = 0\n'
    + '\n'.join('    ' + l for l in block.splitlines()[1:]) + '\n'
    '    return direction_changes\n'
)
ns = {}
exec(compile(FUNC_SRC, '<extracted-from-main.py>', 'exec'), ns)
dc_of = ns['direction_changes_of']


def stats(points, label):
    """points: [(x,y)] 原始轨迹。按产品口径（相邻差、3<d<50 才入历史、保留最近15）统计。"""
    hist = []          # 产品同口径的 movement_history
    flips = 0
    steps = 0
    prev_dir = None
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        d = math.hypot(dx, dy)
        if not (3 < d < 50):
            continue
        steps += 1
        cur_dir = 'horizontal' if abs(dx) > abs(dy) else 'vertical'
        if prev_dir is not None and cur_dir != prev_dir:
            flips += 1
        prev_dir = cur_dir
        hist.append((dx, dy, d))
        if len(hist) > 15:
            hist.pop(0)

    # 产品是"每次移动都整段重算"，这里取"历史攒够 5 条之后"的典型值
    dc = dc_of(hist) if len(hist) >= 5 else 0
    rate = (flips / steps * 100.0) if steps else 0.0
    print('  %-34s 步数=%-4d 主轴翻转=%-4d (%.0f%%)  末段 direction_changes=%d  %s'
          % (label, steps, flips, rate, dc,
             '[达阈值≥2 ✓]' if dc >= 2 else '[未达阈值 ✗ 抚摸不触发]'))
    return dc, rate


print('=' * 72)
print('探针 22：真实鼠标轨迹主轴翻转率 & 产品判据实测（数值模拟）')
print('=' * 72)
print()
print('模拟参数：采样间隔 ~8ms（约 125Hz），人手速度 ~500 px/s ⇒ 每步约 4 px')
print('（产品入历史门槛 3 < distance < 50，故每步都入历史）')
print()

random.seed(20260922)
results = []

# --- 轨迹 1：教科书式纯水平往返（人手理想化）---
pts = []
for cycle in range(3):
    for t in range(20):
        x = 100 + 60 * math.sin(t / 20 * math.pi * 2 + (cycle * 0))
        pts.append((x, 200))
    for t in range(20):
        x = 100 + 60 * math.sin(t / 20 * math.pi * 2 + math.pi)
        pts.append((x, 200))
results.append(('T1 纯水平往返（理想）', stats(pts, 'T1 纯水平往返（理想）')))

# --- 轨迹 2：纯水平往返 + 人手垂直抖动（±1px）---
pts2 = []
for cycle in range(3):
    for t in range(20):
        x = 100 + 60 * math.sin(t / 20 * math.pi * 2)
        pts2.append((x, 200 + random.uniform(-1.2, 1.2)))
    for t in range(20):
        x = 100 + 60 * math.sin(t / 20 * math.pi * 2 + math.pi)
        pts2.append((x, 200 + random.uniform(-1.2, 1.2)))
results.append(('T2 水平往返+抖动 ±1.2px', stats(pts2, 'T2 水平往返+抖动 ±1.2px')))

# --- 轨迹 3：沿躯干上下抚摸（垂直往返）+ 水平抖动 ---
pts3 = []
for cycle in range(3):
    for t in range(20):
        y = 200 + 50 * math.sin(t / 20 * math.pi * 2)
        pts3.append((300 + random.uniform(-1.2, 1.2), y))
    for t in range(20):
        y = 200 + 50 * math.sin(t / 20 * math.pi * 2 + math.pi)
        pts3.append((300 + random.uniform(-1.2, 1.2), y))
results.append(('T3 垂直往返+抖动 ±1.2px', stats(pts3, 'T3 垂直往返+抖动 ±1.2px')))

# --- 轨迹 4：人手自然弧线（圆头圆脑的来回撸，两个轴都在动）---
pts4 = []
for cycle in range(3):
    for t in range(40):
        ang = t / 40 * math.pi * 2
        x = 300 + 50 * math.sin(ang)
        y = 200 + 18 * (1 - math.cos(ang))     # 弧线本身带 18px 的纵向起伏
        pts4.append((x, y))
results.append(('T4 自然弧线撸（横向主+纵向副）', stats(pts4, 'T4 自然弧线撸（横向主+纵向副）')))

# --- 轨迹 5：自然弧线 + 抖动（最接近真人）---
pts5 = []
for cycle in range(3):
    for t in range(40):
        ang = t / 40 * math.pi * 2
        x = 300 + 50 * math.sin(ang) + random.uniform(-1.0, 1.0)
        y = 200 + 18 * (1 - math.cos(ang)) + random.uniform(-1.0, 1.0)
        pts5.append((x, y))
results.append(('T5 自然弧线+抖动（最像真人）', stats(pts5, 'T5 自然弧线+抖动（最像真人）')))

# --- 轨迹 6：慢慢撸（速度更慢，每步约 3.5px，抖动占比更大）---
pts6 = []
for cycle in range(3):
    for t in range(30):
        x = 300 + 45 * math.sin(t / 30 * math.pi * 2) + random.uniform(-1.5, 1.5)
        y = 200 + random.uniform(-1.5, 1.5)
        pts6.append((x, y))
results.append(('T6 慢速水平撸+抖动 ±1.5', stats(pts6, 'T6 慢速水平撸+抖动 ±1.5')))

print()
print('-' * 72)
print('汇总：产品 direction_changes 是否达阈值（≥2 才触发抚摸）')
print('-' * 72)
ok = 0
for label, (dc, rate) in results:
    flag = 'OK  ' if dc >= 2 else 'MISS'
    print('  [%s] %-34s dc=%d  翻转率=%.0f%%' % (flag, label, dc, rate))
    if dc >= 2:
        ok += 1
print()
print('  达标 %d / %d' % (ok, len(results)))
print()
print('SUITE_SUMMARY pass=%d fail=%d' % (ok, len(results) - ok))
sys.exit(0)

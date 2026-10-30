# -*- coding: utf-8 -*-
u"""第117轮调研 ①：看清 `niko_door_portal.png` 到底是什么颜色结构。

用户口径（逐字，10-18）：
「oneshot 用最后 niko 回家走的那道门，但**颜色变成黑光**，然后 niko 的家还是用
 他那道，ut 的门就用你的那个就好，对了**大一点都**」

要做的变体 = 同一张「回家光门」，把**光的颜色**从原色改成「黑光」。
⇒ 动手前必须先知道：这张图里"光"是哪些像素、"底"是哪些像素，
   否则"变黑光"很容易做成一整块黑（正是第116轮用户报的「黑底」）。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OBJS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs')

try:
    from PIL import Image
except Exception as e:                                        # noqa: BLE001
    sys.stdout.write('PIL 不可用: %r\n' % (e,))
    sys.exit(2)

NAME = 'niko_door_portal.png'
p = os.path.join(OBJS, NAME)
im = Image.open(p).convert('RGBA')
w, h = im.size
px = list(im.getdata())
n = float(len(px))
sys.stdout.write('== %s ==\n' % NAME)
sys.stdout.write('尺寸 %dx%d  像素 %d  字节 %d\n' % (w, h, len(px), os.path.getsize(p)))

tot_a0 = sum(1 for *_, a in px if a == 0)
tot_a255 = sum(1 for *_, a in px if a == 255)
sys.stdout.write('alpha==0 : %d (%.1f%%)\nalpha==255: %d (%.1f%%)\n'
                 % (tot_a0, 100.0 * tot_a0 / n, tot_a255, 100.0 * tot_a255 / n))

# 不透明像素的亮度分布（看"光"在哪一档）
vis = [(r, g, b, a) for (r, g, b, a) in px if a > 0]
lum = [0.299 * r + 0.587 * g + 0.114 * b for (r, g, b, a) in vis]
buckets = [(0, 26), (27, 60), (61, 110), (111, 170), (171, 220), (221, 255)]
sys.stdout.write('\n-- 可见像素亮度分档（n=%d）--\n' % len(vis))
for lo, hi in buckets:
    c = sum(1 for v in lum if lo <= v <= hi)
    sys.stdout.write('  %3d..%-3d : %6d (%.1f%% 可见 / %.1f%% 全图)\n'
                     % (lo, hi, c, 100.0 * c / max(1, len(vis)), 100.0 * c / n))

# 最亮的那些像素长什么样（"光"的本体色）
top = sorted(vis, key=lambda t: -(0.299 * t[0] + 0.587 * t[1] + 0.114 * t[2]))[:12]
sys.stdout.write('\n-- 最亮 12 个像素 --\n')
for t in top:
    sys.stdout.write('  rgba=%r\n' % (t,))
# 最不透明 + 最亮
op = [t for t in vis if t[3] >= 250]
if op:
    from collections import Counter
    cnt = Counter((r // 16 * 16, g // 16 * 16, b // 16 * 16) for (r, g, b, a) in op)
    sys.stdout.write('\n-- 不透明像素的颜色主档（RGB 量化 16 档，前 8）--\n')
    for (r, g, b), c in cnt.most_common(8):
        sys.stdout.write('  rgb(%3d,%3d,%3d) : %6d (%.1f%% 不透明)\n'
                         % (r, g, b, c, 100.0 * c / max(1, len(op))))

# 四角与中心的采样
sys.stdout.write('\n-- 采样 --\n')
for (x, y, tag) in ((0, 0, '左上'), (w - 1, 0, '右上'), (0, h - 1, '左下'),
                    (w - 1, h - 1, '右下'), (w // 2, h // 2, '中心'),
                    (w // 2, 0, '上中'), (w // 2, h - 1, '下中')):
    sys.stdout.write('  %s (%d,%d) = %r\n' % (tag, x, y, im.getpixel((x, y))))

# 一张放大的缩略（ASCII）便于看形状：按 alpha 与亮度画
sys.stdout.write('\n-- 形状（每 8x8 块取均值；# 不透明亮 / + 半透 / . 全透）--\n')
for by in range(0, h, 8):
    line = []
    for bx in range(0, w, 8):
        sx = min(w, bx + 8)
        sy = min(h, by + 8)
        box = im.crop((bx, by, sx, sy)).getdata()
        a_avg = sum(t[3] for t in box) / float(len(box))
        l_avg = sum(0.299 * t[0] + 0.587 * t[1] + 0.114 * t[2] for t in box) / float(len(box))
        if a_avg < 12:
            line.append('.')
        elif a_avg < 128:
            line.append('+')
        else:
            line.append('#' if l_avg < 120 else '@')
    sys.stdout.write('  ' + ''.join(line) + '\n')

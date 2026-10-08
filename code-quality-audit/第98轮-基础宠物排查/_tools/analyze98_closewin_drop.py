# -*- coding: utf-8 -*-
u"""第98轮：**关窗坠落**几何对账（吃 `rec97_moves.txt`，逐次移动粒度）。

服务用户口径：
    「他下坠也不是直接下坠到屏幕底下啊，而且不是关掉窗口一瞬间就摔扁，
      你总得摔到桌面上才能扁吧，是那种偏俯视2D游戏似的效果，不是侧视2D」

为什么读 `moves` 而不是 `frames.csv`：抓屏周期 500 ms，一次坠落 ~1 s ⇒ 只有 2 个采样点，
**落点采不到**。`moves` 是劫持 `window.move` 写的 ⇒ 每次位置变化一行（≈30 fps 粒度）。

输出每段：
  · 起点 (x,y) / 落点 (x,y) / 落点 `y+h` 与屏高的关系（贴屏幕底？）
  · 下落耗时（秒）与采样点个数
  · 期间动画序列（`fall_mad` 是否被顶掉）
另读 `rec98_block_probe.txt` 输出 `_fall_phase` 的切换时刻。

用法：python analyze98_closewin_drop.py [evidence_dir]
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EVD = os.path.normpath(os.path.join(HERE, '..', '_evidence', 'run_inj_closewin'))
if len(sys.argv) > 1:
    EVD = sys.argv[1]
SCREEN_H = 1600      # 本机 2560x1600（`rec97_meta.txt` 的"屏幕"行）

# ★★ 只匹配**稳定前缀**。首版把 `tgt=([^\s]+)` 也写进正则 —— 而 `rec97_moves.txt`
#   的 `tgt=%r` 对 Qt 对象会输出 `<PyQt5.QtCore.QPoint object at 0x...>`，
#   **含空格** ⇒ 整行匹配失败 ⇒ `mv` 为空 ⇒ 脚本淡定地报"坠落段 0 段"
#   （"判据也是被测物"的又一例：数据全在，是我没读到）。
MOV = re.compile(r"t=([\d.]+) x=(-?\d+) y=(-?\d+) anim='([^']*)'")
SZC = re.compile(r' sz=(\d+)x(\d+)')
BLK = re.compile(
    r"t=([\d.]+) .*?wx=(-?\d+) wy=(-?\d+) ww=(\d+) wh=(\d+) .*?"
    r"phase=(\S+) freason=(\S+) fspeed=(\S+)")


def read(p):
    return io.open(p, encoding='utf-8', newline='').read().split('\n')


print('=' * 78)
print(u'# 第98轮：关窗坠落几何对账（EVD=%s）' % EVD)
print('=' * 78)

# ---------------- moves：精确落点 ----------------
mv = []
for ln in read(os.path.join(EVD, 'rec97_moves.txt')):
    m = MOV.search(ln)
    if m:
        _s = SZC.search(ln)
        _h = int(_s.group(2)) if _s else 0
        mv.append((float(m.group(1)), int(m.group(2)), int(m.group(3)),
                   m.group(4), '', '', _h, _h))
mv.sort(key=lambda r: r[0])

# 切"坠落段"：y 单调不减、且总增幅 > 40px 的连续串
#   ⚠️ 阈值原来是 200px —— 那是按"掉到屏幕底"设的。改成偏俯视落点后一次坠落只有
#      几十像素（落差 10 ⇒ 64px），阈值 200 会把**全部**真实坠落段滤掉、报"0 段"。
#      这正是"判据跟着被测口径走"的一个小例子。
SEG_MIN_DY = 40
segs = []
cur = None
for r in mv:
    t, x, y = r[0], r[1], r[2]
    if cur is None:
        cur = [r]
        continue
    if y >= cur[-1][2] - 2 and (y - cur[0][2]) <= 4000:
        cur.append(r)
    else:
        if cur[-1][2] - cur[0][2] > SEG_MIN_DY:
            segs.append(cur)
        cur = [r]
if cur is not None and cur[-1][2] - cur[0][2] > SEG_MIN_DY:
    segs.append(cur)

print('')
print(u'-- 坠落段（moves 粒度）共 %d 段' % len(segs))
for k, s in enumerate(segs, 1):
    t0, t1 = s[0][0], s[-1][0]
    y0, y1 = s[0][2], s[-1][2]
    x0, x1 = s[0][1], s[-1][1]
    wh = s[-1][7]
    anims = []
    for r in s:
        if not anims or anims[-1] != r[3]:
            anims.append(r[3])
    print('  段#%d  t=%.2f..%.2f (%.2fs, %d 点)' % (k, t0, t1, t1 - t0, len(s)))
    print('       x %d -> %d (dx=%+d)   y %d -> %d (dy=%+d)'
          % (x0, x1, x1 - x0, y0, y1, y1 - y0))
    _bot = y1 + wh
    _note = (u'<== 贴屏底（**侧视**口径，改前就是这样）' if _bot >= SCREEN_H
             else u'（远未到屏底 ⇒ **偏俯视**落点）')
    print(u'       落点底边 = y+h = %d  %s' % (_bot, _note))
    print(u'       动画序列 = %s' % anims)
    # 每点之间最大单步位移（看是否有"一帧掉上千像素"）
    steps = [s[i + 1][2] - s[i][2] for i in range(len(s) - 1)]
    if steps:
        print(u'       单点 max dy = %d px（%d 点共 %d px）'
              % (max(steps), len(steps), y1 - y0))

# ---------------- block probe：phase 切换 ----------------
print('')
print(u'-- `_fall_phase` 切换（block probe，500 ms 粒度）')
prev = None
for ln in read(os.path.join(EVD, 'rec98_block_probe.txt')):
    m = BLK.search(ln)
    if not m:
        continue
    t, wx, wy, ww, wh, phase, freason, fspeed = m.groups()
    key = (phase, freason)
    if key != prev:
        print('      t=%-7s phase=%-12s freason=%-16s wy=%-5s wh=%-4s fspeed=%s'
              % (t, phase, freason, wy, wh, fspeed))
        prev = key
print('')
print('#' * 78)
print(u'# 判读：`落点底边==屏高` ⇒ 现状把 z 直接映射到屏幕 y（**侧视**）；')
print(u'#       `单点 max dy` 很大 ⇒ 离散积分一步跨过去，用户看到的是"瞬移式下坠"。')
print('#' * 78)

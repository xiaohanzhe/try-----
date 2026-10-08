# -*- coding: utf-8 -*-
u"""第98轮：重力坠落**几何对账** —— 落点 y 到底在哪、掉了几帧/几秒。

用户口径（第98轮，本脚本服务的那条指令）：
    「他下坠也不是直接下坠到屏幕底下啊，而且不是关掉窗口一瞬间就摔扁，
      你总得摔到桌面上才能扁吧，是那种偏俯视2D游戏似的效果，不是侧视2D」

要回答的问题（只看数据能答的部分）：
  ① 坠落**终点**的 `wy` 是不是 = `屏幕高 - 窗口高`（= 贴屏幕最底边）？
     ⇒ 是 ⇒ 现状 = 侧视"掉到屏幕底"，与"偏俯视2D"不符（用户观点）。
  ② 从起点 `wy` 到终点 `wy` 花了多少**帧 / 墙钟秒**？
     ⇒ 太短 ⇒ 用户感知为"关窗一瞬间就摔扁"。
  ③ 落地后立刻进的是什么动画（splat 家族 or land/idle）？

本脚本**只读 CSV**，不改产品、不产生副作用。
`wy + wh` = 宠物窗口**底边**；贴屏幕底边时 `wy + wh == 屏高`。

用法：
    python analyze98_drop_geometry.py [--screen-h 1600] [run ...]
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EVD = os.path.normpath(os.path.join(HERE, '..', '_evidence'))
SCREEN_H = 1600
TMP = 'E:\\Download\\_tmp'

DEFAULT = ['run_inj_gfall_before', 'run_inj_gfall_after',
           'run_inj_gfall_after2', 'run_natural', 'run_natural_postfix']


def load(name):
    p = os.path.join(EVD, name, 'rec97_frames.csv')
    if not os.path.exists(p):
        return None
    # ★ 字节忠实读取：rec97 写 CSV 用默认 '\\r\\n'，若按通用换行读会把表头末项
    #   读成 'spdy\\r'（第96轮 csv 双坑之一）。这里 newline='' 且 split('\\n') 后
    #   再 rstrip('\\r') 兜一层。
    txt = io.open(p, encoding='utf-8', newline='').read()
    lines = txt.split('\n')
    hdr = [h.strip() for h in lines[0].split(',')]
    rows = []
    for x in lines[1:]:
        if not x.strip():
            continue
        vals = [v.rstrip('\r') for v in x.split(',')]
        rows.append(dict(zip(hdr, vals)))
    return rows


def segs_of(rows, key='gfall'):
    idx = [int(r['frame']) for r in rows if r.get(key) == 'True']
    segs = []
    for i in idx:
        if segs and i == segs[-1][1] + 1:
            segs[-1][1] = i
        else:
            segs.append([i, i])
    return segs


def by_frame(rows):
    return dict((int(r['frame']), r) for r in rows)


def report(name):
    rows = load(name)
    if rows is None:
        print('  !! 缺 %s/rec97_frames.csv' % name)
        return
    fm = by_frame(rows)
    segs = segs_of(rows)
    print('')
    print('-- %s   帧=%d' % (name, len(rows)))
    if not segs:
        print('     重力坠落帧 = 0（本次没触发）')
        return
    floor_y = SCREEN_H - 94  # 只用来说明口径；每段用自身 wh 现算
    print('     (屏幕高=%d；贴底判据 wy+wh==%d)'
          % (SCREEN_H, SCREEN_H))
    for a, b in segs:
        ra, rb = fm[a], fm[b]
        wy0, wy1 = int(ra['wy']), int(rb['wy'])
        wh1 = int(rb['wh'])
        dt = float(rb['t']) - float(ra['t'])
        n = b - a + 1
        # 段后 3 帧的动画（落地表现）
        after = []
        for k in range(b + 1, b + 6):
            if k in fm:
                after.append('%s@f%d(%s)' % (fm[k]['anim'], k, fm[k]['gfall']))
        anims = sorted(set(r['anim'] for r in rows if a <= int(r['frame']) <= b))
        print('     f%03d-f%03d  帧=%2d  %5.2fs  wy %5d -> %5d (dy=%+d)  底边=%d%s'
              % (a, b, n, dt, wy0, wy1, wy1 - wy0, wy1 + wh1,
                 '  <== 贴屏幕底' if wy1 + wh1 >= SCREEN_H else ''))
        print('         动画 = %s' % anims)
        print('         落地后 = %s' % (', '.join(after) or '(无后续帧)'))


args = [a for a in sys.argv[1:]]
runs = []
i = 0
while i < len(args):
    if args[i] == '--screen-h':
        SCREEN_H = int(args[i + 1]); i += 2
    else:
        runs.append(args[i]); i += 1
if not runs:
    runs = DEFAULT

print('=' * 78)
print(u'# 第98轮：重力坠落几何对账（EVD=%s）' % EVD)
print('=' * 78)
for r in runs:
    report(r)
print('')
print('#' * 78)
print(u'# 判读：`底边==屏高` 的段 = 落在**屏幕最底边**（侧视口径）；')
print(u'#       `dy` 很小 / `秒` 很短 = 用户说的"一瞬间就摔扁"。')
print('#' * 78)

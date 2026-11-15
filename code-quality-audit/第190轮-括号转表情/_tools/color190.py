# -*- coding: utf-8 -*-
u"""第190轮 · 判定"导出的贴图页到底有没有颜色"。

为什么要单独做这一步
--------------------
用户 2026-11-15 提出关键质疑：「有没有可能有些原版头像就是没颜色只是黑白呢」

这一问直接打中我的旧判据：我原先拿「裁出的图颜色数 ≤ 2 ⇒ 蒙版 ⇒ 解码失败」当排除闸。
但这条闸的**前提**是"原版头像一定有颜色"。若原作本来就画了黑白/单色头像
（UT 的 Sans 是白骷髅、Napstablook 是灰幽灵；Deltarune / OneShot 也有大量单色图），
这条闸就会把**正确的黑白图判成解码失败** —— 正是我记忆里的「判据过窄 = 误报」。

★ 所以本脚本不再只数颜色数，而是把"颜色数"和**结构证据**分开看：

    现象                           结论
    ------------------------------  --------------------------------------
    出图是彩条/色块噪声             解码真的错了
    出图是轮廓清晰的单色角色        原版就是单色，**旧判据错了**

    颜色数这个指标**区分不了**这两者（噪声也"颜色很多"，蒙版和正确单色图都是 1~2 色）。
    因此额外算三项结构量，它们对"噪声 vs 真实图形"敏感：

      · 不透明像素占比  opaque%   —— 蒙版/噪声常接近 0 或接近 100
      · 相邻像素同色率  flat%     —— 真实像素画是大片平涂（通常 > 70%）；噪声接近 0
      · 4-邻域连通块数  comp      —— 真实图形是少数大块；噪声是海量碎片

    再加一条**最硬的**：把可疑页存成 PNG 让肉眼确认（ViewImage），
    因为"看起来对不对"最终只能由人判，指标只用来决定"先看哪几张"。

用法
----
    python color190.py                  # 全量统计 + 挑出可疑页
    python color190.py --tag hy --top 6 # 只打前 6 个可疑页的路径
"""
import io
import os
import sys
import collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from PIL import Image  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
# 页面 PNG 在工作区（不在仓库里，避免几百 MB 二进制进 git）
PAGE_DIRS = [u'D:\\_tmp190\\hy_export_pages190\\pages',
             u'D:\\_tmp190\\ut_export_pages190\\pages',
             u'D:\\_tmp190\\ot_export_pages190\\pages']


def arg(key, default=None):
    a = sys.argv[1:]
    if key not in a:
        return default
    i = a.index(key)
    return a[i + 1] if i + 1 < len(a) else default


def stats(path):
    """返回 (w, h, ncolor, opaque_pct, flat_pct, comp_est)。"""
    im = Image.open(path).convert('RGBA')
    w, h = im.size
    px = list(im.getdata())

    ncol = len(set(px))
    n = float(len(px))
    opaque = sum(1 for p in px if p[3] > 16)
    opaque_pct = 100.0 * opaque / n

    # flat%：水平相邻同色率（真实像素画大片平涂 ⇒ 高；噪声 ⇒ 低）
    flat = 0
    tot = 0
    for y in range(h):
        row = px[y * w:(y + 1) * w]
        for x in range(1, w):
            tot += 1
            if row[x] == row[x - 1]:
                flat += 1
    flat_pct = 100.0 * flat / tot if tot else 0.0

    # comp_est：4-邻域连通块数（只在缩到 <=192 的网格上算，够判"碎片 vs 大块"）
    step = max(1, int(max(w, h) // 192))
    gw, gh = (w + step - 1) // step, (h + step - 1) // step
    seen = bytearray(gw * gh)
    grid = [None] * (gw * gh)
    for gy in range(gh):
        for gx in range(gw):
            grid[gy * gw + gx] = px[(gy * step) * w + (gx * step)]
    comp = 0
    for i in range(gw * gh):
        if seen[i]:
            continue
        if grid[i][3] <= 16:      # 透明不算块
            seen[i] = 1
            continue
        comp += 1
        col = grid[i]
        stack = [i]
        seen[i] = 1
        while stack:
            j = stack.pop()
            jy, jx = divmod(j, gw)
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ny, nx = jy + dy, jx + dx
                if 0 <= ny < gh and 0 <= nx < gw:
                    k = ny * gw + nx
                    if not seen[k] and grid[k] == col:
                        seen[k] = 1
                        stack.append(k)
    return w, h, ncol, opaque_pct, flat_pct, comp


def main():
    tag = arg('--tag', 'hy')
    top = int(arg('--top', '0'))
    fn = os.path.join(EV, 'pages', tag + '.tsv')
    if not os.path.isfile(fn):
        print('[停手] 没有清单：%s' % fn)
        return 2

    base = None
    for d in PAGE_DIRS:
        if os.path.isdir(d):
            base = d
            break
    if not base:
        print('[停手] 找不到页面 PNG 目录')
        return 2

    rows = [l.split('\t') for l in io.open(fn, encoding='utf-8').read().splitlines()[1:] if l.strip()]
    print('[清单] %s  %d 页' % (fn, len(rows)))
    print('[目录] %s' % base)
    print('')
    print('%-5s %-11s %-6s %-7s %-7s %-6s %s' %
          ('idx', 'size', 'colors', 'opaque%', 'flat%', 'comp', '判定'))

    buckets = collections.Counter()
    suspicious = []
    for r in rows:
        idx = int(r[0])
        p = os.path.join(base, 'p%03d.png' % idx)
        if not os.path.isfile(p):
            continue
        w, h, ncol, op, fl, cp = stats(p)
        # ★ 判定口径（先宽松，最后仍要看图确认；这里只做"分级"不做"定罪"）
        if op < 0.5:
            verdict = '全透明(可疑)'
        elif fl < 40:
            verdict = '噪声(可疑)'
        elif ncol <= 2:
            verdict = '单色(待肉眼看)'
        else:
            verdict = '彩色'
        buckets[verdict] += 1
        if verdict != '彩色':
            suspicious.append((idx, p, verdict, ncol, op, fl, cp))
        if top == 0 or idx < top:
            print('%-5d %-11s %-6d %-7.1f %-7.1f %-6d %s'
                  % (idx, '%dx%d' % (w, h), ncol, op, fl, cp, verdict))

    print('')
    print('[汇总] ' + '  '.join('%s=%d' % (k, v) for k, v in sorted(buckets.items())))
    if suspicious:
        print('[需肉眼确认的前 8 个]')
        for s in suspicious[:8]:
            print('   %s  %s  colors=%d opaque=%.1f%% flat=%.1f%%' % (s[1], s[2], s[3], s[4], s[5]))
    return 0


if __name__ == '__main__':
    sys.exit(main())

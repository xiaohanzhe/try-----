# -*- coding: utf-8 -*-
"""第101轮诊断：map63 为何"铺了 2806 块瓦片却仍是单色"。"""
import importlib.util
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TOOLS100 = os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景', '_tools')


def load_mod(p, n):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


BG = load_mod(os.path.join(TOOLS100, 'os_bg100.py'), 'os_bg100')

for N in (63,):
    mp = os.path.join(BG.MAPS, 'map%d.tmx' % N)
    m = BG.parse_map(mp)
    print('=== map%d: %dx%d tiles of %dx%d => %s px' %
          (N, m['w'], m['h'], m['tw'], m['th'], (m['w'] * m['tw'], m['h'] * m['th'])))
    print('tilesets:', m['tilesets'])
    for lname, gs in m['layers']:
        c = Counter(g for g in gs if g > 0)
        print('  layer %-16s filled=%-6d unique_gid=%-4d top=%s'
              % (lname, sum(1 for g in gs if g > 0), len(c), c.most_common(6)))

    colors = BG.load_map_colors()
    im, used, mm = BG.render(mp, colors)
    print('render: size=%s used=%d extrema=%s' % (im.size, used, im.convert('RGBA').getextrema()))
    print('base color from mapColors =', colors.get(N))

    for fg, src in m['tilesets']:
        tsx = os.path.normpath(os.path.join(BG.MAPS, src))
        t = BG.parse_tsx(tsx)
        ip = BG.resolve_img(os.path.dirname(tsx), t['img'])
        g = BG.xnb_rgba(ip) if ip else None
        print('  tileset %-24s fg=%-4d cols=%-3d count=%-5d img=%s'
              % (os.path.basename(src), fg, t['columns'], t['tilecount'],
                 os.path.basename(ip) if ip else '?'))
        if g is not None:
            rg = g.convert('RGBA')
            print('     atlas size=%s extrema=%s' % (rg.size, rg.getextrema()))
            # 看这张图集里到底有多少种颜色（alpha 是否全 0）
            cols = Counter(rg.getdata())
            print('     atlas 颜色种类=%d 最常见 3 种=%s'
                  % (len(cols), cols.most_common(3)))
        else:
            print('     !! 图集解不开（xnb=None）')

# -*- coding: utf-8 -*-
"""第196轮 · 单帧放大查看（10 倍最近邻），用于判断"这张到底是谁"。

用法：python zoom196.py susie/anim/angry_up_0.png susie/down_0.png
"""
from __future__ import print_function

import io
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
DROP = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites', 'dr')
EVID = os.path.join(ROUND, '_evidence')
K = 10


def main(argv):
    if not argv:
        print('用法: zoom196.py <相对 dr/ 的路径> [...]')
        return 2
    items = [(a, os.path.join(DROP, a.replace('/', os.sep))) for a in argv]
    bad = [a for a, p in items if not os.path.isfile(p)]
    if bad:
        print('[FAIL] 不存在: %s' % bad)
        return 2
    ims = []
    for label, p in items:
        im = Image.open(p)
        im.load()
        im = im.convert('RGBA')
        ims.append((label, im, im.size))
    cell = max(i.width for _l, i, _s in ims) * K + 8
    W = len(ims) * cell + 8
    H = cell + 30
    sheet = Image.new('RGB', (W, H), (24, 24, 30))
    draw = ImageDraw.Draw(sheet)
    for i, (label, im, size) in enumerate(ims):
        x = 8 + i * cell
        draw.text((x, 4), label[-28:], fill=(255, 210, 130))
        draw.text((x, 16), '%dx%d' % size, fill=(150, 220, 160))
        big = im.resize((im.width * K, im.height * K), Image.NEAREST)
        # 棋盘格底（看透明区）
        for yy in range(0, big.height, 10):
            for xx in range(0, big.width, 10):
                if (xx // 10 + yy // 10) % 2:
                    draw.rectangle([x + xx, 30 + yy,
                                    x + min(xx + 9, big.width - 1),
                                    30 + min(yy + 9, big.height - 1)],
                                   fill=(38, 38, 46))
        sheet.paste(big.convert('RGB'), (x, 30), big)
    out = os.path.join(EVID, 'zoom196.png')
    sheet.save(out)
    print('[OK] %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

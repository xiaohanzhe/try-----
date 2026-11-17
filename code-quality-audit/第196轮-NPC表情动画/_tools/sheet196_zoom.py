# -*- coding: utf-8 -*-
"""第196轮 · 人工核对图（逐情绪一张，每行一个角色，摊开**所有帧**）。

为什么不用 `pick196.py --sheet` 那一张总图：11 行 × 6 列挤成 618×1282，
每一格只有 96px，看图也看不清"这到底是不是那个人、旁边有没有站第二个人"。
本脚本按情绪分文件，横向摊开所有 (朝向, 帧)，每格 64px，读得清。

★ 这是**人工把关**环节（第191轮教训：自动挑素材一定会错，最终只能看图）。
"""
from __future__ import print_function

import io
import json
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
DROP = os.path.join(PET, 'assets', 'sprites', 'dr')
MAN = os.path.join(DROP, '_npc_anims.json')
FRAMES = os.path.join(DROP, '_npc_frames.json')
EVID = os.path.join(ROUND, '_evidence')

EMOS = ['happy', 'sad', 'angry', 'surprised', 'hurt']
DIRS = ['down', 'left', 'right', 'up']
CELL, PAD, LH = 64, 5, 13


def load_manifest():
    """清单还没落盘时（预演阶段）也能出图：直接从 `_npc_frames.json` + anim 目录推。"""
    if os.path.isfile(MAN):
        with io.open(MAN, 'r', encoding='utf-8') as f:
            return json.load(f).get('characters') or {}
    return None


def main(argv):
    chars = load_manifest()
    if chars is None:
        print('[INFO] 还没有 %s，先跑 pick196.py --write' % MAN)
        return 2

    ids = sorted(chars.keys())
    if not os.path.isdir(EVID):
        os.makedirs(EVID)
    out = []
    for emo in EMOS:
        # 先算每行单元格数自适应
        maxcols = 0
        for cid in ids:
            n = 0
            for dd in DIRS:
                n += len((((chars[cid] or {}).get(emo) or {}).get(dd)) or [])
            maxcols = max(maxcols, n)
        if maxcols == 0:
            print('  [--] %-10s 无帧' % emo)
            continue
        cols = max(1, maxcols)
        W = PAD + (cols + 1) * (CELL + PAD)
        H = PAD + len(ids) * (CELL + PAD + LH) + PAD
        sheet = Image.new('RGB', (W, H), (28, 28, 34))
        draw = ImageDraw.Draw(sheet)
        for c in range(cols):
            draw.text((PAD + (c + 1) * (CELL + PAD), 3), '#%d' % c,
                      fill=(255, 200, 120))
        for r, cid in enumerate(ids):
            y = PAD + r * (CELL + PAD + LH) + LH
            draw.text((PAD, y - LH + 1), cid, fill=(190, 220, 255))
            col = 0
            for dd in DIRS:
                rows = ((((chars[cid] or {}).get(emo) or {}).get(dd)) or [])
                for i, row in enumerate(rows):
                    x = PAD + (col + 1) * (CELL + PAD)
                    draw.rectangle([x, y, x + CELL, y + CELL],
                                   outline=(64, 64, 76))
                    p = os.path.join(DROP, cid, row['f'])
                    try:
                        im = Image.open(p)
                        im.load()
                    except Exception:
                        draw.text((x + 2, y + 24), 'FAIL', fill=(255, 0, 0))
                        col += 1
                        continue
                    k = 2
                    while k > 1 and (im.width * k > CELL - 2
                                     or im.height * k > CELL - 2):
                        k -= 1
                    im = im.resize((max(1, im.width * k), max(1, im.height * k)),
                                   Image.NEAREST)
                    if im.width > CELL - 2 or im.height > CELL - 2:
                        im.thumbnail((CELL - 2, CELL - 2), Image.NEAREST)
                    px = x + (CELL - im.width) // 2
                    py = y + CELL - im.height
                    sheet.paste(im.convert('RGB'), (px, py))
                    draw.text((x + 1, y + CELL - 9),
                              '%s%d %dx%d' % (dd[0].upper(), i, row['w'], row['h']),
                              fill=(120, 220, 140))
                    col += 1
            if col > cols:
                cols = col
        path = os.path.join(EVID, 'sheet196_%s.png' % emo)
        sheet.save(path)
        print('  [OK] %-10s %dx%d → %s' % (emo, W, H, path))
        out.append(path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

# -*- coding: utf-8 -*-
"""第196轮 · 定点比对：把某个角色的「走路帧」与「表情帧」并排放大，人眼确认。

用法：
    python compare196.py rudy susie                 # 用清单里实际选中的帧
    python compare196.py rudy --walk-only
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
DROP = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites', 'dr')
EVID = os.path.join(ROUND, '_evidence')


def load(name):
    with io.open(os.path.join(DROP, name), 'r', encoding='utf-8') as f:
        return json.load(f)


def main(argv):
    ids = [a for a in argv if not a.startswith('-')]
    if not ids:
        print('用法: compare196.py <id> [<id> ...]')
        return 2
    frames = load('_npc_frames.json').get('characters') or {}
    anims = load('_npc_anims.json').get('characters') or {}

    K = 4
    CELL = 40 * K
    PAD, LH = 6, 14
    PER_ROW = 8
    for cid in ids:
        items = []
        fr = (frames.get(cid) or {}).get('frames') or {}
        d = 'down' if 'down' in fr else (sorted(fr)[0] if fr else None)
        if d:
            for row in fr[d][:4]:
                items.append(('walk ' + row['f'], os.path.join(DROP, cid, row['f'])))
        for emo in sorted(anims.get(cid) or {}):
            for dd in sorted(anims[cid][emo]):
                row = anims[cid][emo][dd][0]
                items.append(('%s %s' % (emo, dd), os.path.join(DROP, cid, row['f'])))
        if not items:
            print('  [--] %s 无帧' % cid)
            continue
        # ★ 折行：18 格挤一行会被缩到看不清（第196轮自己踩的）
        cols = min(PER_ROW, len(items))
        rows = (len(items) + cols - 1) // cols
        W = PAD + cols * (CELL + PAD)
        H = PAD + rows * (LH + CELL + PAD + 16)
        sheet = Image.new('RGB', (W, H), (26, 26, 32))
        draw = ImageDraw.Draw(sheet)
        for i, (label, p) in enumerate(items):
            x = PAD + (i % cols) * (CELL + PAD)
            y = PAD + (i // cols) * (LH + CELL + PAD + 16)
            draw.text((x, y), label[:16], fill=(255, 210, 130))
            draw.rectangle([x, y + LH, x + CELL, y + LH + CELL],
                           outline=(64, 64, 76))
            try:
                im = Image.open(p)
                im.load()
                src_w, src_h = im.size
                im = im.convert('RGBA')
            except Exception as e:
                draw.text((x + 2, y + LH + 20), 'FAIL', fill=(255, 0, 0))
                print('  !! %s %s' % (p, e))
                continue
            im = im.resize((im.width * K, im.height * K), Image.NEAREST)
            if im.width > CELL or im.height > CELL:
                im.thumbnail((CELL, CELL), Image.NEAREST)
            # 底部中央（脚底对齐）
            # ★ 必须带 alpha mask 贴：直接 `paste(RGB)` 会把透明像素的 RGB 也画出来
            #   （`spr_susie_laugh_up` 的透明区底下是浅色 ⇒ 看着像"一条浅色背景"，
            #   第196轮差点把它当废帧）。产品那边 `BodyWindow` 是分层透明窗，认 alpha。
            sheet.paste(im, (x + (CELL - im.width) // 2, y + LH + CELL - im.height),
                        im)
            draw.text((x + 1, y + LH + CELL + 2), '%dx%d' % (src_w, src_h),
                      fill=(140, 220, 160))
        out = os.path.join(EVID, 'cmp196_%s.png' % cid)
        sheet.save(out)
        print('  [OK] %-12s %d 格 → %s' % (cid, len(items), out))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

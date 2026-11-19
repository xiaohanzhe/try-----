# -*- coding: utf-8 -*-
"""第200轮 · Mac 端：把 OneShot 的格子表**切开放大**，标出 (行,列)，供人眼挑行。

为什么必须切开：`os_*` 的 96x128 / 120x200 / 448x320 都是 **4x4 帧表**
（`os_ling/contacts_ling.png` 本身就是从 120x200 表里切出来的 30x50 一格，
  这条是"格 = 画布/4"的**实证**，不是我推的）。

输出 `~/sheets/_cell/<id>.png`：每个非空格子放大 4 倍，左上角标 `r c`。
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SRC = os.path.expanduser('~/sheetsrc')
PLAN = os.path.expanduser('~/cell_plan.json')
OUT = os.path.expanduser(os.path.join('~', 'sheets', '_cell'))
ZOOM = 4
GAP = 10
BAR = 18
BG = (255, 255, 255)


def grid_of(w, h):
    """返回 (格宽, 格高, 列数, 行数)；判为单张则 (w,h,1,1)。"""
    if w % 4 == 0 and h % 4 == 0 and w >= 96 and h >= 128:
        return w // 4, h // 4, 4, 4
    return w, h, 1, 1


def main():
    plan = json.load(open(PLAN))
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    fpath = None
    for c in ('/System/Library/Fonts/Supplemental/Arial Bold.ttf',
              '/System/Library/Fonts/Helvetica.ttc'):
        if os.path.isfile(c):
            fpath = c
            break
    font = ImageFont.truetype(fpath, 14) if fpath else ImageFont.load_default()
    meta = {}
    for it in plan:
        cid, work, fn = it['id'], it['work'], it['file']
        p = os.path.join(SRC, work, fn)
        im = Image.open(p).convert('RGBA')
        w, h = im.size
        cw, ch, nc, nr = grid_of(w, h)
        cw, ch = w // nc, h // nr
        CELLW, CELLH = cw * ZOOM, ch * ZOOM
        W = nc * (CELLW + GAP) + GAP
        H = nr * (CELLH + BAR + GAP) + GAP
        page = Image.new('RGB', (W, H), BG)
        d = ImageDraw.Draw(page)
        cells = []
        for r in range(nr):
            for c in range(nc):
                box = (c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)
                sub = im.crop(box)
                bb = sub.split()[3].getbbox()
                x = GAP + c * (CELLW + GAP)
                y = GAP + r * (CELLH + BAR + GAP)
                d.text((x + 2, y + 1), '%d %d' % (r, c), fill=(200, 0, 0),
                       font=font)
                if bb is None:
                    cells.append({'r': r, 'c': c, 'empty': True})
                    d.rectangle([x, y + BAR, x + CELLW - 1, y + BAR + CELLH - 1],
                                outline=(210, 210, 210))
                    continue
                big = sub.resize((CELLW, CELLH), Image.NEAREST)
                page.paste(big, (x, y + BAR), big)
                cells.append({'r': r, 'c': c, 'empty': False,
                              'bbox': list(bb)})
        dst = os.path.join(OUT, cid + '.png')
        page.save(dst)
        meta[cid] = {'file': fn, 'work': work, 'canvas': [w, h],
                     'cell': [cw, ch], 'grid': [nr, nc], 'cells': cells,
                     'out': os.path.basename(dst)}
        print('  [切] %-22s %dx%d 格%dx%d → %dx%d' % (cid, w, h, nr, nc, cw, ch))
    with open(os.path.join(OUT, '_meta.json'), 'w') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print('共 %d 张 → %s' % (len(meta), OUT))


if __name__ == '__main__':
    sys.exit(main())

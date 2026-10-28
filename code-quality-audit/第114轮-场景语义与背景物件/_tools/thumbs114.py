# -*- coding: utf-8 -*-
u"""给「待命名清单」配缩略图对照表 —— 让人看着图起名，而不是对着 `green.tsx` 猜。

做法：直接把 `_evidence/objects_lib.json` 里每个图案的**首个出现位置**当裁剪框，
从已渲染好的整间房图上裁下来，放大（整数倍、NEAREST，保持像素风）后拼成 36 格/张的对照表。

★ 为什么裁“已渲染的整间房”而不是只画物件本身：
  物件常常靠地板/墙衬托才认得出（地毯、水渍、招牌阴影）。只画物件＝一堆浮在透明底的碎块，
  反而更难认。整房渲染里它就在它该在的位置。

★ 大于 36 格的图案会被缩到 120px 以内（LANCZOS）—— 那些本来就该看整体轮廓。

产物：
  _evidence/thumbs/sheet_01.png … 每张 6×6 = 36 格，格上有编号（A001 / B007）
  _evidence/thumbs/index.json     编号 → 哪张表、第几行第几列（给清单引用）

依赖 Pillow；渲染图默认取 `D:/_tmp/render_all`（`render_room.py --all` 的产物），可用 `--render` 改。
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.normpath(os.path.join(HERE, '..', '_evidence'))

try:
    from PIL import Image, ImageDraw
except ImportError:                        # pragma: no cover
    Image = None

CELL = 128          # 每格边长
PAD = 4             # 格内留白
COLS, ROWS = 6, 6   # 每张表 36 格
BOX = CELL - 2 * PAD
BG = (46, 46, 46)   # 深灰底，透明区域/深色物件都看得清
FG = (235, 235, 235)


def fit_crop(img, box):
    u"""裁 box 后按整数倍放大（小图）或等比缩小（大图）到 BOX 以内。"""
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0), max(0, y0)
    x1 = min(img.size[0], x1)
    y1 = min(img.size[1], y1)
    if x1 <= x0 or y1 <= y0:
        return None
    c = img.crop((x0, y0, x1, y1))
    w, h = c.size
    f = float(BOX) / max(w, h)
    if f >= 1.0:
        s = int(f)                                  # 像素风：只做整数倍最近邻
        if s > 1:
            c = c.resize((w * s, h * s), Image.NEAREST)
    else:
        c = c.resize((max(1, int(w * f)), max(1, int(h * f))), Image.LANCZOS)
    return c


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--lib', default=os.path.join(EV, 'objects_lib.json'))
    ap.add_argument('--render', default='D:/_tmp/render_all',
                    help='render_room.py --all 的输出目录（mapN.png）')
    ap.add_argument('--out', default=os.path.join(EV, 'thumbs'))
    ap.add_argument('--margin', type=int, default=2,
                    help='裁剪时四周多留几像素，免得切掉物件边缘')
    a = ap.parse_args(argv)
    if Image is None:
        print(u'需要 Pillow')
        return 2

    lib = json.load(io.open(a.lib, encoding='utf-8'))
    todo = lib['todo']
    print(u'待配图 %d 类' % len(todo))

    if not os.path.isdir(a.out):
        os.makedirs(a.out)

    cache = {}
    cells = {}
    sheet = None
    sheet_no = 0
    slot = 0
    n_missing = 0
    files = []

    def flush():
        if sheet is None:
            return
        p = os.path.join(a.out, 'sheet_%02d.png' % sheet_no)
        sheet.save(p)
        files.append(p)

    for e in todo:
        f0 = e['first']
        num = f0['map']
        im = cache.get(num)
        if im is None:
            p = os.path.join(a.render, 'map%d.png' % num)
            im = Image.open(p).convert('RGBA') if os.path.isfile(p) else False
            cache[num] = im
        if slot % (COLS * ROWS) == 0:
            if sheet is not None:
                flush()
            sheet_no += 1
            slot = 0
            sheet = Image.new('RGBA', (COLS * CELL, ROWS * CELL), BG)
            drw = ImageDraw.Draw(sheet)
        r, c = divmod(slot, COLS)
        x, y = c * CELL, r * CELL
        drw.rectangle([x + 1, y + 1, x + CELL - 2, y + CELL - 2],
                      outline=(90, 90, 90))
        if im is False:
            n_missing += 1
            drw.line([x + PAD, y + PAD, x + CELL - PAD, y + CELL - PAD],
                     fill=(160, 60, 60))
        else:
            m = a.margin
            px = f0['px']
            cu = fit_crop(im, (int(px[0]) - m, int(px[1]) - m,
                               int(px[2]) + m, int(px[3]) + m))
            if cu is not None:
                cx = x + (CELL - cu.size[0]) // 2
                cy = y + (CELL - cu.size[1]) // 2 + 4
                sheet.alpha_composite(cu.convert('RGBA'), (cx, cy))
        drw.text((x + 4, y + 3), e['code'], fill=FG)
        cells[e['code']] = {'file': 'sheet_%02d.png' % sheet_no,
                            'row': r, 'col': c,
                            'map': num, 'px': f0['px']}
        slot += 1
    flush()

    idx = {'note': u'编号 → 对照表位置。格上有编号，格子边长 %dpx，每张 %dx%d 格'
                    % (CELL, COLS, ROWS),
           'cell_px': CELL, 'cols': COLS, 'rows': ROWS,
           'sheets': [os.path.basename(p) for p in files],
           'cells': cells}
    p_idx = os.path.join(a.out, 'index.json')
    with io.open(p_idx, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(idx, ensure_ascii=False, indent=1))
    print(u'对照表 %d 张 → %s' % (len(files), a.out))
    if n_missing:
        print(u'!! %d 类找不到渲染图（房间里没有 mapN.png）' % n_missing)
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))

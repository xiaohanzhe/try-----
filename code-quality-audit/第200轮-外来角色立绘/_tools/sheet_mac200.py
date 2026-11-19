# -*- coding: utf-8 -*-
"""第200轮 · Mac 端：把每个角色的候选帧渲染成一张拼版（contact sheet）

跑在 mac 上（`~/ralsei-venv/bin/python`，Python 3.9 + Pillow 10.4）。

输入
----
`~/sheetsrc/<work>/*.png`   帧本体（本地 scp 过来，只读用）
`~/sheet_plan.json`         任务书：`[{id, work, files:[...]}]`

输出
----
`~/sheets/<id>.png`         4 列网格；每格是等比例缩略图 + `文件名 WxH`
`~/sheets/_index.json`      每张拼版的 `{id: {files, cells, sha1}}`

★ 为什么坚持出图：第191轮实测"自动按 token 匹配族"会把人挑错
  （`spr_dw_castle_queen_room_traffic_light` 当成 queen 的立绘），
  **猜错不报错、只画错人**。所以候选必须**人眼过一遍**再登记。
"""
import hashlib
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SRC = os.path.expanduser('~/sheetsrc')
PLAN = os.path.expanduser('~/sheet_plan.json')
OUT = os.path.expanduser('~/sheets')

COLS = 4
CELL = 120          # 格子内容区
PAD = 8
LABEL_H = 26
BG1 = (245, 245, 245)
BG2 = (222, 222, 222)


def sha1(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 16), b''):
            h.update(b)
    return h.hexdigest()


def checker(w, h):
    im = Image.new('RGB', (w, h), BG1)
    d = ImageDraw.Draw(im)
    for y in range(0, h, 12):
        for x in range(0, w, 12):
            if ((x // 12) + (y // 12)) % 2:
                d.rectangle([x, y, x + 11, y + 11], fill=BG2)
    return im


def main():
    plan = json.load(open(PLAN))
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    font = ImageFont.load_default()
    index = {}
    for item in plan:
        cid, work, files = item['id'], item['work'], item['files']
        rows = (len(files) + COLS - 1) // COLS
        W = COLS * (CELL + PAD) + PAD
        H = rows * (CELL + LABEL_H + PAD) + PAD
        sheet = checker(W, H).convert('RGBA')
        d = ImageDraw.Draw(sheet)
        for i, fn in enumerate(files):
            p = os.path.join(SRC, work, fn)
            r, c = divmod(i, COLS)
            x = PAD + c * (CELL + PAD)
            y = PAD + r * (CELL + LABEL_H + PAD)
            try:
                im = Image.open(p).convert('RGBA')
            except Exception as e:                       # noqa: BLE001
                d.text((x + 2, y + 2), 'ERR', fill=(200, 0, 0), font=font)
                print('  [坏图] %s %s' % (fn, e))
                continue
            w0, h0 = im.size
            k = min(CELL / float(w0), CELL / float(h0), 1.0)
            if k < 1.0:
                im = im.resize((max(1, int(w0 * k)), max(1, int(h0 * k))),
                               Image.LANCZOS)
            sheet.alpha_composite(im, (x + (CELL - im.size[0]) // 2,
                                       y + (CELL - im.size[1]) // 2))
            d.text((x + 2, y + CELL + 2), fn[:26], fill=(20, 20, 20), font=font)
            d.text((x + 2, y + CELL + 13), '%dx%d' % (w0, h0),
                   fill=(90, 90, 90), font=font)
        dst = os.path.join(OUT, cid + '.png')
        sheet.convert('RGB').save(dst)
        index[cid] = {'work': work, 'files': files, 'cells': len(files),
                      'sheet': os.path.basename(dst), 'sha1': sha1(dst)}
        print('  [写] %-24s %2d 张  %dx%d' % (cid, len(files), W, H))
    with open(os.path.join(OUT, '_index.json'), 'w') as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    print('完成 %d 张拼版 → %s' % (len(index), OUT))


if __name__ == '__main__':
    sys.exit(main())

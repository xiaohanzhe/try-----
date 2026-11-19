# -*- coding: utf-8 -*-
"""第200轮 · Mac 端：把若干张拼版合成为 2x2 的"看图页"，每格左上角打大号角色 id。

为什么合并：56 张单看要 56 次人眼提交，合并成 14 页只为省往返，**不降分辨率**
（拼版原宽 520，2x2 后 1040，人眼模型的最大边 1568 还够）。

输入 `~/sheets/<id>.png`；输出 `~/sheets/_view/pNN.png`，顺序由 `~/view_plan.json`
给定（`[[id,id,id,id], ...]`）。
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SRC = os.path.expanduser('~/sheets')
PLAN = os.path.expanduser('~/view_plan.json')
OUT = os.path.join(SRC, '_view')
GAP = 10
BAR = 30
BG = (255, 255, 255)

# 可选配置：`~/view_cfg.json` = {"src": "...", "out": "..."}，用来把同一条合成逻辑
# 复用到"切格页"上（避免为了换个目录再抄一份脚本）。
_CFG = os.path.expanduser('~/view_cfg.json')
if os.path.isfile(_CFG):
    _c = json.load(open(_CFG))
    SRC = os.path.expanduser(_c.get('src', SRC))
    OUT = os.path.join(SRC, _c.get('out', '_view'))
    PLAN = os.path.expanduser(_c.get('plan', PLAN))


def main():
    plan = json.load(open(PLAN))
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    fpath = None
    for cand in ('/System/Library/Fonts/Supplemental/Arial Bold.ttf',
                 '/System/Library/Fonts/Helvetica.ttc'):
        if os.path.isfile(cand):
            fpath = cand
            break
    font = ImageFont.truetype(fpath, 22) if fpath else ImageFont.load_default()
    for n, grp in enumerate(plan):
        ims = []
        for cid in grp:
            p = os.path.join(SRC, cid + '.png')
            if not os.path.isfile(p):
                print('  [缺] %s' % cid)
                ims.append(None)
                continue
            ims.append(Image.open(p).convert('RGB'))
        w0 = max(i.size[0] for i in ims if i is not None)
        h0 = max(i.size[1] for i in ims if i is not None)
        W = 2 * (w0 + GAP) + GAP
        H = 2 * (h0 + BAR + GAP) + GAP
        page = Image.new('RGB', (W, H), BG)
        d = ImageDraw.Draw(page)
        for k, cid in enumerate(grp):
            r, c = divmod(k, 2)
            x = GAP + c * (w0 + GAP)
            y = GAP + r * (h0 + BAR + GAP)
            d.text((x + 6, y + 3), cid, fill=(220, 0, 0), font=font)
            im = ims[k]
            if im is None:
                continue
            page.paste(im, (x, y + BAR))
        dst = os.path.join(OUT, 'p%02d.png' % (n + 1))
        page.save(dst)
        print('  [页] %s  %s  %dx%d' % (os.path.basename(dst),
                                        ','.join(grp), W, H))
    print('共 %d 页' % len(plan))


if __name__ == '__main__':
    sys.exit(main())

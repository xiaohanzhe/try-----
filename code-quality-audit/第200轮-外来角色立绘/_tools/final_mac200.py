# -*- coding: utf-8 -*-
"""第200轮 · Mac 端：把 54 个外来角色的**正面首帧**拼成一张总览图。

用途：肉眼最后过一遍——**"素材在盘上"不等于"屏幕上看得见"，
        "登记成功"也不等于"画出来是那个人"**（第191轮教训的第三次复述）。

输入 `~/final/<work>/<id>_down_0.png`；输出 `~/final/_overview.png`
（9 列，格内 2 倍最近邻放大，底部对齐，标 id 与像素尺寸）。
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

SRC = os.path.expanduser('~/final')
PLAN = os.path.expanduser('~/final_plan.json')
OUT = os.path.join(SRC, '_overview.png')
# ★ 同一份拼图逻辑允许在**任一端**跑：Mac 端用默认 `~/final`；本地端用环境变量指过去。
#   第200轮收尾时 Mac 掉线（SSH 22 端口超时），总览图就是这样在本地补出来的
#   —— 拼图是纯 IO，换机器不影响结果；**换的是机器，不是口径**。
SRC = os.path.expanduser(os.environ.get('FINAL_SRC', SRC))
PLAN = os.path.expanduser(os.environ.get('FINAL_PLAN', PLAN))
OUT = os.path.expanduser(os.environ.get('FINAL_OUT', OUT))
COLS, CELL, PAD, BAR = 9, 96, 8, 24
BG = (246, 247, 249)


def main():
    plan = json.load(open(PLAN))
    fpath = None
    for c in ('/System/Library/Fonts/Supplemental/Arial Bold.ttf',
              '/System/Library/Fonts/Helvetica.ttc'):
        if os.path.isfile(c):
            fpath = c
            break
    font = ImageFont.truetype(fpath, 11) if fpath else ImageFont.load_default()
    rows = (len(plan) + COLS - 1) // COLS
    W = COLS * (CELL + PAD) + PAD
    H = rows * (CELL + BAR + PAD) + PAD
    page = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(page)
    ok = miss = 0
    for i, it in enumerate(plan):
        cid, work = it['id'], it['work']
        p = os.path.join(SRC, work, cid + '_down_0.png')
        r, c = divmod(i, COLS)
        x = PAD + c * (CELL + PAD)
        y = PAD + r * (CELL + BAR + PAD)
        d.text((x, y), cid[:16], fill=(30, 30, 34), font=font)
        d.rectangle([x, y + BAR, x + CELL - 1, y + BAR + CELL - 1],
                    outline=(206, 208, 214))
        if not os.path.isfile(p):
            d.text((x + 4, y + BAR + 40), 'MISS', fill=(200, 0, 0), font=font)
            miss += 1
            print('  [缺] %s' % p)
            continue
        im = Image.open(p).convert('RGBA')
        w0, h0 = im.size
        k = 2
        while k > 1 and (w0 * k > CELL - 4 or h0 * k > CELL - 4):
            k -= 1
        if k > 1:
            im = im.resize((w0 * k, h0 * k), Image.NEAREST)
        if im.size[0] > CELL - 4 or im.size[1] > CELL - 4:
            im.thumbnail((CELL - 4, CELL - 4), Image.NEAREST)
        px = x + (CELL - im.size[0]) // 2
        py = y + BAR + CELL - im.size[1] - 2        # 底部对齐（与运行时同口径）
        page.paste(im, (px, py), im)
        d.text((x + 2, y + BAR + CELL - 10), '%dx%d' % (w0, h0),
               fill=(120, 120, 130), font=font)
        ok += 1
    page.save(OUT)
    print('总览 %d 人（缺 %d）→ %s  %dx%d' % (ok, miss, OUT, W, H))
    return 0 if miss == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

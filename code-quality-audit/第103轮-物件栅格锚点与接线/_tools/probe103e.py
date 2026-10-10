# -*- coding: utf-8 -*-
u"""probe103e.py —— 第103轮侦察 5：**单张高倍放大 + 候选网格线**（最终目视裁决）。

每张图集单独出一张图：原图放大 5 倍，叠上**两套候选网格线**
  红 = 4 列 × 4 行等分（cell = w/4 × h/4）
  青 = 3 列 × 4 行（VX Ace 标准：3 帧 × 4 方向，cell = w/3 × h/4）
再在每格左上角标 (col,row)。看图就知道哪套线落在**精灵之间**。
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image, ImageDraw                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
PROPS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'oneshot_props')
os.makedirs(EV, exist_ok=True)

PICK = ['items_tut', 'jars_new', 'green_marimo', 'water_waves_green2',
        'DOORS', 'green_npc_cedric', 'bed', 'pc', 'sparkle_blue1', 'red_rue']


def render(nm, zoom=5):
    p = os.path.join(PROPS, nm + '.png')
    im = Image.open(p).convert('RGBA')
    w, h = im.size
    Z = max(2, min(zoom, int(900 / max(w, h)) or 2))
    big = im.resize((w * Z, h * Z), Image.NEAREST)
    out = Image.new('RGBA', (w * Z, h * Z), (26, 26, 34, 255))
    out.alpha_composite(big)
    dr = ImageDraw.Draw(out)
    # 4x4（红）
    for i in (1, 2, 3):
        x = int(w * Z * i / 4.0)
        y = int(h * Z * i / 4.0)
        dr.line([(x, 0), (x, h * Z)], fill=(255, 70, 70, 220), width=1)
        dr.line([(0, y), (w * Z, y)], fill=(255, 70, 70, 220), width=1)
    # 3 列（青）
    for i in (1, 2):
        x = int(w * Z * i / 3.0)
        dr.line([(x, 0), (x, h * Z)], fill=(70, 235, 235, 200), width=1)
    # 标 (col,row) 于 4x4 格
    cw, ch = w * Z // 4, h * Z // 4
    for r in range(4):
        for c in range(4):
            dr.text((c * cw + 3, r * ch + 2), '%d,%d' % (c, r), fill=(255, 235, 120, 255))
    # 边框
    dr.rectangle([0, 0, w * Z - 1, h * Z - 1], outline=(180, 180, 200))
    return out


for nm in PICK:
    p = os.path.join(PROPS, nm + '.png')
    if not os.path.isfile(p):
        print('  跳过（不在盘）', nm)
        continue
    im = Image.open(p)
    o = render(nm)
    f = os.path.join(EV, 'zoom_%s103.png' % nm)
    o.save(f)
    print('  %-22s %4dx%-4d -> %s  %s' % (nm, im.width, im.height,
                                          os.path.basename(f), o.size))

# -*- coding: utf-8 -*-
u"""sheet101.py —— 263 张 OneShot 背景总览（目视把关）。

用户口径：「**一定要看录像而不是只读后台输出**」⇒ 落盘之后必须**看图**，
不能只信 `[PASS]`。产物：_evidence/os_bg_all101.png（16 列缩略图，带 room_id 标签）。
"""
import importlib.util
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image, ImageDraw                                # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
BGDIR = os.path.join(SCENES, 'bg')
EV = os.path.join(os.path.dirname(HERE), '_evidence')

# room_id -> scene 名
names = {}
for z in sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.')):
    with io.open(os.path.join(SCENES, z), encoding='utf-8') as f:
        d = json.load(f)
    for sid, s in (d.get('scenes') or {}).items():
        names[int(s['original_room_id'])] = sid.split('.', 2)[2]

COLS, CW, PAD, LBL = 16, 132, 5, 14
rows = (263 + COLS - 1) // COLS
CH = 100
W = COLS * (CW + PAD) + PAD
H = rows * (CH + LBL + PAD) + PAD
sheet = Image.new('RGB', (W, H), (28, 28, 34))
dr = ImageDraw.Draw(sheet)

for i in range(1, 264):
    col, row = (i - 1) % COLS, (i - 1) // COLS
    x = PAD + col * (CW + PAD)
    y = PAD + row * (CH + LBL + PAD)
    p = os.path.join(BGDIR, 'oneshot_map%d.png' % i)
    if not os.path.isfile(p):
        dr.rectangle([x, y, x + CW, y + CH], outline=(200, 60, 60))
        continue
    im = Image.open(p).convert('RGB')
    k = min(CW / im.width, CH / im.height)
    im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))),
                   Image.NEAREST)
    sheet.paste(im, (x + (CW - im.width) // 2, y + (CH - im.height) // 2))
    dr.text((x + 2, y + CH + 1), '%d %s' % (i, names.get(i, '?')[:14]),
            fill=(200, 200, 210))

os.makedirs(EV, exist_ok=True)
out = os.path.join(EV, 'os_bg_all101.png')
sheet.save(out)
print('总览 %s  %s  共 %d 格' % (out, sheet.size, 263))

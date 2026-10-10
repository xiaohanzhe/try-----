# -*- coding: utf-8 -*-
u"""cmp103.py —— 第103轮判定图：**门（16x32）在瓦片格里的对齐**四格并排。

为什么选门：`DOORS2` 的格恰好 **16 宽 × 32 高**（= 1 瓦片宽、2 瓦片高）⇒
**水平锚点在它身上无歧义**，只剩下"格底贴瓦片底（A1/A2）还是格顶贴瓦片顶（A0）"。
把它叠到 `oneshot_map4.png`（= tmx 瓦片层逐像素合成的原样）上，
**哪一个能落在原作留的门洞里**，肉眼即可判定。

地图 4 的 `north door` 事件：tile (21,9)、`DOORS2`、direction=2、pattern=0。
"""
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image, ImageDraw                                            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')

TILE = 16
X0, Y0, X1, Y1 = 18, 5, 26, 13           # 裁切区（瓦片坐标，右/下开区间）
Z = 7
DOOR_TILE = (21, 9)


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


# 找 map4 的可见物件（真源 = 原作 events_map4.json，不用 build103 的产物）
objs = []
for e in rj(os.path.join(MAPS, 'events_map4.json')).get('events', []):
    pgs = e.get('pages') or []
    if not pgs:
        continue
    g = pgs[0].get('graphic') or {}
    if int(g.get('tile_id') or 0) > 0:
        continue
    cn = (g.get('character_name') or '').strip()
    if not cn:
        continue
    objs.append(dict(name=e.get('name'), x=e['x'], y=e['y'], cn=cn,
                     d=int(g.get('direction') or 0), p=int(g.get('pattern') or 0)))
print('map4 可见物件 %d 个：%s' % (len(objs), [(o2['name'], o2['cn'], o2['x'], o2['y'])
                                           for o2 in objs]))
DIR_ROW = {2: 0, 4: 1, 6: 2, 8: 3}
CANDS = [
    ('仅背景（tmx 合成 = 原作瓦片原样）', None),
    ('A0 格左上=瓦片左上', lambda x, y, cw, ch: (x * TILE, y * TILE)),
    ('A1 底居中（本方案）', lambda x, y, cw, ch: (x * TILE + TILE // 2 - cw // 2,
                                                y * TILE + TILE - ch)),
    ('A2 底左', lambda x, y, cw, ch: (x * TILE, y * TILE + TILE - ch)),
]

base = Image.open(os.path.join(SCENES, 'bg', 'oneshot_map4.png')).convert('RGBA')
crop_box = (X0 * TILE, Y0 * TILE, X1 * TILE, Y1 * TILE)
cw, ch = (X1 - X0) * TILE * Z, (Y1 - Y0) * TILE * Z
panels = []
for label, fn in CANDS:
    canvas = base.copy()
    if fn is not None:
        for o2 in objs:
            sp = os.path.join(SCENES, 'oneshot_props', o2['cn'] + '.png')
            if not os.path.isfile(sp):
                continue
            im = Image.open(sp).convert('RGBA')
            w, h = im.size
            ccw, cch = w // 4, h // 4
            cell = im.crop((min(3, o2['p']) * ccw, DIR_ROW[o2['d']] * cch,
                            min(3, o2['p']) * ccw + ccw,
                            DIR_ROW[o2['d']] * cch + cch))
            canvas.alpha_composite(cell, fn(o2['x'], o2['y'], ccw, cch))
    p = canvas.crop(crop_box).resize((cw, ch), Image.NEAREST)
    d = ImageDraw.Draw(p)
    # 青线 = 瓦片格边
    for tx in range(X0, X1 + 1):
        xx = (tx - X0) * TILE * Z
        d.line([xx, 0, xx, ch], fill=(0, 255, 255, 255))
    for ty in range(Y0, Y1 + 1):
        yy = (ty - Y0) * TILE * Z
        d.line([0, yy, cw, yy], fill=(0, 255, 255, 255))
    # 红框 = 门所在瓦片 (21,9)
    rx = (DOOR_TILE[0] - X0) * TILE * Z
    ry = (DOOR_TILE[1] - Y0) * TILE * Z
    d.rectangle([rx, ry, rx + TILE * Z - 1, ry + TILE * Z - 1], outline=(255, 0, 0, 255))
    d.text((6, 4), label, fill=(255, 255, 0, 255))
    panels.append(p)

G = 8
sheet = Image.new('RGBA', (cw * 2 + G, ch * 2 + G), (20, 20, 26, 255))
for i, p in enumerate(panels):
    sheet.alpha_composite(p, ((i % 2) * (cw + G), (i // 2) * (ch + G)))
out = os.path.join(EV, 'cmp_door_map4_103.png')
sheet.save(out)
print('裁切区 = 瓦片 %s -> %s；放大 %dx；红框 = 门瓦片(21,9)' % (crop_box, '', Z))
print('出图 -> %s  %s' % (os.path.basename(out), sheet.size))

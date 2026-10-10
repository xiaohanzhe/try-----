# -*- coding: utf-8 -*-
u"""cmp103b.py —— 第103轮判定图 2：**水平锚点**能不能也拿到像素判据？

map4 的第 2 个可见物件 = `key`（图集 `start_scenery1`）@tile (27,12)。
`oneshot_map4.png`（tmx 合成）那一带有一处**键盘样的瓦片特征**。
若该物件就是"键盘"，它应当**正好压在**那处瓦片特征上 ⇒ 水平锚点就有了判据。

出两张（背景 / A1）并排裁切图，裁切区放大。
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
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
EV = os.path.join(HERE, '..', '_evidence')
spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')

TILE, Z = 16, 7
X0, Y0, X1, Y1 = 22, 8, 32, 16
DIR_ROW = {2: 0, 4: 1, 6: 2, 8: 3}


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


objs = []
for e in rj(os.path.join(MAPS, 'events_map4.json')).get('events', []):
    pgs = e.get('pages') or []
    if not pgs:
        continue
    g = pgs[0].get('graphic') or {}
    if int(g.get('tile_id') or 0) > 0:
        continue
    cn = (g.get('character_name') or '').strip()
    if cn:
        objs.append(dict(name=e.get('name'), x=e['x'], y=e['y'], cn=cn,
                         d=int(g.get('direction') or 0), p=int(g.get('pattern') or 0)))
for o2 in objs:
    sp = os.path.join(SCENES, 'oneshot_props', o2['cn'] + '.png')
    if os.path.isfile(sp):
        w, h = Image.open(sp).size
        print('  %-12s %-16s %dx%d 格=%dx%d tile=(%d,%d) d=%d p=%d'
              % (o2['name'], o2['cn'], w, h, w // 4, h // 4, o2['x'], o2['y'],
                 o2['d'], o2['p']))

base = Image.open(os.path.join(SCENES, 'bg', 'oneshot_map4.png')).convert('RGBA')
box = (X0 * TILE, Y0 * TILE, X1 * TILE, Y1 * TILE)

panels = []
for tag, use in (('仅背景', False), ('A1 底居中（本方案）', True)):
    cv = base.copy()
    if use:
        for o2 in objs:
            sp = os.path.join(SCENES, 'oneshot_props', o2['cn'] + '.png')
            if not os.path.isfile(sp):
                continue
            im = Image.open(sp).convert('RGBA')
            w, h = im.size
            cw, ch = w // 4, h // 4
            cell = im.crop((min(3, o2['p']) * cw, DIR_ROW[o2['d']] * ch,
                            min(3, o2['p']) * cw + cw, DIR_ROW[o2['d']] * ch + ch))
            cv.alpha_composite(cell, (o2['x'] * TILE + TILE // 2 - cw // 2,
                                      o2['y'] * TILE + TILE - ch))
    p = cv.crop(box).resize(((X1 - X0) * TILE * Z, (Y1 - Y0) * TILE * Z), Image.NEAREST)
    d = ImageDraw.Draw(p)
    for tx in range(X0, X1 + 1):
        xx = (tx - X0) * TILE * Z
        d.line([xx, 0, xx, p.size[1]], fill=(0, 255, 255, 255))
    for ty in range(Y0, Y1 + 1):
        yy = (ty - Y0) * TILE * Z
        d.line([0, yy, p.size[0], yy], fill=(0, 255, 255, 255))
    # 黄框 = key 所在瓦片 (27,12)
    d.rectangle([(27 - X0) * TILE * Z, (12 - Y0) * TILE * Z,
                 (27 - X0) * TILE * Z + TILE * Z - 1,
                 (12 - Y0) * TILE * Z + TILE * Z - 1], outline=(255, 255, 0, 255))
    d.text((6, 4), tag, fill=(255, 255, 0, 255))
    panels.append(p)

sheet = Image.new('RGBA', (panels[0].size[0], panels[0].size[1] * 2 + 8), (20, 20, 26, 255))
sheet.alpha_composite(panels[0], (0, 0))
sheet.alpha_composite(panels[1], (0, panels[0].size[1] + 8))
out = os.path.join(EV, 'cmp_key_map4_103.png')
sheet.save(out)
print('出图 -> %s %s（黄框 = key 瓦片(27,12)）' % (os.path.basename(out), sheet.size))

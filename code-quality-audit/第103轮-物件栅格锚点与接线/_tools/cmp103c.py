# -*- coding: utf-8 -*-
u"""cmp103c.py —— 第103轮判定图 3：从**严格 54 例**里再挑两个不同尺度的案例出图。

严格例（`_evidence/anchor_cases103.json`）全是"格宽>=2 瓦片的物件落在**恰好同宽**
的黑洞上"。挑 `tv_encounter`(112x64 = 7x4 瓦片) 与 `tv_screens1`(48x32 = 3x2)
各一，出 A1/A2/A0 三格并排图。
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
BAC = os.path.join(SCENES, 'bg')
EV = os.path.join(HERE, '..', '_evidence')
spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')
TILE = 16
DIR_ROW = {2: 0, 4: 1, 6: 2, 8: 3}


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


CASES = json.load(io.open(os.path.join(EV, 'anchor_cases103.json'),
                          encoding='utf-8'))['cases']
want = {}
for c in CASES:
    want.setdefault(c['sheet'], c)
PICK = [want['tv_encounter'], want['tv_screens1']]
for c in PICK:
    print('  挑中 room%-4d %-14s %-14s tile=%s 格=%s'
          % (c['room'], c['name'], c['sheet'], c['tile'], c['cell']))

for c in PICK:
    base = Image.open(os.path.join(BAC, 'oneshot_map%d.png' % c['room'])).convert('RGBA')
    sp = Image.open(os.path.join(SCENES, 'oneshot_props', c['sheet'] + '.png')).convert('RGBA')
    w, h = sp.size
    ccw, cch = w // 4, h // 4
    cell = sp.crop((c['col'] * ccw, c['row'] * cch,
                    c['col'] * ccw + ccw, c['row'] * cch + cch))
    x, y = c['tile']
    kc, kr = c['cell'][0] // TILE, c['cell'][1] // TILE
    Z = 5
    x0, y0 = (x - kc - 1) * TILE, (y - kr - 1) * TILE
    x1, y1 = (x + kc + 1) * TILE, (y + kr + 1) * TILE
    panels = []
    for tag, f in (('A1 底居中（本方案）', lambda: (x * TILE + TILE // 2 - ccw // 2,
                                                y * TILE + TILE - cch)),
                   ('A2 底左', lambda: (x * TILE, y * TILE + TILE - cch)),
                   ('A0 顶左', lambda: (x * TILE, y * TILE))):
        cv = base.copy()
        cv.alpha_composite(cell, f())
        p = cv.crop((x0, y0, x1, y1)).resize(((x1 - x0) * Z, (y1 - y0) * Z), Image.NEAREST)
        d = ImageDraw.Draw(p)
        for tx in range(x0 // TILE, x1 // TILE + 1):
            xx = (tx * TILE - x0) * Z
            d.line([xx, 0, xx, p.size[1]], fill=(0, 255, 255, 255))
        for ty in range(y0 // TILE, y1 // TILE + 1):
            yy = (ty * TILE - y0) * Z
            d.line([0, yy, p.size[0], yy], fill=(0, 255, 255, 255))
        d.rectangle([(x * TILE - x0) * Z, (y * TILE - y0) * Z,
                     (x * TILE - x0) * Z + TILE * Z - 1,
                     (y * TILE - y0) * Z + TILE * Z - 1], outline=(255, 0, 0, 255))
        d.text((6, 4), tag, fill=(255, 255, 0, 255))
        panels.append(p)
    W2 = sum(p.size[0] for p in panels) + 8 * 2
    sh = Image.new('RGBA', (W2, panels[0].size[1]), (20, 20, 26, 255))
    xx = 0
    for p in panels:
        sh.alpha_composite(p, (xx, 0))
        xx += p.size[0] + 8
    out = os.path.join(EV, 'cmp_strict_%s_r%d103.png' % (c['sheet'], c['room']))
    sh.save(out)
    print('  -> %s %s（红框 = 事件瓦片）' % (os.path.basename(out), sh.size))

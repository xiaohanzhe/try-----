# -*- coding: utf-8 -*-
u"""probe103j.py —— 第103轮侦察 10：**把物件按 4 种候选锚点叠到 tmx 合成图上，看图**。

已定死：cell=(w/4,h/4)、col=pattern、row=DIR_ROW={2:0,4:1,6:2,8:3}。
未定：锚点（格相对瓦片 (x,y) 画到哪）。

本脚本：
  S1 逐格不透明包围盒（客观量：精灵在格内怎么摆 —— 支持/反对"底居中"）
  S2 grass 高波 vs 短波的下 16 行结构对照
  S3 产出 4 张叠图（map4 Livingroom）→ 直接看图
  S4 产出 4 张叠图（map240 Forest 局部）
"""
import collections
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')
PROPS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'oneshot_props')
BG = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'bg')
TILE = 16
DIR_ROW = {2: 0, 4: 1, 6: 2, 8: 3}


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


def visible(rid):
    out = []
    p = os.path.join(MAPS, 'events_map%d.json' % rid)
    if not os.path.isfile(p):
        return out
    for e in rj(p).get('events', []):
        pgs = e.get('pages') or []
        if not pgs:
            continue
        g = pgs[0].get('graphic') or {}
        if int(g.get('tile_id') or 0) > 0:
            continue
        nm = (g.get('character_name') or '').strip()
        if not nm:
            continue
        out.append(dict(name=(e.get('name') or ''), x=int(e.get('x') or 0),
                        y=int(e.get('y') or 0), cn=nm,
                        d=int(g.get('direction') or 0),
                        p=int(g.get('pattern') or 0),
                        op=int(g.get('opacity') or 0)))
    return out


_sheet_cache = {}


def cell_img(cn, d, p):
    u"""取 (character_name, direction, pattern) 对应的一格；返回 RGBA。"""
    if cn in _sheet_cache:
        im = _sheet_cache[cn]
    else:
        fp = os.path.join(PROPS, cn + '.png')
        if not os.path.isfile(fp):
            _sheet_cache[cn] = None
            return None
        im = Image.open(fp).convert('RGBA')
        _sheet_cache[cn] = im
    if im is None:
        return None
    w, h = im.size
    cw, ch = w // 4, h // 4
    col = max(0, min(3, p))
    row = DIR_ROW.get(d, 0)
    return im.crop((col * cw, row * ch, col * cw + cw, row * ch + ch)), (cw, ch)


print('=' * 100)
print('S1 逐格不透明包围盒（客观量：精灵在格内怎么摆）')
print('=' * 100)
print('  %-24s %-8s %s' % ('sheet', 'cell', '每格 opacity bbox（dx0,dy1 距格左/格底；c 距格中）'))
for nm in ('green_npc_cedric', 'pc', 'bed', 'DOORS', 'water_waves_green_tall',
           'water_waves_green2', 'items_tut', 'green_marimo', 'red_rue',
           'jars_new', 'green_npc_adult3'):
    fp = os.path.join(PROPS, nm + '.png')
    if not os.path.isfile(fp):
        continue
    im = Image.open(fp).convert('RGBA')
    w, h = im.size
    cw, ch = w // 4, h // 4
    rec = []
    for col in range(4):
        for row in range(4):
            c = im.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch))
            bb = c.getchannel('A').getbbox()
            rec.append(None if bb is None else bb)
    ne = [r for r in rec if r]
    if not ne:
        print('  %-24s %-8s （全透明）' % (nm, '%dx%d' % (cw, ch)))
        continue
    x0 = collections.Counter(r[0] for r in ne).most_common(2)
    y1 = collections.Counter(r[3] for r in ne).most_common(2)
    cx = collections.Counter(((r[0] + r[2]) / 2.0 - cw / 2.0) for r in ne).most_common(2)
    print('  %-24s %-8s 空%d/16  x0=%s  底距格底=%s  中心偏移=%s'
          % (nm, '%dx%d' % (cw, ch), 16 - len(ne), x0,
             [('ch-%d' % v, n) for v, n in y1], cx))

print()
print('=' * 100)
print('S2 water_waves_green_tall 的「下 16 行」 vs water_waves_green2 的格（结构是否同源）')
print('=' * 100)
tall = Image.open(os.path.join(PROPS, 'water_waves_green_tall.png')).convert('RGBA')
short = Image.open(os.path.join(PROPS, 'water_waves_green2.png')).convert('RGBA')
tw, th = tall.size
tcw, tch = tw // 4, th // 4
scw, sch = short.size[0] // 4, short.size[1] // 4
for col in range(4):
    tl = tall.crop((col * tcw, 0, (col + 1) * tcw, tch))          # 上 16（浪尖）
    tb = tall.crop((col * tcw, tch, (col + 1) * tcw, tch * 2))    # 下 16
    sh = short.crop((col * scw, 0, (col + 1) * scw, sch))
    a_tb = sum(tb.getchannel('A').getdata())
    a_tl = sum(tl.getchannel('A').getdata())
    a_sh = sum(sh.getchannel('A').getdata())
    diff = 0
    if a_tb and a_sh:
        db, ds = tb.tobytes(), sh.tobytes()
        diff = sum(1 for i in range(0, len(db), 4) if db[i:i + 4] != ds[i:i + 4])
    print('  col%d  上16 alpha和=%-7d  下16 alpha和=%-7d  green2 格=%-7d  下16与green2不同像素=%d/%d'
          % (col, a_tl, a_tb, a_sh, diff, tch * tcw))

print()
print('=' * 100)
print('S3/S4 叠图：同一房间 × 4 种锚点')
print('=' * 100)
CANDS = [
    ('A0_格左上=瓦片左上', lambda x, y, cw, ch: (x * TILE, y * TILE)),
    ('A1_底居中', lambda x, y, cw, ch: (x * TILE + TILE // 2 - cw // 2,
                                       y * TILE + TILE - ch)),
    ('A2_底左', lambda x, y, cw, ch: (x * TILE, y * TILE + TILE - ch)),
    ('A3_居中', lambda x, y, cw, ch: (x * TILE + TILE // 2 - cw // 2,
                                      y * TILE + TILE // 2 - ch // 2)),
]


def draw_room(rid, crop=None, zoom=2, tag=''):
    bp = os.path.join(BG, 'oneshot_map%d.png' % rid)
    if not os.path.isfile(bp):
        print('  map%d 无合成图' % rid)
        return
    base = Image.open(bp).convert('RGBA')
    objs = visible(rid)
    sizes = collections.Counter()
    for e in objs:
        got = cell_img(e['cn'], e['d'], e['p'])
        sizes[got[1] if got else None] += 1
    print('  map%-4d 合成图 %s  可见物件 %d  格尺寸分布 %s'
          % (rid, base.size, len(objs), dict(sizes.most_common(6))))
    for nm, fn in CANDS:
        canvas = base.copy()
        drawn = 0
        for e in objs:
            got = cell_img(e['cn'], e['d'], e['p'])
            if got is None:
                continue
            c, (cw, ch) = got
            px, py = fn(e['x'], e['y'], cw, ch)
            canvas.alpha_composite(c, (px, py))
            drawn += 1
        if crop:
            canvas = canvas.crop(crop)
        if zoom != 1:
            canvas = canvas.resize((canvas.size[0] * zoom, canvas.size[1] * zoom),
                                   Image.NEAREST)
        out = os.path.join(EV, 'anchor_map%d%s_%s.png' % (rid, tag, nm))
        canvas.save(out)
        print('      %-22s 画了 %3d 个 -> %s  %s'
              % (nm, drawn, os.path.basename(out), canvas.size))


draw_room(4)
draw_room(240, crop=(0, 320, 832, 800), tag='_crop')
print()
print('  说明：A0 = 格左上贴在瓦片左上；A1 = 格底边贴瓦片底边且水平居中；')
print('        A2 = 格底边贴瓦片底边、左对齐；A3 = 格中心贴瓦片中心。')

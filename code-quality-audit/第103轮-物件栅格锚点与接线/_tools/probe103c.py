# -*- coding: utf-8 -*-
u"""probe103c.py —— 第103轮侦察 3：把候选栅格规则**在同一张图上并排渲染**，肉眼裁决。

候选规则（都只吃 name/direction/pattern，因为数据里没有 `character_index`）：
  R_A  cell = (w/4, h/4)；col = pattern，row = {2:0, 4:1, 6:2, 8:3}[direction]
  R_B  cell = (w/3, h/4)（VX Ace 标准单角色：3 帧 × 4 方向）
  R_C  cell = 32×32 固定；col = pattern，row = dir_idx
  R_D  整张图（不切）

输出：每张图集一行 —— [整张] [R_A 取到的格] [R_B 取到的格] [R_C 取到的格]，
格内画出该图集**实际用到的第一个** (dir, pattern) 的取块结果，并标注坐标。
"""
import collections
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image, ImageDraw                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
PROPS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'oneshot_props')
spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')

ING = json.load(io.open(os.path.join(
    ROOT, 'code-quality-audit', '第102轮-光照与ambient接入', '_evidence',
    'ingest102.json'), encoding='utf-8'))
SIZES = {f['name']: (f['w'], f['h']) for f in ING['files']}
DIR_ROW = {2: 0, 4: 1, 6: 2, 8: 3}


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


use = collections.defaultdict(collections.Counter)
for n in range(1, 264):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p):
        continue
    for e in rj(p).get('events', []):
        pgs = e.get('pages') or []
        if not pgs:
            continue
        g = pgs[0].get('graphic') or {}
        nm = (g.get('character_name') or '').strip()
        if not nm or int(g.get('tile_id') or 0) > 0:
            continue
        use[nm][(int(g.get('direction') or 0), int(g.get('pattern') or 0))] += 1

# ---- 全量体检：4×4 假设是否对 148 张**全部**成立 ----
bad4 = [(nm, SIZES[nm]) for nm in SIZES
        if SIZES[nm][0] % 4 or SIZES[nm][1] % 4]
bad32 = [(nm, SIZES[nm]) for nm in SIZES
         if SIZES[nm][0] % 32 or SIZES[nm][1] % 32]
print('=' * 92)
print('S1 整除性体检（148 张）')
print('=' * 92)
print('  宽高**都能被 4 整除**的例外 = %d 个 %s' % (len(bad4), bad4[:5]))
print('  宽高**都能被 32 整除**的例外 = %d 个 %s' % (len(bad32), bad32[:8]))

# ---- 越界体检：按各规则算出的格，会不会越出图集 ----
print()
print('=' * 92)
print('S2 越界体检（同一批 7,805 个物件，三种规则各算一遍）')
print('=' * 92)
cnt = collections.Counter()
oob = collections.Counter()
ex = collections.defaultdict(list)
for nm, combo in use.items():
    if nm not in SIZES:
        continue
    w, h = SIZES[nm]
    for (d, pat), k in combo.items():
        row = DIR_ROW.get(d, 0)
        cnt['total'] += k
        r, c = h // 4, w // 4
        if not (0 <= pat < c and 0 <= row < r):
            oob['A'] += k
            if len(ex['A']) < 4:
                ex['A'].append((nm, w, h, d, pat, c, r))
        r3, c3 = h // 4, w // 3
        if not (0 <= pat < c3 and 0 <= row < r3):
            oob['B'] += k
            if len(ex['B']) < 4:
                ex['B'].append((nm, w, h, d, pat, c3, r3))
        r32, c32 = h // 32, w // 32
        if not (0 <= pat < c32 and 0 <= row < r32):
            oob['C'] += k
            if len(ex['C']) < 4:
                ex['C'].append((nm, w, h, d, pat, c32, r32))
print('  物件总数 = %d' % cnt['total'])
for k, nm_ in (('A', 'w/4 x h/4'), ('B', 'w/3 x h/4'), ('C', '32x32 固定')):
    print('   规则 %s %-11s 越界 = %-6d 例 %s' % (k, nm_, oob[k], ex[k][:2]))

# ---- 并排渲染 ----
print()
print('=' * 92)
print('S3 并排渲染（肉眼裁决）')
print('=' * 92)
PICK = ['green_npc_cedric', 'red_rue', 'water_waves_green2', 'sparkle_blue1',
        'DOORS', 'bed', 'jars_new', 'blue_silver_crush', 'vehicle_blue_minecart',
        'tv_screens1', 'green_marimo', 'blue_crater_big', 'guardians', 'pc',
        'red_npc_1', 'green_robots_in']


def cell_of(im, w, h, d, pat, rule):
    row = DIR_ROW.get(d, 0)
    if rule == 'A':
        cw, ch = max(1, w // 4), max(1, h // 4)
    elif rule == 'B':
        cw, ch = max(1, w // 3), max(1, h // 4)
    elif rule == 'C':
        cw, ch = 32, 32
    else:
        return im, (0, 0), (w, h)
    x, y = pat * cw, row * ch
    x = min(x, max(0, w - cw))
    y = min(y, max(0, h - ch))
    return im.crop((x, y, x + cw, y + ch)), (x, y), (cw, ch)


def tile(im, box, cw, ch, cell_w=140, cell_h=140, zoom_max=4):
    z = max(1, min(zoom_max, cell_w // max(1, cw), cell_h // max(1, ch)))
    im2 = im.convert('RGBA').resize((cw * z, ch * z), Image.NEAREST)
    t = Image.new('RGBA', (cell_w, cell_h), (28, 28, 36, 255))
    t.alpha_composite(im2, ((cell_w - cw * z) // 2, (cell_h - ch * z) // 2))
    return t


CW, CH, PAD, LBL, HEAD = 140, 140, 6, 13, 20
rows = []
for nm in PICK:
    if nm not in SIZES or nm not in use:
        continue
    w, h = SIZES[nm]
    combos = sorted(use[nm])
    d, pat = combos[0]
    im = Image.open(os.path.join(PROPS, nm + '.png'))
    tiles = [('整张', tile(im, None, w, h, zoom_max=1))]
    for rule in ('A', 'B', 'C'):
        c, (x, y), (cw, ch) = cell_of(im, w, h, d, pat, rule)
        tiles.append(('%s %d,%d' % (rule, x, y), tile(c, None, cw, ch)))
    rows.append((nm, w, h, d, pat, combos, tiles))

W = 5 * (CW + PAD) + PAD + 150
H = HEAD + len(rows) * (CH + LBL + PAD) + PAD
sheet = Image.new('RGB', (W, H), (16, 16, 22))
dr = ImageDraw.Draw(sheet)
dr.text((6, 4), u'第103轮：栅格规则并排（首格 = 整张；A=w/4×h/4 取 pattern 列 / dir 行；'
                u'B=w/3×h/4；C=32×32）', fill=(235, 235, 245))
y = HEAD
for nm, w, h, d, pat, combos, tiles in rows:
    dr.text((6, y + 40), u'%s\n%dx%d\ndir=%d pat=%d\n组合%d种'
            % (nm, w, h, d, pat, len(combos)), fill=(220, 220, 235))
    x = PAD + 150
    for label, t in tiles:
        sheet.paste(t.convert('RGB'), (x, y), t)
        dr.rectangle([x, y, x + CW, y + CH], outline=(80, 80, 100))
        dr.text((x + 3, y + 2), label, fill=(255, 220, 90))
        x += CW + PAD
    y += CH + LBL + PAD
out = os.path.join(EV, 'gridab103.png')
sheet.save(out)
print('   %s  %s  行数 %d' % (out, sheet.size, len(rows)))

# -*- coding: utf-8 -*-
u"""probe103n.py —— 第103轮侦察 14：**四选一严格对照**（竖向 A0/A1 × 横向 左/居中）。

上一脚本（probe103m）已给出 54:0 —— 但它**预设了竖向 = A1** 才去测横向。
本脚本把两个轴**同时**当未知量：
  对每个"格宽能被 16 整除且 cw ≥ 32"的物件，在 (±1 瓦片) 的窗口里算
  4 个候选 (row_span, col_span) 的"是否全落在黑洞上"，输出 2x2 命中表。
  ★ 若唯一赢家是 (竖向底、横向居中) ⇒ 两个轴都被像素同时定死。

另外给出黑洞的**精确跨度**（不是"包含"），并出两张目视对照图。
"""
import collections
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


rows = []
for n in range(1, 400):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p) or not os.path.isfile(os.path.join(BAC, 'oneshot_map%d.png' % n)):
        continue
    for e in rj(p).get('events', []):
        pgs = e.get('pages') or []
        if not pgs:
            continue
        g = pgs[0].get('graphic') or {}
        if int(g.get('tile_id') or 0) > 0:
            continue
        cn = (g.get('character_name') or '').strip()
        sp = os.path.join(SCENES, 'oneshot_props', cn + '.png')
        if not cn or not os.path.isfile(sp):
            continue
        w, h = Image.open(sp).size
        cw, ch = w // 4, h // 4
        if cw < 32 or cw % TILE or ch % TILE or cw > 128:
            continue
        rows.append(dict(room=n, name=(e.get('name') or ''), cn=cn, x=e['x'], y=e['y'],
                         col=min(3, int(g.get('pattern') or 0)),
                         row=DIR_ROW[int(g.get('direction') or 0)], cw=cw, ch=ch))
print('候选物件（cw>=32 且 16 整除，ch 也被 16 整除）共 %d 个' % len(rows))

cache = {}
imgs = {}


def tile_black(im, W, H, tx, ty):
    if tx < 0 or ty < 0 or tx * TILE + TILE > W or ty * TILE + TILE > H:
        return None
    reg = im.crop((tx * TILE, ty * TILE, tx * TILE + TILE, ty * TILE + TILE))
    return max(reg.getdata(), key=lambda c: max(c))[0:3] == (0, 0, 0)


tbl = collections.Counter()
run_info = []
for r in rows:
    bp = os.path.join(BAC, 'oneshot_map%d.png' % r['room'])
    if r['room'] not in cache:
        im = Image.open(bp).convert('RGB')
        cache[r['room']] = im
    im = cache[r['room']]
    W, H = im.size
    kc, kr = r['cw'] // TILE, r['ch'] // TILE
    cols = {'左': [r['x'] + i for i in range(kc)],
            '居中': [r['x'] - kc // 2 + i for i in range(kc)]}
    rws = {'底': [r['y'] - kr + 1 + i for i in range(kr)],
           '顶': [r['y'] + i for i in range(kr)]}
    hit = {}
    for rk, rsp in rws.items():
        for ck, csp in cols.items():
            vals = [tile_black(im, W, H, tx, ty) for ty in rsp for tx in csp]
            hit[(rk, ck)] = (all(v is True for v in vals) and len(vals) > 0
                             and not any(v is None for v in vals))
    winners = [k for k, v in hit.items() if v]
    tbl[tuple(sorted(winners))] += 1
    if winners == [('底', '居中')]:
        # 精确跨度：该行带上黑洞的连续列区间
        rsp = rws['底']
        run = [tx for tx in range(max(0, r['x'] - 6), min(W // TILE, r['x'] + 7))
               if all(tile_black(im, W, H, tx, ty) for ty in rsp)]
        run_info.append((r, run))

print()
print('=' * 96)
print('2x2 命中表（唯一赢家 = 两个轴同时被像素定死）')
print('=' * 96)
for k, v in tbl.most_common():
    print('  赢家=%-24s %d 例' % (k, v))
print()
print('  ⇒ 「竖向=底对齐 且 横向=居中」唯一赢家：%d 例' % len(run_info))
print('  精确黑洞跨度核对（跨度必须**恰等于** A1 的列集合）：')
ok_run = 0
for r, run in run_info:
    kc = r['cw'] // TILE
    a1 = list(range(r['x'] - kc // 2, r['x'] - kc // 2 + kc))
    a2 = list(range(r['x'], r['x'] + kc))
    if run == a1 and run != a2:
        ok_run += 1
print('    跨度恰 == A1 列集合且 != A2：%d / %d' % (ok_run, len(run_info)))
print('    例：')
for r, run in run_info[:8]:
    print('      room%-4d %-18s %-18s tile=(%d,%d) 格%dx%d 黑洞列=%s'
          % (r['room'], r['name'][:18], r['cn'], r['x'], r['y'], r['cw'], r['ch'], run))

# ---- 目视对照图：取 elevator（48x48）与 door_automatic（48x32）各一 ----
print()
print('=' * 96)
print('目视对照图')
print('=' * 96)
PICK = [('red_elevator', 48), ('door_automatic', 32)]
for cn, _h in PICK:
    hit_rows = [r for r in rows if r['cn'] == cn]
    if not hit_rows:
        continue
    r = hit_rows[0]
    base = Image.open(os.path.join(BAC, 'oneshot_map%d.png' % r['room'])).convert('RGBA')
    kc, kr = r['cw'] // TILE, r['ch'] // TILE
    sp = Image.open(os.path.join(SCENES, 'oneshot_props', cn + '.png')).convert('RGBA')
    w, h = sp.size
    ccw, cch = w // 4, h // 4
    cell = sp.crop((r['col'] * ccw, r['row'] * cch,
                    r['col'] * ccw + ccw, r['row'] * cch + cch))
    Z = 6
    x0 = (r['x'] - kc - 1) * TILE
    y0 = (r['y'] - kr - 1) * TILE
    x1 = (r['x'] + kc + 1) * TILE
    y1 = (r['y'] + kr + 1) * TILE
    panels = []
    for tag, fn in (('A1 底居中', lambda: (r['x'] * TILE + TILE // 2 - ccw // 2,
                                          r['y'] * TILE + TILE - cch)),
                    ('A2 底左', lambda: (r['x'] * TILE, r['y'] * TILE + TILE - cch)),
                    ('A0 顶左', lambda: (r['x'] * TILE, r['y'] * TILE))):
        cv = base.copy()
        cv.alpha_composite(cell, fn())
        p = cv.crop((x0, y0, x1, y1)).resize(((x1 - x0) * Z, (y1 - y0) * Z), Image.NEAREST)
        d = ImageDraw.Draw(p)
        for tx in range(x0 // TILE, x1 // TILE + 1):
            xx = (tx * TILE - x0) * Z
            d.line([xx, 0, xx, p.size[1]], fill=(0, 255, 255, 255))
        for ty in range(y0 // TILE, y1 // TILE + 1):
            yy = (ty * TILE - y0) * Z
            d.line([0, yy, p.size[0], yy], fill=(0, 255, 255, 255))
        # 红框 = 事件瓦片
        d.rectangle([(r['x'] * TILE - x0) * Z, (r['y'] * TILE - y0) * Z,
                     (r['x'] * TILE - x0) * Z + TILE * Z - 1,
                     (r['y'] * TILE - y0) * Z + TILE * Z - 1], outline=(255, 0, 0, 255))
        d.text((6, 4), tag, fill=(255, 255, 0, 255))
        panels.append(p)
    W2 = sum(p.size[0] for p in panels) + 8 * (len(panels) - 1)
    sheet = Image.new('RGBA', (W2, panels[0].size[1]), (20, 20, 26, 255))
    x = 0
    for p in panels:
        sheet.alpha_composite(p, (x, 0))
        x += p.size[0] + 8
    out = os.path.join(EV, 'cmp_wide_%s103.png' % cn)
    sheet.save(out)
    print('  %-18s room%-4d tile=(%d,%d) 格%dx%d -> %s %s'
          % (cn, r['room'], r['x'], r['y'], r['cw'], r['ch'],
             os.path.basename(out), sheet.size))

io.open(os.path.join(EV, 'anchor_cases103.json'), 'w', encoding='utf-8',
        newline='\n').write(json.dumps(
            dict(note='第103轮：锚点的像素判据（宽物件填同宽黑洞）',
                 candidates=len(rows),
                 winner_table={'%s' % ('+'.join(w) if w else '无'): c
                               for w, c in tbl.items()},
                 unique_bottom_center=len(run_info),
                 exact_span_ok=ok_run,
                 cases=[dict(room=r['room'], name=r['name'], sheet=r['cn'],
                             tile=[r['x'], r['y']], cell=[r['cw'], r['ch']],
                             hole_cols=run) for r, run in run_info]),
            ensure_ascii=False, indent=1))
print('  证据 -> _evidence/anchor_cases103.json')

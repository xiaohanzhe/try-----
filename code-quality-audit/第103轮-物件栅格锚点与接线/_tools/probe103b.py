# -*- coding: utf-8 -*-
u"""probe103b.py —— 第103轮侦察 2：把「一格多大」**从数据 + 像素两头对上**。

背景（probe103 已证）：全库 13,830 个事件 page **没有** `character_index`
（page 级键全集已列全，也无 `$`/`index` 之类同义键）⇒ 选块**只能**靠
`character_name` / `direction` / `pattern` 三者。

probe103 顺手量出一个强信号：**148 张图集里只有 `120×200` 不是 32 的整数倍**，
其余（96×128 / 64×64 / 192×192 / 192×128 / 64×128 / 192×256 / 160×160 / 448×320 …）
**全部能被 32 整除** ⇒ 强烈暗示「**32×32 是格**」。

本脚本做三件事
  R1 每张图集的 `w/32 × h/32` 网格，与该图集**实际用到的 (direction, pattern) 组合数**对照
     —— 若"用到的组合数 == 格数"，栅格语义基本坐实；若远超，说明有钳制/包裹
  R2 ★★ **像素级 A/B 锚点**：把若干图集按 32×32 切，生成带编号的放大对照图（肉眼判"格对不对"）
  R3 反向锚点：同样几张图按 **4×4**（第102轮曾假设的 4 列）切，与 R2 并排 —— 谁对一眼可见
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
SPEC = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')
PROPS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'oneshot_props')

ING = json.load(io.open(os.path.join(
    ROOT, 'code-quality-audit', '第102轮-光照与ambient接入', '_evidence',
    'ingest102.json'), encoding='utf-8'))
SIZES = {f['name']: (f['w'], f['h']) for f in ING['files']}


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


use = collections.defaultdict(collections.Counter)      # name -> (dir,pat) -> n
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
        if not nm:
            continue
        if int(g.get('tile_id') or 0) > 0:
            continue
        use[nm][(int(g.get('direction') or 0), int(g.get('pattern') or 0))] += 1

print('=' * 96)
print('R1 每张图集：32×32 网格数 vs 实际用到的 (dir,pattern) 组合数')
print('=' * 96)
print('  %-26s %-11s %-9s %-8s %s' % ('charset', 'size', '32格 w x h', '用到组合', '用到的 (dir,pat)'))
over = []
for nm in sorted(use, key=lambda k: -sum(use[k].values())):
    if nm not in SIZES:
        continue
    w, h = SIZES[nm]
    cw, ch = w // 32, h // 32
    cells = cw * ch
    combos = sorted(use[nm])
    flag = ''
    if len(combos) > cells:
        flag = '  ← 组合数 > 格数'
        over.append((nm, w, h, cells, len(combos)))
    print('  %-26s %-11s %-9s %-8d %s%s'
          % (nm[:26], '%dx%d' % (w, h), '%dx%d=%d' % (cw, ch, cells), len(combos),
             str(combos[:6]) + ('…' if len(combos) > 6 else ''), flag))
print()
print('  ★ 组合数 > 格数 的图集 %d 个：%s' % (len(over), over[:6]))

print()
print('=' * 96)
print('R2/R3 像素级 A/B 锚点：32×32 切 vs 4×4 等分切')
print('=' * 96)


def grid_sheet(name, cell_w, cell_h, cols, rows, zoom=2):
    """按给定格宽高切，编号后拼成一张放大对照图。"""
    p = os.path.join(PROPS, name + '.png')
    im = Image.open(p).convert('RGBA')
    cw = max(1, im.width // cols)
    ch = max(1, im.height // rows)
    W = cols * cw * zoom
    H = rows * ch * zoom
    out = Image.new('RGB', (W, H), (18, 18, 24))
    dr = ImageDraw.Draw(out)
    for r in range(rows):
        for c in range(cols):
            cell = im.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
            cell = cell.resize((cw * zoom, ch * zoom), Image.NEAREST)
            tile = Image.new('RGBA', cell.size, (0, 0, 0, 0))
            tile.alpha_composite(cell)
            out.paste(tile, (c * cw * zoom, r * ch * zoom), tile)
            dr.rectangle([c * cw * zoom, r * ch * zoom,
                          (c + 1) * cw * zoom - 1, (r + 1) * ch * zoom - 1],
                         outline=(90, 90, 110))
            dr.text((c * cw * zoom + 3, r * ch * zoom + 2),
                    '%d,%d' % (c, r), fill=(255, 220, 90))
    return out


SAMPLES = [(nm, SIZES[nm]) for nm in
           ('water_waves_green2', 'sparkle_blue1', 'green_marimo', 'DOORS',
            'jars_new', 'bed', 'tower_tile') if nm in SIZES]
os.makedirs(EV, exist_ok=True)
for nm, (w, h) in SAMPLES:
    a = grid_sheet(nm, 32, 32, max(1, w // 32), max(1, h // 32), zoom=2)
    b = grid_sheet(nm, 0, 0, 4, 4, zoom=2)
    W = a.width + b.width + 24
    H = max(a.height, b.height) + 26
    canvas = Image.new('RGB', (W, H), (12, 12, 16))
    canvas.paste(a, (4, 22), a)
    canvas.paste(b, (a.width + 20, 22), b)
    dr = ImageDraw.Draw(canvas)
    dr.text((6, 5), u'%s %dx%d  ← 左：按 32×32 切（%d×%d 格）  右：按 4×4 等分切'
                   % (nm, w, h, max(1, w // 32), max(1, h // 32)), fill=(235, 235, 245))
    out = os.path.join(EV, 'gridab_%s103.png' % nm)
    canvas.save(out)
    print('   %-22s %-10s -> %s  (%s)' % (nm, '%dx%d' % (w, h),
                                          os.path.basename(out), a.size))

# 汇总大图（纵向堆叠，方便一次看全）
made = [os.path.join(EV, 'gridab_%s103.png' % nm) for nm, _ in SAMPLES]
ims = [Image.open(p) for p in made]
W = max(i.width for i in ims)
H = sum(i.height for i in ims) + 8 * (len(ims) + 1)
sheet = Image.new('RGB', (W + 8, H), (8, 8, 12))
y = 8
for i in ims:
    sheet.paste(i, (8, y))
    y += i.height + 8
    i.close()
big = os.path.join(EV, 'gridab_all103.png')
sheet.save(big)
print()
print('   汇总：%s  %s' % (big, sheet.size))

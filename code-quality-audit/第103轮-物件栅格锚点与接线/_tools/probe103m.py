# -*- coding: utf-8 -*-
u"""probe103m.py —— 第103轮侦察 13：把"门洞法"推广，给**水平锚点**找像素判据。

原理（与门的判据同源）：`bg/oneshot_map<N>.png` 是 tmx 瓦片层的 1:1 合成。
原作会在需要放物件的地方留**黑洞**（`black.tsx` 全黑瓦片）—— 门就是最明显的例子。
⇒ 若某个**宽物件**（cw > 16）正好坐在一块**宽度 == cw/16 瓦片**的黑洞上，
   那么"格的中线贴瓦片中心（A1 居中）"与"格左边贴瓦片左边（A2 底左）"
   会给出**相差 1 瓦片**的落位 ⇒ 哪个与黑洞吻合，就是哪个。

本脚本：
  S1 所有名字含 door/gate 的物件及其格宽（找"宽门/闸门"）
  S2 全量扫 cw > 16 的物件：把它们所在瓦片行的**黑瓦片连续段**求出来，
     比较 A1 / A2 的列跨度是否**恰好**等于黑洞跨度（exactly one match 才有判定力）
"""
import collections
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image, ImageStat                                            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
CELLS = os.path.join(SCENES, 'oneshot_cells')
BAC = os.path.join(SCENES, 'bg')
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


# ---- 收集：room -> [(name, cn, x, y, col, row, cw, ch)] ----
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
        if cw <= TILE:
            continue
        rows.append(dict(room=n, name=(e.get('name') or ''), cn=cn, x=e['x'], y=e['y'],
                         col=min(3, int(g.get('pattern') or 0)),
                         row=DIR_ROW[int(g.get('direction') or 0)], cw=cw, ch=ch))
print('=' * 96)
print('S1 名字含 door/gate 的物件（格宽 >16 的）')
print('=' * 96)
mk = [r for r in rows if re.search(r'door|gate|stairs|ladder', r['name'], re.I)]
print('  宽物件里门/闸门类 %d 个；前 12：' % len(mk))
for r in mk[:12]:
    print('    room%-4d %-18s %-22s tile=(%d,%d) 格=%dx%d'
          % (r['room'], r['name'][:18], r['cn'], r['x'], r['y'], r['cw'], r['ch']))
print('  宽物件总数 %d' % len(rows))

print()
print('=' * 96)
print('S2 黑洞法：cw>16 的物件里，谁的落位能被"黑洞跨度"判出来')
print('=' * 96)
cache = {}
note = collections.Counter()
decisive = []
for r in rows:
    bp = os.path.join(BAC, 'oneshot_map%d.png' % r['room'])
    if r['room'] not in cache:
        im = Image.open(bp).convert('RGB')
        cache[r['room']] = im
    im = cache[r['room']]
    W, H = im.size
    ncol, nrow = W // TILE, H // TILE
    # 该物件纵向覆盖的瓦片行
    ty0 = r['y'] + 1 - r['ch'] // TILE
    ty1 = r['y']
    if ty0 < 0 or ty1 >= nrow or ty1 < 0:
        continue
    # 逐列判"黑"（该列在物件覆盖行里是否全黑）
    def col_black(tx):
        if tx < 0 or tx >= ncol:
            return False
        reg = im.crop((tx * TILE, ty0 * TILE, tx * TILE + TILE, (ty1 + 1) * TILE))
        return max(reg.getdata(), key=lambda c: max(c))[0:3] == (0, 0, 0)

    kcol = r['cw'] // TILE                      # 格占几列（cw 是 16 的倍数时才整除）
    if r['cw'] % TILE:
        note['格宽不是 16 的倍数'] += 1
        continue
    a1 = [r['x'] + TILE // TILE - 1 - (kcol - 1) // 2 + i for i in range(kcol)]   # 居中
    a1 = [r['x'] - (kcol // 2) + i for i in range(kcol)]
    a2 = [r['x'] + i for i in range(kcol)]
    b1 = all(col_black(t) for t in a1)
    b2 = all(col_black(t) for t in a2)
    if b1 == b2:
        note['两候选同判（无判定力）'] += 1
        continue
    note['有判定力'] += 1
    decisive.append((r, b1, b2, a1, a2))
print('  统计：%s' % dict(note))
print('  有判定力的 %d 例；前 15：' % len(decisive))
for r, b1, b2, a1, a2 in decisive[:15]:
    print('    room%-4d %-16s %-20s tile=(%d,%d) 格%dx%d | A1列%s 全黑=%s | A2列%s 全黑=%s'
          % (r['room'], r['name'][:16], r['cn'], r['x'], r['y'], r['cw'], r['ch'],
             a1, b1, a2, b2))
if decisive:
    v1 = sum(1 for d in decisive if d[1] and not d[2])
    v2 = sum(1 for d in decisive if d[2] and not d[1])
    print('  ⇒ A1（居中）全黑 而 A2 不全黑：%d 例；反之：%d 例' % (v1, v2))

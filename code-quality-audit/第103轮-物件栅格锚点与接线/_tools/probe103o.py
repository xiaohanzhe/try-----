# -*- coding: utf-8 -*-
u"""probe103o.py —— 第103轮侦察 15：**顶住反驳** —— 那 9 例"顶对齐赢"是真反例还是代理失真？

probe103n 的 2x2 表里除了 54 例「底+居中」唯一赢，还有
  · 9 例「顶+居中」与「顶+左」同时赢（= 对竖向提出反例）
  · 3 例 4 个候选全赢（无判定力）
必须先排除**代理失真**："黑" 在本脚本里同时意味着两件事 ——
  ① 原作留的**物件洞**（`black.tsx` 瓦片）
  ② 地图**没用到/画到外面的黑**（房间边界的虚空）
② 会让"物件下方一片黑"这种巧合把"顶对齐"判成赢家。

⇒ 本脚本加三条**洞的资格判据**（缺一不可）：
  H1 赢家跨度**全黑**
  H2 跨度**左右（或上下）两侧至少一侧非黑** ⇒ 黑是**局部**的，不是虚空
  H3 跨度**不超过**该物件应有的格数（防"整行都黑"蒙对）
再重跑 2x2 表，并要求**唯一赢家**。
"""
import collections
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                                      # noqa: E402

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
print('候选 %d 个' % len(rows))

cache = {}


def getim(rid):
    if rid not in cache:
        cache[rid] = Image.open(
            os.path.join(BAC, 'oneshot_map%d.png' % rid)).convert('RGB')
    return cache[rid]


def blackat(im, W, H, tx, ty):
    if tx < 0 or ty < 0 or (tx + 1) * TILE > W or (ty + 1) * TILE > H:
        return None
    reg = im.crop((tx * TILE, ty * TILE, tx * TILE + TILE, ty * TILE + TILE))
    return max(reg.getdata(), key=lambda c: max(c))[0:3] == (0, 0, 0)


def hole_ok(im, W, H, xs, ys):
    u"""H1 全黑 + H2 局部（外圈至少一侧非黑）。"""
    vals = [blackat(im, W, H, tx, ty) for ty in ys for tx in xs]
    if not vals or any(v is None for v in vals) or not all(vals):
        return False
    if len(xs) > 1:
        L = [blackat(im, W, H, xs[0] - 1, ty) for ty in ys]
        R = [blackat(im, W, H, xs[-1] + 1, ty) for ty in ys]
        if all(v is True for v in L) and all(v is True for v in R):
            return False                      # 左右都还黑 ⇒ 更像虚空，不算洞
    if len(ys) > 1:
        T = [blackat(im, W, H, tx, ys[0] - 1) for tx in xs]
        B = [blackat(im, W, H, tx, ys[-1] + 1) for tx in xs]
        if all(v is True for v in T) and all(v is True for v in B):
            return False
    return True


tbl = collections.Counter()
winner_cases = collections.defaultdict(list)
for r in rows:
    im = getim(r['room'])
    W, H = im.size
    kc, kr = r['cw'] // TILE, r['ch'] // TILE
    cols = {'左': [r['x'] + i for i in range(kc)],
            '居中': [r['x'] - kc // 2 + i for i in range(kc)]}
    rws = {'底': [r['y'] - kr + 1 + i for i in range(kr)],
           '顶': [r['y'] + i for i in range(kr)]}
    wins = []
    for rk, rsp in rws.items():
        for ck, csp in cols.items():
            if hole_ok(im, W, H, csp, rsp):
                wins.append((rk, ck))
    key = tuple(sorted(wins))
    tbl[key] += 1
    if wins:
        winner_cases[key].append(r)

print()
print('=' * 96)
print('加 H1/H2 资格判据后的 2x2 命中表')
print('=' * 96)
for k, v in tbl.most_common():
    print('  赢家=%-34s %d 例' % ('+'.join('%s%s' % t for t in k) if k else '无', v))
uni = tuple(sorted([('底', '居中')]))
print()
print('  ⇒ 唯一赢家 ==「竖向底对齐 + 横向居中」：%d 例' % tbl.get(uni, 0))
print('  ⇒ 任何含「顶」的赢家：%d 例' % sum(v for k, v in tbl.items()
                                        if any(t[0] == '顶' for t in k)))
print()
print('  含「顶」的赢家明细（看是不是虚空蒙的）：')
for k, v in tbl.items():
    if any(t[0] == '顶' for t in k):
        for r in winner_cases[k][:6]:
            print('    room%-4d %-18s %-18s tile=(%d,%d) 格%dx%d 赢家=%s'
                  % (r['room'], r['name'][:18], r['cn'], r['x'], r['y'],
                     r['cw'], r['ch'], '+'.join('%s%s' % t for t in k)))
uni_cases = winner_cases.get(uni, [])
print()
print('  「底+居中」唯一赢家 %d 例（sheet 分布）：%s'
      % (len(uni_cases), dict(collections.Counter(r['cn'] for r in uni_cases))))

# 精确跨度核对
ok_span = 0
spans = []
for r in uni_cases:
    im = getim(r['room'])
    W, H = im.size
    kc, kr = r['cw'] // TILE, r['ch'] // TILE
    rsp = [r['y'] - kr + 1 + i for i in range(kr)]
    run = [tx for tx in range(max(0, r['x'] - 8), min(W // TILE, r['x'] + 9))
           if all(blackat(im, W, H, tx, ty) is True for ty in rsp)]
    a1 = list(range(r['x'] - kc // 2, r['x'] - kc // 2 + kc))
    a2 = list(range(r['x'], r['x'] + kc))
    if run == a1 and run != a2:
        ok_span += 1
    spans.append((r, run, a1))
print('  精确跨度 == A1 列集合 且 != A2：%d / %d' % (ok_span, len(uni_cases)))

io.open(os.path.join(EV, 'anchor_cases103.json'), 'w', encoding='utf-8',
        newline='\n').write(json.dumps(dict(
            note=u'第103轮：锚点的像素判据 —— 「宽物件填满同宽黑洞」，候选 2 轴 x 2 档，'
                 u'加 H1(全黑)/H2(局部，外圈至少一侧非黑) 资格判据',
            candidates=len(rows),
            winner_table={'+'.join('%s%s' % t for t in k) if k else '无': v
                          for k, v in tbl.items()},
            unique_bottom_center=tbl.get(uni, 0),
            any_top_winner=sum(v for k, v in tbl.items()
                               if any(t[0] == '顶' for t in k)),
            exact_span_ok=ok_span,
            sheet_hist=dict(collections.Counter(r['cn'] for r in uni_cases)),
            cases=[dict(room=r['room'], name=r['name'], sheet=r['cn'], tile=[r['x'], r['y']],
                        cell=[r['cw'], r['ch']], hole_cols=run, a1_cols=a1)
                   for r, run, a1 in spans],
        ), ensure_ascii=False, indent=1))
print('  证据 -> _evidence/anchor_cases103.json')

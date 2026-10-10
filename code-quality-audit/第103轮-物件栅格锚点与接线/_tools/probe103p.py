# -*- coding: utf-8 -*-
u"""probe103p.py —— 第103轮侦察 16：**最严判据** —— 黑洞跨度必须「恰等于」格的落位跨度。

前面已排除"虚空蒙对"（probe103o 的 H2）。这里再顶一层：
  ① 横向上把第三档「右对齐」也当候选（= 3 档），防止"只有左/居中被测过"的漏洞；
  ② 判据从"包含"升级成**恰等**：该行带里含格落位的**黑洞连续段**必须
     **长度与位置都等于**该候选的列集合（差一列即不算）。
只有**唯一**候选满足才算这一例"有判定力"。
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


def blk(im, W, H, tx, ty):
    if tx < 0 or ty < 0 or (tx + 1) * TILE > W or (ty + 1) * TILE > H:
        return None
    reg = im.crop((tx * TILE, ty * TILE, tx * TILE + TILE, ty * TILE + TILE))
    return max(reg.getdata(), key=lambda c: max(c))[0:3] == (0, 0, 0)


def rowband(im, W, H, ys, tx):
    return all(blk(im, W, H, tx, ty) is True for ty in ys)


def run_of(im, W, H, ys, xs):
    u"""含 xs 的**极大**全黑列连续段（该行带内）。"""
    if not all(rowband(im, W, H, ys, x) for x in xs):
        return None
    a = xs[0]
    while rowband(im, W, H, ys, a - 1) if a - 1 >= 0 else False:
        a -= 1
    b = xs[-1]
    while b + 1 < W // TILE and rowband(im, W, H, ys, b + 1):
        b += 1
    return list(range(a, b + 1))


tbl = collections.Counter()
uni_cases = []
for r in rows:
    im = getim(r['room'])
    W, H = im.size
    kc, kr = r['cw'] // TILE, r['ch'] // TILE
    cols = {'左': [r['x'] + i for i in range(kc)],
            '居中': [r['x'] - kc // 2 + i for i in range(kc)],
            '右': [r['x'] - kc + 1 + i for i in range(kc)]}
    rws = {'底': [r['y'] - kr + 1 + i for i in range(kr)],
           '顶': [r['y'] + i for i in range(kr)]}
    wins = []
    for rk, rsp in rws.items():
        for ck, csp in cols.items():
            run = run_of(im, W, H, rsp, csp)
            if run is not None and run == csp:          # ★ 恰等
                wins.append((rk, ck))
    key = tuple(sorted(wins))
    tbl[key] += 1
    if key == (('底', '居中'),):
        uni_cases.append(r)

print()
print('=' * 96)
print('「黑洞跨度恰等于格落位跨度」的赢家表')
print('=' * 96)
for k, v in tbl.most_common(12):
    print('  赢家=%-40s %d 例' % ('+'.join('%s%s' % t for t in k) if k else '无', v))
print()
print('  ⇒ 唯一赢家 = 底+居中：%d 例' % tbl.get((('底', '居中'),), 0))
print('  ⇒ 唯一赢家 = 底+左  ：%d 例' % tbl.get((('底', '左'),), 0))
print('  ⇒ 唯一赢家 = 底+右  ：%d 例' % tbl.get((('底', '右'),), 0))
print('  ⇒ 任何含「顶」      ：%d 例'
      % sum(v for k, v in tbl.items() if any(t[0] == '顶' for t in k)))
print()
print('  样例（前 10）：')
for r in uni_cases[:10]:
    print('    room%-4d %-18s %-16s tile=(%d,%d) 格%dx%d'
          % (r['room'], r['name'][:18], r['cn'], r['x'], r['y'], r['cw'], r['ch']))
print('  sheet 分布：%s' % dict(collections.Counter(r['cn'] for r in uni_cases)))
print('  room 分布（前 6）：%s'
      % collections.Counter(r['room'] for r in uni_cases).most_common(6))

io.open(os.path.join(EV, 'anchor_cases103.json'), 'w', encoding='utf-8',
        newline='\n').write(json.dumps(dict(
            note=u'第103轮：锚点的像素判据。候选 = 竖向{底,顶} x 横向{左,居中,右} 共 6 档；'
                 u'判据 = 该行带内「含格落位的极大全黑列段」**恰等于**格的列集合'
                 u'（差一列即不算）；只认**唯一**赢家。q=「黑」的原作含义 = '
                 u'`black.tsx` 瓦片（原作给物件留的洞）。',
            candidates=len(rows),
            winner_table={'+'.join('%s%s' % t for t in k) if k else '无': v
                          for k, v in tbl.most_common()},
            unique_bottom_center=tbl.get((('底', '居中'),), 0),
            unique_bottom_left=tbl.get((('底', '左'),), 0),
            unique_bottom_right=tbl.get((('底', '右'),), 0),
            any_top_winner=sum(v for k, v in tbl.items()
                               if any(t[0] == '顶' for t in k)),
            sheet_hist=dict(collections.Counter(r['cn'] for r in uni_cases)),
            room_hist=dict(collections.Counter(r['room'] for r in uni_cases)),
            cases=[dict(room=r['room'], name=r['name'], sheet=r['cn'],
                        tile=[r['x'], r['y']], cell=[r['cw'], r['ch']],
                        col=min(3, r['col']), row=r['row']) for r in uni_cases],
        ), ensure_ascii=False, indent=1))
print('  证据 -> _evidence/anchor_cases103.json')

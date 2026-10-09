# -*- coding: utf-8 -*-
u"""probe102d.py —— 第102轮侦察 4：把「184 张近黑」逐张**归因**（不许只数异常）。

分类（互斥，按优先级）：
  A 空转黑   ：**有瓦片**但摆放的瓦片**全透明** ⇒ 合成丢了内容（我们的锅）
  B 无底黑   ：瓦片数为 0，且该地图**不在** `oneshot_map_colors.json` 里 ⇒ 纯黑底
  C 空房黑   ：瓦片数为 0，但有底色 ⇒ 房间本来就空（靠 panorama / 事件）
  D 暗但忠实 ：有**不透明**瓦片，均亮度低 ⇒ 原作瓦片本身暗（忠实）
  E 正常     ：均亮度 ≥ 90

同时交叉核对第101轮的 manifest（`used` 字段）是否与本次重算一致（对账）。
"""
import collections
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
OB = os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景', '_tools', 'os_bg100.py')
spec = importlib.util.spec_from_file_location('os_bg100', OB)
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)

REPO_BG = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'bg')
MAN = os.path.join(ROOT, 'code-quality-audit', '第101轮-OneShot背景落盘与场景接线',
                   '_evidence', 'bg_manifest101.json')

colors = o.load_map_colors()
man = {}
if os.path.isfile(MAN):
    man = {int(e['room_id']): e for e in json.load(io.open(MAN, encoding='utf-8'))['rows']}

_alpha_cache = {}


def tile_alpha(ip, im, t, lid):
    k = (ip, lid)
    if k in _alpha_cache:
        return _alpha_cache[k]
    col, row = lid % t['columns'], lid // t['columns']
    r = im.crop((col * t['tw'], row * t['th'],
                 col * t['tw'] + t['tw'], row * t['th'] + t['th']))
    a = r.getchannel('A')
    lo, hi = a.getextrema()
    v = (hi > 0, lo > 0)                       # (有实心像素, 整块不透明)
    _alpha_cache[k] = v
    return v


rows = []
for n in range(1, 264):
    mp = os.path.join(o.MAPS, 'map%d.tmx' % n)
    if not os.path.isfile(mp):
        continue
    m = o.parse_map(mp)
    imgs = []
    tsx_names = []
    for fg, src in m['tilesets']:
        tsx = os.path.normpath(os.path.join(o.MAPS, src))
        tsx_names.append(os.path.basename(tsx))
        if not os.path.isfile(tsx):
            imgs.append((fg, None, None, None))
            continue
        t = o.parse_tsx(tsx)
        ip = o.resolve_img(os.path.dirname(tsx), t['img'])
        imgs.append((fg, t, ip, o.xnb_rgba(ip) if ip else None))
    placed = opaque = solid = 0
    for lname, gids in m['layers']:
        for idx, g in enumerate(gids):
            if g <= 0:
                continue
            placed += 1
            cur = None
            for e in imgs:
                if g >= e[0]:
                    cur = e
                else:
                    break
            if cur is None or cur[2] is None or cur[3] is None:
                continue
            fg, t, ip, im = cur
            lid = g - fg
            if lid >= t['tilecount']:
                continue
            any_a, all_a = tile_alpha(ip, im, t, lid)
            if any_a:
                opaque += 1
            if all_a:
                solid += 1
    p = os.path.join(REPO_BG, 'oneshot_map%d.png' % n)
    lum = None
    if os.path.isfile(p):
        im2 = Image.open(p).convert('RGB')
        px = im2.resize((min(im2.width, 160), min(im2.height, 160))).getdata()
        lum = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px) / float(len(px))
    rows.append(dict(n=n, placed=placed, opaque=opaque, solid=solid, lum=lum,
                     has_color=n in colors, tsx=tsx_names,
                     blanks=[x for x in tsx_names if x.startswith('blank') or x == 'black.tsx'],
                     man_used=(man[n]['used'] if n in man else None)))

print('=' * 78)
print('归因（263 张）')
print('=' * 78)


def cls(r):
    if r['opaque'] > 0:
        return 'E 正常' if (r['lum'] or 0) >= 90 else 'D 暗但忠实'
    if r['placed'] > 0:
        return 'A 空转黑'
    return 'B 无底黑' if not r['has_color'] else 'C 空房黑'


buck = collections.Counter(cls(r) for r in rows)
for k in sorted(buck):
    print('   %-12s %3d 张' % (k, buck[k]))
print('   合计 %d' % sum(buck.values()))

print()
print('--- A 空转黑（有瓦片但全透明）明细 ---')
A = [r for r in rows if cls(r) == 'A 空转黑']
for r in A[:25]:
    print('   map%-4d placed=%-6d opaque=0  均亮度 %5s  tsx=%s' %
          (r['n'], r['placed'], ('%.1f' % r['lum']) if r['lum'] is not None else 'NA', r['tsx']))
print('   A 共 %d 张；其中用 blank*/black.tsx 的 = %d' %
      (len(A), sum(1 for r in A if r['blanks'])))

print()
print('--- C 空房黑（无瓦片、有底色）---')
C = [r for r in rows if cls(r) == 'C 空房黑']
print('   共 %d 张：%s' % (len(C), [r['n'] for r in C][:30]))

print()
print('--- B 无底黑（无瓦片、无底色）---')
B = [r for r in rows if cls(r) == 'B 无底黑']
print('   共 %d 张：%s' % (len(B), [r['n'] for r in B][:30]))

print()
print('--- D 暗但忠实：均亮度最低的 15 张（有实心瓦片）---')
D = sorted([r for r in rows if cls(r) == 'D 暗但忠实'], key=lambda r: r['lum'])
for r in D[:15]:
    print('   map%-4d placed=%-6d opaque=%-6d solid=%-6d 均亮度 %5.1f' %
          (r['n'], r['placed'], r['opaque'], r['solid'], r['lum']))
print('   D 共 %d 张，均亮度区间 %.1f ~ %.1f' %
      (len(D), D[0]['lum'], D[-1]['lum']) if D else '')

print()
print('=' * 78)
print('对账：本次重算 placed vs 第101轮 manifest 的 used')
print('=' * 78)
bad = [r for r in rows if r['man_used'] is not None and r['man_used'] != r['placed']]
print('   不一致 %d 张 %s' % (len(bad), [(r['n'], r['man_used'], r['placed']) for r in bad[:6]]))
print('   manifest 覆盖 %d 张' % sum(1 for r in rows if r['man_used'] is not None))

print()
print('=' * 78)
print('全谱：每档「均亮度」的 opaque 分布（看黑是不是只发生在 opaque==0）')
print('=' * 78)
tbl = collections.defaultdict(lambda: [0, 0])
for r in rows:
    if r['lum'] is None:
        continue
    k = int(r['lum'] // 32)
    tbl[k][0 if r['opaque'] > 0 else 1] += 1
print('   %-10s %-12s %s' % ('亮度档', '有实心瓦片', '无实心瓦片'))
for k in sorted(tbl):
    print('   %3d~%-6d %-12d %d' % (k * 32, k * 32 + 31, tbl[k][0], tbl[k][1]))

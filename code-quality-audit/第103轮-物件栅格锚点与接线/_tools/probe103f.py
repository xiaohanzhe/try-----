# -*- coding: utf-8 -*-
u"""probe103f.py —— 第103轮侦察 6：找**锚点**的 ground truth（多部件物件）。

要接线的下一步是"格画到哪儿"。RPG Maker 的角色精灵惯例是
**水平居中于所在格、底边对齐所在格底部**（tile size = 16），但这只是惯例，
必须有**可验证的锚点**。

★ 最硬的锚点 = **由多个事件拼成的一个物件**：若某个物件的若干部件是分开的事件，
  正确的锚点会让它们**严丝合缝地拼成一体**，错一像素都会错位。

本脚本：
  A 按"可见物件数"排前列的房，打印全部 name/x/y/cn/dir/pat
  B 专门找 name 里含 bed/door/window/desk/table 等**成套命名**的事件，按房分组
  C 找同名同图集、坐标相邻的事件对（潜在的"拼接件"）
"""
import collections
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')
GEO = json.load(io.open(os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes',
                                     '_room_geometry.json'), encoding='utf-8'))['rooms']


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


rooms = {}
for n in range(1, 264):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p):
        continue
    out = []
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
        out.append(dict(name=(e.get('name') or ''), x=e.get('x'), y=e.get('y'),
                        cn=nm, d=int(g.get('direction') or 0),
                        p=int(g.get('pattern') or 0),
                        op=int(g.get('opacity') or 0)))
    if out:
        rooms[n] = out

print('=' * 96)
print('A 可见物件最多的 10 间房')
print('=' * 96)
top = sorted(rooms.items(), key=lambda kv: -len(kv[1]))[:10]
for rid, evs in top:
    g = GEO.get('oneshot:%d' % rid, {})
    print('  room %-4d  %-22s %dx%d 物件 %d' % (rid, g.get('name'), g.get('w', 0),
                                                g.get('h', 0), len(evs)))
print()
rid, evs = top[0]
print('  --- room %d 全部可见物件 ---' % rid)
for e in sorted(evs, key=lambda e: (e['y'], e['x'])):
    print('     %-22s x=%-4d y=%-4d %-24s dir=%d pat=%d op=%d'
          % (e['name'][:22], e['x'], e['y'], e['cn'][:24], e['d'], e['p'], e['op']))

print()
print('=' * 96)
print('B 成套命名（同一物件拆成多个事件）—— 锚点的 ground truth')
print('=' * 96)
KEY = re.compile(r'(bed|desk|table|window|door|sofa|couch|piano|bookshelf|shelf|'
                 r'fridge|stove|sink|toilet|bathtub|mirror|clock|painting|poster|'
                 r'carpet|rug|curtain|stairs|plant|tree|fence|sign)', re.I)
hits = collections.defaultdict(list)
for rid, evs in rooms.items():
    for e in evs:
        m = KEY.search(e['name'])
        if m:
            hits[m.group(1).lower()].append((rid, e['name'], e['x'], e['y'], e['cn']))
for k in sorted(hits, key=lambda k: -len(hits[k])):
    print('  %-11s %3d 条  例：%s' % (k, len(hits[k]), hits[k][:3]))

print()
print('同一房内**同名图集且坐标相邻**的事件对（潜在拼接件）：')
pairs = []
for rid, evs in rooms.items():
    for i in range(len(evs)):
        for j in range(i + 1, len(evs)):
            a, b = evs[i], evs[j]
            if a['cn'] != b['cn']:
                continue
            if abs(a['x'] - b['x']) + abs(a['y'] - b['y']) != 1:
                continue
            pairs.append((rid, a['name'], b['name'], a['x'], a['y'], b['x'], b['y'],
                          a['cn'], a['d'], a['p'], b['d'], b['p']))
print('  共 %d 对；前 20：' % len(pairs))
for t in pairs[:20]:
    print('     room%-4d %-18s @(%d,%d)  ↔  %-18s @(%d,%d)  %s d=%d/%d p=%d/%d'
          % (t[0], t[1][:18], t[3], t[4], t[2][:18], t[5], t[6],
             t[7], t[8], t[10], t[9], t[11]))

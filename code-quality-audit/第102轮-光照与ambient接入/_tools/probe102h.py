# -*- coding: utf-8 -*-
u"""probe102h.py —— 第102轮侦察 8（**修正上一支的解析 bug**）：房间物件有多少、怎么画。

★ 上一支 probe102g 把 `graphic` 读在事件顶层 ⇒ 报 `tile_id>0 = 0`（**假 0**）。
  真值在 `pages[i].graphic`。本支修正，并把「gid 空间」与「坐标单位」两件事**用锚点验证**。

 U1 修正后的事件统计（tile_id / character_name / 空）
 U2 character_name 全谱（→ 需要哪种图集）
 U3 ★ 锚点：`tile_id` 是否落在 tmx 的 firstgid 空间内（同图集的 gid 换算）
 U4 ★ 锚点：事件坐标是否为 tmx 瓦片坐标（max x,y vs map w,h）
 U5 每个事件的页面数 / `always_on_top` / `opacity` 分布（决定画法）
 U6 `content/npc` / `facepics` 里有什么（character_name 的图集在哪）
"""
import collections
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OSD = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
       r'\OneShot.World.Machine.Edition.Build.16512634')
MAPS = os.path.join(OSD, 'gamedata', 'maps')
_TAG = re.compile(r'<(\w+)([^>]*?)/?>')
_ATTR = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


def parse_map(path):
    s = io.open(path, encoding='utf-8', newline='').read()
    a = dict(_ATTR.findall(re.search(r'<map\b([^>]*)>', s).group(1)))
    ts = []
    for name, tail in _TAG.findall(s):
        if name == 'tileset':
            at = dict(_ATTR.findall(tail))
            ts.append((int(at['firstgid']), at['source']))
    return dict(w=int(a['width']), h=int(a['height']),
                tw=int(a['tilewidth']), th=int(a['tileheight']), tilesets=ts)


tile_ev = char_ev = empty_ev = tot_ev = 0
chars = collections.Counter()
tids = collections.Counter()
pages_c = collections.Counter()
always_top = 0
n_ev_room = 0
oob = []
tid_ok = tid_bad = 0
mismatch = []
for n in range(1, 264):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p):
        continue
    d = rj(p)
    evs = d.get('events', [])
    if not evs:
        continue
    n_ev_room += 1
    m = parse_map(os.path.join(MAPS, 'map%d.tmx' % n))
    maxgid = 1 + 48 * (len(m['tilesets']) - 1) + 295
    for e in evs:
        tot_ev += 1
        pgs = e.get('pages') or []
        pages_c[len(pgs)] += 1
        g = (pgs[0].get('graphic') if pgs else None) or {}
        tid = int(g.get('tile_id') or 0)
        cn = (g.get('character_name') or '').strip()
        if tid > 0:
            tile_ev += 1
            tids[tid] += 1
            if tid <= maxgid:
                tid_ok += 1
            else:
                tid_bad += 1
        elif cn:
            char_ev += 1
            chars[cn] += 1
        else:
            empty_ev += 1
        if pgs and pgs[0].get('always_on_top'):
            always_top += 1
        x, y = e.get('x'), e.get('y')
        if isinstance(x, int) and isinstance(y, int):
            if x >= m['w'] or y >= m['h']:
                oob.append((n, e.get('name'), x, y, m['w'], m['h']))

print('=' * 78)
print('U1 修正后的事件统计')
print('=' * 78)
print('  有事件的房 = %d / 263' % n_ev_room)
print('  事件总数   = %d' % tot_ev)
print('  tile_id>0（家具/地形/墙） = %d (%.1f%%)' % (tile_ev, 100.0 * tile_ev / tot_ev))
print('  character_name（角色图）  = %d (%.1f%%)' % (char_ev, 100.0 * char_ev / tot_ev))
print('  空图形（触发器）          = %d (%.1f%%)' % (empty_ev, 100.0 * empty_ev / tot_ev))
print('  always_on_top = %d' % always_top)

print()
print('=' * 78)
print('U2 character_name 全谱')
print('=' * 78)
print('  不同名字 %d 个' % len(chars))
for k, v in chars.most_common(40):
    print('     %-34s %d' % (k, v))

print()
print('=' * 78)
print('U3 锚点：tile_id 是否落在该图 tmx 的 gid 空间内')
print('=' * 78)
print('  落在空间内 = %d ；超出 = %d' % (tid_ok, tid_bad))
print('  tile_id top15:', tids.most_common(15))
print('  ★ 说明：firstgid 规律 1 + 48k（autotile 槽）/ tileset 槽连续')
s0 = parse_map(os.path.join(MAPS, 'map2.tmx'))
print('  map2 tilesets =', s0['tilesets'])

print()
print('=' * 78)
print('U4 锚点：事件坐标单位')
print('=' * 78)
print('  越界事件数 = %d' % len(oob))
for r in oob[:10]:
    print('     map%-4d %-24s (%s,%s) 但 map 是 %sx%s' % r)

print()
print('=' * 78)
print('U5 页面数分布')
print('=' * 78)
for k in sorted(pages_c):
    print('   pages=%d : %d' % (k, pages_c[k]))

print()
print('=' * 78)
print('U6 character_name 的图集在哪')
print('=' * 78)
for sub in ['npc', 'facepics', 'footprints']:
    d = os.path.join(OSD, 'content', sub)
    if os.path.isdir(d):
        fs = sorted(os.listdir(d))
        print('--- content/%s (%d) ---' % (sub, len(fs)))
        for x in fs[:18]:
            print('     %-42s %s' % (x, os.path.getsize(os.path.join(d, x))))
        if len(fs) > 18:
            print('     ... 另 %d' % (len(fs) - 18))

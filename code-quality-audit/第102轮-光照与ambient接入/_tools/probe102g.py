# -*- coding: utf-8 -*-
u"""probe102g.py —— 第102轮侦察 7：定量「房间物件」这个真缺口，并找参考图。

 T1 用户补发目录 `…\\项目文件夹\\assets\\` 的**文件名清单**（绝不读内容；里面混有工作文件）
 T2 `Content/` 剩下的目录（有没有 characters / bgm 等）
 T3 263 间房的**事件统计**：事件数 / `tile_id>0`（家具）vs `character_name`（角色）
 T4 事件坐标单位与 `_index.json` 里 oneshot 房间的 `objects` 现状
 T5 仓库侧 `scene_system` 消费 `objects` 的形状（只读少量行）
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
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))

print('=' * 78)
print('T1 用户补发目录（只列名字）')
print('=' * 78)
for cand in [r'C:\Users\23002\Desktop\项目文件夹\assets']:
    if os.path.isdir(cand):
        fs = sorted(os.listdir(cand))
        print('%s  (%d 项)' % (cand, len(fs)))
        for f in fs[:60]:
            p = os.path.join(cand, f)
            print('   %-50s %s' % (f, os.path.getsize(p) if os.path.isfile(p) else '<DIR>'))
        if len(fs) > 60:
            print('   ... 另 %d' % (len(fs) - 60))
    else:
        print('(缺)', cand)

print()
print('=' * 78)
print('T2 Content 全目录（含被截断的 7 项）')
print('=' * 78)
c = os.path.join(OSD, 'content')
for f in sorted(os.listdir(c)):
    p = os.path.join(c, f)
    print('   %-42s %s' % (f, '<DIR>' if os.path.isdir(p) else os.path.getsize(p)))

print()
print('=' * 78)
print('T3 263 间房的事件统计')
print('=' * 78)
tot_ev = 0
n_rooms_ev = 0
tile_ev = char_ev = empty_ev = 0
chars = collections.Counter()
tile_ids = collections.Counter()
big = []
for n in range(1, 264):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p):
        continue
    d = json.loads(re.sub(r',(\s*[}\]])', r'\1',
                          io.open(p, encoding='utf-8', newline='').read()))
    evs = d.get('events', d if isinstance(d, list) else [])
    if isinstance(evs, dict):
        evs = [v for v in evs.values()]
    if not evs:
        continue
    n_rooms_ev += 1
    tot_ev += len(evs)
    for e in evs:
        g = e.get('graphic') or {}
        tid = g.get('tile_id') or 0
        cn = (g.get('character_name') or '').strip()
        if tid and tid > 0:
            tile_ev += 1
            tile_ids[tid] += 1
        elif cn:
            char_ev += 1
            chars[cn] += 1
        else:
            empty_ev += 1
    if len(evs) > 40:
        big.append((n, len(evs)))
print('  有事件的房 = %d / 263' % n_rooms_ev)
print('  事件总数   = %d' % tot_ev)
print('  图形=tile_id>0（家具/地形） = %d' % tile_ev)
print('  图形=character_name（角色） = %d' % char_ev)
print('  图形=空                     = %d' % empty_ev)
print('  character_name top20:', chars.most_common(20))
print('  tile_id top12:', tile_ids.most_common(12))
print('  事件最多的房:', sorted(big, key=lambda x: -x[1])[:12])

print()
print('=' * 78)
print('T4 单间房的事件样本（map2 前 2 个）+ 坐标范围')
print('=' * 78)
p = os.path.join(MAPS, 'events_map2.json')
d = json.loads(re.sub(r',(\s*[}\]])', r'\1', io.open(p, encoding='utf-8', newline='').read()))
evs = d.get('events', [])
print('  map2 事件数 =', len(evs))
for e in evs[:2]:
    s = json.dumps(e, ensure_ascii=False)
    print('  %s' % s[:900])
xs = [e.get('x') for e in evs if isinstance(e.get('x'), int)]
ys = [e.get('y') for e in evs if isinstance(e.get('y'), int)]
print('  x 范围 %s..%s   y 范围 %s..%s' % (min(xs), max(xs), min(ys), max(ys)))

print()
print('=' * 78)
print('T5 仓库侧：oneshot 房间 objects 现状 + scene_system 消费形状')
print('=' * 78)
idx = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_index.json')
dd = json.loads(io.open(idx, encoding='utf-8', newline='').read())
ch = dd.get('chapters', {})
os_area = ch.get('oneshot', {}).get('areas', {})
tot = withobj = 0
for area, av in os_area.items():
    for sid, sv in (av.get('scenes') or {}).items():
        tot += 1
        if sv.get('objects'):
            withobj += 1
print('  oneshot 场景 = %d，其中 objects 非空 = %d' % (tot, withobj))
print('  scene 键 =', sorted((list(os_area.values())[0]['scenes'].values()))[0].keys()
      if os_area else 'NA')

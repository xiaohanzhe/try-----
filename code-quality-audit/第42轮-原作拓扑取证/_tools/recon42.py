# -*- coding: utf-8 -*-
"""第42轮 · 只读：① 五章房间名全表 + 按语义分组  ② 小镇相关 room_goto 边  ③ 门/传送门对象"""
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
DRW = r'E:\Download\_tmp\drw'
CH = ['chapter1_windows', 'chapter2_windows', 'chapter3_windows',
      'chapter4_windows', 'chapter5_windows']

print('=' * 76)
print('1. 五章房间名按前缀归类（看"小镇"是哪些）')
print('=' * 76)
allrooms = {}
for c in CH:
    d = json.loads(open(os.path.join(DRW, c, 'rooms_map.json'), 'rb').read().decode('utf-8'))
    allrooms[c] = [r['name'] for r in d['rooms']]
    print('  %-18s rooms=%d' % (c, len(allrooms[c])))

# ch1 全表（147 行有点多，但最有用）
print('\n--- ch1 房间名全表（147）---')
for i, n in enumerate(allrooms[CH[0]]):
    print('   %3d  %s' % (i, n))

print('\n--- ch1 名字含 town/hometown 的 ---')
tw = [n for n in allrooms[CH[0]] if re.search(r'town', n, re.I)]
print('  ', tw)

print('\n--- 五章各自含 town 的 ---')
for c in CH:
    t = [n for n in allrooms[c] if re.search(r'town', n, re.I)]
    print('  %-18s %d 个: %s' % (c, len(t), t[:30]))

print()
print('=' * 76)
print('2. ch1 连接边里涉及 town 的（来自上一轮 edges41.json）')
print('=' * 76)
ej = os.path.join(DRW, CH[0], 'edges41.json')
if os.path.isfile(ej):
    d = json.load(open(ej, 'rb'))
    for e in d['edges']:
        to = e.get('to') or ''
        if re.search(r'town|school|hometown|kris|torhouse|hospital|church|alphys',
                     (to + ' ' + e['from']), re.I):
            print('   %-46s --%s--> %s' % (e['from'][:46], e['kind'], to))
    print('  （共 %d 条边里筛出上面这些）' % d['n_edges'])

print()
print('=' * 76)
print('3. 门 / 传送门 / 暗世界入口 相关对象（rooms_map 的 instances）')
print('=' * 76)
objs = Counter()
for c in CH:
    d = json.loads(open(os.path.join(DRW, c, 'rooms_map.json'), 'rb').read().decode('utf-8'))
    for r in d['rooms']:
        for L in (r.get('layers') or []):
            for v in (L.get('instances') or []):
                objs[v] += 1
pat = re.compile(r'door|portal|closet|dark|gate|warp|exit|entrance|fountain', re.I)
hit = sorted([k for k in objs if pat.search(k)])
print('  含门/传送/暗世界线索的实例名 %d 个：' % len(hit))
for k in hit[:70]:
    print('    %-46s x%d' % (k, objs[k]))

print()
print('=' * 76)
print('4. ch1 里 room_krisroom / room_dark1 这类关键房间的层与实例')
print('=' * 76)
d1 = json.loads(open(os.path.join(DRW, CH[0], 'rooms_map.json'), 'rb').read().decode('utf-8'))
want = ('room_krisroom', 'room_dark1', 'room_insidecloset', 'room_town_school',
        'room_schooldoor', 'room_alphysclass', 'room_town_mid')
for r in d1['rooms']:
    if r['name'] not in want:
        continue
    print('  [%d] %s  %dx%d' % (r['index'], r['name'], r['width'], r['height']))
    for L in (r.get('layers') or []):
        ex = []
        if L.get('instances'):
            ex.append('inst=' + ','.join(L['instances'][:8]))
        if L.get('bg_sprite'):
            ex.append('bg=' + L['bg_sprite'])
        if L.get('asset_sprites'):
            ex.append('asset=%d个' % len(L['asset_sprites']))
        if L.get('tiles'):
            ex.append('tiles=%d' % len(L['tiles']))
        print('      %-34s %-10s d=%-12s %s'
              % (L['name'][:34], L['type'], L['depth'], ' '.join(ex)))

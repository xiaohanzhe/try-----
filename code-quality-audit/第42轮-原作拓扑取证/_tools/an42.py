# -*- coding: utf-8 -*-
"""第42轮 · 分析 probe42.json：ch1 现实世界 32 房间的实例构成 + 入口/门/记号坐标"""
import io
import json
import os
import re
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
P = r'E:\Download\_tmp\drw\chapter1_windows\probe42.json'
d = json.loads(open(P, 'rb').read().decode('utf-8')
               .replace(': True', ': true').replace(': False', ': false'))

print('=' * 78)
print('A. 32 房间实例数 + 对象直方图 Top10')
print('=' * 78)
for r in d['rooms']:
    c = Counter(i['obj'] for i in r['instances'])
    top = ', '.join('%s x%d' % (k, v) for k, v in c.most_common(10))
    print('  [%2d] %-24s %5dx%-5d n=%-4d  %s'
          % (r['index'], r['name'], r['w'], r['h'], r['n_inst'], top))

print()
print('=' * 78)
print('B. 关键实例（门 / 记号 / 事件 / NPC / 存档 / 车）坐标明细')
print('=' * 78)
KEYS = re.compile(r'door|marker|town_event|carcutscene|cutscene|savepoint|npc|'
                  r'mainchara|musicer|sdr|event$|_event|interact|closet', re.I)
for r in d['rooms']:
    rows = [i for i in r['instances'] if KEYS.search(i['obj'])]
    if not rows:
        continue
    print('\n  [%2d] %s  %dx%d' % (r['index'], r['name'], r['w'], r['h']))
    for i in rows:
        print('       %-34s x=%-9s y=%-9s  %s' % (i['obj'], i['x'], i['y'], i['layer']))

print()
print('=' * 78)
print('C. 全部实例名去重计数（32 房间）')
print('=' * 78)
tot = Counter()
for r in d['rooms']:
    for i in r['instances']:
        tot[i['obj']] += 1
print('  去重对象数=%d  实例总数=%d' % (len(tot), d['n_inst']))
for k, v in tot.most_common(60):
    print('    %-38s x%d' % (k, v))

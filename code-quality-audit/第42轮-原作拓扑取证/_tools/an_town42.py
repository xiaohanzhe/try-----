# -*- coding: utf-8 -*-
"""第42轮 · 五章 conn42b.json 汇总：① 全量统计 ② 涉及 town 的边 ③ 现实世界 vs 暗世界边界"""
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
DRW = r'E:\Download\_tmp\drw'
CH = ['chapter1_windows', 'chapter2_windows', 'chapter3_windows',
      'chapter4_windows', 'chapter5_windows']

print('=' * 78)
print('A. 五章 conn42b 总览')
print('=' * 78)
data = {}
tot_items = 0
for c in CH:
    d = json.loads(open(os.path.join(DRW, c, 'conn42b.json'), 'rb').read().decode('utf-8'))
    data[c] = d
    tot_items += d['n_items']
    print('  %-18s rooms=%-4d codes=%-6d with_rg=%-4d items=%-4d'
          % (c, d['n_rooms'], d['n_codes'], d['n_with_room_goto'], d['n_items']))
print('  items 合计 = %d' % tot_items)

print()
print('=' * 78)
print('B. 五章门对象分布（哪个 obj_door* 承担连接）')
print('=' * 78)
for c in CH:
    cnt = Counter()
    for it in data[c]['items']:
        code = it['code']
        m = re.match(r'gml_Object_(\w+?)_(Alarm|Step|Create|Other)', code)
        cnt[m.group(1) if m else code] += 1
    print('  %-18s %s' % (c, dict(cnt.most_common(10))))

print()
print('=' * 78)
print('C. 五章里「涉及 town 的门表条目」（src 或 dst 名字含 town）')
print('=' * 78)
for c in CH:
    d = data[c]
    rn = d['room_names']
    rows = []
    for it in d['items']:
        s = rn[it['src']] if 0 <= it['src'] < len(rn) else ''
        t = rn[it['dst']] if 0 <= it['dst'] < len(rn) else ''
        if 'town' in s.lower() or 'town' in t.lower():
            rows.append((it['src'], s, it['dst'], t, it['op'], it['code']))
    print('\n  ## %s   %d 条' % (c, len(rows)))
    for s, sn, t, tn, op, code in rows:
        print('      %-28s -> %-28s  [%s] %s' % (sn, tn, op, code.replace('gml_Object_', '')))

print()
print('=' * 78)
print('D. 五章房间名：现实世界（非 dark/field/forest/cc/castle 等）分类计数')
print('=' * 78)
for c in CH:
    rn = data[c]['room_names']
    pat = re.compile(r'dark|field|forest|_cc_|castle|PLACE_|shop|legend|gameover|'
                     r'splash|battletest|_ed$|_man$|empty|continue|INITIALIZE|LOGO', re.I)
    real = [n for n in rn if not pat.search(n)]
    town = [n for n in rn if re.search(r'^room_town', n, re.I)]
    print('  %-18s 总=%-4d 现实=%-4d 含 room_town_* = %d' % (c, len(rn), len(real), len(town)))
    print('       现实世界前 40: %s' % real[:40])

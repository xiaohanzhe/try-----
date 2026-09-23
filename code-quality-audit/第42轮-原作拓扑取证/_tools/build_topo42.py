# -*- coding: utf-8 -*-
"""第42轮 · 推导 ch1 现实世界房间的完整拓扑
输入: probe42.json (32 房间实例) + conn42b.json (全量 room_goto)
规则（全部来自原作代码实证）:
  obj_doorA  -> room_goto_next()                                  -> index + 1
  obj_doorB  -> room_goto_previous()                              -> index - 1
  obj_doorC  -> room_goto(room_next(room_next(room)))             -> index + 2
  obj_doorD  -> room_goto(room_previous(room_previous(room)))     -> index - 2
  obj_doorX / obj_doorX_musfade / obj_doorW -> 表驱动 {src_room: dst_room}
"""
import io
import json
import os
import sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
W = r'E:\Download\_tmp\drw\chapter1_windows'
OUT = r'E:\Download\_tmp\topo42.json'

inst = json.loads(open(os.path.join(W, 'probe42.json'), 'rb').read().decode('utf-8')
                  .replace(': True', ': true').replace(': False', ': false'))
conn = json.loads(open(os.path.join(W, 'conn42b.json'), 'rb').read().decode('utf-8'))

rnames = conn['room_names']
N = len(rnames)


def rn(i):
    return rnames[i] if 0 <= i < N else ('?%d' % i)


# ---- 门表：{code: {src: dst}} ----
tables = defaultdict(dict)
for it in conn['items']:
    if it['op'] == 'goto' and it['src'] >= 0:
        tables[it['code']][it['src']] = it['dst']

print('=' * 78)
print('A. ch1 门表（来自 room_goto 配对）')
print('=' * 78)
for code in sorted(tables):
    t = tables[code]
    print('\n  ## %s   %d 条' % (code, len(t)))
    for s in sorted(t):
        print('      %-28s -> %-28s (%d -> %d)' % (rn(s), rn(t[s]), s, t[s]))

# ---- next / prev ----
np_ops = defaultdict(list)
for it in conn['items']:
    if it['op'] in ('room_goto_next', 'room_goto_previous'):
        np_ops[it['code']].append(it['op'])
print()
print('=' * 78)
print('B. next / previous 门对象')
print('=' * 78)
for code in sorted(np_ops):
    print('   %-46s %s' % (code, sorted(set(np_ops[code]))))

# ---- 按房间推导 ----
print()
print('=' * 78)
print('C. 32 个现实世界房间：门实例 -> 推导目标')
print('=' * 78)
DOORRULE = {
    'obj_doorA': ('+1', 1), 'obj_doorA_musfade': ('+1', 1),
    'obj_doorB': ('-1', -1), 'obj_doorB_musfade': ('-1', -1),
    'obj_doorC': ('+2', 2), 'obj_doorC_musfade': ('+2', 2),
    'obj_doorD': ('-2', -2), 'obj_doorD_musfade': ('-2', -2),
}
XTABLE = {
    'obj_doorX': 'gml_Object_obj_doorX_Alarm_2',
    'obj_doorX_musfade': 'gml_Object_obj_doorX_musfade_Alarm_2',
    'obj_doorW': 'gml_Object_obj_doorW_Alarm_2',
    'obj_doorw_musfade': 'gml_Object_obj_doorW_Alarm_2',
}

result = []
for r in inst['rooms']:
    ri, rname = r['index'], r['name']
    doors = defaultdict(list)
    for i in r['instances']:
        o = i['obj']
        if o.startswith('obj_door'):
            doors[o].append((i['x'], i['y']))
    if not doors:
        print('\n  [%2d] %-24s  (无门)' % (ri, rname))
        continue
    print('\n  [%2d] %-24s' % (ri, rname))
    edges = []
    for o in sorted(doors):
        for (x, y) in doors[o]:
            if o in DOORRULE:
                lbl, d = DOORRULE[o]
                tgt = ri + d
                note = ''
            elif o in XTABLE:
                code = XTABLE[o]
                tgt = tables.get(code, {}).get(ri, -1)
                note = '(表)'
                if tgt < 0:
                    note = '(表内无此行%d)' % ri
            else:
                tgt, note = -1, '(未建模)'
            ok = (0 <= tgt < N)
            print('      %-22s x=%-7s y=%-7s -> %-26s %s'
                  % (o, x, y, rn(tgt) if ok else '?', note))
            if ok:
                edges.append((o, x, y, tgt))
    result.append({'index': ri, 'name': rname, 'edges': edges})

json.dump({'rooms': result}, open(OUT, 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('\n落盘: %s (%d B)' % (OUT, os.path.getsize(OUT)))

# ---- 汇总：无向去重的房间连边 ----
print()
print('=' * 78)
print('D. 房间级无向连边汇总（去重）')
print('=' * 78)
und = set()
for rr in result:
    for (o, x, y, t) in rr['edges']:
        a, b = rr['index'], t
        und.add((min(a, b), max(a, b)))
for a, b in sorted(und):
    print('   %-28s <-> %-28s  (%d<->%d)' % (rn(a), rn(b), a, b))
print('   共 %d 条' % len(und))

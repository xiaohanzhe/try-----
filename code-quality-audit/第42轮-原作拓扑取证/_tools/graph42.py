# -*- coding: utf-8 -*-
"""第42轮 · 合成五章完整拓扑
规则（全部来自原作 Alarm 事件反汇编实证）:
  obj_doorA[_musfade] -> room_goto_next()                          -> index + 1
  obj_doorB[_musfade] -> room_goto_previous()                      -> index - 1
  obj_doorC[_musfade] -> room_goto(room_next(room_next(room)))     -> index + 2
  obj_doorD[_musfade] -> room_goto(room_previous(room_previous))   -> index - 2
  obj_doorX / obj_doorX_musfade / obj_doorW / obj_doorw_musfade    -> 表驱动 {src_room: dst_room}
"""
import io
import json
import os
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
DRW = r'E:\Download\_tmp\drw'
OUT = r'E:\Download\_tmp\graph42.json'
CH = [('chapter1_windows', 'ch1'), ('chapter2_windows', 'ch2'), ('chapter3_windows', 'ch3'),
      ('chapter4_windows', 'ch4'), ('chapter5_windows', 'ch5')]

DOORRULE = {
    'obj_doorA': 1, 'obj_doorA_musfade': 1,
    'obj_doorB': -1, 'obj_doorB_musfade': -1,
    'obj_doorC': 2, 'obj_doorC_musfade': 2,
    'obj_doorD': -2, 'obj_doorD_musfade': -2,
}
XTABLE = {
    'obj_doorX': 'gml_Object_obj_doorX_Alarm_2',
    'obj_doorX_musfade': 'gml_Object_obj_doorX_musfade_Alarm_2',
    'obj_doorW': 'gml_Object_obj_doorW_Alarm_2',
    'obj_doorw_musfade': 'gml_Object_obj_doorw_musfade_Alarm_2',
}

out = {}
unmodelled = Counter()
for folder, key in CH:
    conn = json.loads(open(os.path.join(DRW, folder, 'conn42b.json'), 'rb').read().decode('utf-8'))
    inst = json.loads(open(os.path.join(DRW, folder, 'inst42.json'), 'rb').read().decode('utf-8')
                      .replace(': True', ': true').replace(': False', ': false'))
    rnames = conn['room_names']
    N = len(rnames)

    tables = defaultdict(dict)
    for it in conn['items']:
        if it['op'] == 'goto' and it['src'] >= 0:
            tables[it['code']][it['src']] = it['dst']

    edges = []
    for room in inst['rooms']:
        ri = room['index']
        for i in room['insts']:
            o = i['obj']
            tgt = None
            kind = None
            if o in DOORRULE:
                tgt = ri + DOORRULE[o]
                kind = 'delta'
            elif o in XTABLE:
                tgt = tables.get(XTABLE[o], {}).get(ri)
                kind = 'table'
                if tgt is None:
                    continue
            else:
                if o.startswith('obj_door'):
                    unmodelled[o] += 1
                continue
            if not (0 <= tgt < N):
                continue
            edges.append({'src': ri, 'dst': tgt, 'door': o, 'kind': kind,
                          'x': i['x'], 'y': i['y']})

    out[key] = {'folder': folder, 'n_rooms': N, 'room_names': rnames,
                'n_edges': len(edges), 'edges': edges}

print('=' * 78)
print('A. 五章拓扑合成结果')
print('=' * 78)
for folder, key in CH:
    d = out[key]
    und = set()
    for e in d['edges']:
        und.add((min(e['src'], e['dst']), max(e['src'], e['dst'])))
    print('  %-4s rooms=%-4d 有向边=%-4d 无向去重=%-4d'
          % (key, d['n_rooms'], d['n_edges'], len(und)))

print()
print('=' * 78)
print('B. 未建模的 obj_door* 实例（需补规则）')
print('=' * 78)
if unmodelled:
    for k, v in unmodelled.most_common(20):
        print('   %-34s x%d' % (k, v))
else:
    print('   （无）')

print()
print('=' * 78)
print('C. 每章「小镇 + 邻接生活区 + 暗世界入口」的连接（现实世界部分）')
print('=' * 78)
import re
REALPAT = re.compile(r'dark|field|forest|_cc_|castle|PLACE_|shop|legend|gameover|splash|'
                     r'battletest|_ed$|_man$|empty|continue|INITIALIZE|LOGO|debug|tester|'
                     r'test|demo', re.I)
for folder, key in CH:
    d = out[key]
    rn = d['room_names']
    rows = []
    for e in d['edges']:
        s, t = rn[e['src']], rn[e['dst']]
        if REALPAT.search(s) or REALPAT.search(t):
            continue
        rows.append((s, t, e['door']))
    und = []
    seen = set()
    for s, t, o in sorted(rows):
        k = (min(s, t), max(s, t))
        if k in seen:
            continue
        seen.add(k)
        und.append((s, t, o))
    print('\n  ## %s  现实世界无向边 %d 条' % (key, len(und)))
    for s, t, o in und:
        print('      %-28s <-> %-28s  [%s]' % (s, t, o))

json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n落盘: %s (%d B)' % (OUT, os.path.getsize(OUT)))

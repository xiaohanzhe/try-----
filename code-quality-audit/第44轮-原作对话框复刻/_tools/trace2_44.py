# -*- coding: utf-8 -*-
"""追查 2 个疑点（只读）：
  ① ch2.cyber_field.dw_cyber_maze_virokun 字母序 B,C,A 异常
  ② 7 个"真缺口"场景：原作门的位移目标为何没编边
"""
import io
import json
import os
import collections

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
DRW = r'E:\Download\_tmp\drw'
CHS = ['chapter1_windows', 'chapter2_windows', 'chapter3_windows',
       'chapter4_windows', 'chapter5_windows']
TAG = {CHS[i]: 'ch%d' % (i + 1) for i in range(5)}
DELTA = {'A': 1, 'B': -1, 'C': 2}


def jload(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def door_letter(n):
    if not n or not n.startswith('obj_door'):
        return None
    t = n[len('obj_door'):]
    for s in ('_musfade', '_solid'):
        if t.endswith(s):
            t = t[:-len(s)]
    if len(t) == 1 and t.isalpha() and t.upper() in DELTA:
        return t.upper()
    return None


def marker_letter(n):
    if not n or not n.startswith('obj_marker'):
        return None
    t = n[len('obj_marker'):]
    if len(t) == 1 and t.isalpha() and t.isupper():
        return t
    return None


def pts(l):
    o = []
    for s in l or []:
        p = str(s).split(',')
        if len(p) >= 3:
            o.append((p[0], p[1], p[2]))
    return o


rooms = {}
for w in CHS:
    d = jload(os.path.join(DRW, w, 'rooms44.json'))
    for r in d['rooms']:
        r['_ch'] = TAG[w]
        rooms[(TAG[w], r['id'])] = r

idx = jload(os.path.join(SC, '_index.json'))
scenes, by_room = {}, {}
for chid, c in (idx.get('chapters') or {}).items():
    for aid, a in (c.get('areas') or {}).items():
        for sid, e in (a.get('scenes') or {}).items():
            e2 = dict(e); e2['chapter_id'] = chid
            scenes[sid] = e2
            if isinstance(e.get('original_room_id'), int):
                by_room[(chid, e['original_room_id'])] = sid

rd = jload(os.path.join(SC, '_routes.json'))
routes = rd.get('routes') or []
by_src = collections.defaultdict(list)
for r in routes:
    by_src[r.get('when_scene')].append(r)

print('=' * 78)
print('[①] dw_cyber_maze_virokun 明细')
S = 'ch2.cyber_field.dw_cyber_maze_virokun'
e = scenes.get(S) or {}
print('  场景:', S, '| 原作房 =', e.get('chapter_id'), ':', e.get('original_room_id'))
rec = rooms.get((e.get('chapter_id'), e.get('original_room_id')))
if rec:
    print('  原作房名 =', rec.get('name'))
    dl = [(x, y, door_letter(n), n) for (x, y, n) in pts(rec.get('doors'))]
    for it in dl:
        print('    门 坐标=(%s,%s) letter=%s raw=%s' % it)
print('  该场景的产品出边:')
for r in by_src.get(S, []):
    print('    p=%s when_door=%s to=%s' % (r.get('priority'), r.get('when_door'), r.get('to')))

print()
print('[②] 7 个真缺口逐个查（原房间的门 + 位移目标是否登记）')
gaps = ['ch1.hometown.schooldoor', 'ch2.cyber_city.dw_city_spamton_shop_exterior',
        'ch2.hometown.schooldoor', 'ch3.hometown.schooldoor',
        'ch4.hometown.hospital_rudy', 'ch4.hometown.schooldoor',
        'ch5.hometown.schooldoor']
for sid in gaps:
    e = scenes.get(sid) or {}
    ch, orid = e.get('chapter_id'), e.get('original_room_id')
    rec = rooms.get((ch, orid))
    print('  --- %s (原作 %s:%s 名=%s)' % (sid, ch, orid, rec.get('name') if rec else '?'))
    if not rec:
        continue
    for (x, y, n) in pts(rec.get('doors')):
        L = door_letter(n)
        if not L:
            if 'door' in n:
                print('      raw门 %-28s (无字母)' % n)
            continue
        tr = rooms.get((ch, orid + DELTA[L]))
        mark = None
        if tr is not None:
            mark = any(marker_letter(m) == L for (_, _, m) in pts(tr.get('markers')))
        dst = by_room.get((ch, orid + DELTA[L])) if tr else None
        print('      %s门 -> 下标%+d 目标房=%s 有同字母落点=%s 目标已登记=%s'
              % (L, DELTA[L], (tr.get('name') if tr else '<不存在>'), mark, dst or '<无>'))

print()
print('[done]')

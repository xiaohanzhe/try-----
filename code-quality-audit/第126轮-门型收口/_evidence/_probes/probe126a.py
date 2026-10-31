# -*- coding: utf-8 -*-
u"""第126轮取证探针 A：ch1~ch5 的边按**门型**分组，并列出：
  ① 全部 door 取值分布（含 `other` 那些）
  ② `_musfade` 变体边的 marker 命中（同一把尺：目标房含 `obj_marker<同字母>`）
  ③ 端点未登记（`by_rid` 查不到）的边逐条详情
只读，不写产品。
"""
import io
import os
import json
import collections
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
EV42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
GRAPH = os.path.join(EV42, '_room_graph.json')
for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from modules import scene_system as SS  # noqa: E402

CH = [('ch1', 'inst42.json', 'conn42b.json')] + [
    ('ch%d' % i, 'ch%d_inst42.json' % i, 'ch%d_conn42b.json' % i) for i in (2, 3, 4, 5)]


def jload(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


IDX = SS.load_index(SCENES)
SCN = IDX.get('scenes') or {}
by_rid = collections.defaultdict(dict)
for sid, rec in SCN.items():
    if isinstance(rec, dict) and isinstance(rec.get('original_room_id'), int):
        cid = rec.get('chapter_id') or sid.split('.')[0]
        by_rid[cid].setdefault(rec['original_room_id'], sid)

G = (jload(GRAPH) or {}).get('chapters') or {}

door_stat = collections.Counter()
same_letter = collections.Counter()     # 同字母（A/B/C/D/W/X）
mus = []
unreg = []
for cid, instf, connf in CH:
    inst = jload(os.path.join(EV42, instf))
    rooms = {r['index']: r for r in (inst.get('rooms') or [])}
    objs = {i: {x.get('obj') for x in (r.get('insts') or [])} for i, r in rooms.items()}
    for e in (G.get(cid) or {}).get('edges') or []:
        d = e.get('door')
        door_stat[d] += 1
        if isinstance(d, str) and d.startswith('obj_door'):
            same_letter[d[len('obj_door'):][:1].upper()] += 1
        if isinstance(d, str) and d.endswith('_musfade'):
            L = d[len('obj_door'):][:1].upper()
            mk = 'obj_marker' + L
            hit = mk in objs.get(e.get('dst'), set())
            mus.append({'cid': cid, 'door': d, 'L': L, 'src': e.get('src'),
                        'dst': e.get('dst'), 'hit': hit,
                        'src_sid': by_rid[cid].get(e.get('src')),
                        'dst_sid': by_rid[cid].get(e.get('dst')),
                        'dst_raw': (rooms.get(e.get('dst')) or {}).get('name'),
                        'via': e.get('via')})
        if not by_rid[cid].get(e.get('src')) or not by_rid[cid].get(e.get('dst')):
            unreg.append({'cid': cid, 'door': d, 'src': e.get('src'), 'dst': e.get('dst'),
                          'src_ok': bool(by_rid[cid].get(e.get('src'))),
                          'dst_ok': bool(by_rid[cid].get(e.get('dst'))),
                          'src_raw': (rooms.get(e.get('src')) or {}).get('name'),
                          'dst_raw': (rooms.get(e.get('dst')) or {}).get('name')})

print(u'===== ① 门型分布（ch1~ch5，共 %d 条）====='
      % sum(door_stat.values()))
for d, n in door_stat.most_common():
    print(u'  %-28s %4d' % (d, n))
print(u'----- 同字母合计 -----')
for L, n in sorted(same_letter.items()):
    print(u'  %-4s %4d' % (L, n))

print(u'')
print(u'===== ② `_musfade` 变体边：%d 条 =====' % len(mus))
_mh = sum(1 for m in mus if m['hit'])
print(u'marker 命中 %d/%d = %.1f%%' % (_mh, len(mus), 100.0 * _mh / max(1, len(mus))))
for m in mus:
    print(u'  [%s] %-24s %4s→%-4s %s  src=%s dst=%s raw=%s'
          % ('HIT ' if m['hit'] else 'MISS', m['door'], m['src'], m['dst'],
             m['L'], m['src_sid'], m['dst_sid'], m['dst_raw']))

print(u'')
print(u'===== ③ 端点未登记：%d 条 =====' % len(unreg))
for u in unreg:
    print(u'  [%s] %-24s %4s→%-4s src_ok=%-5s dst_ok=%-5s raw=%s → %s'
          % (u['cid'], u['door'], u['src'], u['dst'], u['src_ok'], u['dst_ok'],
             u['src_raw'], u['dst_raw']))

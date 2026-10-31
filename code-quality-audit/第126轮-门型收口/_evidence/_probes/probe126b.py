# -*- coding: utf-8 -*-
u"""第126轮取证探针 B：把 `_musfade` 变体（A/B/C/D/X/W 共 84 条）过**与第125轮同一套**三闸，
逐条给出卡在哪一闸；并给出对照组（同字母的非 musfade 边）的 marker 命中率，
用来证明"marker 判据不是对 A/B/C 恒假"。

三闸：
  ① 机制：A +1 / B −1 / C +2 / D −2 / X 查表（与产品口径一致）
  ② 落点自证：目标房含 `obj_marker<同字母>`
  ③ 产品侧不冲突：端点已登记 · 同场景同 when_door 尚无路由 · 三元不重复

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
ROUTES = os.path.join(SCENES, '_routes.json')
EV42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
GRAPH = os.path.join(EV42, '_room_graph.json')
for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from modules import scene_system as SS  # noqa: E402

CH = [('ch1', 'inst42.json', 'conn42b.json')] + [
    ('ch%d' % i, 'ch%d_inst42.json' % i, 'ch%d_conn42b.json' % i) for i in (2, 3, 4, 5)]
DELTA = {'A': 1, 'B': -1, 'C': 2, 'D': -2}
TABLE = {'X': 'gml_Object_obj_doorX_Alarm_2', 'X_musfade': 'gml_Object_obj_doorX_musfade_Alarm_2'}


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

RL = (json.loads(io.open(ROUTES, encoding='utf-8', newline='').read()) or {}).get('routes') or []
have_door = set((r.get('when_scene'), str(r.get('when_door') or '')) for r in RL)
have_edge = set((r.get('when_scene'), r.get('to')) for r in RL)
G = (jload(GRAPH) or {}).get('chapters') or {}

rows = []          # musfade 行
ctrl = collections.Counter()   # 对照组：非 musfade 边的 marker 命中
for cid, instf, connf in CH:
    inst = jload(os.path.join(EV42, instf))
    conn = jload(os.path.join(EV42, connf))
    rooms = {r['index']: r for r in (inst.get('rooms') or [])}
    objs = {i: {x.get('obj') for x in (r.get('insts') or [])} for i, r in rooms.items()}
    tables = collections.defaultdict(dict)
    for it in conn.get('items') or []:
        if it.get('op') == 'goto' and isinstance(it.get('src'), int) and it['src'] >= 0:
            tables[it['code']][it['src']] = it['dst']
    for e in (G.get(cid) or {}).get('edges') or []:
        d = e.get('door') or ''
        L = d[len('obj_door'):][:1].upper() if d.startswith('obj_door') else '?'
        mus = d.endswith('_musfade')
        # 机制
        if L == 'X':
            key = 'X_musfade' if mus else 'X'
            want = tables.get(TABLE[key], {}).get(e.get('src'))
        elif L in DELTA:
            want = e.get('src') + DELTA[L]
        else:
            want = None
        mech_ok = (want == e.get('dst'))
        mk_ok = ('obj_marker' + L) in objs.get(e.get('dst'), set())
        if not mus:
            ctrl[L + ('/mech_ok' if mech_ok else '/mech_bad') + ('/mk' if mk_ok else '/nomk')] += 1
            continue
        s_sid, d_sid = by_rid[cid].get(e.get('src')), by_rid[cid].get(e.get('dst'))
        rows.append({
            'cid': cid, 'door': d, 'L': L, 'src': e.get('src'), 'dst': e.get('dst'),
            's_sid': s_sid, 'd_sid': d_sid, 'mech_ok': mech_ok, 'mk_ok': mk_ok,
            'unreg': (not s_sid) or (not d_sid),
            'clash': (s_sid, L) in have_door,
            'dup': (s_sid, d_sid) in have_edge,
            'src_raw': (rooms.get(e.get('src')) or {}).get('name'),
            'dst_raw': (rooms.get(e.get('dst')) or {}).get('name'),
        })

print(u'===== 对照组：非 musfade 边（同字母）机制/marker 命中 =====')
for k in sorted(ctrl):
    print(u'  %-16s %4d' % (k, ctrl[k]))
print(u'  （A/B/C 的 marker 命中率 = 机制正确且带 marker 的比例）')

print(u'')
print(u'===== musfade 84 条的逐闸判定 =====')
cnt = collections.Counter()
for r in rows:
    why = []
    if not r['mech_ok']:
        why.append(u'机制不符')
    if r['unreg']:
        why.append(u'端点未登记')
    if not r['mk_ok']:
        why.append(u'目标无 marker')
    if r['clash']:
        why.append(u'同场景同门已有路由')
    if r['dup']:
        why.append(u'该边已存在')
    r['why'] = why
    cnt[r['L'] + (u'/可收' if not why else u'/卡住')] += 1
    print(u'  [%s] %-22s %-4s %4s→%-4s mech=%-5s mk=%-5s %s%s'
          % (u'可收' if not why else u'卡住', r['door'], r['L'], r['src'], r['dst'],
             r['mech_ok'], r['mk_ok'], u'・'.join(why),
             (u'  raw=%s→%s' % (r['src_raw'], r['dst_raw'])) if why else ''))
print(u'')
print(u'===== 小结 =====')
for k in sorted(cnt):
    print(u'  %s %d' % (k, cnt[k]))
print(u'  musfade 总 %d' % len(rows))

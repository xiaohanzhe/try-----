# -*- coding: utf-8 -*-
u"""第126轮取证探针 D：outertale 的 105 条候选边**逐条过独立验证**。

独立验证（第122/123轮对 ut 用的同型尺，不是照抄 conn115 的结论）：
  ★ **那扇门必须真的摆在源房里** —— `inst_full.tsv` 里源房实例表要含该门对象。
     （等价于 Deltarune 的 `obj_marker<字母>`：机制只是先验，落点/在场是独立证据。）

同时回答：
  ① 144 条边里，`code` 抽出来的对象**门类**有多少（非门的 battle trigger / 演出移动要剔）
  ② 门类候选的"源房真摆了这扇门"命中率
  ③ `_room_graph.json` 的章节结构（供 outertale 对齐）
只读。
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
EV115 = os.path.join(REPO, 'code-quality-audit', '第115轮-跨作品物件普查', '_evidence')
CONN = os.path.join(EV115, 'conn115.json')
INST = os.path.join(EV115, 'raw', 'outertale', 'inst_full.tsv')
GRAPH42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence', '_room_graph.json')
for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from modules import scene_system as SS  # noqa: E402


def jload(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


def obj_of(code):
    u"""`gml_Object_obj_door_ruins13_Alarm_2` → `obj_door_ruins13`；抽不出返 None。"""
    if not isinstance(code, str) or not code.startswith('gml_Object_'):
        return None
    s = code[len('gml_Object_'):]
    for suf in ('_Alarm_', '_Step_', '_Create_', '_Collision_', '_Draw_', '_Destroy_',
                '_Other_', '_KeyPress_', '_KeyRelease_', '_Mouse_'):
        i = s.find(suf)
        if i > 0:
            s = s[:i]
            break
    return s


IDX = SS.load_index(SCENES)
SCN = IDX.get('scenes') or {}
ot_rid = {r['original_room_id']: sid for sid, r in SCN.items()
          if sid.startswith('outertale.') and isinstance(r.get('original_room_id'), int)}
RL = (json.loads(io.open(ROUTES, encoding='utf-8', newline='').read()) or {}).get('routes') or []
have = set((r.get('when_scene'), r.get('to')) for r in RL)

# ---- 实例表（按行扫，`R` 行切换当前房，`I` 行记实例）----
rooms, inst = {}, collections.defaultdict(set)
cur = None
with io.open(INST, encoding='utf-8', errors='replace', newline='') as fh:
    for ln in fh:
        p = ln.rstrip('\r\n').split('\t')
        if p[0] == 'R' and len(p) >= 3:
            cur = int(p[1])
        elif p[0] == 'I' and len(p) >= 2 and cur is not None:
            inst[cur].add(p[1])
print(u'实例：%d 个房间有实例，总实例 %d' % (len(inst), sum(len(v) for v in inst.values())))

E = jload(CONN)['outertale']['edges']
print(u'')
print(u'① 144 条边的 code → 对象（按出现次数）')
codes = collections.Counter(e.get('code') for e in E)
door_like, other = [], []
for c, n in codes.most_common():
    o = obj_of(c) or ''
    (door_like if o.startswith('obj_door') else other).append((c, o, n))
    print(u'   %-58s %-30s %3d %s' % (c, o or '?', n,
                                      u'[门]' if o.startswith('obj_door') else u'[非门]'))
print(u'   门类 code %d 个 / 非门 %d 个' % (len(door_like), len(other)))

print(u'')
print(u'② 门类候选的独立验证（源房真摆了这扇门）')
rows = []
for e in E:
    o = obj_of(e.get('code')) or ''
    if not o.startswith('obj_door'):
        continue
    s, d = ot_rid.get(e.get('src')), ot_rid.get(e.get('dst'))
    if not s or not d or s == d:
        continue
    if (s, d) in have:
        continue
    present = o in inst.get(e.get('src'), set())
    rows.append({'src': s, 'dst': d, 'code': e.get('code'), 'obj': o,
                 'src_rid': e.get('src'), 'dst_rid': e.get('dst'),
                 'present': present, 'src_name': e.get('src_name'),
                 'dst_name': e.get('dst_name')})
hit = sum(1 for r in rows if r['present'])
print(u'   门类候选 %d 条，源房有该门实例 %d 条 = %.1f%%'
      % (len(rows), hit, 100.0 * hit / max(1, len(rows))))
for r in rows:
    if not r['present']:
        print(u'   [MISS] %-24s %4s→%-4s  %s → %s'
              % (r['obj'], r['src_rid'], r['dst_rid'], r['src_name'], r['dst_name']))
print(u'   实例表里该门在哪几间房出现过（抽样 3 个门）：')
for o in sorted(set(r['obj'] for r in rows))[:3]:
    where = sorted(i for i, s in inst.items() if o in s)
    print(u'     %-24s %r' % (o, where[:12]))

print(u'')
print(u'③ `_room_graph.json` 章节结构')
GP = jload(GRAPH42)
ch = GP.get('chapters') or {}
print(u'   chapters: %r' % list(ch.keys()))
for k, v in ch.items():
    if isinstance(v, dict):
        es = v.get('edges') or []
        print(u'   %-8s edges=%-5d keys=%r sample=%s'
              % (k, len(es), list(v.keys()),
                 json.dumps(es[0], ensure_ascii=False)[:220] if es else None))
    else:
        print(u'   %-8s = %r' % (k, v))
print(u'   top-level keys: %r' % list(GP.keys()))

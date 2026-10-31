# -*- coding: utf-8 -*-
u"""第126轮取证探针 G：修正版账（上一版把 `uncond` 展开到**该对象的全部实例房**，
这是错的 —— 同一个对象的不同 Alarm 才是"哪段代码在哪间房跑"的真依据，
拿不准就**丢**，不猜）。

规则（三条，逐条可追）：
  guard   `if (room == N) room_goto(M)`  ⇒ (N→M)；★ 独立验证：该对象**真的摆在这间房**
  next    `room_goto_next()`             ⇒ 每个实例房 r → r+1（位移门，第123轮 ut 同型）
  prev    `room_goto_previous()`         ⇒ r → r−1
  uncond  无条件 `room_goto(M)`（src 未知）  ⇒ **丢**（不知道它哪间房会跑）

准入：门类对象 · 两端已登记 · 非自环 · **同(场景,对象)只一个目标** · 三元去重。
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
RAW = os.path.join(EV115, 'raw', 'outertale')
CONN = os.path.join(RAW, 'conn_ut.json')
INST = os.path.join(RAW, 'inst_full.tsv')
for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from modules import scene_system as SS  # noqa: E402


def jload(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


def obj_of(code):
    if not isinstance(code, str) or not code.startswith('gml_Object_'):
        return None
    s = code[len('gml_Object_'):]
    for suf in ('_Alarm_', '_Step_', '_Create_', '_Collision_', '_Draw_', '_Destroy_',
                '_Other_', '_KeyPress_', '_KeyRelease_', '_Mouse_'):
        i = s.find(suf)
        if i > 0:
            return s[:i]
    return s


IDX = SS.load_index(SCENES)
SCN = IDX.get('scenes') or {}
ot_rid = {r['original_room_id']: sid for sid, r in SCN.items()
          if sid.startswith('outertale.') and isinstance(r.get('original_room_id'), int)}
RL = (json.loads(io.open(ROUTES, encoding='utf-8', newline='').read()) or {}).get('routes') or []
have = set((r.get('when_scene'), r.get('to')) for r in RL)

rooms, inst = {}, collections.defaultdict(set)
cur = None
with io.open(INST, encoding='utf-8', errors='replace', newline='') as fh:
    for ln in fh:
        p = ln.rstrip('\r\n').split('\t')
        if p[0] == 'R' and len(p) >= 3:
            cur = int(p[1])
            rooms[cur] = p[2]
        elif p[0] == 'I' and len(p) >= 2 and cur is not None:
            inst[cur].add(p[1])
by_obj = collections.defaultdict(list)
for i, s in inst.items():
    for o in s:
        by_obj[o].append(i)
for o in by_obj:
    by_obj[o].sort()

items = jload(CONN)['items']
EXCLUDE = {'obj_mainchara'}


def is_door(o):
    return isinstance(o, str) and (o.startswith('obj_door') or o.startswith('obj_demodoor')) \
        and o not in EXCLUDE


# 先按对象统计它有哪些 op —— 有多个 op 的对象要小心
ops_of = collections.defaultdict(collections.Counter)
for it in items:
    o = obj_of(it.get('code')) or ''
    if is_door(o):
        ops_of[o][it.get('op')] += 1

stat = collections.Counter()
cand = []
for it in items:
    o = obj_of(it.get('code')) or ''
    if not is_door(o):
        stat['item_nondoor'] += 1
        continue
    op, dst, src = it.get('op'), it.get('dst'), it.get('src')
    if op == 'goto' and isinstance(src, int) and src >= 0:
        stat['guard'] += 1
        if o not in inst.get(src, set()):
            stat['guard_no_inst'] += 1
            continue
        cand.append((src, dst, o, 'guard', it.get('code')))
    elif op == 'goto':
        stat['uncond_dropped'] += 1
    elif op in ('room_goto_next', 'room_goto_previous'):
        stat['shift'] += 1
        if len(ops_of[o]) > 1:
            stat['shift_ambiguous_obj'] += 1
        step = 1 if op == 'room_goto_next' else -1
        for r in (by_obj.get(o) or []):
            cand.append((r, r + step, o, 'next' if step > 0 else 'prev', it.get('code')))

print(u'stat %r' % dict(stat))
print(u'候选（过 guard 实例互证 / 位移展开）%d 条' % len(cand))

step1 = []
for src, dst, o, kind, code in cand:
    if not isinstance(dst, int):
        stat['drop_bad_idx'] += 1
        continue
    if src == dst:
        stat['drop_self'] += 1
        continue
    s, d = ot_rid.get(src), ot_rid.get(dst)
    if not s or not d:
        stat['drop_unreg'] += 1
        continue
    step1.append({'src_rid': src, 'dst_rid': dst, 'scene': s, 'to': d, 'obj': o,
                  'kind': kind, 'code': code})
print(u'① 已登记且非自环 %d（未登记 %d / 自环 %d）'
      % (len(step1), stat['drop_unreg'], stat['drop_self']))

grp = collections.defaultdict(set)
for e in step1:
    grp[(e['scene'], e['obj'])].add(e['to'])
amb = set(k for k, v in grp.items() if len(v) > 1)
print(u'② 同(场景,对象) 多目标 %d 组 ⇒ 整组丢' % len(amb))
for k in sorted(amb)[:10]:
    print(u'   %-42s %-20s %r' % (k[0], k[1], sorted(grp[k])))
if len(amb) > 10:
    print(u'   ...（共 %d 组）' % len(amb))
step2 = [e for e in step1 if (e['scene'], e['obj']) not in amb]

seen = set()
step3 = []
for e in step2:
    k = (e['scene'], e['obj'], e['to'])
    if k in seen:
        stat['dup'] += 1
        continue
    seen.add(k)
    if (e['scene'], e['to']) in have:
        stat['alreadythere'] += 1
        continue
    step3.append(e)
print(u'③ 三元去重 %d · 产品已有 %d ⇒ **可写 %d 条**'
      % (stat['dup'], stat['alreadythere'], len(step3)))
srcs, dsts = set(e['scene'] for e in step3), set(e['to'] for e in step3)
print(u'   src %d / dst %d / 并集 %d' % (len(srcs), len(dsts), len(srcs | dsts)))
print(u'   按 kind %r' % dict(collections.Counter(e['kind'] for e in step3)))
print(u'   按对象 %r' % dict(collections.Counter(e['obj'] for e in step3)))
print(u'   按区 %r' % dict(collections.Counter(e['scene'].split('.')[1] for e in step3)))
print(u'')
print(u'===== 前 12 条 =====')
for e in step3[:12]:
    print(u'  %-44s [%-5s] %-20s -> %s' % (e['scene'], e['kind'], e['obj'], e['to']))

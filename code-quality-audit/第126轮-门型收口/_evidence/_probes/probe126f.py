# -*- coding: utf-8 -*-
u"""第126轮取证探针 F：outertale 门路由的**完整账**（写生成器之前的最后一步）。

推导规则（三种，全部来自 `conn_ut.json` 的原始 op + `inst_full.tsv` 的实例分布）：

  kind=guard   `if (room == N) room_goto(M)`  ⇒ (N → M)，src 由守卫给定
  kind=next    `room_goto_next()`             ⇒ 每个实例房 r → r+1
  kind=prev    `room_goto_previous()`         ⇒ 每个实例房 r → r−1
  kind=uncond  无条件 `room_goto(M)`          ⇒ 每个实例房 r → M

准入：① 对象是门（`obj_door*` / `obj_demodoor*`，**排除** `obj_mainchara` —— 它是
"走到屏幕边缘换房"，另一层机制，第122轮已裁定不写）；② 两端能按 `original_room_id`
解析到场景；③ 不自环；④ **同 (场景, 对象) 只允许一个目标**（原作按 `x` 坐标分叉的门
⇒ 两个目标，产品表达不了 ⇒ 整组丢掉，不猜）；⑤ 三元 (场景, 对象, 目标) 去重。

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
N_ROOMS = len(rooms)
EXCLUDE = {'obj_mainchara'}


def is_door(o):
    return isinstance(o, str) and (o.startswith('obj_door') or o.startswith('obj_demodoor')) \
        and o not in EXCLUDE


stat = collections.Counter()
raw_edges = []      # (src_rid, dst_rid, obj, kind, extra)
for it in items:
    o = obj_of(it.get('code')) or ''
    stat['item_total'] += 1
    if not is_door(o):
        stat['item_nondoor'] += 1
        continue
    op = it.get('op')
    dst = it.get('dst')
    src = it.get('src')
    if op == 'goto':
        if isinstance(src, int) and src >= 0:
            stat['guard'] += 1
            raw_edges.append((src, dst, o, 'guard', it.get('code')))
        else:
            stat['uncond'] += 1
            locs = by_obj.get(o) or []
            if not locs:
                stat['uncond_noplace'] += 1
                continue
            for r in locs:
                raw_edges.append((r, dst, o, 'uncond', it.get('code')))
    elif op == 'room_goto_next':
        stat['next'] += 1
        for r in (by_obj.get(o) or []):
            raw_edges.append((r, r + 1, o, 'next', it.get('code')))
    elif op == 'room_goto_previous':
        stat['prev'] += 1
        for r in (by_obj.get(o) or []):
            raw_edges.append((r, r - 1, o, 'prev', it.get('code')))

print(u'items %d → 门类展开 %d 条原始候选' % (len(items), len(raw_edges)))
print(u'stat %r' % dict(stat))

# ---- 准入门 ①：两端能解析 ----
step1 = []
for src, dst, o, kind, code in raw_edges:
    if not isinstance(dst, int) or not isinstance(src, int):
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
print(u'① 两端已登记且非自环：%d（丢掉 未登记 %d / 自环 %d / 坏下标 %d）'
      % (len(step1), stat['drop_unreg'], stat['drop_self'], stat['drop_bad_idx']))

# ---- 准入门 ②：同 (场景, 对象) 只许一个目标 ----
grp = collections.defaultdict(set)
for e in step1:
    grp[(e['scene'], e['obj'])].add(e['to'])
amb = set(k for k, v in grp.items() if len(v) > 1)
print(u'② 同(场景,对象) 有 %d 组出现**多个目标** ⇒ 整组丢（原件按 x 坐标分叉，产品表达不了）'
      % len(amb))
for k in sorted(amb):
    print(u'   %-40s %-24s → %r' % (k[0], k[1], sorted(grp[k])))
step2 = [e for e in step1 if (e['scene'], e['obj']) not in amb]

# ---- 准入门 ③：三元去重 + 产品已有 ----
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
print(u'③ 三元去重后 %d（重复 %d）→ 去掉产品已有 %d ⇒ **%d 条可写**'
      % (len(seen), stat['dup'], stat['alreadythere'], len(step3)))

print(u'')
print(u'===== 覆盖与分布 =====')
srcs = set(e['scene'] for e in step3)
dsts = set(e['to'] for e in step3)
print(u'  src 场景 %d · dst 场景 %d · 并集 %d / outertale 共 244'
      % (len(srcs), len(dsts), len(srcs | dsts)))
print(u'  按 kind：%r' % dict(collections.Counter(e['kind'] for e in step3)))
print(u'  按对象：%r' % dict(collections.Counter(e['obj'] for e in step3)))
print(u'  按区（src 场景前缀）：%r'
      % dict(collections.Counter(e['scene'].split('.')[1] for e in step3)))
print(u'')
print(u'===== 前 10 条样例 =====')
for e in step3[:10]:
    print(u'  %-42s [%-6s] %-22s -> %s'
          % (e['scene'], e['kind'], e['obj'], e['to']))

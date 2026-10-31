# -*- coding: utf-8 -*-
u"""第126轮 · 把 **outertale 的门**接进产品（`_routes.json` + `_room_graph.json` 两层）。

## 为什么这一轮

第115轮的可达账里，outertale **244 个场景、0 条路由** —— 整个作品"看得到、走不通"。
uty 同理只有 1 条可信边（第115轮已裁定"证据不足，不写"），本轮不动。

## 边从哪来（三个前提，缺一不写）

  ① `conn_ut.json` 的**原始 op**（第115轮从 `game.droid` 抽的 301 条 goto 记录）
  ② `inst_full.tsv` 的**实例分布**（358 间房、4,600 个实例）
  ③ 第123轮 ut 已证的位移门语义（`obj_doorA` = `room_goto_next`）

## 推导三类（逐条可追）

  kind=ot_door_guard  `if (room == N) room_goto(M)` ⇒ (N → M)
                       ★ 独立验证：**那个门对象真的摆在 N 这间房**的实例表里
                       （等价于 Deltarune 的 `obj_marker`：机制只是先验，在场是独立证据）
  kind=ot_door_shift  `room_goto_next()` ⇒ 每个实例房 r → r+1（第123轮 ut 同型）
  （`goto_const_nosrc`，无条件 `room_goto(M)`、src 未知 ⇒ **丢**，不猜）

## 准入闸（与第122/125轮同一套纪律）

  ① 门类对象：`obj_door*` / `obj_demodoor*`；**排除 `obj_mainchara`**
     （297 间房都有它，"走到屏幕边缘换房"是另一层机制，第122轮已裁定不写）
  ② 两端能按 `original_room_id` 解析到场景（否则这条边人走不到）
  ③ 不自环
  ④ **同 (场景, 对象) 只允许一个目标**：原作有按 `x` 坐标分叉的门（旅馆大堂
     `x < 300` → 商店 / `x > 300` → 新家电梯），产品一扇门只能一个目标 ⇒ 整组丢
  ⑤ 三元 (场景, 对象, 目标) 去重

## 输出

`_routes.json` 追加 **209** 条（guard 93 + shift 116），priority 从 **6000** 起
（既有段：110~2478 / 3000+ OneShot / 4000+ ut / 5000+ ch1~ch5 门型），
并把**同一组边**追加成 `_room_graph.json` 的 `chapters.outertale`
（逐门寻路 `plan_route_to` 读的是这张图，不是 routes —— 第105轮 OneShot 同款两层）。

★ 五章 782 边与 `chapters.oneshot` 420 边**逐字段指纹必须不变**（脚本内自证）。
"""
import io
import os
import json
import sys
import hashlib
import collections

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
ROUTES = os.path.join(SCENES, '_routes.json')
#: ★ 逐门寻路图**不在** `assets/scenes/` —— 产品 `scene_pathfind.room_graph_path()`
#: 硬编码到第42轮的证据目录（第105轮已核过：这份证据同时是运行时数据）。
ROOM_GRAPH = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证',
                          '_evidence', '_room_graph.json')
EV115 = os.path.join(REPO, 'code-quality-audit', '第115轮-跨作品物件普查', '_evidence')
RAW = os.path.join(EV115, 'raw', 'outertale')
CONN = os.path.join(RAW, 'conn_ut.json')
INST = os.path.join(RAW, 'inst_full.tsv')
for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from modules import scene_system as SS  # noqa: E402

PRIO_BASE = 6000
EXPECT_ADD = 209
EXPECT_GUARD = 93
EXPECT_SHIFT = 116
KIND_GUARD = 'ot_door_guard'
KIND_SHIFT = 'ot_door_shift'
CHAPTER = 'outertale'
EXCLUDE = {'obj_mainchara'}
FROZEN_CH = ('ch1', 'ch2', 'ch3', 'ch4', 'ch5', 'oneshot')


def jload(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


def obj_of(code):
    u"""`gml_Object_obj_door_t_Alarm_2` → `obj_door_t`（抽不出返 None）。"""
    if not isinstance(code, str) or not code.startswith('gml_Object_'):
        return None
    s = code[len('gml_Object_'):]
    for suf in ('_Alarm_', '_Step_', '_Create_', '_Collision_', '_Draw_', '_Destroy_',
                '_Other_', '_KeyPress_', '_KeyRelease_', '_Mouse_'):
        i = s.find(suf)
        if i > 0:
            return s[:i]
    return s


def is_door(o):
    return isinstance(o, str) and (o.startswith('obj_door') or o.startswith('obj_demodoor')) \
        and o not in EXCLUDE


def label(rec):
    a = rec.get('area_name') or rec.get('area_id') or ''
    n = rec.get('name') or ''
    if not a:
        return n
    return n if n.startswith(a) else (a + u'·' + n)


def raw_name(rec):
    return (rec.get('name_raw') or rec.get('name') or '')


def _ch_fp(v):
    return hashlib.sha256(
        json.dumps(v, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


IDX = SS.load_index(SCENES)
SCN = IDX.get('scenes') or {}
ot_rid = {r['original_room_id']: sid for sid, r in SCN.items()
          if sid.startswith(CHAPTER + '.') and isinstance(r.get('original_room_id'), int)}
RL_RAW = json.loads(io.open(ROUTES, encoding='utf-8', newline='').read())
RL = RL_RAW.get('routes') or []
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
        stat['item_guard'] += 1
        if o not in inst.get(src, set()):
            stat['drop_guard_no_inst'] += 1
            continue
        cand.append((src, dst, o, KIND_GUARD, it.get('code')))
    elif op == 'goto':
        stat['drop_uncond_nosrc'] += 1
    elif op in ('room_goto_next', 'room_goto_previous'):
        stat['item_shift'] += 1
        step = 1 if op == 'room_goto_next' else -1
        for r in (by_obj.get(o) or []):
            cand.append((r, r + step, o, KIND_SHIFT, it.get('code')))

step1 = []
for src, dst, o, kind, code in cand:
    if not isinstance(dst, int) or dst < 0:
        stat['drop_bad_idx'] += 1
        continue
    if src == dst:
        stat['drop_self'] += 1
        continue
    s_sid, d_sid = ot_rid.get(src), ot_rid.get(dst)
    if not s_sid or not d_sid:
        stat['drop_unreg'] += 1
        continue
    step1.append({'src_rid': src, 'dst_rid': dst, 'scene': s_sid, 'to': d_sid,
                  'obj': o, 'kind': kind, 'code': code})

grp = collections.defaultdict(set)
for e in step1:
    grp[(e['scene'], e['obj'])].add(e['to'])
amb = set(k for k, v in grp.items() if len(v) > 1)
step2 = [e for e in step1 if (e['scene'], e['obj']) not in amb]
stat['drop_amb_group'] = len(amb)

seen = set()
plan = []
for e in step2:
    k = (e['scene'], e['obj'], e['to'])
    if k in seen:
        stat['dup'] += 1
        continue
    seen.add(k)
    if (e['scene'], e['to']) in have:
        stat['already'] += 1
        continue
    plan.append(e)

plan.sort(key=lambda p: (p['src_rid'], p['obj'], p['to']))
n_g = sum(1 for p in plan if p['kind'] == KIND_GUARD)
n_s = sum(1 for p in plan if p['kind'] == KIND_SHIFT)
print(u'计划 %d 条（guard %d / shift %d）' % (len(plan), n_g, n_s))
print(u'丢弃账：%r' % {k: v for k, v in sorted(stat.items())})
if len(plan) != EXPECT_ADD:
    raise SystemExit(u'计划 %d 条 ≠ 期望 %d 条，拒绝写入' % (len(plan), EXPECT_ADD))
if (n_g, n_s) != (EXPECT_GUARD, EXPECT_SHIFT):
    raise SystemExit(u'guard/shift 分项 %d/%d ≠ 期望 %d/%d'
                     % (n_g, n_s, EXPECT_GUARD, EXPECT_SHIFT))

new = []
for i, p in enumerate(plan):
    s_rec, d_rec = SCN.get(p['scene']) or {}, SCN.get(p['to']) or {}
    if p['kind'] == KIND_GUARD:
        reason = (u'原作 GML：房间 %s 里的 %s 触发 `room_goto(%s)`（取证 `conn_ut.json` 的 '
                  u'`if (room == %d)` 常量对；该门对象**确实摆在这间房**的实例表里）。'
                  % (label(s_rec), p['obj'], label(d_rec), p['src_rid']))
        orig = {'chapter': CHAPTER, 'kind': KIND_GUARD, 'via': p['obj'],
                'code': p['code'], 'src_room_name': raw_name(s_rec),
                'dst_room_name': raw_name(d_rec), 'src_room_id': p['src_rid'],
                'dst_room_id': p['dst_rid']}
    else:
        reason = (u'原作 GML：%s 的 `Alarm_2` 调 `room_goto_next()` ⇒ 房间 %s（下标 %d）'
                  u'+1 = %s（下标 %d）。'
                  % (p['obj'], label(s_rec), p['src_rid'], label(d_rec), p['dst_rid']))
        orig = {'chapter': CHAPTER, 'kind': KIND_SHIFT, 'via': p['obj'],
                'code': p['code'], 'room_delta': 1,
                'src_room_name': raw_name(s_rec), 'dst_room_name': raw_name(d_rec),
                'src_room_id': p['src_rid'], 'dst_room_id': p['dst_rid']}
    new.append({'to': p['to'], 'priority': PRIO_BASE + i, 'reason': reason,
                'when_scene': p['scene'], 'when_door': None, 'when_src': p['obj'],
                '_original': orig})

RL_RAW['routes'] = list(RL) + new
_note = (u'★ 第126轮：outertale 新增 **%d** 条门路由（`ot_door_guard` %d / `ot_door_shift` %d，'
         u'priority %d~%d）。此前 outertale **0 条**（"看得到、走不通"）。'
         u'来源＝第115轮 `conn_ut.json` 的原始 op（301 条 goto）+ `inst_full.tsv` 的实例分布；'
         u'`guard` = `if (room == N) room_goto(M)`，且**该门对象真摆在 N 这间房**（实例互证）；'
         u'`shift` = `room_goto_next()`，按实例房 r → r+1（第123轮 ut 同型）。'
         u'**不写**：无条件 `room_goto(M)`（src 未知，%d 条）、守卫与实例打架（%d 条）、'
         u'两端未登记（%d 条）、同(场景,对象)按坐标分叉的多目标（%d 组）、'
         u'`obj_mainchara`（走到屏幕边缘换房，另一层机制）。'
         u'同时把同一组边写进 `_room_graph.json` 的 `chapters.outertale`（逐门寻路读那张图）。'
         u'生成器 `code-quality-audit/第126轮-门型收口/_tools/gen_routes126.py`。'
         % (len(new), n_g, n_s, PRIO_BASE, PRIO_BASE + len(new) - 1,
            stat['drop_uncond_nosrc'], stat['drop_guard_no_inst'],
            stat['drop_unreg'], stat['drop_amb_group']))
RL_RAW.setdefault('meta', {})
RL_RAW['meta']['note'] = (RL_RAW['meta'].get('note') or '') + _note

text = json.dumps(RL_RAW, ensure_ascii=False, indent=2).replace('\n', '\r\n')
with io.open(ROUTES, 'wb') as fh:
    fh.write(text.encode('utf-8'))
print(u'routes 写入完成：总数 %d · %d bytes' % (len(RL_RAW['routes']), len(text.encode('utf-8'))))

# ---------------- 第二层：逐门寻路图 ----------------
G = json.loads(io.open(ROOM_GRAPH, encoding='utf-8', newline='').read())
chs = G.get('chapters')
if not isinstance(chs, dict):
    raise SystemExit(u'房间图缺 chapters')
before = {k: _ch_fp(v) for k, v in chs.items() if k in FROZEN_CH}

grows = []
for p in plan:
    grows.append({'src': p['src_rid'], 'src_name': rooms.get(p['src_rid']) or '',
                  'dst': p['dst_rid'], 'dst_name': rooms.get(p['dst_rid']) or '',
                  'door': p['obj'], 'kind': p['kind']})
grows.sort(key=lambda r: (r['src'], r['door'], r['dst']))
chs[CHAPTER] = {'folder': CHAPTER, 'n_edges': len(grows), 'edges': grows}
G.setdefault('meta', {})['outertale_note'] = (
    u'★ 第126轮：本图新增 `outertale` 章（%d 条边，guard %d / shift %d）。'
    u'`kind=ot_door_guard` / `ot_door_shift`，`door` = 触发它的原作门对象名。'
    u'⚠️ ch1~ch5 与 oneshot 一个字段都没动（生成器内含指纹自证）。' % (len(grows), n_g, n_s))
after = {k: _ch_fp(v) for k, v in chs.items() if k in FROZEN_CH}
if before != after:
    raise SystemExit(u'冻结章被改动了！只许追加 chapters.outertale')
gtext = json.dumps(G, ensure_ascii=False, indent=1).replace('\n', '\r\n')
with io.open(ROOM_GRAPH, 'w', encoding='utf-8', newline='') as fh:
    fh.write(gtext)
print(u'寻路图写入：chapters.outertale %d 边 · %d bytes · 冻结章未变=%s'
      % (len(grows), len(gtext.encode('utf-8')), before == after))
print(u'按对象：%r' % dict(collections.Counter(p['obj'] for p in plan)))
print(u'覆盖：src %d / dst %d / 并集 %d'
      % (len(set(p['scene'] for p in plan)), len(set(p['to'] for p in plan)),
         len(set(p['scene'] for p in plan) | set(p['to'] for p in plan))))

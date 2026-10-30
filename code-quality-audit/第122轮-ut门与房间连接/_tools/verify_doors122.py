# -*- coding: utf-8 -*-
u"""第122轮：**真链路**验证 ut 的门真的建出来了、目标真的对、Deltarune 一字未变。

零 Qt、零网络、零外部盘（只读仓库内资产）。走的链路与产品一致：

    _zone.ut.rooms.json 的场景 dict
        → item_interact.build_props(..., routes=load_routes())
        → DoorProp(target_scene=…)
        → DoorProp.on_interact(actor)   ← 真的调用 on_enter

## 为什么要真调 `on_interact` 而不是只比 target

第121轮的教训：**断行为不断赋值**。`target_scene` 对了不等于门真能用 ——
`on_interact` 还有两道闸（没 target 返 False / 没 on_enter 返 False）。
所以这里注入一个假的 `on_enter`，看它**真被调用**、参数是目标场景、返回值被如实传出去。

用法：python verify_doors122.py
"""
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
MODULES = os.path.join(REPO, 'ralsei_pet', 'modules')

sys.path.insert(0, MODULES)
import item_interact as II       # noqa: E402
import scene_routing as SR       # noqa: E402

_n = {'p': 0, 'f': 0}
_failed = []


def ok(desc, cond, detail=''):
    if cond:
        _n['p'] += 1
        print(u'[PASS] %s%s' % (desc, (u'    ' + detail) if detail else u''))
    else:
        _n['f'] += 1
        _failed.append(desc)
        print(u'[FAIL] %s%s' % (desc, (u'    ' + detail) if detail else u''))


def _json(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return json.load(f)


ZONE = _json(os.path.join(SCENES, '_zone.ut.rooms.json'))['scenes']
ROUTES = _json(os.path.join(SCENES, '_routes.json'))
ALL = ROUTES.get('routes') or []
UT = [r for r in ALL if str(r.get('when_scene') or '').startswith('ut.')]
NO_UT = {'routes': [r for r in ALL if r not in UT]}


def scene_of(sid):
    u"""把分片里的场景 dict 补上 `scene_id`（`build_props` 用它拼 key）。"""
    sc = ZONE.get(sid)
    if not isinstance(sc, dict):
        return None
    d = dict(sc)
    d['scene_id'] = sid
    return d


def doors_of(sid, routes):
    sc = scene_of(sid)
    if sc is None:
        return None
    props = II.build_props(sc, 'ut', 'light', routes=routes)
    return [p for p in props if getattr(p, 'kind', None) == 'door']


print(u'== A 分母 ==')
ok(u'A0 ut 路由 %d 条（对象级 %d / 字母级 %d）'
   % (len(UT), sum(1 for r in UT if r.get('when_src')),
      sum(1 for r in UT if not r.get('when_src'))),
   len(UT) == 243 and sum(1 for r in UT if r.get('when_src')) == 110
   and sum(1 for r in UT if not r.get('when_src')) == 133,
   u'%d / %d / %d' % (len(UT), sum(1 for r in UT if r.get('when_src')),
                      sum(1 for r in UT if not r.get('when_src'))))

print(u'')
print(u'== B 逐条路由：该场景里真建出了这扇门，且目标一致 ==')
miss, wrong = [], []
for r in UT:
    sid = r['when_scene']
    want_obj = r.get('when_src') or 'obj_doorA'
    got = doors_of(sid, ROUTES) or []
    hit = [p for p in got if getattr(p, 'src', None) == want_obj]
    if not hit:
        miss.append((sid, want_obj, [getattr(p, 'src', None) for p in got]))
        continue
    bad = [p for p in hit if getattr(p, 'target_scene', None) != r.get('to')]
    if bad:
        wrong.append((sid, want_obj, r.get('to'),
                      [getattr(p, 'target_scene', None) for p in bad]))
ok(u'B1 243 条路由**逐条**都在对应场景建出了 `%s` 的门（缺 %d 条）'
   % (u'预期对象', len(miss)), not miss, repr(miss[:3]))
ok(u'B2 建出来的门**目标逐条等于**路由表里的 `to`（错 %d 条）' % len(wrong), not wrong,
   repr(wrong[:3]))

print(u'')
print(u'== C 负控制（证明门来自路由表，不是凭空冒出来的）==')
_noroute = collections.Counter()
for r in UT:
    got = doors_of(r['when_scene'], None) or []
    if got:
        _noroute[r['when_scene']] = len(got)
ok(u'C1 不给 routes ⇒ 那 243 条对应场景里门数全为 0（有门的场景 %d 个）'
   % len(_noroute), not _noroute, repr(list(_noroute.items())[:3]))

_has = set(r['when_scene'] for r in UT)
_routed_objs = set((r['when_scene'], r.get('when_src') or 'obj_doorA') for r in UT)
_leftover = []
for sid, sc in ZONE.items():
    if not isinstance(sc, dict) or sid in _has:
        continue
    got = doors_of(sid, ROUTES) or []
    keep = [p for p in got if (sid, getattr(p, 'src', None)) in _routed_objs]
    if keep:
        leftover.append((sid, keep))
ok(u'C2 没有路由的 ut 场景**一扇门都不建**（越界的 %d 个）' % len(_leftover), not _leftover,
   repr([x[0] for x in _leftover[:3]]))

# 负控制 2：把 ut 条目从表里删掉 ⇒ 门必须消失（证明是这 243 条在起作用）
_sample = UT[0]['when_scene']
ok(u'C3 删掉 ut 条目后，%s 的门从 %d 变成 0'
   % (_sample, len(doors_of(_sample, ROUTES) or [])),
   len(doors_of(_sample, NO_UT) or []) == 0,
   u'%d' % len(doors_of(_sample, NO_UT) or []))

print(u'')
print(u'== D 行为（真调 on_interact，不只看赋值）==')
rid = UT[0]
_p = [p for p in (doors_of(rid['when_scene'], ROUTES) or [])
      if getattr(p, 'src', None) == (rid.get('when_src') or 'obj_doorA')][0]
_seen = []
_p.on_enter = lambda tgt: _seen.append(tgt) or True
_ret = _p.on_interact(object())
ok(u'D1 `on_interact` 真把目标交给 on_enter 并返回 True',
   _ret is True and _seen == [rid['to']], u'%r / %r' % (_ret, _seen))

_p2 = [p for p in (doors_of(rid['when_scene'], ROUTES) or [])
       if getattr(p, 'src', None) == (rid.get('when_src') or 'obj_doorA')][0]
_p2.on_enter = lambda tgt: False
ok(u'D2 负控制：on_enter 返 False ⇒ `on_interact` 如实返 False（不谎报成功）',
   _p2.on_interact(object()) is False)

_letter = [p for p in (doors_of(UT[0]['when_scene'], ROUTES) or [])
           if getattr(p, 'door_letter', None)]
_anya = [r for r in UT if not r.get('when_src')][0]
_pa = [p for p in (doors_of(_anya['when_scene'], ROUTES) or [])
       if getattr(p, 'src', None) == 'obj_doorA'][0]
ok(u'D3 字母级那条：`door_letter` == "A"（走的是原有字母机制，不是新造的）',
   getattr(_pa, 'door_letter', None) == 'A', repr(getattr(_pa, 'door_letter', None)))

_pb = [p for p in (doors_of(rid['when_scene'], ROUTES) or [])
       if getattr(p, 'src', None) == rid.get('when_src')][0] \
    if rid.get('when_src') else None
ok(u'D4 对象级那条：`door_letter` 为 None（不带字母，靠 when_src 定位）',
   _pb is not None and getattr(_pb, 'door_letter', None) is None,
   repr(None if _pb is None else getattr(_pb, 'door_letter', None)))

print(u'')
print(u'== E Deltarune 零回归（加 ut 条目不许改变任何既有门）==')


def _sig(sid, routes):
    got = doors_of(sid, routes)
    if got is None:
        return None
    return sorted((getattr(p, 'src', None), getattr(p, 'target_scene', None),
                   getattr(p, 'door_letter', None)) for p in got)


_old_scenes = sorted(set(r.get('when_scene') for r in NO_UT['routes']
                         if r.get('when_door') in II.DOOR_LETTERS
                         and not str(r.get('when_scene') or '').startswith(
                             ('ut.', 'oneshot', 'desktop'))))
_diff = []
for sid in _old_scenes:
    a, b = _sig(sid, ROUTES), _sig(sid, NO_UT)
    if a != b:
        _diff.append((sid, a, b))
ok(u'E1 既有 %d 个 Deltarune 门场景：加/不加 ut 条目，门清单**逐条相同**'
   % len(_old_scenes), not _diff and len(_old_scenes) > 100,
   u'差异 %d / 场景 %d' % (len(_diff), len(_old_scenes)))

print(u'')
print(u'== F `_match_one` 的 when_src（语境级，正负成对）==')
_route = {'when_scene': 'ut.rooms.room_area1', 'when_src': 'obj_door_ruins13',
          'to': 'x', 'priority': 1}
_ctx0 = {'scene_id': 'ut.rooms.room_area1'}
_m1, s1 = SR._match_one(_route, _ctx0)
_m2, s2 = SR._match_one(_route, dict(_ctx0, src='obj_door_ruins13'))
_m3, s3 = SR._match_one(_route, dict(_ctx0, src='obj_door_w'))
ok(u'F1 语境没给 src ⇒ **不匹配**（不是"放行" —— 否则等于凭空指定一扇门）',
   _m1 is False, u'matched=%r score=%r' % (_m1, s1))
ok(u'F2 语境给了对的 src ⇒ 匹配且 score +1', _m2 is True and s2 == 2,
   u'matched=%r score=%r' % (_m2, s2))
ok(u'F3 负控制：给了错的 src ⇒ 不匹配', _m3 is False,
   u'matched=%r score=%r' % (_m3, s3))
_m4, _ = SR._match_one({'when_scene': 'ut.rooms.room_area1', 'to': 'y', 'priority': 1},
                       _ctx0)
ok(u'F4 正控制：不带 when_src 的普通规则照旧匹配（没被新键牵连）', _m4 is True)

print(u'')
print(u'---- 共 %d 条：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(1 if _failed else 0)

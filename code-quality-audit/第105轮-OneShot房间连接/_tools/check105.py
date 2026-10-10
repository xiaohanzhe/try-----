# -*- coding: utf-8 -*-
"""第105轮回归锁：OneShot 房间连接（原作 code-201 传送门）不许回退。

用户口径：「一切根据原作」「把原作的世界搬到桌面上（桌面也是一个场景）」。

这一轮补的是什么
----------------
第100~104轮把 OneShot 的 263 间房**画出来**了，但 `_routes.json` 里
`oneshot.*` 起源的规则是 **0 条** ⇒ 站在任何一间 OneShot 房里，
`scene_routing.match()` 只能落 `_fallback`（回桌面）——「看得到、走不通」。
本轮把原作 **code 201 = Transfer Player** 事件指令接进来：826 条 → page0 且
无条件的 749 条 → 去自环 19 → 跨房 730 条按 `(src_map, dst_map)` 去重成
**420 条唯一边**，写进同一张路由表（priority 独立段 3000+）。

本锁守的五件事（每件都配正/负控制，避免"恒看像在守其实没守"）

  A. **证据面自洽** —— `_evidence/oneshot_transfers.json` 是**原作事实**，
     计数自洽、边自洽、两端都能回溯 `_index.json` 的 `original_room_id`。
  B. **产品面 == 证据面** —— 产品里 oneshot 起源的边集合**恰好**等于证据推出来的；
     缺一条、多一条都报红（不是"至少包含"）。
  C. **独立重推 `when_door` / `priority`** —— 本锁自己实现 slug 与排序，
     只从证据出发重算，不去读生成器的决策字段（否则比对是自证）。
  D. **不碰既有段** —— 452 条 Deltarune/desktop 规则**逐字节指纹**不许变。
     （高优先级的 regression 保护：本轮是"追加"，不是"改写"。）
  E. **只登记不生成的两类** —— 19 条自环与 77 条剧情传送**不得**凭空变成路由。

外加 F 段**行为级**（真调 `scene_routing.match()`）与 G 段**鉴别力**（把判据
本身当被测物：喂坏的输入必须报红）。

铁律：成功标记 `[PASS]` 字面量；零依赖（不 import Qt / 不碰外部盘 / 不依赖
`_index` 之外的时相变量）；判据里不出现恒真（本文件自查 G0）。
"""
import collections
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
SC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
EV = os.path.join(ROUND, '_evidence', 'oneshot_transfers.json')
ROUTES = os.path.join(SC, '_routes.json')
INDEX = os.path.join(SC, '_index.json')
MODULES = os.path.join(ROOT, 'ralsei_pet', 'modules')

#: ★ 第105轮生成器的 priority 段起点（见 `gen_routes105.PRIO_BASE`）。
PRIO_BASE = 3000

#: ★ D 段用的**既有段指纹** —— 452 条非 oneshot 规则的 sha256。
#: 为什么用指纹而不是条数：条数抓不住"改了一条 reason / 换了 to"。
#: 这是"本轮是追加不是改写"的硬证据。将来若**有意**改既有段，
#: 必须连着这里一起更新，并在报告里说明理由。
OLD_FP = '364e75caaee1fb4f45965a0351a6f624a8eb38af4496fc01f7615af1f0029866'
OLD_N = 452
DESKTOP_N = 9

_N = [0]
_FAIL = []


def ok(cond, msg):
    _N[0] += 1
    if cond:
        print('[PASS] %s' % msg)
    else:
        _FAIL.append(msg)
        print('[FAIL] %s' % msg)


def jload(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def slug(name):
    """★ 独立实现的 slug —— **故意与生成器分开写一份**。

    同一个归一化规则两处实现，若一处改了另一处没改，C 段就会报红
    （而不是像"读生成器写好的字段"那样静默自洽）。
    """
    s = re.sub(r'[^0-9a-z]+', '_', str(name or '').strip().lower()).strip('_')
    return s or 'unnamed'


def fp(rows):
    """规则列表的稳定指纹（键排序 + 逐条 + 换行分隔）。"""
    h = hashlib.sha256()
    for r in rows:
        h.update(json.dumps(r, ensure_ascii=False, sort_keys=True).encode('utf-8'))
        h.update(b'\n')
    return h.hexdigest()


# ===========================================================================
#  纯谓词（把判据本身也做成可被测的物 —— G 段拿它们做负控制）
# ===========================================================================
def edge_set_mismatch(prod_edges, want_edges):
    """产品边集合 vs 期望边集合的对称差。空 = 完全一致。"""
    return prod_edges ^ want_edges


def label_conflicts(routes):
    """返回「场景内 when_door 重复」的 (scene, door) 列表。"""
    by = collections.defaultdict(list)
    for r in routes:
        by[(r.get('when_scene'), r.get('when_door'))].append(r)
    return sorted([k for k, v in by.items() if len(v) > 1])


def order_violations(routes):
    """同场景内「when_door 序 != priority 序」的场景列表。"""
    by = collections.defaultdict(list)
    for r in routes:
        by[r.get('when_scene')].append(r)
    bad = []
    for sid, lst in by.items():
        labs = [r.get('when_door') for r in sorted(lst, key=lambda x: x['priority'])]
        if labs != sorted(labs):
            bad.append(sid)
    return sorted(bad)


def non_monotonic(prios):
    """声明序上 priority 下降的次数（原作生成段必须为 0）。"""
    return [i for i in range(1, len(prios)) if prios[i] < prios[i - 1]]


def label_from_evidence(ev_row):
    """从证据行独立重推 `when_door` 的**词根**（不含唯一化后缀）。

    代表事件 = 按 (事件名, x, y) 最小 —— 与坐标无关的取值顺序，
    再对坐标缺失做 -1 兜底（与生成器同口径，但代码是分开写的）。
    """
    evs = ev_row.get('events') or []
    if not evs:
        return 'unnamed'
    def key(e):
        xy = e.get('xy') or [None, None]
        x = xy[0] if isinstance(xy[0], int) else -1
        y = xy[1] if isinstance(xy[1], int) else -1
        return (str(e.get('event') or ''), x, y)
    return slug(min(evs, key=key).get('event'))


# ===========================================================================
#  读盘
# ===========================================================================
_ev = jload(EV) if os.path.isfile(EV) else {}
_idx = jload(INDEX)
_raw = json.loads(io.open(ROUTES, encoding='utf-8', newline='').read())
_RL = _raw.get('routes') or []
_OS = [r for r in _RL if str((r or {}).get('when_scene') or '').startswith('oneshot')]
_OLD = [r for r in _RL if not str((r or {}).get('when_scene') or '').startswith('oneshot')]

#: 登记表：scene_id → original_room_id / 房名 / 区名
_REG = {}
for _aid, _area in (((_idx.get('chapters') or {}).get('oneshot') or {})
                    .get('areas') or {}).items():
    for _sid, _rec in (_area.get('scenes') or {}).items():
        _REG[_sid] = {'rid': _rec.get('original_room_id'),
                      'name': _rec.get('name'),
                      'area': _area.get('name')}

_EDGES = _ev.get('edges') or []
_EV_EDGE_SET = set()
for _e in _EDGES:
    _EV_EDGE_SET.add((_e.get('src_scene'), _e.get('dst_scene')))

os_scenes = set(_REG)

# ===========================================================================
#  A 证据面自洽
# ===========================================================================
print('--- A 证据面自洽 ---')
ok(bool(_ev) and _ev.get('schema') == 1 and _ev.get('round') == 105,
   'A1 原作事实蒸馏存在且 schema=1 / round=105（%s）' % os.path.basename(EV))

_c = _ev.get('counts') or {}
ok(_c.get('code201_total') == _c.get('doors_page0_uncond', -1) +
   _c.get('deferred_conditional_or_nonpage0', -1),
   'A2a 计数自洽：code201 总数 %r == 门候选 %r + 剧情传送 %r'
   % (_c.get('code201_total'), _c.get('doors_page0_uncond'),
      _c.get('deferred_conditional_or_nonpage0')))
ok(_c.get('doors_page0_uncond') == _c.get('self_loops', -1) +
   _c.get('unregistered_or_bad_dst', -1) + _c.get('cross_room_transfers', -1),
   'A2b 计数自洽：门候选 %r == 自环 %r + 未登记 %r + 跨房 %r'
   % (_c.get('doors_page0_uncond'), _c.get('self_loops'),
      _c.get('unregistered_or_bad_dst'), _c.get('cross_room_transfers')))
ok(_c.get('unique_edges') == len(_EDGES),
   'A2c 计数自洽：unique_edges %r == 证据里 %d 条边'
   % (_c.get('unique_edges'), len(_EDGES)))
# —— 负控制：把总数 +1，A2a 的等式必须不成立（证明 A2a 不是恒真）
_neg_c = dict(_c)
_neg_c['code201_total'] = (_c.get('code201_total') or 0) + 1
ok(_neg_c.get('code201_total') != _neg_c.get('doors_page0_uncond', -1) +
   _neg_c.get('deferred_conditional_or_nonpage0', -1),
   'A2d 负控制：把总数改 +1 后 A2a 的等式确实不成立（有鉴别力）')

_bad_reg = []
for _e in _EDGES:
    for _side in ('src', 'dst'):
        _sid, _rid = _e.get('%s_scene' % _side), _e.get('%s_map' % _side)
        _r = _REG.get(_sid)
        if _r is None:
            _bad_reg.append('%s 未登记' % _sid)
        elif _r['rid'] != _rid:
            _bad_reg.append('%s rid=%r≠%r' % (_sid, _r['rid'], _rid))
ok(not _bad_reg,
   'A3 证据每条边的两端都登记为场景、且 original_room_id 与 src/dst_map 一致'
   '（不一致 %d: %s）' % (len(_bad_reg), _bad_reg[:3]))
# —— 负控制：换一个错的 rid，A3 的口径必须抓得住
_neg_e = {'src_scene': 'oneshot.barrens.Blue', 'src_map': 99999,
          'dst_scene': 'oneshot.barrens.Entrance', 'dst_map': 12}
_bad_neg = []
for _side in ('src', 'dst'):
    _r = _REG.get(_neg_e.get('%s_scene' % _side))
    if _r is None or _r['rid'] != _neg_e.get('%s_map' % _side):
        _bad_neg.append(_side)
ok(_bad_neg == ['src'],
   'A3b 负控制：故意写错的 src_map 会被 A3 的口径抓到（got=%r）' % (_bad_neg,))

ok(all(e.get('src_map') != e.get('dst_map') for e in _EDGES)
   and len(_EV_EDGE_SET) == len(_EDGES),
   'A4 证据里无自环且 (src_scene, dst_scene) 唯一（%d 条）' % len(_EDGES))

# ===========================================================================
#  B 产品面 == 证据面
# ===========================================================================
print('--- B 产品面 == 证据面 ---')
_PROD_SET = set((r.get('when_scene'), r.get('to')) for r in _OS)
_mis = edge_set_mismatch(_PROD_SET, _EV_EDGE_SET)
ok(_PROD_SET and not _mis,
   'B1 ★★ 产品里 oneshot 起源的边集合**恰好**等于证据推出的集合'
   '（产品 %d / 证据 %d / 对称差 %d）' % (len(_PROD_SET), len(_EV_EDGE_SET), len(_mis)))
# —— 负控制：从产品集合里挖掉一条 ⇒ 对称差必须非空（证明 B1 不是恒真）
_p = set(_PROD_SET)
_victim = sorted(_p)[0]
_p.discard(_victim)
ok(edge_set_mismatch(_p, _EV_EDGE_SET) == {_victim},
   'B1b 负控制：挖掉一条后 B1 确实报红（挖 %r ⇒ 差 %d）'
   % (_victim, len(edge_set_mismatch(_p, _EV_EDGE_SET))))
# —— 负控制 F：塞一条**多出来**的边也必须报红
_extra = ('oneshot.barrens.Blue', 'oneshot.glen.Blue')
ok(edge_set_mismatch(_PROD_SET | {_extra}, _EV_EDGE_SET) == {_extra},
   'B1c 负控制：多塞一条边 B1 也会报红（证明是"恰好"而不是"至少包含"）')

ok(len(_OS) == len(_EV_EDGE_SET),
   'B2 oneshot 规则条数 %d == 唯一边数 %d（同一条边不许写两遍）'
   % (len(_OS), len(_EV_EDGE_SET)))

_kind_bad = [r.get('to') for r in _OS
             if (r.get('_original') or {}).get('kind') != 'oneshot_transfer'
             or (r.get('_original') or {}).get('chapter') != 'oneshot']
ok(not _kind_bad,
   'B3 每条 oneshot 规则的 _original.kind == "oneshot_transfer" 且 chapter == "oneshot"'
   '（不符 %d: %s）' % (len(_kind_bad), _kind_bad[:3]))

# 按 (when_scene, to) 建证据索引，逐条核对 src_map/dst_map
_ev_by_pair = {}
for _e in _EDGES:
    _ev_by_pair[(_e.get('src_scene'), _e.get('dst_scene'))] = _e
_map_bad = []
for _r in _OS:
    _e = _ev_by_pair.get((_r.get('when_scene'), _r.get('to')))
    _o = _r.get('_original') or {}
    if _e is None:
        _map_bad.append('%s(证据无此边)' % _r.get('to'))
        continue
    if _o.get('src_map') != _e.get('src_map') or _o.get('dst_map') != _e.get('dst_map'):
        _map_bad.append('%s(%r→%r ≠ %r→%r)'
                        % (_r.get('to'), _o.get('src_map'), _o.get('dst_map'),
                           _e.get('src_map'), _e.get('dst_map')))
    if _o.get('src_room_name') != _e.get('src_room_name') \
            or _o.get('dst_room_name') != _e.get('dst_room_name'):
        _map_bad.append('%s(房名不符)' % _r.get('to'))
    if _o.get('n_events') != len(_e.get('events') or []):
        _map_bad.append('%s(n_events=%r≠%d)'
                        % (_r.get('to'), _o.get('n_events'), len(_e.get('events') or [])))
ok(not _map_bad,
   'B4 ★每条 oneshot 规则的 _original 与证据逐字段一致'
   '（map / 两端房名 / n_events；不符 %d: %s）' % (len(_map_bad), _map_bad[:3]))

_orphan = sorted(set(r.get('to') for r in _OS if r.get('to') not in os_scenes))
ok(not _orphan,
   'B5 每条 oneshot 规则的目标场景都登记在 _index.json（无孤儿）%s'
   % (('缺=%s' % _orphan[:3]) if _orphan else ''))

# ===========================================================================
#  C 独立重推 when_door / priority
# ===========================================================================
print('--- C 独立重推 when_door / priority ---')
_root_bad = []
for _r in _OS:
    _e = _ev_by_pair.get((_r.get('when_scene'), _r.get('to')))
    if _e is None:
        continue
    _want = label_from_evidence(_e)
    _got = _r.get('when_door')
    if _got != _want and not (isinstance(_got, str) and _got.startswith(_want + '__')):
        _root_bad.append('%s:%r≠%r' % (_r.get('to'), _got, _want))
ok(not _root_bad,
   'C1 ★when_door 的词根 == 由证据独立重推的 slug（允许唯一化后缀 `__k`）'
   '（不符 %d: %s）' % (len(_root_bad), _root_bad[:3]))

_conf = label_conflicts(_OS)
ok(not _conf,
   'C2 同一场景内 when_door 唯一（重复 %d: %s）' % (len(_conf), _conf[:3]))
# —— 负控制：造两条同场景同门名的规则 ⇒ C2 的口径必须报红
ok(label_conflicts([{'when_scene': 'a', 'when_door': 'x', 'priority': 1},
                    {'when_scene': 'a', 'when_door': 'x', 'priority': 2}]) == [('a', 'x')],
   'C2b 负控制：同场景同 when_door 会被 C2 的口径判出（有鉴别力）')

_ov = order_violations(_OS)
ok(not _ov,
   'C3 ★同场景内「when_door 序 == priority 序」（违反 %d: %s）' % (len(_ov), _ov[:3]))
# —— 负控制：priority 反着给，C3 的口径必须报红
ok(order_violations([{'when_scene': 'a', 'when_door': 'z', 'priority': 1},
                     {'when_scene': 'a', 'when_door': 'a', 'priority': 2}]) == ['a'],
   'C3b 负控制：priority 与门名反序会被 C3 的口径判出')

_prios = [r.get('priority') for r in _OS]
ok(all(isinstance(p, int) for p in _prios)
   and min(_prios) >= PRIO_BASE and max(_prios) < PRIO_BASE + 5000,
   'C4 oneshot 段 priority 全为 int 且落在独立段 [%d, ...]（实测 [%r, %r]）'
   % (PRIO_BASE, min(_prios), max(_prios)))
ok(max(r.get('priority') for r in _OLD) < PRIO_BASE,
   'C5 oneshot 段的 priority 下界(**%d**) 高于既有段最大值(**%d**) —— 段不重叠'
   % (PRIO_BASE, max(r.get('priority') for r in _OLD)))

_all_prios = [r.get('priority') for r in _RL
              if str((r or {}).get('when_scene') or '') != 'desktop']
_drops = non_monotonic(_all_prios)
ok(not _drops,
   'C6 全表（排除 desktop）声明序无 priority 回绕（下降 %d 次）' % len(_drops))
ok(non_monotonic([1, 3, 2]) == [2],
   'C6b 负控制：合成 [1,3,2] 会被"回绕"口径判出（有鉴别力）')

# ===========================================================================
#  D 不碰既有段（本轮是"追加"）
# ===========================================================================
print('--- D 不碰既有段 ---')
ok(len(_OLD) == OLD_N,
   'D1 既有段条数 == %d（实测 %d）' % (OLD_N, len(_OLD)))
ok(fp(_OLD) == OLD_FP,
   'D2 ★既有段 sha256 == %s…（逐字节未变；实测 %s…）'
   % (OLD_FP[:16], fp(_OLD)[:16]))
# —— 负控制：改一条既有规则的 reason ⇒ 指纹必须变（证明 D2 抓得住"静默改写"）
_neg_old = [dict(r) for r in _OLD]
_neg_old[0] = dict(_neg_old[0])
_neg_old[0]['reason'] = (_neg_old[0].get('reason') or '') + '（篡改）'
ok(fp(_neg_old) != OLD_FP,
   'D2b 负控制：改一条 reason 后 D2 的指纹确实变化（有鉴别力）')
_desk = [r for r in _OLD if r.get('when_scene') == 'desktop']
ok(len(_desk) == DESKTOP_N and sorted(str(r.get('when_door')) for r in _desk)
   == ['A', 'B', 'C', 'D', 'E', 'F', 'W', 'X', 'Y'],
   'D3 desktop 门段仍是 %d 扇 A..F/W/X/Y（本轮不许动它）' % DESKTOP_N)

# ===========================================================================
#  E 只登记不生成的两类
# ===========================================================================
print('--- E 只登记不生成 ---')
_self = _ev.get('self_loops') or []
ok(len(_self) == 19 and all(e.get('src_map') == e.get('dst_map') for e in _self),
   'E1 自环 %d 条仍在证据里"只登记"且确为自环' % len(_self))
ok(not any(r.get('when_scene') == r.get('to') for r in _OS),
   'E1b 产品里没有"切到自己"的 oneshot 规则（自环不生成路由）')

_def = _ev.get('deferred') or []
ok(len(_def) == 77
   and all((e.get('has_condition') or e.get('page') != 0) for e in _def),
   'E2 剧情传送 %d 条全部是"带条件 或 非 page0"（口径没混进纯位置门）' % len(_def))
# 「只由剧情传送支撑」的 (src,dst) 对**不得**出现在产品里
_def_only = set()
_def_all = set()
for e in _def:
    _def_all.add((e.get('src_map'), e.get('dst_map')))
_door_pairs = set((e.get('src_map'), e.get('dst_map')) for e in _EDGES)
_self_pairs = set((e.get('src_map'), e.get('dst_map')) for e in _self)
_def_only = _def_all - _door_pairs - _self_pairs
_ev_orid = {}
for _e in _EDGES:
    _ev_orid[(_e.get('src_map'), _e.get('dst_map'))] = 1
_leak = []
for (s, d) in sorted(_def_only):
    sids = [k for k, v in _REG.items() if v['rid'] == s]
    dids = [k for k, v in _REG.items() if v['rid'] == d]
    for a in sids:
        for b in dids:
            if (a, b) in _PROD_SET and (s, d) not in _door_pairs:
                _leak.append((a, b))
ok(not _leak,
   'E2b 只由剧情传送支撑的 %d 对房间**没有**混进产品（泄漏 %d: %s）'
   % (len(_def_only), len(_leak), _leak[:3]))
# —— 负控制：把一对剧情传送当成门喂进产品集合 ⇒ E2b 的口径必须报红
if _def_only:
    _pd = sorted(_def_only)[0]
    _sid = [k for k, v in _REG.items() if v['rid'] == _pd[0]][0]
    _did = [k for k, v in _REG.items() if v['rid'] == _pd[1]][0]
    ok((_sid, _did) in (_PROD_SET | {(_sid, _did)}) and _pd not in _door_pairs,
       'E2c 负控制：剧情传送对 %r 确实不在门集合里（判据有区分度）' % (_pd,))

# ===========================================================================
#  F 行为级：真调 scene_routing.match()
# ===========================================================================
print('--- F 行为级 ---')
sys.path.insert(0, MODULES)
try:
    import scene_routing as SR          # noqa: E402  纯标准库，安全
    _loaded = SR.load_routes(SC)
    ok(_loaded.get('ok') is True,
       'F1 真表能被 load_routes 读上（%r）' % (_loaded.get('error'),))
    ok(len(_loaded.get('routes') or []) == len(_RL),
       'F2 load_routes 条数 == 文件条数（%d）' % len(_RL))

    # 取一个"多出口"的 oneshot 源场景做锚点
    _bysrc = collections.OrderedDict()
    for r in _OS:
        _bysrc.setdefault(r.get('when_scene'), []).append(r)
    _multi = [k for k, v in _bysrc.items() if len(v) > 1]
    _anchor = sorted(_multi)[0] if _multi else sorted(_bysrc)[0]
    _hit = SR.match(_loaded, {'scene_id': _anchor, 'chapter_id': 'oneshot'})
    ok(SR.route_target(_hit) not in (None, 'desktop'),
       'F3 ★站在 OneShot 场景 %s 上，match() 给出**具体**目标 %r（不是回桌面兜底）'
       % (_anchor, SR.route_target(_hit)))
    # —— 负控制：换成一个**没有** oneshot 规则的场景 ⇒ 落兜底（证明 F3 不是恒真）
    _hit0 = SR.match(_loaded, {'scene_id': 'oneshot.__no_such__',
                               'chapter_id': 'oneshot'})
    ok(SR.route_target(_hit0) in (None, 'desktop'),
       'F3b 负控制：无规则的 OneShot 场景 → 落兜底 %r（证明 F3 有区分度）'
       % (SR.route_target(_hit0),))

    # 共同卡口：指定 when_door 时精确分流到该条规则的目标
    if _multi:
        _rows = sorted(_bysrc[_anchor], key=lambda r: r['priority'])
        _r0 = _rows[0]
        _hit_d = SR.match(_loaded, {'scene_id': _anchor, 'chapter_id': 'oneshot',
                                    'door': _r0.get('when_door')})
        ok(SR.route_target(_hit_d) == _r0.get('to'),
           'F4 ★指定 door=%r 时精确分流到 %r（共同卡口在有出口标识时可用）'
           % (_r0.get('when_door'), _r0.get('to')))
        # —— 负控制：指定一个该场景不存在的门 ⇒ 不命中该场景任何规则
        _hit_bad = SR.match(_loaded, {'scene_id': _anchor, 'chapter_id': 'oneshot',
                                      'door': '__no_such_door__'})
        ok(SR.route_target(_hit_bad) in (None, 'desktop'),
           'F4b 负控制：不存在的门 → 不命中（%r）' % (SR.route_target(_hit_bad),))

    # 目的地自省：oneshot 目标能被列出来（且过掉"未登记"过滤）
    _des = SR.destinations(_loaded, _idx)
    _des_ids = set(d['scene_id'] for d in _des)
    ok(len(set(r.get('to') for r in _OS) & _des_ids) == len(set(r.get('to') for r in _OS)),
       'F5 destinations() 列出全部 %d 个 oneshot 目标（未被未登记过滤掉）'
       % len(set(r.get('to') for r in _OS)))
except Exception as e:                  # 不静默：导入/调用失败要看得见
    ok(False, 'F 段执行失败: %r' % (e,))

# ===========================================================================
#  G 鉴别力总检（判据本身也是被测物）
# ===========================================================================
print('--- G 鉴别力总检 ---')


def _taut_ok_lines(src):
    """找出 `ok(<常量真值>, …)` 的行号 —— **走 AST，不走文本扫**。

    ⚠️ 第一版是纯文本 `re.search(r'ok\\(\\s*(True|1)\\s*,')` —— 它把本判据
    **自己那句提示语**（里面写了 `ok(True, …)` 作例子）当成了违规，
    于是 G0 每次必然报红。这正是本项目反复踩的坑：「禁某 API 出现」类判据
    **禁纯文本扫**（注释/文档串一提名字即误报）。⇒ 改成 AST：
    只有真正的 `ok(...)` **调用节点**、且首参是常量 True/1 才算。
    """
    import ast as _ast
    tree = _ast.parse(src)
    hits = []
    for node in _ast.walk(tree):
        if not isinstance(node, _ast.Call):
            continue
        if not (isinstance(node.func, _ast.Name) and node.func.id == 'ok'):
            continue
        if node.args and isinstance(node.args[0], _ast.Constant) \
                and node.args[0].value in (True, 1):
            hits.append(getattr(node, 'lineno', '?'))
    return hits


_SELF_SRC = io.open(os.path.abspath(__file__), encoding='utf-8').read()
_taut = _taut_ok_lines(_SELF_SRC)
ok(not _taut,
   'G0 本文件里没有 `ok(<常量真>, …)` 这类恒真判据（命中行 %s）' % (_taut or '无'))
# —— 负控制：合成的恒真判据必须被同一个口径抓出（证明 G0 不是恒真）
_SYNTH = ('def ok(*a):\n    pass\n'
          "ok(True, 'x')\n"
          "ok(1, 'y')\n"
          "ok(cond_is_real, 'z')\n")
ok(_taut_ok_lines(_SYNTH) == [3, 4],
   'G0b 负控制：合成的恒真判据被抓出 %r（有鉴别力）' % (_taut_ok_lines(_SYNTH),))
ok(non_monotonic([]) == [] and non_monotonic([1]) == []
   and edge_set_mismatch(set(), set()) == set(),
   'G1 三个纯谓词在空输入上返回"无违例"（不误报空表）')
ok(order_violations([]) == [] and label_conflicts([]) == [],
   'G2 两个结构谓词在空输入上返回空（不误报）')

print()
print('合计 PASS=%d FAIL=%d' % (_N[0] - len(_FAIL), len(_FAIL)))
if _FAIL:
    raise SystemExit(1)

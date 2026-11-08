# -*- coding: utf-8 -*-
u"""第174轮 · 「`obj_doorAnyHorz/Vert` 物化 + 落边」回归锁。

## 本轮做了什么

第173轮把 `obj_doorAny` 的 820 个实例物化了，但**同一家族的另外两个变体一扇都没补**：

    obj_doorAnyHorz          42（仅 ch5）
    obj_doorAnyVert           9（仅 ch5）
    obj_doorAnyModespecific   0（对象表里有，五章**零实例**）

于是 `ch5.garden.garden_shrine` 这种房间在原作里有 3 扇 Horz 门、产品里**一扇都没有**
⇒ 没有出口。本轮补：**51 条边 + 51 个物件**。

## 三件必须先弄清的事实（都在 A/B 段独立重算）

1. **取证早就有，不用重跑 UTMT。** 第172轮探针按**子串** `doorany` 过滤对象名，
   四个变体全部被录进 `probe_any172.ch5.json`（每条带自己的 `creation_gml`）。
   `analyze172.json` 的 `via` 全 None 只是分析脚本没把 `obj` 带进 rows
   （881 = 830 + 42 + 9，一条不少）。
2. **A/B 双盲**：`csx` 探针（UTMT 对象模型）与第42轮 CLI 普查是两条独立读取路径，
   逐变体的 `{(room_index, x, y)}` 集合**完全相等**（42/42、9/9）。
3. **★ 第172轮有 42 条边的 `via` 说假话。** 用 `precreate` 名字反查探针里的真实实例：
   798 条里有 42 条（Horz 36 / Vert 6）真身是**变体**，却被标成 `obj_doorAny`。
   本轮**只留档不修**（改标签会动第172轮与第36轮两套账，须单独一轮裁定），
   所以 B6/B7 两条把它们钉住：172 那 798 条一条都不许动。

## 判据分五段

- A 段：取证账（数量 / 逐变体 A/B / 逐章 / 分类 / 两房都登记 / 零实例变体）
- B 段：路由对账（51 条一一对应取证实例 / 目标真实 / priority 段 / 字段齐全 / 负控制 / 老账不动）
- C 段：**端到端**（真过 `build_props` → `route_for_door`）
- D 段：不造 + 反回滚（条数 / 既有物件没动 / 形状 / 查重 / 载体两路 / 未登记泄漏）
- E 段：自检（单一 harness / AST 查恒真 / 零外部盘 / 不起真机 / 零网络）

★ 环境变量口子（只给 `mutate174.py` 用，判据本身一行不改）
  `CQ_PKG174` / `CQ_EV42_174` / `CQ_EV172_174` / `CQ_ROUTES_174`
"""
import ast
import collections
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.environ.get('CQ_PKG174') or os.path.join(REPO, 'ralsei_pet')
SCENES = os.environ.get('CQ_SCENES_174') or os.path.join(PKG, 'assets', 'scenes')
OBJS = os.path.join(SCENES, 'objs')
EV = os.path.join(ROUND, '_evidence')
E42 = os.environ.get('CQ_EV42_174') or os.path.join(
    REPO, 'code-quality-audit', u'第42轮-原作拓扑取证', '_evidence')
E172 = os.environ.get('CQ_EV172_174') or os.path.join(
    REPO, 'code-quality-audit', u'第172轮-Any门接线', '_evidence')
SELF = os.path.abspath(__file__)

for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from modules.item_interact import build_props, classify, door_letter_of, \
    route_for_door  # noqa: E402
from modules.scene_system import load_obj_visible, is_drawable_object  # noqa: E402

#: 本轮补的两个变体（**不含** `obj_doorAny`，那是第173轮的）
HORZ = 'obj_doorAnyHorz'
VERT = 'obj_doorAnyVert'
WANT = (HORZ, VERT)
#: 整个 doorany 家族（第173轮 + 本轮）；`obj_doorAnyModespecific` 零实例，只登记不补
FAMILY = ('obj_doorAny', HORZ, VERT, 'obj_doorAnyModespecific')

#: ---- 口径锚点（全部在 A/B 段独立重算，不是"随手写的数"）----
EXPECT_INST = 51          # 取证里的变体实例（42 Horz + 9 Vert）
EXPECT_HORZ = 42
EXPECT_VERT = 9
EXPECT_ROOMS = 29         # 落在 29 个「章:房间」键上
EXPECT_EDGES = 51         # 本轮新增的路由条数（**一条实例一条边**）
EXPECT_RESOLVED = 42      # 端到端解析出的「场景→不同目标」对数（去重）
EXPECT_MULTI = 11         # 同房多扇、目标两两不同的场景数
EXPECT_FILES_ZONE = 3     # 分片载体
EXPECT_FILES_ONE = 1      # 独立场景文件载体
PRIO_BASE = 8100
PRIO_END = PRIO_BASE + EXPECT_EDGES - 1
EXPECT_ROUTES_FLOOR = 2810   # 2,759 + 51
EXPECT_ANY_172 = 798         # 第172轮的 `when_src == obj_doorAny` 条数，**本轮一条不许动**
EXPECT_MISLABEL = 42         # 172 里 via 说假话的条数（Horz 36 + Vert 6），只留档不修
EXPECT_ORIG_OBJS = 3197      # 第68轮普查口径（五章 · 非 doorany 家族）
EXPECT_DESKTOP_DOORS = 4
CHECK_FLOOR = 35

INST42 = {'ch1': 'inst42.json', 'ch2': 'ch2_inst42.json', 'ch3': 'ch3_inst42.json',
          'ch4': 'ch4_inst42.json', 'ch5': 'ch5_inst42.json'}
CHS = ('ch1', 'ch2', 'ch3', 'ch4', 'ch5')

_n = {'p': 0, 'f': 0}
_bad = []


def check(desc, cond, extra=u''):
    if cond:
        _n['p'] += 1
        print('[PASS] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        _n['f'] += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace',
                              newline='').read())


# ---------------------------------------------------------------------------
# 一、源数据
# ---------------------------------------------------------------------------
AN = jl(os.path.join(EV, 'analyze174.json'))
INDEX = jl(os.path.join(SCENES, '_index.json'))
ROUTES_RAW = jl(os.path.join(SCENES, '_routes.json'))
ROUTES = ROUTES_RAW.get('routes') if isinstance(ROUTES_RAW, dict) else ROUTES_RAW
ROUTES = ROUTES or []


def index_room_of():
    out = {}
    for _ch, blk in ((INDEX.get('chapters')) or {}).items():
        if not isinstance(blk, dict):
            continue
        for _a, ablk in ((blk.get('areas')) or {}).items():
            if not isinstance(ablk, dict):
                continue
            for sid, e in ((ablk.get('scenes')) or {}).items():
                if isinstance(e, dict) and isinstance(e.get('original_room_id'), int):
                    out[str(sid)] = int(e['original_room_id'])
    return out


ROOM_OF = index_room_of()
REG = set((ch, rid) for ch, rid in
          [(k.split('.')[0], v) for k, v in ROOM_OF.items()])


# ---------------------------------------------------------------------------
# 二、产品侧载体
# ---------------------------------------------------------------------------
def scene_units():
    out = []
    for name in sorted(os.listdir(SCENES)):
        if not name.endswith('.json'):
            continue
        if name.startswith('_') and not name.startswith('_zone.'):
            continue
        try:
            d = jl(os.path.join(SCENES, name))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        inner = d.get('scenes')
        if isinstance(inner, dict):
            ch = d.get('chapter_id')
            for sid, sc in inner.items():
                if not isinstance(sc, dict):
                    continue
                rid = sc.get('original_room_id')
                if not isinstance(rid, int):
                    rid = ROOM_OF.get(str(sc.get('scene_id') or sid))
                out.append((name, ch, rid, sc, str(sc.get('scene_id') or sid)))
        elif 'objects' in d or 'scene_id' in d:
            sid = str(d.get('scene_id') or '')
            rid = d.get('original_room_id')
            if not isinstance(rid, int):
                rid = ROOM_OF.get(sid)
            out.append((name, d.get('chapter_id'), rid, d, sid))
    return out


UNITS = scene_units()


def unit_var(sc):
    return [(tuple(o.get('pos') or ()), o)
            for o in (sc.get('objects') or [])
            if isinstance(o, dict) and o.get('src') in WANT]


def unit_any(sc):
    return [(tuple(o.get('pos') or ()), o)
            for o in (sc.get('objects') or [])
            if isinstance(o, dict) and o.get('src') == 'obj_doorAny']


def rows_ok():
    return [r for r in (AN.get('rows') or [])
            if r.get('obj') in WANT and r.get('kind') == 'static_dst_ok'
            and r.get('src')]


# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'A 段  取证账（全部独立重算）')
print('=' * 70)

_ROWS_ALL = [r for r in (AN.get('rows') or []) if r.get('obj') in WANT]
_c_horz = len([r for r in _ROWS_ALL if r['obj'] == HORZ])
_c_vert = len([r for r in _ROWS_ALL if r['obj'] == VERT])
check(u'A0 取证：变体实例 %d 条 == %d（Horz %d + Vert %d）'
      % (len(_ROWS_ALL), EXPECT_INST, EXPECT_HORZ, EXPECT_VERT),
      len(_ROWS_ALL) == EXPECT_INST and _c_horz == EXPECT_HORZ
      and _c_vert == EXPECT_VERT and len(rows_ok()) == EXPECT_INST,
      u'（不读脚本自报数；分类不全是 ok 的话 A3 会红）')

# ---- A1 ★ A/B 双盲：csx 探针 vs 第42轮 CLI 普查（两条独立读取路径）----
_probe = collections.defaultdict(set)
for ch, fn in (('ch1', 'probe_any172.ch1.json'), ('ch2', 'probe_any172.ch2.json'),
               ('ch3', 'probe_any172.ch3.json'), ('ch4', 'probe_any172.ch4.json'),
               ('ch5', 'probe_any172.ch5.json')):
    p = os.path.join(E172, fn)
    if not os.path.isfile(p):
        continue
    for i in (jl(p).get('instances') or []):
        if i.get('obj') in WANT:
            _probe[(ch, i['obj'])].add((i.get('room_index'), i.get('x'), i.get('y')))
_census = collections.defaultdict(set)
for ch, fn in INST42.items():
    p = os.path.join(E42, fn)
    if not os.path.isfile(p):
        continue
    for rec in (jl(p).get('rooms') or []):
        rid = rec.get('index')
        if not isinstance(rid, int):
            continue
        for it in (rec.get('insts') or []):
            if it.get('obj') in WANT:
                _census[(ch, it['obj'])].add((rid, it.get('x'), it.get('y')))
_ab_bad = sorted(k for k in set(_probe) | set(_census)
                 if _probe.get(k, set()) != _census.get(k, set()))
check(u'A1 ★★ A/B 双盲：%d 个 (章,变体) 键里 %d 个不一致（csx 探针 vs 第42轮 CLI 普查，'
      u'逐实例 (房,x,y) 集合）' % (len(set(_probe) | set(_census)), len(_ab_bad)),
      not _ab_bad and len(_probe) == 2,
      u'不一致=%r；分母=%r' % (_ab_bad[:3],
                            sorted((k, len(v)) for k, v in _census.items())))

_by_ch = collections.Counter(r['ch'] for r in _ROWS_ALL)
check(u'A2 逐章分布：ch1~ch4 各 0 扇、ch5 %d 扇（两个变体**只存在于 ch5**）'
      % _by_ch.get('ch5', 0),
      all(_by_ch.get(c, 0) == 0 for c in ('ch1', 'ch2', 'ch3', 'ch4'))
      and _by_ch.get('ch5', 0) == EXPECT_INST,
      u'实得=%r' % (dict(_by_ch),))

_kind = collections.Counter(r['kind'] for r in _ROWS_ALL)
check(u'A3 分类账：%d 扇**全部**拿到 `doorRoom` 字面量且目标房已登记（unmapped/debug/'
      u'unknown 各 0）' % EXPECT_INST,
      _kind.get('static_dst_ok', 0) == EXPECT_INST and len(_kind) == 1,
      u'分布=%r' % (dict(_kind),))

check(u'A4 源房全登记（源房未登记 %d 条）⇒ 51 条边一条都不用"硬塞到别的载体"'
      % sum(1 for r in _ROWS_ALL if not r.get('src')),
      all(r.get('src') for r in _ROWS_ALL),
      u'缺 src 的=%r' % ([r.get('room') for r in _ROWS_ALL if not r.get('src')][:3],))

_keys = set((r['ch'], r['room_index']) for r in _ROWS_ALL)
check(u'A5 分母：落在 %d 个「章:房间」键上、每个键都在 `_index.json` 里登记过'
      % len(_keys),
      len(_keys) == EXPECT_ROOMS and all(k in REG for k in _keys),
      u'实得=%d 未登记=%r' % (len(_keys), [k for k in _keys if k not in REG][:3]))

_pairs = set((r['src'], r['dst']) for r in rows_ok())
check(u'A7 ★为什么**一条实例一条边**而不是一对一条：(源,目标) 去重后只有 %d 对，'
      u'按对落边会吞掉 %d 扇（第二扇的坐标在表里没有对应条目 ⇒ `_pick_by_pos` 挑不出唯一 '
      u'⇒ 退回 priority 最小 ⇒ 静默走错房间）'
      % (len(_pairs), EXPECT_INST - len(_pairs)),
      len(_pairs) < EXPECT_INST and len(_pairs) > 0,
      u'（"按对去重会少几条"这件事必须由数据自己说出来，不能只写在注释里）')

_modes = [r for r in (AN.get('rows') or []) if r.get('obj') == 'obj_doorAnyModespecific']
_modes_census = _census.get(('ch5', 'obj_doorAnyModespecific'), set()) \
    | _census.get(('ch4', 'obj_doorAnyModespecific'), set())
check(u'A6 `obj_doorAnyModespecific` 五章**零实例** ⇒ 本轮如实不补（不是漏了）',
      not _modes and not _modes_census,
      u'（但它在 `_obj_visible.json` 的 hidden 名单里、`classify` 也认它是 door —— '
      u'登记齐全、实例为零，这一条是"零实例"的凭据）')

# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'B 段  路由对账')
print('=' * 70)

VE = [q for q in ROUTES if isinstance(q, dict) and q.get('when_src') in WANT]
check(u'B0 `_routes.json` 里 `when_src` 属于变体的边 %d 条 == %d'
      % (len(VE), EXPECT_EDGES), len(VE) == EXPECT_EDGES)

_key_ev = set((r['src'], r['dst'], r['obj'], r['x'], r['y']) for r in rows_ok())
_key_rt = set((q.get('when_scene'), q.get('to'), q.get('when_src'),
               (q.get('_original') or {}).get('door_x'),
               (q.get('_original') or {}).get('door_y')) for q in VE)
check(u'B1 ★★一一对应：%d 条边 == 取证里 %d 条实例（(场景,目标,变体,x,y) 集合相等）'
      % (len(_key_rt), len(_key_ev)),
      _key_rt == _key_ev,
      u'只在表里=%r 只在取证=%r' % (sorted(_key_rt - _key_ev)[:3],
                                sorted(_key_ev - _key_rt)[:3]))

_all_scenes = set(ROOM_OF.keys())
_bad_to = [q.get('to') for q in VE if q.get('to') not in _all_scenes]
check(u'B2 51 条边的目标场景**全部真实存在**（%d 个不同目标）'
      % len(set(q.get('to') for q in VE)),
      not _bad_to, u'不存在的=%r' % (_bad_to[:3],))

_prios = sorted(q.get('priority') for q in VE)
check(u'B3 priority 段连续且唯一：%d ~ %d（共 %d 条，无重复无空洞）'
      % (PRIO_BASE, PRIO_END, EXPECT_EDGES),
      _prios == list(range(PRIO_BASE, PRIO_END + 1)),
      u'实得首尾=%r 去重后 %d 条' % ((_prios[0], _prios[-1]) if _prios else None,
                                 len(set(_prios))))

_NEED = ('chapter', 'kind', 'table', 'own_event', 'via', 'precreate',
         'src_room_name', 'dst_room_name', 'src_room_id', 'door_x', 'door_y', 'batch')
_miss, _badval = [], []
for q in VE:
    o = q.get('_original') or {}
    lack = [k for k in _NEED if k not in o]
    if lack:
        _miss.append((q.get('when_scene'), lack))
    if o.get('via') != q.get('when_src') or o.get('batch') != 174 \
            or o.get('kind') != 'delta_door_any_variant':
        _badval.append((q.get('when_scene'), o.get('via'), o.get('batch'), o.get('kind')))
check(u'B4 `_original` 字段齐全且自洽（`via` == `when_src`、`batch`=174、'
      u'`kind`=delta_door_any_variant）；缺字段 %d、值不符 %d'
      % (len(_miss), len(_badval)),
      not _miss and not _badval,
      u'缺=%r 不符=%r' % (_miss[:3], _badval[:3]))

check(u'B5 负控制：`route_for_door` 对**编造的变体名**必须返 None（不是"总能查到"）',
      route_for_door(ROUTES, 'ch5.garden.garden_shrine', None,
                     src='obj_doorAnyHorzFAKE', pos=None) is None
      and route_for_door(ROUTES, 'ch5.garden.garden_shrine', None,
                         src=HORZ, pos=None) is not None)

_any172 = [q for q in ROUTES if isinstance(q, dict) and q.get('when_src') == 'obj_doorAny']
check(u'B6 ★★老账不动：第172轮的 `when_src == obj_doorAny` 仍 %d 条，'
      u'且本轮一条都没被改标签（`kind` 不是 delta_door_any_variant）'
      % EXPECT_ANY_172,
      len(_any172) == EXPECT_ANY_172
      and not [q for q in _any172
               if (q.get('_original') or {}).get('kind') == 'delta_door_any_variant'],
      u'实得=%d' % len(_any172))

# ---- B7 ★ 留档：172 那 798 条里有 42 条的 `via` 说假话（真身是变体）----
_pc2obj = {}
for ch, fn in (('ch1', 'probe_any172.ch1.json'), ('ch2', 'probe_any172.ch2.json'),
               ('ch3', 'probe_any172.ch3.json'), ('ch4', 'probe_any172.ch4.json'),
               ('ch5', 'probe_any172.ch5.json')):
    p = os.path.join(E172, fn)
    if not os.path.isfile(p):
        continue
    for i in (jl(p).get('instances') or []):
        if i.get('creation_code'):
            _pc2obj[(ch, i['creation_code'])] = i['obj']
_b172 = [q for q in ROUTES if (q.get('_original') or {}).get('batch') == 172]
_mislabel = [q for q in _b172
             if _pc2obj.get(((q['_original']).get('chapter'),
                             (q['_original']).get('precreate'))) in WANT]
check(u'B7 ★留档（**不修**）：172 的 %d 条边里有 %d 条 `via` 标的 `obj_doorAny` '
      u'其实来自变体（用 `precreate` 反查探针的真实实例）—— 改标签要动第172/36轮两套账，'
      u'留待单独一轮裁定' % (len(_b172), len(_mislabel)),
      len(_b172) == EXPECT_ANY_172 and len(_mislabel) == EXPECT_MISLABEL,
      u'（这条红只可能意味着两件事之一：172 的边被改过，或探针取证被换了）')

# ★ B8：实例创建代码的名字是**机械生成**的 `gml_RoomCC_<源房名>_<实例号>_PreCreate`
#   ⇒ 拿它反查"这条边真是这间房摆的那扇门吗"，是**编不出来**的硬证据。
#   第36轮就靠这条口径抓过"按房间硬凑边"的坏数据，本轮沿用。
_bad_pc = []
for q in VE:
    o = q.get('_original') or {}
    rn, pc = o.get('src_room_name'), o.get('precreate')
    if not isinstance(pc, str) or not isinstance(rn, str) \
            or not pc.startswith('gml_RoomCC_' + rn + '_') \
            or not pc.endswith('_PreCreate'):
        _bad_pc.append((q.get('when_scene'), rn, pc))
check(u'B8 `precreate` 必须形如 `gml_RoomCC_<源房名>_<n>_PreCreate`（与源房对得上）：'
      u'不符 %d 条' % len(_bad_pc),
      not _bad_pc,
      u'（代码名是机械生成的 ⇒ 这条等于"边是不是这间房摆的那扇门"的第三方证据，'
      u'不靠我自己写下的 `src_room_name` 自证）')

# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'C 段  端到端消费（build_props → route_for_door → 目标场景）')
print('=' * 70)
check(u'C0 分类器认得两个变体：`classify(kind) == door` 且 `door_letter_of` 为 None'
      u'（无字母 ⇒ 只能走对象级 `when_src` 那一路）',
      all((classify(v) or {}).get('kind') == 'door' for v in WANT)
      and all(door_letter_of(v) is None for v in WANT),
      u'%r' % ([ (v, (classify(v) or {}).get('kind'), door_letter_of(v)) for v in WANT ],))

_act = []
for _u in UNITS:
    _act.extend(unit_var(_u[3]))
check(u'C1 产品侧：`src ∈ {Horz, Vert}` 的物件 %d 条 == 取证 %d 条'
      % (len(_act), EXPECT_INST), len(_act) == EXPECT_INST)

_targets, _resolved, _unres = {}, 0, []
for label, ch, rid, sc, sid in UNITS:
    insts = unit_var(sc)
    if not insts:
        continue
    sc2 = dict(sc)
    sc2['scene_id'] = sid
    props = build_props(sc2, ch or (sid or '').split('.')[0], None, routes=ROUTES)
    got = [p for p in props if getattr(p, 'src', None) in WANT]
    _resolved += len(got)
    for p in got:
        _targets.setdefault(sid, set()).add(getattr(p, 'target_scene', None))
    if len(got) < len(insts):
        _unres.append((sid, len(insts), len(got)))

check(u'C2 ★★端到端：%d 条实例里 **%d 条真的建出门并解析出目标**（`build_props` 实测）'
      % (EXPECT_INST, _resolved),
      _resolved == EXPECT_INST and not _unres,
      u'实得=%d，没建出来的场景=%r' % (_resolved, _unres[:3]))

check(u'C3 解析出的 %d 个「场景→不同目标」对，目标**全部真实存在**'
      % sum(len(v) for v in _targets.values()),
      sum(len(v) for v in _targets.values()) == EXPECT_RESOLVED
      and all(t in _all_scenes for vs in _targets.values() for t in vs if t)
      and all(t for vs in _targets.values() for t in vs),
      u'不存在的=%r' % ([t for vs in _targets.values() for t in vs
                       if not t or t not in _all_scenes][:3],))

_multi = {s: ts for s, ts in _targets.items() if len(ts) >= 2}
check(u'C4 ★同房多扇变体门**分流到不同目标**的场景 %d 个（`_pick_by_pos` 真的在起作用）'
      % len(_multi),
      len(_multi) == EXPECT_MULTI,
      u'（若这里变成 1 个，说明 `door_x/door_y` 没记或者记错了）')

# ★★★ 负控制：把本轮的 51 条边**摘掉**再跑一次 ⇒ 必须一条门都建不出来
_nove = [q for q in ROUTES if q.get('when_src') not in WANT]
_lost = 0
for label, ch, rid, sc, sid in UNITS:
    if not unit_var(sc):
        continue
    sc2 = dict(sc)
    sc2['scene_id'] = sid
    _lost += len([p for p in build_props(sc2, ch, None, routes=_nove)
                  if getattr(p, 'src', None) in WANT])
check(u'C5 ★★负控制：摘掉本轮 51 条边后，同一个 `build_props` 建出的变体门数从 %d 掉到 %d'
      u'（证明这些门**确实**靠本轮新边，不是别处兜的）' % (_resolved, _lost),
      _lost == 0 and _resolved > 0)

_probe_sid = None
for label, ch, rid, sc, sid in UNITS:
    if len(_targets.get(sid) or ()) >= 2:
        _probe_sid = sid
        break
if _probe_sid is None:
    check(u'C6 负控制：多扇场景"不给 pos 退回 priority 最小"', False, u'找不到多扇场景')
else:
    _a = route_for_door(ROUTES, _probe_sid, None, src=HORZ, pos=None)
    _b = route_for_door(ROUTES, _probe_sid, None, src=HORZ, pos=[-999999, -999999])
    check(u'C6 负控制：不给 pos / 给不存在的坐标 ⇒ 退回 priority 最小，**两次答案相同**',
          _a is not None and _a == _b, u'%s -> %r / %r' % (_probe_sid, _a, _b))

# ★★ C7：本轮**不改可达图** —— 42 个 (源,目标) 对在"不含本轮 51 条边"的旧表里
#      就已经全部存在。这句话必须由数据自己说，否则"补了 51 条边"很容易被误读成
#      "新增了 51 条通路"。真实效果是：把**原本无人消费的死边**变成了**真能走过去的门**。
_old_pairs = set((q.get('when_scene'), q.get('to')) for q in ROUTES
                 if isinstance(q, dict) and q.get('when_src') not in WANT)
_new_only = sorted(_pairs - _old_pairs)
check(u'C7 ★★可达图不变：42 个 (源,目标) 对里，**%d 个**在旧表（不含本轮 51 条）中就已存在 '
      u'⇒ 本轮不新增任何新通路，只把死边变活门' % (len(_pairs) - len(_new_only)),
      not _new_only,
      u'只在本地新增的对=%r' % (_new_only[:3],))

# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'D 段  不造 + 反回滚')
print('=' * 70)

check(u'D0 `_routes.json` 条数 %d >= %d（本轮 +%d；用 floor 不写死绝对数，'
      u'因为后续轮次只许往上加）' % (len(ROUTES), EXPECT_ROUTES_FLOOR, EXPECT_EDGES),
      len(ROUTES) >= EXPECT_ROUTES_FLOOR,
      u'实得=%d' % len(ROUTES))

_non_fam = 0
for _u in UNITS:
    if _u[1] not in CHS:
        continue
    for o in (_u[3].get('objects') or []):
        if isinstance(o, dict) and o.get('src') not in FAMILY:
            _non_fam += 1
_desktop_p = os.path.join(SCENES, 'desktop.json')
_desktop = len((jl(_desktop_p).get('objects') or [])) if os.path.isfile(_desktop_p) else -1
check(u'D1 既有 objects **一个都没被改**：五章非 doorany 家族 %d == %d、桌面世界门 %d == %d'
      % (_non_fam, EXPECT_ORIG_OBJS, _desktop, EXPECT_DESKTOP_DOORS),
      _non_fam == EXPECT_ORIG_OBJS and _desktop == EXPECT_DESKTOP_DOORS,
      u'（把整个 doorany 家族排除在外，这样第173/174轮各自的增量都撞不到这条）')

_badshape = []
for label, ch, rid, sc, sid in UNITS:
    for pos, o in unit_var(sc):
        if not (isinstance(o.get('pos'), (list, tuple)) and len(o['pos']) == 2
                and all(isinstance(v, int) for v in o['pos'])):
            _badshape.append((label, 'pos', o))
        if o.get('sprite') is not None:
            _badshape.append((label, 'sprite 非 None', o))
        if 'depth' in o and not isinstance(o['depth'], int):
            _badshape.append((label, 'depth', o))
check(u'D2 条目形状：pos=2×int / **无 sprite**（原作 visible=false，写了才是假话）'
      u'—— 坏 %d' % len(_badshape),
      not _badshape, u'首个=%r' % ((_badshape[0] if _badshape else None),))

_dup = []
for label, ch, rid, sc, sid in UNITS:
    c = [(o.get('src'), p) for p, o in unit_var(sc)]
    if len(c) != len(set(c)):
        _dup.append((label, c))
check(u'D3 无重复条目（同场景同变体同坐标只允许一条）重复场景=%d' % len(_dup),
      not _dup, u'首个=%r' % ((_dup[0] if _dup else None),))

_leak = [(u[0], u[1], u[2], len(unit_var(u[3])))
         for u in UNITS if unit_var(u[3]) and (u[1], u[2]) not in _keys]
check(u'D4 变体物件没有泄漏到别的载体（29 个键之外一条都不许有）：泄漏 %d 处'
      % len(_leak), not _leak, u'首个=%r' % ((_leak[0] if _leak else None),))

_zone_files = set(u[0] for u in UNITS if u[0].startswith('_zone.') and unit_var(u[3]))
_file_files = set(u[0] for u in UNITS if not u[0].startswith('_zone.') and unit_var(u[3]))
check(u'D5 两种载体**都写到了**：分片文件 %d 个、独立场景文件 %d 个（分别覆盖 %d / %d 个场景）'
      % (len(_zone_files), len(_file_files),
         len([u for u in UNITS if u[0] in _zone_files and unit_var(u[3])]),
         len([u for u in UNITS if u[0] in _file_files and unit_var(u[3])])),
      len(_zone_files) == EXPECT_FILES_ZONE and len(_file_files) == EXPECT_FILES_ONE,
      u'（★ 这里数的是**文件**不是场景：3 个分片里装着 28 个场景；只写中一边就说明注入器漏了一路，'
      u'第173轮踩过这个坑）')

check(u'D6 可见性一致：两个变体都在 `_obj_visible.json` 的 hidden 名单里 ⇒ '
      u'`is_drawable_object(..., hidden)` 判不可绘制',
      all(v in load_obj_visible() for v in WANT)
      and all(is_drawable_object({'src': v}, load_obj_visible()) is False for v in WANT)
      and is_drawable_object({'src': 'obj_doorAnyHorz'}) is True,
      u'（★ `hidden` 是必传参数，不传恒 True —— 这条同时钉住这个坑）')

# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'E 段  自检')
print('=' * 70)

_src = io.open(SELF, encoding='utf-8').read()
_tree = ast.parse(_src)
_harness = [n.name for n in _tree.body
            if isinstance(n, ast.FunctionDef)
            and n.name in ('check', 'ok', 'PASS', 'FAIL', 'report')]
check(u'E0 单一 harness：本文件只有 `check()` 一个判据出口（找到 %r）' % (_harness,),
      _harness == ['check'], u'混用两套 harness 会让"查恒真"各查一套、漏掉另一半')

_MARK = '[' + 'PASS' + ']'
_cst = [n.value for n in ast.walk(_tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and _MARK in n.value]
check(u'E1 判据标记（PASS 括号）作为字符串字面量只出现 1 处（找到 %d 处）' % len(_cst),
      len(_cst) == 1, u'G2 的 `count_results()` 靠正则数这个标记，散着写会数错')

_trivial = []
for n in ast.walk(_tree):
    if not isinstance(n, ast.Call) or not isinstance(n.func, ast.Name) \
            or n.func.id != 'check':
        continue
    if len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) \
            and n.args[1].value is True:
        _trivial.append(getattr(n, 'lineno', 0))
check(u'E2 AST 查恒真：没有 `check(..., True)` 这种写死的绿（找到 %d 处 %r）'
      % (len(_trivial), _trivial), not _trivial)

check(u'E3 判据条数 %d >= %d（判据太少等于没锁）' % (_n['p'] + _n['f'], CHECK_FLOOR),
      _n['p'] + _n['f'] >= CHECK_FLOOR, u'（本条自己也算一条，所以是"跑完再看"）')

_DRV = re.compile('[A-Za-z]' + ':' + r'[\\/]')
_ext = _DRV.findall(_src)
check(u'E4 零外部盘：源码里没有盘符开头的绝对路径字面量（找到 %d 处）' % len(_ext),
      not _ext, u'回归不许依赖外部盘/临时区')

_MAIN_IMP = 'import ' + 'main'
_TRUE_APP = 'Ralsei' + 'Pet('
check(u'E5 不构造真机 App：本文件不 import `main`、也不出现真机构造调用',
      _MAIN_IMP not in _src and _TRUE_APP not in _src)

_NET = ['import ' + m for m in ('requests', 'urllib', 'socket', 'http.client')]
_hit_net = [k for k in _NET if k in _src]
check(u'E6 零网络：本文件不 import 网络库（命中 %r）' % (_hit_net,), not _hit_net)

# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'合计：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _bad:
    print(u'红项：')
    for _b in _bad:
        print(u'  - %s' % _b)
print('=' * 70)
sys.exit(1 if _n['f'] else 0)

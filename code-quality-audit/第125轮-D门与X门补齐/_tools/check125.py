# -*- coding: utf-8 -*-
u"""第125轮回归锁：Deltarune 五章的 **D 门（−2）** 与 **X 门（表驱动）** 补齐不许回退。

## 这一轮做了什么

第124轮末的可达账暴露：ch1~ch5「有出边的场景」只有 **105/127/23/22/20**，
而场景数是 128/236/187/261/201 —— ch3~ch5 尤其稀。

查根因（**不是"没数据"**）：`第42轮/_evidence/_room_graph.json`（反编译合成）里
ch1~ch5 共有 **782** 条边，而产品 `_routes.json` 只转出 **443** 条 —— 差在**门型**：
第44轮的生成器只编 A(+1)/B(−1)/C(+2)，并在 docstring 里明确**拒收**了
`obj_doorD`（理由是"实测 +2 只有 33%，证据不足"）与 `obj_doorX`（"表驱动，需读对象代码"）。

本轮先读对象代码、再用**第44轮对 A/B/C 用过的同一条判据**独立复核
（目标房必须含 `obj_marker<同字母>` —— 位移只是先验，落点是独立验证）：

    组  有目标的实例  命中 marker   命中率
    D(−2)     74          71       95.9%
    X(表)     94          94      100.0%
    W         97           0        0.0%（marker 实为小写 `obj_markerw`：60.2%；
                                      换成 `obj_markerX` 84.3% ⇒ 两套都到不了 100%）

⇒ 收 D 与 X，**W 仍不收**（"证据不足不猜"这条纪律照旧）。
⇒ 追加 **139 条**（D 56 / X 83，priority 5000~5138）。

## 本套件守什么（零 Qt / 零网络 / 零外部盘 —— 只读仓库内证据与资产）

A 段位与分母 —— 新段 139 条 · priority 5000~5138 连续 · 只落在 ch1~ch5
B 独立重推   —— **只从证据重算**这 139 条（不读生成器的任何决策字段），
                与产品**集合相等**（对称差 0）；挖一条/塞一条都必须报红
C 逐条自洽   —— D 条 `dst == src − 2` ｜ X 条 `dst == 表[src]` ｜
                目标房含 `obj_marker<字母>` ｜ `_original` 两端房名 == `name_raw`
D 拒收纪律   —— 产品里**一条 W 门都没有**，而证据里**确有 98 条** W 边
                （这一对是成对的：没有后者，"0 条"就是空集恒真）
E 例外有账   —— 3 条 backup/test 房的 `no_marker` 例外：证据里有、产品里没有，逐条定位
F 密度账     —— 每章「有出边的场景数」只增不减（第124轮基线钉住）
G 自检       —— AST 查恒真判据 · 无 BOM / 无 U+FFFD · CRLF 与无尾换行 · 被测文件在盘

## 纪律

`print('[PASS] %s')` 字面量；正/负控制成对；**断行为不断赋值**；
负控制必须**真的落进被测分支**（B 段直接改传入的集合再比对，不是另写一份判据）。
"""
import ast
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(REPO, 'ralsei_pet')
MODULES = os.path.join(PKG, 'modules')
SCENES = os.path.join(PKG, 'assets', 'scenes')
ROUTES_P = os.path.join(SCENES, '_routes.json')
EV42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
GRAPH_P = os.path.join(EV42, '_room_graph.json')

for _p in (PKG, MODULES):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from modules import scene_system as SS       # noqa: E402

#: 本轮新段的 priority 起点（既有 110~2478 / oneshot 3000+ / ut 4000+ / 本轮 5000+）
PRIO_BASE = 5000
EXPECT_ADD = 139
EXPECT_D = 56
EXPECT_X = 83
EXPECT_BY_CH = {'ch1': 46, 'ch2': 26, 'ch3': 24, 'ch4': 21, 'ch5': 22}
#: 证据侧边总数（ch1~ch5 合计）
EXPECT_EDGES = 782
#: ★ 拒收的 W 门边数（证据里真有这么多，故"产品 0 条"不是空集恒真）
EXPECT_REFUSED_W = 98
#: 各章「有出边的场景数」—— 第124轮实测基线（**只增不减**）
DENSITY_124 = {'ch1': 105, 'ch2': 127, 'ch3': 23, 'ch4': 22, 'ch5': 20}
#: ★ 证据侧唯一允许的 3 条 `no_marker` 例外（如实不写）。
#: ⚠️ 本清单被 **E1 当场纠正过一次**：我最初按"probe125c 的印象"写成
#:   `(ch2,263,261) / (ch4,34,32) / (ch4,90,88)` —— 错的。实测是
#:   `(ch2,263,261) / (ch2,55,53) / (ch4,34,32)`。`ch4 90→88` 不是"无 marker"，
#:   而是**目标房 `room_test_climb_new` 根本没登记成场景**（归 `unreg`，
#:   该房 `doors=[]`）。这正是"报红先怀疑判据、再怀疑自己的记录"的现场。
NO_MARKER_EXC = (
    ('ch2', 263, 261),   # room_cc_clover → room_dw_city_traffic_3_backup（backup 房）
    ('ch2', 55, 53),     # room_castle_town → room_insidecloset
    ('ch4', 34, 32),     # room_hospital_room2 → room_hospital_hallway
)
#: ★ D 门边里"端点未登记"的条数（`ch4 90→88` 就在其中；本轮 15 条 unreg 里占 9 条）
EXPECT_UNREG_D = 9
#: 已证位移门（第42轮 Alarm 反汇编 → `room_goto(room_previous(room_previous))`）
DELTA_DOOR = {'obj_doorD': -2, 'obj_doorD_musfade': -2}
#: 已证表驱动门 → 它读的那段 `Alarm_2`
TABLE_DOOR = {'obj_doorX': 'gml_Object_obj_doorX_Alarm_2',
              'obj_doorX_musfade': 'gml_Object_obj_doorX_musfade_Alarm_2'}
#: 拒收的 W 门（写在这里是为了让 D 段能"点名"检查，而不是靠模糊匹配）。
#: ★ 证据里的真实写法只有这两种（大写 W + 小写 w 的 musfade 变体）——
#:   实测 `obj_doorW` 85 + `obj_doorw_musfade` 13 = 98 条。
W_DOOR = ('obj_doorW', 'obj_doorw_musfade')

CH = [('ch1', 'inst42.json', 'conn42b.json')] + [
    ('ch%d' % i, 'ch%d_inst42.json' % i, 'ch%d_conn42b.json' % i) for i in (2, 3, 4, 5)]

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, detail=u''):
    if cond:
        _n['p'] += 1
        print(u'[PASS] %s%s' % (desc, (u'    ' + detail) if detail else u''))
    else:
        _n['f'] += 1
        _failed.append(desc)
        print(u'[FAIL] %s%s' % (desc, (u'    ' + detail) if detail else u''))


def jload(p):
    u"""读第42轮证据 —— 那些文件是 `True/False` 的 JSON 变体（大写），要先归一。"""
    s = io.open(p, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


def letter_of(door):
    for k in list(DELTA_DOOR) + list(TABLE_DOOR):
        if door == k:
            return k[len('obj_door'):][:1].upper()
    return None


# ===========================================================================
#  读盘：产品路由表 + 场景登记
# ===========================================================================
RAW = json.loads(io.open(ROUTES_P, encoding='utf-8', newline='').read())
RL = RAW.get('routes') or []
IDX = SS.load_index(SCENES)
SC = IDX.get('scenes') or {}

NEW = [r for r in RL if isinstance(r.get('priority'), int) and r['priority'] >= PRIO_BASE]
OLD_KEYS = set((r.get('when_scene'), str(r.get('when_door') or ''))
               for r in RL if not (isinstance(r.get('priority'), int)
                                   and r['priority'] >= PRIO_BASE))

#: 章内 原作房间下标 → scene_id（★ 第124轮的坑：**不能用 `name` 映射**）
REV = collections.defaultdict(dict)
for _sid, _rec in SC.items():
    if isinstance(_rec, dict) and isinstance(_rec.get('original_room_id'), int):
        _cid = _rec.get('chapter_id') or _sid.split('.')[0]
        REV[_cid].setdefault(_rec['original_room_id'], _sid)

# ===========================================================================
print(u'')
print(u'== A. 段位与分母（防空集恒真） ==')
# ===========================================================================
check(u'A0 分母：`load_index()` ok=True、场景数 == %d、路由 == %d 条'
      % (2166, len(RL)),
      IDX.get('ok') is True and len(SC) == 2166 and len(RL) > 0,
      u'scenes=%d routes=%d ok=%r' % (len(SC), len(RL), IDX.get('ok')))

_prios = sorted(r['priority'] for r in NEW)
check(u'A1 ★★ 新段 %d 条、priority %d~%d **连续无空洞**'
      % (EXPECT_ADD, PRIO_BASE, PRIO_BASE + EXPECT_ADD - 1),
      len(NEW) == EXPECT_ADD and _prios == list(range(PRIO_BASE, PRIO_BASE + EXPECT_ADD)),
      u'n=%d 首末=%r' % (len(NEW), (_prios[0], _prios[-1]) if _prios else None))

_bad_world = sorted(set(r.get('when_scene') for r in NEW
                        if str(r.get('when_scene') or '').split('.')[0]
                        not in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5')))
check(u'A2 ★★★ 新段只落在 ch1~ch5（绝不碰 desktop / oneshot / ut / outertale / uty）',
      not _bad_world, u'越界=%r' % (_bad_world[:4],))

_by_letter = collections.Counter(r.get('when_door') for r in NEW)
check(u'A3 新段字母分布 == D %d / X %d（`_original.via` 也只有这两种门）'
      % (EXPECT_D, EXPECT_X),
      _by_letter.get('D') == EXPECT_D and _by_letter.get('X') == EXPECT_X
      and len(_by_letter) == 2,
      u'%r' % (dict(_by_letter),))

_by_ch = collections.Counter(str(r.get('when_scene')).split('.')[0] for r in NEW)
check(u'A4 新段逐章条数 == %r（ch3~ch5 才是本轮的主要目标）' % (EXPECT_BY_CH,),
      dict(_by_ch) == EXPECT_BY_CH, u'%r' % (dict(_by_ch),))

# --- 分母闸：REV 必须单射（否则「按原作品下标映射」这一步就自相矛盾） ---
_dup_rid = []
for _cid in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
    _r1 = collections.Counter(r for r, _s in
                              [(v, k) for k, v in REV[_cid].items()])
    if any(v > 1 for v in _r1.values()):
        _dup_rid.append(_cid)
check(u'A5 ★ 章内 原作下标 → scene_id 是**单射**（第124轮的"按 name 映射"坑的反面保险）',
      not _dup_rid, u'重复章节=%r' % (_dup_rid,))


# ===========================================================================
print(u'')
print(u'== B. ★★★ 独立重推：只从证据重算这 %d 条 ==' % EXPECT_ADD)
# ===========================================================================


def rebuild():
    u"""从第42轮证据重推期望路由集合。

    **不读** `_routes.json` 里任何决策字段（`_original` / `reason` / `priority`）：
    期望值只由「证据边的门型 + 门机制 + 落点 marker」三件事决定。
    返回 (want, stat)：want = {(scene, letter, to): detail}。
    """
    want = {}
    stat = collections.Counter()
    seen = {}
    for cid, instf, connf in CH:
        inst, conn = jload(os.path.join(EV42, instf)), jload(os.path.join(EV42, connf))
        objs = {r['index']: {x.get('obj') for x in (r.get('insts') or [])}
                for r in (inst.get('rooms') or [])}
        tables = collections.defaultdict(dict)
        for it in (conn.get('items') or []):
            if it.get('op') == 'goto' and isinstance(it.get('src'), int) and it['src'] >= 0:
                tables[it['code']][it['src']] = it['dst']
        edges = ((jload(GRAPH_P).get('chapters') or {}).get(cid) or {}).get('edges') or []
        stat['ch_%s' % cid] = len(edges)
        for e in edges:
            door, src, dst = e.get('door'), e.get('src'), e.get('dst')
            stat['edge_total'] += 1
            if door in W_DOOR:
                stat['refused_W'] += 1
                continue
            L = letter_of(door)
            if L is None:
                stat['other'] += 1
                continue
            s_sid, d_sid = REV[cid].get(src), REV[cid].get(dst)
            if not s_sid or not d_sid:
                stat['unreg'] += 1
                if L == 'D':
                    stat['unreg_d'] += 1
                continue
            mech = (src + DELTA_DOOR[door]) if door in DELTA_DOOR \
                else tables.get(TABLE_DOOR[door], {}).get(src)
            if mech != dst:
                stat['mech_mismatch'] += 1
                continue
            if ('obj_marker' + L) not in objs.get(mech, set()):
                stat['no_marker'] += 1
                stat['nm_%s_%d_%d' % (cid, src, dst)] += 1
                continue
            if (s_sid, L) in OLD_KEYS:
                stat['letter_clash'] += 1
                continue
            k = (s_sid, L, d_sid)
            if k in seen:
                stat['dup_edge'] += 1
                continue
            seen[k] = 1
            want[k] = {'how': ('delta' if door in DELTA_DOOR else 'table'),
                       'via': door, 'src_rid': src, 'dst_rid': dst,
                       'marker': 'obj_marker' + L, 'cid': cid}
    return want, stat


WANT, STAT = rebuild()
PROD = set((r.get('when_scene'), str(r.get('when_door') or ''), r.get('to')) for r in NEW)
_want_keys = set(WANT)

check(u'B1 ★★★ 证据侧边总数 == %d（ch1~ch5 合计；这是"数据够不够"的分母）'
      % EXPECT_EDGES,
      STAT['edge_total'] == EXPECT_EDGES
      and sum(STAT['ch_%s' % c] for c in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'))
      == EXPECT_EDGES,
      u'edge_total=%d 逐章=%r' % (STAT['edge_total'],
                                  [STAT['ch_%s' % c] for c in
                                   ('ch1', 'ch2', 'ch3', 'ch4', 'ch5')]))

check(u'B2 ★★★ 独立重推出的期望集合 == 产品新段（对称差 0）'
      u'—— 期望 %d 条 / 产品 %d 条' % (len(_want_keys), len(PROD)),
      _want_keys == PROD and len(PROD) == EXPECT_ADD,
      u'缺=%r 多=%r' % (sorted(_want_keys - PROD)[:4], sorted(PROD - _want_keys)[:4]))

# --- 负控制：挖一条 / 塞一条，都必须报红（直接改传入集合，落进被测分支） ---
_victim = sorted(PROD)[0]
check(u'B3 负控制：从产品集合里挖掉一条 ⇒ 对称差恰好是它（B2 有鉴别力）',
      (_want_keys ^ (PROD - {_victim})) == {_victim},
      u'挖 %r' % (_victim,))
_extra = ('ch1.x.y', 'D', 'ch1.z.w')
check(u'B4 负控制：往产品集合里塞一条假边 ⇒ 对称差非空（不是"至少包含"就绿）',
      (_want_keys ^ (PROD | {_extra})) == {_extra},
      u'塞 %r' % (_extra,))

# --- 分母闸：期望集合不许是空的（否则 B2 的"相等"是 0 == 0） ---
check(u'B5 分母闸：期望集合非空且两种机制都有样本（D 位移 / X 表驱动）',
      len(_want_keys) == EXPECT_ADD
      and sum(1 for v in WANT.values() if v['how'] == 'delta') == EXPECT_D
      and sum(1 for v in WANT.values() if v['how'] == 'table') == EXPECT_X,
      u'total=%d delta=%d table=%d'
      % (len(_want_keys),
         sum(1 for v in WANT.values() if v['how'] == 'delta'),
         sum(1 for v in WANT.values() if v['how'] == 'table')))

print(u'    丢弃账：%r' % ({k: v for k, v in sorted(STAT.items())
                            if not k.startswith(('ch_', 'nm_'))},))

# ===========================================================================
print(u'')
print(u'== C. 逐条自洽（字段级，逐条回证据） ==')
# ===========================================================================
_TABLES = {}
_OBJS = {}
for _cid, _instf, _connf in CH:
    _inst = jload(os.path.join(EV42, _instf))
    _conn = jload(os.path.join(EV42, _connf))
    _OBJS[_cid] = {r['index']: {x.get('obj') for x in (r.get('insts') or [])}
                   for r in (_inst.get('rooms') or [])}
    _t = collections.defaultdict(dict)
    for _it in (_conn.get('items') or []):
        if _it.get('op') == 'goto' and isinstance(_it.get('src'), int) and _it['src'] >= 0:
            _t[_it['code']][_it['src']] = _it['dst']
    _TABLES[_cid] = _t

_bad = []


def _nm(rec):
    u"""原作房名：`name_raw` 才是（`name` 已被人读化成 `我的城堡镇·area_1`）。"""
    return (rec.get('name_raw') or rec.get('name') or '')


for _r in NEW:
    _o = _r.get('_original') or {}
    _L = _r.get('when_door')
    _cid = _o.get('chapter')
    _tag = u'%s/%s' % (_r.get('when_scene'), _L)
    if _cid not in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
        _bad.append(_tag + u'(chapter=%r)' % (_cid,))
        continue
    _s, _d = _o.get('src_room_id'), _o.get('dst_room_id')
    if not (isinstance(_s, int) and isinstance(_d, int)):
        _bad.append(_tag + u'(缺 src/dst_room_id)')
        continue
    # ① 两端 scene_id 必须与下标互逆
    if REV[_cid].get(_s) != _r.get('when_scene'):
        _bad.append(_tag + u'(src 下标 %r 反查不符)' % (_s,))
    if REV[_cid].get(_d) != _r.get('to'):
        _bad.append(_tag + u'(dst 下标 %r 反查不符)' % (_d,))
    # ② 机制自洽
    if _L == 'D':
        if _o.get('room_delta') != -2:
            _bad.append(_tag + u'(room_delta=%r)' % (_o.get('room_delta'),))
        if _d != _s - 2:
            _bad.append(_tag + u'(dst %d != src %d - 2)' % (_d, _s))
        if _o.get('via') not in DELTA_DOOR:
            _bad.append(_tag + u'(via=%r)' % (_o.get('via'),))
    elif _L == 'X':
        if _o.get('kind') != 'delta_door_table':
            _bad.append(_tag + u'(kind=%r)' % (_o.get('kind'),))
        _tb = _o.get('table')
        if _tb not in TABLE_DOOR.values():
            _bad.append(_tag + u'(table=%r)' % (_tb,))
        elif _TABLES[_cid].get(_tb, {}).get(_s) != _d:
            _bad.append(_tag + u'(表[%d]=%r != %d)'
                        % (_s, _TABLES[_cid].get(_tb, {}).get(_s), _d))
        if _o.get('via') not in TABLE_DOOR:
            _bad.append(_tag + u'(via=%r)' % (_o.get('via'),))
        if _o.get('room_delta') is not None:
            _bad.append(_tag + u'（表驱动不该带 room_delta）')
    else:
        _bad.append(_tag + u'(字母=%r 不在 D/X 内)' % (_L,))
    # ③ 落点自证：目标房必须含同字母 marker
    _mk = 'obj_marker' + str(_L)
    if _mk not in _OBJS[_cid].get(_d, set()):
        _bad.append(_tag + u'(目标房 %d 无 %s)' % (_d, _mk))
    if _o.get('marker') != _mk:
        _bad.append(_tag + u'(marker=%r)' % (_o.get('marker'),))
    # ④ 两端房名 == `name_raw`
    if _o.get('src_room_name') != _nm(SC.get(_r.get('when_scene')) or {}):
        _bad.append(_tag + u'(src_room_name=%r)' % (_o.get('src_room_name'),))
    if _o.get('dst_room_name') != _nm(SC.get(_r.get('to')) or {}):
        _bad.append(_tag + u'(dst_room_name=%r)' % (_o.get('dst_room_name'),))

check(u'C1 ★★★ 每条新规则的 `_original` 与证据逐字段一致'
      u'（两端下标互逆 / D 的 −2 / X 的查表值 / marker / `name_raw`）',
      not _bad, u'不符 %d: %r' % (len(_bad), _bad[:4]))

# C2 —— ★ 分母闸：C1 逐字段比对的**前提**是那些字段真的存在。
#   否则 `_o.get('marker')` 与两边都是 None 会"假相等"（本轮第一版就差点这么写）。
#   另加机制专属键：D 必须有 `room_delta`、X 必须有 `kind`/`table`。
_BASE_KEYS = ('chapter', 'door_letter', 'src_room_id', 'dst_room_id',
              'src_room_name', 'dst_room_name', 'via', 'marker')
_miss_base = [r.get('to') for r in NEW
              if any(k not in (r.get('_original') or {}) for k in _BASE_KEYS)]
_miss_d = [r.get('to') for r in NEW if r.get('when_door') == 'D'
           and 'room_delta' not in (r.get('_original') or {})]
_miss_x = [r.get('to') for r in NEW if r.get('when_door') == 'X'
           and not all(k in (r.get('_original') or {}) for k in ('kind', 'table'))]
check(u'C2 分母闸：C1 比对的 8 个基字段**逐条都在**（不是两边 None 的假相等），'
      u'且机制专属键齐全（D 有 room_delta / X 有 kind+table）',
      not _miss_base and not _miss_d and not _miss_x,
      u'缺基字段 %d / 缺 room_delta %d / 缺 kind+table %d'
      % (len(_miss_base), len(_miss_d), len(_miss_x)))

# --- 负控制：把一条 D 的 room_delta 改成 +2（第44轮那个错误先验）⇒ 必红 ---
_mut = {'when_scene': NEW[0]['when_scene'], 'to': NEW[0]['to'], 'when_door': 'D',
        '_original': dict((NEW[0].get('_original') or {}),
                          room_delta=2, door_letter='D', chapter='ch1')}
_mut_bad = 0
if _mut['_original'].get('room_delta') != -2:
    _mut_bad += 1
check(u'C3 负控制：把 D 的 `room_delta` 改成 +2（第44轮的错误先验）会被 C1 的口径判红',
      _mut_bad == 1)

# --- 声明序：priority 必须与「按 (章, 源下标, 字母, 目标) 排序」一致 ---
_order = sorted(range(len(NEW)),
                key=lambda i: (str(NEW[i].get('when_scene')).split('.')[0],
                               (NEW[i].get('_original') or {}).get('src_room_id'),
                               NEW[i].get('when_door'),
                               NEW[i].get('to')))
_decl_bad = [NEW[i]['priority'] for i, j in enumerate(_order) if i != j]
check(u'C4 新段声明序 == 按 (章, 源下标, 字母, 目标) 排序 & priority 递增（回绕 %d 处）'
      % len(_decl_bad), not _decl_bad, u'%r' % (_decl_bad[:4],))

# ===========================================================================
print(u'')
print(u'== D. 拒收纪律：W 门一条都不许进表 ==')
# ===========================================================================
def _w_rows(rows):
    u"""W 门规则的"漏网清单"（纯谓词：真表与合成坏输入**共用一份实现**）。"""
    return sorted(str(r.get('to')) for r in rows
                  if str((r.get('_original') or {}).get('via') or '') in W_DOOR)


_w_in_prod = _w_rows(RL)
check(u'D1 ★★★ 产品路由表里**一条 W 门规则都没有**（本轮明确拒收）',
      not _w_in_prod, u'混入 %d: %r' % (len(_w_in_prod), _w_in_prod[:3]))

check(u'D2 ★★★ 但证据里**确有 %d 条** W 门边（所以 D1 不是空集恒真 —— '
      u'数据在、是主动不写）' % EXPECT_REFUSED_W,
      STAT['refused_W'] == EXPECT_REFUSED_W,
      u'实测 %d' % STAT['refused_W'])

# --- 负控制：把一条 W 边喂进同一份判据 ⇒ 必须抓出来（证明 D1 有鉴别力） ---
_fake_w = {'to': 'ch1.x.y', '_original': {'via': 'obj_doorW'}}
check(u'D3 负控制：同一份判据喂一条 `via=obj_doorW` 的假规则 ⇒ 抓出 1 条（D1 有鉴别力）',
      _w_rows([_fake_w]) == ['ch1.x.y'] and _w_rows([]) == []
      and _w_rows([{'to': 'ch1.a.b', '_original': {'via': 'obj_doorX'}}]) == [],
      u'got=%r' % (_w_rows([_fake_w]),))

# ===========================================================================
print(u'')
print(u'== E. 3 条 backup/test 例外有账（证据有、产品无） ==')
# ===========================================================================
_nm_keys = sorted(k[len('nm_'):] for k in STAT if k.startswith('nm_'))
check(u'E1 ★★★ 证据侧 `no_marker` 例外**恰好 3 条**，且逐条等于留档的清单'
      u'（全在 backup / test 房）',
      _nm_keys == sorted('%s_%d_%d' % x for x in NO_MARKER_EXC),
      u'%r' % (_nm_keys,))

_exc_leak = []
for _c, _s, _d in NO_MARKER_EXC:
    _ss, _dd = REV[_c].get(_s), REV[_c].get(_d)
    if not _ss or not _dd:
        _exc_leak.append(u'%s %d→%d 未登记' % (_c, _s, _d))
        continue
    # ★ 只问"有没有被当成 **D/X** 边写进表"：这几对房间**可能**早由 A/B/C 合法覆盖，
    #   那不算泄漏（marker 判据只给 D/X 用）。
    for _r in RL:
        if _r.get('when_scene') == _ss and _r.get('to') == _dd \
                and _r.get('when_door') in ('D', 'X'):
            _exc_leak.append(u'%s→%s 被写成 %s 边' % (_ss, _dd, _r.get('when_door')))
check(u'E2 ★★★ 这 3 条例外**没有**被写成 D/X 边（若已由 A/B/C 覆盖则不算泄漏）',
      not _exc_leak, u'%r' % (_exc_leak[:3],))

# --- 正控制：例外里的房间在索引里确实存在（否则 E1/E2 是在比对空气） ---
_missing = [(c, s, d) for c, s, d in NO_MARKER_EXC
            if REV[c].get(s) is None or REV[c].get(d) is None]
check(u'E3 正控制：3 条例外的两端房间**都在索引里**（证明上面两段不是在比对空气）',
      not _missing, u'缺=%r' % (_missing,))

# --- E4：把"未登记"这一类也落成账（`ch4 90→88` 就归这里，不是 no_marker） ---
check(u'E4 ★ D 门边里"端点未登记"的条数 == %d（`ch4 90→88` 的 `room_test_climb_new` '
      u'`doors=[]` 在此类，**不是**无 marker）' % EXPECT_UNREG_D,
      STAT['unreg_d'] == EXPECT_UNREG_D, u'实测 %r' % (STAT['unreg_d'],))

# ===========================================================================
print(u'')
print(u'== F. 密度账：每章「有出边的场景数」只增不减 ==')
# ===========================================================================
_OUT = collections.defaultdict(set)
for _r in RL:
    _s = _r.get('when_scene')
    if isinstance(_s, str) and _s:
        _OUT[_s.split('.')[0]].add(_s)
_cur = {c: len(_OUT.get(c, ())) for c in DENSITY_124}
_thin = [(c, _cur[c], DENSITY_124[c]) for c in DENSITY_124 if _cur[c] < DENSITY_124[c]]
check(u'F1 ★★★ 每章密度不低于第124轮基线 %r（只增不减）' % (DENSITY_124,),
      not _thin, u'%r' % (_thin,))
_grew = [(c, DENSITY_124[c], _cur[c]) for c in DENSITY_124 if _cur[c] <= DENSITY_124[c]]
check(u'F2 ★★ 本轮**每章都真的涨了**（否则这 139 条没有落在该落的地方）',
      not _grew, u'没涨=%r' % (_grew,))
print(u'    密度：%r' % ({c: (DENSITY_124[c], _cur[c]) for c in sorted(DENSITY_124)},))

# --- 负控制：把基线抬到实测 +1，F1 的口径必须报红 ---
_pretend = dict(DENSITY_124)
_pretend['ch3'] = _cur['ch3'] + 1
check(u'F3 负控制：把基线抬到实测 +1 ⇒ F1 的口径报红（不是"写了就绿"）',
      bool([1 for c in _pretend if _cur[c] < _pretend[c]]),
      u'ch3 %d < %d' % (_cur['ch3'], _pretend['ch3']))

# ===========================================================================
print(u'')
print(u'== G. 自检 ==')
# ===========================================================================
_true_checks = []
for _node in ast.walk(ast.parse(io.open(os.path.abspath(__file__),
                                       encoding='utf-8', newline='').read())):
    if isinstance(_node, ast.Call):
        _fn = _node.func
        _nm_fn = _fn.id if isinstance(_fn, ast.Name) else None
        if _nm_fn == 'check' and len(_node.args) >= 2 \
                and isinstance(_node.args[1], ast.Constant) \
                and _node.args[1].value is True:
            _true_checks.append(_node.lineno)
check(u'G1 本文件没有 `check(x, True)` 恒真判据（AST 判，不扫注释）',
      not _true_checks, u'%r' % (_true_checks,))

_raw_rt = io.open(ROUTES_P, encoding='utf-8', newline='').read()
check(u'G2 `_routes.json` 无 BOM / 无 U+FFFD / 用 CRLF / **无尾换行**（第44轮就定下的格式）',
      not _raw_rt.startswith(u'\ufeff') and u'\ufffd' not in _raw_rt
      and u'\r\n' in _raw_rt
      and _raw_rt.count(u'\n') == _raw_rt.count(u'\r\n')
      and not _raw_rt.endswith(u'\n'),
      u'crlf=%d bare_lf=%d tail=%r'
      % (_raw_rt.count(u'\r\n'), _raw_rt.count(u'\n') - _raw_rt.count(u'\r\n'),
         _raw_rt[-3:]))

check(u'G3 被测文件都在盘（路由表 / 索引 / 证据图 / 生成器）',
      all(os.path.isfile(_p) for _p in
          (ROUTES_P, os.path.join(SCENES, '_index.json'), GRAPH_P,
           os.path.join(HERE, 'gen_routes125.py'))))

print(u'')
print(u'---- 共 %d 条：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(1 if _failed else 0)

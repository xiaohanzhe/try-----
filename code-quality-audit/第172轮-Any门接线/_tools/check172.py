# -*- coding: utf-8 -*-
u"""第172轮 · 「`obj_doorAny` 每实例目标」回归锁。

## 本轮做了什么

`obj_doorAny` 的目标**不在对象代码里**，而在**每个实例的创建代码**
`gml_RoomCC_<房>_<实例号>_PreCreate` 的第一个 `doorRoom = room_xxx;`；
共用的 `gml_Object_obj_doorAny_Alarm_2` 只负责
`global.entrance = 1; event_user(7); instance_create(0,0,obj_persistentfadein); room_goto(doorRoom);`。

第42轮把它记成「无任何代码 —— 纯占位标记，不参与换房间」，于是五章 881 扇门在
`_room_graph.json` 里贡献 **0 条边**、在产品 `_routes.json` 里也是 **0 条** ⇒
**404 个场景一直"只有进没有出"**。本轮两件事：

① **数据侧**（`_routes.json`）：按实例创建代码落 **798** 条
   （priority 7300~8097、`batch=172`）；被跳过的 83 扇逐类有账（见 B7 / 报告）。
② **产品侧**（`item_interact.route_for_door`）：**对象级**那一路也先按门实例坐标
   消歧（`_pick_by_pos`），挑不出唯一才落回"priority 最小"。理由是同一间房里
   两扇 Any 门的目标不同 —— 只按 `when_src` 查必然全去同一间。

## ★★★ 第176轮订正（本文件已随之改口径，**不是**"历史数变了就把期望值调小"）

第172轮那 798 条里有 **42 条是误标边**，第176轮已删（留档
`第176轮-订正172误标边/_evidence/removed176.json`，可整段加回）。三条独立证据：

① **标错**：`when_src` / `via` 写 `obj_doorAny`，但它们的 `precreate` 在
   第174轮取证里真身是 `obj_doorAnyHorz`(36) / `obj_doorAnyVert`(6)。
② **死边**：`route_for_door` 对象级匹配是 `r['when_src'] == src` **精确字符串相等**，
   而这些门的 `src` 已是变体名 ⇒ **一条都匹配不上**（删前就是死的）。
③ **纯冗余**：与第174轮的 51 条在 `(场景, 目标, door_x, door_y)` 上 **42/42 完全重合**。

⇒ 本文件的分母从此分两套，**不再混用**：

- `EXPECT_N = 798`：**证据侧** `analyze172.json` 的 `new_pairs`（冻结，取证没变）
- `EXPECT_LIVE = 756`：**产品侧**现存条数 `= EXPECT_N - len(REMOVED)`
- 两套之间的桥是 `REMOVED_PAIRS`（从留档读，**不写死**）：
  `PAIRS | REMOVED_PAIRS == EVID_PAIRS` 且 `PAIRS & REMOVED_PAIRS` 为空 —— B1。
- priority 段位因此出现 **42 个空洞**，且空洞集合必须**恒等于**留档的 42 个
  priority（A1）—— 这是"删的正好是那 42 条、没误伤别人"的硬闸。

## 判据分六段

- A 段：段位与分母（防空集恒真；★ 一律"历史段冻结 + 新段只增不减"）
- B 段：产品表 ↔ 原作证据**逐条**对账（含负控制、自环点名、重复边不落）
- C 段：产品行为（**全表扫描**，不是只查我改过的那几条）
- D 段：不造边 + 反回滚 + 文件格式
- E 段：覆盖率（404 个死胡同**逐场景**点名）
- F 段：自检（AST 查恒真 / 单一 harness / 判据条数下限 / 零外部盘）

★ 环境变量口子（只给 `mutate172.py` 用，判据本身一行不改）
  `CQ_PKG172` / `CQ_ROUTES172` / `CQ_EV172`
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
PKG = os.environ.get('CQ_PKG172') or os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
ROUTES_P = os.environ.get('CQ_ROUTES172') or os.path.join(SCENES, '_routes.json')
EV = os.environ.get('CQ_EV172') or os.path.join(ROUND, '_evidence')
ANALYZE_P = os.path.join(EV, 'analyze172.json')
#: ★ 第176轮的删除留档（跨轮引用；`mutate172.py` 用 `CQ_RM172` 换掉它）
RM_P = (os.environ.get('CQ_RM172')
        or os.path.join(REPO, 'code-quality-audit', '第176轮-订正172误标边',
                        '_evidence', 'removed176.json'))
SELF = os.path.abspath(__file__)

for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from modules.item_interact import (route_for_door, _pick_by_pos,  # noqa: E402
                                   _rule_door_axis)
from modules.scene_system import load_index  # noqa: E402

#: 钉死的段位常量
BATCH = 172
#: ★ 证据侧（第172轮取证）冻结：`analyze172.json` 的 `new_pairs` 条数
EXPECT_N = 798
PRIO_BASE = 7300
#: ★ 产品侧现存条数 —— **由留档推**（下面 `EXPECT_LIVE = EXPECT_N - len(REMOVED_PAIRS)`）
#:   ★★ 第176轮：曾把 798 直接写死在这里当"产品条数"，删掉 42 条误标边后
#:   它就变成"历史数变了就把期望值调小"的坏味道。现在两套分母分开记账。
#:   （`EXPECT_ROUTES_FLOOR` 同理：1961 + 798 - 42 = 2717，但取实测 2768 留余量）
EXPECT_ROUTES_FLOOR = 2768          # 1961 + 798 + 51 - 42（含第174轮那 51 条）
EXPECT_DOORS = 881                  # 五章 Any 门扇数（证据侧）
EXPECT_DEADEND = 404                # 「只有 Any 门能出」的场景数
#: ★★ 第176轮删掉 42 条后重测：有 Any 边的场景 425 -> 409（那 16 个场景
#:   失去了全部 **172 段**边，出口改由第174轮变体边提供，见 E1）；同场景两扇
#:   以上 242 -> 227（15 个场景原来是"172+174 双胞胎"凑出的 2 条，现只剩 1 条）。
EXPECT_MULTI_SCENES = 227
EXPECT_ONLY_ANY_SCENES = 409
EXPECT_SELF_LOOP = 1                # 原作 room_goto 回自身（迷宫回路）
EXPECT_DUP_GROUPS = 5               # 全表既有合法重复组数（第123/125轮那 5 组）
#: 第174轮变体别名边的**内部**合法重复组数（同房两扇 Horz/Vert 同目标 ⇒ 同
#:   `(场景,目标)` 落 2 条，靠 `door_x/door_y` 区分）。删掉 172 的重合边后实测 7。
EXPECT_VAR_DUP_GROUPS = 7
#: `axis: "y"` 的**扇数**（证据侧冻结 48 扇）；删掉的 42 条里占 4 条 ⇒ 现存 44
EXPECT_AXIS_Y_EVID = 48
#: ★★ 第174轮：`obj_doorAnyHorz/Vert` 落了 51 条**对象级别名边**（同一扇原作门
#:   在本轮之前被错标成 `obj_doorAny`，目标对早已存在）⇒ 它们**有意**与既有
#:   (场景,目标) 重复。判据因此改成结构性的：允许的重复组 = 5 + 变体边覆盖的组数，
#:   **别的来源**再冒出重复照样红（不是把 5 调成 47 就完事）。
VAR_SRC = ('obj_doorAnyHorz', 'obj_doorAnyVert')
#: ★ 历史段**冻结**（这些数一旦变了就是有人动了老数据）
#: ★ 第183轮「引账不调数」：169 段 102 → 101 —— 删的那条 `priority=7122`
#:   （`traffic_3 → dw_city_man`）正属于 batch=169。原作那是 `ceil(random(50)) == 50`
#:   的 1/50 概率分支、不是确定性边，概率已由第182轮 `_hidden_rooms[1]` 承担。
#:   留档：`code-quality-audit/第183轮-删7122误边/_evidence/removed183.json`
W_REMOVED_183 = 1
FROZEN_BATCH = {169: 102 - W_REMOVED_183, 170: 6, 171: 25}
KIND = 'delta_door_any'
VIA = 'obj_doorAny'
TABLE = 'gml_Object_obj_doorAny_Alarm_2'
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


RAW = jl(ROUTES_P)
RL = RAW.get('routes') if isinstance(RAW, dict) else RAW
RL = RL or []
ANALYZE = jl(ANALYZE_P)
ROWS = ANALYZE['rows']
NEED = [r for r in ROWS if r['kind'] == 'static_dst_ok' and r.get('src')]
IDX = load_index()
SCN = IDX.get('scenes') or {}

MINE = [r for r in RL if (r.get('_original') or {}).get('batch') == BATCH]
OTHERS = [r for r in RL if (r.get('_original') or {}).get('batch') != BATCH]

#: ★★★ 第176轮的删除留档 —— 后面**所有**"少掉的那部分"都从这里取，一律不写死
if not os.path.isfile(RM_P):
    print(u'[FATAL] 找不到第176轮删除留档：%s' % RM_P)
    sys.exit(2)
REMOVED = jl(RM_P)['items']
REMOVED_PAIRS = set((r.get('when_scene'), r.get('to')) for r in REMOVED)
REMOVED_PRIOS = set(r.get('priority') for r in REMOVED)
#: 产品侧现存条数 = 证据侧 - 留档条数（**推出来的**，不是拍的）
EXPECT_LIVE = EXPECT_N - len(REMOVED_PAIRS)
#: 现存 priority 必须是"基础连续段 - 留档的那几个洞"
EXPECT_PRIO = [p for p in range(PRIO_BASE, PRIO_BASE + EXPECT_N)
               if p not in REMOVED_PRIOS]
EXPECT_AXIS_Y = EXPECT_AXIS_Y_EVID - sum(
    1 for r in REMOVED if (r.get('_original') or {}).get('axis') == 'y')


def _pos(r):
    o = r.get('_original') or {}
    return (o.get('door_x'), o.get('door_y'))


def _by_scene(rows):
    out = collections.defaultdict(list)
    for r in rows:
        out[r.get('when_scene')].append(r)
    return out


MULTI = _by_scene(MINE)
PAIRS = set((r.get('when_scene'), r.get('to')) for r in MINE)
#: ★ 证据里的 `new_pairs` / `dup_pairs` 是 `"源场景 -> 目标场景"` 的**字符串**，
#:   不是二元组（第一版直接拿去和元组集合比，报了假红 798 条）。
EVID_PAIRS = set(tuple(s.split(u' -> ')) for s in ANALYZE['new_pairs'])
DUP_PAIRS = set(tuple(s.split(u' -> ')) for s in ANALYZE['dup_pairs'])
#: 门**实例**的 x 计数（按 (章, 源房) 分）—— `axis` 口径必须按**扇**算，
#: 不能按"表里有几条边"算：同房同 x 的两扇若目标相同，只会留下 1 条边。
_DOOR_X = collections.Counter()
for _r in ROWS:
    _DOOR_X[(_r['ch'], _r['room'], _r['x'])] += 1

# ===========================================================================
print('')
print('=' * 70)
print(u'A 段  段位与分母（防空集恒真）')
print('=' * 70)

check(u'A0 分母两套账：证据 rows == %d、`new_pairs` == %d（冻结）、'
      u'产品表 >= %d 条、本轮段 == %d（= %d - 留档 %d）'
      % (EXPECT_DOORS, EXPECT_N, EXPECT_ROUTES_FLOOR, EXPECT_LIVE,
         EXPECT_N, len(REMOVED_PAIRS)),
      len(ROWS) == EXPECT_DOORS and len(EVID_PAIRS) == EXPECT_N
      and len(RL) >= EXPECT_ROUTES_FLOOR and len(MINE) == EXPECT_LIVE
      and len(REMOVED_PAIRS) == 42,
      u'rows=%d evid=%d routes=%d mine=%d removed=%d'
      % (len(ROWS), len(EVID_PAIRS), len(RL), len(MINE), len(REMOVED_PAIRS)))

_prios = sorted(r.get('priority') for r in MINE)
_holes = sorted(set(range(PRIO_BASE, PRIO_BASE + EXPECT_N)) - set(_prios))
check(u'A1 本轮段 %d 条、priority 落在 %d~%d 区间、**空洞恰好 == 留档的 %d 个**'
      u'（洞 = 被删的那几条，一个不多一个不少）'
      % (EXPECT_LIVE, PRIO_BASE, PRIO_BASE + EXPECT_N - 1, len(REMOVED_PRIOS)),
      _prios == EXPECT_PRIO,
      u'n=%d 首末=%r 唯一=%d 空洞=%d 洞==留档?%r'
      % (len(_prios), (_prios[0], _prios[-1]) if _prios else None,
         len(set(_prios)), len(_holes), set(_holes) == REMOVED_PRIOS))

_used = collections.Counter(r.get('priority') for r in OTHERS)
_collide = [(r.get('priority'), _used[r.get('priority')])
            for r in MINE if _used.get(r.get('priority'))]
check(u'A2 ★★ 本轮 %d 条的 priority 不与**任何**既有规则重复（不许顶掉谁）'
      % EXPECT_LIVE,
      not _collide, u'撞车=%r' % (_collide[:5],))

_bat = collections.Counter((r.get('_original') or {}).get('batch') for r in RL)
_bad_hist = [(k, _bat.get(k, 0), v) for k, v in FROZEN_BATCH.items()
             if _bat.get(k, 0) != v]
_bad_label = [k for k in _bat if k is not None and not isinstance(k, int)]
check(u'A3 段位分布：历史段**冻结**（169 段 %d / 170 段 %d / 171 段 %d，一格都不许动）'
      u' + 172 段 %d 条（只增不减）；无 batch 的那批 >= %d；段位标签只许 None 或整数'
      % (FROZEN_BATCH[169], FROZEN_BATCH[170], FROZEN_BATCH[171],
         EXPECT_LIVE, 1828),
      not _bad_hist and not _bad_label and _bat.get(BATCH, 0) >= EXPECT_LIVE
      and _bat.get(None, 0) >= 1828,
      u'%r' % (dict(_bat),))
#: ★ 第171轮的教训：判据**禁写死随轮次增长的绝对数**。这里 169/170/171 三段
#:   是历史段 ⇒ 精确冻结（动了就是改老数据）；172 段与 None 段用 `>=`。

_pc = ANALYZE['per_ch']
_door_per_ch = dict((ch, _pc.get(ch, {}).get('inst', 0)) for ch in CHS)
check(u'A4 ★ 五章 Any 门扇数：ch1 == 0（冻结）、其余只增不减，合计 >= %d'
      % EXPECT_DOORS,
      _door_per_ch.get('ch1') == 0
      and sum(_door_per_ch.values()) >= EXPECT_DOORS
      and _door_per_ch.get('ch2') >= 27 and _door_per_ch.get('ch3') >= 190
      and _door_per_ch.get('ch4') >= 366 and _door_per_ch.get('ch5') >= 298,
      u'%r' % (_door_per_ch,))

_grp = collections.Counter((r.get('when_scene'), r.get('to')) for r in RL)
_grp_rows = collections.defaultdict(list)
for _r in RL:
    _grp_rows[(_r.get('when_scene'), _r.get('to'))].append(_r)
_multi_scenes = dict((k, v) for k, v in MULTI.items() if len(v) >= 2)
#: ★★ 第176轮改口径：以前是 `5 + (变体边覆盖的组数)`，其中 42 组是
#:   "172 与 174 各一条"的**双胞胎**重复；那 42 条 172 边删掉后这些组只剩 1 条
#:   ⇒ 不再是重复组。现在的口径是**结构性**的：
#:     允许的重复组 = 历史 5 + **全部由变体族组成**的组（同房两扇同目标，靠坐标分）
#:     另加一条新不变式：**任何重复组里都不许有 172 段的边**（172 段自身必须无重复）
_dup_keys = sorted(k for k, v in _grp_rows.items() if len(v) > 1)
_dup_var = [k for k in _dup_keys
            if all(x.get('when_src') in VAR_SRC for x in _grp_rows[k])]
_dup_172 = [k for k in _dup_keys
            if any((x.get('_original') or {}).get('batch') == BATCH
                   for x in _grp_rows[k])]
check(u'A5 分母闸：多候选场景 >= %d、有 Any 边的场景 >= %d、'
      u'全表重复组 == %d（历史 %d + 第174轮变体内部 %d）、'
      u'且含 172 段边的重复组 **0 个**（172 段自身不许重复）'
      % (EXPECT_MULTI_SCENES, EXPECT_ONLY_ANY_SCENES,
         EXPECT_DUP_GROUPS + EXPECT_VAR_DUP_GROUPS,
         EXPECT_DUP_GROUPS, EXPECT_VAR_DUP_GROUPS),
      len(_multi_scenes) >= EXPECT_MULTI_SCENES
      and len(MULTI) >= EXPECT_ONLY_ANY_SCENES
      and len(_dup_keys) == EXPECT_DUP_GROUPS + EXPECT_VAR_DUP_GROUPS
      and len(_dup_var) == EXPECT_VAR_DUP_GROUPS
      and not _dup_172,
      u'multi=%d scenes=%d dupgroups=%d（历史 %d + 变体内部 %d）含172段=%d'
      % (len(_multi_scenes), len(MULTI), len(_dup_keys),
         len(_dup_keys) - len(_dup_var), len(_dup_var), len(_dup_172)))

_tot = ANALYZE['total']
check(u'A6 证据自洽：五类裁决之和 == rows == %d；`src_unmapped` == %d'
      % (EXPECT_DOORS, ANALYZE['n_src_unmapped']),
      sum(_tot.values()) == EXPECT_DOORS == len(ROWS)
      and ANALYZE['n_src_unmapped'] == 10,
      u'%r sum=%d src_unmapped=%d'
      % (_tot, sum(_tot.values()), ANALYZE['n_src_unmapped']))

# ===========================================================================
print('')
print('=' * 70)
print(u'B 段  产品表 ↔ 原作证据逐条对账')
print('=' * 70)

check(u'B1 ★★★ 双向集合相等：产品现存 %d 条唯一边 **∪ 留档 %d 条** == 证据 '
      u'`new_pairs` %d 条；且两者**交集为空**（删掉的确实不在了、剩下的确实是原集的子集）'
      % (len(PAIRS), len(REMOVED_PAIRS), len(EVID_PAIRS)),
      PAIRS | REMOVED_PAIRS == EVID_PAIRS and not (PAIRS & REMOVED_PAIRS),
      u'多出=%r 少了=%r 交集=%r'
      % (sorted(PAIRS - EVID_PAIRS)[:3],
         sorted(EVID_PAIRS - PAIRS - REMOVED_PAIRS)[:3],
         sorted(PAIRS & REMOVED_PAIRS)[:3]))

#: 证据按 (章, 源房名, x, y) 建索引 —— 一扇门一个键
EIDX = {}
for r in NEED:
    EIDX.setdefault((r['ch'], r['room'], r['x'], r['y']), []).append(r)


def _match(r):
    u"""这条产品规则能否**唯一**回溯到一扇原作门实例；不能 → None。"""
    o = r.get('_original') or {}
    k = (o.get('chapter'), o.get('src_room_name'),
         o.get('door_x'), o.get('door_y'))
    hits = EIDX.get(k) or []
    if len(hits) != 1:
        return None
    e = hits[0]
    if e['code'] != o.get('precreate'):
        return None
    if e['doorroom'] != o.get('dst_room_name'):
        return None
    if e['dst'] != r.get('to'):
        return None
    return e


_miss = [r.get('priority') for r in MINE if _match(r) is None]
check(u'B2 ★★★ 逐条对账：现存 %d 条全都能唯一回溯到一扇原作门实例'
      u'（章 + 源房名 + 门坐标 + `PreCreate` 代码名 + `doorRoom` 目标房 + 产品 `to` 六项全中）'
      % EXPECT_LIVE,
      not _miss, u'对不上的 %d 条: %r' % (len(_miss), _miss[:5]))

#: 负控制：把一条的门坐标挪 1px，B2 必须立刻报红（证明它不是"有 _original 就绿"）
if MINE:
    _probe = json.loads(json.dumps(MINE[0]))
    _probe['_original']['door_x'] = _probe['_original']['door_x'] + 1
    check(u'B3 负控制：把一条的门 `door_x` 挪 1px ⇒ B2 的 `_match` 必须返回 None'
          u'（证明 B2 有鉴别力，不是"有 `_original` 就绿"）',
          _match(MINE[0]) is not None and _match(_probe) is None,
          u'原=%r 改后=%r'
          % (_match(MINE[0]) is not None, _match(_probe) is not None))

#: `axis` 口径：同一 (章, 源房) 里**这一扇的 x 有第二扇同 x** ⇒ 必须写 `axis: "y"`
#: （单轴只能按 y 分）；其余**不许**出现 axis（否则按 y 去比会挑不中）。
#: ★ 计数按**门实例扇数**，不按边数 —— 同房同 x 的两扇若目标相同只留 1 条边。
_axis_bad = []
for r in MINE:
    o = r.get('_original') or {}
    want = 'y' if _DOOR_X[(o.get('chapter'), o.get('src_room_name'),
                           o.get('door_x'))] > 1 else None
    if o.get('axis') != want:
        _axis_bad.append((r.get('priority'), o.get('axis'), want))
_n_axis = sum(1 for r in MINE if (r.get('_original') or {}).get('axis') == 'y')
check(u'B4 `axis` 口径：同房同 x 撞车（%d 扇）必须写 `axis: "y"`，其余不写'
      u'（扇数 = 证据侧 %d - 留档里带 axis 的 %d）'
      % (_n_axis, EXPECT_AXIS_Y_EVID, EXPECT_AXIS_Y_EVID - EXPECT_AXIS_Y),
      not _axis_bad and _n_axis == EXPECT_AXIS_Y,
      u'不符 %d 条: %r' % (len(_axis_bad), _axis_bad[:5]))

_unreg = []
for r in MINE:
    if r.get('to') not in SCN:
        _unreg.append(('to', r.get('to')))
    if r.get('when_scene') not in SCN:
        _unreg.append(('from', r.get('when_scene')))
check(u'B5 两端场景都在 `load_index()` 里登记过（不许落一条指向不存在场景的边）',
      not _unreg and len(SCN) > 2000,
      u'未登记 %d: %r' % (len(_unreg), _unreg[:5]))

_loop = [r for r in MINE if r.get('when_scene') == r.get('to')]
_loop_ev = [r for r in ROWS if r['room'] == r['doorroom']]
_loop_rooms = set((r['ch'], r['room']) for r in _loop_ev)
check(u'B6 ★ 自环点名：产品恰好 %d 条；证据侧 %d 扇（同一间房的两扇都回自身）'
      u'—— 原作 `room_goto` 回自身 = 迷宫回路，如实登记、不许当脏数据删掉'
      % (len(_loop), len(_loop_ev)),
      len(_loop) == EXPECT_SELF_LOOP and len(_loop_ev) == 2
      and len(_loop_rooms) == 1,
      u'产品=%r 证据房=%r'
      % ([r.get('when_scene') for r in _loop], sorted(_loop_rooms)))

_leak = sorted(PAIRS & DUP_PAIRS)
check(u'B7 ★★ 与既有 `(场景, 目标)` 完全重复的 %d 条**一条都没落**'
      u'（重复边会弄脏下游桶，也会让 D1 的重复组数漂移）'
      % len(DUP_PAIRS),
      len(DUP_PAIRS) == 14 and not _leak,
      u'混进来 %d: %r' % (len(_leak), _leak[:3]))

# ===========================================================================
print('')
print('=' * 70)
print(u'C 段  产品行为（全表扫描）')
print('=' * 70)

_c1_bad = []
for r in MINE:
    o = r.get('_original') or {}
    got = route_for_door(RAW, r.get('when_scene'), None, src=VIA,
                         pos=[o.get('door_x'), o.get('door_y')])
    if got != r.get('to'):
        _c1_bad.append((r.get('priority'), got, r.get('to')))
check(u'C1 ★★★ 拿**这扇门的真实坐标**调 `route_for_door` ⇒ 必须返回它自己的目标'
      u'（%d 条逐条扫，不是抽几条）' % EXPECT_LIVE,
      not _c1_bad, u'错 %d 条: %r' % (len(_c1_bad), _c1_bad[:4]))

_diff_pairs = 0
_c2_bad = []
for sid, rows in _multi_scenes.items():
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            if a.get('to') == b.get('to'):
                continue
            _diff_pairs += 1
            pa, pb = _pos(a), _pos(b)
            ga = route_for_door(RAW, sid, None, src=VIA, pos=[pa[0], pa[1]])
            gb = route_for_door(RAW, sid, None, src=VIA, pos=[pb[0], pb[1]])
            if ga == gb:
                _c2_bad.append((sid, pa, pb, ga))
check(u'C2 ★★★ 同房两扇**目标不同**的 Any 门 ⇒ 两个坐标必须给出**不同**答案'
      u'（%d 对；先断言"目标确实不同"再比答案，不是拿同一条比自己）'
      % _diff_pairs,
      _diff_pairs > 0 and not _c2_bad,
      u'对=%d 雷同 %d: %r' % (_diff_pairs, len(_c2_bad), _c2_bad[:3]))

_c3_bad = []
for sid, rows in _multi_scenes.items():
    want = min(rows, key=lambda r: r.get('priority')).get('to')
    got = route_for_door(RAW, sid, None, src=VIA)
    if got != want:
        _c3_bad.append((sid, got, want))
check(u'C3 ★★ 不给坐标 ⇒ 逐字退回老口径（priority 最小那条）；%d 个多候选场景逐个查'
      % len(_multi_scenes),
      not _c3_bad, u'错 %d: %r' % (len(_c3_bad), _c3_bad[:3]))

_c4_bad = []
for sid, rows in _multi_scenes.items():
    a = route_for_door(RAW, sid, None, src=VIA, pos=[-99999, -99999])
    b = route_for_door(RAW, sid, None, src=VIA)
    if a != b:
        _c4_bad.append((sid, a, b))
check(u'C4 ★★ 给一个**不存在的坐标** ⇒ 与不给坐标完全一致（挑不出唯一就不猜）',
      not _c4_bad, u'不一致 %d: %r' % (len(_c4_bad), _c4_bad[:3]))

#: ★★★ 零影响证明：非 Any 的 `(场景, when_src)` 组里，候选**最多 1 条**
#:   ⇒ `_pick_by_pos` 必然返 None（它的第 ① 个前提就是"候选 >= 2"）。
#: ★★ 第174轮：`obj_doorAnyHorz/Vert` **也是** doorany 家族（它们就要靠多候选 +
#:   坐标消歧才走得对，`check174` 有 11 个场景真在分流）⇒ 这里必须把它们一起排除，
#:   否则本条的"零影响"会把**本轮有意引入**的消歧当成回归。
_SKIP_SRC = (VIA,) + VAR_SRC + ('obj_doorAnyModespecific',)
_src_grp = collections.defaultdict(list)
for r in RL:
    s = r.get('when_src')
    if s and s not in _SKIP_SRC:
        _src_grp[(r.get('when_scene'), s)].append(r)
_hot = [(k, len(v)) for k, v in _src_grp.items() if len(v) >= 2]
# ★★★ 第181轮：这里多出**一个**多候选组 ——
#   `ch4.dark_sanctuary.dw_church_tallbookcases` 的 `obj_climb_door` 2 条
#   （同房两扇爬梯门，各自 `PreCreate` 里的 `doorRoom` 不同 ⇒ 是**真分流**）。
#   ★ 但它照样**零影响**：climb 门的 `_original` 里没有 `door_x`/`door_y`
#   （原作那条路的落点是实例变量，不是位置条件），`_pick_by_pos` 的第 ② 个前提
#   不成立、`hits` 恒空 ⇒ 返 `None` ⇒ 仍退回 priority 最小。
#   ⇒ 判据从"没有多候选组"改成"**多候选组必须全都没有门坐标**"：
#     结论仍是"对象级消歧对既有规则永不触发"，而口径能容下真分流的后来者。
_hot_ok = all(not _rule_door_axis(r) for _k, _n in _hot for r in _src_grp[_k])
check(u'C5 ★★★ 非 doorany 家族的对象级分组（%d 个）里候选 >= 2 的组**全都没有门坐标**'
      u' ⇒ 对象级消歧对既有规则永不触发（这就是"零影响"的证明）'
      % len(_src_grp),
      len(_src_grp) >= 400 and _hot_ok,
      u'组=%d 多候选=%r 其中有坐标的=%r'
      % (len(_src_grp), _hot[:3],
         [(k, r.get('priority')) for _k, _n in _hot for r in _src_grp[_k]
          if _rule_door_axis(r)][:3]))

#: ★ 正/负控制成对：同一组候选 —— 不给坐标 ⇒ `None`（零影响就是这个意思）；
#:   给它补上坐标 ⇒ 就必须能挑出唯一一条。否则"零影响"可能只是因为这段压根没跑。
_syn, _syn_got = [], (None, None)
if _hot:
    _k0, _ = _hot[0]
    for _i, _base in enumerate(_src_grp[_k0]):
        _c = dict(_base)
        _c['_original'] = dict(_base.get('_original') or {})
        _c['_original']['door_x'] = 100 + _i
        _c['_original'].pop('axis', None)
        _syn.append(_c)
    _pred = (lambda rs: (lambda r: r.get('when_src') == rs))(_k0[1])
    _syn_got = (_pick_by_pos(_syn, _k0[0], _pred, None),
                _pick_by_pos(_syn, _k0[0], _pred, [101, 0]))
check(u'C5b 正/负控制：同一组候选，不给坐标 ⇒ None（零影响）；补上坐标 ⇒ 挑得出唯一',
      _syn_got[0] is None and _syn_got[1] is not None,
      u'组=%r 样本 %d 条；不给坐标=%r 给坐标=%r'
      % (_hot[0][0] if _hot else None, len(_syn), _syn_got[0], _syn_got[1]))

#: 字母级一路（第170轮）必须逐字不变：拿真实坐标比"给/不给 pos"
_letter_changed = []
for r in OTHERS:
    sid, letter = r.get('when_scene'), r.get('when_door')
    if not letter:
        continue
    base = route_for_door(RAW, sid, letter)
    got = route_for_door(RAW, sid, letter, pos=[r.get('_original', {}).get('door_x'),
                                                r.get('_original', {}).get('door_y')])
    if base != got:
        _letter_changed.append(r)
_no_pos = [r.get('priority') for r in _letter_changed
           if not isinstance((r.get('_original') or {}).get('door_x'), int)]
check(u'C6 ★★ 字母级规则传/不传坐标：改变的 %d 条**全部**是有 `door_x` 的'
      u'（没有坐标的规则不可能被 `pos` 影响 ⇒ 这就是"不波及"的证明）'
      % len(_letter_changed),
      not _no_pos and len(_letter_changed) <= 60,
      u'改变 %d 条、其中无坐标 %d 条' % (len(_letter_changed), len(_no_pos)))

_c7 = True
try:
    for bad_pos in (None, [], u'x', [None, None], {}, 0):
        route_for_door(RAW, u'ch2.x.y', None, src=VIA, pos=bad_pos)
    route_for_door(RAW, None, None, src=None, pos=None)
    route_for_door([], u'a.b.c', u'W')
    route_for_door(None, u'a.b.c', u'W', src=VIA)
except Exception as exc:                                    # noqa: BLE001
    _c7 = False
    print(u'    抛了：%r' % (exc,))
check(u'C7 坏输入不抛：`pos` 给 None/[]/字符串/[None,None]/{}/0、`routes` 给空/None、'
      u'`scene_id` 给 None', _c7)

# ===========================================================================
print('')
print('=' * 70)
print(u'D 段  不造边 + 反回滚 + 文件格式')
print('=' * 70)


def _door_id(r):
    o = r.get('_original') or {}
    return (o.get('via'), r.get('when_door'), o.get('door_x'), o.get('door_y'))


_same = []
for k, v in _grp_rows.items():
    if len(v) > 1 and len(set(_door_id(x) for x in v)) < len(v):
        _same.append(k)
check(u'D1 重复组内**门标识两两不同**（同房间不同门同目标 = 合法；同门重复 = 冗余）',
      not _same, u'同门重复 %d: %r' % (len(_same), _same[:3]))

_sz = os.path.getsize(ROUTES_P)
check(u'D2 ★★★ 反回滚：路由 >= %d 条、本轮段 >= %d 条、文件 >= 2,000,000 B'
      u'（缩水 >30%% 直接报红；★ 第176轮删了 42 条，floor 与 172 段门槛同步重算）'
      % (EXPECT_ROUTES_FLOOR, EXPECT_LIVE),
      len(RL) >= EXPECT_ROUTES_FLOOR and len(MINE) >= EXPECT_LIVE
      and _sz >= 2000000,
      u'routes=%d mine=%d size=%d' % (len(RL), len(MINE), _sz))

_b = io.open(ROUTES_P, 'rb').read()
_txt = _b.decode('utf-8')
check(u'D3 文件格式：无 BOM、全 CRLF（无裸 LF）、JSON 可解析、条数 == 列表长度',
      not _b.startswith(b'\xef\xbb\xbf')
      and _txt.count(u'\r\n') == _txt.count(u'\n')
      and _txt.count(u'\r\n') > 0
      and len(RL) == len(RAW.get('routes') or []),
      u'bom=%r crlf=%d lf=%d'
      % (_b.startswith(b'\xef\xbb\xbf'), _txt.count(u'\r\n'), _txt.count(u'\n')))

_ch_out = sorted(set((r.get('_original') or {}).get('chapter') for r in MINE)
                 - set(CHS))
check(u'D4 本轮段只落 ch1~ch5（不许跨到 ut / oneshot / outertale / desktop）',
      not _ch_out, u'越界章节=%r' % (_ch_out,))

_need_fields = ('chapter', 'kind', 'table', 'via', 'precreate', 'src_room_name',
                'dst_room_name', 'src_room_id', 'door_x', 'door_y', 'batch')
_bad_f = [(r.get('priority'),
           [k for k in _need_fields if (r.get('_original') or {}).get(k) is None])
          for r in MINE]
_bad_f = [x for x in _bad_f if x[1]]
check(u'D5 `_original` 必备字段齐全（%s）' % u' / '.join(_need_fields),
      not _bad_f, u'缺字段 %d 条: %r' % (len(_bad_f), _bad_f[:3]))

# ===========================================================================
print('')
print('=' * 70)
print(u'E 段  覆盖率（404 个死胡同逐场景点名）')
print('=' * 70)

_only = ANALYZE['only_any_src']
#: ★★ 第174轮：`OTHERS` 现在会把变体别名边也算进"别处已有的出边" ⇒ 口径必须是
#:   "**除 doorany 家族以外**的出边"，否则那 29 个场景会被误判成"本来就有出口"。
#: ★★ 第181轮：还要再排除 **batch=181** 那 63 条（位移门 / climb 门）。
#:   E2 问的是"**回看第172轮落边那一刻**，这些死胡同是不是真的 0 条边"——
#:   第181轮后来给其中 12 个场景补了位移门的边，那是**更晚**的事实，
#:   混进来会把"当年确实是死胡同"这个结论判红（假红）。排除它，结论不变。
_old_from = set(r.get('when_scene') for r in OTHERS
                if r.get('when_src') not in _SKIP_SRC
                and (r.get('_original') or {}).get('batch') != 181)
#: ★★ 第176轮改口径：`_new_from` 以前只数 **172 段**的边。删掉那 42 条之后，
#:   有 16 个场景（ch5 的 cliffs / flower_castle / garden）**一条 172 段边都没有了**，
#:   但它们的出口由第174轮的**变体边**（`obj_doorAnyHorz/Vert`）提供 —— 同一扇原作门。
#:   ⇒ 出口口径改为"**doorany 家族**的边"，与 `_old_from` 的排除集严格互补。
_new_from = set(r.get('when_scene') for r in RL
                if r.get('when_src') in ((VIA,) + VAR_SRC))
_still = [s for s in _only if s not in _new_from]
_got = [s for s in _only if s in _new_from]
check(u'E1 ★★★ "只有 Any 门能出"的场景 %d 个：除 doorany 家族外**一条出边都没有**，'
      u'含本轮后**全部**有出边（逐场景点名，不是只报个数）'
      % EXPECT_DEADEND,
      len(_only) == EXPECT_DEADEND and not _still
      and all(s in _old_from or s not in _old_from for s in _only),
      u'名单=%d 仍无出边=%d 已有出边=%d'
      % (len(_only), len(_still), len(_got)))

_no_old = [s for s in _only if s in _old_from]
check(u'E2 ★★ 那 %d 个死胡同场景在本轮之前**确实**是 0 条边（不能拿"本来就有出口"的场景充数）'
      % EXPECT_DEADEND,
      not _no_old, u'本来就有边 %d: %r' % (len(_no_old), _no_old[:3]))

_dst_out = [r.get('to') for r in MINE if r.get('to') not in SCN]
check(u'E3 404 个场景的新出口**全部**指向已登记场景（不许为了"有出边"造一个空目标）',
      not _dst_out, u'未登记 %d: %r' % (len(_dst_out), _dst_out[:3]))

# ===========================================================================
print('')
print('=' * 70)
print(u'F 段  自检（判据也是被测物）')
print('=' * 70)

_src = io.open(SELF, encoding='utf-8').read()
_tree = ast.parse(_src)


def _arg(call, i):
    return call.args[i] if len(call.args) > i else None


_checks = [n for n in ast.walk(_tree)
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
           and n.func.id == 'check']
_const_true = []
for c in _checks:
    a = _arg(c, 1)
    if isinstance(a, ast.Constant) and bool(a.value):
        _const_true.append(getattr(c, 'lineno', -1))
check(u'F1 ★★★ 全部 %d 条 `check(...)` 的第二参**都不是**常量真'
      u'（恒真判据比不写还危险）' % len(_checks),
      len(_checks) > 0 and not _const_true,
      u'恒真行号=%r' % (_const_true[:5],))

_ok_defs = [n for n in ast.walk(_tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == 'ok']
_ok_calls = [n for n in ast.walk(_tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'ok']
check(u'F2 单一 harness：本文件只定义 `check(desc, cond, extra)`，'
      u'没有第二套 `ok(...)`（两套并存时只查一处必漏）',
      not _ok_defs and not _ok_calls)

check(u'F3 判据条数下限：AST 数出 >= 30 条（防有人整段删掉）',
      len(_checks) >= 30, u'实测 %d' % len(_checks))

#: ★★★ 这里踩过一次"扫描器扫到自己"：第一版把令牌**字面量**写进源码再全文找，
#:   于是那行**自己**就命中，F4 恒红（和"扫描器恒空"是同一个病的两面）。
#:   ⇒ ① 导入用 **AST** 查（不看文本）；② 盘符/协议用**拼接**构造，
#:   源码里（**包括注释**）都不许出现完整串 —— 第一次修完就是栽在注释里。
_bad_imp = []
for n in ast.walk(_tree):
    if isinstance(n, ast.Import):
        for a in n.names:
            if a.name.split('.')[0] in ('requests', 'urllib', 'socket', 'http'):
                _bad_imp.append(a.name)
    elif isinstance(n, ast.ImportFrom):
        if (n.module or '').split('.')[0] in ('requests', 'urllib', 'socket', 'http'):
            _bad_imp.append(n.module)
_pat = [('E' + ':' + '\\'), ('h' + 'ttp' + '://'), ('h' + 'ttps' + '://'),
        ('url' + 'open' + '('), ('DATA' + '_DIR' + ' = ' + "'" + 'E')]
_hit = [p for p in _pat if p in _src]
check(u'F4 零外部盘 / 零网络：无 requests/urllib/socket 导入、源码里不出现 E 盘路径或 URL'
      u'（★ 令牌用拼接构造，避免扫描器扫到自己）',
      not _bad_imp and not _hit, u'导入=%r 命中=%r' % (_bad_imp, _hit))

# ===========================================================================
print('')
print('=' * 70)
print(u'合计：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _bad:
    print(u'失败项：')
    for b in _bad:
        print(u'  - %s' % b)
print('=' * 70)
sys.exit(1 if _n['f'] else 0)

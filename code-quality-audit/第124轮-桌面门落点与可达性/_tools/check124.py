# -*- coding: utf-8 -*-
u"""第124轮回归锁：桌面 4 门的**落点**与「从桌面出发到底能走到几间」的可达性账。

## 本轮抓到的真缺陷（这套锁的由来）

桌面 C 门（UT）落点写的是 `ut.rooms.room_start`。而 `room_start` 是原作
**下标 0 的空壳/标题房** —— 实例只有 `obj_time` / `obj_layerchecker`，
**一个门都没有**（出边 0）⇒ 玩家从桌面推门进 UT 之后只能站在那一间里，
**整个 UT 一间接不到**（实测可达 1 间）。

真正的"人类坠落的地方"是 `room_area1`（出边 1 ⇒ ut 可达 33 间）。

★ 根因不是"路由条数不够"（ut 已有 525 条门路由），而是**入口选错了一间房**。
★ 更关键的教训：**之前 122 套件里没有任何一条判据问过"从桌面出发能走到几间"**
  —— 所有锁都在看"表里有没有这条边"，没有一条看"人能不能走到"。
  这套锁补的就是这个视角。

## 本套件守什么（零 Qt、零网络、零外部盘 —— 只读仓库内资产）

A 桌面落点 —— 4 条路由的 `to` 逐条等于口径 · C 门**不许**是 `room_start` ·
  **每条目标的出边都必须 > 0**（结构性判据，比字面量更根本）· 负控制：空壳房出边确实 0 ·
  **落点得真能画出来**（`load_scene` 走产品真路径拿到 bg 且文件在盘）· 落点带可交互物
B 可达性账 —— 从桌面并集可达 ≥ 199 · 每扇门单独可达 > 1 · ut 从 `room_area1` ≥ 33 ·
  **负控制：把 C 门换回 `room_start` ⇒ 可达掉到 167 / ut 掉到 1**（直接复现本轮缺陷）·
  守恒：可达 + 不可达 == 总场景（分母闸，防空集恒真）
C 空壳房负向锚 —— 4 间空壳/标题房**出边必须 0、且不许出现在任何 `to` 里** ·
  **原作下标 0~3 恰好就是这 4 间**（`room_area1` 是 4）· 负控制：`room_area1` 与它们相反
D 密度账 —— 每个作品"有出边的场景数"**只增不减** · 边数守恒（1 条合法重复边有账）
E 自检 —— AST 数恒真判据（不扫注释）· 无 BOM / 无 U+FFFD

## 纪律

`print('[PASS] %s')` 字面量；判据名不自带标记；正/负控制成对；**断行为不断赋值**；
★★★ 分母闸：任何"全都是 X"的判据都必须先证明分母非空（本套件的空集会把可达算成 0，
    而 0 < 199 会**恰好**让 B1 报红 —— 但会漏过 A3/C1 这类"空集恒真"的写法，故显式断分母）。
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
INDEX_P = os.path.join(SCENES, '_index.json')

for _p in (PKG, MODULES):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ★★★ 走产品真入口 `load_index()`（带 `ok`），**不是** `_index.json` 原始 JSON。
#   本套件第一版就踩了这个坑：原始 JSON 顶层是
#   `{schema_version, meta, default_scene, chapters}`（场景嵌在 chapters→areas→scenes），
#   直接 `d['scenes']` 拿到 `None` ⇒ 场景数 0 ⇒ 可达 0 ⇒ **每个数字都错，但不报错**。
from modules import scene_system as SS       # noqa: E402

EXPECT_SCENES = 2166
EXPECT_ROUTES = 1531

#: 字母 → (世界, 落点 scene_id)。**唯一真源**，与 `check89._A_DOOR_WORLD` 同口径。
DOOR_WANT = {
    'A': ('oneshot', 'oneshot.mainline.INIT'),    # 正上：车厢（原作 room 1）
    'B': ('oneshot', 'oneshot.mainline.Start'),   # 正下：Niko 的家（彩蛋门，永远进不去）
    'C': ('ut', 'ut.rooms.room_area1'),           # 正左：人类坠落的地方（★ 不是 room_start）
    'D': ('ch1', 'ch1.hometown.town_mid'),        # 正右：光世界小镇中心（原作 room 11）
}

#: 原作里的**空壳/标题房**：有房间资产，但没有一个门 ⇒ 出边 0。
#: 它们**永远不许**被当成入口或传送落点（第124轮的 bug 就是把这个当入口）。
BLANK_ROOMS = (
    'ut.rooms.room_start',        # 标题/空壳（实例只有 obj_time / obj_layerchecker）
    'ut.rooms.room_introstory',   # 开场文字（对象自绘，无门）
    'ut.rooms.room_introimage',   # 开场图片
    'ut.rooms.room_intromenu',    # 开场菜单
)

#: 从桌面出发的总可达下界（第124轮实测 199；只许增不许减）。
REACH_TOTAL_MIN = 199
#: ut 从 `room_area1` 的可达下界（实测 33）。
REACH_UT_MIN = 33
#: 负控制口径：把 C 门换回 `room_start` 后的可达（实测 167 / ut 1）。
REACH_TOTAL_OLD = 167
REACH_UT_OLD = 1

#: 各作品"有出边的场景数"下界（实测值；**只增不减**）。
DENSITY_MIN = {
    'ch1': 105, 'ch2': 127, 'ch3': 23, 'ch4': 22, 'ch5': 20,
    'oneshot': 196, 'ut': 270,
}
#: 唯一边数（1531 条路由里有 5 条合法重复：同房间**不同门**指向同一目标）。
#: · 1 条：`room_water12` 的两扇不同门都指向 `room_water11`（第123轮，见
#:   `verify_routes_order44.C1b`）；
#: · 4 条：第125轮新补的 X 门与该房间原有的 A/B 门指向同一目标
#:   （`cc_prison_cells↔cc_prisonlancer`、`forest_dancers1↔forest_secret1`）。
#: ★ 判据不靠这个数字：`D2` 同时要求"每个重复组内的门标识两两不同"
#:   —— 同门重复才是冗余，不同门同目标原作里本来就有。
EXPECT_UNIQUE_EDGES = 1526
EXPECT_DUP_EDGES = 5

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, detail=''):
    if cond:
        _n['p'] += 1
        print(u'[PASS] %s%s' % (desc, (u'    ' + detail) if detail else u''))
    else:
        _n['f'] += 1
        _failed.append(desc)
        print(u'[FAIL] %s%s' % (desc, (u'    ' + detail) if detail else u''))


def _json(p):
    with io.open(p, encoding='utf-8', newline='') as fh:
        return json.load(fh)


# ===========================================================================
#  读盘：产品真表
# ===========================================================================
IDX = SS.load_index(SCENES)
SC = IDX.get('scenes') or {}
RL = (_json(ROUTES_P) or {}).get('routes') or []

OUT = collections.defaultdict(set)
for _r in RL:
    _s, _t = _r.get('when_scene'), _r.get('to')
    if _s and _t:
        OUT[_s].add(_t)

INDEG = collections.Counter()
for _s, _ds in OUT.items():
    for _t in _ds:
        INDEG[_t] += 1


def closure(start, out_map=None):
    """从 `start` 出发按路由表做可达闭包（含自己）。"""
    om = OUT if out_map is None else out_map
    seen = {start}
    stack = [start]
    while stack:
        n = stack.pop()
        for m in om.get(n, ()):
            if m not in seen:
                seen.add(m)
                stack.append(m)
    return seen


def desk_targets():
    return {str(r.get('when_door')): r.get('to')
            for r in RL if r.get('when_scene') == 'desktop'}


def union_reach(tmap, out_map=None):
    u = set()
    for _L in sorted(tmap):
        u |= closure(tmap[_L], out_map)
    return u


# ===========================================================================
print(u'')
print(u'== A. 桌面 4 门的落点 ==')
# ===========================================================================
check(u'A0 分母：`load_index()` ok=True 且场景数 == %d、路由 == %d 条'
      u'（防空集恒真：场景数为 0 时后面"全都是 0"的判据会假绿）'
      % (EXPECT_SCENES, EXPECT_ROUTES),
      IDX.get('ok') is True and len(SC) == EXPECT_SCENES and len(RL) == EXPECT_ROUTES,
      u'scenes=%d routes=%d ok=%r' % (len(SC), len(RL), IDX.get('ok')))

TGT = desk_targets()
check(u'A1 ★★★ 桌面 4 条路由的字母 ↔ 落点**逐条等于口径**',
      set(TGT) == set(DOOR_WANT)
      and all(TGT.get(_L) == DOOR_WANT[_L][1] for _L in DOOR_WANT),
      u'%r' % (TGT,))

# A2 ★★★ 点破本轮缺陷：C 门**不许**再落回空壳房
#   ★ 为什么单独立一条：A1 是"等于口径"，口径本身写错了它也会跟着错
#     （第109轮就是这么把 `room_start` 写进口径的）。A2 是**独立于口径**的结构断言。
check(u'A2 ★★★ C 门（UT）落点**不是**空壳房 `ut.rooms.room_start`'
      u'（第124轮修的就是这个 —— 走进去只能站着）',
      TGT.get('C') != 'ut.rooms.room_start' and TGT.get('C') == 'ut.rooms.room_area1',
      u'C -> %r' % (TGT.get('C'),))

# A3 ★★★ 每条桌面门的**目标必须有出边**
#   这一条比 A1/A2 更根本：它不问"落点叫什么名字"，只问"落下去还能不能动"。
#   将来若把 C 门改成第三个房间，只要那间是死胡同，A3 一样报红。
_dead_doors = sorted(_L for _L in TGT if not OUT.get(TGT[_L]))
check(u'A3 ★★★ 4 扇桌面门的目标**出边都 > 0**（落下去就能继续走，不是死胡同）',
      len(TGT) == len(DOOR_WANT) and not _dead_doors,
      u'%r' % ({_L: len(OUT.get(TGT[_L], ())) for _L in sorted(TGT)},))

# A4 负控制：A3 的口径确实有鉴别力 —— 空壳房的出边真的是 0
#   ★ 若 `room_start` 也有出边，A3 就变成恒真判据（守不到任何东西）。
check(u'A4 负控制：`room_start` 出边 == 0（A3 因此**有鉴别力**，不是恒真）',
      len(OUT.get('ut.rooms.room_start', ())) == 0,
      u'out=%d' % len(OUT.get('ut.rooms.room_start', ())))

# A5 ★★★ "能走"之外还要"看得见"：落点必须能真读出场景（有 bg 且文件在盘）
#   ★ 走产品真路径 `load_scene(sid, SCENES, entry)`（= 独立文件 → 区域分片），
#     **不是**直接读 `_index.json` —— 索引里的 `bg` 是**摘要**，ut 全部房间在索引里
#     都是 `bg: null`，真正的 bg 只在 `_zone.ut.rooms.json` 分片里。
#     第一版若不慎读索引，会得到"全都没有背景"的假结论（这也是个"入口用错"的坑）。
_LAND = 'ut.rooms.room_area1'
_sc = SS.load_scene(_LAND, SCENES, SC.get(_LAND))
_bg = (_sc.bg if _sc is not None else None)
_bg_p = os.path.join(SCENES, _bg.replace('/', os.sep)) if isinstance(_bg, str) and _bg else ''
check(u'A5 ★★★ 落点 %s **真能画出来**（`load_scene` 非空 · bg 非空 · 文件在盘且非空）'
      % _LAND,
      _sc is not None and isinstance(_bg, str) and bool(_bg)
      and os.path.isfile(_bg_p) and os.path.getsize(_bg_p) > 0,
      u'bg=%r size=%s' % (_bg, (os.path.getsize(_bg_p) if os.path.isfile(_bg_p) else None)))

# A5b ★★ 对照：`room_start` **也有背景**（`bg/ut_room_start.png`）——
#   所以"空壳"的准确含义是**没门没物**，不是"没图"。别把它说成黑屏。
_st_bg = None
_st = SS.load_scene('ut.rooms.room_start', SCENES, SC.get('ut.rooms.room_start'))
if _st is not None:
    _st_bg = _st.bg
check(u'A5b ★★ `room_start` 也有背景（"空壳"= 无门无物，**不是**黑屏）'
      u'—— 所以不能靠"有没有图"判断是不是入口',
      isinstance(_st_bg, str) and bool(_st_bg)
      and len((SC.get('ut.rooms.room_start') or {}).get('objects') or []) == 0,
      u'room_start.bg=%r objects=%d'
      % (_st_bg, len((SC.get('ut.rooms.room_start') or {}).get('objects') or [])))

# A5c ★★ 落点**有可交互物**（不是空屋子）：那朵花 `obj_readable_flowers1` 就在这间
_objs = [o.get('src') for o in ((_sc.objects if _sc is not None else None) or [])
         if isinstance(o, dict)]
check(u'A5c ★★ 落点带 %d 个物件（含开头那朵花 `obj_readable_flowers1`）'
      % len(_objs),
      len(_objs) > 0 and 'obj_readable_flowers1' in _objs,
      u'%r' % (_objs[:6],))

# ===========================================================================
print(u'')
print(u'== B. 可达性账（本套件第一次把"人能不能走到"写成判据） ==')
# ===========================================================================
NEW_UNION = union_reach(TGT)

check(u'B1 ★★★ 从桌面出发（4 门并集）可达 ≥ %d 间' % REACH_TOTAL_MIN,
      len(NEW_UNION) >= REACH_TOTAL_MIN,
      u'%d / %d' % (len(NEW_UNION), len(SC)))

_alone = {_L: len(closure(TGT[_L])) for _L in sorted(TGT)}
_stub = sorted(_L for _L, _v in _alone.items() if _v <= 1)
check(u'B2 ★★★ 每扇门**单独**可达 > 1（门后面不是一间空屋子）',
      len(_alone) == len(DOOR_WANT) and not _stub,
      u'%r' % (_alone,))

UT_NEW = len(closure('ut.rooms.room_area1'))
check(u'B3 ★★ ut 从 `room_area1` 可达 ≥ %d 间' % REACH_UT_MIN,
      UT_NEW >= REACH_UT_MIN, u'%d' % UT_NEW)

# B4 ★★★ 负控制：**直接复现本轮缺陷** —— 只把 C 门换回 `room_start`，其余不动。
#   ★ 这是本套件最重要的一条：它证明 B1/B3 抓得住"退回空壳房"这个回退。
#   ★★ 不落盘篡改：只在内存里换一条边再重算（判据改变被测状态是纪律红线）。
#   ★★★ 第125轮改判据口径（**不是放宽**）：原来钉的是绝对值"总可达 == 167、
#     ut == 1"—— 那两个数**只是第124轮当时的时相值**。第125轮给 ch1~ch5 补了
#     139 条原作边，总可达必然变大 ⇒ 绝对值会假红。改成**结构性等价**：
#       · `room_start` 侧 ut 可达必须 == 1（它出边 0，只能站着 —— 这是空壳房的**定义**）；
#       · 两侧总可达之差**恰好等于**丢掉的 UT 房间数（`UT_NEW - 1`）。
#     这比绝对值更硬：它要求"换回空壳房只损失 UT 那一段，别处一间不差"。
_OLD_TGT = dict(TGT)
_OLD_TGT['C'] = 'ut.rooms.room_start'
OLD_UNION = union_reach(_OLD_TGT)
OLD_UT = len(closure('ut.rooms.room_start'))
check(u'B4 ★★★ 负控制：C 门换回 `room_start` ⇒ ut 只剩 %d 间、总可达恰好少掉 UT 那 %d 间'
      u'（缺陷可复现，且损失只落在 UT 段）'
      % (REACH_UT_OLD, UT_NEW - REACH_UT_OLD),
      OLD_UT == REACH_UT_OLD
      and len(OLD_UNION) == len(NEW_UNION) - (UT_NEW - REACH_UT_OLD),
      u'old_total=%d new_total=%d old_ut=%d new_ut=%d'
      % (len(OLD_UNION), len(NEW_UNION), OLD_UT, UT_NEW))

_unreach = len(SC) - len(NEW_UNION)
check(u'B5 ★★ 守恒：可达 %d + 不可达 %d == 总场景 %d（分母闸）'
      % (len(NEW_UNION), _unreach, len(SC)),
      len(NEW_UNION) + _unreach == len(SC) and len(SC) > 0)

_noout = [s for s in SC if not OUT.get(s)]
_island = [s for s in SC if OUT.get(s) and INDEG.get(s, 0) == 0]
print(u'    账：不可达 %d = 完全无出边 %d + 有出边但无入边（孤岛）%d'
      % (_unreach, len(_noout), len(_island)))
print(u'    分作品可达/总数：%r'
      % ({_k: (sum(1 for s in SC if s.split('.')[0] == _k and s in NEW_UNION),
              sum(1 for s in SC if s.split('.')[0] == _k))
          for _k in sorted({s.split('.')[0] for s in SC})},))

# ===========================================================================
print(u'')
print(u'== C. 空壳房负向锚（它们永远不许当入口/落点） ==')
# ===========================================================================
_bad_out = [(s, len(OUT.get(s, ()))) for s in BLANK_ROOMS if OUT.get(s)]
check(u'C1 ★★★ %d 间空壳/标题房的出边**都是 0**' % len(BLANK_ROOMS),
      not _bad_out, u'%r' % (_bad_out,))

_present = [s for s in BLANK_ROOMS if s in SC]
_as_to = sorted(s for s in BLANK_ROOMS if INDEG.get(s, 0))
check(u'C2 ★★★ %d 间空壳房**都不在任何 `to` 里**（不许被当传送落点）' % len(BLANK_ROOMS),
      len(_present) == len(BLANK_ROOMS) and not _as_to,
      u'in_index=%d/%d as_to=%r' % (len(_present), len(BLANK_ROOMS), _as_to))

# C3 负控制：`room_area1` 与空壳房**正好相反** ⇒ 证明 C1/C2 不是在"全都 0"的退化下通过
check(u'C3 负控制：`room_area1` 出边 > 0 且是落点（与空壳房相反，C1/C2 有鉴别力）',
      len(OUT.get('ut.rooms.room_area1', ())) > 0
      and INDEG.get('ut.rooms.room_area1', 0) > 0)

# C4 ★★★ 房间号这一层也要对：`room_area1` = 原作下标 **4**，`room_start` = **0**
#   ★★★ 本条是"判据自己也是被测物"的现场：我第一版写的是
#     "两间房 `original_room_id` 都是 0 ⇒ 房间号判据分辨不出它们"，**这句是错的**
#     （实测 4 vs 0），当场被这条判据打红。真相反过来：
#     **房间号能分辨，所以 `check89.B4c` 把期望值写成 0 是写错了** —— 已同步改成 4。
#   ★★ 顺带钉住原作事实：0=room_start · 1=room_introstory · 2=room_introimage ·
#     3=room_intromenu · 4=room_area1 —— **0~3 全是开场/标题屏**。
_rid_a1 = (SC.get('ut.rooms.room_area1') or {}).get('original_room_id')
_rid_st = (SC.get('ut.rooms.room_start') or {}).get('original_room_id')
check(u'C4 ★★★ 原作下标：`room_area1` == 4 · `room_start` == 0（两者**可分辨**）'
      u'—— 所以"UT 入门 = room 0"这个旧口径本身是错的',
      _rid_a1 == 4 and _rid_st == 0 and _rid_a1 != _rid_st,
      u'area1.rid=%r room_start.rid=%r' % (_rid_a1, _rid_st))

# C5 ★★★ 前 4 间（下标 0~3）**全部**是开场/标题屏 —— 这是把 C1/C2/C4 串起来的原作事实
#   依据：`第61轮/_evidence/ut_rooms.json` 的 index↔name 表（338 行）。
_OPENING = {'ut.rooms.room_start': 0, 'ut.rooms.room_introstory': 1,
            'ut.rooms.room_introimage': 2, 'ut.rooms.room_intromenu': 3}
_rid_of = {v: (SC.get(v) or {}).get('original_room_id') for v in _OPENING}
check(u'C5 ★★★ 下标 0~3 恰好是那 4 间空壳/标题房（开场屏全体，一个不差）',
      _rid_of == _OPENING and sorted(_OPENING) == sorted(BLANK_ROOMS),
      u'%r' % (_rid_of,))

# ===========================================================================
print(u'')
print(u'== D. 路由密度账（只增不减） ==')
# ===========================================================================
_world_out = collections.Counter()
_world_sc = collections.Counter()
for _s in SC:
    _k = _s.split('.')[0]
    _world_sc[_k] += 1
    if OUT.get(_s):
        _world_out[_k] += 1
_thin = sorted((_k, _world_out.get(_k, 0), _v) for _k, _v in DENSITY_MIN.items()
               if _world_out.get(_k, 0) < _v)
check(u'D1 ★★★ 每个作品"有出边的场景数"不低于 %r（只增不减）' % (DENSITY_MIN,),
      not _thin, u'%r' % (_thin,))

_uniq = sum(len(v) for v in OUT.values())


def _door_id(r):
    u"""一条路由的"门标识"：字母门用 `when_door`，对象级门（ut）用 `when_src`。"""
    return str(r.get('when_door') or r.get('when_src') or '')


def _same_door_groups(rows):
    u"""返回"同一对 (场景,目标) 里有**同一扇门**重复"的键（空 = 没有冗余重复）。

    纯谓词：真表与合成坏输入共用一份实现（同一判据不许两份实现）。
    """
    by = collections.defaultdict(list)
    for r in rows:
        by[(r.get('when_scene'), r.get('to'))].append(r)
    return sorted(k for k, v in by.items()
                  if len(v) > 1 and len(set(_door_id(x) for x in v)) < len(v))


_same_door = _same_door_groups(RL)
check(u'D2 ★★ 边数守恒：唯一边 %d + %d 条合法重复 == 路由 %d 条；且每个重复组内的'
      u'**门标识两两不同**（同房间不同门同目标 = 合法；同门重复 = 冗余）'
      % (EXPECT_UNIQUE_EDGES, EXPECT_DUP_EDGES, EXPECT_ROUTES),
      _uniq == EXPECT_UNIQUE_EDGES and len(RL) - _uniq == EXPECT_DUP_EDGES
      and not _same_door,
      u'unique=%d routes=%d dup=%d 同门重复=%r'
      % (_uniq, len(RL), len(RL) - _uniq, _same_door[:3]))
check(u'D2b 正/负控制：`_same_door_groups` 对真表返回空、对"同门重复"的合成输入报出 1 组'
      u'（证明 D2 不是"条数对上就绿"）',
      _same_door_groups([]) == []
      and _same_door_groups([
          {'when_scene': 'a', 'to': 'b', 'when_door': 'A'},
          {'when_scene': 'a', 'to': 'b', 'when_door': 'A'}]) == [('a', 'b')]
      and _same_door_groups([
          {'when_scene': 'a', 'to': 'b', 'when_door': 'A'},
          {'when_scene': 'a', 'to': 'b', 'when_door': 'X'}]) == [])

print(u'    密度账：%r' % ({_k: (_world_out.get(_k, 0), _world_sc[_k])
                            for _k in sorted(_world_sc)},))

# ===========================================================================
print(u'')
print(u'== E. 自检 ==')
# ===========================================================================


def _true_checks(path):
    out = []
    for node in ast.walk(ast.parse(io.open(path, encoding='utf-8', newline='').read())):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else None
        if name not in ('check', 'ok'):
            continue
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
                and node.args[1].value is True:
            out.append((os.path.basename(path), node.lineno))
    return out


check(u'E1 没有 `check(x, True)` 恒真判据（AST 判，不扫注释）',
      not _true_checks(os.path.abspath(__file__)))

for _p, _tag in ((ROUTES_P, u'_routes.json'), (os.path.join(MODULES, u'scene_system.py'),
                                              u'scene_system.py')):
    _raw = io.open(_p, encoding='utf-8', newline='').read()
    check(u'E2 `%s` 无 BOM / 无 U+FFFD' % _tag,
          not _raw.startswith(u'\ufeff') and u'\ufffd' not in _raw)

check(u'E3 被测文件都在盘（路由表 / 索引 / 产品加载器）',
      all(os.path.isfile(_p) for _p in
          (ROUTES_P, INDEX_P, os.path.join(MODULES, u'scene_system.py'))))

print(u'')
print(u'---- 共 %d 条：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(1 if _failed else 0)

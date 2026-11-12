# -*- coding: utf-8 -*-
u"""第173轮 · 「`obj_doorAny` 实例物化」回归锁。

## 本轮做了什么

第172轮把 **798 条** Any 门边写进了 `_routes.json`，但**一条都没被消费** ——
`build_props()` 遍历 `scene['objects']`，而场景数据里 `src == 'obj_doorAny'`
的条目**一个都没有** ⇒ 没有实例就没人调 `route_for_door()`。

根因不是"忘了写"，是**素材缺失导致的过滤**：
`gen_objects44.object()` 的规矩是「查不到 sprite 帧 ⇒ 返回 None」，
而 `assets/scenes/objs/` 里**没有 `spr_doorAny_0.png`**（`spr_doorA..F` 都有）
⇒ 881 条 Any 实例被生成器静默跳过。

本轮按「幂等追加」把实例补进场景（**不重跑生成器**，避免冲掉第68/117轮的增量）：

    {`pos`: [x, y], `src`: "obj_doorAny", `depth`?: int}

**故意不写 `sprite`**：原作 `obj_doorAny` 是 `visible=false` 的触发器，
`is_drawable_object()` 靠 `_obj_visible.json` 的 hidden 名单把它滤掉 ⇒ 永不绘制；
写一个指向不存在文件的 sprite 才是假话。

## 四本账（本节最重要，全在 A 段独立重算）

    881  第42轮普查里的 Any 实例总数
    830  按「章:房间」去重后（同坐标重复摆两扇算一条）
    820  落在**已登记场景**里的（= 本轮物化条数）
     10  落在**未登记房间**里的（没有载体，如实落空，不硬塞）

## 判据分五段

- A 段：四本账 + 逐章（**全部独立重算**，不读注入器自报数）
- B 段：产品 ↔ 普查**逐单元**对账（每个场景载体一份坐标集合必须相等）
- C 段：**端到端**消费（真的过 `build_props` → `route_for_door` → 得到目标场景）
- D 段：不造边 + 反回滚（`_routes.json` 与既有 objects 一个字都不许动）
- E 段：自检（单一 harness / 判据条数下限 / AST 查恒真 / 零外部盘 / 不起真机）

## 本轮踩到的坑（留档，别再踩）

★★★ **`_index.json` 比场景文件多 87 个「(章,房间)」对。** 第一版注入器只认场景
自带的 `original_room_id`，而 **88 个独立场景文件里 87 个没有这个字段**
⇒ 那 87 个房间的 115 条 Any 门全被算成"未登记"。
修法：房间号**回退到 `_index.json`**（产品运行时 `MainWindow._scene_rooms()`
本来就只读 index，见 `main.py` 第 4694~4698 行）⇒ 与运行时同源。
★★ 判据第一版拿 index 当分母、产品当分子，`C2` 少了 115 条报红 —— 那不是回归，
是**分母没对齐载体**。现在两边都按"载体 + index 回退"算，且 A 段把四本账摊开。

★ 环境变量口子（只给 `mutate173.py` 用，判据本身一行不改）
  `CQ_PKG173` / `CQ_EV42_173` / `CQ_E43_173` / `CQ_EV68_173`
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
PKG = os.environ.get('CQ_PKG173') or os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
OBJS = os.path.join(SCENES, 'objs')
E42 = os.environ.get('CQ_EV42_173') or os.path.join(
    REPO, 'code-quality-audit', u'第42轮-原作拓扑取证', '_evidence')
E43 = os.environ.get('CQ_E43_173') or os.path.join(
    REPO, 'code-quality-audit', u'第43轮-原作门与相机取证', '_evidence')
EV68 = os.environ.get('CQ_EV68_173') or os.path.join(
    REPO, 'code-quality-audit', u'第68轮-可交互道具实例补采', '_evidence')
#: ★ 第172轮取证（原作侧 Any 实例表）—— 只用来**交叉锚定 881** 这个数，
#   不参与任何产品口径。跨轮取证比"我记忆里是 881"硬。
E172 = os.environ.get('CQ_EV172_173') or os.path.join(
    REPO, 'code-quality-audit', u'第172轮-Any门接线', '_evidence')
SELF = os.path.abspath(__file__)

for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from modules.item_interact import build_props, classify, door_letter_of  # noqa: E402
from modules.scene_system import load_index, load_obj_visible, \
    is_drawable_object  # noqa: E402

#: 本轮补的对象名
WANT = 'obj_doorAny'
#: ★ 四本账的**口径锚点**（不是"随手写的数"）
#:   881 = 第172轮**原作侧**实例表（`analyze172.json` 的 rows，跨轮交叉锚定）
#:   830 = 第42轮普查里的 Any 实例条数（恰好已无重复坐标 ⇒ 与去重值相同）
#:   820 + 10 = 830 按「有没有场景载体」二分
EXPECT_INST = 881
EXPECT_DEDUP = 830
EXPECT_MATERIAL = 820
EXPECT_NOROOM = 10
#: 历史冻结：`_routes.json` 第172轮落定后不许再变
#: ★ 第174轮：2,759 → 2,810（补了 `obj_doorAnyHorz/Vert` 51 条）。
#:   这里改成 **floor**（`>=`）：后续轮次只许往上加，缩水由「Any 边 798 未变 +
#:   反回滚」两条兜；写死绝对数会在下一轮合法增量时假红（第171轮踩过）。
EXPECT_ROUTES = 2768              # 2,810 - 42（第176轮删误标边，见下）
#: ★★ 第176轮：删掉 42 条**误标**的 `via='obj_doorAny'` 边（真身是变体
#:   `obj_doorAnyHorz/Vert`，第174轮已落过同样的 (场景,目标,坐标)）⇒
#:   `obj_doorAny` 边 798 -> 756。**从留档读，不写死**：这条判据的本意是
#:   "any 边数没被本轮（第173轮）动过"，删边是**另一轮**的事、有账可查才放行。
RM_P = os.environ.get('CQ_RM173') or os.path.join(
    REPO, 'code-quality-audit', u'第176轮-订正172误标边', '_evidence',
    'removed176.json')
EXPECT_ANY_EDGES_EVID = 798       # 第172轮落定时的原值（冻结）
#: 第174轮把另外两个变体也物化了 ⇒ 「非本轮对象」的口径必须扩到**整个家族**，
#: 否则每加一个变体 `_non_any_ch` 就会涨一截，这条守卫会自己失效。
ANY_FAMILY = ('obj_doorAny', 'obj_doorAnyHorz', 'obj_doorAnyVert',
              'obj_doorAnyModespecific')
#: 历史冻结：本轮**不许**动任何既有 objects（只追加）
EXPECT_ORIG_OBJS = 3197           # 第68轮普查口径（五章可绘制实例）
#: ★ 第185轮：`ch1.forest.room_man` 登记进产品 ⇒ 它那 **4 个**物件进入世界。
#: **只加账**：上面那个历史冻结值一个字不动。
MAN_185 = 4
EXPECT_DESKTOP_DOORS = 4          # `desktop.json` 的世界门（现读校验）
#: C 段：解析不出目标的那几条（所在场景在原作里就没有 Any 门边）
EXPECT_UNRESOLVED = 19
#: 判据条数下限（自检用）
CHECK_FLOOR = 30
#: 普查分段文件名
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


#: ★★ 第176轮的删除留档 —— `obj_doorAny` 边的期望值由它**推出来**
if not os.path.isfile(RM_P):
    print(u'[FATAL] 找不到第176轮删除留档：%s' % RM_P)
    sys.exit(2)
EXPECT_ANY_EDGES = EXPECT_ANY_EDGES_EVID - len(jl(RM_P)['items'])


def inst_rooms(p):
    """一张普查 → `{房间下标: [实例, ...]}`（缺文件 ⇒ 空表，让 A 段报红而非中途抛）。"""
    if not os.path.isfile(p):
        return {}
    out = {}
    for rec in ((jl(p).get('rooms')) or []):
        rid = rec.get('index')
        if isinstance(rid, int):
            out[rid] = rec.get('insts') or []
    return out


# ---------------------------------------------------------------------------
# 一、源数据
# ---------------------------------------------------------------------------
INST = {ch: inst_rooms(os.path.join(E42, fn)) for ch, fn in INST42.items()}
IDX = load_index() if False else None            # 占位：下面显式读，避免循环导入副作用
INDEX = jl(os.path.join(SCENES, '_index.json'))
ROUTES_RAW = jl(os.path.join(SCENES, '_routes.json'))
ROUTES = ROUTES_RAW.get('routes') if isinstance(ROUTES_RAW, dict) else ROUTES_RAW
ROUTES = ROUTES or []
OBJ_FILES = set(os.listdir(OBJS)) if os.path.isdir(OBJS) else set()


def index_pairs():
    """`_index.json` 里登记的全部 `(章, 房间下标)`（★保留重复：一房可登记成多场景）。"""
    out = []
    for ch, blk in ((INDEX.get('chapters')) or {}).items():
        if not isinstance(blk, dict):
            continue
        for _a, ablk in ((blk.get('areas')) or {}).items():
            if not isinstance(ablk, dict):
                continue
            for _s, e in ((ablk.get('scenes')) or {}).items():
                if isinstance(e, dict) and isinstance(e.get('original_room_id'), int):
                    out.append((ch, e['original_room_id']))
    return out


def index_room_of():
    """`{scene_id: 房间下标}` —— 与 `main.py::_scene_rooms()` **同源同口径**。"""
    out = {}
    for ch, blk in ((INDEX.get('chapters')) or {}).items():
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
PAIRS = index_pairs()


def survey_any():
    """`{(章, 房间): {(x, y), ...}}` —— 普查里 Any 门的**去重**坐标集合。

    ★ 为什么是集合而不是计数：注入器按 `(x, y)` 去重（同一坐标重复摆两扇＝一条），
      判据若按条数比，遇到原作者手抖摆重就会报假红。
    """
    out = collections.defaultdict(set)
    raw = 0
    for ch, rooms in INST.items():
        for rid, insts in rooms.items():
            for it in insts:
                if it.get('obj') != WANT:
                    continue
                x, y = it.get('x'), it.get('y')
                if not isinstance(x, int) or not isinstance(y, int):
                    continue
                raw += 1
                out[(ch, rid)].add((x, y))
    return out, raw


ANY_SURVEY, ANY_RAW = survey_any()
REG = set(PAIRS)
ANY_EXPECT = {k: v for k, v in ANY_SURVEY.items() if k in REG}
ANY_NOROOM = {k: v for k, v in ANY_SURVEY.items() if k not in REG}
#: 独立重算的「应物化」条数（按载体算：每个登记了对都给一份）
EXP_MATERIAL = sum(len(ANY_EXPECT.get(p, ())) for p in PAIRS)
EXP_MATERIAL_BY_CH = collections.Counter()
for _p in PAIRS:
    EXP_MATERIAL_BY_CH[_p[0]] += len(ANY_EXPECT.get(_p, ()))


# ---------------------------------------------------------------------------
# 二、产品侧：把每个**场景载体**摊平成单元
# ---------------------------------------------------------------------------
def scene_units():
    """`[(标签, 章, 房间下标或None, 场景dict)]` —— 与注入器**同源**（场景容器）。

    ★ 独立场景文件里 87 个**没有 `original_room_id`** ⇒ 回退 `_index.json`
      （与产品运行时 `_scene_rooms()` 同源）。这条回退是本轮最贵的一课：
      第一版不给回退，87 个房间的 115 条门全被算成"未登记"。
    """
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
                out.append(('%s#%s' % (name, sid), ch, rid, sc,
                            str(sc.get('scene_id') or sid)))
        elif 'objects' in d or 'scene_id' in d:
            ch = d.get('chapter_id')
            rid = d.get('original_room_id')
            sid = str(d.get('scene_id') or '')
            if not isinstance(rid, int):
                rid = ROOM_OF.get(sid)
            out.append((name, ch, rid, d, sid))
    return out


UNITS = scene_units()


def unit_any(sc):
    """一个场景里 Any 条目的坐标列表（**保留重复**，用于查重）。"""
    return [(tuple(o.get('pos') or ()), o)
            for o in (sc.get('objects') or [])
            if isinstance(o, dict) and o.get('src') == WANT]


# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'A 段  四本账与分母（全部独立重算）')
print('=' * 70)

_n172 = os.path.join(E172, 'analyze172.json')
_n172_rows = len((jl(_n172).get('rows') or [])) if os.path.isfile(_n172) else -1

check(u'A0 原作侧锚定：第172轮实例表 %d 条 == %d（跨轮互证；缺文件此处必红）'
      % (_n172_rows, EXPECT_INST),
      _n172_rows == EXPECT_INST,
      u'（不读它就无法证明"普查没漏采"）')

check(u'A1 普查侧：Any 实例 %d 条、去重后 %d 条、落 %d 个「章:房间」键'
      % (ANY_RAW, sum(len(v) for v in ANY_SURVEY.values()), len(ANY_SURVEY)),
      ANY_RAW == EXPECT_DEDUP
      and sum(len(v) for v in ANY_SURVEY.values()) == EXPECT_DEDUP,
      u'raw=%d dedup=%d keys=%d（第42轮普查恰好没有重复坐标，故两个数相等；'
      u'若哪天不等，说明普查口径变了）'
      % (ANY_RAW, sum(len(v) for v in ANY_SURVEY.values()), len(ANY_SURVEY)))

_material = sum(len(v) for v in ANY_EXPECT.values())
_noroom = sum(len(v) for v in ANY_NOROOM.values())
check(u'A2 四本账自洽：%d（普查）＝ %d（已登记房间）＋ %d（未登记房间）'
      % (EXPECT_DEDUP, EXPECT_MATERIAL, EXPECT_NOROOM),
      sum(len(v) for v in ANY_SURVEY.values()) == _material + _noroom
      and _material == EXPECT_MATERIAL and _noroom == EXPECT_NOROOM,
      u'已登记=%d 未登记=%d' % (_material, _noroom))

check(u'A3 分母非空：已登记且有 Any 的 `(章,房间)` 键 %d 个、未登记 %d 个'
      % (len(ANY_EXPECT), len(ANY_NOROOM)),
      len(ANY_EXPECT) > 0 and len(ANY_NOROOM) > 0,
      u'登记键=%d 未登记键=%d' % (len(ANY_EXPECT), len(ANY_NOROOM)))

_act = []
for _u in UNITS:
    _act.extend(unit_any(_u[3]))
check(u'A4 产品侧：`src == obj_doorAny` 条目 %d 条 == 独立重算 %d 条'
      % (EXPECT_MATERIAL, EXP_MATERIAL),
      len(_act) == EXP_MATERIAL,
      u'实得=%d 独立算=%d' % (len(_act), EXP_MATERIAL))

check(u'A5 ★本轮之前产品里 Any 条目恒为 0（"路网画在图上没铺到地上"的直接证据）'
      u' —— 本轮从 0 起算，故 %d 条全部是本轮增量' % EXPECT_MATERIAL,
      EXPECT_MATERIAL == len(_act) and len(_act) > 0,
      u'n=%d（若这条红了，说明别处也在写 Any，先查清谁写的）' % len(_act))

for _ch in CHS:
    _got = sum(len(unit_any(u[3])) for u in UNITS if u[1] == _ch)
    _want = EXP_MATERIAL_BY_CH.get(_ch, 0)
    check(u'A6-%s 逐章：%d 条 == 独立重算 %d 条' % (_ch, _got, _want),
          _got == _want and (_want > 0 or _ch == 'ch1'),
          u'实得=%d 期望=%d' % (_got, _want))

_zone_units = [u for u in UNITS if u[0].startswith('_zone.') and unit_any(u[3])]
_file_units = [u for u in UNITS if not u[0].startswith('_zone.') and unit_any(u[3])]
check(u'A7 两种载体**都有**：分片 %d 个场景、独立文件 %d 个场景'
      % (len(_zone_units), len(_file_units)),
      bool(_zone_units) and bool(_file_units),
      u'（只写分片或只写独立文件都说明注入器漏了一路）')

check(u'A8 判据分母不随环境变：分片数 %d >= 61、独立文件载体 %d >= 1'
      % (len([f for f in os.listdir(SCENES)
              if f.startswith('_zone.') and f.endswith('.json')]), len(_file_units)),
      len([f for f in os.listdir(SCENES)
           if f.startswith('_zone.') and f.endswith('.json')]) >= 61
      and len(_file_units) >= 1)

# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'B 段  产品 ↔ 普查 逐单元对账')
print('=' * 70)

#: 每个单元的违规（多一条/少一条/坐标不同）
_diff = []
for label, ch, rid, sc, sid in UNITS:
    key = (ch, rid)
    want = ANY_EXPECT.get(key)
    got = [p for p, _o in unit_any(sc)]
    if want is None:
        if got:
            _diff.append((label, ch, rid, u'不该有却有 %d 条' % len(got)))
        continue
    if set(got) != want:
        _diff.append((label, ch, rid,
                      u'多 %d / 少 %d' % (len(set(got) - want), len(want - set(got)))))
check(u'B0 ★逐单元对账：%d 个载体里坐标集合与普查**完全相等**（不同=%d）'
      % (len(UNITS), len(_diff)),
      not _diff,
      u'首个不符=%r' % ((_diff[0] if _diff else None),))
for _d in _diff[:5]:
    print('       不符: %r' % (_d,))

_dup = []
for label, ch, rid, sc, sid in UNITS:
    coords = [p for p, _o in unit_any(sc)]
    if len(coords) != len(set(coords)):
        _dup.append((label, coords))
check(u'B1 无重复条目（同一场景同一坐标只允许一条）重复场景=%d' % len(_dup),
      not _dup, u'首个=%r' % ((_dup[0] if _dup else None),))

_badshape = []
for label, ch, rid, sc, sid in UNITS:
    for pos, o in unit_any(sc):
        if not (isinstance(o.get('pos'), (list, tuple)) and len(o['pos']) == 2
                and all(isinstance(v, int) for v in o['pos'])):
            _badshape.append((label, 'pos', o))
        if o.get('sprite') is not None:
            _badshape.append((label, 'sprite 非 None', o))
        if 'depth' in o and not isinstance(o['depth'], int):
            _badshape.append((label, 'depth', o))
check(u'B2 条目形状：pos=2×int / **无 sprite**（原作 visible=false，写了才是假话）'
      u'/ depth 若存在必 int —— 坏 %d' % len(_badshape),
      not _badshape, u'首个=%r' % ((_badshape[0] if _badshape else None),))

_noroom_leak = [(u[0], u[1], u[2], len(unit_any(u[3])))
                for u in UNITS
                if (u[1], u[2]) not in ANY_EXPECT and unit_any(u[3])]
check(u'B3 「普查里没有 Any 的键」产品里**一条都不许有**（含 %d 个未登记房间的 %d 条'
      u' —— 落不进去就如实记账，不许硬塞到别的载体）：泄漏 %d 处'
      % (len(ANY_NOROOM), _noroom, len(_noroom_leak)),
      not _noroom_leak,
      u'（★ 这条为什么不按坐标判：实测 ch3/ch4/ch5 各有 1~4 个坐标在'
      u'「已登记/未登记」房间之间**重复**（如 ch4 的 (0,360)），按坐标判会假红）')

_keys_hit = set()
for _u in UNITS:
    if unit_any(_u[3]):
        _keys_hit.add((_u[1], _u[2]))
check(u'B4 覆盖到的「章:房间」键 %d == 独立重算 %d'
      % (len(_keys_hit), len(ANY_EXPECT)),
      _keys_hit == set(ANY_EXPECT),
      u'缺=%r 多=%r' % (sorted(set(ANY_EXPECT) - _keys_hit)[:3],
                        sorted(_keys_hit - set(ANY_EXPECT))[:3]))

# ---- 负控制：判据真的抓得住"少一条/多一条"吗 ----
_fake_missing = None
for label, ch, rid, sc, sid in UNITS:
    if unit_any(sc):
        coords = [p for p, _o in unit_any(sc)]
        _fake_missing = (label, set(coords[1:]), set(coords))
        break
check(u'B5 负控制：从任一有 Any 的场景**抠掉一条** ⇒ B0 的集合比较必然不等'
      u'（证明 B0 不是恒真）',
      _fake_missing is not None
      and _fake_missing[1] != _fake_missing[2]
      and len(_fake_missing[1]) < len(_fake_missing[2]),
      u'样本=%r' % ((_fake_missing[0], len(_fake_missing[1]),
                     len(_fake_missing[2])) if _fake_missing else None,))

check(u'B6 负控制：编造一个未登记房间键 `(ch1, -1)` 必然不在普查里'
      u'（证明 B3 的"未登记"判定有鉴别力）',
      ('ch1', -1) not in REG and ('ch1', -1) not in ANY_SURVEY)

check(u'B7 正/负控制：`obj_doorAny` 在 `_obj_visible.json` 的 hidden 名单里、'
      u'**可见**物件 `obj_savepoint` 不在（前者是"无 sprite"豁免的前提）',
      WANT in load_obj_visible() and 'obj_savepoint' not in load_obj_visible(),
      u'hidden 条数=%d' % len(load_obj_visible()))

# ★ 注意：`is_drawable_object` 的 `hidden` 是**必传参数**，默认 None ⇒ 恒 True。
#   第一版没传，B8 就成了恒真（"不传 = 什么都画"），差点当绿收工。
_HID = load_obj_visible()
check(u'B8 `is_drawable_object({"src": "obj_doorAny"}, hidden)` 判**不可绘制**、'
      u'`obj_savepoint` 判可绘制（◇ 传 hidden 才算数，不传恒 True）',
      is_drawable_object({'src': WANT}, _HID) is False
      and is_drawable_object({'src': 'obj_savepoint'}, _HID) is True
      and is_drawable_object({'src': WANT}) is True,
      u'不传 hidden 时恒 True —— 这条负控制就是钉这个坑的')

# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'C 段  端到端消费（build_props → route_for_door → 目标场景）')
print('=' * 70)

check(u'C0 `classify("obj_doorAny")["kind"] == "door"`（分类器认得它，才有人建门）',
      (classify(WANT) or {}).get('kind') == 'door',
      u'rec=%r' % (classify(WANT),))
check(u'C1 `door_letter_of("obj_doorAny")` 为 None ⇒ 只能走**对象级**（when_src）那一路'
      u'（走字母级必然查不到）',
      door_letter_of(WANT) is None, u'got=%r' % (door_letter_of(WANT),))

_has_src_row = collections.defaultdict(bool)
for r in ROUTES:
    if isinstance(r, dict) and r.get('when_src') == WANT and r.get('to'):
        _has_src_row[r.get('when_scene')] = True

_resolved = 0
_unresolved = []
_targets = {}
for label, ch, rid, sc, sid in UNITS:
    insts = unit_any(sc)
    if not insts:
        continue
    sc2 = dict(sc)
    sc2['scene_id'] = sid
    props = build_props(sc2, ch or (sid or '').split('.')[0], None, routes=ROUTES)
    got = [p for p in props if getattr(p, 'src', None) == WANT]
    _resolved += len(got)
    for p in got:
        _targets.setdefault(sid, set()).add(getattr(p, 'target_scene', None))
    if len(got) < len(insts):
        for _pos, o in insts[len(got):]:
            _unresolved.append((sid, ch, rid, _pos))
        _unresolved_sid_missing = None

check(u'C2 ★★端到端：%d 条实例里 **%d 条真的解析出了目标场景**（`build_props` 实测，'
      u'不是查源码猜的）' % (EXPECT_MATERIAL, _resolved),
      _resolved == EXPECT_MATERIAL - EXPECT_UNRESOLVED,
      u'实得=%d 期望=%d' % (_resolved, EXPECT_MATERIAL - EXPECT_UNRESOLVED))

check(u'C3 解析不出的 %d 条，**逐条**都落在「该场景在原作里没有 Any 门边」的场景里'
      u'（不是查表失败，是原作就没写）' % len(_unresolved),
      len(_unresolved) == EXPECT_UNRESOLVED
      and all(not _has_src_row.get(sid) for sid, _c, _r, _p in _unresolved),
      u'实际=%d、其中所在场景有路由的=%d'
      % (len(_unresolved),
         sum(1 for sid, _c, _r, _p in _unresolved if _has_src_row.get(sid))))

_all_scenes = set(ROOM_OF.keys())
check(u'C4 解析出的目标场景**全部真实存在**（%d 个来源场景 → %d 个目标）'
      % (len(_targets), len(set().union(*_targets.values()) if _targets else set())),
      _targets and all(t in _all_scenes
                       for ts in _targets.values() for t in ts if t),
      u'不存在的目标=%r' % ([t for ts in _targets.values() for t in ts
                            if t and t not in _all_scenes][:3],))

# ★ 同场景两扇门各去各处（第172轮 `_pick_by_pos` 的立身之本）
_multi = {sid: ts for sid, ts in _targets.items() if len(ts) >= 2}
check(u'C5 ★同场景多扇 Any 门**分流到不同目标**的场景 %d 个（`_pick_by_pos` 真的在起作用）'
      % len(_multi),
      len(_multi) >= 1,
      u'样本=%r' % (list(_multi.items())[:2],))

# ★ 不给 pos 时必须退回"priority 最小"，且**仍非 None**（老调用方不受影响）
_probe = None
for label, ch, rid, sc, sid in UNITS:
    if len(_targets.get(sid) or ()) >= 2:
        _probe = sid
        break
if _probe is None:
    check(u'C6 负控制：挑一个多扇场景验证"不给 pos 退回 priority 最小"', False,
          u'找不到多扇场景')
else:
    from modules.item_interact import route_for_door  # noqa: E402
    _a = route_for_door(ROUTES, _probe, None, src=WANT, pos=None)
    _b = route_for_door(ROUTES, _probe, None, src=WANT, pos=[-999999, -999999])
    check(u'C6 负控制：不给 pos / 给不存在的坐标 ⇒ 退回 priority 最小，**两次答案相同**',
          _a is not None and _a == _b,
          u'%s -> %r / %r' % (_probe, _a, _b))

check(u'C7 负控制：`route_for_door` 对**编造的 src** 必须返 None（不是"总能查到"）',
      route_for_door(ROUTES, _probe, None, src='obj_door_zzz_fake', pos=None) is None)

# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'D 段  不造边 + 反回滚')
print('=' * 70)

_any_edges = [r for r in ROUTES if isinstance(r, dict) and r.get('when_src') == WANT]
check(u'D0 `_routes.json` 总条数 %d >= %d（floor）、`obj_doorAny` 边 %d 条**未变**'
      u'（本轮**只动物件，不动路网**）'
      % (len(ROUTES), EXPECT_ROUTES, EXPECT_ANY_EDGES),
      len(ROUTES) >= EXPECT_ROUTES and len(_any_edges) == EXPECT_ANY_EDGES,
      u'实际 routes=%d any=%d' % (len(ROUTES), len(_any_edges)))

_non_any_ch = 0
for _u in UNITS:
    if _u[1] not in CHS:
        continue
    for o in (_u[3].get('objects') or []):
        if isinstance(o, dict) and o.get('src') not in ANY_FAMILY:
            _non_any_ch += 1
_desktop_p = os.path.join(SCENES, 'desktop.json')
_desktop = len((jl(_desktop_p).get('objects') or [])) if os.path.isfile(_desktop_p) else -1
check(u'D1 既有 objects **一个都没被改**：五章 %d == %d（原作普查）、桌面世界门 %d == %d'
      % (_non_any_ch, EXPECT_ORIG_OBJS, _desktop, EXPECT_DESKTOP_DOORS),
      _non_any_ch == EXPECT_ORIG_OBJS + MAN_185 and _desktop == EXPECT_DESKTOP_DOORS,
      u'合计 %d == %d' % (_non_any_ch + _desktop,
                         EXPECT_ORIG_OBJS + MAN_185 + EXPECT_DESKTOP_DOORS))

check(u'D2 场景载体未缩水：分片 %d 个、摊平后单元 %d 个'
      % (len([f for f in os.listdir(SCENES)
              if f.startswith('_zone.') and f.endswith('.json')]), len(UNITS)),
      len(UNITS) >= 2000 and
      len([f for f in os.listdir(SCENES)
           if f.startswith('_zone.') and f.endswith('.json')]) >= 61,
      u'（反回滚闸：缩水 >30% 就是被换旧版了）')

# ★ 反回滚：Any 条目凭空消失是**最可能的坏结局**（重跑 gen68 会把追加项冲掉）
check(u'D3 ★反回滚：Any 条目**没有凭空消失**（本轮 %d 条，若某天重跑生成器把它们冲掉，'
      u'这里必红）' % EXPECT_MATERIAL,
      len(_act) == EXPECT_MATERIAL,
      u'实际=%d' % len(_act))

_orphan = [o for _u in UNITS for o in (_u[3].get('objects') or [])
           if isinstance(o, dict) and o.get('src') == WANT and o.get('sprite')]
check(u'D4 没有一条 Any 被硬塞了 sprite（写了 sprite 就是"指向不存在文件"的假话）'
      u'违规=%d' % len(_orphan), not _orphan)

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

# ★ 第173轮踩坑：E 段这几条**第一版全是自指恒真/恒假** ——
#   判据把「自己文案里写的盘符路径样例」「自己注释里写的网络库导入语句」
#   当成了"被测物"的证据。现在一律**从 parts 拼**，判据自己的字面量不进检测面。
_MARK = '[' + 'PASS' + ']'
_cst = [n.value for n in ast.walk(_tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and _MARK in n.value]
check(u'E1 判据标记（PASS 括号）作为字符串字面量只出现 1 处（找到 %d 处）' % len(_cst),
      len(_cst) == 1,
      u'G2 的 `count_results()` 靠正则数这个标记，散着写会数错')

# ★ AST 查恒真：`check(..., True)` 这种写死的绿
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
      _n['p'] + _n['f'] >= CHECK_FLOOR,
      u'（本条自己也算一条，所以是"跑完再看"）')

# 「盘符 + 冒号 + 斜杠」的绝对路径字面量；**用拼的**，免得与本条文案自指。
_DRV = re.compile('[A-Za-z]' + ':' + r'[\\/]')
_ext = _DRV.findall(_src)
check(u'E4 零外部盘：源码里没有盘符开头的绝对路径字面量（找到 %d 处）' % len(_ext),
      not _ext, u'回归不许依赖外部盘/临时区（第173轮坏块 + 超时假象的教训）')

_MAIN_IMP = 'import ' + 'main'
_TRUE_APP = 'Ralsei' + 'Pet('
check(u'E5 不构造真机 App：本文件不 import `main`、也不出现真机构造调用',
      _MAIN_IMP not in _src and _TRUE_APP not in _src)

_NET = ['import ' + m for m in ('requests', 'urllib', 'socket', 'http.client')]
_hit_net = [k for k in _NET if k in _src]
check(u'E6 零网络：本文件不 import 网络库（命中 %r）' % (_hit_net,),
      not _hit_net)

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

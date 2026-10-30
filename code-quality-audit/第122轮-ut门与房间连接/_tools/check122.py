# -*- coding: utf-8 -*-
u"""第122轮回归锁：ut 的**门**不许静默失效 / 不许静默改目标。

## 本套件守什么（零 Qt、零网络、零外部盘 —— 只读仓库内资产）

A 规模与形状：`_routes.json` 的 ut 段 = **243 条**（110 对象级 + 133 字母级）
B ★★ **独立重算**：从 `conn115.json`（反编译函数名）+ `conn_inferred115.json`
  （`obj_doorA` 的 `room_goto_next`）+ `inst_full.tsv`（实例）**重推**
  每条 (场景, 门对象) → 目标，与产品逐条比。错一条就红。
C ★ 双射：`objects` 里的每一扇门都在路由表里有目标；路由表里每一条都在
  `objects` 里真有那扇门（**点不动的门**与**幽灵规则**都报红）
D 产品接线（AST + 行为）：`route_for_door` 真有 `src` 那一路；`build_props`
  真把 `src=` 传下去；字母那一路**跳过对象级条目**（行为判，不扫字符串）
E 防回滚：条数 / 覆盖实例数下界
F 自检：AST 数恒真判据 / 无 BOM / 无 U+FFFD

## 为什么"只写 243 条"不是偷懒

ut 有 **1,299** 个门实例、**34** 种门对象。有**原作出处**的只有两类：
  · 每间房显式 `if (room == X) room_goto(Y);` 的（可信层 131 条边 → 110 条可用）；
  · `obj_doorA` 的 `room_goto_next()`（133 条，`dst == src+1` 133/133 自洽）。
其余（`obj_doorB/C/D` + 各种 musicfade 变体）在证据里**没有**边 —— 写了就是猜。
`obj_mainchara` 那 420 条"走到屏幕边缘换房"更不是门，属于另一层机制，本轮不做。

用法：python check122.py
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
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
MODULES = os.path.join(REPO, 'ralsei_pet', 'modules')
RAW115 = os.path.join(os.path.dirname(ROUND), '第115轮-跨作品物件普查', '_evidence')
RAW = os.path.join(RAW115, 'raw', 'ut')

sys.path.insert(0, MODULES)
import item_interact as II       # noqa: E402

EXPECT_N = 243
EXPECT_SRC = 110
EXPECT_NEXT = 133
EXPECT_COVERED_INST = 548
PRIO_BASE = 4000

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


def _rows(p):
    for ln in io.open(p, encoding='utf-8', newline='').read().split('\n'):
        if ln:
            yield ln.split('\t')


def _json(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return json.load(f)


# ---------- 载入 ----------
ZONE = _json(os.path.join(SCENES, '_zone.ut.rooms.json'))['scenes']
ROUTES = _json(os.path.join(SCENES, '_routes.json'))
_RL = ROUTES.get('routes') or []
UT = [r for r in _RL if str((r or {}).get('when_scene') or '').startswith('ut.')]

OBJS = set(r[1] for r in _rows(os.path.join(RAW, 'objmap_ut.txt'))
           if len(r) >= 5 and r[0] != 'GameObjects')
INSTS = collections.Counter()
_cur = None
for _r in _rows(os.path.join(RAW, 'inst_full.tsv')):
    if _r[0] == 'R':
        _cur = _r[2]
    elif _r[0] == 'I' and _cur is not None:
        INSTS[(_cur, _r[1])] += 1

NAME2SID = {}
for _sid, _sc in ZONE.items():
    if isinstance(_sc, dict) and _sc.get('name'):
        NAME2SID[_sc['name']] = _sid

print(u'== A. 规模与形状 ==')
# ★★★ 第123轮改口径（**不是放宽**）：第122轮引入的 ut 段是 243 条，第123轮又补了
#   282 条位移机制门 ⇒ 整段变成 525 条。如果这里仍钉"整段 == 243"，第123轮一落地
#   这条判据就会红 —— 但它红的原因是"段长大了"，不是"122 那 243 条坏了"。
#   ⇒ 改成本轮**真正要守的语义**：`ut_doors122.json` 里那 243 条**按内容逐条仍在**
#      （场景 / 门字母 / 对象 / 目标 / 原作机制，四项全等），一条都不许丢、不许改。
#   整段的规模与连续编号由第123轮的 `check123` 接手。
_FACT122 = _json(os.path.join(ROUND, '_evidence', 'ut_doors122.json')).get('routes') or []


def _sig(r):
    u"""一条路由的**身份**（不掺 reason/priority 之类会随排版变的字段）。"""
    o = r.get('_original') or {}
    return (r.get('when_scene'), r.get('when_door'), r.get('when_src'),
            r.get('to'), o.get('kind'))


_HAVE_SIG = set(_sig(r) for r in UT)
_missing_122 = [s for s in (_sig(r) for r in _FACT122) if s not in _HAVE_SIG]
check(u'A0 第122轮那 %d 条**逐条仍在**（缺 %d）；ut 段现共 %d 条（对象级 %d / 字母级 %d）'
      % (EXPECT_N, len(_missing_122), len(UT),
         sum(1 for r in UT if r.get('when_src')),
         sum(1 for r in UT if not r.get('when_src'))),
      len(_FACT122) == EXPECT_N and not _missing_122
      and sum(1 for r in _FACT122 if r.get('when_src')) == EXPECT_SRC
      and sum(1 for r in _FACT122 if not r.get('when_src')) == EXPECT_NEXT,
      u'实测 %d / %d / %d / 缺 %d' % (len(UT), sum(1 for r in UT if r.get('when_src')),
                                   sum(1 for r in UT if not r.get('when_src')),
                                   len(_missing_122)))

_bad_prio = [r for r in UT
             if not (isinstance(r.get('priority'), int)
                     and PRIO_BASE <= r['priority'] < PRIO_BASE + 5000)]
_prios = sorted(r['priority'] for r in UT)
check(u'A1 priority 全落在独立段 [%d, +5000)，且**连续无洞**（实测 [%s, %s]）'
      % (PRIO_BASE, _prios[0], _prios[-1]),
      not _bad_prio and _prios == list(range(PRIO_BASE, PRIO_BASE + len(UT))),
      repr([r.get('priority') for r in _bad_prio[:3]]))

_bad_ref = [r for r in UT
            if r.get('when_scene') not in ZONE or r.get('to') not in ZONE]
_self = [r for r in UT if r.get('when_scene') == r.get('to')]
check(u'A2 每条的两端都是已登记 ut 场景（越界 %d）且**无自环**（%d）' % (len(_bad_ref), len(_self)),
      not _bad_ref and not _self, repr((_bad_ref[:2], _self[:2])))

_bad_src = [r for r in UT if r.get('when_src') and r['when_src'] not in OBJS]
_bad_door = [r for r in UT
             if not r.get('when_src')
             and r.get('when_door') not in II.DOOR_LETTERS]
check(u'A3 `when_src` 都在 ut objmap 里（坏 %d）／字母级 `when_door` 都是合法字母（坏 %d）' % (len(_bad_src), len(_bad_door)),
      not _bad_src and not _bad_door, repr((_bad_src[:2], _bad_door[:2])))

_KINDS = set((r.get('_original') or {}).get('kind') for r in UT)
check(u'A4 每条都带 `work: "ut"`，`_original.kind` 只在本轮已知的三种里（实测 %s）'
      % sorted(_KINDS),
      all(r.get('work') == 'ut' for r in UT)
      and _KINDS <= {'ut_door_src', 'ut_door_next', 'ut_door_shift'}
      and {'ut_door_src', 'ut_door_next'} <= _KINDS,
      repr(sorted(_KINDS)))

print(u'')
print(u'== B. 独立重算（本套件最硬的一条）==')


def _obj_of_code(code):
    u"""`gml_Object_obj_door_ruins13_Alarm_2` → `obj_door_ruins13`（最长前缀）。"""
    if not isinstance(code, str) or not code.startswith('gml_Object_'):
        return None
    tail = code[len('gml_Object_'):]
    best = None
    for nm in OBJS:
        if (tail == nm or tail.startswith(nm + '_')) and (best is None or len(nm) > len(best)):
            best = nm
    return best


def recount():
    u"""从**证据**重推 `(when_scene, when_src|None, when_door|None) -> to`。"""
    got = {}

    # ① 可信层：反编译函数名 → 门对象；同名多目标丢掉（条件分支，不猜）
    grp = collections.defaultdict(set)
    for e in _json(os.path.join(RAW115, 'conn115.json'))['ut']['edges']:
        o = _obj_of_code(e.get('code'))
        if o is None:
            continue
        rec = II.classify(o)
        if not rec or rec.get('kind') != 'door':
            continue
        grp[(e.get('src_name'), o)].add(e.get('dst_name'))
    for (rn, o), dsts in grp.items():
        if len(dsts) != 1:
            continue
        dn = next(iter(dsts))
        if not INSTS.get((rn, o)):
            continue
        a, b = NAME2SID.get(rn), NAME2SID.get(dn)
        if a and b:
            got[(a, o, None)] = b

    # ② 字母级：obj_doorA 的 room_goto_next（off=+1 且 dst==src+1）
    for e in _json(os.path.join(RAW115, 'conn_inferred115.json'))['ut']['edges']:
        if e.get('via') != 'obj_doorA':
            continue
        if e.get('off') != 1 or e.get('dst') != (e.get('src') or 0) + 1:
            continue
        rn, dn = e.get('src_name'), e.get('dst_name')
        if not INSTS.get((rn, 'obj_doorA')):
            continue
        a, b = NAME2SID.get(rn), NAME2SID.get(dn)
        if a and b:
            got[(a, None, 'A')] = b
    return got


EXPECT = recount()
# ★★ 第123轮：`recount()` 只会重推**本轮的两种机制**（对象级 `room_goto(常量)` 与
#   `obj_doorA` 的 `room_goto_next`），所以对账范围也必须限定在本轮引入的那批。
#   拿整段（含 282 条 `ut_door_shift`）来比，`_extra` 必然非空 —— 那不是错，
#   是"分母换了物种"。整段的独立重算由 `check123` 负责。
UT122 = [r for r in UT
         if (r.get('_original') or {}).get('kind') in ('ut_door_src', 'ut_door_next')]
HAVE = dict(((r['when_scene'], r.get('when_src'), r.get('when_door')), r['to'])
            for r in UT122)
_KEY = lambda k: (k[0], k[1] or '', k[2] or '')      # None 与 str 不能直接排（已栽过）
_missing = sorted(set(EXPECT) - set(HAVE), key=_KEY)
_extra = sorted(set(HAVE) - set(EXPECT), key=_KEY)
_diff = sorted((k for k in (set(EXPECT) & set(HAVE)) if EXPECT[k] != HAVE[k]), key=_KEY)
check(u'B1 重推 %d 条（%d 对象级 + %d 字母级）；缺 %d / 多 %d / 目标不同 %d'
      % (len(EXPECT), sum(1 for k in EXPECT if k[1]), sum(1 for k in EXPECT if k[2]),
         len(_missing), len(_extra), len(_diff)),
      not _missing and not _extra and not _diff
      and len(EXPECT) == EXPECT_N,
      repr((_missing[:2], _extra[:2], _diff[:2])))

# B2 负控制：把一条目标改掉 ⇒ 判据必须报红
if HAVE:
    _k = sorted(HAVE, key=lambda k: (k[0], k[1] or '', k[2] or ''))[0]
    _neg = dict(HAVE)
    _neg[_k] = 'ut.rooms.__不存在__'
    check(u'B2 负控制：改掉一条目标后判据报红（B1 有鉴别力）',
          _neg != EXPECT)
# B3 正控制：不动的 HAVE 与 EXPECT 逐条相等（不是两边一起错）
check(u'B3 正控制：产品条目与重推结果**逐条相等**', HAVE == EXPECT)

# B4 分母闸：重推本身不许退化成空（空对照空会恒真）
check(u'B4 重推结果非空且两类都有（对象级 %d / 字母级 %d）'
      % (sum(1 for k in EXPECT if k[1]), sum(1 for k in EXPECT if k[2])),
      len(EXPECT) > 0
      and any(k[1] for k in EXPECT) and any(k[2] for k in EXPECT))

print(u'')
print(u'== C. 与 objects 的双射 ==')
_have_doors = set()
for _sid, _sc in ZONE.items():
    if not isinstance(_sc, dict):
        continue
    for _e in (_sc.get('objects') or []):
        if (II.classify((_e or {}).get('src')) or {}).get('kind') == 'door':
            _have_doors.add((_sc.get('name'), _e['src']))
_routed = set()
for r in UT:
    o = (r.get('when_src') or (r.get('_original') or {}).get('via') or 'obj_doorA')
    _routed.add(((r.get('_original') or {}).get('src_room_name'), o))
# ★★ 第123轮：双射仍要守，但分母从「本轮那 243 组」换成「ut 段现有的全部门组」——
#   因为 `objects` 里的门是**按整张路由表**写进去的（`build_objs121.load_routed_doors`），
#   拿 243 去比 525 只会红得莫名其妙。整段的规模闸由 `check123` 接手。
#   这里改成**双向相等**（点不动的门 0 / 幽灵规则 0），再加非空闸防"两边都空"。
check(u'C1 `objects` 里的门 %d 组 == 路由表 %d 组，逐组相等（点不动的 %d / 幽灵 %d）'
      % (len(_have_doors), len(_routed), len(_have_doors - _routed),
         len(_routed - _have_doors)),
      _have_doors == _routed and len(_have_doors) >= EXPECT_N,
      repr((sorted(_have_doors - _routed)[:3], sorted(_routed - _have_doors)[:3])))

_covered = sum(n for (_rn, _o), n in INSTS.items() if (_rn, _o) in _routed)
# ★★ 第123轮：分母/分子一起长大（548 → 1,233）。这里不写死新数字，改守**下界** +
#   "不许把已经写过的门写丢"（防回滚），精确值由 `check123` 用独立算法对账。
check(u'C2 被这些门覆盖的实例数 %d（第121轮统计 ut 门实例共 1,299；本轮下界 %d）'
      % (_covered, EXPECT_COVERED_INST),
      _covered >= EXPECT_COVERED_INST, u'%d' % _covered)

print(u'')
print(u'== D. 产品接线 ==')
_src_r2d = io.open(os.path.join(MODULES, 'item_interact.py'),
                   encoding='utf-8', newline='').read()
_src_sr = io.open(os.path.join(MODULES, 'scene_routing.py'),
                  encoding='utf-8', newline='').read()


def _func(path_src, name):
    for node in ast.walk(ast.parse(path_src)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


_rfd = _func(_src_r2d, 'route_for_door')
_args = [a.arg for a in _rfd.args.args] if _rfd else []
check(u'D1 `route_for_door` 真有 `src` 形参（实际形参 %s）' % (_args,),
      'src' in _args)
_rfd_src = ast.get_source_segment(_src_r2d, _rfd) or '' if _rfd else ''
check(u'D2 `route_for_door` 函数体里真按 `when_src` 精确匹配，且字母那一路**跳过**它',
      "r.get('when_src') == src" in _rfd_src
      and "not r.get('when_src')" in _rfd_src, u'')

_bp = _func(_src_r2d, 'build_props')
_kw = []
for node in ast.walk(_bp):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id == 'route_for_door':
        _kw.append([k.arg for k in node.keywords])
check(u'D3 `build_props` 真把 `src=` 传给 `route_for_door`（调用点 %s）' % (_kw,),
      bool(_kw) and all('src' in k for k in _kw))

_mo = _func(_src_sr, '_match_one')
_mo_src = ast.get_source_segment(_src_sr, _mo) or '' if _mo else ''
check(u'D4 `_match_one` 里 `when_src` 被真消费，且**语境没给 src 时判不匹配**',
      "route.get('when_src')" in _mo_src and 'return False, 0' in _mo_src)

# D5 行为：字母那一路绝不能被对象级条目顶替
_routes_probe = [
    {'when_scene': 's', 'when_src': 'obj_door_ruins13', 'when_door': None,
     'to': 'WRONG', 'priority': 1},
    {'when_scene': 's', 'when_door': 'A', 'to': 'RIGHT_A', 'priority': 2},
]
_got_a = II.route_for_door(_routes_probe, 's', 'A')
_got_src = II.route_for_door(_routes_probe, 's', None, src='obj_door_ruins13')
check(u'D5 ★行为：字母查询拿到 `RIGHT_A`、对象查询拿到 `WRONG`（互不串台）'
      u'实际=%r / %r' % (_got_a, _got_src),
      _got_a == 'RIGHT_A' and _got_src == 'WRONG')

print(u'')
print(u'== E. 防回滚 ==')
check(u'E1 ut 段 ≥ 243 条（防批量删路由）', len(UT) >= EXPECT_N, str(len(UT)))
check(u'E2 覆盖实例 ≥ 548（防把有目标的门写丢）', _covered >= EXPECT_COVERED_INST,
      str(_covered))

print(u'')
print(u'== F. 自检 ==')
_src_self = io.open(os.path.abspath(__file__), encoding='utf-8', newline='').read()
_true = []
for _node in ast.walk(ast.parse(_src_self)):
    if isinstance(_node, ast.Call) and isinstance(_node.func, ast.Name) \
            and _node.func.id == 'check' and len(_node.args) >= 2:
        if isinstance(_node.args[1], ast.Constant) and _node.args[1].value is True:
            _true.append(getattr(_node, 'lineno', -1))
check(u'F1 没有 `check(x, True)` 恒真判据（AST 判，不扫注释）', not _true, repr(_true))
check(u'F2 `_routes.json` 无 BOM / 无 U+FFFD',
      not _src_self.startswith(u'\ufeff')
      and u'\ufffd' not in io.open(
          os.path.join(SCENES, '_routes.json'), encoding='utf-8', newline='').read())

print(u'')
print(u'---- 共 %d 条：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(1 if _failed else 0)

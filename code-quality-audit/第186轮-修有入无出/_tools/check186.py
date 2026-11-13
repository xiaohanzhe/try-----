# -*- coding: utf-8 -*-
u"""第186轮 · ch1 那 5 间「进得去出不来」的房接上出口。

## 这一轮修的是什么

根因**不是"路由表缺边"**，逐间查完是两类：

  ① **房里没有能出去的东西**（物件都没进过场景）
     · `room_dark_chase2`：出口是过场触发器 `obj_lancerslideevent`
       （`if (slidetimer == 540) room_goto_next()`），从没进过 objects；
     · `room_alphysclass`：出口是 **运行时创建**的 `obj_doorB`
       （`obj_classscene_Create_0` 里 `if (global.plot >= 3) instance_create(242, 48, obj_doorB)`），
       静态实例表里没有它 ⇒ 我们从来没建过这扇门。
  ② **边要的条件我们的表达方式没有**
     · `room_forest_maze_susie`：两扇 X 门同场景同字母，靠**门自身 y** 分流
       （`y >= room_height/2` ⇒ 340；实测门在 665 / 0）；
     · `room_cc_prisonelevator`：一扇门四个去向，按 `flag[239]` 分 —— 而那个 flag 的
       语义就是「**你从哪层上来**」（107→0 / 114→1 / 123→2 / 111→3）⇒ 出口 = 回程。
     本轮新增 `when_prev`（来路）表达它。
  ③ 另有一间房的**落点压根没登记**：`room_cc_fountain` 闭泉后
     `room_goto(room_school_unusedroom)`（rid 33），而这间房从来不在
     `_index.json` 里 ⇒ 本轮补登记 `ch1.hometown.school_unusedroom`。

## 分段

A 数据 10 · B 纯函数 8 · C 接线（AST）6 · D 端到端 5 · E 自检 4

★ 环境变量口子（只给 `mutate186.py` 用，判据本身一行不改）：
  `CQ_SCENES_186` / `CQ_MODS_186` / `CQ_MAIN_186` / `CQ_CTRL_186`
"""
import ast
import copy
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(REPO, 'ralsei_pet')
SCENES = os.environ.get('CQ_SCENES_186') or os.path.join(PET, 'assets', 'scenes')
MODS = os.environ.get('CQ_MODS_186') or os.path.join(PET, 'modules')
MAINPY = os.environ.get('CQ_MAIN_186') or os.path.join(PET, 'src', 'main.py')
CTRLPY = os.environ.get('CQ_CTRL_186') or os.path.join(MODS, 'scene_controller.py')
ITEMPY = os.path.join(MODS, 'item_interact.py')
SRPY = os.path.join(MODS, 'scene_routing.py')

ROUTES = os.path.join(SCENES, '_routes.json')
INDEX = os.path.join(SCENES, '_index.json')
ZONE_H = os.path.join(SCENES, '_zone.ch1.hometown.json')
ZONE_D = os.path.join(SCENES, '_zone.ch1.dark_world.json')
WORLDS = os.path.join(SCENES, '_worlds.json')

#: 本轮自己的取证留档（**独立来源**，不是从产品数据抄的）
EVID_CODES = os.path.join(ROUND, '_evidence', 'codes')
EVID_ROOMS = os.path.join(ROUND, '_evidence', 'all_rooms186.json')

MAZE = u'ch1.forest.forest_maze_susie'
ELEV = u'ch1.card_castle.cc_prisonelevator'
CHASE2 = u'ch1.dark_world.dark_chase2'
ALPHYS = u'ch1.hometown.alphysclass'
FOUNTAIN = u'ch1.card_castle.cc_fountain'
NEW = u'ch1.hometown.school_unusedroom'
BEFORE_MAZE = u'ch1.forest.forest_before_maze'
MAZE2 = u'ch1.forest.forest_maze2'
SCHOLLOBBY = u'ch1.hometown.schoollobby'
SCHOOLDOOR = u'ch1.hometown.schooldoor'
OUTSKIRTS = u'ch1.castle_town.castle_outskirts'
PRISON = u'ch1.card_castle.card_castle_prison'
CASTLE1F = u'ch1.card_castle.card_castle_1f'
CASTLE5F = u'ch1.card_castle.card_castle_5f'
UNKNOWN = u'ch1.card_castle.card_castle_unknown'

PRIO_LO, PRIO_HI = 9100, 9110
TOTAL_CHECKS = 33
EXPECT_ROUTES = 2843
EXPECT_NEW_EDGES = 11

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


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def jload(p):
    return json.loads(rd(p))


sys.path.insert(0, MODS)
import scene_routing as SR                       # noqa: E402
import item_interact as II                       # noqa: E402
import scene_system as SS                        # noqa: E402

RAW = jload(ROUTES)
RT = RAW.get('routes') or []
IDX = jload(INDEX)
ZH = jload(ZONE_H).get('scenes') or {}
ZD = jload(ZONE_D).get('scenes') or {}
WL = jload(WORLDS)

ROUTES_OK = SR.load_routes()
IDX_OK = SS.load_index()
SCN = IDX_OK.get('scenes') or {}


def _obj_pos(scene_objs, src):
    return [o.get('pos') for o in (scene_objs or []) if o.get('src') == src]


NEWEDGES = [
    dict(to=BEFORE_MAZE, when_scene=MAZE, when_door='X', door_y=665),
    dict(to=MAZE2, when_scene=MAZE, when_door='X', door_y=0),
    #: ★★★ 第186轮定稿：**删掉了「来路=牢廊」那条**（与下面默认支同门同目标 ⇒ 同门重复，
    #:   check124/171/172 一起报红）。原作 `flag[239]==0` 的落点与默认支相同，
    #:   所以少这一条不减少任何一条原创分支。
    dict(to=CASTLE1F, when_scene=ELEV, when_door='X', when_prev=CASTLE1F),
    dict(to=CASTLE5F, when_scene=ELEV, when_door='X', when_prev=CASTLE5F),
    dict(to=UNKNOWN, when_scene=ELEV, when_door='X', when_prev=UNKNOWN),
    dict(to=PRISON, when_scene=ELEV, when_door='X'),     # 默认支：兜 flag=0 与"来路未知"
    dict(to=OUTSKIRTS, when_scene=CHASE2, when_src='obj_lancerslideevent'),
    dict(to=SCHOLLOBBY, when_scene=ALPHYS, when_door='B', when_src='obj_doorB'),
    dict(to=NEW, when_scene=FOUNTAIN, when_src='obj_fountainkris'),
    dict(to=SCHOOLDOOR, when_scene=NEW, when_door='D'),
    #: ★★★ 第186轮补：`room_schooldoor`(31) 那扇 `obj_doorC` = 下标 +2 → rid 33，
    #:   是上面 D 门（33 −2 = 31）的**互逆**半边，一进一出。
    dict(to=NEW, when_scene=SCHOOLDOOR, when_door='C'),
]


def _match(rule, spec):
    for k in ('to', 'when_scene', 'when_door', 'when_src', 'when_prev'):
        if rule.get(k) != spec.get(k):
            return False
    dy = spec.get('door_y')
    if dy is not None:
        if (rule.get('_original') or {}).get('door_y') != dy:
            return False
    return True


def _find(spec, table=None):
    for r in (table if table is not None else RT):
        if isinstance(r, dict) and _match(r, spec):
            return r
    return None


# ---------------------------------------------------------------------------
#  A 数据 10
# ---------------------------------------------------------------------------
print('')
print('=' * 72)
print(u'A 数据：1 间新场景 / 2 个补的物件 / 11 条新边')
print('=' * 72)

_d = IDX['chapters']['ch1']['areas']['hometown']['scenes']
check(u'A1 `_index.json` 已登记 `school_unusedroom`，房号 33', 
      (_d.get(NEW) or {}).get('original_room_id') == 33, u'%r' % (_d.get(NEW),))

_nobj = len((ZH.get(NEW) or {}).get('objects') or [])
check(u'A2 zone 分片有它，9 个物件（原作 21 实例里取门/标记/事件/可读）', _nobj == 9,
      u'物件数=%d' % _nobj)
check(u'A3 它的 D 门在 (140,180)（取自一手实例表）',
      _obj_pos(ZH.get(NEW, {}).get('objects'), 'obj_doorD') == [[140, 180]],
      u'%r' % (_obj_pos(ZH.get(NEW, {}).get('objects'), 'obj_doorD'),))

_w = (WL.get('rooms') or {}).get('ch1', {}).get('33')
_sc = SS.load_scene(NEW, entry=SCN.get(NEW))
check(u'A4 世界判为 light（`_worlds.json` 已有 33 号房，不用补）',
      _w == 'light' and _sc is not None and SS.world_of_scene(_sc) == 'light',
      u'worlds=%r / world_of_scene=%r' % (_w, SS.world_of_scene(_sc) if _sc else None))

check(u'A5 `alphysclass` 补进了 `obj_doorB` @(242,48)',
      _obj_pos(ZH.get(ALPHYS, {}).get('objects'), 'obj_doorB') == [[242, 48]],
      u'%r' % (_obj_pos(ZH.get(ALPHYS, {}).get('objects'), 'obj_doorB'),))
check(u'A6 `dark_chase2` 补进了 `obj_lancerslideevent` @(280,160)',
      _obj_pos(ZD.get(CHASE2, {}).get('objects'), 'obj_lancerslideevent') == [[280, 160]],
      u'%r' % (_obj_pos(ZD.get(CHASE2, {}).get('objects'), 'obj_lancerslideevent'),))

check(u'A7 路由总数 = %d' % EXPECT_ROUTES, len(RT) == EXPECT_ROUTES, u'实测 %d' % len(RT))

_missing = [s for s in NEWEDGES if _find(s) is None]
check(u'A8 11 条新边全部在表里（逐条按 场景/字母/对象/来路/目标 精确匹配）',
      not _missing, u'缺 %d 条：%r' % (len(_missing), _missing[:3]))

_prios = sorted(r.get('priority') for r in RT if isinstance(r.get('priority'), int)
                and PRIO_LO <= r.get('priority') <= PRIO_HI)
check(u'A9 新边 priority 恰为 %d~%d，且不与其他条目撞号' % (PRIO_LO, PRIO_HI),
      _prios == list(range(PRIO_LO, PRIO_HI + 1)),
      u'实测 %r' % (_prios,))

#: ★ 第一版这条是"全表无重复键" —— **过宽**，实测全表本来就有 **7 组**重复，
#:   全部是 ch5 的 `obj_doorAnyHorz/Vert`（同一间房、同一个无字母门对象、多实例去同一目标，
#:   第174轮已裁定「按实例落边、不按 (源,目标) 去重」）⇒ 那些重复是**原作事实**，不是脏数据。
#:   本键要守的是**本轮这 11 条**的幂等性（重跑 apply186 不会加第二份），所以只数它们。
_keys = [(r.get('when_scene'), r.get('when_door'), r.get('when_src'),
          r.get('when_prev'), r.get('to')) for r in RT]
_cnt = {}
for _k in _keys:
    _cnt[_k] = _cnt.get(_k, 0) + 1
_newkeys = [(s.get('when_scene'), s.get('when_door'), s.get('when_src'),
             s.get('when_prev'), s.get('to')) for s in NEWEDGES]
_dup_new = [k for k in _newkeys if _cnt.get(k) != 1]
check(u'A10 本轮 11 条边各自唯一（幂等：重跑 apply186 不会加第二份）',
      not _dup_new, u'重复 %d 条：%r' % (len(_dup_new), _dup_new[:2]))

# ---------------------------------------------------------------------------
#  B 纯函数 8
# ---------------------------------------------------------------------------
print('')
print('=' * 72)
print(u'B 纯函数：真 `route_for_door` 逐扇门试')
print('=' * 72)


def _door(sid, letter, src, pos, prev=None):
    return II.route_for_door(ROUTES_OK, sid, letter, src=src, pos=pos, prev=prev)


check(u'B1 `maze_susie` 下门 y=665 ⇒ savepoint_relax（rid 90 的场景 id）',
      _door(MAZE, 'X', 'obj_doorX', [280, 665]) == BEFORE_MAZE,
      u'%r' % (_door(MAZE, 'X', 'obj_doorX', [280, 665]),))
check(u'B2 `maze_susie` 上门 y=0 ⇒ maze2（同字母两扇门靠坐标分开）',
      _door(MAZE, 'X', 'obj_doorX', [280, 0]) == MAZE2,
      u'%r' % (_door(MAZE, 'X', 'obj_doorX', [280, 0]),))

_four = [_door(ELEV, 'X', 'obj_doorX_musfade', [280, 460], prev=p) for p in
         (PRISON, CASTLE1F, CASTLE5F, UNKNOWN)]
check(u'B3 电梯四分支按来路各回各家', _four == [PRISON, CASTLE1F, CASTLE5F, UNKNOWN],
      u'%r' % (_four,))
check(u'B4 电梯无来路 ⇒ 默认支（`global.flag` 缺省 0 ⇒ 回牢廊）',
      _door(ELEV, 'X', 'obj_doorX_musfade', [280, 460]) == PRISON,
      u'%r' % (_door(ELEV, 'X', 'obj_doorX_musfade', [280, 460]),))
check(u'B5 `dark_chase2` 滑行事件 ⇒ castle_outskirts（rid 43→44，不是 chase1）',
      _door(CHASE2, None, 'obj_lancerslideevent', [280, 160]) == OUTSKIRTS,
      u'%r' % (_door(CHASE2, None, 'obj_lancerslideevent', [280, 160]),))
check(u'B6 `alphysclass` 运行时的 B 门 ⇒ schoollobby（rid 30 −1 = 29）',
      _door(ALPHYS, 'B', 'obj_doorB', [242, 48]) == SCHOLLOBBY,
      u'%r' % (_door(ALPHYS, 'B', 'obj_doorB', [242, 48]),))
check(u'B7 `cc_fountain` 闭泉 ⇒ 新场景（rid 33）',
      _door(FOUNTAIN, None, 'obj_fountainkris', [300, 260]) == NEW,
      u'%r' % (_door(FOUNTAIN, None, 'obj_fountainkris', [300, 260]),))
check(u'B8 新场景自己那扇 D 门 ⇒ schooldoor（−2）',
      _door(NEW, 'D', 'obj_doorD', [140, 180]) == SCHOOLDOOR,
      u'%r' % (_door(NEW, 'D', 'obj_doorD', [140, 180]),))

# ---------------------------------------------------------------------------
#  C 接线（AST）6
# ---------------------------------------------------------------------------
print('')
print('=' * 72)
print(u'C 接线：`when_prev` 这一路**真的**从宿主走到查表')
print('=' * 72)


def _ast(p):
    return ast.parse(rd(p))


def _func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def _calls(node, fname, want_kw=None):
    """`node` 里对 `fname` 的调用中，带 `want_kw` 关键字的那些。"""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            fn = n.func
            nm = fn.id if isinstance(fn, ast.Name) else getattr(fn, 'attr', None)
            if nm != fname:
                continue
            kws = {k.arg for k in n.keywords if k.arg}
            if want_kw is None or want_kw in kws:
                out.append(n.lineno)
    return out


_ti = _ast(ITEMPY)
_rfd = _func(_ti, 'route_for_door')
_args = [a.arg for a in _rfd.args.args] if _rfd else []
check(u'C1 `route_for_door` 有 `prev` 形参', 'prev' in _args, u'形参=%r' % (_args,))
_bp = _func(_ti, 'build_props')
_bp_args = [a.arg for a in _bp.args.args] if _bp else []
check(u'C2 `build_props` 有 `prev` 形参', 'prev' in _bp_args, u'形参=%r' % (_bp_args,))
check(u'C3 `build_props` 里调 `route_for_door` 时**传了** `prev=`',
      _calls(_bp, 'route_for_door', 'prev') if _bp else [],
      u'行号=%r' % (_calls(_bp, 'route_for_door', 'prev') if _bp else [],))

_tm = _ast(MAINPY)
_dec = []
for n in ast.walk(_tm):
    if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) \
            and n.value.value is None:
        for t in n.targets:
            if isinstance(t, ast.Attribute) and t.attr == '_scene_prev':
                _dec.append(n.lineno)
check(u'C4 `main.py` **预声明**了 `self._scene_prev`（不预声明 ⇒ 状态劈两份）',
      bool(_dec), u'行号=%r' % (_dec,))
_reb = _func(_tm, '_rebuild_item_props')
check(u'C5 `_rebuild_item_props` 调 `build_props` 时传了 `prev=`',
      _calls(_reb, 'build_props', 'prev') if _reb else [],
      u'行号=%r' % (_calls(_reb, 'build_props', 'prev') if _reb else [],))

_tc = _ast(CTRLPY)
_sw = _func(_tc, 'switch')
check(u'C6 `SceneController.switch` 会写 `_scene_prev`',
      [n.lineno for n in ast.walk(_sw)
       if isinstance(n, ast.Attribute) and n.attr == '_scene_prev'] if _sw else [],
      u'行号=%r' % ([n.lineno for n in ast.walk(_sw)
                    if isinstance(n, ast.Attribute) and n.attr == '_scene_prev']
                   if _sw else [],))

# ---------------------------------------------------------------------------
#  D 端到端 5
# ---------------------------------------------------------------------------
print('')
print('=' * 72)
print(u'D 端到端：真 `build_props` / 负控制（拆掉来路分流必报红）')
print('=' * 72)


def _props(sid, prev=None):
    sc = SS.load_scene(sid, entry=SCN.get(sid))
    if sc is None:
        return []
    return II.build_props(sc, 'ch1', 'dark', routes=ROUTES_OK, prev=prev,
                          on_enter=lambda t, d=None: True)


def _targets(props):
    return [getattr(p, 'target_scene', None) for p in props
            if getattr(p, 'kind', '') == 'door']


_d_ok = True
_d_msg = []
for _sid, _prev, _want in ((MAZE, None, [BEFORE_MAZE, MAZE2]),
                           (CHASE2, None, [OUTSKIRTS]),
                           (ALPHYS, None, [SCHOLLOBBY]),
                           (FOUNTAIN, None, [NEW]),
                           (NEW, None, [SCHOOLDOOR])):
    _got = _targets(_props(_sid, _prev))
    if _got != _want:
        _d_ok = False
        _d_msg.append((_sid, _got, _want))
check(u'D1 五间房的 `DoorProp` 目标与证据一致（真跑 build_props）', _d_ok,
      u'%r' % (_d_msg[:3],))

_top = _targets(_props(ELEV, CASTLE5F))
check(u'D2 电梯：来路=五层时，建出来的那扇门目标就是五层', _top == [CASTLE5F],
      u'%r' % (_top,))
_ton = _targets(_props(ELEV, None))
check(u'D3 电梯：无来路时建出来的门走默认支', _ton == [PRISON], u'%r' % (_ton,))

# ★★★ 负控制 A：**删掉** prev=一层 那条 ⇒ 应落回默认支（而不是一层的那个目标）。
_rt2 = [dict(r) for r in ROUTES_OK['routes']
        if not (r.get('when_scene') == ELEV and r.get('when_prev') == CASTLE1F)]
_got2 = II.route_for_door(_rt2, ELEV, 'X', src='obj_doorX_musfade', pos=[280, 460],
                          prev=CASTLE1F)
# ★★★ 负控制 B：把三条 prev 规则的 `when_prev` **全拆掉** ⇒ 它们退化成普通候选，
#   按升序裁决由 priority 最小的 9102（回一层）赢 ⇒ **来路=五层 也拿不到五层**。
#   ★ 靶子换过一次：定稿删掉「来路=牢廊」那条之后，ELEV 的最小 priority 已不是回牢廊，
#     再断言"拆掉后落牢廊"就成了**恒假**（判据过时），所以靶子改成"五层拿不到五层"
#     —— 这才是这一路真正在保证的事：没有 `when_prev`，四支必然塌成一支。
_rt3 = []
for r in ROUTES_OK['routes']:
    r2 = dict(r)
    if r2.get('when_scene') == ELEV and r2.get('when_prev'):
        r2.pop('when_prev')
    _rt3.append(r2)
_got3 = II.route_for_door(_rt3, ELEV, 'X', src='obj_doorX_musfade', pos=[280, 460],
                          prev=CASTLE5F)
check(u'D4 ★负控制：删掉「来路=一层」那条 ⇒ 落到默认支（不是一层）',
      _got2 == PRISON and _got2 != CASTLE1F, u'%r' % (_got2,))
check(u'D5 ★负控制：把三条 `when_prev` 全拆掉 ⇒ 来路=五层 也拿不到五层（塌成最小 priority 那支）',
      _got3 == CASTLE1F and _got3 != CASTLE5F, u'%r' % (_got3,))

# ---------------------------------------------------------------------------
#  E 自检 4
# ---------------------------------------------------------------------------
print('')
print('=' * 72)
print(u'E 自检：条数固定 / 不 import 宿主 / 不写死盘路径 / 分母闸')
print('=' * 72)

_SELF = rd(os.path.abspath(__file__))
_imp = [n.names[0].name for n in ast.walk(ast.parse(_SELF))
        if isinstance(n, ast.Import) and n.names]
_impfrom = [n.module for n in ast.walk(ast.parse(_SELF))
            if isinstance(n, ast.ImportFrom) and n.module]
_ralsei = [n.lineno for n in ast.walk(ast.parse(_SELF))
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
           and n.func.id == 'RalseiPet']
check(u'E1 不 import `main` / 不构造 `RalseiPet`',
      'main' not in _imp and 'main' not in _impfrom and not _ralsei,
      u'调用行=%r' % (_ralsei,))

_ABS = re.compile(r'^[A-Za-z]:[\\/]')
_hard = [n.value for n in ast.walk(ast.parse(_SELF))
         if isinstance(n, ast.Constant) and isinstance(n.value, str)
         and _ABS.match(n.value)]
check(u'E2 判据自己不写死外部盘路径（AST 常量扫描）', not _hard, u'命中=%r' % (_hard,))

#: ★ 分母闸：新边必须真是 11 条 —— 若扫描/匹配逻辑静默失效（比如 `_match`
#:   全返 False），下面这条会红，而不是"11 条都不在"被当成正常。
_found = [s for s in NEWEDGES if _find(s) is not None]
check(u'E3 分母闸：按同一套匹配能找回 11 条（扫描失效会红）',
      len(_found) == EXPECT_NEW_EDGES, u'找回 %d 条' % len(_found))

check(u'E4 条数固定 %d' % TOTAL_CHECKS, _n['p'] + _n['f'] == TOTAL_CHECKS - 1,
      u'实测 %d' % (_n['p'] + _n['f']))

print('')
print('=' * 72)
print(u'合计：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _bad:
    print(u'★ 失败项：')
    for d in _bad:
        print(u'   %s' % d)
print('=' * 72)
sys.exit(0 if _n['f'] == 0 else 1)

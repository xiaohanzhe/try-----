# -*- coding: utf-8 -*-
u"""第184轮 · **门控层**：同一扇门随剧情状态改去向（`traffic_3` 的 W 门这一扇）。

## 要解决什么

第183轮收尾时留了一条 `[NOTE]`：`7123 → dw_city_moss` 被 `7121` 无条件遮挡
⇒ **`dw_city_moss` 永远不可达**。根因不是边写错，而是路由表里一条规则只能表达
"从哪个场景的哪扇门出去 → 一个固定目标"，而原作 `obj_doorw_musfade.Alarm_2` 是：

    if (global.flag[917] == 0 && scr_sideb_get_phase() == 0)
        room_goto(room_dw_city_dog_traffic);
    else {
        var man_room = scr_sideb_get_phase() == 0 && global.flag[917] < 2
                       && global.flag[918] == 0 && ceil(random(50)) == 50;
        if (man_room) room_goto(room_dw_city_man);
        else          room_goto(room_dw_city_moss);
    }

**同一扇门，剧情早期去 A、之后去 B**。本轮只做 `dog_traffic` / `moss` 这两支
（`man` 那支是 1/50，第182轮已由 `_hidden_rooms[1]` 承担，与门控无关）。

## 形状：顶层 `_gates`，**不碰 route 对象**

塞进 route 对象要给 7121/7123 各加字段，而 `check169` 的 `_original` 指纹、
`check176` 的规范化 sha1 都对 route **逐字段**敏感 ⇒ 会撞一排与本轮无关的老锁。
顶层只影响"统计文件字节/CRLF 数"的纯回显套件（A7 专门钉"没有任何 route 带门控键"）。

## 三处口径（都是用户裁定的，写错就白干）

1. **状态源 = `plot_mark`**（复用现成设施，不新造文件）。它此前**零调用方**，
   等于死设施 ⇒ 本轮是它的第一处真实消费（C7 钉这个）。
2. **记账时机 = 真站进去才写**（与第182轮隐藏房同口径 `cur != sid`）：
   `switch` 失败 / 过渡被取消都不算。按"意图"记账会让门控**提前换支**且不报错。
3. **只代理"去过 / 没去过"**：原件里 `flag[917]` 是**次数**（`< 2` 才会继续掷 man），
   布尔表达不了那层精度 —— 如实记在 `_original.note` 里，不假装保住了。

## 分段

A 数据 8 · B 纯函数/加载器 10 · C 接线（AST）7 · D 端到端（真 build_props）4 · E 自检 5

★ 环境变量口子（只给 `mutate184.py` 用，判据本身一行不改）：
  `CQ_ROUTES_184` / `CQ_MODS_184` / `CQ_MAIN_184` / `CQ_APPLY184_184`
  ⚠️ `CQ_ROUTES_184` 指到的文件**必须**叫 `_routes.json`（产品侧 `load_routes()`
  是按目录拼文件名的，B1/B2 走的是产品真身）。
"""
import ast
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PET, 'assets', 'scenes')
MODS = os.environ.get('CQ_MODS_184') or os.path.join(PET, 'modules')
ROUTES = os.environ.get('CQ_ROUTES_184') or os.path.join(SCENES, '_routes.json')
MAINPY = os.environ.get('CQ_MAIN_184') or os.path.join(PET, 'src', 'main.py')
APPLY184 = os.environ.get('CQ_APPLY184_184') or os.path.join(HERE, 'apply184.py')

#: 第170轮 `applied170.json` 里那三条分支的 `cond` 原文（**独立来源**，用于 A8 对账）
APPLIED170 = os.path.join(REPO, 'code-quality-audit', u'第170轮-门实例级落点',
                          '_evidence', 'applied170.json')

TR = u'ch2.cyber_city.dw_city_traffic_3'
DOG = u'ch2.cyber_city.dw_city_dog_traffic'
MOSS = u'ch2.cyber_city.dw_city_moss'
MAN = u'ch2.cyber_city.dw_city_man'
MARK = u'ch2.city.dog_traffic'
LETTER = u'W'

#: ★ 第185轮引账：本轮当天是 2830；第185轮加了 2 条森林手工边
#:   （`area5 --X--> forest_starwalker` 9001、`room_man --X--> forest_bake_sale` 9002）。
#:   ★ 不把原数字改成 2832：那个数字的含义是“第184轮当天的路由数”，
#:     改它等于把历史读数也拉到今天，下一轮又要再改一次。
_ADDED_185 = 2
EXPECT_ROUTES = 2830 + _ADDED_185
EXPECT_GATES = 1
TOTAL_CHECKS = 34

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


def rdb(p):
    with io.open(p, 'rb') as f:
        return f.read()


def jload(p):
    return json.loads(rd(p))


def _sig(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
#  准备：真·产品加载器 + 纯函数
# ---------------------------------------------------------------------------
sys.path.insert(0, MODS)
import scene_routing as SR          # noqa: E402
import item_interact as II          # noqa: E402

RAW = jload(ROUTES)
GATES_RAW = RAW.get('_gates')
ROUTES_L = RAW.get('routes') or []
TABLE = SR.load_routes(os.path.dirname(ROUTES))
GATES = TABLE.get('gates') or []

INDEX = jload(os.path.join(SCENES, '_index.json'))


def _flatten_scenes(obj, acc=None):
    u"""把 `_index.json` 里**任意嵌套**的场景登记摊平（章 → 区域 → 场景）。

    ★ 不按固定层数取：`chapters` 的下面是 `areas`，`areas` 的下面才是 `scenes`，
      中间还可能加层。**只认形状**（key 里带 ≥2 个点、value 是 dict），
      这样将来索引多包一层也不会让 A6 变成"扫了个空表"的假绿。
    """
    if acc is None:
        acc = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.count('.') >= 2 and isinstance(v, dict):
                acc.setdefault(k, v)
            _flatten_scenes(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _flatten_scenes(v, acc)
    return acc


IDX = _flatten_scenes(INDEX)


def _gate0():
    return GATES[0] if GATES else {}


G0 = _gate0()


# ---------------------------------------------------------------------------
#  A 数据：`_gates` 这一条表
# ---------------------------------------------------------------------------
check(u'A1 顶层 `_gates` 存在且恰好 %d 条' % EXPECT_GATES,
      isinstance(GATES_RAW, list) and len(GATES_RAW) == EXPECT_GATES,
      u'实际 %r' % (len(GATES_RAW) if isinstance(GATES_RAW, list) else GATES_RAW))

_KEYS = (u'when_scene', u'when_door', u'mark', u'set_mark_when_arrive',
         u'to_when_unset', u'to_when_set', u'_original')
_miss = [k for k in _KEYS if k not in (GATES_RAW[0] if GATES_RAW else {})]
check(u'A2 七个必备键齐全（缺一个就不是一条完整的门控）',
      _miss == [], u'缺 %r' % (_miss,))

_g = GATES_RAW[0] if GATES_RAW else {}
check(u'A3 值对：管的是 (traffic_3, W)，未记→dog_traffic / 已记→moss',
      _g.get('when_scene') == TR and _g.get('when_door') == LETTER
      and _g.get('to_when_unset') == DOG and _g.get('to_when_set') == MOSS
      and _g.get('mark') == MARK,
      u'实测 %r' % ({k: _g.get(k) for k in (u'when_scene', u'when_door', u'mark',
                                            u'to_when_unset', u'to_when_set')},))

check(u'A4 记账点 == 未记那一支的目的地（"去了 dog_traffic 才算过完那一拍"）',
      _g.get('set_mark_when_arrive') == _g.get('to_when_unset') == DOG,
      u'set_mark_when_arrive=%r / to_when_unset=%r'
      % (_g.get('set_mark_when_arrive'), _g.get('to_when_unset')))

_edges = [r for r in ROUTES_L if isinstance(r, dict) and r.get('when_scene') == TR
          and r.get('when_door') == LETTER]
_tgts = set(r.get('to') for r in _edges)
check(u'A5 两个目标**本来就有边**（门控不是凭空造路）',
      {DOG, MOSS} <= _tgts, u'同门现存目标 %r' % (sorted(_tgts),))

_idx_ok = [s for s in (DOG, MOSS) if s in IDX]
check(u'A6 两个目标都在 `_index.json` 登记成场景（否则切过去必失败）',
      len(_idx_ok) == 2, u'登记到 %r / 缺 %r'
      % (len(_idx_ok), [s for s in (DOG, MOSS) if s not in IDX]))

_GATEY = (u'when_gate', u'gate', u'when_flag', u'when_phase')
_dirty = [r for r in ROUTES_L if isinstance(r, dict)
          and any(k in r for k in _GATEY)]
check(u'A7 ★★ 本轮**没有**动任何 route 对象（带门控键的规则 0 条）；routes == 2830 + %d（第185轮新增账）= %d 条'
      % (_ADDED_185, EXPECT_ROUTES),
      _dirty == [] and len(ROUTES_L) == EXPECT_ROUTES,
      u'脏规则 %d 条 / routes=%d' % (len(_dirty), len(ROUTES_L)))

#: 第170轮留档的三条 cond 原文（独立来源）
def _walk_prio(obj, acc):
    u"""把 JSON 里**任意深度**的 `{prio, cond}` 记录收进来（不看外层是 dict 还是 list）。"""
    if isinstance(obj, dict):
        if isinstance(obj.get('prio'), int) and 'cond' in obj:
            acc.setdefault(obj['prio'], obj.get('cond'))
        for v in obj.values():
            _walk_prio(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _walk_prio(v, acc)
    return acc


_AP = {}
try:
    _walk_prio(jload(APPLIED170), _AP)
except Exception:
    _AP = {}
_og = _g.get('_original') or {}
_ap_ok = (_AP.get(7121) == _og.get('cond_unset')
          and _AP.get(7123) == _og.get('cond_set')
          and _AP.get(7122) == _og.get('cond_man'))

_check_missing = None
check(u'A8 `_original` 的三个 cond 与第170轮留档**逐字相同**（不是我誊的）',
      _ap_ok, u'留档 %r\n         本表 %r'
      % ({k: _AP.get(k) for k in (7121, 7122, 7123)},
         {k: _og.get(k) for k in (u'cond_unset', u'cond_man', u'cond_set')}))


# ---------------------------------------------------------------------------
#  B 纯函数 / 加载器
# ---------------------------------------------------------------------------
check(u'B1 产品 `load_routes()` 真的把 `_gates` 带出来了（1 条）',
      len(GATES) == EXPECT_GATES, u'gates=%d' % len(GATES))

_HIT = SR.gate_for(GATES, TR, LETTER)
check(u'B2 `gate_for(traffic_3, W)` 命中', isinstance(_HIT, dict), u'实测 %r' % (_HIT,))

check(u'B3 负控制：换个场景（`traffic_4`）必须不命中',
      SR.gate_for(GATES, u'ch2.cyber_city.dw_city_traffic_4', LETTER) is None)

check(u'B4 负控制：同场景换扇门（`A`）必须不命中',
      SR.gate_for(GATES, TR, u'A') is None)

check(u'B5 ★★ 没给门字母 ⇒ **不套门控**（否则"随便哪个门出门都去 moss"）',
      SR.gate_for(GATES, TR, None) is None)

_t_unset = SR.gate_target(_HIT, None)
_t_set = SR.gate_target(_HIT, lambda m: m == MARK)
check(u'B6 未记→%s / 已记→%s，且两者**必须不同**' % (DOG.split('.')[-1], MOSS.split('.')[-1]),
      _t_unset == DOG and _t_set == MOSS and _t_unset != _t_set,
      u'未记=%r 已记=%r' % (_t_unset, _t_set))


def _boom(_m):
    raise RuntimeError(u'查账炸了')


_ok_boom = True
try:
    _t_boom = SR.gate_target(_HIT, _boom)
except Exception:
    _ok_boom = False
    _t_boom = None
check(u'B7 查账抛异常 ⇒ 当"没记"（不向上抛、也不擅自改道）',
      _ok_boom and _t_boom == DOG, u'抛了吗 %r / 结果 %r' % (not _ok_boom, _t_boom))

check(u'B8 `is_done` 传 None ⇒ 当"没记"（fail-open，等于第183轮的行为）',
      SR.gate_target(_HIT, None) == DOG)

_m_arrive = SR.gate_marks_on_arrival(GATES, DOG)
check(u'B9 到了 %s 才该记账；到 %s 不记' % (DOG.split('.')[-1], TR.split('.')[-1]),
      _m_arrive == [MARK] and SR.gate_marks_on_arrival(GATES, TR) == []
      and SR.gate_marks_on_arrival(GATES, u'ch1.kris_room.kris_s_room') == [],
      u'到 dog=%r 到 traffic_3=%r' % (_m_arrive, SR.gate_marks_on_arrival(GATES, TR)))

_ov_unset = SR.gate_overrides(GATES, TR, None)
_ov_set = SR.gate_overrides(GATES, TR, lambda m: m == MARK)
check(u'B10 `gate_overrides` 打成 `{字母: 目标}`：未记 %r / 已记 %r'
      % (_ov_unset, _ov_set),
      _ov_unset == {LETTER: DOG} and _ov_set == {LETTER: MOSS}
      and SR.gate_overrides(GATES, u'ch1.kris_room.kris_s_room', lambda m: True) == {})


# ---------------------------------------------------------------------------
#  C 接线（全 AST，不 import main —— import 会构造真机）
# ---------------------------------------------------------------------------
II_SRC = rd(os.path.join(MODS, 'item_interact.py'))
II_TREE = ast.parse(II_SRC)
MAIN_SRC = rd(MAINPY)
MAIN_TREE = ast.parse(MAIN_SRC)


def _func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _args(node):
    if node is None:
        return []
    return [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]


_bp = _func(II_TREE, 'build_props')
check(u'C1 `build_props` 有 `door_overrides` 形参',
      'door_overrides' in _args(_bp), u'形参 %r' % (_args(_bp),))

_uses = [n for n in ast.walk(_bp or ast.parse('')) if isinstance(n, ast.Call)
         and isinstance(n.func, ast.Attribute) and n.func.attr == 'get'
         and isinstance(n.func.value, ast.Name) and n.func.value.id == 'door_overrides']
#: ★ 只判"读过这张表"不够 —— `_ov = door_overrides.get(...)` 之后如果**没有**
#:   `tgt = _ov`，表读了等于没读（第184轮变异 M11 就是把这个分支废掉）。
#:   所以再加一条：函数体里必须出现 `tgt = _ov` 这个赋值本身。
_apply = [n for n in ast.walk(_bp or ast.parse(''))
          if isinstance(n, ast.Assign) and isinstance(n.value, ast.Name)
          and n.value.id == '_ov'
          and any(isinstance(t, ast.Name) and t.id == 'tgt' for t in n.targets)]
check(u'C2 ★★ 门分支真的读了这张表**并且**把结果用上了'
      u'（`door_overrides.get(...)` + `tgt = _ov`）',
      len(_uses) >= 1 and len(_apply) >= 1,
      u'读取 %d 处 / 赋值 %d 处' % (len(_uses), len(_apply)))

_dep = []
for _n2 in ast.walk(II_TREE):
    _mods = []
    if isinstance(_n2, ast.Import):
        _mods = [(a.name or u'') for a in _n2.names]
    elif isinstance(_n2, ast.ImportFrom):
        _mods = [_n2.module or u'']
    for _m in _mods:
        if _m.split('.')[0] in ('scene_routing', 'plot_mark'):
            _dep.append((getattr(_n2, 'lineno', 0), _m))
check(u'C3 ★★ `item_interact` **没有** import `scene_routing` / `plot_mark`'
      u'（零依赖 L1，G1 硬闸）',
      _dep == [], u'命中 %r' % (_dep,))

_rip = _func(MAIN_TREE, '_rebuild_item_props')
_rip_calls = [n for n in ast.walk(_rip or ast.parse('')) if isinstance(n, ast.Call)]
_call_gates = [c for c in _rip_calls
               if isinstance(c.func, ast.Attribute) and c.func.attr == 'gate_overrides']
_kw_ov = []
for c in _rip_calls:
    if isinstance(c.func, ast.Attribute) and c.func.attr == 'build_props':
        _kw_ov += [k.arg for k in c.keywords if k.arg == 'door_overrides']
check(u'C4 ★★ 宿主真的求值并**按关键字**传下去（`gate_overrides(...)` + `door_overrides=`）',
      len(_call_gates) >= 1 and _kw_ov == ['door_overrides'],
      u'求值 %d 处 / 关键字 %r' % (len(_call_gates), _kw_ov))

_tc = _func(MAIN_TREE, '_travel_feedback_done')
_order = []
for n in ast.walk(_tc or ast.parse('')):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
        if n.func.attr in ('_commit_hidden_seen', '_commit_gate_marks'):
            _order.append((n.lineno, n.func.attr))
_order.sort()
_seq = [x[1] for x in _order]
check(u'C5 `_travel_feedback_done` 里两处记账都在，且 hidden 在 gate 之前（收尾点唯一）',
      len(_seq) == 2 and _seq[0] == '_commit_hidden_seen'
      and _seq[1] == '_commit_gate_marks', u'实际顺序 %r' % (_seq,))

_cg = _func(MAIN_TREE, '_commit_gate_marks')
_cg_attrs = [n.attr for n in ast.walk(_cg or ast.parse('')) if isinstance(n, ast.Attribute)]
_cg_strs = [n.value for n in ast.walk(_cg or ast.parse('')) if isinstance(n, ast.Constant)
            and isinstance(n.value, str)]
check(u'C6 ★★ 记账判据是"当前场景"（读 `current_scene`），不是"刚走过哪扇门"',
      'current_scene' in _cg_strs and 'gate_marks_on_arrival' in _cg_attrs,
      u'属性 %r / 关键字符串命中 %r'
      % (sorted(set(_cg_attrs))[:8], 'current_scene' in _cg_strs))

_calls_plot = []
for _root, _dirs, _files in os.walk(PET):
    _dirs[:] = [d for d in _dirs if d not in ('__pycache__', '.git')]
    for _f in _files:
        if not _f.endswith('.py'):
            continue
        _p = os.path.join(_root, _f)
        try:
            _t = ast.parse(rdb(_p).decode('utf-8', 'replace'))
        except Exception:
            continue
        for n in ast.walk(_t):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                    and n.func.attr == 'mark_plot_done':
                _calls_plot.append(os.path.relpath(_p, PET))
check(u'C7 ★★ `plot_mark` 不再是死设施：`mark_plot_done` 有真实调用方',
      len(_calls_plot) >= 1, u'调用方 %r' % (_calls_plot,))


# ---------------------------------------------------------------------------
#  D 端到端：真 `build_props`（合成一个只有这扇门的场景）
# ---------------------------------------------------------------------------
_H = II.build_props


def _scene(sid, src=u'obj_doorw_musfade', pos=(301, 600)):
    return {'scene_id': sid, 'objects': [{'src': src, 'pos': list(pos)}]}


def _door_target(**kw):
    props = _H(_scene(TR), u'ch2', u'dark', routes=TABLE, **kw)
    doors = [p for p in props if getattr(p, 'target_scene', None)]
    return doors[0].target_scene if len(doors) == 1 else None


_d1 = _door_target(door_overrides=SR.gate_overrides(GATES, TR, None))
check(u'D1 真 `build_props`（未记）⇒ 门指向 dog_traffic',
      _d1 == DOG, u'实测 %r' % (_d1,))

_d2 = _door_target(door_overrides=SR.gate_overrides(GATES, TR, lambda m: m == MARK))
check(u'D2 真 `build_props`（已记）⇒ 门指向 moss —— **这就是本轮要的效果**',
      _d2 == MOSS, u'实测 %r' % (_d2,))

_d3 = _door_target()
check(u'D3 ★★ 不给 `door_overrides` ⇒ 与第183轮**逐字相同**（priority 口径 → dog_traffic）',
      _d3 == DOG, u'实测 %r' % (_d3,))

_d4 = _door_target(door_overrides={u'A': u'ch1.kris_room.kris_s_room'})
check(u'D4 负控制：覆盖表里塞个**无关字母** ⇒ 这扇 W 门一个字母都不许被顶掉',
      _d4 == DOG, u'实测 %r' % (_d4,))


# ---------------------------------------------------------------------------
#  E 自检
# ---------------------------------------------------------------------------
_BOMS = [p for p in (ROUTES, MAINPY, os.path.join(MODS, 'scene_routing.py'), APPLY184)
         if os.path.isfile(p) and rdb(p)[:3] == b'\xef\xbb\xbf']
_FFFD = [p for p in (MAINPY, os.path.join(MODS, 'scene_routing.py'),
                     os.path.join(MODS, 'item_interact.py'))
         if u'\ufffd' in rd(p)]
check(u'E1 无 BOM / 无 U+FFFD', not _BOMS and not _FFFD,
      u'BOM %r / FFFD %r' % (_BOMS, _FFFD))

_SELF = rd(os.path.abspath(__file__))
_SELF_TREE = ast.parse(_SELF)
_const = []
for n in ast.walk(_SELF_TREE):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'check':
        if len(n.args) >= 2 and isinstance(n.args[1], ast.Constant):
            _const.append(n.lineno)
check(u'E2 没有恒真判据（`check(..., <字面量>)` 0 处）',
      _const == [], u'可疑行 %r' % (_const[:5],))

_bad_imp = [n for n in ast.walk(_SELF_TREE)
            if isinstance(n, ast.Import) and any(
                (a.name or '').split('.')[0] == 'main' for a in n.names)]
_bad_new = [n for n in ast.walk(_SELF_TREE)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == 'RalseiPet']
check(u'E3 不 import main / 不构造 RalseiPet（不碰 Qt、不起真机）',
      not _bad_imp and not _bad_new)

#: 外部盘路径：形如 `<字母>:\` 或 `<字母>:/` 的字面量。**白名单**只放本机用户目录，
#: 因为判据里正常不该出现任何盘符 —— 出现了说明"换台机器就跑不了"。
_DRV_RE_WIN = None
_drv = []
for n in ast.walk(_SELF_TREE):
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        v = n.value
        if len(v) >= 3 and v[1] == ':' and v[2] in ('\\', '/') and v[0].isalpha():
            _drv.append(v)
check(u'E4 判据自己**不写死外部盘路径**（机器无关）', _drv == [],
      u'命中 %r' % (_drv[:5],))

_TOTAL = _n['p'] + _n['f'] + 1
check(u'E5 判据条数 == %d（本行执行时 %d 条已跑 + 自己）' % (TOTAL_CHECKS, _TOTAL - 1),
      _TOTAL == TOTAL_CHECKS, u'实测 %d' % _TOTAL)


print('=' * 74)
print(u'合计 %d 条判据  PASS=%d  FAIL=%d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _bad:
    print(u'[BAD ] %r' % (_bad,))
print('=' * 74)

# 收尾说明（不是判据）：本轮**没修**的东西
print(u'[NOTE] 本轮只做 `traffic_3` 这一扇。其余 11 条惰性规则、另外 3 间隐藏房')
print(u'       （ch1 `room_man` / ch3 `dw_ch3_man` / ch4 `dw_churchb_man`）仍是')
print(u'       `gate_unresolved`，继续只登记不投用。')

sys.exit(0 if _n['f'] == 0 else 1)

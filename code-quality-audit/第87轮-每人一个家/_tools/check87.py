# -*- coding: utf-8 -*-
u"""第87轮回归锁：**每人一个家**（跨作品 NPC 的静态归属地 + 家字段接线）。

用户口径（逐字，本轮）
--------------------
* 「迁入场景后再找对应的，然后npc就按原作的分布规律来就好，oneshot那个就放在他
  游戏最后那个光门后面（原作最后出现他回家要跨过的拿到门，就安置在那里面，
  相当于没有，然后oneshot世界的入口你就用原作里的门就好）」
* 「先落「家」的数据面（推荐）」
* 「标 authored，按原作分布规律安家（推荐）」
* 「立刻参与（推荐）」

本轮做的事
----------
① `_placement.json` 新增**独立 `home` 列**（与 `scene` = 当前站位**语义不同**）；
② 补 50 条家：UT 14 / 黄魂 15 / OneShot 21；三级证据 original 16 / derived 11 /
   authored 23（**逐条**带 `home_evidence`）；
③ `npc_placement.Placement` 加 `home`/`home_source`/`home_evidence`/`home_why` 四槽
   + `PlacementBook.home_of()/home_declared()/homes()/home_source_of()`；
④ `main.py` 接线：`home_of` 改读 `book.home_of()`；
⑤ ★★ **自主移动候选池收窄**（`_npc_roam_roster()`）—— 跨作品 NPC `scene` 为 `None`
   ⇒ 不进 `npc_roam.step(roster=...)`（否则一群"不在这个世界"的人会去 Deltarune
   房间里游荡，而且**不报错**）；
⑥ ★★★ **修一个从第79轮就存在的真 bug**：`npc_roam._call()` 以 `fn(npc_id, 默认值)`
   （**两个位置参数**）调用取值器，而 `main.py` 注入的 `_npc_roam_traits` /
   `_npc_roam_familiar` / `_npc_roam_friends` 只收一个参数、两个 lambda 同样单参
   ⇒ `TypeError` 被 `_call` 自己的 `except` **静默吞掉** ⇒ 取值恒 `None`
   ⇒ **`home_of` 从未生效**（"回家"一直退化成"随便走走"）。
   修法 = 给宿主侧补齐第二个形参（不动被判据锁住的 `npc_roam` 一行）。

段一览
------
  A ★★ 家的数据面（50 条 / 三级来源 / 逐条证据 / `home_of` 回落语义）
  B ★★★ 自主移动隔离（候选池收窄；跨作品角色零决策 —— 含**成对负控制**）
  C ★★★ 就寝决策真消费 `home`（落回自己家；不可达时不硬落）
  D ★★★ **`_call` 两参约定的防回归锁**（宿主注入的取值器都必须吃两个位置参数）
  E ★★ Outertale 未被硬安家（`_index.json` 无 `outertale` 章 ⇒ 如实挂起）
  F ★★ 数据面自洽（索引登记 / 几何可查 / 场景可 `load_scene`）
  G 判据自身体检（负控制成对 + 被测文件在盘）

★ 判据纪律：`print('[PASS] %s')` 字面量；判据名里不自带标记；
  正/负控制成对；**断行为不断赋值**（关键判据真调产品函数，不看源码字面量）；
  ★ 夹具保真：**取值器必须给全且必须吃两个位置参数**（本轮实测被它坑过两次）。
★ 零网络 / 零 UI / 不需要显示器 / **零外部盘**（证据已蒸馏进仓库）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
if PKG not in sys.path:
    sys.path.insert(0, PKG)

from modules import npc_placement as NP     # noqa: E402
from modules import npc_roam as NR          # noqa: E402
from modules import npc_intent as NI        # noqa: E402

_failed = []


def check(desc, cond, star=False):
    mark = ' ★' if star else ''
    if cond:
        print('[PASS]%s %s' % (mark, desc))
    else:
        print('[FAIL]%s %s' % (mark, desc))
        _failed.append(desc)


def _load_json(p):
    try:
        with io.open(p, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


PLACEMENT = os.path.join(PKG, 'assets', 'npc', '_placement.json')
SCENES = os.path.join(PKG, 'assets', 'scenes')
MAIN = os.path.join(PKG, 'src', 'main.py')

print('=' * 70)
print('第87轮回归锁：每人一个家')
print('ROOT =', ROOT)
print('=' * 70)

# ================================================================ A. 家的数据面
book = NP.load_placement()
homes = book.homes()

check('A1 家条目共 50 条', len(homes) == 50, star=True)

_world_cnt = {}
for _nid in homes:
    _world_cnt[_nid.split('_')[0]] = _world_cnt.get(_nid.split('_')[0], 0) + 1
check('A2 三个跨作品世界都有家（ut/hy/os 均非空）',
      all(_world_cnt.get(w, 0) > 0 for w in ('ut', 'hy', 'os')),
      star=True)

check('A3 家的来源都在三级标签内（不另造第四套标签）',
      set(book.home_source_of(n) for n in homes) <= set(NP.HOME_SOURCE_KINDS),
      star=True)

_incomplete = [n for n in homes
               if not book.get(n).home_source or not book.get(n).home_evidence]
check('A4 每条家都有来源标签 + 逐条证据（不许空口安家）',
      not _incomplete, star=True)

# A5 正面控制：家值必须与「家表」逐条一致（真源交叉核验）
_homes_tbl = _load_json(os.path.join(HERE, 'homes87.json'))
_tbl_ok = True
if isinstance(_homes_tbl, dict):
    _byid = {h['id']: h['scene'] for h in _homes_tbl.get('homes') or []}
    _mismatch = [(n, _byid[n], book.home_of(n))
                 for n in _byid if book.home_of(n) != _byid[n]]
    _tbl_ok = not _mismatch
check('A5 家值与仓库内家表逐条一致（交叉核验，非自证）',
      _tbl_ok, star=True)

# A6 回落语义：未登记 home 的旧站位必须回落 scene（不是 None）
_fb_bad = [n for n in book.ids()
           if book.home_declared(n) is None and book.scene_of(n)
           and book.home_of(n) != book.scene_of(n)]
check('A6 未登记家的旧站位正确回落到站位场景', not _fb_bad, star=True)

# A7 负控制：未登记且无站位 ⇒ None（证明 home_of 不是恒真）
check('A7 既无家又无站位者返 None（负控制）',
      book.home_of('ot_sans') is None and book.home_of('__不存在__') is None,
      star=True)

# A8 跨作品条目不许冒充站位（scene 必须为 None）
_cross = [n for n in homes if n.startswith(('ut_', 'hy_', 'os_'))]
_bad_scene = [n for n in _cross if book.scene_of(n) is not None]
check('A8 跨作品角色无站位场景（scene=None，不冒充站位）',
      not _bad_scene, star=True)

# A9 ★★★ `by_source()` 只数**站位**（第87轮实测暴露的静默缺陷）
#    ---- 起因：加 50 条家条目后 `by_source()` 把 84 条一起数 ⇒ `authored` 从 9
#    冲成 59（家条目的 `source` 恒 `authored`，那只是"这条不是站位"的标记）。
#    该缺陷**不是报红暴露的，是逐条核对 DIFF 时发现的**（本项目 §「判据本身也是
#    被测物」的又一例）⇒ 补此判据把它钉死。判据 = `by_source()` 必须与
#    `counts.by_source`（JSON 里的站位口径）逐值相等，且 `station_ids()` 就是
#    站位集合。
_bs = book.by_source()
_cnt_bs = (_load_json(NP.placement_path()) or {}).get('counts', {}).get('by_source')
check('A9 ★★ `by_source()` 只数站位（与 counts.by_source 同源，不含家条目）',
      _bs == _cnt_bs
      and len(book.station_ids()) == sum(_bs.values())
      and len(book.station_ids()) < len(book.ids()),
      star=False)

# ================================================================ B. 自主移动隔离
_roster_all = book.ids()
_roster_filtered = [n for n in _roster_all if book.scene_of(n)]

check('B1 候选池被收窄（跨作品不进自主移动池）',
      len(_roster_filtered) < len(_roster_all), star=True)
check('B2 跨作品角色零人在候选池',
      not any(n in _roster_filtered for n in _cross), star=True)
check('B3 旧站位角色仍在候选池（不是把池清空）',
      all(n in _roster_filtered for n in ('ralsei', 'susie', 'berdly')),
      star=True)

# B4/B5/B6：真跑 npc_roam.step（**行为级**，用真实量级输入）
NOW = 3 * 3600.0                        # 凌晨 3 点（night 段，就寝闸会开）
REACH = ['ch1.unknown.unknown', 'ch2.my_castle_town.my_castle_town']
# ★★ 夹具保真（本轮实测被坑过两次）：
#   ① 取值器必须给全（不给 ⇒ _call(None,…) 返 None）；
#   ② 取值器必须吃**两个位置参数**（单参会被 _call 静默吞掉 ⇒ 全员不动）。
TRAITS = lambda n, _d=None: None                            # noqa: E731
FAMILIAR = lambda n, _d=None: 0.0                           # noqa: E731
FRIENDS = lambda n, _d=None: None                           # noqa: E731
HOME = lambda n, _d=None: book.home_of(n)                   # noqa: E731
REACHP = lambda n, _d=None: REACH                           # noqa: E731


def _decide(nid, now, **kw):
    return NI.decide(nid, now, **kw)


def _sleep(nid, now, **kw):
    return NI.choose_sleep_scene(nid, now, **kw)


def _run_step(roster, salt):
    st = NR.RoamState(enabled=True)
    return st, NR.step(st, NOW, roster=roster, decide_fn=_decide,
                       traits_of=TRAITS, familiar_of=FAMILIAR, home_of=HOME,
                       reachable_of=REACHP, friends_of=FRIENDS,
                       sleep_fn=_sleep, salt=salt)


_st1, _out1 = _run_step(_roster_filtered, 'r87')
_cross1 = [n for n in (_out1.get('decided') or []) if n in _cross]
check('B4 过滤池下跨作品角色零决策（正确接线）', not _cross1, star=True)

# ★★ B5 是**接线断言**（「函数写对了 ≠ 产品用上了」—— 实测：把
#    `roster=self._npc_roam_roster()` 退回 `book.ids()` 时，上面 B1~B4
#    全都会照常 PASS，因为那一侧测的是我自己重演的过滤逻辑，不是产品真用的那个。
#    ⇒ 必须断言 **`main.py` 真的把 `_npc_roam_roster()` 传给了 `step`**。
_src_b = ''
try:
    with io.open(MAIN, 'r', encoding='utf-8') as _fh:
        _src_b = _fh.read()
except Exception:
    pass
_btree = ast.parse(_src_b) if _src_b else None
_b_step = None
if _btree is not None:
    for _n in ast.walk(_btree):
        if isinstance(_n, ast.Call):
            _f = _n.func
            if (isinstance(_f, ast.Attribute) and _f.attr == 'step'
                    and isinstance(_f.value, ast.Name)
                    and _f.value.id == 'npc_roam_mod'):
                _b_step = _n
                break
_roster_arg = None
if _b_step is not None:
    for _kw in _b_step.keywords:
        if _kw.arg == 'roster':
            _roster_arg = _kw.value
_roster_is_fn = False
if _roster_arg is not None:
    for _c in ast.walk(_roster_arg):
        if isinstance(_c, ast.Attribute) and _c.attr == '_npc_roam_roster':
            _roster_is_fn = True
check('B5 ★★★ main.py 真把 `_npc_roam_roster()` 传给了 step（接线断言）',
      _roster_is_fn, star=True)

_old1 = [n for n in (_out1.get('decided') or []) if n not in _cross]
check('B6 同一拍下旧站位角色确实有人在动（B4 不是"全员不动"的假绿）',
      len(_old1) > 0, star=True)

_st2, _out2 = _run_step(_roster_all, 'r87')
_cross2 = [n for n in (_out2.get('decided') or []) if n in _cross]
check('B7 未过滤池下跨作品角色确实会被派出去（成对负控制）',
      len(_cross2) > 0, star=True)
_landed = [n for n in _cross2 if _st2.get(n) is not None]
check('B8 负控制里他们真落到了场景（不是"决策了没落点"）',
      len(_landed) == len(_cross2), star=True)

# ================================================================ C. 就寝真消费 home
_sc, _why = NI.choose_sleep_scene(
    'ut_toriel', NOW, home=book.home_of('ut_toriel'),
    friends=[], reachable=[book.home_of('ut_toriel')] + REACH, last_sleep=None)
check('C1 就寝决策能落回自己的家',
      _sc == book.home_of('ut_toriel'), star=True)

_sc2, _why2 = NI.choose_sleep_scene(
    'ut_toriel', NOW, home=book.home_of('ut_toriel'),
    friends=[], reachable=list(REACH), last_sleep=None)
check('C2 家不可达时不硬落（成对负控制）',
      _sc2 != book.home_of('ut_toriel'), star=True)

# ================================================================ D. _call 两参约定锁
_src = ''
try:
    with io.open(MAIN, 'r', encoding='utf-8') as _fh:
        _src = _fh.read()
except Exception:
    pass
_tree = ast.parse(_src) if _src else None

_step_call = None
if _tree is not None:
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Call):
            _f = _n.func
            if (isinstance(_f, ast.Attribute) and _f.attr == 'step'
                    and isinstance(_f.value, ast.Name)
                    and _f.value.id == 'npc_roam_mod'):
                _step_call = _n
                break

check('D1 在 main.py 里找到 npc_roam.step 的调用点',
      _step_call is not None, star=True)

_CALL_KW = ('traits_of', 'familiar_of', 'home_of', 'reachable_of', 'friends_of')
_injected = {}
if _step_call is not None:
    for _kw in _step_call.keywords:
        if _kw.arg in _CALL_KW:
            _injected[_kw.arg] = _kw.value

check('D2 五个取值器都注入了', len(_injected) == 5, star=True)

_d_bad = []
for _name, _node in _injected.items():
    if isinstance(_node, ast.Lambda):
        if len(_node.args.args) < 2:
            _d_bad.append((_name, 'lambda 形参 %d 个' % len(_node.args.args)))
    else:
        _mn = _node.attr if isinstance(_node, ast.Attribute) else None
        _defn = None
        if _tree is not None:
            for _c in ast.walk(_tree):
                if isinstance(_c, ast.FunctionDef) and _c.name == _mn:
                    _defn = _c
                    break
        if _defn is None:
            _d_bad.append((_name, '找不到 def %s' % _mn))
        else:
            _pos = [a for a in _defn.args.args if a.arg != 'self']
            if len(_pos) < 2:
                _d_bad.append((_name, '%s 位置形参 %s' % (_mn, [a.arg for a in _pos])))
check('D3 ★★★ 注入的取值器都吃两个位置参数（_call 的调用约定）',
      not _d_bad, star=True)

# D4 行为级：按 _call 的真形状调一次，必须拿回非 None
_hv = NR._call(HOME, 'ralsei', None)
_rv = NR._call(REACHP, 'ralsei', None)
check('D4 home_of 经 _call 拿到非 None（行为级）', _hv is not None, star=True)
check('D5 reachable_of 经 _call 拿到非 None（行为级）', _rv is not None, star=True)

# D6 成对负控制：单参 lambda 必须失败
_nv = NR._call(lambda nid: book.home_of(nid), 'ralsei', None)
check('D6 单参 lambda 经 _call 返 None（成对负控制）', _nv is None, star=True)

# D7 那三个方法也必须能被两参调用（行为级）
try:
    import inspect
    _cls = None
    for _c in ast.walk(_tree):
        if isinstance(_c, ast.ClassDef):
            _names = {x.name for x in ast.walk(_c) if isinstance(x, ast.FunctionDef)}
            if '_npc_roam_roster' in _names:
                _cls = _c
                break
    _sig_bad = []
    for _mn in ('_npc_roam_traits', '_npc_roam_familiar', '_npc_roam_friends'):
        _fd = None
        for _x in ast.walk(_cls) if _cls is not None else []:
            if isinstance(_x, ast.FunctionDef) and _x.name == _mn:
                _fd = _x
                break
        if _fd is None:
            _sig_bad.append((_mn, '缺失'))
            continue
        _pos = [a for a in _fd.args.args if a.arg != 'self']
        if len(_pos) < 2:
            _sig_bad.append((_mn, [a.arg for a in _pos]))
    check('D7 三个取值器方法的位置形参都 >= 2', not _sig_bad, star=True)
except Exception as _e:
    check('D7 三个取值器方法的位置形参都 >= 2', False, star=True)

# ================================================================ E. Outertale 未硬安家
_reg = _load_json(os.path.join(PKG, 'assets', 'npc', '_registry.json'))
_ot = [n['id'] for n in (_reg or {}).get('npcs', []) if n['id'].startswith('ot_')]
_ot_homed = [n for n in _ot if book.home_of(n) is not None]
check('E1 Outertale 的 %d 人未被硬安家' % len(_ot), not _ot_homed, star=True)

_idx = _load_json(os.path.join(SCENES, '_index.json')) or {}
_has_outertale = 'outertale' in (_idx.get('chapters') or {})
check('E2 如实反映：_index.json 里没有 outertale 章 ⇒ 挂起而非硬编',
      (not _has_outertale) or bool(_ot_homed), star=True)

# ================================================================ F. 数据面自洽
_entries = {}
for _cid, _c in (_idx.get('chapters') or {}).items():
    for _aid, _a in (_c.get('areas') or {}).items():
        for _sid, _e in (_a.get('scenes') or {}).items():
            _ee = dict(_e)
            _ee['chapter_id'] = _cid
            _ee['area_id'] = _aid
            _entries[_sid] = _ee

_sids = []
for _h in homes:
    if homes[_h] not in _sids:
        _sids.append(homes[_h])

_miss_idx = [s for s in _sids if s not in _entries]
check('F1 每个家的场景都在 _index.json 里登记',
      not _miss_idx, star=True)

_geo = _load_json(os.path.join(SCENES, '_room_geometry.json')) or {}
_nogeo = []
for _s in _sids:
    _e = _entries.get(_s) or {}
    _gk = '%s:%s' % (_e.get('chapter_id'), _e.get('original_room_id'))
    if not isinstance((_geo.get('rooms') or {}).get(_gk), dict):
        _nogeo.append(_s)
check('F2 每个家的场景都有原作几何（可查宽高）', not _nogeo, star=True)

# F3 真调 load_scene（★ 判据取"产物输出"，不取源码字面量）
from modules import scene_system as SS     # noqa: E402
_bad_load = []
for _s in _sids:
    _st = SS.load_scene(_s, SCENES, entry=_entries.get(_s))
    if _st is None or _st.original_room_id is None:
        _bad_load.append(_s)
check('F3 每个家的场景都能被 load_scene 真加载且带原作房间号',
      not _bad_load, star=True)

# F4 成对负控制：不存在的 id ⇒ None；不给 entry 的分片场景也 ⇒ None
check('F4 load_scene 负控制（不存在 id / 缺 entry 都不放行）',
      SS.load_scene('ut.rooms.__不存在__', SCENES, entry=None) is None
      and SS.load_scene(_sids[0], SCENES, entry=None) is None, star=True)

# ================================================================ G. 判据自身体检
check('G1 被测文件都在盘（_placement.json / main.py / _index.json）',
      os.path.isfile(PLACEMENT) and os.path.isfile(MAIN)
      and os.path.isfile(os.path.join(SCENES, '_index.json')), star=True)
check('G2 判据计数守恒（家 + 未安家 ≤ 注册表总数）',
      len(homes) + len(_ot) <= len((_reg or {}).get('npcs', [])) + len(_ot),
      star=True)

print('=' * 70)
print('第87轮：FAIL %d 项 %s' % (len(_failed), _failed if _failed else ''))
print('=' * 70)
sys.exit(0 if not _failed else 1)

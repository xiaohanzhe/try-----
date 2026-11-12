# -*- coding: utf-8 -*-
u"""第185轮 · **ch1 森林那扇 1/50 神秘门**（`room_man`）完整接上 + 修掉"推门不触发"的接线缺陷。

## 要解决什么（三条实证，都是本轮量出来的）

1. `_hidden_rooms[0]`（ch1 `forest_area5` → `room_man`，概率 1/50）一直挂着
   `target_not_registered` —— 因为 `room_man` 没登记成场景。原作确有这扇门：
   `gml_Object_obj_doorX_musfade_Alarm_2` 里
   `if (room == room_forest_area5) { ch = ceil(random(50));
        if (ch == 50 && global.flag[910] == 0) room_goto(room_man);
        else                                   room_goto(room_forest_starwalker); }`
2. **`area5` 有两扇门**：`obj_doorA`（字母 A，走通用下标位移机制 ⇒ 现有那条
   `(area5, A) → before_maze` 是对的，**不许动**）与 `obj_doorX_musfade`（字母 X，
   就是这扇 1/50 门，之前**一条边都没有**）。
3. ★★★ **隐藏房掷骰接在了没人走的那条路上**：`_maybe_divert_to_hidden` 只在
   `travel_to_scene` 里，而推门走 `DoorProp.on_interact → _item_enter_scene →
   scene.switch`，**完全绕过**它。同理第184轮的 `_commit_gate_marks` 也只在
   `_travel_feedback_done` 里 ⇒ **真推门时隐藏房不触发、门控标记不写**。
   本轮修接线，并给两条登记补 `when_door`（ch1=X / ch2=W，原作条件挂在门对象上）。

## 分段

A 数据 12 · B 纯函数 9 · C 接线（AST）8 · D 端到端 5 · E 自检 5

★ 环境变量口子（只给 `mutate185.py` 用，判据本身一行不改）：
  `CQ_SCENES_185` / `CQ_MODS_185` / `CQ_MAIN_185` / `CQ_ITEM_185`
"""
import ast
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
SCENES = os.environ.get('CQ_SCENES_185') or os.path.join(PET, 'assets', 'scenes')
MODS = os.environ.get('CQ_MODS_185') or os.path.join(PET, 'modules')
MAINPY = os.environ.get('CQ_MAIN_185') or os.path.join(PET, 'src', 'main.py')
ITEMPY = os.environ.get('CQ_ITEM_185') or os.path.join(MODS, 'item_interact.py')
SRPY = os.path.join(MODS, 'scene_routing.py')

ROUTES = os.path.join(SCENES, '_routes.json')
ZONE = os.path.join(SCENES, '_zone.ch1.forest.json')
INDEX = os.path.join(SCENES, '_index.json')

#: 独立来源（**不是**从产品数据抄的）：原作反编译留档 + 第115轮物件普查
DOORCODES = os.path.join(REPO, 'code-quality-audit', u'第109轮-场景过渡动画',
                         '_evidence', 'door_codes109b.json')
INST115 = os.path.join(REPO, 'code-quality-audit', u'第115轮-跨作品物件普查',
                       '_evidence', 'raw', 'ch1', 'inst68.json')

AREA5 = u'ch1.forest.forest_area5'
MAN = u'ch1.forest.room_man'
STAR = u'ch1.forest.forest_starwalker'
BAKE = u'ch1.forest.forest_bake_sale'
BEFORE_MAZE = u'ch1.forest.forest_before_maze'
GML_NAME = 'gml_Object_obj_doorX_musfade_Alarm_2'

#: ★ 条数写死是为了防"某段整段被删掉还全绿"。**本条自身还没 +1** ⇒ 判 `TOTAL - 1`。
TOTAL_CHECKS = 41
EXPECT_ROUTES = 2832
#: ★★★ 两条**手工边**的 priority 必须在 `gen_routes44.py` 的生成区间（110 + ord*BAND + k，
#: 实测占满 7850~8262）**之外**。第一版取的 7900/7901 是错的：`7901` 早被
#: `ch5.flower_castle.dw_fcastle_gloves_tower` 的 Any 门占着（第172轮补的那条），
#: 而且整个 7900 段都在生成器区里 ⇒ 重跑生成器会静默撞号。改到 9001/9002（`fix_prio185.py`）。
EXPECT_PRIO_X = 9001
EXPECT_PRIO_MAN = 9002

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


def lf(s):
    return s.replace('\r\n', '\n')


sys.path.insert(0, MODS)
import scene_routing as SR          # noqa: E402
import item_interact as II          # noqa: E402

RAW = jload(ROUTES)
RT = RAW.get('routes') or []
HID = RAW.get('_hidden_rooms') or []
Z = jload(ZONE).get('scenes') or {}
IDX = jload(INDEX)
EVID = jload(INST115)
ROOMS = {r['name']: r for r in EVID['rooms']}
CODES = {e['name']: e.get('src') or '' for e in jload(DOORCODES)['codes']}

# ---------------------------------------------------------------------------
#  A 数据 14
# ---------------------------------------------------------------------------
print('')
print('=' * 72)
print(u'A 数据：两间场景 / 两条边 / 两条带门字母的登记')
print('=' * 72)

_idx_sc = IDX['chapters']['ch1']['areas']['forest']['scenes']
check(u'A1 `_index.json` 已登记 `room_man`，房号 142',
      _idx_sc.get(MAN, {}).get('original_room_id') == 142,
      u'%r' % (_idx_sc.get(MAN),))
check(u'A2 zone 里有 `room_man`，4 个物件（原作 n=4）',
      len((Z.get(MAN) or {}).get('objects') or []) == 4,
      u'物件数=%d' % len((Z.get(MAN) or {}).get('objects') or []))
#: ★★★ 第185轮的**施工修正**（这条判据现在是那次事故的固化）：
#: `bake_sale`（原作 `room_forest_savepoint2`）**早就有独立场景文件**
#: `ch1.forest.forest_bake_sale.json`（带 `bg`/`bgm`/`ambient`，10 个物件与证据 10/10 一致）。
#: 我第一版误以为它"缺物件数据"，又往 `_zone.ch1.forest.json` 里塞了一份 ⇒ **重复载体**，
#: 物件总数被多算 10（`objects_round44 C2/C3` 就是这么红的：独立重算 4076、实得 4086）。
#: ⇒ 这条现在钉的是「**同一间房不许有两个载体**」这个不变量，方向正好反过来。
_BAKE_F = os.path.join(SCENES, 'ch1.forest.forest_bake_sale.json')
check(u'A3 ★★ `bake_sale` **不在** zone，走它自己的独立文件（不许重复载体）',
      BAKE not in Z and os.path.isfile(_BAKE_F),
      u'在 zone=%s / 文件在=%s' % (BAKE in Z, os.path.isfile(_BAKE_F)))

_sp_map = {}
for _fn in os.listdir(SCENES):
    if _fn.startswith('_zone.') and _fn.endswith('.json'):
        for _sc in (jload(os.path.join(SCENES, _fn)).get('scenes') or {}).values():
            for _o in (_sc.get('objects') or []):
                if _o.get('src') and _o.get('sprite'):
                    _sp_map.setdefault(_o['src'], _o['sprite'])


def _obj_ok(sid, room_name, objs=None, sprite=True):
    u"""逐条比对：`src` / `pos` 与原作实例**一致**，且 `sprite` 映射与本仓既有规则一致。

    :param objs: 传了就按它比（`bake_sale` 走独立文件，不在 zone 里）。
    :param sprite: `bake_sale` 的物件（`obj_savepoint` 之类）在 zone 里**没有同类先例**，
        `_sp_map` 给不出映射 ⇒ 那一间只比 src+pos（贴图是否存在由 A6 逐个验文件），
        免得把"本仓没有先例"误判成"sprite 错"。
    """
    want = ROOMS[room_name]['insts']
    got = objs if objs is not None else ((Z.get(sid) or {}).get('objects') or [])
    if len(want) != len(got):
        return (False, u'条数 %d vs %d' % (len(want), len(got)))
    for w, g in zip(want, got):
        if g.get('src') != w['obj']:
            return (False, u'src 不同 %r vs %r' % (g.get('src'), w['obj']))
        if list(g.get('pos') or []) != [w['x'], w['y']]:
            return (False, u'pos 不同 %r vs %r' % (g.get('pos'), [w['x'], w['y']]))
        if sprite and g.get('sprite') != _sp_map.get(w['obj']):
            return (False, u'sprite %r' % (g.get('sprite'),))
    return (True, u'%d 条逐条一致%s' % (len(want), u'' if sprite else u'（只比 src+pos）'))


_ok4, _e4 = _obj_ok(MAN, 'room_man')
check(u'A4 `room_man` 4 个物件与原作实例**逐条**一致（src/pos/sprite）', _ok4, _e4)
_ok5, _e5 = _obj_ok(BAKE, 'room_forest_savepoint2',
                    jload(_BAKE_F).get('objects') or [], sprite=False)
check(u'A5 `bake_sale` 独立文件里 10 个物件与原作实例**逐条**一致（本轮没动它）', _ok5, _e5)

_all_objs = ((Z.get(MAN) or {}).get('objects') or []) + (jload(_BAKE_F).get('objects') or [])
_bad_sp = [(o.get('sprite'),) for o in _all_objs
           if not os.path.isfile(os.path.join(SCENES, o.get('sprite') or ''))]
check(u'A6 两个场景引用的贴图**逐个**真实存在（含 bake_sale 独立文件那 10 个）',
      bool(_all_objs) and not _bad_sp, u'共 %d 个 / 缺=%r' % (len(_all_objs), _bad_sp))

check(u'A7 routes 总数 == 2832（原 2830 + 2）', len(RT) == EXPECT_ROUTES,
      u'实测=%d' % len(RT))


def _edge(scene, letter):
    got = [r for r in RT if r.get('when_scene') == scene and r.get('when_door') == letter]
    return got[0] if len(got) == 1 else None


_r_x = _edge(AREA5, u'X')
_r_man = _edge(MAN, u'X')
_r_a = _edge(AREA5, u'A')

check(u'A8 `(area5, X)` → starwalker，priority %d' % EXPECT_PRIO_X,
      _r_x is not None and _r_x.get('to') == STAR and _r_x.get('priority') == EXPECT_PRIO_X,
      u'实测 %r' % (((_r_x or {}).get('to'), (_r_x or {}).get('priority')),))
check(u'A9 `(room_man, X)` → bake_sale，priority %d' % EXPECT_PRIO_MAN,
      _r_man is not None and _r_man.get('to') == BAKE
      and _r_man.get('priority') == EXPECT_PRIO_MAN,
      u'实测 %r' % (((_r_man or {}).get('to'), (_r_man or {}).get('priority')),))
check(u'A10 ★★ `(area5, A)` **一个字没动**（仍是 before_maze / 662）',
      _r_a is not None and _r_a.get('to') == BEFORE_MAZE and _r_a.get('priority') == 662,
      u'实测 %r' % (((_r_a or {}).get('to'), (_r_a or {}).get('priority')),))

#: `_original.code` 必须是**原作反编译原文的逐字子串**（CRLF 归一后比，不重写）
_src_gml = lf(CODES.get(GML_NAME) or '')
_c1 = lf(((_r_x or {}).get('_original') or {}).get('code') or '')
_c2 = lf(((_r_man or {}).get('_original') or {}).get('code') or '')
check(u'A11 两条边的 `_original.code` 都是原作 GML 的**逐字子串**',
      bool(_src_gml) and bool(_c1) and bool(_c2)
      and _c1 in _src_gml and _c2 in _src_gml
      and 'room_forest_starwalker' in _c1 and 'room_forest_savepoint2' in _c2,
      u'gml=%d 字 / c1=%d / c2=%d' % (len(_src_gml), len(_c1), len(_c2)))

_h0 = HID[0] if HID else {}
check(u'A12 `_hidden_rooms[0]` 启用且限定 **X** 门（ch1）/ `[1]` 限定 **W** 门（ch2）',
      _h0.get('scene') == MAN and _h0.get('enabled') is True
      and _h0.get('when_door') == u'X'
      and len(HID) > 1 and (HID[1].get('when_door') == u'W'),
      u'%r / %r' % (_h0.get('when_door'), (HID[1] if len(HID) > 1 else {}).get('when_door')))

#: ★★ A13：**这条判据是第185轮一次真实事故的固化**。第一版我把两条手工边的 priority
#: 取成 7900/7901，而 `7901` 早被 ch5 的 Any 门占着 —— 撞号不影响本轮行为（两条边
#: 不同 `when_scene`、不互相竞争），但 `route_for_door` 的第二键就是 priority，
#: **同号时胜负退化成声明顺序**（`sorted` 稳定），下次谁改一行数据就会静默翻结果。
#: 更要紧的是 7850~8262 整段属于 `gen_routes44.py` 的生成区间，手工边塞在里面，
#: 重跑生成器就会再撞一次、而且没人报错。⇒ 手工边挪到 9001/9002，并钉住这条不变量。
#: ★ 桌面那组 `200`（A~D 四扇门）是**施工前就有**的历史数据、四扇门不同字母不竞争，
#: 本条明确把它排除，否则这条判据会一上线就红。
_prio = [r.get('priority') for r in RT if isinstance(r.get('priority'), int)]
_cnt = {}
for _p in _prio:
    _cnt[_p] = _cnt.get(_p, 0) + 1
_duphi = sorted(p for p, n in _cnt.items() if n > 1 and p != 200)
check(u'A13 ★ 两条手工边 priority 全表唯一，且**高于生成器区间**（撞号 ⇒ 胜负退化成声明序）',
      EXPECT_PRIO_X != EXPECT_PRIO_MAN
      and EXPECT_PRIO_X not in _duphi and EXPECT_PRIO_MAN not in _duphi
      and bool(_prio) and max(_prio) == max(EXPECT_PRIO_X, EXPECT_PRIO_MAN),
      u'除桌面 200 外的重复=%r / max=%r' % (_duphi, max(_prio) if _prio else None))

#: ★★★ A14：**载体唯一性** —— 第185轮那次"重复载体"事故的固化判据。
#: 全局不变量：`index 场景数 == 独立文件数 + zone 场景数`，且三件事同时成立：
#: ① 同一场景**不许**既是独立文件又在 zone（否则物件被数两遍，而且谁生效取决于
#:    `load_scene` 先读谁 —— 静默的、不可见的错）；
#: ② zone 里每一间都在 index 里登记过（否则是**孤儿**，产品读得到但没人知道它存在）；
#: ③ index 里每一间都有载体（否则是**空壳**，登记了却打不开 —— 本轮施工前的
#:    `bake_sale` 就是"有文件但没数据"的近亲）。
#: ★ 这三条不是我凭空加的：①③ 正是本轮 `objects_round44 C2/C3`（+10 假增量）
#:   与 `rooms_round47 B1`（`room_man.json` 不存在）两处红暴露出来的。
_SCN = {}


def _walk_scn(o):
    if isinstance(o, dict):
        for _k, _v in o.items():
            if isinstance(_v, dict):
                if 'original_room_id' in _v:
                    _SCN[_k] = _v
                _walk_scn(_v)


_walk_scn(IDX)
_solo = {k for k, v in _SCN.items() if v.get('file')}
_zoneall = {}
for _fn in sorted(os.listdir(SCENES)):
    if _fn.startswith('_zone.') and _fn.endswith('.json'):
        for _k in (jload(os.path.join(SCENES, _fn)).get('scenes') or {}):
            _zoneall[_k] = _fn
_overlap = sorted(_solo & set(_zoneall))
_orphan = sorted(set(_zoneall) - set(_SCN))
_shell = sorted(set(_SCN) - _solo - set(_zoneall))
check(u'A14 ★★★ 载体唯一：index == 独立文件 + zone，且无重叠/无孤儿/无空壳',
      len(_SCN) == len(_solo) + len(_zoneall)
      and not _overlap and not _orphan and not _shell,
      u'%d vs %d+%d 重叠=%r 孤儿=%r 空壳=%r'
      % (len(_SCN), len(_solo), len(_zoneall),
         _overlap[:3], _orphan[:3], _shell[:3]))

# ---------------------------------------------------------------------------
#  B 纯函数 9（走产品真身 `load_routes()` + `pick_hidden`）
# ---------------------------------------------------------------------------
print('')
print('=' * 72)
print(u'B 纯函数：门字母决定掷不掷（走产品 `load_routes()` 真身）')
print('=' * 72)

H = SR.load_routes()['hidden']


def _pick(scene, door=None, roll=0.0, seen=None):
    hit = SR.pick_hidden(H, scene, seen, roll=lambda: roll, door=door)
    return SR.hidden_key(hit) if hit else None


check(u'B1 X 门 + roll=0.0 ⇒ 命中 `room_man`（**本轮要的效果**）',
      _pick(AREA5, door=u'X') == MAN, u'实测 %r' % (_pick(AREA5, door=u'X'),))
check(u'B2 ★ A 门 + roll=0.0 ⇒ **不掷**（同一间房另一扇门）',
      _pick(AREA5, door=u'A') is None, u'实测 %r' % (_pick(AREA5, door=u'A'),))
check(u'B3 ★★ 不知道是哪扇门（door=None）⇒ **不掷**（fail-closed）',
      _pick(AREA5) is None, u'实测 %r' % (_pick(AREA5),))
check(u'B4 X 门 + roll=0.5 ⇒ 不命中（1/50 是真的概率，不是必中）',
      _pick(AREA5, door=u'X', roll=0.5) is None)
check(u'B5 已发现过（seen 含 man）⇒ 再去 X 门也不掷（永久锁）',
      _pick(AREA5, door=u'X', seen={MAN}) is None)
check(u'B6 ch2 那条仍能命中（只在 W 门）',
      _pick(u'ch2.cyber_city.dw_city_traffic_3', door=u'W') == u'ch2.cyber_city.dw_city_man'
      and _pick(u'ch2.cyber_city.dw_city_traffic_3', door=u'A') is None,
      u'W=%r A=%r' % (_pick(u'ch2.cyber_city.dw_city_traffic_3', door=u'W'),
                      _pick(u'ch2.cyber_city.dw_city_traffic_3', door=u'A')))

#: 向后兼容：**没写** `when_door` 的登记仍然"任意门都掷"
_LEGACY = [{'scene': u'x.y.z', 'from_scene': u'a.b.c', 'enabled': True,
            'probability': 0.5, 'once': True, '_order': 0}]
_wild = [dict(_LEGACY[0], when_door=u'*')]
check(u'B7 ★ 无 `when_door` 的登记 ⇒ 任意门都掷（向后兼容，老数据不受影响）',
      SR.hidden_key(SR.pick_hidden(_LEGACY, u'a.b.c', None,
                                    roll=lambda: 0.0, door=u'Z') or {}) == u'x.y.z')
check(u'B8 `when_door: "*"` ⇒ 任意门都掷',
      SR.hidden_key(SR.pick_hidden(_wild, u'a.b.c', None,
                                    roll=lambda: 0.0, door=u'Z') or {}) == u'x.y.z')
check(u'B9 不启用（enabled=False）的登记一律不掷（ch3/ch4 两条仍挂着）',
      all(_pick(h.get('from_scene') or u'', door=u'X') is None
          for h in H if h.get('enabled') is not True) if H else False,
      u'未启用条数=%d' % len([h for h in H if h.get('enabled') is not True]))

# ---------------------------------------------------------------------------
#  C 接线（AST）8
# ---------------------------------------------------------------------------
print('')
print('=' * 72)
print(u'C 接线：门字母一路传下去，且"真换房了"才收尾（AST）')
print('=' * 72)

_sr = ast.parse(rd(SRPY))
_ii = ast.parse(rd(ITEMPY))
_mp = ast.parse(rd(MAINPY))


def _fn(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


_pickf = _fn(_sr, 'pick_hidden')
_args = [a.arg for a in (_pickf.args.args if _pickf else [])]
check(u'C1 `pick_hidden` 有 `door` 形参', 'door' in _args, u'形参=%r' % (_args,))
_uses_door = []
if _pickf is not None:
    for n in ast.walk(_pickf):
        if isinstance(n, ast.Compare):
            _uses_door += [x for x in ast.walk(n)
                           if isinstance(x, ast.Name) and x.id in ('want_door', 'door')]
check(u'C2 ★ `pick_hidden` 里**真的用上**了门字母（不是只加了个形参）',
      len(_uses_door) >= 3, u'命中 %d 处' % len(_uses_door))

_divf = _fn(_mp, '_maybe_divert_to_hidden')
_dargs = [a.arg for a in (_divf.args.args if _divf else [])]
check(u'C3 `_maybe_divert_to_hidden` 有 `door` 形参', 'door' in _dargs, u'%r' % (_dargs,))
_pass_door = []
if _divf is not None:
    for n in ast.walk(_divf):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == 'pick_hidden':
            _pass_door = [k for k in n.keywords if k.arg == 'door']
check(u'C4 它把 `door=` 传给 `pick_hidden`', len(_pass_door) == 1)

_ent = _fn(_mp, '_item_enter_scene')
_eargs = [a.arg for a in (_ent.args.args if _ent else [])]
check(u'C5 `_item_enter_scene` 有 `door` 形参', 'door' in _eargs, u'%r' % (_eargs,))

_lines = (rd(MAINPY).split('\n'))
_calls, _sw = -1, -1
if _ent is not None:
    for n in ast.walk(_ent):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr == '_maybe_divert_to_hidden' and _calls < 0:
                _calls = n.lineno
            if n.func.attr == 'switch' and _sw < 0:
                _sw = n.lineno
check(u'C6 ★★ 掷骰发生在 `switch` **之前**（先改目的地再换房）',
      _calls > 0 and _sw > 0 and _calls < _sw, u'掷骰@%d switch@%d' % (_calls, _sw))

_fb = -1
if _ent is not None:
    for n in ast.walk(_ent):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == '_travel_feedback_done':
            _fb = n.lineno
check(u'C7 ★★★ 推门成功后走 `_travel_feedback_done()`（隐藏房/门控记账的唯一收尾点）',
      _fb > 0 and _fb > _sw, u'收尾@%d switch@%d' % (_fb, _sw))

_doorf = _fn(_ii, 'DoorProp.on_interact') if False else None
for n in ast.walk(_ii):
    if isinstance(n, ast.ClassDef) and n.name == 'DoorProp':
        for m in n.body:
            if isinstance(m, ast.FunctionDef) and m.name == 'on_interact':
                _doorf = m
_pass_letter = []
if _doorf is not None:
    for n in ast.walk(_doorf):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id == '_call_enter':
            _pass_letter = [a for a in n.args
                            if isinstance(a, ast.Attribute) and a.attr == 'door_letter']
check(u'C8 `DoorProp.on_interact` 经 `_call_enter` 把 `self.door_letter` 传出去',
      len(_pass_letter) == 1)

# ---------------------------------------------------------------------------
#  D 端到端 5
# ---------------------------------------------------------------------------
print('')
print('=' * 72)
print(u'D 端到端：真 `build_props` / 真 `route_for_door` / 真 `_call_enter`')
print('=' * 72)


def _props(sid):
    sc = {'scene_id': sid, 'objects': (Z.get(sid) or {}).get('objects') or []}
    return II.build_props(sc, u'ch1', u'dark', routes=RAW)


def _door_of(props, src):
    got = [p for p in props if getattr(p, 'src', None) == src
           and getattr(p, 'target_scene', None)]
    return got[0].target_scene if len(got) == 1 else None


_d1 = _door_of(_props(MAN), u'obj_doorX_musfade')
check(u'D1 真 `build_props` 在 `room_man` 建出那扇门，指向 `bake_sale`',
      _d1 == BAKE, u'实测 %r' % (_d1,))
_p5 = _props(AREA5)
check(u'D2 ★ `area5` 两扇门各走各的：X → starwalker，A → before_maze',
      _door_of(_p5, u'obj_doorX_musfade') == STAR
      and _door_of(_p5, u'obj_doorA') == BEFORE_MAZE,
      u'X=%r A=%r' % (_door_of(_p5, u'obj_doorX_musfade'), _door_of(_p5, u'obj_doorA')))
check(u'D3 `route_for_door(room_man, "X")` == bake_sale',
      II.route_for_door(RAW, MAN, u'X', src=u'obj_doorX_musfade') == BAKE)

_seen_calls = []


def _two(scene_id, door=None):
    _seen_calls.append((scene_id, door))
    return True


def _one(scene_id):
    _seen_calls.append((scene_id, 'NOPE'))
    return True


II._call_enter(_two, u'a.b.c', u'X')
_ok_two = _seen_calls[-1] == (u'a.b.c', u'X')
#: ★ 桩只吃 1 个参数 —— 若 `_call_enter` 无脑传 `door=`，这里会抛 `TypeError`。
#:   捕获成"红"而不是让整套崩掉（崩掉也看不见其它判据的结果）。
try:
    II._call_enter(_one, u'a.b.c', u'X')
    _ok_one = _seen_calls[-1] == (u'a.b.c', 'NOPE')
except TypeError:
    _ok_one = False
check(u'D4 `_call_enter`：认 `door=` 就带过去，1 参桩仍按旧签名调（不炸）',
      _ok_two and _ok_one, u'%r' % (_seen_calls[-2:],))

_host = None
for n in ast.walk(_mp):
    if isinstance(n, ast.FunctionDef) and n.name == '_item_enter_scene':
        _host = [a.arg for a in n.args.args]
check(u'D5 宿主真方法 `_item_enter_scene` 的签名**真的**接受 `door`（不是只有桩认）',
      _host is not None and 'door' in _host, u'%r' % (_host,))

# ---------------------------------------------------------------------------
#  E 自检 5
# ---------------------------------------------------------------------------
print('')
print('=' * 72)
print(u'E 自检')
print('=' * 72)

_F = [ITEMPY, SRPY, MAINPY, ROUTES, ZONE]
_BOMS = [p for p in _F if os.path.isfile(p) and rdb(p)[:3] == b'\xef\xbb\xbf']
_FFFD = [p for p in _F if os.path.isfile(p) and u'\ufffd' in rd(p)]
check(u'E1 无 BOM / 无 U+FFFD', not _BOMS and not _FFFD,
      u'BOM %r / FFFD %r' % (_BOMS, _FFFD))

_SELF = rd(os.path.abspath(__file__))
_const = []
for n in ast.walk(ast.parse(_SELF)):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'check':
        if len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) \
                and n.args[1].value is True:
            _const.append(n.lineno)
check(u'E2 无恒真判据（`check(..., True)` 一处都没有）', not _const, u'行号=%r' % (_const,))

_imp = [a.name for n in ast.walk(ast.parse(_SELF)) if isinstance(n, ast.Import)
        for a in n.names]
_impfrom = [n.module for n in ast.walk(ast.parse(_SELF))
            if isinstance(n, ast.ImportFrom) and n.module]
#: ★★ 第一版这条判据是**扫文本** `'RalseiPet(' not in _SELF` —— 它扫到了**自己那一行**
#:    （断言的源码里就写着这串）⇒ 恒假。改成扫 AST 里有没有这个**调用**。
_ralsei_call = [n.lineno for n in ast.walk(ast.parse(_SELF))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == 'RalseiPet']
check(u'E3 不 import `main` / 不构造 `RalseiPet`',
      'main' not in _imp and 'main' not in _impfrom and not _ralsei_call,
      u'调用行=%r' % (_ralsei_call,))

#: ★★ 同上：这条原来是扫文本里的 `'D:\\'` 字面量 —— 也扫到了自己。
#:   改成扫 **AST 常量**里有没有"盘符开头的绝对路径"。
_ABS = re.compile(r'^[A-Za-z]:[\\/]')
_hard = [n.value for n in ast.walk(ast.parse(_SELF))
         if isinstance(n, ast.Constant) and isinstance(n.value, str)
         and _ABS.match(n.value)]
check(u'E4 判据自己不写死外部盘路径（AST 常量扫描）', not _hard, u'命中=%r' % (_hard,))
check(u'E5 条数固定 %d' % TOTAL_CHECKS, _n['p'] + _n['f'] == TOTAL_CHECKS - 1,
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

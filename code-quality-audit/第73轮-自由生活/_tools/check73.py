# -*- coding: utf-8 -*-
"""第73轮 · 常驻锁：NPC「自由生活」不许静默漂移。

为什么值得常驻
--------------
第73轮新加了一个**零依赖纯策略**模块 `npc_life.py`（场景特质 / 熟络度 / 传话 /
自主节拍）并把它接进产品。三样东西都可能被后来的人无声改坏：

  ① **数据镜像**：`npc_life.TRAIT_WORDS_CN` 与 `familiarity_seed` 的常量必须与
     `_crossworld.json` **逐字同源**（各写一份 = 两个真相）；
  ② **匹配规则**：场景特质靠"英文词在 id 分量里的**词首/词尾**"判定。
     退回朴素子串匹配 ⇒ `ash` 会命中 `afterthrash2`、`night` 会命中 `knightclimb`
     （本轮实测踩过）；
  ③ **接线**：`_npc_life_tick` 有没有被 `update_movement` 真调用、
     `npc_system_prompt` 有没有真把生活块拼进去 —— 这是本项目最贵的坑
     「函数写对了 != 产品用上了」。

设计纪律（沿用 check71 / check72）
----------------------------------
① **零网络、零真实存储** ⇒ 可进 G2。
   ⚠️ **第74轮 B11 更正**：这里原来写"真机段用的是隔离内存记忆"，**那句话不成立** ——
   `_pet = M.RalseiPet()` 在**构造期**就把真实保管库定下来了（下面换 `npc_memory`
   是构造**之后**的事），构造期那行日志还会把 `E:\RalseiMemory\npc_memory` 打进输出。
   真正管用的隔离层是 `run_all.HERMETIC_IDS` 里的 `check73`（注入 `RALSEI_MEMORY_DIR`
   ⇒ `find_device_dir` 直接 return）。本文件里的夹具只算**第二层**，不要拿它当隔离依据。
② **正/负控制成对**：每条"放行"都配一条"拒"，每条内核都配一个"改坏了必须报红"。
③ **不自比**：A 段的真源是 `_crossworld.json`（数据面契约），不是本文件自己写死的表。
④ **判据名里不许自带 `[PASS]`/`[FAIL]`/`[OK]` 字样**（会污染 run_all 的计数）。
⑤ ★ C 段**真 import 真跑** `npc_life` 的每个公开函数；E 段**真机**实例化 `RalseiPet()`
   并停掉全部定时器（与 check55 / check56 同规）。
"""
from __future__ import print_function

import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODULES = os.path.join(PET, 'modules')
SRC = os.path.join(PET, 'src')
NPCDIR = os.path.join(PET, 'assets', 'npc')
CROSS = os.path.join(NPCDIR, '_crossworld.json')
LIFE = os.path.join(MODULES, 'npc_life.py')
NPC_SYSTEM = os.path.join(MODULES, 'npc_system.py')
NPC_PERSONA = os.path.join(MODULES, 'npc_persona.py')
MAIN = os.path.join(SRC, 'main.py')
INDEX = os.path.join(PET, 'assets', 'scenes', '_index.json')

FAILS = []
NCHECK = 0
_LINES = []

#: 只有这一个场景同场有 >= 2 位纯 NPC（第73轮实测；`_placement.json` 34 条里数出来的）。
#: ★ 这条本身就是**如实结论**：自由生活的"自主闲聊"现网**只在一个场景真的跑得起来**。
LIVE_SCENE = 'ch5.my_castle_town.my_castle_town'

#: 禁止出现在 NPC 提示词里的**具体标识符**（作品归属 / 版本 / 世界模型内部名）。
#: ⚠️ 刻意**不**把 `dark`/`light` 放进来：它们是普通英文词，容易误报；
#:    归属泄露的真判据是"作品名 + 前缀 + 内部字段名"这几类具体串。
LEAK_WORDS = ('ut_', 'hy_', 'ot_', 'os_', 'Deltarune', 'Undertale', 'Outertale',
              'OneShot', '黄魂', 'foreign', 'roam_scope', 'home_world')


def check(name, cond, extra=''):
    global NCHECK
    NCHECK += 1
    for tok in ('[PASS]', '[FAIL]', '[OK]'):
        if tok in name:
            FAILS.append('判据名字面量污染: %s' % name)
    line = ('[PASS] %s %s' % (name, extra)) if cond else ('[FAIL] %s %s' % (name, extra))
    _LINES.append(line)
    print(line)
    if not cond:
        FAILS.append(name)


def read_json(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def source_of(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


for _p in (MODULES, SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ast                                                    # noqa: E402
import collections                                            # noqa: E402

import npc_life as L                                          # noqa: E402
import npc_system as NS                                       # noqa: E402
import npc_persona as NP                                      # noqa: E402

CROSSJ = read_json(CROSS)
REGJ = read_json(REG := os.path.join(NPCDIR, '_registry.json'))
MAIN_SRC = source_of(MAIN)
LIFE_SRC = source_of(LIFE)


# ==========================================================================
print('=' * 74)
print('A 契约与镜像（真源 = _crossworld.json，不是本文件写死的表）')
print('=' * 74)

# ★ 第77轮改：写死 `== 73` 会让"契约随轮次推进"必然报红（本轮已推进到 77）。
#   判据本意是"七段齐 + 已推进到 73 或之后"，故改成下界。
check('A1 跨世界契约七段齐且已推进到第73轮或之后',
      all(k in CROSSJ for k in ('roam', 'twin_groups', 'identity_blind',
                                'familiarity_seed', 'scene_traits', 'visitor', 'wiring'))
      and (CROSSJ.get('round') or 0) >= 73,
      'round=%s' % CROSSJ.get('round'))

_traits_id = [t.get('id') for t in (CROSSJ['scene_traits'].get('traits') or [])]
check('A2 契约的特质 id 集合与 `npc_life.TRAITS` 逐项相等（含顺序）',
      tuple(_traits_id) == tuple(L.TRAITS),
      '契约=%s 代码=%s' % (_traits_id, list(L.TRAITS)))

_mismatch = []
for _t in (CROSSJ['scene_traits'].get('traits') or []):
    _want = tuple(_t.get('words') or [])
    _got = tuple(L.TRAIT_WORDS_CN.get(_t.get('id'), ()))
    if _want != _got:
        _mismatch.append((_t.get('id'), _want, _got))
check('A3 每个特质的中文词表与契约 `words` **逐字相等**（各写一份 = 两个真相）',
      not _mismatch, str(_mismatch[:2] or '(一致)'))

_sv = CROSSJ['familiarity_seed'].get('seed_values') or {}
check('A4 熟络度初值三个常量与契约 `seed_values` 逐值相等',
      _sv.get('same_au_twin') == L.SEED_SAME_AU_TWIN
      and _sv.get('same_production') == L.SEED_SAME_PRODUCTION
      and _sv.get('stranger') == L.SEED_STRANGER,
      '契约=%s / 代码=%s' % (_sv, [L.SEED_SAME_AU_TWIN, L.SEED_SAME_PRODUCTION,
                                     L.SEED_STRANGER]))

_tor = [g for g in (CROSSJ['twin_groups'].get('groups') or [])
        if g.get('name') == 'Toriel']
check('A5 ★ Toriel 组：AU 成员只有两人，Deltarune 那位被明确记为**同名**',
      len(_tor) == 1
      and sorted(_tor[0].get('au_family_members') or []) == ['ot_toriel', 'ut_toriel']
      and (_tor[0].get('namesake_members') or []) == ['toriel'],
      str({k: _tor[0].get(k) for k in ('au_family_members', 'namesake_members')}
          if _tor else '(组缺失)'))

_pairs = NS.au_twin_pairs(CROSSJ)
_n_expect = 0
for _g in (CROSSJ['twin_groups'].get('groups') or []):
    _n = len(_g.get('au_family_members') or [])
    _n_expect += _n * (_n - 1) // 2
check('A6 `npc_system.au_twin_pairs` 真跑：配对数 == 各组 AU 成员的组合数之和',
      len(_pairs) == _n_expect and _n_expect > 0,
      '配对=%d 期望=%d' % (len(_pairs), _n_expect))
check('A6b ★ 负控制：`(ot_toriel, toriel)` **不在** AU 配对里'
      '（同名的一对不该享受"另一个版本的我"的加速）',
      frozenset(('ot_toriel', 'toriel')) not in _pairs
      and frozenset(('ut_toriel', 'ot_toriel')) in _pairs)

_ni = CROSSJ['identity_blind'].get('not_injected') or []
check('A7 「不许注入」清单四条齐（作品归属 / 版本 / npc id / 人设）',
      len(_ni) >= 4, '%d 条' % len(_ni))

check('A8 `scene_traits.how` 仍如实写着"来源本轮未定"以外的两种候选里的**已定方案**'
      '（来源 = 文本语义），且 traits 里给了 `words`',
      all(t.get('words') for t in (CROSSJ['scene_traits'].get('traits') or [])))


# ==========================================================================
print('=' * 74)
print('B 代码面（AST：形状不许被无声改坏）')
print('=' * 74)

check('B1 `npc_life.py` 在盘上', os.path.isfile(LIFE))
_LIFE_T = ast.parse(LIFE_SRC)
_top_imports = set()
for _n in _LIFE_T.body:
    if isinstance(_n, ast.Import):
        for _a in _n.names:
            _top_imports.add(_a.name.split('.')[0])
    elif isinstance(_n, ast.ImportFrom):
        _top_imports.add((_n.module or '').split('.')[0])
check('B2 ★ 零依赖：`npc_life` 顶层 import 只含标准库（实测 {collections}）',
      _top_imports <= {'collections'}, str(sorted(_top_imports)))

_fn_imports = []
for _n in ast.walk(_LIFE_T):
    if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for _x in ast.walk(_n):
            if isinstance(_x, (ast.Import, ast.ImportFrom)):
                _fn_imports.append((_n.name, _x.lineno))
check('B3 ★ 零函数内 import（与 `companion*` / `npc_placement` 同一条纪律）',
      not _fn_imports, str(_fn_imports[:3] or '(无)'))

_MAIN_T = ast.parse(MAIN_SRC)
check('B4 main.py 真 import 了 `npc_life`（且是用 `_mod` 别名那种写法）',
      'from modules import npc_life as npc_life_mod' in MAIN_SRC)


def _method_ast(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _calls(node):
    out = set()
    if node is None:
        return out
    for x in ast.walk(node):
        if isinstance(x, ast.Call):
            f = x.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    return out


_um = _method_ast(_MAIN_T, 'update_movement')
check('B5 ★ `update_movement` 里**真调用**了 `_npc_life_tick`'
      '（不是只定义了函数 —— 本项目最贵的坑）',
      _um is not None and '_npc_life_tick' in _calls(_um))
check('B5b 调用点与 `npc_placement_tick` / `_ghost_tick` **同一个函数**'
      '（同一处钩子；早退分支之前，睡着了也过日子）',
      _um is not None and {'_npc_life_tick', 'npc_placement_tick',
                           '_ghost_tick'} <= _calls(_um))

_nsp = _method_ast(_MAIN_T, 'npc_system_prompt')
_life_kw = False
if _nsp is not None:
    for x in ast.walk(_nsp):
        if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) \
                and x.func.attr == 'build_system_prompt':
            if any(k.arg == 'life' for k in x.keywords):
                _life_kw = True
check('B6 ★ `npc_system_prompt` 调 `build_system_prompt` 时**真的带了 `life=`**'
      '（少这一个 kwarg，生活块就永远进不了 prompt）', _life_kw)

_bsp = None
for n in _MAIN_T.body:
    pass
_pp_T = ast.parse(source_of(NPC_PERSONA))
for n in ast.walk(_pp_T):
    if isinstance(n, ast.FunctionDef) and n.name == 'build_system_prompt':
        _bsp = n
_has_param = _bsp is not None and 'life' in [a.arg for a in _bsp.args.args]
_appended = False
if _bsp is not None:
    # ⚠️ 判据别写死"测试必须是一个裸 Name"：实际写法是
    #   `if isinstance(life, str) and life.strip():` —— test 是 **BoolOp**，
    #   只认 `ast.Name` 会漏判成 FAIL（本轮首跑就栽在这：判据过窄 ⇒ 误报）。
    #   正确做法 = 在 test 子树里找**有没有出现 `life` 这个名**。
    for x in ast.walk(_bsp):
        if isinstance(x, ast.If):
            _names = {n.id for n in ast.walk(x.test) if isinstance(n, ast.Name)}
            if 'life' in _names:
                if any(isinstance(y, ast.Call) and isinstance(y.func, ast.Attribute)
                       and y.func.attr == 'append' for y in ast.walk(x)):
                    _appended = True
check('B7 `build_system_prompt` 有 `life` 形参，且 `life` **真进了 parts**（不是收了不用）',
      _has_param and _appended)

_nspk = _method_ast(_MAIN_T, 'npc_speak')
check('B8 ★ `npc_speak` 里真调了 `transmit`（说完一句就转告同场的另一位）',
      _nspk is not None and 'transmit' in _calls(_nspk))

check('B9 负控制：`npc_life` 里没有 Qt / 没有项目内 import（零依赖的硬证据）',
      not any(k in LIFE_SRC for k in ('QTimer', 'QWidget', 'QPixmap', 'PyQt'))
      and 'from modules' not in LIFE_SRC and 'import modules' not in LIFE_SRC)


# ==========================================================================
print('=' * 74)
print('C 行为面（真 import 真跑，不是读字面量）')
print('=' * 74)


def _index_keys():
    """→ `(真场景, 章键, 区域键, 松口径)`。

    真场景 = 住在 `areas[*].scenes` 里的键 + 旧式**自带 `file`** 的锚点场景。
    ★ 松口径 = 带 `file` **或** `name` 的节点键 —— 会把**章名 / 区域名**一起收进来
      （实测多 37 个：5 章名 + 32 区域名）。本套件**故意**用松口径跑（宁可多跑几个
      名字也别漏真场景），但 C1b 钉住"差集只含名字、一个真场景都不漏"，
      **不让口径与措辞打架**（上一版措辞写"全部场景 id"而实际收了章/区域名）。
    """
    d = read_json(INDEX)
    scenes, areas, loose = set(), set(), set()

    def _walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, dict):
                    if isinstance(v.get('scenes'), dict):
                        areas.add(k)
                        scenes.update(v['scenes'].keys())
                    if 'file' in v:
                        scenes.add(k)
                    if 'file' in v or 'name' in v:
                        loose.add(k)
                    _walk(v)
                elif isinstance(v, list):
                    _walk(v)
        elif isinstance(o, list):
            for x in o:
                _walk(x)
    _walk(d.get('chapters') or {})
    return scenes, set((d.get('chapters') or {}).keys()), areas, loose


_SCENES, _CH_KEYS, _AREA_KEYS, _LOOSE = _index_keys()
_IDS = sorted(_LOOSE)          # ★ 用松口径跑（更严）；真场景数另算，供 C1b/C2 说清
# ★ 第80轮：`OMITTED` 类禁词（`room`/`light`/`square`/`street` …）供 C/D 两段共用，
#   提前到此处定义（原本只在 D 段才建，C2b2 会用到）。
_om_b = set(L.banned_tokens('OMITTED'))
_bad = []
_has = 0
_ta = collections.Counter()
for _sid in _IDS:
    try:
        _r = L.scene_traits(_sid)
    except Exception as e:
        _bad.append((_sid, repr(e)))
        continue
    if not isinstance(_r, tuple) or len(_r) > L.MAX_TRAITS:
        _bad.append((_sid, 'shape=%r' % (_r,)))
    if any(t not in L.TRAITS for t in _r):
        _bad.append((_sid, 'unknown trait'))
    if _r:
        _has += 1
        for t in _r:
            _ta[t] += 1
check('C1 对 `_index.json` 的**全部 %d 个 id 键**（真场景 %d + 章/区域名 %d）真跑 '
      '`scene_traits`：不抛、形状合法、档位都在枚举内'
      % (len(_IDS), len(_SCENES), len(_LOOSE) - len(_SCENES)),
      _IDS and not _bad, str(_bad[:2] or '(全通过)'))
check('C1b ★ 口径诚实：松口径 ⊇ 真场景，且差集**全部**是章名/区域名 —— 一个真场景都不漏',
      bool(_SCENES) and _SCENES <= _LOOSE
      and (_LOOSE - _SCENES) <= (_CH_KEYS | _AREA_KEYS),
      '真场景=%d 松口径=%d 差集=%d（章 %d / 区域 %d）'
      % (len(_SCENES), len(_LOOSE), len(_LOOSE - _SCENES),
         len(_CH_KEYS), len(_AREA_KEYS)))

# ★ 报告/结论一律以**真场景口径**为准（松口径会把"forest"这类区域名算成一次命中）。
_ta_p = collections.Counter()
_none_p = 0
for _sid in sorted(_SCENES):
    _r = L.scene_traits(_sid)
    if _r:
        for t in _r:
            _ta_p[t] += 1
    else:
        _none_p += 1
check('C2 有场景真命中（不是"全空集"）', _has > 0,
      '松口径 命中=%d/%d；★真场景口径 无特质=%d/%d 分布=%s'
      % (_has, len(_IDS), _none_p, len(_SCENES), dict(_ta_p)))

# ★★★ 第77轮改：原判据把 `ruined` 也列进"必须零命中" —— 那条在**第73轮**是对的
#   （当时 `_index.json` 只有 Deltarune，一个 `ruin` 都命不中）。
#   第77轮把 UT / 黄魂 迁入后，UT 的「废墟」区域（`room_ruins1`…）**真的命中 35 处**
#   ⇒ 契约已把 `ruined` 从 `TRAIT_TOKENS_RESERVED` **转正**进 `TRAIT_TOKENS`。
#   ⇒ 判据同步改：`ruined` 改为**必须 > 0**（能力真到位），
#     并新增"预留表里不许再留着 ruined"（防两处都有 = 两个真相）。
#
# ★★★ 第80轮再改（同机制）：OneShot 263 场景迁入 ⇒ `bright`/`cosmic` **不再是零命中**：
#   · `bright` 由 `sun`（`Sunroom` / `basement_after_sun`）兑现 3 处；
#   · `cosmic` 由 `sky`（`Red_sky` / `POSTGAME_RED_SKY`）兑现 2 处。
#   旧断言"`cosmic`/`bright` 仍零命中"**已过时** ⇒ 改为**随事实**：
#   **必须 > 0**（能力真到位，但只由**转正令牌**兑现；预留槽仍不许命中，
#   该点由 C2b2 单独把守 —— 防"假装覆盖了全部明亮与宇宙"）。
check('C2b ★★ 第80轮转正：`bright` / `cosmic` 现网 **必须 > 0 命中**'
      '（OneShot 的 `sun` / `sky` 已迁入）',
      all(_ta_p.get(_t, 0) > 0 for _t in ('bright', 'cosmic')),
      'bright=%d cosmic=%d（第73/77轮时均为 0）'
      % (_ta_p.get('bright', 0), _ta_p.get('cosmic', 0)))
# ★ 正/负控制成对：能力**只**由转正令牌兑现，预留槽**仍 0 命中**（没偷偷扩大覆盖）。
_res_leak80 = [tok for _t in ('bright', 'cosmic')
               for tok in L.TRAIT_TOKENS_RESERVED.get(_t, ())
               if tok not in _om_b and any(L._token_hits(tok, s) for s in _IDS)]
_live_bc80 = set(L.TRAIT_TOKENS.get('bright', ())) | set(L.TRAIT_TOKENS.get('cosmic', ()))
check('C2b2 ★ 如实：`bright`/`cosmic` 只由转正令牌 `sun`/`sky` 兑现，'
      '预留槽不许偷偷命中（不许假装覆盖了全部明亮与宇宙）',
      not _res_leak80 and _live_bc80 <= {'sun', 'sky'},
      'live=%r res_leak=%r' % (sorted(_live_bc80), _res_leak80))
check('C2c ★★ 第77轮转正：`ruined` 现网 **必须 > 0 命中**（UT 废墟区域已迁入）',
      _ta_p.get('ruined', 0) > 0,
      'ruined 命中 %d（第73轮时为 0）' % _ta_p.get('ruined', 0))
# ★★ 判据本身也复检：第一版写的是"`ruined` 键名不许同现两表" ⇒ **过严**
#   （正确形状恰恰是：本位表放实测命中的 `ruin`/`ruined`，预留表放同义但零命中的
#    `broken`/`wreck`/… ⇒ **键名相同、令牌不重叠**）。真正该守的是**令牌集不相交**。
_overlap = {t: sorted(set(L.TRAIT_TOKENS.get(t, ()))
                      & set(L.TRAIT_TOKENS_RESERVED.get(t, ())))
            for t in set(L.TRAIT_TOKENS) | set(L.TRAIT_TOKENS_RESERVED)}
_overlap = {t: v for t, v in _overlap.items() if v}
check('C2d ★ 无第二份真相：同位表与预留表的**令牌集不许相交**',
      not _overlap
      and bool(L.TRAIT_TOKENS.get('ruined'))
      and bool(L.TRAIT_TOKENS_RESERVED.get('ruined')),
      '重叠=%r live_ruined=%r res_ruined=%r'
      % (_overlap, L.TRAIT_TOKENS.get('ruined'),
         L.TRAIT_TOKENS_RESERVED.get('ruined')))

# 边界规则：正/负控制成对
for _tok, _txt, _want in (
        ('ash', 'ch1.forest.forest_afterthrash2', False),
        ('night', 'ch4.dw_church_knightclimb', False),
        ('cave', 'ch5.dw_cliff_shicave', True),
        ('dark', 'ch1.dark_world.dark1', True),
        ('town', 'castle_town', True),
        ('home', 'ch1.home.krishallway', True)):
    check('C3 边界规则 %s：`%s` ⇒ %s' % ('正控制' if _want else '负控制', _tok, _want),
          L._token_hits(_tok, _txt) is _want, _txt)

_hits_ok = True
for _sid in _IDS[:120]:
    for _t, _ws in L.trait_hits(_sid).items():
        for _w in _ws:
            if not L._token_hits(_w, _sid):
                _hits_ok = False
check('C4 可解释：`trait_hits` 报出的每个命中词都能**按规则在原文里找到**（不许报假账）',
      _hits_ok)

check('C5 无命中 ⇒ `()`（不猜）；`max_traits<=0` ⇒ `()`；`max_traits=1` ⇒ 最多 1 个',
      L.scene_traits('zzz_qqq_nothing') == ()
      and L.scene_traits('ch1.home.town_church', max_traits=0) == ()
      and len(L.scene_traits('ch1.home.town_church', max_traits=1)) <= 1,
      str(L.scene_traits('ch1.home.town_church')))
check('C6 `trait_hint(())` == ""（不产空块）；非空时带【你周围】前缀且**不含台词示范**',
      L.trait_hint(()) == '' and L.trait_hint(('dark',)).startswith('【你周围】')
      and '真黑' not in L.trait_hint(('dark',)))

# ---- Bonds ----
_b = L.Bonds()
for _i in range(3):
    _b.meet('a', 'b', 0.3)
check('C7 ★ 熟络度**对称**：`get(a,b) == get(b,a)`（无向键，结构上不可能分叉）',
      _b.get('a', 'b') == _b.get('b', 'a') and _b.pairs() == [('a', 'b')],
      str(_b.pairs()))
check('C7b 自反 / 空 / 非字符串 ⇒ 不建键（`pair_key` 返回 None；`get` 返回 0.0）',
      L.pair_key('a', 'a') is None and L.pair_key('', 'b') is None
      and L.pair_key(None, 'b') is None and _b.get('a', 'a') == 0.0)
check('C8 封顶 1.0（`meet` 超额后不越界）', _b.meet('a', 'b', 5.0) == 1.0)
_b3 = L.Bonds()
_b3.meet('x', 'y', 0.1)
check('C9 `seed` 不覆盖已有记录 / 新键可写入',
      _b3.seed('x', 'y', 0.9) is False and _b3.get('x', 'y') == 0.1
      and _b3.seed('x', 'z', 0.4) is True and _b3.get('x', 'z') == 0.4,
      'x-y=%.2f x-z=%.2f' % (_b3.get('x', 'y'), _b3.get('x', 'z')))
_b4 = L.Bonds()
_b4.meet('p', 'q', 0.25)
_b4.meet('p', 'r', 0.55)
check('C10 `known()` 按熟络度**降序**、同分按 id 升序 ⇒ 稳定；阈值可调',
      _b4.known('p') == ['r', 'q'] and _b4.known('p', threshold=0.5) == ['r'],
      str(_b4.known('p')))
check('C11 `to_dict` / `from_dict` 往返守恒（键用 `|` 拼，读回仍**对称**）',
      L.Bonds.from_dict(_b4.to_dict()).get('r', 'p') == _b4.get('p', 'r'))


# ---- transmit ----
class _Mem(object):
    """最小 MiniMemory 形状（只实现本模块用到的三个方法）。"""

    def __init__(self):
        self.d = {}
        self.calls = []

    def history(self, i):
        return list(self.d.get(i, ()))

    def remember(self, i, t, who='player', scene=None):
        self.calls.append((i, t, who))
        self.d.setdefault(i, []).append({'who': who, 'text': t, 'scene': scene})
        return True


_m = _Mem()
_m.remember('sans', '这地方真黑', who='player')
_m.remember('sans', '你是谁', who='player')
_m.remember('sans', '我改主意了', who='toriel')      # 对方自己说的 ⇒ 不该被"转告"
_n = L.transmit(_m, 'sans', 'toriel')
check('C12 传话：只传 `limit` 条、**带署名**（`who == src`）、且跳过对方自己说的那句',
      _n == 2 and [e['who'] for e in _m.d['toriel']] == ['sans', 'sans']
      and '我改主意了' not in [e['text'] for e in _m.d['toriel']],
      'n=%d dst=%s' % (_n, [e['text'] for e in _m.d['toriel']]))
check('C12b ★ **不共享容器**：src 与 dst 是两条独立的列表（改一条不影响另一条）',
      _m.d['sans'] is not _m.d['toriel']
      and len(_m.d['sans']) == 3 and len(_m.d['toriel']) == 2)
check('C13 负控制：自传 / 非法 id / 空记忆 / `limit<=0` ⇒ 0（都不是错误）',
      L.transmit(_m, 'sans', 'sans') == 0
      and L.transmit(_m, '', 'toriel') == 0
      and L.transmit(_m, 'nobody', 'toriel') == 0
      and L.transmit(_m, 'sans', 'toriel', limit=0) == 0
      and L.transmit(None, 'sans', 'toriel') == 0)
_m2 = _Mem()
_m2.remember('a', '我来过这里')
_m3 = _Mem()
_m3.remember('a', '这句是你自己说的', who='b')
check('C13b 负控制：目标侧的记忆为空 ⇒ 能传 1 条；'
      '源里只剩"对方说的"那一条 ⇒ 传 0 条',
      L.transmit(_m2, 'a', 'b') == 1 and L.transmit(_m3, 'a', 'b') == 0,
      'dst_b=%s' % ([e['text'] for e in _m2.d.get('b', [])],))

# ---- LifeLoop ----
_loop = L.LifeLoop(min_gap=0.0)
_s1 = _loop.tick(0.0, ['a', 'b'])
check('C14 节拍：`tick` 返回一位；**busy 期间再 tick 恒 None**（不并发）',
      _s1 in ('a', 'b') and _loop.tick(0.0, ['a', 'b']) is None, str(_s1))
_ok, _reason = _loop.finish(0.0, _s1)
_s2 = _loop.tick(0.0, ['a', 'b'])
check('C15 ★ 下一个 speaker **绝不等于**上一个（不出现自己跟自己聊）',
      _ok and _reason == '' and _s2 is not None and _s2 != _s1,
      '%s -> %s' % (_s1, _s2))
_loop.abort(1.0)
_s3 = _loop.tick(1.0, ['a', 'b'])
check('C16 `abort` **解锁**且**不推进**轮转（下次还是同一位 —— 不是他的错）',
      _s3 == _s2, '%s vs %s' % (_s3, _s2))

_loopG = L.LifeLoop(min_gap=0.0)
for _i in range(L.MAX_CONSECUTIVE_FAILURES):
    _loopG.tick(0.0, ['a', 'b'])
    _loopG.abort(0.0)
check('C17 ★ **反活锁**：连续失败到阈值后 `tick` 恒 None（不空转烧 CPU）',
      _loopG.fail_count >= L.MAX_CONSECUTIVE_FAILURES
      and _loopG.tick(99.0, ['a', 'b']) is None,
      'fails=%d' % _loopG.fail_count)
check('C17b 正控制：重新 `reset` 后又能开口（证明上面不是"坏了就永远不说话"）',
      _loopG.reset(keep_turns=False).tick(200.0, ['a', 'b']) is not None)

_gate_state = {'ok': False}
_loopH = L.LifeLoop(min_gap=0.0, gate=lambda: _gate_state['ok'])
check('C18 ★ 让路闸：`gate` 返回假 ⇒ 不开口，**且不推进轮转**'
      '（被让路的是这一次机会，不是这个人）',
      _loopH.tick(0.0, ['a', 'b']) is None and _loopH.turns == 0
      and _loopH.pending_id is None)
_gate_state['ok'] = True
check('C18b 正控制：闸放开后立刻能开口（证明上面不是"永远不开"）',
      _loopH.tick(0.0, ['a', 'b']) is not None)
check('C18c `gate` 抛异常 ⇒ 当作不允许（不把宿主带崩）',
      L.LifeLoop(min_gap=0.0, gate=lambda: (_ for _ in ()).throw(RuntimeError('x'))
                 ).tick(0.0, ['a', 'b']) is None)
check('C19 单人（`allow_solo=False`）⇒ 不开口；`allow_solo=True` ⇒ 可以',
      L.LifeLoop(min_gap=0.0).tick(0.0, ['a']) is None
      and L.LifeLoop(min_gap=0.0, allow_solo=True).tick(0.0, ['a']) == 'a')
_mis = L.LifeLoop(min_gap=0.0)
_x = _mis.tick(0.0, ['a', 'b'])
_mis.finish(0.0, 'zzz' if _x != 'zzz' else 'yyy')
check('C20 张冠李戴（`from_id` != 预期）⇒ 记账 `speaker_mismatch`，但**仍然解锁并推进**'
      '（卡死比错一次更严重）',
      _mis.mismatch_count == 1 and _mis.busy is False and _mis.turns == 1)

_lines_pool = ['一', '二', '三']
_u = None
_seen = []
for _i in range(3):
    _line, _u = L.pick_line(_lines_pool, _u)
    _seen.append(_line)
_line4, _u4 = L.pick_line(_lines_pool, _u)
check('C21 内置台词池：一圈内**不重复**；走完一圈自动开新圈；空池 ⇒ ("", 原集合)',
      sorted(_seen) == sorted(_lines_pool) and _line4 == _lines_pool[0]
      and L.pick_line([], None) == ('', set()))


# ==========================================================================
print('=' * 74)
print('D 镜像 / 出处（令牌必须真的能在数据里落地）')
print('=' * 74)

_zero_pos = [(t, tok) for t, toks in L.TRAIT_TOKENS.items() for tok in toks
             if not any(L._token_hits(tok, s) for s in _IDS)]
check('D1 ★ 本位令牌**逐条**在现网 ≥1 命中（零命中的令牌 = 虚假宣传一项不存在的能力）',
      not _zero_pos, str(_zero_pos[:3] or '(全命中)'))

# ★ 第80轮：OneShot 263 场景迁入 ⇒ `sun`/`sky` 实测命中且**语义正确** ⇒ 转正；
#   `square`/`street` 实测命中但**语义错位**（几何方形 / 街名）⇒ 移入 BANNED('OMITTED')。
#   ⇒ 预留表判据改为**随事实**：逐条仍必须 0 命中，但先把已扬弃的禁词排除
#     （禁词不许出现在任何表 → 自然也不该被当作"预留"来数）。
_nz_res = [(t, tok, sum(1 for s in _IDS if L._token_hits(tok, s)))
           for t, toks in L.TRAIT_TOKENS_RESERVED.items() for tok in toks
           if tok not in _om_b and any(L._token_hits(tok, s) for s in _IDS)]
check('D2 预留令牌**逐条**现网 == 0 命中（不许拿它们混进本位凑数字；第80轮起禁词已排除）',
      not _nz_res, str(_nz_res[:3] or '(全 0)'))

_all_tok = set()
for _mapi in (L.TRAIT_TOKENS, L.TRAIT_TOKENS_RESERVED, L.TRAIT_WORDS_CN):
    for _v in _mapi.values():
        _all_tok |= set(_v)
_omitted_in = [t for t in L.banned_tokens('OMITTED') if t in _all_tok]
check('D3 `OMITTED` 类禁词（room / light / square / street）**不在任何令牌表里**'
      '（这类靠"没人往表里写"挡 + 第80轮起运行期也硬过滤，匹配规则挡不住）',
      not _omitted_in, str(_omitted_in))
check('D3b `SUBSTRING` 类禁词（ash / night）被匹配规则挡住（负控制）',
      all(L._token_hits(t, 'x_afterthrash2 knightclimb') is False
          for t in L.banned_tokens('SUBSTRING')))
check('D3c ★ 第80轮负控制：`OMITTED` 禁词即使被硬塞进令牌表，`_match_terms`/`trait_hits`'
      '也**进不了匹配**（运行期过滤，不依赖人自觉）',
      all(w not in L._match_terms('crowded') for w in ('square', 'street'))
      and all(w not in L._match_terms('crowded', use_reserved=True)
              for w in L.banned_tokens('OMITTED'))
      and not L.trait_hits('x_vendor_street x_house_squares',
                           use_reserved=True).get('crowded'))
check('D3b `SUBSTRING` 类禁词（ash / night）被匹配规则挡住（负控制）',
      all(L._token_hits(t, 'x_afterthrash2 knightclimb') is False
          for t in L.banned_tokens('SUBSTRING')))
_spr = os.path.join(PET, 'assets', 'sprites')
_dirs = set()
if os.path.isdir(_spr):
    _dirs = {d for d in os.listdir(_spr) if os.path.isdir(os.path.join(_spr, d))}
check('D4 `PRODUCTION_PREFIXES` 的作品都真有贴图目录（前缀不是编的）',
      {p[:-1] for p in NS.PRODUCTION_PREFIXES} <= _dirs,
      '前缀=%s 目录=%s' % ([p[:-1] for p in NS.PRODUCTION_PREFIXES], sorted(_dirs)))

check('D5 `production_of` 正负控制：`ut_sans`→ut / `ot_toriel`→ot / `ralsei`→dr / '
      '`hy_flowey`→hy / `os_niko`→os / 空 ⇒ ""',
      NS.production_of('ut_sans') == 'ut' and NS.production_of('ot_toriel') == 'ot'
      and NS.production_of('ralsei') == NS.DEFAULT_PRODUCTION
      and NS.production_of('hy_flowey') == 'hy' and NS.production_of('os_niko') == 'os'
      and NS.production_of('') == '')


# ==========================================================================
print('=' * 74)
print('E 产品接线（真机：RalseiPet() + 停掉全部定时器）')
print('=' * 74)

from PyQt5.QtWidgets import QApplication                     # noqa: E402

import main as M                                             # noqa: E402

_app = QApplication.instance() or QApplication([])
_pet = M.RalseiPet()
for _a in ('animation_timer', 'ai_timer', 'stats_timer', 'dialogue_init_timer',
           'auto_mouse_drag_timer', 'api_control_timer', 'placeholder_timer',
           'movement_timer', 'mouse_drag_timer', '_bounce_timer',
           '_hide_search_timer'):
    _t = getattr(_pet, _a, None)
    try:
        if _t is not None:
            _t.stop()
    except Exception:
        pass
# 夹具：本地模型不可用 + 换掉这个实例的记忆后端。
# ⚠️ **第74轮 B11 更正**：这里原来写"绝不碰用户的 E:\RalseiMemory 保管库" —— 是**假的**。
#   上面 `RalseiPet()` 构造时已经解析并建过真实保管库（日志里那行
#   `记忆落盘=E:\RalseiMemory\npc_memory` 就是它），这一行只是**构造之后**的补救。
#   真隔离 = `run_all.HERMETIC_IDS` 注入的 `RALSEI_MEMORY_DIR`。
_pet.api_enabled = False
_pet._npc_invited = []
_pet.npc_memory = NP.MiniMemory(root=None)

check('E1 ★ 真机：自由生活三件套都建起来了（契约 / 熟络度 / 节拍器）',
      isinstance(_pet.npc_crossworld, dict) and bool(_pet.npc_crossworld)
      and _pet.npc_bonds is not None and _pet.npc_life is not None,
      'cross keys=%d bonds=%s loop=%s' % (len(_pet.npc_crossworld or {}),
                                          type(_pet.npc_bonds).__name__,
                                          type(_pet.npc_life).__name__))
check('E2 ★ 真机：AU 配对从契约推出来了（非空），且**不含**同名的一对',
      bool(_pet._npc_au_pairs)
      and frozenset(('ot_toriel', 'toriel')) not in _pet._npc_au_pairs,
      'n=%d' % len(_pet._npc_au_pairs))
check('E3 ★ 真机：熟络度初值三档实测（同 AU 0.55 / 同作品 0.30 / 跨作品 0.0）',
      _pet._npc_seed_lookup('ut_sans', 'ot_sans') == L.SEED_SAME_AU_TWIN
      and _pet._npc_seed_lookup('ut_sans', 'ut_papyrus') == L.SEED_SAME_PRODUCTION
      and _pet._npc_seed_lookup('ralsei', 'ut_sans') == L.SEED_STRANGER,
      '%s / %s / %s' % (_pet._npc_seed_lookup('ut_sans', 'ot_sans'),
                        _pet._npc_seed_lookup('ut_sans', 'ut_papyrus'),
                        _pet._npc_seed_lookup('ralsei', 'ut_sans')))
check('E3b ★ 真机：同名**不**享受 AU 加速（`ut_toriel` ↔ `toriel` = 跨作品 0.0）',
      _pet._npc_seed_lookup('ut_toriel', 'toriel') == L.SEED_STRANGER)

# 场景反应：把"当前场景"指到一个**真带特质**的场景（`_npc_scene_id()` 读
# `_scene_state.scene_id`），再看生活块里有没有【你周围】。
# ⚠️ 用最小桩对象而不是 monkeypatch 方法：`_npc_scene_id` 走的是
#    `self.__dict__['_scene_state'].scene_id`，喂一个只有 `scene_id` 的对象就够，
#    被测的仍然是**产品真代码路径**。
class _SceneStub(object):
    def __init__(self, sid):
        self.scene_id = sid


_pet._scene_state = _SceneStub('ch1.home.town_church')
# 目标 NPC 要有**人设**（`ralsei` 是桌宠本体，不在 `npc_personas` 里 ⇒
# `npc_system_prompt` 对它恒返回 ''），所以用一位真装了设定的主线 NPC。
TARGET = 'toriel'
_blk = _pet._npc_life_blocks(TARGET)
check('E4 ★ 真机：`_npc_life_blocks` 对真场景产出【你周围】块'
      '（用户那句"能对场景有反应"的落地）',
      '【你周围】' in _blk, _blk.replace('\n', ' | ')[:150])

# 熟络度 → 【你认识谁】
_pet.npc_bonds.meet(TARGET, 'susie', 0.5)
_blk2 = _pet._npc_life_blocks(TARGET)
check('E4b ★ 真机：够熟的人在【你认识谁】里出现（写**显示名**，不写 id）',
      '【你认识谁】' in _blk2 and '苏西' in _blk2, _blk2.replace('\n', ' | ')[:200])
_leak = [w for w in LEAK_WORDS if w in _blk2]
check('E4c ★★ 真机：生活块里**不含**任何作品归属 / 版本 / 内部字段名'
      '（用户那句"怪物之间没有身份标识，得自己判断"）',
      not _leak, '泄露=%s' % (_leak or '(无)'))

_sp = _pet.npc_system_prompt(TARGET)
check('E5 ★ 真机：`npc_system_prompt` 里真带上了生活块（端到端）',
      bool(_sp) and '【你认识谁】' in _sp,
      # ★ 第74轮（B11）：**不打印长度** —— 同一份 prompt 的长度会被"真实天气"
      #   （`_build_npc_context` 拼进 system）和时段带着走，长度不是判据本体。
      '有生活块=%s' % ('【你认识谁】' in (_sp or '')))

_pet._npc_talking = None
_g1 = _pet._npc_life_gate()
_pet._npc_talking = 'ralsei'
_g2 = _pet._npc_life_gate()
_pet._npc_talking = None
check('E6 ★ 真机：让路闸正负成对（空闲 ⇒ True；正跟用户说话 ⇒ False）',
      _g1 is True and _g2 is False, 'idle=%s talking=%s' % (_g1, _g2))

# ---- 自主开口：真跑 ----
_pet._scene_state = None
_pet._npc_seed_bodies(LIVE_SCENE)
_ids = _pet._npc_life_ids()
_plain = _pet._npc_plain_ids(_ids)
check('E7 ★ 真机：`%s` 播下了 >=2 位纯 NPC（现网**唯一**能跑自主闲聊的场景）'
      % LIVE_SCENE, len(_ids) >= 2 and len(_plain) >= 2,
      'bodies=%s plain=%s' % (_ids, _plain))
_before = {n: len(_pet.npc_memory.history(n)) for n in _plain}
_spoke = _pet._npc_life_tick(0.1)
_a = _spoke[0] if _spoke else None
check('E7b ★★ 真机：`_npc_life_tick` **真的开了一次口**（零模型成本，取内置台词）',
      bool(_spoke) and _a in _plain,
      'spoke=%s' % (_spoke,))
check('E7c ★ 真机：那句**进了他自己的记忆**（`who` 是他自己 —— 他自己说的）',
      bool(_a) and len(_pet.npc_memory.history(_a)) > _before.get(_a, 0)
      and _pet.npc_memory.history(_a)[-1]['who'] == _a,
      str(_pet.npc_memory.history(_a)[-1] if _a else None))
_other = [n for n in _ids if n != _a]
_trans = _pet.npc_memory.history(_other[0]) if _a and _other else []
check('E7d ★★ 真机：那句**传给了同场的另一位**（带署名 = 说话人 id，不共享容器）',
      bool(_trans) and _trans[-1]['who'] == _a,
      str(_trans[-1] if _trans else None))
check('E7e 负控制：只有 1 位纯 NPC 在场时**不开口**'
      '（把另一位挪走，`tick` 必须返回空）',
      (lambda: (_pet.npc_bodies.pop(_other[0], None),
                _pet._npc_life_tick(999.0))[-1] == [])(),
      'remaining=%s' % list(_pet.npc_bodies))

# ---- npc_speak 的转话接线（不联网：api_enabled=False ⇒ 记忆已写、转话已发生）----
# ⚠️ 夹具用**手搭的在场表**（`_npc_life_ids()` 只读 `npc_bodies.keys()`，值不参与），
#    因为要的是"两位都装了人设的主线 NPC" —— `npc_speak` 对没设定的人会**明确拒绝**
#    （这正是它该做的事），拿纯 NPC 来测会把"拒绝"误读成"转话没接上"。
_pet._scene_state = _SceneStub(LIVE_SCENE)
_pet.npc_bodies = {'susie': None, 'toriel': None}
_pet.npc_memory = NP.MiniMemory(root=None)
_SPEAKER, _LISTENER = 'susie', 'toriel'
_pet.npc_speak(_SPEAKER, '你看见我的钥匙了吗', lambda x: None)
_A = _pet.npc_memory.history(_SPEAKER)
_B = _pet.npc_memory.history(_LISTENER)
check('E8 ★ 真机：跟 A 说一句 ⇒ A 的记忆里有它（`who=player`）+ '
      '**B 的记忆里也有"A 说过"这条**（`npc_speak` 的转话接线）',
      any(e['who'] == 'player' and e['text'] == '你看见我的钥匙了吗' for e in _A)
      and bool(_B) and _B[-1]['who'] == _SPEAKER,
      'A=%d B=%s' % (len(_A), _B[-1] if _B else None))
check('E8b ★ 负控制：B 那条的 `who` **是 A**（带着来源），不是 `player`'
      '（"我知道了"与"A 说过"必须能分开）',
      bool(_B) and _B[-1]['who'] != 'player')


# ==========================================================================
print('=' * 74)
print('F 诚实判据：只准把真接线的写成 wired')
print('=' * 74)
_w = CROSSJ['wiring']
_wired = set(_w.get('wired') or [])
check('F1 台账：五块已接线（roam + 第73轮四块），`visitor` 仍 spec_only',
      _wired == {'roam', 'twin_groups', 'identity_blind', 'familiarity_seed',
                 'scene_traits'} and (_w.get('spec_only') or []) == ['visitor'],
      'wired=%s spec_only=%s' % (sorted(_wired), _w.get('spec_only')))
check('F1b 每一项 wired 都带 `used_by`（谁在用）+ `wired_how`（接到什么程度）',
      all(CROSSJ.get(k, {}).get('used_by') and CROSSJ.get(k, {}).get('wired_how')
          for k in _wired))
check('F2 ★★★ 台账随事实推进：「主线 NPC 自主开口」**已从 not_yet 移进 wired**'
      '（第86轮接入）—— 判据**加强**：不仅要求它现在在 wired，还要求 not_yet 里**不再有**它'
      '（防"接完了台账却忘了搬"，那种"写得漂亮但和事实脱节"的台账）',
      any('主线 NPC' in x and ('自主' in x or '自发' in x)
          for x in (CROSSJ['round73'].get('wired') or []))
      and not any('主线 NPC' in x and ('自主' in x or '自发' in x)
                  for x in (CROSSJ['round73'].get('not_yet') or [])),
      'wired=%d not_yet=%d' % (len(CROSSJ['round73'].get('wired') or []),
                               len(CROSSJ['round73'].get('not_yet') or [])))
check('F3 ★ `scene_traits.wired_how` 必须**写明** ruined/cosmic 的覆盖实况'
      '（第77轮记 ruined 转正、第80轮记 bright/cosmic 转正 —— 不许含糊地宣称"全覆盖"）',
      all(k in (CROSSJ['scene_traits'].get('wired_how') or '')
          for k in ('ruined', 'cosmic')),
      'len=%d' % len(CROSSJ['scene_traits'].get('wired_how') or ''))
check('F4 契约里有 `round73` 段，记着本轮接了哪四件、还差哪三件',
      isinstance(CROSSJ.get('round73'), dict)
      and bool(CROSSJ['round73'].get('wired')) and bool(CROSSJ['round73'].get('not_yet')))


# ==========================================================================
print('=' * 74)
print('G 判据自身体检')
print('=' * 74)

_hook = []


def _hookcheck(cond):
    if not cond:
        _hook.append('x')


_hookcheck(False)
check('G1 记账口不是 no-op（真造一个 False 会进账）', _hook == ['x'])
check('G2 恒真体检：`存在` 与 `不存在` 两条判断结论必须不同'
      '（`A in rev[B]` 那种恒真不入册）',
      os.path.isfile(LIFE) is not os.path.isfile(os.path.join(MODULES, '__nope73__.py')))
_bad_lines = [l for l in _LINES
              if len([1 for t in ('[PASS]', '[FAIL]') if t in l]) != 1]
check('G3 已打印的 %d 行里每行**恰好一个**标记（判据名不许自带标记）' % len(_LINES),
      not _bad_lines and len(_LINES) == NCHECK, '多标记行=%s' % (_bad_lines[:2],))

print('')
print('---- 第73轮 自由生活锁：%d 项判据，FAIL=%d ----' % (NCHECK, len(FAILS)))
if FAILS:
    for f in FAILS:
        print('   FAIL: %s' % f)
sys.exit(0 if not FAILS else 1)

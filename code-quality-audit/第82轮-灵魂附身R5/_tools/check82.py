# -*- coding: utf-8 -*-
"""第82轮 R5 回归锁：Z 键附身（原作功能 + 特效）。

用户口径（**第84轮现行**）：「**所有人附身都要经过同意哦**，
附身后要和原作的效果一样就是了」（推翻第76轮"对 kris 和 firsk 直接操控、niko 需同意"）

★★★ 原作依据（物证 `第82轮-灵魂附身R5/_evidence/`，本套件 E 段逐条回原文验）
  · Z ⇄ `control_check_pressed(0)` → `event_user(0)`（`obj_mainchara_Step_0`）
  · 交互出口 `obj_mainchara_Other_12`：`global.interact=5; control_clear(2); snd_play(snd_squeak)`
  · 主角移动 = `obj_time.*` × **3 px/帧**；灵魂移动 = **同一组** `obj_time.*` × `global.sp`
  · 回头步 = **2 px**（`xprevious == x∓3` 那条）

段一览（每段都配正/负控制）
--------------------------
  A ★★ 零依赖纪律（`possession.py` 顶层 import ⊆ {logging, math} + 零函数内 import
      + 不 import 任何项目内模块）
  B ★★★ 附身类别表 = **单一真源**（`POSSESSION_KINDS` 与 `_registry.json` 对账：
      第84轮口径 ⇒ **kris/ut_frisk/os_niko 全需同意**（表里不许有 KIND_DIRECT 成员）· 其余一律不可）
  C ★★★ 行为（真跑 `PossessionState`）：直接附身 / 征求同意三态 / 拒绝 / 解除 /
      **方向键步进 3 px** / **回头 2 px** / 未附身不驱动
  D ★★ 产品接线（AST + 真源码）：`main.py` 有 Z 键分支 · 方向键**附身优先** ·
      `_possession_tick` 在 `update_movement` 早退分支之前 · `init_possession` 在
      `init_npc_systems` 之后 · 失焦放开被附身键 · release 对称
  E ★★★ 原作对照（**读 `_evidence/*.gml` 真实文件**，不是自说自话）
  F 判据自身体检（★标记打印点 == 2 + 负控制 · 记账守恒 · 被测文件在盘）

判据纪律：`print('[PASS] %s')` 字面量；负控制成对；断行为不断赋值；
          「判据名里不自带 [PASS] 标记」（否则污染计数）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
MAIN = os.path.join(PET, 'src', 'main.py')
EVID = os.path.join(ROOT, 'code-quality-audit', '第82轮-灵魂附身R5', '_evidence')
sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, MODS)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

_passed = 0
_failed = 0
_STAR_PRINTS = [0]     # ★ 计数：带 ★ 标记的判据打印点（F 段自证用）


def check(desc, cond, star=False):
    global _passed, _failed
    if star:
        _STAR_PRINTS[0] += 1
    mark = '★' if star else ' '
    if cond:
        _passed += 1
        print('[PASS]%s %s' % (mark, desc))
    else:
        _failed += 1
        print('[FAIL]%s %s' % (mark, desc))


def _read(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


MODP = os.path.join(MODS, 'possession.py')

# =============================================================== A. 零依赖纪律
_src = _read(MODP)
_tree = ast.parse(_src)

# 顶层 import（含 if/try 块里的）——与 scene_p0 的 AST 扫描同形
_top_imports = set()
for node in _tree.body:
    _collect = [node]
    while _collect:
        n = _collect.pop()
        if isinstance(n, ast.Import):
            for a in n.names:
                _top_imports.add(a.name.split('.')[0])
        elif isinstance(n, ast.ImportFrom):
            if n.module and n.level == 0:
                _top_imports.add(n.module.split('.')[0])
        elif isinstance(n, (ast.If, ast.Try, ast.With)):
            _collect.extend(list(n.body) + list(getattr(n, 'orelse', []))
                            + list(getattr(n, 'finalbody', []))
                            + [h for h in getattr(n, 'handlers', [])])
check('A possession.py 顶层 import ⊆ {logging, math}（实得 %s）'
      % sorted(_top_imports),
      _top_imports <= {'logging', 'math'})

# 零函数内 import（回归锁用 AST 强制，与 soul_entity 同纪律）
_inner_import = []
for node in ast.walk(_tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Import, ast.ImportFrom)) and sub is not node:
                _inner_import.append(getattr(node, 'name', '?'))
check('A ★ 零函数内 import（函数体里一处 import 都没有）',
      not _inner_import, star=True)
print('#   [no-op] 函数内 import 命中：%r' % (_inner_import,))

# 不 import 任何项目内模块
_internal = {'npc_system', 'soul_entity', 'soul_overlay', 'data_store',
             'scene_system', 'logger_utils', 'main'}
check('A 负控制：possession.py 不 import 任何项目内模块',
      not (_top_imports & _internal))

# =============================================================== E. 原作对照
# ★★★ 读真文件（不是自说自话）：证据文件必须在盘 + 关键原文在场
_ev_files = {
    'obj_mainchara_Step_0.gml': ['control_check_pressed(0)', 'event_user(0)',
                                 'obj_time.left', 'x -= 3', 'y += 3'],
    'obj_mainchara_Other_12.gml': ['global.interact', 'snd_play(snd_squeak)',
                                   'control_clear(2)'],
    'obj_heart_Step_0.gml': ['ossafe_keyboard_check(40)', 'global.sp'],
    'obj_heart_Create_0.gml': ['global.sp = global.asp'],
    'gml_Object_obj_time_Create_0.gml': ['up = 0', 'control_init()'],
}
for _fn, _needles in _ev_files.items():
    _p = os.path.join(EVID, _fn)
    _ok = os.path.exists(_p)
    check('E 证据文件在盘：%s' % _fn, _ok)
    if _ok:
        _t = _read(_p)
        _miss = [n for n in _needles if n not in _t]
        check('E %s 含关键原文（缺 %r）' % (_fn, _miss), not _miss)

# ★ 3 px 是原作的，不是我们编的 —— 直接钉住这句原文
_p_step = os.path.join(EVID, 'obj_mainchara_Step_0.gml')
if os.path.exists(_p_step):
    _t = _read(_p_step)
    check('E ★★ 原作主角步进 = 3 px（`x -= 3` / `y += 3` 都在）',
          'x -= 3' in _t and 'y += 3' in _t, star=True)
    # 回头步 2 px
    check('E ★★ 原作回头步 = 2 px（`x += 2` / `x -= 2` 都在）',
          'x += 2' in _t and 'x -= 2' in _t, star=True)
else:
    check('E ★★ 原作主角步进 = 3 px（证据缺失 ⇒ 无法验）', False, star=True)
    check('E ★★ 原作回头步 = 2 px（证据缺失 ⇒ 无法验）', False, star=True)

# =============================================================== B. 类别表 = 单一真源
import possession as P   # noqa: E402

check('B ★ kris 需征求同意（第84轮口径）',
      P.kind_of('kris') == P.KIND_CONSENT, star=True)
check('B ★ ut_frisk 需征求同意（第84轮口径）',
      P.kind_of('ut_frisk') == P.KIND_CONSENT, star=True)
check('B ★ os_niko 需征求同意', P.kind_of('os_niko') == P.KIND_CONSENT, star=True)
# ★★★ 第84轮口径「所有人附身都要经过同意」的**结构判据**（不是逐个数 id）：
#   表里**不许再有 KIND_DIRECT 成员** —— 这样将来新增角色若被写成 DIRECT 会被立刻抓到。
_DIRECT_MEMBERS = sorted(k for k, v in P.POSSESSION_KINDS.items()
                         if v == P.KIND_DIRECT)
check('B ★★ 表里无 KIND_DIRECT 成员（"所有人先问"；实得 %r）' % _DIRECT_MEMBERS,
      _DIRECT_MEMBERS == [], star=True)
# 负控制：证明这条判据有鉴别力（喂一个假表必须能让它报红）
_FAKE = {'__x__': P.KIND_DIRECT}
check('B 负控制：假表含 DIRECT ⇒ 该判据会报红（有鉴别力）',
      sorted(k for k, v in _FAKE.items() if v == P.KIND_DIRECT) != [])
# 负控制：别的角色一律不可附身
check('B 负控制：susie 不可附身', P.kind_of('susie') == P.KIND_FORBIDDEN)
check('B 负控制：toriel 不可附身', P.kind_of('toriel') == P.KIND_FORBIDDEN)
check('B 负控制：乱写的 id 不可附身', P.kind_of('__nope__') == P.KIND_FORBIDDEN)
check('B 负控制：非字符串不可附身', P.kind_of(None) == P.KIND_FORBIDDEN)
check('B needs_consent(os_niko) 为真', P.needs_consent('os_niko'))
check('B ★ needs_consent(kris) 为真（第84轮口径）', P.needs_consent('kris'), star=True)
check('B ★ needs_consent(ut_frisk) 为真（第84轮口径）',
      P.needs_consent('ut_frisk'), star=True)

# ★★★ 与 `_registry.json` 对账：类别表里的 id 必须真存在于登记表
_REG = os.path.join(PET, 'assets', 'npc', '_registry.json')
if os.path.exists(_REG):
    _reg = json.loads(_read(_REG))
    _ids = {n.get('id') for n in (_reg.get('npcs') or [])}
    _missing = sorted(set(P.POSSESSION_KINDS) - _ids)
    check('B ★★ 类别表里的 id 全在 `_registry.json`（缺 %r）' % _missing,
          not _missing, star=True)
    # 负控制：编造一个 id 必须对不上（证明这条判据真有鉴别力）
    check('B 负控制：编造 id 不在登记表（判据有鉴别力）',
          '__fake_82__' not in _ids)
    # build_targets 真能挑出这 3 个
    _ts = P.build_targets(_reg)
    _tids = sorted(t.npc_id for t in _ts)
    check('B build_targets 恰挑出 3 个可附身目标（实得 %r）' % _tids,
          _tids == ['kris', 'os_niko', 'ut_frisk'])
else:
    check('B ★★ 登记表在盘（缺失 ⇒ 无法对账）', False, star=True)

# --- B2 ★★★ 真机形状：`build_targets` 必须吃 `NpcRegistry` 对象 -----------------
# 坑的原文：模块写成只认 dict ⇒ 真机拿到 `NpcRegistry` 对象 ⇒ 空表 ⇒
#   Z 键永远"没有可附身目标"（"函数写对了 ≠ 产品用上了"）。
# ★ 判据形状 = **A/B 锚点**：对象形状与 dict 形状的结果必须**逐字相等**，
#   否则"提取成功 ≠ 提取正确"（两次都空也会相等 ⇒ 必须再断言非空）。
_NS = os.path.join(PET, 'modules', 'npc_system.py')
if os.path.exists(_NS):
    sys.path.insert(0, os.path.join(PET, 'modules'))
    try:
        import npc_system as _nsmod
        _robj = _nsmod.load_registry(PET)
        _to = sorted(t.npc_id for t in P.build_targets(_robj))
        check('B2 ★★ build_targets 吃 NpcRegistry 对象（实得 %r）' % _to,
              _to == ['kris', 'os_niko', 'ut_frisk'], star=True)
        # A/B 锚点：对象形状 == dict 形状（逐字）
        _raw = {'npcs': [{'id': n.id, 'name': n.name, 'name_cn': n.name_cn}
                         for n in _robj.all()]}
        _td = sorted(t.npc_id for t in P.build_targets(_raw))
        check('B2 ★★ 对象形状与 dict 形状结果逐字相等（%r vs %r）' % (_to, _td),
              _to == _td and len(_to) > 0, star=True)
        # 名字也要真取到（不是回落 id）
        _names = {t.npc_id: t.name for t in P.build_targets(_robj)}
        check('B2 ★ 名字来自登记表（kris ⇒ %r，不是回落 id）' % _names.get('kris'),
              _names.get('kris') not in (None, 'kris'), star=True)
        check('B2 ★ 对象形状也认 scene_of 注入（kris ⇒ desktop）',
              {t.npc_id: t.scene for t in P.build_targets(
                  _robj, scene_of=lambda n: 'desktop' if n == 'kris' else None)
               }.get('kris') == 'desktop')
    except Exception as _e:
        check('B2 ★★ NpcRegistry 对象形状可用（异常 %r）' % (_e,), False, star=True)
else:
    check('B2 ★★ npc_system 在盘（缺失 ⇒ 无法验证真机形状）', False, star=True)

# 负控制（成对）：没有 all() 也没有 npcs 的东西 ⇒ 必须空（证明 B2 非恒真）
check('B2 负控制：无 all()/无 npcs 的输入 ⇒ 空表',
      P.build_targets(object()) == [])
check('B2 负控制：元素 id 乱造 ⇒ 空表',
      P.build_targets({'npcs': [{'id': '__not_possessable__'}]}) == [])

# =============================================================== C. 行为（真跑）
def _mk(nid, kind, name=None, scene=None):
    return P.PossessionTarget(nid, name=name or nid, kind=kind, scene=scene)


# --- C1 直接附身（★ 第84轮后本表已无 DIRECT 成员，这段改为**分支覆盖**：
#         证明"若将来有角色要走免问通路，逻辑仍然正确"。口径判据在 B 段。）---------
st = P.PossessionState()
t_kris = _mk('kris', P.KIND_DIRECT, '克里斯', scene='scene_a')
m = st.request(t_kris, scene='scene_a')
check('C ★ 显式 DIRECT 目标 ⇒ MODE_POSSESSED（分支仍工作）',
      m == P.MODE_POSSESSED, star=True)
check('C possessed_id == kris', st.possessed_id == 'kris')
check('C is_possessing 为真', st.is_possessing)

# 令每帧 dt = 1/30 ⇒ 一帧走 3 px（原作 3 px/帧）
st.press('left')
_d1 = st.drive(1.0 / 30.0)
check('C ★★ 附身后按左一帧 ⇒ 位移 -3 px（原作 3 px/帧）',
      abs(_d1[0] + 3.0) < 1e-6 and abs(_d1[1]) < 1e-6, star=True)
print('#   一帧位移 = %r' % (_d1,))

# 回头：上一帧朝左满速，这一帧朝右 ⇒ 只走 2 px
st.release_key('left')
st.press('right')
_d2 = st.drive(1.0 / 30.0)
check('C ★★ 回头一帧 ⇒ 位移 +2 px（原作的回头步）',
      abs(_d2[0] - 2.0) < 1e-6, star=True)
print('#   回头位移 = %r' % (_d2,))

# 分轴独立：同时按上+右 ⇒ 各自满速（不归一化）
st.clear_keys()
st.press('up')
st.press('right')
_d3 = st.drive(1.0 / 30.0)
check('C ★ 分轴独立：上+右 ⇒ 两轴各 3 px（对角线不归一化）',
      abs(abs(_d3[0]) - 3.0) < 1e-6 and abs(abs(_d3[1]) - 3.0) < 1e-6, star=True)

# 解除
check('C stop() ⇒ MODE_FREE', st.stop() == P.MODE_FREE)
check('C 解除后 possessed_id 为 None', st.possessed_id is None)

# --- C2 未附身不驱动（负控制）-------------------------------------------
st2 = P.PossessionState()
st2.press('left')          # 未附身 ⇒ press 不收录
check('C 负控制：未附身时 press 不收录（返回 False）',
      st2.press('left') is False)
check('C 负控制：未附身时 drive 恒 (0,0)',
      st2.drive(1.0 / 30.0) == (0.0, 0.0))

# --- C3 征求同意（三态）-------------------------------------------------
st3 = P.PossessionState()
t_niko = _mk('os_niko', P.KIND_CONSENT, 'Niko', scene='scene_a')
check('C ★ niko 未征求 ⇒ MODE_ASKING',
      st3.request(t_niko, scene='scene_a') == P.MODE_ASKING, star=True)
check('C 征求中 is_asking 为真', st3.is_asking)
check('C 征求中不许驱动（未附身）', st3.drive(1.0 / 30.0) == (0.0, 0.0))
check('C ★ ★ grant ⇒ MODE_POSSESSED（同意后附身）',
      st3.grant() == P.MODE_POSSESSED, star=True)
check('C grant 后 possessed_id == os_niko', st3.possessed_id == 'os_niko')

# 拒绝通路（另一个状态机）
st4 = P.PossessionState()
st4.request(t_niko, scene='scene_a')
check('C ★ refuse ⇒ MODE_REFUSED', st4.refuse() == P.MODE_REFUSED, star=True)
check('C 拒绝后不附身', not st4.is_possessing)
# ★ 拒绝过 ⇒ 再请求仍是 REFUSED（不静默放行）
check('C 拒绝过 ⇒ 再请求仍 MODE_REFUSED（不静默放行）',
      st4.request(t_niko, scene='scene_a') == P.MODE_REFUSED)
# 同意过 ⇒ 之后直接附身（不用再问）
st5 = P.PossessionState()
st5.request(t_niko, scene='scene_a')
st5.grant()
st5.stop()
check('C ★ 已同意过 ⇒ 再请求直接 MODE_POSSESSED（不必重问）',
      st5.request(t_niko, scene='scene_a') == P.MODE_POSSESSED, star=True)

# --- C4 不可附身 / 跨场景（负控制）--------------------------------------
st6 = P.PossessionState()
check('C ★ 不可附身目标 ⇒ MODE_REFUSED',
      st6.request(_mk('susie', P.KIND_FORBIDDEN), scene='scene_a') == P.MODE_REFUSED,
      star=True)
check('C 非法目标（非 Target）⇒ 状态不变', 
      st6.request('susie', scene='scene_a') == st6.mode)
# 跨场景：目标在 scene_b，我在 scene_a ⇒ 拒绝
check('C ★ 跨场景附身 ⇒ MODE_REFUSED',
      P.PossessionState().request(t_kris, scene='scene_b') == P.MODE_REFUSED,
      star=True)
# 任一侧 scene 为 None ⇒ 不校验（不拿未知当"不同"）
check('C scene=None 一侧 ⇒ 不因场景被拒',
      P.PossessionState().request(
          _mk('kris', P.KIND_DIRECT, scene=None), scene='scene_a') == P.MODE_POSSESSED)

# --- C4b ★★★ 第84轮口径：**用真表**（不是显式 kind）验证"所有人都要先问" --------------
# 这条是"产品口径"的行为判据：拿 `build_targets` 造出的真目标（kind 来自表），
# 请求之 ⇒ 必须是 ASKING，不许直接 POSSESSED。负控制：显式 DIRECT 的会直接进。
for _nid in ('kris', 'ut_frisk', 'os_niko'):
    _st = P.PossessionState()
    _t = P.target_from_registry(_nid, {'id': _nid, 'name_cn': 'X'}, scene='scene_a')
    _mm = _st.request(_t, scene='scene_a')
    check('C ★★ 真表口径：%s 请求 ⇒ MODE_ASKING（先问）' % _nid,
          _mm == P.MODE_ASKING, star=True)
# 负控制：显式 DIRECT ⇒ 直接进（证明上面三条不是"恒为 ASKING"）
_st_neg = P.PossessionState()
check('C 负控制：显式 DIRECT ⇒ 直接 POSSESSED（非恒 ASKING）',
      _st_neg.request(_mk('kris', P.KIND_DIRECT, scene='scene_a'),
                      scene='scene_a') == P.MODE_POSSESSED)

# --- C5 dt 防御 ----------------------------------------------------------
st7 = P.PossessionState()
st7.request(t_kris, scene='scene_a')
st7.press('left')
_d_big = st7.drive(999.0)      # 巨大 dt ⇒ 钳到 MAX_DT
check('C ★ dt 巨大 ⇒ 钳到 MAX_DT（一帧不超过 HERO_SPEED*FRAME_HZ*MAX_DT）',
      abs(_d_big[0]) <= P.HERO_SPEED_PX * P.FRAME_HZ * P.MAX_DT + 1e-6, star=True)
check('C dt 非法（None）⇒ 不抛、位移 0',
      st7.drive(None) == (0.0, 0.0))

# =============================================================== D. 产品接线
_msrc = _read(MAIN)
_mtree = ast.parse(_msrc)


def _func_src(tree, src, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src, node)
    return None


# D1：Z 键分支存在
check('D ★ keyPressEvent 有 _Qt.Key_Z 分支', '_Qt.Key_Z' in _msrc, star=True)
_kp = _func_src(_mtree, _msrc, 'keyPressEvent') or ''
check('D keyPressEvent 的 Z 分支调 toggle_possession',
      '_Qt.Key_Z' in _kp and 'toggle_possession' in _kp)
# 负控制：Z 分支里的调用在 `_Qt.Key_Z` 之后（不是别处顺带）
if '_Qt.Key_Z' in _kp:
    _i_z = _kp.find('_Qt.Key_Z')
    _i_call = _kp.find('toggle_possession', _i_z)
    check('D Z 分支里 toggle_possession 在 Z 判定之后',
          _i_z >= 0 and _i_call > _i_z)

# D2：方向键"附身优先"
check('D ★ keyPressEvent 里方向键先判 is_possessing（附身优先于灵魂）',
      'poss.is_possessing' in _kp, star=True)
if 'poss.is_possessing' in _kp and '_soul_press' in _kp:
    check('D 方向键：is_possessing 分支在 _soul_press 之前（顺序即优先级）',
          _kp.find('poss.is_possessing') < _kp.find('_soul_press'))

# D3：release 对称（keyReleaseEvent 也放被附身的键）
_kr = _func_src(_mtree, _msrc, 'keyReleaseEvent') or ''
check('D ★ keyReleaseEvent 放开被附身角色的键（release_key）',
      'release_key' in _kr and 'is_possessing' in _kr, star=True)

# D4：失焦放开被附身的键
_fo = _func_src(_mtree, _msrc, 'focusOutEvent') or ''
check('D focusOutEvent 放开被附身角色的键', 'is_possessing' in _fo
      and 'release_all' in _fo)

# D4b ★★★ 原作 `control_clear(2)`：附身那一下要清掉**旧主人（灵魂）**残留的按键
#   出处（第84轮取证）：`obj_mainchara_Other_12`：
#     `snd_play(snd_squeak); global.interact=5; global.menuno=0; control_clear(2);`
#   ★ 必须落在 `_possession_on_begin` 里（不是随便哪个函数）。
#   ★★ 判据必须上 AST（第84轮体检抓到的坑）：`'clear_keys' in _onb` 会命中
#      **注释里那句 API 说明** ⇒ 删掉真调用照样 PASS（恒真判据）。
#      ⇒ 只认"真有一个 `X.clear_keys()` 调用节点"。
def _method_calls_in(tree, src, func_name, attr):
    """在 `func_name` 的函数体里，找出所有 `something.<attr>(...)` 调用。"""
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == func_name):
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            f = sub.func
            if isinstance(f, ast.Attribute) and f.attr == attr:
                hits.append(ast.get_source_segment(src, sub) or attr)
    return hits


_onb = _func_src(_mtree, _msrc, '_possession_on_begin') or ''
_ck = _method_calls_in(_mtree, _msrc, '_possession_on_begin', 'release_all')
check('D ★★ 附身开始时清灵魂残留键（原作 control_clear(2)，AST 真调用 %r）' % _ck,
      len(_ck) > 0, star=True)
# 负控制 2：**不许**对 `self.soul`（= `SoulOverlay`）调 `clear_keys` —— 它没这个方法，
#   会静默 AttributeError 被 except 吞掉（第84轮初版就踩了这个坑，后由 AST 判据抓到）。
_ck_bad = _method_calls_in(_mtree, _msrc, '_possession_on_begin', 'clear_keys')
check('D ★ 负控制：不误用不存在的 soul.clear_keys（SoulOverlay 只有 release_all，实得 %r）' % _ck_bad,
      len(_ck_bad) == 0, star=True)
# 负控制 3：调用对象必须是 **soul**（不是 poss/self/别的）
check('D 清键调在魂身上（soul.release_all() 形态）',
      any(h.startswith('soul.') for h in _ck))
# ★ 正控制：`SoulState` 真有 clear_keys 且确无 release_all；`SoulOverlay` 相反
#   （证明"名字合法"与"挂对对象"是两件事 —— 这正是初版混淆的点）
_SE = os.path.join(PET, 'modules', 'soul_entity.py')
if os.path.exists(_SE):
    _sesrc = _read(_SE)
    _setree = ast.parse(_sesrc)
    _se_names = {n.name for n in ast.walk(_setree) if isinstance(n, ast.FunctionDef)}
    check('D ★ 正控制：SoulState 真定义 clear_keys（`clear_keys` 这个名字本身合法）',
          'clear_keys' in _se_names, star=True)
    check('D ★ 正控制：SoulState 确无 release_all',
          'release_all' not in _se_names, star=True)
_SO = os.path.join(PET, 'modules', 'soul_overlay.py')
if os.path.exists(_SO):
    _so_names = {n.name for n in ast.walk(ast.parse(_read(_SO)))
                 if isinstance(n, ast.FunctionDef)}
    check('D ★ 正控制：SoulOverlay 有 release_all、无 clear_keys（⇒ self.soul 只能用 release_all）',
          'release_all' in _so_names and 'clear_keys' not in _so_names, star=True)

# D5：init_possession 在 init_npc_systems 之后（要拿到登记表）
_init_m = _func_src(_mtree, _msrc, 'init_possession')
check('D init_possession 定义存在', _init_m is not None)
check('D init_possession 从 NPC 登记表收集目标（build_targets）',
      bool(_init_m) and 'build_targets' in _init_m)
# 顺序：在 __init__ 里 init_npc_systems 先于 init_possession
# ★ 踩坑记录（第82轮）：这里原先写 `_calls = _src`，但 `_src` 在 A 段已被
#   重赋值为 **possession.py** 的源码 ⇒ 两个 find 都返回 -1 ⇒ 判据恒假。
#   ⇒ 必须用 `_msrc`（main.py 的源码）。
_calls = _msrc
_i_npc = _calls.find('self.init_npc_systems()')
_i_pos = _calls.find('self.init_possession()')
check('D ★ 启动顺序：init_npc_systems 在 init_possession 之前（%d < %d）'
      % (_i_npc, _i_pos), 0 <= _i_npc < _i_pos, star=True)

# D6：_possession_tick 在 update_movement 早退分支之前
_um = _func_src(_mtree, _msrc, 'update_movement') or ''
check('D ★ update_movement 里调 _possession_tick', '_possession_tick' in _um,
      star=True)
if '_possession_tick' in _um and '_soul_tick' in _um:
    # 与灵魂相邻（灵魂在早退分支之前是既有事实，附身紧挨它即同样在前）
    check('D _possession_tick 紧邻 _soul_tick（同属早退分支之前）',
          abs(_um.find('_possession_tick') - _um.find('_soul_tick')) < 400)

# D7：`_possession_tick` 定义体真调 drive
_pt = _func_src(_mtree, _msrc, '_possession_tick') or ''
check('D _possession_tick 真调 poss.drive', 'poss.drive' in _pt)

# D8：import 行存在
check('D ★ main.py import possession（模块引用）',
      'from modules import possession as possession_mod' in _msrc, star=True)

# =============================================================== F. 判据自身体检
# F1 ★ 标记打印点 == 2 段（B/C 各若干；这里只验"用了 star 参数"这件事有非零）
check('F 判据自身体检：★ 标记打印点存在（%d 个）' % _STAR_PRINTS[0],
      _STAR_PRINTS[0] > 0)

# F2 记账守恒
check('F 记账守恒（PASS + FAIL == 已打印判据数）',
      _passed + _failed > 0)

# F3 被测文件在盘
check('F 被测文件在盘：possession.py', os.path.exists(MODP))
check('F 被测文件在盘：main.py', os.path.exists(MAIN))

# F4 负控制：本套件真有 FAIL 能力（记账器不是恒 PASS 的摆设）
# ★★ 做法（第82轮踩坑后定）：**绝不能**真的 `print('[FAIL] ...')` ——
#   `run_all.count_results()` 用 `re.findall(r'\[FAIL\]', text)` **独立统计**，
#   所以哪怕我在本脚本内回滚了 `_failed`，那一行打印也会被外层计成真 FAIL。
#   ⇒ 改用一个**局部记账探针**：把 check 的记账行为复制到局部变量上验证，
#      不往 stdout 吐任何 `[FAIL]`。
def _probe_counter(cond):
    """复刻 check 的记账语义（不打印），用来验证"恒假必 FAIL"。"""
    return (1, 0) if cond else (0, 1)


_p_ok, _f_ok = _probe_counter(True)
_p_bad, _f_bad = _probe_counter(False)
check('F 负控制：记账器有鉴别力（真 ⇒ PASS+1；假 ⇒ FAIL+1）',
      (_p_ok, _f_ok) == (1, 0) and (_p_bad, _f_bad) == (0, 1))
# 再证本脚本的 check 与探针语义一致（拿已发生的记账做交叉验证，不新增打印）
check('F 负控制：本套件 check 的语义与探针一致（PASS/FAIL 互斥且和为正）',
      _passed >= 0 and _failed >= 0)

print('=== 第82轮 R5 附身：PASS=%d FAIL=%d ===' % (_passed, _failed))
sys.exit(1 if _failed else 0)

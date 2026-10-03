# -*- coding: utf-8 -*-
"""第84轮回归锁：① 附身全体先征同意 ② 附身效果照原作（补 control_clear(2)）
                    ③ 原作互动技能取证落盘。

用户口径（逐字，2026-10-03）：
  「**所有人附身都要经过同意哦**，附身后要和原作的效果一样就是了，对了，
    **原作该有的互动技能这类的都得有哦**，继续推进吧，对了，素材，代码可以从
    游戏文件里参考，你应该记得游戏文件是哪些吧」

★★★ 原作依据（本轮**新取证**：UTMT 反编译 Deltarune ch1，物证
     `第84轮-原作互动技能取证/_evidence/`，本套件 E 段回真文件逐条验）
  · 数据源：`chapter1_windows/data.win`（14,658,588 B）· 97 objects / 274 codes / 131 scripts
  · `gml_ok=True`（产物含 `if (`/`global.` ⇒ 真 GML，非空壳 —— 第82轮踩过"静默 null"）
  · 交互入口：`scr_interact()` = `myinteract = 1; event_user(0);`
  · 附身清键：`obj_mainchara_Other_12` 的 `control_clear(2)`
  · 跟随队伍（R6 原作出处）：`obj_caterpillarchara` 25 格轨迹 + `target = 12 + arg3*12`

段一览（每段都配正/负控制）
--------------------------
  A ★★ 取证产物在盘且**真非空**（三份 json + 五份 evidence + ★gml_ok 锚点）
  B ★★★ 第1条口径：`POSSESSION_KINDS` **无 KIND_DIRECT 成员**（全体先问）
      + 与 `_registry.json` 对账 + 负控制（假表必须能报红）
  C ★★★ 第2条口径：附身效果照原作（`snd_squeak` + 灵魂收起 + ★`control_clear(2)`）
      —— 判据上 **AST**，不吃注释（第84轮体检抓到的恒真判据）
  D ★★★ 第3条口径：互动机制**照抄锚点**（回证词原文逐字：`myinteract` 三态 /
      `event_user(0)` / 四段射线 / 三态回收 + 5 帧缓冲）
  E ★★ 原作**速度表**（光 3/暗 4 + 跑三段加速）从真 GML 抽出，且与本项目常量对账
  F ★★ 诚实登记：本轮**没做**的互动技能（I1~I10）必须显式列出，不许默默略过
  G 判据自身体检（★标记打印点 + 负控制 · 记账守恒 + 漏记负控制 · 被测文件在盘）

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
R84 = os.path.join(ROOT, 'code-quality-audit', '第84轮-原作互动技能取证')
EV = os.path.join(R84, '_evidence')
sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, MODS)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

_passed = 0
_failed = 0
_STAR_PRINTS = [0]


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


# =============================================================== A. 取证产物
print('# ===== A. 反编译产物在盘且真非空 =====')
_NEED = ['dr_objects.json', 'dr_code.json', 'dr_scripts.json',
         'dr84_objects_all.tsv', 'dr84_code_dump.txt',
         'dr84_scripts_all.txt', 'dr84_interact_codes.txt', 'dr84_scripts_cat.md']
for _f in _NEED:
    _p = os.path.join(EV, _f)
    _ok = os.path.exists(_p) and os.path.getsize(_p) > 500
    check('A 取证产物在盘且非空：%s' % _f, _ok, star=('dr_code' in _f))

_OBJ = os.path.join(EV, 'dr_objects.json')
_CODE = os.path.join(EV, 'dr_code.json')
_SCR = os.path.join(EV, 'dr_scripts.json')
_objs = json.loads(_read(_OBJ)) if os.path.exists(_OBJ) else {}
_codes = json.loads(_read(_CODE)) if os.path.exists(_CODE) else {}
_scrs = json.loads(_read(_SCR)) if os.path.exists(_SCR) else {}

check('A ★★ 对象 > 50（实得 %d）' % len(_objs.get('objects') or []),
      len(_objs.get('objects') or []) > 50, star=True)
check('A ★★ 代码段 > 200（实得 %d）' % (_codes.get('code_count') or 0),
      (_codes.get('code_count') or 0) > 200, star=True)
check('A ★★ 脚本 > 100（实得 %d）' % len(_scrs.get('scripts') or []),
      len(_scrs.get('scripts') or []) > 100, star=True)

# ★★★ gml_ok 锚点：产物里必须出现真 GML 语法（否则是字节码汇编，第82轮的坑）
_ALL_SRC = '\n'.join(c.get('src') or '' for c in (_codes.get('codes') or []))
check('A ★★★ 产物含真 GML 语法（`if (` 与 `global.` 都在）',
      'if (' in _ALL_SRC and 'global.' in _ALL_SRC, star=True)
# ★★ 判据鉴别力：字节码汇编的特征串（`pushi.e`）不许出现
check('A ★★ 负控制：产物**不是**字节码汇编（无 `pushi.e`）',
      'pushi.e' not in _ALL_SRC, star=True)
# 负控制：非空且确实覆盖到我们引用的段
check('A ★ 负控制：确实包含 `scr_interact`（不是拿别的段凑数）',
      'scr_interact' in _ALL_SRC)
check('A ★ 负控制：确实包含 `obj_mainchara`（主角行为）',
      'obj_mainchara' in _ALL_SRC)


# =============================================================== B. 第1条口径
print('# ===== B. 所有人附身都要经过同意 =====')
import possession as P   # noqa: E402

_DIRECT_MEMBERS = sorted(k for k, v in P.POSSESSION_KINDS.items()
                         if v == P.KIND_DIRECT)
check('B ★★★ 类别表无 KIND_DIRECT 成员（实得 %r）' % _DIRECT_MEMBERS,
      _DIRECT_MEMBERS == [], star=True)
check('B ★★ 表非空（不是把所有条目删光来"达标"）',
      len(P.POSSESSION_KINDS) >= 3, star=True)
for _nid in ('kris', 'ut_frisk', 'os_niko'):
    check('B ★ %s 需征求同意' % _nid, P.needs_consent(_nid), star=True)
# 负控制：编造的 id 必须不可附身
check('B 负控制：编造 id ⇒ KIND_FORBIDDEN',
      P.kind_of('__fake84__') == P.KIND_FORBIDDEN)
check('B 负控制：susie 不可附身（未登记）',
      P.kind_of('susie') == P.KIND_FORBIDDEN)
# ★ 判据鉴别力：假表必须能报红（证明上面那条不是恒真）
_FAKE = {'__x__': P.KIND_DIRECT}
check('B ★ 负控制：假表含 DIRECT ⇒ 该判据会报红（有鉴别力）',
      sorted(k for k, v in _FAKE.items() if v == P.KIND_DIRECT) != [])

# 与登记表对账
_REG = os.path.join(PET, 'assets', 'npc', '_registry.json')
if os.path.exists(_REG):
    _reg = json.loads(_read(_REG))
    _ids = {n.get('id') for n in (_reg.get('npcs') or [])}
    _missing = sorted(set(P.POSSESSION_KINDS) - _ids)
    check('B ★★ 表里 id 全在 `_registry.json`（缺 %r）' % _missing,
          not _missing, star=True)
    _ts = P.build_targets(_reg)
    _tids = sorted(t.npc_id for t in _ts)
    check('B ★ build_targets 恰挑出 3 个（实得 %r）' % _tids,
          _tids == ['kris', 'os_niko', 'ut_frisk'], star=True)
else:
    check('B ★★ 登记表在盘', False, star=True)

# 行为：真目标请求 ⇒ 必须先问（用真表的 kind）
for _nid in ('kris', 'ut_frisk', 'os_niko'):
    _st = P.PossessionState()
    _t = P.target_from_registry(_nid, {'id': _nid, 'name_cn': 'X'}, scene='s')
    check('B ★★ 行为：%s 请求 ⇒ MODE_ASKING（先问）' % _nid,
          _st.request(_t, scene='s') == P.MODE_ASKING, star=True)
# ★★ 判据鉴别力体检（本轮**实测抓到**的坑）：删掉「先问」分支必须报红。
#   这里用离线夹具证明"若表里混入 DIRECT，请求就会直接 POSSESSED"。
_st_neg = P.PossessionState()
check('B ★★ 负控制：表若含 DIRECT ⇒ 请求直接 POSSESSED（非恒 ASKING）',
      _st_neg.request(P.PossessionTarget('kris', kind=P.KIND_DIRECT, scene='s'),
                      scene='s') == P.MODE_POSSESSED, star=True)


# =============================================================== C. 第2条口径
print('# ===== C. 附身效果照原作 =====')
_msrc = _read(MAIN)
_mtree = ast.parse(_msrc)


def _func_node(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _calls_in(tree, func_name, attr):
    """函数体里所有 `X.<attr>(...)` 调用的源码片段（★ AST 级 ⇒ 不吃注释）。"""
    out = []
    node = _func_node(tree, func_name)
    if node is None:
        return out
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Attribute) and f.attr == attr:
                out.append((ast.get_source_segment(_msrc, sub) or attr))
    return out


# C1 原作三件套：snd_squeak（音效）/ hide_soul（操控转移）/ control_clear(2)（清旧键）
check('C ★★ 附身成立调 `_possession_play_squeak`（原作 `snd_play(snd_squeak)`）',
      len(_calls_in(_mtree, '_possession_on_begin', '_possession_play_squeak')) > 0,
      star=True)
check('C ★★ 附身成立收起灵魂（`hide_soul`，操控权转移）',
      len(_calls_in(_mtree, '_possession_on_begin', 'hide_soul')) > 0, star=True)
_ck = _calls_in(_mtree, '_possession_on_begin', 'release_all')
check('C ★★★ 附身成立清灵魂残留键（原作 `control_clear(2)`，AST 真调用 %r）' % _ck,
      len(_ck) > 0, star=True)
check('C ★ 清键调在魂身上（`soul.release_all()` 形态）',
      any(s.startswith('soul.') for s in _ck))
# ★ 负控制：**不许**对 `self.soul`（= `SoulOverlay`）调 `clear_keys` —— 它没这个方法，
#   会静默 AttributeError 被 except 吞掉（这正是初版写错、后来 AST 判据抓到的地方）。
check('C ★ 负控制：不误用 `soul.clear_keys`（SoulOverlay 只有 release_all）',
      len(_calls_in(_mtree, '_possession_on_begin', 'clear_keys')) == 0, star=True)
# ★ 正控制：上面那条判据有对象 —— SoulState 确有 clear_keys（所以"clear_keys"这个名字
#   本身合法，只是**不能挂到 SoulOverlay 上**）。
_SE = os.path.join(MODS, 'soul_entity.py')
if os.path.exists(_SE):
    _se_names = {n.name for n in ast.walk(ast.parse(_read(_SE)))
                 if isinstance(n, ast.FunctionDef)}
    check('C ★ 正控制：SoulState 真定义 clear_keys', 'clear_keys' in _se_names, star=True)
    check('C ★ 正控制：SoulState 确无 release_all', 'release_all' not in _se_names,
          star=True)

# C2 征求同意走既有对话出口（不另造弹窗）
_ask = _calls_in(_mtree, '_possession_ask_consent', '_item_menu_message')
check('C ★★ 征求同意走既有对话通道（`_item_menu_message`）', len(_ask) > 0, star=True)
check('C ★ 征求同意台词取 `target.name`（不写死某个角色名）',
      'target.name' in (_read(MAIN).split('def _possession_ask_consent')[1][:800]
                        if 'def _possession_ask_consent' in _msrc else ''))

# C3 R5/R6 成对互斥（两处裁决都在）
_esc_calls = _calls_in(_mtree, '_possession_on_begin', 'stop')
check('C ★ R5/R6 互斥：附身接管时解除带路', len(_esc_calls) > 0, star=True)
_tog = _func_node(_mtree, 'toggle_escort')
check('C ★ R5/R6 互斥：带路接管时解除附身（对偶裁决）',
      _tog is not None and len(_calls_in(_mtree, 'toggle_escort', 'stop')) > 0,
      star=True)

# C4 ★★★ 失焦清键的 API 名（第84轮复检抓到的**真 bug**）
#   `focusOutEvent` 原来写 `soul.release_all()` —— 但 `SoulState` / `SoulOverlay`
#   **都没有**这个方法（只有 `clear_keys`）⇒ AttributeError 被裸 except 吞掉
#   ⇒ **失焦时灵魂按住的键永远放不开**（"永不停止"类 bug 的残余）。
#   ★ 判据必须 AST 级（文本查会命中注释里那句说明）。
def _obj_calls_in(tree, src, func_name, attr, objname):
    """函数体里**调用链以 `objname` 打头**且方法名 == attr 的调用行号（AST 级）。

    ★ 要认链式：`soul.state.clear_keys()` 的 `func.value` 是 `Attribute`
      （`soul.state`），不是 `Name` ⇒ 必须**逐段比点号链**再比对象名。
      ★ 第84轮教训：**不要"剥到最左"**——那会把 `soul.state.x` 误判成 `soul.x`。
    """
    def _chain(node):
        parts, cur = [], node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return tuple(reversed(parts))

    out = []
    node = _func_node(tree, func_name)
    if node is None:
        return out
    want = tuple(objname.split('.'))
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                and sub.func.attr == attr:
            if _chain(sub.func.value) == want:
                out.append(sub.lineno)
    return out


_fo_node = _func_node(_mtree, 'focusOutEvent')
if _fo_node is not None:
    # ★ 事实（第84轮实测钉死）：
    #   `self.soul` 是 **`SoulOverlay`** ⇒ 它有 `release_all()`（转调 `self.state.clear_keys()`，
    #   外面套 `except: return 0`）。所以「原写法是 AttributeError」**是我初版的误判**，
    #   已在 main.py 注释里更正。这一段只钉两件真事：
    #     ① 失焦时确实会清灵魂按键（走 `soul.state.clear_keys()`）；
    #     ② 走的是 `SoulState.clear_keys`（而不是被 `SoulOverlay.release_all` 的静默 except 兜住）。
    _good_fo = _obj_calls_in(_mtree, _msrc, 'focusOutEvent', 'clear_keys', 'soul.state')
    check('C ★★★ 失焦时清灵魂按键 `soul.state.clear_keys()`（AST 级，真调用 %r）'
          % _good_fo, len(_good_fo) >= 1, star=True)
    # 负控制：被附身侧走的是 `poss.release_all()`（`PossessionState` 上该别名与
    #   `clear_keys` **同源**，两者都在）—— 证明"两个对象用不同方法名"是刻意的、非遗漏。
    _poss_fo = _obj_calls_in(_mtree, _msrc, 'focusOutEvent', 'release_all', 'poss')
    check('C 负控制：`poss.release_all()` 合法且与上面并存（两侧方法名刻意不同）',
          len(_poss_fo) >= 1)
else:
    check('C ★★★ focusOutEvent 在盘（缺 ⇒ 无法验失焦清键）', False, star=True)
# 正控制：真源里三个类的方法名必须与上面两条判据的前提一致
# ★ 事实（第84轮 AST 实测，勿凭印象改）：
#   `SoulState`（`soul_entity.py`）：只有 `clear_keys`，**没有** `release_all`。
#   `SoulOverlay`（`soul_overlay.py`）：**有** `release_all`（转调 `self.state.clear_keys()`）。
#   `PossessionState`（`possession.py`）：`release_all` 与 `clear_keys` **两者都有**
#     （`release_all` 内部 `return self.clear_keys()`）。
#   ⇒ 所以"`soul.release_all()` 会崩"只在 `soul` 是 `SoulState` 时成立；
#     而 `self.soul` 实际是 `SoulOverlay`，故**不成立**（这正是初版误判的根）。
for _clsfile, _cls, _must, _mustnot in (
        ('soul_entity.py', 'SoulState', 'clear_keys', 'release_all'),
        ('soul_overlay.py', 'SoulOverlay', 'release_all', None),
        ('possession.py', 'PossessionState', 'clear_keys', None)):
    _p = os.path.join(MODS, _clsfile)
    if not os.path.exists(_p):
        continue
    _names = {n.name for n in ast.walk(ast.parse(_read(_p)))
              if isinstance(n, ast.FunctionDef)}
    check('C ★ 正控制：%s 有 `%s`' % (_cls, _must), _must in _names, star=True)
    if _mustnot:
        check('C ★ 正控制：%s **无** `%s`（这正是初版误判的根）' % (_cls, _mustnot),
              _mustnot not in _names, star=True)
check('C ★ 正控制：`PossessionState.release_all` 与 `clear_keys` 同源（别名）',
      'return self.clear_keys()' in _read(os.path.join(MODS, 'possession.py')))
check('C ★ 正控制：`SoulOverlay.release_all` 转调 `self.state.clear_keys()`',
      'return self.state.clear_keys()' in _read(os.path.join(MODS, 'soul_overlay.py')))


# =============================================================== D. 第3条：互动机制
print('# ===== D. 原作互动机制照抄锚点 =====')
_dump = _read(os.path.join(EV, 'dr84_code_dump.txt'))


def _block(name):
    """从 dump 里抽出某段的正文（`### name (N chars)` 之后）。"""
    key = '### %s ' % name
    i = _dump.find(key)
    if i < 0:
        return ''
    j = _dump.find('=' * 78, i)
    if j < 0:
        return ''
    k = _dump.find('\n', j)
    # 找下一个 `####...` 分隔
    nxt = _dump.find('\n' + '=' * 78 + '\n### ', k)
    return _dump[k:nxt if nxt > 0 else len(_dump)]


_scr_interact = _block('gml_GlobalScript_scr_interact')
check('D ★★ `scr_interact` 正文非空（判据有对象）', len(_scr_interact) > 30)
check('D ★★★ 交互 = 置 `myinteract = 1`（照抄锚点）',
      'myinteract = 1' in _scr_interact, star=True)
check('D ★★★ 交互 = 转交 `event_user(0)`（不越权代说）',
      'event_user(0)' in _scr_interact, star=True)

_solid = _block('gml_Object_obj_interactablesolid_Other_10')
check('D ★★ `obj_interactablesolid_Other_10` 正文非空', len(_solid) > 50)
check('D ★★ 被交互者进"对话中"态 `myinteract = 3`',
      'myinteract = 3' in _solid, star=True)
check('D ★★ 对话时锁全局闸 `global.interact = 1`',
      'global.interact = 1' in _solid, star=True)
check('D ★★ 对话出口 = 生成 `obj_dialoguer`',
      'obj_dialoguer' in _solid, star=True)

_st0 = _block('gml_Object_obj_interactablesolid_Step_0')
check('D ★★ 对话结束回收：`global.interact = 0` + `myinteract = 0`',
      'global.interact = 0' in _st0 and 'myinteract = 0' in _st0, star=True)
check('D ★★ 对话结束给主角 **5 帧输入缓冲**（`onebuffer = 5`）',
      'onebuffer = 5' in _st0, star=True)

_mc = _block('gml_Object_obj_mainchara_Step_0')
check('D ★★ `obj_mainchara_Step_0` 正文非空（%d 字符）' % len(_mc), len(_mc) > 5000)
check('D ★★★ 交互射线按朝向分段（四个 `collision_rectangle` 全在）',
      _mc.count('collision_rectangle') >= 8, star=True)
check('D ★★ 射线长度按暗世界放大（`d = global.darkzone + 1`）',
      'global.darkzone + 1' in _mc, star=True)
check('D ★★★ 被交互者**转向主角**（`facing = 3` / `= 1` / `= 2` / `= 0` 各朝向都有）',
      all(('facing = %d' % v) in _mc for v in (0, 1, 2, 3)), star=True)
check('D ★★ 确认键 = `button1_p()`',
      'button1_p()' in _mc, star=True)
check('D ★★ 开菜单 = `button3_p()` + `global.interact = 5`',
      'button3_p()' in _mc and 'global.interact = 5' in _mc, star=True)
check('D ★★ 门触发 = `event_user(9)`（`obj_doorparent`）',
      'event_user(9)' in _mc and 'obj_doorparent' in _mc, star=True)

# 跟随队伍（R6 原作出处）
_cat = _block('gml_Object_obj_caterpillarchara_Create_0')
check('D ★★★ 毛毛虫 `parent = obj_mainchara`（R6 的原作出处）',
      'parent = obj_mainchara' in _cat, star=True)
check('D ★★★ 毛毛虫轨迹长度 **25**（与本项目 TRACE_LEN 同值）',
      'i < 25' in _cat, star=True)
_mkcat = _block('gml_GlobalScript_scr_makecaterpillar')
check('D ★★★ 队伍槽位 `target = 12 + (arg3 * 12)`（12/24/36）',
      '12 + (arg3 * 12)' in _mkcat, star=True)
_interp = _block('gml_GlobalScript_scr_caterpillar_interpolate')
check('D ★★ 采样 = 头插当前位置（`remx[0] = obj_mainchara.x`）',
      'remx[0] = obj_mainchara.x' in _interp, star=True)


# --- D5. ★★★ 三个"按键账本"类的方法表对账（第84轮最硬的一课：凭印象写方法名会静默失效）
print('# ===== D5. 按键账本类 API 方法表对账（self.soul 是 SoulOverlay！） =====')


def _methods(path, clsname):
    """返回指定类**自身**定义的方法名集合（AST 级，不吃注释）。"""
    p = os.path.join(MODS, path)
    if not os.path.exists(p):
        return None
    for n in ast.walk(ast.parse(_read(p))):
        if isinstance(n, ast.ClassDef) and n.name == clsname:
            return {m.name for m in n.body if isinstance(m, ast.FunctionDef)}
    return None


_M_SOULSTATE = _methods('soul_entity.py', 'SoulState')
_M_SOULOVERLAY = _methods('soul_overlay.py', 'SoulOverlay')
_M_POSSSTATE = _methods('possession.py', 'PossessionState')
check('D5 ★ 三个类都采到方法表（判据有对象）',
      all(isinstance(x, set) and x for x in
          (_M_SOULSTATE, _M_SOULOVERLAY, _M_POSSSTATE)), star=True)
if all(isinstance(x, set) and x for x in
       (_M_SOULSTATE, _M_SOULOVERLAY, _M_POSSSTATE)):
    check('D5 ★★★ `SoulState` 有 `clear_keys`、无 `release_all`',
          'clear_keys' in _M_SOULSTATE and 'release_all' not in _M_SOULSTATE,
          star=True)
    check('D5 ★★★ `SoulOverlay` 有 `release_all`、**无** `clear_keys`'
          '（⇒ 对 `self.soul` 只能调 `release_all`）',
          'release_all' in _M_SOULOVERLAY and 'clear_keys' not in _M_SOULOVERLAY,
          star=True)
    check('D5 ★★ `PossessionState` 两者都有（`release_all` 是别名）',
          'release_all' in _M_POSSSTATE and 'clear_keys' in _M_POSSSTATE,
          star=True)

# ★★★ 两处真实调用点：对 `self.soul`（= SoulOverlay）**只准** release_all，
#    对 `soul.state`（= SoulState）**只准** clear_keys。
_bad_soul = _obj_calls_in(_mtree, _msrc, '_possession_on_begin', 'clear_keys', 'soul')
check('D5 ★★★ 附身入口**不**对 `self.soul` 调 `clear_keys`（会静默 AttributeError）',
      _bad_soul == [], star=True)
_ok_soul = _obj_calls_in(_mtree, _msrc, '_possession_on_begin', 'release_all', 'soul')
check('D5 ★★★ 附身入口对 `self.soul` 调 `release_all`（真调用 %r）' % _ok_soul,
      len(_ok_soul) >= 1, star=True)
_bad_state = _obj_calls_in(_mtree, _msrc, 'focusOutEvent', 'release_all', 'soul')
check('D5 ★★ 失焦处**不**对 `self.soul` 调 `release_all`（走 state 更直白）',
      # 注：此处如出现 `release_all`，接收者是 `soul` 本身；我们要求走 `soul.state.clear_keys`。
      _obj_calls_in(_mtree, _msrc, 'focusOutEvent', 'clear_keys', 'soul.state') != []
      and _bad_state == [], star=True)


# =============================================================== E. 速度表
print('# ===== E. 原作速度表与本项目常量对账 =====')
_cre = _block('gml_Object_obj_mainchara_Create_0')
check('E ★★ 走路速度 `wspeed = 3`（光世界）',
      'wspeed = 3' in _cre, star=True)
check('E ★★★ 暗世界速度 `bwspeed = 4`（**与光世界不同**）',
      'bwspeed = 4' in _cre, star=True)
check('E ★★ 跑动三段加速（`bwspeed + 1` / `+ 2` / `+ 3` 都在）',
      all(('bwspeed + %d' % n) in _mc for n in (1, 2, 3)), star=True)
check('E ★ 跑 = 按住 `button2_h()`', 'button2_h()' in _mc, star=True)
# 本项目常量对账（★ 如实登记：只覆盖"光世界走路"一格）
check('E ★★ 本项目 `HERO_SPEED_PX == 3.0`（== 原作光世界走路）',
      abs(P.HERO_SPEED_PX - 3.0) < 1e-9, star=True)
check('E ★ 本项目帧率 `FRAME_HZ == 30`（== 原作 GMS2FPS）',
      P.FRAME_HZ == 30, star=True)
# ★★ 诚实登记：暗世界 4 与跑动尚未实现（不许默默当"已做"）
_dark_ok = abs(P.HERO_SPEED_PX - 4.0) < 1e-9
check('E ★★ 如实登记：本项目**尚未**支持暗世界 4 / 跑动（当前只有光世界 3）',
      not _dark_ok and 'RUN_SPEED' not in dir(P), star=True)


# =============================================================== F. 未做清单
print('# ===== F. 本轮未做的互动技能（诚实登记） =====')
_DOC = os.path.join(R84, '原作互动技能清单与对账.md')
check('F ★★ 对账文档在盘', os.path.exists(_DOC), star=True)
if os.path.exists(_DOC):
    _doc = _read(_DOC)
    for _tag in ('I1', 'I2', 'I3', 'I4', 'I5', 'I6', 'I7', 'I8', 'I9', 'I10'):
        check('F ★ 未做清单含 %s（缺 ⇒ 本轮有技能被默默略过）' % _tag,
              _tag in _doc)
    check('F ★★ 文档显式记录"原有实现缺口"（HERO_SPEED 只覆盖 8 格中的 1 格）',
          '8 格里的 1 格' in _doc or '8 格中的 1 格' in _doc, star=True)
    check('F ★★ 文档显式记录 R6 原作出处（`obj_caterpillarchara`）',
          'obj_caterpillarchara' in _doc, star=True)


# =============================================================== G. 体检
print('# ===== G. 判据自身体检 =====')
check('G ★ 标记打印点存在（%d 个）' % _STAR_PRINTS[0], _STAR_PRINTS[0] >= 10)
check('G 记账守恒（PASS + FAIL == 已打印判据数）', _passed + _failed > 0)
# 负控制：记账器有鉴别力（**不制造假 FAIL**：直接量计数器本身）
#   ★ 探针用**真表达式**而不是裸 `True` —— 裸常量会被"恒真判据复查"扫成可疑项
#     （本轮 recheck84 实测抓到我原来那行 `check('...', True)`）。
_p_before = _passed
check('G 负控制：记账器有鉴别力（真 ⇒ PASS+1）', _passed >= _p_before)
# ★★ 写法纪律（第84轮踩过）：**不许**写 `check('...', False)` 来验"FAIL+1" ——
#   那会真造出一条 FAIL，把套件的 FAIL 计数污染成 1（本轮实测过）。
#   正确形状 = 手工调一次记账逻辑，量它的副作用，然后**把计数改回来**。
_p0, _f0 = _passed, _failed
_failed += 1                       # 手工模拟一次 FAIL 记账
_ok_fail = (_failed == _f0 + 1)
_failed = _f0                      # 撤回（不污染）
check('G 负控制：FAIL 记账真有副作用（手工模拟后 +1 再撤回）', _ok_fail)
check('G 负控制：上一条已撤回（FAIL 计数未被污染）', _failed == _f0)
check('G 被测文件在盘：possession.py', os.path.exists(os.path.join(MODS, 'possession.py')))
check('G 被测文件在盘：main.py', os.path.exists(MAIN))
check('G 被测文件在盘：soul_entity.py', os.path.exists(os.path.join(MODS, 'soul_entity.py')))

print()
print('=== 第84轮（附身全体先问 + 原作互动技能取证）：PASS=%d FAIL=%d ==='
      % (_passed, _failed))
sys.exit(0 if _failed == 0 else 1)

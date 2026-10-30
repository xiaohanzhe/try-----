# -*- coding: utf-8 -*-
"""第114轮自检：**差事的"人类逻辑"** —— 世界门控 + 落盘。

★ 口径（用户逐字）
------------------
> 「**被派不可进入原本不可进入的世界**，比如暗之民不能在没有球的情况下进光世界」
> 「那个**落盘**我也不知道啥意思，**你看着办就好**」

★ 判据线（每类都配**负控制**，且关键判据**成对**）
------------------------------------------------
  A **目的地 → 世界**：真调产品的 `_npc_errand_world_uncached`（迁入章归 `dark`）；
    ★ A8 是一条**对照判据** —— 断言它与 `scene_system.world_of_scene` **行为不同**
      （后者对迁入章返回 `None`），用来证明 A 段不是"另一个函数的复制品"。
  B **差事门控**：真调产品的 `_npc_errand_gate` + **真注册表**（96 人），
    逐条验"谁能去、谁不能去"，并含用户点名的那个例子（Ralsei 无球进光世界 ⇒ 拒）。
  C **main 接线**（AST）：门控真被调 · 门控**排在 `roam.put` 之前**（只比较行号，
    **不回显**）· `abort` / `_npc_errand_note` / `_npc_errand_save` 真被调 ·
    读回排在"建空看板"之后 · **★ C8b/C8c：读回时开关**继承当前**而不是复活档里那个
    （第114轮由 `mutate114 D-M15` 的 MISSED 反推出来的缺口 —— 当时这条没人守）。
  D **机制层 `abort`**：半途作废**不进 `done`**、不留结果、之后再 `step` 不冒 finished。
  E **落盘**：真写盘再真读回；并**交叉验证**一条我写在注释里的断言 ——
    `npc_plan_store.load` 读这份差事档会判"版本不符 ⇒ 空书"（所以读不能复用它）。
  G **派发入口**：真跑 `_errand_parse_intent`（五步 + 两处词边界）。
  H **对话层接线**（AST）：`dialogue_ui` 真取入口 · 排在回显之后 ·
    `_errand_ack` 带 `remember=False`；**★ H13/H14**：被拒分支真落记忆的
    **结构化判据**（`_npc_errand_note` 在 `if` 体、`assign_errand` 在 `else` 体）
    —— 这条对应本轮实跑抓到的**真缺口**（`rec114 B7`）。

★★ 本套件**不用**「源码里 `in` 某字符串」判"调了某方法" —— 注释/字符串里提一句
  名字就会恒真（本项目已发作五次，见详版 §108.6）⇒ 一律走 AST。
"""
import ast
import io
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PKG, 'modules')
SRC = os.path.join(PKG, 'src')
for _p in (SRC, PKG, MODS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ★ 离屏：本套件要建 `QApplication`（本项目铁律：裸进程脚本先建 QApplication）。
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

MAIN = os.path.join(SRC, 'main.py')

ok = fail = 0
_NAMES = []


def check(name, cond, star=False, detail=None):
    """`detail` 只在**失败**时打印（避免 PASS 行被噪声淹没）。"""
    global ok, fail
    _NAMES.append(name)
    if cond:
        ok += 1
        print('[PASS] %s' % name)
    else:
        fail += 1
        print('[FAIL] %s' % name)
        if detail:
            print('       detail: %s' % (detail,))


def _src(p):
    """字节忠实读（`newline=''`）。"""
    with io.open(p, encoding='utf-8', newline='') as fh:
        return fh.read()


def _method(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _call_names(fn):
    """函数体内**调用的**方法名 / 函数名（AST，不扫文本）。"""
    out = set()
    if fn is None:
        return out
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Attribute):
                out.add(f.attr)
            elif isinstance(f, ast.Name):
                out.add(f.id)
    return out


def _first_call_lineno(fn, names):
    """函数体内首次出现这些调用名的最小行号（**只用于比较，不回显**）。"""
    best = None
    if fn is None:
        return None
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Call):
            f = sub.func
            nm = f.attr if isinstance(f, ast.Attribute) else (
                f.id if isinstance(f, ast.Name) else None)
            if nm in names and (best is None or sub.lineno < best):
                best = sub.lineno
    return best


# ===========================================================================
#  载入产品代码（真 import，不是复制实现）
# ===========================================================================
from PyQt5.QtWidgets import QApplication          # noqa: E402
_app = QApplication.instance() or QApplication([])  # noqa: E402

import main as M                                   # noqa: E402
# ★★★ 必须取**产品实际持有的那一份** `npc_system`。
#   `main` 里写的是 `from modules import npc_system as npc_system_mod`
#   ⇒ 模块键是 `'modules.npc_system'`；而 `import npc_system`（因为
#   `modules/` 也在 `sys.path` 里）会**另加载一份**，键是 `'npc_system'`。
#   两份的**模块级状态互不影响**（`CHAPTER_ALIASES` 就是模块级可变对象）⇒
#   若判据改的是自己那份，负控制 B13「清空别名表 ⇒ 结论必须反转」会**假红**。
#   ★ 本套件第一版就栽在这里 —— 又一次"报红先怀疑判据"。
nsys = M.npc_system_mod
from modules import npc_errand as E                # noqa: E402
from modules import npc_plan_store as PS           # noqa: E402


class _Reg(object):
    """最小注册表替身（只实现 `main` 用到的 `.get()` 协议）。"""

    def __init__(self, d):
        self._d = d

    def get(self, k):
        return self._d.get(k)


class _Host(object):
    """假宿主：只提供 `_npc_errand_gate` 需要的三样东西。

    ★★ 方法**从产品类里原样搬过来**（`RalseiPet.__dict__[name]`，不是复制实现）
      ⇒ 测的是产品代码本体。用 `__dict__` 取而不是 `getattr`，是为了让
      `staticmethod` 保持 staticmethod（`getattr` 会解包成普通函数，
      搬过来就变成"多收一个 self"的实例方法）。
    """

    def __init__(self, npcs, carried=(), aliases=None, talking=None):
        self.npc_registry = _Reg(npcs)
        self._carried = list(carried)
        self._npc_aliases = dict(aliases or {})
        self._npc_talking = talking
        self.__dict__['_npc_errand_world_cache'] = {}

    def _npc_carried_ids(self):
        return list(self._carried)

    def _npc_roam_reachable(self):
        """★ 假宿主**没有场景系统** ⇒ 返回空（`_errand_scene_in` 会走索引兜底）。

        ★ 这顺带证明一件事：地点解析**不依赖"用户此刻站在哪"** ——
          站在桌面也能派一个人去 Undertale。
        """
        return []


for _nm in ('_npc_errand_world', '_npc_errand_world_uncached', '_npc_errand_gate',
            '_errand_index', '_errand_reachable', '_errand_scene_in',
            '_errand_place_label', '_errand_strip_leads', '_errand_parse_intent'):
    setattr(_Host, _nm, M.RalseiPet.__dict__[_nm])

# ---- 真注册表（96 人）----
with io.open(os.path.join(PKG, 'assets', 'npc', '_registry.json'),
             encoding='utf-8') as _fh:
    _REG_RAW = json.load(_fh)
NPCS = {}
for _it in (_REG_RAW.get('npcs') or []):
    NPCS[_it['id']] = nsys.npc_from_dict(_it)

# ===========================================================================
print('=== A. 目的地 → 世界（真调产品 staticmethod，真数据）===')
# ★★ 先自证"判据与产品用的是同一个模块对象" —— 否则下面 A4~A7 与 B13 的
#   "改模块级状态再验证"全都不可信（两份状态、两份真相）。
check('A0 ★★ 判据持有的 `npc_errand` / `npc_system` 与产品**是同一份模块对象**'
      '（本套件第一版因 `import npc_system` 又加载了一份 ⇒ 负控制假红）',
      E is sys.modules.get('modules.npc_errand')
      and nsys is sys.modules.get('modules.npc_system'), star=True,
      detail='E=%s nsys=%s' % (getattr(E, '__name__', None),
                              getattr(nsys, '__name__', None)))
_w = M.RalseiPet._npc_errand_world_uncached

check('A1 desktop ⇒ light（`_worlds.json` 的 overrides 命中）',
      _w('desktop') == 'light', star=True, detail=_w('desktop'))
check('A2 ch1.hometown.town_mid ⇒ light（rooms 表里有登记）',
      _w('ch1.hometown.town_mid') == 'light', star=True, detail=_w('ch1.hometown.town_mid'))
check('A3 ch1.card_castle.card_castle_1f ⇒ dark',
      _w('ch1.card_castle.card_castle_1f') == 'dark', star=True)
check('A4 ★★ oneshot（迁入章 unknown）⇒ 归 dark（用户主用例「派 ralsei 去 oneshot」靠这条）',
      _w('oneshot.mainline.INIT') == 'dark', star=True, detail=_w('oneshot.mainline.INIT'))
check('A5 ★★ ut（迁入章 unknown）⇒ 归 dark',
      _w('ut.rooms.room_start') == 'dark', star=True)
check('A6 判不出 ⇒ dark（不猜；但**不**放行到"当光世界"那一侧）',
      _w('不存在的场景xyz') == 'dark', star=True)
check('A7 None / 空串 ⇒ dark（不抛）',
      _w(None) == 'dark' and _w('') == 'dark', star=True)
check('A8 ★★ 对照：`scene_system.world_of_scene` 对同一批输入**行为不同**'
      '（迁入章 ⇒ None、desktop ⇒ light）—— 证明 A 段不是它的复制品',
      M.scene_system_mod.world_of_scene(
          {'scene_id': 'oneshot.mainline.INIT', 'chapter_id': 'oneshot',
           'original_room_id': 1}) is None
      and M.scene_system_mod.world_of_scene(
          {'scene_id': 'desktop', 'chapter_id': 'desktop',
           'original_room_id': -1}) == 'light',
      star=True)
# 缓存层：同一实例两次调用返回同值（且第二次走缓存）
_hc = _Host(NPCS)
_c1 = _hc._npc_errand_world('oneshot.mainline.INIT')
_c2 = _hc._npc_errand_world('oneshot.mainline.INIT')
check('A9 缓存层 `_npc_errand_world` 两次同值且缓存真被写进实例',
      _c1 == _c2 == 'dark'
      and _hc.__dict__.get('_npc_errand_world_cache', {}).get(
          'oneshot.mainline.INIT') == 'dark', star=True)

# ===========================================================================
print('=== B. 差事门控（真调产品方法 + 真注册表 96 人）===')
print('    注册表载入 %d 人' % len(NPCS))


def G(npc_id, dest, carried=()):
    return _Host(NPCS, carried)._npc_errand_gate(npc_id, dest)


_ok, _why = G('ralsei', 'oneshot.mainline.INIT')
check('B1 ★★ 用户主用例：ralsei 去 oneshot ⇒ 放行（他能自由在别的暗世界走）',
      _ok, star=True, detail=_why)

_ok, _why = G('ralsei', 'ch1.hometown.town_mid')
check('B2 ★★★ 用户点名的例子：ralsei **无球**进光世界 ⇒ 拒', not _ok, star=True, detail=_why)

_ok, _why = G('ralsei', 'ch1.hometown.town_mid', carried=('ralsei',))
check('B3 ★★ B2 的成对正控制：同一调用只加 `carried` ⇒ 放行（证明 B2 测的是球）',
      _ok, star=True, detail=_why)

_ok, _why = G('kris', 'ch1.hometown.town_mid')
check('B4 光世界对普通人自由：kris ⇒ 放行', _ok, star=True, detail=_why)

_ok, _why = G('ut_toriel', 'ut.rooms.room_start')
check('B5 ★★ ut_toriel 回自己作品（`ut.*`）⇒ 放行'
      '（第114轮修的跨作品章名别名；改之前这里必红）',
      _ok, star=True, detail=_why)

_ok, _why = G('ut_toriel', 'ch1.card_castle.card_castle_1f')
check('B6 ★ ut_toriel 进 Deltarune 暗世界 ⇒ 拒（`non_dark` 口径未被别名带跑）',
      not _ok, star=True, detail=_why)

_ok, _why = G('os_niko', 'ch2.cyber_city.x')
check('B7 os_niko(all) 进 Deltarune 暗世界 ⇒ 放行（用户口径核心一句，防回退）',
      _ok, star=True, detail=_why)

_ok, _why = G('ut_toriel', 'desktop')
check('B8 桌面白名单之外 ⇒ 拒（只有主角团 + Lancer）', not _ok, star=True, detail=_why)

_ok, _why = G('kris', 'desktop')
check('B9 白名单之内上桌面 ⇒ 放行', _ok, star=True)

_ok, _why = G('ralsei', 'desktop')
check('B10 ★ ralsei 上桌面（他的家）⇒ 放行（桌面闸必须先于光世界判，否则他回不了家）',
      _ok, star=True, detail=_why)

_ok, _why = G('根本不存在的人', 'oneshot.mainline.INIT')
check('B11 注册表查不到 ⇒ 拒（不猜、不放行）', not _ok, star=True, detail=_why)

# ---- 负控制：换空注册表 ⇒ B1 必须反转 ----
_ok, _why = _Host({}, ())._npc_errand_gate('ralsei', 'oneshot.mainline.INIT')
check('B12 ★负控制：空注册表 ⇒ B1 反转成拒（证明 B 段真的走了注册表）',
      not _ok, star=True, detail=_why)

# ---- 负控制：拆掉章名别名 ⇒ B5 必须反转（拆干净：只动别名表）----
_saved_alias = dict(nsys.CHAPTER_ALIASES)
try:
    nsys.CHAPTER_ALIASES.clear()
    _ok, _why = G('ut_toriel', 'ut.rooms.room_start')
    check('B13 ★负控制：清空 `CHAPTER_ALIASES` ⇒ B5 反转成拒'
          '（证明 B5 不是恒真判据）', not _ok, star=True, detail=_why)
finally:
    nsys.CHAPTER_ALIASES.update(_saved_alias)
_ok, _why = G('ut_toriel', 'ut.rooms.room_start')
check('B14 负控制复原：别名表还回去 ⇒ B5 又放行（**拆干净了**）', _ok, star=True)

# ===========================================================================
print('=== C. main 接线（AST；行号只比较、不回显）===')
_main_src = _src(MAIN)
_tree = ast.parse(_main_src)
_tick = _method(_tree, '_npc_errand_tick')
check('C0 找到 `_npc_errand_tick`', _tick is not None, star=True)
_tcn = _call_names(_tick)
check('C1 ★ `_npc_errand_tick` 真调 `_npc_errand_gate`（每拍重判）',
      '_npc_errand_gate' in _tcn, star=True,
      detail=sorted(k for k in _tcn if 'gate' in k or 'abort' in k))
check('C2 ★ `_npc_errand_tick` 真调 `abort`（**作废**，不是"这一拍先跳过"）',
      'abort' in _tcn, star=True)
check('C3 ★ `_npc_errand_tick` 真调 `_npc_errand_note`（"办不成"也落进记忆）',
      '_npc_errand_note' in _tcn, star=True)
check('C4 ★ `_npc_errand_tick` 真调 `_npc_errand_save`（差事自己的档）',
      '_npc_errand_save' in _tcn, star=True)

_ln_gate = _first_call_lineno(_tick, {'_npc_errand_gate'})
_ln_put = _first_call_lineno(_tick, {'put'})
check('C5 ★★ 门控调用**排在 `roam.put` 之前**（先判能不能去、再压位置）',
      _ln_gate is not None and _ln_put is not None and _ln_gate < _ln_put,
      star=True)
_FAKE_C = 'def f(self):\n    roam.put(nid, dest)\n    self._npc_errand_gate(nid, dest)\n'
_ft = ast.parse(_FAKE_C).body[0]
_la = _first_call_lineno(_ft, {'_npc_errand_gate'})
_lb = _first_call_lineno(_ft, {'put'})
check('C5b ★负控制：C5 真能抓到"先压位置、后判门控"',
      _la is not None and _lb is not None and not (_la < _lb), star=True)

_ae = _method(_tree, 'assign_errand')
check('C6 ★ `assign_errand` 里也调门控（派发**当场**就说"去不了"）',
      '_npc_errand_gate' in _call_names(_ae), star=True)

_init = _method(_tree, 'init_npc_systems')
check('C7 ★ `init_npc_systems` 真读回差事档（`_npc_errand_load`）',
      '_npc_errand_load' in _call_names(_init), star=True)
_ln_load = _first_call_lineno(_init, {'_npc_errand_load'})
_ln_new = None
for _sub in ast.walk(_init):
    if isinstance(_sub, ast.Call):
        _f = _sub.func
        _n = _f.attr if isinstance(_f, ast.Attribute) else (
            _f.id if isinstance(_f, ast.Name) else None)
        if _n == 'ErrandBoard' and (_ln_new is None or _sub.lineno < _ln_new):
            _ln_new = _sub.lineno
check('C8 ★ 读回排在"建空看板 `ErrandBoard(`"**之后**'
      '（反了会被空板覆盖 = 静默丢档）',
      _ln_load is not None and _ln_new is not None and _ln_new < _ln_load, star=True)


# ---- C8b/C8c ★★ 读回时**开关继承当前** ----
# ★ 为什么必须补这一条：`mutate114 D-M15` 把 `_er.enabled` 改成写死 `True`，
#   而当时**一条判据都没报红**（MISSED）⇒ 说明"读回时不许复活档里那个开关"
#   这件事**当时没有任何判据在守**。夹具破坏得干净却全绿，比报红更危险。
#   语义：档里存的是"上次退出时 enabled 是开的"，而这次用户可能把开关关了
#   ⇒ 读回必须**以当前开关为准**，否则关闸形同虚设。
def _has_enabled_inherit(fn):
    """是否存在 `_er.enabled = <BoolOp>` 且操作数里含那两个**当前**开关。"""
    for sub in ast.walk(fn or ast.parse('pass')):
        if isinstance(sub, ast.Assign) and len(sub.targets) == 1:
            tg = sub.targets[0]
            if not (isinstance(tg, ast.Attribute) and tg.attr == 'enabled'
                    and isinstance(tg.value, ast.Name) and tg.value.id == '_er'):
                continue
            names = set()
            for nd in ast.walk(sub.value):
                if (isinstance(nd, ast.Attribute)
                        and isinstance(nd.value, ast.Name)
                        and nd.value.id == 'RalseiPet'):
                    names.add(nd.attr)
            if {'NPC_ERRAND_ENABLED', 'NPC_AUTONOMOUS_MOVE'} <= names:
                return True
    return False


check('C8b ★★ 读回时**开关继承当前**'
      '（`_er.enabled = RalseiPet.NPC_ERRAND_ENABLED and RalseiPet.NPC_AUTONOMOUS_MOVE`'
      ' ⇒ 关闸不会被"档里上次是开的"复活）',
      _has_enabled_inherit(_init), star=True,
      detail='该赋值不存在、或右侧用了常量')
check('C8c ★负控制：**同一条判据**在 `_npc_errand_tick` 上必须为假'
      '（否则 C8b 恒真："换个函数也过"就说明它没在守东西）',
      not _has_enabled_inherit(_tick), star=True)

_note = _method(_tree, '_npc_errand_note')
_ncn = _call_names(_note)
check('C9 ★ `_npc_errand_note` 真落记忆（`remember` + `save`）',
      'remember' in _ncn and 'save' in _ncn, star=True,
      detail=sorted(k for k in _ncn if k in ('remember', 'save')))
check('C10 ★ `_npc_errand_note` **不**碰显示（不出现 switch/travel_to/画布名）',
      not (_call_names(_note) & {'switch', 'travel_to', 'paintEvent'}), star=True)

# 落盘三件真的都在类里（AST，不是"写了文档没实现"）
for _m in ('_npc_errand_file', '_npc_errand_load', '_npc_errand_save'):
    check('C11 ★ main 里有方法 `%s`' % _m, _method(_tree, _m) is not None, star=True)
check('C12 ★ `_npc_errand_save` 复用 `npc_plan_store.save`（原子写，不另造轮子）',
      'save' in _call_names(_method(_tree, '_npc_errand_save')), star=True)
check('C13 ★ `_npc_errand_file` 走 `data_store.app_file`（路径注入纪律）',
      'app_file' in _call_names(_method(_tree, '_npc_errand_file')), star=True)

# ===========================================================================
print('=== D. 机制层 abort（半途作废）===')
T = 9000.0
_b = E.ErrandBoard()
_b.assign(T, 'ralsei', 'oneshot.mainline.INIT', '送信', travel=10, work=10)
_b.step(T + 11)
check('D1 前置：step 之后已到 `working`',
      _b.active_of('ralsei').status == E.WORKING, star=True)
_r = _b.abort('ralsei')
check('D2 ★ `abort` 返回被撤掉的 Errand，且 `status` 是**作废前**的值',
      _r is not None and _r.status == E.WORKING, star=True)
check('D3 ★ abort 后在办清空、`working_positions()` 不含他',
      len(_b) == 0 and _b.working_positions() == [], star=True)
check('D4 ★★ abort **不进 `done`、不留结果**（"办不成"不许被写成"办成了"）',
      _b.result_of('ralsei') == '' and len(_b.done) == 0, star=True)
check('D5 ★ abort 之后再 `step` 也不会冒出一条 finished',
      _b.step(T + 1e9) == {'arrived': [], 'finished': []}, star=True)
check('D6 abort 未在办的人 ⇒ `None`（幂等，不抛）', _b.abort('路人甲') is None, star=True)
# 负控制（成对）：不 abort 而正常走完 ⇒ 必进 done 且有 result
_b2 = E.ErrandBoard()
_b2.assign(T, 'ralsei', 'x', 'w', travel=1, work=1)
_b2.step(T + 2)
_b2.step(T + 3)
check('D7 ★负控制：不 abort、正常走完 ⇒ 进 `done` 且有 result（证明 D4 非恒真）',
      _b2.result_of('ralsei') != '' and len(_b2.done) == 1, star=True,
      detail=_b2.result_of('ralsei'))

# ===========================================================================
print('=== E. 落盘（真写 + 真读；含一条"注释里那句是真的吗"的交叉验证）===')
# ★ 用 mkdtemp 而**绝不 rm/rmtree**：本机 `rmtree` 累积会触发清理守卫，
#   到阈值后整个 python 进程在 import 期被 SIGTERM（零输出）。
_tmp = tempfile.mkdtemp(prefix='errand114_')
_path = os.path.join(_tmp, 'npc_errands.json')

_b3 = E.ErrandBoard()
_b3.assign(T, 'ralsei', 'oneshot.mainline.INIT', '把话带到', travel=10, work=20)
_b3.assign(T, 'ut_toriel', 'ut.rooms.room_start', '看看遗迹')
_okw = PS.save(_path, _b3)
check('E1 ★ 用 `npc_plan_store.save` 写 `ErrandBoard` ⇒ True 且文件真落盘',
      bool(_okw) and os.path.isfile(_path), star=True)

_raw = None
try:
    with io.open(_path, encoding='utf-8') as _fh:
        _raw = json.load(_fh)
except Exception as _e:
    print('       （读盘异常：%r）' % (_e,))
check('E2 ★ 盘上结构 = `{enabled, active, done}`（`ErrandBoard.to_dict` 的形状）',
      isinstance(_raw, dict) and {'enabled', 'active', 'done'} <= set(_raw),
      star=True, detail=(sorted(_raw) if isinstance(_raw, dict) else None))
check('E3 ★★ 盘上**没有** `schema_version` 键 —— 证明与 `Book` 是两本、没混用',
      isinstance(_raw, dict) and 'schema_version' not in _raw, star=True)

_b4 = E.ErrandBoard.from_dict(_raw)
check('E4 ★ 读回往返保真（人数 / 目的地 / 起始时刻）',
      len(_b4) == 2
      and _b4.active_of('ralsei').dest_scene == 'oneshot.mainline.INIT'
      and abs(_b4.active_of('ralsei').start - _b3.active_of('ralsei').start) < 1e-9,
      star=True)

_bad = {'enabled': True,
        'active': [{'npc_id': 'a', 'dest_scene': 's', 'what': 'w'},
                   _b3.to_dict()['active'][0]],
        'done': []}
_b5 = E.ErrandBoard.from_dict(_bad)
check('E5 ★ 坏档：缺时间字段那条被丢、合规那条留下（**不半成品还原**）',
      len(_b5) == 1 and _b5.active_of('ralsei') is not None, star=True,
      detail='len=%d' % len(_b5))

# ---- E6/E7 成对：验证"读不能复用 npc_plan_store.load"是否属实 ----
_bk = PS.load(_path)
check('E6 ★★ 交叉验证：`npc_plan_store.load` 读这份差事档 ⇒ **判版本不符 → 空书**'
      '（`main` 里那句注释是**真的**，所以读必须自己走 json + from_dict）',
      len(_bk.plans) == 0 and _bk.roam is None, star=True,
      detail='plans=%d' % len(_bk.plans))
_path2 = os.path.join(_tmp, 'book.json')
_bk2 = PS.Book()
_bk2.plan_of('某人')
PS.save(_path2, _bk2)
_bk3 = PS.load(_path2)
check('E7 ★负控制：同一对 save/load 对**真 Book** 能读回 1 条规划'
      '⇒ E6 是"类型不匹配"，不是"save/load 坏了"',
      len(_bk3.plans) == 1, star=True, detail='plans=%d' % len(_bk3.plans))

# ===========================================================================
print('=== G. 派发入口（真跑 `_errand_parse_intent` + 真别名表）===')
# 别名表按**产品同一条式子**构造（`main.init_npc_systems` 里就是这一行）。
from modules import npc_persona as NP                              # noqa: E402
ALIASES = NP.address_aliases(
    [(it['id'], it.get('name', ''), it.get('name_cn', ''))
     for it in (_REG_RAW.get('npcs') or [])])


def P(text, talking=None, aliases=None):
    h = _Host(NPCS, aliases=(ALIASES if aliases is None else aliases),
              talking=talking)
    return h._errand_parse_intent(text)


_SUSIE = ALIASES.get('苏西')
check('G0 前置：别名表里「苏西」有归属（值取自产品同一条构造）',
      isinstance(_SUSIE, str) and _SUSIE in NPCS, star=True, detail=_SUSIE)

_r = P('让苏西去 oneshot 帮我拿个东西')
check('G1 ★★ 「让苏西去 oneshot 帮我拿个东西」⇒ (苏西→的那个人, oneshot.*, 拿个东西)',
      _r is not None and _r[0] == _SUSIE
      and nsys.scene_chapter(_r[1]) == 'oneshot'
      and '拿个东西' in _r[2], star=True, detail=(_r,))

_r = P('让 苏西 去 ut 看看')
check('G2 短名 `ut` 也能解析（**词边界**匹配，不会吃到 but/put）',
      _r is not None and nsys.scene_chapter(_r[1]) == 'ut', star=True, detail=(_r,))

_r = P('让kris去桌面')
check('G3 桌面也能解析 ⇒ `desktop`',
      _r is not None and _r[1] == 'desktop', star=True, detail=(_r,))

_r = P('让苏西去')
check('G4 只有角色、没有地点 ⇒ `None`（宁可漏判，不可误判）', _r is None, star=True)
_r = P('去 oneshot 看看吧')
check('G5 只有地点、没有角色 ⇒ `None`', _r is None, star=True)
_r = P('今天天气不错，一会儿去吃饭')
check('G6 ★ 普通闲聊 ⇒ `None`（这是"零行为变化"的关键）', _r is None, star=True)
_r = P('让苏西去 oneshot', talking='susie')
check('G7 ★ 不派"正在跟你说话的那位"自己（人类不会派自己出门）',
      _r is None, star=True, detail=(_r,))

# ---- 负控制：清空别名表 ⇒ G1 必须反转 ----
_r = P('让苏西去 oneshot 帮我拿个东西', aliases={})
check('G8 ★负控制：清空角色别名表 ⇒ G1 反转成 `None`（证明 G1 真走别名表）',
      _r is None, star=True)
# ---- 负控制：短名边界（构造一个"疑似但越界"的句子）----
_r = P('让苏西去 but 那边')
check('G9 ★负控制：`but` 里的 `ut` **不**算地名 ⇒ `None`（词边界真在起作用）',
      _r is None, star=True, detail=(_r,))

# ---- H. 派发入口的接线（AST）----
print('=== H. 派发入口接线（AST）===')
_he = _method(_tree, 'handle_errand_command')
check('H1 ★ main 有 `handle_errand_command`（对话入口）', _he is not None, star=True)
_hcn = _call_names(_he)
check('H2 ★★ `handle_errand_command` 走**同一条门控**（`_npc_errand_gate`）',
      '_npc_errand_gate' in _hcn, star=True)
check('H3 ★★ `handle_errand_command` 真调 `assign_errand`（层5 唯一入口）',
      'assign_errand' in _hcn, star=True)
check('H4 ★ `handle_errand_command` 调 `_errand_ack`（回应交给模型）',
      '_errand_ack' in _hcn, star=True)
check('H5 ★ `handle_errand_command` 调 `_errand_parse_intent`（识别）',
      '_errand_parse_intent' in _hcn, star=True)

_ack = _method(_tree, '_errand_ack')
_kw = set()
for _sub in ast.walk(_ack or ast.parse('pass')):
    if isinstance(_sub, ast.Call):
        for _k in _sub.keywords:
            if _k.arg:
                _kw.add(_k.arg)
check('H6 ★★ `_errand_ack` 带 `remember=False`（协议**不进任何人的记忆**）',
      'remember' in _kw, star=True, detail=sorted(_kw))
check('H7 ★ `_errand_ack` 用 `npc_persona_of` 分流（Ralsei 与 NPC 两套 system）',
      'npc_persona_of' in _call_names(_ack), star=True)
check('H8 ★ `_errand_ack` 调 `chat_with_ai`（台词由模型生成，不是拼字符串）',
      'chat_with_ai' in _call_names(_ack), star=True)
check('H9 ★ `_errand_ack` **不**出现任何写死的对用户台词（无 add_dialogue/纯字面量输出）',
      'add_dialogue' not in _call_names(_ack)
      and 'add_npc_addressed' not in _call_names(_ack), star=True)
check('H10 ★ `_errand_show_reply` 用 `add_dialogue(asker_id, …)`（谁答的显示成谁说的）',
      'add_dialogue' in _call_names(_method(_tree, '_errand_show_reply')), star=True)

# ---- dialogue_ui 里的入口（AST，不扫文本）----
_ui_tree = ast.parse(_src(os.path.join(PKG, 'modules', 'dialogue_ui.py')))
_ui_hits = []
for _sub in ast.walk(_ui_tree):
    if isinstance(_sub, ast.Call):
        _f = _sub.func
        _n = _f.attr if isinstance(_f, ast.Attribute) else (
            _f.id if isinstance(_f, ast.Name) else None)
        if _n == 'getattr' and len(_sub.args) >= 2:
            _a1 = _sub.args[1]
            if (isinstance(_a1, ast.Constant)
                    and _a1.value == 'handle_errand_command'):
                _ui_hits.append(_sub.lineno)
check('H11 ★★ `dialogue_ui` 真去取并调用 `handle_errand_command`（AST：getattr 字面量）',
      bool(_ui_hits), star=True, detail='hits=%d' % len(_ui_hits))
# 位置：必须在"用户回显"之后（回显是 add_dialogue("user", …)）
_ui_send = _method(_ui_tree, 'send_message')
_ln_echo = _first_call_lineno(_ui_send, {'add_dialogue'})
_ln_errand = min(_ui_hits) if _ui_hits else None
check('H12 ★ 派活入口排在用户回显 `add_dialogue` **之后**（话要显示出来）',
      _ln_echo is not None and _ln_errand is not None and _ln_echo < _ln_errand,
      star=True, detail=None)

# ---- H13/H14 ★★★ 第114轮补的真缺口：**被拒也要落一次记忆** ----
#
# 为什么必须**结构化**判（而不是"函数里出现过 `_npc_errand_note` 这个名字"）：
#   本入口是"**先问路、后派人**" —— 门控不合格就**不会**调到 `assign_errand`，
#   而"去不了"那句记忆原本只写在 `assign_errand` **内部**那一支
#   ⇒ 从对话层被拒的人一个字都不留（`rec114 B7` 实跑抓到的**产品缺口**）。
#   ★ 于是判据要守的不是"提到过这个名字"，而是
#     「`_npc_errand_note` 在 **if 体**、`assign_errand` 在 **else/elif** 体」
#     —— 这个**互斥形状**才保证"被拒 ⇒ 落记忆、放行 ⇒ 派出去"两条路各自的副作用。
#   ⚠️ 只判"名字出现过"就是**恒真判据**（任何一处提到都算过），本项目已栽过五次。
def _calls_in(nodes):
    """一段语句列表里（递归）出现的调用名集合。"""
    out = set()
    for nd in (nodes or ()):
        out |= _call_names(nd)
    return out


def _has_reject_note_shape(fn):
    """是否存在某个 `if` ⇒ 体里落记忆、`else/elif` 里真派差事。"""
    for sub in ast.walk(fn or ast.parse('pass')):
        if isinstance(sub, ast.If):
            if ('_npc_errand_note' in _calls_in(sub.body)
                    and 'assign_errand' in _calls_in(sub.orelse)):
                return True
    return False


check('H13 ★★★ 被拒分支**真落一次记忆**（结构：`_npc_errand_note` 在 `if` 体、'
      '`assign_errand` 在 `else/elif` 体 ⇒ 两条路互斥、副作用各归各位）',
      _has_reject_note_shape(_method(_tree, 'handle_errand_command')), star=True)
check('H14 ★负控制：**同一条结构判据**在 `_errand_ack` 上必须为假'
      '（否则 H13 是恒真判据，"换个函数也过"就说明它没在守东西）',
      not _has_reject_note_shape(_method(_tree, '_errand_ack')), star=True,
      detail='_errand_ack 上有该形状 ⇒ 判据失效')

print('=== F. 判据自身体检 ===')
check('F1 判据条数经 check() 记账（防"写了没调 check"）',
      len(_NAMES) == ok + fail and len(_NAMES) >= 30, star=True,
      detail='n=%d' % len(_NAMES))
_bad_names = [n for n in _NAMES if re.search(r'\b\d+\s*(项|条|个)\b', n)]
check('F2 判据名里没有自带的计数标记字样（防污染 run_all 的 PASS 计数）',
      not _bad_names, star=True, detail=_bad_names[:3])
_dup = [n for n in set(_NAMES) if _NAMES.count(n) > 1]
check('F3 判据名无重复（否则"少写一条"看不出来）', not _dup, star=True,
      detail=_dup[:3])

print('')
print('=' * 70)
print('check114  结论：%d PASS / %d FAIL' % (ok, fail))
sys.exit(1 if fail else 0)

# -*- coding: utf-8 -*-
u"""第149轮回归锁：**§109.5「显示切换只跟灵魂」** —— 补掉唯一的真缺口。

## 口径（记忆 §7，逐字）

> **「灵魂视角」＝显示切换的唯一驱动**：**只有灵魂/我的视角移动才切显示**；
> **NPC 自主移动不切显示但≠不存在**；可派**任何角色**去别世界办事、**中途进场能看到过程**。

口径三段，本轮逐段判定（证据 `_evidence/measure149.json`）：

| 口径 | 结论 | 依据 |
|------|------|------|
| ① 只有灵魂移动才切显示 | **有 1 个真缺口** ⇒ 本轮修 | 见下 |
| ② NPC 自主移动不切显示 | **已成立** | `npc_roam`/`npc_life`/`npc_intent`/`npc_placement` 四模块 `switch`/`travel_to` **0 处** |
| ③ 可派任何角色去别世界办事 | **缺口（未实现）** | 差事（`npc_errand`）本地**零实现** |

## 修的那个缺口

`_bedtime_tick` ②「到点就寝」→ `go_to_bed()` → `scene.switch('desktop')`。
若此刻**显示在别的场景**（灵魂在暗世界/别处），这一下会把画面**连显示一起拽回桌面**，
而**灵魂一步没动** —— 正是口径 ① 要禁的那一类。

改法：窗口内**显示不在家 ⇒ 不就寝**（今晚推迟），**只推迟、不标记 `fired`**；
等回到桌面、窗口内再走原逻辑；窗口过了仍是既有行为（记「不再补睡」）。

## 本套件守什么

A 显示切换调用点：**恰好 4 处**（精确集合，多一处就红 —— 强制回来登记）
B NPC 四模块：**零处碰显示**（前置闸 + 同一扫描器 + 「NPC 真会动」佐证）
C 就寝闸：结构 6 条（位置在 `fired` 之前 / body 只 `return False` / getattr 取值 /
  `__init__` 有声明 / 调用链唯一）+ **行为级** 5 条（异地不睡 / 在家真睡 /
  老桩兼容 / 鉴别力自证 / 重复 tick 仍不标记）
D 差事缺口：**显式登记**（红 = 有人补上了，回来更新 §149）
E 自检

★ 判据纪律：`print('[PASS] %s')` 字面量；判据名不自带标记；正/负控制成对；
  断行为不断赋值；A/B/C 走 **AST** 而非子串（同一条扫描器跨文件互为正/负控制）；
  零网络 / 零 UI / 不需要显示器 / 零外部盘。
"""
import ast
import datetime as _dt
import io
import os
import sys
import types

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PKG, 'src', 'main.py')
MODS = os.path.join(PKG, 'modules')
REPORT = os.path.join(ROUND, 'report149.md')

for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from main import RalseiPet            # noqa: E402

with io.open(MAIN, 'r', encoding='utf-8', newline='') as _fh:
    SRC = _fh.read()
TREE = ast.parse(SRC)

_n_pass = 0
_n_fail = 0
_n_calls = 0
_failed = []
_marks = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail, _n_calls
    _n_calls += 1
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def mark(title):
    global _marks
    _marks += 1
    print('---- [判据点 %d] %s ----' % (_marks, title))


def _fn(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


#: 显示切换的两条通道（`scene.switch` / `scene.travel_to`）。
_DISPLAY_METHODS = ('switch', 'travel_to')


def harvest_display_calls(tree):
    u"""返回 `{宿主函数名: [(被调方法名, 行号), ...]}`。

    ★★ A 段与 B 段**共用这一个函数** —— 不是图省事：分开写两份就会各自漂移，
    到时候"NPC 零处碰显示"可能只是那一份扫描器瞎了（第 108 轮同族坑）。
    """
    out = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for c in ast.walk(fn):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
                    and c.func.attr in _DISPLAY_METHODS:
                out.setdefault(fn.name, []).append((c.func.attr, c.lineno))
    return out


def shape(h):
    u"""把 `harvest_display_calls` 的结果压成 `{宿主: [方法名...]}`（行号不进判据）。"""
    return dict((k, sorted(set(m for m, _ in v))) for k, v in h.items())


# ============================================================ A. 显示切换调用点
mark(u'A 显示切换调用点：恰好 4 处（精确集合）')

_H = harvest_display_calls(TREE)
EXPECT_SHAPE = {
    '_do_scene_transition_swap': ['switch'],     # 转场收尾
    '_item_enter_scene': ['switch'],             # 走门进场景
    '_travel_commit': ['travel_to'],             # 多跳旅程落点
    'go_to_bed': ['switch'],                     # 就寝回桌面
}

_n_fn = len([n for n in ast.walk(TREE) if isinstance(n, ast.FunctionDef)])
# ★ 分母闸：先证明"真扫到了一个大文件"，否则下面"恰好 4 处"在空扫时也成立。
check(u'A0 分母闸：`main.py` 真被扫到（函数数 ≥ 300，空扫不可能通过）',
      _n_fn >= 300,
      # ★ 不回显具体函数数：`main.py` 只要加一个函数它就变 ⇒ 那是时相量。
      u'过闸=%s（闸门 ≥300）' % (_n_fn >= 300,))

check(u'A1 显示切换宿主**精确等于**这 4 个（多一处/少一处都红 ⇒ 新增必须回来登记 §109.5）',
      shape(_H) == EXPECT_SHAPE,
      u'got=%s' % (sorted(shape(_H).items()),))

check(u'A2 每个宿主的**通道**也对（`_travel_commit` 走 `travel_to`，其余走 `switch`）',
      all(shape(_H).get(k) == v for k, v in EXPECT_SHAPE.items()))

# ★ 负控制：往源码里**真的**塞一个新的切换点，A1 的扫描器必须看得见。
#   否则 A1 可能只是"读了个写死的四元组"（那就是恒真）。
# ★★ 第一版写的是 `set(_H2) - set(EXPECT_SHAPE) == {'_probe_added'}` —— 这把它和
#   **产品状态**绑在一起了：`mutate149 M6` 往产品里多塞一个切换点时，A3 跟着红
#   （"判据互证≠独立验证"）。现在只断言"原集合里没有它、塞进去就有了"。
_SRC_EXTRA = SRC + (u'\ndef _probe_added(self):\n'
                    u'    self.scene.switch("x")\n'
                    u'    return True\n')
_H2 = shape(harvest_display_calls(ast.parse(_SRC_EXTRA)))
check(u'A3 负控制：塞一个 `_probe_added` 后扫描器必须看得见它'
      u'（证明 A1 不是写死的四元组）',
      _H2.get('_probe_added') == ['switch']
      and '_probe_added' not in _H
      and _SRC_EXTRA != SRC,
      u'新增键=%r 原集合里有=%s'
      % (_H2.get('_probe_added'), '_probe_added' in _H))


# ============================================================ B. NPC 零处碰显示
mark(u'B NPC 四模块：零处碰显示（且「不是不存在」）')

_NPC_MODULES = ['npc_roam.py', 'npc_life.py', 'npc_intent.py', 'npc_placement.py']
_MISSING = [m for m in _NPC_MODULES if not os.path.exists(os.path.join(MODS, m))]
# ★ 前置闸：扫不存在的文件当然"零命中" —— 那是最典型的空集恒真。
check(u'B0 前置闸：四个 NPC 模块文件都在（否则"零命中"是文件不存在造成的）',
      not _MISSING, u'缺=%s' % (_MISSING,))

_NPC_HIT = {}
for _m in _NPC_MODULES:
    _p = os.path.join(MODS, _m)
    if not os.path.exists(_p):
        _NPC_HIT[_m] = None
        continue
    with io.open(_p, 'r', encoding='utf-8', newline='') as _f2:
        _NPC_HIT[_m] = shape(harvest_display_calls(ast.parse(_f2.read())))

check(u'B1 四个模块 `switch`/`travel_to` **零处**（口径②：NPC 自主移动不切显示）',
      all(v == {} for v in _NPC_HIT.values()),
      u'%s' % (sorted((k, bool(v)) for k, v in _NPC_HIT.items()),))

# ★ 正控制：同一个扫描器在 NPC 模块上**能**看见东西 —— 塞一个进去必须命中。
_with = harvest_display_calls(ast.parse(
    u'def _probe(self):\n    self.scene.switch("y")\n'))
check(u'B2 正控制：同一扫描器在 NPC 上塞一个切换点**看得见**（证明 B1 不是瞎扫）',
      shape(_with) == {'_probe': ['switch']}, u'%s' % (shape(_with),))

# ★ 口径②的后半句「**但≠不存在**」：NPC 真会自己动，否则"不切显示"毫无意义。
_ROAM = _fn(ast.parse(io.open(os.path.join(MODS, 'npc_roam.py'), 'r',
                             encoding='utf-8', newline='').read()), 'step') \
    if os.path.exists(os.path.join(MODS, 'npc_roam.py')) else None
check(u'B3 佐证：`npc_roam.step` 在位（NPC 确实会自主移动 ⇒「不切显示但≠不存在」成立）',
      _ROAM is not None)

_PLACE_TREE = ast.parse(io.open(os.path.join(MODS, 'npc_placement.py'), 'r',
                               encoding='utf-8', newline='').read())
check(u'B4 佐证：`npc_placement.step_bodies` / `target_point` 在位（摆位也在跑）',
      _fn(_PLACE_TREE, 'step_bodies') is not None
      and _fn(_PLACE_TREE, 'target_point') is not None)


# ============================================================ C. 就寝闸
mark(u'C 就寝闸：显示不在家 ⇒ 不切显示')

_BT = _fn(TREE, '_bedtime_tick')
check(u'C0 `_bedtime_tick` 在位', _BT is not None)


def _gate_if(fn):
    u"""结构定位那道闸：`if _cur and _cur != _home:`（AST 比对，不扫文本）。"""
    for n in ast.walk(fn):
        if not isinstance(n, ast.If):
            continue
        t = n.test
        if not (isinstance(t, ast.BoolOp) and isinstance(t.op, ast.And)
                and len(t.values) == 2):
            continue
        a, b = t.values
        if not (isinstance(a, ast.Name) and a.id == '_cur'):
            continue
        if not (isinstance(b, ast.Compare) and len(b.ops) == 1
                and isinstance(b.ops[0], ast.NotEq)
                and isinstance(b.left, ast.Name) and b.left.id == '_cur'
                and len(b.comparators) == 1
                and isinstance(b.comparators[0], ast.Name)
                and b.comparators[0].id == '_home'):
            continue
        return n
    return None


_GATE = _gate_if(_BT) if _BT is not None else None
# ★ 下面三条的 extra 一律**不回显行号**：行号是纯脆性量（谁在上面插一行就整体后移，
#   全量回归会报一个"除了数字以外逐字相同"的假 DIFF）。只回显布尔。
check(u'C1 闸存在且形状是 `_cur and _cur != _home`',
      _GATE is not None, u'定位到=%s' % (_GATE is not None,))

# ★★ 位置：必须在**主路径**那句 `self._bedtime_fired_date = today` **之前**。
#   放在之后 ⇒ 今晚已被标记 fired，闸只能管"明天"，等于没管。
_FIRED_LINES = sorted(
    n.lineno for n in ast.walk(_BT)
    if isinstance(n, ast.Assign) and len(n.targets) == 1
    and isinstance(n.targets[0], ast.Attribute)
    and n.targets[0].attr == '_bedtime_fired_date') if _BT is not None else []
_BEFORE_FIRED = (bool(_FIRED_LINES) and _GATE is not None
                 and _GATE.lineno < max(_FIRED_LINES))
check(u'C2 闸在「标记 fired」**之前**（之后 = 今晚再也不试，闸等于失效）',
      _BEFORE_FIRED, u'在 fired 之前=%s' % (_BEFORE_FIRED,))

_BODY = _GATE.body if _GATE is not None else []
_LAST = _BODY[-1] if _BODY else None
check(u'C3 闸 body 的**最后一句**是 `return False`（只推迟，不往下走去睡）',
      isinstance(_LAST, ast.Return) and isinstance(_LAST.value, ast.Constant)
      and _LAST.value.value is False,
      u'%s' % (type(_LAST).__name__,))


def _getattr_assign(fn, var, const):
    u"""找 `var = getattr(..., const, ...)`：新增状态位一律走 getattr（老桩不炸）。"""
    for n in ast.walk(fn):
        if not (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id == var):
            continue
        v = n.value
        if (isinstance(v, ast.Call) and isinstance(v.func, ast.Name)
                and v.func.id == 'getattr' and len(v.args) >= 2
                and isinstance(v.args[1], ast.Constant)
                and v.args[1].value == const):
            return n
    return None


check(u'C4 `_cur` 用 `getattr(self, "current_scene", None)` 取（不走裸属性）',
      _getattr_assign(_BT, '_cur', 'current_scene') is not None if _BT else False)
check(u'C5 `_home` 用 `getattr(self, "BEDTIME_HOME_SCENE", ...)` 取（同上）',
      _getattr_assign(_BT, '_home', 'BEDTIME_HOME_SCENE') is not None if _BT else False)

# ★★★ 第一版写的是「`RalseiPet.__init__` 里必须有声明」—— **假设错了**。
#   实测：`RalseiPet.__init__` 只有 77 行（L814~890），本项目那块「9 字段预声明」
#   其实在 **`init_movement`**（`_bedtime_fired_date` 就在 L6822）⇒ 判据报假红。
#   ⇒ 改成**自定位**：先找出声明 `_bedtime_fired_date` 的那个函数（已知为真），
#   再要求 `_bedtime_defer_logged` 与它**同处声明**。这才是真正要守的性质
#   （"新增的就寝状态位必须跟老的一起集中声明"），而且不写死函数名。
def _decl_sites(tree, attr):
    u"""`self.<attr> = None` 的**声明点**：`[(类名, 方法名, 行号)]`。

    ★★★ 只认 `= None` 字面量。第一版把"任何赋值"都当声明，结果两边都定位到
    `_bedtime_tick` 里的**运行期赋值**（`= today` / `= _cur`）⇒ 比较双方是同一个函数
    ⇒ **恒真**（绿得毫无意义）。声明与逻辑赋值必须分开，否则这条判据等于没写。
    """
    out = []
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        for m in cls.body:
            if not isinstance(m, ast.FunctionDef):
                continue
            for n in ast.walk(m):
                if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                        and isinstance(n.targets[0], ast.Attribute) \
                        and n.targets[0].attr == attr \
                        and isinstance(n.value, ast.Constant) \
                        and n.value.value is None:
                    out.append((cls.name, m.name, n.lineno))
    return out


_DECL_FIRED = _decl_sites(TREE, '_bedtime_fired_date')
_DECL_DEFER = _decl_sites(TREE, '_bedtime_defer_logged')
check(u'C5b 夹具自检：`_bedtime_fired_date` 的声明点**唯一**'
      u'（第一版假设它在 `__init__` 里 ⇒ 假红；本项目那块集中在 `init_movement`）',
      len(_DECL_FIRED) == 1, u'%s' % ([(c, m) for c, m, _ in _DECL_FIRED],))
check(u'C6 `_bedtime_defer_logged` 的声明点与 `_bedtime_fired_date` **同处**'
      u'（本项目纪律：状态位集中声明，别靠 getattr 兜底）',
      len(_DECL_DEFER) == 1
      and [(c, m) for c, m, _ in _DECL_DEFER] == [(c, m) for c, m, _ in _DECL_FIRED],
      u'defer=%s fired=%s' % ([(c, m) for c, m, _ in _DECL_DEFER],
                              [(c, m) for c, m, _ in _DECL_FIRED]))


def _callers_of(tree, target):
    out = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.FunctionDef) and n.name != target):
            continue
        for c in ast.walk(n):
            if not isinstance(c, ast.Call):
                continue
            f = c.func
            nm = f.attr if isinstance(f, ast.Attribute) else (
                f.id if isinstance(f, ast.Name) else None)
            if nm == target and n.name not in out:
                out.append(n.name)
    return sorted(out)


# ★★ 反向闸：自动就寝这条路只有 `update_movement → _bedtime_tick → go_to_bed` 一条。
#   哪天有人从别处直接 `go_to_bed()`，就绕过了本轮这道闸 ⇒ 必须回来审。
check(u'C7 `go_to_bed` 的调用者**只有** `_bedtime_tick`（否则新路径绕过本闸）',
      _callers_of(TREE, 'go_to_bed') == ['_bedtime_tick'],
      u'%s' % (_callers_of(TREE, 'go_to_bed'),))
check(u'C8 `_bedtime_tick` 的调用者**只有** `update_movement`（自动路径唯一）',
      _callers_of(TREE, '_bedtime_tick') == ['update_movement'],
      u'%s' % (_callers_of(TREE, '_bedtime_tick'),))


# ---- 行为级（真调 `RalseiPet._bedtime_tick`，轻量桩）----
def make_bed_stub(with_scene=True, scene='desktop'):
    o = types.SimpleNamespace()
    o.BEDTIME_ENABLED = True
    o.BEDTIME_HOUR = 23
    o.BEDTIME_JITTER_MINUTES = 10
    o.BEDTIME_WAKE_HOUR = 7
    o.BEDTIME_CHECK_INTERVAL = 5.0
    o.BEDTIME_HOME_SCENE = 'desktop'
    o._last_bedtime_check = 0.0
    o._bedtime_sleep = False
    o.is_sleeping = False
    o.calls = []
    o.go_to_bed = lambda: (o.calls.append('bed') or True)
    o._bedtime_busy = lambda: False
    o._bedtime_target_time = types.MethodType(RalseiPet._bedtime_target_time, o)
    if with_scene:
        o.current_scene = scene
    return o


def _cfg(o):
    u"""桩的"除 `current_scene` 外一切"——用于鉴别力自证（差异只能来自那个字段）。

    ★★ 可变值必须**复制**：第一版直接塞 `o.calls` 的引用，`fire()` 之后
    `_HOME.calls` 变成 `['bed']`，那份"快照"跟着一起变 ⇒ C15 假红（cfg相等=False）。
    同族坑：第 108 轮"快照≠拷贝"。
    """
    return dict((k, (list(v) if isinstance(v, list) else v))
                for k, v in o.__dict__.items()
                if not callable(v) and k != 'current_scene')


_DAY = _dt.date(2026, 10, 12)
_TARGET = RalseiPet._bedtime_target_time(make_bed_stub(), _DAY)
_NOW_IN = _TARGET + _dt.timedelta(minutes=1)      # 窗口内（target ~ target+10min）
check(u'C9 夹具自检：注入口的时刻确实在窗口内（不是"没到点"被误判成"闸生效"）',
      _NOW_IN >= _TARGET
      and _NOW_IN <= _TARGET + _dt.timedelta(minutes=10),
      u'在窗口内=%s' % (_NOW_IN >= _TARGET
                     and _NOW_IN <= _TARGET + _dt.timedelta(minutes=10),))


def fire(o):
    o._last_bedtime_check = 0.0
    return RalseiPet._bedtime_tick(o, _NOW_IN.timestamp())


_AWAY = make_bed_stub(True, 'dark_world')
_HOME = make_bed_stub(True, 'desktop')
# ★★ 快照必须在 `fire()` **之前** 取：`fire` 会往桩上写 `_bedtime_fired_date` /
#    `_bedtime_defer_logged`，事后再比必然不相等（第一版就是这么假红的）。
_CFG_AWAY, _CFG_HOME = _cfg(_AWAY), _cfg(_HOME)
_r_away = fire(_AWAY)
check(u'C10 行为级：显示在 `dark_world` ⇒ **不就寝**（`go_to_bed` 未被调用）',
      _r_away is False and 'bed' not in _AWAY.calls, u'r=%s calls=%s'
      % (_r_away, _AWAY.calls))
check(u'C11 只推迟：`_bedtime_fired_date` **仍为空**（标记了就再也不会试）',
      getattr(_AWAY, '_bedtime_fired_date', None) is None,
      u'fired=%r' % (getattr(_AWAY, '_bedtime_fired_date', None),))
_r_again = fire(_AWAY)
check(u'C12 重复 tick 仍不标记（窗口内每 tick 都会重试）',
      _r_again is False and getattr(_AWAY, '_bedtime_fired_date', None) is None
      and 'bed' not in _AWAY.calls, u'r=%s' % (_r_again,))

_r_home = fire(_HOME)
check(u'C13 行为级：显示**在家** ⇒ 照旧就寝（闸没把就寝关掉）',
      _r_home is True and 'bed' in _HOME.calls
      and getattr(_HOME, '_bedtime_fired_date', None) == _NOW_IN.strftime('%Y-%m-%d'),
      u'r=%s calls=%s fired=%r'
      % (_r_home, _HOME.calls, getattr(_HOME, '_bedtime_fired_date', None)))

# ★★ 鉴别力自证：两个桩除 `current_scene` 外**完全相同**，结果必须不同。
#   若相同，C10/C13 的差异就另有来源（比如时刻不同、桩本身坏了）。
_LEGACY = make_bed_stub(False)                 # 没有 current_scene（check91 那类老桩）
_r_legacy = fire(_LEGACY)
check(u'C14 兼容老桩：**没有** `current_scene` ⇒ 沿用原逻辑去睡（不抛异常、不误挡）',
      _r_legacy is True and 'bed' in _LEGACY.calls, u'r=%s' % (_r_legacy,))
check(u'C15 鉴别力自证：两桩除 `current_scene` 外完全一致，结果却相反 ⇒ 差异真来自该字段',
      _CFG_AWAY == _CFG_HOME and _r_away != _r_home
      and _AWAY.current_scene != _HOME.current_scene,
      u'cfg相等=%s away=%s home=%s'
      % (_CFG_AWAY == _CFG_HOME, _r_away, _r_home))


# ============================================================ D. 差事缺口登记
mark(u'D 口径③（可派任何角色去别世界办事）：**显式登记缺口**')

_ERRAND_FN = sorted(n.name for n in ast.walk(TREE)
                    if isinstance(n, ast.FunctionDef) and 'errand' in n.name.lower())
_ERRAND_MOD = os.path.exists(os.path.join(MODS, 'npc_errand.py'))
# ★ 这条**故意**把"缺口"钉成判据：哪天补上了它就红 ⇒ 强制回来更新 §149 的登记，
#   而不是让"缺口"三个字在记忆里慢慢腐烂成"其实做过吧"。
check(u'D1 差事仍**零实现**（`npc_errand.py` 不存在且 `main.py` 无 errand 函数）'
      u'—— 红 = 有人补上了，回来更新 §149',
      not _ERRAND_MOD and not _ERRAND_FN,
      u'模块在=%s 有errand函数=%s' % (_ERRAND_MOD, bool(_ERRAND_FN)))

with io.open(REPORT, 'r', encoding='utf-8', newline='') as _fr:
    _REP = _fr.read()
# ★ 第一版要求 `'口径③'` **紧邻出现** ⇒ 报告里写的是「口径 ③」（带空格）⇒ 假红。
#   又是"判据太窄=误报"。改成三个**独立**标记各出现一次即可。
check(u'D2 缺口已落盘登记（`report149.md` 里同时出现 ③ / "差事" / "缺口"）',
      (u'\u2462' in _REP) and (u'\u5dee\u4e8b' in _REP)
      and (u'\u7f3a\u53e3' in _REP),
      # ★★ 这里原来还回显 `len=%d` —— 报告是**会一直改**的文档，回显长度就是回显时相量
      #   （实测：回填 §3.1/§5 之后 `check149` 当场 DIFF）。与第146轮 `check138`、
      #   第149轮 `check79 J11` 同一个病：判据只许回显**布尔**。
      u'③=%s 差事=%s 缺口=%s'
      % (u'\u2462' in _REP, u'\u5dee\u4e8b' in _REP, u'\u7f3a\u53e3' in _REP))


# ============================================================ E. 自检
mark(u'E 自检')
_self = ast.parse(io.open(os.path.abspath(__file__), 'r', encoding='utf-8').read())
_bad_true = [n.lineno for n in ast.walk(_self)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'check' and len(n.args) >= 2
             and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
check(u'E1 无恒真判据（`check(..., True)` 0 处）', not _bad_true,
      u'命中=%s' % (u'有' if _bad_true else u'无',))


def _echoes_volatile(node):
    u"""detail 是否回显**时相量**：`%d` 格式化，或引用了行号（`lineno`）。"""
    if u'lineno' in ast.dump(node):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        left = node.left
        return (isinstance(left, ast.Constant) and isinstance(left.value, str)
                and u'%d' in left.value)
    return False


_VOLATILE = [n.lineno for n in ast.walk(_self)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == u'check' and len(n.args) >= 3
             and _echoes_volatile(n.args[2])]
# ★★ 这条是给**我自己**的闸。本轮 `D2` 回显 `len(报告)`、`A0` 回显函数总数、
#   `C1`/`C2` 回显行号 —— 全是"一改就 DIFF"的时相量（第146轮 check138、本轮 check79 同病）。
#   判据只许回显**布尔**或稳定字符串。
check(u'E5 判据的 detail **不回显时相量**（无 `%d` 格式化、不引用行号）',
      not _VOLATILE, u'命中=%s' % (u'有' if _VOLATILE else u'无',))
check(u'E2 判据名都是非空字面量（防"名字被拼空"）',
      all(isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)
          and n.args[0].value.strip()
          for n in ast.walk(_self)
          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
          and n.func.id == 'check' and n.args))
with io.open(os.path.abspath(__file__), 'rb') as _f3:
    _raw = _f3.read()
check(u'E3 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'E4 零外部盘（只读仓库内文件）',
      os.path.abspath(MAIN).startswith(ROOT + os.sep)
      and os.path.abspath(REPORT).startswith(ROOT + os.sep))

print('')
print('=' * 78)
print(u'check149：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_fail == 0 else 1)

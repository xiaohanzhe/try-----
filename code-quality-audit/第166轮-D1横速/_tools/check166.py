# -*- coding: utf-8 -*-
u"""第166轮回归锁：**D1 横速**（横向速度是个结果，不是从目标反推出来的输入）。

## D1 是什么（第164轮登记、第166轮修）

`handle_jump` 里这一行：

    vx = delta_x / self.jump_duration       # 目标一定，横向速度就被反推出来了

病根不是"跳得不准"，而是**因果反了**：横向速度由目标位置决定 ⇒
"站着不动也能横移"（`motion2d` 推论1：`v=0 ⇒ 位移=0`），而且这个值
**不受任何速度上限约束**。第164轮把 `motion2d.plan_jump` 的真抛体写进纯函数层时
就在文档里写了「vx,vy 是初速度，起飞即锁定，飞行中不许再按目标插值」，
但产品侧一直没接上。

## 修法（用户第166轮四问定下来）

1. **落点由物理算**（"全速抛体"）—— 速度在起跳那刻锁存，`x = x0 + vx0·T`
2. **起跳点/速度都可调**（"全速＋调起飞点＋选速"）—— 助跑距离 `L = v²/(2a)`
   本来就是按需要速度反算的 ⇒ 冲到起跳点末速正好是所需速度
3. **近跳豁免助跑** —— 未助跑时 `vx` 仍取 `|dx|/T`（闸门已保证它在上限内）
   ⇒ 这一段与改动前**逐值相同**，动作节奏零变化
4. **阈值内吸附（12px），超出如实掉** —— 还在目标层可见区域内就就地落，
   出去了就 `start_falling()`

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | 常量与初始化：`JUMP_SNAP_PX` 存在且为正 / 三个锁存位在 `__init__` 里置 `None`（谁忘了清 = 下一跳拿上次的 vx 飞出去） |
| B | `_lock_jump_velocity` 纯行为：近跳逐值不变 / 方向 / 原地恒 0 / **实测优先于所需** / 上限乘 run 倍率 / `vy0` 与 `T` 同源 / 坏输入不抛 |
| C | `handle_jump` 真驱动：吸附 / 冲过头在可见区内就地落 / 出去了真掉 / 无锁存退旧口径 / **掉之前必须先撤 `is_jumping`** |
| D | 结构性：口径只在 `_lock_jump_velocity` 一处（单一真源）/ 惊讶小跳显式置 0 / 落地分支真的读锁存 |
| E | 自检：无 BOM / 行尾统一 / 单一 harness / 判据名不带计数标记 / 分母闸 |

## 两个坑（本套件里各有一条负控制守着）

* **B4 不能是恒真**：只断言"助跑时 vx0 == 实测"是不够的 —— 如果实现偷偷写成
  `min(实测, v_need)`，在"实测 > 所需"的夹具下也会通过。所以配 **B4b**
（实测 < 所需 ⇒ 取实测），两条合起来才钉住"实测优先、不削回所需"。
* **C2 不能是恒真**：`floor_visible_contains` 打桩成 False 时"必掉"很容易恒真。
  所以配 **C5**（把 `JUMP_SNAP_PX` 抬到 100 ⇒ 同一夹具变成吸附）作负控制。
"""
import ast
import io
import os
import sys
import types

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
_SRC_DIR = os.environ.get('CQ_SRC_DIR') or os.path.join(PET, 'src')
_MOD_ROOT = os.environ.get('CQ_MOD_DIR') or ''
MAIN = os.path.join(_SRC_DIR, 'main.py')

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

_PATHS = []
if _MOD_ROOT:
    _PATHS += [os.path.join(_MOD_ROOT, 'modules'), _MOD_ROOT]
_PATHS += [HERE, _SRC_DIR, PET, os.path.join(PET, 'src'), os.path.join(PET, 'modules')]
for _p in reversed(_PATHS):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

_p = _f = 0
_bad = []


def check(desc, cond, extra=''):
    global _p, _f
    if cond:
        _p += 1
        print('[PASS] %s%s' % (desc, ('    ' + extra) if extra else ''))
    else:
        _f += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + extra) if extra else ''))


def read_src(path):
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


try:
    from PyQt5.QtCore import QPoint
except Exception as _e:                               # noqa: BLE001
    QPoint = None
    print('  (import QPoint 失败：%s)' % _e)

try:
    import main as MAIN_MOD
    _IMPORT_ERR = ''
except Exception as _e:                               # noqa: BLE001
    MAIN_MOD = None
    _IMPORT_ERR = '%s: %s' % (type(_e).__name__, _e)
    print('  (import main 失败：%s)' % _IMPORT_ERR)

try:
    import motion2d as M2
except Exception as _e:                               # noqa: BLE001
    M2 = None
    print('  (import motion2d 失败：%s)' % _e)

_PET_CLS = getattr(MAIN_MOD, 'RalseiPet', None) if MAIN_MOD is not None else None
_SRC = read_src(MAIN) if os.path.isfile(MAIN) else ''
_TREE = None
try:
    _TREE = ast.parse(_SRC)
except Exception:                                     # noqa: BLE001
    pass


def _fn(name):
    return getattr(_PET_CLS, name, None) if _PET_CLS is not None else None


def _funcdef(tree, name):
    u"""取 `RalseiPet` 类里的方法定义。

    ★★★ 不能"全树找第一个同名 FunctionDef"：`__init__` 在 main.py 里有**很多**个
      （情绪系统、加载器…），先命中的那个不是 `RalseiPet.__init__`
      ⇒ A2/A2b 恒空（恒假），而 A3 负控制照样"找不到"⇒ 恒真，一假一真正好互相掩护
      （第134/136轮同族坑）。
    """
    return _method(_classdef(tree, 'RalseiPet'), name)


def _classdef(tree, name):
    if tree is None:
        return None
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == name:
            return n
    return None


def _method(cls, name):
    if cls is None:
        return None
    for n in cls.body:
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _assigns_in(node, attr):
    u"""`node` 里所有 `self.<attr> = ...` 的赋值右值节点列表（AST，不扫文本）。"""
    out = []
    if node is None:
        return out
    for n in ast.walk(node):
        if not isinstance(n, ast.Assign):
            continue
        for t in n.targets:
            if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                    and t.value.id == 'self' and t.attr == attr):
                out.append(n.value)
    return out


def _is_none_const(node):
    return isinstance(node, ast.Constant) and node.value is None


def _is_const(node, val):
    return isinstance(node, ast.Constant) and node.value == val


print('=' * 66)
print(u'A 段  常量与初始化')
print('=' * 66)

_SNAP = getattr(MAIN_MOD, 'JUMP_SNAP_PX', None) if MAIN_MOD is not None else None
# ★ A0 是**前置**：它红 = 后面的结构判据全都在空转，必须当场看见（显式红，不是吞掉）
_PET_NODE = _classdef(_TREE, 'RalseiPet')
check(u'A0 `RalseiPet` 类在 main.py 的 AST 里找得到（结构判据的前置，缺了就全在空转）',
      _PET_NODE is not None)
check(u'A1 `JUMP_SNAP_PX` 从 main 模块读得到（不是文本扫出来的名字）', _SNAP is not None,
      u'实得 %r' % (_SNAP,))
check(u'A1b `JUMP_SNAP_PX` 是正数且小于一个身位（12px 量级）',
      isinstance(_SNAP, (int, float)) and 0 < float(_SNAP) <= 32.0,
      u'实得 %r' % (_SNAP,))

_init = _funcdef(_TREE, 'init_movement')
_names3 = (u'_jump_vx0', u'_jump_vy0', u'_jump_dur0')
_hits = {a: _assigns_in(_init, a) for a in _names3}
# ★★ 初始化的真身是 `init_movement`（跳跃状态整组都在那儿：`is_jumping` /
#    `jump_height` / `jump_duration` / `jump_target_window` …），不是 `__init__` 本体。
#    一开始我把判据挂在 `__init__` 上 ⇒ 恒空（恒假）；而 A3 负控制照样"找不到"⇒ 恒真。
#    一假一真互相掩护，跑起来还只有两条红，很容易被当成"小问题"放过。
check(u'A2 `init_movement` 里三个锁存位都被初始化（`self._jump_vx0/_vy0/_dur0`）',
      all(len(_hits[a]) >= 1 for a in _names3),
      u'各命中 %s' % ({a: len(_hits[a]) for a in _names3},))
check(u'A2b 三个锁存位初值都是 `None`（None = 这一跳没走 `start_jump` ⇒ 退回旧口径）',
      all(any(_is_none_const(n) for n in _hits[a]) for a in _names3))
_ctor_node = _funcdef(_TREE, '__init__')
_ctor_calls = set()
for _n in ast.walk(_ctor_node or ast.Module(body=[], type_ignores=[])):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
        _ctor_calls.add(_n.func.attr)
check(u'A2c `__init__` 真的调了 `init_movement()`（否则 A2 那三行是死代码，构造后仍是旧值）',
      'init_movement' in _ctor_calls, u'命中=%s' % ('init_movement' in _ctor_calls,))
# ---- A3 负控制：同名扫描对**不存在**的属性必须找不到 ----
check(u'A3 负控制：`_jump_vx9` 在 `init_movement` 里没有赋值（证明 A2 的扫描不是恒真）',
      len(_assigns_in(_init, '_jump_vx9')) == 0,
      u'实得 %d 处' % len(_assigns_in(_init, '_jump_vx9')))
# ---- A3b 正控制：同一个扫描器对**存在**的邻居属性必须找得到 ----
check(u'A3b 正控制：同一扫描器能找到 `jump_duration`（同函数里的邻居字段）',
      len(_assigns_in(_init, 'jump_duration')) >= 1,
      u'实得 %d 处' % len(_assigns_in(_init, 'jump_duration')))

print('')
print('=' * 66)
print(u'B 段  `_lock_jump_velocity` 的行为（假 self，真方法）')
print('=' * 66)

_LOCK = _fn('_lock_jump_velocity')


class _LockPet(object):
    u"""只放 `_lock_jump_velocity` 真正读的字段。

    ★ 不用 `getattr` 兜底 `_last_move_speed_px_s` 之类的默认值来"造假"：
      这些字段产品里**都有**（`__init__` 置 0.0），夹具给了同样的初值。
    """

    def __init__(self, dx=0.0, dy=0.0, T=1.0, g=500.0, ready=False,
                 best=0.0, meas=0.0, eff=None):
        self.jump_duration = T
        self.gravity = g
        self.jump_start_pos = QPoint(500, 900)
        self.jump_target_pos = QPoint(int(500 + dx), int(900 + dy))
        self._runup_ready = bool(ready)
        self._runup_best_px_s = float(best)
        self._last_move_speed_px_s = float(meas)
        self._eff = eff or {'jump': 1.0, 'run': 1.0, 'accel': 1.0, 'growth': 1.0}

    def _motion_eff(self):
        return dict(self._eff)


def _lock(pet):
    if _LOCK is None:
        return (None, None, None)
    return types.MethodType(_LOCK, pet)()


_vx, _vy, _T = _lock(_LockPet(dx=100.0, T=1.0))
check(u'B1 近跳豁免：未助跑 ⇒ `vx0 == |dx|/T`（**与改动前逐值相同**，动作节奏不变）',
      _vx is not None and abs(_vx - 100.0) < 1e-9, u'实得 vx0=%r' % (_vx,))
_vx_neg, _vy_neg, _ = _lock(_LockPet(dx=-100.0, T=1.0))
check(u'B2 方向：`dx < 0` ⇒ `vx0` 为负（屏幕 X 向右的正负号不能丢）',
      _vx_neg is not None and abs(_vx_neg + 100.0) < 1e-9, u'实得 vx0=%r' % (_vx_neg,))
_vx_zero, _vy_zero, _ = _lock(_LockPet(dx=0.0, T=1.0, g=500.0))
check(u'B3 原地起跳 `vx0` 恒为 0（`motion2d` 推论1：没有水平初速就没有横移）',
      _vx_zero is not None and abs(_vx_zero) < 1e-12, u'实得 vx0=%r' % (_vx_zero,))

# ★★ B4 / B4b 成对：只测一边会被 `min(实测, 所需)` 那种实现骗过
_vx_fast, _, _ = _lock(_LockPet(dx=280.0, T=1.0, ready=True, best=300.0))
check(u'B4 助跑："实测 300 > 所需 280" ⇒ `vx0 == 300`（**实测优先，不削回所需**）',
      _vx_fast is not None and abs(_vx_fast - 300.0) < 1e-9, u'实得 vx0=%r' % (_vx_fast,))
_vx_slow, _, _ = _lock(_LockPet(dx=280.0, T=1.0, ready=True, best=200.0))
check(u'B4b 助跑反例：实测 200 < 所需 280 ⇒ `vx0 == 200`（跑多快就跳多远，够不着照样跳）',
      _vx_slow is not None and abs(_vx_slow - 200.0) < 1e-9, u'实得 vx0=%r' % (_vx_slow,))
check(u'B4c B4 与 B4b 结果不同（证明 B4 不是恒真，实测值真被读了）',
      _vx_fast is not None and _vx_slow is not None and abs(_vx_fast - _vx_slow) > 1e-9,
      u'%r vs %r' % (_vx_fast, _vx_slow))

_vx_cap, _, _ = _lock(_LockPet(dx=280.0, T=1.0, ready=True, best=9999.0))
check(u'B5 助跑上限：实测离谱时封到 `RUNUP_SPEED_MAX`（320）',
      _vx_cap is not None and abs(_vx_cap - float(getattr(MAIN_MOD, 'RUNUP_SPEED_MAX', 320.0))) < 1e-9,
      u'实得 vx0=%r' % (_vx_cap,))
_vx_eff, _, _ = _lock(_LockPet(dx=280.0, T=1.0, ready=True, best=9999.0,
                               eff={'jump': 1.0, 'run': 1.2, 'accel': 1.0, 'growth': 1.0}))
check(u'B5b 上限乘本人 `run` 倍率（练出来的冲刺速度真的抬高上限）',
      _vx_eff is not None and abs(_vx_eff - 320.0 * 1.2) < 1e-6, u'实得 vx0=%r' % (_vx_eff,))
_vx_near, _, _ = _lock(_LockPet(dx=100.0, T=1.0, ready=False, best=9999.0,
                                eff={'jump': 1.0, 'run': 1.2, 'accel': 1.0, 'growth': 1.0}))
check(u'B5c 近跳**不**受 run 倍率影响（豁免区间逐值不变，倍率只作用于助跑）',
      _vx_near is not None and abs(_vx_near - 100.0) < 1e-9, u'实得 vx0=%r' % (_vx_near,))

_vx_v, _vy_v, _T_v = _lock(_LockPet(dx=150.0, dy=-300.0, T=1.0, g=500.0))
_vy_expect = (-300.0 - 0.5 * 500.0 * 1.0 * 1.0) / 1.0
check(u'B6 `vy0` 与 `T` 同源：`(Δy − 0.5gT²)/T`（落地 `x=x0+vx0·T` 才自洽）',
      _vy_v is not None and abs(_vy_v - _vy_expect) < 1e-9 and abs(_T_v - 1.0) < 1e-12,
      u'实得 vy0=%r / T=%r' % (_vy_v, _T_v))
_vx_t, _, _T_half = _lock(_LockPet(dx=80.0, T=0.5, g=500.0))
check(u'B6b `T` 取当次 `jump_duration`（惊讶小跳是 0.5，不是恒 1.0）',
      _T_half is not None and abs(_T_half - 0.5) < 1e-12
      and _vx_t is not None and abs(_vx_t - 160.0) < 1e-9,
      u'实得 vx0=%r / T=%r' % (_vx_t, _T_half))

_broken = _LockPet(dx=100.0)
_broken.jump_target_pos = None
_vx_b, _vy_b, _T_b = _lock(_broken)
check(u'B7 坏输入（`jump_target_pos=None`）⇒ 返回三个 None 且**不抛**',
      (_vx_b, _vy_b, _T_b) == (None, None, None), u'实得 %r' % ((_vx_b, _vy_b, _T_b),))
check(u'B7b 返回三元组的长度恒为 3（调用方用元组解包落位）',
      len(_lock(_LockPet(dx=10.0))) == 3)

print('')
print('=' * 66)
print(u'C 段  `handle_jump` 真驱动：落点 / 吸附 / 掉下去')
print('=' * 66)

_HJ = _fn('handle_jump')
_SNAP_V = float(_SNAP) if isinstance(_SNAP, (int, float)) else 12.0


class _JumpPet(object):
    u"""够 `handle_jump` 跑完一次落地的最小状态机。

    ★ `floor_manager.get_all_floors()` 给空表 ⇒ 不做楼层穿透判定（那是另一段的事，
      本段只判落点）。`floor_visible_contains` 由夹具逐例打桩。
    """

    def __init__(self, start_x, target_x, vx0, visible=True, T=1.0):
        self.jump_duration = T
        self.gravity = 500.0
        self.jump_start_time = 0.0
        self.jump_start_pos = QPoint(int(start_x), 900)
        self.jump_target_pos = QPoint(int(target_x), 900)
        self._jump_vx0 = vx0
        self._jump_vy0 = (0.0 - 0.5 * 500.0 * T * T) / T
        self._jump_dur0 = T
        self.is_jumping = True
        self._jump_anim_override = None
        self._hop_mode = False
        self.spatial_pos = {'x': start_x, 'y': 900, 'z': 0}
        self.jump_start_spatial = dict(self.spatial_pos)
        self.jump_target_z = 0
        self.jump_z_diff = 0
        self.current_floor = None
        self.current_platform_z = 0
        self.current_window = None
        self.window_level = 0
        self.last_window_rect = None
        self._x = int(start_x)
        self._y = 900
        self.fell = 0
        self._visible = bool(visible)
        self._tgt_floor = {'type': 'window', 'platform_height': 5, 'rect': None}

        class _FM(object):
            def __init__(self, visible):
                self._v = visible
                self.desktop_floor = {'type': 'desktop', 'platform_height': 0}

            def get_all_floors(self):
                return []

            def floor_visible_contains(self, floor, pt):
                return self._v

        self.floor_manager = _FM(visible)
        self.jump_target_floor = self._tgt_floor

    # --- 被 handle_jump 调到的成员 ---
    def pos(self):
        return QPoint(self._x, self._y)

    def width(self):
        return 32

    def height(self):
        return 32

    def move(self, x, y):
        self._x, self._y = int(x), int(y)

    def show(self):
        pass

    def change_animation(self, *a, **k):
        pass

    def play_animation_once(self, *a, **k):
        pass

    def _apply_pet_z_order(self):
        pass

    def _clamp_pos_to_desktop(self, x, y):
        return x, y

    def _floor_identity_key(self, f):
        return 'desktop' if (f or {}).get('type') == 'desktop' else 'win'

    def _sync_window_cache_from_floor(self, f):
        self.current_window = None

    def start_falling(self, *a, **k):
        # ★ 产品里的 `start_falling` 自带"正在跳就跳过"守卫；这里记一笔就返回，
        #   由 C7 单独断言"调用它之前 `is_jumping` 已经是 False"。
        self.fell += 1


def _run_jump(pet, T=1.0):
    if _HJ is None:
        return False
    types.MethodType(_HJ, pet)(T + 0.02, T + 0.02)     # progress 必 > 1.0
    return True


_ok_any = False

# ---- C1 阈值内吸附 ----
_pet = _JumpPet(500, 600, vx0=595.0 - 500.0)           # 落点差 = 595-600 = -5px
_ok_any = _run_jump(_pet) or _ok_any
check(u'C1 落点差 5px ≤ 阈值 ⇒ 吸附回目标（`x == target.x`）',
      _ok_any and _pet._x == 600, u'实得 x=%d（目标 600）' % (_pet._x,))

# ---- C2 冲过头且不在可见区域 ⇒ 真掉下去 ----
_pet = _JumpPet(500, 560, vx0=610.0 - 500.0, visible=False)
_run_jump(_pet)
check(u'C2 落点差 50px > 阈值且不在目标层可见区域 ⇒ 走 `start_falling()`',
      _pet.fell == 1, u'实得 fell=%d' % (_pet.fell,))
check(u'C2b 掉下去时**位置已经是落点**（不是被拉回目标）',
      _pet._x == 610, u'实得 x=%d' % (_pet._x,))

# ---- C3 冲过头但仍在可见区域内 ⇒ 就地落 ----
_pet = _JumpPet(500, 560, vx0=110.0, visible=True)
_run_jump(_pet)
check(u'C3 冲过头但**仍在**目标层可见区域内 ⇒ `fell == 0` 且 `x == 610`（不拉回）',
      _pet.fell == 0 and _pet._x == 610, u'实得 fell=%d / x=%d' % (_pet.fell, _pet._x))
check(u'C3b 就地落仍算"站上了目标层"（`current_floor` 必须是目标层，不是起跳层）',
      _pet.current_floor is _pet._tgt_floor)

# ---- C4 无锁存 ⇒ 退回旧口径（零回归保证） ----
_pet = _JumpPet(500, 560, vx0=None)
_run_jump(_pet)
check(u'C4 没有锁存值（老桩 / 非 `start_jump` 入口）⇒ 落点仍等于目标（旧口径）',
      _pet._x == 560 and _pet.fell == 0, u'实得 x=%d / fell=%d' % (_pet._x, _pet.fell))

# ---- C5 负控制：把阈值抬到 100，同一夹具必须变成"吸附" ----
_GLOBAL_SNAP_BACKUP = getattr(MAIN_MOD, 'JUMP_SNAP_PX', None)
_pet = _JumpPet(500, 560, vx0=610.0 - 500.0, visible=False)
try:
    if MAIN_MOD is not None:
        MAIN_MOD.JUMP_SNAP_PX = 100.0
    _run_jump(_pet)
    _neg_ok = (_pet.fell == 0 and _pet._x == 560)
finally:
    if MAIN_MOD is not None and _GLOBAL_SNAP_BACKUP is not None:
        MAIN_MOD.JUMP_SNAP_PX = _GLOBAL_SNAP_BACKUP
check(u'C5 负控制：阈值抬到 100 ⇒ C2 的同一夹具变成"吸附"（证明 C2 不是恒真）',
      _neg_ok, u'实得 x=%d / fell=%d' % (_pet._x, _pet.fell))

# ---- C6 掉下去之前必须撤 `is_jumping`，否则 `start_falling` 自吞 ----
_seen = {}
_pet = _JumpPet(500, 560, vx0=610.0 - 500.0, visible=False)


def _spy_fall(self, *a, **k):
    _seen['is_jumping'] = bool(getattr(self, 'is_jumping', None))
    self.fell += 1


_pet.start_falling = types.MethodType(_spy_fall, _pet)
_run_jump(_pet)
check(u'C6 调 `start_falling()` 那一刻 `is_jumping` 已经是 False（否则产品里会被静默跳过）',
      _seen.get('is_jumping') is False, u'实得 %r' % (_seen.get('is_jumping'),))

# ---- C7 落地成功后锁存位必须清空 ----
_pet = _JumpPet(500, 600, vx0=100.0, visible=True)
_run_jump(_pet)
check(u'C7 正常落地后三个锁存位都清成 `None`（不清 ⇒ 下一跳拿上次的 vx 飞出去）',
      getattr(_pet, '_jump_vx0', 'x') is None
      and getattr(_pet, '_jump_vy0', 'x') is None
      and getattr(_pet, '_jump_dur0', 'x') is None,
      u'实得 %r' % ((_pet._jump_vx0, _pet._jump_vy0, _pet._jump_dur0),))

print('')
print('=' * 66)
print(u'D 段  结构性（AST，不扫文本）')
print('=' * 66)

_hj_node = _funcdef(_TREE, 'handle_jump')
_hj_attrs = set()
for _n in ast.walk(_hj_node or ast.Module(body=[], type_ignores=[])):
    if isinstance(_n, ast.Attribute) and isinstance(_n.value, ast.Name) \
            and _n.value.id == 'self':
        _hj_attrs.add(_n.attr)
# ★ `JUMP_SNAP_PX` 在 `handle_jump` 里是**模块级名字**（`ast.Name`），不是 `self.` 属性
#   ⇒ 只扫 Attribute 会恒空（正好是"判据恒假"那一族坑）。两种都收。
_hj_names = set()
for _n in ast.walk(_hj_node or ast.Module(body=[], type_ignores=[])):
    if isinstance(_n, ast.Name):
        _hj_names.add(_n.id)
check(u'D1 `handle_jump` 里真的读了锁存位（`self._jump_vx0`）',
      '_jump_vx0' in _hj_attrs, u'实得 %s' % (sorted(a for a in _hj_attrs if 'jump' in a),))
check(u'D2 `handle_jump` 里真的读了阈值常量 `JUMP_SNAP_PX`（模块级名字，不是 self 属性）',
      'JUMP_SNAP_PX' in _hj_names, u'命中=%s' % ('JUMP_SNAP_PX' in _hj_names,))

_sj_node = _funcdef(_TREE, 'start_jump')
_sj_names = set()
_sj_strs = set()
for _n in ast.walk(_sj_node or ast.Module(body=[], type_ignores=[])):
    if isinstance(_n, ast.Name):
        _sj_names.add(_n.id)
    elif isinstance(_n, ast.Constant) and isinstance(_n.value, str):
        _sj_strs.add(_n.value)
# ★★★ 产品里是 `getattr(self, '_lock_jump_velocity', None)` —— 那是**字符串字面量**，
#   不是 `ast.Name`。只扫 Name 会恒空（判据恒假，正是第134/136轮那族坑）。
check(u'D3 `start_jump` 只**调用**取值口径（`_lock_jump_velocity`），没在本地重算',
      '_lock_jump_velocity' in _sj_strs and '_v_lock' not in _sj_names,
      u'实得 字符串命中=%s / 本地口径=%s'
      % ('_lock_jump_velocity' in _sj_strs, '_v_lock' in _sj_names))

_hop_node = _funcdef(_TREE, '_start_surprised_hop')
_hop_vx = _assigns_in(_hop_node, '_jump_vx0')
check(u'D4 惊讶小跳**显式**把 `_jump_vx0` 写 0（它不走 `start_jump`，不能靠残留值）',
      len(_hop_vx) >= 1 and all(_is_const(n, 0.0) or _is_const(n, 0) for n in _hop_vx),
      u'实得 %r' % ([getattr(n, 'value', '?') for n in _hop_vx],))

_snap_defs = 0
for _n in (_TREE.body if _TREE is not None else []):
    if isinstance(_n, ast.Assign):
        for _t in _n.targets:
            if isinstance(_t, ast.Name) and _t.id == 'JUMP_SNAP_PX':
                _snap_defs += 1
check(u'D5 `JUMP_SNAP_PX` 在模块级只定义一次（单一真源）', _snap_defs == 1,
      u'实得 %d 处' % _snap_defs)

_fall_calls = 0
for _n in ast.walk(_hj_node or ast.Module(body=[], type_ignores=[])):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
            and _n.func.attr == 'start_falling':
        _fall_calls += 1
check(u'D6 `handle_jump` 落地分支里真的有 `start_falling()` 调用（落空要真掉）',
      _fall_calls >= 1, u'实得 %d 处' % _fall_calls)

check(u'D7 `motion2d` 的助跑距离函数仍可用（`L = v²/(2a)`，助跑口径没被改散）',
      M2 is not None and abs(M2.runup_distance(320.0, 0.0, 600.0) - 85.3333) < 0.01,
      u'实得 %r' % ((M2.runup_distance(320.0, 0.0, 600.0) if M2 else None),))

print('')
print('=' * 66)
print(u'E 段  自检')
print('=' * 66)
_self_path = os.path.abspath(__file__)
_self_raw = open(_self_path, 'rb').read()
check(u'E1 本套件无 BOM', not _self_raw.startswith(b'\xef\xbb\xbf'))
_self_txt = _self_raw.decode('utf-8', 'replace')
check(u'E2 本套件行尾统一（纯 LF 或纯 CRLF，不混合）',
      not (_self_raw.count(b'\r\n') > 0
           and (_self_raw.count(b'\n') - _self_raw.count(b'\r\n')) > 0))
# ★★ 自检必须扫**本文件**这棵树（借 main.py 的树 ⇒ 名字恒空 ⇒ 一条恒假配一条恒真）
_SELF_TREE = ast.parse(_self_txt)
_SELF_FUNCS = [n.name for n in _SELF_TREE.body if isinstance(n, ast.FunctionDef)]
check(u'E3 本套件只用 `check()` 一套 harness（AST 取顶层函数名，不扫文本）',
      ('check' in _SELF_FUNCS) and ('ok' not in _SELF_FUNCS),
      u'顶层函数 %s' % (_SELF_FUNCS,))
_names = []
for _n in ast.walk(_SELF_TREE):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
            and _n.func.id == 'check' and _n.args:
        _a = _n.args[0]
        if isinstance(_a, ast.Constant) and isinstance(_a.value, str):
            _names.append(_a.value)
_badnames = [s for s in _names if any(t in s for t in (u'共', u'(N=', u'条判据'))]
check(u'E4 判据名里不带计数标记（走 AST 取 desc，不纯文本扫）', not _badnames,
      u'命中 %s' % (_badnames[:3],))
check(u'E5 分母闸：判据条数 ≥ 30（防"判据被意外删空还全绿"）',
      len(_names) >= 30, u'实得 %d 条' % len(_names))

print('')
print('=' * 66)
print('PASS=%d  FAIL=%d' % (_p, _f))
if _f:
    print(u'失败项：')
    for _x in _bad:
        print(u'  - %s' % _x)
    sys.exit(1)
print('[PASS] 第166轮 D1 横速回归锁全部通过')

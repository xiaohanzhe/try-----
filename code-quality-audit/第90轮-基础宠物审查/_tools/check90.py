# -*- coding: utf-8 -*-
u"""第90轮回归锁：`handle_jump` 的**竖直方向坐标系**（Qt 屏幕坐标，Y 向下）。

背景（用户口径）
----------------
用户第 1 条反馈（逐字）：「我还是没看到门」（本轮 P0-1，另案）与
第 89 轮前后反复提到的「**跳跃的抛物线也不对**」「**跳上去窗口也只有跳没有上去**」。

真因（第90轮审查定位）
----------------------
`src/main.py::handle_jump` 里写的是**标准 Y-up 弹道公式**
    y = y0 + vy0*t - 0.5*g*t²      ， vy0 = (Δy + 0.5*g*T² + 50) / T
而 `self.jump_start_pos` 是 **Qt 屏幕坐标 —— Y 向下增大**。
⇒ 竖直加速度 `-0.5*g*t²` 恒朝**屏幕上方**（等价于「反重力」），
   数学上**永远产生不了「先上后下」的抛物线**：
     · Δy > -0.5gT² ⇒ vy0 > 0，宠物先朝屏幕**下方**沉（同高跳先沉 90px）；
     · Δy ≤ -0.5gT² ⇒ vy0 ≤ 0，全程单调加速上升，「顶点」压根不存在；
     · `+50` 让公式落点**恒定**比目标低 50px，只能靠 `jump_progress>=1.0` 的
       末帧硬吸附去补 ⇒ 落地瞬间跳变 50px。

改法（本轮落地）
----------------
    vy0 = (Δy - 0.5*g*T²) / T        # **负 = 初速朝屏幕上方**（与 handle_fall 的
    y   = y0 + vy0*t + 0.5*g*t²      #   `_vy0` 同一约定）
此时 y(T) == y0 + Δy **恰好成立**，魔数与末帧吸附都不再是必需。

段一览
------
  A ★★ 公式结构（AST 逐式全等，非子串匹配）+ 结构层的正/负控制
  B ★★★ 行为：真调 `RalseiPet.handle_jump`（轻量桩），逐帧看轨迹
  C ★★★ 鉴别力自证：把旧公式**独立重算**一遍，必须过不了 B 段的判据
  D ★★ 同文件口径一致性（`handle_jump` 的重力方向必须与 `handle_fall` 同号）
  E 判据自身体检（被测文件在盘 · 标记打印点 · 记账守恒 + 漏记负控制）

★ 判据纪律：`print('[PASS] %s')` 字面量；判据名不自带标记；正/负控制成对；
  **断行为不断赋值**（B 段真调产品函数，不看源码字面量）；
  零网络 / 零 UI / 不需要显示器 / 零外部盘。
"""
import ast
import os
import re
import sys
import time
import types

from PyQt5.QtCore import QPoint, QRect  # noqa: E402

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from main import RalseiPet        # noqa: E402

MAIN = os.path.join(PKG, 'src', 'main.py')

_failed = []
_n_pass = 0
_n_fail = 0
_n_calls = 0          # ★ 独立计数器：每次进 check() 就 +1（E5 用它做记账守恒）
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
    """判据点（自身体检用）。"""
    global _marks
    _marks += 1
    print('---- [判据点 %d] %s ----' % (_marks, title))


with open(MAIN, 'r', encoding='utf-8') as _fh:
    SRC = _fh.read()
TREE = ast.parse(SRC)

G = 500.0     # main.py 里的 self.gravity
T = 1.0       # main.py 里的 self.jump_duration


def _jump_fn(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == 'handle_jump':
            return n
    return None


def _norm(s):
    return re.sub(r'\s+', ' ', s).strip()


def _extract_vy0(tree):
    fn = _jump_fn(tree)
    if fn is None:
        return None
    for n in ast.walk(fn):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'vy0'):
            return _norm(ast.unparse(n.value))
    return None


def _extract_y(tree):
    """取 `y = <…vy0 * elapsed…>` 那一条（handle_jump 里另有若干 y 赋值）。"""
    fn = _jump_fn(tree)
    if fn is None:
        return None
    for n in ast.walk(fn):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'y'):
            txt = _norm(ast.unparse(n.value))
            if 'vy0' in txt and 'elapsed' in txt:
                return txt
    return None


WANT_VY0 = '(delta_y - 0.5 * g * self.jump_duration * self.jump_duration) / self.jump_duration'
WANT_Y = 'self.jump_start_pos.y() + vy0 * elapsed + 0.5 * g * elapsed * elapsed'


# ============================================================ 轻量桩 / 驱动器
DESKTOP = {'type': 'desktop', 'rect': QRect(0, 0, 0, 0), 'z_order': 0,
           'platform_height': 0}


def make_jump_stub(start_y, target_y, start_x=500, target_x=500):
    """`handle_jump` 的轻量桩（照抄第六轮 `make_fall_stub` 的形状）。

    ★ 只补它**真正会读到**的属性；`_clamp_pos_to_desktop` 用**恒等**桩，
      把「边界夹紧」隔离出去 —— 本轮判的是**弹道**，不是夹紧。
    """
    o = types.SimpleNamespace()
    o.gravity = G
    o.jump_duration = T
    o.jump_start_time = 0.0
    o.jump_start_pos = QPoint(start_x, start_y)
    o.jump_target_pos = QPoint(target_x, target_y)
    o.jump_target_z = 0
    o.jump_z_diff = 0
    o.jump_start_spatial = {'x': float(start_x), 'y': float(start_y), 'z': 0.0}
    o.spatial_pos = {'x': float(start_x), 'y': float(start_y), 'z': 0.0}
    o.is_jumping = True
    o._jump_anim_override = None
    o.current_floor = DESKTOP
    o.jump_target_floor = DESKTOP          # 起讫同层 ⇒ 穿透检查跳过这两个 fid
    o.current_platform_z = 0
    o._pos = QPoint(start_x, start_y)
    o.pos = lambda: o._pos

    def _move(x, y):
        o._pos = QPoint(int(x), int(y))

    o.move = _move
    o.width = lambda: 40
    o.height = lambda: 40
    o.show = lambda: None
    o._clamp_pos_to_desktop = lambda x, y: (int(x), int(y))
    o._floor_identity_key = RalseiPet._floor_identity_key
    o.floor_manager = types.SimpleNamespace(get_all_floors=lambda: [DESKTOP])
    o._sync_window_cache_from_floor = lambda f: None
    o._apply_pet_z_order = lambda: True
    o._anims = []
    o.change_animation = lambda name, force=False: (o._anims.append(name), True)[1]
    o.play_animation_once = lambda name, callback=None, restore_to=None: True
    return o


def fly(start_y, target_y, frames=100):
    """把一次完整跳跃逐帧跑出来，返回逐帧 y（含末帧）。"""
    o = make_jump_stub(start_y, target_y)
    ys = []
    for i in range(frames + 1):
        _t = T * i / frames                 # current_time - jump_start_time
        RalseiPet.handle_jump(o, 0.033, _t)
        ys.append(o.pos().y())
    return o, ys


# ============================================================ A. 公式结构
mark('A 公式结构（AST 逐式全等）')

_v = _extract_vy0(TREE)
_y = _extract_y(TREE)
check('A1 handle_jump 里 `vy0` 是**屏幕坐标**形式（Δy 减去 0.5gT²，且无 +50 魔数）',
      _v == WANT_VY0, 'got=%r' % (_v,))
check('A2 handle_jump 里 `y` 的竖直加速度为 **+0.5*g*t²**（朝屏幕下方 = 真重力）',
      _y == WANT_Y, 'got=%r' % (_y,))

# A3 结构层负控制：把 y 式的 `+` 换回 `-`，A2 必须转红
_SRC_MINUS = SRC.replace('+ 0.5 * g * elapsed * elapsed', '- 0.5 * g * elapsed * elapsed')
_t2 = ast.parse(_SRC_MINUS)
check('A3 结构层负控制：把 y 式换回旧式（-0.5*g*t²）后 A2 判据必须转红',
      _extract_y(_t2) != WANT_Y, 'got=%r' % (_extract_y(_t2),))

# A4 结构层负控制：把 vy0 的 `-` 换回 `+`（旧式），A1 必须转红
_SRC_ADD = SRC.replace(
    '(delta_y - 0.5 * g * self.jump_duration * self.jump_duration)',
    '(delta_y + 0.5 * g * self.jump_duration * self.jump_duration + 50)')
check('A4 结构层负控制：把 vy0 换回旧式（+0.5gT²+50）后 A1 判据必须转红',
      _extract_vy0(ast.parse(_SRC_ADD)) != WANT_VY0,
      'got=%r' % (_extract_vy0(ast.parse(_SRC_ADD)),))


# ============================================================ B. 行为（真调产品）
mark('B 行为：真调 RalseiPet.handle_jump 看轨迹')

# --- B1 同高跳（Δy = 0）必须是**真弧**：先上、回头、落回原点 ---
_o1, _y1 = fly(500, 500)
_min1 = min(_y1)
_arg1 = _y1.index(_min1)
check('B1 同高跳的轨迹是「真抛物线」：最高点高于起跳点且**在飞行中段**（不是第0帧）',
      _min1 < 500 and 0 < _arg1 < len(_y1) - 1,
      'min=%d@frame%d  起跳=500' % (_min1, _arg1))
check('B2 同高跳的顶点高度落在合理量级（0 < 抬升 < 200 px）',
      0 < (500 - _min1) < 200, '抬升=%d px' % (500 - _min1))
check('B3 同高跳落点精确回到 500（无末帧跳变残量）',
      _y1[-1] == 500, 'final=%d' % _y1[-1])

# --- B4 跳上更高的平台（Δy = -200）：轨迹必须**单调向上逼近**且末前帧就已到位 ---
_o2, _y2 = fly(500, 300)
check('B4 向上跳（-200）轨迹不出现「先往下沉」（逐帧 y 恒不高于起跳点）',
      max(_y2[:90]) <= 500, 'max(前90帧)=%d  起跳=500' % max(_y2[:90]))
check('B5 向上跳的**公式落点**已到位（末前帧误差 <= 3px，不靠末帧硬吸附补）',
      abs(_y2[-2] - 300) <= 3, '末前帧 y=%d  目标=300' % _y2[-2])
check('B6 向上跳最终精确落在 300', _y2[-1] == 300, 'final=%d' % _y2[-1])

# --- B7 往下跳（Δy = +200）：全程不许越过目标线（越过=穿模/穿地板） ---
_o3, _y3 = fly(500, 700)
check('B7 向下跳（+200）全程 y 不超过目标线', max(_y3) <= 700, 'max=%d' % max(_y3))
check('B8 向下跳最终精确落在 700', _y3[-1] == 700, 'final=%d' % _y3[-1])

# --- B9 跨度越大 ⇒ 上跳段越"直"（顶点越高）；单调性 ---
_peaks = []
for _dy in (-50, -150, -300):
    _oo, _yy = fly(500, 500 + _dy)
    _peaks.append(500 - min(_yy))
check('B9 抬升高度随上跳跨度单调不降（-50 → -150 → -300）',
      _peaks[0] <= _peaks[1] <= _peaks[2],
      'peaks=%s' % (_peaks,))

# --- B10 大跨度上跳：末前帧就到得了（旧式会差 50px，靠吸附） ---
_o4, _y4 = fly(900, 300)
check('B10 大跨度上跳（-600）末前帧已在高位（误差 <= 8px）',
      abs(_y4[-2] - 300) <= 8, '末前帧 y=%d  目标=300' % _y4[-2])


# ============================================================ C. 鉴别力自证
mark('C 鉴别力自证：旧公式必须过不了 B 段判据')

OLD_TAIL = 50.0


def fly_old(start_y, target_y, frames=100):
    """**独立重算**旧公式的轨迹（不碰产品代码）。

    y(t) = y0 + vy0*t - 0.5*g*t² ，vy0 = (Δy + 0.5*g*T² + 50)/T
    末帧（progress>=1.0）同样做硬吸附 —— 与产品旧实现一致。
    """
    dy = float(target_y - start_y)
    vy0 = (dy + 0.5 * G * T * T + OLD_TAIL) / T
    ys = []
    for i in range(frames + 1):
        t = T * i / frames
        if i == frames:
            ys.append(target_y)                    # 末帧硬吸附
        else:
            ys.append(int(start_y + vy0 * t - 0.5 * G * t * t))
    return ys


_old_same = fly_old(500, 500)
check('C1 旧公式在同高跳上**过不了** B1（最高点就是第0帧 ⇒ 没有弧）',
      not (min(_old_same) < 500 and 0 < _old_same.index(min(_old_same)) < len(_old_same) - 1),
      '旧式 min=%d@frame%d' % (min(_old_same), _old_same.index(min(_old_same))))

_old_up = fly_old(500, 300)
check('C2 旧公式在向上跳上**过不了** B4（出现了「先往下沉」）',
      not (max(_old_up[:90]) <= 500), '旧式 max(前90帧)=%d' % max(_old_up[:90]))

check('C3 旧公式**过不了** B5（末前帧误差远大于 3px）',
      abs(_old_up[-2] - 300) > 3, '旧式末前帧=%d  目标=300' % _old_up[-2])

# C4 反向：新公式的实现（产品）在三处**都过得去** —— 已由 B1/B4/B5 断言；
#    这里只显式记账一次，避免"只有负控制没有正控制"。
check('C4 正控制：新公式在同样三个判据上全部成立',
      (min(_y1) < 500 and 0 < _y1.index(min(_y1)) < len(_y1) - 1)
      and max(_y2[:90]) <= 500 and abs(_y2[-2] - 300) <= 3)


# ============================================================ D. 同文件口径一致性
mark('D 同文件口径：handle_jump 与 handle_fall 的重力必须同号')

_fn_fall = None
for _n in ast.walk(TREE):
    if isinstance(_n, ast.FunctionDef) and _n.name == 'handle_fall':
        _fn_fall = _n
_fall_src = _norm(ast.unparse(_fn_fall)) if _fn_fall is not None else ''
check('D1 handle_fall 里竖直速度是 `+ _gy * elapsed_time`（重力朝屏幕下方 —— 基准口径）',
      '+ _gy * elapsed_time' in _fall_src, 'found=%s'
      % ('+ _gy * elapsed_time' in _fall_src))
check('D2 handle_jump 的 y 式同一约定（`+ 0.5 * g * elapsed * elapsed`）',
      (_y or '').endswith('+ 0.5 * g * elapsed * elapsed'), 'y=%r' % (_y,))
check('D3 两处**无第二份真相冲突**：全文件不再残留 `vy0 * elapsed - 0.5 * g`',
      'vy0 * elapsed - 0.5 * g' not in SRC)


# ============================================================ E. 判据自身体检
mark('E 判据自身体检')

check('E1 被测文件在盘', os.path.isfile(MAIN))
check('E2 判据点全部执行到位（标记打印点 == 5）', _marks == 5, 'marks=%d' % _marks)

# E3 漏记负控制：手工模拟一次"打了点却没调 check() 的判据"必须被抓
_probe_calls = _n_calls
_probe_marks = _marks


def _noop_probe():
    """模拟一条**打了标记点却没记账**的判据（no-op）。"""
    mark('E3 空判据探针')
    return None


_noop_probe()
check('E3 记账口不是 no-op（打了标记点但没走 check ⇒ 独立计数器不涨）',
      _n_calls == _probe_calls and _marks == _probe_marks + 1,
      'calls=%d(+0) marks=%d(+1)' % (_n_calls, _marks))

# E4 记账守恒：**独立计数器** == PASS + FAIL（★ 计数与判定分离，防"记了不判/判了不记"）
check('E4 记账守恒（独立计数器 CALLS == PASS + FAIL）',
      _n_calls == _n_pass + _n_fail,
      'calls=%d pass=%d fail=%d' % (_n_calls, _n_pass, _n_fail))

# E5 漏记负控制：上面未记账的那一步若被"算进总数"，守恒判据必须报红
check('E5 守恒判据有鉴别力（把漏记那一步计进总数 ⇒ 等式不再成立）',
      (_n_calls + 1) != (_n_pass + _n_fail),
      'calls+1=%d vs pass+fail=%d' % (_n_calls + 1, _n_pass + _n_fail))

print('=' * 70)
print('第90轮：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print('失败项：')
    for _d in _failed:
        print('  - %s' % _d)
print('=' * 70)
sys.exit(0 if not _failed else 1)

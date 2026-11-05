# -*- coding: utf-8 -*-
u"""第164轮回归锁：**运动类改造**（惊讶小跳 / 起跳闸门 / 助跑 / 分段）。

## 这一轮修的是两条病

用户口径（2026-11-05）：

> 「跳跃不能原地起跳后出现横向位移 —— 你需要给他一个**水平初速度**他才能跳远，
>   否则就是跳高，而且，**要有助跑距离哦**」
> 「窗口也是有**层高**的，所以**也不可能跳无限高**，和之前同理」
> 「有中途落脚那就**分段**，无那就**放弃或向用户求助**」
> 「这个**预留点**可别和**助跑距离**搞混了哦」

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | `modules/motion2d.py` 的纯数学：高度上限 / 飞行时间 / 可达性三态 / 助跑距离 / 欧拉积分与解析解一致 / 原地跳零横移 |
| B | 起跳闸门 `_jump_reach_ok`：太高拒、太远拒、正常放行；**助跑才解锁冲刺速度**，标了旗没跑起来一律不许放行 |
| C | 惊讶小跳真的跳起来了（旧实现只写参数、从不置 `is_jumping`），且**原地不横移**、`_hop_mode` 不参与楼层穿透 |
| D | 助跑状态机：规划（`v²/(2a)` / 反方向 / 垂直跳不助跑 / 试满上限就停）+ 看门狗（超时清状态） |
| E | 分段：候选层只夹在中间、朝目标方向、先近后远；递归闸；够不着逐个换候选后如实返回 False |
| F | 自检：产品文件无 BOM / 行尾未变 / 只用 `check()` / 不碰外部盘 |

## 为什么用**假 self** 而不是 `RalseiPet()`

`import main` 只要 **0.6 秒**，慢的是 `RalseiPet()` **构造**（约 31 秒，
第163轮实测更正了"import 要 31 秒"这个错记忆）。本套件把产品方法用
`types.MethodType` 绑到假对象上，**调的是产品那一个函数**，不是复制的逻辑，
所以既快又不会变成"判据在测自己"。

## 三条判据口径（都是踩过的坑）

1. **禁纯文本扫**：判"某个写法已消失"一律走 AST —— 第一版 `syntax164` 用纯文本
   扫 `'self.jump_height = 20' not in src`，被**我自己 docstring 里的举例**打红。
2. **禁魔法数字枚举**：不写 `convertToFormat(4)` 这类"看着对其实换了语义"的常量
   （第163轮用它造出过一条恒真判据）。
3. **判据条数不随环境变**：不遍历"有几个窗口 / 几个模块"再逐条断言。
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
# ★ 变异测试（`mutate164.py`）把 main.py 的**副本**喂进来，绝不改产品文件：
#   `CQ_SRC_DIR` 指向临时目录时，AST 与 import 都读那份副本。
_SRC_DIR = os.environ.get('CQ_SRC_DIR') or os.path.join(PET, 'src')
MAIN = os.path.join(_SRC_DIR, 'main.py')

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

_n_pass = 0
_n_fail = 0
_failed = []


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def read_bytes(path):
    with open(path, 'rb') as fh:
        return fh.read()


def read_src(path):
    """按字节读、保持原换行（条款 §11）。"""
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


# ============================================================ 导入
sys.path.insert(0, os.path.join(PET, 'modules'))
sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, PET)
if os.environ.get('CQ_SRC_DIR'):
    sys.path.insert(0, os.environ['CQ_SRC_DIR'])   # 变异副本优先，否则全成假绿

from PyQt5.QtWidgets import QApplication             # noqa: E402
from PyQt5.QtCore import QPoint                      # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv[:1])

try:
    import motion2d as M2
    _M2_ERR = ''
except Exception as _e:                              # noqa: BLE001
    M2 = None
    _M2_ERR = '%s: %s' % (type(_e).__name__, _e)

# ★ 不许让 import 崩掉整个套件：变异把文件改出语法错时，直接抛异常会让本套件
#   一行 `[FAIL]` 都打不出来 ⇒ 变异测试误判"全绿"（第163轮 M5 就这么漏过）。
try:
    import main as MAIN_MOD
    _IMPORT_ERR = ''
except Exception as _e:                              # noqa: BLE001
    MAIN_MOD = None
    _IMPORT_ERR = '%s: %s' % (type(_e).__name__, _e)
    print('  (import main 失败：%s)' % _IMPORT_ERR)

_PET_CLS = getattr(MAIN_MOD, 'RalseiPet', None) if MAIN_MOD is not None else None
_SRC = read_src(MAIN)
_TREE = None
try:
    _TREE = ast.parse(_SRC)
except Exception:                                    # noqa: BLE001
    pass


def _find_class(tree, name):
    if tree is None:
        return None
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == name:
            return n
    return None


def _find_func(cls, name):
    if cls is None:
        return None
    for n in cls.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


_CLS = _find_class(_TREE, 'RalseiPet')


class _FakePet(object):
    """假 self：只放产品方法真正读到的字段，方法本身用产品那一份。"""

    def __init__(self):
        self._px, self._py = 500, 500
        self.target_pos = QPoint(500, 500)
        self.is_moving = False
        self.is_jumping = False
        self.gravity = 500.0
        self.jump_duration = 1.0
        self.jump_height = 50
        self.jump_start_pos = QPoint(500, 500)
        self.jump_target_pos = QPoint(500, 500)
        self.jump_start_spatial = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.spatial_pos = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.jump_count = 0
        self.last_jump_time = 0.0
        self.needs_rest = False
        self.max_speed = 8.0
        self.speed = 5.0
        self.JUMP_SPEED_MAX = 700.0
        self._runup = None
        self._runup_dashing = False
        self._runup_ready = False
        self._runup_tried = 0
        self._last_move_speed_px_s = 0.0
        self._runup_best_px_s = 0.0
        self._segment_busy = False
        self._last_move_dt = 0.0
        self._jump_reject = None
        self.current_floor = None
        self.floor_manager = None
        self.spoken = 0

    def pos(self):
        return QPoint(self._px, self._py)

    def move(self, x, y):
        self._px, self._py = int(x), int(y)

    def start_autonomous_speech(self, *a, **k):
        self.spoken += 1


def _raw(name):
    """取产品类上的**未绑定**函数。拿不到返回 None（判据自己会说清楚）。"""
    if _PET_CLS is None:
        return None
    return getattr(_PET_CLS, name, None)


def _mt(pet, fn):
    """绑到指定实例。★ 绝不复用"绑到另一个实例"的 MethodType ——
    那样 `self` 会指向被丢弃的假对象，读到的全是它的字段（本次第一版就踩了）。"""
    return types.MethodType(fn, pet) if fn is not None else None


_NOMINAL = _raw('_nominal_move_dt')
_MAXRUN = _raw('_max_run_px_s')
_GATE = _raw('_jump_reach_ok')
_HOP = _raw('_start_surprised_hop')
_TRY_RUNUP = _raw('_try_runup')
_RUNUP_ARRIVE = _raw('_runup_on_arrive')
_RUNUP_TICK = _raw('_runup_tick')
_SEG_CANDS = _raw('_segment_candidates')


# ============================================================ A · motion2d
print('=' * 66)
print('A 段  motion2d：2.5D 跳跃的纯数学（零 Qt、可脱离产品单测）')
print('=' * 66)

check(u'A0 `modules/motion2d.py` 能导入（零依赖）',
      M2 is not None, '' if M2 is not None else _M2_ERR)

if M2 is None:
    check(u'A0b motion2d 不可用 —— 后面 A 段全部无法执行', False)
else:
    h = M2.max_jump_height(250.0, 500.0)
    check(u'A1 高度上限 = v²/(2g)：250²/(2×500) = 62.5',
          abs(h - 62.5) < 1e-9, '实得 %.3f' % h)
    check(u'A1b 起跳力越大上限越高（正控制，防判据恒真）',
          M2.max_jump_height(500.0, 500.0) > h,
          '500 ⇒ %.1f' % M2.max_jump_height(500.0, 500.0))
    check(u'A1c g<=0 时不除零、返回 0',
          M2.max_jump_height(250.0, 0.0) == 0.0)

    t0 = M2.flight_time(0.0, 250.0, 500.0)
    check(u'A2 平跳飞行时间 = 2v/g = 1.0s', abs(t0 - 1.0) < 1e-9, '实得 %.4f' % t0)
    check(u'A2b 目标更高 ⇒ 飞得更短（同一跳力）',
          M2.flight_time(30.0, 250.0, 500.0) < t0)
    check(u'A2c 目标比 h_max 还高 ⇒ 无解（返回 None）',
          M2.flight_time(100.0, 250.0, 500.0) is None,
          'h_max=62.5，取 dz=100')

    r_ok = M2.reachable(100.0, 0.0, 242.0)
    r_far = M2.reachable(400.0, 0.0, 242.0)
    r_hi = M2.reachable(100.0, 200.0, 242.0)
    check(u'A3 可达性三态：ok / too_far / too_high 各自互不相同（正控制）',
          r_ok['reason'] == 'ok' and r_far['reason'] == 'too_far'
          and r_hi['reason'] == 'too_high',
          '%s / %s / %s' % (r_ok['reason'], r_far['reason'], r_hi['reason']))
    check(u'A3b ok 分支真的给出 T 与 v_req',
          r_ok['ok'] and r_ok['T'] > 0 and abs(r_ok['v_req'] - 100.0) < 1e-6,
          'T=%.3f v_req=%.1f' % (r_ok['T'], r_ok['v_req']))
    check(u'A3c too_high 时 T 为 None（不是 0，别让调用方误算）',
          r_hi['T'] is None)

    d = M2.runup_distance(320.0, 0.0, 600.0)
    check(u'A4 助跑距离 = (v²-v0²)/(2a)：320²/(2×600) = 85.33',
          abs(d - 320.0 * 320.0 / 1200.0) < 1e-9, '实得 %.3f' % d)
    check(u'A4b 已经够快 ⇒ 不用退（返回 0）',
          M2.runup_distance(100.0, 200.0, 600.0) == 0.0)
    check(u'A4c 反解自证：跑完这段距离正好到目标速度',
          abs(M2.reachable_speed(0.0, d, 600.0, 9999.0) - 320.0) < 1e-6,
          '实得 %.3f' % M2.reachable_speed(0.0, d, 600.0, 9999.0))

    # 积分 vs 解析解：半隐式欧拉误差应随 dt 变小
    def _integrate(dt, total=0.2):
        x, y, z, vz = 0.0, 0.0, 0.0, 250.0
        n = int(round(total / dt))
        for _ in range(n):
            x, y, z, vz = M2.step(x, y, z, 0.0, 0.0, vz, 500.0, dt)
        return z

    z_fine = _integrate(0.001)
    z_coarse = _integrate(0.02)
    z_ana = 250.0 * 0.2 - 0.5 * 500.0 * 0.2 * 0.2
    check(u'A5 半隐式欧拉 dt=1ms 时与解析解误差 < 1px',
          abs(z_fine - z_ana) < 1.0, '积分 %.3f / 解析 %.3f' % (z_fine, z_ana))
    check(u'A5b 正控制：dt 放大到 20ms 误差必须更大（判据能分辨精度）',
          abs(z_coarse - z_ana) > abs(z_fine - z_ana),
          '20ms 误差 %.3f > 1ms 误差 %.3f'
          % (abs(z_coarse - z_ana), abs(z_fine - z_ana)))

    check(u'A6 屏幕投影 = (x, y - z)：z 越高画得越靠上',
          M2.screen_pos(100.0, 300.0, 40.0) == (100.0, 260.0))

    p_stand = M2.plan_jump(0.0, 0.0, 0.0, 242.0)
    p_side = M2.plan_jump(200.0, 0.0, 0.0, 242.0)
    check(u'A7 ★ 原地跳（无水平初速）横向分量必须为 0',
          p_stand['vx'] == 0.0 and p_stand['vy'] == 0.0,
          'vx=%.3f vy=%.3f' % (p_stand['vx'], p_stand['vy']))
    check(u'A7b 正控制：有横向目标时 vx 必须非 0',
          abs(p_side['vx'] - 200.0) < 1e-6, 'vx=%.3f' % p_side['vx'])

# ============================================================ B · 起跳闸门
print()
print('=' * 66)
print('B 段  起跳闸门：不可能跳无限高 / 太远必须先助跑')
print('=' * 66)


def _gate_case(pet, dx, dy, ready=False, meas=0.0, dur=1.0):
    pet.jump_duration = dur
    pet.jump_start_pos = QPoint(500, 500)
    pet.jump_target_pos = QPoint(500 + int(dx), 500 + int(dy))
    pet._runup_ready = ready
    pet._last_move_speed_px_s = meas
    pet._runup_best_px_s = 0.0
    r = pet._jump_reach_ok()
    rej = pet._jump_reject
    pet._runup_ready = False
    pet._last_move_speed_px_s = 0.0
    return r, rej


if _GATE is None:
    check(u'B0 起跳闸门方法存在（缺它就没有本轮的"不可能跳无限高"）', False)
else:
    p = _FakePet()
    p._nominal_move_dt = _mt(p, _NOMINAL)
    p._max_run_px_s = _mt(p, _MAXRUN)
    p._jump_reach_ok = _mt(p, _GATE)
    v_walk = p._max_run_px_s()
    check(u'B0 走路速度上限在合理量级（换算过，不是裸的 max_speed）',
          30.0 < v_walk < 900.0, '%.1f px/s（max_speed=%.1f 是 px/帧）'
          % (v_walk, p.max_speed))

    r, _ = _gate_case(p, 0, 0)
    check(u'B1 原地跳必须放行（否则连跳高都不行）', r is True)
    r, _ = _gate_case(p, 200, 0)
    check(u'B2 正常横跳 200px 必须放行', r is True)
    r, _ = _gate_case(p, 0, -80)
    check(u'B3 正常跳高 80px 必须放行', r is True)

    r_far, rej_far = _gate_case(p, int(v_walk) + 60, 0)
    check(u'B4 超出跳远极限必须拒绝', r_far is False)
    check(u'B4b 拒绝原因 = too_far（区分"该助跑"还是"该死心"）',
          rej_far is not None and rej_far[0] == 'too_far',
          '%r' % (rej_far,))
    r_hi, rej_hi = _gate_case(p, 0, -1000)
    check(u'B5 超出跳高极限必须拒绝', r_hi is False)
    check(u'B5b 拒绝原因 = too_high，且与 too_far **不同**（正控制）',
          rej_hi is not None and rej_hi[0] == 'too_high'
          and rej_far[0] != rej_hi[0], '%r' % (rej_hi,))

    # ★ 助跑分层：同一跳，助跑前拒、助跑后放
    dx_between = int(v_walk) + 30
    r_no, _ = _gate_case(p, dx_between, 0, ready=False, meas=0.0)
    r_yes, _ = _gate_case(p, dx_between, 0, ready=True, meas=320.0)
    check(u'B6 ★ 同一跳（dx=%d）不助跑必须拒、真冲到冲刺速度必须放'
          % dx_between, r_no is False and r_yes is True,
          '不助跑=%s / 助跑=%s' % (r_no, r_yes))

    v_off = p._max_run_px_s()
    p._runup_ready = False
    p._last_move_speed_px_s = 900.0
    v_ignored = p._max_run_px_s()
    check(u'B7 ★ 不助跑时实测值被**忽略**（900 进来也不许抬上限 → 防假放行）',
          abs(v_ignored - v_off) < 1e-6, '%.1f vs %.1f' % (v_ignored, v_off))

    p._runup_ready = True
    p._last_move_speed_px_s = 60.0
    p._runup_best_px_s = 0.0
    v_low = p._max_run_px_s()
    check(u'B8 ★ 标了助跑但只跑到 60 ⇒ 退回走路速度（不许假放行）',
          abs(v_low - v_off) < 1e-6, '%.1f vs %.1f' % (v_low, v_off))

    p._last_move_speed_px_s = 320.0
    v_hi = p._max_run_px_s()
    check(u'B9 助跑 + 实测 320 ⇒ 上限抬到冲刺速度',
          v_hi > v_off * 1.15, '%.1f > %.1f' % (v_hi, v_off))
    check(u'B9b 抬升有上限（不超过 RUNUP_SPEED_MAX 常量）',
          abs(v_hi - float(getattr(MAIN_MOD, 'RUNUP_SPEED_MAX', 320.0))) < 1e-6,
          '%.1f' % v_hi)
    p._runup_ready = False
    p._last_move_speed_px_s = 0.0

    # ★ 帧率放大回归闸：`speed` 是"像素/帧"，换算必须用**名义**帧长。
    #   实测踩过：某帧 dt≈2ms 时 `max_speed/0.002` 推出 4000px/s（第一版探针
    #   打的是 2777），闸门照它放行 = **假放行**。这里把 `_last_move_dt` 设成
    #   那个病态值，观察量必须是"冲刺速度本身"，不是"帧率的倒数"。
    p2 = _FakePet()
    p2._nominal_move_dt = _mt(p2, _NOMINAL)
    p2._max_run_px_s = _mt(p2, _MAXRUN)
    p2._last_move_dt = 0.002          # 病态短帧（不是名义 tick）
    p2._runup_ready = True
    p2._last_move_speed_px_s = 310.0  # 已按名义帧长换算好的实测速度
    v_spike = p2._max_run_px_s()
    check(u'B10 ★ 病态短帧不放大速度（实测 310 ⇒ 上限 ≈310，不是 4000+）',
          v_spike < 500.0, '实得 %.1f（未夹范围时是 4000.0）' % v_spike)
    check(u'B10b 正控制：同一输入、正常名义帧长 ⇒ 结果一致（没被夹歪）',
          abs(v_spike - 310.0) < 1e-6, '实得 %.1f' % v_spike)

# ============================================================ C · 惊讶小跳
print()
print('=' * 66)
print('C 段  惊讶小跳：真的跳起来、且原地不横移')
print('=' * 66)

_hop_fn = _find_func(_CLS, '_start_surprised_hop')
check(u'C1 `_start_surprised_hop` 是 RalseiPet 的成员（旧实现根本没有这函数）',
      _hop_fn is not None and _HOP is not None)


def _no_height_assign(fn):
    """AST：该函数里不许再出现 `xxx.jump_height = <常数>` 的赋值。

    ★ 必须走 AST：第一版 `syntax164` 用纯文本扫，被**我自己 docstring 里的举例**
      打红（"禁某短语出现"类判据禁纯文本扫，这是第 N 次复发）。
    """
    if fn is None:
        return None
    hits = 0
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if (isinstance(t, ast.Attribute) and t.attr == 'jump_height'
                        and isinstance(n.value, ast.Constant)
                        and isinstance(n.value.value, (int, float))):
                    hits += 1
    return hits


_ua = _find_func(_CLS, 'update_animation')
hits_ua = _no_height_assign(_ua)
check(u'C2 `update_animation` 里不再写死 `jump_height = 常数`（AST，不扫文本）',
      hits_ua == 0, '实得 %r 处' % (hits_ua,))
check(u'C2b 正控制：同一判据能识别**真的**赋值（否则 C2 是恒真）',
      _no_height_assign(ast.parse('def f(self):\n    self.jump_height = 20\n'
                                  ).body[0]) == 1)

if _HOP is not None:
    p3 = _FakePet()
    p3._start_surprised_hop = _mt(p3, _HOP)
    p3._start_surprised_hop()
    check(u'C3 调用后真的进入跳跃状态（旧实现只写参数、从不置 `is_jumping`）',
          p3.is_jumping is True)
    check(u'C3b ★ 原地：目标点 == 起点 ⇒ 横向初速为 0（"没水平初速只能跳高"）',
          p3.jump_target_pos.x() == p3.pos().x()
          and p3.jump_target_pos.y() == p3.pos().y(),
          '起点 (%d,%d) 目标 (%d,%d)' % (p3.pos().x(), p3.pos().y(),
                                         p3.jump_target_pos.x(),
                                         p3.jump_target_pos.y()))
    check(u'C3c `_hop_mode` 置上了（`handle_jump` 据此跳过楼层穿透）',
          getattr(p3, '_hop_mode', False) is True)
    n_before = p3.jump_count
    p3._start_surprised_hop()          # 正在跳 ⇒ 不该叠加
    check(u'C4 正在跳时再被吓 ⇒ 不打断、不叠加（幂等）',
          p3.jump_count == n_before, 'jump_count %d → %d'
          % (n_before, p3.jump_count))
    check(u'C4b 还原点已存（`jump_duration` 是全局参数，改完必须能还回去）',
          getattr(p3, '_surprised_saved_jump', None) is not None)

_hj = _find_func(_CLS, 'handle_jump')
_hop_break = 0
if _hj is not None:
    # ★ 锚点要认**字符串常量**：短路写的是 `getattr(self, '_hop_mode', False)`，
    #   `_hop_mode` 是 Constant('_hop_mode') 而不是 Name —— 第一版只收 Name
    #   就恒判 0 处（判据过窄 = 误报，反过来也会变成恒假）。
    # ★ 还要求它**套在 `for` 里**：这条短路的意义是"中断楼层穿透循环"，
    #   一个孤零零的 `if _hop_mode: break` 在语法上根本不成立、也守不住任何东西。
    for _n in ast.walk(_hj):
        if not isinstance(_n, ast.For):
            continue
        for _m in ast.walk(_n):
            if not isinstance(_m, ast.If):
                continue
            _toks = {x.id for x in ast.walk(_m.test) if isinstance(x, ast.Name)}
            _toks |= {x.value for x in ast.walk(_m.test)
                      if isinstance(x, ast.Constant) and isinstance(x.value, str)}
            if ('_hop_mode' in _toks and len(_m.body) == 1
                    and isinstance(_m.body[0], ast.Break)):
                _hop_break += 1
check(u'C5 `handle_jump` 里 `_hop_mode` 短路 + `break` 在位（AST 结构）',
      _hop_break == 1, '实得 %d 处' % _hop_break)


# ============================================================ D · 助跑
print()
print('=' * 66)
print('D 段  助跑：起跳点 vs 起跑点（两个量不许混）')
print('=' * 66)


class _FakeFm(object):
    def __init__(self):
        self.floors = []

    def floor_visible_contains(self, floor, pos):
        return True          # 起跑点校验：本段只想测"规划"，不想测可见区域


if _TRY_RUNUP is None:
    check(u'D0 助跑规划方法存在（缺它 = 本轮助跑根本没接线）', False)
else:
    p4 = _FakePet()
    p4._try_runup = _mt(p4, _TRY_RUNUP)
    p4.floor_manager = _FakeFm()
    p4.current_floor = {'type': 'desktop', 'platform_height': 0}
    v_walk4 = 242.0
    land = QPoint(800, 500)          # 落点在 +x 方向 300px

    ok_plan = p4._try_runup({'type': 'window'}, land, 'bottom', v_walk4 + 30)
    check(u'D1 太远（需要 272px/s > 走路 242）⇒ 排上助跑', ok_plan is True)
    ru = getattr(p4, '_runup', None) or {}
    frm, to = ru.get('from'), ru.get('to')
    check(u'D2 第一腿是 `back`（先退后，不是直接跳）',
          ru.get('leg') == 'back')
    check(u'D3 ★ 起跳点 == 宠物现在站的位置（预留空间归落点选择管，本函数不动它）',
          to is not None and to.x() == p4.pos().x() and to.y() == p4.pos().y(),
          'to=%s pos=%s' % (to, p4.pos()))
    check(u'D4 ★ 起跑点在起跳点的**反方向**（远离落点）',
          frm is not None and frm.x() < to.x(),
          'from.x=%s < to.x=%s' % (frm.x() if frm else None,
                                   to.x() if to else None))
    if frm is not None:
        L_got = ((frm.x() - to.x()) ** 2 + (frm.y() - to.y()) ** 2) ** 0.5
    else:
        L_got = -1.0
    L_want = M2.runup_distance(v_walk4 + 30, 0.0,
                               float(getattr(MAIN_MOD, 'RUNUP_ACCEL', 600.0)))
    L_min = float(getattr(MAIN_MOD, 'RUNUP_MIN_PX', 40))
    L_max = float(getattr(MAIN_MOD, 'RUNUP_MAX_PX', 320))
    L_want = max(L_min, min(L_max, L_want))
    check(u'D5 ★ 助跑距离 = v²/(2a)（由**速度差**决定，与目标几何无关）',
          abs(L_got - L_want) <= 1.5, '实得 %.1f / 解析 %.1f' % (L_got, L_want))
    check(u'D6 已经排上队：is_moving=True 且 target_pos 指向起跑点',
          p4.is_moving is True and frm is not None
          and p4.target_pos.x() == frm.x())

    p5 = _FakePet()
    p5._try_runup = _mt(p5, _TRY_RUNUP)
    p5.floor_manager = _FakeFm()
    p5.current_floor = {'type': 'desktop', 'platform_height': 0}
    p5._runup_tried = int(getattr(MAIN_MOD, 'RUNUP_MAX_TRIES', 1))
    check(u'D7 ★ 试满 RUNUP_MAX_TRIES 次后不再排（防死循环）',
          p5._try_runup({'type': 'window'}, QPoint(800, 500), 'bottom', 280.0)
          is False)

    p6 = _FakePet()
    p6._try_runup = _mt(p6, _TRY_RUNUP)
    p6.floor_manager = _FakeFm()
    p6.current_floor = {'type': 'desktop', 'platform_height': 0}
    check(u'D8 ★ 近乎垂直的跳不排助跑（助跑买不到横向速度，纯浪费）',
          p6._try_runup({'type': 'window'}, QPoint(500, 400), 'top', 280.0)
          is False)

    p7 = _FakePet()
    p7._try_runup = _mt(p7, _TRY_RUNUP)
    p7.floor_manager = _FakeFm()
    p7.current_floor = {'type': 'desktop', 'platform_height': 0}
    check(u'D9 需要速度超过 RUNUP_SPEED_MAX ⇒ 不排（跑断腿也到不了，交求助）',
          p7._try_runup({'type': 'window'}, QPoint(800, 500), 'bottom',
                        float(getattr(MAIN_MOD, 'RUNUP_SPEED_MAX', 320.0)) + 200.0)
          is False)

    if _RUNUP_TICK is not None:
        p8 = _FakePet()
        p8._runup_tick = _mt(p8, _RUNUP_TICK)
        p8._runup = {'from': QPoint(400, 500), 'to': QPoint(500, 500),
                     'args': (), 'leg': 'back', 't0': 0.0}   # 很久以前
        p8._runup_dashing = True
        p8._runup_tick()
        check(u'D10 ★ 超时 ⇒ 状态被清干净（否则这一层永远上不去，静默死锁）',
              p8._runup is None and p8._runup_dashing is False)

        p9 = _FakePet()
        p9._runup_tick = _mt(p9, _RUNUP_TICK)
        p9._runup = {'from': QPoint(400, 500), 'to': QPoint(500, 500),
                     'args': (), 'leg': 'back', 't0': 9e18}    # 未来 ⇒ 不算超时
        p9._runup_tick()
        check(u'D10b 负控制：没超时就不许清（否则一开跑就被掐）',
              p9._runup is not None)

    if _RUNUP_ARRIVE is not None:
        fired = []
        p10 = _FakePet()
        p10._runup_on_arrive = _mt(p10, _RUNUP_ARRIVE)
        p10._start_floor_jump = lambda *a, **k: (fired.append(1) or True)
        p10.move(500, 500)
        p10._runup = {'from': QPoint(500, 500), 'to': QPoint(529, 500),
                      'args': ({}, 'bottom', QPoint(800, 500)),
                      'leg': 'dash', 't0': 0.0}
        r = p10._runup_on_arrive()
        check(u'D11 ★ 差 29px（> RUNUP_FIRE_PX）不许起跳 —— 否则 dx 凭空 +29，'
              u'刚助跑换来的速度又被吃掉',
              r is True and len(fired) == 0 and p10._runup is not None,
              '起跳次数=%d' % len(fired))

        p10._runup = {'from': QPoint(500, 500), 'to': QPoint(504, 500),
                      'args': ({}, 'bottom', QPoint(800, 500)),
                      'leg': 'dash', 't0': 0.0}
        r = p10._runup_on_arrive()
        check(u'D12 进到 RUNUP_FIRE_PX 内 ⇒ 起跳一次且 `_runup` 已清',
              r is True and len(fired) == 1 and p10._runup is None,
              '起跳次数=%d' % len(fired))

# ============================================================ E · 分段
print()
print('=' * 66)
print('E 段  分段：够不着 ⇒ 先跳到中途落脚板（第十八轮"勿回退"按 2.5D 解重开）')
print('=' * 66)

_seg_cands = getattr(_PET_CLS, '_segment_candidates', None) if _PET_CLS else None
_try_seg = getattr(_PET_CLS, '_try_segment', None) if _PET_CLS else None
check(u'E1 `_segment_candidates` / `_try_segment` 都是 RalseiPet 的成员',
      _seg_cands is not None and _try_seg is not None)


class _FmWithFloors(object):
    def __init__(self, heights):
        self.floors = [{'type': 'desktop' if i == 0 else 'window',
                        'platform_height': h} for i, h in enumerate(heights)]


if _seg_cands is not None:
    def _cands(heights, cur_i, tgt_i):
        fm = _FmWithFloors(heights)
        return [f.get('platform_height')
                for f in _seg_cands(None, fm, fm.floors[cur_i], fm.floors[tgt_i])]

    # ★ 楼层**故意打乱**给（0,10,5,15）：排序若失效，"先近后远"就测不出来
    #   （按升序给的话 insertion order 恰好等于排序结果 ⇒ 删掉 sort 也全绿 = 假绿）。
    c_up = _cands([0, 10, 5, 15], 0, 3)
    check(u'E2 ★ 上楼只取**严格夹在中间**的层，且**先近后远**',
          c_up == [5, 10], '实得 %s' % (c_up,))
    # ⚠️ 这条实际是被"严格夹在中间"那个范围滤掉的（`lo < h < hi`），
    #   `_segment_candidates` 里那两条方向判断在这套几何下**不承重** ——
    #   照实写清楚，别让后来人以为它守的是方向判断。
    check(u'E2b ★ 上楼只往更高找（否则会在两层之间来回弹）',
          len(c_up) == 2 and min(c_up) > 0, '实得 %s' % (c_up,))
    c_dn = _cands([0, 10, 5, 15], 3, 0)
    check(u'E3 下楼镜像：15→0 得到 [10, 5]', c_dn == [10, 5], '实得 %s' % (c_dn,))
    check(u'E4 相邻两层之间没有候选（0→5）', _cands([0, 5, 10, 15], 0, 1) == [])
    check(u'E4b 只有两层时也没有候选（0→5）', _cands([0, 5], 0, 1) == [])

    p11 = _FakePet()
    p11._segment_busy = True
    p11.floor_manager = _FmWithFloors([0, 5, 10, 15])
    p11.current_floor = p11.floor_manager.floors[0]
    check(u'E5 ★ `_segment_busy=True` ⇒ 立刻 False（递归闸：'
          u'`_start_floor_jump` 失败会回调 `_on_jump_rejected` 再进本函数）',
          _try_seg(p11, p11.floor_manager.floors[3], QPoint(900, 100), 'bottom')
          is False)

if _try_seg is not None:
    p12 = _FakePet()
    p12._try_segment = types.MethodType(_try_seg, p12)
    p12._segment_candidates = _mt(p12, _SEG_CANDS)
    p12.floor_manager = _FmWithFloors([0, 5, 10, 15])
    p12.current_floor = p12.floor_manager.floors[0]
    p12._climb_landing = lambda fmx, fl: (QPoint(700, 300), 'right')
    calls = []
    p12._start_floor_jump = lambda f, e, l: (calls.append(f.get('platform_height'))
                                            or True)
    r = p12._try_segment(p12.floor_manager.floors[3], QPoint(900, 100), 'bottom')
    check(u'E6 ★ 够不着 15 层 ⇒ 真的改成跳 **5 层**', r is True and calls == [5],
          '跳跃目标=%s' % (calls,))

    calls2 = []
    p13 = _FakePet()
    p13._try_segment = types.MethodType(_try_seg, p13)
    p13._segment_candidates = _mt(p13, _SEG_CANDS)
    p13.floor_manager = _FmWithFloors([0, 5, 10, 15])
    p13.current_floor = p13.floor_manager.floors[0]
    p13._climb_landing = lambda fmx, fl: (QPoint(700, 300), 'right')
    p13._start_floor_jump = lambda f, e, l: (calls2.append(
        f.get('platform_height')) or False)
    r = p13._try_segment(p13.floor_manager.floors[3], QPoint(900, 100), 'bottom')
    check(u'E7 所有候选都够不着 ⇒ 逐个试完（5、10）后**如实**返回 False',
          r is False and calls2 == [5, 10], '试过=%s' % (calls2,))

    # 求助只喊一次：内层失败时不喊（`_segment_busy` 区分内外层）
    _reject = getattr(_PET_CLS, '_on_jump_rejected', None)
    if _reject is not None:
        p14 = _FakePet()
        p14._on_jump_rejected = types.MethodType(_reject, p14)
        p14._try_segment = types.MethodType(_try_seg, p14)
        p14._segment_candidates = _mt(p14, _SEG_CANDS)
        p14._try_runup = lambda *a, **k: False
        p14.floor_manager = _FmWithFloors([0, 5, 10, 15])
        p14.current_floor = p14.floor_manager.floors[0]
        p14._climb_landing = lambda fmx, fl: (QPoint(700, 300), 'right')
        # ★ 真实 `_start_floor_jump` 失败时**会回调** `_on_jump_rejected`；
        #   桩必须照抄这条链，否则 E8 测的就不是"内层不喊"，而是"根本没有内层"
        #   （假绿：桩不回调 ⇒ 只喊一次，看着通过，其实守的是空气）。
        p14._start_floor_jump = lambda f, e, l: (
            p14._on_jump_rejected(f, l, e) or False)
        p14._jump_reject = ('too_high', 900.0, 700.0)
        p14._runup = None
        p14.spoken = 0
        p14._on_jump_rejected(p14.floor_manager.floors[3],
                              QPoint(900, 100), 'bottom')
        inner_spoken = p14.spoken          # 内层跳失败时的喊话次数
        check(u'E8 ★ 内层（分段尝试中的某一跳）失败**不喊**，'
              u'求助由最外层统一喊一次',
              inner_spoken == 1, '实际喊了 %d 次（内层若也喊会是 3 次）'
              % inner_spoken)

# ============================================================ F · 自检
print()
print('=' * 66)
print('F 段  自检')
print('=' * 66)

_raw = read_bytes(MAIN)
check(u'F1 产品文件无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
_n_lf = _raw.count(b'\n')
_n_crlf = _raw.count(b'\r\n')
check(u'F1b 行尾仍是 CRLF（零裸 LF —— 编辑不许改 EOL）',
      _n_lf == _n_crlf, 'LF=%d CRLF=%d' % (_n_lf, _n_crlf))

_m2_path = os.path.join(PET, 'modules', 'motion2d.py')
_m2_raw = read_bytes(_m2_path)
check(u'F2 `motion2d.py` 零依赖（不 import 任何产品模块）',
      b'import main' not in _m2_raw and b'from modules' not in _m2_raw
      and b'PyQt' not in _m2_raw)

_self_src = read_src(os.path.abspath(__file__))
# ★ 自检必须**只看 F 段之前**的部分：F 段自己的判据里就写着被禁的字符串
#   （`'def ok('` / `'[PASS]'` / `'E:\\'`），扫全文会百分百自我打红 ——
#   这正是"禁某短语出现"类判据的老坑（本文件第一版就踩了，三条一起红）。
_F_MARK = "print('F 段  自检')"
_head = _self_src.split(_F_MARK)[0]
check(u'F3 本套件只用 `check()`（不混用第二套 harness，免得恒真判据漏网）',
      'def ok(' not in _head)
check(u'F4 不引用外部盘（D:/E:）',
      'E:\\\\' not in _head and 'D:\\\\' not in _head)

# F3b 走 AST 取**判据名本身**，不做全文扫：判据名里不许自带 `[PASS]` / `[FAIL]`
#   （那是 harness 加的；自带会把"判据名"和"结果"混成一件事）。
_desc_bad = 0
_n_check_calls = 0
try:
    _self_tree = ast.parse(_self_src)
    for _n in ast.walk(_self_tree):
        if not (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
                and _n.func.id == 'check' and _n.args):
            continue
        _n_check_calls += 1
        _a0 = _n.args[0]
        if isinstance(_a0, ast.Constant) and isinstance(_a0.value, str):
            if '[PASS]' in _a0.value or '[FAIL]' in _a0.value:
                _desc_bad += 1
except Exception as _e:                              # noqa: BLE001
    _desc_bad = -1
    print('  (自检 AST 解析失败：%s)' % _e)
check(u'F3b 判据名不带计数标记（那是 harness 加的，名字里不许自带）',
      _desc_bad == 0, '带标记 %r 处 / 共 %d 条判据'
      % (_desc_bad, _n_check_calls))
check(u'F3c 分母闸：本套件确实有判据（0 条也算"全绿"是假绿）',
      _n_check_calls >= 50, '%d 条' % _n_check_calls)

print()
print('=' * 66)
print('PASS=%d  FAIL=%d' % (_n_pass, _n_fail))
if _n_fail:
    print('失败项：')
    for _d in _failed:
        print('  - %s' % _d)
    sys.exit(1)
print('[PASS] 第164轮：运动类改造（小跳/闸门/助跑/分段）全部判据通过')

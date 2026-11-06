# -*- coding: utf-8 -*-
u"""第166轮 · 探针二：**"全速抛体"到底会把多少跳打掉**（改代码之前先量）。

## 背景

用户在有 D1（`vx = delta_x / jump_duration`）的三种改法里选了
「**全速抛体（真物理）**」：

    vx = 他真跑到的速度（全速），距离是结果不是输入。

这条在物理上最干净，但它有一个必然的连锁后果：**落点 = vx × T 是定值**，
而目标距离 `dx` 是任意的 ⇒ 两者几乎不可能正好相等。本探针就是为了把这个
"几乎"量化成具体数字，摆到用户面前再动 `main.py`。

## 本探针量化三种子模型（同一次跳跃、同一组参数）

| 代号 | 横向速度 | 起飞点 | 距离是谁 |
|---|---|---|---|
| **N 现状** | `min(v_cap, dx/T)` | 原地 | 距离是**输入**（D1 病根） |
| **F 原地全速** | `v_cap` 恒 | 原地 | 距离是**结果** |
| **B 全速＋调起飞点** | `v_cap` 恒 | 退到 `目标 − v_cap·T` | 距离是结果，**起跳时机**是输入 |
| **C 跑道定速** | `min(v_cap, √(2a·L))` | 原地 | 距离是结果，**可用助跑道**是约束 |

`B` 是真实平台跳跃的玩法（玩家全速跑、**在正确时机起跳**）；
`C` 是"跑道不够就只能慢跑"的写法（近距跳不必全速）。

## 纪律

* 全部速度上限由**产品函数**算（`_max_run_px_s`），不抄公式；
* `T` 也取产品值（`jump_duration` 默认 1.0；只有"惊讶小跳"是 0.5）；
* 纯数学部分用 `modules/motion2d.py`（第164轮已落地的真抛体纯函数）；
* 本脚本**不构造 `RalseiPet()`**（31s 那个）、**不联网、不改任何文件**。
"""
import io
import json
import os
import sys
import types

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
CFG = os.path.join(PET, 'config.json')

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
for _p in (PET, os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PyQt5.QtCore import QPoint  # noqa: E402

import main as M            # noqa: E402
import motion2d as M2       # noqa: E402


def _hr(t):
    print('')
    print('=' * 74)
    print(t)
    print('=' * 74)


def _cfg():
    with io.open(CFG, 'r', encoding='utf-8') as fh:
        d = json.load(fh)
    mv = d.get('movement') or {}
    return (float(mv.get('speed', 5.0)),
            float(mv.get('min_speed', 3.0)),
            float(mv.get('max_speed', 8.0)))


class _Pet(object):
    u"""假 self：只放 `_max_run_px_s` / `_jump_reach_ok` 真正读的字段。"""

    def __init__(self, max_speed, speed):
        self.max_speed = float(max_speed)
        self.speed = float(speed)
        self._last_move_dt = 0.0
        self._runup_ready = False
        self._last_move_speed_px_s = 0.0
        self._runup_best_px_s = 0.0
        self.JUMP_SPEED_MAX = float(getattr(M.RalseiPet, 'JUMP_SPEED_MAX', 700.0))
        self.jump_duration = 1.0
        self.gravity = 500.0
        self._jump_reject = None
        self.jump_start_pos = None
        self.jump_target_pos = None
        self._motion_exp = 0.0
        self._motion_eff_cache = None
        self._motion_profile_cache = None
        self._motion_progress_loaded = True
        self._motion_exp_map = {}
        self._motion_progress_path = None


def _bind(max_speed, speed, ready=False, best=0.0, measured=0.0):
    p = _Pet(max_speed, speed)
    for name in ('_max_run_px_s', '_jump_reach_ok', '_nominal_move_dt',
                 '_motion_eff', '_motion_profile_of', '_motion_profile_table'):
        fn = getattr(M.RalseiPet, name, None)
        if fn is not None:
            setattr(p, name, types.MethodType(fn, p))
    p._runup_ready = bool(ready)
    p._runup_best_px_s = float(best)
    p._last_move_speed_px_s = float(measured)
    return p


def _gate(p, dx, dy=-300):
    u"""产品闸门自己说这一跳能不能过。→ (放行?, 拒绝原因)"""
    p.jump_start_pos = QPoint(500, 900)
    p.jump_target_pos = QPoint(int(500 + dx), 900 + dy)
    ok = p._jump_reach_ok()
    rj = p._jump_reject
    return bool(ok), (rj[0] if rj else '')


SPEED, MIN_SPEED, MAX_SPEED = _cfg()

# ---------------------------------------------------------------- A 参数
_hr(u'A 参数真值（全部从产品/config 读，不硬编码）')
_p0 = _bind(MAX_SPEED, SPEED)
DT = _p0._nominal_move_dt()
V_WALK = _bind(SPEED, SPEED, ready=False)._max_run_px_s()
V_MIN = MIN_SPEED / DT        # 他能跑出的最慢速度（min_speed）
V_CAP_OLD = _bind(MAX_SPEED, SPEED, ready=False)._max_run_px_s()
V_CAP_NEW = V_WALK
V_FULL = _bind(SPEED, SPEED, ready=True, best=9999.0)._max_run_px_s()
T = 1.0        # 产品 `self.jump_duration` 默认值（main.py:8402）；惊讶小跳例外 0.5
G = 500.0
ACCEL = float(getattr(M, 'RUNUP_ACCEL', 600.0))
H_MAX = M2.max_jump_height(M2.JUMP_SPEED, G)

print(u'  movement: speed=%.2f  min=%.2f  max=%.2f  （px/帧）'
      % (SPEED, MIN_SPEED, MAX_SPEED))
print(u'  名义帧长 dt=%.4fs' % DT)
print(u'  走路速      = %.1f px/s' % V_WALK)
print(u'  配置上限速  = %.1f px/s   （165 旧口径给门票用的就是这个）' % V_CAP_OLD)
print(u'  助跑满速    = %.1f px/s   （RUNUP_SPEED_MAX × run 倍率）' % V_FULL)
print(u'  飞行时长 T  = %.2fs（`jump_duration` 默认值；惊讶小跳例外为 0.5）' % T)
print(u'  重力 g=%.0f  起跳初速 vz0=%.0f  ⇒ 高度硬上限 h_max=%.1f px'
      % (G, M2.JUMP_SPEED, H_MAX))
print(u'  助跑加速度 a=%.0f  ⇒ 从 0 加速到 %0.0f 需 %.1f px 跑道'
      % (ACCEL, V_FULL, M2.runup_distance(V_FULL, 0.0, ACCEL)))

# ---------------------------------------------------------------- B 位移表
_hr(u'B 三种速度下"一跳能横移多远"（D = v × T，T=1.0s）')
for label, v in ((u'走路速     ', V_WALK), (u'配置上限速 ', V_CAP_OLD),
                 (u'助跑满速   ', V_FULL)):
    print(u'  %s v=%6.1f px/s  ⇒  D = %6.1f px' % (label, v, v * T))
print(u'  ★ 注意：D 一旦锁定，落点就定了 —— 与目标在哪无关。')

# ---------------------------------------------------------------- C 命中率
_hr(u'C 命中率：`|dx − D| ≤ 8px` 才算"踩在目标上"（dx 取样 40~480，步长 10）')
_DXS = list(range(40, 481, 10))


def _hit_count(d_fixed):
    return sum(1 for dx in _DXS if abs(dx - d_fixed) <= 8)


print(u'  F 原地全速（D 恒 = %.0f）：命中 %d / %d 个取样  ⇒ %.1f%%'
      % (V_FULL * T, _hit_count(V_FULL * T), len(_DXS),
         100.0 * _hit_count(V_FULL * T) / len(_DXS)))
print(u'  F 原地全速（走路速 D = %.0f）：命中 %d / %d  ⇒ %.1f%%'
      % (V_WALK * T, _hit_count(V_WALK * T), len(_DXS),
         100.0 * _hit_count(V_WALK * T) / len(_DXS)))
_n_now = sum(1 for dx in _DXS if dx <= V_CAP_NEW * T + 1e-9)
print(u'  N 现状：闸门放行区间内**恒命中**（它按 dx 反推 vx，必然踩中）；')
print(u'          取样中落入放行区间的有 %d / %d 个（未助跑口径 v_cap=%.0f ⇒ ≤%.0f px）'
      % (_n_now, len(_DXS), V_CAP_NEW, V_CAP_NEW * T))
print(u'  ★ 也就是：现状不是"命中率高"，而是"先按速度卡掉够不着的，剩下的保证踩中"。')
print(u'    代价 = `vx = dx/T` 把目标距离当成了输入 —— 这正是 D1。')

# ---------------------------------------------------------------- D 明细表
_hr(u'D 逐 dx 明细：落点差 / 需退多少 / 需多长跑道')
print(u'  · 落点差 = D − dx（正=冲过头，负=够不着）')
print(u'  · 需退   = "全速＋调起飞点"要把起跳点摆到 目标−D，得先往回走多远')
print(u'  · 需跑道 = 从 0 加速到 v_cap 的物理距离 v_cap²/(2a)（固定）')
_RUN_FULL = M2.runup_distance(V_FULL, 0.0, ACCEL)
print(u'')
print(u'  %5s | %8s | %8s | %8s | %8s | %s'
      % ('dx', 'D(全速)', '落点差', '需退', '总需空间', 'B 子模型可行?'))
for dx in (60, 100, 120, 160, 200, 240, 280, 320, 360, 400, 480):
    d = V_FULL * T
    err = d - dx
    back = max(0.0, err)
    space = back + _RUN_FULL
    verdict = u'可行' if dx <= d else u'够不着（只能分段）'
    print(u'  %5d | %8.1f | %+8.1f | %8.1f | %8.1f | %s'
          % (dx, d, err, back, space, verdict))

# ---------------------------------------------------------------- E 跑道表
_hr(u'E 子模型 C（跑道定速）：每个 dx 最少要留多长跑道')
print(u'  v_need = dx/T；跑道 L_min = v_need²/(2a)；v 上限 = v_cap = %.0f' % V_FULL)
print(u'')
print(u'  %5s | %9s | %10s | %s' % ('dx', 'v_need', 'L_min(px)', '备注'))
for dx in (40, 80, 120, 160, 200, 240, 280, 320, 360, 400):
    v_need = float(dx) / T
    l_min = M2.runup_distance(min(v_need, V_FULL), 0.0, ACCEL)
    note = u'超上限（v_need>%.0f）⇒ 够不着' % V_FULL if v_need > V_FULL + 1e-9 else u''
    print(u'  %5d | %9.1f | %10.1f | %s' % (dx, v_need, l_min, note))

# ---------------------------------------------------------------- F 空间
_hr(u'F 子模型 B＋选速：每个 dx 最少要多大的可站空间')
print(u'  规则：选一个 he 跑得出来的速度 v（∈[走路速, 助跑满速]），')
print(u'        先退到 目标 − v·T，再从静止加速 v/a 距离冲到该点起跳。')
print(u'        所需空间 = (v·T − dx) + v²/(2a)')
print('')
print(u'  %5s | %8s | %10s | %12s | %s'
      % ('dx', '选中的 v', '需退(v·T−dx)', '需跑道 v²/2a', '合计空间'))
for dx in (40, 60, 80, 100, 120, 160, 200, 240, 280, 320, 360, 400):
    if float(dx) / T > V_FULL + 1e-9:
        print(u'  %5d | %8s | %10s | %12s | %s'
              % (dx, '—', '—', '—', u'超满速上限 ⇒ 只能分段跳'))
        continue
    v_need = max(float(dx) / T, V_MIN)           # 他跑不出比 min_speed 更慢的速度
    if v_need > V_FULL:
        best_v, best_sp = V_FULL, None
    else:
        best_v, best_sp = v_need, None
    # 在 [v_need, V_FULL] 里找"空间最小"的速度（快一点退得少、但跑道更长）
    cands = []
    vv = v_need
    while vv <= V_FULL + 1e-9:
        cands.append(vv)
        vv += 10.0
    cands.append(V_FULL)
    best = None
    for v in sorted(set(cands)):
        if v * T + 1e-9 < dx:
            continue
        sp = (v * T - dx) + M2.runup_distance(v, 0.0, ACCEL)
        if best is None or sp < best[1] - 1e-9:
            best = (v, sp)
    if best is None:
        print(u'  %5d | %8s | %10s | %12s | %s' % (dx, '—', '—', '—', u'无可行速度'))
        continue
    v, sp = best
    print(u'  %5d | %8.1f | %10.1f | %12.1f | %.1f px'
          % (dx, v, v * T - dx, M2.runup_distance(v, 0.0, ACCEL), sp))
print(u'  ★ 对比 D 段：原地全速要 345px 才能跳 60px；选速后只需上表的数。')

# ---------------------------------------------------------------- G 高度
_hr(u'G 高度上限：h_max=%.1f px 对"窗口 32px/层"意味着什么' % H_MAX)
_layers = int(H_MAX // 32)
print(u'  h_max = vz0²/(2g) = %.0f²/(2×%.0f) = %.1f px' % (M2.JUMP_SPEED, G, H_MAX))
print(u'  按 32px/层 ⇒ 理论上限 %d 层（余 %.1f px 不够再上一层）'
      % (_layers, H_MAX - _layers * 32))
print(u'  ★ 这是"物理高度上限"，与横向改动无关，但改"全速抛体"时会被一起问到：')
print(u'    分段跳（第164轮 `_try_segment`）本来就是为它准备的。')

# ---------------------------------------------------------------- G 闸门口径
_hr(u'H 闸门（`_jump_reach_ok`）三种口径放行的 dx 区间')
for label, kw in ((u'未助跑', dict(ready=False)),
                  (u'助跑满 ', dict(ready=True, best=9999.0))):
    _p_old = _bind(MAX_SPEED, SPEED, **kw)
    _p_new = _bind(SPEED, SPEED, **kw)
    _ok_new = [dx for dx in _DXS if _gate(_bind(SPEED, SPEED, **kw), dx)[0]]
    _ok_old = [dx for dx in _DXS if _gate(_bind(MAX_SPEED, SPEED, **kw), dx)[0]]
    print(u'  %s：old 放行 ≤%s px ／ new 放行 ≤%s px'
          % (label,
             ('%d' % max(_ok_old)) if _ok_old else u'无',
             ('%d' % max(_ok_new)) if _ok_new else u'无'))
    del _p_old, _p_new

_hr(u'I 结论（自动算）')
print(u'  ① 现状 N：vx 由 dx 反推 ⇒ 距离是输入，全部命中 ——— 这是 D1 病根本身。')
print(u'  ② 原地全速 F：D 恒 = %.0f px ⇒ 只有 dx≈%.0f 附近才踩得中'
      u'（%.1f%% 命中）⇒ 其余全部落空。' % (V_FULL * T, V_FULL * T,
                                          100.0 * _hit_count(V_FULL * T) / len(_DXS)))
print(u'  ③ 全速＋调起飞点 B：dx ≤ %.0f 全部可命中，代价是"先往回退 D−dx"：'
      u'近距跳退得最多。' % (V_FULL * T))
print(u'     dx=100 时要退 %.0f px、总需 %.0f px 的可站空间；'
      u'dx=320 时不用退、但需 %.0f px 跑道。'
      % (V_FULL * T - 100, V_FULL * T - 100 + _RUN_FULL, _RUN_FULL))
print(u'  ④ 跑道定速 C：跑道不足时按 L 给速（近距低速度），需要的是 L_min 表（E 段）。')
print('')
print(u'（本探针只打印数据，不改任何文件、不联网、不构造 RalseiPet）')

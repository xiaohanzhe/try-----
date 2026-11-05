# -*- coding: utf-8 -*-
"""motion2d —— 2.5D 平台跳跃的纯数学（零依赖，可脱离产品单测）。

为什么单独一个模块
------------------
`main.py` 里的跳跃是"定点插值"：`vx = delta_x / jump_duration`，横向位移由
**目标位置**决定，与起跳速度无关；竖直方向用一条抛物线插值屏幕 Y；而
`spatial_pos["z"]` 又用 `sin(pi*progress)` 另算一套高度。三套东西互不相干，
于是出现三种病：

  · 原地起跳只要目标有横向差就会横移（违反"要有初速度才跳得远"）；
  · 空中匀速平移（违反"速度锁死"）；
  · 高度没有上限概念，层高只能靠人工卡常数（`CLIMB_SPAN_JUMP_MAX` 这类）。

本模块把**真抛体**写死成一组纯函数，让上层只负责"给参数、拿结果"。

坐标约定（全模块统一，别混）
----------------------------
· **平面坐标** `(x, y)`：屏幕坐标，**X 向右、Y 向下**（Qt 一致）。
· **高度** `z`：**向上为正**，单位 px。地面/平台面上 `z = 0`。
· 屏幕绘制位置 = `(x, y - z)` —— 高度靠"精灵往上挪"表达，这正是 2.5D 的投影。
· `dz > 0` 表示**目标比起点高**；`dz < 0` 表示往下跳。
· `vz > 0` 表示初速朝**上**。

物理模型
--------
竖直：`z(t) = vz0*t - 0.5*g*t^2`，`vz0 = JUMP_SPEED`（起跳力固定）。
        ⇒ 最高点 `h_max = vz0^2 / (2g)`
        ⇒ 落回 `dz` 的时刻解 `0.5*g*T^2 - vz0*T + dz = 0`
水平：`vx, vy` **起跳即锁定**（空中不许改向），位移 = `v*T`。

两条重要推论（用户口径的数学形式）
----------------------------------
1. `v = 0 ⇒ 位移 = 0` —— **原地起跳绝不横移**，跳远必须先有水平初速度。
2. `dz > h_max ⇒ 判别式 < 0 ⇒ 无解` —— **高度有硬上限**，跳不上更高的平台。
   想上去只能：找中途落脚点（分段）／放弃／求助。
"""

import math

# ---- 与产品一致的缺省物理量（`main.py` 实测：gravity=500，峰值 62.5）----
GRAVITY = 500.0          # px/s^2，屏幕竖直向下
JUMP_SPEED = 250.0       # px/s，起跳竖直初速（向上）
                         # 由 g=500 与 T=1.0 反推：vz0 = 0.5*g*T = 250
                         # ⇒ h_max = 250^2/(2*500) = 62.5（实测峰值 63，吻合）
RUN_ACCEL = 600.0        # px/s^2，助跑加速度（用户默认值）
RUN_MAX = 320.0          # px/s，最大冲刺速度（用户默认值）
RUNUP_MAX_TRIES = 2      # 助跑尝试上限，超过就放弃并"说一句求助"

_EPS = 1e-9


# ----------------------------------------------------------------------
# 一、竖直：能从多高、要飞多久
# ----------------------------------------------------------------------
def max_jump_height(jump_speed=JUMP_SPEED, gravity=GRAVITY):
    """起跳力决定的高度硬上限：`v^2 / (2g)`，单位 px。

    这是"窗口有层高，不可能跳无限高"的数学表达 —— 不是人为卡的常数。
    """
    if gravity <= 0:
        return 0.0
    return (jump_speed * jump_speed) / (2.0 * gravity)


def flight_time(dz, jump_speed=JUMP_SPEED, gravity=GRAVITY):
    """落到高度差 `dz` 处所需时间（秒）。够不着返回 `None`。

    `dz > 0` = 目标更高；`dz < 0` = 往下跳（时间更长）。
    上升段与下落段各有一个根，**取大根** —— 那才是"落地"时刻，
    小根是"上升途中路过这个高度"，不是落点。
    """
    if gravity <= 0 or jump_speed <= 0:
        return None
    disc = jump_speed * jump_speed - 2.0 * gravity * dz
    if disc < -_EPS:
        return None                       # 判别式 < 0 ⇒ 永远到不了这个高度
    if disc < 0.0:
        disc = 0.0
    t = (jump_speed + math.sqrt(disc)) / gravity
    return t if t > 0 else None


def peak_time(jump_speed=JUMP_SPEED, gravity=GRAVITY):
    """到最高点的时间 `vz0 / g`（抛物线对称，落地时间的一半）。"""
    if gravity <= 0:
        return 0.0
    return jump_speed / gravity


# ----------------------------------------------------------------------
# 二、水平：跳这么远需要多快
# ----------------------------------------------------------------------
def required_horizontal_speed(distance, t):
    """飞 `t` 秒要覆盖 `distance` 的水平距离，所需速度（标量）。"""
    if t is None or t <= _EPS:
        return None
    return abs(distance) / t


def reachable(distance, dz, v_max, jump_speed=JUMP_SPEED, gravity=GRAVITY):
    """能不能一跳到位？返回诊断字典（不用异常，调用方好分支）。

    `distance`：平面距离（标量，px）。
    `dz`：目标相对起点的高度差，**向上为正**。
    `v_max`：起跳时**已锁定**的水平速度上限（= 当前冲刺速度）。

    返回：
      ok        —— 能否一跳到达
      T         —— 飞行时长（秒）；够不着高度时为 None
      v_req     —— 所需水平初速；为 0 表示"原地跳高"
      h_max     —— 高度上限（供日志/判据）
      reason    —— 'ok' / 'too_high' / 'too_far'
    """
    h_max = max_jump_height(jump_speed, gravity)
    t = flight_time(dz, jump_speed, gravity)
    if t is None:
        return {'ok': False, 'T': None, 'v_req': None,
                'h_max': h_max, 'reason': 'too_high'}
    v_req = required_horizontal_speed(distance, t)
    if v_req > v_max + _EPS:
        return {'ok': False, 'T': t, 'v_req': v_req,
                'h_max': h_max, 'reason': 'too_far'}
    return {'ok': True, 'T': t, 'v_req': v_req,
            'h_max': h_max, 'reason': 'ok'}


def horizontal_drift(v, t):
    """初速 `v` 锁定后，飞 `t` 秒的位移大小。`v=0 ⇒ 0`（原地跳的判据）。"""
    if t is None or t <= 0:
        return 0.0
    return v * t


# ----------------------------------------------------------------------
# 三、助跑：还差多少速度、要退多远
# ----------------------------------------------------------------------
def runup_distance(v_target, v_now=0.0, accel=RUN_ACCEL):
    """从 `v_now` 加速到 `v_target` 所需的距离：`(v^2 - v0^2) / (2a)`。

    这正是"助跑距离"的物理量 —— 速度不够就先退这么远，再冲过来。
    已经够快时返回 0（不用退）。
    """
    if accel <= 0:
        return 0.0
    v_target = max(0.0, v_target)
    v_now = max(0.0, v_now)
    if v_now >= v_target - _EPS:
        return 0.0
    return (v_target * v_target - v_now * v_now) / (2.0 * accel)


def reachable_speed(v_now, distance_to_run, accel=RUN_ACCEL, v_max=RUN_MAX):
    """在给定助跑距离内，最多能加速到多少（不超过 `v_max`）。"""
    if distance_to_run <= 0 or accel <= 0:
        return min(v_now, v_max)
    v2 = v_now * v_now + 2.0 * accel * distance_to_run
    return min(math.sqrt(max(0.0, v2)), v_max)


# ----------------------------------------------------------------------
# 四、积分一步（供逐帧推进用；与解析解等价，用来验算）
# ----------------------------------------------------------------------
def step(x, y, z, vx, vy, vz, gravity=GRAVITY, dt=0.0):
    """推进 `dt` 秒。返回 `(x, y, z, vz)`。

    竖直用**半隐式欧拉**（先更新速度再更新位置），比显式欧拉更贴近解析解，
    且长时间积分不发散。`vz` 向上为正，重力让它逐帧减小。
    """
    if dt <= 0:
        return x, y, z, vz
    vz = vz - gravity * dt
    x = x + vx * dt
    y = y + vy * dt
    z = z + vz * dt
    return x, y, z, vz


def screen_pos(x, y, z):
    """平面坐标 + 高度 ⇒ 屏幕绘制坐标（高度靠"往上挪"表达）。"""
    return x, y - z


# ----------------------------------------------------------------------
# 五、一次性规划：把上面几步串起来（上层只调这一个）
# ----------------------------------------------------------------------
def plan_jump(dx, dy, dz, v_max, jump_speed=JUMP_SPEED, gravity=GRAVITY):
    """规划一次跳跃。返回字典，包含能否到达、时长、所需速度与可直接用的速度分量。

    `dx, dy`：**平面**位移（屏幕坐标，Y 向下）。
    `dz`：高度差（向上为正）。
    `v_max`：可用的水平速度上限（= 助跑后的冲刺速度）。

    ★ 关键：返回的 `vx, vy` 是**初速度**，一旦起飞就锁定。
      调用方在飞行中只能按 `x += vx*dt` 推进，**不许**再按目标位置插值。
    """
    dist = math.hypot(dx, dy)
    diag = reachable(dist, dz, v_max, jump_speed, gravity)
    out = dict(diag)
    out['dist'] = dist
    out['dz'] = dz
    t = diag['T']
    if diag['ok'] and t and t > _EPS:
        # 把标量速度拆回方向（原地跳时 dist=0 ⇒ 两个分量都为 0）
        scale = (1.0 / t)
        out['vx'] = dx * scale
        out['vy'] = dy * scale
    else:
        out['vx'] = 0.0
        out['vy'] = 0.0
    out['vz0'] = jump_speed
    return out

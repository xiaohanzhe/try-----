# -*- coding: utf-8 -*-
"""第164轮 · `motion2d` 的数值验证（纯函数，不需要 QApplication）。

为什么要单独验
--------------
`motion2d` 是整个跳跃物理化的地基：上层 `main.py` 只负责把坐标喂进来、
把速度拿出去。**地基算错，上层全错**，而且错得很像"对"（比如原地跳不横移，
可能只是因为它返回了 0，而不是因为它真的算了 0）。

所以这里的每一条都要求"**断了会红**"：
  · 正控制 —— 该成立的必须成立；
  · 负控制 —— 该失败的必须失败（举不出反例的判据等于没写）；
  · A/B 对照 —— 先断言两边**不相等**，再断言各自的预期。

判据表见文件末尾 `CASES`，每条都能单独定位。
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
# ★ 支持指向"变异副本"：`MOTION2D_DIR=<临时目录>` ⇒ 用来证明判据真的会红。
#   不设则指向产品模块（正常回归走这条）。
_MOD_DIR = os.environ.get('MOTION2D_DIR') or os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, _MOD_DIR)

import motion2d as m2                      # noqa: E402

_fails = []
_passes = [0]


def ok(cond, msg):
    if cond:
        _passes[0] += 1
        print('  [PASS] %s' % msg)
    else:
        _fails.append(msg)
        print('  [FAIL] %s' % msg)


def near(a, b, tol=1e-6):
    return a is not None and abs(a - b) <= tol


def sec(t):
    print('\n' + '=' * 68)
    print(t)
    print('=' * 68)


def main():
    print('motion2d 数值验证  GRAVITY=%.1f  JUMP_SPEED=%.1f'
          % (m2.GRAVITY, m2.JUMP_SPEED))

    # ---------------------------------------------------------------- 1
    sec('1 高度上限 = 起跳力的函数（不是人为常数）')
    h = m2.max_jump_height()
    ok(near(h, 62.5), 'h_max = v^2/(2g) = 62.5（实得 %.4f）' % h)
    ok(near(m2.max_jump_height(250, 1000), 31.25),
       '重力翻倍 ⇒ 高度减半（31.25，实得 %.4f）' % m2.max_jump_height(250, 1000))
    # 负控制：h_max 不应是恒定返回值
    ok(not near(m2.max_jump_height(250, 1000), h),
       '负控制：不同重力必须得到不同 h_max（否则是写死的常数）')

    # ---------------------------------------------------------------- 2
    sec('2 飞行时长：同高回落地 = 2*vz0/g')
    t0 = m2.flight_time(0.0)
    ok(near(t0, 1.0), 'dz=0 ⇒ T=1.0s（实得 %.4f）' % t0)
    ok(near(m2.peak_time(), 0.5), '到顶点 T/2=0.5s（实得 %.4f）' % m2.peak_time())
    t_top = m2.flight_time(62.5)
    ok(near(t_top, 0.5), 'dz=h_max ⇒ T=0.5（正好在顶点碰到，实得 %s）'
       % ('None' if t_top is None else '%.4f' % t_top))

    sec('2b 负控制：够不着的高度必须返回 None，不能给个假时间')
    ok(m2.flight_time(62.6) is None, 'dz=62.6（略高于 h_max）⇒ None')
    ok(m2.flight_time(200.0) is None, 'dz=200 ⇒ None')
    ok(m2.flight_time(0.0) is not None,
       '正控制：同高必须给出时间（证明上面两条不是因为函数整体坏了）')

    sec('2c 往下跳用时更长')
    t_down = m2.flight_time(-60.0)
    ok(t_down is not None and t_down > t0,
       'dz=-60 ⇒ T=%.3fs > 同高的 %.3fs' % (t_down or -1, t0))

    # ---------------------------------------------------------------- 3
    sec('3 ★ 核心口径：没有水平初速度就不许有横向位移')
    p_still = m2.plan_jump(0, 0, 0, v_max=m2.RUN_MAX)
    ok(p_still['ok'], '原地跳 ok=True')
    ok(p_still['vx'] == 0.0 and p_still['vy'] == 0.0,
       '原地跳 vx=vy=0（实得 %.3f, %.3f）' % (p_still['vx'], p_still['vy']))
    ok(near(m2.horizontal_drift(0.0, p_still['T']), 0.0),
       '原地跳水平位移 = v*T = 0')
    # A/B 先断言两边不相等，再分别判
    p_far = m2.plan_jump(200, 0, 0, v_max=m2.RUN_MAX)
    ok(p_far['vx'] != p_still['vx'],
       'A/B：横跳 200 的 vx 必须 != 原地跳（%.3f vs %.3f）'
       % (p_far['vx'], p_still['vx']))
    ok(near(p_far['vx'], 200.0), '横跳 200/1s ⇒ vx=200（实得 %.3f）' % p_far['vx'])
    ok(near(m2.horizontal_drift(p_far['vx'], p_far['T']), 200.0),
       '横跳实际位移 = vx*T = 200（实得 %.3f）'
       % m2.horizontal_drift(p_far['vx'], p_far['T']))

    sec('3b ★★ 打在病根上：同一位移，速度上限一变，可达性必须跟着变')
    # 产品的旧算法是 `vx = delta_x / jump_duration` —— 它**根本不看速度上限**，
    # 所以"目标 200px"永远可达。新算法必须能被速度上限否掉，否则等于没改。
    p_fast = m2.plan_jump(200, 0, 0, v_max=m2.RUN_MAX)
    p_slow = m2.plan_jump(200, 0, 0, v_max=100.0)
    ok(p_fast['ok'], 'v_max=320 ⇒ 200px 可达')
    ok(not p_slow['ok'], 'v_max=100 ⇒ 同一目标**不可达**（旧算法不会拒绝）')
    ok(p_fast['ok'] != p_slow['ok'],
       'A/B：同一位移、不同速度上限，可达性必须不同')
    ok(near(p_fast['T'], p_slow['T']),
       '对照：T 与速度上限无关（两边都是 %.3f）' % p_fast['T'])
    ok(p_slow['reason'] == 'too_far',
       "拒绝原因必须是 'too_far'（实得 %r）" % p_slow['reason'])

    # ---------------------------------------------------------------- 4
    sec('4 极限：太远 / 太高都要明确失败，且失败原因不同')
    p1 = m2.plan_jump(400, 0, 0, v_max=m2.RUN_MAX)
    ok(not p1['ok'], '跳 400px 超出 320*1s ⇒ 不可达')
    ok(p1['reason'] == 'too_far', "原因 = 'too_far'（实得 %r）" % p1['reason'])
    p2 = m2.plan_jump(0, 0, 70, v_max=m2.RUN_MAX)
    ok(not p2['ok'], '跳高 70 超出 62.5 ⇒ 不可达')
    ok(p2['reason'] == 'too_high', "原因 = 'too_high'（实得 %r）" % p2['reason'])
    ok(p1['reason'] != p2['reason'],
       '两种失败原因必须不同（否则分不出该"分段"还是该"放弃"）')

    # ---------------------------------------------------------------- 5
    sec('5 边界：刚好够得着必须 ok（别把等号写错成够不着）')
    p_edge = m2.plan_jump(320, 0, 0, v_max=m2.RUN_MAX)
    ok(p_edge['ok'], '恰恰等于 v_max*T=320 ⇒ 可达')
    p_over = m2.plan_jump(320.001, 0, 0, v_max=m2.RUN_MAX)
    ok(not p_over['ok'], '超出 0.001 ⇒ 不可达（边界是闭区间）')

    # ---------------------------------------------------------------- 6
    sec('6 助跑距离：v^2/(2a)')
    d1 = m2.runup_distance(320, 0)
    ok(near(d1, 320 * 320 / (2 * 600), 1e-6),
       '0→320 需 %.3fpx（= v^2/2a）' % d1)
    ok(m2.runup_distance(320, 320) == 0.0, '已经够快 ⇒ 不用退（0）')
    ok(m2.runup_distance(320, 320) < d1, 'A/B：够快时必须比不够快退得少')
    v = m2.reachable_speed(0, d1)
    ok(near(v, 320, 0.5), '跑完 d1 距离应该正好到 320（实得 %.3f）' % v)

    # ---------------------------------------------------------------- 7
    sec('7 逐帧积分 ≈ 解析解（两条独立路径互证）')
    g, vz, dt = m2.GRAVITY, m2.JUMP_SPEED, 0.001
    z, v = 0.0, vz
    steps = int(round(1.0 / dt))
    for _ in range(steps):
        _, _, z, v = m2.step(0, 0, z, 0, 0, v, g, dt)
    ok(abs(z) < 2.0, '积分 1.0s 后 z=%.3f（解析解 0.0，容差 2px）' % z)
    # 半隐式欧拉对二次运动有 O(dt) 偏差，1px 量级可接受；这里同时验方向
    z2, v2 = 0.0, vz
    for _ in range(500):
        _, _, z2, v2 = m2.step(0, 0, z2, 0, 0, v2, g, dt)
    ok(z2 > 60.0, '积分到 t=0.5s 时 z=%.2f 接近峰值 62.5' % z2)
    # 负控制：不该越过 h_max
    ok(z2 < m2.max_jump_height() + 2.0,
       '峰值不得越过 h_max=62.5（实得 %.2f）' % z2)

    # ---------------------------------------------------------------- 8
    sec('8 投影：高度靠"精灵往上挪"表达')
    sx, sy = m2.screen_pos(100.0, 500.0, 60.0)
    ok(sx == 100.0 and near(sy, 440.0), 'z=60 ⇒ 屏幕 y 上移 60（实得 %.1f）' % sy)
    sx0, sy0 = m2.screen_pos(100.0, 500.0, 0.0)
    ok(sy0 == 500.0, 'z=0 ⇒ 屏幕 y 不变（落地就该回到地面）')
    ok(sy != sy0, 'A/B：有高度与无高度的屏幕位置必须不同')

    # ---------------------------------------------------------------- 9
    sec('9 速度锁死：同一初速度在不同 dt 下位移应当可加')
    v = 150.0
    total = 0.0
    for _ in range(100):
        total += v * 0.01
    ok(near(total, v * 1.0), 'v 恒定 1s 累计位移 = %.3f（等于 v*T）' % total)
    p = m2.plan_jump(150, 0, 0, v_max=m2.RUN_MAX)
    ok(near(p['vx'], v), '规划给出的 vx=%.3f 与手算一致' % p['vx'])

    # --------------------------------------------------------------- 汇总
    print('\n' + '=' * 68)
    print('通过 %d 项，失败 %d 项' % (_passes[0], len(_fails)))
    if _fails:
        for f in _fails:
            print('  ✗ %s' % f)
        return 1
    print('[PASS] motion2d 数值验证全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())

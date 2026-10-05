# -*- coding: utf-8 -*-
"""第90轮 · handle_jump 抛物线数值仿真（只读，不改任何被测代码）

复刻 main.py:7707-7712 的公式，逐帧打印 Y 轨迹，判断"抛物线方向"是否合理。

坐标系事实：Qt `self.pos()` 是**屏幕坐标，Y 向下增大**。
公式事实（main.py:7708）：vy0 = (delta_y + 0.5*g*T*T + 50) / T
公式事实（main.py:7712）：y = y0 + vy0*t - 0.5*g*t*t
落地收口（main.py:7740）：jump_progress>=1.0 时 y 被**硬吸附**到 target_y
"""
G = 500.0      # main.py:5277
T = 1.0        # main.py:5335


def traj(delta_y, frames=20):
    vy0 = (delta_y + 0.5 * G * T * T + 50) / T
    rows = []
    for i in range(frames + 1):
        t = T * i / frames
        y = vy0 * t - 0.5 * G * t * t      # 相对起跳点的位移（正=屏幕下方）
        rows.append((t, y))
    return vy0, rows


def report(label, delta_y):
    vy0, rows = traj(delta_y)
    ys = [y for _, y in rows]
    y_end_formula = ys[-1]
    print('--- %s  (delta_y=%+.0f) ---' % (label, delta_y))
    print('  vy0 = %+.1f   （>0 = 初速朝屏幕下方）' % vy0)
    print('  中途 Y 位移范围: min=%+.1f  max=%+.1f' % (min(ys), max(ys)))
    # 早期方向
    y_early = rows[3][1]
    print('  t=0.15 位移 %+.1f  → 前段朝 %s' % (y_early, '下' if y_early > 0 else '上'))
    print('  公式落点位移 %+.1f ，而目标位移 %+.0f ⇒ 末帧硬吸附跳变 %+.1f px'
          % (y_end_formula, delta_y, delta_y - y_end_formula))
    print('  采样: ' + ' '.join('%+.0f' % y for y in ys))
    print()


print('=' * 66)
print('handle_jump 抛物线仿真（g=%.0f, T=%.1f，屏幕 Y 向下为正）' % (G, T))
print('=' * 66)
report('跳上更高的窗口（目标在上方 300px）', -300)
report('跳上略高的窗口（目标在上方 100px）', -100)
report('跳到同高平台', 0)
report('往下跳到低平台（目标在下方 200px）', +200)
print('判读：正确的一次"跳"应当是 **前段朝上**（位移为负）后段回落；')
print('      若前段朝下，说明竖直方向的初速/重力符号与屏幕坐标系相反。')

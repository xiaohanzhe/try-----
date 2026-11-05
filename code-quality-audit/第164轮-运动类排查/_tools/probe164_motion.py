# -*- coding: utf-8 -*-
"""第164轮 · 运动类七块只读测量（不改产品代码）。

用户口径（2026-11-05）：
  · 跳跃/坠落要"偏俯视 2D + 屏幕竖直向下重力 + 正确抛物线"；
  · **原地起跳不许出现横向位移**（要跳远必须先有水平初速度）；
  · 要有**助跑距离**；水平距离与高度**都有极限**；
  · 空中速度**锁死**；超限走"分段 / 放弃 / 说一句求助"。

本支只测量、只记录，**不做任何修改**。七段：
  1 漫游轨迹  2 跳跃  3 重力坠落  4 拖拽  5 甩飞弹跳  6 边界夹紧  7 跟随

跑法：C:\\Python311\\python.exe probe164_motion.py   输出重定向到文件，别接管道。
"""
import os
import sys
import tempfile
import time

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['RALSEI_DATA_DIR'] = os.path.join(tempfile.gettempdir(), 'pet164_data')
os.makedirs(os.environ['RALSEI_DATA_DIR'], exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'src'))

import memory_store as _ms
_ms.find_device_dir = lambda create=True: None
# 第163轮教训：只打 find_device_dir 会落到用户桌面兜底目录
_ms.default_memory_dir = lambda: (os.path.join(
    os.environ['RALSEI_DATA_DIR'], 'memory'), False, None)
import data_store as _ds
_ds.vault_root = lambda create=True: None

from PyQt5.QtWidgets import QApplication            # noqa: E402
from PyQt5.QtCore import QPoint, QPointF, Qt, QEvent  # noqa: E402
from PyQt5.QtGui import QMouseEvent                  # noqa: E402

app = QApplication(sys.argv[:1])


def sec(t):
    print('\n' + '=' * 70)
    print(t)
    print('=' * 70)


def main():
    from main import RalseiPet
    w = RalseiPet()
    w.max_idle_duration = 1e9          # 禁随机漫游，隔离变量
    w.is_moving = False
    w.show()
    app.processEvents()

    g = float(getattr(w, 'gravity', 0) or 0)
    print('gravity = %.1f px/s^2   jump_duration = %.2f   jump_height = %s'
          % (g, float(getattr(w, 'jump_duration', 0) or 0),
             getattr(w, 'jump_height', None)))

    # ---------------------------------------------------------------- 段 2 跳跃
    sec('2 跳跃：原地起跳会不会横移 / 抛物线形状 / 落点精度')

    def run_jump(tag, dx, dy, dur=1.0):
        start = w.pos()
        tgt = QPoint(start.x() + dx, start.y() + dy)
        w.jump_duration = dur
        w.is_jumping = True
        w.jump_start_time = time.time()
        w.jump_start_pos = QPoint(start.x(), start.y())
        w.jump_start_spatial = dict(getattr(w, 'spatial_pos', {}) or {})
        w.jump_target_window = None
        w.jump_target_pos = QPoint(tgt)
        w.jump_target_z = 0
        w.jump_z_diff = 0
        w._jump_anim_override = None
        w.current_floor = getattr(w.floor_manager, 'desktop_floor', None)
        w.jump_target_floor = getattr(w.floor_manager, 'desktop_floor', None)
        traj = []
        t0 = w.jump_start_time
        for i in range(0, 31):
            now = t0 + i * (dur / 20.0)
            try:
                w.handle_jump(dur / 20.0, now)
            except Exception as e:                    # noqa: BLE001
                print('   %-10s handle_jump 抛异常: %s: %s'
                      % (tag, type(e).__name__, e))
                return None
            p = w.pos()
            traj.append((round(now - t0, 3), p.x() - start.x(), p.y() - start.y()))
        xs = [t[1] for t in traj]
        ys = [t[2] for t in traj]
        peak = min(ys)
        end = traj[-1]
        print('   %-10s 目标(dx=%4d,dy=%4d)  x范围[%d,%d]  y峰值%+d  落点(%+d,%+d)  '
              '单调?%s' % (tag, dx, dy, min(xs), max(xs), peak,
                          end[1], end[2],
                          '先上后下' if (peak < end[2] and peak < 0) else '不规则'))
        return traj

    run_jump('原地跳', 0, 0)
    run_jump('原地跳(短)', 0, 0, 0.5)
    run_jump('横跳200', 200, 0)
    run_jump('斜上跳', 150, -80)
    run_jump('纯上跳', 0, -60)

    print('\n   —— "原地跳"逐帧明细（前 12 帧，看 x 是否恒为 0）——')
    tr = run_jump('明细', 0, 0)
    if tr:
        for row in tr[:12]:
            print('      t=%.2f  dx=%+d  dy=%+d' % row)

    # -------------------------------------------------------------- 段 3 坠落
    sec('3 重力坠落：水平惯性 / 是否落出屏 / 会不会半路卡住')
    for tag, vx in (('静止坠落', 0.0), ('带速坠落', 240.0)):
        w.is_gravity_falling = True
        w.fall_speed = 0.0
        w.fall_velocity_x = vx
        if hasattr(w, '_fall_land_y'):
            del w._fall_land_y
        if hasattr(w, '_is_thrown'):
            w._is_thrown = False
        p0 = w.pos()
        ys, xs = [], []
        t0 = time.time()
        for i in range(1, 61):
            now = t0 + i * 0.05
            try:
                w.handle_gravity_fall(0.05, now)
            except Exception as e:                    # noqa: BLE001
                print('   %-8s 抛异常 %s: %s' % (tag, type(e).__name__, e))
                break
            p = w.pos()
            ys.append(p.y())
            xs.append(p.x())
            if not getattr(w, 'is_gravity_falling', False):
                break
        scr = w._virtual_screen_rect()
        print('   %-8s 帧数=%d  y %+d..%+d  x %+d..%+d  屏幕底=%d  落出屏=%s'
              % (tag, len(ys), min(ys) - p0.y() if ys else 0,
                 max(ys) - p0.y() if ys else 0,
                 min(xs) - p0.x() if xs else 0,
                 max(xs) - p0.x() if xs else 0,
                 scr.bottom(), (max(ys) > scr.bottom()) if ys else 'n/a'))

    # -------------------------------------------------------------- 段 6 边界
    sec('6 边界夹紧：极端坐标 / 负坐标 / 超出右下的行为')
    scr = w._virtual_screen_rect()
    print('   虚拟屏幕 rect = (%d,%d) %dx%d' % (scr.x(), scr.y(),
                                               scr.width(), scr.height()))
    print('   工作区底 `_desktop_ground_y` = %s' % w._desktop_ground_y())
    print('   任务栏上沿 `_taskbar_top_y` = %s' % w._taskbar_top_y())
    cases = [
        ('正常', 500, 500),
        ('左上负', -9999, -9999),
        ('右下超界', 99999, 99999),
        ('副屏左', scr.x() - 500, 300),
        ('贴任务栏', 500, w._desktop_ground_y()),
    ]
    for tag, x, y in cases:
        nx, ny = w._clamp_pos_to_desktop(x, y)
        inside = scr.contains(QPoint(nx, ny))
        print('   %-10s (%6d,%6d) -> (%6d,%6d)  在屏幕内=%s'
              % (tag, x, y, nx, ny, inside))

    # -------------------------------------------------------------- 段 1 漫游
    sec('1 漫游轨迹：目标点是否可达 / 会不会越界')
    bad = 0
    for _ in range(200):
        try:
            w.generate_new_move_target()
        except Exception as e:                        # noqa: BLE001
            print('   generate_new_move_target 抛异常: %s: %s' % (type(e).__name__, e))
            break
        t = getattr(w, 'target_pos', None)
        if t is None:
            bad += 1
            continue
        if not scr.contains(t):
            bad += 1
    print('   200 次生成目标：越界或空 = %d 次' % bad)
    print('   _no_progress_frames 阈值 = 60（源码常量），当前值 = %s'
          % getattr(w, '_no_progress_frames', 'N/A'))

    # -------------------------------------------------------------- 段 4 拖拽
    sec('4 拖拽：1:1 跟随是否还成立')
    # ★ 第一版探针只给了 localPos，而产品读的是 `event.globalPos()`（14253 行）
    #   ⇒ offscreen 下 globalPos 恒 (0,0) ⇒ target_pos 恒定 ⇒ 位移 (0,0)。
    #   那是**夹具不保真**，不是产品缺陷。这里显式给 screenPos。
    p0 = w.pos()
    w.drag_position = QPoint(10, 10)

    def _mev(etype, gx, gy, btn, btns):
        return QMouseEvent(etype, QPointF(gx, gy), QPointF(gx, gy),
                           btn, btns, Qt.NoModifier)

    w.mousePressEvent(_mev(QEvent.MouseButtonPress, 10, 10,
                           Qt.LeftButton, Qt.LeftButton))
    ok = True
    for step in (1, 2, 3):
        gx, gy = 10 + step * 20, 10 + step * 10
        before = w.pos()
        w.mouseMoveEvent(_mev(QEvent.MouseMove, gx, gy,
                              Qt.NoButton, Qt.LeftButton))
        after = w.pos()
        dx, dy = after.x() - before.x(), after.y() - before.y()
        if (dx, dy) != (20, 10):
            ok = False
            print('   第%d步 期望(20,10) 实得(%d,%d)  拖后目标=(%d,%d)'
                  % (step, dx, dy, gx - 10, gy - 10))
    w.mouseReleaseEvent(_mev(QEvent.MouseButtonRelease, 70, 40,
                             Qt.LeftButton, Qt.NoButton))
    print('   1:1 跟随 = %s（拖拽位移总计 %d,%d）'
          % (ok, w.pos().x() - p0.x(), w.pos().y() - p0.y()))

    # -------------------------------------------------------------- 段 5 甩飞
    sec('5 甩飞弹跳：落点是否走工作区底 / 会不会越界')
    try:
        w.start_falling(fall_velocity=200, is_thrown=True, reason='probe')
        ys = []
        t0 = time.time()
        for i in range(1, 81):
            now = t0 + i * 0.05
            w.handle_gravity_fall(0.05, now)
            ys.append(w.pos().y())
            if not getattr(w, 'is_gravity_falling', False):
                break
        ground = w._desktop_ground_y()
        print('   甩飞 帧数=%d  最终 y=%s  工作区底=%s  沉到下面=%s'
              % (len(ys), ys[-1] if ys else None, ground,
                 (ys[-1] > ground + 2) if ys else 'n/a'))
        for _ in range(60):
            if not getattr(w, 'is_bouncing', False):
                break
            w.update_bounce()
        print('   弹跳后 y=%d  is_bouncing=%s'
              % (w.pos().y(), getattr(w, 'is_bouncing', False)))
    except Exception as e:                            # noqa: BLE001
        print('   甩飞测试抛异常: %s: %s' % (type(e).__name__, e))

    # -------------------------------------------------------------- 段 7 跟随
    sec('7 跟随鼠标：死区 / 追上后是否抖动')
    before = w.pos()
    w.is_following_mouse = True
    deltas = []
    for _ in range(30):
        w._handle_mouse_follow(0.033)
        d = w.pos()
        deltas.append((d.x(), d.y()))
    moved = sum(1 for i in range(1, len(deltas))
                if deltas[i] != deltas[i - 1])
    print('   30 帧内位置变化次数 = %d  起点=%s 终点=%s'
          % (moved, (before.x(), before.y()), deltas[-1]))
    w.is_following_mouse = False

    try:
        w.cleanup_on_exit()
    except Exception:                                 # noqa: BLE001
        pass


if __name__ == '__main__':
    main()

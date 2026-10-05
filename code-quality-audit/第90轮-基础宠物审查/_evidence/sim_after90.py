# -*- coding: utf-8 -*-
u"""第90轮 · 改前/改后弹道对照（**直接驱动真实的 `RalseiPet.handle_jump`**）

与 `sim_jump90.py` 的区别：那个是**复刻公式**（只读快照），
本脚本**真调产品函数**（轻量桩），并用**独立重算**的旧公式做对照。
⇒ 满足「断行为不断赋值」：判据取的是产品的**产物输出**，不是源码字面量。
"""
import os
import sys
import types

from PyQt5.QtCore import QPoint, QRect

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(REPO, 'ralsei_pet')
for p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if p not in sys.path:
        sys.path.insert(0, p)

from main import RalseiPet      # noqa: E402

G, T = 500.0, 1.0
DESKTOP = {'type': 'desktop', 'rect': QRect(0, 0, 0, 0), 'z_order': 0,
           'platform_height': 0}


def stub(start_y, target_y):
    o = types.SimpleNamespace()
    o.gravity = G
    o.jump_duration = T
    o.jump_start_time = 0.0
    o.jump_start_pos = QPoint(500, start_y)
    o.jump_target_pos = QPoint(500, target_y)
    o.jump_target_z = 0
    o.jump_z_diff = 0
    o.jump_start_spatial = {'x': 500.0, 'y': float(start_y), 'z': 0.0}
    o.spatial_pos = {'x': 500.0, 'y': float(start_y), 'z': 0.0}
    o.is_jumping = True
    o._jump_anim_override = None
    o.current_floor = DESKTOP
    o.jump_target_floor = DESKTOP
    o.current_platform_z = 0
    o._pos = QPoint(500, start_y)
    o.pos = lambda: o._pos
    o.move = lambda x, y: setattr(o, '_pos', QPoint(int(x), int(y)))
    o.width = lambda: 40
    o.height = lambda: 40
    o.show = lambda: None
    o._clamp_pos_to_desktop = lambda x, y: (int(x), int(y))
    o._floor_identity_key = RalseiPet._floor_identity_key
    o.floor_manager = types.SimpleNamespace(get_all_floors=lambda: [DESKTOP])
    o._sync_window_cache_from_floor = lambda f: None
    o._apply_pet_z_order = lambda: True
    o.change_animation = lambda name, force=False: True
    o.play_animation_once = lambda name, callback=None, restore_to=None: True
    return o


def fly_new(start_y, target_y, n=100):
    o = stub(start_y, target_y)
    ys = []
    for i in range(n + 1):
        RalseiPet.handle_jump(o, 0.033, T * i / n)
        ys.append(o.pos().y())
    return ys


def fly_old(start_y, target_y, n=100):
    """独立重算旧公式（不碰产品代码）。"""
    dy = float(target_y - start_y)
    vy0 = (dy + 0.5 * G * T * T + 50.0) / T
    ys = []
    for i in range(n + 1):
        t = T * i / n
        ys.append(target_y if i == n else int(start_y + vy0 * t - 0.5 * G * t * t))
    return ys


def row(label, start_y, target_y):
    new = fly_new(start_y, target_y)
    old = fly_old(start_y, target_y)
    print('--- %s   (起跳 y=%d → 目标 y=%d, Δy=%+d) ---'
          % (label, start_y, target_y, target_y - start_y))
    for tag, ys in (('改后(真调产品)', new), ('改前(独立重算)', old)):
        _mn, _ai = min(ys), ys.index(min(ys))
        arc = (_mn < start_y) and (0 < _ai < len(ys) - 1)
        early = ys[3]
        print('   %-14s 前段朝向=%-4s 顶点抬升=%-5s 弧=%s  末前帧误差=%+d  落点=%d'
              % (tag,
                 '上' if early < start_y else '下',
                 ('%dpx' % (start_y - _mn)),
                 '真' if arc else '**无**',
                 ys[-2] - target_y,
                 ys[-1]))
    print()


print('=' * 78)
print('第90轮 handle_jump 弹道对照（真调产品 vs 旧公式独立重算）')
print('=' * 78)
row('跳上更高的窗口', 500, 200)
row('跳上略高的窗口', 500, 400)
row('跳到同高平台', 500, 500)
row('往下跳到低平台', 500, 700)
print('判读：')
print('  · 「弧=真」要求**顶点在飞行中段**（先上后下）；旧公式在同高/略高跳上恒为「无弧」。')
print('  · 「末前帧误差」= 跳跃结束前最后一帧与目标的距离；旧公式恒差 ≈ -50px，')
print('     只能靠 `jump_progress>=1.0` 的**末帧硬吸附**去补 ⇒ 落地瞬间跳变 50px。')
print('  · 改后落点误差 0~1px（纯离散取整），不再需要任何魔数或硬吸附。')

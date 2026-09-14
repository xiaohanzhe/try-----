# -*- coding: utf-8 -*-
"""第八轮 · 甩飞轨迹 / 卡动画 / 空中接住 修复验证（Task #12）

对应用户报的三条：
  1) "他被甩飞时候的那个抛物线是斜抛运动，轨迹要由初速度方向和大小决定"
  2) "他偶尔会在被甩飞的时候卡在一个动画里不继续"
  3) "他坠落过程中没办法用鼠标二次抓住他……要有一个针对他当时线速度的减速效果，
      而不是和撞上一堵墙毫无缓冲的感觉"

根因：
  · 甩飞初速把竖直分量**强行掰成向上**（`if _vy > -350: _vy = -350 - abs(_vy)*0.5`），
    于是"横着甩/往下甩"都被改成上抛，方向与松手方向无关；
    且落点判定用 `_vy > 0 and _ny >= _launch_y`，水平/下甩的初速一上来就满足条件
    → 第 1 帧原地落地，斜抛根本飞不起来。
  · "卡在动画里不继续"的主因是状态互斥被破坏：check_window_movement 跑在
    update_movement 三个坠落分支**之前**，飞行途中越过"窗口→桌面"边界就会
    触发 start_falling()，使 is_falling 与 is_gravity_falling 同时为真 →
    update_movement 永远优先走 handle_gravity_fall，handle_fall 的 _fall_phase
    再也不推进 → 宠物永久停在 jump_ball。另有一次性动画在"帧数为 0"时
    完成检测永不触发 → _play_once_active 永久为真 → 动画冻结。
  · 坠落中按鼠标：update_movement 在拖拽保护之前就走 handle_fall 并 return，
    抛物线继续移动宠物、与鼠标拖拽互相拉扯 → 抓不住；且一抓就是撞墙式急停。

验证方式：stub 直接驱动真实的 handle_fall / _catch_falling_in_air /
_tick_catch_brake / check_window_movement，外加源码级不变量。
"""
import os
import sys
import time
import types

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PET = os.path.join(BASE, 'ralsei_pet')
for _p in (os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if _p not in sys.path:
        sys.path.append(_p)

from PyQt5.QtCore import QPoint, QRect  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])

from main import RalseiPet  # noqa: E402

MAIN_SRC = open(os.path.join(PET, 'src', 'main.py'), encoding='utf-8').read()

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, detail))
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                         (" <- " + str(detail)) if detail else ""))


SCREEN = QRect(0, 0, 1920, 1080)


class Quiet:
    def add_dialogue(self, *a, **k):
        pass

    def show_dialogue(self, *a, **k):
        pass

    def react_to_event(self, *a, **k):
        pass

    def play_splat(self):
        pass


def make_fall_stub(launch_y=500, floor_y=969, gravity=2000.0):
    """只装 handle_fall / 空中接住 真正用到的属性。"""
    o = types.SimpleNamespace()
    o._x, o._y = 400, int(launch_y)
    o.gravity = gravity
    o.is_recovering = False
    o.is_falling = True
    o.is_splat = False
    o.is_gravity_falling = False
    o.fall_duration = 0.0
    o.recovery_duration = 0.0
    o.max_fall_duration = 3.5
    o.recovery_max_duration = 2.0
    o._fall_phase = "flying"
    o._fall_phase_start = 0.0
    o._fall_flight_time = 0.0
    o._fall_landed = False
    o._fall_launch_y = int(launch_y)
    o.sprite_loader = types.SimpleNamespace(
        sprites={"splat": [1], "fall": [1], "fall_back_rub": [1],
                 "fall_back": [1], "land": [1], "jump_ball": [1], "idle": [1]})
    o.sound_manager = Quiet()
    o.dialogue_ui = Quiet()
    o.emotion_system = Quiet()
    o.play_animation_once = lambda *a, **k: True
    o.change_animation = lambda *a, **k: True
    o.calls = []

    def _pos():
        return QPoint(o._x, o._y)

    def _move(x, y):
        o._x, o._y = int(x), int(y)

    o.pos = _pos
    o.move = _move
    o.width = lambda: 110
    o.height = lambda: 110
    o.frameGeometry = lambda: QRect(o._x, o._y, 110, 110)
    o._desktop_floor_y = lambda: int(floor_y)
    o._clamp_pos_to_desktop = lambda x, y: (int(x), max(0, min(int(y), int(floor_y))))
    return o


def fly(o, frames=400, dt=0.033):
    """推进 handle_fall 直到落地（或跑满 frames），返回落点轨迹。"""
    xs, ys = [], []
    for _ in range(frames):
        RalseiPet.handle_fall(o, dt, time.time())
        xs.append(o._x)
        ys.append(o._y)
        if getattr(o, '_fall_phase', "flying") != "flying":
            break
    return xs, ys


# ------------------------------------------------------------------------ tests
def t1_no_forced_upward():
    """源码级：不得再把竖直分量强行掰成向上。"""
    # 只看代码行，注释里的"当年写法"说明不算
    code_lines = [ln for ln in MAIN_SRC.splitlines()
                  if not ln.lstrip().startswith('#')]
    check("F1.1 已删除[强行上抛]的硬编码（_vy = -350 - abs(_vy)*0.5）",
          not any("-350.0 - abs(_vy) * 0.5" in ln for ln in code_lines))
    check("F1.2 改为等比缩放 + 按矢量和限幅（不掰弯方向）",
          "_LAUNCH_SCALE" in MAIN_SRC and "_MAX_LAUNCH_SPEED" in MAIN_SRC
          and "_k = _MAX_LAUNCH_SPEED / _v_mag" in MAIN_SRC)
    check("F1.3 落点判定要求初速朝上才用[回到起跳高度]",
          "_hit_launch = (_vy0_launch < 0 and _vy > 0 and _ny >= _launch_y)" in MAIN_SRC)


def t2_horizontal_throw_falls_not_rises():
    """核心：水平甩出 → 一开始就往下走（不再被掰成上抛）。"""
    o = make_fall_stub(launch_y=500)
    o._fall_vx = 900.0
    o._fall_vy = 0.0
    xs, ys = fly(o, frames=6)
    check("F2.1 水平甩出后首帧即下落（y 增大），没有被强行上抛",
          len(ys) >= 2 and ys[0] > 500, "ys[:4]=%s" % ys[:4])
    check("F2.2 水平方向持续朝甩出方向前进（x 递增）",
          len(xs) >= 2 and xs[0] > 400 and xs[1] > xs[0], "xs[:4]=%s" % xs[:4])


def t3_downward_throw_descends_to_floor():
    """向下甩出 → 一路落到实心地面，而不是第 1 帧原地落地。"""
    o = make_fall_stub(launch_y=200)
    o._fall_vx = 0.0
    o._fall_vy = 700.0
    xs, ys = fly(o)
    check("F3.1 下甩不会原地秒落地（至少飞了多帧）", len(ys) > 3, "frames=%d" % len(ys))
    check("F3.2 最终落到屏幕底边（而不是悬停在松手高度）",
          ys and ys[-1] == o._desktop_floor_y(), "final_y=%s floor_y=%s" % (ys[-1], o._desktop_floor_y()))


def t4_upward_throw_keeps_round6_behaviour():
    """向上甩出 → 仍是上抛并精确落回起跳高度（保留第六轮已验证语义）。"""
    o = make_fall_stub(launch_y=500)
    o._fall_vx = 400.0
    o._fall_vy = -350.0
    xs, ys = fly(o)
    check("F4.1 上抛：先升（y 先减小）再落回起跳高度",
          ys and min(ys) < 500 and ys[-1] == 500,
          "min_y=%s final_y=%s" % (min(ys) if ys else None, ys[-1] if ys else None))


def t5_pure_vertical_up_lands_at_launch_height():
    """纯竖直上抛：精确吸附回起跳高度（第六轮 D6b 的等价复核）。"""
    o = make_fall_stub(launch_y=500)
    o._fall_vx = 0.0
    o._fall_vy = -600.0
    xs, ys = fly(o)
    check("F5 纯竖直上抛精确落回起跳高度并进入 splat 之后",
          ys and ys[-1] == 500 and o._fall_phase in ("splat", "dazed", "recovering"),
          "final_y=%s phase=%s" % (ys[-1] if ys else None, o._fall_phase))


def t6_catch_in_air_works():
    """核心：坠落途中能被"接住"，且线速度进入缓冲窗口。"""
    o = make_fall_stub()
    o._fall_vx = 600.0
    o._fall_vy = 300.0
    o._CATCH_BRAKE_SECONDS = 0.28
    o._catch_brake = None
    ok = RalseiPet._catch_falling_in_air(o)
    check("F6.1 坠落中按下 → 接住成功", ok is True)
    check("F6.2 接住后坠落状态全部清掉（两种坠落都不再为真）",
          o.is_falling is False and o.is_gravity_falling is False,
          "is_falling=%s is_gravity=%s" % (o.is_falling, o.is_gravity_falling))
    check("F6.3 抛物线字段已清理（_fall_vx/_fall_vy/_fall_phase）",
          not hasattr(o, '_fall_vx') and not hasattr(o, '_fall_vy')
          and not hasattr(o, '_fall_phase'))
    cb = getattr(o, '_catch_brake', None)
    # 注意：detail 里**不要**打印 cb['t0']（time.time() 每次不同）——G2 要求输出
    # 逐字节可比，带时间戳会让本套件永远判 DIFF。
    check("F6.4 线速度被记录进缓冲窗口（vx=600, vy=300）",
          cb is not None and cb['vx'] == 600.0 and cb['vy'] == 300.0,
          "cb.vx=%s cb.vy=%s cb.dur=%s" % (cb['vx'], cb['vy'], cb['dur']) if cb else "cb=None")
    check("F6.5 未坠落时不该有缓冲（普通拖拽零影响）",
          RalseiPet._catch_falling_in_air(
              types.SimpleNamespace(is_falling=False, is_gravity_falling=False,
                                    _catch_brake=None)) is False)


def t7_catch_brake_decays_not_wall_stop():
    """核心：缓冲是"按线速度滑一段并衰减到 0"，不是撞墙式急停。"""
    o = make_fall_stub()
    o._fall_vx = 700.0
    o._fall_vy = 0.0
    o._CATCH_BRAKE_SECONDS = 0.30
    o._catch_brake = None
    o.drag_position = None
    o._clamp_pos_to_desktop = lambda x, y: (int(x), int(y))
    RalseiPet._catch_falling_in_air(o)
    start_x = o._x
    cb = o._catch_brake

    xs = []
    # 注意：最后一步要**明确越过** dur（用 0.32 > 0.30），否则 `time.time()` 在
    # 10^9 量级上的双精度误差会让 elapsed 落在 0.2999996 这种"差一点点"的值上，
    # 导致缓冲窗口没被判定结束 —— 那是测试脚手架的假失败，不是代码缺陷。
    for frac in (0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.32):
        cb['t0'] = time.time() - frac          # 模拟已过 frac 秒
        RalseiPet._tick_catch_brake(o, 0.033)
        xs.append(o._x)

    total = xs[-1] - start_x
    check("F7.1 接住后确实还会滑行一段（不是原地急停）", total > 20,
          "位移=%d px" % total)
    check("F7.2 位移单调不减且随速度衰减收敛（减速效果）",
          all(b >= a for a, b in zip(xs, xs[1:])) and total < 250,
          "xs=%s" % xs)
    check("F7.3 缓冲结束后窗口自动清空", o._catch_brake is None)
    # 注意：不打印 drag_position 的坐标 —— 它来自 QCursor.pos()，离屏下也可能变。
    check("F7.4 缓冲结束时重设拖拽锚点（避免被拉回光标处跳动）",
          getattr(o, 'drag_position', None) is not None)
    check("F7.5 源码级：缓冲推进被接进 update_movement（拖拽保护之前）",
          "self._tick_catch_brake(elapsed_time)" in MAIN_SRC
          and "self._catch_falling_in_air()" in MAIN_SRC)


def t8_states_are_mutually_exclusive():
    """源码级不变量：两种坠落状态互斥，不再出现同时为真。"""
    src = MAIN_SRC
    check("F8.1 start_fall 清 is_gravity_falling",
          "self.is_gravity_falling = False" in src)
    check("F8.2 start_falling 清 is_falling（并清 is_splat）",
          "self.is_falling = False\n        self.is_splat = False" in src)
    check("F8.3 trigger_splat 也清 is_gravity_falling（把隐患从[靠调用方记得清]变自洽）",
          "self.is_gravity_falling = False\n        self.is_recovering = False" in src
          or "self.is_moving = False\n        self.is_falling = True" in src)


def t9_airborne_skips_floor_check():
    """核心：坠落/跳跃/拖拽中不再做楼层判定（否则会破坏状态互斥并卡死动画）。"""
    o = make_fall_stub()
    o.is_falling = True
    o.is_jumping = False
    o.is_gravity_falling = False
    o._spell_stage = None
    o.game_state = {"is_playing": False}
    touched = {"n": 0}

    class FM:
        def update_floors(self):
            touched["n"] += 1

    o.floor_manager = FM()
    RalseiPet.check_window_movement(o)
    check("F9.1 is_falling 时直接返回（连窗口枚举都不做）", touched["n"] == 0,
          "update_floors 调用次数=%d" % touched["n"])

    for flag in ('is_gravity_falling', 'is_jumping'):
        o2 = make_fall_stub()
        o2.is_falling = False
        o2.is_jumping = False
        o2.is_gravity_falling = False
        setattr(o2, flag, True)
        o2._spell_stage = None
        o2.game_state = {"is_playing": False}
        o2.floor_manager = FM()
        touched["n"] = 0
        RalseiPet.check_window_movement(o2)
        check("F9.2 %s 时同样不判定楼层" % flag, touched["n"] == 0,
              "update_floors=%d" % touched["n"])

    o3 = make_fall_stub()
    o3.is_falling = False
    o3.is_jumping = False
    o3.is_gravity_falling = False
    o3._is_being_dragged = True
    o3._spell_stage = None
    o3.game_state = {"is_playing": False}
    o3.floor_manager = FM()
    touched["n"] = 0
    RalseiPet.check_window_movement(o3)
    check("F9.3 拖拽中同样不判定楼层（不与鼠标抢位置）", touched["n"] == 0,
          "update_floors=%d" % touched["n"])


def t10_once_anim_selfcheck():
    """源码级：一次性动画"数不出帧"时必须有自检解除（否则动画永久冻结）。"""
    check("F10.1 update_animation 增加了[帧数为 0 就解除一次性动画保护]的自检",
          "没有可用帧，解除卡死保护并回落 idle" in MAIN_SRC
          and "len(self.sprite_loader.sprites.get(self.current_animation, [])) == 0"
          in MAIN_SRC)


def t11_second_fling_not_polluted():
    """第二轮甩飞不能被上一轮残留的 _fall_vy0 污染。

    这是"卡在动画里不继续"的第二条真实成因：`_fall_vy0`（起跳竖直初速）是
    Task #12 新增的，而落地/恢复三处清理点当时是**内联属性名元组**、漏了它 →
    第一次甩飞结束后 `_fall_vy0` 留在对象上；第二次往下甩时 `handle_fall`
    读到上一轮的负值（-700），把"初速朝上"判定为真，于是要求"回到起跳高度"，
    而实际在下坠 → 永远不满足 → 一路飞到 2.5s 兜底超时才落地。
    """
    o = make_fall_stub(launch_y=500)
    o._fall_vx = 0.0
    o._fall_vy = -700.0
    fly(o)
    check("F11.1 第一次甩飞落地后 _fall_vy0 已被清理（不留残留）",
          not hasattr(o, '_fall_vy0'), "has=%s" % hasattr(o, '_fall_vy0'))

    # 模拟"同一个宠物对象"再被往下甩一次
    o._fall_phase = "flying"
    o._fall_flight_time = 0.0
    o._x, o._y = 400, 120
    o._fall_launch_y = 120
    o._fall_vx = 0.0
    o._fall_vy = 700.0
    o.is_splat = False
    xs, ys = fly(o)
    check("F11.2 紧接着下甩第二轮仍能正常落地（不沿用上一轮初速）",
          ys and ys[-1] == o._desktop_floor_y() and len(ys) < 60,
          "frames=%d final_y=%s floor_y=%s" % (len(ys), ys[-1] if ys else None,
                                               o._desktop_floor_y()))

    # 源码级防复发：三处清理点必须共用常量，不得再内联属性名元组
    check("F11.3 清理点统一用 _FALL_VELOCITY_ATTRS/_FALL_STATE_ATTRS 常量",
          "_FALL_VELOCITY_ATTRS" in MAIN_SRC and "_FALL_STATE_ATTRS" in MAIN_SRC
          and "'_fall_landed', '_fall_flight_time'" not in MAIN_SRC)
    check("F11.4 _fall_vy0 在速度清理常量里（新增字段不会再被漏掉）",
          "_fall_vy0'," in MAIN_SRC.split("_FALL_VELOCITY_ATTRS = (")[1].split(")")[0]
          if "_FALL_VELOCITY_ATTRS = (" in MAIN_SRC else False)


def main():
    t1_no_forced_upward()
    t2_horizontal_throw_falls_not_rises()
    t3_downward_throw_descends_to_floor()
    t4_upward_throw_keeps_round6_behaviour()
    t5_pure_vertical_up_lands_at_launch_height()
    t6_catch_in_air_works()
    t7_catch_brake_decays_not_wall_stop()
    t8_states_are_mutually_exclusive()
    t9_airborne_skips_floor_check()
    t10_once_anim_selfcheck()
    t11_second_fling_not_polluted()

    total = len(RESULTS)
    passed = sum(1 for ok, _n, _d in RESULTS if ok)
    print("-" * 68)
    print("第八轮甩飞/卡动画/空中接住验证：%d/%d PASS, %d FAIL"
          % (passed, total, total - passed))
    for ok, name, detail in RESULTS:
        if not ok:
            print("  FAIL: %s  %s" % (name, detail))
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""第六轮修复的回归验证（只读，不改动项目文件）。

覆盖用户本轮提出的 6 条诉求：
  A 内置台词已删除（方法级 + 源码级 + 定时器级）
  B 自主开口：唯一入口是 AI，且 10 分钟最多 1 次
  C 甩飞判定：按真实速度(px/s)判定，慢放/停顿后松手不触发
  D 抛物路径：飞行阶段是"上抛 + 重力 + 空气阻力"的抛物线，落地即进 splat
  E "站起身"类动作只播一次
  F 动画帧率默认 6；多显示器夹紧不再把宠物拉回主屏
"""
import io
import json
import os
import re
import sys
import time
import types

BASE = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
sys.path.insert(0, os.path.join(BASE, "src"))
sys.path.insert(0, os.path.join(BASE, "modules"))

from PyQt5.QtCore import QPoint, QRect  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("  [PASS] " if ok else "  [FAIL] ") + name + ((" :: " + detail) if detail else ""))


MAIN_SRC = io.open(os.path.join(BASE, "src", "main.py"), encoding="utf-8").read()
DS_SRC = io.open(os.path.join(BASE, "modules", "dialogue_system.py"), encoding="utf-8").read()

import main as main_mod  # noqa: E402
from main import RalseiPet  # noqa: E402
import dialogue_system as ds_mod  # noqa: E402

# ============================================================
print("=== A. 内置台词（系统自带对话）已删除 ===")
REMOVED = [
    "check_browser_windows", "check_ppt_windows", "check_excel_windows",
    "check_word_windows", "check_task_management", "check_time_tracking",
    "check_meeting_reminders", "check_file_organization", "check_quick_notes",
    "check_email_management", "check_schedule_planning", "check_project_management",
    "check_work_efficiency", "check_document_collaboration", "check_meeting_recording",
    "check_work_life_balance", "check_excel_table_needs",
    "check_weather_response", "check_interesting_files",
    "handle_dragging_play",
]
missing = [n for n in REMOVED if hasattr(RalseiPet, n)]
check("A1 RalseiPet 上 20 个内置台词/假搬运方法全部不存在",
      not missing, "still present=%s" % missing)

check("A2 dialogue_system 不再有 should_initiate_conversation / initiate_conversation",
      not hasattr(ds_mod.DialogueSystem, "should_initiate_conversation")
      and not hasattr(ds_mod.DialogueSystem, "initiate_conversation"))

_dead_pat = r"self\.(" + "|".join(REMOVED) + r")\s*\("
dead_calls = re.findall(_dead_pat, MAIN_SRC)
check("A3 main.py 源码里已无这些方法的调用点",
      not dead_calls, "calls=%s" % sorted(set(dead_calls)))

check("A4 天气播报定时器已停用（weather_timer 置 None，不再每 5 分钟播报）",
      re.search(r"self\.weather_timer\s*=\s*None", MAIN_SRC) is not None
      and MAIN_SRC.count("self.weather_timer.timeout.connect") == 0)

check("A5 check_initiate_dialogue 只调 start_autonomous_speech（不再走模板库）",
      "start_autonomous_speech" in MAIN_SRC
      and "should_initiate_conversation()" not in MAIN_SRC
      and "initiate_conversation()" not in MAIN_SRC)

# ============================================================
print("=== B. 自主开口：AI 唯一通道 + 10 分钟闸门 ===")


class FakeDialogueUI:
    def __init__(self):
        self.history = []
        self.visible = 0
        self.user_typing = False
        self._ai_inflight = False

    def add_dialogue(self, who, text, face="normal"):
        self.history.append((who, text, face))

    def show_dialogue(self, *a, **k):
        self.visible += 1

    def _is_user_inputting(self):
        return self.user_typing


def make_speech_stub(api_enabled=True, reply="  你好呀，主人在忙什么呢？  "):
    o = types.SimpleNamespace()
    o.AUTONOMOUS_SPEECH_MIN_INTERVAL = 600.0
    o.is_sleeping = False
    o.game_state = {"is_playing": False}
    o.is_falling = o.is_recovering = o.is_splat = False
    o.is_jumping = o.is_gravity_falling = False
    o._is_being_dragged = False
    o.is_following_mouse = False
    o.dialogue_ui = FakeDialogueUI()
    o.api_enabled = api_enabled
    o.emotion_system = types.SimpleNamespace(
        get_current_emotion=lambda: ("happy", 10),
        get_face_for_emotion=lambda e, v: "happy")
    o.calls = []

    def _chat(text, cb):
        o.calls.append(text)
        cb(reply)

    o.chat_with_ai = _chat
    return o


F_speech = RalseiPet.start_autonomous_speech
F_allowed = RalseiPet._autonomous_speech_allowed
F_can = RalseiPet._can_speak_now


def bind_speech(o):
    """SimpleNamespace 不是 RalseiPet 实例，把两个内部方法绑上去。"""
    o._autonomous_speech_allowed = lambda: F_allowed(o)
    o._can_speak_now = lambda: F_can(o)
    return o


_orig_make_speech_stub = make_speech_stub


def make_speech_stub(*a, **k):   # noqa: F811
    return bind_speech(_orig_make_speech_stub(*a, **k))

s = make_speech_stub()
check("B1 三个新方法存在（start / _autonomous_speech_allowed / _can_speak_now）",
      all(callable(x) for x in (F_speech, F_allowed, F_can)))

first = F_speech(s, "timer")
second = F_speech(s, "timer")
check("B2 首次开口成功、紧接着第二次被 10 分钟闸门挡住",
      first is True and second is False and len(s.dialogue_ui.history) == 1,
      "first=%s second=%s shown=%d" % (first, second, len(s.dialogue_ui.history)))

s2 = make_speech_stub()
s2._last_autonomous_speech_time = time.time() - 599.0
blocked = F_speech(s2, "timer")
s3 = make_speech_stub()
s3._last_autonomous_speech_time = time.time() - 601.0
passed = F_speech(s3, "timer")
check("B3 边界：差 1 秒（599s）拒绝，满 600s 以上放行",
      blocked is False and passed is True, "599s->%s 601s->%s" % (blocked, passed))

s4 = make_speech_stub()
s4.dialogue_ui.user_typing = True
s5 = make_speech_stub()
s5.is_sleeping = True
s6 = make_speech_stub()
s6.game_state = {"is_playing": True}
s7 = make_speech_stub()
s7.is_falling = True
check("B4 用户打字中 / 睡眠中 / 游戏中 / 摔倒中 一律闭嘴",
      all(F_can(x) is False for x in (s4, s5, s6, s7)))

s8 = make_speech_stub(api_enabled=False)
off = F_speech(s8, "timer")
check("B5 未启用本地 AI → 保持沉默，且不落任何台词（不再回落内置模板）",
      off is False and not s8.dialogue_ui.history and not s8.calls)

s9 = make_speech_stub(reply="   。  ")
F_speech(s9, "timer")
check("B6 AI 选择沉默（只回一个句号）→ 不显示任何对话",
      not s9.dialogue_ui.history)

s10 = make_speech_stub(reply="主人好久没跟我说话啦，是不是很忙呀？要不要休息一下呢？")
F_speech(s10, "timer")
shown = s10.dialogue_ui.history
check("B7 AI 正常返回 → 只取第一句、去引号、显示一次",
      len(shown) == 1 and shown[0][1] == "主人好久没跟我说话啦，是不是很忙呀？",
      "shown=%r" % (shown,))

s11 = make_speech_stub()
r11 = F_speech(s11, "user_chat", user_requested=True)
r12 = F_speech(s11, "user_chat", user_requested=True)
check("B8 用户主动点'聊天'不受 10 分钟闸门限制（可连续两次）",
      r11 is True and r12 is True)

# ============================================================
print("=== C. 甩飞判定：真实速度(px/s) + 时效性 ===")


class _Sentinel(Exception):
    pass


class FakeEvent:
    """到 event.pos() 时抛哨兵，把 mouseReleaseEvent 精确截断在释放逻辑之后。"""

    def button(self):
        from PyQt5.QtCore import Qt
        return Qt.LeftButton

    def pos(self):
        raise _Sentinel()


class FakeTimer:
    def start(self, ms):
        pass

    def stop(self):
        pass


def make_drag_stub():
    o = types.SimpleNamespace()
    o._is_being_dragged = True
    o._drag_speed = 0.0
    o._last_drag_pos = QPoint(100, 100)
    o.is_falling = False
    o.is_recovering = False
    o._bounce_timer = FakeTimer()
    o.sprite_loader = types.SimpleNamespace(sprites={"jump_ball": [1], "fall": [1]})
    o.dialogue_ui = FakeDialogueUI()
    o.pet_ai = types.SimpleNamespace(react_to_event=lambda *a, **k: None)
    o._anims = []

    def _ca(name, force=False):
        o._anims.append(name)
        return True

    o.change_animation = _ca
    o._pos = QPoint(300, 400)
    o.pos = lambda: o._pos
    return o


def release_with(o, samples):
    o._drag_samples = list(samples)
    try:
        RalseiPet.mouseReleaseEvent(o, FakeEvent())
    except _Sentinel:
        pass


now = time.time()
# C1 慢拖：600 px/s（120ms 内走 72px）→ 不该飞
o = make_drag_stub()
release_with(o, [(now - 0.12, 0, 0), (now, 72, 0)])
check("C1 慢拖 600px/s 松手 → 不触发甩飞",
      not getattr(o, "is_falling", False),
      "is_falling=%s" % getattr(o, "is_falling", False))

# C2 猛甩：2000 px/s 向上斜甩 → 触发，且竖直初速为负（先腾空）
o = make_drag_stub()
release_with(o, [(now - 0.12, 0, 0), (now, 0, -240)])
check("C2 猛甩 2000px/s → 触发甩飞，且竖直初速向上（<0）",
      getattr(o, "is_falling", False) is True and getattr(o, "_fall_vy", 0) < 0,
      "falling=%s vx=%.0f vy=%.0f" % (getattr(o, "is_falling", False),
                                      getattr(o, "_fall_vx", 0), getattr(o, "_fall_vy", 0)))

# C3 拖完停住 0.5 秒再松手（最后一次采样陈旧）→ 即使位移很大也当轻放
o = make_drag_stub()
release_with(o, [(now - 0.62, 0, 0), (now - 0.5, 900, 900)])
check("C3 拖完停住 0.5s 再松手 → 视为轻放，绝不甩飞",
      not getattr(o, "is_falling", False))

# C4 只有一次采样（按下即松）→ 不甩飞
o = make_drag_stub()
release_with(o, [(now, 0, 0)])
check("C4 按下即松（无位移采样）→ 不甩飞", not getattr(o, "is_falling", False))

# C5 门槛值就在源码里，且远高于旧的 150
m = re.search(r"_FLING_SPEED\s*=\s*([0-9.]+)", MAIN_SRC)
check("C5 甩飞门槛显式定义且 >= 900px/s（旧实现是 150 像素差）",
      m is not None and float(m.group(1)) >= 900.0,
      "threshold=%s" % (m.group(1) if m else None))

# C6/C7 判定位置（这是"动作触发逻辑不对"的根因修复）
import inspect as _inspect  # noqa: E402

_rel_src = _inspect.getsource(RalseiPet.mouseReleaseEvent)
_mv_src = _inspect.getsource(RalseiPet.mouseMoveEvent)
check("C6 松手判定已搬进 mouseReleaseEvent，mouseMoveEvent 里不再有它",
      "_FLING_SPEED" in _rel_src and "_FLING_SPEED" not in _mv_src,
      "rel=%s mv=%s" % ("_FLING_SPEED" in _rel_src, "_FLING_SPEED" in _mv_src))

check("C7 长按部位反应加了 not is_falling 守卫（被甩飞时不顺带捏脸/拉手）",
      "['is_pressing'] and not getattr(self, 'is_falling', False)" in MAIN_SRC)

# ============================================================
print("=== D. 抛物路径（俯视 2D 风格）===")


def make_fall_stub(launch_y=500, floor_y=700):
    o = types.SimpleNamespace()
    o.is_recovering = False
    o.fall_duration = 0.0
    o._fall_phase = "flying"
    o._fall_vx = 400.0
    o._fall_vy = -350.0
    o._fall_launch_y = launch_y
    o.gravity = 500.0
    o.max_fall_duration = 3.5
    o.recovery_max_duration = 2.0
    o.is_splat = False
    o.sprite_loader = types.SimpleNamespace(sprites={"splat": [1], "fall_back_rub": [1],
                                                     "land": [1], "idle": [1]})
    o.dialogue_ui = FakeDialogueUI()
    o.emotion_system = types.SimpleNamespace(react_to_event=lambda *a, **k: None)
    o.sound_manager = types.SimpleNamespace(play_splat=lambda: None)
    o.last_interaction_time = 0.0
    o._pos = QPoint(500, launch_y)
    o.pos = lambda: o._pos

    def _move(x, y):
        o._pos = QPoint(x, y)

    o.move = _move
    o._desktop_floor_y = lambda: floor_y
    o._clamp_pos_to_desktop = lambda x, y: (int(x), max(0, min(int(y), floor_y)))
    o._anims = []
    o._once = []

    def _ca(name, force=False):
        o._anims.append(name)
        return True

    def _once_(name, callback=None, restore_to=None):
        o._once.append((name, restore_to))
        o._anims.append(name)
        return True

    o.change_animation = _ca
    o.play_animation_once = _once_
    return o


f = make_fall_stub()
ys = []
for i in range(80):        # 80 tick × 0.033s ≈ 2.6s（斜抛约 1.4s 落地）
    RalseiPet.handle_fall(f, 0.033, time.time())
    ys.append(f.pos().y())
peak_up = min(ys)
check("D1 飞行阶段确实先向上腾空（y 减小）",
      peak_up < 500, "min_y=%d (launch=500)" % peak_up)
check("D2 落地后经历 splat 阶段（不再是空中摔扁）",
      "splat" in f._anims and f._fall_phase in ("splat", "dazed", "recovering"),
      "phase=%s anims=%s" % (f._fall_phase, f._anims[:3]))
check("D3 全程 y 不超过地面线（不会穿到桌面底下）",
      max(ys) <= 700, "max_y=%d" % max(ys))
check("D4 水平方向有位移（抛物线不是垂直落体）",
      f.pos().x() != 500, "x=%d" % f.pos().x())
check("D5 落地后飞行速度被清零（置 0 或已清理）",
      getattr(f, "_fall_vx", 0.0) in (0.0, None) and getattr(f, "_fall_vy", 0.0) in (0.0, None),
      "vx=%r vy=%r" % (getattr(f, "_fall_vx", None), getattr(f, "_fall_vy", None)))

# D6 关键回归：上抛很高时绝不能"空中摔扁"，必须先落回起跳高度
f2 = make_fall_stub()
f2._fall_vx = 0.0
f2._fall_vy = -600.0   # 纯竖直上抛（约 1.2s 才到最高点）
f2._fall_flight_time = 0.0
f2._fall_landed = False
f2._fall_phase_start = 0.0
ys2 = []
phase_at_1s = None
for i in range(120):   # 4 秒
    RalseiPet.handle_fall(f2, 0.033, time.time())
    ys2.append(f2.pos().y())
    if phase_at_1s is None and f2.fall_duration >= 1.0:
        phase_at_1s = f2._fall_phase
check("D6a 飞行 1 秒时**不再**强行切 splat（说明不是空中摔扁）",
      phase_at_1s == "flying", "phase@1s=%s" % phase_at_1s)
check("D6b 最终精确落回起跳高度（落点吸附，无离散多冲）并进入 splat 之后",
      ys2[-1] == 500 and f2._fall_phase in ("splat", "dazed", "recovering"),
      "final_y=%d phase=%s" % (ys2[-1], f2._fall_phase))

check("D6c 落地前的最高点确实高于起跳高度（真抛物线）",
      min(ys2) < 500, "min_y=%d" % min(ys2))

# ============================================================
print("=== E. 一次性动作（'站起身这类的动作播一次就好'）===")
import inspect  # noqa: E402

sig = inspect.signature(RalseiPet.play_animation_once)
check("E1 play_animation_once 支持 restore_to（播完显式切回指定动画）",
      "restore_to" in sig.parameters)

check("E2 摔倒恢复分支用 play_animation_once('land', restore_to='idle')",
      "play_animation_once(\"land\", restore_to=\"idle\")" in MAIN_SRC)

check("E3 跳跃落地也用一次性 land（不再 change_animation 循环重播）",
      MAIN_SRC.count('play_animation_once("land", restore_to="idle")') >= 3)

check("E4 update_bounce 地面改用 _desktop_floor_y（多显示器）",
      "ground_y = self._desktop_floor_y()" in MAIN_SRC)

# ============================================================
print("=== F. 帧率与多显示器夹紧 ===")
cfg = json.loads(io.open(os.path.join(BASE, "config.json"), encoding="utf-8").read())
check("F1 config.json：fps=6 / frame_delay=166",
      cfg.get("animation", {}).get("fps") == 6
      and cfg.get("animation", {}).get("frame_delay") == 166,
      "animation=%s" % cfg.get("animation"))

cm_src = io.open(os.path.join(BASE, "modules", "config_manager.py"), encoding="utf-8").read()
check("F2 config_manager 默认 fps=6（新装用户也是 6 帧）",
      re.search(r'"fps"\s*:\s*6\b', cm_src) is not None
      and re.search(r'"frame_delay"\s*:\s*166\b', cm_src) is not None)

stub = types.SimpleNamespace()
# 模拟"主屏右侧还有一块副屏"：虚拟桌面 3840x1080，原点 0,0
stub._virtual_screen_rect = lambda: QRect(0, 0, 3840, 1080)
stub.width = lambda: 100
stub.height = lambda: 100
x1, y1 = RalseiPet._clamp_pos_to_desktop(stub, 2500, 900)
check("F3 副屏坐标不再被拉回主屏（2500 保持 2500）",
      x1 == 2500 and y1 == 900, "-> (%d,%d)" % (x1, y1))

# 模拟"副屏在主屏左侧"：虚拟桌面原点 -1920
stub2 = types.SimpleNamespace()
stub2._virtual_screen_rect = lambda: QRect(-1920, 0, 3840, 1080)
stub2.width = lambda: 100
stub2.height = lambda: 100
x2, y2 = RalseiPet._clamp_pos_to_desktop(stub2, -1500, 500)
check("F4 负坐标副屏可停留（-1500 保持 -1500）",
      x2 == -1500, "-> (%d,%d)" % (x2, y2))

x3, y3 = RalseiPet._clamp_pos_to_desktop(stub2, -5000, 500)
check("F5 越界仍会被夹回虚拟桌面左边界（-1920）", x3 == -1920, "-> %d" % x3)

check("F6 _desktop_floor_y / _current_screen_rect 均已定义",
      callable(getattr(RalseiPet, "_desktop_floor_y", None))
      and callable(getattr(RalseiPet, "_current_screen_rect", None)))

check("F7 update_movement 里对 dt 做了 0.1s 截断（瞬移防治）",
      "elapsed_time > 0.1" in MAIN_SRC)

# ============================================================
print("\n" + "=" * 60)
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
print("总计 %d 项，通过 %d，失败 %d" % (total, passed, total - passed))
sys.exit(0 if passed == total else 1)

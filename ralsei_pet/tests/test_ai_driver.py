# -*- coding: utf-8 -*-
"""ai_driver 单元测试（无 GUI 依赖，可独立运行：python tests/test_ai_driver.py）

覆盖：extract_json 容错、动作白名单映射、冲突守卫、失败退避、say 冷却。
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from modules.ai_driver import (AiActionDriver, extract_json, ANIMATION_ACTIONS,
                               PASSIVE_ACTIONS, WANDER_ACTIONS)

FAILED = []


def check(name, cond, extra=""):
    if not cond:
        FAILED.append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}  {extra}")


# ---------- extract_json 容错 ----------
check("纯JSON", extract_json('{"action":"dance"}') == {"action": "dance"})
check("围栏JSON", extract_json('```json\n{"action":"sing"}\n```') == {"action": "sing"})
check("前有碎话", extract_json('好的！{"action":"wave"} 这样如何') == {"action": "wave"})
check("后有碎话", extract_json('{"action":"bow"}\n希望你喜欢~') == {"action": "bow"})
check("列表返回None", extract_json('[1,2]') is None)
check("无JSON返回None", extract_json('完全看不懂') is None)
check("None输入", extract_json(None) is None)
check("空串输入", extract_json("") is None)
check("嵌套字符串含花括号",
      extract_json('{"say":"我说 {好} 啊","action":"idle"}') == {"say": "我说 {好} 啊", "action": "idle"})


class FakeDialogue:
    def __init__(self):
        self._ai_inflight = False
        self.is_typing = False
        self.calls = []
        self.visible = False

    def isVisible(self):
        return self.visible

    def show_dialogue(self):
        self.visible = True

    def add_dialogue(self, speaker, msg, face):
        self.calls.append((speaker, msg, face))

    def _is_user_inputting(self):
        return False


class FakeAgent:
    def __init__(self):
        self._last_decision_time = 99.0
        self.busy = False

    def is_busy(self):
        return self.busy


class _FakeSignal:
    def __init__(self, owner):
        self._owner = owner

    def emit(self, text, cb):
        self._owner._emit_cb(text, cb)


class StubOwner:
    def __init__(self):
        self.api_enabled = True
        self.dialogue_ui = FakeDialogue()
        self.game_state = {"is_playing": False}
        self.is_sleeping = False
        self.is_moving = False
        self.is_dragging_mouse = False
        self._is_being_dragged = False
        self.is_following_mouse = False
        self.is_jumping = False
        self.is_falling = False
        self.is_gravity_falling = False
        self.is_recovering = False
        self._spell_stage = None
        self.current_animation = "idle"
        self.autonomous_agent = FakeAgent()
        self.chat_reply = None
        self.evt = threading.Event()
        self.calls = {"anim": [], "sleep": 0, "wake": 0}
        self._api_result = _FakeSignal(self)
        self.energy_hunger = type("E", (), {"get_energy": lambda s: 70,
                                            "get_hunger": lambda s: 40})()
        self.emotion_system = type("Em", (), {"get_current_emotion": lambda s: ("happy", 30)})()
        self.weather_system = type("W", (), {"get_current_weather": lambda s: "晴"})()
        self.pos = lambda: type("P", (), {"x": lambda s: 10, "y": lambda s: 20})()

    def _emit_cb(self, text, cb):
        try:
            cb(text)
        finally:
            self.evt.set()

    @property
    def api_client(self):
        c = type("C", (), {"enabled": True})()
        c.chat = self._chat
        return c

    def _chat(self, prompt, system_prompt=None, **kw):
        return self.chat_reply

    def play_animation_once(self, anim):
        self.calls["anim"].append(anim)
        return True

    def enter_sleep_mode(self):
        self.calls["sleep"] += 1

    def wake_up(self):
        self.calls["wake"] += 1


def fire(drv, owner):
    owner.evt.clear()
    owner.evt.wait(5.0)


# ---------- 动作映射 ----------
o = StubOwner()
d = AiActionDriver(o)
o.chat_reply = '{"action":"dance"}'
d._next_at = 0
d.tick(time.time())
fire(d, o)
check("dance→play_animation_once", o.calls["anim"] == ["dance"])
check("成功不触发退避", d._current_interval == d._base_interval)

o2 = StubOwner()
d2 = AiActionDriver(o2)
o2.chat_reply = '{"action":"sing","say":"给你唱首歌","emotion":"happy"}'
d2._next_at = 0
d2._last_say_at = 0
d2.tick(time.time())
fire(d2, o2)
check("sing+say", o2.calls["anim"] == ["sing"] and
      any(m == "给你唱首歌" for _, m, _ in o2.dialogue_ui.calls))

o3 = StubOwner()
d3 = AiActionDriver(o3)
o3.chat_reply = '{"action":"wander"}'
d3._next_at = 0
d3.tick(time.time())
fire(d3, o3)
check("wander→agent决策", o3.autonomous_agent._last_decision_time == 0.0)

o4 = StubOwner()
o4.is_sleeping = True
d4 = AiActionDriver(o4)
o4.chat_reply = '{"action":"dance"}'
d4._next_at = 0
d4.tick(time.time())
fire(d4, o4)
check("睡觉时不跳舞", o4.calls["anim"] == [])
check("睡觉时被拒→温和退避", d4._current_interval > d4._base_interval)

o5 = StubOwner()
o5.is_sleeping = True
d5 = AiActionDriver(o5)
o5.chat_reply = '{"action":"wake"}'
d5._next_at = 0
d5.tick(time.time())
fire(d5, o5)
check("睡觉中被叫醒", o5.calls["wake"] == 1)

o6 = StubOwner()
d6 = AiActionDriver(o6)
o6.chat_reply = "我不太懂你想让我干嘛……"
d6._next_at = 0
base = d6._current_interval
d6.tick(time.time())
fire(d6, o6)
check("解析失败退避翻倍", d6._current_interval == base * 2.0)

# 未知动作 → 退避
o6b = StubOwner()
d6b = AiActionDriver(o6b)
o6b.chat_reply = '{"action":"delete_system32"}'
d6b._next_at = 0
base = d6b._current_interval
d6b.tick(time.time())
fire(d6b, o6b)
check("未知动作退避", d6b._current_interval > base)

# 关键流程冲突
o7 = StubOwner()
o7.game_state = {"is_playing": True}
d7 = AiActionDriver(o7)
d7._next_at = 0
d7.tick(time.time())
check("游戏中不触发请求", d7._busy is False)

o8 = StubOwner()
o8.dialogue_ui._ai_inflight = True
d8 = AiActionDriver(o8)
d8._next_at = 0
d8.tick(time.time())
check("对话在飞时不触发", not o8.evt.is_set())

# say 冷却
o9 = StubOwner()
d9 = AiActionDriver(o9)
o9.chat_reply = '{"action":"say","say":"第一句话"}'
d9._next_at = 0
d9.tick(time.time())
fire(d9, o9)
first = len(o9.dialogue_ui.calls)
o9.chat_reply = '{"action":"say","say":"第二句话"}'
d9._next_at = 0
d9.tick(time.time())
fire(d9, o9)
check("say冷却生效", len(o9.dialogue_ui.calls) == first)

print("=" * 50)
if FAILED:
    print(f"FAILED: {FAILED}")
    sys.exit(1)
print("ALL PASS")

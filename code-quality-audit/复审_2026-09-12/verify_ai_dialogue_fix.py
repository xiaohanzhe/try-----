# -*- coding: utf-8 -*-
"""pet_ai.py + dialogue_system.py 修复验证（第4区块）"""
import os
import sys
import types

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet", "modules"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)
from PyQt5.QtCore import QPoint

from pet_ai import PetAI
from dialogue_system import DialogueSystem


class FakeEmotion:
    def add_emotion(self, *a, **k):
        pass


class FakeDialogueUI:
    def __init__(self):
        self.calls = []
    def add_dialogue(self, *a, **k):
        self.calls.append(("add_dialogue", a, k))
    def show_dialogue(self, *a, **k):
        self.calls.append(("show_dialogue", a, k))


class FakeParent:
    def __init__(self):
        self.target_pos = QPoint(100, 100)
        self.energy_hunger = types.SimpleNamespace(get_energy=lambda: 80, get_hunger=lambda: 80,
                                                   energy=80, hunger=80)
        self.emotion_system = FakeEmotion()
        self.dialogue_ui = FakeDialogueUI()
        self.dialogue_system = types.SimpleNamespace(
            should_initiate_conversation=lambda: False, initiate_conversation=lambda: "你好")
        self.desktop_interaction = types.SimpleNamespace(
            get_desktop_folders=lambda: [], get_desktop_files=lambda: [])
        self.weather_system = types.SimpleNamespace(
            get_weather_response=lambda: {"dialogue": "晴", "mood": "happy", "animation": "idle"})
        self.current_animation = "idle"
        self.animations = ["dance", "victory", "jump"]
        self._spell_stage = None
        self.game_state = {}
        self._is_being_dragged = False
        self.is_jumping = False
        self.is_falling = False
        self.calls = []

    def change_animation(self, anim, force=False):
        self.calls.append(("change_animation", anim, force))
        self.current_animation = anim


def test_react_unknown_event_no_crash():
    p = FakeParent()
    ai = PetAI(p)
    ai.react_to_event("user_dragged_forcefully", None)  # 原无分支 → 静默
    ai.react_to_event("totally_unknown_event_xyz", {"x": 1})  # 默认分支
    print("[PASS] react_to_event 未知事件/新事件不抛异常")


def test_trigger_event_celebrate_animation():
    p = FakeParent()
    ai = PetAI(p)
    ai.trigger_event('level_up', {'new_level': 3})
    assert ("change_animation", "dance", True) in p.calls, p.calls
    ai.trigger_event('game_start', {'game_name': '躲猫猫'})
    assert ("change_animation", "jump", True) in p.calls, p.calls
    ai.trigger_event('evolution', {'stage': 2})
    assert p.calls.count(("change_animation", "dance", True)) >= 2, p.calls
    print("[PASS] 升级/游戏开始/进化庆祝动画真实触发")


def test_dialogue_question_branch():
    ds = DialogueSystem()
    ds.dialogue_history = [("user", "之前的问题"), ("ralsei", "之前的回答")]
    # 有问号的输入应命中 question 模板
    r1 = ds.generate_response("你今天过得怎么样？")
    q = ds.response_templates["question"]
    assert r1 in q, f"问句未命中 question 模板: {r1!r}"
    # 无问号的输入走随机模板（不崩溃即可）
    r2 = ds.generate_response("今天天气不错")
    assert isinstance(r2, str) and r2.strip()
    print("[PASS] 问句命中 question 模板，普通句正常")


if __name__ == "__main__":
    test_react_unknown_event_no_crash()
    test_trigger_event_celebrate_animation()
    test_dialogue_question_branch()
    print("\n全部通过 ✔")

# -*- coding: utf-8 -*-
"""dialogue_ui 接入本地 AI 的离屏行为测试（回归保护）。

运行：python tests/test_dialogue_ai.py
覆盖：A 未启用→规则 / B 模型不可用→回退规则 / C 思考占位→AI回复且占位
不入历史 / D 并发乱序作废旧回复 / E 非字符串回复不崩溃。
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QWidget

from modules.dialogue_ui import DialogueUI

FAILED = []


def check(name, cond, extra=""):
    if not cond:
        FAILED.append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}  {extra}")


def pump(ms):
    deadline = time.time() + ms / 1000.0
    while time.time() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    QApplication.processEvents()


class StubSprite:
    def get_face(self, name):
        p = QPixmap(64, 64)
        p.fill(Qt.white)
        return p


class StubEmotion:
    def get_current_emotion(self):
        return ("happy", 0.7)

    def get_face_for_emotion(self, e, i):
        return "happy"

    def add_emotion(self, *a, **k):
        pass


class StubDialogue:
    def generate_response(self, text, emotion):
        return "规则回复:" + text


class StubSound:
    def play_typewriter(self):
        pass


class StubParent(QWidget):
    def __init__(self):
        super().__init__()
        self.sprite_loader = StubSprite()
        self.emotion_system = StubEmotion()
        self.dialogue_system = StubDialogue()
        self.sound_manager = StubSound()
        self.api_enabled = False
        self.reply_schedule = []

    def handle_game_input(self, t):
        return False

    def chat_with_ai(self, text, cb):
        if not self.reply_schedule:
            QTimer.singleShot(0, lambda: cb(None))
            return
        delay, reply = self.reply_schedule.pop(0)
        if delay <= 0:
            cb(reply)
        else:
            QTimer.singleShot(delay, lambda: cb(reply))


def new_ui(parent):
    return DialogueUI(parent)


app = QApplication.instance() or QApplication(sys.argv)

# A：未启用 API
pa = StubParent()
ui = new_ui(pa)
ui.input_field.setPlainText("q_rule_abc")
ui.send_message()
check("A_规则回复", ui.typing_text == "规则回复:q_rule_abc")
check("A_无占位残留", "正在想" not in ui._history_html and "正在想" not in ui.typing_text)

# B：启用但模型立即返回 None → 回退规则
pb = StubParent()
pb.api_enabled = True
pb.reply_schedule = [(0, None)]
ui = new_ui(pb)
ui.input_field.setPlainText("q_fallback_xyz")
ui.send_message()
pump(50)
check("B_回退规则回复", ui.typing_text == "规则回复:q_fallback_xyz")
check("B_无占位残留", "正在想" not in ui._history_html)

# C：模型正常回复（延迟 250ms）
pc = StubParent()
pc.api_enabled = True
pc.reply_schedule = [(250, "这是来自本地Ralsei的回复")]
ui = new_ui(pc)
ui.input_field.setPlainText("q_ai_normal_hello")
ui.send_message()
pump(10)
check("C_思考占位显示", ui.typing_text == ui.AI_THINKING_PLACEHOLDER)
check("C_占位不入历史", "……" not in ui._history_html
      and "正在想" not in ui._history_html)
pump(400)
check("C_AI回复显示", ui.typing_text == "这是来自本地Ralsei的回复")
check("C_最终历史无占位", "正在想" not in ui._history_html)

# D：并发乱序（q1 慢 400ms、q2 快 100ms）→ 只显示最新
pd = StubParent()
pd.api_enabled = True
pd.reply_schedule = [(400, "回复一_应被作废"), (100, "回复二_最终显示")]
ui = new_ui(pd)
ui.input_field.setPlainText("q_first_slow")
ui.send_message()
pump(20)
ui.input_field.setPlainText("q_second_fast")
ui.send_message()
pump(700)
check("D_只显示最新回复", ui.typing_text == "回复二_最终显示")
check("D_旧回复被作废", "回复一_应被作废" not in ui._history_html
      and "回复一_应被作废" not in ui.typing_text)
check("D_无占位残留", "正在想" not in ui._history_html)

# E：非字符串回复（类型防御）
pe = StubParent()
pe.api_enabled = True
pe.reply_schedule = [(0, 12345)]
ui = new_ui(pe)
ui.input_field.setPlainText("q_num_reply")
ui.send_message()
pump(50)
check("E_非字符串回复不崩溃", "12345" in ui.typing_text)

print("=" * 50)
if FAILED:
    print(f"FAILED: {len(FAILED)} 项未通过 -> {FAILED}")
    sys.exit(1)
print("ALL PASS")

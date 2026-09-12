# -*- coding: utf-8 -*-
"""对话框修复验证：打字机生效 / HTML 实体不残片 / 滚动条不抢焦点"""
import sys, os, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
os.chdir(tempfile.mkdtemp())
for p in (os.path.join(ROOT,'src'), os.path.join(ROOT,'modules'), ROOT):
    if p not in sys.path: sys.path.insert(0, p)
from PyQt5.QtWidgets import QApplication, QWidget
app = QApplication(sys.argv)
from dialogue_ui import DialogueUI
OUT=[]
def ck(l, c, extra=""):
    OUT.append(("PASS " if c else "FAIL ")+l+(("  "+str(extra)) if extra else ""))

class FakeSprite:
    def has_face(self, n): return True
    def get_face(self, n): return None
class FakeParent(QWidget):
    def __init__(self):
        super().__init__()
        self.sprite_loader = FakeSprite()
        self.sound_manager = None
        self.game_state = {'is_playing': False}
        self.pos = lambda: self.geometry().topLeft()
        self.width = lambda: 100
        self.height = lambda: 100
        self.frameGeometry = lambda: self.geometry()

ui = DialogueUI(FakeParent())
text = "A&B <tag> \"q\" 这是一句足够长的测试台词用来触发打字机效果哦哦哦"
ui.add_dialogue("ralsei", text, "normal")
ck("add_dialogue 后进入打字状态", ui.is_typing is True)
ck("打字索引从 0 开始", ui.typing_index == 0, ui.typing_index)
ui.show_dialogue()
ck("show_dialogue 不再打断打字机（核心修复）", ui.is_typing is True,
   f"is_typing={ui.is_typing} idx={ui.typing_index}/{len(ui.typing_text)}")
# 逐字推进，检查是否出现 HTML 实体残片
frag = None
for i in range(len(text)+3):
    ui._type_next_char()
    shown = ui.dialogue_content.toPlainText()
    if "&am" in shown or "&lt" in shown or "&quot" in shown or "&gt" in shown:
        frag = shown
        break
ck("逐字渲染不出现 HTML 实体残片", frag is None, frag[-30:] if frag else "")
ck("打字完成后文本完整", "A&B <tag>" in ui.dialogue_content.toPlainText())
# 滚到底只在内容增长时发生
sb = ui.dialogue_content.verticalScrollBar()
sb.setValue(0)
ui._blink_cursor()
ck("光标闪烁不再把滚动条强制拉到底（核心修复）", sb.value() == 0, sb.value())
print("\n".join(OUT))
print("FAILED:", sum(1 for o in OUT if o.startswith("FAIL")))

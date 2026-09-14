# -*- coding: utf-8 -*-
"""临时探针：offscreen 下量出对话框各部件的真实几何，用于确定验证断言阈值。"""
import os, sys, io

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
for p in (os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if p not in sys.path:
        sys.path.append(p)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication, QWidget
app = QApplication.instance() or QApplication([])


class FakeLoader:
    def has_face(self, name):
        return False

    def get_face(self, name):
        return None


class FakeEmotion:
    def get_current_emotion(self):
        return ("normal", 0)

    def get_face_for_emotion(self, e, i):
        return "normal"


class FakeParent(QWidget):
    """DialogueUI(parent) 要求 parent 是 QWidget；同时提供它读到的系统属性。"""

    def __init__(self):
        super().__init__()
        self.sprite_loader = FakeLoader()
        self.emotion_system = FakeEmotion()
        self.sound_manager = None


from dialogue_ui import DialogueUI

ui = DialogueUI(FakeParent())
ui.add_dialogue("ralsei", "这是一段用来测试换行与滚动位置的长文本。" * 20)
try:
    ui.stop_typing()
except Exception as e:
    print("stop_typing err:", e)

ui.resize(540, 320)
ui._position_cursor_overlay()

c = ui.dialogue_content
lbl = ui._cursor_label

out = []
out.append("window.size          = %s" % (ui.size(),))
out.append("frame.size           = %s" % (ui._frame.size(),))
out.append("content.geometry     = %s" % (c.geometry(),))
out.append("content.right(in win)= %s" % (c.mapTo(ui, c.rect().topRight()).x(),))
out.append("content.width        = %s" % (c.width(),))
out.append("viewport.width       = %s" % (c.viewport().width(),))
out.append("width - viewport     = %s" % (c.width() - c.viewport().width(),))
out.append("doc.textWidth        = %s" % (c.document().textWidth(),))
out.append("doc.size.height      = %s" % (c.document().size().height(),))
out.append("scrollbar max/value  = %s / %s" % (
    c.verticalScrollBar().maximum(), c.verticalScrollBar().value()))
out.append("cursor_label.geom    = %s" % (lbl.geometry(),))
out.append("cursor_label.hidden  = %s" % (lbl.isHidden(),))
out.append("content_fixed_h      = %s" % (c.height(),))
out.append("toPlainText has ▼    = %s" % ("▼" in c.toPlainText()))

# 文本实际排版宽度（用 QTextDocument 的 idealWidth 近似）
doc = c.document()
doc.setTextWidth(c.viewport().width())
out.append("doc.idealWidth       = %s" % (doc.idealWidth(),))

print("\n".join(out))

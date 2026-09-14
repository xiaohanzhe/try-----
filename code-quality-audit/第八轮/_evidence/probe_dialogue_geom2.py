# -*- coding: utf-8 -*-
"""探针 v2：show() 之后量真实布局几何，确认 ▼ 覆盖层与正文视口的水平间隙。"""
import os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
for p in (os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if p not in sys.path:
        sys.path.append(p)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication, QWidget
app = QApplication.instance() or QApplication([])


class FakeLoader:
    def has_face(self, n):
        return False

    def get_face(self, n):
        return None


class FakeEmotion:
    def get_current_emotion(self):
        return ("normal", 0)

    def get_face_for_emotion(self, e, i):
        return "normal"


class FakeParent(QWidget):
    def __init__(self):
        super().__init__()
        self.sprite_loader = FakeLoader()
        self.emotion_system = FakeEmotion()
        self.sound_manager = None


from dialogue_ui import DialogueUI

ui = DialogueUI(FakeParent())
ui.resize(540, 320)
ui.show()
for _ in range(8):
    app.processEvents()
ui._auto_hide_timer.stop()

ui.add_dialogue("ralsei", "短消息，用于观察几何。")
ui.stop_typing()
ui.typing_text = "有前台消息"
ui.is_typing = False
ui._cursor_visible = True
ui._update_cursor_overlay()
ui._position_cursor_overlay()
for _ in range(6):
    app.processEvents()

c = ui.dialogue_content
vp = c.viewport()
lbl = ui._cursor_label

out = []
out.append("win.size            = %s" % (ui.size(),))
out.append("frame.geometry      = %s" % (ui._frame.geometry(),))
out.append("outer margins       = %s" % (ui.layout().contentsMargins(),))
out.append("frame inner margins = %s" % (ui._frame.layout().contentsMargins(),))
out.append("content.geometry    = %s" % (c.geometry(),))
out.append("content right in win= %s" % (c.mapTo(ui, c.rect().topRight()).x(),))
out.append("viewport.size       = %s" % (vp.size(),))
out.append("viewport right in win= %s" % (vp.mapTo(ui, vp.rect().topRight()).x(),))
out.append("viewport bottom in win=%s" % (vp.mapTo(ui, vp.rect().bottomRight()).y(),))
out.append("lbl.geometry        = %s" % (lbl.geometry(),))
out.append("gap  lbl.x - vp_right = %s" % (lbl.x() - vp.mapTo(ui, vp.rect().topRight()).x(),))
print("\n".join(out))

# -*- coding: utf-8 -*-
"""第162轮 · 交互有没有反应（真窗口 + 真模型在线）。

用户最容易说"有毛病"的形态不是崩溃，是**点了没反应**。本支按右键菜单的
四个入口逐个点一遍，记录：有没有抛异常、对话框有没有出字、出了什么字、
是不是在等 AI（`_ai_pending`）、最终有没有落地。

不判对错，只记录"有没有反馈"。
"""
import os
import sys
import time
import traceback

SANDBOX = r"D:\_tmp\pet162"
os.environ['RALSEI_DATA_DIR'] = r'D:\_tmp\pet162_data'
os.environ.pop('QT_QPA_PLATFORM', None)
sys.path.insert(0, os.path.join(SANDBOX, 'modules'))
sys.path.insert(0, os.path.join(SANDBOX, 'src'))
try:
    import memory_store as _ms
    _ms.find_device_dir = lambda create=True: None
except Exception:
    pass
try:
    import data_store as _ds
    _ds.vault_root = lambda create=True: None
except Exception:
    pass

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QPoint, QEvent
from PyQt5.QtGui import QMouseEvent

app = QApplication(sys.argv)
from main import RalseiPet

w = RalseiPet()
w.show()


def pump(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


pump(3000)

LINES = []
_orig_add = w.dialogue_ui.add_dialogue


def _spy(speaker, message, face_type='normal', _streamed=False):
    LINES.append((speaker, (message or '')[:60]))
    return _orig_add(speaker, message, face_type, _streamed)


w.dialogue_ui.add_dialogue = _spy

CASES = [
    ('聊天 initiate_chat', lambda: w.initiate_chat()),
    ('喂食 feed_ralsei', lambda: w.feed_ralsei()),
    ('抚摸 pet_ralsei', lambda: w.pet_ralsei()),
    ('玩游戏 play_game', lambda: w.play_game()),
]


def run(label, fn, wait_ms=6000):
    before = len(LINES)
    n0 = len(LINES)
    err = None
    t0 = time.time()
    try:
        fn()
    except Exception:
        err = traceback.format_exc()
    pump(wait_ms)
    new = LINES[before:]
    print('\n=== %s ===' % label, flush=True)
    print('  异常: %s' % ('无' if not err else err.strip().splitlines()[-1]), flush=True)
    print('  对话框可见=%s  新台词 %d 条' % (w.dialogue_ui.isVisible(), len(new)), flush=True)
    for sp, tx in new[:4]:
        print('    [%s] %s' % (sp, tx), flush=True)
    print('  anim=%s  ai_pending=%s  耗时 %.1fs' % (
        getattr(w, 'current_animation', '?'),
        getattr(w, '_ai_pending', '?'), time.time() - t0), flush=True)
    if err:
        print(err, flush=True)
    return len(new)


for label, fn in CASES:
    run(label, fn)
    pump(500)

# 双击精灵
print('\n=== 双击精灵 ===', flush=True)
try:
    c = w.sprite_label.geometry().center()
    g = w.mapToGlobal(c)
    for kind in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease,
                 QEvent.MouseButtonDblClick):
        e = QMouseEvent(kind, c, g, Qt.LeftButton,
                        Qt.LeftButton if kind != QEvent.MouseButtonRelease else Qt.NoButton,
                        Qt.NoModifier)
        app.sendEvent(w, e)
        pump(60)
    pump(1500)
    print('  双击后 anim=%s 对话框=%s' % (
        getattr(w, 'current_animation', '?'), w.dialogue_ui.isVisible()), flush=True)
except Exception:
    print('[ERR] 双击: %s' % traceback.format_exc(), flush=True)

try:
    w.cleanup_on_exit()
except Exception:
    pass
app.quit()
print('\n[DONE]', flush=True)

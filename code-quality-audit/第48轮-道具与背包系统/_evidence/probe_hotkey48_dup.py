# -*- coding: utf-8 -*-
"""第48轮 · 精确诊断「一次按键是否被重复派发」（入库版；蒸馏自 `E:\\Download\\_tmp`）。

动机：真机上一次 `PostMessage(WM_HOTKEY)` 实测触发了**两次**回调。
菜单的开关是"取反"，重复一次正好等于**没开**（开了又立刻关）——
这种故障在界面上表现为"按了没反应"，最难往热键上想。
⇒ 本诊断 + 产品侧 `item_menu.TOGGLE_DEBOUNCE_SEC`（0.25s）去抖共同兜住它。

用法（**不要**设 `QT_QPA_PLATFORM=offscreen`）::

    C:\\Python311\\python.exe "code-quality-audit/第48轮-道具与背包系统/_evidence/probe_hotkey48_dup.py"
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(ROUND))
PET = os.path.join(REPO, 'ralsei_pet')

sys.path.insert(0, os.path.join(PET, 'modules'))
sys.path.insert(0, os.path.join(PET, 'src'))
os.chdir(PET)

import ctypes                                       # noqa: E402
import ctypes.wintypes as wt                        # noqa: E402

from PyQt5.QtWidgets import QApplication, QWidget    # noqa: E402

import global_hotkey as G                           # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
w = QWidget()
w.resize(80, 80)
w.show()
app.processEvents()

G.reset_default()
n = [0]


def cb():
    n[0] += 1


done, bad = G.install(w, {'ctrl+alt+s': cb})
print('install done=%s bad=%s hwnd=%s' % (done, bad, int(w.winId())))
print('原生过滤器 =', getattr(w, '_ralsei_hotkey_filter', None))

reg = G.default_registrar()
hid = reg._by_key['ctrl+alt+S']
print('hotkey id =', hid)

u = ctypes.windll.user32
u.PostMessageW(wt.HWND(int(w.winId())), G.WM_HOTKEY, hid, 0)
app.processEvents()
print('第1次投递 + 1次 processEvents ⇒ 回调=%d seen=%d'
      % (n[0], w._ralsei_hotkey_filter.seen))

u.PostMessageW(wt.HWND(int(w.winId())), G.WM_HOTKEY, hid, 0)
for _ in range(10):
    app.processEvents()
print('第2次投递后 ⇒ 回调=%d seen=%d'
      % (n[0], w._ralsei_hotkey_filter.seen))

n2 = [0]
reg.unregister_all()
G.reset_default()
done2, bad2 = G.install(w, {'ctrl+alt+s': lambda: n2.__setitem__(0, n2[0] + 1)})
reg2 = G.default_registrar()
hid2 = reg2._by_key['ctrl+alt+S']
u.PostMessageW(wt.HWND(int(w.winId())), G.WM_HOTKEY, hid2, 0)
for _ in range(5):
    app.processEvents()
print('换一份登记表后重新装 ⇒ 回调=%d（若=1，说明之前是"两份登记表都装过过滤器"）' % n2[0])
reg2.unregister_all()
w.close()

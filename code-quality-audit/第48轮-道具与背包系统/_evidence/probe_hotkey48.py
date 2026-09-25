# -*- coding: utf-8 -*-
"""第48轮 · **真实平台**下验证全局热键全链路（入库版；蒸馏自 `E:\\Download\\_tmp`）。

★ 为什么必须用真实平台跑一遍：
  离屏平台（`offscreen`）的 `winId()` 是**假句柄**（实测 = 1），
  `RegisterHotKey(hwnd=1)` 必然失败 —— 那是**平台假象**，不是产品缺陷。
  但也**不能**因为"我猜真机能行"就下结论（那正是本项目最贵的坑）。
⇒ 这里用**真实 windows 平台 + 真窗口**，把整条链路走完：
      建窗口 → `install()` → 真注册 → `PostMessage(WM_HOTKEY)` → Qt 原生事件过滤器 → 回调

用法（**不要**设 `QT_QPA_PLATFORM=offscreen`）::

    C:\\Python311\\python.exe "code-quality-audit/第48轮-道具与背包系统/_evidence/probe_hotkey48.py"
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
import ctypes.wintypes as wintypes                   # noqa: E402

from PyQt5.QtWidgets import QApplication, QWidget     # noqa: E402

import global_hotkey as G                            # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
FAIL = []


def check(name, cond, extra=''):
    print('%-46s %s %s' % (name, 'PASS' if cond else 'FAIL', extra))
    if not cond:
        FAIL.append(name)


w = QWidget()
w.resize(120, 120)
w.show()
app.processEvents()
hwnd = int(w.winId())
print('平台 =', app.platformName(), ' winId =', hwnd)
check('真实平台的 winId 不是假句柄', hwnd > 1, hwnd)

G.reset_default()
fired = []
done, bad = G.install(w, {'ctrl+alt+s': lambda: fired.append('menu'),
                          'ctrl+alt+e': lambda: fired.append('interact')})
print('install → done=%s bad=%s' % (done, bad))
check('★ 两个全局热键都真注册上了', len(done) == 2 and not bad, (done, bad))

reg = G.default_registrar()
ids = dict(reg._by_key)
print('已注册 id:', ids)

# 真投递 WM_HOTKEY（模拟系统按键）——验证"派发链"而不只是"注册成功"
u = ctypes.windll.user32
for name, expect in (('ctrl+alt+S', 'menu'), ('ctrl+alt+E', 'interact')):
    hid = ids.get(name)
    if hid is None:
        check('有 id：%s' % name, False)
        continue
    u.PostMessageW(wintypes.HWND(hwnd), G.WM_HOTKEY, hid, 0)
    for _ in range(20):
        app.processEvents()
    check('★ WM_HOTKEY 投递 → 回调 %s' % expect, fired and fired[-1] == expect, fired)

check('热键过滤器收到了消息', getattr(w, '_ralsei_hotkey_filter', None) is not None
      and w._ralsei_hotkey_filter.seen >= 2,
      getattr(getattr(w, '_ralsei_hotkey_filter', None), 'seen', None))

n = reg.unregister_all()
check('注销干净', n == 2 and not reg.registered, (n, reg.registered))

w.close()
app.processEvents()
print()
print('FAIL =', FAIL)

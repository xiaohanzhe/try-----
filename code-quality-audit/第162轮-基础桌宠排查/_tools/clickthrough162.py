# -*- coding: utf-8 -*-
"""第162轮 · 透明像素会不会挡住鼠标（点穿测试）。

宠物窗口是 `FramelessWindowHint|Tool` + `WA_TranslucentBackground`，窗口矩形
往往比精灵大一圈（实测 229x156 里精灵只占中间）。如果窗口没做命中裁剪，
用户在**看起来是桌面**的那圈透明区点一下，点到的其实是桌宠 ——
表现为"桌面图标点不动 / 拖选断掉"。

判据（客观、不看感觉）：
  1. 用 `QWidget.grab()` 拿到宠物自己画出来的图，找 alpha==0 的像素；
  2. 该像素换算成屏幕坐标，调 Win32 `WindowFromPoint`；
  3. 返回的是宠物自己的 hwnd ⇒ 透明处**挡住**了点击；否则算穿透。
正负成对：同一个窗口里 alpha>200 的像素必须**命中**自己（否则说明探针本身坏了）。
"""
import os
import sys
import time
import ctypes
import ctypes.wintypes as wt

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
from PyQt5.QtCore import QPoint

app = QApplication(sys.argv)
from main import RalseiPet

user32 = ctypes.windll.user32


class _PT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


# ★ ctypes.windll.user32 的属性每次访问都新建一个 _FuncPtr，argtypes 设上去等于
#   设给了临时对象（第162轮实测：报 "expected POINT instance instead of _PT"）。
#   必须先把函数对象绑定到局部变量，再设签名。
_WF = user32.WindowFromPoint
_WF.argtypes = [_PT]
_WF.restype = wt.HWND
_GA = user32.GetAncestor
_GA.argtypes = [wt.HWND, ctypes.c_uint]
_GA.restype = wt.HWND
GA_ROOT = 2


def root_of(h):
    # 产品代码也用同一个 windll 缓存对象，它会按自己的口径改 argtypes
    # （实测被改成 `wt.POINT`）⇒ 每次调用前重设签名，别依赖"我设过一次"。
    _GA.argtypes = [wt.HWND, ctypes.c_uint]
    _GA.restype = wt.HWND
    return _GA(h, GA_ROOT) or h


w = RalseiPet()
w.show()
end = time.time() + 3
while time.time() < end:
    app.processEvents()
    time.sleep(0.01)

hwnd = int(w.winId())
print('[WIN] hwnd=0x%x pos=%s size=%dx%d' % (hwnd, w.pos(), w.width(), w.height()), flush=True)

pix = w.grab().toImage()
W, H = pix.width(), pix.height()
print('[IMG] grab = %dx%d' % (W, H), flush=True)

transparent = []
opaque = []
for y in range(0, H, 3):
    for x in range(0, W, 3):
        a = pix.pixelColor(x, y).alpha()
        if a == 0 and len(transparent) < 60:
            transparent.append((x, y))
        elif a > 200 and len(opaque) < 60:
            opaque.append((x, y))

print('[IMG] 采样：透明 %d 个 / 不透明 %d 个' % (len(transparent), len(opaque)), flush=True)


def hit(x, y):
    g = w.mapToGlobal(QPoint(x, y))
    _WF.argtypes = [wt.POINT]
    _WF.restype = wt.HWND
    h = _WF(wt.POINT(g.x(), g.y()))
    return int(h or 0), root_of(h) if h else 0


def stats(points, label):
    if not points:
        print('[HIT %s] 无样本' % label, flush=True)
        return
    hit_self = 0
    others = {}
    for (x, y) in points:
        h, r = hit(x, y)
        if r == hwnd:
            hit_self += 1
        else:
            others[h] = others.get(h, 0) + 1
    print('[HIT %s] 命中自己 %d/%d = %.0f%%   其他窗口 %s' % (
        label, hit_self, len(points), 100.0 * hit_self / len(points),
        [(hex(k), v) for k, v in list(others.items())[:4]]), flush=True)


stats(transparent, '透明')
stats(opaque, '不透明')

try:
    w.cleanup_on_exit()
except Exception:
    pass
app.quit()
print('[DONE]', flush=True)

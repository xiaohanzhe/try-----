# -*- coding: utf-8 -*-
"""第94轮 · 透明留白命中测试：窗口的透明区域会不会吞掉桌面点击？

背景：`idle`/`defend`/`victory`/`spell` 用的是**原作战斗立绘**（画布 69x47，
带大量透明留白 ⇒ 窗口 138x94），而 `walk_*`/`run_*` 是行走图（19x40 ⇒ 38x80）。
若 Qt 分层窗口不做逐像素命中，则离 Ralsei 四十多像素的空白处也会被宠物窗口吃掉
⇒ 用户点不到底下的桌面图标/窗口。这是**基础可用性**问题。

判据：
  · `WindowFromPoint(角色不透明像素)` 返回宠物 hwnd（正控制：证明测试有效）；
  · `WindowFromPoint(窗口内纯透明留白)` 若也返回宠物 hwnd ⇒ 吞点击（真问题）；
  · 同时读 hwnd 的 WS_EX_* 与 `QWidget.mask()`，给出机制解释。
"""
import ctypes
import io
import os
import sys
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'ralsei_pet')
for _p in (os.path.join(SRC, 'src'), SRC, os.path.join(SRC, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

EVID = os.path.join(ROOT, 'code-quality-audit', '第94轮-基础宠物真机全功能验收', '_evidence')
OUT = os.path.join(EVID, 'probe94_hittest.txt')
_buf = []


def w(s=''):
    _buf.append(str(s))
    try:
        print(s, flush=True)
    except Exception:
        pass
    try:
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(_buf))
    except Exception:
        pass


from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QPoint, QRect
from PyQt5.QtGui import QRegion


class P(ctypes.Structure):
    """自定义 POINT：绕开 `ctypes.wintypes.POINT` 在本机的类型解析冲突。"""
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


u = ctypes.windll.user32
# ★ 不要用 `u.WindowFromPoint.argtypes = [...]`：实测该函数对象的 argtypes
#   已被进程内其它库设置成 `ctypes.wintypes.POINT`，我们的赋值被"无名 POINT"顶掉，
#   于是报 `expected POINT instance instead of P`（同名不同类型）。
#   改用 `WINFUNCTYPE` **新建**一个函数对象 ⇒ 自带原型，不受外部 argtypes 影响。
_WFP_PROTO = ctypes.WINFUNCTYPE(ctypes.c_void_p, P)
_WFP = _WFP_PROTO(('WindowFromPoint', u))
u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
u.GetWindowLongW.restype = ctypes.c_long
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


def wfp(x, y):
    h = _WFP(P(int(x), int(y)))
    return int(h) if h else 0


def flagnames(v):
    out = []
    for nm, bit in (('TRANSPARENT', WS_EX_TRANSPARENT), ('LAYERED', WS_EX_LAYERED),
                    ('TOOLWINDOW', WS_EX_TOOLWINDOW), ('NOACTIVATE', WS_EX_NOACTIVATE)):
        if v & bit:
            out.append(nm)
    return '+'.join(out) if out else '(none)'


app = QApplication.instance() or QApplication(sys.argv)
import main as main_mod

p = main_mod.RalseiPet()
app.processEvents()
if not p.isVisible():
    p.show()
app.processEvents()

w('=== 第94轮 透明留白命中测试 ===')
w('时间 = %s' % time.strftime('%Y-%m-%d %H:%M:%S'))

g = app.primaryScreen().availableGeometry()
p.move(g.center().x() - p.width() // 2, g.center().y() - p.height() // 2)
for _ in range(20):
    app.processEvents()
    time.sleep(0.02)

results = {}
for anim in ('pose', 'idle'):
    # ★ 必须先冻住自主移动：否则 `update_animation` 的 `is_moving` 分支会一直选
    #   `walk_*`，`change_animation(anim, force=True)` 下一拍就被顶掉（上一轮实测到了）。
    for _ in range(20):
        p.is_moving = False
        p.is_following_mouse = False
        p.is_sleeping = False
        try:
            p.change_animation(anim, force=True)
        except Exception as e:
            w('切 %r 失败：%r' % (anim, e))
            break
        app.processEvents()
        time.sleep(0.02)
    p.is_moving = False
    p.stop_following_mouse(announce=False)
    for _ in range(10):
        p.is_moving = False
        app.processEvents()
        time.sleep(0.02)

    hwnd = int(p.winId())
    ex = u.GetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE) & 0xFFFFFFFF
    w()
    w('---- anim=%r  hwnd=%d  size=%dx%d  pos=(%d,%d) ----'
      % (p.current_animation, hwnd, p.width(), p.height(), p.x(), p.y()))
    w('  WS_EX = 0x%08X [%s]' % (ex, flagnames(ex)))
    try:
        rg = p.mask()
        br = rg.boundingRect()
        w('  QWidget.mask(): isEmpty=%r  boundingRect=%r  rectCount=%d'
          % (rg.isEmpty(), (br.x(), br.y(), br.width(), br.height()), rg.rectCount()))
    except Exception as e:
        w('  mask() 读失败：%r' % e)
        rg = None

    cx, cy = p.x() + p.width() // 2, p.y() + p.height() // 2
    pts = [
        ('角色中心', cx, cy),
        ('窗口内左边缘+4', p.x() + 4, cy),
        ('窗口内右边缘-5', p.x() + p.width() - 5, cy),
        ('窗口内顶部+3', cx, p.y() + 3),
        ('窗口内底部-4', cx, p.y() + p.height() - 4),
        ('窗口外左侧 20', p.x() - 20, cy),
    ]
    pm = p.sprite_label.pixmap()
    img = pm.toImage() if (pm is not None and not pm.isNull()) else None
    w()
    w('  %-18s %-14s %-14s %-8s %-8s %s'
      % ('采样点', '屏幕坐标', 'WindowFromPoint', '=宠物?', 'mask含?', 'alpha'))
    swallow = 0
    for nm, x, y in pts:
        h = wfp(x, y)
        is_pet = (h == hwnd)
        in_mask = 'n/a'
        if rg is not None:
            # 注意：mask 是**窗口局部**坐标 ⇒ 用窗口内坐标判定
            in_mask = '是' if rg.contains(QPoint(x - p.x(), y - p.y())) else '否'
        alpha = 'n/a'
        if img is not None:
            lx, ly = x - p.x(), y - p.y()
            if 0 <= lx < img.width() and 0 <= ly < img.height():
                alpha = img.pixelColor(lx, ly).alpha()
        inside_window = (p.x() <= x < p.x() + p.width()
                         and p.y() <= y < p.y() + p.height())
        if is_pet and inside_window and str(alpha) == '0':
            swallow += 1
        w('  %-18s (%5d,%5d)   %-14s %-8s %-8s %s'
          % (nm, x, y,
             ('宠物' if is_pet else str(h)),
             '是' if is_pet else '否', in_mask, alpha))
    w()
    w('  anim=%r：窗口内**纯透明**采样点被宠物窗口吃掉 = %d 个' % (p.current_animation, swallow))
    results[anim] = (p.width(), p.height(), ex, swallow,
                     (p.mask().rectCount() if rg is not None else -1))

w()
w('=== 汇总裁决 ===')
for k, v in results.items():
    w('  %-6s size=%dx%d WS_EX=0x%08X 吞透明点击=%d mask.rectCount=%s'
      % (k, v[0], v[1], v[2], v[3], v[4]))
try:
    p.close()
except Exception:
    pass
os._exit(0)

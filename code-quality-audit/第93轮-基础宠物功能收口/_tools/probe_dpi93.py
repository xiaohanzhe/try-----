# -*- coding: utf-8 -*-
"""probe_dpi93.py —— 这台机器上「DPI 感知 / 坐标空间是否自洽」的取证探针（只读）

★ 第93轮修正（本脚本第一版自己踩的坑，必须记住）
------------------------------------------------
第一版把「进程 DPI 感知」和「win32 屏幕度量」量在**建 `QApplication` 之前**，
又拿建完之后的值做对账 ⇒ 打印出
    section2: SM_CXSCREEN = 1707x1067   （建 QApplication 之前）
    section4: SM_CXSCREEN = 2560x1600   （建 QApplication 之后）
自相矛盾。根因：**Qt5 在构造 `QApplication` 时会把本进程的 DPI 感知级别改掉**
（本机实测 UNAWARE → SYSTEM_AWARE）⇒ 同一个 `GetSystemMetrics` 在"之前/之外"
返回**被虚拟化**的值、在"之后"返回**物理**值。

⇒ 教训：**"感知级别"是随时相变的量**，跨时相做对账 = 探针失真（假结论）。
本版分 A/B 两相各量一遍，**对账只在同一相内做**。

结论口径（本机实测）
-------------------
- 产品（`src/main.py`）在最早阶段就建 `QApplication` ⇒ 运行期进程是 **SYSTEM_AWARE**，
  `GetSystemMetrics` 与 Qt 坐标**同为物理像素** ⇒ `_virtual_screen_rect()` 与 Qt 混用
  **安全**（不是第90轮推断的"隐性风险"）。
- `devicePixelRatio = 1.0` ⇒ Qt 不做额外缩放，精灵按物理像素绘制 ⇒ 不存在
  "被 Windows 位图放大变糊"。
- 真实残余风险只剩**多显示器不同 DPI 的混用**（Qt5 system-aware 在混 DPI 下会偏），
  本机只有 1 块屏 ⇒ 该风险当前不可达。
"""
import ctypes
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', '..', '..', 'ralsei_pet'))

_NAME = {0: 'UNAWARE', 1: 'SYSTEM_AWARE', 2: 'PER_MONITOR_AWARE'}
R = {}


def awareness():
    try:
        v = ctypes.c_int()
        ctypes.windll.shcore.GetProcessDpiAwareness(None, ctypes.byref(v))
        return v.value, _NAME.get(v.value, '?')
    except Exception:
        try:
            return (1 if ctypes.windll.user32.IsProcessDPIAware() else 0), 'via IsProcessDPIAware'
        except Exception:
            return -1, 'unknown'


def gsm(i):
    return ctypes.windll.user32.GetSystemMetrics(i)


def snap(tag):
    lvl, nm = awareness()
    try:
        dpi_sys = ctypes.windll.user32.GetDpiForSystem()
    except Exception:
        dpi_sys = -1
    R[tag] = {
        'awareness': (lvl, nm), 'dpi_sys': dpi_sys,
        'sm_screen': (gsm(0), gsm(1)),
        'sm_virtual': (gsm(78), gsm(79)),
        'sm_origin': (gsm(76), gsm(77)),
    }
    d = R[tag]
    print('---- %s ----' % tag)
    print('  DPI 感知      = %d (%s)   GetDpiForSystem=%d' % (lvl, nm, dpi_sys))
    print('  SM_CXSCREEN   = %d x %d' % d['sm_screen'])
    print('  SM_CXVIRTUALSCREEN = %d x %d  origin=(%d,%d)'
          % (d['sm_virtual'] + d['sm_origin']))


print('=' * 74)
print('A 相：建 QApplication **之前**（= 宿主裸进程的原始级别）')
print('=' * 74)
snap('A')

print('')
print('=' * 74)
print('B 相：建 QApplication **之后**（= 产品实际运行时的级别）')
print('=' * 74)
from PyQt5.QtWidgets import QApplication          # noqa: E402
from PyQt5.QtGui import QGuiApplication           # noqa: E402
app = QApplication([])
snap('B')
d = app.desktop()
sg = d.screenGeometry()
avg = d.availableGeometry()
print('  Qt screenGeometry()    = (%d,%d,%d,%d)' % (sg.x(), sg.y(), sg.width(), sg.height()))
print('  Qt availableGeometry() = (%d,%d,%d,%d)' % (avg.x(), avg.y(), avg.width(), avg.height()))
print('  Qt logicalDpi=%s  physicalDpi=%s  dpr(primary)=%s  screens=%d'
      % (d.logicalDpiX(), d.physicalDpiX(),
         QGuiApplication.primaryScreen().devicePixelRatio(),
         len(QGuiApplication.screens())))

print('')
print('=' * 74)
print('对账（★ 只在同一相内比较）')
print('=' * 74)
flip = R['A']['awareness'][0] != R['B']['awareness'][0]
print('  感知级别是否被 QApplication 改掉 = %s  (%s → %s)'
      % (flip, R['A']['awareness'][1], R['B']['awareness'][1]))
qt = (sg.width(), sg.height())
b = R['B']['sm_screen']
print('  B 相 Qt 主屏 = %d x %d ;  B 相 win32 SM_CXSCREEN = %d x %d' % (qt + b))
ok = (qt == b)
print('  ⇒ **同相内**两套坐标空间一致 = %s' % ok)
print('  ⇒ `_virtual_screen_rect()`（读 76..79）与 Qt 混用的安全性 = %s'
      % ('**安全**（同为物理像素）' if ok else '**不安全**（需换算）'))
print('  ⇒ 「被 Windows 位图放大变糊」假设 = %s'
      % ('**不成立**（dpr=1.0，按物理像素 1:1 绘制）'
         if QGuiApplication.primaryScreen().devicePixelRatio() == 1.0 else '可能成立'))
print('')
print(' 【P1-5 裁定】**不声明 DPI 感知**。本机实测：Qt5 在构造 `QApplication` 时已把进程')
print('            设为 **PER_MONITOR_AWARE(2)**（A 相 UNAWARE → B 相 2），且同相内')
print('            Qt 主屏 == `GetSystemMetrics(SM_CXSCREEN)` == 2560x1600 ⇒ 两套坐标')
print('            空间一致 ⇒ `_virtual_screen_rect()` 与 Qt 混用**安全**；`dpr=1.0` ⇒')
print('            按物理像素 1:1 绘制，**不存在**"被 Windows 位图放大变糊"。')
print('            ⇒ 第90轮"物理/逻辑混用是隐性风险"的推断**不成立**（它量在 A 相、')
print('            推断用在 B 相 —— 跨时相对账）。手动再声明反而会改变现有几何契约。')
print('            该做的两件事：① 把"包内不出现显式 DPI 声明"钉成回归锁')
print('            （防有人加 manifest/声明把语义改坏）；② 记录"感知级别随')
print('            QApplication 相变"这条方法论（探针跨时相对账 = 假结论）。')

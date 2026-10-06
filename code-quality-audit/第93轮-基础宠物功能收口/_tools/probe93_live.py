# -*- coding: utf-8 -*-
"""第93轮 · 真机验收（1/2）：**首帧落点**与窗口存在性。

为什么单独做这一步：
  P1-4 的判据是「桌面右下角那块屏的**工作区**」，而不是「整屏」。两者在单屏上差一个
  任务栏高度（本机 72px）。只做离屏断言看不出这个差别 —— 必须真机量：
    · 旧逻辑（整屏）= (screen.right-150, screen.bottom-150)
    · 新逻辑（工作区）= (work.right-150,  work.bottom-150)
  本机 2560x1600 ⇒ 两者分别是 y=1450 与 y=1378（差 72）。观测到的**首个**位置落在哪一侧，
  就是这一条改动的真机判据。

纪律：
  · **先声明 DPI 感知**再枚举/取几何（铁律：量桌宠/浮层必须先声明 DPI 感知）。
  · 宠物是 Qt.Tool 不置顶 ⇒ 用 `IsWindowVisible` 判存在，不用截图面积。
  · 宠物会自己走 ⇒ 取「首次出现」的坐标作为首帧代理，并连续采样看漂移。
"""
import ctypes
import sys
import time
from ctypes import wintypes

# ---------- ① 先声明 DPI 感知（必须在任何几何调用之前） ----------
_u = ctypes.WinDLL("user32")
_shcore = None
try:
    _shcore = ctypes.WinDLL("shcore")
except OSError:
    pass

DPI_MODE = "n/a"
try:
    # -4 = PER_MONITOR_AWARE_V2；Win10 1703+
    if _u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
        DPI_MODE = "PER_MONITOR_AWARE_V2"
except Exception:
    pass
if DPI_MODE == "n/a":
    try:
        if _shcore and _shcore.SetProcessDpiAwareness(2) == 0:
            DPI_MODE = "PER_MONITOR_AWARE"
    except Exception:
        pass
if DPI_MODE == "n/a":
    try:
        if _u.SetProcessDPIAware():
            DPI_MODE = "SYSTEM_AWARE"
    except Exception:
        pass

DURATION_MS = int(sys.argv[1]) if len(sys.argv) > 1 else 20000


def rect_of(h):
    r = wintypes.RECT()
    _u.GetWindowRect(wintypes.HWND(h), ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def work_area():
    r = wintypes.RECT()
    _u.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)  # SPI_GETWORKAREA
    return r.left, r.top, r.right, r.bottom


def px(m):
    return _u.GetSystemMetrics(m)


def flags(h):
    GWL_STYLE, GWL_EXSTYLE = -16, -20
    st = _u.GetWindowLongW(wintypes.HWND(h), GWL_STYLE)
    ex = _u.GetWindowLongW(wintypes.HWND(h), GWL_EXSTYLE)
    WS_POPUP = 0x80000000
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_LAYERED = 0x00080000
    WS_EX_TOPMOST = 0x00000008
    return {
        "popup": bool(st & WS_POPUP),
        "tool": bool(ex & WS_EX_TOOLWINDOW),
        "layered": bool(ex & WS_EX_LAYERED),
        "topmost": bool(ex & WS_EX_TOPMOST),
    }


CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
_u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_u.GetWindowTextW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
_u.GetClassNameW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]


def snapshot():
    """返回 [(hwnd, l, t, w, h, visible, title, cls)]."""
    out = []

    def cb(h, _l):
        r = wintypes.RECT()
        _u.GetWindowRect(h, ctypes.byref(r))
        w, hh = r.right - r.left, r.bottom - r.top
        if w <= 0 or hh <= 0:
            return True
        n = _u.GetWindowTextLengthW(h)
        b = ctypes.create_unicode_buffer(n + 2)
        _u.GetWindowTextW(h, b, n + 2)
        c = ctypes.create_unicode_buffer(256)
        _u.GetClassNameW(h, c, 256)
        out.append((int(h), r.left, r.top, w, hh, bool(_u.IsWindowVisible(h)), b.value, c.value))
        return True

    _u.EnumWindows(CB(cb), 0)
    return out


def is_pet_body(w, h):
    """形状判据（第91轮定案）：高 > 宽，且落在 18..90 × 38..120 —— 否则会抓到对话框 620x255。"""
    return h > w and 18 <= w <= 90 and 38 <= h <= 120


wl, wt, wr, wb = work_area()
vsx, vsy = px(76), px(77)
vw, vh = px(78), px(79)
scr_w, scr_h = px(0), px(1)

print("=== 环境 ===")
print("DPI 感知声明 =", DPI_MODE)
print("工作区   (SPI_GETWORKAREA) = (%d,%d)-(%d,%d)  %dx%d" % (wl, wt, wr, wb, wr - wl, wb - wt))
print("主屏     (SM_CXSCREEN)     = %dx%d" % (scr_w, scr_h))
print("虚拟桌面 (SM_*VIRTUALSCREEN)= (%d,%d) %dx%d" % (vsx, vsy, vw, vh))
print("任务栏高度(推算)           = %d px" % (scr_h - (wb - wt)))
print()
new_expected = (wr - 150, wb - 150)
old_expected = (scr_w - 150, scr_h - 150)
print("=== 判据 ===")
print("新逻辑（工作区右下角）期望首帧 = %s" % (new_expected,))
print("旧逻辑（整屏  右下角）期望首帧 = %s" % (old_expected,))
print()

t0 = time.time()
first = None
samples = []
while (time.time() - t0) * 1000 < DURATION_MS:
    for it in snapshot():
        hwnd, l, t, w, h, vis, title, cls = it
        if not is_pet_body(w, h):
            continue
        if first is None:
            first = (hwnd, l, t, w, h, vis, title, cls, (time.time() - t0) * 1000)
        if hwnd == first[0]:
            samples.append((round((time.time() - t0) * 1000), l, t, w, h, vis))
    if first is not None and len(samples) >= 1:
        time.sleep(0.2)
    else:
        time.sleep(0.05)

print("=== 观测 ===")
if first is None:
    print("[FAIL] 在 %.1fs 内没有找到符合形状判据的宠物本体窗口" % (DURATION_MS / 1000.0))
    sys.exit(2)

hwnd, l, t, w, h, vis, title, cls, ms = first
print("宠物本体首次出现：hwnd=%d  rect=(%d,%d,%d,%d)  visible=%s  t=%.0fms" % (hwnd, l, t, w, h, vis, ms))
print("  title=%r  class=%r  flags=%s" % (title, cls, flags(hwnd)))
d_new = (l - new_expected[0], t - new_expected[1])
d_old = (l - old_expected[0], t - old_expected[1])
print("  与新逻辑（工作区）差 = %s" % (d_new,))
print("  与旧逻辑（整屏  ）差 = %s" % (d_old,))
verdict = "新逻辑（工作区）" if abs(d_new[0]) + abs(d_new[1]) < abs(d_old[0]) + abs(d_old[1]) else "旧逻辑（整屏）"
print("  ⇒ 首帧落点判定 = **%s**" % verdict)

# —— 同一进程的**全部**顶层窗口（找到本体的那一刻）——
_dp = wintypes.DWORD()
_u.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(_dp))
PID = _dp.value
print()
print("=== 该进程(pid=%d)的全部顶层窗口（t=%.0fms 快照）===" % (PID, ms))
print("%10s %6s %6s %5s %5s %8s %-28s %s" % ("hwnd", "left", "top", "w", "h", "visible", "class", "title"))
for it in snapshot():
    hh, ll, tt, ww, hh2, vv, ti, cl = it
    d2 = wintypes.DWORD()
    _u.GetWindowThreadProcessId(wintypes.HWND(hh), ctypes.byref(d2))
    if d2.value != PID:
        continue
    mark = "  <== 与『新逻辑期望』重合" if abs(ll - new_expected[0]) <= 3 and abs(tt - new_expected[1]) <= 3 else ""
    mark = mark or ("  <== 与『旧逻辑期望』重合" if abs(ll - old_expected[0]) <= 3 and abs(tt - old_expected[1]) <= 3 else "")
    print("%10d %6d %6d %5d %5d %8s %-28s %s%s" % (hh, ll, tt, ww, hh2, vv, cl, ti, mark))

print()
print("=== 采样（宠物是否真的在动 / 是否被任务栏压住） ===")
print("%8s %6s %6s %5s %5s %8s" % ("t_ms", "left", "top", "w", "h", "visible"))
for s in samples[:40]:
    print("%8d %6d %6d %5d %5d %8s" % s)
if len(samples) > 1:
    xs = [s[1] for s in samples]
    ys = [s[2] for s in samples]
    print("移动量：dx=%d  dy=%d  （采样 %d 次 / %.1fs）" % (max(xs) - min(xs), max(ys) - min(ys),
                                                       len(samples), (samples[-1][0] - samples[0][0]) / 1000.0))
    under = [s for s in samples if s[2] + s[4] > wb]
    print("压在任务栏下方的采样数 = %d / %d" % (len(under), len(samples)))
print()
print("[DONE]")

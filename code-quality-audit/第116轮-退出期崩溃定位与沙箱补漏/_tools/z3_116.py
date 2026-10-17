# -*- coding: utf-8 -*-
u"""z3_116.py —— **负控制**：不启动桌宠，只枚举顶层 z 序 4 秒。

为什么必须先做这一步（本项目的"负控制"纪律）
--------------------------------------------
`z2_116.py` 看到 z 序列表头部有 `ThumbnailDeviceHelperWnd` ×2 与
`ForegroundStaging` ×2 —— 这是 Windows **前台切换机制**正在活动的迹象，
而本会话跑在 Agent 沙箱里（旁边有 IDE 窗口 `Trae CN`、宿主窗口）。
⇒ 必须先回答：**"任务栏反复置顶"到底是不是我们的桌宠引起的？**

判据
----
  · 本脚本（**完全不起桌宠**）若同样看到任务栏名次 313↔4 高频翻
    ⇒ **环境噪声**，与桌宠无关 ⇒ 上一轮把 `raise_()` 改掉并不能治它，
      用户看到的"闪"必须换一个解释/治法（或至少不能声称"修好了"）。
  · 若本脚本里任务栏名次恒定 ⇒ 是桌宠侧引起 ⇒ 继续沿着 `raise_()` 那条线查。
"""
import ctypes
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROUND, '_evidence', 'rec116')
os.makedirs(OUT, exist_ok=True)
SECS = float(os.environ.get('Z3_SECS') or '4')

U32 = ctypes.windll.user32
U32.EnumWindows.restype = ctypes.c_bool
PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
U32.EnumWindows.argtypes = [PROC, ctypes.c_void_p]
U32.FindWindowW.restype = ctypes.c_void_p
U32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
U32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]

TB = int(U32.FindWindowW(u'Shell_TrayWnd', None) or 0)


def cls(h):
    buf = ctypes.create_unicode_buffer(256)
    U32.GetClassNameW(ctypes.c_void_p(h), buf, 256)
    return buf.value


def order():
    out = []

    def _cb(h, lp):
        out.append(int(h))
        return True
    U32.EnumWindows(PROC(_cb), None)
    return out


S = []
t0 = time.perf_counter()
while time.perf_counter() - t0 < SECS:
    o = order()
    S.append((round(time.perf_counter() - t0, 3),
              o.index(TB) if TB in o else -1, [cls(h) for h in o[:6]]))
    time.sleep(0.025)

rep = [u'# z3_116 —— 负控制（**不起桌宠**）']
rep.append(u'任务栏 hwnd=%d  采样 %d 次 / %.2f s' % (TB, len(S), S[-1][0]))
v = [s[1] for s in S]
rep.append(u'任务栏 z 名次 取值集合 = %s' % (sorted(set(v))[:12],))
fl = sum(1 for i in range(1, len(v)) if v[i] != v[i - 1])
rep.append(u'名次变化次数 = %d ⇒ %.2f Hz' % (fl, fl / max(1e-9, S[-1][0])))
rep.append(u'')
rep.append(u'前 16 个采样（t, taskbar_z, head6）:')
for t, z, h in S[:16]:
    rep.append(u'  t=%.3f tb_z=%d head=%r' % (t, z, h))
txt = u'\n'.join(rep) + u'\n'
with io.open(os.path.join(OUT, 'z3_116.txt'), 'w',
             encoding='utf-8', newline='\n') as fh:
    fh.write(txt)
sys.stdout.write(txt.encode('utf-8', 'replace').decode('utf-8', 'replace'))

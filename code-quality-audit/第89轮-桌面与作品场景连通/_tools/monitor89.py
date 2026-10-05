# -*- coding: utf-8 -*-
u"""第89轮真机监控：每 10 秒截图 + 抓取桌宠日志（用户口径）。

用户原话（逐字）
----------------
* 「**你自己每10秒截一下图，存在E盘里当做参考材料**，
   然后看运行后台你自己瞅瞅他说话的逻辑和其他的行动对不对」（第89轮）
* 「**还有，这有一堆bug，你自己开程序检验一下**」（第89轮）

★ 落盘位置说明（**必须如实**）：
  E 盘在本轮实测为**只读**（`E:/__wtest89.txt` 写入 ⇒ `PermissionError`，
  `E:/Download/` 连读都读不到）⇒ 用户要求的"存E盘"**做不到**。
  降级落仓库内 `_evidence/shots/`（并在此脚本与报告里写明原因）。

做的事
------
1. **截图**：`QScreen.grabWindow(0)` 全屏（2560×1600），每 `INTERVAL` 秒一张，
   文件名带序号 + 时间戳。
   ★★ 必须先声明 DPI 感知（`SetProcessDpiAwareness(2)`）—— 否则
     `GetWindowRect` 按缩放比缩小，会误判"窗口不存在"（第67轮栽过）。
2. **抓日志**：桌宠自己的 `_log` 走 stdout ⇒ 直接捕获子进程 stdout 即可。
   同时按关键词分类，便于"看说话逻辑对不对"。
3. **窗口探测**：按 PID 枚举该进程的顶层窗口，报出**窗口类名**
   （`Qt5152QWindowToolSaveBits` = 工具窗口正确 / `...QWindowIcon` = 普通窗口 = "小框"）。
"""
import ctypes
import os
import re
import subprocess
import sys
import time

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
OUT = os.path.join(HERE, '..', '_evidence', 'shots')
INTERVAL = 10.0        # 用户口径：每 10 秒
DURATION = float(os.environ.get('MON89_DURATION') or 120.0)

# ★★★ DPI 感知必须**在任何窗口 API 调用之前**声明。
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)     # PROCESS_PER_MONITOR_DPI_AWARE
    _DPI_OK = True
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        _DPI_OK = True
    except Exception:
        _DPI_OK = False

user32 = ctypes.windll.user32
EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)


def _class_of(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _pid_of(hwnd):
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _title_of(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def top_windows(pid):
    out = []

    def _cb(hwnd, _l):
        if _pid_of(hwnd) == pid:
            out.append((hwnd, _class_of(hwnd), _title_of(hwnd)))
        return True

    EnumWindows(EnumWindowsProc(_cb), 0)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    env.pop('QT_QPA_PLATFORM', None)      # ★ 真机：必须是真窗口平台插件

    print('[MON89] 启动桌宠（真机，非 offscreen）…')
    proc = subprocess.Popen(
        [sys.executable, os.path.join(PKG, 'src', 'main.py')],
        cwd=PKG, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    print('[MON89] PID=%s  输出落 %s' % (proc.pid, OUT))

    # ★ 截图必须在**本进程**做（子进程在跑自己的事件循环）。
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    scr = app.primaryScreen()
    print('[MON89] DPI 感知声明 = %s · 屏幕 = %sx%s · devicePixelRatio=%s'
          % (_DPI_OK, scr.geometry().width(), scr.geometry().height(),
             scr.devicePixelRatio()))

    shots = []
    t0 = time.time()
    n = 0
    while time.time() - t0 < DURATION:
        n += 1
        pm = scr.grabWindow(0)
        stamp = time.strftime('%H%M%S')
        fp = os.path.join(OUT, 'mon89_%02d_%s.png' % (n, stamp))
        ok = pm.save(fp, 'PNG')
        shots.append((fp, ok, pm.width(), pm.height()))
        wl = top_windows(proc.pid)
        cls = sorted({c for _h, c, _t in wl})
        print('[MON89] #%02d %s  save=%s %sx%s  窗口类=%s  标题=%s'
              % (n, stamp, ok, pm.width(), pm.height(), cls,
                 [t for _h, _c, t in wl if t][:4]))
        time.sleep(INTERVAL)

    # 收尾：抓日志并杀进程
    try:
        proc.terminate()
        raw = proc.stdout.read() if proc.stdout else b''
    except Exception:
        raw = b''
    log = raw.decode('utf-8', 'replace')
    logp = os.path.join(OUT, 'mon89_runtime.log')
    with open(logp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(log)

    print('\n[MON89] 截图 %d 张' % sum(1 for _f, ok, _w, _h in shots if ok))
    print('[MON89] 日志 %d 字符 ⇒ %s' % (len(log), logp))

    # ---- 日志摘要（"说话逻辑和行动对不对"）----
    pats = {
        '对话/AI': r'对话|AI |回复|说话|台词',
        '场景': r'场景|scene_id|换房|门',
        'NPC 挪窝': r'自己挪到了',
        '错误': r'\[ERROR\]|\[WARNING\]|异常|失败',
        '就寝': r'就寝',
        '幽灵': r'幽灵',
        '浏览器': r'浏览器|bilibili|哔哩',
    }
    print('\n[MON89] ---- 日志分类计数 ----')
    for k, p in pats.items():
        hits = re.findall(p, log)
        print('  %-10s %d' % (k, len(hits)))
    print('\n[MON89] ---- 前 40 行日志 ----')
    for ln in log.splitlines()[:40]:
        print('  ' + ln[:150])

    return 0


if __name__ == '__main__':
    sys.exit(main())

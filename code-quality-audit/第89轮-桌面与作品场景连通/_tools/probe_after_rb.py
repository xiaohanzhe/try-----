# -*- coding: utf-8 -*-
u"""回退后真机探针：列出桌宠进程的**全部真实窗口**并逐窗抓图。

为什么必须逐窗抓（而不是全屏抓）
--------------------------------
`QScreen.grabWindow(0)` 在 Windows 上**抓不到** `WA_TranslucentBackground`
的分层窗口 —— 全屏图里只有壁纸和任务栏。改用
`PrintWindow(h, hdc, PW_RENDERFULLCONTENT=2)`（见 `grabwin89.py`）。

输出：窗口类名（`Qt5152QWindowToolSaveBits` = 工具窗口，正确；
`Qt5152QWindowIcon` = 普通应用窗口，错误）＋ 真几何 ＋ 可见性 ＋ 抓图落盘。
"""
import ctypes
import os
import subprocess
import sys
import time

HERE = os.path.abspath(os.path.dirname(__file__))
SH = os.path.join(HERE, '..', '_evidence', 'shots')
sys.path.insert(0, HERE)


def find_pid():
    """找跑着 `src/main.py` 的 python 进程。用 PowerShell 取，避开 shell 编码坑。"""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
          "Where-Object { $_.CommandLine -like '*main.py*' } | "
          "Select-Object -First 1 -ExpandProperty ProcessId")
    out = subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                         capture_output=True)
    t = out.stdout.decode('utf-8', 'replace').strip()
    return int(t) if t.isdigit() else None


def main():
    os.makedirs(SH, exist_ok=True)
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else find_pid()
    if not pid:
        print('!! 没找到跑 main.py 的 python 进程（桌宠没起来？）')
        return 2
    print('桌宠 pid =', pid)

    import grabwin89
    import winprobe89

    u = ctypes.windll.user32
    print('主屏 =', u.GetSystemMetrics(0), 'x', u.GetSystemMetrics(1))

    rows = []

    def cb(h, _l):
        if winprobe89.pid_of(h) != pid:
            return True
        c = winprobe89.cls(h)
        if c == 'IME':
            return True
        r = winprobe89.one(h)
        w, hh = r.right - r.left, r.bottom - r.top
        vis = bool(u.IsWindowVisible(h))
        rows.append((h, c, r.left, r.top, w, hh, vis, winprobe89.ttl(h)))
        return True

    winprobe89.EnumWindows(winprobe89.P(cb), 0)

    print('窗口数 =', len(rows))
    for i, (h, c, x, y, w, hh, vis, t) in enumerate(rows):
        kind = ('工具窗口✔' if 'ToolSaveBits' in c else
                '普通窗口✘' if 'QWindowIcon' in c else '')
        print('  #%02d %-30s vis=%-5s rect=(%5d,%5d) %4dx%-4d %s title=%r'
              % (i, c, vis, x, y, w, hh, kind, t))

    # 逐窗抓图
    print('\n--- 逐窗 PrintWindow 抓图 ---')
    stamp = time.strftime('%m%d_%H%M%S')
    for i, (h, c, x, y, w, hh, vis, t) in enumerate(rows):
        img, _w, _h = grabwin89.grab(h)
        if img is None or img.isNull():
            print('  #%02d 抓取失败' % i)
            continue
        scale = 4 if max(w, hh) <= 120 else (2 if max(w, hh) <= 700 else 1)
        out = img.scaled(img.width() * scale, img.height() * scale)
        fp = os.path.join(SH, 'rb_after_%s_win%02d_%dx%d.png'
                          % (stamp, i, w, hh))
        out.save(fp, 'PNG')
        print('  #%02d %-30s %4dx%-4d x%d -> %s'
              % (i, c, w, hh, scale, os.path.basename(fp)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

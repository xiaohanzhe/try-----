# -*- coding: utf-8 -*-
"""第51轮 · 宠物窗口普查（判据自证）

动机：`motion_audit51.py` 报的"宠物窗口 = 138x94"，与既有证据（Ralsei sprite ≈43x80，
窗口应 ≈76x160 或 43x80）**对不上** —— 怀疑 `pick_pet_window` 抓错了窗口。
教训（见项目记忆 §4）：**探针不保真 = 报假问题** ⇒ 抓之前先自证"我抓的确实是 Ralsei"。

做法：起一次程序，把该 pid 下**全部**顶层窗口的
  hwnd / class / title / style / exstyle / rect / 像素特征 打出来，
  并按窗口矩形各抓一张 PNG 存 `_evidence/wincand_<i>.png` 供目视核对。
"""
import os
import sys
import io
import time
import ctypes
import subprocess
from ctypes import wintypes

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.abspath(os.path.join(HERE, '..', '_evidence'))
PY = r'C:\Python311\python.exe'
PET_DIR = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet'

user32 = ctypes.windll.user32
try:
    user32.SetProcessDPIAware()
except Exception:
    pass

WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
GWL_EXSTYLE = -20
GWL_STYLE = -16

_WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


def all_windows(pid):
    out = []

    def _cb(hwnd, _lp):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid:
            return True
        r = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        cls = buf.value
        tbuf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, tbuf, 512)
        title = tbuf.value
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        st = user32.GetWindowLongW(hwnd, GWL_STYLE)
        out.append(dict(hwnd=hwnd, cls=cls, title=title,
                        rect=(r.left, r.top, r.right - r.left, r.bottom - r.top),
                        visible=bool(user32.IsWindowVisible(hwnd)),
                        ex=ex, st=st))
        return True

    user32.EnumWindows(_WNDENUMPROC(_cb), 0)
    return out


def main():
    import psutil
    from PIL import ImageGrab
    import numpy as np

    for p in psutil.process_iter(['pid', 'cmdline']):
        try:
            cl = ' '.join(p.info['cmdline'] or [])
        except Exception:
            continue
        if 'main.py' in cl and 'ralsei_pet' in cl.lower():
            print('!! 已有实例', p.info['pid']); return 2

    env = dict(os.environ); env['PYTHONPATH'] = ''
    lf = open(os.path.join(EV, 'wincand_app.log'), 'w', encoding='utf-8', errors='replace')
    proc = subprocess.Popen([PY, os.path.join('src', 'main.py')], cwd=PET_DIR,
                            env=env, stdout=lf, stderr=subprocess.STDOUT)
    pid = proc.pid
    print('pid =', pid)
    time.sleep(12)          # 等窗口全部建好

    ws = all_windows(pid)
    print('\n共 %d 个顶层窗口（该 pid）\n' % len(ws))
    cand = []
    for i, w in enumerate(ws):
        x, y, ww, hh = w['rect']
        lay = bool(w['ex'] & WS_EX_LAYERED)
        tool = bool(w['ex'] & WS_EX_TOOLWINDOW)
        app = bool(w['ex'] & WS_EX_APPWINDOW)
        flags = ('L' if lay else '-') + ('T' if tool else '-') + ('A' if app else '-')
        print('[%d] hwnd=%-9s vis=%-5s %4dx%-5d @(%-5d,%-5d) ex=%s  cls=%-28s title=%r'
              % (i, w['hwnd'], w['visible'], ww, hh, x, y, flags, w['cls'], w['title'][:40]))
        if w['visible'] and ww >= 16 and hh >= 16 and ww < 900 and hh < 900:
            cand.append((i, w))
    print('\n=== 候选（可见、16~900px）%d 个，逐个抓图 ===' % len(cand))
    for idx, (i, w) in enumerate(cand):
        x, y, ww, hh = w['rect']
        try:
            img = ImageGrab.grab(bbox=(x, y, x + ww, y + hh))
            fp = os.path.join(EV, 'wincand_%02d.png' % idx)
            img.save(fp)
            a = np.asarray(img.convert('RGB'))
            # Ralsei 特征色：白(>230)、绿(G>R 且 G>120)、粉(R>180,B>140,G<160)
            white = int(((a[:, :, 0] > 230) & (a[:, :, 1] > 230) & (a[:, :, 2] > 230)).sum())
            green = int(((a[:, :, 1] > 120) & (a[:, :, 1] > a[:, :, 0] + 20)).sum())
            pink = int(((a[:, :, 0] > 180) & (a[:, :, 2] > 140) & (a[:, :, 1] < 170)).sum())
            print('  [%d] -> %s  %dx%d  white=%d green=%d pink=%d'
                  % (idx, os.path.basename(fp), ww, hh, white, green, pink))
        except Exception as e:
            print('  [%d] 抓图失败 %s' % (idx, e))

    lf.close()
    try:
        pr = psutil.Process(pid)
        for c in pr.children(recursive=True):
            try: c.kill()
            except Exception: pass
        pr.kill()
    except Exception:
        pass
    print('\n已关闭')
    return 0


if __name__ == '__main__':
    sys.exit(main())

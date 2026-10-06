# -*- coding: utf-8 -*-
u"""第93轮 P0-1 真机验收：**画布真的上屏了吗 / 8 扇门真的看得见吗**。

为什么必须这么做（第89轮真机血泪，第93轮升为铁律）
-------------------------------------------------
1. `QScreen.grabWindow(0)`（全屏抓）在 Windows 上**抓不到带 `WA_TranslucentBackground`
   的分层窗口** —— 抓出来只有壁纸和任务栏，桌宠/画布/对话框一律不见。
   唯一可行方式 = `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT=2)` 逐窗口抓。
   （复用第89轮已验证的 `grabwin89.py` / `winprobe89.py`，只读导入，不改它们。）
2. **"状态变了" ≠ "屏幕上看得见"**：`canvas.grab()`（离屏渲染）能把门画得清清楚楚，
   而屏幕上什么都没有。两个方向必须单独验。
3. **不要靠尺寸猜窗口类型**：第89轮的教训是"分类猜错就当没事"。本脚本把该 pid 名下
   **所有**顶层窗口逐个抓下来落盘 + 打印尺寸表，再由人看图判定。

★ 同时声明 DPI 感知（`PER_MONITOR_AWARE_V2`），否则 `GetWindowRect` 会被系统按缩放比缩小。

用法（cwd 任意）： C:\\Python311\\python.exe real_doors93.py
产物：`_evidence/shots/d93_<tag>_w<i>_<w>x<h>.png` + 控制台尺寸表 + 门带像素统计。
"""
import ctypes
import os
import subprocess
import sys
import time

HERE = os.path.abspath(os.path.dirname(__file__))
Q93 = os.path.join(HERE, '..')                       # 第93轮-基础宠物功能收口
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SH = os.path.join(Q93, '_evidence', 'shots')
T89 = os.path.join(ROOT, 'code-quality-audit', '第89轮-桌面与作品场景连通', '_tools')

# ---- 驱动器：真窗口平台起宠物 → 等 4s → 依次切场景 → 停在事件循环 ----
DRIVER = '''# -*- coding: utf-8 -*-
import os, sys, time
PKG = __PKG__
for _p in (os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    sys.path.append(_p)
os.environ.pop('QT_QPA_PLATFORM', None)
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
app = QApplication.instance() or QApplication([])
from main import RalseiPet
pet = RalseiPet()
pet.BEDTIME_ENABLED = False
pet._npc_roam_last_tick = float('inf')

TARGETS = __TARGETS__
STEP_MS = 7000
_idx = [0]


def step():
    if _idx[0] >= len(TARGETS):
        print('[DRV] done', flush=True)
        return                      # 不 quit：保持窗口在屏上给父进程抓
    t = TARGETS[_idx[0]]
    _idx[0] += 1
    try:
        r = pet.travel_to_scene(t)
        ok = r.get('ok') if isinstance(r, dict) else r
        sid = r.get('scene_id') if isinstance(r, dict) else None
        print('[DRV] travel_to_scene(' + repr(t) + ') ok=' + repr(ok)
              + ' sid=' + repr(sid)
              + ' now=' + repr(pet.__dict__.get('current_scene')), flush=True)
    except Exception as e:
        print('[DRV] EXC ' + repr(e), flush=True)
    QTimer.singleShot(STEP_MS, step)


def report():
    try:
        print('[DRV] scene=' + repr(pet.__dict__.get('current_scene'))
              + ' canvas_visible=' + repr(pet.scene_canvas.isVisible())
              + ' canvas_iswin=' + repr(pet.scene_canvas.isWindow())
              + ' canvas_geo=' + repr((pet.scene_canvas.x(), pet.scene_canvas.y(),
                                       pet.scene_canvas.width(), pet.scene_canvas.height()))
              + ' plan_n=' + repr(len(pet.scene_canvas.plan())), flush=True)
    except Exception as e:
        print('[DRV] report EXC ' + repr(e), flush=True)


QTimer.singleShot(12000, step)
for _i in range(len(TARGETS) + 1):
    QTimer.singleShot(12000 + STEP_MS * _i + 2500, report)
app.exec_()
'''


class RECT(ctypes.Structure):
    _fields_ = [('l', ctypes.c_long), ('t', ctypes.c_long),
                ('r', ctypes.c_long), ('b', ctypes.c_long)]


def main():
    targets = ['ch1.castle_town.castle_town', 'desktop']
    os.makedirs(SH, exist_ok=True)

    src = DRIVER.replace('__PKG__', repr(PKG)).replace('__TARGETS__', repr(targets))
    drv = os.path.join(HERE, '_drv93doors.py')
    with open(drv, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(src)

    sys.path.insert(0, T89)
    sys.path.insert(0, HERE)
    import grabwin89
    import winprobe89

    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    env.pop('QT_QPA_PLATFORM', None)
    env['RALSEI_MEMORY_DIR'] = os.path.join(os.environ.get('TEMP', '.'), 'ralsei_d93')
    env['RALSEI_LOG_DIR'] = os.path.join(os.environ.get('TEMP', '.'), 'ralsei_d93')

    logp = os.path.join(SH, 'd93_driver.log')
    log = open(logp, 'w', encoding='utf-8', newline='\n')
    p = subprocess.Popen([sys.executable, drv], cwd=PKG, env=env,
                         stdout=log, stderr=subprocess.STDOUT)
    print('driver pid', p.pid, '（日志 -> %s）' % os.path.basename(logp))

    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    time.sleep(6)
    tags = ['00_start'] + ['%02d_%s' % (i + 1, t.replace('.', '_')[:22])
                           for i, t in enumerate(targets)]
    for tag in tags:
        time.sleep(7.5)
        print('--- 抓 %s ---' % tag)
        idx = [0]

        def cb(h, _l, _pid=p.pid, _tag=tag, _idx=idx):
            if winprobe89.pid_of(h) != _pid:
                return True
            c = winprobe89.cls(h)
            if c == 'IME':
                return True
            rr = RECT()
            ctypes.windll.user32.GetWindowRect(h, ctypes.byref(rr))
            w, hh = rr.r - rr.l, rr.b - rr.t
            vis = bool(ctypes.windll.user32.IsWindowVisible(h))
            img, gw, gh = grabwin89.grab(h)
            _idx[0] += 1
            if img is None or img.isNull():
                print('  w%d cls=%-30s %dx%d vis=%s 抓取失败' % (_idx[0], c, w, hh, vis))
                return True
            fp = os.path.join(SH, 'd93_%s_w%d_%dx%d.png' % (_tag, _idx[0], gw, gh))
            img.save(fp, 'PNG')
            print('  w%d cls=%-30s rect=(%5d,%5d)-(%5d,%5d) %dx%d vis=%-5s -> %s'
                  % (_idx[0], c, rr.l, rr.t, rr.r, rr.b, gw, gh, vis, os.path.basename(fp)))
            return True

        winprobe89.EnumWindows(winprobe89.P(cb), 0)

    try:
        p.terminate()
        time.sleep(1.5)
        if p.poll() is None:
            p.kill()
    except Exception:
        pass
    log.close()

    print('\n--- driver 日志（[DRV] 行）---')
    with open(logp, encoding='utf-8', errors='replace') as fh:
        for ln in fh:
            if '[DRV]' in ln:
                print('  ' + ln.rstrip()[:170])
    return 0


if __name__ == '__main__':
    sys.exit(main())

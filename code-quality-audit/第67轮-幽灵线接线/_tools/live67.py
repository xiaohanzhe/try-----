# -*- coding: utf-8 -*-
"""live67：第67轮 幽灵线 **真机验收**（可复跑；从 E 盘临时探针 live67j 收进仓库）。

它做的是"函数写对了"**之外**的那一半 —— **产品真的用上了吗**：
真起一次桌宠、用 Win32 枚举它进程的顶层窗口，看那只 44×58 的幽灵窗**是否真的存在 / 可见**，
再拿**日志**（`幽灵就绪` / `幽灵定点在`）与**磁盘产物**（`ghost_state.json`）做交叉验证。

★ 两条踩过的坑，本脚本已修（写在这里免得后人重走）
------------------------------------------------------------------
① **必须先声明 DPI 感知**：未声明时 `GetWindowRect` / `GetSystemMetrics` 返回的是
   被系统按缩放比缩小过的"虚拟"坐标（本机 150% ⇒ ÷1.5）。同一扇窗在人眼里是
   `(2515,1393) 44×58`、在非感知探针眼里是 `(1677,927) 29×39` —— 上一版据此
   断言"幽灵窗不存在"，把一个完全正常的功能判成坏的。**量桌宠/浮层必须先声明 DPI 感知。**
② **判别器用"尺寸"而不是样式位**：`Qt.WindowDoesNotAcceptFocus` 在本平台**没有**
   落成 `WS_EX_NOACTIVATE (0x08000000)` ⇒ 拿样式位找幽灵**恒 0 命中**。
   改为在"同一 pid 的顶层窗口"里按尺寸 `44×58` 认（宠物主窗是别的尺寸、
   灵魂窗是 48×48，不会撞）。

③（本版新增）**不要 `shutil.rmtree()` 旧目录**：本环境有删除守卫（同一轮次内按路径
   累计删除超过阈值即拦截），旧 `ghost_live67j/` 累积到 54 个文件后直接把探针打死在
   import 期。改为**每次用一个带时间戳的新目录**，天然无需删除。

断言（每条独立可证伪；A5 拿"日志锚点 vs 实测宠物中心"互证）：
  A1 桌宠主窗口出现
  A2 存在 44×58 的同 pid 顶层窗口（= 幽灵浮层）
  A3 该窗口在真机上**可见**过
  A4 日志文件出现「幽灵就绪」（**依赖 main 的日志器接线修复** —— 不修则日志落到
     `__main__` logger ⇒ 这行永远查不到 ⇒ A4 会红）
  A5 日志「幽灵定点在」的锚点 == 实测宠物中心 + `GHOST_SPAWN_OFFSET(96,-6)`（±3px）
     ★ 为什么不拿"幽灵窗口中心"当基准：窗口位置会被**虚拟屏边界钳制**（契约①的
       既定行为），拿它比会把正常钳制判成错。
  A6 `ghost_state.json` 落盘且 `ver == 1`
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import subprocess
import sys
import time

import psutil

# ---- ① 先声明 DPI 感知（必须在任何 GetWindowRect 之前）----
_DPI_MODE = 'none'
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)          # PER_MONITOR_DPI_AWARE
    _DPI_MODE = 'shcore/2'
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        _DPI_MODE = 'user32'
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))                # …/第67轮-幽灵线接线/_tools
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))     # 仓库根（try - 副本）
APP = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(APP, 'src', 'main.py')
# ③ 每次一个**新目录**（不再 rmtree —— 见 docstring 坑③）
ISO = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out',
                   'ghost_live67_' + time.strftime('%Y%m%d_%H%M%S'))
PY = r'C:\Python311\python.exe'
GHOST_W, GHOST_H = 44, 58
EXPECT_DIST = (96.0 ** 2 + 6.0 ** 2) ** 0.5

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def log(m):
    print(m, flush=True)


def kill_all():
    me = os.getpid()
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        if p.info['pid'] == me:
            continue
        c = ' '.join(p.info['cmdline'] or [])
        if 'python' in (p.info['name'] or '').lower() and 'ralsei_pet' in c.lower() and 'main.py' in c:
            try:
                p.kill()
            except Exception:
                pass
    time.sleep(1.2)


def _t(h):
    n = user32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 2)
    user32.GetWindowTextW(h, b, n + 2)
    return b.value


def _cls(h):
    b = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, b, 256)
    return b.value


def _pid(h):
    p = wt.DWORD(0)
    user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def _rect(h):
    r = wt.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def snap(pid):
    out = []

    def cb(h, l):
        if _pid(h) == pid:
            out.append({'h': int(h), 'title': _t(h), 'cls': _cls(h), 'rect': _rect(h),
                        'vis': bool(user32.IsWindowVisible(h))})
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def main():
    log('===== live67：幽灵线真机验收（DPI-aware） =====')
    log('[0] DPI 感知设置 = %s' % _DPI_MODE)
    vm = (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
    log('    主屏(SM_CXSCREEN,CYSCREEN) = %s   ← 未声明 DPI 感知时这里是"缩小值"' % (vm,))
    if not os.path.isfile(SRC):
        log('[!] 找不到 %s' % SRC)
        return 2
    os.makedirs(ISO, exist_ok=True)
    kill_all()
    env = dict(os.environ)
    env['RALSEI_MEMORY_DIR'] = ISO            # ★ 最高优先级覆盖 ⇒ vault 完全隔离在仓内
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'
    out = os.path.join(ISO, 'stdout.txt')
    f = open(out, 'w', encoding='utf-8', errors='replace')
    proc = subprocess.Popen([PY, SRC], cwd=APP, env=env, stdout=f, stderr=subprocess.STDOUT)
    t0 = time.time()
    log('[1] pid=%d  vault=%s' % (proc.pid, ISO))

    samples = []
    while time.time() - t0 < 22.0:
        ws = snap(proc.pid)
        pet = [x for x in ws if x['title'] == 'Ralsei Pet' and x['vis']]
        gh = [x for x in ws if x['rect'][2:4] == (GHOST_W, GHOST_H)]
        rec = {'t': time.time() - t0, 'pet': pet[0]['rect'] if pet else None,
               'gh': gh[0]['rect'] if gh else None, 'ghvis': gh[0]['vis'] if gh else None,
               'nwin': len(ws)}
        samples.append(rec)
        time.sleep(1.0)
    proc.kill()
    try:
        proc.wait(timeout=10)
    except Exception:
        pass
    f.close()

    log('')
    log('[2] 逐秒采样')
    for s in samples:
        if not s['pet']:
            continue
        d = None
        if s['gh']:
            pc = (s['pet'][0] + s['pet'][2] / 2.0, s['pet'][1] + s['pet'][3] / 2.0)
            gc = (s['gh'][0] + s['gh'][2] / 2.0, s['gh'][1] + s['gh'][3] / 2.0)
            d = ((gc[0] - pc[0]) ** 2 + (gc[1] - pc[1]) ** 2) ** 0.5
        log('   t=%4.1fs pet=%-22s ghost=%-20s vis=%-5s 距离=%s'
            % (s['t'], str(s['pet']), str(s['gh']), str(s['ghvis']),
               ('%.2f' % d) if d is not None else '—'))

    ok = True
    log('')
    log('===== 断言 =====')
    pet_any = [s for s in samples if s['pet']]
    a1 = bool(pet_any)
    log('[A1] 桌宠主窗口出现 : %s' % a1)
    ok &= a1

    ghs = [s for s in samples if s['gh']]
    a2 = bool(ghs)
    log('[A2] 存在 44x58 幽灵窗口 : %s（%d/%d 采样点命中；尺寸集合 %s）'
        % (a2, len(ghs), len(samples),
           sorted({(s['gh'][2], s['gh'][3]) for s in ghs})))
    ok &= a2

    hits = [(s['t'], s['ghvis']) for s in ghs]
    a3 = any(v for _t, v in hits)
    log('[A3] 幽灵窗口在真机上**可见**过 : %s（可见 %d/%d 个含幽灵窗口的采样点）'
        % (a3, sum(1 for _t, v in hits if v), len(hits)))
    ok &= a3

    lp = os.path.join(ISO, 'logs', 'ralsei_pet.log')
    txt = open(lp, encoding='utf-8', errors='replace').read() if os.path.isfile(lp) else ''
    a4 = '幽灵就绪' in txt
    log('[A4] 日志出现「幽灵就绪」: %s' % a4)
    ok &= a4

    anchors = re.findall(r'幽灵定点在 x=(-?[\d.]+) y=(-?[\d.]+)', txt)
    a5 = False
    if anchors and pet_any:
        ax, ay = float(anchors[-1][0]), float(anchors[-1][1])
        p = pet_any[0]['pet']
        pcx, pcy = p[0] + p[2] / 2.0, p[1] + p[3] / 2.0
        ex, ey = pcx + 96.0, pcy - 6.0
        dd = ((ax - ex) ** 2 + (ay - ey) ** 2) ** 0.5
        a5 = dd <= 3.0
        log('       日志锚点=(%.1f,%.1f)  期望=宠物中心(%.1f,%.1f)+(96,-6)=(%.1f,%.1f)  偏差=%.2f'
            % (ax, ay, pcx, pcy, ex, ey, dd))
    log('[A5] 日志「幽灵定点在」↔ 实测宠物位置 一致 : %s（锚点行 %d 条）' % (a5, len(anchors)))
    ok &= a5

    sp = os.path.join(ISO, 'ghost_state.json')
    st = json.load(open(sp, encoding='utf-8')) if os.path.isfile(sp) else None
    a6 = bool(st) and st.get('ver') == 1
    log('[A6] ghost_state.json 落盘 ver==1 : %s  %s'
        % (a6, json.dumps(st, ensure_ascii=False) if st else ''))
    ok &= a6

    log('')
    log('===== 判定：%s =====' % ('PASS（A1~A6 全绿）' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

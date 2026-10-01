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

    # ⚠️ 第74轮 B5 修：采样**不能只靠固定 22s 窗口碰运气**。
    #   真相（实测）：Qt 顶层窗是**第一次 `show()` 才创建原生句柄**的 —— 幽灵在
    #   "走动"档下 `alpha` 恒 0 ⇒ 从不 `show()` ⇒ `EnumWindows` 一条都枚举不到。
    #   于是"宠物恰好一直在走"的那次跑，A2/A3/A7 会全红，而功能其实完全正常
    #   （DEBUG 诊断 728 帧实测：走 ⇒ alpha=0/vis=False，停 ⇒ alpha=0.6/vis=True）。
    #   ⇒ 改成**等待式**：先等幽灵窗首次**可见**（最多 WAIT_GHOST_S），等到之后再采。
    #   判据不变（仍是"到底有没有这只窗、距离多少"），只是不再把"采样时机"当运气。
    WAIT_GHOST_S = 75.0
    TAIL_S = 14.0
    samples = []
    waited = 0.0
    while time.time() - t0 < WAIT_GHOST_S:
        ws = snap(proc.pid)
        gh = [x for x in ws if x['rect'][2:4] == (GHOST_W, GHOST_H)]
        if gh and gh[0]['vis']:
            waited = time.time() - t0
            break
        time.sleep(0.5)
    log('[1b] 等到幽灵窗**可见**用了 %.1fs（上限 %.0fs；0 ⇒ 没等到）' % (waited, WAIT_GHOST_S))
    t1 = time.time()
    while time.time() - t1 < TAIL_S:
        ws = snap(proc.pid)
        # ⚠️ pet 的挑法：**不能只看标题**。同一个进程里"Ralsei Pet"名下会短暂出现
        #   别的浮层（气泡 / 场景画布尺寸 620×236、桌宠本体 38×80 或 42×82）。
        #    实测（第74轮 B5 探针）：只按标题 + vis 会随机命中画布 ⇒ "宠物在移动"
        #    这个观察本身就是假的。改为**在标题命中的里面挑最贴近桌宠尺寸的那个**。
        pets = [x for x in ws if x['title'] == 'Ralsei Pet']
        _pw, _ph = 42, 82
        pet = min(pets, key=lambda x: abs(x['rect'][2] - _pw) + abs(x['rect'][3] - _ph)) \
            if pets else None
        gh = [x for x in ws if x['rect'][2:4] == (GHOST_W, GHOST_H)]
        rec = {'t': time.time() - t0, 'pet': pet['rect'] if pet else None,
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

    anchors = re.findall(r'幽灵定点在\s*(?:模式=\S+\s*)?x=(-?[\d.]+) y=(-?[\d.]+)', txt)
    # ⚠️ 第74轮 B5 修：`describe()` 现在会在 `x=` 之前多打一段 `模式=follow`。
    #    旧正则 `幽灵定点在 x=` 因此**一条都匹配不到** ⇒ A5 会红，而真相是"日志变了、
    #    功能没坏"。正则改成"允许中间夹一段可选前缀"，并在下面把"匹配到几条"打出来
    #    —— 静默 0 条正是这类判据最危险的失效方式（本项目踩过）。
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
    log('[A5] 日志「幽灵定点在」↔ 实测宠物位置 一致 : %s（锚点行 %d 条，0 条 = 判据失效不是功能坏）'
        % (a5, len(anchors)))
    ok &= a5

    # ---- A7（第74轮 B5 追加）：产品真的在"跟飘"，不是"定点" ----
    # ★ 这条判据的阈值不是随手取的：**跟飘**的偏移量 = |GHOST_FOLLOW_OFFSET| = √(46²+6²) ≈ 46.4，
    #   而**定点**出生偏移 = √(96²+6²) ≈ 96.2 ⇒ 60 这条线能把两种模式干净分开。
    #   （窗口位置会被虚拟屏边界钳制，所以只判"中位距离"，不判每帧都相等。）
    # ⚠️ 第74轮 B5 修（判据侧）：只在**幽灵可见的采样点**上算。
    #   真相（真机 5882 帧取证）：跟飘幽灵在宠物**跑动**时 alpha 归 0、窗口被 
    #   收起；而跑远了之后它的锚点会跟着跑，但窗口位置还会受**虚拟屏边界钳制**。
    #   拿这些帧去算“窗口中心到宠物中心”的距离，量到的是“钳制差”而不是“跟飘偏移”，
    #   会把**完全正常**的行为判成红。⇒ 只在 （= 站住显形，此时没被钳）
    #   的采样点上取中位。“没有任何可见采样”本身就是失败（A3 已经报了）。
    _ds = []
    for s in samples:
        if s['pet'] and s['gh'] and s['ghvis']:
            pc = (s['pet'][0] + s['pet'][2] / 2.0, s['pet'][1] + s['pet'][3] / 2.0)
            gc = (s['gh'][0] + s['gh'][2] / 2.0, s['gh'][1] + s['gh'][3] / 2.0)
            _ds.append(((gc[0] - pc[0]) ** 2 + (gc[1] - pc[1]) ** 2) ** 0.5)
    _ds.sort()
    _med = _ds[len(_ds) // 2] if _ds else None
    a7 = _med is not None and _med <= 60.0
    log('[A7] 幽灵**可见**采样点上的中位距离 = %s（样本 %d 个）'
        ' ⇒ 跟飘（≤60，定点会是 ~96）: %s'
        % (('%.2f' % _med) if _med is not None else '无样本', len(_ds), a7))
    ok &= a7

    sp = os.path.join(ISO, 'ghost_state.json')
    st = json.load(open(sp, encoding='utf-8')) if os.path.isfile(sp) else None
    a6 = bool(st) and st.get('ver') == 1
    log('[A6] ghost_state.json 落盘 ver==1 : %s  %s'
        % (a6, json.dumps(st, ensure_ascii=False) if st else ''))
    ok &= a6

    log('')
    # ⚠️ 第74轮 B5：以前写死 "A1~A6 全绿"，加了 A7 之后结论行就成了假陈述。
    #    改成把**登记过的编号逐个列出来**（不按大小排序，按登记顺序），
    #    加断言时只改 `_names` 一处，结论行自动跟上，不会再出现"说了 A6 其实还有 A7"。
    _names = ['A1', 'A2', 'A3', 'A4', 'A5', 'A7', 'A6']
    log('===== 判定：%s =====' % (('PASS（%s 全绿）' % '+'.join(_names))
                                 if ok else 'FAIL'))
    return 0 if ok else 1
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

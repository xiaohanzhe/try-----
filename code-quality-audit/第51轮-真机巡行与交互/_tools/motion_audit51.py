# -*- coding: utf-8 -*-
"""第51轮 · 移动系统真机体检器（屏幕自动化口径，不读后台日志）

用户口径（逐字）：「他现在光有那个移动的动画，没有实际移动，这样吧，你自己到时候也整体
查一下他的移动系统这类的，用屏幕自动化来看，而不是后台日志，对了，测完了记得关掉」

观测手段（全部落在"看得见"的层面）：
  ① `EnumWindows` + `GetWindowRect`  → 宠物窗口的**真实屏幕矩形**（每 0.4s 一次）
  ② `PIL.ImageGrab.grab(bbox)`      → 宠物窗口**区域像素**（仅在位置未变时抓，用于判动画）
  ③ 由 ①② 推：位移 / 行走段 / 静息段 / 贴边占用 / **"原地播动画"** 时长

⚠️ 关键实现约束（踩过的坑）：
  - 启动子进程时必须 `env['PYTHONPATH'] = ''`：宿主注入的 shim `sitecustomize.py` 会劫持
    `os.remove` → 同步 `subprocess.run`，单次阻塞 0.6~6.8s，会伪造出"主线程卡顿"，
    那是**我的采集环境**的artifact，不是产品行为。
  - 绝不用 `python -c` 内联 / 绝不从 Bash 调 PowerShell（反引号、\\n 会被吞）。
用法：
  python motion_audit51.py [时长秒=180]
输出：
  <HERE>/../_evidence/motion_audit51.json   ← 原始采样 + 统计
  <HERE>/../_evidence/motion_audit51.png    ← 位移曲线 + 动画活跃度（PIL 手绘，零新依赖）
"""
import os
import sys
import io
import json
import time
import math
import ctypes
import subprocess
from ctypes import wintypes

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.abspath(os.path.join(HERE, '..', '_evidence'))
os.makedirs(EV, exist_ok=True)

PY = r'C:\Python311\python.exe'
ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'      # 仓库根
PET_DIR = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET_DIR, 'src', 'main.py')

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 180.0
SAMPLE_DT = 0.25                      # 窗口矩形采样间隔（窗口仅 38x80，采样可以更密）
PIX_DT = 0.4                          # 位置不变时的像素抓取间隔

user32 = ctypes.windll.user32
try:
    user32.SetProcessDPIAware()
except Exception:
    pass


# ---------------------------------------------------------------- 窗口枚举
class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


_WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


def windows_for_pid(pid):
    """返回该 pid 下所有可见、尺寸>1 的顶层窗口 [(hwnd, x, y, w, h)]。"""
    out = []

    def _cb(hwnd, _lp):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        r = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        if w <= 1 or h <= 1:
            return True
        out.append((hwnd, r.left, r.top, w, h))
        return True

    try:
        user32.EnumWindows(_WNDENUMPROC(_cb), 0)
    except Exception:
        pass
    return out


def win_title(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def pick_pet_window(pid):
    """★ 判据必须严格自证 —— v1 用"第一个 16~1200px 的可见窗口"，实测抓到了**非宠物
    窗口**（报 138x94；而宠物恒为 38x80），据此产出的 180s 数据**全部作废**。
    教训（项目记忆 §4）：**探针不保真 = 报假问题**，先从"我抓的是谁"证起。

    现在只认窗口标题 `'Ralsei Pet'`（实测特征：类 `Qt5152QWindowToolSaveBits`、
    exstyle 含 LAYERED|TOOLWINDOW、38x80）。返回 (hwnd,x,y,w,h) 或 None。
    """
    for hwnd, x, y, w, h in windows_for_pid(pid):
        if win_title(hwnd) == 'Ralsei Pet':
            return (hwnd, x, y, w, h)
    return None


def pet_pixel_signature(x, y, w, h):
    """回证用：窗口区域的 白/绿/粉 像素计数（Ralsei 配色的指纹）。"""
    try:
        from PIL import ImageGrab
        import numpy as np
        a = np.asarray(ImageGrab.grab(bbox=(x, y, x + w, y + h)).convert('RGB'))
        white = int(((a[:, :, 0] > 230) & (a[:, :, 1] > 230) & (a[:, :, 2] > 230)).sum())
        green = int(((a[:, :, 1] > 120) & (a[:, :, 1] > a[:, :, 0] + 20)).sum())
        pink = int(((a[:, :, 0] > 180) & (a[:, :, 2] > 140) & (a[:, :, 1] < 170)).sum())
        return dict(white=white, green=green, pink=pink)
    except Exception as e:
        return dict(err=str(e))


def virtual_screen():
    SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
    SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
    return (user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))


# ---------------------------------------------------------------- 主流程
def main():
    from PIL import ImageGrab
    import numpy as np
    import psutil

    print('=' * 68)
    print('第51轮 · 移动系统真机体检')
    print('=' * 68)

    # 0) 环境预检：确认没有残留实例（单实例锁 Global\\RalseiPetMutex）
    leftover = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cl = ' '.join(p.info['cmdline'] or [])
        except Exception:
            continue
        if 'main.py' in cl and 'ralsei_pet' in cl.lower():
            leftover.append(p.info['pid'])
    print('残留实例:', leftover)
    if leftover:
        print('!! 先清理再测'); return 2

    # 1) 启动（剥掉 shim）
    env = dict(os.environ)
    env['PYTHONPATH'] = ''
    logf = r'E:\Download\_tmp\motion_audit51_app.log'
    try:
        os.makedirs(os.path.dirname(logf), exist_ok=True)
    except Exception:
        logf = os.path.join(EV, 'motion_audit51_app.log')   # E 盘不可用则落证据目录
    lf = open(logf, 'w', encoding='utf-8', errors='replace')
    t0 = time.time()
    proc = subprocess.Popen([PY, os.path.join('src', 'main.py')], cwd=PET_DIR,
                            env=env, stdout=lf, stderr=subprocess.STDOUT)
    pid = proc.pid
    print('已启动 pid =', pid, ' log =', logf)

    # 2) 等宠物窗口**真正就绪**（最多 60s）
    #    ★★ 为什么不能"窗口一出现就开始采"：实测启动后 ~4.5s 时窗口标题已是
    #    'Ralsei Pet'、矩形 138x94，但**表面还是全透明的**（sprite 尚未绘制），
    #    自证像素 white/green/pink 全为 0 —— 此时抓到的"像素差"全是气泡/桌面噪声，
    #    "位移"也毫无意义。要求**连续 3 次**白/绿/粉像素合计 >= 50 才认为就绪。
    pet = None
    sig = {}
    stable = 0
    while time.time() - t0 < 60:
        if proc.poll() is not None:
            print('!! 进程提前退出，rc =', proc.returncode); break
        pet = pick_pet_window(pid)
        if pet:
            _, _x, _y, _w, _h = pet
            sig = pet_pixel_signature(_x, _y, _w, _h)
            if sum(sig.get(k, 0) for k in ('white', 'green', 'pink')) >= 50:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
        time.sleep(1.0)
    if not pet or stable < 3:
        print('!! 60s 内 Ralsei 未就绪（像素自证未通过），当前自证 =', sig)
        try: kill_tree(pid)
        except Exception: pass
        return 3
    hwnd, x, y, w, h = pet
    print('宠物窗口: hwnd=%s  %dx%d @ (%d,%d)   (耗时 %.1fs)' % (hwnd, w, h, x, y, time.time() - t0))
    vx, vy, vw, vh = virtual_screen()
    print('虚拟桌面: %dx%d @ (%d,%d)' % (vw, vh, vx, vy))
    # ★ 自证：把抓到的窗口原样存一张，肉眼核对"这确实是 Ralsei"
    print('就绪自证（白/绿/粉像素计数）:', sig)
    try:
        from PIL import ImageGrab
        selfp = os.path.join(EV, 'motion_audit51_petwin_ready.png')
        ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(selfp)
        print('自证截图 ->', selfp)
    except Exception as e:
        print('自证截图失败:', e)

    # 3) 采样
    samples = []
    anim = []                 # (t, diff) 只在位置未变时抓
    last_rect = None
    last_img = None
    last_pix_t = 0.0
    scan_t0 = time.time()
    while time.time() - scan_t0 < DURATION:
        if proc.poll() is not None:
            print('!! 进程中途退出 rc =', proc.returncode); break
        p = pick_pet_window(pid)
        if not p:
            time.sleep(SAMPLE_DT); continue
        _, cx, cy, cw, ch = p
        t = time.time() - scan_t0
        same = (last_rect is not None and abs(cx - last_rect[0]) <= 1
                and abs(cy - last_rect[1]) <= 1 and cw == last_rect[2] and ch == last_rect[3])
        diff = None
        if same and t - last_pix_t >= PIX_DT:
            try:
                img = ImageGrab.grab(bbox=(cx, cy, cx + cw, cy + ch))
                a = np.asarray(img.convert('L'), dtype=np.float32)
                if last_img is not None and last_img.shape == a.shape:
                    diff = float(np.abs(a - last_img).mean())
                last_img = a
                last_pix_t = t
            except Exception:
                pass
        else:
            if not same:
                last_img = None
        samples.append([round(t, 2), cx, cy, cw, ch,
                        (round(diff, 3) if diff is not None else None)])
        if diff is not None:
            anim.append([round(t, 2), round(diff, 3)])
        last_rect = (cx, cy, cw, ch)
        time.sleep(SAMPLE_DT)

    # 4) 收尾：关掉（用户明确要求）
    print('采集中止时间 %.1fs，正在关闭…' % (time.time() - scan_t0))
    kill_tree(pid)
    lf.close()
    print('关闭完成，残留:', [p.info['pid'] for p in psutil.process_iter(['pid', 'cmdline'])
                              if 'main.py' in ' '.join(p.info['cmdline'] or [])])

    # 5) 统计（★ 用 try 包住：分析/绘图失败也**必须**把原始采样落盘，240s 数据不可再生）
    try:
        st = analyze(samples, anim, (vx, vy, vw, vh), w, h)
    except Exception as e:
        import traceback
        traceback.print_exc()
        st = {'err': '%s: %s' % (type(e).__name__, e)}
    data = {'pid': pid, 'window': {'w': w, 'h': h}, 'virtual': [vx, vy, vw, vh],
            'duration': round(time.time() - scan_t0, 1), 'samples': samples,
            'anim': anim, 'stats': st}
    jf = os.path.join(EV, 'motion_audit51.json')
    with open(jf, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('\n=== 统计 ===')
    for k, v in st.items():
        print('  %-26s %s' % (k, v))

    draw_plot(data, os.path.join(EV, 'motion_audit51.png'))
    print('\nJSON ->', jf)
    print('PNG  ->', os.path.join(EV, 'motion_audit51.png'))
    return 0


def kill_tree(pid):
    import psutil
    try:
        p = psutil.Process(pid)
        for c in p.children(recursive=True):
            try: c.kill()
            except Exception: pass
        p.kill()
        p.wait(timeout=5)
    except Exception:
        pass


def analyze(samples, anim, virt, ww, wh):
    vx, vy, vw, vh = virt
    if not samples:
        return {'err': 'no samples'}
    xs = [s[1] for s in samples]
    ys = [s[2] for s in samples]
    ts = [s[0] for s in samples]
    total = 0.0
    walks = []          # (t_start, t_end, dist)
    cur = None
    for i in range(1, len(samples)):
        d = math.hypot(samples[i][1] - samples[i - 1][1], samples[i][2] - samples[i - 1][2])
        total += d
        if d > 1.5:
            if cur is None:
                cur = [ts[i - 1], ts[i], d]
            else:
                cur[1] = ts[i]; cur[2] += d
        else:
            if cur is not None:
                walks.append(cur); cur = None
    if cur:
        walks.append(cur)

    # 静息段（同一位置连续 >= 5 个采样）
    rests = []
    r0 = None
    for i in range(1, len(samples)):
        moved = math.hypot(samples[i][1] - samples[i - 1][1], samples[i][2] - samples[i - 1][2]) > 1.5
        if not moved:
            if r0 is None:
                r0 = i - 1
        else:
            if r0 is not None and i - 1 - r0 >= 5:
                rests.append([ts[r0], ts[i - 1], round(ts[i - 1] - ts[r0], 1)])
            r0 = None
    if r0 is not None and len(samples) - 1 - r0 >= 5:
        rests.append([ts[r0], ts[-1], round(ts[-1] - ts[r0], 1)])

    # 边界占用（距虚拟屏任一边 <= 8px 视为贴边）
    edge = 0
    for s in samples:
        _, cx, cy, cw, ch = s[0], s[1], s[2], s[3], s[4]
        if (cx <= vx + 8 or cy <= vy + 8
                or cx + cw >= vx + vw - 8 or cy + ch >= vy + vh - 8):
            edge += 1

    # "原地播动画"：位置不变却像素在变
    moving_pix = [a for a in anim if a[1] > 2.0]
    still_pix = [a for a in anim if a[1] <= 2.0]

    # ★★ 三态时长 —— 直接回答用户那句「光有那个移动的动画，没有实际移动」：
    #   ① moving_s       位置在变                    → 真移动
    #   ② still_anim_s   位置不变、画面在变          → **"原地播动画"**（用户报的现象）
    #   ③ still_silent_s 位置不变、画面也不变        → 完全静止（含睡眠/特殊动画锁）
    #   每个采样归属哪态：以"本采样相对上一采样位置是否变" + "最近一次已知像素差"判定。
    last_diff = None
    moving_s = still_anim_s = still_silent_s = 0.0
    for i in range(1, len(samples)):
        s, p = samples[i], samples[i - 1]
        if s[5] is not None:
            last_diff = s[5]
        moved = math.hypot(s[1] - p[1], s[2] - p[2]) > 0.5
        if moved:
            moving_s += SAMPLE_DT
        elif last_diff is not None and last_diff > 2.0:
            still_anim_s += SAMPLE_DT
        else:
            still_silent_s += SAMPLE_DT
    sizes = sorted({(s[3], s[4]) for s in samples})

    return {
        'samples': len(samples),
        'span_s': round(ts[-1] - ts[0], 1),
        'total_travel_px': round(total, 1),
        'avg_speed_px_s': round(total / max(ts[-1] - ts[0], 0.1), 1),
        'walk_segments': len(walks),
        'walk_px_median': round(sorted([x[2] for x in walks])[len(walks) // 2], 1) if walks else 0,
        'rest_segments(>=2s)': len(rests),
        'longest_rest_s': max([r[2] for r in rests], default=0.0),
        'edge_busy_ratio': round(edge / len(samples), 3),
        'x_range': [min(xs), max(xs)],
        'y_range': [min(ys), max(ys)],
        'anim_probe_n': len(anim),
        'anim_changing_n': len(moving_pix),
        'anim_idle_n': len(still_pix),
        'anim_change_ratio': round(len(moving_pix) / len(anim), 3) if anim else None,
        'anim_diff_mean': round(sum(a[1] for a in anim) / len(anim), 3) if anim else None,
        'T_moving_s': round(moving_s, 1),
        'T_still_anim_s': round(still_anim_s, 1),
        'T_still_silent_s': round(still_silent_s, 1),
        'T_moving_pct': round(100.0 * moving_s / max(moving_s + still_anim_s + still_silent_s, 0.1), 1),
        'T_still_anim_pct': round(100.0 * still_anim_s / max(moving_s + still_anim_s + still_silent_s, 0.1), 1),
        'window_sizes_seen': sizes,
    }


def draw_plot(data, out):
    """PIL 手绘：上=轨迹(x,y vs t)，下=动画活跃度。零新依赖。"""
    from PIL import Image, ImageDraw
    W, H = 1200, 760
    im = Image.new('RGB', (W, H), (18, 20, 26))
    d = ImageDraw.Draw(im)
    FG = (232, 234, 240)
    GRID = (60, 66, 80)
    C1, C2, C3 = (255, 106, 106), (106, 200, 255), (140, 230, 150)

    samples = data['samples']
    anim = data['anim']
    st = data['stats']
    if not samples:
        im.save(out); return
    t_end = max(samples[-1][0], 1.0)

    def panel(top, height, title):
        d.rectangle([40, top, W - 40, top + height], outline=GRID)
        for i in range(5):
            yy = top + height * i // 4
            d.line([40, yy, W - 40, yy], fill=GRID)
        d.text((44, top - 18), title, fill=FG)

    # --- panel 1: x / y ---
    top1, h1 = 70, 300
    panel(top1, h1, 'Ralsei window position (px) vs time (s)   red=x  blue=y')
    xs = [s[1] for s in samples]
    ys = [s[2] for s in samples]
    lo, hi = min(xs + ys), max(xs + ys)
    rng = max(hi - lo, 1)

    def pt(t, v):
        px = 40 + (W - 80) * (t / t_end)
        py = top1 + h1 - h1 * ((v - lo) / rng)
        return (px, py)

    for series, col in ((xs, C1), (ys, C2)):
        pts = [pt(samples[i][0], series[i]) for i in range(len(samples))]
        d.line(pts, fill=col, width=2)

    # --- panel 2: anim diff ---
    top2, h2 = 450, 200
    panel(top2, h2, 'pixel diff inside pet window (animation activity)  |  only sampled while position unchanged')
    if anim:
        amax = max(a[1] for a in anim) or 1.0
        pts = [(40 + (W - 80) * (a[0] / t_end), top2 + h2 - h2 * (a[1] / amax)) for a in anim]
        d.line(pts, fill=C3, width=2)
        # 2.0 阈值线
        yth = top2 + h2 - h2 * (2.0 / amax)
        d.line([40, yth, W - 40, yth], fill=(255, 200, 90), width=1)
        d.text((W - 300, yth - 16), 'threshold=2.0 (below = frozen frame)', fill=(255, 200, 90))

    # --- 统计行 ---
    d.text((44, 16), 'window %dx%d  |  span %ss  |  travel %spx  |  walks %d  |  longest rest %ss  |  edge-busy %s' % (
        data['window']['w'], data['window']['h'], st.get('span_s'), st.get('total_travel_px'),
        st.get('walk_segments'), st.get('longest_rest_s'), st.get('edge_busy_ratio')), fill=FG)
    d.text((44, 36), 'T_moving %ss (%s%%)   |   T_STILL+animating %ss (%s%%) <- 用户报的"只播动画不移动"   |   T_still-silent %ss' % (
        st.get('T_moving_s'), st.get('T_moving_pct'), st.get('T_still_anim_s'),
        st.get('T_still_anim_pct'), st.get('T_still_silent_s')), fill=(255, 200, 90))
    d.text((44, 700), 'anim samples %s  |  changing %s  |  frozen %s  |  change-ratio %s  |  mean diff %s  |  sizes %s' % (
        st.get('anim_probe_n'), st.get('anim_changing_n'), st.get('anim_idle_n'),
        st.get('anim_change_ratio'), st.get('anim_diff_mean'), st.get('window_sizes_seen')), fill=C3)
    im.save(out)


if __name__ == '__main__':
    sys.exit(main())

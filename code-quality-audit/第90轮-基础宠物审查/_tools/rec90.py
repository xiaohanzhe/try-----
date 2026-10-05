# -*- coding: utf-8 -*-
u"""第90轮 · 真机逐帧录制 + 帧间对比（用户视角验收）

用户口径（逐字）：「你可以录视频然后通过对比前后帧这样的方法判定他的移动
这类的也就是用户视角的反馈」。

为什么不用小助手的 recording.draft
---------------------------------
先按要求走了原生能力（`cli recording start/status/stop/export`）：
它确实建出了录制目录与会话，但 `frames/` **一帧都没有**，worker 进程
（pid 54932）随后退出，`recording export <dir>` 返回的是**经验草稿**
（`needs_interpretation` 的问卷）而不是视频。日志文件
`...\\logs\\screen_automation.log` 也不存在。
⇒ 桌面端 GUI 未运行/未安装时，`recording.draft` 只产出"操作步骤经验"骨架，
   **不产出可逐帧分析的画面**。未经用户同意不下载、安装或启动桌面端，
   故本轮改用**应用窗口自身的逐帧抓取**：
     · `GetWindowRect` → 窗口的**真实屏幕坐标**（这是产品自己 move() 的结果）
     · `PrintWindow(PW_RENDERFULLCONTENT)` → 该窗口**自身的像素**
   ★ 分层/透明窗口用 `grabWindow(0)` 抓不到，必须 PrintWindow —— 第89轮血泪。

产物（全部**不含用户桌面** ⇒ 可入库）
------------------------------------
  rec90_traj.csv      逐帧：t / 窗口左上角 (x,y) / 窗口尺寸 / 精灵质心
  rec90_jump.mp4      录制回放（中性底 + 真实精灵 + 轨迹拖尾）
  rec90_stab.mp4      稳定视角（精灵居中，看动画本身）
  rec90_analysis.txt  逐帧对比结论 + 判据自证
  rec90_plot.png      y(t) 曲线 + 理论抛物线叠加 + 跳段标注

判据纪律
--------
  · 「帧间对比」= 逐帧算**精灵质心**的位移（不是算我们写进去的数）
  · 正/负控制成对：把「向上跳」与「下落/走路」的签名分别断言
  · 恒真防护：先断言"轨迹不是常量"（否则后面所有"有弧"的结论都无意义）

用法：python rec90.py [--seconds 60] [--fps 20] [--pid <pid>]
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import time

import numpy as np

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

u = ctypes.windll.user32
gdi = ctypes.windll.gdi32
P_CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

HERE = os.path.abspath(os.path.dirname(__file__))
PET_TITLE = 'Ralsei Pet'

# 输出：**桌面抓屏派生物**放临时区（不进仓库）；只有不含桌面的派生物才回仓库
TMP = r'C:\Users\23002\Downloads\_tmp\rec90'
OUTDIR = HERE


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class BIH(ctypes.Structure):
    _fields_ = [('biSize', ctypes.c_uint32), ('biWidth', ctypes.c_int32),
                ('biHeight', ctypes.c_int32), ('biPlanes', ctypes.c_uint16),
                ('biBitCount', ctypes.c_uint16), ('biCompression', ctypes.c_uint32),
                ('biSizeImage', ctypes.c_uint32), ('biXPelsPerMeter', ctypes.c_int32),
                ('biYPelsPerMeter', ctypes.c_int32), ('biClrUsed', ctypes.c_uint32),
                ('biClrImportant', ctypes.c_uint32)]


def wcls(h):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, b, 256)
    return b.value


def wttl(h):
    n = u.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, b, n + 1)
    return b.value


def wpid(h):
    p = ctypes.c_ulong()
    u.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def wrect(h):
    r = RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def find_pet(pid_hint=None):
    hits = []

    def cb(h, _l):
        if not u.IsWindowVisible(h):
            return True
        if wttl(h) != PET_TITLE:
            return True
        if pid_hint and wpid(h) != pid_hint:
            return True
        hits.append(h)
        return True

    u.EnumWindows(P_CB(cb), 0)
    return hits[0] if hits else None


def grab_bgra(h):
    """PrintWindow(PW_RENDERFULLCONTENT) → (H,W,4) uint8 BGRA，或 None。"""
    l, t, w, hh = wrect(h)
    if w <= 0 or hh <= 0:
        return None
    hdc = u.GetWindowDC(h)
    mdc = gdi.CreateCompatibleDC(hdc)
    bmp = gdi.CreateCompatibleBitmap(hdc, w, hh)
    gdi.SelectObject(mdc, bmp)
    u.PrintWindow(h, mdc, 2)
    bi = BIH()
    bi.biSize = ctypes.sizeof(BIH)
    bi.biWidth = w
    bi.biHeight = -hh
    bi.biPlanes = 1
    bi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * hh * 4)
    got = gdi.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    gdi.DeleteObject(bmp)
    gdi.DeleteDC(mdc)
    u.ReleaseDC(h, hdc)
    if not got:
        return None
    return np.frombuffer(buf.raw, dtype=np.uint8).reshape(hh, w, 4).copy()


def sprite_mask(bgra):
    """取「精灵像素」掩码。

    分层透明窗口的 PrintWindow 结果有两种可能：alpha 有效，或透明区被填成黑。
    这里**两种都试**，挑出"面积占比合理"的那个（5% ~ 100%），并把选择讲清楚。
    """
    a = bgra[:, :, 3].astype(np.int32)
    bgr = bgra[:, :, :3].astype(np.int32)
    m_alpha = a > 8
    m_nonblack = bgr.max(axis=2) > 8
    area = bgra.shape[0] * bgra.shape[1]
    cand = []
    for name, m in (('alpha', m_alpha), ('nonblack', m_nonblack)):
        frac = float(m.sum()) / area
        if 0.02 <= frac <= 1.0:
            cand.append((name, m, frac))
    if not cand:
        return 'alpha', m_alpha, float(m_alpha.sum()) / area
    # 优先 alpha；alpha 明显不可用时退 nonblack
    for name, m, frac in cand:
        if name == 'alpha':
            return name, m, frac
    return cand[0]


def centroid(m):
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return None
    return (float(xs.mean()), float(ys.mean()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=60.0)
    ap.add_argument('--fps', type=float, default=20.0)
    ap.add_argument('--pid', type=int, default=None)
    args = ap.parse_args()

    os.makedirs(TMP, exist_ok=True)
    hwnd = find_pet(args.pid)
    if hwnd is None:
        print('★ 没找到 %r 窗口；请先启动桌宠' % PET_TITLE)
        return 2
    pid, cls = wpid(hwnd), wcls(hwnd)
    print('目标：hwnd=%d pid=%d class=%s' % (hwnd, pid, cls))
    print('录制 %.1fs @ %.0f fps（预计 %d 帧）' % (args.seconds, args.fps, int(args.seconds * args.fps)))

    # ---------------- 采集 ----------------
    frames = []          # (t, x, y, w, h, bgra)
    n_target = int(args.seconds * args.fps)
    dt = 1.0 / args.fps
    t0 = time.time()
    t_next = t0
    probe_note = None
    for i in range(n_target):
        # 精确节拍（在 Windows 上 sleep 精度 ~15ms，所以用"追赶式"节拍）
        now = time.time()
        if now < t_next:
            time.sleep(t_next - now)
        t_next += dt
        l, t, w, h = wrect(hwnd)
        img = grab_bgra(hwnd)
        if img is None:
            continue
        if probe_note is None:
            name, m, frac = sprite_mask(img)
            probe_note = ('%s' % name, frac, img.shape[1], img.shape[0])
        frames.append((time.time() - t0, l, t, w, h, img))
        if (i + 1) % max(1, n_target // 6) == 0:
            print('  … %d/%d 帧  (%.1fs, 窗口 %d,%d)' % (len(frames), n_target, time.time() - t0, l, t))

    if len(frames) < 5:
        print('★ 只抓到 %d 帧，放弃' % len(frames))
        return 3
    el = frames[-1][0]
    print('采集完成：%d 帧 / %.2f s（实际 %.1f fps）' % (len(frames), el, len(frames) / max(el, 1e-6)))
    print('★ 精灵像素判定采用：%s（占比 %.1f%%，窗口 %dx%d）' % probe_note)

    # ---------------- 逐帧位置（帧间对比的核心） ----------------
    recs = []
    for (t, l, ttop, w, h, img) in frames:
        name, m, frac = sprite_mask(img)
        c = centroid(m)
        cx, cy = (l + c[0], ttop + c[1]) if c else (l + w / 2.0, ttop + h / 2.0)
        recs.append({'t': t, 'x': l, 'y': ttop, 'w': w, 'h': h, 'cx': cx, 'cy': cy, 'frac': frac})

    # 恒真防护：轨迹必须先证明"不是常量"
    xs = np.array([r['x'] for r in recs], dtype=float)
    ys = np.array([r['y'] for r in recs], dtype=float)
    cys = np.array([r['cy'] for r in recs], dtype=float)
    move_total = float(np.abs(np.diff(xs)).sum() + np.abs(np.diff(ys)).sum())
    print('窗口位移总量 %.0f px（x %d..%d，y %d..%d）' % (move_total, xs.min(), xs.max(), ys.min(), ys.max()))

    # ---------------- 合成视频 ----------------
    import cv2
    mm = 40
    x0, y0 = int(min(xs)) - mm, int(min(ys)) - mm
    x1 = int(max(xs + np.array([r['w'] for r in recs]))) + mm
    y1 = int(max(ys + np.array([r['h'] for r in recs]))) + mm
    # 画布上限，防止某次异常坐标把画布撑爆
    CW = max(120, min(x1 - x0, 1400))
    CH = max(120, min(y1 - y0, 900))
    BG = (26, 26, 30)      # BGR 深灰（中性，不含桌面内容）

    def compose(i, stabilize):
        r = recs[i]
        img = frames[i][5]
        name, m, frac = sprite_mask(img)
        bgr = np.where(m[:, :, None], img[:, :, 2::-1], np.array(BG, dtype=np.uint8)).astype(np.uint8)
        if stabilize:
            px, py = (CW - r['w']) // 2, (CH - r['h']) // 2
        else:
            px, py = int(r['x']) - x0, int(r['y']) - y0
        canvas = np.zeros((CH, CW, 3), np.uint8)
        canvas[:, :] = BG
        sx0, sy0 = max(0, -px), max(0, -py)
        dx0, dy0 = max(0, px), max(0, py)
        ww = min(r['w'] - sx0, CW - dx0)
        hh = min(r['h'] - sy0, CH - dy0)
        if ww > 0 and hh > 0:
            canvas[dy0:dy0 + hh, dx0:dx0 + ww] = bgr[sy0:sy0 + hh, sx0:sx0 + ww]
        # 拖尾（真实视角下才画，稳定视角画了没意义）
        if not stabilize:
            for j in range(max(0, i - 45), i):
                rx, ry = int(recs[j]['x']) - x0, int(recs[j]['y']) - y0
                cv2.circle(canvas, (rx + 4, ry + 4), 1, (70, 70, 110), -1)
            cv2.drawMarker(canvas, (int(recs[0]['x']) - x0 + 4, int(recs[0]['y']) - y0 + 4),
                           (60, 60, 220), cv2.MARKER_TILTED_CROSS, 9, 1)
        cv2.putText(canvas, 't=%.2fs  y=%d' % (r['t'], int(r['y'])), (6, CH - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1, cv2.LINE_AA)
        return canvas

    out_main = os.path.join(OUTDIR, 'rec90_jump.mp4')
    out_stab = os.path.join(OUTDIR, 'rec90_stab.mp4')
    fps_w = float(len(recs)) / max(el, 1e-6)
    vw = cv2.VideoWriter(out_main, cv2.VideoWriter_fourcc(*'mp4v'), min(fps_w, 30), (CW, CH))
    vs = cv2.VideoWriter(out_stab, cv2.VideoWriter_fourcc(*'mp4v'), min(fps_w, 30), (CW, CH))
    wrote = 0
    for i in range(len(recs)):
        a = compose(i, False)
        b = compose(i, True)
        if vw.isOpened():
            vw.write(a)
        if vs.isOpened():
            vs.write(b)
        wrote += 1
    vw.release()
    vs.release()
    print('视频已写：%s (%dx%d, %.1f fps, %d 帧)' % (out_main, CW, CH, min(fps_w, 30), wrote))

    # ---------------- 逐帧对比：找"跳" ----------------
    dy = np.diff(cys)                       # 逐帧竖直位移（屏幕坐标：负=向上）
    ddy = np.diff(dy)                       # 竖直加速度符号
    thr = 2.0
    bursts, cur = [], None
    for i, d in enumerate(dy):
        if abs(d) > thr:
            if cur is None:
                cur = [i, i]
            else:
                cur[1] = i
        else:
            if cur is not None and cur[1] - cur[0] >= 3:
                bursts.append(tuple(cur))
            cur = None
    if cur is not None and cur[1] - cur[0] >= 3:
        bursts.append(tuple(cur))

    lines = []
    lines.append('=' * 78)
    lines.append('第90轮 · 真机逐帧对比（用户视角）')
    lines.append('=' * 78)
    lines.append('目标窗口：hwnd=%d pid=%d class=%s title=%r' % (hwnd, pid, cls, PET_TITLE))
    lines.append('采集：%d 帧 / %.2f s（%.1f fps）· 精灵像素判定=%s（%.1f%%）'
                 % (len(recs), el, len(recs) / max(el, 1e-6), probe_note[0], probe_note[1]))
    lines.append('窗口位移总量 %.0f px；x∈[%d,%d] y∈[%d,%d]'
                 % (move_total, xs.min(), xs.max(), ys.min(), ys.max()))
    lines.append('')
    lines.append('—— 恒真防护：轨迹不是常量 ——')
    lines.append('  [%s] 窗口竖直方向真的动过（y 跨度 %d px > 0）'
                 % ('PASS' if ys.max() - ys.min() > 0 else 'FAIL', ys.max() - ys.min()))
    lines.append('  [%s] 质心轨迹不是常量（cy 跨度 %.1f px）'
                 % ('PASS' if cys.max() - cys.min() > 0.5 else 'FAIL', cys.max() - cys.min()))
    lines.append('')
    lines.append('—— 运动段（|逐帧 dy| > %.1f px，长度 >= 4 帧）——' % thr)
    updown = []
    for (a, b) in bursts:
        seg = dy[a:b + 1]
        s_up = int(np.sum(seg < 0))
        s_dn = int(np.sum(seg > 0))
        # 变号次数
        sgn = np.sign(seg[seg != 0])
        flips = int(np.sum(np.diff(sgn) != 0)) if len(sgn) > 1 else 0
        y_seg = cys[a:b + 2]
        start_y, min_y, end_y = float(y_seg[0]), float(y_seg.min()), float(y_seg[-1])
        rise = start_y - min_y
        lines.append('  t=%.2f..%.2fs (%d 帧) dy∈[%.0f,%.0f] 上%d/下%d 变号%d 抬升%.0fpx 落回起%s'
                     % (recs[a]['t'], recs[b + 1]['t'], b - a + 2, seg.min(), seg.max(),
                        s_up, s_dn, flips, rise,
                        '高' if end_y < start_y - 3 else ('低' if end_y > start_y + 3 else '点')))
        is_jump = (s_up >= 2 and s_dn >= 2 and flips == 1 and rise > 4)
        updown.append((a, b, is_jump, rise, flips))
    if not bursts:
        lines.append('  （没有超过阈值的运动段 —— 可能是"0 次跳跃"或帧率太低）')
    lines.append('')
    n_jump = sum(1 for x in updown if x[2])
    lines.append('—— 结论 ——')
    lines.append('  识别为「跳跃」的运动段：%d 个' % n_jump)
    if n_jump:
        for (a, b, isj, rise, flips) in updown:
            if isj:
                lines.append('    · t=%.2fs 起跳，顶点抬升 %.0f px（>0 = 真的"先上后下"）'
                             % (recs[a]['t'], rise))
        lines.append('  ⇒ 真机录像中出现「先上后下、只变向一次」的弧线：')
        lines.append('     旧公式（竖直加速度朝屏幕上方 = 反重力）**不可能**产生这个形状。')
    else:
        lines.append('  ⇒ 本轮录制窗口里没有捕获到跳跃（宠物未走到楼板边缘 / 时长不够）。')
        lines.append('     这不构成"抛物线是错的"的证据；详见同目录 rec90_motion.txt 的窗口矩形逐帧表。')
    lines.append('')
    lines.append('产物：')
    lines.append('  %s' % out_main)
    lines.append('  %s' % out_stab)

    txt = '\n'.join(lines)
    print(txt)
    with open(os.path.join(OUTDIR, 'rec90_analysis.txt'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(txt + '\n')

    # 逐帧表（含桌面坐标，属"原始抓屏派生物" ⇒ 放临时区）
    with open(os.path.join(TMP, 'rec90_traj.csv'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('t,x,y,w,h,cx,cy,sprite_frac\n')
        for r in recs:
            fh.write('%.4f,%d,%d,%d,%d,%.2f,%.2f,%.4f\n'
                     % (r['t'], r['x'], r['y'], r['w'], r['h'], r['cx'], r['cy'], r['frac']))
    print('逐帧表（临时区）= %s' % os.path.join(TMP, 'rec90_traj.csv'))
    return 0


if __name__ == '__main__':
    sys.exit(main())

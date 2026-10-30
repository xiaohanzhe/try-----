# -*- coding: utf-8 -*-
u"""alpha117_pick.py —— 用**真机录像**反解出「渐显下限该取多少」，而不是凭手调。

问题（第117轮录屏逐帧发现的第 2 条）
------------------------------------
门 C/D 是渐显门（`door_reveal`，用户第112轮口径「检测到实体靠近后才从透明到实象」）。
录屏实测它们在**宠物远离**时 alpha 只有 **0.14 / 0.29**，代价是：

    `doors117_track_D.png` 八格**全是壁纸** —— 门 D 在壁纸上几乎看不见。

⇒ 「大一点都」把门放大了 1.01 倍，但视觉收益被渐显抵消。下限 `MIN_ALPHA = 0.14`
   是第112轮拍的板（「留一丝幽灵般的可见度」），当时**没有真机像素证据**。

怎么给出证据（不猜、不手调）
----------------------------
屏幕上那块像素是**合成**出来的（`scene_canvas` 用 `drawPixmap` + `setOpacity`）：

    frame = tex × a + bg × (1 - a)

`tex`（贴图 RGB）与 `a`（该帧真实 alpha，来自 `rec117_frames.csv` 的内省值）都已知
⇒ **可以精确反解背景**：

    bg = (frame - a × tex) / (1 - a)

反解出的 `bg` = "如果没有这扇门，那块屏幕长什么样"。然后对任意候选下限 `a2`
重新合成 `comp = tex × a2 + bg × (1 - a2)`，量 **comp 与 bg 的**感知色差 `ΔE`（CIE76，
sRGB→XYZ→Lab）。ΔE 是**色相也参与**的量 —— 这一步很关键：门 D 是**金框**，它和
背景的差别主要在**颜色**不在亮度（实测亮度几乎相等 ⇒ 只量亮度会得出"怎么调都看不见"
的荒谬结论，第一版就栽在这里，见文末"两个坑"）。

判据取 **ΔE ≥ 10**：CIE 里 ΔE≈2.3 是"刚能察觉"，10 是"非专业人士一眼看出" ⇒ 留足余量。

★★★ 采样帧必须干净（第一版的两个坑）
------------------------------------
1. **宠物站在门前**：门 D 在右边缘中部，宠物走过去时会盖住它 ⇒ 反解出的"背景"
   里混进宠物 ⇒ 同一块壁纸一会儿 L=90、一会儿 L=210（实测）。⇒ 只取
   **宠物矩形与门矩形不相交**的帧。
2. **相位搜错了**：代码原先写 `r['phase'] == '2'`，而 CSV 里是 `'P1'/'P2'`
   ⇒ 搜索恒失败、静默退回"最后一帧"（可能就是宠物站门口那帧）。⇒ 改 `'P2'`，
   并且**找不到就报错退出**（不许静默退回）。
3. 只取 `dlg_vis == '0'` 的帧（对话框是不透明 UI，会整块盖住门）。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第117轮-门贴图黑光与放大\\_tools\\alpha117_pick.py
"""
import csv
import io
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
ASSETS = os.path.join(PKG, 'assets', 'scenes')
OUT = os.path.join(ROUND, '_evidence', 'rec117')
AVI = os.path.join(OUT, 'rec117.avi')
CSV_F = os.path.join(OUT, 'rec117_frames.csv')

SPRITE = {'C': 'objs/desk_door_ut.png', 'D': 'objs/desk_door_deltarune.png'}
CANDIDATES = (0.14, 0.25, 0.35, 0.45, 0.50, 0.60)
NEED_DE = 10.0          # 判据：一眼看得出（CIE76 ΔE，见 docstring）


# ------------------------------------------------------------------ 色差
def srgb_to_lab(rgb):
    u"""`(...,3)` 的 0..255 sRGB ⇒ CIE Lab（D65，CIE76 的底子）。"""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ m.T
    wp = np.array([0.95047, 1.00000, 1.08883])
    t = xyz / wp
    d = 6.0 / 29.0
    f = np.where(t > d ** 3, np.cbrt(t), t / (3 * d * d) + 4.0 / 29.0)
    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def delta_e(a_rgb, b_rgb):
    u"""逐像素 CIE76 ΔE。"""
    la = srgb_to_lab(np.clip(a_rgb, 0, 255))
    lb = srgb_to_lab(np.clip(b_rgb, 0, 255))
    return np.sqrt(((la - lb) ** 2).sum(axis=-1))


# ------------------------------------------------------------------ 像素工具
def erase(mask, n=1):
    u"""二值掩膜腐蚀 n 圈（纯 numpy 移位与，不依赖 cv2）。"""
    m = mask.copy()
    for _ in range(n):
        m = (m & np.roll(m, 1, 0) & np.roll(m, -1, 0)
             & np.roll(m, 1, 1) & np.roll(m, -1, 1))
        m[0, :] = m[-1, :] = False
        m[:, 0] = m[:, -1] = False
    return m


def load_tex(sid, w, h):
    u"""贴图按 **NEAREST** 缩放到门的屏幕尺寸（产品就是最近邻，见 §117.9）。"""
    im = Image.open(os.path.join(ASSETS, SPRITE[sid])).convert('RGBA')
    im = im.resize((int(w), int(h)), Image.NEAREST)
    a = np.asarray(im, dtype=np.float64)
    return a[:, :, :3], erase(a[:, :, 3] >= 250, 1)


def _rect(r, k):
    try:
        return (int(r['%s_x' % k]), int(r['%s_y' % k]),
                int(r['%s_w' % k]), int(r['%s_h' % k]))
    except (KeyError, TypeError, ValueError):
        return None


def _overlap(a, b):
    if not a or not b:
        return 0
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return max(0, x1 - x0) * max(0, y1 - y0)


def main():
    rows = list(csv.DictReader(io.open(CSV_F, 'r', encoding='utf-8')))
    import cv2
    cap = cv2.VideoCapture(AVI)
    frames = []
    while True:
        got, f = cap.read()
        if not got:
            break
        frames.append(f[:, :, ::-1].astype(np.float64))   # BGR ⇒ RGB
    cap.release()
    print('帧数 csv=%d avi=%d' % (len(rows), len(frames)))
    if len(frames) != len(rows):
        print('!! 帧数与 CSV 不等 ⇒ 无法逐帧对齐，停止（不猜）')
        sys.exit(2)

    report = {'metric': 'CIE76 dE (threshold %.1f)' % NEED_DE, 'doors': {}}
    for sid in ('C', 'D'):
        rect = _rect(rows[0], sid)
        # 干净帧：P2 + 对话框不在 + **宠物不压在门上**
        clean = []
        for i, r in enumerate(rows):
            if r.get('phase') != 'P2' or r.get('dlg_vis') != '0':
                continue
            pet = (int(r['pet_x']), int(r['pet_y']), int(r['pet_w']), int(r['pet_h'])) \
                if r.get('pet_x') else None
            if _overlap(rect, pet):
                continue
            clean.append(i)
        if not clean:
            print('!! 门 %s 没有干净帧（P2+无对话框+宠物不压门）—— 停止（不猜）' % sid)
            sys.exit(3)
        idx = clean[-1]                       # 最后一帧最稳（渐显可能还在动，取尾）
        print('\n=== 门 %s  rect=%s  采样帧 %d（干净帧 %d 个：%s）'
              % (sid, rect, idx, len(clean), clean[:3] + (['...'] if len(clean) > 3 else [])))

        r = rows[idx]
        x, y, w, h = rect
        a_now = float(r['%s_alpha' % sid])
        frame = frames[idx][y:y + h, x:x + w]
        tex, m = load_tex(sid, w, h)
        if frame.shape[:2] != tex.shape[:2] or not m.any():
            print('!! 形状/掩膜不对（frame=%s tex=%s mask=%d）—— 跳过'
                  % (frame.shape[:2], tex.shape[:2], int(m.sum())))
            sys.exit(4)
        if a_now >= 0.90:
            print('!! 该帧 alpha=%.3f 接近全实，无法反解背景 —— 跳过' % a_now)
            sys.exit(5)
        bg = np.clip((frame - a_now * tex) / (1.0 - a_now), 0.0, 255.0)

        t_mean = tex[m].mean(axis=0)
        b_mean = bg[m].mean(axis=0)
        row = {'rect': list(rect), 'frame': idx, 'clean_frames': len(clean),
               'alpha_now': round(a_now, 4), 'n_px': int(m.sum()),
               'tex_rgb': [round(float(v), 1) for v in t_mean],
               'bg_rgb': [round(float(v), 1) for v in b_mean],
               'bg_std_lum': round(float((0.299 * bg[..., 0] + 0.587 * bg[..., 1]
                                          + 0.114 * bg[..., 2])[m].std()), 2),
               'cands': []}
        print('    贴图 RGB=%s ｜ 反解背景 RGB=%s（背景亮度 std=%.1f）'
              % (row['tex_rgb'], row['bg_rgb'], row['bg_std_lum']))
        print('    %-6s %-22s %-8s %s' % ('a', '合成 RGB', 'ΔE', '达成'))
        pick = None
        for a2 in CANDIDATES:
            comp = tex * a2 + bg * (1.0 - a2)
            de = float(delta_e(comp, bg)[m].mean())
            good = de >= NEED_DE
            if good and pick is None:
                pick = a2
            row['cands'].append({'a': a2, 'dE': round(de, 2), 'ok': bool(good),
                                 'comp_rgb': [round(float(v), 1)
                                              for v in comp[m].mean(axis=0)]})
            print('    %-6.2f %-22s %-8.1f %s'
                  % (a2, str([round(float(v), 1) for v in comp[m].mean(axis=0)]),
                     de, 'PASS' if good else '-'))
        row['pick'] = pick
        report['doors'][sid] = row
        print('    ⇒ 最小达标 alpha = %s' % pick)

    picks = [v['pick'] for v in report['doors'].values() if v['pick'] is not None]
    report['pick_unified'] = max(picks) if picks else None
    print('\n=== 结论：两扇门里要求最高的那个候选 = %s' % report['pick_unified'])

    p = os.path.join(OUT, 'alpha117_pick.json')
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=2))
    print('written %s' % p)


if __name__ == '__main__':
    main()

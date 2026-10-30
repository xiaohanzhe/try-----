# -*- coding: utf-8 -*-
u"""shots118_from_avi.py —— 从**现成的** `rec118.avi` 重出 1:1 裁图（不重录）。

为什么要这个文件
----------------
`rec118.py` 第一版存 PNG 时把 **BGR 当 RGB** 用了
（`QImage.grabWindow()` → `Format_RGB32` → 内存 BGRA、小端）
⇒ 裁图里**红蓝颠倒**。最直接的证据：`spr_heart_0.png` 是纯红 `(255,0,0)`
（188 个不透明像素全红），而裁图里那颗心量出来是纯蓝 `(0,0,255)`。
**这不是产品的 bug，是我的取证管线的 bug。**

⇒ 修 `rec118.py` 的 `_shot()` 之外，还必须把**已经录好的这条片子**重出一遍，
   否则报告里贴的图仍然是错的（而且如果只看图，会得出"红心是蓝的"这种假结论）。

★ 为什么不用重录：`rec118.avi` 是走 `cv2.VideoWriter` 写的，**它要的就是 BGR**，
  ⇒ 视频本身颜色是对的。只是 PNG 那一步错了。重出即可，不必再折腾一遍桌面。

★ 顺带做一件"图案层面"的取证：**逐模态帧量红心的 y 质心**——
  默认态应停在第 2 行（y 大），按 ↑ 之后应移到第 1 行（y 小）。
  这条判据不读任何字符串，只看**红像素在哪一行**。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\shots118_from_avi.py
"""
import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROUND, '_evidence', 'rec118')
SHOTS = os.path.join(OUT, 'shots')
os.makedirs(SHOTS, exist_ok=True)

import cv2                                                       # noqa: E402
import numpy as np                                               # noqa: E402
from PIL import Image                                            # noqa: E402

AVI = os.path.join(OUT, 'rec118.avi')
CSV = os.path.join(OUT, 'rec118_frames.csv')
if not (os.path.isfile(AVI) and os.path.isfile(CSV)):
    sys.stdout.write('!! 缺 %s 或 %s\n' % (AVI, CSV))
    sys.exit(2)

ROWS = []
with io.open(CSV, encoding='utf-8', newline='') as f:
    for r in csv.DictReader(f):
        ROWS.append(r)


def num(r, k, d=0):
    v = r.get(k, '')
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


L = []


def say(m):
    L.append(m)
    sys.stdout.write(m + '\n')
    sys.stdout.flush()


cap = cv2.VideoCapture(AVI)
N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
say('avi 帧数 = %d，csv 行数 = %d' % (N, len(ROWS)))
if N <= 0:
    say('!! avi 打不开')
    sys.exit(2)


def frame_at(i):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
    ok, fr = cap.read()
    return fr if ok else None


def save(name, fr, box=None, max_w=1400):
    sub = fr
    if box is not None:
        x, y, w, h = [int(v) for v in box]
        hh, ww = fr.shape[0], fr.shape[1]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(ww, x + w), min(hh, y + h)
        if x1 > x0 and y1 > y0:
            sub = fr[y0:y1, x0:x1]
    im = Image.fromarray(np.ascontiguousarray(sub[:, :, ::-1]))    # BGR → RGB
    if box is None and im.width > max_w:
        im = im.resize((max_w, int(im.height * max_w / float(im.width))),
                       Image.LANCZOS)
    p = os.path.join(SHOTS, name + '.png')
    im.save(p)
    say('  → %-28s %dx%d' % (name + '.png', im.width, im.height))
    return p


def ctx(box, m=40):
    return (box[0] - m, box[1] - m, box[2] + m * 2, box[3] + m * 2)


# ---------------------------------------------------------------- ① 全景
pano = [i for i, r in enumerate(ROWS) if r['step'] == 'P0_pano']
if pano:
    fr = frame_at(pano[-1])
    if fr is not None:
        save('pano_2560x1600', fr)

# ---------------------------------------------------------------- ② 四门 1:1
for L2 in 'ABCD':
    idx = [i for i, r in enumerate(ROWS)
           if r['step'].startswith('P%s_' % (('A', 'C', 'D', 'B').index(L2) + 1))
           and r['step'].endswith('_hold')]
    if not idx:
        say('!! 门 %s 没有 hold 帧' % L2)
        continue
    r = ROWS[idx[-1]]
    box = (num(r, '%s_x' % L2), num(r, '%s_y' % L2),
           num(r, '%s_w' % L2), num(r, '%s_h' % L2))
    if box[2] <= 0 or box[3] <= 0:
        say('!! 门 %s 矩形缺失' % L2)
        continue
    fr = frame_at(idx[-1])
    if fr is None:
        continue
    # ★ 门的"外接上下文"不能超出画面：负坐标会被裁掉，这里只报告不动几何
    say('门 %s 矩形=%s（屏 %dx%d）' % (L2, tuple(int(v) for v in box),
                                    fr.shape[1], fr.shape[0]))
    save('door_%s_1to1' % L2, fr, ctx(box))


# ---------------------------------------------------------------- ③ 选择框
def heart_y(fr, box):
    u"""框内**纯红**像素的 y 质心（BGR 下红 = R 高、G/B 低）。"""
    x, y, w, h = [int(v) for v in box]
    hh, ww = fr.shape[0], fr.shape[1]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(ww, x + w), min(hh, y + h)
    if x1 <= x0 or y1 <= y0:
        return None
    sub = fr[y0:y1, x0:x1].astype(int)
    b, g, r = sub[:, :, 0], sub[:, :, 1], sub[:, :, 2]
    m = (r > 180) & (g < 70) & (b < 70)
    n = int(m.sum())
    if n < 12:
        return None
    ys, xs = np.nonzero(m)
    return (float(ys.mean()) + y0, float(xs.mean()) + x0, n)


modal = [i for i, r in enumerate(ROWS) if r.get('modal') == '1']
say('模态帧 %d 个' % len(modal))
seen = []
for i in modal:
    r = ROWS[i]
    box = (num(r, 'dlg_x'), num(r, 'dlg_y'), num(r, 'dlg_w'), num(r, 'dlg_h'))
    fr = frame_at(i)
    if fr is None:
        continue
    hy = heart_y(fr, box)
    seen.append((i, hy))
    say('  frame %3d t=%-7s 红心=%s' % (i, r.get('t'), None if hy is None
                                        else '(y=%.1f x=%.1f n=%d)' % hy))
ok = [(i, hy) for i, hy in seen if hy is not None]
if not ok:
    say('!! 模态帧里找不到红心（红像素不足）')
else:
    # 默认态 = 红心最靠下；移动后 = 红心最靠上
    lo = max(ok, key=lambda t: t[1][0])
    hi = min(ok, key=lambda t: t[1][0])
    say('红心最靠下 = frame %d（y=%.1f）⇒ 默认态；最靠上 = frame %d（y=%.1f）⇒ 按过 ↑'
        % (lo[0], lo[1][0], hi[0], hi[1][0]))
    r = ROWS[lo[0]]
    box = (num(r, 'dlg_x'), num(r, 'dlg_y'), num(r, 'dlg_w'), num(r, 'dlg_h'))
    fr = frame_at(lo[0])
    if fr is not None:
        save('choice_1to1_default', fr,
             (box[0] - 30, box[1] - 30, box[2] + 60, box[3] + 60))
    r = ROWS[hi[0]]
    box = (num(r, 'dlg_x'), num(r, 'dlg_y'), num(r, 'dlg_w'), num(r, 'dlg_h'))
    fr = frame_at(hi[0])
    if fr is not None:
        save('choice_1to1_moved', fr,
             (box[0] - 30, box[1] - 30, box[2] + 60, box[3] + 60))
    say('红心纵向位移 = %.1f px（>8 px 才算"真的换行"，两行行距约 34×scale）'
        % (lo[1][0] - hi[1][0]))

cap.release()
say('done')

# -*- coding: utf-8 -*-
u"""ab117_alpha.py —— 出「同一帧、不同 alpha」的**1:1 对照图**，用来判定"门到底看不看得见"。

为什么需要它
------------
`doors117_track_D.png` 是**逐门竖直条**（182 px 宽、按 8 帧拼起来后被我看成"全是壁纸"）。
那是**缩略判据**：门 D 的金框只占矩形的 **17.5%**，在拼图里被压掉 ⇒ 容易得出
"看不见"的**误判**。本脚本改用**未缩放、带上下文的 1:1 裁图**，并直接把
alpha 0.14 / 0.29 / 0.50 / 1.00 四种情形并排放在**同一张壁纸背景上**。

做法（数学上等价于产品绘制）
----------------------------
1. 取真机一帧（`rec117.avi` 尾帧，P2、无对话框、宠物不压门）；
2. 用该帧内省 alpha `a_now` 反解背景 `bg = (frame - a*tex)/(1-a)`；
3. 对 `a2 ∈ {0.14, 0.29, 0.50, 1.00}` 重新合成 `comp = tex*a2 + bg*(1-a2)`；
4. 裁门矩形 + 四周 80 px 上下文，四张竖排，左侧标字。

⇒ 这张图就是"如果下限是 X，桌面上那块长什么样"的**事实**，不依赖任何阈值。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第117轮-门贴图黑光与放大\\_tools\\ab117_alpha.py
"""
import csv
import io
import os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
ASSETS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
OUT = os.path.join(ROUND, '_evidence', 'rec117')
AVI = os.path.join(OUT, 'rec117.avi')
CSV_F = os.path.join(OUT, 'rec117_frames.csv')

SPRITE = {'C': 'objs/desk_door_ut.png', 'D': 'objs/desk_door_deltarune.png'}
ALPHAS = (0.14, 0.29, 0.50, 1.00)
PAD = 80


def erase(mask, n=1):
    m = mask.copy()
    for _ in range(n):
        m = (m & np.roll(m, 1, 0) & np.roll(m, -1, 0)
             & np.roll(m, 1, 1) & np.roll(m, -1, 1))
        m[0, :] = m[-1, :] = False
        m[:, 0] = m[:, -1] = False
    return m


def main():
    rows = list(csv.DictReader(io.open(CSV_F, 'r', encoding='utf-8')))
    import cv2
    cap = cv2.VideoCapture(AVI)
    frames = []
    while True:
        got, f = cap.read()
        if not got:
            break
        frames.append(f[:, :, ::-1].astype(np.float64))
    cap.release()
    idx = len(rows) - 1
    print('采样帧 %d / 共 %d' % (idx, len(rows)))

    for sid in ('C', 'D'):
        r = rows[idx]
        x, y, w, h = (int(r['%s_x' % sid]), int(r['%s_y' % sid]),
                      int(r['%s_w' % sid]), int(r['%s_h' % sid]))
        a_now = float(r['%s_alpha' % sid])
        im = Image.open(os.path.join(ASSETS, SPRITE[sid])).convert('RGBA').resize(
            (w, h), Image.NEAREST)
        arr = np.asarray(im, dtype=np.float64)
        tex, alpha = arr[:, :, :3], arr[:, :, 3]
        m = erase(alpha >= 250, 1)

        frame = frames[idx]
        sub = frame[y:y + h, x:x + w]
        bg = np.clip((sub - a_now * tex) / (1.0 - a_now), 0.0, 255.0)

        # 上下文：把门"抠掉"还原成背景后的整块（含四周 PAD）
        y0, y1 = max(0, y - PAD), min(frame.shape[0], y + h + PAD)
        x0, x1 = max(0, x - PAD), min(frame.shape[1], x + w + PAD)
        ctx = frame[y0:y1, x0:x1].copy()
        # 门所在矩形替换成反解背景 ⇒ 得到"没有门"的底图（贴图透明处本就透出背景，
        # 所以直接把整块换成 bg 是**等价**的：那里的屏幕像素本来就该 = bg）
        ctx[y - y0:y - y0 + h, x - x0:x - x0 + w] = bg

        tiles = []
        af = alpha[:, :, None] / 255.0          # 贴图自身的 alpha（门形状的边界）
        for a2 in ALPHAS:
            tile = ctx.copy()
            comp = tex * a2 + bg * (1.0 - a2)
            blend = bg * (1.0 - af) + comp * af
            tile[y - y0:y - y0 + h, x - x0:x - x0 + w] = blend
            tiles.append(tile)

        th, tw = tiles[0].shape[:2]
        canvas = Image.new('RGB', (tw, (th + 26) * len(tiles)), (20, 20, 24))
        dr = ImageDraw.Draw(canvas)
        for i, t in enumerate(tiles):
            yy = i * (th + 26)
            canvas.paste(Image.fromarray(t.astype(np.uint8)), (0, yy + 26))
            dr.text((6, yy + 7), 'door %s   alpha = %.2f   (context %d px, 1:1, no rescale)'
                    % (sid, ALPHAS[i], PAD), fill=(230, 230, 230))
        p = os.path.join(OUT, 'ab117_alpha_%s.png' % sid)
        canvas.save(p)
        print('written %s  %dx%d' % (p, canvas.width, canvas.height))


if __name__ == '__main__':
    main()

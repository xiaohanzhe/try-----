# -*- coding: utf-8 -*-
u"""make_doorY99.py —— 第99轮：生成桌面第 9 扇门贴图 `spr_doorY_0.png`。

为什么需要它 / 依据是什么
------------------------
实测 `spr_doorA~F/W/X_0.png` 的结构（`probe99x` 逐像素）：**每张 20×20**，
= ① **蓝色方框** `#0000ff`（一圈 76 px + 第 1 行左起 6 px 的**铰链凸块** = 81 px）
  + ② **绿色像素字母**（A~F 用 `#40ff40`，X 用 `#1cf400`）。
⇒ **门贴图本来就是"框 + 字母"**，不是图画。所以第 9 扇门也必须是一个**字母 Y**。

做法（把"自绘"压到最小）
----------------------
* **方框逐像素复制自 `spr_doorA_0.png`** —— 边框不是本项目画的，是原作像素；
* **Y 字模**用 2 px 线宽手写（与原作字母同款笔画粗细），颜色取多数派的 `#40ff40`；
* 字母包围盒对齐 `spr_doorA_0.png` 实测的 `x∈[5,14] × y∈[4,16]`（10×13）。

★ 诚实登记：**这是一个"混合来源"贴图** —— 边框=原作、字母=本项目绘制。
  Outertale 原作没有 `obj_doorY`（这正是我们要新增的入口），
  所以不存在"照抄一张 Y 门"的可能；抄边框 + 同规格手写字模是**最接近原作**的做法。
"""
import io
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(ROUND, u'..', u'..'))
OBJS = os.path.join(REPO, u'ralsei_pet', u'assets', u'scenes', u'objs')

SRC_A = os.path.join(OBJS, u'spr_doorA_0.png')
DST = os.path.join(OBJS, u'spr_doorY_0.png')
PREVIEW_CANDIDATES = [
    u'E:\\Download\\_tmp\\doorY_preview.png',
    os.path.join(ROUND, u'_evidence', u'doorY_preview.png'),
]

#: ★ 注意通道序：`cv2` 的 4 通道数组是 **BGRA**，而 `#0000ff` 是 **RGB** 三元组。
#:   所以"纯蓝"在 BGRA 里是 `(255, 0, 0, 255)`（b=255）—— 首版我把前两位写成了
#:   `(0, 0, 255, 255)`（= 红），被末尾的自证判据（`n_frame == 81`）当场抓出。
FRAME = (255, 0, 0, 255)      # BGRA：纯蓝（RGB `#0000ff`）
GLYPH = (64, 255, 64, 255)    # BGRA：RGB `#40ff40`（A~F 的绿）

#: Y 字模（10 宽 × 13 高）—— 列 = x5..x14、行 = y4..y16，
#: **与 `spr_doorA_0.png` 实测的字形包围盒逐位对齐**（自证判据会查这一条）。
#: `.` 空 / `#` 实；线宽 1 px（与 A 的笔画一致）。
Y_ROWS = [
    u'#........#',
    u'#........#',
    u'.#......#.',
    u'.#......#.',
    u'..#....#..',
    u'..#....#..',
    u'...#..#...',
    u'....##....',
    u'....##....',
    u'....##....',
    u'....##....',
    u'....##....',
    u'....##....',
]


def read_png(p):
    with io.open(p, 'rb') as fh:
        b = fh.read()
    return cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_UNCHANGED)


def to_bgra(img):
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    if img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    return img


def main():
    if not os.path.isfile(SRC_A):
        print(u'!! 缺 %s' % SRC_A)
        return 2
    a = to_bgra(read_png(SRC_A))
    h, w = a.shape[:2]
    print(u'[src] spr_doorA_0.png %dx%d' % (w, h))
    if (w, h) != (20, 20):
        print(u'!! 预期 20x20，实得 %dx%d，停止（不猜）' % (w, h))
        return 2

    # ---- ① 方框：逐像素复制 A 的蓝色像素 ----
    canvas = np.zeros((h, w, 4), np.uint8)
    n_frame = 0
    for y in range(h):
        for x in range(w):
            b, g, r, al = a[y, x]
            if al > 0 and b > 200 and g < 60 and r < 60:
                canvas[y, x] = FRAME
                n_frame += 1
    print(u'[frame] 复制蓝色像素 %d 个（A 的门框）' % n_frame)

    # ---- ② Y 字模 ----
    x0, y0 = 5, 4
    n_glyph = 0
    for dy, row in enumerate(Y_ROWS):
        for dx, ch in enumerate(row):
            if ch == u'#':
                yy, xx = y0 + dy, x0 + dx
                if 0 <= yy < h and 0 <= xx < w:
                    canvas[yy, xx] = GLYPH
                    n_glyph += 1
    print(u'[glyph] 写入 Y 字模 %d 个像素（x%d..y%d）'
          % (n_glyph, x0, y0))

    # ---- ③ 自证：包围盒与 A 的字形对齐 ----
    ga = np.argwhere((a[:, :, 3] > 0)
                     & ~((a[:, :, 0] > 200) & (a[:, :, 1] < 60) & (a[:, :, 2] < 60)))
    gn = np.argwhere((canvas[:, :, 3] > 0)
                     & ~((canvas[:, :, 0] > 200) & (canvas[:, :, 1] < 60)
                         & (canvas[:, :, 2] < 60)))
    ba = (ga[:, 1].min(), ga[:, 0].min(), ga[:, 1].max(), ga[:, 0].max())
    bn = (gn[:, 1].min(), gn[:, 0].min(), gn[:, 1].max(), gn[:, 0].max())
    print(u'[box] A 字形包围盒 x%d..%d y%d..%d' % (ba[0], ba[2], ba[1], ba[3]))
    print(u'[box] Y 字形包围盒 x%d..%d y%d..%d' % (bn[0], bn[2], bn[1], bn[3]))

    ok, buf = cv2.imencode(u'.png', canvas)
    if not ok:
        print(u'!! imencode 失败')
        return 1
    with io.open(DST, 'wb') as fh:
        fh.write(buf.tobytes())
    print(u'[out] %s  %d B' % (DST, len(buf.tobytes())))
    back = to_bgra(read_png(DST))
    print(u'[check] 读回 %dx%d ch=%d' % (back.shape[1], back.shape[0], back.shape[2]))

    # ---- ④ 对照图（给人眼看）----
    tiles = []
    for name in (u'A', u'B', u'C', u'D', u'E', u'F', u'W', u'X', u'Y'):
        p = os.path.join(OBJS, u'spr_door%s_0.png' % name)
        if not os.path.isfile(p):
            continue
        im = to_bgra(read_png(p))
        big = cv2.resize(im, (im.shape[1] * 8, im.shape[0] * 8),
                         interpolation=cv2.INTER_NEAREST)
        al = big[:, :, 3:4].astype(np.float32) / 255.0
        rgb = big[:, :, :3].astype(np.float32)
        big = (rgb * al + np.full_like(rgb, 205.0) * (1 - al)).astype(np.uint8)
        band = np.full((26, big.shape[1], 3), 30, np.uint8)
        cv2.putText(band, u'%s %dx%d' % (name, im.shape[1], im.shape[0]), (4, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(np.vstack([band, big]))
    if tiles:
        hm = max(t.shape[0] for t in tiles)
        pad = [np.vstack([t, np.zeros((hm - t.shape[0], t.shape[1], 3), np.uint8)])
               if t.shape[0] < hm else t for t in tiles]
        merged = pad[0]
        for t in pad[1:]:
            merged = np.hstack([merged, np.full((hm, 8, 3), 70, np.uint8), t])
        ok2, buf2 = cv2.imencode(u'.png', merged)
        if ok2:
            for cand in PREVIEW_CANDIDATES:
                try:
                    d = os.path.dirname(cand)
                    if d and not os.path.isdir(d):
                        os.makedirs(d)
                    with io.open(cand, 'wb') as fh:
                        fh.write(buf2.tobytes())
                    print(u'[preview] %s (%dx%d)'
                          % (cand, merged.shape[1], merged.shape[0]))
                    break
                except Exception as e:
                    print(u'[preview] 写 %s 失败：%r' % (cand, e))

    bad = []
    want_glyph = sum(row.count(u'#') for row in Y_ROWS)
    if n_frame != 81:
        bad.append(u'门框像素 %d != 81' % n_frame)
    if n_glyph != want_glyph:
        bad.append(u'字形像素 %d != 字模算出的 %d' % (n_glyph, want_glyph))
    if bn != ba:
        bad.append(u'Y 字形包围盒 %r != A 的 %r（未对齐）' % (bn, ba))
    print(u'[结果] %s' % (u'PASS' if not bad else u'FAIL %r' % bad))
    return 0 if not bad else 1


if __name__ == u'__main__':
    sys.exit(main())

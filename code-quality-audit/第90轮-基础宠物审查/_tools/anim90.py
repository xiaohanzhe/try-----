# -*- coding: utf-8 -*-
u"""第90轮：把「可能是他睡觉动画」的候选素材拼成一张对照图（便于用户指认）。

只读素材、只写图（纯精灵，不含桌面）⇒ 可入库。
用法：python anim90.py
"""
import glob
import os

import cv2
import numpy as np

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
SPR = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\deltarune_ralsei'
OUT = os.path.join(ROUND, 'rec90_anim_candidates.png')

# (标签, glob)  —— 每个 glob 里所有帧都会画出来
CAND = [
    ('sleep 组(sprite_loader 登记的)', 'spr_ralsei_walk_down_sleep_*.png'),
    ('board_ralsei_sleep', 'spr_board_ralsei_sleep_*.png'),
    ('walk_down（对照：清醒朝下走）', 'spr_ralsei_walk_down_0.png'),
    ('sit（4 帧）', 'spr_ralsei_sit_*.png'),
    ('pose', 'spr_ralsei_pose*.png'),
    ('idle', 'spr_ralsei_idle*.png'),
    ('walk_up_sleep?', 'spr_ralsei_walk_up_sleep_*.png'),
    ('walk_left_sleep?', 'spr_ralsei_walk_left_sleep_*.png'),
    ('walk_right_sleep?', 'spr_ralsei_walk_right_sleep_*.png'),
]
SCALE = 3
PAD = 10
BG = (28, 28, 32)


def load(p):
    # ★ OpenCV 在 Windows 上读不了含中文的路径（本仓库根含「项目文件夹」）
    #   ⇒ 一律 np.fromfile + imdecode，不用 cv2.imread。
    try:
        buf = np.fromfile(p, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    except Exception:
        img = None
    if img is None:
        return None
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    if img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    # 透明合成到中性底
    a = img[:, :, 3:4].astype(np.float32) / 255.0
    rgb = img[:, :, :3].astype(np.float32)
    bgc = np.array(BG, dtype=np.float32)
    out = (rgb * a + bgc * (1 - a)).astype(np.uint8)
    return out


def main():
    cols = []
    for label, pat in CAND:
        files = sorted(glob.glob(os.path.join(SPR, pat)))
        if not files:
            continue
        tiles = []
        for f in files:
            t = load(f)
            if t is None:
                continue
            tiles.append(cv2.resize(t, (t.shape[1] * SCALE, t.shape[0] * SCALE),
                                    interpolation=cv2.INTER_NEAREST))
        if not tiles:
            continue
        cols.append((label, tiles))
        print('%-34s %d 帧  %s' % (label, len(tiles), [os.path.basename(x) for x in files]))

    if not cols:
        print('没有任何候选素材被发现')
        return 2

    # 布局：每行一个候选组；组内横向排帧
    rowh = max(max(t.shape[0] for t in tiles) for _l, tiles in cols)
    labelw = 300
    total_w = labelw + max(sum(t.shape[1] + PAD for t in tiles) for _l, tiles in cols) + PAD
    total_h = (rowh + PAD * 3) * len(cols) + PAD
    canvas = np.zeros((total_h, total_w, 3), np.uint8)
    canvas[:, :] = (44, 44, 50)

    y = PAD
    for label, tiles in cols:
        cv2.putText(canvas, label, (PAD, y + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (235, 235, 235), 1, cv2.LINE_AA)
        x = labelw
        yy = y + 22
        for t in tiles:
            h, w = t.shape[:2]
            canvas[yy:yy + h, x:x + w] = t
            cv2.rectangle(canvas, (x - 1, yy - 1), (x + w, yy + h), (90, 90, 100), 1)
            x += w + PAD
        y += rowh + PAD * 3
    cv2.imwrite(OUT, canvas)
    print()
    print('对照图 = %s  (%dx%d)' % (OUT, total_w, total_h))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

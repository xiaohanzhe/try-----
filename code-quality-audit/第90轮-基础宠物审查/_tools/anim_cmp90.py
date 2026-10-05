# -*- coding: utf-8 -*-
u"""第90轮：睡眠/待机「候选动画」放大对照图。

修：上一版 `anim90.py` 用 `cv2.imwrite` 写**含中文的仓库路径** ⇒ Windows 上
静默失败（OpenCV 的 imwrite 走 ANSI 路径），图从未落盘。本版：
  · 读：np.fromfile + cv2.imdecode（绕开中文路径）
  · 写：cv2.imencode + ndarray.tofile（同样绕开）
  · 输出到 ASCII 路径，便于 Read 工具直接查看。
用法：python anim_cmp90.py
"""
import os
import numpy as np
import cv2

SPR = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\deltarune_ralsei'
OUT_DIR = r'C:\Users\23002\Downloads\_tmp'
OUT = os.path.join(OUT_DIR, 'sleep_candidates.png')

SCALE = 6
PAD = 12
BG = (245, 245, 248)          # 浅底（IDE 浅色主题友好）

# (标签, 文件?glob?)
CAND = [
    ('sleep 组(生效表登记)', 'spr_ralsei_walk_down_sleep_0.png'),
    ('sleep 第2帧(未登记)', 'spr_ralsei_walk_down_sleep_1.png'),
    ('board_ralsei_sleep_0', 'spr_board_ralsei_sleep_0.png'),
    ('board_ralsei_sleep_1', 'spr_board_ralsei_sleep_1.png'),
    ('sit_rest(坐定)', 'spr_ralsei_sit_2.png'),
    ('idle(当前实际在播)', 'spr_ralsei_idle_0.png'),
    ('pose(唤醒时播)', 'spr_ralsei_pose_0.png'),
]


def load(p):
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
    a = img[:, :, 3:4].astype(np.float32) / 255.0
    rgb = img[:, :, :3].astype(np.float32)
    bgc = np.array(BG, dtype=np.float32)
    out = (rgb * a + bgc * (1 - a))
    return out


def main():
    tiles = []
    infos = []
    for label, fn in CAND:
        p = os.path.join(SPR, fn)
        t = load(p)
        if t is None:
            infos.append((label, fn, None))
            continue
        h, w = t.shape[:2]
        big = cv2.resize(t, (w * SCALE, h * SCALE), interpolation=cv2.INTER_NEAREST)
        tiles.append((label, big))
        infos.append((label, fn, (w, h)))

    if not tiles:
        print('没有可加载的候选素材')
        return 2

    rowh = max(t.shape[0] for _l, t in tiles)
    labelw = 250
    total_w = labelw + max(t.shape[1] for _l, t in tiles) + PAD * 2
    total_h = (rowh + PAD) * len(tiles) + PAD + 40
    canvas = np.zeros((total_h, total_w, 3), np.uint8)
    canvas[:, :] = (38, 38, 42)      # 深底画布
    cv2.putText(canvas, 'Ralsei sleep / idle animation candidates (x%d)' % SCALE,
                (PAD, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 1, cv2.LINE_AA)

    y = 40 + PAD
    for label, big in tiles:
        cv2.putText(canvas, label, (PAD, y + rowh // 2 + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 220, 255), 1, cv2.LINE_AA)
        h, w = big.shape[:2]
        canvas[y:y + h, labelw:labelw + w] = big
        cv2.rectangle(canvas, (labelw - 1, y - 1), (labelw + w, y + h), (110, 110, 120), 1)
        y += rowh + PAD

    cv2.imencode('.png', canvas)[1].tofile(OUT)
    print('对照图 -> %s (%dx%d)' % (OUT, total_w, total_h))
    for label, fn, dim in infos:
        print('  %-26s %-34s %s' % (label, fn, '%dx%d' % dim if dim else '缺失'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

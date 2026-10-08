# -*- coding: utf-8 -*-
u"""第98轮：从 `rec97_raw.avi` 抽指定帧、按"宠物窗口"裁剪、拼成对照图。

用户第98轮硬规矩：
  「追一定要**看录像而不是只读后台输出**」

用法：
  python shot98.py <evidence目录名> <f0> <f1> [step] [out.png]

  · 录像帧号 == `rec97_frames.csv` 的 `frame`（每 tick 写一帧，一一对应）；
  · 裁剪框 = 该帧的窗口矩形外扩 PAD px（窗口位置/尺寸从 CSV 取）；
  · 拼接：每行最多 6 张，左上角写帧号。

★ 中文路径坑：`cv2.imread/imwrite` 在含中文的路径下**静默失败**
  ⇒ 读用 `np.fromfile + cv2.imdecode`，写用 `cv2.imencode + 手写 bytes`。
"""
import io
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EVROOT = os.path.normpath(os.path.join(HERE, '..', '_evidence'))
PAD = 90
PER_ROW = 6


def rd(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


def load_geo(path):
    """frame -> (wx, wy, ww, wh)"""
    txt = rd(path)
    lines = [l for l in txt.split('\n') if l.strip()]
    hdr = [h.strip() for h in lines[0].split(',')]
    out = {}
    for l in lines[1:]:
        parts = l.split(',')
        if len(parts) != len(hdr):
            continue
        d = dict(zip(hdr, parts))
        try:
            out[int(d['frame'])] = (int(float(d['wx'])), int(float(d['wy'])),
                                    int(float(d['ww'])), int(float(d['wh'])),
                                    d['anim'], d['dir'])
        except Exception:
            continue
    return out


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    run = sys.argv[1]
    f0 = int(sys.argv[2])
    f1 = int(sys.argv[3])
    step = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    out = (sys.argv[5] if len(sys.argv) > 5
           else os.path.join(EVROOT, run, 'shots_%d_%d.png' % (f0, f1)))
    full = os.environ.get('SHOT98_FULL', '0') == '1'
    d = os.path.join(EVROOT, run)
    avi = os.path.join(d, 'rec97_raw.avi')
    geo = load_geo(os.path.join(d, 'rec97_frames.csv'))
    cap = cv2.VideoCapture(avi)
    if not cap.isOpened():
        print('无法打开录像 %s' % avi)
        return 1
    tiles = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if f0 <= i <= f1 and (i - f0) % step == 0:
            g = geo.get(i)
            if g is None:
                i += 1
                continue
            wx, wy, ww, wh, anim, dr = g
            if full:
                # 全屏模式：整帧缩到 1/2（`SHOT98_FULL_SCALE` 可调）⇒ 能看出
                #   "掉到了屏幕的哪个位置"，同时宠物还看得清（38x80 -> 19x40）
                _s = int(os.environ.get('SHOT98_FULL_SCALE', '2'))
                crop = np.ascontiguousarray(cv2.resize(
                    fr, (fr.shape[1] // _s, fr.shape[0] // _s),
                    interpolation=cv2.INTER_AREA))
                cv2.rectangle(crop, (wx // _s, wy // _s),
                              ((wx + ww) // _s, (wy + wh) // _s),
                              (0, 0, 255), 2)
                lab = 'f%d %s/%s y=%d' % (i, anim, dr, wy)
                cv2.putText(crop, lab, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(crop, lab, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            (255, 255, 255), 1, cv2.LINE_AA)
                tiles.append(crop)
                i += 1
                continue
            x0 = max(0, wx - PAD)
            y0 = max(0, wy - PAD)
            x1 = min(fr.shape[1], wx + ww + PAD)
            y1 = min(fr.shape[0], wy + wh + PAD)
            crop = np.ascontiguousarray(fr[y0:y1, x0:x1])
            if crop.size == 0:
                i += 1
                continue
            lab = 'f%d %s/%s' % (i, anim, dr)
            cv2.putText(crop, lab, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(crop, lab, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 1, cv2.LINE_AA)
            cv2.rectangle(crop, (PAD, PAD), (PAD + ww, PAD + wh), (0, 0, 255), 1)
            tiles.append(crop)
        i += 1
    cap.release()
    if not tiles:
        print('没有抽到帧（f0=%d f1=%d）' % (f0, f1))
        return 1
    h = max(t.shape[0] for t in tiles)
    w = max(t.shape[1] for t in tiles)
    padded = []
    for t in tiles:
        canvas = np.zeros((h, w, 3), np.uint8)
        canvas[:t.shape[0], :t.shape[1]] = t
        padded.append(canvas)
    _perrow = 2 if full else PER_ROW
    rows = []
    for k in range(0, len(padded), _perrow):
        rows.append(np.hstack(padded[k:k + _perrow]))
    rw = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, rw - r.shape[1]), (0, 0)),
                   mode='constant') for r in rows]
    grid = np.vstack(rows)
    ok, buf = cv2.imencode('.png', grid)
    if not ok:
        print('编码失败')
        return 1
    with open(out, 'wb') as f:
        f.write(buf.tobytes())
    print('已写出 %s  （%d 帧，单格 %dx%d）' % (out, len(tiles), w, h))
    return 0


if __name__ == '__main__':
    sys.exit(main())

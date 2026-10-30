# -*- coding: utf-8 -*-
u"""assets116_doors.py —— 把门贴图（+候选）铺在棋盘格上放大，供人眼判"形式"。

棋盘格 = 透明的可视化（否则 RGBA 的透明区会与白底混成一片，看不出洞）。
输出 `_evidence/rec116/analysis/door_assets.png` + `sprites/` 下的单张放大图。
"""
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROUND, '_evidence', 'rec116')
ANA = os.path.join(OUT, 'analysis')
os.makedirs(ANA, exist_ok=True)
OBJS = os.path.abspath(os.path.join(ROUND, '..', '..',
                                    'ralsei_pet', 'assets', 'scenes', 'objs'))

NAMES = [
    ('A OneShot 现用', 'spr_darkdoor_0.png'),
    ('A cand darkdoor_1', 'spr_darkdoor_1.png'),
    ('A cand darkdoor_2', 'spr_darkdoor_2.png'),
    ('B Niko家 现用', 'niko_door_portal.png'),
    ('B rays', 'niko_portal_rays.png'),
    ('C UT 现用', 'ut_castle_realdoor_0.png'),
    ('D 符文 现用', 'spr_giantdarkdoor_0.png'),
    ('D cand darkdoor_1', 'spr_giantdarkdoor_1.png'),
    ('cand shortcut', 'spr_shortcut_door_0.png'),
    ('cand 编辑器doorA', 'spr_doorA_0.png'),
    ('cand 编辑器doorD', 'spr_doorD_0.png'),
    ('cand 编辑器doorY', 'spr_doorY_0.png'),
]
BOOST = int(os.environ.get('BOOST') or '4')
CELL_W, CELL_H = 260, 220


def _read_rgba(name):
    p = os.path.join(OBJS, name)
    if not os.path.exists(p):
        return None, None
    buf = np.fromfile(p, dtype=np.uint8)
    im = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    if im is None:
        return None, None
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGRA)
    if im.shape[2] == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
    return im, p


def _checker(h, w, sq=12):
    yy, xx = np.mgrid[0:h, 0:w]
    c = (((yy // sq) + (xx // sq)) % 2).astype(np.uint8)
    return (c * 90 + 110).astype(np.uint8)[:, :, None].repeat(3, axis=2)


def _compose(im_rgba):
    h, w = im_rgba.shape[:2]
    bg = _checker(h, w)
    a = im_rgba[:, :, 3:4].astype(np.float32) / 255.0
    rgb = im_rgba[:, :, :3].astype(np.float32)
    return (rgb * a + bg.astype(np.float32) * (1 - a)).astype(np.uint8)


def stats(im_rgba):
    rgb = im_rgba[:, :, :3]
    a = im_rgba[:, :, 3]
    black_op = float(((rgb.max(axis=2) < 16) & (a >= 250)).mean())
    return (float((a >= 250).mean()), float((a <= 5).mean()), black_op)


def main():
    rep = []
    cells = []
    for label, name in NAMES:
        im, p = _read_rgba(name)
        if im is None:
            cells.append(None)
            rep.append('%-18s %-28s 读不出' % (label, name))
            continue
        h, w = im.shape[:2]
        op, tr, blk = stats(im)
        cv2.putText(im, '', (0, 0), 0, 0, (0, 0, 0))
        comp = _compose(im)
        big = cv2.resize(comp, (w * BOOST, h * BOOST),
                         interpolation=cv2.INTER_NEAREST)
        cell = np.full((CELL_H, CELL_W, 3), 30, np.uint8)
        if big.shape[0] > CELL_H - 34 or big.shape[1] > CELL_W - 8:
            k = min((CELL_H - 34) / big.shape[0], (CELL_W - 8) / big.shape[1])
            big = cv2.resize(big, (max(1, int(big.shape[1] * k)),
                                   max(1, int(big.shape[0] * k))),
                             interpolation=cv2.INTER_NEAREST)
        y0 = 30 + (CELL_H - 34 - big.shape[0]) // 2
        x0 = (CELL_W - big.shape[1]) // 2
        cell[y0:y0 + big.shape[0], x0:x0 + big.shape[1]] = big
        cv2.putText(cell, label, (5, 16), cv2.FONT_HERSHEY_SIMPLEX,
                    0.42, (255, 255, 0), 1, cv2.LINE_AA)
        cv2.putText(cell, '%dx%d op%.2f blk%.2f' % (w, h, op, blk),
                    (5, CELL_H - 6), cv2.FONT_HERSHEY_SIMPLEX,
                    0.38, (200, 255, 200), 1, cv2.LINE_AA)
        cells.append(cell)
        rep.append('%-18s %-28s %3dx%-3d 不透明=%.3f 全透=%.3f 不透明且纯黑=%.3f'
                   % (label, name, w, h, op, tr, blk))
    cells = [c if c is not None else np.full((CELL_H, CELL_W, 3), 60, np.uint8)
             for c in cells]
    per = 4
    rows = []
    for k in range(0, len(cells), per):
        grp = cells[k:k + per]
        while len(grp) < per:
            grp.append(np.full((CELL_H, CELL_W, 3), 20, np.uint8))
        rows.append(np.hstack(grp))
    sheet = np.vstack(rows)
    sp = os.path.join(ANA, 'door_assets.png')
    ok, buf = cv2.imencode('.png', sheet)
    if ok:
        with open(sp, 'wb') as fh:
            fh.write(buf.tobytes())
    txt = u'\n'.join(rep) + u'\n\nwritten %s (%d bytes)\n' % (
        sp, os.path.getsize(sp) if os.path.exists(sp) else -1)
    sys.stdout.write(txt.encode('utf-8', 'replace').decode('utf-8', 'replace'))


if __name__ == '__main__':
    main()

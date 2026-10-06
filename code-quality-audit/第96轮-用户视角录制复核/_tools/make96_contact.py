# -*- coding: utf-8 -*-
u"""make96_contact.py —— 把关键帧 PNG 拼成"人眼看的一页"（contact sheet）。

为什么要拼
----------
关键帧有几十上百张（状态每变化一次落一张），逐张看不现实。
拼成一张大图 + 标注帧号/时刻/动画/方向，人眼一眼就能核对"看着对不对"。

★ 走 `cv2.imdecode` + 手动读 bytes（不是 `cv2.imread`）：
  本仓库路径含中文，`cv2.imread/imwrite` 在中文路径下会**静默失败**（实测）。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第96轮-用户视角录制复核\\_tools\\make96_contact.py
"""
import io
import os
import re
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.join(os.path.normpath(os.path.join(HERE, '..')), '_evidence')
FRAMES = os.path.join(EV, 'frames')

COLS = 6
THUMB_W = 300
LABEL_H = 26


def imread_u(p):
    u"""中文路径安全读图（`cv2.imread` 会静默返回 None）。"""
    try:
        with open(p, 'rb') as f:
            buf = np.frombuffer(f.read(), np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except Exception:
        return None


def imwrite_u(p, img):
    ok, buf = cv2.imencode(os.path.splitext(p)[1] or '.png', img)
    if ok:
        with open(p, 'wb') as f:
            f.write(buf.tobytes())
    return ok


def main():
    if not os.path.isdir(FRAMES):
        print(u'★ 没有 frames/ 目录')
        return 2
    names = sorted(f for f in os.listdir(FRAMES) if f.endswith('.png'))
    if not names:
        print(u'★ frames/ 里没有 PNG')
        return 2
    print(u'关键帧 %d 张' % len(names))

    # 读 frames.csv 拿每帧的 时刻/动画/方向/尺寸 —— 关键帧落盘条件是
    # (anim, dir, w, h, sleeping) 变化，这里用**同样规则**重放一遍，
    # 就能把 k%06d.png 对应回具体的采样行。
    meta_rows = []           # [anim_base, dir, anim, w, h, sleeping, t, frame]
    csvp = os.path.join(EV, 'rec96_frames.csv')
    if os.path.exists(csvp):
        txt = io.open(csvp, encoding='utf-8', newline='').read()
        hdr = None
        for ln in txt.split('\n'):
            v = ln.split(',')
            if hdr is None:
                hdr = v
                continue
            if len(v) != len(hdr):
                continue
            d = dict(zip(hdr, v))
            an = d.get('anim', '')
            base = an.split('_')[0] if an else ''
            m = re.match(r'^(walk|run)_(up|down|left|right)$', an)
            meta_rows.append([base if m else '', m.group(2) if m else '',
                              an, d.get('ww', ''), d.get('wh', ''),
                              d.get('sleeping', ''), d.get('t', ''),
                              d.get('frame', '')])

    thumbs = []
    for nm in names:
        # 文件名 k000123.png -> 该帧的采样序号其实是"第几次状态变化"，
        # 与 frames.csv 的 frame 不是一回事 ⇒ 用 mtime 顺序近似，但这里直接显示文件名
        img = imread_u(os.path.join(FRAMES, nm))
        if img is None:
            continue
        h, w = img.shape[:2]
        sc = float(THUMB_W) / w
        th = cv2.resize(img, (THUMB_W, max(1, int(h * sc))))
        thumbs.append((nm, th))

    if not thumbs:
        print(u'★ 没有可读 PNG')
        return 2

    rows = (len(thumbs) + COLS - 1) // COLS
    th_h = max(t.shape[0] for _, t in thumbs)
    cell_h = th_h + LABEL_H
    sheet = np.full((rows * cell_h, COLS * THUMB_W, 3), 24, np.uint8)

    for i, (nm, t) in enumerate(thumbs):
        r, c = divmod(i, COLS)
        y0 = r * cell_h + LABEL_H
        x0 = c * THUMB_W
        sheet[y0:y0 + t.shape[0], x0:x0 + t.shape[1]] = t
        cv2.putText(sheet, nm.replace('.png', ''), (x0 + 4, r * cell_h + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    out = os.path.join(EV, 'rec96_contact_sheet.png')
    ok = imwrite_u(out, sheet)
    print(u'拼图 %s  %dx%d  ok=%s  (%.1f MB)'
          % (out, sheet.shape[1], sheet.shape[0], ok,
             os.path.getsize(out) / 1048576.0 if ok and os.path.exists(out) else 0))

    # ★★ 再做一张"**朝向对照图**" —— 这是最贴用户视角、也最有说服力的证据：
    #    把 4 个走路方向各挑一张，横排在一起，下面标"动画名 / dir / 实际位移向量"。
    #    人眼一眼就能核对"脸朝的方向 和 位移方向 一致吗"。
    #    ★ 关键帧文件名 = 第 N 次"状态变化"，与 frames.csv 的 frame 编号**不是一回事**
    #      ⇒ 只能按"挑哪一帧"的语义选：从 frames.csv 里找"某方向走路且刚变化"的采样，
    #        再按**采样顺序**映射到关键帧序号（关键帧也是按状态变化顺序落的）。
    # 用"首帧出现该 anim"的方式找关键帧（关键帧按状态变化落，顺序与采样一致）
    idx_by_anim = {}
    # frames.csv 的 frame 与 PNG 名不同 ⇒ 用"状态变化序列"重建：
    # 关键帧落盘条件是 (anim,dir,w,h,sleep) 变化；这里同样规则扫一遍 frames.csv，
    # 得到"第 N 次变化"所对应的行，再对到 k%06d.png
    last = None
    change_rows = []
    for r in meta_rows:
        key = (r[2], r[3], r[4], r[5], r[6])
        if key != last:
            last = key
            change_rows.append(r)
    for nm, th in thumbs:
        try:
            n = int(nm[1:7])
        except Exception:
            continue
        if n >= len(change_rows):
            continue
        r = change_rows[n]
        if r[0] in ('walk', 'run') and r[0] not in idx_by_anim:
            idx_by_anim[r[0] + '_' + r[1]] = (nm, th, r)
        elif r[0] in ('walk', 'run') and len(idx_by_anim.get(r[0] + '_' + r[1], ())) == 0:
            idx_by_anim[r[0] + '_' + r[1]] = (nm, th, r)

    order = ['walk_left', 'walk_right', 'walk_up', 'walk_down',
             'run_left', 'run_right', 'run_up', 'run_down']
    sel = [(k, idx_by_anim[k]) for k in order if k in idx_by_anim]
    if sel:
        cw = max(t.shape[1] for _, (_, t, _) in sel)
        ch = max(t.shape[0] for _, (_, t, _) in sel) + LABEL_H + 18
        g = np.full((ch, cw * len(sel), 3), 24, np.uint8)
        for j, (k, (nm, t, r)) in enumerate(sel):
            x0 = j * cw
            g[LABEL_H + 18:LABEL_H + 18 + t.shape[0], x0:x0 + t.shape[1]] = t
            cv2.putText(g, k, (x0 + 4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(g, u'%s t=%ss' % (nm.replace('.png', ''), r[7]),
                        (x0 + 4, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                        (180, 220, 255), 1, cv2.LINE_AA)
        out2 = os.path.join(EV, 'rec96_dir_compare.png')
        ok2 = imwrite_u(out2, g)
        print(u'朝向对照图 %s  %dx%d ok=%s  收录 %s'
              % (out2, g.shape[1], g.shape[0], ok2, [k for k, _ in sel]))

    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
u"""cmp116_doorD_px.py —— 门 D「框内」到底是**白色门板**还是**透明洞**？

为什么要它
----------
`cmp116_doors.py` 只报了"纯黑比 / 全透明比"。门 D 的原件是「黑底 + 金框 +
**框内一片浅色**」，那片浅色**是白像素还是透明**决定了桌面上的观感：
  · 是白像素 ⇒ 桌面上一扇**白头门**；
  · 是透明   ⇒ 桌面上**透出壁纸**（= 用户要的"黑底去干净"）。
两件事都可能，光看渲染图分不清（Read 的渲染把透明合成到白）⇒ **量**。

做法：取贴图**正中心**竖线（x = w//2）上若干 y 的像素，逐点打印 (R,G,B,A)。
再对桌面**实拍图**的同一条线上取点，看框内是不是壁纸色。

跑法
----
  C:\\Python311\\python.exe "...\\_tools\\cmp116_doorD_px.py"
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OBJS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs')
EV = os.path.join(ROUND, '_evidence', 'rec116')

try:
    from PyQt5.QtGui import QImage
except Exception as e:
    sys.stdout.write('PyQt5 不可用: %r\n' % (e,))
    sys.exit(2)


def load(path):
    img = QImage(path)
    if img.isNull():
        return None
    return img.convertToFormat(QImage.Format_ARGB32)


def px(img, x, y):
    c = img.pixel(int(x), int(y))
    return ((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF, (c >> 24) & 0xFF)


def main():
    rep = []
    for name in ('spr_giantdarkdoor_0.png', 'desk_door_deltarune.png'):
        img = load(os.path.join(OBJS, name))
        if img is None:
            rep.append(u'%s 读不到' % name)
            continue
        w, h = img.width(), img.height()
        rep.append(u'== %s  %dx%d  ==' % (name, w, h))
        # 正中心竖线：y 取 15% / 30% / 50% / 70% / 90%
        for frac in (0.15, 0.30, 0.50, 0.70, 0.90):
            y = int(h * frac)
            c = px(img, w // 2, y)
            rep.append(u'   x=%d y=%d (%.0f%%)  R=%3d G=%3d B=%3d A=%3d'
                       % (w // 2, y, frac * 100, c[0], c[1], c[2], c[3]))
        # 框内但偏左一点（避开中间那根金色竖条）
        for frac in (0.30, 0.55, 0.80):
            y = int(h * frac)
            c = px(img, int(w * 0.34), y)
            rep.append(u'   x=%d y=%d (%.0f%%)  R=%3d G=%3d B=%3d A=%3d  [框内偏左]'
                       % (int(w * 0.34), y, frac * 100, c[0], c[1], c[2], c[3]))
        # 四角（背景）
        for (sx, sy) in ((0.03, 0.03), (0.97, 0.03), (0.03, 0.97), (0.97, 0.97)):
            c = px(img, int(w * sx), int(h * sy))
            rep.append(u'   角(%.2f,%.2f)  R=%3d G=%3d B=%3d A=%3d'
                       % (sx, sy, c[0], c[1], c[2], c[3]))
        rep.append(u'')

    # ---- 实拍图：门 D 屏幕矩形内取点（判"框内看到的是什么"）----
    shot = None
    for tag in ('shot116_doorform3_fullD.png', 'shot116_doorform2_fullD.png'):
        p = os.path.join(EV, tag)
        if os.path.isfile(p):
            shot = load(p)
            rep.append(u'== 实拍 %s  ==' % tag)
            break
    if shot is not None:
        # 门 D 产品口径矩形 = (2423, 705, 137, 118)
        x0, y0, w, h = 2423, 705, 137, 118
        rep.append(u'   门 D 屏幕矩形 = (%d,%d,%d,%d)' % (x0, y0, w, h))
        for frac in (0.25, 0.45, 0.65, 0.85):
            y = int(y0 + h * frac)
            c = px(shot, x0 + w // 2, y)
            rep.append(u'   框内中轴 y=%d (%.0f%%)  R=%3d G=%3d B=%3d'
                       % (y, frac * 100, c[0], c[1], c[2]))
        for frac in (0.30, 0.55, 0.80):
            y = int(y0 + h * frac)
            c = px(shot, int(x0 + w * 0.34), y)
            rep.append(u'   框内偏左  y=%d (%.0f%%)  R=%3d G=%3d B=%3d'
                       % (y, frac * 100, c[0], c[1], c[2]))
        # 框外（壁纸参照）
        c = px(shot, x0 - 60, y0 + h // 2)
        rep.append(u'   框外壁纸(左60px)  R=%3d G=%3d B=%3d' % (c[0], c[1], c[2]))
    txt = u'\n'.join(rep) + u'\n'
    with io.open(os.path.join(EV, 'cmp116_doorD_px.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    sys.stdout.write(txt)
    return 0


if __name__ == '__main__':
    sys.exit(main())

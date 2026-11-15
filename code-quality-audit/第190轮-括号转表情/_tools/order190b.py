# -*- coding: utf-8 -*-
u"""第190轮续 · 旁白/台词 的**逐行直方图**（把"串色"的杂行剔掉再看顺序）。

上一版 `order190.py` 直接取 `min_y`，被输入框占位符（同样灰）污染了。
这一版把每个 y 的命中数打出来，人工/程序都能看出"哪几行真的是那两个字"。
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from PyQt5.QtGui import QImage   # noqa: E402

IMG = os.path.join('D:\\', '_tmp190', 'preview', 'narration190.png')

NARR = (0xa9, 0xa2, 0x9a)
LINE = (0xc9, 0xa8, 0x6a)
TOL = 12
MIN_RUN = 3          # 一行至少 3 个像素才算"有字"，否则算抗锯齿噪点


def _near(r, g, b, ref):
    return (abs(r - ref[0]) <= TOL
            and abs(g - ref[1]) <= TOL
            and abs(b - ref[2]) <= TOL)


def rows(img, ref):
    """→ [(y, 命中数)]，只保留命中数 >= MIN_RUN 的行。"""
    out = []
    for y in range(img.height()):
        n = 0
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if _near(c.red(), c.green(), c.blue(), ref):
                n += 1
        if n >= MIN_RUN:
            out.append((y, n))
    return out


def spans(rs):
    """把连续 y 归并成段 → [(y0, y1, 总像素)]。"""
    out = []
    cur = None
    for y, n in rs:
        if cur and y == cur[1] + 1:
            cur = (cur[0], y, cur[2] + n)
        else:
            if cur:
                out.append(cur)
            cur = (y, y, n)
    if cur:
        out.append(cur)
    return out


def main():
    img = QImage(IMG)
    print(u'图: %s  %dx%d' % (IMG, img.width(), img.height()))

    for name, ref in ((u'旁白', NARR), (u'台词', LINE)):
        rs = rows(img, ref)
        sp = spans(rs)
        print(u'')
        print(u'== %s %s == 行数=%d 段落=%d' % (
            name, '#%02x%02x%02x' % ref, len(rs), len(sp)))
        for y0, y1, tot in sp:
            print(u'   y=%3d..%3d  (%2d 行, %4d px)' % (y0, y1, y1 - y0 + 1, tot))

    # ★ 只取"最高的那一段"比较 —— 段内就是那一行字本身
    sn = spans(rows(img, NARR))
    sl = spans(rows(img, LINE))
    if not sn or not sl:
        print(u'\n[FAIL] 有一方完全没有成段的像素')
        return 1

    # 台词只可能有一段（一个 ▸ 行）；旁白可能多段，取最上面那段
    ny0 = sn[0][0]
    ly0 = sl[0][0]
    ok = ny0 < ly0
    print(u'')
    print(u'[判定] 旁白首段 y=%d ；台词首段 y=%d ⇒ 旁白%s'
          % (ny0, ly0, u'在上 ✔' if ok else u'在下 ✘'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

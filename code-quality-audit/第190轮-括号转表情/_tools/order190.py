# -*- coding: utf-8 -*-
u"""第190轮续 · 用**像素**判定"旁白在上还是台词在上"。

★ 为什么不用肉眼/视觉模型：上一轮我看图得出的结论是反的。
  这两行的颜色是**产品代码里写死的常量**，可以直接按 RGB 精确扫：

    · 旁白  `#a9a29a`  （`_narration_html`）
    · 台词  `#c9a86a`  （`add_npc_line` 的 `▸ 名字: 内容`）

  分别求出它们的**出现行号区间**，比 `min_y` 就得到确定答案。
★ 容差 ±12：Qt 的字体抗锯齿会让边缘像素漂移，但中心笔画仍落在原位。
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


def _near(r, g, b, ref):
    return (abs(r - ref[0]) <= TOL
            and abs(g - ref[1]) <= TOL
            and abs(b - ref[2]) <= TOL)


def scan(img, ref):
    """→ (命中像素数, 最小 y, 最大 y)。"""
    n = 0
    y0 = None
    y1 = None
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if _near(c.red(), c.green(), c.blue(), ref):
                n += 1
                if y0 is None:
                    y0 = y
                y1 = y
    return n, y0, y1


def main():
    img = QImage(IMG)
    if img.isNull():
        print(u'[!] 读不到 %s' % IMG)
        return 2
    print(u'图: %s  %dx%d' % (IMG, img.width(), img.height()))

    n_narr, ny0, ny1 = scan(img, NARR)
    n_line, ly0, ly1 = scan(img, LINE)
    print(u'旁白 #a9a29a : %6d px  y=[%s, %s]' % (n_narr, ny0, ny1))
    print(u'台词 #c9a86a : %6d px  y=[%s, %s]' % (n_line, ly0, ly1))

    if not n_narr:
        print(u'[FAIL] 一个旁白像素都没找到 —— 要么没画出来，要么颜色被改了。')
        return 1
    if not n_line:
        print(u'[FAIL] 一个台词像素都没找到。')
        return 1

    ok = ny0 < ly0
    print(u'')
    print(u'[判定] 旁白首行 y=%s  %s  台词首行 y=%s'
          % (ny0, u'<' if ok else u'>', ly0))
    print(u'[结论] %s' % (u'旁白在上 ✔ 与 HTML 顺序一致'
                          if ok else u'旁白在下 ✘ 与 HTML 顺序相反'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

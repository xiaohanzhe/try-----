# -*- coding: utf-8 -*-
"""量化 PNG 内容：不透明像素占比 + 去重色数（判"空白 vs 有内容"）。

用法： C:\\Python311\\python.exe pngstats93.py <目录> [子串过滤]
★ 判据说明：`opaque%` 低 + `colors` 少 ⇒ 基本空白；实测 89 轮空白画布
   该值接近 0%（透明分层窗口若 PrintWindow 失败，抓出来全透明）。
"""
import os
import sys

from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def stats(path, budget=160):
    img = QImage(path)
    if img.isNull():
        return None
    w, h = img.width(), img.height()
    step = max(1, min(w, h) // budget)
    n = op = 0
    cols = set()
    for y in range(0, h, step):
        for x in range(0, w, step):
            c = img.pixel(x, y)          # ARGB32
            if ((c >> 24) & 0xff) > 8:
                op += 1
                cols.add(c & 0x00ffffff)
            n += 1
    return w, h, op, n, len(cols)


def main():
    d = sys.argv[1]
    sub = sys.argv[2] if len(sys.argv) > 2 else ''
    rows = []
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith('.png') or sub not in f:
            continue
        p = os.path.join(d, f)
        try:
            st = stats(p)
        except Exception as e:
            rows.append((f, os.path.getsize(p), 'ERR %r' % (e,)))
            continue
        if st is None:
            rows.append((f, os.path.getsize(p), 'LOAD-FAIL'))
            continue
        w, h, op, n, nc = st
        rows.append((f, os.path.getsize(p),
                     '%4dx%-4d opaque=%3d/%3d(%5.1f%%) colors=%3d'
                     % (w, h, op, n, 100.0 * op / max(1, n), nc)))
    for r in rows:
        print('%-44s %8d  %s' % r)
    print('共 %d 张' % len(rows))


if __name__ == '__main__':
    main()

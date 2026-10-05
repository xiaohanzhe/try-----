# -*- coding: utf-8 -*-
u"""第90轮：整屏抓取 → 裁剪出宠物附近的小块（避免把用户整桌面读进来）。

用法：python crop90.py <full.png> <out.png> <x,y,w,h>
"""
import sys
import cv2


def main():
    full, out = sys.argv[1], sys.argv[2]
    x, y, w, h = [int(v) for v in sys.argv[3].split(',')]
    img = cv2.imread(full, cv2.IMREAD_UNCHANGED)
    print('整屏: %s  shape=%s' % (full, None if img is None else img.shape))
    if img is None:
        return 2
    H, W = img.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    crop = img[y0:y1, x0:x1]
    # 放大 3 倍便于目视
    big = cv2.resize(crop, (crop.shape[1] * 3, crop.shape[0] * 3), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(out, big)
    print('裁剪 (%d,%d)-(%d,%d) → %s  放大后 %s' % (x0, y0, x1, y1, out, big.shape))
    return 0


if __name__ == '__main__':
    sys.exit(main())

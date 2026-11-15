# -*- coding: utf-8 -*-
u"""第190轮 · GameMaker 贴图页解码：PNG / BZh(内嵌 QOI) 两种形态。

背景（实测，2026-11-15）
------------------------
* 黄魂（UTY）的 117 张贴图页里：**34 张是 PNG，84 张是 `BZh`（bzip2）压缩块**，
  解压后不是 PNG，而是 **GameMaker 的 QOI 容器**：
  `magic "fioq"(4B) + width(uint16 LE) + height(uint16 LE) + QOI 码流`。
* Undertale 的 42 页全是 PNG。
* `TextureWorker.ExportAsPNG` 对 QOI 页只吐**黑白蒙版**（ceroba/undyne 的脸都是 2 色）
  ⇒ 只能自己解。

★ 验证手段：GM 容器头里的宽高必须与 UTMT 报的 `Data.EmbeddedTextures[i]` 宽高**逐页相等**；
  这不是装饰——它就是"解压顺序没串位"的证明。
"""
import bz2
import io
import struct

QOI_OP_INDEX = 0x00
QOI_OP_DIFF = 0x40
QOI_OP_LUMA = 0x80
QOI_OP_RUN = 0xC0
QOI_OP_RGB = 0xFE
QOI_OP_RGBA = 0xFF


def qoi_decode(data, w, h):
    u"""标准 QOI 解码 → bytes(RGBA)。`data` 从第一个 op 字节开始。"""
    px = [0, 0, 0, 255]
    index = [(0, 0, 0, 0)] * 64
    out = bytearray()
    p = 0
    n = len(data)
    run = 0
    need = w * h
    while len(out) < need * 4:
        if run > 0:
            run -= 1
        else:
            if p >= n:
                raise ValueError('QOI 码流提前结束（已出 %d/%d 像素）' % (len(out) // 4, need))
            b1 = data[p]
            p += 1
            if b1 == QOI_OP_RGB:
                px[0], px[1], px[2] = data[p], data[p + 1], data[p + 2]
                p += 3
            elif b1 == QOI_OP_RGBA:
                px[0], px[1], px[2], px[3] = data[p], data[p + 1], data[p + 2], data[p + 3]
                p += 4
            elif (b1 & 0xC0) == QOI_OP_INDEX:
                px = list(index[b1])
            elif (b1 & 0xC0) == QOI_OP_DIFF:
                px[0] = (px[0] + ((b1 >> 4) & 0x03) - 2) & 0xFF
                px[1] = (px[1] + ((b1 >> 2) & 0x03) - 2) & 0xFF
                px[2] = (px[2] + (b1 & 0x03) - 2) & 0xFF
            elif (b1 & 0xC0) == QOI_OP_LUMA:
                b2 = data[p]
                p += 1
                vg = (b1 & 0x3F) - 32
                px[0] = (px[0] + vg - 8 + ((b2 >> 4) & 0x0F)) & 0xFF
                px[1] = (px[1] + vg) & 0xFF
                px[2] = (px[2] + vg - 8 + (b2 & 0x0F)) & 0xFF
            else:
                run = b1 & 0x3F
        index[(px[0] * 3 + px[1] * 5 + px[2] * 7 + px[3] * 11) % 64] = tuple(px)
        out += bytes(px)
    return bytes(out)


def decode_gm_qoi(blob):
    u"""GameMaker 的 QOI 容器 → (w, h, rgba_bytes)。"""
    if len(blob) < 12 or blob[:4] != b'fioq':
        raise ValueError('不是 GM QOI（头 4 字节 %r）' % blob[:4])
    w, h = struct.unpack('<HH', blob[4:8])
    if w <= 0 or h <= 0:
        raise ValueError('宽高非法 %dx%d' % (w, h))
    return w, h, qoi_decode(blob[8:], w, h)


def decode_bz2_page(raw):
    u"""`BZh` 起头的块（从包体里切出来的剩余字节）→ (w, h, rgba)。"""
    blob = bz2.BZ2File(io.BytesIO(raw)).read()
    return decode_gm_qoi(blob)


def _selftest():
    import os
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    from PIL import Image
    pkg = r'D:/_wb_tmp/dw_ut/uty/game.droid'
    d = open(pkg, 'rb').read()
    import re
    offs = [m.start() for m in re.finditer(b'BZh', d)]
    print('BZh 块 %d 个' % len(offs))
    for i in (0, 1, 5):
        w, h, rgba = decode_bz2_page(d[offs[i]:])
        im = Image.frombytes('RGBA', (w, h), rgba)
        cols = im.getcolors(1 << 22)
        out = os.path.join(r'D:/_tmp190', 'qoi_selftest_%d.png' % i)
        im.save(out)
        print('  #%d %dx%d 颜色数=%s → %s' % (i, w, h,
                                             len(cols) if cols else '>4M', out))


if __name__ == '__main__':
    _selftest()

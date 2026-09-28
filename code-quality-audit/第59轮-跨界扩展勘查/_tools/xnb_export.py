# -*- coding: utf-8 -*-
"""通用 XNB -> PNG 导出（复用最小解析器）。用法：脚本 <相对路径> [<相对路径> ...]"""
import os
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                   # noqa: E402

C = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
     r'\OneShot.World.Machine.Edition.Build.16512634\content')
OUT = r'E:\Download\_tmp\xnb_out'
os.makedirs(OUT, exist_ok=True)


def rd7(b, i):
    r = s = 0
    while True:
        x = b[i]
        i += 1
        r |= (x & 0x7F) << s
        if not (x & 0x80):
            return r, i
        s += 7


def read_xnb(path):
    b = open(path, 'rb').read()
    assert b[:3] == b'XNB'
    flags = b[5]
    i = 10
    assert not (flags & 0xC0), '压缩格式未实现 flags=0x%02x' % flags
    n, i = rd7(b, i)
    for _ in range(n):
        ln, i = rd7(b, i)
        i += ln + 4
    _ns, i = rd7(b, i)
    _ti, i = rd7(b, i)
    fmt, w, h, mips = struct.unpack('<iIII', b[i:i + 16])
    i += 16
    data = None
    for m in range(mips):
        sz = struct.unpack('<I', b[i:i + 4])[0]
        i += 4
        if m == 0:
            data = b[i:i + sz]
        i += sz
    return fmt, w, h, mips, data


for rel in sys.argv[1:]:
    p = os.path.join(C, rel)
    if not os.path.isfile(p):
        print('MISSING', rel)
        continue
    try:
        fmt, w, h, mips, data = read_xnb(p)
    except Exception as e:
        print('FAIL', rel, repr(e))
        continue
    print('%-34s %5dx%-5d fmt=%d bytes=%d' % (rel, w, h, fmt, len(data or b'')))
    if fmt != 0 or not data:
        continue
    img = Image.frombytes('RGBA', (w, h), data[:w * h * 4])
    name = os.path.splitext(os.path.basename(rel))[0] + '.png'
    img.save(os.path.join(OUT, name))
    print('        ->', os.path.join(OUT, name))

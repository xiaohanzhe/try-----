# -*- coding: utf-8 -*-
u"""sheet100b.py —— 只看一眼：`en` 到底是谁（和 niko 是不是同一角色）。"""
import os
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image, ImageDraw                                  # noqa: E402

OSD = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
       r'\OneShot.World.Machine.Edition.Build.16512634')
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), '_evidence')


def rd7(b, i):
    r = s = 0
    while True:
        x = b[i]
        i += 1
        r |= (x & 0x7F) << s
        if not (x & 0x80):
            return r, i
        s += 7


def xnb_img(path):
    raw = open(path, 'rb').read()
    if raw[:3] != b'XNB' or (raw[5] & 0xC0):
        return None
    i = 10
    nr, i = rd7(raw, i)
    for _ in range(nr):
        n, i = rd7(raw, i)
        i += n + 4
    _s, i = rd7(raw, i)
    _t, i = rd7(raw, i)
    fmt, w, h, mips = struct.unpack('<iIII', raw[i:i + 16])
    i += 16
    data = None
    for m in range(mips):
        sz = struct.unpack('<I', raw[i:i + 4])[0]
        i += 4
        if m == 0:
            data = raw[i:i + sz]
        i += sz
    return Image.frombytes('RGBA', (w, h), data)


wanted = [('npc', 'niko'), ('npc', 'en'), ('npc', 'niko_bulb'),
          ('facepics', 'en'), ('facepics', 'niko2'), ('facepics', 'niko_smile'),
          ('facepics', 'en6')]
SC = 4
CELL = 180
cells = []
for sub, nm in wanted:
    p = os.path.join(OSD, 'content', sub, nm + '.xnb')
    if not os.path.isfile(p):
        cells.append((Image.new('RGB', (CELL, CELL), (255, 0, 255)), '%s/%s 缺' % (sub, nm)))
        continue
    im = xnb_img(p)
    if im is None:
        continue
    k = max(1, min(CELL // max(1, im.width), CELL // max(1, im.height)))
    big = im.resize((im.width * k, im.height * k), Image.NEAREST)
    bgc = Image.new('RGBA', (CELL, CELL), (255, 255, 255, 255))
    bgc.paste(big, ((CELL - big.width) // 2, (CELL - big.height) // 2), big)
    cells.append((bgc.convert('RGB'), '%s/%s %dx%d' % (sub, nm, im.width, im.height)))

g = Image.new('RGB', (len(cells) * (CELL + 6) + 6, CELL + 26), (240, 240, 240))
d = ImageDraw.Draw(g)
for i, (im, lab) in enumerate(cells):
    x = 6 + i * (CELL + 6)
    g.paste(im, (x, 20))
    d.text((x, 4), lab, fill=(0, 0, 0))
p = os.path.join(OUT, 'whois_en100.png')
g.save(p)
print('已存', p, g.size)
for im, lab in cells:
    print('  ', lab)

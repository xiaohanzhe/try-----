# -*- coding: utf-8 -*-
u"""sheet100.py —— 生成两张**看图用**的核对图（不下结论，只给人眼判断）。

  sup100_sheet.png   补发目录 74 项的总览（PNG 缩略拼图 + wav 名称列表）
  ab100_dialog.png   A/B 对照：左=补发 dialog_* 缩略，右=WME 对应 facepics 放大

★ 为什么必须出图：识别脚本只能给"相关=0.95"这种数字，而**数字判据本身也会说谎**
  （第100轮已实测：mad 判据把空白图对空白图算成 mad=2.5 的"极像"）。人眼是最后一道。
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image, ImageDraw                                  # noqa: E402

SUP = r'C:\Users\23002\Desktop\项目文件夹\assets'
OSD = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
       r'\OneShot.World.Machine.Edition.Build.16512634')
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), '_evidence')
NOT_ASSETS = {'config.json', 'save_key.py', 'desktop.ini'}
CELL = 120
PAD = 6
COLS = 10


def grid_background(cells, cols=COLS, cell=CELL, pad=PAD, label_h=16):
    rows = (len(cells) + cols - 1) // cols
    bg = Image.new('RGB', (cols * (cell + pad) + pad,
                           rows * (cell + pad + label_h) + pad), (245, 245, 245))
    d = ImageDraw.Draw(bg)
    for i, (im, label) in enumerate(cells):
        r, c = divmod(i, cols)
        x = pad + c * (cell + pad)
        y = pad + r * (cell + pad + label_h)
        bg.paste(im, (x, y))
        d.rectangle([x, y, x + cell - 1, y + cell - 1], outline=(180, 180, 180))
        d.text((x + 1, y + cell + 2), label[:20], fill=(20, 20, 20))
    return bg


def thumb(p, cell=CELL):
    im = Image.open(p).convert('RGBA')
    bgc = Image.new('RGBA', (cell, cell), (255, 255, 255, 255))
    im.thumbnail((cell, cell), Image.LANCZOS)
    bgc.paste(im, ((cell - im.width) // 2, (cell - im.height) // 2), im)
    return bgc.convert('RGB')


def main():
    os.makedirs(OUT, exist_ok=True)
    names = sorted(n for n in os.listdir(SUP) if n not in NOT_ASSETS
                   and not n.endswith('.jpg'))
    pngs = [n for n in names if n.lower().endswith('.png')]
    wavs = [n for n in names if n.lower().endswith('.wav')]

    cells = [(thumb(os.path.join(SUP, n)), n[:-4]) for n in pngs]
    g = grid_background(cells)
    p1 = os.path.join(OUT, 'sup100_sheet.png')
    g.save(p1)
    print('已存', p1, g.size, '%d 张 PNG' % len(pngs))

    # ---- A/B：dialog_* vs WME facepics
    pairs = [('dialog_normal.png', 'en'), ('dialog_sad.png', 'en_sad'),
             ('dialog_shocked.png', 'en_surprised'), ('dialog_yawning.png', 'en_yawn'),
             ('dialog_smiling.png', 'en_smile'), ('dialog_very_wtf.png', 'en_huh'),
             ('dialog_eyes_closed.png', 'en_eyeclosed'), ('dialog_hungry.png', 'en6')]
    cw, ch = 200, 420
    ab = Image.new('RGB', (cw * len(pairs), ch), (250, 250, 250))
    d = ImageDraw.Draw(ab)
    for i, (sup_name, os_name) in enumerate(pairs):
        a = thumb(os.path.join(SUP, sup_name), 190)
        x, x0 = i * cw + 5, i * cw + 5
        xnb = os.path.join(OSD, 'content', 'facepics', os_name + '.xnb')
        b = Image.new('RGB', (190, 190), (255, 255, 255))
        if os.path.isfile(xnb):
            # 复用 identify100 的解码（这里直接内联最小版，避免耦合）
            import struct

            def rd7(bb, j):
                r = s = 0
                while True:
                    xx = bb[j]
                    j += 1
                    r |= (xx & 0x7F) << s
                    if not (xx & 0x80):
                        return r, j
                    s += 7
            raw = open(xnb, 'rb').read()
            j = 10
            nr, j = rd7(raw, j)
            for _ in range(nr):
                n2, j = rd7(raw, j)
                j += n2 + 4
            _s, j = rd7(raw, j)
            _t, j = rd7(raw, j)
            fmt, w, h, mips = struct.unpack('<iIII', raw[j:j + 16])
            j += 16
            data = None
            for m in range(mips):
                sz = struct.unpack('<I', raw[j:j + 4])[0]
                j += 4
                if m == 0:
                    data = raw[j:j + sz]
                j += sz
            ximg = Image.frombytes('RGBA', (w, h), data).resize((190, 190), Image.NEAREST)
            b.paste(ximg, (0, 0), ximg)
        d.text((x, 2), '补发 %s' % sup_name[:-4], fill=(10, 10, 10))
        ab.paste(a, (x, 16))
        d.text((x, 210), 'WME facepics/%s 放大' % os_name, fill=(10, 10, 10))
        ab.paste(b, (x, 224))
    p2 = os.path.join(OUT, 'ab100_dialog.png')
    ab.save(p2)
    print('已存', p2, ab.size, '(上=补发  下=WME 放大)')

    print('\nwav 清单（%d）：' % len(wavs))
    for n in wavs:
        print('   ', n)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
u"""sheet102.py —— 第102轮目视把关（用户口径：「**一定要看录像而不是只读后台输出**」）。

只信 `[PASS]` 不算数，落两张**肉眼可核**的对照图到 `_evidence/`：

  ① `oneshot_props102.png` —— 148 张入库图集的缩略网格（带名字 + 尺寸）。
     一眼能看出"整张入库"意味着什么：**多块图集**（96×128 / 120×200 / 192×192…）
     全都在，块与块之间的排布**肉眼可见**，这正是下一轮要定死栅格语义的依据。
  ② `brightness_ascending102.png` —— 263 张房间背景**按亮度升序**铺开。
     这条是"房间偏暗"归因更正的**直观证据**：左边一大片就是原作本身暗的房间，
     而不是我们漏接了光照层。
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image, ImageDraw                                # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
PROPS = os.path.join(SCENES, 'oneshot_props')
BGDIR = os.path.join(SCENES, 'bg')
EV = os.path.join(os.path.dirname(HERE), '_evidence')
os.makedirs(EV, exist_ok=True)

BRI = json.load(io.open(os.path.join(EV, 'brightness102.json'), encoding='utf-8'))
ING = json.load(io.open(os.path.join(EV, 'ingest102.json'), encoding='utf-8'))
SIZES = {f['name']: (f['w'], f['h']) for f in ING['files']}


def fit(im, cw, ch, bg=(30, 30, 36)):
    """等比缩到 cw×ch 画布内，**不放大**（NEAREST 保像素感）。"""
    k = min(cw / im.width, ch / im.height, 1.0)
    w, h = max(1, int(im.width * k)), max(1, int(im.height * k))
    tile = Image.new('RGB', (cw, ch), bg)
    tile.paste(im.convert('RGBA').resize((w, h), Image.NEAREST),
               ((cw - w) // 2, (ch - h) // 2), im.convert('RGBA').resize((w, h), Image.NEAREST))
    return tile


# ------------------------------------------------------------------ ① 图集网格
names = sorted(SIZES)
COLS, CW, CH, PAD, LBL = 12, 96, 96, 6, 13
rows = (len(names) + COLS - 1) // COLS
W = COLS * (CW + PAD) + PAD
H = rows * (CH + LBL + PAD) + PAD + 24
sheet = Image.new('RGB', (W, H), (24, 24, 30))
dr = ImageDraw.Draw(sheet)
dr.text((PAD, 5), u'第102轮：OneShot 物件图集**整张**入库 %d 张（不切帧）' % len(names),
        fill=(220, 220, 230))
for i, nm in enumerate(names):
    col, row = i % COLS, i // COLS
    x = PAD + col * (CW + PAD)
    y = 24 + PAD + row * (CH + LBL + PAD)
    p = os.path.join(PROPS, nm + '.png')
    if os.path.isfile(p):
        sheet.paste(fit(Image.open(p), CW, CH), (x, y))
    else:
        dr.rectangle([x, y, x + CW, y + CH], outline=(200, 60, 60))
    w, h = SIZES[nm]
    dr.text((x + 1, y + CH + 1), '%s %dx%d' % (nm[:13], w, h), fill=(200, 200, 210))
out1 = os.path.join(EV, 'oneshot_props102.png')
sheet.save(out1)
print('① %s  %s  %d 张' % (out1, sheet.size, len(names)))

# ------------------------------------------------------------------ ② 亮度升序
by = sorted(BRI['rows'], key=lambda r: (r['lum'] if r['lum'] is not None else -1))
COLS2, CW2, CH2, PAD2, LBL2 = 16, 84, 62, 4, 11
rows2 = (len(by) + COLS2 - 1) // COLS2
W2 = COLS2 * (CW2 + PAD2) + PAD2
H2 = rows2 * (CH2 + LBL2 + PAD2) + PAD2 + 24
sheet2 = Image.new('RGB', (W2, H2), (24, 24, 30))
dr2 = ImageDraw.Draw(sheet2)
dr2.text((PAD2, 5),
         u'第102轮：263 张房间背景按亮度升序（左=最暗）—— 221 张"有实心瓦片却近黑"，'
         u'暗来自原作瓦片本身', fill=(220, 220, 230))
for i, r in enumerate(by):
    col, row = i % COLS2, i // COLS2
    x = PAD2 + col * (CW2 + PAD2)
    y = 24 + PAD2 + row * (CH2 + LBL2 + PAD2)
    p = os.path.join(BGDIR, 'oneshot_map%d.png' % r['room_id'])
    if os.path.isfile(p):
        sheet2.paste(fit(Image.open(p), CW2, CH2), (x, y))
    dr2.text((x + 1, y + CH2 + 1), '%d %s %.0f' % (r['room_id'], r['cls'], r['lum'] or 0),
             fill=(200, 200, 210))
out2 = os.path.join(EV, 'brightness_ascending102.png')
sheet2.save(out2)
print(u'② %s  %s  %d 张' % (out2, sheet2.size, len(by)))

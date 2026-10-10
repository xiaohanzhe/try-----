# -*- coding: utf-8 -*-
u"""probe103k.py —— 第103轮侦察 11：**逐格不透明包围盒精确表 + 单格放大图**。

目标：判断"艺术家在格内怎么摆精灵"，从而推出引擎锚点。
  S1 4 张代表图的**全部**格 bbox（不许只看聚合众数）
  S2 单格 ×8 放大（带格边框标注），直接看图
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image, ImageDraw                                            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
PROPS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'oneshot_props')

print('=' * 96)
print('S1 逐格 bbox 全表（x0,y0,x1,y1 相对格左上；格尺寸 cs）')
print('=' * 96)
for nm in ('bed', 'pc', 'DOORS', 'green_npc_cedric', 'items_tut',
           'water_waves_green_tall', 'red_rue'):
    fp = os.path.join(PROPS, nm + '.png')
    im = Image.open(fp).convert('RGBA')
    w, h = im.size
    cw, ch = w // 4, h // 4
    print('  %-24s %4dx%-4d 格=%dx%d' % (nm, w, h, cw, ch))
    for row in range(4):
        line = []
        for col in range(4):
            c = im.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch))
            bb = c.getchannel('A').getbbox()
            line.append('%-18s' % ('-' if bb is None else '%d,%d,%d,%d' % bb))
        print('     行%d  %s' % (row, ' '.join(line)))
    # 汇总：右/底余量
    bbs = []
    for row in range(4):
        for col in range(4):
            c = im.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch))
            bb = c.getchannel('A').getbbox()
            if bb:
                bbs.append(bb)
    if bbs:
        print('     -> 左余量 x0=%s  右余量 cs-x1=%s  上余量 y0=%s  下余量 cs-y1=%s'
              % (sorted({b[0] for b in bbs}), sorted({cw - b[2] for b in bbs}),
                 sorted({b[1] for b in bbs}), sorted({ch - b[3] for b in bbs})))
    print()

print('=' * 96)
print('S2 单格 ×8 放大（青色虚线 = 格边界；红色十字 = 格中心）')
print('=' * 96)
Z = 8
for nm in ('bed', 'pc', 'DOORS', 'green_npc_cedric'):
    im = Image.open(os.path.join(PROPS, nm + '.png')).convert('RGBA')
    w, h = im.size
    cw, ch = w // 4, h // 4
    parts = []
    for col in range(4):
        c = im.crop((col * cw, 0, (col + 1) * cw, ch))
        big = c.resize((cw * Z, ch * Z), Image.NEAREST)
        bg = Image.new('RGBA', big.size, (24, 24, 32, 255))
        bg.alpha_composite(big)
        d = ImageDraw.Draw(bg)
        d.rectangle([0, 0, cw * Z - 1, ch * Z - 1], outline=(0, 255, 255, 255))
        cxm, cym = cw * Z // 2, ch * Z // 2
        d.line([cxm - 6, cym, cxm + 6, cym], fill=(255, 0, 0, 255))
        d.line([cxm, cym - 6, cxm, cym + 6], fill=(255, 0, 0, 255))
        parts.append(bg)
    W = sum(p.size[0] for p in parts) + 3 * 6
    sheet = Image.new('RGBA', (W, parts[0].size[1]), (24, 24, 32, 255))
    x = 0
    for p in parts:
        sheet.alpha_composite(p, (x, 0))
        x += p.size[0] + 6
    out = os.path.join(EV, 'cell_%s103.png' % nm)
    sheet.save(out)
    print('  %-24s 格=%dx%d  -> %s  %s' % (nm, cw, ch, os.path.basename(out), sheet.size))

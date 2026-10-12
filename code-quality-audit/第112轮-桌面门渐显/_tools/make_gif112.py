# -*- coding: utf-8 -*-
"""把 `anim112.py` 产出的帧序列编成 **GIF**（无 ffmpeg 时的替代）。

用户要「看录像」—— 静态长图看得出"越来越实"，但看不出"过程"。
本脚本用 Pillow 把 31 帧编成循环 GIF（缩到 640 宽，控制体积）。

跑法：
    C:\\Python311\\python.exe make_gif112.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, '..', '_evidence', 'anim112'))
FRAMES = os.path.join(OUT, 'frames')

try:
    from PIL import Image
except Exception as e:
    print(u'[FATAL] Pillow 不可用: %s' % e)
    sys.exit(2)

files = sorted(f for f in os.listdir(FRAMES) if f.endswith('.png'))
if not files:
    print(u'[FATAL] 没有帧')
    sys.exit(3)

imgs = []
W = 720
for f in files:
    im = Image.open(os.path.join(FRAMES, f)).convert('RGB')
    h = int(im.height * W / float(im.width))
    imgs.append(im.resize((W, h), Image.LANCZOS))

p = os.path.join(OUT, 'reveal112.gif')
imgs[0].save(p, save_all=True, append_images=imgs[1:],
             duration=90, loop=0, optimize=True)
print(u'GIF -> %s  (%.1f KB, %d 帧, %dx%d)'
      % (os.path.basename(p), os.path.getsize(p) / 1024.0,
         len(imgs), imgs[0].width, imgs[0].height))

# 再来一张"只裁 UT 门 + 三角符文门区域"的特写 GIF（看得更清）
# ★ 真机实测几何（见 composite112 输出）：画面 x747 y400 1066x800，scale=3.33125
#   UT 门房间 (0,70) 44x99  ⇒ 屏幕 x≈747~894、y≈633~963
#   符文门房间 (284,94) 36x52 ⇒ 屏幕 x≈747+946=1693~1813、y≈713~886
#   ⇒ 裁 x=690..1900 / y=580..1010 把两扇渐变门一起框进来
BOX = (690, 580, 1900, 1010)
imgs2 = []
for f in files:
    im = Image.open(os.path.join(FRAMES, f)).convert('RGB')
    l, t, r, b = BOX
    box = (max(0, l), max(0, t), min(im.width, r), min(im.height, b))
    imgs2.append(im.crop(box))
# 缩到宽 900 控制体积
imgs2 = [i.resize((900, int(i.height * 900 / float(i.width))), Image.LANCZOS)
         for i in imgs2]
p2 = os.path.join(OUT, 'reveal112_doors_zoom.gif')
imgs2[0].save(p2, save_all=True, append_images=imgs2[1:],
              duration=90, loop=0, optimize=True)
print(u'GIF(两门特写) -> %s  (%.1f KB)'
      % (os.path.basename(p2), os.path.getsize(p2) / 1024.0))

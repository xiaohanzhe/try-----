# -*- coding: utf-8 -*-
"""第49轮 · 把导出的扭蛋球/角色精灵帧蒸馏进产品资产目录。

源: E:\\Download\\_tmp\\drw\\chapter3_windows\\spr49\\*.png
目标: ralsei_pet/assets/bubble/<spr>_<i>.png

用法: C:\\Python311\\python.exe distill_spr49.py
"""
import io
import os
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SRC = r'E:\Download\_tmp\drw\chapter3_windows\spr49'
DST = os.path.join(REPO, 'ralsei_pet', 'assets', 'bubble')

if not os.path.isdir(SRC):
    print('缺源目录 %s' % SRC)
    sys.exit(1)
if not os.path.isdir(DST):
    os.makedirs(DST)
n = 0
miss = []
for f in sorted(os.listdir(SRC)):
    if not f.endswith('.png'):
        continue
    out = os.path.join(DST, f)
    ok = False
    for _ in range(4):
        try:
            shutil.copyfile(os.path.join(SRC, f), out)
            ok = True
            break
        except OSError:
            pass
    if ok:
        n += 1
    else:
        miss.append(f)
print('蒸馏 %d 个 PNG -> %s' % (n, DST))
if miss:
    print('失败:', miss)

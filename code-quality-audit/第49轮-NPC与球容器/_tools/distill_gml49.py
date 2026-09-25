# -*- coding: utf-8 -*-
"""第49轮 · 把 UTMT 反编译产物蒸馏进仓库 _evidence/gml/。

命名与第48轮一致：ch<N>.<code名>.gml（去掉 gml_Object_/gml_GlobalScript_/gml_Script_ 前缀）。

用法: C:\\Python311\\python.exe distill_gml49.py
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
DST = os.path.join(ROUND, '_evidence', 'gml')
DRW = r'E:\Download\_tmp\drw'

PREFIXES = ('gml_Object_', 'gml_GlobalScript_', 'gml_Script_', 'gml_RoomCC_')


def short(name):
    for p in PREFIXES:
        if name.startswith(p):
            return name[len(p):]
    return name


if not os.path.isdir(DST):
    os.makedirs(DST)
total = 0
for idx in (1, 2, 3, 4, 5):
    src = os.path.join(DRW, 'chapter%d_windows' % idx, 'gml49')
    if not os.path.isdir(src):
        print('缺 %s' % src)
        continue
    n = 0
    for f in sorted(os.listdir(src)):
        if not f.endswith('.gml'):
            continue
        try:
            t = io.open(os.path.join(src, f), encoding='utf-8').read()
        except OSError:
            continue
        out = os.path.join(DST, 'ch%d.%s' % (idx, short(f[:-4]) + '.gml'))
        for _ in range(4):
            try:
                with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
                    fh.write(t)
                n += 1
                break
            except OSError:
                pass
    print('ch%d 蒸馏 %d 个 .gml' % (idx, n))
    total += n
print('合计 %d' % total)

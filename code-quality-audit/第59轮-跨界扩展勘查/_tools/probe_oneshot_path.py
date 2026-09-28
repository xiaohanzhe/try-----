# -*- coding: utf-8 -*-
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
print('BASE 存在 =', os.path.isdir(BASE))
print('BASE 下:', os.listdir(BASE) if os.path.isdir(BASE) else 'N/A')

SUB = os.path.join(BASE, 'OneShot.World.Machine.Edition.Build.16512634')
print()
print('SUB 存在 =', os.path.isdir(SUB))
if os.path.isdir(SUB):
    for x in sorted(os.listdir(SUB)):
        p = os.path.join(SUB, x)
        print('  %-50s %s' % (x, 'DIR' if os.path.isdir(p) else os.path.getsize(p)))

GD = os.path.join(SUB, 'content', 'gamedata')
print()
print('gamedata 存在 =', os.path.isdir(GD))
if os.path.isdir(GD):
    for x in sorted(os.listdir(GD)):
        p = os.path.join(GD, x)
        print('  %-45s %s' % (x, 'DIR(%d)' % len(os.listdir(p)) if os.path.isdir(p)
                              else os.path.getsize(p)))

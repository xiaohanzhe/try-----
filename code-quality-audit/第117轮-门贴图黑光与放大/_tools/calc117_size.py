# -*- coding: utf-8 -*-
u"""第117轮：验「大一点都」落到了哪（用**产品真函数**算，不是另写一份公式）。

真机口径：屏 2560×1600；`_cached_scale_factor` 被 `PET_MAX_LONG_SIDE_PX=144` 钳过
⇒ `pet_box = pet_screen_box(144/69)` = (144, 98)。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

import desk_doors as D                                        # noqa: E402
from PIL import Image                                         # noqa: E402

OBJS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs')
DESK = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'desktop.json')

LETTERS = {'obj_doorA': 'A', 'obj_doorB': 'B', 'obj_doorC': 'C', 'obj_doorD': 'D'}

data = json.load(io.open(DESK, encoding='utf-8'))
sizes = {}
names = {}
for o in data['objects']:
    L = LETTERS.get(o.get('src'))
    if not L:
        continue
    p = os.path.join(OBJS, os.path.basename(o['sprite']))
    if not os.path.isfile(p):
        sys.stdout.write('!! 缺素材 %s\n' % p)
        continue
    with Image.open(p) as im:
        sizes[L] = im.size
    names[L] = o['sprite']

k_pet = float(D.PET_MAX_LONG_SIDE_PX) / float(max(D.PET_BOX_LOGICAL))
pet_box = D.pet_screen_box(k_pet)
k_uniform = D.fit_doors_uniform_scale(sizes, pet_box)

sys.stdout.write('CAP=%r  pet_box=%r  k=%.4f\n' % (D.DOOR_FIT_CAP, pet_box, k_uniform))
plan = D.plan_screen_doors(sizes, 2560, 1600, pet_box=pet_box)
sys.stdout.write('\n%-2s %-34s %-11s %s\n' % ('字母', '贴图', '原始尺寸', '屏幕矩形 (x,y,w,h)'))
for L, r in plan:
    sys.stdout.write('%-2s %-34s %-11s %r\n'
                     % (L, os.path.basename(names[L]), '%dx%d' % sizes[L], r))

# 与第116轮实测（k=0.759）的对比：写死的是**当时的实测值**，只作对照，不当判据
OLD = {'A': (33, 42), 'B': (146, 97), 'C': (33, 75), 'D': (137, 118)}
sys.stdout.write('\n-- 相对第116轮实测（整屏 2560×1600）--\n')
for L, r in plan:
    ow, oh = OLD.get(L, (0, 0))
    if ow:
        sys.stdout.write('  %s: %dx%d → %dx%d  (宽 %+.0f%%, 高 %+.0f%%)\n'
                         % (L, ow, oh, r[2], r[3],
                            100.0 * (r[2] - ow) / ow, 100.0 * (r[3] - oh) / oh))

# 贴边自检：top/bottom 水平居中且贴边；left/right 垂直居中且贴边
sw, sh = 2560, 1600
bad = []
for side, L in D.SIDE_LETTERS:
    r = dict(plan).get(L)
    if not r:
        continue
    x, y, w, h = r
    if side == 'top':
        ok = (y == 0) and abs((x + w / 2.0) - sw / 2.0) <= 1
    elif side == 'bottom':
        ok = (y + h == sh) and abs((x + w / 2.0) - sw / 2.0) <= 1
    elif side == 'left':
        ok = (x == 0) and abs((y + h / 2.0) - sh / 2.0) <= 1
    else:
        ok = (x + w == sw) and abs((y + h / 2.0) - sh / 2.0) <= 1
    if not ok:
        bad.append((side, L, r))
sys.stdout.write('\n贴边自检：%s\n' % ('OK' if not bad else 'FAIL %r' % (bad,)))

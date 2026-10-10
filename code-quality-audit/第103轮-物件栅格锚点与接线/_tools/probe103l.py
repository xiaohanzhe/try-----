# -*- coding: utf-8 -*-
u"""probe103l.py —— 第103轮侦察 12：**切帧规模量化 + 可画性体检**。

要花多少文件？哪些画不出来？先把账算清：
  A 全部可见物件里，distinct (character_name, col, row) 组合有多少
  B 每个 cn 用到几格 / 哪些 cn 缺文件
  C 每间房的物件数分布 / 单个物件最大格
  D always_on_bottom / always_on_top 各多少（绘序覆盖）
  E tile_id>0（贴瓦片）的事件多少 —— 这些**不进**物件表
"""
import collections
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')
PROPS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'oneshot_props')
DIR_ROW = {2: 0, 4: 1, 6: 2, 8: 3}
HAVE = set(f[:-4] for f in os.listdir(PROPS) if f.endswith('.png'))


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


cells = collections.Counter()
per_cn = collections.Counter()
per_room = {}
aob_aot = collections.Counter()
tileid_events = 0
no_cn_events = 0
missing = collections.Counter()
bad_dir = collections.Counter()
pat_hist = collections.Counter()
n_obj = 0
for n in range(1, 400):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p):
        continue
    cnt = 0
    for e in rj(p).get('events', []):
        pgs = e.get('pages') or []
        if not pgs:
            continue
        pg = pgs[0]
        g = pg.get('graphic') or {}
        if int(g.get('tile_id') or 0) > 0:
            tileid_events += 1
            continue
        nm = (g.get('character_name') or '').strip()
        if not nm:
            no_cn_events += 1
            continue
        n_obj += 1
        cnt += 1
        d = int(g.get('direction') or 0)
        pat = int(g.get('pattern') or 0)
        pat_hist[pat] += 1
        if d not in DIR_ROW:
            bad_dir[d] += 1
        row = DIR_ROW.get(d, 0)
        col = pat
        cells[(nm, col, row)] += 1
        per_cn[nm] += 1
        if nm not in HAVE:
            missing[nm] += 1
        if pg.get('always_on_bottom'):
            aob_aot['bottom'] += 1
        if pg.get('always_on_top'):
            aob_aot['top'] += 1
    if cnt:
        per_room[n] = cnt

print('=' * 96)
print('A 切帧规模')
print('=' * 96)
print('  可见物件总数 %d' % n_obj)
print('  distinct (sheet,col,row) 组合数 = **%d**  <- 切帧要产出的文件数' % len(cells))
print('  distinct sheet = %d（有文件 %d，缺 %d 张：%s）'
      % (len(per_cn), len([c for c in per_cn if c in HAVE]),
         len([c for c in per_cn if c not in HAVE]),
         sorted(c for c in per_cn if c not in HAVE)))
# 估算字节
tot_b = 0
for (nm, col, row), _cnt in cells.items():
    if nm not in HAVE:
        continue
    im = Image.open(os.path.join(PROPS, nm + '.png')).convert('RGBA')
    w, h = im.size
    cw, ch = w // 4, h // 4
    c = im.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch))
    b = io.BytesIO()
    c.save(b, 'PNG', optimize=True)
    tot_b += b.tell()
print('  切帧后总体积 ≈ %.2f MB（PNG optimize）' % (tot_b / 1048576.0))

print()
print('=' * 96)
print('B 每张图集用到几格（前 15）')
print('=' * 96)
per_cn_cells = collections.Counter()
for (nm, _c, _r) in cells:
    per_cn_cells[nm] += 1
for nm, k in per_cn_cells.most_common(15):
    print('    %-26s 用 %2d 格 / 物件 %4d  %s' % (nm, k, per_cn[nm],
                                                '' if nm in HAVE else '★缺文件'))

print()
print('=' * 96)
print('C 每间房的物件数分布')
print('=' * 96)
h = collections.Counter()
for rid, c in per_room.items():
    h[c // 20 * 20] += 1
print('  有物件的房 %d 间；物件总数 %d' % (len(per_room), sum(per_room.values())))
print('  按 20 分档：%s' % dict(sorted(h.items())))
top = sorted(per_room.items(), key=lambda kv: -kv[1])[:10]
print('  物件最多的 10 间：%s' % top)

print()
print('=' * 96)
print('D 绘序覆盖标记 / E 贴瓦片事件 / pattern 分布 / 方向异常')
print('=' * 96)
print('  always_on_bottom=%d  always_on_top=%d' % (aob_aot['bottom'], aob_aot['top']))
print('  tile_id>0 事件 = %d（贴瓦片，不进物件表）' % tileid_events)
print('  无 character_name 且无 tile_id 的事件 = %d' % no_cn_events)
print('  pattern 分布 = %s' % dict(sorted(pat_hist.items())))
print('  非 2/4/6/8 的 direction = %s' % (dict(bad_dir) if bad_dir else '无'))
print('  合计校验：%d + %d + %d = %d'
      % (n_obj, tileid_events, no_cn_events, n_obj + tileid_events + no_cn_events))

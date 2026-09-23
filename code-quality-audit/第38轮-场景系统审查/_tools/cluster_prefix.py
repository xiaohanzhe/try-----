# -*- coding: utf-8 -*-
"""第 38 轮：把五章 1,251 个 room 按资源名前缀聚类，供设计 region/area 划分。

只读。输出每个聚类：计数 + 样例名 + 是否含官方命名房间（scr_roomname）。
"""
import io
import json
import os
import re
from collections import OrderedDict

DR = r'E:\Download\_tmp\dr_out'
DRW = r'E:\Download\_tmp\drw'
ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PAIRS = [('ch1', 'chapter1_windows'), ('ch2', 'chapter2_windows'),
         ('ch3', 'chapter3_windows'), ('ch4', 'chapter4_windows'),
         ('ch5', 'chapter5_windows')]
EV = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查', '_evidence')

out = []


def w(s=''):
    out.append(str(s))
    print(s)


# 已知的前缀"噪音词"，剥掉后剩下的头两段才是区域线索
NOISE = ('room_', 'dw_', 'ch1_', 'ch2_', 'ch3_', 'ch4_', 'ch5_', 'gml_')

NONSCENE = [
    re.compile(r'^ROOM_INITIALIZE$'), re.compile(r'^PLACE_'),
    re.compile(r'debug|failsafe', re.I), re.compile(r'test', re.I),
    re.compile(r'title_placeholder', re.I),
    re.compile(r'^(room_empty|room_DARKempty)$'),
]
MAYBE = [re.compile(r'^(room_legend|room_chapter_continue|room_shop1|room_shop2)$'),
         re.compile(r'unusedroom', re.I), re.compile(r'room_myroom_dark')]


def keep(name):
    for rx in NONSCENE:
        if rx.search(name):
            return False
    for rx in MAYBE:
        if rx.search(name):
            return 'maybe'
    return True


for ch, folder in PAIRS:
    d = json.loads(io.open(os.path.join(DR, folder, 'rooms_map.json'),
                           'r', encoding='utf-8').read())
    rooms = d.get('rooms') if isinstance(d, dict) else d
    names = [str(r.get('name') or '') for r in rooms]
    txt = io.open(os.path.join(DRW, folder, '_roomname_code.txt'),
                  'r', encoding='utf-8').read()
    official = set(int(x) for x in re.findall(r'if \(arg0 == (\d+)\)', txt))

    clusters = OrderedDict()
    for i, n in enumerate(names):
        st = keep(n)
        if st is False:
            continue
        base = n
        for p in NOISE:
            if base.startswith(p):
                base = base[len(p):]
                break
        toks = [t for t in base.split('_') if t]
        key = '_'.join(toks[:2]) if len(toks) >= 2 else (toks[0] if toks else '<empty>')
        c = clusters.setdefault(key, {'n': 0, 'maybe': 0, 'official': [], 'sample': []})
        c['n'] += 1
        if st == 'maybe':
            c['maybe'] += 1
        if i in official:
            c['official'].append(names[i])
        if len(c['sample']) < 3:
            c['sample'].append(names[i])

    w('########## %s : %d 个可当场景，%d 个聚类 ##########'
      % (ch, sum(c['n'] for c in clusters.values()), len(clusters)))
    for k, c in sorted(clusters.items(), key=lambda kv: -kv[1]['n']):
        w('  %-24s n=%-3d maybe=%-2d official=%-2d  %s'
          % (k, c['n'], c['maybe'], len(c['official']), c['sample']))
    w('')

os.makedirs(EV, exist_ok=True)
with io.open(os.path.join(EV, '房间前缀聚类.txt'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
print('written')

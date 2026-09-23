# -*- coding: utf-8 -*-
"""第 38 轮：打印五章 room 名的**首词清单**（紧凑），供手写 regex→area 规则表。"""
import io
import json
import os
import re
from collections import Counter

DR = r'E:\Download\_tmp\dr_out'
PAIRS = [('ch1', 'chapter1_windows'), ('ch2', 'chapter2_windows'),
         ('ch3', 'chapter3_windows'), ('ch4', 'chapter4_windows'),
         ('ch5', 'chapter5_windows')]
EV = (r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
      r'\code-quality-audit\第38轮-场景系统审查\_evidence')
out = []


def w(s=''):
    out.append(str(s))
    print(s)


NONSCENE = [re.compile(r'^ROOM_INITIALIZE$'), re.compile(r'^PLACE_'),
            re.compile(r'debug|failsafe', re.I), re.compile(r'test', re.I),
            re.compile(r'title_placeholder', re.I),
            re.compile(r'^(room_empty|room_DARKempty)$')]

for ch, folder in PAIRS:
    d = json.loads(io.open(os.path.join(DR, folder, 'rooms_map.json'),
                           'r', encoding='utf-8').read())
    rooms = d.get('rooms') if isinstance(d, dict) else d
    names = [str(r.get('name') or '') for r in rooms]
    cnt = Counter()
    for n in names:
        if any(rx.search(n) for rx in NONSCENE):
            continue
        base = n
        if base.startswith('room_'):
            base = base[5:]
        base = re.sub(r'^(dw|ch\d)_', '', base)
        toks = [t for t in base.split('_') if t]
        cnt[toks[0] if toks else '<empty>'] += 1
    w('=== %s  首词 %d 个（共 %d 个可当场景）==='
      % (ch, len(cnt), sum(cnt.values())))
    w('  ' + '  '.join('%s:%d' % (k, v) for k, v in cnt.most_common()))
    w('')

os.makedirs(EV, exist_ok=True)
with io.open(os.path.join(EV, '房间首词清单.txt'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
print('written')

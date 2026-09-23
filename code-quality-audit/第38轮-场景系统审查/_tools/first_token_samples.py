# -*- coding: utf-8 -*-
"""第 38 轮：按首词分组，打印每组最多 6 个样例全名（ch2~ch5 重点）。只读。"""
import io
import json
import os
import re
from collections import OrderedDict

DR = r'E:\Download\_tmp\dr_out'
PAIRS = [('ch2', 'chapter2_windows'), ('ch3', 'chapter3_windows'),
         ('ch4', 'chapter4_windows'), ('ch5', 'chapter5_windows')]
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
    groups = OrderedDict()
    for n in names:
        if any(rx.search(n) for rx in NONSCENE):
            continue
        base = re.sub(r'^room_', '', n)
        base = re.sub(r'^(dw|ch\d)_', '', base)
        toks = [t for t in base.split('_') if t]
        k = toks[0] if toks else '<empty>'
        groups.setdefault(k, []).append(n)
    w('########## %s ##########' % ch)
    for k, lst in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        w('  [%s] n=%d' % (k, len(lst)))
        w('      ' + ' | '.join(lst[:6]))
        if len(lst) > 6:
            w('      … 共 %d' % len(lst))
    w('')

os.makedirs(EV, exist_ok=True)
with io.open(os.path.join(EV, '首词样例清单.txt'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
print('written')

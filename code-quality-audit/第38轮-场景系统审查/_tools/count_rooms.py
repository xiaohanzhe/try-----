# -*- coding: utf-8 -*-
"""第 38 轮：量化原作房间真实规模 vs 我们登记的场景数。

只读。数据源 = 第 37 轮 UTMT 导出的 `rooms_map.json`（E:\\Download\\_tmp\\dr_out）。
"""
import io
import json
import os

DR = r'E:\Download\_tmp\dr_out'
CHS = ['chapter1_windows', 'chapter2_windows', 'chapter3_windows',
       'chapter4_windows', 'chapter5_windows']

out = []


def w(s=''):
    out.append(str(s))
    print(s)


sample_shown = False
totals = {}
for ch in CHS:
    p = os.path.join(DR, ch, 'rooms_map.json')
    if not os.path.isfile(p):
        w('%s  MISSING' % ch)
        continue
    with io.open(p, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        rooms = data.get('rooms') or data
    else:
        rooms = data
    n = len(rooms)
    totals[ch] = n
    if not sample_shown:
        k = list(rooms)[0] if isinstance(rooms, dict) else 0
        w('--- %s 结构样例 ---' % ch)
        w('  type=%s' % type(rooms).__name__)
        w('  first key = %r' % (k,))
        w('  first val = %s' % json.dumps(
            rooms[k] if isinstance(rooms, dict) else rooms[0],
            ensure_ascii=False)[:400])
        w('')
        sample_shown = True
    w('%s  房间数 = %d' % (ch, n))

w('')
w('五章房间合计 = %d' % sum(totals.values()))

ev = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第38轮-场景系统审查\_evidence'
os.makedirs(ev, exist_ok=True)
with io.open(os.path.join(ev, '原作房间规模量化.txt'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
print('ok')

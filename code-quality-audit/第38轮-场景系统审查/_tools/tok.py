# -*- coding: utf-8 -*-
"""第 38 轮：统计 1,013 个 scene 资源名的尾段词频（用于设计中文命名词典）。

口径：把资源名去掉 `room_` 前缀、按 `_` 切词，丢掉纯数字/单字母/已知区域前缀，
剩下的词按出现次数排序。
"""
import collections
import io
import json
import os
import re

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
EV = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查', '_evidence')

table = json.loads(io.open(os.path.join(EV, '房间表_全量.json'),
                           'r', encoding='utf-8').read())
FLAT = [r for ch in table for r in table[ch]]
scenes = [r for r in FLAT if r['cls'] == 'scene']

# 区域自身的名字段（`room_dw_mansion_east_2f` 里的 mansion/east 不该进"尾段"）
AREA_TOKENS = set('''
lw dw cc dark castle town city cyber mansion teevie tv b3bs board couch ranking
puzzlecloset snow green church churchb churchc garden cliff fcastle castle_
field forest cc_ noellehouse ralsei_castle fcount
'''.split())

cnt = collections.Counter()
uniq = collections.Counter()
for r in scenes:
    nm = r['resource']
    body = re.sub(r'^room_', '', nm)
    toks = [t for t in body.split('_') if t]
    for t in toks:
        if re.fullmatch(r'\d+', t) or len(t) <= 1:
            continue
        cnt[t] += 1
    uniq[tuple(sorted(set(toks)))] += 1

out = []
out.append('=== scene 房间数 = %d ===' % len(scenes))
out.append('')
out.append('--- 尾段词频 Top 120 ---')
for t, n in cnt.most_common(120):
    out.append('  %-26s %4d' % (t, n))
out.append('')
out.append('总不同词数 = %d' % len(cnt))
out.append('')
out.append('--- 含"数字变体"的词（area1/2/3 …）---')
for t, n in cnt.most_common():
    if re.search(r'\d', t):
        out.append('  %-26s %4d' % (t, n))
out.append('')
out.append('--- 按区域统计 room 数量 ---')
byarea = collections.Counter()
for r in scenes:
    byarea[(r['chapter'], r['area_id'])] += 1
for k in sorted(byarea):
    out.append('  %-6s %-20s %3d' % (k[0], k[1], byarea[k]))
out.append('')
out.append('章节×区域 组合数 = %d' % len(byarea))

txt = '\n'.join(out)
io.open(os.path.join(EV, '尾段词频.txt'), 'w', encoding='utf-8').write(txt + '\n')
print(txt[:3600])
print('...')
print('written 尾段词频.txt')

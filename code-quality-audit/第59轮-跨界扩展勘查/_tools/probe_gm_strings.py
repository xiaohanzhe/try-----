# -*- coding: utf-8 -*-
"""从 GameMaker data（GEN8）里提取可读字符串 —— 用于**实证**角色/精灵名。

不解析 chunk 结构，只做"字符串表扫描"：GEN8 的字符串以 4 字节长度前缀 + UTF-8 存储，
但简单起见用正则扫可读 ASCII/UTF-8 串，再按前缀过滤（spr_/obj_/scr_/mus_ 等）。
★ 这是**筛查**，不是权威解析 —— 结论只用于"该去问哪些角色"，不作为数据源。
"""
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RX = re.compile(rb'[\x20-\x7e]{4,48}')
NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]{2,47}$')

for name, path in (('undertale', r'E:\Download\apk_extract\undertale\assets\game.droid'),
                   ('huanghun', r'E:\Download\apk_extract\huanghun\assets\game.droid')):
    print('=' * 78)
    print('[%s] %s' % (name, path))
    data = open(path, 'rb').read()
    print('  大小 %.1f MB' % (len(data) / 1048576.0))
    toks = RX.findall(data)
    print('  可读串 %d 个 / 去重 %d' % (len(toks), len(set(toks))))
    c = Counter(t.decode('ascii', 'ignore') for t in toks)
    pref = Counter()
    for s in c:
        m = re.match(r'^([a-z]{2,4})_', s)
        if m:
            pref[m.group(1)] += 1
    print('  前缀分布 top20：%s' % pref.most_common(20))
    # 角色名常见形态：spr_xxx / obj_xxx / 大写名
    for pat in (r'^spr_([a-z0-9_]+)$', r'^obj_([a-z0-9_]+)$'):
        rx = re.compile(pat)
        got = sorted({rx.match(s).group(1) for s in c if rx.match(s)})
        print('  [%s] %d 个：%s' % (pat, len(got), ', '.join(got[:60])))
    del data

# -*- coding: utf-8 -*-
"""追加详版 §23.14。"""
import io
import os

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
DETAIL = os.path.join(ROOT, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')
APPEND = os.path.join(ROOT, 'code-quality-audit', '第34轮-移动行为基础代码严查',
                      '_evidence', '_detail_append_2314.md')

before = io.open(DETAIL, encoding='utf-8').read()
add = io.open(APPEND, encoding='utf-8').read()

if '### §23.14 第 34 轮续二' in before:
    print('已存在，跳过')
else:
    merged = before.rstrip('\n') + '\n' + add
    io.open(DETAIL, 'w', encoding='utf-8', newline='\n').write(merged)
    print('已追加；%d -> %d 字符（增 %d）' % (len(before), len(merged), len(merged) - len(before)))

after = io.open(DETAIL, encoding='utf-8').read()
for k in ['§23.14 第 34 轮续二', 'F34-1', 'PASS=1440', '138×94', '三次自我推翻']:
    print('核验 %-20s = %s' % (k, k in after))

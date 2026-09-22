# -*- coding: utf-8 -*-
"""追加当日日志（用文件拼接）。"""
import io
import os

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
LOG = os.path.join(ROOT, '.workbuddy', 'memory', '2026-09-22.md')
APPEND = os.path.join(ROOT, 'code-quality-audit', '第34轮-移动行为基础代码严查',
                      '_evidence', '_log_append_34f.md')

before = io.open(LOG, encoding='utf-8').read()
add = io.open(APPEND, encoding='utf-8').read()

if '## 第 34 轮（续二）：移动核心节拍缺陷 F34-1' in before:
    print('已存在，跳过')
else:
    merged = before.rstrip('\n') + '\n' + add
    io.open(LOG, 'w', encoding='utf-8', newline='\n').write(merged)
    print('已追加；%d -> %d 字符' % (len(before), len(merged)))

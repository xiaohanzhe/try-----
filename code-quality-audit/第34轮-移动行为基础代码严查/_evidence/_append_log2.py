# -*- coding: utf-8 -*-
"""把第 34 轮（续）追加进当日工作日志，逐字节核验。"""
import os

LOG = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\.workbuddy\memory\2026-09-22.md'
ADD = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第34轮-移动行为基础代码严查\_evidence\_log_append_34b.md'

with open(LOG, 'r', encoding='utf-8') as f:
    old = f.read()
with open(ADD, 'r', encoding='utf-8') as f:
    add = f.read()

before = len(old)
new = old.rstrip('\n') + '\n' + add
assert new[:before] == old, 'PREFIX MISMATCH'

with open(LOG, 'w', encoding='utf-8', newline='') as f:
    f.write(new)

with open(LOG, 'r', encoding='utf-8') as f:
    back = f.read()

print('before chars:', before)
print('after  chars:', len(back))
print('prefix identical:', back[:before] == old)
print('has F7 section:', 'F7：本轮最重发现' in back)
print('has has_ball:', 'has_ball` 是恒假字段' in back)
print('bytes:', os.path.getsize(LOG))

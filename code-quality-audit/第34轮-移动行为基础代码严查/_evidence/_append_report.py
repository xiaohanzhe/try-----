# -*- coding: utf-8 -*-
"""把 §11/§12 追加进第 34 轮报告，逐字节核验"只追加、未改写"。"""
import os

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
REPORT = os.path.join(REPO, '第三十四轮移动行为基础代码严查报告_2026-09-22.md')
ADD = os.path.join(REPO, 'code-quality-audit', '第34轮-移动行为基础代码严查',
                   '_evidence', '_report_append_11_12.md')

with open(REPORT, 'r', encoding='utf-8') as f:
    old = f.read()
with open(ADD, 'r', encoding='utf-8') as f:
    add = f.read()

before = len(old)
new = old.rstrip('\n') + '\n' + add
assert new[:before] == old, 'PREFIX MISMATCH'

with open(REPORT, 'w', encoding='utf-8', newline='') as f:
    f.write(new)

with open(REPORT, 'r', encoding='utf-8') as f:
    back = f.read()

print('before chars:', before)
print('after  chars:', len(back))
print('prefix identical:', back[:before] == old)
print('has §11:', '## 十一、' in back)
print('has §12:', '## 十二、' in back)
print('has 11.5:', '### 11.5' in back)
print('has 12.5:', '### 12.5' in back)
print('bytes:', os.path.getsize(REPORT))

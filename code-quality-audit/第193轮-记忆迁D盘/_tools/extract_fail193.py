# -*- coding: utf-8 -*-
r"""把 regress193.txt 里 `[FAIL]` 字面量的每一处上下文抠出来，逐条定性。"""
import io
import sys

P = r'D:\_tmp\regress193.txt'
KEY = '[FAIL]'
with io.open(P, 'r', encoding='utf-8', errors='replace', newline='') as fh:
    text = fh.read()

lines = text.split('\n')
total = 0
for i, ln in enumerate(lines, 1):
    if KEY not in ln:
        continue
    suite = ln.split()[0] if ln.split() else '?'
    pos = 0
    while True:
        j = ln.find(KEY, pos)
        if j < 0:
            break
        total += 1
        a = max(0, j - 42)
        b = min(len(ln), j + len(KEY) + 42)
        seg = ln[a:b].replace('\t', ' ')
        print('%3d行 %-10s ...%s...' % (i, suite, seg))
        pos = j + len(KEY)

print('')
print('字面量总数 = %d' % total)
real_fail = 0
# 真失败行的特征：行首是套件名 + 数字列（suite / exit / PASS / FAIL / 比对）
for i, ln in enumerate(lines, 1):
    parts = ln.split()
    # 列序：suite / exit / PASS / FAIL / 比对
    if len(parts) >= 5 and all(p.isdigit() for p in parts[1:4]):
        if parts[3] != '0':
            print('!! 真失败行 %d (FAIL=%s): %s' % (i, parts[3], ln[:80]))
            real_fail += 1
print('真失败行数 = %d（必须 0）' % real_fail)
sys.exit(0)

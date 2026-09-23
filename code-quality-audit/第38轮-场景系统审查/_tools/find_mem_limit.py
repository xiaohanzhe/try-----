# -*- coding: utf-8 -*-
"""从 WorkBuddy 打包产物里找「记忆注入上限」的真实数字。"""
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

CANDIDATES = [
    r'D:\LenovoSoftstore\Install\WorkBuddy\resources\app.asar.unpacked\cli\dist\codebuddy-headless.js',
    r'D:\LenovoSoftstore\Install\WorkBuddy\resources\app.asar.unpacked\cli\dist\codebuddy-lite-wb.mjs',
]

NEEDLES = [
    'exceeded the size limit',
    'MEMORY.md is too large',
    'memory truncated',
]


def scan(path):
    if not os.path.isfile(path):
        print('MISSING', path)
        return
    size = os.path.getsize(path)
    print('=' * 70)
    print('FILE', path, 'bytes=', size)
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        text = fh.read()
    for needle in NEEDLES:
        start = 0
        hits = 0
        while hits < 3:
            i = text.find(needle, start)
            if i < 0:
                break
            hits += 1
            lo = max(0, i - 1200)
            hi = min(len(text), i + 900)
            snippet = text[lo:hi]
            print('-' * 70)
            print('needle=%r  at=%d' % (needle, i))
            print(snippet)
            start = i + len(needle)
        if hits == 0:
            print('(no hit) %r' % needle)
    # 顺带找可能的数字常量
    print('-' * 70)
    print('numeric candidates near MEMORY:')
    for m in re.finditer(r'MEMORY\.md', text):
        i = m.start()
        seg = text[max(0, i - 300):i + 300]
        nums = re.findall(r'\b\d{4,6}\b', seg)
        if nums:
            print('  at', i, '->', sorted(set(nums))[:8])
            if len(nums) > 0:
                print('     ctx:', seg.replace('\n', ' ')[:400])


for p in CANDIDATES:
    scan(p)

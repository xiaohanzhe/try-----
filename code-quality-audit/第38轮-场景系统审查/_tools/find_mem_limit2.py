# -*- coding: utf-8 -*-
"""找「ACTION REQUIRED ... truncated during injection」这条提醒的真实阈值。"""
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

FILES = [
    r'D:\LenovoSoftstore\Install\WorkBuddy\resources\app.asar.unpacked\cli\dist\codebuddy-headless.js',
    r'D:\LenovoSoftstore\Install\WorkBuddy\resources\app.asar.unpacked\cli\dist\codebuddy-lite-wb.mjs',
]
NEEDLES = [
    'truncated during injection',
    'ACTION REQUIRED',
    'working_memory_content',
    'has exceeded the size limit',
]


def scan(path):
    if not os.path.isfile(path):
        print('MISSING', path)
        return
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        text = fh.read()
    print('=' * 70)
    print('FILE', path)
    for needle in NEEDLES:
        idx = [m.start() for m in re.finditer(re.escape(needle), text)]
        print('-' * 70)
        print('needle=%r hits=%d' % (needle, len(idx)))
        for i in idx[:3]:
            seg = text[max(0, i - 900):i + 700]
            print('   at %d:' % i)
            print('   ' + seg.replace('\n', ' ')[:1500])


for p in FILES:
    scan(p)

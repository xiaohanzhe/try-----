# -*- coding: utf-8 -*-
"""量速查本 MEMORY.md 的 js_len（= 注入上限判据，见 skill agent-memory-compaction）。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
P = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')

with io.open(P, encoding='utf-8') as fh:
    s = fh.read()

js_len = len(s.strip().encode('utf-16-le')) // 2
print('文件          :', P)
print('len(chars)    :', len(s))
print('len(utf-8 B)  :', len(s.encode('utf-8')))
print('js_len(UTF-16):', js_len, ' / 上限 10000')
print('余量          :', 10000 - js_len)

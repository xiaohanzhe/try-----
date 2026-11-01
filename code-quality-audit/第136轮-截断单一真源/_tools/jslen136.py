# -*- coding: utf-8 -*-
"""算记忆文件的 **JS 字符数**（UTF-16 码元）—— 注入上限按这个算，不按字节。

`check95 A2` 是硬闸：`js_len <= 10000`。`len(bytes)` 是假安全（一个中文 3 字节、2 码元）。
"""
import io
import os
import sys

p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '.workbuddy',
    'memory', 'MEMORY.md')
s = io.open(os.path.abspath(p), 'r', encoding='utf-8', newline='').read()
js = len(s.encode('utf-16-le')) // 2
print('file   %s' % os.path.abspath(p))
print('bytes  %d' % len(s.encode('utf-8')))
print('js_len %d / 10000  余 %d' % (js, 10000 - js))
print('chars  %d' % len(s))

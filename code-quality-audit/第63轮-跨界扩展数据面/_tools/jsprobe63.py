#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""第63轮 · index.js 探针（按正则取上下文，避免裸子串计数误导）。

用法：
  python jsprobe63.py "<regex>" [前后字符数] [最多条数]
"""
import io
import os
import re
import sys

WWW = u'E:\\Download\\_extract61\\outertale\\www'


def main():
    pat = sys.argv[1]
    span = int(sys.argv[2]) if len(sys.argv) > 2 else 220
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    js = [f for f in os.listdir(WWW)
          if f.lower().startswith(u'index-') and f.lower().endswith(u'.js')]
    t = io.open(os.path.join(WWW, js[0]), 'rb').read().decode('utf-8', 'replace')
    rx = re.compile(pat)
    n = 0
    for m in rx.finditer(t):
        n += 1
        if n > limit:
            break
        a = max(0, m.start() - span)
        b = min(len(t), m.end() + span)
        seg = t[a:b].replace(u'\n', u'\\n')
        print(u'--- #%d @%d ---' % (n, m.start()))
        print(seg)
        print()
    print(u'total_matches=%d' % len(rx.findall(t)))


if __name__ == '__main__':
    sys.exit(main())

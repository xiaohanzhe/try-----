#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""第62轮 · 把 7B 人设实测的计时/流式统计汇总成可读文本（只读证据，不联网）。

为什么单独写文件而不是 `python -c`：本项目踩过多次"内联脚本被 shell 拆掉"的坑
（引号/换行被吞），一律落盘成脚本再跑。
"""
import io
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.join(os.path.dirname(HERE), '_evidence')
d = json.load(io.open(os.path.join(EV, 'personas_live62.json'), encoding='utf-8'))
R = d['replies']

zero = [r for r in R if r.get('n_delta') == 0]
tt = [r['ttf'] for r in R if r.get('ttf') is not None]
to = [r['total'] for r in R if r.get('total') is not None]

print(u'生成 %d 次；非空 %d；零分片 %d' % (
    len(R), sum(1 for r in R if r['reply']), len(zero)))
print(u'零分片涉及人设：%s' % u', '.join(sorted({r['id'] for r in zero})))
print()
if tt:
    print(u'可测首字 n=%d 中位=%.2fs 均值=%.2fs 区间=[%.2f, %.2f]'
          % (len(tt), st.median(tt), sum(tt) / len(tt), min(tt), max(tt)))
if to:
    print(u'整句     n=%d 中位=%.2fs 均值=%.2fs 区间=[%.2f, %.2f]'
          % (len(to), st.median(to), sum(to) / len(to), min(to), max(to)))

first, rest, seen = {}, [], set()
for r in R:
    if r['id'] not in seen:
        seen.add(r['id'])
        first[r['id']] = r
    else:
        rest.append(r)
ft = [r['ttf'] for r in first.values() if r.get('ttf') is not None]
rt = [r['ttf'] for r in rest if r.get('ttf') is not None]
print()
if ft:
    print(u'每人首问（换人⇒前缀缓存必失效=冷）n=%d 首字中位=%.2fs'
          % (len(ft), st.median(ft)))
if rt:
    print(u'同一人的后续问（前缀可命中=热）  n=%d 首字中位=%.2fs'
          % (len(rt), st.median(rt)))
print()
print(u'零分片逐条：')
for r in zero:
    print(u'   %-8s %-10s total=%.1fs' % (r['id'], r['probe_tag'],
                                         r['total'] if r['total'] else -1))

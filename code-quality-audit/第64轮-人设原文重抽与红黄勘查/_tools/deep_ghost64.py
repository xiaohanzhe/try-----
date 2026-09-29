# -*- coding: utf-8 -*-
u"""第64轮 · 深挖「幽灵」：settings_ghost / scr_ghosttalk / 幽灵对象 / 逐字空格的中文。

★ 教训复用：`决心` 搜不到不代表没有 —— 本作的台词是「逐 字 空 格」排版，
  ⇒ 关键词必须同时试**无空格**与**逐字加空格**两种形态（否则=判据过窄）。
"""
from __future__ import print_function

import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding=u'utf-8', errors=u'replace')
except Exception:
    pass

SRCDIR = u'E:\\Download\\_extract64\\assets'
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EVID = os.path.join(ROUND, u'_evidence')


def load(n):
    with io.open(os.path.join(SRCDIR, n), 'r', encoding='utf-8') as fh:
        return json.load(fh)


def spaced(s):
    u"""把中文串变成「逐字加空格」形态，用于匹配本作的排版。"""
    return u' '.join(list(s))


def main():
    nm = load(u'r64_names.json')
    names = nm[u'names']
    with io.open(os.path.join(SRCDIR, u'r64_strhits.json'), 'r', encoding='utf-8') as fh:
        pass

    # 直接重扫全部字符串（strhits 只留了命中项，不够）
    # —— 但 r64_names.json 没存 strings 全文；改用 strhits + 资源名。
    # 先看资源名里的 object/script/room 幽灵相关
    print(u'=== 资源名：含 ghost 的对象/脚本/房间/音效/背景 ===')
    for ln in names:
        t, _, rest = ln.partition(u'\t')
        if t == u'code':
            continue
        low = rest.lower()
        if u'ghost' in low:
            print(u'  %-12s %s' % (t, rest))
    print()

    print(u'=== Data.Strings：含 settings_ghost / scr_ghosttalk 的全量上下文 ===')
    sh = load(u'r64_strhits.json')[u'strhits']
    # strhits 只保留了「命中关键词」的项；settings_ghost* 命中的是 ghost 关键词
    for line in sh:
        if u'settings_ghost' in line or u'scr_ghosttalk' in line or u'ghosttimer' in line:
            print(u'  #%s' % line.replace(u'\n', u'\\n')[:240])
    print()

    print(u'=== strhits 中所有 ghost 命中（含下标，供回查）===')
    for line in sh:
        p = line.split(u'\t', 2)
        if len(p) >= 3 and p[1] == u'ghost':
            print(u'  #%-8s %s' % (p[0], p[2].replace(u'\n', u'\\n')[:160]))
    print()

    # ---- 逐字空格形态检查：直接在 strhits 里找「决 心」/「幽 灵」
    print(u'=== 逐字空格形态命中（判据过窄的补丁）===')
    for kw in [u'决 心', u'幽 灵', u'灵 魂', u'd e t e r m i n']:
        hits = [l for l in sh if kw in l]
        print(u'  「%s」 -> %d 条' % (kw, len(hits)))
        for h in hits[:6]:
            p = h.split(u'\t', 2)
            print(u'        #%s %s' % (p[0], (p[2] if len(p) > 2 else u'').replace(u'\n', u'\\n')[:140]))
    print()

    # ---- 幽灵相关对象（sprite 含 ghost 的 object）
    print(u'=== object 里 sprite 或名字含 ghost ===')
    for ln in names:
        t, _, rest = ln.partition(u'\t')
        if t == u'object' and u'ghost' in rest.lower():
            print(u'  %s' % rest)
    print()
    return 0


if __name__ == u'__main__':
    raise SystemExit(main())

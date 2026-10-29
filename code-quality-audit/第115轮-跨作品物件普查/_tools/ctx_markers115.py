# -*- coding: utf-8 -*-
u"""从 dump_scrtext.txt 里抽出「标记常量出现处 ±N 条指令」的上下文。

为什么要有这一步：`SCR_TEXT` 有 26,667 条指令（其中绝大部分是字符宽度表），
`SCR_TEXTTYPE` 3,648 条。整段读不可能，但**规则一定落在 push 标记常量的那十几处**，
把它们连同前后分支摊开就够判断了。

用法：python ctx_markers115.py [--sec SCR_TEXTTYPE] [--rad 18]
"""
import argparse
import io
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
RAW = os.path.join(os.path.dirname(HERE), '_evidence', 'raw', 'ut', 'dump_scrtext.txt')

MARKERS = (u"'/'", u"'%'", u"'%%'", u"'%%%'", u"'&'", u"'^'", u"'^1'", u"'^2'")


def string_of(val):
    """从 dump 的 `ValueString = "内容"@42` 里取内容。

    ★ 实测：`ValueString` 不是 `UndertaleString` 本身，而是 **按 id 的引用包装**，
      它的 `ToString()` 是 `"内容"@<id>`。第一版直接按 `'…'` 比 ⇒ 一处都命不中
      （静默空结果，正是"探针自己没证明任何东西"的典型）。
    """
    m = re.match(r'^"(.*)"@\d+$', val)
    if m:
        return m.group(1)
    if len(val) >= 2 and val[0] == u"'" and val[-1] == u"'":
        return val[1:-1]
    return None



def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--sec', default=None, help='只看这一段（子串匹配段名）')
    ap.add_argument('--rad', type=int, default=18, help='上下文半径（指令条数）')
    ap.add_argument('--range', default=None,
                    help='直接摊开一段指令：如 1900:2700（与 --rad 互斥，命中段才生效）')
    a = ap.parse_args(argv)

    with io.open(RAW, encoding='utf-8', errors='replace', newline='') as f:
        lines = f.read().splitlines()

    # 切段：`========== <name>  ins=N ==========`
    secs = []
    cur = None
    for ln in lines:
        m = re.match(r'^========== (.+?)  ins=(\d+) ==========$', ln)
        if m:
            cur = {'name': m.group(1), 'n': int(m.group(2)), 'body': []}
            secs.append(cur)
            continue
        if cur is not None:
            cur['body'].append(ln)

    if not secs:
        print('[FAIL] 一段都没切出来 —— 文件不是本脚本预期的形状')
        return 2
    print('段落：%d' % len(secs))
    for s in secs:
        print('   %-28s ins=%d' % (s['name'], s['n']))

    hits = 0
    want_lo = want_hi = None
    if a.range:
        try:
            want_lo, want_hi = [int(x) for x in a.range.split(':')]
        except ValueError:
            print('[FAIL] --range 要写成 a:b')
            return 2
    for s in secs:
        if a.sec and a.sec not in s['name']:
            continue
        body = s['body']
        if want_lo is not None:
            cur_idx = None
            printing = False
            hits = 1
            print('')
            print('#### %s  ins[%d:%d]' % (s['name'], want_lo, want_hi))
            for ln in body:
                m = re.match(r'^\s*(\d+): (\w+)$', ln)
                if m:
                    cur_idx = int(m.group(1))
                    printing = want_lo <= cur_idx <= want_hi
                if printing:
                    print(ln)
            continue
        # 指令行形如 `  123: Push`
        idx_of = {}
        for i, ln in enumerate(body):
            m = re.match(r'^\s*(\d+): (\w+)$', ln)
            if m:
                idx_of[i] = int(m.group(1))
        for i, ln in enumerate(body):
            if 'ValueString = ' not in ln:
                continue
            val = ln.split('ValueString = ', 1)[1].strip()
            content = string_of(val)
            if not content or any(c not in u'/%&^' for c in content):
                continue
            hits += 1
            # 找到这条指令的行号，回溯到它的 `N: Kind` 行
            j = i
            while j >= 0 and j not in idx_of:
                j -= 1
            lo = max(0, j - a.rad)
            hi = min(len(body), i + a.rad)
            print('')
            print('#### %s  @ins[%s]  %s' % (s['name'],
                                             idx_of.get(j, '?'), val))
            for k in range(lo, hi):
                print(body[k])

    if not hits:
        print('')
        print('[FAIL] 一处标记都没命中 —— 半径/段名选错了，或 dump 变了')
        return 1
    print('')
    print('[PASS] 命中 %d 处' % hits)
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))

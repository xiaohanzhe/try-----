# -*- coding: utf-8 -*-
"""第199轮 · 把 76 份人设的【语言风格】逐份打出来（只读）

目的：判断"口癖补齐"到底缺什么 —— 是缺**具体口癖设定**，还是缺**场合规则**。
输出到 stdout，按文件名排序。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'ralsei_pet'))
PDIR = os.path.join(ROOT, 'assets', 'npc', 'persona')
SEC_RE = re.compile(u'^【[^】]+】')


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def get_sec(t, kw):
    cur = None
    buf = []
    for ln in t.splitlines():
        s = ln.strip()
        if SEC_RE.match(s):
            if cur is not None:
                break
            if kw in s:
                cur = s
                continue
        elif cur is not None:
            buf.append(ln)
    return cur, u'\n'.join(buf).strip()


def main():
    want = sys.argv[1:] or None
    names = sorted(n for n in os.listdir(PDIR) if n.endswith('.txt'))
    if want:
        names = [n for n in names if any(w in n for w in want)]
    for n in names:
        t = rd(os.path.join(PDIR, n))
        h, body = get_sec(t, u'语言风格')
        print('=' * 70)
        print('%s   [%s]  %d B' % (n, h, len(body.encode('utf-8'))))
        print(body)


if __name__ == '__main__':
    main()

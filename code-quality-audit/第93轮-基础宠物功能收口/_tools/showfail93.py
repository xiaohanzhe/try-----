# -*- coding: utf-8 -*-
u"""把 `regress/_out/<suite>.diff.txt` 里 **now 侧** 的 `[FAIL]` 行全部打出来。

为什么单独写：`git diff` 看不到（`_out/` 被 gitignore），而 `run_all --show-diff`
会**重跑套件**（慢且会改 `_out`）。这里只读已生成的 diff 文件，做只读归因。

用法： C:\\Python311\\python.exe showfail93.py [suite ...]   （不带参数 = 所有）
"""
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
OUT = os.path.join(HERE, '..', '..', 'regress', '_out')


def main(names):
    for name in names:
        p = os.path.join(OUT, name + '.diff.txt')
        if not os.path.exists(p):
            print('%-22s [SKIP]' % name)
            continue
        fails = []
        plus_total = minus_total = 0
        with io.open(p, 'r', encoding='utf-8', errors='replace', newline='') as fh:
            for ln in fh.read().replace('\r\n', '\n').split('\n'):
                if ln.startswith('+') and not ln.startswith('+++'):
                    plus_total += 1
                    if '[FAIL]' in ln:
                        fails.append(ln[1:])
                elif ln.startswith('-') and not ln.startswith('---'):
                    minus_total += 1
        print('%-22s now 侧新增 %d 行 / 移除 %d 行 ；其中 FAIL %d 条'
              % (name, plus_total, minus_total, len(fails)))
        for f in fails[:14]:
            print('      ' + f.strip()[:190])
        print()


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        args = sorted(f[:-9] for f in os.listdir(OUT) if f.endswith('.diff.txt'))
    main(args)

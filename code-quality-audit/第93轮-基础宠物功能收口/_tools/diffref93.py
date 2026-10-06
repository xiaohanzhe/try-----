# -*- coding: utf-8 -*-
u"""ref89（`_evidence/ref89/`）与**当前工作区**的定向 diff —— 只看变更 hunk。

为什么不用 `git diff`：当前工作区对 `main.py` / `scene_canvas.py` 有**第93轮未提交
改动**，`git diff` 会把它们混在一起。这里直接用**文件字节**比，得到"89 轮参考版
↔ 现在磁盘上"的差异，正是要恢复/避开的那部分。

用法： C:\\Python311\\python.exe diffref93.py [子串 ...] [--full]
不带参数 = 列全部 13 个文件的变更块数概览。
"""
import difflib
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
REF = os.path.join(HERE, '..', '_evidence', 'ref89')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        # ★ 归一化 EOL：tag 里的文件可能是 CRLF，工作区是 LF（记忆 §65.2：
        #   `autocrlf=true` 而工作区存在两代 EOL 风格）。不归一化 ⇒ 每一行都"不同"，
        #   得到 hunks=1 / 全量差异的**假象**（实测 13 个文件里 12 个被 EOL 淹没）。
        return fh.read().replace('\r\n', '\n').replace('\r', '\n').split('\n')


def pairs(sub, full):
    for f in sorted(os.listdir(REF)):
        path = f.replace('__', '/')
        if sub and sub not in path:
            continue
        a = read(os.path.join(REF, f))
        cur = os.path.join(ROOT, path)
        b = read(cur) if os.path.exists(cur) else []
        d = list(difflib.unified_diff(a, b, fromfile='ref89:' + os.path.basename(path),
                                      tofile='now:' + os.path.basename(path),
                                      n=3, lineterm=''))
        hunks = sum(1 for ln in d if ln.startswith('@@'))
        plus = sum(1 for ln in d if ln.startswith('+') and not ln.startswith('+++'))
        minus = sum(1 for ln in d if ln.startswith('-') and not ln.startswith('---'))
        print('%-46s hunks=%-3d  +%-5d -%-5d' % (path, hunks, plus, minus))
        if full and d:
            for ln in d:
                print('    ' + ln)
            print()


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--full']
    pairs(' '.join(args), '--full' in sys.argv)

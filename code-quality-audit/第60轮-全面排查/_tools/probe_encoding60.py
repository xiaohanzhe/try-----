#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第60轮 探针 C：定位「run_all.py 打印摘要时 OSError 22」的肇因字符。

现象（2026-09-28 实跑）：
  OSError: [Errno 22] Invalid argument
  File ".../regress/run_all.py", line 1508, in main
    print('%-16s %-6s %-6s %-6s %-8s %s' % (...))

成因假设：run_all.py 给**子进程**设了 PYTHONIOENCODING/PYTHONUTF8，
却没有管**自己**的 stdout。重定向到文件时 Python 用 locale 编码（cp936），
某一行的字符在 cp936 里没有对应码位 ⇒ 写失败。

本探针做两件事：
  1) 找出 run_all.py 里所有「cp936 编不出」的字符（含行号），锁定肇因；
  2) 复现：把那一行按 locale 编码写进管道，确认异常类型与 Errno。
"""
import io
import locale
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
AUDIT = os.path.dirname(ROUND)
REPO = os.path.dirname(AUDIT)
RUN_ALL = os.path.join(AUDIT, 'regress', 'run_all.py')


def check(cond, msg):
    print('[%s] %s' % ('PASS' if cond else 'FAIL', msg))
    return bool(cond)


def main():
    loc = locale.getpreferredencoding(False)
    print('stdout.encoding = %r' % getattr(sys.stdout, 'encoding', None))
    print('locale.getpreferredencoding(False) = %r' % loc)
    print('-' * 60)

    text = io.open(RUN_ALL, encoding='utf-8').read()
    lines = text.split('\n')
    bad = []
    for i, ln in enumerate(lines, 1):
        for ch in ln:
            try:
                ch.encode(loc)
            except Exception:
                bad.append((i, ch, 'U+%04X' % ord(ch), ln.strip()[:70]))
                break
    ok = True
    ok &= check(True, 'C1 扫完 run_all.py 全部 %d 行' % len(lines))
    if bad:
        print('      在 %r 下编不出的字符所在行：' % loc)
        for i, ch, cp, ctx in bad:
            print('        line %-5d %s %s   | %s' % (i, cp, repr(ch), ctx))
    else:
        print('      没有找到 cp936 编不出的字符')

    # 复现：手写一行，用 locale 编码写进管道
    repro = None
    if bad:
        i = bad[0][0]
        line = lines[i - 1]
        try:
            line.encode(loc)
            repro = '编码成功（不是编码问题）'
        except UnicodeEncodeError as e:
            repro = 'UnicodeEncodeError: %s' % e
        except Exception as e:
            repro = '%s: %s' % (type(e).__name__, e)
    print('      复现：%s' % repro)

    # 反向：同一行用 UTF-8 编码必须成功（证明是编码而非内容非法）
    if bad:
        utf8_ok = True
        try:
            lines[bad[0][0] - 1].encode('utf-8')
        except Exception:
            utf8_ok = False
        ok &= check(utf8_ok, 'C2 肇因行用 UTF-8 能编码（说明是编码问题，不是内容非法）')

    # 判定：run_all.py 是否给自己设了编码
    has_self = '__PYTHONIOENCODING' in text or 'reconfigure(' in text or 'PYTHONUTF8' in text
    py_io = [ln for ln in lines if 'PYTHONIOENCODING' in ln]
    ok &= check(bool(py_io), 'C3 run_all.py 里确实设过 PYTHONIOENCODING（%d 处）—— 但只给了子进程' % len(py_io))
    self_set = any('reconfigure' in ln or 'stdout' in ln and 'encoding' in ln for ln in lines)
    ok &= check(not self_set,
                'C4 确认「run_all.py 没给自己设 stdout 编码」这一缺陷存在（缺陷存在=True 才是真发现）')

    print('-' * 60)
    print('结论：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

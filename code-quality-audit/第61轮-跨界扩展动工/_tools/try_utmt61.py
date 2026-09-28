# -*- coding: utf-8 -*-
u"""第61轮 · 探针：UTMT CLI 到底能不能在本环境跑。

判据：
- 能拿到 stdout/stderr（不论退出码） => 可跑 => 'RUNNABLE'
- 进程被外部杀掉 / 无任何输出       => 'KILLED'
"""
from __future__ import print_function

import os
import subprocess
import sys

EXE = u'E:\\Download\\UTMT_CLI_v0.9.2.0\\UndertaleModCli.exe'


def run(args):
    print(u'\n>>> %s %s' % (os.path.basename(EXE), u' '.join(args)))
    try:
        p = subprocess.run([EXE] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=90)
        out = p.stdout or b''
        print(u'    returncode = %s' % p.returncode)
        print(u'    输出 %d 字节：' % len(out))
        txt = out.decode(u'utf-8', u'replace')
        for line in txt.splitlines()[:40]:
            print(u'      | %s' % line)
        return u'RUNNABLE' if out else u'RUNNABLE(无输出)'
    except subprocess.TimeoutExpired:
        print(u'    !! 超时')
        return u'TIMEOUT'
    except Exception as e:  # noqa: BLE001
        print(u'    !! %s: %s' % (type(e).__name__, e))
        return u'ERROR'


def main():
    print(u'=' * 78)
    print(u'UTMT CLI 可运行性探针')
    print(u'=' * 78)
    print(u'exists = %s' % os.path.exists(EXE))
    if not os.path.exists(EXE):
        return 2
    r1 = run([u'--help'])
    r2 = run([])
    print(u'\n结论: --help=%s  (noargs)=%s' % (r1, r2))
    return 0


if __name__ == u'__main__':
    raise SystemExit(main())

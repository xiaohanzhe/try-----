# -*- coding: utf-8 -*-
u"""第61轮 · 探针2：给 UTMT CLI 造一个真控制台（多策略一次试完）。

已知：无参数时崩在 System.ConsolePal.GetCursorPosition()（.NET 10 在无控制台环境）。
本脚本依次尝试 4 种策略，谁先拿到输出谁就是答案。
"""
from __future__ import print_function

import ctypes
import io
import os
import subprocess
import time

EXE = u'E:\\Download\\UTMT_CLI_v0.9.2.0\\UndertaleModCli.exe'
TMP = u'E:\\Download\\_tmp'
ARGS = [u'--help']


def read_head(p, n=900):
    try:
        with io.open(p, u'rb') as fh:
            return fh.read(n).decode(u'utf-8', u'replace')
    except OSError as e:
        return u'<读不到: %s>' % e


def attempt(tag, cmd, logname, flags=0):
    log = os.path.join(TMP, logname)
    if os.path.exists(log):
        try:
            os.remove(log)
        except OSError:
            pass
    print(u'\n>>> [%s] %s' % (tag, u' '.join(cmd)))
    t0 = time.time()
    try:
        with io.open(log, u'wb') as fh:
            p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, creationflags=flags, timeout=75)
        dt = time.time() - t0
        body = read_head(log)
        print(u'    rc=%s  %.1fs  log=%d bytes' % (p.returncode, dt, os.path.getsize(log)))
        if body:
            for line in body.splitlines()[:16]:
                print(u'      | %s' % line)
        return (p.returncode == 0 or bool(body.strip())), p.returncode, body
    except subprocess.TimeoutExpired:
        print(u'    !! 超时 %.1fs' % (time.time() - t0))
        return (False, u'TIMEOUT', u'')
    except Exception as e:  # noqa: BLE001
        print(u'    !! %s: %s' % (type(e).__name__, e))
        return (False, type(e).__name__, u'')


def main():
    if not os.path.isdir(TMP):
        os.makedirs(TMP)
    print(u'=' * 78)
    print(u'UTMT CLI 控制台策略探针    exe exists=%s' % os.path.exists(EXE))
    print(u'=' * 78)

    res = {}
    # 策略1：普通（已知崩溃，作基线）
    res['S1_plain'] = attempt(u'S1 普通管道', [EXE] + ARGS, u'utmt_s1.txt')
    # 策略2：CREATE_NEW_CONSOLE
    res['S2_newconsole'] = attempt(u'S2 新建控制台', [EXE] + ARGS, u'utmt_s2.txt',
                                   flags=0x00000010)
    # 策略3：CREATE_NO_WINDOW
    res['S3_nowindow'] = attempt(u'S3 无窗口', [EXE] + ARGS, u'utmt_s3.txt',
                                 flags=0x08000000)
    # 策略4：经 cmd /c
    res['S4_cmd'] = attempt(u'S4 经 cmd /c', [u'cmd', u'/c', EXE] + ARGS, u'utmt_s4.txt')
    # 策略5：进程内 AllocConsole 后再起
    print(u'\n>>> [S5] kernel32.AllocConsole() 之后再起')
    try:
        k = ctypes.windll.kernel32
        ok = k.AllocConsole()
        print(u'    AllocConsole() -> %s (err=%s)' % (ok, k.GetLastError()))
        res['S5_alloc'] = attempt(u'S5 AllocConsole 后', [EXE] + ARGS, u'utmt_s5.txt')
    except Exception as e:  # noqa: BLE001
        print(u'    !! %s: %s' % (type(e).__name__, e))
        res['S5_alloc'] = (False, u'EXC', u'')

    print(u'\n' + u'=' * 78)
    print(u'结论：')
    win = [k for k, v in res.items() if v[0]]
    for k, v in res.items():
        print(u'  %-16s ok=%-5s rc=%s' % (k, v[0], v[1]))
    print(u'\n可用策略: %s' % (win or u'（全部失败 ⇒ 必须用户侧运行）'))
    return 0 if win else 1


if __name__ == u'__main__':
    raise SystemExit(main())

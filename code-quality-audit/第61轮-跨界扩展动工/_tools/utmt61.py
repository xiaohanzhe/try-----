# -*- coding: utf-8 -*-
u"""第61轮 · UTMT CLI 驱动（自动化封装）。

★★ 铁律（本轮实测）：UTMT CLI 的 stdout **必须是文件**，绝不能是 PIPE
   —— .NET 10 的 ConsolePal.GetCursorPosition() 在管道下会崩/挂。
   本模块一律 stdout/stderr 重定向到文件，再读回来打印。

用法：
  python utmt61.py info   <datafile>
  python utmt61.py dump   <datafile> <outdir> [--sprites] [--code] ...
  python utmt61.py script <datafile> <script.csx>
"""
from __future__ import print_function

import io
import os
import subprocess
import sys
import time

EXE = u'E:\\Download\\UTMT_CLI_v0.9.2.0\\UndertaleModCli.exe'
LOGDIR = u'E:\\Download\\_tmp\\utmt61_logs'


def ensure_dir(d):
    if os.path.isdir(d):
        return True
    for _ in range(8):
        try:
            os.makedirs(d)
        except OSError:
            pass
        if os.path.isdir(d):
            return True
        time.sleep(0.35)
    return os.path.isdir(d)


def run_utmt(args, tag, timeout=900):
    u"""跑 UTMT CLI；stdout/stderr 落文件。返回 (rc, 输出全文)。"""
    if not ensure_dir(LOGDIR):
        return (-1, u'<无法创建日志目录>')
    log = os.path.join(LOGDIR, u'%s.log' % tag)
    cmd = [EXE] + list(args)
    print(u'>>> %s' % u' '.join(cmd))
    t0 = time.time()
    try:
        with io.open(log, u'wb') as fh:
            p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired:
        return (-2, u'<超时 %ds>' % timeout)
    dt = time.time() - t0
    try:
        with io.open(log, u'rb') as fh:
            txt = fh.read().decode(u'utf-8', u'replace')
    except OSError as e:
        txt = u'<读日志失败: %s>' % e
    print(u'    rc=%s  %.1fs  输出 %d 字节  (log=%s)' % (p.returncode, dt, len(txt), log))
    return (p.returncode, txt)


def show(txt, limit=60):
    lines = txt.splitlines()
    for ln in lines[:limit]:
        print(u'    | %s' % ln)
    if len(lines) > limit:
        print(u'    | ...(共 %d 行)' % len(lines))


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode = argv[1]
    data = argv[2]
    if not os.path.exists(data):
        print(u'!! datafile 不存在: %s' % data)
        return 2

    if mode == u'info':
        rc, txt = run_utmt([u'info', data], u'info_%s' % os.path.basename(data)[:24])
        show(txt)
        return 0

    if mode == u'dump':
        if len(argv) < 4:
            print(u'需要输出目录'); return 2
        outdir = argv[3]
        ensure_dir(outdir)
        opts = argv[4:]
        full = [u'dump', data] + opts + [u'-o', outdir]
        rc, txt = run_utmt(full, u'dump_%s' % os.path.basename(data)[:24])
        show(txt, 80)
        return 0

    if mode == u'script':
        if len(argv) < 4:
            print(u'需要 .csx 脚本'); return 2
        script = argv[3]
        rc, txt = run_utmt([u'load', data, u'-s', script], u'script_%s' % os.path.basename(script)[:24])
        show(txt, 120)
        return 0

    print(u'未知模式: %s' % mode)
    return 2


if __name__ == u'__main__':
    raise SystemExit(main(sys.argv))

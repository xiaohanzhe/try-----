# -*- coding: utf-8 -*-
u"""第65轮 · 跑 dump_uty65.csx（UTMT CLI 驱动）。

★★ 铁律：UTMT CLI 的 stdout **必须是文件**（.NET ConsolePal.GetCursorPosition() 在管道下会崩/挂）
   ⇒ 本脚本一律 stdout/stderr 重定向到日志文件，再读回来打印。

用法:
  python run_dump65.py [<datafile>] [<outdir>]

缺省 datafile = E:\Download\_extract64\assets\game.droid   （红与黄.apk 解出的 game.droid）
缺省 outdir   = E:\Download\_extract64\assets\r65
"""
from __future__ import print_function

import io
import os
import subprocess
import sys
import tempfile
import time

EXE = u'E:\\Download\\UTMT_CLI_v0.9.2.0\\UndertaleModCli.exe'
CWD = u'E:\\Download\\UTMT_CLI_v0.9.2.0'
HERE = os.path.dirname(os.path.abspath(__file__))
CSX = os.path.join(HERE, u'dump_uty65.csx')

DEF_DATA = u'E:\\Download\\_extract64\\assets\\game.droid'
DEF_OUT = u'E:\\Download\\_extract64\\assets\\r65'

LOGDIR_CANDIDATES = [
    u'E:\\Download\\_tmp65\\utmt65_logs',
    os.path.join(tempfile.gettempdir(), u'utmt65_logs'),
]


def writable(d):
    try:
        if not os.path.isdir(d):
            os.makedirs(d)
    except OSError:
        pass
    if not os.path.isdir(d):
        return False
    probe = os.path.join(d, u'_w.tmp')
    for _ in range(6):
        try:
            with io.open(probe, u'wb') as fh:
                fh.write(b'ok')
            try:
                os.remove(probe)
            except OSError:
                pass
            return True
        except OSError:
            time.sleep(0.35)
    return False


def pick_logdir():
    for d in LOGDIR_CANDIDATES:
        if writable(d):
            return d
    return None


def main(argv):
    # 支持 --csx <path>（第65轮要跑两份 csx：黄魂版 / Undertale 版）
    csx = CSX
    if u'--csx' in argv:
        i = argv.index(u'--csx')
        csx = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    data = argv[1] if len(argv) > 1 else DEF_DATA
    outdir = argv[2] if len(argv) > 2 else DEF_OUT

    print(u'datafile = %s' % data)
    print(u'  存在 = %s  大小 = %s' % (os.path.isfile(data),
                                      os.path.getsize(data) if os.path.isfile(data) else '-'))
    print(u'outdir   = %s' % outdir)
    print(u'csx      = %s' % csx)
    if not os.path.isfile(data):
        print(u'!! datafile 不存在，停手')
        return 2
    if not os.path.isfile(csx):
        print(u'!! csx 不存在，停手')
        return 2

    ld = pick_logdir()
    if not ld:
        print(u'!! 无可用日志目录，停手')
        return 2
    # 日志名跟 outdir 走，避免两次运行互相覆盖
    tag = os.path.basename(outdir.rstrip(u'\\/')) or u'out'
    log = os.path.join(ld, u'dump65_%s.log' % tag)
    print(u'log      = %s' % log)

    env = dict(os.environ)
    env[u'R65_OUT'] = outdir
    try:
        if not os.path.isdir(outdir):
            os.makedirs(outdir)
    except OSError as e:
        print(u'    (建 outdir 报错，继续: %s)' % e)

    cmd = [EXE, u'load', data, u'-s', csx]
    print(u'>>> %s' % u' '.join(cmd))
    t0 = time.time()
    with io.open(log, u'wb') as fh:
        p = subprocess.run(cmd, cwd=CWD, env=env,
                           stdin=subprocess.DEVNULL,
                           stdout=fh, stderr=subprocess.STDOUT,
                           timeout=3600)
    dt = time.time() - t0
    txt = io.open(log, u'rb').read().decode(u'utf-8', u'replace')
    print(u'    rc=%s  %.1fs  日志 %d 字节' % (p.returncode, dt, len(txt)))
    print(u'---- 日志尾巴 ----')
    for ln in txt.strip().splitlines()[-25:]:
        print(u'  | %s' % ln)

    produced = []
    if os.path.isdir(outdir):
        for n in sorted(os.listdir(outdir)):
            f = os.path.join(outdir, n)
            produced.append((n, os.path.getsize(f) if os.path.isfile(f) else u'<dir>'))
    print(u'---- 产物 ----')
    for n, sz in produced:
        print(u'  %-24s %s' % (n, sz))
    return 0


if __name__ == u'__main__':
    raise SystemExit(main(sys.argv))

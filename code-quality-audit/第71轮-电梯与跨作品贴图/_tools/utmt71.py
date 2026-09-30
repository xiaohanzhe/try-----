# -*- coding: utf-8 -*-
"""第71轮 · UTMT CLI 定向导出驱动。

★★ 铁律 1（第61轮实测）：UTMT CLI 的 stdout **必须是文件**，绝不能是 PIPE
   —— .NET 10 的 ConsolePal.GetCursorPosition() 在管道下会崩/挂。

★★ 铁律 2（第71轮实测，新）：**cwd 不能含非 ASCII 字符**。
   cwd = `...\项目文件夹\try - 副本` 时，CLI 在 `System.CommandLine` 的参数转换里
   调 `Path.GetFullPath` 直接 `ExecutionEngineException: In page error`（rc=0xC0000142 族，
   1 秒即崩，零有用输出）。⇒ 本驱动**强制把 cwd 切到 ASCII 目录**，并把 .csx 也复制到
   ASCII 路径再跑（脚本路径含中文同样会踩到）。
   这是"路径全是中文"的仓库里跑 .NET 工具必须付的过路费。
"""
from __future__ import print_function

import io
import os
import shutil
import subprocess
import sys
import time

#: ★ 不要在 import 期改写 sys.stdout —— TextIOWrapper 被 GC 时会 close 掉底层 buffer，
#: 把调用方的 print 一起搞死（本轮实测：`ValueError: I/O operation on closed file`）。
#: 只在本模块作为主程序跑时才包一层。
EXE = r'E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe'
#: ASCII 工作目录候选（★ 必须纯 ASCII）
ASCII_CWD = [r'E:\Download\_tmp', r'E:\Download', os.environ.get('TEMP', '')]
CSX_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dump_spr71.csx')


def _ascii_cwd():
    for d in ASCII_CWD:
        if not d:
            continue
        try:
            os.makedirs(d, exist_ok=True)
            nonascii = [c for c in d if ord(c) > 127]
            if nonascii:
                continue
            probe = os.path.join(d, '_w71.tmp')
            with io.open(probe, 'wb') as fh:
                fh.write(b'ok')
            os.remove(probe)
            return d
        except OSError:
            continue
    raise RuntimeError('找不到可写的纯 ASCII 工作目录')


def run(names, data, outdir, tag, timeout=3600):
    """定向导出 names 到 outdir。返回 (rc, 输出文本)。"""
    cwd = _ascii_cwd()
    os.makedirs(outdir, exist_ok=True)
    csx = os.path.join(cwd, 'dump_spr71_%s.csx' % tag)
    shutil.copy2(CSX_SRC, csx)
    lst = os.path.join(cwd, 'r71_list_%s.txt' % tag)
    with io.open(lst, 'w', encoding='utf-8') as fh:
        fh.write(u'\n'.join(names) + u'\n')
    log = os.path.join(cwd, 'r71_%s.log' % tag)
    env = dict(os.environ)
    env['R71_LIST'] = lst
    env['R71_OUT'] = outdir
    cmd = [EXE, 'load', data, '-s', csx]
    print(u'>>> %s' % ' '.join(cmd))
    print(u'    cwd=%s   names=%d' % (cwd, len(names)))
    t0 = time.time()
    with io.open(log, 'wb') as fh:
        p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                           stdin=subprocess.DEVNULL, env=env, cwd=cwd, timeout=timeout)
    dt = time.time() - t0
    txt = io.open(log, 'rb').read().decode(u'utf-8', u'replace')
    print(u'    rc=%s  %.1fs  log=%d B' % (p.returncode, dt, len(txt)))
    tail = u'\n'.join(txt.splitlines()[-6:])
    print(u'    | %s' % tail.replace(u'\n', u'\n    | '))
    return p.returncode, txt


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print(__doc__)

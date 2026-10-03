# -*- coding: utf-8 -*-
u"""第84轮 · UTMT CLI 驱动（驱动 dump_dr84.csx 反编译 Deltarune ch1）。

★★ 铁律：UTMT CLI 的 stdout **必须是文件**，不能是 PIPE
   （.NET ConsolePal.GetCursorPosition() 在管道下崩/挂）。
"""
from __future__ import print_function
import io, os, subprocess, sys, tempfile, time

EXE = u'E:\\Download\\UTMT_CLI_v0.9.2.0\\UndertaleModCli.exe'
DATA = (u'C:\\Users\\23002\\Desktop\\项目文件夹\\niko的秘密\\DELTARUNE_183049'
        u'\\DELTARUNE\\chapter1_windows\\data.win')
HERE = os.path.dirname(os.path.abspath(__file__))
LOGDIR_CANDIDATES = [
    u'E:\\Download\\_tmp84c\\logs',
    u'E:\\Download\\_tmp\\utmt84_logs',
    os.path.join(tempfile.gettempdir(), u'utmt84_logs'),
]
DATA_DIR_CANDIDATES = [
    u'E:\\Download\\_tmp84c\\_data',
    os.path.join(tempfile.gettempdir(), u'dr84_data'),
]


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
    return False


def writable(d):
    if not ensure_dir(d):
        return False
    probe = os.path.join(d, u'_w.tmp')
    for _ in range(6):
        try:
            with io.open(probe, u'wb') as fh:
                fh.write(b'ok')
            os.remove(probe)
            return True
        except OSError:
            time.sleep(0.35)
    return False


def pick(cands):
    for d in cands:
        if writable(d):
            return d
    return None


def main():
    logdir = pick(LOGDIR_CANDIDATES)
    ddir = pick(DATA_DIR_CANDIDATES)
    print(u'[logdir] %s' % logdir)
    print(u'[datadir] %s' % ddir)
    if not logdir or not ddir:
        print(u'!! 无可写目录'); return 2
    if not os.path.exists(EXE):
        print(u'!! UTMT 不存在: %s' % EXE); return 2
    if not os.path.exists(DATA):
        print(u'!! data.win 不存在: %s' % DATA); return 2

    csx = os.path.join(HERE, u'dump_dr84.csx')
    # ★ 脚本要落在 data.win 同目录（csx 里用 Path.GetDirectoryName(FilePath)）
    workcsx = os.path.join(ddir, u'dump_dr84.csx')
    with io.open(csx, u'r', encoding=u'utf-8') as fh:
        body = fh.read()
    # ★★ 把 __OUTDIR__ 占位符替换成**绝对产物目录**（CLI 下 FilePath 不可靠）
    body = body.replace(u'__OUTDIR__', ddir.replace(u'\\', u'/'))
    with io.open(workcsx, u'w', encoding=u'utf-8', newline=u'\n') as fh:
        fh.write(body)

    # ★★ 正确形式（R5 验证过）：`load <datafile> -s <script.csx>`
    # ❗ 不要写成 `--output <dir> load <data>` —— 实测卡死 12 分钟、日志 0 字节。
    log = os.path.join(logdir, u'utmt84.txt')
    cmd = [EXE, u'load', DATA, u'-s', workcsx]
    print(u'[run] %s' % u' '.join(cmd))
    t0 = time.time()
    with io.open(log, u'wb') as fh:
        p = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL)
        rc = p.wait()
    print(u'[rc] %s  %.1fs' % (rc, time.time() - t0))
    try:
        print(io.open(log, u'r', encoding=u'utf-8', errors=u'replace').read()[:4000])
    except Exception as e:
        print(u'log read fail %s' % e)

    for f in sorted(os.listdir(ddir)):
        print(u'  %12d %s' % (os.path.getsize(os.path.join(ddir, f)), f))
    return rc


if __name__ == u'__main__':
    sys.exit(main())

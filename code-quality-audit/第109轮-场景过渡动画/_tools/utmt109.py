# -*- coding: utf-8 -*-
u"""第109轮 · UTMT CLI 驱动（反编译 Deltarune ch1 的 fade 过渡实现）。

★★ 铁律（第84/85轮实测，勿改）：
   ① UTMT CLI 的 stdout **必须是文件**，不能是 PIPE。
   ② 调用形式 = `UndertaleModCli.exe load <datafile> -s <script.csx>`。
   ③ `.csx` 里 `FilePath` 在 CLI 下不可靠 ⇒ 用 `__OUTDIR__` 占位符由本脚本替换。
   ④ E 盘写通道会间歇失效 ⇒ 产物目录换新名字 / 回退 TEMP。
"""
from __future__ import print_function
import io, os, subprocess, sys, tempfile, time

EXE = u'E:\\Download\\UTMT_CLI_v0.9.2.0\\UndertaleModCli.exe'
DATA = (u'C:\\Users\\23002\\Desktop\\项目文件夹\\niko的秘密\\DELTARUNE_183049'
        u'\\DELTARUNE\\chapter1_windows\\data.win')
HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.abspath(os.path.join(HERE, u'..', u'_evidence'))
LOGDIR_CANDIDATES = [
    u'E:\\Download\\_tmp109\\logs',
    os.path.join(tempfile.gettempdir(), u'utmt109_logs'),
]
DATA_DIR_CANDIDATES = [
    u'E:\\Download\\_tmp109\\_data',
    os.path.join(tempfile.gettempdir(), u'dr109_data'),
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
        print(u'!! 无可写目录')
        return 2
    for lbl, p in ((u'UTMT', EXE), (u'data.win', DATA)):
        if not os.path.exists(p):
            print(u'!! %s 不存在: %s' % (lbl, p))
            return 2

    csx = os.path.join(HERE, u'dump_fade109.csx')
    workcsx = os.path.join(ddir, u'dump_fade109.csx')
    with io.open(csx, u'r', encoding=u'utf-8') as fh:
        body = fh.read()
    body = body.replace(u'__OUTDIR__', ddir.replace(u'\\', u'/'))
    with io.open(workcsx, u'w', encoding=u'utf-8', newline=u'\n') as fh:
        fh.write(body)

    log = os.path.join(logdir, u'utmt109.txt')
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

    try:
        for f in sorted(os.listdir(ddir)):
            print(u'  %12d %s' % (os.path.getsize(os.path.join(ddir, f)), f))
    except Exception:
        pass

    # 把产物拷回仓库证据目录（UTMT 只写 ASCII 安全路径）
    if ensure_dir(EV):
        for f in (u'fade_codes.json', u'fade_objects.json'):
            src = os.path.join(ddir, f)
            if os.path.exists(src):
                dst = os.path.join(EV, f)
                try:
                    shutil_copy(src, dst)
                    print(u'[copy] %s -> %s' % (src, dst))
                except Exception as e:
                    print(u'[copy-fail] %s: %s' % (f, e))
    return rc


def shutil_copy(a, b):
    import shutil
    shutil.copyfile(a, b)


if __name__ == u'__main__':
    sys.exit(main())

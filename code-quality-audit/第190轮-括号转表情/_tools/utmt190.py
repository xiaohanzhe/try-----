# -*- coding: utf-8 -*-
u"""第190轮 · 用 UTMT CLI 导出游戏包的 Sprite 名单（只导名字/尺寸/帧数，不导图）。

为什么要这一步
--------------
用户口径（2026-11-15）：「反正在原作的解包里应该有全套的，你看一下，都做，没有的也不用改动」
⇒ 得先知道**原作到底给哪些角色画了脸**。现有 `/e/项目文件夹/face` 等目录是历史抽出来的，
只有 Deltarune/UT 的一部分，**UTY 与 OuterTale 一片空白**，不能凭"目录里没有"就断言"原作没有"。

★★ 铁律（第84/85轮实测，勿改）：
   ① UTMT CLI 的 stdout **必须是文件**，不能是 PIPE；
   ② 调用形式 = `UndertaleModCli.exe load <datafile> -s <script.csx>`；
   ③ `.csx` 里 `FilePath` 在 CLI 下不可靠 ⇒ 用 `__OUTDIR__` 占位符由本脚本替换；
   ④ 中文路径会挂 ⇒ 工作目录用纯 ASCII（`D:\\_tmp190\\<tag>`），产物再拷回仓库。

用法
----
    python utmt190.py --pkg D:/_wb_tmp/dw_ut/uty/game.droid --tag hy
    python utmt190.py --pkg D:/_wb_tmp/dw_ut/outertale/game.droid --tag ot
    python utmt190.py --pkg D:/_wb_tmp/dw_ut/ut/game.droid --tag ut
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
import utmtpath190
EXE = utmtpath190.require()  # 优先 D 盘副本，E 盘坏点会 FailFast
EV = os.path.join(ROUND, '_evidence', 'sprites')
WORK_ROOTS = [u'D:\\_tmp190', os.path.join(tempfile.gettempdir(), 'utmt190')]


def ensure_dir(d):
    for _ in range(8):
        try:
            os.makedirs(d)
        except OSError:
            pass
        if os.path.isdir(d):
            return True
        time.sleep(0.3)
    return False


def writable(d):
    if not ensure_dir(d):
        return False
    p = os.path.join(d, '_w.tmp')
    try:
        with io.open(p, 'wb') as fh:
            fh.write(b'ok')
        os.remove(p)
        return True
    except Exception:  # noqa: BLE001
        return False


def pick():
    for r in WORK_ROOTS:
        if writable(r):
            return r
    return None


def main():
    argv = sys.argv[1:]
    if '--pkg' not in argv or '--tag' not in argv:
        print(__doc__)
        return 2
    pkg = argv[argv.index('--pkg') + 1]
    tag = argv[argv.index('--tag') + 1]
    if not os.path.isfile(pkg):
        print('[停手] 包不存在：%s' % pkg)
        return 2
    if not os.path.isfile(EXE):
        print('[停手] UTMT 不存在：%s' % EXE)
        return 2

    root = pick()
    if not root:
        print('[停手] 没有可写的 ASCII 工作目录')
        return 2
    ddir = os.path.join(root, tag)
    ensure_dir(ddir)
    print('[work] %s' % ddir)

    csx = os.path.join(HERE, 'dump_sprites190.csx')
    body = io.open(csx, 'r', encoding='utf-8').read()
    body = body.replace('__OUTDIR__', ddir.replace('\\', '/'))
    work = os.path.join(ddir, 'dump_sprites190.csx')
    with io.open(work, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(body)

    log = os.path.join(ddir, 'utmt.log')
    cmd = [EXE, 'load', pkg, '-s', work]
    print('[run] %s' % ' '.join(cmd))
    t0 = time.time()
    with io.open(log, 'wb') as fh:
        p = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL)
        rc = p.wait()
    print('[rc] %s  %.1fs' % (rc, time.time() - t0))
    try:
        txt = io.open(log, 'r', encoding='utf-8', errors='replace').read()
        print(txt[-1500:])
    except Exception:  # noqa: BLE001
        pass

    src = os.path.join(ddir, 'sprites.tsv')
    if not os.path.isfile(src):
        print('[失败] 没产出 sprites.tsv')
        return 3
    ensure_dir(EV)
    dst = os.path.join(EV, tag + '.tsv')
    shutil.copyfile(src, dst)
    n = sum(1 for _ in io.open(dst, encoding='utf-8', errors='replace')) - 1
    print('[ok] %s  %d 行' % (dst, n))
    return 0


if __name__ == '__main__':
    sys.exit(main())

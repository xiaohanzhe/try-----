# -*- coding: utf-8 -*-
u"""第190轮 · 导出整张贴图页（UTMT 自己解好的 Bitmap），用来判定"能不能上色"。

背景（详见 export_pages190.csx 顶部注释）
----------------------------------------
自写 QOI 解码器连试三种起点都是"解满但只吃 ~500 字节 / 出彩条噪声"⇒ 路不对。
改问最上游：UTMT 内存里的 `UndertaleEmbeddedTexture.TextureData.Image` 长什么样。
它是 UTMT **自己解出来的**，若它也是蒙版，就说明这是工具链上限而不是我写错。

★★ 铁律沿用（第84/85轮）：
   ① UTMT CLI 的 stdout 必须是**文件**；② `load <datafile> -s <script.csx>`；
   ③ csx 里用 `__OUTDIR__` 占位符，由本脚本替换；④ csx 与工作目录必须**纯 ASCII**
      （中文路径 ⇒ rc=3221225478 且不打印理由）。

用法
----
    python pages190.py --pkg D:/_wb_tmp/dw_ut/uty/game.droid --tag hy
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
EV = os.path.join(ROUND, '_evidence', 'pages')
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
    ddir = os.path.join(root, tag + '_pages')
    ensure_dir(ddir)
    print('[work] %s' % ddir)

    body = io.open(os.path.join(HERE, 'export_pages190.csx'), 'r', encoding='utf-8').read()
    body = body.replace('__OUTDIR__', ddir.replace('\\', '/'))
    work = os.path.join(ddir, 'export_pages190.csx')
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
        print(io.open(log, 'r', encoding='utf-8', errors='replace').read()[-2000:])
    except Exception:  # noqa: BLE001
        pass

    src = os.path.join(ddir, 'pages.tsv')
    if not os.path.isfile(src):
        print('[失败] 没产出 pages.tsv')
        return 3

    # ★ 验证闸：这张表必须有数据行，否则"没报错"毫无意义
    lines = [l for l in io.open(src, encoding='utf-8', errors='replace').read().splitlines() if l.strip()]
    if len(lines) < 2:
        print('[失败] pages.tsv 只有表头，没有页面')
        return 4

    ensure_dir(EV)
    dst = os.path.join(EV, tag + '.tsv')
    shutil.copyfile(src, dst)

    # 统计：有颜色的页（colors > 2）占比 —— 这是本轮的核心判据
    ok_c = 0
    tot = 0
    for l in lines[1:]:
        f = l.split('\t')
        if len(f) < 6:
            continue
        tot += 1
        try:
            if int(f[3]) > 2:
                ok_c += 1
        except Exception:  # noqa: BLE001
            pass
    print('[ok] %s  %d 页，其中 colors>2 的 %d 页' % (dst, tot, ok_c))
    return 0


if __name__ == '__main__':
    sys.exit(main())

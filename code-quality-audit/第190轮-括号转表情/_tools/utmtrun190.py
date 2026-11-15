# -*- coding: utf-8 -*-
u"""第190轮 · 通用 UTMT 脚本跑手（纯 ASCII 工作目录 + __OUTDIR__ 替换 + 日志落盘）。

为什么单独立一个
----------------
`utmt190.py`（导 sprite 名单）、`pages190.py`（导整页）各写了一遍驱动，
再为"反射探测 API"抄第三遍就是三份会各自跑偏的代码。
本脚本只做一件事：把 .csx 丢给 UTMT 跑，产物拷回 `_evidence/<子目录>/`。

★★ 铁律（第84/85轮实测）：
   ① CLI 的 stdout **必须是文件**，不能是 PIPE；
   ② 形式 = `UndertaleModCli.exe load <datafile> -s <script.csx>`；
   ③ `FilePath` 在 CLI 下不可靠 ⇒ csx 内用 `__OUTDIR__` 占位符；
   ④ csx 与工作目录必须**纯 ASCII**（中文路径 ⇒ rc=3221225478 = 0xC0000602，
      且不打印任何理由）。

用法
----
    python utmtrun190.py --pkg <game.droid> --tag hy --csx probe_api190.csx \
                         --ev api --want api_probe.txt
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
# ★★★ E 盘有散落坏点（记忆「环境」条已记）：跑 UTMT 时实测到
#   `ExecutionEngineException: In page error`（0xC0000006）——加载 Magick.NET 元数据时
#   磁盘页读不出来，进程直接 FailFast、rc=3221225478，日志里**只有这一句**，
#   看起来像"代码写错了"，极易误诊。E 盘原件的 md5 核对完好（属于偶发读坏）。
#   ⇒ 一律优先从 D 盘副本跑；副本由 `mkutmt190.py` 生成并逐字节校验。
EXE_CANDIDATES = [
    u'D:\\_tmp190\\utmt\\UndertaleModCli.exe',
    u'E:\\Download\\UTMT_CLI_v0.9.2.0\\UndertaleModCli.exe',
]
EXE = next((p for p in EXE_CANDIDATES if os.path.isfile(p)), EXE_CANDIDATES[-1])
EVID = os.path.join(ROUND, '_evidence')
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


def arg(argv, key, default=None):
    if key not in argv:
        return default
    i = argv.index(key)
    return argv[i + 1] if i + 1 < len(argv) else default


def main():
    argv = sys.argv[1:]
    pkg = arg(argv, '--pkg')
    tag = arg(argv, '--tag')
    csx_name = arg(argv, '--csx')
    ev_sub = arg(argv, '--ev', tag)
    want = arg(argv, '--want')
    lst = arg(argv, '--list')

    if not (pkg and tag and csx_name):
        print(__doc__)
        return 2
    csx_src = os.path.join(HERE, csx_name)
    for p in (pkg, csx_src, EXE):
        if not os.path.exists(p):
            print('[停手] 不存在：%s' % p)
            return 2

    root = pick()
    if not root:
        print('[停手] 没有可写的 ASCII 工作目录')
        return 2
    ddir = os.path.join(root, tag + '_' + os.path.splitext(csx_name)[0])
    ensure_dir(ddir)
    print('[work] %s' % ddir)

    # ★ 有的 csx（dump_uv190）靠**环境变量**拿清单，不靠占位符。
    #   清单本身可能在中文路径下 ⇒ 必须复制进 ASCII 工作目录再交给 UTMT，
    #   否则 csx 里 File.Exists 会因为编码/路径问题失败（表现为"清单为空"）。
    env = dict(os.environ)
    env['R190_OUT'] = ddir
    if lst:
        if not os.path.isfile(lst):
            print('[停手] 清单不存在：%s' % lst)
            return 2
        l2 = os.path.join(ddir, 'list.txt')
        with io.open(l2, 'w', encoding='utf-8', newline='\n') as fh:
            for ln in io.open(lst, encoding='utf-8').read().splitlines():
                if ln.strip():
                    fh.write(ln.strip() + '\n')
        env['R190_LIST'] = l2
        print('[list] %d 行 → %s' % (sum(1 for _ in io.open(l2, encoding='utf-8')), l2))

    body = io.open(csx_src, 'r', encoding='utf-8').read()
    # ★ 只替换占位符，别自作聪明改别的
    body = body.replace('__OUTDIR__', ddir.replace('\\', '/'))
    work = os.path.join(ddir, csx_name)
    with io.open(work, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(body)

    log = os.path.join(ddir, 'utmt.log')
    cmd = [EXE, 'load', pkg, '-s', work]
    print('[run] %s' % ' '.join(cmd))
    t0 = time.time()
    with io.open(log, 'wb') as fh:
        p = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, env=env)
        rc = p.wait()
    dt = time.time() - t0
    print('[rc] %s  %.1fs' % (rc, dt))
    txt = u''
    try:
        txt = io.open(log, 'r', encoding='utf-8', errors='replace').read()
    except Exception:  # noqa: BLE001
        pass
    print(txt[-2500:])

    if want:
        src = os.path.join(ddir, want)
        if not os.path.isfile(src):
            print('[失败] 没产出 %s' % want)
            return 3
        dst_dir = os.path.join(EVID, ev_sub)
        ensure_dir(dst_dir)
        dst = os.path.join(dst_dir, want)
        shutil.copyfile(src, dst)
        print('[ok] %s  %d B' % (dst, os.path.getsize(dst)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

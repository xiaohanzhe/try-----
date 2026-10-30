# -*- coding: utf-8 -*-
u"""第123轮：对 UT 的 game.droid **副本**跑 `dump_doors123.csx`，取回全部门对象的反编译代码。

为什么不复用 `第115轮/_tools/run_csx_ut.py`：
  那个脚本默认跑三款作品（ut / uty / outertale），一次要几十分钟；本轮只要 ut。
  但它已经踩平的那些坑必须照抄，所以这里**逐条沿用**：
  · 启动方式 `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`（普通 subprocess 起不来，§115C）
  · **stdout 必须落文件**（管道会被吞）
  · 先 sha256 双向核对副本，再对**副本** `load`，绝不碰原始 game.droid
  · 产物 sha256 核验后才入库

★ E: 是坏盘（读卡死会拖死父进程）⇒ 工作目录与副本一律放 D:。

用法::

    python run123.py            # 跑并入库
    python run123.py --dry      # 只打印将要执行的命令
"""
import argparse
import hashlib
import io
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

# ★★ 第123轮实测：`E:\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe` **启动即
#   `OSError: [WinError 193] 不是有效的 Win32 应用程序`** —— 而同一份 exe（sha256 逐字节
#   相同、PE 头 machine=0x8664 x64、目录里 dll 齐全）从 `D:\E盘备份_20261028\...` 起就正常。
#   ⇒ 这也是 **E: exFAT 坏盘**的又一形态：`CreateProcess` 读镜像时拿到坏页。
#   ⇒ 默认改走 D 盘副本；`UTMT_EXE` 仍可覆盖。
EXE = os.environ.get(
    'UTMT_EXE',
    r'D:\E盘备份_20261028\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe')
SRC = os.environ.get(
    'UT_DATA',
    r'D:\E盘备份_20261028\Download\_extract61\_data\undertale\game.droid')
WORK = os.environ.get('DUMP_WORK123', r'D:\_wb_tmp\dw123')
#: csx 会产出**两个**文件：事件代码 + 对象元数据（含父对象）
OUT_NAMES = ('door_codes123.json', 'door_objects123.json')
RAW = os.path.join(ROUND, '_evidence', 'raw')

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
TIMEOUT = 1800


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args(argv)

    csx = os.path.join(HERE, 'dump_doors123.csx')
    for p, why in ((EXE, 'UTMT'), (SRC, 'UT game.droid'), (csx, 'csx')):
        if not os.path.isfile(p):
            print(u'[FAIL] %s 不存在: %s' % (why, p))
            return 2

    os.makedirs(WORK, exist_ok=True)
    dst = os.path.join(WORK, 'game.droid')
    need_copy = not (os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(SRC))
    print(u'数据源 %s (%.1f MB)' % (SRC, os.path.getsize(SRC) / 1048576.0))
    print(u'工作副本 %s（%s）' % (dst, u'待复制' if need_copy else u'已存在、大小一致'))
    if a.dry:
        print(u'将执行: %s load %s -s %s' % (EXE, dst, csx))
        return 0

    if need_copy:
        t0 = time.time()
        shutil.copyfile(SRC, dst)
        print(u'  复制用 %.1fs' % (time.time() - t0))
    if sha(SRC) != sha(dst):
        print(u'[FAIL] 副本 sha256 不一致（不 load 可疑数据）')
        return 3
    print(u'  sha256 双向一致: %s' % sha(dst)[:16])

    produced = [os.path.join(WORK, n) for n in OUT_NAMES]
    for p0 in produced:
        if os.path.isfile(p0):
            try:
                os.remove(p0)
            except OSError as e:
                print(u'  旧产物删不掉（会覆写）: %s' % e)

    logp = os.path.join(WORK, 'run_door123.log')
    t0 = time.time()
    with open(logp, 'wb') as f:
        p = subprocess.Popen([EXE, 'load', dst, '-s', csx],
                             stdout=f, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL,
                             creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
        while p.poll() is None:
            if time.time() - t0 > TIMEOUT:
                print(u'[FAIL] 超时 %ds，强杀' % TIMEOUT)
                p.kill()
                break
            time.sleep(2)
    dt = time.time() - t0
    tail = io.open(logp, 'rb').read()[-800:].decode('utf-8', 'replace')
    print(u'  rc=%r 用时 %.1fs' % (p.returncode, dt))
    for ln in tail.strip().splitlines()[-8:]:
        print(u'    | %s' % ln)

    miss = [os.path.basename(q) for q in produced
            if not (os.path.isfile(q) and os.path.getsize(q) > 0)]
    if miss:
        print(u'[FAIL] 缺产物: %s' % miss)
        return 4

    outdir = os.path.join(RAW, 'ut')
    os.makedirs(outdir, exist_ok=True)
    bad = []
    for q in produced:
        dst_raw = os.path.join(outdir, os.path.basename(q))
        shutil.copyfile(q, dst_raw)
        same = sha(q) == sha(dst_raw)
        if not same:
            bad.append(os.path.basename(q))
        print(u'[ok] 入库 %s（%.1f KB）sha256 一致=%s'
              % (dst_raw, os.path.getsize(dst_raw) / 1024.0, same))
    return 0 if not bad else 5


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))

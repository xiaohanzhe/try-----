# -*- coding: utf-8 -*-
u"""第120轮通用 UTMT 运行器（独立于第115轮那份，只为本轮服务）。

与 115 轮的 `run_csx_ut.py` 的差别：
  · 不再「复制 game.droid + sha256 双向核对」—— 副本早在 115 轮就建好了，
    这里只**复核一次** sha256 与源一致，不一致直接拒绝跑（防止有人换了源还以为在测旧的）。
  · 产物落 `_out/<file>`，可以一次落**多个**（贴图导出会顺手写一整个目录）。

用法：
    python run120.py --game ut --csx probe_tex120.csx --out probe_tex120.tsv
    python run120.py --game outertale --csx dump_rooms120.csx --out rooms120.tsv
"""
import argparse
import hashlib
import io
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)

EXE = os.environ.get(
    'UTMT_EXE',
    r'D:\E盘备份_20261028\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe')
WORK = os.environ.get('DUMP_WORK_UT', r'D:\_wb_tmp\dw_ut')

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
TIMEOUT = 3600

_SRC = r'D:\E盘备份_20261028\Download\_extract61\_data'
_PRE = r'D:\E盘备份_20261028\Download\_extract64\assets'

GAMES = {
    'ut': os.path.join(_SRC, 'undertale', 'game.droid'),
    'uty': os.path.join(_SRC, 'undertale_yellow', 'game.droid'),
    'outertale': os.path.join(_PRE, 'game.droid'),
}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', required=True, help='ut / uty / outertale')
    ap.add_argument('--csx', required=True, help='要跑的 csx 文件名（放 _tools 下）')
    ap.add_argument('--out', required=True, help='csx 写出的文件名（落 _out/）')
    ap.add_argument('--distil', action='store_true',
                    help='把产物复制进 _evidence/raw/<game>/')
    a = ap.parse_args(argv)

    src = GAMES.get(a.game)
    if not src:
        print('[FAIL] 未知 --game=%r（可选 %s）' % (a.game, '/'.join(GAMES)))
        return 2
    if not os.path.isfile(src):
        print('[FAIL] 源不存在: %s' % src)
        return 2

    csx = a.csx if os.path.isabs(a.csx) else os.path.join(HERE, a.csx)
    if not os.path.isfile(csx):
        print('[FAIL] csx 不存在: %s' % csx)
        return 2
    if not os.path.isfile(EXE):
        print('[FAIL] UTMT 不存在: %s' % EXE)
        return 2

    d = os.path.join(WORK, a.game)
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, 'game.droid')

    if os.path.isfile(dst):
        hs, hd = sha(src), sha(dst)
        if hs != hd:
            print('[FAIL] 工作副本与源 sha256 不一致，拒绝运行：\n  源 %s\n  副 %s' % (hs, hd))
            return 3
        print('[ok] 工作副本 sha256 一致 %s' % hs[:16])
    else:
        t0 = time.time()
        shutil.copyfile(src, dst)
        print('[ok] 复制 %.1f MB 用 %.1fs' % (os.path.getsize(src) / 1048576.0, time.time() - t0))
        if sha(src) != sha(dst):
            print('[FAIL] 复制后 sha256 不一致')
            return 3

    outdir = os.path.join(d, '_out')
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, a.out)
    if os.path.isfile(outpath):
        os.remove(outpath)

    env = dict(os.environ)
    env['UTMT_OUT'] = outpath
    logpath = os.path.join(d, 'run_%s.log' % a.out.replace('.', '_'))
    t0 = time.time()
    with open(logpath, 'wb') as f:
        p = subprocess.Popen([EXE, 'load', dst, '-s', csx],
                             stdout=f, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, env=env,
                             creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
        while p.poll() is None:
            if time.time() - t0 > TIMEOUT:
                print('[FAIL] 超时 %ds，强杀' % TIMEOUT)
                p.kill()
                break
            time.sleep(2)
    dt = time.time() - t0

    tail = ''
    if os.path.isfile(logpath):
        tail = io.open(logpath, 'rb').read()[-1500:].decode('utf-8', 'replace')
    ok = os.path.isfile(outpath)
    print('[run] rc=%r 用时 %.1fs 产物=%s 大小=%s'
          % (p.returncode, dt, ok, os.path.getsize(outpath) if ok else -1))
    if tail.strip():
        print('----- stdout tail -----')
        print(tail)

    if ok and a.distil:
        raw = os.path.join(ROUND, '_evidence', 'raw', a.game)
        os.makedirs(raw, exist_ok=True)
        shutil.copyfile(outpath, os.path.join(raw, a.out))
        print('[ok] 已入库 %s' % os.path.join(raw, a.out))

    return 0 if ok else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))

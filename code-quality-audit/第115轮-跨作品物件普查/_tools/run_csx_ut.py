# -*- coding: utf-8 -*-
u"""通用 UTMT 运行器：对 UT / UTY / Outertale 三份 game.droid 跑任意 csx。

比再写第三个专用脚本好：csx 与产物名都由参数给，复制/校验/分离启动/蒸馏只有一份实现。

用法：
    python run_csx_ut.py --csx conn_ut.csx --out conn_ut.json
    python run_csx_ut.py --csx dump_objects_ut.csx --out objmap_ut.txt --no-distil

★ 启动方式沿用第115轮结论：DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP，stdout 落文件。
★ 先 sha256 双向核对副本，再对**副本** load，绝不碰原始 game.droid。
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
RAW = os.path.join(ROUND, '_evidence', 'raw')

EXE = os.environ.get(
    'UTMT_EXE',
    r'D:\E盘备份_20261028\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe')
WORK = os.environ.get('DUMP_WORK_UT', r'D:\_wb_tmp\dw_ut')

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
TIMEOUT = 1800

_SRC = r'D:\E盘备份_20261028\Download\_extract61\_data'
_PRE = r'D:\E盘备份_20261028\Download\_extract64\assets'

GAMES = [
    ('ut', os.path.join(_SRC, 'undertale', 'game.droid'), 338),
    ('uty', os.path.join(_SRC, 'undertale_yellow', 'game.droid'), 287),
    ('outertale', os.path.join(_PRE, 'game.droid'), 358),
]


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--csx', required=True, help='_tools 下的 csx 文件名')
    ap.add_argument('--out', required=True, help='csx 在工作目录里产出的文件名')
    ap.add_argument('--no-distil', action='store_true', help='只留在工作目录，不复制进仓库')
    a = ap.parse_args(argv)

    csx = a.csx if os.path.isabs(a.csx) else os.path.join(HERE, a.csx)
    if not os.path.isfile(csx):
        print('[FAIL] csx 不存在: %s' % csx)
        return 2
    if not os.path.isfile(EXE):
        print('[FAIL] UTMT 不存在: %s' % EXE)
        return 2

    logpath = os.path.join(WORK, '_run_%s.log' % a.out.replace('.', '_'))
    os.makedirs(WORK, exist_ok=True)
    log = io.open(logpath, 'w', encoding='utf-8', buffering=1)

    def w(s):
        log.write(s + '\n')
        log.flush()

    w('CSX = %s' % csx)
    w('OUT = %s' % a.out)
    rows = []
    for key, src, exp_rooms in GAMES:
        w('=' * 60)
        d = os.path.join(WORK, key)
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, 'game.droid')
        if not os.path.isfile(src):
            w('[%s] !! 源不存在' % key)
            rows.append((key, 'MISSING', -1))
            continue
        if not (os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(src)):
            t0 = time.time()
            shutil.copyfile(src, dst)
            w('[%s] 复制 %.1f MB 用 %.1fs'
              % (key, os.path.getsize(src) / 1048576.0, time.time() - t0))
        if sha(src) != sha(dst):
            w('[%s] !! 副本 sha256 不一致，跳过' % key)
            rows.append((key, 'SHA_MISMATCH', -1))
            continue

        produced = os.path.join(d, a.out)
        if os.path.isfile(produced):
            try:
                os.remove(produced)
            except OSError as e:
                w('[%s] 旧产物删不掉（不影响，会覆写）: %s' % (key, e))

        out_log = os.path.join(d, 'run_%s.log' % a.out.replace('.', '_'))
        t0 = time.time()
        with open(out_log, 'wb') as f:
            p = subprocess.Popen([EXE, 'load', dst, '-s', csx],
                                 stdout=f, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL,
                                 creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
            while p.poll() is None:
                if time.time() - t0 > TIMEOUT:
                    w('[%s] !! 超时，强杀' % key)
                    p.kill()
                    break
                time.sleep(2)
        dt = time.time() - t0
        ok = os.path.isfile(produced)
        sz = os.path.getsize(produced) if ok else -1
        tail = (io.open(out_log, 'rb').read()[-500:].decode('utf-8', 'replace')
                if os.path.isfile(out_log) else '')
        w('[%s] rc=%r 用时 %.1fs 产物=%s 大小=%d' % (key, p.returncode, dt, ok, sz))
        w('[%s] stdout: %s' % (key, tail.replace('\n', ' | ')[:400]))
        verdict = 'OK' if ok and sz > 0 else 'NO_OUTPUT'
        rows.append((key, verdict, sz))
        if ok and not a.no_distil:
            dst_raw = os.path.join(RAW, key, a.out)
            os.makedirs(os.path.dirname(dst_raw), exist_ok=True)
            shutil.copyfile(produced, dst_raw)
            w('[%s] 已入库 %s sha256 一致=%s'
              % (key, dst_raw, sha(produced) == sha(dst_raw)))

    w('=' * 60)
    w('SUMMARY')
    for k, v, s in rows:
        w('  %-10s %-12s size=%d' % (k, v, s))
    log.close()
    print('DONE  (log: %s)' % logpath)
    for k, v, s in rows:
        print('  %-10s %-12s size=%d' % (k, v, s))
    return 0 if all(v == 'OK' for _, v, _ in rows) else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))

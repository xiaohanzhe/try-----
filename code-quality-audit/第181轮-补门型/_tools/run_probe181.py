# -*- coding: utf-8 -*-
u"""第181轮 · 跑 probe181.csx（五章各一次 load）。

★ 只读：不写 data.win，只写本脚本自己的产物 ⇒ 重跑安全（幂等，不删任何既有件）。
★ 产出落 D 盘临时区（`D:\\_tmp181\\`），核验后再拷进仓库 `_evidence/raw/`。
   依据用户口径：临时/递归活 → D；成品证据 → 仓库。
★ 启动方式沿用第115/171轮：DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP，stdin=DEVNULL，
  stdout 落文件（**不许接管道**，UTMT 会挂）。

用法：
    python run_probe181.py            # 五章全跑
    python run_probe181.py --ch 1 2   # 只跑指定章
    python run_probe181.py --force    # 已有产物也重跑
"""
import argparse
import hashlib
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
RAW = os.path.join(ROUND, '_evidence', 'raw')

EXE = os.environ.get(
    'UTMT_EXE',
    r'D:\E盘备份_20261028\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe')
DRW = os.environ.get(
    'P181_DRW',
    r'D:\E盘备份_20261028\Download\_tmp\drw')
WORK = os.environ.get('P181_WORK', r'D:\_tmp181')

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
TIMEOUT = 2400


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--ch', nargs='*', type=int, default=[1, 2, 3, 4, 5])
    ap.add_argument('--force', action='store_true')
    # ★ 通用化：同一套"分离启动 + stdout 落文件 + 产物核验"给两个探针共用，
    #   避免复制粘贴出两份会各自漂移的实现。默认值 = 原来的 probe181 行为。
    ap.add_argument('--csx', default='probe181.csx')
    ap.add_argument('--env', default='P181_OUT')
    ap.add_argument('--tag', default='probe181')
    ap.add_argument('--ext', default='txt')
    a = ap.parse_args(argv)

    csx = a.csx if os.path.isabs(a.csx) else os.path.join(HERE, a.csx)
    for p in (csx, EXE):
        if not os.path.isfile(p):
            print(u'[FAIL] 缺 %s' % p)
            return 2
    os.makedirs(WORK, exist_ok=True)

    print(u'CSX  = %s' % csx)
    print(u'TAG  = %s   ENV = %s' % (a.tag, a.env))
    print(u'EXE  = %s' % EXE)
    print(u'DRW  = %s' % DRW)
    print(u'WORK = %s' % WORK)
    rows = []
    for ch in a.ch:
        src = os.path.join(DRW, 'chapter%d_windows' % ch, 'data.win')
        out = os.path.join(WORK, '%s.ch%d.%s' % (a.tag, ch, a.ext))
        log = os.path.join(WORK, 'run_%s.ch%d.log' % (a.tag, ch))
        print('=' * 66)
        print(u'ch%d' % ch)
        if not os.path.isfile(src):
            print(u'  !! data.win 不存在: %s' % src)
            rows.append((ch, 'MISSING', -1))
            continue
        if os.path.isfile(out) and os.path.getsize(out) > 0 and not a.force:
            print(u'  已有产物 %.1f KB，跳过（--force 可重跑）'
                  % (os.path.getsize(out) / 1024.0))
            rows.append((ch, 'CACHED', os.path.getsize(out)))
            continue

        env = dict(os.environ)
        env[a.env] = out
        t0 = time.time()
        with open(log, 'wb') as f:
            p = subprocess.Popen([EXE, 'load', src, '-s', csx],
                                 stdout=f, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, env=env,
                                 creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
            while p.poll() is None:
                if time.time() - t0 > TIMEOUT:
                    print(u'  !! 超时，强杀')
                    p.kill()
                    break
                time.sleep(2)
        dt = time.time() - t0
        ok = os.path.isfile(out) and os.path.getsize(out) > 0
        sz = os.path.getsize(out) if ok else -1
        tail = ''
        if os.path.isfile(log):
            tail = io.open(log, 'rb').read()[-300:].decode('utf-8', 'replace')
        print(u'  rc=%r 用时 %.1fs 产物=%s 大小=%d' % (p.returncode, dt, ok, sz))
        print(u'  stdout: %s' % tail.replace('\n', ' | ')[:300])
        rows.append((ch, 'OK' if ok else 'NO_OUTPUT', sz))

    print('=' * 66)
    print(u'SUMMARY')
    for ch, v, s in rows:
        print(u'  ch%-3d %-12s size=%d' % (ch, v, s))
    return 0 if all(v in ('OK', 'CACHED') for _, v, _ in rows) else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))

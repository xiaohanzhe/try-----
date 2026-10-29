# -*- coding: utf-8 -*-
"""导出 UT / UTY / Outertale 的 GameObject 索引（objmap_ut.txt）。

产物格式与第43轮 objmap43.txt 完全一致，便于 props 分级脚本复用 load_objmap()。

★ 启动方式沿用第115轮结论：DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP，stdout 落文件。
★ 先校验源→副本 sha256，再对副本 load（绝不碰原始 game.droid）。
"""
import hashlib
import io
import os
import shutil
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
RAW = os.path.join(ROUND, '_evidence', 'raw')

EXE = os.environ.get(
    'UTMT_EXE',
    r'D:\E盘备份_20261028\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe')
CSX = os.path.join(HERE, 'dump_objects_ut.csx')
WORK = os.environ.get('DUMP_WORK_UT', r'D:\_wb_tmp\dw_ut')
LOG = os.path.join(WORK, '_dump_obj_ut.log')

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

os.makedirs(WORK, exist_ok=True)
log = io.open(LOG, 'w', encoding='utf-8', buffering=1)


def w(s):
    log.write(s + '\n')
    log.flush()


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


w('EXE=%s exists=%s' % (EXE, os.path.isfile(EXE)))
w('CSX=%s exists=%s' % (CSX, os.path.isfile(CSX)))
if not (os.path.isfile(EXE) and os.path.isfile(CSX)):
    w('!! 前置缺失，终止')
    log.close()
    raise SystemExit(2)

summary = []
for key, src, exp_rooms in GAMES:
    w('=' * 60)
    d = os.path.join(WORK, key)
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, 'game.droid')
    if not os.path.isfile(src):
        w('[%s] !! 源不存在' % key)
        summary.append((key, 'MISSING', -1, -1))
        continue
    ssz = os.path.getsize(src)
    if not (os.path.isfile(dst) and os.path.getsize(dst) == ssz):
        t0 = time.time()
        shutil.copyfile(src, dst)
        w('[%s] 复制 %.1f MB 用 %.1fs' % (key, ssz / 1048576.0, time.time() - t0))
    if sha(src) != sha(dst):
        w('[%s] !! sha256 不一致，跳过' % key)
        summary.append((key, 'SHA_MISMATCH', -1, -1))
        continue
    w('[%s] 副本 sha256 校验通过（源 %.1f MB）' % (key, ssz / 1048576.0))

    out_txt = os.path.join(d, 'objmap_ut.txt')
    out_log = os.path.join(d, 'run_obj.log')
    if os.path.isfile(out_txt):
        try:
            os.remove(out_txt)
        except OSError as e:
            w('[%s] 旧文件删不掉（不影响，会覆写）: %s' % (key, e))

    t0 = time.time()
    with open(out_log, 'wb') as f:
        p = subprocess.Popen([EXE, 'load', dst, '-s', CSX],
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

    ok = os.path.isfile(out_txt)
    nobj = nrooms = 0
    header = ''
    if ok:
        in_rooms = False
        for ln in io.open(out_txt, encoding='utf-8', errors='replace'):
            ln = ln.rstrip('\n')
            if ln.startswith('GameObjects = '):
                header = ln
                continue
            if ln.startswith('== Rooms = '):
                in_rooms = True
                continue
            if ln.startswith('!!'):
                header = ln[:120]
                continue
            if not ln:
                continue
            if not ln.split('\t')[0].strip().isdigit():
                continue
            if in_rooms:
                nrooms += 1
            else:
                nobj += 1

    w('[%s] rc=%r 用时 %.1fs txt=%s objs=%d rooms=%d %s' % (
        key, p.returncode, dt,
        os.path.getsize(out_txt) if ok else -1, nobj, nrooms, header))
    tail = io.open(out_log, 'rb').read()[-400:].decode('utf-8', 'replace')
    w('[%s] log: %s' % (key, tail.replace('\n', ' | ')[:300]))

    verdict = 'OK'
    notes = []
    if not ok:
        verdict = 'NO_TXT'
    else:
        if nrooms != exp_rooms:
            verdict = 'CONFLICT'
            notes.append('房间数 %d != 已知 %d' % (nrooms, exp_rooms))
        if nobj <= 0:
            verdict = 'NO_OBJ'
    w('[%s] 判定=%s %s' % (key, verdict, '; '.join(notes)))
    summary.append((key, verdict, nobj, nrooms))

    if ok:
        dst_raw = os.path.join(RAW, key, 'objmap_ut.txt')
        os.makedirs(os.path.dirname(dst_raw), exist_ok=True)
        shutil.copyfile(out_txt, dst_raw)
        w('[%s] 已入库 %s sha256 一致=%s'
          % (key, dst_raw, sha(out_txt) == sha(dst_raw)))

w('=' * 60)
w('SUMMARY')
for k, v, o, r in summary:
    w('  %-10s %-12s objs=%-6d rooms=%-5d' % (k, v, o, r))
w('ALL DONE')
log.close()
print('DONE')
for k, v, o, r in summary:
    print('  %-10s %-12s objs=%-6d rooms=%-5d' % (k, v, o, r))

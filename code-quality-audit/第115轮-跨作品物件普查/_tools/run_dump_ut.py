# -*- coding: utf-8 -*-
"""用 UTMT CLI 导出 UT / UTY / Outertale 的全量实例坐标。

与 run_dump115.py 的差异（只有三点）：
  1. 源是 `game.droid`（安卓包），不是 `data.win`；
  2. 三款各自一份，`EXPECT` 允许为 None（未知就只记录实测值，不假装校验）；
  3. 蒸馏规则改为「原始 TSV 一律入库，期望不符单独记 CONFLICT」——
     因为这是新开的 raw 子目录，不存在被坏数据覆盖的旧件。

★ 启动方式沿用第115轮结论：DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP，
  stdout 必须落文件（否则 UTMT 的输出会把父进程一起带走）。
★ 临时副本一律落 D:（E: 是坏盘，不当工作盘）。
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
CSX = os.path.join(HERE, 'dump_instances.csx')
WORK = os.environ.get('DUMP_WORK_UT', r'D:\_wb_tmp\dw_ut')
LOG = os.path.join(WORK, '_dump_ut.log')

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
TIMEOUT = 1800

_SRC = r'D:\E盘备份_20261028\Download\_extract61\_data'
_PRE = r'D:\E盘备份_20261028\Download\_extract64\assets'

# key -> (源文件, 期望房间数, 期望房间名前缀)
# 338 / 287 来自详版 §87.11 登记（第42轮拓扑取证），作为独立交叉校验；
# Outertale 没有历史登记，期望写 None。
GAMES = [
    ('ut', os.path.join(_SRC, 'undertale', 'game.droid'), 338, 'room_'),
    ('uty', os.path.join(_SRC, 'undertale_yellow', 'game.droid'), 287, 'rm_'),
    ('outertale', os.path.join(_PRE, 'game.droid'), None, None),
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


w('EXE exists = %s' % os.path.isfile(EXE))
w('CSX exists = %s' % os.path.isfile(CSX))
if not os.path.isfile(EXE) or not os.path.isfile(CSX):
    w('!! 前置缺失，终止')
    log.close()
    raise SystemExit(2)

summary = []

for key, src, exp_rooms, exp_prefix in GAMES:
    w('=' * 60)
    w('[%s] src=%s' % (key, src))
    if not os.path.isfile(src):
        w('[%s] !! 源文件不存在，跳过' % key)
        summary.append((key, 'MISSING', -1, -1, ''))
        continue

    d = os.path.join(WORK, key)
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, 'game.droid')
    ssz = os.path.getsize(src)
    if not (os.path.isfile(dst) and os.path.getsize(dst) == ssz):
        t0 = time.time()
        shutil.copyfile(src, dst)
        w('[%s] 复制 %.1f MB 用 %.1fs' % (key, ssz / 1048576.0, time.time() - t0))
    hs, hd = sha(src), sha(dst)
    w('[%s] sha256 src=%s dst=%s 一致=%s' % (key, hs[:12], hd[:12], hs == hd))
    if hs != hd:
        w('[%s] !! 副本校验失败，跳过' % key)
        summary.append((key, 'SHA_MISMATCH', -1, -1, ''))
        continue

    out_tsv = os.path.join(d, 'inst_full.tsv')
    out_log = os.path.join(d, 'run.log')
    env = dict(os.environ)
    env['UTMT_OUT'] = out_tsv
    if os.path.isfile(out_tsv):
        try:
            os.remove(out_tsv)          # 单文件删除，非批量，允许
        except OSError as e:
            w('[%s] 旧 tsv 删不掉（不影响，会覆写）: %s' % (key, e))

    t0 = time.time()
    with open(out_log, 'wb') as f:
        p = subprocess.Popen(
            [EXE, 'load', dst, '-s', CSX],
            stdout=f, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, env=env,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
        while p.poll() is None:
            if time.time() - t0 > TIMEOUT:
                w('[%s] !! 超时 %ds，强杀' % (key, TIMEOUT))
                p.kill()
                break
            time.sleep(2)
    dt = time.time() - t0

    ok = os.path.isfile(out_tsv)
    nrooms = ninst = 0
    prefixes = {}
    if ok:
        with io.open(out_tsv, encoding='utf-8') as f:
            f.readline()                     # H 行
            for ln in f:
                if ln.startswith('R\t'):
                    nrooms += 1
                    parts = ln.rstrip('\n').split('\t')
                    if len(parts) > 2:
                        nm = parts[2]
                        pre = nm.split('_')[0] + '_' if '_' in nm else '(no underscore)'
                        prefixes[pre] = prefixes.get(pre, 0) + 1
                elif ln.startswith('I\t'):
                    ninst += 1

    w('[%s] rc=%r 用时 %.1fs tsv=%s rooms=%d inst=%d' % (
        key, p.returncode, dt,
        os.path.getsize(out_tsv) if ok else -1, nrooms, ninst))
    top = sorted(prefixes.items(), key=lambda kv: -kv[1])[:6]
    w('[%s] 房间名前缀 top: %s' % (key, top))
    tail = io.open(out_log, 'rb').read()[-500:].decode('utf-8', 'replace') if os.path.isfile(out_log) else ''
    w('[%s] log: %s' % (key, tail.replace('\n', ' | ')[:350]))

    verdict = 'OK'
    notes = []
    if not ok:
        verdict = 'NO_TSV'
    else:
        if exp_rooms is not None and nrooms != exp_rooms:
            verdict = 'CONFLICT'
            notes.append('房间数 %d != 历史登记 %d' % (nrooms, exp_rooms))
        if exp_prefix is not None and prefixes.get(exp_prefix, 0) < nrooms * 0.5:
            notes.append('房间名前缀 %s 只占 %d/%d' % (exp_prefix, prefixes.get(exp_prefix, 0), nrooms))
        if ninst <= 0:
            verdict = 'NO_INST'
            notes.append('实例数为 0')
    w('[%s] 判定=%s %s' % (key, verdict, '; '.join(notes)))
    summary.append((key, verdict, nrooms, ninst, ','.join(notes)))

    # 原始件一律入库（新目录，不会覆盖旧证据）
    if ok:
        dst_raw = os.path.join(RAW, key)
        os.makedirs(dst_raw, exist_ok=True)
        dst_tsv = os.path.join(dst_raw, 'inst_full.tsv')
        shutil.copyfile(out_tsv, dst_tsv)
        w('[%s] 已入库 %s sha256 一致=%s' % (key, dst_tsv, sha(out_tsv) == sha(dst_tsv)))

w('=' * 60)
w('SUMMARY')
for k, v, r, i, n in summary:
    w('  %-10s %-10s rooms=%-5d inst=%-7d %s' % (k, v, r, i, n))
w('ALL DONE')
log.close()
print('DONE')
for k, v, r, i, n in summary:
    print('  %-10s %-10s rooms=%-5d inst=%-7d %s' % (k, v, r, i, n))

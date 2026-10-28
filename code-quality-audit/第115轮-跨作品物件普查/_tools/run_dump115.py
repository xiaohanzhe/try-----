# -*- coding: utf-8 -*-
"""用 UTMT CLI 导出五章全量实例坐标。

★ 关键：必须用 DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP 启动。
  直接 Popen/CreateProcess（继承我们的控制台/作业）会被秒杀，连父进程一起 SIGTERM；
  断出去之后一切正常（实测 --help 返回 rc=0）。

流程（每章）：复制 data.win 到 D:（只对副本 load）→ sha256 双向核对 → 跑 csx → 校验行数。
进度写 D:\\_wb_tmp\\_dump_progress.log（逐行 flush）。
"""
import hashlib
import io
import os
import shutil
import subprocess
import time

EXE = os.environ.get('UTMT_EXE',
                     r'D:\E盘备份_20261028\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe')
CSX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dump_instances.csx')
GAME = os.environ.get('DELTARUNE_DIR',
                      r'C:\Users\23002\Desktop\项目文件夹\珍贵的回忆\DELTARUNE_183049\DELTARUNE')
WORK = os.environ.get('DUMP_WORK', r'D:\_wb_tmp\dw')
LOG = os.path.join(WORK, '_dump_progress.log')
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
EXPECT = {1: (147, 3513), 2: (278, 8050), 3: (246, 9892), 4: (328, 13953), 5: (252, 12487)}
RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   '_evidence', 'raw')

os.makedirs(WORK, exist_ok=True)
log = open(LOG, 'w', encoding='utf-8', buffering=1)


def w(s):
    log.write(s + '\n')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


for ch in (1, 2, 3, 4, 5):
    src = os.path.join(GAME, 'chapter%d_windows' % ch, 'data.win')
    d = os.path.join(WORK, 'ch%d' % ch)
    dst = os.path.join(d, 'data.win')
    os.makedirs(d, exist_ok=True)
    if not (os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(src)):
        t0 = time.time()
        shutil.copyfile(src, dst)
        w('ch%d 复制 %.1f MB 用 %.1fs' % (ch, os.path.getsize(src) / 1048576.0, time.time() - t0))
    hs, hd = sha(src), sha(dst)
    w('ch%d sha256 src=%s dst=%s 一致=%s' % (ch, hs[:12], hd[:12], hs == hd))
    if hs != hd:
        w('ch%d !! 副本校验失败，跳过' % ch)
        continue

    out_tsv = os.path.join(d, 'inst_full.tsv')
    out_log = os.path.join(d, 'run.log')
    env = dict(os.environ)
    env['UTMT_OUT'] = out_tsv
    t0 = time.time()
    with open(out_log, 'wb') as f:
        p = subprocess.Popen([EXE, 'load', dst, '-s', CSX],
                             stdout=f, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, env=env,
                             creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
        while p.poll() is None:
            if time.time() - t0 > 1800:
                w('ch%d !! 超时 30min，强杀' % ch)
                p.kill()
                break
            time.sleep(2)
    dt = time.time() - t0
    ok = os.path.isfile(out_tsv)
    nrooms = ninst = -1
    if ok:
        with io.open(out_tsv, encoding='utf-8') as f:
            head = f.readline().rstrip('\n').split('\t')
            nrooms = 0
            ninst = 0
            for ln in f:
                if ln.startswith('R\t'):
                    nrooms += 1
                elif ln.startswith('I\t'):
                    ninst += 1
    w('ch%d rc=%r 用时 %.1fs tsv=%s rooms=%d inst=%d 期望=%s' % (
        ch, p.returncode, dt, os.path.getsize(out_tsv) if ok else -1, nrooms, ninst, EXPECT[ch]))
    tail = io.open(out_log, 'rb').read()[-600:].decode('utf-8', 'replace')
    w('    log: ' + tail.replace('\n', ' | ')[:400])

    # 只有「房间数 + 实例数」都对上才蒸馏进仓库（否则宁可留空的，也不要把坏数据写进去）
    if ok and (nrooms, ninst) == EXPECT[ch]:
        dst_raw = os.path.join(RAW, 'ch%d' % ch)
        os.makedirs(dst_raw, exist_ok=True)
        dst_tsv = os.path.join(dst_raw, 'inst_full.tsv')
        shutil.copyfile(out_tsv, dst_tsv)
        same = sha(out_tsv) == sha(dst_tsv)
        w('ch%d 已蒸馏进仓库 %s sha256 一致=%s' % (ch, dst_tsv, same))
    elif ok:
        w('ch%d !! 房间/实例数与既有普查不符 (%d,%d) != %s，不蒸馏'
          % (ch, nrooms, ninst, EXPECT[ch]))

w('ALL DONE')
log.close()
print('DONE')

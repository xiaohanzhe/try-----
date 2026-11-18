# -*- coding: utf-8 -*-
"""Mac 异地冷备：打包 → 上传 → 双端校验 → 解包 → 回验 → 轮转保留。

设计要点（都是踩过的）：
  * 主判据用 **hash 多重集**，不比路径 —— macOS 的 NFD 归一化会影响中文名，
    但与内容是否无损无关；路径集合另作次判据只报不判。
  * 刻意不备 `.git`（远端已是异地副本）与 `diag_frames*`（可重生成的诊断截图）。
  * 远端命令一律纯 ASCII，避免 PowerShell / GBK 编码把引号吃掉。
  * 本脚本用 subprocess 的 argv 形式调 ssh（不经 PowerShell 解析），引号可控。

用法：
    python mac_backup.py                # 正常跑
    python mac_backup.py --keep 7       # 远端保留最近 7 份
    python mac_backup.py --no-extract   # 只上传不删除远端旧份
"""
from __future__ import print_function

import argparse
import collections
import datetime
import hashlib
import json
import os
import subprocess
import sys
import tarfile

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))

HOST = os.environ.get('RALSEI_MAC_HOST', 'sunyanli@192.168.1.30')
KEY = os.path.expanduser(r'~\.ssh\ralsei_mac')
REMOTE_ROOT = 'RalseiBackup'
SSH = r'C:\Windows\System32\OpenSSH\ssh.exe'
SCP = r'C:\Windows\System32\OpenSSH\scp.exe'
TMPDIR = r'D:\_tmp'

ROOTS = [
    'ralsei_pet',
    '.workbuddy/memory',
    'code-quality-audit/regress',
]
# 每轮的报告目录也带一份（目录不存在就跳过）
ROUND_GLOB_PARENT = 'code-quality-audit'

SKIP_DIRS = {'__pycache__', 'diag_frames', 'diag_frames2', '_out',
             '.pytest_cache', '.mypy_cache', 'node_modules'}
SKIP_EXT = {'.pyc', '.pyo'}


def log(msg):
    print(msg)
    sys.stdout.flush()


def ssh_run(remote_cmd, timeout=600):
    """跑远端命令，返回 (rc, stdout+stderr)。argv 形式，不经 PowerShell 解析。"""
    argv = [SSH, '-i', KEY, '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=accept-new',
            '-o', 'ConnectTimeout=10', '-o', 'LogLevel=ERROR',
            HOST, remote_cmd]
    try:
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, 'TIMEOUT'
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def scp_to(local, remote, timeout=1800):
    argv = [SCP, '-i', KEY, '-o', 'BatchMode=yes', '-o', 'LogLevel=ERROR',
            local, '%s:%s' % (HOST, remote)]
    try:
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, 'TIMEOUT'
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def scp_from(remote, local, timeout=600):
    argv = [SCP, '-i', KEY, '-o', 'BatchMode=yes', '-o', 'LogLevel=ERROR',
            '%s:%s' % (HOST, remote), local]
    try:
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, 'TIMEOUT'
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def build_pack(out_path, round_dirs):
    n_file = n_bytes = 0
    roots = list(ROOTS) + list(round_dirs)
    with tarfile.open(out_path, 'w:gz', compresslevel=6) as tf:
        for rel in roots:
            base = os.path.join(REPO, rel)
            if not os.path.isdir(base):
                log('  [skip] 缺目录 %s' % rel)
                continue
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for f in sorted(files):
                    if os.path.splitext(f)[1].lower() in SKIP_EXT:
                        continue
                    full = os.path.join(root, f)
                    arc = os.path.relpath(full, REPO).replace('\\', '/')
                    try:
                        tf.add(full, arcname=arc, recursive=False)
                        n_file += 1
                        n_bytes += os.path.getsize(full)
                    except OSError:
                        pass
    return n_file, n_bytes


def tar_hash_multiset(tar_path):
    out = collections.Counter()
    with tarfile.open(tar_path, 'r:gz') as tf:
        for m in tf:
            if not m.isfile():
                continue
            fp = tf.extractfile(m)
            h = hashlib.sha256()
            for chunk in iter(lambda: fp.read(1 << 20), b''):
                h.update(chunk)
            out[h.hexdigest()] += 1
    return out


def parse_manifest(path):
    hashes = collections.Counter()
    paths = set()
    with open(path, 'r', encoding='utf-8', errors='replace') as fp:
        for line in fp:
            line = line.rstrip('\n')
            if not line.strip():
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            h, p = parts
            if p.startswith('./'):
                p = p[2:]
            hashes[h] += 1
            paths.add(p)
    return hashes, paths


def pick_round_dirs(limit=2):
    """本轮的审计目录也带一份：按目录名里的**数字**排序取末尾。

    ★ 不能按字符串排序：'第98轮…' > '第196轮…'（字典序），会把陈旧轮次当最新。
    """
    import re
    parent = os.path.join(REPO, ROUND_GLOB_PARENT)
    if not os.path.isdir(parent):
        return []
    got = []
    for d in os.listdir(parent):
        if not os.path.isdir(os.path.join(parent, d)):
            continue
        m = re.match(r'^第(\d+)轮', d)
        if m:
            got.append((int(m.group(1)), d))
    got.sort()
    return ['%s/%s' % (ROUND_GLOB_PARENT, d) for _, d in got[-limit:]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keep', type=int, default=7, help='远端保留最近几份')
    ap.add_argument('--rounds', type=int, default=2, help='附带最近几轮的审计目录')
    ap.add_argument('--no-extract', action='store_true', help='不删除远端旧份')
    ap.add_argument('--json', default='', help='把结果写成 json 到该路径')
    args = ap.parse_args()

    if not os.path.isfile(KEY):
        log('[FATAL] 找不到密钥 %s' % KEY)
        return 2
    if not os.path.isdir(TMPDIR):
        os.makedirs(TMPDIR)

    today = datetime.date.today().strftime('%Y-%m-%d')
    stamp = datetime.date.today().strftime('%Y%m%d')
    pack_name = 'ralsei_backup_%s.tar.gz' % stamp
    local_pack = os.path.join(TMPDIR, pack_name)
    remote_dir = '%s/%s' % (REMOTE_ROOT, today)
    remote_pack_dir = '%s/_packs' % REMOTE_ROOT
    remote_pack = '%s/%s' % (remote_pack_dir, pack_name)

    result = {'date': today, 'host': HOST, 'ok': False, 'steps': {}}

    log('== [1/8] 打包 ==')
    round_dirs = pick_round_dirs(args.rounds)
    n_file, n_bytes = build_pack(local_pack, round_dirs)
    size = os.path.getsize(local_pack)
    sha = sha256_file(local_pack)
    log('  files=%d  raw=%.1f MB  packed=%.1f MB' % (n_file, n_bytes / 1048576.0, size / 1048576.0))
    log('  sha256=%s' % sha)
    log('  含审计目录=%s' % (round_dirs or '无'))
    result['steps']['pack'] = {'files': n_file, 'packed_mb': round(size / 1048576.0, 1)}

    log('== [2/8] 远端建目录 ==')
    # ★ 归档放 _packs/，解包树放 <date>/ —— 两者不能同目录，否则归档自己会被算进清单
    rc, out = ssh_run('mkdir -p ~/%s ~/%s && echo MKDIR_OK' % (remote_dir, remote_pack_dir))
    if rc != 0 or 'MKDIR_OK' not in out:
        log('  [FATAL] %s' % out.strip()[:300])
        return 3

    log('== [3/8] 上传 ==')
    rc, out = scp_to(local_pack, remote_pack)
    if rc != 0:
        log('  [FATAL] scp 失败: %s' % out.strip()[:300])
        return 4
    log('  scp ok')

    log('== [4/8] 传输完整性（远端 shasum） ==')
    rc, out = ssh_run('shasum -a 256 ~/%s' % remote_pack)
    if rc != 0:
        log('  [FATAL] shasum 失败: %s' % out.strip()[:300])
        return 5
    remote_sha = out.split()[0] if out.split() else ''
    if remote_sha != sha:
        log('  [FATAL] 传输损坏  local=%s remote=%s' % (sha, remote_sha))
        return 6
    log('  一致: %s' % remote_sha)
    result['steps']['transfer'] = {'sha256': sha, 'match': True}

    log('== [5/8] 解包 ==')
    # ★ 必须先清空目标目录：tar 是覆盖式合并，上一份多出来的文件会残留，
    #   混进清单后表现为"远端多 36 个文件"（实测踩过）。
    rc, out = ssh_run('rm -rf ~/%s && mkdir -p ~/%s && cd ~/%s && tar -xzf ~/%s && echo EXTRACT_OK'
                      % (remote_dir, remote_dir, remote_dir, remote_pack))
    if rc != 0 or 'EXTRACT_OK' not in out:
        log('  [FATAL] 解包失败: %s' % out.strip()[:300])
        return 7
    log('  解包 ok（目标目录已先清空）')

    log('== [6/8] 远端生成全量 hash 清单 ==')
    man_name = 'manifest_%s.txt' % stamp
    cmd = ('cd ~/%s && find . -type f -print0 | xargs -0 shasum -a 256 > ~/%s/%s '
           '&& wc -l < ~/%s/%s' % (remote_dir, REMOTE_ROOT, man_name, REMOTE_ROOT, man_name))
    rc, out = ssh_run(cmd)
    if rc != 0:
        log('  [FATAL] 清单失败: %s' % out.strip()[:300])
        return 8
    n_remote = int(out.split()[-1]) if out.split() else 0
    log('  远端文件数=%d' % n_remote)

    log('== [7/8] 取回清单并比对（主判据=hash 多重集） ==')
    local_man = os.path.join(TMPDIR, man_name)
    rc, out = scp_from('~/%s/%s' % (REMOTE_ROOT, man_name), local_man)
    if rc != 0:
        log('  [FATAL] 取清单失败: %s' % out.strip()[:300])
        return 9
    local_hashes = tar_hash_multiset(local_pack)
    remote_hashes, remote_paths = parse_manifest(local_man)
    diff = (local_hashes - remote_hashes) + (remote_hashes - local_hashes)
    n_diff = sum(diff.values())
    log('  本地 tar=%d 远端清单=%d 差异=%d' % (sum(local_hashes.values()),
                                              sum(remote_hashes.values()), n_diff))
    result['steps']['verify'] = {'n_files': n_remote, 'n_diff': n_diff}
    if n_diff != 0:
        log('  [FAIL] 副本不一致（不是传输问题就是解包问题）')
        result['ok'] = False
        _emit(args, result)
        return 10
    log('  IDENTICAL（异地副本逐字节无损）')

    if not args.no_extract:
        log('== [8/8] 轮转，只保留最近 %d 份 ==' % args.keep)
        # 目录名是 YYYY-MM-DD，字典序即时间序；tail -n +N 丢掉最新的 N-1 个
        # ★ 用 `ls -1d 20*`（不带斜杠）而不是 `20*/` + sed —— `$#` 是 shell 特殊变量，
        #   写 `sed "s#/$##"` 会被展开成 `s#/0#`，报 unterminated substitute（实测踩过）。
        cmd = ('cd ~/%s && ls -1d 20* 2>/dev/null | sort -r | tail -n +%d '
               '| xargs -I{} rm -rf {} ; '
               'cd ~/%s && ls -1t *.tar.gz 2>/dev/null | tail -n +%d '
               '| xargs -I{} rm -f {} ; '
               'echo "dirs=$(ls -1d ~/%s/20* 2>/dev/null | wc -l) '
               'packs=$(ls -1 ~/%s | wc -l)"'
               % (REMOTE_ROOT, args.keep + 1, remote_pack_dir, args.keep + 1,
                  REMOTE_ROOT, remote_pack_dir))
        rc, out = ssh_run(cmd)
        log('  远端: %s' % out.strip().replace('\n', ' '))
        result['steps']['rotate'] = {'raw': out.strip()}
    else:
        log('== [8/8] 跳过轮转 ==')

    try:
        os.remove(local_pack)
        os.remove(local_man)
    except OSError:
        pass

    result['ok'] = True
    log('')
    log('=== BACKUP_OK  %s  %d 文件  %.1f MB  sha=%s ===' % (today, n_file, size / 1048576.0, sha[:12]))
    _emit(args, result)
    return 0


def _emit(args, result):
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as fp:
            json.dump(result, fp, ensure_ascii=False, indent=2)
        log('json -> %s' % args.json)


if __name__ == '__main__':
    sys.exit(main())

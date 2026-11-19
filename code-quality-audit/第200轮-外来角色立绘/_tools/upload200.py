# -*- coding: utf-8 -*-
"""第200轮 · 把帧素材 + 任务书 + 渲染脚本送上 Mac，跑完把拼版取回（本地只读源）。

分工：**Mac 渲染，人眼把关，本地只登记**。
  * 上传 = 一个 tar（458 个 PNG 共 0.36 MB，体积不值得逐文件 scp）
  * 远端命令**纯 ASCII**（GBK / ZHS 编码会把引号吃掉，`mac_backup.py` 踩过）
  * 取回后写 `_evidence/sheets/`，sha1 双端比对（独立解码，能查出坏帧）

用法：
    python upload200.py            # 上传 + 渲染 + 取回
    python upload200.py --render   # 只重跑渲染 + 取回（素材已在远端）
"""
from __future__ import print_function

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
SPR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites')
EVI = os.path.join(ROUND, '_evidence')
PLAN = os.path.join(EVI, 'sheet_plan.json')
LOCAL_SHEETS = os.path.join(EVI, 'sheets')
TMP = r'D:\_tmp\sheets200'
TAR = os.path.join(TMP, 'sheetsrc.tar')

HOST = os.environ.get('RALSEI_MAC_HOST', 'sunyanli@192.168.1.30')
KEY = os.path.expanduser(r'~\.ssh\ralsei_mac')
SSH = r'C:\Windows\System32\OpenSSH\ssh.exe'
SCP = r'C:\Windows\System32\OpenSSH\scp.exe'
PY = '~/ralsei-venv/bin/python'


def log(m):
    print(m)
    sys.stdout.flush()


def ssh_run(cmd, timeout=600):
    argv = [SSH, '-i', KEY, '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=accept-new',
            '-o', 'ConnectTimeout=10', '-o', 'LogLevel=ERROR', HOST, cmd]
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def scp_to(local, remote, timeout=900):
    argv = [SCP, '-i', KEY, '-o', 'BatchMode=yes', '-o', 'LogLevel=ERROR',
            local, '%s:%s' % (HOST, remote)]
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def scp_from(remote, local, timeout=900):
    argv = [SCP, '-i', KEY, '-o', 'BatchMode=yes', '-o', 'LogLevel=ERROR',
            '-r', '%s:%s' % (HOST, remote), local]
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def sha1(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 16), b''):
            h.update(b)
    return h.hexdigest()


def build_tar(plan):
    """按 `<work>/<file>` 布局打包，远端直接解到 ~/sheetsrc。"""
    if not os.path.isdir(TMP):
        os.makedirs(TMP)
    n = 0
    # ★ filter 去掉非 ASCII 之外的噪音，但保留路径；决定性的是 arcname 自己拼
    with tarfile.open(TAR, 'w') as tf:
        for it in plan:
            w = it['work']
            for fn in it['files']:
                src = os.path.join(SPR, w, fn)
                if not os.path.isfile(src):
                    log('  [缺] %s/%s' % (w, fn))
                    continue
                ti = tf.gettarinfo(src, arcname='%s/%s' % (w, fn))
                ti.uid = ti.gid = 0
                ti.uname = ti.gname = ''
                with open(src, 'rb') as f:
                    tf.addfile(ti, f)
                n += 1
    log('打包 %d 个帧 → %s (%.2f MB)' % (n, TAR, os.path.getsize(TAR) / 1048576.0))
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--render', action='store_true')
    a = ap.parse_args()

    plan = json.loads(io.open(PLAN, encoding='utf-8').read())
    log('任务书 %d 条' % len(plan))

    if not a.render:
        n = build_tar(plan)
        if n == 0:
            log('没东西可传'); return 2
        rc, out = ssh_run('rm -rf ~/sheetsrc ~/sheets; mkdir -p ~/sheetsrc')
        log('远端清场 rc=%d %s' % (rc, out.strip()))
        if rc != 0:
            return 3
        rc, out = scp_to(TAR, 'sheetsrc.tar')
        log('scp tar rc=%d %s' % (rc, out.strip()))
        if rc != 0:
            return 3
        rc, out = ssh_run('cd ~ && tar xf sheetsrc.tar -C sheetsrc && '
                          'find ~/sheetsrc -type f | wc -l')
        log('解包 rc=%d 远端文件数=%s' % (rc, out.strip()))
        if rc != 0:
            return 3
        for src, dst in ((PLAN, 'sheet_plan.json'),
                         (os.path.join(HERE, 'sheet_mac200.py'), 'sheet_mac200.py')):
            rc, out = scp_to(src, dst)
            log('scp %s rc=%d %s' % (os.path.basename(src), rc, out.strip()))
            if rc != 0:
                return 4

    rc, out = ssh_run('%s ~/sheet_mac200.py' % PY, timeout=900)
    log('渲染 rc=%d\n%s' % (rc, out))
    if rc != 0:
        return 5

    rc, out = ssh_run('ls ~/sheets | wc -l; cat ~/sheets/_index.json | shasum')
    log('远端产物: %s' % out.strip())

    if os.path.isdir(LOCAL_SHEETS):
        for fn in os.listdir(LOCAL_SHEETS):
            os.remove(os.path.join(LOCAL_SHEETS, fn))
    else:
        os.makedirs(LOCAL_SHEETS)
    rc, out = scp_from('sheets', LOCAL_SHEETS)
    log('取回 rc=%d %s' % (rc, out.strip()))
    if rc != 0:
        return 6

    # ★ scp -r 到**已存在**的目标目录会多套一层 `sheets/sheets`；拍平后再比对
    local_dir = LOCAL_SHEETS
    nest = os.path.join(LOCAL_SHEETS, 'sheets')
    if os.path.isdir(nest):
        for fn in os.listdir(nest):
            os.replace(os.path.join(nest, fn), os.path.join(LOCAL_SHEETS, fn))
        os.rmdir(nest)
    idx_p = os.path.join(local_dir, '_index.json')
    if not os.path.isfile(idx_p):
        log('[FAIL] 取回后没找到 _index.json'); return 7

    idx = json.loads(io.open(idx_p, encoding='utf-8').read())
    same = diff = miss = 0
    for cid, meta in idx.items():
        p = os.path.join(local_dir, meta['sheet'])
        if not os.path.isfile(p):
            miss += 1
            log('  [缺] %s' % meta['sheet'])
            continue
        if sha1(p) == meta['sha1']:
            same += 1
        else:
            diff += 1
            log('  [改] %s' % meta['sheet'])
    log('拼版 %d 张：一致 %d · 不一致 %d · 缺 %d' % (len(idx), same, diff, miss))
    log('本地目录 %s' % local_dir)
    return 0 if (diff == 0 and miss == 0) else 8


if __name__ == '__main__':
    sys.exit(main())

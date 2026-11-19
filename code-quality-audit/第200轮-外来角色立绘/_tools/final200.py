# -*- coding: utf-8 -*-
"""第200轮 · 把 54 人的正面首帧送上 Mac 拼总览图，取回 `_evidence/final200.png`。"""
from __future__ import print_function

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
DR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites', 'dr')
EVI = os.path.join(ROUND, '_evidence')
TAR = r'D:\_tmp\final200.tar'
PLAN = os.path.join(EVI, 'final_plan.json')

HOST = os.environ.get('RALSEI_MAC_HOST', 'sunyanli@192.168.1.30')
KEY = os.path.expanduser(r'~\.ssh\ralsei_mac')
SSH = r'C:\Windows\System32\OpenSSH\ssh.exe'
SCP = r'C:\Windows\System32\OpenSSH\scp.exe'
PY = '~/ralsei-venv/bin/python'


def sh(argv, timeout=600):
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def ssh(cmd):
    return sh([SSH, '-i', KEY, '-o', 'BatchMode=yes',
               '-o', 'StrictHostKeyChecking=accept-new',
               '-o', 'ConnectTimeout=10', '-o', 'LogLevel=ERROR', HOST, cmd])


def main():
    sys.path.insert(0, HERE)
    import pick200 as P

    man = json.loads(io.open(os.path.join(DR, '_npc_frames.json'),
                             encoding='utf-8').read())
    plan = []
    for nid in sorted(P.MAP):
        e = man['characters'][nid]
        f = e['frames']['down'][0]['f']
        plan.append({'id': nid, 'work': P.MAP[nid]['work'], 'file': f})
    with io.open(PLAN, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(plan, ensure_ascii=False, indent=1))
    print('总览任务 %d 人' % len(plan))

    if not os.path.isdir(os.path.dirname(TAR)):
        os.makedirs(os.path.dirname(TAR))
    n = 0
    with tarfile.open(TAR, 'w') as tf:
        for it in plan:
            src = os.path.join(DR, it['id'], it['file'])
            if not os.path.isfile(src):
                print('  [缺] %s' % src)
                continue
            ti = tf.gettarinfo(src, arcname='%s/%s_%s'
                               % (it['work'], it['id'], it['file']))
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = ''
            with open(src, 'rb') as fh:
                tf.addfile(ti, fh)
            n += 1
    print('打包 %d 个 PNG (%.1f KB)' % (n, os.path.getsize(TAR) / 1024.0))

    rc, o = ssh('rm -rf ~/final; mkdir -p ~/final')
    if rc:
        print('清场失败 %s' % o.strip()); return 2
    rc, o = sh([SCP, '-i', KEY, '-o', 'BatchMode=yes', '-o', 'LogLevel=ERROR',
                TAR, '%s:final200.tar' % HOST])
    if rc:
        print('scp 失败 %s' % o.strip()); return 2
    rc, o = ssh('cd ~ && tar xf final200.tar -C final && '
                'find ~/final -type f | wc -l')
    print('解包 rc=%d 文件数=%s' % (rc, o.strip()))
    for l, r in ((PLAN, 'final_plan.json'),
                 (os.path.join(HERE, 'final_mac200.py'), 'final_mac200.py')):
        rc, o = sh([SCP, '-i', KEY, '-o', 'BatchMode=yes', '-o', 'LogLevel=ERROR',
                    l, '%s:%s' % (HOST, r)])
        if rc:
            print('scp %s 失败 %s' % (r, o.strip())); return 2
    rc, o = ssh('%s ~/final_mac200.py' % PY)
    print('拼图 rc=%d\n%s' % (rc, o))
    if rc:
        return 3
    dst = os.path.join(EVI, 'final200.png')
    rc, o = sh([SCP, '-i', KEY, '-o', 'BatchMode=yes', '-o', 'LogLevel=ERROR',
                '%s:final/_overview.png' % HOST, dst])
    print('取回 rc=%d %s' % (rc, o.strip()))
    print('→ %s  %d 字节' % (dst, os.path.getsize(dst)))
    return 0 if rc == 0 else 4


if __name__ == '__main__':
    sys.exit(main())

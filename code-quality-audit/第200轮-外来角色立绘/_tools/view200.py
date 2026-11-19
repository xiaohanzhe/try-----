# -*- coding: utf-8 -*-
"""第200轮 · 看图分页（通用）：把一批单张图合成 2x2「看图页」送 Mac 渲染后取回。

两种用途共用一套逻辑（避免抄第二份脚本）：
  * `--src sheets`  走路帧拼版（56 张 → 14 页）
  * `--src cell`    OneShot 切格页（18 张 → 5 页，超大页单独一页）

★ 单页过大（>1300 像素）的图**单独成页**：2x2 会把它的尺寸放大到别人身上，
  整页被模型降采样后小图就糊了。
"""
from __future__ import print_function

import argparse
import io
import json
import os
import subprocess
import sys

from PIL import Image

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EVI = os.path.join(ROUND, '_evidence')

HOST = os.environ.get('RALSEI_MAC_HOST', 'sunyanli@192.168.1.30')
KEY = os.path.expanduser(r'~\.ssh\ralsei_mac')
SSH = r'C:\Windows\System32\OpenSSH\ssh.exe'
SCP = r'C:\Windows\System32\OpenSSH\scp.exe'
PY = '~/ralsei-venv/bin/python'
GROUP = 4


def sh(argv, timeout=600):
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def ssh(cmd):
    return sh([SSH, '-i', KEY, '-o', 'BatchMode=yes',
               '-o', 'StrictHostKeyChecking=accept-new',
               '-o', 'ConnectTimeout=10', '-o', 'LogLevel=ERROR', HOST, cmd])


def scp_to(a, b):
    return sh([SCP, '-i', KEY, '-o', 'BatchMode=yes', '-o', 'LogLevel=ERROR',
               a, '%s:%s' % (HOST, b)])


def scp_from(a, b):
    return sh([SCP, '-i', KEY, '-o', 'BatchMode=yes', '-o', 'LogLevel=ERROR',
               '-r', '%s:%s' % (HOST, a), b])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', choices=('sheets', 'cell'), default='sheets')
    a = ap.parse_args()
    local_src = os.path.join(EVI, 'sheets' if a.src == 'sheets' else 'sheets_cell')
    local_out = os.path.join(EVI, 'sheets_view' if a.src == 'sheets'
                             else 'sheets_cell_view')
    plan_l = os.path.join(EVI, 'view_plan_%s.json' % a.src)
    cfg_l = os.path.join(EVI, 'view_cfg_%s.json' % a.src)

    ids = sorted(f[:-4] for f in os.listdir(local_src)
                 if f.endswith('.png') and not f.startswith('_'))
    if a.src == 'sheets':          # 按作品交错，免得同名角色相邻混淆
        order = {'ut': 0, 'ot': 1, 'hy': 2, 'os': 3}
        ids.sort(key=lambda s: (order.get(s.split('_')[0], 9), s))
        groups = [ids[i:i + GROUP] for i in range(0, len(ids), GROUP)]
    else:
        big, small = [], []
        for i in ids:
            w, h = Image.open(os.path.join(local_src, i + '.png')).size
            (big if max(w, h) > 1300 else small).append(i)
        groups = [[b] for b in big]
        groups += [small[i:i + GROUP] for i in range(0, len(small), GROUP)]

    with io.open(plan_l, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(groups, ensure_ascii=False, indent=1))
    print('%s：%d 张 → %d 页' % (a.src, len(ids), len(groups)))
    for n, g in enumerate(groups):
        print('  p%02d  %s' % (n + 1, ','.join(g)))

    sub = {'sheets': ('sheets', '_view', 'view_plan.json'),
           'cell': ('sheets/_cell', '_view', 'cell_view_plan.json')}[a.src]
    with io.open(cfg_l, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps({'src': '~/' + sub[0], 'out': sub[1],
                            'plan': '~/' + sub[2]}, ensure_ascii=False, indent=1))
    for l, r in ((cfg_l, 'view_cfg.json'), (plan_l, sub[2]),
                 (os.path.join(HERE, 'sheetview_mac200.py'), 'sheetview_mac200.py')):
        rc, o = scp_to(l, r)
        if rc:
            print('scp %s 失败 %s' % (r, o.strip()))
            return 2
    rc, o = ssh('%s ~/sheetview_mac200.py' % PY)
    print('合成 rc=%d\n%s' % (rc, o))
    if rc:
        return 3

    if os.path.isdir(local_out):
        for fn in os.listdir(local_out):
            os.remove(os.path.join(local_out, fn))
    else:
        os.makedirs(local_out)
    remote = 'sheets/_view' if a.src == 'sheets' else 'sheets/_cell/_view'
    rc, o = scp_from(remote, local_out)
    print('取回 rc=%d %s' % (rc, o.strip()))
    nest = os.path.join(local_out, '_view')
    if os.path.isdir(nest):
        for fn in os.listdir(nest):
            os.replace(os.path.join(nest, fn), os.path.join(local_out, fn))
        os.rmdir(nest)
    n = len([f for f in os.listdir(local_out) if f.endswith('.png')])
    print('本地看图页 %d 张（期望 %d）→ %s' % (n, len(groups), local_out))
    return 0 if n == len(groups) else 4


if __name__ == '__main__':
    sys.exit(main())

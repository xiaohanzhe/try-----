# -*- coding: utf-8 -*-
"""第200轮 · 选图 → 送 Mac 切格 → 取回（本地只读源）。"""
from __future__ import print_function

import io
import json
import os
import subprocess
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
SPR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites')
EVI = os.path.join(ROUND, '_evidence')
PLAN = os.path.join(EVI, 'sheet_plan.json')
CELLPLAN = os.path.join(EVI, 'cell_plan.json')
CELLOUT = os.path.join(EVI, 'sheets_cell')

HOST = os.environ.get('RALSEI_MAC_HOST', 'sunyanli@192.168.1.30')
KEY = os.path.expanduser(r'~\.ssh\ralsei_mac')
SSH = r'C:\Windows\System32\OpenSSH\ssh.exe'
SCP = r'C:\Windows\System32\OpenSSH\scp.exe'
PY = '~/ralsei-venv/bin/python'


def sh(argv, timeout=900):
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


def pick():
    """每人挑**一张**表来切。优先能切成 4x4 的画布；排除 292x293 这类对话头像。"""
    from PIL import Image
    plan = json.loads(io.open(PLAN, encoding='utf-8').read())
    out = []
    for it in plan:
        if not it['id'].startswith('os_'):
            continue
        best = None
        for fn in it['files']:
            p = os.path.join(SPR, it['work'], fn)
            if not os.path.isfile(p):
                continue
            w, h = Image.open(p).size
            # 对话头像（**近正方形的大图**）直接排除：它不是走路帧，切了也没方向。
            # ★ 判 `min(w,h) > 200` 而不是 `w == h`：`dialog_smiling.png` 是
            #   292x293，**差一个像素**，写成 `w == h` 就漏过去了（实测踩到）。
            if min(w, h) > 200:
                continue
            can4 = (w % 4 == 0 and h % 4 == 0 and w >= 96 and h >= 128)
            score = (1 if can4 else 0, w * h)
            if best is None or score > best[0]:
                best = (score, fn, w, h)
        if best is None:                     # 全被排除 ⇒ 退回最小那张
            for fn in it['files']:
                p = os.path.join(SPR, it['work'], fn)
                if not os.path.isfile(p):
                    continue
                w, h = Image.open(p).size
                if best is None or w * h < best[0][1]:
                    best = ((0, w * h), fn, w, h)
        if best:
            out.append({'id': it['id'], 'work': it['work'], 'file': best[1],
                        'w': best[2], 'h': best[3]})
    return out


def main():
    picks = pick()
    with io.open(CELLPLAN, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(picks, ensure_ascii=False, indent=1))
    print('切格任务 %d 条' % len(picks))
    for p in picks:
        print('  %-22s %-28s %dx%d' % (p['id'], p['file'], p['w'], p['h']))

    rc, o = scp_to(CELLPLAN, 'cell_plan.json')
    print('scp plan rc=%d %s' % (rc, o.strip()))
    if rc:
        return 2
    rc, o = scp_to(os.path.join(HERE, 'explode_mac200.py'), 'explode_mac200.py')
    if rc:
        return 2
    rc, o = ssh('%s ~/explode_mac200.py' % PY)
    print('切格 rc=%d\n%s' % (rc, o))
    if rc:
        return 3

    if os.path.isdir(CELLOUT):
        for fn in os.listdir(CELLOUT):
            os.remove(os.path.join(CELLOUT, fn))
    else:
        os.makedirs(CELLOUT)
    rc, o = scp_from('sheets/_cell', CELLOUT)
    print('取回 rc=%d %s' % (rc, o.strip()))
    nest = os.path.join(CELLOUT, '_cell')
    if os.path.isdir(nest):
        for fn in os.listdir(nest):
            os.replace(os.path.join(nest, fn), os.path.join(CELLOUT, fn))
        os.rmdir(nest)
    n = len([f for f in os.listdir(CELLOUT) if f.endswith('.png')])
    print('本地切图 %d 张 → %s' % (n, CELLOUT))
    return 0 if n == len(picks) else 4


if __name__ == '__main__':
    sys.exit(main())

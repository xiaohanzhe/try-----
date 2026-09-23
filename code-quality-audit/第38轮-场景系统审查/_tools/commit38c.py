# -*- coding: utf-8 -*-
"""第 38 轮续：提交 + 尝试推送一次（严格：先看 numstat 的 deletions）。"""
import os
import subprocess
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MSG = r'E:\Download\_tmp\commit_msg_38c.txt'
PROXY = 'http://127.0.0.1:7897'
CA = r'E:/Download/_tmp/win_ca.pem'

raw = open(MSG, 'rb').read()
print('msg bytes =', len(raw), 'has_bom =', raw[:3] == b'\xef\xbb\xbf')
if raw[:3] == b'\xef\xbb\xbf':
    sys.exit(2)


def run(a, **kw):
    r = subprocess.run(a, cwd=ROOT, capture_output=True, **kw)
    return (r.returncode, r.stdout.decode('utf-8', 'replace'),
            r.stderr.decode('utf-8', 'replace'))


rc, so, se = run(['git', 'add', '-A'])
print('add rc =', rc)
rc, so, se = run(['git', 'diff', '--cached', '--numstat'])
tot_i = tot_d = 0
files = 0
for ln in so.splitlines():
    p = ln.split('\t')
    if len(p) >= 3:
        files += 1
        if p[0].isdigit():
            tot_i += int(p[0])
        if p[1].isdigit():
            tot_d += int(p[1])
print('staged: files=%d  +%d  -%d' % (files, tot_i, tot_d))
if tot_d > 1000:
    print('!!! 停手：deletions > 1000 !!!')
    sys.exit(2)

rc, so, se = run(['git', 'commit', '-F', MSG])
print('commit rc =', rc, so[:300], se[:300])
rc, so, se = run(['git', 'log', '--oneline', '-1'])
print('HEAD =', so.strip())

try:
    rc, so, se = run(['git', '-c', 'http.proxy=' + PROXY,
                      '-c', 'https.proxy=' + PROXY,
                      '-c', 'http.sslBackend=openssl',
                      '-c', 'http.sslCAInfo=' + CA,
                      '-c', 'http.version=HTTP/1.1', 'push', 'origin', 'main'],
                     timeout=150)
    print('push rc =', rc)
    print('push out:', so[:500])
    print('push err:', se[:500])
except subprocess.TimeoutExpired:
    print('push TIMEOUT(150s) —— 按铁律 7.0 不重试，如实报告')
except Exception as e:
    print('push 异常:', type(e).__name__, e)

# -*- coding: utf-8 -*-
"""第 38 轮开局：提交 + 尝试推送一次（消息文件由外部写好，本脚本不再自己写）。"""
import os
import subprocess
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MSG = r'E:\Download\_tmp\commit_msg_38a.txt'
PROXY = 'http://127.0.0.1:7897'
CA = r'E:/Download/_tmp/win_ca.pem'

if not os.path.isfile(MSG):
    print('消息文件不存在:', MSG)
    sys.exit(2)
raw = open(MSG, 'rb').read()
print('msg bytes =', len(raw), 'has_bom =', raw[:3] == b'\xef\xbb\xbf')
if raw[:3] == b'\xef\xbb\xbf':
    print('!!! 有 BOM，停手 !!!')
    sys.exit(2)


def run(args, **kw):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, **kw)
    return (r.returncode, r.stdout.decode('utf-8', 'replace'),
            r.stderr.decode('utf-8', 'replace'))


rc, so, se = run(['git', 'add', '-A'])
print('add rc =', rc, se[:300])

rc, so, se = run(['git', 'diff', '--cached', '--numstat'])
print('--- staged numstat ---')
print(so if so.strip() else '(空)')
tot = 0
for ln in so.splitlines():
    p = ln.split('\t')
    if len(p) >= 2 and p[1].isdigit():
        tot += int(p[1])
print('total deletions =', tot)
if tot > 1000:
    print('!!! 停手：deletions > 1000 !!!')
    sys.exit(2)

rc, so, se = run(['git', 'commit', '-F', MSG])
print('commit rc =', rc)
print(so[:500], se[:500])
rc, so, se = run(['git', 'log', '--oneline', '-1'])
print('HEAD =', so.strip())

try:
    rc, so, se = run(['git', '-c', 'http.proxy=' + PROXY,
                      '-c', 'https.proxy=' + PROXY,
                      '-c', 'http.sslBackend=openssl',
                      '-c', 'http.sslCAInfo=' + CA,
                      '-c', 'http.version=HTTP/1.1', 'push', 'origin', 'main'],
                     timeout=180)
    print('push rc =', rc)
    print('push out:', so[:800])
    print('push err:', se[:800])
except subprocess.TimeoutExpired:
    print('push TIMEOUT(180s) —— 按铁律 7.0：不重试，直接如实报告')
except Exception as e:
    print('push 异常:', type(e).__name__, e)

rc, so, se = run(['git', 'log', '--oneline', '-4'])
print('--- 最近 4 条 ---')
print(so)

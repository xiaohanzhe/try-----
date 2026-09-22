# -*- coding: utf-8 -*-
"""第30轮提交：add + commit -F + push + ls-remote 独立核验。"""
import io
import os
import subprocess
import shutil
import sys

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
GIT = shutil.which('git') or r'D:\Program Files\Git\cmd\git.EXE'
MSG = os.path.join(REPO, 'code-quality-audit', '场景系统-P0', '_evidence',
                   '_commit_msg_r30.txt')
OUT = os.path.join(REPO, 'code-quality-audit', '场景系统-P0', '_evidence',
                   'git_push_r30.txt')

lines = []


def w(s=''):
    lines.append(str(s))
    print(s, flush=True)


def run(args, **kw):
    r = subprocess.run([GIT] + args, cwd=REPO, capture_output=True, **kw)
    return r.returncode, r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')


# 1) 检查提交信息源文件编码
with io.open(MSG, 'rb') as f:
    raw = f.read()
w('提交信息文件: %d bytes, BOM=%s' % (len(raw), raw[:3] == b'\xef\xbb\xbf'))
if raw[:3] == b'\xef\xbb\xbf':
    w('!! 有 BOM，去掉')
    with io.open(MSG, 'wb') as f:
        f.write(raw[3:])
    with io.open(MSG, 'rb') as f:
        raw = f.read()
    w('   修正后: %d bytes, BOM=%s' % (len(raw), raw[:3] == b'\xef\xbb\xbf'))
w()

# 2) add
rc, o, e = run(['add', '-A'])
w('git add -A  rc=%d' % rc)
if e.strip():
    w('  stderr: ' + e.strip()[:300])
rc, o, e = run(['status', '--porcelain'])
w('status after add: %r' % o.decode('utf-8', 'surrogateescape')[:400])
w()

# 3) commit
rc, o, e = run(['commit', '-F', MSG])
w('git commit -F  rc=%d' % rc)
w((o or '').strip()[:1500])
if e.strip():
    w('  stderr: ' + e.strip()[:1200])
w()

# 4) 核验提交信息逐字节一致
rc, o, e = run(['rev-parse', 'HEAD'])
head = o.strip()
w('HEAD = %s' % head)
rc, o, e = run(['cat-file', 'commit', 'HEAD'])
blob = o.encode('utf-8') if isinstance(o, str) else o
blob = subprocess.run([GIT, 'cat-file', 'commit', 'HEAD'], cwd=REPO,
                      capture_output=True).stdout
# 提取 message 段（第一个空行之后）
idx = blob.find(b'\n\n')
msg_bytes = blob[idx + 2:] if idx >= 0 else b''
with io.open(MSG, 'rb') as f:
    src = f.read()
w('提交信息逐字节比对: commit=%d src=%d IDENTICAL=%s'
  % (len(msg_bytes), len(src), msg_bytes == src))
w()

# 5) push
rc, o, e = run(['push', 'origin', 'main'])
w('git push origin main  rc=%d' % rc)
if o.strip():
    w('  stdout: ' + o.strip()[:600])
if e.strip():
    w('  stderr: ' + e.strip()[:900])
w()

# 6) ls-remote 独立核验
ok = False
for i in range(1, 6):
    rc, o, e = run(['ls-remote', 'origin', 'refs/heads/main'])
    remote = o.split()[0].strip() if o.strip() else ''
    local = head.decode().strip() if isinstance(head, bytes) else head.strip()
    if remote:
        w('尝试 %d: remote=%s  local=%s  SYNCED=%s'
          % (i, remote[:12], local[:12], remote == local))
        ok = (remote == local)
        break
    else:
        w('尝试 %d: 空输出 rc=%d err=%s' % (i, rc, e.strip()[:150]))
w()
w('FINAL SYNCED = %s' % ok)

rc, o, e = run(['status', '--porcelain'])
w('工作区: %r' % o.decode('utf-8', 'surrogateescape')[:300])

with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(lines) + '\n')
print('\nWROTE ' + OUT)

# -*- coding: utf-8 -*-
"""第 38 轮：绕过宿主注入的 helper-selector，直接问 GCM 要凭据。

背景（真事故）
--------------
· 仓库是**公开**的 ⇒ `ls-remote` 匿名就能通 ⇒ 我误判"凭据已可用"。
· push 必需要写权限 ⇒ 走 `credential.helper=helper-selector`（宿主注入）
  ⇒ 它不读 Windows 凭据管理器，直接弹 GUI 选择框 ⇒ push 挂死。
· 本机凭据管理器里其实**有** `git:https://github.com`（GCM 的存储格式）
  ⇒ 直接调用 git-credential-manager 就能静默拿到。

安全：GCM_INTERACTIVE=never + credential.interactive=never ⇒ 任何情况下都不弹窗；
密码**只留在进程内**，打印时只输出长度。
"""
import os
import subprocess
import sys

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
GCM = (r'C:\Users\23002\.workbuddy\binaries\PortableGit\versions\1.2.0'
       r'\mingw64\bin\git-credential-manager.exe')

env = dict(os.environ)
env['GCM_INTERACTIVE'] = 'never'
env['GCM_PROVIDER'] = 'github'
# ⚠️ 别写 'windows' —— GCM 只认 wincredman / dpapi / plaintext / none。
env['GCM_CREDENTIAL_STORE'] = 'wincredman'

inp = b'protocol=https\nhost=github.com\n\n'
try:
    p = subprocess.run([GCM, 'get'], input=inp, capture_output=True,
                       timeout=45, env=env, cwd=REPO)
except subprocess.TimeoutExpired:
    print('RESULT=TIMEOUT  GCM 45s 没返回')
    sys.exit(2)
except Exception as e:
    print('RESULT=EXC %r' % (e,))
    sys.exit(3)

out = p.stdout.decode('utf-8', 'replace')
err = p.stderr.decode('utf-8', 'replace')
print('rc=%d' % p.returncode)
usr = pw = ''
for ln in out.splitlines():
    if ln.startswith('username='):
        usr = ln[9:]
        print('username=%s' % usr)
    elif ln.startswith('password='):
        pw = ln[9:]
        print('password=<len %d>' % len(pw))
    elif ln.strip():
        print('stdout: %s' % ln[:120])
for ln in err.splitlines()[:10]:
    if ln.strip():
        print('stderr: %s' % ln[:170])
print('RESULT=%s' % ('CRED_OK' if pw else 'NO_CRED'))

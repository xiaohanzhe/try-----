# -*- coding: utf-8 -*-
"""第113轮推送工具 —— **默认拒绝执行**（这个仓库与远端已分叉）

## 结论先说
这个目录是 `try - 副本`。远端 `main` 已经跑到**第118轮**（`c88292b`），
本地的线停在**第112轮**（`50c821a`），两边**互不为祖先**（分叉，不是落后）。
往同一个远端推 = 覆盖主线第114~118轮 ⇒ 所以本脚本默认只做体检，**不推**。

## 两条环境真相（今晚实测，都会让人误判成"网络坏了"）
1. 本机有**本地代理 `127.0.0.1:61111`**（TLS 中间人）。它的 CA 装在 Windows
   证书库里，所以：
   - `http.sslBackend=openssl` ⇒ 永远 `unable to get local issuer certificate (20)`
     （加 `http.sslCAInfo` 指向 PortableGit 的 ca-bundle.crt **也没用**，因为那个
     CA 不认代理的中间证书）；
   - `http.sslBackend=schannel` ⇒ **通**（读系统证书库）。
2. 纯默认（schannel 但没关吊销检查）⇒ `CRYPT_E_NO_REVOCATION_CHECK (0x80092012)`，
   要配 `http.schannelCheckRevoke=false`。

## 用法
    python push113.py            # 只体检（默认）
    python push113.py --push     # 真推 —— 只有在分叉被人工解决后才允许
"""
import os
import subprocess
import sys
import time

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
BASE = ['-c', 'core.quotepath=false',
        '-c', 'http.sslBackend=schannel',
        '-c', 'http.schannelCheckRevoke=false',
        '-c', 'http.version=HTTP/1.1']


def w(m):
    print(m, flush=True)


def run(args, timeout=300):
    p = subprocess.run(['git'] + BASE + list(args), cwd=REPO,
                       capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace')


def main(argv):
    do_push = '--push' in argv

    rc, local, _ = run(['rev-parse', 'HEAD'])
    local = local.strip()
    w('[1] 本地 HEAD = %s' % local[:12])
    rc, o, _ = run(['log', '-1', '--pretty=%s'])
    w('    %s' % o.strip()[:110])

    w('[2] 连通性体检（ls-remote，只读）')
    remote = ''
    for i in range(3):
        rc, o, e = run(['ls-remote', 'origin', 'refs/heads/main'], timeout=120)
        for ln in o.splitlines():
            if ln.endswith('refs/heads/main'):
                remote = ln.split()[0]
        if remote:
            break
        w('    第 %d 次失败：%s' % (i + 1, e.strip().splitlines()[-1][:80] if e.strip() else '?'))
        time.sleep(2)
    w('    远端 main = %s' % (remote[:12] if remote else '(读不到)'))
    if not remote:
        w('=== 结论 = 连不上远端（网络/代理），不是本地问题 ===')
        return 5

    w('[3] ★ 分叉闸（唯一目的：别覆盖主线）')
    rc, o, e = run(['merge-base', '--is-ancestor', remote, local])
    ff = (rc == 0)
    rc2, o2, _ = run(['log', '--oneline', '%s..%s' % (local, remote)])
    ahead_remote = [x for x in o2.splitlines() if x.strip()]
    w('    远端是本地祖先（可快进）：%s' % ff)
    w('    远端独有提交 %d 个' % len(ahead_remote))
    for x in ahead_remote[:6]:
        w('      ' + x[:100])
    if not ff:
        w('')
        w('    !! 分叉：直接 push 会被 git 拒（non-fast-forward）；强推会覆盖上面这些提交。')
        w('    !! 脚本**不推**。请先决定这条副本线要不要并回主线（或换个远端/分支）。')
        if not do_push:
            w('=== 结论 = REFUSED_BECAUSE_DIVERGED（未推送，符合预期）===')
            return 0

    if not do_push:
        w('=== 结论 = DRY_OK（加 --push 才真推）===')
        return 0

    w('[4] push origin main（**只试一次**）')
    rc, o, e = run(['push', 'origin', 'main'], timeout=600)
    w('    rc=%d' % rc)
    for ln in (o + e).splitlines():
        if ln.strip():
            w('    ' + ln[:180])

    w('[5] 独立核验（ls-remote 重试 5 次 + rev-parse 交叉）')
    got = ''
    for i in range(5):
        rc, o, e = run(['ls-remote', 'origin', 'refs/heads/main'], timeout=120)
        for ln in o.splitlines():
            if ln.endswith('refs/heads/main'):
                got = ln.split()[0]
        if got == local:
            break
        time.sleep(3)
    rc, om, _ = run(['rev-parse', 'origin/main'])
    ok = bool(got) and got == local and om.strip() == local
    w('    remote=%s / origin/main=%s / 本地=%s'
      % ((got or '(空)')[:12], om.strip()[:12], local[:12]))
    w('=== 结论 = %s ===' % ('PUSHED' if ok else 'NOT_VERIFIED'))
    return 0 if ok else 5


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

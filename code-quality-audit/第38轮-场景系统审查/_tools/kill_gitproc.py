# -*- coding: utf-8 -*-
"""第 38 轮：杀掉挂起的 git push 及其凭据弹窗子进程。

铁律 7.0：`helper-selector` 弹 GUI 时 push 会挂住 —— 必须立刻停手。
这里只动 **git 家族**进程，绝不误伤别的。
"""
import os
import signal
import sys

try:
    import psutil
except Exception as e:
    print('psutil import failed: %r' % (e,))
    sys.exit(1)

TARGETS = ('git.exe', 'git-remote-https.exe', 'git-remote-http.exe',
           'git-credential-manager.exe', 'git-credential-manager-core.exe',
           'git-credential-helper-selector.exe')
ME = os.getpid()

found = []
for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
    try:
        nm = (p.info.get('name') or '')
        cl = p.info.get('cmdline') or []
        joined = ' '.join(cl)
        if nm.lower() in TARGETS or 'push origin main' in joined:
            found.append((p.info['pid'], nm, joined[:110]))
    except Exception:
        pass

print('=== 命中 %d 个 git 家族进程 ===' % len(found))
for pid, nm, cl in found:
    print('  pid=%-7d %-28s %s' % (pid, nm, cl))

killed, failed = [], []
for pid, nm, cl in found:
    if pid == ME:
        continue
    try:
        proc = psutil.Process(pid)
        for ch in proc.children(recursive=True):
            try:
                ch.kill()
                killed.append(ch.pid)
            except Exception:
                pass
        proc.kill()
        killed.append(pid)
    except Exception as e:
        failed.append((pid, repr(e)))

print('killed=%d  %s' % (len(killed), killed))
print('failed=%s' % (failed,))

# 复核：再扫一遍
left = []
for p in psutil.process_iter(['pid', 'name']):
    try:
        if (p.info.get('name') or '').lower() in TARGETS:
            left.append((p.info['pid'], p.info['name']))
    except Exception:
        pass
print('remaining=%s' % (left,))

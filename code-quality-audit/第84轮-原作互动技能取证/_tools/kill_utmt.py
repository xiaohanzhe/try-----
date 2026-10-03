# -*- coding: utf-8 -*-
u"""清理残留的 UndertaleModCli.exe 进程（第84轮 UI 挂死后的收尾）。"""
from __future__ import print_function
import io, os, subprocess, sys, time

try:
    import psutil
except ImportError:
    print(u'!! psutil 不可用'); sys.exit(2)

targets = []
for p in psutil.process_iter([u'pid', u'name']):
    try:
        nm = (p.info.get(u'name') or u'')
    except Exception:
        continue
    if u'UndertaleModCli' in nm:
        targets.append(p.info[u'pid'])

print(u'[found] %d: %s' % (len(targets), targets))
for pid in targets:
    for _ in range(3):
        try:
            pp = psutil.Process(pid)
            pp.kill()
        except Exception as e:
            print(u'  kill %s: %s' % (pid, e))
            break
        time.sleep(0.4)
        try:
            if not psutil.pid_exists(pid):
                print(u'  killed %s' % pid); break
        except Exception:
            break

time.sleep(0.8)
left = []
for p in psutil.process_iter([u'pid', u'name']):
    try:
        if u'UndertaleModCli' in (p.info.get(u'name') or u''):
            left.append(p.info[u'pid'])
    except Exception:
        pass
print(u'[left] %s' % left)
sys.exit(0 if not left else 1)

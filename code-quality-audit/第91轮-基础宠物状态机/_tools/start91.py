# -*- coding: utf-8 -*-
"""第91轮：真机起宠（detached），stdout/stderr 全部落盘。

为什么不用 Start-Process（沙箱里静默失效）/ 不用 Shell 后台（随 shell 结束被杀）：
  用 subprocess + DETACHED_PROCESS，进程独立于本会话，日志可事后取证。
"""
import os
import subprocess
import time

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
CWD = os.path.join(ROOT, 'ralsei_pet')
PY = r'C:\Python311\python.exe'
LOG = r'C:\Users\23002\Downloads\_tmp\pet91.log'

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

fh = open(LOG, 'w', encoding='utf-8', errors='replace')
p = subprocess.Popen([PY, 'src/main.py'], cwd=CWD,
                     stdout=fh, stderr=subprocess.STDOUT,
                     creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                     close_fds=True)
print('pet pid =', p.pid)
print('log     =', LOG)
time.sleep(1)
print('alive   =', p.poll() is None)

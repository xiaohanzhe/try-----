# -*- coding: utf-8 -*-
"""run_g2.py —— 绕开 shell 管道，用 Python subprocess 跑全量 G2 并落文件。

★ 第96轮b 环境事实：本会话里 `run_all.py` 经 shell 重定向/管道偶发 **SIGTERM 零输出**
  （连续 3 次）。用 Python `subprocess` 直接捕获 stdout 稳定得多。
"""
import io
import os
import re
import subprocess
import sys

REG = r'C:\Users\23002\WorkBuddy\Worktrees\try - 副本\main-a7556e9c\code-quality-audit\regress'
OUT = os.path.join(os.environ.get('TEMP', r'C:\Windows\Temp'), 'g2_run_out.txt')

p = subprocess.run([r'C:\Python311\python.exe', '-u', 'run_all.py'],
                   cwd=REG, capture_output=True)
txt = p.stdout.decode('utf-8', 'replace')
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(txt)

print('RC =', p.returncode)
print('stdout 行数 =', len(txt.split('\n')))
lines = txt.split('\n')

# 非 IDENTICAL 的套件行
nonid = [l for l in lines if re.match(r'^\S+\s+\d+\s+\d+\s+\d+\s+\S+', l)
         and 'IDENTICAL' not in l]
print('\n=== 非 IDENTICAL 套件行 ===')
for l in nonid:
    print('  ', l[:160])
if not nonid:
    print('   （无）')

print('\n=== 合计 / 问题段 ===')
for l in lines:
    if l.startswith('合计') or l.startswith('【') or l.strip().startswith('- '):
        print('  ', l[:200])

print('\n落盘:', OUT)

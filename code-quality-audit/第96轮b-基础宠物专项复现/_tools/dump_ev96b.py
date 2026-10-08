# -*- coding: utf-8 -*-
"""dump_ev96b.py —— 把本轮各工具的原始输出落进 _evidence/。"""
import io
import os
import subprocess

ROOT = r'C:\Users\23002\WorkBuddy\Worktrees\try - 副本\main-a7556e9c'
ROUND = os.path.join(ROOT, 'code-quality-audit', '第96轮b-基础宠物专项复现')
EV = os.path.join(ROUND, '_evidence')
T = os.path.join(ROUND, '_tools')

JOBS = [
    ('check96b.txt', [os.path.join(T, 'check96b.py')]),
    ('mutate96b.txt', [os.path.join(T, 'mutate96b.py')]),
    ('recheck96b_final.txt', [os.path.join(T, 'recheck96b_final.py')]),
    ('reach96b.txt', [os.path.join(T, 'reach96b.py')]),
    ('probe97_surprise_jump.txt', [os.path.join(T, 'probe97_surprise_jump.py')]),
    ('probe96b_canned.txt', [os.path.join(T, 'probe96b_canned.py')]),
    ('g2_full.txt', [os.path.join(T, 'run_g2.py')]),
]

for out, cmd in JOBS:
    p = subprocess.run([r'C:\Python311\python.exe'] + cmd, cwd=ROOT,
                       capture_output=True)
    txt = p.stdout.decode('utf-8', 'replace')
    if p.stderr:
        txt += '\n--- stderr ---\n' + p.stderr.decode('utf-8', 'replace')
    io.open(os.path.join(EV, out), 'w', encoding='utf-8', newline='\n').write(txt)
    print('%-30s rc=%d bytes=%d' % (out, p.returncode, len(txt)))

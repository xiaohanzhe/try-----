# -*- coding: utf-8 -*-
"""第199轮 · 批量同步 `_personas.json` 的登记字段

为什么不自己算：`sync_index113i.py` 就是产品口径（chars 含 CRLF / bytes / sha256 /
sha256_lf / sections 不含尾块），另写一套必然漂。这里只负责**批量调用它**。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PER = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')
TOOL = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                    '_tools', 'sync_index113i.py')
PY = r'C:\Python311\python.exe'


def main():
    ids = sorted(n[:-4] for n in os.listdir(PER) if n.endswith('.txt'))
    print('共 %d 个 id' % len(ids))
    cmd = [PY, TOOL] + ids + ['--write']
    r = subprocess.run(cmd, capture_output=True)
    out = (r.stdout or b'').decode('utf-8', 'replace')
    err = (r.stderr or b'').decode('utf-8', 'replace')
    tail = out.strip().splitlines()[-25:]
    print('\n'.join(tail))
    if err.strip():
        print('--- stderr ---')
        print(err.strip()[:1500])
    print('rc=%d' % r.returncode)
    return r.returncode


if __name__ == '__main__':
    sys.exit(main())

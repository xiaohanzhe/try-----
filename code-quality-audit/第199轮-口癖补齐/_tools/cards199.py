# -*- coding: utf-8 -*-
"""第199轮 · 批量重建**人设真变过**的训练卡

为什么必须做：`check113 A4`「77 张卡的人设 sha256 与磁盘一致（改了人设必须重建卡片）」
在第199轮全量回归里当场变红（不同步：asgore,berdly,... 64 份）。
我先前判断"卡片只是记账、训练走 persona_rel 读文件"——**判据证明我错了**，照判据办。

为什么不用 `cards113.py --all`：会把 77 张全重写，`patch`/`eval` 被清空过（第189轮实证）。
只重建磁盘人设**真变过**的那些，`carry_trained` 保 patch/eval。
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
TOOL = os.path.join(ROOT, 'code-quality-audit', '第189轮-口语化与发声',
                    '_tools', 'sync_card189.py')
PY = r'C:\Python311\python.exe'

sys.path.insert(0, HERE)
import apply199 as A        # noqa: E402

PER = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')


def main():
    # 本轮被改动的 = 有正例的（64 份）；被改写强化的 9 份全在这 64 里
    # ★ 不能 `import check199`：那个文件在模块级就跑判据并 `sys.exit()`，
    #   import 时会把整个套件执行一遍，还会把你退出。
    all_names = sorted(n for n in os.listdir(PER) if n.endswith('.txt'))
    ids = sorted(n[:-4] for n in all_names if n not in A.SKIP_EX)
    print('需要重建 %d 张卡' % len(ids))
    cmd = [PY, TOOL, '--ids', ','.join(ids), '--write']
    r = subprocess.run(cmd, capture_output=True)
    out = (r.stdout or b'').decode('utf-8', 'replace')
    err = (r.stderr or b'').decode('utf-8', 'replace')
    lines = out.strip().splitlines()
    print('\n'.join(lines[:6]))
    print('  ...')
    print('\n'.join(lines[-12:]))
    if err.strip():
        print('--- stderr ---')
        print(err.strip()[:1200])
    print('rc=%d' % r.returncode)
    return r.returncode


if __name__ == '__main__':
    sys.exit(main())

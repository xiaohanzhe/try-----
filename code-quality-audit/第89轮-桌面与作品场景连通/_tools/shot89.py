# -*- coding: utf-8 -*-
u"""一键：起桌宠 -> 等就绪 -> 逐窗口 PrintWindow 抓图 -> 杀进程。

★ 为什么合成一个脚本：Bash 工具在本机**不共享状态**（后台进程 + 后续命令取不到 pid），
  而且 `/tmp` 在 Git Bash 里映射行为不稳定（`FileNotFoundError`）。
  Python 单进程内 spawn + 抓 + kill 最可靠。
"""
import os
import re
import subprocess
import sys
import time

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, HERE)

import winprobe89  # noqa: E402  复用窗口枚举

def main():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    env.pop('QT_QPA_PLATFORM', None)

    log = open(os.path.join(HERE, '..', '_evidence', 'shots',
                            'win89_runtime.log'), 'w', encoding='utf-8', newline='\n')
    p = subprocess.Popen([sys.executable, os.path.join(PKG, 'src', 'main.py')],
                         cwd=PKG, env=env,
                         stdout=log, stderr=subprocess.STDOUT)
    print('spawned pid', p.pid)
    time.sleep(11)

    # 走 grabwin89 的抓图
    import grabwin89
    sys.argv = ['grabwin89.py', str(p.pid)]
    grabwin89.main()

    # 场景切换：调 travel_to 需要进程内调用；这里先只做"现状取证"。
    time.sleep(1)
    try:
        p.terminate()
        time.sleep(1.5)
        if p.poll() is None:
            p.kill()
    except Exception:
        pass
    log.close()
    print('killed')
    return 0


if __name__ == '__main__':
    sys.exit(main())

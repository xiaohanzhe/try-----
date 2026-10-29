# -*- coding: utf-8 -*-
u"""跑一次 UTMT CLI 并抓 stdout（DETACHED_PROCESS 分离启动，避免被父进程连带杀掉）。

用法：python cli_help115.py [参数...]
默认只跑 `--help`。
"""
import os
import subprocess
import sys
import time

EXE = os.environ.get(
    'UTMT_EXE',
    r'D:\E盘备份_20261028\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe')
WORK = os.environ.get('DUMP_WORK_UT', r'D:\_wb_tmp\dw_ut')
LOG = os.path.join(WORK, '_cli_help.log')

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def main(argv):
    os.makedirs(WORK, exist_ok=True)
    args = [EXE] + (argv or ['--help'])
    with open(LOG, 'wb') as f:
        p = subprocess.Popen(args, stdout=f, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL,
                             creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
        t0 = time.time()
        while p.poll() is None:
            if time.time() - t0 > 120:
                p.kill()
                break
            time.sleep(1)
    txt = open(LOG, 'rb').read().decode('utf-8', 'replace')
    print(txt)
    print('[rc=%r  %d bytes]' % (p.returncode, len(txt)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

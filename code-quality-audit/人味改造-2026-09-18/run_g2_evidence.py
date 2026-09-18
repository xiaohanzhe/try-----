# -*- coding: utf-8 -*-
"""跑一遍全量 G2，把输出**由 Python 自己**写成 UTF-8 证据文件。

为什么要这一层：PowerShell 的 `*>` / `Out-File` 捕获原生程序 stdout 时，会先按控制台
代码页（本机 GBK）解码、再按 UTF-8 重写 → 中文全变方块，文件本身已经坏了（见 MEMORY 环境铁律）。
证据文件必须由 Python `open(path,'w',encoding='utf-8')` 直接写。

用法（cwd 任意）：
    & C:\\Python311\\python.exe run_g2_evidence.py
"""
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
REGRESS = os.path.join(ROOT, 'code-quality-audit', 'regress')
EV = os.path.join(HERE, '_evidence')


def main():
    py = r'C:\Python311\python.exe'
    if not os.path.exists(py):
        py = sys.executable
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    proc = subprocess.run([py, os.path.join(REGRESS, 'run_all.py')],
                          cwd=REGRESS, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = proc.stdout.decode('utf-8', 'replace')

    # 套件数 / 合计行从输出里读出来，文件名跟着实际结果走（免得下次忘了改文件名）
    import re
    n_suite = text.count('IDENTICAL') + text.count('BASELINE') + text.count('DIFF')
    m = re.search(r'合计：PASS=(\d+) FAIL=(\d+)\s+套件=(\d+)', text)
    if m:
        name = 'G2_回归_%s套件_%sPASS.txt' % (m.group(3), m.group(1))
    else:
        name = 'G2_回归_%d套件.txt' % n_suite
    out = os.path.join(EV, name)
    os.makedirs(EV, exist_ok=True)
    with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
        f.write('\nEXIT=%d\n' % proc.returncode)
    print('EXIT=%d\n-> %s' % (proc.returncode, out))
    return proc.returncode


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""原样捕获子进程 stdout 的 UTF-8 字节并落盘 —— 绕开 PowerShell 管道的中文乱码。

背景（项目环境铁律）：PowerShell 管道会把子进程的中文 stdout 按 ANSI 解码、再按 UTF-8
写文件 → 双重编码 → 中文必乱码，且落盘后不可逆恢复。凡"想把某脚本输出存成证据"，
一律用本工具，**不要**用 `| Out-File`。

用法：
    C:\\Python311\\python.exe code-quality-audit/第十一轮/capture_utf8.py <目标脚本> <输出文件>
例：
    C:\\Python311\\python.exe code-quality-audit/第十一轮/capture_utf8.py ^
        code-quality-audit/第十一轮/verify_round11_input.py ^
        code-quality-audit/第十一轮/_evidence/round11_selftest.txt
"""
import io
import os
import subprocess
import sys


def main():
    if len(sys.argv) < 3:
        print('usage: capture_utf8.py <target.py> <out.txt>')
        return 2
    target = os.path.abspath(sys.argv[1])
    out = os.path.abspath(sys.argv[2])
    root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    r = subprocess.run([sys.executable, target], capture_output=True, cwd=root)
    raw = r.stdout or b''
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        text = raw.decode('gbk', 'replace')
    tail = '\n[stderr]\n' + (r.stderr or b'').decode('utf-8', 'replace') if r.stderr else ''
    with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
        f.write(tail)
        f.write('\n[exit] %s\n' % r.returncode)
    print('captured %d bytes -> %s (exit %s)' % (len(raw), out, r.returncode))
    return 0


if __name__ == '__main__':
    sys.exit(main())

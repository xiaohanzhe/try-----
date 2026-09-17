# -*- coding: utf-8 -*-
"""跑第十八轮（批次 B）审计套件，并把 stdout 交给 **Python 自己** 写成证据文件。

为什么需要这一层（第十三轮的真实翻车，见 tools/check_evidence_encoding.py）：
用 PowerShell 的 `*>` / `Out-File` 捕获原生程序 stdout 时，字节会先按控制台代码页
（本机 GBK）解码、再按 UTF-8 重写 → 中文全部变成看不懂的方块字，文件内容本身已经坏了。
本轮就吃过一次：第一遍跑套件用 `Out-File` 捕获，读回来是乱码（"涓婃ゼ" 之类），
虽然还能猜出 PASS/FAIL，但**不能当证据留痕**。证据文件必须由 Python 直接写。

用法：& C:\\Python311\\python.exe run_round18.py
"""
import io
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EV_DIR = os.path.join(HERE, '_evidence')
OUT = os.path.join(EV_DIR, 'round18_output.txt')

os.makedirs(EV_DIR, exist_ok=True)

_buf = io.StringIO()
_old = sys.stdout
sys.stdout = _buf
_code = 0
try:
    runpy.run_path(os.path.join(HERE, 'verify_round18_climb.py'), run_name='__main__')
except SystemExit as e:
    _code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
finally:
    sys.stdout = _old

with open(OUT, 'w', encoding='utf-8', newline='\n') as _fh:
    _fh.write(_buf.getvalue())
    _fh.write('\nEXIT=%d\n' % _code)

_old.write('EXIT=%d  →  %s\n' % (_code, OUT))
sys.exit(_code)

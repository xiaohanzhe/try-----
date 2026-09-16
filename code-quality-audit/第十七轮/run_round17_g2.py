# -*- coding: utf-8 -*-
"""第十七轮：跑 G2 全量回归（先 --update 固化基线，再跑一遍验证"全绿"），
并把两次的**控制台输出**交给 Python 自己写成证据文件。

为什么不用 PowerShell 捕获（见 tools/check_evidence_encoding.py）：`*>` / `Out-File`
会把子进程 stdout 先按控制台代码页解码再按 UTF-8 写回 → 中文全乱且文件已坏。

产出：code-quality-audit/第十七轮/_evidence/round17_g2.txt

用法：& C:\\Python311\\python.exe run_round17_g2.py
"""
import io
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
RUN_ALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
OUT = os.path.join(HERE, '_evidence', 'round17_g2.txt')

os.makedirs(os.path.dirname(OUT), exist_ok=True)


def run(argv):
    """跑一次 run_all.py，返回 (退出码, 捕获到的 stdout)。"""
    buf = io.StringIO()
    old_out, old_argv = sys.stdout, sys.argv
    sys.stdout = buf
    code = 0
    try:
        sys.argv = ['run_all.py'] + argv
        runpy.run_path(RUN_ALL, run_name='__main__')
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.stdout = old_out
        sys.argv = old_argv
    return code, buf.getvalue()


code1, out1 = run(['--update'])
code2, out2 = run([])

with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('#' * 72 + '\n')
    fh.write('# 第 1 遍：--update（固化基线：新增 round17_build_fall；'
             'round14_move 的 G1 断言改名为"派生时长"）\n')
    fh.write('#' * 72 + '\n')
    fh.write('EXIT=%d\n\n' % code1)
    fh.write(out1.replace('\ufeff', ''))
    fh.write('\n' + '#' * 72 + '\n')
    fh.write('# 第 2 遍：与刚固化的基线比对（期望：套件全 IDENTICAL、FAIL=0）\n')
    fh.write('#' * 72 + '\n')
    fh.write('EXIT=%d\n\n' % code2)
    fh.write(out2.replace('\ufeff', ''))

sys.stderr.write('EXIT1=%d EXIT2=%d -> %s\n' % (code1, code2, OUT))
sys.exit(code2)

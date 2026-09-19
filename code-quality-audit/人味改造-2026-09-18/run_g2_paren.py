# -*- coding: utf-8 -*-
"""跑一次全量 G2 并把原始输出**逐字节**存成证据（Python 自写 UTF-8，不经 PowerShell 管道）。

为什么用 Python 捕获：PowerShell 捕获原生程序 stdout 会按 GBK 有损解码再按 UTF-8 重写，
中文会真的坏掉（本项目的血泪教训）。Python 的 subprocess 拿的是原始字节。
"""
import os
import subprocess
import sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
OUT = os.path.join(ROOT, "code-quality-audit", "人味改造-2026-09-18", "_evidence",
                   "g2_after_括号动作闸_2026-09-19.txt")

p = subprocess.run([r"C:\Python311\python.exe",
                    os.path.join(ROOT, "code-quality-audit", "regress", "run_all.py")],
                   cwd=ROOT, capture_output=True)
txt = (p.stdout or b"").decode("utf-8", "replace")
err = (p.stderr or b"").decode("utf-8", "replace")
head = ("== G2 全量回归（括号动作闸之后）==\n"
        "命令：python code-quality-audit/regress/run_all.py\n"
        "退出码 = %d\n" % p.returncode)
open(OUT, "w", encoding="utf-8").write(head + txt + ("\n--- stderr ---\n" + err if err.strip() else ""))
print("exit=%d wrote=%s" % (p.returncode, OUT))
sys.exit(0 if p.returncode == 0 else 1)

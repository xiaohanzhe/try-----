# -*- coding: utf-8 -*-
"""跑全量 G2，输出落盘（Bash 缺 coreutils，不走管道）。"""
import subprocess, os, sys

REPO = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
OUT = os.path.join(REPO, "code-quality-audit", "第34轮-移动行为基础代码严查",
                   "_evidence", "_g2_final_29.txt")
p = subprocess.run([r"C:\Python311\python.exe",
                    os.path.join(REPO, "code-quality-audit", "regress", "run_all.py")],
                   cwd=REPO, capture_output=True, timeout=1800)
out = p.stdout.decode("utf-8", "replace")
err = p.stderr.decode("utf-8", "replace")
with open(OUT, "w", encoding="utf-8") as f:
    f.write("=== rc=%d ===\n" % p.returncode)
    f.write(out)
    if err.strip():
        f.write("\n=== stderr ===\n" + err)
# 摘要
lines = out.splitlines()
tail = [l for l in lines if ('PASS' in l and 'FAIL' in l) or 'IDENTICAL' in l or 'DIFF' in l
        or l.startswith('[') or '套件' in l or 'SUMMARY' in l]
print("rc =", p.returncode)
for l in (tail[-45:] if tail else lines[-45:]):
    print(l)
print("full ->", OUT)

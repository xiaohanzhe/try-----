# -*- coding: utf-8 -*-
"""把 G2 输出以 UTF-8 自写方式落到 _evidence（避免 PS 捕获原生的 GBK 有损解码）。"""
import io
import os
import re
import subprocess
import sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
REGRESS = os.path.join(ROOT, "code-quality-audit", "regress")
OUT = os.path.join(ROOT, "code-quality-audit", "第二十六轮", "_evidence", "G2_after_deadcode.txt")

env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
p = subprocess.run([r"C:\Python311\python.exe", "run_all.py"], cwd=REGRESS,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
text = p.stdout.decode("utf-8", "replace")

# 附加声明
head = []
head.append("第26轮 P1 死代码处置后的 G2 全量回归")
head.append("命令：C:\\Python311\\python.exe run_all.py   (cwd=code-quality-audit/regress)")
head.append("退出码：%d" % p.returncode)
m = re.search(r"合计：PASS=(\d+) FAIL=(\d+)\s+套件=(\d+)", text)
if m:
    head.append("汇总：PASS=%s FAIL=%s 套件=%s" % (m.group(1), m.group(2), m.group(3)))
head.append("DIFF 数：%d" % len(re.findall(r"\bDIFF\b", text)))
head.append("")

with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(head) + text)

sys.stdout.write("wrote %s rc=%d\n" % (OUT, p.returncode))

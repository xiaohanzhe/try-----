# -*- coding: utf-8 -*-
import io
import os

TARGET = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src\main.py"
with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
    lines = f.read().split("\n")

out = []
for n in (8232, 8236, 8238, 8241, 8243, 8256, 8257, 8259, 8273, 8275, 8306, 8308, 8332, 8334, 8350, 8588, 8591):
    out.append("L%d: [%s]" % (n, lines[n - 1]))
out.append("total_lines=%d" % len(lines))
with io.open(r"E:\Download\_tmp\anchors2.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out) + "\n")
print("ok")

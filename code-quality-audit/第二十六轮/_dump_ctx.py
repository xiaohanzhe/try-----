# -*- coding: utf-8 -*-
import io

TARGET = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src\main.py"
with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
    lines = f.read().split("\n")

out = []
for n in range(8230, 8352):
    out.append("%4d|%s|" % (n, lines[n - 1]))
out.append("----")
for n in range(8584, 8595):
    out.append("%4d|%s|" % (n, lines[n - 1]))
with io.open(r"E:\Download\_tmp\ctx.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out) + "\n")
print("ok")

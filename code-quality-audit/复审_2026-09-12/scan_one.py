# -*- coding: utf-8 -*-
"""扫描指定文件的类与方法结构（通用）"""
import re
import sys

path = sys.argv[1]
label = sys.argv[2] if len(sys.argv) > 2 else path
src = open(path, encoding="utf-8").read()
lines = src.splitlines()
print(f"{'='*70}\n{label}  总行数: {len(lines)}\n{'='*70}")
for i, l in enumerate(lines, 1):
    m = re.match(r"^(\s*)(?:def|class)\s+(\w+)", l)
    if m:
        indent = len(m.group(1))
        print(f"{i:5d} {'  '*(indent//4)}{m.group(2)}")

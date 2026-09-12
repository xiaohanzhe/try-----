# -*- coding: utf-8 -*-
"""扫描 main.py / modules 的结构：类与方法定义清单（本轮审查用）"""
import re
import os
import sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
TARGET = os.path.join(ROOT, "ralsei_pet", "src", "main.py")


def scan(path, label):
    src = open(path, encoding="utf-8").read()
    lines = src.splitlines()
    print(f"\n{'='*70}\n{label}  总行数: {len(lines)}\n{'='*70}")
    for i, l in enumerate(lines, 1):
        m = re.match(r"^(\s*)(?:def|class)\s+(\w+)", l)
        if m:
            indent = len(m.group(1))
            print(f"{i:5d} {'  '*(indent//4)}{m.group(2)}")


if __name__ == "__main__":
    scan(TARGET, "main.py")

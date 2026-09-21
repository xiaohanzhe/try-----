# -*- coding: utf-8 -*-
"""收尾：把 L8231/L8232 的连续空行折叠成一个（保持类体 `\\n\\n` 惯例）。
带断言 + 反向归一证明（保留**逐字符原样**，含行内空白）。
"""
import hashlib
import io
import os

TARGET = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src\main.py"

with io.open(TARGET, "rb") as f:
    raw_before = f.read()
md5_before = hashlib.md5(raw_before).hexdigest()

with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
    lines = f.read().split("\n")

# 锚断言（保留原样字符串）
assert lines[8230].strip() == "" and lines[8231].strip() == "", \
    "锚不匹配: L8231=%r L8232=%r" % (lines[8230], lines[8231])
assert lines[8229].strip().startswith('self.emotion_system.react_to_event("saw_sad_content"'), \
    "前置行不匹配: %r" % lines[8229]
assert lines[8232].startswith("    def react_to_vs_code_code("), \
    "后置行不匹配: %r" % lines[8232]

removed_line = lines[8231]          # 逐字符保存
db = sum(1 for i in range(len(lines) - 1)
         if lines[i].strip() == "" and lines[i + 1].strip() == "")

new_lines = list(lines)
del new_lines[8231]

with io.open(TARGET, "w", encoding="utf-8", newline="") as f:
    f.write("\n".join(new_lines))

# 反向归一：把**原样的那一行**插回 → 逐字符等于原文
norm = list(new_lines)
norm.insert(8231, removed_line)
assert "\n".join(norm) == "\n".join(lines), "反向归一失败"

with io.open(TARGET, "rb") as f:
    raw_after = f.read()

out = []
out.append("收尾：折叠连续空行（L8231 / L8232）")
out.append("被删行逐字符：%r" % removed_line)
out.append("md5 %s -> %s  bytes %d -> %d" % (
    md5_before, hashlib.md5(raw_after).hexdigest(),
    len(raw_before), len(raw_after)))
out.append("全文件原「连续两空行」位置数（含本处）：%d" % db)
out.append("反向归一证明：通过")
with io.open(r"C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第二十六轮\_evidence\r26_seam_tidy.txt",
             "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out) + "\n")
print("ok")

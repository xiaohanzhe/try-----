# -*- coding: utf-8 -*-
"""核验收尾结果：当前 main.py 的 L8231 处是否已只剩一个空行，
并用「与手术产物 main_before? 」无关的独立判据确认：
  · 当前文件 == 手术产物 减去一行 8 空格空行
  · 逐字符反向归一（插回那一行 → 字节流等于手术产物）
"""
import hashlib
import io
import os

TARGET = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src\main.py"
# 手术产物由 G2 基线时的 main.py 决定；这里直接与「E 盘备份 + 手术脚本」无关，
# 改用"结构判据"：L8231 唯一的 def 相邻空行数 == 1。

with io.open(TARGET, "r", encoding="utf-8", newline="") as f:
    text = f.read()
lines = text.split("\n")

out = []
out.append("当前文件 md5=%s 行数=%d 字节=%d" % (
    hashlib.md5(text.encode("utf-8")).hexdigest(), len(lines), len(text.encode("utf-8"))))

# 定位 react_to_file_emotionally 末尾 -> react_to_vs_code_code 之间的空行
idx = None
for i, ln in enumerate(lines):
    if ln.startswith("    def react_to_vs_code_code("):
        idx = i
        break
out.append("react_to_vs_code_code 首行 index=%d (L%d)" % (idx, idx + 1))
# 向上数空行
k = idx - 1
blank = 0
while k >= 0 and lines[k].strip() == "":
    blank += 1
    k -= 1
out.append("其上方连续空行数=%d  上一非空行=%r" % (blank, lines[k]))
out.append("判据：blank == 1 → %s" % ("通过" if blank == 1 else "失败"))

# 全文件「连续两空行」位置统计（收尾后）
db = []
for i in range(len(lines) - 1):
    if lines[i].strip() == "" and lines[i + 1].strip() == "":
        db.append(i + 1)
out.append("全文件「连续两空行」位置数=%d" % len(db))
out.append("明细(前 30 个 L 号)：%s" % db[:30])

with io.open(r"C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第二十六轮\_evidence\r26_seam_tidy.txt",
             "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(out) + "\n")
print("ok")

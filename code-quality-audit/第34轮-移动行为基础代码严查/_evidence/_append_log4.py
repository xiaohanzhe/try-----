# -*- coding: utf-8 -*-
"""追加当日日志（前缀逐字节核验）。"""
import traceback

LOG = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\.workbuddy\memory\2026-09-22.md"
ADD = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第34轮-移动行为基础代码严查\_evidence\_log_append_34d.md"
OUT = r"E:\Download\_tmp\_log34d_result.txt"

buf = []
def log(s): buf.append(s)
try:
    old = open(LOG, "r", encoding="utf-8").read()
    add = open(ADD, "r", encoding="utf-8").read()
    log("before len=%d" % len(old))
    if "task #13 存储/配置层（生命周期线）细查与修复" in old:
        log("ALREADY PRESENT -> skip")
    else:
        new = old + add
        assert new[:len(old)] == old
        with open(LOG, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        back = open(LOG, "r", encoding="utf-8").read()
        log("after len=%d" % len(back))
        log("PREFIX-IDENTICAL=%s" % (back[:len(old)] == old))
        log("TAIL-PRESENT=%s" % ("task #13 存储/配置层（生命周期线）细查与修复" in back))
        log("first3=%s" % list(open(LOG, "rb").read(3)))
except Exception:
    log("!! " + traceback.format_exc())
open(OUT, "w", encoding="utf-8").write("\n".join(buf) + "\n")
print("done")

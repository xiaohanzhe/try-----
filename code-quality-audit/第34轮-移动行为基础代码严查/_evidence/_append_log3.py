# -*- coding: utf-8 -*-
"""把 _log_append_34c.md 追加进当日日志（前缀逐字节核验）"""
import traceback

LOG = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\.workbuddy\memory\2026-09-22.md"
ADD = r"E:\Download\_tmp\_log_append_34c.md"
OUT = r"E:\Download\_tmp\_log_append_result.txt"

buf = []
def log(s): buf.append(s)

try:
    old = open(LOG, "r", encoding="utf-8").read()
    add = open(ADD, "r", encoding="utf-8").read()
    log("before len=%d" % len(old))
    if "第 34 轮收尾：提交与推送" in old:
        log("ALREADY PRESENT -> skip")
    else:
        new = old + add
        # 前缀逐字节核验
        assert new[:len(old)] == old
        with open(LOG, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        back = open(LOG, "r", encoding="utf-8").read()
        log("after len=%d" % len(back))
        log("PREFIX-IDENTICAL=%s" % (back[:len(old)] == old))
        log("TAIL-PRESENT=%s" % ("第 34 轮收尾：提交与推送" in back))
        # 首字节无 BOM
        raw = open(LOG, "rb").read(3)
        log("first3=%s (not BOM)" % list(raw))
except Exception:
    log("!! " + traceback.format_exc())

open(OUT, "w", encoding="utf-8").write("\n".join(buf) + "\n")
print("done")

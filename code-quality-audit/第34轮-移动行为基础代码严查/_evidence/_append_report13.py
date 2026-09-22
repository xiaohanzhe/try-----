# -*- coding: utf-8 -*-
"""把 §十三 追加进报告 + 更新头部 G2 数字（前缀逐字节核验）。"""
import traceback

REP = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\第三十四轮移动行为基础代码严查报告_2026-09-22.md"
ADD = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第34轮-移动行为基础代码严查\_evidence\_report_append_13.md"
OUT = r"E:\Download\_tmp\_rep13_result.txt"

buf = []
def log(s): buf.append(s)

try:
    old = open(REP, "r", encoding="utf-8").read()
    add = open(ADD, "r", encoding="utf-8").read()
    log("before len=%d" % len(old))

    # 1) 头部数字更新
    new = old
    reps = [
        ("| **G2 结果**：`PASS=1410 FAIL=0`，**28 套件全 IDENTICAL**",
         "| **G2 结果**：`PASS=1427 FAIL=0`，**29 套件全 IDENTICAL**"),
        ("（最终；新增 `round34_movement` 36 项 + `round34_floor_manager` 15 项）",
         "（最终；新增 `round34_movement` 36 项 + `round34_floor_manager` 15 项 + `round34_store_config` 17 项）"),
    ]
    for a, b in reps:
        if a in new:
            new = new.replace(a, b, 1); log("HEAD replaced: %s" % a[:44])
        else:
            log("HEAD MISS: %s" % a[:44])

    # 2) 追加 §十三
    if "## 十三、存储 / 配置层细查" in new:
        log("SECTION13 ALREADY PRESENT -> skip append")
    else:
        new = new + add
        log("appended %d chars" % len(add))

    assert new[:len(old)].startswith(old[:200]), "前缀异常"
    with open(REP, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    back = open(REP, "r", encoding="utf-8").read()
    log("after len=%d" % len(back))
    log("TAIL-PRESENT=%s" % ("## 十三、存储 / 配置层细查" in back))
    log("PASS1427=%s" % ("PASS=1427" in back))
    log("first3=%s (not BOM)" % list(open(REP, "rb").read(3)))
except Exception:
    log("!! " + traceback.format_exc())

open(OUT, "w", encoding="utf-8").write("\n".join(buf) + "\n")
print("done")

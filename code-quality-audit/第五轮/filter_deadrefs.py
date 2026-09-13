# -*- coding: utf-8 -*-
"""过滤 _deadrefs.json：剔除 Qt 事件回调等"由框架调用"的假阳性，
输出真正可疑的死代码清单。只读。"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with io.open(os.path.join(HERE, "_deadrefs.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

# 由 Qt / Python 协议调用的名字，不算死代码
FRAMEWORK = {
    "paintEvent", "moveEvent", "mousePressEvent", "mouseMoveEvent", "mouseReleaseEvent",
    "mouseDoubleClickEvent", "mouseEnterEvent", "mouseLeaveEvent", "resizeEvent",
    "closeEvent", "keyPressEvent", "wheelEvent", "showEvent", "hideEvent", "enterEvent",
    "leaveEvent", "changeEvent", "dropEvent", "dragEnterEvent", "dragMoveEvent",
    "__init__", "__del__", "__repr__", "__str__", "__len__", "__getitem__", "__setitem__",
    "__iter__", "__next__", "__contains__", "__eq__", "__hash__", "__enter__", "__exit__",
    "main", "callback",
}

rows = []
for item in data["never_referenced"]:
    n = item["name"]
    if n in FRAMEWORK:
        continue
    if n.startswith("__") and n.endswith("__"):
        continue
    rows.append(item)

rows.sort(key=lambda r: (r["file"], r["line"]))

lines = []
lines.append("真正可疑的死代码（已剔除 Qt 事件回调等框架调用）")
lines.append("总数: %d（原 %d，剔除 %d）" % (len(rows), len(data["never_referenced"]),
                                           len(data["never_referenced"]) - len(rows)))
lines.append("")
for r in rows:
    lines.append("%-46s :%-5d  %s" % (r["file"], r["line"], r["name"]))

lines.append("")
lines.append("=" * 70)
lines.append("同名重复定义（可能构成覆写风险）")
lines.append("=" * 70)
for d in data["duplicate_definitions"]:
    locs = ", ".join("%s:%d" % (x["file"], x["line"]) for x in d["locs"])
    lines.append("%-34s %s" % (d["name"], locs))

out = os.path.join(HERE, "_deadrefs_filtered.txt")
with io.open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("\n".join(lines[:80]))
print("...")
print("total suspicious:", len(rows))

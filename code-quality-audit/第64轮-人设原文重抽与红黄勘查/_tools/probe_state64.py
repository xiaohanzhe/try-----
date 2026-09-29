# -*- coding: utf-8 -*-
"""第64轮：动手前的现状核实（只读，不改任何被测状态）。

判据（每条显式打印）：
  P1 轮次目录存在 + 子目录清单
  P2 已产出的 _evidence 文件清单 + 字节数 + 是否非空
  P3 UTMT 工具链存在（utmt61.py / UTMT_CLI 可执行）
  P4 E:\Download\_extract64\assets\game.droid 存在 + 字节数 == 134313139
  P5 仓库工作区是否干净（git status --porcelain）
"""
import os
import subprocess
import sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
R64 = os.path.join(ROOT, "code-quality-audit", "第64轮-人设原文重抽与红黄勘查")
UTMT61 = os.path.join(ROOT, "code-quality-audit", "第61轮-跨界扩展动工", "_tools", "utmt61.py")
GAMEDROID = r"E:\Download\_extract64\assets\game.droid"

ok = []
bad = []


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    (ok if cond else bad).append(name)
    print("[%s] %s  %s" % (tag, name, detail))


# ---- P1 轮次目录 ----
check("P1a 轮次目录存在", os.path.isdir(R64), R64)
if os.path.isdir(R64):
    subs = sorted(os.listdir(R64))
    print("      R64 子项: %s" % subs)

# ---- P2 _evidence ----
ev = os.path.join(R64, "_evidence")
check("P2a _evidence 存在", os.path.isdir(ev), ev)
if os.path.isdir(ev):
    files = sorted(os.listdir(ev))
    for f in files:
        p = os.path.join(ev, f)
        sz = os.path.getsize(p) if os.path.isfile(p) else -1
        print("      %-34s %s" % (f, (str(sz) + " 字节") if sz >= 0 else "<DIR>"))
    check("P2b _evidence 非空", len(files) > 0, "%d 项" % len(files))

# ---- P3 UTMT ----
check("P3a utmt61.py 存在", os.path.isfile(UTMT61), UTMT61)
tools_dir = os.path.join(ROOT, "code-quality-audit", "第61轮-跨界扩展动工", "_tools")
if os.path.isdir(tools_dir):
    print("      第61轮 _tools: %s" % sorted(os.listdir(tools_dir)))

# ---- P4 game.droid ----
if os.path.isfile(GAMEDROID):
    sz = os.path.getsize(GAMEDROID)
    check("P4a game.droid 字节数 == 134313139", sz == 134313139, "实测 %d" % sz)
else:
    check("P4a game.droid 存在", False, GAMEDROID)

# ---- P5 工作区 ----
r = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
lines = [l for l in (r.stdout or "").splitlines() if l.strip()]
check("P5a 工作区干净", len(lines) == 0, "%d 条改动" % len(lines))
for l in lines[:20]:
    print("      | %s" % l)

print("")
print("== 汇总: %d PASS / %d FAIL ==" % (len(ok), len(bad)))
if bad:
    print("FAIL 项: %s" % bad)
sys.exit(0 if not bad else 1)

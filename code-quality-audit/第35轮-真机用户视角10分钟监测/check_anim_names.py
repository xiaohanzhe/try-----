# -*- coding: utf-8 -*-
"""第 35 轮 —— 动画名「代码引用 vs 资源存在」全量比对（F35-1 的同类排查）。

动机：
    真机跑出 [anim-miss] walk_down_sleep / walk_left_sleep，说明代码会拼出
    资源里不存在的动画名。这类洞**只要有一个，就可能有一片**。
    必须全量扫，不能只修被观测到的那一个。

做法（走 AST，不用正则）：
    1. 从 main.py + modules/*.py 里收集所有**字符串字面量**（AST Constant），
       这些是潜在的动画名。
    2. 与 assets/animations.json 的 groups 键 + sprite_loader 的别名做差集。
    3. 只报"看起来像动画名"的（形如 foo_bar / 已知前缀），避免噪音。
"""
import ast
import json
import os
import re

WS = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PET = os.path.join(WS, "ralsei_pet")
EV = os.path.join(WS, "code-quality-audit", "第35轮-真机用户视角10分钟监测", "_evidence")

# ---- 资源侧真名 ----
anim = json.load(open(os.path.join(PET, "assets", "animations.json"), encoding="utf-8"))
groups = set(anim.get("groups", {}).keys())

# sprite_loader 里的别名/回退表
sl = open(os.path.join(PET, "modules", "sprite_loader.py"), encoding="utf-8").read()
alias = set()
for m in re.finditer(r'["\']([a-z][a-z0-9_]{2,})["\']\s*:', sl):
    alias.add(m.group(1))

KNOWN = groups | alias

# ---- 代码侧：AST 收集字符串字面量 ----
ANIM_PREFIX = re.compile(
    r"^(idle|walk|run|jump|fall|land|splat|climb|slide|roll|dance|spin|bow|sing|"
    r"hug|cower|look|nuzzle|item|pose|smile|shocked|surprised|laugh|cry|tea|curtsy|"
    r"wave|victory|act|spell|sleep|hatless|darkchurch|susie|stun|hurt|blush|unhappy|"
    r"butler|cotton|throw|dark|shadow|wake|sit|stand|dodge|pat|pet_)")

found = {}
skip_dirs = {"__pycache__", ".git"}


def scan(path):
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except Exception:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if 3 <= len(v) <= 40 and ANIM_PREFIX.match(v) and " " not in v and "/" not in v:
                found.setdefault(v, []).append(os.path.relpath(path, WS))

for root, dirs, files in os.walk(PET):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for fn in files:
        if fn.endswith(".py"):
            scan(os.path.join(root, fn))

missing = sorted(k for k in found if k not in KNOWN)

lines = []
lines.append("第35轮 动画名比对：代码引用 vs 资源存在（AST 口径）")
lines.append("=" * 66)
lines.append("资源侧真名(groups): %d 个" % len(groups))
lines.append("sprite_loader 别名: %d 个" % len(alias))
lines.append("代码侧疑似动画名字面量: %d 个" % len(found))
lines.append("")
lines.append("★ 资源中不存在（= 运行时会 anim-miss 回退）: %d 个" % len(missing))
lines.append("-" * 66)
for k in missing:
    lines.append("  %-28s 引用处: %s" % (k, ", ".join(sorted(set(found[k]))[:3])))
lines.append("")
lines.append("（注：部分字面量可能是动画**前缀**片段而非完整名，需人工复核；")
lines.append("  下方列出资源侧全部真名，供比对。）")
lines.append("-" * 66)
lines.append("资源侧 groups 全量：")
lines.append("  " + ", ".join(sorted(groups)))

dst = os.path.join(EV, "36_动画名比对_代码vs资源.txt")
open(dst, "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
print()
print("WROTE", dst)

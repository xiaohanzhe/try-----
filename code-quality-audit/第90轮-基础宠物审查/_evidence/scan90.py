# -*- coding: utf-8 -*-
"""第90轮 · 基础宠物静态扫描（只读；一律 ast.parse，绝不 py_compile 产 .pyc）"""
import ast
import io
import os
import re
import sys
from collections import Counter, defaultdict

SRC = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"

TARGETS = [
    r"src\main.py",
    r"modules\dialogue_ui.py",
    r"modules\sprite_loader.py",
    r"modules\floor_manager.py",
    r"modules\desktop_interaction.py",
    r"modules\video_controller.py",
]


def read(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


print("=" * 70)
print("A. 规模基线")
print("=" * 70)
total = 0
files = []
for root, _d, fs in os.walk(SRC):
    if any(x in root for x in ("__pycache__", ".git", "assets", "sprites", "_scratch")):
        continue
    for fn in fs:
        if fn.endswith(".py"):
            fp = os.path.join(root, fn)
            try:
                n = len(read(fp).splitlines())
            except Exception:
                continue
            files.append((n, os.path.relpath(fp, SRC)))
            total += n
files.sort(reverse=True)
print("  全包 .py = %d 个，合计 %d 行" % (len(files), total))
for n, p in files[:8]:
    print("    %6d  %s" % (n, p))

print()
print("=" * 70)
print("B. 异常吞噬：`except …: pass` / 只有注释或 log 的分支")
print("=" * 70)
grand = Counter()
for rel in TARGETS:
    fp = os.path.join(SRC, rel)
    if not os.path.isfile(fp):
        continue
    src = read(fp)
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print("  !! %s 语法错误 %s" % (rel, e))
        continue
    bare = 0        # except:
    silent = 0      # except: pass（体只有 Pass 常量）
    broad = 0       # except Exception
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                bare += 1
            elif isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
                broad += 1
            body = [b for b in node.body if not (isinstance(b, ast.Expr)
                                                 and isinstance(b.value, ast.Constant)
                                                 and isinstance(b.value.value, str))]
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                silent += 1
    lines = src.count("\n") + 1
    print("  %-34s 行=%5d  except=%-4d 裸except=%-3d 宽except=%-4d **静默pass=%d**"
          % (rel, lines, bare + silent + broad, bare, broad, silent))
    grand["bare"] += bare
    grand["silent"] += silent
    grand["broad"] += broad
print("  ---- 合计：静默 pass=%d  裸 except=%d  宽 Exception=%d"
      % (grand["silent"], grand["bare"], grand["broad"]))

print()
print("=" * 70)
print("C. 恒真/可疑判据 & 硬编码魔数（main.py）")
print("=" * 70)
src = read(os.path.join(SRC, r"src\main.py"))
pats = {
    "assert True / check(..., True)": r"\b(assert\s+True|check\([^)]*,\s*True\s*\))",
    "恒真比较 x == x 或 True == True": r"\bTrue\s*==\s*True\b|(\b(\w+)\.\w+\(\)\s*==\s*True\b)",
    "if True:": r"^\s*if\s+True\s*:",
    "硬编码像素魔数(>=3位)": r"(?<![\w.])\d{3,}(?:\.[0-9]+)?(?![\w.])",
}
for name, p in pats.items():
    m = re.findall(p, src, re.M)
    print("  %-32s 命中 %d" % (name, len(m)))
    if name.startswith("恒真") and m:
        print("      样例: %s" % m[:5])

print()
print("=" * 70)
print("D. `hasattr(..., 'has_ball')` 类恒假条件（全仓库）")
print("=" * 70)
for root, _d, fs in os.walk(SRC):
    if "__pycache__" in root:
        continue
    for fn in fs:
        if not fn.endswith(".py"):
            continue
        fp = os.path.join(root, fn)
        s = read(fp)
        if "has_ball" in s:
            rel = os.path.relpath(fp, SRC)
            for i, l in enumerate(s.splitlines(), 1):
                if "has_ball" in l:
                    print("  %s:%d  %s" % (rel, i, l.strip()[:100]))

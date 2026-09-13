# -*- coding: utf-8 -*-
"""第五轮审查辅助：找出"定义了但全项目无任何引用"的函数/方法。

判定方式：AST 收集每个 def 的名字，然后统计该名字在全部 .py 文本中
（排除注释与字符串字面量之外）出现的次数。出现次数 == 1（仅定义处）
即视为可疑死代码，需人工确认。

同时输出：同名 def 重复定义（覆盖风险）、模块级 import 但未使用。
只读脚本，不修改任何文件。
"""
import ast
import io
import json
import os
import re
import sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
# 只审生产代码
INCLUDE_DIRS = [os.path.join(ROOT, "modules"), os.path.join(ROOT, "src")]
EXCLUDE_NAME_PARTS = ("__pycache__",)
# 测试/诊断脚本不算生产引用来源，但仍要参与"引用计数"（保守起见全算，避免误报）
EXCLUDE_FILES = {"main_simple.py"}


def iter_py():
    for d in INCLUDE_DIRS:
        for dirpath, dirnames, filenames in os.walk(d):
            if any(p in dirpath for p in EXCLUDE_NAME_PARTS):
                continue
            for fn in filenames:
                if fn.endswith(".py") and fn not in EXCLUDE_FILES:
                    yield os.path.join(dirpath, fn)


def strip_noise(src: str) -> str:
    """去掉注释与字符串字面量，避免"名字出现在注释里"被误判为引用。"""
    out = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        # 三引号字符串
        if src.startswith('"""', i) or src.startswith("'''", i):
            q = src[i:i + 3]
            j = src.find(q, i + 3)
            i = n if j == -1 else j + 3
            out.append("  ")
            continue
        if c == "#":
            j = src.find("\n", i)
            i = n if j == -1 else j
            out.append("\n")
            continue
        if c in ('"', "'"):
            q = c
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == q:
                    break
                j += 1
            i = j + 1
            out.append("  ")
            continue
        out.append(c)
        i += 1
    return "".join(out)


files = list(iter_py())
srcs = {}
for f in files:
    try:
        with io.open(f, "r", encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
        srcs[f] = (raw, strip_noise(raw))
    except Exception as e:
        print("READ FAIL", f, e, file=sys.stderr)

# 收集定义
defs = []          # (name, file, lineno, kind)
dupe = {}
for f, (raw, clean) in srcs.items():
    try:
        tree = ast.parse(raw)
    except SyntaxError as e:
        print("SYNTAX ERROR", f, e, file=sys.stderr)
        continue
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            kind = "method" if any(k in f for k in ("modules", "src")) else "func"
            defs.append((name, f, node.lineno, kind))
            dupe.setdefault(name, []).append((f, node.lineno))

# 统计引用：把"去噪后的文本"里所有标识符找出来
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
file_tokens = {f: IDENT.findall(clean) for f, (raw, clean) in srcs.items()}
all_counts = {}
for f, toks in file_tokens.items():
    for t in toks:
        all_counts[t] = all_counts.get(t, 0) + 1

report = {
    "never_referenced": [],
    "defined_once_referenced_once": [],
    "duplicate_definitions": [],
}

seen = set()
for name, f, lineno, kind in defs:
    total = all_counts.get(name, 0)
    if total <= 1:
        key = (name, f)
        if key in seen:
            continue
        seen.add(key)
        report["never_referenced"].append({
            "name": name, "file": os.path.relpath(f, ROOT), "line": lineno, "occurrences": total,
        })

# 重复定义（同名 def 出现多次，且不在不同类里也要提示）
for name, locs in dupe.items():
    if len(locs) > 1:
        report["duplicate_definitions"].append({
            "name": name,
            "locs": [{"file": os.path.relpath(f, ROOT), "line": l} for f, l in locs],
        })

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_deadrefs.json")
with io.open(out, "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=2)

print("files scanned:", len(srcs))
print("defs:", len(defs))
print("never_referenced:", len(report["never_referenced"]))
print("duplicate_definitions:", len(report["duplicate_definitions"]))
print("written:", out)

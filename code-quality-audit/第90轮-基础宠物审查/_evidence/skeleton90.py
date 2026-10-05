# -*- coding: utf-8 -*-
"""第90轮 · 用 AST 打印指定函数的控制流骨架（只读、不执行被测代码）"""
import ast
import io
import os
import sys

SRC = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src\main.py"
WANT = sys.argv[1:] or ["update_movement"]


def read(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


src = read(SRC)
lines = src.splitlines()
tree = ast.parse(src)


def short(node, maxlen=96):
    try:
        s = ast.get_source_segment(src, node) or ""
    except Exception:
        s = ""
    s = " ".join(s.split())
    return s if len(s) <= maxlen else s[:maxlen - 3] + "..."


FUNCS = {}
for n in ast.walk(tree):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        FUNCS.setdefault(n.name, []).append(n)


def walk(node, depth, out, parent_kind=None):
    pad = "  " * depth
    for child in node.body:
        if isinstance(child, ast.If):
            out.append("%sif %s:            L%d" % (pad, short(child.test, 70), child.lineno))
            walk(child, depth + 1, out, 'if')
            if child.orelse:
                if len(child.orelse) == 1 and isinstance(child.orelse[0], ast.If):
                    out.append("%selif %s:          L%d"
                               % (pad, short(child.orelse[0].test, 68), child.orelse[0].lineno))
                    walk(child.orelse[0], depth + 1, out, 'if')
                    # 继续展开链
                    cur = child.orelse[0]
                    while cur.orelse and len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
                        cur = cur.orelse[0]
                        out.append("%selif %s:          L%d"
                                   % (pad, short(cur.test, 68), cur.lineno))
                        walk(cur, depth + 1, out, 'if')
                else:
                    out.append("%selse:                 L%d" % (pad, child.orelse[0].lineno))
                    walk(child, depth + 1, out, 'else')
        elif isinstance(child, (ast.For, ast.While)):
            out.append("%s%s ...:            L%d" % (pad, type(child).__name__.lower(), child.lineno))
            walk(child, depth + 1, out)
        elif isinstance(child, ast.Return):
            out.append("%sreturn %s            L%d" % (pad, short(child.value, 50) if child.value else "", child.lineno))
        elif isinstance(child, (ast.Try,)):
            out.append("%stry:                    L%d" % (pad, child.lineno))
            walk(child, depth + 1, out)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append("%sdef %s(...)          L%d" % (pad, child.name, child.lineno))


for name in WANT:
    for fn in FUNCS.get(name, []):
        n_stmt = sum(1 for _ in ast.walk(fn) if isinstance(_, ast.stmt))
        print("=" * 72)
        print("%s()  L%d  体语句=%d" % (name, fn.lineno, n_stmt))
        print("=" * 72)
        out = []
        walk(fn, 0, out)
        print("\n".join(out))
        print()

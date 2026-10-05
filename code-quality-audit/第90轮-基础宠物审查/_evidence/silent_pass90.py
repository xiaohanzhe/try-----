# -*- coding: utf-8 -*-
"""第90轮 · 列出全部"静默 except: pass"站点（只读）"""
import ast
import io
import os

SRC = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
TARGETS = [r"src\main.py", r"modules\floor_manager.py", r"modules\desktop_interaction.py"]


def read(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


total = 0
for rel in TARGETS:
    fp = os.path.join(SRC, rel)
    src = read(fp)
    lines = src.splitlines()
    tree = ast.parse(src)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            body = [b for b in node.body if not (isinstance(b, ast.Expr)
                                                 and isinstance(b.value, ast.Constant)
                                                 and isinstance(b.value.value, str))]
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                hits.append((node.lineno, node.name or "-"))
    print("=" * 70)
    print("%s —— 静默 pass %d 处" % (rel, len(hits)))
    print("=" * 70)
    for ln, nm in hits:
        # 往上找 try 的那一行，给出上下文
        ctx = []
        for k in range(max(0, ln - 4), min(len(lines), ln + 1)):
            ctx.append("      %5d|%s" % (k + 1, lines[k]))
        print("  --- line %d (as %s) ---" % (ln, nm))
        print("\n".join(ctx))
    total += len(hits)
    print()
print("合计静默 pass = %d" % total)

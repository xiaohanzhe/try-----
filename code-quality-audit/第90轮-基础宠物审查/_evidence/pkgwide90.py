# -*- coding: utf-8 -*-
u"""第90轮 · 全包（105 个 .py）核验：裸 except / if True / True==True（只读，ast.parse 不产 .pyc）

输出（2026-10-05 实测）：
    扫描 .py 文件数 = 105
    裸 except    = 0
    if True:     = 0
    True==True   = 0
"""
import ast
import io
import os

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"


def main():
    bare = iftrue = taut = files = bad_syntax = 0
    sites = []
    for dp, _dn, fn in os.walk(ROOT):
        if any(x in dp for x in ("__pycache__", ".git")):
            continue
        for f in fn:
            if not f.endswith(".py"):
                continue
            p = os.path.join(dp, f)
            files += 1
            try:
                s = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            try:
                t = ast.parse(s)
            except SyntaxError:
                bad_syntax += 1
                continue
            for n in ast.walk(t):
                if isinstance(n, ast.ExceptHandler) and n.type is None:
                    bare += 1
                    sites.append((os.path.relpath(p, ROOT), n.lineno, "bare except"))
                if (isinstance(n, ast.If) and isinstance(n.test, ast.Constant)
                        and n.test.value is True):
                    iftrue += 1
                    sites.append((os.path.relpath(p, ROOT), n.lineno, "if True"))
                if isinstance(n, ast.Compare) and len(n.comparators) == 1:
                    l, r = n.left, n.comparators[0]
                    if (isinstance(l, ast.Constant) and isinstance(r, ast.Constant)
                            and l.value is True and r.value is True):
                        taut += 1
                        sites.append((os.path.relpath(p, ROOT), n.lineno, "True==True"))
    print("扫描 .py 文件数 =", files)
    print("语法解析失败   =", bad_syntax)
    print("裸 except      =", bare)
    print("if True:       =", iftrue)
    print("True==True     =", taut)
    for s in sites[:20]:
        print("   ", s)


if __name__ == "__main__":
    main()

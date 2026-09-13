# -*- coding: utf-8 -*-
"""AST 静态扫描：寻找高风险代码模式候选（供人工复核）"""
import ast
import os
import sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
TARGETS = ["src", "modules"]

SKIP_DIRS = {"__pycache__", ".git"}


def iter_files():
    for t in TARGETS:
        base = os.path.join(ROOT, t)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(".py"):
                    yield os.path.join(dirpath, fn)


def lineno(node):
    return getattr(node, "lineno", "?")


def main():
    findings = {
        "randint_risk": [],
        "division": [],
        "while_true": [],
        "sleep": [],
        "bare_except": [],
        "except_pass": [],
        "destructive": [],
        "eval_exec": [],
        "subprocess": [],
        "qtimer": [],
        "global_var": [],
    }
    for path in iter_files():
        rel = os.path.relpath(path, ROOT)
        try:
            with open(path, encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src)
        except SyntaxError as e:
            print(f"SYNTAX_ERROR {rel}: {e}")
            continue

        for node in ast.walk(tree):
            # random.randint / randrange / uniform / choice 边界
            if isinstance(node, ast.Call):
                fn = node.func
                name = None
                if isinstance(fn, ast.Attribute):
                    name = fn.attr
                elif isinstance(fn, ast.Name):
                    name = fn.id
                if name in ("randint", "randrange", "uniform", "randint_range"):
                    args = [ast.unparse(a) for a in node.args]
                    findings["randint_risk"].append(f"{rel}:{lineno(node)}: {name}({', '.join(args)})")
                if name == "sleep":
                    findings["sleep"].append(f"{rel}:{lineno(node)}: time.sleep({ast.unparse(node.args[0]) if node.args else ''})")
                if name in ("eval", "exec"):
                    findings["eval_exec"].append(f"{rel}:{lineno(node)}: {ast.unparse(node)}")
                if name in ("rmtree", "unlink", "remove"):
                    findings["destructive"].append(f"{rel}:{lineno(node)}: {ast.unparse(node)}")

            # 除法
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                left = ast.unparse(node.left)
                findings["division"].append(f"{rel}:{lineno(node)}: {left} {type(node.op).__name__}")

            # while True
            if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
                findings["while_true"].append(f"{rel}:{lineno(node)}")

            # bare except / except: pass
            if isinstance(node, ast.Try):
                for h in node.handlers:
                    if h.type is None:
                        findings["bare_except"].append(f"{rel}:{lineno(h)}")
                    if h.type is None and len(h.body) == 1 and isinstance(h.body[0], ast.Pass):
                        pass

            # QTimer 创建
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Attribute) and fn.attr in ("QTimer", "start"):
                    if isinstance(fn.value, ast.Name) and fn.value.id in ("QTimer", "self"):
                        findings["qtimer"].append(f"{rel}:{lineno(node)}: {ast.unparse(node)[:80]}")

            # 模块级可变全局
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    if isinstance(t, ast.Name) and isinstance(node.value, (ast.Dict, ast.List, ast.Set)):
                        findings["global_var"].append(f"{rel}:{lineno(node)}: {t.id}")

    for k, v in findings.items():
        print(f"\n===== {k} ({len(v)}) =====")
        for item in v[:60]:
            print(" ", item)


if __name__ == "__main__":
    main()

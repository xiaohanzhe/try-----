# -*- coding: utf-8 -*-
"""决定性验证：证明 main.py::_tick_spell_flow 引用的 current_time 是未绑定全局名。

方法：
1) 找出该方法 AST 节点，提取源码单独 compile；
2) 反汇编，查看 LOAD_GLOBAL 的名字集合 —— 若出现 current_time 即为全局查找；
3) 扫描整个 main.py 的模块级（顶层）赋值，确认 current_time 从未在模块层被绑定；
4) 同时列出该方法内部的局部名，确认 current_time 不是局部变量。
只读，不修改任何文件。
"""
import ast
import dis
import io
import sys

PATH = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src\main.py"

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()
lines = src.splitlines()
tree = ast.parse(src)

target = None
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "_tick_spell_flow":
        target = node
        break

if target is None:
    print("NOT FOUND")
    sys.exit(1)

print("=== 目标方法 ===")
print("_tick_spell_flow  @ line", target.lineno, "-", target.end_lineno)

# 1) 提取方法体源码（去掉装饰器后按缩进还原）
frag = "\n".join(lines[target.lineno - 1: target.end_lineno])
# 统一去掉一层 4 空格缩进，使其可独立编译
dedented = "\n".join(
    (ln[4:] if ln.startswith("    ") else ln) for ln in frag.splitlines()
)

# 2) 包装成模块级函数以便单独编译
mod_src = "def _f(self):\n" + "\n".join("    " + ln for ln in dedented.splitlines())
code = compile(mod_src, "<probe>", "exec")

# 找到内部函数的 code object
ns = {}
exec(code, ns)
fn = ns["_f"]

global_names = set()
local_names = set()


def walk_codes(c):
    global_names.update(c.co_names)
    local_names.update(c.co_varnames)
    for const in c.co_consts:
        if hasattr(const, "co_names"):
            walk_codes(const)


walk_codes(fn.__code__)

print()
print("=== 该方法及内嵌函数引用的【全局名】 ===")
print(sorted(global_names))
print()
print("是否出现 current_time :", "current_time" in global_names)

# 3) 模块顶层赋值扫描
toplevel_assigns = set()
for node in tree.body:  # 只遍历顶层
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name):
                toplevel_assigns.add(t.id)
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        toplevel_assigns.add(node.target.id)
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
        for a in node.names:
            toplevel_assigns.add((a.asname or a.name).split(".")[0])

print()
print("=== 模块顶层是否绑定过 current_time ===")
print("current_time in module globals:", "current_time" in toplevel_assigns)
print("模块顶层名数量:", len(toplevel_assigns))

# 4) 反汇编定位 LOAD_GLOBAL
print()
print("=== 反汇编中所有 current_time 相关指令 ===")
found = []


def dis_code(c, depth=0):
    for ins in dis.get_instructions(c):
        if "current_time" in str(ins.argval) or "current_time" in str(ins.argrepr):
            found.append((depth, ins.offset, ins.opname, ins.argval, ins.argrepr))
    for const in c.co_consts:
        if hasattr(const, "co_names"):
            dis_code(const, depth + 1)


dis_code(fn.__code__)
for row in found:
    print(row)
print()
print("current_time 指令条数:", len(found))
print()
print("=== 结论 ===")
if "current_time" in global_names and "current_time" not in toplevel_assigns:
    print(">>> 已证实：current_time 在方法内以 LOAD_GLOBAL 方式解析，")
    print(">>> 而模块顶层从未绑定该名字 => 运行到该行必然抛 NameError。")
else:
    print(">>> 未证实，需要进一步检查。")

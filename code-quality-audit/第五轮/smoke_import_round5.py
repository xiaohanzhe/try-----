# -*- coding: utf-8 -*-
"""第五轮收尾：全模块导入冒烟（无 GUI 实例化）+ 关键不变量检查。只读。"""
import io
import os
import re
import sys
import traceback

BASE = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
MODS = os.path.join(BASE, "modules")
sys.path.insert(0, MODS)
sys.path.insert(0, os.path.join(BASE, "src"))
for m in ("src", "modules"):
    sys.path.insert(0, os.path.join(BASE, m))

fail = []
files = sorted(f for f in os.listdir(MODS) if f.endswith(".py") and f != "__init__.py")
print("待导入模块数:", len(files))
for f in files:
    name = f[:-3]
    try:
        __import__(name)
        print("  [ OK ]", name)
    except Exception as e:
        fail.append((name, traceback.format_exc(limit=3)))
        print("  [FAIL]", name, "->", e)

print()
print("导入失败数:", len(fail))
for n, tb in fail:
    print("----", n)
    print(tb)

# 关键不变量：main.py 的 _tick_spell_flow 里不允许再出现未定义的裸 current_time 引用
# 注意：必须剔除注释（本次修复的说明注释里含该词，朴素的全文 grep 会误报）。
MAIN = os.path.join(BASE, "src", "main.py")
src = io.open(MAIN, encoding="utf-8").read()
body = src.split("def _tick_spell_flow", 1)[1].split("\n    def ", 1)[0]
code_only = "\n".join(
    (ln.split("#", 1)[0] if "#" in ln else ln) for ln in body.splitlines()
)
n_bad = len(re.findall(r"(?<!self\.)\bcurrent_time\b", code_only))
print()
print("_tick_spell_flow 代码体（已剔除注释）中残留裸 current_time 次数:", n_bad, "(应为 0)")
for ln in code_only.splitlines():
    if re.search(r"(?<!self\.)\bcurrent_time\b", ln):
        print("   >>> 命中行:", ln.strip())

# 不变量：动作分支必须早于宽泛名词分支
di = io.open(os.path.join(MODS, "dialogue_system.py"), encoding="utf-8").read()
i_opt = di.find('elif "优化" in user_input_lower')
i_file = di.find('elif "文件" in user_input_lower or "文档" in user_input_lower')
print("优化分支位置", i_opt, " 文件分支位置", i_file, " 动作优先:", 0 < i_opt < i_file)

sys.exit(1 if (fail or n_bad != 0) else 0)

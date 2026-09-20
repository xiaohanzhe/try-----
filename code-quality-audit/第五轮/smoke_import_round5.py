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

# 关键不变量：_tick_spell_flow 里不允许再出现未定义的裸 current_time 引用
# 注意：必须剔除注释（本次修复的说明注释里含该词，朴素的全文 grep 会误报）。
#
# H4/H5 W1-1：`_tick_spell_flow` 已搬进 modules/spell_controller.py。
# 原来这里靠 `src.split("def _tick_spell_flow", 1)[1]` 切 main.py 源码 ——
# 搬走后切不到 → IndexError 崩掉整个套件（症状同 round5_verify：
# exit=1 但 FAIL=0，容易被误读成断言失败）。
# 修**定位器**（跨模块找方法并切源码），**不动产品代码、不动基线**。
# ⚠️ 严禁弱化成"找不到就跳过"（= 悄悄扔锁）。
import ast

_CANDIDATES = [
    (os.path.join(BASE, "src", "main.py"), "RalseiPet"),
    (os.path.join(MODS, "spell_controller.py"), "SpellFlowController"),
    (os.path.join(MODS, "games_controller.py"), "GamesController"),
    (os.path.join(MODS, "video_controller.py"), "VideoController"),
]


def _extract_func_body(fname):
    """跨模块提取方法源码（返回源码串，找不到返回 None）。"""
    for path, cls_name in _CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            s = io.open(path, encoding="utf-8").read()
            t = ast.parse(s)
        except Exception:
            continue
        scope = t
        if cls_name:
            scope = None
            for n in t.body:
                if isinstance(n, ast.ClassDef) and n.name == cls_name:
                    scope = n
                    break
            if scope is None:
                continue
        for n in ast.walk(scope):
            if isinstance(n, ast.FunctionDef) and n.name == fname:
                ls = s.splitlines()
                return "\n".join(ls[n.lineno - 1:n.end_lineno])
    return None


body = _extract_func_body("_tick_spell_flow")
if body is None:
    print()
    print("!! 定位器失败：_tick_spell_flow 在 %d 个候选模块里都没找到"
          % len(_CANDIDATES))
    print("!! 这是**定位器过时**，不是产品回归 —— 请更新 _CANDIDATES 而不是删锁。")
    sys.exit(2)
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

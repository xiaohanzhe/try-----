# -*- coding: utf-8 -*-
"""第 35 轮 —— 动画名比对 v2（精确口径，取代 v1 的宽分类器）。

v1 的教训：用「形似动画名的前缀」做筛，抓出 96 个"缺失"，其中绝大多数是
变量名/参数名/状态名（fall_speed、jump_phase、pet_ai…）—— **分类器太宽**。

v2 改为**只取真正流进动画 API 的字符串**：
    change_animation(<str>)          —— 直接改动画
    play_animation_once(<str>, ...)  —— 播一次
    sprite_loader.get_animation_files(<str>)
并额外做**前缀到达性**分析：对 f-string 拼出来的名字（如 f"walk_{dir}"）
不可能静态枚举，单独列为"动态拼接，需实测"。

对每个字面量核验：是否在 animations.json 的 groups 中（或 sprite_loader 别名）。
"""
import ast
import json
import os
import re

WS = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PET = os.path.join(WS, "ralsei_pet")
EV = os.path.join(WS, "code-quality-audit", "第35轮-真机用户视角10分钟监测", "_evidence")

anim = json.load(open(os.path.join(PET, "assets", "animations.json"), encoding="utf-8"))
GROUPS = set(anim.get("groups", {}).keys())

# sprite_loader 会把这些别名映射到真实动画（含 _butler/_blush/_unhappy 等后缀族）
sl = open(os.path.join(PET, "modules", "sprite_loader.py"), encoding="utf-8").read()
for m in re.finditer(r'["\']([a-zA-Z][a-zA-Z0-9_]{2,})["\']\s*:', sl):
    GROUPS.add(m.group(1))

APIS = {"change_animation", "play_animation_once", "get_animation_files",
        "add_animation", "on_animation_complete"}

hits = []      # (literal, api, file, line)
dynamic = []   # f-string 拼名，静态不可判


def scan(path, rel):
    try:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
    except Exception:
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = None
        if isinstance(fn, ast.Attribute):
            name = fn.attr
        elif isinstance(fn, ast.Name):
            name = fn.id
        if name not in APIS:
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                hits.append((arg.value, name, rel, node.lineno))
            elif isinstance(arg, ast.JoinedStr):
                # f-string：取字面量片段拼出"形状"
                parts = []
                for v in arg.values:
                    if isinstance(v, ast.Constant) and isinstance(v.value, str):
                        parts.append(v.value)
                    else:
                        parts.append("{?}")
                dynamic.append(("".join(parts), name, rel, node.lineno))


for root, dirs, files in os.walk(PET):
    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "tests", "regress")]
    for fn in files:
        if fn.endswith(".py"):
            p = os.path.join(root, fn)
            scan(p, os.path.relpath(p, WS))

L = []
L.append("第35轮 动画名比对 v2（精确口径：只取流入动画 API 的字符串）")
L.append("=" * 66)
L.append("资源侧可解析动画名: %d" % len(GROUPS))
L.append("静态字面量调用: %d 处" % len(hits))
L.append("f-string 动态拼名: %d 处" % len(dynamic))
L.append("")

miss = [h for h in hits if h[0] not in GROUPS]
ok = [h for h in hits if h[0] in GROUPS]
L.append("【静态字面量核验】")
L.append("  命中资源: %d" % len(ok))
L.append("  ★ 未命中资源: %d" % len(miss))
L.append("-" * 66)
seen = set()
for lit, api, rel, ln in sorted(miss):
    if lit in seen:
        continue
    seen.add(lit)
    L.append("  %-24s <- %s  (%s:%d)" % (lit, api, rel.replace("ralsei_pet\\", ""), ln))
L.append("")

L.append("【f-string 动态拼名】（静态不可判，列出形状供实测对照）")
L.append("-" * 66)
seen2 = set()
for shape, api, rel, ln in sorted(dynamic):
    k = (shape, api)
    if k in seen2:
        continue
    seen2.add(k)
    L.append("  %-34s <- %s  (%s:%d)" % (shape, api, rel.replace("ralsei_pet\\", ""), ln))
L.append("")

# 对动态拼名做"形状可达性"检查：把 {?} 换成资源里的已知片段逐个组合
L.append("【动态拼名可达性抽检】")
L.append("-" * 66)
DIRS = ["down", "left", "right", "up"]
SUF = ["", "_blush", "_unhappy", "_butler", "_butler_unhappy", "_sleep", "_tea"]
for shape, api, rel, ln in sorted(set((s, a, r, l) for s, a, r, l in dynamic)):
    if "{?}" not in shape:
        continue
    cands = []
    hyphens = shape.count("{?}")
    if hyphens == 1:
        base, tail = shape.split("{?}")
        for d in DIRS:
            cands.append(base + d + tail)
    elif hyphens == 2:
        a1, rest = shape.split("{?}", 1)
        b1, tail = rest.split("{?}", 1)
        for d in DIRS:
            for s2 in SUF:
                cands.append(a1 + d + b1 + s2 + tail)
    bad = [c for c in cands if c not in GROUPS]
    good = [c for c in cands if c in GROUPS]
    L.append("  %s  (%s:%d)" % (shape, rel.replace("ralsei_pet\\", ""), ln))
    L.append("      可达 %d / 不可达 %d" % (len(good), len(bad)))
    if bad:
        L.append("      不可达样例: %s" % ", ".join(bad[:8]))

dst = os.path.join(EV, "36_动画名比对v2_精确口径.txt")
open(dst, "w", encoding="utf-8").write("\n".join(L))
print("\n".join(L))
print()
print("WROTE", dst)

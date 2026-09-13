# -*- coding: utf-8 -*-
"""H5 前置分析：代码引用的动画名 vs animation_mapping 已定义的键

目的：确定"配置化"必须守住的契约面。
如果代码里 change_animation("xxx") / play_animation_once("xxx") 用到的名字
在 mapping 中不存在，动画会静默退化为 idle —— 这是 H5 改造的验收红线。

只读。产物：_evidence/animation_name_contract.txt
"""
import ast
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'ralsei_pet', 'src')
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
SPRITE = os.path.join(MODS, 'sprite_loader.py')

# --- 已定义的动画组键 ---
s_tree = ast.parse(open(SPRITE, encoding='utf-8').read())
keys = set()
for node in ast.walk(s_tree):
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Attribute) and t.attr == 'animation_mapping' and isinstance(node.value, ast.Dict):
                for k in node.value.keys:
                    if isinstance(k, ast.Str):
                        keys.add(k.s)

# --- 代码中动画相关调用的字面量参数 ---
# (?<![A-Za-z_]) 防止把 base_animation / new_animation 误判成 animation ==
API = re.compile(r'(?<![A-Za-z_])(?:change_animation|play_animation_once|play_animation|'
                 r'current_animation\s*==|animation\s*==|is_own_animation)\s*\(?\s*[\'\"]'
                 r'([A-Za-z0-9_]+)[\'\"]')

referenced = {}
for d in (SRC, MODS):
    for fn in os.listdir(d):
        if not fn.endswith('.py'):
            continue
        p = os.path.join(d, fn)
        txt = open(p, encoding='utf-8', errors='ignore').read()
        for m in API.finditer(txt):
            referenced.setdefault(m.group(1), set()).add(fn)

missing = sorted(n for n in referenced if n not in keys)
ok = sorted(n for n in referenced if n in keys)
never_used = sorted(keys - set(referenced))

L = []
L.append('=== 动画名契约（H5 验收红线）===')
L.append('mapping 已定义键: %d' % len(keys))
L.append('代码中以"动画名"形式出现的字面量: %d' % len(referenced))
L.append('  -> 已被 mapping 覆盖: %d' % len(ok))
L.append('  -> mapping 中缺失（运行时静默退化 idle）: %d' % len(missing))
L.append('mapping 定义了但代码从不引用: %d' % len(never_used))
L.append('')
L.append('--- 缺失名单（每项=一处潜在静默失效）---')
for n in missing:
    L.append('   %-34s  引用自: %s' % (n, ', '.join(sorted(referenced[n]))))
L.append('')
L.append('--- 定义了但零引用（配置化时可标注 legacy）---')
L.append('   ' + ', '.join(never_used))

# --- 动态拼接点：静态扫描看不见，却是"配置缺失"的高发区 ---
DYN = re.compile(r'(?<![A-Za-z_])(?:change_animation|play_animation_once|_change_anim|'
                 r'play_animation)\s*\(\s*f[\'"]([^\'"]*)')
dyn_sites = []
for d in (SRC, MODS):
    for fn in os.listdir(d):
        if not fn.endswith('.py'):
            continue
        txt = open(os.path.join(d, fn), encoding='utf-8', errors='ignore').read()
        for m in DYN.finditer(txt):
            dyn_sites.append((fn, m.group(1)))

patterns = sorted({p for _, p in dyn_sites})
L.append('')
L.append('--- 动态拼接的动画名（静态扫描不可见，H5 必须靠运行时自检）---')
L.append('拼接点数量: %d，模板 %d 种' % (len(dyn_sites), len(patterns)))
for p in patterns:
    srcs = sorted({f for f, q in dyn_sites if q == p})
    L.append('   f"%s"   来源: %s' % (p, ', '.join(srcs)))
L.append('')
L.append('!!! 结论：上面 %d 个"零引用"键不能直接判为 legacy —— 其中 walk_/run_/walk_tea_ 等' % len(never_used))
L.append('    键由 f-string 在运行时拼出（如 walk_{direction}、run_{direction}），静态不可见。')
L.append('    H5 配置化的第一步不是搬字面量，而是给 change_animation 加"未命中即告警"的自检。')

txt = '\n'.join(L)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_evidence', 'animation_name_contract.txt')
open(out, 'w', encoding='utf-8').write(txt)
print(txt)

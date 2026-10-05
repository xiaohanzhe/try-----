# -*- coding: utf-8 -*-
u"""第90轮 · 定位"内置台词"：speak_event / add_dialogue / dialogue 字面量（只读）"""
import ast
import io
import os
import re

SRC = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
CJK = re.compile(u'[\u4e00-\u9fff]')
CALLS = ('speak_event', 'add_dialogue', 'add_dialogue_line', 'speak',
         'show_dialogue', 'say')


def read(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


total = 0
per_file = []
for root, _d, fs in os.walk(SRC):
    if any(x in root for x in ("__pycache__", ".git", "_scratch")):
        continue
    for fn in fs:
        if not fn.endswith(".py"):
            continue
        fp = os.path.join(root, fn)
        rel = os.path.relpath(fp, SRC)
        if rel.startswith(("test_", "regress", "code-quality")):
            continue
        src = read(fp)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        hits = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            nm = f.id if isinstance(f, ast.Name) else (
                f.attr if isinstance(f, ast.Attribute) else None)
            if nm not in CALLS:
                continue
            # 该调用里任何一个字符串字面量含中文 ⇒ 记为"内置台词"
            lits = [n.value for n in ast.walk(node)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            zh = [s for s in lits if CJK.search(s)]
            if zh:
                hits.append((node.lineno, nm, zh))
        if hits:
            per_file.append((rel, hits))
            total += sum(len(h[2]) for h in hits)

per_file.sort(key=lambda x: -sum(len(h[2]) for h in x[1]))
print('=' * 72)
print('内置台词（调用点内的中文字面量）分布')
print('=' * 72)
for rel, hits in per_file:
    n_call = len(hits)
    n_str = sum(len(h[2]) for h in hits)
    print('  %-38s 调用点 %-4d 字面量 %d' % (rel, n_call, n_str))
print('  ---- 合计字面量 =', total)
print()
print('★ 明细（前 60 条）')
shown = 0
for rel, hits in per_file:
    for ln, nm, zh in hits:
        if shown >= 60:
            break
        print('  %s:%d  %s(%s)' % (rel, ln, nm, ' | '.join(s[:26] for s in zh[:3])))
        shown += 1
    if shown >= 60:
        break

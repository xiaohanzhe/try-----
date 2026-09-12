# -*- coding: utf-8 -*-
"""审计 react_to_event 的事件覆盖度：
- handled: emotion_system.react_to_event 中 event_type == 'X' 的分支
- triggered: 全项目 react_to_event('X') / trigger_event('X') 调用的字面量
- 输出 triggered - handled
"""
import ast, os

ROOT = os.path.dirname(os.path.abspath(__file__))
PET = os.path.join(ROOT, 'ralsei_pet')

def read(p):
    with open(p, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()

es = os.path.join(PET, 'modules', 'emotion_system.py')
t = ast.parse(read(es))

handled = set()
triggered = {}   # event -> [(file,line)]

def walk_calls(tree, fp):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = None
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        if name in ('react_to_event', 'trigger_event'):
            arg = node.args[0] if node.args else None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                triggered.setdefault(arg.value, []).append((os.path.relpath(fp, ROOT), node.lineno))

# 收集 react_to_event 内部的分支（只在该函数体内）
target_fn = None
for node in ast.walk(t):
    if isinstance(node, ast.FunctionDef) and node.name == 'react_to_event':
        target_fn = node
        break
if target_fn:
    for node in ast.walk(target_fn):
        if isinstance(node, ast.Compare):
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, ast.Eq) and isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                    # 只认 event_type == 'X'
                    if isinstance(node.left, ast.Name) and node.left.id == 'event_type':
                        handled.add(comp.value)

for dirpath, _, filenames in os.walk(PET):
    if '__pycache__' in dirpath:
        continue
    for fn in filenames:
        if fn.endswith('.py'):
            fp = os.path.join(dirpath, fn)
            try:
                walk_calls(ast.parse(read(fp)), fp)
            except Exception:
                pass

unhandled = {k: v for k, v in triggered.items() if k not in handled}

out = []
out.append("== react_to_event 已处理事件 (%d) ==" % len(handled))
out.append("   " + ", ".join(sorted(handled)))
out.append("")
out.append("== 全项目被触发的事件 (%d) ==" % len(triggered))
out.append("   " + ", ".join(sorted(triggered)))
out.append("")
out.append("== 被触发但【未处理】的事件 (%d) ==" % len(unhandled))
for k in sorted(unhandled):
    locs = unhandled[k]
    out.append("   %-32s 触发 %d 处: %s" % (k, len(locs), ", ".join("%s:%d" % x for x in locs[:4])))

with open(os.path.join(ROOT, '_audit_events_out.txt'), 'w', encoding='utf-8') as f:
    f.write("\n".join(out))
print("handled=%d triggered=%d unhandled=%d" % (len(handled), len(triggered), len(unhandled)))

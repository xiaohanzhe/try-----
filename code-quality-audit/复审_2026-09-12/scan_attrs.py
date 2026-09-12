
import ast, os, sys, json, collections

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
files = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    if '__pycache__' in dirpath: continue
    for fn in filenames:
        if fn.endswith('.py') and not fn.startswith('test_') and not fn.startswith('diag'):
            files.append(os.path.join(dirpath, fn))

report = {}
for path in files:
    src = open(path, encoding='utf-8', errors='replace').read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        report[path] = {'syntax_error': str(e)}
        continue
    info = {'classes': {}, 'globals': set(), 'bare_excepts': [], 'silent_excepts': [], 'div': [], 'index0': []}
    # 收集顶层函数
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info['globals'].add(node.name)
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name): info['globals'].add(t.id)
    class MethodCollector(ast.NodeVisitor):
        def __init__(self):
            self.stack = []
        def visit_ClassDef(self, node):
            cls = {'methods': set(), 'assigned': set(), 'used': [], 'bases': [ast.unparse(b) for b in node.bases]}
            for b in node.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    cls['methods'].add(b.name)
            self.stack.append((node.name, cls))
            self.generic_visit(node)
            self.stack.pop()
            info['classes'][node.name] = cls
        def visit_Attribute(self, node):
            if isinstance(node.value, ast.Name) and node.value.id == 'self' and self.stack:
                cls = self.stack[-1][1]
                if isinstance(node.ctx, ast.Store):
                    cls['assigned'].add(node.attr)
                else:
                    cls['used'].append((node.attr, node.lineno))
            self.generic_visit(node)
        def visit_AugAssign(self, node):
            if isinstance(node.target, ast.Attribute) and isinstance(node.target.value, ast.Name) and node.target.value.id == 'self' and self.stack:
                self.stack[-1][1]['assigned'].add(node.target.attr)
            self.generic_visit(node)
    MethodCollector().visit(tree)
    # 异常 / 除零 / 下标扫描
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            body = node.body
            is_bare = node.type is None
            silent = all(isinstance(s, ast.Pass) for s in body)
            if is_bare:
                info['bare_excepts'].append(node.lineno)
            if silent:
                info['silent_excepts'].append(node.lineno)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            rhs = node.right
            safe = isinstance(rhs, ast.Constant) and rhs.value not in (0, 0.0)
            if not safe:
                info['div'].append((node.lineno, ast.unparse(node)[:80]))
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and node.slice.value in (0, -1):
            info['index0'].append((node.lineno, ast.unparse(node)[:80]))
    report[path] = info

# 输出属性缺失分析
print("======== 属性引用但从未赋值/定义（潜在 AttributeError） ========")
for path, info in report.items():
    if 'classes' not in info: continue
    for cname, cls in info['classes'].items():
        known = cls['methods'] | cls['assigned']
        missing = collections.Counter()
        for attr, ln in cls['used']:
            if attr not in known and not attr.startswith('__'):
                missing[attr] += 1
        if missing:
            items = sorted(missing.items(), key=lambda x: -x[1])
            print(f"\n-- {os.path.relpath(path, ROOT)} :: class {cname} --")
            print("   " + ", ".join(f"{a}({n})" for a, n in items[:40]))
print()
print("======== 裸 except / 静默 except 统计 ========")
for path, info in report.items():
    if 'classes' not in info: continue
    if info['bare_excepts'] or info['silent_excepts']:
        print(os.path.relpath(path, ROOT), "bare:", info['bare_excepts'][:20], "silent-pass:", info['silent_excepts'][:20])

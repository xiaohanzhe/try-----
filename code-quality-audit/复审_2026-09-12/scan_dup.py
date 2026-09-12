
import ast, os, hashlib, collections

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
files = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    if '__pycache__' in dirpath: continue
    for fn in filenames:
        if fn.endswith('.py') and not fn.startswith(('test_','diag')):
            files.append(os.path.join(dirpath, fn))

def norm(node):
    """结构归一化：忽略常量值和变量名，只保留语句/调用结构"""
    class N(ast.NodeTransformer):
        def visit_Name(self, n): return ast.Name(id='V', ctx=n.ctx)
        def visit_Constant(self, n): return ast.Constant(value='C')
        def visit_Attribute(self, n):
            self.generic_visit(n); return ast.Attribute(value=n.value, attr='A', ctx=n.ctx)
        def visit_arg(self, n): return ast.arg(arg='a')
    n = N().visit(ast.parse(ast.unparse(node)))
    return ast.dump(n)

groups = collections.defaultdict(list)
funcs = []
for path in files:
    src = open(path, encoding='utf-8', errors='replace').read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            # 去掉 docstring
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                body = body[1:]
            if len(body) < 4:   # 太短的忽略
                continue
            key = hashlib.md5(norm(ast.Module(body=body, type_ignores=[])).encode()).hexdigest()
            groups[key].append((os.path.relpath(path, ROOT), node.name, node.lineno, len(body)))

print("======== 结构完全相同的函数组（重复编码） ========")
n_dup = 0
for key, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    if len(items) < 2: continue
    n_dup += 1
    print(f"\n[组{n_dup}] {len(items)} 个函数体结构相同：")
    for path, name, line, size in items:
        print(f"    {path}:{line}  def {name}  ({size} 语句)")
if n_dup == 0:
    print("（无）")

print()
print("======== 结构高度相似的函数组（>=2 且规模>15语句，可能模板复制） ========")
# 用粗粒度签名：调用名序列
sig = collections.defaultdict(list)
for path in files:
    src = open(path, encoding='utf-8', errors='replace').read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and len(node.body) >= 15:
            calls = []
            for n in ast.walk(node):
                if isinstance(n, ast.Call):
                    try: calls.append(ast.unparse(n.func).split('.')[-1])
                    except Exception: pass
            if len(calls) >= 8:
                sig[tuple(calls)].append((os.path.relpath(path, ROOT), node.name, node.lineno, len(node.body)))
m = 0
for k, items in sorted(sig.items(), key=lambda kv: -len(kv[1])):
    if len(items) < 3: continue
    m += 1
    print(f"\n[相似组{m}] 调用序列相同 ({len(items)} 个): {', '.join(k[:6])}...")
    for path, name, line, size in items:
        print(f"    {path}:{line}  def {name} ({size} statements)")
if m == 0: print("（无）")

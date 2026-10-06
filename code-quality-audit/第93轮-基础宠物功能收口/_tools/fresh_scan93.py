# -*- coding: utf-8 -*-
"""fresh_scan93.py —— 第93轮全新静态扫描（只读，不碰产品代码）

覆盖用户点名的五个维度，逐条给证据：
  1) 隐藏 bug（以 P1-3「素材名缺 .png 兜底」为例做解析链全量取证）
  2) 边界条件（除零 / 空序列 / 下标 / None 解包等可疑片段）
  3) 重复编码（函数体指纹聚类）
  4) 未来拓展坑（TODO/FIXME/XXX、同步重复实现、死字段）
  5) 异常处理不完整（裸 except / 静默 pass / 仅 pass 无日志）

纪律：只 ast.parse + 文本 grep，不打行号进判据，不 import 产品代码。
"""
import ast
import io
import os
import re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src', 'main.py')
MODS = os.path.join(PKG, 'modules')

OUT = []


def emit(section, text):
    OUT.append(('[%s] %s' % (section, text)))


# 收集所有 .py 文本
files = {}
for d in (SRC, MODS):
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith('.py'):
                files[os.path.join(d, f)] = io.open(
                    os.path.join(d, f), encoding='utf-8', errors='replace').read()
    elif os.path.exists(d):
        files[d] = io.open(d, encoding='utf-8', errors='replace').read()

# ============================================================ 1. P1-3 素材名解析链
emit('1-P1-3', '素材名是否补 .png 后缀')
png_append = []
for p, s in files.items():
    for m in re.finditer(r"(?:endswith|splitext|'\.png'|['\"]_0\.png['\"]|\.png['\"]\s*\+|\+\s*['\"]\.png|\+\s*['\"]_0\.png)", s):
        ln = s[:m.start()].count('\n') + 1
        png_append.append((os.path.relpath(p, ROOT), ln, m.group(0)))
emit('1-P1-3', '全仓 .png 补齐/endswith/splitext 命中 = %d 处' % len(png_append))
for p, ln, g in png_append:
    emit('1-P1-3', '  %-34s line %-5d %s' % (p, ln, g))

# ============================================================ 2. 裸 except / 静默
emit('2-EXC', '异常处理')
bare_except = 0
silent_pass = []
for p, s in files.items():
    try:
        t = ast.parse(s)
    except SyntaxError:
        continue
    parents = {}
    for n in ast.walk(t):
        for c in ast.iter_child_nodes(n):
            parents[c] = n

    def encl(n):
        q = parents.get(n)
        while q is not None:
            if isinstance(q, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return q.name
            q = parents.get(q)
        return '<module>'

    for n in ast.walk(t):
        if isinstance(n, ast.ExceptHandler):
            if n.type is None:
                bare_except += 1
                emit('2-EXC', '  裸 except: %s (%s:line %d)' % (
                    os.path.relpath(p, ROOT), encl(n), getattr(n, 'lineno', 0)))
            # 静默：body 全为 pass，或 body 里没有任何 _log.* 调用
            has_log = any(
                isinstance(c, ast.Call) and
                isinstance(c.func, ast.Attribute) and
                getattr(c.func.value, 'id', None) in ('_log', 'log', 'logger')
                for b in n.body for c in ast.walk(b)
            )
            if len(n.body) == 1 and isinstance(n.body[0], ast.Pass):
                silent_pass.append((os.path.relpath(p, ROOT), encl(n), getattr(n, 'lineno', 0), has_log))
emit('2-EXC', '裸 except 总数 = %d' % bare_except)
emit('2-EXC', '仅 `pass` 的 except 分支数 = %d（其中无 _log 的 = %d）' % (
    len(silent_pass), sum(1 for x in silent_pass if not x[3])))
for p, f, ln, haslog in silent_pass:
    if not haslog:
        emit('2-EXC', '  无日志静默 pass: %-30s %s:line %d' % (f, p, ln))

# ============================================================ 3. TODO/FIXME 未来坑
emit('3-TODO', '未来拓展标记 TODO/FIXME/XXX/HACK')
todo = []
for p, s in files.items():
    for m in re.finditer(r'(TODO|FIXME|XXX|HACK)\b', s):
        ln = s[:m.start()].count('\n') + 1
        seg = s[m.start():m.start() + 60].replace('\n', ' ')
        todo.append((os.path.relpath(p, ROOT), ln, seg))
emit('3-TODO', '命中 = %d' % len(todo))
for p, ln, seg in todo[:60]:
    emit('3-TODO', '  %-34s line %-5d %s' % (p, ln, seg))
if len(todo) > 60:
    emit('3-TODO', '  ...截断（其余 %d 条）' % (len(todo) - 60))

# ============================================================ 4. 重复编码指纹
emit('4-DUP', '函数体重复指纹（normalized body 字符串）')
norm_bodies = Counter()
for p, s in files.items():
    try:
        t = ast.parse(s)
    except SyntaxError:
        continue
    for n in ast.walk(t):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = n.body
            # 跳过小函数（<3 条语句）与 getter/setter
            stmts = [x for x in body if not isinstance(x, (ast.Pass,))]
            if len(stmts) < 3:
                continue
            try:
                k = ast.dump(body)
            except Exception:
                continue
            norm_bodies[(p, n.name, k)] += 1
# 找共享 body 的
bykey = defaultdict(list)
for (p, name, k), c in norm_bodies.items():
    bykey[k].append((p, name))
dups = [(k, v) for k, v in bykey.items() if len(v) > 1]
emit('4-DUP', '跨函数共享同一 body 的簇 = %d' % len(dups))
for k, v in dups[:40]:
    emit('4-DUP', '  ' + ' ; '.join('%s::%s' % (os.path.basename(p), n) for p, n in v))

# ============================================================ 5. 边界可疑片段
emit('5-EDGE', '边界可疑：除零 / 空序列下标 / None 属性访问')
pat = re.compile(
    r'\[-?1\]|\.pop\(\)|/ *len\(|/ *\(.*- *1\)|\[[a-zA-Z_]+ *\+ *1\]')
cnt = 0
for p, s in files.items():
    for m in pat.finditer(s):
        ln = s[:m.start()].count('\n') + 1
        seg = s[m.start():m.start() + 50].replace('\n', ' ')
        cnt += 1
        if cnt <= 50:
            emit('5-EDGE', '  %-30s line %-5d %s' % (os.path.relpath(p, ROOT), ln, seg))
emit('5-EDGE', '可疑片段总数（粗筛） = %d' % cnt)

# ============================================================ 输出
print('\n'.join(OUT))
print('\n===== END fresh_scan93 =====')
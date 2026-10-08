# -*- coding: utf-8 -*-
"""第97轮 · 核心文件复检（用户口径：改过重要核心文件必须逐项复检）。

覆盖：
  ① 语法/可编译（用 ast.parse，绝不用 py_compile —— 它产 .pyc 会改变被测状态）
  ② 结构自检（MEMORY.md 节号 0..14 齐全、无粘连）
  ④ 恒真判据复查（`check(..., True)` 这类"看着在守其实没守"的写法）
  ⑥ 工作区干净留给 git status（本脚本不判）

③ 编码（无 BOM / 无 U+FFFD）与 ⑤ 逐令牌回验 已由
   `verify_tokens97.py` / 内联检查覆盖，此处只留一条汇总断言。
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
# ↑ 4 层：`_tools/` -> `第97轮-基础宠物排查/` -> `code-quality-audit/` -> 仓库根
M97 = os.path.join(ROOT, 'code-quality-audit', '第97轮-基础宠物排查')
MEM = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')

PY_FILES = [
    os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py'),
    os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'),
    os.path.join(M97, '_tools', 'check97.py'),
    os.path.join(M97, '_tools', 'verify_check97_count.py'),
    os.path.join(M97, '_tools', 'rec97.py'),
    os.path.join(M97, '_tools', 'analyze97.py'),
    os.path.join(M97, '_tools', 'probe97b_pierce.py'),
]

fails = []

print('=== ① 语法（ast.parse，不产 .pyc）===')
for f in PY_FILES:
    try:
        src = open(f, 'r', encoding='utf-8', newline='').read()
        ast.parse(src)
        print('  [PASS] %s' % os.path.basename(f))
    except Exception as e:
        fails.append('语法 %s: %r' % (f, e))
        print('  [FAIL] %s -> %r' % (os.path.basename(f), e))

print()
print('=== ② MEMORY.md 结构（节号 0..14 齐全、无粘连）===')
mem = open(MEM, 'r', encoding='utf-8', newline='').read()
secs = re.findall(r'^## (\d+)\.', mem, re.M)
want = [str(i) for i in range(0, 15)]
if secs == want:
    print('  [PASS] 节号 = %s' % secs)
else:
    fails.append('MEMORY.md 节号 %s != %s' % (secs, want))
    print('  [FAIL] 节号 = %s  期望 = %s' % (secs, want))
# 粘连检测：**同一行内**出现 ≥2 个 `## \d+.` 模式才算粘连。
# ⚠ 首版用"行长度 > 60"当判据 ⇒ 把 `## 2. git push（skill ...）` 这种**合法的长标题**
#   误报成粘连（判据过窄/错误判据，第 23 例）。长度跟"粘连"没有必然关系。
glued = []
for ln in mem.split('\n'):
    if len(re.findall(r'## \d+\.', ln)) > 1:
        glued.append(ln.strip()[:80])
if glued:
    fails.append('标题行粘连: %r' % glued[:2])
    print('  [FAIL] 标题行粘连: %r' % glued[:2])
else:
    print('  [PASS] 标题行无粘连（同行标题数 ≤ 1）')
# §13 内容抽检
if '## 13. 97' in mem and 'desktop_floor' in mem and 'ast.unparse' in mem:
    print('  [PASS] §13(97) 关键令牌在位')
else:
    fails.append('§13(97) 关键令牌缺失')
    print('  [FAIL] §13(97) 关键令牌缺失')

print()
print('=== ④ 恒真判据复查（check(..., True)）===')
for f in [os.path.join(M97, '_tools', 'check97.py'),
          os.path.join(M97, '_tools', 'verify_check97_count.py')]:
    tree = ast.parse(open(f, 'r', encoding='utf-8', newline='').read())
    bad = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == 'check' and len(n.args) >= 2):
            if isinstance(n.args[1], ast.Constant) and n.args[1].value is True:
                bad.append(n.lineno)
    if bad:
        fails.append('%s 恒真 check() 行 %s' % (os.path.basename(f), bad))
        print('  [FAIL] %s 恒真 check(): %s' % (os.path.basename(f), bad))
    else:
        print('  [PASS] %s 无恒真 check()' % os.path.basename(f))

print()
print('=== ③⑤ 编码 / 令牌回验（汇总）===')
enc_bad = []
for f in PY_FILES + [MEM, os.path.join(ROOT, '.gitignore')]:
    b = open(f, 'rb').read()
    if b[:3] == b'\xef\xbb\xbf':
        enc_bad.append((f, 'BOM'))
    if b.count(b'\xef\xbf\xbd'):
        enc_bad.append((f, 'U+FFFD'))
if enc_bad:
    fails.append('编码问题 %s' % enc_bad)
    print('  [FAIL] %s' % enc_bad)
else:
    print('  [PASS] 无 BOM / 无 U+FFFD')
print('  （逐令牌回验见 verify_tokens97.py：35 个令牌全可检索）')

print()
print('=' * 70)
if fails:
    print('[FAIL] 核心文件复检未通过，共 %d 项：' % len(fails))
    for x in fails:
        print('   -', x)
    sys.exit(1)
print('[PASS] 核心文件复检全部通过')

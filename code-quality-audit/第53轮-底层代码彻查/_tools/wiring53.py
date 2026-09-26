# -*- coding: utf-8 -*-
"""第53轮「底层代码彻查」· 模块接线图（只读）。

产出三块硬证据：
  (1) 每个 modules/*.py **被哪些生产代码文件 import**（不含 test_*/diag*/monitor_*）
  (2) **从未被任何生产代码 import 的模块** —— 模块级"零调用"
  (3) main.py 里对各控制器的**实例化点** + `importlib` 动态导入点
输出：_evidence/wiring.txt
"""
import ast
import io
import os
import re

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROOT, 'code-quality-audit', '第53轮-底层代码彻查', '_evidence')

JUNK = re.compile(r'^(test_|diag|monitor_|main_simple)')

out = []
W = out.append


def pyfiles(d):
    p = os.path.join(PET, d)
    return [os.path.join(p, n) for n in sorted(os.listdir(p))
            if n.endswith('.py')]


prod = [os.path.join(PET, 'src', 'main.py')]
for n in sorted(os.listdir(PET)):
    if n.endswith('.py') and not JUNK.match(n):
        prod.append(os.path.join(PET, n))
# 生产模块
mods = {}
for p in pyfiles('modules'):
    mods[os.path.basename(p)[:-3]] = p

importers = {m: set() for m in mods}
dyn = []
inst = []

for f in prod + pyfiles('modules'):
    rel = os.path.relpath(f, ROOT)
    try:
        src = io.open(f, encoding='utf-8').read()
        tree = ast.parse(src, filename=f)
    except Exception as e:
        W('!! parse fail %s %r' % (rel, e))
        continue
    for node in ast.walk(tree):
        # ★★ 修正（第 53 轮，本脚本的头号假阳性）：
        #   第一版只认 `import modules.X` 与 `from modules.X import Y`，
        #   漏掉两种真实写法 ⇒ 把一批**活着的**模块判成"无人 import"：
        #     (a) `from modules import bubble_system as bubble_system_mod`
        #         —— ImportFrom 的 module 正好等于 'modules'，子模块名在 names 里；
        #     (b) **函数体内的延迟导入** `import data_store`（为打断循环依赖刻意写在
        #         函数里，logger_utils / config_manager / entertainment_system /
        #         text_segmenter / social_growth_system / main.py 都是这个写法）。
        #   教训：判据过窄 ⇒ 误报"死模块"，比漏报更误导人。
        if isinstance(node, ast.Import):
            for a in node.names:
                parts = a.name.split('.')
                if parts[0] == 'modules' and len(parts) > 1:
                    if parts[1] in importers:
                        importers[parts[1]].add(rel)
                elif parts[0] in importers:
                    importers[parts[0]].add(rel)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ''
            parts = mod.split('.')
            if parts[0] == 'modules':
                if len(parts) > 1:
                    if parts[1] in importers:
                        importers[parts[1]].add(rel)
                else:
                    for a in node.names:          # from modules import X
                        if a.name in importers:
                            importers[a.name].add(rel)
            elif mod in importers and node.level == 0:
                importers[mod].add(rel)           # import data_store / from data_store import *
            elif node.level > 0:                  # from . import memory_store
                if len(parts) > 1 and parts[0] in importers:
                    importers[parts[0]].add(rel)
                for a in node.names:
                    if a.name in importers:
                        importers[a.name].add(rel)
        # 动态导入
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if 'import_module' in src[max(0, node.col_offset - 40):node.end_col_offset + 40]:
                pass
    for m in re.finditer(r'import_module\(\s*[\'"]([^\'"]+)', src):
        dyn.append('%s  ->  %s' % (rel, m.group(1)))
    for m in re.finditer(r'__import__\(\s*[\'"]([^\'"]+)', src):
        dyn.append('%s  ->  __import__(%s)' % (rel, m.group(1)))
    if rel.endswith('src\\main.py') or rel.endswith('src/main.py'):
        for m in re.finditer(r'self\.(\w+)\s*=\s*(\w+)\(', src):
            inst.append('%s   self.%s = %s(...)' % (rel, m.group(1), m.group(2)))

W('=== (1) 每个 modules 模块的引用者 ===')
never = []
for m in sorted(mods):
    who = sorted(importers[m])
    prod_who = [w for w in who if not w.startswith('modules\\')]
    if not who:
        never.append(m)
    W('%-26s %s' % (m, ', '.join(who) if who else '<<< 无人 import >>>'))

W('')
W('=== (2) 从未被任何生产代码 import 的模块（模块级零调用）===')
if never:
    for m in never:
        W('  %s' % m)
else:
    W('  （无）')
# 只被"别的模块"引用、从未被 main.py 引用的
W('')
W('=== (2b) 从未被 src/main.py 直接 import 的模块 ===')
for m in sorted(mods):
    if not any('main.py' in w for w in importers[m]):
        W('  %-26s 引用者: %s' % (m, ', '.join(sorted(importers[m])) or '无'))

W('')
W('=== (3) main.py 里的控制器实例化点（正则 self.X = Y(...)）===')
W('共 %d 条' % len(inst))
for s in inst:
    W('  ' + s)

W('')
W('=== (4) 动态导入点 import_module / __import__ ===')
W('共 %d 条' % len(dyn))
for s in dyn:
    W('  ' + s)

io.open(os.path.join(EV, 'wiring.txt'), 'w', encoding='utf-8',
        newline='\n').write('\n'.join(out) + '\n')
print('never imported:', len(never), '| modules:', len(mods),
      '| inst lines:', len(inst), '| dyn:', len(dyn))

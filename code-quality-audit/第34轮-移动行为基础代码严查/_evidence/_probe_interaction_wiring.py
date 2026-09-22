# -*- coding: utf-8 -*-
"""探针 20 号：pet_interaction.py 是否真的"未接线"（AST 硬核验）。

背景
----
`审查报告_2026.md:99` 断言："`pet_interaction.py` 全模块未接线（孤儿）：
main.py 内另有一套身体分区/手势识别（重复编码）"。
但字面量 grep 会漏掉别名导入、getattr、动态属性等写法 —— 按项目铁律
"零引用筛查一律走 AST"，本探针不靠 grep，直接对全仓 .py 建 AST，
统计：

  (a) 谁 import 了 pet_interaction 这个名字（Import / ImportFrom 节点）
  (b) 谁引用了该模块导出的符号（PetInteractionTracker / GestureTracker /
      BodyRegionMapper / PetEvent / BodyPart / Gesture / _StrokeDetector）
  (c) main.py 里是否存在**第二套**身体分区 / 手势识别实现（重复编码证据）

判据
----
只统计**产品代码**：跳过仓库根的 `_audit_*`/`_fix_*`/`_verify_*` 一次性脚本、
`code-quality-audit/` 证据目录、`__pycache__`。但两侧都打印，避免误判。
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))  # 仓库根 = try - 副本
PKG = os.path.join(ROOT, 'ralsei_pet')

SYMBOLS = {
    'PetInteractionTracker', 'GestureTracker', 'BodyRegionMapper',
    'PetEvent', 'BodyPart', 'Gesture', '_StrokeDetector', 'GestureTracker',
}

SKIP_DIRS = {'__pycache__', '.git', 'code-quality-audit', 'node_modules',
             '.workbuddy', 'audit_evidence', '_evidence'}


def iter_py(base):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith('.py'):
                yield os.path.join(dirpath, fn)


def rel(p):
    try:
        return os.path.relpath(p, ROOT).replace('\\', '/')
    except ValueError:
        return p


def is_oneshot(rp):
    """仓库根的一次性脚本（_audit_* / _fix_* / _verify_*），不算产品代码。"""
    name = os.path.basename(rp)
    if '/' not in rp:  # 仓库根
        return name.startswith(('_audit_', '_fix_', '_verify_', '_probe_'))
    return False


print('=' * 72)
print('探针 20：pet_interaction.py 接线核查（AST 判据，不依赖 grep）')
print('=' * 72)
print('仓库根 :', ROOT)
print('扫描包 :', rel(PKG))
print()

importers = []          # (file, lineno, how, names)
symbol_users = []       # (file, lineno, name)
parse_errors = []
scanned = 0

for path in sorted(iter_py(PKG)) + sorted(iter_py(ROOT)):
    rp = rel(path)
    if rp.startswith('code-quality-audit/'):
        continue
    if is_oneshot(rp):
        continue
    try:
        with io.open(path, 'r', encoding='utf-8', errors='replace') as f:
            src = f.read()
    except OSError as e:
        parse_errors.append((rp, 'READ %s' % e))
        continue
    scanned += 1
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError as e:
        parse_errors.append((rp, 'SYNTAX %s' % e))
        continue

    for node in ast.walk(tree):
        # (a) import pet_interaction / from modules import pet_interaction
        if isinstance(node, ast.Import):
            for a in node.names:
                if 'pet_interaction' in (a.name or ''):
                    importers.append((rp, node.lineno, 'import', a.name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ''
            for a in node.names:
                if 'pet_interaction' in mod or 'pet_interaction' in (a.name or ''):
                    importers.append((rp, node.lineno,
                                      'from %s' % mod, a.name))
        # (b) 符号引用（Name 节点，排除 import 语句本身）
        elif isinstance(node, ast.Name) and node.id in SYMBOLS:
            # 排除定义处所在文件自身
            if 'pet_interaction.py' not in rp:
                symbol_users.append((rp, node.lineno, node.id))
        elif isinstance(node, ast.Attribute) and node.attr in SYMBOLS:
            if 'pet_interaction.py' not in rp:
                symbol_users.append((rp, node.lineno, '.' + node.attr))

print('-' * 72)
print('[A] 谁 import 了 pet_interaction（产品代码范围内）')
print('-' * 72)
if not importers:
    print('  （无）—— 该模块没有任何外部导入语句')
else:
    for rp, ln, how, nm in importers:
        print('  %s:%d  %s %s' % (rp, ln, how, nm))
print()

print('-' * 72)
print('[B] 谁引用了该模块的导出符号（含属性访问）')
print('-' * 72)
if not symbol_users:
    print('  （无）—— 全仓产品代码零引用')
else:
    seen = {}
    for rp, ln, nm in symbol_users:
        seen.setdefault(nm, []).append((rp, ln))
    for nm in sorted(seen):
        hits = seen[nm]
        print('  %-26s %d 处' % (nm, len(hits)))
        for rp, ln in hits[:6]:
            print('      %s:%d' % (rp, ln))
        if len(hits) > 6:
            print('      ... 另 %d 处' % (len(hits) - 6))
print()

print('-' * 72)
print('[C] main.py 内是否有"第二套"身体分区 / 手势识别（重复编码证据）')
print('-' * 72)
MAIN = os.path.join(PKG, 'src', 'main.py')
try:
    with io.open(MAIN, 'r', encoding='utf-8', errors='replace') as f:
        main_src = f.read()
except OSError as e:
    print('  读 main.py 失败:', e)
    main_src = ''
if main_src:
    try:
        mt = ast.parse(main_src, filename=MAIN)
    except SyntaxError as e:
        print('  main.py 语法错误:', e)
        mt = None
    if mt is not None:
        funcs = [n.name for n in ast.walk(mt)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n.name for n in ast.walk(mt)
                   if isinstance(n, ast.ClassDef)]
        kw = ('body_region', 'bodymapper', 'region_map', 'gesture',
              'stroke', 'body_part', 'bodypart', 'on_pet', 'classify',
              'is_on_pet')
        hit_funcs = sorted({f for f in funcs
                            if any(k in f.lower() for k in kw)})
        hit_classes = sorted({c for c in classes
                              if any(k in c.lower() for k in kw)})
        print('  main.py 中与"身体分区/手势"命名相关的**函数** (%d):' % len(hit_funcs))
        for f in hit_funcs:
            print('      def %s' % f)
        print('  main.py 中与"身体分区/手势"命名相关的**类** (%d):' % len(hit_classes))
        for c in hit_classes:
            print('      class %s' % c)
        # 关键：main.py 是否也自己实现了 alpha 遮罩/分区
        probes = {
            'alpha 遮罩取样': ('pixelAlpha', 'alphaChannel', 'createAlphaMask',
                           'toImage', 'mask()'),
            '百分比分区常量': ('0.15', '0.35', '0.55', '0.75'),
        }
        print()
        for label, pats in probes.items():
            found = [p for p in pats if p in main_src]
            print('  %s: %s' % (label, found if found else '未命中'))
print()

print('-' * 72)
print('[D] 结论判定')
print('-' * 72)
has_import = bool(importers)
has_sym = bool(symbol_users)
# 区分：符号引用是否来自 pet_interaction.py 自身（自引用不算接线）
ext_sym = [s for s in symbol_users if 'pet_interaction.py' not in s[0]]
print('  外部 import 语句        :', '有' if has_import else '无')
print('  外部符号引用            :', '有 (%d)' % len(ext_sym) if ext_sym else '无')
verdict_orphan = (not has_import) and (not ext_sym)
print('  → 判定 "全模块未接线"   :', '成立' if verdict_orphan else '不成立')

fails = 0
if scanned == 0:
    print('[FAIL] 扫描到 0 个 .py —— 探针自身路径有误')
    fails += 1
if parse_errors:
    print('[INFO] 解析失败 %d 个（不影响结论）' % len(parse_errors))
    for rp, why in parse_errors[:5]:
        print('       %s -> %s' % (rp, why))

print()
print('SUITE_SUMMARY pass=%d fail=%d' % (1 if fails == 0 else 0, fails))
sys.exit(0 if fails == 0 else 1)

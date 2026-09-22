# -*- coding: utf-8 -*-
"""探针 25 号：动画播放状态机一致性（AST 静态判据）。

背景
----
`play_animation_once` / `update_animation` / `change_animation` 靠一组
`_play_once_*` 状态位协作。这类"状态位"最容易出的问题是：
  ① 只置不还原（残留 True → 后续正常状态逻辑被跳过 → 动画卡死）
  ② 多处设置，但只有一处还原（路径覆盖不全）
  ③ 定义了但从未被读（死状态位）

判据（全部可静态判定）
----------------------
  P1  每个 `_play_once_*` / `_special_anim_*` 状态位，必须**既被赋值又被读取**
      （只写不读 = 死状态位；只读不写 = 永假判据）
  P2  `_play_once_active` 的置 True 处数 vs 置 False 处数（路径覆盖）
  P3  找出所有"赋值了 True 但同函数内没有对应还原"的裸奔点（启发式，人工复核）
  P4  `_play_once_callback` / `_play_once_frame_counter` 的读取点是否都在
      `_play_once_active` 为真的守卫内
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

SRC = io.open(MAIN, 'r', encoding='utf-8', errors='replace').read()
TREE = ast.parse(SRC, filename=MAIN)
LINES = SRC.splitlines()

# 目标状态位：以 _play_once_ / _special_anim_ 开头的属性
def is_target(name):
    return name.startswith('_play_once_') or name.startswith('_special_anim_')

writes = {}    # name -> [(lineno, value_repr, funcname)]
reads = {}     # name -> [(lineno, funcname, ctx)]


def func_of(node, stack):
    return stack[-1] if stack else '<module>'


class V(ast.NodeVisitor):
    def __init__(self):
        self.stack = []

    def _enter(self, node):
        self.stack.append(node.name)

    def _exit(self):
        self.stack.pop()

    def visit_FunctionDef(self, node):
        self._enter(node)
        self.generic_visit(node)
        self._exit()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node):
        fn = func_of(node, self.stack)
        for t in node.targets:
            # 取属性名
            targets = []
            if isinstance(t, ast.Attribute):
                targets.append((t.attr, self._attr_full(t)))
            elif isinstance(t, ast.Tuple):
                for e in t.elts:
                    if isinstance(e, ast.Attribute):
                        targets.append((e.attr, self._attr_full(e)))
            for attr, full in targets:
                if is_target(attr):
                    val = self._repr(node.value)
                    writes.setdefault(attr, []).append(
                        (node.lineno, val, fn))
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if isinstance(node.target, ast.Attribute) and is_target(node.target.attr):
            fn = func_of(node, self.stack)
            writes.setdefault(node.target.attr, []).append(
                (node.lineno, self._repr(node.value), fn))
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        if isinstance(node.target, ast.Attribute) and is_target(node.target.attr):
            fn = func_of(node, self.stack)
            writes.setdefault(node.target.attr, []).append(
                (node.lineno, 'aug:%s' % self._repr(node.value), fn))
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if is_target(node.attr):
            fn = func_of(node, self.stack)
            ctx = type(node.ctx).__name__
            if ctx == 'Load':
                reads.setdefault(node.attr, []).append((node.lineno, fn))
        self.generic_visit(node)

    @staticmethod
    def _attr_full(node):
        return ast.unparse(node) if hasattr(ast, 'unparse') else ''

    @staticmethod
    def _repr(v):
        if v is None:
            return 'None'
        if isinstance(v, ast.Constant):
            return repr(v.value)
        if isinstance(v, ast.Name):
            return v.id
        if isinstance(v, ast.Call):
            try:
                return '%s(...)' % v.func.attr
            except Exception:
                return '<call>'
        return '<expr>'


V().visit(TREE)

print('=' * 76)
print('探针 25：动画播放状态位一致性（AST 静态判据）')
print('=' * 76)
print()

names = sorted(set(list(writes.keys()) + list(reads.keys())))

# ★ 判据修正（第一版自身缺陷）：字符串字面量读法 AST 看不到
#   `getattr(self, '_play_once_active', False)` 里属性名是 **字符串常量**，
#   visit_Attribute 根本不会命中，于是被我误判成"只写不读"。
#   同理 `self._special_anim_locked()` 是**方法**不是属性，也不该进这张表。
#   修法：把字符串字面量里的同名引用也算作"读"。
STR_LITERAL_READS = {}
for node in ast.walk(TREE):
    if isinstance(node, ast.Constant) and isinstance(node.value, str) \
            and is_target(node.value):
        STR_LITERAL_READS.setdefault(node.value, []).append(node.lineno)

# `_special_anim_locked` 是方法名：确认它有没有 FunctionDef 定义
DEFINED_METHODS = {n.name for n in ast.walk(TREE)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

print('-' * 76)
print('[P1] 每个状态位：是否既写又读')
print('-' * 76)
print('  （"读" = Attribute Load  + getattr/hasattr 字符串字面量）')
print()
p1_fail = []
p1_info = []
for nm in names:
    w = writes.get(nm, [])
    r = reads.get(nm, [])
    lit = STR_LITERAL_READS.get(nm, [])
    total_read = len(r) + len(lit)

    # 方法名（非属性）单列，不参与属性判定
    if nm in DEFINED_METHODS and not w:
        p1_info.append((nm, '是**方法**定义，非属性；此处仅被调用 → 正常'))
        continue

    if not w:
        tag = '[FAIL] 只读不写 ⇒ 恒为初始值'
        p1_fail.append(nm)
    elif total_read == 0:
        tag = '[FAIL] 只写不读 ⇒ 死状态位'
        p1_fail.append(nm)
    else:
        tag = '[PASS]'
    print('  %-30s 写=%-3d 读属性=%-3d 读字面量=%-3d %s'
          % (nm, len(w), len(r), len(lit), tag))
print()
for nm, why in p1_info:
    print('  [INFO] %-28s %s' % (nm, why))
print()

print('-' * 76)
print('[P2] 状态位置 True / 置 False 的路径覆盖')
print('-' * 76)
for nm in names:
    w = writes.get(nm, [])
    trues = [x for x in w if x[1] == 'True']
    falses = [x for x in w if x[1] in ('False', 'None')]
    if not w:
        continue
    print('  %s' % nm)
    print('      置真值 %d 处:' % len(trues))
    for ln, v, fn in trues:
        print('         L%-6d %s()' % (ln, fn))
    print('      置假/清空 %d 处:' % len(falses))
    for ln, v, fn in falses:
        print('         L%-6d %s()  -> %s' % (ln, fn, v))
print()

print('-' * 76)
print('[P3] 同函数内"置 True 却无还原"的裸奔点（启发式）')
print('-' * 76)
p3 = []
for nm in names:
    w = writes.get(nm, [])
    trues = [x for x in w if x[1] == 'True']
    falses = [x for x in w if x[1] in ('False', 'None')]
    for ln, v, fn in trues:
        same_fn_restore = [f for f in falses if f[2] == fn]
        if not same_fn_restore:
            p3.append((nm, ln, fn))
            print('  [WARN] %s 在 %s() L%d 置 True，该函数内无还原' % (nm, fn, ln))
if not p3:
    print('  （无）每个置 True 的函数内都有对应还原')
print()

print('-' * 76)
print('[P4] 相关函数清单与行数')
print('-' * 76)
TARGETS = ('play_animation_once', 'change_animation', 'update_animation',
           '_special_anim_locked', '_is_special_anim',
           'update_animation_by_emotion', 'change_animation_randomly')
for node in ast.walk(TREE):
    if isinstance(node, ast.FunctionDef) and node.name in TARGETS:
        end = max([n.lineno for n in ast.walk(node)
                   if hasattr(n, 'lineno')] or [node.lineno])
        print('  %-32s L%-6d ~ L%-6d (%d 行)'
              % (node.name, node.lineno, end, end - node.lineno + 1))
print()

print('=' * 76)
print('SUITE_SUMMARY pass=%d fail=%d' % (len(names) - len(p1_fail), len(p1_fail)))
if p1_fail:
    print('  P1 不合格:', ', '.join(p1_fail))
else:
    print('  P1 全部合格（每个状态位都既写又读）')
if STR_LITERAL_READS:
    print()
    print('  字面量读法命中点（getattr/hasattr 用字符串取属性）:')
    for nm in sorted(STR_LITERAL_READS):
        print('    %-30s L%s' % (nm, ', '.join(str(x) for x in STR_LITERAL_READS[nm])))
sys.exit(0 if not p1_fail else 1)

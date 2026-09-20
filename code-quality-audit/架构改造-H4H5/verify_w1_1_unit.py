# -*- coding: utf-8 -*-
"""W1-1 单元级校验：搬进 SpellFlowController 的 4 个方法体是否**逐字等价**，
并配**正/负控制**证明这套判据有鉴别力。

口径（H4/H5 W1-1）：
  · 只搬方法、不搬状态；方法体逐字搬运
  · 唯一允许的机械改写：`_log.` → `_log_().`（本项共 11 处，逐方法计数见下）
  · 控制器不 import 任何项目内模块

判据来源：**父版本** `git show <parent>:ralsei_pet/src/main.py`（绝不能取已提交的当前版，
否则 A == B、探针退化成自己跟自己比 —— W1-4 报告第五节的铁律）。
"""
import ast
import io
import os
import re
import subprocess
import sys
import textwrap

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
CTRL = os.path.join(ROOT, 'ralsei_pet', 'modules', 'spell_controller.py')

NAMES = ['_spell_interrupted_reason', '_tick_spell_flow',
         '_cast_spell_then', '_start_open_with_spell']

# 逐方法的 `_log.` 出现次数（施工前从父版本数出来的期望值）
EXPECT_REWRITES = {
    '_spell_interrupted_reason': 0,
    '_tick_spell_flow': 8,
    '_cast_spell_then': 2,
    '_start_open_with_spell': 1,
}

results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('  [PASS] ' if ok else '  [FAIL] ') + name +
          ((' :: ' + detail) if detail else ''))


def norm(s):
    """统一行尾 + 归一缩进。

    不能直接 textwrap.dedent —— 首行 `def xxx(self):` 缩进为 0，
    公共前缀会算成 0。做法：首行单独拎出，其余 dedent。
    """
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    ls = s.split('\n')
    head = ls[0].strip()
    rest = textwrap.dedent('\n'.join(ls[1:]))
    return (head + '\n' + rest).strip('\n')


print('=== 载入两份源码 ===')
main_src = io.open(MAIN, encoding='utf-8').read()
ctrl_src = io.open(CTRL, encoding='utf-8').read()
check('X1 main.py 可读', bool(main_src), 'bytes=%d' % len(main_src))
check('X2 spell_controller.py 可读', bool(ctrl_src), 'bytes=%d' % len(ctrl_src))

# ---- 从父版本取"旧"方法体（若本项已提交，HEAD~ 里那份是搬移前的） ----
print()
print('=== 取父版本（A/B 前置：必须 A ≠ B） ===')


def _load_parent_main():
    """父版本 main.py（搬移前）。策略：
    1) 若 git 工作区里 main.py 与 HEAD 相同 → 用 `git show HEAD~1:...`
    2) 否则用 `git show HEAD:...`（说明本次搬移尚未提交）
    返回 (源码, 说明串) 或 (None, 原因)。
    """
    def _run(args):
        p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        return p.returncode, p.stdout

    rc, head_main = _run(['git', 'show', 'HEAD:ralsei_pet/src/main.py'])
    if rc != 0 or not head_main:
        return None, 'HEAD:main.py 取不到 (rc=%s)' % rc
    # HEAD 版本里是否还含这 4 个方法？
    has = all(('def %s' % n) in head_main for n in NAMES)
    if has:
        return head_main, 'git show HEAD:ralsei_pet/src/main.py'
    rc2, prev = _run(['git', 'show', 'HEAD~1:ralsei_pet/src/main.py'])
    if rc2 == 0 and prev and all(('def %s' % n) in prev for n in NAMES):
        return prev, 'git show HEAD~1:ralsei_pet/src/main.py'
    return None, 'HEAD 与 HEAD~1 都不含这 4 个方法'


parent_src, parent_note = _load_parent_main()
check('X3 取到父版本 main.py', parent_src is not None, parent_note)

# ---- X4 A/B 退化哨兵：父版本必须与当前 main.py **不同** ----
# W1-4 报告第五节铁律：取"旧值"若恰好拿到**已提交的当前版**，A == B，
# 逐字等价断言就退化成"自己跟自己比" → 永远 PASS 且**非常像真的**。
# 这里显式断言两份源码 md5 不同；相同即立刻失败（说明取错了版本）。
import hashlib
_md5_p = hashlib.md5(parent_src.encode('utf-8')).hexdigest() if parent_src else ''
_md5_c = hashlib.md5(main_src.encode('utf-8')).hexdigest()
check('X4 父版本 ≠ 当前 main.py（A/B 未退化）',
      bool(_md5_p) and _md5_p != _md5_c,
      'parent=%s current=%s' % (_md5_p[:12], _md5_c[:12]))

# 逐方法从父版本取"旧"体，从控制器取"新"体，归一后比较
print()
print('=== V1 逐方法逐字等价（含 _log_(). 改写计数） ===')


def _methods(src, cls_name):
    t = ast.parse(src)
    if cls_name:
        cls = [n for n in t.body
               if isinstance(n, ast.ClassDef) and n.name == cls_name]
        assert cls, 'class %s not found' % cls_name
        return {n.name: n for n in cls[0].body if isinstance(n, ast.FunctionDef)}
    return {n.name: n for n in t.body if isinstance(n, ast.FunctionDef)}


old_nodes = _methods(parent_src, 'RalseiPet') if parent_src else {}
new_nodes = _methods(ctrl_src, 'SpellFlowController')
parent_lines = parent_src.split('\n') if parent_src else []

total_re = 0
all_ok = True
for n in NAMES:
    if n not in new_nodes:
        check('V1 %s 存在于控制器' % n, False, 'NOT FOUND')
        all_ok = False
        continue
    new_raw = ast.get_source_segment(ctrl_src, new_nodes[n])
    # 数改写次数（口径：`_log.` → `self._log_().`）
    n_re = new_raw.count('self._log_().')
    total_re += n_re
    exp = EXPECT_REWRITES[n]
    check('V1a %s _log.->self._log_(). 次数 == %d' % (n, exp), n_re == exp,
          'actual=%d' % n_re)

    if n not in old_nodes:
        check('V1b %s 父版本可比对' % n, False, '父版本里找不到该方法')
        all_ok = False
        continue
    on = old_nodes[n]
    old_raw = '\n'.join(parent_lines[on.lineno - 1:on.end_lineno])
    a = norm(old_raw)
    b = norm(new_raw).replace('self._log_().', '_log.')
    same = (a == b)
    if not same:
        all_ok = False
        detail = ''
        for i, (x, y) in enumerate(zip(a.split('\n'), b.split('\n'))):
            if x != y:
                detail = 'line %d OLD=%r NEW=%r' % (i, x, y)
                break
        else:
            detail = 'len differs old=%d new=%d' % (len(a.split('\n')),
                                                    len(b.split('\n')))
        check('V1b %s 方法体逐字等价' % n, False, detail)
    else:
        check('V1b %s 方法体逐字等价' % n, True,
              'lines=%d' % (on.end_lineno - on.lineno + 1))

check('V1c 改写总数 == 11', total_re == 11, 'actual=%d' % total_re)
check('V1d 全部方法逐字等价', all_ok)

# ---- V2 负控制：故意改一个字，判据必须判不等 ----
print()
print('=== V2 负控制（证明判据有鉴别力） ===')
probe_name = '_tick_spell_flow'
new_raw = ast.get_source_segment(ctrl_src, new_nodes[probe_name])
on = old_nodes[probe_name]
old_raw = '\n'.join(parent_lines[on.lineno - 1:on.end_lineno])
a = norm(old_raw)
# 负控制 1：把 11 改成 12（一个真实的语义数字）
mut = new_raw.replace('expected = 11', 'expected = 12')
check('V2a needle 真的命中了（命中数 >= 1）',
      mut != new_raw, 'replace changed=%s' % (mut != new_raw))
check('V2b 篡改后判据判**不等**',
      norm(mut).replace('self._log_().', '_log.') != a)
# 负控制 2：去掉一个注释（必须判不等，否则说明比对忽略了注释）
mut2 = new_raw.replace('        now = time.time()', '        now = time.time() ')
check('V2c 空白篡改后判**不等**',
      norm(mut2).replace('self._log_().', '_log.') != a)

# ---- V3 结构断言：控制器不 import 项目内模块 ----
print()
print('=== V3 结构断言 ===')
t = ast.parse(ctrl_src)
# ⚠️ 只看**模块级** import —— 不能 ast.walk 全树。
# 方法体内的**局部** import（本项是 `_tick_spell_flow` 里的 `import shutil`）
# 是逐字搬运的一部分、也是刻意保留的，不该算"控制器 import 了项目内模块"。
# 第一版用 ast.walk(t) → 把 `shutil` 也算进来 → 假红（本探针自身的 bug）。
module_imports = []
for node in t.body:
    if isinstance(node, ast.Import):
        for al in node.names:
            module_imports.append(al.name)
    elif isinstance(node, ast.ImportFrom):
        module_imports.append(node.module or '')
ALLOWED = ('PyQt5', 'logging', 'os', 'sys', 'time', 'random', 'json', 're')
proj = [m for m in module_imports
        if m and not m.startswith(ALLOWED)]
check('V3a 控制器模块级不 import 任何项目内模块', not proj,
      'module-level imports=%s' % module_imports)
check('V3b 模块级必备导入齐备（os/time/QPoint）',
      all(k in ctrl_src for k in ('import os', 'import time',
                                  'from PyQt5.QtCore import QPoint')),
      'checked 3 names')

# 方法体内局部 import 白名单核对：shutil 必须仍留在方法内（不能提到模块级）
check('V3c shutil 仍是方法内局部导入（未被提到模块级）',
      'import shutil' in ctrl_src and '\nimport shutil' not in ctrl_src)

# ---- V4 状态名预声明（铁律 3）----
print()
print('=== V4 状态预声明（铁律 3）===')
# 口径：两个名字必须在**宿主首次使用它们之前**就被宿主自己拥有。
# 「首次使用」= 4 个施法方法里的任意一次 `self.<name> = ...`（搬走后那些赋值
# 由控制器发出、经 __setattr__ 转发）—— 转发判据要求宿主**已拥有**该名。
# 施法状态声明区在 init_systems（不是 __init__）—— 第一版只查 __init__ → 假红。
# 判据改为：在 main.py **类体**里，除那 4 个已搬走的方法外，存在对它的 Store。
t2 = ast.parse(main_src)
cls2 = [n for n in t2.body
        if isinstance(n, ast.ClassDef) and n.name == 'RalseiPet'][0]
MOVED = set(NAMES)
for nm in ('_spell_seen_frame', '_spell_cast_start_time'):
    stores = []
    for fn in cls2.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        if fn.name in MOVED:
            continue          # 已搬走的方法不算（它们现在在控制器里）
        for n in ast.walk(fn):
            if (isinstance(n, ast.Attribute) and n.attr == nm
                    and isinstance(n.ctx, ast.Store)):
                stores.append(fn.name)
    check('V4 %s 已被宿主拥有（声明先于首次使用）' % nm, bool(stores),
          'declared in: %s' % sorted(set(stores)))

# ---- V5 转发名单 ----
print()
print('=== V5 转发接线 ===')
check("V5a _CONTROLLER_ATTRS 含 'spell'",
      "_CONTROLLER_ATTRS = ('games', 'video', 'spell')" in main_src)
check('V5b 已实例化 SpellFlowController',
      'self.spell = SpellFlowController(self)' in main_src)
check('V5c 已导入 SpellFlowController',
      'from modules.spell_controller import SpellFlowController' in main_src)
check('V5d 4 个方法已从 RalseiPet 移除',
      not any(('    def %s' % n) in main_src for n in NAMES))

# ---- 汇总 ----
print()
n_pass = sum(1 for _, ok, _ in results if ok)
n_fail = len(results) - n_pass
print('=' * 60)
print('W1-1 单元级：共 %d 项，通过 %d，失败 %d' % (len(results), n_pass, n_fail))
sys.exit(0 if n_fail == 0 else 1)

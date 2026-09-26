# -*- coding: utf-8 -*-
"""第53轮「底层代码彻查」· 静态基线（**只读**，不产 .pyc、不改任何源码）。

做四件事，全部落盘到 _evidence/：
  (1) pyflakes（跑隔离 venv 里的 python -m pyflakes）
      → undefined name / 未用导入 / 未用局部变量 / 重复定义
  (2) ast.parse 全量语法检查（刻意不用 compileall：它会写 .pyc，污染被 git 跟踪的文件）
  (3) 零引用符号穷举（剔除 Qt 事件回调 / dunder / 魔法名）
  (4) 同名重复定义（同一作用域内重复 def / class）

用法：
    C:\\Python311\\python.exe baseline53.py
输出：
    _evidence/baseline_pyflakes.txt
    _evidence/baseline_syntax.txt
    _evidence/baseline_deadcode.txt
    _evidence/baseline_dupes.txt
"""
import ast
import io
import os
import subprocess
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROOT, 'code-quality-audit', '第53轮-底层代码彻查', '_evidence')
VENV_PY = (r'C:\Users\23002\.workbuddy\binaries\python\envs\default'
           r'\Scripts\python.exe')

# Qt 事件回调 / 框架钩子：被 Qt 反调，静态引用数必然是 1，不能当死代码
QT_HOOKS = {
    'paintEvent', 'mousePressEvent', 'mouseMoveEvent', 'mouseReleaseEvent',
    'mouseDoubleClickEvent', 'wheelEvent', 'resizeEvent', 'moveEvent',
    'closeEvent', 'changeEvent', 'enterEvent', 'leaveEvent', 'dropEvent',
    'dragEnterEvent', 'dragMoveEvent', 'dragLeaveEvent', 'showEvent',
    'hideEvent', 'keyPressEvent', 'keyReleaseEvent', 'focusInEvent',
    'focusOutEvent', 'contextMenuEvent', 'timerEvent', 'eventFilter',
    'event', 'sizeHint', 'minimumSizeHint', 'heightForWidth', 'hitButton',
    'drawContents', 'initStyleOption', 'dragEnterEvent',
    'supportedDropActions', 'mimeData', 'flags', 'data', 'rowCount',
    'columnCount', 'headerData', 'setData', 'index', 'parent',
    'startDrag', 'drag', 'canDropMimeData', 'dropMimeData',
    'retranslateUi', 'setupUi', 'paintGL', 'initializeGL', 'resizeGL',
}
# 框架/约定式名称：由外部协议、信号、序列化或 __getattr__ 触发
CONVENTIONAL = {
    'main', 'setUp', 'tearDown', 'setUpClass', 'tearDownClass',
    'slot', 'run', 'tick', 'update', 'on', 'emit', 'handle',
}
DUNDER_OK = {'__init__', '__enter__', '__exit__', '__len__', '__repr__',
             '__str__', '__eq__', '__hash__', '__iter__', '__next__',
             '__contains__', '__getitem__', '__setitem__'}


def collect_files():
    out = []
    for sub in ('src', 'modules'):
        d = os.path.join(PET, sub)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            if n.endswith('.py'):
                out.append(os.path.join(d, n))
    for n in sorted(os.listdir(PET)):
        p = os.path.join(PET, n)
        if n.endswith('.py') and os.path.isfile(p):
            out.append(p)
    return out


def write(name, text):
    p = os.path.join(EV, name)
    with io.open(p, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    return p


def strip_comments(src):
    """剥注释但**保留字符串字面量**（零引用统计必须看字符串里的 getattr 名）。"""
    import tokenize
    try:
        toks = tokenize.generate_tokens(io.StringIO(src).readline)
    except Exception:
        return src
    out = []
    for tok in toks:
        if tok.type == tokenize.COMMENT:
            continue
        out.append(tok.string)
    return ' '.join(out)


def main():
    files = collect_files()
    print('files =', len(files))
    lines = []

    # ---------- (1) pyflakes ----------
    if os.path.isfile(VENV_PY):
        r = subprocess.run([VENV_PY, '-m', 'pyflakes'] + files,
                           capture_output=True, cwd=ROOT, timeout=600)
        raw = r.stdout.decode('utf-8', 'replace')
        lines.append('exit=%d  stdout_lines=%d' % (r.returncode, len(raw.splitlines())))
        write('baseline_pyflakes.txt', raw)
    else:
        lines.append('!! venv python 不存在，pyflakes 未跑')
        write('baseline_pyflakes.txt', '')

    # ---------- (2) ast 语法检查 ----------
    bad = []
    ok = 0
    trees = {}
    for p in files:
        try:
            src = io.open(p, encoding='utf-8').read()
        except Exception as e:
            bad.append('%s | READ_FAIL %r' % (p, e))
            continue
        try:
            trees[p] = ast.parse(src, filename=p)
            ok += 1
        except SyntaxError as e:
            bad.append('%s | SyntaxError line %s: %s' % (p, e.lineno, e.msg))
        except Exception as e:
            bad.append('%s | PARSE_FAIL %r' % (p, e))
    write('baseline_syntax.txt',
          'parse_ok=%d  parse_fail=%d\n' % (ok, len(bad)) + '\n'.join(bad) + '\n')
    lines.append('syntax: ok=%d fail=%d' % (ok, len(bad)))
    for b in bad:
        lines.append('  ' + b)

    # ---------- (3) 零引用符号穷举 ----------
    defs = []            # (name, qual, file, lineno, kind)
    for p, t in trees.items():
        rel = os.path.relpath(p, ROOT)
        _collect_defs(t, rel, defs)

    # ★★ 引用面（第 53 轮修正）：把「真引用」与「仅被字符串提及」分开。
    #   旧版把**源码文本里所有标识符**（含 docstring / 日志文案里的提及）都计入引用 ⇒
    #   一个只在文档字符串里被提过名字的方法永远不算死代码 ⇒ **系统性漏报**
    #   （实测：`react_to_file_emotionally` 唯一的"引用"来自
    #    file_sheet_controller.py 的 docstring，它实际是条死链）。
    #   现在：Name / Attribute / getattr 家族的字面量参数 = hard（真引用）；
    #         其余字符串字面量 = soft（仅提及，最多算"弱引用"）。
    DYNAMIC = ('getattr', 'hasattr', 'setattr', 'delattr', '__import__',
               'import_module', 'exec', 'eval')
    hard, soft = {}, {}
    for p, t in trees.items():
        for node in ast.walk(t):
            if isinstance(node, ast.Name):
                hard[node.id] = hard.get(node.id, 0) + 1
            elif isinstance(node, ast.Attribute):
                hard[node.attr] = hard.get(node.attr, 0) + 1
            elif isinstance(node, ast.Call):
                fn = node.func
                fname = (fn.id if isinstance(fn, ast.Name)
                         else fn.attr if isinstance(fn, ast.Attribute) else None)
                if fname in DYNAMIC:
                    for a in node.args:
                        if isinstance(a, ast.Constant) and isinstance(a.value, str):
                            for m in _WORDS.finditer(a.value):
                                hard[m.group(0)] = hard.get(m.group(0), 0) + 1
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                for m in _WORDS.finditer(node.value):
                    soft[m.group(0)] = soft.get(m.group(0), 0) + 1

    dead, weak = [], []
    for name, qual, rel, ln, kind in defs:
        if name.startswith('__') and name.endswith('__'):
            continue
        if name in QT_HOOKS or name in CONVENTIONAL or name in DUNDER_OK:
            continue
        row = '%-6s %-42s %s:%d' % (kind, qual, rel, ln)
        if hard.get(name, 0) == 0:
            (weak if soft.get(name, 0) > 0 else dead).append(row)
    dead.sort()
    weak.sort()
    write('baseline_deadcode.txt',
          '【A】真·零引用（全项目没有任何代码引用它，且字符串里也没提过）%d 个\n' % len(dead)
          + '\n'.join(dead)
          + '\n\n【B】零代码引用，但被字符串字面量提过（多为 docstring/日志文案）%d 个\n'
          % len(weak)
          + '\n'.join(weak) + '\n')
    lines.append('deadcode A(真零引用)=%d  B(仅字符串提及)=%d' % (len(dead), len(weak)))

    # ---------- (4) 同名重复定义 ----------
    # ★★ 判据修正（第 2 次，本脚本自己的假阳性）：第一版用 (qual, kind) 做键，
    #   但**顶层函数的 qual 就等于函数名**（不含文件名）⇒ 10 个文件各写一个
    #   `get_logger` / `describe` 会被判成"同作用域重复定义"。
    #   真正该守的是 **(文件, qual, kind) 三元组** —— 同一文件同一作用域同名才算真重复。
    #   跨文件同名另立一栏（那对应"重复编码/漂移副本"，性质不同，且很可能是刻意 fallback）。
    seen = {}
    for name, qual, rel, ln, kind in defs:
        seen.setdefault((rel, qual, kind), []).append(ln)
    dupes, cross = [], {}
    for (rel, qual, kind), lns in sorted(seen.items()):
        if len(lns) > 1:
            dupes.append('%-6s %s:%s  ->  行 %s'
                         % (kind, rel, qual, ', '.join(str(x) for x in lns)))
    byname = {}
    for name, qual, rel, ln, kind in defs:
        byname.setdefault((name, kind), []).append('%s:%d' % (rel, ln))
    for (name, kind), where in sorted(byname.items()):
        files = {w.split(':')[0] for w in where}
        if len(files) > 1:
            cross['%s %s' % (kind, name)] = where
    txt = ['【真·同作用域重复定义】%d 处' % len(dupes)] + dupes
    txt += ['', '【跨文件同名】%d 组（可能是重复编码/漂移副本，也可能是刻意 fallback）'
            % len(cross)]
    for k in sorted(cross):
        v = cross[k]
        txt.append('  %-28s x%-3d %s' % (k, len(v), ' '.join(
            sorted({w.split(':')[0] for w in v}))))
    write('baseline_dupes.txt', '\n'.join(txt) + '\n')
    lines.append('same-scope dupes = %d ; cross-file same-name groups = %d'
                 % (len(dupes), len(cross)))

    print('\n'.join(lines))
    write('baseline_stdout.txt', '\n'.join(lines) + '\n')
    return 0


def _collect_defs(tree, rel, out):
    """单遍带作用域栈收集 def/class，避免 ast.walk 的 O(n^2) 反查。"""
    stack = []

    def visit(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                kind = 'class' if isinstance(child, ast.ClassDef) else 'def'
                qual = '.'.join(stack + [child.name])
                # ★ `@x.setter` / `@x.deleter` / `@x.getter` 与 `@property` 同名是
                #   Python 的正常写法（memory_system.assoc 就是这样），不是重复定义。
                is_accessor = any(
                    isinstance(d, ast.Attribute)
                    and d.attr in ('setter', 'deleter', 'getter')
                    for d in getattr(child, 'decorator_list', []))
                if not is_accessor:
                    out.append((child.name, qual, rel, child.lineno, kind))
                stack.append(child.name)
                visit(child)
                stack.pop()
            else:
                visit(child)

    visit(tree)


import re
_WORDS = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')

if __name__ == '__main__':
    sys.exit(main())

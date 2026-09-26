# -*- coding: utf-8 -*-
"""第53轮 · 级联死代码（可达性）分析（只读）。

为什么需要它：`baseline53.py` 的 A 类只能抓 **直接零引用**。
抓不到这种情况 —— B 只被 A 调用、而 A 自己是死的（级联死代码）。
例：`react_to_file_emotionally` 无人调用（A 类），
    但 `check_file_content` 因为被它调用而"看起来是活的"。

做法：从**模块级代码**（各类顶层语句 + `if __name__` 块）出发，
沿「谁调用了谁」反向传播可达性：
  - 一个 def/class 若被**模块级代码**引用 ⇒ 活
  - 若被某个**活着**的 def 引用 ⇒ 活
  - 迭代到不动点，剩下的就是「从入口不可达」的死代码
输出：_evidence/cascade_deadcode.txt（按模块分组 + 整类皆死的类）
"""
import ast
import io
import os
import re

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROOT, 'code-quality-audit', '第53轮-底层代码彻查', '_evidence')

JUNK = re.compile(r'^(test_|diag|monitor_|main_simple)')
DYNAMIC = ('getattr', 'hasattr', 'setattr', 'delattr', '__import__',
           'import_module', 'invokeMethod')

files = [os.path.join(PET, 'src', 'main.py')]
for n in sorted(os.listdir(PET)):
    if n.endswith('.py') and not JUNK.match(n):
        files.append(os.path.join(PET, n))
for n in sorted(os.listdir(os.path.join(PET, 'modules'))):
    if n.endswith('.py'):
        files.append(os.path.join(PET, 'modules', n))

defs = {}          # qual -> dict(name, rel, line, kind, cls)
callers = {}       # name -> set(qual)   （'<module>' 表示模块级代码引用）
members = {}       # cls_qual -> [method qual]


def add_ref(name, scope):
    callers.setdefault(name, set()).add(scope)


for f in files:
    rel = os.path.relpath(f, ROOT)
    try:
        tree = ast.parse(io.open(f, encoding='utf-8').read(), filename=f)
    except Exception:
        continue
    stack = []

    def visit(node):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = 'class' if isinstance(ch, ast.ClassDef) else 'def'
                qual = '.'.join(stack + [ch.name])
                # property setter 等访问器与 property 同名，合并到同一 qual
                is_acc = any(isinstance(d, ast.Attribute) and
                             d.attr in ('setter', 'deleter', 'getter')
                             for d in getattr(ch, 'decorator_list', []))
                if not is_acc:
                    defs[qual] = dict(name=ch.name, rel=rel, line=ch.lineno,
                                      kind=kind,
                                      cls='.'.join(stack) if stack else '')
                    if stack and kind == 'def':
                        members.setdefault('.'.join(stack), []).append(qual)
                stack.append(ch.name)
                visit(ch)
                stack.pop()
            else:
                # 引用收集：Name / Attribute / getattr 家族字面量
                scope = '.'.join(stack) if stack else '<module>'
                if isinstance(ch, ast.Name):
                    add_ref(ch.id, scope)
                elif isinstance(ch, ast.Attribute):
                    add_ref(ch.attr, scope)
                elif isinstance(ch, ast.Call):
                    fn = ch.func
                    fname = (fn.id if isinstance(fn, ast.Name)
                             else fn.attr if isinstance(fn, ast.Attribute) else None)
                    if fname in DYNAMIC:
                        for a in ch.args:
                            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                                for m in re.finditer(r'[A-Za-z_]\w*', a.value):
                                    add_ref(m.group(0), scope)
                visit(ch)

    visit(tree)

# 协议/框架反调名：它们由语言或 Qt 按名字调用，**不会产生同名引用**
PROTOCOL = {'__init__', '__new__', '__call__', '__enter__', '__exit__',
            '__len__', '__iter__', '__next__', '__getitem__', '__setitem__',
            '__contains__', '__repr__', '__str__', '__eq__', '__hash__',
            '__getattr__', '__setattr__', '__delattr__', '__getattribute__',
            '__bool__', '__float__', '__int__', '__add__', '__radd__',
            '__lt__', '__le__', '__gt__', '__ge__', '__format__'}
QT_EVENTS = {'paintEvent', 'mousePressEvent', 'mouseMoveEvent',
             'mouseReleaseEvent', 'mouseDoubleClickEvent', 'wheelEvent',
             'resizeEvent', 'moveEvent', 'closeEvent', 'changeEvent',
             'enterEvent', 'leaveEvent', 'dropEvent', 'dragEnterEvent',
             'dragMoveEvent', 'dragLeaveEvent', 'showEvent', 'hideEvent',
             'keyPressEvent', 'keyReleaseEvent', 'focusInEvent',
             'focusOutEvent', 'contextMenuEvent', 'timerEvent', 'eventFilter',
             'event'}

# ---- 可达性传播 ----
alive = set()
for qual, d in defs.items():
    if '<module>' in callers.get(d['name'], ()):
        alive.add(qual)
changed = True
rounds = 0
while changed and rounds < 50:
    changed = False
    rounds += 1
    for qual, d in defs.items():
        if qual in alive:
            continue
        nm = d['name']
        # ★ 修正（本脚本的头号假阴性）：`__init__` / dunder / Qt 事件回调是
        #   **按名字被语言或框架反调**的 —— 实例化 `ClassX()` 不会产生任何
        #   名为 `__init__` 的引用，paintEvent 也不会被显式调用。
        #   不加这两条会把**所有只被 __init__ 调用的方法**判成死代码（实测
        #   1318/1613 皆"死"，比例荒谬，就是这个原因）。
        #   判据：只要它所在的类本身是活的，就认为它活。
        if nm in PROTOCOL or nm in QT_EVENTS:
            cls = d['cls']
            if not cls:
                alive.add(qual)
                changed = True
            elif (cls in alive
                  or '<module>' in callers.get(cls.split('.')[-1], ())):
                alive.add(qual)
                changed = True
            continue
        cs = callers.get(nm, set())
        if not cs:
            continue
        if any(c == '<module>' or c in alive for c in cs):
            alive.add(qual)
            changed = True

dead = sorted(q for q in defs if q not in alive)

out = []
out.append('defs 总数 = %d ；可达 = %d ；不可达（级联死代码）= %d ；迭代 %d 轮'
           % (len(defs), len(alive), len(dead), rounds))
out.append('')
byfile = {}
for q in dead:
    byfile.setdefault(defs[q]['rel'], []).append(q)
out.append('=== 按文件分组的不可达符号 ===')
for rel in sorted(byfile):
    out.append('--- %s  (%d 个) ---' % (rel, len(byfile[rel])))
    for q in sorted(byfile[rel]):
        d = defs[q]
        out.append('  %-7s %s:%d' % (d['kind'], q, d['line']))
    out.append('')

out.append('=== 整个类「所有方法都不可达」的类（最可疑：被实例化但从不使用）===')
for cq, ms in sorted(members.items()):
    if ms and all(m in dead for m in ms):
        d = defs.get(cq, {})
        out.append('  %-46s %s:%s   方法数=%d'
                   % (cq, d.get('rel', '?'), d.get('line', '?'), len(ms)))

io.open(os.path.join(EV, 'cascade_deadcode.txt'), 'w', encoding='utf-8',
        newline='\n').write('\n'.join(out) + '\n')
print(out[0])
print('整类皆死:', sum(1 for cq, ms in members.items()
                       if ms and all(m in dead for m in ms)))

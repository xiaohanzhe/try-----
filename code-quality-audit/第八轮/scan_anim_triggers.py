# -*- coding: utf-8 -*-
"""动画来源侦察（只读）：列出 main.py 中所有 play_animation_once / change_animation
调用点及其**归属函数**，用于回答"这个动画到底是谁触发的？"

第八轮背景：用户要求"所有特殊动画（除 walk/run/idle）只交给 AI 判断是否播放"。
光看 `main.py` 里的字面量是不够的 —— 必须知道每个调用点**挂在哪个函数上**，
才能判断它是"用户点了鼠标"、"物理状态机"、还是"环境自动触发（要收编）"。
本工具就是这个判据的生产器；对应的长期闸门断言在 `verify_round8_anim.py` 的 H1.1。

用法：
    python scan_anim_triggers.py            # 打印到 stdout
    python scan_anim_triggers.py out.txt    # 落盘
"""
import ast
import io
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = {'play_animation_once', 'change_animation'}


def find_main():
    """从脚本所在目录逐级上溯，找到 ralsei_pet/src/main.py（与摆放位置无关）。"""
    cur = HERE
    for _ in range(6):
        cand = os.path.join(cur, 'ralsei_pet', 'src', 'main.py')
        if os.path.exists(cand):
            return cand
        cur = os.path.dirname(cur)
    raise SystemExit('找不到 ralsei_pet/src/main.py（请把本脚本放在仓库内）')


def enclosing_map(tree):
    """{Call 节点: [外层函数名…]}，自外向内。"""
    out = {}

    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def _visit_func(self, node):
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        visit_FunctionDef = _visit_func
        visit_AsyncFunctionDef = _visit_func

        def visit_Call(self, node):
            f = node.func
            if isinstance(f, ast.Attribute):
                name = f.attr
            elif isinstance(f, ast.Name):
                name = f.id
            else:
                name = None
            if name in TARGETS:
                out[node] = list(self.stack)
            self.generic_visit(node)

    V().visit(tree)
    return out


def main():
    path = find_main()
    src = open(path, encoding='utf-8').read()
    rows = sorted(enclosing_map(ast.parse(src)).items(),
                  key=lambda kv: kv[0].lineno)

    lines = [
        '# play_animation_once / change_animation 调用点 → 归属函数',
        '# 文件: %s  (%d 行)' % (path, src.count('\n') + 1),
        '',
    ]
    for node, stack in rows:
        f = node.func
        attr = f.attr if isinstance(f, ast.Attribute) else f.id
        if node.args:
            a0 = node.args[0]
            arg = (repr(a0.value) if isinstance(a0, ast.Constant)
                   else ast.dump(a0)[:40])
        else:
            arg = ''
        kw = [k.arg for k in node.keywords]
        lines.append('L%-6d %-22s %-14s owner=%s  kw=%s'
                     % (node.lineno, attr, arg,
                        ' > '.join(stack) or '<module>', kw))

    c = Counter(' > '.join(s) or '<module>' for _n, s in rows)
    lines += ['', '# 归属函数统计（%d 个函数，%d 个调用点）' % (len(c), len(rows))]
    for owner, n in c.most_common():
        lines.append('%3d  %s' % (n, owner))

    text = '\n'.join(lines)
    if len(sys.argv) > 1:
        with io.open(sys.argv[1], 'w', encoding='utf-8') as fh:
            fh.write(text)
    else:
        sys.stdout.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())

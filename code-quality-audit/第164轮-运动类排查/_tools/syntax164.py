# -*- coding: utf-8 -*-
"""第164轮 · 改完 `main.py` 后的即时体检（语法 / EOL / 关键符号 / 未接线残留）。

★ 只用 `ast.parse`，**不 `py_compile`** —— 那会产 `.pyc` 改变被测目录状态
  （本项目的复检纪律：复检不许改变被测状态）。
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

fails = []


def ok(cond, msg):
    print(('  [PASS] ' if cond else '  [FAIL] ') + msg)
    if not cond:
        fails.append(msg)


def main():
    with io.open(MAIN, 'r', encoding='utf-8', newline='') as f:
        src = f.read()

    print('=== 1 语法 ===')
    try:
        tree = ast.parse(src)
        ok(True, 'ast.parse 通过（%d 个顶层节点）' % len(tree.body))
    except SyntaxError as e:
        ok(False, 'ast.parse 失败: %s 第 %s 行' % (e.msg, e.lineno))
        return 1

    print('=== 2 行尾（原文件是 CRLF，不许掺裸 LF）===')
    n_crlf = src.count('\r\n')
    n_lf = src.count('\n') - n_crlf
    n_cr = src.count('\r') - n_crlf
    ok(n_lf == 0, '裸 LF = %d（期望 0）' % n_lf)
    ok(n_cr == 0, '裸 CR = %d（期望 0）' % n_cr)
    ok(n_crlf > 1000, 'CRLF 行数 = %d（应在千级）' % n_crlf)

    print('=== 3 新增/改动的符号都在 ===')
    ok('def _start_surprised_hop' in src, '新方法 _start_surprised_hop 已定义')
    ok("if getattr(self, '_hop_mode', False):" in src,
       'handle_jump 里的 _hop_mode 短路在位')
    ok('self._hop_mode = False' in src, '落地处清 _hop_mode 在位')
    ok('self._start_surprised_hop()' in src,
       'update_animation 里调用在位')
    ok(src.count('self._start_surprised_hop()') >= 2,
       '调用点 >= 2（trigger_surprise + update_animation，实得 %d）'
       % src.count('self._start_surprised_hop()'))

    print('=== 4 旧的死写法已消失（不许回潮）===')
    # ★★ 第一版这里用纯文本扫 `'self.jump_height = 20' not in src` —— 结果被
    #   **我自己写在 docstring 里的举例**打红（我解释了"旧写法长什么样"）。
    #   这正是项目里记了七八次的那条：**"禁某短语出现"禁纯文本扫，一律 AST**。
    _bad = []
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Assign):
            for _t in _n.targets:
                if (isinstance(_t, ast.Attribute) and _t.attr == 'jump_height'
                        and isinstance(_n.value, ast.Constant)
                        and _n.value.value == 20):
                    _bad.append(_n.lineno)
    ok(not _bad, 'AST 里没有 `jump_height = 20` 的赋值（实得 %d 处）' % len(_bad))
    # 正控制：同一套 AST 判据必须能抓到**真的**赋值（证明它不是在空跑）
    _probe = ast.parse('self.jump_height = 20')
    _hit = [n for n in ast.walk(_probe)
            if isinstance(n, ast.Assign)
            for t in n.targets
            if isinstance(t, ast.Attribute) and t.attr == 'jump_height']
    ok(bool(_hit), '正控制：同一条 AST 判据能识别真的 `jump_height` 赋值')
    # 负控制：注释里提到它**不该**算
    _probe2 = ast.parse('# self.jump_height = 20\nx = 1')
    _hit2 = [n for n in ast.walk(_probe2) if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Attribute) and t.attr == 'jump_height'
                     for t in n.targets)]
    ok(not _hit2, '负控制：注释里的 `jump_height = 20` 不算赋值')

    print('=== 5 括号/缩进没被写坏（AST 之外的结构自检）===')
    _cls = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    _pet = [c for c in _cls if c.name == 'RalseiPet']
    ok(bool(_pet), 'RalseiPet 类还在')
    if _pet:
        _methods = {m.name for m in _pet[0].body
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
        ok('_start_surprised_hop' in _methods, '新方法是 RalseiPet 的成员')
        ok('handle_jump' in _methods, 'handle_jump 仍是成员')
        ok('trigger_surprise' in _methods, 'trigger_surprise 仍是成员')
        ok('_restore_surprised_jump' in _methods, '第99轮那条还原路径仍在')

    print()
    if fails:
        print('失败 %d 项' % len(fails))
        return 1
    print('[PASS] 即时体检全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())

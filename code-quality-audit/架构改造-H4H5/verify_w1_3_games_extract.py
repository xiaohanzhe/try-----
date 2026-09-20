# -*- coding: utf-8 -*-
"""W1-3 搬运保真校验：证明 games_controller 里的 7 个方法体与搬走前的 main.py 逐字相同。

判据（两条都要过）：
  A. 方法级：AST 取 `FunctionDef` 的源码段，把 `self.` 前缀（宿主的）与 `self.p.`
     （控制器的宿主引用）归一后比较 —— 归一只做「接收者写法」的映射，**不动任何
     其他字符**，所以实参、注释、字面量、缩进只要差一个字节就会 FAIL。
  B. 文件级：本脚本自己读两个文件，不做任何 shell 管道（避免 GBK 有损解码）。

反例控制（必须有鉴别力）：
  故意改一个字符（把某方法的某个数字 +1）再比一次，必须 FAIL —— 否则说明判据是
  「两侧同值」的假锁。
"""
import ast
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OLD = os.path.join(HERE, '_evidence', 'w1_3_main_before.py')
CUR = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
NEW = os.path.join(ROOT, 'ralsei_pet', 'modules', 'games_controller.py')

METHODS = [
    'start_rock_paper_scissors',
    'play_rock_paper_scissors',
    'determine_rock_paper_scissors_winner',
    'end_rock_paper_scissors',
    'start_guess_number',
    'play_guess_number',
    'end_guess_number',
]

n_pass = n_fail = 0


def check(cond, msg):
    global n_pass, n_fail
    if cond:
        n_pass += 1
        print('[PASS] ' + msg)
    else:
        n_fail += 1
        print('[FAIL] ' + msg)


def read(p):
    with io.open(p, encoding='utf-8', newline='') as fh:
        return fh.read()


def class_method_src(src, cls_name):
    """返回 {method_name: 源码段}，取参数列表首行到函数结束（含 body，不含外层缩进归一）。"""
    tree = ast.parse(src)
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    seg = ast.get_source_segment(src, sub)
                    out[sub.name] = seg
    return out


def strip_self(seg):
    """归一「接收者写法」：`self.p.xxx` → `self.xxx`。

    只做这一个替换 —— 它对应「宿主 self.xxx 在控制器里写 self.p.xxx」这一条
    必然差异。其余一个字符都不动。
    """
    return seg.replace('self.p.', 'self.')


def main():
    for p in (OLD, CUR, NEW):
        if not os.path.exists(p):
            print('[FAIL] 缺文件: %s' % p)
            return 1

    old_src, cur_src, new_src = read(OLD), read(CUR), read(NEW)
    old_m = class_method_src(old_src, 'RalseiPet')
    cur_m = class_method_src(cur_src, 'RalseiPet')
    new_m = class_method_src(new_src, 'GamesController')

    # --- 1. 搬走前：7 个方法都在 RalseiPet 上 ---
    for m in METHODS:
        check(m in old_m, '搬移前 RalseiPet 有 %s' % m)

    # --- 2. 搬走后：7 个方法都不在 RalseiPet 上（真的搬走了，不是复制） ---
    for m in METHODS:
        check(m not in cur_m, '搬移后 RalseiPet 不再定义 %s（只留转发）' % m)

    # --- 3. 7 个方法都在 GamesController 上 ---
    for m in METHODS:
        check(m in new_m, 'GamesController 定义 %s' % m)

    # --- 4. 逐方法逐字节等价（归一 self.p. 后） ---
    for m in METHODS:
        if m not in old_m or m not in new_m:
            check(False, '%s 无法比较（缺段）' % m)
            continue
        a = old_m[m].replace('\r\n', '\n').rstrip()
        b = strip_self(new_m[m]).replace('\r\n', '\n').rstrip()
        check(a == b, '%s 方法体逐字等价' % m)
        if a != b:
            # 打印首个差异位置，便于定位
            for i, (ca, cb) in enumerate(zip(a, b)):
                if ca != cb:
                    print('       首个差异 @%d: old=%r new=%r' % (i, a[max(0, i-40):i+40], b[max(0, i-40):i+40]))
                    break
            if len(a) != len(b):
                print('       长度 old=%d new=%d' % (len(a), len(b)))

    # --- 5. 反例控制：改一个字符必须能测出来 ---
    # 注意语义：这里断言的是「判据**有鉴别力**」——篡改后 must 判为不等。
    # 所以正确的结果是 `tampered != base`（→ PASS）；若篡改后仍相等，说明
    # 判据退化成"自己跟自己比"，那才是真 FAIL。
    #
    # 坑（本脚本第一版真踩）：needle 写成 `"max_attempts"`（ASCII 双引号），而
    # 源码里是 `'max_attempts'`（单引号）→ replace 一次都没命中 → 篡改是空操作
    # → 判据"篡改后仍相等" → 反例控制**假通过**。所以下面**先断言 needle 命中**，
    # 命中次数不为 1 就直接判 FAIL —— 这是"两个反例互相作证"的纪律：
    # 篡改必须真的发生，判据必须真的能测出来。
    if 'start_guess_number' in new_m:
        base = old_m['start_guess_number'].replace('\r\n', '\n').rstrip()
        raw_new = strip_self(new_m['start_guess_number']).replace('\r\n', '\n').rstrip()
        needle = "'max_attempts'"
        hits = raw_new.count(needle)
        check(hits >= 1, '反例控制：篡改 needle %r 在源码中命中 %d 次（必须 ≥1）' % (needle, hits))
        tampered = raw_new.replace(needle, "'max_attemptsX'", 1)
        check(tampered != raw_new, '反例控制：篡改确实改变了文本（不是空操作）')
        check(tampered != base,
              '反例控制：篡改一个字符后判据判为不等（证明判据有鉴别力）')
        check(raw_new == base,
              '反例控制：未篡改的原文仍判为相等（排除替换式自伤）')

    # --- 6. handle_game_input 仍在宿主（本 PR 刻意不搬） ---
    check('handle_game_input' in cur_m, 'handle_game_input 仍在 RalseiPet（本 PR 刻意不搬）')
    check('handle_game_input' not in new_m, 'handle_game_input 未被搬进 GamesController')

    # --- 7. 控制器不 import 任何项目内模块（初始化环纪律） ---
    tree = ast.parse(new_src)
    proj_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for al in node.names:
                if al.name.split('.')[0] not in ('random', 'time', 'logging', 'os', 'sys', 'json'):
                    proj_imports.append(al.name)
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or '')
            if mod.split('.')[0] not in ('__future__',):
                proj_imports.append(mod)
    check(not proj_imports, 'games_controller 不 import 项目内模块（实际: %r）' % proj_imports)

    # --- 8. 状态仍在宿主（只搬方法不搬状态） ---
    for attr in ('game_state', 'guess_number_game', 'rock_paper_scissors_options'):
        check(attr not in new_src or ('self.%s =' % attr) not in new_src,
              '控制器不持有状态 self.%s（只借宿主）' % attr)

    print()
    print('合计：PASS=%d FAIL=%d' % (n_pass, n_fail))
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())

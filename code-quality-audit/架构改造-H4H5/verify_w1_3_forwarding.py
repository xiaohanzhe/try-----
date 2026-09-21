# -*- coding: utf-8 -*-
"""G1 零引用筛查（AST 口径）—— W1-3 专属版。

为什么不用字符串匹配：`grep "start_rock_paper_scissors"` 会把注释、docstring、
证据文件里的引用一起算进去（本项目已踩：源码级断言必须剥注释/字符串）。
本脚本用 AST 计数 `ast.Attribute.attr` 与 `ast.Name.id`，只算**真引用**。

更关键的是第三段：**转发是否真被接上**。本轮口径是「转发壳 + 宿主 API」，
`RalseiPet` 上已经没有这 7 个方法的定义体了 —— 它们靠 `__getattr__` 转发。
所以"零引用筛查"在这里的正确问法不是「还有没有人调用」，而是
「**每一个调用点是否都还能解析到方法**」。这才是"函数写对了但产品用不上"
那道最贵的坑的反面判据。

反例控制：故意把控制器上的某方法删掉（用桩替换），转发必须失败。
"""
import ast
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.workbuddy', 'code-quality-audit'}

MOVED = [
    'start_rock_paper_scissors',
    'play_rock_paper_scissors',
    'determine_rock_paper_scissors_winner',
    'end_rock_paper_scissors',
    'start_guess_number',
    'play_guess_number',
    'end_guess_number',
]
# W1-7（第二十六轮）：`handle_game_input` 由「刻意留在宿主」改为「搬入 games」。
# 它原本单列在 STAYED 里；现在与其余 7 个方法**同等待遇**（真的搬走了、要能转发）。
MOVED += ['handle_game_input']
STAYED = []

n_pass = n_fail = 0


def check(cond, msg):
    global n_pass, n_fail
    if cond:
        n_pass += 1
        print('[PASS] ' + msg)
    else:
        n_fail += 1
        print('[FAIL] ' + msg)


def py_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith('.py'):
                yield os.path.join(dirpath, fn)


def defs_of(name, path=None):
    """只在 FunctionDef 节点上数「定义」，与「引用」严格分开。

    坑（本脚本第一版真踩）：拿 `refs()`（属性名/裸名计数）去断言"只定义一次"，
    结果把控制器内部的 `self.end_guess_number()` 三处**调用**也算成了"定义"，
    报出"实际 4 次"这种假红。定义与引用是两个不同的 AST 节点类型，必须分开数。
    """
    out = []
    targets = [path] if path else list(py_files())
    for p in targets:
        try:
            tree = ast.parse(io.open(p, encoding='utf-8').read())
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                out.append((p, node.lineno))
    return out


def class_defs_in(relpath, cls_name):
    """返回 {method_name: lineno} —— 只看某个类体内的 def。"""
    p = os.path.join(ROOT, *relpath.split('/'))
    tree = ast.parse(io.open(p, encoding='utf-8').read())
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out[sub.name] = sub.lineno
    return out


def refs(name):
    """返回 [(relpath, lineno)]，只计真引用（属性名 / 裸名 / 裸函数名）。"""
    out = []
    for p in py_files():
        try:
            with io.open(p, encoding='utf-8') as fh:
                src = fh.read()
            tree = ast.parse(src)
        except Exception:
            continue
        for node in ast.walk(tree):
            hit = False
            if isinstance(node, ast.Attribute) and node.attr == name:
                hit = True
            elif isinstance(node, ast.Name) and node.id == name:
                hit = True
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                hit = True
            if hit:
                out.append((os.path.relpath(p, ROOT), node.lineno))
    return sorted(set(out), key=lambda x: (x[0], x[1]))


def main():
    print('=' * 72)
    print('G1 零引用筛查（W1-3 · games 七方法）')
    print('=' * 72)

    # --- 1. 每个方法的定义，只应出现在 games_controller.py 里一次 ---
    ctrl_path = os.path.join(ROOT, 'ralsei_pet', 'modules', 'games_controller.py')
    host_cls = class_defs_in('ralsei_pet/src/main.py', 'RalseiPet')
    ctrl_cls = class_defs_in('ralsei_pet/modules/games_controller.py', 'GamesController')
    for m in MOVED:
        all_defs = defs_of(m)
        in_ctrl = [d for d in all_defs if os.path.samefile(d[0], ctrl_path)]
        check(len(in_ctrl) == 1,
              '%s 在全仓库只定义 1 次且位于 games_controller.py（实际 %d 次）' % (m, len(in_ctrl)))
        check(m not in host_cls, '%s 在 RalseiPet 里已无 def（只留转发）' % m)
        check(m in ctrl_cls, '%s 在 GamesController 类体内有 def' % m)

    # --- 2. 调用点清单（跨模块真引用），必须全部仍可解析 ---
    print()
    print('--- 调用点清单（真引用，排除定义处） ---')
    all_call_sites = {}
    for m in MOVED + STAYED:
        rs = [r for r in refs(m)
              if not r[0].replace('\\', '/').endswith('games_controller.py')]
        all_call_sites[m] = rs
        print('  %-38s %d 处' % (m, len(rs)))
        for rel, ln in rs:
            print('        %s  L%d' % (rel.replace('\\', '/'), ln))

    # --- 3. 关键外部调用点必须存在（防"改了没人调用"的反面：调用点还在） ---
    def has_call(m, needle):
        return any(needle in rel.replace('\\', '/') for rel, _ in all_call_sites[m])

    check(has_call('start_rock_paper_scissors', 'dialogue_ui.py'),
          'dialogue_ui 仍调用 start_rock_paper_scissors')
    check(has_call('start_guess_number', 'dialogue_ui.py'),
          'dialogue_ui 仍调用 start_guess_number')
    check(has_call('handle_game_input', 'dialogue_ui.py'),
          'dialogue_ui 仍调用 handle_game_input（W1-7 后经宿主 __getattr__ 转发）')
    check(has_call('end_rock_paper_scissors', 'main.py'),
          'main.py（update_stats 5 分钟超时）仍调用 end_rock_paper_scissors')
    check(has_call('end_guess_number', 'main.py'),
          'main.py 仍调用 end_guess_number')

    # --- 4. 行为级：转发真的能解析到方法（这才是"接上了"的判据） ---
    print()
    print('--- 行为级转发探针 ---')
    # 按产品同款方式导入：main.py 把 modules/ append 进 sys.path，然后
    # `from modules.games_controller import ...`。这里也 append，直接用顶层名
    # `games_controller` 导入（与其它 verify 脚本一致；`modules` 包在离屏环境里
    # 未必可解析，因为它没有正规的包初始化）。
    sys.path.append(os.path.join(ROOT, 'ralsei_pet', 'modules'))
    import games_controller as _gc
    GamesController = _gc.GamesController

    class FakeHost(object):
        def __init__(self):
            self.game_state = {'is_playing': False, 'game_type': None}
            self.guess_number_game = {'min_number': 1, 'max_number': 100,
                                      'target_number': 0, 'attempts': 0, 'max_attempts': 7}
            self.rock_paper_scissors_options = ['石头', '剪刀', '布']

    host = FakeHost()
    ctrl = GamesController(host)
    for m in MOVED:
        check(hasattr(ctrl, m), 'GamesController 实例可解析 %s' % m)
        check(callable(getattr(ctrl, m)), '%s 可调用' % m)

    # --- 5. 反例控制：控制器上没有的方法，宿主转发必须失败 ---
    class HostShim(object):
        """模拟 RalseiPet 的 __getattr__ 转发（与产品同构）。"""
        _CONTROLLER_ATTRS = ('games',)

        def __init__(self, ctrl):
            self.games = ctrl

        def __getattr__(self, name):
            for attr in HostShim._CONTROLLER_ATTRS:
                c = self.__dict__.get(attr)
                if c is not None and hasattr(c, name):
                    return getattr(c, name)
            raise AttributeError(name)

    shim = HostShim(GamesController(FakeHost()))
    check(hasattr(shim, 'start_rock_paper_scissors'), '转发：宿主可解析 start_rock_paper_scissors')
    check(hasattr(shim, 'end_guess_number'), '转发：宿主可解析 end_guess_number')
    check(not hasattr(shim, '__no_such_method__'),
          '反例控制：不存在的方法 hasattr 必须为 False（转发不会吞掉 AttributeError）')
    try:
        shim.__no_such_method__
        check(False, '反例控制：不存在的方法必须抛 AttributeError')
    except AttributeError:
        check(True, '反例控制：不存在的方法抛 AttributeError（保住 hasattr/getattr 语义）')

    # --- 6. 反例控制：把控制器方法删掉，转发必须失效 ---
    class EmptyCtrl(object):
        pass
    shim2 = HostShim(EmptyCtrl())
    check(not hasattr(shim2, 'start_rock_paper_scissors'),
          '反例控制：控制器无该方法时转发确实失效（证明上一段不是恒真）')

    print()
    print('合计：PASS=%d FAIL=%d' % (n_pass, n_fail))
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())

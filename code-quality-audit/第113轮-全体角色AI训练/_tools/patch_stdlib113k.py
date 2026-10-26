# -*- coding: utf-8 -*-
"""修 `check73 B2` / `check86 A` 的 stdlib 白名单：**手抄的白名单会漂**。

现象（第113轮k 全量 G2）：两个套件各 FAIL=1，报红行完全相同 —
    `零依赖：顶层 import 只含标准库（实得 ['collections', 're']）`
根因：本轮 `place_matches()` 用了 `re.search`（词边界），`npc_life` 顶层
      因此多了 `import re` —— 而 **`re` 本来就是标准库**。
      两份判据各自**手抄**了一份白名单（`{'collections'}` / 七个名字），
      抄的时候没写 `re` ⇒ **判据过窄 = 误报**（不是产品缺陷）。

★ 修法：不再手抄，直接问解释器 `sys.stdlib_module_names`（3.10+；
  取不到就退回一份仍然正确的兜底集）。这样以后再加 `itertools` 之类
  标准库，判据**自动跟着走**，不会再因为"忘了往白名单里加一个名字"假红。
★ 注意**没有放宽**：判据守的是「只含**标准库**」，`main` / `modules` 这类
  项目内模块不在 `stdlib_module_names` 里，照样报红（另有专门判据守）。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
NL = '\r\n'

FALLBACK = ("        {'collections', 're', 'os', 'json', 'math', 'random', 'time',\n"
            "         'logging', 'itertools', 'functools', 'typing', 'dataclasses'}")

# ---------------------------------------------------------------- check73
C73_OLD = """check('B2 ★ 零依赖：`npc_life` 顶层 import 只含标准库（实测 {collections}）',
      _top_imports <= {'collections'}, str(sorted(_top_imports)))"""
C73_NEW = """# ★★ 白名单**不许手抄**：第113轮k 加 `import re`（`place_matches` 要词边界）时，
#   这里手抄的 `{'collections'}` 漏了它 ⇒ 标准库被判成"非标准库"，**误报**。
#   直接问解释器要标准库名单（`sys.stdlib_module_names`，3.10+），
#   以后再加标准库判据自动跟着走；`main` / `modules` 这类项目内模块仍会报红。
_STDLIB = set(getattr(sys, 'stdlib_module_names', ())) or {
    'collections', 're', 'os', 'json', 'math', 'random', 'time',
    'logging', 'itertools', 'functools', 'typing', 'dataclasses'}
check('B2 ★ 零依赖：`npc_life` 顶层 import 只含标准库（白名单取 sys.stdlib_module_names）',
      _top_imports <= _STDLIB, str(sorted(_top_imports)))"""

# ---------------------------------------------------------------- check86
C86_OLD = """_ALLOWED = {'logging', 'math', 'collections', 'os', 'time', 'random', 'json'}"""
C86_NEW = """# ★★★ 白名单**不许手抄**（第113轮k 实测）：加 `import re` 后这份手抄表漏了它
#   ⇒ 标准库被判成"非标准库"、两个套件同时假红。直接问解释器要名单，
#   项目内模块（`main` / `modules`）不在里面，判据**没有放宽**。
_ALLOWED = set(getattr(sys, 'stdlib_module_names', ())) or {
    'logging', 'math', 'collections', 'os', 'time', 'random', 'json', 're'}"""


def pat(path, old, new, tag):
    t = io.open(path, 'r', encoding='utf-8', newline='').read()
    if new.replace('\n', NL) in t:
        print('[SKIP] %s 已是新版' % tag)
        return True
    o = old.replace('\n', NL)
    n = new.replace('\n', NL)
    if o not in t:
        print('[FAIL] %s 锚点没命中' % tag)
        return False
    io.open(path, 'w', encoding='utf-8', newline='').write(t.replace(o, n, 1))
    print('[ OK ] %s' % tag)
    import ast
    try:
        ast.parse(io.open(path, 'r', encoding='utf-8', newline='').read())
        print('        语法 PASS')
    except SyntaxError as e:
        print('        [FAIL] 语法 %s' % e)
        return False
    return True


def main():
    ok = pat(os.path.join(ROOT, 'code-quality-audit', '第73轮-自由生活', '_tools',
                          'check73.py'), C73_OLD, C73_NEW, 'check73 B2 白名单')
    ok = pat(os.path.join(ROOT, 'code-quality-audit', '第86轮-主线NPC自主开口', '_tools',
                          'check86.py'), C86_OLD, C86_NEW, 'check86 A 白名单') and ok
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

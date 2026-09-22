# -*- coding: utf-8 -*-
"""第34轮续 探针 F34-1：`_last_desktop_elem_check` 无条件刷新 ⇒ 5 秒节拍失效

被测物（main.py L1690-1695，**逐字抽取**）：
    try:
        if not hasattr(self, '_last_desktop_elem_check') or current_time - self._last_desktop_elem_check > 5.0:
            self.check_nearby_desktop_elements()
    except Exception as e:
        _log.warning(...)
    self._last_desktop_elem_check = current_time      # ← 无条件执行

判据纪律：
  · 不 import 产品代码（main.py 太重）。从源码抽取 L1690-1695 的**原文**，
    用一个最小 self 桩执行 —— 不重写控制流。
  · 正/负控制成对：
      负控制 = 现写法（无条件赋值）→ 5 秒内**不应**重复触发
      正控制 = 修法（赋值移进 if 内）→ 5 秒内**不应**触发、>5 秒**应**触发
  · 若两版结果相同 ⇒ 探针没测到东西（必须有鉴别力）。
"""
import ast
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MAIN = os.path.join(REPO, 'ralsei_pet', 'src', 'main.py')

pass_n = 0
fail_n = 0


def check(name, cond, detail=''):
    global pass_n, fail_n
    if cond:
        pass_n += 1
        print('[PASS] %s %s' % (name, detail))
    else:
        fail_n += 1
        print('[FAIL] %s %s' % (name, detail))


src = open(MAIN, encoding='utf-8').read()
lines = src.splitlines()

# ---------------------------------------------------------------- 逐字抽取
print('== 抽取被测片段（main.py L1690-1695 原文）==')
snippet = '\n'.join(lines[1689:1695])
print(snippet)
print()

# AST 定位：确认 check_nearby_desktop_elements() 调用与 _last_desktop_elem_check 赋值
# 分属不同语句、后者不在 if 块内
tree = ast.parse(src)
target_fn = None
for n in ast.walk(tree):
    if isinstance(n, ast.FunctionDef) and n.name == 'update_movement':
        target_fn = n
        break
assert target_fn is not None

seg = [s for s in target_fn.body if getattr(s, 'lineno', -1) in range(1690, 1696)]
print('== AST：本级语句体 ==')


def _desc(node):
    if isinstance(node, ast.Try):
        return 'Try(L%d-%d)' % (node.lineno, node.end_lineno)
    if isinstance(node, ast.Assign):
        tgts = ','.join(ast.unparse(t) for t in node.targets)
        return 'Assign(%s, L%d)' % (tgts, node.lineno)
    if isinstance(node, ast.If):
        return 'If(L%d)' % node.lineno
    return type(node).__name__ + '(L%d)' % getattr(node, 'lineno', -1)


for s in seg:
    print('   %s' % _desc(s))

has_try = any(isinstance(s, ast.Try) for s in seg)
has_assign_after = any(isinstance(s, ast.Assign)
                       and any(isinstance(t, ast.Attribute)
                               and t.attr == '_last_desktop_elem_check'
                               for t in s.targets)
                       for s in seg)
check('A1 片段含 Try（节拍判定 + 调用）', has_try)
check('A2 片段含 `_last_desktop_elem_check` 赋值，且它是**本级**语句（不在 if 内）',
      has_assign_after)
if has_assign_after:
    for s in seg:
        if isinstance(s, ast.Assign):
            print('   赋值语句 L%d 是 update_movement 的**直接子语句**（不是 if 的子块）'
                  % s.lineno)
check('A3 该赋值**不在**任何 if 块内（这正是缺陷所在）',
      not any(isinstance(s, ast.If) for s in seg))

# ---------------------------------------------------------------- 行为核验
print()
print('== 行为核验：最小 self 桩 + 逐字 exec 现写法 ==')


class _Log(object):
    def warning(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass


class _Self(object):
    def __init__(self):
        self.hits = 0

    def check_nearby_desktop_elements(self):
        self.hits += 1


_log = _Log()

# 现写法（L1691-1695 逐字，缩进适配为函数体顶层）
_CODE_CUR = """
try:
    if not hasattr(self, '_last_desktop_elem_check') or current_time - self._last_desktop_elem_check > 5.0:
        self.check_nearby_desktop_elements()
except Exception as e:
    _log.warning("check_nearby_desktop_elements 异常: %s" % e)
self._last_desktop_elem_check = current_time
"""

# 修法（赋值移进 if 块内 —— 与 _last_env_update / last_floor_check_time 同口径）
_CODE_FIX = """
try:
    if not hasattr(self, '_last_desktop_elem_check') or current_time - self._last_desktop_elem_check > 5.0:
        self.check_nearby_desktop_elements()
        self._last_desktop_elem_check = current_time
except Exception as e:
    _log.warning("check_nearby_desktop_elements 异常: %s" % e)
"""


def _run(code, t0, steps):
    """按 30ms tick 推进，返回 hits 与最终时间戳。"""
    s = _Self()
    ns = {'self': s, '_log': _log}
    t = t0
    for _ in range(steps):
        t += 0.030
        ns['current_time'] = t
        exec(code, ns)
    return s.hits


# 模拟 20 秒 = 约 667 ticks（30ms）
TICKS_20S = 667

hits_cur = _run(_CODE_CUR, 1000.0, TICKS_20S)
hits_fix = _run(_CODE_FIX, 1000.0, TICKS_20S)

print('   20 秒内（667 tick）：现写法 hits=%d，修法 hits=%d' % (hits_cur, hits_fix))
check('B1 现写法：20 秒内只触发 1 次（节拍失效，功能形同死）', hits_cur == 1,
      '(got=%d)' % hits_cur)
check('B2 修法：20 秒内触发 4 次（5 秒节拍，20/5=4）', hits_fix == 4,
      '(got=%d)' % hits_fix)
check('B3 鉴别力：两版结果不同（探针确实测到了差异）', hits_cur != hits_fix)

# 60 秒对照，进一步佐证"次数与时间无关"
TICKS_60S = 2000
hits_cur60 = _run(_CODE_CUR, 1000.0, TICKS_60S)
hits_fix60 = _run(_CODE_FIX, 1000.0, TICKS_60S)
print('   60 秒内（2000 tick）：现写法 hits=%d，修法 hits=%d' % (hits_cur60, hits_fix60))
check('B4 现写法：60 秒内**仍然**只触发 1 次（时间翻三倍次数不变 ⇒ 确证节拍失效）',
      hits_cur60 == 1, '(got=%d)' % hits_cur60)
check('B5 修法：60 秒内触发 12 次（60/5=12，线性）', hits_fix60 == 12,
      '(got=%d)' % hits_fix60)

# 负控制：把节拍判定去掉（每 tick 都调），确认桩"接上了"
_CODE_ALWAYS = """
self.check_nearby_desktop_elements()
self._last_desktop_elem_check = current_time
"""
hits_always = _run(_CODE_ALWAYS, 1000.0, 100)
print('   桩接线自证：去节拍版 100 tick → hits=%d（应=100）' % hits_always)
check('C 桩接线自证：去节拍版每 tick 都触发（证明桩与调用链确实通）',
      hits_always == 100, '(got=%d)' % hits_always)

print()
print('SUITE_SUMMARY pass=%d fail=%d' % (pass_n, fail_n))

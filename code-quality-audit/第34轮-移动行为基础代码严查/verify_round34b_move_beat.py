# -*- coding: utf-8 -*-
"""第三十四轮续 · 移动核心（update_movement）回归锁：节拍时间戳不得被无条件推进

锁住本轮实测确认的缺陷 F34-1：

    main.py `update_movement` 里 `check_nearby_desktop_elements` 的 5 秒节拍，
    其时间戳 `self._last_desktop_elem_check = current_time` 原来写在 `try` 之外
    **无条件执行** ⇒ 时间戳每 tick（30ms）被刷新 ⇒ 节拍判据
    `current_time - _last_desktop_elem_check > 5.0` 除首次外**永远为假**
    ⇒ 该检查一生只跑一次。

    后果链（真机可达）：
      check_nearby_desktop_elements 近乎从不执行
        → react_to_desktop_element 近乎从不执行
          → _note_desktop_observation 从不执行（唯一调用点在此）
            → "宠物凑近桌面文件后的观察"从不进入 AI 事件队列。

判据纪律（对照记忆 §4/§5）：
  · **断言结构，不断言写法**：只判"该赋值语句是否落在 if 的语句体内"，
    不判缩进、不判周边注释、不判变量名风格；
  · 走 **AST**（不 import main.py —— 它 8960 行且需要完整 Qt 环境）；
  · 正/负控制成对：
      A 组 = 结构断言（赋值必须在 If 体内 / 本级不得再有裸赋值）
      B 组 = 行为断言（逐字抽取该片段，用最小 self 桩跑 20s/60s，数触发次数）
      C 组 = 反向控制（确认"节拍判据还在"——防"把节拍整个删掉也 PASS"）
  · 行为组必须自带**接线自证**（去节拍版每 tick 都触发），否则桩没接上会假绿。

输出格式必须是字面量 `[PASS]` / `[FAIL]` —— `run_all.py` 用
`re.findall(r'\[PASS\]|\[\s*OK\s*\]')` 计数。

**不联网、不实例化 App、不需要显示器**（AST + 无 Qt 的纯逻辑重演）。
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

_results = []


def check(cond, msg):
    _results.append(bool(cond))
    print('[PASS] %s' % msg if cond else '[FAIL] %s' % msg)


src = open(MAIN, encoding='utf-8').read()
tree = ast.parse(src)

# 定位 update_movement
_upd = None
for n in ast.walk(tree):
    if isinstance(n, ast.FunctionDef) and n.name == 'update_movement':
        _upd = n
        break

check(_upd is not None, '[PRE] 找到 update_movement（实测 %s）'
      % ('找到' if _upd is not None else '未找到'))

if _upd is None:
    print('SUITE_SUMMARY pass=%d fail=%d' % (len(_results) - sum(_results), sum(_results)))
    sys.exit(1)


# ======================================================================
# [A] 结构断言：赋值必须在 If 体内；本级（update_movement 直接语句）不得再有裸赋值
# ======================================================================
print('--- [A] 结构：节拍时间戳的赋值必须落在 if 语句体内 ---')

TARGET_ATTR = '_last_desktop_elem_check'


def _assigns_in(node_body):
    """返回 node_body 里所有 Assign 的 (目标属性名列表, 行号)。"""
    out = []
    for st in node_body:
        if isinstance(st, ast.Assign):
            names = [t.attr for t in st.targets
                     if isinstance(t, ast.Attribute)]
            out.append((names, st.lineno))
        # 只下探一层 if/try 的语句体（本片段的形态固定）
        for sub in ('body', 'orelse', 'finalbody'):
            for inner in getattr(st, sub, []) or []:
                if isinstance(inner, ast.Assign):
                    names = [t.attr for t in inner.targets
                             if isinstance(t, ast.Attribute)]
                    out.append((names, inner.lineno))
                for s2 in getattr(inner, 'body', []) or []:
                    if isinstance(s2, ast.Assign):
                        names = [t.attr for t in s2.targets
                                 if isinstance(t, ast.Attribute)]
                        out.append((names, s2.lineno))
            for h in getattr(st, 'handlers', []) or []:
                for s2 in h.body:
                    if isinstance(s2, ast.Assign):
                        names = [t.attr for t in s2.targets
                                 if isinstance(t, ast.Attribute)]
                        out.append((names, s2.lineno))
    return out


# A1：update_movement 本级直接子语句里，不得再有 _last_desktop_elem_check 裸赋值
top_level_bare = []
for st in _upd.body:
    if isinstance(st, ast.Assign):
        names = [t.attr for t in st.targets if isinstance(t, ast.Attribute)]
        if TARGET_ATTR in names:
            top_level_bare.append(st.lineno)

check(len(top_level_bare) == 0,
      '[A1] update_movement 本级**不得**有裸的 `%s = ...`（原缺陷写法；实测 L%s）'
      % (TARGET_ATTR, top_level_bare if top_level_bare else '无'))

# A2：必须存在一处该赋值，且它在某个 If 的语句体内
found_in_if = []
for st in _upd.body:
    if isinstance(st, ast.Try):
        for inner in st.body:
            if isinstance(inner, ast.If):
                for s2 in inner.body:
                    if isinstance(s2, ast.Assign):
                        names = [t.attr for t in s2.targets
                                 if isinstance(t, ast.Attribute)]
                        if TARGET_ATTR in names:
                            found_in_if.append(s2.lineno)

check(len(found_in_if) >= 1,
      '[A2] 必须存在一处 `%s = ...` 落在 if 语句体内（实测 L%s）'
      % (TARGET_ATTR, found_in_if if found_in_if else '无'))

# A3：节拍判据本身必须还在（反向控制：防"把节拍整个删掉"也 PASS）
has_beat = False
for st in _upd.body:
    if isinstance(st, ast.Try):
        for inner in st.body:
            if isinstance(inner, ast.If):
                cond_src = ast.unparse(inner.test)
                if TARGET_ATTR in cond_src and '5.0' in cond_src:
                    has_beat = True

check(has_beat,
      '[A3] 反向控制：5 秒节拍判据 `%s` 仍必须存在（防"删掉节拍"也通过）' % TARGET_ATTR)

# A4：调用点必须还在
has_call = False
for st in _upd.body:
    for sub in ast.walk(st):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                and sub.func.attr == 'check_nearby_desktop_elements':
            has_call = True

check(has_call, '[A4] 反向控制：`check_nearby_desktop_elements()` 调用点仍必须存在')


# ======================================================================
# [B] 行为断言：逐字抽取该片段，用最小 self 桩跑 20s / 60s
# ======================================================================
print('--- [B] 行为：节拍必须真的按 5 秒触发（而不是只触发一次）---')

lines = src.splitlines()


def _extract_try_block():
    """抽取 update_movement 里那个 Try 语句的源码（含其后可能的裸赋值）。"""
    for st in _upd.body:
        if isinstance(st, ast.Try):
            # 判断是不是我们要的那段（含 5.0 节拍）
            txt = '\n'.join(lines[st.lineno - 1:st.end_lineno])
            if TARGET_ATTR in txt and '5.0' in txt:
                # 若紧随其后还有本级裸赋值（旧写法），一并纳入
                extra = ''
                for st2 in _upd.body:
                    if isinstance(st2, ast.Assign) and st2.lineno == st.end_lineno + 1:
                        names = [t.attr for t in st2.targets
                                 if isinstance(t, ast.Attribute)]
                        if TARGET_ATTR in names:
                            extra = '\n' + '\n'.join(
                                lines[st2.lineno - 1:st2.end_lineno])
                return txt + extra
    return None


code = _extract_try_block()
check(code is not None, '[B0] 成功抽取被测片段（实测 %s）'
      % ('成功' if code else '失败'))


class _Log(object):
    def warning(self, *a, **k):
        pass


class _Self(object):
    def __init__(self):
        self.hits = 0

    def check_nearby_desktop_elements(self):
        self.hits += 1


def _run(snippet, steps):
    """按 30ms tick 推进，返回触发次数。snippet 需以 self/current_time/_log 为自由变量。

    注意：从 main.py 抽出的片段自带类方法缩进，必须 dedent 后才能 exec。
    """
    import textwrap
    body = textwrap.dedent(snippet).lstrip('\n')
    # 逐字执行前先编译一次，语法错就抛出（避免静默吞掉）
    compiled = compile(body, '<extracted-update_movement-beat>', 'exec')
    s = _Self()
    ns = {'self': s, '_log': _Log()}
    t = 1000.0
    for _ in range(steps):
        t += 0.030
        ns['current_time'] = t
        exec(compiled, ns)
    return s.hits


hits_20 = _run(code, 667)     # ≈20 秒
hits_60 = _run(code, 2000)    # ≈60 秒

check(hits_20 == 4,
      '[B1] 20 秒内必须触发 4 次（5 秒节拍；实测 %d 次）' % hits_20)
check(hits_60 == 12,
      '[B2] 60 秒内必须触发 12 次（线性；实测 %d 次）' % hits_60)
check(hits_60 > hits_20,
      '[B3] 触发次数必须随时间增长（旧缺陷下 20s/60s 都是 1 次；实测 %d -> %d）'
      % (hits_20, hits_60))

# B4：接线自证 —— 去掉节拍后每 tick 都该触发（证明桩是通的）
_PROBE_ALWAYS = """
self.check_nearby_desktop_elements()
"""
hits_always = _run(_PROBE_ALWAYS, 100)
check(hits_always == 100,
      '[B4] 接线自证：无节拍版 100 tick 必须触发 100 次（证明桩与调用链确实通；实测 %d）'
      % hits_always)

# B5：负控制 —— 旧写法（无条件推进时间戳）必须重现"只触发一次"
_OLD = """
try:
    if not hasattr(self, '_last_desktop_elem_check') or current_time - self._last_desktop_elem_check > 5.0:
        self.check_nearby_desktop_elements()
except Exception as e:
    pass
self._last_desktop_elem_check = current_time
"""
hits_old = _run(_OLD, 2000)
check(hits_old == 1,
      '[B5] 负控制：旧写法（无条件推进）在 60 秒内**只能**触发 1 次'
      '（证明本锁确实在区分两种写法；实测 %d）' % hits_old)


# ======================================================================
# [C] 一致性：另两处同口径节拍不得被反向改坏
# ======================================================================
print('--- [C] 一致性：`_last_env_update` / `last_floor_check_time` 仍是块内赋值 ---')

env_ok = False
for st in _upd.body:
    if isinstance(st, ast.If):
        c = ast.unparse(st.test)
        if '_last_env_update' in c:
            for s2 in st.body:
                if isinstance(s2, ast.Assign):
                    names = [t.attr for t in s2.targets if isinstance(t, ast.Attribute)]
                    if '_last_env_update' in names:
                        env_ok = True
            # 也可能嵌在 if/else 两层里
            for s2 in st.body:
                for s3 in getattr(s2, 'body', []) or []:
                    if isinstance(s3, ast.Assign):
                        names = [t.attr for t in s3.targets
                                 if isinstance(t, ast.Attribute)]
                        if '_last_env_update' in names:
                            env_ok = True

check(env_ok, '[C1] `_last_env_update` 的推进仍留在条件块内（同口径）')

floor_ok = False
for st in _upd.body:
    if isinstance(st, ast.If):
        c = ast.unparse(st.test)
        if 'last_floor_check_time' in c:
            for s2 in st.body:
                if isinstance(s2, ast.Assign):
                    names = [t.attr for t in s2.targets if isinstance(t, ast.Attribute)]
                    if 'last_floor_check_time' in names:
                        floor_ok = True
                # 在 try 里
                for s3 in getattr(s2, 'body', []) or []:
                    if isinstance(s3, ast.Assign):
                        names = [t.attr for t in s3.targets
                                 if isinstance(t, ast.Attribute)]
                        if 'last_floor_check_time' in names:
                            floor_ok = True

check(floor_ok, '[C2] `last_floor_check_time` 的推进仍留在条件块内（同口径）')


# ======================================================================
n_fail = len(_results) - sum(_results)
n_pass = sum(_results)
print('SUITE_SUMMARY pass=%d fail=%d' % (n_pass, n_fail))
sys.exit(0 if n_fail == 0 else 1)

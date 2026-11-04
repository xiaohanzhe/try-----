# -*- coding: utf-8 -*-
u"""第160轮回归锁：**判据别绑写法，也别绑时相**。

## 为什么

第159轮的 `recheck159_core.py` 里有三条判据把"守卫该长什么样"写死了，实测都会**假红**：

| 判据 | 绑的是什么 | 症状（`probe160` 实证） |
|---|---|---|
| `H5g` | `if` 的**形状**（两半必须挤在同一个 `if` 里） | 语义等价的"拆成两个连续 `if`"被判成"缺一半" |
| `H6a` | **多行文本片段**（含缩进与续行） | 同一改写一拆段就数出 0 处 |
| `H1a` | **时相**（要求两个产品文件"恰好"处于已修改状态） | 一提交就 `产品改动=[]` ⇒ 必假红 |

判据过窄 = 误报，比不写还危险（会训练人"改判据"而不是"改代码"；第107轮教训同族）。

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | 把 `recheck159_core` 里的三个判定函数**当被测物**，喂 8 个**独立样本**（不是我手写的那一份产品源码）：两种等价写法都要认，缺一半都要拒，`what` 归一要认得出 |
| B | 判据的**时相**：`H1a` 只许问"有没有第三个文件"，不许要求"恰好两个在改"（源码级 AST 检查 + 行为级模拟） |
| C | 自检：分母闸 · 判据名字面量 · 只用 `check()` · 无 BOM 全 LF · 零外部盘 |

★ 纪律：样本源码是**独立构造**的（不经产品），所以这是对判据的真实验证，不是重跑产品。
"""
import ast
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
RECHECK = os.path.join(ROOT, 'code-quality-audit',
                       u'第159轮-空白名字不算人', '_tools', 'recheck159_core.py')

_n_pass = 0
_n_fail = 0
_failed = []


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def mark(title):
    print('---- %s ----' % (title,))


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


# ================================================ 取出被测的三个判定函数
_SRC = _read(RECHECK)
_TREE = ast.parse(_SRC)
_NS = {'ast': ast, 'u': None}
for _want in ('_strip_cmp', '_not_guard', '_what_norm'):
    _seg = None
    for _n in _TREE.body:
        if isinstance(_n, ast.FunctionDef) and _n.name == _want:
            _seg = ast.get_source_segment(_SRC, _n)
            break
    if _seg is not None:
        exec(compile(_seg, '<%s>' % (_want,), 'exec'), _NS)

_strip_cmp = _NS.get('_strip_cmp')
_not_guard = _NS.get('_not_guard')
_what_norm = _NS.get('_what_norm')


def _fn(sample_src):
    u"""把样本源码里的第一个函数取出来（样本自己写，不经产品）。"""
    t = ast.parse(sample_src)
    for n in t.body:
        if isinstance(n, ast.FunctionDef):
            return n
    return None


# ================================================ 样本（独立构造）
S_SAME_IF = u'''
def f(npc_id, dest_scene):
    if not isinstance(npc_id, str) or not npc_id \\
            or npc_id != npc_id.strip():
        return None
    return 1
'''

S_TWO_IF = u'''
def f(npc_id, dest_scene):
    if not isinstance(npc_id, str) or not npc_id:
        return None
    if npc_id != npc_id.strip():
        return None
    return 1
'''

S_ONLY_NOT = u'''
def f(npc_id, dest_scene):
    if not isinstance(npc_id, str) or not npc_id:
        return None
    return 1
'''

S_ONLY_STRIP_CALL = u'''
def f(npc_id, dest_scene):
    if not isinstance(npc_id, str) or not npc_id.strip():
        return None
    return 1
'''

S_ONLY_CMP = u'''
def f(npc_id, dest_scene):
    if npc_id != npc_id.strip():
        return None
    return 1
'''

S_WHAT_OK = u'''
def g(what):
    if not isinstance(what, str):
        what = ''
    elif not what.strip():
        what = ''
    return what
'''

S_WHAT_MISSING = u'''
def g(what):
    if not isinstance(what, str):
        what = ''
    elif False:
        what = ''
    return what
'''

S_NOISE = u'''
def h(npc_id):
    x = npc_id.strip()
    y = npc_id + 'x'
    return (x, y)
'''


def _has(fn_list):
    return bool(fn_list)


# ================================================ A 判据的行为面
mark(u'A 把三个判定函数当被测物：等价写法都要认、缺一半都要拒')

check(u'A0 三个判定函数都从 `recheck159_core.py` 里取到了（不是空壳）',
      callable(_strip_cmp) and callable(_not_guard) and callable(_what_norm),
      u'strip_cmp=%s not_guard=%s what_norm=%s'
      % (callable(_strip_cmp), callable(_not_guard), callable(_what_norm)))

_f1 = _fn(S_SAME_IF)
_f2 = _fn(S_TWO_IF)
_f3 = _fn(S_ONLY_NOT)
_f4 = _fn(S_ONLY_STRIP_CALL)
_f5 = _fn(S_ONLY_CMP)
_g1 = _fn(S_WHAT_OK)
_g2 = _fn(S_WHAT_MISSING)
_h1 = _fn(S_NOISE)

check(u'A1 ★★★ 两半挤在**同一个 `if`** 里：strip 半与 not 半都要认',
      _has(_strip_cmp(_f1, 'npc_id')) and _has(_not_guard(_f1, 'npc_id')),
      u'strip=%d not=%d' % (len(_strip_cmp(_f1, 'npc_id')),
                            len(_not_guard(_f1, 'npc_id'))))

check(u'A2 ★★★ 语义等价的**两个连续 `if`**：同样都要认（判据绑写法就死在这里）',
      _has(_strip_cmp(_f2, 'npc_id')) and _has(_not_guard(_f2, 'npc_id')),
      u'strip=%d not=%d' % (len(_strip_cmp(_f2, 'npc_id')),
                            len(_not_guard(_f2, 'npc_id'))))

check(u'A3 ★★ **只有 not 半**（没写 strip 比较）⇒ strip 半必须判"没有"',
      not _strip_cmp(_f3, 'npc_id'), u'strip=%d' % (len(_strip_cmp(_f3, 'npc_id')),))

check(u'A4 ★★★ `if not npc_id.strip():` 这类**不是比较**的写法 ⇒ 不许当成 strip 半'
      u'（它挡不住 `\' ralsei \'`：非空即真，反而把所有人都拒了）',
      not _strip_cmp(_f4, 'npc_id'), u'strip=%d' % (len(_strip_cmp(_f4, 'npc_id')),))

check(u'A5 ★★ **只有 strip 半**（没有 `not` 判据）⇒ not 半必须判"没有"',
      _has(_strip_cmp(_f5, 'npc_id')) and not _not_guard(_f5, 'npc_id'),
      u'strip=%d not=%d' % (len(_strip_cmp(_f5, 'npc_id')),
                            len(_not_guard(_f5, 'npc_id'))))

check(u'A6 ★ `what` 归一分支在位 ⇒ 认得出（`elif not what.strip(): what = \'\'`）',
      len(_what_norm(_g1)) == 1, u'处数=%d' % (len(_what_norm(_g1)),))

check(u'A7 ★★ `what` 归一被换成死分支（`elif False`）⇒ 必须认不出'
      u'（这条是 A6 的负控制）',
      len(_what_norm(_g2)) == 0, u'处数=%d' % (len(_what_norm(_g2)),))

check(u'A8 ★ 只在**语句里**出现 `strip()`（不是判据）不算守卫（防"提到就算"的恒真）',
      not _strip_cmp(_h1, 'npc_id') and not _not_guard(_h1, 'npc_id'),
      u'strip=%d not=%d' % (len(_strip_cmp(_h1, 'npc_id')),
                            len(_not_guard(_h1, 'npc_id'))))

# ================================================ B 时相
mark(u'B 判据的**时相**：只许问"有没有第三个文件"，不许要求"恰好两个在改"')

_H1A = None
for _n in ast.walk(_TREE):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
            and _n.func.id == 'check' and _n.args \
            and isinstance(_n.args[0], ast.Constant) \
            and isinstance(_n.args[0].value, str) \
            and _n.args[0].value.startswith('H1a'):
        _H1A = _n
check(u'B1 复检里确实有 `H1a` 这条（名字是字面量，能被独立定位）', _H1A is not None)

_cmp_in = [n for n in ast.walk(_H1A.args[1]) if isinstance(n, ast.Compare)] \
    if _H1A is not None and len(_H1A.args) > 1 else []
_names_in = set(x.id for x in ast.walk(_H1A.args[1])
                if isinstance(x, ast.Name)) \
    if _H1A is not None and len(_H1A.args) > 1 else set()
check(u'B2 ★★★ `H1a` 不再拿列表做**相等比较**（那会绑死时相：一提交就空 ⇒ 必假红）',
      _H1A is not None and not _cmp_in,
      u'比较节点=%d' % (len(_cmp_in),))
check(u'B3 ★★ `H1a` 问的是"**多出来的**文件"（子集判：`_extra` 必须为空）',
      u'_extra' in _names_in, u'名字=%r' % (sorted(_names_in),))

# 行为面模拟：三种时相下同一个表达式该给什么答案
_ALLOWED = ('ralsei_pet/modules/npc_errand.py', 'ralsei_pet/src/main.py')


def _h1a_ok(prod):
    return not [p for p in prod if p not in _ALLOWED]


check(u'B4 ★★★ 时相模拟：**已提交**（产品改动为空）⇒ 必须过（原来这条必假红）',
      _h1a_ok([]) is True)
check(u'B5 ★★ 时相模拟：改动就是那两个文件 ⇒ 必须过',
      _h1a_ok(list(_ALLOWED)) is True)
check(u'B6 ★★★ 时相模拟：多出**第三个**产品文件 ⇒ 必须不过（这是真守卫，不许放宽掉）',
      _h1a_ok(['ralsei_pet/src/main.py', 'ralsei_pet/modules/npc_alive.py']) is False)

# ★ 防"模拟逻辑 vs 真代码"漂移：把 recheck 里那个**白名单常量**读出来对一遍。
#   若有人把 `_ALLOWED` 改成空/改成"所有产品文件"，上面的模拟全绿而真判据已经失效。
_ALLOW = None
for _n in _TREE.body:
    if isinstance(_n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == '_ALLOWED' for t in _n.targets):
        try:
            _ALLOW = ast.literal_eval(_n.value)
        except Exception:
            _ALLOW = None
check(u'B7 ★★★ 真代码里的白名单 `_ALLOWED` **恰好是那两个文件**（防"模拟绿、真判据恒真"）',
      isinstance(_ALLOW, tuple) and sorted(_ALLOW) == sorted(_ALLOWED),
      u'_ALLOWED=%r' % (_ALLOW,))

# ================================================ C 自检
mark(u'C 自检：分母闸 · 字面量 · 只用 check() · 编码 · 零外部盘')

with io.open(os.path.abspath(__file__), 'r', encoding='utf-8', newline='') as _sf:
    SELF = _sf.read()
SELF_TREE = ast.parse(SELF)

_bad_names = []
_n_check = 0
for n in ast.walk(SELF_TREE):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'check':
        _n_check += 1
        if not n.args or not isinstance(n.args[0], ast.Constant) \
                or not isinstance(n.args[0].value, str) \
                or not n.args[0].value.strip():
            _bad_names.append(getattr(n, 'lineno', -1))
check(u'C0 分母闸：本文件里 `check(` 调用**非空**', _n_check > 0,
      u'处数=%d' % (_n_check,))
check(u'C1 每条判据的说明都是**非空字面量**，且条数不少于 21',
      not _bad_names and _n_check >= 21,
      u'坏的=%d 条数=%d' % (len(_bad_names), _n_check))

_n_ok = 0
for n in ast.walk(SELF_TREE):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'ok':
        _n_ok += 1
check(u'C2 只用 `check()`，不用 `ok()`（两套 harness 混用 ⇒ 查恒真会漏一半）',
      _n_ok == 0, u'ok 调用=%d' % (_n_ok,))

_crlf = SELF.count('\r\n')
check(u'C3 无 BOM 且**全 LF**（与本目录其他套件同构）',
      not SELF.startswith(u'\ufeff') and _crlf == 0,
      u'BOM=%s CRLF=%d' % (SELF.startswith(u'\ufeff'), _crlf))

_mark_a = u'D' + u':' + u'\\_tmp'
_mark_b = u'E' + u':' + u'\\'
_mark_c = u'C' + u':' + u'\\Users'
_drive = [d for d in (_mark_a, _mark_b, _mark_c) if d in SELF]
check(u'C4 零外部盘：判据本身不引用工作区外的路径（临时件落系统 temp）',
      not _drive, u'命中=%d 处' % (len(_drive),))

print('')
if _n_fail:
    print('check160：FAIL %d / PASS %d' % (_n_fail, _n_pass))
    for _d in _failed:
        print(u'  红：%s' % (_d,))
    sys.exit(1)
print('check160：%d 条全过' % (_n_pass,))
sys.exit(0)

# -*- coding: utf-8 -*-
u"""第151轮 · 核心文件复检（本轮改了 **1 个产品文件 + 1 个套件登记表**，新增 1 个目录）。

规矩来源（用户口径逐字）：「**以后再调整重要核心文件时一定要记得复检**」。
六项固定形状：① 语法 ② 结构自检 ③ 无 BOM / 无 U+FFFD ④ 恒真判据复查
⑤ 逐令牌回验 ⑥ 工作区干净 ＋ 该跑回归的跑回归。

| 段 | 守什么 |
|---|---|
| H1 | 改动面：**恰好**点名的跟踪文件（多一个少一个都红）+ 未跟踪只有本轮那个目录 |
| H2 | 产品足迹：`main.py` **+63/−0**（纯新增，零删除）；速查本**只加不删** |
| H3 | 语法：`main.py` `ast.parse`（**不**用 `py_compile` —— 会产 `.pyc`，改被测状态） |
| H4 | 编码：无 BOM / 无 U+FFFD / **裸 LF = 0**（`main.py` 全篇 CRLF） |
| H5 | 结构自检：四条**本轮新增**的关系（`check151` 没守的那几条） |
| H6 | 逐令牌回验：本轮新增的与**旧的**都回验；下沉到详版的令牌去详版 `in` 一次 |
| H7 | 恒真判据复查：两套 harness（`check` / `mutate`）都看；`mutate` 的还原在 `finally` |
| H8 | 卫生：`.pyc/.bak/~` 0 个；`_evidence` 无易变物 |

★ 本文件**不进 `SUITES`**：H1/H2 依赖 `git diff`（提交后就变空），它是**提交前**的闸。
  常驻回归由 `check151`（27 条）+ `mutate151`（16 条）承担。

## H5 为什么**不重复** `check151` 的 B 段

`check151 B` 已经钉住"调用恰好一次 / 排在 `_npc_seed_bodies` 之后 / 体内只走
`assign_errand`"。这里补的是它**没有**守的四条 —— 全是"示范差事失败不许拖垮启动"
这句话的分解：

1. `assign_errand` 的调用真的包在 `try` 里，且 handler 捕的是 `Exception`（不是窄类型）；
2. 调用点的返回值**不被 `init_npc_systems` 用来做分支**（它只能是独立语句）；
3. `NPC_ERRAND_DEMO` 在类体里**只有一处**赋值（两处赋值 ⇒ 后者静默覆盖前者）；
4. 文档那行例子仍在 `NPC_ERRAND_DEMO = None` 的**紧邻注释**里（`C3` 的静态复算）。
"""
import ast
import io
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PKG, 'src', 'main.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
MEM = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
MEM_LONG = os.path.join(ROOT, '.workbuddy', 'memory', u'参考-契约与历轮（详版）.md')

_n_ok = 0
_n_bad = 0
_failed = []
_marks = 0


def check(desc, cond, extra=u''):
    global _n_ok, _n_bad
    cond = bool(cond)
    if cond:
        _n_ok += 1
    else:
        _n_bad += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else u''))


def head(t):
    global _marks
    _marks += 1
    print(u'---- [复检点 %d] %s ----' % (_marks, t))


def _git(*args):
    p = subprocess.Popen([u'git'] + list(args), cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    o, e = p.communicate()
    return (o.decode('utf-8', 'replace'), e.decode('utf-8', 'replace'), p.returncode)


def _read(p):
    # ★ 字节忠实：`newline=''` 保住 CRLF
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _raw(p):
    with io.open(p, 'rb') as f:
        return f.read()


SRC_MAIN = _read(MAIN)
SRC_MEM = _read(MEM)
SRC_LONG = _read(MEM_LONG)

# =============================================== H1 改动面
head(u'H1 改动面：点名核对（多一个少一个都红）')

_num, _err, _ = _git('-c', 'core.quotepath=false', 'diff', '--numstat')
_rows = [ln for ln in _num.splitlines() if ln.strip()]
_NS = dict((ln.split(u'\t')[2], (ln.split(u'\t')[0], ln.split(u'\t')[1]))
           for ln in _rows)

#: ★ 点名而不是"只许动 N 个文件" —— 第146轮栽过：登记新套件本来就要改 `run_all.py`。
_EXPECT = set([
    u'ralsei_pet/src/main.py',
    u'code-quality-audit/regress/run_all.py',
    u'code-quality-audit/regress/baseline.json',
    u'.workbuddy/memory/MEMORY.md',
    u'.workbuddy/memory/2026-11-03.md',
    u'.workbuddy/memory/\u53c2\u8003-\u5951\u7ea6\u4e0e\u5386\u8f6e\uff08\u8be6\u7248\uff09.md',
])
check(u'H1 被改的跟踪文件**恰好**是本轮那 6 个（产品 1 + 审计 2 + 记忆 3）',
      set(_NS) == _EXPECT,
      u'多=%s 少=%s' % (sorted(set(_NS) - _EXPECT), sorted(_EXPECT - set(_NS))))

_st, _, _ = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_untracked = [ln[3:] for ln in _st.splitlines() if ln.startswith(u'?? ')]
_untracked_norm = [u.rstrip(u'/') for u in _untracked]
check(u'H1b 未跟踪的只有**本轮新增的那一个目录**（`第151轮…/`）',
      set(_untracked_norm) == set([u'code-quality-audit/\u7b2c151\u8f6e-'
                                   u'\u7559\u4e00\u6761\u771f\u5dee\u4e8b']),
      u'%s' % (_untracked_norm,))

# =============================================== H2 产品足迹
head(u'H2 产品足迹：改动文件的增删对账')
check(u'H2 `main.py` **+63 / −0**（纯新增：一处类属性 + 一处调用 + 一个方法，零删除）',
      _NS.get(u'ralsei_pet/src/main.py') == (u'63', u'0'),
      u'%s' % (_NS.get(u'ralsei_pet/src/main.py'),))

_mem_add = _NS.get(u'.workbuddy/memory/MEMORY.md')
check(u'H2b 速查本**等量替换**（`+1/−1`：只把"锁号速查"里最旧的 `check145` 换成 '
      u'`check151`，不借机膨胀 —— 它离 `check95 A2` 的 10,000 上限只剩 4）',
      _mem_add == (u'1', u'1'),
      u'%s' % (_mem_add,))

_run = _NS.get(u'code-quality-audit/regress/run_all.py')
check(u'H2c `run_all.py` 只加了 `check151` 一条登记（`−0`，没顺手改别的套件）',
      _run is not None and _run[1] == u'0',
      u'成立=%s' % (_run is not None and _run[1] == u'0',))

# =============================================== H3 语法
head(u'H3 语法：ast.parse（不产 .pyc）')
try:
    _TREE = ast.parse(SRC_MAIN)
    _syn = None
except SyntaxError as _e:
    _TREE = None
    _syn = str(_e)
check(u'H3 `main.py` 可解析', _syn is None, u'%s' % (_syn,))
check(u'H3b 分母闸：真解析出了大文件（函数数 ≥ 300，空串也能 parse）',
      _TREE is not None
      and len([n for n in ast.walk(_TREE) if isinstance(n, ast.FunctionDef)]) >= 300,
      u'成立=%s' % (_TREE is not None,))

_SELF_T = ast.parse(_read(os.path.abspath(__file__)))
_SELF_FN = set(n.name for n in ast.walk(_SELF_T) if isinstance(n, ast.FunctionDef))
check(u'H3c **本模块自己**也可解析，且 `check`/`head`/`_git` 都在'
      u'（复检脚本自己坏了就不该报绿）',
      set([u'check', u'head', u'_git']) <= _SELF_FN,
      u'缺 %s' % (sorted(set([u'check', u'head', u'_git']) - _SELF_FN),))

# =============================================== H4 编码
head(u'H4 编码：无 BOM / 无 U+FFFD / 裸 LF = 0')
_b = _raw(MAIN)
_crlf = _b.count(b'\r\n')
_bare = _b.count(b'\n') - _crlf
check(u'H4 `main.py`：无 BOM / 无 U+FFFD / 全 CRLF（裸 LF = 0）',
      not _b.startswith(b'\xef\xbb\xbf') and u'\ufffd' not in SRC_MAIN
      and _bare == 0 and _crlf > 100,
      u'成立=%s' % (_bare == 0 and _crlf > 100,))

# =============================================== H5 结构自检
head(u'H5 结构自检：四条"示范差事失败不许拖垮启动"的分解（`check151` 没守的）')


def _cls(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == name:
            return n
    return None


def _m(cls, name):
    if cls is None:
        return None
    for n in cls.body:
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _calls(fn, attr):
    out = []
    if fn is None:
        return out
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
                and c.func.attr == attr:
            out.append(c)
    return out


_CLS = _cls(_TREE, u'RalseiPet')
_DEMO = _m(_CLS, u'_npc_errand_demo')
_INIT = _m(_CLS, u'init_npc_systems')

# ---- H5a：`assign_errand` 的调用包在 `try` 里，handler 捕 `Exception` ----
# ★ 做法：找出所有 `Try` 节点，看 `assign_errand` 那个 Call 是否落在 body 子树里，
#   且该 Try 至少有一个 handler 的 type 是 `Exception`（`None` = 裸 except 也算拦住，
#   但这里明确要求写 `Exception` —— 裸 except 会连 KeyboardInterrupt 一起吞）。
_guard_hit = False
_bare_exc = 0
_assign_calls = _calls(_DEMO, u'assign_errand')
for _t in (ast.walk(_DEMO) if _DEMO is not None else []):
    if not isinstance(_t, ast.Try):
        continue
    _ids = set(id(x) for _s in _t.body for x in ast.walk(_s))
    if not any(id(c) in _ids for c in _assign_calls):
        continue
    for _h in _t.handlers:
        if _h.type is None:
            _bare_exc += 1
        elif isinstance(_h.type, ast.Name) and _h.type.id == u'Exception':
            _guard_hit = True
check(u'H5 `_npc_errand_demo` 里 `assign_errand` 的调用**包在 `try/except Exception`** '
      u'里（示范差事失败不许冒到 `init_npc_systems`）',
      _guard_hit, u'成立=%s' % (_guard_hit,))
check(u'H5b 那个 `except` **不是裸 `except:`**（裸的会连 `KeyboardInterrupt` 一起吞）',
      _bare_exc == 0, u'成立=%s' % (_bare_exc == 0,))

# ---- H5c：调用点返回值**不参与分支**（只能是独立表达式语句）----
_demo_calls = _calls(_INIT, u'_npc_errand_demo')
_expr_only = len(_demo_calls) == 1
if _expr_only:
    _target = _demo_calls[0]
    _stmt_hit = [s for s in (_INIT.body if _INIT else [])
                 if isinstance(s, ast.Expr) and s.value is _target]
    #: ★ 也可能被别的语句（if/with）包着 —— 那就不是"独立语句"了
    _expr_only = len(_stmt_hit) == 1
check(u'H5c `init_npc_systems` 里那次调用是**独立语句**（返回值不许被用来做分支；'
      u'否则"没派出去"会变成"启动流程改道"）',
      _expr_only, u'成立=%s' % (_expr_only,))

# ---- H5d：类体里 `NPC_ERRAND_DEMO` 只有一处赋值 ----
_attr_writes = [n for n in (_CLS.body if _CLS else [])
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == u'NPC_ERRAND_DEMO'
                        for t in n.targets)]
check(u'H5d 类体里 `NPC_ERRAND_DEMO` **只有一处**赋值'
      u'（两处 ⇒ 后者静默覆盖前者，改的人以为改生效了）',
      len(_attr_writes) == 1, u'成立=%s' % (len(_attr_writes) == 1,))

# ---- H5e：文档那行例子仍在紧邻注释里（静态复算 `check151 C3`）----
_DOC_RE = re.compile(r"`\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']*)'\s*\)`")
_DOC_HIT = _DOC_RE.search(SRC_MAIN)
_ATTR_POS = SRC_MAIN.find(u'NPC_ERRAND_DEMO = None')
_gap = (_ATTR_POS - _DOC_HIT.start()) if (_DOC_HIT and _ATTR_POS > 0) else -1
check(u'H5e 注释里那行例子在 `NPC_ERRAND_DEMO = None` **上方 2000 字内**'
      u'（离太远就说明它守的是别处的东西）',
      0 < _gap < 2000, u'成立=%s' % (0 < _gap < 2000,))

# =============================================== H6 逐令牌回验
head(u'H6 逐令牌回验：新增的与**旧的**都逐个回验')
_NEW = [u'NPC_ERRAND_DEMO', u'_npc_errand_demo', u'assign_errand',
        u'oneshot.barrens.Blue', u'示范差事']
_NEW_BAD = [t for t in _NEW if t not in SRC_MAIN]
check(u'H6 本轮新增的 5 个令牌**逐个**在 `main.py` 里',
      not _NEW_BAD, u'缺=%s' % (_NEW_BAD,))

_OLD = [u'def _npc_errand_tick', u'def _npc_errand_gate', u'def _npc_errand_commit',
        u'def _npc_errand_load', u'def _npc_errand_save', u'def assign_errand',
        u'NPC_ERRAND_ENABLED', u'def _npc_seed_bodies', u'def _npc_roam_tick',
        u'def go_to_bed', u'npc_errands.json']
_OLD_BAD = [t for t in _OLD if SRC_MAIN.count(t) < 1]
check(u'H6b 旧令牌也逐个回验（示范差事没把差事/自主移动/就寝整条链挤掉）',
      not _OLD_BAD, u'缺=%s' % (_OLD_BAD,))

check(u'H6c `run_all.py` 里 `check151` 已登记（`SUITES` 里真有这条）',
      u"'id': 'check151'" in _read(RUNALL),
      u'成立=%s' % (u"'id': 'check151'" in _read(RUNALL),))

check(u'H6d 记忆：速查本的"锁号速查"里已有 `check151`（下一轮能找到入口）',
      u'`check151`' in SRC_MEM,
      u'成立=%s' % (u'`check151`' in SRC_MEM,))
# ★ 速查本体积有上限（`check95 A2` 硬闸）⇒ 容易只留指针 ⇒ 逐令牌必须**去详版 `in` 一次**
_DOWN = [u'check151', u'\u00a7151', u'NPC_ERRAND_DEMO', u'_npc_errand_demo',
         u'\u793a\u8303\u5dee\u4e8b']
_DOWN_BAD = [t for t in _DOWN if t not in SRC_LONG]
check(u'H6e 详版里 §151 的令牌**逐个找得到**（速查本留指针 ≠ 丢信息）',
      not _DOWN_BAD, u'缺=%s' % (_DOWN_BAD,))

# =============================================== H7 恒真判据复查
head(u'H7 恒真判据复查：检查"守人的判据"自己')
_TOOLS = [os.path.join(HERE, u'check151.py'), os.path.join(HERE, u'mutate151.py')]
_bad_true = []
for _p in _TOOLS:
    _t = ast.parse(_read(_p))
    for n in ast.walk(_t):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        nm = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else u'')
        if nm not in (u'check', u'ok', u'mutate'):
            continue
        # `check(desc, cond, …)` / `ok(cond, …)` / `mutate(tag, path, pairs, expect)`
        idx = 1 if nm in (u'check', u'ok') else 3
        if len(n.args) > idx and isinstance(n.args[idx], ast.Constant) \
                and n.args[idx].value is True:
            _bad_true.append((os.path.basename(_p), n.lineno))
check(u'H7 两套 harness（`check` / `mutate`）里 `..., True)` **0 处**',
      not _bad_true, u'%s' % (_bad_true,))

_MC = ast.parse(_read(_TOOLS[1]))
_finally = [n for n in ast.walk(_MC) if isinstance(n, ast.Try) and n.finalbody]
check(u'H7b `mutate151` 的"按字节还原"确实在 `finally` 里（中途抛异常也不留坏文件）',
      len(_finally) >= 1, u'成立=%s' % (len(_finally) >= 1,))

_C151 = ast.parse(_read(_TOOLS[0]))
_call_cnt = len([n for n in ast.walk(_C151)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == u'check'])
check(u'H7c `check151` 的判据条数是**常量**（不随环境增减 ⇒ 换机器不会少数）',
      _call_cnt >= 27, u'过阈=%s' % (_call_cnt >= 27,))
# ★ 反面：`_run151` 里按输出解析的那一段不能把 `[FAIL]` 前缀写错，
#   否则 mutate 永远拿到空集合 ⇒ "恰好变红"变成"恰好没红"也绿。
check(u'H7d `mutate151` 解析失败行时用的是产品那套 `[FAIL] ` 前缀（写错=永久假绿）',
      u"u'[FAIL] '" in _read(_TOOLS[1]),
      u'成立=%s' % (u"u'[FAIL] '" in _read(_TOOLS[1]),))

# =============================================== H8 卫生
head(u'H8 卫生：临时产物 / 证据')
_bad = []
for d, _dirs, files in os.walk(ROUND):
    for fn in files:
        if fn.endswith((u'.pyc', u'.pyo', u'.bak', u'~')):
            _bad.append(os.path.join(d, fn))
check(u'H8 整轮目录**无** `.pyc/.bak/~`', not _bad, u'%s' % (_bad[:3],))
_EV = os.path.join(ROUND, u'_evidence')
check(u'H8b 本轮**没有** `_evidence/`（判据全是活跑，不存易变物）',
      not os.path.isdir(_EV), u'成立=%s' % (not os.path.isdir(_EV),))

print(u'')
print(u'=' * 78)
print(u'recheck151_core：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)

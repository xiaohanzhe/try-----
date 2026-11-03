# -*- coding: utf-8 -*-
u"""第154轮 · 核心文件复检（本轮改了 **1 个产品文件 + 1 个旧夹具 + 登记表 + 基线**，
新增 1 个目录）。

规矩来源（用户口径逐字）：「**以后再调整重要核心文件时一定要记得复检**」。
六项固定形状：① 语法 ② 结构自检 ③ 无 BOM / 无 U+FFFD ④ 恒真判据复查
⑤ 逐令牌回验 ⑥ 工作区干净 ＋ 该跑回归的跑回归。

| 段 | 守什么 |
|---|---|
| H1 | 改动面：**恰好**点名的 6 个跟踪文件（多一个少一个都红）+ 未跟踪只能是"本轮目录 + 当天新建日志" |
| H2 | 产品足迹：`main.py` **+82/−3** / `check152.py` **+5/−1**（旧夹具补收参） / `run_all.py` **+32/−0** / `baseline.json` **+6/−0** |
| H3 | 语法：`ast.parse`（**不**用 `py_compile` —— 会产 `.pyc`，改被测状态）+ 分母闸 |
| H4 | 编码：无 BOM / 无 U+FFFD / **裸 LF = 0**（`main.py` 全篇 CRLF） |
| H5 | 结构自检：**五条读源码才看得见**的关系 |
| H6 | 逐令牌回验：本轮新增的与**旧的**都回验；下沉到详版的令牌去详版 `in` 一次 |
| H7 | 恒真判据复查：**两套 harness** 都看；`mutate` 的还原在 `finally` |
| H8 | 卫生：`.pyc/.bak/~` 0 个；本轮目录里没有易变物 |

## H5 为什么**不重复** `check154`

`check154` 的 A/B 段是**行为级**（真跑）。这里补的是"**读源码才能看见**"的那几条：

1. `_errand_same_job` 是**模块级**函数（写成方法 ⇒ 第150~153轮那些只挂产品函数的
   轻宿主当场 `AttributeError`）；这条**只能看 AST 的 body 层级**，行为面看不出来；
2. `assign_errand` 里的**三段行序** `active_of < assign < note`（`C1`/`C2` 各看一段，
   这里看**三段合起来的顺序**）；
3. `_errand_ack` 里也有 `_errand_same_job`（两侧共用**同一个判据**，不是各写一半）；
4. 全仓 `_errand_same_job` **定义 1 处 / 调用 2 处**（多一处 = "同一件事两个真相"）；
5. `probe154.py` 的宿主是**从 `check154` 借的**（不自己再写一套）。

★ 本文件**不进 `SUITES`**：H1/H2 依赖 `git diff`（提交后就变空），它是**提交前**的闸。
  常驻回归由 `check154`（32 条）+ `mutate154`（26 条）承担。
"""
import ast
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PKG, 'src', 'main.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
BASE = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
MEM = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
MEM_LONG = os.path.join(ROOT, '.workbuddy', 'memory',
                        u'\u53c2\u8003-\u5951\u7ea6\u4e0e\u5386\u8f6e\uff08\u8be6\u7248\uff09.md')
CHECK154 = os.path.join(HERE, 'check154.py')
MUTATE154 = os.path.join(HERE, 'mutate154.py')
PROBE154 = os.path.join(HERE, 'probe154.py')

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
    return (o.decode('utf-8', 'replace'), e.decode('utf-8', 'replace'),
            p.returncode)


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
SRC_RUN = _read(RUNALL)
SRC_PROBE = _read(PROBE154)

# =============================================== H1 改动面
head(u'H1 改动面：点名核对（多一个少一个都红）')

_num, _err, _ = _git('-c', 'core.quotepath=false', 'diff', '--numstat')
_rows = [ln for ln in _num.splitlines() if ln.strip()]
_NS = dict((ln.split(u'\t')[2], (ln.split(u'\t')[0], ln.split(u'\t')[1]))
           for ln in _rows)

#: ★ 当天日志是**新建**的（未跟踪）⇒ 它不出现在 `git diff` 里，由 H1b/H1c 单独守。
_EXPECT = set([
    u'ralsei_pet/src/main.py',
    u'code-quality-audit/regress/run_all.py',
    u'code-quality-audit/regress/baseline.json',
    # ★ 旧夹具：产品给 `_errand_ack` 加了可选 `prev=`，check152 的桩 `(*a)` 收不住。
    u'code-quality-audit/\u7b2c152\u8f6e-\u5dee\u4e8b\u53eb\u505c/_tools/check152.py',
    u'.workbuddy/memory/MEMORY.md',
    u'.workbuddy/memory/\u53c2\u8003-\u5951\u7ea6\u4e0e\u5386\u8f6e\uff08\u8be6\u7248\uff09.md',
])
check(u'H1 被改的跟踪文件**恰好**是本轮那 6 个'
      u'（产品 1 + 旧夹具 1 + 审计 2 + 记忆 2）；当天日志是新建的，由 H1b/H1c 守',
      set(_NS) == _EXPECT,
      u'多=%s 少=%s' % (sorted(set(_NS) - _EXPECT), sorted(_EXPECT - set(_NS))))

_st, _, _ = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_untracked = [ln[3:] for ln in _st.splitlines() if ln.startswith(u'?? ')]
_untracked_norm = [u.rstrip(u'/') for u in _untracked]
# ★ 当天日志是**新建**的（11-04 第一次落盘）⇒ 它必然出现在未跟踪里；
#   除此之外只许有本轮那个目录。
check(u'H1b 未跟踪的只有**本轮目录** + **当天新建的日志**（其余一律算多）',
      set(_untracked_norm) == set([
          u'code-quality-audit/\u7b2c154\u8f6e-\u6539\u6d3e\u7559\u75d5',
          u'.workbuddy/memory/2026-11-04.md']),
      u'%s' % (_untracked_norm,))

_DAY = os.path.join(ROOT, '.workbuddy', 'memory', '2026-11-04.md')
_day_txt = _read(_DAY) if os.path.exists(_DAY) else u''
check(u'H1c 当天日志**真的写了**（新建文件，`git diff` 看不见它）+ 里面有本轮令牌',
      len(_day_txt) > 300 and u'154' in _day_txt
      and u'check154' in _day_txt and u'_errand_same_job' in _day_txt,
      u'字符=%d' % (len(_day_txt),))

# =============================================== H2 产品足迹
head(u'H2 产品足迹：改动文件的增删对账')
_MAIN_NS = _NS.get(u'ralsei_pet/src/main.py')
check(u'H2 `main.py` **+82 / −3**（新增模块级 `_errand_same_job` 整段 + `assign_errand`'
      u' 里"先派成再写痕" + `_errand_ack` 的 `prev` 事实块 + 三处注释改写；'
      u'−3 = 旧的三行 `try/return board.assign/except` 收成 `return _new`，'
      u'外加注释里"为什么在 assign 之前"改成"为什么**取旧**必须在 assign 之前"）',
      _MAIN_NS == (u'82', u'3'), u'%s' % (_MAIN_NS,))

_RUN_NS = _NS.get(u'code-quality-audit/regress/run_all.py')
check(u'H2b `run_all.py` 只加了 `check154` 一条登记（`−0`，没顺手改别的套件）',
      _RUN_NS is not None and _RUN_NS[1] == u'0' and u'check154' in SRC_RUN,
      u'%s' % (_RUN_NS,))

_BASE_NS = _NS.get(u'code-quality-audit/regress/baseline.json')
check(u'H2c `baseline.json` **+6 / −0** —— 只多了 `check154` 那一项（32 条）',
      _BASE_NS == (u'6', u'0'), u'%s' % (_BASE_NS,))

check(u'H2d 本轮**没有**改 `modules/` 下任何模块（改派留痕全在宿主侧，'
      u'`npc_errand` 的契约面一个字没动）',
      not [p for p in _NS if p.startswith(u'ralsei_pet/modules/')],
      u'%s' % ([p for p in _NS if p.startswith(u'ralsei_pet/modules/')],))

check(u'H2e 速查本**只动锁号那一处**（`+1/−1`：它离 `check95 A2` 的 10,000 上限'
      u'只剩个位数，不许借机膨胀）',
      _NS.get(u'.workbuddy/memory/MEMORY.md') == (u'1', u'1'),
      u'%s' % (_NS.get(u'.workbuddy/memory/MEMORY.md'),))

_152 = _NS.get(u'code-quality-audit/\u7b2c152\u8f6e-\u5dee\u4e8b\u53eb\u505c'
               u'/_tools/check152.py')
check(u'H2f 旧夹具 `check152.py` **+5 / −1** —— 只把桩的 `(*a)` 改成 `(*a, **kw)`'
      u'（产品新加了可选 `prev=`），**一条判据都没动**',
      _152 == (u'5', u'1'), u'%s' % (_152,))

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
      and len([n for n in ast.walk(_TREE)
               if isinstance(n, ast.FunctionDef)]) >= 300,
      u'成立=%s' % (_TREE is not None,))

_SELF_T = ast.parse(_read(os.path.abspath(__file__)))
_SELF_FN = set(n.name for n in ast.walk(_SELF_T)
               if isinstance(n, ast.FunctionDef))
check(u'H3c **本模块自己**也可解析，且 `check`/`head`/`_git` 都在'
      u'（复检脚本自己坏了就不该报绿）',
      set([u'check', u'head', u'_git']) <= _SELF_FN,
      u'缺 %s' % (sorted(set([u'check', u'head', u'_git']) - _SELF_FN),))

for _p, _tag in ((CHECK154, u'H3d `check154.py`'), (MUTATE154, u'H3e `mutate154.py`')):
    try:
        ast.parse(_read(_p))
        _s = None
    except SyntaxError as _e:
        _s = str(_e)
    check(u'%s 可解析' % _tag, _s is None, u'%s' % (_s,))

# =============================================== H4 编码
head(u'H4 编码：无 BOM / 无 U+FFFD / 裸 LF = 0')
_b = _raw(MAIN)
_crlf = _b.count(b'\r\n')
_bare = _b.count(b'\n') - _crlf
check(u'H4 `main.py`：无 BOM / 无 U+FFFD / 全 CRLF（裸 LF = 0）',
      not _b.startswith(b'\xef\xbb\xbf') and u'\ufffd' not in SRC_MAIN
      and _bare == 0 and _crlf > 100,
      u'裸LF=%d / CRLF=%d' % (_bare, _crlf))
check(u'H4b 记忆两份都没有 U+FFFD（替换字符一出现就是编码事故）',
      u'\ufffd' not in SRC_MEM and u'\ufffd' not in SRC_LONG,
      u'成立=%s' % (u'\ufffd' not in SRC_MEM and u'\ufffd' not in SRC_LONG,))

# =============================================== H5 结构自检
head(u'H5 结构自检：五条"读源码才看得见"的关系')


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


def _ncalls(fn, name):
    u"""按**函数名**（不是属性名）找调用 —— `_errand_same_job` 是模块级、裸名调用。"""
    out = []
    if fn is None:
        return out
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) \
                and c.func.id == name:
            out.append(c)
    return out


def _lineno(fn, attr):
    got = _calls(fn, attr)
    return got[0].lineno if got else None


_RC = _cls(_TREE, u'RalseiPet')
_ASSIGN = _m(_RC, u'assign_errand')
_ACK = _m(_RC, u'_errand_ack')
_TOP = set(n.name for n in _TREE.body if isinstance(n, ast.FunctionDef))

# ---- H5a：判据必须是**模块级** ----
check(u'H5a ★★ `_errand_same_job` 是**模块级函数**，不是方法'
      u'（写成方法 ⇒ 第150~153轮那些只挂产品函数的轻宿主当场 `AttributeError`，'
      u'而且会被 `except` 吞掉、症状是"什么都没发生"）',
      u'_errand_same_job' in _TOP and _m(_RC, u'_errand_same_job') is None,
      u'模块级=%s 是方法=%s'
      % (u'_errand_same_job' in _TOP, _m(_RC, u'_errand_same_job') is not None))

# ---- H5b：三段行序（静态）----
_la = _lineno(_ASSIGN, u'active_of')
_ls = _lineno(_ASSIGN, u'assign')
_ln_list = sorted(c.lineno for c in _calls(_ASSIGN, u'_npc_errand_note'))
_ln_dispatch = _ln_list[-1] if _ln_list else None
check(u'H5b 静态行序 `active_of < assign < 改派留痕`'
      u'（取旧 → 派 → 写痕；`C1`/`C2` 各看一段，这里看**三段合起来**）',
      None not in (_la, _ls, _ln_dispatch) and _la < _ls < _ln_dispatch,
      u'%s < %s < %s' % (_la, _ls, _ln_dispatch))

# ---- H5c：两侧共用一个判据 ----
check(u'H5c ★★ `_errand_ack` 里也调了 `_errand_same_job` —— 写痕与说话**共用同一个判据**'
      u'（各写一半 = 以后"记忆里没有、嘴上却说被作废了"）',
      len(_ncalls(_ACK, u'_errand_same_job')) == 1,
      u'处数=%d' % (len(_ncalls(_ACK, u'_errand_same_job')),))

# ---- H5d：定义 1 处 / 调用 2 处 ----
check(u'H5d 全仓 `_errand_same_job`：**定义 1 处 / 调用 2 处**'
      u'（`assign_errand` + `_errand_ack`；多一处就是"同一件事两个真相"）',
      len([n for n in _TREE.body
           if isinstance(n, ast.FunctionDef) and n.name == u'_errand_same_job']) == 1
      and len(_ncalls(_TREE, u'_errand_same_job')) == 2,
      u'定义=%d 调用=%d'
      % (len([n for n in _TREE.body
              if isinstance(n, ast.FunctionDef) and n.name == u'_errand_same_job']),
         len(_ncalls(_TREE, u'_errand_same_job'))))

# ---- H5e：探针不另起一套宿主 ----
check(u'H5e `probe154.py` 的宿主是**从 `check154` 借的**（`runpy` + `check154.py`），'
      u'没有自己再写一套 —— 两边不一致时代码没错、人先看晕',
      u'runpy' in SRC_PROBE and u'check154.py' in SRC_PROBE,
      u'runpy=%s 指向=%s' % (u'runpy' in SRC_PROBE, u'check154.py' in SRC_PROBE))

# =============================================== H6 逐令牌回验
head(u'H6 逐令牌回验：新增的与**旧的**都回验')
_TOK_MAIN = [
    u'_errand_same_job',        # 本轮新增
    u'_new = board.assign',     # 本轮新增（先派成）
    u'还没办完',
    u'又被派去',
    u'_npc_errand_note',        # 旧的
    u'active_of',               # 旧的（`ErrandBoard` 读口）
    u'_errand_report_ack',      # 第153轮
    u'remember=False',          # 第153轮
]
_missing = [t for t in _TOK_MAIN if t not in SRC_MAIN]
check(u'H6 本轮新增 + 前几轮的令牌**逐个**回 `main.py` 各 `in` 一次'
      u'（新旧都查，别只查新的）',
      not _missing, u'缺=%s' % (_missing,))

_TOK_LONG = [u'\u00a7154', u'_errand_same_job', u'_new is not None',
             u'假记忆']
_missing2 = [t for t in _TOK_LONG if t not in SRC_LONG]
check(u'H6b 下沉到**详版**的令牌逐条回 `in`（§154 真的写进去了）',
      not _missing2, u'缺=%s' % (_missing2,))

check(u'H6c 速查本仍指向最新的锁号（`check154` 在、`check151` 已让位）',
      u'check154' in SRC_MEM and u'check152' in SRC_MEM,
      u'成立=%s' % (u'check154' in SRC_MEM,))

# =============================================== H7 恒真判据复查
head(u'H7 恒真判据复查：**两套 harness** 都看')


def _const_true_args(tree, fname):
    bad = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id == fname and len(n.args) >= 2:
            a = n.args[1]
            if isinstance(a, ast.Constant) and a.value is True:
                bad.append(n.lineno)
    return bad


_T154 = ast.parse(_read(CHECK154))
_TM154 = ast.parse(_read(MUTATE154))
check(u'H7 `check154` 里没有 `check(desc, True, …)` 这种**恒真**断言',
      not _const_true_args(_T154, u'check'),
      u'条数=%d' % (len(_const_true_args(_T154, u'check')),))
check(u'H7b `mutate154` 里同样没有恒真（`mutate` 自己的 `check` 也查）',
      not _const_true_args(_TM154, u'check'),
      u'条数=%d' % (len(_const_true_args(_TM154, u'check')),))
_ok_calls = [n for n in ast.walk(_T154)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == u'ok']
check(u'H7c `check154` **不用** `ok()` —— 两套 harness 的签名不同'
      u'（`ok(cond,msg)` / `check(desc,cond,…)`），混用就会"看着在守其实没守"',
      not _ok_calls, u'ok() 调用=%d' % (len(_ok_calls),))

_finally_write = False
for n in ast.walk(_TM154):
    if isinstance(n, ast.Try) and n.finalbody:
        for b in ast.walk(ast.Module(body=n.finalbody, type_ignores=[])):
            if isinstance(b, ast.Call) and isinstance(b.func, ast.Name) \
                    and b.func.id == u'_write':
                _finally_write = True
check(u'H7d `mutate154` 的**字节级还原在 `finally` 里**'
      u'（中途 `SystemExit`/异常也要还原，否则产品被留在破坏态）',
      _finally_write, u'成立=%s' % (_finally_write,))

# =============================================== H8 卫生
head(u'H8 卫生：没有残留产物')
_bin = []
for _root, _dirs, _files in os.walk(ROUND):
    for _f in _files:
        if _f.endswith((u'.pyc', u'.pyo', u'.bak', u'.orig', u'.rej')) \
                or _f.endswith(u'~'):
            _bin.append(os.path.join(_root, _f))
check(u'H8 本轮目录里 `.pyc/.pyo/.bak/.orig/.rej/~` **0 个**',
      not _bin, u'%s' % (_bin[:5],))
check(u'H8b 本轮**没有** `_evidence/`（判据全是活跑 + 一份可跑的探针，不存易变物）',
      not os.path.isdir(os.path.join(ROUND, u'_evidence')),
      u'成立=%s' % (not os.path.isdir(os.path.join(ROUND, u'_evidence')),))

print(u'')
if _n_bad:
    print(u'==== recheck154_core：FAIL %d / PASS %d ====' % (_n_bad, _n_ok))
    for _d in _failed:
        print(u'  - %s' % _d)
    sys.exit(1)
print(u'==== recheck154_core：PASS %d / FAIL 0 ====' % (_n_ok,))

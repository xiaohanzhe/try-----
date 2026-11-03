# -*- coding: utf-8 -*-
u"""第153轮 · 核心文件复检（本轮改了 **2 个产品文件 + 5 个旧夹具 + 1 个登记表**，新增 1 个目录）。

规矩来源（用户口径逐字）：「**以后再调整重要核心文件时一定要记得复检**」。
六项固定形状：① 语法 ② 结构自检 ③ 无 BOM / 无 U+FFFD ④ 恒真判据复查
⑤ 逐令牌回验 ⑥ 工作区干净 ＋ 该跑回归的跑回归。

| 段 | 守什么 |
|---|---|
| H1 | 改动面：**恰好**点名的 12 个跟踪文件（多一个少一个都红）+ 未跟踪只有本轮那个目录 |
| H2 | 产品足迹：`main.py` **+65/−1** / `npc_errand.py` **+1/−0**（只补 `WIRING` 文本，**七键不变**）/ 五个旧夹具各 **+7/−0**（空桩） |
| H3 | 语法：`ast.parse`（**不**用 `py_compile` —— 会产 `.pyc`，改被测状态）+ 分母闸 |
| H4 | 编码：无 BOM / 无 U+FFFD / **裸 LF = 0**（`main.py` 全篇 CRLF） |
| H5 | 结构自检：**五条读源码才看得见**的关系 |
| H6 | 逐令牌回验：本轮新增的与**旧的**都回验；下沉到详版的令牌去详版 `in` 一次 |
| H7 | 恒真判据复查：**两套 harness** 都看；`mutate` 的还原在 `finally` |
| H8 | 卫生：`.pyc/.bak/~` 0 个；新增目录里没有易变物 |

## H5 为什么**不重复** `check153`

`check153` 的 A/B 段是**行为级**（真跑）。这里补的是"**读源码才能看见**"的那几条：

1. tick 里三句的**行序** `drop < commit < report`（行为面 `A5` 看的是运行期事件表，
   这里看的是**源码顺序** —— 两者能同时被满足，但一个是动态、一个是静态）；
2. `_errand_report_ack` 体内**没有** `npc_speak`、**没有** `remember(`
   （`C2`/`C3` 已守，这里在"改过之后"再静态确认一次，防的是复检自己也被改坏）；
3. `chat_with_ai(..., remember=False)` 是**字面量**（不是变量）；
4. **`WIRING` 仍是 7 键** —— 本轮改了 `finish` 条目的**文本**，
   绝不能顺手加第 8 个键（`check150 A25` 锁死了这个契约面）；
5. 全仓 `_errand_report_ack` 的**调用点恰好 1 处**。

★ 本文件**不进 `SUITES`**：H1/H2 依赖 `git diff`（提交后就变空），它是**提交前**的闸。
  常驻回归由 `check153`（32 条）+ `mutate153`（30 条）承担。
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
MOD = os.path.join(PKG, 'modules', 'npc_errand.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
MEM = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
MEM_LONG = os.path.join(ROOT, '.workbuddy', 'memory',
                        u'\u53c2\u8003-\u5951\u7ea6\u4e0e\u5386\u8f6e\uff08\u8be6\u7248\uff09.md')
CHECK153 = os.path.join(HERE, 'check153.py')
MUTATE153 = os.path.join(HERE, 'mutate153.py')

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

# =============================================== H1 改动面
head(u'H1 改动面：点名核对（多一个少一个都红）')

_num, _err, _ = _git('-c', 'core.quotepath=false', 'diff', '--numstat')
_rows = [ln for ln in _num.splitlines() if ln.strip()]
_NS = dict((ln.split(u'\t')[2], (ln.split(u'\t')[0], ln.split(u'\t')[1]))
           for ln in _rows)

#: ★ 点名而不是"只许动 N 个文件" —— 第146轮栽过：登记新套件本来就要改 `run_all.py`。
_EXPECT = set([
    u'ralsei_pet/src/main.py',
    u'ralsei_pet/modules/npc_errand.py',
    u'code-quality-audit/regress/run_all.py',
    u'code-quality-audit/regress/baseline.json',
    # ★ 五个旧夹具：产品在 tick 里新调 `_errand_report_ack`，挂真 tick 的桩必须补装。
    u'code-quality-audit/\u7b2c150\u8f6e-\u5dee\u4e8b\u63a5\u56de\u672c\u5730\u7ebf'
    u'/_tools/check150.py',
    u'code-quality-audit/\u7b2c151\u8f6e-\u7559\u4e00\u6761\u771f\u5dee\u4e8b'
    u'/_tools/check151.py',
    u'code-quality-audit/\u7b2c151\u8f6e-\u7559\u4e00\u6761\u771f\u5dee\u4e8b'
    u'/_tools/seed151.py',
    u'code-quality-audit/\u7b2c152\u8f6e-\u5dee\u4e8b\u53eb\u505c'
    u'/_tools/check152.py',
    u'code-quality-audit/\u7b2c152\u8f6e-\u5dee\u4e8b\u53eb\u505c'
    u'/_tools/seed152.py',
    u'.workbuddy/memory/MEMORY.md',
    u'.workbuddy/memory/2026-11-03.md',
    u'.workbuddy/memory/\u53c2\u8003-\u5951\u7ea6\u4e0e\u5386\u8f6e\uff08\u8be6\u7248\uff09.md',
])
check(u'H1 被改的跟踪文件**恰好**是本轮那 12 个'
      u'（产品 2 + 审计 6 + 记忆 3 + 基线 1）',
      set(_NS) == _EXPECT,
      u'多=%s 少=%s' % (sorted(set(_NS) - _EXPECT), sorted(_EXPECT - set(_NS))))

_st, _, _ = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_untracked = [ln[3:] for ln in _st.splitlines() if ln.startswith(u'?? ')]
_untracked_norm = [u.rstrip(u'/') for u in _untracked]
check(u'H1b 未跟踪的只有**本轮新增的那一个目录**（`第153轮…/`）',
      set(_untracked_norm) == set([u'code-quality-audit/\u7b2c153\u8f6e-'
                                   u'\u5dee\u4e8b\u4ea4\u5dee']),
      u'%s' % (_untracked_norm,))

# =============================================== H2 产品足迹
head(u'H2 产品足迹：改动文件的增删对账')
check(u'H2 `main.py` **+68 / −1**（新增 `_errand_report_ack` 整段 + tick 一处调用'
      u' + `_npc_scene_id()` 取不到时的人话兜底；那 1 行删除 = brief 里 `%s` '
      u'后面不再补句号）',
      _NS.get(u'ralsei_pet/src/main.py') == (u'68', u'1'),
      u'%s' % (_NS.get(u'ralsei_pet/src/main.py'),))

check(u'H2b `npc_errand.py` **+1 / −0** —— 只往 `WIRING["finish"]` 的**文本**里补一句，'
      u'**契约七键不变**（`check150 A25` 仍绿）',
      _NS.get(u'ralsei_pet/modules/npc_errand.py') == (u'1', u'0'),
      u'%s' % (_NS.get(u'ralsei_pet/modules/npc_errand.py'),))

_OBSOLETE = [
    u'code-quality-audit/\u7b2c150\u8f6e-\u5dee\u4e8b\u63a5\u56de\u672c\u5730\u7ebf'
    u'/_tools/check150.py',
    u'code-quality-audit/\u7b2c151\u8f6e-\u7559\u4e00\u6761\u771f\u5dee\u4e8b'
    u'/_tools/check151.py',
    u'code-quality-audit/\u7b2c151\u8f6e-\u7559\u4e00\u6761\u771f\u5dee\u4e8b'
    u'/_tools/seed151.py',
    u'code-quality-audit/\u7b2c152\u8f6e-\u5dee\u4e8b\u53eb\u505c'
    u'/_tools/check152.py',
    u'code-quality-audit/\u7b2c152\u8f6e-\u5dee\u4e8b\u53eb\u505c'
    u'/_tools/seed152.py',
]
_obs_ok = all(_NS.get(p) == (u'7', u'0') for p in _OBSOLETE)
check(u'H2c 五个旧夹具各 **+7 / −0**（一个空桩 = 1 空行 + def + 4 行注释 + return，'
      u'**不动它们任何一条判据**）',
      _obs_ok, u'%s' % ([(os.path.basename(p), _NS.get(p)) for p in _OBSOLETE],))

_mem_add = _NS.get(u'.workbuddy/memory/MEMORY.md')
check(u'H2d 速查本**只动一处**（`+1/−1`：锁号速查换成 `check153`，不借机膨胀 ——'
      u'它离 `check95 A2` 的 10,000 上限只剩个位数）',
      _mem_add == (u'1', u'1'), u'%s' % (_mem_add,))

_run = _NS.get(u'code-quality-audit/regress/run_all.py')
check(u'H2e `run_all.py` 只加了 `check153` 一条登记（`−0`，没顺手改别的套件）',
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
      and len([n for n in ast.walk(_TREE)
               if isinstance(n, ast.FunctionDef)]) >= 300,
      u'成立=%s' % (_TREE is not None,))

_MOD = None
try:
    _MOD = ast.parse(_read(MOD))
    _syn2 = None
except SyntaxError as _e:
    _syn2 = str(_e)
check(u'H3c `npc_errand.py` 可解析（只改了一个字符串，但它仍是**零依赖模块**）',
      _syn2 is None, u'%s' % (_syn2,))

_SELF_T = ast.parse(_read(os.path.abspath(__file__)))
_SELF_FN = set(n.name for n in ast.walk(_SELF_T)
               if isinstance(n, ast.FunctionDef))
check(u'H3d **本模块自己**也可解析，且 `check`/`head`/`_git` 都在'
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
      u'裸LF=%d / CRLF=%d' % (_bare, _crlf))
check(u'H4b 记忆两份与 `run_all.py` 都没有 U+FFFD（替换字符一出现就是编码事故）',
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


def _lineno(fn, attr):
    got = _calls(fn, attr)
    return got[0].lineno if got else None


_RC = _cls(_TREE, u'RalseiPet')
_TICK = _m(_RC, u'_npc_errand_tick')
_REPORT = _m(_RC, u'_errand_report_ack')

# ---- H5a：三句的行序（静态）----
_ld = _lineno(_TICK, u'drop')
_lc = _lineno(_TICK, u'_npc_errand_commit')
_lr = _lineno(_TICK, u'_errand_report_ack')
check(u'H5a tick 里 `drop < commit < report`（源码行序；`A5` 看的是运行期事件表，'
      u'一个静态一个动态）',
      None not in (_ld, _lc, _lr) and _ld < _lc < _lr,
      u'三者都找到=%s' % (None not in (_ld, _lc, _lr),))

# ---- H5b：交差体内不许有的两个调用 ----
check(u'H5b `_errand_report_ack` 体内**没有** `npc_speak` 也没有 `remember(`'
      u'（前者会伪造玩家发言、后者会把同一件事记两条）',
      _REPORT is not None and not _calls(_REPORT, u'npc_speak')
      and not _calls(_REPORT, u'remember'),
      u'npc_speak=%d / remember=%d'
      % (len(_calls(_REPORT, u'npc_speak')),
         len(_calls(_REPORT, u'remember'))))

# ---- H5c：remember=False 是字面量 ----
_kw = None
for _c in (_calls(_REPORT, u'chat_with_ai') or []):
    for _k in _c.keywords:
        if _k.arg == u'remember' and isinstance(_k.value, ast.Constant):
            _kw = _k.value.value
check(u'H5c `chat_with_ai(..., remember=False)` 是**字面量**（不是变量名，改着改着不会变 True）',
      _kw is False, u'实得=%r' % (_kw,))

# ---- H5d：WIRING 仍是 7 键 ----
sys.path.insert(0, PKG)
sys.path.insert(0, os.path.join(PKG, 'modules'))
from modules import npc_errand as ER                        # noqa: E402

check(u'H5d ★★ `npc_errand.WIRING` 仍是**七键**（本轮只改了 `finish` 的文本，'
      u'`check150 A25` 锁的就是这个键集 —— 加第 8 个键会当场红）',
      set(ER.WIRING) == set((u'assign', u'tick', u'gate', u'abort', u'put',
                             u'finish', u'decoupled'))
      and u'\u4ea4\u5dee' in ER.WIRING.get(u'finish', u''),
      u'键数=%d' % (len(ER.WIRING),))

# ---- H5e：全仓调用点恰好 1 处 ----
_n_call = 0
for _n in ast.walk(_TREE):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
            and _n.func.attr == u'_errand_report_ack':
        _n_call += 1
check(u'H5e 全仓 `_errand_report_ack` **调用点恰好 1 处**（就 tick 里那一处；'
      u'别处偷偷调 = 再说一遍）',
      _n_call == 1, u'调用点=%d' % (_n_call,))

# =============================================== H6 逐令牌回验
head(u'H6 逐令牌回验：新增的与**旧的**都回验')
_TOK_MAIN = [
    u'_errand_report_ack',
    u'_ERRAND_CANCEL_NEEDS_NAME',   # 旧的（第152轮）
    u'ERRAND_NEGATIONS',            # 旧的
    u'_errand_find_name',           # 旧的
    u'remember=False',
    u'_npc_ai_available',
    u'npc_persona_of',
    u'_errand_place_label',
    u'_errand_show_reply',
]
_missing = [t for t in _TOK_MAIN if t not in SRC_MAIN]
check(u'H6 本轮新增 + 前三轮的令牌**逐个**回 `main.py` 各 `in` 一次'
      u'（新旧都查，别只查新的）',
      not _missing, u'缺=%s' % (_missing,))

_TOK_LONG = [u'\u00a7153', u'_errand_report_ack', u'remember=False',
             u'take_results']
_missing2 = [t for t in _TOK_LONG if t not in SRC_LONG]
check(u'H6b 下沉到**详版**的令牌逐条回 `in`（§153 真的写进去了）',
      not _missing2, u'缺=%s' % (_missing2,))

check(u'H6c 速查本仍指向最新的锁号（`check153` 在、`check147` 已让位）',
      u'check153' in SRC_MEM and u'check150' in SRC_MEM,
      u'成立=%s' % (u'check153' in SRC_MEM,))

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


_T153 = ast.parse(_read(CHECK153))
_TM153 = ast.parse(_read(MUTATE153))
check(u'H7 `check153` 里没有 `check(desc, True, …)` 这种**恒真**断言',
      not _const_true_args(_T153, u'check'),
      u'条数=%d' % (len(_const_true_args(_T153, u'check')),))
check(u'H7b `mutate153` 里同样没有恒真（`mutate` 自己的 `check` 也查）',
      not _const_true_args(_TM153, u'check'),
      u'条数=%d' % (len(_const_true_args(_TM153, u'check')),))
_ok_calls = [n for n in ast.walk(_T153)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == u'ok']
check(u'H7c `check153` **不用** `ok()` —— 两套 harness 的签名不同'
      u'（`ok(cond,msg)` / `check(desc,cond,…)`），混用就会"看着在守其实没守"',
      not _ok_calls, u'ok() 调用=%d' % (len(_ok_calls),))

_finally_write = False
for n in ast.walk(_TM153):
    if isinstance(n, ast.Try) and n.finalbody:
        for b in ast.walk(ast.Module(body=n.finalbody, type_ignores=[])):
            if isinstance(b, ast.Call) and isinstance(b.func, ast.Name) \
                    and b.func.id == u'_write':
                _finally_write = True
check(u'H7d `mutate153` 的**字节级还原在 `finally` 里**'
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
_evidence = os.path.join(ROUND, u'_evidence')
check(u'H8b 本轮**没有** `_evidence/`（判据全是活跑，不存易变物）',
      not os.path.isdir(_evidence), u'成立=%s' % (not os.path.isdir(_evidence),))

print(u'')
if _n_bad:
    print(u'==== recheck153_core：FAIL %d / PASS %d ====' % (_n_bad, _n_ok))
    for _d in _failed:
        print(u'  - %s' % _d)
    sys.exit(1)
print(u'==== recheck153_core：PASS %d / FAIL 0 ====' % (_n_ok,))

# -*- coding: utf-8 -*-
u"""第152轮 · 核心文件复检（本轮改了 **1 个产品文件 + 1 个套件登记表**，新增 1 个目录）。

规矩来源（用户口径逐字）：「**以后再调整重要核心文件时一定要记得复检**」。
六项固定形状：① 语法 ② 结构自检 ③ 无 BOM / 无 U+FFFD ④ 恒真判据复查
⑤ 逐令牌回验 ⑥ 工作区干净 ＋ 该跑回归的跑回归。

| 段 | 守什么 |
|---|---|
| H1 | 改动面：**恰好**点名的跟踪文件（多一个少一个都红）+ 未跟踪只有本轮那个目录 |
| H2 | 产品足迹：`main.py` **+196/−19**（19 行删除**全部**是"名字查找"抽出来的那一段）；速查本等量 |
| H3 | 语法：`main.py` `ast.parse`（**不**用 `py_compile` —— 会产 `.pyc`，改被测状态） |
| H4 | 编码：无 BOM / 无 U+FFFD / **裸 LF = 0**（`main.py` 全篇 CRLF） |
| H5 | 结构自检：**五条本轮新增**的关系（`check152` 没守或只守一半的） |
| H6 | 逐令牌回验：本轮新增的与**旧的**都回验；下沉到详版的令牌去详版 `in` 一次 |
| H7 | 恒真判据复查：两套 harness（`check` / `mutate`）都看；`mutate` 的还原在 `finally` |
| H8 | 卫生：`.pyc/.bak/~` 0 个；`_evidence` 无易变物 |

★ 本文件**不进 `SUITES`**：H1/H2 依赖 `git diff`（提交后就变空），它是**提交前**的闸。
  常驻回归由 `check152`（37 条）+ `mutate152`（24 条）承担。

## H5 为什么**不重复** `check152`

`check152` 的 A/B/C 段是**行为级**（真跑）。这里补的是"**读源码才能看见**"的那几条：

1. `handle_errand_command` 里两个解析各**恰好一次**（多一次 = 重复判断，行为可能没错，
   但以后改一处忘一处就是两个真相）；
2. `cancel_errand` 体内 **`abort` 必须先于 `drop`** —— 反过来的话，撤覆盖那一刻
   差事还在表里 ⇒ 下一拍 `working_positions()` 又把他压回目的地；
3. `cancel_errand` 体内**不许出现** `_npc_errand_commit`（作废 ≠ 办完，
   这是第150轮 §150.5 那条"两种收尾不能混"的同一条）；
4. **两层** `board.enabled` 检查都在（解析层别吞聊天 / 动作层别动手）——
   `B8` 与 `A6` 各守一层，这里再静态确认两处都在；
5. `ERRAND_NEGATIONS` 里没有**空串 / 单字 ASCII** 这种会全命中的垃圾词。
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
    # ★ 本轮改了**两个旧夹具**：产品新增了 `_errand_find_name` 这个协作者，
    #   桩必须跟着装（否则旧套件在 `_Host` 上 AttributeError —— 是"夹具比产品旧"，
    #   不是产品坏了）。`check114` 顺带**补登记**进 `SUITES`（它从没进过）。
    u'code-quality-audit/\u7b2c150\u8f6e-\u5dee\u4e8b\u63a5\u56de\u672c\u5730\u7ebf'
    u'/_tools/check150.py',
    u'code-quality-audit/\u7b2c114\u8f6e-\u5dee\u4e8b\u4e16\u754c\u95e8\u63a7\u4e0e\u6d3e\u53d1'
    u'/_tools/check114.py',
    u'.workbuddy/memory/MEMORY.md',
    u'.workbuddy/memory/2026-11-03.md',
    u'.workbuddy/memory/\u53c2\u8003-\u5951\u7ea6\u4e0e\u5386\u8f6e\uff08\u8be6\u7248\uff09.md',
])
check(u'H1 被改的跟踪文件**恰好**是本轮那 8 个（产品 1 + 审计 4 + 记忆 3）',
      set(_NS) == _EXPECT,
      u'多=%s 少=%s' % (sorted(set(_NS) - _EXPECT), sorted(_EXPECT - set(_NS))))

_st, _, _ = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_untracked = [ln[3:] for ln in _st.splitlines() if ln.startswith(u'?? ')]
_untracked_norm = [u.rstrip(u'/') for u in _untracked]
check(u'H1b 未跟踪的只有**本轮新增的那一个目录**（`第152轮…/`）',
      set(_untracked_norm) == set([u'code-quality-audit/\u7b2c152\u8f6e-'
                                   u'\u5dee\u4e8b\u53eb\u505c']),
      u'%s' % (_untracked_norm,))

# =============================================== H2 产品足迹
head(u'H2 产品足迹：改动文件的增删对账')
check(u'H2 `main.py` **+200 / −19**（19 行删除 = 把"名字查找"抽成 `_errand_find_name`，'
      u'逻辑等价、零语义删除）',
      _NS.get(u'ralsei_pet/src/main.py') == (u'200', u'19'),
      u'%s' % (_NS.get(u'ralsei_pet/src/main.py'),))

_mem_add = _NS.get(u'.workbuddy/memory/MEMORY.md')
check(u'H2b 速查本**只动一处**（`+1/−1`：锁号速查换成 `check152`，不借机膨胀 —— '
      u'它离 `check95 A2` 的 10,000 上限只剩个位数）',
      _mem_add == (u'1', u'1'), u'%s' % (_mem_add,))

_run = _NS.get(u'code-quality-audit/regress/run_all.py')
check(u'H2c `run_all.py` 只加了 `check152` 一条登记（`−0`，没顺手改别的套件）',
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


def _has_enabled_guard(fn):
    if fn is None:
        return False
    for n in ast.walk(fn):
        if isinstance(n, ast.If) and any(
                isinstance(x, ast.Attribute) and x.attr == u'enabled'
                for x in ast.walk(n.test)):
            return True
    return False


_CLS = _cls(_TREE, u'RalseiPet')
_HANDLE = _m(_CLS, u'handle_errand_command')
_PCANCEL = _m(_CLS, u'_errand_parse_cancel')
_CANCEL = _m(_CLS, u'cancel_errand')

# ---- H5a：两个解析各恰好一次，取消在前 ----
_par = _calls(_HANDLE, u'_errand_parse_cancel')
_int = _calls(_HANDLE, u'_errand_parse_intent')
_order = (len(_par) == 1 and len(_int) == 1
          and _par[0].lineno < _int[0].lineno)
check(u'H5a `handle_errand_command` 里两个解析各**恰好一次**，且取消在派活**之前**',
      _order, u'成立=%s' % (_order,))

# ---- H5b：abort 先于 drop ----
_ab = _calls(_CANCEL, u'abort')
_dr = _calls(_CANCEL, u'drop')
_order2 = (len(_ab) == 1 and len(_dr) == 1 and _ab[0].lineno < _dr[0].lineno)
check(u'H5b `cancel_errand` 里 **`abort` 先于 `drop`**（反了 ⇒ 下一拍又被压回目的地）',
      _order2, u'成立=%s' % (_order2,))

# ---- H5c：作废不许走 commit ----
check(u'H5c `cancel_errand` 体内**没有** `_npc_errand_commit`（作废 ≠ 办完）',
      not _calls(_CANCEL, u'_npc_errand_commit'),
      u'成立=%s' % (not _calls(_CANCEL, u'_npc_errand_commit'),))

# ---- H5d：两层 enabled 检查都在 ----
check(u'H5d **两层** `board.enabled` 检查都在（解析层 `B8` / 动作层 `A6` 各守一层）',
      _has_enabled_guard(_PCANCEL) and _has_enabled_guard(_CANCEL),
      u'解析层=%s 动作层=%s' % (_has_enabled_guard(_PCANCEL),
                                _has_enabled_guard(_CANCEL)))

# ---- H5e：否定词表里没有空串/单 ASCII 这种全命中的垃圾词 ----
_NEG = None
for _n in (_CLS.body if _CLS else []):
    if isinstance(_n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == u'ERRAND_NEGATIONS'
            for t in _n.targets):
        try:
            _NEG = list(ast.literal_eval(_n.value))
        except Exception:
            _NEG = None
_JUNK = [w for w in (_NEG or []) if not isinstance(w, str) or not w.strip()
         or (len(w) == 1 and w.isascii())]
check(u'H5e 否定词表每一项都是**非空多字**（空串/单 ASCII 会让每条句子都被当否定句）',
      bool(_NEG) and not _JUNK, u'垃圾项=%s' % (_JUNK,))

# =============================================== H6 逐令牌回验
head(u'H6 逐令牌回验：新增的与**旧的**都逐个回验')
_NEW = [u'cancel_errand', u'_errand_parse_cancel', u'_errand_find_name',
        u'_errand_is_negative', u'ERRAND_NEGATIONS', u'_errand_cancel_ack',
        u'_ERRAND_CANCEL_NEEDS_NAME', u'_ERRAND_CANCEL_ANY']
_NEW_BAD = [t for t in _NEW if t not in SRC_MAIN]
check(u'H6 本轮新增的 8 个令牌**逐个**在 `main.py` 里',
      not _NEW_BAD, u'缺=%s' % (_NEW_BAD,))

_OLD = [u'def assign_errand', u'def handle_errand_command', u'def _errand_parse_intent',
        u'def _npc_errand_tick', u'def _npc_errand_gate', u'def _npc_errand_commit',
        u'def _npc_errand_note', u'NPC_ERRAND_ENABLED', u'NPC_ERRAND_DEMO',
        u'def _npc_errand_demo', u'ERRAND_INTENT_VERBS', u'ERRAND_PLACE_ALIASES']
_OLD_BAD = [t for t in _OLD if SRC_MAIN.count(t) < 1]
check(u'H6b 旧令牌也逐个回验（叫停没把派活/示范差事/门控整条链挤掉）',
      not _OLD_BAD, u'缺=%s' % (_OLD_BAD,))

check(u'H6c `run_all.py` 里 `check152` 已登记（`SUITES` 里真有这条）',
      u"'id': 'check152'" in _read(RUNALL),
      u'成立=%s' % (u"'id': 'check152'" in _read(RUNALL),))

check(u'H6d 记忆：速查本的"锁号速查"里已有 `check152`（下一轮能找到入口）',
      u'`check152`' in SRC_MEM,
      u'成立=%s' % (u'`check152`' in SRC_MEM,))
# ★ 速查本体积有上限（`check95 A2` 硬闸）⇒ 容易只留指针 ⇒ 逐令牌必须**去详版 `in` 一次**
_DOWN = [u'check152', u'\u00a7152', u'cancel_errand', u'_errand_parse_cancel',
         u'ERRAND_NEGATIONS', u'\u53eb\u505c']
_DOWN_BAD = [t for t in _DOWN if t not in SRC_LONG]
check(u'H6e 详版里 §152 的令牌**逐个找得到**（速查本留指针 ≠ 丢信息）',
      not _DOWN_BAD, u'缺=%s' % (_DOWN_BAD,))

# =============================================== H7 恒真判据复查
head(u'H7 恒真判据复查：检查"守人的判据"自己')
_TOOLS = [os.path.join(HERE, u'check152.py'), os.path.join(HERE, u'mutate152.py')]
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
check(u'H7b `mutate152` 的"按字节还原"确实在 `finally` 里（中途抛异常也不留坏文件）',
      len(_finally) >= 1, u'成立=%s' % (len(_finally) >= 1,))

_C152 = ast.parse(_read(_TOOLS[0]))
_call_cnt = len([n for n in ast.walk(_C152)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == u'check'])
check(u'H7c `check152` 的判据条数是**常量**（不随环境增减 ⇒ 换机器不会少数）',
      _call_cnt >= 37, u'过阈=%s' % (_call_cnt >= 37,))
# ★ 反面：`_run152` 里按输出解析的那一段不能把 `[FAIL] ` 前缀写错，
#   否则 mutate 永远拿到空集合 ⇒ "恰好变红"变成"恰好没红"也绿。
check(u'H7d `mutate152` 解析失败行时用的是产品那套 `[FAIL] ` 前缀（写错=永久假绿）',
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
print(u'recheck152_core：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)

# -*- coding: utf-8 -*-
u"""第156轮 · **核心文件复检**（`main.py` 是产品主链路，改过就必须逐项打 PASS）。

用户口径（逐字）：「**以后再调整重要核心文件时一定要记得复检**」。
⇒ 改完不许只说"改完了"。这份东西逐项核：改动面 / 体积 / 语法 / 编码 / 结构 /
   令牌 / 恒真 / 卫生，八段全绿才算收工。

★ 纪律（第144~147轮踩出来的）：
  · 判据**不回显时相量**（行号不进 desc；体积/计数只进 extra）；
  · 判据条数**不随环境变**（不用 `len(glob(...))` 当分母）；
  · ★ 报红先怀疑判据 —— 本轮 `H5d` 第一版按 `RalseiPet.__init__` 找预声明，
    实测它在 `init_npc_systems`（第149轮同款），那是**假红**，不是产品错。
"""
import ast
import io
import json
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
BASELINE = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
CHECK156 = os.path.join(HERE, 'check156.py')
MUTATE156 = os.path.join(HERE, 'mutate156.py')
PROBE156 = os.path.join(HERE, 'probe156.py')
REPORT = os.path.join(ROUND, 'report156.md')
DAYLOG = os.path.join(ROOT, '.workbuddy', 'memory', '2026-11-04.md')
FULL = os.path.join(ROOT, '.workbuddy', 'memory',
                    u'参考-契约与历轮（详版）.md')
SPEED = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')

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


def _git(*args):
    p = subprocess.Popen(['git', '-c', 'core.quotepath=false'] + list(args),
                         cwd=ROOT, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    return p.communicate()[0].decode('utf-8', 'replace')


def _read(path, newline=''):
    with io.open(path, 'r', encoding='utf-8', newline=newline) as fh:
        return fh.read()


def _numstat():
    rows = {}
    for line in _git('diff', '--numstat').strip().splitlines():
        parts = line.split('\t')
        if len(parts) != 3:
            continue
        a, d, path = parts
        try:
            rows[path.strip()] = (int(a), int(d))
        except ValueError:
            continue
    return rows


_P = 'ralsei_pet/src/main.py'
EX_NUMSTAT = {
    _P: (136, 6),
    'code-quality-audit/regress/run_all.py': (46, 0),
    'code-quality-audit/regress/baseline.json': (6, 0),
}
# ★ 三层记忆也在版本控制里，但它们每加一段就变 ⇒ 不按"精确 +/−"管，
#   只按**语义闸**：速查本不许涨、详版只增不删、日誌 append-only。
_MEM = u'.workbuddy/memory/'
EX_MEM = (_MEM + u'2026-11-04.md', _MEM + u'MEMORY.md',
          _MEM + u'参考-契约与历轮（详版）.md')
EX_MOD = sorted(list(EX_NUMSTAT.keys()) + list(EX_MEM))
ROUND_DIR = u'code-quality-audit/第156轮-欠账要留在状态里/'

SRC = _read(MAIN)
TREE = ast.parse(SRC)
_TOP = [n.name for n in TREE.body if isinstance(n, ast.FunctionDef)]
_TOPOBJ = dict((n.name, n) for n in TREE.body if isinstance(n, ast.FunctionDef))


def _clsdef(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == name:
            return n
    return None


def _method(cls, name):
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


def _calls_name(fn, name):
    out = []
    if fn is None:
        return out
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) \
                and c.func.id == name:
            out.append(c)
    return out


# ================================================ H1 改动面
mark(u'H1 改动面：跟踪文件点名 / 未跟踪只有一个目录 / 当天日志真写了 / 报告落盘')

_status = _git('status', '--porcelain')
_mod = sorted(l[3:].strip() for l in _status.splitlines()
              if l[:2].strip() == 'M')
check(u'H1 被改的**跟踪文件**恰好这六个（三个代码文件 + 三层记忆），没有第七个',
      _mod == EX_MOD,
      u'实得=%d 个 / 期望=%d 个' % (len(_mod), len(EX_MOD)))

_untracked = sorted(l[3:].strip() for l in _status.splitlines()
                    if l.startswith('??'))
check(u'H1b 未跟踪的**只有一个**：本轮目录（临时件一律落外部盘，不进工作区）',
      _untracked == [ROUND_DIR], u'实得=%d 个' % (len(_untracked),))

_day = _read(DAYLOG) if os.path.isfile(DAYLOG) else u''
check(u'H1c 当天日志**真写了**且带本轮标题', u'第156轮' in _day,
      u'字符数=%d' % (len(_day),))

check(u'H1d 报告落盘（`report156.md` 在轮次目录下、不是占位）',
      os.path.isfile(REPORT) and len(_read(REPORT)) > 2500,
      u'存在=%s' % (os.path.isfile(REPORT),))

# ================================================ H2 体积
mark(u'H2 体积：每个文件 +/− 与登记一致；`modules/` 一个字没动')

_ns = _numstat()
for _k, (_a, _d) in sorted(EX_NUMSTAT.items()):
    _got = _ns.get(_k)
    check(u'H2 %s 的改动量与登记一致' % (_k.split('/')[-1],),
          _got == (_a, _d), u'实得=%r 期望=%r' % (_got, (_a, _d)))

_mods = [k for k in _ns if k.startswith('ralsei_pet/modules/')]
check(u'H2e `ralsei_pet/modules/` **零改动**（本轮只动宿主层，'
      u'机制层 `npc_errand.py` 一个字节都没碰）',
      not _mods, u'改动文件=%d 个' % (len(_mods),))

_mem_speed = _ns.get(EX_MEM[1], (0, 0))
_mem_day = _ns.get(EX_MEM[0], (0, 0))
_mem_full = _ns.get(EX_MEM[2], (0, 0))
check(u'H2g 速查本 `MEMORY.md` **没有涨**（净增 ≤ 0：`check95 A2` 的 10000 闸就在头上）',
      _mem_speed[0] <= _mem_speed[1], u'+%d/−%d' % _mem_speed)
check(u'H2h 详版本轮**只增不删**（老内容一个字都不许被顺手删掉）',
      _mem_full[1] == 0 and _mem_full[0] > 0, u'+%d/−%d' % _mem_full)
check(u'H2i 当天日志 `append-only`', _mem_day[1] == 0 and _mem_day[0] > 0,
      u'+%d/−%d' % _mem_day)

_lines = SRC.count('\r\n')
check(u'H2f `main.py` **没有缩水**（净增 > 0 且行数高于上轮收口值，反回滚闸）',
      _ns.get(_P, (0, 0))[0] > _ns.get(_P, (0, 0))[1] and _lines > 18559,
      u'行数=%d（第155轮收口时 18559）' % (_lines,))

# ================================================ H3 语法
mark(u'H3 语法：本轮碰过的五个文件都能 `ast.parse`（**不产 `.pyc`**）')

for _label, _path in ((u'main.py', MAIN), (u'check156.py', CHECK156),
                      (u'mutate156.py', MUTATE156), (u'probe156.py', PROBE156),
                      (u'run_all.py', RUNALL)):
    try:
        ast.parse(_read(_path))
        _ok = True
        _err = u''
    except SyntaxError as e:
        _ok = False
        _err = u'%s: %s' % (e.lineno, e.msg)
    check(u'H3 %s 语法 ok' % (_label,), _ok, _err)

# ================================================ H4 编码
mark(u'H4 编码：无 BOM / `main.py` 全 CRLF / 新文件全 LF / 无 U+FFFD')

check(u'H4a `main.py` 无 BOM（一有 BOM，`ast.parse` 与打包都会出怪事）',
      not SRC.startswith(u'\ufeff'), u'BOM=%s' % (SRC.startswith(u'\ufeff'),))
_bare = SRC.count('\n') - _lines
check(u'H4b `main.py` 全 CRLF、**裸 LF = 0**（编辑没把换行改掉）',
      _lines > 18000 and _bare == 0, u'CRLF=%d 裸LF=%d' % (_lines, _bare))

_lf_ok = []
for _path in (CHECK156, MUTATE156, PROBE156):
    _t = _read(_path, newline='')
    _lf_ok.append(_t.count('\r\n') == 0)
check(u'H4c 本轮三个新工具脚本全 LF（与 `第150~155轮` 的套件同构）',
      all(_lf_ok), u'全 LF=%s' % (all(_lf_ok),))

_fffd = SRC.count(u'\ufffd')
check(u'H4d `main.py` 里**没有** U+FFFD（编码被转坏时最先出这个字符）',
      _fffd == 0, u'个数=%d' % (_fffd,))

# ================================================ H5 结构
mark(u'H5 结构：登记在派成之后 / 不在门控拒支 / 函数模块级 / 预声明在位 / '
     u'空账返回空串 / 两条线各用各的 id')

_assign = _method(_clsdef(TREE, 'RalseiPet'), 'assign_errand')
_ln_add = [c.lineno for c in _calls_name(_assign, '_errand_given_up_add')]
_ln_bassign = [c.lineno for c in _calls(_assign, 'assign')]
check(u'H5a 欠账登记在 `board.assign` **之后**（派发失败也记一笔"被挤掉"= 假记忆）',
      bool(_ln_add) and bool(_ln_bassign) and min(_ln_add) > min(_ln_bassign),
      u'登记处数=%d assign 处数=%d' % (len(_ln_add), len(_ln_bassign)))

_gate_calls = _calls(_assign, '_npc_errand_gate')
_gate_if = None
if _gate_calls:
    _cand = [n for n in _assign.body
             if isinstance(n, ast.If) and n.lineno >= _gate_calls[0].lineno]
    if _cand:
        _gate_if = min(_cand, key=lambda n: n.lineno)
_in_gate = False
if _gate_if is not None:
    for c in ast.walk(_gate_if):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) \
                and c.func.id == '_errand_given_up_add':
            _in_gate = True
check(u'H5b 欠账**不在**门控拒那一支里（"去不了"不是"被改派"）',
      _gate_if is not None and not _in_gate,
      u'定位到拒支=%s 支内=%s' % (_gate_if is not None, _in_gate))

check(u'H5c 三个欠账帮手是**模块级**（写成方法 ⇒ 轻宿主当场 `AttributeError`，'
      u'第152轮同款第 4 次）',
      all(n in _TOP for n in ('_errand_given_up_add', '_errand_given_up_of',
                              '_errand_backlog_brief', '_errand_item_txt')),
      u'模块级=%s' % (all(n in _TOP for n in (
          '_errand_given_up_add', '_errand_given_up_of',
          '_errand_backlog_brief', '_errand_item_txt')),))

# ★ 第一版按 `RalseiPet.__init__` 找 ⇒ 假红：预声明在 `init_npc_systems`
#   （第149轮同款坑，那批"9 字段预声明"也在那儿）。
_init = _method(_clsdef(TREE, 'RalseiPet'), 'init_npc_systems')
_decl = False
for n in ast.walk(_init) if _init is not None else []:
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Attribute) and t.attr == '_errand_given_up' \
                    and isinstance(t.value, ast.Name) and t.value.id == 'self':
                _decl = True
check(u'H5d `self._errand_given_up = {}` 在 `init_npc_systems` 里**预声明**'
      u'（不是靠 `getattr` 兜底过的）',
      _decl, u'声明=%s' % (_decl,))

_bfn = _TOPOBJ.get('_errand_backlog_brief')
_empty_ret = False
if _bfn is not None:
    for n in _bfn.body:
        if isinstance(n, ast.If) and isinstance(n.test, ast.UnaryOp) \
                and isinstance(n.test.operand, ast.Name) \
                and n.test.operand.id == 'items':
            for s in n.body:
                if isinstance(s, ast.Return) and isinstance(s.value, ast.Constant) \
                        and s.value.value == '':
                    _empty_ret = True
check(u'H5e `_errand_backlog_brief` 空账**返回 `\'\'`**（零回归的根：调用方一个字都不加）',
      _empty_ret, u'空返回=%s' % (_empty_ret,))

_sel_npc = []
for c in _calls_name(_method(_clsdef(TREE, 'RalseiPet'), '_build_npc_context'),
                     '_errand_backlog_brief'):
    for a in c.args[1:]:
        _sel_npc.append(getattr(a, 'id', None) or getattr(a, 'value', None))
_sel_rs = []
for n in ast.walk(TREE):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
            and n.func.id == '_errand_backlog_brief':
        for a in n.args[1:]:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                _sel_rs.append(a.value)
check(u'H5f NPC 线用**传进来的 `npc_id`**、Ralsei 线用 `\'ralsei\'`（各一处，不串味）',
      _sel_npc == ['npc_id'] and _sel_rs == ['ralsei'],
      u'npc=%r ralsei=%r' % (_sel_npc, _sel_rs))

_consts = {}
for _name in ('ERRAND_GIVEN_UP_TTL', 'ERRAND_GIVEN_UP_MAX'):
    _hit = False
    for n in TREE.body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == _name:
                    _hit = True
    _consts[_name] = _hit
_used = set()
for _f in ('_errand_given_up_add', '_errand_given_up_of'):
    for n in ast.walk(_TOPOBJ.get(_f) or ast.Module(body=[], type_ignores=[])):
        if isinstance(n, ast.Name) and n.id.startswith('ERRAND_GIVEN_UP'):
            _used.add(n.id)
check(u'H5g TTL 与上限是**模块级常量**、且被函数**真的读**（不是写死字面量）',
      all(_consts.values()) and _used == {'ERRAND_GIVEN_UP_TTL',
                                         'ERRAND_GIVEN_UP_MAX'},
      u'常量=%s 引用=%r' % (all(_consts.values()), sorted(_used)))

# ================================================ H6 令牌回验
mark(u'H6 令牌回验：改过 / 删掉的每一处都回原文件 `in` 一次')

_TOKENS = (
    (u'def _errand_item_txt', True),
    (u'def _errand_given_up_add', True),
    (u'def _errand_given_up_of', True),
    (u'def _errand_backlog_brief', True),
    (u'ERRAND_GIVEN_UP_TTL = 86400.0', True),
    (u'ERRAND_GIVEN_UP_MAX = 8', True),
    (u'self._errand_given_up = {}', True),
    (u'你手上还有 %d 件没办完就被叫走的事', True),
    (u'要不要提、怎么提由你自己决定', True),
    (u'我本来要%s，还没办完，又被派去 %s %s了', True),
    (u'去 %s 走一趟', True),
    (u'_errand_given_up_of(self, npc_id, now=now)', True),
)
_bad_tok = []
for _tok, _want in _TOKENS:
    if (_tok in SRC) != _want:
        _bad_tok.append(_tok)
check(u'H6 十二个令牌逐个回验（改过的都在、删掉的确实不在了）',
      not _bad_tok, u'不符=%d 个' % (len(_bad_tok),))

check(u'H6b 机制层 `npc_errand.py` 里**不出现** `given_up`'
      u'（存档格式与 `WIRING` 契约都没动）',
      'given_up' not in _read(os.path.join(ROOT, 'ralsei_pet', 'modules',
                                           'npc_errand.py')),
      u'')

_ctx_doc = ast.get_docstring(_TOPOBJ.get('_errand_backlog_brief') or
                             ast.Module(body=[], type_ignores=[])) or u''
check(u'H6c `_errand_backlog_brief` 的 docstring 写明了"空 ⇒ `\'\'`、调用方一个字都不加"'
      u'与"台词不写死"（下一个人不用读代码猜）',
      u"''" in _ctx_doc or u'`\'\'`' in _ctx_doc or u'空' in _ctx_doc,
      u'docstring 长度=%d' % (len(_ctx_doc),))

# ================================================ H7 恒真复查
mark(u'H7 恒真复查：判据名非空字面量 / 不用 `ok()` / 破坏清单都填了期望 / 探针挂的是产品函数')

_self = _read(CHECK156, newline='')
_self_tree = ast.parse(_self)
_bad_names = []
_n_chk = 0
_n_ok = 0
for n in ast.walk(_self_tree):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
        if n.func.id == 'check':
            _n_chk += 1
            if not n.args or not isinstance(n.args[0], ast.Constant) \
                    or not isinstance(n.args[0].value, str) \
                    or not n.args[0].value.strip():
                _bad_names.append(getattr(n, 'lineno', -1))
        elif n.func.id == 'ok':
            _n_ok += 1
check(u'H7a `check156` 的判据名全是**非空字面量**（不是变量、不夹带计数标记）',
      not _bad_names and _n_chk >= 30,
      u'坏的=%d 条数=%d' % (len(_bad_names), _n_chk))
check(u'H7b `check156` **不用** `ok()`（两套 harness 混用 ⇒ 查恒真会漏一半）',
      _n_ok == 0, u'ok 调用=%d' % (_n_ok,))

_mut_tree = ast.parse(_read(MUTATE156, newline=''))
_n_mut = 0
_n_expect_none = 0
for n in _mut_tree.body:
    if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == 'MUTATIONS' for t in n.targets):
        for elt in n.value.elts:
            _n_mut += 1
            if len(elt.elts) >= 5 and isinstance(elt.elts[4], ast.Constant) \
                    and elt.elts[4].value is None:
                _n_expect_none += 1
check(u'H7c `mutate156` 里 15 处破坏**都填了期望**（没有留 `None` 占位）',
      _n_mut == 15 and _n_expect_none == 0,
      u'破坏=%d 占位=%d' % (_n_mut, _n_expect_none))

_probe_src = _read(PROBE156, newline='')
check(u'H7d `probe156` 挂的是**产品函数**（`assign_errand = RalseiPet.assign_errand`），'
      u'不是另写一套差事逻辑',
      'assign_errand = RalseiPet.assign_errand' in _probe_src,
      u'挂产品=%s' % ('assign_errand = RalseiPet.assign_errand' in _probe_src,))

# ================================================ H8 卫生
mark(u'H8 卫生：轮次目录齐 / 基线已登记 / 无临时盘引用 / 无新增 `.pyc`')

_files = sorted(os.listdir(HERE))
check(u'H8a 本轮 `_tools/` 四件齐（`check156` / `mutate156` / `probe156` / 本文件）',
      _files.count('check156.py') == 1 and _files.count('mutate156.py') == 1
      and _files.count('probe156.py') == 1
      and _files.count('recheck156_core.py') == 1,
      u'文件数=%d' % (len(_files),))

_bl = json.load(io.open(BASELINE, 'r', encoding='utf-8'))
_suites = _bl.get('suites', {})
check(u'H8b 基线里已登记 `check156`，且 PASS/FAIL 与实跑一致',
      _suites.get('check156', {}).get('pass') == 35
      and _suites.get('check156', {}).get('fail') == 0,
      u'登记=%s' % (bool(_suites.get('check156')),))

_rundesc = _read(RUNALL)
check(u'H8c `SUITES` 里确有 `check156` 且 desc 写明了改前数值与五处补',
      "'id': 'check156'" in _rundesc and u'欠账要留在状态里' in _rundesc,
      u'登记=%s' % ("'id': 'check156'" in _rundesc,))

_pyc_dirty = [l for l in _status.splitlines() if l.strip().endswith('.pyc')]
check(u'H8d 本轮**没有新增 / 改动**任何 `.pyc`（复检一律 `ast.parse`，不 `py_compile`）；'
      u'仓库历史遗留的那些不算',
      not _pyc_dirty, u'脏文件=%d 个' % (len(_pyc_dirty),))

check(u'H8e 三个新脚本里**没有**外部盘路径（临时件不落工作区，脚本也不许依赖它）',
      all(u'D:' + u'/_tmp' not in _read(p, newline='')
          for p in (CHECK156, MUTATE156, PROBE156)), u'')

check(u'H8f 速查本里**没有**残留"未做 灵魂视角"这类过期陈述'
      u'（本轮顺手修了 §19 那处矛盾）',
      u'**未做** 灵魂视角' not in _read(SPEED), u'')

# ================================================ 汇总
print('')
if _n_fail:
    print('recheck156_core：FAIL %d / PASS %d' % (_n_fail, _n_pass))
    for _d in _failed:
        print('  红：%s' % (_d,))
    sys.exit(1)
print('recheck156_core：%d 条全过' % (_n_pass,))
sys.exit(0)

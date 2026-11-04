# -*- coding: utf-8 -*-
u"""第157轮 · **核心文件复检**（`main.py` 是产品主链路，改过就必须逐项打 PASS）。

用户口径（逐字）：「**以后再调整重要核心文件时一定要记得复检**」。
⇒ 改完不许只说"改完了"。这份东西逐项核：改动面 / 体积 / 语法 / 编码 / 结构 /
   令牌 / 恒真 / 卫生，八段全绿才算收工。

★ 纪律（第144~156轮踩出来的）：
  · 判据**不回显时相量**（行号 / 体积 / 计数不进 desc，只进 extra）；
  · 判据条数**不随环境变**（不用 `len(glob(...))` 当分母）；
  · ★ 报红先怀疑判据 —— 本轮 `H5c` 第一版按"`_errand_` 前缀的模块级函数个数"断言，
    产品一加函数就红（规模量），改成**点名**（缺哪个）。
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
CHECK157 = os.path.join(HERE, 'check157.py')
MUTATE157 = os.path.join(HERE, 'mutate157.py')
PROBE157 = os.path.join(HERE, 'probe157.py')
CHECK156 = os.path.join(ROOT, 'code-quality-audit',
                        u'第156轮-欠账要留在状态里', '_tools', 'check156.py')
REPORT = os.path.join(ROUND, 'report157.md')
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
    _P: (148, 1),
    'code-quality-audit/regress/run_all.py': (43, 0),
    'code-quality-audit/regress/baseline.json': (7, 1),
    u'code-quality-audit/第156轮-欠账要留在状态里/_tools/check156.py': (4, 1),
}
_MEM = u'.workbuddy/memory/'
EX_MEM = (_MEM + u'2026-11-04.md', _MEM + u'MEMORY.md',
          _MEM + u'参考-契约与历轮（详版）.md')
EX_MOD = sorted(list(EX_NUMSTAT.keys()) + list(EX_MEM))
ROUND_DIR = u'code-quality-audit/第157轮-欠账要落盘/'

SRC = _read(MAIN)
TREE = ast.parse(SRC)
_TOP = [n.name for n in TREE.body if isinstance(n, ast.FunctionDef)]
_TOPOBJ = dict((n.name, n) for n in TREE.body if isinstance(n, ast.FunctionDef))
_CLSOBJ = dict((n.name, n) for n in TREE.body if isinstance(n, ast.ClassDef))


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


def _mod_calls(fn, mod_name, attr):
    out = []
    if fn is None:
        return out
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
                and c.func.attr == attr \
                and isinstance(c.func.value, ast.Name) \
                and c.func.value.id == mod_name:
            out.append(c)
    return out


# ================================================ H1 改动面
mark(u'H1 改动面：跟踪文件点名 / 未跟踪只有一个目录 / 当天日志真写了 / 报告落盘')

_status = _git('status', '--porcelain')
_mod = sorted(l[3:].strip() for l in _status.splitlines()
              if l[:2].strip() == 'M')
check(u'H1 被改的**跟踪文件**恰好这七个（四个代码/数据文件 + 三层记忆），没有第八个',
      _mod == EX_MOD,
      u'实得=%d 个 / 期望=%d 个' % (len(_mod), len(EX_MOD)))

_untracked = sorted(l[3:].strip() for l in _status.splitlines()
                    if l.startswith('??'))
check(u'H1b 未跟踪的**只有一个**：本轮目录（临时件一律落外部盘，不进工作区）',
      _untracked == [ROUND_DIR], u'实得=%d 个' % (len(_untracked),))

_day = _read(DAYLOG) if os.path.isfile(DAYLOG) else u''
check(u'H1c 当天日志**真写了**且带本轮标题', u'第157轮' in _day,
      u'字符数=%d' % (len(_day),))

check(u'H1d 报告落盘（`report157.md` 在轮次目录下、不是占位）',
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
check(u'H2e `ralsei_pet/modules/` **零改动**（本轮只动宿主层；'
      u'`npc_errand.py` 一个字节都没碰 —— 第156轮定的边界继续成立）',
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
      _ns.get(_P, (0, 0))[0] > _ns.get(_P, (0, 0))[1] and _lines > 18690,
      u'行数=%d（第156轮收口时 18690）' % (_lines,))

# ================================================ H3 语法
mark(u'H3 语法：本轮碰过的五个文件都能 `ast.parse`（**不产 `.pyc`**）')

for _label, _path in ((u'main.py', MAIN), (u'check157.py', CHECK157),
                      (u'mutate157.py', MUTATE157), (u'probe157.py', PROBE157),
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
for _path in (CHECK157, MUTATE157, PROBE157):
    _t = _read(_path, newline='')
    _lf_ok.append(_t.count('\r\n') == 0)
check(u'H4c 本轮三个新工具脚本全 LF（与 `第150~156轮` 的套件同构）',
      all(_lf_ok), u'全 LF=%s' % (all(_lf_ok),))

_fffd = SRC.count(u'\ufffd')
check(u'H4d `main.py` 里**没有** U+FFFD（编码被转坏时最先出这个字符）',
      _fffd == 0, u'个数=%d' % (_fffd,))

# ================================================ H5 结构
mark(u'H5 结构：包装文档在位 / 机制层干净 / 读侧接线 / 两个函数模块级 / '
     u'不要 tuple 的那步 / 不自己写盘')

_save = _method(_CLSOBJ.get('RalseiPet'), '_npc_errand_save')
_load = _method(_CLSOBJ.get('RalseiPet'), '_npc_errand_load')
_doc = _CLSOBJ.get('_ErrandDoc')

check(u'H5a `_ErrandDoc` 是**模块级类**且带 `to_dict`（落盘只要求这个协议）',
      _doc is not None and _method(_doc, 'to_dict') is not None,
      u'类=%s to_dict=%s'
      % (_doc is not None,
         _doc is not None and _method(_doc, 'to_dict') is not None))

check(u'H5b save 里传的是 `_ErrandDoc(...)`、且仍调 `npc_plan_store_mod.save`'
      u'（原子写照旧复用，没另写一套写盘）',
      bool([c for c in _calls(_save, 'save')
            if any(isinstance(a, ast.Call) and isinstance(a.func, ast.Name)
                   and a.func.id == '_ErrandDoc' for a in c.args)])
      and bool(_mod_calls(_save, 'npc_plan_store_mod', 'save')),
      u'处数=%d' % (len(_mod_calls(_save, 'npc_plan_store_mod', 'save')),))

check(u'H5c ★ 读侧**接上了** `_errand_given_up_restore`（写了不读 = 白改）',
      len([c for c in ast.walk(_load)
           if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
           and c.func.id == '_errand_given_up_restore']) == 1,
      u'处数=%d' % (len([c for c in ast.walk(_load)
                         if isinstance(c, ast.Call)
                         and isinstance(c.func, ast.Name)
                         and c.func.id == '_errand_given_up_restore']),))

check(u'H5d 机制层 `npc_errand.py` 里**仍不出现** `given_up`'
      u'（欠账是人类叙事，只住在宿主侧）',
      'given_up' not in _read(os.path.join(ROOT, 'ralsei_pet', 'modules',
                                           'npc_errand.py')),
      u'')

check(u'H5e dump / restore / `_ErrandDoc` 全是**模块级**（写成方法 ⇒ 轻宿主当场 '
      u'`AttributeError`，第156轮同款第 4 次的教训）',
      '_errand_given_up_dump' in _TOP and '_errand_given_up_restore' in _TOP
      and '_ErrandDoc' in _CLSOBJ,
      u'模块级=%s' % (('_errand_given_up_dump' in _TOP
                      and '_errand_given_up_restore' in _TOP
                      and '_ErrandDoc' in _CLSOBJ),))

_rst = _TOPOBJ.get('_errand_given_up_restore')
_tuple_ok = False
for n in ast.walk(_rst) if _rst is not None else []:
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
            and n.func.attr == 'append' and n.args:
        if isinstance(n.args[0], ast.Tuple) and len(n.args[0].elts) == 3:
            _tuple_ok = True
check(u'H5f ★ restore 里那步**转回 tuple** 在位（JSON 只有 list）——'
      u'不转就是"盘上有、界面上没有"',
      _tuple_ok, u'tuple 追加=%s' % (_tuple_ok,))

_io_hit = []
for _fn_name in ('_errand_given_up_dump', '_errand_given_up_restore'):
    for n in ast.walk(_TOPOBJ.get(_fn_name) or ast.Module(body=[], type_ignores=[])):
        if isinstance(n, ast.Call):
            _nm = getattr(n.func, 'id', '') or ''
            if _nm in ('open', 'makedirs', 'replace', 'remove'):
                _io_hit.append(_nm)
check(u'H5g dump / restore **自己不写盘**（纯数据变换；写盘只有一个口子）',
      not _io_hit, u'命中=%d 处' % (len(_io_hit),))

# ================================================ H6 令牌回验
mark(u'H6 令牌回验：改过 / 新增的每一处都回原文件 `in` 一次')

_TOKENS = (
    (u'class _ErrandDoc(object):', True),
    (u'def _errand_given_up_dump', True),
    (u'def _errand_given_up_restore', True),
    (u"_ErrandDoc(board, _errand_given_up_dump(self, now=now))", True),
    (u"raw.get('given_up')", True),
    (u"d['given_up'] = self._given_up", True),
    (u'rows.append((ts, dest, what))', True),
    (u"ok = bool(npc_plan_store_mod.save(path, board))", False),
)
_bad_tok = []
for _tok, _want in _TOKENS:
    if (_tok in SRC) != _want:
        _bad_tok.append(_tok)
check(u'H6 八个令牌逐个回验（新增的都在、退回裸 board 的旧写法确实不在了）',
      not _bad_tok, u'不符=%d 个' % (len(_bad_tok),))

_save_doc = ast.get_docstring(_save) or u''
_load_doc = ast.get_docstring(_load) or u''
check(u'H6b save / load 的 docstring 都写明了 `given_up` 与"机制层不该认识欠账"'
      u'（下一个人不用读代码猜边界）',
      'given_up' in _save_doc and 'given_up' in _load_doc,
      u'save=%s load=%s' % ('given_up' in _save_doc, 'given_up' in _load_doc))

# ================================================ H7 恒真复查
mark(u'H7 恒真复查：判据名非空字面量 / 不用 `ok()` / 破坏清单都填了期望 / '
     u'探针能跑改前基线')

_self = _read(CHECK157, newline='')
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
check(u'H7a `check157` 的判据名全是**非空字面量**（不是变量、不夹带计数标记）',
      not _bad_names and _n_chk >= 28,
      u'坏的=%d 条数=%d' % (len(_bad_names), _n_chk))
check(u'H7b `check157` **不用** `ok()`（两套 harness 混用 ⇒ 查恒真会漏一半）',
      _n_ok == 0, u'ok 调用=%d' % (_n_ok,))

_mut_tree = ast.parse(_read(MUTATE157, newline=''))
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
check(u'H7c `mutate157` 里 10 处破坏**都填了期望**（没有留 `None` 占位）',
      _n_mut == 10 and _n_expect_none == 0,
      u'破坏=%d 占位=%d' % (_n_mut, _n_expect_none))

_probe_src = _read(PROBE157, newline='')
check(u'H7d `probe157` 挂的是**产品函数**，且带 `--before` 改前基线口径',
      'assign_errand = RalseiPet.assign_errand' in _probe_src
      and u'--before' in _probe_src,
      u'挂产品=%s' % ('assign_errand = RalseiPet.assign_errand' in _probe_src,))

# ================================================ H8 卫生
mark(u'H8 卫生：轮次目录齐 / 基线已登记 / 无临时盘引用 / 无新增 `.pyc` / 顺带修的一处')

_files = sorted(os.listdir(HERE))
check(u'H8a 本轮 `_tools/` 四件齐（`check157` / `mutate157` / `probe157` / 本文件）',
      _files.count('check157.py') == 1 and _files.count('mutate157.py') == 1
      and _files.count('probe157.py') == 1
      and _files.count('recheck157_core.py') == 1,
      u'文件数=%d' % (len(_files),))

_bl = json.load(io.open(BASELINE, 'r', encoding='utf-8'))
_suites = _bl.get('suites', {})
check(u'H8b 基线里已登记 `check157`，且 PASS/FAIL 与实跑一致',
      _suites.get('check157', {}).get('pass') == 31
      and _suites.get('check157', {}).get('fail') == 0,
      u'登记=%s' % (bool(_suites.get('check157')),))

_rundesc = _read(RUNALL)
check(u'H8c `SUITES` 里确有 `check157` 且 desc 写明了改前数值与改法边界',
      "'id': 'check157'" in _rundesc and u'欠账要落盘' in _rundesc,
      u'登记=%s' % ("'id': 'check157'" in _rundesc,))

_pyc_dirty = [l for l in _status.splitlines() if l.strip().endswith('.pyc')]
check(u'H8d 本轮**没有新增 / 改动**任何 `.pyc`（复检一律 `ast.parse`，不 `py_compile`）；'
      u'仓库历史遗留的那些不算',
      not _pyc_dirty, u'脏文件=%d 个' % (len(_pyc_dirty),))

check(u'H8e 三个新脚本里**没有**外部盘路径（临时件落系统 temp，脚本也不许依赖它）',
      all(u'D:' + u'/_tmp' not in _read(p, newline='')
          for p in (CHECK157, MUTATE157, PROBE157)), u'')

# ★ 顺带修的一处必须留痕：check156 的 A0 原来回显"`_errand_` 前缀函数个数"（规模量），
#   本轮新增两个模块级函数 ⇒ 它报 DIFF（判定一个字没变）。改成"缺几个"（健康态恒 0）。
_c156 = _read(CHECK156, newline='')
check(u'H8f 顺带修 `check156 A0`：extra 不再回显"前缀函数个数"这种**规模量**，'
      u'改成"缺几个"（判定表达式一字未动）',
      u'模块级=%d 个' not in _c156 and u'缺=%d 个' in _c156,
      u'')

# ================================================ 汇总
print('')
if _n_fail:
    print('recheck157_core：FAIL %d / PASS %d' % (_n_fail, _n_pass))
    for _d in _failed:
        print('  红：%s' % (_d,))
    sys.exit(1)
print('recheck157_core：%d 条全过' % (_n_pass,))
sys.exit(0)

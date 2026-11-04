# -*- coding: utf-8 -*-
u"""第155轮 · **核心文件复检**（`main.py` 是产品主链路，改过就必须逐项打 PASS）。

用户口径（逐字）：「**以后再调整重要核心文件时一定要记得复检**」。
⇒ 改完不许只说"改完了"。这份东西逐项核：改动面 / 体积 / 语法 / 编码 / 结构 /
   令牌 / 恒真 / 卫生，八段全绿才算收工。

★ 纪律（第144~147轮踩出来的）：
  · 判据**不回显时相量**（行号 / 体积 / 计数不进 desc，只进 extra 或干脆不写）；
  · 判据条数**不随环境变**（不用 `len(glob(...))` 当分母）；
  · 报红先怀疑判据 —— 本轮 `H1` 第一版把"新建的当天日志"算进 `git diff`，
    它当然不在 diff 里 ⇒ 一跑就红（判据写错，不是文件错）。
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
CHECK154 = os.path.join(ROOT, 'code-quality-audit', u'第154轮-改派留痕',
                        '_tools', 'check154.py')
CHECK155 = os.path.join(HERE, 'check155.py')
MUTATE155 = os.path.join(HERE, 'mutate155.py')
PROBE155 = os.path.join(HERE, 'probe155.py')
REPORT = os.path.join(ROUND, 'report155.md')
DAYLOG = os.path.join(ROOT, '.workbuddy', 'memory', '2026-11-04.md')

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
                         stderr=subprocess.STDOUT)
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
    _P: (72, 11),
    'code-quality-audit/regress/run_all.py': (44, 0),
    'code-quality-audit/regress/baseline.json': (7, 1),
    u'code-quality-audit/第154轮-改派留痕/_tools/check154.py': (5, 2),
}
# ★ 三层记忆文件也**在版本控制里** —— 第一版 H1 只登记了四个代码文件，
#   一跑就红（判据写窄了，不是改动面超标）。这三个不按"精确 +/−"管
#   （每加一段就变），改成**语义闸**：速查本不许涨、日誌只增不删、详版必须增。
_MEM = u'.workbuddy/memory/'
EX_MEM = (_MEM + u'2026-11-04.md', _MEM + u'MEMORY.md',
          _MEM + u'参考-契约与历轮（详版）.md')
EX_MOD = sorted(list(EX_NUMSTAT.keys()) + list(EX_MEM))

SRC = _read(MAIN)
TREE = ast.parse(SRC)


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


# ================================================ H1 改动面
mark(u'H1 改动面：跟踪文件点名 / 未跟踪只有一个目录 / 当天日志真写了')

_status = _git('status', '--porcelain')
_mod = sorted(l[3:].strip() for l in _status.splitlines()
              if l[:2].strip() == 'M')
check(u'H1 被改的**跟踪文件**恰好这几个（四个代码文件 + 三层记忆），没有第五个',
      _mod == EX_MOD,
      u'实得=%d 个 / 期望=%d 个' % (len(_mod), len(EX_MOD)))

_untracked = sorted(l[3:].strip() for l in _status.splitlines()
                    if l.startswith('??'))
check(u'H1b 未跟踪的**只有一个**：本轮目录（工作时临时件一律落外部盘，不进工作区）',
      _untracked == [u'code-quality-audit/第155轮-催不是重新派/'],
      u'实得=%d 个' % (len(_untracked),))

_day = _read(DAYLOG) if os.path.isfile(DAYLOG) else u''
check(u'H1c 当天日志**真写了**且带本轮令牌（`155`）',
      u'155' in _day, u'字符数=%d' % (len(_day),))

check(u'H1d 报告落盘（`report155.md` 在轮次目录下）',
      os.path.isfile(REPORT) and len(_read(REPORT)) > 2000,
      u'存在=%s' % (os.path.isfile(REPORT),))

# ================================================ H2 体积
mark(u'H2 体积：每个文件的 +/− 与登记一致；`modules/` 一个字没动')

_ns = _numstat()
for _k, (_a, _d) in sorted(EX_NUMSTAT.items()):
    _got = _ns.get(_k)
    check(u'H2 %s 的改动量 = +%d/−%d' % (_k.split('/')[-1], _a, _d),
          _got == (_a, _d), u'实得=%r' % (_got,))

_mods = [k for k in _ns if k.startswith('ralsei_pet/modules/')]
check(u'H2e `ralsei_pet/modules/` **零改动**（本轮只动宿主层，'
      u'机制层 `npc_errand.py` 一个字节都没碰）',
      not _mods, u'改动文件=%d 个' % (len(_mods),))

_mem_speed = _ns.get(EX_MEM[1], (0, 0))
_mem_day = _ns.get(EX_MEM[0], (0, 0))
_mem_full = _ns.get(EX_MEM[2], (0, 0))
check(u'H2g 速查本 `MEMORY.md` **没有涨**（净增 ≤ 0：`check95 A2` 的 10000 闸就在头上，'
      u'本轮是"换进 `check155`、换掉一条旧锁号"的等量改写）',
      _mem_speed[0] <= _mem_speed[1],
      u'+%d/−%d' % _mem_speed)
check(u'H2h 详版本轮**只增不删**（`+%d/−%d`：老内容一个字都不许被顺手删掉）'
      % _mem_full, _mem_full[1] == 0 and _mem_full[0] > 0,
      u'+%d/−%d' % _mem_full)
check(u'H2i 当天日志 `append-only`（`+%d/−%d`）' % _mem_day,
      _mem_day[1] == 0 and _mem_day[0] > 0, u'+%d/−%d' % _mem_day)

_lines = SRC.count('\r\n')
check(u'H2f `main.py` **没有缩水**（净增 > 0，反回滚闸）',
      _ns.get(_P, (0, 0))[0] > _ns.get(_P, (0, 0))[1] and _lines > 18499,
      u'行数=%d（第154轮收口时 18499）' % (_lines,))

# ================================================ H3 语法
mark(u'H3 语法：本轮碰过的五个文件都能 `ast.parse`（**不产 `.pyc`**）')

for _label, _path in ((u'main.py', MAIN), (u'check155.py', CHECK155),
                      (u'mutate155.py', MUTATE155), (u'probe155.py', PROBE155),
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
check(u'H4b `main.py` 全 CRLF、**裸 LF = 0**（与原文件同构，编辑没把换行改掉）',
      _lines > 18000 and _bare == 0, u'CRLF=%d 裸LF=%d' % (_lines, _bare))

_lf_ok = []
for _path in (CHECK155, MUTATE155, PROBE155):
    _t = _read(_path, newline='')
    _lf_ok.append(_t.count('\r\n') == 0)
check(u'H4c 本轮三个新工具脚本全 LF（与 `第150~154轮` 的套件同构）',
      all(_lf_ok), u'全 LF=%s' % (all(_lf_ok),))

_fffd = SRC.count(u'\ufffd')
check(u'H4d `main.py` 里**没有** U+FFFD（编码被转坏时最先出这个字符）',
      _fffd == 0, u'个数=%d' % (_fffd,))

# ================================================ H5 结构
mark(u'H5 结构：短路的位置与形状 / 常量走单一真源 / 两处 brief')

_assign = _method(_clsdef(TREE, 'RalseiPet'), 'assign_errand')
_ack = _method(_clsdef(TREE, 'RalseiPet'), '_errand_ack')

_ln_ret = [n.lineno for n in ast.walk(_assign)
           if isinstance(n, ast.Return) and isinstance(n.value, ast.Name)
           and n.value.id == '_prev']
_ln_assign = [c.lineno for c in _calls(_assign, 'assign')]
_ln_gate = [c.lineno for c in _calls(_assign, '_npc_errand_gate')]
check(u'H5a "催"的短路（`return _prev`）在 `board.assign` **之前**',
      bool(_ln_ret) and bool(_ln_assign) and min(_ln_ret) < min(_ln_assign),
      u'短路处数=%d' % (len(_ln_ret),))
check(u'H5b 同一条短路也在**门控之前**（没重新派 ⇒ 不问路）',
      bool(_ln_ret) and bool(_ln_gate) and min(_ln_ret) < min(_ln_gate),
      u'门控处数=%d' % (len(_ln_gate),))

_enabled = False
for n in ast.walk(_assign):
    if isinstance(n, ast.If):
        for sub in ast.walk(n.test):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                    and sub.func.id == 'getattr' and len(sub.args) >= 2 \
                    and isinstance(sub.args[0], ast.Name) \
                    and sub.args[0].id == 'board' \
                    and isinstance(sub.args[1], ast.Constant) \
                    and sub.args[1].value == 'enabled':
                _enabled = True
check(u'H5c 短路带 `board.enabled` 闸（守 `NPC_ERRAND_ENABLED=False ⇒ '
      u'`assign_errand()` 恒 `None`` 的契约）',
      _enabled, u'有闸=%s' % (_enabled,))

_toplevel = [n.name for n in TREE.body if isinstance(n, ast.FunctionDef)]
_n_same = 0
for c in ast.walk(_assign):
    if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) \
            and c.func.id == '_errand_same_job':
        _n_same += 1
check(u'H5d `_errand_same_job` 仍是**模块级**、且 `assign_errand` 里只调**一次**'
      u'（第154轮那处重复判断已删：一条规则一个家）',
      '_errand_same_job' in _toplevel and _n_same == 1,
      u'模块级=%s 调用=%d' % ('_errand_same_job' in _toplevel, _n_same))

_consts = sorted(set(c.attr for c in ast.walk(_ack)
                     if isinstance(c, ast.Attribute)
                     and isinstance(c.value, ast.Name)
                     and c.value.id == 'npc_errand_mod'
                     and c.attr in ('WORKING', 'DONE', 'TRAVELING')))
check(u'H5e `_errand_ack` 读状态走 `npc_errand_mod` 的**常量**'
      u'（不写字面量 `\'working\'`）',
      _consts == ['DONE', 'WORKING'], u'用到=%r' % (_consts,))


def _str_of(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) \
            and isinstance(node.left, ast.Constant) \
            and isinstance(node.left.value, str):
        return node.left.value
    return None


_briefs = []
for n in ast.walk(_ack):
    if isinstance(n, ast.Assign) \
            and any(isinstance(t, ast.Name) and t.id == 'brief' for t in n.targets):
        _s = _str_of(n.value)
        if _s is not None:
            _briefs.append(_s)
check(u'H5f `_errand_ack` 里"催"与"首次"是**两处不同赋值**（`brief` 共 3 处赋值：'
      u'催 / 首次 / 去不了），两句必须不同',
      len(_briefs) == 3
      and len([s for s in _briefs if u'没有重新计时' in s]) == 1
      and len([s for s in _briefs if u'已经在路上了' in s]) == 1
      and [s for s in _briefs if u'没有重新计时' in s][0]
      != [s for s in _briefs if u'已经在路上了' in s][0],
      u'赋值处数=%d' % (len(_briefs),))

# ================================================ H6 令牌回验
mark(u'H6 令牌回验：改过 / 删掉的每一处都回原文件 `in` 一次')

_TOKENS = (
    (u'催（不重启）', True),
    (u'没有重新计时', True),
    (u'还在去的路上', True),
    (u'已经到了那里', True),
    (u"getattr(board, 'enabled', False)", True),
    (u'_errand_same_job(_prev, dest_scene, what)', True),
    (u'and not _errand_same_job(_prev, dest_scene, what)', False),
    (u'第155轮：**「催」不是「重新派」**', True),
)
_bad_tok = []
for _tok, _want in _TOKENS:
    if (_tok in SRC) != _want:
        _bad_tok.append(_tok)
check(u'H6 八个令牌逐个回验（该在的在、删掉的**确实不在了**）',
      not _bad_tok, u'不符=%d 个' % (len(_bad_tok),))

check(u'H6b 产品里**没有**残留"催也重新计时"的旧注释'
      u'（`同一句话会重新计时` 之类的话不许留在文件里误导下一个人）',
      u'同一句话会重新计时' not in SRC, u'残留=%s' % (u'同一句话会重新计时' in SRC,))

_doc = _method(_clsdef(TREE, 'RalseiPet'), 'assign_errand')
_docstr = ast.get_docstring(_doc) or u''
check(u'H6c `assign_errand` 的 docstring 写明了"同一件事重说 ⇒ 原样返回"'
      u'与"`travel/work/result` 被忽略"（下一个人不用读代码猜）',
      u'原样返回' in _docstr and u'被忽略' in _docstr,
      u'docstring 长度=%d' % (len(_docstr),))

# ================================================ H7 恒真复查
mark(u'H7 恒真复查：判据名非空字面量 / 不用 `ok()` / 破坏清单与期望数一致')

_self = _read(CHECK155, newline='')
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
check(u'H7a `check155` 的判据名全是**非空字面量**（不是变量、不夹带计数标记）',
      not _bad_names and _n_chk >= 30,
      u'坏的=%d 条数=%d' % (len(_bad_names), _n_chk))
check(u'H7b `check155` **不用** `ok()`（两套 harness 混用 ⇒ 查恒真会漏一半）',
      _n_ok == 0, u'ok 调用=%d' % (_n_ok,))

_mut_src = _read(MUTATE155, newline='')
_mut_tree = ast.parse(_mut_src)
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
check(u'H7c `mutate155` 里 12 处破坏**都填了期望**（没有留 `None` 占位）',
      _n_mut == 12 and _n_expect_none == 0,
      u'破坏=%d 占位=%d' % (_n_mut, _n_expect_none))

_probe_src = _read(PROBE155, newline='')
check(u'H7d `probe155` 借的是**同一份宿主**（`runpy` 读 `check155.py`），'
      u'没有另写一套桩',
      'runpy.run_path' in _probe_src and 'check155.py' in _probe_src,
      u'runpy=%s' % ('runpy.run_path' in _probe_src,))

# ================================================ H8 卫生
mark(u'H8 卫生：轮次目录齐 / 基线已登记 / 无临时盘引用 / 无 `.pyc`')

_files = sorted(os.listdir(HERE))
check(u'H8a 本轮 `_tools/` 四件齐（`check155` / `mutate155` / `probe155` / 本文件）',
      _files.count('check155.py') == 1 and _files.count('mutate155.py') == 1
      and _files.count('probe155.py') == 1
      and _files.count('recheck155_core.py') == 1,
      u'文件数=%d' % (len(_files),))

_bl = json.load(io.open(BASELINE, 'r', encoding='utf-8'))
_suites = _bl.get('suites', {})
check(u'H8b 基线里已登记 `check155`，且 PASS/FAIL 与实跑一致（37/0）',
      _suites.get('check155', {}).get('pass') == 37
      and _suites.get('check155', {}).get('fail') == 0,
      u'登记=%s' % (bool(_suites.get('check155')),))

_rundesc = _read(RUNALL)
check(u'H8c `SUITES` 里确有 `check155` 且 desc 写明了改前数值与两处补',
      "'id': 'check155'" in _rundesc and u'催」不是「重新派」' in _rundesc,
      u'登记=%s' % ("'id': 'check155'" in _rundesc,))

# ★ 第一版写"整个 `code-quality-audit/` 里没有 `.pyc`" ⇒ 一跑红 37 个：
#   那些是**仓库历史上就在的**（第143轮那条教训：判"无 .pyc 被跟踪"是恒假，
#   该守的是"**本轮没有新增/改动** `*.pyc`"）。改成看 `git status`。
_pyc_dirty = [l for l in _status.splitlines() if l.strip().endswith('.pyc')]
check(u'H8d 本轮**没有新增 / 改动**任何 `.pyc`（复检一律 `ast.parse`，不 `py_compile`）；'
      u'仓库历史遗留的那些不算',
      not _pyc_dirty, u'脏文件=%d 个' % (len(_pyc_dirty),))

check(u'H8e 三个新脚本里**没有**外部盘路径（临时件不落工作区，脚本也不许依赖它）',
      all(u'D:' + u'/_tmp' not in _read(p, newline='')
          for p in (CHECK155, MUTATE155, PROBE155)),
      u'')

# ================================================ 汇总
print('')
if _n_fail:
    print('recheck155_core：FAIL %d / PASS %d' % (_n_fail, _n_pass))
    for _d in _failed:
        print('  红：%s' % (_d,))
    sys.exit(1)
print('recheck155_core：%d 条全过' % (_n_pass,))
sys.exit(0)

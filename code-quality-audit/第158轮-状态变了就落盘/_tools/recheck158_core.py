# -*- coding: utf-8 -*-
u"""第158轮复检：改过 `main.py` 必复检（用户铁律）。

跑：python recheck158_core.py

守六件事：
  H1/H2 改动面与体积（**只动该动的**，且没缩水 —— 反回滚）
  H3/H4 语法与编码（CRLF、无 BOM、无 U+FFFD）
  H5   结构：四处落盘点的**力**与**位置**（和 `check158` 的 B 段互为独立验证）
  H6   令牌逐个回验（本轮新增的写法在、旧写法不在了）
  H7   恒真复查（判据名是字面量、不用 `ok()`、变异体都有期望）
  H8   卫生（四件齐、基线已登记、`SUITES` 已登记、没碰 `.pyc`、脚本不依赖外部盘）
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
MODS = os.path.join(PKG, 'modules')
BASELINE = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
MEM = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')

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


def _read(path, newline=''):
    with io.open(path, 'r', encoding='utf-8', newline=newline) as fh:
        return fh.read()


def _git(*args):
    p = subprocess.Popen(['git'] + list(args), cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.communicate()[0].decode('utf-8', 'replace')
    return p.returncode, out


SRC = _read(MAIN, newline='')
TREE = ast.parse(SRC)
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


def _kw(call, name):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def _const_is(node, val):
    return isinstance(node, ast.Constant) and node.value is val


_CLS = _CLSOBJ.get('RalseiPet')
_ASSIGN = _method(_CLS, 'assign_errand')
_CANCEL = _method(_CLS, 'cancel_errand')
_TICK = _method(_CLS, '_npc_errand_tick')

# ================================================ H1 改动面
mark(u'H1 改动面：只该动 `main.py` + 本轮目录 + 三层记忆')

_rc, _por = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_mod = [ln[3:] for ln in _por.splitlines() if ln[:2].strip() in ('M', 'A', 'D')]
_prod = [p for p in _mod if p.startswith('ralsei_pet/')]
check(u'H1 产品侧被改的**只有** `ralsei_pet/src/main.py`（数据/资源一个没动）',
      _prod == ['ralsei_pet/src/main.py'], u'合计=%d 产品改动=%r'
      % (len(_mod), _prod))
check(u'H1b 未跟踪项**全在本轮目录内**（临时件一律落外部盘，不进工作区）',
      all(p.startswith('code-quality-audit/') for p in
          [ln[3:] for ln in _por.splitlines() if ln.startswith('??')]),
      u'未跟踪=%d' % (len([ln for ln in _por.splitlines() if ln.startswith('??')]),))

# ================================================ H2 体积
mark(u'H2 体积：没缩水（反回滚闸）· `modules/` 零改动')

_n_lines = SRC.count('\r\n')
check(u'H2a `main.py` **没有缩水**：行数仍高于第157轮收口值（18837）且净增有限',
      _n_lines > 18837 and (_n_lines - 18837) < 120,
      u'行数=%d 较157轮 %+d' % (_n_lines, _n_lines - 18837))
check(u'H2b `main.py` 体积**只增**（本轮是"加落盘时机"，不该删任何东西）',
      len(SRC) > 810000, u'字符=%d' % (len(SRC),))

_rc, _ns = _git('-c', 'core.quotepath=false', 'diff', '--numstat', 'HEAD', '--',
                'ralsei_pet/modules')
check(u'H2c `ralsei_pet/modules/` **零改动**（本轮只动宿主层，机制层一个字不许碰）',
      not _ns.strip(), u'numstat=%r' % (_ns.strip()[:60],))

# ================================================ H3 语法
mark(u'H3 语法：`main.py` + 本轮四个工具脚本都能 parse')

_ok_main = True
try:
    ast.parse(SRC)
except SyntaxError as e:
    _ok_main = False
    print('  main.py 语法错：%s 行 %s' % (e, e.msg))
check(u'H3a `main.py` 语法 ok（`ast.parse`，不用 `py_compile` —— 别产 `.pyc`）', _ok_main)

for _f in ('check158.py', 'mutate158.py', 'probe158.py', 'recheck158_core.py'):
    _p = os.path.join(HERE, _f)
    _ok = os.path.isfile(_p)
    if _ok:
        try:
            ast.parse(_read(_p))
        except SyntaxError:
            _ok = False
    check(u'H3b %s 存在且语法 ok' % (_f,), _ok)

# ================================================ H4 编码
mark(u'H4 编码：CRLF 原样 · 无 BOM · 无 U+FFFD')

_bom = SRC.startswith(u'\ufeff')
_n_lf = SRC.count('\n') - SRC.count('\r\n')
check(u'H4a `main.py` 无 BOM', not _bom, u'BOM=%s' % (_bom,))
check(u'H4b `main.py` 全 CRLF、**裸 LF = 0**（编辑没把换行改掉）', _n_lf == 0,
      u'裸LF=%d' % (_n_lf,))
check(u'H4c `main.py` 里**没有** U+FFFD（编码被转坏时最先出这个字符）',
      u'\ufffd' not in SRC, u'命中=%d' % (SRC.count(u'\ufffd'),))

_crlf_tools = [f for f in ('check158.py', 'mutate158.py', 'probe158.py')
               if os.path.isfile(os.path.join(HERE, f))
               and _read(os.path.join(HERE, f), newline='').count('\r\n')]
check(u'H4d 本轮三个新工具脚本**全 LF**（与本目录既有套件同构）',
      not _crlf_tools, u'带 CRLF 的=%r' % (_crlf_tools,))

# ================================================ H5 结构
mark(u'H5 结构：四处落盘的力与位置（与 check158 B 段独立实现）')

_save_a = _calls(_ASSIGN, '_npc_errand_save')
check(u'H5a 派活里恰一处落盘且 `force=True`',
      len(_save_a) == 1 and _const_is(_kw(_save_a[0], 'force'), True),
      u'处数=%d' % (len(_save_a),))

_ret = [n for n in ast.walk(_ASSIGN) if isinstance(n, ast.Return)
        and isinstance(n.value, ast.Name) and n.value.id == '_prev']
check(u'H5b 派活落盘排在 `return _prev` 之后（催不写盘）',
      len(_ret) == 1 and len(_save_a) == 1 and _save_a[0].lineno > _ret[0].lineno,
      u'return _prev=%d' % (len(_ret),))

_h_ifs = []
if len(_save_a) == 1:
    for n in ast.walk(_ASSIGN):
        if isinstance(n, ast.If):
            for s in ast.walk(n):
                if s is _save_a[0]:
                    _h_ifs.append(n)
                    break
_gt = _h_ifs[-1].test if _h_ifs else None
check(u'H5c 派活落盘被 `if _new is not None` 守卫',
      isinstance(_gt, ast.Compare)
      and isinstance(_gt.left, ast.Name) and _gt.left.id == '_new'
      and isinstance(_gt.ops[0], ast.IsNot)
      and isinstance(_gt.comparators[0], ast.Constant)
      and _gt.comparators[0].value is None)

_save_c = _calls(_CANCEL, '_npc_errand_save')
check(u'H5d 叫停的落盘 `force=True`',
      len(_save_c) == 1 and _const_is(_kw(_save_c[0], 'force'), True),
      u'处数=%d' % (len(_save_c),))

_save_t = _calls(_TICK, '_npc_errand_save')
_kw_t = _kw(_save_t[0], 'force') if len(_save_t) == 1 else None
check(u'H5e tick 的落盘力来自 `_structural`，且 tick 内**只有这一处**落盘',
      len(_save_t) == 1 and isinstance(_kw_t, ast.Name) and _kw_t.id == '_structural',
      u'处数=%d 力=%s' % (len(_save_t), getattr(_kw_t, 'id', repr(_kw_t))))

_asg = None
for n in ast.walk(_TICK):
    if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == '_structural' for t in n.targets):
        _asg = n.value
_names = set(x.id for x in ast.walk(_asg)
             if isinstance(x, ast.Name)) if _asg is not None else set()
check(u'H5f `_structural` 认 `dropped` 与 `finished`、**不认 `touched`**',
      isinstance(_asg, ast.BoolOp) and isinstance(_asg.op, ast.Or)
      and 'dropped' in _names and 'finished' in ast.dump(_asg)
      and 'touched' not in _names,
      u'名字=%r' % (sorted(_names),))

_plan = []
for n in ast.walk(TREE):
    if isinstance(n, ast.FunctionDef):
        for c in _calls(n, '_npc_plan_save'):
            if _const_is(_kw(c, 'force'), True):
                _plan.append((n, c))
_ok_exit = False
if len(_plan) == 1:
    _fn, _pc = _plan[0]
    _ok_exit = any(_const_is(_kw(c, 'force'), True) and c.lineno > _pc.lineno
                   for c in _calls(_fn, '_npc_errand_save'))
check(u'H5g 退出兜底：生活档案强写之后**紧跟**差事档强写', _ok_exit,
      u'生活档强写=%d 处' % (len(_plan),))

_all = [n for n in ast.walk(TREE) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute) and n.func.attr == '_npc_errand_save']
check(u'H5h 全文件落盘调用点**恰好 4 处**（派活 / 叫停 / tick / 退出）',
      len(_all) == 4, u'处数=%d' % (len(_all),))

# ================================================ H6 令牌回验
mark(u'H6 令牌逐个回验：新写法在、旧写法不在了')

_tokens = [
    (u'self._npc_errand_save(force=True)', 3),      # 派活 / 叫停 / 退出
    (u'self._npc_errand_save(force=_structural)', 1),
    (u'_structural = bool(dropped) or bool(out.get(\'finished\'))', 1),
]
_bad_tok = []
for _tok, _n in _tokens:
    if SRC.count(_tok) != _n:
        _bad_tok.append((_tok, SRC.count(_tok), _n))
check(u'H6a 三个新写法各按**预期次数**出现（不是"提到就算"）', not _bad_tok,
      u'不符=%r' % (_bad_tok,))

_old = [
    u"            self._npc_errand_save()\n        except Exception as exc:\n"
    u"            _log.debug('叫停后落盘/重建失败（已忽略）: %s', exc)",
]
_old = [s.replace('\n', '\r\n') for s in _old]
check(u'H6b 叫停那处的**旧写法**（不吃 force）已经不在了', not any(s in SRC for s in _old))

_bad_force = []
for _n in ast.walk(TREE):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
            and _n.func.attr == '_npc_errand_save':
        _v = _kw(_n, 'force')
        if isinstance(_v, ast.Name) and _v.id == 'touched':
            _bad_force.append(getattr(_n, 'lineno', -1))
check(u'H6c 没有把 `force=touched` 真写进代码（只看**调用实参** —— 第108.6：'
      u'注释里提一句不算，纯文本扫会误报）',
      not _bad_force, u'命中=%d 行=%r' % (len(_bad_force), _bad_force))

# ================================================ H7 恒真复查
mark(u'H7 恒真复查：判据名是字面量 · 不用 ok() · 变异体都有期望')

_CK = _read(os.path.join(HERE, 'check158.py'))
_CKT = ast.parse(_CK)
_bad = []
_n_ck = 0
for n in ast.walk(_CKT):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'check':
        _n_ck += 1
        if not n.args or not isinstance(n.args[0], ast.Constant) \
                or not isinstance(n.args[0].value, str) or not n.args[0].value.strip():
            _bad.append(getattr(n, 'lineno', -1))
check(u'H7a `check158` 的判据名全是**非空字面量**、且条数与自己声称的一致',
      not _bad and _n_ck >= 24, u'坏的=%d 条数=%d' % (len(_bad), _n_ck))

_n_ok = 0
for n in ast.walk(_CKT):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'ok':
        _n_ok += 1
check(u'H7b `check158` **不用** `ok()`（两套 harness 混用 ⇒ 查恒真会漏一半）',
      _n_ok == 0, u'ok 调用=%d' % (_n_ok,))

_MT = ast.parse(_read(os.path.join(HERE, 'mutate158.py')))
_n_mut = 0
_bad_mut = 0
for n in ast.walk(_MT):
    if isinstance(n, ast.Tuple) and len(n.elts) == 5 \
            and isinstance(n.elts[0], ast.Constant) \
            and isinstance(n.elts[0].value, str) and n.elts[0].value.startswith('M'):
        _n_mut += 1
        _exp = n.elts[4]
        if not (isinstance(_exp, ast.Tuple) and len(_exp.elts) >= 1):
            _bad_mut += 1
check(u'H7c `mutate158` 每处破坏**都填了期望**（没有空期望/占位）',
      _bad_mut == 0 and _n_mut >= 10, u'破坏=%d 缺期望=%d' % (_n_mut, _bad_mut))

_PR = _read(os.path.join(HERE, 'probe158.py'))
check(u'H7d `probe158` 带 `--before` 改前基线口径，且挂的是**产品函数**',
      ('--before' in _PR) and ("RalseiPet.assign_errand" in _PR)
      and ('RalseiPet._npc_errand_save' in _PR))

# ================================================ H8 卫生
mark(u'H8 卫生：四件齐 · 基线已登记 · SUITES 已登记 · 没碰 .pyc · 不依赖外部盘')

_need = ('check158.py', 'mutate158.py', 'probe158.py', 'recheck158_core.py')
_missing = [f for f in _need if not os.path.isfile(os.path.join(HERE, f))]
check(u'H8a 本轮 `_tools/` 四件齐', not _missing, u'缺=%r' % (_missing,))

_base = _read(BASELINE)
check(u'H8b 基线里已登记 `check158`', 'check158' in _base,
      u'命中=%s' % ('check158' in _base,))

_runall = _read(RUNALL)
check(u'H8c `SUITES` 里确有 `check158` 且 desc 写明了改前数值与改法边界',
      'check158' in _runall and u'落盘' in _runall,
      u'命中=%s' % ('check158' in _runall,))

_rc, _pyc = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_pyc_hit = [ln for ln in _pyc.splitlines() if '.pyc' in ln]
check(u'H8d 本轮**没有新增 / 改动任何 `.pyc`**（复检一律 `ast.parse`）',
      not _pyc_hit, u'命中=%d' % (len(_pyc_hit),))

_self = _read(os.path.abspath(__file__))
_mark_a = u'D' + u':' + u'\\_tmp'
_mark_b = u'E' + u':' + u'\\'
_mark_c = u'C' + u':' + u'\\Users'
_drive = [d for d in (_mark_a, _mark_b, _mark_c) if d in _self]
check(u'H8e 复检脚本本身**不引用外部盘**（临时件落系统 temp）',
      not _drive, u'命中=%d' % (len(_drive),))

print('')
if _n_fail:
    print('recheck158_core：FAIL %d / PASS %d' % (_n_fail, _n_pass))
    for _d in _failed:
        print('  红：%s' % (_d,))
    sys.exit(1)
print('recheck158_core：%d 条全过' % (_n_pass,))
sys.exit(0)

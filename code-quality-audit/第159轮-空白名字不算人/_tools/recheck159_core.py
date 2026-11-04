# -*- coding: utf-8 -*-
u"""第159轮复检：本轮改过 `main.py` **和** `modules/npc_errand.py` ⇒ 必须复检（用户铁律）。

跑：python recheck159_core.py

守这些事：
  H1   改动面：产品侧**只该动那两个文件**，未跟踪项全在本轮目录内
  H2   体积：两个文件都**没缩水**（与 `HEAD` 比，反回滚闸）· 净增有上限
  H3   语法：`main.py` / `npc_errand.py` / 本轮四个工具脚本都能 `ast.parse`
  H4   编码：全 CRLF、裸 LF = 0、无 BOM、无 U+FFFD；工具脚本全 LF
  H5   结构：四处判据都在、**两半**都在（全空白 + 首尾空白）、宿主两道在门控**之前**
  H6   令牌逐个回验（**按预期次数**，不是"提到就算"）：新写法在、旧写法不在了
  H7   恒真复查：判据名是字面量 · 不用 `ok()` · 变异体都有期望 · 探针挂产品函数
  H8   卫生：四件齐 · 基线已登记 · `SUITES` 已登记 · 没碰 `.pyc` · 脚本不依赖外部盘
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
ERRAND = os.path.join(PKG, 'modules', 'npc_errand.py')
BASELINE = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')

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
ESRC = _read(ERRAND, newline='')
ETREE = ast.parse(ESRC)
_CLSOBJ = dict((n.name, n) for n in TREE.body if isinstance(n, ast.ClassDef))


def _clsdef(tree, name):
    for n in tree.body:
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


def _func(tree, name):
    for n in tree.body:
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


def _strip_cmp(fn, name):
    u"""返回函数体里「`name` 与 `name.strip()` 相比」的 `ast.Compare` 节点。

    ★ 第160轮：只认**比较表达式**，不认缩进/换行/是否多行拼接 ——
      判据绑写法 ⇒ 语义等价的改写（拆成两个连续 `if`）会被判成破坏（假红）。
    """
    out = []
    if fn is None:
        return out
    for n in ast.walk(fn):
        if isinstance(n, ast.Compare):
            sides = [n.left] + list(n.comparators)
            has_strip = any(isinstance(x, ast.Call)
                            and isinstance(x.func, ast.Attribute)
                            and x.func.attr == 'strip' for x in sides)
            has_name = any(isinstance(x, ast.Name) and x.id == name for x in sides)
            if has_strip and has_name:
                out.append(n)
    return out


def _not_guard(fn, name):
    u"""返回「`not name` 落在 `if` 的 test 里」的那些 `ast.If` 节点。

    ★ 第160轮：与 `_strip_cmp` 分开数 —— **两半在同一个 `if` 里**只是其中一种写法，
      拆成两个连续 `if` 语义完全等价。判据只该问"两半都在不在"，不该问"长什么样"。
    """
    out = []
    if fn is None:
        return out
    for n in ast.walk(fn):
        if isinstance(n, ast.If):
            for x in ast.walk(n.test):
                if isinstance(x, ast.UnaryOp) and isinstance(x.op, ast.Not) \
                        and isinstance(x.operand, ast.Name) and x.operand.id == name:
                    out.append(n)
                    break
    return out


def _what_norm(fn):
    u"""返回「`not what.strip()` 判据 + `what = ''` 归一」的 `ast.If` 节点（不绑写法）。"""
    out = []
    if fn is None:
        return out
    for n in ast.walk(fn):
        if isinstance(n, ast.If):
            has_test = any(isinstance(x, ast.UnaryOp) and isinstance(x.op, ast.Not)
                           and isinstance(x.operand, ast.Call)
                           and isinstance(x.operand.func, ast.Attribute)
                           and x.operand.func.attr == 'strip'
                           for x in ast.walk(n.test))
            has_assign = any(isinstance(s, ast.Assign)
                             and isinstance(s.value, ast.Constant)
                             and s.value.value == ''
                             for s in ast.walk(n))
            if has_test and has_assign:
                out.append(n)
    return out



_CLS = _CLSOBJ.get('RalseiPet')
_ASSIGN = _method(_CLS, 'assign_errand')
_GIVEN_UP = _func(TREE, '_errand_given_up_add')
_E_ASSIGN = _method(_clsdef(ETREE, 'ErrandBoard'), 'assign')
_E_FROM = _method(_clsdef(ETREE, 'Errand'), 'from_dict')

# ================================================ H1 改动面
mark(u'H1 改动面：产品侧只该动 `main.py` + `npc_errand.py`')

_rc, _por = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_mod = [ln[3:] for ln in _por.splitlines() if ln[:2].strip() in ('M', 'A', 'D')]
_prod = sorted(p for p in _mod if p.startswith('ralsei_pet/'))
_ALLOWED = ('ralsei_pet/modules/npc_errand.py', 'ralsei_pet/src/main.py')
_extra = [p for p in _prod if p not in _ALLOWED]
# ★ 第160轮：这条判据**不许绑时相**。原来写的是"恰好等于那两个文件"，
#   于是一提交就变成 `[]` ⇒ 必假红（第21轮起的"判据禁回显时相量"同族）。
#   真正要守的是两件事：① 产品侧**没有第三个文件**被动过；② 那两个文件要么已提交、
#   要么就是这两处改动本身。第①条用子集判，第②条由上面的 `_mod` 全集兜住。
check(u'H1a 产品侧**没有第三个文件**被改（只可能是这两个；已提交时为空也算过）',
      not _extra, u'产品改动=%r 多出来的=%r' % (_prod, _extra))
check(u'H1b 未跟踪项**全在本轮目录内**（临时件一律落外部盘，不进工作区）',
      all(p.startswith('code-quality-audit/') for p in
          [ln[3:] for ln in _por.splitlines() if ln.startswith('??')]),
      u'未跟踪=%d' % (len([ln for ln in _por.splitlines()
                          if ln.startswith('??')]),))

# ================================================ H2 体积
mark(u'H2 体积：两个文件都**没缩水**（与 HEAD 比）· 净增有上限')

_H_LINES = {}
_H_CHARS = {}
for _p, _k in ((MAIN, 'main'), (ERRAND, 'errand')):
    _rc, _old = _git('-c', 'core.quotepath=false', 'show',
                     'HEAD:' + _p[len(ROOT) + 1:].replace('\\', '/'))
    _H_LINES[_k] = _old.count('\n')
    _H_CHARS[_k] = len(_old)

_n_main = SRC.count('\r\n')
_n_err = ESRC.count('\r\n')
check(u'H2a `main.py` **没缩水**（行数与字符数都不少于 `HEAD`），且净增 < 120 行',
      _n_main >= _H_LINES['main'] and len(SRC) >= _H_CHARS['main']
      and (_n_main - _H_LINES['main']) < 120,
      u'行数=%d（HEAD %d，%+d）字符=%d（%+d）'
      % (_n_main, _H_LINES['main'], _n_main - _H_LINES['main'],
         len(SRC), len(SRC) - _H_CHARS['main']))
check(u'H2b `npc_errand.py` **没缩水**，且净增 < 120 行（本轮只加判据，不该删东西）',
      _n_err >= _H_LINES['errand'] and len(ESRC) >= _H_CHARS['errand']
      and (_n_err - _H_LINES['errand']) < 120,
      u'行数=%d（HEAD %d，%+d）字符=%d（%+d）'
      % (_n_err, _H_LINES['errand'], _n_err - _H_LINES['errand'],
         len(ESRC), len(ESRC) - _H_CHARS['errand']))

_rc, _ns = _git('-c', 'core.quotepath=false', 'diff', '--numstat', 'HEAD', '--',
                'ralsei_pet')
_n_del = 0
for _ln in _ns.splitlines():
    _t = _ln.split('\t')
    if len(_t) >= 2 and _t[1].isdigit():
        _n_del += int(_t[1])
check(u'H2c 产品侧**删除行数极少**（只换了那两行旧判据 + 一行 `what` 归一）',
      _n_del <= 8, u'删除=%d 行' % (_n_del,))

# ================================================ H3 语法
mark(u'H3 语法：两个产品文件 + 本轮四个工具脚本都能 parse')

for _p, _label in ((MAIN, 'main.py'), (ERRAND, 'npc_errand.py')):
    _ok = True
    try:
        ast.parse(_read(_p))
    except SyntaxError as e:
        _ok = False
        print('  %s 语法错：%s 行 %s' % (_label, e, e.msg))
    check(u'H3a `%s` 语法 ok（`ast.parse`，不用 `py_compile` —— 别产 `.pyc`）'
          % (_label,), _ok)

for _f in ('check159.py', 'mutate159.py', 'probe159.py', 'recheck159_core.py'):
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

for _s, _label in ((SRC, 'main.py'), (ESRC, 'npc_errand.py')):
    _bare = _s.count('\n') - _s.count('\r\n')
    check(u'H4a `%s` 全 CRLF、**裸 LF = 0**（编辑没把换行改掉）' % (_label,),
          _bare == 0, u'裸LF=%d' % (_bare,))
    check(u'H4b `%s` 无 BOM、无 U+FFFD' % (_label,),
          not _s.startswith(u'\ufeff') and u'\ufffd' not in _s,
          u'BOM=%s FFFD=%d' % (_s.startswith(u'\ufeff'), _s.count(u'\ufffd')))

_crlf_tools = [f for f in ('check159.py', 'mutate159.py', 'probe159.py')
               if os.path.isfile(os.path.join(HERE, f))
               and _read(os.path.join(HERE, f), newline='').count('\r\n')]
check(u'H4c 本轮三个新工具脚本**全 LF**（与本目录既有套件同构）',
      not _crlf_tools, u'带 CRLF 的=%r' % (_crlf_tools,))

# ================================================ H5 结构
mark(u'H5 结构：四处判据都在、**两半**都在、宿主两道在门控**之前**（与 check159 B 段独立实现）')

check(u'H5a 宿主 `assign_errand` 的 `npc_id` 判据含"首尾空白"那一半',
      bool(_strip_cmp(_ASSIGN, 'npc_id')),
      u'行=%r' % ([n.lineno for n in _strip_cmp(_ASSIGN, 'npc_id')],))
check(u'H5b 宿主 `assign_errand` 的 `dest_scene` 判据同上',
      bool(_strip_cmp(_ASSIGN, 'dest_scene')),
      u'行=%r' % ([n.lineno for n in _strip_cmp(_ASSIGN, 'dest_scene')],))

_gate = _calls(_ASSIGN, '_npc_errand_gate')
_id_l = [n.lineno for n in _strip_cmp(_ASSIGN, 'npc_id')]
_dest_l = [n.lineno for n in _strip_cmp(_ASSIGN, 'dest_scene')]
check(u'H5c 宿主那两道闸**都排在** `_npc_errand_gate` 之前（脏参数不问路），且门控只调一处',
      len(_gate) == 1 and bool(_id_l) and bool(_dest_l)
      and max(_id_l) < _gate[0].lineno and max(_dest_l) < _gate[0].lineno,
      u'id行=%r 地点行=%r 门控行=%s'
      % (_id_l, _dest_l, _gate[0].lineno if _gate else u'无'))

check(u'H5d 模块级 `_errand_given_up_add` 也有 `npc_id` 判据（欠账表不许多一个看不见的槽）',
      bool(_strip_cmp(_GIVEN_UP, 'npc_id')),
      u'行=%r' % ([n.lineno for n in _strip_cmp(_GIVEN_UP, 'npc_id')],))

check(u'H5e 机制层 `ErrandBoard.assign` 的 id 与地点判据都含"首尾空白"',
      bool(_strip_cmp(_E_ASSIGN, 'npc_id'))
      and bool(_strip_cmp(_E_ASSIGN, 'dest_scene')),
      u'id=%d 处 地点=%d 处' % (len(_strip_cmp(_E_ASSIGN, 'npc_id')),
                            len(_strip_cmp(_E_ASSIGN, 'dest_scene'))))
check(u'H5f `Errand.from_dict` 的 id 与地点判据同样含"首尾空白"（老档幽灵才挡得住）',
      bool(_strip_cmp(_E_FROM, 'npc_id'))
      and bool(_strip_cmp(_E_FROM, 'dest_scene')),
      u'id=%d 处 地点=%d 处' % (len(_strip_cmp(_E_FROM, 'npc_id')),
                            len(_strip_cmp(_E_FROM, 'dest_scene'))))

# ★★★ 第160轮：「两半都在」**只问在不在，不问写法**。
#   第159轮这里写的是"同一个 `if` 里既 `not x` 又 strip 比较" ⇒ 判据绑了 if 的形状，
#   而下面这段**语义完全等价**的代码会被判成"缺一半"（`probe160 --before` 实测 H5g 红）：
#       if not isinstance(npc_id, str) or not npc_id: return None
#       if npc_id != npc_id.strip():                 return None
#   ⇒ 判据过窄=误报（第107轮教训同族）。改成按节点分别找：两半各自在同函数内出现即可。
_bad_half = []
for _fn, _name in ((_ASSIGN, 'npc_id'), (_ASSIGN, 'dest_scene'),
                   (_E_ASSIGN, 'npc_id'), (_E_ASSIGN, 'dest_scene'),
                   (_E_FROM, 'npc_id'), (_E_FROM, 'dest_scene'),
                   (_GIVEN_UP, 'npc_id')):
    if not _strip_cmp(_fn, _name) or not _not_guard(_fn, _name):
        _bad_half.append(_name)
check(u'H5g 判据**两半都在**：既挡空串（`not x`），又挡首尾空白（`x != x.strip()`）'
      u'—— 只问在不在，不问是否挤在同一个 `if` 里（绑写法会假红）',
      not _bad_half, u'缺一半=%r' % (_bad_half,))

# ================================================ H6 令牌回验
mark(u'H6 令牌回验：新判据在、旧写法不在了（**按 AST 数，不按文本片段**）')

# ★★ 第160轮：原来是按"多行拼接的文本片段"计数（`if not isinstance(npc_id, str) or
#   not npc_id \` + 续行）。语义等价的改写一拆段就不命中 ⇒ 假红（`probe160 --before`
#   实测 H6a 红）。改成数 `ast.Compare` 节点：问的是"有几处这样的判据"，不是"长什么样"。
_n_main_id = len(_strip_cmp(_ASSIGN, 'npc_id')) + len(_strip_cmp(_GIVEN_UP, 'npc_id'))
_n_main_dest = len(_strip_cmp(_ASSIGN, 'dest_scene'))
check(u'H6a `main.py` 里 `npc_id` 的 strip 比较**恰好 2 处**（宿主 + 欠账表）、'
      u'`dest_scene` 恰好 1 处（数 AST 节点，不绑缩进/换行）',
      _n_main_id == 2 and _n_main_dest == 1,
      u'id=%d 地点=%d' % (_n_main_id, _n_main_dest))

_n_e_id = len(_strip_cmp(_E_ASSIGN, 'npc_id')) + len(_strip_cmp(_E_FROM, 'npc_id'))
_n_e_dest = (len(_strip_cmp(_E_ASSIGN, 'dest_scene'))
             + len(_strip_cmp(_E_FROM, 'dest_scene')))
_n_e_what = len(_what_norm(_E_ASSIGN)) + len(_what_norm(_E_FROM))
check(u'H6b `npc_errand.py` 里 id / 地点各**恰好 2 处**、`what` 归一**恰好 2 处**'
      u'（两处都归一，漏一处就有 `\'   \'` 原样存进档）',
      _n_e_id == 2 and _n_e_dest == 2 and _n_e_what == 2,
      u'id=%d 地点=%d what=%d' % (_n_e_id, _n_e_dest, _n_e_what))

_OLD = [
    u'if not (isinstance(npc_id, str) and npc_id):',
    u'if not (isinstance(dest_scene, str) and dest_scene):',
]
_old_hit = [s for s in _OLD if s in SRC or s in ESRC]
check(u'H6c 旧的**单半判据**（`isinstance(x, str) and x`）已经不在了', not _old_hit,
      u'残留=%r' % (_old_hit,))

_rewrite = []
for _t in (TREE, ETREE):
    for _n in ast.walk(_t):
        if isinstance(_n, ast.Assign):
            for _tg in _n.targets:
                if isinstance(_tg, ast.Name) and _tg.id in ('npc_id', 'dest_scene'):
                    if isinstance(_n.value, ast.Call) \
                            and isinstance(_n.value.func, ast.Attribute) \
                            and _n.value.func.attr == 'strip':
                        _rewrite.append(_n.lineno)
check(u'H6d 全仓**没有** `npc_id = npc_id.strip()` 这种"静默改写"（只看 AST 赋值，'
      u'不扫文本 —— 第108.6：注释里提一句不算）',
      not _rewrite, u'命中=%d 行=%r' % (len(_rewrite), _rewrite))

# ================================================ H7 恒真复查
mark(u'H7 恒真复查：判据名是字面量 · 不用 ok() · 变异体都有期望 · 探针挂产品函数')

_CK = _read(os.path.join(HERE, 'check159.py'))
_CKT = ast.parse(_CK)
_bad = []
_n_ck = 0
for n in ast.walk(_CKT):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'check':
        _n_ck += 1
        if not n.args or not isinstance(n.args[0], ast.Constant) \
                or not isinstance(n.args[0].value, str) or not n.args[0].value.strip():
            _bad.append(getattr(n, 'lineno', -1))
check(u'H7a `check159` 的判据名全是**非空字面量**、且条数不少于声称的 25 条',
      not _bad and _n_ck >= 25, u'坏的=%d 条数=%d' % (len(_bad), _n_ck))

_n_ok = 0
for n in ast.walk(_CKT):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'ok':
        _n_ok += 1
check(u'H7b `check159` **不用** `ok()`（两套 harness 混用 ⇒ 查恒真会漏一半）',
      _n_ok == 0, u'ok 调用=%d' % (_n_ok,))

_MT = ast.parse(_read(os.path.join(HERE, 'mutate159.py')))
_n_mut = 0
_bad_mut = 0
for n in ast.walk(_MT):
    if isinstance(n, ast.Tuple) and len(n.elts) == 6 \
            and isinstance(n.elts[0], ast.Constant) \
            and isinstance(n.elts[0].value, str) and n.elts[0].value.startswith('M'):
        _n_mut += 1
        _exp = n.elts[5]
        if not (isinstance(_exp, ast.Tuple) and len(_exp.elts) >= 1):
            _bad_mut += 1
check(u'H7c `mutate159` 每处破坏**都填了期望**（没有空期望/占位），且不少于 8 处',
      _bad_mut == 0 and _n_mut >= 8, u'破坏=%d 缺期望=%d' % (_n_mut, _bad_mut))

_PR = _read(os.path.join(HERE, 'probe159.py'))
check(u'H7d `probe159` 带 `--before` 改前基线口径，且挂的是**产品函数**',
      ('--before' in _PR) and ('RalseiPet.assign_errand' in _PR)
      and ('ErrandBoard' in _PR or 'npc_errand' in _PR))

# ================================================ H8 卫生
mark(u'H8 卫生：四件齐 · 基线已登记 · SUITES 已登记 · 没碰 .pyc · 不依赖外部盘')

_need = ('check159.py', 'mutate159.py', 'probe159.py', 'recheck159_core.py')
_missing = [f for f in _need if not os.path.isfile(os.path.join(HERE, f))]
check(u'H8a 本轮 `_tools/` 四件齐', not _missing, u'缺=%r' % (_missing,))

_base = _read(BASELINE)
check(u'H8b 基线里已登记 `check159`', 'check159' in _base,
      u'命中=%s' % ('check159' in _base,))

_runall = _read(RUNALL)
check(u'H8c `SUITES` 里确有 `check159` 且 desc 写明了改前数值与"宁拒不改写"',
      'check159' in _runall and u'空白名字不算一个人' in _runall
      and u'宁拒不改写' in _runall,
      u'命中=%s' % ('check159' in _runall,))

_rc, _st = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_pyc_hit = [ln for ln in _st.splitlines() if '.pyc' in ln]
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
    print('recheck159_core：FAIL %d / PASS %d' % (_n_fail, _n_pass))
    for _d in _failed:
        print('  红：%s' % (_d,))
    sys.exit(1)
print('recheck159_core：%d 条全过' % (_n_pass,))
sys.exit(0)

# -*- coding: utf-8 -*-
u"""第160轮复检：这一轮**没改产品**，改的是"判据"本身 —— 所以复检换口径。

跑：python recheck160_core.py

守这些事：
  H1   产品侧**零改动**（本轮只该动工具/判据：`ralsei_pet/` 一个文件都不许变）
  H2   三个被改的判据脚本**规模没缩水**：`check159` 26 条 · `recheck159_core` 36 条 ·
       `mutate159` 9 处（其中 M9 是无害变异）· `mutate160` 5 处
  H3   语法：本轮四个脚本 + 上一轮那三个都能 `ast.parse`
  H4   编码：全 LF、无 BOM、无 U+FFFD
  H5   登记：`baseline.json` 有 `check160` · `SUITES` 有 `check160` 且 desc 写了本轮口径 ·
       `check159` 的 desc 已改成 26 条
  H6   恒真复查：`check160` 判据名是字面量 · 不用 `ok()` · `mutate160` 每处都有期望
  H7   卫生：四件齐 · 没碰 `.pyc` · 脚本不依赖外部盘
"""
import ast
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
R159 = os.path.join(ROOT, 'code-quality-audit',
                    u'第159轮-空白名字不算人', '_tools')
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


def _n_check_calls(path):
    t = ast.parse(_read(path))
    n = 0
    for x in ast.walk(t):
        if isinstance(x, ast.Call) and isinstance(x.func, ast.Name) \
                and x.func.id == 'check':
            n += 1
    return n


def _n_mutations(path):
    u"""数 MUTATIONS 里的条目。★ 两个脚本的元组长度不同：
    `mutate159` 是 6 元（多一个"目标文件"），`mutate160` 是 5 元（目标固定）。
    第一版只认 6 元 ⇒ 在 mutate160 上数出 0（判据把"写法"绑死了，自己先踩一次）。"""
    t = ast.parse(_read(path))
    n = 0
    for x in ast.walk(t):
        if isinstance(x, ast.Tuple) and len(x.elts) in (5, 6) \
                and isinstance(x.elts[0], ast.Constant) \
                and isinstance(x.elts[0].value, str) \
                and x.elts[0].value.startswith('M'):
            n += 1
    return n


# ================================================ H1 产品零改动
mark(u'H1 产品侧**零改动**（这一轮改的是判据，不是产品）')

_rc, _por = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_prod = [ln[3:] for ln in _por.splitlines()
         if ln[:2].strip() in ('M', 'A', 'D') and ln[3:].startswith('ralsei_pet/')]
check(u'H1a `ralsei_pet/` 下**一个文件都没改**（产品零改动是本轮的边界）',
      not _prod, u'产品改动=%r' % (_prod,))
check(u'H1b 未跟踪项**全在 `code-quality-audit/` 下**（临时件不进工作区）',
      all(p.startswith('code-quality-audit/') for p in
          [ln[3:] for ln in _por.splitlines() if ln.startswith('??')]),
      u'未跟踪=%d' % (len([ln for ln in _por.splitlines()
                          if ln.startswith('??')]),))

# ================================================ H2 规模
mark(u'H2 判据脚本**规模没缩水**（被改的是口径，不是把判据删了）')

_n159 = _n_check_calls(os.path.join(R159, 'check159.py'))
_n_rc = _n_check_calls(os.path.join(R159, 'recheck159_core.py'))
_n_m159 = _n_mutations(os.path.join(R159, 'mutate159.py'))
_n_m160 = _n_mutations(os.path.join(HERE, 'mutate160.py'))
_n_c160 = _n_check_calls(os.path.join(HERE, 'check160.py'))

check(u'H2a `check159` 仍有 26 条判据（第160轮补了 B8，只加不减）',
      _n159 == 26, u'条数=%d' % (_n159,))
check(u'H2b `recheck159_core` 的判据**静态条数不减**（运行期 36 条：有几条在 `for` 里'
      u'按文件展开 ⇒ 静态 30 · 运行 36，两个数都别当成对方的证明）',
      _n_rc >= 30, u'静态=%d 条（运行期应为 36）' % (_n_rc,))
check(u'H2c `mutate159` 仍是 9 处（8 破坏 + 1 无害变异 M9）',
      _n_m159 == 9, u'处数=%d' % (_n_m159,))
check(u'H2d `mutate160` 5 处破坏，`check160` 21 条判据',
      _n_m160 == 5 and _n_c160 == 21,
      u'破坏=%d 判据=%d' % (_n_m160, _n_c160))

# ================================================ H3 语法
mark(u'H3 语法：本轮四个脚本 + 上一轮那三个都能 parse')

for _f in ('probe160.py', 'check160.py', 'mutate160.py', 'recheck160_core.py'):
    _p = os.path.join(HERE, _f)
    _ok = os.path.isfile(_p)
    if _ok:
        try:
            ast.parse(_read(_p))
        except SyntaxError:
            _ok = False
    check(u'H3a %s 存在且语法 ok' % (_f,), _ok)

for _f in ('check159.py', 'mutate159.py', 'recheck159_core.py'):
    _p = os.path.join(R159, _f)
    _ok = os.path.isfile(_p)
    if _ok:
        try:
            ast.parse(_read(_p))
        except SyntaxError:
            _ok = False
    check(u'H3b （改过的）%s 语法 ok' % (_f,), _ok)

# ================================================ H4 编码
mark(u'H4 编码：全 LF · 无 BOM · 无 U+FFFD')

_bad_enc = []
for _f in ('probe160.py', 'check160.py', 'mutate160.py', 'recheck160_core.py'):
    _p = os.path.join(HERE, _f)
    if not os.path.isfile(_p):
        _bad_enc.append((_f, 'missing'))
        continue
    _s = _read(_p)
    if _s.count('\r\n') or _s.startswith(u'\ufeff') or u'\ufffd' in _s:
        _bad_enc.append((_f, 'crlf/bom/fffd'))
for _f in ('check159.py', 'mutate159.py', 'recheck159_core.py'):
    _p = os.path.join(R159, _f)
    _s = _read(_p)
    if _s.count('\r\n') or _s.startswith(u'\ufeff') or u'\ufffd' in _s:
        _bad_enc.append((_f, 'crlf/bom/fffd'))
check(u'H4a 七个判据脚本**全 LF**、无 BOM、无 U+FFFD（编辑没把换行改掉）',
      not _bad_enc, u'坏的=%r' % (_bad_enc,))

# ================================================ H5 登记
mark(u'H5 登记：基线 · SUITES · 两条 desc 都写对了')

_base = _read(BASELINE)
check(u'H5a `baseline.json` 里已登记 `check160`', 'check160' in _base,
      u'命中=%s' % ('check160' in _base,))

_runall = _read(RUNALL)
check(u'H5b `SUITES` 里确有 `check160`，且 desc 写明"判据也是被测物"',
      'check160' in _runall and u'判据也是被测物' in _runall,
      u'命中=%s' % ('check160' in _runall,))
check(u'H5c `check159` 的 desc 已改成 26 条、并记了第160轮补 B8',
      u'判据 **26/0**' in _runall and u'第160轮补' in _runall)

# ================================================ H6 恒真复查
mark(u'H6 恒真复查：判据名字面量 · 不用 ok() · 破坏都有期望')

_CK = ast.parse(_read(os.path.join(HERE, 'check160.py')))
_bad = []
_n = 0
for x in ast.walk(_CK):
    if isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id == 'check':
        _n += 1
        if not x.args or not isinstance(x.args[0], ast.Constant) \
                or not isinstance(x.args[0].value, str) or not x.args[0].value.strip():
            _bad.append(getattr(x, 'lineno', -1))
check(u'H6a `check160` 的判据名全是**非空字面量**', not _bad,
      u'坏的=%d 条数=%d' % (len(_bad), _n))

_n_ok = 0
for x in ast.walk(_CK):
    if isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id == 'ok':
        _n_ok += 1
check(u'H6b `check160` **不用** `ok()`（两套 harness 混用 ⇒ 查恒真会漏一半）',
      _n_ok == 0, u'ok 调用=%d' % (_n_ok,))

_MT = ast.parse(_read(os.path.join(HERE, 'mutate160.py')))
_bad_mut = 0
_n_mut = 0
for x in ast.walk(_MT):
    if isinstance(x, ast.Tuple) and len(x.elts) in (5, 6) \
            and isinstance(x.elts[0], ast.Constant) \
            and isinstance(x.elts[0].value, str) and x.elts[0].value.startswith('M'):
        _n_mut += 1
        _exp = x.elts[-1]
        if not (isinstance(_exp, ast.Tuple) and len(_exp.elts) >= 1):
            _bad_mut += 1
check(u'H6c `mutate160` 每处破坏**都填了期望**（没有空期望/占位）',
      _bad_mut == 0 and _n_mut == 5, u'破坏=%d 缺期望=%d' % (_n_mut, _bad_mut))

# ================================================ H7 卫生
mark(u'H7 卫生：四件齐 · 没碰 .pyc · 不依赖外部盘')

_need = ('probe160.py', 'check160.py', 'mutate160.py', 'recheck160_core.py')
_missing = [f for f in _need if not os.path.isfile(os.path.join(HERE, f))]
check(u'H7a 本轮 `_tools/` 四件齐', not _missing, u'缺=%r' % (_missing,))

_rc, _st = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_pyc = [ln for ln in _st.splitlines() if '.pyc' in ln]
check(u'H7b 本轮**没有新增 / 改动任何 `.pyc`**（复检一律 `ast.parse`）',
      not _pyc, u'命中=%d' % (len(_pyc),))

_self = _read(os.path.abspath(__file__))
_mark_a = u'D' + u':' + u'\\_tmp'
_mark_b = u'E' + u':' + u'\\'
_mark_c = u'C' + u':' + u'\\Users'
_drive = [d for d in (_mark_a, _mark_b, _mark_c) if d in _self]
check(u'H7c 复检脚本本身**不引用外部盘**（临时件落系统 temp）',
      not _drive, u'命中=%d' % (len(_drive),))

print('')
if _n_fail:
    print('recheck160_core：FAIL %d / PASS %d' % (_n_fail, _n_pass))
    for _d in _failed:
        print(u'  红：%s' % (_d,))
    sys.exit(1)
print('recheck160_core：%d 条全过' % (_n_pass,))
sys.exit(0)

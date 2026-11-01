# -*- coding: utf-8 -*-
"""第135轮核心文件复检（六项）。

复检对象：
  1. `ralsei_pet/modules/event_speech.py`（**产品改动**：`first_sentence` 的切点规则）
  2. `code-quality-audit/第135轮-事件截断吊尾巴/_tools/check135.py`（新建回归锁）
  3. `code-quality-audit/regress/run_all.py`（SUITES 追加 check135）
  4. `code-quality-audit/第135轮-事件截断吊尾巴/_evidence/report135.md`

★ 纪律（每一条都对应一次踩坑）：
  · 语法用 `ast.parse`，**不用** `py_compile`（复检不许改变被测状态、不许产 `.pyc`）。
  · 恒真判据**必须带正控制**：塞一条假 `check(..., True)`，抓不到就说明判据是摆设。
  · 令牌回验**逐条打印**，并带负控制（编造的令牌必须判"不在"）。
  · 行尾只查"不混用"：`event_speech.py` 是 CRLF（产品原样），新脚本是 LF。
  · 判据口径：断**行为/结构**，不断"我脑子里那份实现"。
"""
import ast
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
ES_PY = os.path.join(PET, 'modules', 'event_speech.py')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
CHECK = os.path.join(HERE, 'check135.py')
RUNALL = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
REPORT = os.path.join(ROUND, '_evidence', 'report135.md')
DIAG = os.path.join(EV := os.path.join(ROUND, '_evidence'), 'diag135.txt')

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, extra=''):
    cond = bool(cond)
    if cond:
        _n['p'] += 1
    else:
        _n['f'] += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else ''))


def head(t):
    print(u'')
    print(u'=' * 78)
    print(t)


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _bytes(p):
    with io.open(p, 'rb') as f:
        return f.read()


# =============================================== 1 语法
head(u'1. 语法（ast.parse，不产 .pyc）')

_src_es = _read(ES_PY)
_src_check = _read(CHECK)
_src_runall = _read(RUNALL)
_report = _read(REPORT)

for name, src in ((u'event_speech.py', _src_es), (u'check135.py', _src_check),
                  (u'run_all.py', _src_runall)):
    try:
        ast.parse(src)
        check(u'1.1 %s 可解析' % name, True, u'%d 行' % len(src.splitlines()))
    except SyntaxError as e:
        check(u'1.1 %s 可解析' % name, False, repr(e))

check(u'1.2 report135.md 非空（> 2 KB）', len(_report.encode('utf-8')) > 2000,
      u'%d 字节' % len(_report.encode('utf-8')))
check(u'1.3 diag135.txt 落盘（旧/新逐条对照的证据）',
      os.path.isfile(DIAG) and os.path.getsize(DIAG) > 500,
      u'%d 字节' % (os.path.getsize(DIAG) if os.path.isfile(DIAG) else -1))

# =============================================== 2 结构
head(u'2. 结构（三条分支都在 / 假断言已撤 / 段标题齐）')

_t_es = ast.parse(_src_es)
_fn = None
for n in ast.walk(_t_es):
    if isinstance(n, ast.FunctionDef) and n.name == 'first_sentence':
        _fn = n
        break
check(u'2.1 `first_sentence` 真在', _fn is not None)

_check_names = [n.id for n in ast.walk(_fn) if isinstance(n, ast.Name)] if _fn else []
check(u'2.2 分支①的标志在位：`_periods` 局部变量真被算出来并用上',
      u'_periods' in _check_names, u'%r' % (sorted(set(_check_names))[:12],))
check(u'2.3 分支②的标志在位：`ends[0]`（只看第一个句末标点）出现在函数里',
      any(isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
          and n.slice.value == 0 for n in (ast.walk(_fn) if _fn else [])))

# ★ 假断言必须已撤：旧 docstring 说的是"与 `start_autonomous_speech` 里那段截断**同源**"。
#   ⚠️ 第一版判据写的是"不许出现『同源』二字" ⇒ 报红，而红的是判据本身：
#      **纠错句里必须能提这件事**（"原注释写的『同源』是假断言"）⇒ 禁词法必然误伤（第133轮同型，第 6 次）。
#   改成：断**旧肯定式断言**（那个长串）不在，且**纠错措辞**在。
_doc = ast.get_docstring(_fn) or u''
check(u'2.4 旧的肯定式断言（"与 start_autonomous_speech 里那段截断同源"）已撤',
      u'里那段截断同源' not in _doc)
check(u'2.5 已改成"不是同一份实现"（纠正的措辞在）',
      u'不是同一份实现' in _doc)

for seg in (u'A. 真机回归', u'B. 修复效果', u'C. 切点规则', u'D. `MIN_FIRST_CHARS`',
            u'E. 不变量', u'F. 接线', u'G. 本套件自检'):
    check(u'2.6 段标题在位：%s' % seg, seg in _src_check)

_calls = [n for n in ast.walk(ast.parse(_src_check))
          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
          and n.func.id == 'check']
# ★ 静态 20 处 / 实跑 27 条 —— 差在 C 段那个 `for src, want, tag in CASES` 的
#   循环体（1 处 `check(`，8 条 case ⇒ 跑 8 次）。第一版这里写 `== 27` ⇒ 报红，
#   红的是**这条断言**（把运行数当成静态数）。
check(u'2.7 判据静态 20 处（C 段循环 8 条 case ⇒ 实跑 27）', len(_calls) == 20,
      u'%d 处' % len(_calls))

# =============================================== 3 编码
head(u'3. 编码（BOM / U+FFFD / 行尾不混用）')

for p in (ES_PY, CHECK, RUNALL, REPORT):
    b = _bytes(p)
    s = b.decode('utf-8')
    name = os.path.basename(p)
    check(u'3.1 %s 无 BOM' % name, not b.startswith(b'\xef\xbb\xbf'))
    check(u'3.2 %s 无 U+FFFD' % name, u'\ufffd' not in s)
    crlf = b.count(b'\r\n')
    lf = b.count(b'\n') - crlf
    check(u'3.3 %s 行尾不混用（CRLF=%d / 裸 LF=%d）' % (name, crlf, lf),
          crlf == 0 or lf == 0)
check(u'3.4 产品文件仍是 CRLF（没有把整个文件改成 LF）',
      _bytes(ES_PY).count(b'\r\n') > 100)

# =============================================== 4 恒真判据 + 正控制
head(u'4. 恒真判据复查（含正控制）')


def _find_true_calls(tree):
    out = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == 'check' and len(n.args) >= 2
                and isinstance(n.args[1], ast.Constant) and n.args[1].value is True):
            out.append(n.lineno)
    return out


_t_check = ast.parse(_src_check)
check(u'4.1 真文件里 `check(..., True)` 0 处', not _find_true_calls(_t_check),
      u'%r' % (_find_true_calls(_t_check),))
_fake = _src_check + u'\n\ncheck(u\'假的恒真判据\', True)\n'
check(u'4.2 正控制：塞一条 `check(..., True)` 必须被抓到',
      len(_find_true_calls(ast.parse(_fake))) == 1)

# ★ B 段必须"先断言不同"（A/B 纪律）
check(u'4.3 C 段有 A/B 对照（`B3` 断言新旧结果不同）', u'B3 新旧结果真的不同' in _src_check)
check(u'4.4 每条负控制都打印分母（B2 打印"旧实现下有几条吊尾巴"）',
      u'B2 A/B 先断言不同' in _src_check and u'len(_old_tail)' in _src_check)

# =============================================== 5 逐令牌回验
head(u'5. 逐令牌回验（每条回原文件 `in` 一次）')

_main_src = _read(MAIN_PY)
_tok = [
    (u'`_SENTENCE_ENDS` 常量', u'_SENTENCE_ENDS = u\'\u3002\uff01\uff1f!?\\n\'', _src_es),
    (u'`MIN_FIRST_CHARS = 6`', u'MIN_FIRST_CHARS = 6', _src_es),
    (u'`EVENT_MAX_CHARS = 24`', u'EVENT_MAX_CHARS = 24', _src_es),
    (u'main.py 调用 `first_sentence(reply, self.EVENT_SPEAK_MAX_CHARS)`',
     u'first_sentence(reply, self.EVENT_SPEAK_MAX_CHARS)', _main_src),
    (u'产品外的旧注释已改正（"不是同一份实现"）', u'不是同一份实现', _src_es),
]
for name, needle, src in _tok:
    check(u'5.1 %s 在位' % name, needle in src, u'len=%d' % len(needle))

for t in (u'6414', u'134 套件', u'你说的是坏消息吗？', u'诶？！好舒服呀。'):
    check(u'5.2 报告含 %r' % t, t in _report)

# ★ 负控制：编造的令牌必须判"不在"
for fake in (u'zzz_135_not_here', u'_SENTENCE_ENDS = u\'。\'', u'first_sentence(reply, 24)'):
    check(u'5.3 负控制：编造/过期的令牌 %r 必须判不在' % fake,
          not (fake in _src_es or fake in _main_src))

# =============================================== 6 工作区
head(u'6. 本轮只动该动的路径')

_ev_json = os.path.join(EV, 'tail135.json')
check(u'6.1 证据文件落盘', os.path.isfile(_ev_json), _ev_json)
check(u'6.2 所有读取路径都在仓库内（零外部盘）',
      all(os.path.abspath(p).startswith(ROOT + os.sep)
          for p in (ES_PY, MAIN_PY, CHECK, RUNALL, REPORT, DIAG, _ev_json)))

print(u'')
print(u'=' * 78)
print(u'recheck135_core：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)

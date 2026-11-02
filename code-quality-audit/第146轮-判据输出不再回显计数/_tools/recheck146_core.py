# -*- coding: utf-8 -*-
u"""第146轮 · 核心文件复检（改过 `check138.py` —— 它是回归锁本身，改它等于改"尺子"）。

用户口径：「以后再调整重要核心文件时一定要记得复检」——
改完不许只说"改完了"，要逐项打 PASS/FAIL 并落盘。

| 段 | 查什么 |
|---|---|
| H1 改动面 | `git diff --numstat`：只有 `check138.py`，+12/−2；删掉的 2 行逐行归类 |
| H2 语法 | 4 个文件 `ast.parse` 全过（**不产 `.pyc`**：复检不许改变被测状态） |
| H3 编码 | 无 BOM / 无 U+FFFD / EOL 与 HEAD **同构**（纯 LF，增量 == 新增行数） |
| H4 恒真复查 | `check`/`ok` **两套 harness 都看**（第125轮教训），外加 `or True` 形态 |
| H5 逐令牌回验 | 旧 token 真消失、新 token 真在位、**判定本体一字未动** |
| H6 注册与残留 | `check146` 已进 `SUITES`；探针无残留、`run_all.py` 与 HEAD 同字节 |
| H7 证据 | 冻结件 `phase138.json` 未被碰；`measure146.json` 只含稳定结论 |
| H8 工作区 | 只有预期内的改动（1 个 M + 第146轮目录下的新文件） |

★ 三件"判据自己会说谎"的事，这里都躲开了：
  ① `H4` 不用"提到的名字"判恒真 ⇒ AST 看 `Constant True`；
  ② `H5` 不用宽式 `in` 判"旧写法还在" ⇒ 先归一 EOL 再逐字比；
  ③ `H3` 不写成"裸 LF 必须 0"（那个文件 HEAD 本来就是纯 LF，写 0 会**恒真**）⇒
     写成"与 HEAD 同构 + 增量对得上"。
"""
import ast
import hashlib
import io
import json
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
AUDIT = os.path.join(ROOT, 'code-quality-audit')
CHECK138 = os.path.join(AUDIT, u'第138轮-判据输出去时相', '_tools', 'check138.py')
PHASE138 = os.path.join(AUDIT, u'第138轮-判据输出去时相', '_evidence', 'phase138.json')
MEASURE_JSON = os.path.join(ROUND, '_evidence', 'measure146.json')
RUN_ALL = os.path.join(AUDIT, 'regress', 'run_all.py')
NEW = [os.path.join(HERE, f) for f in ('measure146.py', 'check146.py', 'mutate146.py',
                                       'recheck146_core.py')]
PROBE = u'D:\\_tmp\\probe146.py'

_n_ok = 0
_n_bad = 0
_failed = []


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
    print(u'')
    print(u'=' * 78)
    print(t)


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _bytes(p):
    with io.open(p, 'rb') as f:
        return f.read()


def _sha1b(b):
    return hashlib.sha1(b).hexdigest()


def _git(*args):
    p = subprocess.Popen(['git'] + list(args), cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    o, e = p.communicate()
    return o.decode('utf-8', 'replace'), e.decode('utf-8', 'replace'), p.returncode


def _lf(t):
    u"""归一 EOL：比对文本前必做（否则 CRLF 锚点必然假阴性）。"""
    return t.replace(u'\r\n', u'\n').replace(u'\r', u'\n')


def _head_text(rel):
    o, _, rc = _git('show', 'HEAD:' + rel)
    return o if rc == 0 else u''


REL138 = u'code-quality-audit/第138轮-判据输出去时相/_tools/check138.py'

# =============================================== H1 改动面
head(u'H1 改动面：2 个跟踪文件，且删掉的每一行都能说清')
REL_RUNALL = u'code-quality-audit/regress/run_all.py'
_num, _, _ = _git('-c', 'core.quotepath=false', 'diff', '--numstat')
_rows = [ln.split(u'\t') for ln in _num.splitlines() if ln.strip()]
_rows = [r for r in _rows if len(r) == 3]
_by = {r[2]: (r[0], r[1]) for r in _rows}
# ★ 第一版这里写"恰好 1 个被改" —— 那是**登记 check146 之前**的事实。
#   登记本身就要改 `run_all.py`，所以判据必须跟着从 1 变 2，否则它守的是一个过期前提。
check(u'H1 跟踪文件里恰好 2 个被改（`check138.py` + `run_all.py` 的套件登记）',
      len(_rows) == 2, u'%d 个' % len(_rows))
check(u'H2 被改的就是那两个', sorted(_by.keys()) == sorted([REL138, REL_RUNALL]),
      u' + '.join(sorted(x.split(u'/')[-1] for x in _by.keys())))
check(u'H3 `check138.py` 改动面 +12/−2（8 行注释 + 2 条判据各拆两行）',
      _by.get(REL138) == (u'12', u'2'), u'+%s/−%s' % _by.get(REL138, (u'?', u'?')))
check(u'H3b `run_all.py` 只有新增（–0：登记不该动到别人的行）',
      _by.get(REL_RUNALL, (u'', u''))[1] == u'0',
      u'−%s' % _by.get(REL_RUNALL, (u'?', u'?'))[1])

_d, _, _ = _git('-c', 'core.quotepath=false', 'diff', '-U0', '--', REL138)
_removed = [ln[1:] for ln in _d.splitlines()
            if ln.startswith(u'-') and not ln.startswith(u'---')]
_added = [ln[1:] for ln in _d.splitlines()
          if ln.startswith(u'+') and not ln.startswith(u'+++')]
check(u'H4 删掉的 2 行**全部**是旧 extra（没有误删判定本体）',
      len(_removed) == 2
      and all(u'%d' in r and (u'_targets' in r or u'_n_calls' in r) for r in _removed),
      u'%d 行' % len(_removed))
check(u'H5 新增的 12 行 = 8 行注释 + 4 行判据（D1/D2 各拆两行，判定表达式未变）',
      len(_added) == 12
      and sum(1 for a in _added if a.lstrip().startswith(u'#')) == 8,
      u'%d 行（注释 %d）' % (len(_added),
                          sum(1 for a in _added if a.lstrip().startswith(u'#'))))

# =============================================== H2 语法
head(u'H2 语法：全部能解析（用 ast，不产 .pyc）')
for _p in [CHECK138] + NEW:
    if not os.path.exists(_p):
        check(u'H6 %s 存在' % os.path.basename(_p), False)
        continue
    # ★★ 第一版这里写的是 `check(u'...语法通过', True)` —— **恒真判据**，
    #   被本文件的 H12/H13 当场抓住（本轮第 2 次自己写恒真，第 1 次是 `E5` 的 `or True`）。
    #   改成真条件：解析出来的模块**必须真有语句**。
    _good = False
    try:
        _tree = ast.parse(_read(_p))
        _good = len(_tree.body) > 0
    except SyntaxError as e:
        check(u'H6 %s 语法通过' % os.path.basename(_p), False,
              u'line %s: %s' % (e.lineno, e.msg))
        continue
    check(u'H6 %s 语法通过（且模块非空）' % os.path.basename(_p), _good)

# =============================================== H3 编码
head(u'H3 编码：无 BOM / 无替换符 / EOL 与 HEAD 同构')
for _p in [CHECK138] + NEW:
    _b = _bytes(_p)
    _n = os.path.basename(_p)
    check(u'H7 %s 无 BOM' % _n, not _b.startswith(b'\xef\xbb\xbf'))
    check(u'H8 %s 无 U+FFFD' % _n, b'\xef\xbf\xbd' not in _b)
    try:
        _dec = _b.decode('utf-8')
        check(u'H9 %s 是合法 UTF-8' % _n, len(_dec) > 0)   # ★ 真条件，不要 `True`
    except UnicodeDecodeError:
        check(u'H9 %s 是合法 UTF-8' % _n, False)

_hb = _head_text(REL138).encode('utf-8')
_hc = _hb.count(b'\r\n')
_hl = _hb.count(b'\n') - _hc
_wb = _bytes(CHECK138)
_wc = _wb.count(b'\r\n')
_wl = _wb.count(b'\n') - _wc
check(u'H10 `check138.py` 的 EOL 风格与 HEAD 一致（CRLF 0 对 0）',
      _wc == _hc, u'工作区 CRLF=%d / HEAD CRLF=%d' % (_wc, _hc))
check(u'H11 裸 LF 净增 10 行（+12/−2，多出来的只能是本次新增的那些行）',
      _wl - _hl == 10, u'增量 %d' % (_wl - _hl))

# =============================================== H4 恒真复查
head(u'H4 恒真复查：`check` 与 `ok` **两套 harness 都看**（第125轮教训）')


def _true_args(tree):
    u"""`check`/`ok` 里把 `Constant True` 当**条件**用的地方。

    ★ `check(desc, cond, …)` 条件在 `args[1]`；`ok` 有 16 种签名，前两位都看。
    ★ 另外抓 `cond or True` 这种"看着在判其实恒真"的形态 —— 本轮我自己踩过一次。
    """
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        nm = getattr(n.func, 'id', '') or getattr(n.func, 'attr', '')
        if nm not in ('check', 'ok'):
            continue
        slots = n.args[1:2] if nm == 'check' else n.args[0:2]
        for s in slots:
            if isinstance(s, ast.Constant) and s.value is True:
                out.append((n.lineno, u'常真'))
            if isinstance(s, ast.BoolOp) and any(
                    isinstance(v, ast.Constant) and v.value is True for v in s.values):
                out.append((n.lineno, u'or True'))
    return out


_tot = 0
for _p in [CHECK138] + NEW:
    if not os.path.exists(_p):
        continue
    _bad = _true_args(ast.parse(_read(_p)))
    _tot += len(_bad)
    check(u'H12 %s 无恒真条件' % os.path.basename(_p), not _bad,
          u'%d 处 %s' % (len(_bad), _bad[:3] if _bad else u''))
check(u'H13 四份文件恒真条件合计 0 处', _tot == 0, u'%d 处' % _tot)

# =============================================== H5 逐令牌回验
head(u'H5 逐令牌回验：旧 token 真消失 / 新 token 真在位 / 判定本体没动')
_w = _lf(_read(CHECK138))
GONE = [u"u'%d \u4e2a' % len(_targets)", u"u'%d \u5904' % _n_calls"]
for _t in GONE:
    # ★★★ 第一版写的是 `_t not in _w` —— **误报**，而且是我自己造的：
    #   我把旧写法抄进注释当反例（"原来是 `u'%d 个' % len(_targets)`"），
    #   于是"禁这个短语出现"被自己的注释满足。这是"禁某短语出现⇒禁纯文本扫"的又一次复发。
    #   ⇒ 只看**非注释行**。
    _code = [ln for ln in _w.split(u'\n')
             if _t in ln and not ln.lstrip().startswith(u'#')]
    check(u'H14 旧写法已从**代码行**消失：%s' % _t, not _code,
          u'代码行 %d 处' % len(_code))
check(u'H14b 那句旧写法**只**出现在注释里（当反例登记，不是残留代码）',
      any(_t in ln for _t in GONE for ln in _w.split(u'\n')
          if ln.lstrip().startswith(u'#')))
KEPT = [u'len(_targets) >= 100', u'_n_calls >= 2000',
        u"u'\u8fc7\u9608=%s\uff08\u95f8\u95e8 \u2265100\uff09' % (len(_targets) >= 100)",
        u"u'\u8fc7\u9608=%s\uff08\u95f8\u95e8 \u22652000\uff09' % (_n_calls >= 2000)"]
for _t in KEPT:
    check(u'H15 必需 token 在位：%s' % _t[:34], _t in _w)
# 判定本体：两处 `check(` 的首两个实参**逐字**等于 HEAD 版
_hw = _lf(_head_text(REL138))
_ok_same = 0
for _d in (u"check(u'D1 \u626b\u5230\u7684\u5224\u636e\u6587\u4ef6 \u2265 100 \u4e2a', len(_targets) >= 100",
           u"check(u'D2 \u626b\u5230\u7684 `check`/`ok` \u8c03\u7528 \u2265 2000 \u5904', _n_calls >= 2000"):
    if _d in _w and _d in _hw:
        _ok_same += 1
check(u'H16 D1/D2 的 desc 与判定表达式与 HEAD **逐字相同**（只动了 extra）',
      _ok_same == 2, u'%d/2' % _ok_same)

# =============================================== H6 注册与残留
head(u'H6 注册与残留')
_ra = _read(RUN_ALL)
check(u'H17 `check146` 已登记进 `SUITES`', u"'check146'" in _ra)
# ★ H18 原来写"run_all.py 与 HEAD 同字节"—— 那查的是**探针残留**。
#   但现在这个文件本来就该变（多了 check146 一条登记），所以拆成两条真判据：
#   ① 探针痕迹不在；② 套件条数恰好 +1（不是"加了一条还顺手删了一条"）。
check(u'H18 `run_all.py` 里没有探针痕迹（`probe146` / `check146-probe` 都不在）',
      u'probe146' not in _ra and u'check146-probe' not in _ra)


def _suite_n(src):
    u"""`SUITES = [...]` 里有几个 dict 条目。"""
    t = ast.parse(src)
    for n in ast.walk(t):
        if isinstance(n, ast.Assign) and any(
                getattr(x, 'id', '') == 'SUITES' for x in n.targets):
            return sum(1 for el in getattr(n.value, 'elts', [])
                       if isinstance(el, ast.Dict))
    return -1


_n_now = _suite_n(_ra)
_n_head = _suite_n(_head_text(REL_RUNALL))
check(u'H18b `SUITES` 条目恰好 +1（只加了 check146，没顺手动别人）',
      _n_now == _n_head + 1, u'+%d' % (_n_now - _n_head))
check(u'H19 探针临时件已删（`D:\\_tmp\\probe146.py` 不存在）',
      not os.path.exists(PROBE))

# =============================================== H7 证据
head(u'H7 证据：冻结件没被碰 / 新证据只放稳定结论')
_hp = _git('show', 'HEAD:' + u'code-quality-audit/第138轮-判据输出去时相/_evidence/phase138.json')[0]
check(u'H20 冻结件 `phase138.json` 与 HEAD 同字节（历史证据不许自己变）',
      _sha1b(_hp.encode('utf-8')) == _sha1b(_bytes(PHASE138)))
if os.path.exists(MEASURE_JSON):
    _mj = json.loads(_read(MEASURE_JSON))
    _keys = sorted(_mj.keys())
    check(u'H21 `measure146.json` 只含结论键（无绝对计数 / 无行号）',
          not any(k in _keys for k in ('files_scanned', 'calls_scanned', 'lines', 'base')),
          u'%d 个键' % len(_keys))
    check(u'H22 `measure146.json` 的结论仍是"输出没动 + 数动了"',
          _mj.get('diff_lines') == 0 and _mj.get('negctl_changed') == 2
          and _mj.get('d_files') == 1 and _mj.get('family_hits') == 0)
else:
    check(u'H21 `measure146.json` 存在', False)

# =============================================== H8 工作区
head(u'H8 工作区：只有预期内的改动')
_st, _, _ = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_lines = [ln for ln in _st.splitlines() if ln.strip()]
_mod = [ln[3:] for ln in _lines if ln[:2].strip() == u'M']
_new = [ln[3:] for ln in _lines if ln[:2] == u'??']
check(u'H23 被修改的跟踪文件只有那 2 个',
      sorted(_mod) == sorted([REL138, REL_RUNALL]), u'%d 个' % len(_mod))
check(u'H24 未跟踪项只有第146轮目录（临时件不许落在工作区）',
      all(u'第146轮' in x or u'regress/_out' in x for x in _new),
      u'%d 项' % len(_new))

# =============================================== 收口
print(u'')
print(u'=' * 78)
print(u'recheck146_core：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)

# -*- coding: utf-8 -*-
u"""第147轮 · 核心文件复检（改过 `modules/event_speech.py` —— 两条链共用的截断实现）。

用户口径：「以后再调整重要核心文件时一定要记得复检」——
改完不许只说"改完了"，要逐项打 PASS/FAIL 并落盘。

| 段 | 查什么 |
|---|---|
| H1 改动面 | `git diff --numstat`：3 个跟踪文件（`event_speech.py` +46/−3、`check145.py` +8/−3、`run_all.py` +38/−0） |
| H2 语法 | 全部 `ast.parse`（**不产 `.pyc`**：复检不许改变被测状态） |
| H3 编码 | 无 BOM / 无 U+FFFD / 合法 UTF-8 / **EOL 与同目录同族一致**（这轮踩过一次，见下） |
| H4 逐行归类 | 删掉的 6 行、新增的 92 行各自能说清；判定本体没被顺手改掉 |
| H5 恒真复查 | `check`/`ok` **两套 harness 都看**（第125轮教训），外加 `or True` 形态 |
| H6 逐令牌回验 | 旧写法真消失、`_hard_cut` 三处调用在位、`_WORDY` 无 CJK、`check145 C8` 新断言在位 |
| H7 注册与残留 | `check147` 已进 `SUITES`、条目恰好 +1、无探针残留 |
| H8 证据 | 两个 JSON 只含稳定结论；`ab147` 满足**守恒式**（不是"两数相等"） |
| H9 工作区 | 只有预期内的改动（3 个 M + 第147轮目录下的新文件） |

★★★ 本轮真踩过的坑（写在这儿，省得下一个人重走）：

**① EOL 被编辑带跑。** 改完 `event_speech.py` 一量：工作区 **CRLF 1063 / 裸 LF 0**，
而 `git show HEAD:` 是 **纯 LF 1020**。同目录其他模块（`ai_driver` / `api_client` / …）
**全是纯 LF** ⇒ 说明是**我这次编辑**把整份文件的 EOL 换掉了，不是仓库惯例。
已按字节还原成 LF（转换前后做 **LF 归一 sha1 比对**，内容完全相同），
`git diff --numstat` 仍是 +46/−3 —— 说明这纯粹是 EOL，没夹带内容改动。
★ 所以 H3 的判据**不能**写成"CRLF 必须为 0"就完事（那对不同文件会假阴性），
  写成"与**同目录同族**一致 + 与 HEAD 同为 LF"。

**② 恒真判据的老账。** H5 用 AST 抓 `Constant True`，不靠"有没有提到某个名字"。
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
SRC = os.path.join(ROOT, 'ralsei_pet', 'modules', 'event_speech.py')
CHECK145 = os.path.join(AUDIT, u'第145轮-事件链英文切点', '_tools', 'check145.py')
RUN_ALL = os.path.join(AUDIT, 'regress', 'run_all.py')
MEASURE_JSON = os.path.join(ROUND, '_evidence', 'measure147.json')
AB_JSON = os.path.join(ROUND, '_evidence', 'ab147.json')
NEW = [os.path.join(HERE, f) for f in ('measure147.py', 'measure147b.py', 'check147.py',
                                       'mutate147.py', 'recheck147_core.py')]

REL_SRC = u'ralsei_pet/modules/event_speech.py'
REL_145 = u'code-quality-audit/第145轮-事件链英文切点/_tools/check145.py'
REL_RUN = u'code-quality-audit/regress/run_all.py'

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


def _lf(t):
    u"""归一 EOL：比对文本前必做（否则 CRLF 锚点必然假阴性）。"""
    return t.replace(u'\r\n', u'\n').replace(u'\r', u'\n')


def _git(*args):
    p = subprocess.Popen(['git'] + list(args), cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    o, e = p.communicate()
    return o.decode('utf-8', 'replace'), e.decode('utf-8', 'replace'), p.returncode


def _head_text(rel):
    o, _, rc = _git('show', 'HEAD:' + rel)
    return _lf(o) if rc == 0 else u''


# =============================================== H1 改动面
head(u'H1 改动面：3 个跟踪文件，改动量逐个对账')
_num, _, _ = _git('-c', 'core.quotepath=false', 'diff', '--numstat')
_rows = [ln.split(u'\t') for ln in _num.splitlines() if ln.strip()]
_rows = [r for r in _rows if len(r) == 3]
_by = dict((r[2], (r[0], r[1])) for r in _rows)
check(u'H1 跟踪文件里恰好 3 个被改（产品 1 + 契约锁 1 + 套件登记 1）',
      len(_rows) == 3, u'%d 个' % len(_rows))
check(u'H2 被改的就是那三个', sorted(_by.keys()) == sorted([REL_SRC, REL_145, REL_RUN]),
      u' + '.join(sorted(x.split(u'/')[-1] for x in _by.keys())))
check(u'H3 `event_speech.py` 改动面 +46/−3',
      _by.get(REL_SRC) == (u'46', u'3'), u'+%s/−%s' % _by.get(REL_SRC, (u'?', u'?')))
check(u'H3b `check145.py` 改动面 +8/−3（契约变更：5 行理由 + 3 行判据）',
      _by.get(REL_145) == (u'8', u'3'), u'+%s/−%s' % _by.get(REL_145, (u'?', u'?')))
check(u'H3c `run_all.py` 只增不删（−0：登记不许动到别人的行）',
      _by.get(REL_RUN, (u'', u''))[1] == u'0',
      u'−%s' % _by.get(REL_RUN, (u'?', u'?'))[1])

# =============================================== H2 语法
head(u'H2 语法：全部能解析（用 ast，不产 .pyc）')
for _p in [SRC, CHECK145, RUN_ALL] + NEW:
    _n = os.path.basename(_p)
    if not os.path.exists(_p):
        check(u'H4 %s 存在' % _n, False)
        continue
    try:
        _tree = ast.parse(_read(_p))
        _good = len(_tree.body) > 0      # ★ 真条件，不写 `True`
    except SyntaxError as e:
        check(u'H4 %s 语法通过' % _n, False, u'line %s: %s' % (e.lineno, e.msg))
        continue
    check(u'H4 %s 语法通过（且模块非空）' % _n, _good)

# =============================================== H3 编码
head(u'H3 编码：无 BOM / 无替换符 / EOL 与同族一致')
for _p in [SRC, CHECK145, RUN_ALL] + NEW:
    _b = _bytes(_p)
    _n = os.path.basename(_p)
    check(u'H5 %s 无 BOM' % _n, not _b.startswith(b'\xef\xbb\xbf'))
    check(u'H6 %s 无 U+FFFD' % _n, b'\xef\xbf\xbd' not in _b)
    try:
        _dec = _b.decode('utf-8')
        check(u'H7 %s 是合法 UTF-8' % _n, len(_dec) > 0)
    except UnicodeDecodeError:
        check(u'H7 %s 是合法 UTF-8' % _n, False)

# ★ EOL：本轮踩过（见文件头 ①）。判据 = 与同目录其他模块"同族"，不是"必须 0"。
_mod_dir = os.path.join(ROOT, 'ralsei_pet', 'modules')
_peers = [os.path.join(_mod_dir, f) for f in sorted(os.listdir(_mod_dir))
          if f.endswith('.py') and f != 'event_speech.py'][:6]
_peer_same = sum(1 for p in _peers
                 if _lf(_read(p)) == _read(p))
_src_now = _read(SRC)
check(u'H8 `event_speech.py` 是**纯 LF**（同目录 %d/%d 个模块也是纯 LF）'
      % (_peer_same, len(_peers)),
      _src_now.count(u'\r\n') == 0 and _peer_same == len(_peers),
      u'CRLF %d 处' % _src_now.count(u'\r\n'))
_hsrc = _head_text(REL_SRC)
check(u'H9 `event_speech.py` 的 EOL 与 HEAD 同族（两边都纯 LF）',
      _hsrc.count(u'\r\n') == 0)
check(u'H10 `event_speech.py` 行数 1063 = HEAD 1020 + (46 − 3)',
      len(_src_now.split(u'\n')) == len(_hsrc.split(u'\n')) + 43,
      u'%d 行（HEAD %d）' % (len(_src_now.split(u'\n')), len(_hsrc.split(u'\n'))))

# =============================================== H4 逐行归类
head(u'H4 逐行归类：删的 6 行 / 新增的 92 行')
_d_src, _, _ = _git('-c', 'core.quotepath=false', 'diff', '-U0', '--', REL_SRC)
_rm_src = [ln[1:] for ln in _d_src.splitlines()
           if ln.startswith(u'-') and not ln.startswith(u'---')]
_ad_src = [ln[1:] for ln in _d_src.splitlines()
           if ln.startswith(u'+') and not ln.startswith(u'+++')]
check(u'H11 删掉的 3 行**全是**旧硬截写法（没有误删判定本体）',
      len(_rm_src) == 3
      and all(u"t[:max_chars].rstrip(" in r for r in _rm_src),
      u'%d 行' % len(_rm_src))
check(u'H12 新增的 46 行里有 `_hard_cut` 定义 + 两个常量 + 三处调用',
      len(_ad_src) == 46
      and any(r.startswith(u'def _hard_cut(') for r in _ad_src)
      and any(r.startswith(u'_WORDY = (') for r in _ad_src)
      and any(r.startswith(u'_HARD_CUT_TAIL = ') for r in _ad_src)
      and sum(1 for r in _ad_src if u't = _hard_cut(t, max_chars)' in r) == 3,
      u'%d 行' % len(_ad_src))
_d_145, _, _ = _git('-c', 'core.quotepath=false', 'diff', '-U0', '--', REL_145)
_rm_145 = [ln[1:] for ln in _d_145.splitlines()
           if ln.startswith(u'-') and not ln.startswith(u'---')]
_ad_145 = [ln[1:] for ln in _d_145.splitlines()
           if ln.startswith(u'+') and not ln.startswith(u'+++')]
check(u'H13 `check145.py` 删掉的 3 行是 C8 旧断言（别的判据没被碰）',
      len(_rm_145) == 3
      and any(u'C8' in r for r in _rm_145)
      and any(u'endswith(u\'d\')' in r for r in _rm_145),
      u'%d 行' % len(_rm_145))
check(u'H14 `check145.py` 新增 8 行 = 5 行注释 + 3 行判据',
      len(_ad_145) == 8
      and sum(1 for r in _ad_145 if r.lstrip().startswith(u'#')) == 5,
      u'%d 行（注释 %d）' % (len(_ad_145),
                          sum(1 for r in _ad_145 if r.lstrip().startswith(u'#'))))

# =============================================== H5 恒真复查
head(u'H5 恒真复查：`check` 与 `ok` **两套 harness 都看**')


def _true_args(tree):
    u"""`check`/`ok` 里把 `Constant True` 当**条件**用、以及 `cond or True` 形态。"""
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
for _p in [SRC, CHECK145, RUN_ALL] + NEW:
    if not os.path.exists(_p):
        continue
    _bad = _true_args(ast.parse(_read(_p)))
    _tot += len(_bad)
    check(u'H15 %s 无恒真条件' % os.path.basename(_p), not _bad,
          u'%d 处 %s' % (len(_bad), _bad[:3] if _bad else u''))
check(u'H16 全部文件恒真条件合计 0 处', _tot == 0, u'%d 处' % _tot)

# =============================================== H6 逐令牌回验
head(u'H6 逐令牌回验：旧写法真消失 / 新 token 真在位')
_w = _lf(_read(SRC))
_old_tail = u"t[:max_chars].rstrip('\uff0c,\u3001\u3002\uff01\uff1f!?\uff1b;\uff1a: ')"
_code_hits = [ln for ln in _w.split(u'\n')
              if _old_tail in ln and not ln.lstrip().startswith(u'#')]
check(u'H17 旧硬截写法已从**代码行**消失（注释里当反例不算）',
      not _code_hits, u'代码行 %d 处' % len(_code_hits))
# ★★ H17b 第一版写 `_old_tail not in _w` —— **报红，而且是判据的错**：
#   产品第 48 行的**注释**里就引着这句旧写法当反例（`#   ⇒ 只能走末尾 t[:…].rstrip(…) 硬截`）。
#   这正是"禁某短语出现 ⇒ 禁纯文本扫"的第 N 次复发（第146轮 H14 已经踩过一模一样的坑）。
#   ⇒ 改成"只许出现在注释里，且恰好 1 处"。
_cmt_hits = [ln for ln in _w.split(u'\n')
             if _old_tail in ln and ln.lstrip().startswith(u'#')]
check(u'H17b 旧写法**只**出现在注释里当反例（恰好 1 处，不是残留代码）',
      len(_cmt_hits) == 1, u'注释行 %d 处' % len(_cmt_hits))
check(u'H17c 常量本身在位且内容就是那串尾巴',
      u"_HARD_CUT_TAIL = u'\uff0c,\u3001\u3002\uff01\uff1f!?\uff1b;\uff1a: '" in _w)
KEEP = [u'_HARD_CUT_TAIL = ', u'_WORDY = (', u'def _hard_cut(t, max_chars):',
        u'sp = cut.rfind(u\' \')', u'if sp > 0:',
        u'len(keep.strip()) >= MIN_FIRST_CHARS',
        u'len(keep) * 2 >= max_chars']
for _t in KEEP:
    check(u'H18 必需 token 在位：%s' % _t[:36], _t in _w)
check(u'H19 `_hard_cut` 的调用恰好 3 处（1 + 2，一处实现取代三处复刻）',
      _w.count(u't = _hard_cut(t, max_chars)') == 3,
      u'%d 处' % _w.count(u't = _hard_cut(t, max_chars)'))

# `_WORDY` 逐字符复查（不看"看着像 ASCII"，看实际码位）
_sys_path_added = sys.path[:]
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
from modules import event_speech as ES        # noqa: E402
sys.path[:] = _sys_path_added
_cjk = [c for c in ES._WORDY if u'\u4e00' <= c <= u'\u9fff']
check(u'H20 `_WORDY` 里一个 CJK 都没有（含一个就会改坏中文）',
      not _cjk, u'CJK %d 个' % len(_cjk))
check(u'H20b `_WORDY` 真的含字母与数字（不是空集/半集）',
      all(c in ES._WORDY for c in u'azAZ09'))
_seen = len(ES._WORDY) == len(set(ES._WORDY))
check(u'H20c `_WORDY` 无重复字符（重复不影响行为，但说明是手写白名单）', _seen)

# check145 的契约变更
_w145 = _lf(_read(CHECK145))
_old_c8 = u"bad.endswith(u'd')"
check(u'H21 `check145 C8` 的旧断言 `bad.endswith(u\'d\')` 已不在代码行',
      not [ln for ln in _w145.split(u'\n')
           if _old_c8 in ln and not ln.lstrip().startswith(u'#')])
check(u'H21b `check145 C8` 新断言在位，且**登记了理由**',
      u"bad == u'Well, well, well. What'" in _w145
      and u'\u7b2c147\u8f6e\u5951\u7ea6\u53d8\u66f4' in _w145)
# ★ 判定本体没被顺手改松：C1 的断言行与 HEAD **逐字相同**（本次只动了 C8）
_hw145 = _head_text(REL_145)
# ★ H21c 第一版按 `u'C1 ' in ln and u'check(' in ln` 筛 —— 捞到 **2** 行，
#   因为 C8 的 desc 里也写着"证明 C1 不是恒真"。判据过窄/过宽都是错，改成 desc 开头精确匹配。
_c1_lines = [ln for ln in _w145.split(u'\n') if u"check(u'C1 " in ln]
check(u'H21c `C1` 的断言行与 HEAD 逐字相同（本次只动 C8，没顺手松掉配对的那一半）',
      len(_c1_lines) == 1 and _c1_lines[0] in _hw145,
      u'%d 行' % len(_c1_lines))

# =============================================== H7 注册与残留
head(u'H7 注册与残留')
_ra = _lf(_read(RUN_ALL))
check(u'H22 `check147` 已登记进 `SUITES`', u"'check147'" in _ra)
check(u'H23 `run_all.py` 里没有探针痕迹', u'probe147' not in _ra)


def _suite_n(src):
    t = ast.parse(src)
    for n in ast.walk(t):
        if isinstance(n, ast.Assign) and any(
                getattr(x, 'id', '') == 'SUITES' for x in n.targets):
            return sum(1 for el in getattr(n.value, 'elts', [])
                       if isinstance(el, ast.Dict))
    return -1


_n_now = _suite_n(_ra)
_n_head = _suite_n(_head_text(REL_RUN))
check(u'H24 `SUITES` 条目恰好 +1（只加了 check147，没顺手动别人）',
      _n_now == _n_head + 1, u'+%d（%d → %d）' % (_n_now - _n_head, _n_head, _n_now))
# ★ H25 第一版的 token 写成 `'存半个预算'`（手滑），原文是"留下 ≥ 半个预算" ⇒ 恒假报红。
check(u'H25 `check147` 的 `desc` 写进了本轮三个关键事实（`isalnum` / 半个预算 / 151·57 条）',
      all(t in _ra for t in (u'isalnum', u'\u534a\u4e2a\u9884\u7b97', u'151 / 57')))
# ★ H26 第一版写成 `... or True` —— **恒真**，被 H16 当场抓住（本轮又自己写了一次）。
#   换成真条件：`_tools/` 里没有编译产物与备份残留（复检用 ast，不许产 .pyc）。
_junk = [f for f in sorted(os.listdir(HERE))
         if f.endswith((u'.pyc', u'.bak', u'~')) or f.endswith(u'.orig')]
check(u'H26 `_tools/` 里没有 `.pyc` / `.bak` / `~` 残留', not _junk,
      u'%s' % (_junk or u'无'))

# =============================================== H8 证据
head(u'H8 证据：只含稳定结论，且守恒式成立')
_mj = json.loads(_read(MEASURE_JSON))
check(u'H27 `measure147.json` 有两条链的实测块',
      all(k in _mj for k in ('event24', 'auto40')),
      u'键：%s' % u', '.join(sorted(_mj.keys())[:6]))
_badkeys = [k for k in _mj.keys() if k in ('timestamp', 'mtime', 'elapsed', 'line')]
check(u'H28 `measure147.json` 不含时相量（时间戳/耗时/行号）', not _badkeys,
      u'%s' % (_badkeys or u'无'))
_ab = json.loads(_read(AB_JSON))
_cons = 0
for _k, _m in ((u'event24', 24), (u'auto40', 40)):
    _b = _ab.get(_k, {})
    if _b.get('midword_old_en', -1) - _b.get('midword_new_en', -2) == _b.get('en_changed', -3):
        _cons += 1
check(u'H29 `ab147` 满足守恒式：`旧切词中 − 仍切词中 == 英文改动数`（两条链）',
      _cons == 2,
      u'；'.join(u'%s %d−%d vs %d' % (k, _ab[k]['midword_old_en'],
                                     _ab[k]['midword_new_en'], _ab[k]['en_changed'])
                for k in ('event24', 'auto40')))
check(u'H30 `ab147` 的中文改动**违规 0**（合法的那类才是"该改的"）',
      _ab['event24']['zh_changed_illegal'] == 0
      and _ab['auto40']['zh_changed_illegal'] == 0,
      u'illegal %d / %d' % (_ab['event24']['zh_changed_illegal'],
                            _ab['auto40']['zh_changed_illegal']))
check(u'H30b `ab147` 里合法改动 + 违规改动 == 中文总改动（分类不漏）',
      all(_ab[k]['zh_changed_legal'] + _ab[k]['zh_changed_illegal']
          == _ab[k]['zh_changed'] for k in ('event24', 'auto40')))
check(u'H31 负控制成对：旧形状 False / 新形状 True（A/B 有鉴别力）',
      _ab.get('negctl_old_shape') is False and _ab.get('negctl_new_shape') is True)

# =============================================== H9 工作区
head(u'H9 工作区：只有预期内的改动')
_st, _, _ = _git('-c', 'core.quotepath=false', 'status', '--porcelain')
_lines = [ln for ln in _st.splitlines() if ln.strip()]
_mod = [ln[3:] for ln in _lines if ln[:2].strip() == u'M']
_new = [ln[3:] for ln in _lines if ln[:2] == u'??']
check(u'H32 被修改的跟踪文件只有那 3 个',
      sorted(_mod) == sorted([REL_SRC, REL_145, REL_RUN]), u'%d 个' % len(_mod))
check(u'H33 未跟踪项只有第147轮目录（临时件不许落在工作区）',
      all(u'第147轮' in x or u'regress/_out' in x for x in _new),
      u'%d 项' % len(_new))

# =============================================== 收口
print(u'')
print(u'=' * 78)
print(u'recheck147_core：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)

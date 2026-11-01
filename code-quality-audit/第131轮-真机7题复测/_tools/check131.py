# -*- coding: utf-8 -*-
u"""第131轮回归锁：**真机 7 题复测**的方法学与证据不许再退化。

## 这一轮干什么

第130轮把第115轮丢在 worktree 里的人设四节取回来了
（「我是什么」/「他说话的时候，先把他的事接住」/「他说要去一个地方的时候」/「我想起来的事」），
但报告 §7 第 3 条明写着**真机没复测**。本轮补这一刀：
同一模型、同一批 7 题、同一段尾部，只变 system 里的人设正文 —— 比的是"那四节在不在"。

两臂：
  before = `git show edae364^:ralsei_pet/assets/ralsei_persona.md`（7 节 / 3,606 字符）
  after  = 磁盘现值（11 节 / 4,494 字符）

## 本套件守什么（零 Qt / 零网络 / 零外部盘）

A 判读旗标   —— 六个"该出现/不该出现"的旗标，正负控制成对；
                负控制必须**真落进被测分支**（如 `confab` 的负控里"豆豆"与 ADMIT 同时在场，
                否则 False 可能只是"没提到豆豆"，属于假绿）
B 证据形状   —— 42 条记录的格数/分母/无错误/回复非空；两臂的人设差正好是**那四节**
C 探针自检   —— `flags()` 复用第115轮的 `extra_flags`（**判据只有一份**）、
                基线来自 `git show` 而不是手抄、回复来自 HTTP 响应而不是常量
D 自检       —— AST 查恒真判据 / 分母 / 零外部盘 / 夹具规模

## 纪律

`print('[PASS] %s')` 字面量；判据名不自带标记；**不把结论写成判据**
（真机输出会变，写"after 一定赢"就是恒真/恒假的定时炸弹，方向性结论留在报告里）。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
PROBE = os.path.join(HERE, 'probe131_live7.py')
JSONL = os.path.join(EV, 'live7_131.jsonl')
SUMMARY = os.path.join(EV, 'live7_131_summary.json')
SNAP = os.path.join(EV, 'persona_before130.md')
PERSONA = os.path.join(ROOT, 'ralsei_pet', 'assets', 'ralsei_persona.md')

if HERE not in sys.path:
    sys.path.insert(0, HERE)
import probe131_live7 as P                                  # noqa: E402

FOUR = ('我是什么', '他说话的时候，先把他的事接住',
        '他说要去一个地方的时候', '我想起来的事')

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


def _sections(t):
    """人设里的 `—— 小节名 ——` 行。

    ★ 判据自纠：第一版写成 `s.endswith(' ——')`，于是
      `—— 我知道的世界（初始记忆）——`（结尾是 `）——`，没有空格）被漏掉 ——
      11 节被数成 10 节，而当时**还显示全绿**（因为只断言"四节在不在"）。
      这跟第130轮 `apply130_persona_fix.split_sections()` 栽的是同一个坑：
      **格式化判据绑死了一种排版**。改用正则取首尾破折号之间的内容。
    """
    import re as _re
    pat = _re.compile(u'^——\\s*(.+?)\\s*——$')
    out = []
    for line in t.splitlines():
        m = pat.match(line.strip())
        if m:
            out.append(m.group(1).strip())
    return out


# =============================================== A. 判读旗标（正负控制成对）
head(u'A. 判读旗标：正负控制成对，负控制必须真落进被测分支')

FIX = [
    # (题, 回复, 旗标名, 期望)
    (u'Q5', u'别放弃啊，继续努力就好了', u'vague', True),
    (u'Q5', u'城堡镇啊，我认得路，走不走得开我去看看', u'vague', False),
    (u'Q5', u'城堡镇我当然认得，拐过去就是喷泉', u'place', True),
    (u'Q5', u'那我们动身吧，路上慢点儿', u'place', False),
    (u'Q6', u'对，豆豆！它每天都来', u'confab', True),
    (u'Q6', u'名字我真记不清了……是不是豆豆来着？', u'confab', False),
    (u'Q7', u'我毕竟是从游戏里来的嘛，不过日子是真的', u'role_ack', True),
    (u'Q7', u'你说的是坏消息吧…那件事具体是怎么样的？', u'role_ack', False),
]
check(u'A0 分母闸：夹具清单非空', len(FIX) > 0, u'n=%d' % len(FIX))

for qid, reply, field, want in FIX:
    got = bool(P.flags(reply, qid).get(field))
    check(u'A 旗标 %-10s 期望 %-5s 实测 %-5s ← %s'
          % (field, want, got, reply[:18]),
          got == want)

# ★ 负控制"真的落进被测分支"：confab 的负控里两个条件都在场，
#   所以 False 只可能来自 admit 那一支生效，不可能是"没提到豆豆"的空跑。
_neg = u'名字我真记不清了……是不是豆豆来着？'
_ex = P.flags(_neg, u'Q6')
check(u'A9 负控制非空跑：confab 的负控里「豆豆」在场且 ADMIT 为真',
      (u'豆豆' in _neg) and bool(_ex.get('admit')) and not _ex.get('confab'))

# ★ A/B 先断言"输入不同 ⇒ 输出不同"（否则这两个旗标可能是同一个函数）
_ab_same = P.flags(u'城堡镇我认得路', u'Q5')['place'] == \
    P.flags(u'那我们动身吧', u'Q5')['place']
check(u'A10 A/B 先断言：place 的两条夹具输入不同、判定结果也不同', not _ab_same)

# ★ 题外话：side/pushback/admit 三个是第115轮的口径，本套件不许另写一份
check(u'A11 三个既有旗标确有值（复用 115 实现，不是本套件重写的）',
      all(k in P.flags(u'我记不清了，那边的事', u'Q6') for k in
          ('side', 'pushback', 'admit')))


# =============================================== B. 证据形状
head(u'B. 证据形状：条数 / 分母 / 两臂差异正好是那四节')

check(u'B0 证据文件都在', os.path.isfile(JSONL) and os.path.isfile(SUMMARY)
      and os.path.isfile(SNAP),
      u'jsonl=%s snap=%s' % (os.path.isfile(JSONL), os.path.isfile(SNAP)))

rows = []
if os.path.isfile(JSONL):
    with io.open(JSONL, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
summ = {}
if os.path.isfile(SUMMARY):
    summ = json.loads(_read(SUMMARY))

samples = int(summ.get('samples') or 0)
check(u'B1 记录条数 = 2 臂 × 7 题 × 采样数', len(rows) == 2 * 7 * samples,
      u'rows=%d samples=%d 期望 %d' % (len(rows), samples, 2 * 7 * samples))
check(u'B2 summary 自陈条数与实际一致', int(summ.get('n_rows') or -1) == len(rows),
      u'summary=%s 实际=%d' % (summ.get('n_rows'), len(rows)))
check(u'B3 没有 error 记录', not any(r.get('error') for r in rows),
      u'%r' % ([r.get('error') for r in rows if r.get('error')][:2],))
check(u'B4 没有空回复', all((r.get('reply') or '').strip() for r in rows),
      u'空=%d' % sum(1 for r in rows if not (r.get('reply') or '').strip()))

# 分母闸：每一格都必须真有 samples 条
_cells = {}
for r in rows:
    _cells.setdefault((r['arm'], r['qid']), 0)
    _cells[(r['arm'], r['qid'])] += 1
check(u'B5 分母闸：每臂每题都满 %d 条（14 格）' % samples,
      len(_cells) == 14 and all(v == samples for v in _cells.values()),
      u'格数=%d 最小=%d' % (len(_cells), min(_cells.values()) if _cells else 0))

# 同一个问题文本，两臂必须逐字相同（否则比的不是人设）
_q_ok = True
for qid in sorted(set(r['qid'] for r in rows)):
    qs = set(r['q'] for r in rows if r['qid'] == qid)
    if len(qs) != 1:
        _q_ok = False
check(u'B6 同一题在两臂里问的是同一句话（唯一变量只有人设）', _q_ok)

check(u'B7 两臂人设体积不同，且 before 更小（否则 A/B 无意义）',
      0 < int(summ.get('persona_before_chars') or 0)
      < int(summ.get('persona_after_chars') or 0),
      u'before=%s after=%s' % (summ.get('persona_before_chars'),
                               summ.get('persona_after_chars')))

# ★ 最要紧的一条：两臂的差异**正好是那四节**，不是别的
_before_secs = _sections(_read(SNAP))
_after_secs = _sections(_read(PERSONA))
check(u'B8 快照（before）里四节都不在',
      all(s not in _before_secs for s in FOUR),
      u'before 节数=%d' % len(_before_secs))
check(u'B9 现值（after）里四节都在',
      all(s in _after_secs for s in FOUR),
      u'after 节数=%d' % len(_after_secs))
check(u'B10 两臂差的正是这四节（after − before == 四节）',
      sorted(set(_after_secs) - set(_before_secs)) == sorted(FOUR)
      and not (set(_before_secs) - set(_after_secs)),
      u'多出=%r 少了=%r' % (sorted(set(_after_secs) - set(_before_secs)),
                            sorted(set(_before_secs) - set(_after_secs))))

# 计数不许比样本数还大（计数逻辑坏了会静默"看起来更好"）
_bad_cnt = []
for arm, per in (summ.get('summary') or {}).items():
    for qid, cell in per.items():
        n = cell.get('n') or 0
        for f, v in (cell.get('flags') or {}).items():
            if v > n:
                _bad_cnt.append((arm, qid, f, v, n))
check(u'B11 每格旗标计数 ≤ 该格样本数', not _bad_cnt, u'%r' % (_bad_cnt[:3],))


# =============================================== C. 探针自检（AST）
head(u'C. 探针自检：判据只有一份 / 基线来自 git / 回复来自响应')

_tree = ast.parse(_read(PROBE))


def _func(name):
    for node in ast.walk(_tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


_flags_fn = _func('flags')
_calls_ab = []
if _flags_fn is not None:
    for node in ast.walk(_flags_fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == 'extra_flags' and getattr(node.func.value, 'id', '') == 'AB':
                _calls_ab.append(node.lineno)
check(u'C1 flags() 复用 probe115ab.extra_flags（side/pushback/admit 只一份实现）',
      bool(_calls_ab), u'行号=%r' % (_calls_ab,))

_pb = _func('persona_before')
_has_git = False
if _pb is not None:
    for node in ast.walk(_pb):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and 'git show' in node.value:
            _has_git = True
check(u'C2 基线来自 `git show`（不是凭记忆重敲的"大概那一版"）', _has_git)

_oc = _func('one_call')
_msg_from_resp = False
if _oc is not None:
    # ★ 判据自纠：第一版只认 `msg = <Call>`，而产品代码写的是
    #   `msg = (r.get('message') or {}).get('content', '') or ''`
    #   ⇒ 右值是 `BoolOp`，直接判 Call 永远抓不到（这条判据当时报红是**判据的错**）。
    #   改成：先定位 `msg = ...` 这条赋值，再在它的右值子树里找 `.get('content'...)`。
    for node in ast.walk(_oc):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and getattr(node.targets[0], 'id', '') == 'msg':
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                        and sub.func.attr == 'get' and sub.args \
                        and isinstance(sub.args[0], ast.Constant) \
                        and sub.args[0].value == 'content':
                    _msg_from_resp = True
check(u'C3 回复取自 HTTP 响应（`msg = …get("content")`），不是常量', _msg_from_resp)


# =============================================== D. 自检
head(u'D. 自检（恒真判据 / 分母 / 零外部盘）')

_self = ast.parse(_read(os.path.abspath(__file__)))
_true_bad = []
for node in ast.walk(_self):
    if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'check' \
            and len(node.args) >= 2:
        a = node.args[1]
        if isinstance(a, ast.Constant) and a.value is True:
            _true_bad.append(node.lineno)
check(u'D1 没有 `check(..., True)` 这种恒真判据', not _true_bad, u'%r' % (_true_bad,))

check(u'D2 判据数 ≥ 20（分母非空）', _n['p'] + _n['f'] >= 20,
      u'实际 %d' % (_n['p'] + _n['f']))

_bad_drive = []
for _p in (os.path.abspath(__file__), PROBE):
    _s = _read(_p)
    # 盘符用 chr 拼，别写字面量 —— 否则判据会命中它自己的说明文字
    for _ch in (68, 69):
        for _sep in (chr(58) + chr(92), chr(58) + chr(47)):
            if (chr(_ch) + _sep) in _s:
                _bad_drive.append((os.path.basename(_p), chr(_ch) + _sep))
check(u'D3 零外部盘：本文件与探针里没有盘符路径', not _bad_drive,
      u'' if not _bad_drive else u'%r' % (_bad_drive,))

check(u'D4 夹具规模在位（%d 条，覆盖 3 个旗标 × 正负控制）' % len(FIX),
      len(FIX) == 8)

check(u'D5 产品人设读到了（非空且节数 ≥ 10）',
      len(_read(PERSONA)) > 3000 and len(_after_secs) >= 10,
      u'字符=%d 节=%d' % (len(_read(PERSONA)), len(_after_secs)))

print(u'')
print(u'=' * 78)
print(u'check131：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)

# -*- coding: utf-8 -*-
"""第199轮回归锁 · **人设口癖补齐**（70 份里实际动 64 份 + 15 处强化语）

用户口径
--------
    「11-14 四条」里的第一条：口癖要**偶尔**，不是每轮都交作业（§191.1）。
    第189轮b 只改了 6 人 17 处；这一轮把剩下的补齐。

改法不是我的口味，是 189b/189d 的实测结论
------------------------------------------
  · 只加「偶尔」没用 ⇒ 必须动**强化语**（标志性 / 每句 / 总是 / 这是你的本能）
  · 条件式限频在"条件恒真"时无效 ⇒ 用**绝对频率**（十次里三四次）
  · 压一个 marker 会把同槽位另一个顶上来 ⇒ **按槽位整体限**
  · 补 **2 条**不含口癖的中性正例即可改风格（2 条 > 6 条，§192.9 三臂实测）

它守什么
--------
A 改动面    —— 15 处、每条都是"绝对频率/行为描述"而不是"新禁令"；正例池不含口癖
B 落盘结果  —— 64 份各 2 条、12 份 0 条；行数只许 0/+2；无拼接事故；尾块未动
C 内容不丢  —— 被改人设的英文台词**一个不删**（check113g C3 的同一条命）；节结构不变
D 幂等      —— 施工脚本第二遍必须 0 改动；正例选取可复现
E 自检      —— 判据条数、判据名不带计数标记、无恒真判据 + 负控制

★ 为什么不直接用词表统计"强化语少了多少"当主判据：
  60 条词表命中里**大部分根本不是口癖**（`kris` 的"几乎不说话"是核心设定、
  `ut_gaster` 的"我一直在看着"是台词）。拿它当验收会把"改对了"判成"改少了"。
  这里只用它做**逐条性质的**判断（某一行改编后不再命中），不用它做总量指标。
"""
from __future__ import print_function

import ast
import hashlib
import io
import json
import os
import re
import sys
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PER = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')
#: ★ 基准不是"另存一份人设"（1.4 MB 重复正文，且备份不该进仓库），
#:   而是 `baseline199.json` 里的**派生量**：尾块 sha / 行尾计数 / 【】节名 / 英文词集合。
#:   这四样足以复核"尾块没动、英文台词没删、节结构没变"，且只有百来 KB。
BASE = os.path.join(ROUND, '_evidence', 'baseline199.json')
sys.path.insert(0, HERE)

import apply199 as A            # noqa: E402
import survey_quirks199 as S    # noqa: E402

_n = {'p': 0, 'f': 0}
TAIL = u'【本项目补充'.encode('utf-8')

#: 「绝对频率 / 行为描述」的落点词 —— 改法必须命中其中至少一个，
#: 否则就是"加了一句新禁令"，而 113g 实测禁令类措辞会把违规率从 1/10 推到 10/10。
FREQ = (u'有时', u'偶尔', u'挑着用', u'不是每句', u'不是每句话', u'十次里',
        u'到了那儿才', u'话头到了才', u'一两轮', u'多数', u'一轮里', u'不用每轮',
        u'不是每句话', u'不是每次', u'不是每轮')


def check(name, ok, extra=u''):
    if ok:
        _n['p'] += 1
        print('[PASS] %s' % name)
    else:
        _n['f'] += 1
        print('[FAIL] %s' % name)
    if extra:
        print('       %s' % extra)


def rd(p):
    with open(p, 'rb') as f:
        return f.read()


def txt(p):
    return rd(p).decode('utf-8')


def tail_of(b):
    i = b.rfind(TAIL)
    if i < 0:
        return None
    j = b.rfind(b'\n', 0, i) + 1
    return b[j:]


NAMES = sorted(n for n in os.listdir(PER) if n.endswith('.txt'))
BASELINE = json.loads(rd(BASE).decode('utf-8'))
BF = BASELINE['files']


# ------------------------------------------------------------------ A 改动面
check('A1 施工表是 15 处（与"只改真口癖"的裁定一致）', len(A.EDITS) == 15,
      'EDITS=%d' % len(A.EDITS))

_bad_freq = [e[0] for e in A.EDITS if not any(w in e[3] for w in FREQ)]
check('A2 每处改写都落在"绝对频率/行为描述"上（不是新禁令）', not _bad_freq,
      '缺落点=%s' % (_bad_freq or '无'))

#: 新措辞里**不许出现**的强化语（出现就等于没改，只是换个说法）
#: ★ 必须走 `boost_hits`（带否定语境感知），不能用裸 `in`：
#:   「不是每句话都要交」里有「每句话都」，裸 `in` 会把它判成残留（第一版实测踩到）。
_bad_boost = []
for _f, _m, _o, _nw in A.EDITS:
    if S.boost_hits(_nw):
        _bad_boost.append((_f, [w for w, _c in S.boost_hits(_nw)]))
check('A3 新措辞里没有残留强化语（否定语境不算）', not _bad_boost,
      '残留=%s' % (_bad_boost or '无'))

_ex_mk = [i for i, x in enumerate(A.EX_POOL) if S.markers_of(x)]
check('A4 正例池 6 条不含任何口癖候选（否则等于换个口癖加进去）', not _ex_mk,
      '命中=%s' % (_ex_mk or '无'))

check('A5 排除名单 12 份且每份都有理由', len(A.SKIP_EX) == 12
      and all(bool(v.strip()) for v in A.SKIP_EX.values()),
      'n=%d' % len(A.SKIP_EX))

# ------------------------------------------------------------------ B 落盘结果
_t = set()
for _n2 in NAMES:
    _t.add(tail_of(rd(os.path.join(PER, _n2))))
check('B1 76 份尾块仍逐字节相同（本轮没碰尾块）', len(_t) == 1,
      'distinct=%d' % len(_t))

_tb = 0
for _n2 in NAMES:
    _h = hashlib.sha256(tail_of(rd(os.path.join(PER, _n2)))).hexdigest()
    if _h == BF[_n2]['tail_sha256']:
        _tb += 1
check('B2 尾块 sha 与改动前基线逐份相同（本轮没碰尾块）', _tb == len(NAMES),
      '%d/%d' % (_tb, len(NAMES)))

_delta = {}
for _n2 in NAMES:
    _c = rd(os.path.join(PER, _n2)).count(b'\r\n')
    _delta[_n2] = _c - BF[_n2]['crlf']
_weird = {k: v for k, v in _delta.items() if v not in (0, 2)}
check('B3 正文行数变化只允许 0（改写）或 +2（补正例）', not _weird,
      '异常=%s' % (_weird or '无'))

_dbl = [_n2 for _n2 in NAMES if u'。。' in txt(os.path.join(PER, _n2))]
check('B4 无「。。」拼接事故', not _dbl, '命中=%s' % (_dbl[:5] or '无'))

_cnt = {}
for _n2 in NAMES:
    _s = txt(os.path.join(PER, _n2))
    _cnt[_n2] = sum(1 for x in A.EX_POOL if x in _s)
check('B5 正例：64 份各 2 条、12 份 0 条、没有别的数',
      sum(1 for v in _cnt.values() if v == 2) == 64
      and sum(1 for v in _cnt.values() if v == 0) == 12
      and all(v in (0, 2) for v in _cnt.values()),
      '2条=%d 0条=%d' % (sum(1 for v in _cnt.values() if v == 2),
                         sum(1 for v in _cnt.values() if v == 0)))

_skip_bad = sorted(k for k, v in _cnt.items() if v == 0) != sorted(A.SKIP_EX)
check('B5b 0 条的正是排除名单（不是漏改）', not _skip_bad,
      '差=%s' % (sorted(set(k for k, v in _cnt.items() if v == 0)
                        ^ set(A.SKIP_EX))[:5] or '无'))

# ------------------------------------------------------------------ C 内容不丢
_ENG = re.compile(u'[A-Za-z][A-Za-z\'’\\.\\-]{2,}')
_lost = {}
for _f, _m, _o, _nw in A.EDITS:
    _now = set(_ENG.findall(txt(os.path.join(PER, _f))))
    _d = set(BF[_f]['eng']) - _now
    if _d:
        _lost[_f] = sorted(_d)[:5]
check('C1 被改的 9 份人设：英文台词一个不删（check113g C3 同一条命）', not _lost,
      '丢=%s' % (_lost or '无'))

_sec_bad = []
for _n2 in NAMES:
    _a = [ln.strip() for ln in txt(os.path.join(PER, _n2)).split(u'\r\n')
          if S.SEC_RE.match(ln.strip())]
    if _a != BF[_n2]['sections']:
        _sec_bad.append(_n2)
check('C2 76 份的【】节结构与改动前一致（没有新增/删除节）', not _sec_bad,
      '变了=%s' % (_sec_bad[:5] or '无'))

# 逐处：改完的那一行不许再命中强化语
_still = []
for _f, _m, _o, _nw in A.EDITS:
    for _ln in txt(os.path.join(PER, _f)).split(u'\r\n'):
        if _ln.startswith(u'· ' + _nw[:12]):
            if S.boost_hits(_ln):
                _still.append((_f, _nw[:14]))
check('C3 15 处改完的行里不再命中强化语词表', not _still,
      '仍命中=%s' % (_still[:4] or '无'))

# ------------------------------------------------------------------ D 幂等
_buf = io.StringIO()
with redirect_stdout(_buf):
    _ok = A.apply_edits(dry=True)
    _added, _sk, _noanchor = A.apply_ex(dry=True)
_out = _buf.getvalue()
check('D1 施工脚本第二遍 0 改动（幂等）', _ok and not _added and not _noanchor,
      'added=%d noanchor=%d' % (len(_added), len(_noanchor)))

_p = A.pick_ex('ut_sans.txt')
check('D2 正例选取可复现（同一份文件两次取到同样两条）',
      _p == A.pick_ex('ut_sans.txt') and len(_p) == 2, 'pick=%s' % _p[0][:12])

_diverse = set()
for _n2 in NAMES:
    _diverse.add(tuple(A.pick_ex(_n2)))
check('D3 正例组合不是全库同一套（避免 64 份完全雷同）', len(_diverse) >= 3,
      '不同组合=%d' % len(_diverse))

# ------------------------------------------------------------------ E 自检
_mark_p = '[' + 'PASS' + ']'
_mark_f = '[' + 'FAIL' + ']'
_own = ast.parse(rd(os.path.abspath(__file__)).decode('utf-8'))
_calls = [n for n in ast.walk(_own)
          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
          and n.func.id == 'check']
# ★ 只扫**判据名**（check 的第一个实参），不扫整份文件。
#   第一版扫全文 ⇒ 把 `check()` 里那句打印格式串也算成"自带标记"，直接报假红。
#   187 那条老账的真意是"判据名里不许出现计数标记"，因为那行会自己往 stdout 多打一个。
_names = [c.args[0].value for c in _calls
          if c.args and isinstance(c.args[0], ast.Constant)
          and isinstance(c.args[0].value, str)]
_bad_lit = [x for x in _names if _mark_p in x or _mark_f in x]
check('E1 判据名里没有自带的计数标记（防污染 run_all 计数）',
      not _bad_lit and len(_names) == len(_calls),
      '判据名=%d 命中=%d' % (len(_names), len(_bad_lit)))

_trivial = [c for c in _calls
            if len(c.args) > 1 and isinstance(c.args[1], ast.Constant)
            and c.args[1].value is True]
check('E2 无恒真判据（第二实参不许是字面量 True）', not _trivial,
      'check()=%d 恒真=%d' % (len(_calls), len(_trivial)))
check('E3 判据条数经 check() 记账（加判据时同步改这里）', len(_calls) == 21,
      'check()=%d' % len(_calls))

# 负控制：boost_hits 必须真能分开"强化语"和"否定语境"
case_hit = S.boost_hits(u'· 你总是这样说。')
case_no = S.boost_hits(u'· 但不是每句都带。')
check('E4 负控制：boost_hits 对「总是」命中、对「不是每句」不命中',
      bool(case_hit) and not case_no, 'hit=%d no=%d' % (len(case_hit), len(case_no)))

print('\n' + '=' * 70)
print('check199  结论：%d PASS / %d FAIL' % (_n['p'], _n['f']))
sys.exit(1 if _n['f'] else 0)

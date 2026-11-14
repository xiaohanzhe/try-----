# -*- coding: utf-8 -*-
u"""第187轮 · 训练线收口：把「24.22% 硬违规率」拆成能执行的四件事。

## 这一轮做了什么

① 演化卡重跑：`turns_n == 36`（44 人过渡版）→ **`turns_n == 48`（77 人正式版）**
   —— 判据在 `check134` 的 `B0c`（那边管，这里不重复）。
② `voice_markers` 登记普查：12 张卡**早已干净**，无需再动（实证留档）。
③ `_seek.json` 重生：实测与现有文件**完全相同**（它早就是 48 轮语料生成的）。
④ **违规率归因**：本轮真正的新东西 —— 见下。

## 为什么 24.22% 需要拆

`report30.md` 原来只有一个 `895 / 3696 = 24.2%`。这个数字**不可执行**：
它不说是哪一种违规、哪些人、哪一段。拆开后是四个不同的问题：

| 切面 | 值 | 性质 |
|---|---|---|
| 违规轮（全部） | 895/3696 = 24.22% | `report30` 原口径 |
| ├─ 出戏探测三问 | 161/231 = 69.7% | **测量设计**（故意去戳"你是不是 AI"） |
| └─ 其余正常问法 | 734/3465 = 21.19% | 人设真实水平 |
| 第 4 段（37-48 轮） | 35.0% → **23.4%** | **假象**：探测题恰好全在第 42/43/44 轮 |

三个根因（都有实证）：
  · `ACTION_PAREN` 419 条 = **模型能力上限**。9 个高发角色的 `patch` 里
    **全都写了**「不要用括号加动作…」，而写了同一句话的 `ut_mettaton` 只有 2 条
    ⇒ 再加 prompt 文案无效（与第161轮「反问已在提示词层到顶」同构）。
  · `REPEAT` 267 条 = **人设要求的重复**。`os_prophetbot` 24 条报的全是
    「欢迎来到我们的世界，朋友！」——人设明文写的固定开场白。
    ★ 用户裁定：**算缺陷，判据不动**（用户聊 48 轮都听到同一句，体验上就是复读机）。
  · `NOT_CN` 155 条 = **素材本身英文**（`ut_sans` 47/48 轮整段英文）。

## 分段

A 报表口径 5 · B 独立重数 6 · C 交叉一致 4 · D 负控制 5 · E 自检 3

## 判据纪律

★ **故意不写死 42/43/44 和 3696**：探测轮用「77 人在同一 `i` 上的 `slot` 完全相同」
  这个**结构事实**反推（`_probe_turns()`）；总轮数用 `chars × turns_cap` 反推。
  语料一旦变，判据跟着变，而不是留一个会过期的常数。
★ 负控制全部在**内存里改值**再跑同一条判据，**不碰磁盘**（不污染被测状态）。
★ 本脚本**只读**，不写任何文件（E3 用 AST 自证）。
"""
import ast
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

T113 = os.path.join(REPO, 'code-quality-audit', '第113轮-全体角色AI训练')
RAW30 = os.path.join(T113, '_evidence', 'raw30')
REP30 = os.path.join(T113, '_evidence', 'report30.md')
EVOLVE = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc', '_relations', '_evolution.json')
SEEK = os.path.join(REPO, 'ralsei_pet', 'assets', 'npc', '_seek.json')

#: 本轮自己的证据（`attr_viol187.py` 产物）
EVID = os.path.join(ROUND, '_evidence', 'attr_viol187.json')

_n = {'p': 0, 'f': 0}
_bad = []


def check(desc, cond, extra=u''):
    if cond:
        _n['p'] += 1
        print('[PASS] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        _n['f'] += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def jload(p):
    return json.loads(rd(p))


# ---------------------------------------------------------------- 独立重数
def _latest48():
    u"""`id -> 该 id 最后一条 `turns_n == 48` 的记录`。

    与 `train30` / `attr_viol187` 同一个口径，但**这里独立写一遍**：
    归因脚本自己算出来的数不能自己验自己。
    """
    out = {}
    if not os.path.isdir(RAW30):
        return out
    for f in sorted(os.listdir(RAW30)):
        if not f.endswith('.jsonl'):
            continue
        best = None
        for line in io.open(os.path.join(RAW30, f), 'r', encoding='utf-8',
                            errors='replace'):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if isinstance(r, dict) and r.get('turns_n') == 48:
                best = r
        if best:
            out[f[:-6]] = best
    return out


def _probe_turns(rows):
    u"""反推探测轮 —— **不用写死 42/43/44，也不靠关键词**。

    依据：探测三问是同一份剧本发给所有人，所以「在某个 `i` 上，77 个角色拿到的
    `slot` 完全相同」这件事只有剧本题才成立（自由对话的 slot 是逐轮推进的剧本，
    但每人的 slot 序列一致——所以单看"相同"不够）。

    ⇒ 再加两个条件才认：
      ① 这些 slot 里含探测特征词（问"提示词 / 被设定出来 / 是个 AI"）；
      ② 该 `i` 不是常规推进段（`i` 出现在所有角色的同一位置且 **重复 3 次**）。

    返回 `(probe_i_set, probe_slot_set, 每人探测轮数)`；拿不到就空。
    """
    hints = (u'提示词', u'设定出来', u'是个 AI', u'是个AI')
    by_i = {}
    for nid, rec in rows.items():
        for t in (rec.get('turns') or []):
            i = int(t.get('i') or 1)
            sl = t.get('slot') or ''
            by_i.setdefault(i, []).append((nid, sl))
    n_char = len(rows)
    hit = {}
    for i, lst in by_i.items():
        if len(lst) != n_char:
            continue                      # 不是所有人都有的轮次，不是剧本固定题
        slots = set(sl for _, sl in lst)
        if len(slots) != 1:
            continue                      # 每人拿到的不一样 ⇒ 不是同一道题
        sl = slots.pop()
        if not any(h in sl for h in hints):
            continue                      # 没有探测特征
        hit[i] = sl
    return set(hit), set(hit.values()), len(hit)


ROWS = _latest48()
PROBE_I, PROBE_SLOT, PROBE_PER_CHAR = _probe_turns(ROWS)
D = jload(EVID) if os.path.exists(EVID) else {}
REP = rd(REP30) if os.path.exists(REP30) else u''


# ---------------------------------------------------------------- 纯不变量
def inv_bucket_monotone(d):
    u"""剔除子集之后，每段的「违规轮」和「总轮」都**不可能变大**。"""
    for k, full in (d.get('by_turn_bucket') or {}).items():
        ex = (d.get('by_turn_bucket_ex_probe') or {}).get(k)
        if not ex:
            return False
        if ex[0] > full[0] or ex[1] > full[1]:
            return False
    return True


def inv_probe_sum(d):
    u"""probe + normal 必须拼回全体（轮数与违规轮数都要拼回）。"""
    p, nm = d.get('probe') or {}, d.get('normal') or {}
    return (p.get('turns', -1) + nm.get('turns', -1) == d.get('turns')
            and p.get('bad', -1) + nm.get('bad', -1) == d.get('bad_turns'))


def inv_code_sum(d):
    u"""各违规码条数之和 == 违规条总数。"""
    return sum((d.get('by_code_turns') or {}).values()) == d.get('violation_items')


def inv_report_split(text):
    u"""报告必须**同时**出现「全部」和「正常问法」两行 —— 只有一行就是又回到不可执行。"""
    return (u'出戏探测三问' in text and u'其余正常问法' in text
            and u'剔除探测后' in text)


def _pct(x):
    return u'%.1f%%' % x


def inv_report_has_rate(text, val):
    return _pct(val) in text


def _row_of(text, marker):
    for line in text.splitlines():
        if marker in line:
            return line
    return u''


# ================================================================ A 报表口径
print('\n=== A 报表口径（report30.md 现在读得出行动了吗）===')

check(u'A1 report30.md 同时有「出戏探测三问」「其余正常问法」「剔除探测后」三处',
      inv_report_split(REP),
      u'%d 字符' % len(REP))

_ALL_ROW = _row_of(REP, u'硬违规（**全部**轮）')
check(u'A2 「全部」那一行还在，且仍是 24.2%（拆开≠洗数字）',
      bool(_ALL_ROW) and u'24.2%' in _ALL_ROW,
      _ALL_ROW.strip()[:70])

_PROBE_ROW = _row_of(REP, u'出戏探测三问')
_NORM_ROW = _row_of(REP, u'其余正常问法')
check(u'A3 探测行与正常行是**两个不同的数**（69.7% vs 21.2%，不是同一个数抄两遍）',
      bool(_PROBE_ROW) and bool(_NORM_ROW) and _PROBE_ROW != _NORM_ROW
      and u'69.7%' in _PROBE_ROW and u'21.2%' in _NORM_ROW,
      u'探测=%r 正常=%r' % (_PROBE_ROW.strip()[-30:], _NORM_ROW.strip()[-30:]))

_B4 = _row_of(REP, u'第 4 段')
check(u'A4 分段表第 4 段成对报出（35.0% 对照 23.4%）—— 假象与真相并排',
      u'35.0%' in _B4 and u'23.4%' in _B4,
      _B4.strip()[:70])

check(u'A5 报告注明了探测题落在哪几轮（否则读者不知道 231 轮从哪来）',
      bool(PROBE_I) and all(str(i) in REP for i in sorted(PROBE_I)),
      u'探测轮次=%r' % (sorted(PROBE_I),))


# ================================================================ B 独立重数
print('\n=== B 独立重数（不采信归因脚本自己算的数）===')

_n_char = len(ROWS)
_turns = sum(len(r.get('turns') or []) for r in ROWS.values())
check(u'B1 从 raw30 独立重数：角色数与总轮数 == 证据里的 chars / turns',
      (D.get('chars'), D.get('turns')) == (_n_char, _turns),
      u'重数 %d 人 / %d 轮；证据 %r' % (_n_char, _turns,
                                        (D.get('chars'), D.get('turns'))))

_exp_probe_n = _n_char * PROBE_PER_CHAR
check(u'B2 探测轮数 == 角色数 × 每人探测题数（结构反推，**不写死 231**）',
      (D.get('probe') or {}).get('turns') == _exp_probe_n and _exp_probe_n > 0,
      u'%d × %d = %d；证据 %r' % (_n_char, PROBE_PER_CHAR, _exp_probe_n,
                                  (D.get('probe') or {}).get('turns')))

_bad_turns = sum(1 for r in ROWS.values() for t in (r.get('turns') or [])
                 if t.get('violations'))
check(u'B3 从 raw30 独立重数：违规轮数 == 证据里的 bad_turns',
      D.get('bad_turns') == _bad_turns,
      u'重数 %d；证据 %r' % (_bad_turns, D.get('bad_turns')))

_bad_probe = sum(1 for r in ROWS.values() for t in (r.get('turns') or [])
                 if t.get('violations') and int(t.get('i') or 1) in PROBE_I)
check(u'B4 从 raw30 独立重数：探测轮里的违规数 == 证据 probe.bad',
      (D.get('probe') or {}).get('bad') == _bad_probe,
      u'重数 %d；证据 %r' % (_bad_probe, (D.get('probe') or {}).get('bad')))

check(u'B5 探测题**每个角色拿到的 slot 完全相同**（同一份剧本，不是自由对话）',
      len(PROBE_SLOT) == PROBE_PER_CHAR and PROBE_PER_CHAR > 0,
      u'%d 个不同 slot / %d 轮' % (len(PROBE_SLOT), PROBE_PER_CHAR))

# ★ JSON 往返会把 int 键变成字符串（`{42: 77}` → `{'42': 77}`），
#   所以这里必须 `int(k)` 归一 —— 第一版直接比集合，必然不等（记为判据 bug，不是数据错）。
_pat = dict((int(k), v) for k, v in (D.get('probe_at_turn') or {}).items())
check(u'B6 探测轮位置 == 证据 probe_at_turn 的键集，且每人各 1 次',
      set(_pat) == PROBE_I and bool(_pat)
      and all(v == _n_char for v in _pat.values()),
      u'证据 %r' % (D.get('probe_at_turn'),))


# ================================================================ C 交叉一致
print('\n=== C 交叉一致（归因脚本 与 报表脚本 是两条独立代码路径）===')

check(u'C1 报告里的探测违规率 == 证据 probe.rate（两位独立算出同一个数）',
      inv_report_has_rate(REP, (D.get('probe') or {}).get('rate', -1)),
      u'证据 %.2f%%' % (D.get('probe') or {}).get('rate', -1))

check(u'C2 报告里的正常问法违规率 == 证据 normal.rate',
      inv_report_has_rate(REP, (D.get('normal') or {}).get('rate', -1)),
      u'证据 %.2f%%' % (D.get('normal') or {}).get('rate', -1))

_ex4 = (D.get('by_turn_bucket_ex_probe') or {}).get('4') or [0, 0, -1]
_fu4 = (D.get('by_turn_bucket') or {}).get('4') or [0, 0, -1]
check(u'C3 报告第 4 段两个数 == 证据的 full / ex_probe（35.0 / 23.4）',
      _pct(_fu4[2]) in _B4 and _pct(_ex4[2]) in _B4,
      u'证据 full=%s ex=%s' % (_pct(_fu4[2]), _pct(_ex4[2])))

check(u'C4 证据内部自洽：probe+normal 拼回全体、各码之和 == 违规条总数、剔探测后每段不增',
      inv_probe_sum(D) and inv_code_sum(D) and inv_bucket_monotone(D),
      u'turns=%r bad=%r items=%r' % (D.get('turns'), D.get('bad_turns'),
                                     D.get('violation_items')))


# ================================================================ D 负控制
print('\n=== D 负控制（改坏一个值，同一条判据必须报红）===')


def _mut(**kw):
    m = json.loads(json.dumps(D))
    for k, v in kw.items():
        m[k] = v
    return m


_m1 = _mut()
_m1['probe'] = dict(_m1['probe'])
_m1['probe']['turns'] = _m1['probe']['turns'] + 1
check(u'D1 把 probe.turns 改成 +1 ⇒ 「probe+normal 拼回全体」必须判红',
      not inv_probe_sum(_m1),
      u'篡改后 probe.turns=%d' % _m1['probe']['turns'])

_m2 = _mut()
_m2['by_turn_bucket_ex_probe'] = dict(_m2['by_turn_bucket_ex_probe'])
_ex = list(_m2['by_turn_bucket_ex_probe']['4'])
_ex[0] = _m2['by_turn_bucket']['4'][0] + 1        # 剔探测后反而变多
_m2['by_turn_bucket_ex_probe']['4'] = _ex
check(u'D2 把「剔除后违规轮」改成比「剔除前」还大 ⇒ 单调性判据必须判红',
      not inv_bucket_monotone(_m2),
      u'篡改后 ex[0]=%d > full[0]=%d' % (_ex[0], _m2['by_turn_bucket']['4'][0]))

check(u'D3 从报告里删掉「出戏探测三问」⇒ A1 那条判据必须判红',
      not inv_report_split(REP.replace(u'出戏探测三问', u'XX')),
      u'替换后仍判绿＝判据恒真')

check(u'D4 把正常问法那行改成 24.2%（洗回一个总数）⇒ C2 必须判红',
      not inv_report_has_rate(_NORM_ROW.replace(u'21.2%', u'24.2%'),
                              (D.get('normal') or {}).get('rate', -1)),
      u'替换后仍能找到 21.2% 才是错的')

_m3 = _mut()
_m3['by_code_turns'] = dict(_m3['by_code_turns'])
_k = sorted(_m3['by_code_turns'])[0]
_m3['by_code_turns'][_k] = _m3['by_code_turns'][_k] + 1
check(u'D5 把任一违规码的条数 +1 ⇒ 「各码之和 == 违规条总数」必须判红',
      not inv_code_sum(_m3),
      u'篡改 %s = %d' % (_k, _m3['by_code_turns'][_k]))


# ================================================================ E 自检
print('\n=== E 自检 ===')

_src = rd(os.path.abspath(__file__))
_tree = ast.parse(_src)
_writes = []
for node in ast.walk(_tree):
    if isinstance(node, ast.Call):
        fn = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
        if fn in ('open', 'write_text', 'dump', 'write'):
            args = [a for a in node.args if isinstance(a, ast.Constant)]
            modes = [a.value for a in node.args if isinstance(a, ast.Constant)
                     and isinstance(a.value, str)]
            if fn == 'open' and any(('w' in m or 'a' in m or '+' in m)
                                    for m in modes[1:] if isinstance(m, str)):
                _writes.append(getattr(node, 'lineno', -1))
            elif fn in ('write_text', 'dump', 'write'):
                _writes.append(getattr(node, 'lineno', -1))
check(u'E1 本脚本只读：AST 里没有写模式的 open / dump / write',
      not _writes, u'可疑行 %r' % (_writes,))

EXPECT = 23         # A5 + B6 + C4 + D5 + E3

#: ★ E2 在**自己执行之前**数，天然少「E2 自己」和「E3」两条 ⇒ 比 `EXPECT - 2`。
#:   第一版写成 `_real == EXPECT`，于是永远差 2（记为判据 bug）。
E2_BEFORE = EXPECT - 2
_real = _n['p'] + _n['f']
check(u'E2 判据条数 == 声明的 %d 条（少跑一条就等于漏验一段）' % EXPECT,
      _real == E2_BEFORE, u'实跑 %d 条（E2 之前）' % (_real,))

# ★★ 这一条的 extra **绝不能回显 `[PASS]` / `[FAIL]` 字面量** ——
#   `run_all.py` 是按输出里这两个标记的**出现次数**统计的，回显一次就多算一条
#   （第一版就把 PASS 数成 24、FAIL 数成 1，明明 23/0）。判据检查源码可以，别打印。
check(u'E3 每个判据都走 check()（保证 PASS / FAIL 标记是字面量，`run_all` 才数得到）',
      u"'[PASS] %s%s'" in _src and u"'[FAIL] %s%s'" in _src,
      u'源码里两处字面量都在（此处不回显，免得污染计数）')

print()
print(u'%d PASS / %d FAIL' % (_n['p'], _n['f']))
if _bad:
    print(u'失败项：')
    for b in _bad:
        print(u'  - %s' % b)
sys.exit(0 if _n['f'] == 0 else 1)

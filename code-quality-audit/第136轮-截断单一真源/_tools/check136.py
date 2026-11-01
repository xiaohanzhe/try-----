# -*- coding: utf-8 -*-
"""第136轮回归锁：截断规则**单一真源**（自主开口那段不再自己写一遍）。

## 病是什么

`main.start_autonomous_speech._on_reply` 里有一段**自己写的** 8 行截断：

```python
for sep in ('\\n', '。', '！', '？', '!', '?'):
    if sep in text:
        head = text.split(sep, 1)[0].strip()
        if head:
            text = head + ('' if sep == '\\n' else sep)
        break
if len(text) > 40:
    text = text[:40]
```

它和事件链的 `first_sentence()` **从来就不是同一份实现**：
sep 顺序不同（一个 `\\n` 优先、一个句号优先）、上限不同（40 vs 24）、
一个有 `MIN_FIRST_CHARS` 一个没有。原注释写的"同源"是**假断言**（第135轮已改正注释）。

## 实测后果（第136轮 `diag136.py` / `diag136c.py`）

★ 口径先说死：**84 条真实 AI 回复**（第131轮真机 42 + 第133轮事件 42）。
`diag136.py` 里跑的是 98 条 ＝ 这 84 条 + 14 条构造样本（用来覆盖边角），
下表的数是 **84 条真实语料** 上的（构造样本会把平均分拉偏，不能混着报）。

| 实现 | 吊尾巴 | 平均长度 |
|---|---|---|
| 旧内联（`for sep in (...)` + 40 字硬截） | **10 条** | 16.2 字 |
| 换成 `first_sentence(t, 40)` | 0 条 | 12.5 字（**9 条砍掉后半句**，丢了"追问一句"） |
| `fit_sentences(t, 40)`（本轮） | **0 条** | **18.6 字** |

旧内联 vs `first_sentence(t,40)`：84 条里 **20 条**不同 —— 10 条是"旧的在吊尾巴、新的不吊"（修复），
9 条是"旧的没吊、新的更短"（把第二句砍了），1 条其余。
`fit_sentences` 比 `first_sentence` 多 **33 条**不同，其中 **32 条多留了一整句以上**，平均多 **+6.2 字**。

⇒ 目标不是"合并成同一个函数"，而是"两条链各自只有一份实现、语义各自明确"：
**事件反应只要一句（24 字）** ｜ **主动搭话能说几句但必须说完整（40 字）**。

## 本套件守什么（零 Qt / 零网络 / 零外部盘）

A 单一真源（AST）：`main.py` 里那段内联没了、改调 `fit_sentences`、上限从模块 import；
  **破坏性负控制**：把内联形状写回去 ⇒ A1 必须报红
B `fit_sentences` 行为：长句群保住信息量 / 不吊尾巴 / 短文本整句 / 无标点硬截 / 只有标点返空 / 上限恒定
C 两个函数的分工：同一输入下 `fit_sentences` 一定**不短于** `first_sentence`
D 真实语料：84 条上吊尾巴 0 条、平均长度不低于旧内联（不许"修 bug 把话变少"）
E 连续句末标点：`……` / `诶？！` 不许切一半；**破坏性负控制**：停掉 `_eat_sentence_end` 必须报红
  ★★ 这条负控制的靶子必须选 `first_sentence`。第一版选的是 `fit_sentences`，
     **抓不到** —— 详见 E 段头的自纠记录与 `_evidence/diag136b2.txt`。
F 事件链没被带坏：3 条元话语泄漏的输出仍是 9 字完整句
G 自检

## 纪律

`print('[PASS] %s')` 字面量；判据名不自带标记；**判据只有一份**（一律调产品函数）；
不把"我觉得更好看"写进判据 —— 只断"完整 / 不吊尾巴 / 上限 / 单一真源"。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROUND, '_evidence')
MAIN_PY = os.path.join(PET, 'src', 'main.py')
ES_PY = os.path.join(PET, 'modules', 'event_speech.py')
LIVE131 = os.path.join(ROOT, 'code-quality-audit', '第131轮-真机7题复测',
                       '_evidence', 'live7_131.jsonl')
EV133 = os.path.join(ROOT, 'code-quality-audit', '第133轮-事件台词元话语核查',
                     '_evidence', 'event133.jsonl')

sys.path.insert(0, os.path.join(PET, 'modules'))
import event_speech as ES                                     # noqa: E402

MAX_AUTO = ES.AUTO_SPEAK_MAX_CHARS
ENDS = ES._SENTENCE_ENDS

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


def _rows(p):
    out = []
    with io.open(p, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _tail(s, limit=MAX_AUTO):
    """吊尾巴：非空、顶到上限附近、结尾不是句末标点。"""
    if not s:
        return False
    return (s[-1] not in ENDS) and len(s) >= limit - 2


def _old_inline(text, limit=40):
    """**旧内联实现的快照**（`main.start_autonomous_speech` 里那 8 行，第136轮已删）。

    ★ 它不是第二份真源：产品里已经没有这段了。留着只为 D 段能证明
      "旧实现确实在真实语料上吊了 10 条尾巴" —— 否则 D1 只是在描述一个从没坏过的实现。
    """
    if not isinstance(text, str):
        return ''
    for sep in (u'\n', u'。', u'！', u'？', u'!', u'?'):
        if sep in text:
            h = text.split(sep, 1)[0].strip()
            if h:
                text = h + (u'' if sep == u'\n' else sep)
            break
    if len(text) > limit:
        text = text[:limit]
    return text


_src_main = _read(MAIN_PY)
_t_main = ast.parse(_src_main)
_src_es = _read(ES_PY)


def _func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


# =============================================== A 单一真源
head(u'A. 单一真源：`main.py` 里那段内联截断没了，改调 `fit_sentences`')

_auto = _func(_t_main, 'start_autonomous_speech')
check(u'A0 `start_autonomous_speech` 真在', _auto is not None)

_names = [n.id for n in ast.walk(_auto) if isinstance(n, ast.Name)] if _auto else []
_attrs = [n.attr for n in ast.walk(_auto) if isinstance(n, ast.Attribute)] if _auto else []
check(u'A1 内联截断已删（函数体里不再有 `sep` 循环 / 20 行那个 magic 40）',
      (u'sep' not in _names) and (40 not in [c.value for c in
                                            (ast.walk(_auto) or [])
                                            if isinstance(c, ast.Constant)
                                            and isinstance(c.value, int)]),
      u'names 含 sep=%s' % (u'sep' in _names))
check(u'A2 改调 `fit_sentences`', u'fit_sentences' in _names, u'%r' % (sorted(set(_names))[:14],))
check(u'A3 上限从模块取（`AUTO_SPEAK_MAX_CHARS`，不是本地魔法数）',
      u'AUTO_SPEAK_MAX_CHARS' in _names)
check(u'A4 `main.py` 顶部真从 event_speech import 了这两个名字',
      u'fit_sentences, AUTO_SPEAK_MAX_CHARS' in _src_main)

# ★ 破坏性负控制：把内联形状写回去，A1 必须报红
_mut_src = _src_main.replace(
    u'text = fit_sentences(text, AUTO_SPEAK_MAX_CHARS)',
    u"for sep in ('\\n', u'。'):\n                if sep in text:\n                    text = text.split(sep, 1)[0]\n                    break\n            if len(text) > 40:\n                text = text[:40]")
_mut_names = []
try:
    _mfn = _func(ast.parse(_mut_src), 'start_autonomous_speech')
    _mut_names = [n.id for n in ast.walk(_mfn) if isinstance(n, ast.Name)]
except SyntaxError:
    _mut_names = [u'<语法坏>']
check(u'A5 负控制：把内联形状写回去后 A1 必须报红（`sep` 重新出现）',
      u'sep' in _mut_names, u'%r' % (_mut_names[:6],))

# =============================================== B 行为面
head(u'B. `fit_sentences` 的行为（上限 40 / 切点落在句末 / 保住信息量）')

_LONG = u'听说被领导训了一顿？那天是什么情况呢？有没有遇到什么特别让人心烦的事？我在这边听着呢。'
_r = ES.fit_sentences(_LONG)
check(u'B1 长问句链：输出 ≤ 上限', len(_r) <= MAX_AUTO, u'%d 字' % len(_r))
check(u'B2 长问句链：**没有**被切成一句（≥ 30 字，保住了"追问一句"这层）',
      len(_r) >= 30, u'%r' % _r)
check(u'B3 长问句链：结尾是句末标点（不吊尾巴）', _r and _r[-1] in ENDS, u'%r' % _r)

_ell = u'嗯，那天你说起过一只总在窗台上待着的小猫，叫豆豆是吧……我记得你有时候会给它点吃'
_re = ES.fit_sentences(_ell)
check(u'B4 `……` 那条不再吊尾巴（旧内联在它上面断在"叫豆豆是吧……我记得你有时候会给它点吃"）',
      bool(_re) and _re[-1] in ENDS and len(_re) <= MAX_AUTO,
      u'%d 字 %r' % (len(_re), _re))

check(u'B5 短文本整句保留', ES.fit_sentences(u'你回来啦。今天怎么样？') == u'你回来啦。今天怎么样？',
      u'%r' % ES.fit_sentences(u'你回来啦。今天怎么样？'))
check(u'B6 只有标点 / 空串 ⇒ 返回空（不许把「……」当台词显示）',
      ES.fit_sentences(u'……') == u'' and ES.fit_sentences(u'。') == u''
      and ES.fit_sentences(u'') == u'' and ES.fit_sentences(None) == u'')
check(u'B7 无句末标点的超长文本 ⇒ 硬截到上限（这是唯一兜底）',
      len(ES.fit_sentences(u'a' * 120)) == MAX_AUTO,
      u'%d 字' % len(ES.fit_sentences(u'a' * 120)))
check(u'B8 上限恒定：随便喂都 ≤ %d 字' % MAX_AUTO,
      all(len(ES.fit_sentences(s)) <= MAX_AUTO for s in
          (_LONG, _ell, u'a' * 120, u'。' * 60, u'你好。' * 40)),
      u'%d' % max(len(ES.fit_sentences(s)) for s in (_LONG, _ell, u'a' * 120)))

# =============================================== C 两个函数的分工
head(u'C. `fit_sentences` 与 `first_sentence` 分工不同（不该被合并成一个）')

_a = ES.fit_sentences(_LONG)
_b = ES.first_sentence(_LONG, ES.EVENT_MAX_CHARS)
check(u'C1 同一输入：`fit_sentences`(40) 比 `first_sentence`(24) **不短**',
      len(_a) >= len(_b), u'%d vs %d：%r / %r' % (len(_a), len(_b), _a, _b))
check(u'C2 两者都不吊尾巴（各守各的上限）',
      (not _tail(_a, MAX_AUTO)) and (not _tail(_b, ES.EVENT_MAX_CHARS)))
check(u'C3 两个上限是**两个**数（24 != 40）',
      ES.EVENT_MAX_CHARS != MAX_AUTO, u'%d / %d' % (ES.EVENT_MAX_CHARS, MAX_AUTO))

# =============================================== D 真实语料
head(u'D. 84 条真实 AI 回复：吊尾巴归零，且**没有**把话变少')

_live = _rows(LIVE131)
_ev = _rows(EV133)
_corpus = [(r.get('reply') or u'') for r in _live] + [(r.get('raw') or u'') for r in _ev]
check(u'D0 分母非空：84 条真实回复（第131轮真机 42 + 第133轮事件 42）',
      len(_corpus) == 84, u'%d 条' % len(_corpus))

_new_out = [ES.fit_sentences(s) for s in _corpus]
_old_out = [_old_inline(s) for s in _corpus]
_new_tail = [o for o in _new_out if _tail(o)]
_old_tail = [o for o in _old_out if _tail(o)]
check(u'D1 旧内联**确实**吊了 ≥ 5 条尾巴（否则 D2 是在描述一个没坏过的实现）',
      len(_old_tail) >= 5, u'%d 条' % len(_old_tail))
check(u'D2 新实现：吊尾巴 0 条', not _new_tail, u'%d 条：%r' % (len(_new_tail), _new_tail[:2]))

_avg_new = sum(len(o) for o in _new_out) / float(len(_new_out))
_avg_old = sum(len(o) for o in _old_out) / float(len(_old_out))
check(u'D3 平均长度**不低于**旧内联（修 bug 不许把话变少）',
      _avg_new >= _avg_old - 0.5, u'old %.1f → new %.1f' % (_avg_old, _avg_new))
check(u'D4 上限恒定（全部 ≤ %d）' % MAX_AUTO,
      all(len(o) <= MAX_AUTO for o in _new_out),
      u'max=%d' % max(len(o) for o in _new_out))

# =============================================== E 连续句末标点
head(u'E. 连续句末标点不许切一半（`……` / `诶？！`）')

# ★★★ 这一段的自纠记录（别删，它比断言本身更值钱）：
#   第一版把 E1 写成 `ES.fit_sentences(u'嗯，好吧……').endswith(u'……')`，看着在守 `……`，
#   **实际恒真** —— 全文 6 字 ≤ 40，走的是"整段就是 head"那条路，切点下标是谁都一样。
#   负控制当场把它抓出来：把 `_eat_sentence_end` 停成恒等后 E1/E2 **照样绿**。
#   然后去查为什么（`_tools/diag136b.py` → `diag136b2.py`，落 `_evidence/`）：
#     · `fit_sentences` 在**默认上限下与 eat 状态完全等价** —— 40 / 24 两个上限上
#       6 个上限 × 1250 条语料实测 **0 条差异**；只有 max ≤ 12 才出现。
#       原因：它挑的是 `ok[-1]`（最大下标），而连续标点里 run-final 下标最大
#       ⇒ 只要 run-final 放得下就总是它被选中，"吃不吃完"不影响选择。
#     · `first_sentence` 会变：它的句号分支是"挑第一个够长的切点"，
#       若连续标点里**靠前那个就已经够长**，就会切在 run 中间 ⇒ 只剩一个 `…`。
#     · 真实语料（84 条）上确实有 **3 条**差异，方向全是 **eat=on 保住 `……`**、
#       eat=off 退化成单个 `…`（逐条见 `_evidence/diag136b2.txt` ② 节）。
#   ⇒ 结论：`……` 的断言落在 `first_sentence` 上才测得动；`fit_sentences` 那边只保留
#     一条"合同"（输出不许以单个 `…` 收尾），**不假装它是 eat 的守卫**。

_ELL = u'真的很好呀……'
check(u'E1 `……` 不被切成单个 `…`（`first_sentence`：全文 7 字都放得下，本该整句留）',
      ES.first_sentence(_ELL) == _ELL, u'%r' % ES.first_sentence(_ELL))
check(u'E2 既有契约：`诶？！好舒服呀。` 仍是完整一句（`？！` 不被切一半）',
      ES.first_sentence(u'诶？！好舒服呀。后面还有好多话要说呢。') == u'诶？！好舒服呀。',
      u'%r' % ES.first_sentence(u'诶？！好舒服呀。后面还有好多话要说呢。'))
check(u'E3 合同（不是 eat 的守卫）：`fit_sentences` 输出不以单个 `…` 收尾',
      ES.fit_sentences(u'嗯，好吧……').endswith(u'……'),
      u'%r' % ES.fit_sentences(u'嗯，好吧……'))

# ★ 破坏性负控制（成对）：把 `_eat_sentence_end` 停成恒等，E1 必须报红
_orig = ES._eat_sentence_end
try:
    ES._eat_sentence_end = lambda t, i: i
    _e1 = ES.first_sentence(_ELL)
finally:
    ES._eat_sentence_end = _orig
check(u'E4 负控制：停掉 `_eat_sentence_end` 后 `……` 必须退化成单个 `…`',
      _e1 == u'真的很好呀…', u'停掉后 %r（期望 %r）' % (_e1, u'真的很好呀…'))
check(u'E5 恢复后 E1/E2 仍成立（负控制没把产品改坏）',
      ES.first_sentence(_ELL) == _ELL
      and ES.first_sentence(u'诶？！好舒服呀。后面还有好多话要说呢。') == u'诶？！好舒服呀。')

# ★ 真实语料上的正收益（不是构造样本）：拿 84 条里以 `……` 收句的那几条来断
_ell_rows = [s for s in _corpus
             if ES.first_sentence(s, ES.EVENT_MAX_CHARS).endswith(u'……')]
check(u'E6 分母非空：真实语料里真有以 `……` 收句的回复', len(_ell_rows) >= 3,
      u'%d 条' % len(_ell_rows))
try:
    ES._eat_sentence_end = lambda t, i: i
    _ell_dry = [ES.first_sentence(s, ES.EVENT_MAX_CHARS) for s in _ell_rows]
finally:
    ES._eat_sentence_end = _orig
check(u'E7 这几条停掉 eat 后**全部**退化成单个 `…`（所以 E4 不是单点巧合）',
      all(not d.endswith(u'……') for d in _ell_dry),
      u'%d/%d 条退化' % (sum(1 for d in _ell_dry if not d.endswith(u'……')), len(_ell_dry)))

# =============================================== F 事件链没被带坏
head(u'F. 事件链的 3 条元话语泄漏仍是完整的 9 字句')

_leaks = [r for r in _live if ES.looks_like_meta_leak(r.get('reply') or u'')]
check(u'F0 分母：3 条', len(_leaks) == 3, u'%d' % len(_leaks))
check(u'F1 输出全是「你说的是坏消息吗？」或「那听起来挺辛苦的。」（9 字，完整）',
      all(len(ES.first_sentence(r['reply'], ES.EVENT_MAX_CHARS)) == 9 for r in _leaks),
      u'%r' % [ES.first_sentence(r['reply'], ES.EVENT_MAX_CHARS) for r in _leaks])

# =============================================== G 自检
head(u'G. 本套件自检')

_self = ast.parse(_read(os.path.abspath(__file__)))
_bad_true = [n.lineno for n in ast.walk(_self)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'check' and len(n.args) >= 2
             and isinstance(n.args[1], ast.Constant) and n.args[1].value is True]
check(u'G1 无恒真判据（`check(..., True)` 0 处）', not _bad_true, u'%d 处' % len(_bad_true))
with io.open(os.path.abspath(__file__), 'rb') as f:
    _raw = f.read()
check(u'G2 无 BOM', not _raw.startswith(b'\xef\xbb\xbf'))
check(u'G3 零外部盘（读的文件全在仓库内）',
      all(os.path.abspath(p).startswith(ROOT + os.sep)
          for p in (MAIN_PY, ES_PY, LIVE131, EV133)))
check(u'G4 `AUTO_SPEAK_MAX_CHARS` 是模块常量（不是函数默认值里的裸数字）',
      isinstance(MAX_AUTO, int) and MAX_AUTO == 40, u'%r' % (MAX_AUTO,))

# =============================================== 落盘
if not os.path.isdir(EV):
    os.makedirs(EV)
_ev = {'auto_max': MAX_AUTO, 'event_max': ES.EVENT_MAX_CHARS,
       'corpus': len(_corpus),
       'old_tail': len(_old_tail), 'new_tail': len(_new_tail),
       'avg_old': round(_avg_old, 2), 'avg_new': round(_avg_new, 2),
       'sample_long': _r, 'sample_ellipsis': _re}
with io.open(os.path.join(EV, 'auto136.json'), 'w', encoding='utf-8', newline='') as f:
    f.write(json.dumps(_ev, ensure_ascii=False, indent=1))

print(u'')
print(u'=' * 78)
print(u'check136：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)

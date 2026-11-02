# -*- coding: utf-8 -*-
"""第135轮回归锁：事件台词的截断不许"吊尾巴"。

## 病是什么

`event_speech.first_sentence()` 原来的切点是**按标点类型优先级**挑的：
`。`→`！`→`？`→`!`→`?`→`\\n`，看哪个**类型**先出现在文里，就用它的**第一个下标**切。
于是"第一句是问句、后面某句有句号"时，切点被推到**后面那句的句号**上，
再硬截 24 字 ⇒ 截在半个句子上，原样显示成吊尾巴的坏台词。

真机证据（第131轮 3 条元话语泄漏里的 2 条，都是这个形状）：

    raw = 「你说的是坏消息吗？\\n\\n你说的是坏消息的时候我不该用亮起来的开头，…。」
    old = 「你说的是坏消息吗？\\n\\n你说的是坏消息的时候我不该」   ← 24 字，断在"我不该"
    new = 「你说的是坏消息吗？」                                  ← 9 字，完整

## 修法（不是"取最靠前"，那会丢掉"句号=想法边界"）

    ① 有句号 ⇒ 只在"句号及之前"的切点里挑第一个够长的；都不够长就用句号本身；
    ② 没句号 ⇒ 只看**第一个**句末标点，够长就切、太短就整句保留；
    ③ 没句号 + 太短 + 全文超上限 ⇒ 切（保持改造前行为）。

★ ①②③ 每一支都有既有判据撑着。第一版我写成"取最靠前的够长切点"，
  `s7_event_speech A11` 当场判红（它把「诶？！好舒服呀。后面还有好多话要说呢。」
  **整句**留下了）⇒ "句号优先"这条语义不能丢。这条教训进报告 §135.4。

## 本套件守什么（零 Qt / 零网络 / 零外部盘）

A 真机回归：42 条真机事件回复逐字不变（**回归判据**，不是效果判据 —— 它们本来就短）
B 修复效果：3 条真泄漏输出干净（B4/B5 是成对的旧/新对照 + 负控制）
C 规则面：8 条 case，其中 5 条是 `s7_event_speech A9/A11` 的既有契约
D `MIN_FIRST_CHARS` 语义保住（「嗯？发生了什么吗？」不许切成 2 个字）
E 不变量：**凡是顶到 24 字的输出，结尾必须是句末标点**（从根上防"吊尾巴"复发）
F 接线（AST）：`main.py` 仍用 `first_sentence(reply, self.EVENT_SPEAK_MAX_CHARS)`
G 自检

## 纪律

`print('[PASS] %s')` 字面量；判据名不自带标记；**判据只有一份**（一律调产品函数）；
不把"更好看"写成判据 —— 只断"完整句 / 不吊尾巴 / 既有契约不变"。
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

EV133 = os.path.join(ROOT, 'code-quality-audit', '第133轮-事件台词元话语核查',
                     '_evidence', 'event133.jsonl')
LIVE131 = os.path.join(ROOT, 'code-quality-audit', '第131轮-真机7题复测',
                       '_evidence', 'live7_131.jsonl')

sys.path.insert(0, os.path.join(PET, 'modules'))
import event_speech as ES                                     # noqa: E402

MAX = ES.EVENT_MAX_CHARS
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


def _tail(s):
    """"吊尾巴"的可判定定义：非空、顶到上限附近、结尾不是句末标点。"""
    if not s:
        return False
    return (s[-1] not in ENDS) and len(s) >= MAX - 2


def _old_first_sentence(text, max_chars=MAX):
    """**旧实现的快照**（第135轮之前的版本），只用于 B4/B5 的对照。

    ★ 它不是第二份真源：产品里已经没有这段代码了，这里留着是为了
      "证明旧版本在同一条输入上确实吊尾巴"（否则 B1 可能只是在描述一个
      从来没坏过的函数）。改它没有任何意义，别把它当契约。
    """
    if not isinstance(text, str):
        return ''
    t = text.strip()
    if not t:
        return ''
    t = t.strip(u'"\'“”「」『』《》').strip()
    if not t:
        return ''
    chosen = None
    for sep in (u'。', u'！', u'？', u'!', u'?', u'\n'):
        if sep in t:
            chosen = sep
            break
    if chosen is not None:
        i = t.index(chosen)
        h = t[:i] if chosen == '\n' else t[:i + 1]
        if len(h.strip()) < ES.MIN_FIRST_CHARS and len(t) <= max_chars:
            pass
        else:
            t = h
    t = t.strip()
    if len(t) > max_chars:
        t = t[:max_chars].rstrip(u'，,、。！？!?；;：: ')
    return t.strip()


EV_ROWS = _rows(EV133)
LIVE_ROWS = _rows(LIVE131)
LEAKS = [r for r in LIVE_ROWS if ES.looks_like_meta_leak(r.get('reply') or '')]


def _kind_of(r, key):
    return r.get(key) or ''


# =============================================== A 真机回归
head(u'A. 真机回归：42 条事件回复的截断结果**逐字不变**（改动对真实语料零影响）')

check(u'A0 分母非空：42 条真机事件 / 3 条元话语泄漏',
      (len(EV_ROWS), len(LEAKS)) == (42, 3),
      u'%d / %d' % (len(EV_ROWS), len(LEAKS)))

_diff = [(r.get('kind'), r.get('sample'), r.get('first'),
          ES.first_sentence(r.get('raw') or '', MAX))
         for r in EV_ROWS
         if ES.first_sentence(r.get('raw') or '', MAX) != (r.get('first') or '')]
check(u'A1 42 条逐字不变（对照第133轮冻结的 first 字段）', not _diff,
      u'变了 %d 条：%s' % (len(_diff), _diff[:3]))

# ★ 正控制：**在开头**加一句，必须让"逐字不变"判据看出差异。
#   第一版写在结尾（`+ '。多出来的一句。'`）⇒ 判据报红，红的是这条正控制：
#   `first_sentence` 只取第一句，**往末尾加东西本来就不影响结果**
#   ⇒ 负控制的输入没落进被测分支（第129/133轮那条教训的同型）。
_mut = dict(EV_ROWS[0])
_mut['raw'] = u'我先说一句。' + (_mut.get('raw') or u'')
check(u'A1n 正控制：**开头**多一句必须让"逐字不变"判据报差',
      ES.first_sentence(_mut['raw'], MAX) != (EV_ROWS[0].get('first') or u''),
      u'变异后=%r' % ES.first_sentence(_mut['raw'], MAX))

# =============================================== B 修复效果
head(u'B. 修复效果：3 条真泄漏不再吊尾巴（含旧/新对照与负控制）')

_new = [(r.get('qid'), r.get('sample'), ES.first_sentence(r['reply'], MAX))
        for r in LEAKS]
_bad_tail = [(q, s, t) for q, s, t in _new if _tail(t)]
check(u'B1 输出全部不再"吊尾巴"（结尾是句末标点，或没顶到上限）', not _bad_tail,
      u'%d 条：%s' % (len(_bad_tail), _bad_tail))

_old = [(r.get('qid'), r.get('sample'), _old_first_sentence(r['reply'], MAX))
        for r in LEAKS]
_old_tail = [(q, s, t) for q, s, t in _old if _tail(t)]
check(u'B2 A/B 先断言不同：旧实现下**确实至少 2 条**吊尾巴（否则 B1 无从谈起）',
      len(_old_tail) >= 2, u'%d 条：%s' % (len(_old_tail), _old_tail))

_old_set = set(t for _, _, t in _old)
_new_set = set(t for _, _, t in _new)
check(u'B3 新旧结果真的不同（不是"改了代码但行为没变"）', _old_set != _new_set,
      u'old=%r' % (_old_set,))

check(u'B4 两条长回复的输出逐字等于第一句问句',
      [t for q, s, t in _new if q == u'Q7'] == [u'你说的是坏消息吗？'] * 2,
      u'%r' % ([t for q, s, t in _new if q == u'Q7'],))

_g = [ES.guard_reaction(t) for _, _, t in _new]
check(u'B5 结果全部能过 `guard_reaction`（放行且原样返回，不是被判退空串）',
      all(g == t for g, (_, _, t) in zip(_g, _new)), u'%r' % (_g,))

# =============================================== C 规则面
head(u'C. 切点规则：既有契约 5 条 + 第135轮新增 3 条')

# ★ 前 5 条来自 `s7_event_speech` 的 A9/A11（**既有契约，不许因为改实现而丢**）
CASES = [
    (u'谢谢你，小豆。让我靠你一会儿。', u'谢谢你，小豆。', u'A9'),
    (u'哎呀！别捏我的耳朵！好痒呀！', u'哎呀！别捏我的耳朵！好痒呀！', u'A9'),
    (u'嗯？发生了什么吗？', u'嗯？发生了什么吗？', u'A9'),
    (u'嘿嘿~ 好舒服呀！谢谢你主人！', u'嘿嘿~ 好舒服呀！', u'A9'),
    (u'诶？！听到这话我都有点不好意思起来了。感觉就像在阳光下晒着一样舒服呢。',
     u'诶？！听到这话我都有点不好意思起来了。', u'A11'),
    (u'诶？！好舒服呀。后面还有好多话要说呢。', u'诶？！好舒服呀。', u'135'),
    (u'你说的是坏消息吗？\n\n你说的是坏消息的时候我不该用亮起来的开头，先就着那件具体的事问一句。',
     u'你说的是坏消息吗？', u'135'),
    (u'你说的是坏消息吗？\n\n先就着你说的那件事问一句：“这么说，你是觉得……”再留个“我在”的意思。',
     u'你说的是坏消息吗？', u'135'),
]
for src, want, src_tag in CASES:
    got = ES.first_sentence(src)
    check(u'C1 [%s] %r ⇒ %r' % (src_tag, src[:16], want), got == want, u'实际=%r' % got)

# ★ 正控制：把 want 故意写错一个字符，同一判据必须报红
_wrong = ES.first_sentence(CASES[0][0]) + u'。'
check(u'C1n 正控制：want 写错一个字必须不相等（证明上面是逐字比，不是比前缀）',
      _wrong != CASES[0][1], u'%r' % _wrong)

# =============================================== D MIN 语义
head(u'D. `MIN_FIRST_CHARS` 的原始语义不许被这次改动带走')

check(u'D1 「嗯？发生了什么吗？」不被切成 2 个字（这条是 MIN 的实测起因）',
      ES.first_sentence(u'嗯？发生了什么吗？') == u'嗯？发生了什么吗？',
      u'%r' % ES.first_sentence(u'嗯？发生了什么吗？'))
check(u'D2 「诶？！好舒服呀。…」按**句号**切（不是按更早的问号切）',
      ES.first_sentence(u'诶？！好舒服呀。后面还有好多话要说呢。') == u'诶？！好舒服呀。',
      u'%r' % ES.first_sentence(u'诶？！好舒服呀。后面还有好多话要说呢。'))

# =============================================== E 不变量
head(u'E. 不变量：**凡是顶到上限的输出，结尾必须是句末标点**（从根上防复发）')

_all_src = [(r.get('raw') or '') for r in EV_ROWS] + [r['reply'] for r in LEAKS]
_tail_all = [ES.first_sentence(s, MAX) for s in _all_src]
_tail_bad = [t for t in _tail_all if _tail(t)]
check(u'E1 %d 条语料里 0 条顶格吊尾巴' % len(_all_src), not _tail_bad,
      u'%d 条：%r' % (len(_tail_bad), _tail_bad[:3]))
check(u'E2 分母非空（45 条里至少有一条被真的压到接近上限，否则 E1 是空跑）',
      any(len(t) >= MAX - 8 for t in _tail_all),
      u'最长 %d 字' % max([len(t) for t in _tail_all] or [0]))

# =============================================== F 接线
head(u'F. 接线（AST）：`main.py` 仍从事件链拿截断结果')

_src = _read(MAIN_PY)
_t = ast.parse(_src)
_call = [n for n in ast.walk(_t)
         if isinstance(n, ast.Call)
         and ((isinstance(n.func, ast.Name) and n.func.id == 'first_sentence')
              or (isinstance(n.func, ast.Attribute) and n.func.attr == 'first_sentence'))]
# ★★ 第138轮：extra **不再打印行号**（旧写法 `u'%d 处：第 %s 行'`）——
#   行号是时相量：第137轮我在 `chat_with_ai` 上方加了注释，这条全绿的判据就 DIFF。
check(u'F1 `main.py` 里 `first_sentence(...)` 真被调用', len(_call) == 1,
      u'%d 处' % len(_call))
check(u'F2 它的第二个实参是 `self.EVENT_SPEAK_MAX_CHARS`（不是写死的数字）',
      bool(_call) and len(_call[0].args) >= 2
      and isinstance(_call[0].args[1], ast.Attribute)
      and _call[0].args[1].attr == 'EVENT_SPEAK_MAX_CHARS',
      u'%r' % (ast.dump(_call[0].args[1]) if _call and len(_call[0].args) >= 2 else None,))

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
          for p in (MAIN_PY, ES_PY, EV133, LIVE131)))
check(u'G4 `_SENTENCE_ENDS` 在位且含句号（改常量要同时看 C 段）',
      u'。' in ENDS)

# =============================================== 落盘
if not os.path.isdir(EV):
    os.makedirs(EV)
_ev = {'max_chars': MAX, 'min_first_chars': ES.MIN_FIRST_CHARS,
       'corpus': len(_all_src), 'leaks': len(LEAKS),
       'changed_on_real_corpus': len(_diff),
       'old_tail': [t for _, _, t in _old if _tail(t)],
       'new': [t for _, _, t in _new]}
with io.open(os.path.join(EV, 'tail135.json'), 'w', encoding='utf-8', newline='') as f:
    f.write(json.dumps(_ev, ensure_ascii=False, indent=1))

print(u'')
print(u'=' * 78)
print(u'check135：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(0 if _n['f'] == 0 else 1)

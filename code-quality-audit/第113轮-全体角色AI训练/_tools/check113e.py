# -*- coding: utf-8 -*-
u"""第113轮e回归锁：**括号旁白**的两把尺不许再同时失效。

为什么单独加一条锁
------------------
第113轮冒烟（susie 48 轮）里，模型每一轮都在写：

    烦死了。（你皱起眉头看着屏幕那边的人，"你别这么盯着我看。"）

而**两处判据同时放行**了它：

  · 训练判据 `common113._PAREN_RE` 上限 `{1,30}` ⇒ 40~80 字的旁白**完全不匹配**，
    48 轮里只有 2 轮被判违规（真值接近 48）；
  · 产品护栏 `event_speech.strip_action_parentheticals` 的三道闸都抓不到
    「第二人称描述自己」这种形态（`_ANY_PAREN_RE` 还有 40 字上限，长旁白连门都进不去）。

⇒ 结果是"**指标说没问题、用户每轮都看到旁白**"。这类缺陷不会崩、不会报错，
只能靠一条锁盯着。本套件因此不测"有没有这段代码"，而测**行为**：

  A 产品护栏：4 条真实模型输出必须把旁白删掉、台词留下；
  B 产品护栏负控制：7 条正常台词一个字都不许动（含第一人称心里话，按既有裁定必须保留）；
  C 训练判据：同样 4 条必须报违规；无括号的正常台词不许误报；
  D **破坏性负控制**：把新判据拆掉/把上限改回 30，A 与 C 必须重新漏掉
    —— 证明通过不是恒真。

★ 两把尺**本来就不是同一把**：产品只删「第二人称旁白 + 含引号」，训练把**任何括号**
  都算违规（`（你懂的）` 产品保留、训练报违规）。这是有意为之，套件里显式断言二者不同，
  免得后来者"顺手统一"。

零网络、零 Qt、不读临时盘。
"""
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.path.insert(0, HERE)

import modules.event_speech as ES   # noqa: E402
import common113 as C               # noqa: E402

_failed = []
_n_pass = 0
_n_fail = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))
        _failed.append(desc)


S = ES.strip_action_parentheticals

# ---- A 正控制：真实模型输出（susie 第1/3/4/6 轮，一字未改） ----
# ★★★ 第113轮f 改期望：括号里**包着台词**的不再整段删，而是把引号里的内容**救出来**
#   当台词（实测 susie 48 处括号里 47 处是这种，删掉等于把她要说的话全丢了）。
POS = [
    ('第1轮', '烦死了。（你皱起眉头看着屏幕那边的人，“你别这么盯着我看。我才没空想东想西的！”）',
     '烦死了。你别这么盯着我看。我才没空想东想西的！'),
    ('第3轮', '先啃点东西充饥。（你轻描淡写地说道）不过晚上得开夜车。', '先啃点东西充饥。不过晚上得开夜车。'),
    ('第4轮', '哈，你说那个啊。（你的目光闪烁了一下，“有时候确实会沉迷进去好几个小时……”）',
     '哈，你说那个啊。有时候确实会沉迷进去好几个小时……'),
    ('第6轮', '嗯……其实我没特别想留下的地方。（你的目光游离，“不过在黑暗世界的湖边挺好的。”）',
     '嗯……其实我没特别想留下的地方。不过在黑暗世界的湖边挺好的。'),
    ('第7轮', '哦对。（你顿了顿，「其实我一直记着那件事。」）', '哦对。其实我一直记着那件事。'),
]

# ---- B 负控制：正常台词，一个字都不许动 ----
NEG = [
    '（你懂的）那种感觉。',
    '（你说的对）那就这么办。',
    '（笑）随你便。',
    '（其实我很害怕）但我还是要去。',
    '（你叫什么名字）我先问问。',
    '（你想去吗）我等你决定。',
    '那种感觉，你知道的。',
]

# ---- C 训练判据负控制：完全不含括号的正常台词 ----
NEG_GATE = ['那就这么办吧。', '随你便，我无所谓。', '我一直都在这儿等你。']


# ==================================================== A 产品护栏·正控制
for tag, src, want in POS:
    got = S(src)
    check('A 产品护栏删旁白留台词 [%s]' % tag, got == want, repr(got))

# 拆干净防护：正控制输入确实含括号，且确实比原来短（不是"本来就没东西可删"）
check('A0 正控制输入确实含括号且被改短（防"没东西可删"）',
      all(('（' in s) and len(S(s)) < len(s) for _, s, _ in POS),
      '4 条均变短')

# ==================================================== B 产品护栏·负控制
for i, src in enumerate(NEG, 1):
    got = S(src)
    check('B%d 负控制逐字不变 %r' % (i, src[:8]), got == src, repr(got[:24]))

# 第一人称心里话（既有裁定：Ralsei 原作里括号是正常表达，必须保留）
check('B8 第一人称心里话不被误删（既有裁定）',
      S('（其实我很害怕）但我还是要去。') == '（其实我很害怕）但我还是要去。')

# ==================================================== C 训练判据
for tag, src, _ in POS:
    m = C._PAREN_RE.search(src)
    check('C 训练判据报出括号旁白 [%s]' % tag, bool(m), (m.group(0)[:34] if m else '漏报'))

for i, src in enumerate(NEG_GATE, 1):
    check('C-gate%d 无括号台词不误报' % i, not C._PAREN_RE.search(src), repr(src[:16]))

# 两把尺必须**不同**（否则等于没分开，也说明其中一把被改坏了）
check('C9 两把尺刻意不同：`（你懂的）` 产品保留、训练报违规',
      S('（你懂的）那种感觉。') == '（你懂的）那种感觉。'
      and bool(C._PAREN_RE.search('（你懂的）那种感觉。')),
      '产品=留 / 训练=违规')


# ==================================================== D 破坏性负控制
def _with_broken_guard(fn):
    """**把新判据拆干净**：四条一起拆，只拆一条不算数（§95.13）。

    ★ 第113轮f 追加第四条：`_rescue_quoted`。不拆它，引号里的话会被救出来，
      正控制就"看起来仍然生效"—— 那正是"负控制没拆干净"的假绿。
    """
    saved = (ES._SECOND_PERSON_NARRATION, ES._QUOTED_IN_PAREN, ES._ANY_PAREN_RE,
             ES._rescue_quoted)
    try:
        ES._SECOND_PERSON_NARRATION = re.compile(r'(?!)')
        ES._QUOTED_IN_PAREN = re.compile(r'(?!)')
        ES._ANY_PAREN_RE = re.compile(r'[（(]([^）)]{0,40})[）)]')
        ES._rescue_quoted = lambda m: m.group(0)
        return fn()
    finally:
        (ES._SECOND_PERSON_NARRATION, ES._QUOTED_IN_PAREN, ES._ANY_PAREN_RE,
         ES._rescue_quoted) = saved


_broken_kept = _with_broken_guard(lambda: [S(s) for _, s, _ in POS])
check('D1 ★ 拆掉新判据后 4 条正控制必须**全部**重新漏掉（证明 A 不是恒真）',
      all(g == s for g, (_, s, _) in zip(_broken_kept, POS)),
      '漏掉 %d/4' % sum(1 for g, (_, s, _) in zip(_broken_kept, POS) if g == s))

# 拆完之后负控制仍然不许被误伤（说明 B 也不是靠"改坏了才通过"）
_broken_neg = _with_broken_guard(lambda: [S(s) for s in NEG])
check('D2 拆掉新判据后负控制仍逐字不变（B 不是靠误伤换来的）',
      _broken_neg == NEG, '7 条一致')


def _with_narrow_gate(fn):
    saved = C._PAREN_RE
    try:
        C._PAREN_RE = re.compile(r'[（(][^（()）]{1,30}[)）]')
        return fn()
    finally:
        C._PAREN_RE = saved


_narrow_hits = _with_narrow_gate(lambda: [bool(C._PAREN_RE.search(s)) for _, s, _ in POS])
check('D3 ★ 上限改回 {1,30} 后训练判据必须重新漏报（证明 C 不是恒真）',
      sum(_narrow_hits) < len(POS),
      '窄版命中 %d/%d（宽版 %d/%d）'
      % (sum(_narrow_hits), len(POS),
         sum(1 for _, s, _ in POS if C._PAREN_RE.search(s)), len(POS)))

# 还原后必须与跑之前一致（防止 finally 写错把全局搞坏）
check('D4 破坏性测试结束后全局已还原',
      bool(C._PAREN_RE.search(POS[0][1])) and S(POS[0][1]) == POS[0][2],
      '判据与护栏均正常')


def _with_broken_rescue(fn):
    """只拆「救出台词」这一闸（其余照旧），看台词是不是真的会跟着旁白一起消失。"""
    saved = ES._rescue_quoted
    try:
        ES._rescue_quoted = lambda m: m.group(0)   # 不救 ⇒ 原样交给后续几闸删掉
        return fn()
    finally:
        ES._rescue_quoted = saved


_lost = _with_broken_rescue(lambda: [S(s) for _, s, _ in POS])
check('D5 ★ 拆掉「救出台词」后，引号里的话必须跟着旁白一起消失（证明 A 的新期望不是恒真）',
      all('你别这么盯着我看' not in g for g in _lost[:1])
      and all('有时候确实会沉迷进去' not in g for g in _lost[2:3]),
      '拆掉后第1轮=%r' % (_lost[0][:26],))

# 拆完之后，**不含引号**的那条（第3轮）结果不该变 —— 说明救出闸只动"包台词"的那类
_lost3 = _lost[1]
check('D6 救出闸只动「包台词」的括号，纯动作旁白行为不变',
      _lost3 == POS[1][2], repr(_lost3))

print()
print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print('失败项：')
    for f in _failed:
        print('  - ' + f)
sys.exit(1 if _n_fail else 0)

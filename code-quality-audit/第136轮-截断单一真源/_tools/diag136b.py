# -*- coding: utf-8 -*-
"""第136轮附诊断：`_eat_sentence_end` 到底在哪条分支上起作用。

## 为什么要有这一份

`check136 E3` 的负控制（把 `_eat_sentence_end` 停成恒等 `lambda t, i: i`）
**没有让 E1 / E2 报红** —— 停掉后两条断言照样成立。这说明：

> 输入根本没有落进被测分支。

不当成"判据换个写法糊过去"，先实测两件事：

1. `fit_sentences` 上**有没有任何输入**会因为 eat 而改变输出？
   （直觉上"取最长可放下的切点"＝ `ok[-1]`，而连续标点里最后一个下标最大，
     所以 run-final 一旦放得下就总是它被选中 ⇒ eat 可能是**行为等价**的。）
2. `first_sentence` 上**最小可变形态**是什么？
   （它的句号分支是"挑第一个够长的切点"，若连续标点里**靠前那个就已经够长**，
     就会切在 run 中间 ⇒ 输出只剩一个 `…`。）

结论要落成"能用哪个输入做负控制"，而不是"我觉得应该用哪个"。
"""
import io
import itertools
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROUND, '_evidence')
sys.path.insert(0, os.path.join(PET, 'modules'))
import event_speech as ES                                     # noqa: E402

OUT = []


def say(s=u''):
    OUT.append(s)
    print(s)


def head(t):
    say(u'')
    say(u'=' * 78)
    say(t)


def with_eat_off(fn, *a, **kw):
    """临时把 `_eat_sentence_end` 停成恒等，跑一次，恢复。"""
    orig = ES._eat_sentence_end
    try:
        ES._eat_sentence_end = lambda t, i: i
        return fn(*a, **kw)
    finally:
        ES._eat_sentence_end = orig


# ---------------------------------------------------------------- 语料
FILL_HEAD = [u'a' * k for k in range(0, 13)]
FILL_HEAD += [u'真的很好呀'[:k] for k in range(1, 6)]
FILL_HEAD += [u'诶', u'好呀', u'真的很好呀']
RUNS = [u'…', u'……', u'…', u'？！', u'！！！', u'！', u'。', u'！。', u'？。', u'……。']
TAILS = [u'', u'后面还有好多话要说呢。', u'我记得你有时候会给它点吃', u'b' * 20,
         u'嗯。好。', u'后面的话我不能说太多。再等等吧。']

CORPUS = []
for h, r, tl in itertools.product(FILL_HEAD, RUNS, TAILS):
    if h or tl:
        CORPUS.append(h + r + tl)

say(u'语料：%d 条（前缀 × 连续标点 × 尾巴 的笛卡尔积）' % len(CORPUS))

# ---------------------------------------------------------------- ① fit_sentences
head(u'① `fit_sentences`：有没有输入会因为 eat 而变？')

diff_fit = []
for mc in (ES.AUTO_SPEAK_MAX_CHARS, ES.EVENT_MAX_CHARS, 12, 6, 5, 3):
    for s in CORPUS:
        on = ES.fit_sentences(s, mc)
        off = with_eat_off(ES.fit_sentences, s, mc)
        if on != off:
            diff_fit.append((mc, s, on, off))

if diff_fit:
    say(u'有 %d 条不同，前 5 条：' % len(diff_fit))
    for mc, s, on, off in diff_fit[:5]:
        say(u'  max=%d  %r\n     eat=on  %r\n     eat=off %r' % (mc, s, on, off))
else:
    say(u'**0 条不同**（6 个上限 × %d 条语料）' % len(CORPUS))
    say(u'⇒ 在 `fit_sentences` 里 eat 是**行为等价**的：它挑的是 `ok[-1]`（最大下标），')
    say(u'   而连续标点的 run-final 下标最大 ⇒ 只要 run-final 放得下就总是它被选中。')

# 为什么等价 —— 把推理落成可读的一句
say(u'')
say(u'   （run-final 放不下时：ok 里只剩靠前那个，但紧接着的 `elif len(t) > max_chars`')
say(u'     硬截路径产出的前缀与"带着重复标点硬截"逐字相同，两条路又合流。）')

# ---------------------------------------------------------------- ② first_sentence
head(u'② `first_sentence`：最小可变形态')


def _need_eat(s):
    on = ES.first_sentence(s, ES.EVENT_MAX_CHARS)
    off = with_eat_off(ES.first_sentence, s, ES.EVENT_MAX_CHARS)
    return on, off


diff_fs = []
for s in CORPUS:
    on, off = _need_eat(s)
    if on != off:
        diff_fs.append((s, on, off))

say(u'会因为 eat 而变的输入：%d 条 / %d' % (len(diff_fs), len(CORPUS)))
for s, on, off in diff_fs[:8]:
    say(u'  %r\n     eat=on  %r（%d 字）\n     eat=off %r（%d 字）'
        % (s, on, len(on), off, len(off)))
if diff_fs:
    # 挑最短的那条当负控制输入（越短越好读）
    best = min(diff_fs, key=lambda x: len(x[0]))
    say(u'')
    say(u'最短的一条（拿它做负控制输入）：%r' % (best[0],))
    say(u'  eat=on  %r' % (best[1],))
    say(u'  eat=off %r   ← 只剩一个 `…`，就是"切一半"' % (best[2],))

# ---------------------------------------------------------------- ③ 现有 E1/E2 为什么不红
head(u'③ 为什么现有 E1 / E2 停掉 eat 后**照样成立**')


def show(s, label):
    on_fit = ES.fit_sentences(s)
    off_fit = with_eat_off(ES.fit_sentences, s)
    on_fs = ES.first_sentence(s, ES.EVENT_MAX_CHARS)
    off_fs = with_eat_off(ES.first_sentence, s, ES.EVENT_MAX_CHARS)
    say(u'')
    say(u'%s  %r' % (label, s))
    say(u'  fit  on=%r  off=%r  %s' % (on_fit, off_fit,
                                       u'相同' if on_fit == off_fit else u'**不同**'))
    say(u'  first on=%r  off=%r  %s' % (on_fs, off_fs,
                                        u'相同' if on_fs == off_fs else u'**不同**'))


show(u'嗯，好吧……', u'E1')
show(u'诶？！好舒服呀。后面还有好多话要说呢。', u'E2')
say(u'')
say(u'E1：全文 %d 字 ≤ 上限 %d ⇒ 走"整段就是 head"那条路，切点下标是谁都一样。'
    % (len(u'嗯，好吧……'), ES.AUTO_SPEAK_MAX_CHARS))
say(u'E2：有句号 ⇒ 走句号分支，而 `诶？`（2 字）/ `诶？！`（3 字）都 < MIN_FIRST_CHARS(6)，')
say(u'    循环会跳过它们一路走到句号 ⇒ eat 有没有都不影响最终 pick。')

# ---------------------------------------------------------------- ④ 真实语料回看
head(u'④ 真实语料上 eat 到底改变了什么（98 条）')
import json


def rows(p):
    out = []
    with io.open(p, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


LIVE = os.path.join(ROOT, 'code-quality-audit', '第131轮-真机7题复测',
                    '_evidence', 'live7_131.jsonl')
EV133 = os.path.join(ROOT, 'code-quality-audit', '第133轮-事件台词元话语核查',
                     '_evidence', 'event133.jsonl')
corpus = []
for p, key in ((LIVE, 'reply'), (EV133, 'raw')):
    if os.path.isfile(p):
        corpus += [(r.get(key) or u'') for r in rows(p)]
say(u'真实语料 %d 条' % len(corpus))

n_fit = sum(1 for s in corpus if ES.fit_sentences(s) != with_eat_off(ES.fit_sentences, s))
n_fs = sum(1 for s in corpus
           if ES.first_sentence(s, ES.EVENT_MAX_CHARS)
           != with_eat_off(ES.first_sentence, s, ES.EVENT_MAX_CHARS))
say(u'  `fit_sentences` 会变的：%d 条' % n_fit)
say(u'  `first_sentence` 会变的：%d 条' % n_fs)
say(u'⇒ %s' % (u'真实语料里两者都不变 —— eat 目前是"**防未来**"，不是"修已知 bug"。'
               if n_fit == 0 and n_fs == 0 else u'真实语料里有实际差异，需逐条看。'))

# ---------------------------------------------------------------- 落盘
if not os.path.isdir(EV):
    os.makedirs(EV)
with io.open(os.path.join(EV, 'diag136b.txt'), 'w', encoding='utf-8', newline='') as f:
    f.write(u'\n'.join(OUT) + u'\n')
print(u'')
print(u'[OK] 已落 _evidence/diag136b.txt')

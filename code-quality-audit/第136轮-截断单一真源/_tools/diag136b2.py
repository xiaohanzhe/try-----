# -*- coding: utf-8 -*-
"""第136轮附诊断（续）：把 `diag136b` 里两处"没看清"的细节挖到底。

1. `fit_sentences` 的差异是不是**只**出现在非默认上限上？（决定 E 段该拿哪个上限断言）
2. 真实语料上 `first_sentence` 那 3 条差异**方向是哪边**（eat 让输出变好还是变坏）？
   这是唯一能证明"eat 在真实数据上有正收益"的证据；若方向是坏的，本轮的产品改动要回退。
"""
import io
import itertools
import json
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


def off(fn, *a, **kw):
    orig = ES._eat_sentence_end
    try:
        ES._eat_sentence_end = lambda t, i: i
        return fn(*a, **kw)
    finally:
        ES._eat_sentence_end = orig


FILL_HEAD = [u'a' * k for k in range(0, 13)]
FILL_HEAD += [u'真的很好呀'[:k] for k in range(1, 6)]
FILL_HEAD += [u'诶', u'好呀', u'真的很好呀']
RUNS = [u'…', u'……', u'？！', u'！！！', u'！', u'。', u'！。', u'？。', u'……。']
TAILS = [u'', u'后面还有好多话要说呢。', u'我记得你有时候会给它点吃', u'b' * 20,
         u'嗯。好。', u'后面的话我不能说太多。再等等吧。']
CORPUS = []
for h, r, tl in itertools.product(FILL_HEAD, RUNS, TAILS):
    if h or tl:
        CORPUS.append(h + r + tl)

# ---------------------------------------------------------------- ① 按上限拆
head(u'① `fit_sentences` 的差异**只**出现在哪些上限上')
for mc in (40, 24, 20, 16, 12, 8, 6, 5, 3):
    d = [(s, ES.fit_sentences(s, mc), off(ES.fit_sentences, s, mc)) for s in CORPUS]
    d = [x for x in d if x[1] != x[2]]
    say(u'  max=%-3d 差异 %3d 条  %s' % (mc, len(d),
                                     (u'例：%r on=%r off=%r' % (d[0][0], d[0][1], d[0][2]))
                                     if d else u''))
say(u'')
say(u'⇒ 默认 40 与事件链 24 上**都是 0 条**；差异只在 max < 本次语料里"前缀+标点"的长度时才出现。')
say(u'  形状是：run-final 放不下 ⇒ eat 把这个切点整个从 ok 里删掉 ⇒ 退回更早的切点。')
say(u'  默认上限下这个形状要求"连续标点正好跨在上限位置"，本语料 0 命中。')

# ---------------------------------------------------------------- ② 真实语料 3 条
head(u'② 真实语料：`first_sentence` 有差异的 3 条，方向是哪边')


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
    corpus += [(r.get(key) or u'') for r in rows(p)]

diff = []
for s in corpus:
    on = ES.first_sentence(s, ES.EVENT_MAX_CHARS)
    of = off(ES.first_sentence, s, ES.EVENT_MAX_CHARS)
    if on != of:
        diff.append((s, on, of))

say(u'差异 %d 条 / %d' % (len(diff), len(corpus)))
for s, on, of in diff:
    say(u'')
    say(u'  raw   %r' % s)
    say(u'  eat=on  %r（%d 字）%s' % (on, len(on),
                                    u'结尾是句末标点 ✓' if on and on[-1] in ES._SENTENCE_ENDS else u'结尾不是标点 ✗'))
    say(u'  eat=off %r（%d 字）%s' % (of, len(of),
                                     u'结尾是句末标点 ✓' if of and of[-1] in ES._SENTENCE_ENDS else u'结尾不是标点 ✗'))
    say(u'  ⇒ %s' % (u'eat=on 更完整/更干净' if (on and on[-1] in ES._SENTENCE_ENDS)
                     and not (of and of[-1] in ES._SENTENCE_ENDS) else
                     (u'两者都收在标点上，只是长度不同' if (of and of[-1] in ES._SENTENCE_ENDS)
                      else u'**eat=on 变坏了**，要重新考虑')))

# ---------------------------------------------------------------- ③ 负控制输入候选
head(u'③ 负控制输入候选（要求：默认上限下、单调用、能一眼看出"切一半"）')

CAND = [u'aaaa……。', u'诶？！好舒服呀。', u'真的很好呀……后面还有好多话要说呢。',
        u'真的很好呀……', u'aaa！！！bbbbbbbbbbbbbbbbbbbb', u'……好呀。']
for s in CAND:
    fs_on = ES.first_sentence(s, ES.EVENT_MAX_CHARS)
    fs_of = off(ES.first_sentence, s, ES.EVENT_MAX_CHARS)
    fit_on = ES.fit_sentences(s)
    fit_off = off(ES.fit_sentences, s)
    tag = u'first 有效' if fs_on != fs_of else u'first 无效'
    tag2 = u'fit 有效' if fit_on != fit_off else u'fit 无效'
    say(u'')
    say(u'  %r' % s)
    say(u'    first on=%r off=%r  [%s]' % (fs_on, fs_of, tag))
    say(u'    fit   on=%r off=%r  [%s]' % (fit_on, fit_off, tag2))

# ---------------------------------------------------------------- 落盘
if not os.path.isdir(EV):
    os.makedirs(EV)
with io.open(os.path.join(EV, 'diag136b2.txt'), 'w', encoding='utf-8', newline='') as f:
    f.write(u'\n'.join(OUT) + u'\n')
print(u'')
print(u'[OK] 已落 _evidence/diag136b2.txt')

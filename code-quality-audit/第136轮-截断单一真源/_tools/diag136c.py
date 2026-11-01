# -*- coding: utf-8 -*-
"""第136轮附诊断（三）：`round6_verify B7` 报红之后，重新量三条路。

## 起因

`B7` 是第六轮就写下的契约（`verify_round6_fixes.py` 181 行）：

    F_speech(s10, "timer")  # 自主开口
    reply = "主人好久没跟我说话啦，是不是很忙呀？要不要休息一下呢？"
    期望 shown[0][1] == "主人好久没跟我说话啦，是不是很忙呀？"     ← **只取第一句**

本轮把内联换成 `fit_sentences`（"能塞进 40 字的最长完整句群"）之后，两句都留下了 ⇒ B7 报红。
**红得对**：本轮的任务是"统一实现"，不是"改显示行为"。

## 要回答的问题

1. `first_sentence(t, 40)`（**同一个函数、不同上限**）在 B7 那条上是否与老契约逐字一致？
2. 在 84 条真实语料上，`first_sentence(t, 40)` 相对旧内联：
   - 吊尾巴是否归零？
   - "被切短"的条数里，有多少是**旧内联本来就在吊尾巴**（那是修复），
     有多少是**旧内联保留了整段、现在被切掉后半**（那是损失）？
3. `fit_sentences` 的唯一优势（多留一句）是否值得破坏 B7？
"""
import io
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
LIMIT = 40


def say(s=u''):
    OUT.append(s)
    print(s)


def head(t):
    say(u'')
    say(u'=' * 78)
    say(t)


def old_inline(text, limit=LIMIT):
    if not isinstance(text, str):
        return u''
    for sep in (u'\n', u'。', u'！', u'？', u'!', u'?'):
        if sep in text:
            h = text.split(sep, 1)[0].strip()
            if h:
                text = h + (u'' if sep == u'\n' else sep)
            break
    if len(text) > limit:
        text = text[:limit]
    return text


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
corpus = [(r.get('reply') or u'') for r in rows(LIVE)]
corpus += [(r.get('raw') or u'') for r in rows(EV133)]

ENDS = ES._SENTENCE_ENDS


def tail(s, limit=LIMIT):
    return bool(s) and (s[-1] not in ENDS) and len(s) >= limit - 2


# ---------------------------------------------------------------- ① B7 那条
head(u'① `round6_verify B7` 那条输入：三条实现各给什么')
B7 = u'主人好久没跟我说话啦，是不是很忙呀？要不要休息一下呢？'
say(u'  reply   %r（%d 字）' % (B7, len(B7)))
o = old_inline(B7)
f1 = ES.first_sentence(B7, LIMIT)
f2 = ES.fit_sentences(B7, LIMIT)
say(u'  旧内联          %r（%d 字）' % (o, len(o)))
say(u'  first_sentence  %r（%d 字）  %s' % (f1, len(f1), u'== 旧内联 ✓' if f1 == o else u'!= 旧内联 ✗'))
say(u'  fit_sentences   %r（%d 字）  %s' % (f2, len(f2), u'== 旧内联 ✓' if f2 == o else u'!= 旧内联 ✗'))
say(u'')
say(u'  B7 期望的正是旧内联那 24 字 ⇒ `first_sentence(t, 40)` **满足既有契约**。')

# ---------------------------------------------------------------- ② 84 条对照
head(u'② 84 条真实语料：`first_sentence(t, 40)` vs 旧内联（逐条归因）')
news = [ES.first_sentence(s, LIMIT) for s in corpus]
olds = [old_inline(s) for s in corpus]
fits = [ES.fit_sentences(s, LIMIT) for s in corpus]

say(u'  吊尾巴：旧内联 %d 条 ｜ first(40) %d 条 ｜ fit(40) %d 条'
    % (sum(1 for s in olds if tail(s)), sum(1 for s in news if tail(s)),
       sum(1 for s in fits if tail(s))))
say(u'  平均长度：旧 %.1f ｜ first %.1f ｜ fit %.1f'
    % (sum(len(s) for s in olds) / float(len(olds)),
       sum(len(s) for s in news) / float(len(news)),
       sum(len(s) for s in fits) / float(len(fits))))

diff = [(a, b, c, d) for a, b, c, d in zip(corpus, olds, news, fits) if b != c]
say(u'')
say(u'  旧内联 != first(40) 的：%d 条 / %d' % (len(diff), len(corpus)))

gain = [d for d in diff if tail(d[1]) and not tail(d[2])]        # 修掉吊尾巴
loss = [d for d in diff if not tail(d[1]) and len(d[2]) < len(d[1])]  # 变短且旧的不算尾巴
other = [d for d in diff if d not in gain and d not in loss]
say(u'    · 旧的在吊尾巴、新的不吊（**修复**）：%d 条' % len(gain))
say(u'    · 旧的没吊、新的更短（**可能损失**）：%d 条' % len(loss))
say(u'    · 其余（长度不变/变长等）：%d 条' % len(other))

say(u'')
say(u'  【修复样本】')
for raw, a, b, c in gain[:4]:
    say(u'    raw   %r' % raw[:60])
    say(u'      old %r' % a)
    say(u'      new %r' % b)
say(u'  【可能损失样本】')
for raw, a, b, c in loss[:4]:
    say(u'    raw   %r' % raw[:60])
    say(u'      old %r' % a)
    say(u'      new %r' % b)
say(u'  【其余样本】')
for raw, a, b, c in other[:4]:
    say(u'    raw   %r' % raw[:60])
    say(u'      old %r' % a)
    say(u'      new %r' % b)

# ---------------------------------------------------------------- ③ fit 是否值得
head(u'③ `fit_sentences` 比 `first_sentence(t, 40)` 多留了多少？值不值得破坏 B7')
more = [(a, b, c) for a, b, c in zip(corpus, news, fits) if c != b]
say(u'  两者不同的：%d 条 / %d' % (len(more), len(corpus)))
n_multi = 0
for raw, a, b in more:
    # fit 保留了多句？
    extra = len([ch for ch in b if ch in ENDS]) - len([ch for ch in a if ch in ENDS])
    if extra > 0:
        n_multi += 1
say(u'  其中 fit **多保留了一整句以上**的：%d 条' % n_multi)
say(u'  平均多 %+.1f 字' % ((sum(len(c) for c in fits) - sum(len(b) for b in news))
                            / float(len(fits))))
say(u'')
say(u'  ⇒ 这 %d 条多出来的就是"第二句/追问"。B7 明确要求不显示它。' % n_multi)
say(u'     除非本轮**特意**改这条显示口径（那不是"统一实现"，是"改需求"），否则不该留。')

# ---------------------------------------------------------------- 落盘
if not os.path.isdir(EV):
    os.makedirs(EV)
with io.open(os.path.join(EV, 'diag136c.txt'), 'w', encoding='utf-8', newline='') as f:
    f.write(u'\n'.join(OUT) + u'\n')
print(u'')
print(u'[OK] 已落 _evidence/diag136c.txt')

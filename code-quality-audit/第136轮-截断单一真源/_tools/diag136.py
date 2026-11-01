# -*- coding: utf-8 -*-
"""第136轮 · 自主开口那段内联截断 vs `first_sentence(text, 40)` 的 A/B。

**只读 + 纯函数调用，不发请求，不改产品。**

背景：`main.start_autonomous_speech._on_reply` 里有一段**自己写的**截断：

    for sep in ('\\n', '。', '！', '？', '!', '?'):
        if sep in text:
            head = text.split(sep, 1)[0].strip()
            if head:
                text = head + ('' if sep == '\\n' else sep)
            break
    if len(text) > 40:
        text = text[:40]

而事件链路用的是 `event_speech.first_sentence(text, 24)`。
★ 第135轮已确认这两者**不是同一份实现**（sep 顺序不同、上限不同、一个有 MIN 规则一个没有），
  旧注释写的"同源"是假断言。

本节回答两个问题：
  ① 如果把内联那段换成 `first_sentence(text, 40)`，**真实 AI 回复上会变多少条**？
  ② 变了的是哪些形状（是变好还是变坏）？
"""
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'modules'))
import event_speech as ES                                   # noqa: E402

AUTO_MAX = 40          # 自主开口的上限（与内联代码里的 40 一致）
LIVE131 = os.path.join(ROOT, 'code-quality-audit', '第131轮-真机7题复测',
                       '_evidence', 'live7_131.jsonl')
EV133 = os.path.join(ROOT, 'code-quality-audit', '第133轮-事件台词元话语核查',
                     '_evidence', 'event133.jsonl')

BUF = io.StringIO()


def say(m=''):
    print(m)
    BUF.write(u'%s\n' % m)


def rows(p):
    out = []
    with io.open(p, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def old_cut(text, limit=AUTO_MAX):
    """**旧内联实现的快照**（`main.start_autonomous_speech` 里那 8 行）。

    ★ 它不是第二份真源：产品里这段即将被删掉，这里留着只为"证明换掉之后确实有差异 /
      确实没差异"。改它没有任何意义，别把它当契约。
    """
    if not isinstance(text, str):
        return ''
    for sep in (u'\n', u'。', u'！', u'？', u'!', u'?'):
        if sep in text:
            head = text.split(sep, 1)[0].strip()
            if head:
                text = head + (u'' if sep == u'\n' else sep)
            break
    if len(text) > limit:
        text = text[:limit]
    return text


def new_cut(text, limit=AUTO_MAX):
    return ES.first_sentence(text, limit)


def fit_cut(text, limit=AUTO_MAX, min_chars=ES.MIN_FIRST_CHARS):
    """候选方案 C（原型）：取"不超过 limit 的**最长完整句群**"。

    与 `first_sentence` 的语义差别：
      · `first_sentence(t, 24)` = **只要一句**（事件反应）；
      · `fit_cut(t, 40)`        = **能说多少说多少，但必须说完整**（主动搭话）。
    旧内联实现的毛病正是：它既不是"只要一句"（会把整段留下来），也不是"说完整"
    （40 字硬截 ⇒ 吊在半个词上，实测 3/98 条）。
    """
    if not isinstance(text, str):
        return ''
    t = text.strip()
    if not t:
        return ''
    t = t.strip(u'"\'“”「」『』《》').strip()
    if not t:
        return ''
    ends = sorted(i for i, ch in enumerate(t) if ch in ES._SENTENCE_ENDS)
    ok_ends = [i for i in ends
               if len(t[:i] if t[i] == u'\n' else t[:i + 1]) <= limit]
    good = [i for i in ok_ends
            if len((t[:i] if t[i] == u'\n' else t[:i + 1]).strip()) >= min_chars]
    pick = good[-1] if good else (ok_ends[-1] if ok_ends else None)
    if pick is not None and len((t[:pick] if t[pick] == u'\n'
                                 else t[:pick + 1]).strip()) >= min_chars:
        t = t[:pick] if t[pick] == u'\n' else t[:pick + 1]
    elif len(t) > limit:
        t = t[:limit].rstrip(u'，,、。！？!?；;：: ')
    t = t.strip()
    if not t:
        return ''
    import re as _re
    if not _re.search(u'[0-9A-Za-z\\u4e00-\\u9fff]', t):
        return ''
    return t


def main():
    say(u'第136轮 · 自主开口截断：内联实现 vs first_sentence(text, 40)')
    say(u'AUTO_MAX=%d  EVENT_MAX_CHARS=%d  MIN_FIRST_CHARS=%d'
        % (AUTO_MAX, ES.EVENT_MAX_CHARS, ES.MIN_FIRST_CHARS))

    live = rows(LIVE131)
    ev = rows(EV133)
    corpus = [(u'live131/%s#%s' % (r.get('qid'), r.get('sample')), r.get('reply') or u'')
              for r in live]
    corpus += [(u'ev133/%s#%s' % (r.get('kind'), r.get('sample')), r.get('raw') or u'')
               for r in ev]

    # 构造样本：自主开口常见的几种形状
    craft = [
        u'嗯…今天也辛苦了。',
        u'你回来啦。',
        u'诶？你在忙吗？\n\n那我先不吵你。',
        u'你今天话很少，是累了吗？',
        u'我在想，你要不要先喝口水，然后再跟我说说今天的事？我觉得你看起来很累的样子。',
        u'「嘿嘿，被你发现了。」',
        u'……',
        u'。',
        u'',
        u'好呀！',
        u'嗯？',
        u'你今天有没有好好吃饭？我总是有点担心这个。',
        u'a' * 60,
        u'你好。\n第二段。\n第三段。',
    ]
    corpus += [(u'craft/%d' % i, s) for i, s in enumerate(craft)]

    say(u'')
    say(u'=== 语料 ===')
    say(u'  真实 AI 回复 %d 条（live131 %d + ev133 %d）+ 构造 %d 条 = 共 %d'
        % (len(live) + len(ev), len(live), len(ev), len(craft), len(corpus)))

    diff = []
    empty_new = []
    for tag, s in corpus:
        o = old_cut(s)
        n = new_cut(s)
        if o != n:
            diff.append((tag, s, o, n))
        if o and not n:
            empty_new.append((tag, o))

    say(u'')
    say(u'=== ① 变动 ===')
    say(u'  变了 %d 条 / 共 %d 条' % (len(diff), len(corpus)))
    for tag, s, o, n in diff[:20]:
        say(u'  · %s' % tag)
        say(u'      raw(%d)=%r' % (len(s), s[:70]))
        say(u'      old(%d)=%r' % (len(o), o))
        say(u'      new(%d)=%r' % (len(n), n))

    say(u'')
    say(u'=== ② 变空（旧有内容、新变空串）===')
    say(u'  %d 条' % len(empty_new))
    for tag, o in empty_new[:8]:
        say(u'  · %s old=%r' % (tag, o))

    say(u'')
    say(u'=== ③ 长度分布 ===')
    lo = [len(old_cut(s)) for _, s in corpus]
    ln = [len(new_cut(s)) for _, s in corpus]
    say(u'  old: max=%d  超 24 字的有 %d 条' % (max(lo), sum(1 for x in lo if x > 24)))
    say(u'  new: max=%d  超 24 字的有 %d 条' % (max(ln), sum(1 for x in ln if x > 24)))

    say(u'')
    say(u'=== ④ 三路对照：吊尾巴 / 平均长度 / 变空 ===')
    for name, fn in ((u'旧内联', old_cut), (u'A first_sentence(t,40)', new_cut),
                     (u'C fit_cut(t,40)', fit_cut)):
        outs = [fn(s) for _, s in corpus]
        tails = [o for o in outs if o and o[-1] not in ES._SENTENCE_ENDS
                 and len(o) >= AUTO_MAX - 2]
        empt = [1 for (_, s), o in zip(corpus, outs) if s.strip() and not o]
        avg = sum(len(o) for o in outs) / float(len(outs))
        say(u'  %-24s 吊尾巴 %2d 条 · 平均 %5.1f 字 · 变空 %d 条'
            % (name, len(tails), avg, len(empt)))
        if tails:
            say(u'      吊尾巴样本：%r' % (tails[:2],))

    say(u'')
    say(u'=== ⑤ C 方案逐条（与旧内联比，只看变了的）===')
    n_c = 0
    for tag, s in corpus:
        o, c = old_cut(s), fit_cut(s)
        if o != c:
            n_c += 1
            if n_c <= 12:
                say(u'  · %s' % tag)
                say(u'      old(%d)=%r' % (len(o), o))
                say(u'      C  (%d)=%r' % (len(c), c))
    say(u'  C 与旧内联不同的：%d / %d 条' % (n_c, len(corpus)))

    out = os.path.join(EV, 'diag136.txt')
    if not os.path.isdir(EV):
        os.makedirs(EV)
    with io.open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(BUF.getvalue())
    print(u'')
    print(u'[落盘] %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())

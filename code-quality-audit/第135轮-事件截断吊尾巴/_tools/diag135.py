# -*- coding: utf-8 -*-
"""第135轮 · 诊断："吊尾巴"到底怎么产生的，新规则会改动多少条。

**只读 + 纯函数调用，不发请求，不改产品。**

四节：
  ① 复现：第131轮那 3 条真泄漏，`first_sentence(raw, 24)` 现在的输出长什么样；
  ② 归因：现在的句末切分是"按标点**类型**优先级找第一个出现的类型"，
     而不是"取文本里**最靠前**的那个句末标点" ⇒ 第一句是问句、后面某句有句号时，
     会把问号那句 + 后面整段都当成 head，再硬截 24 字 ⇒ 截在半个句子上。
  ③ A/B：42 条真机事件回复 + 3 条泄漏，旧规则 vs 新规则（原型）；
  ④ 残留：新规则下还有多少条要硬截（即"第一句本身就超 24 字"），它们断在哪。
"""
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'modules'))
import event_speech as ES                                   # noqa: E402

LIVE131 = os.path.join(ROOT, 'code-quality-audit', '第131轮-真机7题复测',
                       '_evidence', 'live7_131.jsonl')
EV133 = os.path.join(ROOT, 'code-quality-audit', '第133轮-事件台词元话语核查',
                     '_evidence', 'event133.jsonl')

MAX = ES.EVENT_MAX_CHARS
MIN = ES.MIN_FIRST_CHARS
ENDS = u'。！？!?\n'
SOFT = u'，,、；;：: '

BUF = io.StringIO()


def say(m=''):
    print(m)
    BUF.write(u'%s\n' % m)


def rows(path):
    out = []
    with io.open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def cut_v2(text, max_chars=MAX):
    """候选新规则（原型，**尚未进产品**）。

    与旧规则的唯一区别在**怎么挑切点**：
      旧：按类型优先级 `。`→`！`→`？`→`\n`，看哪个类型先出现在文里，就用它的**第一个下标**；
          于是"第一句是问句、后面有句号"时，切点被推到后面那句的句号上。
      新：把所有句末标点**按位置升序**排，取第一个让 head 长度 ≥ MIN 的切点。
    """
    if not isinstance(text, str):
        return ''
    t = text.strip()
    if not t:
        return ''
    t = t.strip(u'"\'“”「」『』《》').strip()
    if not t:
        return ''
    ends = sorted(i for i, ch in enumerate(t) if ch in ENDS)
    if ends:
        pick = None
        for i in ends:
            head = t[:i] if t[i] == u'\n' else t[:i + 1]
            if len(head.strip()) >= MIN:
                pick = i
                break
        if pick is None:
            # ★ 与原规则的 MIN_FIRST_CHARS 语义对齐：**没有任何切点够长**时，
            #   若全文放得下就整句保留（不然「嗯？发生了什么吗？」会被切成 2 个字）。
            #   第一版原型漏了这条 ⇒ `嗯？（被轻轻戳了一下）` 从 11 字变 2 字（假差异）。
            if len(t) > max_chars:
                pick = ends[-1]
        if pick is not None:
            t = t[:pick] if t[pick] == u'\n' else t[:pick + 1]
    t = t.strip()
    if len(t) > max_chars:
        cut = t[:max_chars]
        soft = max([cut.rfind(c) for c in SOFT] or [-1])
        if soft >= MIN:
            cut = cut[:soft]
        t = cut.rstrip(u'，,、。！？!?；;：: ')
    t = t.strip()
    if not re.search(u'[0-9A-Za-z\\u4e00-\\u9fff]', t):
        return ''
    return t


def looks_tail(s):
    """是不是"吊在半句上"：非空、结尾不是句末标点、且长度顶到上限附近。"""
    if not s:
        return False
    return (s[-1] not in ENDS) and len(s) >= MAX - 2


def main():
    say(u'第135轮 · 事件截断"吊尾巴"诊断')
    say(u'EVENT_MAX_CHARS=%d  MIN_FIRST_CHARS=%d' % (MAX, MIN))

    live = rows(LIVE131)
    leaks = [r for r in live if ES.looks_like_meta_leak(r.get('reply') or '')]
    say(u'')
    say(u'=== ① 复现：3 条真泄漏过现在的 first_sentence ===')
    for r in leaks:
        raw = r['reply']
        old = ES.first_sentence(raw, MAX)
        say(u'  [%s/%s#%s] old(%d)=%r  吊尾巴=%s'
            % (r.get('arm'), r.get('qid'), r.get('sample'), len(old), old,
               looks_tail(old)))
        say(u'     raw 头 40 字 = %r' % raw[:40])

    say(u'')
    say(u'=== ② 归因：旧规则挑中的是哪个标点 ===')
    for r in leaks:
        raw = r['reply'].strip()
        pick_old = None
        for sep in (u'。', u'！', u'？', u'!', u'?', u'\n'):
            if sep in raw:
                pick_old = sep
                break
        first_end = raw[min(i for i, ch in enumerate(raw) if ch in ENDS)] \
            if any(ch in ENDS for ch in raw) else None
        say(u'  [%s#%s] 旧规则选中类型=%r；文本里**最靠前**的句末标点=%r'
            % (r.get('qid'), r.get('sample'), pick_old, first_end))
        if pick_old != first_end:
            say(u'    ★ 跨句了：问号/感叹号在前面，却被后面那个句号拉走')

    say(u'')
    say(u'=== ③ A/B：42 条真机事件回复 + 3 条泄漏 ===')
    ev = rows(EV133)
    diff = []
    for r in ev:
        raw = r.get('raw') or ''
        old = ES.first_sentence(raw, MAX)
        new = cut_v2(raw, MAX)
        if old != new:
            diff.append((r.get('kind'), r.get('sample'), old, new))
    say(u'  42 条里变了 %d 条' % len(diff))
    for kind, smp, old, new in diff[:12]:
        say(u'  · %s #%s' % (kind, smp))
        say(u'      old(%d)=%r' % (len(old), old))
        say(u'      new(%d)=%r' % (len(new), new))

    say(u'')
    say(u'  3 条泄漏：')
    for r in leaks:
        raw = r['reply']
        old = ES.first_sentence(raw, MAX)
        new = cut_v2(raw, MAX)
        say(u'  · %s#%s  old=%r  new=%r  %s'
            % (r.get('qid'), r.get('sample'), old, new,
               u'（变干净了）' if (looks_tail(old) and not looks_tail(new)) else u''))

    say(u'')
    say(u'=== ④ 残留：新规则下还要硬截的有多少条 ===')
    all_rows = [(r.get('raw') or '') for r in ev] + [r['reply'] for r in leaks]
    hard = []
    for raw in all_rows:
        new = cut_v2(raw, MAX)
        if looks_tail(new):
            hard.append(new)
    say(u'  %d / %d 条仍顶到 %d 字且结尾不是句末标点' % (len(hard), len(all_rows), MAX))
    for h in hard[:8]:
        say(u'    %r' % h)

    say(u'')
    say(u'=== ⑤ 空串/过短检查（新规则会不会把话吞掉）===')
    empt = [raw for raw in all_rows if ES.first_sentence(raw, MAX) and not cut_v2(raw, MAX)]
    short = [(ES.first_sentence(raw, MAX), cut_v2(raw, MAX)) for raw in all_rows
             if cut_v2(raw, MAX) and len(cut_v2(raw, MAX)) < MIN]
    say(u'  旧有内容、新变空：%d 条' % len(empt))
    say(u'  新结果短于 MIN(%d)：%d 条' % (MIN, len(short)))
    for a, b in short[:8]:
        say(u'    old=%r  new=%r' % (a, b))

    out = os.path.join(EV, 'diag135.txt')
    if not os.path.isdir(EV):
        os.makedirs(EV)
    with io.open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(BUF.getvalue())
    print(u'')
    print(u'[落盘] %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())

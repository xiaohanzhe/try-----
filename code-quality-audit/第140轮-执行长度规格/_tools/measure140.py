# -*- coding: utf-8 -*-
"""第140轮 · 先量再改：`max_sentences: 3` 这个规格到底有多少条不遵守？

★ 为什么必须先量：第139轮用"句末标点 = `。！？!?…`"切句，得出「>3 句 40/48 = 83.3%」。
   但人设 `ralsei_persona.md` 第 57 行白纸黑字写着——
   「句子说一半停住、用省略号让声音软下来：**很少用，别拿它当句号**」。
   拿 `…` 当句号，等于**用一条人设明确否定的口径去判人设的遵守率**。
   本轮先把这个差量量出来，再决定要不要执行 `max_sentences`。

三个切句器（都"连续标点归一处"，否则 `！！`/`……` 会被数成两三句）：
  A：`。！？!?…` + 换行   —— 复刻第139轮，用来**对齐**那个 83.3%
  B：`。！？!?`  + 换行   —— 人设口径（省略号不算句末）
  C：`。！？!?`  + 换行，且**引号内**的句号也不算 —— 备用，看它会不会更宽
     （C 只在 B 的基础上多一条：`“…”`/`「…」` 里的句末不切）

输出：每个切句器下的句数分布 / >3 句占比 / 若硬砍到 3 句要丢多少字。
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')

RAW30 = os.path.join(ROOT, '第113轮-全体角色AI训练', '_evidence', 'raw30', 'ralsei.jsonl')
AB139 = os.path.join(ROOT, '第139轮-patch与人设去重', '_evidence', 'ab139.jsonl')

END_A = u'\u3002\uff01\uff1f!?\u2026'          # 。！？!?…
END_B = u'\u3002\uff01\uff1f!?'                # 。！？!?
QUOTE_PAIRS = ((u'\u201c', u'\u201d'), (u'\u300c', u'\u300d'), (u'\u300e', u'\u300f'))


def sents(text, endset, skip_in_quote=False):
    """按句末标点切句：连续标点归一处；换行也算句末。返回句子列表（已去空白）。"""
    out = []
    buf = []
    depth = 0
    prev_end = False
    for ch in text or u'':
        if skip_in_quote:
            for op, cl in QUOTE_PAIRS:
                if ch == op:
                    depth += 1
                elif ch == cl and depth > 0:
                    depth -= 1
        is_end = (ch in endset) or (ch == u'\n')
        if is_end and skip_in_quote and depth > 0:
            is_end = False
        buf.append(ch)
        if is_end:
            if prev_end:
                # 连续标点：并进同一句，不另起
                continue
            seg = u''.join(buf).strip()
            if seg:
                out.append(seg)
            buf = []
            prev_end = True
        else:
            if not ch.isspace():
                prev_end = False
    tail = u''.join(buf).strip()
    if tail:
        out.append(tail)
    return [s for s in out if re.search(u'[0-9A-Za-z\u4e00-\u9fff]', s)]


def load_raw30():
    rows = [json.loads(l) for l in io.open(RAW30, encoding='utf-8', newline='') if l.strip()]
    txts = []
    for row in rows:
        for turn in row.get('turns') or []:
            t = (turn.get('final') or u'').strip()
            if t:
                txts.append(t)
    return txts


def load_ab139():
    arms = {}
    for l in io.open(AB139, encoding='utf-8', newline=''):
        if not l.strip():
            continue
        r = json.loads(l)
        if not r.get('reply'):
            continue
        arms.setdefault(r.get('arm'), []).append(r['reply'])
    return arms


def stats(name, txts):
    print()
    print('=== %s（n=%d） ===' % (name, len(txts)))
    print('%-6s %-8s %-10s %-10s %s' % ('切句器', '均句数', '中位', '>3句', '若砍到3句：平均丢字 / 最多丢字'))
    for label, es, sq in (('A 含…', END_A, False),
                          ('B 人设', END_B, False),
                          ('C 去引号', END_B, True)):
        counts, lost = [], []
        for t in txts:
            ss = sents(t, es, sq)
            counts.append(len(ss))
            if len(ss) > 3:
                keep = u''.join(ss[:3])
                lost.append(len(t) - len(keep))
        over = sum(1 for c in counts if c > 3)
        counts_sorted = sorted(counts)
        med = counts_sorted[len(counts_sorted) // 2]
        avg_lost = (float(sum(lost)) / len(lost)) if lost else 0.0
        max_lost = max(lost) if lost else 0
        print('%-8s %-9.2f %-11d %-11s %5.1f / %d' % (
            label, float(sum(counts)) / len(counts), med,
            '%d (%.1f%%)' % (over, 100.0 * over / len(txts)), avg_lost, max_lost))
    return


def main():
    print('raw30 =', os.path.normpath(RAW30))
    print('ab139 =', os.path.normpath(AB139))
    t30 = load_raw30()
    stats(u'第113轮 raw30 真机（48 轮）', t30)

    arms = load_ab139()
    for arm in sorted(arms):
        stats(u'第139轮 A/B 臂 %s' % arm, arms[arm])

    both = arms.get('no1', []) + arms.get('with1', [])
    if both:
        stats(u'第139轮 A/B 两臂合并', both)


if __name__ == '__main__':
    main()

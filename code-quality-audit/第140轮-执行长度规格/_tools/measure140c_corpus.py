# -*- coding: utf-8 -*-
"""第140轮 · 全角色语料（77 份 / 约 5600 轮）上的句数分布 —— 定天花板的真依据。

为什么不用 104 条拍板：`raw30/` 下不是只有 ralsei，**77 个角色各有语料**，
合计五千多轮。`max_sentences` 要管的是全体角色，分母就该是全体。

两个切句集的**分工**（这不是重复定义，是两件事）：
  · 数句子 → 不含 `…`：人设第 57 行「用省略号让声音软下来：别拿它当句号」。
  · 找切点 → 含 `…`：产品既有的 `_SENTENCE_ENDS`，因为切在省略号后面比切在句号上更软。
本脚本只做第一件事（数句子），"切点在哪儿"由产品代码自己负责。
"""
import collections
import glob
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
RAW = os.path.join(ROOT, '第113轮-全体角色AI训练', '_evidence', 'raw30')

COUNT_ENDS = u'\u3002\uff01\uff1f!?\n'      # 数句子：不含省略号


def count_sents(text):
    """数"说了几句"：连续标点归一处；换行算句末；纯标点不算一句。"""
    n = 0
    buf_has_word = False
    started = False
    i, L = 0, len(text or u'')
    in_end = False
    while i < L:
        ch = text[i]
        if ch in COUNT_ENDS:
            if not in_end:
                if started and buf_has_word:
                    n += 1
                started = True
                in_end = True
                buf_has_word = False
            i += 1
            continue
        in_end = False
        if not ch.isspace():
            buf_has_word = True
        i += 1
    if buf_has_word:
        n += 1
    return n


def load_all():
    rows = []
    for p in sorted(glob.glob(os.path.join(RAW, '*.jsonl'))):
        name = os.path.basename(p)[:-6]
        for line in io.open(p, encoding='utf-8', newline=''):
            if not line.strip():
                continue
            rec = json.loads(line)
            for turn in rec.get('turns') or []:
                txt = (turn.get('final') or u'').strip()
                if txt:
                    rows.append((name, txt))
    return rows


def main():
    rows = load_all()
    chars = [len(t) for _, t in rows]
    cnts = [count_sents(t) for _, t in rows]
    n = len(rows)
    print('语料：%d 个角色 / %d 条回复' % (len({k for k, _ in rows}), n))
    print('字数：中位 %d / 均值 %.1f / 最长 %d · >200 字 %d 条（%.1f%%）· >220 字 %d 条'
          % (sorted(chars)[n // 2], float(sum(chars)) / n, max(chars),
             sum(1 for c in chars if c > 200), 100.0 * sum(1 for c in chars if c > 200) / n,
             sum(1 for c in chars if c > 220)))
    dist = collections.Counter(cnts)
    print('句数分布：', ' '.join('%d句:%d' % (k, dist[k]) for k in sorted(dist)))
    print()
    print('%-8s %-10s %-16s %-16s %s' % ('句数', '条数', '占比', '累计（≥该句数）', '这些条的平均字数'))
    for k in sorted(dist):
        ge = sum(v for kk, v in dist.items() if kk >= k)
        avg_c = float(sum(c for c, s in zip(chars, cnts) if s == k)) / dist[k]
        print('%-9d %-11d %-17s %-17s %.1f'
              % (k, dist[k], '%.2f%%' % (100.0 * dist[k] / n),
                 '%d (%.2f%%)' % (ge, 100.0 * ge / n), avg_c))

    print()
    print('=== 天花板扫描：砍到 N 句会动到多少条、丢多少字 ===')
    print('%-8s %-14s %-12s %-12s %s' % ('天花板', '会截的条数', '占比', '平均丢字', '最多丢字'))
    for cap in range(3, 11):
        lost = [c - sum(len(s) for s in _split_keep(t, cap)) for (_, t), c, s in
                [(x, y, cnts[i]) for i, x in enumerate(rows)] if s > cap]
        touched = sum(1 for s in cnts if s > cap)
        print('%-10d %-14d %-12s %-12s %s' % (
            cap, touched, '%.2f%%' % (100.0 * touched / n),
            ('%.1f' % (float(sum(lost)) / len(lost))) if lost else '—',
            max(lost) if lost else '—'))


def _split_keep(text, cap):
    """保留前 cap 句（用于算"砍掉多少字"），切点跟产品一致：句末标点簇整组保留。"""
    out, buf, has_word, started, in_end = [], [], False, False, False
    for ch in text:
        buf.append(ch)
        if ch in COUNT_ENDS:
            if not in_end:
                if started and has_word:
                    out.append(u''.join(buf))
                    buf = []
                started = True
                in_end = True
                has_word = False
            continue
        in_end = False
        if not ch.isspace():
            has_word = True
    if buf and has_word:
        out.append(u''.join(buf))
    return out[:cap]


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""第141轮 · 先量：「念说明」到底长什么样？

第140轮的结论是 **句子数抓不住"话太多"**（6 句那批平均才 150 字，在预算内）。
当时登记的候选指标是「单句过长 / 最长句占比」—— 假设是：
念说明的形态不是"句多"，是**一句话里用逗号串了很长一串**。

本轮先把这个假设量出来，再决定要不要动。三个指标：

  1. `max_sent_len`    每条回复里**最长的那一句**多少字
  2. `long_ratio`      最长句 / 全文（占比高 = 全文就是一句话串下来的）
  3. `comma_chain`     单句里逗号数（≥3 个基本就是"一句串到底"的说明腔）

切句口径：**不含 `…`**（人设第 57 行「别拿它当句号」）—— 与第140轮同一把尺子。
"""
import collections
import glob
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
RAW = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                   '_evidence', 'raw30')

END = u'\u3002\uff01\uff1f!?\n'          # 数句子：不含省略号
COMMAS = u'\uff0c\u3001,;；'


def split(text):
    out, buf, has_word, started, in_end = [], [], False, False, False
    for ch in text:
        buf.append(ch)
        if ch in END:
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
    return out


def pct(vals, p):
    if not vals:
        return 0
    s = sorted(vals)
    k = int(round((len(s) - 1) * p / 100.0))
    return s[k]


def main():
    rows = []
    for p in sorted(glob.glob(os.path.join(RAW, '*.jsonl'))):
        name = os.path.basename(p)[:-6]
        for line in io.open(p, encoding='utf-8', newline=''):
            if not line.strip():
                continue
            rec = json.loads(line)
            for turn in rec.get('turns') or []:
                t = (turn.get('final') or u'').strip()
                if t:
                    rows.append((name, t))

    maxlen, ratios, chains, nsent = [], [], [], []
    long_samples = []
    for name, t in rows:
        ss = split(t)
        if not ss:
            continue
        lens = [len(s) for s in ss]
        mx = max(lens)
        maxlen.append(mx)
        ratios.append(float(mx) / max(1, len(t)))
        nsent.append(len(ss))
        for s in ss:
            c = sum(1 for ch in s if ch in COMMAS)
            chains.append(c)
            if len(s) >= 60:
                long_samples.append((len(s), c, name, s))

    n = len(maxlen)
    print(u'语料：%d 条（%d 个角色）' % (n, len({k for k, _ in rows})))
    print(u'')
    print(u'最长句字数：P50=%d P75=%d P90=%d P95=%d P99=%d max=%d'
          % (pct(maxlen, 50), pct(maxlen, 75), pct(maxlen, 90),
             pct(maxlen, 95), pct(maxlen, 99), max(maxlen)))
    print(u'  分布：≥30 字 %d(%.1f%%) · ≥40 字 %d(%.1f%%) · ≥50 字 %d(%.1f%%) · ≥60 字 %d(%.1f%%)'
          % (sum(1 for v in maxlen if v >= 30), 100.0 * sum(1 for v in maxlen if v >= 30) / n,
             sum(1 for v in maxlen if v >= 40), 100.0 * sum(1 for v in maxlen if v >= 40) / n,
             sum(1 for v in maxlen if v >= 50), 100.0 * sum(1 for v in maxlen if v >= 50) / n,
             sum(1 for v in maxlen if v >= 60), 100.0 * sum(1 for v in maxlen if v >= 60) / n))
    print(u'')
    print(u'最长句占全文：P50=%.2f P90=%.2f P99=%.2f max=%.2f'
          % (pct(ratios, 50), pct(ratios, 90), pct(ratios, 99), max(ratios)))
    print(u'  ≥0.60 的 %d 条(%.1f%%) · ≥0.80 的 %d 条(%.1f%%)'
          % (sum(1 for r in ratios if r >= 0.6), 100.0 * sum(1 for r in ratios if r >= 0.6) / n,
             sum(1 for r in ratios if r >= 0.8), 100.0 * sum(1 for r in ratios if r >= 0.8) / n))
    print(u'')
    print(u'单句逗号数：P50=%d P90=%d P99=%d max=%d'
          % (pct(chains, 50), pct(chains, 90), pct(chains, 99), max(chains)))
    print(u'  句子里 ≥3 个逗号的占 %.1f%%（句数分母 %d）'
          % (100.0 * sum(1 for c in chains if c >= 3) / len(chains), len(chains)))
    print(u'')
    print(u'--- 最长句 ≥60 字的样本（最多 12 条，按长度倒序） ---')
    for ln, c, name, s in sorted(long_samples, reverse=True)[:12]:
        print(u'  [%d 字 / %d 逗号] %-14s %s' % (ln, c, name, s.replace(u'\n', u' ')[:90]))

    ev = {
        'replies': n,
        'max_sent_len': {'p50': pct(maxlen, 50), 'p90': pct(maxlen, 90),
                         'p99': pct(maxlen, 99), 'max': max(maxlen),
                         'ge30': sum(1 for v in maxlen if v >= 30),
                         'ge40': sum(1 for v in maxlen if v >= 40),
                         'ge50': sum(1 for v in maxlen if v >= 50),
                         'ge60': sum(1 for v in maxlen if v >= 60)},
        'long_ratio': {'p50': round(pct(ratios, 50), 3), 'p90': round(pct(ratios, 90), 3),
                       'ge60_pct': round(100.0 * sum(1 for r in ratios if r >= 0.6) / n, 1),
                       'ge80_pct': round(100.0 * sum(1 for r in ratios if r >= 0.8) / n, 1)},
        'comma_chain': {'p50': pct(chains, 50), 'p90': pct(chains, 90),
                        'p99': pct(chains, 99), 'max': max(chains),
                        'ge3_pct': round(100.0 * sum(1 for c in chains if c >= 3) / len(chains), 1)},
        'samples_ge60': [{'chars': ln, 'commas': c, 'npc': name, 'text': s}
                         for ln, c, name, s in sorted(long_samples, reverse=True)[:12]],
    }
    evd = os.path.join(ROUND, '_evidence')
    if not os.path.isdir(evd):
        os.makedirs(evd)
    with io.open(os.path.join(evd, 'sentence_len141.json'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print(u'')
    print(u'已落盘：', os.path.join(evd, 'sentence_len141.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())

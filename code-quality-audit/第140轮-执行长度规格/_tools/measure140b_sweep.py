# -*- coding: utf-8 -*-
"""第140轮 · 句数上限该定在哪：3 / 4 / 5 / 6 / 7 / 8 各自会动到多少条、砍掉多少字。

★ 为什么不是"照着 max_sentences 写 3"：
   `_clean_ai_reply` 的第 3 步只能**截断**（不能重采样，否则 65% 的回复都要重来）。
   截断砍掉的是**结尾**，而人设要求的「先接住、再补一句我自己的感受」正好在结尾 ——
   照着目标值 3 砍，等于系统性地把"感受"那半句削掉，比话长更伤人。
   所以 3 只能是**目标**，真正落地的必须是明显高于目标的**硬天花板**。

本脚本只回答一个问题：天花板取多少，才既能抓住"念说明"的跑飞，又不碰正常回复。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from measure140 import (END_B, load_raw30, load_ab139, sents)  # noqa: E402


def sweep(name, txts):
    print()
    print('=== %s（n=%d，切句器 B＝人设口径：省略号不算句末） ===' % (name, len(txts)))
    counts = [len(sents(t, END_B)) for t in txts]
    chars = [len(t) for t in txts]
    print('句数分布 %r' % ({k: counts.count(k) for k in sorted(set(counts))}))
    print('字数  中位 %d / 最长 %d / 落在 200~220 的 %d 条'
          % (sorted(chars)[len(chars) // 2], max(chars),
             sum(1 for c in chars if 200 < c <= 220)))
    print()
    print('%-8s %-10s %-14s %s' % ('天花板', '会截的条数', '平均丢字', '其中丢得最多的'))
    for cap in range(3, 9):
        touched, lost = 0, []
        for t in txts:
            ss = sents(t, END_B)
            if len(ss) > cap:
                touched += 1
                lost.append(len(t) - len(u''.join(ss[:cap])))
        avg = (float(sum(lost)) / len(lost)) if lost else 0.0
        print('%-10d %-12s %-15s %s' % (
            cap, '%d (%.0f%%)' % (touched, 100.0 * touched / len(txts)),
            ('%.1f 字' % avg) if lost else '—',
            ('%d 字' % max(lost)) if lost else '—'))


def main():
    sweep(u'第113轮 raw30 真机（48 轮）', load_raw30())
    arms = load_ab139()
    both = arms.get('no1', []) + arms.get('with1', [])
    if both:
        sweep(u'第139轮 A/B 两臂合并（56 条）', both)


if __name__ == '__main__':
    main()

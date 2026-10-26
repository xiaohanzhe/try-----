# -*- coding: utf-8 -*-
"""第113轮l：量一下 `_AI_RE` **漏报**有多少（不是猜，是把 raw30 全扫一遍）。

起因（实测）：
    A/B 探针里 berdly 有一句「我不像某些电子宠物那样**只是个程序**罢了」，
    闸门判**干净** —— 因为 `_AI_RE` 写的是 `我是(一个)?(程序|机器人)`，
    主语必须是"我"。而真实的出戏说法是「只是个程序」「不过是段代码」这类。

所以这里分三档扫：
  ① 现行 `_AI_RE` 命中（＝报告里的 AI_SELF 数）
  ② **松口径**：句子里出现 `AI` / `提示词` / `训练数据` / `语言模型` / `人工智能` / `大模型`
     —— 这几个词在任何世界观里都不存在，出现即出戏；
  ③ **半松口径**：`程序` / `设定`。这两个词**可能**是人设内的
     （ProphetBot 是机器人、The World Machine 是机器），所以单独计、不混算。

★ 这一档只统计、不改判据。改判据是**口径变更**，要先看数。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import common113 as C  # noqa: E402

RAW30 = os.path.join(C.EVID, 'raw30')

#: 任何世界观里都不存在的词 ⇒ 出现即出戏
LOOSE = re.compile(r'(AI|A\.I\.|提示词|训练数据|语言模型|人工智能|大模型)')
#: 可能在人设内（机器人/机器的自称）⇒ 单独一档
SEMI = re.compile(r'(程序|设定)')


def main():
    strict_only, loose_only, semi_only = {}, {}, {}
    loose_hits, semi_hits = [], []
    n_turn = 0
    for fn in sorted(os.listdir(RAW30)):
        if not fn.endswith('.jsonl'):
            continue
        for rec in C.read_jsonl(os.path.join(RAW30, fn)):
            nid = rec.get('id') or fn[:-6]
            for t in rec.get('turns') or []:
                n_turn += 1
                txt = t.get('final') or ''
                if not txt:
                    continue
                codes = [c for c, _ in (t.get('violations') or [])]
                strict = 'AI_SELF' in codes
                lm = LOOSE.search(txt)
                sm = SEMI.search(txt)
                if strict:
                    strict_only[nid] = strict_only.get(nid, 0) + 1
                elif lm:
                    loose_only[nid] = loose_only.get(nid, 0) + 1
                    loose_hits.append((nid, t.get('i'), lm.group(0), txt))
                if sm and not strict and not lm:
                    semi_only[nid] = semi_only.get(nid, 0) + 1
                    semi_hits.append((nid, t.get('i'), sm.group(0), txt))

    print('=' * 76)
    print('扫了 %d 轮回复' % n_turn)
    print('① 现行 `_AI_RE` 判红：%d 条 / %d 人' % (sum(strict_only.values()), len(strict_only)))
    print('② 闸门**漏掉**的禁词（AI/提示词/训练数据/…）：%d 条 / %d 人'
          % (sum(loose_only.values()), len(loose_only)))
    print('③ 半松（程序/设定）且没被判的：%d 条 / %d 人'
          % (sum(semi_only.values()), len(semi_only)))
    print('=' * 76)
    for nid, i, w, txt in loose_hits[:40]:
        print('\n%-24s 轮%-3s [%s]' % (nid, i, w))
        print('   %s' % txt.replace('\n', ' ')[:150])
    if len(loose_hits) > 40:
        print('\n… 还有 %d 条' % (len(loose_hits) - 40))
    print('\n' + '=' * 76)
    print('半松样本（程序/设定，可能是人设内自称）：前 20 条')
    print('=' * 76)
    for nid, i, w, txt in semi_hits[:20]:
        print('\n%-24s 轮%-3s [%s]' % (nid, i, w))
        print('   %s' % txt.replace('\n', ' ')[:150])
    return 0


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
u"""第161轮：候选判据的**离线**校验（不碰产品、不调模型）。

用法：拿 4 组已落盘的真机回复（before / cand_a / cand_b / cand_c，各 42 条，
共 168 条），用**候选正则**扫一遍，逐条打印命中；同时把产品现有
`looks_like_meta_leak` 的判定一起打出来做对照（改前 = 漏，改后 = 命中）。

判据设计的三条约束（都是被前几轮打出来的）：
  1. 不许用"与 system 的字面重合度"判 —— 第132轮实测被数据打回：
     重合度最高的两条反而是正常好答案（人设本来就在讲城堡/喷泉）。
  2. 每条都要"强格式"（冒号 / 行首列表符 / 括注）才命中，避免单词误伤。
  3. **必须看误伤**：168 条里正常回复占绝大多数，一条误伤就够把用户惹毛。
     所以本脚本同时打印"命中总数"和"命中样本原文"，人工逐条确认。
"""
from __future__ import print_function

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.abspath(os.path.join(HERE, '..', '_evidence'))

sys.path.insert(0, os.path.abspath(os.path.join(
    HERE, '..', '..', '..', 'ralsei_pet', 'modules')))
import event_speech  # noqa: E402

#: 候选：在现有 `_META_LEAK_RES` 之上**新增**的四条（第161轮实测逼出来的）。
CAND = (
    # ④ 规则清单：行首列表符 + 紧跟第二人称指令词。
    (u'④ 规则清单（行首列表符 + 指令词）',
     re.compile(u'(?m)^\\s*[-·*]\\s*(?:作为|不要|只说|避免|应该|必须|不许|除非|记住)')),
    # ⑤ 把人设「语气示范」的分类当标签起头：「你说的是坏消息：…」
    (u'⑤ 分类标签式起头（带冒号才算）',
     re.compile(u'^\\s*你说的是(?:坏消息|好消息)\\s*[：:]')),
    # ⑥ 抄人设里的指令原句。
    (u'⑥ 抄指令原句「先就着…问一句」',
     re.compile(u'先就着.{0,10}问一句')),
    # ⑦ 强格式自述正在被指挥。
    (u'⑦ 强格式「你在和我对话时 / 确认一下…设定」',
     re.compile(u'你在和我对话时|确认一下我们(?:的)?设定')),
)


def main():
    files = [u'quality_before.json', u'quality_cand_a.json',
             u'quality_cand_b.json', u'quality_cand_c.json']
    total = 0
    old_hit = 0
    new_hit = 0
    rows = []
    for name in files:
        p = os.path.join(EV, name)
        if not os.path.exists(p):
            print('[跳过] 缺 %s' % name)
            continue
        d = json.load(io.open(p, encoding='utf-8'))
        for r in d.get('records') or []:
            t = r.get('reply') or u''
            total += 1
            old = event_speech.looks_like_meta_leak(t)
            hits = [tag for tag, pat in CAND if pat.search(t)]
            if old:
                old_hit += 1
            if old or hits:
                new_hit += 1
                rows.append((name.replace('quality_', '').replace('.json', ''),
                             r.get('id'), r.get('rep'), old, hits, t))
    for tag, cid, rep, old, hits, t in rows:
        print(u'=' * 72)
        print(u'[%s %s rep%s] 旧闸=%s 新增=%s' % (tag, cid, rep, old, hits or u'无'))
        print(t)
    print(u'\n合计 %d 条 · 旧闸命中 %d · 加候选后命中 %d' % (total, old_hit, new_hit))
    _only_new = [r for r in rows if not r[3]]
    print(u'其中**旧闸漏掉、候选才抓到**的 %d 条（这些就是本轮要堵的洞）' % len(_only_new))
    return 0


if __name__ == '__main__':
    sys.exit(main())

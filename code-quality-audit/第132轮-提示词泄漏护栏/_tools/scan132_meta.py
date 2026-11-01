# -*- coding: utf-8 -*-
"""第132轮 · 取证二：用"元语言标记"而不是"字面重合"来识别念规则（零网络）。

## 为什么不用重合度

`scan132_leak.py` 已经证明它不行：after 组两条**好答案**的 `lcs_flat` 是 13/17、
`n6` 是 11/12，而**真正的泄漏**（before/Q7#2）只有 10/11 —— 因为人设本身就在讲
"城堡/喷泉/角色/Deltarune"，好回复用同一批词，重合度天然高。
⇒ **重合度抓不住"念规则"，只会误伤"说正事"。**

## 改抓什么

泄漏的共同点是**元语言**：回复在谈论"我该怎么说话"，或把规则/模板当台词引用。
按可复核的**结构特征**列候选（每条都写成"必须同时出现的两件事"，防单词误伤）：

  M1 `我不该` + 说话类词（开头/说/问/留/语气）   ← before/Q7#2 命中
  M2 `我该说` / `我应该说` / `我本该`             ← 元话语最强形态
  M3 `问一句：` / `留个"我在"` / `留个“……的意思”`  ← 直接引用模板
  M4 括注解释 `（这里…）` `（这样…）` `（注：…）`   ← after/Q3#3 命中
  M5 `而不是(直接)?(给|说|讲)` + `建议|道理|方案`   ← 复述"别给建议"这条规则

## 本脚本只做一件事

把 42 条逐条过这 5 条，**打印命中位置与上下文**，供人工确认"是不是真泄漏"。
不设阈值、不下结论 —— 阈值要等看清命中再说。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV131 = os.path.join(ROOT, 'code-quality-audit', '第131轮-真机7题复测', '_evidence')
EV = os.path.join(ROUND, '_evidence')
JSONL = os.path.join(EV131, 'live7_131.jsonl')

RULES = [
    ('M1', u'我不该', u'开头|说|问|留|语气'),
    ('M2', u'我该说|我应该说|我本该|我本可以', u''),
    ('M3', u'问一句[：:]|留个|的意思', u''),
    ('M4', u'[（(]\\s*(这里|这样|这是|以上|注)', u''),
    ('M5', u'而不是', u'建议|道理|方案|安慰'),
]


def hits(text):
    out = []
    for name, p1, p2 in RULES:
        if not re.search(p1, text):
            continue
        if p2 and not re.search(p2, text):
            continue
        m = re.search(p1, text)
        out.append((name, m.group(0), text[max(0, m.start() - 12):m.start() + 26]))
    return out


def main():
    rows = [json.loads(l) for l in io.open(JSONL, encoding='utf-8') if l.strip()]
    print('[数据] %d 条' % len(rows))
    print('')
    flagged = []
    for r in rows:
        rep = r['reply'] or ''
        h = hits(rep)
        if h:
            flagged.append((r, h))
    print('[命中] %d / %d 条' % (len(flagged), len(rows)))
    print('')
    for r, h in flagged:
        print('--- %s/%s#%d  (%d 字)' % (r['arm'], r['qid'], r['sample'], len(r['reply'])))
        for name, tok, ctx in h:
            print('    %s 命中 %r' % (name, tok))
            print('        …%s…' % ctx.replace('\n', ' '))
        print('    全文：%s' % r['reply'].replace('\n', ' / ')[:220])
        print('')

    # 按规则名统计，看哪条最"专"
    from collections import Counter
    c = Counter(n for _r, h in flagged for n, _t, _c in h)
    print('[按规则] %s' % dict(c))

    with io.open(os.path.join(EV, 'leak_meta_132.json'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write(json.dumps([{'arm': r['arm'], 'qid': r['qid'], 'sample': r['sample'],
                             'reply': r['reply'],
                             'hits': [{'rule': n, 'tok': t, 'ctx': c2}
                                      for n, t, c2 in h]} for r, h in flagged],
                           ensure_ascii=False, indent=1))
    print('')
    print('[落盘] %s' % os.path.join(EV, 'leak_meta_132.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""A/B：同一条模型输出，产品护栏 vs 训练判据，各自怎么判。

目的：证明「硬违规 2/48」是不是假数（判据过窄 ⇒ 漏报）。
"""
import io
import json
import os
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
sys.path.insert(0, os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools'))

from modules.event_speech import strip_action_parentheticals   # noqa: E402
import common113 as C                                          # noqa: E402

# 真实模型输出（取自 transcripts30/susie.md，一字未改）
CASES = [
    ('第1轮', '烦死了。（你皱起眉头看着屏幕那边的人，“你别这么盯着我看。我才没空想东想西的！”）'),
    ('第3轮', '好吧……早上起来，先啃点东西充饥。然后就是各种捣乱和惹事。'
              '（你轻描淡写地说道）不过到了晚上就得跟朋友们一起开夜车打怪什么的……挺忙活的一天嘛！'),
    ('第4轮', '哈，你说那个啊。（你的目光闪烁了一下，“有时候确实会沉迷进去好几个小时……'
              '不过那都是晚上没人打扰的时候。”）“你要是觉得无聊了，可以试着搜搜攻略什么的，'
              '挺有意思的。反正我技术也不咋样。”'),
    ('第6轮', '嗯……其实我没特别想留下的地方。（你的目光游离，“不过有时候啊，'
              '在黑暗世界里的那个湖边挺好的。那儿安静，跟谁都挺好。”）“你懂的……那种没人的感觉。”'),
]

print('训练判据 _PAREN_RE =', C._PAREN_RE.pattern)
print()
for tag, text in CASES:
    m = C._PAREN_RE.search(text)
    train_hit = bool(m)
    prod = strip_action_parentheticals(text)
    print('--- %s' % tag)
    print('   原文      : %s' % text[:60])
    print('   训练判据  : %s%s' % ('报违规' if train_hit else '★ 放行（漏报）',
                                  ('  ' + m.group(0)[:40]) if m else ''))
    print('   产品护栏  : %s' % ('空 ⇒ 判无效' if not prod else prod[:60]))
    print()

# -*- coding: utf-8 -*-
u"""第148轮 · 补量：那 2 条兜底为什么**没有**切在词中间。

三种可能，逐个排：
 A 第 mc 位正好是空格 / 标点 ⇒ 天然在边界上；
 B 第 mc 位是 ASCII 词字符，但 `_hard_cut` 的底线把它挡回去了（keep 不够长）；
 C 这条压根不是英文单词流（数字/符号/全大写拼写之外的东西）。
"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
RAW = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                   '_evidence', 'raw30')
CARDS = os.path.join(PET, 'assets', 'npc', '_training', 'cards')

sys.path.insert(0, PET)
from modules import event_speech as ES          # noqa: E402

V0 = (u'\u3002', u'\uff01', u'\uff1f', u'!', u'?', u'\n')
CJK = re.compile(u'[\u4e00-\u9fff]')


def _src(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _cut(t, mc):
    cut = -1
    dot = t.rfind(u'.', 0, mc)
    while dot > 0 and dot + 1 < len(t) and t[dot + 1].isdigit():
        dot = t.rfind(u'.', 0, dot)
    if dot > cut:
        cut = dot
    for sep in V0:
        i = t.rfind(sep, 0, mc)
        if i > cut:
            cut = i
    return cut


cards = {}
for p in sorted(glob.glob(os.path.join(CARDS, '*.json'))):
    try:
        d = json.loads(_src(p))
    except Exception:
        continue
    mc = (d.get('length_policy') or {}).get('max_chars')
    if isinstance(mc, int) and mc > 0:
        cards[os.path.basename(p)[:-5]] = mc

fall = []
for p in sorted(glob.glob(os.path.join(RAW, '*.jsonl'))):
    name = os.path.basename(p)[:-6]
    mc = cards.get(name, 220)
    for line in io.open(p, encoding='utf-8', newline=''):
        if not line.strip():
            continue
        for turn in (json.loads(line).get('turns') or []):
            t = (turn.get('final') or u'').strip()
            if t and len(t) > mc and _cut(t, mc) <= 0:
                lang = 'zh' if len(CJK.findall(t)) >= 0.3 * len(t) else 'en'
                fall.append((name, mc, t, lang))

print(u'兜底 %d 条' % len(fall))
for name, mc, t, lang in fall:
    head, tail = t[:mc], t[mc:]
    print(u'')
    print(u'[%s/%s] len=%d mc=%d' % (name, lang, len(t), mc))
    print(u'  t[mc-12:mc] = %r' % (t[mc - 12:mc],))
    print(u'  t[mc]       = %r  in _WORDY=%s' % (t[mc], t[mc] in ES._WORDY))
    print(u'  t[mc-1]     = %r  in _WORDY=%s' % (t[mc - 1], t[mc - 1] in ES._WORDY))
    print(u'  old tail    = %r' % (head.strip()[-30:],))
    print(u'  new tail    = %r' % (ES._hard_cut(t, mc).strip()[-30:],))
    sp = head.rstrip(ES._HARD_CUT_TAIL).rfind(u' ')
    keep = head.rstrip(ES._HARD_CUT_TAIL)[:sp] if sp > 0 else u''
    print(u'  最后一个空格在 %d，keep 长 %d，半预算=%d，MIN=%d ⇒ 够不够：%s'
          % (sp, len(keep), mc // 2, ES.MIN_FIRST_CHARS,
             bool(keep) and len(keep.strip()) >= ES.MIN_FIRST_CHARS
             and len(keep) * 2 >= mc))
    print(u'  是不是"英文字母流"：字母占比 %.2f，空格数 %d'
          % (sum(1 for c in t if c.isalpha()) / float(len(t)), t.count(u' ')))

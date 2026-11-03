# -*- coding: utf-8 -*-
u"""第148轮 · 第一量：对话链（200 字）兜底硬截到底是什么规模，退到词边界能改多少。

## 为什么要先量

第147轮把**事件链（24）/ 自主开口（40）**的兜底改成了"退到最后一个空格"。
但 `src/main.py` 的 `_clean_ai_reply` 里还有**第 4 处**硬截：

```python
cut = -1
...（扫 `.`、`。！？!?\\n`，取最靠后的切点）...
t = (t[:cut + 1] if cut > 0 else t[:max_chars]).strip()
                          ^^^^^^^^^^^^ 这里
```

第143轮实测"补 `.` 之后英文残留 **2 条**"。2 条听起来不值一轮 —— 但它有第二个价值：
**147 的主张是"一处实现取代三处复刻"，留着第 4 处那句话就是半真**。

## 量什么

对 77 人 / 5592 条真机回复里**超 max_chars** 的那批：
1. 有多少条走到 `cut <= 0` 这条兜底（按语言拆）；
2. 旧兜底 `t[:mc]` vs 新兜底 `_hard_cut(t, mc)` 改了几条；
3. 旧的是不是真"切在词中间"、新的还是不是（**两边都数**，不许只报好消息）。

★ 只读仓库内冻结语料（`第113轮/_evidence/raw30`），不碰产品、不写盘到工作区。
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
EVID = os.path.join(ROUND, '_evidence')

sys.path.insert(0, PET)
from modules import event_speech as ES          # noqa: E402

V0 = (u'\u3002', u'\uff01', u'\uff1f', u'!', u'?', u'\n')
CJK = re.compile(u'[\u4e00-\u9fff]')


def _src(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def say(s):
    sys.stdout.write(s + u'\n')


def _cut(t, mc):
    u"""与 `main._clean_ai_reply` 第 3 步**同构**：先 `.`（带小数守卫），再 V0，取最靠后。"""
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


def _midword(t, r):
    u"""结果 `r` 的末尾是不是"切在 ASCII 词中间"（与第147轮同口径）。"""
    if not r or len(r) >= len(t):
        return False
    return r[-1] in ES._WORDY and t[len(r)] in ES._WORDY


def main():
    cards = {}
    for p in sorted(glob.glob(os.path.join(CARDS, '*.json'))):
        try:
            d = json.loads(_src(p))
        except Exception:
            continue
        mc = (d.get('length_policy') or {}).get('max_chars')
        if isinstance(mc, int) and mc > 0:
            cards[os.path.basename(p)[:-5]] = mc

    over = []
    for p in sorted(glob.glob(os.path.join(RAW, '*.jsonl'))):
        name = os.path.basename(p)[:-6]
        mc = cards.get(name, 220)
        for line in io.open(p, encoding='utf-8', newline=''):
            if not line.strip():
                continue
            for turn in (json.loads(line).get('turns') or []):
                t = (turn.get('final') or u'').strip()
                if not t or len(t) <= mc:
                    continue
                lang = 'zh' if len(CJK.findall(t)) >= 0.3 * len(t) else 'en'
                over.append({'id': name, 'mc': mc, 't': t, 'lang': lang})

    say(u'超 max_chars 的回复：%d 条（中文 %d / 英文 %d）' % (
        len(over),
        len([s for s in over if s['lang'] == 'zh']),
        len([s for s in over if s['lang'] == 'en'])))

    fall = [s for s in over if _cut(s['t'], s['mc']) <= 0]
    say(u'走到兜底（`cut <= 0`）：%d 条（中文 %d / 英文 %d）' % (
        len(fall),
        len([s for s in fall if s['lang'] == 'zh']),
        len([s for s in fall if s['lang'] == 'en'])))
    say(u'')

    changed = []
    old_mid = new_mid = 0
    for s in fall:
        old = s['t'][:s['mc']].strip()
        new = ES._hard_cut(s['t'], s['mc']).strip()
        if _midword(s['t'], old):
            old_mid += 1
        if _midword(s['t'], new):
            new_mid += 1
        if old != new:
            changed.append({'id': s['id'], 'lang': s['lang'], 'len': len(s['t']),
                            'old': old[-24:], 'new': new[-24:],
                            'lost': len(old) - len(new)})

    say(u'旧兜底切在词中间：%d / %d' % (old_mid, len(fall)))
    say(u'新兜底切在词中间：%d / %d' % (new_mid, len(fall)))
    say(u'行为变化：%d 条（中 %d / 英 %d）' % (
        len(changed),
        len([c for c in changed if c['lang'] == 'zh']),
        len([c for c in changed if c['lang'] == 'en'])))
    if changed:
        _lost = [c['lost'] for c in changed]
        say(u'  平均少 %d 字，最多少 %d 字，最少少 %d 字'
            % (sum(_lost) / len(_lost), max(_lost), min(_lost)))
    for c in changed[:8]:
        say(u'   [%s/%s] len=%d −%d  …%r → …%r'
            % (c['id'], c['lang'], c['len'], c['lost'], c['old'], c['new']))

    out = {
        'over': len(over),
        'over_zh': len([s for s in over if s['lang'] == 'zh']),
        'over_en': len([s for s in over if s['lang'] == 'en']),
        'fallback': len(fall),
        'fallback_zh': len([s for s in fall if s['lang'] == 'zh']),
        'fallback_en': len([s for s in fall if s['lang'] == 'en']),
        'old_midword': old_mid,
        'new_midword': new_mid,
        'changed': len(changed),
        'changed_zh': len([c for c in changed if c['lang'] == 'zh']),
        'changed_en': len([c for c in changed if c['lang'] == 'en']),
        'lost_avg': (sum(c['lost'] for c in changed) // len(changed)) if changed else 0,
        'samples': changed[:8],
    }
    if not os.path.isdir(EVID):
        os.makedirs(EVID)
    with io.open(os.path.join(EVID, 'measure148.json'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    say(u'')
    say(u'证据已落 `_evidence/measure148.json`')


main()

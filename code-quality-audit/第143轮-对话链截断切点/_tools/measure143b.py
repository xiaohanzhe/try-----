# -*- coding: utf-8 -*-
"""第143轮 · 第二量：`cut == -1` 的那 61 条到底是"谁"（中文还是英文），
以及补 ASCII `.` 到底能解掉多少。

## 为什么必须拆语言

`measure143.py` 的结果里，硬截样例**全是英文**（`hy_bowll` 连着 5 条）。
如果 61 条全是英文，那这条缺陷的**真实名字不是"缺 `…`"，是"缺 ASCII `.`"** ——
和第141轮登记的遗留 ②「英文角色长度指标全失真（先补 ASCII `.`）」是**同一根因**。
如果不拆就直接把 `…` 补进切点集，等于治错了病（实测只解掉 2/61）。

## 四个变体（互相做对照，不许只看最好那个）

| 变体 | 切点集 |
|---|---|
| V0 | `。！？!?\\n`            —— 现状 |
| V1 | V0 + `…`               —— 第141轮遗留 ① 的方案 |
| V2 | V0 + `.`               —— 第141轮遗留 ② 的方案 |
| V3 | V0 + `…` + `.`         —— 两个都补 |

## 补 `.` 的风险（必须一起量，否则就是"只报好消息"）

ASCII `.` 在正文里不只是句号：`3.14` / `Mr. Smith` / `e.g.` / 网址 / 省略号 `...`。
判据：切点那个 `.` 的**前一个字符是数字或字母、后一个是小写字母或数字** ⇒ 记一个"疑似非句末点"。
（这是**上界**估计：真在 200 字处切到 `3.1|4` 才是真出事，这里先全记下来。）
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
EVID = os.path.join(ROUND, '_evidence')
CARDS = os.path.join(PET, 'assets', 'npc', '_training', 'cards')

V0 = (u'\u3002', u'\uff01', u'\uff1f', u'!', u'?', u'\n')
ELL = u'\u2026'
DOT = u'.'

CJK = re.compile(u'[\u4e00-\u9fff]')


def _src(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def say(s):
    sys.stdout.write(s + u'\n')


def _cut(t, mc, seps):
    cut = -1
    for sep in seps:
        i = t.rfind(sep, 0, mc)
        if i > cut:
            cut = i
    return cut


def _risky_dot(t, i):
    """切点 i 是 `.` 时，判断它像不像"小数点 / 缩写点"。"""
    if t[i] != DOT:
        return False
    prev = t[i - 1] if i > 0 else u''
    nxt = t[i + 1] if i + 1 < len(t) else u''
    return bool(prev) and (prev.isdigit() or prev.isalpha()) and bool(nxt) \
        and (nxt.islower() or nxt.isdigit())


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

    # 第142轮的分组（带 ① 的 38 人），用于对账 247 那个数
    idx = json.loads(_src(os.path.join(PET, 'assets', 'npc', '_training',
                                      '_index.json')))
    lead38 = set()
    for k, v in (idx.get('patches') or {}).items():
        blob = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        if u'两三句' in blob and u'随口说' in blob:
            lead38.add(k)

    samples = []
    for p in sorted(glob.glob(os.path.join(RAW, '*.jsonl'))):
        name = os.path.basename(p)[:-6]
        mc = cards.get(name, 220)
        for line in io.open(p, encoding='utf-8', newline=''):
            if not line.strip():
                continue
            for turn in (json.loads(line).get('turns') or []):
                t = (turn.get('final') or u'').strip()
                if t and len(t) > mc:
                    n_cjk = len(CJK.findall(t))
                    lang = 'zh' if n_cjk >= 0.3 * len(t) else 'en'
                    samples.append({'id': name, 'mc': mc, 't': t, 'lang': lang})

    say(u'超过 max_chars 的样本：%d 条（中文 %d / 英文 %d）' % (
        len(samples),
        len([s for s in samples if s['lang'] == 'zh']),
        len([s for s in samples if s['lang'] == 'en'])))
    n38 = len([s for s in samples if s['id'] in lead38])
    say(u'  其中带 ① 的 38 人占 %d 条（第142轮记的是 247 ⇒ %s）'
        % (n38, u'对得上' if n38 == 247 else u'**对不上，要归因**'))
    say(u'')

    variants = [
        ('V0 现状          ', V0),
        ('V1 +`…`          ', V0 + (ELL,)),
        ('V2 +`.`          ', V0 + (DOT,)),
        ('V3 +`…`+`.`      ', V0 + (ELL, DOT)),
    ]
    table = {}
    for label, seps in variants:
        hard = {'zh': 0, 'en': 0}
        risky = 0
        chars = {}
        for s in samples:
            c = _cut(s['t'], s['mc'], seps)
            if c < 0:
                hard[s['lang']] += 1
            else:
                key = s['t'][c].replace(u'\n', u'\\n')
                chars[key] = chars.get(key, 0) + 1
                if _risky_dot(s['t'], c):
                    risky += 1
        table[label.strip()] = {
            'hard_zh': hard['zh'], 'hard_en': hard['en'],
            'hard_total': hard['zh'] + hard['en'],
            'risky_dot': risky,
            'cut_chars': chars,
        }
        say(u'%-18s 硬截 中文 %-3d 英文 %-3d 合计 %-3d · 疑似非句末点 %d'
            % (label, hard['zh'], hard['en'], hard['zh'] + hard['en'], risky))
        say(u'                   切点：%s' % json.dumps(
            chars, ensure_ascii=False, sort_keys=True))
    say(u'')

    # 残差：V3 之后还硬截的是谁
    left = []
    for s in samples:
        if _cut(s['t'], s['mc'], V0 + (ELL, DOT)) < 0:
            left.append({'id': s['id'], 'lang': s['lang'], 'len': len(s['t']),
                         'head': s['t'][:50]})
    say(u'V3 之后仍硬截：%d 条（中文 %d）' % (
        len(left), len([x for x in left if x['lang'] == 'zh'])))
    for x in left[:6]:
        say(u'   [%s/%s] len=%d %s' % (x['id'], x['lang'], x['len'], x['head']))
    say(u'')

    out = {'over': len(samples),
           'over_zh': len([s for s in samples if s['lang'] == 'zh']),
           'over_en': len([s for s in samples if s['lang'] == 'en']),
           'lead38_over': n38,
           'variants': table,
           'still_hard_v3': left}
    p = os.path.join(EVID, 'lead143b.json')
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))
    say(u'写盘：%s' % os.path.relpath(p, ROOT))


if __name__ == '__main__':
    main()

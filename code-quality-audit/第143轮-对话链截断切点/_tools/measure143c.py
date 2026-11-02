# -*- coding: utf-8 -*-
"""第143轮 · 第三量：把 V0/V2 的切点**按语言拆开**，并看清"硬截"到底长什么样。

前一步（`measure143b.py`）的结论已经很清楚：
  · 336 条超 `max_chars` 的回复里，**中文 170 条一条都没硬截**，英文 166 条硬截 **61** 条；
  · 补 `…` 只解掉 2 条（61→59），补 `.` 解掉 59 条（61→2）；
  · 而且补 `…` 会让切点从 `。` 上挪走 8 条、从 `\\n` 挪走 5 条（切得更晚，但更可能在句子中间）。

**但这还不够**：如果补 `.` 会让**中文**回复也切在英文句点上，那就是拆东墙补西墙。
本脚本就是补这一刀：

Q1 V0 / V2 的切点表**按语言分列**（中文样本里 `.` 到底用了几次）
Q2 中文样本里切点是 `.` 的，逐条打出来看（是不是"结尾夹了个 OK." 这种）
Q3 那 61 条硬截的**结尾 12 字**（证明它是半句话，不是"正好切干净"）
Q4 补 `.` 之后仍硬截的 2 条是谁
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
V2 = V0 + (u'.',)
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


def main():
    cards = {}
    for p in sorted(glob.glob(os.path.join(CARDS, '*.json'))):
        try:
            mc = (json.loads(_src(p)).get('length_policy') or {}).get('max_chars')
        except Exception:
            continue
        if isinstance(mc, int) and mc > 0:
            cards[os.path.basename(p)[:-5]] = mc

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
                    n = len(CJK.findall(t))
                    samples.append({'id': name, 'mc': mc, 't': t,
                                    'lang': 'zh' if n >= 0.3 * len(t) else 'en'})

    # Q1 按语言分列
    say(u'=== Q1 切点表（按语言分列）===')
    out = {}
    for label, seps in (('V0', V0), ('V2', V2)):
        per_lang = {}
        for s in samples:
            c = _cut(s['t'], s['mc'], seps)
            key = u'<硬截>' if c < 0 else s['t'][c].replace(u'\n', u'\\n')
            d = per_lang.setdefault(s['lang'], {})
            d[key] = d.get(key, 0) + 1
        out[label] = per_lang
        for lang in ('zh', 'en'):
            d = per_lang.get(lang, {})
            say(u'  %s %s：%s' % (label, lang, json.dumps(
                d, ensure_ascii=False, sort_keys=True)))
    say(u'')

    # Q2 中文样本里切在 `.` 上的
    say(u'=== Q2 中文样本里切点是 `.` 的 ===')
    zh_dot = []
    for s in samples:
        if s['lang'] != 'zh':
            continue
        c = _cut(s['t'], s['mc'], V2)
        if c >= 0 and s['t'][c] == u'.':
            zh_dot.append((s['id'], s['mc'], c, s['t']))
    say(u'  共 %d 条' % len(zh_dot))
    for name, mc, c, t in zh_dot[:8]:
        say(u'   [%s] 切在 %d 字（上限 %d）尾部=%r 后文=%r'
            % (name, c + 1, mc, t[max(0, c - 16):c + 1], t[c + 1:c + 14]))
    say(u'')

    # Q3 硬截的尾巴
    say(u'=== Q3 61 条硬截的尾巴（证明它是半句话）===')
    tails = []
    for s in samples:
        if _cut(s['t'], s['mc'], V0) >= 0:
            continue
        cut_txt = s['t'][:s['mc']]
        tails.append({'id': s['id'], 'len': len(s['t']),
                      'tail': cut_txt[-14:], 'next': s['t'][s['mc']:s['mc'] + 10]})
    say(u'  共 %d 条；尾字符不是句末标点的：%d'
        % (len(tails), len([x for x in tails if x['tail'][-1] not in
                            u'\u3002\uff01\uff1f!?' + u'\n'])))
    for x in tails[:8]:
        say(u'   [%s] len=%d …%r | 被丢掉的开头=%r' % (x['id'], x['len'],
                                                   x['tail'], x['next']))
    say(u'')

    # Q4 V2 之后仍硬截
    say(u'=== Q4 补 `.` 之后仍硬截的 ===')
    left = []
    for s in samples:
        if _cut(s['t'], s['mc'], V2) < 0:
            left.append({'id': s['id'], 'lang': s['lang'], 'len': len(s['t']),
                         'tail': s['t'][:s['mc']][-14:]})
    say(u'  共 %d 条' % len(left))
    for x in left:
        say(u'   [%s/%s] len=%d 尾=%r' % (x['id'], x['lang'], x['len'], x['tail']))
    say(u'')

    data = {'cut_by_lang': out, 'zh_dot_cut': len(zh_dot),
            'zh_dot_samples': [{'id': n, 'cut': c + 1, 'mc': m,
                                'tail': t[max(0, c - 16):c + 1]}
                               for n, m, c, t in zh_dot[:20]],
            'hard_total': len(tails), 'hard_samples': tails[:20],
            'still_hard_v2': left}
    p = os.path.join(EVID, 'lead143c.json')
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1))
    say(u'写盘：%s' % os.path.relpath(p, ROOT))


if __name__ == '__main__':
    main()

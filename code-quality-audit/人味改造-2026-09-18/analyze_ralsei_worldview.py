# -*- coding: utf-8 -*-
"""从 Ralsei 原作语料里统计"他到底提到过谁 / 什么"—— 作为 persona「我知道的世界」一节的事实依据。

判据说明：只统计 **Ralsei 自己说出口的 853 条**（output 侧）= 直接证据"他确实知道 / 会谈到"；
input 侧另计 = "他身边的人"，用来判断关系是否需要写进设定。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, '_evidence', 'ralsei_lora_corpus.jsonl')
OUT = os.path.join(HERE, '_evidence', 'ralsei_worldview_2026-09-19.txt')

rows = [json.loads(ln) for ln in io.open(CORPUS, encoding='utf-8') if ln.strip()]
outs = [r['output'] for r in rows]
ins = [r['input'] for r in rows]

# 人物（含称呼变体）
PEOPLE = {
    'Kris': [r'\bKris\b'],
    'Susie': [r'\bSusie\b'],
    'Lancer': [r'\bLancer\b'],
    'Noelle': [r'\bNoelle\b'],
    'Berdly': [r'\bBerdly\b'],
    'Toriel': [r'\bToriel\b'],
    'Asgore': [r'\bAsgore\b'],
    'Alphys': [r'\bAlphys\b'],
    'Undyne': [r'\bUndyne\b'],
    'King (黑桃国王)': [r'\bKing\b(?!dom)'],
    'Queen': [r'\bQueen\b'],
    'Jevil': [r'\bJevil\b'],
    'Spamton': [r'\bSpamton\b'],
    'Rouxls (Kaard)': [r'\bRouxls\b', r'\bKaard\b'],
    'Mr. Tenna (电视先生)': [r'\bTenna\b'],
    'Mike': [r'\bMike\b'],
    'Gerson': [r'\bGerson\b'],
    'Knight (骑士)': [r'\bKnight\b'],
    'Rudin': [r'\bRudin\b'],
}

# 世界观概念
LORE = {
    'Dark World 黑暗世界': [r'\bDark World\b', r'\bDarkworld\b'],
    'Light World 光明世界': [r'\bLight World\b', r'\bLightworld\b'],
    'Darkner': [r'\bDarkners?\b'],
    'Lightner': [r'\bLightners?\b'],
    'Fountain 喷泉': [r'\bFountain\b'],
    'prophecy 预言': [r'\bprophec'],
    'Delta Rune': [r'\bDelta Rune\b', r'\bDelta Warriors?\b'],
    'SOUL': [r'\bSOUL\b'],
    'TP': [r'\bTP\b'],
    'SPARE 饶恕': [r'\bspar', r'\bsparable\b'],
    'ACT 行动': [r'\bACT\b'],
    'hero 英雄': [r'\bhero', r'\bHeroes\b'],
    'Castle Town 城堡镇': [r'\bCastle Town\b', r'\bCastletown\b'],
    'Hometown': [r'\bHometown\b'],
    "Angel 天使": [r'\bAngel\b'],
    'Roaring': [r'\bRoaring\b'],
    'world/real 世界真实性': [r'\breal\b', r'\bworld\b'],
    'darkness 黑暗': [r'\bdark(?:ness|er)?\b'],
    'light 光': [r'\blight\b'],
}


def count(pats, texts):
    hits = 0
    for t in texts:
        for p in pats:
            if re.search(p, t):
                hits += 1
                break
    return hits


lines = []
lines.append('Ralsei 原作语料 · 世界观事实依据')
lines.append('=' * 60)
lines.append('来源 : %s' % os.path.basename(CORPUS))
lines.append('规模 : %d 条 Ralsei 台词（output 侧）/ 章覆盖 = %s' % (
    len(rows), sorted(set(r['chapter'] for r in rows))))
lines.append('')
lines.append('-- 人物：他自己说到过（output 命中条数 / 853）--')
for name, pats in sorted(PEOPLE.items(), key=lambda kv: -count(kv[1], outs)):
    lines.append('  %-22s out=%3d   in=%3d' % (name, count(pats, outs), count(pats, ins)))

lines.append('')
lines.append('-- 世界观概念 --')
for name, pats in sorted(LORE.items(), key=lambda kv: -count(kv[1], outs)):
    lines.append('  %-22s out=%3d   in=%3d' % (name, count(pats, outs), count(pats, ins)))

# 场景名里的世界观地标（按章）
lines.append('')
lines.append('-- 场景名里的地标（按章，取前若干）--')
scenes = {}
for r in rows:
    scenes.setdefault(r['chapter'], set()).add(r['scene'])
for ch in sorted(scenes):
    names = sorted(scenes[ch])
    lines.append('  ch%d (%d 个场景): %s' % (ch, len(names), ' | '.join(names[:14])))

# 关键句抽样：含"现实/物品化/预言"的 Ralsei 台词
lines.append('')
lines.append('-- 关键设定句抽样（含 real / object / prophecy / cards / laptop）--')
KEYS = ['no longer', 'real', 'playing card', 'laptop', 'prophec', 'Dark Fountain',
        'the Fountain', 'Darkners', 'Lightners']
shown = 0
for r in rows:
    o = r['output']
    if any(k.lower() in o.lower() for k in KEYS):
        lines.append('  [ch%d|%s] %s' % (r['chapter'], r['scene'][:38], o.strip()))
        shown += 1
        if shown >= 30:
            break

io.open(OUT, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('WROTE %s (%d B)' % (OUT, os.path.getsize(OUT)))
for ln in lines[:60]:
    print(ln)

# -*- coding: utf-8 -*-
"""第141轮 · 出戏闸补词的**净增量**（不算已有闸的功劳）

候选正则全语料命中 N 条，但其中一部分**现有 20 条子串已经能抓**（比如含「提示词」）。
只有"现有闸漏掉"的那些才是这条正则的净增量 —— 不做这一步就会把功劳报大。

同时对每条新抓到的样本给出"归谁"：`_OOC_PATTERNS`（现有）/ `_META_LEAK_RES`（132 轮）/
`_OOC_RES`（本轮候选）。
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
RAW = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                   '_evidence', 'raw30')
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
from modules import event_speech as ES   # noqa: E402

CANDS = [
    (u'setting_play', re.compile(u'设定.{0,4}扮演')),
    (u'based_on_title', re.compile(u'(基于|根据).{0,24}(《|作品|游戏).{0,24}角色')),
    (u'not_real', re.compile(u'(不是|并非).{0,6}真实存在')),
    (u'real_entity', re.compile(u'真实存在的独立')),
]


def main():
    rows = []
    for p in sorted(glob.glob(os.path.join(RAW, '*.jsonl'))):
        name = os.path.basename(p)[:-6]
        for line in io.open(p, encoding='utf-8', newline=''):
            if not line.strip():
                continue
            rec = json.loads(line)
            for turn in rec.get('turns') or []:
                t = (turn.get('final') or u'').strip()
                if t:
                    rows.append((name, t))
    n = len(rows)
    base = [t for _k, t in rows if ES.looks_out_of_character(t)]
    print(u'语料 %d 条 · 现有 OOC 闸抓 %d 条 (%.1f%%)' % (n, len(base), 100.0 * len(base) / n))
    print(u'')

    ev = {'corpus': n, 'base_hits': len(base), 'cand': {}}
    union = set()
    for tag, rx in CANDS:
        hit = [(i, k, t) for i, (k, t) in enumerate(rows) if rx.search(t)]
        new = [(i, k, t) for i, k, t in hit if not ES.looks_out_of_character(t)]
        print(u'=== %-14s 全量 %d 条 · 现有闸漏 %d 条（净增量）===' % (tag, len(hit), len(new)))
        for i, k, t in new:
            union.add(i)
            print(u'   + %-18s %s' % (k, t.replace(u'\n', u' ')[:92]))
        ev['cand'][tag] = {'hits': len(hit), 'new': len(new),
                           'new_samples': [{'npc': k, 'text': t} for _i, k, t in new],
                           'npcs': sorted({k for _i, k, _t in new})}
        print(u'')

    print(u'=== 合计 ===')
    print(u'  四条正则并集净增 %d 条（现有 %d → %d，%.1f%% → %.1f%%）'
          % (len(union), len(base), len(base) + len(union),
             100.0 * len(base) / n, 100.0 * (len(base) + len(union)) / n))
    ral = [rows[i] for i in union if rows[i][0] == 'ralsei']
    print(u'  其中 ralsei 本人 %d 条（%d 轮里）' % (len(ral), 48))
    ev['union_new'] = len(union)
    ev['ralsei_new'] = len(ral)

    # 主宠那一条逐字留档
    if ral:
        ev['ralsei_sample'] = ral[0][1]
        print(u'  ralsei 样本：%s' % ral[0][1].replace(u'\n', u' '))
    print(u'')
    print(u'  现有闸（20 条子串）对这条样本：%r' % ES.looks_out_of_character(
        ev.get('ralsei_sample') or u''))
    evd = os.path.join(ROUND, '_evidence')
    out = os.path.join(evd, 'ooc_delta141.json')
    with io.open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print(u'已落盘：', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())

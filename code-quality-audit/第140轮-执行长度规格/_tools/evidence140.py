# -*- coding: utf-8 -*-
"""第140轮证据落盘：把「到底有多少条不遵守句数规格」量成一份可复核的 JSON。

三块内容：
  1. `splitters`  同一批 48 轮，三种切句口径下的 >3 句占比（证明 83.3% 是口径产物）
  2. `corpus`     全体角色（77 份 / 5592 条）的句数分布与累计占比
  3. `sweep`      天花板取 3~10 时会动到多少条、平均丢多少字

★ 只读仓库内的 `raw30/`（不外接盘、不联网）。
"""
import collections
import glob
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                   '_evidence', 'raw30')
AB139 = os.path.join(ROOT, 'code-quality-audit', '第139轮-patch与人设去重',
                     '_evidence', 'ab139.jsonl')

sys.path.insert(0, HERE)
import measure140 as M1          # noqa: E402  三个切句器
import measure140c_corpus as M3  # noqa: E402  全角色语料 + 句数计数


def _splitter_table(txts):
    out = []
    for label, ends, skip_q in ((u'A 含省略号', M1.END_A, False),
                                (u'B 不含省略号（人设口径）', M1.END_B, False),
                                (u'C 不含省略号且引号内不切', M1.END_B, True)):
        counts = [len(M1.sents(t, ends, skip_q)) for t in txts]
        over = sum(1 for c in counts if c > 3)
        out.append({'splitter': label, 'n': len(txts), 'gt3': over,
                    'gt3_pct': round(100.0 * over / len(txts), 1),
                    'mean_sentences': round(float(sum(counts)) / len(counts), 2)})
    return out


def _load_all():
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
    return rows


def _sweep(chars, cnts):
    out = []
    for cap in range(3, 11):
        touched = sum(1 for c in cnts if c > cap)
        out.append({'cap': cap, 'touched': touched,
                    'pct': round(100.0 * touched / len(cnts), 2)})
    return out


def main():
    rows = _load_all()
    chars = [len(t) for _, t in rows]
    cnts = [M3.count_sents(t) for _, t in rows]
    n = len(rows)
    dist = collections.Counter(cnts)

    ab_rows = [json.loads(l) for l in io.open(AB139, encoding='utf-8', newline='')
               if l.strip()]
    ab_arms = {}
    for r in ab_rows:
        if r.get('reply'):
            ab_arms.setdefault(r.get('arm'), []).append(r['reply'])

    ev = {
        'corpus': {
            'files': len({k for k, _ in rows}),
            'replies': n,
            'chars_median': sorted(chars)[n // 2],
            'chars_max': max(chars),
            'gt200': sum(1 for c in chars if c > 200),
            'gt220': sum(1 for c in chars if c > 220),
            'sentences_median': sorted(cnts)[n // 2],
            'sent_dist': {str(k): dist[k] for k in sorted(dist)},
            'ge_n': {str(k): sum(v for kk, v in dist.items() if kk >= k)
                     for k in sorted(dist)},
        },
        'sweep': _sweep(chars, cnts),
        'splitters_raw30': _splitter_table(M1.load_raw30()),
        'splitters_ab139': _splitter_table(
            ab_arms.get('no1', []) + ab_arms.get('with1', [])),
        'note': u'切句「不含省略号」的依据 = ralsei_persona.md 第 57 行'
                u'「用省略号让声音软下来：很少用，别拿它当句号」',
    }
    if not os.path.isdir(EV):
        os.makedirs(EV)
    with io.open(os.path.join(EV, 'length140.json'), 'w', encoding='utf-8',
                 newline='') as f:
        f.write(json.dumps(ev, ensure_ascii=False, indent=1))

    print(u'语料 %d 份 / %d 条；中位句数 %d；>200 字 %d、>220 字 %d'
          % (ev['corpus']['files'], n, ev['corpus']['sentences_median'],
             ev['corpus']['gt200'], ev['corpus']['gt220']))
    print(u'切句口径（raw30 48 轮）：',
          [(x['splitter'], x['gt3_pct']) for x in ev['splitters_raw30']])
    print(u'天花板扫描：', [(x['cap'], x['pct']) for x in ev['sweep']])
    print(u'已落盘：', os.path.join(EV, 'length140.json'))


if __name__ == '__main__':
    main()

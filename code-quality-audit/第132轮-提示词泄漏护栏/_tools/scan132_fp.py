# -*- coding: utf-8 -*-
"""第132轮 · 取证三：在 300 条**与本题无关**的历史回复上估误伤率。

为什么需要这一步：42 条里"3 命中 / 39 干净"样本太小，误伤率估不准。
第128轮 `_evidence/raw/*.jsonl` 有 5 个臂共 300 条真实回复（同一角色、同一模型、
不同批问题），是现成的**负样本大池**：如果新闸在这 300 条上狂响，说明它太宽。

★ 但"命中"不等于"误伤" —— 300 条里也可能真有人念规则。所以本脚本**不自动判对错**，
  只是把命中逐条打印出来给人看（并落盘），误伤率的口径由人工复核后写进报告。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
RAW = os.path.join(ROOT, 'code-quality-audit', '第128轮-结巴率收敛', '_evidence', 'raw')
EV = os.path.join(ROUND, '_evidence')
PET = os.path.join(ROOT, 'ralsei_pet')
if PET not in sys.path:
    sys.path.insert(0, PET)
from modules.event_speech import looks_like_meta_leak     # noqa: E402

FILES = ('base.jsonl', 'pnew_bnew.jsonl', 'pnew_bnew2.jsonl',
         'pnew_bold.jsonl', 'pnew_relax.jsonl')


def main():
    if not os.path.isdir(EV):
        os.makedirs(EV)
    total = 0
    hits = []
    per_file = {}
    for fn in FILES:
        p = os.path.join(RAW, fn)
        if not os.path.isfile(p):
            print('[SKIP] 没有 %s' % fn)
            continue
        n = 0
        h = 0
        for line in io.open(p, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rep = rec.get('reply') or ''
            n += 1
            if looks_like_meta_leak(rep):
                h += 1
                hits.append({'file': fn, 'user': rec.get('user'), 'reply': rep})
        total += n
        per_file[fn] = (n, h)
        print('[%s] %d 条，命中 %d' % (fn, n, h))

    print('')
    print('[合计] %d 条，命中 %d（%.2f%%）'
          % (total, len(hits), 100.0 * len(hits) / max(1, total)))
    print('')
    for h in hits:
        print('--- %s  用户问：%s' % (h['file'], (h['user'] or '')[:40]))
        print('    回复：%s' % h['reply'].replace('\n', ' / ')[:260])
        print('')

    with io.open(os.path.join(EV, 'leak_fp_128.json'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write(json.dumps({'total': total, 'per_file': per_file, 'hits': hits},
                           ensure_ascii=False, indent=1))
    print('[落盘] %s' % os.path.join(EV, 'leak_fp_128.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())

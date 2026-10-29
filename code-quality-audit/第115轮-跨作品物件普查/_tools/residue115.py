# -*- coding: utf-8 -*-
u"""量一遍：解码之后正文里还剩哪些"可能是控制符"的字符。

不先量就断言"解码后没有残留" = 拿一个没证明的判据当闸（本项目发作过多次：
判据过窄 ⇒ 假红；判据过宽 ⇒ 恒真）。所以先看剩什么、各剩多少、上下文长什么样。
"""
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(ROUND))
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'modules'))
import item_interact as II                                   # noqa: E402

ASSET = os.path.join(PET, 'assets', 'scenes', '_readable_text.json')


def main():
    doc = json.loads(io.open(ASSET, encoding='utf-8').read())
    table = II.load_readable_text(ASSET)
    if not table:
        print('[FAIL] 表为空')
        return 1
    cnt = collections.Counter()
    samples = collections.defaultdict(list)
    n_empty = 0
    n_total = 0
    for sid, per in table.items():
        for obj, txt in per.items():
            n_total += 1
            if not txt.strip():
                n_empty += 1
            for ch in (u'%', u'&', u'/', u'^', u'\\', u'[', u']', u'*'):
                k = txt.count(ch)
                if k:
                    cnt[ch] += k
                    if len(samples[ch]) < 3:
                        i = txt.find(ch)
                        samples[ch].append(txt[max(0, i - 10):i + 11].replace(u'\n', u'|'))
    print('解码后条目 = %d，其中空白 = %d' % (n_total, n_empty))
    for ch, n in cnt.most_common():
        print('  %-3r %5d 次   例：%s' % (ch, n, ' / '.join(samples[ch])))
    if not cnt:
        print('  （一个都没有）')
    # 原始条目数（对照，确认没有整批被丢）
    raw_n = sum(len(v) for v in (doc.get('by_scene') or {}).values())
    print('')
    print('原始条目 = %d，解码保留 = %d' % (raw_n, n_total))
    if n_total <= 0:
        print('[FAIL] 一条都没解出来')
        return 1
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())

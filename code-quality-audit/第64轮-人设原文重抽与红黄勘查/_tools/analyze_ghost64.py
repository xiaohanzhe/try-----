# -*- coding: utf-8 -*-
u"""第64轮 · 分析红与黄探针产出，定位「幽灵」素材。

只读 E:\\Download\\_extract64\\assets\\r64_*.json，产出 `_evidence/ghost64.json`。

★ 纪律：先过**锚点**再看结论 —— 已知真值（Undertale 原版一定有的
  obj_chara / obj_truechara / spr_chara* / mus_ghostbattle）必须命中，
  否则「提取正确」不成立，结论一律作废。
"""
from __future__ import print_function

import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding=u'utf-8', errors=u'replace')
except Exception:
    pass

SRCDIR = u'E:\\Download\\_extract64\\assets'
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EVID = os.path.join(ROUND, u'_evidence')


def load(name):
    p = os.path.join(SRCDIR, name)
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def main():
    nm = load(u'r64_names.json')
    ht = load(u'r64_hits.json')
    sh = load(u'r64_strhits.json')

    counts = nm[u'counts']
    names = nm[u'names']
    hits = ht[u'hits']
    strhits = sh[u'strhits']

    print(u'=== 计数 ===')
    for k in sorted(counts):
        print(u'  %-12s %d' % (k, counts[k]))
    print(u'  资源名合计 %d / 关键词命中 %d / 字符串命中 %d' % (len(names), len(hits), len(strhits)))
    print()

    # ---------------- 锚点自证 ----------------
    print(u'=== 锚点（已知真值，必须命中）===')
    anchors = {
        u'obj_chara 对象': [h for h in hits if h.startswith(u'object\t') and u'chara' in h.lower()],
        u'spr_chara* 精灵': [h for h in hits if h.startswith(u'sprite\t') and u'chara' in h.lower()],
        u'幽灵/ghost 精灵': [h for h in hits if h.startswith(u'sprite\t') and (u'ghost' in h.lower() or u'幽灵' in h)],
        u'mus_ghostbattle 音效': [h for h in hits if h.startswith(u'sound\t') and u'ghost' in h.lower()],
    }
    for k in sorted(anchors):
        v = anchors[k]
        print(u'  [%s] %s  -> %d 条' % (u'PASS' if v else u'★FAIL', k, len(v)))
        for h in v[:12]:
            print(u'        %s' % h)
    print()

    # ---------------- 资源名命中（去掉字符串噪音）----------------
    print(u'=== 资源名命中（按类型）===')
    byt = {}
    for h in hits:
        t = h.split(u'\t')[0]
        byt.setdefault(t, []).append(h)
    for t in sorted(byt):
        print(u'')
        print(u'--- %s (%d) ---' % (t, len(byt[t])))
        for h in byt[t][:200]:
            print(u'  %s' % h)
    print()

    # ---------------- 字符串命中：幽灵 / 决心 ----------------
    def show_strhits(kw, limit=40):
        print(u'=== 字符串命中 [%s] ===' % kw)
        n = 0
        for line in strhits:
            parts = line.split(u'\t', 2)
            if len(parts) < 3:
                continue
            idx, k, text = parts
            if k != kw:
                continue
            n += 1
            if n <= limit:
                print(u'  #%s  %s' % (idx, text.replace(u'\n', u'\\n')[:180]))
        print(u'  共 %d 条（%s）' % (n, u'以上为前 %d' % limit if n > limit else u'全部'))
        print(u'')
        return n

    stat = {}
    for kw in [u'幽灵', u'幽霊', u'亡灵', u'决心', u'決意', u'灵魂', u'魂', u'鬼',
               u'ghost', u'chara', u'determin', u'phantom', u'spirit', u'soul']:
        stat[kw] = show_strhits(kw, 24 if kw in (u'幽灵', u'决心') else 12)

    # ---------------- 落证 ----------------
    art = {
        u'source': u'E:\\Download\\_extract64\\assets\\game.droid',
        u'counts': counts,
        u'names_total': len(names),
        u'hits_total': len(hits),
        u'strhits_total': len(strhits),
        u'anchors': {k: v for k, v in anchors.items()},
        u'hits_by_type': {k: v for k, v in byt.items()},
        u'string_kw_counts': stat,
    }
    p = os.path.join(EVID, u'ghost64.json')
    with io.open(p, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(art, ensure_ascii=False, indent=1))
    print(u'证据 -> %s' % p)
    return 0


if __name__ == u'__main__':
    raise SystemExit(main())

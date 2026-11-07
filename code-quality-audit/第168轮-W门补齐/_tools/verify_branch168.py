# -*- coding: utf-8 -*-
u"""第168轮 · 验分支解析的可信度，并算"分支字母 → 目标房 marker"的命中率。

两件事：
  A. 解析出的 (src, dst) 必须与 `conn42b.json` 的查表项**逐条对上**（否则解析器不可信）
  B. 对每个分支，目标房是否含 `obj_marker<分字母>`（大小写不敏感）/ `obj_markerAny`
"""
import io
import json
import os
import re
import sys
import collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
EV = os.path.join(ROUND, '_evidence')

CH = [('ch1', 'conn42b.json', 'inst42.json'),
      ('ch2', 'ch2_conn42b.json', 'ch2_inst42.json')]
WCODE = ('gml_Object_obj_doorW_Alarm_2', 'gml_Object_obj_doorw_musfade_Alarm_2')
#: ★★★ 这里必须写**后缀**（`ds` 存的是 `MRK.match(o).group(1).lower()`）。
#:   v1 写的是完整对象名（`obj_markerany`），与后缀集求交**恒为空** ⇒
#:   「通用 Any 落点」29 条被误判成 MISS，ch2 命中率假跌到 73.2%
#:   （修正后 90.9%）。这是「判据恒假」的又一例：口径不一致的常量。
ANY = ('any', 'any40px')

_T1 = "\x3a True"
_t1 = "\x3a true"
_T0 = "\x3a False"
_t0 = "\x3a false"


def jload(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    return json.loads(s.replace(_T1, _t1).replace(_T0, _t0))


B = jload(os.path.join(EV, 'branch168.json'))['chapters']
MRK = re.compile(r'^obj_marker(.*)$')

for ch, cf, inf in CH:
    conn = jload(os.path.join(EV42, cf))
    inst = jload(os.path.join(EV42, inf))
    rn = conn['room_names']
    N = len(rn)
    robj = {r['index']: set(x.get('obj') for x in r['insts']) for r in inst['rooms']}
    mk = {i: set((MRK.match(o).group(1) or '').lower() for o in s if MRK.match(o))
          for i, s in robj.items()}
    tbl = collections.defaultdict(dict)
    for it in conn['items']:
        if it['op'] == 'goto' and isinstance(it.get('src'), int) and it['src'] >= 0 \
                and it['code'] in WCODE:
            tbl[it['code']][it['src']] = it['dst']

    rows = B.get(ch) or []
    print('=' * 92)
    print(u'%s  分支解析 %d 条' % (ch, len(rows)))
    # ---- A. 与 conn42b 对账 ----
    mine = collections.defaultdict(dict)
    for r in rows:
        mine[r['code']][r['src']] = r['dst']
    for code in WCODE:
        a, b = tbl.get(code) or {}, mine.get(code) or {}
        extra = sorted(set(b) - set(a))
        miss = sorted(set(a) - set(b))
        diff = sorted(k for k in (set(a) & set(b)) if a[k] != b[k])
        print(u'  %-46s conn42b=%d 解析=%d 多出=%r 缺=%r 目标不同=%r'
              % (code.split('obj_')[-1], len(a), len(b), extra[:6], miss[:6], diff[:6]))
    # ---- B. 落点 ----
    c = collections.Counter()
    bad = []
    for r in rows:
        t = r['dst']
        if not (0 <= t < N):
            c['OOB'] += 1
            continue
        L = (r['letter'] or '').lower()
        ds = mk.get(t, set())
        if L and L in ds:
            c['LETTER'] += 1
        elif ds & set(ANY):
            c['ANY'] += 1
        elif not ds:
            c['NOMARKER'] += 1
            bad.append((r['src'], t, r['letter'], r['entrance'], sorted(ds),
                        rn[r['src']] if r['src'] < N else '', rn[t] if t < N else ''))
        else:
            c['MISS'] += 1
            bad.append((r['src'], t, r['letter'], r['entrance'], sorted(ds),
                        rn[r['src']] if r['src'] < N else '', rn[t] if t < N else ''))
    tot = sum(c.values())
    print(u'  落点：%r  命中率 %.1f%%（零 marker 的 %d 条单列，不算"字母不符"）'
          % (dict(c), 100.0 * (tot - c['MISS'] - c['NOMARKER']) / tot if tot else 0,
             c['NOMARKER']))
    for b in bad:
        print(u'     MISS %3d → %-3d 字=%s ent=%-3s dstM=%-28r %s → %s'
              % (b[0], b[1], b[2], b[3], b[4], (b[5] or '')[:30], (b[6] or '')[:30]))
    print()

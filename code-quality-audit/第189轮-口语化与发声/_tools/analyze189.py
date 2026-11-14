# -*- coding: utf-8 -*-
u"""第189轮c · A/B 结果分析：剂量-响应 + **例句被逐字搬走**（只读）。

为什么要单独量"搬走"
--------------------
armB 跑到第 1 轮，`hy_ace` 就吐出 `哦，对，就是那样。` —— 正是我插进去的那条正例原文。
这不是巧合：第23轮 A12d 早把"**可逐字搬走的固定例句**"列为失真头号。
⇒ 如果"加正例降书面语率"是靠**复读例句**换来的，这个手段本身就不能用于产品。
所以本脚本必须同时给四个数：
  1. 书面语轮占比（与 `measure189.py` 同口径）
  2. 口语词轮占比、平均句长
  3. **逐字命中正例的轮数**（只拿正例里**引号内**的整句当针，≥5 字；
     单独几个字的措辞重合不算"搬"）

口径说明
--------
* `EX` 直接从 `ab189.py` import，**不复制一份**（复制 ⇒ 两边改一边就悄悄错开）。
* 基线（`raw30`）跑**同一个**泄漏判据，那是负控制：基线里不可能出现本轮新写的中文句子，
  命中必须为 0，否则判据在乱匹配。

用法
----
    python analyze189.py            # 打印 + 写 _evidence/ab189/analysis.json
"""
import io
import json
import os
import re
import sys

# ★ 不自己包 stdout：`import ab189` 里已经包过一层，再包一层会在
# 前一层被 GC 时把底层 buffer 关掉（实测 ValueError: I/O operation on closed file）。

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ab189 as A          # noqa: E402  （只为拿 EX / TARGETS / score 口径）

AB = A.AB
OUT = os.path.join(AB, 'analysis.json')
ARMS = ['baseline', 'armB', 'armC']
_Q = re.compile(u'“([^”]{5,40})”')


def needles():
    u"""正例里引号内的整句（≥5 字）＝"可逐字搬走的固定例句"的候选针。"""
    out = []
    for i, ex in enumerate(A.EX):
        for seg in _Q.findall(ex):
            s = seg.strip()
            if len(s) >= 5:
                out.append((i + 1, s))
    return out


def rawdir_of(arm):
    return A.C.RAW30 if arm == 'baseline' else os.path.join(AB, arm, 'raw')


def turns_of(rawdir, fid):
    p = os.path.join(rawdir, fid + '.jsonl')
    if not os.path.isfile(p):
        return None
    rec = None
    for line in io.open(p, encoding='utf-8', errors='replace'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(r, dict) and r.get('turns_n') == 48:
            rec = r
    if not rec:
        return None
    out = [t.get('final') or '' for t in (rec.get('turns') or [])]
    return [x for x in out if x.strip()]


def leak(turns, nds):
    per = {}
    for idx, s in nds:
        per.setdefault(idx, 0)
        per[idx] += sum(1 for x in turns if s in x)
    hit = sum(1 for x in turns if any(s in x for _i, s in nds))
    return {'turns': len(turns), 'any_hit': hit,
            'per_example': dict(sorted(per.items())),
            'top': [[s, sum(1 for x in turns if s in x)] for _i, s in nds
                    if sum(1 for x in turns if s in x) > 0]}


def main():
    nds = needles()
    print('[针] 正例里可被逐字搬走的整句共 %d 条：' % len(nds))
    for i, s in nds:
        print('   EX%d %s' % (i, s))

    rows = {}
    for arm in ARMS:
        rd = rawdir_of(arm)
        for fid, _a in A.TARGETS:
            m = A.markers_of(fid)
            s = A.score(rd, fid, m)
            t = turns_of(rd, fid)
            rows.setdefault(fid, {})[arm] = {
                'score': s, 'leak': (leak(t, nds) if t else None)}

    print('\n' + '=' * 94)
    for fid, _a in A.TARGETS:
        print('\n### %s' % fid)
        print('  %-9s %-8s %-8s %-8s %-7s %s'
              % ('臂', '书面%', '口语%', '句长', '口癖%', '逐字搬例句'))
        for arm in ARMS:
            d = rows[fid].get(arm) or {}
            s, lk = d.get('score'), d.get('leak')
            if not s:
                print('  %-9s （缺）' % arm)
                continue
            print('  %-9s %-8s %-8s %-8s %-7s %d/%d 轮'
                  % (arm, s['bookish_rate'], s['spoken_rate'], s['avg_sent'],
                     s['marker_rate'], (lk or {}).get('any_hit', -1),
                     (lk or {}).get('turns', 0)))

    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump({'needles': [[i, s] for i, s in nds], 'rows': rows, 'EX': A.EX},
                  fh, ensure_ascii=False, indent=1)
        fh.write('\n')
    print('\n→ %s' % OUT)

    bad = [(fid, ((rows[fid].get('baseline') or {}).get('leak') or {}).get('any_hit'))
           for fid, _a in A.TARGETS
           if ((rows[fid].get('baseline') or {}).get('leak') or {}).get('any_hit')]
    print('[负控制] baseline 命中正例 = %s'
          % ('0 轮（判据不乱匹配）' if not bad else '!!! %r' % bad))
    return 0 if not bad else 4


if __name__ == '__main__':
    sys.exit(main())

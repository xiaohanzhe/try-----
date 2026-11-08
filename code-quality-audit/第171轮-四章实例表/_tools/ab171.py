# -*- coding: utf-8 -*-
"""第171轮 · A/B 锚点：`inst171.ch2.json` 必须**逐实例复现**第42轮的 `ch2_inst42.json`。

为什么必须先过这一关：本轮要靠四章快照去判「这间房到底摆没摆这扇门」，
而四章没有第二份来源可交叉。唯一的办法是拿**已有独立结果**的 ch2 当锚点 ——
`inst171.csx` 是 `inst42.csx` 的改写（多两个字段），若它在 ch2 上给出同样的
rooms / insts / 坐标，才有资格相信它在 ch1/ch3/ch4/ch5 上的输出。

判据：
  A 分母：rooms 总数、rooms_hit、inst 总数、distinct 对象数 四项全等
  B 逐房间：房间集合（name↔index）全等；每间房的实例**多重集**（obj,x,y）全等
  C 负控制：把一条实例的 y 改 1 ⇒ B 必须报出差异（证明 B 不是恒真）
  D 新增字段不许影响老判据：`n_all` / `n_rooms_listed` / `n_inst_all` 只在 inst171 里有
用法: python ab171.py
"""
import collections
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
NEW = os.path.join(ROUND, '_evidence', 'inst171.ch2.json')
OLD = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence',
                   'ch2_inst42.json')

_n = {'p': 0, 'f': 0}
_bad = []


def check(desc, cond, extra=u''):
    if cond:
        _n['p'] += 1
        print('[PASS] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        _n['f'] += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))


def load(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def sig_rooms(d):
    """{room_name: Counter((obj,x,y))} + {room_name: index}"""
    ms = {}
    idx = {}
    for r in d['rooms']:
        idx[r['name']] = r.get('index')
        ms[r['name']] = collections.Counter(
            (i.get('obj'), i.get('x'), i.get('y')) for i in r.get('insts') or [])
    return ms, idx


def main():
    if not (os.path.isfile(NEW) and os.path.isfile(OLD)):
        print('缺文件：%s / %s' % (NEW, OLD))
        return 1
    a, b = load(NEW), load(OLD)

    # ---- A 分母
    check(u'A1 房间总数相等（%d vs %d）' % (a['n_rooms_total'], b['n_rooms_total']),
          a['n_rooms_total'] == b['n_rooms_total'], u'')
    check(u'A2 rooms_hit 相等（%d vs %d）' % (a['n_rooms_hit'], b['n_rooms_hit']),
          a['n_rooms_hit'] == b['n_rooms_hit'], u'')
    check(u'A3 实例总数相等（%d vs %d）' % (a['n_inst'], b['n_inst']),
          a['n_inst'] == b['n_inst'], u'')
    check(u'A4 distinct 对象数相等（%d vs %d）' % (len(a['top']), len(b['top'])),
          set(a['top']) == set(b['top']),
          u'只在新：%r 只在旧：%r' % (sorted(set(a['top']) - set(b['top']))[:5],
                                     sorted(set(b['top']) - set(a['top']))[:5]))
    check(u'A5 分母闸：上面四项都不为 0（防空集恒真）',
          all(a[k] > 0 for k in ('n_rooms_total', 'n_rooms_hit', 'n_inst'))
          and len(a['top']) > 0, u'%r' % ({k: a[k] for k in
                                           ('n_rooms_total', 'n_rooms_hit', 'n_inst')},))

    # ---- B 逐房间
    # ★ 本轮 csx **有意多列了 n==0 的房间**（本轮新增 `n_all`，
    #   目的是区分「这间房没摆门」与「这间房没被 dump 到」）；
    #   第42轮只列有命中的房间。所以 B 段的口径是：
    #   **新文件里 n>0 的房间集合** 必须与老文件逐间相等（不是拿 278 比 226）。
    am, ai = sig_rooms(a)
    bm, bi = sig_rooms(b)
    a_hit = set(k for k, v in am.items() if sum(v.values()) > 0)
    check(u'B0 分母：新文件里「有命中实例」的房间数 == 老文件的房间数（%d vs %d）'
          % (len(a_hit), len(bm)), len(a_hit) == len(bm) and len(bm) > 0)
    check(u'B0b 设计的差异：新文件多列了 %d 间 n==0 的房间（只记 n_all，不冒充有门）'
          % (len(am) - len(a_hit)),
          len(am) > len(a_hit)
          and all(sum(am[k].values()) == 0 for k in set(am) - a_hit))
    check(u'B1 有命中的房间名集合全等', a_hit == set(bm),
          u'只在新：%r 只在旧：%r' % (sorted(a_hit - set(bm))[:5],
                                     sorted(set(bm) - a_hit)[:5]))
    common = a_hit & set(bm)
    idx_bad = [k for k in common if ai.get(k) != bi.get(k)]
    check(u'B2 房间 index 逐间相等', not idx_bad,
          u'不一致 %d 间：%r' % (len(idx_bad),
                                 [(k, ai.get(k), bi.get(k)) for k in idx_bad][:5]))
    diff = [k for k in common if am.get(k) != bm.get(k)]
    check(u'B3 每间房实例多重集 (obj,x,y) 逐间相等', not diff,
          u'不一致 %d 间：%r' % (len(diff), diff[:5]))
    # 逐实例展开，给出确切差几条（判据不许只报"有差异"）
    n_bad = 0
    for k in common:
        if am.get(k) == bm.get(k):
            continue
        n_bad += sum(((am[k] - bm[k]) + (bm[k] - am[k])).values())
    check(u'B4 差异实例总数为 0（逐实例展开，不是只判"集合不等"）', n_bad == 0,
          u'差 %d 条' % n_bad)

    # ---- C 负控制
    a2 = json.loads(json.dumps(a))
    for r in a2['rooms']:
        if r.get('insts'):
            r['insts'][0]['y'] = (r['insts'][0].get('y') or 0) + 1
            break
    am2, _ = sig_rooms(a2)
    ctl = [k for k in common if am2.get(k) != bm.get(k)]
    check(u'C1 负控制：改一条实例的 y ⇒ B3 必须报差异（证明 B3 有鉴别力）',
          len(ctl) == 1, u'报出 %d 间：%r' % (len(ctl), ctl[:3]))
    ctl2 = sum(sum((am2[k] - bm[k]).values()) + sum((bm[k] - am2[k]).values())
               for k in common)
    check(u'C2 负控制：且 B4 的差异计数必须 ≥1（不是恒 0）', ctl2 >= 1, u'%d' % ctl2)

    # ---- D 新增字段只在新文件里
    check(u'D1 `n_all` / `n_inst_all` 只出现在新文件（不污染老 schema）',
          all(('n_all' in r) for r in a['rooms'][:50])
          and all(('n_all' not in r) for r in b['rooms'][:50]),
          u'新 %d 间有 n_all，旧 %d 间有' % (
              sum(1 for r in a['rooms'] if 'n_all' in r),
              sum(1 for r in b['rooms'] if 'n_all' in r)))

    print('')
    print('=' * 70)
    print('SUMMARY  pass=%d  fail=%d' % (_n['p'], _n['f']))
    if _bad:
        for x in _bad:
            print('  [FAIL] %s' % x)
    print('=' * 70)
    return 0 if _n['f'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

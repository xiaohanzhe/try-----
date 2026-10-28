# -*- coding: utf-8 -*-
u"""事件名 ↔ 物件块的挂载质量核对（第114轮）。

普查用「事件坐标落进块 bbox（容差 1 格）」来把原作名字挂到物件上。
这套办法**会挂错**，而且挂错了没有报错 —— 模型会照着错名字说话，比没名字更糟。
所以这里把它可能出错的三种形状都数出来：

  A. **一块挂多名**：同一个块被 2 个以上不同名字的事件覆盖。
     合法情形（原作就是分开做的相邻件，如 `bookshelf left` + `bookshelf right`），
     但如果一个 1×1 的格子上挂了 5 个名字，那就是容差把邻近的都吸进来了。
  B. **一名多块**：同一个名字（**同一房间内**）挂到了 2 个以上的块。
     跨房间重名是正常的（每间房都有 `door`），所以必须按 map 分组数。
  C. **名字落空**：有名字的事件，附近一个物件块都没有。
     这些是**互动点**（门、NPC 站位、触发区），不是可拆物件 —— 数出来是为了说明
     「924 个有名块」不等于「原作所有有名事件」。

只打印统计，不改任何数据。判据留在人这边：看数字是否合理，不预设 PASS/FAIL。
"""
import collections
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import oneshot_tmx as T
import census_objects114 as C

EV = os.path.normpath(os.path.join(HERE, '..', '_evidence'))


def main():
    rooms = json.load(io.open(os.path.join(EV, 'objects_l1l2.json'),
                              encoding='utf-8'))['rooms']
    tot_ev = tot_named = 0
    a_cases, b_cases, c_cases = [], [], []
    for r in rooms:
        evs = [e for e in C.load_events(r['map']) if e['name']]
        tot_ev += len(evs)
        tot_named += sum(1 for e in evs if e['named'])
        # A：一块挂多名
        for o in r['objects']:
            nm = o['named']
            if len(set(nm)) > 1:
                a_cases.append((r['map'], r['name'], o['layer'], o['x0'], o['y0'],
                                o['cw'], o['ch'], sorted(set(nm))))
        # B：同一房间内一名多块
        byname = collections.defaultdict(list)
        for o in r['objects']:
            for nm in set(o['named']):
                byname[nm].append((o['layer'], o['x0'], o['y0'], o['cw'], o['ch']))
        for nm, v in byname.items():
            if len(v) > 1:
                b_cases.append((r['map'], r['name'], nm, v))
        # C：名字没落到任何块
        for e in evs:
            if not e['named']:
                continue
            hit = any(o['x0'] - 1 <= e['x'] <= o['x1'] + 1
                      and o['y0'] - 1 <= e['y'] <= o['y1'] + 1
                      for o in r['objects'])
            if not hit:
                c_cases.append((r['map'], r['name'], e['name'], e['x'], e['y']))

    print(u'事件总数 %d（其中有名字 %d）' % (tot_ev, tot_named))
    print(u'')
    print(u'A 一块挂多名：%d 处' % len(a_cases))
    big = [c for c in a_cases if c[5] * c[6] <= 2]
    print(u'   其中 bbox ≤2 格（最可能是容差吸进来的）：%d 处' % len(big))
    for c in sorted(a_cases, key=lambda x: -(len(x[7])))[:6]:
        print(u'   map%-4d %-16s L%d (%d,%d) %dx%d ← %s'
              % (c[0], c[1], c[2], c[3], c[4], c[5], c[6], u' / '.join(c[7])))
    print(u'')
    print(u'B 同一房间内一名多块：%d 处' % len(b_cases))
    for c in sorted(b_cases, key=lambda x: -len(x[3]))[:6]:
        print(u'   map%-4d %-16s %-18s x%d %s'
              % (c[0], c[1], c[2], len(c[3]), c[3][:4]))
    print(u'')
    print(u'C 名字一个块都没碰上：%d 个（这些是门/站位/触发区，不是可拆物件）'
          % len(c_cases))
    cc = collections.Counter(c[2] for c in c_cases)
    print(u'   最常见：%s' % cc.most_common(10))
    print(u'')
    print(u'★ 口径提醒：924 个「有名块」只统计到“名字落在块上”的那批；'
          u'上面 C 组 %d 个有名事件没有对应块。' % len(c_cases))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())

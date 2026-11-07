# -*- coding: utf-8 -*-
u"""第170轮：**第169轮 `x_range` 与 GML 源码逐条对账**（旧的元数据错误）。

发现路径
--------
修 `dw_city_big_1 -> dw_city_treasure` 的坐标时看到：
    源码分支 `x < 10`  ⇒ 表里 `x_range = [10, None]`（即 `x > 10`）  ← 方向反了
而 `town_mid -> lw_icee_pizza` 的 `x > 290 && x < 370` ⇒ `[290, 370]` 是对的。
⇒ 怀疑：**只有单边条件（另一头是 null）时，lo/hi 记反**。

为什么必须查
------------
`x_range` 目前产品不消费，所以没造成走错房间；但它是我这轮**实例级消歧**
的判据来源之一，也是后人理解"这条规则对应哪扇门"的唯一线索。
留着反的区间＝埋雷（将来谁按区间匹配就会全部命错）。

判据
----
逐条 batch169 规则，用 `(章, 源房名, 对象, 目标房号)` 去 `gml170` 里找**唯一**
分支，比对 `(lo, hi)`：
  · 相等          ⇒ OK
  · `(hi, lo)`    ⇒ **方向反了**（要修）
  · 其它          ⇒ 记 `other`，逐条点名（可能是分支匹配错，不许瞎改）
匹配不到分支或匹配到多条 ⇒ 记 `unmatched`，同样点名、不改。
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
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
GML = os.path.join(ROUND, '_evidence', 'gml170.json')
OUT = os.path.join(ROUND, '_evidence', 'range170.json')


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace', newline='').read())


def main():
    g = jl(GML)
    routes = jl(os.path.join(SCENES, '_routes.json'))['routes']

    #: (ch, room_name, obj, dst_room_id) -> [branch]
    idx = collections.defaultdict(list)
    for ch, chd in g['chapters'].items():
        for obj, d in chd.items():
            for room, v in d['rooms'].items():
                for b in v['branches']:
                    if b['to_id'] is not None:
                        idx[(ch, room, obj, b['to_id'])].append(b)

    ok, flipped, other, unmatched = [], [], [], []
    for r in routes:
        o = r.get('_original') or {}
        if o.get('batch') != 169:
            continue
        k = (o.get('chapter'), o.get('src_room_name'), o.get('via'), o.get('dst_room_id'))
        bs = idx.get(k) or []
        if len(bs) != 1:
            unmatched.append({'key': k, 'n': len(bs), 'priority': r.get('priority')})
            continue
        b = bs[0]
        # ★ 按分支的轴取字段：y 轴分支写的是 `y_range`（`x_range` 保持 [None,None]，
        #   因为它本来就没有 x 条件）。只比 `x_range` 会把 y 轴那批全报成"不符"。
        field = '%s_range' % (b['axis'] or 'x')
        tbl = o.get(field)
        if not isinstance(tbl, list) or len(tbl) != 2:
            unmatched.append({'key': k, 'n': 'range_shape', 'priority': r.get('priority'),
                              'tbl': tbl})
            continue
        want = [b['lo'], b['hi']]
        if tbl == want:
            ok.append(k)
        elif tbl == [want[1], want[0]]:
            flipped.append({'key': k, 'priority': r.get('priority'), 'tbl': tbl,
                            'src': want, 'cond': b['cond'], 'axis': b['axis']})
        else:
            other.append({'key': k, 'priority': r.get('priority'), 'tbl': tbl,
                          'src': want, 'cond': b['cond'], 'axis': b['axis']})

    print(u'== 第169轮 x_range vs GML 源码 ==')
    print(u'   一致        %d' % len(ok))
    print(u'   ★方向反了   %d' % len(flipped))
    print(u'   其它不符    %d' % len(other))
    print(u'   匹配不到    %d' % len(unmatched))
    print()
    if flipped:
        print(u'   --- 方向反了（要修）---')
        for x in flipped:
            print(u'     prio=%-6s %-34s %-30s cond=%-18r 表=%r 源码=%r'
                  % (x['priority'], x['key'][1], x['key'][2], x['cond'], x['tbl'], x['src']))
    if other:
        print(u'   --- 其它不符（逐条点名，先不改）---')
        for x in other:
            print(u'     prio=%-6s %-34s %-30s cond=%-18r 表=%r 源码=%r'
                  % (x['priority'], x['key'][1], x['key'][2], x['cond'], x['tbl'], x['src']))
    if unmatched:
        print(u'   --- 匹配不到（先不改）---')
        for x in unmatched[:10]:
            print(u'     prio=%-6s key=%r n=%r' % (x['priority'], x['key'], x['n']))

    io.open(OUT, 'wb').write(json.dumps(
        {'ok': len(ok), 'flipped': flipped, 'other': other, 'unmatched': unmatched},
        ensure_ascii=False, indent=1).replace('\n', '\r\n').encode('utf-8'))
    print()
    print(u'落盘 %s' % OUT)


if __name__ == '__main__':
    main()

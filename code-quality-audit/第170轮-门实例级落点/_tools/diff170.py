# -*- coding: utf-8 -*-
u"""第170轮：**全量比对**「原作 GML 源码」vs「`_routes.json` 里的 W 门规则」。

为什么必须全量
--------------
抽样已抓到硬错（`room_dw_mansion_darkbulb_1`）：

    GML : x < 10   -> room_dw_mansion_lightner_hallway  (ent 21)
          表里同一条 -> queen_s_mansion_guest_hall      (ent 21)   ← 目标错了
    GML : x > 600  -> room_dw_mansion_darkbulb_2        (ent 20)   ← 有
          表里还有一条 -> dw_mansion_dining_a           (ent 20)   ← GML 里根本没有

⇒ 第169轮那套「字节码反推」不只是**漏**，还**错**和**多**。用户口径：
「以源码为准，改并留档」——所以先出全量差异，再逐条改。

比对键用 **数字房号**，不用名字
------------------------------
`sid` 与 `room_name` 不是简单前缀关系（`room_dw_mansion_east_3f` 对应
`ch2.queens_mansion.queen_s_mansion_3f`），拿名字拼 sid 会全错。
`_original.src_room_id` / `dst_room_id` 与 GML 里的 `room_names` 下标是同一套。
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
GML = os.path.join(ROUND, '_evidence', 'gml170.json')
ROUTES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_routes.json')
OUT = os.path.join(ROUND, '_evidence', 'diff170.json')

#: 属于 W 门的两条控制器（与第168/169轮同一份常量）
W_VIA = ('obj_doorW', 'obj_doorw_musfade')


def jl(p):
    s = io.open(p, encoding='utf-8', errors='replace', newline='').read()
    return json.loads(s)


def main():
    g = jl(GML)
    routes = jl(ROUTES)['routes']

    # ---- GML 侧：(ch, src_room_id, obj) -> [(dst_id, ent, kind, axis, lo, hi, cond)]
    gml = collections.defaultdict(list)
    for ch, chd in g['chapters'].items():
        for obj, d in chd.items():
            for room, v in d['rooms'].items():
                if v['room_id'] is None:
                    continue
                for b in v['branches']:
                    gml[(ch, v['room_id'], obj)].append(
                        {'dst': b['to_id'], 'dst_name': b['to'], 'ent': b['ent'],
                         'kind': b['kind'], 'axis': b['axis'],
                         'lo': b['lo'], 'lo_incl': b['lo_incl'],
                         'hi': b['hi'], 'hi_incl': b['hi_incl'],
                         'cond': b['cond']})

    # ---- 表侧：(ch, src_room_id, via) -> [规则]
    tbl = collections.defaultdict(list)
    for r in routes:
        o = r.get('_original') or {}
        if o.get('via') not in W_VIA:
            continue
        if o.get('src_room_id') is None:
            continue
        tbl[(o.get('chapter'), o.get('src_room_id'), o.get('via'))].append(r)

    keys = sorted(set(gml) | set(tbl), key=lambda k: (str(k[0]), k[1], str(k[2])))
    rows = []
    for k in keys:
        gs = gml.get(k, [])
        rs = tbl.get(k, [])
        # 目标多重集
        gc = collections.Counter(x['dst'] for x in gs)
        rc = collections.Counter((r.get('_original') or {}).get('dst_room_id') for r in rs)
        gml_only = list((gc - rc).elements())
        rule_only = list((rc - gc).elements())
        # entrance 对账（按 dst 配对；同 dst 多条时只报集合差）
        gent = collections.defaultdict(list)
        for x in gs:
            gent[x['dst']].append(x['ent'])
        rent = collections.defaultdict(list)
        for r in rs:
            o = r['_original']
            rent[o.get('dst_room_id')].append(o.get('entrance'))
        ent_bad = []
        ent_missing = []
        for dst in set(gent) & set(rent):
            if sorted(gent[dst]) == sorted(rent[dst]):
                continue
            # ★★★ 必须把「没记」和「记错」分开：
            #   第125轮那批老规则**根本没写 `entrance` 字段**（None）。
            #   把 None 当成「与 GML 不符」会把 94 处里绝大多数误报成错
            #   —— 它其实只是「没记」，本轮可以顺手补上。
            if all(v is None for v in rent[dst]):
                ent_missing.append({'dst': dst, 'gml': sorted(gent[dst])})
            else:
                ent_bad.append({'dst': dst, 'gml': sorted(gent[dst]),
                                'tbl': sorted(rent[dst])})
        if not gml_only and not rule_only and not ent_bad and not ent_missing:
            continue
            # 完全一致的（门实例级之外的）不列
        rows.append({
            'key': list(k), 'chapter': k[0], 'src_room_id': k[1], 'via': k[2],
            'gml': gs, 'rules': [{'to': r['to'],
                                  'dst_id': (r.get('_original') or {}).get('dst_room_id'),
                                  'ent': (r.get('_original') or {}).get('entrance'),
                                  'door_x': (r.get('_original') or {}).get('door_x'),
                                  'batch': (r.get('_original') or {}).get('batch'),
                                  'prio': r.get('priority')} for r in rs],
            'gml_only': gml_only, 'rule_only': rule_only, 'ent_bad': ent_bad,
            'ent_missing': ent_missing,
        })

    print(u'== 全量比对（W 门两条控制器；规则含 batch 168 与 169）==')
    print(u'  GML 侧 (章,源房,对象) 组合 %d 个，覆盖分支 %d 条'
          % (len(gml), sum(len(v) for v in gml.values())))
    print(u'  表侧 组合 %d 个，覆盖规则 %d 条' % (len(tbl), sum(len(v) for v in tbl.values())))
    print(u'  有差异的组合 %d 个' % len(rows))
    ng = sum(len(r['gml_only']) for r in rows)
    nr = sum(len(r['rule_only']) for r in rows)
    ne = sum(len(r['ent_bad']) for r in rows)
    nm = sum(len(r['ent_missing']) for r in rows)
    print(u'    GML 有、表里没有：%d 条' % ng)
    print(u'    表里有、GML 没有：%d 条  ← 多造的' % nr)
    print(u'    两边都有但 entrance 记错：%d 处' % ne)
    print(u'    两边都有但表里没记 entrance：%d 处（可补，不算错）' % nm)
    print()
    # GML_ONLY 的分支类型分布 —— 决定「能补多少」
    allg = {}
    for r in rows:
        for x in r['gml']:
            allg[(r['chapter'], r['src_room_id'], r['via'], x['dst'])] = x
    kc = collections.Counter()
    for r in rows:
        for dst in r['gml_only']:
            x = allg.get((r['chapter'], r['src_room_id'], r['via'], dst))
            kc[x['kind'] if x else '?'] += 1
    print(u'== GML_ONLY 那 76 条按分支类型分 ==  %r' % (dict(kc),))
    print(u'   （pos=按位置可精确还原 / uncond=一房一门 / other=flag·random 状态型）')
    print()
    for r in rows:
        print(u'--- %s room=%-4s %s' % (r['chapter'], r['src_room_id'], r['via']))
        for x in r['gml']:
            print(u'      GML  dst=%-4s ent=%-4s %-5s %-35s'
                  % (x['dst'], x['ent'], x['kind'], (x['cond'] or '')[:35]))
        for x in r['rules']:
            print(u'      TBL  dst=%-4s ent=%-4s door_x=%-6s batch=%s'
                  % (x['dst_id'], x['ent'], x['door_x'], x['batch']))
        if r['gml_only']:
            print(u'      ★ GML_ONLY %r' % (r['gml_only'],))
        if r['rule_only']:
            print(u'      ★ RULE_ONLY %r' % (r['rule_only'],))
        for x in r['ent_bad']:
            print(u'      ★ ENT_MISMATCH dst=%s gml=%r tbl=%r' % (x['dst'], x['gml'], x['tbl']))

    text = json.dumps({'rows': rows,
                       'stat': {'gml_keys': len(gml), 'tbl_keys': len(tbl),
                                'gml_branches': sum(len(v) for v in gml.values()),
                                'tbl_rules': sum(len(v) for v in tbl.values()),
                                'diff_keys': len(rows), 'gml_only': ng,
                                'rule_only': nr, 'ent_bad': ne}},
                      ensure_ascii=False, indent=1)
    io.open(OUT, 'wb').write(text.replace('\n', '\r\n').encode('utf-8'))
    print()
    print(u'落盘 %s (%d B)' % (OUT, os.path.getsize(OUT)))


if __name__ == '__main__':
    main()

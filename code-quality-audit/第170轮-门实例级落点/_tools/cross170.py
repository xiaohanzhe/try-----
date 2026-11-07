# -*- coding: utf-8 -*-
u"""第170轮：把「原作 GML 的分流类型」与「_routes.json 的多出口场景」对账。

回答一个问题：**37 个多出口场景里，有多少是「按门实例位置」分流（可精确还原），
有多少是运行时状态（flag / extflag / random，产品无状态、不该猜）？**
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
OUT = os.path.join(ROUND, '_evidence', 'cross170.json')


def jl(p):
    s = io.open(p, encoding='utf-8', errors='replace', newline='').read()
    return json.loads(s)


def main():
    g = jl(GML)
    routes = jl(ROUTES)['routes']
    mine = [r for r in routes if (r.get('_original') or {}).get('batch') == 169]

    # (章, room_name) -> 分流信息
    #
    # ★★★ 必须按**章**分开存：ch3/ch4/ch5 的 `obj_doorW_Alarm_2` 里**也包含**
    #   ch2 的 `room_town_mid` / `room_library` 等段落（各章 data.win 里这个对象
    #   是沿用的）。若不按章筛，同一个房间会被算进 5 份分支 ⇒ 看起来「GML 12 支
    #   对 3 条规则」，全是假账。
    info = {}
    for ch, chd in g['chapters'].items():
        for obj, d in chd.items():
            for room, v in d['rooms'].items():
                if v['kind'] == 'uncond':
                    continue
                k = (ch, room)
                if k in info:
                    info[k] = {'kind': 'both',
                               'branches': info[k]['branches'] + v['branches'],
                               'objs': info[k]['objs'] + [obj]}
                else:
                    info[k] = {'kind': v['kind'], 'branches': v['branches'], 'objs': [obj]}

    by = collections.defaultdict(list)
    for r in mine:
        by[r['when_scene']].append(r)
    multi = {k: v for k, v in by.items() if len(v) > 1}

    rows = []
    for sid, rs in sorted(multi.items()):
        o = rs[0]['_original']
        rn = o.get('src_room_name')
        ch = o.get('chapter') or sid.split('.')[0]
        gi = info.get((ch, rn))
        kind = gi['kind'] if gi else 'NOT-IN-GML'
        nb = len(gi['branches']) if gi else 0
        rows.append({
            'chapter': ch, 'scene': sid, 'room': rn, 'n_rules': len(rs),
            'gml_kind': kind, 'gml_branches': nb,
            'objs': gi['objs'] if gi else [],
            'has_door_x': sum(
                1 for r in rs if (r.get('_original') or {}).get('door_x') is not None),
            'tops': [r['to'] for r in rs],
            'axes': sorted(set(b['axis'] for b in (gi['branches'] if gi else []) if b.get('axis'))),
        })

    print(u'== 37 个多出口场景 × 原作分流类型 ==')
    cnt = collections.Counter(r['gml_kind'] for r in rows)
    for k, v in sorted(cnt.items(), key=lambda x: -x[1]):
        print(u'  %-12s %d 个场景' % (k, v))
    print()
    print(u'%-44s %-34s %-6s %-5s %-6s' % ('scene', 'room', 'kind', '规则', 'GML支'))
    for r in rows:
        print(u'%-44s %-34s %-10s %-5d %-5d %s'
              % (r['scene'], r['room'], r['gml_kind'], r['n_rules'],
                 r['gml_branches'], ','.join(r['axes'])))

    print()
    posn = [r for r in rows if r['gml_kind'] == 'pos']
    print(u'== 可精确还原的（pos：按 x/y 位置）%d 个场景 / %d 条规则 =='
          % (len(posn), sum(r['n_rules'] for r in posn)))
    bad = [r for r in posn if r['gml_branches'] != r['n_rules']]
    if bad:
        print(u'  ★ 分支数与规则数不等（要逐条看）：%d 个' % len(bad))
        for r in bad:
            print(u'     %-44s GML %d 支 vs 规则 %d 条' % (r['scene'], r['gml_branches'], r['n_rules']))
    else:
        print(u'  ✔ 分支数与规则数逐一相等')

    text = json.dumps({'rows': rows, 'kind_count': dict(cnt)},
                      ensure_ascii=False, indent=1)
    io.open(OUT, 'wb').write(text.replace('\n', '\r\n').encode('utf-8'))
    print()
    print(u'落盘 %s (%d B)' % (OUT, os.path.getsize(OUT)))


if __name__ == '__main__':
    main()

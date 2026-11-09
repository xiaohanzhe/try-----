# -*- coding: utf-8 -*-
u"""第181轮 · 补门型：先建账（只读，不改产品）。

用户口径（11-09）：
    「不必要连成一整张吧，按照原作那种一个一个房间的就可以了啊，记住咱的中心准则是符合原作」
    「如果你担心房间切换的衔接性，那原作那种也ok」

⇒ 本轮**不追求连通**，只做「原作有门 ⇒ 路由必须有边」的逐房间对账。
   **不做的事**：不为连通造边；不动 UT / outertale / uty（另一套机制）。

本脚本产出三张表（落 `_evidence/`）：
  ① `door_kinds.tsv`   门型 × 实例数 × 涉及房间数 × 当前路由条数 × 是否已接线
  ② `rooms_gap.tsv`    房间级缺口：原作有"会换房间的门"但路由条数 < 门数
  ③ `orphan_rooms.tsv` 零出边房间（再分「门型未接线」与「压根没抽到门」两类）

判定"会换房间的门"的排除项（装饰/标记，不是门）：
    marker / doorframe / ambience / indicator / *_markers
★ 这条排除必须写死在代码里并可核：它决定"账本分母"。

用法：python survey181.py
"""
import io
import json
import os
import sys
import collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
EV42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
EV = os.path.join(ROUND, '_evidence')

CHAPTERS = [
    ('ch1', 'inst42.json'),
    ('ch2', 'ch2_inst42.json'),
    ('ch3', 'ch3_inst42.json'),
    ('ch4', 'ch4_inst42.json'),
    ('ch5', 'ch5_inst42.json'),
]

#: 不是"会换房间的门"的物件（装饰 / 标记 / 环境）。
EXCLUDE_SUB = ('marker', 'doorframe', 'ambience', 'indicator')


def is_travel_door(obj):
    o = obj.lower()
    if 'door' not in o:
        return False
    return not any(t in o for t in EXCLUDE_SUB)


def load():
    idx = json.load(io.open(os.path.join(SCENES, '_index.json'), encoding='utf-8'))
    routes = json.load(io.open(os.path.join(SCENES, '_routes.json'), encoding='utf-8'))['routes']
    scenes = {}
    for w, wd in idx['chapters'].items():
        for a, ad in wd.get('areas', {}).items():
            for sid, sd in ad.get('scenes', {}).items():
                scenes[sid] = (w, sd.get('original_room_id'), sd.get('name') or sid)
    return scenes, routes


def main():
    os.makedirs(EV, exist_ok=True)
    scenes, routes = load()
    by_rid = {}
    for sid, (w, rid, nm) in scenes.items():
        by_rid.setdefault((w, rid), sid)

    n_routes = collections.Counter(r['when_scene'] for r in routes)
    #: 已接线门型 = 路由 `_original.via` 里出现过的物件名（第168/173/174 轮的写法）
    wired = set()
    for r in routes:
        v = (r.get('_original') or {}).get('via')
        if v:
            wired.add(v)

    kind_inst = collections.defaultdict(int)          # (kind) -> 实例数
    kind_rooms = collections.defaultdict(set)         # (kind) -> 房间 scene 集合
    kind_zeroroom = collections.defaultdict(set)      # (kind) -> 零出边房间
    kind_ch = collections.defaultdict(collections.Counter)

    gap_rows = []
    orphan = []
    for ch, f in CHAPTERS:
        p = os.path.join(EV42, f)
        if not os.path.exists(p):
            print(u'!! 缺证据：%s' % p)
            continue
        d = json.load(io.open(p, encoding='utf-8'))
        for rm in d['rooms']:
            sid = by_rid.get((ch, rm['index']))
            if not sid:
                continue
            doors = [i['obj'] for i in rm['insts'] if is_travel_door(i['obj'])]
            if not doors:
                continue
            nr = n_routes.get(sid, 0)
            for o in doors:
                kind_inst[o] += 1
                kind_ch[o][ch] += 1
                kind_rooms[o].add(sid)
                if nr == 0:
                    kind_zeroroom[o].add(sid)
            if len(doors) > nr:
                gap_rows.append((ch, rm['index'], rm['name'], len(doors), nr,
                                 sorted(set(doors)), sid))
            if nr == 0:
                orphan.append((ch, rm['index'], rm['name'], sorted(set(doors)), sid))

    # ---- ① 门型表
    lines = [u'门型\t实例数\t房间数\t零出边房间数\t已接线\t按章']
    for k in sorted(kind_inst, key=lambda x: -kind_inst[x]):
        lines.append(u'%s\t%d\t%d\t%d\t%s\t%s' % (
            k, kind_inst[k], len(kind_rooms[k]), len(kind_zeroroom[k]),
            u'yes' if k in wired else u'NO',
            u' '.join(u'%s:%d' % (c, n) for c, n in sorted(kind_ch[k].items()))))
    io.open(os.path.join(EV, 'door_kinds.tsv'), 'w', encoding='utf-8', newline='\r\n').write(
        u'\n'.join(lines) + u'\n')

    # ---- ② 房间级缺口
    gap_rows.sort(key=lambda t: -(t[3] - t[4]))
    g = [u'章节\t原房下标\t原作房名\tscene\t门数\t路由数\t缺\t门物件']
    for ch, ridx, name, nd, nr, kinds, sid in gap_rows:
        g.append(u'%s\t%d\t%s\t%s\t%d\t%d\t%d\t%s'
                 % (ch, ridx, name, sid, nd, nr, nd - nr, u','.join(kinds)))
    io.open(os.path.join(EV, 'rooms_gap.tsv'), 'w', encoding='utf-8', newline='\r\n').write(
        u'\n'.join(g) + u'\n')

    # ---- ③ 零出边房间
    o = [u'章节\t原房下标\t原作房名\tscene\t门物件\t门型是否已接线']
    for ch, ridx, name, kinds, sid in sorted(orphan):
        allwired = all(k in wired for k in kinds)
        o.append(u'%s\t%d\t%s\t%s\t%s\t%s'
                 % (ch, ridx, name, sid, u','.join(kinds), u'全已接线' if allwired else u'含未接线'))
    io.open(os.path.join(EV, 'orphan_rooms.tsv'), 'w', encoding='utf-8', newline='\r\n').write(
        u'\n'.join(o) + u'\n')

    # ---- 屏显摘要
    print(u'=' * 78)
    print(u'第181轮 门型账本（只读）')
    print(u'=' * 78)
    print(u'场景 %d ｜ 路由 %d 条 ｜ 已接线门型（出现过 via）%d 种'
          % (len(scenes), len(routes), len(wired)))
    print(u'')
    print(u'%-34s %6s %6s %8s %s' % (u'门型', u'实例', u'房间', u'零出边房', u'接线'))
    for k in sorted(kind_inst, key=lambda x: -kind_inst[x])[:24]:
        print(u'%-34s %6d %6d %8d %s'
              % (k, kind_inst[k], len(kind_rooms[k]), len(kind_zeroroom[k]),
                 u'已接' if k in wired else u'**未接**'))
    miss_kinds = [k for k in kind_inst if k not in wired]
    print(u'')
    print(u'★ 未接线门型 %d 种，合计 %d 个实例，涉及 %d 间房（其中零出边 %d 间）'
          % (len(miss_kinds), sum(kind_inst[k] for k in miss_kinds),
             len(set().union(*[kind_rooms[k] for k in miss_kinds]) if miss_kinds else set()),
             len(set().union(*[kind_zeroroom[k] for k in miss_kinds]) if miss_kinds else set())))
    print(u'★ 房间级缺口：%d 间「门数 > 路由数」，合计缺 %d 条'
          % (len(gap_rows), sum(t[3] - t[4] for t in gap_rows)))
    print(u'★ 零出边房间：%d 间' % len(orphan))
    print(u'')
    print(u'产出：_evidence/door_kinds.tsv  rooms_gap.tsv  orphan_rooms.tsv')
    return 0


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
u"""第169轮 · 从分支级解析生成 W 门路由（`_original.batch = 169`）。

## 与第168轮的关系
第168轮用的是 `_room_graph.json` 里的 98 条 W 边 —— 那是**下界**。
本轮改用 `branch_x169.json`（按分支解析），ch1/ch2 上能多认出 113 条。

## 入表规则（逐条可查）
1. 已在 `_room_graph` 的 W 边里 ⇒ 跳过（168 已处理）
2. 已被**任何门型**覆盖同一 `(when_scene, to)` ⇒ 跳过（不重复）
3. 落点自证：目标房含 `obj_marker<分支字母>`（大小写按**真实对象名**）或 `obj_markerAny*`
   ⇒ 落点 = 该对象；都不含 ⇒ `marker = None`（**按原作照收**，第169轮口径）
4. `(when_scene, to)` 重复 ⇒ 合并（保留先出现的）

## 输出
`_evidence/w_rules169.json`（98 条候选规则），供 `apply_routes169.py` 写入产品表。
"""
import io
import json
import os
import re
import sys
import collections

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
EV = os.path.join(ROUND, '_evidence')
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
OUT = os.path.join(EV, 'w_rules169.json')

sys.path.insert(0, os.path.join(REPO, 'ralsei_pet'))
from modules import scene_system as SS   # noqa: E402

PRIO_BASE = 7088
BATCH = 169
W_VIA = ('obj_doorW', 'obj_doorw_musfade')
MRK = re.compile(r'^obj_marker(.*)$')
ANY = ('any', 'any40px')
CH = [('ch1', 'conn42b.json', 'inst42.json'),
      ('ch2', 'ch2_conn42b.json', 'ch2_inst42.json')]


def jl(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


def main():
    BX = jl(os.path.join(EV, 'branch_x169.json'))['chapters']
    GRAPH = jl(os.path.join(EV42, '_room_graph.json'))['chapters']
    IDX = SS.load_index(SCENES)
    SCN = IDX.get('scenes') or {}
    RL = json.loads(io.open(os.path.join(SCENES, '_routes.json'),
                            encoding='utf-8', newline='').read())['routes']

    # 章 → 房号 → scene_id
    RID2SID = collections.defaultdict(dict)
    for sid, rec in SCN.items():
        if isinstance(rec, dict) and isinstance(rec.get('original_room_id'), int):
            RID2SID[sid.split('.')[0]].setdefault(rec['original_room_id'], sid)

    have_pair = set((r.get('when_scene'), r.get('to')) for r in RL)

    stat = collections.Counter()
    cand = []
    seen_pair = set()
    drops = {'unreg': [], 'dup': []}
    for ch, cf, inf in CH:
        conn = jl(os.path.join(EV42, cf))
        inst = jl(os.path.join(EV42, inf))
        rn = conn['room_names']
        N = len(rn)
        # 房号 → 真实 marker 对象名（小写后缀 → 原名）
        mkobj = {}
        for r in inst['rooms']:
            d = {}
            for o in r['insts']:
                mm = MRK.match(o.get('obj') or '')
                if mm:
                    d.setdefault((mm.group(1) or '').lower(), mm.group(0))
            mkobj[r['index']] = d
        # graph 里的 W 边（按门对象分开）
        gset = set()
        for e in (GRAPH.get(ch) or {}).get('edges') or []:
            if e.get('door') in W_VIA:
                gset.add((e['door'], e['src'], e['dst']))

        for r in BX.get(ch) or []:
            via = 'obj_doorW' if r['code'] == 'gml_Object_obj_doorW_Alarm_2' else 'obj_doorw_musfade'
            s, t = r['src'], r['dst']
            stat['raw'] += 1
            if (via, s, t) in gset:
                stat['in_graph_168'] += 1
                continue
            if not (0 <= s < N and 0 <= t < N):
                stat['oob'] += 1
                continue
            sid_s = RID2SID[ch].get(s)
            sid_t = RID2SID[ch].get(t)
            if not sid_s or not sid_t:
                stat['unreg'] += 1
                drops['unreg'].append((ch, rn[s], rn[t], bool(sid_s), bool(sid_t)))
                continue
            if (sid_s, sid_t) in have_pair:
                stat['already_other_door'] += 1
                continue
            if (sid_s, sid_t) in seen_pair:
                stat['dup'] += 1
                drops['dup'].append((ch, sid_s, sid_t, r['letter'], r['entrance']))
                continue

            # ---- 落点自证（真实对象名，不拼字符串）----
            d = mkobj.get(t) or {}
            L = (r['letter'] or '').lower()
            marker = None
            if L and L in d:
                marker = d[L]
                stat['land_letter'] += 1
            elif any(a in d for a in ANY):
                marker = d.get('any') or d.get('any40px')
                stat['land_any'] += 1
            elif not d:
                stat['land_nomarker'] += 1
            else:
                stat['land_mismatch'] += 1

            seen_pair.add((sid_s, sid_t))
            xs = r.get('x_hit') or []
            door_x = xs[0] if len(xs) == 1 else None
            cand.append({
                'ch': ch, 'via': via, 'code': r['code'],
                'src_id': s, 'dst_id': t, 'src_name': rn[s], 'dst_name': rn[t],
                'sid_s': sid_s, 'sid_t': sid_t,
                'letter': r['letter'], 'entrance': r['entrance'],
                'marker': marker,
                'xlo': r['xlo'], 'xhi': r['xhi'],
                'door_x': door_x,
                'door_x_all': r.get('door_x') or [],
                'x_hit': xs,
            })

    # ---- 排序：章 → 源房 → 目标，保证 priority 稳定可复现 ----
    cand.sort(key=lambda o: (o['ch'], o['src_id'], o['dst_id'], o['code']))

    rules = []
    for i, o in enumerate(cand):
        prio = PRIO_BASE + i
        xs = o['door_x_all']
        if o['door_x'] is not None:
            where = u'W 门（x=%d）' % o['door_x']
            if len(xs) > 1:
                where = (u'W 门（x=%d；本房该门共 %d 扇，x=%s，'
                         u'本分支按位置对应这一扇）'
                         % (o['door_x'], len(xs),
                            u'/'.join(str(v) for v in xs)))
        else:
            where = u'W 门'
            if len(xs) > 1:
                where = (u'W 门（本房 %d 扇，x=%s；**分支对应哪一扇未解出**）'
                         % (len(xs), u'/'.join(str(v) for v in xs)))
            elif not xs:
                where = (u'W 门（本房**无**该门实例；原作用运行时创建或直接调用，'
                         u'表里仍有这条连接）')

        if o['marker']:
            land = u'目标房含 `%s` 作为出生点' % o['marker']
        else:
            land = (u'**目标房没有该字母的落点**（原作如此：`entrance=%s` 指向房内'
                    u'不存在的 marker），按原作照收' % o['entrance'])

        reason = (u'原作连接：从 %s 的 %s离开，落到 %s（**分支级**：`%s` 的 `Alarm_2` 里 '
                  u'`if (room == %d)` 之后各自指定 `entrance=%s`；%s）。'
                  % (o['src_name'], where, o['dst_name'], o['via'], o['src_id'],
                     o['entrance'], land))

        rules.append({
            'to': o['sid_t'],
            'priority': prio,
            'reason': reason,
            'when_scene': o['sid_s'],
            'when_door': 'W',
            '_original': {
                'chapter': o['ch'],
                'door_letter': 'W',
                'kind': 'delta_door_table',
                'table': o['code'],
                'via': o['via'],
                'marker': o['marker'],
                'src_room_name': o['src_name'],
                'dst_room_name': o['dst_name'],
                'src_room_id': o['src_id'],
                'dst_room_id': o['dst_id'],
                'entrance': o['entrance'],
                'branch_letter': o['letter'],
                'door_x': o['door_x'],
                'door_x_all': o['door_x_all'],
                'x_range': [o['xlo'], o['xhi']],
                'batch': BATCH,
            },
        })

    print(u'== 统计 ==')
    for k in ('raw', 'in_graph_168', 'oob', 'unreg', 'already_other_door', 'dup',
              'land_letter', 'land_any', 'land_nomarker', 'land_mismatch'):
        print(u'  %-20s %d' % (k, stat[k]))
    print(u'  => 生成 %d 条，priority %d~%d'
          % (len(rules), PRIO_BASE, PRIO_BASE + len(rules) - 1))
    print(u'  marker 分布 %r' % (dict(collections.Counter(
        r['_original']['marker'] for r in rules)),))
    print(u'  门 x 已解出 %d 条 / 未解出 %d 条'
          % (sum(1 for r in rules if r['_original']['door_x'] is not None),
             sum(1 for r in rules if r['_original']['door_x'] is None)))
    print()
    print(u'== 落地不了的 / 合并掉的（逐条点名，不许"不落就算了"）==')
    for ch, a, b, hs, ht in drops['unreg']:
        print(u'  UNREG %s %s -> %s   源已登记=%r 目标已登记=%r' % (ch, a, b, hs, ht))
    for ch, s, t, L, ent in drops['dup']:
        print(u'  DUP   %s %s -> %s   字=%s ent=%s（同一条边重复出现，合并）'
              % (ch, s, t, L, ent))
    print()
    print(u'== 前 3 条 reason 样例 ==')
    for r in rules[:3]:
        print(u'  ' + r['reason'])

    os.makedirs(EV, exist_ok=True)
    text = json.dumps(rules, ensure_ascii=False, indent=1)
    io.open(OUT, 'wb').write(text.replace('\n', '\r\n').encode('utf-8'))
    print()
    print(u'落盘 %s (%d B)' % (OUT, os.path.getsize(OUT)))


if __name__ == '__main__':
    main()

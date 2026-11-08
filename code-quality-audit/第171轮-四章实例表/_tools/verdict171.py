# -*- coding: utf-8 -*-
"""第171轮 · 67 条「GML 有、表里没有」逐条裁决（v2：用**真实门坐标**匹配区间）。

v1 把上一轮的 `range_miss` 原样搬过来，但那批 `range_miss` 是**拿产品场景 JSON 的
objects 去算区间命中**得出的（`plan170.py` line 80~91），不是拿原作实例算的。
本轮补了逐房间实例快照，就能拿**真实门坐标**重算。

★ 关键结论（本轮新证据）：`obj_doorAny` 有**自己的** `Alarm_2`
  （`gml_Object_obj_doorAny_Alarm_2` = `global.entrance = 1; event_user(7);
  instance_create(0,0,obj_persistentfadein); room_goto(doorRoom);`），
  它走的是**每实例变量 `doorRoom`**，**不执行** `obj_doorW` 的房间表
  ⇒ 「房里只有 obj_doorAny、但 GML 里 obj_doorW 有这条 room 分支」**构不成一条 W 边**。

裁决分类
  R0 `room_absent`   源房不在快照（ch2 有 52 间未 dump）
  R1 `no_door`       源房里没有这扇 W 族门（摆的是 A/B/Any）⇒ 代码到不了，不补
  R2 `pair_exists`   (场景,目标) 已在表里 ⇒ 冗余
  R3 `src_unreg` / `dst_unreg`  端点未登记成场景 ⇒ 不补
  R4 `state`         分支含 state 条件（剧情旗标）⇒ 本轮不猜
  R5 `hit_zero` / `hit_multi`  区间在真实门实例上命中 0 扇 / >1 扇 ⇒ 不猜
  R6 `ADD`           **可补**：门摆着，且每条分支恰好命中一扇门、互不重复
                    （uncond 单分支不需要区间；pos 分支用区间命中）
用法: python verdict171.py
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
EV = os.path.join(ROUND, '_evidence')
R170 = os.path.join(REPO, 'code-quality-audit', '第170轮-门实例级落点', '_evidence')
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
CHS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']

#: 同族变体：同一个字母、不同对象。两者各有自己的 `Alarm_2`，但产品按字母认。
SIBLING = {
    'obj_doorw': 'obj_doorw_musfade',
    'obj_doorw_musfade': 'obj_doorw',
}


def load(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def in_range(v, b):
    u"""按 lo/hi 与 incl 判 v 是否落在分支区间内（与第170轮 `plan170._in` 同义）。"""
    lo, hi = b.get('lo'), b.get('hi')
    if lo is not None:
        if b.get('lo_incl'):
            if v < lo:
                return False
        elif v <= lo:
            return False
    if hi is not None:
        if b.get('hi_incl'):
            if v > hi:
                return False
        elif v >= hi:
            return False
    return True if (lo is not None or hi is not None) else False


def main():
    plan = load(os.path.join(R170, 'plan170.json'))
    gml = load(os.path.join(R170, 'gml170.json'))['chapters']
    inst = {ch: load(os.path.join(EV, 'inst171.%s.json' % ch)) for ch in CHS}
    routes = load(os.path.join(SCENES, '_routes.json'))
    RL = routes['routes'] if isinstance(routes, dict) else routes
    pairs = set((r.get('when_scene'), r.get('to')) for r in RL)

    rid2name = {}
    for ch in CHS:
        for via, blob in gml[ch].items():
            for nm, d in blob['rooms'].items():
                rid2name[(ch, via, d['room_id'])] = nm

    doors = {}     # (ch, room) -> {obj_low: [(x,y)]}
    markers = {}   # (ch, room) -> Counter(obj_low)
    for ch in CHS:
        for r in inst[ch]['rooms']:
            m = collections.defaultdict(list)
            mk = collections.Counter()
            for i in r.get('insts') or []:
                o = (i.get('obj') or '').lower()
                m[o].append((i.get('x'), i.get('y')))
                if o.startswith('obj_marker'):
                    mk[o] += 1
            doors[(ch, r['name'])] = m
            markers[(ch, r['name'])] = mk

    rows = []
    stat = collections.Counter()
    for r in plan['rows']:
        if r.get('ok'):
            continue
        ch, via, rid = r['ch'], r['via'], r['src_room']
        nm = rid2name.get((ch, via, rid))
        blob = (gml[ch].get(via) or {}).get('rooms', {}).get(nm) if nm else None
        brs = blob['branches'] if blob else []
        insts = (doors.get((ch, nm), {}) or {}).get(via.lower()) or []
        # ★ 同族变体：`obj_doorW` 与 `obj_doorw_musfade` 是**两个对象**（各有自己的
        #   `Alarm_2`），但产品一律按字母 'W' 认。第169轮把 via 一律记成 `obj_doorW`，
        #   于是"房里摆的是 musfade 变体"的房间会被误判成"没摆门"。
        #   ⇒ 请求的 via 缺席但同族变体在时，用变体的实例去配对，判定时标明 `via_fix`。
        via_fix = None
        if not insts:
            sib = SIBLING.get(via.lower())
            if sib:
                alt = (doors.get((ch, nm), {}) or {}).get(sib) or []
                if alt:
                    insts, via_fix = alt, sib
        # ★ 分支与房号对齐必须用 `to_id`（int）；
        #   `sid_t` 的末段是 **scene_id 尾**（`lw_icee_pizza`），不是 room 名
        #   （`room_lw_icee_pizza`）—— 拿它去比 `to` 会一条都对不上（v2 第一版就这么错）。
        br = next((x for x in brs if x.get('to_id') == r.get('dst')), None)
        dst_name = br.get('to') if br else None
        mk = markers.get((ch, dst_name)) if dst_name else None
        verdict, why, match = None, [], None
        if (ch, nm) not in doors:
            verdict = 'R0_room_absent'
        elif not insts:
            verdict = 'R1_no_door'
            why.append('房内门对象=%r' % sorted(
                o for o in (doors.get((ch, nm)) or {}) if o.startswith('obj_door')))
        elif (r.get('sid_s'), r.get('sid_t')) in pairs:
            verdict = 'R2_pair_exists'
        elif not r.get('sid_s'):
            verdict = 'R3_src_unreg'
        elif not r.get('sid_t'):
            verdict = 'R3_dst_unreg'
        elif br is None:
            verdict = 'R5_branch_not_found'
        elif (br.get('state_conds') or []) or br.get('kind') == 'state':
            verdict = 'R4_state'
        elif br.get('kind') == 'uncond':
            verdict = 'R6_ADD'
            why.append('uncond')
            match = {'axis': None, 'door': None, 'range': None}
        else:
            ax = 0 if br.get('axis') == 'x' else 1
            hits = [p for p in insts if p[ax] is not None and in_range(p[ax], br)]
            if len(hits) == 1:
                verdict = 'R6_ADD'
                match = {'axis': br.get('axis'), 'door': list(hits[0]),
                         'range': [br.get('lo'), br.get('hi')],
                         'lo_incl': br.get('lo_incl'), 'hi_incl': br.get('hi_incl')}
            elif not hits:
                verdict = 'R5_hit_zero'
            else:
                verdict = 'R5_hit_multi%d' % len(hits)
                why.append('命中%r' % (hits,))

        stat[verdict] += 1
        rows.append({
            'verdict': verdict, 'note': why,
            'ch': ch, 'via': via, 'src_room': rid, 'src_room_name': nm,
            'dst': r.get('dst'), 'dst_room_name': dst_name,
            'sid_s': r.get('sid_s'), 'sid_t': r.get('sid_t'),
            'kind': r.get('kind'), 'cond': r.get('cond'), 'ent': r.get('ent'),
            'n_inst': len(insts), 'door_all': insts, 'match': match,
            'via_fix': via_fix,
            'marker': sorted(mk) if mk is not None else None,
        })

    # 同一 (场景, 目标) 只能一条：ADD 里若有重复，只留分支唯一的那条
    seen = collections.Counter((x['sid_s'], x['sid_t']) for x in rows
                               if x['verdict'] == 'R6_ADD')
    dup = [k for k, v in seen.items() if v > 1]
    if dup:
        print('★ 同一 (场景,目标) 出现多分支，降级为 R5_hit_multi：')
        for x in rows:
            if x['verdict'] == 'R6_ADD' and (x['sid_s'], x['sid_t']) in dup:
                x['verdict'] = 'R5_same_pair_multi'
                x['note'] = ['同 (场景,目标) 有多条分支']
                stat['R6_ADD'] -= 1
                stat['R5_same_pair_multi'] += 1
        for d in dup:
            print('   ', d)

    with io.open(os.path.join(EV, 'verdict171.json'), 'w', encoding='utf-8') as fh:
        json.dump({'stat': dict(stat), 'rows': rows}, fh, ensure_ascii=False, indent=2)
        fh.write('\n')

    print('未入表 %d 条裁决：' % len(rows))
    for k in sorted(stat):
        print('  %-22s %d' % (k, stat[k]))
    adds = [x for x in rows if x['verdict'] == 'R6_ADD']
    print('')
    print('== R6_ADD（%d 条，可补）==' % len(adds))
    for x in adds:
        m = x['match'] or {}
        print('  %s %-42s W -> %-44s %-8s %s' % (
            x['ch'], x['sid_s'] or x['src_room'], x['sid_t'], x['kind'],
            ('range=%r door=%r' % (m.get('range'), m.get('door'))) if m.get('range')
            else 'uncond'))
    return 0


if __name__ == '__main__':
    sys.exit(main())

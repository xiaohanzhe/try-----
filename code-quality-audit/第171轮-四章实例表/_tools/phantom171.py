# -*- coding: utf-8 -*-
"""第171轮 · 揪出「惰性 W 规则」：规则说 via 是某扇 W 门，但那间房**根本没摆**这族门。

为什么要查（本轮新能力带来的第一个真问题）
  `obj_doorAny` 有**自己的** `Alarm_2`（`room_goto(doorRoom)`，走每实例变量），
  **不执行** `obj_doorW` 的房间表 ⇒ 一间房若只摆了 `obj_doorAny`，
  `obj_doorW` 里那条 `if (room == N)` 分支**永远执行不到**。
  第168/169轮没有实例表，把这类分支也收成了边 ⇒ 那些边在产品里**永久惰性**
  （房里没有任何实例能产出字母 'W'，`route_for_door` 永远选不中）。

★ 本脚本只**记录**，不改表（口径：能证实是假的才删；证实不了的一律留档）。
  · `via_absent`  请求的 via 对象不在源房，且**同族变体也不在** ⇒ 惰性
  · `via_variant` 请求的 via 不在，但同族变体在 ⇒ 只是 via 记错（行为不变）
产物 `_evidence/phantom171.json`
用法: python phantom171.py
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
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
CHS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']
SIBLING = {'obj_doorw': 'obj_doorw_musfade', 'obj_doorw_musfade': 'obj_doorw'}


def load(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def main():
    routes = load(os.path.join(SCENES, '_routes.json'))
    RL = routes['routes'] if isinstance(routes, dict) else routes
    # (章, room_id) -> room_name 与 (章, room_name) -> {obj_low: [(x,y)]}
    rid2name = collections.defaultdict(dict)
    doors = collections.defaultdict(lambda: collections.defaultdict(list))
    for ch in CHS:
        d = load(os.path.join(EV, 'inst171.%s.json' % ch))
        for r in d['rooms']:
            rid2name[ch][r['index']] = r['name']
            for i in r.get('insts') or []:
                doors[(ch, r['name'])][(i.get('obj') or '').lower()].append(
                    (i.get('x'), i.get('y')))

    rows = []
    for r in RL:
        if r.get('when_door') != 'W':
            continue
        o = r.get('_original') or {}
        ch = o.get('chapter')
        nm = o.get('src_room_name')
        if ch not in rid2name:
            continue
        if nm not in rid2name[ch].values():
            # ★ 已知：ch1 的 `src_room_name` 是**中文本地化名**（"纸牌城堡·一层"）
            #   ⇒ 用 src_room_id 兜底（第170轮 D1 同一条教训）
            nm = rid2name[ch].get(o.get('src_room_id'), nm)
        via = (o.get('via') or '').lower()
        here = doors.get((ch, nm)) or {}
        if via in here:
            continue
        sib = SIBLING.get(via)
        kind = 'via_variant' if (sib and sib in here) else 'via_absent'
        rows.append({'kind': kind, 'ch': ch, 'room': nm, 'via': o.get('via'),
                     'sibling': sib if kind == 'via_variant' else None,
                     'to': r.get('to'), 'priority': r.get('priority'),
                     'batch': o.get('batch'),
                     'doors_here': sorted(k for k in here if k.startswith('obj_door'))})

    stat = collections.Counter(x['kind'] for x in rows)
    with io.open(os.path.join(EV, 'phantom171.json'), 'w', encoding='utf-8') as fh:
        json.dump({'stat': dict(stat), 'rows': rows}, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    print('惰性/记错的 W 规则：%r' % (dict(stat),))
    for x in rows:
        print('  %-12s %s %-30s via=%-18s -> %-44s 房里门=%r' % (
            x['kind'], x['ch'], x['room'], x['via'], x['to'], x['doors_here']))
    return 0


if __name__ == '__main__':
    sys.exit(main())

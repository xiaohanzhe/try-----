# -*- coding: utf-8 -*-
u"""第170轮：**落地前的影响面评估**（只读，不改任何文件）。

问三件事
--------
  ① 那 9 条新增规则，落地后 `route_for_door` 会不会**真的改变**结果？
       · 不会改变 ⇒ 它只是把源码事实记进表里（元数据价值），零风险；
       · 会改变   ⇒ 那是在本场景里**新开一扇门**，必须单独点出来。
     判法：直接调产品函数，比对「加之前 / 加之后」两次返回值。**不自己模拟**
     `_pick` 的裁决规则 —— 那等于把被测物再写一遍（历轮教训：判据互证≠独立验证）。
  ② `door_x_add` 里 `axis == 'y'` 的条目：产品字段必须是 `door_y`，
     不能写进 `door_x`（写错＝用一个区分不了上下的数字去区分上下门）。
  ③ 88 条 `ent_fill` 的 `ent` 值分布（防止某一族值异常扎堆＝解析串味）。
"""
import collections
import io
import json
import os
import sys

_PET = os.path.abspath(os.path.join(
    os.path.abspath(os.path.dirname(__file__)), '..', '..', '..', 'ralsei_pet'))
#: ★ `item_interact.py` 用**扁平导入**（`from companion import Interactable`）
#:   ⇒ 只把 `ralsei_pet/` 加进去不够，`modules/` 也必进，否则 ImportError。
sys.path.insert(0, os.path.join(_PET, 'modules'))
sys.path.insert(0, _PET)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
FIX = os.path.join(ROUND, '_evidence', 'fix170.json')
OUT = os.path.join(ROUND, '_evidence', 'impact170.json')


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace', newline='').read())


def main():
    from modules.item_interact import route_for_door

    fix = jl(FIX)
    routes = jl(os.path.join(SCENES, '_routes.json'))

    # ---------- ① 9 条新增规则的行为影响 ----------
    #: 新规则只带 {when_scene, when_door='W', to}，priority 7190+（全表最大）。
    #: 逐条「加之前」问一次产品函数，「加之后」再问一次。
    rows = []
    for i, nr in enumerate(fix['new_rules']):
        sid_s = nr['sid_s']
        before = route_for_door(routes, sid_s, 'W', src='obj_doorW')
        prio = 7190 + i
        newr = {'to': nr['sid_t'], 'priority': prio, 'when_scene': sid_s,
                'when_door': 'W',
                'reason': u'原作连接（第170轮按 GML 源码补）：%s' % (nr.get('cond') or u'无位置条件'),
                '_original': {'chapter': nr['ch'], 'door_letter': 'W',
                              'kind': 'delta_door_table', 'via': nr['via'],
                              'src_room_id': nr['src_room'], 'dst_room_id': nr['dst'],
                              'entrance': nr['ent'], 'batch': 170}}
        trial = {'routes': list(routes['routes']) + [newr]}
        after = route_for_door(trial, sid_s, 'W', src='obj_doorW')
        rows.append({'i': i, 'priority': prio, 'scene': sid_s, 'to': nr['sid_t'],
                     'before': before, 'after': after,
                     'changed': before != after,
                     'same_as_before': before == nr['sid_t']})
    n_chg = sum(1 for r in rows if r['changed'])
    print(u'== ① 9 条新增规则的行为影响 ==')
    print(u'   会改变：%d 条   不改变：%d 条' % (n_chg, len(rows) - n_chg))
    for r in rows:
        print(u'  prio=%-6s %-46s before=%-42s after=%-42s %s'
              % (r['priority'], r['scene'], r['before'], r['after'],
                 u'[改]' if r['changed'] else u'[不变]'))

    # ---------- ② axis 分布 ----------
    by_axis = collections.Counter(x['axis'] for x in fix['door_x_add'])
    print()
    print(u'== ② door_x_add 的轴分布 ==')
    for k, v in sorted(by_axis.items()):
        print(u'   axis=%-3s %d' % (k, v))
    print(u'   ★ axis==y 的必须写 `door_y`，不许写 `door_x`：')
    for x in fix['door_x_add']:
        if x['axis'] == 'y':
            print(u'     prio=%-6s %-44s -> %-40s %s  (门在 x=%s, y=%s)'
                  % (x['priority'], x['scene'], x['dst'], x['cond'], x['x'], x['y']))

    # ---------- ③ ent 值分布 ----------
    print()
    print(u'== ③ ent_fill 的值分布 ==')
    c = collections.Counter(x['ent'] for x in fix['ent_fill'])
    print(u'   ' + u'  '.join(u'%s:%d' % (k, v) for k, v in sorted(c.items())))

    out = {'new_rule_impact': rows, 'changed': n_chg,
           'axis': dict(by_axis),
           'ent_dist': {str(k): v for k, v in sorted(c.items())}}
    io.open(OUT, 'wb').write(json.dumps(out, ensure_ascii=False, indent=1)
                             .replace('\n', '\r\n').encode('utf-8'))
    print()
    print(u'落盘 %s' % OUT)


if __name__ == '__main__':
    main()

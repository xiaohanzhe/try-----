# -*- coding: utf-8 -*-
"""第115轮 · 物件分级与待填清单

输入（全部已在仓库里，不碰游戏目录）：
  _evidence/deltarune_objects115.json        上一轮的对象汇总（名字/精灵/是否可见/实例数）
  _evidence/raw/chN/rooms_map.json            逐房间逐层的实例名（本章唯一真源）

输出：
  _evidence/deltarune_props115.json           每个对象的层深统计 / 房间样例 / 分级
  _evidence/deltarune_objects_todo.csv        实体物件待填清单（utf-8-sig，Excel 直接开）
  _evidence/deltarune_triggers115.txt         事件触发器名单（只作参考，不用填）

分级规则（写在代码里，判据可复现）：
  logic     ：没有 sprite 或 vis=false            —— 纯逻辑
  trigger   ：sprite 是「触发器占位图」           —— 剧情事件/判定区，不是布景
  prop      ：其余可见对象                        —— 真正要摆到桌面上的东西
"""
import io
import json
import os
import re
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')
CHAPTERS = [1, 2, 3, 4, 5]

# ---- 触发器占位图：名字长得像「事件/判定/调试标记」的精灵 -------------------
_TRIGGER_RES = [
    re.compile(r'^spr_(board_)?eventsmall(_\d+)?$', re.I),
    re.compile(r'^spr_(board_)?event(_\d+)?$', re.I),
    re.compile(r'^spr_board_triggerarea(_\d+)?$', re.I),
    re.compile(r'^spr_debug_', re.I),
    re.compile(r'^spr_crosshair', re.I),
    re.compile(r'^spr_invisible$', re.I),
]


def is_trigger_sprite(spr):
    if not spr:
        return False
    return any(r.match(spr) for r in _TRIGGER_RES)


def load_json(p):
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


def scan_rooms():
    """逐章扫 rooms_map，得到 obj -> {depth 计数, 房间名, 实例数}"""
    per_obj = collections.defaultdict(lambda: {
        'depth': collections.Counter(),
        'rooms': [],
        'seen': set(),
        'inst': 0,
        'chapters': set(),
    })
    ch_rooms = {}
    ch_inst = {}
    for ch in CHAPTERS:
        d = load_json(os.path.join(RAW, 'ch%d' % ch, 'rooms_map.json'))
        rooms = d['rooms']
        ch_rooms[ch] = len(rooms)
        total = 0
        for r in rooms:
            rname = r['name']
            for ly in r.get('layers') or []:
                if (ly.get('type') or '') != 'Instances':
                    continue
                depth = ly.get('depth')
                for oname in ly.get('instances') or []:
                    e = per_obj[oname]
                    e['depth'][depth] += 1
                    e['inst'] += 1
                    e['chapters'].add(ch)
                    # 一间房只记一次（用 set 判重，obj_mainchara 这种 1116 间的对象
                    # 用 list 的 in 判定会把复杂度顶到上亿次）
                    if rname not in e['seen']:
                        e['seen'].add(rname)
                        e['rooms'].append(rname)
                    total += 1
        ch_inst[ch] = total
    return per_obj, ch_rooms, ch_inst


def main():
    lib = load_json(os.path.join(EV, 'deltarune_objects115.json'))
    per_obj, ch_rooms, ch_inst = scan_rooms()

    # 对账：rooms_map 汇总出来的实例数必须等于上一轮的 47,895
    total_inst = sum(ch_inst.values())
    assert total_inst == 47895, '实例总数对不上：%d' % total_inst
    assert ch_rooms == {1: 147, 2: 278, 3: 246, 4: 328, 5: 252}, ch_rooms

    rows = []
    for o in lib['objects']:
        name = o['name']
        e = per_obj.get(name)
        assert e is not None, '对象 %s 在 rooms_map 里一次都没出现' % name
        assert e['inst'] == o['inst'], '%s 实例数不一致 %d vs %d' % (name, e['inst'], o['inst'])
        depths = sorted(e['depth'].items(), key=lambda kv: (-kv[1], kv[0]))
        dvals = [d for d, _ in depths]
        if not o['sprite'] or o['vis'] != 'True':
            cls = 'logic'
        elif is_trigger_sprite(o['sprite']):
            cls = 'trigger'
        else:
            cls = 'prop'
        rows.append({
            'name': name,
            'sprite': o['sprite'],
            'class': cls,
            'vis': o['vis'],
            'rooms': o['rooms'],
            'inst': o['inst'],
            'chapters': sorted(e['chapters']),
            'depth_min': min(dvals) if dvals else None,
            'depth_max': max(dvals) if dvals else None,
            'depth_mode': dvals[0] if dvals else None,
            'n_depths': len(depths),
            'room_samples': e['rooms'][:3],
            'vague': o['vague'],
            'in_objmap': o['in_objmap'],
        })

    cnt = collections.Counter(r['class'] for r in rows)
    inst_by_cls = collections.Counter()
    for r in rows:
        inst_by_cls[r['class']] += r['inst']

    out = {
        'note': '第115轮 · 物件分级；class=logic/trigger/prop，判据见 _tools/props115.py',
        'per_chapter': {'rooms': ch_rooms, 'inst': ch_inst},
        'totals': {
            'objects': len(rows),
            'inst': total_inst,
            'by_class': {k: {'objects': cnt[k], 'inst': inst_by_cls[k]} for k in ('prop', 'trigger', 'logic')},
            'vague_prop': sum(1 for r in rows if r['class'] == 'prop' and r['vague']),
        },
        'objects': rows,
    }
    with io.open(os.path.join(EV, 'deltarune_props115.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # ---- 待填清单：只收 prop（实体物件），按实例数降序 ----
    props = [r for r in rows if r['class'] == 'prop']
    props.sort(key=lambda r: (-r['inst'], r['name']))
    csv_p = os.path.join(EV, 'deltarune_objects_todo.csv')
    with io.open(csv_p, 'w', encoding='utf-8-sig', newline='') as f:
        f.write(u'编号,对象名,精灵,章节,房间数,实例数,最常见层深,示例房间,名字含糊,功能简介（请填写）\n')
        for i, r in enumerate(props, 1):
            f.write(u'%03d,%s,%s,%s,%d,%d,%s,%s,%s,\n' % (
                i, r['name'], r['sprite'], '/'.join('ch%d' % c for c in r['chapters']),
                r['rooms'], r['inst'],
                r['depth_mode'],
                ' | '.join(r['room_samples']),
                u'是' if r['vague'] else u'',
            ))

    trig = [r for r in rows if r['class'] == 'trigger']
    trig.sort(key=lambda r: (-r['inst'], r['name']))
    with io.open(os.path.join(EV, 'deltarune_triggers115.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(u'第115轮 · 事件触发器（占位精灵，不是布景，不用填功能简介）\n')
        f.write(u'共 %d 个对象 / %d 次实例\n\n' % (len(trig), inst_by_cls['trigger']))
        for r in trig:
            f.write(u'%-42s %-22s inst=%-4d rooms=%-3d ch=%s  %s\n' % (
                r['name'], r['sprite'], r['inst'], r['rooms'],
                ''.join(str(c) for c in r['chapters']),
                ' | '.join(r['room_samples'])))

    print(u'对象 %d（实例 %d）' % (len(rows), total_inst))
    for k, lab in (('prop', u'实体物件'), ('trigger', u'事件触发器'), ('logic', u'纯逻辑')):
        print(u'  %-8s %4d 个 / %6d 次' % (lab, cnt[k], inst_by_cls[k]))
    print(u'  其中名字不表意的实体物件 %d 个' % out['totals']['vague_prop'])

    # 覆盖面：前 N% 覆盖多少实例
    cum = 0
    marks = {}
    for i, r in enumerate(props, 1):
        cum += r['inst']
        for pct in (10, 25, 50):
            key = len(props) * pct // 100
            if i == key:
                marks[pct] = (i, cum, 100.0 * cum / inst_by_cls['prop'])
    for pct in (10, 25, 50):
        if pct in marks:
            n, c, share = marks[pct]
            print(u'  前 %d%%（%d 个）覆盖 %d 次 = %.1f%% 的实体物件实例' % (pct, n, c, share))

    print(u'落盘：deltarune_props115.json / deltarune_objects_todo.csv / deltarune_triggers115.txt')


if __name__ == '__main__':
    main()

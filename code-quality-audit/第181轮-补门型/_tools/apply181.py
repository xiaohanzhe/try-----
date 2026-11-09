# -*- coding: utf-8 -*-
u"""第181轮 · 补门型：把「按位移 / 按实例变量」推出来的净增边落进 `_routes.json`。

★ 只增不改：既有 2,768 条**一个字段都不动**（用户 11-09 裁定「只落 63 条净增」）。

## 取证依据（两条独立路径互证）

| 来源 | 内容 |
|---|---|
| `probe181.ch{1..5}.txt` | UTMT 导出的**原始指令**（Push/Call），用来判 `room_goto` 常量与位移次数 |
| `probe181b.ch{1..5}.json` | UTMT **反编译 GML**，用来判目标是否写在实例变量里 |

逐门机制（五章一致，`gml_Object_<obj>_Alarm_2`）：

    obj_doorA / _musfade : global.entrance=..; room_goto_next();                          → +1
    obj_doorB / _musfade : global.entrance=..; room_goto_previous();                      → −1
    obj_doorC / _musfade : room_goto(room_next(room_next(room)));                         → +2
    obj_doorD / _musfade : room_goto(room_previous(room_previous(room)));                 → −2
    obj_doorE            : room_goto(room_next(room_next(room_next(room))));              → +3
    obj_doorF            : room_goto(room_previous(room_previous(room_previous(room))));  → −3
    obj_climb_door       : 实例 PreCreate 写 `doorRoom`；Alarm_2 `room_goto(doorRoom)`

★★★ `entrance` 数值**不等于**门名字母（ch1 的 C=4、D=5、E=6、F=7；ch2 起 C=3、D=4），
   所以 `when_door` 取**名字字母**（与既有 1,200+ 条 `when_door: "A"/"B"/...` 同口径），
   **判据里禁止**把 `entrance` 数值当常量断言。

★ 唯一的单点覆盖：ch3 `obj_doorC` 在 `room == 110` 时 `room_goto(28)`（`chapter==3` 且 `exit`）。
  证据 `probe181b.ch3.json` → `gml_Object_obj_doorC_Alarm_2`。

## 幂等

同一台机器上可能把 `--go` 跑两次（第180轮的教训）。本脚本按
「`_original.batch == 181` 且 `(when_scene, to)` 已存在」判重 ⇒ 第二趟是空操作。

用法：
    python apply181.py          # dry-run，只打印
    python apply181.py --go     # 真写（先备份到 D:\\_tmp181\\）
"""
import argparse
import io
import json
import os
import shutil
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
ROUTES = os.path.join(SCENES, '_routes.json')
EV42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
EV = os.path.join(ROUND, '_evidence')
WORK = os.environ.get('P181_WORK', r'D:\_tmp181')

BATCH = 181
PRIORITY_BASE = 8200

CHAPTERS = [
    ('ch1', 'inst42.json'),
    ('ch2', 'ch2_inst42.json'),
    ('ch3', 'ch3_inst42.json'),
    ('ch4', 'ch4_inst42.json'),
    ('ch5', 'ch5_inst42.json'),
]

#: 门型 → (位移, 机制描述)
SHIFT = {
    'obj_doorA':            (+1, u'room_goto_next()'),
    'obj_doorA_musfade':    (+1, u'room_goto_next()'),
    'obj_doorB':            (-1, u'room_goto_previous()'),
    'obj_doorB_musfade':    (-1, u'room_goto_previous()'),
    'obj_doorC':            (+2, u'room_goto(room_next(room_next(room)))'),
    'obj_doorC_musfade':    (+2, u'room_goto(room_next(room_next(room)))'),
    'obj_doorD':            (-2, u'room_goto(room_previous(room_previous(room)))'),
    'obj_doorD_musfade':    (-2, u'room_goto(room_previous(room_previous(room)))'),
    'obj_doorE':            (+3, u'room_goto(room_next(room_next(room_next(room))))'),
    'obj_doorF':            (-3, u'room_goto(room_previous(room_previous(room_previous(room))))'),
}

#: 单点覆盖：(章, 源房下标, 门型) -> 目标房下标
OVERRIDE = {('ch3', 110, 'obj_doorC'): 28}


def door_letter(kind):
    u"""`obj_doorA_musfade` → `A`；`obj_climb_door` 无字母 → None。"""
    if not kind.startswith('obj_door') or kind == 'obj_doorw_musfade':
        if kind == 'obj_doorw_musfade':
            return u'W'
        return None
    rest = kind[len('obj_door'):]
    if not rest:
        return None
    c = rest[0]
    return c.upper() if c.isalpha() else None


def load_scenes():
    idx = json.load(io.open(os.path.join(SCENES, '_index.json'), encoding='utf-8'))
    by_rid, sid2name = {}, {}
    for w, wd in idx['chapters'].items():
        for a, ad in wd.get('areas', {}).items():
            for sid, sd in ad.get('scenes', {}).items():
                sid2name[sid] = sd.get('name') or sid
                rid = sd.get('original_room_id')
                if rid is not None:
                    by_rid[(w, rid)] = sid
    return by_rid, sid2name


def build():
    u"""返回 (edges, unresolved)。

    edges: [ dict(route 字段所需的一切) ]
    """
    by_rid, sid2name = load_scenes()
    order = json.load(io.open(os.path.join(EV42, '_room_order.json'), encoding='utf-8'))['chapters']
    name2sid = {}
    for ch, cd in order.items():
        for r in cd['rooms']:
            s = by_rid.get((ch, r['index']))
            if s:
                name2sid[(ch, r['name'])] = s

    edges, unresolved = [], []
    for ch, f in CHAPTERS:
        p = os.path.join(EV42, f)
        if not os.path.exists(p):
            raise SystemExit(u'!! 缺证据 %s' % p)
        d = json.load(io.open(p, encoding='utf-8'))
        rid2name = {r['index']: r['name'] for r in order[ch]['rooms']}
        maxidx = max(rid2name) if rid2name else -1
        for rm in d['rooms']:
            src = by_rid.get((ch, rm['index']))
            if not src:
                continue
            for inst in rm['insts']:
                kind = inst['obj']
                if kind not in SHIFT:
                    continue
                shift, mech = SHIFT[kind]
                tgt_idx = OVERRIDE.get((ch, rm['index'], kind), rm['index'] + shift)
                ovr = (ch, rm['index'], kind) in OVERRIDE
                if tgt_idx < 0 or tgt_idx > maxidx:
                    unresolved.append((ch, rm['index'], kind, 'out_of_range', tgt_idx, None))
                    continue
                dst = by_rid.get((ch, tgt_idx))
                if not dst:
                    unresolved.append((ch, rm['index'], kind, 'no_scene',
                                       tgt_idx, rid2name.get(tgt_idx)))
                    continue
                edges.append({
                    'ch': ch, 'src': src, 'dst': dst,
                    'src_idx': rm['index'], 'dst_idx': tgt_idx,
                    'src_name': rm['name'], 'dst_name': rid2name.get(tgt_idx),
                    'kind': kind, 'mech': mech, 'shift': shift, 'ovr': ovr,
                    'src_label': u'', 'how': u'room_goto',
                })

    # ---- obj_climb_door：目标在实例 PreCreate 的 doorRoom ----
    for n in (1, 2, 3, 4, 5):
        ch = 'ch%d' % n
        p = os.path.join(WORK, 'probe181b.ch%d.json' % n)
        if not os.path.exists(p):
            raise SystemExit(u'!! 缺反编译证据 %s' % p)
        d = json.load(io.open(p, encoding='utf-8'))
        for i in d['instances']:
            if i['obj'] != 'obj_climb_door':
                continue
            g = i.get('creation_gml') or ''
            m = None
            for ln in g.split('\n'):
                ln = ln.strip()
                if ln.startswith('doorRoom'):
                    m = ln.split('=', 1)[1].strip().rstrip(';').strip()
                    break
            src = by_rid.get((ch, i['room_index']))
            if not m or not src:
                unresolved.append((ch, i['room_index'], 'obj_climb_door',
                                   'no_doorRoom', None, None))
                continue
            dst = name2sid.get((ch, m))
            if not dst:
                unresolved.append((ch, i['room_index'], 'obj_climb_door',
                                   'no_scene', None, m))
                continue
            edges.append({
                'ch': ch, 'src': src, 'dst': dst,
                'src_idx': i['room_index'], 'dst_idx': None,
                'src_name': i['room'], 'dst_name': m,
                'kind': 'obj_climb_door', 'mech': u'room_goto(doorRoom)',
                'shift': None, 'ovr': False,
                'src_label': i.get('creation_code') or u'', 'how': u'room_goto(doorRoom)',
            })
    return edges, unresolved, sid2name


def hidden_rooms():
    u"""隐藏房登记（只写数据，不改行为；机制见第182轮）。"""
    return [
        {
            'scene': None,
            'scene_name': u'森林·man（隐藏房）',
            'from_scene': 'ch1.forest.forest_area5',
            'from_room': 'room_forest_area5',
            'probability': 0.02,
            'probability_expr': u'ceil(random(50)) == 50',
            'gate': u'global.flag[910] == 0',
            'once': True,
            'status': 'target_not_registered',
            'note': (u'原作确有这扇门，但目标房 room_man 在本项目里**没有登记成场景**'
                     u'（_index.json 查无此项）⇒ 无法落边，只登记证据。'),
            'evidence': (u'第181轮 probe181b.ch1.json → gml_Object_obj_doorX_musfade_Alarm_2：'
                         u'`if (room == room_forest_area5) { ch = ceil(random(50)); '
                         u'if (ch == 50 && global.flag[910] == 0) room_goto(room_man); '
                         u'else room_goto(room_forest_starwalker); }`'),
        },
        {
            'scene': 'ch2.cyber_city.dw_city_man',
            'scene_name': u'赛博都市·man',
            'from_scene': 'ch2.cyber_city.dw_city_traffic_3',
            'from_room': 'room_dw_city_traffic_3',
            'probability': 0.02,
            'probability_expr': u'ceil(random(50)) == 50',
            'gate': (u'scr_sideb_get_phase() == 0 && global.flag[917] < 2 '
                     u'&& global.flag[918] == 0'),
            'once': True,
            'status': 'data_only',
            'note': (u'现有 `_routes.json` 把 `dw_city_traffic_3 → dw_city_man` 记成**确定性边**'
                     u'（priority 7122），与原作 1/50 不符。第181轮只登记不改既有边；'
                     u'第182轮做加权挑选时再改成概率分支。'),
            'evidence': (u'第181轮 probe181b.ch2.json → gml_Object_obj_doorw_musfade_Alarm_2：'
                         u'`if (global.flag[917] == 0 && scr_sideb_get_phase() == 0) '
                         u'room_goto(room_dw_city_dog_traffic); else { var man_room = '
                         u'scr_sideb_get_phase() == 0 && global.flag[917] < 2 && '
                         u'global.flag[918] == 0 && ceil(random(50)) == 50; '
                         u'if (man_room) room_goto(room_dw_city_man); else room_goto(room_dw_city_moss); }`'),
        },
        {
            'scene': 'ch3.system.dw_ch3_man',
            'scene_name': u'系统与演出·ch3_man',
            'from_scene': None,
            'from_room': None,
            'probability': None,
            'probability_expr': None,
            'gate': None,
            'once': None,
            'status': 'no_incoming_edge',
            'note': u'场景已登记但路由表里**没有任何入边**；本轮取证未找到指向它的门代码，条件未解。',
            'evidence': u'第181轮 probe181b.ch1..ch5.json 全部 door 代码反编译，未见 room_dw_ch3_man 引用',
        },
        {
            'scene': 'ch4.second_sanctuary.dw_churchb_man',
            'scene_name': u'第二圣域·churchb_man',
            'from_scene': 'ch4.second_sanctuary.dw_churchb_windows',
            'from_room': 'room_dw_churchb_windows',
            'probability': None,
            'probability_expr': None,
            'gate': None,
            'once': None,
            'status': 'gate_unresolved',
            'note': (u'入边是 `obj_doorAny`（priority 7776），其实例 PreCreate **无条件**写 '
                     u'`doorRoom = room_dw_churchb_man`；概率/前置条件不在门对象代码里，'
                     u'本轮**未解**，不臆造数值。'),
            'evidence': (u'第181轮 probe181b.ch4.json → 实例 room_dw_churchb_windows 的 '
                         u'creation_gml：`doorRoom = room_dw_churchb_man; doorEntrance = 9; '
                         u'doorFadeMusic = 1;`'),
        },
    ]


def make_route(e, prio):
    ch = e['ch']
    if e['kind'] == 'obj_climb_door':
        reason = (
            u'原作 GML：房间 %s 的 `obj_climb_door` 在自己的实例创建代码 `%s` 里把 `doorRoom` '
            u'写成 %s；`Alarm_2` 执行 `event_user(7); instance_create(0,0,obj_persistentfadein); '
            u'room_goto(doorRoom)` ⇒ 落到 %s。'
            u'取证：第181轮 `probe181b.%s.json`（反编译 GML）。'
            % (e['src_name'], e['src_label'] or u'(缺名)', e['dst_name'],
               e['dst_name'], ch))
        orig = {
            'chapter': ch,
            'kind': 'delta_door_instance',
            'via': 'obj_climb_door',
            'code': 'gml_Object_obj_climb_door_Alarm_2',
            'precreate': e['src_label'] or None,
            'src_room_name': e['src_name'],
            'dst_room_name': e['dst_name'],
            'src_room_id': e['src_idx'],
            'batch': BATCH,
        }
        wd = None
    else:
        extra = u''
        if e['ovr']:
            extra = (u'（★ 该房有单点覆盖：`if (global.chapter == 3 && room == 110) '
                     u'{ room_goto(28); exit; }`，此处按覆盖落 28，不是 %d。）'
                     % (e['src_idx'] + e['shift']))
        reason = (
            u'原作 GML：房间 %s 的 `%s` 的 `Alarm_2` 执行 `%s`；位移 %+d 落在 '
            u'`Data.Rooms` **下标**上 ⇒ 落到 %s（下标 %d→%d）。%s'
            u'取证：第181轮 `probe181.%s.txt`（逐指令）+ `probe181b.%s.json`（反编译 GML）。'
            % (e['src_name'], e['kind'], e['mech'], e['shift'],
               e['dst_name'], e['src_idx'], e['dst_idx'], extra,
               ch, ch))
        orig = {
            'chapter': ch,
            'kind': 'delta_door_shift',
            'via': e['kind'],
            'code': 'gml_Object_%s_Alarm_2' % e['kind'],
            'shift': e['shift'],
            'src_room_name': e['src_name'],
            'dst_room_name': e['dst_name'],
            'src_room_id': e['src_idx'],
            'dst_room_id': e['dst_idx'],
            'batch': BATCH,
        }
        if e['ovr']:
            orig['override'] = 'global.chapter == 3 && room == 110'
        wd = door_letter(e['kind'])

    return {
        'to': e['dst'],
        'priority': prio,
        'reason': reason,
        'when_scene': e['src'],
        'when_door': wd,
        'when_src': e['kind'],
        '_original': orig,
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--go', action='store_true')
    a = ap.parse_args(argv)

    edges, unresolved, sid2name = build()
    raw = io.open(ROUTES, 'rb').read().decode('utf-8')
    doc = json.loads(raw)
    routes = doc['routes']

    # 既有 (when_scene, to) —— 不造重复边
    have = set((r.get('when_scene'), r.get('to')) for r in routes)
    # 本轮已落的（幂等判据）
    mine = set((r.get('when_scene'), r.get('to')) for r in routes
               if (r.get('_original') or {}).get('batch') == BATCH)

    new = []
    dup = 0
    for e in edges:
        k = (e['src'], e['dst'])
        if k in have:
            dup += 1
            continue
        have.add(k)
        new.append(e)

    # 稳定顺序：按 (章, 源下标, 门型) 排，保证两趟跑出同一份 priority
    new.sort(key=lambda t: (t['ch'], t['src_idx'], t['kind'], t['dst']))

    print(u'=' * 88)
    print(u'第181轮 · 落边（batch=%d，priority %d 起）%s'
          % (BATCH, PRIORITY_BASE, u'【真写】' if a.go else u'【dry-run】'))
    print(u'=' * 88)
    print(u'候选边 %d ｜ 与既有重复（跳过）%d ｜ 待落 %d ｜ 本轮已落 %d'
          % (len(edges), dup, len(new), len(mine)))
    print(u'')
    import collections
    c = collections.Counter(t['kind'] for t in new)
    for k, v in sorted(c.items(), key=lambda x: -x[1]):
        print(u'  %-24s %d' % (k, v))
    print(u'')
    print(u'--- 未解（不落边）%d 条 ---' % len(unresolved))
    for u_ in unresolved[:20]:
        print(u'  %-4s #%-5s %-22s %-14s -> %s %s'
              % (u_[0], u_[1], u_[2], u_[3], u_[4], u_[5]))

    if not new:
        print(u'')
        print(u'没有待落边（幂等：可能已落过）。')
        return 0

    if not a.go:
        print(u'')
        print(u'[dry-run] 前 5 条预览：')
        for i, e in enumerate(new[:5]):
            print(json.dumps(make_route(e, PRIORITY_BASE + i), ensure_ascii=False, indent=2))
        print(u'')
        print(u'加 --go 才写盘。')
        return 0

    # ---- 备份（放 D 临时区，不进工作区）----
    os.makedirs(WORK, exist_ok=True)
    bak = os.path.join(WORK, '_routes.before181.%d.json' % int(time.time()))
    shutil.copyfile(ROUTES, bak)
    print(u'')
    print(u'备份 → %s' % bak)

    for i, e in enumerate(new):
        routes.append(make_route(e, PRIORITY_BASE + i))

    # ---- 隐藏房登记（顶层新键；load_routes 忽略未知顶层键）----
    hr = hidden_rooms()
    if '_hidden_rooms' not in doc:
        doc['_hidden_rooms'] = hr
        print(u'新增顶层键 `_hidden_rooms`（%d 间）' % len(hr))
    else:
        print(u'`_hidden_rooms` 已存在，保持不动')

    out = json.dumps(doc, ensure_ascii=False, indent=2)
    # ★ 写前自检：目标场景必须存在
    bad = [r for r in routes if r['to'] not in sid2name]
    if bad:
        print(u'!! 有 %d 条 to 指向不存在的场景，中止' % len(bad))
        for r in bad[:5]:
            print(u'   ', r['to'])
        return 3
    io.open(ROUTES, 'wb').write(out.replace('\n', '\r\n').encode('utf-8'))

    # ---- 写后核验 ----
    doc2 = json.loads(io.open(ROUTES, 'rb').read().decode('utf-8'))
    r2 = doc2['routes']
    print(u'')
    print(u'写后核验：路由 %d → %d（+%d）' % (len(routes) - len(new), len(r2), len(r2) - (len(routes) - len(new))))
    uniq = set((r.get('when_scene'), r.get('to')) for r in r2)
    mine_dup = 0
    seen = set()
    for r in r2:
        if (r.get('_original') or {}).get('batch') != BATCH:
            continue
        k = (r.get('when_scene'), r.get('to'))
        if k in seen:
            mine_dup += 1
        seen.add(k)
    print(u'  (when_scene,to) 全表唯一对 %d / %d（**既有重复 %d 行，不是本轮造的**）'
          % (len(uniq), len(r2), len(r2) - len(uniq)))
    print(u'  本轮 batch=%d 内部重复 %d  %s'
          % (BATCH, mine_dup, u'OK' if mine_dup == 0 else u'!! 本轮自造了重复边'))
    print(u'  to 指向不存在场景 %d  %s'
          % (sum(1 for r in r2 if r['to'] not in sid2name),
             u'OK' if all(r['to'] in sid2name for r in r2) else u'!!'))

    os.makedirs(EV, exist_ok=True)
    io.open(os.path.join(EV, 'added181.json'), 'w', encoding='utf-8', newline='').write(
        json.dumps([make_route(e, PRIORITY_BASE + i) for i, e in enumerate(new)],
                   ensure_ascii=False, indent=2))
    io.open(os.path.join(EV, 'hidden_rooms181.json'), 'w', encoding='utf-8', newline='').write(
        json.dumps(hr, ensure_ascii=False, indent=2))
    print(u'证据 → _evidence/added181.json  hidden_rooms181.json')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

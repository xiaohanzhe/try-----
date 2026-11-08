# -*- coding: utf-8 -*-
u"""第174轮 · 把 `obj_doorAnyHorz` / `obj_doorAnyVert` 的边落进 `_routes.json`（**只增不改**）。

背景（本轮最重要的发现，全部有据）
--------------------------------
第172轮的分析脚本 `analyze172.py` **没有按 `obj` 过滤** —— 它把探针采到的
**全部** doorany 家族实例（`obj_doorAny` 830 + `obj_doorAnyHorz` 42 +
`obj_doorAnyVert` 9 = 881）都当成 `obj_doorAny` 处理，`via` 硬写成
`obj_doorAny`。用 `precreate` 名字反查探针里的真实实例对象，**798 条里有 42 条
真身是变体**（Horz 36 / Vert 6）：

    (ch5, gml_RoomCC_room_dw_garden_aquahole_19_PreCreate) -> obj_doorAnyHorz

后果有两层：
  ① 那 42 条边的 `when_src` / `via` **说的是假话**（数据缺陷，本轮只留档不改，
     因为改标签会动第172轮与第36轮两套账，须单独一轮裁定）；
  ② `obj_doorAnyHorz/Vert` 这 51 扇**从未物化**进场景 ⇒ 坐在这些房间里的
     玩家没有任何可用出口（例：`ch5.garden.garden_shrine` 在原作房间
     `room_dw_garden_aquahole` 里有 3 扇 Horz 门，产品里却一扇都没有）。

本轮就补 ②：**按每扇实例**落 51 条 `when_src = 真变体名` 的边 + 物化 51 个物件。

与第170/171/172轮 `apply*.py` 同规矩
------------------------------------
  1. **无损往返自检**：`json.dumps(indent=2)` 归一 CRLF 后必须与原文逐字相同，否则拒写；
  2. **幂等**：按 `(when_scene, to, when_src, door_x, door_y)` 去重，重复跑不会加第二遍；
  3. 写 `.new` → 复读 → 断言条数/无 BOM/CRLF → `os.replace`；
  4. priority 起点大于全表最大值，绝不撞号。

★ 为什么**一条实例一条边**而不是一对一条：
  同房可以有多扇变体门、目标两两不同，`_pick_by_pos` 靠 `door_x/door_y`
  逐扇对坐标；若按 (源,目标) 去重，第二扇的坐标在表里没有对应条目 ⇒
  挑不出唯一 ⇒ 退回 priority 最小 ⇒ 静默走错房间。实测 51 扇里 9 扇会被吞。

用法: python apply174.py [--dry]
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
ROUTES = os.path.join(SCENES, '_routes.json')
E172 = os.path.join(REPO, 'code-quality-audit', u'第172轮-Any门接线', '_evidence')

PRIO_BASE = 8100
BATCH = 174
CHS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']
#: 变体 → (自身事件表, 说明)。**这两个对象自身没有 Alarm_2**：
#: `room_goto(doorRoom)` 来自父对象 `obj_doorAny_Alarm_2`，由它们继承来的
#: `Other_19`（碰到玩家）里 `alarm[2] = 8` 触发 ⇒ `table` 如实写父表 + 备注。
VAR = {
    'obj_doorAnyHorz': ('gml_Object_obj_doorAny_Alarm_2', 'Step_1',
                        u'玩家乘平台时 x 相对 xstart 偏移 ±40（按房间左右半区）'),
    'obj_doorAnyVert': ('gml_Object_obj_doorAny_Alarm_2', 'Step_1',
                        u'玩家乘平台时 y 相对 ystart 偏移 ±40（按房间上下半区）'),
}


def load(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return json.load(f)


def room_names():
    """每章房名 → `Data.Rooms` 下标（用来补 `dst_room_id`）。"""
    out = {}
    for ch in CHS:
        p = os.path.join(E172, 'probe_any172.%s.json' % ch)
        if not os.path.isfile(p):
            continue
        out[ch] = dict((r['name'], r['index']) for r in (load(p).get('rooms') or []))
    return out


def main():
    dry = '--dry' in sys.argv
    an = load(os.path.join(EV, 'analyze174.json'))
    rows = [r for r in an['rows'] if r['kind'] == 'static_dst_ok' and r['src']]
    nm = room_names()

    # 同房「家族门的全部 x」—— 沿用第172轮 `door_x_all` 口径（只有该轴撞车才写 axis）
    fam = collections.defaultdict(list)
    for ch in CHS:
        p = os.path.join(E172, 'probe_any172.%s.json' % ch)
        if not os.path.isfile(p):
            continue
        for i in (load(p).get('instances') or []):
            if 'doorany' in str(i.get('obj') or '').lower():
                fam[(ch, i.get('room_index'))].append(i.get('x'))

    data = load(ROUTES)
    items = data.get('routes') if isinstance(data, dict) else data
    have = set()
    for q in items:
        o = q.get('_original') or {}
        have.add((q.get('when_scene'), q.get('to'), q.get('when_src'),
                  o.get('door_x'), o.get('door_y')))
    maxp = max([q.get('priority') for q in items if isinstance(q.get('priority'), int)] or [0])

    new_items, skipped = [], collections.Counter()
    for r in sorted(rows, key=lambda x: (x['obj'], x['src'], x['y'] or 0, x['x'] or 0)):
        key = (r['src'], r['dst'], r['obj'], r['x'], r['y'])
        if key in have:
            skipped['already'] += 1
            continue
        table, own_event, note = VAR.get(r['obj'], (None, None, None))
        if table is None:
            skipped['unknown_variant'] += 1
            continue
        xs = [v for v in fam.get((r['ch'], r['room_index']), []) if isinstance(v, int)]
        same_x = isinstance(r['x'], int) and xs.count(r['x']) > 1

        orig = collections.OrderedDict()
        orig['chapter'] = r['ch']
        orig['kind'] = 'delta_door_any_variant'
        orig['table'] = table
        orig['own_event'] = own_event
        orig['via'] = r['obj']
        orig['precreate'] = r['code']
        orig['src_room_name'] = r['room']
        orig['dst_room_name'] = r['doorroom']
        orig['src_room_id'] = r['room_index']
        rid = (nm.get(r['ch']) or {}).get(r['doorroom'])
        if isinstance(rid, int):
            orig['dst_room_id'] = rid
        orig['door_x'] = r['x']
        orig['door_y'] = r['y']
        if same_x:
            orig['axis'] = 'y'
        orig['door_x_all'] = sorted(set(xs))
        orig['batch'] = BATCH

        it = collections.OrderedDict()
        it['to'] = r['dst']
        it['priority'] = PRIO_BASE + len(new_items)
        it['reason'] = (
            u'原作 GML：%s 的 `%s` 实例（x=%s, y=%s）在自己的**实例创建代码** '
            u'`%s` 里把 `doorRoom` 写死成 %s ⇒ 继承来的 `Other_19`（碰到玩家）置 '
            u'`alarm[2]=8`、父对象 `Alarm_2` 执行 `room_goto(doorRoom)` 落到 %s。'
            u'（第174轮按实例补；此前 `_routes.json` 里一条 `%s` 边都没有 ⇒ '
            u'这些房间在产品里**没有任何出口**。★ 该对象 `%s` %s，因此本轮记录的'
            u'是 `xstart/ystart` 原值。）'
            % (r['room'], r['obj'], r['x'], r['y'], r['code'], r['doorroom'], r['dst'],
               r['obj'], own_event, note))
        it['when_scene'] = r['src']
        it['when_door'] = None
        it['when_src'] = r['obj']
        it['_original'] = orig
        new_items.append(it)

    print(u'候选实例 %d | 新增 %d | 已在表里(跳过) %d | 未知变体 %d'
          % (len(rows), len(new_items), skipped['already'], skipped['unknown_variant']))
    print(u'priority 段: %d ~ %d（全表 max=%d）'
          % (PRIO_BASE, PRIO_BASE + len(new_items) - 1, maxp))
    if not new_items:
        print(u'无新增，不写盘')
        return 0
    if PRIO_BASE <= maxp:
        print(u'!! PRIO_BASE(%d) 不大于全表最大 priority(%d) —— 拒写' % (PRIO_BASE, maxp))
        return 1
    if dry:
        print(u'[dry] 不写盘')
        return 0

    txt = io.open(ROUTES, encoding='utf-8', newline='').read()
    rt = json.dumps(data, ensure_ascii=False, indent=2).replace('\n', '\r\n')
    if rt != txt:
        print(u'!! 无损往返自检失败：不写盘（先查 indent/EOL 口径）')
        return 2

    items.extend(new_items)
    out = json.dumps(data, ensure_ascii=False, indent=2)
    tmp = ROUTES + '.new'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(out.replace('\n', '\r\n'))
    back = io.open(tmp, 'rb').read()
    if back.startswith(b'\xef\xbb\xbf'):
        print(u'!! 写出带 BOM，拒写')
        os.remove(tmp)
        return 3
    d2 = json.loads(back.decode('utf-8'))
    it2 = d2.get('routes') if isinstance(d2, dict) else d2
    if len(it2) != len(items):
        print(u'!! 复读条数不符 %d != %d' % (len(it2), len(items)))
        os.remove(tmp)
        return 4
    b0 = os.path.getsize(ROUTES)
    os.replace(tmp, ROUTES)
    print(u'落盘: %d -> %d 条；%d -> %d B'
          % (len(items) - len(new_items), len(items), b0, os.path.getsize(ROUTES)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

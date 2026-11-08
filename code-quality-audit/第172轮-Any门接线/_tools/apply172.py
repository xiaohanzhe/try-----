# -*- coding: utf-8 -*-
"""第172轮 · 把 `obj_doorAny` 的边落进 `_routes.json`（**只增不改**）。

与第170/171轮 `apply*.py` 同规矩：
  1. **无损往返自检**：`json.dumps(indent=2)` 归一 CRLF 后必须与原文逐字相同，否则拒写；
  2. **重复边不加**：与既有 `(when_scene, to)` 相同的候选直接剔除；
  3. 写 `.new` → 复读 → 断言条数/无 BOM/CRLF → `os.replace`；
  4. priority 起点大于全表最大值，绝不撞号。

字段口径（对齐既有 1,961 条；Any 门走**对象级** `when_src`，不用 `when_door`）：
  `when_scene` / `when_door: null` / `when_src: "obj_doorAny"` / `to` / `priority`
  `_original` = chapter / kind(delta_door_any) / table(Alarm_2) / via / precreate /
                src_room_name / dst_room_name / src_room_id / dst_room_id /
                door_x / door_y / axis(可选) / door_x_all / batch

★ `axis` 口径：同房有两扇 Any 门的 **x 相同** ⇒ 这扇只能按 y 分（写 `axis:"y"`）；
   否则按 x（不写 axis，与 168/169 一致）。同房 (x,y) **完全相同而目标不同** ⇒
   记进 `ambig`，报告出来（这种 `_pick_by_pos` 会挑不出唯一，退回老口径）。

用法: python apply172.py [--dry]
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

PRIO_BASE = 7300
BATCH = 172
CHS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']


def load(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return json.load(f)


def main():
    dry = '--dry' in sys.argv
    an = load(os.path.join(EV, 'analyze172.json'))
    rows = an['rows']

    # ---- 每章：房名 -> 下标（用于 dst_room_id）----
    name2rid, door_pos = {}, collections.defaultdict(list)
    for ch in CHS:
        p = os.path.join(EV, 'probe_any172.%s.json' % ch)
        if not os.path.exists(p):
            continue
        d = load(p)
        name2rid[ch] = dict((r['name'], r['index']) for r in (d.get('rooms') or []))
    for r in rows:
        door_pos[(r['ch'], r['room_index'])].append((r['x'], r['y'], r['dst'], r['kind']))

    # ---- 候选：可入边 + 目标已登记 + 源已登记 ----
    cand, skipped = [], collections.Counter()
    for r in rows:
        if r['kind'] != 'static_dst_ok':
            skipped['kind:' + r['kind']] += 1
            continue
        if not r.get('src'):
            skipped['src_unmapped'] += 1
            continue
        cand.append(r)
    cand.sort(key=lambda r: (r['ch'], r['src'], r['dst'], r['y'] or 0, r['x'] or 0))

    data = load(ROUTES)
    items = data.get('routes') if isinstance(data, dict) else data
    have_pair = set((q.get('when_scene'), q.get('to')) for q in items)
    maxp = max([q.get('priority') for q in items if isinstance(q.get('priority'), int)] or [0])

    added, dup, ambig = [], [], []
    seen = set()
    for r in cand:
        key = (r['src'], r['dst'])
        if key in seen:
            skipped['same_pair_in_this_batch'] += 1
            continue
        seen.add(key)
        if key in have_pair:
            dup.append(key)
            skipped['pair_exists'] += 1
            continue
        added.append(r)

    if PRIO_BASE <= maxp:
        print('!! PRIO_BASE(%d) 不大于全表最大 priority(%d) —— 拒写' % (PRIO_BASE, maxp))
        return 1

    new_items = []
    for i, r in enumerate(added):
        ch, room, ri = r['ch'], r['room'], r['room_index']
        dst = r['dst']
        dst_rid = name2rid.get(ch, {}).get(r['doorroom'])
        # 同房所有 Any 门的 x（door_x_all 口径 = 该 via 自己的全部 x）
        xs = [p[0] for p in door_pos[(ch, ri)] if isinstance(p[0], int)]
        x_all = sorted(set(xs))
        same_x = xs.count(r['x']) > 1 if isinstance(r['x'], int) else False
        # (x,y) 完全撞车且目标不同 ⇒ 消歧一定失败，记下来
        twins = [p for p in door_pos[(ch, ri)]
                 if p[0] == r['x'] and p[1] == r['y'] and p[2] and p[2] != dst]
        if twins:
            ambig.append((r['src'], r['x'], r['y'], dst, twins[0][2]))
        orig = collections.OrderedDict()
        orig['chapter'] = ch
        orig['kind'] = 'delta_door_any'
        orig['table'] = 'gml_Object_obj_doorAny_Alarm_2'
        orig['via'] = 'obj_doorAny'
        orig['precreate'] = r['code']
        orig['src_room_name'] = room
        orig['dst_room_name'] = r['doorroom']
        orig['src_room_id'] = ri
        if isinstance(dst_rid, int):
            orig['dst_room_id'] = dst_rid
        orig['door_x'] = r['x']
        orig['door_y'] = r['y']
        if same_x:
            orig['axis'] = 'y'
        orig['door_x_all'] = x_all
        orig['batch'] = BATCH

        it = collections.OrderedDict()
        it['to'] = dst
        it['priority'] = PRIO_BASE + i
        it['reason'] = (
            u'原作 GML：%s 的 `obj_doorAny` 实例（x=%s, y=%s）在**每实例创建代码** '
            u'`%s` 里把 `doorRoom` 写死成 %s ⇒ `Alarm_2` 的 `room_goto(doorRoom)` '
            u'落到 %s（第172轮按实例创建代码补；此前表里没有这条边 ⇒ 门查不到目标 ⇒ '
            u'按 E 没反应）。' % (room, r['x'], r['y'], r['code'], r['doorroom'], dst))
        it['when_scene'] = r['src']
        it['when_door'] = None
        it['when_src'] = 'obj_doorAny'
        it['_original'] = orig
        new_items.append(it)

    print('候选 %d | 新增 %d | 与既有重复(不加) %d | 本轮内重复 %d'
          % (len(cand), len(new_items), len(dup), skipped['same_pair_in_this_batch']))
    print('跳过明细: %r' % (dict(skipped),))
    print('priority 段: %d ~ %d' % (PRIO_BASE, PRIO_BASE + len(new_items) - 1))
    print('同房同 (x,y) 但目标不同（消歧会失效，须留档）: %d %r'
          % (len(ambig), ambig[:4]))
    if dry:
        print('[dry] 不写盘')
        return 0

    # ---- 无损往返自检（**必须用改动前的数据**；否则必然不等）----
    txt = io.open(ROUTES, encoding='utf-8', newline='').read()
    rt = json.dumps(data, ensure_ascii=False, indent=2).replace('\n', '\r\n')
    if rt != txt:
        print('!! 无损往返自检失败：不写盘（先查 indent/EOL 口径）')
        return 2

    items.extend(new_items)
    out = json.dumps(data, ensure_ascii=False, indent=2)

    tmp = ROUTES + '.new'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(out.replace('\n', '\r\n'))
    back = io.open(tmp, 'rb').read()
    if back.startswith(b'\xef\xbb\xbf'):
        print('!! 写出带 BOM，拒写'); os.remove(tmp); return 3
    d2 = json.loads(back.decode('utf-8'))
    it2 = d2.get('routes') if isinstance(d2, dict) else d2
    if len(it2) != len(items):
        print('!! 复读条数不符 %d != %d' % (len(it2), len(items))); os.remove(tmp); return 4
    b0 = os.path.getsize(ROUTES)
    os.replace(tmp, ROUTES)
    print('落盘: %d -> %d 条；%d -> %d B' % (len(items) - len(new_items), len(items),
                                          b0, os.path.getsize(ROUTES)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

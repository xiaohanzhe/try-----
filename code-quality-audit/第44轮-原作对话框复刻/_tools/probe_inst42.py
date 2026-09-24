# -*- coding: utf-8 -*-
"""只读量化：42 轮实例普查（inst42 / chN_inst42）能不能直接当渲染层的 objects 源。

问题（先量化再动手）：
  A. 五章实例普查覆盖了哪些房间？没覆盖的房间是"真没有实例"还是"脚本没抓"？
  B. 实例字段（obj/x/y/layer/depth）够不够 scene_render.plan_frame 用？
     —— 它要 `pos`(len 2) + `sprite|image|asset` 名；普查给的是 `x/y` + `obj`。
  C. 这些 obj 名（obj_xxx）在素材层有没有对应 sprite？（否则只能画占位）
  D. 普查里的房间 id 是否 = `Data.Rooms` 下标（能与 `_room_geometry.json` 的
     `ch:room_id` 键对齐）。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
E42 = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')

FILES = {'ch1': 'inst42.json', 'ch2': 'ch2_inst42.json', 'ch3': 'ch3_inst42.json',
         'ch4': 'ch4_inst42.json', 'ch5': 'ch5_inst42.json'}


def load(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def main():
    geo = load(os.path.join(SCENES, '_room_geometry.json'))
    geo_rooms = geo.get('rooms') or {}
    # geo 键 = 'ch1:2'
    geo_by_ch = {}
    for k in geo_rooms:
        ch, _, rid = k.partition(':')
        geo_by_ch.setdefault(ch, {})[int(rid)] = geo_rooms[k]

    print('=== 几何表 ===')
    for ch in sorted(geo_by_ch):
        print('%s: 几何 %d 间' % (ch, len(geo_by_ch[ch])))

    A = 0
    all_obj_names = {}
    ch_stat = {}
    empty_rooms = 0
    for ch in ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']:
        d = load(os.path.join(E42, FILES[ch]))
        rooms = d.get('rooms') or []
        stat = {'rooms': d.get('n_rooms_total'), 'hit': d.get('n_rooms_hit'),
                'inst': d.get('n_inst'), 'empty': 0, 'nodata': 0,
                'geo_mismatch': 0, 'ids_not_in_geo': 0}
        hit_ids = set()
        for rec in rooms:
            rid = rec.get('index')
            n = rec.get('n')
            hit_ids.add(rid)
            if n == 0:
                stat['empty'] += 1
                empty_rooms += 1
            # 几何对齐检查
            g = geo_by_ch.get(ch, {}).get(rid)
            if g is None:
                stat['ids_not_in_geo'] += 1
            elif (g.get('w'), g.get('h')) != (rec.get('w'), rec.get('h')):
                stat['geo_mismatch'] += 1
            for it in (rec.get('insts') or []):
                A += 1
                nm = it.get('obj')
                if nm:
                    all_obj_names[nm] = all_obj_names.get(nm, 0) + 1
        # 几何里有、普查里没有的房间数
        stat['geo_not_in_census'] = len(set(geo_by_ch.get(ch, {})) - hit_ids)
        ch_stat[ch] = stat

    print('')
    print('=== 逐章覆盖 ===')
    print('%-5s %7s %7s %8s %8s %11s %9s %9s' %
          ('章', '总房', '命中', '空房', '实例数', '几何缺普查', 'id不在几何', '几何不符'))
    for ch in ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']:
        s = ch_stat[ch]
        print('%-5s %7d %7d %8d %8d %11d %9d %9d' %
              (ch, s['rooms'], s['hit'], s['empty'], s['inst'],
               s['geo_not_in_census'], s['ids_not_in_geo'], s['geo_mismatch']))

    print('')
    print('=== 实例总计 ===')
    print('实例总条数 = %d' % A)
    print('不同 obj 名 = %d' % len(all_obj_names))
    top = sorted(all_obj_names.items(), key=lambda kv: -kv[1])[:25]
    print('Top 25 obj:')
    for nm, c in top:
        print('  %6d  %s' % (c, nm))

    print('')
    print('=== 房间索引对齐（真值锚点）===')
    d1 = load(os.path.join(E42, 'inst42.json'))
    for rec in (d1.get('rooms') or []):
        if rec.get('index') == 2:
            print('ch1 room 2 = %s %dx%d n=%d' % (rec.get('name'), rec.get('w'), rec.get('h'), rec.get('n')))
            print('  几何表 ch1:2 =', json.dumps(geo_rooms.get('ch1:2'), ensure_ascii=False))
            for it in (rec.get('insts') or [])[:3]:
                print('   ', json.dumps(it, ensure_ascii=False))
            break

    print('')
    print('RESULT: 实例总计 %d，obj 名 %d' % (A, len(all_obj_names)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

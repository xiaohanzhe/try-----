# -*- coding: utf-8 -*-
u"""Deltarune 跨作品物件普查（第115轮）—— 回答「除了 OneShot，其它作品怎么整理」。

数据从哪来：五章 `data.win` 经 UTMT 反编译后的两份产物（**已蒸馏进 `_evidence/raw/chN/`**，
不再依赖 `E:/Download/_tmp`）：
  · `rooms_map.json` —— 每间房的层与层里的**实例名**（`{"rooms":[{"name","width","layers":
    [{"type":"Instances","instances":["obj_chair", …]}]}]}`），**只有名字、没有坐标**。
  · `objmap43.txt` —— 353+ 个 GameObject 的 `id / 名字 / spr= / vis= / pers=`。

★★ 与 OneShot 的**根本差别**（这决定了后续做法完全不同）：
  OneShot 是 Tiled 瓦片地图，物件只是"一坨格子"，**没有名字**（4380 块里 3456 块无名）⇒
  只能靠图案签名去重、请用户起名。
  Deltarune 是 GameMaker，物件是**有名字的实例**（`obj_chair` / `obj_pizza`）⇒
  **不需要起名**，需要的是「这个名字是干嘛的」= 功能简介。

所以本工具的产物不是"待命名清单"，而是：
  ① 每个 obj 的**知名度**（出现在几间房、多少个实例）—— 先写高频的，收益最大；
  ② **能看到但名字不表意**的那批（`obj_prop_*` / `obj_thing` / 单字母），这才是需要人补的一类；
  ③ 纯逻辑对象（无 sprite / 不可见）单独剔出去，别混进"画面上的东西"。

★ 数据缺口（必须说清）：`rooms_map.json` **没有实例坐标**。要做"这块地毯在哪一格"那级别的
  物件表，得重新跑 UTMT 写新的 csx 采 x/y（第115轮未做，列待办）。
"""
import argparse
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
RAW = os.path.join(ROUND, '_evidence', 'raw')

#: 每章房间数（既有记录：1,251 间；用来钉住"读全了没"）
EXPECT_ROOMS = {1: 147, 2: 278, 3: 246, 4: 328, 5: 252}

#: 名字不表意的形态：obj_prop_1 / obj_thing / obj_x2 / 单个字母
_VAGUE = re.compile(r'(^obj_(prop|thing|stuff|misc|obj|deco)\b|_?\d+$|^obj_[a-z]$)', re.I)


def load_objmap(ch):
    u"""`objmap43.txt` 逐行：`id\\tname\\tspr=xxx\\tvis=True\\tpers=False`。"""
    p = os.path.join(RAW, 'ch%d' % ch, 'objmap43.txt')
    out = {}
    for ln in io.open(p, encoding='utf-8', errors='replace'):
        parts = ln.rstrip('\n').split('\t')
        if len(parts) < 2 or not parts[0].strip().isdigit():
            continue
        d = {'id': int(parts[0]), 'name': parts[1].strip()}
        for extra in parts[2:]:
            k, _, v = extra.partition('=')
            d[k.strip()] = v.strip()
        out[d['name']] = d
    return out


def load_rooms(ch):
    p = os.path.join(RAW, 'ch%d' % ch, 'rooms_map.json')
    return json.load(io.open(p, encoding='utf-8'))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROUND, '_evidence',
                                                  'deltarune_objects115.json'))
    a = ap.parse_args(argv)

    objs = collections.OrderedDict()      # 名字 → 汇总
    per_chapter = {}
    for ch in sorted(EXPECT_ROOMS):
        d = load_rooms(ch)
        om = load_objmap(ch)
        rooms = d['rooms']
        assert len(rooms) == EXPECT_ROOMS[ch], (
            u'ch%d 房间数 %d ≠ 预期 %d ⇒ 数据没读全' % (ch, len(rooms), EXPECT_ROOMS[ch]))
        n_inst = 0
        used = set()
        for r in rooms:
            seen_here = set()
            for ly in r.get('layers') or []:
                # ★ 只有 `Instances` 层装的是对象实例；`Background`/`Tiles`/`Assets` 层
                #   在 ch1 的产物里根本没有 `instances` 键（实测）。别把别的层混进来。
                if (ly.get('type') or '') != 'Instances':
                    continue
                for nm in ly.get('instances') or []:
                    assert isinstance(nm, str) and nm, u'ch%d 出现空实例名' % ch
                    n_inst += 1
                    used.add(nm)
                    seen_here.add(nm)
                    e = objs.get(nm)
                    if e is None:
                        e = objs[nm] = {'name': nm, 'rooms': set(), 'inst': 0,
                                        'chapters': set(),
                                        'sprite': om.get(nm, {}).get('spr') or '',
                                        'vis': om.get(nm, {}).get('vis', ''),
                                        'pers': om.get(nm, {}).get('pers', ''),
                                        'in_objmap': nm in om}
                    e['inst'] += 1
                    e['chapters'].add(ch)
            # 「出现在几间房」按房计一次（同一间房里同名实例可能叠放多个）
            for nm in seen_here:
                objs[nm]['rooms'].add((ch, r['name']))
        per_chapter[ch] = {'rooms': len(rooms), 'instances': n_inst,
                           'objects_used': len(used), 'objects_defined': len(om),
                           'rooms_empty': sum(1 for r in rooms
                                              if not any((ly.get('instances') or [])
                                                         for ly in r.get('layers') or []))}
        print(u'ch%d：房间 %d｜实例 %d｜用到的对象 %d｜定义的对象 %d｜零实例房间 %d'
              % (ch, len(rooms), n_inst, len(used), len(om),
                 per_chapter[ch]['rooms_empty']))

    rows = []
    for nm, e in objs.items():
        rows.append({'name': nm, 'sprite': e['sprite'], 'vis': e['vis'],
                     'pers': e['pers'], 'rooms': len(e['rooms']),
                     'inst': e['inst'], 'chapters': sorted(e['chapters']),
                     'in_objmap': e['in_objmap'],
                     'vague': bool(_VAGUE.search(nm)),
                     # 能看到 = 有 sprite 且 vis=True；这类才是"画面上的东西"
                     'visible_prop': bool(e['sprite']) and e['vis'] == 'True'})
    rows.sort(key=lambda r: (-r['rooms'], -r['inst'], r['name']))

    total_inst = sum(r['inst'] for r in rows)
    vis = [r for r in rows if r['visible_prop']]
    logic = [r for r in rows if not r['visible_prop']]
    vague = [r for r in vis if r['vague']]
    missing = [r for r in rows if not r['in_objmap']]
    print(u'\n合计对象 %d 个（实例 %d 次）' % (len(rows), total_inst))
    print(u'  有 sprite 且可见（画面上的物件）%d 个，占实例 %.1f%%'
          % (len(vis), 100.0 * sum(r['inst'] for r in vis) / max(1, total_inst)))
    print(u'  纯逻辑 / 无 sprite / 不可见 %d 个' % len(logic))
    print(u'  其中名字不表意（obj_prop_* / 带编号 / 单字母）%d 个' % len(vague))
    if missing:
        print(u'  ⚠️ 不在 objmap 里的 %d 个：%s' % (len(missing), [r['name'] for r in missing][:8]))
    print(u'\n出现房间最多的 10 个：')
    for r in rows[:10]:
        print(u'   %-28s %4d 间 / %5d 次  spr=%-22s ch%s'
              % (r['name'], r['rooms'], r['inst'], r['sprite'] or '-', r['chapters']))
    print(u'\n名字不表意的可见物件（需要人补功能简介的那一类）：')
    for r in vague[:12]:
        print(u'   %-28s %3d 间  spr=%s' % (r['name'], r['rooms'], r['sprite']))

    payload = {'note': u'第115轮 Deltarune 物件普查（数据来自五章 data.win 的 UTMT 产物，'
                       u'rooms_map.json 只有实例名、无坐标）',
               'per_chapter': per_chapter,
               'totals': {'objects': len(rows), 'instances': total_inst,
                          'visible_props': len(vis), 'logic_only': len(logic),
                          'vague_names': len(vague)},
               'objects': rows}
    d = os.path.dirname(a.out)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=1))
    print(u'\n清单 → %s (%.1f KB)' % (a.out, os.path.getsize(a.out) / 1024.0))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))

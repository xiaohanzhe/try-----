# -*- coding: utf-8 -*-
u"""第121轮：把 ut 的**可交互物**写进场景 `objects`（在此之前 358 个场景全是空数组）。

## 为什么要这一步

第120轮把 ut 的画面烘成了背景图，但 `objects` 仍是 `[]` ⇒ 产品侧
`item_interact.build_props()` 遍历 `scene['objects']` 找不到任何东西 ⇒
**走进去什么都点不了**（可读物、存档点、告示牌全哑）。画面有了，交互没有。

## 三条口径（每条都有取证）

1. **只写现在真能用的 6 类**：`readable` / `sign` / `savepoint` / `pickup` /
   `fountain` / `interactable`。
   · `door`(1,299 个实例) **不写** —— `build_props` 建门要 `routes` 表，
     ut 侧还没有 `_routes.json` 条目（第109轮只做了桌面 4 门）。没有目标就建门，
     就是"推不开的门"。等路由那轮一起做。
   · `cutscene`(375) **不写** —— `build_props` 落 `else` 直接丢弃，写了也是噪音。
   · `marker` 属 `NON_INTERACTIVE_KINDS`，本来就不该进。

2. **`sprite` 一律写 `null`**（不是省略键）。理由：
   · ut 的画面**已经在背景图里**（第120轮烘的），再画一遍就是重复绘制；
   · `_obj_visible.json` 那张 `hidden` 名单是**全局扁平**的，ut 的
     `obj_savepoint`(vis=True) 与 Deltarune 的 `obj_savepoint`(要画) **同名**
     ⇒ 并进全局名单会**跨作品污染**（实测冲突 1 个：`obj_savepoint`）。
   · `scene_render` 对 `sprite=None` 的处理是 `name=None` → `_paint_obj`
     的 `assets.get(name) if name else None` ⇒ **不落笔**，不崩（已逐行核过）。
   ⇒ 条目语义：**"这里有个可交互物，画面已在背景里"**。

3. **`pos` 用左上角语义** `[x-ox, y-oy]`。
   · `scene_render` 的 rect 就是左上角；`gen_objects44` 的 docstring 也这么写。
   · 烘图（`bake120`）画实例用的**正是** `(x-ox, y-oy)` ⇒ 两者同一坐标系。
   · ⚠️ Deltarune 侧 `gen_objects44` 写的是 `[x, y]`（没减原点）—— 那是既有欠账，
     本轮不动它（会改 10,608 条），只在报告里登记。

## 幂等

连跑两次字节相同（排序固定：按 `pos.y, pos.x, src`）。

用法：python build_objs121.py [--dry-run]
"""
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
ROUND120_TOOLS = os.path.join(os.path.dirname(ROUND), '第120轮-ut场景背景与物件', '_tools')

sys.path.insert(0, ROUND120_TOOLS)
sys.path.insert(0, os.path.join(REPO, 'ralsei_pet', 'modules'))

import bake120 as B              # noqa: E402  复用第120轮的载入器（不写第二份口径）
import item_interact as II       # noqa: E402  复用产品的分类器（不写第二份 kind 表）

ZONE = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_zone.ut.rooms.json')

#: 本轮写进 objects 的 kind（见 docstring 第 1 条）
WANT_KINDS = ('readable', 'sign', 'savepoint', 'pickup', 'fountain', 'interactable')

#: `pos` 塌缩成一行 —— 与 Deltarune 侧 `gen_objects44` 的排版一致
_RE_POS = re.compile(r'"pos": \[\s*(-?\d+),\s*(-?\d+)\s*\]')


def _rows(path):
    for ln in io.open(path, encoding='utf-8', newline='').read().split('\n'):
        if ln:
            yield ln.split('\t')


def _load_all():
    u"""载入第120轮那套「房间 / 精灵原点 / 实例 / 对象可见性」——**复用同一个实现**。"""
    viz = os.path.join(os.path.dirname(ROUND), '第120轮-ut场景背景与物件',
                       '_evidence', 'raw', 'ut', 'viz120.ut.tsv')
    rooms, _layers, _lbg, _lsp, spr = B.load_viz(viz)
    objs = B.load_objmap('ut')
    origin = {}
    for (nm, _f), v in spr.items():
        origin.setdefault(nm, (v['ox'], v['oy']))
    for o in objs.values():
        o['ox'], o['oy'] = origin.get(o['spr'], (0, 0))
    return rooms, objs, B.load_inst('ut')


def build_objects(insts_of_room, objs):
    u"""一间房的实例 → `objects` 列表（只收 WANT_KINDS）。"""
    out = []
    for it in insts_of_room:
        src = it['obj']
        rec = II.classify(src)
        if not rec or rec['kind'] in II.NON_INTERACTIVE_KINDS:
            continue
        if rec['kind'] not in WANT_KINDS:
            continue
        o = objs.get(src) or {}
        out.append({
            'pos': [int(it['x']) - int(o.get('ox', 0)),
                    int(it['y']) - int(o.get('oy', 0))],
            'sprite': None,
            'src': src,
            'depth': int(it['depth']),
        })
    # 确定性排序（幂等的必要条件）
    out.sort(key=lambda e: (e['pos'][1], e['pos'][0], e['src']))
    return out


def dump_like(path, data):
    u"""按仓库既有排版写回（`indent=1` / `ensure_ascii=False` / LF），并把 `pos` 塌缩。"""
    s = json.dumps(data, ensure_ascii=False, indent=1).replace('\r\n', '\n')
    s = _RE_POS.sub(lambda m: '"pos": [%s, %s]' % (m.group(1), m.group(2)), s)
    if not s.endswith('\n'):
        s += '\n'
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def main(argv):
    dry = '--dry-run' in argv
    rooms, objs, insts = _load_all()

    zone = json.load(io.open(ZONE, encoding='utf-8', newline=''))
    scenes = zone['scenes']

    # 房间名 → 实例（第120轮同样按名字对齐，不按下标：20 个附加房间的下标不是 UT 的）
    by_name = {}
    for ri, items in insts.items():
        r = rooms.get(ri)
        if r is not None:
            by_name[r['name']] = items

    stat = {'scenes': 0, 'with': 0, 'entries': 0, 'no_inst': 0}
    per_kind = {}
    for sid, sc in scenes.items():
        if not isinstance(sc, dict):
            continue
        stat['scenes'] += 1
        items = by_name.get(sc.get('name'))
        if items is None:
            stat['no_inst'] += 1
            sc['objects'] = []
            continue
        lst = build_objects(items, objs)
        sc['objects'] = lst
        if lst:
            stat['with'] += 1
        stat['entries'] += len(lst)
        for e in lst:
            k = (II.classify(e['src']) or {}).get('kind')
            per_kind[k] = per_kind.get(k, 0) + 1

    print('场景 %d；有实例的房间 %d；无实例（20 个附加场景）%d'
          % (stat['scenes'], stat['scenes'] - stat['no_inst'], stat['no_inst']))
    print('写入 objects 的条目 %d，分布在 %d 个场景' % (stat['entries'], stat['with']))
    print('按 kind：%s' % dict(sorted(per_kind.items(), key=lambda kv: -kv[1])))
    if dry:
        print('[dry-run] 不写盘')
        return 0
    dump_like(ZONE, zone)
    print('[ok] 已写回 %s' % os.path.relpath(ZONE, REPO))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))

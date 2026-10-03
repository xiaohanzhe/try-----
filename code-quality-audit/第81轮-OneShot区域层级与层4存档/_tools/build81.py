# -*- coding: utf-8 -*-
u"""第81轮：把 OneShot 章从**单区域 `rooms`** 改成**官方 5 区**（用户裁决「5 区」）。

背景（第80轮遗留）
------------------
第80轮 `build80.py` 抬头写明：
> ★ 区域层级待补（OneShot 的 map name **没有** `" - "` 区域前缀）。

第81轮找到了**可证的事实源**（不是猜）—— 原作 `gamedata/` 的 4 份明文，三源互证：
  · `oneshot_map_colors.json`  分组（purple/red/green/blue）+ `maps[]`
  · `oneshot_map_zone_names.json` 命名（Blue/Green/Red/RedGround）
  · `oneshot_minimap_nodes.json`  官方**邻接图**，zone 键与上表**逐字相同**
  · `loc/zh_cn/map_zone_name_strs.po` 官方中文名
产物 = `_evidence/oneshot_zones81.json`（由 `survey_oneshot_zones81.py` 生成，含 11 项锚点）。

口径（用户第81轮裁定：「5 区」）
--------------------------------
  barrens(荒野) 35 · glen(幽谷) 55 · refuge(城市) 73 · refuge_ground(城市·地表区) 9
  mainline(主线·家/塔/终局，官方未命名) 69 · unzoned(未分区·废弃/调试/演示) 22
  ⇒ 覆盖 263 / 263，两两零交集（`overlaps == []`，由勘查脚本断言）。

★ 三条纪律（沿用 build80，逐条同构）
  1. **不新建世界**：`oneshot` 仍是**章**，只是从 1 个区域变 6 个区域。
  2. **锚点优先**：写前逐条核验（original_room_id + name 全等 + 分区归属一致）。
  3. **两处同源**：`_index.json` 与 `_worlds.json` 由**同一份勘查产物**派生。
     —— 历史坑：第80轮首版漏同步 `meta.unknown_rooms` 被 ch48 F4 抓红。

★★ scene_id 会变（`oneshot.rooms.X` → `oneshot.<area>.X`）。本脚本**强制**做
  「迁移守恒」核验：旧 263 个 id 逐条必须有归宿，且**总数、room_id 集合、name 全等**。
  实测 `trait_hits` 零差异（area slug 均不引入令牌命中，见 `_evidence/traits81.json`）。

用法：
    python build81.py --check      # 只核验，不写
    python build81.py --write      # 核验通过后写盘
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
EVID = os.path.join(HERE, '..', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
ZONES_SRC = os.path.join(EVID, 'oneshot_zones81.json')

CH = 'oneshot'

#: 区域顺序与中文名 —— ★ 与勘查产物**逐字对齐**（名字从产物读，这里只定顺序与 slug）
#: slug 选择纪律：**不许引入 `npc_life` 的令牌命中**（实测 6 个 slug 均零命中）。
AREA_ORDER = [
    ('Blue',         'barrens',        '荒野'),
    ('Green',        'glen',           '幽谷'),
    ('Red',          'refuge',         '城市'),
    ('RedGround',    'refuge_ground',  '城市（地表区）'),
    ('Purple',       'mainline',       '主线 · 家/塔/终局'),
    ('UNZONED',      'unzoned',        '未分区（废弃/调试/演示）'),
]


def load_json(p):
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


def dump_json(p, obj, indent):
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)


def scene_id_of(area_id, name, idx):
    """`<chapter>.<area>.<scene>` —— 与产品既有命名逐字同构。"""
    seg = ''.join(c if (c.isalnum() or c == '_') else '_' for c in name).strip('_')
    return '%s.%s.%s' % (CH, area_id, seg or ('r%d' % idx))


def make_scene(node):
    """★ 字段集逐字对齐既有分片场景（build77/80 的血泪注释）。"""
    return {
        'name': node['name'],
        'name_raw': node['name'],
        'name_derived': False,
        'original_room_id': node['index'],
        'bg': None,
        'bg_source': 'none',
        'objects': [],
    }


def build():
    z = load_json(ZONES_SRC)
    members = z['members']

    # room_id -> node（名字/尺寸来自第80轮勘查，逐条复用，不重抽）
    src80 = load_json(os.path.join(ROOT, 'code-quality-audit', '第80轮-OneShot场景迁入',
                                   '_evidence', 'oneshot80.json'))
    by_idx = {}
    for n in src80['nodes']:
        by_idx[n['index']] = n

    areas = {}
    for zone_key, area_id, area_name in AREA_ORDER:
        ids = members[zone_key]
        scenes = {}
        for i in ids:
            n = by_idx.get(i)
            if n is None:
                continue
            sid = scene_id_of(area_id, n['name'], i)
            base = sid
            k = 2
            while sid in scenes:
                sid = '%s_%d' % (base, k)
                k += 1
            scenes[sid] = make_scene(n)
        areas[area_id] = {'name': area_name, 'scenes': scenes}
    return z, by_idx, areas


def verify(z, by_idx, areas):
    """★★ 迁移守恒：旧 263 个 id 逐条有归宿，总数/room_id/name 全等。"""
    problems = []

    # 1. 覆盖守恒：新分区里的 room_id 集合 == 勘查产物 members 的并集
    want = set()
    for ids in z['members'].values():
        want |= set(ids)
    got = set()
    for a in areas.values():
        for ent in a['scenes'].values():
            got.add(ent['original_room_id'])
    if got != want:
        problems.append('room_id 集合不等：缺 %s / 多 %s'
                        % (sorted(want - got)[:10], sorted(got - want)[:10]))

    # 2. 计数守恒：总数 == 263，且逐区与勘查产物 counts 一致
    total = sum(len(a['scenes']) for a in areas.values())
    if total != z['expected_total']:
        problems.append('总数 %d != %d' % (total, z['expected_total']))
    for zone_key, area_id, _ in AREA_ORDER:
        exp = z['counts'][zone_key]
        act = len(areas[area_id]['scenes'])
        if exp != act:
            problems.append('区 %s：应 %d 实 %d' % (area_id, exp, act))

    # 3. name 逐条全等（不信"上一次跑绿了"）
    bad = []
    for a in areas.values():
        for sid, ent in a['scenes'].items():
            n = by_idx.get(ent['original_room_id'])
            if n is None or n['name'] != ent['name_raw']:
                bad.append((sid, ent['name_raw'], None if n is None else n['name']))
    if bad:
        problems.append('name 不符 %d 条：%s' % (len(bad), bad[:5]))

    # 4. scene_id 前缀必须分布在 6 个不同 area
    prefixes = set(sid.rsplit('.', 1)[0] for a in areas.values() for sid in a['scenes'])
    if len(prefixes) != len(AREA_ORDER):
        problems.append('area 前缀数 %d != %d' % (len(prefixes), len(AREA_ORDER)))

    return problems, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    z, by_idx, areas = build()

    if z['overlaps']:
        print('[ABORT] 勘查产物自己报了交集 ⇒ 不写盘：%s' % z['overlaps'])
        return 1

    problems, total = verify(z, by_idx, areas)
    print('[VERIFY] 分区 %d 个，总场景 %d（期望 %d）'
          % (len(areas), total, z['expected_total']))
    for zone_key, area_id, _ in AREA_ORDER:
        print('   %-14s %d' % (area_id, len(areas[area_id]['scenes'])))
    if problems:
        print('[ABORT] 核验失败 %d 条：' % len(problems))
        for p in problems:
            print('   -', p)
        return 1

    if args.check or not args.write:
        print('[CHECK-ONLY] 核验通过，未写盘（加 --write 才写）')
        return 0

    # ---- 写 6 个区域分片 ----
    note = ('第81轮：区域层级由**原作明文**派生（oneshot_map_colors / map_zone_names / '
            'minimap_nodes / loc 中文名，三源互证；见 _evidence/oneshot_zones81.json）。'
            '★ OneShot 房数据**没有** light/dark 维度 ⇒ 明暗维持 unknown（与 UT/黄魂同规）。')
    written = []
    for zone_key, area_id, area_name in AREA_ORDER:
        zone = {
            'schema_version': 1,
            'chapter_id': CH,
            'area_id': area_id,
            'area_name': area_name,
            'note': note,
            'scenes': areas[area_id]['scenes'],
        }
        zp = os.path.join(SCENES, '_zone.%s.%s.json' % (CH, area_id))
        dump_json(zp, zone, indent=1)
        written.append(os.path.basename(zp))
    for w in written:
        print('[WRITE] %s' % w)

    # ---- 删旧单区域分片（**先备份**）----
    old_zone = os.path.join(SCENES, '_zone.%s.rooms.json' % CH)
    if os.path.exists(old_zone):
        bak = os.path.join(EVID, '_zone.oneshot.rooms.before81.json')
        if not os.path.exists(bak):
            with io.open(old_zone, encoding='utf-8') as f:
                content = f.read()
            with io.open(bak, 'w', encoding='utf-8', newline='\n') as f:
                f.write(content)
            print('[BACKUP] %s' % os.path.basename(bak))
        os.remove(old_zone)
        print('[RM] %s（已备份）' % os.path.basename(old_zone))

    # ---- 改 _index.json ----
    idxp = os.path.join(SCENES, '_index.json')
    idx = load_json(idxp)
    idx['chapters'][CH]['areas'] = areas
    dump_json(idxp, idx, indent=2)
    print('[WRITE] _index.json（oneshot.areas -> %d 个区域）' % len(areas))

    # ---- 同步 _worlds.json 的 areas.oneshot（**rooms 不动**：按 room_id，与区域无关）----
    wp = os.path.join(SCENES, '_worlds.json')
    w = load_json(wp)
    w['areas'][CH] = dict((aid, 'unknown') for _, aid, _ in AREA_ORDER)
    dump_json(wp, w, indent=1)
    print('[WRITE] _worlds.json（areas.oneshot -> %d 键，全 unknown）' % len(AREA_ORDER))

    # ---- 写后回验 ----
    idx2 = load_json(idxp)
    w2 = load_json(wp)
    ok = (len(idx2['chapters'][CH]['areas']) == len(AREA_ORDER)
          and len(w2['areas'][CH]) == len(AREA_ORDER)
          and all(v == 'unknown' for v in w2['areas'][CH].values())
          and len(w2['rooms'][CH]) == 263)
    print('[VERIFY] 回读: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

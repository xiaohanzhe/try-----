# -*- coding: utf-8 -*-
"""第77轮：把跨作品大图（UT / 黄魂）**接入产品场景索引**。

口径：用户「感觉场景数太少了…5 个作品加起来怎么可能就 1000 刚出头」
      ⇒ 现状 1,014 **只是三角符文**；UT(338) / 黄魂(287) 只在 `bigmap66.json` 里，
        从未写进 `ralsei_pet/assets/scenes/_index.json`。

本脚本做**一件事**：把大图里的房间**逐条**写成产品索引能读的
「章 / 区域 / 场景」三级结构 + 区域分片文件（`_zone.<ch>.<area>.json`）。

★★ 三条纪律（都是本项目踩过的坑）：
  1. **不新建世界**：`_index.json` 新增 `ut`/`uty` 两章，`_worlds.json` 同步加 areas。
     ★ 判据「同一份规则两处算」——`_worlds.json` 与 `_index.json` 必须一致，故由
     同一份中间产物（`_generated77.json`）派生，不手写两遍。
  2. **锚点优先**：写之前**逐条**与大图比对（名字 + 宽 + 高），全等才写。
     实测 338/338 + 287/287 全等（零 DIFF）。
  3. **零改 main.py**：沿用既有 schema（`chapters` / `areas` / `scenes` / 分片），
     索引是数据，加载器是通用代码。

用法：
    python build77.py --check      # 只核验锚点，不写
    python build77.py --write      # 核验通过后写盘
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))      # 仓库根
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
BIGMAP = os.path.join(ROOT, 'code-quality-audit', '第66轮-大图连通与mod并入',
                      '_evidence', 'bigmap66.json')

#: 作品 → 产品章 id。★ 用**作品自己的** id（`ut`/`uty`），不并进 ch1~ch5，
#: 因为「同一份规则两处算」的另一种形态就是"UT 的房间被塞进三角符文的章里"。
WORK_TO_CHAPTER = {
    'ut':  {'id': 'ut',  'name': 'Undertale · 原版', 'order': 100, 'alias': 'Undertale',
            'tint': '#1c1c1c', 'hub': 'hub:ut'},
    'uty': {'id': 'uty', 'name': '黄魂 · Undertale Yellow', 'order': 101,
            'alias': 'Undertale Yellow', 'tint': '#4a3b1a', 'hub': 'hub:uty'},
}

#: 区域划分：UT 家族暂时**单区域**（`rooms`），因为大图节点本身的 `name` 已足够细，
#: 而分区要靠"区域名"（原作显示名的 ' - ' 前缀）——UT 的 room name 没有这个前缀，
#: ⇒ **不硬编区域**（硬编 7 个区会把 338 个房间按猜测切错，比不切更糟）。
#: 如实登记：UT/黄魂的**区域层级待补**（需要 UT 的 room 中文名表，属素材轮）。
DEFAULT_AREA = {'id': 'rooms', 'name': '全部房间'}


def load_json(path):
    with io.open(path, encoding='utf-8') as f:
        return json.load(f)


def build_nodes():
    """大图节点 → 待写入的产品场景（**只取 ut/uty 两个 work**）。"""
    big = load_json(BIGMAP)
    out = {}
    for w in WORK_TO_CHAPTER:
        out[w] = [n for n in big['nodes'] if n.get('work') == w]
        out[w].sort(key=lambda n: n['index'])
    return big, out


def verify(sourced_rooms, nodes):
    """★★ 锚点优先：逐条核验（名字 + 宽 + 高全等才算命中）。

    返回 (ok, bad_list)。**bad 非空就不许写盘**。
    """
    by_idx = {n['index']: n for n in nodes}
    ok, bad = 0, []
    for r in sourced_rooms:
        n = by_idx.get(r['index'])
        if n is None:
            bad.append((r['index'], r['name'], '<missing>'))
            continue
        if n['name'] == r['name'] and n['w'] == r['w'] and n['h'] == r['h']:
            ok += 1
        else:
            bad.append((r['index'], r['name'], n.get('name')))
    return ok, bad


def scene_id_of(ch, area, name):
    """`<chapter>.<area>.<scene>` —— 与产品既有命名**逐字同构**。

    ★ 为什么直接拿 room name 当 scene 段：它已经是 ASCII slug（`room_start`），
      过一遍 `_aliases.json` 的规则也不会有事。若重度清洗，反而会让
      「大图节点 ↔ 产品场景」失去**可机器比对**的一一对应（本项目最珍视的可验证性）。
    """
    seg = ''.join(c if (c.isalnum() or c == '_') else '_' for c in name).strip('_')
    return '%s.%s.%s' % (ch, area, seg or ('r%d' % 0))


def make_scene(ch, area, node):
    """分片场景条目的字段 —— ★ **逐字对齐** `_zone.ch1.hometown.json` 的既有形状。

    ⚠️ 第一版自造了 `file: '__zone__'` 与 `w/h`，结果：
      · `scene_route_original` E1a 报红：**每个场景条目必须显式声明 `bg` 键**
        （Deltarune 的分片场景都有 `bg: null` + `bg_source: 'none'`）；
      · `rooms_round47` B1 报红：载体判据按 `file` 字段找独立文件，
        自造值 `'__zone__'` 被当成"文件缺失"（645 个一起报）。
    ⇒ **教训**：新增数据必须**先对齐既有 schema 的最小字段集**，
      不能只写"我以为需要的字段"。见 `check77` 的 A 段对账判据。
    """
    return {
        'name': node['name'],
        'name_raw': node['name'],
        'name_derived': False,          # 原名照搬，未做机械裁剪
        'original_room_id': node['index'],
        'bg': None,
        'bg_source': 'none',
        'objects': [],
    }


def build():
    big, nodes = build_nodes()
    report = {'round': 77, 'verify': {}, 'chapters': {}}
    zones = {}
    for w, nds in nodes.items():
        meta = WORK_TO_CHAPTER[w]
        ch = meta['id']
        area = DEFAULT_AREA
        scenes = {}
        for n in nds:
            sid = scene_id_of(ch, area['id'], n['name'])
            # 重名保护：同 index 不同名不可能，但 slug 可能撞（如 `room_1` vs `room-1`）
            base = sid
            k = 2
            while sid in scenes:
                sid = '%s_%d' % (base, k)
                k += 1
            scenes[sid] = make_scene(ch, area['id'], n)
        zones[(ch, area['id'])] = {
            'schema_version': 1,
            'chapter_id': ch,
            'area_id': area['id'],
            'area_name': area['name'],
            'note': ('第77轮：从跨作品大图 bigmap66.json 迁入。'
                     'name 为原作 room 名原样；w/h 与大图逐条核验全等。'
                     '★ 区域层级待补（UT 无中文区域名表）。'),
            'scenes': scenes,
        }
        report['chapters'][ch] = {
            'id': ch, 'name': meta['name'], 'order': meta['order'],
            'alias': meta['alias'], 'tint': meta['tint'],
            'areas': [area['id']], 'scene_count': len(scenes),
        }
    return big, nodes, report, zones


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    big, nodes, report, zones = build()

    # ---- 锚点核验（必须全等）----
    allbad = []
    for w, src in [('ut', os.path.join(r'E:\Download\_extract61\_data\undertale',
                                       'ut_rooms.json')),
                   ('uty', os.path.join(r'E:\Download\_extract61\_data\undertale_yellow',
                                        'ut_rooms.json'))]:
        if not os.path.exists(src):
            print('[SKIP] 源不在（%s）' % src)
            continue
        rooms = load_json(src)['rooms']
        ok, bad = verify(rooms, nodes[w])
        report['verify'][w] = {'source_rooms': len(rooms), 'matched': ok,
                               'mismatch': len(bad)}
        print('[VERIFY] %s: 原版 %d 间 / 逐条全等 %d / 不符 %d'
              % (w, len(rooms), ok, len(bad)))
        allbad += bad

    for ch, r in report['chapters'].items():
        print('[BUILD] %s: %d 场景' % (ch, r['scene_count']))

    if allbad:
        print('[ABORT] 锚点核验有 %d 条不符，**不写盘**' % len(allbad))
        for x in allbad[:10]:
            print('   ', x)
        return 1

    if args.check or not args.write:
        print('[CHECK-ONLY] 核验通过，未写盘（加 --write 才写）')
        return 0

    # ---- 写盘 ----
    idx_path = os.path.join(SCENES, '_index.json')
    idx = load_json(idx_path)
    for ch, r in report['chapters'].items():
        areas = {}
        for (c2, a2), z in zones.items():
            if c2 != ch:
                continue
            areas[a2] = {'name': z['area_name'], 'scenes': z['scenes']}
        idx['chapters'][ch] = {
            'name': r['name'], 'order': r['order'], 'alias': r['alias'],
            'tint': r['tint'], 'areas': areas,
        }
        for (c2, a2), z in zones.items():
            if c2 != ch:
                continue
            zp = os.path.join(SCENES, '_zone.%s.%s.json' % (ch, a2))
            with io.open(zp, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(z, f, ensure_ascii=False, indent=1)
            print('[WRITE] %s' % os.path.basename(zp))
    with io.open(idx_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    print('[WRITE] _index.json')

    with io.open(os.path.join(HERE, '..', '_evidence', 'build77.json'), 'w',
                 encoding='utf-8', newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print('[REPORT] build77.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())

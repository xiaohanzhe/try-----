# -*- coding: utf-8 -*-
u"""第80轮：把 OneShot 263 个房间**接入产品场景索引**（Q1「要」）。

口径
----
用户裁决（逐字，第79轮收尾）：「**要**」= Q1 接 OneShot 263。

本脚本做**一件事**：把 `extract_oneshot80.py` 勘查出的 263 房间**逐条**写成
产品索引能读的「章 / 区域 / 场景」三级结构 + 区域分片文件。

★★ 与第77轮（`build77.py`）**逐条同构**——因为 `_index.json` 的 schema 是同一份：
     · `_index.json` 加一个新章 `oneshot`；
     · 分片 `_zone.oneshot.rooms.json`；
     · 场景条目**字段集逐字对齐** Deltarune 的分片场景（`bg: null` + `bg_source: 'none'`
       + `objects: []`）—— 第77轮第一版自造字段撞了两个套件（`scene_route_original` E1a /
       `rooms_round47` B1），**教训已写进 build77 的注释**，这里原样继承。

★ 三条纪律
  1. **不新建世界**：`oneshot` 是**章**（与 `ut`/`uty` 平级），不是新顶层。
  2. **锚点优先**：写之前**逐条**与勘查产物比对（id + name + w + h），全等才写。
  3. **零改 main.py**：沿用既有 schema，索引是数据，加载器是通用代码。

用法：
    python build80.py --check      # 只核验锚点，不写
    python build80.py --write      # 核验通过后写盘
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))      # 仓库根
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
SRC = os.path.join(ROOT, 'code-quality-audit', '第80轮-OneShot场景迁入',
                   '_evidence', 'oneshot80.json')

#: ★ 作品 → 产品章。用**作品自己的** id（`oneshot`），与 `ut`/`uty` 同规：
#: 「同一份规则两处算」的一种坏形态就是把 OneShot 的房间塞进别人的章里。
CHAPTER = {
    'id': 'oneshot',
    'name': 'OneShot · 世界机器版',
    'order': 102,                 # ut=100 / uty=101 ⇒ 顺延
    'alias': 'OneShot',
    'tint': '#2a2036',
}

#: 区域：暂时**单区域**（`rooms`）—— 与 UT/黄魂同规。
#: ★ OneShot 的 map name **没有** `" - "` 区域前缀（实测 `map_names` 全是裸名字），
#:   硬编区域会把 263 个房间按猜测切错 ⇒ **不硬编**，如实登记区域层级待补。
DEFAULT_AREA = {'id': 'rooms', 'name': '全部房间'}


def load_json(p):
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


def scene_id_of(ch, area, name, idx):
    """`<chapter>.<area>.<scene>` —— 与产品既有命名**逐字同构**。

    ★ 与 build77 同规：直接拿原始名当 scene 段，只做 ASCII-slug 化。
      OneShot 的 map name 里有空格/大小写（`House 4 - squares`），
      slug 化后是 `House_4_-_squares` —— 保留可读性，便于人肉比对。
    ★ `idx` 参与兜底：名字全被清洗成空时（如 `???`）用 `r<idx>`。
    """
    seg = ''.join(c if (c.isalnum() or c == '_') else '_' for c in name).strip('_')
    return '%s.%s.%s' % (ch, area, seg or ('r%d' % idx))


def make_scene(node):
    """★ 字段集**逐字对齐**既有分片场景（见 build77 的血泪注释）。

    `w`/`h` **不写进场景条目** —— 它们属大图/几何层，
    产品场景条目的既有字段里没有这两个键（写了就是"自造字段"）。
    """
    return {
        'name': node['name'],
        'name_raw': node['name'],
        'name_derived': False,
        'original_room_id': node['index'],
        'bg': None,
        'bg_source': 'none',
        'objects': [],
    }


def verify(nodes, src_nodes):
    """★★ 锚点优先：逐条核验（index + name + w + h 全等才算命中）。"""
    by_idx = {n['index']: n for n in src_nodes}
    ok, bad = 0, []
    for n in nodes:
        s = by_idx.get(n['index'])
        if s is None:
            bad.append((n['index'], n['name'], '<missing>'))
            continue
        if (s['name'] == n['name'] and s['w'] == n['w'] and s['h'] == n['h']):
            ok += 1
        else:
            bad.append((n['index'], n['name'], s.get('name')))
    return ok, bad


def build():
    src = load_json(SRC)
    nodes = src['nodes']
    report = {'round': 80, 'chapter': CHAPTER['id'],
              'source_nodes': len(nodes), 'scenes': len(nodes)}

    area = DEFAULT_AREA
    scenes = {}
    for n in nodes:
        sid = scene_id_of(CHAPTER['id'], area['id'], n['name'], n['index'])
        base = sid
        k = 2
        while sid in scenes:
            sid = '%s_%d' % (base, k)
            k += 1
        scenes[sid] = make_scene(n)
    zone = {
        'schema_version': 1,
        'chapter_id': CHAPTER['id'],
        'area_id': area['id'],
        'area_name': area['name'],
        'note': ('第80轮：从 OneShot（MonoGame，明文 gamedata/）迁入。'
                 '263 个房间 = gamedata/maps/*.tmx；name 取自官方 '
                 'oneshot_map_names.json；尺寸取自 TMX <map> 头 ×tile。'
                 '★ 区域层级待补（OneShot 的 map name 无 " - " 区域前缀）。'),
        'scenes': scenes,
    }
    return src, nodes, report, zone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    src, nodes, report, zone = build()

    ok, bad = verify(nodes, src['nodes'])
    report['verify'] = {'source_nodes': len(src['nodes']), 'matched': ok,
                        'mismatch': len(bad)}
    print('[VERIFY] OneShot: 勘查 %d 间 / 逐条全等 %d / 不符 %d'
          % (len(src['nodes']), ok, len(bad)))
    print('[BUILD] %s: %d 场景' % (CHAPTER['id'], report['scenes']))

    if bad:
        print('[ABORT] 锚点核验有 %d 条不符，**不写盘**' % len(bad))
        for x in bad[:10]:
            print('   ', x)
        return 1

    # ★ 二次核验：勘查产物自身的锚点也必须全绿（不信任"上一次跑绿了"）
    if not src.get('anchors_ok'):
        print('[ABORT] 勘查产物 anchors_ok=False ⇒ 不写盘')
        return 1

    if args.check or not args.write:
        print('[CHECK-ONLY] 核验通过，未写盘（加 --write 才写）')
        return 0

    idx_path = os.path.join(SCENES, '_index.json')
    idx = load_json(idx_path)
    idx['chapters'][CHAPTER['id']] = {
        'name': CHAPTER['name'], 'order': CHAPTER['order'],
        'alias': CHAPTER['alias'], 'tint': CHAPTER['tint'],
        'areas': {zone['area_id']: {'name': zone['area_name'],
                                    'scenes': zone['scenes']}},
    }
    zp = os.path.join(SCENES, '_zone.%s.%s.json' % (CHAPTER['id'], zone['area_id']))
    with io.open(zp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(zone, f, ensure_ascii=False, indent=1)
    print('[WRITE] %s' % os.path.basename(zp))
    with io.open(idx_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    print('[WRITE] _index.json')

    with io.open(os.path.join(HERE, '..', '_evidence', 'build80.json'), 'w',
                 encoding='utf-8', newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print('[REPORT] build80.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())

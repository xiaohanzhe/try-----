# -*- coding: utf-8 -*-
u"""build_outertale99.py —— 第99轮：把抽出的 outertale 房间写进产品数据面（幂等）。

产出
----
1. `ralsei_pet/assets/scenes/_zone.outertale.<area>.json` × 7（分片载体，LF + indent=1）
2. `_index.json` 新章 `outertale`（order=103，CRLF + indent=2）
3. `_worlds.json` 的 `areas` / `rooms` / `meta.unknown_rooms` 同步（LF + indent=1）
4. `_routes.json` 追加 1 条桌面传送门（`when_door='Y'`）（CRLF + indent=2）
5. `_room_geometry.json` 登记 `gaps`（Outertale 房间尺寸**采不到**，不伪造）

★ 幂等：重复跑不会叠加 —— 已存在的章/区域/路由先移除再重建。
★ EOL 保真：各文件按**实测**的 (indent, newline) 原样回写（probe99w 已逐字节验证过）。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.normpath(os.path.join(ROUND, u'..', u'..'))
SC = os.path.join(REPO, u'ralsei_pet', u'assets', u'scenes')
TOOLS = HERE
OUT = os.path.join(ROUND, u'_evidence')

sys.path.insert(0, TOOLS)
import extract_outertale99 as EX  # noqa: E402

CHAPTER = u'outertale'
ORDER = 103
ALIAS = u'Outertale'
CNAME = u'Outertale · 太空版'
TINT = u'#1a1430'
FIRST_SCENE = u'outertale.wastelands.w_start'
DOOR = u'Y'
TABLES = EX.TABLES
GEO_WHY = (
    u'Outertale 是 Vite 打包的 Web 游戏（Android 版 `outertale.apk` 解包产物）。'
    u'房间定义对象是 `{$schema, background, preload, neighbors, layers, region}` —— '
    u'**没有房间像素尺寸**；`background` 是**层名字符串**（`"below"`）而不是背景图，'
    u'`region` 是**出生点数组**（如 `[{x:160,y:280},{x:460,y:280}]`），'
    u'两者都不能闭合出房间宽高。⇒ 按第44/80轮口径**不伪造 640×480**，如实缺着；'
    u'调用方按"未知房间"退化处理。'
)


def rd_json(name):
    with io.open(os.path.join(SC, name), 'rb') as fh:
        return json.loads(fh.read().decode('utf-8'))


def wr_json(name, data, indent, nl):
    s = json.dumps(data, ensure_ascii=False, indent=indent)
    b = s.replace(u'\n', nl).encode('utf-8')
    with io.open(os.path.join(SC, name), 'wb') as fh:
        fh.write(b)
    return len(b)


def collect_rooms():
    u"""复跑抽取；跳过键名为 `_` 的**哨兵**（`Bn.rooms` 自己 `.filter(t => t !== "_")`）。"""
    _path, _raw, t = EX.load_js()
    rows = []
    for var in TABLES:
        _at, _body, rs = EX.parse_table(t, var)
        for k, rid, reg, data in rs:
            if k == u'_':
                continue
            rows.append((var, rid, reg, EX.REGION_OF_VAR[reg][0]))
    return rows


REGION_NAME = {
    u'special': u'特殊',
    u'wastelands': u'Wastelands',
    u'starton': u'Starton',
    u'foundry': u'Foundry',
    u'aerialis': u'Aerialis',
    u'core': u'Core',
    u'citadel': u'Citadel',
}
REGION_ORDER = [u'wastelands', u'starton', u'foundry', u'aerialis', u'core',
                u'citadel', u'special']


def main():
    rows = collect_rooms()
    print(u'[抽] 房间 %d 个（已剔哨兵 `_`）' % len(rows))

    # ---- 分配 original_room_id（全局稳定序号，按六表字面顺序）----
    by_region = {}
    scenes_flat = {}
    for i, (var, rid, reg, region) in enumerate(rows):
        by_region.setdefault(region, []).append((i, rid))
        sid = u'%s.%s.%s' % (CHAPTER, region, rid)
        scenes_flat[sid] = {
            u'name': rid, u'name_raw': rid, u'name_derived': False,
            u'original_room_id': i, u'bg': None, u'bg_source': u'none',
            u'objects': [],
        }
    print(u'[抽] 分区：%s' % {k: len(v) for k, v in sorted(by_region.items())})

    # ---- 1. 分片 ----
    note = (
        u'第99轮：从 Outertale 的 Vite bundle（`E:\\Download\\_extract61\\outertale'
        u'\\www\\index-*.js`）迁入。六张房间表 `Sb/w3/I3/y3/Ub/Fb` 逐表抽取，'
        u'锚点自证见 `_tools/extract_outertale99.py`（A1~A6 全 PASS）。'
        u'★ `original_room_id` 是**本项目分配的稳定序号**（按六表字面顺序 0 起），'
        u'**不是原作房间下标** —— Outertale 房间以字符串 id 寻址，本就没有整数下标；'
        u'这是与 Deltarune/OneShot 的**已知差异**，如实登记。'
    )
    for region in REGION_ORDER:
        if region not in by_region:
            continue
        aid = region
        scenes = {sid: body for sid, body in scenes_flat.items()
                  if sid.split(u'.')[1] == region}
        z = {
            u'schema_version': 1, u'chapter_id': CHAPTER, u'area_id': aid,
            u'area_name': REGION_NAME[region], u'note': note, u'scenes': scenes,
        }
        n = wr_json(u'_zone.%s.%s.json' % (CHAPTER, aid), z, 1, u'\n')
        print(u'  [zone] _zone.%s.%s.json  %d 间  %d B' % (CHAPTER, aid, len(scenes), n))

    # ---- 2. _index.json ----
    idx = rd_json(u'_index.json')
    areas = {}
    for region in REGION_ORDER:
        if region not in by_region:
            continue
        areas[region] = {
            u'name': REGION_NAME[region],
            u'scenes': {sid: body for sid, body in scenes_flat.items()
                        if sid.split(u'.')[1] == region},
        }
    idx[u'chapters'][CHAPTER] = {
        u'name': CNAME, u'order': ORDER, u'alias': ALIAS, u'tint': TINT,
        u'areas': areas,
    }
    n = wr_json(u'_index.json', idx, 2, u'\r\n')
    print(u'  [index] chapters=%s  %d B' % (list(idx[u'chapters'])[-3:], n))

    # ---- 3. _worlds.json ----
    wl = rd_json(u'_worlds.json')
    wl[u'areas'][CHAPTER] = {r: u'unknown' for r in by_region}
    wl[u'rooms'][CHAPTER] = {str(i): u'unknown'
                             for i, (_v, _r, _g, _rg) in enumerate(rows)}
    # meta.unknown_rooms：删掉旧的 outertale 条目再重建（幂等）
    meta = wl[u'meta']
    ur = [x for x in (meta.get(u'unknown_rooms') or [])
          if x.get(u'chapter') != CHAPTER]
    for i, (_v, rid, _g, region) in enumerate(rows):
        ur.append({u'chapter': CHAPTER, u'room_id': i, u'area': region,
                   u'resource': rid,
                   u'why': u'迁入章，明暗判定表未建（如实标 unknown，'
                           u'沿用第77/80轮口径）'})
    meta[u'unknown_rooms'] = ur
    n = wr_json(u'_worlds.json', wl, 1, u'\n')
    print(u'  [worlds] areas/rooms/unknown_rooms(%d)  %d B' % (len(ur), n))

    # ---- 4. _routes.json ----
    rt = rd_json(u'_routes.json')
    routes = [x for x in rt[u'routes']
              if not (x.get(u'when_scene') == u'desktop'
                      and x.get(u'when_door') == DOOR)]
    maxord = max([int(x.get(u'_order') or 0) for x in rt[u'routes']] or [0])
    routes.append({
        u'to': FIRST_SCENE, u'priority': 200,
        u'reason': u'桌面传送门：从桌面的 %s 号门进入「%s」的第一间。' % (DOOR, ALIAS),
        u'when_scene': u'desktop', u'when_door': DOOR,
        u'_original': {
            u'chapter': u'desktop', u'door_letter': DOOR,
            u'kind': u'desktop_portal',
            u'note': u'★ 第99轮新增（沿用第89轮形态）。这一条**不是**原作门位移'
                     u'（桌面不是原作房间），是『桌面作为一个场景』的出口。'
                     u'priority=200 高于原作边的 100~110，与桌面门一一对应；'
                     u'同字母的唯一性靠 when_scene 收窄，不靠 priority。'
                     u'★ Outertale 侧的目标是 `w_start`（原作 `w3` 表第一项，'
                     u'即游戏开局房间）。',
        },
        u'_order': maxord + 1,
    })
    rt[u'routes'] = routes
    n = wr_json(u'_routes.json', rt, 2, u'\r\n')
    print(u'  [routes] 追加 %s 号门 -> %s，_order=%d，共 %d 条  %d B'
          % (DOOR, FIRST_SCENE, maxord + 1, len(routes), n))

    # ---- 5. _room_geometry.json gaps ----
    rg = rd_json(u'_room_geometry.json')
    gaps = rg.get(u'gaps') or {}
    gaps[CHAPTER] = {u'rooms': len(rows), u'why': GEO_WHY,
                     u'evidence': u'code-quality-audit/第99轮-睡觉惊醒与场景系统/'
                                   u'_evidence/outertale99_rooms.json'}
    rg[u'gaps'] = gaps
    n = wr_json(u'_room_geometry.json', rg, 2, u'\r\n')
    print(u'  [geo] gaps[%s].rooms=%d  %d B' % (CHAPTER, len(rows), n))

    # ---- 汇总 ----
    print()
    print(u'[汇总] 章 %d / 区 %d / 房间 %d / 首场景 %s'
          % (len(idx[u'chapters']), len(areas), len(scenes_flat), FIRST_SCENE))
    return 0


if __name__ == u'__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
第 39 轮 · 背景素材判据的**单一真源**（纯标准库，只读）。

为什么单独抽一个模块：`pick_asset` 的判定顺序是这一轮的**核心口径**
（"什么算真背景、什么算近似"）。如果探针、构建脚本、验证套件各抄一份，
迟早出现"三份实现三种结论"——本项目已经因为"同一判据两份实现"吃过亏。

本模块与第 37 轮 `build_bg6.py` 的 `pick_asset` / `load_rooms` / `load_assets`
**逐字同口径**（唯一差异：这里不写盘、不生成画布，只做判定）。
"""
import collections
import json
import os
import re
import struct

DR_OUT = r'E:\Download\_tmp\dr_out'
DRW = r'E:\Download\_tmp\drw'

CH_DIR = {'ch1': 'chapter1_windows', 'ch2': 'chapter2_windows', 'ch3': 'chapter3_windows',
          'ch4': 'chapter4_windows', 'ch5': 'chapter5_windows'}
CHS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']

#: 第 37 轮口径：房间自带素材宽高都要 ≥ 这个尺寸才算"能当背景"
MIN_REAL_BG = (300, 200)
MAX_FRAMES = 8

#: 真背景档次（可直接落地，零编造）
REAL_HOWS = ('room.bg_layer', 'room.asset_layer')

HOW_CN = {
    'room.bg_layer': '房间自带真背景',
    'room.asset_layer': '房间自带资源层',
    'override': '房间级指定',
    'area_table': '区域代表素材(近似)',
    'chapter_tiles': '章节兜底-平铺(近似)',
    'chapter_fallback': '章节兜底-最大图(近似)',
    'none': '未配上',
}

#: 与第 37 轮 build_bg6.py 完全一致的区域代表素材表
AREA_ASSET = {
    'ch1': {'kris_room': ('bg_myroom', False), 'unknown': ('bg_darkfield_tiles', True),
            'eye_puzzle': ('bg_darkfield_tiles', True), 'field': ('bg_darkfield_tiles', True),
            'forest': ('bg_darkforest_tiles', True), 'castle_town': ('bg_darktown', False),
            'card_castle': ('bg_cctiles', True)},
    'ch2': {'kris_room': ('bg_dw_kris_room', False), 'castle_town': ('bg_darktown', False),
            'my_castle_town': ('bg_darktown', False),
            'cyber_field': ('bg_dw_cyber_battle_tiles', True),
            'cyber_city': ('bg_dw_city_alleyway_street_tiles', True),
            'queens_mansion': ('bg_dw_mansion_acid_animated_tiles_old', True)},
    'ch3': {'dark_world': ('bg_darkfield_tiles', True),
            'tv_world': ('bg_dw_tvland_stage_tiles_old', True),
            'green_room': ('bg_dw_tvland_backstage_tiles_old', True),
            'cold_place': ('bg_dw_tvland_backstage_tiles_old', True)},
    'ch4': {'kris_room': ('bg_myroom', False), 'castle_town': ('bg_darktown', False),
            'my_castle_town': ('bg_darktown', False), 'hometown': ('bg_towntiles', True),
            'noelles_house': ('bg_noellehouse_main', False),
            'dark_sanctuary': ('bg_darkfield_tiles', True),
            'second_sanctuary': ('bg_darktiles1', True),
            'third_sanctuary': ('bg_darktiles1', True),
            'mike_zone': ('bg_darkfield_tiles', True)},
    'ch5': {'kris_room': ('bg_dw_kris_room', False),
            'castle_town': ('bg_towntiles', True), 'my_castle_town': ('bg_towntiles', True),
            'hometown': ('bg_towntiles', True), 'dark_world': ('bg_darktiles1', True),
            'garden': ('bg_towntiles', True),
            'flower_castle': ('bg_fcastle_flower_tower_lattice_tiles_split', True),
            'cliffs': ('bg_darktiles1', True)},
}


def png_dims(path):
    """只读 PNG 头 24 字节拿宽高。不是合法 PNG → None。"""
    try:
        with open(path, 'rb') as fh:
            head = fh.read(24)
    except Exception:
        return None
    if len(head) < 24 or head[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', head[16:24])


def load_rooms():
    """`{ch: {room_index: room}}`。优先用 drw 下的副本，回落 dr_out。"""
    out = {}
    for ch, d in CH_DIR.items():
        p = os.path.join(DRW, d, 'rooms_map.json')
        if not os.path.exists(p):
            p = os.path.join(DR_OUT, d, 'rooms_map.json')
        if os.path.exists(p):
            with open(p, encoding='utf-8') as fh:
                out[ch] = {r['index']: r for r in json.load(fh)['rooms']}
    return out


def load_assets(rooms):
    """`{ch: {素材名: (png路径, (w, h))}}`。

    只对"可能被用到"的名字读 PNG 头：所有 `bg_*` + 房间层里引用到的
    `bg_sprite` / `asset_sprites`。同一个名字多帧时取**像素面积最大**的那帧
    （与第 37 轮一致）——动画背景取最大帧是"看起来最完整"的那张。
    """
    inv = {}
    for ch, d in CH_DIR.items():
        spr = os.path.join(DR_OUT, d, 'Sprites')
        idx = collections.defaultdict(list)
        try:
            entries = os.listdir(spr)
        except Exception:
            entries = []
        for e in entries:
            if not e.endswith('.png'):
                continue
            m = re.match(r'^(.*)_(\d+)\.png$', e)
            if m:
                idx[m.group(1)].append(os.path.join(spr, e))
        want = set(n for n in idx if n.startswith('bg_'))
        for r in (rooms.get(ch) or {}).values():
            for ly in r.get('layers') or []:
                bs = ly.get('bg_sprite')
                if bs and bs != 'UndertaleSprite':
                    want.add(bs)
                for a in ly.get('asset_sprites') or []:
                    if a:
                        want.add(a)
        best = {}
        for nm in want:
            for p in idx.get(nm, [])[:MAX_FRAMES]:
                dm = png_dims(p)
                if dm is None:
                    continue
                if nm not in best or dm[0] * dm[1] > best[nm][2]:
                    best[nm] = (p, dm, dm[0] * dm[1])
        inv[ch] = {k: (v[0], v[1]) for k, v in best.items()}
    return inv


def classify(room, ch, area, inv):
    """判定一个房间该用哪张素材 → `(素材名|None, 是否平铺, how)`。

    判定顺序（**顺序即优先级，与第 37 轮逐字一致**）：
      1. 房间自己的 `bg_sprite` 且尺寸够 → `room.bg_layer`（**真背景**）
      2. 房间自己的 `asset_sprites` 且尺寸够 → `room.asset_layer`（**真背景**）
      3. 区域代表素材表 → `area_table`（近似）
      4. 本章最大的 `*_tiles`，平铺 → `chapter_tiles`（近似）
      5. 本章最大的 `bg_*` ≥600×400 → `chapter_fallback`（近似）
      6. 都没有 → `none`
    """
    inv_ch = inv.get(ch, {})

    def big(nm):
        if nm and nm in inv_ch:
            w, h = inv_ch[nm][1]
            return w >= MIN_REAL_BG[0] and h >= MIN_REAL_BG[1]
        return False

    for ly in (room or {}).get('layers', []):
        if big(ly.get('bg_sprite')):
            return ly['bg_sprite'], False, 'room.bg_layer'
    for ly in (room or {}).get('layers', []):
        for a in ly.get('asset_sprites') or []:
            if big(a):
                return a, False, 'room.asset_layer'
    nm, tiled = (AREA_ASSET.get(ch, {}) or {}).get(area, (None, False))
    if nm and nm in inv_ch:
        return nm, tiled, 'area_table'
    tiles = [(n, v) for n, v in inv_ch.items() if n.endswith('_tiles') or '_tiles_' in n]
    if tiles:
        n, v = max(tiles, key=lambda kv: kv[1][1][0] * kv[1][1][1])
        return n, True, 'chapter_tiles'
    cands = [(n, v) for n, v in inv_ch.items()
             if n.startswith('bg_') and v[1][0] >= 600 and v[1][1] >= 400]
    if cands:
        n, v = max(cands, key=lambda kv: kv[1][1][0] * kv[1][1][1])
        return n, False, 'chapter_fallback'
    return None, False, 'none'


def bg_filename(scene_id):
    """场景 id → `bg/` 下的文件名。与 87 个锚点的既有命名约定一致。"""
    return scene_id.replace('.', '_') + '.png'


def collect_scenes(scenes_dir):
    """按 `_index.json` 的顺序收集全部场景登记 → `[(scene_id, 章, 区, room_id, 来源)]`。

    来源 ∈ `{'anchor', 'zone'}`：有独立 `<scene_id>.json` 的是锚点，其余在区域分片里。
    """
    with open(os.path.join(scenes_dir, '_index.json'), encoding='utf-8') as fh:
        idx = json.load(fh)
    out = []
    zcache = {}
    for chk, chv in (idx.get('chapters') or {}).items():
        if chk == 'desktop':
            continue
        for areak, areav in (chv.get('areas') or {}).items():
            for sid in (areav.get('scenes') or {}):
                p = os.path.join(scenes_dir, sid + '.json')
                if os.path.isfile(p):
                    with open(p, encoding='utf-8') as fh:
                        sd = json.load(fh)
                    rid = (sd.get('_comment') or {}).get('original_room') or {}
                    rid = rid.get('room_id')
                    out.append((sid, chk, areak, rid, 'anchor'))
                else:
                    zp = os.path.join(scenes_dir, '_zone.%s.%s.json' % (chk, areak))
                    if zp not in zcache:
                        with open(zp, encoding='utf-8') as fh:
                            zcache[zp] = json.load(fh).get('scenes') or {}
                    rid = (zcache[zp].get(sid) or {}).get('original_room_id')
                    out.append((sid, chk, areak, rid, 'zone'))
    return out


def load_round37_mapping(repo):
    """第 37 轮实际产出的映射表 → `{scene_id: row}`（87 个锚点的权威 how/asset）。"""
    p = os.path.join(repo, 'code-quality-audit', '第37轮-原作素材反编译',
                     '_evidence', 'scene_bg_mapping_final.json')
    if not os.path.isfile(p):
        return {}
    with open(p, encoding='utf-8') as fh:
        m = json.load(fh)
    return {r['scene_id']: r for r in m.get('rows', [])}

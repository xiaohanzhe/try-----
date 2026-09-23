# -*- coding: utf-8 -*-
"""
第 39 轮 · 背景覆盖量化探针（只读）

目的：把第 37 轮的 `pick_asset` 口径**原封不动**套到全量 1,013 个场景上，
回答一个问题：**其中有多少能拿到"真背景"（房间自带 bg_sprite / asset_sprites ≥300×200），
有多少只能靠近似（区域代表素材 / 章节兜底）。**

严格只读：不写任何 assets/ 下的文件。
"""
import io
import json
import os
import re
import struct
import sys
import collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
DR_OUT = r'E:\Download\_tmp\dr_out'
DRW = r'E:\Download\_tmp\drw'
EV = os.path.join(REPO, 'code-quality-audit', '第39轮-全量场景背景', '_evidence')

CH_DIR = {'ch1': 'chapter1_windows', 'ch2': 'chapter2_windows', 'ch3': 'chapter3_windows',
          'ch4': 'chapter4_windows', 'ch5': 'chapter5_windows'}
CHS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']
MIN_REAL_BG = (300, 200)
MAX_FRAMES = 8

# 与 37 轮 build_bg6.py 完全一致的区域代表素材表（用于判定"近似"档）
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


def png_dims(p):
    try:
        with open(p, 'rb') as fh:
            head = fh.read(24)
    except Exception:
        return None
    if len(head) < 24 or head[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', head[16:24])


def load_rooms():
    out = {}
    for ch, d in CH_DIR.items():
        p = os.path.join(DRW, d, 'rooms_map.json')
        if not os.path.exists(p):
            p = os.path.join(DR_OUT, d, 'rooms_map.json')
        if os.path.exists(p):
            dd = json.load(open(p, encoding='utf-8'))
            out[ch] = {r['index']: r for r in dd['rooms']}
    return out


def load_assets(rooms):
    """与 37 轮同口径：只对"可能用到的名字"读 PNG 头取尺寸。"""
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
    """返回 (asset_name, tiled, how) —— 逐字复刻 37 轮 pick_asset 的判定顺序。"""
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


def collect_scenes():
    """(scene_id, chapter, area, room_id, source) —— source ∈ {anchor, zone}"""
    out = []
    idx = json.load(open(os.path.join(SCENES, '_index.json'), encoding='utf-8'))
    for chk, chv in idx['chapters'].items():
        if chk == 'desktop':
            continue
        for areak, areav in (chv.get('areas') or {}).items():
            for sid in (areav.get('scenes') or []):
                p = os.path.join(SCENES, sid + '.json')
                if os.path.exists(p):
                    sd = json.load(open(p, encoding='utf-8'))
                    rid = sd.get('_comment', {}).get('original_room', {}).get('room_id')
                    out.append((sid, chk, areak, rid, 'anchor'))
                else:
                    out.append((sid, chk, areak, None, 'zone'))  # 稍后从分片补
    # 分片补 room_id
    fixed = []
    zcache = {}
    for sid, chk, areak, rid, src in out:
        if rid is None:
            zp = os.path.join(SCENES, '_zone.%s.%s.json' % (chk, areak))
            if zp not in zcache:
                zcache[zp] = json.load(open(zp, encoding='utf-8')).get('scenes', {})
            e = zcache[zp].get(sid) or {}
            rid = e.get('original_room_id')
        fixed.append((sid, chk, areak, rid, src))
    return fixed


def main():
    t0 = __import__('time').time()
    rooms = load_rooms()
    inv = load_assets(rooms)
    scenes = collect_scenes()

    L = []
    def w(s=''):
        print(s)
        L.append(s)

    w('第 39 轮 · 背景覆盖量化  %s' % __import__('time').strftime('%Y-%m-%d %H:%M:%S'))
    w('=' * 76)
    w('房间表：%s' % {ch: len(v) for ch, v in sorted(rooms.items())})
    w('精灵表（仅"可能用到"的名字）：%s' % {ch: len(v) for ch, v in sorted(inv.items())})
    w('')

    # ---- 1. 房间级：真背景可达性 ----
    w('1) 房间级真背景可达性（判据：bg_sprite / asset_sprites 尺寸 ≥ %s）' % (MIN_REAL_BG,))
    w('   %-6s %6s %10s %10s %10s' % ('章', '房间', '有bg层', '真背景', '仅asset真'))
    room_real = {}
    for ch in CHS:
        rs = rooms.get(ch, {})
        nb = nreal = nasset = 0
        real_ids = set()
        asset_ids = set()
        for rid, r in rs.items():
            if any(ly.get('bg_sprite') for ly in (r.get('layers') or [])):
                nb += 1
            got = None
            for ly in (r.get('layers') or []):
                bs = ly.get('bg_sprite')
                if bs and bs != 'UndertaleSprite' and bs in inv.get(ch, {}):
                    ww, hh = inv[ch][bs][1]
                    if ww >= MIN_REAL_BG[0] and hh >= MIN_REAL_BG[1]:
                        got = 'bg'
                        break
            if got is None:
                for ly in (r.get('layers') or []):
                    for a in (ly.get('asset_sprites') or []):
                        if a in inv.get(ch, {}):
                            ww, hh = inv[ch][a][1]
                            if ww >= MIN_REAL_BG[0] and hh >= MIN_REAL_BG[1]:
                                got = 'asset'
                                break
                    if got:
                        break
            if got == 'bg':
                nreal += 1
                real_ids.add(rid)
            elif got == 'asset':
                nasset += 1
                asset_ids.add(rid)
        room_real[ch] = (real_ids, asset_ids)
        w('   %-6s %6d %10d %10d %10d' % (ch, len(rs), nb, nreal, nasset))
    w('')

    # ---- 2. 场景级：按 37 轮口径分类 ----
    w('2) 场景级分类（全量 %d 个场景，逐字套用 37 轮 pick_asset）' % len(scenes))
    cnt = collections.Counter()
    per_ch = collections.defaultdict(collections.Counter)
    real_list, approx_list, none_list = [], [], []
    bad_room = []
    for sid, ch, area, rid, src in scenes:
        room = (rooms.get(ch) or {}).get(rid)
        if room is None:
            bad_room.append((sid, ch, rid))
        nm, tiled, how = classify(room, ch, area, inv)
        cnt[how] += 1
        per_ch[ch][how] += 1
        rec = (sid, ch, area, rid, nm, tiled, src)
        if how in ('room.bg_layer', 'room.asset_layer'):
            real_list.append(rec)
        elif how == 'none':
            none_list.append(rec)
        else:
            approx_list.append(rec)
    w('   来源分布：')
    for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]):
        w('     %-18s %4d' % (k, v))
    w('')
    w('   逐章：')
    for ch in CHS:
        w('     %-5s %s' % (ch, dict(per_ch[ch])))
    w('')
    w('   ★ 真背景（可直接落地，零编造） = %d' % len(real_list))
    w('   ⚠️ 近似（区域代表素材/章节兜底，需用户口径） = %d' % len(approx_list))
    w('   ✗ 未配上 = %d' % len(none_list))
    if bad_room:
        w('   ❗ room_id 在房间表里找不到的场景 %d 个（样例 %s）' % (len(bad_room), bad_room[:5]))
    w('')

    # ---- 3. 87 锚点：37 轮给了什么 vs 现在能拿什么 ----
    w('3) 87 锚点复看：37 轮实际给了什么，现在是否还能升级为真背景')
    oldman_p = os.path.join(REPO, 'code-quality-audit', '第37轮-原作素材反编译',
                            '_evidence', 'scene_bg_mapping_final.json')
    old = {}
    if os.path.exists(oldman_p):
        om = json.load(open(oldman_p, encoding='utf-8'))
        for r in om.get('rows', []):
            old[r['scene_id']] = r
    upgrade = []
    for sid, ch, area, rid, nm, tiled, src in real_list:
        if src != 'anchor':
            continue
        o = old.get(sid)
        if o and o.get('how') not in ('room.bg_layer', 'room.asset_layer'):
            upgrade.append((sid, o.get('how'), o.get('asset'), nm))
    w('   37 轮 how 分布：%s' % dict(collections.Counter(o.get('how') for o in old.values())))
    w('   ★ 可用真背景替换掉近似的锚点 = %d' % len(upgrade))
    for u in upgrade[:40]:
        w('     %-46s %-14s %-28s -> %s' % u)
    w('')

    # ---- 4. 真背景清单落盘 ----
    os.makedirs(EV, exist_ok=True)
    with open(os.path.join(EV, '背景覆盖量化.txt'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')
    with open(os.path.join(EV, '真背景可达清单.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(dict(
            generated_at=__import__('time').strftime('%Y-%m-%d %H:%M:%S'),
            min_real_bg=list(MIN_REAL_BG),
            real=[dict(scene_id=s, chapter=c, area=a, room_id=r, asset=n, tiled=t, kind=k)
                  for s, c, a, r, n, t, k in real_list],
            approx=[dict(scene_id=s, chapter=c, area=a, room_id=r, asset=n, tiled=t, kind=k)
                    for s, c, a, r, n, t, k in approx_list],
            none=[dict(scene_id=s, chapter=c, area=a, room_id=r) for s, c, a, r, n, t, k in none_list],
        ), f, ensure_ascii=False, indent=2)
    w('耗时 %.1fs' % (__import__('time').time() - t0))
    w('落盘 -> _evidence/背景覆盖量化.txt / 真背景可达清单.json')


if __name__ == '__main__':
    main()

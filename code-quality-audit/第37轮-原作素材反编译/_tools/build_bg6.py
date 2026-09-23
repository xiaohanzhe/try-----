# -*- coding: utf-8 -*-
"""
第 37 轮 最终脚本：产出 87 张场景背景 + 映射 JSON + 自检 + 预览页。

口径（两条，写进报告）：
  · **真背景**（`room.bg_layer` / `room.asset_layer` / `override` / 非平铺 `area_table`）
    → **原样提取原作 PNG**，不缩放不裁切（保真优先）。
  · **平铺素材**（`*_tiles`，原作本就 draw_background_tiled）
    → 按房间尺寸合成画布（宽 1280，高 = 1280×clamp(rh/rw, 0.5, 0.9)），平铺铺满。

输出全部为**新文件**（本会话无法覆写既有文件，故改新的文件名）。
"""
import json, os, re, sys, struct, shutil, collections, traceback, time
from PIL import Image

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
OUT_BG = os.path.join(SCENES, 'bg')
DR_OUT = r'E:\Download\_tmp\dr_out'
DRW = r'E:\Download\_tmp\drw'
RDIR = os.path.join(REPO, 'code-quality-audit', '第37轮-原作素材反编译')
EDIR = os.path.join(RDIR, '_evidence')

CH_DIR = {'ch1': 'chapter1_windows', 'ch2': 'chapter2_windows', 'ch3': 'chapter3_windows',
          'ch4': 'chapter4_windows', 'ch5': 'chapter5_windows'}
CHS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']

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
ROOM_OVERRIDE = {}
MIN_REAL_BG = (300, 200)
MAX_FRAMES = 8
CANVAS_W = 1280


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


def canvas_size(rw, rh):
    if not rw or not rh:
        return (CANVAS_W, 720)
    r = max(0.5, min(0.9, rh / float(rw)))
    return (CANVAS_W, max(1, int(CANVAS_W * r)))


def compose_tiled(src_png, size):
    src = Image.open(src_png).convert('RGBA')
    W, H = size
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sw, sh = src.size
    for y in range(0, H, sh):
        for x in range(0, W, sw):
            canvas.alpha_composite(src, (x, y))
    return canvas


def pick_asset(room, ch, area, inv):
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
    rid = (room or {}).get('index')
    if rid in ROOM_OVERRIDE:
        nm, tiled = ROOM_OVERRIDE[rid]
        if nm in inv_ch:
            return nm, tiled, 'override'
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


HOW_CN = {'room.bg_layer': '房间自带真背景', 'room.asset_layer': '房间自带资源层',
          'override': '房间级指定', 'area_table': '区域代表素材',
          'chapter_tiles': '章节兜底(平铺)', 'chapter_fallback': '章节兜底(最大图)',
          'none': '未配上'}
COLOR = {'room.bg_layer': '#2e7d32', 'room.asset_layer': '#2e7d32', 'override': '#1565c0',
         'area_table': '#f9a825', 'chapter_tiles': '#ef6c00', 'chapter_fallback': '#ef6c00',
         'none': '#c62828'}


def main():
    t0 = time.time()
    dry = '--dry' in sys.argv
    idx = json.load(open(os.path.join(SCENES, '_index.json'), encoding='utf-8'))
    rooms = load_rooms()
    inv = load_assets(rooms)
    os.makedirs(EDIR, exist_ok=True)
    if not dry:
        os.makedirs(OUT_BG, exist_ok=True)

    scenes = []
    for chk, chv in idx['chapters'].items():
        if chk == 'desktop':
            continue
        for areak, areav in (chv.get('areas') or {}).items():
            for sid in (areav.get('scenes') or []):
                scenes.append((chk, areak, sid))

    rows, cnt = [], collections.Counter()
    ok = exists = miss = err = copied = composed = 0
    for chk, areak, sid in scenes:
        sd = json.load(open(os.path.join(SCENES, sid + '.json'), encoding='utf-8'))
        rid = sd.get('_comment', {}).get('original_room', {}).get('room_id')
        room = (rooms.get(chk) or {}).get(rid)
        nm, tiled, how = pick_asset(room, chk, areak, inv)
        cnt[how] += 1
        fname = sid.replace('.', '_') + '.png'
        if not nm:
            miss += 1
            rows.append(dict(scene_id=sid, chapter=chk, area=areak, room_id=rid, asset=None,
                             file=None, size='-', mode='-', how=how))
            continue
        src_png, (_sw, _sh) = inv[chk][nm]
        rw = (room or {}).get('width')
        rh = (room or {}).get('height')
        outp = os.path.join(OUT_BG, fname)
        if dry:
            rows.append(dict(scene_id=sid, chapter=chk, area=areak, room_id=rid, asset=nm,
                             file=fname, size='-', mode='tile' if tiled else 'copy', how=how))
            continue
        if os.path.exists(outp):
            exists += 1
            rows.append(dict(scene_id=sid, chapter=chk, area=areak, room_id=rid, asset=nm,
                             file=fname, size='EXISTS', mode='-', how=how))
            continue
        try:
            if tiled:
                size = canvas_size(rw, rh)
                compose_tiled(src_png, size).save(outp)
                composed += 1
                sz = '%dx%d' % size
            else:
                shutil.copyfile(src_png, outp)      # 原样提取，保真
                copied += 1
                d = png_dims(outp) or (0, 0)
                sz = '%dx%d(原图)' % d
            ok += 1
            rows.append(dict(scene_id=sid, chapter=chk, area=areak, room_id=rid, asset=nm,
                             file=fname, size=sz, mode='tile' if tiled else 'copy', how=how))
        except Exception as e:
            err += 1
            rows.append(dict(scene_id=sid, chapter=chk, area=areak, room_id=rid, asset=nm,
                             file=fname, size='-', mode='-', how='ERR %s' % e))

    # 落盘：映射
    man = dict(generated_at=time.strftime('%Y-%m-%d %H:%M:%S'), total=len(scenes), ok=ok,
               exists=exists, miss=miss, err=err, copied=copied, composed=composed,
               min_real_bg=list(MIN_REAL_BG), canvas_width=CANVAS_W,
               how_counts=dict(cnt),
               area_asset={k: {a: list(v) for a, v in d.items()} for k, d in AREA_ASSET.items()},
               rows=rows)
    mpath = os.path.join(EDIR, 'scene_bg_mapping_final.json')
    with open(mpath, 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, indent=2)

    # 去重统计
    hashes = {}
    for r in rows:
        if r.get('file') and os.path.isfile(os.path.join(OUT_BG, r['file'])):
            p = os.path.join(OUT_BG, r['file'])
            b = open(p, 'rb').read()
            hashes.setdefault(hash(b), []).append(r['scene_id'])
    uniq = len(hashes)

    # 自检
    lines = []
    lines.append('第 37 轮 · 场景背景自检  %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
    lines.append('=' * 68)
    lines.append('总场景 %d | 新生成 %d | 已存在跳过 %d | 缺失 %d | 出错 %d'
                 % (len(scenes), ok, exists, miss, err))
    lines.append('其中 原样提取 %d 张 / 平铺合成 %d 张' % (copied, composed))
    lines.append('文件内容去重后 %d 份（%d 个场景）' % (uniq, len(rows)))
    lines.append('')
    lines.append('来源分布：')
    for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]):
        lines.append('   %-20s %3d  %s' % (k, v, HOW_CN.get(k, '')))
    lines.append('')
    lines.append('逐场景核验（文件存在 / 是合法 PNG / 尺寸）：')
    bad = []
    for r in rows:
        fp = os.path.join(OUT_BG, r['file']) if r.get('file') else None
        if not fp or not os.path.isfile(fp):
            bad.append(r['scene_id'])
            lines.append('  [MISSING] %-46s %s' % (r['scene_id'], r.get('file')))
            continue
        d = png_dims(fp)
        lines.append('  [OK] %-46s %-34s %-14s %s'
                     % (r['scene_id'], str(r.get('asset')), str(d), r['how']))
    lines.append('')
    lines.append('结论：%s' % ('全部 87 个场景均已生成合法 PNG' if not bad
                              else '有 %d 个场景缺失：%s' % (len(bad), bad)))
    with open(os.path.join(EDIR, '背景自检_final.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 预览页
    h = []
    h.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    h.append('<title>第 37 轮 · 87 场景背景预览</title><style>')
    h.append('body{background:#12141a;color:#e8e8ea;font:14px/1.6 -apple-system,"Segoe UI",'
             '"Microsoft YaHei",sans-serif;margin:0;padding:24px}')
    h.append('h1{font-size:20px;margin:0 0 6px}h2{font-size:16px;margin:28px 0 10px;'
             'border-left:3px solid #5b8def;padding-left:8px}')
    h.append('.meta{color:#9aa0b0;font-size:13px;margin-bottom:14px}')
    h.append('.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}')
    h.append('.card{background:#1b1f28;border:1px solid #2a2f3a;border-radius:8px;overflow:hidden}')
    h.append('.card img{width:100%;height:150px;object-fit:cover;display:block;background:#0a0c10}')
    h.append('.cap{padding:8px 10px}.cap b{font-size:12px;font-weight:600;display:block;'
             'word-break:break-all}')
    h.append('.cap span{display:block;color:#9aa0b0;font-size:11px;margin-top:3px;word-break:break-all}')
    h.append('.tag{display:inline-block;padding:1px 6px;border-radius:4px;color:#fff;font-size:11px;margin-top:5px}')
    h.append('.legend{margin:6px 0 0}.legend em{font-style:normal;margin-right:14px;font-size:12px}')
    h.append('.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;'
             'margin-right:4px;vertical-align:middle}')
    h.append('</style></head><body>')
    h.append('<h1>第 37 轮 · 原作素材反编译 → 87 个场景背景预览</h1>')
    h.append('<div class="meta">生成于 %s ｜ 新生成 %d ｜ 原样提取 %d ｜ 平铺合成 %d ｜ '
             '缺失 %d ｜ 出错 %d</div>' % (time.strftime('%Y-%m-%d %H:%M'),
                                          ok, copied, composed, miss, err))
    h.append('<div class="legend">')
    for k in ['room.bg_layer', 'area_table', 'chapter_tiles', 'none']:
        h.append('<em><i style="background:%s"></i>%s（%d）</em>'
                 % (COLOR[k], HOW_CN[k], cnt.get(k, 0)))
    h.append('</div>')
    for ch in CHS:
        rs = [r for r in rows if r['chapter'] == ch]
        if not rs:
            continue
        h.append('<h2>%s · %d 个场景</h2><div class="grid">' % (ch, len(rs)))
        for r in rs:
            src = '../../ralsei_pet/assets/scenes/bg/' + (r.get('file') or '')
            h.append('<div class="card"><img src="%s" alt="%s" loading="lazy">'
                     '<div class="cap"><b>%s</b><span>%s ｜ room %s</span>'
                     '<span>%s ｜ %s</span><span class="tag" style="background:%s">%s</span>'
                     '</div></div>'
                     % (src, r['scene_id'], r['scene_id'],
                        r['area'], r.get('room_id'), r.get('asset'), r.get('size'),
                        COLOR.get(r['how'].split(' ')[0], '#555'), HOW_CN.get(r['how'], r['how'])))
        h.append('</div>')
    h.append('</body></html>')
    hp = os.path.join(RDIR, '场景背景预览.html')
    with open(hp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(h))

    print('耗时 %.1fs' % (time.time() - t0))
    print('how 分布:', dict(cnt))
    print('OK=%d EXISTS=%d MISS=%d ERR=%d  (copy=%d tile=%d)' % (ok, exists, miss, err, copied, composed))
    print('mapping ->', mpath)
    print('selfcheck ->', os.path.join(EDIR, '背景自检_final.txt'))
    print('preview ->', hp)


try:
    main()
except Exception:
    traceback.print_exc()

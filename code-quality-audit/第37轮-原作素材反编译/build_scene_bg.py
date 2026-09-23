# -*- coding: utf-8 -*-
"""
第37轮：把五章反编译出来的原作素材，组装成 87 个场景的背景图。

素材来源（按优先级）：
  1. 房间自带背景层精灵（>=300x200 视为"真背景"）      —— 最忠实
  2. 房间资源层里 bg_ 前缀且够大的
  3. 房间级覆盖表 ROOM_OVERRIDE                        —— 手工纠正
  4. 区域策划表 AREA_ASSET                             —— 区域级代表素材
  5. 该章任意大背景兜底

平铺类素材（瓷砖条）会被重复平铺铺满画布 —— 与原作 draw_background_tiled 的做法一致。

输入：E:\\Download\\_tmp\\dr_out\\<chapter>\\Sprites\\*.png（UTMT CLI dump 产出）
      E:\\Download\\_tmp\\drw\\<chapter>\\rooms_map.json（自写 csx 产出）
输出：ralsei_pet\\assets\\scenes\\bg\\<scene_id 点转下划线>.png
      code-quality-audit/第37轮-原作素材反编译/_evidence/scene_bg_mapping.json
"""
import json, os, re, struct
from PIL import Image

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
OUT_BG = os.path.join(SCENES, 'bg')
DR_OUT = r'E:\Download\_tmp\dr_out'
DRW = r'E:\Download\_tmp\drw'
REPORT_DIR = os.path.join(REPO, 'code-quality-audit', '第37轮-原作素材反编译', '_evidence')

CHS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']
CH_DIR = {'ch1': 'chapter1_windows', 'ch2': 'chapter2_windows',
          'ch3': 'chapter3_windows', 'ch4': 'chapter4_windows',
          'ch5': 'chapter5_windows'}

AREA_ASSET = {
    'ch1': {
        'kris_room':     ('bg_myroom', False),
        'unknown':       ('bg_darkfield_tiles', True),
        'eye_puzzle':    ('bg_darkfield_tiles', True),
        'castle_town':   ('bg_darktown', False),
        'field':         ('bg_darkfield_tiles', True),
        'forest':        ('bg_treetiles', True),
        'card_castle':   ('bg_cctiles', True),
    },
}

ROOM_OVERRIDE = {}
MIN_REAL_BG = (300, 200)


def png_dims(p):
    with open(p, 'rb') as f:
        head = f.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', head[16:24])


def load_assets():
    """{ch: {sprite_name: (png_path, (w,h))}}"""
    inv = {}
    for ch, d in CH_DIR.items():
        spr = os.path.join(DR_OUT, d, 'Sprites')
        m = {}
        if os.path.isdir(spr):
            for f in os.listdir(spr):
                mt = re.match(r'^(.*)_(\d+)\.png$', f)
                if not mt:
                    continue
                nm = mt.group(1)
                p = os.path.join(spr, f)
                dm = png_dims(p)
                if dm is None:
                    continue
                if nm not in m or dm[0] * dm[1] > m[nm][2]:
                    m[nm] = (p, dm, dm[0] * dm[1])
        inv[ch] = {k: (v[0], v[1]) for k, v in m.items()}
    return inv


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


def target_size(rw, rh, cap=1280):
    """按房间原始比例定输出尺寸；长边 <= cap，宽度不足 640 时整数倍放大（像素风）"""
    if not rw or not rh:
        return (640, 480)
    s = 1.0
    if max(rw, rh) > cap:
        s = cap / float(max(rw, rh))
    w, h = max(1, int(rw * s)), max(1, int(rh * s))
    if w < 640:
        k = min(4, max(1, 640 // w))
        w, h = w * k, h * k
    return (w, h)


def build_image(src_png, size, tiled):
    src = Image.open(src_png).convert('RGBA')
    W, H = size
    if tiled:
        canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        sw, sh = src.size
        for y in range(0, H, sh):
            for x in range(0, W, sw):
                canvas.alpha_composite(src, (x, y))
        return canvas
    sw, sh = src.size
    k = max(W / float(sw), H / float(sh))
    nw, nh = max(1, int(round(sw * k))), max(1, int(round(sh * k)))
    big = src.resize((nw, nh), Image.NEAREST if k >= 1 else Image.LANCZOS)
    left, top = (nw - W) // 2, (nh - H) // 2
    return big.crop((left, top, left + W, top + H))


def pick_asset(room, ch, area, inv):
    inv_ch = inv.get(ch, {})
    for ly in (room or {}).get('layers', []):
        bs = ly.get('bg_sprite')
        if bs and bs in inv_ch:
            w, h = inv_ch[bs][1]
            if w >= MIN_REAL_BG[0] and h >= MIN_REAL_BG[1]:
                return bs, False, 'room.bg_layer'
        for a in ly.get('asset_sprites', []):
            if a.startswith('bg_') and a in inv_ch:
                w, h = inv_ch[a][1]
                if w >= MIN_REAL_BG[0] and h >= MIN_REAL_BG[1]:
                    return a, False, 'room.asset_layer'
    rid = (room or {}).get('index')
    if rid in ROOM_OVERRIDE:
        return ROOM_OVERRIDE[rid], True, 'override'
    tbl = AREA_ASSET.get(ch, {})
    if area in tbl:
        nm, tiled = tbl[area]
        if nm in inv_ch:
            return nm, tiled, 'area_table'
    best = None
    for nm, (p_, (w, h)) in inv_ch.items():
        if not nm.startswith('bg_'):
            continue
        if w >= 600 and h >= 400:
            if best is None or w * h > best[2]:
                best = (nm, (w, h), w * h)
    if best:
        return best[0], False, 'chapter_fallback'
    return None, False, 'none'


def main():
    idx = json.load(open(os.path.join(SCENES, '_index.json'), encoding='utf-8'))
    inv = load_assets()
    rooms = load_rooms()

    print('=== 素材清单 ===')
    for ch in CHS:
        n = len([k for k in inv.get(ch, {}) if k.startswith('bg_')])
        print('  %s: 精灵 %d 个，其中 bg_* %d 个，房间 %d 个'
              % (ch, len(inv.get(ch, {})), n, len(rooms.get(ch, {}))))
    print()

    os.makedirs(OUT_BG, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)

    scenes = []
    for chk, chv in idx['chapters'].items():
        if chk == 'desktop':
            continue
        for areak, areav in (chv.get('areas') or {}).items():
            for sid in (areav.get('scenes') or []):
                scenes.append((chk, areak, sid))

    print('待处理场景 =', len(scenes))
    print()

    rows = []
    ok = miss = 0
    for chk, areak, sid in scenes:
        sd = json.load(open(os.path.join(SCENES, sid + '.json'), encoding='utf-8'))
        cm = sd.get('_comment', {}).get('original_room', {})
        rid = cm.get('room_id')
        room = (rooms.get(chk) or {}).get(rid)
        nm, tiled, how = pick_asset(room, chk, areak, inv)
        if not nm:
            miss += 1
            rows.append((sid, chk, areak, rid, None, '-', 'MISS'))
            continue
        src_png, (sw, sh) = inv[chk][nm]
        rw = (room or {}).get('width') or sw
        rh = (room or {}).get('height') or sh
        size = target_size(rw, rh)
        try:
            img = build_image(src_png, size, tiled)
        except Exception as e:
            rows.append((sid, chk, areak, rid, nm, 'ERR %s' % e, 'FAIL'))
            miss += 1
            continue
        img.save(os.path.join(OUT_BG, sid.replace('.', '_') + '.png'))
        ok += 1
        rows.append((sid, chk, areak, rid, nm,
                     '%dx%d%s' % (size[0], size[1], ' TILE' if tiled else ''), how))

    print('=== 映射结果 ===')
    for r in rows:
        print('%-46s %-4s %-13s %-5s %-26s %-12s %s' %
              (r[0][:46], r[1], str(r[2])[:13], r[3], str(r[4])[:26], r[5], r[6]))
    print()
    print('OK=%d MISS=%d' % (ok, miss))

    man = {'total': len(scenes), 'ok': ok, 'miss': miss,
           'min_real_bg': list(MIN_REAL_BG),
           'rows': [dict(scene_id=r[0], chapter=r[1], area=r[2], room_id=r[3],
                         asset=r[4], out=r[5], how=r[6]) for r in rows]}
    with open(os.path.join(REPORT_DIR, 'scene_bg_mapping.json'), 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    print('mapping ->', os.path.join(REPORT_DIR, 'scene_bg_mapping.json'))


if __name__ == '__main__':
    main()

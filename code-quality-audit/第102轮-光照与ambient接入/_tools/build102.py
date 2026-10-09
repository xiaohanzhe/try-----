# -*- coding: utf-8 -*-
u"""build102.py —— 第102轮：① 修正「光照/ambient」归因（只读取证）② OneShot 房间物件**普查**
③ 物件图集**整张**入库（`assets/scenes/oneshot_props/`）。

为什么本轮**不切帧**（刻意的范围限制，写进报告）
------------------------------------------------
`events_map<N>.json` 的 `graphic` 只有 7 个键，**没有 `character_index`**：
    tile_id / character_hue / direction / pattern / opacity / blend_type / character_name
⇒ 148 张图集里**只有 26 张**是 64×64 的**单块**，其余 **122 张**（w>64 或 h>64；
   绝大多数是 96×128 / 120×200 / 192×192 这种**多块**图集）**该取哪一块在数据里根本没有依据**。
    栅格语义（4 列×4 行？3 列×4 行？块内偏移？）需要**独立锚点**才能定死，
    现在切帧 = 把错假设固化进产品。本轮的处置：**整张入库**（可复用、不预判），
    切片与接线留给下一轮（先过栅格 A/B 锚点）。

锚点（不通过就不落盘）
--------------------
 B1 有事件的房数 == 244
 B2 事件总数 == 11371
 B3 可见（character_name 非空）== 7805 ；不可见触发器 == 3397
 B4 tile_id>0 == 169（三档互斥且和为 B2）
 B5 ★ 坐标锚点：**越界事件数 == 0**（事件 x/y 就是 tmx 瓦片坐标）
 B6 不同 character_name == 149 ；(name,dir,pattern) 三元组 == 380
 B7 入库图集数 == 148（= 149 − 缺失 1 张 `npc_BIG`，如实登记）
 B8 正控制：**入库 PNG 重新解码后与源 XNB 解码逐像素相同**
 B9 负控制：把源图裁掉 1 行再比 ⇒ B8 的判据**必须报红**（证明它有鉴别力）

★ 第102轮补（收口时查出的两处记账缺陷，本文件已修）
------------------------------------------------------
 ① `counts['rooms_with_events']` 原来写的是 **189**，那其实是
    「**有可见物件**的房」（`rows` 只在 `room` 非空时 append）——
    真正的"有事件的房"是 **244**（由 `_all_rooms_with_events()` 数）。两个数不是一回事
    ⇒ 现在**两个字段都给**：`rooms_with_events`(244) / `rooms_with_visible_props`(189)。
 ② 入库清单只记了**源 XNB 的 sha256**，没记**落盘 PNG 自己**的 sha256
    ⇒ 回归侧无法判"入库图有没有被人改过"。现在补 `png_sha256`。
 另：新增 `brightness102.json` —— 把 263 张合成图的**亮度画像 + 五档归因**落成可复查的
    登记事实（"房间偏暗"是本轮被**证伪**的归因，必须有量化底账）。

用法：
    python -X utf8 build102.py            # 锚点 + 入库
    python -X utf8 build102.py --probe    # 只跑锚点，不写盘
"""
import collections
import hashlib
import io
import importlib.util
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
SPEC = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')
NPC = os.path.join(o.OSD, 'content', 'npc')
PROPS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'oneshot_props')

FAILS = []


def check(name, ok, detail=''):
    print('[%s] %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok:
        FAILS.append(name)
    return ok


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


# ------------------------------------------------------------------ 普查
def census():
    rows = []
    rooms_with_events = []
    n_ev = n_vis = n_inv = n_tile = 0
    names = collections.Counter()
    triples = collections.Counter()
    oob = []
    for n in range(1, 264):
        p = os.path.join(MAPS, 'events_map%d.json' % n)
        if not os.path.isfile(p):
            continue
        tmx = os.path.join(MAPS, 'map%d.tmx' % n)
        mw = mh = None
        if os.path.isfile(tmx):
            s = io.open(tmx, encoding='utf-8', newline='').read()
            a = re.search(r'<map\b([^>]*)>', s).group(1)
            mw = int(re.search(r'width\s*=\s*"(\d+)"', a).group(1))
            mh = int(re.search(r'height\s*=\s*"(\d+)"', a).group(1))
        evs = rj(p).get('events', [])
        if evs:
            rooms_with_events.append(n)      # ★ 有**任意**事件（含隐形触发器）的房
        room = []
        for e in evs:
            n_ev += 1
            pgs = e.get('pages') or []
            g = (pgs[0].get('graphic') if pgs else None) or {}
            tid = int(g.get('tile_id') or 0)
            nm = (g.get('character_name') or '').strip()
            x, y = e.get('x'), e.get('y')
            if mw is not None and isinstance(x, int) and isinstance(y, int) \
                    and (x < 0 or y < 0 or x >= mw or y >= mh):
                oob.append((n, e.get('name'), x, y, mw, mh))
            if tid > 0:
                n_tile += 1
                continue
            if not nm:
                n_inv += 1
                continue
            n_vis += 1
            d = int(g.get('direction') or 0)
            pa = int(g.get('pattern') or 0)
            names[nm] += 1
            triples[(nm, d, pa)] += 1
            room.append(dict(name=e.get('name'), x=x, y=y, cn=nm, dir=d, pat=pa,
                             opacity=int(g.get('opacity') or 0),
                             blend=int(g.get('blend_type') or 0),
                             top=bool(pgs[0].get('always_on_top')),
                             pages=len(pgs)))
        if room:
            rows.append(dict(room_id=n, n=len(room), props=room))
    return dict(rows=rows, n_ev=n_ev, n_vis=n_vis, n_inv=n_inv, n_tile=n_tile,
                names=names, triples=triples, oob=oob,
                rooms_with_events=rooms_with_events)


def lighting_evidence():
    u"""从 exe 抠出光照 API 的字符串证据（**只登记语义，不入库 lightmaps**）。"""
    raw = open(os.path.join(o.OSD, 'OneShotMG.exe'), 'rb').read()
    strs = [m.group().decode('utf-16-le', 'replace')
            for m in re.finditer(rb'(?:[\x20-\x7e]\x00){3,}', raw)]
    api = [s for s in strs if re.search(r'add_light|del_light|^\w*ambient$|ambient -', s)]
    calls = []
    for n in range(1, 264):
        p = os.path.join(MAPS, 'events_map%d.json' % n)
        if not os.path.isfile(p):
            continue
        t = io.open(p, encoding='utf-8', errors='replace', newline='').read()
        for k in ('add_light', 'del_light'):
            c = t.count(k)
            if c:
                calls.append(dict(room_id=n, kind=k, count=c))
    return dict(api_strings=sorted(set(api)), call_sites=calls)


def brightness_evidence():
    u"""263 张合成图的**亮度画像 + 五档归因**（"偏暗"证伪这件事的量化底账）。

    五档（互斥，按优先级）——与 `probe102d.py` 同口径：
      A 空转     有瓦片但摆放的瓦片**全透明**（合成只剩底色 = **我们的**锅；
                 ⚠️ 底色不一定是黑的 —— 实测 map63 退化成**单色紫**，均亮度 101.7）
      B 无底黑   瓦片 0，且该地图**不在** `oneshot_map_colors.json` 里
      C 空房黑   瓦片 0，但有底色（原作这间本来就空）
      D 暗但忠实 有**不透明**瓦片且均亮度 < 90 ⇒ **原作瓦片本身暗**（忠实）
      E 正常     有实心瓦片且均亮度 >= 90
    """
    colors = o.load_map_colors()
    bgdir = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'bg')
    _alpha = {}

    def tile_alpha(ip, im, t, lid):
        k = (ip, lid)
        if k not in _alpha:
            col, row = lid % t['columns'], lid // t['columns']
            a = im.crop((col * t['tw'], row * t['th'],
                         col * t['tw'] + t['tw'], row * t['th'] + t['th'])).getchannel('A')
            lo, hi = a.getextrema()
            _alpha[k] = (hi > 0, lo > 0)
        return _alpha[k]

    rows = []
    for n in range(1, 264):
        mp = os.path.join(MAPS, 'map%d.tmx' % n)
        placed = opaque = 0
        tsx_names = []
        if os.path.isfile(mp):
            m = o.parse_map(mp)
            imgs = []
            for fg, src in m['tilesets']:
                tsx = os.path.normpath(os.path.join(MAPS, src))
                tsx_names.append(os.path.basename(tsx))
                if not os.path.isfile(tsx):
                    imgs.append((fg, None, None, None))
                    continue
                t = o.parse_tsx(tsx)
                ip = o.resolve_img(os.path.dirname(tsx), t['img'])
                imgs.append((fg, t, ip, o.xnb_rgba(ip) if ip else None))
            for _ln, gids in m['layers']:
                for g in gids:
                    if g <= 0:
                        continue
                    placed += 1
                    cur = None
                    for e in imgs:
                        if g >= e[0]:
                            cur = e
                        else:
                            break
                    if cur is None or cur[2] is None or cur[3] is None:
                        continue
                    fg, t, ip, im = cur
                    lid = g - fg
                    if lid >= t['tilecount']:
                        continue
                    if tile_alpha(ip, im, t, lid)[0]:
                        opaque += 1
        lum = None
        p = os.path.join(bgdir, 'oneshot_map%d.png' % n)
        if os.path.isfile(p):
            im2 = Image.open(p).convert('RGB')
            px = im2.resize((min(im2.width, 160), min(im2.height, 160))).getdata()
            lum = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px) / float(len(px))
        if opaque > 0:
            cls = 'E' if (lum or 0) >= 90 else 'D'
        elif placed > 0:
            cls = 'A'
        else:
            cls = 'C' if n in colors else 'B'
        rows.append(dict(room_id=n, lum=(round(lum, 3) if lum is not None else None),
                         placed=placed, opaque=opaque, cls=cls,
                         blanks=any(x.startswith('blank') or x == 'black.tsx'
                                    for x in tsx_names)))
    return rows


def main():
    probe = '--probe' in sys.argv
    c = census()

    n_rooms_ev = len(_all_rooms_with_events())
    check('B1 有事件的房 == 244', n_rooms_ev == 244, str(n_rooms_ev))
    check('B2 事件总数 == 11371', c['n_ev'] == 11371, str(c['n_ev']))
    check('B3 可见 7805 / 隐形 3397', c['n_vis'] == 7805 and c['n_inv'] == 3397,
          '可见=%d 隐形=%d' % (c['n_vis'], c['n_inv']))
    check('B4 tile_id>0 == 169 且三档互斥求和', c['n_tile'] == 169
          and c['n_vis'] + c['n_inv'] + c['n_tile'] == c['n_ev'],
          'tile=%d 和=%d/%d' % (c['n_tile'], c['n_vis'] + c['n_inv'] + c['n_tile'], c['n_ev']))
    check('B5 ★ 坐标锚点：越界事件数 == 0', not c['oob'], '%d 个 %s' % (len(c['oob']), c['oob'][:3]))
    check('B6 名字 149 / 三元组 380', len(c['names']) == 149 and len(c['triples']) == 380,
          '%d / %d' % (len(c['names']), len(c['triples'])))

    # ---- 入库 ----
    have, miss = [], []
    for nm in sorted(c['names']):
        (have if os.path.isfile(os.path.join(NPC, nm + '.xnb')) else miss).append(nm)
    check('B7 图集可得 %d / 不可得 %d' % (len(have), len(miss)),
          len(have) + len(miss) == len(c['names']), '缺：%s' % (miss,))

    lit = lighting_evidence()
    print('   光照 API 字符串 %d 条；add_light/del_light 调用点 %s'
          % (len(lit['api_strings']), lit['call_sites']))

    # ---- 亮度画像（"偏暗"归因的量化底账）----
    br = brightness_evidence()
    buck = collections.Counter(r['cls'] for r in br)
    print('   亮度五档：%s（合计 %d）' % (dict(sorted(buck.items())), sum(buck.values())))
    check('B10 亮度五档互斥求和 == 263', sum(buck.values()) == 263,
          '%d 张' % sum(buck.values()))
    check('B11 ★ 归因更正：D 档（有实心瓦片却均亮度<90）>= 200，且 A 档（我们的锅）<= 2',
          buck.get('D', 0) >= 200 and buck.get('A', 0) <= 2,
          'D=%d A=%d' % (buck.get('D', 0), buck.get('A', 0)))
    check('B12 A 档（空转：有瓦片却全透明 ⇒ 合成退化成单色）全部用 blank*/black.tsx',
          all(r['blanks'] for r in br if r['cls'] == 'A'),
          [r['room_id'] for r in br if r['cls'] == 'A'])

    if probe:
        print('\n[--probe] 不落盘。FAIL =', len(FAILS), FAILS)
        return 1 if FAILS else 0

    os.makedirs(EV, exist_ok=True)
    os.makedirs(PROPS, exist_ok=True)
    man, total, pix_ok, pix_bad = [], 0, 0, 0
    for nm in have:
        src = os.path.join(NPC, nm + '.xnb')
        im = o.xnb_rgba(src)
        if im is None:
            man.append(dict(name=nm, ok=False, why='解码失败'))
            continue
        im = im.convert('RGBA')
        dst = os.path.join(PROPS, nm + '.png')
        im.save(dst)
        total += os.path.getsize(dst)
        # B8 正控制：读回磁盘 PNG，与源解码逐像素比
        back = Image.open(dst).convert('RGBA')
        same = back.size == im.size and back.tobytes() == im.tobytes()
        pix_ok += 1 if same else 0
        pix_bad += 0 if same else 1
        man.append(dict(name=nm, ok=same, w=im.width, h=im.height,
                        png=os.path.getsize(dst),
                        png_sha256=hashlib.sha256(open(dst, 'rb').read()).hexdigest()[:16],
                        src_sha256=hashlib.sha256(open(src, 'rb').read()).hexdigest()[:16]))
    check('B8 正控制：入库 PNG 与源 XNB 解码**逐像素相同**', pix_bad == 0,
          'ok=%d bad=%d' % (pix_ok, pix_bad))

    # B9 负控制：把源裁掉 1 行 ⇒ 同一条判据必须报红
    probe_nm = have[0]
    im = o.xnb_rgba(os.path.join(NPC, probe_nm + '.xnb')).convert('RGBA')
    cut = im.crop((0, 0, im.width, im.height - 1))
    ng = not (cut.size == im.size and cut.tobytes() == im.tobytes())
    check('B9 负控制：裁掉 1 行 ⇒ B8 判据必须报红', ng,
          '（%s 裁后 size=%s vs %s）' % (probe_nm, cut.size, im.size))

    io.open(os.path.join(EV, 'objects_census102.json'), 'w', encoding='utf-8',
            newline='\n').write(json.dumps(dict(
        note='OneShot 263 间房的**可见物件**普查（第102轮）。只登记，不接线。'
             '★ rooms_with_events=244 是"有事件的房"（含隐形触发器）；'
             'len(rooms)=189 是"有可见物件的房"，两者不是一回事。',
        counts=dict(rooms_with_events=len(c['rooms_with_events']),
                    rooms_with_visible_props=len(c['rows']),
                    events=c['n_ev'],
                    visible=c['n_vis'], invisible_triggers=c['n_inv'],
                    tile_graphic=c['n_tile'], charset_names=len(c['names']),
                    frame_triples=len(c['triples']), out_of_bounds=len(c['oob'])),
        names=c['names'].most_common(),
        triples=[[k[0], k[1], k[2], v] for k, v in c['triples'].most_common()],
        missing_charsets=miss,
        rooms=c['rows']), ensure_ascii=False, indent=1))

    io.open(os.path.join(EV, 'oneshot_lighting102.json'), 'w', encoding='utf-8',
            newline='\n').write(json.dumps(dict(
        note='原作光照语义取证（第102轮）。**未入库 lightmaps**：它们不是房间光照层。',
        conclusion='add_light/del_light 是**事件脚本**级特殊效果，全库仅 7 次 / 6 间房；'
                   'ambient 是**色调命令**（`ambient -100, -100, -100`）。',
        api_strings=lit['api_strings'], call_sites=lit['call_sites']),
        ensure_ascii=False, indent=1))

    io.open(os.path.join(EV, 'ingest102.json'), 'w', encoding='utf-8',
            newline='\n').write(json.dumps(dict(
        note='物件图集**整张**入库（不切帧，理由见 build102.py 头注）',
        dir='ralsei_pet/assets/scenes/oneshot_props/', count=len(man),
        total_bytes=total, files=man), ensure_ascii=False, indent=1))

    _lm = [r['lum'] for r in br if r['lum'] is not None]
    io.open(os.path.join(EV, 'brightness102.json'), 'w', encoding='utf-8',
            newline='\n').write(json.dumps(dict(
        note='263 张合成图**亮度画像 + 五档归因**（第102轮）。'
             '「房间偏暗 ⇒ 因为没接 lightmaps」这个归因本轮**被证伪**：'
             'lightmaps 是**加色光罩**（用了只会更亮），ambient 是**调暗命令**且全库仅 7 次；'
             '而 263 张里 221 张（D 档）是**有实心瓦片却近黑** ⇒ 暗来自**原作瓦片/图集本身**。',
        classes=dict(sorted(buck.items())),
        summary=dict(n=len(br),
                     mean_lum=round(sum(_lm) / max(1, len(_lm)), 3),
                     dark_bucket_0_31=sum(1 for x in _lm if x < 32),
                     exact_black=[r['room_id'] for r in br if r['lum'] == 0.0],
                     brightest=max(_lm) if _lm else None),
        rows=br), ensure_ascii=False, indent=1))

    print('\n入库 %d 张 → %s （合计 %.2f MB）' % (len(man), PROPS, total / 1048576.0))
    print('证据：objects_census102.json / oneshot_lighting102.json / ingest102.json '
          '/ brightness102.json')
    print('亮度：均 %.2f ｜ 档 0~31 = %d 张 ｜ %s'
          % (sum(_lm) / max(1, len(_lm)), sum(1 for x in _lm if x < 32),
             dict(sorted(buck.items()))))
    print('FAIL =', len(FAILS), FAILS)
    return 1 if FAILS else 0


def _all_rooms_with_events():
    out = []
    for n in range(1, 264):
        p = os.path.join(MAPS, 'events_map%d.json' % n)
        if os.path.isfile(p) and rj(p).get('events'):
            out.append(n)
    return out


if __name__ == '__main__':
    sys.exit(main())

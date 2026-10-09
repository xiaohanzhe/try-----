# -*- coding: utf-8 -*-
u"""build101.py —— 第101轮：OneShot 263 间背景「合成 → 落盘 → 两层接线」。

口径（用户）：「**一切根据原作**」「把原作的世界搬到桌面上」。
所以背景**不手画**：拿原作 `gamedata/maps/map<N>.tmx` + tsx 图集 + `oneshot_map_colors.json`
逐像素合成，落进 `ralsei_pet/assets/scenes/bg/oneshot_<area>_<scene>.png`。

为什么不重抄第100轮的合成代码：**唯一真源** ⇒ `import` 它（`os_bg100.py`）。

接线（**两层登记都要改** —— 第101轮侦察实证 index 内联副本与 zone 分片逐字段全等）：
  · `_zone.oneshot.<area>.json` 的 scenes.<sid>.{bg,bg_source,bg_asset}
  · `_index.json` 的 chapters.oneshot.areas.<area>.scenes.<sid>.{同三字段}
字段值：
  bg        = "bg/oneshot_<area>_<scene>.png"
  bg_source = "tmx.composite"     ← 新增档次（既有只有 room.bg_layer/area_table/none）
  bg_asset  = "map<N>.tmx"        ← 溯源到具体原作文件

★ 写入用**文本级逐行替换**（第39轮契约）：场景 JSON 是 CRLF + 1 空格缩进 + 中文原样，
  全量重序列化会产出与"到底改了什么"无关的巨型 diff，把真改动埋掉。

用法：
    python -X utf8 build101.py --build          # 只合成落盘 + 打锚点 B1~B4
    python -X utf8 build101.py --wire --dry     # 只看接线计划
    python -X utf8 build101.py --wire           # 合成 + 接线 + 落盘后复核
"""
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
BGDIR = os.path.join(SCENES, 'bg')
TOOLS100 = os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景', '_tools')
EV = os.path.join(os.path.dirname(HERE), '_evidence')

FAILS = []
LOG = []


def w(s=''):
    print(s)
    LOG.append(s)


def check(name, ok, detail=''):
    w('[%s] %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok:
        FAILS.append(name)
    return ok


def load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


BG = load_mod(os.path.join(TOOLS100, 'os_bg100.py'), 'os_bg100')


def jload(p):
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


def read_text(p, ):
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


def write_text(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(t)


def split_keepends(t):
    return re.findall(r'[^\r\n]*(?:\r\n|\r|\n|$)', t)[:-1] or []


def sanitize(s):
    return re.sub(r'[^0-9A-Za-z_.-]+', '_', s)


# --------------------------------------------------------------- 场景表
ZONE_FILES = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.'))


def zone_scenes():
    """→ {room_id(int): dict(sid, area, zone, scene)}（6 个分片合并）。"""
    out = {}
    for z in ZONE_FILES:
        d = jload(os.path.join(SCENES, z))
        area = d['area_id']
        for sid, s in (d.get('scenes') or {}).items():
            rid = int(s['original_room_id'])
            out[rid] = {'sid': sid, 'area': area, 'zone': z, 'scene': s}
    return out


def target_name(rid):
    """★ 文件名**必须含 room_id**：OneShot 里存在**只差大小写**的 scene 名对
    （如 `ignore` / `UNUSED` 这类同族名），而 Windows 文件系统**大小写不敏感**
    ⇒ 按 scene 命名会互相覆盖（第101轮 B4 首跑实测：263 写下去只落地 259，缺 4）。
    room_id 与 map 编号严格 1:1（1..263，零差集零重复）⇒ 拿它做唯一键最稳，
    也便于与 `_evidence/os_<N>.png` 交叉验证。"""
    return 'oneshot_map%d.png' % rid


# --------------------------------------------------------------- 阶段 1：合成
def stage_build(scenes):
    colors = BG.load_map_colors()
    w('mapColors 覆盖 %d 张地图' % len(colors))
    geom = jload(os.path.join(SCENES, '_room_geometry.json'))['rooms']
    os.makedirs(BGDIR, exist_ok=True)
    # ★ 清掉本轮早期"按 scene 命名"的残留（会与 Windows 大小写不敏感互相覆盖）
    stale = [f for f in os.listdir(BGDIR)
             if f.startswith('oneshot_') and not re.fullmatch(r'oneshot_map\d+\.png', f)]
    for f in stale:
        os.remove(os.path.join(BGDIR, f))
    if stale:
        w('清理早期命名残留 %d 个' % len(stale))

    made, names = [], {}
    for rid in sorted(scenes):
        rec = scenes[rid]
        fn = target_name(rid)
        if fn in names:
            w('!! 文件名冲突 %s: %s vs %s' % (fn, names[fn], rid))
        names[fn] = rid
        mp = os.path.join(BG.MAPS, 'map%d.tmx' % rid)
        im, used, m = BG.render(mp, colors)
        im.save(os.path.join(BGDIR, fn))
        made.append({'room_id': rid, 'file': fn, 'w': im.width, 'h': im.height,
                     'used': used, 'sid': rec['sid']})

    check('B1 合成落盘 %d 张 / 期望 263' % len(made), len(made) == 263, str(len(made)))
    check('B1b 文件名唯一（无覆盖）', len(names) == len(made),
          '%d vs %d' % (len(names), len(made)))

    # ★★ B2：合成尺寸 == `_room_geometry.json` 登记的房间世界尺寸（**独立来源**交叉验）
    bad, miss = [], []
    for r in made:
        g = geom.get('oneshot:%d' % r['room_id'])
        if not g:
            miss.append(r['room_id'])
        elif (g.get('w'), g.get('h')) != (r['w'], r['h']):
            bad.append((r['room_id'], (r['w'], r['h']), (g.get('w'), g.get('h'))))
    check('B2 ★ 每张合成图尺寸 == 独立登记的 `_room_geometry.json` 房间几何（1:1）',
          not bad and not miss,
          '不符 %d 缺 %d %s' % (len(bad), len(miss), bad[:4]))

    # B3 信息量：★★★ 判据改了**两轮**才立住 —— 单色图有三种成因，只有一种是错：
    #    ① 该房一层瓦片都没铺（used==0，如 Unused/Tower/Water）⇒ 只剩底色，忠实；
    #    ② 铺了，但瓦片来自 blank*.tsx（blank.xnb 是**1 种颜色 (0,0,0,0) 全透明**占位）
    #       ⇒ 贴 2806 块透明也是底色，同样忠实（map63 实证）；
    #    ③ **有实心瓦片却画成单色** ⇒ 合成空转 = 真错（这才该报红）。
    #    首跑只判"单色"把 ①② 一起误杀。判据必须**看输入（瓦片 alpha）**——
    #    从输出侧无法区分"瓦片透明"与"合成丢块"。
    def opaque_used(mpath):
        m = BG.parse_map(mpath)
        imgs = []
        for fg, src in m['tilesets']:
            tsx = os.path.normpath(os.path.join(BG.MAPS, src))
            t = BG.parse_tsx(tsx)
            ip = BG.resolve_img(os.path.dirname(tsx), t['img'])
            imgs.append((fg, t, BG.xnb_rgba(ip) if ip else None))
        n = 0
        for _lname, gids in m['layers']:
            for g in gids:
                if g <= 0:
                    continue
                cur = None
                for fg, t, im in imgs:
                    if g >= fg:
                        cur = (fg, t, im)
                    else:
                        break
                if cur is None or cur[2] is None:
                    continue
                fg, t, im = cur
                lid = g - fg
                if lid >= t['tilecount']:
                    continue
                col, row = lid % t['columns'], lid // t['columns']
                tl = im.crop((col * t['tw'], row * t['th'],
                              col * t['tw'] + t['tw'], row * t['th'] + t['th']))
                if tl.convert('RGBA').getextrema()[3][1] > 0:
                    n += 1
        return n

    solid_real, solid_empty, solid_ghost = [], [], []
    for r in made:
        im = BG.Image.open(os.path.join(BGDIR, r['file']))
        if not all(lo == hi for lo, hi in im.convert('RGBA').getextrema()):
            continue
        if r['used'] == 0:
            solid_empty.append(r['file'])
        elif opaque_used(os.path.join(BG.MAPS, 'map%d.tmx' % r['room_id'])) == 0:
            solid_ghost.append(r['file'])
        else:
            solid_real.append(r['file'])
    check('B3 ★ 单色图必须能解释（无瓦片的空房 / 瓦片全为透明占位）；'
          '「有实心瓦片却画成单色」= 合成空转，才报红',
          not solid_real,
          '空转 %d %s ｜ 空房 %d ｜ 全透明占位 %d %s'
          % (len(solid_real), solid_real[:3], len(solid_empty),
             len(solid_ghost), solid_ghost[:3]))

    # B4 post-check：磁盘上真的存在（不信内存）
    on_disk = set(os.listdir(BGDIR))
    lost = [r['file'] for r in made if r['file'] not in on_disk]
    check('B4 落盘后回读：263 个文件都在磁盘上', not lost, '缺 %d %s' % (len(lost), lost[:4]))

    # B5 跨轮一致：本轮落盘图必须与第100轮**已验证**的 _evidence/os_bg/os_<N>.png
    #    逐像素相同（同一渲染函数的产物，跨轮不许漂移）
    ev_bg = os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                         '_evidence', 'os_bg')
    pair, bad2 = 0, []
    if os.path.isdir(ev_bg):
        for r in made:
            p = os.path.join(ev_bg, 'os_%d.png' % r['room_id'])
            if os.path.isfile(p):
                pair += 1
                if BG.Image.open(p).convert('RGBA').tobytes() != \
                        BG.Image.open(os.path.join(BGDIR, r['file'])).convert('RGBA').tobytes():
                    bad2.append(r['file'])
    check('B5 ★ 跨轮一致：与第100轮已验证的合成图逐像素相同（%d 对样本）' % pair,
          pair > 0 and not bad2, '不符 %d %s' % (len(bad2), bad2))

    os.makedirs(EV, exist_ok=True)
    with io.open(os.path.join(EV, 'bg_manifest101.json'), 'w', encoding='utf-8',
                 newline='\n') as f:
        json.dump({'generated_at': __import__('time').strftime('%Y-%m-%d %H:%M:%S'),
                   'count': len(made), 'rows': made,
                   'solid_empty_rooms': solid_empty, 'solid_transparent_ghosts': solid_ghost},
                  f, ensure_ascii=False, indent=1)
    return made


# --------------------------------------------------------------- 阶段 2：接线
ENTRY_RE = re.compile(r'^\s*"([^"]+)":\s*\{\s*$')


def wire_zone(path, targets, stats):
    """文本级逐行替换（保 CRLF / 缩进 / 键序）。targets: {sid: (bg,src,asset)}"""
    text = read_text(path)
    out, cur, changed = [], None, 0
    armed = False
    for ln in split_keepends(text):
        m = ENTRY_RE.match(ln)
        if m:
            cur = m.group(1)
            out.append(ln)
            continue
        if cur in targets:
            bg, src, asset = targets[cur]
            ind = ln[:len(ln) - len(ln.lstrip())]
            nl = ln[len(ln.rstrip('\r\n')):]
            if re.match(r'^\s*"bg":\s*null\s*,\s*$', ln):
                out.append('%s"bg": %s,%s' % (ind, json.dumps(bg, ensure_ascii=False), nl))
                out.append('%s"bg_source": %s,%s' % (ind, json.dumps(src, ensure_ascii=False), nl))
                armed = True
                changed += 1
                continue
            # ★★ 第101轮修正：`bg_source` **不一定是条目的最后一个键**（OneShot 分片里
            #    后面还跟着 `objects`）⇒ 原行 `"none"` 是**带尾逗号**的。第39轮的写法
            #    只认无逗号版；照搬会 (a) 漏替换 (b) 留下**重复键**（Python json 取最后
            #    一个 ⇒ bg_source 恒 'none'）。C1 首跑 bad=526 正是它。
            #    修法：允许尾逗号，并把原逗号**原样带过去**（行尾换行也照搬）。
            m2 = re.match(r'^(\s*)"bg_source":\s*"none"\s*(,?)\s*$', ln)
            if armed and m2:
                ind, cm = m2.group(1), m2.group(2)
                nl = ln[len(ln.rstrip('\r\n')):]
                out.append('%s"bg_asset": %s%s%s'
                           % (ind, json.dumps(asset, ensure_ascii=False), cm, nl))
                armed = False
                continue
        out.append(ln)
    if changed:
        write_text(path, ''.join(out))
    stats['zone'] += changed
    return changed


def wire_index(path, targets, stats):
    """`_index.json` 同结构（内联副本），同一套逐行替换。

    ★ 注意 `_index.json` 是 **LF**（本项目 index 与 zone 分片行尾不同代），
      逐行替换天然保住原行尾，无需特判。
    """
    return wire_zone(path, targets, stats)


def stage_wire(scenes, made, dry=False):
    by_fn = {r['file']: r for r in made}
    targets = {}
    for rid, rec in scenes.items():
        fn = target_name(rid)
        if fn not in by_fn:
            continue
        targets[rec['sid']] = ('bg/' + fn, 'tmx.composite', 'map%d.tmx' % rid)

    w('接线目标 %d 个' % len(targets))
    # 干跑：每个目标都要在对应文件里找到落点
    plan = []
    for z in ZONE_FILES:
        txt = read_text(os.path.join(SCENES, z))
        sids = [s for s in targets if s.split('.')[1] == z.split('.')[2]]
        miss = [s for s in sids if ('"%s": {' % s) not in txt]
        plan.append((z, len(sids), miss))
        w('   %-34s %3d 个目标  %s' % (z, len(sids), ('❗缺落点 %s' % miss if miss else 'OK')))
    itxt = read_text(os.path.join(SCENES, '_index.json'))
    imiss = [s for s in targets if ('"%s": {' % s) not in itxt]
    w('   %-34s %3d 个目标  %s' % ('_index.json（内联副本）', len(targets),
                                   ('❗缺落点 %s' % imiss[:4] if imiss else 'OK')))
    if dry:
        return targets

    stats = {'zone': 0}
    for z, _n, _m in plan:
        wire_zone(os.path.join(SCENES, z), targets, stats)
    if imiss:
        w('!! _index.json 缺落点 %d ⇒ 不改它（避免改半截）' % len(imiss))
    else:
        wire_index(os.path.join(SCENES, '_index.json'), targets, stats)
    w('接线改写条目 = %d（6 分片 + index 内联，两处同一份 key）' % stats['zone'])

    # ---- 落盘后复核（重新读盘，不信内存）----
    ok, bad = 0, []
    for z in ZONE_FILES:
        d = jload(os.path.join(SCENES, z))
        for sid, s in (d.get('scenes') or {}).items():
            if sid in targets:
                bg, src, asset = targets[sid]
                if (s.get('bg'), s.get('bg_source'), s.get('bg_asset')) != (bg, src, asset):
                    bad.append(('zone', sid, s.get('bg'), s.get('bg_source')))
                else:
                    ok += 1
    idx = jload(os.path.join(SCENES, '_index.json'))
    for ak, av in ((idx['chapters'].get('oneshot') or {}).get('areas') or {}).items():
        for sid, s in ((av or {}).get('scenes') or {}).items():
            if sid in targets:
                bg, src, asset = targets[sid]
                if (s.get('bg'), s.get('bg_source'), s.get('bg_asset')) != (bg, src, asset):
                    bad.append(('index', sid, s.get('bg'), s.get('bg_source')))
                else:
                    ok += 1
    check('C1 ★ 两处都写对且**一致**（zone 263 + index 263，逐字段）',
          not bad and ok == 526, 'ok=%d bad=%d %s' % (ok, len(bad), bad[:4]))
    return targets


def main():
    argv = sys.argv[1:]
    scenes = zone_scenes()
    w('OneShot scene = %d（room_id 1..263）' % len(scenes))
    if '--wire' not in argv:
        made = stage_build(scenes)
        w('产物目录 %s' % BGDIR)
        w('FAIL = %d %s' % (len(FAILS), FAILS))
        return 1 if FAILS else 0
    made = stage_build(scenes)
    stage_wire(scenes, made, dry=('--dry' in argv))
    if '--dry' in argv:
        return 0
    w('FAIL = %d %s' % (len(FAILS), FAILS))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())

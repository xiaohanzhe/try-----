# -*- coding: utf-8 -*-
u"""build103.py —— 第103轮构建：**物件切帧 + 写进区域分片**。

已定死的两条规则（证据见 _evidence/grid_anchor103.json 与第103轮报告）：

  ① 栅格：`cell = (sheet_w // 4, sheet_h // 4)`；`col = pattern`；`row = DIR_ROW[direction]`
     （`{2:0, 4:1, 6:2, 8:3}` = 下/左/右/上，原点左上）。
     证据：`pc`(192x128) 行 0 四列 = 显示器**暗/蓝/绿/粉**四态；`green_npc_cedric` 列 0
     = 四朝向；3 列候选线把角色**切成两半**（像素否掉）；数据侧 `pattern` 0~3 全有用量
     （1684 个用 3 ⇒ 4 列才有地方放）；宽高能被 4 整除 **0 例外**。

  ② 锚点：`tile_bottom_center` —— 格**底边贴瓦片底边、水平居中于瓦片中心**：
        pos = (x*16 + 8 - cw//2, y*16 + 16 - ch)
     **两轴都由像素定死**（不再只是"RPG Maker 惯例"）：
     · 竖向：`bg/oneshot_map4.png`（= `map4.tmx` 瓦片层 1:1 合成）**列 21 的行 8/9
       全黑**（RGB max == 0）= 门洞，相邻列/行非黑 = 墙/地板；`DOORS2` 格恰 16x32
       ⇒ "格底贴瓦片底"覆盖行 8..9 **正好落进门洞**，"格左上贴瓦片左上"覆盖行 9..10
       ⇒ 门掉到地板上（判据图 `cmp_door_map4_103.png`）。
     · 横向：把"门洞法"推广成「**宽物件（cw≥32 且 cw%16==0）落在恰好同宽的黑洞上**」，
       并加资格判据（洞必须**局部**：外圈至少一侧非黑，否则那是房间虚空）——
       6 候选（竖{底,顶} × 横{左,居中,右}）里 **「底+居中」54 例唯一赢**，
       底+左 0 / 底+右 0 / 顶 0（`probe103p.py` ⇒ `anchor_cases103.json`）。
     · 唯一的"推导"成分：逐格不透明包围盒实测「地面接触线在格底」（
       `green_npc_cedric`/`green_npc_adult3`/`red_rue`/`DOORS`/`items_tut`/`pc`
       全部 `y1 == ch`）—— 它解释**为什么**是这个锚点，但不单独构成横向判据。

产出：
  · `ralsei_pet/assets/scenes/oneshot_cells/<sheet>__c<col>r<row>.png`（**380** 个）
  · 6 个 `_zone.oneshot.<area>.json` 的场景 `objects`（**就地行替换**，保留原 EOL/缩进）
  · `_evidence/cells103.json` / `objects103.json`

⚠️ 刻意**不写** `_index.json` 的内联副本 —— 见脚本末尾 `INDEX_NOTE` 与报告 §103：
   内联 `objects` 是**占位**（`load_scene` 只从独立文件/区域分片取场景体，
   见 `scene_system.load_scene` 来源 1/2），把 78 万字节派生数据再抄一份进索引
   没有收益、只有维护风险。这条与第101轮 `bg` 三字段"两层登记"的**区别**已写进
   索引 meta（`objects_source`），并在 `check103` 里正负成对断言。
"""
import collections
import hashlib
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
PROPS = os.path.join(SCENES, 'oneshot_props')
CELLS = os.path.join(SCENES, 'oneshot_cells')
spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')

TILE = 16
DIR_ROW = {2: 0, 4: 1, 6: 2, 8: 3}
ZONES = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.'))
INDEX_NOTE = (u'物件数据**只在区域分片**里（`objects`）；`_index.json` 内联副本的 '
              u'`objects` 恒为**占位空表** —— 场景体由 `scene_system.load_scene` 从'
              u'「独立文件 > 区域分片」取，索引行只提供 章/区/房间号。'
              u'第101轮 `bg` 三字段两层同名是因为它只有几十字节；物件是 78 万字节的'
              u'**派生**数据（由 tile/dir/pattern + 栅格规则可重算），再抄一份进索引'
              u'没有收益。栅格与锚点规则见第103轮报告 §103 与 check103 A 段。')


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


def read_raw(p):
    return io.open(p, encoding='utf-8', newline='').read()


def write_raw(p, t):
    io.open(p, 'w', encoding='utf-8', newline='').write(t)


def cell_file(cn, col, row):
    u"""格文件名。sheet 名先做文件系统安全化（只留 [A-Za-z0-9_-]）。"""
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', cn)
    return '%s__c%dr%d.png' % (safe, col, row)


def cell_size(sheet_path):
    im = Image.open(sheet_path)
    w, h = im.size
    assert w % 4 == 0 and h % 4 == 0, u'%s 宽高不能被 4 整除：%dx%d' % (sheet_path, w, h)
    return w // 4, h // 4


# ----------------------------------------------------------------- S0 前置
print('=' * 96)
print('S0 前置')
print('=' * 96)
assert os.path.isdir(PROPS), PROPS
assert os.path.isdir(SCENES)
print('  分片 %d 个：%s' % (len(ZONES), ZONES))
if not os.path.isdir(CELLS):
    os.makedirs(CELLS)
    print('  新建 %s' % os.path.relpath(CELLS, ROOT))
else:
    print('  已存在 %s' % os.path.relpath(CELLS, ROOT))

# ----------------------------------------------------------------- S1 切帧
print()
print('=' * 96)
print('S1 切帧（只切**实际用到的**格）')
print('=' * 96)
HAVE = set(f[:-4] for f in os.listdir(PROPS) if f.endswith('.png'))
rooms = {}
for n in range(1, 400):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p):
        continue
    evs = []
    for e in rj(p).get('events', []):
        pgs = e.get('pages') or []
        if not pgs:
            continue
        pg = pgs[0]
        g = pg.get('graphic') or {}
        if int(g.get('tile_id') or 0) > 0:
            continue
        cn = (g.get('character_name') or '').strip()
        if not cn:
            continue
        evs.append(dict(
            name=(e.get('name') or '').strip(),
            x=int(e.get('x') or 0), y=int(e.get('y') or 0), cn=cn,
            d=int(g.get('direction') or 0), p=int(g.get('pattern') or 0),
            aob=bool(pg.get('always_on_bottom')),
            aot=bool(pg.get('always_on_top')),
        ))
    if evs:
        rooms[n] = evs
print('  有物件房 %d 间 / 物件 %d 个' % (len(rooms), sum(len(v) for v in rooms.values())))

need = collections.OrderedDict()
skipped = collections.Counter()
skipped_rooms = collections.Counter()
for rid in sorted(rooms):
    for e in rooms[rid]:
        if e['cn'] not in HAVE:
            skipped[e['cn']] += 1
            skipped_rooms[rid] += 1
            continue
        col = e['p'] if e['p'] in (0, 1, 2, 3) else 0
        row = DIR_ROW[e['d']]
        need.setdefault((e['cn'], col, row), 0)
        need[(e['cn'], col, row)] += 1
print('  distinct (sheet,col,row) = %d；缺图集跳过 %d 个（%s，涉 %d 间房）'
      % (len(need), sum(skipped.values()), dict(skipped), len(skipped_rooms)))

cells_man = []
trans = 0
named = {}
for (cn, col, row), cnt in need.items():
    sp = os.path.join(PROPS, cn + '.png')
    cw, ch = cell_size(sp)
    im = Image.open(sp).convert('RGBA')
    cell = im.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch))
    fn = cell_file(cn, col, row)
    assert fn not in named or named[fn] == (cn, col, row), \
        u'文件名撞车：%s <- %s / %s' % (fn, named.get(fn), (cn, col, row))
    named[fn] = (cn, col, row)
    dst = os.path.join(CELLS, fn)
    cell.save(dst, 'PNG', optimize=True)
    blob = open(dst, 'rb').read()
    if cell.getchannel('A').getbbox() is None:
        trans += 1
    cells_man.append(dict(file=fn, sheet=cn, col=col, row=row,
                          w=cw, h=ch, objects=cnt, bytes=len(blob),
                          sha256=hashlib.sha256(blob).hexdigest()))
cells_man.sort(key=lambda r: r['file'])
tot_b = sum(r['bytes'] for r in cells_man)
print('  切出 %d 个格（其中**全透明** %d 个）· 合计 %.3f MB'
      % (len(cells_man), trans, tot_b / 1048576.0))
disk = sorted(f for f in os.listdir(CELLS) if f.endswith('.png'))
extra = sorted(f for f in os.listdir(CELLS) if not f.endswith('.png'))
print('  磁盘核对：目录里 %d 个 PNG（== 清单 %d：%s）· 杂项 %s'
      % (len(disk), len(cells_man), len(disk) == len(cells_man), extra or '(无)'))
assert not extra, u'cells 目录里有非 PNG 杂项'

# ----------------------------------------------------------------- S2 物件表
print()
print('=' * 96)
print('S2 物件表（按足底深度排序，声明顺序 = 绘制顺序）')
print('=' * 96)
objs_by_room = {}
for rid in sorted(rooms):
    ent = []
    for e in rooms[rid]:
        if e['cn'] not in HAVE:
            continue
        col = e['p'] if e['p'] in (0, 1, 2, 3) else 0
        row = DIR_ROW[e['d']]
        sp = os.path.join(PROPS, e['cn'] + '.png')
        cw, ch = cell_size(sp)
        x, y = e['x'], e['y']
        px = x * TILE + TILE // 2 - cw // 2
        py = y * TILE + TILE - ch
        ground = y * TILE + TILE
        depth = ground - 10 ** 6 if e['aob'] else (ground + 10 ** 6 if e['aot'] else ground)
        it = collections.OrderedDict()
        it['pos'] = [px, py]
        it['sprite'] = 'oneshot_cells/%s' % cell_file(e['cn'], col, row)
        it['tile'] = [x, y]
        it['depth'] = depth
        if e['name']:
            it['src'] = e['name']
        if e['aob']:
            it['layer'] = 'bottom'
        elif e['aot']:
            it['layer'] = 'top'
        ent.append(it)
    ent.sort(key=lambda o: (o['depth'], o['tile'][1], o['tile'][0]))
    objs_by_room[rid] = ent
n_written = sum(len(v) for v in objs_by_room.values())
print('  写入 %d 个物件（原 %d − 缺图集 %d = %d：%s）'
      % (n_written, sum(len(v) for v in rooms.values()), sum(skipped.values()),
         sum(len(v) for v in rooms.values()) - sum(skipped.values()),
         n_written == sum(len(v) for v in rooms.values()) - sum(skipped.values())))
print('  depth 单调（每间房内非降）：%s'
      % all(all(v[i]['depth'] <= v[i + 1]['depth'] for i in range(len(v) - 1))
            for v in objs_by_room.values() if len(v) > 1))
b = [o for v in objs_by_room.values() for o in v if o.get('layer') == 'bottom']
t = [o for v in objs_by_room.values() for o in v if o.get('layer') == 'top']
print('  layer=bottom %d / layer=top %d' % (len(b), len(t)))
print('  物件最多的 3 间：%s'
      % sorted(((r, len(v)) for r, v in objs_by_room.items()),
               key=lambda t2: -t2[1])[:3])

# ----------------------------------------------------------------- S3 写分片
print()
print('=' * 96)
print('S3 写进区域分片（就地行替换；保留原 EOL / 缩进）')
print('=' * 96)
room2scene = {}
for zf in ZONES:
    raw = rj(os.path.join(SCENES, zf))
    for sid, entry in (raw.get('scenes') or {}).items():
        if not isinstance(entry, dict):
            continue
        rid = entry.get('original_room_id')
        if isinstance(rid, int):
            room2scene.setdefault(rid, []).append((zf, sid))
dup_room = {r: v for r, v in room2scene.items() if len(v) > 1}
print('  分片里登记了 %d 个房间号；一房多场景 %s' % (len(room2scene), dup_room or '(无)'))
unmapped = sorted(set(objs_by_room) - set(room2scene))
print('  有物件但**没登记场景**的房：%d 间 %s' % (len(unmapped), unmapped[:10]))

payload = {}
for rid, ent in objs_by_room.items():
    hit = room2scene.get(rid)
    if not hit:
        continue
    zf, sid = hit[0]
    payload.setdefault(zf, {})[sid] = ent

total_patched = 0
for zf in ZONES:
    path = os.path.join(SCENES, zf)
    text = read_raw(path)
    n = text.count('\r\n')
    eol = '\r\n' if n else '\n'
    lines = text.split('\n')
    want = payload.get(zf, {})
    done = set()
    for i, ln in enumerate(lines):
        st = ln.rstrip('\r').strip()
        # ★ 别用 `st[:-2].strip().strip('"')` —— `.strip('"')` 只剥**两端**，
        #   尾部是 `:` 不是引号 ⇒ 会得到 `xxx":` 这种带残渣的键，永远匹配不上
        #   （首跑就栽在这：barrens 修 0 个场景）。用正则认键。
        mkey = re.match(r'^"([^"]+)"\s*:\s*\{\s*$', st)
        if not mkey:
            continue
        sid = mkey.group(1)
        if sid not in want:
            continue
        ind = None
        for j in range(i + 1, min(i + 40, len(lines))):
            s2 = lines[j].rstrip('\r').strip()
            if s2.startswith('"objects"'):
                ind = j
                break
        assert ind is not None, u'%s 里 %s 找不到 objects 行' % (zf, sid)
        raw_ln = lines[ind]
        indent = raw_ln[:len(raw_ln) - len(raw_ln.lstrip())]
        comma = ',' if raw_ln.rstrip('\r').rstrip().endswith(',') else ''
        cr = '\r' if raw_ln.endswith('\r') else ''
        blob = json.dumps(want[sid], ensure_ascii=False, separators=(',', ':'))
        assert raw_ln[:len(indent)] == indent
        lines[ind] = '%s"objects": %s%s%s' % (indent, blob, comma, cr)
        done.add(sid)
        total_patched += 1
    new = '\n'.join(lines)
    assert new.count('\r\n') == n, u'%s EOL 被改动（%d -> %d）' % (zf, n, new.count('\r\n'))
    write_raw(path, new)
    # 读回自证
    # ★ 比对要**对称**：`exp` 里可能有 `0`（某间房的物件**全被跳过** ——
    #   例如 `unzoned.Lobby_OLD_VER` 只有 1 个 `npc_BIG`，图集缺）；首跑我把
    #   "非空"当过滤条件 ⇒ 0 条的两边对不上，是**判据侧**的错，不是数据的错。
    back = rj(path)
    bsc = {sid: e for sid, e in (back.get('scenes') or {}).items()
           if isinstance(e, dict)}
    exp = {sid: len(v) for sid, v in want.items()}
    got = {sid: len((bsc.get(sid) or {}).get('objects') or []) for sid in want}
    stray = [sid for sid, e in bsc.items()
             if sid not in want and (e.get('objects') or [])]
    print('  %-30s 修 %2d 个场景 · 读回 %2d 个非空 · 条数一致 %s · 误改 %s'
          % (zf, len(done), len([x for x in got.values() if x]), got == exp,
             stray or '(无)'))
    assert got == exp, (zf, got, exp)
    assert not stray, (zf, stray)
print('  合计修 %d 个场景行' % total_patched)

# ----------------------------------------------------------------- S3.5 索引 meta
print()
print('=' * 96)
print('S3.5 索引 meta 声明 `objects_source`（无则插入）')
print('=' * 96)
ipath = os.path.join(SCENES, '_index.json')
itext = read_raw(ipath)
if '"objects_source"' in itext:
    print('  已存在，跳过')
else:
    crl = itext.count('\r\n')
    ilines = itext.split('\n')
    k = None
    for i, ln in enumerate(ilines):
        if ln.rstrip('\r').strip().startswith('"zone_note"'):
            k = i
            break
    assert k is not None, u'_index.json 找不到 zone_note'
    raw_ln = ilines[k]
    cr = '\r' if raw_ln.endswith('\r') else ''
    assert not raw_ln.rstrip('\r').rstrip().endswith(','), u'zone_note 后已有逗号？'
    ilines[k] = raw_ln.rstrip('\r') + ',' + cr
    new_ln = '    "objects_source": %s%s' % (
        json.dumps(INDEX_NOTE, ensure_ascii=False), cr)
    ilines.insert(k + 1, new_ln)
    newt = '\n'.join(ilines)
    assert newt.count('\r\n') == crl + (1 if cr else 0)
    write_raw(ipath, newt)
    d = rj(ipath)
    assert 'objects_source' in d['meta']
    print('  插入 1 行；读回 meta 键数 %d；objects_source 前 40 字：%s'
          % (len(d['meta']), d['meta']['objects_source'][:40]))

# ----------------------------------------------------------------- S4 汇总
print()
print('=' * 96)
print('S4 证据落盘')
print('=' * 96)
io.open(os.path.join(EV, 'cells103.json'), 'w', encoding='utf-8', newline='\n').write(
    json.dumps(dict(note='第103轮切帧清单（380 格）', tile=TILE,
                    rule=dict(cell='sheet_w//4 x sheet_h//4', col='pattern',
                              row='DIR_ROW{2:0,4:1,6:2,8:3}', origin='左上'),
                    anchor='tile_bottom_center  pos=(x*16+8-cw//2, y*16+16-ch)',
                    total=len(cells_man), bytes=tot_b, transparent=trans,
                    files=cells_man), ensure_ascii=False, indent=1))
per_scene = {}
for rid, ent in objs_by_room.items():
    hit = room2scene.get(rid)
    if hit:
        per_scene[hit[0][1]] = dict(room=rid, zone=hit[0][0], n=len(ent),
                                    tiles=[o['tile'] for o in ent][:1])
io.open(os.path.join(EV, 'objects103.json'), 'w', encoding='utf-8', newline='\n').write(
    json.dumps(dict(note='第103轮物件接线普查',
                    objects_total=sum(len(v) for v in rooms.values()),
                    objects_written=n_written,
                    skipped_missing_sheet=dict(skipped),
                    skipped_rooms=sorted(skipped_rooms),
                    rooms_with_objects=len(objs_by_room),
                    rooms_registered=len(room2scene),
                    unmapped_rooms=unmapped,
                    cells=len(cells_man), cells_transparent=trans,
                    layer_bottom=len(b), layer_top=len(t),
                    per_room={str(r): len(v) for r, v in sorted(objs_by_room.items())},
                    scenes_patched=total_patched), ensure_ascii=False, indent=1))
print('  _evidence/cells103.json    %d 条格' % len(cells_man))
print('  _evidence/objects103.json  写入 %d / 跳过 %d' % (n_written, sum(skipped.values())))

# ---- S4b 规则与**证据等级**（防"把推导写成实测"）----
n_big = sum(1 for v in objs_by_room.values() for o in v
            if Image.open(os.path.join(CELLS, os.path.basename(o['sprite']))).size[0] > TILE)

# ★★★ 证据等级**派生**，不许手打。
#    起因：横向锚点最早只有"包围盒 + RPG Maker 惯例"的**推导**，于是诚实标成
#    `authored（推导）`；后来 `probe103p.py` 用"宽物件填同宽黑洞"给出了**像素判据**
#    （6 候选里「底+居中」54 例唯一赢）。如果这里继续写死字符串，就会出现
#    「证据升级了但登记没跟上」/「有人把它改回 authored 也没人发现」两种漂移。
#    ⇒ 从 `anchor_cases103.json`（probe103p 的产物）**算**出等级，并把票数抄进证据。
_ac = None
_acp = os.path.join(EV, 'anchor_cases103.json')
if os.path.isfile(_acp):
    _ac = rj(_acp)
if _ac and _ac.get('unique_bottom_center') and not (
        _ac.get('unique_bottom_left') or _ac.get('unique_bottom_right')
        or _ac.get('any_top_winner')):
    h_level = u'proven_by_pixel'
    h_text = (u'**像素**（升级自推导）：把"门洞法"推广成「**宽物件（cw>=32 且 cw%%16==0）'
              u'落在**恰好同宽**的黑洞上」——判据 = 该行带内「含格落位的极大全黑列段」'
              u'**恰等于**格的列集合（差一列即不算），加资格判据（洞必须**局部**：'
              u'外圈至少一侧非黑，否则那是房间虚空而不是"给物件留的洞"）。'
              u'6 候选（竖{底,顶} x 横{左,居中,右}）结果：**底+居中 %d 例唯一赢**，'
              u'底+左 %d / 底+右 %d / 顶 %d（判据脚本 `probe103p.py` -> '
              u'`anchor_cases103.json`；样例 `cmp_strict_tv_encounter_r131103.png` / '
              u'`cmp_strict_tv_screens1_r241103.png`）。"黑"= 原作 `black.tsx` 瓦片，'
              u'也就是**原作自己给物件留的洞**。'
              % (_ac['unique_bottom_center'], _ac['unique_bottom_left'],
                 _ac['unique_bottom_right'], _ac['any_top_winner']))
    h_note = u'★ 本字段由 `anchor_cases103.json` 派生，不是手打（见 build103.py S4b 注释）。'
else:
    h_level = u'authored（推导）'
    h_text = (u'**推导**（不是实测）：① 逐格不透明包围盒实测"地面接触线在格底、'
              u'且角色类左右余量对称（2/3、2/2）" ⇒ 格中心 = 瓦片中心；'
              u'② RPG Maker / Tiled 的 `screenX = x*tw + tw/2`、锚点 (cw/2, ch) 惯例。'
              u'★ 未找到 `anchor_cases103.json`（或它没有唯一赢家）⇒ 如实标 authored。')
    h_note = u''
grid = dict(
    note=u'第103轮：OneShot 物件「栅格 + 锚点」规则及其**证据等级**。',
    tile_px=TILE,
    cell=dict(formula='sheet_w//4 x sheet_h//4', origin=u'格左上',
              sample={'green_npc_cedric': [96, 128, 24, 32],
                      'pc': [192, 128, 48, 32],
                      'items_tut': [64, 64, 16, 16],
                      'DOORS': [64, 128, 16, 32],
                      'DOORS2': [64, 128, 16, 32]}),
    col='pattern', row=dict(map=DIR_ROW,
                            why=u'下/左/右/上 = RPG Maker 的 direction 行序（2/4/6/8）'),
    anchor=dict(rule='tile_bottom_center',
                formula='pos = (tile_x*16 + 8 - cw//2, tile_y*16 + 16 - ch)',
                vertical=u'proven_by_pixel',
                horizontal=h_level),
    anchor_evidence_note=h_note,
    evidence=dict(
        grid=u'像素：`pc`(192x128) 行 0 四列 = 显示器 暗/蓝/绿/粉 四态、各含一张完整书桌 ⇒ '
             u'列 = pattern 且**只有 4 列**成立；3 列候选线把角色切成两半（放大图上肉眼可判）。'
             u'数据：`pattern` 0~3 全有用量（1684 个物件用 3）⇒ 3 列无处置放；'
             u'全部图集宽高能被 4 整除 0 例外。',
        vertical=u'像素：`bg/oneshot_map4.png`（= `map4.tmx` 瓦片层 1:1 合成）列 21 的行 8/9 '
                 u'**全黑**（RGB max == 0）= 门洞；相邻列 20/22 同行 ≈13.5、同列行 10 ≈22.5 = 墙/地板。'
                 u'`DOORS2` 格恰 16x32（1 瓦片宽 x 2 瓦片高）；A1（格底贴瓦片底）覆盖行 8..9 = '
                 u'**正好落在门洞里**；A0（格左上贴瓦片左上）覆盖行 9..10 ⇒ 门掉到地板上（判据图 '
                 u'`cmp_door_map4_103.png`）。',
        horizontal=h_text),
    stats=dict(cells=len(cells_man), transparent_cells=trans, objects=n_written,
               objects_with_cell_wider_than_tile=n_big,
               cells_rule_hits=dict(col0=sum(1 for k in need if k[1] == 0),
                                    col1=sum(1 for k in need if k[1] == 1),
                                    col2=sum(1 for k in need if k[1] == 2),
                                    col3=sum(1 for k in need if k[1] == 3))))
io.open(os.path.join(EV, 'grid_anchor103.json'), 'w', encoding='utf-8',
        newline='\n').write(json.dumps(grid, ensure_ascii=False, indent=1))
print('  _evidence/grid_anchor103.json  规则 + 证据等级（竖向=像素 / 水平=%s，由 '
      'anchor_cases103.json 派生）' % h_level)
print('  格宽 > 16px 的物件 %d 个（水平锚点只影响这些）' % n_big)
print()
print('  ★ 守恒：%d(写入) + %d(缺图集) == %d(原作可见物件) -> %s'
      % (n_written, sum(skipped.values()), sum(len(v) for v in rooms.values()),
         n_written + sum(skipped.values()) == sum(len(v) for v in rooms.values())))

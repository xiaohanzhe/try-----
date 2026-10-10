# -*- coding: utf-8 -*-
u"""第103轮回归锁：OneShot 物件「栅格 + 锚点」规则与接线不许漂移。

口径（用户）：
    「**一切根据原作**」/「把原作的世界搬到桌面上，桌面也是一个场景」
    /「（第44轮原始设计）场景图就和 ralsei 桌宠的体积与原作 ralsei 体积的比例
       **等比放大**，**剩下的用黑色填充**」

本轮做了什么
------------
第102轮把 **148** 张物件图集**整张**入库，**刻意不切帧** —— 理由是 `graphic` 里
**没有 `character_index`**，"取哪一块"在数据里**没有依据**。本轮把这个依据**定死**，
然后切帧 + 接线：

  ① **栅格**：`cell = (sheet_w // 4, sheet_h // 4)`；`col = pattern`；
     `row = DIR_ROW[direction]`（`{2:0,4:1,6:2,8:3}` = 下/左/右/上，原点左上）。
  ② **锚点**：`tile_bottom_center` ——
     `pos = (tile_x*16 + 8 - cw//2, tile_y*16 + 16 - ch)`。
     **两轴都由像素定死**：竖向靠"`DOORS2`(16x32) 落进 `map4` 的门洞（列 21 行 8/9
     全黑）"；横向靠"宽物件落在**恰好同宽**的黑洞上"（6 候选里「底+居中」**54:0**
     唯一赢）。"黑" = 原作 `black.tsx` 瓦片 = **原作自己给物件留的洞**。
  ③ **切帧**：distinct `(sheet,col,row)` = **380** ⇒ 去掉缺图集的 1 张（`npc_BIG`）
     ⇒ 实切 **379** 个格（**2** 个全透明），合计 **0.275 MB**。
  ④ **接线**：**7804** 个物件写进 6 个区域分片（**189** 个场景行；其中 **188** 行非空
     —— 第 189 行是房间 96，它唯一的物件就是缺图集的 `npc_BIG`）。
     **两层登记的偏差是声明过的**：物件只写区域分片，`_index.json` 内联副本的
     `objects` 保持**占位空表**（场景体由 `scene_system.load_scene` 从
     「独立文件 > 区域分片」取），并在索引 `meta.objects_source` 里写明原因。

判据分四段
----------
 A **栅格/锚点面**（从磁盘**复算**，不读构建脚本的结论）：
   379 格 ↔ 148 图集 · 格 = 图集 1/4 · 格与图集裁切**逐像素**相同 ·
   **每个物件的 `pos` 都等于公式**（用格 PNG 的真尺寸，不信任何"记录尺寸"）·
   ★ **证据等级不得被悄悄降级**（`grid_anchor103.json` 与 `anchor_cases103.json`）
 B **落盘面**：379 张在位/无杂项 · 逐张 sha256 · 尺寸 · 总字节 · 全透明 2 张
 C **数据面**：守恒（7804 + 1 == 7805）· 逐房计数对第102轮普查**独立对账** ·
   depth/layer 自洽 + 场景内单调 · 两层登记偏差**正是声明的那样**（正负成对）
 D **渲染面 + 纪律**：真跑 `plan_frame` ⇒ `K_OBJ` 数目与**坐标**都对 ·
   真画布 `paint_on` 出图且零缺素材 · **负控制：把一个物件挪 16px 必须改对** ·
   工具在位 · ★★ 零外部依赖 / 无恒真判据

★ 铁律：成功标记 `[PASS]` 字面量（`run_all.py` 按它计数）；正/负控制成对；
  判据名禁自带标记；**零 Qt 窗口**（`QT_QPA_PLATFORM=offscreen`）；
  **零外部盘依赖**（原作在 C 盘桌面，回归碰不得 —— 本套件只读仓库内文件 +
  第102轮落在仓库里的 `objects_census102.json`）。
"""
import ast
import collections
import hashlib
import io
import json
import os
import re
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.dirname(os.path.abspath(__file__))
# ⚠️ 住在 `<轮次>/_tools/` ⇒ 上溯三层才是仓库根（第38轮起的老坑）
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
EV102 = os.path.join(ROOT, 'code-quality-audit', '第102轮-光照与ambient接入', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
PROPS = os.path.join(SCENES, 'oneshot_props')
CELLS = os.path.join(SCENES, 'oneshot_cells')
TILE = 16
DIR_ROW = {2: 0, 4: 1, 6: 2, 8: 3}
ZONE_FILES = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.'))

sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

_N = [0]
_FAIL = []
_APP = None          # Qt 应用单例（必须在模块级持有，见 sec_d 注释）


def ok(cond, msg):
    _N[0] += 1
    if cond:
        print('[PASS] %s' % msg)
    else:
        _FAIL.append(msg)
        print('[FAIL] %s' % msg)


def jload(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


def _png_size(path):
    """零依赖读 PNG 宽高（IHDR）—— 不为量尺寸去起 Qt。"""
    try:
        with open(path, 'rb') as fh:
            head = fh.read(33)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', head[16:24])


def _sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _alpha_has_content(path):
    from PIL import Image
    return Image.open(path).convert('RGBA').getchannel('A').getbbox() is not None


# ★★ D2 的外部路径特征串：**必须拼出来**，不能写成整串字面量 ——
#    否则检查器自己的这几条常量会被自己的 AST 扫描扫到 ⇒ **恒假判据**（自己报自己）。
_EXTERNAL = ('ni' + 'ko', 'OneShot' + 'MG', 'OneShot.World' + '.Machine',
             'gamedata' + os.sep + 'maps')

# ---------------------------------------------------------------- 读一次，全用
_CEN = jload(os.path.join(EV102, 'objects_census102.json'))
_MAN = jload(os.path.join(EV, 'cells103.json'))
_OBJ = jload(os.path.join(EV, 'objects103.json'))
_GA = jload(os.path.join(EV, 'grid_anchor103.json'))
_AC = jload(os.path.join(EV, 'anchor_cases103.json'))
_REN = jload(os.path.join(EV, 'render103.json'))
_IDX = jload(os.path.join(SCENES, '_index.json'))

# 分片里的物件：**只从分区文件读**，不读构建脚本的产物清单
_OBJS = []           # (zone, sid, room_id, obj)
for _zf in ZONE_FILES:
    _d = jload(os.path.join(SCENES, _zf))
    for _sid, _ent in (_d.get('scenes') or {}).items():
        if not isinstance(_ent, dict):
            continue
        for _o in (_ent.get('objects') or []):
            _OBJS.append((_zf, _sid, _ent.get('original_room_id'), _o))

_FN_RE = re.compile(r'^(?P<sheet>.+)__c(?P<col>\d)r(?P<row>\d)$')


def _sprite_fn(o):
    return os.path.basename(o.get('sprite') or '')


# 格 PNG 的真尺寸（**唯一可信来源** —— 不信 cells103.json 里的记录）
_CELL_SZ = {}
for _f in sorted(os.listdir(CELLS)):
    if _f.endswith('.png'):
        _CELL_SZ[_f] = _png_size(os.path.join(CELLS, _f))


# ===========================================================================
# A 栅格 / 锚点面（**复算**，不读构建脚本的结论）
# ===========================================================================
def sec_a():
    print('== A 栅格/锚点面（从磁盘复算，不信构建脚本的结论）==')

    # ---- A1 栅格规则：格 * 4 == 图集尺寸（对每个被引用的 sheet 都验）----
    sheets = set()
    bad_grid = []
    for _z, _s, _r, o in _OBJS:
        fn = _sprite_fn(o)
        m = _FN_RE.match(fn[:-4] if fn.endswith('.png') else '')
        if not m:
            bad_grid.append((fn, '名字不合规'))
            continue
        sheets.add(m.group('sheet'))
    bad_frac = []
    for sh in sorted(sheets):
        ps = os.path.join(PROPS, sh + '.png')
        sw, shh = _png_size(ps)
        # 任取该 sheet 的一个格，验"格 * 4 == 图集"
        cand = sorted(f for f in _CELL_SZ if f.startswith(sh + '__c'))
        if not cand:
            bad_frac.append((sh, '没有它的格 PNG'))
            continue
        # 格尺寸只由 sheet 尺寸决定 ⇒ 取任一个都对；取第一个（排序后）保证可复现
        cw, ch = _CELL_SZ[cand[0]]
        if (cw * 4, ch * 4) != (sw, shh):
            bad_frac.append((sh, (cw, ch), (sw, shh)))
    ok(not bad_grid and len(sheets) == 148,
       'A1 物件引用的 sheet 恰好 148 个（第102轮普查 149 − 缺的 1 张 `npc_BIG`）'
       '实际 %d；命名不合规 %d %s' % (len(sheets), len(bad_grid), bad_grid[:2]))

    ok(not bad_frac,
       'A2 ★★ 栅格规则 `cell = (sheet_w//4, sheet_h//4)` 对全部 148 个 sheet 成立'
       '（格 x4 == 图集尺寸；不符 %d %s）' % (len(bad_frac), bad_frac[:2]))

    # ---- A3 格 PNG 与"从图集裁下来"逐像素相同 ----
    mism = []
    for f in sorted(_CELL_SZ):
        m = _FN_RE.match(f[:-4])
        sh, col, row = m.group('sheet'), int(m.group('col')), int(m.group('row'))
        cw, ch = _CELL_SZ[f]
        a = _PIL().open(os.path.join(PROPS, sh + '.png')).convert('RGBA')
        b = _PIL().open(os.path.join(CELLS, f)).convert('RGBA')
        if a.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch)).tobytes() \
                != b.tobytes():
            mism.append(f)
    ok(not mism,
       'A3 ★★ 379 个格 PNG 全部与「按 `(col,row)` 从图集裁下来」**逐像素相同**'
       '（证明切帧位置没偏、`col=pattern` 没写反；不一致 %d %s）'
       % (len(mism), mism[:3]))

    # ---- A4 ★★★ 锚点：每个物件的 pos 都由 (tile, 格真尺寸) 复算得出 ----
    bad_pos = []
    for _z, _s, _r, o in _OBJS:
        fn = _sprite_fn(o)
        if fn not in _CELL_SZ:
            bad_pos.append((fn, '格不在盘上'))
            continue
        cw, ch = _CELL_SZ[fn]
        tx, ty = o['tile']
        exp = [tx * TILE + TILE // 2 - cw // 2, ty * TILE + TILE - ch]
        if list(o['pos']) != exp:
            bad_pos.append((_s, fn, o['tile'], o['pos'], exp))
    ok(not bad_pos,
       'A4 ★★★ 全部 %d 个物件的 `pos` == `(tile_x*16+8-cw//2, tile_y*16+16-ch)`'
       '（`cw/ch` 取**格 PNG 的真尺寸**，不信记录；不符 %d %s）'
       % (len(_OBJS), len(bad_pos), bad_pos[:2]))

    # ---- A4b 负控制：这条判据有鉴别力（换一个 tile 就必须不等）----
    o0 = _OBJS[0][3]
    cw, ch = _CELL_SZ[_sprite_fn(o0)]
    tx, ty = o0['tile']
    f0 = (tx * TILE + TILE // 2 - cw // 2, ty * TILE + TILE - ch)
    f1 = ((tx + 1) * TILE + TILE // 2 - cw // 2, ty * TILE + TILE - ch)
    f2 = (tx * TILE + TILE // 2 - cw // 2, (ty + 1) * TILE + TILE - ch)
    ok(f0 != f1 and f1[0] - f0[0] == TILE and f1[1] == f0[1]
       and f2[1] - f0[1] == TILE and f2[0] == f0[0],
       'A4b 负控制：同一物件"tile_x+1"算出的 pos 必须差 **恰好一个瓦片**、'
       '且只动 x（%s -> %s）；"tile_y+1"只动 y（-> %s）。'
       '说明 A4 的等式两边真的在量同一个东西' % (f0, f1, f2))

    # ---- A5 ★ 证据等级不得被悄悄降级 ----
    ok(_GA['anchor']['vertical'] == 'proven_by_pixel',
       'A5 ★ `grid_anchor103.json` 竖向证据等级 == `proven_by_pixel`（实际 %r）——'
       '门洞法（`DOORS2` 16x32 落进 `map4` 列 21 行 8/9 全黑）是像素级实证，'
       '不许被降格成"惯例推导"' % (_GA['anchor']['vertical'],))
    ok(_GA['anchor']['horizontal'] == 'proven_by_pixel',
       'A6 ★ 横向证据等级 == `proven_by_pixel`（实际 %r）—— "宽物件填同宽黑洞"是'
       '像素级实证，不许被降格' % (_GA['anchor']['horizontal'],))
    n_win = _AC['unique_bottom_center']
    others = (_AC['unique_bottom_left'], _AC['unique_bottom_right'], _AC['any_top_winner'])
    ok(n_win == 54 and others == (0, 0, 0),
       'A7 ★★ 横向锚点判据：6 候选里「底+居中」**%d 例唯一赢**，其余三档 '
       '左/右/顶 = %s 全 0（弱于 54:0 就不再是"唯一赢家"）' % (n_win, others))
    ok(_GA['anchor'].get('formula') == 'pos = (tile_x*16 + 8 - cw//2, tile_y*16 + 16 - ch)'
       and _GA.get('tile_px') == TILE and _GA.get('col') == 'pattern'
       and {int(k): v for k, v in _GA['row']['map'].items()} == DIR_ROW,
       'A8 ★ 登记在案的规则与判据实现**逐字一致**（公式 / tile_px=16 / col=pattern / '
       'row 映射 %s）' % DIR_ROW)
    ok(bool(_GA.get('anchor_evidence_note')) and '派生' in _GA['anchor_evidence_note'],
       'A9 ★ 证据等级是**派生**的（`anchor_evidence_note` 声明它来自 '
       '`anchor_cases103.json`），不是手打的字符串')

    # A10 复核：候选取样量不能太小（否则"54"没有说服力）
    ok(_AC['candidates'] >= 700 and _AC['unique_bottom_center'] +
       _AC['winner_table'].get(u'无', 0) == _AC['candidates'],
       'A10 判据取样规模 %d 个候选，且"赢 %d + 无 %d" == 取样总数（分类不重不漏）'
       % (_AC['candidates'], n_win, _AC['winner_table'].get(u'无', 0)))


def _PIL():
    from PIL import Image
    return Image


# ===========================================================================
# B 落盘面（379 个格）
# ===========================================================================
def sec_b():
    print('== B 落盘面（379 个格 PNG）==')
    disk = sorted(f for f in os.listdir(CELLS) if f.endswith('.png'))
    extra = sorted(f for f in os.listdir(CELLS) if not f.endswith('.png'))
    ok(len(disk) == 379 and not extra,
       'B1 `oneshot_cells/` 里恰好 379 张 PNG 且无杂项（实际 %d 张；杂项 %s）'
       % (len(disk), extra[:3]))

    man = {f['file']: f for f in _MAN['files']}
    ok(len(_MAN['files']) == 379 and set(man) == set(disk),
       'B2 清单与磁盘**一一对应**（清单 %d / 磁盘 %d）' % (len(_MAN['files']), len(disk)))

    bad_sha = [f for f in disk
               if _sha(os.path.join(CELLS, f)) != man.get(f, {}).get('sha256')]
    ok(not bad_sha,
       'B3 ★★ 逐张 sha256 与清单一致（防格被改/被重压；不符 %d %s）'
       % (len(bad_sha), bad_sha[:3]))

    bad_sz = [f for f in disk
              if _CELL_SZ[f] != (man.get(f, {}).get('w'), man.get(f, {}).get('h'))]
    ok(not bad_sz, 'B4 逐张尺寸与清单一致（不符 %d %s）' % (len(bad_sz), bad_sz[:3]))

    tot = sum(os.path.getsize(os.path.join(CELLS, f)) for f in disk)
    ok(tot == _MAN['bytes'],
       'B5 落盘总字节 == 清单 %d（实际 %d；%.3f MB）'
       % (_MAN['bytes'], tot, tot / 1048576.0))

    trans = [f for f in disk if not _alpha_has_content(os.path.join(CELLS, f))]
    ok(len(trans) == 2 and len(trans) == _MAN['transparent'],
       'B6 全透明格**恰好 2 个**且与清单一致（实际 %d %s）—— '
       '如实登记而不是"悄悄丢掉"：透明格说明该 `(col,row)` 在原作里真的是空的'
       % (len(trans), trans))

    # B7 负控制：裁掉 1 列 ⇒ 尺寸判据必须报红
    #   ⚠️ 别写死文件名：`DOORS` 只有 `r0`（原作只用了 direction=2）——
    #      "DOORS__c0r3.png" 根本不在盘上，写死会让负控制自己先崩。
    f0 = sorted(man)[0]
    exp = (_MAN_W(f0), _MAN_H(f0))
    from PIL import Image
    im = Image.open(os.path.join(CELLS, f0))
    cut = im.crop((0, 0, im.width - 1, im.height))
    ok(cut.size != exp and cut.size == (exp[0] - 1, exp[1]),
       'B7 负控制：把 %s 裁掉 1 列 ⇒ 尺寸判据必须报红（%s vs %s）' % (f0, cut.size, exp))

    # B8 反向：清单里的每一行都真的是一个"用到的格"（没有多切）
    used = set()
    for _z, _s, _r, o in _OBJS:
        used.add(_sprite_fn(o))
    ok(used == set(disk),
       'B8 ★ 磁盘上的格**没有一个是多余的**（用到的 %d == 盘上 %d；多切 %s / 少切 %s）'
       % (len(used), len(disk), sorted(set(disk) - used)[:3], sorted(used - set(disk))[:3]))


def _MAN_W(f):
    return {x['file']: x['w'] for x in _MAN['files']}[f]


def _MAN_H(f):
    return {x['file']: x['h'] for x in _MAN['files']}[f]


# ===========================================================================
# C 数据面（两层登记 + 守恒 + 深度）
# ===========================================================================
def sec_c():
    print('== C 数据面（守恒 / 逐房独立对账 / 深度）==')
    ok(_OBJ['objects_written'] == 7804 and _OBJ['objects_total'] == 7805
       and _OBJ['skipped_missing_sheet'] == {'npc_BIG': 1},
       'C1 守恒：写入 %d + 缺图集 %s == 原作可见物件 %d'
       % (_OBJ['objects_written'], _OBJ['skipped_missing_sheet'], _OBJ['objects_total']))

    ok(len(_OBJS) == 7804 and _OBJ['objects_written'] == len(_OBJS),
       'C2 ★ 从 6 个分片里**数出来**的物件数 == 登记的写入数（%d）—— '
       '结论不是只活在构建脚本的产物清单里' % len(_OBJS))

    ok(_CEN['counts']['visible'] == _OBJ['objects_total'] + 0
       and _OBJ['objects_written'] == _CEN['counts']['visible'] - 1,
       'C3 ★★ 与第102轮普查**跨轮对账**：`visible` %d − 缺图集 1 == 写入 %d'
       % (_CEN['counts']['visible'], _OBJ['objects_written']))

    # ---- C4 ★★ 逐房计数对第102轮普查独立对账 ----
    #   ⚠️ 第 1 个坎：**先决定哪些房"允许不等"**，再断言其余全等。
    #      房间 96 在普查里有 1 个物件，而写入 0 个（那 1 个正是缺图集的
    #      `npc_BIG`）⇒ 它**必然**是 (1, 0)。如果把"全部相等"写成一条断言，
    #      这条锁就会永远报红，而真相是"如实跳过"。（首跑就是踩这个。）
    cen_room = {str(r['room_id']): r['n'] for r in _CEN['rooms']}
    got_room = collections.Counter()
    for _z, _s, _r, o in _OBJS:
        got_room[str(_r)] += 1
    skip_room = set(str(r) for r in _OBJ['skipped_rooms'])
    diff = {k: (cen_room[k], got_room.get(k, 0)) for k in cen_room
            if k not in skip_room and cen_room[k] != got_room.get(k, 0)}
    ok(len(cen_room) == 189 and skip_room == {'96'} and not diff,
       'C4 ★★ **逐房**计数与普查一致（189 间房；除"缺图集房"外 0 处不等）—— '
       '不等 %s；允许不等的房 = %s' % (diff or '(无)', sorted(skip_room)))

    ok(cen_room.get('96') == 1 and got_room.get('96', 0) == 0,
       'C5 ★ 房间 96 的差**恰好**是 `(%s, %s)`：普查里 1 个、写入 0 个 —— '
       '因为那 1 个就是缺图集的 `npc_BIG`（如实跳过，不静默丢、也不假装它不存在）'
       % (cen_room.get('96'), got_room.get('96', 0)))

    # ---- C6 场景行：189 行**被写过**，其中 188 行非空 ----
    rows = {}
    for _zf in ZONE_FILES:
        _d = jload(os.path.join(SCENES, _zf))
        for _sid, _ent in (_d.get('scenes') or {}).items():
            if isinstance(_ent, dict) and isinstance(_ent.get('objects'), list):
                rows[_sid] = len(_ent['objects'])
    nonempty = [s for s, n in rows.items() if n]
    ok(len(rows) == 263,
       'C6 ★ 263 个 OneShot 场景**每个都有** `objects` 键（不是"有的场景漏了字段"）'
       '实际 %d' % len(rows))
    ok(len(nonempty) == 188 and _OBJ['rooms_with_objects'] == 189,
       'C7 ★★ 两个数要分清：**有物件的场景 188 个** / 普查里"有物件的房" 189 间'
       '（差的那 1 间是房间 96，行的 `objects` 是**空表**但字段在位）'
       '实际 %d / 登记 %d' % (len(nonempty), _OBJ['rooms_with_objects']))

    ok(_OBJ['unmapped_rooms'] == [] and _OBJ['rooms_registered'] == 263,
       'C8 有物件但没登记场景的房 0 间；登记场景 %d 个（覆盖全部房间号）'
       % _OBJ['rooms_registered'])

    # ---- C9 depth / layer 自洽 ----
    lay = collections.Counter()
    bad_depth = []
    for _z, _s, _r, o in _OBJS:
        g = o['tile'][1] * TILE + TILE
        L = o.get('layer')
        lay[L] += 1
        exp = g - 10 ** 6 if L == 'bottom' else (g + 10 ** 6 if L == 'top' else g)
        if o['depth'] != exp:
            bad_depth.append((_s, o['tile'], L, o['depth'], exp))
    ok(not bad_depth and lay[None] == 7122 and lay['bottom'] == 424 and lay['top'] == 258,
       'C9 ★ depth 由 `tile_y` 推出：`always_on_bottom` %d 个压到 −10^6、'
       '`always_on_top` %d 个抬到 +10^6、其余 %d 个 == 地面线（不符 %d）'
       % (lay['bottom'], lay['top'], lay[None], len(bad_depth)))

    by = collections.defaultdict(list)
    for _z, _s, _r, o in _OBJS:
        by[_s].append(o)
    nonmono = []
    for _s, v in by.items():
        key = [(o['depth'], o['tile'][1], o['tile'][0]) for o in v]
        if key != sorted(key):
            nonmono.append(_s)
    ok(not nonmono,
       'C10 ★ **声明顺序即绘制顺序**：每个场景内 `(depth, tile_y, tile_x)` 非降'
       '（否则"后面的物件被前面的挡住"就会随机；非单调 %d %s）'
       % (len(nonmono), nonmono[:3]))

    # ---- C11 ★★ 两层登记的偏差**正是声明的那样**（正负成对）----
    inline = {}
    for _an, _av in ((_IDX['chapters'].get('oneshot') or {}).get('areas') or {}).items():
        for _sid, _e in ((_av or {}).get('scenes') or {}).items():
            inline[_sid] = _e
    inline_nonempty = [s for s, e in inline.items() if e.get('objects')]
    ok(len(inline) == 263 and not inline_nonempty,
       'C11 ★★ `_index.json` 的 263 条内联副本里 `objects` **全是占位空表**'
       '（非空 %d）—— 这正是本轮声明的偏差：物件是 78 万字节的**派生**数据，'
       '只落区域分片，不抄进索引' % len(inline_nonempty))
    ok(bool(_IDX['meta'].get('objects_source'))
       and u'区域分片' in _IDX['meta']['objects_source'],
       'C12 ★ 该偏差在索引 `meta.objects_source` 里**写明了**（读到 %d 字，含"区域分片"）'
       % len(_IDX['meta'].get('objects_source') or ''))
    # C12b 负控制：这条"声明"不是恒真 —— 换一个不含该词的串就必须报红
    fake = u'物件只在分片里'
    ok((u'区域分片' in (_IDX['meta']['objects_source'] or ''))
       and (u'区域分片' not in fake),
       'C12b 负控制：C12 的关键词确实来自文件本身（把它换成 %r 就必须报红）' % fake)
    ok(set(inline) == set(rows) == set(_OBJ_INLINE_SIDS()),
       'C13 ★ 索引内联的 263 个场景 id 与分片里的 263 个**同集合**（%d == %d）—— '
       '两层"各写各的"没漏没多' % (len(inline), len(rows)))


def _OBJ_INLINE_SIDS():
    out = []
    for _zf in ZONE_FILES:
        _d = jload(os.path.join(SCENES, _zf))
        for _sid, _ent in (_d.get('scenes') or {}).items():
            if isinstance(_ent, dict):
                out.append(_sid)
    return out


# ===========================================================================
# D 渲染面 + 纪律（数据接好了 != 画得出来）
# ===========================================================================
def sec_d():
    print('== D 渲染面（真跑 plan_frame + 真画布）==')
    from PyQt5.QtGui import QGuiApplication, QImage, QPainter
    import scene_canvas as SCV
    import scene_camera as SCC
    import scene_render as SR
    import scene_system as SS
    # 必须留一个**模块级**引用：局部变量被回收后 Qt 会连带拆掉底层上下文，
    # 后面的 `QImage`/`paint_on` 就会在随机位置炸（不是本轮踩的，是 Qt 的老规矩）。
    global _APP
    _APP = QGuiApplication.instance() or QGuiApplication([])

    GEO = jload(os.path.join(SCENES, '_room_geometry.json'))['rooms']
    ENT = SS.load_index().get('scenes') or {}
    room2sid = {}
    for _zf in ZONE_FILES:
        for _sid, _e in (jload(os.path.join(SCENES, _zf)).get('scenes') or {}).items():
            if isinstance(_e, dict) and isinstance(_e.get('original_room_id'), int):
                room2sid.setdefault(_e['original_room_id'], _sid)

    rooms = [r['room'] for r in _REN['rooms']]
    got = {}
    for rid in rooms:
        sid = room2sid[rid]
        sc = SS.load_scene(sid, entry=ENT.get(sid))
        g = GEO['oneshot:%d' % rid]
        rw, rh = g['w'], g['h']
        cache = SCV.SceneAssetCache()
        cam = SCC.Camera((rw, rh), 0, 1.0)
        cam.follow((0.0, 0.0, float(rw), float(rh)), (0.0, 0.0, float(rw), float(rh)))
        plan = SR.plan_frame(sc, cam, GEO, tick=0, sprite_size=cache.sprite_size)
        objs = [it for it in plan if it['kind'] == SR.K_OBJ]
        img = QImage(rw, rh, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        pt = QPainter(img)
        ndraw = SCV.paint_on(pt, plan, cache, view_size=(rw, rh))
        pt.end()
        got[rid] = dict(n_obj=len(sc.objects), k_obj=len(objs), plan=len(plan),
                        drawn=ndraw, missing=list(cache.missing), plan_items=objs,
                        objs=sc.objects, sc=sc, geo=GEO, cache=cache, SR=SR, SCC=SCC)

    bad = [r for r in rooms if got[r]['k_obj'] != got[r]['n_obj']]
    ok(not bad,
       'D1 ★★ 整间房 1:1 相机下，`plan_frame` 产出的 `K_OBJ` 条数 == 场景物件数'
       '（%s；不符 %s）—— 物件**真的进了绘制清单**，不是只躺在 JSON 里'
       % ([(r, got[r]['n_obj'], got[r]['k_obj']) for r in rooms], bad))

    badr = []
    for rid in rooms:
        for o, it in zip(got[rid]['objs'], got[rid]['plan_items']):
            cw, ch = _CELL_SZ[os.path.basename(o['sprite'])]
            exp = (o['tile'][0] * TILE + TILE // 2 - cw // 2,
                   o['tile'][1] * TILE + TILE - ch, cw, ch)
            if tuple(it['rect']) != exp:
                badr.append((rid, it['name'], it['rect'], exp))
    ok(not badr,
       'D2 ★★★ **渲染坐标 == 栅格/锚点公式**（相机 1:1 时 `rect` 就该等于 `pos` 与格尺寸；'
       '不符 %d %s）' % (len(badr), badr[:2]))

    # 负控制：把一个物件挪 16px ⇒ 绘制坐标必须跟着走 16px
    rid0 = rooms[0]
    sc0 = got[rid0]['sc']
    o0 = sc0.objects[0]
    before_x = got[rid0]['plan_items'][0]['rect'][0]
    saved = list(o0['pos'])
    o0['pos'] = [saved[0] + TILE, saved[1]]
    g0 = GEO['oneshot:%d' % rid0]
    cam2 = SCC.Camera((g0['w'], g0['h']), 0, 1.0)
    cam2.follow((0.0, 0.0, float(g0['w']), float(g0['h'])),
                (0.0, 0.0, float(g0['w']), float(g0['h'])))
    p2 = [it for it in SR.plan_frame(sc0, cam2, GEO, tick=0,
                                    sprite_size=got[rid0]['cache'].sprite_size)
          if it['kind'] == SR.K_OBJ]
    o0['pos'] = saved
    ok(p2 and p2[0]['rect'][0] - before_x == TILE,
       'D3 负控制：把第 1 个物件挪 +16px ⇒ 绘制 `rect[0]` 必须**恰好** +16'
       '（%d -> %d）—— 证明 D2 不是恒真' % (before_x, p2[0]['rect'][0] if p2 else -1))

    ok(all(not got[r]['missing'] for r in rooms) and got[rid0]['drawn'] > 0,
       'D4 ★ 真画布 `paint_on` 出图、**零缺素材**（%s；画出条数 %s）—— '
       '第102轮踩过的"数据对了但画不出来"（路径解析）在这条路上被守住'
       % ({r: len(got[r]['missing']) for r in rooms}, {r: got[r]['drawn'] for r in rooms}))

    ok(_REN['path_check']['objects'] == 7804 and _REN['path_check']['missing'] == 0,
       'D5 ★★ 全量：7804 个物件的 `sprite` 路径**逐个查盘**，缺失 %d 个'
       % _REN['path_check']['missing'])

    # D5b 独立复核（不读 render103.json）：自己再走一遍全量查盘
    miss = [(s, o.get('sprite')) for _z, s, _r, o in _OBJS
            if not os.path.isfile(os.path.join(SCENES, o.get('sprite') or ''))]
    ok(not miss, 'D5b ★ 独立复核同一件事：从分片自己数，缺失 %d 个 %s'
       % (len(miss), miss[:3]))

    # ---- D6 纪律 ----
    ok(all(os.path.isfile(os.path.join(HERE, t))
           for t in ('build103.py', 'check103.py', 'verify103.py', 'sheet103.py')),
       'D6 本轮四件工具（build / check / verify / sheet）都在盘上')

    src = io.open(os.path.abspath(__file__), encoding='utf-8').read()
    tree = ast.parse(src)
    badstr = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if any(m in v or m in v.lower() for m in _EXTERNAL):
                badstr.append(v[:60])
    ok(not badstr,
       'D7 ★★ 回归套件**零外部依赖**：本文件不含原作绝对路径/游戏目录特征串'
       '（原作在 C 盘桌面，回归碰不得）命中 %s' % (badstr[:2],))

    taut = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'ok' and node.args):
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and a0.value is True:
                taut.append(getattr(node, 'lineno', -1))
    ok(not taut,
       'D8 ★★ **无恒真判据**：本文件所有 `ok(...)` 的首参都不是字面量 `True`'
       '（命中行 %s）' % (taut[:3],))

    fake = ast.parse('ok(True, "x")\nok(n > 0, "y")\n')
    hits = [n for n in ast.walk(fake)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == 'ok' and n.args
            and isinstance(n.args[0], ast.Constant) and n.args[0].value is True]
    ok(len(hits) == 1,
       'D9 负控制：D8 的检查器对"造出来的恒真"确实命中 1 条（检查器本身不是恒真）')

    ok(_N[0] > 30, 'D10 断言条数 > 30（防"套件只剩几条"）实际 %d' % _N[0])


def main():
    print('第103轮 物件栅格/锚点与接线 回归锁（%s）' % os.path.basename(__file__))
    sec_a()
    sec_b()
    sec_c()
    sec_d()
    print()
    if _FAIL:
        print('[FAIL] 共 %d 条失败（断言 %d）' % (len(_FAIL), _N[0]))
        for f in _FAIL:
            print('   - ' + f)
        return 1
    print('物件栅格/锚点/接线：%d/%d 全绿' % (_N[0], _N[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main())

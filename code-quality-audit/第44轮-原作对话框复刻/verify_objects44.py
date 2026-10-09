# -*- coding: utf-8 -*-
"""第44轮续：场景 objects 补全不许静默漂移。

为什么必须有这个锁
------------------
`objects` 是**程序化生成的数据**（615 个场景、3,197 条物件是从原作实例普查
换算来的）。这类产物最典型的失败模式是"某天悄悄变了个值/少了一批"，
而 `run_all.py` 的 IDENTICAL 判据只比对**判据输出文本** —— 数据本身变了
只要判据还是绿的，就没人知道。所以判据必须**直接把数据当事实来断言**。

★ 数据源随第68轮升级（本文件第 5 次大改）
----------------------------------------
第44轮最初的数据是**第42轮 ch1 单表普查**（`inst42.json` 一系 + `objmap43.txt`）。
第68轮把普查扩到**五章**并**按章取对象表**（`inst68 ⊇ inst42`，逐条 0 漂移），
产物随之从 2,043 条 → **3,197 条**、532 场景 → **615 场景**。
⇒ 本锁的数据源与期望值一并升级；**旧常量留在原地会让判据站到事实的对立面**
（这正是第48轮 E3 踩过的坑）。核心鉴别力（A 结构 / B 锚点 / C 守恒 / D 负控制）
一条没少。

判据分四段：

  A 结构不变量（对所有场景普适，不看具体数字）
     · 每条 object 必有 `pos`（2 个 int）与 `sprite`（非空 str）
     · `sprite` 必须指向 `objs/` 下**真实存在的文件**（这是"能画出来"的唯一保证）
     · 不得再有 `why_objects_is_empty` 这种**过期假话**注释

  B 真值锚点（具体场景的具体内容，来自原作普查，可回查）
     · ch1:2 krisroom（独立文件载体）：**门/标记集合**精确 = doorA(155,230) + markerB(155,185)
     · ch1:3 krishallway（分片载体）：**门/标记集合**精确 = doorB/markerA/doorC/markerD
     · 两条锚点**分别覆盖两种载体** —— 只写分片的 bug 会被立刻抓到
     · ★ 第68轮补采给这两间房各加了若干 `obj_readable_room1`（原作事实）⇒
       总数**不再锁死**（`>= 原锚点数`），但"门/标记集合"仍是**精确**断言
       —— 锚点的鉴别力落在集合上，不落在"恰好 N 条"这个会随扩容而变的形态上

  C 覆盖与守恒
     · 带 objects 的场景数 == 537（分片）+ 79（独立文件）= 616
     · 全场景 objects 总条数 == 3,197（原作可绘制实例数）+ 桌面世界门数
       （★ 第99轮起桌面门数从 `desktop.json` 现读，不再写死：第89轮 +8、第99轮 +1）
     · ★ 全量守恒：**场景里的 objects 总条数** 必须 == **普查里能映射到 sprite 的实例数**
       + 桌面世界门（这条是"没漏没多"的核心判据；判据自己从三源重算，不信生成器自报）

  D 负控制（证明判据有鉴别力）
     · 编一个不存在的 sprite 名，必须判为"文件不存在"
     · 找一个普查缺席的房间，其 objects 必须是 `[]` 且**存在键**
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')          # = 仓库根
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
OBJS = os.path.join(SCENES, 'objs')
#: 第68轮普查（**当前数据源**：五章、含可交互类）。
EV68 = os.path.join(ROOT, 'code-quality-audit', '第68轮-可交互道具实例补采', '_evidence')
#: 第43轮对象表（五章各一张；第68轮起按章取表）。
E43 = os.path.join(ROOT, 'code-quality-audit', '第43轮-原作门与相机取证', '_evidence')

INST68 = {'ch1': 'inst68.json', 'ch2': 'ch2_inst68.json', 'ch3': 'ch3_inst68.json',
          'ch4': 'ch4_inst68.json', 'ch5': 'ch5_inst68.json'}
OBMAP = {'ch1': 'objmap43.txt', 'ch2': 'chapter2_objmap43.txt',
         'ch3': 'chapter3_objmap43.txt', 'ch4': 'chapter4_objmap43.txt',
         'ch5': 'chapter5_objmap43.txt'}

#: 期望总条数（= 可绘制实例数，**只统计已登记为场景的房间**）。
#   ★ 为什么不是"普查里的全部实例"：普查里有若干房间**产品没登记为场景**
#     （room_school_unusedroom ×5 / room_man / room_title_placeholder /
#      room_floortex_test 等原作废案或测试房），它们的实例不该出现在任何场景里。
#     判据跟着"已登记"这个口径才正确（见 `_registered_scene_rooms`）。
#   ★ 第68轮补采（五章 + 可交互类）后，由 2,043 → **3,197**；两条锚点房间各加了
#     若干 `obj_readable_room1` —— 均为**原作事实**（等价性见 verify_items68 A1）。
EXPECT_TOTAL_ORIGINAL = 3197
EXPECT_ZONE_WITH_OBJ = 537
EXPECT_FILE_WITH_OBJ = 79


def _desktop_doors():
    """桌面世界门数 —— **从 `desktop.json` 现读**（★ 第99轮起不再写死）。

    ★★ 第89轮增量（**显式记账**，不写裸魔数）：desktop.json 挂了世界门
      （`obj_doorA~F/W/X/Y` → ch1..ch5 / ut / uty / oneshot / outertale），
      这是用户口径「先能让我看到场景可以切换」＋「那几个世界的入口……你记得
      添上」的直接落地。
        · 场景数 615 → **616**（desktop 从"零 objects"变成"有 objects"）
        · 条数   3197 → **3205**（第89轮 +8）/ **3206**（第99轮再 +1 = Outertale）
    ★★ 第99轮：这里原先是写死的 `DESKTOP_DOORS = 8`。加第 9 扇门时它立刻成了
      "判据与事实脱节"的样本（C2/C3 双双报红）。改成**现读**后语义更准：
      `原作重算 + 桌面**实际声明**的门数 == 产品 objects 总数` ——
      桌面端改了门数这里自动跟上；而"声明了却没进产品"仍会报红（鉴别力不丢）。
      ★ 读不到就返 0 ⇒ 后面两条守恒必然报红（**故意不吞异常**）。
    """
    try:
        with io.open(os.path.join(SCENES, 'desktop.json'), 'r',
                     encoding='utf-8') as fh:
            return len((json.load(fh).get('objects')) or [])
    except Exception:
        return 0


DESKTOP_DOORS = _desktop_doors()
EXPECT_TOTAL = EXPECT_TOTAL_ORIGINAL + DESKTOP_DOORS

RE_ZONE = re.compile(r'^_zone\.(ch\d+)\.')

PASS = 0
FAIL = 0


def ok(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('[PASS] %s' % msg)
    else:
        FAIL += 1
        print('[FAIL] %s' % msg)


def load(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def main():
    print('== A 结构不变量 ==')
    obj_files = set(os.listdir(OBJS)) if os.path.isdir(OBJS) else set()
    ok(len(obj_files) >= 25, 'A1 objs/ 素材目录存在且有 %d 个文件' % len(obj_files))

    zone_files = sorted(f for f in os.listdir(SCENES)
                        if f.startswith('_zone.') and f.endswith('.json'))
    # ★ 第77轮改：原来是 `== 61`（Deltarune 分片数）。UT/黄魂 第77轮迁入后
    #   多了 `_zone.ut.rooms.json` / `_zone.uty.rooms.json` ⇒ 63。
    #   判据**本意**是"分片载体真在盘上"，故改成下界（加作品不误报，
    #   而"分片被误删"照样报红）。
    ok(len(zone_files) >= 61, 'A2 分片文件 %d 个' % len(zone_files))

    # 收集全部场景 objects
    all_objs = []          # [(sprite, pos, src, 来源标签)]
    scenes_with_obj = 0
    zone_with_obj = 0
    file_with_obj = 0
    bad_shape = []
    missing_sprite = []
    stale_comment = []

    def scan_scene(raw, label):
        nonlocal scenes_with_obj, zone_with_obj, file_with_obj
        objs = raw.get('objects')
        if not isinstance(objs, list):
            return
        if objs:
            scenes_with_obj += 1
            if label.startswith('zone'):
                zone_with_obj += 1
            else:
                file_with_obj += 1
        for o in objs:
            if not isinstance(o, dict):
                bad_shape.append((label, o))
                continue
            pos = o.get('pos')
            spr = o.get('sprite')
            if not (isinstance(pos, (list, tuple)) and len(pos) == 2
                    and all(isinstance(v, int) for v in pos)):
                bad_shape.append((label, 'pos', o))
            if not (isinstance(spr, str) and spr.strip()):
                bad_shape.append((label, 'sprite', o))
            else:
                fn = os.path.basename(spr)
                if fn not in obj_files:
                    missing_sprite.append((label, spr))
            all_objs.append((spr, pos, o.get('src'), label))

    for zf in zone_files:
        d = load(os.path.join(SCENES, zf))
        t = d.get('scenes') if isinstance(d, dict) and 'scenes' in d else {}
        for sid, raw in (t or {}).items():
            if isinstance(raw, dict):
                scan_scene(raw, 'zone:%s' % zf)

    for f in sorted(os.listdir(SCENES)):
        if not f.endswith('.json') or f.startswith('_'):
            continue
        if RE_ZONE.match(f):
            continue
        p = os.path.join(SCENES, f)
        try:
            d = load(p)
        except Exception:
            continue
        if not isinstance(d, dict) or 'scene_id' not in d:
            continue
        scan_scene(d, 'file:%s' % f)
        cm = d.get('_comment')
        if isinstance(cm, dict) and 'why_objects_is_empty' in cm:
            stale_comment.append(f)

    ok(not bad_shape, 'A3 所有 object 形状合法（pos=2×int / sprite=非空 str）坏=%d'
       % len(bad_shape))
    if bad_shape:
        for b in bad_shape[:5]:
            print('       坏样本: %r' % (b,))
    ok(not missing_sprite, 'A4 所有 sprite 指向 objs/ 下真实文件 缺=%d'
       % len(missing_sprite))
    if missing_sprite:
        for m in missing_sprite[:5]:
            print('       缺样本: %r' % (m,))
    ok(not stale_comment, 'A5 无过期的 why_objects_is_empty 假话注释 余=%d'
       % len(stale_comment))
    if stale_comment:
        print('       残留: %s' % stale_comment[:5])

    print('')
    print('== B 真值锚点（两种载体各一）==')
    # B1 独立文件载体：ch1.kris_room.kris_s_room
    # ★ 第68轮补采后该房间多了若干 `obj_readable_room1`（原作事实）⇒ 总数不再锁死 2；
    #   改为「总数 >= 2」+「**门/标记集合**精确等于两条已知真值」。
    fp = os.path.join(SCENES, 'ch1.kris_room.kris_s_room.json')
    d1 = load(fp)
    o1 = d1.get('objects')
    ok(isinstance(o1, list) and len(o1) >= 2,
       'B1a ch1:2 krisroom（独立文件）objects >= 2 实际=%s'
       % (len(o1) if isinstance(o1, list) else o1))
    if isinstance(o1, list):
        got = sorted((o.get('src'), tuple(o.get('pos'))) for o in o1
                     if str(o.get('src') or '').startswith(('obj_door', 'obj_marker')))
        want = sorted([('obj_doorA', (155, 230)), ('obj_markerB', (155, 185))])
        ok(got == want, 'B1b ch1:2 门/标记集合与原作普查一致（doorA(155,230)+markerB(155,185)）实际=%s' % (got,))

    # B2 分片载体：ch1:3 krishallway
    dz = load(os.path.join(SCENES, '_zone.ch1.home.json'))
    tz = dz.get('scenes') or {}
    o3 = None
    for sid, raw in tz.items():
        if isinstance(raw, dict) and raw.get('original_room_id') == 3:
            o3 = raw.get('objects')
    ok(isinstance(o3, list) and len(o3) >= 4,
       'B2a ch1:3 krishallway（分片）objects >= 4 实际=%s'
       % (len(o3) if isinstance(o3, list) else o3))
    if isinstance(o3, list):
        got3 = sorted((o.get('src'), tuple(o.get('pos'))) for o in o3
                      if str(o.get('src') or '').startswith(('obj_door', 'obj_marker')))
        want3 = sorted([('obj_doorB', (289, 104)), ('obj_markerA', (289, 112)),
                        ('obj_doorC', (425, 100)), ('obj_markerD', (426, 118))])
        ok(got3 == want3, 'B2b ch1:3 门/标记集合与原作普查一致 实际=%s' % (got3,))

    print('')
    print('== C 覆盖与守恒 ==')
    # ★ 数据源在位（防"读不到 ⇒ 空表 ⇒ 独立算 0"这种**失去鉴别力**的假绿；
    #   同时让"缺了哪个文件"一眼可见，而不是只看到 C3 的数字对不上）。
    miss_src = [fn for fn in INST68.values()
                if not os.path.isfile(os.path.join(EV68, fn))]
    miss_tbl = [fn for fn in OBMAP.values()
                if not os.path.isfile(os.path.join(E43, fn))]
    ok(not miss_src and not miss_tbl,
       'C0 数据源在位：第68轮普查 缺=%s / 按章对象表 缺=%s'
       % (miss_src or '无', miss_tbl or '无'))
    ok(scenes_with_obj == EXPECT_ZONE_WITH_OBJ + EXPECT_FILE_WITH_OBJ,
       'C1 带 objects 的场景数 == %d（分片 %d + 独立 %d）实际=%d'
       % (EXPECT_ZONE_WITH_OBJ + EXPECT_FILE_WITH_OBJ, EXPECT_ZONE_WITH_OBJ,
          EXPECT_FILE_WITH_OBJ, scenes_with_obj))
    ok(len(all_objs) == EXPECT_TOTAL,
       'C2 ★守恒：objects 总条数 == 原作 %d + 桌面世界门 %d = %d 实际=%d'
       % (EXPECT_TOTAL_ORIGINAL, DESKTOP_DOORS, EXPECT_TOTAL, len(all_objs)))

    # C3 独立重算：从**第68轮普查 + 按章对象表 + objs/** 三个真源重算期望值，
    #    必须与场景里的一致。这是"判据不依赖生成器自报"的关键 —— 判据自己算一遍。
    #    ★ 第89轮：重算只覆盖**原作房间**；桌面世界门是产品侧新增
    #      （桌面不属于任何原作房间，`original_room_id=-1`）⇒ 期望 = 重算 + 桌面门数。
    #      两边都要动才自洽：只改常量不改重算会让 C3 报红（鉴别力正确）。
    #    ★★ 第99轮：`DESKTOP_DOORS` 改为从 `desktop.json` **现读** ⇒
    #      语义 = 「原作重算 + 桌面实际声明 == 产品总数」，加门不用再改这里。
    expect = _recount_expected(obj_files) + DESKTOP_DOORS
    ok(expect > 0 and expect == len(all_objs),
       'C3 ★判据独立重算（第68轮普查×按章对象表×objs 三源 + desktop %d 扇门）== 实得 独立算=%d 实得=%d'
       % (DESKTOP_DOORS, expect, len(all_objs)))

    print('')
    print('== D 负控制（证明判据有鉴别力）==')
    ok('spr_this_does_not_exist_zzz_0.png' not in obj_files,
       'D1 负控制：编造的 sprite 名不在 objs/（A4 会对它报红）')
    # 普查缺席房间 → objects == [] 且键存在
    dz2 = load(os.path.join(SCENES, '_zone.ch1.home.json'))
    tz2 = dz2.get('scenes') or {}
    found_empty = None
    for sid, raw in tz2.items():
        if isinstance(raw, dict) and raw.get('original_room_id') == 4:
            found_empty = raw
    if found_empty is not None:
        ok(found_empty.get('objects') == [] and 'objects' in found_empty,
           'D2 负控制：普查缺席的 ch1:4 objects == [] 且键存在')
    else:
        ok(False, 'D2 负控制：找不到 ch1:4 用于验证')

    print('')
    print('合计：PASS=%d FAIL=%d' % (PASS, FAIL))
    return 1 if FAIL else 0


def _registered_scene_rooms():
    """索引里每个**已登记场景**的 `(章, 原作房间id)`（★保留重复：一个房间可对应多个场景）。

    ★ 口径为什么按「场景」而不是按「房间去重」：生成器是**逐场景**写 objects 的
      （分片遍历 sid、独立文件遍历 entry）。若某房间被登记成两个场景，产物里就有
      两份条数。判据若按房间去重会少算 ⇒ 报假 FAIL。这里与生成器口径对齐。
    ★ 为什么要过滤（第44轮实测）：普查覆盖 963 个房间，但产品只把其中一部分
      登记成了场景（PLACE_* / 测试房 / 废案房不登记）。用"普查全量"当期望
      ⇒ 恒多出一批（未登记房间的可绘制实例），报假 FAIL。
    """
    idx = load(os.path.join(SCENES, '_index.json'))
    out = []
    for ch, blk in (idx.get('chapters') or {}).items():
        if not isinstance(blk, dict):
            continue
        for area, ablk in (blk.get('areas') or {}).items():
            if not isinstance(ablk, dict):
                continue
            for sid, entry in (ablk.get('scenes') or {}).items():
                if not isinstance(entry, dict):
                    continue
                rid = entry.get('original_room_id')
                if isinstance(rid, int):
                    out.append((ch, rid))
    return out


def _parse_objmap(path):
    """`objmap43.txt` 一系的解析：`obj名 → spr_名`（无 spr 记 None）。

    ★ 文件缺失 ⇒ 返回空表（**不抛**）：让 C0 报"数据源缺"、C3 报"独立算对不上"，
      而不是在重算中途抛 FileNotFoundError 把 C3 那行整个吃掉
      （第68轮体检实测：缺 ch1 普查时 C3 根本没打印 ⇒ 只报 {'C0'} 而非 {'C0','C3'}）。
    """
    if not os.path.isfile(path):
        return {}
    out = {}
    with io.open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            name = parts[1].strip()
            m = re.search(r'spr=([^\t]*)', line)
            if name:
                out[name] = m.group(1).strip() if m and m.group(1).strip() else None
    return out


def _load_inst_rooms(path):
    """一个章普查文件 → `{房间id: [实例, ...]}`。★ 文件缺失 ⇒ 空表（不抛，见上）。"""
    if not os.path.isfile(path):
        return {}
    d = load(path)
    out = {}
    for rec in (d.get('rooms') or []):
        rid = rec.get('index')
        if isinstance(rid, int):
            out[rid] = rec.get('insts') or []
    return out


def _recount_expected(obj_files):
    """从**第68轮**普查 + **按章**对象表 + objs/ 三源独立重算「应该有多少条 objects」。

    ★ 为什么判据要自己重算而不是信生成器自报的 3,197：
      "生成器说它写了 3,197 条"和"场景里真有 3,197 条"是两件事。
      判据独立重算 = 唯一能抓到"生成器少写了一批"的办法
      （本项目最贵的坑之一："函数写对了不等于产品用上了"）。
    ★ 与生成器 `gen_objects68.object()` 的**过滤条件等价**（不读产物）：
      `objmap[ch][obj]` 非空 且 objs/ 里有该 spr 的帧文件 且 x/y 是 int。
    """
    # objs/ 里的 sprite 基名集合
    spr_keys = set()
    for f in obj_files:
        m = re.match(r'^(.*)_(\d+)\.png$', f)
        spr_keys.add(m.group(1) if m else f[:-4])
    # 按章对象表 + 按章普查
    objmaps = {ch: _parse_objmap(os.path.join(E43, fn)) for ch, fn in OBMAP.items()}
    inst_by_ch = {ch: _load_inst_rooms(os.path.join(EV68, fn))
                  for ch, fn in INST68.items()}
    n = 0
    for ch, rid in _registered_scene_rooms():
        for it in (inst_by_ch.get(ch, {}).get(rid) or []):
            nm = it.get('obj')
            x, y = it.get('x'), it.get('y')
            if not nm or not isinstance(x, int) or not isinstance(y, int):
                continue
            spr = objmaps.get(ch, {}).get(nm)
            if spr and spr in spr_keys:
                n += 1
    return n


if __name__ == '__main__':
    sys.exit(main())

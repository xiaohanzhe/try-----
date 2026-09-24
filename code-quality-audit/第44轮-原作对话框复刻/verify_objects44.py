# -*- coding: utf-8 -*-
"""第44轮续：场景 objects 补全不许静默漂移。

为什么必须有这个锁
------------------
`objects` 是**程序化生成的数据**（503 个场景、2,067 条物件是从原作实例普查
换算来的）。这类产物最典型的失败模式是"某天悄悄变了个值/少了一批"，
而 `run_all.py` 的 IDENTICAL 判据只比对**判据输出文本** —— 数据本身变了
只要判据还是绿的，就没人知道。所以判据必须**直接把数据当事实来断言**。

判据分四段：

  A 结构不变量（对所有场景普适，不看具体数字）
     · 每条 object 必有 `pos`（2 个 int）与 `sprite`（非空 str）
     · `sprite` 必须指向 `objs/` 下**真实存在的文件**（这是"能画出来"的唯一保证）
     · 不得再有 `why_objects_is_empty` 这种**过期假话**注释

  B 真值锚点（具体场景的具体内容，来自原作普查，可回查）
     · ch1:2 krisroom（独立文件载体）= 2 条：doorA(155,230) + markerB(155,185)
     · ch1:3 krishallway（分片载体）= 4 条：doorB/markerA/doorC/markerD
     · 两条锚点**分别覆盖两种载体** —— 只写分片的 bug 会被立刻抓到

  C 覆盖与守恒
     · 带 objects 的场景数 == 455（分片）+ 77（独立文件），与生成器自报一致
     · 全场景 objects 总条数 == 2,067（== 可绘制实例数）
     · ★ 全量守恒：**场景里的 objects 总条数** 必须 == **普查里能映射到 sprite 的实例数**
       （这条是"没漏没多"的核心判据）

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
E42 = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')

#: 期望总条数（= 可绘制实例数，**只统计已登记为场景的房间**）。
#   ★ 为什么不是 2067：普查里有 8 个房间**产品没登记为场景**
#     （room_school_unusedroom ×5 / room_man / room_title_placeholder /
#      room_floortex_test —— 原作废案或测试房），它们的 24 条实例
#     不该出现在任何场景里。判据跟着"已登记"这个口径才正确。
EXPECT_TOTAL = 2043
EXPECT_ZONE_WITH_OBJ = 455
EXPECT_FILE_WITH_OBJ = 77

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
    ok(len(zone_files) == 61, 'A2 分片文件 %d 个' % len(zone_files))

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
    fp = os.path.join(SCENES, 'ch1.kris_room.kris_s_room.json')
    d1 = load(fp)
    o1 = d1.get('objects')
    ok(isinstance(o1, list) and len(o1) == 2,
       'B1a ch1:2 krisroom（独立文件）objects == 2 实际=%s'
       % (len(o1) if isinstance(o1, list) else o1))
    if isinstance(o1, list) and len(o1) == 2:
        got = sorted((o.get('src'), tuple(o.get('pos'))) for o in o1)
        want = sorted([('obj_doorA', (155, 230)), ('obj_markerB', (155, 185))])
        ok(got == want, 'B1b ch1:2 内容与原作普查一致（doorA(155,230)+markerB(155,185)）实际=%s' % (got,))

    # B2 分片载体：ch1:3 krishallway
    dz = load(os.path.join(SCENES, '_zone.ch1.home.json'))
    tz = dz.get('scenes') or {}
    o3 = None
    for sid, raw in tz.items():
        if isinstance(raw, dict) and raw.get('original_room_id') == 3:
            o3 = raw.get('objects')
    ok(isinstance(o3, list) and len(o3) == 4,
       'B2a ch1:3 krishallway（分片）objects == 4 实际=%s'
       % (len(o3) if isinstance(o3, list) else o3))
    if isinstance(o3, list) and len(o3) == 4:
        got3 = sorted((o.get('src'), tuple(o.get('pos'))) for o in o3)
        want3 = sorted([('obj_doorB', (289, 104)), ('obj_markerA', (289, 112)),
                        ('obj_doorC', (425, 100)), ('obj_markerD', (426, 118))])
        ok(got3 == want3, 'B2b ch1:3 内容与原作普查一致 实际=%s' % (got3,))

    print('')
    print('== C 覆盖与守恒 ==')
    ok(scenes_with_obj == EXPECT_ZONE_WITH_OBJ + EXPECT_FILE_WITH_OBJ,
       'C1 带 objects 的场景数 == %d（分片 %d + 独立 %d）实际=%d'
       % (EXPECT_ZONE_WITH_OBJ + EXPECT_FILE_WITH_OBJ, EXPECT_ZONE_WITH_OBJ,
          EXPECT_FILE_WITH_OBJ, scenes_with_obj))
    ok(len(all_objs) == EXPECT_TOTAL,
       'C2 ★守恒：objects 总条数 == 可绘制实例数 %d 实际=%d'
       % (EXPECT_TOTAL, len(all_objs)))

    # C3 独立重算：从普查 + objmap + objs/ 三个真源重算期望值，必须与场景里的一致。
    #    这是"判据不依赖生成器自报"的关键 —— 判据自己算一遍。
    expect = _recount_expected(obj_files)
    ok(expect == len(all_objs),
       'C3 ★判据独立重算（普查×objmap×objs 三源）== 实得 独立算=%d 实得=%d'
       % (expect, len(all_objs)))

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


def _registered_rooms():
    """索引里**已登记为场景**的 `(章, 原作房间id)` 集合。

    ★ 判据必须用它过滤期望集：普查覆盖 963 个房间，但产品只把其中一部分
      登记成了场景（PLACE_* / 测试房 / 废案房不登记）。用"普查全量"当期望
      ⇒ 恒多出 24 条（8 个未登记房间的可绘制实例），报假 FAIL。
      第 44 轮实测现场：期望 2067 vs 实得 2043，差 24 ——
      差的正是 room_school_unusedroom×5 / room_man / room_title_placeholder /
      room_floortex_test 这 8 个**原作废案或测试房**（产品有意不登记）。
    """
    idx = load(os.path.join(SCENES, '_index.json'))
    out = set()
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
                    out.add((ch, rid))
    return out


def _recount_expected(obj_files):
    """从三个真源独立重算「应该有多少条 objects」（**限已登记场景的房间**）。

    ★ 为什么判据要自己重算而不是信生成器自报的 2043：
      "生成器说它写了 2043 条"和"场景里真有 2043 条"是两件事。
      判据独立重算 = 唯一能抓到"生成器少写了一批"的办法
      （本项目最贵的坑之一："函数写对了不等于产品用上了"）。

    ★ 为什么要 `_registered_rooms()` 过滤：见该函数文档。
    """
    inst = {'ch1': 'inst42.json', 'ch2': 'ch2_inst42.json', 'ch3': 'ch3_inst42.json',
            'ch4': 'ch4_inst42.json', 'ch5': 'ch5_inst42.json'}
    reg = _registered_rooms()
    # objmap
    objmap = {}
    objmap_path = os.path.join(ROOT, 'code-quality-audit', '第43轮-原作门与相机取证',
                               '_evidence', 'objmap43.txt')
    with io.open(objmap_path, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            nm = parts[1].strip()
            m = re.search(r'spr=([^\t]*)', line)
            if nm:
                objmap[nm] = m.group(1).strip() if m and m.group(1).strip() else None
    # objs/ 里有哪些 sprite 前缀
    spr_keys = set()
    for f in obj_files:
        m = re.match(r'^(.*)_(\d+)\.png$', f)
        spr_keys.add(m.group(1) if m else f[:-4])
    n = 0
    for ch, fn in inst.items():
        p = os.path.join(E42, fn)
        if not os.path.exists(p):
            continue
        with io.open(p, 'r', encoding='utf-8') as fh:
            d = json.load(fh)
        for rec in (d.get('rooms') or []):
            rid = rec.get('index')
            if (ch, rid) not in reg:
                continue
            for it in (rec.get('insts') or []):
                nm = it.get('obj')
                x, y = it.get('x'), it.get('y')
                if not nm or not isinstance(x, int) or not isinstance(y, int):
                    continue
                spr = objmap.get(nm)
                if spr and spr in spr_keys:
                    n += 1
    return n


if __name__ == '__main__':
    sys.exit(main())

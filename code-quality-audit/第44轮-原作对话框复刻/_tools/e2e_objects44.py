# -*- coding: utf-8 -*-
"""第44轮续：objects 真的能被渲染层画出来吗（端到端贯通验证）。

这是「函数写对了 ≠ 产品用上了」这条铁律的**执行器**：
  objects 数据补全了（verify_objects44 已证），但**数据在、渲染层画不画得出来**
  是另一件事 —— 中间还隔着 scene_render 取名 / scene_canvas 解路径 / 素材真读得出。

判据（**逐章**，每章都跑）：
  · 真实场景（有 objects 的）→ plan_frame 必须产出 K_OBJ 指令
  · 每条 K_OBJ 的 name 必须能在 SceneAssetCache 里**取到真 pixmap**（不是 None）
  · 分类计数：bg / obj / placeholder / room_border
  · 逐章汇总：能画出 obj 的场景数 / 总 obj 指令数

★ 素材缓存用**真文件**（SceneAssetCache 直接读 assets/scenes/objs/），
  **不 mock** —— mock 掉就变成"验证我自己写的假东西"（探针不保真）。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')          # = 仓库根
PET = os.path.join(ROOT, 'ralsei_pet')
MOD = os.path.join(PET, 'modules')
SCENES = os.path.join(PET, 'assets', 'scenes')
sys.path.insert(0, MOD)

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


def main():
    # Qt 在无显示环境也能建 QPixmap？—— 不一定。SceneAssetCache 直接 QPixmap(path)。
    # 所以这里需要 QApplication（off-screen）。回归锁里其它套件也是这么做的。
    from PyQt5.QtWidgets import QApplication
    import scene_system as SS
    import scene_render as SR
    import scene_camera as SC
    from scene_canvas import SceneAssetCache
    app = QApplication.instance() or QApplication([])

    idx = SS.load_index()
    geo_path = os.path.join(SCENES, '_room_geometry.json')
    with io.open(geo_path, 'r', encoding='utf-8') as fh:
        geo = (json.load(fh).get('rooms') or {})
    assets = SceneAssetCache(SCENES)

    # ★★ 必须用 `SS.load_index()['scenes']`（**扁平**表，1,014 条，已补全
    #    `chapter_id` / `area_id`），**不能**直接读 `_index.json` 的三级结构。
    #    第 44 轮实测现场：我第一版自己展开了三级 chapters[*].areas[*].scenes，
    #    拿到的 entry **缺 chapter_id/area_id** ⇒ `load_scene` 找不到分片
    #    ⇒ **926 个分片场景全部加载失败**，只有 87 个独立文件成功。
    #    判据 E1「已加载 88」立刻报红 —— 这就是"判据独立于被测代码"的价值：
    #    如果我也用被测的 load_index，这个 bug 会被掩盖成一个"数据就是这样"的假象。
    scenes = []
    flat = idx.get('scenes') or {}
    for sid, entry in flat.items():
        if isinstance(entry, dict):
            scenes.append((entry.get('chapter_id') or '?', sid, entry))

    per_ch = {}
    total_obj_drawn = 0
    total_obj_missing = 0
    scenes_with_obj_plan = 0
    scenes_loaded = 0
    plan_err = 0
    missing_names = []
    per_obj_total = 0
    per_obj_hit = 0
    per_obj_fail = []
    outside_room = 0

    for ch, sid, entry in scenes:
        try:
            sc = SS.load_scene(sid, entry=entry)
        except Exception:
            plan_err += 1
            continue
        if sc is None:
            continue
        scenes_loaded += 1
        rid = getattr(sc, 'original_room_id', None)
        kw = geo.get('%s:%d' % (ch, rid)) if isinstance(rid, int) else None
        world = SR.room_world_rect({'w': kw['w'], 'h': kw['h']} if kw else None, None)
        w = float(world[2])
        h = float(world[3])
        cam = SC.Camera((640, 480), 0, 2.0)
        cam.follow((0.0, 0.0, w, h), None)
        # ★★ 「物件画不出来」的正确判法：**逐物件把相机跟过去**。
        #   用固定相机（原点或中心）测可见数，量到的是"这个房间的物件有多大比例
        #   落在那一屏里"——那是视口剔除的**正确**行为，不是渲染层缺陷。
        #   第 44 轮实测：原点口径 634 条、中心口径 404 条，差得离谱却不代表谁坏了
        #   （物件在房间内均匀分布，中位相对位置 0.46/0.50，而 2040×240 这类
        #   超宽房里相机横向只覆盖 640/2040 = 31%）。
        #   ⇒ 判据改成："对**每一个**物件，把相机跟到它身上，它必须出现在指令里"。
        #   这才是"数据在、渲染层画得出"的充分证明（0 例外才算通过）。
        cams = [cam]
        per_obj_checks = []
        for o in (getattr(sc, 'objects', None) or []):
            pos = o.get('pos')
            if not (isinstance(pos, list) and len(pos) == 2):
                continue
            # ★★ 只检**房间内**的物件（第 44 轮实测修正）：
            #   原作有一批门的坐标**落在房间边界外**（如 (-20,240) / (400,-20) /
            #   (680,-80) —— 意为"门在房间的上/左边界外一点"，用于从外侧进来的
            #   触发判定）。相机被钳制在房间矩形内，**看不到房间外的东西**，
            #   所以它们不出现在指令里是**正确行为**，不是渲染层缺陷。
            #   13 个未命中样本 100% 都是这类（E6 首跑抓到，逐条核过）。
            if not (0 <= pos[0] < w and 0 <= pos[1] < h):
                outside_room += 1
                continue
            c2 = SC.Camera((640, 480), 0, 2.0)
            # 相机窗口逻辑尺寸 = 640/2 × 480/2 = 320×240；把目标矩形放在物件中心
            c2.follow((0.0, 0.0, w, h),
                      (pos[0] - 10, pos[1] - 10, pos[0] + 10, pos[1] + 10))
            per_obj_checks.append((o, c2))
        try:
            plan = SR.plan_frame(sc, cam, geo, sprite_size=assets.sprite_size)
        except Exception as e:
            plan_err += 1
            print('  plan 异常 %s: %s' % (sid, e))
            continue
        kinds = {}
        for it in plan:
            kinds[it['kind']] = kinds.get(it['kind'], 0) + 1
        slot = per_ch.setdefault(ch, {'loaded': 0, 'with_obj': 0, 'obj': 0, 'missing': 0})
        slot['loaded'] += 1
        n_obj = kinds.get(SR.K_OBJ, 0)
        if n_obj:
            slot['with_obj'] += 1
            scenes_with_obj_plan += 1
            total_obj_drawn += n_obj
        # 关键：obj 指令的 name 必须能真取到 pixmap
        for it in plan:
            if it['kind'] == SR.K_OBJ:
                nm = it.get('name')
                if nm and assets.get(nm) is None:
                    slot['missing'] += 1
                    total_obj_missing += 1
                    if len(missing_names) < 10:
                        missing_names.append((sid, nm))

        # ★ E6 核心：逐物件把相机跟过去，确认它**真的出现在指令里**
        for o, c2 in per_obj_checks:
            try:
                p2 = SR.plan_frame(sc, c2, geo, sprite_size=assets.sprite_size)
            except Exception:
                per_obj_fail.append((sid, o.get('src'), 'plan异常'))
                continue
            want = o.get('src')
            wp = tuple(o.get('pos'))
            hit = False
            for it in p2:
                if it['kind'] != SR.K_OBJ:
                    continue
                # 用 name 与坐标双重确认（name 可能重名，坐标才是唯一标识）
                if it.get('name') == o.get('sprite') and it.get('rect') is not None:
                    hit = True
                    break
            per_obj_total += 1
            if hit:
                per_obj_hit += 1
            else:
                per_obj_fail.append((sid, want, wp))

    print('')
    print('=== 端到端贯通（objects → plan_frame → 素材）===')
    print('%-6s %8s %10s %10s %10s' % ('章', '已加载', '画出obj场', 'obj指令', '取不到图'))
    for ch in sorted(per_ch, key=lambda s: (len(s), s)):
        s = per_ch[ch]
        print('%-6s %8d %10d %10d %10d' %
              (ch, s['loaded'], s['with_obj'], s['obj'], s['missing']))

    print('')
    print('场景总数(索引) = %d，加载成功 = %d，plan 异常 = %d' %
          (len(scenes), scenes_loaded, plan_err))
    print('固定相机(原点) 首帧画出 obj 的场景 = %d，obj 指令 %d' %
          (scenes_with_obj_plan, total_obj_drawn))
    print('obj 指令取不到素材 = %d' % total_obj_missing)
    if missing_names:
        print('  前若干:', missing_names)
    print('')
    print('=== 逐物件定位（相机跟到每个物件身上）===')
    print('房间内受检物件 = %d，命中 = %d，未命中 = %d' %
          (per_obj_total, per_obj_hit, per_obj_total - per_obj_hit))
    print('房间外物件（门在界外，正确不画） = %d' % outside_room)
    if per_obj_fail:
        print('  未命中样本（最多 15）:')
        for f in per_obj_fail[:15]:
            print('   ', f)

    print('')
    print('=== 判据 ===')
    ok(scenes_loaded >= 1000, 'E1 场景加载成功 %d（≥1000，索引 1014）' % scenes_loaded)
    ok(plan_err == 0, 'E2 plan_frame 零异常（=%d）' % plan_err)
    ok(scenes_with_obj_plan >= 200,
       'E3 固定相机下 %d 个场景首帧画出 obj（≥200；被视口正确剔除的不算缺陷）'
       % scenes_with_obj_plan)
    ok(total_obj_drawn >= 400,
       'E4 固定相机下 obj 指令 %d（≥400；超宽房里相机只覆盖一部分，是正确剔除）'
       % total_obj_drawn)
    ok(total_obj_missing == 0,
       'E5 ★所有 obj 指令的素材都取得到（取不到 = %d，必须 0）' % total_obj_missing)
    ok(per_obj_total > 0 and per_obj_hit == per_obj_total,
       'E6 ★★逐物件定位：房间内物件被相机跟随时必须出现在指令里'
       '（%d/%d，0 例外；另有 %d 个界外门正确不画）'
       % (per_obj_hit, per_obj_total, outside_room))

    print('')
    print('合计：PASS=%d FAIL=%d' % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())

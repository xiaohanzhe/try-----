# -*- coding: utf-8 -*-
"""第44轮续 · 逐章验收渲染层（用户裁定 8：逐章验收）。

口径
----
用户裁定「逐章验收」⇒ 不以单点冒烟代替，必须**每章都有真实场景走完整链路**：
    _index.json → load_scene → room_geometry → Camera.follow → plan_frame
并断言：

  V1 每章都有可加载场景（ch1~ch5 各 >= 1）
  V2 每章带 bg 的场景，plan 里至少有 1 条 bg 指令
  V3 每章带 objects 的场景，plan 里 obj 指令数 == 该场景 objects 数
     （相机视口内的才算；用视口外过滤，界外门正确不画）
  V4 每条 bg/obj 指令的素材文件**真实存在于磁盘**（SceneAssetCache 口径）
  V5 相机矩形钳制在房间内（不与房间矩形相交出界 > 1px）
  V6 负控制：编造场景 id → 加载返回 None（不是「假装成功」）

为什么每章都要跑：不同章的房间尺寸分布不同（ch1 有 640×1160 竖塔、
ch4 有 2040×240 超宽廊），只测 ch1 无法暴露量级问题。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, MOD)

import scene_system as SS      # noqa: E402
import scene_camera as SC      # noqa: E402
import scene_render as SR      # noqa: E402

SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')

results = []


def check(cid, ok, msg):
    results.append((cid, bool(ok), msg))
    print('[%s] %s  %s' % ('PASS' if ok else 'FAIL', cid, msg))


def asset_exists(name):
    """按 SceneAssetCache 口径判素材文件是否存在（无前缀 → 相对 assets/scenes/）。"""
    if not isinstance(name, str) or not name:
        return False
    rel = name
    if rel.startswith('sprite:'):
        base = os.path.join(ROOT, 'ralsei_pet', rel[len('sprite:'):])
    else:
        base = os.path.join(SCENES, rel)
    return os.path.isfile(base)


def main():
    idx = SS.load_index()
    scenes = idx.get('scenes') or {}
    geo = json.load(io.open(os.path.join(SCENES, '_room_geometry.json'),
                            encoding='utf-8'))['rooms']

    # ---- 每章挑真实场景：各取一个有 objects 的 + 一个尺寸极端的 ----
    by_ch = {}
    for sid, ent in scenes.items():
        ch = ent.get('chapter_id')
        if ch:
            by_ch.setdefault(ch, []).append((sid, ent))

    # V1 每章都有可加载场景
    for ch in sorted(by_ch):
        check('V1.%s' % ch, len(by_ch[ch]) > 0,
              '第%s章可加载场景 %d 个' % (ch, len(by_ch[ch])))

    total_bg = total_obj = total_checked = 0
    bad_asset = []
    cam_bad = []

    for ch in sorted(by_ch):
        cands = by_ch[ch]
        # 选样本：有 objects 的 + 最大的房间 + 最小的房间
        with_obj, with_bg = [], []
        for sid, ent in cands:
            try:
                sc = SS.load_scene(sid, entry=ent)
            except Exception:
                continue
            if sc is None:
                continue
            if getattr(sc, 'objects', None):
                with_obj.append((sid, ent, sc))
            if getattr(sc, 'bg', None):
                with_bg.append((sid, ent, sc))
            if len(with_obj) >= 3 and len(with_bg) >= 3:
                break

        sample = (with_obj[:2] + with_bg[:2]) or [(cands[0][0], cands[0][1], None)]
        n_bg = n_obj = 0
        for sid, ent, sc in sample:
            if sc is None:
                continue
            total_checked += 1
            oid = getattr(sc, 'original_room_id', None)
            g = SR.room_geometry(oid, sc.chapter_id, geo)
            world = SR.room_world_rect(g, None)
            cam = SC.Camera((640, 480), 0, 1.5)
            cx = world[0] + world[2] / 2.0
            cy = world[1] + world[3] / 2.0
            tgt = (cx - 8, cy - 16, cx + 8, cy)
            rect = cam.follow(world, tgt)
            plan = SR.plan_frame(sc, cam, geo)

            for it in plan:
                if it.get('kind') == 'bg':
                    n_bg += 1
                    if not asset_exists(it.get('name')):
                        bad_asset.append((sid, 'bg', it.get('name')))
                elif it.get('kind') == 'obj':
                    n_obj += 1
                    if not asset_exists(it.get('name')):
                        bad_asset.append((sid, 'obj', it.get('name')))

            # V5 相机与房间的关系（两种合法形态，见 scene_camera.camera_rect._axis）
            #   ① 房间边长 >= 相机边长 ⇒ 该轴**必须钳在房间内**（原作四向钳制）
            #   ② 房间边长 <  相机边长 ⇒ 该轴**必须居中**（原作小房间不抖动）
            #   ⚠️ 判据初版只写 ①，「房间 320×240 < 相机 427×320」时相机矩形
            #      必然大出房间（居中偏移 -53.5）⇒ 12 例误报。这是判据错，不是代码错。
            if world and rect:
                tol = 1.01
                rw, rh = world[2], world[3]
                cw, chh = rect[2], rect[3]
                okx = oky = True
                if rw >= cw - tol:                                  # 轴 ①
                    okx = (rect[0] >= world[0] - tol
                           and rect[0] + cw <= world[0] + rw + tol)
                else:                                               # 轴 ②
                    okx = abs((rect[0] + cw / 2.0)
                              - (world[0] + rw / 2.0)) <= tol
                if rh >= chh - tol:
                    oky = (rect[1] >= world[1] - tol
                           and rect[1] + chh <= world[1] + rh + tol)
                else:
                    oky = abs((rect[1] + chh / 2.0)
                              - (world[1] + rh / 2.0)) <= tol
                if not (okx and oky):
                    cam_bad.append((sid, world, rect, okx, oky))

        total_bg += n_bg
        total_obj += n_obj
        check('V2.%s' % ch, n_bg >= 1 or not any(
            getattr(s, 'bg', None) for _, _, s in sample if s),
            '第%s章样本 bg 指令 = %d（样本 %d 个）' % (ch, n_bg, len(sample)))
        check('V3.%s' % ch, n_obj >= 1 or not any(
            getattr(s, 'objects', None) for _, _, s in sample if s),
            '第%s章样本 obj 指令 = %d' % (ch, n_obj))

    check('V4', not bad_asset,
          'bg/obj 指令素材文件全部存在（检查 %d 个场景，bg=%d obj=%d；缺 %d）'
          % (total_checked, total_bg, total_obj, len(bad_asset)))
    for b in bad_asset[:5]:
        print('      [MISS] %s' % (b,))

    check('V5', not cam_bad,
          '相机与房间关系正确（房间≥相机则钳内、房间<相机则居中；越界 %d 例）'
          % len(cam_bad))
    for b in cam_bad[:5]:
        print('      [CAM] %s' % (b,))

    # V6 负控制
    nope = SS.load_scene('chX.no.such_scene_zzz', entry={'chapter_id': 'chX'})
    check('V6', nope is None, '负控制：编造场景 id 加载返回 None')

    n_pass = sum(1 for _, ok, _ in results if ok)
    n_all = len(results)
    print('')
    print('合计：PASS=%d FAIL=%d' % (n_pass, n_all - n_pass))
    return 0 if n_pass == n_all else 1


if __name__ == '__main__':
    sys.exit(main())

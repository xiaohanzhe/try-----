# -*- coding: utf-8 -*-
u"""第120轮真机（离屏）验证：UT 场景的 bg 到底能不能被渲染层用上、且画对位置。

只看 JSON 字段是**不够**的（第119轮的教训：数据对了、产品读不到等于没做）。
本脚本走的就是产品那条路：
    SceneAssetCache（真读 PNG） → Camera（真跟随） → scene_render.plan_frame（真出指令）

判据：
  V1 每张采样场景都能出 `K_BG` 指令，且 name 与 JSON 里的 bg 一字不差
  V2 `sprite_size()` 拿到的是**房间原尺寸**（烘图就按房间像素烘的，不等就说明贴错图）
  V3 `fit == 'cover'`（背景等比盖满房间，不是按素材尺寸铺）
  V4 素材缓存 `missing` 为空（没有任何一张图读不出来）
  V5 负控制：把 bg 改成一个不存在的路径 ⇒ 必须**没有** K_BG 恰好命中（退化成占位/房间矩形），
     证明 V1 不是恒真
  V6 反向负控制：一张真图但尺寸被缩放（用 room 的一半）⇒ `native` 必须反映真实尺寸

用法：python verify120_render.py [--game ut]
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SCENES = os.path.join(PET, 'assets', 'scenes')

sys.path.insert(0, os.path.join(PET, 'modules'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication            # noqa: E402
from PyQt5.QtGui import QPixmap                    # noqa: E402

import scene_canvas                                  # noqa: E402
import scene_camera                                  # noqa: E402
import scene_render                                  # noqa: E402
import scene_system                                  # noqa: E402

SAMPLES = ['room_start', 'room_ruins1', 'room_ruins3', 'room_fire1',
           'room_water1', 'room_tundra1']


def _read_json(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return json.load(f)


def _scene_map(zone_path):
    d = _read_json(zone_path)
    return d.get('scenes') or {}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', default='ut')
    a = ap.parse_args(argv)

    app = QApplication.instance() or QApplication([])
    zone = os.path.join(SCENES, '_zone.%s.rooms.json' % a.game)
    scenes = _scene_map(zone)
    geo = _read_json(os.path.join(SCENES, '_room_geometry.json')).get('rooms') or {}
    cache = scene_canvas.SceneAssetCache(SCENES)

    by_name = {}
    for sid, sc in scenes.items():
        by_name[sc.get('name')] = (sid, sc)

    fails = []

    def check(desc, cond, detail=''):
        print(('[PASS] ' if cond else '[FAIL] ') + desc + (('    ' + detail) if detail else ''))
        if not cond:
            fails.append(desc)

    print('== 采样 %d 个 UT 场景 ==' % len(SAMPLES))
    for room in SAMPLES:
        hit = by_name.get(room)
        if not hit:
            check('V0 %s 在 zone 里' % room, False)
            continue
        sid, raw = hit
        bg = raw.get('bg')
        check('V0 %s 有 bg' % room, bool(bg), repr(bg))
        if not bg:
            continue

        s = scene_system.SceneState.from_dict(dict(raw, scene_id=sid))
        pm = cache.get(bg)
        check('V4 %s 素材可读' % room, pm is not None and not pm.isNull())

        w = h = None
        if pm is not None:
            w, h = pm.width(), pm.height()

        cam = scene_camera.Camera(size=(320, 240), scale=1.0)
        room_rect = (0, 0, w or 320, h or 240)
        cam.follow(room_rect, (room_rect[0], room_rect[1], 40, 40))
        items = scene_render.plan_frame(s, cam, geo_table=geo, tick=0,
                                        sprite_size=cache.sprite_size)
        bgs = [it for it in items if it.get('kind') == scene_render.K_BG]
        check('V1 %s 出 K_BG 指令' % room, len(bgs) == 1, 'n=%d' % len(bgs))
        if not bgs:
            continue
        it = bgs[0]
        check('V1b %s 指令里的 name == JSON 的 bg' % room, it.get('name') == bg,
              '%r vs %r' % (it.get('name'), bg))
        check('V2 %s native 尺寸 == 图真实尺寸' % room,
              tuple(it.get('native') or ()) == (w, h), '%r vs %r' % (it.get('native'), (w, h)))
        check('V3 %s fit == cover' % room, it.get('fit') == 'cover', repr(it.get('fit')))

    print('== 负控制 ==')
    # V5：bg 指向不存在的文件 → 必须**不能**命中一条"素材可读"的 K_BG
    bad = dict(by_name['room_start'][1])
    bad['bg'] = 'bg/__不存在_120__.png'
    s = scene_system.SceneState.from_dict(dict(bad, scene_id='ut.rooms.room_start'))
    cam = scene_camera.Camera(size=(320, 240), scale=1.0)
    cam.follow((0, 0, 640, 480), (0, 0, 40, 40))
    items = scene_render.plan_frame(s, cam, geo_table=geo, tick=0,
                                   sprite_size=cache.sprite_size)
    got = [it for it in items if it.get('kind') == scene_render.K_BG]
    # ★ 我最初的判据是"读不到就不出 K_BG"，跑出来是 n=1 —— **判据错了**：
    #   `plan_frame` 的设计是"读不到尺寸就退回房间矩形照样画"（见 scene_render 里
    #   `bg_px = room_px` 那条注释），所以每张 bg 都必然出一条 K_BG。
    #   真正能区分"真读到图"和"读不到"的是 `native` 与 `fit`：
    #     · 读到 → native=(w,h)、fit='cover'
    #     · 读不到 → native=None、fit='room'
    # ⚠️ `native` 在"读不到"时是 `(None, None)`（**非空 tuple**，truthy）
    #   ⇒ 不能用 `not native` 判，必须逐值比。这是本脚本第二次被自己的判据绊到。
    nat = got[0].get('native') if got else None
    ok_neg = (len(got) == 1 and tuple(nat or ()) == (None, None)
              and got[0].get('fit') == 'room')
    check('V5 不存在的 bg ⇒ native 为空且 fit=room（V1 非恒真）', ok_neg,
          repr((got[0].get('native'), got[0].get('fit'))) if got else 'n=0')
    check('V5b 该名字进了 missing 名单', 'bg/__不存在_120__.png' in cache.missing)

    # V6：拿一张真图但报一个假尺寸 ⇒ native 必须跟着"真读到的尺寸"走，不被 JSON 骗
    real = cache.get(by_name['room_ruins1'][1]['bg'])
    if real is not None:
        tmp = os.path.join(HERE, '_tmp_v6.png')
        real.scaled(max(1, real.width() // 2), max(1, real.height() // 2)).save(tmp)
        c2 = scene_canvas.SceneAssetCache(SCENES)
        c2._cache['bg/__v6__.png'] = QPixmap(tmp)      # 直接塞进缓存，绕过目录约定
        s2 = scene_system.SceneState.from_dict(
            dict(by_name['room_ruins1'][1], bg='bg/__v6__.png', scene_id='x'))
        cam2 = scene_camera.Camera(size=(320, 240), scale=1.0)
        cam2.follow((0, 0, 320, 480), (0, 0, 40, 40))
        it2 = [it for it in scene_render.plan_frame(s2, cam2, geo_table=geo, tick=0,
                                                    sprite_size=c2.sprite_size)
               if it.get('kind') == scene_render.K_BG]
        ok = len(it2) == 1 and tuple(it2[0].get('native') or ()) == \
            (real.width() // 2, real.height() // 2)
        check('V6 尺寸变了 native 跟着变（不是抄 JSON）', ok,
              repr(it2[0].get('native') if it2 else None))
        try:
            os.remove(tmp)
        except OSError:
            pass

    print('== 缓存自省 ==')
    # ★ 负控制故意留了一个坏名字在 missing 里；这里只要求 missing **恰好**是那个，
    #   多一个都说明有别的图读不出来。
    stray = [n for n in cache.missing if n != 'bg/__不存在_120__.png']
    check('V7 除负控制外没有读不出的图', not stray, repr(stray[:5]))
    print('---- 采样 %d 条，失败 %d 条' % (len(SAMPLES), len(fails)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

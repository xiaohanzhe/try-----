# -*- coding: utf-8 -*-
u"""第121轮（离屏）真机验证：ut 场景的 `objects` 到底能不能被产品**用起来**。

只看 JSON 里有 422 条是不够的（第119/120轮两次教训）。本脚本走产品那条路：

    scene_system.SceneState.from_dict → item_interact.build_props（真建物件）
    → scene_render.plan_frame（真出绘制指令）

判据：
  A 数据面：358 场景 / 136 有物件 / 422 条；每条字段恰好 4 个、`sprite` 必须为 None
  B 交互面：**136 个场景逐个**真跑 `build_props`，不抛、总数与条目数对得上
  C 内容面：可读物拿到的是**原作正文**（逐字等于资产里的 cn），不是兜底台词
  D 负控制：清空 objects ⇒ 物件 0；把 src 改成不存在的名字 ⇒ 物件 0（B 非恒真）
  E 绘制面：`plan_frame` 出的 K_OBJ 里 **name 全为 None** ⇒ `_paint_obj` 不落笔
     （画面已在第120轮的背景里，再画一遍就是重复绘制）
  F 正控制：给同一条目塞一个真实 sprite ⇒ 该 K_OBJ 的 name 非 None（E 非恒真）

用法：python verify_objs121.py
"""
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PET, 'assets', 'scenes')

sys.path.insert(0, os.path.join(PET, 'modules'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication            # noqa: E402

import item_interact as II                          # noqa: E402
import scene_camera                                  # noqa: E402
import scene_render                                  # noqa: E402
import scene_system                                  # noqa: E402

FIELDS = {'pos', 'sprite', 'src', 'depth'}
_fails = []
_npass = 0


def check(desc, cond, detail=''):
    global _npass
    if cond:
        _npass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _fails.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def _json(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return json.load(f)


def _props_of(raw, sid, readables=None):
    u"""按产品调用方式建物件（`present` 给个桩 —— 本脚本只验"建得出来"，不验弹窗）。"""
    scene = dict(raw, scene_id=sid)
    return II.build_props(scene, chapter='ut', world='otherworld',
                          present=lambda text, actor=None: 'TOKEN',
                          readables=readables)


def main():
    QApplication.instance() or QApplication([])
    scenes = _json(os.path.join(SCENES, '_zone.ut.rooms.json'))['scenes']
    geo = _json(os.path.join(SCENES, '_room_geometry.json')).get('rooms') or {}
    readables = II.load_readable_text(os.path.join(SCENES, '_readable_text.json'))

    withobj = [(sid, sc) for sid, sc in scenes.items() if sc.get('objects')]
    total = sum(len(sc['objects']) for _s, sc in withobj)

    print('== A. 数据面 ==')
    check('A1 358 个场景里 136 个有 objects、合计 422 条',
          len(scenes) == 358 and len(withobj) == 136 and total == 422,
          '%d 场景 / %d 有物件 / %d 条' % (len(scenes), len(withobj), total))
    bad_fields, bad_sprite, bad_pos = [], [], []
    for sid, sc in withobj:
        for e in sc['objects']:
            if set(e) != FIELDS:
                bad_fields.append((sid, sorted(e)))
            if e.get('sprite') is not None:
                bad_sprite.append((sid, e.get('sprite')))
            p = e.get('pos')
            if not (isinstance(p, list) and len(p) == 2
                    and all(isinstance(v, int) for v in p)):
                bad_pos.append((sid, p))
    check('A2 每条字段恰好 {pos, sprite, src, depth}', not bad_fields, repr(bad_fields[:3]))
    check('A3 `sprite` 必须为 None（画面已在背景里，不重复绘制）',
          not bad_sprite, repr(bad_sprite[:3]))
    check('A4 `pos` 是两个 int（左上角语义）', not bad_pos, repr(bad_pos[:3]))

    print()
    print('== B. 交互面（136 个场景逐个真跑 build_props）==')
    n_props = 0
    crash, mismatch = [], []
    for sid, sc in withobj:
        try:
            got = _props_of(sc, sid, readables)
        except Exception as ex:                        # noqa: BLE001
            crash.append((sid, type(ex).__name__ + ': ' + str(ex)[:60]))
            continue
        n_props += len(got)
        # 能被 `build_props` 建成物件的只有 savepoint / fountain / readable / sign /
        # interactable（pickup 还要 `pickups` 表，door 要路由表 ⇒ 本轮都不给）
        want = sum(1 for e in sc['objects']
                   if (II.classify(e['src']) or {}).get('kind')
                   in ('savepoint', 'fountain', 'readable', 'sign', 'interactable'))
        if len(got) != want:
            mismatch.append((sid, len(got), want))
    check('B1 136 个场景跑 build_props 全部不抛', not crash, repr(crash[:3]))
    check('B2 每个场景建出的物件数 == 可建条目数（没有静默丢弃）',
          not mismatch, repr(mismatch[:3]))
    check('B3 建出物件总数 > 0（分母非空，B2 不是空集恒真）', n_props > 0, str(n_props))

    print()
    print('== C. 内容面：可读物说原文 ==')
    # 找一对 (场景, obj) 在正文资产里真有正文的
    hit = None
    for sid, sc in withobj:
        rt = readables.get(sid) or {}
        for e in sc['objects']:
            if e['src'] in rt:
                hit = (sid, sc, e['src'], rt[e['src']])
                break
        if hit:
            break
    if hit:
        sid, sc, src, want_text = hit
        got = [p for p in _props_of(sc, sid, readables) if getattr(p, 'src', None) == src]
        got_text = getattr(got[0], 'text', None) if got else None
        check('C1 可读物拿到的是**原作正文**（逐字相等，不是兜底）',
              bool(got) and got_text == want_text,
              '%s / %s：%r' % (sid, src, (got_text or '')[:40]))
        # 负控制：不给 readables ⇒ 必须退到兜底，且**不等于**原文
        nb = [p for p in _props_of(sc, sid, None) if getattr(p, 'src', None) == src]
        nb_text = getattr(nb[0], 'text', None) if nb else None
        check('C2 负控制：不给正文资产 ⇒ 退到兜底台词，且与原文不同（C1 非恒真）',
              nb_text is not None and nb_text != want_text,
              repr((nb_text or '')[:40]))
    else:
        check('C1 找到一对"场景+可读物"都能对上正文的样本', False, '一个都没找到')

    print()
    print('== D. 负控制：B 的判据不是"有 objects 就必然有物件" ==')
    sid0, sc0 = withobj[0]
    empty = dict(sc0, objects=[])
    check('D1 把 objects 清空 ⇒ 物件 0', len(_props_of(empty, sid0, readables)) == 0)
    fake = dict(sc0, objects=[dict(sc0['objects'][0], src='__no_such_obj_121__')])
    check('D2 把 src 换成不存在的对象名 ⇒ 物件 0',
          len(_props_of(fake, sid0, readables)) == 0)

    print()
    print('== E/F. 绘制面：不重复画，且判据有鉴别力 ==')
    sid1, sc1 = withobj[0]
    s = scene_system.SceneState.from_dict(dict(sc1, scene_id=sid1))
    cam = scene_camera.Camera(size=(320, 240), scale=1.0)
    cam.follow((0, 0, 680, 260), (0, 0, 40, 40))
    items = scene_render.plan_frame(s, cam, geo_table=geo, tick=0,
                                    sprite_size=lambda n: (20, 20))
    objs = [it for it in items if it.get('kind') == scene_render.K_OBJ]
    check('E1 该场景确实出了 K_OBJ 指令（分母非空）', len(objs) > 0, 'n=%d' % len(objs))
    check('E2 所有 K_OBJ 的 name 都是 None ⇒ `_paint_obj` 的 `if name` 不成立、不落笔',
          all(it.get('name') is None for it in objs),
          repr([it.get('name') for it in objs][:3]))

    real_spr = 'objs/spr_savepoint_0.png'
    exists = os.path.isfile(os.path.join(SCENES, real_spr))
    patched = dict(sc1, objects=[dict(sc1['objects'][0], sprite=real_spr)])
    s2 = scene_system.SceneState.from_dict(dict(patched, scene_id=sid1))
    cam2 = scene_camera.Camera(size=(320, 240), scale=1.0)
    cam2.follow((0, 0, 680, 260), (0, 0, 40, 40))
    it2 = [it for it in scene_render.plan_frame(s2, cam2, geo_table=geo, tick=0,
                                                sprite_size=lambda n: (20, 20))
           if it.get('kind') == scene_render.K_OBJ]
    check('F1 正控制：给同一条目塞真 sprite ⇒ name 非 None（E2 非恒真）',
          bool(it2) and any(it.get('name') == real_spr for it in it2),
          'sprite 文件在盘=%s；got=%r' % (exists, [it.get('name') for it in it2][:3]))

    print()
    print('---- 共 %d 条：PASS %d / FAIL %d' % (_npass + len(_fails), _npass, len(_fails)))
    if _fails:
        print('失败项：')
        for d in _fails:
            print('  - %s' % d)
    return 1 if _fails else 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())

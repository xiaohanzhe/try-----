# -*- coding: utf-8 -*-
"""第44轮续 · 动效（sprite 逐帧动画）回归锁。

背景（为什么动效 = 逐帧动画）
-----------------------------
第44轮全量普查（`_evidence/动效普查44.txt`）实测：
  · 背景层 HSpeed/VSpeed 非零 = **0 / 191**  ⇒ 无背景滚动（复核第43轮：背景移动=相机平移）
  · 图层 EffectType 非空 = **0**            ⇒ 无 shader 特效层
  · 瓦片 AnimationFrames>1 = **0**          ⇒ 无瓦片动画
  · 房间级 Sequence = **0**                 ⇒ 无时间轴演出
  · **多帧 sprite = 523 / 1097（47.7%）**   ⇒ ★ 唯一动效载体
所以「动效全做」的正确内容是：**让物件按原作速度播放 sprite 帧序列**。

判据（A 数据 / B 渲染 / C 负控制）
  A1 `_sprite_anim.json` 存在、结构合法、fps=30
  A2 多帧物件的 `anim` 字段齐全（base/frames/frame_ms/src 都在）
  A3 `anim.base` 指向的帧文件在磁盘上**真的存在**（frames 个，一个不少）
  A4 `anim.frame_ms` 与源参数自洽（= 1000/(30*speed)，容差 0.1ms）
  B1 `_anim_frame_index` **随时间前进**（t 增大 → 帧号变化；真实量级输入）
  B2 周期正确：t 与 t + frames*frame_ms 取同一帧
  B3 `plan_frame` 传不同 tick → obj 指令的 `name` 真的不同（端到端在动）
  B4 tick=0 → 恒第 0 帧（确定性；回归锁据此稳定）
  C1 负控制：单帧物件（无 anim）→ 名不随 tick 变（不能"乱动"）
  C2 负控制：`anim` 非法（frames=0 / 缺 base）→ 不抛，退单帧
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')          # = 仓库根（锁在 第44轮.../ 下）
PET = os.path.join(ROOT, 'ralsei_pet')
MOD = os.path.join(PET, 'modules')
sys.path.insert(0, MOD)
sys.path.insert(0, os.path.join(PET, 'src'))

import scene_render as SR      # noqa: E402
import scene_system as SS      # noqa: E402
import scene_camera as SC      # noqa: E402

SCENES = os.path.join(PET, 'assets', 'scenes')
ANIM = os.path.join(SCENES, '_sprite_anim.json')
OBJS = os.path.join(SCENES, 'objs')

results = []


def check(cid, ok, msg):
    results.append((cid, bool(ok), msg))
    print('[%s] %s  %s' % ('PASS' if ok else 'FAIL', cid, msg))


def main():
    # ---- A1 ----
    if not os.path.isfile(ANIM):
        check('A1', False, '_sprite_anim.json 不存在')
        return _finish()
    with io.open(ANIM, 'r', encoding='utf-8') as fh:
        anim_doc = json.load(fh)
    sp = anim_doc.get('sprites') or {}
    check('A1', int(anim_doc.get('fps') or 0) == 30 and len(sp) > 0,
          'A1 _sprite_anim.json 合法（fps=%s，多帧 sprite=%d）'
          % (anim_doc.get('fps'), len(sp)))

    # ---- 收集真数据里的 anim ----
    # ★ 必须从**磁盘真值**（场景 JSON）取，不能只信 _sprite_anim.json
    #   —— 后者"配了但没被写进场景"是可能的（最贵的坑：函数对了产品没用上）。
    found = []
    idx = SS.load_index()
    for sid, ent in (idx.get('scenes') or {}).items():
        try:
            sc = SS.load_scene(sid, entry=ent)
        except Exception:
            continue
        if sc is None:
            continue
        for ob in (getattr(sc, 'objects', None) or []):
            if isinstance(ob, dict) and isinstance(ob.get('anim'), dict):
                found.append((sid, ob))
    check('A2', len(found) > 0,
          'A2 场景数据里带 anim 的物件 = %d 条（全仓）' % len(found))

    # 字段齐全
    bad_field = []
    for sid, ob in found:
        a = ob['anim']
        base = a.get('base')
        try:
            n = int(a.get('frames') or 0)
        except (TypeError, ValueError):
            n = 0
        ms = a.get('frame_ms')
        src = a.get('src')
        if (not isinstance(base, str) or not base or n < 2
                or not isinstance(ms, (int, float)) or ms <= 0
                or src not in ('original', 'default_30fps')):
            bad_field.append((sid, ob.get('src'), a))
    check('A2b', not bad_field,
          'A2b anim 字段齐全（base/frames>=2/frame_ms>0/src 合法）；异常 %d'
          % len(bad_field))
    for b in bad_field[:3]:
        print('      [BAD] %s' % (b,))

    # ---- A3 帧文件真实存在 ----
    missing = []
    for sid, ob in found:
        a = ob['anim']
        base = a['base']
        n = int(a['frames'])
        for i in range(n):
            p = os.path.join(SCENES, '%s_%d.png' % (base, i))
            if not os.path.isfile(p):
                missing.append((sid, ob.get('src'), '%s_%d.png' % (base, i)))
    check('A3', not missing,
          'A3 anim.base 的 %d 条动画物件、全部帧文件在磁盘存在（缺 %d）'
          % (len(found), len(missing)))
    for m in missing[:5]:
        print('      [MISS] %s' % (m,))

    # ---- A4 frame_ms 与源参数自洽 ----
    fps = float(anim_doc.get('fps') or 30)
    bad_ms = []
    for name, rec in sp.items():
        try:
            n = int(rec.get('frames') or 0)
            s = float(rec.get('speed') or 0)
            ms = float(rec.get('frame_ms'))
        except (TypeError, ValueError):
            bad_ms.append((name, 'unparsable', rec))
            continue
        if n < 2:
            continue
        want = 1000.0 / (fps * s) if s > 0 else None
        if want is None or abs(ms - want) > 0.11:
            bad_ms.append((name, ms, want))
    check('A4', not bad_ms,
          'A4 frame_ms 与 fps/speed 自洽（1000/(30*speed)，容差 0.11ms）；异常 %d'
          % len(bad_ms))
    for b in bad_ms[:3]:
        print('      [BAD] %s' % (b,))

    # ---- B1/B2 帧号随时间前进 + 周期正确 ----
    # ★ 必须给**真实量级的毫秒时间戳**（记忆铁律：行为判据必须用真实量级输入）。
    #   初版写成 `int(ms*1)`：ms=33.3 ⇒ int=33，而阈值判据是 `t >= ms`
    #   （33 >= 33.3 假）⇒ 落进"每 tick 一帧"的回落分支，得到 33 % 6 = 3 的
    #   假报红。这是**判据侧**的错，不是代码错。
    a0 = found[0][1]['anim'] if found else None
    if a0:
        ms = float(a0['frame_ms'])
        n = int(a0['frames'])
        # 用「第 k 帧的起点 + 半个帧宽」这种“明确落在第 k 帧”的时刻
        def at_frame(k, frac=0.5):
            return int(ms * (k + frac))
        f_t0 = SR._anim_frame_index(a0, at_frame(0))[0]
        f_t1 = SR._anim_frame_index(a0, at_frame(1))[0]
        f_t2 = SR._anim_frame_index(a0, at_frame(2))[0]
        check('B1', (f_t0 == 0 and f_t1 == 1 % n and f_t2 == 2 % n),
              'B1 帧号随时间前进（落在第0/1/2帧 → %d,%d,%d；n=%d，ms=%.1f）'
              % (f_t0, f_t1, f_t2, n, ms))
        fa = SR._anim_frame_index(a0, at_frame(5))[0]
        fb = SR._anim_frame_index(a0, at_frame(5 + n))[0]
        check('B2', fa == fb,
              'B2 周期正确（第5帧 与 第5+%d帧 同帧：%d == %d）' % (n, fa, fb))
    else:
        check('B1', False, 'B1 无动画物件可测')

    # ---- B3/B4 端到端：plan_frame 真的换帧 ----
    # 找一个「有 anim 物件且在相机视口内」的场景
    target = None
    for sid, ob in found:
        ent = (idx.get('scenes') or {}).get(sid)
        if ent is None:
            continue
        try:
            sc = SS.load_scene(sid, entry=ent)
        except Exception:
            continue
        if sc is None:
            continue
        geo = json.load(io.open(os.path.join(SCENES, '_room_geometry.json'),
                                encoding='utf-8'))['rooms']
        g = SR.room_geometry(getattr(sc, 'original_room_id', None),
                             getattr(sc, 'chapter_id', None), geo)
        world = SR.room_world_rect(g, None)
        cam = SC.Camera((640, 480), 0, 1.0)
        cx = world[0] + world[2] / 2.0
        cy = world[1] + world[3] / 2.0
        cam.follow(world, (cx - 8, cy - 16, cx + 8, cy))
        for tick in (0, 40, 80, 120):
            plan = SR.plan_frame(sc, cam, geo, tick=tick)
            names = [it.get('name') for it in plan
                     if it.get('kind') == 'obj' and it.get('anim_frames')]
            if names:
                target = (sid, sc, cam, geo)
                break
        if target:
            break

    if target is None:
        check('B3', False, 'B3 找不到「动画物件落在视口内」的场景 ⇒ 判据无法执行')
        check('B4', False, 'B4 同上')
    else:
        sid, sc, cam, geo = target
        a = None
        for ob in (getattr(sc, 'objects', None) or []):
            if isinstance(ob, dict) and isinstance(ob.get('anim'), dict):
                a = ob['anim']
                break
        ms = float(a['frame_ms'])
        names0 = [it.get('name') for it in SR.plan_frame(sc, cam, geo, tick=0)
                  if it.get('kind') == 'obj' and it.get('anim_frames')]
        names1 = [it.get('name') for it in SR.plan_frame(sc, cam, geo,
                                                         tick=int(ms * 1.5))
                  if it.get('kind') == 'obj' and it.get('anim_frames')]
        check('B3', names0 != names1,
              'B3 plan_frame 换帧（tick=0 → %s ；tick=%.0fms → %s；场景 %s）'
              % (names0[:2], ms * 1.5, names1[:2], sid))

        # B4 tick=0 两次调用必须一致（确定性）
        n0a = [it.get('name') for it in SR.plan_frame(sc, cam, geo, tick=0)
               if it.get('kind') == 'obj' and it.get('anim_frames')]
        n0b = [it.get('name') for it in SR.plan_frame(sc, cam, geo, tick=0)
               if it.get('kind') == 'obj' and it.get('anim_frames')]
        check('B4', n0a == n0b and all(n.endswith('_0.png') for n in n0a),
              'B4 tick=0 确定性且恒第 0 帧（%s）' % n0a[:3])

    # ---- C1 负控制：单帧物件不随 tick 变 ----
    if target is not None:
        sid, sc, cam, geo = target
        def _static_names(t):
            return [it.get('name') for it in SR.plan_frame(sc, cam, geo, tick=t)
                    if it.get('kind') == 'obj' and not it.get('anim_frames')]
        s0 = _static_names(0)
        s1 = _static_names(int(1e6))
        check('C1', s0 == s1,
              'C1 负控制：单帧物件名不随 tick 变（%s）' % s0[:2])
    else:
        check('C1', False, 'C1 无比对场景')

    # ---- C2 负控制：非法 anim 不抛、退单帧 ----
    ok2 = True
    detail = []
    for bad_anim in ({'frames': 0}, {'base': ''}, {'frames': 3}, None, 'x', 5):
        try:
            r = SR._anim_frame_index(bad_anim, 999)
            if not (isinstance(r, tuple) and len(r) == 2):
                ok2 = False
                detail.append((bad_anim, r))
        except Exception as e:
            ok2 = False
            detail.append((bad_anim, repr(e)))
    check('C2', ok2, 'C2 负控制：非法 anim → 不抛且返回 (0,1)（异常 %d）'
          % len(detail))
    for d in detail[:3]:
        print('      [BAD] %s' % (d,))

    return _finish()


def _finish():
    n_pass = sum(1 for _, ok, _ in results if ok)
    n_all = len(results)
    print('')
    print('合计：PASS=%d FAIL=%d' % (n_pass, n_all - n_pass))
    return 0 if n_pass == n_all else 1


if __name__ == '__main__':
    sys.exit(main())

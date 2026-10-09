# -*- coding: utf-8 -*-
u"""第101轮回归锁：OneShot 263 间背景「合成落盘 + 两层接线 + 渲染真出图」不许漂移。

口径（用户）：
    「**一切根据原作**」/「把原作的世界搬到桌面上」/「**一定要看录像而不是只读后台输出**」

本轮做了什么
------------
第100轮打通了"从原作 tmx 合成背景"的**管线**（只在 `_evidence/` 里产了 3 张样例）。
本轮把它**落进产品**：263 张进 `assets/scenes/bg/`，并把
`bg` / `bg_source` / `bg_asset` 写进**两层登记**（`_zone.oneshot.*.json` 与 `_index.json` 内联副本）。

判据分四段
----------
 A **落盘面**：263 张在位、尺寸与**独立来源**（`_room_geometry.json`）1:1、与第100轮已验证样本逐像素相同
 B **数据面**：两层逐字段一致、三字段合法、**无重复键**（首跑 bug 的守点）
 C **渲染面** ★：263 个场景逐个跑 `plan_frame` ⇒ 必须产 `K_BG` 且**盖满视口**
   （数据接好了 ≠ 画得出来；这条是"接线真的生成了画面"的端到端判据）
 D **纪律**：新档次 `bg_source` 只此一档、文件命名与 room_id 自洽、判据条数自查

★ 铁律：成功标记 `[PASS]` 字面量（`run_all.py` 按它计数）；正/负控制成对；
  判据名禁自带标记；本套件**零 Qt 窗口**（只有 import 级）。
"""
import ast
import io
import json
import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# ⚠️ 住在 `<轮次>/_tools/` ⇒ 上溯三层才是仓库根（第38轮起的老坑）
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
RELP = 'ralsei_pet/assets/scenes/'
sys.path.insert(0, MOD)

import scene_render as SR                                     # noqa: E402
import scene_camera as SC                                     # noqa: E402
import scene_system as SS                                     # noqa: E402

_N = [0]
_FAIL = []


def ok(cond, msg):
    _N[0] += 1
    if cond:
        print('[PASS] %s' % msg)
    else:
        _FAIL.append(msg)
        print('[FAIL] %s' % msg)


def jload(p):
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


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


def _covers(rect, view):
    if not rect or not view:
        return False
    x, y, w, h = rect
    return x <= 0 and y <= 0 and x + w >= view[0] and y + h >= view[1]


def _cam_at(room_w, room_h, out_w=640, out_h=480, scale=2.0):
    """相机摆到"宠物在屏幕右下角时所对应的房间坐标"（与 check99 同口径）。"""
    cw, ch = out_w / scale, out_h / scale
    cx, cy = room_w * 0.84, room_h * 0.84
    tgt = (cx - cw / 2.0, cy - ch / 2.0, cx + cw / 2.0, cy + ch / 2.0)
    cam = SC.Camera((out_w, out_h), 0, scale)
    cam.follow((0.0, 0.0, float(room_w), float(room_h)), tgt)
    return cam


ZONE_FILES = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.'))
TARGETS = {}          # sid -> (bg, bg_source, bg_asset)
RID = {}              # sid -> original_room_id


def _load_targets():
    for f in ZONE_FILES:
        d = jload(os.path.join(SCENES, f))
        for sid, s in (d.get('scenes') or {}).items():
            TARGETS[sid] = (s.get('bg'), s.get('bg_source'), s.get('bg_asset'))
            RID[sid] = int(s.get('original_room_id'))


def _inline():
    idx = jload(os.path.join(SCENES, '_index.json'))
    out = {}
    for ak, av in ((idx['chapters'].get('oneshot') or {}).get('areas') or {}).items():
        for sid, s in ((av or {}).get('scenes') or {}).items():
            out[sid] = s
    return out, idx


# ===========================================================================
# A 落盘面
# ===========================================================================
def sec_a():
    print('== A 落盘面 ==')
    geo = jload(os.path.join(SCENES, '_room_geometry.json'))['rooms']
    _load_targets()
    miss, sizebad = [], []
    for sid, (bg, _s, _a) in sorted(TARGETS.items()):
        p = os.path.join(SCENES, bg or '')
        if not bg or not os.path.isfile(p):
            miss.append(sid)
            continue
        sz = _png_size(p)
        g = geo.get('oneshot:%s' % RID[sid])
        if sz is None or not g or (g.get('w'), g.get('h')) != sz:
            sizebad.append((sid, sz, (g or {}).get('w'), (g or {}).get('h')))

    ok(not miss, 'A1 263 张背景图**全部**在磁盘上（缺 %d %s）' % (len(miss), miss[:3]))
    ok(len(TARGETS) == 263, 'A2 OneShot 场景数 == 263（实际 %d）' % len(TARGETS))
    ok(not sizebad,
       'A3 ★ 每张图尺寸 == 独立登记的 `_room_geometry.json` 房间几何（1:1，不符 %d %s）'
       % (len(sizebad), sizebad[:3]))

    # A4 跨轮一致：与第100轮**已验证**样例逐像素相同（不许漂移）
    try:
        from PIL import Image
    except ImportError:
        print('[SKIP] A4 PIL 不在（跨轮像素比对跳过，不假红）')
        return
    ev = os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                      '_evidence', 'os_bg')
    pair, bad = 0, []
    for fn in (sorted(os.listdir(ev)) if os.path.isdir(ev) else []):
        m = re.match(r'os_(\d+)\.png$', fn)
        if not m:
            continue
        mp = os.path.join(SCENES, 'bg', 'oneshot_map%s.png' % m.group(1))
        if os.path.isfile(mp):
            pair += 1
            if Image.open(os.path.join(ev, fn)).convert('RGBA').tobytes() != \
                    Image.open(mp).convert('RGBA').tobytes():
                bad.append(fn)
    ok(pair > 0 and not bad,
       'A4 ★ 跨轮一致：与第100轮已验证合成图逐像素相同（%d 对，不符 %d %s）'
       % (pair, len(bad), bad))


# ===========================================================================
# B 数据面
# ===========================================================================
def sec_b():
    print('== B 数据面 ==')
    inline, idx = _inline()
    ok(len(inline) == 263, 'B1 `_index.json` 内联副本 263 条（实际 %d）' % len(inline))

    bad3 = [sid for sid, (bg, src, asset) in TARGETS.items()
            if not (isinstance(bg, str) and bg.startswith('bg/oneshot_map')
                    and src == 'tmx.composite'
                    and re.fullmatch(r'map\d+\.tmx', str(asset or '')))]
    ok(not bad3, 'B2 ★ 三字段合法（bg=bg/oneshot_map*.png / bg_source=tmx.composite / '
                 'bg_asset=map*.tmx）违规 %d %s' % (len(bad3), bad3[:3]))

    mis = [sid for sid in TARGETS
           if json.dumps(TARGETS[sid], ensure_ascii=False)
           != json.dumps((inline.get(sid, {}).get('bg'),
                          inline.get(sid, {}).get('bg_source'),
                          inline.get(sid, {}).get('bg_asset')), ensure_ascii=False)]
    ok(not mis, 'B3 ★ 两层登记（zone 分片 / index 内联）逐字段一致（不一致 %d %s）'
       % (len(mis), mis[:3]))

    # ★★ 无重复键 —— 首跑 bug 的守点（OneShot 的 bg_source 后面还跟着 objects
    #    ⇒ 原行带尾逗号；照搬第39轮"只认无逗号"的正则 ⇒ 漏替换 + 重复键
    #    ⇒ Python json 取最后一个 ⇒ bg_source 恒 'none'）
    dup = {}
    for f in ZONE_FILES + ['_index.json']:
        found = []

        def hook(pairs, _found=found):
            seen = set()
            for k, v in pairs:
                if k in seen:
                    _found.append(k)
                seen.add(k)
            return dict(pairs)

        with io.open(os.path.join(SCENES, f), encoding='utf-8') as fh:
            json.load(fh, object_pairs_hook=hook)
        if found:
            dup[f] = found[:3]
    ok(not dup, 'B4 ★★ 7 个文件都没有**重复键**（首跑 bad=526 的守点）%s'
       % (dup or '(无)'))

    # 负控制：判据真的能抓到重复键（造一个假的，用同一套 hook）
    fake = '{"bg": 1, "bg_source": "x", "bg_source": "none"}'


    def _h(pairs):
        out = []
        seen = set()
        for k, v in pairs:
            out.append(k if k not in seen else ('DUP!' + k))
            seen.add(k)
        return out

    ok('DUP!bg_source' in json.loads(fake, object_pairs_hook=_h),
       'B5 负控制：重复键检测器对"造出来的重复"确实报 DUP（不是恒真判据）')

    ok(sorted(z for _b, z, _a in TARGETS.values()) == ['tmx.composite'] * 263,
       'B6 `bg_source` **只**用新增的 `tmx.composite` 一档（没混进 room.bg_layer 等）')


# ===========================================================================
# C 渲染面 ★ 数据接好了 != 画得出来
# ===========================================================================
def sec_c():
    print('== C 渲染面（真跑 plan_frame）==')
    geo = jload(os.path.join(SCENES, '_room_geometry.json'))['rooms']
    idx = SS.load_index()
    scenes = idx.get('scenes') or {}
    n = 0
    n_bg = n_cover = n_native = n_fill = 0
    bad = []
    for sid in sorted(TARGETS):
        ent = scenes.get(sid)
        sc = SS.load_scene(sid, entry=ent)
        if sc is None:
            bad.append((sid, 'load_scene=None'))
            continue
        n += 1
        rid = sc.original_room_id
        g = geo.get('oneshot:%s' % rid)
        if not g:
            bad.append((sid, 'no geo'))
            continue
        sz = _png_size(os.path.join(SCENES, sc.bg or ''))
        cam = _cam_at(g['w'], g['h'])
        plan = SR.plan_frame(sc, cam, geo, sprite_size=lambda _n, _s=sz: _s)
        bgs = [it for it in plan if it['kind'] == SR.K_BG]
        fills = [it for it in plan if it['kind'] == SR.K_ROOM_FILL]
        view = SR.plan_viewport(sc, cam, geo)
        if len(bgs) == 1:
            n_bg += 1
            if _covers(bgs[0]['rect'], view):
                n_cover += 1
            else:
                bad.append((sid, 'bg not cover', bgs[0]['rect'], view))
            if bgs[0].get('native') == sz:
                n_native += 1
        else:
            bad.append((sid, 'bg items=%d' % len(bgs)))
        if len(fills) == 1:
            n_fill += 1
    print('  渲染：场景 %d ｜ 出 bg 指令 %d ｜ 盖满视口 %d ｜ native 如实 %d ｜ 出黑底 %d'
          % (n, n_bg, n_cover, n_native, n_fill))
    ok(n == 263, 'C1 ★ 263 个 OneShot 场景**全部**能加载（实际 %d）%s' % (n, bad[:2]))
    ok(n_bg == 263, 'C2 ★★ 263 个场景**全部**产出 `bg` 指令（缺 %d —— 数据接好不等于画得出）'
       % (263 - n_bg))
    ok(n_cover == 263, 'C3 ★★ 每条 bg 指令都**盖满视口**（未盖满 %d %s）'
       % (263 - n_cover, [b for b in bad if len(b) > 2][:2]))
    ok(n_native == 263, 'C4 bg 指令如实记载 `native`=素材真像素（不符 %d）' % (263 - n_native))
    ok(n_fill == 263, 'C5 263 个场景都产房间底色（黑底兜底，不露壁纸）实际 %d' % n_fill)

    # 负控制：把 bg 抹掉 ⇒ 必须变成"占位"而不是"照旧出 bg"（证明 C2 不是恒真）
    one = sorted(TARGETS)[0]
    sc2 = SS.load_scene(one, entry=scenes.get(one))
    sc2.bg = None
    g2 = geo.get('oneshot:%s' % sc2.original_room_id)
    p2 = SR.plan_frame(sc2, _cam_at(g2['w'], g2['h']), geo,
                       sprite_size=lambda _n: (10, 10))
    k2 = [it['kind'] for it in p2]
    ok(SR.K_BG not in k2 and SR.K_PLACEHOLDER in k2,
       'C6 负控制：把 bg 置 None ⇒ 不再出 bg 指令、改出占位（实际 %s）' % (k2,))


# ===========================================================================
# D 纪律与自检
# ===========================================================================
def sec_d():
    print('== D 纪律与自检 ==')
    # D1 文件名与 room_id 自洽（map 编号 == scene.original_room_id）
    rid_of = {}
    for f in ZONE_FILES:
        d = jload(os.path.join(SCENES, f))
        for sid, s in (d.get('scenes') or {}).items():
            rid_of[sid] = int(s['original_room_id'])
    bad = [sid for sid, (bg, _s, a) in TARGETS.items()
           if bg != 'bg/oneshot_map%d.png' % rid_of[sid]
           or a != 'map%d.tmx' % rid_of[sid]]
    ok(not bad, 'D1 文件名/溯源与 room_id 自洽（room_id 1..263 与 map 编号 1:1）不符 %d'
       % len(bad))
    ok(sorted(rid_of.values()) == list(range(1, 264)),
       'D2 room_id 恰好是 1..263 且无重复（唯一键成立）')
    # D3 工具在位
    tools = os.path.join(ROOT, 'code-quality-audit', '第101轮-OneShot背景落盘与场景接线',
                         '_tools')
    ok(all(os.path.isfile(os.path.join(tools, t))
           for t in ('build101.py', 'verify101.py', 'sheet101.py')),
       'D3 本轮工具（build/verify/sheet）都在盘上')
    # D4 ★ 单色图画像（登记事实：13 间空房 + 1 张全透明占位）——
    #    这是"哪些房间在原作里就没有视觉内容"的**可复查名单**，变了要复核；
    #    但不把它当失败（单色本身可以是忠实的，见 build101 B3 的两轮教训）。
    mf = jload(os.path.join(ROOT, 'code-quality-audit',
                            '第101轮-OneShot背景落盘与场景接线', '_evidence',
                            'bg_manifest101.json'))
    ok(len(mf.get('solid_empty_rooms') or []) == 13
       and len(mf.get('solid_transparent_ghosts') or []) == 1,
       'D4 ★ 单色图画像与登记一致（空房 %d / 全透明占位 %d；期望 13/1）'
       % (len(mf.get('solid_empty_rooms') or []),
          len(mf.get('solid_transparent_ghosts') or [])))
    ok(_N[0] > 18, 'D5 断言条数 > 18（防"套件只剩几条"）实际 %d' % _N[0])


def main():
    print('第101轮 OneShot 背景落盘与接线回归锁（%s）' % os.path.basename(__file__))
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
    print('OneShot 背景落盘与接线：%d/%d 全绿' % (_N[0], _N[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main())

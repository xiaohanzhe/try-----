# -*- coding: utf-8 -*-
u"""key116_doors.py —— 门贴图的黑底结构分析 + 去黑（**只产新文件，不动原件**）。

为什么需要它（第116轮，用户逐字）
----------------------------------
「黑底也没去干净」「你门的形式也没用对」

逐帧取证已确认：门 D 的贴图 `spr_giantdarkdoor_0` 是**不透明黑卡片 + 金色门框**
（180×155，纯黑 82.6%），贴到桌面上就是**一块实心黑**；门 C
`ut_castle_realdoor_0`（44×99，纯黑 76.4%）同理。真机像素：门 D 矩形内纯黑比
中位 **0.820**、门 C 区域几乎全被黑吃掉。

用法
----
  # 1) 只分析 + 出棋盘对照图
  python key116_doors.py
  # 2) 顺便产出去黑变体（写到 assets/scenes/objs_key/，**不覆盖原件**）
  python key116_doors.py --key
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
PKG = os.path.abspath(os.path.join(ROUND, '..', '..', 'ralsei_pet'))
OBJS = os.path.join(PKG, 'assets', 'scenes', 'objs')
OUT = os.path.join(ROUND, '_evidence', 'rec116', 'analysis')
os.makedirs(OUT, exist_ok=True)

import cv2                                                    # noqa: E402

#: 纯黑判定阈值（max channel）。原作这些门贴图的"黑底"是 (0,0,0,255)。
BLACK_MAX = 26
#: 软边：max channel 从 `BLACK_MAX` 到 `SOFT_MAX` 线性过渡，避免锯齿。
SOFT_MAX = 96

#: 只分析/出图用的候选（含不产变体的，用于对照）。
DOORS = ['spr_darkdoor_0.png', 'niko_door_portal.png',
         'ut_castle_realdoor_0.png', 'spr_giantdarkdoor_0.png',
         'spr_giantdarkdoor_1.png', 'spr_shortcut_door_0.png']

#: ★★★ 只产这**两张**桌面变体。理由（第116轮取证）：
#:   · `spr_giantdarkdoor_0.png` **还被 `_zone.ch1.castle_town.json`（暗世界城堡镇）
#:     用着** —— 在暗世界里那面黑门洞是**对的**（暗世界背景本就黑）。
#:     ⇒ 绝不能原地覆盖，否则把世界内的门也扣成空框。
#:   · 用户第112轮逐字「**只针对桌面上的 ut 和三角符文的门**」⇒ 桌面变体
#:     只服务这两扇，世界内贴图**一字不动**。
#:   · 门 A（`spr_darkdoor_0`）近黑占 18.8% 且**与边框连通 93.1%**（就是门板本身）
#:     ⇒ 扣黑会把门板吃掉、只剩描边（棋盘对照图实证）⇒ **不产**。
#:   · 门 B（`niko_door_portal`）连通比仅 2.7%、扣完与原件几乎无差 ⇒ **不产**。
KEYED = [
    ('ut_castle_realdoor_0.png', 'desk_door_ut.png'),
    ('spr_giantdarkdoor_0.png', 'desk_door_deltarune.png'),
]
#: 桌面变体落到**同一个 `objs/` 目录**（不另开子目录：少一个可能撞"资产清单"
#: 类判据的面），文件名与 `desktop.json` 的物件 id 对齐（`desk_door_ut` /
#: `desk_door_deltarune`），自解释。
OUTDIR = OBJS


def _load(name):
    p = os.path.join(OBJS, name)
    if not os.path.exists(p):
        return None
    a = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    return a


def _stats(a):
    if a is None or a.ndim != 3:
        return None
    b, g, r = a[:, :, 0].astype(np.int32), a[:, :, 1].astype(np.int32), \
        a[:, :, 2].astype(np.int32)
    al = a[:, :, 3]
    mx = np.maximum(np.maximum(b, g), r)
    opaque = al >= 250
    transp = al <= 5
    black = (mx <= BLACK_MAX) & opaque
    return {
        'wh': (a.shape[1], a.shape[0]),
        'opaque': float(opaque.mean()),
        'transp': float(transp.mean()),
        'black_of_all': float(black.mean()),
        'black_of_opaque': float(black.sum() / max(1, opaque.sum())),
    }


def _border_connected_black(mask):
    u"""纯黑区域里**与图片边框连通**的部分占纯黑的比例。

    ★ 为什么要分开算：`spr_giantdarkdoor` 的纯黑既在画面四角（背景）**也在**
      金色门框内部（门芯）。只去"与边框连通"的 ⇒ 门芯仍是黑的（用户仍会说
      「黑底没去干净」）；两处都去 ⇒ 只剩金色门框线（= 用户 112 轮自己说的
      「门框似的那个门」）。
    """
    m = mask.astype(np.uint8)
    h, w = m.shape
    ff = m.copy()
    mask2 = np.zeros((h + 2, w + 2), np.uint8)
    # 从四条边上的纯黑点起做 flood fill
    seeds = []
    for x in range(w):
        if m[0, x]:
            seeds.append((x, 0))
        if m[h - 1, x]:
            seeds.append((x, h - 1))
    for y in range(h):
        if m[y, 0]:
            seeds.append((0, y))
        if m[y, w - 1]:
            seeds.append((w - 1, y))
    tot = int(m.sum())
    if not seeds or tot == 0:
        return 0.0, tot
    reach = np.zeros((h, w), np.uint8)
    for x, y in seeds:
        if reach[y, x]:
            continue
        m2 = m.copy()
        mask2[:] = 0
        cv2.floodFill(m2, mask2, (x, y), 2)
        # floodFill 只填 4-连通同值区域
        reach |= (m2 == 2).astype(np.uint8)
    return float(reach.sum() / max(1, tot)), tot


def _checker(w, h, cell=12):
    yy, xx = np.mgrid[0:h, 0:w]
    c = (((yy // cell) + (xx // cell)) % 2).astype(np.uint8)
    return np.where(c[:, :, None] > 0, 205, 150).astype(np.uint8) * \
        np.ones((1, 1, 3), np.uint8)


def _composite(a, scale=1):
    h, w = a.shape[0], a.shape[1]
    bg = _checker(w, h).astype(np.float32)
    al = (a[:, :, 3:4].astype(np.float32) / 255.0)
    rgb = a[:, :, 2::-1].astype(np.float32)      # BGRA → RGB
    out = rgb * al + bg * (1.0 - al)
    o = np.clip(out, 0, 255).astype(np.uint8)
    if scale != 1:
        o = cv2.resize(o, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)
    return o


def _key(a):
    u"""把**近黑**像素变透明；`BLACK_MAX..SOFT_MAX` 之间线性给 alpha（软边）。"""
    o = a.copy().astype(np.float32)
    rgb = o[:, :, :3]
    mx = rgb.max(axis=2)
    al = o[:, :, 3].copy()
    # 参考亮度：用 max channel（纯黑 0；金色 ≈ 200+）
    keep = np.clip((mx - BLACK_MAX) / float(max(1, SOFT_MAX - BLACK_MAX)),
                   0.0, 1.0)
    o[:, :, 3] = np.clip(al * keep, 0, 255)
    return o.astype(np.uint8)


def _write(path, img):
    ext = os.path.splitext(path)[1]
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise RuntimeError('imencode fail %s' % path)
    with open(path, 'wb') as fh:          # ★ 中文路径必须手写盘，见项目铁律
        fh.write(buf.tobytes())
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise RuntimeError('写盘未落地: %s' % path)
    return os.path.getsize(path)


def main():
    do_key = '--key' in sys.argv
    lines = []
    tiles = []
    for nm in DOORS:
        a = _load(nm)
        if a is None:
            lines.append(u'%-30s  ✗ 缺文件' % nm)
            continue
        st = _stats(a)
        if st is None:
            lines.append(u'%-30s  ✗ 非 BGRA' % nm)
            continue
        mx = a[:, :, :3].max(axis=2)
        black = (mx <= BLACK_MAX) & (a[:, :, 3] >= 250)
        conn, tot = _border_connected_black(black)
        lines.append(
            u'%-30s %3dx%-3d 不透明=%.3f 全透=%.3f 纯黑(占全图)=%.3f '
            u'纯黑(占不透明)=%.3f | 纯黑里"与边框连通"=%.3f'
            % (nm, st['wh'][0], st['wh'][1], st['opaque'], st['transp'],
               st['black_of_all'], st['black_of_opaque'], conn))
        tiles.append((nm, a))

    # ---- 只产 `KEYED` 里那两张桌面变体（**绝不覆盖原件**）----
    if do_key:
        for src, dst in KEYED:
            a = _load(src)
            if a is None:
                raise SystemExit('✗ 缺源图 %s' % src)
            k = _key(a)
            p = os.path.join(OUTDIR, dst)
            sz = _write(p, k)
            kst = _stats(k)
            sst = _stats(a)
            # ★ 尺寸/不透明/纯黑三件事都要打印：**尺寸必须不变**（门摆位按
            #   素材原尺寸算，改了尺寸门的大小就变了 —— 用户「各用原尺寸」）。
            ok_size = kst['wh'] == sst['wh']
            lines.append(u'⇒ 桌面变体 objs/%-26s %dx%d（尺寸不变=%s） '
                         u'不透明 %.3f→%.3f  纯黑 %.3f→%.3f  (%.0f B)'
                         % (dst, kst['wh'][0], kst['wh'][1],
                            u'是' if ok_size else u'**否**',
                            sst['opaque'], kst['opaque'],
                            sst['black_of_all'], kst['black_of_all'], sz))
            if not ok_size:
                raise SystemExit('✗ 变体尺寸被改：%s' % dst)

    # 棋盘对照图：每行 [原图 | 去黑后]
    rows = []
    for nm, a in tiles:
        left = _composite(a, 2)
        right = _composite(_key(a), 2) if do_key else np.zeros_like(left)
        sep = np.full((left.shape[0], 8, 3), 255, np.uint8)
        r = np.hstack([left, sep, right])
        lab = np.full((26, r.shape[1], 3), 30, np.uint8)
        cv2.putText(lab, nm[:34], (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (255, 255, 255), 1, cv2.LINE_AA)
        rows.append(np.vstack([lab, r]))
    W = max(r.shape[1] for r in rows)
    H = sum(r.shape[0] for r in rows) + 8 * (len(rows) - 1)
    canvas = np.full((H, W, 3), 60, np.uint8)
    y = 0
    for r in rows:
        canvas[y:y + r.shape[0], 0:r.shape[1]] = r
        y += r.shape[0] + 8
    tag = 'key' if do_key else 'raw'
    p = os.path.join(OUT, 'doors116_%s.png' % tag)
    # ★★ `_composite` 产出的是 **RGB**，而 `cv2.imencode` 要 **BGR**
    #   ⇒ 落盘前换回来（上一版没换，金框被显示成蓝框 —— 只是"看图的坑"，
    #     但会让人误判颜色）。
    sz = _write(p, canvas[:, :, ::-1])
    lines.append(u'')
    lines.append(u'棋盘对照图（左=原件 右=去黑；2 倍最近邻）已写 %s (%d B)' % (p, sz))
    txt = u'\n'.join(lines) + u'\n'
    with open(os.path.join(OUT, 'doors116_%s.txt' % tag), 'w',
              encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    sys.stdout.write(txt)


if __name__ == '__main__':
    main()

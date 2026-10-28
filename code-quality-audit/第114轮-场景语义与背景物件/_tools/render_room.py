# -*- coding: utf-8 -*-
u"""按 `.tmx` + 解出来的**真图集**重渲染房间 —— 背景物件的唯一正确画法。

为什么必须走这条路（第114轮实测）：
  · 从 tmx 分层画：L0 地板、L1 物件各画各的 ⇒ **拆掉某个物件只是少画那几格**，
    底下 L0 的地板天然露出来，不存在“洞”。
  · 拿仓库里 `assets/scenes/bg/oneshot_map*.png`（**合成后**的整张图）当底图去“整格复制地板”
    填空，砖缝接缝 9.31 → 81.49（恶化 9 倍）。
  · ⚠️ 但那批 PNG 本身**是对的**（别被上一句误导）：把底色层 `oneshot_map_colors.json` 补上后，
    `bg_base114.py` 实测 **222/263 间逐像素差异 ≤1%**（中位 0.0000，`map1` = 0.0000），
    剩 41 间 1%~12.5% 的差异几乎全在**半透明瓦片**（我给 alpha 109~115、PNG 给 192~193）
    —— 合成算法差异，不是画错。**不构成替换 PNG 的理由。**

图集从哪来（`.xnb` 必须先解包，本脚本不碰 xnb）：
    env -u NODE_OPTIONS -u NODE_PATH D:/xnbcil/xnbcli.exe unpack <Content/tilesets> <out_tiles>
    env -u NODE_OPTIONS -u NODE_PATH D:/xnbcil/xnbcli.exe unpack <Content/autotiles> <out_auto>
  ★ 必须带 `env -u NODE_OPTIONS` —— 本机环境里 `NODE_OPTIONS` 指向 WorkBuddy 的 shim，
    会让 pkg 打包的 exe 直接 `Cannot find module ... node-language-shim.cjs`。

★★ 图集按 `Content/<tilesets|autotiles>/<名>` **分桶取图**：两边都有 `blank.png` / `black.png`
  但内容不同，只认 basename 会静默拿错图（画出来“有东西”，但每一格都是错的）。

用法：
    python render_room.py --atlas D:/_tmp/xnb_tiles_out --auto D:/_tmp/xnb_auto_out \
        --out D:/_tmp/render_tmx --maps 2,3,4
    python render_room.py ... --all                 # 263 间全渲
    python render_room.py ... --maps 2 --drop 1:11,14,20,16   # 演示：抠掉 L1 一块
"""
import argparse
import os
import sys

import oneshot_tmx as T

try:
    from PIL import Image
except ImportError:                       # pragma: no cover
    Image = None


def atlas_path(d, atlas_dir, auto_dir):
    u"""按 `image source` 的**目录**选桶，再取同名文件。取不到返 None（由调用方报出来）。"""
    src = (d.get('img') or '').replace('\\', '/')
    if not src:
        return None
    base = os.path.basename(src)
    parts = [p for p in src.split('/') if p]
    kind = parts[-2] if len(parts) >= 2 else ''
    if kind == 'autotiles':
        roots = [auto_dir, atlas_dir]
    elif kind == 'tilesets':
        roots = [atlas_dir, auto_dir]
    else:
        roots = [atlas_dir, auto_dir]
    for r in roots:
        if not r:
            continue
        p = os.path.join(r, base)
        if os.path.isfile(p):
            return p
    return None


def render(num, atlas_dir, auto_dir, drop=None, out_path=None):
    u"""画一张图。`drop` = {(layer_index, x, y)}，用来演示“把这几个格子从物件层拿掉”。"""
    if Image is None:
        raise RuntimeError(u'需要 Pillow')
    m = T.load_map(num)
    W, H = m['W'] * m['TW'], m['H'] * m['TH']
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    cache, missing = {}, set()
    drop = drop or set()
    drawn = dropped = 0
    for li, ly in enumerate(m['layers']):
        op = ly.get('opacity', 1.0)
        lw = ly['w']
        for i, g in enumerate(ly['data']):
            r = T.gid_to(m, g)
            if not r:
                continue
            tsx, d, lid = r
            x, y = i % lw, i // lw
            if (li, x, y) in drop:
                dropped += 1
                continue
            if tsx not in cache:
                p = atlas_path(d, atlas_dir, auto_dir)
                cache[tsx] = Image.open(p).convert('RGBA') if p else None
                if cache[tsx] is None:
                    missing.add(os.path.basename(tsx))
            at = cache[tsx]
            if at is None:
                continue
            tw, th, cols = d['tw'], d['th'], d['cols']
            sx, sy = (lid % cols) * tw, (lid // cols) * th
            tile = at.crop((sx, sy, sx + tw, sy + th))
            if op < 1.0:
                tile.putalpha(tile.getchannel('A').point(lambda v: int(v * op)))
            canvas.alpha_composite(tile, (x * m['TW'], y * m['TH']))
            drawn += 1
    if out_path:
        d = os.path.dirname(out_path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        canvas.save(out_path)
    return {'num': num, 'size': canvas.size, 'drawn': drawn, 'dropped': dropped,
            'missing': sorted(missing), 'path': out_path, 'img': canvas}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--atlas', required=True, help='解出来的 tilesets 目录')
    ap.add_argument('--auto', default='', help='解出来的 autotiles 目录')
    ap.add_argument('--out', default='', help='输出目录（不给就只统计不落盘）')
    ap.add_argument('--maps', default='', help='逗号分隔的房间号')
    ap.add_argument('--all', action='store_true', help='263 间全渲')
    ap.add_argument('--drop', default=[], action='append',
                    help='L:x0,y0,x1,y1 —— 把该层这个 bbox 内的格子拿掉（演示“拆走物件”）')
    a = ap.parse_args(argv)

    if a.all:
        nums = sorted(int(f[3:-4]) for f in os.listdir(T.MAPS)
                      if f.startswith('map') and f.endswith('.tmx'))
    else:
        nums = [int(x) for x in a.maps.split(',') if x.strip()] or [2]

    drop = set()
    for spec in a.drop:
        li, box = spec.split(':')
        x0, y0, x1, y1 = [int(v) for v in box.split(',')]
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                drop.add((int(li), x, y))

    bad = 0
    for n in nums:
        dst = os.path.join(a.out, 'map%d.png' % n) if a.out else None
        info = render(n, a.atlas, a.auto, drop, dst)
        if info['missing']:
            bad += 1
            print(u'map%-4d 缺图集：%s' % (n, ','.join(info['missing'])))
        if len(nums) <= 20:
            print(u'map%-4d %dx%d 画 %d 格 拿掉 %d 格%s'
                  % (n, info['size'][0], info['size'][1], info['drawn'],
                     info['dropped'], (u'  → %s' % dst) if dst else ''))
    print(u'合计 %d 间；缺图集的 %d 间' % (len(nums), bad))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))

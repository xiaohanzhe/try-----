# -*- coding: utf-8 -*-
u"""第121轮侦察②：已被第120轮判为"不画"的对象，**在烘出来的图里到底有没有像素**。

为什么必须做这步：
    第120轮的可见性门是「资产 `vis=False` ⇒ 不画」。但 GM 的 `visible` 只约束
    **自动绘制**（无 Draw 事件时），自定义 Draw 事件**照跑**。所以这条门可能
    把"对象只是隐形触发器、画面靠 tile 画"和"真的漏画了"混为一谈。

判据（可判定、不靠眼）：
    取该实例的 sprite 原点补偿后的矩形 `(x-ox, y-oy, w, h)`，在烘好的 PNG 上
    统计"非底色/非纯透明"像素比例。
      · 若 ≈0 ⇒ 该位置**什么都没画** ⇒ 对象确实不该由自己画（画面在别处，多为 tile）
      · 若 >0 ⇒ 那个位置**有东西** ⇒ 要么是它自己画的，要么是别的层画的（需人眼复核）

用法：python probe_missing121.py [--room room_ruins1]
"""
import collections
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROUND120 = os.path.join(os.path.dirname(ROUND), '第120轮-ut场景背景与物件', '_tools')
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
BAKED = r'D:\_wb_tmp\dw_ut\ut\_out\baked'

sys.path.insert(0, ROUND120)
sys.path.insert(0, os.path.join(REPO, 'ralsei_pet', 'modules'))

import bake120 as B              # noqa: E402
import item_interact as II       # noqa: E402

from PIL import Image            # noqa: E402


def main(argv):
    only = None
    if '--room' in argv:
        only = argv[argv.index('--room') + 1]

    viz = os.path.join(ROUND120, '..', '_evidence', 'raw', 'ut', 'viz120.ut.tsv')
    rooms, layers, lbg, lsp, spr = B.load_viz(os.path.normpath(viz))
    objs = B.load_objmap('ut')
    spr_origin = {}
    for (nm, _f), v in spr.items():
        spr_origin.setdefault(nm, (v['ox'], v['oy']))
    for o in objs.values():
        o['ox'], o['oy'] = spr_origin.get(o['spr'], (0, 0))
        o['w'], o['h'] = spr.get((o['spr'], 0), {}).get('w', 0), spr.get((o['spr'], 0), {}).get('h', 0)
    draw_kind = B.load_draw('ut')
    hidden = B.load_hidden('ut')
    insts = B.load_inst('ut')

    rows = []
    for ri, items in insts.items():
        room = rooms.get(ri)
        if room is None:
            continue
        if only and room['name'] != only:
            continue
        p = os.path.join(BAKED, 'ut_%s.png' % room['name'])
        if not os.path.isfile(p):
            continue
        im = Image.open(p).convert('RGB')
        for it in items:
            src = it['obj']
            o = objs.get(src)
            if not o or not o['spr']:
                continue
            if o['vis']:
                continue                              # 画了的，不在本探针范围
            if draw_kind.get(src) == 'custom':
                continue                              # 自绘，本来就不该按 sprite 贴
            if src in hidden:
                continue                              # Create 里关了
            rec = II.classify(src)
            kind = rec['kind'] if rec else '(非交互)'
            w, h = o['w'], o['h']
            if w <= 0 or h <= 0:
                continue
            x0 = int(it['x']) - o['ox']
            y0 = int(it['y']) - o['oy']
            box = (max(0, x0), max(0, y0), min(im.width, x0 + w), min(im.height, y0 + h))
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            crop = im.crop(box)
            px = list(crop.getdata())
            # 底色 = 该点最常见的颜色（房间底色/地板），用它当"空"的基线
            base = collections.Counter(px).most_common(1)[0][0]
            non = sum(1 for c in px if c != base)
            rows.append((room['name'], src, kind, x0, y0, w, h, non, len(px)))

    print('== 资产 vis=False 且有 sprite、非自绘、非 Create 隐藏的实例 ==')
    print('共 %d 条，分布在 %d 间房' % (len(rows), len(set(r[0] for r in rows))))
    byk = collections.Counter(r[2] for r in rows)
    print('按 kind: %s' % dict(sorted(byk.items(), key=lambda kv: -kv[1])))
    empty = [r for r in rows if r[7] * 100.0 / r[8] < 1.0]
    filled = [r for r in rows if r[7] * 100.0 / r[8] >= 1.0]
    print()
    print('★ 位置<b>几乎没像素</b>（<1%%）: %d 条 → 画面在别处（多为 tile），漏画不成立' % len(empty))
    print('★ 位置<b>有像素</b>（>=1%%）  : %d 条 → 需人眼复核是否已有内容' % len(filled))
    ck = collections.Counter(r[2] for r in filled)
    print('   有像素的按 kind: %s' % dict(sorted(ck.items(), key=lambda kv: -kv[1])))
    for r in filled[:12]:
        print('   %-26s %-34s %-10s pos=(%d,%d) %dx%d 非底色 %d/%d'
              % (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))

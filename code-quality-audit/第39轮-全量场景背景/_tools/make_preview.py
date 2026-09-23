# -*- coding: utf-8 -*-
"""
第 39 轮 · 生成 157 张真背景的**预览页 + 缩略总览图**。

为什么要总览图：肉眼扫一眼就能看出"这些图到底像不像一个房间的画面"——
比"断言文件存在"强得多。本项目吃过"能从运行时读到的量就别推算"的教训，
这里同理：**能直接看的就别只信统计**。
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bg_common as C   # noqa: E402

from PIL import Image, ImageDraw, ImageFont   # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
BG = os.path.join(SCENES, 'bg')
EV = os.path.join(ROUND, '_evidence')
MAN = os.path.join(EV, '真背景导出清单.json')

THUMB_H = 96
COLS = 8
PAD = 6
CAP_H = 14

HOW_CN = C.HOW_CN


def main():
    man = json.load(io.open(MAN, encoding='utf-8'))
    rows = man['rows']
    rows.sort(key=lambda r: (r['chapter'], r['scene_id']))

    # ---------------- 缩略总览图 ----------------
    cells = []
    for i, r in enumerate(rows, 1):
        p = os.path.join(BG, r['file'])
        try:
            im = Image.open(p).convert('RGBA')
        except Exception:
            im = Image.new('RGBA', (THUMB_H, THUMB_H), (255, 0, 0, 255))
        w = max(1, int(im.width * THUMB_H / float(im.height)))
        cells.append((i, im.resize((w, THUMB_H), Image.NEAREST)))

    colw = max(c[1].width for c in cells) + PAD
    n = len(cells)
    nrows = (n + COLS - 1) // COLS
    W = COLS * colw + PAD
    H = nrows * (THUMB_H + CAP_H + PAD) + PAD
    mont = Image.new('RGBA', (W, H), (18, 20, 26, 255))
    dr = ImageDraw.Draw(mont)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    idx_lines = []
    for k, (i, im) in enumerate(cells):
        cx = PAD + (k % COLS) * colw
        cy = PAD + (k // COLS) * (THUMB_H + CAP_H + PAD)
        bgc = Image.new('RGBA', (im.width, THUMB_H), (40, 44, 54, 255))
        bgc.alpha_composite(im)
        mont.alpha_composite(bgc, (cx, cy))
        dr.text((cx, cy + THUMB_H + 1), '#%d' % i, fill=(210, 214, 222), font=font)
        idx_lines.append('#%-4d %-46s %-16s %s'
                         % (i, rows[k]['scene_id'], rows[k]['asset'], rows[k]['file']))
    mp = os.path.join(EV, '真背景总览.png')
    mont.convert('RGB').save(mp, quality=92)

    with io.open(os.path.join(EV, '真背景总览_索引.txt'), 'w', encoding='utf-8',
                 newline='\n') as f:
        f.write('真背景总览图编号索引（与 真背景总览.png 一一对应）\n')
        f.write('=' * 78 + '\n')
        f.write('\n'.join(idx_lines) + '\n')

    # ---------------- 预览页 ----------------
    h = []
    h.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">')
    h.append('<title>第39轮 · 场景真背景预览</title><style>')
    h.append('body{background:#12141a;color:#e8e8ea;font:14px/1.6 -apple-system,"Segoe UI",'
             '"Microsoft YaHei",sans-serif;margin:0;padding:24px}')
    h.append('h1{font-size:20px;margin:0 0 6px}h2{font-size:16px;margin:28px 0 10px;'
             'border-left:3px solid #5b8def;padding-left:8px}')
    h.append('.meta{color:#9aa0b0;font-size:13px;margin-bottom:14px}')
    h.append('.warn{background:#2a2418;border:1px solid #6b5a1f;color:#f0d489;'
             'padding:10px 12px;border-radius:6px;margin:12px 0;font-size:13px}')
    h.append('.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}')
    h.append('.card{background:#1b1f28;border:1px solid #2a2f3a;border-radius:8px;overflow:hidden}')
    h.append('.card img{width:100%;height:150px;object-fit:contain;display:block;background:#0a0c10}')
    h.append('.cap{padding:8px 10px}.cap b{font-size:12px;font-weight:600;display:block;'
             'word-break:break-all}')
    h.append('.cap span{display:block;color:#9aa0b0;font-size:11px;margin-top:3px;word-break:break-all}')
    h.append('.tag{display:inline-block;padding:1px 6px;border-radius:4px;background:#2e7d32;'
             'color:#fff;font-size:11px;margin-top:5px}')
    h.append('</style></head><body>')
    h.append('<h1>第39轮 · 全量场景「真背景」预览</h1>')
    h.append('<div class="meta">共 %d 张，全部为**原作 PNG 原样复制**（不缩放、不裁切、不合成）'
             '｜ 数据来源：UTMT 反编译的 room.Layers 里房间自带的背景精灵</div>'
             % len(rows))
    h.append('<div class="warn">⚠️ 另有 %d 个场景的原作房间**没有背景精灵**（画面靠瓦片/物件拼），'
             '本轮<strong>没有</strong>给它们填"区域代表素材"式的近似图 —— '
             '是否要近似、怎么近似，等你定口径。<br>'
             '⚠️ <strong>原作房间本身就有尺寸分级</strong>：真背景里多数素材与房间是 '
             '<code>1:1</code>，但房间有 <code>320×240</code> 的小房间、'
             '<code>640×480</code> 的标准房间、以及更宽的滚动房间；少数房间比素材大得多'
             '（素材宽度不足房间一半）⇒ 那些层是<strong>平铺/重复绘制</strong>的。'
             '所以 P1 渲染层<strong>不能假设房间都是 640×480</strong>，需要按房间尺寸适配，'
             '并且需要背景层的 <code>x/y/xscale/yscale/tiled</code> 几何 —— '
             '现有反编译脚本尚未导出这些字段。</div>'
             % man['approx'])
    for ch in C.CHS:
        rs = [r for r in rows if r['chapter'] == ch]
        if not rs:
            continue
        h.append('<h2>%s · %d 张真背景</h2><div class="grid">' % (ch, len(rs)))
        for r in rs:
            src = os.path.relpath(os.path.join(BG, r['file']), ROUND).replace('\\', '/')
            h.append('<div class="card"><img src="%s" alt="%s" loading="lazy">'
                     '<div class="cap"><b>%s</b>'
                     '<span>%s ｜ room %s ｜ 素材 %s</span>'
                     '<span>%s ｜ %s ｜ 房间 %sx%s</span>'
                     '<span class="tag">%s</span></div></div>'
                     % (src, r['scene_id'], r['scene_id'], r['area'],
                        r['room_id'], r['asset'],
                        r['file'], r['mode'], r.get('room_w'), r.get('room_h'),
                        HOW_CN.get(r['how'], r['how'])))
        h.append('</div>')
    h.append('</body></html>')
    hp = os.path.join(ROUND, '第39轮-场景真背景预览.html')
    with io.open(hp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(h))

    print('总览图 -> %s  (%dx%d, %d 格)' % (mp, W, H, n))
    print('索引   -> %s' % os.path.join(EV, '真背景总览_索引.txt'))
    print('预览页 -> %s' % hp)


if __name__ == '__main__':
    main()

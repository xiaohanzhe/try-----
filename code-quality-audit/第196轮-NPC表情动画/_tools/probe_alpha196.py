# -*- coding: utf-8 -*-
"""第196轮探针 7：**像素级**体检 —— 给"这张帧能不能用"找可量化的判据。

为什么必须走到像素这一层
------------------------
看图人工核对时抓到的三类废帧，都是"文件名对、尺寸对、画出来不对"：
  · **不透明背景**：`spr_susie_shocked_lw_0` 带整块绿底 ⇒ 小窗里是个绿方块；
  · **两个主体**：`spr_susie_grabsmile_0`（43×43）是"抓着什么东西笑"，
    挂到 Susie 身上会多画一块；
  · **夹带道具**：`spr_kris_door_laugh_0` 是"隔着门笑"（带门）、
    `spr_cutscene_01_toriel_laugh_pie_tin_0` 是"端着派盘笑"（带盘子）。
三者都能用 alpha 通道量出来，不必靠眼睛一格格看：

  ① `opaque_ratio` = alpha>32 的像素数 / bbox 面积
     —— 人形像素画不会把 bbox 填满；贴近 1.0 就是"整块底色"。
  ② `gap` = bbox 内部**整列全透明**的最长连续列数，且两侧都有实质像素
     —— 一个身体中间不会断开 3 列以上；断开就是并排两个东西。
  ③ `area_ratio` = 实心像素数 / 该角色走路帧的实心像素数
     —— 道具会让"这个人的像素量"突然翻倍（门、盘子、抱着的箱子）。

★ 本脚本**只测量、不判定**：阈值要按实测分布来定，不能拍脑袋。
"""
from __future__ import print_function

import io
import json
import os
import sys
from collections import defaultdict

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
DROP = os.path.join(PET, 'assets', 'sprites', 'dr')
FRAMES = os.path.join(DROP, '_npc_frames.json')
ANIMS = os.path.join(DROP, '_npc_anims.json')

ALPHA_MIN = 32


def stats(path):
    im = Image.open(path)
    im.load()
    im = im.convert('RGBA')
    w, h = im.size
    px = im.load()
    mask = [[px[x, y][3] > ALPHA_MIN for x in range(w)] for y in range(h)]
    cols = [sum(mask[y][x] for y in range(h)) for x in range(w)]
    xs = [x for x in range(w) if cols[x]]
    if not xs:
        return None
    x0, x1 = xs[0], xs[-1]
    ys = [y for y in range(h) if any(mask[y][x] for x in range(x0, x1 + 1))]
    y0, y1 = ys[0], ys[-1]
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    opaque = sum(cols[x] for x in range(x0, x1 + 1))
    ratio = opaque / float(bw * bh)
    # 内部最长"整列全透明"连续段（只在有像素的列区间内找）
    best = cur = 0
    best_at = -1
    for x in range(x0, x1 + 1):
        if cols[x] == 0:
            cur += 1
            if cur > best:
                best, best_at = cur, x
        else:
            cur = 0
    return {'w': w, 'h': h, 'bw': bw, 'bh': bh, 'opaque': opaque,
            'ratio': round(ratio, 3), 'gap': best, 'gap_at': best_at,
            'x0': x0, 'y0': y0}


def main():
    with io.open(FRAMES, 'r', encoding='utf-8') as f:
        frames_man = json.load(f).get('characters') or {}
    with io.open(ANIMS, 'r', encoding='utf-8') as f:
        anim_man = json.load(f).get('characters') or {}

    # 基线：每个角色走路帧 down 的前 4 帧
    base = {}
    for cid, e in frames_man.items():
        fr = (e or {}).get('frames') or {}
        d = 'down' if 'down' in fr else (sorted(fr)[0] if fr else None)
        if not d:
            continue
        ss = []
        for row in fr[d][:4]:
            s = stats(os.path.join(DROP, cid, row['f']))
            if s:
                ss.append(s)
        if ss:
            base[cid] = {
                'ratio': round(sum(x['ratio'] for x in ss) / len(ss), 3),
                'opaque': int(sum(x['opaque'] for x in ss) / len(ss)),
                'gap': max(x['gap'] for x in ss),
                'bw': max(x['bw'] for x in ss),
            }

    print('=' * 96)
    print('走路帧基线（同一角色的"正常"长什么样）')
    print('=' * 96)
    print('%-12s %-8s %-8s %-6s %-5s' % ('角色', 'ratio', 'opaque', 'maxgap', 'bw'))
    for cid in sorted(base):
        b = base[cid]
        print('%-12s %-8s %-8s %-6d %-5d' % (cid, b['ratio'], b['opaque'],
                                             b['gap'], b['bw']))

    print('\n' + '=' * 96)
    print('候选帧体检（★ 标记的是明显偏离基线的）')
    print('=' * 96)
    flagged = defaultdict(list)
    for cid in sorted(anim_man):
        b = base.get(cid)
        if not b:
            continue
        print('\n### %s' % cid)
        for emo in sorted(anim_man[cid]):
            for dd in sorted(anim_man[cid][emo]):
                for i, row in enumerate(anim_man[cid][emo][dd]):
                    p = os.path.join(DROP, cid, row['f'])
                    s = stats(p)
                    if not s:
                        print('    [空] %s %s[%d] 无像素' % (emo, dd, i))
                        continue
                    tags = []
                    if s['ratio'] >= 0.85:
                        tags.append('不透明底')
                    if s['gap'] >= 3:
                        tags.append('两个主体')
                    if b['opaque'] and s['opaque'] > 1.8 * b['opaque']:
                        tags.append('像素量%0.1fx' % (s['opaque'] / float(b['opaque'])))
                    if s['bw'] > 1.6 * b['bw']:
                        tags.append('过宽%0.1fx' % (s['bw'] / float(b['bw'])))
                    flag = ('★' + '/'.join(tags)) if tags else ''
                    print('    %-10s %-6s[%d] %2dx%-2d bbox %2dx%-2d ratio=%-5s '
                          'gap=%-2d opaque=%-4d %s  %s'
                          % (emo, dd, i, s['w'], s['h'], s['bw'], s['bh'],
                             s['ratio'], s['gap'], s['opaque'],
                             row['src_name'][:42], flag))
                    if tags:
                        flagged[cid].append((emo, dd, i, row['src_name'], '/'.join(tags)))

    print('\n' + '=' * 96)
    print('汇总：被判为可疑的帧')
    print('=' * 96)
    n = 0
    for cid in sorted(flagged):
        for emo, dd, i, fn, why in flagged[cid]:
            n += 1
            print('  %-12s %-10s %-6s[%d] %-46s %s' % (cid, emo, dd, i, fn, why))
    print('\n可疑合计 %d 帧' % n)
    return 0


if __name__ == '__main__':
    sys.exit(main())

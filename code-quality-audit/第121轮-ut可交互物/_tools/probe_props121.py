# -*- coding: utf-8 -*-
u"""第121轮侦察：ut 到底有多少**可交互物**该进 `objects`。

★ 纪律：**直接 import `bake120` 的载入函数**，不重写一份。
   （本项目吃过"同一判据两份实现、三种结论"的亏；第120轮的三层可见性过滤
   已经写在 bake120 里，这里必须复用它，否则就是第二份口径。）

输出：按 kind 分类的可交互实例数 / 有 sprite 的 / 被三层过滤掉的 / 无原点的。
用法：python probe_props121.py [ut|outertale]
"""
import io
import os
import sys
import collections

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROUND120 = os.path.join(os.path.dirname(ROUND), '第120轮-ut场景背景与物件', '_tools')
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

sys.path.insert(0, ROUND120)
sys.path.insert(0, os.path.join(REPO, 'ralsei_pet', 'modules'))

import bake120 as B              # noqa: E402
import item_interact as II       # noqa: E402


def main(argv):
    game = argv[0] if argv else 'ut'
    d = os.path.join(ROUND120)
    viz = os.path.join(d, '..', '_evidence', 'raw', game, 'viz120.%s.tsv' % game)
    viz = os.path.normpath(viz)
    if not os.path.isfile(viz):
        viz = os.path.normpath(os.path.join(d, '..', '_evidence', 'raw', game,
                                            'viz120.%s.tsv' % game))
    rooms, layers, lbg, lsp, spr = B.load_viz(viz)
    objs = B.load_objmap(game)
    # ★ 原点：bake120 在 main 里做这一步（SPR 表首帧 → obj 原点），这里照抄同一规则
    spr_origin = {}
    for (nm, _f), v in spr.items():
        spr_origin.setdefault(nm, (v['ox'], v['oy']))
    for o in objs.values():
        o['ox'], o['oy'] = spr_origin.get(o['spr'], (0, 0))
    draw_kind = B.load_draw(game)
    hidden = B.load_hidden(game)
    insts = B.load_inst(game)

    tot = collections.Counter()
    keep = collections.Counter()
    drop = collections.Counter()
    noorigin = []
    frames = collections.Counter()
    for ri, rows in insts.items():
        room = rooms.get(ri)
        if room is None:
            continue
        for it in rows:
            src = it['obj']
            rec = II.classify(src)
            if not (rec and rec['kind'] not in II.NON_INTERACTIVE_KINDS):
                continue
            kind = rec['kind']
            tot[kind] += 1
            o = objs.get(src)
            if not o or not o['spr']:
                drop['无sprite'] += 1
                continue
            if not o['vis']:
                drop['vis=False'] += 1
                continue
            if draw_kind.get(src) == 'custom':
                drop['自绘'] += 1
                continue
            if src in hidden:
                drop['Create里隐藏'] += 1
                continue
            keep[kind] += 1
            frames[o['spr']] += 1
            if o['spr'] not in spr_origin:
                noorigin.append((src, o['spr']))

    print('== %s ==' % game)
    print('可交互实例合计 %d' % sum(tot.values()))
    print('  按 kind : %s' % dict(sorted(tot.items(), key=lambda kv: -kv[1])))
    print('进 objects（过三层过滤）%d' % sum(keep.values()))
    print('  按 kind : %s' % dict(sorted(keep.items(), key=lambda kv: -kv[1])))
    print('被过滤掉 %d：%s' % (sum(drop.values()), dict(drop)))
    print('唯一 sprite %d 张' % len(frames))
    print('缺原点的 sprite %d 个（会按 0,0 贴）%s' % (len(set(noorigin)), sorted(set(s[1] for s in noorigin))[:5]))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))

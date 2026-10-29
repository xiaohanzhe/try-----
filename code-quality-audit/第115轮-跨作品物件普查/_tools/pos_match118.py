# -*- coding: utf-8 -*-
u"""第118轮：产品的 `objects[].pos` 与普查的实例坐标**是不是同一套**。

为什么必须先验：位置分桶（`x < 130`）要拿产品里的实例坐标去代入。
如果产品生成器当年对坐标做过取整/偏移/换算，那"按 x 选文本"从第一步就错，
而且**错得很安静**（大多数 x 条件仍会碰巧成立）。

对照方式：同一 scene 里，按 `src` 分组比较 `pos` 与 `inst_full.tsv` 的 (x,y) 多重集。
"""
import collections
import glob
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(ROUND))
RAW = os.path.join(ROUND, '_evidence', 'raw')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')


def read_tsv(path):
    with io.open(path, encoding='utf-8', errors='replace', newline='') as f:
        lines = f.read().splitlines()
    return [ln.split('\t') for ln in lines if ln.strip()]


def inst_pos(game):
    """room_idx → {obj: [(x, y), ...]}（只收可读物）"""
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    cur = None
    for row in read_tsv(os.path.join(RAW, game, 'inst_full.tsv')):
        if row[0] == 'R' and len(row) >= 3:
            try:
                cur = int(row[1])
            except ValueError:
                cur = None
        elif row[0] == 'I' and cur is not None and len(row) >= 4 and 'readable' in row[1]:
            try:
                out[cur][row[1]].append((int(float(row[2])), int(float(row[3]))))
            except ValueError:
                pass
    return out


def zone_scenes(game):
    """scene_id → {objects: [...]}，以及 original_room_id → scene_id"""
    by_oid = {}
    for p in sorted(glob.glob(os.path.join(SCENES, '_zone.%s.*.json' % game))):
        d = json.loads(io.open(p, encoding='utf-8').read())
        for sid, s in (d.get('scenes') or {}).items():
            oid = s.get('original_room_id')
            if isinstance(oid, int):
                by_oid.setdefault(oid, (sid, s))
    return by_oid


def main(argv):
    game = argv[0] if argv else 'ut'
    ipos = inst_pos(game)
    zones = zone_scenes(game)
    if not ipos or not zones:
        print('[FAIL] 分母为空：inst=%d zone=%d' % (len(ipos), len(zones)))
        return 1

    n_cmp = 0
    n_same = 0
    diffs = []
    for oid, (sid, s) in zones.items():
        objs = s.get('objects') or []
        prod = collections.defaultdict(list)
        for o in objs:
            src = o.get('src')
            pos = o.get('pos')
            if not src or not isinstance(pos, (list, tuple)) or len(pos) < 2:
                continue
            if 'readable' not in src:
                continue
            prod[src].append((int(pos[0]), int(pos[1])))
        for src, plist in prod.items():
            ip = ipos.get(oid, {}).get(src)
            n_cmp += 1
            if ip is not None and sorted(plist) == sorted(ip):
                n_same += 1
            else:
                diffs.append((sid, src, plist, ip))

    print('[%s] 可读物对象组对照 %d 组：完全一致 %d，不一致 %d'
          % (game, n_cmp, n_same, len(diffs)))
    for d in diffs[:8]:
        print('   %s / %s  产品=%s 普查=%s' % d)
    if not n_cmp:
        print('[FAIL] 一组都没对上 —— 产品里没有可读物的 pos，或字段名变了')
        return 1
    ratio = n_same / float(n_cmp)
    print('')
    print('[%s] 坐标同一套（一致率 %.1f%%，下界 95%%）'
          % ('PASS' if ratio >= 0.95 else 'FAIL', ratio * 100))
    return 0 if ratio >= 0.95 else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))

# -*- coding: utf-8 -*-
"""追查 objects 守恒缺口：2043 vs 2067 少 24 条，丢在哪。

方法（**双向集合差**）：
  · 期望集 = 普查里「有 spr 且在 objs/ 有帧文件」的实例，按 (章, 房id, obj, x, y) 归一
  · 实际集 = 场景 JSON 里的 objects，按 (章, 房id, src, x, y) 归一
  · 期望 − 实际 = 丢了哪些（本脚本的重点）
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
OBJS = os.path.join(SCENES, 'objs')
E42 = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
E43 = os.path.join(ROOT, 'code-quality-audit', '第43轮-原作门与相机取证', '_evidence')
INST = {'ch1': 'inst42.json', 'ch2': 'ch2_inst42.json', 'ch3': 'ch3_inst42.json',
        'ch4': 'ch4_inst42.json', 'ch5': 'ch5_inst42.json'}
RE_ZONE = re.compile(r'^_zone\.(ch\d+)\.')


def load(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def main():
    objmap = {}
    with io.open(os.path.join(E43, 'objmap43.txt'), 'r', encoding='utf-8',
                 errors='replace') as fh:
        for line in fh:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3:
                continue
            nm = parts[1].strip()
            m = re.search(r'spr=([^\t]*)', line)
            if nm:
                objmap[nm] = m.group(1).strip() if m and m.group(1).strip() else None
    spr_keys = set()
    for f in os.listdir(OBJS):
        m = re.match(r'^(.*)_(\d+)\.png$', f)
        spr_keys.add(m.group(1) if m else f[:-4])

    # 期望集
    expect = {}      # (ch, rid) -> set of (obj, x, y)
    for ch, fn in INST.items():
        d = load(os.path.join(E42, fn))
        for rec in (d.get('rooms') or []):
            rid = rec.get('index')
            s = expect.setdefault((ch, rid), set())
            for it in (rec.get('insts') or []):
                nm, x, y = it.get('obj'), it.get('x'), it.get('y')
                if not nm or not isinstance(x, int) or not isinstance(y, int):
                    continue
                spr = objmap.get(nm)
                if spr and spr in spr_keys:
                    s.add((nm, x, y))

    # 实际集
    actual = {}
    # 分片
    for zf in sorted(f for f in os.listdir(SCENES)
                     if f.startswith('_zone.') and f.endswith('.json')):
        m = RE_ZONE.match(zf)
        ch = m.group(1) if m else None
        d = load(os.path.join(SCENES, zf))
        for sid, raw in (d.get('scenes') or {}).items():
            if not isinstance(raw, dict):
                continue
            rid = raw.get('original_room_id')
            objs = raw.get('objects')
            if not isinstance(objs, list):
                continue
            s = actual.setdefault((ch, rid), set())
            for o in objs:
                if isinstance(o, dict) and isinstance(o.get('pos'), list) and len(o['pos']) == 2:
                    s.add((o.get('src'), o['pos'][0], o['pos'][1]))
    # 独立文件（rid 从索引取）
    idx = load(os.path.join(SCENES, '_index.json'))
    for ch, blk in (idx.get('chapters') or {}).items():
        if not isinstance(blk, dict):
            continue
        for area, ablk in (blk.get('areas') or {}).items():
            if not isinstance(ablk, dict):
                continue
            for sid, entry in (ablk.get('scenes') or {}).items():
                if not isinstance(entry, dict) or not entry.get('file'):
                    continue
                rid = entry.get('original_room_id')
                fp = os.path.join(SCENES, entry['file'])
                if not os.path.exists(fp):
                    continue
                d = load(fp)
                objs = d.get('objects')
                if not isinstance(objs, list):
                    continue
                s = actual.setdefault((ch, rid), set())
                for o in objs:
                    if isinstance(o, dict) and isinstance(o.get('pos'), list) and len(o['pos']) == 2:
                        s.add((o.get('src'), o['pos'][0], o['pos'][1]))

    tot_e = sum(len(v) for v in expect.values())
    tot_a = sum(len(v) for v in actual.values())
    print('期望 %d / 实际 %d / 差 %d' % (tot_e, tot_a, tot_e - tot_a))
    print('')
    print('=== 逐房间缺口（期望 − 实际 非空）===')
    n_rooms = 0
    lost = 0
    for key in sorted(expect, key=lambda k: (k[0], k[1])):
        e = expect[key]
        a = actual.get(key, set())
        miss = e - a
        if miss:
            n_rooms += 1
            lost += len(miss)
            if n_rooms <= 25:
                print('%-5s room %-4s 期望%2d 实得%2d 缺%d %s' %
                      (key[0], key[1], len(e), len(a), len(miss),
                       sorted(miss)[:6]))

    print('')
    print('缺口房间数 = %d，缺口条数 = %d' % (n_rooms, lost))
    print('')
    print('=== 反向（实际有、期望无）===')
    for key in sorted(actual):
        e = expect.get(key, set())
        a = actual[key]
        extra = a - e
        if extra:
            print('%-5s room %-4s 多 %d 条 %s' % (key[0], key[1], len(extra), sorted(extra)[:6]))
    return 0


if __name__ == '__main__':
    sys.exit(main())

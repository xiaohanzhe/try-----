# -*- coding: utf-8 -*-
u"""第170轮：76 条 GML 缺口「能不能补」的可行性分析（只读，不动数据）。

三个前置条件缺一不可（与第169轮 `unreg` 同一把尺）：
  ① 源场景已登记成 scene；② 目标场景已登记成 scene；③ 源场景里真有该门实例。
`pos` 型还多一条：④ **区间能唯一命中一扇门实例**（对不上就不知道是哪一扇）。
"""
import collections
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
DIFF = os.path.join(ROUND, '_evidence', 'diff170.json')
OUT = os.path.join(ROUND, '_evidence', 'plan170.json')

W_VIA = ('obj_doorW', 'obj_doorw_musfade')


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace', newline='').read())


def load_scenes():
    u"""→ (room_id -> sid) 按章分、sid -> objects。"""
    by_room = collections.defaultdict(dict)
    objs = {}
    for f in glob.glob(os.path.join(SCENES, '_zone.*.json')):
        z = jl(f)
        ch = z.get('chapter_id') or ''
        s = z.get('scenes')
        it = (s.items() if isinstance(s, dict) else ((v.get('scene_id'), v) for v in s))
        for k, v in it:
            if not isinstance(v, dict):
                continue
            sid = v.get('scene_id') or k
            rid = v.get('original_room_id')
            if rid is not None:
                by_room[ch][rid] = sid
            objs[sid] = v.get('objects') or []
    return by_room, objs


def letter_of(src):
    import re
    m = re.match(r'obj_door([A-Za-z])', str(src))
    return m.group(1) if m else None


def main():
    d = jl(DIFF)
    by_room, objs = load_scenes()
    print(u'场景表：%d 章 / %d 个 scene' % (len(by_room), len(objs)))

    rows = []
    for r in d['rows']:
        if not r['gml_only']:
            continue
        ch = r['chapter']
        rid_s = r['src_room_id']
        via = r['via']
        sid_s = (by_room.get(ch) or {}).get(rid_s)
        for dst in r['gml_only']:
            b = next((x for x in r['gml'] if x['dst'] == dst), None)
            sid_t = (by_room.get(ch) or {}).get(dst)
            why = []
            if sid_s is None:
                why.append('src_unreg')
            if sid_t is None:
                why.append('dst_unreg')
            hit = None
            if sid_s is not None:
                cand = [(i, (o.get('pos') or [None, None])[0], (o.get('pos') or [None, None])[1])
                        for i, o in enumerate(objs.get(sid_s) or [])
                        if o.get('src') == via]
                if not cand:
                    why.append('no_instance')
                if b and b['kind'] == 'pos':
                    ax = 0 if b['axis'] == 'x' else 1
                    h = [c for c in cand if c[ax] is not None and _in(c[ax], b)]
                    if len(h) == 1:
                        hit = h[0][1] if ax == 0 else h[0][2]
                    elif len(h) == 0:
                        why.append('range_miss')
                    else:
                        why.append('range_multi%d' % len(h))
                hit = hit
            rows.append({'ch': ch, 'src_room': rid_s, 'sid_s': sid_s, 'via': via,
                         'dst': dst, 'sid_t': sid_t, 'kind': b['kind'] if b else '?',
                         'axis': b['axis'] if b else None,
                         'lo': b['lo'] if b else None, 'hi': b['hi'] if b else None,
                         'ent': b['ent'] if b else None, 'cond': b['cond'] if b else None,
                         'pos_hit': hit, 'why': why,
                         'ok': not why})

    print()
    print(u'== 76 条缺口的分桶 ==')
    c1 = collections.Counter(r['kind'] for r in rows)
    print(u'  按分支类型：%r' % (dict(c1),))
    c2 = collections.Counter('|'.join(r['why']) if r['why'] else 'OK' for r in rows)
    for k, v in sorted(c2.items(), key=lambda x: -x[1]):
        print(u'  %-24s %d' % (k, v))
    ok = [r for r in rows if r['ok']]
    print()
    print(u'== 可补 %d 条 ==' % len(ok))
    for r in ok:
        print(u'  %s %-34s -> %-40s %-5s %-8s ent=%s%s'
              % (r['ch'], r['sid_s'] or r['src_room'], r['sid_t'] or r['dst'],
                 r['kind'], r['cond'] or '', r['ent'],
                 (u'  door_x=%s' % r['pos_hit']) if r['pos_hit'] is not None else ''))
    bad = [r for r in rows if not r['ok']]
    print()
    print(u'== 补不了 %d 条（逐条点名，不许"不补就算了"）==' % len(bad))
    for r in bad:
        print(u'  %s %-34s -> %-40s %-5s %-10s why=%s'
              % (r['ch'], r['sid_s'] or r['src_room'], r['sid_t'] or r['dst'],
                 r['kind'], (r['cond'] or '')[:10], ','.join(r['why'])))

    text = json.dumps({'stat': {'total': len(rows), 'ok': len(ok),
                                'kind': dict(c1), 'why': dict(c2)},
                       'rows': rows}, ensure_ascii=False, indent=1)
    io.open(OUT, 'wb').write(text.replace('\n', '\r\n').encode('utf-8'))
    print()
    print(u'落盘 %s (%d B)' % (OUT, os.path.getsize(OUT)))


def _in(v, b):
    lo, hi = b['lo'], b['hi']
    if lo is not None:
        if b['lo_incl']:
            if v < lo:
                return False
        elif v <= lo:
            return False
    if hi is not None:
        if b['hi_incl']:
            if v > hi:
                return False
        elif v >= hi:
            return False
    return True


if __name__ == '__main__':
    main()

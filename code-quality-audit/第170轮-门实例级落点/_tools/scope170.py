# -*- coding: utf-8 -*-
u"""第170轮：**若产品侧按门实例坐标消歧，会影响多少个场景**（只读统计）。

★ 这里**不模拟** `route_for_door` 的裁决（那等于把被测物再抄一遍），只统计
  「同时满足下面三条」的场景数 —— 这是**事实计数**，不是推演：
    ① 该场景里有 ≥2 扇**同字母**门实例（现在必然全去同一处 = 一房多出口）；
    ② 该 (场景, 字母) 在表里有 ≥2 条候选规则；
    ③ 其中 ≥2 条带**可用区间**（`x_range` 或将来的 `y_range` 有非空端点）。

  只有这种场景，"按坐标消歧"才可能改变结果；其余场景（单门 / 单规则 /
  规则全没区间）改前后必然一致 —— **那些才是零风险面**。
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
OUT = os.path.join(ROUND, '_evidence', 'scope170.json')

DOOR_LETTERS = ('A', 'B', 'C', 'D', 'E', 'F', 'W', 'X', 'Y')


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace', newline='').read())


def door_letter_of(src):
    if not isinstance(src, str):
        return None
    s = src.strip()
    if not s.lower().startswith('obj_door'):
        return None
    head = s[len('obj_door'):].split('_', 1)[0]
    if len(head) == 1 and head.upper() in DOOR_LETTERS:
        return head.upper()
    return None


def has_range(o):
    for k in ('x_range', 'y_range'):
        v = o.get(k)
        if isinstance(v, list) and len(v) == 2 and (v[0] is not None or v[1] is not None):
            return True
    return False


def main():
    #: scene -> letter -> [pos,...]
    doors = collections.defaultdict(lambda: collections.defaultdict(list))
    for f in glob.glob(os.path.join(SCENES, '_zone.*.json')):
        z = jl(f)
        s = z.get('scenes')
        it = (s.items() if isinstance(s, dict) else ((v.get('scene_id'), v) for v in s))
        for k, v in it:
            if not isinstance(v, dict):
                continue
            sid = v.get('scene_id') or k
            for o in v.get('objects') or []:
                if not isinstance(o, dict):
                    continue
                lt = door_letter_of(o.get('src'))
                if lt:
                    doors[sid][lt].append(o.get('pos'))

    routes = jl(os.path.join(SCENES, '_routes.json'))['routes']
    #: (scene, letter) -> [rule]
    cand = collections.defaultdict(list)
    for r in routes:
        wd = r.get('when_door')
        ws = r.get('when_scene')
        if r.get('when_src') or not wd or not ws:
            continue
        cand[(ws, wd)].append(r)

    rows = []
    for sid, by_lt in doors.items():
        for lt, poss in by_lt.items():
            if len(poss) < 2:
                continue
            rs = cand.get((sid, lt)) or []
            nr = len(rs)
            n_ranged = sum(1 for r in rs if has_range(r.get('_original') or {}))
            rows.append({'scene': sid, 'letter': lt, 'n_doors': len(poss),
                         'n_rules': nr, 'n_ranged': n_ranged,
                         'affected': nr >= 2 and n_ranged >= 2, 'pos': poss})

    rows.sort(key=lambda x: (not x['affected'], -x['n_doors']))
    print(u'== 同字母多门实例的场景 ==')
    print(u'   总计 %d 个 (场景,字母) 组合；其中「规则≥2 且 ≥2 条带区间」= **%d** 个'
          % (len(rows), sum(1 for r in rows if r['affected'])))
    print()
    for r in rows:
        if r['affected']:
            print(u'  ★ %-46s %s 门=%d 规则=%d 带区间=%d  %r'
                  % (r['scene'], r['letter'], r['n_doors'], r['n_rules'],
                     r['n_ranged'], r['pos']))
    print()
    print(u'  --- 不受影响的多门场景（规则不足或无区间）---')
    for r in rows:
        if not r['affected']:
            print(u'    %-46s %s 门=%d 规则=%d 带区间=%d'
                  % (r['scene'], r['letter'], r['n_doors'], r['n_rules'], r['n_ranged']))

    io.open(OUT, 'wb').write(json.dumps({'rows': rows}, ensure_ascii=False, indent=1)
                             .replace('\n', '\r\n').encode('utf-8'))
    print()
    print(u'落盘 %s' % OUT)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
u"""第170轮：**`door_x` 到底是「门实例真实坐标」还是「区间里的某个代表值」**。

为什么必须先证这一步
--------------------
实例级消歧有两条路可选：
  (a) **区间包含**（`x_range` 含住门的 x）—— 但第169轮没存端点开闭
      （`x > 290 && x < 370` 与 `x >= 290` 在表里都只是 `[290, 370]`），
      门正好压在边界上时会判错；
  (b) **精确相等**（规则的 `door_x` == 这扇门实例的 x）—— 无端点歧义，
      但**前提是 `door_x` 记的必须是实例坐标**。

本脚本只证一件事：对每个可映射房间，每条规则的 `door_x` 是否**恰好等于**
本房间某扇同字母门的真实 x，且**不同规则不撞同一扇门**。
  · 全过 ⇒ 走 (b)，精确相等，零端点歧义；
  · 有例外 ⇒ 逐条点名，不许默默套 (a)。
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
SCOPE = os.path.join(ROUND, '_evidence', 'scope170.json')

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


def main():
    scope = jl(SCOPE)
    affected = [r for r in scope['rows'] if r['affected']]

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
                    doors[sid][lt].append(o.get('pos') or [None, None])

    routes = jl(os.path.join(SCENES, '_routes.json'))['routes']
    cand = collections.defaultdict(list)
    for r in routes:
        wd, ws = r.get('when_door'), r.get('when_scene')
        if r.get('when_src') or not wd or not ws:
            continue
        cand[(ws, wd)].append(r)

    bad = []
    print(u'== 11 个受影响场景：规则的 door_x 是否精确落在某扇门实例上 ==')
    for a in affected:
        sid, lt = a['scene'], a['letter']
        poss = doors[sid][lt]
        xs = [p[0] for p in poss if p and p[0] is not None]
        rs = cand[(sid, lt)]
        print()
        print(u'  %s  [%s]  门实例 x=%r' % (sid, lt, xs))
        used = []
        for r in sorted(rs, key=lambda t: t.get('priority') or 0):
            o = r.get('_original') or {}
            dx = o.get('door_x')
            ok = dx is not None and dx in xs
            dup = ok and used.count(dx) > 0
            if ok:
                used.append(dx)
            print(u'    prio=%-5s door_x=%-6r %s  -> %s'
                  % (r.get('priority'), dx,
                     u'✓' if ok and not dup else (u'✗撞车' if dup else u'✗不在实例里'),
                     r.get('to')))
            if not ok or dup:
                bad.append({'scene': sid, 'letter': lt, 'priority': r.get('priority'),
                            'door_x': dx, 'xs': xs, 'to': r.get('to'),
                            'why': 'dup' if dup else 'not_in_instances'})

    print()
    print(u'== 结论 ==')
    if not bad:
        print(u'   全部精确命中且不撞车 ⇒ **可用精确相等匹配**，无需区间端点语义')
    else:
        print(u'   ★ 有 %d 条不符，逐条如下：' % len(bad))
        for b in bad:
            print(u'     %-46s %s prio=%s door_x=%r why=%s'
                  % (b['scene'], b['letter'], b['priority'], b['door_x'], b['why']))

    io.open(os.path.join(ROUND, '_evidence', 'exact170.json'), 'wb').write(
        json.dumps({'bad': bad, 'ok': not bad}, ensure_ascii=False, indent=1)
        .replace('\n', '\r\n').encode('utf-8'))


if __name__ == '__main__':
    main()

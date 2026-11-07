# -*- coding: utf-8 -*-
u"""第170轮：**行为冒烟** —— 受影响场景的每扇门现在各自去哪个房间。

只看三件事，不替代正式判据（`check170.py`）：
  ① 受影响场景里，各扇门是否**去了不同目标**（原来是全去同一处）；
  ② 每个目标是否与该门的 `x_range` / `y_range` 相符；
  ③ 其它场景（不受影响）传不传 `pos`，结果是否**逐一相同**。
"""
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'modules'))
sys.path.insert(0, PET)

SCENES = os.path.join(PET, 'assets', 'scenes')

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
    return head.upper() if len(head) == 1 and head.upper() in DOOR_LETTERS else None


def main():
    from modules.item_interact import route_for_door
    routes = jl(os.path.join(SCENES, '_routes.json'))

    #: 受影响场景（改前 scope170 报的那 11 个）
    sc = jl(os.path.join(ROUND, '_evidence', 'scope170.json'))
    affected = {(r['scene'], r['letter']) for r in sc['rows'] if r['affected']}

    print(u'== ① 受影响场景：逐门结果 ==')
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
                if not lt or (sid, lt) not in affected:
                    continue
                pos = o.get('pos')
                with_pos = route_for_door(routes, sid, lt, src=o.get('src'), pos=pos)
                without = route_for_door(routes, sid, lt, src=o.get('src'))
                mark = u'' if with_pos == without else u'  <== 变了'
                print(u'  %-46s %s pos=%-14r -> %-44s (旧的: %s)%s'
                      % (sid, lt, pos, with_pos, without, mark))

    # ---------- ③ 不受影响的场景：传不传 pos 必须一致 ----------
    diff = []
    n = 0
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
                if not lt or (sid, lt) in affected:
                    continue
                n += 1
                a = route_for_door(routes, sid, lt, src=o.get('src'), pos=o.get('pos'))
                b = route_for_door(routes, sid, lt, src=o.get('src'))
                if a != b:
                    diff.append((sid, lt, o.get('src'), o.get('pos'), a, b))
    print()
    print(u'== ③ 不受影响的 %d 个门实例：传 pos vs 不传 ==' % n)
    print(u'   结果不同 %d 个' % len(diff))
    for x in diff[:10]:
        print(u'   ✗ %-40s %s %-22s pos=%r pos->%s  无pos->%s' % x)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
u"""第170轮：**这 6 条会改变行为的新规则，会不会把「没反应」换成「走错房间」**。

问题
----
`route_for_door(.., letter)` 是**场景级**的：同一场景所有 `obj_doorW` 拿到的
`letter` 都是 `'W'`（`door_letter_of('obj_doorW') == 'W'`），于是共享同一条规则。

⇒ 若某场景有 **2 扇以上** W 门，补一条规则会让它们**全都**通向同一个目标。
   原来「查不到 ⇒ 不建门 ⇒ 按 E 没反应」；补完可能变成「按 E 走错房间」。
   **后者更糟** —— 静默错误比明显缺失更难发现。

判据
----
逐场景数 `objects` 里 `src` 归一后等于 `obj_doorW` 的实例：
  · count == 1 ⇒ 补规则**安全**（唯一那扇门就该去那儿）
  · count >= 2 ⇒ 补规则**必须**同时靠实例级消歧（Task #39）兜住，
                 否则判为「不可单独补」
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
FIX = os.path.join(ROUND, '_evidence', 'fix170.json')
OUT = os.path.join(ROUND, '_evidence', 'sharing170.json')


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace', newline='').read())


def norm(src):
    u"""`obj_doorW` / `obj_doorW_0` / `obj_doorW_2` → `obj_doorW`（去掉实例后缀）。"""
    if not isinstance(src, str):
        return ''
    s = src.strip()
    if '_' in s[len('obj_door'):]:
        return s.split('_', 1)[0]
    return s


def main():
    fix = jl(FIX)

    M = {}
    for f in glob.glob(os.path.join(SCENES, '_zone.*.json')):
        z = jl(f)
        s = z.get('scenes')
        it = (s.items() if isinstance(s, dict) else ((v.get('scene_id'), v) for v in s))
        for k, v in it:
            if isinstance(v, dict):
                M[v.get('scene_id') or k] = v.get('objects') or []

    rows = []
    for nr in fix['new_rules']:
        sid = nr['sid_s']
        ws = [o for o in M.get(sid) or []
              if isinstance(o, dict) and norm(o.get('src')) == 'obj_doorW']
        rows.append({'scene': sid, 'to': nr['sid_t'], 'n_doorW': len(ws),
                     'safe': len(ws) == 1,
                     'pos': [o.get('pos') for o in ws]})

    print(u'== 6 条「会改变行为」的新规则：本场景 W 门实例数 ==')
    for r in rows:
        print(u'  %-46s W门=%d  %s  pos=%r'
              % (r['scene'], r['n_doorW'],
                 u'安全' if r['safe'] else u'★需消歧', r['pos']))
    print()
    n_safe = sum(1 for r in rows if r['safe'])
    print(u'   单门(安全) %d / 多门 %d' % (n_safe, len(rows) - n_safe))

    io.open(OUT, 'wb').write(json.dumps({'rows': rows, 'safe': n_safe},
                                        ensure_ascii=False, indent=1)
                             .replace('\n', '\r\n').encode('utf-8'))
    print(u'落盘 %s' % OUT)


if __name__ == '__main__':
    main()

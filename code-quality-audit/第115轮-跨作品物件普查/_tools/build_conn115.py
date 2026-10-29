# -*- coding: utf-8 -*-
"""生成三款的房间连通数据（两个文件，**来源分开标注**）。

产物
----
_evidence/conn115.json           只放**可信**的边：GML 里写死常量的 `room_goto(M)`，
                                 src 来自同一 code 里的 `if (room == N)` 守卫。
_evidence/conn_inferred115.json  候选边：对象事件里 `room_goto_next/previous` 推出的
                                 (R, R±1)。**未经代码真值验证**，靠"同区域率 84.6% vs 随机 11.9%"
                                 支撑方向，逐条带 via/off/same_area 标记，供后续开关。

★ 为什么分两个文件：项目口径是「当原作门逐门寻路（禁瞬移）」，
  一条错边会把角色送进错的房间，错边比缺边更糟。所以可信边与推断边**绝不混放**。

用法
----
    python build_conn115.py
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
RAW = os.path.join(ROUND, '_evidence', 'raw')
OUT_EXACT = os.path.join(ROUND, '_evidence', 'conn115.json')
OUT_INFER = os.path.join(ROUND, '_evidence', 'conn_inferred115.json')

KEYS = ['ut', 'uty', 'outertale']


def area(name):
    """房间名 -> 区域名（与 probe_conn115._base 保持同一口径）"""
    s = re.sub(r'^(room|rm)[_\-]', '', name or '', flags=re.I)
    m = re.match(r'[A-Za-z]+', s)
    return (m.group(0) if m else s).lower()


def obj_of_code(code, objnames):
    pre = 'gml_Object_'
    if not code.startswith(pre):
        return None
    rest = code[len(pre):]
    best = None
    for o in objnames:
        if rest.startswith(o + '_') and (best is None or len(o) > len(best)):
            best = o
    return best


def main():
    exact_out = {}
    infer_out = {}
    for key in KEYS:
        conn = json.load(io.open(os.path.join(RAW, key, 'conn_ut.json'), encoding='utf-8'))
        names = conn['room_names']
        n = len(names)

        # 对象 -> 摆了实例的房间
        obj2rooms = collections.defaultdict(set)
        cur = None
        with io.open(os.path.join(RAW, key, 'inst_full.tsv'), encoding='utf-8') as f:
            for ln in f:
                ln = ln.rstrip('\n')
                if ln.startswith('R\t'):
                    cur = int(ln.split('\t')[1])
                elif ln.startswith('I\t') and cur is not None:
                    obj2rooms[ln.split('\t')[1]].add(cur)
        objnames = sorted(obj2rooms, key=len, reverse=True)

        exact = []
        seen = set()
        for x in conn['items']:
            if x['src'] >= 0 and x['dst'] >= 0 and 0 <= x['dst'] < n:
                k = (x['src'], x['dst'])
                if k in seen:
                    continue
                seen.add(k)
                exact.append({'src': x['src'], 'dst': x['dst'],
                              'src_name': names[x['src']], 'dst_name': names[x['dst']],
                              'code': x['code']})
        exact.sort(key=lambda e: (e['src'], e['dst']))

        rel = collections.defaultdict(set)
        for x in conn['items']:
            o = obj_of_code(x['code'], objnames)
            if not o:
                continue
            if x['op'] == 'room_goto_next':
                rel[o].add(1)
            elif x['op'] == 'room_goto_previous':
                rel[o].add(-1)

        infer = []
        iseen = set(seen)
        for o, offs in sorted(rel.items()):
            for r in sorted(obj2rooms.get(o) or ()):
                for off in sorted(offs):
                    d = r + off
                    if not (0 <= d < n) or d == r or (r, d) in iseen:
                        continue
                    iseen.add((r, d))
                    infer.append({'src': r, 'dst': d,
                                  'src_name': names[r], 'dst_name': names[d],
                                  'via': o, 'off': off,
                                  'same_area': area(names[r]) == area(names[d])})
        infer.sort(key=lambda e: (e['src'], e['dst']))

        exact_out[key] = {
            'n_rooms': n,
            'n_edges': len(exact),
            'src_rooms': len(set(e['src'] for e in exact)),
            'rule': 'GML 里 `if (room == N) room_goto(M)` 的常量对；src 取自同一 code 内的守卫',
            'edges': exact,
        }
        infer_out[key] = {
            'n_rooms': n,
            'n_edges': len(infer),
            'same_area': sum(1 for e in infer if e['same_area']),
            'rule': '对象事件里的 room_goto_next / room_goto_previous（= 房间序 ±1）；'
                    '前提「摆了该对象的房间就存在这条边」**未经验证**',
            'edges': infer,
        }

    for path, obj in [(OUT_EXACT, exact_out), (OUT_INFER, infer_out)]:
        with io.open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True))
            f.write('\n')

    for key in KEYS:
        e, i = exact_out[key], infer_out[key]
        print('[%s] 房间 %d / 可信边 %d（src %d 间）/ 候选边 %d（同区域 %d）'
              % (key, e['n_rooms'], e['n_edges'], e['src_rooms'], i['n_edges'], i['same_area']))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()

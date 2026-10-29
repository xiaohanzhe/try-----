# -*- coding: utf-8 -*-
"""三款交互点的**语义**标注（门通向哪 / 存档点 / 可读物 / 招牌 / 宝箱 / 传送 / 标记）。

与第 115 轮前半段的区别：
  `points115.py` 只给 Deltarune 分了类（door/save/readable/...），没有"通向哪"；
  这里补三款，并把**门的语义**做出来 —— 每个门实例 → 目的地房间（带依据）。

分类口径**故意与 Deltarune 完全一致**（同一个 KINDS 列表，同样的顺序、同样的匹配方式），
否则三款与 Deltarune 的统计没法比。UTY 的命名体系不同（`obj_doorway` / `obj_savebox` /
`obj_books`），所以额外给一个 `subkind` 记更细的类，但**不拿它去改 kind**。

门的语义怎么来的（这是唯一有依据的做法）：
  exact 边里每条都带 `code`（如 `gml_Object_obj_door_t_Alarm_2`），
  把 code 里的对象名与「这间房里摆的门实例」对上，就能说"这扇门通向哪"。
  ★ 只有**唯一匹配**才算 resolved；多条候选一律列出来标 ambiguous，不猜。

用法
----
    python semantic115.py
产物
----
    _evidence/cross_semantics115.json / .txt
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')

KEYS = ['ut', 'uty', 'outertale']

# ★ 与 points115.py 逐字一致（顺序即优先级）。改这里就会破坏与 Deltarune 的可比性。
KINDS = [
    ('door', lambda n: 'door' in n),
    ('warp', lambda n: 'warp' in n),
    ('marker', lambda n: 'marker' in n),
    ('save', lambda n: 'savepoint' in n),
    ('treasure', lambda n: 'treasure' in n),
    ('readable', lambda n: n.startswith('obj_readable')),
    ('sign', lambda n: 'sign' in n),
]
# 只用于补充说明，不参与 kind 判定
SUBKIND = [
    ('挡路物', lambda n: 'blocker' in n),
    ('假门', lambda n: 'fake' in n),
    ('门洞/出口', lambda n: 'doorway' in n or 'doorexit' in n or 'door_exit' in n
                              or 'doorlight' in n),
    ('存档盒', lambda n: n in ('obj_savebox', 'obj_savefl')),
    ('书架', lambda n: 'bookshelf' in n),
    ('书', lambda n: 'books' in n or n.endswith('_book') or '_book_' in n),
    ('箱子', lambda n: 'chest' in n),
]
# ★ 三款**自己的**口径（UTY 用 doorway / savebox / chest / books 这套命名）。
#   统一口径（KINDS）保持与 Deltarune 一致以便横比；这里只是"补漏"，另存一个字段，
#   不覆盖 kind —— 覆盖了就等于偷偷改口径，三款的数就不再能跟 Deltarune 比了。
KINDS_EXT = [
    ('door', lambda n: ('doorway' in n or 'doorexit' in n or 'door_exit' in n
                        or 'doorlight' in n) and 'blocker' not in n),
    ('save', lambda n: n in ('obj_savebox', 'obj_savefl')),
    ('treasure', lambda n: 'chest' in n),
    ('readable', lambda n: 'bookshelf' in n or 'books' in n
                           or n.endswith('_book') or '_book_' in n),
]
KIND_LAB = {'door': u'门', 'warp': u'传送', 'marker': u'命名标记', 'save': u'存档点',
            'treasure': u'宝箱', 'readable': u'可读物', 'sign': u'招牌', 'other': u'其它'}


def kind_of(name):
    n = name.lower()
    for k, f in KINDS:
        if f(n):
            return k
    return 'other'


def subkind_of(name):
    n = name.lower()
    for k, f in SUBKIND:
        if f(n):
            return k
    return None


def kind_ext_of(name):
    """统一口径判成 other 时，再用三款自己的命名规则补一次；否则沿用原 kind。"""
    k = kind_of(name)
    if k != 'other':
        return k
    n = name.lower()
    for kk, f in KINDS_EXT:
        if f(n):
            return kk
    return 'other'


def load_rooms(key):
    """rooms[idx] = {'name','w','h','objs':[(obj,x,y)]}"""
    p = os.path.join(RAW, key, 'inst_full.tsv')
    rooms, cur = {}, None
    with io.open(p, encoding='utf-8') as f:
        for ln in f:
            ln = ln.rstrip('\n')
            if ln.startswith('R\t'):
                q = ln.split('\t')
                cur = int(q[1])
                rooms[cur] = {'name': q[2], 'w': float(q[3]), 'h': float(q[4]), 'objs': []}
            elif ln.startswith('I\t') and cur is not None:
                q = ln.split('\t')
                rooms[cur]['objs'].append((q[1], float(q[2]), float(q[3])))
    return rooms


def obj_in_code(code, obj):
    """`gml_Object_obj_door_t_Alarm_2` 里是不是这个对象（按边界匹配，防 obj_door 命中 obj_door_t）"""
    return re.search(r'(^|_)' + re.escape(obj) + r'(_|$)', code) is not None


def annotate_doors(key, rooms, ex, inf, names, by_idx):
    rows, stat = [], collections.Counter()
    ex_by_src = collections.defaultdict(list)
    for e in ex['edges']:
        ex_by_src[e['src']].append(e)
    inf_by_src = collections.defaultdict(list)
    for e in inf['edges']:
        inf_by_src[e['src']].append(e)

    for idx in sorted(rooms):
        for obj, x, y in rooms[idx]['objs']:
            if kind_ext_of(obj) != 'door':
                continue
            stat['doors'] += 1
            cand = [e for e in ex_by_src.get(idx, ()) if obj_in_code(e['code'], obj)]
            prov = 'exact'
            if not cand:
                cand = [e for e in inf_by_src.get(idx, ()) if e['via'] == obj]
                prov = 'inferred'
            if len(cand) == 1:
                e = cand[0]
                stat['resolved_' + prov] += 1
                rows.append({'game': key, 'room': idx, 'room_name': rooms[idx]['name'],
                             'obj': obj, 'sub': subkind_of(obj), 'x': x, 'y': y,
                             'to_room': e['dst'], 'to_name': names[e['dst']],
                             'to_scene': by_idx.get(e['dst']),
                             'provenance': prov, 'n_cand': 1,
                             'via': e.get('code') or e.get('via')})
            else:
                stat['ambiguous' if cand else 'unknown'] += 1
                rows.append({'game': key, 'room': idx, 'room_name': rooms[idx]['name'],
                             'obj': obj, 'sub': subkind_of(obj), 'x': x, 'y': y,
                             'to_room': None, 'to_name': None, 'to_scene': None,
                             'provenance': 'ambiguous' if cand else 'unknown',
                             'n_cand': len(cand),
                             'cand': [e['dst'] for e in cand]})
    return rows, stat


def annotate_others(key, rooms):
    out = collections.defaultdict(list)
    for idx in sorted(rooms):
        for obj, x, y in rooms[idx]['objs']:
            k = kind_ext_of(obj)
            if k in ('door', 'other'):
                continue
            out[k].append({'game': key, 'room': idx, 'room_name': rooms[idx]['name'],
                           'obj': obj, 'sub': subkind_of(obj), 'x': x, 'y': y})
    return out


def main():
    ex_all = json.load(io.open(os.path.join(EV, 'conn115.json'), encoding='utf-8'))
    inf_all = json.load(io.open(os.path.join(EV, 'conn_inferred115.json'), encoding='utf-8'))
    graph = json.load(io.open(os.path.join(EV, 'room_graph115.json'), encoding='utf-8'))

    doors, others = [], collections.defaultdict(list)
    by_kind, by_kind_game = collections.Counter(), collections.defaultdict(collections.Counter)
    door_stat = {}
    sub_counter = collections.Counter()
    rooms_total = rooms_hit = points = 0

    for key in KEYS:
        rooms = load_rooms(key)
        raw = json.load(io.open(os.path.join(RAW, key, 'conn_ut.json'), encoding='utf-8'))
        names = raw['room_names']
        by_idx = {}
        for e in graph[key]['edges']:
            if e.get('src_scene'):
                by_idx.setdefault(e['src'], e['src_scene'])
            if e.get('dst_scene'):
                by_idx.setdefault(e['dst'], e['dst_scene'])

        rooms_total += len(rooms)
        rows, stat = annotate_doors(key, rooms, ex_all[key], inf_all[key], names, by_idx)
        doors.extend(rows)
        door_stat[key] = dict(stat)
        others.update({})  # 保持可变对象
        for k, v in annotate_others(key, rooms).items():
            others[k].extend(v)

        for idx, r in rooms.items():
            n = 0
            for obj, _x, _y in r['objs']:
                k = kind_ext_of(obj)
                by_kind[k] += 1
                by_kind_game[key][k] += 1
                s = subkind_of(obj)
                if s:
                    sub_counter[s] += 1
                if k != 'other':
                    n += 1
            if n:
                rooms_hit += 1
                points += n

    out = {
        'note': '三款交互点语义（门/传送/标记/存档/宝箱/可读物/招牌）',
        'source': '_evidence/raw/<game>/inst_full.tsv + conn115.json + conn_inferred115.json',
        'rules': {
            'kind': [k for k, _ in KINDS],
            'kind_note': '与 points115.py 逐字一致，顺序即优先级；先命中先算',
            'door_to': 'exact 边里 code 含该对象名 => 唯一匹配才算 resolved；'
                       '否则退回 inferred（via == 对象名）；多条候选标 ambiguous，不猜',
        },
        'coverage': {'rooms': rooms_total, 'rooms_with_points': rooms_hit, 'points': points},
        'by_kind': dict(by_kind),
        'by_kind_per_game': {k: dict(v) for k, v in by_kind_game.items()},
        'subkind': dict(sub_counter),
        'door_stat': door_stat,
        'doors': doors,
        'saves': others.get('save', []),
        'readables': others.get('readable', []),
        'signs': others.get('sign', []),
        'treasures': others.get('treasure', []),
        'warps': others.get('warp', []),
        'markers': others.get('marker', []),
    }

    nde = sum(1 for d in doors if d['provenance'] == 'exact')
    nin = sum(1 for d in doors if d['provenance'] == 'inferred')
    lines = [u'三款交互点语义（%d 间房 / %d 个可交互实例）' % (rooms_hit, points), u'']
    kinds_nz = [(k, v) for k, v in by_kind.items() if k != 'other']
    lines.append(u'分类：' + u' · '.join(u'%s %d' % (KIND_LAB.get(k, k), v)
                                       for k, v in sorted(kinds_nz, key=lambda kv: -kv[1])))
    lines.append(u'（另有其它 %d 个非交互场景物件，不在本节口径内 —— 它们归 §12 的物件分级）'
                 % by_kind.get('other', 0))
    if out['subkind']:
        lines.append(u'细分：' + u' · '.join(u'%s %d' % (k, v)
                                           for k, v in sorted(out['subkind'].items(),
                                                              key=lambda kv: -kv[1])))
    for key in KEYS:
        st = door_stat[key]
        lines.append(u'')
        lines.append(u'[%s] 门实例 %d：exact 解析 %d / inferred 解析 %d / 多候选 %d / 无解 %d'
                     % (key, st.get('doors', 0), st.get('resolved_exact', 0),
                        st.get('resolved_inferred', 0), st.get('ambiguous', 0),
                        st.get('unknown', 0)))
        mine = [d for d in doors if d['game'] == key and d['to_name']][:4]
        for d in mine:
            lines.append(u'     %-22s %-24s -> %-22s (%s)'
                         % (d['room_name'], d['obj'], d['to_name'], d['provenance']))
    lines.append(u'')
    lines.append(u'门总计 %d 个：exact %d / inferred %d' % (len(doors), nde, nin))
    lines.append(u'存档点 %d · 可读物 %d · 招牌 %d · 宝箱 %d · 传送 %d · 标记 %d'
                 % (len(out['saves']), len(out['readables']), len(out['signs']),
                    len(out['treasures']), len(out['warps']), len(out['markers'])))

    txt = u'\n'.join(lines) + u'\n'
    with io.open(os.path.join(EV, 'cross_semantics115.json'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
        f.write(u'\n')
    with io.open(os.path.join(EV, 'cross_semantics115.txt'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write(txt)
    sys.stdout.write(txt)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()

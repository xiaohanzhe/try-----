# -*- coding: utf-8 -*-
u"""探针：从原作房间图取「1 跳邻居」，看它们的**地名标签**长什么样（第113轮n）。

为什么要探：`place_hint(near=)` 这块从第113轮j 起就是**预留未接线**的。
接之前必须先看数据 —— 1 跳邻居可能是走廊（`room_krishallway`）、可能是
我们自己的容器、也可能整章没有连接图。**先看再写**，别先写完再发现全是噪音。

用法：
    python probe_near113n.py            # 每章抽 6 个场景
    python probe_near113n.py 20         # 每章抽 20 个
"""
import ast
import io
import json
import os
import sys
import textwrap

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
IDX = os.path.join(PET, 'assets', 'scenes', '_index.json')
REG = os.path.join(PET, 'assets', 'npc', '_registry.json')
GRAPH_AUDIT = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证',
                           '_evidence', '_room_graph.json')
GRAPH_PROD = os.path.join(PET, 'assets', 'scenes', '_room_graph.json')

sys.path.insert(0, os.path.join(PET, 'modules'))
import npc_life as L                                        # noqa: E402


def _label_fn():
    src = io.open(MAIN, encoding='utf-8', newline='').read()
    tree = ast.parse(src)
    code = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == '_scene_place_label':
                    code = textwrap.dedent(ast.get_source_segment(src, fn))
    idx = {}
    for _cid, ch in ((json.loads(io.open(IDX, encoding='utf-8').read())
                      .get('chapters')) or {}).items():
        for _aid, ar in ((ch or {}).get('areas') or {}).items():
            for sid, sc in ((ar or {}).get('scenes') or {}).items():
                sc = sc or {}
                idx[str(sid)] = (str((ch or {}).get('name') or ''),
                                 str((ar or {}).get('name') or ''),
                                 str(sc.get('name') or ''),
                                 bool(sc.get('name_derived')),
                                 str(sc.get('name_raw') or ''))
                idx[str(sid)] += (sc.get('original_room_id'),)
    reg = json.loads(io.open(REG, encoding='utf-8').read())
    proper = {str((r or {}).get('id') or '').rsplit('.', 1)[-1].strip().lower()
              for r in (reg.get('npcs') or [])}
    proper.discard('')

    class Stub(object):
        npc_life_mod = L

        def _scene_label_map(self):
            return {k: v[:5] for k, v in idx.items()}

        def _place_proper(self):
            return proper

    ns = {'npc_life_mod': L}
    exec(compile(code, '<x>', 'exec'), ns)
    return ns['_scene_place_label'], idx, Stub


def main():
    n_each = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    label, idx, Stub = _label_fn()
    stub = Stub()

    gpath = GRAPH_PROD if os.path.isfile(GRAPH_PROD) else GRAPH_AUDIT
    print('房间图 =', gpath)
    print('  （产品内存在 = %s）' % os.path.isfile(GRAPH_PROD))
    g = json.loads(io.open(gpath, encoding='utf-8').read())
    chs = g.get('chapters') or {}

    # 章 → {room: scene_id}
    by_room = {}
    for sid, rec in idx.items():
        rid = rec[5]
        ch = sid.split('.')[0]
        if isinstance(rid, int):
            by_room.setdefault(ch, {}).setdefault(rid, sid)

    for ch in sorted(chs):
        edges = (chs[ch] or {}).get('edges') or []
        adj = {}
        for e in edges:
            adj.setdefault(e.get('src'), set()).add(e.get('dst'))
        print()
        print('=== %s  edges=%d  rooms=%d  scenes=%d'
              % (ch, len(edges), len(adj), len(by_room.get(ch) or {})))
        rooms = sorted(adj)[:n_each]
        for r in rooms:
            sid = (by_room.get(ch) or {}).get(r) or '?'
            nbs = sorted(adj[r])
            names = []
            for d in nbs:
                dsid = (by_room.get(ch) or {}).get(d)
                if not dsid:
                    names.append('<无场景 %d>' % d)
                else:
                    names.append('%s｜%s' % (label(stub, dsid, False),
                                             dsid.split('.', 2)[-1]))
            print('  [%4d] %-34s here=%r' % (r, sid.split('.', 2)[-1],
                                             label(stub, sid, False)))
            print('         邻居(%d): %s' % (len(nbs), ' / '.join(names)))

    print()
    print('=== 有连接图的章 vs 索引里的章 ===')
    print('  图:', sorted(chs))
    print('  索引:', sorted({s.split('.')[0] for s in idx}))
    print('  无图章节的场景数:')
    for ch in sorted({s.split('.')[0] for s in idx} - set(chs)):
        print('    %-12s %d' % (ch, sum(1 for s in idx if s.split('.')[0] == ch)))


if __name__ == '__main__':
    main()

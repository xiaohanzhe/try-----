# -*- coding: utf-8 -*-
"""第十一轮侦察 3：多跳**可达性**的受控实验 —— 决定 EDGE_TOPOLOGY 的最后一票。

背景：`probe_topology_precision` 用"精确率 + 边密度"选出 star，但那份语料里跨句联想
是**顺带出现**的，没有专门测"多跳到底走不走得通"。而 star 是"核心词↔其他词"，
一句话里的非核心词之间**没有直连** —— 这可能让跨句路径变长，反把多跳掐断。必须专门测。

实验设计（三阶段，同一组概念，只改"共现次数"）：

    seed「代码」 ── 熬夜 ── target「咖啡」      （代码 与 咖啡 **从未同句**）

    stage1：两句各 1 次 → 熬夜 的边都是**弱边**(n=1)
            → 预期：**不该**联想（弱边不许当中转站，防漂移）
    stage2：两句各 2 次 → 升**中边**(n=2)
            → 预期：**应该**联想（有证据的桥才放行）
    stage3：两句各 3 次 → 强边 → 预期：更稳、分更高

三种拓扑都跑，看谁"既能挡住 stage1、又能在 stage2 放行"。

运行：C:\\Python311\\python.exe code-quality-audit/第十一轮/probe_multi_hop_gate.py
输出：code-quality-audit/第十一轮/_evidence/round11_multi_hop_gate.txt
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
EV = os.path.join(HERE, '_evidence')
sys.path.insert(0, MODS)
OUT = os.path.join(EV, 'round11_multi_hop_gate.txt')

import conversation_focus as CF          # noqa: E402
import memory_graph as MG                # noqa: E402

S1 = '写代码写到熬夜了'          # 代码 — 熬夜
S2 = '熬夜就靠咖啡撑着'          # 熬夜 — 咖啡
TARGET = '咖啡'

LINES = []


def P(s=''):
    LINES.append(str(s))


P('=' * 76)
P('多跳可达性受控实验：代码 —(熬夜)— 咖啡（代码与咖啡从未同句）')
P('=' * 76)
P('')
P('  句子 A = %s' % S1)
P('  句子 B = %s' % S2)
P('  A 的关键词 = %s' % ' '.join(CF.extract_keywords(S1)))
P('  B 的关键词 = %s' % ' '.join(CF.extract_keywords(S2)))
P('')


def stage(topo, times):
    g = MG.MemoryGraph()
    MG.EDGE_TOPOLOGY = topo
    try:
        for _ in range(times):
            g.add_cooccurrence(CF.extract_keywords(S1))
            g.add_cooccurrence(CF.extract_keywords(S2))
    finally:
        MG.EDGE_TOPOLOGY = 'clique'
    seed = CF.extract_keywords('写代码')
    b = MG.RecallBudget()
    b.start()
    ps = g.paths(MG.seed_map(seed), b, min_node_w=0.30)
    hits = []
    for p in ps:
        ns = p.get('nodes') or []
        if ns and ns[-1] == TARGET:
            hits.append((p.get('hops'), round(p.get('score', 0), 4), ' → '.join(ns)))
    tier = None
    for _nb, e in (g.edges.get('熬夜') or {}).items():
        tier = '%s|n=%s' % (e.get('tier'), e.get('n'))
        break
    return hits, tier, g


P('  %-7s %-8s %-14s %s' % ('拓扑', '阶段', '熬夜边(其一)', '「咖啡」是否被联想起来'))
P('  ' + '-' * 70)
VERDICT = {}
for topo in ('clique', 'star', 'chain'):
    row = []
    for times, name in ((1, 'stage1 x1'), (2, 'stage2 x2'), (3, 'stage3 x3')):
        hits, tier, _g = stage(topo, times)
        got = ('YES  hops=%s score=%s' % (hits[0][0], hits[0][1])) if hits else 'no'
        P('  %-7s %-8s %-14s %s' % (topo, name, tier, got))
        if hits:
            P('            %s' % hits[0][2])
        row.append(bool(hits))
    VERDICT[topo] = row
    P('')

P('  ' + '-' * 70)
P('  判定（stage1 必须 no，stage2 必须 YES）：')
for topo, row in VERDICT.items():
    ok = (not row[0]) and row[1]
    P('    %-7s %s  → %s' % (topo, row, 'PASS' if ok else 'FAIL'))

P('')
P('=' * 76)
P('副表：三种拓扑在 stage2 的图规模（多跳可达要拿噪声换吗）')
P('=' * 76)
for topo in ('clique', 'star', 'chain'):
    _h, _t, g = stage(topo, 2)
    st = g.stats()
    und = st['edges'] // 2
    P('  %-7s 节点 %2d  无向边 %2d  边/点 %.2f  层分布 %s'
      % (topo, st['keys'], und, und / float(max(1, st['keys'])), st['tiers']))

with io.open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(LINES) + '\n')
print('written %s' % OUT)

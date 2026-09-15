# -*- coding: utf-8 -*-
"""第十一轮侦察 2：用「精确率(手标注词表)」比较三种拓扑的检索质量。

为什么这么做：`probe_extract_before_after` 显示 star/chain 能把边密度压到 0.85 边/点
（clique 是 3.3~4.0），但"密度低"不等于"更好"。必须用**检索质量**判优劣。

判据：对每个 seed 取 top-k 路径终点，看它是不是"真词"（落在手标注词表里）。
      精确率 = 真词数 / 返回数。手标注只覆盖这份语料，所以它只用于**相对比较**。
      ⚠ 精确率**不是**决策依据的终点 —— 决定拓扑的是 `probe_multi_hop_gate.py`
      那份多跳可达性实验（结论：只有 clique 走得通）。

运行：C:\\Python311\\python.exe code-quality-audit/第十一轮/probe_topology_precision.py
输出：code-quality-audit/第十一轮/_evidence/round11_topology_precision.txt
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
EV = os.path.join(HERE, '_evidence')
sys.path.insert(0, MODS)
OUT = os.path.join(EV, 'round11_topology_precision.txt')

import conversation_focus as CF          # noqa: E402
import memory_graph as MG                # noqa: E402

LINES = []


def P(s=''):
    LINES.append(str(s))


SENTS = [
    '我明天想写点代码', '要不要休息一下啊', '今天下雨会有点冷吧',
    '我这周末想去爬山记得带水', '想写点代码', '我们聊聊今天的天气怎么样',
    '今天想聊聊塞尔达这游戏的剧情', '刚喝了杯咖啡感觉还行',
    '写代码写累了就喝咖啡', '爬山的时候天气不错',
    '塞尔达这游戏的剧情我觉得挺有意思', '晚上想吃点什么好呢',
    '问题是我还没想好要学什么', '学习编程需要花不少时间',
    '明天开会吗', '这件事很重要', '周末想去爬山', '喝咖啡的时候写代码挺舒服',
]

# 手标注「真词」词表（只覆盖上面这份语料，用于相对比较）
LABELS = set("""
代码 咖啡 爬山 天气 休息 周末 游戏 剧情 塞尔达 重要 开会 编程 时间 学习
需要 记得 带水 下雨 冷 晚饭 吃饭 问题 意思 舒服
""".split())

SEEDS = ['写代码', '喝咖啡', '爬山', '塞尔达', '学习编程', '重要', '休息']


def is_good(node):
    if node in LABELS:
        return True
    return any(lb in node for lb in LABELS if len(lb) >= 2 and lb == node)


def run(topo, strict=True):
    g = MG.MemoryGraph()
    MG.EDGE_TOPOLOGY = topo
    try:
        for s in SENTS:
            g.add_cooccurrence(CF._extract(s, strict=strict))
    finally:
        MG.EDGE_TOPOLOGY = 'clique'
    st = g.stats()
    hits = tot = 0
    detail = []
    hops_dist = {}
    for sd in SEEDS:
        kw = CF._extract(sd, strict=strict)
        b = MG.RecallBudget()
        b.start()
        try:
            ps = g.paths(MG.seed_map(kw), b, min_node_w=0.30)
        except Exception as e:                       # noqa: BLE001
            detail.append('    %-8s ERROR %s' % (sd, e))
            continue
        ends = []
        for p in ps[:5]:
            nodes = p.get('nodes') or []
            if nodes:
                ends.append(nodes[-1])
                hops_dist[p.get('hops')] = hops_dist.get(p.get('hops'), 0) + 1
        good = [n for n in ends if is_good(n)]
        hits += len(good)
        tot += len(ends)
        bad = [n for n in ends if not is_good(n)]
        if bad:
            detail.append('    %-8s 坏: %s' % (sd, ' '.join(bad)))
    prec = hits / float(tot) if tot else 0.0
    return st, prec, tot, hops_dist, detail


P('=' * 78)
P('拓扑 × 词法 的检索质量对比（seed 取 top-5 终点，手标注词表判"真词"）')
P('=' * 78)
P('')
P('  %-7s %-7s %6s %8s %9s %10s' % ('拓扑', '词法', '精确率', '返回数', '边/点', '跳数分布'))
P('  ' + '-' * 66)

for topo in ('clique', 'star', 'chain'):
    for name, strict in (('旧词法', False), ('新词法', True)):
        st, prec, tot, hops, _d = run(topo, strict)
        keys = max(1, st['keys'])
        per = (st['edges'] // 2) / float(keys)
        P('  %-7s %-7s %5.0f%% %8d %9.2f %10s'
          % (topo, name, prec * 100, tot, per, hops))

P('')
P('=' * 78)
P('细看：新词法下各拓扑的"坏词"（非真词终点）')
P('=' * 78)
for topo in ('clique', 'star', 'chain'):
    st, prec, tot, hops, detail = run(topo, True)
    P('')
    P('  [%s] 精确率 %.0f%%  边/点 %.2f  跳数 %s' % (
        topo, prec * 100, (st['edges'] // 2) / float(max(1, st['keys'])), hops))
    for d in detail:
        P(d)
    if not detail:
        P('    （无坏词）')

P('')
P('=' * 78)
P('旗舰查询：seed="写代码" / "喝咖啡" 的 top-5')
P('=' * 78)
for topo in ('clique', 'star', 'chain'):
    for sd in ('写代码', '喝咖啡'):
        P('')
        P('  [%s] seed=%s' % (topo, CF._extract(sd, strict=True)))
        g = MG.MemoryGraph()
        MG.EDGE_TOPOLOGY = topo
        try:
            for s in SENTS:
                g.add_cooccurrence(CF._extract(s, strict=True))
        finally:
            MG.EDGE_TOPOLOGY = 'clique'
        b = MG.RecallBudget()
        b.start()
        for p in g.paths(MG.seed_map(CF._extract(sd, strict=True)), b,
                         min_node_w=0.30)[:5]:
            P('     hops=%s score=%.4f  %s'
              % (p.get('hops'), round(p.get('score', 0), 4),
                 ' → '.join(p.get('nodes') or [])))

with io.open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(LINES) + '\n')
print('written %s (%d lines)' % (OUT, len(LINES)))

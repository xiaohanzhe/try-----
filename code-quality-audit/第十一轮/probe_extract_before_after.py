# -*- coding: utf-8 -*-
"""第十一轮侦察 1：抽词前后对比（旧词法 vs 新词法）+ 建边密度对比。

运行：C:\\Python311\\python.exe code-quality-audit/第十一轮/probe_extract_before_after.py
输出：code-quality-audit/第十一轮/_evidence/round11_extract_before_after.txt

**输出直接由本脚本写文件**：PowerShell 管道会把子进程的中文 stdout 按 ANSI 解码 →
中文必乱码，落盘再读也救不回来（项目环境铁律）。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
EV = os.path.join(HERE, '_evidence')
sys.path.insert(0, MODS)
OUT = os.path.join(EV, 'round11_extract_before_after.txt')

import conversation_focus as CF          # noqa: E402
import memory_graph as MG                # noqa: E402

LINES = []


def P(s=''):
    LINES.append(str(s))


SENTS = [
    '我明天想写点代码',
    '要不要休息一下啊',
    '今天下雨会有点冷吧',
    '我这周末想去爬山记得带水',
    '想写点代码',
    '我们聊聊今天的天气怎么样',
    '今天想聊聊塞尔达这游戏的剧情',
    '刚喝了杯咖啡感觉还行',
    '写代码写累了就喝咖啡',
    '爬山的时候天气不错',
    '塞尔达这游戏的剧情我觉得挺有意思',
    '晚上想吃点什么好呢',
    '问题是我还没想好要学什么',
    '学习编程需要花不少时间',
    '明天开会吗',
    '这件事很重要',
]

OLD = lambda s: CF._extract(s, strict=False)       # noqa: E731  （第九轮既有剪刀）
NEW = CF.extract_keywords

P('=' * 78)
P('【一】抽词：旧词法（第九轮既有剪刀） vs 新词法（extract_keywords）')
P('=' * 78)
tot_old = tot_new = 0
for s in SENTS:
    old, new = OLD(s), NEW(s)
    tot_old += len(old)
    tot_new += len(new)
    P('')
    P('  %s' % s)
    P('    旧(%2d): %s' % (len(old), ' '.join(old)))
    P('    新(%2d): %s' % (len(new), ' '.join(new)))
P('')
P('节点总数（含重复计）：旧 %d → 新 %d（降 %.0f%%）' % (
    tot_old, tot_new, 100.0 * (tot_old - tot_new) / max(1, tot_old)))

P('')
P('=' * 78)
P('【二】建边拓扑：clique vs star vs chain（同一词表，看密度）')
P('=' * 78)


def build(topo, kw_fn):
    g = MG.MemoryGraph()
    MG.EDGE_TOPOLOGY = topo
    try:
        for s in SENTS:
            g.add_cooccurrence(kw_fn(s))
    finally:
        MG.EDGE_TOPOLOGY = 'clique'
    st = g.stats()
    undirected = st['edges'] // 2
    keys = max(1, st['keys'])
    return st, undirected, undirected / float(keys)


for topo in ('clique', 'star', 'chain'):
    for name, fn in (('旧词法', OLD), ('新词法', NEW)):
        st, und, per = build(topo, fn)
        P('  %-7s %-5s 节点 %3d  无向边 %4d  边/点 %5.2f  层分布 %s'
          % (topo, name, st['keys'], und, per, st['tiers']))

with io.open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(LINES) + '\n')
print('written %s (%d lines)' % (OUT, len(LINES)))

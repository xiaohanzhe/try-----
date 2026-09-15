# -*- coding: utf-8 -*-
"""第十一轮侦察 4：语料建图的**节点清单**（就是报告里那份"残渣账本"的原始数据）。

用途：把"还有哪些碎片没剪掉"从印象变成可核对的清单。自检
`verify_round11_input.py` 的 C10 断言就锁这份清单 —— 多出任何新碎片都会 FAIL。

运行：C:\\Python311\\python.exe code-quality-audit/第十一轮/probe_corpus_nodes.py
输出：code-quality-audit/第十一轮/_evidence/round11_corpus_nodes.txt
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
EV = os.path.join(HERE, '_evidence')
sys.path.insert(0, MODS)

import conversation_focus as CF          # noqa: E402
import memory_graph as MG                # noqa: E402

CORPUS = [
    '我明天想写点代码', '要不要休息一下啊', '今天下雨会有点冷吧',
    '我这周末想去爬山记得带水', '刚喝了杯咖啡感觉还行',
    '写代码写累了就喝咖啡', '喝咖啡的时候写代码挺舒服',
    '我们聊聊今天的天气怎么样', '今天想聊聊塞尔达这游戏的剧情',
    '学习编程需要花不少时间', '明天开会吗', '这件事很重要',
]
g = MG.MemoryGraph()
g.refresh_df({}, 0)
for s in CORPUS:
    g.add_cooccurrence(CF.extract_keywords(s))
_adj = sum(len(v) for v in g.edges.values())
out = []
out.append('节点数 = %d  有向邻接项 = %d  无向边 = %d'
           % (len(g.edges), _adj, _adj // 2))
out.append('边/点 = %.2f' % (_adj // 2 / float(max(1, len(g.edges)))))
out.append('层分布 = %s' % g.stats()['tiers'])
out.append('')
out.append('节点清单：')
out.append('  ' + ' '.join(sorted(g.edges)))
out.append('')
out.append('逐句抽词：')
for s in CORPUS:
    out.append('  %s -> %s' % (s, ' '.join(CF.extract_keywords(s))))

with io.open(os.path.join(EV, 'round11_corpus_nodes.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(out) + '\n')
print('written %s' % os.path.join(EV, 'round11_corpus_nodes.txt'))

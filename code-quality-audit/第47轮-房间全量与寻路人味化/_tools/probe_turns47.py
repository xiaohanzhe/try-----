# -*- coding: utf-8 -*-
"""第47轮探针：**旧等权 BFS vs 新字典序 A\*** 在真实房间图上的行为差。

用户口径（本轮）：「那个寻路要符合真人逻辑，别和机器人一样」。

为什么要这份探针（而不是只写断言）
--------------------------------
"我把 BFS 换成 A*"这句话本身**不构成证据** —— 可能换了半天一条路径都没变
（= 白改），也可能变了但变差。所以必须**在真实数据上逐对起终点对照**，
用数字说话：

  · hops 是否一致（**A\* 不许为了少折返而多走门** —— 这是硬约束）；
  · turns（折返次数）是否真的减少；
  · 到底有**多少**对起终点因此变好（= 用户能体感到的规模）。

对照实现 = **从 git HEAD 取回的旧 BFS 原样**（不是"我以为的 BFS"）——
避免"重写探针失真"这条老坑（记忆 §4：探针不保真 = 报假问题）。

不联网、不调 Ollama、不需要显示器。输出落 _evidence/。
"""
import collections
import io
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..'))
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
GRAPH = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证',
                     '_evidence', '_room_graph.json')
sys.path.insert(0, MOD)

import scene_pathfind as SP      # noqa: E402


def old_bfs(adjacency, start, goal):
    """★ git HEAD 里 `shortest_path` 的**原样复制**（等权 BFS）。

    逐字抄自 `git show HEAD:ralsei_pet/modules/scene_pathfind.py`，
    **故意保持原状**（含它"到 goal 就立刻 return"的写法）。
    """
    if not isinstance(adjacency, dict):
        return None
    if start == goal:
        return []
    if start is None or goal is None:
        return None

    queue = collections.deque([(start, [])])
    seen = {start}
    while queue:
        cur, path = queue.popleft()
        for edge in adjacency.get(cur) or []:
            nxt = edge['dst']
            if nxt in seen:
                continue
            new_path = path + [edge]
            if nxt == goal:
                return new_path
            seen.add(nxt)
            queue.append((nxt, new_path))
    return None


def turns(path):
    """折返次数 = 相邻两步的**下标位移反号**次数（同号/零不计）。"""
    if not isinstance(path, list) or len(path) < 2:
        return 0
    signs = []
    for e in path:
        d = e['dst'] - e['src']
        signs.append(1 if d > 0 else (-1 if d < 0 else 0))
    n = 0
    for i in range(1, len(signs)):
        a, b = signs[i - 1], signs[i]
        if a and b and a != b:
            n += 1
    return n


def seq(path):
    return [path[0]['src']] + [e['dst'] for e in path]


def main():
    raw = json.load(io.open(GRAPH, 'r', encoding='utf-8'))
    edges_by_ch = raw['chapters']
    rg = SP.load_room_graph()
    adj_all = SP.build_adjacency(rg['edges_by_chapter'])

    out = []
    w = out.append
    w('第47轮探针 · 旧等权 BFS vs 新字典序 A*（真实 782 条边）')
    w('=' * 72)

    grand_pairs = 0
    grand_better = 0
    grand_hops_diff = 0
    grand_worse = 0
    samples = []

    for ch in sorted(adj_all):
        adj = adj_all[ch]
        nodes = sorted(adj)
        pairs = better = hops_diff = worse = 0
        best_sample = None
        for s in nodes:
            for t in nodes:
                if s == t:
                    continue
                new = SP.shortest_path(adj, s, t)
                if not isinstance(new, list):
                    continue          # 走不到：两版都 None（后续单独断言）
                pairs += 1
                old = old_bfs(adj, s, t)
                ho, hn = len(old), len(new)
                if hn != ho:
                    hops_diff += 1
                    w('  [HOPS!] %s %d->%d  old=%d new=%d' % (ch, s, t, ho, hn))
                to, tn = turns(old), turns(new)
                if tn > to:
                    worse += 1
                    w('  [WORSE] %s %d->%d  turns old=%d new=%d' % (ch, s, t, to, tn))
                elif tn < to:
                    better += 1
                    if best_sample is None:
                        best_sample = (s, t, to, tn, seq(old), seq(new))
        w('%-4s 可比起终点对=%5d  折返更少=%4d  折返变多=%d  门数不一致=%d'
          % (ch, pairs, better, worse, hops_diff))
        if best_sample:
            s, t, to, tn, so, sn = best_sample
            w('     样例 %d->%d : 旧 %s（折返 %d）→ 新 %s（折返 %d）'
              % (s, t, so, to, sn, tn))
            samples.append((ch, s, t, so, sn))
        grand_pairs += pairs
        grand_better += better
        grand_hops_diff += hops_diff
        grand_worse += worse

    w('-' * 72)
    w('合计：可比起终点对=%d  折返更少=%d  折返变多=%d  ★门数不一致=%d'
      % (grand_pairs, grand_better, grand_worse, grand_hops_diff))
    w('判定：门数不一致必须 = 0（A* 不许多走门）；折返变多必须 = 0（不能改坏）。')

    # 真实数据里"等长但折返更多"的对照，取一条最直观的
    w('')
    w('★ 真实数据鉴别力：以下为**同样门数、旧版折返更多**的实例（前 8 条）')
    shown = 0
    for ch in sorted(adj_all):
        if shown >= 8:
            break
        adj = adj_all[ch]
        for s in sorted(adj):
            if shown >= 8:
                break
            for t in sorted(adj):
                if s == t or shown >= 8:
                    continue
                new = SP.shortest_path(adj, s, t)
                if not isinstance(new, list):
                    continue
                old = old_bfs(adj, s, t)
                if turns(old) > turns(new):
                    w('  %s  %d->%d  旧=%s(t=%d)  新=%s(t=%d)'
                      % (ch, s, t, seq(old), turns(old), seq(new), turns(new)))
                    shown += 1
    if shown == 0:
        w('  （真实图中未找到 —— 说明折叠场景稀缺，需以合成夹具承担鉴别力）')

    text = '\n'.join(out)
    print(text)
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                        '_evidence', '旧BFS对A星对照47.txt')
    with io.open(dest, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())

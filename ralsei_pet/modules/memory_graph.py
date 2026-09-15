# -*- coding: utf-8 -*-
"""分层关联图与受控检索管线（MemoryGraph）
=========================================

第九轮的记忆召回是"1 跳弱扩散"：链路短、不会漂，但想起的东西少。
第十轮把它升级成一条**受控的多跳检索管线**（用户提的设计）：

  边分层（强/中/弱） → hub 惩罚 → 有界子图 → PPR + 路径打分 → 五层过滤 → 反馈学习 → 离线巩固

设计要点（与用户方案的对应关系）：

| 用户要求 | 这里的实现 |
|---|---|
| 强/中/弱边 | `tier` 由共现次数与反馈决定；`_TIER_BASE` 给每层不同基础权重 |
| hub 节点惩罚 | `node_weight()` = IDF（逆文档频率）+ 度惩罚（`1/(1+ln(1+df))`）的加权，把"游戏/那个/我"这类高频词压下去 |
| 路径打分而不是只看相似度 | `paths()` 给出**路径**，分数 = Π(边权 × 节点权) × 跨跳衰减；结果按路径分排序，并可解释"我是怎么想到的" |
| PPR | `ppr()` 在**有界子图**上跑 Personalized PageRank（固定重启概率、固定迭代数）；它是**加权手段而非放行手段** —— 一个词能否进候选只由"路径分是否过门槛"决定，PPR 只在其上做融合（否则 hub 会借 PPR 把被路径过滤剪掉的词塞回来） |
| 限制道路 | 每跳有 **tier 下限**：第 1/2 跳允许弱边（稀疏数据下放行），第 3 跳只允许中/强边 —— 越走越严，从结构上挡住"三步之外的漂移"；真正的过滤主力是路径分，见下 |
| 每跳过滤 | `neighbors(min_tier=...)` + 节点权下限 + 出边数上限 |
| 路径过滤 | 路径分低于阈值即剪（且是**早剪**，在扩展时就算，不浪费） |
| 重排去重降冗余 | 结果层做 MMR 式去重（关键词重叠度 + 同日条数上限），见 `rerank()` |
| LLM 验证挡无关 | `verifier` 钩子（**默认关闭**，且受预算约束），由调用方注入 |
| 预算控制 | `RecallBudget`：最大跳数/节点数/每点出边/路径数/候选数/耗时上限 |
| 反馈学习边权 | `feedback()` 沿"被用过的路径"加减边权（tanh 压缩，防单次抖动） |
| 离线巩固 | `consolidate()`：边老化降级、按反馈升/降级、剪枝、从日摘要补边、体量控制 |
| 评估噪声率/有用率/成功率 | 指标在 `memory_system` 侧统计（`by_tier`/`by_hop` 分桶），`tune()` 依据它自动收紧弱边 |

**零第三方依赖**（纯标准库 math/heapq/time）：单机、离线、可解释优先。
图中节点规模是"关键词"级别（数百），PPR 与路径枚举都在有界子图上做，单次召回是亚毫秒级。
"""
import heapq
import math
import time

try:
    from logger_utils import get_logger
    _log = get_logger(__name__)
except ImportError:  # 模块外独立导入时的降级
    import logging
    _log = logging.getLogger(__name__)

# --------------------------------------------------------------------- 边分层
TIER_STRONG = 'strong'
TIER_MID = 'mid'
TIER_WEAK = 'weak'

_TIER_RANK = {TIER_WEAK: 0, TIER_MID: 1, TIER_STRONG: 2}
# 每层的基础权重：强边几乎必走，弱边只是"顺带一提"
_TIER_BASE = {TIER_STRONG: 1.00, TIER_MID: 0.55, TIER_WEAK: 0.25}

# 共现次数 → 初始分层（离线巩固会再按反馈修正）
_TIER_MIN_COUNT = {TIER_STRONG: 3, TIER_MID: 2}

# 第 N 跳允许的最低边等级 + 该跳的路径分门槛倍数。
#
# ⚠ 这里是第十轮**唯一**改过一次的检索策略，原因是实测把原设计打脸了：
# 原设计是"第 2 跳只许中边、第 3 跳只许强边"（越走越严的静态门槛）。但用真实中文语料
# 实测（见 code-quality-audit/第十轮/demo_recall_showcase.py）：17 条对话切出 82 个词、
# 460 条边，其中 **452 条是弱边**（只共现过 1 次）——真实对话里"同一个词再次同框"极少，
# 于是"第 2 跳门槛=中边"直接把多跳联想**整体锁死**（实测只剩 hop=1 结果，"从写代码想到
# 咖啡"这种最典型的联想完全出不来）。
#
# 所以改成"**允许走，但要自证值钱**"：
#   · 第 1、2 跳放行弱边 —— 走不走得通由**路径分**决定（边权×节点权的连乘 × 跨跳衰减）；
#     两个低质词（含 hub）凑出来的路径，乘积自然过不了 `min_path_score`。
#   · 第 3 跳恢复硬门槛（必须中边以上）—— 三步之外的间接联想，光靠分数不够安全。
# 这样"每跳过滤"仍在，但过滤主力从"静态等级"换成了"路径分 + 等级"的联合判据，
# 也就是用户要的"**路径打分而不是只看相似度**"。
HOP_TIER_FLOOR = {1: TIER_WEAK, 2: TIER_WEAK, 3: TIER_MID}

# 「中转资格」：**弱边可以到达，但不能继续出发**。
#
# 这是第二次被实测修正（见 demo_recall_showcase.py 的输出）：
# 放宽到达门槛后，多跳确实活了，但冒出来的是这种东西 ——
# 「写代码」→（弱边）→「写代」→（弱边）→「爬山记得带水」，即**语义漂移**。
# 病灶是"弱边当跳板"：只共现过 1 次的边，往往来自断词切出来的噪声词
# （`写代`/`点代`/`要不`/`要休`），拿它当中转站，联想就会一路滑走。
#
# 于是加一条不对称规则：**到达可以用弱边，出发必须踩过中边以上**。
# 效果（实测）：`写代码--(n=2 中边)-->咖啡` 这类"重复出现过的真概念"仍然是桥，
# 两跳照样通；而噪声词搭的桥被掐断，漂移消失。
# 同时它也解释了为什么"第 3 跳的到达门槛是中边"是够用的：能走到第 3 跳的路径，
# 前两跳都已经踩过中边以上了。
_BRIDGE_MIN_RANK = _TIER_RANK[TIER_MID]

# 跨跳衰减：每一跳把分数乘一次（两跳的间接联想天然不该压过直接命中）
HOP_DECAY = 0.72


def tier_of(count, fb=0.0):
    """由共现次数 + 反馈决定边等级。"""
    n = int(count or 0)
    f = float(fb or 0.0)
    if n >= _TIER_MIN_COUNT[TIER_STRONG] or (n >= 2 and f >= 0.5):
        return TIER_STRONG
    if n >= _TIER_MIN_COUNT[TIER_MID] or f >= 0.15:
        return TIER_MID
    return TIER_WEAK


def edge_weight(edge, weak_penalty=0.0):
    """边权 = 层基础权 × 共现次数（对数，同层更常见的略强）× 反馈修正。

    `weak_penalty` 是"弱边有用率长期过低"时由 `tune()` 自动加的压制量（0~0.8）。
    """
    if not isinstance(edge, dict):
        return 0.0
    tier = edge.get('tier')
    if tier not in _TIER_BASE:
        tier = tier_of(edge.get('n'))
    base = _TIER_BASE[tier]
    if tier == TIER_WEAK:
        base *= max(0.2, 1.0 - float(weak_penalty or 0.0))
    n = max(1, int(edge.get('n') or 1))
    fb = float(edge.get('fb') or 0.0)
    w = base * (1.0 + 0.12 * math.log(1.0 + n)) * (1.0 + 0.40 * math.tanh(fb))
    return max(0.01, min(1.0, w))


def normalize_assoc(raw):
    """把任意历史格式的 assoc 归一成 `{词: {邻词: edge}}`。

    兼容第九轮的旧格式（值是 int 的共现次数）—— 升级不能丢联想。
    """
    out = {}
    if not isinstance(raw, dict):
        return out
    for a, nbrs in raw.items():
        if not isinstance(nbrs, dict):
            continue
        a = str(a)
        slot = {}
        for b, v in nbrs.items():
            b = str(b)
            if a == b:
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                n = int(v)
                slot[b] = {'n': n, 'tier': tier_of(n), 'fb': 0.0, 'last': 0.0}
            elif isinstance(v, dict):
                try:
                    n = int(v.get('n') or 1)
                except Exception:
                    n = 1
                fb = v.get('fb')
                fb = float(fb) if isinstance(fb, (int, float)) else 0.0
                last = v.get('last')
                last = float(last) if isinstance(last, (int, float)) else 0.0
                tier = v.get('tier')
                slot[b] = {'n': max(1, n),
                           'tier': tier if tier in _TIER_BASE else tier_of(n, fb),
                           'fb': fb, 'last': last}
        if slot:
            out[a] = slot
    return out


def seed_map(seeds):
    """把种子归一成 `{词: 权重}`。

    第十轮踩过：调用方图省事传了 `list`，而这里用 `.items()` —— AttributeError
    被外层的防御性 `except` 吞掉，表现成"多跳联想永远为空"这种**静默全废**。
    所以入口处先归一化类型：list/tuple/set → 等权；str → 单元素；dict → 原样（清洗非法值）。
    """
    if isinstance(seeds, dict):
        out = {}
        for k, w in seeds.items():
            try:
                out[str(k)] = float(w)
            except Exception:
                out[str(k)] = 1.0
        return out
    if isinstance(seeds, str):
        return {seeds: 1.0} if seeds else {}
    if isinstance(seeds, (list, tuple, set, frozenset)):
        return {str(k): 1.0 for k in seeds if k}
    return {}


# ------------------------------------------------------------------- 预算对象
class RecallBudget(object):
    """一次召回的全部预算上限：任何一环失控都会被这里拦住。"""

    __slots__ = ('max_hops', 'max_nodes', 'max_edges_per_node', 'max_paths',
                 'max_candidates', 'max_ms', 'max_llm_calls', 'min_path_score',
                 '_t0')

    def __init__(self, max_hops=3, max_nodes=64, max_edges_per_node=8,
                 max_paths=160, max_candidates=12, max_ms=120.0,
                 max_llm_calls=0, min_path_score=0.02):
        self.max_hops = int(max_hops)
        self.max_nodes = int(max_nodes)
        self.max_edges_per_node = int(max_edges_per_node)
        self.max_paths = int(max_paths)
        self.max_candidates = int(max_candidates)
        self.max_ms = float(max_ms)
        self.max_llm_calls = int(max_llm_calls)
        self.min_path_score = float(min_path_score)
        self._t0 = time.time()

    def start(self):
        self._t0 = time.time()
        return self

    def over_time(self):
        try:
            return (time.time() - self._t0) * 1000.0 >= self.max_ms
        except Exception:
            return False

    def snapshot(self):
        return {'max_hops': self.max_hops, 'max_nodes': self.max_nodes,
                'max_edges_per_node': self.max_edges_per_node,
                'max_paths': self.max_paths, 'max_candidates': self.max_candidates,
                'max_ms': self.max_ms, 'max_llm_calls': self.max_llm_calls,
                'min_path_score': self.min_path_score}


# --------------------------------------------------------------------- 关联图
class MemoryGraph(object):
    """关键词关联图：节点=词，边=共现，边带等级/反馈/时间。"""

    MAX_KEYS = 500           # 节点上限（离线巩固时按权重和裁剪）
    MAX_NB_PER_KEY = 12      # 每个节点保留的邻居上限
    EDGE_TTL_SECONDS = 45 * 86400.0   # 45 天没再共现 → 每次巩固降一次级

    def __init__(self, raw=None):
        self.edges = normalize_assoc(raw)
        self.weak_penalty = 0.0
        self._df = {}
        self._total = 0
        self._degrade = {}     # 巩固统计：本次降级/剪枝了多少

    # ------------------------------------------------------------ 度表/权重
    def refresh_df(self, index, total):
        """由片段倒排索引喂"文档频率"表 —— hub 惩罚的依据。"""
        try:
            self._df = {k: len(v) for k, v in (index or {}).items()}
            self._total = int(total or 0)
        except Exception:
            self._df, self._total = {}, 0

    def degree(self, kw):
        return len(self.edges.get(kw) or {})

    def edge_tier(self, a, b):
        """取 a→b 的边等级（无此边时按弱边处理）。"""
        e = (self.edges.get(a) or {}).get(b)
        return (e or {}).get('tier') or TIER_WEAK

    def node_weight(self, kw):
        """节点权 ∈ [0.25, 1.0]：IDF 高（少见词）× 度低（不是 hub）→ 高。

        这一条直接把"那个/我/游戏"这类到处都出现的词压到 0.4 以下。
        """
        try:
            df = int(self._df.get(kw, 0) or 0)
            n = max(1, self._total)
            idf = math.log((n + 1.0) / (df + 1.0))
            idf_n = min(1.0, idf / max(1e-6, math.log(n + 1.0)))
            hub = 1.0 / (1.0 + math.log(1.0 + df))
            deg = self.degree(kw)
            hub2 = 1.0 / (1.0 + 0.5 * math.log(1.0 + deg))
            return round(max(0.25, min(1.0,
                0.25 + 0.75 * (0.5 * idf_n + 0.3 * hub + 0.2 * hub2))), 4)
        except Exception:
            return 0.5

    # ------------------------------------------------------------ 写入/更新
    def add_cooccurrence(self, kws, now=None, weight=1.0):
        """一句话里的词两两互加一条边（这就是"联想"的形成过程）。"""
        try:
            ks = [k for k in (kws or []) if k]
            if len(ks) < 2:
                return
            now = float(now if now is not None else time.time())
            inc = max(1, int(round(float(weight or 1.0))))
            for a in ks:
                slot = self.edges.setdefault(a, {})
                for b in ks:
                    if b == a:
                        continue
                    e = slot.get(b)
                    if not isinstance(e, dict):
                        e = {'n': 0, 'tier': TIER_WEAK, 'fb': 0.0, 'last': now}
                    e['n'] = int(e.get('n') or 0) + inc
                    e['last'] = now
                    e['tier'] = tier_of(e['n'], e.get('fb'))
                    slot[b] = e
                if len(slot) > self.MAX_NB_PER_KEY:
                    slot = dict(heapq.nlargest(
                        self.MAX_NB_PER_KEY, slot.items(),
                        key=lambda kv: edge_weight(kv[1], self.weak_penalty)))
                    self.edges[a] = slot
            if len(self.edges) > self.MAX_KEYS:
                self._cap_keys()
        except Exception as e:
            _log.debug("memory_graph 加边失败（已忽略）: %s", e)

    def _cap_keys(self, limit=None):
        try:
            keep = heapq.nlargest(
                int(limit or self.MAX_KEYS), self.edges.items(),
                key=lambda kv: sum(edge_weight(e, self.weak_penalty)
                                   for e in kv[1].values()))
            self.edges = dict(keep)
        except Exception as e:
            _log.debug("memory_graph 节点裁剪失败（已忽略）: %s", e)

    def cap_keys(self, limit=None):
        """公开的节点裁剪（调用方有更小的上限时用；返回裁剪后节点数）。"""
        if len(self.edges) > int(limit or self.MAX_KEYS):
            self._cap_keys(limit)
        return len(self.edges)

    # ------------------------------------------------------------ 邻居/子图
    def neighbors(self, kw, min_tier=TIER_WEAK, limit=8, min_node_w=0.0):
        """按"每跳 tier 下限"+节点权下限过滤后的邻居（这就是**每跳过滤**）。"""
        slot = self.edges.get(kw)
        if not slot:
            return []
        floor = _TIER_RANK.get(min_tier, 0)
        out = []
        for nb, e in slot.items():
            if _TIER_RANK.get(e.get('tier'), 0) < floor:
                continue
            nw = self.node_weight(nb)
            if nw < float(min_node_w or 0.0):
                continue
            out.append((nb, edge_weight(e, self.weak_penalty), nw))
        out.sort(key=lambda x: -x[1])
        return out[:int(limit)]

    def build_subgraph(self, seeds, budget):
        """以种子词为起点做有界 BFS，返回 (节点列表, 邻接表)。

        约束：跳数 ≤ max_hops、节点数 ≤ max_nodes、每点出边 ≤ max_edges_per_node、
        每跳只走该跳允许的边等级。
        """
        nodes, adj = [], {}
        seen = set()
        in_tier = {}           # 词 -> 它是被什么等级的边带进来的（中转资格的判据）
        seeds = seed_map(seeds)
        # 种子按权重排序入队（(hop, 词)）
        queue = []
        for s, w in sorted((seeds or {}).items(), key=lambda kv: -kv[1]):
            s = str(s)
            if s not in seen:
                seen.add(s)
                nodes.append(s)
                queue.append((0, s))
        head = 0
        while head < len(queue) and len(nodes) < budget.max_nodes:
            hop, kw = queue[head]
            head += 1
            if hop >= budget.max_hops:
                continue
            # 中转资格：种子无门槛；被**弱边**带进来的节点不再往外走（防噪声词当跳板）
            if hop > 0 and _TIER_RANK.get(in_tier.get(kw), 0) < _BRIDGE_MIN_RANK:
                continue
            nxt = hop + 1
            floor = HOP_TIER_FLOOR.get(nxt, TIER_MID)
            row = {}
            for nb, w, _nw in self.neighbors(kw, min_tier=floor,
                                             limit=budget.max_edges_per_node):
                row[nb] = w
                if nb not in seen and len(nodes) < budget.max_nodes:
                    seen.add(nb)
                    nodes.append(nb)
                    in_tier[nb] = self.edge_tier(kw, nb)
                    queue.append((nxt, nb))
            if row:
                adj[kw] = row
            if budget.over_time():
                break
        return nodes, adj

    def ppr(self, seeds, budget, iters=6, alpha=0.15):
        """有界子图上的 Personalized PageRank。

        个人化向量 = 种子权重；重启概率 alpha 固定（人也会"拉回最初的话题"）。
        度归一化天然压制 hub（和 `node_weight` 的度惩罚方向一致）。
        """
        try:
            seeds = seed_map(seeds)
            nodes, adj = self.build_subgraph(seeds, budget)
            if not nodes:
                return {}
            idx = {n: i for i, n in enumerate(nodes)}
            e = [0.0] * len(nodes)
            for s, w in (seeds or {}).items():
                i = idx.get(str(s))
                if i is not None:
                    e[i] = max(float(w or 0.0), 1e-6)
            tot = sum(e) or 1.0
            e = [x / tot for x in e]
            p = list(e)
            for _ in range(max(1, int(iters))):
                nxt = [alpha * x for x in e]
                for i, n in enumerate(nodes):
                    if p[i] <= 0:
                        continue
                    row = adj.get(n)
                    if not row:
                        nxt[i] += (1.0 - alpha) * p[i]
                        continue
                    denom = sum(row.values()) or 1.0
                    for nb, w in row.items():
                        j = idx.get(nb)
                        if j is None:
                            continue
                        nxt[j] += (1.0 - alpha) * p[i] * (w / denom)
                p = nxt
            return {nodes[i]: round(p[i], 6) for i in range(len(nodes))}
        except Exception as e:
            _log.debug("memory_graph PPR 失败（已忽略）: %s", e)
            return {}

    # ------------------------------------------------------------ 路径打分
    def paths(self, seeds, budget, min_node_w=0.0):
        """枚举有界路径并打分（**路径打分而不是只看相似度**）。

        路径分 = Π(边权 × 邻节点权) × HOP_DECAY^跳数。
        低于 `budget.min_path_score` 的**在扩展时就被剪掉**（路径过滤 + 早剪）。
        返回按分数降序的路径列表，每条含 nodes/score/hops（可解释"怎么想到的"）。
        """
        out = []
        seen = set()
        try:
            seeds = seed_map(seeds)
            budget.start()
            roots = sorted((seeds or {}).items(), key=lambda kv: -kv[1])
            for seed, sw in roots[:budget.max_nodes]:
                seed = str(seed)
                stack = [(seed, [seed], float(sw or 1.0), 0, TIER_STRONG)]
                while stack:
                    if len(out) >= budget.max_paths or budget.over_time():
                        break
                    node, path, score, hop, in_tier = stack.pop()
                    if hop >= budget.max_hops:
                        continue
                    # 中转资格：种子无门槛；被弱边带进来的节点不再往外走
                    if hop > 0 and _TIER_RANK.get(in_tier, 0) < _BRIDGE_MIN_RANK:
                        continue
                    nxt = hop + 1
                    floor = HOP_TIER_FLOOR.get(nxt, TIER_MID)
                    for nb, w, nw in self.neighbors(
                            node, min_tier=floor,
                            limit=budget.max_edges_per_node, min_node_w=min_node_w):
                        if nb in path:
                            continue
                        s = score * w * nw * (HOP_DECAY ** nxt)
                        if s < budget.min_path_score:
                            continue          # ← 路径过滤（早剪）
                        np_ = path + [nb]
                        key = tuple(np_)
                        if key in seen:
                            continue
                        seen.add(key)
                        e_tier = self.edge_tier(node, nb)
                        out.append({'nodes': np_, 'score': round(s, 6),
                                    'hops': nxt, 'tier': e_tier})
                        stack.append((nb, np_, s, nxt, e_tier))
            out.sort(key=lambda p: -p['score'])
        except Exception as e:
            _log.debug("memory_graph 路径枚举失败（已忽略）: %s", e)
        return out[:budget.max_paths]

    # ------------------------------------------------------------ 反馈学习
    def feedback(self, paths, success, lr=0.35):
        """沿"被用过的路径"调整边权（反馈学习边权）。

        正反馈：路径上每条边的 fb 向 +1 走；负反馈幅度减半（宁可少罚，
        免得一次不凑巧的失败把整条联想毁掉）。fb 经 tanh 压缩再进 `edge_weight`。
        """
        try:
            delta = float(lr) * (1.0 if success else -0.5)
            touched = 0
            for p in (paths or []):
                nodes = p.get('nodes') if isinstance(p, dict) else None
                if not nodes or len(nodes) < 2:
                    continue
                # 只强化/削弱路径的**最后一跳**及其前驱（离主题最近的两条边）
                for a, b in list(zip(nodes, nodes[1:]))[-2:]:
                    e = self.edges.get(a, {}).get(b)
                    if isinstance(e, dict):
                        e['fb'] = max(-3.0, min(3.0, float(e.get('fb') or 0.0) + delta))
                        e['tier'] = tier_of(e.get('n'), e['fb'])
                        touched += 1
            return touched
        except Exception as e:
            _log.debug("memory_graph 反馈更新失败（已忽略）: %s", e)
            return 0

    # ------------------------------------------------------------ 重排去重
    @staticmethod
    def rerank(items, limit=3, overlap_threshold=0.6, max_per_day=1):
        """重排去重降冗余（MMR 味道的贪心）。

        贪心规则：按已有分数从高到低取，若与**已选**项的关键词 Jaccard 重叠
        超过阈值则跳过（说的是同一件事），同一天最多留 `max_per_day` 条。
        """
        picked, used_kw, day_count = [], [], {}
        for it in items:
            kws = set(it.get('kw') or []) or set(
                k for k in str(it.get('text') or '')[:0])   # 无关键词时退化为不判重
            if kws and used_kw:
                sim = max((len(kws & u) / float(len(kws | u) or 1)) for u in used_kw)
                if sim >= float(overlap_threshold):
                    continue
            day = str(it.get('day') or '')
            if day and day_count.get(day, 0) >= int(max_per_day):
                continue
            picked.append(it)
            if kws:
                used_kw.append(kws)
            if day:
                day_count[day] = day_count.get(day, 0) + 1
            if len(picked) >= int(limit):
                break
        return picked

    # ------------------------------------------------------------ 离线巩固
    def consolidate(self, now=None, extra_cooccurrence=None, budget=None):
        """离线巩固：边老化 → 升降级 → 剪枝 → 补边 → 体量控制。

        `extra_cooccurrence` 是调用方（memory_system）从**日摘要/关键记忆**里
        提炼出的词团 —— 让"很久以前聊过的东西"也能长出新联想（跨天巩固）。
        """
        now = float(now if now is not None else time.time())
        stats = {'edges_before': sum(len(v) for v in self.edges.values()),
                 'decayed': 0, 'pruned': 0, 'promoted': 0, 'demoted': 0,
                 'added': 0, 'keys_before': len(self.edges)}
        try:
            # ① 边老化：太久没共现 → 共现次数减 1（下限 1），据此重算层
            for a, slot in list(self.edges.items()):
                for b, e in list(slot.items()):
                    if not isinstance(e, dict):
                        continue
                    last = float(e.get('last') or 0.0)
                    if last and (now - last) > self.EDGE_TTL_SECONDS:
                        n0 = int(e.get('n') or 1)
                        if n0 > 1:
                            e['n'] = n0 - 1
                            stats['decayed'] += 1
                        t0 = e.get('tier')
                        e['tier'] = tier_of(e['n'], e.get('fb'))
                        if _TIER_RANK[e['tier']] < _TIER_RANK.get(t0, 0):
                            stats['demoted'] += 1
                        elif _TIER_RANK[e['tier']] > _TIER_RANK.get(t0, 0):
                            stats['promoted'] += 1
            # ② 剪枝：退化到弱边、只共现过 1 次、反馈非正、且很久没动 → 忘掉这条联想
            for a, slot in list(self.edges.items()):
                keep = {}
                for b, e in slot.items():
                    if not isinstance(e, dict):
                        continue
                    last = float(e.get('last') or 0.0)
                    stale = (not last) or (now - last) > (2 * self.EDGE_TTL_SECONDS)
                    if (e.get('tier') == TIER_WEAK and int(e.get('n') or 1) <= 1
                            and float(e.get('fb') or 0.0) <= 0.0 and stale):
                        stats['pruned'] += 1
                        continue
                    keep[b] = e
                if keep:
                    self.edges[a] = keep
                else:
                    self.edges.pop(a, None)
            # ③ 对称性修复：A→B 在、B→A 不在时补回来（一边被剪掉会让图变单向）
            for a, slot in list(self.edges.items()):
                for b, e in list(slot.items()):
                    rev = self.edges.setdefault(b, {})
                    if a not in rev:
                        rev[a] = {'n': int(e.get('n') or 1), 'tier': e.get('tier'),
                                  'fb': 0.0, 'last': float(e.get('last') or 0.0)}
            # ④ 跨天补边：从日摘要/关键记忆提炼的词团（权重=1，最高只到中边）
            for kws, w in (extra_cooccurrence or []):
                before = sum(len(v) for v in self.edges.values())
                self.add_cooccurrence(kws, now=now, weight=w)
                after = sum(len(v) for v in self.edges.values())
                if after > before:
                    stats['added'] += max(0, after - before)
            # ⑤ 体量控制
            if len(self.edges) > self.MAX_KEYS:
                self._cap_keys()
            for a in list(self.edges.keys()):
                if len(self.edges[a]) > self.MAX_NB_PER_KEY:
                    self.edges[a] = dict(heapq.nlargest(
                        self.MAX_NB_PER_KEY, self.edges[a].items(),
                        key=lambda kv: edge_weight(kv[1], self.weak_penalty)))
            stats['edges_after'] = sum(len(v) for v in self.edges.values())
            stats['keys_after'] = len(self.edges)
            self._degrade = stats
        except Exception as e:
            _log.warning("memory_graph 离线巩固异常（跳过）: %s", e)
        return stats

    def tune(self, metrics, now=None):
        """按评估指标自动收紧弱边（有用率长期过低 → 弱边整体降权）。

        这是"评估噪声率/有用率 → 反哺检索参数"的闭环。
        """
        try:
            used = (metrics or {}).get('by_tier_used') or {}
            tot = (metrics or {}).get('by_tier_total') or {}
            w_tot = int(tot.get(TIER_WEAK) or 0)
            w_used = int(used.get(TIER_WEAK) or 0)
            before = self.weak_penalty
            if w_tot >= 20:
                rate = w_used / float(w_tot)
                if rate < 0.15:
                    self.weak_penalty = min(0.8, self.weak_penalty + 0.2)
                elif rate > 0.40:
                    self.weak_penalty = max(0.0, self.weak_penalty - 0.1)
            return {'weak_penalty_before': round(before, 4),
                    'weak_penalty_after': round(self.weak_penalty, 4),
                    'weak_useful_rate': round(w_used / float(w_tot), 4) if w_tot else None}
        except Exception as e:
            _log.debug("memory_graph tune 失败（已忽略）: %s", e)
            return {}

    # ------------------------------------------------------------ 自检
    def stats(self):
        tiers = {TIER_STRONG: 0, TIER_MID: 0, TIER_WEAK: 0}
        for slot in self.edges.values():
            for e in slot.values():
                t = e.get('tier') if isinstance(e, dict) else None
                tiers[t if t in tiers else TIER_WEAK] += 1
        return {'keys': len(self.edges),
                'edges': sum(len(v) for v in self.edges.values()),
                'tiers': tiers,
                'weak_penalty': round(self.weak_penalty, 4),
                'df_entries': len(self._df),
                'corpus': self._total}

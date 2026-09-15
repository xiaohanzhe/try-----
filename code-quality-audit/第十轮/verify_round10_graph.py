# -*- coding: utf-8 -*-
"""第十轮验证：分层关联图 + 受控多跳检索管线。

被验证的两条主张（用户原话）：
  · "限制道路：强边/中边/弱边 + hub 节点惩罚 + 路径打分而不是只看相似度"
  · "过滤要分层：每跳过滤防语义漂移、路径过滤保可信、重排去重降冗余、
     预算控制防失控；分层记忆、离线巩固、PPR、反馈学习边权、
     评估噪声率/有用率/成功率"

分组：
  G 图原语：分层边 / 边权 / 旧格式归一 / 共现 / 邻居每跳过滤 / 有界子图 /
           路径打分（含早剪与上限）/ PPR / 节点权（hub 惩罚）
  F 反馈与巩固：反馈调边权 / 重排去重 / 离线巩固（老化·剪枝·对称·补边）/ tune 反哺
  R 召回管线：多跳联想确实想起"没提过的词" / 每跳 tier 下限挡住漂移 /
           hub 被压制 / 预算不影响正确性 / 图缺失与旧格式都能降级跑通
  M 指标闭环：噪声率·有用率·成功率 / 反馈回填 / 落盘往返 / 清空
  X 回归守卫：forget_cycle 不再对 dict 边取 int / assoc 是属性 / 源码契约

全程把 RALSEI_MEMORY_DIR / RALSEI_DESKTOP 指向临时目录 —— **绝不碰真机记忆**。
必须用 C:\\Python311\\python.exe 运行。
"""
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
TMP = tempfile.mkdtemp(prefix='ralsei_g10_')
os.environ['RALSEI_DESKTOP'] = os.path.join(TMP, 'Desktop')
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(TMP, 'dev')
os.environ['RALSEI_LEGACY_MEMORY'] = os.path.join(TMP, '_no_such_legacy.json')
if MODS not in sys.path:
    sys.path.insert(0, MODS)

import memory_graph as MG                      # noqa: E402
from memory_system import MemorySystem         # noqa: E402
_MIN_PAGE_W = MemorySystem.MIN_PAGE_W          # 与产品同源的节点权下限（不写死数字）

PASS, FAIL = [], []


def ok(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('[PASS] ' if cond else '[FAIL] ') + name +
          ('' if cond else '   <<< ' + str(detail)))


def code_only(path):
    """剥掉注释与字符串后的源码（防"注释里出现关键字"型误判）。

    注意：tokenize **不产出空白 token**，所以 ''.join 会把 `import heapq` 粘成
    `importheapq`（漏判），而 needle 里带空格又会误判。因此这里保留 token 间的
    分隔，并配 `has()` 做"忽略空白"的包含判断 —— 自己也要能被自检（见 X0）。
    """
    out = []
    try:
        with io.open(path, encoding='utf-8') as fh:
            for tok in tokenize.generate_tokens(fh.readline):
                out.append('\n' if tok.type in (tokenize.COMMENT, tokenize.STRING)
                           else tok.string)
    except Exception:
        return ''
    return ' '.join(out)


def has(src, needle):
    """在源码里找 needle，两侧都忽略空白（needle 可以照自然写法写）。"""
    return re.sub(r'\s+', '', needle) in re.sub(r'\s+', '', src)


class FakeParent(object):
    def __init__(self):
        self.api_enabled = False


def new_ms(dirname='ms'):
    d = os.path.join(TMP, dirname)
    os.environ['RALSEI_MEMORY_DIR'] = d
    os.environ['RALSEI_LEGACY_MEMORY'] = os.path.join(TMP, '_no_such_legacy.json')
    return MemorySystem(FakeParent())


# =====================================================================  G 组
print('=== G 图原语 ===')
g = MG.MemoryGraph()
g.refresh_df({}, 0)

ok('G1 分层：共现次数 1/2/3+ → 弱/中/强', (
    MG.tier_of(1) == MG.TIER_WEAK and MG.tier_of(2) == MG.TIER_MID
    and MG.tier_of(3) == MG.TIER_STRONG), MG.tier_of(1))
ok('G1b 分层：弱共现 + 强反馈 → 升到中边（单次侥幸不封"极强"）',
   MG.tier_of(1, fb=0.6) == MG.TIER_MID, MG.tier_of(1, fb=0.6))
ok('G1c 分层：重复共现 + 强反馈 → 才封强边',
   MG.tier_of(2, fb=0.6) == MG.TIER_STRONG and MG.tier_of(2, fb=0.1) == MG.TIER_MID)

_w_s = MG.edge_weight({'n': 5, 'tier': MG.TIER_STRONG, 'fb': 0.0})
_w_m = MG.edge_weight({'n': 5, 'tier': MG.TIER_MID, 'fb': 0.0})
_w_w = MG.edge_weight({'n': 5, 'tier': MG.TIER_WEAK, 'fb': 0.0})
ok('G2 边权：强 > 中 > 弱（同共现次数）', _w_s > _w_m > _w_w, (_w_s, _w_m, _w_w))
ok('G2b 边权：weak_penalty 只压弱边',
   MG.edge_weight({'n': 5, 'tier': MG.TIER_WEAK}, 0.6) < _w_w
   and abs(MG.edge_weight({'n': 5, 'tier': MG.TIER_STRONG}, 0.6) - _w_s) < 1e-9)
ok('G2c 边权：正反馈抬权、负反馈压权',
   MG.edge_weight({'n': 5, 'tier': MG.TIER_MID, 'fb': 2.0})
   > MG.edge_weight({'n': 5, 'tier': MG.TIER_MID, 'fb': 0.0})
   > MG.edge_weight({'n': 5, 'tier': MG.TIER_MID, 'fb': -2.0}))

_norm = MG.normalize_assoc({'甲': {'乙': 2, '丙': {'n': 4, 'fb': 0.3, 'last': 9.0}},
                            '丁': 3, '戊': {'戊': 5}})
ok('G3 归一化：旧格式(int) 升级为边记录并定层',
   _norm['甲']['乙']['n'] == 2 and _norm['甲']['乙']['tier'] == MG.TIER_MID,
   _norm.get('甲'))
ok('G3b 归一化：新格式(n/fb/last) 保留并按次数定层',
   _norm['甲']['丙']['n'] == 4 and _norm['甲']['丙']['fb'] == 0.3
   and _norm['甲']['丙']['last'] == 9.0
   and _norm['甲']['丙']['tier'] == MG.TIER_STRONG, _norm.get('甲'))
ok('G3c 归一化：非法值丢弃 / 自环丢弃', '丁' not in _norm and '戊' not in _norm)
ok('G3d 种子归一：list/dict/str 都收（调用方传错类型不再静默全废）',
   MG.seed_map(['甲', '乙']) == {'甲': 1.0, '乙': 1.0}
   and MG.seed_map('甲') == {'甲': 1.0}
   and MG.seed_map({'甲': 2}) == {'甲': 2.0})

# 第十一轮更新：建边拓扑改为可配置（默认 star）。
# 这组断言原来隐含"全互连(clique)"—— 用 3 个词调一次，再断言 `edges['a'] == {b, c}`；
# 换成 star 后它**只是因为 a 恰好是核心词**才继续成立（歪打正着）。
# 现在改成：用 2 个词做"成边 + 升层"断言（与拓扑无关），另在第十一轮套件里
# 逐拓扑显式锁行为（`verify_round11_input.py` B 组）。
g2 = MG.MemoryGraph()
g2.refresh_df({}, 0)
g2.add_cooccurrence(['a', 'b'])
g2.add_cooccurrence(['a', 'b'])
ok('G4 共现：成边且邻接表对称', ('b' in g2.edges['a']) and ('a' in g2.edges['b']))
ok('G4b 共现两次 → n=2 且升为中边',
   g2.edges['a']['b']['n'] == 2 and g2.edges['a']['b']['tier'] == MG.TIER_MID)
g2.add_cooccurrence(['a', 'b'])
ok('G4c 共现三次 → 升为强边', g2.edges['a']['b']['tier'] == MG.TIER_STRONG)

g3 = MG.MemoryGraph()
g3.refresh_df({}, 0)
g3.MAX_NB_PER_KEY = 3
g3.add_cooccurrence(['hub'] + ['n%d' % i for i in range(8)])
ok('G5 每点邻居上限生效', len(g3.edges['hub']) <= 3, len(g3.edges.get('hub', {})))
g3.MAX_KEYS = 2
ok('G5b cap_keys(limit) 公开可用并生效',
   MG.MemoryGraph.cap_keys(g3, 2) <= 2 and len(g3.edges) <= 2, len(g3.edges))

# hub 惩罚：同一个词在语料里到处出现 / 连了很多人 → 权重要被压下去
gh = MG.MemoryGraph()
gh.add_cooccurrence(['hub'] + ['x%d' % i for i in range(12)])
_idx = {'hub': list(range(1000)), 'r@re': [0]}
gh.refresh_df(_idx, 1000)
ok('G6 hub 惩罚：高频词权重被显著压低',
   gh.node_weight('hub') < gh.node_weight('r@re') * 0.6,
   (gh.node_weight('hub'), gh.node_weight('r@re')))
ok('G6b hub 惩罚：权重落在 [0.25,1] 且罕见词接近上限',
   0.25 <= gh.node_weight('hub') <= 1.0 and gh.node_weight('r@re') >= 0.6)

gt = MG.MemoryGraph()
gt.refresh_df({}, 0)
gt.add_cooccurrence(['k', 'wk'])                     # 弱边
gt.add_cooccurrence(['k', 'mk']); gt.add_cooccurrence(['k', 'mk'])       # 中边
for _ in range(3):
    gt.add_cooccurrence(['k', 'sk'])                 # 强边
_mid_up = [n for n, _w, _nw in gt.neighbors('k', min_tier=MG.TIER_MID, limit=10)]
_strong_up = [n for n, _w, _nw in gt.neighbors('k', min_tier=MG.TIER_STRONG, limit=10)]
ok('G7 每跳过滤：min_tier=mid 剔除弱边', 'wk' not in _mid_up and 'mk' in _mid_up
   and 'sk' in _mid_up, _mid_up)
ok('G7b 每跳过滤：min_tier=strong 只剩强边', _strong_up == ['sk'], _strong_up)

# 有界子图：跳数 / 节点数 / 每跳 tier 下限 / 中转资格
sub = MG.MemoryGraph()
sub.refresh_df({}, 0)
sub.add_cooccurrence(['s', 'wm'])        # 弱：到达第 1 跳可以
sub.add_cooccurrence(['wm', 'wx'])       # 弱：但弱桥不让再出发 → wx 不该出现
sub.add_cooccurrence(['s', 'bm'])
for _ in range(2):
    sub.add_cooccurrence(['s', 'bm'])    # 中：够格当中转
sub.add_cooccurrence(['bm', 'cw'])       # 弱：到达第 2 跳可以（踩的是中桥）
sub.add_cooccurrence(['bm', 'm2'])
for _ in range(2):
    sub.add_cooccurrence(['bm', 'm2'])   # 中：够格当中转
sub.add_cooccurrence(['m2', 'dweak'])    # 弱：第 3 跳到不了（该跳门槛=中）
sub.add_cooccurrence(['m2', 'dmid'])
for _ in range(2):
    sub.add_cooccurrence(['m2', 'dmid'])  # 中：第 3 跳到得了
_b = MG.RecallBudget(max_hops=3, max_nodes=64, max_edges_per_node=8,
                     max_paths=200, max_candidates=12, max_ms=5000.0)
_nodes, _adj = sub.build_subgraph({'s': 1.0}, _b.start())
ok('G8 有界子图：弱边可以到达（稀疏数据下多跳才不失效）',
   'wm' in _nodes and 'cw' in _nodes, _nodes)
ok('G8b 中转资格：弱桥不让继续出发（噪声词当跳板 → 漂移，被掐断）',
   'wx' not in _nodes, _nodes)
ok('G8c 中转资格：中桥可以继续出发，第 3 跳的到达门槛=中边',
   'dmid' in _nodes and 'dweak' not in _nodes, _nodes)
_b2 = MG.RecallBudget(max_hops=3, max_nodes=2, max_paths=200, max_ms=5000.0)
_n2, _ = sub.build_subgraph({'s': 1.0}, _b2.start())
ok('G8d 有界子图：节点数被 max_nodes 卡住', len(_n2) <= 2, _n2)
ok('G8e 有界子图：种子传 list 也照常工作（类型归一化）',
   len(sub.build_subgraph(['s'], _b2.start())[0]) <= 2)
ok('G8f 跳数上限生效（max_hops=1 时只剩第一跳）',
   set(sub.build_subgraph({'s': 1.0},
                          MG.RecallBudget(max_hops=1, max_nodes=64,
                                          max_paths=200, max_ms=5000.0).start()
                          )[0]) == {'s', 'wm', 'bm'})
ok('G8g 重排去重：同日条数上限会把同一天的回忆压住（防一次刷屏）',
   len(MG.MemoryGraph.rerank(
       [{'text': 'a%d' % i, 'kw': ['k%d' % i], 'day': 'D', 'score': 1.0 - i * 0.1}
        for i in range(6)], limit=6, max_per_day=3)) == 3)

_p = MG.MemoryGraph()
_p.refresh_df({}, 0)
for _ in range(3):
    _p.add_cooccurrence(['a', 'b'])
    _p.add_cooccurrence(['b', 'c'])
_bp = MG.RecallBudget(max_hops=3, max_nodes=32, max_edges_per_node=8,
                      max_paths=50, max_ms=5000.0, min_path_score=0.0)
_paths = _p.paths({'a': 1.0}, _bp.start(), min_node_w=0.0)
_l1 = [x for x in _paths if x['nodes'] == ['a', 'b']]
_l2 = [x for x in _paths if x['nodes'] == ['a', 'b', 'c']]
ok('G9 路径打分：多跳路径被枚举且可解释',
   bool(_l1) and bool(_l2), [x['nodes'] for x in _paths])
ok('G9b 路径打分：跨跳衰减 → 两跳分低于一跳',
   _l2 and _l1 and _l2[0]['score'] < _l1[0]['score'],
   (_l1[0]['score'] if _l1 else None, _l2[0]['score'] if _l2 else None))
ok('G9c 路径打分：结果按分数降序', all(
    _paths[i]['score'] >= _paths[i + 1]['score'] for i in range(len(_paths) - 1)))
_hi = MG.RecallBudget(max_hops=3, max_paths=50, max_ms=5000.0, min_path_score=0.99)
ok('G9d 路径过滤（早剪）：阈值抬高后路径被剪掉',
   len(_p.paths({'a': 1.0}, _hi.start(), min_node_w=0.0)) == 0)
_lo = MG.RecallBudget(max_hops=3, max_paths=1, max_ms=5000.0, min_path_score=0.0)
ok('G9e 预算：max_paths 卡住路径数量',
   len(_p.paths({'a': 1.0}, _lo.start(), min_node_w=0.0)) <= 1)

_pp = MG.MemoryGraph()
_pp.refresh_df({}, 0)
for _ in range(3):
    _pp.add_cooccurrence(['seed', 'near'])
    _pp.add_cooccurrence(['hub2'] + ['d%d' % i for i in range(9)])
_pp.add_cooccurrence(['seed', 'hub2'])
_bpp = MG.RecallBudget(max_hops=2, max_nodes=64, max_edges_per_node=8,
                       max_paths=200, max_ms=5000.0, min_path_score=0.0)
_ppr = _pp.ppr({'seed': 1.0}, _bpp.start(), iters=8, alpha=0.15)
ok('G10 PPR：返回概率分布且和为 1',
   bool(_ppr) and abs(sum(_ppr.values()) - 1.0) < 0.05, sum(_ppr.values()))
ok('G10b PPR：种子自身权重最高', _ppr and max(_ppr, key=_ppr.get) == 'seed', _ppr)

# 稀疏语料（真实对话的常态：每条边都只共现过 1 次）也必须能走两跳 ——
# 这条是"中转资格"规则的回归锁：多跳的成败系于"桥够不够硬"。
# 一旦有人把"弱桥也能当中转"改回来，第 2 条断言会立刻红（用它来防漂移回潮）。
_sp = MG.MemoryGraph()
_sp.refresh_df({}, 0)
_sp.add_cooccurrence(['w1', 'w2'])
_sp.add_cooccurrence(['w2', 'w3'])
_bsp = MG.RecallBudget(max_hops=3, max_nodes=32, max_edges_per_node=8,
                       max_paths=50, max_ms=5000.0, min_path_score=0.02)
ok('G11 稀疏语料：全弱边时两跳不可达（弱桥不算桥，防漂移）',
   not any(p['nodes'] == ['w1', 'w2', 'w3']
           for p in _sp.paths({'w1': 1.0}, _bsp.start(), min_node_w=_MIN_PAGE_W)))
_sp2 = MG.MemoryGraph()
_sp2.refresh_df({}, 0)
_sp2.add_cooccurrence(['w1', 'w2'])
for _ in range(2):
    _sp2.add_cooccurrence(['w1', 'w2'])          # 升级为中桥
_sp2.add_cooccurrence(['w2', 'w3'])
_bsp2 = MG.RecallBudget(max_hops=3, max_nodes=32, max_edges_per_node=8,
                        max_paths=50, max_ms=5000.0, min_path_score=0.02)
ok('G11b 稀疏语料：桥升级为中边后两跳恢复可达（不是一刀切封死）',
   any(p['nodes'] == ['w1', 'w2', 'w3']
       for p in _sp2.paths({'w1': 1.0}, _bsp2.start(), min_node_w=_MIN_PAGE_W)))
# hub 惩罚的量化：同样的两跳，中转词是 hub 时路径分严格更低
_hub = MG.MemoryGraph()
_hub.refresh_df({}, 0)
for _ in range(2):
    _hub.add_cooccurrence(['h1', 'mid'])
_hub.add_cooccurrence(['mid', 'h2'])
_bh = MG.RecallBudget(max_hops=3, max_nodes=32, max_edges_per_node=8,
                      max_paths=50, max_ms=5000.0, min_path_score=0.0)
_p_norm = [p for p in _hub.paths({'h1': 1.0}, _bh.start(), min_node_w=0.0)
           if p['nodes'] == ['h1', 'mid', 'h2']]
_hub.refresh_df({'h1': [0], 'mid': list(range(400)), 'h2': [0]}, 400)
_p_hub = [p for p in _hub.paths({'h1': 1.0}, _bh.start(), min_node_w=0.0)
          if p['nodes'] == ['h1', 'mid', 'h2']]
ok('G12 hub 惩罚可量化：中转词是 hub 时同一两跳的路径分严格更低',
   _p_norm and _p_hub and _p_hub[0]['score'] < _p_norm[0]['score'],
   (_p_norm[0]['score'] if _p_norm else None,
    _p_hub[0]['score'] if _p_hub else None))

# =====================================================================  F 组
print('=== F 反馈与巩固 ===')
_fb = MG.MemoryGraph()
_fb.refresh_df({}, 0)
_fb.add_cooccurrence(['s1', 't1'])
for _ in range(2):
    _fb.add_cooccurrence(['s2', 't2'])
_w_before = MG.edge_weight(_fb.edges['s1']['t1'])
_touched = _fb.feedback([{'nodes': ['s1', 't1'], 'score': 0.5},
                         {'nodes': ['s2', 't2'], 'score': 0.3}], True, lr=0.5)
ok('F1 反馈：正反馈沿路径加边权',
   _touched == 2 and MG.edge_weight(_fb.edges['s1']['t1']) > _w_before,
   (_touched, _w_before, MG.edge_weight(_fb.edges['s1']['t1'])))
ok('F1b 反馈：单次正反馈把弱边推成中边（反馈学习确实改层）',
   _fb.edges['s1']['t1']['tier'] == MG.TIER_MID, _fb.edges['s1']['t1'])
_fb2 = MG.MemoryGraph()
_fb2.refresh_df({}, 0)
_fb2.add_cooccurrence(['s', 't'])          # 只共现一次：弱边，未被上限饱和
_w2 = MG.edge_weight(_fb2.edges['s']['t'])
_fb2.feedback([{'nodes': ['s', 't']}], False, lr=0.5)
ok('F1c 反馈：负反馈减权（初始同强度下）',
   MG.edge_weight(_fb2.edges['s']['t']) < _w2,
   (_w2, MG.edge_weight(_fb2.edges['s']['t'])))
_fb3 = MG.MemoryGraph()
_fb3.refresh_df({}, 0)
_fb3.add_cooccurrence(['s', 't'])
_fb3.feedback([{'nodes': ['s', 't']}], False, lr=0.5)
_dn = _w2 - MG.edge_weight(_fb3.edges['s']['t'])
_fb4 = MG.MemoryGraph()
_fb4.refresh_df({}, 0)
_fb4.add_cooccurrence(['s', 't'])
_fb4.feedback([{'nodes': ['s', 't']}], True, lr=0.5)
_dp = MG.edge_weight(_fb4.edges['s']['t']) - _w2
ok('F1d 反馈：负反馈幅度小于正反馈（不因一次失败毁掉整条联想）',
   _dn < _dp, (_dn, _dp))

_rr = MG.MemoryGraph.rerank(
    [{'text': '甲', 'kw': ['塞尔达', '剧情'], 'day': '2026-09-15', 'score': 0.9},
     {'text': '乙', 'kw': ['塞尔达', '剧情', '攻略'], 'day': '2026-09-15',
      'score': 0.8},
     {'text': '丙', 'kw': ['塞尔达', '剧情'], 'day': '2026-09-15', 'score': 0.7},
     {'text': '丁', 'kw': ['做饭'], 'day': '2026-09-15', 'score': 0.6},
     {'text': '戊', 'kw': ['跑步'], 'day': '2026-09-15', 'score': 0.5}],
    limit=5, overlap_threshold=0.6, max_per_day=2)
_names = [x['text'] for x in _rr]
ok('F2 重排去重：关键词高度重叠的只留一条', _names.count('甲') + _names.count('乙')
   + _names.count('丙') == 1, _names)
ok('F2b 重排去重：同日条数受限', len(_rr) <= 2, _names)

_cg = MG.MemoryGraph()
_cg.refresh_df({}, 0)
_old = time.time() - 100 * 86400.0
_cg.edges = {'p': {'q': {'n': 3, 'tier': MG.TIER_STRONG, 'fb': 0.0, 'last': _old},
                   'r': {'n': 1, 'tier': MG.TIER_WEAK, 'fb': 0.0, 'last': _old}},
             'q': {'p': {'n': 3, 'tier': MG.TIER_STRONG, 'fb': 0.0, 'last': _old}}}
_cs = _cg.consolidate(now=time.time(),
                      extra_cooccurrence=[(['n1', 'n2', 'n3'], 2)])
ok('F3 离线巩固：久未共现的边被老化降级',
   _cs['decayed'] >= 1 and _cs['demoted'] >= 1, _cs)
ok('F3b 离线巩固：弱且陈旧且无正反馈的边被剪掉', _cs['pruned'] >= 1, _cs)
ok('F3c 离线巩固：对称性被修复（q→p 缺了会补）',
   'p' in _cg.edges.get('q', {}) and 'q' in _cg.edges.get('p', {}))
ok('F3d 离线巩固：从日摘要词团补出新边',
   ('n1' in _cg.edges and 'n2' in _cg.edges) and _cs['added'] >= 3, _cs)
ok('F3e 离线巩固：返回可留痕的统计', all(
    k in _cs for k in ('edges_before', 'edges_after', 'pruned', 'added')))

_tn = MG.MemoryGraph()
_metrics = {'by_tier_total': {MG.TIER_WEAK: 100}, 'by_tier_used': {MG.TIER_WEAK: 5}}
_r1 = _tn.tune(_metrics)
ok('F4 指标反哺：弱边有用率 5% → 自动加压制量',
   _tn.weak_penalty > 0 and _r1['weak_useful_rate'] == 0.05, _r1)
_wp_before = _tn.weak_penalty
_r2 = _tn.tune({'by_tier_total': {MG.TIER_WEAK: 100},
                'by_tier_used': {MG.TIER_WEAK: 80}})
ok('F4b 指标反哺：弱边有用率高 → 放松压制',
   _tn.weak_penalty < _wp_before, (_wp_before, _tn.weak_penalty))
ok('F4c 样本不足时不动参数',
   MG.MemoryGraph().tune({'by_tier_total': {MG.TIER_WEAK: 3},
                          'by_tier_used': {MG.TIER_WEAK: 0}})['weak_penalty_after'] == 0.0)
_st = _fb2.stats()
ok('F5 图自检：节点/边/分层计数可用',
   _st['edges'] >= 2 and sum(_st['tiers'].values()) == _st['edges'], _st)

# =====================================================================  R 组
print('=== R 召回管线 ===')
KW = {}


def kw_stub(text, limit=6):
    return list(KW.get(str(text), []))[:limit]


def ms_with(kw_map, dirname, max_per_day=None):
    """造一个干净的 MemorySystem 并把抽词器换成确定性桩。

    `max_per_day` 用于放宽"同日最多留几条"——测试里所有片段都是"今天"的，
    默认上限会先把结果截断，反而看不清多跳有没有生效（产品默认值保持不变）。
    """
    global KW
    KW = dict(kw_map)
    m = new_ms(dirname)
    m._kw_of = kw_stub
    if max_per_day is not None:
        m.RERANK_MAX_PER_DAY = max_per_day
    return m


# R1 多跳联想：目标片段与线索**没有共同关键词**，只能靠两跳想到
m1 = ms_with({'cue': ['塞尔达'], 'fA': ['塞尔达', '海拉鲁'],
              'fB': ['海拉鲁', '公主'], 'fC': ['公主', '主题曲'],
              'fX': ['完全不相关']}, 'r1', max_per_day=8)
m1.fragments = []
m1._index = {}
for _t in ('fA', 'fB', 'fC', 'fX'):
    m1.add_fragment(_t, who='user', importance=0.6)
for _ in range(3):            # 塞尔达-海拉鲁、海拉鲁-公主：强边
    m1.add_assoc(['塞尔达', '海拉鲁'])
    m1.add_assoc(['海拉鲁', '公主'])
    m1.add_assoc(['公主', '主题曲'])
_hits = m1.recall('cue', limit=5)
_texts = [h.get('text') for h in _hits]
ok('R1 多跳：想到与线索无共同词的两跳片段',
   'fB' in _texts and 'fC' in _texts, _texts)
ok('R1b 多跳：直接命中的片段排在最前', _texts and _texts[0] == 'fA', _texts)
_via_any = [h.get('via') for h in _hits if h.get('via')]
ok('R1c 多跳：回忆带"怎么想到的"（via）可解释', bool(_via_any), _hits)
_hops = sorted(set(h.get('hop') for h in _hits if h.get('hop') is not None))
ok('R1d 多跳：跳数被记录（用于指标分桶）', _hops and max(_hops) >= 2, _hops)
ok('R1e 多跳：完全无关的片段没被拉进来', 'fX' not in _texts, _texts)

# R2 防漂移（三件事）：弱桥不能当中转；三步之外的弱边到不了；hub 中转分会掉
m2 = ms_with({'cue': ['起点'], 'f1': ['起点'], 'f2': ['弱桥'], 'f3': ['弱桥远端'],
              'f4': ['硬桥'], 'f5': ['硬桥远端']}, 'r2', max_per_day=8)
for _t in ('f1', 'f2', 'f3', 'f4', 'f5'):
    m2.add_fragment(_t, who='user', importance=0.6)
m2.add_assoc(['起点', '弱桥'])                 # 弱：能到达
m2.add_assoc(['弱桥', '弱桥远端'])             # 弱：但弱桥不让再出发 → 到不了
m2.add_assoc(['起点', '硬桥'])
for _ in range(2):
    m2.add_assoc(['起点', '硬桥'])             # 中：够格当中转
m2.add_assoc(['硬桥', '硬桥远端'])             # 弱到达 OK（踩的是中桥）
_t2 = [h.get('text') for h in m2.recall('cue', limit=6)]
ok('R2 防漂移：弱边能到达（一步联想照常）', 'f2' in _t2, _t2)
ok('R2b 防漂移：弱桥不让当中转（"顺着噪声词滑走"被掐断）', 'f3' not in _t2, _t2)
ok('R2c 防漂移：踩着中边以上的桥，两跳照常通行', 'f5' in _t2, _t2)
ok('R2d 防漂移：两跳结果带 via（能解释"我是怎么想到的"）',
   any(h.get('via') for h in m2.recall('cue', limit=6) if h.get('text') == 'f5'),
   [h.get('via') for h in m2.recall('cue', limit=6)])

# 同样的两跳，把"中转词"换成到处都出现的 hub → 路径分被压低
m2b = ms_with({'cue': ['起点'], 'f1': ['起点'], 'f2h': ['hub远端']}, 'r2hub')
m2b.add_fragment('f1', who='user', importance=0.6)
m2b.add_fragment('f2h', who='user', importance=0.6)
m2b.add_assoc(['起点', 'hub中'])
for _ in range(2):
    m2b.add_assoc(['起点', 'hub中'])           # 中桥（够格当中转）
m2b.add_assoc(['hub中', 'hub远端'])
_b_r2 = MG.RecallBudget(max_hops=3, max_nodes=32, max_edges_per_node=8,
                        max_paths=50, max_ms=5000.0, min_path_score=0.0)
_p_norm = [p for p in m2b._graph.paths({'起点': 1.0}, _b_r2.start(), min_node_w=0.0)
           if p['nodes'][-1] == 'hub远端']
m2b._graph.refresh_df({'起点': [0], 'hub中': list(range(400)), 'hub远端': [0]}, 400)
_p_hub = [p for p in m2b._graph.paths({'起点': 1.0}, _b_r2.start(), min_node_w=0.0)
          if p['nodes'][-1] == 'hub远端']
ok('R2e hub 惩罚：中转词变 hub 后，同一两跳的路径分被压低（权重比约 2.5:1）',
   _p_norm and _p_hub and _p_hub[0]['score'] < _p_norm[0]['score'] * 0.6,
   (_p_norm[0]['score'] if _p_norm else None,
    _p_hub[0]['score'] if _p_hub else None))

# R3 hub 惩罚：到处都出现的词不能当联想落点/不能盖过主线
m3 = ms_with({'cue': ['塞尔达'], 'fA': ['塞尔达'], 'fH': ['通用词']}, 'r3')
m3.add_fragment('fA', who='user', importance=0.6)
m3.add_fragment('fH', who='user', importance=0.6)
for _ in range(3):
    m3.add_assoc(['塞尔达', '通用词'])
    m3.add_assoc(['通用词'] + ['杂%d' % i for i in range(8)])
m3._index['通用词'] = list(range(400))          # 假装它在 400 条片段里都出现
m3._graph.refresh_df(m3._index, 400)
_t3 = m3.recall('cue', limit=5)
ok('R3 hub 惩罚：高频词的节点权被压低',
   m3._graph.node_weight('通用词') < m3._graph.node_weight('塞尔达') * 0.7,
   (m3._graph.node_weight('通用词'), m3._graph.node_weight('塞尔达')))
ok('R3b hub 惩罚：直接命中的片段仍排最前',
   [h.get('text') for h in _t3][:1] == ['fA'], [h.get('text') for h in _t3])

# R4 预算：把预算压到极小，正确性不塌
m4 = ms_with({'cue': ['甲'], 'f1': ['甲'], 'f2': ['乙'], 'f3': ['丙']}, 'r4')
m4.add_fragment('f1', who='user', importance=0.6)
m4.add_fragment('f2', who='user', importance=0.6)
m4.add_fragment('f3', who='user', importance=0.6)
m4.add_assoc(['甲', '乙'])
m4.add_assoc(['乙', '丙'])
m4.RECALL_BUDGET = dict(max_hops=3, max_nodes=2, max_edges_per_node=1,
                        max_paths=1, max_candidates=3, max_ms=50.0,
                        max_llm_calls=0, min_path_score=0.02)
try:
    _t4 = m4.recall('cue', limit=3)
    ok('R4 预算：极小预算下仍返回结果且不超限', isinstance(_t4, list)
       and len(_t4) <= 3, _t4)
except Exception as e:
    ok('R4 预算：极小预算下仍返回结果且不超限', False, e)

# R5 降级：图缺失 / 旧格式 assoc 都能跑
m5 = ms_with({'cue': ['甲'], 'f1': ['甲']}, 'r5')
m5.add_fragment('f1', who='user', importance=0.6)
m5._graph = None
_t5 = m5.recall('cue', limit=3)
ok('R5 降级：图缺失时靠直接命中仍能想起', [h.get('text') for h in _t5] == ['f1'], _t5)

m6 = new_ms('r6')
m6.memory_dir = os.path.join(TMP, 'r6legacy')
os.makedirs(m6.memory_dir, exist_ok=True)
m6.memory_file = os.path.join(m6.memory_dir, 'memory.json')
with io.open(m6.memory_file, 'w', encoding='utf-8') as fh:
    json.dump({'schema': 1, 'long_term_memory': {},
               'fragments': [{'id': 1, 't': time.time(), 'day': '2026-09-15',
                              'who': 'user', 'kind': 'dialogue', 'text': 'f1',
                              'kw': ['甲'], 'salience': 0.6, 'strength': 0.6}],
               'assoc': {'甲': {'乙': 2}}, 'next_id': 2}, fh, ensure_ascii=False)
m6.load_memory()
m6._kw_of = kw_stub
KW = {'cue': ['甲']}
ok('R6 兼容：旧格式 assoc(int) 升级为边记录',
   isinstance(m6.assoc.get('甲', {}).get('乙'), dict)
   and m6.assoc['甲']['乙']['n'] == 2, m6.assoc.get('甲'))
try:
    _t6 = m6.recall('cue', limit=3)
    ok('R6b 兼容：旧格式记忆可正常召回（不再对 dict 取 int）',
       [h.get('text') for h in _t6] == ['f1'], _t6)
except Exception as e:
    ok('R6b 兼容：旧格式记忆可正常召回（不再对 dict 取 int）', False, e)

# =====================================================================  M 组
print('=== M 指标与反馈闭环 ===')
m7 = ms_with({'cue': ['塞尔达'], 'fA': ['塞尔达', '海拉鲁'],
              'fB': ['海拉鲁', '公主']}, 'm7')
m7.add_fragment('fA', who='user', importance=0.6)
m7.add_fragment('fB', who='user', importance=0.6)
for _ in range(1):        # 合计 n=2（中边，未饱和）：这样"反馈抬权"才看得见
    m7.add_assoc(['塞尔达', '海拉鲁'])
    m7.add_assoc(['海拉鲁', '公主'])
_h7 = m7.recall('cue', limit=5)
_tok = _h7[0].get('recall_token') if _h7 else None
ok('M1 召回：每条结果带 recall_token（供反馈回填）',
   _tok is not None and all('recall_token' in h for h in _h7))
_rep0 = m7.recall_report()
ok('M1b 指标：噪声率/有用率/成功率三个口径齐全',
   all(k in _rep0 for k in ('noise_rate', 'useful_rate', 'success_rate', 'by_tier')))
_before_fb = MG.edge_weight(m7._graph.edges['海拉鲁']['公主'])
_fb_of = m7._graph.edges['海拉鲁']['公主'].get('fb', 0.0)
_fbr = m7.recall_feedback(_tok, success=True, used=1)
_rep1 = m7.recall_report()
ok('M2 反馈回填：标记成功/用过 → 有用率上升',
   _fbr.get('ok') and _rep1['used'] == 1 and _rep1['useful_rate'] > 0
   and _rep1['success_rate'] > 0, (_fbr, _rep1))
ok('M2b 反馈学习：召回管线真的把路径边权抬上去了（不只是图层的单测）',
   _fbr.get('touched', 0) >= 1
   and MG.edge_weight(m7._graph.edges['海拉鲁']['公主']) > _before_fb
   and m7._graph.edges['海拉鲁']['公主'].get('fb', 0.0) > _fb_of,
   (_fbr, _before_fb, MG.edge_weight(m7._graph.edges['海拉鲁']['公主'])))
ok('M2c 反馈回填：未知 token 安全返回',
   m7.recall_feedback(999999, success=True).get('ok') is False)
ok('M2d 指标：按层/按跳分桶可用',
   bool(_rep1['by_tier']) and bool(_rep1['by_hop_total']), _rep1)

m7.save_memory()
m7b = new_ms('m7')
m7b._kw_of = kw_stub
ok('M3 落盘往返：召回指标跨会话保留',
   m7b.recall_stats['queries'] >= 1 and m7b.recall_stats['used'] >= 1,
   m7b.recall_stats)
ok('M3b 落盘往返：图的分层边记录结构完整',
   isinstance(m7b.assoc.get('塞尔达', {}).get('海拉鲁'), dict)
   and 'tier' in m7b.assoc['塞尔达']['海拉鲁'], m7b.assoc.get('塞尔达'))
m7g = m7b._graph
m7g.weak_penalty = 0.6
m7b.save_memory()
m7c = new_ms('m7')
ok('M3c 落盘往返：学出来的 weak_penalty 不丢', m7c._graph.weak_penalty == 0.6,
   m7c._graph.weak_penalty)

m7b.reset_all()
ok('M4 清空：召回记账与日志一并归零',
   m7b.recall_stats['queries'] == 0 and m7b.recall_stats['used'] == 0
   and not m7b._recall_log and m7b._graph.weak_penalty == 0.0)

m8 = ms_with({'cue': ['塞尔达'], 'fA': ['塞尔达', '海拉鲁'],
              'fB': ['海拉鲁', '公主']}, 'm8')
m8.add_fragment('fA', who='user', importance=0.6)
m8.add_fragment('fB', who='user', importance=0.6)
for _ in range(3):
    m8.add_assoc(['塞尔达', '海拉鲁'])
    m8.add_assoc(['海拉鲁', '公主'])
_cons = m8.consolidate()
ok('M5 离线巩固：可由 memory_system 侧一键触发并留痕',
   'edges_after' in _cons and 'tune' in _cons, _cons)
ok('M5b 离线巩固：巩固后重建索引（接口仍可用）', bool(m8._index))
_txt = m8.recall_text('cue', limit=5)
ok('M5c 出口文案：把"怎么想到的"带进模型上下文',
   '联想到的' in _txt or '零星的回忆' in _txt, _txt)

m9 = ms_with({'cue': ['甲']}, 'm9')
m9.add_fragment('f1', who='user', importance=0.5)
m9.remember_key('important', '主人说甲很重要')
_t9 = m9.recall('cue', limit=4)
ok('M6 关键记忆：仍然优先出现在召回结果里',
   any(h.get('is_key') for h in _t9), _t9)

# M7 LLM 验证钩子：默认关闭、注入后受预算额度约束
_v10 = ms_with({'cue': ['甲'], 'f1': ['甲']}, 'm10')
_v10.add_fragment('f1', who='user', importance=0.6)
_calls = {'n': 0}


def _fake_verifier(items, cue, budget):
    _calls['n'] += 1
    return list(items)[:1]


_v10.recall('cue', limit=3)
ok('M7 LLM 验证：默认不接验证器 → 一次都不调用',
   _calls['n'] == 0 and int(_v10.recall_stats.get('llm_calls') or 0) == 0)
ok('M7b LLM 验证：注入成功（返回 True）', _v10.set_verifier(_fake_verifier) is True)
_v10.recall('cue', limit=3)
ok('M7c LLM 验证：预算 max_llm_calls=0（默认）时仍然不调用（预算控死）',
   _calls['n'] == 0, _calls)
_v10.RECALL_BUDGET = dict(_v10.RECALL_BUDGET, max_llm_calls=1)
_v_kept = _v10.recall('cue', limit=3)
ok('M7d LLM 验证：给出额度后按验证结果裁剪',
   _calls['n'] == 1 and len(_v_kept) <= 1 and _v10.recall_stats['llm_calls'] == 1,
   (_calls, _v_kept))
ok('M7e LLM 验证：额度用尽后不再调用',
   (_v10.recall('cue', limit=3) is not None) and _calls['n'] == 1, _calls)
_v10.RECALL_BUDGET = dict(_v10.RECALL_BUDGET, max_llm_calls=5)


def _boom(items, cue, budget):
    _calls['n'] += 1
    raise RuntimeError('verifier down')


_v10.set_verifier(_boom)
_calls['n'] = 0
_t_fail = _v10.recall('cue', limit=3)
ok('M7f LLM 验证：验证器抛异常时保留原结果、且不计入已用额度',
   isinstance(_t_fail, list) and _t_fail and _calls['n'] == 1
   and int(_v10.recall_stats.get('llm_calls') or 0) == 1,
   (_calls, _t_fail, _v10.recall_stats.get('llm_calls')))
ok('M7g LLM 验证：可摘除（set_verifier(None) → False）',
   _v10.set_verifier(None) is False)

# =====================================================================  X 组
print('=== X 回归守卫 ===')
_src = code_only(os.path.join(MODS, 'memory_system.py'))
_gsrc = code_only(os.path.join(MODS, 'memory_graph.py'))
ok('X0 校验器自检：token 间隔得以保留（否则 import heapq 会被粘成 importheapq，'
   '负向断言会假通过）',
   'import heapq' in _gsrc and 'importheapq' not in _gsrc)
ok('X1 回归：forget_cycle 不再对 dict 边取 int（改交图自裁剪）',
   not has(_src, 'int(v) for v in') and has(_src, '_graph.cap_keys'))
ok('X2 契约：assoc 是属性（图是唯一真相源）',
   isinstance(MemorySystem.assoc, property))
ok('X3 契约：召回走"路径分 + PPR"而非只看相似度',
   has(_src, 'graph.paths(') and has(_src, 'graph.ppr('))
ok('X4 契约：预算对象参与召回', has(_src, 'RecallBudget(') and has(_src, 'RECALL_BUDGET'))
ok('X5 契约：更新周期里接了离线巩固',
   has(_src, 'CONSOLIDATE_INTERVAL') and has(_src, 'self.consolidate()'))
ok('X6 契约：反馈学习与指标评估入口存在',
   has(_src, 'def recall_feedback') and has(_src, 'def recall_report'))
ok('X7 契约：图模块零第三方依赖（纯标准库）',
   has(_gsrc, 'import heapq') and has(_gsrc, 'import math')
   and not has(_gsrc, 'import requests') and not has(_gsrc, 'import numpy'))
ok('X8 契约：LLM 验证钩子默认关闭且受预算额度约束',
   has(_src, 'self._verifier is not None')
   and has(_src, 'self._verifier = fn if callable(fn) else None')
   and has(_gsrc, 'max_llm_calls'))
ok('X9 契约：通路过滤五层都有实现（每跳/路径/重排/预算/图内）',
   has(_gsrc, 'HOP_TIER_FLOOR') and has(_gsrc, 'min_path_score')
   and has(_gsrc, 'def rerank') and has(_gsrc, 'max_nodes'))

# ===================================================================== 汇总
shutil.rmtree(TMP, ignore_errors=True)
print('')
print('=' * 62)
print('第十轮自检：%d PASS / %d FAIL' % (len(PASS), len(FAIL)))
if FAIL:
    print('失败项：')
    for f in FAIL:
        print('  - ' + f)
print('=' * 62)
sys.exit(1 if FAIL else 0)

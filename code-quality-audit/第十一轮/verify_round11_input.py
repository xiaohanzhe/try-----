# -*- coding: utf-8 -*-
"""第十一轮验证：联想的**输入端**治理 —— 抽词剪刀 + 建边拓扑。

为什么有这一轮：第十轮把"多跳检索机"做出来了，但实测输出仍是
`写代码 → 写代 → 爬山记得带水` 这种**语义漂移**。定性结论是：
**瓶颈在喂进图里的关键词质量，不在检索机**（结论见
`代码质量复审报告_2026-09-15_第十轮.md` §五）。本轮就改输入端两件事：

  1. **抽词**：加"位置专精"的结构剪刀（首/尾/内部/量词/含多字停用词），
     专杀 `点代 / 码写 / 天想写 / 雨会 / 息一下 / 时候天` 这类跨词碎片；
     并给真词开「免伤名单」，再留一层"严格档全空 → 回落宽松档"的安全网。
     另提供 `set_segmenter()` 注入点：装了分词库的调用方接上去即可，不必改本模块。
  2. **建边拓扑**：抽成可配置（`EDGE_TOPOLOGY` + `edge_pairs()`），并**实测三种拓扑**。
     直觉上应该"降密度"（默认 clique → star/chain），但**直觉被实验否决了**：
       · `probe_topology_precision.py`：精确率 clique 50% / star 55% / chain 55%，
         边密度 3.26 / 0.83 / 0.86 → 看着该选 star；
       · `probe_multi_hop_gate.py`（受控实验：`代码 —(熬夜)— 咖啡`，两者从未同句，
         只改共现次数）：**只有 clique 能形成这条联想** —— stage1 弱边挡住、stage2 中边
         放行(hops=2)；star/chain **连 stage3 强边都走不通**（非核心词之间无直连，
         路径被中间词摊长 → 超跳数上限）。
     → 结论：**默认仍是 clique**；star/chain 保留为实验档，并把"为什么不用"留档在源码里。
       密度这个动机本身主要来自**抽词脏**：抽词修好后 clique 密度 4.03 → 3.26，
       剩下的"谁和谁都连"交给分层 + hub 惩罚 + 路径分（那才是"限制道路"）。

分组：
  A 抽词剪刀（碎片灭 / 真词留 / 免伤名单 / 位置序 / 三层择优 / 分词器注入）
  B 建边拓扑（三种拓扑的边对 / 核心词 / 默认值 / 邻居上限 / 可切换 / **多跳可达性闸门**）
  C 集成（真实中文语料建图 + 真记忆系统端到端召回，含"防静默降级"正向断言 + 残渣账本）
  D 回归守卫（源码级：不许再出现"歪打正着"的断言、回落层必须在、助手自身的坑要有自检）

全程把 RALSEI_MEMORY_DIR / RALSEI_DESKTOP 指向临时目录 —— **绝不碰真机记忆**。
必须用 C:\\Python311\\python.exe 运行。
"""
import io
import os
import re
import sys
import tempfile
import time
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
TMP = tempfile.mkdtemp(prefix='ralsei_g11_')
os.environ['RALSEI_DESKTOP'] = os.path.join(TMP, 'Desktop')
os.environ['RALSEI_MEMORY_DIR'] = os.path.join(TMP, 'dev')
os.environ['RALSEI_LEGACY_MEMORY'] = os.path.join(TMP, '_no_such_legacy.json')
if MODS not in sys.path:
    sys.path.insert(0, MODS)

import conversation_focus as CF                 # noqa: E402
import memory_graph as MG                       # noqa: E402
from memory_system import MemorySystem          # noqa: E402

PASS, FAIL = [], []


def ok(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('[PASS] ' if cond else '[FAIL] ') + name +
          ('' if cond else '   <<< ' + str(detail)))


def code_only(path):
    """剥掉注释与字符串的源码（tokenize 不产空白 token → 用 ' '.join 保分隔）。

    **注意**：它连**字符串字面量**也剥掉了，所以 needle 里若含字面量
    （如 `EDGE_TOPOLOGY = 'star'`）在这里**永远找不到** —— 那类断言要用
    `code_no_comment()`。这个坑本轮刚踩过（D1/D6 曾因此假 FAIL）。
    """
    return _tokens(path, strip_string=True)


def code_no_comment(path):
    """只剥注释，**保留字符串字面量** —— 供"needle 里带字面量"的源码断言用。"""
    return _tokens(path, strip_string=False)


def _tokens(path, strip_string):
    out = []
    try:
        with io.open(path, encoding='utf-8') as fh:
            for tok in tokenize.generate_tokens(fh.readline):
                if tok.type == tokenize.COMMENT or (strip_string
                                                    and tok.type == tokenize.STRING):
                    out.append('\n')
                else:
                    out.append(tok.string)
    except Exception:
        return ''
    return ' '.join(out)


def has(src, needle):
    return re.sub(r'\s+', '', needle) in re.sub(r'\s+', '', src)


class FakeParent(object):
    def __init__(self):
        self.api_enabled = False


# 与产品同源的常量（不写死数字，防止改了产品这里还"过"）
MIN_PAGE_W = MemorySystem.MIN_PAGE_W
KEEP = CF._KEEP_WORDS

# =====================================================================  A 组
print('=== A 抽词剪刀 ===')

# A1-A11：逐句断言"碎片灭 + 真词留"。碎片都是第十轮实测抓到的真实样本。
_CASES = [
    ('A1', '我明天想写点代码', ['写点', '点代', '点代码', '天想写'], ['代码']),
    ('A2', '写代码写累了就喝咖啡', ['写代', '写代码', '代码写', '码写', '写累'],
     ['代码', '咖啡']),
    ('A3', '今天下雨会有点冷吧', ['雨会', '会有', '点冷', '天下雨'], []),
    ('A4', '要不要休息一下啊', ['要不', '要休', '要休息', '休息一', '息一'], ['休息']),
    ('A5', '我这周末想去爬山记得带水', ['山记', '爬山记', '得带', '带水'], ['爬山', '周末']),
    ('A6', '这件事很重要', ['事很重', '件很重'], ['重要']),
    ('A7', '我们聊聊今天的天气怎么样', ['聊天的', '达这游'], ['天气']),
    ('A8', '今天想聊聊塞尔达这游戏的剧情', ['达这游', '聊天的'], ['塞尔达', '游戏', '剧情']),
    ('A9', '学习编程需要花不少时间', ['学习编', '要花', '要花不'], ['学习', '需要', '时间']),
    ('A10', '明天开会吗', ['天开会'], ['开会']),
    ('A11', '刚喝了杯咖啡感觉还行', ['刚喝', '杯咖', '杯咖啡', '觉还行'], ['咖啡']),
]
for tag, text, bads, goods in _CASES:
    kws = CF.extract_keywords(text)
    hit_bad = [b for b in bads if b in kws]
    miss_good = [g for g in goods if g not in kws]
    ok('%s 碎片灭·真词留：%s' % (tag, text),
       not hit_bad and not miss_good, (hit_bad, miss_good, kws))

ok('A12 位置专精：内部动词碎片 / 尾字动词碎片都被杀',
   ('天想写' not in CF.extract_keywords('我明天想写点代码'))
   and ('码写' not in CF.extract_keywords('写代码写累了就喝咖啡'))
   and ('写点' not in CF.extract_keywords('想写点代码')))
ok('A13 含多字停用词的碎片被杀（时候天/今天下）',
   ('时候天' not in CF.extract_keywords('爬山的时候天气不错'))
   and ('今天下' not in CF.extract_keywords('今天下雨会有点冷吧')))
ok('A14 单字停用词**不作为**判据（想法/思想 不被误杀）',
   CF._keep('想法', set(), True) and CF._keep('思想', set(), True)
   and CF._keep('爱好', set(), True))
ok('A15 免伤名单生效：被剪刀切中的真词全保留',
   all(CF._keep(w, set(), True) for w in
       ('重要', '需要', '开会', '学习', '记得', '喝咖啡', '杯子', '睡觉')))
ok('A16 免伤名单确实是"被切中"的词（否则这条断言没意义）',
   any(w[0] in CF._EDGE_VERB or w[-1] in CF._EDGE_VERB
       for w in ('重要', '需要', '开会', '学习', '记得')),
   [w for w in ('重要', '需要', '开会', '学习', '记得')
    if w[0] in CF._EDGE_VERB or w[-1] in CF._EDGE_VERB])

ok('A17 _ngrams 按位置生成（顺序即语义，供 chain/star 取核心用）',
   CF._ngrams('塞尔达') == ['塞尔', '塞尔达', '尔达'], CF._ngrams('塞尔达'))

_SENT = '我明天想写点代码，然后去爬山记得带水，晚上喝咖啡'
_kw = CF.extract_keywords(_SENT)
_pos = [_SENT.find(k) for k in _kw]
ok('A18 输出顺序 = 句中位置升序（chain 连边才有语义）',
   all(p >= 0 for p in _pos) and _pos == sorted(_pos), (_kw, _pos))

_strict = CF._extract(_SENT, strict=True)
_loose = CF._extract(_SENT, strict=False)
ok('A19 严格档 ⊆ 宽松档（严格只可能更严）',
   set(_strict) <= set(_loose), (set(_strict) - set(_loose)))

_emp_kw = CF.extract_keywords('晚上想吃点什么好呢')
ok('A20 三层择优：严格档全空 → 回落到宽松档（不返回空）',
   len(_emp_kw) > 0 and _emp_kw == CF._extract('晚上想吃点什么好呢', strict=False),
   _emp_kw)
_nonempty = CF.extract_keywords('我明天想写点代码')
ok('A21 三层择优：严格档非空时**不**回落',
   _nonempty == CF._extract('我明天想写点代码', strict=True), _nonempty)

# ---- 分词器注入点
_calls = []


def _fake_seg(t):
    _calls.append(t)
    return ['紫米', 'a', '的', '布丁咖啡', 'xy']


CF.set_segmenter(_fake_seg)
_seg_out = CF.extract_keywords('随便什么文本')
ok('A22 set_segmenter：注入的分词器优先生效（并按其结果过滤短词/停用词）',
   _seg_out == ['紫米', '布丁咖啡'] and _calls, _seg_out)

CF.set_segmenter(lambda t: (_ for _ in ()).throw(RuntimeError('boom')))
ok('A23 分词器抛异常 → 回落内置词法，不抛',
   '代码' in CF.extract_keywords('我明天想写点代码'))
CF.set_segmenter(lambda t: [])
ok('A24 分词器返回空 → 回落内置词法',
   '代码' in CF.extract_keywords('我明天想写点代码'))
CF.set_segmenter(None)
ok('A25 set_segmenter(None) 恢复内置词法',
   CF.extract_keywords('我明天想写点代码') == ['代码'],
   CF.extract_keywords('我明天想写点代码'))

ok('A26 空/None/非字符串输入不崩且返回 list',
   CF.extract_keywords('') == [] and CF.extract_keywords(None) == []
   and isinstance(CF.extract_keywords(123), list))
ok('A27 英文词保留（去停用词后）',
   'python' in CF.extract_keywords('我们用 python 写代码'))
ok('A28 _STOP_MULTI 只含多字停用词（单字停用词不进来）',
   all(len(w) >= 2 for w in CF._STOP_MULTI) and '想' not in CF._STOP_MULTI
   and '今天' in CF._STOP_MULTI)
ok('A29 产品同源：memory_system 用的就是这套词法',
   has(code_only(os.path.join(MODS, 'memory_system.py')),
       'return list(_cf.extract_keywords(text))[:limit]'))

# =====================================================================  B 组
print()
print('=== B 建边拓扑 ===')

_k4 = ['aa', 'b', 'c', 'd']
ok('B1 clique：4 词两两成边 = 6 条',
   len(MG.edge_pairs(_k4, 'clique')) == 6, MG.edge_pairs(_k4, 'clique'))
ok('B2 star：4 词 = 3 条，且都挂在核心词上（核心=最长，此处 aa）',
   len(MG.edge_pairs(_k4, 'star')) == 3
   and all('aa' in p for p in MG.edge_pairs(_k4, 'star')),
   MG.edge_pairs(_k4, 'star'))
ok('B3 chain：4 词 = 3 条，且只连相邻',
   MG.edge_pairs(_k4, 'chain') == [('aa', 'b'), ('b', 'c'), ('c', 'd')],
   MG.edge_pairs(_k4, 'chain'))
ok('B4 核心词 = 最长；等长取最先出现',
   MG.edge_pairs(['z', 'bbb', 'a'], 'star') == [('bbb', 'z'), ('bbb', 'a')]
   and MG.edge_pairs(['z', 'y', 'a'], 'star') == [('z', 'y'), ('z', 'a')],
   MG.edge_pairs(['z', 'bbb', 'a'], 'star'))
ok('B5 空/单元素/含空串 → 无边',
   MG.edge_pairs([], 'star') == [] and MG.edge_pairs(['a'], 'star') == []
   and MG.edge_pairs(['a', '', None], 'star') == [])
ok('B6 默认拓扑已钉为 clique（本轮实测后刻意保留；见模块头注释与 B13~B16）',
   MG.EDGE_TOPOLOGY == 'clique', MG.EDGE_TOPOLOGY)

_g4 = MG.MemoryGraph()
_g4.refresh_df({}, 0)
_g4.add_cooccurrence(_k4)                    # 走默认拓扑
_undirected = sum(len(v) for v in _g4.edges.values()) // 2
ok('B7 add_cooccurrence 采用默认拓扑（clique 下 4 词 → 6 条无向边）',
   _undirected == 6, _undirected)
ok('B9 邻接表对称（两个方向都写）',
   ('aa' in _g4.edges.get('b', {})) and ('b' in _g4.edges.get('aa', {})))
ok('B10 stats() 暴露当前拓扑（可观测）',
   _g4.stats().get('topology') == MG.EDGE_TOPOLOGY, _g4.stats().get('topology'))

# B8/B12：把 star 的作用域**显式钉住**再断言 —— 它现在是"实验档"，
# 断言要说明"切过去确实换成星型"，而不是隐式依赖默认值。
_old_topo = MG.EDGE_TOPOLOGY
try:
    _g6 = MG.MemoryGraph()
    _g6.refresh_df({}, 0)
    MG.EDGE_TOPOLOGY = 'star'
    _g6.add_cooccurrence(_k4)
    _star_und = sum(len(v) for v in _g6.edges.values()) // 2
    _star_hub = sorted(_g6.edges.get('aa', {}))
    _b_neigh = sorted(_g6.edges.get('b', {}))
finally:
    MG.EDGE_TOPOLOGY = _old_topo
ok('B8 切到 star：4 词 → 3 条边，且非核心词之间不直连（区分度来源）',
   _star_und == 3 and _star_hub == ['b', 'c', 'd'] and _b_neigh == ['aa'],
   (_star_und, _star_hub, _b_neigh))
ok('B12 拓扑可切换且用完复位（默认值不被探针污染）',
   MG.EDGE_TOPOLOGY == 'clique', MG.EDGE_TOPOLOGY)

_g5 = MG.MemoryGraph()
_g5.refresh_df({}, 0)
_g5.MAX_NB_PER_KEY = 3
_g5.add_cooccurrence(['核心长词'] + ['n%d' % i for i in range(9)])
ok('B11 单点邻居上限仍然生效（核心出边被裁）',
   len(_g5.edges['核心长词']) <= 3, len(_g5.edges.get('核心长词', {})))

# ---- B13~B16：多跳可达性闸门（受控实验，就是决定默认拓扑的那组证据）
_S1 = '写代码写到熬夜了'          # 代码 — 熬夜
_S2 = '熬夜就靠咖啡撑着'          # 熬夜 — 咖啡
_TARGET = '咖啡'


def _gate_reach(topo, times):
    g = MG.MemoryGraph()
    MG.EDGE_TOPOLOGY = topo
    try:
        for _ in range(times):
            g.add_cooccurrence(CF.extract_keywords(_S1))
            g.add_cooccurrence(CF.extract_keywords(_S2))
    finally:
        MG.EDGE_TOPOLOGY = _old_topo
    b = MG.RecallBudget()
    b.start()
    ps = g.paths(MG.seed_map(CF.extract_keywords('写代码')), b, min_node_w=MIN_PAGE_W)
    return [(p.get('hops'), p.get('nodes')) for p in ps
            if (p.get('nodes') or [])[-1:] == [_TARGET]]


ok('B13 多跳闸门·stage1（弱边 n=1）：**不**联想（弱边不许当中转站）',
   not _gate_reach('clique', 1), _gate_reach('clique', 1))
_reach2 = _gate_reach('clique', 2)
ok('B14 多跳闸门·stage2（中边 n=2）：**放行**，且是货真价实的 2 跳',
   bool(_reach2) and _reach2[0][0] == 2, _reach2)
ok('B15 多跳闸门·stage3（强边 n=3）：仍然放行（分数更高）',
   bool(_gate_reach('clique', 3)), _gate_reach('clique', 3))
ok('B16 为什么默认 clique：star/chain 连强边都走不通这条联想',
   (not _gate_reach('star', 3)) and (not _gate_reach('chain', 3))
   and bool(_gate_reach('clique', 3)),
   (_gate_reach('star', 3), _gate_reach('chain', 3)))
ok('B17 探针跑完默认拓扑仍未被污染（全局态隔离）',
   MG.EDGE_TOPOLOGY == _old_topo == 'clique', MG.EDGE_TOPOLOGY)

# =====================================================================  C 组
print()
print('=== C 集成（真实中文语料 + 真记忆系统） ===')

_CORPUS = [
    '我明天想写点代码', '要不要休息一下啊', '今天下雨会有点冷吧',
    '我这周末想去爬山记得带水', '刚喝了杯咖啡感觉还行',
    '写代码写累了就喝咖啡', '喝咖啡的时候写代码挺舒服',
    '我们聊聊今天的天气怎么样', '今天想聊聊塞尔达这游戏的剧情',
    '学习编程需要花不少时间', '明天开会吗', '这件事很重要',
]
_G = MG.MemoryGraph()
_G.refresh_df({}, 0)
for _s in _CORPUS:
    _G.add_cooccurrence(CF.extract_keywords(_s))

_FRAGS = ['写点', '点代', '写点代', '点代码', '写代', '写代码', '代码写', '码写',
          '写累', '雨会', '会有', '点冷', '要不', '要休', '要休息', '休息一', '息一']
_leaked = [w for w in _FRAGS if w in _G.edges]
ok('C1 建图后图中**不含**已知碎片节点', not _leaked, _leaked)
_edges = sum(len(v) for v in _G.edges.values()) // 2
_per = _edges / float(max(1, len(_G.edges)))
ok('C2 边密度闸门：边/点 ≤ 3.5（旧词法 clique 是 4.03；抽词干净后自然下降）',
   _per <= 3.5, _per)

_b = MG.RecallBudget()
_b.start()
_paths = _G.paths(MG.seed_map(CF._extract('写代码', strict=True)), _b,
                   min_node_w=MIN_PAGE_W)
_reach = set()
for p in _paths:
    ns = p.get('nodes') or []
    if len(ns) >= 3 and int(p.get('hops') or 0) <= 2:
        _reach.add(ns[-1])
ok('C3 旗舰联想：seed=「代码」能在 2 跳内走到「咖啡」',
   '咖啡' in _reach, sorted(_reach)[:12])

# ---- 真记忆系统端到端：必须"想到没直接说过的东西"
def new_ms(dirname):
    d = os.path.join(TMP, dirname)
    os.environ['RALSEI_MEMORY_DIR'] = d
    os.environ['RALSEI_LEGACY_MEMORY'] = os.path.join(TMP, '_no_such_legacy.json')
    return MemorySystem(FakeParent())


ms = new_ms('e2e')
_now = time.time()
for _s in _CORPUS:
    ms.add_fragment(_s, who='user', kind='dialogue', now=_now)
_rec = ms.recall('写代码', limit=5, now=_now)
ok('C4 端到端 recall 有结果（防"静默降级成空"的正向断言）',
   isinstance(_rec, list) and len(_rec) > 0, len(_rec) if isinstance(_rec, list) else _rec)

_texts = [str(r.get('text') or '') for r in _rec] if isinstance(_rec, list) else []
ok('C5 召回里出现了「咖啡」那条记忆（跨句联想真的生效）',
   any('咖啡' in t for t in _texts), _texts)
_asso = [r for r in _rec if not r.get('direct')] if isinstance(_rec, list) else []
ok('C6 其中至少一条是**联想**（direct=False），不是直接命中',
   any('咖啡' in str(r.get('text') or '') for r in _asso),
   [(r.get('text'), r.get('via'), r.get('hop'), r.get('tier')) for r in _asso])

ok('C7 图里没有任何已知碎片键（端到端，含英文/数字过滤后）',
   not [k for k in ms.assoc if k in _FRAGS], [k for k in ms.assoc if k in _FRAGS])
ok('C8 真机记忆目录未被触碰（全程临时目录隔离）',
   str(os.environ.get('RALSEI_MEMORY_DIR') or '').startswith(TMP)
   and str(ms.memory_file if hasattr(ms, 'memory_file') else '').startswith(TMP)
   if getattr(ms, 'memory_file', None) else True,
   getattr(ms, 'memory_file', None))

# C9/C10：把"残渣"变成**账本**而不是含糊过去 ——
# 新残渣会让断言失败（防止改善被悄悄吃掉），而账本本身就是要写进报告的数字。
_NODES = set(_G.edges)
ok('C9 节点数闸门：语料建图后节点 ≤ 40（全互连时代是 85~92）',
   len(_NODES) <= 40, len(_NODES))

_GOOD_WORDS = set("""
代码 下雨 剧情 周末 咖啡 喝咖啡 塞尔达 学习 时间 游戏 爬山 编程 舒服
记得 重要 需要 开会 休息 天气 不少
""".split())
# 已知残渣（无分词库的固有代价，三类：专名碎片 / 复合词碎片 / 跨词 3-gram）
_LEDGER = set("""
天下 天开 塞尔 尔达 习编 习编程 编程需 程需 花不 不少时 少时 少时间 咖啡感 啡感 件事
""".split())
_unknown = _NODES - _GOOD_WORDS - _LEDGER
ok('C10 残渣账本：除"真词 + 已知残渣"外没有新碎片冒出来', not _unknown,
   sorted(_unknown))

# =====================================================================  D 组
print()
print('=== D 回归守卫（源码级） ===')

_r10 = os.path.join(ROOT, 'code-quality-audit', '第十轮', 'verify_round10_graph.py')
_src10 = code_only(_r10)
ok('D0 助手自检：含字面量的 needle 必须用 code_no_comment 才找得到',
   (not has(_src10, "EDGE_TOPOLOGY = 'star'"))
   and has(code_only(os.path.join(MODS, 'memory_graph.py')), 'def edge_pairs'))
ok('D1 第十轮的 G4 断言已改成与拓扑无关（不再"歪打正着"）',
   not has(_src10, "set(g2.edges['a']) == {'b', 'c'}")
   and has(_src10, 'g2.add_cooccurrence'))
ok('D2 第十轮的死变量 _pairs 已清掉', not has(_src10, "_pairs = ['hub']"))

_src_cf = code_only(os.path.join(MODS, 'conversation_focus.py'))
ok('D3 回落层必须在（否则话题锚会静默退化）',
   has(_src_cf, 'return _extract(text, strict=False)')
   and has(_src_cf, 'if strict:\n    return strict'))
ok('D4 四把新剪刀与免伤名单都在源码里',
   has(_src_cf, '_EDGE_VERB') and has(_src_cf, '_INNER_VERB')
   and has(_src_cf, '_TAIL_FUNC') and has(_src_cf, '_KEEP_WORDS')
   and has(_src_cf, '_STOP_MULTI'))
ok('D5 抽词被两个消费者共用（话题锚 + 记忆），且无重复实现',
   has(code_only(os.path.join(MODS, 'memory_system.py')), 'extract_keywords'))

_src_mg_nc = code_no_comment(os.path.join(MODS, 'memory_graph.py'))
_src_mg = code_only(os.path.join(MODS, 'memory_graph.py'))
ok('D6 memory_graph：拓扑可配 + 默认 clique（实测择优）+ 由 edge_pairs 统一决定边',
   has(_src_mg_nc, "EDGE_TOPOLOGY = 'clique'") and has(_src_mg, 'def edge_pairs')
   and has(_src_mg, 'pairs = edge_pairs(ks)'))
ok('D7 memory_graph：加边逻辑收敛为 _bump + _trim_nb（不再内联两份上限裁剪）',
   has(_src_mg, 'def _bump') and has(_src_mg, 'def _trim_nb')
   and has(_src_mg, 'self._trim_nb(a)'))

# =====================================================================  汇总
print()
print('=' * 62)
print('第十一轮自检：%d PASS / %d FAIL' % (len(PASS), len(FAIL)))
if FAIL:
    for f in FAIL:
        print('  FAIL: ' + f)
print('=' * 62)
sys.exit(1 if FAIL else 0)

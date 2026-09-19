"""世界观按需召回（第二十轮）—— 把「我知道的世界」从"每次全读"改成"想起才读"。
第二十一轮升级：**块与块连成网图**，命中一块后可以顺着边"多想起一块"。

## 为什么要有这个模块

原先 `assets/ralsei_persona.md` 的「我知道的世界」一节（4768 B / ~600 tokens）
**每一轮对话都整段当作 system 前缀发出去**。用户口径：

> 「没必要每次让他说话的时候都读取完整的世界观啊，可以按照语言的关联性去
>   单个读取或是一定范围内读取，就和咱那个记忆系统一样，或是说这个世界观
>   本就是他自己自带的初始记忆」

于是把它拆成 `assets/ralsei_worldview.md`（语义块），只在**话题真的碰到**
时才把命中的块拼到 system 尾部。效果有两条，第二条比第一条重要得多：

1. **省 token**：常驻前缀从 ~4380 → ~2800 tokens；
2. **保 KV 前缀缓存**：这是真正的收益来源。Ollama 只复用"从头逐字相同"的那一段，
   而世界观是**固定文本**、位置又在 system 中部 —— 一旦它因为任何原因发生位移，
   后面**所有**内容（口癖/怎么说/语气示范/上下文）的缓存全部作废。
   把它抽出去，恒定骨架就变成一段**更短但更稳**的前缀，命中率反而更高。

## 第二十一轮：为什么要把块连成网（用户口径）

> 「我觉得你可以把他的世界观拆分成网图，这应该会更高效」

只看关键词打分时，"聊到黑暗喷泉该不该顺带想起那个传说"是没有依据的 ——
触发词表里碰巧都有"喷泉"就会带，两个词写得不一样就不带，纯属运气。
写成 `@@> 本块 -> 邻块` 的**有向边**之后，这件事由结构决定：
**命中是"直接想起来"，沿边扩是"顺着想起紧挨着的那一块"**，更接近人的回忆方式。

## 与 memory_system 的关系（用户明确要求"和那个记忆系统一样"）

刻意做成**同一套口径**：都是"输入一句话 → 联想出若干片段 → 拼成给模型看的中文块"。
区别只在数据源 —— `memory_graph` 检索的是**相处出来的**片段，
这里检索的是**他本来就有的**初始记忆。所以它不需要存盘、不需要衰减、不需要遗忘：
初始记忆不参与"忘记"。

## 硬约束

- **不 import 任何项目内模块**（初始化环：本模块被 main.py 在启动早期用到；
  项目内已有 4 次踩环记录）。只用标准库。
- **任何异常一律静默返回空串** —— 召回失败不该让对话链路掉线，
  最坏退化成"这轮他想不起那件事"，而不是"这轮崩了"。
- 命中数硬上限 `MAX_BLOCKS`：一次倒太多设定 = 设定倾倒，正是 A15 要防的。
  **扩图不改变这个上限** —— 它只是把上限内的名额分一个给"顺着想起"的那块。
"""

import io
import os
import re

# 一次最多拼几块。「一次别倒太多」是 persona「我知道的世界」节里写死的口径，
# 这里必须同源 —— 否则召回会把它顶掉。
MAX_BLOCKS = 2
# 单块最长字符数（防某块被改得极长后一次灌爆上下文）
MAX_BLOCK_CHARS = 700

# 块头：`@@ 键|标签|触发词,触发词`
_BLOCK_HEAD = re.compile(r'^@@\s*([^|\n]+)\|([^|\n]+)\|([^\n]*)$')
# 边：`@@> 本块键 -> 邻块键, 邻块键`
_EDGE = re.compile(r'^@@>\s*([^\s>]+)\s*->\s*(.+)$')

# 主题度低于这个值的块不进（避免"世界"这种超高频词把整节都拉进来）
_MIN_SCORE = 1


class WorldviewBlock(object):
    """一个世界观块。`body` 是**逐字发给模型的原文**（不加工，不改写）。"""

    __slots__ = ('key', 'label', 'triggers', 'body', 'edges', 'order')

    def __init__(self, key, label, triggers, body, edges=None, order=0):
        self.key = key
        self.label = label
        self.triggers = triggers
        self.body = body
        # 出边（有向）：本块想起后，可以顺带想起哪些块
        self.edges = list(edges or [])
        # 文件里的出现序号。**扩图排序靠它**，不许依赖 dict 顺序（不稳，会抖动）。
        self.order = order

    def score(self, text_low):
        """命中分：长触发词权重更高（"黑暗喷泉"比"世界"更能说明在聊什么）。"""
        total = 0
        for t in self.triggers:
            if t and t in text_low:
                # 单字/双字给 1 分，之后每多一字 +1 —— 让具体词压倒泛词
                total += max(1, len(t) - 1)
        return total


def _parse(text):
    """把索引文件解析成块列表 + 邻接表。

    格式错了就跳过那一块（不让一行坏数据毒死整节）。返回 `(blocks, adj, dangling)`：
      - `blocks`: 文件顺序的块列表
      - `adj`   : {key: [邻块 key, ...]}（只保留**指向真实存在块**的边）
      - `dangling`: [(本块 key, 指向的野键), ...]（悬空边，供体检用，不影响召回）
    """
    out = []
    key = label = None
    triggers = []
    edges = []
    buf = []
    adj = {}       # 解析期先按"声明的顺序"记原始边，键可能不存在
    dangling = []

    def _flush():
        if key is None:
            return
        body = '\n'.join(buf).strip()
        if not body:
            return
        if len(body) > MAX_BLOCK_CHARS:
            body = body[:MAX_BLOCK_CHARS]
        out.append(WorldviewBlock(key, label, triggers, body, edges, len(out)))

    for line in text.split('\n'):
        s = line.strip()
        em = _EDGE.match(s)
        if em:
            # 边行：**不算块体**，只记进邻接表。必须挂在当前块（key）名下。
            if key is not None:
                tgt = [t.strip() for t in em.group(2).split(',') if t.strip()]
                adj.setdefault(key, []).extend(tgt)
            continue
        m = _BLOCK_HEAD.match(s)
        if m:
            _flush()
            key = m.group(1).strip()
            label = m.group(2).strip()
            triggers = [t.strip().lower() for t in m.group(3).split(',') if t.strip()]
            edges = []
            buf = []
        elif key is not None:
            buf.append(line)
    _flush()

    # 建图：只留指向真实块的边；悬空的挑出来（去重、保序）
    keys = set(b.key for b in out)
    clean = {}
    for b in out:
        seen = []
        for t in adj.get(b.key, []):
            if t not in keys:
                dangling.append((b.key, t))
                continue
            if t == b.key:
                continue          # 自环无意义
            if t not in seen:
                seen.append(t)    # 去重但保声明顺序
        clean[b.key] = seen
        b.edges = list(seen)
    return out, clean, dangling


_CACHE = {}


def _load(path=None):
    """读索引文件（带按路径 + mtime 缓存）。失败返回 `([], {}, [])`（静默降级）。"""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'assets', 'ralsei_worldview.md')
    path = os.path.abspath(path)
    try:
        mt = os.path.getmtime(path)
    except Exception:
        return [], {}, []
    hit = _CACHE.get(path)
    if hit and hit[0] == mt:
        return hit[1]
    try:
        with io.open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        blocks, adj, dangling = _parse(text)
    except Exception:
        return [], {}, []
    _CACHE[path] = (mt, (blocks, adj, dangling))
    return blocks, adj, dangling


def load_blocks(path=None):
    """兼容旧调用：只要块列表。失败返回 []（静默降级）。"""
    return _load(path)[0]


def load_graph(path=None):
    """要整张图：`(blocks, adj, dangling)`。给体检脚本 / 回归锁用。"""
    return _load(path)


def recall(cue, limit=MAX_BLOCKS, path=None):
    """按语言关联性召回若干块（按得分降序）。无命中返回 []。

    **不返回空串兜底**：没碰到就是没碰到，硬塞一块反而会让他在无关话题上
    突然讲设定（A15 明确禁止"把话题硬拐"）。

    `limit` 是**上界而非请求数**：`MAX_BLOCKS` 是不可绕过的硬顶 ——
    调用方传再大的数也只给两块。这不是防御性编程，是**契约**：
    persona 里"一次别倒太多"是写死的口径，召回是这个口径的**唯一执行点**，
    留个能被绕过的口子等于那条口径失效（本项目"函数写对了 ≠ 产品用上了"的同型坑）。

    **扩图（第二十一轮）**：先取关键词直接命中的块（种子），
    种子用不满 `want` 个名额时，才沿种子的出边补邻块 —— 顺序是
    "先说直接想起来的，再顺带想起紧挨着的那块"。

    **邻块为什么不再要求自己也被 cue 命中**（这里想过一轮，别改回去）：
    最初给邻块也加了 `_MIN_SCORE` 同门槛，结果扩图几乎不发生 ——
    因为"能命中邻块的 cue"往往**本来就会直接命中邻块**，那它早就是种子了；
    真正需要扩的场景（cue 只说"喷泉"、没想到"传说"）恰好是邻块得分为 0 的时候。
    加了同门槛 = 扩图永远不开火 = 白写。
    正确判据是**邻块与种子相关（有边），而不是邻块与 cue 相关**：
    种子已经证明这轮在聊那边的事了，沿边继续想起是**顺着这条话题线**，
    前提（种子命中）本身就是闸门 —— 闲聊产生不了种子，自然也就扩不了图。
    **但不做二阶扩图**：只从种子出发扩一层。否则一条边链能把整个世界观拖进来。
    """
    if not cue:
        return []
    try:
        text_low = str(cue).lower()
    except Exception:
        return []
    try:
        want = max(0, min(int(limit), MAX_BLOCKS))
    except Exception:
        want = MAX_BLOCKS
    if want == 0:
        return []

    blocks, adj, _dangling = _load(path)
    if not blocks:
        return []
    by_key = {}
    for b in blocks:
        by_key[b.key] = b

    # —— 第一层：关键词命中（种子）——
    scored = []
    for b in blocks:
        try:
            s = b.score(text_low)
        except Exception:
            continue
        if s >= _MIN_SCORE:
            scored.append((s, b))
    # 得分降序；同分按文件顺序（稳定，不抖动）
    scored.sort(key=lambda kv: -kv[0])
    seeds = [b for _s, b in scored[:want]]
    if len(seeds) >= want:
        return seeds

    # —— 第二层：沿边扩图，只补还在空位的名额（**只扩一层，不链式**）——
    # 候选 = 已选中种子的出边；按 (种子序, 边在种子里的声明序) 遍历 → 确定性。
    picked = list(seeds)
    chosen_keys = set(b.key for b in picked)
    for src in seeds:
        for nk in adj.get(src.key, []):
            if len(picked) >= want:
                return picked
            if nk in chosen_keys:
                continue
            nb = by_key.get(nk)
            if nb is None:
                continue
            picked.append(nb)
            chosen_keys.add(nk)
    return picked


def recall_text(cue, limit=MAX_BLOCKS, path=None):
    """给模型看的"想起了什么"中文块。无命中返回空串。

    措辞刻意和 `memory_system.recall_text` 的「【零星的回忆…】」区分开：
    那是"我们相处出来的事"，这是"他自己本来就记得的事" —— 对模型来说
    这是两种不同的信息来源，混成一个标题会让它把两者当成同一类。
    """
    try:
        blocks = recall(cue, limit=limit, path=path)
    except Exception:
        return ''
    if not blocks:
        return ''
    lines = ['【你想起了那边的事（可以自然地说，别一口气倒完）】']
    for b in blocks:
        lines.append(b.body)
    return '\n\n'.join(lines)

"""世界观按需召回（第二十轮）—— 把「我知道的世界」从"每次全读"改成"想起才读"。

## 为什么要有这个模块

原先 `assets/ralsei_persona.md` 的「我知道的世界」一节（4768 B / ~600 tokens）
**每一轮对话都整段当作 system 前缀发出去**。用户口径：

> 「没必要每次让他说话的时候都读取完整的世界观啊，可以按照语言的关联性去
>   单个读取或是一定范围内读取，就和咱那个记忆系统一样，或是说这个世界观
>   本就是他自己自带的初始记忆」

于是把它拆成 `assets/ralsei_worldview.md`（11 个语义块），只在**话题真的碰到**
时才把命中的块拼到 system 尾部。效果有两条，第二条比第一条重要得多：

1. **省 token**：常驻前缀从 ~4380 → ~2800 tokens；
2. **保 KV 前缀缓存**：这是真正的收益来源。Ollama 只复用"从头逐字相同"的那一段，
   而世界观是**固定文本**、位置又在 system 中部 —— 一旦它因为任何原因发生位移，
   后面**所有**内容（口癖/怎么说/语气示范/上下文）的缓存全部作废。
   把它抽出去，恒定骨架就变成一段**更短但更稳**的前缀，命中率反而更高。

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

# 主题度低于这个值的块不进（避免"世界"这种超高频词把整节都拉进来）
_MIN_SCORE = 1


class WorldviewBlock(object):
    """一个世界观块。`body` 是**逐字发给模型的原文**（不加工，不改写）。"""

    __slots__ = ('key', 'label', 'triggers', 'body')

    def __init__(self, key, label, triggers, body):
        self.key = key
        self.label = label
        self.triggers = triggers
        self.body = body

    def score(self, text_low):
        """命中分：长触发词权重更高（"黑暗喷泉"比"世界"更能说明在聊什么）。"""
        total = 0
        for t in self.triggers:
            if t and t in text_low:
                # 单字/双字给 1 分，之后每多一字 +1 —— 让具体词压倒泛词
                total += max(1, len(t) - 1)
        return total


def _parse(text):
    """把索引文件解析成块列表。格式错了就跳过那一块（不让一行坏数据毒死整节）。"""
    out = []
    key = label = None
    triggers = []
    buf = []

    def _flush():
        if key is None:
            return
        body = '\n'.join(buf).strip()
        if not body:
            return
        if len(body) > MAX_BLOCK_CHARS:
            body = body[:MAX_BLOCK_CHARS]
        out.append(WorldviewBlock(key, label, triggers, body))

    for line in text.split('\n'):
        m = _BLOCK_HEAD.match(line.strip())
        if m:
            _flush()
            key = m.group(1).strip()
            label = m.group(2).strip()
            triggers = [t.strip().lower() for t in m.group(3).split(',') if t.strip()]
            buf = []
        elif key is not None:
            buf.append(line)
    _flush()
    return out


_CACHE = {}


def load_blocks(path=None):
    """读索引文件（带按路径缓存）。失败返回 []（静默降级）。"""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'assets', 'ralsei_worldview.md')
    path = os.path.abspath(path)
    try:
        mt = os.path.getmtime(path)
    except Exception:
        return []
    hit = _CACHE.get(path)
    if hit and hit[0] == mt:
        return hit[1]
    try:
        with io.open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        blocks = _parse(text)
    except Exception:
        return []
    _CACHE[path] = (mt, blocks)
    return blocks


def recall(cue, limit=MAX_BLOCKS, path=None):
    """按语言关联性召回若干块（按得分降序）。无命中返回 []。

    **不返回空串兜底**：没碰到就是没碰到，硬塞一块反而会让他在无关话题上
    突然讲设定（A15 明确禁止"把话题硬拐"）。

    `limit` 是**上界而非请求数**：`MAX_BLOCKS` 是不可绕过的硬顶 ——
    调用方传再大的数也只给两块。这不是防御性编程，是**契约**：
    persona 里"一次别倒太多"是写死的口径，召回是这个口径的**唯一执行点**，
    留个能被绕过的口子等于那条口径失效（本项目"函数写对了 ≠ 产品用上了"的同型坑）。
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
    scored = []
    for b in load_blocks(path):
        try:
            s = b.score(text_low)
        except Exception:
            continue
        if s >= _MIN_SCORE:
            scored.append((s, b))
    # 得分降序；同分按文件顺序（稳定，不抖动）
    scored.sort(key=lambda kv: -kv[0])
    return [b for _s, b in scored[:want]]


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

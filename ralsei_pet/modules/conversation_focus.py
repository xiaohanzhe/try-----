# -*- coding: utf-8 -*-
"""对话注意力 / 话题锚（ConversationFocus）
=========================================

用户要求（第九轮）："把那个 AI 整的有些注意力哈，别到时候聊着一个话题呢突然就切换了"。

问题出在哪儿：`chat_with_ai` 只把「最近 6 轮原文」丢给模型，**没有"我们现在在聊什么"这个
念头**。模型每轮都在重新判断"该怎么回"，只要一句里出现别的东西，它就可能顺着跑偏 ——
表现就是"聊着一个话题突然切换"。人不会这样：人脑子里有一个**注意力焦点**，
新听到的话会先和焦点对一下，对得上就继续，对不上才换题。

本模块就是这个焦点，刻意做成一个**轻量、可解释、不需要模型**的跟踪器：

  · 关键词提取：中文取 2/3 字滑窗（过滤停用词与语气词）+ 英文/数字词。
    （第十一轮起再加"首字剪刀"专杀跨词碎片，并支持注入外部分词器；见 `extract_keywords`。）
  · 归属判定：新话与当前话题的关键词做**覆盖度**比较；指代词（"这个/它/继续/刚才"）
    与"接着说"类标记直接判为延续。
  · 话题生命周期：开题 → 延续（累计轮数/时长）→ 冷场超时归档。
  · 悬置事项（pending）：Ralsei 问了问题或做了承诺、对方还没回应 —— 继承到下一轮提示里，
    这样它不会把"自己刚问过什么"忘掉，也不会追着同一个问题反复问。

对外只有几个动作：`note_user()` / `note_assistant()` / `brief()` / `snapshot()`。
`brief()` 返回一段中文，被拼进系统提示词（`main.chat_with_ai`），
是本模块唯一"影响模型"的出口 —— 也因此可以被单独断言。
"""
import re
import time

# ---------------------------------------------------------------- 词法
# 停用词/语气词/单字虚词：这些出现频繁但完全不承载话题，必须剔除，
# 否则"我" "的" "了" 会让任意两句话都"看起来很相关"。
_STOPWORDS = frozenset("""
我 你 他 她 它 我们 你们 他们 咱们 自己 大家
的 了 着 过 是 在 有 和 与 或 也 都 就 还 又 而 但 却 因 为 所以 如果 要是 那么
这 那 这个 那个 这些 那些 这样 那样 这么 那么样
什么 怎么 为什么 哪 哪个 哪里 谁 多少 几
吗 呢 吧 啊 呀 哦 嗯 哎 唉 哈 呵 嘿 咦 噢 喔 啦 咯 嘛 咯 哟 哇
一个 一下 一点 一些 一直 一定 一样 一起 一般
可以 能 会 要 想 说 讲 聊 问 答 知道 觉得 感觉 好像 似乎 应该 可能 也许
现在 刚才 刚刚 已经 曾经 从来 总是 经常 有时 偶尔 马上 立刻 终于 然后 接着 继续
很 挺 太 更 最 非常 特别 真的 确实 其实 反正 大概 差不多 有点 有些
不要 没有 不是 不会 不能 别 没 不 好 好吧 好的
请 帮我 帮忙 给我 让我 告诉我 咱们 一起 怎么样 什么样
今天 明天 昨天 后天 每天 今晚 明晚 早上 中午 晚上 时候 事情 东西 之类 什么的
"""
                        .split())

# 滑窗窗口的"骨架字"过滤 -----------------------------------------------------
# 中文不分词直接取 2/3 字滑窗，必然产生 "达这游""聊天的" 这类跨词碎片。
# 判据：**首/尾**是功能字 → 只可能是句子骨架，不是话题词（`_EDGE_FUNC`）；
#       **内部**出现强功能字 → 一定跨了词（`_INNER_FUNC`）。两把剪刀一起用，
#       剩下的才配当关键词（也因此话题标签才像人话）。
_EDGE_FUNC = frozenset(
    "的了着过和与或也都是就还又而但却为所以这那我们你他她它您"
    "吗呢吧啊呀哦嗯啦嘛哟哇很挺太更最怎谁哪几多么个在把被让给"
    "聊说想问讲看听想做"
)
# 内部功能字。**注意`_INNER_FUNC`里的字全都也在`_EDGE_FUNC`里** ——
# 所以只对长度 ≥3 的词做"内部检查"与原来对 2 字词也做的效果等价（见 `_keep`）。
_INNER_FUNC = frozenset("的了着过和与或这那我们吗呢吧啊呀哦嗯啦嘛么个")

# 第十一轮：把剪刀按"位置专精"补全 --------------------------------------------
#
# 病根（真机实测）：滑窗法最大的漏网之鱼是"**被单字动词切开的碎片**"。
#   "想写点代码"        → 旧词法 {写点, 点代, 点代码, 代码}，只有 `代码` 是真词；
#   "写代码写累了就喝咖啡" → 旧词法 {写代, 写代码, 代码, 代码写, 码写, …}；
#   "今天下雨会有点冷吧"  → 旧词法 9 个词里 `雨会/会有/点冷/天下雨…` 全是碎片。
# 这些碎片混进记忆图后会被反复共现、抬成中边 → 当上"中转站" → 联想一路漂移
# （报告里那条 `写代码 → 写代 → 爬山` 就是这么来的）。
#
# 三把**位置专精**的剪刀（与 `_EDGE_FUNC` 那种"首尾都查、且是第九轮既有"的分开）：
#
# ① `_EDGE_VERB`：查**首字或尾字**。单字动词/助动词出现在窗口边缘，说明窗口是从它
#    中间切开的（首：`点代/想写点`；尾：`码写/雨会/挺有`）。
#    刻意**不收**：来(未来/回来/出来)、去(去年)、下(下雨/下午)、上(上班)、
#    开(开会/开心)、到、得、着、过、好、太、很 —— 它们当边缘字时更多是在构成正常词。
_EDGE_VERB = frozenset("想要会写点有听做用学带记喝去杯觉")

# ② `_INNER_VERB`：查**内部**（只对长度 ≥3 的词，看第 2 个字起）。
#    这样 `天想写`(内部"想")、`息一下`(内部"一")、`事很重`(内部"很")、
#    `气不错`(内部"不") 会被杀掉；而同样含这些字、但落在首/尾的正常词
#    （开会/机会/社会/重要/不错）不受影响 —— 注意 `不错` 是 2 字词，
#    内部检查不碰它，这正是"位置专精"的价值。
_INNER_VERB = frozenset(
    "想要会能该写说讲聊问看听干做给帮带记用来买喝学玩点一"
    "不很挺太更最都也又就而且还但多些好下"
)

# ③ `_TAIL_FUNC`：查**尾字**的数量/量词 —— 碎片"休息一/杯咖啡"这类是"词+量词"截面。
_TAIL_FUNC = frozenset("一二三四五六七八九十百千两半杯")

# 「免伤名单」：会被上面某把剪刀切到、但本身是正常话题词的词。
# 有了它才敢把剪刀开得这么宽 —— 宁可多列几十个词，
# 也不要把"重要/会议/学习/记得"这种高频词误伤（那会让话题锚直接抽不到词，
# 是用户可见的功能退化）。命中即**跳过所有结构剪刀**，只受停用词/去重约束。
#
# 另有一层保险：`extract_keywords` 在"严格词法一个词都没抽到"时会回落到
# 宽松词法（不做这些新剪刀），所以像"重要吗"这种"唯一话题词恰好被切中"的句子
# 不会变成空 —— 见 `extract_keywords` 的三层择优说明。
_KEEP_WORDS = frozenset("""
重要 需要 主要 要求 要紧 要么 必要 想要 理想 梦想 思想 幻想 感想 想象 想法 联想
机会 社会 学会 开会 会议 晚会 一会儿 描写 填写 编写 喝咖啡 喝茶
优点 缺点 重点 地点 热点 景点 起点 终点 特点 点心 所有 拥有 具有
有点 有意思 有趣 有效 听说 好听 动听 做法 做梦 当做 做饭
用户 用途 有用 使用 费用 作用 用法 学习 学校 学生 同学 数学 大学
带来 带走 皮带 记得 记录 记忆 日记 笔记 忘记 记住 玩具 好玩 喝水 买单 去年
杯子 睡觉 干杯
""".split())

# ④ 「含停用词」剪刀：候选词里若**整段包含**一个多字停用词，几乎必然是从它上面
#    切出来的碎片（`时候天` 含 `时候`、`今天下` 含 `今天`）。
#    只认**长度 ≥2** 的停用词：单字停用词（想/要/会/好）太常见于正常词内部
#    （想法/重要/会议/爱好），拿它当判据会大面积误杀。
_STOP_MULTI = frozenset(w for w in _STOPWORDS if len(w) >= 2)

# 可选外部分词器注入点：装了 jieba 之类分词库的调用方可以
# `set_segmenter(lambda t: jieba.cut(t))`，不必改本模块的代码。
# 约定：返回可迭代的词序列；抛异常或返回空 → 自动回落内置词法。
_SEGMENTER = None


def set_segmenter(fn):
    """注入外部分词器（`fn(text) -> Iterable[str]`）；传 `None` 恢复内置词法。"""
    global _SEGMENTER
    _SEGMENTER = fn


# 纯虚词组合（如"的了"）—— 一定不是话题词
_ALL_FUNC = '的了着过和与或也都是就还又而但却为所以如果那么这那'

_CJK = r'\u4e00-\u9fff'
_TOKEN_RE = re.compile(r'[A-Za-z][A-Za-z0-9_\-]{1,}|[0-9]{2,}|[%s]{2,}' % _CJK)
_EN_STOP = frozenset({'the', 'and', 'you', 'for', 'are', 'was', 'this', 'that',
                      'with', 'have', 'but', 'not', 'can', 'what', 'how'})

# 指代词 / 接力标记：出现即视为"接着说，没换题"
_CONTINUE_MARKERS = ('这个', '那个', '它', '继续', '接着', '然后', '还有', '刚才',
                     '刚刚说', '上面说', '你刚', '你说的', '刚才说', '再说', '还有呢',
                     '然后呢', '所以呢', '那么', '嗯嗯', '对呀', '是啊')

# 疑问标记：用来判断"Ralsei 抛出的问题主人还没回答"
_QUESTION_MARKERS = ('?', '？', '吗', '呢', '怎么', '为什么', '什么', '哪', '要不要',
                     '好不好', '行不行', '可以吗', '记得', '知道')


def _ngrams(run):
    """中文串取 2 字与 3 字滑窗，**按出现位置排序**。

    顺序很重要，不是审美问题：`extract_keywords` 的输出顺序会被
    `memory_graph.edge_pairs('chain')` 当作"句子里的先后"来连边。
    旧实现"先把所有 2 字窗倒完、再倒所有 3 字窗"，导致连出来的边
    完全没有语义含义（实测：相邻边把 `点代` 连到 `代码`、`代码` 连到 `天想写`）。
    """
    out = []
    n = len(run)
    for i in range(n):
        for size in (2, 3):
            if i + size <= n:
                out.append(run[i:i + size])
    return out


def _keep(c, seen, strict=True):
    """一个滑窗候选是不是够格当关键词（`strict`=是否启用第十一轮的新剪刀）。

    结构剪刀共五把，各有明确的"位置专精"，避免互相误伤：

      · 首/尾（`_EDGE_FUNC`）—— 句子骨架，第九轮既有；
      · 首/尾（`_EDGE_VERB`）—— 被单字动词切开的碎片（`点代` / `码写` / `雨会`）；
      · 尾字（`_TAIL_FUNC`）—— 数量词截面（`休息一` / `杯咖啡`）；
      · 内部（`_INNER_FUNC` + `_INNER_VERB`，**只看长度 ≥3 词的第 2~n-1 个字**）；
      · 含停用词（`_STOP_MULTI`）—— 整段包住一个多字停用词的碎片（`时候天`）。

    `_INNER_FUNC` 里的字**全都也在 `_EDGE_FUNC` 里**，所以把"内部检查"限制到长度 ≥3
    的词，对 2 字词的效果与第九轮完全等价（2 字词的非首即尾，已被首尾剪刀覆盖）。
    `strict=False` 时只保留第九轮的既有剪刀（回落用），见 `extract_keywords`。
    """
    if c in _STOPWORDS or c in seen:
        return False
    # 免伤名单里的真词：跳过一切结构剪刀
    if c in _KEEP_WORDS:
        return True
    # 整段包含多字停用词 → 是从停用词上切下来的碎片
    if any(w in c for w in _STOP_MULTI):
        return False
    # 纯虚词组合（如"的了"）直接丢
    if all(ch in _ALL_FUNC for ch in c):
        return False
    # 首/尾是骨架字 → 只可能是句子骨架
    if c[0] in _EDGE_FUNC or c[-1] in _EDGE_FUNC:
        return False
    # 内部夹着功能字/单字动词 → 一定跨了词（只对 ≥3 字词做）
    if len(c) >= 3 and any(ch in _INNER_FUNC or ch in _INNER_VERB
                           for ch in c[1:-1]):
        return False
    if strict:
        # 首/尾是单字动词 → 被动词切开的碎片
        if c[0] in _EDGE_VERB or c[-1] in _EDGE_VERB:
            return False
        # 尾字数量词
        if c[-1] in _TAIL_FUNC:
            return False
    return True


def _extract(text, strict=True):
    """内置滑窗词法。`strict=False` = 只做第九轮的既有剪刀（宽松档，回落用）。"""
    s = str(text or '')
    seen, out = set(), []
    for m in _TOKEN_RE.finditer(s):
        tok = m.group(0)
        if re.match(r'^[A-Za-z]', tok) or tok.isdigit():
            low = tok.lower()
            if low in _EN_STOP or len(low) < 3:
                continue
            cand = [low]
        else:
            cand = _ngrams(tok)
        for c in cand:
            if not _keep(c, seen, strict):
                continue
            seen.add(c)
            out.append(c)
    return out


def _from_segmenter(text):
    """外部分词器路径：分词器已经知道词边界，这里只做停用词/长度/去重过滤。"""
    fn = _SEGMENTER
    if fn is None:
        return []
    try:
        words = list(fn(str(text or '')))
    except Exception:
        return []                                   # 分词器坏了 → 回落内置词法
    out, seen = [], set()
    for w in words:
        w = str(w or '').strip()
        if not w:
            continue
        if re.match(r'^[A-Za-z0-9]', w):
            w = w.lower()
            if len(w) < 3 or w in _EN_STOP:
                continue
        elif len(w) < 2:
            continue
        if w in _STOPWORDS or w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


def extract_keywords(text):
    """从一句话里抽出话题关键词（有序去重，保持**句中出现顺序**）。

    三层**择优**（第十一轮）：

      1. **外部注入的分词器**（若有，见 `set_segmenter`）—— 真分词器的结果最可信；
      2. **严格词法** —— 第九轮既有剪刀 + 三把位置专精剪刀，专杀
         `点代/码写/天想写/雨会/息一下` 这类被单字动词切开的碎片；
      3. **宽松词法** —— 严格词法**一个词都没抽到**时，回落到只做第九轮剪刀。

    第 3 层是**安全网**，不是装饰：句子里唯一的话题词若恰好被新剪刀切中
    （如"重要吗"里的"重要"、"开会吗"里的"开会"），严格档会给出空列表，
    于是话题锚会静默退化成"抽不到词 → 不建题" —— 那是**用户可见的功能退化**。
    宁可在这种句子上退回旧行为（带上一点碎片），也不能让整条链路哑掉。

    **顺序即语义**：输出顺序被 `memory_graph.edge_pairs('chain')` 当作"句子里的先后"
    用来连边，因此这里必须按位置升序（`_ngrams` 已按位置生成）。
    """
    if not text:
        return []
    out = _from_segmenter(text)
    if out:
        return out
    strict = _extract(text, strict=True)
    if strict:
        return strict
    return _extract(text, strict=False)



def _coverage(new_kw, topic_kw):
    """新话的关键词里有多少能对上当前话题（0~1）。"""
    if not new_kw or not topic_kw:
        return 0.0
    tset = set(topic_kw)
    hit = sum(1 for k in new_kw if k in tset)
    return hit / float(len(new_kw))


class Topic(object):
    """一个话题：标签 + 关键词 + 生命周期统计。"""

    __slots__ = ('label', 'keywords', 'started_at', 'last_at', 'turns',
                 'user_turns', 'pending')

    def __init__(self, label, keywords, now):
        self.label = label
        self.keywords = list(keywords)[:24]
        self.started_at = now
        self.last_at = now
        self.turns = 0
        self.user_turns = 0
        self.pending = []          # [(提问/承诺文本, 时间)]

    def merge(self, keywords, now):
        """把新关键词并进来（按出现权重累加，保留最有代表性的前若干个）。"""
        score = {}
        for i, k in enumerate(self.keywords):
            score[k] = score.get(k, 0) + max(1, 12 - i)
        for i, k in enumerate(keywords):
            score[k] = score.get(k, 0) + max(1, 12 - i)
        self.keywords = [k for k, _c in
                         sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))][:24]
        self.last_at = now

    def duration(self, now=None):
        return max(0.0, (now if now is not None else time.time()) - self.started_at)


class ConversationFocus(object):
    """当前在聊什么 + 有没有悬着的问题没被回答。"""

    # —— 判定阈值（都是有依据的经验值，可调）——
    NEW_TOPIC_COVERAGE = 0.34     # 新话关键词对当前话题的覆盖率低于此值 → 视为换题
    MIN_SHARED_STRONG = 1         # 至少要有 1 个共同关键词才允许"延续"
    IDLE_ARCHIVE_SECONDS = 300.0  # 5 分钟没人提 → 话题冷场，归档
    PENDING_TTL = 240.0           # 悬置问题超过 4 分钟就不再追问
    MAX_TURNS_BEFORE_REFRESH = 24  # 话题聊太久（24 轮）自动提示"该收了"

    def __init__(self, now=None):
        self.topic = None
        self.history = []           # 已归档话题的摘要
        self._now = now or time.time()

    # ------------------------------------------------------------ 内部
    def _t(self):
        return time.time()

    def _archive(self):
        if self.topic is not None:
            self.history.append({
                'label': self.topic.label,
                'keywords': list(self.topic.keywords[:8]),
                'started_at': self.topic.started_at,
                'ended_at': self.topic.last_at,
                'turns': self.topic.turns,
            })
            self.history = self.history[-12:]

    @staticmethod
    def _label_from(keywords):
        """话题标签：取"最长且最早"的关键词。

        3 字窗口通常比 2 字窗口更具体（"塞尔达" 比 "塞尔" 像人话），
        而 `max(key=len)` 在等长时返回最先出现的那个 → 保持出现顺序的可解释性。
        """
        if not keywords:
            return '（未命名）'
        return max(keywords[:12], key=len)

    # ------------------------------------------------------------ 对外
    def note_user(self, text):
        """用户说了一句话。返回 'new' / 'continue' / 'switch' / 'idle'。"""
        now = self._t()
        kw = extract_keywords(text)
        s = str(text or '')

        if self.topic is not None and (now - self.topic.last_at) > self.IDLE_ARCHIVE_SECONDS:
            self._archive()
            self.topic = None

        if self.topic is None:
            if not kw:
                return 'idle'
            self.topic = Topic(self._label_from(kw), kw, now)
            self.topic.turns = 1
            self.topic.user_turns = 1
            return 'new'

        cov = _coverage(kw, self.topic.keywords)
        shared = len(set(kw) & set(self.topic.keywords))
        has_marker = any(mk in s for mk in _CONTINUE_MARKERS)

        if (shared >= self.MIN_SHARED_STRONG and cov >= self.NEW_TOPIC_COVERAGE) or has_marker:
            self.topic.merge(kw, now)
            self.topic.turns += 1
            self.topic.user_turns += 1
            return 'continue'

        # 换题必须**由用户发起**：只有用户自己带来一组新关键词时才换。
        self._archive()
        self.topic = Topic(self._label_from(kw) if kw else '（闲聊）', kw, now)
        self.topic.turns = 1
        self.topic.user_turns = 1
        return 'switch'

    def note_assistant(self, text):
        """Ralsei 说了一句话：累计轮数，并登记"它抛出的问题"作为悬置事项。"""
        now = self._t()
        if self.topic is None:
            kw = extract_keywords(text)
            if not kw:
                return
            self.topic = Topic(self._label_from(kw), kw, now)
            self.topic.turns = 1
            return
        self.topic.turns += 1
        self.topic.last_at = now
        s = str(text or '')
        if len(s) >= 4 and any(mk in s for mk in _QUESTION_MARKERS):
            # 只留最后一条，避免问题堆成山
            self.topic.pending = [(s.strip()[:60], now)]

    def pending_question(self):
        """还没被回答、且没超时的最后一个问题。"""
        if self.topic is None or not self.topic.pending:
            return None
        text, ts = self.topic.pending[-1]
        if self._t() - ts > self.PENDING_TTL:
            return None
        return text

    def clear_pending(self):
        if self.topic is not None:
            self.topic.pending = []

    def brief(self):
        """给模型看的一段中文（本模块影响模型的唯一出口）。"""
        if self.topic is None:
            return ""
        now = self._t()
        mins = self.topic.duration(now) / 60.0
        if mins >= 1.0:
            span = "约 %d 分钟" % max(1, int(round(mins)))
        else:
            span = "不到 1 分钟"
        lines = ["【注意力焦点·必须遵守】",
                 "你现在正在和主人聊的话题是「%s」（已聊 %d 轮，%s）。"
                 % (self.topic.label, self.topic.turns, span),
                 "除非主人自己把话题换掉，你就**继续这个话题**往下聊；"
                 "不要主动跳到别的事情上，也不要突然问一个和当前话题无关的问题。"
                 "如果主人明显换了话题，就自然跟上。"]
        if self.topic.turns >= self.MAX_TURNS_BEFORE_REFRESH:
            lines.append("这个话题已经聊了很久，可以自然收一收、换个轻松的小话题。")
        pq = self.pending_question()
        if pq:
            lines.append("【还没有回应】你刚才问过：「%s」，主人还没回答。"
                         "可以自然地再提一次，但**不要重复原话**。" % pq)
        return "\n".join(lines)

    # ------------------------------------------------------------ 持久化
    def snapshot(self):
        """可 JSON 化的状态（会话结束/落盘用）。"""
        t = self.topic
        return {
            'topic': None if t is None else {
                'label': t.label, 'keywords': list(t.keywords),
                'started_at': t.started_at, 'last_at': t.last_at,
                'turns': t.turns, 'user_turns': t.user_turns,
                'pending': [list(p) for p in t.pending],
            },
            'history': [dict(h) for h in self.history],
        }

    def restore(self, data):
        """从 snapshot() 恢复（容错：任何字段坏了就当没有）。"""
        try:
            if not isinstance(data, dict):
                return
            hist = data.get('history')
            if isinstance(hist, list):
                self.history = [h for h in hist if isinstance(h, dict)][-12:]
            d = data.get('topic')
            if not isinstance(d, dict):
                self.topic = None
                return
            label = str(d.get('label') or '（未命名）')
            kw = [str(k) for k in (d.get('keywords') or []) if isinstance(k, str)]
            now = time.time()
            t = Topic(label, kw, float(d.get('started_at') or now))
            t.last_at = float(d.get('last_at') or now)
            t.turns = int(d.get('turns') or 0)
            t.user_turns = int(d.get('user_turns') or 0)
            pend = d.get('pending') or []
            t.pending = [(str(p[0]), float(p[1])) for p in pend
                         if isinstance(p, (list, tuple)) and len(p) == 2]
            self.topic = t
        except Exception:
            self.topic = None

    # ------------------------------------------------------------ 查询
    def current_label(self):
        return self.topic.label if self.topic is not None else ''

    def is_empty(self):
        return self.topic is None

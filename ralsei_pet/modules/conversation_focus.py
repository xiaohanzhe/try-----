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
_INNER_FUNC = frozenset("的了着过和与或这那我们吗呢吧啊呀哦嗯啦嘛么个")

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
    """中文串取 2 字与 3 字滑窗（不用分词器也能覆盖绝大多数话题词）。"""
    out = []
    n = len(run)
    for size in (2, 3):
        if n < size:
            continue
        if n == size:
            out.append(run)
            continue
        for i in range(n - size + 1):
            out.append(run[i:i + size])
    return out


def extract_keywords(text):
    """从一句话里抽出话题关键词（有序去重，保持出现顺序便于调试）。"""
    if not text:
        return []
    s = str(text)
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
            if c in _STOPWORDS or c in seen:
                continue
            # 纯虚词组合（如"的了"）直接丢
            if all(ch in '的了着过和与或也都是就还又而但却为所以如果那么这那' for ch in c):
                continue
            # 滑窗碎片：首/尾是骨架字，或内部夹着强功能字 → 不是话题词
            if c[0] in _EDGE_FUNC or c[-1] in _EDGE_FUNC:
                continue
            if any(ch in _INNER_FUNC for ch in c):
                continue
            seen.add(c)
            out.append(c)
    return out


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

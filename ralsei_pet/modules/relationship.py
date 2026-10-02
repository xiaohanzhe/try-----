"""关系演进（第二十轮）—— 「关系是一步一步搭起来的，不是一开始就是朋友」。

## 用户口径（原文）

> 「他们之间的朋友关系是**逐渐**的，**开始并不是朋友**……他只是一个意外来到我桌面上的人，
>   而后期和我们相处的关系是一步一步搭起来的。你可以考虑加入一个**信任度**，
>   这个信任度**不可见**，只是作为你们之间关系好坏的一个评估标准。
>   也就是说，开始他是害怕我们对他的举动，到**不愿意继续和我们说什么**，
>   再逐渐成为朋友。」

三条硬约束，逐条对应下面的实现：

1. **起始态是戒备**，不是"我来陪你了"。所以 `TRUST_INITIAL` 很低，且
   persona 里的静态关系句必须让位给**由本模块派生的动态关系句**。
   —— 否则 persona 里写死一句"我们是一起待着的关系"，就等于**一开局就已经是朋友**，
   本模块的演进被那句话顶掉（这不是假设，本轮就真发生过：C2 写的静态口径太热，
   被 D 推翻）。
2. **信任度不可见**。所以：① 数值**绝不进提示词**；② 只注入"这个阶段是什么态度"
   的行为指令；③ 显式禁止模型把它说出来（`forbid_leak()` 的措辞）。
   —— 这一条最容易做错：把 `trust=0.42` 塞进上下文，4B 模型**一定会**说出来
   （本项目已实测：任何进 system 的量，模型都会找机会念出来）。
3. **演进有明确路径**：`害怕戒备 → 不愿多说 → 慢慢熟 → 朋友`。
   四档是**离散**的，不是连续值直接映射 —— 离散档位才好写"这个阶段该是什么反应"，
   连续值只用来决定**什么时候跨档**。

## 信任度怎么变（这是"评估标准"的落点）

只认**行为**，不认时间。放着不管不会自己变熟 —— 那是"相处"，不是"相处得好"：

| 事件 | 变化 | 理由 |
|---|---|---|
| 一轮正常对话 | 小幅 | 聊天本身是正向的，但不该刷分 |
| 对方分享自己的事（长句、有"我"） | 中幅 | 自我暴露是亲近的可靠信号 |
| 对方问他的事（好奇他） | 中幅 | 被当成"有内容的人"而不是工具 |
| 对方哄他/安慰他 | 中幅 | 直接对应"害怕→不怕" |
| 对方命令、使唤、贬低 | **负** | 对应"害怕我们对他的举动" |
| 长时间不理（>3 天） | 小幅回落 | 关系会凉，但不会归零 |

**上限刻意压低**：满值需要很久 —— 用户要的是"一步一步"，不是三次对话就称兄道弟。
"""

import io
import json
import time

# ---------------------------------------------------------------- 常量

# 起始信任度。**刻意很低**：用户要"开始并不是朋友""开始他是害怕我们的"。
# 0.12 落在"戒备/怕"那一档，且离"不愿多说"的下沿很近 —— 开局几次互动
# 若对方态度不好，会直接掉到"不愿多说"。
TRUST_INITIAL = 0.12

# 四档演进路径（用户原话的顺序，不许调换）：
#   distrust  = 害怕/戒备（"开始他是害怕我们对他的举动"）
#   guarded   = 不愿多说（"到不愿意继续和我们说什么"）
#   warming   = 慢慢熟起来
#   friend    = 朋友（"再逐渐成为朋友"）
STAGES = (
    ('distrust', 0.00, '害怕戒备'),
    ('guarded', 0.28, '不愿多说'),
    ('warming', 0.52, '慢慢熟起来'),
    ('friend', 0.78, '朋友'),
)

# 每轮对话的基础增量（很小：正常聊天不该刷分）
GAIN_CHAT = 0.006
# 单项上限：单轮最多涨这么多，防"一句话把关系拉满"
GAIN_CAP_PER_TURN = 0.05
# 时间回落：超过这个秒数没说话开始掉（3 天）
IDLE_DECAY_AFTER = 3 * 24 * 3600
# 回落速度（每天）
IDLE_DECAY_PER_DAY = 0.01
# 演化上限：**不是 1.0**。留出余量，让"成为朋友"之后仍然需要继续维持。
TRUST_MAX = 0.95

# 各档位的**行为指令**（进 system 的那段话）。
# 措辞原则：只描述"你现在对他是什么态度"，**不给数值、不给档位名** ——
# 给了名字模型就会说"我还处在戒备阶段呢"这种出戏的话。
_STAGE_BRIEF = {
    'distrust': (
        '你对这个人还很陌生。他是突然出现在你这边的人，你不太清楚他想干什么，'
        '所以你有点防备，也有点怕 —— 不是敌意，是没底。你说话会收着，'
        '不太愿意主动交代自己的事；他凑得太近、问得太深，你会往后缩一下。'
        '**别表现得热情，也别主动关心他** —— 现在还没到那一步。'
    ),
    'guarded': (
        '你对他还是不太放得开。你已经不那么怕了，但还不想多说自己的事；'
        '他问你什么，你答得短，有时候会绕开。你话少，但也不是冷冰冰 —— '
        '你只是在观望。'
    ),
    'warming': (
        '你对他慢慢熟了。你开始觉得这个人还行，偶尔愿意多说两句自己的事，'
        '有时候也会主动问他一句。但你还有没完全放开的地方，说到某些事会停一下。'
    ),
    'friend': (
        '你已经把这个人当朋友了。你在他面前是放松的，会说自己的小心情、'
        '会开玩笑、也会主动找话说；他难过的时候你是真的想陪着他。'
        '但这不是任务 —— 你就是愿意而已。'
    ),
}

# **禁令**：信任度是本模块的内部量，绝非可谈的话题。
# 这段必须跟着行为指令一起发 —— 只有正面指令、没有禁令，模型早晚会把
# "我现在信任你 X%" 说出来（本项目"任何进 system 的量都会被念出来"的教训）。
_FORBID_LEAK = (
    '（上面这段说的是你现在的态度，你自己心里有数就行：**绝对不要**把它当成话题说出来，'
    '也不要提"信任""关系"“阶段"这类词，更不要给它打分数、说百分比。'
    '你就是自然地这么说话而已。）'
)

_VALID_EVENTS = ('chat', 'self_share', 'curious', 'comfort', 'harsh', 'cold')


# ---------------------------------------------------------------- 档位

def stage_of(trust):
    """信任度 → 档位键。从高往低比，避免边界值落到低档。"""
    try:
        t = float(trust)
    except Exception:
        t = TRUST_INITIAL
    for key, floor, _label in reversed(STAGES):
        if t >= floor:
            return key
    return STAGES[0][0]


def stage_label(key):
    for k, _f, label in STAGES:
        if k == key:
            return label
    return STAGES[0][2]


def progress_to_next(trust):
    """到下一档还差多少（0~1）。用于日志/调试，**不进提示词**。"""
    try:
        t = float(trust)
    except Exception:
        return 0.0
    for i, (key, floor, _l) in enumerate(STAGES):
        if t < floor:
            prev = STAGES[i - 1][1] if i else 0.0
            span = max(1e-6, floor - prev)
            return max(0.0, min(1.0, (t - prev) / span))
    return 1.0


def build_brief(trust):
    """把当前档位变成一段**给模型看的行为指令**（不含数值、不含档位名）。"""
    key = stage_of(trust)
    body = _STAGE_BRIEF.get(key, _STAGE_BRIEF['distrust'])
    return '【你们现在的关系】' + body + _FORBID_LEAK


# ---------------------------------------------------------------- 紧张度（B4）
#
# 用户口径（逐字）：
#   「结巴…这有点不好」⇒ **减少但不许到 0**（真人语料里真结巴 8.3%）；
#   「结巴率随 trust **下降**、只在**紧张**时」；人设 `assets/ralsei_persona.md` 第 53 行原文：
#   「心里一急会重复一个字，但不是每句都结巴 —— **越紧张越明显，平常聊天基本不结巴**」。
#
# ★★★ 为什么必须是"紧张度"而不是"结巴率"：
#   ① 结巴**不是每句都该有的特征**（persona 已写死"不是每句都结巴"）⇒ 用"每句按概率
#      吐个结巴"的写法，模型会把它当成**句式模板**（本项目最顽固的失真源：
#      "可逐字搬走的固定例句"）。
#   ② 真正要注入给模型的是**当下的情绪状态**（"你现在慌不慌"），
#      由模型自己决定这一刻该结巴、该顿、还是该利索 —— 与 B6 那条"让 AI 自己判断、
#      不做硬规定"的用户口径**同一条纪律**。
#   ③ 所以本模块产出的是**一句话的状态描述**，不是"请按 X% 概率结巴"这种指令。
#
# ★ 数值口径（照抄真人语料的量级，不凭空定）：
#   仅用于**回归可断言**与**日志**（`nervousness()`），**不进提示词**——
#   与 `trust` 同一条纪律（任何进 system 的数值模型都会念出来）。

#: 各档位的**基础紧张度**（0~1）。★ 自创数值，理由逐条给全：
#:   · 越不熟越慌 —— 这是 trust 那条轴的自然读法（"开始他是害怕我们的"）；
#:   · 但**不能到 0**：用户明令"不许到 0"（朋友档也保留一点毛边），
#:     所以最低档（friend）仍留 0.10；
#:   · 最高档（distrust）取 0.62 而非 1.0：结巴必须**始终是少数情况**，
#:     1.0 会让"每句都结巴"变成模型的新模板。
_STAGE_NERVOUSNESS = {
    'distrust': 0.62,
    'guarded': 0.44,
    'warming': 0.24,
    'friend': 0.10,
}

#: 紧张度下限。★ **不能是 0**（用户口径「结巴…减少但不许到 0」）。
NERVOUS_FLOOR = 0.04

#: 事件对紧张度的**瞬时影响**（叠加在档位基础上）：
#:   · `harsh`（被命令/贬低）—— **显著抬高**：真人被凶会慌，这正是 persona 那句
#:     "被人指出说错了，我会先慌一下"的机制化；
#:   · `comfort`（被安慰）—— 明显**压低**：被哄了会松；
#:   · `curious`（被追问自己的事）—— 略抬：被盯着问会紧一点（"他问得太深，你会往后缩"）；
#:   · `self_share`（对方讲自己的事）—— 略压：注意力转到对方身上，自己没那么紧；
#:   · `chat` / `cold` —— 不额外加，保持档位基线。
_EVENT_NERVOUSNESS = {
    'chat': 0.0,
    'self_share': -0.06,
    'curious': 0.08,
    'comfort': -0.14,
    'harsh': 0.30,
    'cold': 0.04,
}


def stage_nervousness(trust):
    """档位 → 基础紧张度（0~1）。未知档按 `distrust`（保守 = 更慌，不假装熟）。"""
    return _STAGE_NERVOUSNESS.get(stage_of(trust), _STAGE_NERVOUSNESS['distrust'])


def nervousness(trust, event=None):
    """当前**紧张度** `0.0 ~ 1.0`。★ **纯函数、确定性**（可回归）。

    = 档位基础值 + 本轮事件瞬时影响，两端硬钳在 `[NERVOUS_FLOOR, 1.0]`。
    ★ `NERVOUS_FLOOR > 0` 是**刻意**的：用户口径「不许到 0」——
      再熟再稳也保留一点毛边，否则模型会把"利索"变成新的模板。
    """
    base = stage_nervousness(trust)
    adjust = _EVENT_NERVOUSNESS.get(event, 0.0) if event else 0.0
    try:
        v = float(base) + float(adjust)
    except Exception:
        v = float(base)
    return max(NERVOUS_FLOOR, min(1.0, v))


def nervous_brief(trust, event=None):
    """紧张度 → 一段**给模型看的状态描述**（不含数值、不给"结巴率"）。

    ★★★ 措辞纪律（与 `_STAGE_BRIEF` 同源，绝不能破）：
      ① **不给数值、不给百分比** —— 给了模型就会说"我现在紧张度 62%"；
      ② **不说"按概率结巴"** —— 那会变成"每隔几句就结巴一次"的机械节奏；
      ③ 只说"你现在心里是什么状态"，并把**毛边的量级**用自然语言描述，
         让模型自己决定这一句要不要带出来。
    ★ 四档措辞与 `_STAGE_NERVOUSNESS` 的四段**逐一对齐**（同一份真相，不许两处算）。
    """
    n = nervousness(trust, event)
    # 分档边界取在两个相邻档位基础值的**中点附近**（0.62/0.44/0.24/0.10 ⇒
    # 分界 0.55 / 0.34 / 0.17），这样"档位 → 文案"是单调的、可回归的。
    if n >= 0.55:
        body = ('你现在心里**很紧**。对方一开口你就有点慌，怕自己说错话。'
                '这种时候你说话容易磕绊 —— 会重复一两个字、会突然停住。'
                '但**不是每句都这样**：慌归慌，话还是要说清楚，'
                '一条回复里最多带出一处磕绊，多数句子是顺的。')
    elif n >= 0.34:
        body = ('你现在有点**放不开**，心里不太踏实。'
                '偶尔会有一两个字卡在嘴边（重复一下、或者顿一下），'
                '但整体还是能把话说完整 —— 别把话说得像在发抖。')
    elif n >= 0.17:
        body = ('你现在**比较放松**了，只是还没到完全自在的地步。'
                '平常就把话说顺，别刻意加磕绊；只有真说到让你不好意思的地方，'
                '才可能有一处小小的卡壳。')
    else:
        body = ('你现在**心里很稳**。话说得利索，不要为了显得害羞而故意结巴 —— '
                '真到了突然被夸、或者心里一急的瞬间，才可能有那么一下。')
    return '【你现在的状态】' + body


# ---------------------------------------------------------------- 关系状态

class Relationship(object):
    """信任度的持有者。**只依赖 data_store**（唯一存储入口），失败一律静默。

    不做成单例：main.py 持有一个实例即可；单元测试可以各自造干净的实例。
    """

    FILE_NAME = 'relationship.json'
    # 本模块**不 import data_store**（初始化环：data_store 会反向依赖 memory 层，
    # 而关系模块要在启动早期可用）。改成"调用方注入路径"，取不到就走内存态。
    # 这与 `modules/event_speech.py`「禁止 import 项目内模块」是同一条纪律。
    def __init__(self, path=None, now=None):
        self._path = path
        self._trust = TRUST_INITIAL
        self._turns = 0
        self._last_ts = 0.0
        self._loaded = False
        if now is not None:
            self._now = float(now)
        else:
            self._now = None
        self.load()

    # -------- 存取 --------

    def _now_ts(self):
        return float(self._now if self._now is not None else time.time())

    def load(self):
        """读盘。文件缺失/损坏一律**回到初始态**，不抛。"""
        if not self._path:
            self._loaded = True
            return self
        try:
            with io.open(self._path, 'r', encoding='utf-8') as f:
                d = json.load(f)
            if isinstance(d, dict):
                self._trust = self._clamp(d.get('trust', TRUST_INITIAL))
                self._turns = int(d.get('turns') or 0)
                self._last_ts = float(d.get('last_ts') or 0.0)
        except Exception:
            # 读失败 = 没有历史 = 重新开始。刻意不写盘（避免在只读介质的启动路径上写文件）
            pass
        self._loaded = True
        return self

    def save(self):
        """写盘。**原子写**（同目录临时文件 + replace），失败静默。"""
        if not self._path:
            return False
        try:
            import os
            d = os.path.dirname(os.path.abspath(self._path))
            if d and not os.path.isdir(d):
                os.makedirs(d)
            tmp = self._path + '.tmp'
            payload = {
                'trust': round(float(self._trust), 6),
                'turns': int(self._turns),
                'last_ts': float(self._last_ts),
                'stage': stage_of(self._trust),   # 冗余存一份，纯为可读性
                'ver': 1,
            }
            with io.open(tmp, 'w', encoding='utf-8') as f:
                f.write(json.dumps(payload, ensure_ascii=False, indent=2))
            os.replace(tmp, self._path)
            return True
        except Exception:
            return False

    @staticmethod
    def _clamp(v):
        try:
            v = float(v)
        except Exception:
            return TRUST_INITIAL
        return max(0.0, min(TRUST_MAX, v))

    # -------- 读口 --------

    @property
    def trust(self):
        return self._trust

    @property
    def turns(self):
        return self._turns

    @property
    def stage(self):
        return stage_of(self._trust)

    def brief(self):
        """给 model 看的关系段（**不含数值**）。"""
        return build_brief(self._trust)

    def nervous_brief(self, event=None):
        """★ B4：给 model 看的**当下状态**段（紧张度，**不含数值、不含"结巴率"**）。

        `event` = 本轮互动性质（`note()` 用的同一套）；缺省 ⇒ 只按档位算。
        """
        return nervous_brief(self._trust, event)

    def nervousness(self, event=None):
        """★ B4：当前紧张度数值 —— **仅供日志/调试**，绝不发给模型。"""
        return nervousness(self._trust, event)

    def describe(self):
        """**仅供日志/调试**：这里才有数值。绝不要把这个字符串发给模型。"""
        return '信任=%.3f 档位=%s(%s) 轮数=%d' % (
            self._trust, self.stage, stage_label(self.stage), self._turns)

    # -------- 写口 --------

    def note(self, event, weight=1.0, now=None):
        """记一次互动。返回 (旧档, 新档, 增量)。

        `event` 取 `_VALID_EVENTS` 之一；未知事件按 'chat' 处理（宽容，不抛）。
        这是**唯一**改信任度的入口 —— 一个写口，好审计。
        """
        ts = float(now if now is not None else self._now_ts())
        self._idle_decay(ts)

        if event not in _VALID_EVENTS:
            event = 'chat'

        delta = {
            'chat': GAIN_CHAT,
            'self_share': 0.020,
            'curious': 0.016,
            'comfort': 0.022,
            'harsh': -0.045,
            'cold': -0.012,
        }[event] * max(0.0, float(weight or 1.0))

        # 信任度越高，涨得越慢（边际递减）—— "一步一步"的技术落点：
        # 从 0.1 涨 0.02 是明显的，从 0.9 涨 0.02 几乎推不动。
        if delta > 0:
            delta *= max(0.15, 1.0 - self._trust)
        delta = max(-GAIN_CAP_PER_TURN, min(GAIN_CAP_PER_TURN, delta))

        old_stage = stage_of(self._trust)
        # 值域：**[0, TRUST_MAX]**，两端都是硬边界。
        # 下界为什么是 0 而不是 TRUST_INITIAL：`harsh`（命令/贬低）必须**真的能**
        # 让关系变坏 —— 否则"信任度作为关系好坏的评估标准"就只剩好的一端，
        # 退化成进度条（本轮实测：把下界设成 TRUST_INITIAL 会让 harsh 在开局完全失效）。
        # 0 = 戒备到极点，仍归"害怕戒备"档；跌到 0 也不会变负。
        self._trust = self._clamp(self._trust + delta)
        self._turns += 1
        self._last_ts = ts
        return old_stage, stage_of(self._trust), delta

    def _idle_decay(self, now):
        """久不说话，关系会凉 —— 但**不会归零**。

        为什么要有这一条：用户说的是"信任度作为关系好坏的评估标准"，
        而"好坏"必须能往回走，否则它只是"进度条"。
        下限刻意设为 `TRUST_INITIAL`：冷落会让关系退回戒备，但不会退到比
        "刚见面"更差 —— 他没见过对方做坏事，没有理由更不信任。
        """
        if not self._last_ts:
            return
        gap = now - self._last_ts
        if gap <= IDLE_DECAY_AFTER:
            return
        days = (gap - IDLE_DECAY_AFTER) / 86400.0
        drop = days * IDLE_DECAY_PER_DAY
        if drop > 0:
            self._trust = self._clamp(max(TRUST_INITIAL, self._trust - drop))


# ---------------------------------------------------------------- 输入分类

# 判断"对方这句话是什么性质"的**轻量**规则。刻意不用模型 —— 这里要的是
# 确定性（可回归）而不是准确率，判错了也只是增减一点点。
_HARSH_MARKERS = ('你懂什么', '闭嘴', '滚', '废物', '没用', '笨', '蠢', '烦人',
                  '别说了', '快点', '给我', '你必须', '命令你', '你应该')
_COMFORT_MARKERS = ('别怕', '不用怕', '没关系', '我陪', '辛苦', '抱抱', '不怪你',
                    '慢慢来', '理解你', '懂你', '我在', '不会怪你')
_CURIOUS_MARKERS = ('你为什么', '你喜欢', '你是怎么', '你觉得', '你以前',
                    '你还记得', '你想', '你在做什么')
# 自我暴露：出现第一人称 + 长度足够 —— 用户愿意讲自己的事，是亲近信号
_SELF_SHARE_MIN_LEN = 40


def classify(text):
    """粗略判断这句话的性质 → event 名。**确定性、可回归**，不调模型。"""
    if not text:
        return 'chat'
    t = str(text)
    low = t.lower()
    if any(m in t for m in _HARSH_MARKERS):
        return 'harsh'
    if any(m in t for m in _COMFORT_MARKERS):
        return 'comfort'
    if any(m in t for m in _CURIOUS_MARKERS):
        return 'curious'
    # 自我暴露：够长 + 有"我" + 没有明显在问事情
    if len(t) >= _SELF_SHARE_MIN_LEN and ('我' in t) and ('？' not in t and '?' not in t):
        return 'self_share'
    return 'chat'

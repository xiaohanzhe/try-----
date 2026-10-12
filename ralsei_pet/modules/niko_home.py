# -*- coding: utf-8 -*-
"""Niko 的家 —— **准入门槛** + **问答护栏**（第112轮 #47 续）。

用户口径（第112轮，逐字）
--------------------------
（1）准入
    「**niko 的家确保只是除了用户（灵魂）不可以进去其他人都能进去哦**」
（2）门后内容
    「niko 没原素材的家，你现在认知的家可能是 niko 在 oneshot 里醒来的那个房子，
      但那不是他的家，所以你只需要做出来一个门就好，**剩下里面的内容没有**，
      也就是营造出来**一个门里是 niko 的家乡的错觉**但实际上**门里啥都没有**」
（3）问答（★ 明确「**两条线都接**」）
    「如果用户问其他人 niko 家长啥样那就让他们**先正常回答 niko 在原作里描述的那样**，
      如果**继续追问**那就回答「**内容以屏蔽**」」

设计要点
--------
1. **零依赖**：纯标准库、纯函数/纯数据。可被回归套件直接 import（与 `door_reveal`
   同规格）。**不 import Qt、不读文件**。
2. ★★★ **单一真源**：三连台词 / 准入规则 / 屏蔽语都在这里；`main.py` 与
   `item_interact.py` 都从这里取，不再各写一份字面量。
3. **准入 = 白名单**（"除了用户都能进"）而不是黑名单（"列出谁能进"）：
   用户原话是"**除了**用户（灵魂）……**其他人都能**进" ⇒ 把"用户/灵魂"这个
   主体排除，其余一律放行。★ 这样将来加了新角色**不需要改这里**
   （黑名单则在每次加角色时都要记得补，必漏）。
"""

#: ★★★ 屏蔽语（用户逐字给定）。**照抄**，不要改字、不要加标点。
BLOCKED_REPLY = '内容以屏蔽'

#: 三连确认台词（用户逐字给定，第111轮落地）。★ 保留在此作为**单一真源**，
#: `item_interact.NIKO_HOME_EGG_TEXT` 由本模块派生（见文件末的一致性断言）。
EGG_TEXTS = ('你确定吗？',
             '你这样的行为可能导致世界崩坏，你真的确定吗？',
             '你真的不再考虑考虑了吗？')

#: 两个选项的文案（原作 OneShot 的两选项结构）。
CHOICE_RECONSIDER = '我再考虑考虑'
CHOICE_CONFIRM = '我确定'
CHOICE_CONFIRM_LAST = '我确定！！！'


# ---------------------------------------------------------------------------
#  1. 准入门槛
# ---------------------------------------------------------------------------

#: 被排除的主体名集合（**"用户" = 灵魂**）。★ 大小写不敏感比对。
#: 这里列的是"**谁不能进**"—— 只有用户/灵魂。
_USER_SUBJECTS = frozenset(('soul', 'user', 'player', 'kris', '灵魂', '用户'))


def is_user_subject(actor):
    """发起者是否 = **用户（灵魂）**。

    判定顺序（命中任一即 True）：
      ① `actor is None` ⇒ **False**（★ 关键：`None` 代表"NPC 自动/系统触发"，
         按用户口径"其他人都能进" ⇒ 必须**放行**，不能当成用户拦掉）；
      ② `actor` 是字符串 ⇒ 归一化后查 `_USER_SUBJECTS`；
      ③ `actor` 有 `subject` / `kind` / `name` 属性 ⇒ 取它（本项目 NPC 的对象惯例）；
      ④ 对象带 `is_soul` / `is_user` 真值属性 ⇒ 真即用户；
      ⑤ 兜底 ⇒ **False**（放行）。

    ★★★ 为什么兜底是 **False（放行）** 而不是 True（拦住）：用户口径是
      "**除了**用户……**其他人都能**进" ⇒ 默认侧必须站在"能进"这一边。
      反过来（默认拦）会把所有 NPC、所有自主行为全部挡死 —— 那才是真 bug。
      宁可"某个奇怪的 actor 被当成普通人放行"，也不要"NPC 全进不去"。
    """
    if actor is None:
        return False
    if isinstance(actor, str):
        return actor.strip().lower() in _USER_SUBJECTS
    # 对象：先看显式布尔标记（最可靠）
    for flag in ('is_soul', 'is_user', 'is_player'):
        try:
            v = getattr(actor, flag, None)
            if v is True:
                return True
        except Exception:
            pass
    # 再看标识字段
    for attr in ('subject', 'kind', 'name', 'id', 'key'):
        try:
            v = getattr(actor, attr, None)
        except Exception:
            v = None
        if isinstance(v, str) and v.strip().lower() in _USER_SUBJECTS:
            return True
    return False


def can_enter(actor):
    """`actor` 能否进 Niko 的家。返回 `(allowed: bool, reason: str)`。

    ★ 用户（灵魂）⇒ **不能进**（`False`）；其他所有人 / `None`（系统触发）
      ⇒ **能进**（`True`）。
    ★ 本函数**只给准入结论**，不负责"进去之后干什么" —— 门后啥都没有，
      "进去"这件事本身由调用方按自己的语义落地（见 `entrance_hint`）。
    """
    if is_user_subject(actor):
        return False, 'user'
    return True, 'other'


# ---------------------------------------------------------------------------
#  2. 门后内容 —— "错觉"，实际为空
# ---------------------------------------------------------------------------

#: 进门后**唯一**给出的观感文案（营造"门里是 Niko 的家乡"的错觉）。
#: ★ 用户口径：「营造出来一个门里是 niko 的家乡的错觉但实际上门里啥都没有」。
#: ★★ 刻意**极短、不提任何具体场景细节** —— 一提细节就等于"编内容"，
#:   而用户明说"里面的内容没有"。所以这里只给"望进去"的**感觉**。
ENTRANCE_HINT = '（门里一片温柔的暖光，隐约像是很远的地方。什么都看不清。）'

#: 敲门 / 张望的具体台词（比 `ENTRANCE_HINT` 更轻，用于"路过看一眼"）。
PEEK_HINT = '（门虚掩着一条缝，里面安安静静的。）'


def entrance_hint(actor):
    """进门 / 张望时给的一句话。返回 `(text, allowed)`。

    · 用户（灵魂）⇒ `('（……你进不去。）', False)`
    · 其他人      ⇒ `(ENTRANCE_HINT, True)`
    """
    ok, _why = can_enter(actor)
    if not ok:
        return '（……你进不去。）', False
    return ENTRANCE_HINT, True


# ---------------------------------------------------------------------------
#  3. 问答护栏 —— "两条线都接"
# ---------------------------------------------------------------------------

#: ★★★ 「先按原作正常回答」的那一条线的内容。
#: 用户口径：「让他们**先正常回答 niko 在原作里描述的那样**」。
#: ★ 取自 OneShot 里 Niko 对自己家乡的描述（原作语气，非我编造的场景细节）：
#:   Niko 说过他要**回家**、家里**在等**他、他家乡是个**有太阳的、温暖**的地方。
#: ⚠️ 这段是"人设线"的**兜底文案**；真正的回答仍应优先走人设 AI
#:   （`assets/npc/persona/*.txt`）。这里给的是"AI 不可用时"的诚实降级，
#:   以及"什么是'正常回答'"的**判据锚点**。
PERSONA_LINE = ('Niko 的家在很远的地方，那里有太阳，很暖和。'
                '他说过家里有人在等他回去。')

#: ★★★ 触发"屏蔽"的追问标记（第 **2** 次及以后的追问）。
#: ★ 用户口径：「**如果继续追问**那就回答「内容以屏蔽」」⇒ 第一次正常答，
#:   之后任何**再次追问**都切到屏蔽语。所以本模块记的是"这一轮是第几次问"。
FOLLOWUP_THRESHOLD = 2


def niko_home_reply(times_asked):
    """按"这是第几次问 Niko 家"给出回答。返回 `(text, is_blocked)`。

    · 第 1 次（`times_asked <= 1`）⇒ **人设线**：按原作正常回答（`PERSONA_LINE`）
    · 第 2 次及以后            ⇒ **护栏线**：`BLOCKED_REPLY`（「内容以屏蔽」）

    ★ 判据锚点 = `times_asked`（调用方维护的计数器），**不猜语义**。
      用户说的"继续追问"= 第二次及以后 —— 把它落成一个**明确的数**，
      而不是"看起来像追问就屏蔽"这种无法回归的模糊判断。

    ★ `times_asked` 非法（None / 非数）⇒ 当作**第一次**（人设线）。
      保守侧理由：宁可多给一次诚实回答，也不要因为一个坏计数把用户
      一上来就怼"内容以屏蔽"——后者观感极差。
    """
    try:
        n = int(times_asked)
    except (TypeError, ValueError):
        n = 1
    if n < 1:
        n = 1
    if n >= FOLLOWUP_THRESHOLD:
        return BLOCKED_REPLY, True
    return PERSONA_LINE, False


def normalize_ask_count(prev_count):
    """把"上次问过几次"推进一格（供调用方做计数器）。

    非法输入 ⇒ 当作 0 ⇒ 推进到 1（**第一次 = 人设线**）。永不抛。
    """
    try:
        n = int(prev_count)
    except (TypeError, ValueError):
        n = 0
    if n < 0:
        n = 0
    return n + 1


#: 「在问 Niko 的家」的关键词（任一命中即算）。★ 用来判"这一轮是不是在问。
#: ★★ 刻意**保守**：必须同时出现"家/家乡"这类**归属词**才认，
#:   避免"你回家了吗"这种普通句子被误判成在问 Niko 的老家。
_ABOUT_KEYS = ('niko', '尼科')
_HOME_KEYS = ('家', '家乡', 'home', '老家', 'hometown')


def looks_like_niko_home_question(text):
    """这一轮用户的话**是不是在问 Niko 的家**。

    ★ 判据 = 「提到 Niko」**且**「提到家/家乡」—— 两个都要。
      只提"家"不算（"你家在哪"可能是在问说话的人自己）；
      只提"Niko"不算（"Niko 在吗"跟他的老家无关）。

    ★ 大小写不敏感；非字符串 / 空 ⇒ `False`（不推进计数 = 不动护栏）。
    """
    if not isinstance(text, str) or not text:
        return False
    low = text.lower()
    has_niko = any(k in low for k in _ABOUT_KEYS)
    if not has_niko:
        return False
    return any(k in low for k in _HOME_KEYS)

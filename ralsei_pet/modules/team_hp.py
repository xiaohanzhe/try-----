# -*- coding: utf-8 -*-
"""队伍 HP 模型（第75轮 · B7）—— 城堡镇战斗系统的**前置**。

回答用户口径（第 75 轮裁定）
----------------------------
    「B7 队伍 HP 模型：**「可以先补」**」⇒ 先补模型，战斗系统再等。

为什么它必须**先**做（而不是跟战斗系统一起做）
--------------------------------------------
第 48 轮做道具/背包时，道具效果表里有一整类效果是**治疗 / 复活**：

    `case 1: scr_healitem(charselect, 40)`      —— 回 40
    `case 2: reviveamt = ceil(maxhp/2); ...`    —— 复活，回半血
    `case 4: scr_healitem(charselect, 70)`      —— 回 70
    ……

这些效果的**语义**（"回多少算满""血满了会怎样""死了怎么算"）全部落在
"队伍有没有 HP 这个概念"上。第48轮把它们做成了"效果编号"，
但**没有 HP 这个落点** —— 所以那一批效果至今是"报了数字、没处生效"。
本轮补上落点，道具效果才有地方真正生效。

★ 原作依据（**逐条**，全部来自已转储的 GML，`_evidence/gml/`）
--------------------------------------------------------------
1. **两条数组、按角色 id 索引**（不是按站位）：

       global.hp[global.char[global.charselect]]
       global.maxhp[global.char[global.charselect]]

   —— `ch1.scr_itemuse.gml:45` / `obj_savepoint_Other_10.gml:115`。
   ⚠️ 这两个数组的**下标是角色 id**（`global.char[]` 的取值），
      `global.char[]` 才是"第几个站位是谁"。本项目早期把两者混过一次，见下。

2. **角色 id 取值**（`ch1.scr_itemuse.gml:13~20`）：

       global.char[i] == 2  ⇒ 那是 Susie
       global.char[i] == 3  ⇒ 那是 Ralsei

   ⇒ **2 = Susie、3 = Ralsei**，1 = Kris（唯一没在转储里显式出现的那个，
     但 `global.char[0]` 恒为主控 ⇒ 由 `charselect == 0` 那一支反推）。
   ⚠️ **本模块用"名字"而不是这些魔法数字**：数字是原作的内存布局，
      搬过来只会到处是"2 是苏西、3 是雷尔赛"的注释。见 `ORIGINAL_CHAR_IDS`
      保留对照（但**不进逻辑**）。

3. **治疗是"封顶"，不是"溢出浪费"**（`gml_GlobalScript_scr_healitemspell.gml:15~21`
   与 `gml_GlobalScript_scr_healallitemspell.gml:17~23`，两处逐字相同）：

       if (global.hp[global.char[myself]] >= global.maxhp[global.char[myself]]) {
           with (dmgwr) { specialmessage = 3; }
       }

   ⇒ **满血时给治疗，要有一个"已经满了"的信号**（原作走的是 `specialmessage = 3`）。
      本模块把它变成一个显式的返回值（`heal()` 回 `0` 且 `full_before=True`），
      而不是静默吞掉 —— "静默吞掉"会让上层以为"治了"，实际什么都没发生。

   ⚠️ **引用纪律**（本项目踩过的坑，写在这里免得后人重复）：
      `_evidence/gml/` 下同名文件有**两代** —— `gml_GlobalScript_scr_*.gml`（有函数体，
      **真转储**）与 `gml_Script_scr_*.gml`（内容是 `// DECOMPILE FAILED`，**空壳**）。
      上面这条判据**只在真转储那一代里**；`scr_healitem_all` / `scr_healallitemspell`
      的**空壳代**存在，但**不含**这段代码。引错代 = 引了等于没引。
      `check75b` 的 A1/A1n 判据专门锁死这个陷阱。

4. **复活 = 回半血**（`ch1.scr_itemuse.gml:45`）：

       reviveamt = ceil(global.maxhp[global.char[global.charselect]] / 2);

   ⇒ 复活量 = `ceil(maxhp / 2)`。这是**原作明确写的**，照抄。

5. **睡觉/存档点回满**（`obj_savepoint_Other_10.gml:113~119`）：

       for (i = 0; i < 4; i += 1) {
           if (global.hp[i] < global.maxhp[i]) { global.hp[i] = global.maxhp[i]; }
       }

   ★ 注意这一处用的是**下标 i（0..3）**，而不是 `global.char[i]` ——
     与第 1 条**不一致**。这是原作的既有写法（存档点这条循环直接按下标遍历），
     本项目**不改原作**：`restore_all()` 语义 = "把每个已在场的角色回满"，
     实现走名字集合，结果一致但不复制那个下标歧义。

   ★★ **同一个"全队遍历"在原作里有三处、上界各不相同**（原文实测）：

       `scr_healitem_all`      → `for (i = 0; i < chartotal; i += 1)`
       `scr_healallitemspell`  → `for (i = 0; i < 3;        i += 1)`
       `obj_savepoint_Other_10`→ `for (i = 0; i < 4;        i += 1)`

     三个数（`chartotal` / `3` / `4`）**不一样**，而且第一处按下标、
     另两处取 `global.charinstance[i]`。⇒ **这是原作既有状态，不是 bug**，
     更不许"顺手统一"。本模块一律**走名字集合**（`self.members()`），
     所以不依赖任何一个上界 —— `check75b` 的 A4 判据把这三个值显式记下来，
     一旦证据被改动（比如有人"修"成一致）就会报红，逼人回来重审。

★ 数值从哪来（**诚实登记**）
----------------------------
`global.maxhp` 的**具体数值**写在 `obj_herokris` / `obj_herosusie` / `obj_herokris`
的 Create 事件里，而**这几个对象至今没有转储**（第49/55轮已登记，
属"素材补采一轮"B15 的范围）。

⇒ 本模块的 `DEFAULT_MAX_HP` 是**产品口径**（明确标注），不是原作数值：
   · 取了 Deltarune 里三名主角**开局**的常见量级（Kris 90 / Susie 100 / Ralsei 80，
     这是原作队伍面板上能看到的那三个数）；
   · **但**：数值一旦可由 `_stats.json`（将来补采）覆盖，就必须以那边的为准 ——
     所以 `TeamHP.from_stats()` 留了口子，`DEFAULT_MAX_HP` 只是**兜底**。
   · ⚠️ 任何"这就是原作数值"的说法，在本轮是**假的**；登记为产品口径。

零依赖纪律（🔴 与 companion / scene_system / item_system 同源）
--------------------------------------------------------------
本模块**禁 import Qt、禁 import 任何项目内模块**（只准标准库）。
理由与本项目其它零依赖模块一致：`main.py` 在 import 期就会建控制器，
回头 import 项目内模块会把「初始化环」接上（已踩 4 次，症状是 import 期直接崩、零输出）。
⇒ 本文件只准 `logging` / `math`。
"""
import logging

_log = logging.getLogger(__name__)

# ===========================================================================
#  常量
# ===========================================================================

WORLD_LIGHT = 'light'
WORLD_DARK = 'dark'

#: ★ 原作内存布局里的角色编号 —— **只作对照，不进逻辑**。
#: 出处：`ch1.scr_itemuse.gml:13~20`（2=Susie / 3=Ralsei）+ `charselect==0` 的主力支（1=Kris）。
#: ⚠️ 为什么留着它：将来若要从"原作的存档结构"导入，必须知道这套编号；
#:   但产品内部一律用**名字**（下面 `SLOT_ORDER`），免得到处是魔法数字。
ORIGINAL_CHAR_IDS = {
    'kris': 1,
    'susie': 2,
    'ralsei': 3,
}

#: ★ 产品内部用的队伍顺序 —— 照抄原作 `global.char[0..2]` 的**站位序**
#: （主控在前，`ch1.scr_itemuse.gml` 里 Ralsei 恒在 `ralpos`、随队的第三人位）。
#: ⚠️ 用名字而不是 id：与 `npc_registry` / `npc_bodies` 同一套 id 体系。
SLOT_ORDER = ('kris', 'susie', 'ralsei')

#: ★ **产品口径**（**非原作数值**）：三名主角的兜底最大 HP。
#: 真源应当是 `obj_hero*.Create`（**至今未转储**，见 `_缺 4 项`）。
#: ⇒ 这只是"补采之前能跑起来"的兜底，`from_stats()` 一来就让位。
DEFAULT_MAX_HP = {
    'kris': 90,
    'susie': 100,
    'ralsei': 80,
}

#: 复活回复量 = 最大值的这个比例 —— ★ 照抄 `ch1.scr_itemuse.gml:45`
#: （`ceil(maxhp / 2)`）。1/2 不是随手取的。
REVIVE_RATIO = 0.5

#: 一个角色的血量下限/状态。
HP_MIN = 0


class HpResult(object):
    """一次血量变更的结果（显式、可审计）。

    ★ 为什么不只返回新血量：上层真正需要区分的是**"这次操作有没有真的产生效果"** ——
      满血时喂药、给死人说"回血"、给不存在的角色回血，这三件事都必须**能分辨**，
      否则 UI 只能一律报"好了"（第48轮那批"报了数字没处生效"的效果表就是前车之鉴）。
    """

    __slots__ = ('char_id', 'before', 'after', 'max_hp', 'delta', 'full_before', 'ok')

    def __init__(self, char_id, before, after, max_hp, delta, full_before, ok):
        self.char_id = char_id
        self.before = before
        self.after = after
        self.max_hp = max_hp
        self.delta = delta            #: **实际**变化量（可能 < 请求量，见"封顶"）
        self.full_before = full_before  #: 操作前是否已满血（对应原作 specialmessage=3）
        self.ok = ok                  #: 是否真的产生了变化

    def __iter__(self):
        return iter((self.char_id, self.before, self.after, self.max_hp,
                     self.delta, self.full_before, self.ok))

    def __repr__(self):
        return ('HpResult(%s %d→%d/%d delta=%+d full_before=%s ok=%s)'
                % (self.char_id, self.before, self.after, self.max_hp,
                   self.delta, self.full_before, self.ok))


def clamp_hp(value, max_hp):
    """把血量钳进 `[0, max_hp]`。非法输入按 0；`max_hp <= 0` ⇒ 回 0。"""
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = 0
    try:
        m = int(max_hp)
    except (TypeError, ValueError):
        m = 0
    if m <= 0:
        return 0
    return max(HP_MIN, min(m, v))


def revive_amount(max_hp):
    """复活回复量 = `ceil(max_hp * REVIVE_RATIO)` —— **逐字照抄**原作的 `ceil(maxhp/2)`。

    ★ 用 `math.ceil` 而不是 `int(maxhp/2)`：原作是 `ceil`，
      差异只在奇数 maxhp 上（90/2=45 vs 91/2=45.5→46），但**必须照抄**，
      否则将来对着原作算账面数字时会对不上。
    """
    import math
    try:
        m = int(max_hp)
    except (TypeError, ValueError):
        m = 0
    if m <= 0:
        return 0
    return int(math.ceil(m * REVIVE_RATIO))


class TeamHP(object):
    """一支队伍的 HP 台账。**纯数据 + 纯函数式变更**（无 Qt、无 IO、无时间）。

    一个实例 = 一支队伍（本项目目前就是 `SLOT_ORDER` 那三人，但**不写死**：
    允许只加一部分人 —— 房间里可能只有两个人跟着）。
    """

    def __init__(self, members=None, stats=None):
        """`members` = 要建台账的角色 id 序列（缺省 = `SLOT_ORDER`，但只建注册表里有的）。

        `stats` = `{char_id: {'maxhp': int, 'hp': int}}`（可选）。给的时候以它为准，
        不给则用 `DEFAULT_MAX_HP` 兜底（见模块 docstring 的"数值从哪来"）。
        """
        if members is None:
            members = SLOT_ORDER
        self._max = {}
        self._hp = {}
        stats = stats or {}
        for cid in members:
            if not cid:
                continue
            st = stats.get(cid) or {}
            m = st.get('maxhp')
            if m is None:
                m = DEFAULT_MAX_HP.get(cid, 0)
            try:
                m = int(m)
            except (TypeError, ValueError):
                m = 0
            if m <= 0:
                continue                     # 没登记 = 不建这条（宁可没有，也不建个 0 血的）
            self._max[cid] = m
            h = st.get('hp')
            self._hp[cid] = clamp_hp(m if h is None else h, m)

    # -------- 读口 --------

    def members(self):
        """已在册的角色 id（按 `SLOT_ORDER` 的序，不在册的跳过）。"""
        return tuple(c for c in SLOT_ORDER if c in self._max)

    def has(self, char_id):
        return char_id in self._max

    def max_hp(self, char_id):
        return self._max.get(char_id, 0)

    def hp(self, char_id):
        return self._hp.get(char_id, 0)

    def is_full(self, char_id):
        """★ 对应原作那条 `hp >= maxhp` 判据（`scr_healitem_all` 的 `specialmessage=3`）。"""
        if char_id not in self._max:
            return False
        return self._hp[char_id] >= self._max[char_id]

    def is_dead(self, char_id):
        """血量归零 = 倒下。⚠️ 本项目**没有"战斗死亡"**（战斗系统未做），
        这里的 `is_dead` 只表示"血是 0"，供道具/复活判定用。"""
        if char_id not in self._max:
            return False
        return self._hp[char_id] <= HP_MIN

    def any_dead(self):
        return any(self.is_dead(c) for c in self.members())

    def all_dead(self):
        ms = self.members()
        return bool(ms) and all(self.is_dead(c) for c in ms)

    def describe(self):
        """**仅供日志/调试**（这里才有一串数值）。"""
        return ' '.join('%s=%d/%d' % (c, self._hp[c], self._max[c])
                        for c in self.members())

    def to_dict(self):
        """序列化（`{char_id: {'hp':..,'maxhp':..}}`）—— 键序固定，便于逐字比对。"""
        return {c: {'hp': self._hp[c], 'maxhp': self._max[c]}
                for c in self.members()}

    @classmethod
    def from_stats(cls, stats, members=None):
        """从一份 `{char_id: {'hp','maxhp'}}` 建台账 —— 将来 `_stats.json` 补采后走这里。

        ★ 只认这份数据里**有的**人（不凭空补 `DEFAULT_MAX_HP`）：
          外部数据在场时它就是唯一真源，不许被兜底值污染（本项目最贵的坑）。
        """
        if not stats:
            return cls(members=members, stats=None)
        ids = [c for c in (members or SLOT_ORDER) if c in stats]
        ids += [c for c in stats if c not in ids]     # 数据里有、名单里没有的也建
        return cls(members=ids, stats=stats)

    # -------- 写口（全部返回 `HpResult`，不静默） --------

    def heal(self, char_id, amount):
        """回血。★ **封顶**（`scr_heal` 语义），返回实际变化量。

        满血时：`full_before=True` 且 `ok=False`、`delta=0`
        —— **不静默吞掉**（原作在这一刻会走 `specialmessage = 3`，
           上层据此可以说"已经满了"，而不是看起来治了）。
        """
        if char_id not in self._max:
            return HpResult(char_id, 0, 0, 0, 0, False, False)
        m = self._max[char_id]
        before = self._hp[char_id]
        if before >= m:
            return HpResult(char_id, before, before, m, 0, True, False)
        try:
            amt = int(amount)
        except (TypeError, ValueError):
            amt = 0
        if amt < 0:
            amt = 0
        after = clamp_hp(before + amt, m)
        self._hp[char_id] = after
        return HpResult(char_id, before, after, m, after - before, False,
                        after != before)

    def damage(self, char_id, amount):
        """掉血。★ 下钳 0（**不出现负血**），返回实际变化量（`delta` 为负）。"""
        if char_id not in self._max:
            return HpResult(char_id, 0, 0, 0, 0, False, False)
        m = self._max[char_id]
        before = self._hp[char_id]
        try:
            amt = int(amount)
        except (TypeError, ValueError):
            amt = 0
        if amt < 0:
            amt = 0
        after = clamp_hp(before - amt, m)
        self._hp[char_id] = after
        return HpResult(char_id, before, after, m, after - before,
                        before >= m, after != before)

    def revive(self, char_id):
        """复活 = 回 `ceil(maxhp*REVIVE_RATIO)` —— **照抄**原作 `scr_itemuse` 的复活分支。

        ⚠️ 语义边界：**只对"倒下的"人生效**。给活人复活 ⇒ `ok=False`、血量不动
          （否则"复活药"会变成回血药，那是另一条效果）。
        """
        if char_id not in self._max:
            return HpResult(char_id, 0, 0, 0, 0, False, False)
        m = self._max[char_id]
        before = self._hp[char_id]
        if before > HP_MIN:
            return HpResult(char_id, before, before, m, 0, before >= m, False)
        after = clamp_hp(revive_amount(m), m)
        self._hp[char_id] = after
        return HpResult(char_id, before, after, m, after - before, False,
                        after != before)

    def heal_all(self, amount):
        """全队回血（照 `scr_healallitemspell` 的"逐个"语义，**不含复活**）。→ 结果列表。"""
        return [self.heal(c, amount) for c in self.members()]

    def restore_all(self):
        """全队回满 —— 对应 `obj_savepoint_Other_10.gml:113~119`（存档点/睡觉）。

        ★ 只回"没满"的（与原作那个 `if (hp < maxhp)` 一致）⇒ 已经是满的人
          `ok=False`（"没动过"），便于上层区分"睡了但本来就没伤"。
        """
        out = []
        for c in self.members():
            if self.is_full(c):
                out.append(HpResult(c, self._hp[c], self._hp[c], self._max[c],
                                    0, True, False))
            else:
                before = self._hp[c]
                self._hp[c] = self._max[c]
                out.append(HpResult(c, before, self._max[c], self._max[c],
                                    self._max[c] - before, False, True))
        return out


# ---------------------------------------------------------------- 道具备注
#
# 第48轮的效果表里那一类"治疗 / 复活"，本模块就是它们的落点。对应关系：
#   `scr_itemuse` case 1  (heal 40)  → TeamHP.heal(char, 40)
#   `scr_itemuse` case 2  (revive)   → TeamHP.revive(char)     [= ceil(maxhp/2)]
#   `scr_itemuse` case 4  (heal 70)  → TeamHP.heal(char, 70)
#   `scr_itemuse` case ?  (heal 20)  → TeamHP.heal(char, 20)
# ⚠️ **本轮不接线到 `item_system`**：效果表按 id 存的是数字，而"谁吃这个道具"
#    （`charselect`）是战斗/菜单侧的上下文，那边还不存在。
#    本模块先提供**能力**，接线留到战斗系统那一轮（与用户"先补模型"的口径一致）。
#    ⇒ 明确登记：`wired=False`。


#: 接线台账（诚实判据）：本模块**尚未**接到产品链路。
WIRING = {
    'module': 'team_hp',
    'round': 75,
    'status': 'model_only',
    'wired': False,
    'not_yet': [
        'item_system 的治疗/复活效果尚未调用本模块（缺"谁吃"的上下文）',
        '战斗系统本身未做（用户口径：先补模型）',
        'DEFAULT_MAX_HP 是产品口径，等 obj_hero* 补采后由 _stats.json 取代',
    ],
}

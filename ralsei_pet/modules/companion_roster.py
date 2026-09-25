# -*- coding: utf-8 -*-
"""伙伴调度层 —— 名册 / 自主对话轮转 / 跟随三态（L3）。

回答用户这条需求（第 46 轮）：
    「一般来说并不会有多个 AI 同时运行的场景，当然，如果可以的话，
      多个一起运行也看不出端倪那也行」
    「要让他们能有自主互相聊天的功能，但不会导致 AI 之间分不清是谁和谁说话」
    「跟随系统这类的按原作的就行，还是跟随 kris 如果 kris 在的话，
      当然，也可自主行动，只是在需要统一行动时跟随」

★ 本层的三块，对应原作的三个机制
----------------------------------
| 本层 | 原作 | 关键数值 |
|---|---|---|
| `Roster`（名册） | `scr_setparty(arg0, arg1)` + `scr_findactor(name)` | **2 个队友位** |
| `ChatScheduler`（轮转调度） | 原作没有（原作是单人剧情，靠剧本决定谁说话） | **本项目扩展** |
| `step_follow`（跟随） | `scr_makecaterpillar` + `obj_caterpillarchara` | **滞后 12/24 帧、缓冲 25** |

★ 「看不出端倪」是怎么做到的（用户口径的原话）
-----------------------------------------------
**同一时刻最多只有一个伙伴在生成。** `ChatScheduler.tick()` 在 `busy` 时直接返回
`None`，没有任何路径能同时吐出两个 speaker ⇒ 峰值内存/CPU = 单个 7B，
对外表现与单宠完全一致。将来若要真并行，只需把 `_busy` 换成"每伙伴一个 busy 位"
+ 一个串行化输出队列，**对外行为不变** —— 现在的设计不堵死将来。

★ 零依赖（🔴 与 companion / companion_dialog 同源）
L3 允许 import L1/L2（它俩都是零依赖），但**仍禁 Qt**。
`companion` / `companion_dialog` 的 import 不会接上初始化环
（环来自"回头 import 有业务反向依赖的模块"，如 logger_utils / data_store）。
"""
import logging

from companion import (MAX_COMPANIONS, FACING_DEFAULT, FOLLOW_FAR_THRESHOLD,
                       FollowMode, Companion, normalize_id, is_blank_id, distance)
from companion_dialog import Message, DialogueLog

_log = logging.getLogger(__name__)

#: 自主对话至少要几个人才叫"互相聊天"（1 个人是"跟用户聊天"，走既有对话链路）。
MIN_TALKERS = 2

#: 「自创」两次自主发言之间的最小间隔（秒）—— 防刷屏。原作没有这个概念。
DEFAULT_MIN_GAP = 8.0

#: 「自创」一轮话题最多往返几次（超过就停，**不硬凑** —— 用户明确
#: 「不要为显得勤快而说话」是既有口径，见 memory §5 工作方式）。
DEFAULT_MAX_TURNS = 6

#: 「自创」连续生成失败多少次后停手（**反活锁**：模型挂了不许无限重试）。
MAX_CONSECUTIVE_FAILURES = 3


# ===========================================================================
#  名册
# ===========================================================================

class Roster(object):
    """伙伴名册 —— 名字（含别名）→ 伙伴实例。

    ★ 主键是**字符串 id**，不是序号（同原作：`scr_anyface` 比字符串、
    `c_actormoveparty` 用 `scr_findactor("kris")`）。
    ★ 槽位（slot）只决定**跟随滞后**（`12 + slot*12`），不是身份。
    """

    def __init__(self, slot_count=MAX_COMPANIONS):
        self.slot_count = int(slot_count)
        self._by_id = {}
        self._alias = {}                    # 归一名字 -> speaker_id
        self._slots = [None] * max(0, self.slot_count)

    # ---------------------------------------------------------------- 登记
    def add(self, companion):
        """登记一只伙伴。→ `(ok, reason)`。

        ★ **原子性**：任何一处冲突 ⇒ 整条不登记（不留下"半只登记好"的伙伴）。
        ★ **别名冲突必须报错**，不许"后者覆盖前者" —— 覆盖会让
        `resolve()` 悄悄指向另一只宠物，正是"分不清谁跟谁说话"的温床。
        """
        if not isinstance(companion, Companion):
            return False, 'not_companion:%r' % (type(companion).__name__,)
        sid = companion.speaker_id
        if sid in self._by_id:
            return False, 'duplicate_id:%s' % sid
        names = companion.names()
        conflicts = sorted({n for n in names
                            if n in self._alias and self._alias[n] != sid})
        if conflicts:
            return False, 'alias_conflict:%s' % ','.join(conflicts)
        self._by_id[sid] = companion
        for n in names:
            self._alias[n] = sid
        return True, ''

    # ---------------------------------------------------------------- 查询
    def resolve(self, name):
        """名字（含别名、大小写不敏感）→ 伙伴。找不到 ⇒ **`None`（绝不猜）**。"""
        n = normalize_id(name)
        if not n:
            return None
        sid = self._alias.get(n)
        if sid is None:
            return None
        return self._by_id.get(sid)

    def by_id(self, speaker_id):
        return self._by_id.get(normalize_id(speaker_id))

    def ids(self):
        """全部登记伙伴的 id 集合（`DialogueLog` 的 `known_ids` 用它）。"""
        return set(self._by_id)

    def alias_index(self):
        """`{归一名字: speaker_id}` 的副本（喂给 `companion_dialog.check_reply`）。"""
        return dict(self._alias)

    def display_map(self):
        """`{id: 显示名}`（喂给 `format_line` 的 `display=`）。"""
        return {sid: c.display_name for sid, c in self._by_id.items()}

    def __len__(self):
        return len(self._by_id)

    def __contains__(self, name):
        return self.resolve(name) is not None

    # ---------------------------------------------------------------- 上场
    def activate(self, names, leader_xy=None):
        """★ 对应原作 `scr_setparty(arg0, arg1)`。→ `(已激活, 未解析)`。

        · `names` 里的空位（`None` / `False` / `''`）**跳过**（对应 `arg0 = false`）；
        · 解析不出来的名字**如实报出**在第二个返回值里，**绝不静默忽略、
          也绝不拿"看起来像的"顶上**（同 scene_pathfind 的设计律 1）；
        · 槽位按**成功激活的顺序**分配（对应原作 `slot++` 写在 `if` 里面）；
        · 超过槽位数的名字进"未解析"（理由 `no_slot`）。
        """
        if isinstance(names, str):
            names = [names]
        activated, unresolved = [], []
        for raw in (names or ()):
            if raw is None or raw is False or is_blank_id(raw):
                continue
            c = self.resolve(raw)
            if c is None:
                unresolved.append((raw, 'not_found'))
                continue
            if c in activated:
                unresolved.append((raw, 'duplicate_in_request'))
                continue
            if len(activated) >= self.slot_count:
                unresolved.append((raw, 'no_slot'))
                continue
            activated.append(c)
        for i, c in enumerate(activated):
            c.slot = i
            if leader_xy is not None:
                # ★ 照抄原作：新进队的毛毛虫初始位置 = 主角当前位置（填满 25 帧缓冲）。
                c.reset_trace(leader_xy[0], leader_xy[1])
            else:
                # ★ 不给主角坐标 ⇒ 轨迹留空。**故意不填 (0,0)**：
                #   填了会让伙伴在头 `lag+1` 帧里"从 (0,0) 慢慢挪到主角身后"
                #   = 一个可见的穿屏漂移。留空 ⇒ 头 13 帧只是"还没开始跟"，
                #   从第 14 帧起从正确的滞后点开始动。
                _log.warning('activate：未提供 leader_xy ⇒ %s 的轨迹为空，'
                             '要等 %d 帧才开始跟随', c.speaker_id, c.follow_lag + 1)
        self._slots = list(activated) + [None] * (self.slot_count - len(activated))
        for raw, why in unresolved:
            _log.warning('activate：%r 没能上场（%s）', raw, why)
        return activated, unresolved

    def active(self):
        """当前在场伙伴（按槽位序）。"""
        return [c for c in self._slots if c is not None]

    def active_ids(self):
        return [c.speaker_id for c in self.active()]

    def deactivate_all(self):
        """清场（对应 `scr_losechar()` + `with (obj_caterpillarchara) instance_destroy();`）。"""
        n = len(self.active())
        self._slots = [None] * max(0, self.slot_count)
        return n

    def __repr__(self):
        return '<Roster 登记=%d 在场=%s>' % (len(self._by_id), self.active_ids())


# ===========================================================================
#  自主对话轮转调度（★ 「看不出端倪」的关键）
# ===========================================================================

class ChatScheduler(object):
    """轮转式自主对话调度。**任一时刻最多一个伙伴处于生成中。**

    用法::

        c = sched.tick(now)          # None = 现在不该有人说话
        if c is not None:
            ok, text = ask_model(c)              # 慢；这期间 tick 恒返回 None
            if ok: sched.finish(now, c.speaker_id)
            else:  sched.abort(now)

    ★ 三条不变量（都有正/负控制断言）：
      1. `tick()` 在 `busy` 时**恒**返回 `None`（不并发）；
      2. 下一个 speaker **绝不等于**上一个 speaker（⇒ 天然 A↔B 往返，
         不出现"A 自问自答" —— 这正是既有 `_clean_ai_reply` 在单宠场景防的那类失真）；
      3. 任何失败路径（`abort` / `speaker_mismatch`）都**必须解锁**（不许永久卡死）。
    """

    def __init__(self, roster, min_gap=DEFAULT_MIN_GAP, max_turns=DEFAULT_MAX_TURNS,
                 topic_source=None, allow_solo=False):
        self.roster = roster
        self.min_gap = float(min_gap)
        self.max_turns = int(max_turns)
        self.allow_solo = bool(allow_solo)
        #: 「话题从哪来」的可插拔点（设计文档 §10.2 待拍板）。
        #: 给了就要求它返回非空话题才开口；默认 `None` = 不门控。
        self.topic_source = topic_source
        self._busy = False
        self._pending = None          # 正在等回复的 speaker_id
        self._last_from = None
        self._last_time = None
        self._turns = 0
        self._fail_count = 0
        self.mismatch_count = 0

    # ---------------------------------------------------------------- 状态
    @property
    def busy(self):
        return self._busy

    @property
    def pending_id(self):
        return self._pending

    @property
    def turns(self):
        return self._turns

    @property
    def last_from(self):
        return self._last_from

    @property
    def fail_count(self):
        """连续失败次数（>= `MAX_CONSECUTIVE_FAILURES` 时 `tick()` 会停手）。"""
        return self._fail_count

    # ---------------------------------------------------------------- 节拍
    def tick(self, now):
        """该谁说话了？→ `Companion` 或 `None`。**调一次就会置 busy。**"""
        if self._busy:
            return None
        if self._fail_count >= MAX_CONSECUTIVE_FAILURES:
            _log.warning('自主对话连续失败 %d 次 ⇒ 停手（反活锁）', self._fail_count)
            return None
        members = self.roster.active()
        if len(members) < (1 if self.allow_solo else MIN_TALKERS):
            return None
        if self._turns >= self.max_turns:
            return None
        if self._last_time is not None and (float(now) - self._last_time) < self.min_gap:
            return None
        if self.topic_source is not None:
            try:
                topic = self.topic_source()
            except Exception:
                _log.exception('topic_source 抛异常 ⇒ 本轮不开口')
                return None
            if not topic:
                return None
        cand = self._next_speaker(members)
        if cand is None:
            return None
        self._busy = True
        self._pending = cand.speaker_id
        return cand

    def _next_speaker(self, members):
        """轮转：从上一位的**下一位**开始找第一个 `!= 上一位` 的人。"""
        start = 0
        if self._last_from is not None:
            for i, c in enumerate(members):
                if c.speaker_id == self._last_from:
                    start = i + 1
                    break
        n = len(members)
        for k in range(n):
            c = members[(start + k) % n]
            if c.speaker_id != self._last_from:
                return c
        return None

    # ---------------------------------------------------------------- 收束
    def finish(self, now, from_id=None):
        """生成结束（**成功或失败都要调**）。→ `(ok, reason)`。

        `from_id` 是"实际说出话的人"。与 `tick()` 返回的人不一致 ⇒ 记
        `speaker_mismatch`（**张冠李戴的兜底报警**），但**仍然解锁并推进轮转**
        —— 因为卡死比错一次更严重（设计律 2）。
        """
        if not self._busy:
            return False, 'not_busy'
        pending = self._pending
        self._busy = False
        self._pending = None
        reason = ''
        if from_id is not None:
            got = normalize_id(from_id)
            if got != pending:
                self.mismatch_count += 1
                reason = 'speaker_mismatch:%s!=%s' % (got, pending)
                _log.warning('实际说话人 %r != 调度预期 %r ⇒ 记一次 mismatch', got, pending)
        self._last_from = pending
        self._last_time = float(now)
        self._turns += 1
        self._fail_count = 0
        return (reason == ''), reason

    def abort(self, now, advance=False):
        """生成失败 / 被打断：**解锁**。→ `True` 表示确实解锁了。

        `advance=False`（默认）⇒ 不推进轮转，下次还是同一位开口
        （**不罚下一个人**：失败是模型的事，不是他的事）。
        """
        if not self._busy:
            return False
        self._busy = False
        self._pending = None
        self._fail_count += 1
        if advance and self._last_from is not None:
            self._last_time = float(now)
        return True

    def reset(self, keep_topic=True):
        """清空轮转状态（`keep_topic=False` 时连话题计数器一起归零）。"""
        self._busy = False
        self._pending = None
        self._last_from = None
        self._last_time = None
        self._fail_count = 0
        if not keep_topic:
            self._turns = 0
        return self

    def __repr__(self):
        return '<ChatScheduler busy=%s pending=%s last=%s turns=%d/%d>' % (
            self._busy, self._pending, self._last_from, self._turns, self.max_turns)


# ===========================================================================
#  跟随（★ 毛毛虫：走主角走过的路，不独立寻路）
# ===========================================================================

def step_follow(roster, leader_x, leader_y, facing=FACING_DEFAULT):
    """每帧调一次。→ 本帧真正移动了的伙伴数。

    做两件事（顺序不能反）：

      ① **把主角当前位置压进所有在场伙伴的轨迹** —— 全员共享同一条轨迹，
         因为原作的毛毛虫 `parent = obj_mainchara`，大家跟的是同一个主角；
      ② 处于 `FOLLOW` / `RALLY` 的伙伴取「滞后 `effective_lag` 帧」那一点
         作为自己的新位置。

    ★ 为什么不做独立寻路：跟随者走的是**主角走过的路** ⇒ 天然不撞墙、不卡住，
    且轨迹本身就是一条自然曲线（满足用户"路线别太死板"的口径）。
    第 45 轮的 `scene_walk` 仍有用 —— 它服务 `FREE` 模式的自主移动
    与 `RALLY` 时"自己走到主角附近"（那时需要真寻路，属 P3 接线）。
    """
    members = roster.active()
    for c in members:
        c.push_trace(leader_x, leader_y, facing)
    moved = 0
    for c in members:
        if c.mode not in (FollowMode.FOLLOW, FollowMode.RALLY):
            continue
        pt = c.sample_at(c.effective_lag)
        if pt is None:
            continue
        c.x, c.y, c.facing = pt.x, pt.y, pt.facing
        moved += 1
    return moved


def select_mode(companion, leader_present, leader_moving, dist=None,
                need_rally=False, far_threshold=None):
    """★ 三态决策（用户口径「也可自主行动，只是在需要统一行动时跟随」）。

    决策顺序（即优先级）::

        主角不在场                 → FREE   （没有人可跟）
        need_rally（切场景/要对话） → RALLY  （统一行动，贴更紧）
        主角在动 且 距离未知/超阈值  → FOLLOW （需要跟上）
        其余                       → FREE   （自主行动，常态）

    ★ 默认是 `FREE` —— 这是**用户口径的直接翻译**，不是原作的默认
    （原作里队友永远在队列里，没有"自主行动"这回事）。
    `dist=None` 且主角在动 ⇒ 按 FOLLOW 处理（"不知道多远"时，
    跟上比掉队安全）。
    """
    if far_threshold is None:
        far_threshold = FOLLOW_FAR_THRESHOLD
    if not leader_present:
        mode = FollowMode.FREE
    elif need_rally:
        mode = FollowMode.RALLY
    elif leader_moving and (dist is None or float(dist) > float(far_threshold)):
        mode = FollowMode.FOLLOW
    else:
        mode = FollowMode.FREE
    companion.set_mode(mode)
    return mode


def apply_modes(roster, leader_xy, leader_moving, need_rally=False,
                far_threshold=None):
    """对全队跑一遍 `select_mode`。→ `{speaker_id: mode}`。"""
    if leader_xy is None:
        leader_present = False
        lx = ly = 0.0
    else:
        leader_present = True
        lx, ly = float(leader_xy[0]), float(leader_xy[1])
    out = {}
    for c in roster.active():
        dist = None
        if leader_present:
            dist = distance((c.x, c.y), (lx, ly))
        out[c.speaker_id] = select_mode(
            c, leader_present, leader_moving, dist=dist,
            need_rally=need_rally, far_threshold=far_threshold)
    return out


# ===========================================================================
#  门面：把三层串起来的一站式入口（P3 接线前先用它做端到端验收）
# ===========================================================================

class CompanionStage(object):
    """L1+L2+L3 的薄门面 —— 「多宠物同桌」的最小可用组合。

    它**不做任何 IO**（不读人设文件、不调模型、不画 UI）。
    P3 的接线层拿它当骨架，把人设/模型/UI 挂上来即可。
    """

    def __init__(self, roster=None, slot_count=MAX_COMPANIONS, **sched_kw):
        self.roster = roster if roster is not None else Roster(slot_count)
        self.log = DialogueLog(
            known_ids=self.roster.ids(),
            alias_map=self.roster.alias_index(),
            display=self.roster.display_map())
        self.scheduler = ChatScheduler(self.roster, **sched_kw)

    def add(self, companion):
        """登记一只伙伴，并**自动**让 `DialogueLog` 认识它（否则它的消息会被拒）。"""
        ok, reason = self.roster.add(companion)
        if ok:
            self.refresh_log_index()
        return ok, reason

    def refresh_log_index(self):
        """名册变动后同步给 `DialogueLog`（否则新伙伴的消息会被判 `unknown_from`）。"""
        self.log.known_ids = self.roster.ids()
        self.log.alias_map = self.roster.alias_index()
        self.log.display = self.roster.display_map()
        return self.log

    def say(self, from_id, text, to_id=None, **kw):
        """收一条消息：校验 → 入库。→ `(ok, reason)`。"""
        msg = Message(text=text, from_id=from_id, to_id=to_id, **kw)
        return self.log.append(msg)

    def tick(self, now):
        """该谁说话了？（不并发）。"""
        return self.scheduler.tick(now)

    def done(self, now, from_id=None):
        return self.scheduler.finish(now, from_id)

    def context(self, n=10):
        return self.log.context_lines(n)

    def step(self, leader_xy, leader_moving=False, need_rally=False,
             far_threshold=None):
        """每帧的「三态决策 + 跟随步进」（`leader_xy=None` = 主角不在场）。"""
        apply_modes(self.roster, leader_xy, leader_moving,
                    need_rally=need_rally, far_threshold=far_threshold)
        if leader_xy is None:
            return 0
        return step_follow(self.roster, leader_xy[0], leader_xy[1])

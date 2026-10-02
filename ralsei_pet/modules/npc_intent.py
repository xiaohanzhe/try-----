# -*- coding: utf-8 -*-
"""NPC 自主生活 · 层1：**意图层**（零依赖，只准标准库）。

用户口径（逐字，第77轮）
------------------------
> 「人物之间也可以自己动，也就是，**他们生活是生活，我和他们只是朋友**，
>  而不是主导人，也就是**不会因为缺少一个人哪怕是我他们就不生活了**，OK？还有，
>  像是**去哪？找谁？干什么？生活规划**这类的事也是由**各自的 AI 决定**，
>  并且**不是一到晚上就必须回自己家**，也可以选择**在朋友那睡觉**，但这也是 AI 决定，
>  反正就是，**人味，人味，还 tm 是人味**，重要的事情说三遍！」

这个模块回答四个问题
--------------------
| 问题 | 谁回答 |
|---|---|
| **去哪** | `Intent.dest_scene` |
| **找谁** | `Intent.who` |
| **干什么** | `Intent.what` |
| **生活规划** | `Plan`（今天的日程 + 昨晚睡哪 + 明天想去哪） |

★★ 与"用户"的关系（L2）
-------------------------
`decide()` 的入参里**根本没有"用户在哪"** —— 这是**刻意的**。
NPC 的意图只由 **他自己的人设 + 熟络度 + 场景特质 + 时间** 决定。
用户想见他，得**自己去那个场景**；用户不在，他照样过这一天。

⇒ 判据：`decide()` 的签名里**不许出现** `pet` / `user` / `player` 之类参数。

★★★ 「人味」怎么落（L6，最高优先级）
--------------------------------------
**禁"整点必做 X"。** 三条机制：

1. **每角色固定种子**（`seed_for(npc_id)`）⇒ 不同人的一天**长得不一样**。
2. **时间段只是"倾向"，不是"开关"**：`_phase_bias()` 返回的是**权重**，
   进 `_weighted_pick()` 一起摇；任何选项在任何时段都**有非零概率**。
   ⚠️ 尤其：**夜里也可能出门**（"去朋友那睡"）、**白天也可能回家**。
3. **`jitter()`**：同一人同一个时段，**每次摇出来的结果可以不同**
   （用 `(seed, day, slot)` 会锁死 ⇒ 故意把 `slot` 换成**连续时间**）。

⇒ 判据：同一个人两天同一时刻的 `Intent` **不强制相同**（见 `check78`）。

零依赖纪律（对齐 `companion*` / `npc_placement`）
--------------------------------------------------
* 顶层只 `import` 标准库（`random` / `hashlib` / `collections`）；
* **零函数内 import**；
* **不 import 任何项目内模块**（连 `npc_life` 都不 import —— 熟络度**从入参拿**）。
"""
import collections
import hashlib
import random

# ---------------------------------------------------------------- 常量

#: 一天的时间段（**只是"倾向"的上下文，不是门禁**）。
#: ⚠️ 键名刻意用中性词，避免"晚上 = 回家"这种默认叙事。
PHASES = collections.OrderedDict((
    ('dawn', (5, 8)),       # 清晨
    ('day', (8, 17)),       # 白天
    ('dusk', (17, 21)),     # 傍晚
    ('night', (21, 29)),    # 夜里（29 = 次日 5 点，跨夜）
))

#: 意图动作表：`what` 的**全集**。中文名用于日志/调试。
#: ★ 刻意**不含** `sleep_here` —— 睡觉是"在哪过夜"，是 `dest_scene` 的事（L4）。
ACTIONS = collections.OrderedDict((
    ('wander', '随便走走'),
    ('visit_friend', '去找朋友'),
    ('go_home', '回自己那边'),
    ('visit_favorite', '去喜欢的地方'),
    ('explore_unknown', '去没去过的地方'),
    ('stay', '就待在原地'),
))

#: 「哪几类事需要朋友参与」—— 决定 `who` 是否非空。
SOCIAL_ACTIONS = ('visit_friend',)

#: 每种动作的**基础权重**（任何人）。★ 全是正数 ⇒ 任何动作在任何时段都有戏。
BASE_WEIGHTS = {
    'wander': 3.0,
    'visit_friend': 3.0,
    'go_home': 2.0,
    'visit_favorite': 2.5,
    'explore_unknown': 1.5,
    'stay': 1.0,
}

#: 场景特质 → 动作权重乘数。★ 只**调权**，不"开关"。
#: 例：`quiet` 的地方更想去、`crowded` 的地方更想找朋友。
TRAIT_WEIGHT_MUL = {
    'quiet': {'visit_favorite': 1.4, 'stay': 1.3, 'wander': 0.9},
    'crowded': {'visit_friend': 1.5, 'wander': 1.2, 'stay': 0.6},
    'dark': {'wander': 1.2, 'explore_unknown': 1.4, 'stay': 0.7},
    'ruined': {'explore_unknown': 1.5, 'wander': 1.2},
    'bright': {'visit_friend': 1.2, 'visit_favorite': 1.2},
    'cosmic': {'explore_unknown': 1.6, 'wander': 1.1},
}

#: 时段 → 动作权重乘数。★★★ **这是"人味"的关键**：
#: 夜里 `visit_friend` **仍然 > 0** ⇒ "在朋友那睡"是**可能**的（L4）；
#: 白天 `go_home` **也 > 0** ⇒ 不强制"白天必须在外"。
PHASE_WEIGHT_MUL = {
    'dawn': {'wander': 1.1, 'stay': 1.4, 'go_home': 1.1},
    'day': {'wander': 1.3, 'visit_friend': 1.2, 'explore_unknown': 1.2},
    'dusk': {'visit_friend': 1.4, 'go_home': 1.2, 'visit_favorite': 1.1},
    'night': {'go_home': 1.6, 'stay': 1.2, 'visit_friend': 1.1},   # ★ visit_friend 不许归零
}

#: 熟络度 → 去投奔朋友的门槛之上的加成。
FAMILIAR_FRIEND_BONUS = 3.0      # 熟人越熟越想去（乘在 visit_friend 上）
FAMILIAR_CAP = 1.0

#: 探索欲上限（别整天只去没去过的地方）。
EXPLORE_MAX = 1.8

DEFAULT_PLAN_DAYS = 1            # 规划只看今天（L5：下次决策读上次结果，不是排 7 天）

# ---------------------------------------------------------------- 时间


def phase_of(hour):
    """`hour`（0~23 的**浮点**，允许 24+ 表示跨夜）→ 时间段 id。

    ★ 任何输入都**有返回值**（越界取模），不抛 —— 意图层不该因为一个坏时间就崩。
    """
    try:
        h = float(hour) % 24.0
    except (TypeError, ValueError):
        h = 12.0
    for pid, (lo, hi) in PHASES.items():
        if lo <= h < hi or (hi > 24 and lo <= h + 24 < hi):
            return pid
    return 'day'


def phase_bias(phase):
    """该时段的权重乘数表（**只调权，不开关**）。"""
    return dict(PHASE_WEIGHT_MUL.get(phase) or {})


# ---------------------------------------------------------------- 种子


def seed_for(npc_id, salt=''):
    """**每角色固定种子**。

    ★ 同一个人**永远**得到同一个种子（跨天、跨进程都一样）⇒ 他的"品味"稳定；
      但 `jitter()` 会在种子之上叠**连续时间** ⇒ 每天/每刻仍可不同（L6）。
    """
    raw = ('ralsei.intent/1|%s|%s' % (npc_id or '', salt or '')).encode('utf-8')
    return int(hashlib.sha256(raw).hexdigest()[:12], 16)


def rng_for(npc_id, salt=''):
    """该角色的独立随机源（**不共享全局 `random`**）。

    ★ 用独立 `Random` 实例：一个人摇意图**不会**扰动别人的随机序列
      ⇒ 判据可复现，且"各自的人生"互不串味。
    """
    return random.Random(seed_for(npc_id, salt))


def jitter(npc_id, now, salt='', lo=0.0, hi=1.0):
    """基于 `(种子, 连续时间)` 的**确定性抖动** ∈ [lo, hi]。

    ★★ 刻意用**连续时间**而不是"第几个时间片"：
      时间片会把同一时段的所有决策**锁成同一个值**（那就成了新的"整点必做"）。
    """
    day = int(float(now) // 86400.0)
    frac = float(now) - day * 86400.0
    h = hashlib.sha256(
        ('%d|%.6f|%s|%s' % (day, frac, npc_id or '', salt or '')).encode('utf-8')
    ).hexdigest()
    u = int(h[:12], 16) / float(0x1000000000000)
    return float(lo) + u * (float(hi) - float(lo))


# ---------------------------------------------------------------- 权重与选择


def action_weights(npc_id, phase, traits=None, familiar=0.0, extra=None):
    """算出**这一拍**各动作的权重（正数，未归一）。

    `extra` 允许宿主注入额外乘数（例：某角色人设里写着"爱待在图书馆"）。

    ★ 任何一步都**只乘不禁** ⇒ 返回的表里**每一项都 > 0**
      （这正是"不出现整点必做"的结构保证）。
    """
    w = {k: float(v) for k, v in BASE_WEIGHTS.items()}

    # ① 时段倾向
    for k, mul in phase_bias(phase).items():
        if k in w:
            w[k] *= float(mul)

    # ② 场景特质
    for t in (traits or ()):
        for k, mul in (TRAIT_WEIGHT_MUL.get(t) or {}).items():
            if k in w:
                w[k] *= float(mul)

    # ③ 熟络度：越熟越想去找人
    try:
        fam = max(0.0, min(FAMILIAR_CAP, float(familiar)))
    except (TypeError, ValueError):
        fam = 0.0
    w['visit_friend'] *= (1.0 + FAMILIAR_FRIEND_BONUS * fam)

    # ④ 宿主注入
    for k, mul in (extra or {}).items():
        if k in w:
            try:
                w[k] *= float(mul)
            except (TypeError, ValueError):
                pass

    # ⑤ 下钳：任何一项都不许被乘成 0 或负（否则"永不发生"= 隐性整点必做）
    floor = 1e-6
    for k in list(w.keys()):
        if not (w[k] > floor):
            w[k] = floor
    return w


def weighted_pick(weights, rng):
    """按权重摇一个 key。非法/空表 ⇒ `None`（**不抛**）。"""
    try:
        items = [(k, float(v)) for k, v in (weights or {}).items() if float(v) > 0]
    except (TypeError, ValueError):
        return None
    if not items:
        return None
    total = sum(v for _, v in items)
    if not (total > 0):
        return None
    x = rng.random() * total
    acc = 0.0
    for k, v in items:
        acc += v
        if x < acc:
            return k
    return items[-1][0]


# ---------------------------------------------------------------- Intent


class Intent(object):
    """一次生活决策的结果：**去哪 + 找谁 + 干什么**。

    `dest_scene` 为 `None` 表示"不出门"（`what == 'stay'` 时必然如此）。
    `who` 只在 `SOCIAL_ACTIONS` 里非空。
    """

    __slots__ = ('what', 'dest_scene', 'who', 'why', 'at')

    def __init__(self, what, dest_scene=None, who=None, why='', at=0.0):
        self.what = what
        self.dest_scene = dest_scene
        self.who = who
        self.why = why
        self.at = float(at)

    @property
    def is_social(self):
        return self.what in SOCIAL_ACTIONS

    def to_dict(self):
        return collections.OrderedDict((
            ('what', self.what),
            ('dest_scene', self.dest_scene),
            ('who', self.who),
            ('why', self.why),
            ('at', self.at),
        ))

    @classmethod
    def from_dict(cls, d):
        d = d or {}
        return cls(d.get('what') or 'stay', d.get('dest_scene'), d.get('who'),
                   d.get('why') or '', d.get('at') or 0.0)

    def __repr__(self):
        return '<Intent %s -> %s who=%s>' % (self.what, self.dest_scene, self.who)


def decide(npc_id, now, *, phase=None, traits=None, familiar=0.0,
           home=None, favorites=None, reachable=None, friends=None,
           last=None, extra_weights=None, salt=''):
    """**替这个 NPC 决定这一拍干什么**（← 用户口径 L3：由各自的 AI 决定）。

    ★★ 签名里**没有** `pet` / `user` / `player`（L2 的结构保证）。

    参数
    ----
    home        : 他自己的场景 id（可以不在 `reachable` 里 ⇒ 那今晚回不去）
    favorites   : 他偏好的场景 id 列表（可空）
    reachable   : **现在真能去**的场景 id 列表（由 `scene_controller` 的门/BFS 提供）
    friends     : `[(id, familiar), ...]` 熟络度（自己算，本模块只消费）
    last        : 上一次的 `Intent`（L5：**读上次结果**，避免原地打转）

    返回 `Intent`。
    """
    ph = phase or phase_of(((float(now) % 86400.0) / 3600.0))
    traits = list(traits or ())
    reach = [s for s in (reachable or ()) if isinstance(s, str) and s.strip()]

    fam_avg = 0.0
    fdat = [(i, float(f or 0.0)) for i, f in (friends or ()) if isinstance(i, str)]
    if fdat:
        fam_avg = sum(f for _, f in fdat) / float(len(fdat))

    w = action_weights(npc_id, ph, traits, familiar=max(familiar, fam_avg),
                       extra=extra_weights)
    rng = rng_for(npc_id, salt)
    # ★★ 抖动叠在随机源上：同样权重、不同时刻 ⇒ 结果可不同（L6）
    rng.random()                       # 消化一次，避免抖动被下面的 pick 吞掉
    rng.seed(seed_for(npc_id, salt) ^ int(jitter(npc_id, now, salt, 0, 1 << 30)))

    what = weighted_pick(w, rng) or 'stay'

    # ---- 收束①：没地方可去 ⇒ 只能待着（**不是懒惰，是事实**）
    if what != 'stay' and not reach:
        return Intent('stay', None, None, 'no_reachable_scene', now)

    # ---- 收束②：原地打转去重（L5：读上次结果）
    if last is not None and what != 'stay':
        if what == 'visit_favorite' and last.what == 'visit_favorite' \
                and last.dest_scene and len(reach) > 1:
            what = 'wander'
        if what == 'go_home' and last.what == 'go_home' and home:
            what = 'wander'

    dest, who = None, None

    if what == 'stay':
        return Intent('stay', None, None, 'chose_to_stay', now)

    if what == 'go_home':
        # ★ L4：**回得去才回**；回不去就退化成随便走走（不硬性"必须回家"）
        if home and home in reach:
            dest, why = home, 'go_home'
        else:
            what, dest, why = 'wander', _pick_reachable(reach, rng), 'home_unreachable'
    elif what == 'visit_friend':
        who, dest, why = _pick_friend(fdat, reach, rng)
        if dest is None:
            what, why = 'wander', 'no_friend_reachable'
            dest = _pick_reachable(reach, rng)
    elif what == 'visit_favorite':
        fav = [s for s in (favorites or ()) if s in reach]
        if fav:
            dest, why = _pick_from(fav, rng), 'favorite'
        else:
            what, dest, why = 'wander', _pick_reachable(reach, rng), 'no_favorite_reachable'
    elif what == 'explore_unknown':
        known = set(favorites or ()) | ({home} if home else set())
        fresh = [s for s in reach if s not in known]
        if fresh:
            # 探索欲别太满：越"没去过"的池子越小越收敛
            fresh = fresh[:max(1, int(len(fresh) * min(1.0, EXPLORE_MAX / 2.0)))]
            dest, why = _pick_from(fresh, rng), 'unknown_place'
        else:
            what, dest, why = 'wander', _pick_reachable(reach, rng), 'nothing_new'
    else:                                    # wander
        dest, why = _pick_reachable(reach, rng), 'wander'

    if dest is None:
        return Intent('stay', None, None, 'dest_unresolved', now)
    return Intent(what, dest, who, why, now)


def _pick_reachable(reach, rng):
    if not reach:
        return None
    return reach[rng.randrange(len(reach))]


def _pick_from(pool, rng):
    if not pool:
        return None
    return pool[rng.randrange(len(pool))]


def _pick_friend(friends, reach, rng):
    """挑一个**熟且到得了**的朋友。→ `(who, dest, why)`；挑不到 → `(None, None, 原因)`。"""
    if not friends:
        return None, None, 'no_friends'
    # 只在"他住的场景可达"的里面挑；按熟络度加权
    cand = [(i, f) for i, f in friends if f > 0 and i]
    if not cand:
        return None, None, 'no_known_friend'
    wts = [max(1e-6, f) for _, f in cand]
    total = sum(wts)
    x = rng.random() * total
    acc = 0.0
    for (i, f), wv in zip(cand, wts):
        acc += wv
        if x < acc:
            # ★ 朋友的"场景"由调用方在 favorites/home 里给；这里只回 id
            return i, _pick_reachable(reach, rng), 'visit_friend'
    i, _f = cand[-1]
    return i, _pick_reachable(reach, rng), 'visit_friend'


# ---------------------------------------------------------------- Plan（L5）


class Plan(object):
    """**今天的生活规划**（L5：下次决策会读上次结果）。

    * `day`      : 规划归属的那一天（`int(now // 86400)`）
    * `intent`   : 今天当前的意图（`Intent`）
    * `last_sleep_scene` : **昨晚睡在哪**（L4：可以是朋友家，不必是自己家）
    * `wants`    : 今天想做的几件事（人设/偏好来的"愿望"，不必全实现）
    * `history`  : 今天做过的事（`why` 列表，**读它来避免原地打转**）
    """

    __slots__ = ('day', 'intent', 'last_sleep_scene', 'wants', 'history')

    def __init__(self, day=0, intent=None, last_sleep_scene=None, wants=None,
                 history=None):
        self.day = int(day)
        self.intent = intent
        self.last_sleep_scene = last_sleep_scene
        self.wants = list(wants or ())
        self.history = list(history or ())

    def roll_day(self, now):
        """跨天 ⇒ 清今天的 history（`wants` 保留，那是长期偏好）。"""
        d = int(float(now) // 86400.0)
        if d != self.day:
            self.day = d
            self.history = []
        return self

    def note(self, intent, keep=12):
        """记下这次决策（**有界**，防无限膨胀 —— 存档体积可控）。"""
        if intent is None:
            return self
        self.intent = intent
        tag = '%s:%s' % (intent.what, intent.dest_scene or '-')
        self.history.append(tag)
        if len(self.history) > int(keep):
            del self.history[:len(self.history) - int(keep)]
        return self

    def repeated_visits(self):
        """→ `{scene: 次数}`（调用方可据此降权，别老去同一个地方）。"""
        out = {}
        for h in self.history:
            _, _, scene = h.partition(':')
            if scene and scene != '-':
                out[scene] = out.get(scene, 0) + 1
        return out

    def to_dict(self):
        return collections.OrderedDict((
            ('day', self.day),
            ('intent', self.intent.to_dict() if self.intent else None),
            ('last_sleep_scene', self.last_sleep_scene),
            ('wants', list(self.wants)),
            ('history', list(self.history)),
        ))

    @classmethod
    def from_dict(cls, d):
        d = d or {}
        it = d.get('intent')
        return cls(d.get('day') or 0,
                   Intent.from_dict(it) if it else None,
                   d.get('last_sleep_scene'),
                   d.get('wants'), d.get('history'))

    def __repr__(self):
        return '<Plan day=%d intent=%s sleep=%s wants=%d hist=%d>' % (
            self.day, self.intent, self.last_sleep_scene, len(self.wants),
            len(self.history))


# ---------------------------------------------------------------- 睡觉（L4）

#: 睡觉地点的**候选权重加成**（不强制）。`own_home` 基础权重与 `friend` 同量级
#: ⇒ **"睡朋友家"和"睡自己家"是可比的选项**，谁赢由 `rng` + 熟络度决定。
SLEEP_HOME_BASE = 1.0
SLEEP_FRIEND_BASE = 1.0


def choose_sleep_scene(npc_id, now, *, home=None, friends=None, reachable=None,
                       last_sleep=None):
    """**今晚睡哪**（L4：**不硬性回家**，也可以睡朋友那）。

    ★★ 与旧口径的差别：旧 `BEDTIME_HOME_SCENE = 'desktop'` 是**常量**；
       这里是一个**决策**。⇒ 老行为**应在接线处标注为"旧口径已废弃"**。

    `friends` 形如 `[(npc_id, familiar, scene_id), ...]` —— **第三个元素是"他住哪"**，
    这是与 `decide()` 的 `friends` 唯一不同处（睡觉需要**地点**）。
    """
    reach = [s for s in (reachable or ()) if isinstance(s, str) and s.strip()]
    opts = []
    if home and home in reach:
        opts.append((home, SLEEP_HOME_BASE, 'own_home'))
    for item in (friends or ()):
        if len(item) < 3:
            continue
        fid, fam, fscene = item[0], item[1], item[2]
        if not (isinstance(fscene, str) and fscene in reach):
            continue
        try:
            fam = max(0.0, min(FAMILIAR_CAP, float(fam)))
        except (TypeError, ValueError):
            fam = 0.0
        if fam <= 0:
            continue
        opts.append((fscene, SLEEP_FRIEND_BASE * (1.0 + FAMILIAR_FRIEND_BONUS * fam),
                     'friend_of:%s' % fid))
    if not opts:
        return None, 'nowhere'
    # ★ 别连着两晚睡同一个朋友家（不是禁止，是**降权**）
    if last_sleep:
        opts = [(s, w * (0.6 if s == last_sleep else 1.0), why) for s, w, why in opts]
    rng = rng_for(npc_id, 'sleep')
    rng.seed(seed_for(npc_id, 'sleep') ^ int(jitter(npc_id, now, 'sleep', 0, 1 << 30)))
    total = sum(w for _, w, _ in opts)
    x = rng.random() * total
    acc = 0.0
    for s, w, why in opts:
        acc += w
        if x < acc:
            return s, why
    s, _w, why = opts[-1]
    return s, why


# ---------------------------------------------------------------- 声明

WIRING = collections.OrderedDict((
    ('wired', False),
    ('used_by', []),
    ('why', '层1 只做"决策"（纯函数，零依赖、可离线验）。'
            '层2（移动）由 main → scene_controller.travel_to 接线，'
            '开关 NPC_AUTONOMOUS_MOVE 默认 false；'
            '层3（睡觉）替换 BEDTIME_HOME_SCENE；层4（存档）走 data_store。'),
    ('not_yet', ['main 接线（层2）', 'BEDTIME_HOME_SCENE 替换（层3）',
                 '规划持久化（层4）']),
))

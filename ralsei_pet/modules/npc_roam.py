# -*- coding: utf-8 -*-
"""NPC 自主生活 · 层2：**驻留层**（零依赖，只准标准库）。

为什么需要这一层（用户口径，第77轮逐字）
------------------------------------------
> 「**不会因为缺少一个人哪怕是我他们就不生活了**」
> 「去哪？找谁？干什么？生活规划这类的事也是由**各自的 AI 决定**」

现状（第78轮定位出的**头号障碍**）
------------------------------------
`_npc_seed_bodies()` **只在两处**被调用（`main.py:2182` 启动、`:2513` **场景切换钩子**）。
⇒ 现有模型是「**NPC = 当前场景的装饰**」：站位表 `_placement.json` 里写死
  `scene_of(npc_id)`，NPC 没有属于自己的位置状态。
⇒ 后果：**用户不动，世界就冻住** —— 与 L2「不会因为缺了我就不生活了」**正相反**。

本模块做的模型升级
------------------
把「**静态归属**」升级成「**静态归属 + 动态驻留覆盖**」：

    · 静态归属（`_placement.json`）  = **默认值**，永远不动；
    · 动态驻留（`RoamState`）        = **覆盖**，只存"偏离了默认"的人。

⇒ `resident_of(npc_id)`：
     · 有覆盖 ⇒ 返回覆盖值（他现在在哪）；
     · 没有   ⇒ 返回 `None`（**不是**默认值 —— 让调用方自己回落站位表）。

★★ 为什么"没有覆盖"必须返回 `None` 而不是"默认值"：
   「默认值」的真源在 `_placement.json`，本模块**不该复制**一份
   （那就是"同一份规则两处算" —— 本项目最贵的坑）。
   返回 `None` = **明确交接**：这个人的位置没人管，去看站位表。

零回归（★ 最重要的一条）
--------------------------
`enabled=False`（= 产品默认 `NPC_AUTONOMOUS_MOVE=False`）时：
`step()` **立即返回、一个字节都不改** ⇒ 覆盖表恒空 ⇒ 全场景回落站位表
⇒ 行为与现在**逐字相同**。这不是"大概一样"，是**结构保证**。

零依赖纪律（对齐 `companion*` / `npc_placement` / `npc_intent`）
------------------------------------------------------------------
* 顶层只 `import` 标准库；
* **零函数内 import**；
* **不 import 任何项目内模块**（连 `npc_intent` 都不 import ——
  决策从**入参**拿，见 `step()` 的 `decide_fn`）。
"""
import collections
import hashlib
import math


def _sha256_hex(b):
    """薄包装（便于判据用 AST 核"只调标准库"，也便于将来换算法只改一处）。"""
    return hashlib.sha256(b).hexdigest()

# ---------------------------------------------------------------- 常量

#: 一次"出行"的最短持续时间（秒）。★ 不许"走到就走" —— 那会让 NPC 每帧换房。
#: 用户口径「生活是生活」⇒ 到了一个新地方，会**待一会儿**。
MIN_DWELL_SECONDS = 180.0

#: 一次"出行"的最长持续时间（秒）。超过就该重新决策（不然会永远卡在别人家）。
MAX_DWELL_SECONDS = 3600.0 * 6.0

#: 两次决策之间的**最小**间隔（秒）—— 防抖（同一秒内被 tick 多次不该决策多次）。
DECIDE_COOLDOWN = 60.0

#: 允许"离开当前位置"的概率下限/上限（★ 不设 0 ⇒ 不出现"永远不动"）。
LEAVE_P_MIN = 0.02
LEAVE_P_MAX = 0.85

#: 桌面是**特殊场景**：不能由自主移动进入（必须走跟随/邀请那条路）。
#: ★ 这是与 `npc_system.DESKTOP_ALLOWED_IDS` **并列**的一道闸，不是替代它。
DESKTOP_SCENE = 'desktop'

DEFAULT_ROAM_ENABLED = False


# ---------------------------------------------------------------- 单条驻留

class Stay(object):
    """一个 NPC **当前待在哪 + 待到什么时候**。

    `until` 是**绝对秒**（`time.time()` 口径）—— 用它而不是"剩余秒数"，
    这样**进程重启后仍然有效**（进程重启不会让所有人的计时归零）。
    """

    __slots__ = ('npc_id', 'scene', 'since', 'until', 'reason')

    def __init__(self, npc_id, scene, since=0.0, until=0.0, reason=''):
        self.npc_id = npc_id
        self.scene = scene
        self.since = float(since)
        self.until = float(until)
        self.reason = reason or ''

    def remaining(self, now):
        try:
            return max(0.0, float(self.until) - float(now))
        except (TypeError, ValueError):
            return 0.0

    def is_expired(self, now):
        return self.remaining(now) <= 0.0

    def to_dict(self):
        return collections.OrderedDict((
            ('npc_id', self.npc_id),
            ('scene', self.scene),
            ('since', self.since),
            ('until', self.until),
            ('reason', self.reason),
        ))

    @classmethod
    def from_dict(cls, d):
        d = d or {}
        return cls(d.get('npc_id'), d.get('scene'),
                   d.get('since') or 0.0, d.get('until') or 0.0,
                   d.get('reason') or '')

    def __repr__(self):
        return '<Stay %s @%s until=%.0f>' % (self.npc_id, self.scene, self.until)


# ---------------------------------------------------------------- 驻留表

class RoamState(object):
    """**驻留覆盖表**：`{npc_id: Stay}`，只存"偏离静态归属"的人。

    ★ 不是"所有人的位置表" —— 那会与 `_placement.json` 抢真源。
      这里只回答一个问题：「**有谁现在不在他该在的地方？**」
    """

    __slots__ = ('enabled', '_by_id', 'last_step')

    def __init__(self, enabled=DEFAULT_ROAM_ENABLED, stays=None):
        self.enabled = bool(enabled)
        self._by_id = collections.OrderedDict()
        for s in (stays or ()):
            if isinstance(s, Stay) and s.npc_id:
                self._by_id[s.npc_id] = s
        self.last_step = 0.0

    # -- 查询（★ 只读，不改状态）
    def __len__(self):
        return len(self._by_id)

    def __contains__(self, npc_id):
        return npc_id in self._by_id

    def ids(self):
        return list(self._by_id.keys())

    def get(self, npc_id):
        return self._by_id.get(npc_id)

    def resident_of(self, npc_id):
        """**他现在在哪**；没人管 ⇒ `None`（**不是**默认值，见模块抬头）。"""
        s = self._by_id.get(npc_id)
        return s.scene if s is not None else None

    def snapshot(self):
        """→ `{npc_id: scene}`（给 `_npc_scene_roster` 用；空表 ⇒ 空 dict）。"""
        return collections.OrderedDict(
            (k, v.scene) for k, v in self._by_id.items())

    # -- 变更
    def put(self, npc_id, scene, now, dwell=None, reason=''):
        """记下"某人现在在 `scene`，待到 `now + dwell`"。

        `dwell` 为 `None` ⇒ 用 `MIN_DWELL_SECONDS`（**不是** 0：不许即到即走）。
        """
        if not (isinstance(npc_id, str) and npc_id):
            return None
        d = MIN_DWELL_SECONDS if dwell is None else float(dwell)
        d = max(MIN_DWELL_SECONDS, min(MAX_DWELL_SECONDS, d))
        st = Stay(npc_id, scene, since=float(now), until=float(now) + d,
                  reason=reason)
        self._by_id[npc_id] = st
        return st

    def drop(self, npc_id):
        """**撤掉覆盖** ⇒ 该 NPC 回落站位表（= "他回家了 / 不该被管了"）。"""
        return self._by_id.pop(npc_id, None)

    def clear(self):
        self._by_id.clear()

    def expired(self, now):
        """→ 已到期的人 id 列表（**只读，不删** —— 删由调用方决定）。"""
        return [k for k, v in self._by_id.items() if v.is_expired(now)]

    # -- 序列化
    def to_dict(self):
        return collections.OrderedDict((
            ('enabled', self.enabled),
            ('stays', [v.to_dict() for v in self._by_id.values()]),
        ))

    @classmethod
    def from_dict(cls, d):
        d = d or {}
        raw = d.get('stays') or []
        stays = []
        for item in raw:
            try:
                stays.append(Stay.from_dict(item))
            except Exception:
                continue
        return cls(d.get('enabled', DEFAULT_ROAM_ENABLED), stays)

    def __repr__(self):
        return '<RoamState enabled=%s n=%d>' % (self.enabled, len(self._by_id))


# ---------------------------------------------------------------- 推进（纯函数）

def leave_probability(stay, now, *, phase='day', familiar=0.0):
    """**他现在离开的概率** ∈ [LEAVE_P_MIN, LEAVE_P_MAX]（★ 恒 > 0）。

    三条：① 待得越久越想动；② 刚到时几乎不想动；③ 夜里更低（要睡了）。

    ★★ **永不返回 0** —— "永远不动"就是另一种"整点必做"（L6）。
    """
    try:
        dwell = max(0.0, float(now) - float(stay.since))
    except (TypeError, ValueError):
        dwell = 0.0
    span = max(1.0, float(stay.until) - float(stay.since))
    frac = min(1.0, dwell / span)                 # 0=刚来，1=该走了
    # ① 时间因子：待得越久，越接近"该走"（但**不到 1** ⇒ 不必然走）
    p = LEAVE_P_MIN + (LEAVE_P_MAX - LEAVE_P_MIN) * (frac ** 2.0)
    # ② 时段：夜里更恋栈（想睡了，不想挪窝）
    if phase == 'night':
        p *= 0.35
    elif phase == 'dawn':
        p *= 0.6
    # ③ 熟人越多越不想走（有人陪着）
    try:
        fam = max(0.0, min(1.0, float(familiar)))
    except (TypeError, ValueError):
        fam = 0.0
    p *= (1.0 - 0.3 * fam)
    return max(LEAVE_P_MIN, min(LEAVE_P_MAX, p))


def step(state, now, *, decide_fn=None, roster=None, traits_of=None,
         familiar_of=None, home_of=None, reachable_of=None,
         friends_of=None, enabled=None, salt=''):
    """推进一拍。**纯函数式**：只改 `state`（调用方给的），不改任何全局。

    参数
    ----
    state       : `RoamState`（就地更新）
    now         : 绝对秒（`time.time()`）
    decide_fn   : **决策函数**（宿主注入）—— 见下 ★
    roster      : 全部候选 npc_id（不给 ⇒ 只处理表内已有的人）
    traits_of   : `npc_id -> [特质]`
    familiar_of : `npc_id -> 熟络度`
    home_of     : `npc_id -> 他自己的场景 id`（★ 静态归属，由宿主从站位表取）
    reachable_of: `npc_id -> [可达场景 id]`
    friends_of  : `npc_id -> [(id, familiar, scene_id)]`
    enabled     : 覆盖 `state.enabled`（`None` ⇒ 用 state 自己的）

    ★★ `decide_fn` 签名 = `(npc_id, now, **kw) -> Intent | (scene, reason) | None`
       这是本模块**唯一**与决策层耦合的地方 —— 且是**注入**的（默认 `None`）。
       ⇒ 零依赖纪律得以保持：本模块**不 import** `npc_intent`。

    返回 `{'decided': [...], 'expired': [...], 'moved': [...]}`（如实登记）。
    """
    out = {'decided': [], 'expired': [], 'moved': []}
    on = state.enabled if enabled is None else bool(enabled)
    if not on:
        # ★★ 零回归：关掉开关 ⇒ 一个字节都不改。
        return out
    try:
        now = float(now)
    except (TypeError, ValueError):
        return out

    # ---- ① 到期：**撤掉覆盖**（回落站位表）----
    for nid in state.expired(now):
        if state.drop(nid) is not None:
            out['expired'].append(nid)

    # ---- ② 决策：谁该动 ----
    cand = list(roster or state.ids())
    for nid in cand:
        if not (isinstance(nid, str) and nid):
            continue
        cur = state.get(nid)
        if cur is not None and not cur.is_expired(now):
            # 还在"驻留期"内 —— 只有概率性地提前走（不是必然）
            ph = _phase_name(now)
            fam = _call(familiar_of, nid, 0.0)
            p = leave_probability(cur, now, phase=ph, familiar=fam)
            if not _roll(nid, now, salt, p):
                continue
        # 走到这里：要么没覆盖、要么到期了、要么摇中"提前走"
        dest, reason = _ask(decide_fn, nid, now,
                            traits=_call(traits_of, nid, None),
                            familiar=_call(familiar_of, nid, 0.0),
                            home=_call(home_of, nid, None),
                            reachable=_call(reachable_of, nid, None),
                            friends=_call(friends_of, nid, None))
        if dest is None:
            continue
        if dest == DESKTOP_SCENE:
            # ★ 桌面不许**自主**进入（要走跟随/邀请那条路）
            continue
        if cur is not None and dest == cur.scene:
            continue                    # 没挪窝 ⇒ 不记（避免刷表）
        state.put(nid, dest, now, reason=reason)
        out['decided'].append(nid)
        out['moved'].append((nid, dest))
    state.last_step = now
    return out


def _phase_name(now):
    """本模块**自带**的时段名（★ 不 import `npc_intent` —— 零依赖纪律）。

    ★ 与 `npc_intent.PHASES` **同值**是刻意的：两边都只是"倾向"，
      真源在各自的模块里；由 `check79` 断言两者**逐字相等**（防悄悄漂移）。
    """
    try:
        h = (float(now) % 86400.0) / 3600.0
    except (TypeError, ValueError):
        h = 12.0
    if 5 <= h < 8:
        return 'dawn'
    if 8 <= h < 17:
        return 'day'
    if 17 <= h < 21:
        return 'dusk'
    return 'night'


def _roll(npc_id, now, salt, p):
    """确定性"是否发生"（同人同刻可复现；异刻可变）。★ 不共享全局 `random`。"""
    u = _unit(npc_id, now, salt)
    return u < max(0.0, min(1.0, float(p)))


def _unit(npc_id, now, salt=''):
    """`(npc_id, 连续时间, salt)` → 确定性 `u ∈ [0,1)`。

    ★ 用**连续时间**（不是"第几个时间片"）：时间片会把同一段锁成同一个值。
    ★ import 在**模块顶层**（零依赖纪律明令禁止函数内 import）。
    """
    h = _sha256_hex(
        ('%.6f|%s|%s' % (float(now), npc_id or '', salt or '')).encode('utf-8'))
    return int(h[:12], 16) / float(0x1000000000000)


def _call(fn, *a):
    """安全调用宿主给的取值器（缺失/抛异常 ⇒ `None`）。"""
    if fn is None:
        return None
    try:
        return fn(*a)
    except Exception:
        return None


def _ask(decide_fn, npc_id, now, **kw):
    """问决策函数"去哪"。→ `(scene_id | None, reason)`。

    ★ 容错三种返回形状：
      · `Intent`（有 `.dest_scene` / `.why`）；
      · `(scene, reason)` 元组；
      · `None` ⇒ 不去。
    """
    if decide_fn is None:
        return None, ''
    try:
        r = decide_fn(npc_id, now, **kw)
    except Exception:
        return None, ''
    if r is None:
        return None, ''
    ds = getattr(r, 'dest_scene', None)
    if isinstance(ds, str) and ds:
        return ds, (getattr(r, 'why', '') or '')
    if isinstance(r, (tuple, list)) and len(r) >= 1:
        s = r[0]
        if isinstance(s, str) and s:
            return s, (r[1] if len(r) > 1 else '')
    return None, ''


def haversine_style_far(a, b):
    """★ 占位几何：本模块**不做**真实距离（那要房间几何，属宿主职责）。

    保留一个**纯算术**的小工具，供宿主/判据算"两个场景是否算远"的临时量。
    不引入任何项目内依赖。
    """
    try:
        dx, dy = float(b[0]) - float(a[0]), float(b[1]) - float(a[1])
    except (TypeError, ValueError, IndexError):
        return None
    return math.sqrt(dx * dx + dy * dy)


# ---------------------------------------------------------------- 声明

WIRING = collections.OrderedDict((
    ('wired', True),
    ('used_by', ['main._npc_scene_roster（读 resident_of，覆盖模式）',
                 'main._npc_roam_tick（按 30s 节拍调 step）',
                 'main.init_npc_systems（建 RoamState）']),
    ('wired_how', '开关 `NPC_AUTONOMOUS_MOVE`（默认 **False**）；'
                  '开 ⇒ NPC 有自己的位置状态（用户不动世界也转）；'
                  '关 ⇒ `step()` 零副作用 + `resident_of()` 恒 None'
                  ' ⇒ 全走 `_placement.json`，行为与第78轮逐字相同（零回归）。'),
    ('why', '层2 = 把「静态归属」升级成「静态归属 + 动态驻留覆盖」。'
            '要解决的头号障碍：`_npc_seed_bodies()` 只在启动与切场景时被调'
            ' ⇒「NPC = 当前场景的装饰」⇒ 用户不动、世界就冻住（与 L2 正相反）。'),
    ('not_yet', ['驻留表落 data_store（存档，层4）',
                 '层3 睡觉接线（`BEDTIME_HOME_SCENE` → `choose_sleep_scene`，挡在 Q3）']),
))

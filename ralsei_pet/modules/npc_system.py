# -*- coding: utf-8 -*-
"""第49轮 · NPC 分层 / 跟随策略 / 世界门控（零依赖，P0~P1 骨架）。

用户口径（第49轮原话，逐字要点）
--------------------------------
* 「主线npc也就是非主角团的但有重大影响的人（包括toriel和asgore哦，其他的就是
   各个章节的boos和相对重要的那几个）可以给他们一个4B模型」
* 「纯npc，也就是没任何有重大帮助对话的人，就用4~10句内置对话就好」
* 「这些npc都可以跟着主角团走，但只有主线npc可以自己自主跟随，
   其他的npc需要主角同意或是要求才行」
* 「这些npc都不可脱离暗世界或是进入不属于他们的暗世界」
* 「ralsei也不可以脱离暗世界，除非是…第3章…那个球」

★ 第50轮用户口径（逐字，**修订上面后两条**）
* 「16项要，但只有ralsei能自由在其他暗世界走，其他人无法通过球去其他世界，
  只能去光世界或是回原先他们的暗世界（这个不需要他们套上球）」

★ 第55轮用户口径（逐字，**修订模型档位**）
* 「我突然觉得4B貌似没办法支撑起来这些角色的灵魂，所以，给他们也升级成7B吧，
  但如果这非常吃性能那就慎重，但又不是同时运行所有，应该不至于」

设计
----
1. **分层**：`NpcTier.MAIN`（主线，**走模型**）/ `NpcTier.PLAIN`（纯 NPC，内置短对话）。
   ⚠️ 上面那句 4B 是**第49轮的历史原话**（当时登记的 `ralsei-npc:4b` 从未被代码读过），
   第55轮一度改成 `ralsei-npc:7b`，**最终定为 `None`** —— 因为 App 实际发的
   `config.json.api.model` 就是 7B（`ralsei:v4` = qwen2.5:7b），NPC 拿到的本就是 7B；
   再建一个同名句柄只会让 Ralsei 与 NPC 各常驻一份 ~4.7GB 权重。见 `DEFAULT_MAIN_MODEL`。
2. **跟随**：主线 = `FollowPolicy.AUTONOMOUS`；纯 NPC = `FollowPolicy.CONSENT`
   （要主角同意或主动要求）。两者**都能跟**，差别只在"谁发起"。
3. **世界门控**（★ 第50轮口径修订，逐字原话与推导见 `world_gate`）：
   · 光世界 —— **谁都能去，且不需要球**；
   · 暗世界 —— 只能进**自己登记过的那几章**（"回原先他们的暗世界"）；
   · 跨暗世界 —— **只有 Ralsei**（`free_dark_roam`）；
   · Ralsei 的例外性 = 他是**纯暗世界居民** ⇒ 脱离暗世界**必须**被装进球容器。
4. **电脑桌面**（★ 第56轮新增，逐字原话见 `world_gate`）：**只有主角团 + Lancer 能上桌面**
   （`DESKTOP_ALLOWED_IDS`），其余一律拒。⚠️ 这一条必须在光世界分支**之前**判 ——
   见 `world_gate` 里 `DESKTOP_SCENE` 那段的三条理由。

跟随的**轨迹数学**不在本模块：复用第46轮的 `companion.py`（`obj_caterpillarchara` 采样轨迹
+ `scr_makecaterpillar` 间距 + `scr_setparty` 2 个队友位）。本模块只负责**策略与门控**。

零依赖契约
----------
只允许模块顶部 `import collections / json / logging / os`。
（回归锁 `verify_npc49.py` 的 A 段用 AST 强制这一点；内部函数**不许**再 import。）
"""
import collections
import json
import logging
import os

try:  # 项目内统一 logger；模块外独立导入时降级
    from logger_utils import get_logger
    _log = get_logger(__name__)
except ImportError:
    _log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# ---------------------------------------------------------------- 常量

PLAIN_LINES_MIN = 4
PLAIN_LINES_MAX = 10

#: 主线 NPC 的模型口径 —— ★ **`None` = 跟随 App 配置（这就是"7B"的落地方式）**。
#:
#: 演进（三段，别把历史引述当现状）：
#:   · 第49轮登记 `ralsei-npc:4b`：那只是**计划值**，Ollama 侧从未建过，也**从未被任何
#:     代码读取** —— 也就是说"主线 NPC 用 4B"这句话在运行时从来不成立。
#:   · 第55轮用户口径：「4B 貌似没办法支撑起来这些角色的灵魂，所以，给他们也升级成
#:     7B 吧，但如果这非常吃性能那就慎重，但又不是同时运行所有，应该不至于」。
#:   · 第55轮最终做法：**改成 `None`（不单独指定）**。因为 App 实际发的
#:     `config.json.api.model` = `ralsei:v4` = `qwen2.5:7b-instruct-q4_K_M`
#:     ⇒ **NPC 拿到的本来就是 7B**，用户要的效果已经成立。
#:     再建一个 `ralsei-npc:7b` 的**唯一**后果是：同名不同句柄不共享实例，
#:     Ralsei 与 NPC 会各常驻一份 ~4.7GB 权重，而收益为零 —— 正是用户提醒的
#:     「非常吃性能那就慎重」。
#: ★ 字段本身**已经接线**（`main._npc_model` → `chat_with_ai(model=)` →
#:   `api_client._chat_payload`），所以将来真要给 NPC 单独换模型，
#:   把它填成 Ollama 里**真实存在**的句柄即可，不必改代码。
DEFAULT_MAIN_MODEL = None


class NpcTier(object):
    """NPC 分层。值即 `_registry.json` 里的字面量。"""
    MAIN = 'main'      # 主线：非主角团但有重大影响（Toriel / Asgore / 各章 Boss / 少数关键角色）
    PLAIN = 'plain'    # 纯 NPC：没有重大帮助对话，用 4~10 句内置对话

    ALL = ('main', 'plain')


class FollowPolicy(object):
    """谁能发起跟随。"""
    AUTONOMOUS = 'autonomous'   # 主线：自己就能跟
    CONSENT = 'consent'         # 纯 NPC：要主角同意或主动要求


#: 分层 → 跟随策略（单一真源）
TIER_FOLLOW_POLICY = {
    NpcTier.MAIN: FollowPolicy.AUTONOMOUS,
    NpcTier.PLAIN: FollowPolicy.CONSENT,
}

#: 分层 → 对话来源
TIER_DIALOGUE = {
    NpcTier.MAIN: 'llm',        # 走模型（`DEFAULT_MAIN_MODEL`，第55轮起为 7B）
    NpcTier.PLAIN: 'builtin',   # 走内置短对话
}

WORLD_LIGHT = 'light'
WORLD_DARK = 'dark'
#: ★ 第72轮：**本作之外的世界**（Undertale / 黄魂 / Outertale / OneShot 各自的世界）。
#:
#: 为什么不能沿用 `light` / `dark`：这两个值是 **Deltarune 语汇**（暗之泉的明暗二分）。
#: UT 的地下世界、OneShot 的城市都**不是"暗世界"** —— 硬塞进 `dark` 会得出
#: 「他要靠球才能出门」这种荒唐结论（第71轮复查时实证：61 位跨作品角色的
#: `home_world` 全是 `dark`，而 `dark` 在本项目里的唯一语义就是"暗之泉那一侧"）。
#: ⇒ 跨作品角色的 `home_world` 一律记 `foreign`，他们的来处由 `chapters`
#:   （作品名，如 `'undertale'` / `'oneshot'`）承载。
WORLD_FOREIGN = 'foreign'


class RoamScope(object):
    """★ 第72轮：**穿行域** —— 一个 NPC 能去哪些世界。

    用户口径（第72轮原话，逐字）：
      「niko可自由穿行所有世界，其余ut及其同人的任务只能在非暗世界穿梭」

    三档（值即 `_registry.json` 里的字面量）：

    * ``HOME``     —— **只在自己登记的世界/章节里活动**。
      **Deltarune 侧 35 位全部走这一档**，行为 = 第49/50轮原口径
      （光世界自由 / 暗世界限本作品章 / 跨暗只有 Ralsei）⇒ **零回归**。
    * ``NON_DARK`` —— 可以穿行**所有非暗世界**（Deltarune 的光世界 + 自己作品的世界），
      但**进不了 Deltarune 的暗世界**。**跨作品角色的默认档**
      （「其余ut及其同人的任务只能在非暗世界穿梭」）。
    * ``ALL``      —— 所有世界（**含** Deltarune 的暗世界）。**仅 Niko 一人**
      （「niko可自由穿行所有世界」）。

    ⚠️ 为什么不复用 `home_world`：`home_world` 说的是"他打哪儿来"（静态归属），
    `roam_scope` 说的是"他能去哪儿"（动态许可）。用户那句话改的正是**后者**
    （"可自由穿行" / "只能在非暗世界穿梭"都是许可句），两者混为一谈会让
    "Niko 是 OneShot 人" 和 "Niko 哪都能去" 互相打架。
    """
    HOME = 'home'
    NON_DARK = 'non_dark'
    ALL = 'all'

    ALL_VALUES = ('home', 'non_dark', 'all')

# 门控结果码
REASON_OK = 'ok'
REASON_LEAVE_DARK = 'leave_dark_world'      # 未知/非法世界
REASON_FOREIGN_DARK = 'foreign_dark_world'  # 进入不属于他的暗世界（且无跨章权限）
REASON_NO_CHAPTERS = 'no_chapters'          # 登记里没有可用章节 ⇒ 不硬判，拒绝
#: ★ 第50轮：Ralsei 想脱离暗世界却没被装进球（他是纯暗世界居民）
REASON_LIGHT_NEEDS_BUBBLE = 'light_needs_bubble'
#: ★ 第56轮：想上电脑桌面，但不在白名单里
REASON_DESKTOP_FORBIDDEN = 'desktop_forbidden'

#: ★ 第56轮：**电脑桌面**这个场景 id。
#: `scene_system` 里 `desktop` 与作品内场景**完全平级**（`_index.json` 顶层就有），
#: 而 `_worlds.json` 的 `overrides.desktop == "light"` ⇒ 只按世界判的话
#: **所有 NPC 都能上桌面**，与用户口径相反 ⇒ 必须单独设一道闸（`DESKTOP_GATED`）。
DESKTOP_SCENE = 'desktop'

#: ★ 第56轮用户口径（逐字）：
#:   「其次，只有主角团最多加个lancer能来电脑桌面，其余的不能」
#: 主角团 = Ralsei / Kris / Susie（`ralsei_pet/assets/npc/_placement.json` 的
#: `groups[0].members`，同一个集合），"最多加个 lancer" ⇒ 共 **4** 个。
#: ⚠️ 这是**代码侧单一真源**；`_placement.json` 的 `desktop.allowed` 是**数据镜像**
#:   （回归锁 `check56.py` 会断言两者逐字相等，防止改一处忘一处）。
#: ★ 也**不要**把它写成"从 tier 推" —— 主角团里 kris/susie 是 `main`，
#:   但 `main` 里还有 toriel/asgore/king/queen 等一堆**不许上桌面**的人。
DESKTOP_ALLOWED_IDS = ('ralsei', 'kris', 'susie', 'lancer')

# 跟随状态
FOLLOW_IDLE = 'idle'          # 没跟
FOLLOW_PENDING = 'pending'    # 纯 NPC 已请求，等主角点头
FOLLOW_ACTIVE = 'active'      # 正在跟
FOLLOW_DENIED = 'denied'      # 主角拒绝了


# ---------------------------------------------------------------- 数据

class NpcDef(object):
    """一个 NPC 的静态定义（不承担运行时状态）。"""

    __slots__ = ('id', 'name', 'name_cn', 'tier', 'chapters', 'home_world',
                 'objects', 'model', 'needs_setting', 'notes',
                 'escape_via_bubble', 'lines', 'persona', 'roam_scope')

    def __init__(self, id, name='', name_cn='', tier=NpcTier.PLAIN,
                 chapters=(), home_world=WORLD_DARK, objects=(), model=None,
                 needs_setting=False, notes='', escape_via_bubble=False, lines=(),
                 persona=None, roam_scope=None):
        self.id = id
        self.name = name or id
        self.name_cn = name_cn or self.name
        self.tier = tier if tier in NpcTier.ALL else NpcTier.PLAIN
        self.chapters = tuple(chapters)
        #: ★ 第72轮：允许第三个值 `WORLD_FOREIGN`（本作之外的世界）。见常量注释。
        self.home_world = (home_world if home_world in (WORLD_LIGHT, WORLD_DARK,
                                                        WORLD_FOREIGN)
                           else WORLD_DARK)
        self.objects = tuple(objects)
        self.model = model
        self.needs_setting = bool(needs_setting)
        self.notes = notes
        #: 是否**只能靠球**离开暗世界（Ralsei 专属；其他 NPC 一律不许离开）
        self.escape_via_bubble = bool(escape_via_bubble)
        self.lines = tuple(lines)
        #: ★ 第55轮：人设文件路径（相对 `assets/npc/`）；`None` = 还没装设定。
        #: 与 `needs_setting` 的关系是**唯一**的：`needs_setting = (persona is None)`。
        #: 为什么新增这个字段而不是把 `needs_setting` 翻成 False 就完事：
        #:   `needs_setting` 只说"要不要"，说不了"设放在哪" —— 装上之后必须能**找到**它。
        self.persona = persona or None
        #: ★ 第72轮：穿行域（`RoamScope` 三档）。
        #: 归一规则（**必须放在 `home_world` 之后**，否则读到的是旧值）：
        #:   显式给了合法值 ⇒ 用它；否则按来处推 —— 本作之外的居民默认 `NON_DARK`，
        #:   其余（Deltarune 侧）一律 `HOME`。
        #:   为什么要兜底而不是拒绝：老注册表（第70轮及以前）没有这个字段，
        #:   读到时必须退化成第49/50轮的原有行为，**不能因为缺字段就崩或改行为**。
        self.roam_scope = (roam_scope if roam_scope in RoamScope.ALL_VALUES
                           else (RoamScope.NON_DARK
                                 if self.home_world == WORLD_FOREIGN
                                 else RoamScope.HOME))

    def to_dict(self):
        return collections.OrderedDict((
            ('id', self.id), ('name', self.name), ('name_cn', self.name_cn),
            ('tier', self.tier), ('chapters', list(self.chapters)),
            ('home_world', self.home_world), ('objects', list(self.objects)),
            ('model', self.model), ('needs_setting', self.needs_setting),
            ('escape_via_bubble', self.escape_via_bubble),
            ('persona', self.persona),
            ('roam_scope', self.roam_scope),
            ('notes', self.notes),
        ))

    def __repr__(self):
        return '<NpcDef %s tier=%s ch=%s>' % (self.id, self.tier, ','.join(self.chapters))


def _as_tuple(v):
    if v is None:
        return ()
    if isinstance(v, (list, tuple)):
        return tuple(v)
    return (v,)


def npc_from_dict(d):
    """从 `_registry.json` 的单条记录构造 `NpcDef`（缺字段一律有默认值）。"""
    if not isinstance(d, dict) or not d.get('id'):
        raise ValueError('NpcDef 需要至少一个 id 字段')
    return NpcDef(
        id=d['id'],
        name=d.get('name', ''),
        name_cn=d.get('name_cn', ''),
        tier=d.get('tier', NpcTier.PLAIN),
        chapters=_as_tuple(d.get('chapters')),
        home_world=d.get('home_world', WORLD_DARK),
        objects=_as_tuple(d.get('objects')),
        model=d.get('model'),
        needs_setting=d.get('needs_setting', False),
        notes=d.get('notes', ''),
        escape_via_bubble=d.get('escape_via_bubble', False),
        persona=d.get('persona') or None,
        roam_scope=d.get('roam_scope'),
    )


class NpcRegistry(object):
    """NPC 注册表（只读视图 + 分层查询）。"""

    def __init__(self, npcs, dialogue=None):
        self._by_id = collections.OrderedDict()
        for n in npcs:
            self._by_id[n.id] = n
        #: {npc_id: [行, ...]} 纯 NPC 的内置对话
        self.dialogue = dict(dialogue or {})

    # -- 查询
    def __len__(self):
        return len(self._by_id)

    def __contains__(self, nid):
        return nid in self._by_id

    def get(self, nid):
        return self._by_id.get(nid)

    def ids(self):
        return list(self._by_id.keys())

    def all(self):
        return list(self._by_id.values())

    def of_tier(self, tier):
        return [n for n in self._by_id.values() if n.tier == tier]

    def main_npcs(self):
        return self.of_tier(NpcTier.MAIN)

    def plain_npcs(self):
        return self.of_tier(NpcTier.PLAIN)

    def lines_of(self, nid):
        """纯 NPC 的内置对话（主线 NPC 返回空表——他们走模型）。"""
        return list(self.dialogue.get(nid, ()))


# ---------------------------------------------------------------- 加载

def _default_root():
    # 本文件位于 ralsei_pet/modules/ ⇒ assets 在上一级
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def registry_paths(root=None):
    root = root or _default_root()
    d = os.path.join(root, 'assets', 'npc')
    return (os.path.join(d, '_registry.json'), os.path.join(d, '_dialogue.json'))


def load_registry(root=None):
    """读 `assets/npc/_registry.json` + `_dialogue.json`。

    读不到 / 解析失败一律**返回空表**，绝不让调用方起不来（与 `sprite_loader` 同口径）。
    """
    reg_p, dia_p = registry_paths(root)
    npcs = []
    dialogue = {}
    try:
        with open(reg_p, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
        for d in raw.get('npcs', []):
            try:
                npcs.append(npc_from_dict(d))
            except Exception as e:
                _log.warning('跳过非法 NPC 记录 %r: %s', d, e)
    except Exception as e:
        _log.warning('NPC 注册表读取失败 %s: %s', reg_p, e)
    try:
        with open(dia_p, 'r', encoding='utf-8') as fh:
            dialogue = json.load(fh).get('lines', {})
    except Exception as e:
        _log.warning('NPC 内置对话读取失败 %s: %s', dia_p, e)
    return NpcRegistry(npcs, dialogue)


# ---------------------------------------------------------------- 策略（纯函数）

def follow_policy(npc):
    """主线 = 自主；纯 NPC = 需同意。"""
    return TIER_FOLLOW_POLICY.get(npc.tier, FollowPolicy.CONSENT)


def needs_consent(npc):
    """要不要主角点头才能跟。"""
    return follow_policy(npc) == FollowPolicy.CONSENT


def can_follow(npc):
    """**所有** NPC 都能跟主角团（差别只在谁发起）。"""
    return bool(npc.chapters)


def dialogue_source(npc):
    return TIER_DIALOGUE.get(npc.tier, 'builtin')


def scene_chapter(scene_id):
    """`ch3.castle_town.castle_town` → `ch3`（不是本格式则返回 None）。"""
    if not isinstance(scene_id, str):
        return None
    parts = scene_id.split('.')
    if not parts or not parts[0]:
        return None
    return parts[0]


class GateResult(object):
    __slots__ = ('ok', 'reason', 'detail')

    def __init__(self, ok, reason=REASON_OK, detail=''):
        self.ok = bool(ok)
        self.reason = reason
        self.detail = detail

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return '<GateResult %s %s>' % ('OK' if self.ok else 'DENY', self.reason)


# ---------------------------------------------------------------- 世界归属特例

#: ★ 第50轮：**纯暗世界居民**（只有 Ralsei）。这一个事实推出两条特例 ——
#:   ① 进光世界**必须**被装进球（「ralsei也不可以脱离暗世界，除非是…那个球」）；
#:   ② 反而**可以自由在别的暗世界走**（「只有ralsei能自由在其他暗世界走」）。
#:   `_registry.json` 里用 `escape_via_bubble` 这一个登记位表达。
DARK_ONLY_IDS = ('ralsei',)


def is_dark_only(npc):
    """是不是**纯暗世界居民**（仅 Ralsei）。"""
    if getattr(npc, 'id', None) in DARK_ONLY_IDS:
        return True
    return bool(getattr(npc, 'escape_via_bubble', False))


def light_needs_bubble(npc):
    """进光世界**是否必须靠球**（仅 Ralsei）。

    「其他人…只能去光世界或是回原先他们的暗世界（**这个不需要他们套上球**）」
    ⇒ 除 Ralsei 外一律 False。
    """
    return is_dark_only(npc)


def free_dark_roam(npc):
    """能否**自由在别的暗世界走**（★ 仅 Ralsei）。

    「只有ralsei能自由在其他暗世界走」—— 其他人「只能…回原先他们的暗世界」，
    跨章即拒（`REASON_FOREIGN_DARK`）。★ 这**不是**球给的能力
    （「其他人无法通过球去其他世界」）⇒ 与 `carried` 无关。
    """
    return is_dark_only(npc)


# ---------------------------------------------------------------- 电脑桌面闸

def desktop_allowed(npc):
    """这个 NPC **能不能上电脑桌面**。

    ★ 第56轮用户口径（逐字）：
      「其次，只有主角团最多加个lancer能来电脑桌面，其余的不能」
    ⇒ 白名单 = `DESKTOP_ALLOWED_IDS`（Ralsei / Kris / Susie / Lancer），
      取 `id` 的**精确相等**（不做前缀/别名匹配 —— `susiedark` 不是 `susie`）。
    """
    return getattr(npc, 'id', None) in DESKTOP_ALLOWED_IDS


def world_gate(npc, world, scene_id=None, carried=False):
    """NPC 能否进入 `world`（`'light'` / `'dark'`）的 `scene_id`。

    ★ 第50轮口径（用户原话逐字）
    -----------------------------
    「16项要，但只有ralsei能自由在其他暗世界走，其他人无法通过球去其他世界，
      只能去光世界或是回原先他们的暗世界（这个不需要他们套上球）」

    ★ 第56轮口径（用户原话逐字，**新增第 0 条**）
    ------------------------------------------
    「其次，只有主角团最多加个lancer能来电脑桌面，其余的不能」

    四条规则（**按本函数里的判断顺序**）：
    0. **电脑桌面**（`scene_id == 'desktop'`）—— **只有 `DESKTOP_ALLOWED_IDS` 能进**
       （Ralsei / Kris / Susie / Lancer）。
    1. **光世界**：**谁都能去，且不需要球**（"这个不需要他们套上球"）。
       唯一例外 = **Ralsei**（纯暗世界居民）：脱离暗世界**必须**被装进球
       （第49轮原口径「ralsei也不可以脱离暗世界，除非是…那个球」）。
    2. **暗世界**：只进**自己登记过的那几章**（"回原先他们的暗世界"）。
    3. **跨暗世界**：只有 Ralsei 自由（`free_dark_roam`）。
       「其他人无法通过球去其他世界」⇒ **球不给**跨暗世界能力。
    4. ★ **第72轮 —— 跨作品角色的穿行域**（`RoamScope`，**排在"暗世界"分支最前面**）：
       「niko可自由穿行所有世界，其余ut及其同人的任务只能在非暗世界穿梭」
       · `NON_DARK`（跨作品 60 位的默认档）：自己作品那一侧 ✅ / Deltarune 暗世界 ❌
       · `ALL`（**仅 Niko 一人**）：全部世界 ✅
       ⚠️ **光世界一侧不用改**：`light_needs_bubble` 只认 `is_dark_only`
       （`DARK_ONLY_IDS` + `escape_via_bubble`），跨作品角色从来就不在其中
       ⇒ 他们**从第49轮起本来就能进光世界**，与本条口径天然一致。
       这也是第71轮"跨作品角色 `home_world=dark` 会不会被球闸拦"那个疑点的答案：
       **不会** —— 拦人的是 `escape_via_bubble`，不是 `home_world`。

    ★★ 为什么第 0 条必须**排在第 1 条前面**（三条理由，缺一不可）
    ---------------------------------------------------------
    a) **数据层不区分**：`_worlds.json` 的 `overrides.desktop == "light"`
       ⇒ `scene_system.world_of_scene('desktop')` 返回 `'light'`，所以进到本函数时
       `world == 'light'`。若不先判 `scene_id`，第 1 条会直接 `light_free` 放行**所有** NPC
       —— 与用户口径完全相反。
    b) **桌面是 Ralsei 的家，不是"光世界"这个剧情概念**：`main.BEDTIME_HOME_SCENE == 'desktop'`，
       他**本来就住在桌面上**。若让它走第 1 条，Ralsei（纯暗世界居民）反而会被
       `REASON_LIGHT_NEEDS_BUBBLE` 拦下 ⇒ **他回不了自己家**。先判桌面即可解开这个矛盾。
    c) **契约不回归**：既有 13 组断言的 E 段（`verify_npc49.py` E1~E11）**没有任何一条**
       传 `scene_id='desktop'`，所以把新闸放在最前面**不会**改变它们的结论。

    :param carried: 是否**被装进球容器里**（只有 Ralsei 认这一条；桌面上不适用）。
    :param scene_id: 缺省 ⇒ 只按世界判，**不做章节判**（不猜）。
    """
    # ---- 0. 电脑桌面：白名单之外一律进不来（★ 必须先于光世界判，理由见 docstring）----
    if scene_id == DESKTOP_SCENE or world == DESKTOP_SCENE:
        if desktop_allowed(npc):
            return GateResult(True, REASON_OK, 'desktop_allowed')
        return GateResult(False, REASON_DESKTOP_FORBIDDEN,
                          '%s 不能来电脑桌面（只有主角团和 Lancer 可以）' % npc.name_cn)
    # ---- 光世界：谁都能去；只有"纯暗世界居民"必须靠球 ----
    if world == WORLD_LIGHT:
        if not light_needs_bubble(npc):
            return GateResult(True, REASON_OK, 'light_free')
        if carried:
            return GateResult(True, REASON_OK, 'carried_in_bubble')
        return GateResult(False, REASON_LIGHT_NEEDS_BUBBLE,
                          '%s 是暗世界居民，脱离暗世界必须被装进球' % npc.name_cn)
    if world != WORLD_DARK:
        return GateResult(False, REASON_LEAVE_DARK, '未知世界 %r' % (world,))
    # ---- 暗世界 ----
    ch = scene_chapter(scene_id)
    # ★ 第72轮：**跨作品角色的穿行域**先判。
    #
    # 用户口径（逐字）：「niko可自由穿行所有世界，其余ut及其同人的任务只能在
    #   非暗世界穿梭」⇒ `RoamScope.NON_DARK` / `ALL` 两档在这里落地。
    #
    # ★★ 为什么必须排在 `npc.chapters` 判空**之前**：
    #   跨作品角色的 `chapters` 填的是**作品名**（`'undertale'` / `'oneshot'` …），
    #   拿它去比 `'ch1'~'ch5'` 必然不命中 ⇒ 会掉进 `REASON_NO_CHAPTERS`
    #   （"没有登记任何暗世界"）—— 那是个**误导性**的拒绝理由：他们不是没登记，
    #   是**本来就不该来**。理由码必须说真话，否则调用方那句"他不能跟你去那里"
    #   会被读成"这孩子没家"。
    if npc.roam_scope != RoamScope.HOME:
        # ① 回自己作品的那一侧（`undertale.*` / `oneshot.*` …）—— 放行
        if ch is not None and ch in npc.chapters:
            return GateResult(True, REASON_OK, 'home_production:%s' % ch)
        # ② 全域通行 —— 仅 Niko（Deltarune 的暗世界也放行）
        if npc.roam_scope == RoamScope.ALL:
            return GateResult(True, REASON_OK, 'roam_all')
        # ③ 其余跨作品角色：Deltarune 的暗世界进不去
        return GateResult(False, REASON_FOREIGN_DARK,
                          '%s 只能在非暗世界穿梭' % npc.name_cn)
    if not npc.chapters:
        return GateResult(False, REASON_NO_CHAPTERS, '%s 没有登记任何暗世界' % npc.name_cn)
    if ch is None:
        return GateResult(True, REASON_OK, 'no_scene_id')
    if ch in npc.chapters:
        return GateResult(True, REASON_OK, ch)
    if free_dark_roam(npc):
        return GateResult(True, REASON_OK, 'free_dark_roam:%s' % ch)
    return GateResult(False, REASON_FOREIGN_DARK,
                      '%s 不属于 %s' % (ch, npc.name_cn))


# ---------------------------------------------------------------- 运行时：跟随板

class FollowerBoard(object):
    """运行时跟随状态机（无 Qt、无 IO，可单测）。

    状态：`idle → (pending) → active`，或 `idle → denied`。
    主线 NPC 直接 `idle → active`（自主跟随）。
    """

    def __init__(self, registry):
        self.reg = registry
        self._state = collections.OrderedDict()   # npc_id -> 状态
        self._refused = set()

    # -- 状态读取
    def state_of(self, nid):
        return self._state.get(nid, FOLLOW_IDLE)

    def is_following(self, nid):
        return self.state_of(nid) == FOLLOW_ACTIVE

    def followers(self):
        return [i for i, s in self._state.items() if s == FOLLOW_ACTIVE]

    def pending(self):
        return [i for i, s in self._state.items() if s == FOLLOW_PENDING]

    def snapshot(self):
        return collections.OrderedDict(self._state)

    # -- 动作
    def request(self, nid):
        """请求跟随。

        * 主线：直接生效（自主）⇒ 返回 `FOLLOW_ACTIVE`
        * 纯 NPC：进 `FOLLOW_PENDING`，等 `respond()` 收到主角同意
        * 未知 id / 不可跟随 ⇒ 返回 `FOLLOW_IDLE`（不抛）
        """
        npc = self.reg.get(nid)
        if npc is None or not can_follow(npc):
            return FOLLOW_IDLE
        if not needs_consent(npc):
            self._state[nid] = FOLLOW_ACTIVE
            return FOLLOW_ACTIVE
        self._state[nid] = FOLLOW_PENDING
        return FOLLOW_PENDING

    def respond(self, nid, approved):
        """主角对「纯 NPC 的跟随请求」表态（只有 pending 才受理）。"""
        if self.state_of(nid) != FOLLOW_PENDING:
            return False
        if approved:
            self._state[nid] = FOLLOW_ACTIVE
        else:
            self._state[nid] = FOLLOW_DENIED
            self._refused.add(nid)
        return True

    def stop(self, nid):
        if nid in self._state:
            self._state[nid] = FOLLOW_IDLE
            return True
        return False

    def may_enter(self, nid, world, scene_id=None, carried=False):
        """把「在不在跟随」和「能不能进这个世界」合并判定。"""
        npc = self.reg.get(nid)
        if npc is None:
            return GateResult(False, REASON_NO_CHAPTERS, 'unknown npc %r' % (nid,))
        return world_gate(npc, world, scene_id=scene_id, carried=carried)

    def tick(self, world, scene_id=None, carried_ids=()):
        """按当前位置清理**进不来**的跟随者。

        返回被踢出的 npc_id 列表（调用方据此提示"他不能跟你去那里"）。
        自动跟随者若被踢出，状态回 `idle`（不是 denied）——他还会在下个合法场景重新跟上。
        """
        carried = set(carried_ids or ())
        kicked = []
        for nid in list(self._state.keys()):
            if self._state.get(nid) != FOLLOW_ACTIVE:
                continue
            g = self.may_enter(nid, world, scene_id=scene_id, carried=nid in carried)
            if not g.ok:
                self._state[nid] = FOLLOW_IDLE
                kicked.append(nid)
        return kicked

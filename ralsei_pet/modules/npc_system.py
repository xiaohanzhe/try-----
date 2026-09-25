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

设计
----
1. **分层**：`NpcTier.MAIN`（主线，配 4B 模型）/ `NpcTier.PLAIN`（纯 NPC，内置短对话）。
2. **跟随**：主线 = `FollowPolicy.AUTONOMOUS`；纯 NPC = `FollowPolicy.CONSENT`
   （要主角同意或主动要求）。两者**都能跟**，差别只在"谁发起"。
3. **世界门控**：NPC 不可脱离暗世界、不可进入不属于自己的暗世界；
   唯一的豁免是第 49 轮的**球容器**（`bubble_system`）——被装进球里才能进光世界。
   Ralsei 同样受此约束（他是主角团，但同为暗世界居民）。

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

DEFAULT_MAIN_MODEL = 'ralsei-npc:4b'      # 主线 NPC 的 4B 句柄（设定由用户提供后再定稿）


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
    NpcTier.MAIN: 'llm',        # 走模型（4B）
    NpcTier.PLAIN: 'builtin',   # 走内置短对话
}

WORLD_LIGHT = 'light'
WORLD_DARK = 'dark'

# 门控结果码
REASON_OK = 'ok'
REASON_LEAVE_DARK = 'leave_dark_world'    # 想脱离暗世界
REASON_FOREIGN_DARK = 'foreign_dark_world'  # 进入不属于他的暗世界
REASON_NO_CHAPTERS = 'no_chapters'        # 登记里没有可用章节 ⇒ 不硬判，拒绝

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
                 'escape_via_bubble', 'lines')

    def __init__(self, id, name='', name_cn='', tier=NpcTier.PLAIN,
                 chapters=(), home_world=WORLD_DARK, objects=(), model=None,
                 needs_setting=False, notes='', escape_via_bubble=False, lines=()):
        self.id = id
        self.name = name or id
        self.name_cn = name_cn or self.name
        self.tier = tier if tier in NpcTier.ALL else NpcTier.PLAIN
        self.chapters = tuple(chapters)
        self.home_world = home_world if home_world in (WORLD_LIGHT, WORLD_DARK) else WORLD_DARK
        self.objects = tuple(objects)
        self.model = model
        self.needs_setting = bool(needs_setting)
        self.notes = notes
        #: 是否**只能靠球**离开暗世界（Ralsei 专属；其他 NPC 一律不许离开）
        self.escape_via_bubble = bool(escape_via_bubble)
        self.lines = tuple(lines)

    def to_dict(self):
        return collections.OrderedDict((
            ('id', self.id), ('name', self.name), ('name_cn', self.name_cn),
            ('tier', self.tier), ('chapters', list(self.chapters)),
            ('home_world', self.home_world), ('objects', list(self.objects)),
            ('model', self.model), ('needs_setting', self.needs_setting),
            ('escape_via_bubble', self.escape_via_bubble),
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


def world_gate(npc, world, scene_id=None, carried=False):
    """NPC 能否进入 `world`（`'light'` / `'dark'`）的 `scene_id`。

    * `carried=True` 表示**被装进球容器里**（只有 `escape_via_bubble` 的 NPC 才认这一条）。
    * 光世界：一律拒绝（「不可脱离暗世界」），除非 `carried` 且该 NPC 允许靠球脱离。
    * 暗世界：`scene_id` 所属章节必须在该 NPC 的登记章节里，否则「不属于他的暗世界」。
    * `scene_id` 缺失 ⇒ 只按世界判，不做章节判（不硬判）。
    """
    if world == WORLD_LIGHT:
        if carried and npc.escape_via_bubble:
            return GateResult(True, REASON_OK, 'carried_in_bubble')
        return GateResult(False, REASON_LEAVE_DARK,
                          '%s 不能脱离暗世界' % npc.name_cn)
    if world != WORLD_DARK:
        return GateResult(False, REASON_LEAVE_DARK, '未知世界 %r' % (world,))
    if not npc.chapters:
        return GateResult(False, REASON_NO_CHAPTERS, '%s 没有登记任何暗世界' % npc.name_cn)
    ch = scene_chapter(scene_id)
    if ch is None:
        return GateResult(True, REASON_OK, 'no_scene_id')
    if ch not in npc.chapters:
        return GateResult(False, REASON_FOREIGN_DARK,
                          '%s 不属于 %s' % (ch, npc.name_cn))
    return GateResult(True, REASON_OK, ch)


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

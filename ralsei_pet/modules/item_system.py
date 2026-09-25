# -*- coding: utf-8 -*-
"""道具系统 —— 「道具效果不出章节 / 回光世界变垃圾团 / 异域使用被神秘力量阻止」。

回答用户这条需求（第 48 轮）
----------------------------
    「对于里面可互动的道具也要做到可以互动，当然，道具效果不可带出当前章节的场景，
      也就回到光世界的时候暗世界的任何道具都会变成垃圾团里包含的东西，道具效果就直接消失，
      如果在其他场景使用非当前场景的道具那就显示"一股神秘的力量阻止了你"。
      对了，游戏里的背包这类的通过S键实现的菜单也要应用哦，但，设置不应用」

拆成 4 条可验收的行为
--------------------
1. **两套袋子**（照抄原作）：暗世界 `item[12]`、光世界 `litem[8]`，容量五章一致。
2. **回光世界 ⇒ 暗世界道具变垃圾团**：效果清零、名字保留、进 `junk` 容器。**不可逆**。
3. **异域使用 ⇒ 神秘力量**：道具的"出身域"≠ 当前域（章节 / 世界 / 场景门控）时，
   统一返回 `VERDICT_MYSTERY` + 文案「一股神秘的力量阻止了你」。
4. 菜单（`item_menu`）与 UI（`item_menu_ui`）**只管展示**，全部判定走本模块。

零依赖纪律（🔴 与 companion / scene_system / scene_pathfind 同源）
----------------------------------------------------------------
本模块**禁 import Qt、禁 import 任何项目内模块**（只准标准库）。
`main.py` 在 import 期就会建控制器，控制器再 import 本模块；
回头 import 项目内模块会把「初始化环」接上（本项目已踩 4 次，
症状是 import 期直接崩、零输出）。⇒ 本文件只准 `collections` / `json` / `logging` / `os`。

★ 原作依据（第 48 轮 UTMT 反编译取证）
  · `scr_itemget` / `scr_litemget` —— 两个袋子 + 容量 + 哨兵 999 的写法
  · `scr_itemuse` / `scr_litemuseb` —— 每个 id 的效果（**逐条**，见 `_evidence/items_effects48.json`）
  · `scr_litemuseb` `case 201` 的 `if (room == room_krisroom || room == room_krishallway
    || room == room_torbathroom)` —— 「按场景门控」的一手依据
  · `obj_overworldc_Step_0` 的 `dontthrow` 名单（id 5 / id 11 丢不掉）

★ 三条设计律
-------------
1. **不静默降级** —— 查不到的道具定义返回"未知道具"（名字 `？？？`），
   但**绝不**把它当成"大概能用"；判定结果必须显式落在某个 verdict 上。
2. **垃圾化不可逆** —— 用户原话是「道具效果**就**直接消失」。
   若做成"回暗世界又恢复"，那就是我们替用户改需求。⇒ 常量 `JUNK_IS_PERMANENT = True`，
   想改必须显式改这个常量（而不是悄悄改行为）。
3. **数值照抄，出处可查** —— 12 / 8 两个容量、`？？？` 表示法、门控房间集合
   全部有出处；本项目自创的（垃圾团容器、文案）单独标注「产品口径」。

「产品口径」（原作没有的，明确标出来）
--------------------------------------
· **「垃圾团」这个容器**：跨五章普查里 `junk` 只命中 ch2 的 `obj_queen_search_junk`（Boss），
  原作**没有**"道具变垃圾"这个机制符号。这是产品为了实现用户口径而定义的概念。
· **「一股神秘的力量阻止了你」这句话**：原作没有任何一句这种文案
  （详版取证 §3）。但「按场景门控道具」这个**结构**是原作的。
"""
import collections
import json
import logging
import os

_log = logging.getLogger(__name__)

# ===========================================================================
#  常量
# ===========================================================================

#: ★ 照抄 `obj_overworldc` / `obj_darkcontroller` 的 `global.darkzone` 取值域。
WORLD_LIGHT = 'light'
WORLD_DARK = 'dark'
WORLDS = (WORLD_DARK, WORLD_LIGHT)

#: ★ 两个袋子的容量 —— 照抄 `scr_itemget`（`global.item[12] = 999`）与
#: `scr_litemget`（`global.litem[8] = 999`）。第48轮五章普查确认**逐章一致**。
BAG_CAPACITY = {WORLD_DARK: 12, WORLD_LIGHT: 8}

#: ★ 哨兵值 —— 照抄原作把"最后一格"写成 999 来让循环撞到边界时判满。
#: 本实现不真的把哨兵写进格子（那是原作的实现细节），但保留这个数用于自检：
#: `Bag.free()` 永远不会回传它。
BAG_SENTINEL = 999

#: 「产品口径」—— 回光世界后暗世界道具的归处。
JUNK_BALL_NAME = '垃圾团'

#: ⚠️ 用户口径的兜底文案（**产品自定，非原作文本**）。
MSG_MYSTERY = '一股神秘的力量阻止了你'

#: 「产品口径」—— 垃圾化是否不可逆。见模块 docstring 设计律 2。
JUNK_IS_PERMANENT = True

#: 未知道具的显示名（原作对未知道具就用 `？？？`）。
UNKNOWN_NAME = '？？？'

#: 四个判定结果（字符串常量，便于直接进 JSON / 日志）。
VERDICT_OK = 'ok'              #: 用得出去
VERDICT_EMPTY = 'empty'        #: 那一格是空的
VERDICT_JUNK = 'junk'          #: 已经变成垃圾团里的东西，效果为 0
VERDICT_MYSTERY = 'mystery'    #: 被"神秘力量"挡住（异章节 / 异世界 / 场景门控）

#: 各 verdict 对应的默认文案（`None` = 不弹话）。
VERDICT_MESSAGE = {
    VERDICT_OK: None,
    VERDICT_EMPTY: None,
    VERDICT_JUNK: '它已经变成垃圾团里的东西了，什么也不会发生。',
    VERDICT_MYSTERY: MSG_MYSTERY,
}

#: ★★ 按场景门控的道具 —— 照抄 `scr_litemuseb` `case 201` 的 `room ==` 白名单。
#: 键 = (章节, 世界, 道具 id)，值 = 允许的**原作房间 id 集合**。
#: 为什么用"原作房间 id"而不是我们自己的 scene_id：原作的判据就是房间常量，
#: 我们的场景索引里恰好带 `original_room_id`（`assets/scenes/_index.json`），
#: 直接对齐它就等于对齐原作，且新增场景时不用回来改这里。
#:
#:   room_krisroom(2) / room_krishallway(3) / room_torhouse(5) / room_torbathroom(6)
GATED_ROOM_IDS = {
    ('ch1', WORLD_LIGHT, 201): frozenset({2, 3, 5, 6}),
}

#: ★ 丢不掉的 id —— 照抄 `obj_overworldc_Step_0` 的 `dontthrow` 名单。
DONT_THROW = {(WORLD_LIGHT, 5), (WORLD_LIGHT, 11)}


# ===========================================================================
#  道具定义 / 目录
# ===========================================================================

class ItemDef(object):
    """一条道具定义（只读，来自 `assets/items/<chapter>.json`）。

    没有名字就是 `None`（显示成 `？？？`）—— 语言包不随 data.win 分发，
    我们拿不到原作中文文本，所以**宁缺勿造**（见模块 docstring）。
    """

    __slots__ = ('id', 'world', 'name', 'name_source', 'desc', 'kind', 'target',
                 'amount', 'per_char', 'consumable', 'droppable', 'scene_gate', 'src')

    def __init__(self, raw, world):
        self.id = int(raw.get('id', 0))
        self.world = world
        self.name = raw.get('name')
        self.name_source = raw.get('name_source')
        self.desc = raw.get('desc')
        self.kind = raw.get('kind') or 'none'
        self.target = raw.get('target') or 'none'
        self.amount = raw.get('amount')
        self.per_char = raw.get('per_char') or None
        self.consumable = bool(raw.get('consumable'))
        self.droppable = bool(raw.get('droppable', True))
        self.scene_gate = bool(raw.get('scene_gate'))
        self.src = raw.get('src')

    @property
    def display_name(self):
        return self.name or UNKNOWN_NAME

    @property
    def known(self):
        """有没有可靠名字（`name_source` 非空即视为有出处）。"""
        return bool(self.name and self.name_source)

    def __repr__(self):
        return '<ItemDef %s.%s#%d %s kind=%s>' % (
            self.world, self.display_name, self.id, self.name_source or '-', self.kind)


def unknown_def(item_id, world):
    """造一个"未知道具"定义 —— **不静默降级**，而是显式标成未知。"""
    return ItemDef({'id': item_id, 'name': None, 'kind': 'none'}, world)


class ItemCatalog(object):
    """章节道具表（惰性加载章节文件，带缓存）。

    用法::

        cat = ItemCatalog('ralsei_pet/assets/items')
        cat.get('ch1', 'dark', 1).display_name   # -> '黑暗糖果'
    """

    def __init__(self, root):
        self.root = root
        self._index = None
        self._chapters = {}
        self.load_errors = []

    # ---------------------------------------------------------------- 索引
    @property
    def index(self):
        if self._index is None:
            self._index = self._read('_index.json') or {}
        return self._index

    def _read(self, name):
        p = os.path.join(self.root, name)
        try:
            with open(p, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception as exc:      # 文件缺失 / JSON 坏 ⇒ 记下来，不抛
            self.load_errors.append('%s: %s' % (name, exc))
            _log.warning('道具表读取失败 %s: %s', p, exc)
            return None

    # ---------------------------------------------------------------- 章节
    def chapter(self, chapter):
        if chapter not in self._chapters:
            self._chapters[chapter] = self._read(chapter + '.json') or {}
        return self._chapters[chapter]

    def chapter_ids(self):
        return sorted((self.index.get('chapters') or {}).keys())

    def bag_capacity(self, world):
        """★ 容量优先读数据文件（`bags`），缺失时回落到实证常量。"""
        cap = (self.index.get('bag_capacity') or {}).get(world)
        return int(cap) if cap else BAG_CAPACITY.get(world, 0)

    # ---------------------------------------------------------------- 取定义
    def get(self, chapter, world, item_id):
        """取定义。表中没有 ⇒ 返回"未知道具"（**不是 None**，见设计律 1）。"""
        world_key = WORLD_DARK if world == WORLD_DARK else WORLD_LIGHT
        rec = (self.chapter(chapter).get('items') or {}).get(world_key) or {}
        raw = rec.get(str(int(item_id)))
        if not isinstance(raw, dict):
            return unknown_def(item_id, world_key)
        return ItemDef(raw, world_key)

    def has(self, chapter, world, item_id):
        rec = (self.chapter(chapter).get('items') or {}).get(world) or {}
        return str(int(item_id)) in rec


# ===========================================================================
#  背包 / 垃圾团
# ===========================================================================

class Slot(object):
    """一个背包格 —— 记录**道具 + 出身域**。

    为什么格子要记出身域：用户口径是"道具效果不可带出当前章节的场景"，
    那就必须知道这件道具**是从哪个章节/世界拿到的**。只记 `item_id` 做不到这一点。
    """

    __slots__ = ('item', 'origin_chapter', 'origin_world', 'junked')

    def __init__(self, item, origin_chapter, origin_world, junked=False):
        self.item = item
        self.origin_chapter = origin_chapter
        self.origin_world = origin_world
        self.junked = bool(junked)

    @property
    def display_name(self):
        return self.item.display_name

    def __repr__(self):
        return '<Slot %s@%s/%s%s>' % (self.display_name, self.origin_chapter,
                                      self.origin_world, ' JUNK' if self.junked else '')


class Bag(object):
    """定容背包 —— **照抄原作的"第一个空格"语义**（不堆叠、不排序）。

    `scr_itemget` 的行为是：从 0 开始线性找第一个 `== 0` 的格子放进去，
    撞到容量就 `noroom = 1`。本类逐条对齐。
    """

    def __init__(self, world, capacity):
        self.world = world
        self.capacity = int(capacity)
        self.slots = [None] * self.capacity

    def __len__(self):
        return sum(1 for s in self.slots if s is not None)

    @property
    def full(self):
        return all(s is not None for s in self.slots)

    def first_free(self):
        """★ 照抄 `scr_itemget` 的线性探测：返回第一个空格下标，满则 `-1`。"""
        for i in range(self.capacity):
            if self.slots[i] is None:
                return i
        return -1

    def add(self, item, origin_chapter, origin_world):
        """放进第一个空格。满 ⇒ `(False, -1)`（**不覆盖、不丢最旧**，同原作 `noroom`）。"""
        i = self.first_free()
        if i < 0:
            return False, -1
        self.slots[i] = Slot(item, origin_chapter, origin_world)
        return True, i

    def remove_at(self, index):
        """★ 照抄 `scr_itemshift`：抽掉一格后**后面的往前补**（不留空洞）。"""
        if not (0 <= index < self.capacity):
            return None
        gone = self.slots[index]
        del self.slots[index]
        self.slots.append(None)
        return gone

    def at(self, index):
        if not (0 <= index < self.capacity):
            return None
        return self.slots[index]

    def iter_filled(self):
        for i, s in enumerate(self.slots):
            if s is not None:
                yield i, s

    def clear(self):
        self.slots = [None] * self.capacity

    def __repr__(self):
        return '<Bag %s %d/%d>' % (self.world, len(self), self.capacity)


class JunkBall(object):
    """「垃圾团」—— **产品口径**（原作无此符号，见模块 docstring）。

    只存**名字**：用户口径是"效果就直接消失"，那留着 `ItemDef` 反而会让
    "能不能再用"变成可争论的问题。只留名字，能力上就不可能再用。
    """

    def __init__(self, name=JUNK_BALL_NAME):
        self.name = name
        self.entries = []          # list[dict] —— {'from': (chapter, world), 'name': str, 'id': int}

    def add(self, slot):
        rec = {
            'id': slot.item.id,
            'name': slot.display_name,
            'from_chapter': slot.origin_chapter,
            'from_world': slot.origin_world,
        }
        self.entries.append(rec)
        return rec

    def __len__(self):
        return len(self.entries)

    def __contains__(self, value):
        return any(e['name'] == value for e in self.entries)

    def names(self):
        return [e['name'] for e in self.entries]

    def clear(self):
        self.entries = []

    def __repr__(self):
        return '<JunkBall %d 件>' % len(self.entries)


# ===========================================================================
#  判定结果
# ===========================================================================

#: `Inventory.use()` 的返回值。
#: `heal` —— 若 kind 是治疗类，这里给出"这次实际生效的回复量"（0 = 没生效）。
UseOutcome = collections.namedtuple(
    'UseOutcome', ('verdict', 'message', 'item', 'healed', 'consumed', 'slot_index'))


# ===========================================================================
#  背包总成
# ===========================================================================

class Inventory(object):
    """两个袋子 + 一个垃圾团 + 当前域。**所有**道具判定都在这里。

    参数
    ----
    catalog : ItemCatalog
    chapter : str   当前章节（`ch1`..`ch5`）
    world   : str   当前世界（`dark` / `light`）
    scene   : str | None
        当前 scene_id（只用于日志/诊断）。
    original_room_id : int | None
        ★ 当前场景对应的**原作房间 id** —— 场景门控用的就是它（见 `GATED_ROOM_IDS`）。
    """

    def __init__(self, catalog, chapter='ch1', world=WORLD_DARK,
                 scene=None, original_room_id=None):
        self.catalog = catalog
        self.bags = {
            WORLD_DARK: Bag(WORLD_DARK, catalog.bag_capacity(WORLD_DARK)),
            WORLD_LIGHT: Bag(WORLD_LIGHT, catalog.bag_capacity(WORLD_LIGHT)),
        }
        self.junk = JunkBall()
        self.chapter = chapter
        self.world = world if world in WORLDS else WORLD_DARK
        self.scene = scene
        self.original_room_id = original_room_id
        self.junk_events = 0        #: 统计：一共把多少件道具变成了垃圾（诊断用）
        self.mystery_hits = 0       #: 统计：被"神秘力量"挡了几次（诊断用）

    # ---------------------------------------------------------------- 切域
    def enter(self, chapter, world, scene=None, original_room_id=None):
        """切到 (章节, 世界, 场景)。

        返回本次**新变成垃圾**的道具名字列表（便于 UI 提示 / 断言）。
        """
        world = world if world in WORLDS else WORLD_DARK
        moved = []
        if world == WORLD_LIGHT and self.world != WORLD_LIGHT:
            moved = self._junkify_dark_bag()
        self.chapter = chapter
        self.world = world
        self.scene = scene
        self.original_room_id = original_room_id
        return moved

    def _junkify_dark_bag(self, world=None):
        """★ 用户口径的核心动作：暗世界道具 ⇒ 垃圾团（效果清零、名字保留）。"""
        bag = self.bags.get(world or WORLD_DARK)
        if bag is None:
            return []
        moved = []
        for _, slot in list(bag.iter_filled()):
            if slot.junked:
                continue          # 已经是垃圾，不重复计数
            slot.junked = True
            slot.item = _seedless(slot.item)
            self.junk.add(slot)
            moved.append(slot.display_name)
            self.junk_events += 1
        if moved:
            _log.info('回到光世界：%d 件暗世界道具变成「%s」：%s',
                      len(moved), self.junk.name, '、'.join(moved))
        return moved

    # ---------------------------------------------------------------- 拾取
    def pick_up(self, item_id, world=None, chapter=None):
        """捡到一件道具（出身域默认 = 当前域）。

        返回 `(成功?, 下标)`。背包满 ⇒ `(False, -1)`（同原作 `noroom`）。
        """
        w = world or self.world
        ch = chapter or self.chapter
        item = self.catalog.get(ch, w, item_id)
        bag = self.bags.get(w)
        if bag is None:
            return False, -1
        return bag.add(item, ch, w)

    # ---------------------------------------------------------------- 使用
    def use(self, world, index):
        """★ 唯一的使用入口。判定顺序 = 优先级（先判"是不是垃圾"，再判"是不是异域"）。

        为什么要先判垃圾：一件道具**同时**可能是"已垃圾化"且"异世界"的。
        用户口径里"垃圾"是更强的状态（效果**就**消失），所以垃圾优先。
        """
        bag = self.bags.get(world)
        if bag is None:
            return UseOutcome(VERDICT_EMPTY, None, None, 0, False, index)

        slot = bag.at(index)
        if slot is None:
            return UseOutcome(VERDICT_EMPTY, VERDICT_MESSAGE[VERDICT_EMPTY],
                              None, 0, False, index)

        if slot.junked:
            return UseOutcome(VERDICT_JUNK, VERDICT_MESSAGE[VERDICT_JUNK],
                              slot.item, 0, False, index)

        reason = self.blocked_reason(slot, world)
        if reason is not None:
            self.mystery_hits += 1
            _log.info('使用道具被阻止（%s）：%s', reason, slot.display_name)
            return UseOutcome(VERDICT_MYSTERY, MSG_MYSTERY, slot.item, 0, False, index)

        healed = _effect_amount(slot.item)
        consumed = False
        if slot.item.consumable:
            moved = bag.remove_at(index)
            consumed = moved is not None
        return UseOutcome(VERDICT_OK, VERDICT_MESSAGE[VERDICT_OK],
                          slot.item, healed, consumed, index)

    def blocked_reason(self, slot, world):
        """能不能用？能用返回 `None`，否则返回一句**中文原因**（诊断/日志用）。"""
        if slot.origin_chapter != self.chapter:
            return '道具出自 %s，当前是 %s' % (slot.origin_chapter, self.chapter)
        if slot.origin_world != world:
            return '道具出自 %s 世界，当前是 %s 世界' % (slot.origin_world, world)
        if slot.origin_world != self.world:
            return '道具出自 %s 世界，当前域是 %s 世界' % (slot.origin_world, self.world)
        if slot.item.scene_gate:
            allowed = GATED_ROOM_IDS.get((self.chapter, world, slot.item.id))
            if allowed is None:
                # ⚠️ 数据说"要门控"，但产品没登记白名单 ⇒ **不静默放行**。
                #    放行等于把"按场景门控"这条需求悄悄丢掉。
                return '该道具声明了场景门控，但没有登记白名单（%s/%s#%d）' % (
                    self.chapter, world, slot.item.id)
            if self.original_room_id is None:
                return '无法确定当前原作房间 id，不能判定场景门控'
            if int(self.original_room_id) not in allowed:
                return '道具限定在原作房间 %s 内使用，当前房间 %s' % (
                    sorted(allowed), self.original_room_id)
        return None

    # ---------------------------------------------------------------- 查询
    def bag(self, world=None):
        return self.bags.get(world or self.world)

    def visible_rows(self, world=None):
        """给菜单用的展示行：`(下标, 显示名, 是否垃圾, 是否可用)`。

        「是否可用」直接用 `blocked_reason` —— 菜单与使用走**同一套**判据，
        不会出现"菜单里亮着、按下去被拒"这种不一致。
        """
        w = world or self.world
        bag = self.bags.get(w)
        rows = []
        if bag is None:
            return rows
        for i, slot in bag.iter_filled():
            usable = (not slot.junked) and self.blocked_reason(slot, w) is None
            rows.append((i, slot.display_name, bool(slot.junked), usable))
        return rows

    def describe(self):
        """一行中文摘要（日志 / 报告用，**不参与任何判据**）。"""
        return '域=%s/%s 暗袋 %d/%d 光袋 %d/%d 垃圾团 %d 件' % (
            self.chapter, self.world,
            len(self.bags[WORLD_DARK]), self.bags[WORLD_DARK].capacity,
            len(self.bags[WORLD_LIGHT]), self.bags[WORLD_LIGHT].capacity,
            len(self.junk))


# ===========================================================================
#  小工具
# ===========================================================================

def _seedless(item):
    """把一件道具"掏空"成纯名字 —— 垃圾团成员的能力面。

    实现上**不是**把 kind 改成 'none'（那还留着 amount/per_char 等字段，
    以后有人读 `amount` 就会读到旧值），而是换成一份只保留身份的新定义。
    """
    return ItemDef({'id': item.id, 'name': item.name, 'name_source': item.name_source,
                    'desc': item.desc, 'kind': 'none', 'consumable': False,
                    'droppable': False, 'src': item.src}, item.world)


def _effect_amount(item):
    """这次使用**实际生效**的回复量（只对治疗类有意义；其它返回 0）。

    判定"用不出去"是 `blocked_reason` 的活，这里只算数。
    """
    if item.kind in ('heal', 'heal_all', 'revive', 'per_char'):
        if item.amount is not None:
            return int(item.amount)
        if item.per_char:
            return sum(int(v) for v in item.per_char.values())
    return 0


def assets_dir():
    """道具表目录：`<ralsei_pet>/assets/items`。

    与 `dr_textbox.assets_dir()` **同一写法**（本模块零依赖，不 import 任何项目模块，
    所以自己算一遍路径）。`modules/../assets/items`。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, '..', 'assets', 'items'))


def load_catalog(root=None):
    """便捷入口：建目录并顺手报错（接线层用）。

    `root=None` ⇒ 自动用 `assets_dir()`（这样接线层不必知道路径约定）。
    """
    cat = ItemCatalog(root or assets_dir())
    cat.index          # 触发一次加载
    if cat.load_errors:
        _log.warning('道具表有 %d 处读取问题：%s', len(cat.load_errors), cat.load_errors)
    return cat

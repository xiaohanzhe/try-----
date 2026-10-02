# -*- coding: utf-8 -*-
"""可交互物分类与接线 —— 把场景 `objects` 里的原件名**分类**并接上 `Interactable` 协议。

回答用户这条需求（第 48 轮）
----------------------------
    「对于里面可互动的道具也要做到可以互动，当然，道具效果不可带出当前章节的场景，……」

本模块负责其中两件事：
  · **分类**：`objects[].src`（原作对象名）→ 一份可交互物定义（哪一类、要不要上锁、给不给东西）
  · **接线**：转成 `companion.Interactable` 子类实例，挂到 `InteractBus` 上

零依赖纪律
----------
本模块**只 import 标准库 + `companion`**（`companion` 本身就是零依赖 L1，见其 docstring）。
**禁 import Qt、禁 import 其它项目内模块** —— 与 companion / item_system 同源理由
（`main.py` import 期建控制器，回头 import 会接上初始化环）。

★ 数据现状（**第68轮已补采；先看这段再动手**）
------------------------------------------------
第48轮这里登记过一个缺口：`obj_readable` / 宝箱 / 拾取 / 招牌 / 可调查家具
**一件实例都没有**。第68轮补上了，根因有**三个 —— 只修一个都不够**：

  1. **普查没采**：第42轮 `inst42.csx` 的关键词表里没有
     `readable / sign / chest / treasure / pickup / interactable / desk …`
     ⇒ 这些类的实例**从未被导出**（不是"采了没收"，是"根本没采"）。
     第68轮 `inst68.csx` 把关键词扩到 14+13 个，五章实例 5,523 → **6,889**。
  2. **对象表只有 ch1 的**：第44轮生成器拿 **ch1 的 353 个对象**去匹配**全五章**的实例，
     ch2~5 独有的对象名查不到 sprite 一律丢弃。实证：`obj_board_pickup` 只在
     `chapter3_objmap43.txt` 里 ⇒ 它虽被采到、素材也搬了，却**永远进不了 objects**。
     第68轮改为**按章取表**（ch1 仍用 `objmap43.txt`，故 ch1 不漂移）。
  3. **sprite 不在仓库**：`object()` 有一条"无素材跳过"⇒ sprite 没进
     `assets/scenes/objs/` 就等于不存在。第68轮一并搬了该类用到的 12 个 sprite。

★ 现在真正能互动的（分类 → 实现）
-----------------------------------
| 分类 | 实现类 | 行为出处 |
|---|---|---|
| `savepoint` | `SavePointProp` | `obj_savepoint_Other_10`：按 `room` 给台词 + **全队回满 HP** |
| `fountain` | `FountainProp` | 暗之泉（产品第一站 = `ch1.room_town_north`，见 §43.6） |
| `pickup` | `PickupProp` | 落点表驱动（`assets/items/pickups.json`）；**没有表就如实不建物** |
| `readable` / `sign` | `ReadableProp` | 产品口径文本（原文本在外部语言包，拿不到） |
| `chest` / `interactable` / `furniture` | `InspectProp` | 同上；第68轮新增（此前落进 `else` 被静默丢弃） |
| `door` | —— | 交回**路由层**（`classify` 标 `handled_by='scene_routing'`） |
"""
import collections
import json
import logging


def _pet_logger_name(_name):
    """把模块 `__name__` 映射到 `ralsei_pet.` 命名空间下的名字。

    ★ 为什么需要它（第75轮实测）：一批模块历史上用**扁平导入**取日志器
      （`try: from logger_utils import get_logger / except ImportError: 降级`）。
      当 main.py 以**包形式**加载（`from modules.x import ...`）时，
      模块内 `from logger_utils import ...` 必然 ImportError ⇒ 静默走降级
      ⇒ 拿到**裸 logger**（`modules.xxx`）⇒ 两个后果：
        ① 不在 `ralsei_pet` 树下 ⇒ 挂在根上的**文件 handler 收不到**；
        ② 没有祖先 `setLevel(INFO)` ⇒ 有效级别退回 **30 (WARNING)** ⇒ INFO 全丢。
      表现就是"故障查不到"、"日志里零故障记录"。

    ★ 为什么用标准库字符串运算而不是 import `logger_utils`：
      `logging` 是**进程级全局注册表** —— 只要名字拼对，拿到的就是同一个对象。
      所以本函数**一行项目 import 都不需要**，从而不违反纯数据层的
      「零依赖 / 白名单」契约（`scene_render` 顶层 import ⊆ logging、
      `team_hp` 禁 `from modules`、`soul_overlay` 不拖业务模块 … 那几条闸）。
    """
    if not _name or _name == '__main__':
        return 'ralsei_pet.main'
    if _name.startswith('ralsei_pet.'):
        return _name
    if _name.startswith('modules.'):
        return 'ralsei_pet.' + _name
    return 'ralsei_pet.' + _name

import os

from companion import Interactable

_log = logging.getLogger(_pet_logger_name(__name__))

# ===========================================================================
#  分类表
# ===========================================================================

#: 分类 → 中文名（报告/日志用）。
KIND_LABEL = {
    'savepoint': '存档点',
    'fountain': '暗之泉',
    'door': '门',
    'readable': '可读物',
    'sign': '招牌',
    'interactable': '可交互物',
    'chest': '宝箱',
    'pickup': '拾取物',
    'furniture': '可调查家具',
    'cutscene': '演出触发器',
}

#: ★ 原件名 → 分类登记表。`in_data` = 我们的场景数据里**到底有没有**这个类。
#: 没数据的一律写 `gap`，说明缺在哪一步（别让读者以为是漏写）。
PROP_CLASSES = {
    # ---- 有数据：本轮可互动 -------------------------------------------------
    'obj_savepoint': {'kind': 'savepoint', 'in_data': True},
    'obj_ch2_room_city_savepoint': {'kind': 'savepoint', 'in_data': True},
    'obj_dw_church_savepoint': {'kind': 'savepoint', 'in_data': True},
    'obj_dw_churchb_savepoint': {'kind': 'savepoint', 'in_data': True},
    'obj_dw_churchc_savepoint': {'kind': 'savepoint', 'in_data': True},
    'obj_dw_churchc_savepoint_judgmentbell': {'kind': 'savepoint', 'in_data': True},

    'obj_darkfountain': {'kind': 'fountain', 'in_data': True},
    'obj_fountainkris': {'kind': 'fountain', 'in_data': True},
    'obj_fountainkris_ch2_sideb': {'kind': 'fountain', 'in_data': True},
    'obj_ch4_DCA12_darkfountain': {'kind': 'fountain', 'in_data': True},
    'obj_ch5_DW45_fountain': {'kind': 'fountain', 'in_data': True},
    'obj_dw_churchb_fountain': {'kind': 'fountain', 'in_data': True},
    'obj_dw_post_fountain_close': {'kind': 'fountain', 'in_data': True},

    'obj_shortcut_door': {'kind': 'door', 'in_data': True},
    'obj_darkdoor': {'kind': 'door', 'in_data': True},
    'obj_darkdoorevent': {'kind': 'door', 'in_data': True},

    # ---- 第68轮实例补采后**已有实例**的类（判据 = 产物里真有条数，见 verify_items68）----
    #   不再标 `gap`：缺口已经补上，留着旧说明就是"假话"（比没有注释更糟）。
    'obj_readable_room1': {'kind': 'readable', 'in_data': True},
    'obj_npc_sign': {'kind': 'sign', 'in_data': True},
    'obj_treasure_room': {'kind': 'chest', 'in_data': True},
    'obj_schooldesk': {'kind': 'furniture', 'in_data': True},
    'obj_alphysdesk': {'kind': 'furniture', 'in_data': True},
    'obj_board_pickup': {'kind': 'pickup', 'in_data': True},
    'obj_bug_treasure_chest': {'kind': 'chest', 'in_data': True},

    # ---- 仍是缺口：登记在册，但第68轮全量普查 + 产物里 **0 条实例** ----
    #   措辞写清"缺的是什么"：不是"没采"，而是"数据里这个名字就没有房间在用"。
    'obj_readable': {'kind': 'readable', 'in_data': False,
                     'gap': '第68轮普查已覆盖 readable 键，但 ch1~5 实例里 0 条'
                            '（spr_interactable 已进 objs/，有房间用它即可用）'},
    'obj_board_readable': {'kind': 'readable', 'in_data': False,
                           'gap': 'ch3 棋盘章专用，普查里 0 条实例'},
    'obj_interactable': {'kind': 'interactable', 'in_data': False,
                         'gap': 'objmap43 里该对象 `spr=` 为空（运行时才给图）⇒ 不可绘制、进不了 objects'},
    'obj_interactablesolid': {'kind': 'interactable', 'in_data': False,
                              'gap': '同上；且普查里 0 条实例'},
    'obj_board_interactable': {'kind': 'interactable', 'in_data': False,
                               'gap': 'ch3 棋盘章，0 条实例'},
    'obj_board_heal_pickup': {'kind': 'pickup', 'in_data': False,
                              'gap': 'ch3 棋盘章，0 条实例'},
    # ★ 下面两条是第68轮**对账判据抓出来的**：第48轮把它们标成 `in_data=True`
    #   （依据是"第42轮普查收录了该类"），但产物里 0 条 —— 因为"普查收录"≠"能进产物"。
    'obj_darkfountain_event': {'kind': 'fountain', 'in_data': False,
                               'gap': '第68轮全量普查里 0 条实例（对象存在，但没有房间在用）'},
    'obj_ch2_scene25_fountain': {'kind': 'fountain', 'in_data': False,
                                 'gap': '对象表里该对象的 `spr=` 为空（运行时才给图）'
                                        '⇒ 不可绘制、进不了 objects'},
}

#: 前缀兜底：按名字前缀归类（用于登记表没写、但语义显然的名字）。
_PREFIX_RULES = (
    ('obj_', ('door',), 'door'),
    ('obj_', ('savepoint',), 'savepoint'),
    ('obj_', ('fountain',), 'fountain'),
    ('obj_', ('readable',), 'readable'),
    ('obj_', ('sign',), 'sign'),
    ('obj_', ('chest', 'treasure'), 'chest'),
    ('obj_', ('pickup',), 'pickup'),
    ('obj_', ('cutscene', 'event'), 'cutscene'),
)

#: 不参与交互的分类 —— 建可交互物时要跳过（标记点是落点、不是可交互物）。
NON_INTERACTIVE_KINDS = frozenset({'marker'})


def classify(src):
    """原作对象名 → `{'kind':..., 'in_data':..., 'gap':...}`；认不出来返回 `None`。

    **不猜**：认不出来就是 `None`（同 companion 的"找不到就是不找到"）。
    """
    if not src or not isinstance(src, str):
        return None
    rec = PROP_CLASSES.get(src)
    if rec is not None:
        return dict(rec)
    low = src.lower()
    if 'marker' in low:
        return {'kind': 'marker', 'in_data': True}
    # ★ 门：**有数据**，但归**路由层**处理（`scene_routing` / `follow_route`）。
    #   不标成"数据缺口"——那会把"已实现"说成"没做"。
    if 'door' in low:
        return {'kind': 'door', 'in_data': True, 'handled_by': 'scene_routing'}
    for _, keys, kind in _PREFIX_RULES:
        if any(k in low for k in keys):
            # ★ `in_data=None` **不等于**"缺数据"：它的意思是"这类名我们**没逐个登记**，
            #   只是按名字前缀归了类"。产物里可能真有条数（如 `obj_cybercity_bg_sign`）。
            #   标 `False` 会让 `data_gaps()` 把**已经落地的物件**误报成缺口
            #   —— 那与"如实"这条原则一样有害（是反向的不如实）。
            return {'kind': kind, 'in_data': None, 'unregistered': True}
    return None


def is_interactive(src):
    """这个原件名是不是"该能互动"的东西（含数据缺口类）。"""
    rec = classify(src)
    return bool(rec) and rec['kind'] not in NON_INTERACTIVE_KINDS and rec['kind'] != 'cutscene'


def data_gaps():
    """列出"机制就位但数据缺席"的分类（报告用）。

    ★ 只统计 `PROP_CLASSES` 里**显式 `in_data=False`** 的登记项 ——
      那才是"我们点名要的类，普查里一条都没有"。
      按名字前缀兜底归类（`in_data=None`）**不算缺口**：那些类没逐个登记，
      但产物里很可能真有条数（如招牌类），把它们列成缺口＝另一种不如实。
    """
    seen = {}
    for name, rec in sorted(PROP_CLASSES.items()):
        if rec.get('in_data') is False:
            seen.setdefault(rec['kind'], []).append(name)
    return seen


# ===========================================================================
#  可交互物实现
# ===========================================================================

#: ★ 「产品口径」台词 —— 原作 `obj_savepoint_Other_10` 的**结构**是"按 room 给不同台词"，
#: 但**文本在外部语言包里**（`lang_zh_names.json`），本项目拿不到（见取证 §2.3）。
#: ⇒ 这里写一句产品自定文案，并保留"按房间覆盖"的钩子（`overrides`）。
SAVEPOINT_TEXT = '* 存档点。光芒笼罩下来——伤口全都愈合了。'

#: ★ 照抄 `obj_savepoint_Other_10` 的 `room == ` 分支结构，按 (章节, 原作房间 id) 覆盖台词。
#: 目前**只有结构、没有原文** ⇒ 留空字典；填的时候键 = (chapter, original_room_id)。
SAVEPOINT_TEXTS = {}

FOUNTAIN_TEXT = '* 暗之泉。深不见底的黑色在缓慢地流动。'

JUNKED_TEXT = '它已经变成垃圾团里的东西了。'


class PropInteractable(Interactable):
    """所有场景可交互物的基类：带 `src`（原作对象名）与 `kind`（分类）。"""

    def __init__(self, key, src, kind, bus=None):
        Interactable.__init__(self, key, bus=bus)
        self.src = src
        self.kind = kind

    def describe(self):
        return '%s(%s)' % (KIND_LABEL.get(self.kind, self.kind), self.src)


class SavePointProp(PropInteractable):
    """存档点 —— ★ 照抄 `obj_savepoint_Other_10` 的两件事：

    1. **按房间给不同台词**（原作 `if (room == room_xxx)`；我们用 `SAVEPOINT_TEXTS` 覆盖，
       没覆盖就用 `SAVEPOINT_TEXT`）；
    2. **全队回满 HP**（原作 `for (i=0;i<4;i++) if (hp[i] < maxhp[i]) hp[i] = maxhp[i];`）。

    `present(text, actor)` / `heal_all()` 由接线层注入（本层不碰 UI、不碰队伍数值）。
    """

    def __init__(self, key, src='obj_savepoint', chapter=None, original_room_id=None,
                 present=None, heal_all=None, bus=None):
        PropInteractable.__init__(self, key, src, 'savepoint', bus=bus)
        self.chapter = chapter
        self.original_room_id = original_room_id
        self.present = present
        self.heal_all = heal_all
        self.talked = 0          #: 对应原作 `talked += 1`

    def line(self):
        return SAVEPOINT_TEXTS.get((self.chapter, self.original_room_id), SAVEPOINT_TEXT)

    def on_interact(self, actor=None):
        self.talked += 1
        if self.heal_all is not None:
            try:
                self.heal_all()
            except Exception:
                _log.exception('存档点回血失败（key=%s）', self.key)
        if self.present is None:
            _log.warning('存档点 %s 没接 present ⇒ 如实返回"没发生"', self.key)
            return False
        self.dialog = self.present(self.line(), actor)
        return bool(self.dialog)


class FountainProp(PropInteractable):
    """暗之泉 —— 交互即"进入泉"（产品第一站 = `ch1.room_town_north`，见 §43.6）。

    `on_enter(scene_id)` 由接线层注入；返回 False 表示"没去成"（**不静默成功**）。
    """

    def __init__(self, key, src='obj_darkfountain', target_scene=None,
                 on_enter=None, present=None, bus=None):
        PropInteractable.__init__(self, key, src, 'fountain', bus=bus)
        self.target_scene = target_scene
        self.on_enter = on_enter
        self.present = present

    def on_interact(self, actor=None):
        if self.on_enter is not None:
            ok = bool(self.on_enter(self.target_scene))
            if not ok:
                _log.warning('暗之泉 %s 未能进入 %s ⇒ 如实返回"没发生"',
                             self.key, self.target_scene)
                return False
            return True
        # 没接"进入"回调时退化成一句描述 —— 至少是可交互的，而不是死的。
        if self.present is None:
            return False
        self.dialog = self.present(FOUNTAIN_TEXT, actor)
        return bool(self.dialog)


class PickupProp(PropInteractable):
    """拾取物 —— 捡起地上的道具放进背包。

    ⚠️ **落点是产品口径**：原作"哪间房地上有什么"要靠实例普查里的 chest/pickup 类，
    而那个类**不在**我们的普查里（见模块 docstring）。所以落点从
    `assets/items/pickups.json` 读，文件里逐条写明 `source`（"产品自定" 或 "原作房间 id"）。
    """

    def __init__(self, key, item_id, world, inventory=None, present=None,
                 src='obj_board_pickup', bus=None):
        PropInteractable.__init__(self, key, src, 'pickup', bus=bus)
        self.item_id = int(item_id)
        self.world = world
        self.inventory = inventory
        self.present = present
        self.taken = False

    def on_interact(self, actor=None):
        if self.taken:
            return False
        if self.inventory is None:
            _log.warning('拾取物 %s 没接 inventory ⇒ 如实返回"没发生"', self.key)
            return False
        ok, idx = self.inventory.pick_up(self.item_id, world=self.world)
        if not ok:
            if self.present is not None:
                self.dialog = self.present('* 背包已经满了。', actor)
                return bool(self.dialog)
            return False
        self.taken = True
        item = self.inventory.catalog.get(self.inventory.chapter, self.world, self.item_id)
        if self.present is not None:
            self.dialog = self.present('* 你捡到了「%s」。' % item.display_name, actor)
            return bool(self.dialog)
        return True


class ReadableProp(PropInteractable):
    """可读物 / 招牌 —— 第68轮补采后**已有实例**（`obj_readable_room1` 856 条 /
    `obj_npc_sign` 81 条等）。

    文本走 `READABLE_TEXT`（产品口径：原文本在 `lang_zh_names.json`，拿不到）。
    """

    def __init__(self, key, text, src='obj_readable', kind='readable', present=None, bus=None):
        # ★ `kind` 默认 `'readable'` ⇒ **不传该参的既有调用行为完全不变**（纯增量）。
        #   第68轮起 `build_props` 把真实 kind（`readable` / `sign`）传进来 ——
        #   否则招牌类物件的 `describe()` 会自称"可读物"（张冠李戴）。
        PropInteractable.__init__(self, key, src, kind, bus=bus)
        self.text = text
        self.present = present

    def on_interact(self, actor=None):
        if self.present is None:
            return False
        self.dialog = self.present(self.text, actor)
        return bool(self.dialog)


#: 「调查类」kind —— 宝箱 / 通用可交互物 / 可调查家具。这三类在原件里的差别
#: **只在实例自带的事件脚本**里（开箱逻辑、家具的台词都存在实例变量），
#: 而实例级脚本**不进我们的数据**（第44轮 objects 只蒸馏了 pos/sprite/src）
#: ⇒ 统一为"调查后给一句描述"，台词按 kind 分流，**不假装**给出了原作文本。
INSPECT_KINDS = frozenset({'chest', 'interactable', 'furniture'})

#: ★ 产品口径台词（原文在外部语言包，拿不到；同 §49.2 的取证）。
INSPECT_TEXT = {
    'chest': '* 一个箱子。盖子扣得很紧——里面像是空的。',
    'interactable': '* 这里似乎有什么东西，但看不出门道。',
    'furniture': '* 一件家具。看起来没什么特别的。',
}


class InspectProp(PropInteractable):
    """「调查类」物件（宝箱 / 可交互物 / 家具）—— 说清"这里有什么"，而不是干瘪的"什么都没有"。

    `present(text, actor)` 由接线层注入；**没注入 ⇒ 如实返回 False**（同其它 Prop 的纪律：
    宁可"看上去不能点"，也不要"点了没反应"）。
    """

    def __init__(self, key, kind, src=None, text=None, present=None, bus=None):
        PropInteractable.__init__(self, key, src or ('obj_%s' % kind), kind, bus=bus)
        if text is not None:
            self.text = text
        else:
            self.text = INSPECT_TEXT.get(kind, INSPECT_TEXT['interactable'])
        self.present = present

    def on_interact(self, actor=None):
        if self.present is None:
            _log.warning('调查物 %s 没接 present ⇒ 如实返回"没发生"', self.key)
            return False
        self.dialog = self.present(self.text, actor)
        return bool(self.dialog)


# ===========================================================================
#  工厂：场景 → 可交互物列表
# ===========================================================================

def build_props(scene, chapter, world, present=None, heal_all=None,
                on_enter=None, inventory=None, bus=None, pickups=None):
    """把一个场景的 `objects` 变成可交互物列表。

    参数
    ----
    scene : dict | object
        场景数据（`{'objects': [...]}` 或带 `.objects` 的对象）。
    chapter, world : str
    present(text, actor) -> handle
        UI 注入：弹一句话，返回"对话句柄"。**没注入 ⇒ 可交互物会如实拒绝交互**
        （这是刻意的：宁可"看上去不能点"，也不要"点了没反应"）。
    heal_all : callable
        存档点用：全队回满 HP。
    on_enter : callable(scene_id) -> bool
        暗之泉用：切到目标场景。
    inventory : item_system.Inventory
        拾取物用。
    pickups : dict
        `{scene_id: [item_id, ...]}` —— 产品口径的落点表。

    ★ `key` 的构造规则：`<scene_id>#<objects下标>`。
      为什么不用 `src`：同一个房间里可能有 **多个** 同名对象（例如两个 `obj_savepoint`），
      用 `src` 会撞 key（`InteractBus` 是进程级单例，撞 key 会导致两个物件变成同一个）。
    """
    objs = scene.get('objects') if isinstance(scene, dict) else getattr(scene, 'objects', None)
    sid = scene.get('scene_id') if isinstance(scene, dict) else getattr(scene, 'scene_id', None)
    room_id = scene.get('original_room_id') if isinstance(scene, dict) \
        else getattr(scene, 'original_room_id', None)
    objs = objs or []

    out = []

    for i, o in enumerate(objs):
        if not isinstance(o, dict):
            continue
        src = o.get('src')
        rec = classify(src)
        if rec is None or rec['kind'] in NON_INTERACTIVE_KINDS:
            continue
        key = '%s#%d' % (sid or 'scene', i)
        kind = rec['kind']
        if kind == 'savepoint':
            out.append(SavePointProp(key, src=src, chapter=chapter,
                                     original_room_id=room_id,
                                     present=present, heal_all=heal_all, bus=bus))
        elif kind == 'fountain':
            out.append(FountainProp(key, src=src, target_scene=FOUNTAIN_TARGET,
                                    on_enter=on_enter, present=present, bus=bus))
        elif kind == 'pickup':
            for item_id in (pickups or {}).get(sid, ()):
                out.append(PickupProp('%s@%s' % (key, item_id), item_id, world,
                                      inventory=inventory, present=present, bus=bus))
        elif kind in ('readable', 'sign'):
            out.append(ReadableProp(key, READABLE_TEXT.get(src, READABLE_TEXT['_default']),
                                    src=src, kind=kind, present=present, bus=bus))
        elif kind in INSPECT_KINDS:
            # ★ 第68轮：宝箱 / 通用可交互物 / 可调查家具 —— 普查与产物里**已有实例**，
            #   不能再落进 else 被静默丢弃（否则就是"补采了数据、却没实现交互"）。
            out.append(InspectProp(key, kind, src=src, present=present, bus=bus))
        else:
            # 仍不在这里实现的：
            #   `door`    —— 交路由层（见 classify 的 handled_by）
            #   `cutscene`—— 演出触发器，不是玩家点的物件
            #   `pickup`  —— 有自己的分支；**没有落点表就如实不建物**（见 PickupProp docstring）
            continue
    return out


#: ★ 暗之泉通向哪 —— 照抄 §43.6 的产品口径（桌面 = 独立前置章，放暗之泉，
#: 切到 `ch1.room_town_north`）。scene_id 由场景索引的真实键填。
FOUNTAIN_TARGET = 'ch1.castle_town.castle_town'

#: 可读物台词（**产品口径**：原文在语言包里，拿不到）。
READABLE_TEXT = {'_default': '* 上面写着些什么，但字迹已经模糊了。'}


def load_pickups(path):
    """读产品口径的拾取落点表。文件不在 ⇒ 返回空表（**不抛**，也不假装有）。"""
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            d = json.load(fh)
    except Exception:
        _log.exception('拾取落点表读取失败 %s', path)
        return {}
    out = {}
    for sid, rec in (d.get('scenes') or {}).items():
        out[sid] = [e['item_id'] for e in (rec.get('items') or []) if 'item_id' in e]
    return out


def survey(scenes_dir, chapter, world):
    """统计一个章节里**实际出现**的可交互原件（报告用；只读，不写盘）。

    ⚠️ `collections` 必须留在**模块顶部** —— 本文件顶部 import 里原来混进过一次
    函数内 `import collections`，与 companion / scene_pathfind 的"零函数内 import"
    纪律（初始化环）不一致。已提到顶部；回归套件 A 段会锁住这一点。
    """
    hit = collections.Counter()
    idx_path = os.path.join(scenes_dir, '_index.json')
    if not os.path.isfile(idx_path):
        return hit
    with open(idx_path, 'r', encoding='utf-8') as fh:
        idx = json.load(fh)
    crec = (idx.get('chapters') or {}).get(chapter) or {}
    for ak, av in (crec.get('areas') or {}).items():
        zpath = os.path.join(scenes_dir, '_zone.%s.%s.json' % (chapter, ak))
        zz = None
        if os.path.isfile(zpath):
            with open(zpath, 'r', encoding='utf-8') as fh:
                zz = (json.load(fh) or {}).get('scenes') or {}
        for sid, sr in (av.get('scenes') or {}).items():
            objs = None
            f = sr.get('file')
            if f and os.path.isfile(os.path.join(scenes_dir, f)):
                with open(os.path.join(scenes_dir, f), 'r', encoding='utf-8') as fh:
                    objs = (json.load(fh) or {}).get('objects')
            elif zz and sid in zz:
                objs = (zz[sid] or {}).get('objects')
            for o in (objs or []):
                if is_interactive(o.get('src')):
                    hit[o.get('src')] += 1
    return hit

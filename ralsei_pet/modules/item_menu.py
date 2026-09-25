# -*- coding: utf-8 -*-
"""场内菜单（S 键菜单）—— 照抄原作 **两个** 菜单对象的状态机，但**摘掉设置页**。

回答用户这条需求（第 48 轮）
----------------------------
    「……对了，游戏里的背包这类的通过 S 键实现的菜单也要应用哦，但，设置不应用」

⇒ 本模块 = 「背包这一类通过 S 键打开的菜单」的状态机本体。

★ 一键摘掉设置页的**原作依据**（不是阉割，是本来并列）
-------------------------------------------------------
原作暗世界菜单 `obj_darkcontroller` 的根菜单是 5 个按钮（`Draw_0` L19–L44）：

    msprite[0] = spr_darkitembt     → menuno 1  道具 ITEM
    msprite[1] = spr_darkequipbt    → menuno 2  装备 EQUIP
    msprite[2] = spr_darktalkbt     → ★ `if (i != 2)` 才画 ⇒ 关闭位
    msprite[3] = spr_darktechbt     → menuno 4  技能 TECH
    msprite[4] = spr_darkconfigbt   → menuno 5  设置 CONFIG ← **用户要求不应用**

而 `menuno == 5`（CONFIG）在 `Step_0` L209+ 与 `Draw_0` L50–L133 里是**独立兄弟分支**
（音量 / 音乐 / 闪光 / 震屏 / 全屏 / 快跑 / 边框）——
摘掉它**不碰**道具 / 装备 / 技能三页。⇒ 用户口径在原作结构上是干净的。
光世界菜单 `obj_overworldc` 的根菜单只有 3 项（道具 / 状态 / 手机），**本来就没有设置**。

两个菜单对象（别混用）
----------------------
| 世界 | 对象 | 状态机 | 根菜单 |
|---|---|---|---|
| 光 | `obj_overworldc` | `global.menuno` | 道具 / 状态 / 手机（3 项） |
| 暗 | `obj_darkcontroller` | `global.menuno` + `global.submenu` | 道具 / 装备 /(空)/ 技能 / 设置（5 位） |

⚠️ 另有一个**同名但完全不同**的 `DEVICE_MENU` —— 那是**标题画面 / 存档选择**菜单，
用的是 `MENU_NO` / `MENUCOORD`（与本模块的 `MENU_NO_LIGHT/DARK` 只差一个下划线）。
详见取证 §6.1，**不要**把两者的编号混用。

锁与开关（照抄）
----------------
    obj_mainchara_Step_0 L20–L38   （开菜单）
        global.menuno = 0
        global.interact = 5        ← 菜单锁（对话锁是 1，场景切换是 6）

    obj_overworldc_Step_0 L176–L191（关菜单）
        global.menuno = -1
        global.interact = 0

⚠️ 本模块**不管** "物理上按了哪个键"。原作是 `button3_p()`，其映射在 `keyconfig_*.ini` 里，
`data.win` 不含默认值（取证 §8.4）⇒ 本产品按用户口径**直接绑 S**（另接受 C 兼容），
那段在 `global_hotkey` + 接线层，不在本模块。

零依赖纪律
----------
本模块**只 import 标准库 + `item_system`**（`item_system` 本身零依赖，见其 docstring）。
**禁 import Qt、禁 import 其它项目内模块** —— 与 companion / scene_pathfind 同源理由
（`main.py` 在 import 期就建控制器；反向 import 会接上初始化环 ⇒ import 期崩、零输出）。

本层**不弹话、不画图**
----------------------
`key()` / `frame()` 只返回一个 `MenuFrame`（纯数据）。要显示的文字在 `frame.message`，
由 UI 壳（`item_menu_ui`）转给对话气泡。**为什么不在这里直接 `present()`**：
判定与显示分开，离线回归才能只断言"该给出的文案给了没"，而不必起 Qt。
"""
import collections
import logging
import random

import item_system

_log = logging.getLogger(__name__)

# ===========================================================================
#  页面常量（字符串，便于直接进日志/报告）
# ===========================================================================

PAGE_CLOSED = 'closed'      #: 菜单关着（`global.menuno = -1`）
PAGE_ROOT = 'root'          #: 根菜单（`menuno == 0`）
PAGE_ITEMS = 'items'        #: 道具列表（`menuno == 1`）
PAGE_ACTION = 'action'      #: 道具动作子菜单：使用 / 查看 / 丢弃（`menuno == 5`）
PAGE_JUNK = 'junk'          #: ★「产品口径」垃圾团查看页（原作无此页，见下）
PAGE_STAT = 'stat'          #: 状态 STAT（光世界 `menuno == 2`）
PAGE_EQUIP = 'equip'        #: 装备 EQUIP（暗世界 `menuno == 2`）
PAGE_PHONE = 'phone'        #: 手机 PHONE（光世界 `menuno == 3`）
PAGE_TECH = 'tech'          #: 技能 TECH（暗世界 `menuno == 4`）
PAGE_CONFIG = 'config'      #: 设置 CONFIG（暗世界 `menuno == 5`）← **不应用**

#: ★ 页面 → 原作 `global.menuno` 编号。**两个世界必须分开**：
#: 光世界的 `menuno == 5` 是"道具动作子菜单"，暗世界的 `menuno == 5` 是"设置"。
#: 合成一个 dict 就会把这两件事混成一件（这正是 `DEVICE_MENU` 那个坑的同型错误）。
MENU_NO_LIGHT = {
    PAGE_CLOSED: -1, PAGE_ROOT: 0, PAGE_ITEMS: 1, PAGE_STAT: 2, PAGE_PHONE: 3,
    PAGE_ACTION: 5, PAGE_JUNK: 5,
}
MENU_NO_DARK = {
    PAGE_CLOSED: -1, PAGE_ROOT: 0, PAGE_ITEMS: 1, PAGE_EQUIP: 2, PAGE_TECH: 4,
    PAGE_CONFIG: 5, PAGE_ACTION: 5, PAGE_JUNK: 5,
}

#: ★ 照抄 `obj_mainchara_Step_0` / `obj_overworldc_Step_0` 的 `global.interact` 取值。
LOCK_NONE = 0        #: 自由
LOCK_DIALOGUE = 1    #: 对话中
LOCK_MENU = 5        #: 菜单开着
LOCK_SCENE = 6       #: 场景切换中（换房 ≈0.92s，见 §44）

#: 道具动作子菜单的三项 —— 照抄 `obj_overworldc_Step_0` L11–L88 与
#: `obj_darkcontroller_Draw_0` L1037–L1125（`global.submenu == 1` 时心形在 0/1/2 之间移动）。
ACT_USE, ACT_LOOK, ACT_DROP = 0, 1, 2
ACTION_LABELS = ('使用', '查看', '丢弃')

#: 根菜单条目（照抄两个对象的按钮顺序）。
#: `pid` 为 `None` = 原作**不绘制**的关闭位（`obj_darkcontroller` 的 `i == 2`）。
RootEntry = collections.namedtuple('RootEntry', ('pid', 'label'))

ROOT_LIGHT = (
    RootEntry(PAGE_ITEMS, '道具'),
    RootEntry(PAGE_STAT, '状态'),
    RootEntry(PAGE_PHONE, '手机'),
)
ROOT_DARK = (
    RootEntry(PAGE_ITEMS, '道具'),
    RootEntry(PAGE_EQUIP, '装备'),
    RootEntry(None, ''),            # ★ 原作 `if (i != 2)` 不画 ⇒ 关闭位
    RootEntry(PAGE_TECH, '技能'),
    RootEntry(PAGE_CONFIG, '设置'),  # ★ 用户口径：不应用 ⇒ 默认不渲染
)

#: ★ 用户口径开关 —— «设置不应用»。
#: 默认 `False` ⇒ 设置条目**不进渲染、不进导航**（既不实现也不露脸）。
#: 想在某天真的应用设置页时，把这里改成 True 并给 `PAGE_CONFIG` 补一个页面工厂即可。
INCLUDE_SETTINGS = False

#: 「产品口径」垃圾团页的入口名 —— 原作没有这一页。
#: 为什么还是要有：用户口径是「回光世界时暗世界道具**变成垃圾团里包含的东西**」；
#: 如果垃圾团不可见，这条需求在界面上就**无法被观察到**（只能靠读日志）。
JUNK_ENTRY_LABEL = '垃圾团'

#: 交互提示（**产品口径**文案；原作靠按键图标，我们没有图标资源）。
HINT_ROOT = '↑↓ 选择    Enter 进入    Esc 关闭'
HINT_LIST = '↑↓ 选择    Enter 确认    Esc 返回'
HINT_ACTION = '←→ 选择动作    Enter 执行    Esc 返回'
HINT_READONLY = 'Esc 返回'

#: ★ 丢弃成功的"手滑文学" —— 照抄 `obj_overworldc_Step_0` 的
#: `i = round(random(30)); if (i <= 3) ...`（4 个分支 + 1 个兜底）。
#: ⚠️ 文本是**产品口径**：原作文本在外部语言包 `lang/lang_zh_names.json` 里，本项目拿不到
#: （取证 §2.3），所以只复刻**结构与数量**，字句自写。
DROP_FLAVOR = (
    '* 手一滑，东西掉了出去。',
    '* 你把它丢在了地上。',
    '* 它骨碌碌滚远了。',
    '* 你随手把它扔了。',
)
DROP_FLAVOR_DEFAULT = '* 你把它丢掉了。'

#: ★ 丢不掉的文案 —— 照抄 `obj_overworldc_Step_0` 的 `dontthrow` 名单，
#: 其中 id 11 走 `dontthrowtype = 2` 的**专属台词**（两档不同）。
#: 名单本身（id 5 / id 11）在 `item_system.DONT_THROW`，这里只放文案。
DONT_THROW_TEXTS = {
    (item_system.WORLD_LIGHT, 5): '* 这个东西不能丢下。',
    (item_system.WORLD_LIGHT, 11): '* ……你又把它收了回去。',
}
DONT_THROW_DEFAULT = '* 你丢不掉它。'

#: 空格子被选中（原作 `itemnameb = " "; itemdescb = "---"`，不弹话）。
EMPTY_ROW_LABEL = '---'


#: `key()` / `frame()` 的返回值 —— **纯数据**，UI 壳只照它画。
#:
#: page    当前页（`PAGE_*`）
#: menuno  对应的原作 `global.menuno`（两世界不同，见 `MENU_NO_LIGHT/DARK`）
#: title   标题行（已是给人看的中文）
#: rows    原始行文本（**没有**光标前缀）
#: lines   `rows` 加上光标前缀后的成品行 —— 照抄 `scr_84_draw_menu` 的 `"> "` / `"  "`
#: cursor  当前选中下标（-1 = 本页无行 / 无光标）
#: message 需要弹给对话气泡的一句话（`None` = 不弹）
#: hint    底部按键提示
#: closed  菜单是否已关闭
MenuFrame = collections.namedtuple(
    'MenuFrame', ('page', 'menuno', 'title', 'rows', 'lines', 'cursor',
                  'message', 'hint', 'closed'))

#: ★ 开关去抖窗口（秒）。
#: 为什么需要：全局热键的回调路径上，同一次按键**实测出现过投递两次**
#: （第48轮真机验证：`PostMessage(WM_HOTKEY)` 一次 → 回调两次，见报告 §热键）。
#: 菜单的开关是"取反"，重复一次正好等于**没开**（开了又立刻关）——
#: 这种故障在界面上表现为"按了没反应"，最难往热键上想。
#: 0.25s 对人是无感的（谁也不会想在半秒内开关两次），却能挡住重复投递。
TOGGLE_DEBOUNCE_SEC = 0.25

#: 光标前缀 —— 照抄 `scr_84_draw_menu`：选中 `"> "`，未选中 `"  "`（**两个空格**，
#: 靠空格在等宽像素字体下对齐；这里保持等宽是为了逐字节对齐原作的观感）。
CURSOR_ON = '> '
CURSOR_OFF = '  '


# ===========================================================================
#  取键名归一化
# ===========================================================================

#: 键名别名 → 规范名。**刻意不收录字母 `s`** ——
#: `S` 是全局热键（开/关菜单），菜单内若再让 `s` = "下" 就会自打架。
#: 菜单内一律用方向键 + Enter + Esc/X（`x` 是原作 `button2_p()` 的常见默认键）。
_KEY_ALIASES = {
    'up': 'up', 'arrowup': 'up',
    'down': 'down', 'arrowdown': 'down',
    'left': 'left', 'arrowleft': 'left',
    'right': 'right', 'arrowright': 'right',
    'w': 'up', 'a': 'left', 'd': 'right',
    'enter': 'confirm', 'return': 'confirm', 'confirm': 'confirm', 'z': 'confirm',
    ' ': 'confirm', 'space': 'confirm',
    'esc': 'cancel', 'escape': 'cancel', 'cancel': 'cancel', 'x': 'cancel',
    'backspace': 'cancel',
    'menu': 'menu', 'm': 'menu',
}


def normalize_key(name):
    """键名 → 规范名；不认识返回 `None`（**不猜**）。"""
    if not isinstance(name, str):
        return None
    return _KEY_ALIASES.get(name.strip().lower())


# ===========================================================================
#  菜单本体
# ===========================================================================

class ItemMenu(object):
    """S 键菜单的状态机。**不弹话、不画图、不管物理按键**。

    参数
    ----
    inventory : item_system.Inventory
        唯一的道具判定入口。菜单**不做**任何"能不能用"的判断 —— 那全在 `item_system`，
        菜单只问它（保证"菜单里亮着、按下去被拒"这种不一致不可能出现）。
        ★ 当前章节/世界**只认 `inventory` 一个真源**，本类刻意**不**提供覆盖参数：
        一旦菜单和 inventory 的域能各说各话，`blocked_reason` 就会按错的域判定，
        而这种 bug 只在"某个具体场景里"才现形，最难查。
    stat_provider / spell_provider : callable | None
        返回 `[(标签, 值), ...]`，用于还原原作的 STAT / TECH 两页。
        **没注入 ⇒ 该页标记为「登记但不可用」**（如实说明缺数据），不假装有内容。
    apply_heal : callable(amount) -> int | None
        实际给队伍回血（本产品当前**没有**队伍 HP 模型 ⇒ 不注入时只显示文案）。
    is_busy : callable() -> bool | None
        外部锁询问（对话中 / 场景切换中）。返回 True ⇒ 开不出菜单。
    rng : random.Random | None
        只为丢弃的"手滑文学"用；测试里注入定种子的实例即可复现。
    include_settings : bool
        ★ «设置不应用» 的开关，默认取模块常量 `INCLUDE_SETTINGS`（= False）。
    """

    def __init__(self, inventory, stat_provider=None,
                 spell_provider=None, apply_heal=None, is_busy=None, rng=None,
                 include_settings=None):
        self.inventory = inventory
        self.stat_provider = stat_provider
        self.spell_provider = spell_provider
        self.apply_heal = apply_heal
        self.is_busy = is_busy
        self.rng = rng or random.Random()
        self.include_settings = INCLUDE_SETTINGS if include_settings is None \
            else bool(include_settings)

        self.page = PAGE_CLOSED
        self.cursor = 0
        self.action = ACT_USE
        #: ★ 选中道具在**背包里的槽位下标**（`Bag.slots` 的下标）。
        #: 为什么单独存：动作页的 `cursor` 是"使用/查看/丢弃"三选一（0..2），
        #: 与"第几件道具"是**两件事**。曾经共用过一个 `cursor`，
        #: 结果"丢弃第 1 件"会落到第 2 件上 —— 这种错位在界面上很难看出来。
        self.slot_index = 0
        #: 从动作页返回列表时，光标回到原来那一行。
        self.row_index = 0
        self.last_message = None
        #: 诊断计数（**不参与任何判据**）。
        self.opens = 0
        self.uses = 0
        self.drops = 0
        self.refusals = 0

    # ---------------------------------------------------------------- 域
    @property
    def is_dark(self):
        """当前是不是暗世界 —— 决定根菜单用哪一套（`ROOT_DARK` / `ROOT_LIGHT`）。"""
        return self.inventory.world == item_system.WORLD_DARK

    @property
    def is_open(self):
        return self.page != PAGE_CLOSED

    def _bag(self):
        return self.inventory.bag()

    # ---------------------------------------------------------------- 开关
    def can_open(self):
        """能不能开 —— 照抄"菜单锁"语义：非自由态（对话/切场景）不开。

        返回 `(可否, 原因)`；原因只用于日志/报告。
        """
        if self.is_open:
            return False, '已经开着'
        if self.is_busy is not None:
            try:
                if self.is_busy():
                    return False, '外部锁未释放（对话中或场景切换中）'
            except Exception:
                _log.exception('is_busy 回调抛异常（按"忙"处理，不硬开）')
                return False, '外部锁询问失败'
        return True, None

    def open(self):
        """开菜单 —— 照抄 `obj_mainchara_Step_0`：`menuno = 0`（根）且上菜单锁。"""
        ok, why = self.can_open()
        if not ok:
            _log.info('菜单没开：%s', why)
            return self.frame()
        self.page = PAGE_ROOT
        self.cursor = 0
        self.action = ACT_USE
        self.slot_index = 0
        self.row_index = 0
        self.last_message = None
        self.opens += 1
        return self.frame()

    def close(self):
        """关菜单 —— 照抄 `obj_overworldc_Step_0`：`menuno = -1`。"""
        self.page = PAGE_CLOSED
        self.cursor = 0
        return self.frame()

    def toggle(self):
        return self.close() if self.is_open else self.open()

    # ---------------------------------------------------------------- 根条目
    def _page_state(self, pid):
        """`pid` → `'ok'` / `'nodata'` / `'noconfig'` / `'hidden'` + 一句原因。

        ★ 这里就是"如实"的地方：本产品**没有**队伍 HP / 武器护甲 / 手机数据，
        所以那些页标 `nodata` 并被排除在渲染之外 —— 而不是画一个空页假装有。
        """
        if pid is None:
            return 'hidden', '原作 `if (i != 2)` 不绘制的关闭位'
        if pid == PAGE_ITEMS:
            return 'ok', ''
        if pid == PAGE_JUNK:
            return 'ok', ''
        if pid == PAGE_STAT:
            if self.stat_provider is not None:
                return 'ok', ''
            return 'nodata', '本产品尚无队伍数值（LV/HP/AT/DF/金币），未接线'
        if pid == PAGE_TECH:
            if self.spell_provider is not None:
                return 'ok', ''
            return 'nodata', '本产品尚无技能表，未接线'
        if pid == PAGE_EQUIP:
            return 'nodata', '本产品尚无武器/护甲数据'
        if pid == PAGE_PHONE:
            return 'nodata', '本产品尚无手机数据'
        if pid == PAGE_CONFIG:
            if not self.include_settings:
                return 'hidden', '★ 用户口径：设置不应用（`INCLUDE_SETTINGS = False`）'
            return 'noconfig', '设置页明确不实现（用户口径）'
        return 'hidden', '未知页 %r' % (pid,)

    def entries(self, visible_only=False):
        """根菜单条目 —— `[(pid, label, state, reason), ...]`。

        `visible_only=True` 只回可用的（渲染与导航都用这一份，两边不可能不一致）。
        """
        src = ROOT_DARK if self.is_dark else ROOT_LIGHT
        out = []
        for e in src:
            state, reason = self._page_state(e.pid)
            if state in ('hidden', 'noconfig'):
                continue
            if visible_only and state != 'ok':
                continue
            out.append((e.pid, e.label, state, reason))
        # ★ 垃圾团入口**只非空时**出现（否则每个世界都多一行死条目）。
        if len(self.inventory.junk) > 0:
            out.append((PAGE_JUNK, '%s（%d 件）' % (JUNK_ENTRY_LABEL, len(self.inventory.junk)),
                        'ok', ''))
        return out

    def page_notes(self):
        """被排除的页 + 原因（**报告用**；只读，不影响状态）。

        为什么要有：用户口径只说了「设置不应用」，但本产品还**顺带**没有 STAT/EQUIP/
        TECH/PHONE 的数据。把这两类分开列出来，读者才不会以为是"照着用户说的砍了"。
        """
        src = ROOT_DARK if self.is_dark else ROOT_LIGHT
        out = []
        for e in src:
            state, reason = self._page_state(e.pid)
            if state != 'ok':
                out.append({'pid': e.pid, 'label': e.label or '(关闭位)',
                            'state': state, 'reason': reason})
        return out

    # ---------------------------------------------------------------- 行
    def _rows_and_labels(self):
        """当前页 → `(rows, labels)`。

        `rows`  显示文本（可能带"（垃圾）"后缀，**纯显示**）；
        `labels` 与 `rows` 等长的语义标签（`'item'` / `'junknote'` / `'kv'` / `'text'`）。
        """
        page = self.page
        w = self.inventory.world

        if page == PAGE_ROOT:
            es = self.entries(visible_only=True)
            return [e[1] for e in es], ['entry'] * len(es)

        if page == PAGE_ITEMS:
            rows, labels = [], []
            for _i, name, is_junk, usable in self.inventory.visible_rows(w):
                # ★「（垃圾）」是**显示层**加的后缀（产品口径）：
                #   用户口径是"暗世界道具变成垃圾团里包含的东西"，若在列表里仍显示原名，
                #   会让人以为它还是那件道具。判定仍由 item_system 负责，这里只写字。
                suffix = '（垃圾）' if is_junk else ('' if usable else '（用不了）')
                rows.append('%s%s' % (name, suffix))
                labels.append('item')
            if not rows:
                rows, labels = ['（空）'], ['note']
            return rows, labels

        if page == PAGE_ACTION:
            return list(ACTION_LABELS), ['action'] * len(ACTION_LABELS)

        if page == PAGE_JUNK:
            names = self.inventory.junk.names()
            if not names:
                return ['（空）'], ['note']
            return list(names), ['junknote'] * len(names)

        if page in (PAGE_STAT, PAGE_TECH):
            prov = self.stat_provider if page == PAGE_STAT else self.spell_provider
            try:
                pairs = list(prov() or [])
            except Exception:
                _log.exception('%s provider 抛异常（按"没数据"处理）', page)
                pairs = []
            if not pairs:
                return ['（暂无数据）'], ['note']
            return ['%s：%s' % (k, v) for k, v in pairs], ['kv'] * len(pairs)

        if page in (PAGE_EQUIP, PAGE_PHONE, PAGE_CONFIG):
            # 走到这里只可能是 `include_settings=True` 且用户真进了设置页。
            state, reason = self._page_state(page)
            return ['（%s）' % (reason or '本页未实现')], ['note']

        return [], []

    def title(self):
        """标题行（中文，给人看的）。**不是**原作里那种 sprite 标题。"""
        bag = self._bag()
        cap = '%d/%d' % (len(bag), bag.capacity) if bag is not None else '-'
        return {
            PAGE_CLOSED: '',
            PAGE_ROOT: '菜单',
            PAGE_ITEMS: '道具（%s）' % cap,
            PAGE_ACTION: '道具 › %s' % ACTION_LABELS[self.action],
            PAGE_JUNK: '%s（%d 件）' % (JUNK_ENTRY_LABEL, len(self.inventory.junk)),
            PAGE_STAT: '状态',
            PAGE_EQUIP: '装备',
            PAGE_PHONE: '手机',
            PAGE_TECH: '技能',
            PAGE_CONFIG: '设置',
        }.get(self.page, '')

    def hint(self):
        if self.page == PAGE_ROOT:
            return HINT_ROOT
        if self.page == PAGE_ITEMS:
            return HINT_LIST
        if self.page == PAGE_ACTION:
            return HINT_ACTION
        return HINT_READONLY

    # ---------------------------------------------------------------- 帧
    def frame(self, message=None):
        """当前状态 → `MenuFrame`。`message` 只覆盖本帧（`last_message` 另存）。"""
        page = self.page
        rows, _labels = self._rows_and_labels()
        if page == PAGE_CLOSED:
            return MenuFrame(PAGE_CLOSED, MENU_NO_LIGHT[PAGE_CLOSED], '', [], [], -1,
                             message, '', True)
        title = self.title()
        lines = ['%s%s' % (CURSOR_ON if i == self.cursor else CURSOR_OFF, r)
                 for i, r in enumerate(rows)]
        menuno = (MENU_NO_DARK if self.is_dark else MENU_NO_LIGHT).get(page, -2)
        msg = message if message is not None else self.last_message
        return MenuFrame(page, menuno, title, rows, lines, self.cursor, msg,
                         self.hint(), False)

    # ---------------------------------------------------------------- 按键
    def key(self, name):
        """处理一次按键，返回新的 `MenuFrame`。**不认识/不该响应 ⇒ 原样返回当前帧**。"""
        k = normalize_key(name)
        if k is None:
            return self.frame()
        self.last_message = None

        if not self.is_open:
            if k == 'menu':
                return self.open()
            return self.frame()

        if k == 'menu':
            return self.close()

        handler = {
            PAGE_ROOT: self._key_root,
            PAGE_ITEMS: self._key_items,
            PAGE_ACTION: self._key_action,
            PAGE_JUNK: self._key_junk,
        }.get(self.page)
        if handler is not None:
            handler(k)
        elif k == 'cancel':
            self._goto(PAGE_ROOT)
        return self.frame()

    def _goto(self, page, cursor=0):
        self.page = page
        self.cursor = cursor

    def _move(self, n, k):
        """列表页的上下移动（循环）。**不处理动作页** —— 动作页的三选一单独写，
        因为它要同时维护 `action`（语义）与 `cursor`（显示），两者必须一致。"""
        if n <= 0:
            return
        if k == 'up':
            self.cursor = (self.cursor - 1) % n
        elif k == 'down':
            self.cursor = (self.cursor + 1) % n

    def _key_root(self, k):
        es = self.entries(visible_only=True)
        self._move(len(es), k)
        if len(es) == 0:
            self.cursor = 0
            return
        self.cursor = min(self.cursor, len(es) - 1)
        if k == 'confirm':
            pid = es[self.cursor][0]
            self._enter(pid)

    def _enter(self, pid):
        if pid == PAGE_ITEMS:
            self._goto(PAGE_ITEMS, 0)
        elif pid == PAGE_JUNK:
            self._goto(PAGE_JUNK, 0)
        elif pid in (PAGE_STAT, PAGE_TECH):
            self._goto(pid, 0)
        else:
            # 登记但无数据的页：**不进**（进了一个空页比"进不去"更让人困惑）。
            state, reason = self._page_state(pid)
            _log.info('页面 %s 不可用（%s）：%s', pid, state, reason)
            self.refusals += 1

    def _key_items(self, k):
        rows = self.inventory.visible_rows(self.inventory.world)
        self._move(len(rows), k)
        if k == 'cancel':
            self._goto(PAGE_ROOT, 0)
            return
        if k == 'confirm' and rows:
            self.cursor = min(self.cursor, len(rows) - 1)
            self.row_index = self.cursor              # 记住是在哪一行按的
            self.slot_index = rows[self.cursor][0]    # ★ 背包槽位（不是行号）
            self.action = ACT_USE
            self._goto(PAGE_ACTION, ACT_USE)

    def _key_action(self, k):
        """动作页：`cursor` 归"使用/查看/丢弃"，要操作的道具**只认 `slot_index`**。"""
        if k in ('up', 'left'):
            self.action = (self.action - 1) % 3
        elif k in ('down', 'right'):
            self.action = (self.action + 1) % 3
        # 显示光标与语义动作**同一步**更新（分开维护就会出现"显示停在查看、实际执行丢弃"）。
        self.cursor = self.action
        if k == 'cancel':
            self._goto(PAGE_ITEMS, self.row_index)
            return
        if k == 'confirm':
            msg = self._perform(self.action, self.slot_index)
            # 行动完回列表，光标回到原来那一行（原作的 `menuno` 回到 1）。
            self._goto(PAGE_ITEMS, self.row_index)
            self.last_message = msg

    def _key_junk(self, k):
        n = len(self.inventory.junk)
        self._move(n, k)
        if k == 'cancel':
            self._goto(PAGE_ROOT, 0)
            return
        if k == 'confirm' and n:
            self.cursor = min(self.cursor, n - 1)
            self.last_message = item_system.VERDICT_MESSAGE[item_system.VERDICT_JUNK]

    # ---------------------------------------------------------------- 三动作
    def _perform(self, action, slot_index):
        if action == ACT_USE:
            return self._do_use(slot_index)
        if action == ACT_LOOK:
            return self._do_look(slot_index)
        if action == ACT_DROP:
            return self._do_drop(slot_index)
        return None

    def _do_use(self, slot_index):
        """★ 使用 —— **全部**判定交给 `item_system.Inventory.use()`。

        本方法只把 verdict 翻成一句人话。这样"菜单里亮着、按下去被拒"在结构上不可能。
        """
        out = self.inventory.use(self.inventory.world, slot_index)
        self.uses += 1
        v = out.verdict
        if v == item_system.VERDICT_EMPTY:
            return None
        if v == item_system.VERDICT_JUNK:
            return out.message or item_system.VERDICT_MESSAGE[item_system.VERDICT_JUNK]
        if v == item_system.VERDICT_MYSTERY:
            # ★★ 用户口径的验收点：异章节 / 异世界 / 场景门控 ⇒ 这句。
            return item_system.MSG_MYSTERY
        name = out.item.display_name if out.item else ''
        if not out.healed:
            return '* 你使用了「%s」。' % name
        # ★ 下面三种说法**刻意分开**：本产品当前没有队伍 HP 模型，
        #   若统一写成"回复了 N 点 HP"，就是在**宣称一件没发生的事**。
        #   （本项目纪律：不把没做的说成做了 —— 宁可文案长一点。）
        if self.apply_heal is None:
            return '* 你使用了「%s」，本应回复 %d 点 HP（队伍数值未接线，本次未实际改动）。' \
                % (name, out.healed)
        applied = None
        try:
            applied = self.apply_heal(out.healed)
        except Exception:
            _log.exception('apply_heal 抛异常（如实说"没生效"，不假装回了血）')
        if applied is None:
            return '* 你使用了「%s」，但回复没有生效。' % name
        return '* 你使用了「%s」，回复了 %d 点 HP。' % (name, int(applied))

    def _do_look(self, slot_index):
        """查看 —— 照抄原作 `scr_itemdesc` / `scr_litemdesc` 的语义（只出台词）。"""
        bag = self._bag()
        slot = bag.at(slot_index) if bag else None
        if slot is None:
            return None
        if slot.junked:
            return item_system.VERDICT_MESSAGE[item_system.VERDICT_JUNK]
        d = slot.item.desc
        if d:
            return '* %s：%s' % (slot.display_name, d)
        if not slot.item.known:
            # ★ 不静默：名字都查不到（语言包拿不到）就明说，而不是编一个。
            return '* %s：名字和说明都看不清了。' % slot.display_name
        return '* %s：没什么特别的。' % slot.display_name

    def _do_drop(self, slot_index):
        """丢弃 —— 照抄 `obj_overworldc_Step_0` 的 `dontthrow` 名单 + 随机台词。"""
        bag = self._bag()
        slot = bag.at(slot_index) if bag else None
        if slot is None:
            return None
        w = self.inventory.world
        if (w, slot.item.id) in item_system.DONT_THROW or \
                (w, slot.item.id) in DONT_THROW_TEXTS:
            # ★ 丢不掉：照抄 `obj_overworldc_Step_0` 的 `dontthrow` 名单
            #   （id 5 一条、id 11 走 `dontthrowtype = 2` 的专属台词）。
            self.refusals += 1
            return DONT_THROW_TEXTS.get((w, slot.item.id), DONT_THROW_DEFAULT)
        bag.remove_at(slot_index)
        self.drops += 1
        return self._drop_flavor()

    def _drop_flavor(self):
        """照抄 `i = round(random(30))` 的分布：i ≤ 3 取 4 个分支，否则兜底。"""
        try:
            i = int(round(self.rng.random() * 30))
        except Exception:
            i = 30
        if 0 <= i < len(DROP_FLAVOR):
            return DROP_FLAVOR[i]
        return DROP_FLAVOR_DEFAULT

    # ---------------------------------------------------------------- 诊断
    def describe(self):
        return '菜单=%s 光标=%d 动作=%s 垃圾团=%d 件（开 %d 次 / 用 %d / 丢 %d / 拦 %d）' % (
            self.page, self.cursor, ACTION_LABELS[self.action], len(self.inventory.junk),
            self.opens, self.uses, self.drops, self.refusals)


def build(inventory, **kw):
    """便捷入口（接线层用）—— 顺手把不用的页登记打进日志，免得到时候查不出"为什么没有状态页"。"""
    menu = ItemMenu(inventory, **kw)
    for rec in menu.page_notes():
        _log.info('菜单页面未启用：%s（%s）—— %s', rec['label'], rec['state'], rec['reason'])
    return menu

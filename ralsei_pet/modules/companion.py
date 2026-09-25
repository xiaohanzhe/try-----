# -*- coding: utf-8 -*-
"""伙伴实体层 —— 「多只宠物同桌」的最底层数据模型（L1，零依赖）。

回答用户这条需求（第 46 轮）：
    「嵌入一下和伙伴的交互系统，方便以后多宠物互相互动」
    「跟随系统这类的按原作的就行，还是跟随 kris 如果 kris 在的话，
      当然，也可自主行动，只是在需要统一行动时跟随」
    「原作里该有的可以交互的东西也要有哦，也就是和原作内的效果一样」

★ 本层只做两件事
------------------
1. **伙伴 = 一份数据**（身份 / 别名 / 槽位 / 轨迹缓冲 / 跟随模式）；
2. **可交互物 = 一套协议**（`interact()` → `on_interact()` + 全局锁 + 防抖）。

**不做**：不做对话（L2 `companion_dialog`）、不做名册/调度（L3 `companion_roster`）、
不碰 Qt、不播放音频、不做寻路。

零依赖纪律（🔴 与 scene_system / scene_pathfind / scene_walk 同源）
----------------------------------------------------------------
本模块**禁 import Qt、禁 import 任何项目内模块**（只准标准库）。
`main.py` 在 import 期就要建控制器，控制器再 import 本模块；
回头 import 项目内模块就会把「初始化环」接上（本项目已踩 4 次，症状是
import 期直接崩、零输出）。⇒ 本文件只准 `collections` / `logging` / `math`。

★ 原作依据（第 46 轮 UTMT 反编译取证，见
  `code-quality-audit/第46轮-原作代码通读/_evidence/原作系统取证46.md`）
-----------------------------------------------------------------------
· **跟随 = 毛毛虫（caterpillar）**，不是独立寻路：
    `scr_makecaterpillar(x, y, char_id, slot)` 里
    `global.cinstance[slot].target = 12 + (slot * 12);`
    `obj_caterpillarchara` 有 `remx[] / remy[] / facing[]`，**长度各 25**，
    初值 = 主角当前位置；`parent = obj_mainchara`；`depth = 主角 + 5`；
    暗世界 `image_xscale = 2`。
  ⇒ 跟随者走的是**主角走过的路**，天然不撞墙、不会自己卡住。
· **队伍规模 = 2 个队友位**：`scr_setparty(arg0, arg1)` 正好两个参数
  ⇒ 与用户说的"我会准备另外两个 7B 的设定"数量**正好对上**。
· **可交互协议**：`scr_interact()` = `myinteract = 1; event_user(0);`
  交互对象在 User Event 0 里设 `global.interact = 1`（上锁）+ 建 `obj_dialoguer`；
  对话结束（`instance_exists(mydialoguer) == false`）后在自己的 Step 里
  解锁并 `with (obj_mainchara) onebuffer = 5;`（防抖 5 帧）。

★ 三条设计律（都有正/负控制断言）
----------------------------------
1. **找不到就是不找到** —— 身份解析失败返回 `None`，**绝不**回落到"可能是他"。
   静默降级是本项目头号敌人（同 scene_pathfind 的"走不到 → None 不就近凑"）。
2. **锁必须能释放** —— 任何异常路径（`on_interact` 抛异常、对话实例凭空消失、
   生成失败）都必须把全局锁解开。锁死 = 整个交互系统永久瘫痪。
3. **数值照抄，出处可查** —— 12 / 24 / 25 / 2 / 5 这些数字不是拍脑袋，
   每个都在上面的原作依据里有出处；本项目自创的数值（RALLY 的收紧倍率、
   远距阈值）**单独标注为自创**，不与原作数值混在一起。
"""
import collections
import logging
import math

_log = logging.getLogger(__name__)

# ===========================================================================
#  常量（★ 每个都有出处；标「自创」的是本项目的扩展，不是原作数值）
# ===========================================================================

#: ★ 轨迹环缓冲长度 —— 照抄 `obj_caterpillarchara` 的 `remx[25]` / `remy[25]` / `facing[25]`。
TRACE_LEN = 25

#: ★ 跟随滞后基准帧数 —— 照抄 `scr_makecaterpillar` 的 `target = 12 + (slot * 12)`。
FOLLOW_LAG_BASE = 12
FOLLOW_LAG_STEP = 12

#: ★ 队友位数量 —— 照抄 `scr_setparty(arg0, arg1)` 的两个参数。
#: 与用户口径「我会准备另外两个 7B 的设定」数量一致。
MAX_COMPANIONS = 2

#: ★ 暗世界缩放倍率 —— 照抄 `obj_caterpillarchara` 的 `darkmode ⇒ image_xscale = 2`。
DARK_SCALE = 2

#: ★ 原作 `global.darkzone` 的取值域（第 46 轮从 `obj_dialoguer_Create_0` 实证）。
DARKZONE_LIGHT = 0
DARKZONE_DARK = 1

#: ★ 交互防抖帧数 —— 照抄 `with (obj_mainchara) onebuffer = 5;`
INTERACT_COOLDOWN_FRAMES = 5

#: ★ 原作帧率（`GMS2FPS = 30`，第 43 轮相机取证确认）。
GMS2_FPS = 30

#: 防抖时长（秒）。帧数 ÷ 帧率 —— 本项目把 `update(dt)` 的 dt 定为**秒**，
#: 所以必须显式换算，不能把「5」当成秒用（那会变成 5 秒，比原作慢 30 倍）。
INTERACT_COOLDOWN_SEC = INTERACT_COOLDOWN_FRAMES / float(GMS2_FPS)

#: ★ 照抄原作的朝向默认值：`scr_caterpillar_interpolate` 里 `facing[i] = 2`
#: （对 `obj_caterpillarchara` 来说 2 = 朝前/朝下，与 Ralsei 的四向 sprite 表一致）。
FACING_DEFAULT = 2

#: 「自创」远距阈值（px）：主角移动且距离超过它 ⇒ 从 FREE 切 FOLLOW。
#: 原作没有这个概念（原作里队友**永远**在队列里），这是为满足用户口径
#: 「也可自主行动，只是在需要统一行动时跟随」而加的。调这个数不影响任何照抄值。
FOLLOW_FAR_THRESHOLD = 160.0

#: 「自创」RALLY（聚拢）时的滞后收紧倍率：`lag // 4`。
#: 原作的 `scr_setparty` 在切场景前直接用主角坐标落位；我们用"更短的滞后"近似，
#: 因为 RALLY 还要求伙伴**自己走到**主角附近（不会瞬移）。
RALLY_LAG_DIVISOR = 4


class FollowMode(object):
    """跟随三态（字符串常量，便于直接进 JSON / 配置）。

    · `FREE`   —— 自主行动（常态，对应用户口径「也可自主行动」）
    · `FOLLOW` —— 走主角走过的路（毛毛虫式滞后采样，对应用户口径「跟随 kris」）
    · `RALLY`  —— 更紧地聚拢（切场景 / 要对话前，**本项目扩展**，非原作机制）
    """

    FREE = 'free'
    FOLLOW = 'follow'
    RALLY = 'rally'

    ALL = (FREE, FOLLOW, RALLY)


# ===========================================================================
#  身份归一
# ===========================================================================

def normalize_id(name):
    """说话人身份归一：**去首尾空白（含全角空格）+ 转小写 + 内部空白折叠为单空格**。

    照抄原作 `scr_anyface` 的 `_speaker = string_lower(_speakerC);`
    （原作的别名就是靠大小写不敏感比较生效的：`"ralsei" || "ral"`）。

    ⚠️ **不**做"模糊匹配/拼音/编辑距离"。找不到就是找不到（设计律 1）——
    模糊匹配会让"苏西"匹配上"Sans"这类事故无法被断言抓到。
    """
    if not isinstance(name, str):
        return ''
    s = name.replace('\u3000', ' ').strip().lower()
    return ' '.join(s.split())


# 无意义词：`normalize_id` 之后若等于这些，视为"没给名字"。
_EMPTY_IDS = frozenset({'', 'none', 'null', 'undefined', '-', '?', 'n/a'})


def is_blank_id(name):
    """归一后是不是"没给名字"。`activate()` 用它跳过空槽位（对应原作 `arg0 = false`）。"""
    return normalize_id(name) in _EMPTY_IDS


# ===========================================================================
#  伙伴
# ===========================================================================

#: 轨迹采样点：位置 + 朝向（对应原作 `remx[i] / remy[i] / facing[i]` 三个平行数组）。
TracePoint = collections.namedtuple('TracePoint', ('x', 'y', 'facing'))


class Companion(object):
    """一只伙伴的**数据模型**（不含对话实现、不含渲染）。

    参数
    ----
    speaker_id : str
        ★ 主键。**必须是字符串**（不是序号）—— 原作全系统都以字符串名字
        作为角色身份的主键：`scr_anyface` 比字符串、`scr_get_plat_followers`
        带 `name` 字段、`c_actormoveparty` 用 `scr_findactor("kris")`。
    display_name : str | None
        显示名（可中文）。缺省 = `speaker_id`。
    aliases : iterable[str]
        别名（对应原作 `"ralsei" || "ral"`）。**统一小写归一后存储**。
    slot : int
        队友位序号（0/1）。决定跟随滞后：`12 + slot * 12`。
    persona_path : str | None
        人设文件路径（★ 单一真源 = 该文件；这里只存路径，不读内容 ——
        读文件是 L3/接线层的事，本层保持"纯数据"）。
    darkmode : int
        0 = 光明世界 / 1 = 暗世界（原作 `global.darkzone` 的取值域）。
    """

    #: 「自创」RALLY 时把滞后收紧到 `follow_lag // RALLY_LAG_DIVISOR`（下限 1 帧）。
    RALLY_LAG_DIVISOR = RALLY_LAG_DIVISOR

    def __init__(self, speaker_id, display_name=None, aliases=(),
                 slot=0, persona_path=None, darkmode=DARKZONE_LIGHT):
        sid = normalize_id(speaker_id)
        if not sid:
            raise ValueError('Companion.speaker_id 不能为空（身份必须显式）')
        self.speaker_id = sid
        self.display_name = display_name or speaker_id
        self.aliases = tuple(sorted(
            set(a for a in (normalize_id(x) for x in aliases) if a and a != sid)))
        self.slot = int(slot)
        self.persona_path = persona_path
        self.darkmode = int(darkmode)

        # ---- 行为状态 ----
        self.mode = FollowMode.FREE
        self.x = 0.0
        self.y = 0.0
        self.facing = FACING_DEFAULT
        #: ★ 主角位置历史环缓冲（长度 25，同原作 `remx/remy/facing`）。
        self.trace = collections.deque(maxlen=TRACE_LEN)
        #: 走路/脸红计时（对应原作 `walktimer` / `blushtimer`，留给动画层用）。
        self.walktimer = 0
        self.blushtimer = 0

    # ---------------------------------------------------------------- 身份
    def names(self):
        """本伙伴能被 `resolve()` 命中的全部名字（主键 + 显示名 + 别名）。"""
        out = [self.speaker_id, normalize_id(self.display_name)]
        out.extend(self.aliases)
        return tuple(n for n in dict.fromkeys(out) if n)

    # ---------------------------------------------------------------- 缩放
    @property
    def scale(self):
        """渲染缩放倍率：暗世界 ×2（照抄原作 `image_xscale`）。"""
        return DARK_SCALE if self.darkmode == DARKZONE_DARK else 1

    # ---------------------------------------------------------------- 跟随
    @property
    def follow_lag(self):
        """★ 落后主角多少帧 —— 照抄 `target = 12 + (slot * 12)`。"""
        return FOLLOW_LAG_BASE + self.slot * FOLLOW_LAG_STEP

    @property
    def effective_lag(self):
        """当前模式下真正使用的滞后帧数（RALLY 收紧；自创规则见常量注释）。"""
        if self.mode == FollowMode.RALLY:
            return max(1, self.follow_lag // self.RALLY_LAG_DIVISOR)
        return self.follow_lag

    def set_mode(self, mode):
        """切换跟随模式。非法值**不静默吃掉** —— 返回 False 并保持原值。"""
        if mode not in FollowMode.ALL:
            _log.warning('非法跟随模式 %r，保持 %r', mode, self.mode)
            return False
        self.mode = mode
        return True

    def push_trace(self, x, y, facing=None):
        """把主角的一个位置压进历史（每帧一次）。"""
        self.trace.append(TracePoint(float(x), float(y),
                                     self.facing if facing is None else int(facing)))

    def reset_trace(self, x, y, facing=FACING_DEFAULT):
        """把历史**填满**成同一个点 —— 照抄原作 `remx[i]` 的初值
        「= 主角当前位置」。

        为什么必须填满而不是清空：清空的话 `sample_at(lag)` 在头 `lag` 帧
        返回 `None` ⇒ 伙伴会从 `(0, 0)` 一路"飞"到主角身后（可见的穿屏）。
        填满 ⇒ 刚进场的伙伴就出现在主角身后 `lag` 帧的位置，与原作一致。
        """
        self.trace.clear()
        pt = TracePoint(float(x), float(y), int(facing))
        for _ in range(TRACE_LEN):
            self.trace.append(pt)
        self.x, self.y, self.facing = pt.x, pt.y, pt.facing
        return self

    def sample_at(self, lag):
        """取「**lag 帧前**」那一个采样点。历史不够长 ⇒ `None`（**不猜**）。

        ★ 下标为什么是 `-(lag+1)`：`trace[-1]` 是**刚压进去的当前帧**
        （对应原作 `remx[0] = obj_mainchara.x`，下标 = **年龄**），
        所以"12 帧前" = `remx[12]` = `trace[-13]`。
        第一版写成 `trace[-lag]` ⇒ 实际只滞后 11 帧（差 1 帧）。
        这种"差一"不会有人肉眼发现，但会让"滞后帧数 = 12"这句**照抄声明变成假话**，
        所以必须是可断言的正确值。

        ⚠️ 与插值版的区别：原作另有 `scr_caterpillar_interpolate`
        （`remx[i] = 主角 + (自己 - 主角) * (i / target)`，ch5 还有
        `scr_caterpillar_stackandinterpolate`），那是**插值**读法，需要额外知道
        "每帧追赶多少"这个速度常数。我们选**滞后采样**，因为它只需要
        `target` 这一个我们已经取到的数，不需要凭空发明第二个。
        """
        lag = int(lag)
        if lag < 1 or len(self.trace) < lag + 1:
            return None
        return self.trace[-(lag + 1)]

    def __repr__(self):
        return '<Companion %s slot=%d mode=%s lag=%d>' % (
            self.speaker_id, self.slot, self.mode, self.effective_lag)


# ===========================================================================
#  可交互物协议（照抄 scr_interact / event_user(0) / global.interact / onebuffer）
# ===========================================================================

class InteractBus(object):
    """★ 对应原作 `global.interact` 这把**全局锁**。

    原作是单变量；这里包一层是为了能问三个问题：
    谁拿着锁（诊断）、被挡了几次（诊断）、以及**能不能保证释放**（设计律 2）。
    """

    def __init__(self):
        self.holder = None
        self.blocked_count = 0

    @property
    def locked(self):
        return self.holder is not None

    def try_acquire(self, obj):
        """拿锁。已被别人拿着 ⇒ `False` 并计数（**不排队、不抢占**，同原作）。"""
        if self.holder is not None:
            self.blocked_count += 1
            return False
        self.holder = obj
        return True

    def release(self, obj=None):
        """放锁。`obj` 给了就必须是当前持有者（防"别人替我解锁"）。"""
        if self.holder is None:
            return False
        if obj is not None and self.holder is not obj:
            return False
        self.holder = None
        return True


_DEFAULT_BUS = None


def default_bus():
    """进程级默认锁（惰性创建）。测试里请用 `reset_default_bus()` 隔离。"""
    global _DEFAULT_BUS
    if _DEFAULT_BUS is None:
        _DEFAULT_BUS = InteractBus()
    return _DEFAULT_BUS


def reset_default_bus():
    """换一把新的默认锁（**只给测试用**：G2 套件之间不许互相污染）。"""
    global _DEFAULT_BUS
    _DEFAULT_BUS = InteractBus()
    return _DEFAULT_BUS


class Interactable(object):
    """可交互物基类 —— 「该交互的还可以交互」的协议层。

    子类只实现 `on_interact(actor)`，返回 **True = 有东西发生（上锁等它结束）**，
    False = 什么也没发生（立刻解锁，不留锁）。

    对应原作的三个状态（`obj_readable` 是最小范例）::

        Create_0 :  myinteract = 0;
        Other_10 :  (被交互) 设文本 + global.interact = 1 + 建 obj_dialoguer;  myinteract = 3;
        Step_0   :  if (myinteract == 3 && !instance_exists(mydialoguer)) {
                        global.interact = 0; myinteract = 0; 主角.onebuffer = 5;
                    }
    """

    #: ★ 状态值照抄原作 `obj_readable` 的 `myinteract`。
    MYINTERACT_IDLE = 0     #: 待机
    MYINTERACT_FIRED = 1    #: `scr_interact()` 刚触发（原作 `myinteract = 1`）
    MYINTERACT_DIALOG = 3   #: 对话中（原作 User Event 0 里设成 3）

    def __init__(self, key, bus=None):
        self.key = str(key)
        self.bus = bus if bus is not None else default_bus()
        self.myinteract = self.MYINTERACT_IDLE
        self.dialog = None          #: 对话句柄（对应原作的 `mydialoguer` 实例）
        self.actor = None           #: 最近一次交互的发起者
        self.cooldown = 0.0         #: 剩余防抖时间（秒）
        self.interact_count = 0
        self.dialog_count = 0

    # ---------------------------------------------------------------- 协议
    def interact(self, actor=None):
        """★ 对应 `scr_interact()`。返回 True 表示"确实交互上了"。

        两道自身闸门 + 一道全局闸门，顺序即优先级：
        ① 自己还在防抖中 / 不在待机态 ⇒ 不响应；
        ② 全局锁被别人拿着 ⇒ 不响应（由 `try_acquire` 判定并**计数**）；
        ③ 拿到锁 → `myinteract = 1` → 调 `on_interact`（对应 `event_user(0)`）。

        ⚠️ 首版在 `try_acquire` 之前又写了一次 `if self.bus.locked: return False`，
        结果 `blocked_count` **永远不会增加**（那条提前返回绕过了计数）——
        一个"看着在统计、其实恒为 0"的死字段。删掉重复判定，让锁判定只有一处。
        """
        if self.cooldown > 0:
            return False
        if self.myinteract != self.MYINTERACT_IDLE:
            return False
        if not self.bus.try_acquire(self):
            return False

        self.myinteract = self.MYINTERACT_FIRED
        self.actor = actor
        self.interact_count += 1
        opened = False
        try:
            opened = bool(self.on_interact(actor))
        except NotImplementedError:
            # ★ `NotImplementedError` = **接线错误**，不是运行时故障 ⇒ 解锁后照样往外抛。
            #   把它一起吞掉会让"某类可交互物根本没实现交互"变成静默无效。
            self.myinteract = self.MYINTERACT_IDLE
            self.bus.release(self)
            raise
        except Exception:
            # ★ 设计律 2：其它异常也必须落到"解锁"这条路上，
            #   否则整个交互系统永久瘫痪（一次异常 = 所有可交互物全部失灵）。
            _log.exception('on_interact 抛异常（key=%s）⇒ 立即解锁', self.key)
            opened = False

        if opened:
            self.myinteract = self.MYINTERACT_DIALOG
            self.dialog_count += 1
        else:
            self.myinteract = self.MYINTERACT_IDLE
            self.bus.release(self)
        return opened

    def on_interact(self, actor=None):
        """子类实现。返回 True = 打开了对话（锁住），False = 无事发生（解锁）。"""
        raise NotImplementedError('%s 未实现 on_interact' % type(self).__name__)

    # ---------------------------------------------------------------- 收尾
    def dialog_done(self):
        """★ 对应原作 `instance_exists(mydialoguer) == false`。"""
        return not self.dialog

    def update(self, dt):
        """每帧调一次（`dt` 单位 = **秒**）。返回 True 表示本帧**刚解锁**。"""
        if self.cooldown > 0:
            self.cooldown = max(0.0, self.cooldown - float(dt))
        if self.myinteract == self.MYINTERACT_DIALOG and self.dialog_done():
            self.myinteract = self.MYINTERACT_IDLE
            self.dialog = None
            self.bus.release(self)
            self.cooldown = INTERACT_COOLDOWN_SEC
            # ★ 照抄 `with (obj_mainchara) onebuffer = 5;`。
            #   只在 actor **本来就有**这个字段时才写 —— 不为任意 actor 凭空造属性
            #   （那会让"字段名写错"这类事故变成静默新增而不是报错）。
            if self.actor is not None and hasattr(self.actor, 'interact_cooldown'):
                self.actor.interact_cooldown = INTERACT_COOLDOWN_SEC
            return True
        return False

    @property
    def busy(self):
        return self.myinteract != self.MYINTERACT_IDLE

    def __repr__(self):
        return '<%s key=%s myinteract=%d locked=%s>' % (
            type(self).__name__, self.key, self.myinteract, self.bus.locked)


class ReadableInteractable(Interactable):
    """最小可交互物范例（对应原作 `obj_readable`：读告示/牌子）。

    `present(text, actor)` 由接线层注入（P3 才接 UI）。它必须返回一个
    **"对话句柄"**（任何真值对象都行）——`update()` 靠它的真假判断"读完了没"，
    这正是原作 `instance_exists(mydialoguer)` 的等价物。
    """

    def __init__(self, key, text, present=None, bus=None):
        Interactable.__init__(self, key, bus=bus)
        self.text = text
        self.present = present

    def on_interact(self, actor=None):
        if self.present is None:
            _log.warning('可交互物 %s 没接线（present=None）⇒ 如实返回"没发生"', self.key)
            return False
        self.dialog = self.present(self.text, actor)
        return bool(self.dialog)


# ===========================================================================
#  自检 / 描述
# ===========================================================================

def describe_companion(c):
    """一行中文描述（给日志与报告用；**不参与任何判据**）。"""
    return '「%s」id=%s 槽位=%d 跟随滞后=%d帧 模式=%s%s' % (
        c.display_name, c.speaker_id, c.slot, c.follow_lag, c.mode,
        '（暗世界×2）' if c.darkmode == DARKZONE_DARK else '')


def distance(a, b):
    """两点欧氏距离（`select_mode` 的输入）。入参非法 ⇒ `None`（不猜）。"""
    try:
        return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))
    except Exception:
        return None

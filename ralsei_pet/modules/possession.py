# -*- coding: utf-8 -*-
"""附身（POSSESSION）—— Z 键把"操控权"从灵魂切到某个角色身上（第82轮 R5）。

用户口径（第84轮**现行**，逐字）
--------------------------------
（第76轮旧口径）「交互键用Z（对 kris 和 firsk，niko 用可以在征求他们同意的情况下附身
（特效用原作的），也就是达到原作操控的功能）」
（**第84轮新口径，推翻上一条**）「**所有人附身都要经过同意哦**，
附身后要和原作的效果一样就是了，对了，**原作该有的互动技能这类的都得有哦**」

⇒ **现行实现**：`POSSESSION_KINDS` 里 kris / ut_frisk / os_niko **全部 = `KIND_CONSENT`**
（即：谁都先问；问过同意了才附身）。`KIND_DIRECT` 保留但**当前无成员**（供将来扩展）。

★★★ 原作依据（第82轮 UTMT 反编译取证，物证全文见
     `code-quality-audit/第82轮-灵魂附身R5/_evidence/`）
------------------------------------------------------------------
源：`undertale/assets/game.droid`（79,628,496 B），UTMT CLI v0.9.2.0，
`CodeImportGroup.DecompileExistingCode` 反编译 469 段 → 蒸馏 19 段入库。

| 事实 | 出处（逐字） |
|---|---|
| **确认键 Z → `control_check_pressed(0)`** | `obj_mainchara_Step_0`：`if (control_check_pressed(0)) { event_user(0); }` |
| **交互的出口是 `event_user(0)`** | 同上（`obj_mainchara_Other_12` 就是 user event 0 的实现） |
| **交互做的事** | `obj_mainchara_Other_12`：`if (global.interact == 0 && global.flag[17] == 0) { snd_play(snd_squeak); global.interact = 5; global.menuno = 0; control_clear(2); }` |
| **主角移动 = 方向键布尔 × 3 px/帧** | `obj_mainchara_Step_0`：`if (obj_time.left) { ... x -= 3; }`（四向同构） |
| **移动由全局控制器 `obj_time` 驱动** | `obj_time_Create_0`：`up=0; down=0; left=0; right=0;` + `control_init()` |
| **灵魂移动 = `obj_time` 布尔 × `global.sp`** | `obj_heart_Step_0`：`if (obj_time.up) { y -= global.sp; }` |
| **灵魂速度 = `global.asp`** | `obj_heart_Create_0`：`global.sp = global.asp;` |
| **"接管"时清掉旧键** | `obj_mainchara_Other_12`：`control_clear(2)` |

★★★ 一句话结论：**原作里"操控谁"是同一套输入（`obj_time` 的四个布尔）指向不同实体**
—— 主角读 `obj_time.*`、灵魂也读 `obj_time.*`，区别只在速度（主角 3、灵魂 `global.sp`）。
所以"附身"在本项目里的**正确形状** = **把方向键的消费方从灵魂切到被附身角色**，
而不是新造一套"附身物理"。本模块只承载这条切换与它的状态，**不引入原作没有的物理**
（没有加速度、没有摩擦、没有跟随）。

三条纪律（与 `soul_entity` / `scene_camera` / `npc_system` 同源）
----------------------------------------------------------------
1. 只允许模块顶部 `import logging / math`。**禁 import Qt、禁 import 任何项目内模块**
   （`main.py` 在 import 期就会拉起本模块；回头 import 项目内模块会接上初始化环）。
2. 内部函数**不许**再 import（回归锁 `check82` 用 AST 强制）。
3. 不认识的东西**返回 `None` / `False`，不猜、不就近凑**（同 `pick_nearest` 纪律）。

★ 与原作**方向相反 / 本项目扩展**的两处（必须标注，不许冒充原作）
--------------------------------------------------------------
* **"征求同意"**：原作里只有主角一人可操控（`obj_herokris`），**没有"问对方能不能附身"**
  这回事。这是用户口径带来的**本项目扩展**，本模块用 `ConsentState` 显式建模。
  ★ **第84轮起该扩展适用于全体**（原来只有 Niko 走这条路，现在 kris / frisk 也走）。
* **特效**：用户说"特效用原作的" ⇒ 只用**原作已有的表现**（`snd_squeak` 音效 +
  灵魂消失/角色接管），**不新造光效/粒子**（原作里没有"附身光效"这个东西）。

★★★ 原作依据（第84轮 UTMT 反编译取证 Deltarune ch1，物证见
     `code-quality-audit/第84轮-原作互动技能取证/`）
--------------------------------------------------------------
源：`chapter1_windows/data.win`（14,658,588 B），97 objects / 274 codes，
    **`gml_ok=True`**（产物含 `if (`/`global.` ⇒ 真 GML，非空壳）。

| 事实 | 出处（逐字） |
|---|---|
| **交互 = 置标记 + 转交对方** | `scr_interact()`：`myinteract = 1; event_user(0);` |
| **被交互者被转向主角** | `obj_mainchara_Step_0`：`with (interactedobject) { facing = 3; }` |
| **交互射线按朝向四段矩形** | 同上：四个 `collision_rectangle(..., obj_interactable/obj_interactablesolid, ...)`，`d = global.darkzone + 1` |
| **★ 走路速度：光 3 / 暗 4** | `obj_mainchara_Create_0`：`wspeed = 3; bwspeed = 3; if (darkmode == 1) { bwspeed = 4; }` |
| **★ 跑动三段加速** | `obj_mainchara_Step_0`：`if (run == 1) { ... bwspeed + 1 ... +2 ... +3 ... }`（暗世界 +2/+4/+5） |
| **跑 = 按住 button2** | 同上：`if (button2_h() && twobuffer < 0) { run = 1; }` |
| **朝向枚举 0=下/1=右/2=上/3=左** | `Create_0`：`if (global.facing == 0) sprite_index = dsprite;` |
| **对话锁定全局闸** | `obj_interactablesolid_Other_10`：`myinteract = 3; global.interact = 1;` |
| **对话结束 + 5 帧缓冲** | `obj_interactablesolid_Step_0`：`global.interact = 0; ... onebuffer = 5;` |
| **★ 跟随队伍（R6 的原作出处）** | `obj_caterpillarchara_Create_0`：`parent = obj_mainchara;` + 25 格 `remx/remy` 轨迹；`scr_makecaterpillar`：`target = 12 + (arg3 * 12)` |
"""
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


import math

_log = logging.getLogger(_pet_logger_name(__name__))

SCHEMA_VERSION = 1

# ---------------------------------------------------------------- 原作常量

#: 原作确认键 ← `control_check_pressed(0)`（`obj_mainchara_Step_0`）。
#: ★ 用户裁定"交互键用 Z" ⇒ 本项目把 Z 映射到 control 0（原作里 0 号键就是确认键）。
CONFIRM_KEY = 'z'

#: 原作主角速度 = **3 像素/帧**（`obj_mainchara_Step_0`：`x -= 3;` / `y -= 3;`）。
#: 与灵魂的 `global.sp`（本项目 `SPEED_PX = 4.0`）**不同** —— 这是原作的既有差异，
#: 不是我们改的（主角比灵魂略慢，因为主角要踩格子/触发碰撞）。
HERO_SPEED_PX = 3.0

#: 原作用 `xprevious == (x + 3)` / `xprevious == (x - 3)` 做**回头判定**
#: （上一帧朝反方向走了整整一格 ⇒ 这一帧只补 2 px，避免"贴脸抖动"）。
#: 本项目保留这条形状（见 `PossessionState.drive`）。
TURN_BACK_STEP = 2.0

#: 原作帧率（第43轮实证 `GMS2FPS = 30`）。
FRAME_HZ = 30

#: ★ 本项目取值（非原作）：单帧 `dt` 上限（秒）。掉帧时不瞬移。
#: 与 `soul_entity.MAX_DT` **同值同理由**（两个实体在同一条 `update_movement` 上推进，
#: 钳制尺度必须一致，否则会出现"掉帧时灵魂停了而角色飞了"）。
MAX_DT = 0.1


# ---------------------------------------------------------------- 状态码

#: 没有附身（操控权在灵魂手里）。
MODE_FREE = 'free'
#: 正在"征求同意"（只对需要同意的角色，如 Niko）。
MODE_ASKING = 'asking'
#: 已附身（方向键驱动被附身角色）。
MODE_POSSESSED = 'possessed'
#: 附身被拒绝 / 中断。
MODE_REFUSED = 'refused'

#: 目标分类
KIND_DIRECT = 'direct'      #: 可直接附身（★ 第84轮后**本项目已无此类**，保留供扩展）
KIND_CONSENT = 'consent'    #: 需先征求同意（★ 第84轮起为**全部可附身者**）
KIND_FORBIDDEN = 'forbidden'  #: 不可附身


class PossessionTarget(object):
    """一个可附身的目标（NPC）的**附身属性**（零依赖小值对象）。

    :param npc_id: NPC id（与 `_registry.json` 同 id 体系）。
    :param name: 显示名（日志/台词用；缺省回落 npc_id）。
    :param kind: `KIND_DIRECT` / `KIND_CONSENT` / `KIND_FORBIDDEN`。
    :param scene: 该角色**当前所在**的场景 id（附身要求同场景；缺省 `None` = 不校验）。
    """

    __slots__ = ('npc_id', 'name', 'kind', 'scene')

    def __init__(self, npc_id, name=None, kind=KIND_FORBIDDEN, scene=None):
        self.npc_id = npc_id
        self.name = name if name else npc_id
        self.kind = kind if kind in _ALL_KINDS else KIND_FORBIDDEN
        self.scene = scene

    def __repr__(self):
        return '<PossessionTarget %s %s kind=%s scene=%r>' % (
            self.npc_id, self.name, self.kind, self.scene)


_ALL_KINDS = (KIND_DIRECT, KIND_CONSENT, KIND_FORBIDDEN)

#: ★★★ 用户口径的**唯一真源**。
#:
#: 口径演进（两代，别混）：
#:   * 第76轮：「交互键用Z（**对 kris 和 firsk**，**niko 用**可以在征求他们同意的情况下附身
#:     （特效用原作的），也就是达到原作操控的功能）」⇒ 当时 kris/frisk = DIRECT、niko = CONSENT。
#:   * **第84轮（现行）**：「**所有人附身都要经过同意哦**」⇒ **全部改 CONSENT**。
#:     ★ 这是**用户明确推翻**前一条的措辞，两个名字（kris / ut_frisk）从 DIRECT 迁到 CONSENT。
#:
#: 其它一律不可附身（原作里也只有主角一人可操控 —— `obj_herokris`）。
#: ⚠️ 这张表是**数据**，`check82` / `check84` 会拿它跟 `_registry.json` 对账
#:    （证明这些 id 真存在于登记表里，而不是凭空写的）。
POSSESSION_KINDS = {
    'kris': KIND_CONSENT,
    'ut_frisk': KIND_CONSENT,
    'os_niko': KIND_CONSENT,
}


def kind_of(npc_id):
    """查 `npc_id` 的附身类别；不在表里 ⇒ `KIND_FORBIDDEN`（**不猜**）。"""
    if not isinstance(npc_id, str):
        return KIND_FORBIDDEN
    return POSSESSION_KINDS.get(npc_id.strip(), KIND_FORBIDDEN)


def is_possessable(npc_id):
    """这个 NPC 能不能被附身（DIRECT 或 CONSENT 都算"能"）。"""
    return kind_of(npc_id) in (KIND_DIRECT, KIND_CONSENT)


def needs_consent(npc_id):
    """附身它之前要不要先征求同意。"""
    return kind_of(npc_id) == KIND_CONSENT


# ---------------------------------------------------------------- 同意状态机

class ConsentState(object):
    """"征求同意"的小状态机（**本项目扩展**：原作没有这一步）。

    只对 `KIND_CONSENT` 的目标使用。语义：
      * `None`  = 还没问
      * `True`  = 已同意
      * `False` = 已拒绝
    ★ 为什么不自造一个多枚举：同意是**三态**（未决/同意/拒绝），
      布尔两态会把"还没问"和"拒绝了"合并，于是"再问一次"永远触发不了
      （这是本项目反复踩的"状态少一档"的坑）。
    """

    __slots__ = ('_by_id',)

    def __init__(self):
        self._by_id = {}

    def get(self, npc_id):
        """取该目标的同意状态：`None` / `True` / `False`。"""
        return self._by_id.get(npc_id)

    def grant(self, npc_id):
        if not isinstance(npc_id, str) or not npc_id:
            return False
        self._by_id[npc_id] = True
        return True

    def refuse(self, npc_id):
        if not isinstance(npc_id, str) or not npc_id:
            return False
        self._by_id[npc_id] = False
        return True

    def reset(self, npc_id):
        """把某个目标打回"没问过"（例如换了场景/对话结束）。"""
        return self._by_id.pop(npc_id, None) is not None

    def clear(self):
        n = len(self._by_id)
        self._by_id.clear()
        return n

    def as_dict(self):
        return {'schema_version': SCHEMA_VERSION,
                'granted': sorted(k for k, v in self._by_id.items() if v),
                'refused': sorted(k for k, v in self._by_id.items() if not v)}

    def load_dict(self, data):
        """从快照恢复（只认显式列出的两桶，非法输入 ⇒ 清空并 False）。"""
        if not isinstance(data, dict):
            return False
        g = data.get('granted')
        r = data.get('refused')
        if not isinstance(g, (list, tuple)) or not isinstance(r, (list, tuple)):
            return False
        self._by_id = {}
        for k in g:
            if isinstance(k, str) and k:
                self._by_id[k] = True
        for k in r:
            if isinstance(k, str) and k:
                self._by_id[k] = False
        return True


# ---------------------------------------------------------------- 主状态机

class PossessionState(object):
    """附身状态机（无 Qt、无 IO，可离线单测）。

    它与 `SoulState` **不是**同一个东西，别混：
      * `SoulState` 管的是"灵魂自己怎么动"（速度/拖拽/闪烁）；
      * `PossessionState` 管的是"方向键**归谁**"（灵魂 or 被附身角色）。
    ★ 分开的理由：附身是可开关的**操控权转移**，而灵魂是一直存在的实体。
      把它塞进 `SoulState` 会变成"灵魂里有一半字段只在附身时才有意义"。

    :param consent: 可注入的 `ConsentState`（默认自建）。
    """

    __slots__ = ('mode', 'target', 'consent',
                 '_pressed', '_last_drive', 'x', 'y', '_target_x', '_target_y',
                 'reason')

    def __init__(self, consent=None, x=0.0, y=0.0):
        self.mode = MODE_FREE
        self.target = None            #: 当前/待附身的 `PossessionTarget`
        self.consent = consent if consent is not None else ConsentState()
        self._pressed = set()
        self._last_drive = (0, 0)     #: 上一帧位移（供回头判定）
        self.x = float(x)             #: 被附身角色的位置（逻辑房间坐标）
        self.y = float(y)
        self._target_x = float(x)     #: 附身前记录的原位（解除时回去）
        self._target_y = float(y)
        self.reason = ''              #: 最近一次状态变化的说明（日志用）

    # ------------------------------------------------------------ 只读
    @property
    def is_possessing(self):
        return self.mode == MODE_POSSESSED

    @property
    def is_asking(self):
        return self.mode == MODE_ASKING

    @property
    def possessed_id(self):
        t = self.target
        return t.npc_id if (self.is_possessing and t is not None) else None

    def describe(self):
        t = self.target
        return '附身[%s] 目标=%s %s' % (
            self.mode, (t.npc_id if t is not None else '无'), self.reason)

    # ------------------------------------------------------------ 请求附身
    def request(self, target, scene=None):
        """请求附身 `target`。返回**状态码**（`MODE_*`），不抛。

        判定序（**顺序即优先级**，与 `_clean_ai_reply` 同一纪律）：
          1. `target` 非法 / 不可附身（`KIND_FORBIDDEN`）⇒ 原状态不变，返回 `MODE_REFUSED`；
          2. 已在附身中 ⇒ 先 `_end()` 解除，再走新一轮（避免"叠着附身"）；
          3. `scene` 与目标 `scene` 不一致（都非 None）⇒ 拒绝（**附身要求同场景**）；
          4. `KIND_DIRECT` ⇒ 直接进 `MODE_POSSESSED`（★ 第84轮后**本表已无此类成员**，
             但仍保留这条分支：一旦将来有角色要"免问"，只需改数据不动逻辑）；
          5. `KIND_CONSENT` ⇒ 同意过（`True`）才进 `MODE_POSSESSED`，
             否则进 `MODE_ASKING`（等 `grant` / `refuse`）。
             ★ **第84轮现行口径**：kris / ut_frisk / os_niko **全走这一条**。
        """
        if not isinstance(target, PossessionTarget):
            self.reason = '非法目标（%r）' % (target,)
            return self.mode
        if target.kind == KIND_FORBIDDEN:
            self.reason = '不可附身：%s' % target.name
            return MODE_REFUSED
        if self.is_possessing:
            self._end('被新的附身请求取代')

        # 同场景校验（任一侧 scene 为 None 则不校验 —— 不拿未知当"不同"）
        if (scene is not None and target.scene is not None
                and scene != target.scene):
            self.reason = '不同场景（我=%s 目标=%s）' % (scene, target.scene)
            return MODE_REFUSED

        self.target = target
        if target.kind == KIND_DIRECT:
            return self._begin('直接附身（%s：可直接操控）' % target.name)
        # KIND_CONSENT
        if self.consent.get(target.npc_id) is True:
            return self._begin('已获同意后附身（%s）' % target.name)
        if self.consent.get(target.npc_id) is False:
            self.reason = '%s 拒绝过（可再次征求）' % target.name
            return MODE_REFUSED
        self.mode = MODE_ASKING
        self.reason = '征求 %s 的同意…' % target.name
        _log.info('附身：向 %s 征求意见', target.name)
        return MODE_ASKING

    def grant(self):
        """被问的人同意了 ⇒ 从 `MODE_ASKING` 进入附身。返回状态码。"""
        if self.mode != MODE_ASKING or self.target is None:
            self.reason = '没有在征求同意（当前 %s）' % self.mode
            return self.mode
        self.consent.grant(self.target.npc_id)
        return self._begin('%s 同意了' % self.target.name)

    def refuse(self):
        """被问的人拒绝了 ⇒ 回到 `MODE_FREE`（记下拒绝态）。返回状态码。"""
        if self.mode != MODE_ASKING or self.target is None:
            return self.mode
        self.consent.refuse(self.target.npc_id)
        name = self.target.name
        self.target = None
        self.mode = MODE_REFUSED
        self.reason = '%s 不同意' % name
        _log.info('附身：%s 拒绝了', name)
        return MODE_REFUSED

    def _begin(self, why):
        self.mode = MODE_POSSESSED
        self.reason = why
        self._pressed.clear()
        self._last_drive = (0, 0)
        _log.info('附身开始：%s（%s）', self.target.name, why)
        return MODE_POSSESSED

    def _end(self, why):
        if self.target is not None:
            _log.info('附身结束：%s（%s）', self.target.name, why)
        self.mode = MODE_FREE
        self._pressed.clear()
        self._last_drive = (0, 0)
        self.reason = why
        self.target = None
        return MODE_FREE

    def stop(self, why='用户解除'):
        """解除附身（再按一次 Z / 失焦 / 关掉菜单）。**幂等**。

        ★ 为什么叫 `stop` 而不是 `release`（第82轮踩过）：本类还有一个
          `release(key)` 是"松开方向键"—— 两个 `release` 同名，
          **后定义的会静默覆盖前一个**（Python 不报错），于是"解除附身"
          永远调到"松开方向键"，传 `why` 直接 `TypeError`。
          这正是本项目"一个名字两个意思"的老坑 ⇒ 一个叫 `stop`、一个叫 `release_key`。
        """
        return self._end(why)

    # ------------------------------------------------------------ 键盘
    def press(self, key):
        """按下方向键。返回"这是一次新按下"（自动重复返回 False）。

        ★ 与 `SoulState.press` 的区别：本类**只在自己处于附身态时**才记录按键 ——
          没附身时的方向键是灵魂的（由 `SoulState` 收），两边不抢。
        """
        d = _norm_dir(key)
        if d is None or not self.is_possessing:
            return False
        if d in self._pressed:
            return False
        self._pressed.add(d)
        return True

    def release_key(self, key):
        """松开方向键。返回 True 表示"确实松掉了一个按住的键"。"""
        d = _norm_dir(key)
        if d is None or d not in self._pressed:
            return False
        self._pressed.discard(d)
        return True

    def release_all(self):
        """放开所有方向键（失焦时用）。返回放开个数。"""
        return self.clear_keys()

    def clear_keys(self):
        n = len(self._pressed)
        self._pressed.clear()
        return n

    def pressed(self):
        return tuple(sorted(self._pressed))

    def direction(self):
        """当前方向 `(dx, dy)`（各取 -1/0/1；**分轴独立**，对角线不归一化）——
        与 `SoulState.direction` 同形（原作主角也是四向独立赋值）。"""
        dx = dy = 0
        if 'left' in self._pressed and 'right' not in self._pressed:
            dx = -1
        elif 'right' in self._pressed and 'left' not in self._pressed:
            dx = 1
        if 'up' in self._pressed and 'down' not in self._pressed:
            dy = -1
        elif 'down' in self._pressed and 'up' not in self._pressed:
            dy = 1
        return (dx, dy)

    # ------------------------------------------------------------ 推进
    def drive(self, dt):
        """按 `dt` 秒推进被附身角色。返回本次位移 `(dx, dy)`（**逻辑**房间像素）。

        照抄 `obj_mainchara_Step_0` 的四条：
        1. **按键即满速**（无加速度）；2. **松键即停**（无残速）；
        3. **分轴独立**；4. **回头补一步只走 2 px**（`xprevious == x ∓ 3` 那条）。
        ★ 未附身 ⇒ 不驱动，返回 `(0, 0)`（**行为判据**：这条是 `check82` C 段的核心）。
        """
        if not self.is_possessing:
            self._last_drive = (0, 0)
            return (0.0, 0.0)
        dx, dy = self.direction()
        try:
            d = float(dt)
        except (TypeError, ValueError):
            d = 0.0
        if not math.isfinite(d) or d <= 0.0:
            d = 0.0
        d = min(d, MAX_DT)
        if dx == 0 and dy == 0:
            self._last_drive = (0, 0)
            return (0.0, 0.0)
        # 单帧满速位移（像素）—— 原作是"每帧固定 3 px"，按 dt 摊到秒。
        step = HERO_SPEED_PX * FRAME_HZ * d
        # ★ 回头判定（照抄 `obj_mainchara_Step_0`）：
        #   原作 `xprevious == (x + 3)` 表示"上一帧朝右整整走了 3 px"，
        #   现在改成朝左走 ⇒ 本帧只走 **2 px**（TURN_BACK_STEP），不是 3。
        #   ⇒ 本帧步长按 `TURN_BACK_STEP / HERO_SPEED_PX` 缩放。
        ldx, ldy = self._last_drive
        if dx != 0 and ldx == -dx:
            step *= TURN_BACK_STEP / HERO_SPEED_PX
        mx = dx * step
        my = dy * step
        self.x += mx
        self.y += my
        self._last_drive = (dx, dy)
        return (mx, my)

    def clamp_to(self, bounds):
        """把被附身角色钳进 `bounds = (l, t, r, b)`（逻辑坐标）。

        照 `soul_entity.SoulState.clamp_to` 的形状（钳左上角）。
        `bounds` 非法 ⇒ 原地 (x, y)，不抛。
        """
        if not bounds or len(bounds) != 4:
            return (self.x, self.y)
        try:
            l, t, r, b = [float(v) for v in bounds]
        except (TypeError, ValueError):
            return (self.x, self.y)
        self.x = min(max(self.x, l), max(l, r))
        self.y = min(max(self.y, t), max(t, b))
        return (self.x, self.y)

    def needs_tick(self):
        """是否需要按帧推进（决定调用方要不要在每帧调 `drive`）。"""
        return self.is_possessing and bool(self._pressed)

    def as_dict(self):
        return {'schema_version': SCHEMA_VERSION,
                'mode': self.mode,
                'possessed': self.possessed_id,
                'consent': self.consent.as_dict()}

    def load_dict(self, data):
        """只恢复"同意"这一层（附身本身是**会话内**状态，不跨会话续）。"""
        if not isinstance(data, dict):
            return False
        return self.consent.load_dict(data.get('consent'))


# ---------------------------------------------------------------- 纯函数

def _norm_dir(name):
    """键名 → `'left'/...'`；认不出 `None`。★ 与 `soul_entity.normalize_key` 同表。"""
    if not isinstance(name, str):
        return None
    return {
        'left': 'left', 'arrow_left': 'left', 'arrowleft': 'left',
        'right': 'right', 'arrow_right': 'right', 'arrowright': 'right',
        'up': 'up', 'arrow_up': 'up', 'arrowup': 'up',
        'down': 'down', 'arrow_down': 'down', 'arrowdown': 'down',
    }.get(name.strip().lower())


def _entry_get(entry, *keys):
    """从一条登记里取第一个非空字段 —— **dict 与对象都吃**（duck typing）。

    ★ 为什么必须两种都吃：本项目里"NPC 登记"有**两种活体形状**——
      ① `_registry.json` 的原始 dict（测试/脚本里常见）；
      ② 宿主 `npc_system.NpcRegistry` 里的 `NpcDef` **对象**（真机路径，
         `main.init_npc_systems()` 建的就是它）。
      只认 dict ⇒ 真机拿到空表（"函数写对了 ≠ 产品用上了"）。
      ⚠️ 本模块**零依赖** ⇒ 不许 `import npc_system`，只按属性名鸭子取。
    """
    for k in keys:
        if isinstance(entry, dict):
            v = entry.get(k)
        else:
            v = getattr(entry, k, None)
        if v:
            return v
    return None


def target_from_registry(npc_id, registry_entry, scene=None):
    """用 `_registry.json` 的一条登记 + 本项目附身表 → `PossessionTarget`。

    这样"谁可附身"只有 `POSSESSION_KINDS` 一处定义，而"他叫什么"来自登记表，
    两边不会分叉。`registry_entry` 非法 ⇒ name 回落 npc_id（**不抛**）。
    """
    name = _entry_get(registry_entry, 'name_cn', 'name') or npc_id
    return PossessionTarget(npc_id, name=name, kind=kind_of(npc_id), scene=scene)


def build_targets(registry, scene_of=None):
    """从登记表挑出**可附身**的目标列表。

    :param registry: `{'npcs': [...]}` / `[...]` / **任何带 `all()` 的注册表对象**
        （三形状都吃，`None` ⇒ `[]`）。★ 第三种是本项目真机路径：
        `npc_system.NpcRegistry` 只有 `.all()/.ids()/.get()`，**不是** list/dict。
    :param scene_of: 可选 callable `npc_id -> scene_id`（注入当前所在场景）。
    :return: `[PossessionTarget, ...]`（顺序稳定，按 npc_id 排序）。
    """
    if isinstance(registry, dict):
        npcs = registry.get('npcs')
    elif isinstance(registry, (list, tuple)):
        npcs = registry
    elif registry is not None and callable(getattr(registry, 'all', None)):
        try:
            npcs = registry.all()
        except Exception:
            npcs = None
    else:
        npcs = None
    if not isinstance(npcs, (list, tuple)):
        return []
    out = []
    for ent in npcs:
        nid = _entry_get(ent, 'id')
        if not is_possessable(nid):
            continue
        sc = None
        if callable(scene_of):
            try:
                sc = scene_of(nid)
            except Exception:
                sc = None
        out.append(target_from_registry(nid, ent, scene=sc))
    out.sort(key=lambda t: t.npc_id)
    return out


def describe_mode(mode):
    """状态码 → 中文（日志/台词用）。认不出原样返回。"""
    return {
        MODE_FREE: '未附身',
        MODE_ASKING: '征求同意中',
        MODE_POSSESSED: '附身中',
        MODE_REFUSED: '被拒/不可附身',
    }.get(mode, str(mode))

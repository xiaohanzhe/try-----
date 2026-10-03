# -*- coding: utf-8 -*-
"""带路（ESCORT）—— G 键请求某个角色**带着灵魂走**（第83轮 R6）。

用户口径（第76轮需求锁定，逐字）
--------------------------------
「**R6 可请求角色带灵魂走**」

★ 本轮两条用户裁定（2026-10-03，逐字）
-------------------------------------
* 「**新增 G 键**」  ⇒ G 专用于请求带路，**与 Z（R5 附身）完全分开**。
* 「**完全照原作（直接置位）**」 ⇒ 轨迹采样后**直接置位**，
  **不引入**"远处走过来"的中间态。瞬移这一点用户知情并明确选择。

★★★ 原作依据 / 以及"原作没有这条"的诚实标注（第46轮取证，物证见
     `code-quality-audit/第46轮-原作代码通读/_evidence/原作系统取证46.md`）
---------------------------------------------------------------------
**机制照抄原作**（毛毛虫 caterpillar，方向与原作相反）：

| 事实 | 出处（逐字） |
|---|---|
| 跟随 = 走目标走过的路（25 帧历史） | `obj_caterpillarchara` 有 `remx[] / remy[] / facing[]`，**长度各 25** |
| 滞后帧数 | `scr_makecaterpillar`：`global.cinstance[slot].target = 12 + (slot * 12);` |
| 跟随目标恒为带路者 | `obj_caterpillarchara.Create_0`：`parent = obj_mainchara;` |
| 采样点的下标记法 | `remx[0] = 主角当前 x` ⇒ 下标 = **年龄** ⇒ "N 帧前" = `remx[N]` |

**但这条需求本身原作没有**（不许冒充）：

* 原作里 `parent = obj_mainchara` —— **主角带路、队友跟随**（方向：主角 → 队友）。
  本项目 R6 是**角色带路、灵魂跟随**（方向：角色 → 灵魂）。
  ⇒ **方向与原作相反**，这是**本项目扩展**。
* 原作**根本没有"灵魂"这个可被带领的实体**：`obj_heart` 是战斗/弹幕里的红心，
  只在战斗界面出现，不是"跟着你走路的同伴"。
  本项目的"灵魂"（`soul_entity`）是**桌面实体**，可自由穿行场景
  （第76轮 R2/R3/R4 已落地）。
* 原作**没有"请求对方带你"这回事** ⇒ "征求同意"是本项目扩展，
  **复用 R5 的 `ConsentState`**（同一套三态，不另建）。

★ 一句话：**机制照抄毛毛虫的轨迹延迟采样，方向与原作相反，且"灵魂"是本项目实体。**

三条纪律（与 `possession` / `soul_entity` / `companion` 同源）
------------------------------------------------------------
1. 只允许模块顶部 `import logging / math`。**禁 import Qt、禁 import 任何项目内模块**
   （`main.py` 在 import 期就会拉起本模块；回头 import 项目内模块会接上初始化环）。
2. 内部函数**不许**再 import（回归锁 `check83` 用 AST 强制）。
3. 不认识的东西**返回 `None` / `False`，不猜、不就近凑**（同 `pick_nearest` 纪律）。

★ 与 R5 的关系：**互斥**（都涉及"控制权/主体位置"的重新分配）
-----------------------------------------------------------
* 附身中 ⇒ **不许**发起带路（`request` 拒绝）；
* 带路中 ⇒ 附身入口**先解除带路**（`main` 侧裁决，见接线注释）。
理由：两个状态机若同时"自认为在管主体移动"，会出现**同一帧两处写坐标**
（本项目"同一份规则两处算"是最贵的坑）。
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
      「零依赖 / 白名单」契约。
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

#: ★ 轨迹环缓冲长度 —— 照抄 `obj_caterpillarchara` 的 `remx[25] / remy[25] / facing[25]`。
TRACE_LEN = 25

#: ★ 滞后基准帧数 —— 照抄 `scr_makecaterpillar` 的 `target = 12 + (slot * 12)`。
#: ⚠️ R6 里"灵魂"没有"队友位"概念（它不是队伍成员）⇒ 取 `slot = 0` 的那一档 = 12。
#:    这是**同一张原作表**的第一个槽位，不是我另拍的数。
FOLLOW_LAG = 12

#: ★ 原作帧率（第43轮实证 `GMS2FPS = 30`）。
FRAME_HZ = 30


# ---------------------------------------------------------------- 状态码

#: 没在带路。
ESCORT_NONE = 'none'
#: 已请求，等对方同意（只对需要同意的角色）。
ESCORT_ASKING = 'asking'
#: 正在带路（灵魂跟着带路者）。
ESCORT_LEADING = 'leading'
#: 请求被拒 / 不可带路。
ESCORT_REFUSED = 'refused'


def _norm_id(v):
    """把 npc_id 归一成**小写去空白**的字符串；非法 ⇒ `None`（不猜）。

    ★ 与 `companion.normalize_id` 的**同一条口径**（去首尾空白 + 转小写），
      但**不**做"内部空白折叠"—— 因为这里只需要"能不能对上号"，
      多一步变换就多一处可能分叉的地方。
    """
    if not isinstance(v, str):
        return None
    s = v.replace('\u3000', ' ').strip().lower()
    return s or None


class EscortState(object):
    """带路状态机（无 Qt、无 IO，可离线单测）。

    它管的是**"灵魂被谁带着"**，与 `PossessionState`（管"方向键归谁"）
    **正交但互斥**：

    * `PossessionState`：用户直接推着角色走（方向键 ⇒ 角色）；
    * `EscortState`    ：角色带路，灵魂跟着角色的轨迹走（方向键 ⇒ 仍是灵魂）。

    :param leader_id:  带路者 npc_id（**必须显式**；`None` 时不成立）
    :param follower_id: 被带者身份，默认 `'soul'`（本项目灵魂的固定身份）
    :param lag:        滞后帧数（缺省用原作 12；显式传入便于测试与可调）
    """

    __slots__ = ('leader_id', 'follower_id', 'lag', 'mode', 'reason',
                 '_trace', '_pressed', 'consent', 'leader_x', 'leader_y',
                 'follower_x', 'follower_y')

    def __init__(self, leader_id=None, follower_id='soul', lag=None,
                 consent=None):
        self.leader_id = _norm_id(leader_id)
        self.follower_id = _norm_id(follower_id) or 'soul'
        self.lag = int(lag) if isinstance(lag, int) and lag > 0 else FOLLOW_LAG
        self.mode = ESCORT_NONE
        self.reason = ''
        #: 带路者的轨迹环缓冲（对应原作 `remx/remy/facing` 三个平行数组里的前两个）。
        self._trace = []
        #: 灵魂当前是否"被牵着"（G 键的开关态；与 mode 分开是因为
        #: 同意流程里 mode 已经是 ASKING 了，但还没开始带）。
        self._pressed = False
        #: ★ 复用 R5 的同意机制形状（三态）—— 本模块**零依赖** ⇒ 只按接口鸭子用，
        #:   不 import `possession`。传 `None` ⇒ 自建一个等价的最小实现。
        self.consent = consent if consent is not None else _MiniConsent()
        self.leader_x = 0.0
        self.leader_y = 0.0
        self.follower_x = 0.0
        self.follower_y = 0.0

    # ------------------------------------------------------------ 只读
    @property
    def is_leading(self):
        return self.mode == ESCORT_LEADING

    @property
    def is_asking(self):
        return self.mode == ESCORT_ASKING

    @property
    def active(self):
        """是否处于"带路相关"的任一活动态（ASKING 或 LEADING）。"""
        return self.mode in (ESCORT_ASKING, ESCORT_LEADING)

    def describe(self):
        return '带路[%s] 带路者=%s 被带者=%s %s' % (
            self.mode, self.leader_id or '无', self.follower_id, self.reason)

    # ------------------------------------------------------------ 轨迹
    def push_trace(self, x, y):
        """把带路者的当前位置压进历史（每帧一次）。

        照抄 `obj_caterpillarchara` 的 `remx[0] = obj_mainchara.x` 那一行。
        """
        try:
            self.leader_x = float(x)
            self.leader_y = float(y)
        except (TypeError, ValueError):
            return False
        if not (math.isfinite(self.leader_x) and math.isfinite(self.leader_y)):
            return False
        self._trace.append((self.leader_x, self.leader_y))
        if len(self._trace) > TRACE_LEN:
            del self._trace[0:len(self._trace) - TRACE_LEN]
        return True

    def reset_trace(self, x, y):
        """把历史**填满**成同一个点 —— 照抄原作 `remx[i]` 的初值
        「= 主角当前位置」。

        ★ 为什么必须填满而不是清空：清空的话 `sample_at(lag)` 在头 `lag` 帧
        返回 `None` ⇒ 灵魂会从 `(0, 0)` 一路被"拽"过来（可见的穿屏）。
        填满 ⇒ 刚开始的带路者就出现在"自己身后 12 帧"的位置，与原作一致。
        """
        try:
            x = float(x)
            y = float(y)
        except (TypeError, ValueError):
            return False
        if not (math.isfinite(x) and math.isfinite(y)):
            return False
        self._trace = [(x, y)] * TRACE_LEN
        self.leader_x, self.leader_y = x, y
        self.follower_x, self.follower_y = x, y
        return True

    def sample_at(self, lag):
        """取「**lag 帧前**」那一个采样点。历史不够长 ⇒ `None`（**不猜**）。

        ★ 下标为什么是 `-(lag+1)`：`trace[-1]` 是**刚压进去的当前帧**
        （对应原作 `remx[0]` = 当前，下标 = **年龄**），所以"12 帧前" = `remx[12]`
        = `trace[-13]`。差一格不会有人肉眼发现，但会让"照抄原作 12 帧"这句
        **声明变成假话** ⇒ 必须是可断言的正确值（与 `companion.sample_at` 同条文）。
        """
        lag = int(lag)
        if lag < 1 or len(self._trace) < lag + 1:
            return None
        return self._trace[-(lag + 1)]

    # ------------------------------------------------------------ 请求
    def request(self, leader_id, kind=None, scene=None, leader_scene=None):
        """请求 `leader_id` 带路。返回**状态码**（`ESCORT_*`），不抛。

        判定序（**顺序即优先级**，与 `_clean_ai_reply` 同一纪律）：
          1. `leader_id` 非法 ⇒ 原状态不变，返回 `ESCORT_REFUSED`；
          2. 已在带路/征求中 ⇒ 先 `stop()` 再走新一轮（避免"叠着带"）；
          3. `kind` 为 `'forbidden'` ⇒ 拒绝（不可带路者）；
          4. 不同场景（两侧都非 None）⇒ 拒绝（**带路要求同场景**）；
          5. `kind == 'consent'` 且同意过 ⇒ `LEADING`；同意过为 False ⇒ 拒绝；
             未问过 ⇒ `ASKING`；
          6. 其余（`kind` 为 `'direct'` 或 `None`）⇒ `LEADING`。

        ★ `kind is None` 视为 direct 的理由：本模块**零依赖**不许 import
          `possession`，所以调用方传不传 kind 都得能跑；传 `None` = "调用方
          没分类" ⇒ 按最宽松处理，但**调用方有义务传**（`main` 侧从 R5 的
          `POSSESSION_KINDS` 取，见接线注释）——单一真源在 `possession`。
        """
        lid = _norm_id(leader_id)
        if lid is None:
            self.reason = '非法带路者（%r）' % (leader_id,)
            return ESCORT_REFUSED
        if self.active:
            self.stop('被新的带路请求取代')

        if kind == 'forbidden':
            self.reason = '不可带路：%s' % lid
            return ESCORT_REFUSED

        # 同场景校验（任一侧为 None 则不校验 —— 不拿未知当"不同"）
        if (scene is not None and leader_scene is not None
                and scene != leader_scene):
            self.reason = '不同场景（灵魂=%s 带路者=%s）' % (scene, leader_scene)
            return ESCORT_REFUSED

        self.leader_id = lid
        if kind == 'consent':
            st = self.consent.get(lid)
            if st is True:
                return self._begin('已获同意后带路（%s）' % lid)
            if st is False:
                self.reason = '%s 拒绝过（可再次请求）' % lid
                return ESCORT_REFUSED
            self.mode = ESCORT_ASKING
            self.reason = '征求 %s 的同意…' % lid
            _log.info('带路：向 %s 征求意见', lid)
            return ESCORT_ASKING
        return self._begin('直接带路（%s：可直接请求）' % lid)

    def grant(self):
        """被请求的人同意了 ⇒ 从 `ESCORT_ASKING` 进入带路。返回状态码。"""
        if self.mode != ESCORT_ASKING or self.leader_id is None:
            self.reason = '没有在征求同意（当前 %s）' % self.mode
            return self.mode
        self.consent.grant(self.leader_id)
        return self._begin('%s 同意了' % self.leader_id)

    def refuse(self):
        """被请求的人拒绝了 ⇒ 回 `ESCORT_REFUSED`（记下拒绝态）。返回状态码。"""
        if self.mode != ESCORT_ASKING or self.leader_id is None:
            return self.mode
        self.consent.refuse(self.leader_id)
        lid = self.leader_id
        self.mode = ESCORT_REFUSED
        self.reason = '%s 不同意' % lid
        _log.info('带路：%s 拒绝了', lid)
        return ESCORT_REFUSED

    def _begin(self, why):
        self.mode = ESCORT_LEADING
        self.reason = why
        self._pressed = True
        _log.info('带路开始：%s（%s）', self.leader_id, why)
        return ESCORT_LEADING

    def stop(self, why='用户解除'):
        """结束带路（再按 G / 失焦 / 附身接管）。**幂等**。"""
        if self.mode != ESCORT_NONE and self.leader_id is not None:
            _log.info('带路结束：%s（%s）', self.leader_id, why)
        self.mode = ESCORT_NONE
        self._pressed = False
        self.reason = why
        self.leader_id = None
        self._trace = []
        return ESCORT_NONE

    # ------------------------------------------------------------ 推进
    def step(self, x=None, y=None):
        """每帧推进带路。返回灵魂**本帧的新位置** `(x, y)`；不成立 ⇒ `None`。

        ★ 用户裁定「完全照原作（直接置位）」⇒ 这里就是**直接置位**：
          灵魂位置 = 带路者轨迹里「滞后 `lag` 帧」那一点。
          与原作 `obj_caterpillarchara` 的 `c.x, c.y = pt.x, pt.y` **完全同形**。

        :param x: 带路者**本帧**位置（给了就压进轨迹；不给则只读，用于测试与
                  "只在位置变化时压轨迹"的调用方）。
        :return: `(nx, ny)` 新位置；`sample_at` 拿不到点 ⇒ `None`（**不猜**）。
        """
        if self.mode != ESCORT_LEADING:
            return None
        if x is not None and y is not None:
            self.push_trace(x, y)
        pt = self.sample_at(self.lag)
        if pt is None:
            return None
        self.follower_x, self.follower_y = pt
        return pt

    def needs_step(self):
        """是否需要按帧推进（决定调用方要不要在每帧调 `step`）。"""
        return self.mode == ESCORT_LEADING

    def distance(self):
        """带路者与灵魂的当前距离（诊断/report 用；**不参与判据**）。

        ⚠️ 它存在的**唯一**理由是日志和报告可读性 —— 不许拿它当行为判据，
           否则就变成"用派生量断行为"（判据侧的事故高发区）。
        """
        return math.hypot(self.leader_x - self.follower_x,
                          self.leader_y - self.follower_y)

    def as_dict(self):
        return {'schema_version': SCHEMA_VERSION,
                'mode': self.mode,
                'leader': self.leader_id,
                'follower': self.follower_id,
                'lag': self.lag,
                'consent': self.consent.as_dict()}

    def load_dict(self, data):
        """只恢复"同意"这一层（带路本身是**会话内**状态，不跨会话续）。"""
        if not isinstance(data, dict):
            return False
        return self.consent.load_dict(data.get('consent'))


# ---------------------------------------------------------------- 兜底同意表

class _MiniConsent(object):
    """`ConsentState` 的最小等价实现（**只在本模块被单独使用时兜底**）。

    ★ 为什么本模块自带一份而不是 import `possession.ConsentState`：
      本模块是**零依赖**层（顶层 import ⊆ {logging, math}），
      `import possession` 会破坏这条闸（回归锁 `check83` 会 AST 断言）。
    ★ 为什么这不构成"同一份规则两处算"：
      `main` 侧接线时**显式把 R5 的 `ConsentState` 注入**（`consent=` 参数），
      于是产品路径上只有**一份**同意表；这份兜底只在**离线单测/独立使用**时生效。
      两者语义必须一致 ⇒ `check83` 用**等价性判据**锚住（同一组操作，两边状态逐值相等）。
    """

    __slots__ = ('_by_id',)

    def __init__(self):
        self._by_id = {}

    def get(self, npc_id):
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


# ---------------------------------------------------------------- 纯函数

def describe_mode(mode):
    """状态码 → 中文（日志/台词用）。认不出原样返回。"""
    return {
        ESCORT_NONE: '未带路',
        ESCORT_ASKING: '征求同意中',
        ESCORT_LEADING: '带路中',
        ESCORT_REFUSED: '被拒/不可带路',
    }.get(mode, str(mode))

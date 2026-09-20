# -*- coding: utf-8 -*-
"""
施法流程控制器 —— H4/H5「上帝类拆分」Wave 1 第 3 项（W1-1）。

搬出来的是什么
--------------
`RalseiPet` 里「施法（spell）流程」这一条业务线的 **4 个方法 / 290 行**：

    _spell_interrupted_reason  (26)  —— 每帧问一次：当前施法该不该中断？返回原因或 None
    _tick_spell_flow          (183)  —— 每帧推进 walking/casting 状态机（含中断清理 + 兜底）
    _cast_spell_then           (44)  —— 纯施法：不走 walking，直接播 spell / spell_left
    _start_open_with_spell     (37)  —— 走去目标 → 施法 11 帧 → 回调真开文件

⚠️ 分组器会把 W1-1 报成「2 个方法 / 63 行」，**那是错的**。
`scan_method_index.py` 用**名字前缀**分组（`name.startswith('_spell')` 或
`name == '_start_open_with_spell'`），于是：

  · `_tick_spell_flow`    —— 前缀是 `_tick` → 落不进 W1-1
  · `_cast_spell_then`    —— 前缀是 `_cast` → 落不进 W1-1

而排期方案 §5.2 对 W1-1 的口径本来就是 **4 个方法 / 290 行**
（方案原文：「`_spell_interrupted_reason` / `_tick_spell_flow`(183) /
`_cast_spell_then` / `_start_open_with_spell` → 4 个方法 / 290 行，9 个 `_spell_*` 属性」）。
→ **开工前重扫方法索引是对的，但索引的分组列只能当"下限"，不能当"清单"**；
  对不上排期方案时必须回去读方案，而不是照抄索引。这是 W1-4 也踩过的同一个分组器缺陷
（W1-4 报告里的"分组器漏标了中间 3 个 `_*video*` 私有方法"）。

为什么是这一块（Wave 1 顺序 W1-3 → W1-4 → W1-1 → W1-2 → W1-6）
--------------------------------------------------------------
它是 Wave 1 里**第一块与另一项（W1-2 躲猫猫）有真实互写**的：
G3 属性归属表点出 4 条互写 —— `_hide_stage` / `_hide_obstacles` / `_hide_folder_path`
（归 W1-2）与 `_spell_auto_suspended`（归 W1-1）。方案给的处置是
「二者合并，或改走 `pyqtSignal`（不得直连）」。

本项**靠"状态全部留在宿主"把这条耦合消掉**：4 个属性一个都不搬，
控制器里 `self._hide_stage` 经 `__getattr__` 读到的是**宿主那一份**，
`self._spell_auto_suspended = True` 经 `__setattr__` 写回**宿主那一份** ——
于是 W1-1 与 W1-2 之间**没有任何直接引用**，两个控制器互不认识。
等 W1-2 也搬完，这 4 条互写自然退化成"两个控制器各自与宿主打交道"，无需 signal。

与本轮口径的一致性
------------------
* 施工口径：**只搬方法、不搬状态**。施法状态全部留在 `RalseiPet.__init__`：
  `_spell_stage` / `_spell_target_direction` / `_spell_target_path` /
  `_spell_target_kind` / `_spell_target_screen_pos` / `_spell_finish_cb` /
  `_spell_frames_seen` / `_spell_cast_start_frame` / `_spell_touched_flag` /
  `_spell_auto_suspended`（`main.py` L744–753 已声明）。
* **本轮补声明了 2 个**（见下面 ⚠️⚠️，铁律 3）：

  · `_spell_seen_frame`       —— 帧去重标记
  · `_spell_cast_start_time`  —— casting 起始时刻（5s 时间兜底用）

* **`_tick_spell_flow` 没搬**：❌ 说错了 —— 它**搬了**。这里要澄清的是
  `update_animation`（W3-1）末尾的 `self._tick_spell_flow()` 调用点：
  **调用点留在宿主**（`main.py` L8336），走 `__getattr__` 命中转发壳。
  施法流程是**每帧驱动**的，所以这条转发路径是热路径 —— 但 `__getattr__`
  只在**常规查找 miss** 时才进，`RalseiPet` 类上已无 `_tick_spell_flow` 定义，
  所以每帧都会走一次转发。代价是一次 `getattr(type(ctrl), name)` +
  `getattr(ctrl, name)`（两个字典查找），相对本函数 183 行的体量可忽略。
* **`_resolve_target_screen_anchor` 没搬**：它是「目标屏幕锚点」的**通用原语**，
  `open_file` / `open_folder` / 躲猫猫三处都在用（`main.py` L9418 / L9614 / L9771），
  不属于施法专有 → 留在宿主，本模块经 `__getattr__` 借调。

为什么不 import 任何项目内模块
----------------------------
同 `event_speech.py` / `games_controller.py` / `video_controller.py` / `lazy_log.py`
的纪律：本模块位于「初始化环」下游（`main.py` import 期就要
`from modules.spell_controller import SpellFlowController`），回头 import
`logger_utils` / `dialogue_ui` 会把环重新接上。

本模块的模块级 import
---------------------
  · `os`     —— `_tick_spell_flow` 里有 **裸用** `os.path.isdir(p)`（L9219）⚠️
  · `time`   —— `_tick_spell_flow` 的 `now = time.time()`（L9235）、
                `_cast_spell_then` 的 `time.time()`（L9399）都是**裸用** ⚠️
  · `PyQt5.QtCore.QPoint` —— `_tick_spell_flow` L9277
                `target = QPoint(int(tx - self.width() / 2), ...)` 是**裸用** ⚠️
  · `logging` —— 见 `_log_()`。

⚠️ 这三个名字是**本轮最容易埋的雷**：被搬的方法体里它们统统是裸名，
在 `main.py` 靠**模块级** `import os` / `import time` / `from PyQt5.QtCore import ... QPoint ...`
解析（`main.py` L3 / L4 / L18）。搬走后模块作用域变了 → `NameError`。
**而逐字等价断言 100% 测不出来**（源码一个字没改，只是换了模块）。
这是 W1-4 踩过的坑 1（`QRect` / `QTimer`）的同型复发 —— 见 W1-4 报告第五节铁律 1。

`shutil` 不走模块级
------------------
`_tick_spell_flow` 里那处 `import shutil` 是**方法体内的局部导入**（L9216），
逐字搬运后依然是局部导入 → 不需要（也不应该）提到模块级。
**判断方式别靠眼睛**：用 AST 取 `Name` 节点的 `Load` 上下文去比对
`main.py` 的模块级绑定集合（本轮的 `_tmp/names.py` 就是干这个的）。

`_log` 去哪儿了
--------------
被搬的 4 个方法里共 **11 处** `_log.debug(...)`：
`_tick_spell_flow` 8 处 / `_cast_spell_then` 2 处 / `_start_open_with_spell` 1 处。
施工时**机械改写**为 `_log_().debug(...)`（只动 `_log.` → `_log_().`，共 11 次，
脚本内带命中断言），并由下面 `_log_()` 把**宿主 main.py 的同一个 logger 对象**取过来。

理由与 W1-4 完全相同：自己 `logging.getLogger(...)` 会**换 logger 名** →
文件落点/级别/格式都可能变，「行为等价」就不成立。取宿主 logger 则逐字节同一条日志。
`_log` 是 `main.py` 的**模块级全局**，既不在宿主实例字典、也不在宿主类型 MRO 上，
两条回落白名单都不满足 → 只能显式 `_log_()` 普通方法（类体赋值无 self、
`@property` 会挡住模块级 `_log`，都不行）。
"""

import logging
import os
import time

# ⚠️ 必须与 main.py 同款导入：被搬方法体里 `QPoint`（_tick_spell_flow L9277）
# 是**裸用**，在 main.py 靠模块级这份导入解析。漏了它 → NameError，
# 且**静态逐字等价断言测不出来**（源码没改，只是换了模块作用域）。
# 同 W1-4 的 `QRect` / `QTimer`（那次是 e2e 才炸出来的）。
from PyQt5.QtCore import QPoint

_log = logging.getLogger(__name__)


class SpellFlowController(object):
    """施法流程。宿主（`RalseiPet`）持有，方法通过宿主 `__getattr__` 转发壳暴露。

    与 `GamesController` / `VideoController` 同构：本类**需要 `__getattr__`**，
    因为「只搬方法不搬状态」意味着方法体里 `self._spell_stage` / `self.change_animation`
    / `self._abort_hide_and_seek` 这些宿主成员一个字都没改。两种做法：
    (a) 全改写成 `self.p.xxx`（本项要改 100+ 处）；(b) 回落给宿主（本实现，
    方法体逐字不变、等价性可硬证明）。选 (b)。

    与宿主 `RalseiPet.__getattr__` 的**方向正好相反**（宿主 → 控制器找方法，
    控制器 → 宿主找状态），两侧都是显式白名单，构成闭合双向转发 —— 详见
    `games_controller.py` 的类 docstring 与 `main.py` 的 `_CONTROLLER_ATTRS` 注释。
    真机踩过的 `RecursionError`（构造期崩）也记在那里，勿回退。

    ⚠️ 本项特有的转发目标：`_tick_spell_flow` 会调 **`self._abort_hide_and_seek(...)`**
    （属 W1-2，仍留在宿主）—— 这**不是**互写，是正常的宿主 API 借调：
    控制器只**调用**它（`getattr` 命中宿主类型 MRO），不碰它的属性。
    等 W1-2 把 `_abort_hide_and_seek` 搬进 `HideAndSeekController` 后，
    这条调用会自动命中**宿主的那层转发壳**再转给 W1-2 —— 本模块一个字都不用改。
    （这正是"集中转发"的自愈能力，见 `main.py` L469–472 的注释。）
    """

    def __init__(self, ralsei_pet):
        # 宿主引用：施法状态全在宿主身上，本类只借用，不复制、不缓存。
        # 普通赋值 → `p` 进实例字典 → `self.p` 走常规查找，不会递归回 __getattr__。
        self.p = ralsei_pet

    def __getattr__(self, name):
        # 只在常规查找失败时进入。两条**显式白名单**后才回落：
        #   · 宿主实例字典（_spell_stage / _hide_stage / dialogue_ui / sprite_loader…）
        #   · 宿主**类型** MRO 上的东西（change_animation / frameGeometry /
        #     _abort_hide_and_seek / _resolve_target_screen_anchor / QMainWindow 的
        #     width/height …）
        # 两条都不满足 → 抛，切断「宿主也没有 → 宿主 __getattr__ → 又转回本类」的成环路径。
        pet = self.__dict__.get('p')
        if pet is None:
            raise AttributeError(name)
        if name in pet.__dict__:
            return pet.__dict__[name]
        if any(name in klass.__dict__ for klass in type(pet).__mro__):
            return getattr(pet, name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        # ⚠️ 这是「逐字等价测不出来」的第二个坑（e2e 才炸出来）。
        #
        # 「只搬方法不搬状态」的口径要求状态留在宿主。`__getattr__` 只解决**读**：
        # 控制器里 `self._spell_stage` 读时回落给宿主。
        # 但**写**不会自动回落 —— Python 的普通赋值走 `__setattr__` → 默认
        # `object.__setattr__` → 直接把属性写进**控制器自己的 `__dict__`**。
        # 实测（W1-4 真踩）：控制器 `self.is_watching_video = True` 之后
        #   host.is_watching_video == False   /   ctrl.is_watching_video == True
        # → 状态被劈成两份，**两边读数不一致**，行为静默错乱。
        #
        # 本项的具体后果（若不修）：`_tick_spell_flow` 里 `self._spell_stage = 'casting'`
        # 落进控制器，而 `update_movement` / `change_animation` / `start_jump`
        # 等**宿主**方法读 `getattr(self, '_spell_stage', None)` 永远读到 False
        # → 「施法期间禁止移动/禁止切动画」这一整组护栏全部失效
        # （宠物会边施法边走、动画被顶掉）→ 施法流程表现成随机抽搐。
        #
        # 修法：把**业务属性**的赋值显式转发给宿主，只把控制器自身的私有成员
        # （`p` 宿主引用）留在自己身上。
        #
        # 转发判据 = 宿主**已经拥有**的名字（实例字典或 MRO 上有）。这个判据的关键是
        # **能自动覆盖新状态名**：以后 `RalseiPet` 再加 `_spell_xxx` 字段，只要它在
        # `__init__` 里赋了值，写进来就会自动落到宿主 —— 不需要来改这份名单
        # （这是本项目最贵的坑：'函数写对了但产品用不上'）。
        # 反过来说：控制器**故意不允许**给自己新增业务属性 —— 想加状态就加到宿主上。
        if name != 'p':
            pet = self.__dict__.get('p')
            if pet is not None:
                if name in pet.__dict__ or any(
                        name in klass.__dict__ for klass in type(pet).__mro__):
                    setattr(pet, name, value)
                    return
        object.__setattr__(self, name, value)

    def _log_(self):
        # 取宿主 main.py 的模块级 `_log`（同一个 logger 对象）—— 见模块 docstring。
        # `_log` 不在宿主实例字典里，所以走宿主**模块**的全局变量。
        import sys
        mod = sys.modules.get(type(self.p).__module__)
        if mod is not None:
            lg = getattr(mod, '_log', None)
            if lg is not None:
                return lg
        return _log

    # ------------------------------------------------------------------
    # 施法业务（W1-1 搬运区，**以下方法体逐字来自 main.py**，
    # 唯一改动：`_log.` → `_log_().`，共 11 处，逐方法计数见施工报告）
    # ------------------------------------------------------------------

    def _spell_interrupted_reason(self):
        """检查当前施法流程是否应该中断。返回 str 原因或 None 表示未中断。"""
        if self._spell_stage is None:
            return None
        # 拖拽：立即中断
        if getattr(self, '_is_being_dragged', False):
            return 'drag_started'
        # 用户触摸 / 鼠标按下
        if getattr(self, '_spell_touched_flag', False):
            return 'user_touched'
        # 跳跃 / 掉落：物理过程覆盖所有动画
        if getattr(self, 'is_jumping', False) or getattr(self, 'is_falling', False):
            return 'physics_started'
        # casting 阶段：动画必须是 spell / spell_left，否则视为被打断
        if self._spell_stage == 'casting' and self._spell_target_direction:
            expected_anim = 'spell_left' if self._spell_target_direction == 'left' else 'spell'
            if self.current_animation != expected_anim:
                # 修复：动画被切走（被 walk/idle/其他动画覆盖）即中断，不再看方向。
                # 原逻辑在"动画不对但方向匹配"时既不中断也不修复，
                # 导致 frames_seen 永不增长、施法流程永久卡死（文件夹永不打开）。
                return 'anim_mismatch'
            if self.current_direction != self._spell_target_direction:
                # 动画正确但方向字段不一致：同步方向，不做中断判定
                self.previous_direction = self.current_direction
                self.current_direction = self._spell_target_direction
        return None

    def _tick_spell_flow(self):
        """每帧执行：推进 spell 流程 walking/casting 状态机。
        只有 _spell_stage != None 时才真正干活。"""
        if self._spell_stage is None:
            return

        # 1. 统一打断检测
        r = self._spell_interrupted_reason()
        if r is not None:
            # ===== 修复：单个 spell 中断 不直接 abort 整个躲猫猫游戏 =====
            # 躲猫猫的 _abort_hide_and_seek 只在：game 主动结束（end_hide_and_seek）/ 超时 / 玩家点退出 时调用
            # 这里只清理 spell 状态，让上层决定是否继续推进游戏或重试
            self._log_().debug(f"[SPELL] 流程中断 reason={r} stage={self._spell_stage}，仅清理 spell 状态")
            # walking/casting 都清理 spell 状态
            self._spell_stage = None
            self._spell_target_direction = None
            self._spell_finish_cb = None
            self._spell_target_path = None
            self._spell_target_kind = None
            self._spell_target_screen_pos = None
            self._spell_cast_start_frame = None
            self._spell_frames_seen = 0
            self._spell_seen_frame = -1
            self._spell_touched_flag = False
            # ===== 修复：躲猫猫进行中的 spell 被打断 → 兜底结束游戏，避免永久卡死 =====
            # 原逻辑只清 spell 状态，_hide_stage 卡在中间阶段：无法重开、超时定时器未启动、
            # _abort_hide_and_seek 全项目仅一处调用 → 游戏永远结束不了。这里统一兜底。
            hs = getattr(self, '_hide_stage', None)
            if hs is not None:
                self._log_().debug(f"[SPELL] 躲猫猫阶段 {hs} 的施法被打断，兜底结束躲猫猫")
                self._abort_hide_and_seek(reason='spell_interrupted')
            else:
                # 躲猫猫销毁阶段（_hide_end_game 已清 _hide_stage，但障碍物还没删）被打断 →
                # 清理残留障碍物，避免桌面上永久残留"障碍物N"文件夹
                obstacles = getattr(self, '_hide_obstacles', []) or []
                if obstacles:
                    self._log_().debug("[SPELL] 躲猫猫销毁施法被打断，清理残留障碍物")
                    import shutil
                    for p in obstacles:
                        try:
                            if os.path.isdir(p):
                                shutil.rmtree(p, ignore_errors=True)
                        except Exception as e:  # 修复：原先静默吞噬
                            self._log_().debug("main 防御性异常（已忽略）: %s", e)
                    self._hide_obstacles = []
                    self._hide_folder_path = None
                # 恢复自主代理（非躲猫猫 spell 被打断时，之前 suspend 的 agent 必须恢复，
                # 否则自主代理永久挂起）
                if getattr(self, '_spell_auto_suspended', False):
                    try:
                        self.autonomous_agent.resume()
                    except Exception as e:  # 修复：原先静默吞噬
                        self._log_().debug("main 防御性异常（已忽略）: %s", e)
                    self._spell_auto_suspended = False
            return

        now = time.time()

        # 2. walking 阶段：向目标点移动（dist<35 → 转 casting）
        if self._spell_stage == 'walking':
            me = self.frameGeometry().center()
            tx, ty = self._spell_target_screen_pos
            dx = tx - me.x()
            dy = ty - me.y()
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < 35:
                # —— 足够近：立刻切换到 casting 阶段 ——
                direction = self._spell_target_direction
                if direction is None:
                    direction = 'right' if (self.current_direction != 'left') else 'left'
                spell_anim = 'spell_left' if direction == 'left' else 'spell'
                self._spell_stage = 'casting'
                # 修复：进入施法时必须停稳——否则 is_moving 残留 True 时
                # update_movement 继续驱动移动，施法过程中漂移/抖动（抽搐感）。
                self.is_moving = False
                self.current_speed_x = 0
                self.current_speed_y = 0
                # 施法音效
                try:
                    self.sound_manager.play_spell()
                except Exception as e:  # 修复：原先静默吞噬
                    self._log_().debug("main 防御性异常（已忽略）: %s", e)
                self._spell_target_direction = direction
                self.previous_direction = self.current_direction
                self.current_direction = direction
                if self.change_animation(spell_anim, force=True):
                    self.current_frame = 0
                self._spell_cast_start_frame = 0
                self._spell_frames_seen = 0
                self._spell_seen_frame = -1  # 修复：重置帧去重标记，避免残留值吞掉首帧计数
                # 暂停自主代理（避免它的 look_up / act 覆盖 spell 动画；躲猫猫结束后恢复）
                try:
                    self.autonomous_agent.suspend()
                    self._spell_auto_suspended = True
                except Exception as e:  # 修复：原先静默吞噬
                    self._log_().debug("main 防御性异常（已忽略）: %s", e)
            else:
                # 每帧向目标移动一小步：用主移动系统，确保走的是 walk 动画
                target = QPoint(int(tx - self.width() / 2), int(ty - self.height() / 2))
                if getattr(self, 'target_pos', None) != target:
                    self.target_pos = target
                    self.is_moving = True
                    self.speed = 6.0
                    # 按方向切 walk_<dir>
                    if abs(dx) > abs(dy):
                        new_dir = 'right' if dx > 0 else 'left'
                    else:
                        new_dir = 'down' if dy > 0 else 'up'
                    # 修复：只在方向确实变化时才 force 切换动画（避免每帧强制切换造成抽搐）。
                    # force=True 保证冷却期内也能切到目标方向（非 force 时会被冷却拒绝）。
                    if self.current_direction != new_dir:
                        self.current_direction = new_dir
                        self.change_animation(f"walk_{new_dir}", force=True)

        # 3. casting 阶段：数 spell/spell_left 帧直到 11 帧播完 → cb
        elif self._spell_stage == 'casting':
            expected = 11
            anim = self.current_animation
            frames = self.sprite_loader.sprites.get(anim, [])
            if not frames:
                # H5 S1：casting 阶段靠数帧推进，frames 为空会让本阶段永不结束
                # （与之前 P0 的 current_time NameError 是同一后果）。记账以便定位来源。
                self.sprite_loader.note_animation_miss(anim, None, '_tick_spell_flow')
            cur_f = self.current_frame
            # 记录 casting 开始时间（用于时间超时 fallback）
            # 修复（P0）：此处原写 current_time —— 该方法内并无此局部变量，模块级
            # 也没有同名全局，运行到 casting 阶段必抛 NameError，被本帧 tick 的
            # try/except 吞掉后 _spell_stage 永远停在 'casting'：施法回调不触发
            # （文件永远打不开、躲猫猫障碍物永不生成），且 pet_ai.trigger_action
            # 见到 _spell_stage 非空即直接 return → 宠物进入无法自恢复的僵直，
            # 日志每 100ms 刷一次堆栈。统一改用本函数第 8054 行已定义的 now。
            if not hasattr(self, '_spell_cast_start_time') or self._spell_cast_start_time is None:
                self._spell_cast_start_time = now
            if (anim in ('spell', 'spell_left')) and len(frames) >= 2:
                # 看到了真实帧：累积 _spell_frames_seen（同一帧重复见不算）
                if getattr(self, '_spell_seen_frame', -1) != cur_f:
                    self._spell_frames_seen = getattr(self, '_spell_frames_seen', 0) + 1
                    self._spell_seen_frame = cur_f
            # 心跳 log 4 次（防止完全不可见）
            frames_seen = getattr(self, '_spell_frames_seen', 0)
            cond_ideal = (frames_seen >= expected) and (anim in ('spell', 'spell_left')) and (len(frames) >= 2)
            # 修复：此前 timeout fallback 仅依赖 frames_seen>=22，若 spell 动画帧数<2
            # （frames_seen 永远为 0）则永久卡住。新增：帧数不足直接完成 + 5秒时间超时。
            cond_frames_insufficient = (anim in ('spell', 'spell_left')) and (len(frames) < 2)
            cond_time_fallback = (now - getattr(self, '_spell_cast_start_time', now)) > 5.0
            cond_timeout_fallback = (not cond_ideal) and (frames_seen >= expected * 2 or cond_time_fallback)
            if cond_ideal or cond_timeout_fallback:
                cb = self._spell_finish_cb
                path = self._spell_target_path
                kind = self._spell_target_kind
                # —— 关键！保存回调前的动画名，避免回调里启动新 spell 时，
                #    后面 finally 把新 spell_left 当作旧 spell 清理掉切 idle。
                _anim_before_cb = self.current_animation
                # 先清理 spell 状态，再回调（避免回调认为"仍在施法"）
                self._spell_stage = None
                self._spell_target_kind = None
                self._spell_target_path = None
                self._spell_target_screen_pos = None
                self._spell_target_direction = None
                self._spell_cast_start_frame = None
                self._spell_cast_start_time = None
                self._spell_finish_cb = None
                self._spell_touched_flag = False
                self._spell_seen_frame = -1
                # 自主代理恢复（仅当 spell 是一次性（非躲猫猫）的情况才恢复；
                # 躲猫猫整体结束再恢复）
                if getattr(self, '_spell_auto_suspended', False) and getattr(self, '_hide_stage', None) is None:
                    try:
                        self.autonomous_agent.resume()
                    except Exception as e:  # 修复：原先静默吞噬
                        self._log_().debug("main 防御性异常（已忽略）: %s", e)
                    self._spell_auto_suspended = False
                elif getattr(self, '_spell_auto_suspended', False):
                    self._spell_auto_suspended = False
                try:
                    if callable(cb):
                        cb(path, kind)
                finally:
                    # 只有 回调没再次启动 spell，且当前动画还停留在 callback 前的 spell/spell_left，才切回 idle
                    if (self._spell_stage is None
                            and _anim_before_cb in ('spell', 'spell_left')
                            and self.current_animation == _anim_before_cb):
                        self.change_animation('idle', force=True)

    def _cast_spell_then(self, cb, direction=None):
        """**纯施法**：不走 walking 阶段，直接播 spell / spell_left。
        用于躲猫猫"创建文件夹"/"躲藏"两个仪式动作。cb：(path, kind) -> None"""
        # 1) 清理旧 spell 状态（只清 spell，不 abort 整个躲猫猫游戏）
        # 多次调用 _cast_spell_then 是躲猫猫的正常流程推进（creating→hiding_spell），
        # 不能调用 _abort_hide_and_seek 否则直接杀掉整个游戏
        self._spell_stage = None
        self._spell_finish_cb = cb
        self._spell_target_path = None
        self._spell_target_kind = '__cast_only__'
        self._spell_frames_seen = 0
        self._spell_seen_frame = -1

        # 2) 确定朝向（spell_left / spell）
        if direction is None:
            direction = 'right' if self.current_direction != 'left' else 'left'
        spell_anim = 'spell_left' if direction == 'left' else 'spell'

        # 3) 登记为 casting 阶段
        self._spell_stage = 'casting'
        # 施法音效
        try:
            self.sound_manager.play_spell()
        except Exception as e:  # 修复：原先静默吞噬
            self._log_().debug("main 防御性异常（已忽略）: %s", e)
        self._spell_target_direction = direction
        self.previous_direction = self.current_direction
        self.current_direction = direction
        ok = self.change_animation(spell_anim, force=True)
        if ok:
            self.current_frame = 0
        else:
            # 兜底：直接强制设置 + 清零帧
            self.current_animation = spell_anim
            self.current_frame = 0
            self.current_priority = 5
            self.last_animation_change = time.time()
        self._spell_cast_start_frame = 0
        # 暂停自主代理（如果有的话）
        try:
            self.autonomous_agent.suspend()
            self._spell_auto_suspended = True
        except Exception as e:  # 修复：原先静默吞噬
            self._log_().debug("main 防御性异常（已忽略）: %s", e)

    def _start_open_with_spell(self, path, kind, cb):
        """打开文件/文件夹的入口：
        1) walking 阶段：Ralsei 走过去（靠近 path 的屏幕坐标）
        2) casting 阶段：施法 11 帧
        3) 调用 cb(path, kind) 真实打开文件"""
        # 清理旧 spell（只清 spell，不 abort 躲猫猫游戏——躲猫猫 searching 阶段找到文件时
        # 本来就是 open_with_spell，不能反过来 abort 游戏）
        self._spell_stage = None

        # 1) 目标屏幕坐标 + 朝向
        (tx, ty) = self._resolve_target_screen_anchor(path)
        me = self.frameGeometry().center()
        dx = tx - me.x()
        dy = ty - me.y()
        if abs(dx) > abs(dy):
            direction = 'right' if dx > 0 else 'left'
        else:
            direction = 'down' if dy > 0 else 'up'
        spell_anim = 'spell_left' if direction == 'left' else 'spell'

        # 2) 登记 walking 阶段
        self._spell_stage = 'walking'
        self._spell_target_kind = kind
        self._spell_target_path = path
        self._spell_target_screen_pos = (tx, ty)
        self._spell_target_direction = direction
        self._spell_finish_cb = cb
        self._spell_frames_seen = 0
        self._spell_seen_frame = -1

        # 3) 如果已经足够近（<35px），下一次 _tick_spell_flow 会立刻转 casting
        #    暂停自主代理（避免干扰）
        try:
            self.autonomous_agent.suspend()
            self._spell_auto_suspended = True
        except Exception as e:  # 修复：原先静默吞噬
            self._log_().debug("main 防御性异常（已忽略）: %s", e)

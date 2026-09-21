# -*- coding: utf-8 -*-
"""
躲猫猫流程控制器 —— H4/H5「上帝类拆分」Wave 1 第 4 项（W1-2）。

搬出来的是什么
--------------
`RalseiPet` 里「躲猫猫 (hide & seek)」这条业务线的 **12 个方法**：

    start_hide_and_seek_game            (27)  —— 入口：走到屏幕中央 → 造障碍物 → 施法藏身
    _abort_hide_and_seek                (34)  —— 中断清理（关计时器 / 销毁障碍物 / 恢复自主代理）
    _hide_move_to_point                 (19)  —— 封装：驱动主移动系统走到 (x,y)，到达回调 cb
    _hide_on_arrive_center               (7)  —— 到达中央 → 造 5 个障碍物文件夹
    _hide_create_obstacles_after_spell  (53)  —— 施法动画后真正建文件夹 + 记入障碍物列表
    _hide_after_hiding_spell            (11)  —— 藏身施法完成 → 走到藏身文件夹
    _hide_on_arrive_folder              (21)  —— 到达藏身处 → 进入 searching，起 20s 计时器
    _hide_search_tick                   (38)  —— 每 3s 打开一个错误文件夹"表演找我"
    _hide_end_game                      (23)  —— 结束：暂停自主代理 / 停计时器 / 销毁障碍物
    _hide_destroy_obstacles             (23)  —— 销毁（移回收站）所有障碍物文件夹
    _hide_report_clicked_folder         (54)  —— 用户点文件夹 → 判对错 → 反馈
    _hide_jump_back_to_desktop          (11)  —— 找到后从文件夹窗口跳回桌面

口径与排期方案的核对
--------------------
* 排期方案 §5.2：**12 个方法 / 342 行**（342 = 含 `def` + docstring 的物理行数）。
  AST 实测 body 行 = **321**，物理行 = **342** —— 与方案一致。
* ⚠️ `scan_method_index.py` 的分组列会把它报成 **12 方法 / 323 行**（口径偏小），
  且**按 `startswith('_hide')` 前缀误纳了 `_hide_ralsei`**（L558，17 行）。
  `_hide_ralsei` 是**托盘隐藏**，方案原文明确「属别处，勿并入」→ **本模块不含它**。
  这是分组器前缀启发式的**第 3 次**踩坑（W1-4 漏标 `_*video*`、W1-1 漏标 `_tick_*`/`_cast_*`、
  本次误纳 `_hide_ralsei`）→ **索引只能当下限，必须回排期方案核对。**

为什么是这一块（Wave 1 顺序 W1-3 → W1-4 → W1-1 → W1-2 → W1-6）
--------------------------------------------------------------
它与 W1-1（施法）有 G3 点名的互写：`_hide_stage` / `_hide_obstacles` / `_hide_folder_path`
（归本项）与 `_spell_auto_suspended`（归 W1-1）。
本项同样**靠"状态全部留在宿主"消掉这条耦合**：4 个属性一个都不搬，
控制器里 `self._hide_stage` 经 `__getattr__` 读到**宿主那一份**，
`self._spell_auto_suspended = False`（`_hide_destroy_obstacles` 尾部）经 `__setattr__`
写回**宿主那一份** → 两个控制器互不认识，无需 `pyqtSignal`。

与宿主 `__getattr__` 的互调用（**不是**互写）
---------------------------------------------
* `_hide_move_to_point` 写 `target_pos` / `is_moving` / `speed` / `moving_duration`
  —— 这 4 个是**移动子系统**的宿主状态（`init_movement()` 声明），归 Wave 2。
  经 `__setattr__` 写回宿主 → 主移动循环（`update_movement`，留在宿主）照常读到。
* 宿主方法 `_notify_arrived_if_needed`（L1315，**留在宿主**）读 `_hide_moving_cb` /
  `_hide_moving_cb_stage` 并**写 None** —— 这是宿主↔本项的互写点，靠"状态留宿主"天然成立。
* `_hide_move_to_point` 调 `self.change_animation(...)`、`self.frameGeometry()`；
  `_hide_jump_back_to_desktop` 调 `self._clamp_pos_to_desktop(...)` —— 均**调用**宿主 API。

本模块的模块级 import
---------------------
  * `time`   —— `_hide_search_tick` L9369 `time.time()` 是**裸用** ⚠️
  * `PyQt5.QtCore.QPoint` —— `_hide_move_to_point` L9248 `QPoint(tx, ty)` 是**裸用** ⚠️
  * `logging` —— 见 `_log_()`。

⚠️ `time` / `QPoint` 被搬的方法体里是裸名，在 `main.py` 靠**模块级** import 解析
（`main.py` L4 / L18）。搬走后模块作用域变了 → `NameError`，而**逐字等价断言测不出来**。
这是 W1-4 坑 1（`QRect`/`QTimer`）、W1-1 坑（`os`/`time`/`QPoint`）的**同型第 3 次**。

❗ 铁律 1（`self` 当对象传出去救不了）
-------------------------------------
`_hide_on_arrive_folder` L9359 原文 `QTimer(self)` —— `self` 在这里是**宿主窗口**（QObject）。
搬进本类后 `self` 是**控制器**（纯 `object`）→ `QTimer(self)` 抛
`TypeError: arguments did not match any overloaded call`。
已改为 **`QTimer(self.p)`**。这是本项**唯一**一处铁律 1，且逐字等价断言 100% 测不出来。
（另两处 L9502 / L9527 是 `QTimer.singleShot` 静态调用，无 parent，**安全**。）

不搬的局部 import
-----------------
`shutil` / `random` / `winshell` / `QTimer` 在方法体里是**局部 import**（L9227/9433、
L9295/9392、L9439、L9358/9501/9526）→ **保持原位**。若提到模块级，会把 `winshell`
这种可选依赖变成导入期硬依赖。

为什么不 import 任何项目内模块
-----------------------------
同 `event_speech.py` / `games_controller.py` / `video_controller.py` / `spell_controller.py`
的纪律：本模块位于「初始化环」下游（`main.py` import 期就要
`from modules.hide_controller import HideAndSeekController`），回头 import
`logger_utils` / `dialogue_ui` 会把环重新接上。
"""

import logging
import os
import time

from PyQt5.QtCore import QPoint

_log = logging.getLogger(__name__)


class HideAndSeekController(object):
    """躲猫猫流程。宿主（`RalseiPet`）持有，方法通过宿主 `__getattr__` 转发壳暴露。

    与 `GamesController` / `VideoController` / `SpellFlowController` **完全同构**：
    本类需要 `__getattr__`（读宿主状态）+ `__setattr__`（写宿主状态），
    因为「只搬方法不搬状态」意味着方法体里 `self._hide_stage` /
    `self.change_animation` / `self.dialogue_ui` 这些宿主成员一个字都没改。

    转发判据与成环防护的完整论证见 `spell_controller.py` / `games_controller.py`
    的类 docstring 与 `main.py` 的 `_CONTROLLER_ATTRS` 注释 —— 真机踩过的
    `RecursionError`（构造期崩）也记在那里，**勿回退**。
    """

    def __init__(self, ralsei_pet):
        # 宿主引用：躲猫猫状态全在宿主身上，本类只借用，不复制、不缓存。
        # 普通赋值 → `p` 进实例字典 → `self.p` 走常规查找，不会递归回 __getattr__。
        self.p = ralsei_pet

    def __getattr__(self, name):
        # 只在常规查找失败时进入。两条**显式白名单**后才回落：
        #   · 宿主实例字典（_hide_stage / _spell_auto_suspended / dialogue_ui …）
        #   · 宿主**类型** MRO 上的东西（change_animation / frameGeometry /
        #     _clamp_pos_to_desktop / _current_screen_rect / QMainWindow 的 move/width …）
        # 两条都不满足 → 抛，切断「宿主也没有 → 宿主 __getattr__ → 又转回本类」的成环路径。
        pet = self.__dict__.get('p')
        if pet is None:
            raise AttributeError(name)
        if name in pet.__dict__:
            return pet.__dict__[name]
        if any(name in klass.__dict__ for klass in type(pet).__mro__):
            return getattr(pet, name)
        # 第 3 条白名单：**兄弟控制器**（W1-2 施工中 e2e 抓到的真 P0）。
        # 控制器 A 调 `self.<B 的方法>` 时，B 的方法是 **B 的类属性** ——
        # 既不在宿主实例字典、也不在宿主类型 MRO → 前两条都不命中 → AttributeError。
        # 实例：`_hide_end_game` 调 `self._cast_spell_then`（属 SpellFlowController）。
        # 修法：复刻宿主的 `_CONTROLLER_ATTRS` 扫描，**跳过自己**；
        # 只看对方**类**上的名字（不触发对方实例的 __getattr__）→ 不成环。
        for _attr in getattr(type(pet), '_CONTROLLER_ATTRS', ()):
            _ctrl = pet.__dict__.get(_attr)
            if _ctrl is None or _ctrl is self:
                continue
            if getattr(type(_ctrl), name, None) is not None:
                return getattr(_ctrl, name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        # ⚠️ 「逐字等价测不出来」的第二个坑（W1-4 e2e 才炸出来）。
        # 普通过赋值走 object.__setattr__ → 直接写进**控制器自己的 __dict__** →
        # 状态被劈成两份（宿主读数与控制器读数不一致，行为静默错乱）。
        # 转发判据 = 宿主**已经拥有**的名字（实例字典或 MRO 上有）——
        # 判据的关键是**能自动覆盖新状态名**（本项目最贵的坑：
        # "函数写对了但产品用不上"）。控制器**故意不允许**给自己新增业务属性。
        #
        # 本项后果（若不修）：`self._hide_stage = 'searching'` 落进控制器，
        # 而宿主 `_notify_arrived_if_needed` 读 `getattr(self,'_hide_stage',None)` 永远 None
        # → 到达回调永不触发 → 躲猫猫卡死。
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
    # 躲猫猫业务（W1-2 搬运区，**以下方法体逐字来自 main.py L9175-9527**，
    # 唯一改动两类：`_log.` → `self._log_().`（15 处）、
    # `QTimer(self)` → `QTimer(self.p)`（1 处），逐方法计数见施工报告）
    # ------------------------------------------------------------------

    def start_hide_and_seek_game(self):
        # 入口：检查重复启动、暂停自主代理、移动到屏幕中央
        # 修复：返回 True 表示成功开始，False 表示已有游戏在玩（供调用方决定话术）
        if getattr(self, 'game_state', {}).get('is_playing'):
            return False
        if getattr(self, '_hide_stage', None) is not None:
            return False
        # 暂停自主代理
        try:
            self.autonomous_agent.suspend()
        except Exception as e:  # 修复：原先静默吞噬
            self._log_().debug("main 防御性异常（已忽略）: %s", e)
        self.game_state['is_playing'] = True
        self.game_state['game_type'] = 'hide_and_seek'

        # 计算屏幕中央（瞬移防治：取 Ralsei 所在的这块屏的中心，而非主屏中心）
        screen = self._current_screen_rect()
        cx = int(screen.x() + screen.width() / 2)
        cy = int(screen.y() + screen.height() / 2)
        self._hide_center_x = cx
        self._hide_center_y = cy

        # 1) 走到屏幕正中央（自然走路：is_moving + target_pos 主系统）
        self._hide_stage = 'moving_to_center'
        self.dialogue_ui.add_dialogue("ralsei", "好~ 我先准备 5 个藏身的地方，然后藏起来，你来找我好不好？", "excited")
        self.dialogue_ui.show_dialogue()
        self._hide_move_to_point(cx, cy, self._hide_on_arrive_center, 'moving_to_center')
        return True

    def _abort_hide_and_seek(self, reason='generic'):
        """躲猫猫任一阶段被中断时调用。
        若有真实游戏在进行，则清理障碍并退出；否则只打印一声。"""
        hs = getattr(self, '_hide_stage', None)
        if hs is None and not getattr(self, 'game_state', {}).get('is_playing'):
            return
        real_interrupt = (hs is not None)
        # 清理游戏状态
        self._hide_stage = None
        self.game_state['is_playing'] = False
        self.game_state['game_type'] = None
        # searching 定时器停掉
        try:
            if getattr(self, '_hide_search_timer', None) is not None:
                self._hide_search_timer.stop()
        except Exception as e:  # 修复：原先静默吞噬
            self._log_().debug("main 防御性异常（已忽略）: %s", e)
        self._hide_search_timer = None
        # 清理障碍物（如果有创建记录）
        obstacles = getattr(self, '_hide_obstacles', []) or []
        for p in obstacles:
            try:
                if os.path.isdir(p):
                    import shutil
                    shutil.rmtree(p, ignore_errors=True)
            except Exception as e:  # 修复：原先静默吞噬
                self._log_().debug("main 防御性异常（已忽略）: %s", e)
        self._hide_obstacles = []
        self._hide_folder_path = None
        # 恢复自主代理
        try:
            self.autonomous_agent.resume()
        except Exception as e:  # 修复：原先静默吞噬
            self._log_().debug("main 防御性异常（已忽略）: %s", e)
        if real_interrupt and reason not in ('end_hide_and_seek', 'cast_spell_then_replaced'):
            self.dialogue_ui.add_dialogue("ralsei", "呜…游戏被打断啦！下次再玩吧~", "sad")
            self.dialogue_ui.show_dialogue()

    def _hide_move_to_point(self, x, y, cb, stage_name):
        """封装：把宠物窗口中心移到 (x, y)，到达时调用 cb()。
        使用主系统 is_moving + target_pos，保证自然走+walk动画。"""
        # 目标坐标（窗口左上角）
        tx = int(x - self.width() / 2)
        ty = int(y - self.height() / 2)
        self.target_pos = QPoint(tx, ty)
        self.is_moving = True
        self.speed = 6.0
        self.moving_duration = 0
        # 注册到达回调（在 _notify_arrived_if_needed 里触发）
        self._hide_moving_cb = cb
        self._hide_moving_cb_stage = stage_name
        # 手动设一次方向，保证立刻走起来
        me = self.frameGeometry().center()
        dx = x - me.x()
        dy = y - me.y()
        if abs(dx) > abs(dy):
            new_dir = 'right' if dx > 0 else 'left'
        else:
            new_dir = 'down' if dy > 0 else 'up'
        self.change_animation(f"walk_{new_dir}", force=True)

    def _hide_on_arrive_center(self):
        if getattr(self, '_hide_stage', None) != 'moving_to_center':
            return
        self._hide_stage = 'creating'
        self.dialogue_ui.add_dialogue("ralsei", "魔法~ 变出 5 个小盒子！✨", "excited")
        self.dialogue_ui.show_dialogue()
        # [spell right] → 完成后回调 _hide_create_obstacles_after_spell
        self._cast_spell_then(self._hide_create_obstacles_after_spell, direction='right')

    def _hide_create_obstacles_after_spell(self, path=None, kind=None):
        if getattr(self, '_hide_stage', None) != 'creating':
            return
        # —— 固定布局：上 3 下 2 ——
        # 上 3：屏幕中心 X 轴 -120 / 0 / +120，Y = 中心 Y - 180
        # 下 2：屏幕中心 X 轴 -60 / +60，Y = 中心 Y + 180
        # 修复：用真实桌面路径（OneDrive 桌面重定向时 USERPROFILE\Desktop 不是用户看到的桌面，
        # 障碍物会创建到看不见的目录 → "躲猫猫根本没生成障碍物"）
        desktop_dir = self.desktop_interaction.desktop_path
        screen = self._current_screen_rect()
        cx = screen.center().x()
        cy = screen.center().y()
        positions = [
            ('top_left',     cx - 120, cy - 180),
            ('top_center',   cx,       cy - 180),
            ('top_right',    cx + 120, cy - 180),
            ('bottom_left',  cx - 60,  cy + 180),
            ('bottom_right', cx + 60,  cy + 180),
        ]
        created = []
        base_names = ['障碍物1', '障碍物2', '障碍物3', '障碍物4', '障碍物5']
        import random
        random.shuffle(positions)
        for i, (tag, px, py) in enumerate(positions):
            folder_path = os.path.join(desktop_dir, base_names[i])
            # 如果存在就加后缀避免冲突
            suffix = 2
            while os.path.exists(folder_path):
                folder_path = os.path.join(desktop_dir, f"{base_names[i]}_{suffix}")
                suffix += 1
            try:
                os.makedirs(folder_path, exist_ok=True)
                created.append(folder_path)
            except Exception as e:
                # 修复：创建失败不再完全静默（否则 len(created)<3 时游戏莫名提前结束，
                # 且原因不可见）。打印失败原因便于排查（如权限/路径问题）。
                self._log_().warning(f"[躲猫猫] 障碍物创建失败: {folder_path} -> {type(e).__name__}: {e}")
        self._hide_obstacles = created
        if len(created) < 3:
            # 极端失败：结束游戏
            self.dialogue_ui.add_dialogue("ralsei", "呜…怎么变不出来呢…下次再玩吧。", "sad")
            self.dialogue_ui.show_dialogue()
            self._abort_hide_and_seek(reason='end_hide_and_seek')
            return

        # 在 5 个里选 1 个当藏身点
        chosen = random.choice(created)
        self._hide_folder_path = chosen

        # —— 躲藏仪式：[spell left] ——
        self._hide_stage = 'hiding_spell'
        self.dialogue_ui.add_dialogue("ralsei", "我要开始藏啦~ 不许偷看哦！", "happy")
        self.dialogue_ui.show_dialogue()
        self._cast_spell_then(self._hide_after_hiding_spell, direction='left')

    def _hide_after_hiding_spell(self, path=None, kind=None):
        if getattr(self, '_hide_stage', None) != 'hiding_spell':
            return
        self._hide_stage = 'moving_to_folder'
        # 计算藏身处 folder 在桌面的坐标（desktop_interaction 查不到就用我们创建时记录的位置）
        folder_path = self._hide_folder_path
        (fx, fy) = self._resolve_target_screen_anchor(folder_path)
        # 再往 folder 下方走一步，站在文件夹前
        fy2 = fy + 80
        screen = self._current_screen_rect()
        fy2 = min(fy2, screen.y() + screen.height() - self.height() // 2 - 10)
        self._hide_move_to_point(fx, fy2, self._hide_on_arrive_folder, 'moving_to_folder')

    def _hide_on_arrive_folder(self):
        if getattr(self, '_hide_stage', None) != 'moving_to_folder':
            return
        # 到达藏身文件夹前 → 躲藏：Ralsei 在桌面上消失（隐藏窗口）
        folder_path = self._hide_folder_path
        # 不自动打开文件夹，等用户自己打开
        self.hide()  # 桌面上消失
        # 进入 searching 阶段
        self._hide_stage = 'searching'
        self.dialogue_ui.add_dialogue("ralsei", "藏好啦~ 快点点桌面上的文件夹来找我吧！（20 秒内找不到算我赢哦）", "excited")
        self.dialogue_ui.show_dialogue()
        # searching 阶段最多 20 秒；每 3 秒打开一个错误文件夹"表演找我"
        self._hide_search_started_at = time.time()
        self._hide_search_checked = set()
        try:
            if getattr(self, '_hide_search_timer', None) is None:
                from PyQt5.QtCore import QTimer
                self._hide_search_timer = QTimer(self.p)
                self._hide_search_timer.timeout.connect(self._hide_search_tick)
            self._hide_search_timer.start(3000)
        except Exception as e:  # 修复：原先静默吞噬
            self._log_().debug("main 防御性异常（已忽略）: %s", e)

    def _hide_search_tick(self):
        if getattr(self, '_hide_stage', None) != 'searching':
            return
        # 20 秒总超时 = Ralsei 赢
        if time.time() - getattr(self, '_hide_search_started_at', 0) > 20:
            self.dialogue_ui.add_dialogue("ralsei", "啦啦啦~ 时间到！你找不到我！我赢啦~ 嘻嘻！", "happy")
            self.dialogue_ui.show_dialogue()
            self._hide_end_game(user_won=False)
            return
        # ===== 修复：检测玩家是否点开了某个障碍物文件夹（"玩家点击获胜"接线）=====
        # 此前 _hide_report_clicked_folder 没有任何调用点，玩家永远无法通过点击文件夹获胜。
        # 这里通过窗口标题匹配 5 个障碍物文件夹名来识别"玩家打开了哪个文件夹"。
        try:
            windows = self.desktop_interaction.get_all_visible_windows()
            for p in getattr(self, '_hide_obstacles', []):
                name = os.path.basename(p)
                for w in windows:
                    title = w.get('title', '') or ''
                    if name and name in title:
                        self._hide_report_clicked_folder(p)
                        return
        except Exception as e:  # 修复：原先静默吞噬
            self._log_().debug("main 防御性异常（已忽略）: %s", e)
        # 每隔 3 秒打开一个"错误的文件夹"（表演找不到）
        unchecked = [p for p in getattr(self, '_hide_obstacles', [])
                     if p != self._hide_folder_path and p not in getattr(self, '_hide_search_checked', set())]
        if unchecked:
            import random
            pick = random.choice(unchecked)
            self._hide_search_checked.add(pick)
            try:
                os.startfile(pick)
            except Exception:
                try:
                    self.desktop_interaction.open_folder(pick)
                except Exception as e:  # 修复：原先静默吞噬
                    self._log_().debug("main 防御性异常（已忽略）: %s", e)
            self.dialogue_ui.add_dialogue("ralsei", "你点的这个…我不在这儿呀~", "happy")
            self.dialogue_ui.show_dialogue()

    def _hide_end_game(self, user_won):
        hs = getattr(self, '_hide_stage', None)
        self._hide_stage = None
        self.game_state['is_playing'] = False
        self.game_state['game_type'] = None
        # 确保 Ralsei 可见
        self.show()
        # 关 searching 定时器
        try:
            if getattr(self, '_hide_search_timer', None) is not None:
                self._hide_search_timer.stop()
        except Exception as e:  # 修复：原先静默吞噬
            self._log_().debug("main 防御性异常（已忽略）: %s", e)
        self._hide_search_timer = None
        # 先把藏身处显示对话（文件夹还没删），让用户知道结果
        if user_won:
            self.change_animation('surprised', force=True)
            self.dialogue_ui.add_dialogue("ralsei", "哎？！被你发现了…真厉害呀~  你赢啦！", "surprised")
            self.dialogue_ui.show_dialogue()
        else:
            self.change_animation('laugh', force=True)
            self.show()  # Ralsei 输了也要重新出现
        # —— 销毁文件夹前播放 spell 动画（spr_ralsei_spell_0~10）——
        self._cast_spell_then(self._hide_destroy_obstacles, direction='right')

    def _hide_destroy_obstacles(self, path=None, kind=None):
        """spell 动画播放完后，真正删除桌面上所有 5 个障碍物文件夹。"""
        obstacles = list(getattr(self, '_hide_obstacles', []) or [])
        import shutil
        for p in obstacles:
            try:
                if os.path.isdir(p):
                    # 先尝试回收；删不掉就彻底删
                    try:
                        import winshell
                        winshell.delete_file(p, no_confirm=True, allow_undo=True)
                    except Exception:
                        shutil.rmtree(p, ignore_errors=True)
            except Exception as e:  # 修复：原先静默吞噬
                self._log_().debug("main 防御性异常（已忽略）: %s", e)
        self._hide_obstacles = []
        self._hide_folder_path = None
        # 恢复自主代理
        try:
            self.autonomous_agent.resume()
        except Exception as e:  # 修复：原先静默吞噬
            self._log_().debug("main 防御性异常（已忽略）: %s", e)
        self._spell_auto_suspended = False
        # 切回 idle
        self.change_animation('idle', force=True)

    def _hide_report_clicked_folder(self, folder_path):
        """searching 阶段：用户点了桌面上某个文件夹就调用它。
        点对了 = 玩家赢：Ralsei 出现在文件夹窗口，说"你找到我了"，然后跳回桌面；
        点错了 = 对话 + 继续。"""
        if getattr(self, '_hide_stage', None) != 'searching':
            return
        if not folder_path or not os.path.isdir(folder_path):
            return
        # 必须是我们创建的 5 个障碍物之一
        if folder_path not in getattr(self, '_hide_obstacles', []):
            return
        if folder_path == self._hide_folder_path:
            # —— 玩家赢 ——
            # 修复：先把 searching 阶段的定时器停掉并离开 searching 状态，
            # 否则 1.2 秒延迟内若恰逢 3 秒 tick / 20 秒超时，会再触发一次
            # _hide_end_game(False)，与跳回后的 _hide_end_game(True) 双执行
            # （双 spell destroy、对话/动画互相覆盖）。
            try:
                if getattr(self, '_hide_search_timer', None) is not None:
                    self._hide_search_timer.stop()
            except Exception as e:  # 修复：原先静默吞噬
                self._log_().debug("main 防御性异常（已忽略）: %s", e)
            self._hide_search_timer = None
            self._hide_stage = 'won_pending'  # 非 searching，避免 tick/超时重复触发
            # 1. 打开正确的文件夹窗口
            try:
                self.desktop_interaction.open_folder(folder_path)
            except Exception:
                try:
                    os.startfile(folder_path)
                except Exception as e:  # 修复：原先静默吞噬
                    self._log_().debug("main 防御性异常（已忽略）: %s", e)
            # 2. Ralsei 出现在文件夹窗口里（显示窗口，定位到文件夹窗口附近）
            self.show()
            # 尝试定位到文件夹窗口的位置
            try:
                (fx, fy) = self._resolve_target_screen_anchor(folder_path)
                self.move(int(fx - self.width() // 2), int(fy - self.height() // 2))
            except Exception as e:  # 修复：原先静默吞噬
                self._log_().debug("main 防御性异常（已忽略）: %s", e)
            # 3. 说"你找到我了"
            self.change_animation('surprised', force=True)
            self.dialogue_ui.add_dialogue("ralsei", "你找到我啦！真厉害！", "surprised")
            self.dialogue_ui.show_dialogue()
            # 4. 延迟1秒后从窗口跳回桌面，然后结束游戏（销毁文件夹）
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(1200, lambda: self._hide_jump_back_to_desktop())
        else:
            # 错误：打开它，加一句对话，继续 searching
            try:
                self.desktop_interaction.open_folder(folder_path)
            except Exception:
                try:
                    os.startfile(folder_path)
                except Exception as e:  # 修复：原先静默吞噬
                    self._log_().debug("main 防御性异常（已忽略）: %s", e)
            self.dialogue_ui.add_dialogue("ralsei", "这里没有我~ 再找找！", "happy")
            self.dialogue_ui.show_dialogue()

    def _hide_jump_back_to_desktop(self):
        """躲猫猫找到后：从文件夹窗口跳回桌面，然后触发结束（销毁障碍物）。"""
        # 播放跳跃动画，从当前位置跳到桌面底部
        screen = self._current_screen_rect()
        target_y = screen.y() + screen.height() - self.height() - 50
        target_x = self.x()
        # 简单跳跃：直接移动到桌面位置，播放jump动画
        self.change_animation('jump', force=True)
        target_x, target_y = self._clamp_pos_to_desktop(target_x, target_y)
        self.move(target_x, target_y)
        # 延迟后结束游戏（用spell动画销毁文件夹）
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(500, lambda: self._hide_end_game(user_won=True))

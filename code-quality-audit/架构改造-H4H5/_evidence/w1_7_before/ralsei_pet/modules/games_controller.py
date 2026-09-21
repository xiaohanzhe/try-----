# -*- coding: utf-8 -*-
"""小游戏控制器 —— H4/H5「上帝类拆分」Wave 1 第 1 项（W1-3）。

搬出来的是什么
--------------
`RalseiPet` 里「石头剪刀布 + 猜数字」这 7 个方法（原 main.py L6522–6785）：

    start_rock_paper_scissors / play_rock_paper_scissors /
    determine_rock_paper_scissors_winner / end_rock_paper_scissors
    start_guess_number / play_guess_number / end_guess_number

为什么是这一块**第一个**搬（Wave 1 顺序 W1-3 → W1-4 → W1-1 → W1-2 → W1-6）
----------------------------------------------------------------
它是 Wave 1 里唯一「**块内闭合、零互写**」的一块：七个方法的互调全在块内
（`play_*` → `determine_*` / `end_*`），对外只依赖 `dialogue_ui` / `play_animation_once`
/ `emotion_system` 这三个**早就独立**的宿主成员，不触碰躲猫猫（W1-2）、施法（W1-1）、
视频（W1-4）、文件表（W1-6）的任何状态。先搬它能把「转发壳」这套口径在最小风险面
上跑通一遍，后面四项照着抄。

施工口径（H4/H5 铁律）：**只搬方法、不搬状态**
--------------------------------------------
* 本类**不持有**任何游戏状态。`game_state` / `guess_number_game` /
  `rock_paper_scissors_options` 三个属性**仍留在 `RalseiPet.__init__`**，本类只通过
  宿主引用（`self.p`）读写它们。
* 状态迁移是**故意推迟**的（那属于 G3 属性归属表的后续批次）。理由：本轮的安全判据
  是「G2 回归输出逐字节一致」，而状态的读写点遍布 `update_stats` / `dialogue_ui` /
  `handle_game_input`；状态留在原地，转发壳就只是「同一个对象、换个方法查找路径」，
  行为等价近乎平凡。反过来若同时搬状态，就同时引入了两类变化，DIFF 时无法归因。

为什么不 import 任何项目内模块
---------------------------
同 `event_speech.py` / `lazy_log.py` 的纪律：本模块位于「**初始化环**」的下游 ——
`main.py` 在 import 期就要 `from modules.games_controller import GamesController`，
此刻若本模块回头 `import logger_utils` / `dialogue_ui` 等，会把环重新接上（本项目已
踩过 4 次，见 `lazy_log.py` 的 docstring）。所以：

* **不 import 任何项目内模块**，日志用标准库 `logging`（本模块的方法体一行日志都不打，
  所以也不会触发 `logger_utils` 的目录解析）；
* 宿主的能力（`dialogue_ui` / `play_animation_once` / `emotion_system`）通过
  `self.p` 动态取用，不做 import。

方法体是**逐字搬运**，注释（含中文「修复：…」历史记录）一字未改 —— 那些注释记录了
真实踩过的坑（`update` vs 整体替换导致的 KeyError、猜对了却放难过动画的方向反转），
是防回退的唯一凭证。
"""
import random
import time


class GamesController(object):
    """石头剪刀布 + 猜数字。宿主（`RalseiPet`）持有，自己的方法通过转发壳暴露。

    为什么本类需要 `__getattr__`
    --------------------------
    「只搬方法不搬状态」意味着方法体**一字未改**地保留了 `self.game_state[...]` /
    `self.dialogue_ui.xxx()` / `self.play_animation_once(...)` 这些写法 —— 它们在
    宿主里合法，在控制器里就成了"找不到的属性"。两种做法：

      (a) 把方法体里的 `self.game_state` 全部改写成 `self.p.game_state` ——
          **改动 100+ 处**，每一处都是引入笔误的机会，而且 verify 的"逐字等价"
          判据会因此失效（要额外做归一化，判据变弱）。
      (b) 让控制器在自身查不到时**回落给宿主**（本实现）—— 方法体保持逐字不变，
          等价性可以用"归一 self.p. 后逐字节比较"来硬证明。

    选 (b)：改动面最小、判据最强。

    与宿主侧 `RalseiPet.__getattr__` 的**方向正好相反**（宿主 → 控制器找方法，
    控制器 → 宿主找状态），两者构成闭合的双向转发。

    ⚠️ 双向转发**必须有一侧是"显式白名单式"的**，否则会成环。现在两侧都是白名单：

      · 宿主那侧（`RalseiPet.__getattr__`）：只转发"控制器**类**上定义的
        `_CONTROLLER_ATTRS` 名单里的控制器"的方法，且用 `getattr(type(ctrl), name)`
        探测 —— **不**去 `hasattr(ctrl, ...)`（那会触发本类回落，直接成环）。
      · 本类这侧：只在**宿主实例字典里存在**、或**在宿主类型的 MRO 上存在**时
        才返回；两者都不满足就抛 —— 于是"宿主也没有"的名字不会在两个
        `__getattr__` 之间来回弹。

    真机踩过的递归（记在这里防回退）：`RalseiPet.__init__` 早期
    `randomize_movement_pattern()` 会 `getattr(self, 'game_state', {})`，而
    `game_state` 直到 `__init__` 末尾才赋值。那一刻：
      宿主 `__getattr__('game_state')` → `hasattr(ctrl, 'game_state')`
      → 本类回落 `getattr(pet, 'game_state')` → 宿主又进 `__getattr__` → 无限递归，
      `RecursionError` 崩在**构造期**（连窗口都起不来）。

    安全边界：取不到就抛原始的 `AttributeError`，保住 `hasattr` /
    `getattr(x, n, default)` 的语义。
    """

    def __init__(self, ralsei_pet):
        # 宿主引用：状态（game_state / guess_number_game / rock_paper_scissors_options）
        # 都在宿主身上，本类只借用，不复制、不缓存。
        # 注意用普通赋值即可 —— `p` 进了实例字典，后续 `self.p` 走常规查找，
        # 不会递归回 `__getattr__`。
        self.p = ralsei_pet

    def __getattr__(self, name):
        # 只在常规查找失败时进入。`self.p` 本身已在 __dict__ 里，所以下面这行
        # 不会递归。
        pet = self.__dict__.get('p')
        if pet is None:
            raise AttributeError(name)
        # 名字必须能由**宿主自己**解析，且解析过程不能重入宿主的 __getattr__：
        #   · 在宿主实例字典里（game_state / guess_number_game / dialogue_ui …）→ 直接给；
        #   · 在宿主**类型**的 MRO 上（play_animation_once / add_emotion 等方法、
        #     C++ 侧注册的属性）→ 走一次 getattr，此时常规查找必命中，不会重入。
        # 两条都不满足就不回落 —— 这切断了"宿主也没有 → 宿主 __getattr__ →
        # 又转回本类"那条唯一的成环路径。真机踩过：`__init__` 早期
        # `randomize_movement_pattern` 会 `getattr(self, 'game_state', {})`，
        # 而 `game_state` 直到 `__init__` 末尾才赋值。
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
        # 与其余四个控制器（SpellFlowController / HideAndSeekController /
        # VideoController / FileSheetController）**逐字同构**的写转发护栏。
        #
        # 为什么 W1-3 当时没加、现在补上：本块七个方法确实是「块内闭合、零互写」，
        # 现有代码里对游戏状态的写全是 `self.game_state.update({...})`（原地改字典）
        # 和 `self.game_state["k"] += 1`（下标写）—— 两者都**不经 __setattr__**，
        # 所以当时功能上正确。但「正确」依赖的是**调用方的写法**，不是类的约束：
        # 只要有人把 `self.game_state.update({...})` 重构成整体重赋值
        # `self.game_state = {...}`，或新增 `self.game_xxx = ...`，赋值就会静默落进
        # **控制器自己的 __dict__** → 宿主读到旧值 → 状态劈成两份。
        # 这个坑本项目真踩过一次（W1-4 的 is_watching_video），且 G2 完全看不见。
        #
        # 判据 = 宿主**已经拥有**的名字（实例字典 or MRO 上有）：
        #   · 自动覆盖将来新增的状态名，不必回来改名单；
        #   · 控制器**故意不允许**给自己新增业务属性 —— 想加状态就加到宿主上。
        # ⚠️ 必跳过 'p'：`p` 是控制器自己的宿主引用，转发出去就永远拿不到宿主了。
        if name != 'p':
            pet = self.__dict__.get('p')
            if pet is not None:
                if name in pet.__dict__ or any(
                        name in klass.__dict__ for klass in type(pet).__mro__):
                    setattr(pet, name, value)
                    return
        object.__setattr__(self, name, value)

    # ------------------------------------------------------------------
    # 石头剪刀布
    # ------------------------------------------------------------------
    def start_rock_paper_scissors(self):
        # 开始石头剪刀布游戏
        # 修复：其他游戏进行中（躲猫猫等）不允许覆盖——否则躲猫猫的 _hide_stage/
        # _hide_search_timer 残留、障碍文件夹永远留在桌面。返回 False 表示未开始。
        if self.game_state.get('is_playing'):
            self.dialogue_ui.add_dialogue("ralsei", "现在还在玩别的呢，等这一局结束再玩石头剪刀布吧~", "curious")
            self.dialogue_ui.show_dialogue()
            return False
        # 使用 update 而不是整体替换，保留 total_wins/current_streak/best_streak 等统计键
        # （否则 end_rock_paper_scissors 访问 self.game_state["total_wins"] 会 KeyError 崩溃）
        self.game_state.update({
            "is_playing": True,
            "game_type": "rock_paper_scissors",
            "game_round": 0,
            "player_score": 0,
            "ralsei_score": 0,
            "game_history": [],
            "started_at": time.time()
        })
        
        self.dialogue_ui.add_dialogue("ralsei", "我们来玩石头剪刀布吧！", "excited")
        self.dialogue_ui.add_dialogue("ralsei", "你要出什么呢？石头、剪刀还是布？", "happy")
        self.dialogue_ui.show_dialogue()
        
        # 播放开心动画
        self.play_animation_once("happy")
    
    def play_rock_paper_scissors(self, player_choice):
        # 处理石头剪刀布游戏的玩家选择
        if not self.game_state["is_playing"] or self.game_state["game_type"] != "rock_paper_scissors":
            return
        
        # 确保玩家选择有效
        player_choice = player_choice.strip()
        if player_choice not in self.rock_paper_scissors_options:
            self.dialogue_ui.add_dialogue("ralsei", f"请输入有效的选项：{'、'.join(self.rock_paper_scissors_options)}", "confused")
            return
        
        # Ralsei随机选择
        ralsei_choice = random.choice(self.rock_paper_scissors_options)
        
        # 判断胜负
        result = self.determine_rock_paper_scissors_winner(player_choice, ralsei_choice)
        
        # 更新分数
        self.game_state["game_round"] += 1
        if result == "player":
            self.game_state["player_score"] += 1
        elif result == "ralsei":
            self.game_state["ralsei_score"] += 1
        
        # 记录游戏历史
        self.game_state["game_history"].append({
            "round": self.game_state["game_round"],
            "player_choice": player_choice,
            "ralsei_choice": ralsei_choice,
            "result": result
        })
        
        # 显示结果
        result_messages = {
            "player": "你赢了！太棒了！",
            "ralsei": "我赢了！嘿嘿~",
            "tie": "平局！再来一次吧！"
        }
        
        self.dialogue_ui.add_dialogue("ralsei", f"你出了：{player_choice}", "neutral")
        self.dialogue_ui.add_dialogue("ralsei", f"我出了：{ralsei_choice}", "neutral")
        self.dialogue_ui.add_dialogue("ralsei", result_messages[result], "happy")
        self.dialogue_ui.add_dialogue("ralsei", f"比分：你 {self.game_state['player_score']} - {self.game_state['ralsei_score']} 我", "neutral")
        
        # 根据结果播放相应的动画
        if result == "player":
            self.play_animation_once("sad")
            self.emotion_system.add_emotion("sad", 20)
        elif result == "ralsei":
            self.play_animation_once("laugh")
            self.emotion_system.add_emotion("happy", 30)
        else:
            self.play_animation_once("neutral")
        
        # 询问是否继续游戏
        if self.game_state["game_round"] >= 5:
            # 游戏结束，显示最终结果
            self.end_rock_paper_scissors()
        else:
            # 询问是否继续
            self.dialogue_ui.add_dialogue("ralsei", "要继续玩吗？请输入石头、剪刀或布，或者输入'结束'来结束游戏。", "happy")
    
    def determine_rock_paper_scissors_winner(self, player_choice, ralsei_choice):
        # 判断石头剪刀布游戏的胜负
        if player_choice == ralsei_choice:
            return "tie"
        
        win_conditions = {
            "石头": "剪刀",
            "剪刀": "布",
            "布": "石头"
        }
        
        if win_conditions[player_choice] == ralsei_choice:
            return "player"
        else:
            return "ralsei"
    
    def end_rock_paper_scissors(self):
        # 结束石头剪刀布游戏
        final_message = "游戏结束！"
        if self.game_state["player_score"] > self.game_state["ralsei_score"]:
            final_message += "你赢了！太棒了！"
            self.play_animation_once("sad")
            self.emotion_system.add_emotion("sad", 20)
            # 更新游戏统计
            self.game_state["total_wins"] += 1
            self.game_state["current_streak"] += 1
            if self.game_state["current_streak"] > self.game_state["best_streak"]:
                self.game_state["best_streak"] = self.game_state["current_streak"]
        elif self.game_state["player_score"] < self.game_state["ralsei_score"]:
            final_message += "我赢了！嘿嘿~"
            self.play_animation_once("laugh")
            self.emotion_system.add_emotion("happy", 30)
            # 更新游戏统计
            self.game_state["total_losses"] += 1
            self.game_state["current_streak"] = 0
        else:
            final_message += "平局！真是一场精彩的比赛！"
            self.play_animation_once("neutral")
            # 更新游戏统计
            self.game_state["total_ties"] += 1
            self.game_state["current_streak"] = 0
        
        final_message += f"最终比分：你 {self.game_state['player_score']} - {self.game_state['ralsei_score']} 我"
        
        # 添加游戏统计信息
        stats_message = f"游戏统计：总游戏数 {self.game_state['total_games']}，胜利 {self.game_state['total_wins']}，失败 {self.game_state['total_losses']}，平局 {self.game_state['total_ties']}，当前连胜 {self.game_state['current_streak']}，最佳连胜 {self.game_state['best_streak']}"
        
        self.dialogue_ui.add_dialogue("ralsei", final_message, "happy")
        self.dialogue_ui.add_dialogue("ralsei", stats_message, "neutral")
        self.dialogue_ui.add_dialogue("ralsei", "谢谢你陪我玩！", "grateful")
        
        # 重置游戏状态
        self.game_state["is_playing"] = False
        self.game_state["game_type"] = None
    
    # ------------------------------------------------------------------
    # 猜数字
    # ------------------------------------------------------------------
    def start_guess_number(self):
        # 开始猜数字游戏
        # 修复：其他游戏进行中不允许覆盖（同 start_rock_paper_scissors）
        if self.game_state.get('is_playing'):
            self.dialogue_ui.add_dialogue("ralsei", "现在还在玩别的呢，等这一局结束再玩猜数字吧~", "curious")
            self.dialogue_ui.show_dialogue()
            return False
        
        # 生成目标数字
        self.guess_number_game["target_number"] = random.randint(
            self.guess_number_game["min_number"],
            self.guess_number_game["max_number"]
        )
        self.guess_number_game["attempts"] = 0
        
        # 更新游戏状态（update 保留统计键，避免后续 end_rock_paper_scissors 等 KeyError）
        self.game_state.update({
            "is_playing": True,
            "game_type": "guess_number",
            "game_round": 0,
            "player_score": 0,
            "ralsei_score": 0,
            "game_history": [],
            "started_at": time.time()
        })
        
        self.dialogue_ui.add_dialogue("ralsei", "我们来玩猜数字游戏吧！", "excited")
        self.dialogue_ui.add_dialogue("ralsei", f"我已经想好了一个{self.guess_number_game['min_number']}到{self.guess_number_game['max_number']}之间的数字，你有{self.guess_number_game['max_attempts']}次机会来猜！", "happy")
        self.dialogue_ui.add_dialogue("ralsei", "请输入你猜的数字：", "happy")
        self.dialogue_ui.show_dialogue()
        
        # 播放开心动画
        self.play_animation_once("happy")
    
    def play_guess_number(self, player_guess):
        # 处理猜数字游戏的玩家输入
        if not self.game_state["is_playing"] or self.game_state["game_type"] != "guess_number":
            return
        
        # 确保玩家输入是有效的数字
        try:
            player_guess = int(player_guess.strip())
        except ValueError:
            self.dialogue_ui.add_dialogue("ralsei", "请输入有效的数字！", "confused")
            return
        
        # 检查数字范围
        if player_guess < self.guess_number_game["min_number"] or player_guess > self.guess_number_game["max_number"]:
            self.dialogue_ui.add_dialogue("ralsei", f"请输入{self.guess_number_game['min_number']}到{self.guess_number_game['max_number']}之间的数字！", "confused")
            return
        
        # 更新尝试次数
        self.guess_number_game["attempts"] += 1
        self.game_state["game_round"] += 1
        
        # 记录游戏历史
        self.game_state["game_history"].append({
            "round": self.game_state["game_round"],
            "player_guess": player_guess,
            "target_number": self.guess_number_game["target_number"]
        })
        
        # 判断猜测结果
        target = self.guess_number_game["target_number"]
        if player_guess == target:
            # 猜对了
            self.game_state["player_score"] += 1
            self.dialogue_ui.add_dialogue("ralsei", f"恭喜你！猜对了！数字就是{target}！", "happy")
            # 修复：玩家猜对时 Ralsei 不该放"难过"动画/加悲伤情绪（原代码方向反转，
            # 文案祝贺、表情却难过）。Ralsei 是"被猜中"但游戏是陪玩，应一起开心。
            self.play_animation_once("happy")
            self.emotion_system.add_emotion("happy", 25)
            self.emotion_system.add_emotion("surprised", 15)
            self.end_guess_number()
        elif player_guess < target:
            # 猜小了
            attempts_left = self.guess_number_game["max_attempts"] - self.guess_number_game["attempts"]
            if attempts_left > 0:
                self.dialogue_ui.add_dialogue("ralsei", f"猜小了！再试一次！还剩{attempts_left}次机会。", "happy")
                self.dialogue_ui.add_dialogue("ralsei", "请输入你猜的数字：", "happy")
                self.play_animation_once("laugh")
                self.emotion_system.add_emotion("happy", 10)
            else:
                self.dialogue_ui.add_dialogue("ralsei", f"猜小了！很遗憾，你已经用完了所有机会。", "sad")
                self.end_guess_number()
        else:
            # 猜大了
            attempts_left = self.guess_number_game["max_attempts"] - self.guess_number_game["attempts"]
            if attempts_left > 0:
                self.dialogue_ui.add_dialogue("ralsei", f"猜大了！再试一次！还剩{attempts_left}次机会。", "happy")
                self.dialogue_ui.add_dialogue("ralsei", "请输入你猜的数字：", "happy")
                self.play_animation_once("laugh")
                self.emotion_system.add_emotion("happy", 10)
            else:
                self.dialogue_ui.add_dialogue("ralsei", f"猜大了！很遗憾，你已经用完了所有机会。", "sad")
                self.end_guess_number()
    
    def end_guess_number(self):
        # 结束猜数字游戏
        target = self.guess_number_game["target_number"]
        
        if self.game_state["player_score"] > 0:
            # 修复：玩家赢 → Ralsei 一起开心（原代码玩家赢却放 sad/难过）
            final_message = f"恭喜你赢了！数字是{target}！"
            self.play_animation_once("happy")
            self.emotion_system.add_emotion("happy", 20)
            self.emotion_system.add_emotion("grateful", 15)
        else:
            # 修复：玩家没猜中（Ralsei 守住了数字）→ 轻快收场（原代码玩家输反而 laugh 正确，保留）
            final_message = f"游戏结束！正确数字是{target}！下次再挑战我呀~"
            self.play_animation_once("laugh")
            self.emotion_system.add_emotion("happy", 10)
            self.emotion_system.add_emotion("playful", 10)
        
        self.dialogue_ui.add_dialogue("ralsei", final_message, "happy")
        self.dialogue_ui.add_dialogue("ralsei", "谢谢你陪我玩！", "grateful")
        
        # 重置游戏状态
        self.game_state["is_playing"] = False
        self.game_state["game_type"] = None

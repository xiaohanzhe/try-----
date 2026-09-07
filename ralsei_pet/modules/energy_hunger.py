import time

class EnergyHungerSystem:
    def __init__(self, parent):
        self.parent = parent
        
        # 初始值（0-100）
        self.energy = 80
        self.hunger = 70
        
        # 消耗速率（每分钟）
        self.energy_drain_rate = 1  # 每分钟消耗1点精力
        self.hunger_drain_rate = 2  # 每分钟消耗2点饥饿度
        
        # 恢复速率（每分钟）
        self.energy_recovery_rate = 5  # 休息时每分钟恢复5点精力
        self.hunger_recovery_rate = 8  # 吃东西时每分钟恢复8点饥饿度
        
        # 状态阈值
        self.low_energy_threshold = 30
        self.critical_energy_threshold = 10
        self.low_hunger_threshold = 30
        self.critical_hunger_threshold = 10
        
        # 上次更新时间
        self.last_update_time = time.time()

        # 状态
        self.is_resting = False
        self.is_eating = False

        # 阈值跨越跟踪：只在状态档位发生变化时才弹对话，避免每个 tick 重复刷屏
        # 档位: 'critical' / 'low' / 'normal' / 'high'
        self._prev_energy_tier = None
        self._prev_hunger_tier = None
        
    def update_stats(self):
        # 更新精力和饥饿度
        current_time = time.time()
        elapsed_time = (current_time - self.last_update_time) / 60  # 转换为分钟
        self.last_update_time = current_time
        
        # 更新精力
        if self.is_resting:
            # 休息时恢复精力
            self.energy += self.energy_recovery_rate * elapsed_time
        else:
            # 活动时消耗精力
            self.energy -= self.energy_drain_rate * elapsed_time
        
        # 更新饥饿度
        if self.is_eating:
            # 吃东西时恢复饥饿度
            self.hunger += self.hunger_recovery_rate * elapsed_time
        else:
            # 正常消耗饥饿度
            self.hunger -= self.hunger_drain_rate * elapsed_time
        
        # 确保数值在0-100之间
        self.energy = max(0, min(100, self.energy))
        self.hunger = max(0, min(100, self.hunger))
        
        # 检查状态变化并触发相应事件
        self.check_status_changes()
        
    def _energy_tier(self):
        if self.energy < self.critical_energy_threshold:
            return 'critical'
        elif self.energy < self.low_energy_threshold:
            return 'low'
        elif self.energy > 80:
            return 'high'
        return 'normal'

    def _hunger_tier(self):
        if self.hunger < self.critical_hunger_threshold:
            return 'critical'
        elif self.hunger < self.low_hunger_threshold:
            return 'low'
        elif self.hunger > 80:
            return 'high'
        return 'normal'

    def check_status_changes(self):
        # 只在档位发生跨越时弹一次对话，避免每个 tick 重复刷屏
        energy_tier = self._energy_tier()
        if energy_tier != self._prev_energy_tier:
            if energy_tier == 'critical':
                self.parent.dialogue_ui.add_dialogue("ralsei", "呜... 我真的好累好累... 几乎走不动了...", "sad")
                self.parent.dialogue_ui.show_dialogue()
                # 修复：原代码直接 self.parent.current_animation="idle"，绕过
                # change_animation 的冷却/优先级/施法(spell)/游戏硬拦截——若恰好处于
                # spell casting 或躲猫猫关键阶段会打断流程。改走受保护接口，
                # 被拦截时保持原动画不强行打断。
                try:
                    _spell_stage = getattr(self.parent, '_spell_stage', None)
                    _playing = getattr(self.parent, 'game_state', {}).get('is_playing', False)
                    if _spell_stage is None and not _playing:
                        self.parent.change_animation("idle", force=False)
                    # spell/游戏中：只记休息意图，不切动画（由主状态机自然处理）
                except Exception:
                    pass
                # 自动进入休息状态
                self.is_resting = True
            elif energy_tier == 'low':
                self.parent.dialogue_ui.add_dialogue("ralsei", "我有点累了... 能不能休息一下？", "sad")
                self.parent.dialogue_ui.show_dialogue()
            elif energy_tier == 'high' and self.is_resting:
                # 精力充足，结束休息
                self.parent.dialogue_ui.add_dialogue("ralsei", "哇！我感觉好多了！谢谢你让我休息！", "happy")
                self.parent.dialogue_ui.show_dialogue()
                self.is_resting = False
            self._prev_energy_tier = energy_tier

        # 检查饥饿状态
        hunger_tier = self._hunger_tier()
        if hunger_tier != self._prev_hunger_tier:
            if hunger_tier == 'critical':
                # 饥饿严重
                self.parent.dialogue_ui.add_dialogue("ralsei", "肚子好饿好饿... 我快饿死了...", "sad")
                self.parent.dialogue_ui.show_dialogue()
            elif hunger_tier == 'low':
                # 有点饿
                self.parent.dialogue_ui.add_dialogue("ralsei", "嗯... 我有点饿了... 有没有什么吃的？", "sad")
                self.parent.dialogue_ui.show_dialogue()
            elif hunger_tier == 'high' and self.is_eating:
                # 饥饿度充足，结束进食
                self.parent.dialogue_ui.add_dialogue("ralsei", "好吃！我已经吃饱了！谢谢你的食物！", "happy")
                self.parent.dialogue_ui.show_dialogue()
                self.is_eating = False
            self._prev_hunger_tier = hunger_tier
    
    def rest(self):
        # 开始休息
        if not self.is_resting:
            self.is_resting = True
            self.parent.dialogue_ui.add_dialogue("ralsei", "我要休息一下啦... 呼...", "normal")
            self.parent.dialogue_ui.show_dialogue()
            # 修复：不直接改 current_animation（绕过 change_animation 会破坏动画状态机），
            # 休息时停止移动，由主状态机自然切到 idle。
            try:
                self.parent.is_moving = False
            except Exception:
                pass
    
    def eat(self):
        # 开始进食
        if not self.is_eating:
            self.is_eating = True
            self.parent.dialogue_ui.add_dialogue("ralsei", "哇！有好吃的！我开动啦！", "happy")
            self.parent.dialogue_ui.show_dialogue()
            # 修复：同上，不直接改 current_animation。
            try:
                self.parent.is_moving = False
            except Exception:
                pass
        
    def set_resting(self, resting):
        # 设置休息状态
        self.is_resting = resting
        
    def set_eating(self, eating):
        # 设置进食状态
        self.is_eating = eating
        
    def get_energy(self):
        # 获取当前精力值
        return self.energy
        
    def get_hunger(self):
        # 获取当前饥饿值
        return self.hunger
        
    def get_energy_percentage(self):
        # 获取精力百分比
        return self.energy
        
    def get_hunger_percentage(self):
        # 获取饥饿百分比
        return self.hunger
        
    def get_status(self):
        # 获取当前状态描述
        energy_status = ""
        if self.energy < self.critical_energy_threshold:
            energy_status = "非常疲惫"
        elif self.energy < self.low_energy_threshold:
            energy_status = "有点累"
        else:
            energy_status = "精力充沛"
        
        hunger_status = ""
        if self.hunger < self.critical_hunger_threshold:
            hunger_status = "非常饥饿"
        elif self.hunger < self.low_hunger_threshold:
            hunger_status = "有点饿"
        else:
            hunger_status = "饱饱的"
        
        return {
            "energy": energy_status,
            "hunger": hunger_status,
            "energy_value": self.energy,
            "hunger_value": self.hunger,
        }
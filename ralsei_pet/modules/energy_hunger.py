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
        
    def check_status_changes(self):
        # 检查精力状态
        if self.energy < self.critical_energy_threshold:
            # 精力严重不足
            self.parent.dialogue_ui.add_dialogue("ralsei", "呜... 我真的好累好累... 几乎走不动了...", "sad")
            self.parent.dialogue_ui.show_dialogue()
            self.parent.current_animation = "idle"
            # 自动进入休息状态
            self.is_resting = True
        elif self.energy < self.low_energy_threshold:
            # 精力不足
            self.parent.dialogue_ui.add_dialogue("ralsei", "我有点累了... 能不能休息一下？", "sad")
            self.parent.dialogue_ui.show_dialogue()
        elif self.energy > 80 and self.is_resting:
            # 精力充足，结束休息
            self.parent.dialogue_ui.add_dialogue("ralsei", "哇！我感觉好多了！谢谢你让我休息！", "happy")
            self.parent.dialogue_ui.show_dialogue()
            self.is_resting = False
        
        # 检查饥饿状态
        if self.hunger < self.critical_hunger_threshold:
            # 饥饿严重
            self.parent.dialogue_ui.add_dialogue("ralsei", "肚子好饿好饿... 我快饿死了...", "sad")
            self.parent.dialogue_ui.show_dialogue()
        elif self.hunger < self.low_hunger_threshold:
            # 有点饿
            self.parent.dialogue_ui.add_dialogue("ralsei", "嗯... 我有点饿了... 有没有什么吃的？", "sad")
            self.parent.dialogue_ui.show_dialogue()
        elif self.hunger > 80 and self.is_eating:
            # 饥饿度充足，结束进食
            self.parent.dialogue_ui.add_dialogue("ralsei", "好吃！我已经吃饱了！谢谢你的食物！", "happy")
            self.parent.dialogue_ui.show_dialogue()
            self.is_eating = False
    
    def rest(self):
        # 开始休息
        if not self.is_resting:
            self.is_resting = True
            self.parent.dialogue_ui.add_dialogue("ralsei", "我要休息一下啦... 呼...", "normal")
            self.parent.dialogue_ui.show_dialogue()
            self.parent.current_animation = "idle"
    
    def eat(self):
        # 开始进食
        if not self.is_eating:
            self.is_eating = True
            self.parent.dialogue_ui.add_dialogue("ralsei", "哇！有好吃的！我开动啦！", "happy")
            self.parent.dialogue_ui.show_dialogue()
            self.parent.current_animation = "idle"
        
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
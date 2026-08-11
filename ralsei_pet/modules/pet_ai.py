import random
import time
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QPoint
import os

class PetAI:
    def __init__(self, parent):
        self.parent = parent
        self.state = "idle"  # idle, moving, interacting, playing, resting
        self.last_state_change = time.time()
        self.state_duration = 0
        
        # AI行为概率
        self.behavior_probabilities = {
            "move": 0.3,
            "interact": 0.2,
            "play": 0.2,
            "rest": 0.2,
            "idle": 0.1,
        }
        
        # 交互目标优先级
        self.interaction_priorities = {
            "user": 0.5,
            "folder": 0.3,
            "file": 0.1,
            "app": 0.1,
        }
        
        # 动作触发条件映射
        self.action_triggers = {
            # 基本动作
            "idle": self.trigger_idle,
            "walk_down": self.trigger_walk_down,
            "walk_left": self.trigger_walk_left,
            "walk_right": self.trigger_walk_right,
            "walk_up": self.trigger_walk_up,
            
            # 表情和情绪动作
            "laugh": self.trigger_laugh,
            "cry": self.trigger_cry,
            "surprised": self.trigger_surprised,
            "cower": self.trigger_cower,
            
            # 互动动作
            "wave": self.trigger_wave,
            "wave_start": self.trigger_wave_start,
            "hug": self.trigger_hug,
            "hug_stop": self.trigger_hug_stop,
            "nuzzle": self.trigger_nuzzle,
            "curtsy": self.trigger_curtsy,
            
            # 游戏和活动
            "dance": self.trigger_dance,
            "sing": self.trigger_sing,
            "roll": self.trigger_roll,
            "pose": self.trigger_pose,
            
            # 特殊动作
            "tea": self.trigger_tea,
            "look_up": self.trigger_look_up,
            "kneel_serious": self.trigger_kneel_serious,
            "kneel_cry": self.trigger_kneel_cry,
        }
        
        # 动作冷却时间
        self.action_cooldowns = {}
        
    # 动作触发条件方法
    def trigger_idle(self):
        # 当Ralsei没有移动或交互时触发
        return self.state == "idle"
    
    def trigger_walk_down(self):
        # 当Ralsei向下移动时触发
        return self.parent.target_pos.y() > self.parent.pos().y()
    
    def trigger_walk_left(self):
        # 当Ralsei向左移动时触发
        return self.parent.target_pos.x() < self.parent.pos().x()
    
    def trigger_walk_right(self):
        # 当Ralsei向右移动时触发
        return self.parent.target_pos.x() > self.parent.pos().x()
    
    def trigger_walk_up(self):
        # 当Ralsei向上移动时触发
        return self.parent.target_pos.y() < self.parent.pos().y()
    
    def trigger_laugh(self):
        # 当Ralsei开心时触发
        return random.random() < 0.1 and self.state in ["idle", "interact"]
    
    def trigger_cry(self):
        # 当Ralsei悲伤时触发
        energy = self.parent.energy_hunger.get_energy()
        hunger = self.parent.energy_hunger.get_hunger()
        return (energy < 20 or hunger < 20) and random.random() < 0.05
    
    def trigger_surprised(self):
        # 当Ralsei感到惊讶时触发
        return random.random() < 0.05
    
    def trigger_cower(self):
        # 当Ralsei感到害怕时触发
        return random.random() < 0.03
    
    def trigger_wave(self):
        # 当Ralsei打招呼或告别时触发
        return random.random() < 0.08 and self.state == "interact"
    
    def trigger_wave_start(self):
        # 当Ralsei准备挥手时触发
        return random.random() < 0.05
    
    def trigger_hug(self):
        # 当Ralsei想要拥抱时触发
        return random.random() < 0.03 and self.state == "interact"
    
    def trigger_hug_stop(self):
        # 当Ralsei停止拥抱时触发
        return self.parent.current_animation == "hug" and random.random() < 0.3
    
    def trigger_nuzzle(self):
        # 当Ralsei想要蹭蹭时触发
        return random.random() < 0.04 and self.state == "interact"
    
    def trigger_curtsy(self):
        # 当Ralsei想要行屈膝礼时触发
        return random.random() < 0.05 and self.state == "interact"
    
    def trigger_dance(self):
        # 当Ralsei想要跳舞时触发
        return random.random() < 0.1 and self.state in ["idle", "play"]
    
    def trigger_sing(self):
        # 当Ralsei想要唱歌时触发
        return random.random() < 0.08 and self.state in ["idle", "play"]
    
    def trigger_roll(self):
        # 当Ralsei想要滚动时触发
        return random.random() < 0.05 and self.state == "play"
    
    def trigger_pose(self):
        # 当Ralsei想要摆姿势时触发
        return random.random() < 0.06 and self.state == "idle"
    
    def trigger_tea(self):
        # 当Ralsei想要喝茶时触发
        return random.random() < 0.04 and self.state == "idle"
    
    def trigger_look_up(self):
        # 当Ralsei想要向上看时触发
        return random.random() < 0.07
    
    def trigger_kneel_serious(self):
        # 当Ralsei想要严肃地跪下时触发
        return random.random() < 0.03 and self.state == "interact"
    
    def trigger_kneel_cry(self):
        # 当Ralsei想要跪下哭泣时触发
        energy = self.parent.energy_hunger.get_energy()
        return energy < 15 and random.random() < 0.02
    
    def update_state(self):
        # 更新AI状态
        current_time = time.time()
        self.state_duration = current_time - self.last_state_change
        
        # 获取当前状态数据
        # 直接访问属性，减少方法调用开销
        energy = self.parent.energy_hunger.energy
        hunger = self.parent.energy_hunger.hunger
        current_emotion, emotion_value = self.parent.emotion_system.get_current_emotion()
        current_animation = self.parent.current_animation
        
        # 基于状态数据动态调整行为概率
        dynamic_probabilities = self.adjust_probabilities_based_on_state(energy, hunger, (current_emotion, emotion_value))
        
        # 更智能的状态转换逻辑
        # 1. 考虑当前动画状态：如果正在播放特定动画，延长当前状态持续时间
        animation_state_map = {
            "dance": "play",
            "sing": "play",
            "laugh": "interact",
            "wave": "interact",
            "hug": "interact",
            "nuzzle": "interact",
            "curtsy": "interact",
            "look_up": "rest",
            "pose": "rest",
            "tea": "rest"
        }
        
        if current_animation in animation_state_map:
            # 正在播放特定动画，确保状态匹配
            expected_state = animation_state_map[current_animation]
            if self.state != expected_state:
                # 调整状态以匹配当前动画
                self.state = expected_state
                self.last_state_change = current_time
                self.state_duration = 0
        
        # 2. 根据当前情绪调整状态持续时间
        emotion_duration_factor = {
            "happy": 1.5,  # 开心时延长状态持续时间
            "excited": 1.8,  # 兴奋时更长
            "sad": 0.8,  # 悲伤时缩短状态持续时间
            "tired": 0.6,  # 疲劳时缩短
            "neutral": 1.0  # 正常
        }
        
        duration_factor = emotion_duration_factor.get(current_emotion, 1.0)
        adjusted_duration = random.uniform(20, 40) * duration_factor
        
        # 3. 根据当前状态和时间决定下一个状态
        if self.state_duration > adjusted_duration:
            # 确保状态转换更合理
            # 避免频繁在相似状态间切换
            next_state = None
            
            # 优化随机选择逻辑，减少重复计算
            rand_val = random.random()
            cumulative_prob = 0.0
            
            if self.state in ["move", "play"]:
                # 活动状态后更容易切换到休息状态
                if rand_val < 0.4:
                    next_state = "rest"
                else:
                    # 简化随机选择，减少计算成本
                    for state, prob in dynamic_probabilities.items():
                        cumulative_prob += prob
                        if rand_val <= cumulative_prob:
                            next_state = state
                            break
            elif self.state in ["rest", "idle"]:
                # 休息状态后更容易切换到活动状态
                if rand_val < 0.5:
                    next_state = random.choice(["move", "interact", "play"])
                else:
                    # 简化随机选择，减少计算成本
                    for state, prob in dynamic_probabilities.items():
                        cumulative_prob += prob
                        if rand_val <= cumulative_prob:
                            next_state = state
                            break
            else:
                # 其他状态正常随机切换
                # 简化随机选择，减少计算成本
                for state, prob in dynamic_probabilities.items():
                    cumulative_prob += prob
                    if rand_val <= cumulative_prob:
                        next_state = state
                        break
            
            # 避免重复切换到相同状态
            if next_state == self.state or next_state is None:
                # 如果随机到相同状态或未选择到状态，尝试重新选择
                available_states = [s for s in dynamic_probabilities.keys() if s != self.state]
                if available_states:
                    next_state = random.choice(available_states)
                else:
                    next_state = "idle"  # 默认状态
            
            self.state = next_state
            self.last_state_change = current_time
            self.state_duration = 0
            
            # 执行状态转换动作
            self.execute_state_action()
        
        # 优化动作触发检查频率，每500ms检查一次
        if not hasattr(self, '_last_action_check') or current_time - self._last_action_check >= 0.5:
            self.check_action_triggers()
            self._last_action_check = current_time
        
        # 优化特殊事件检查频率，每1000ms检查一次
        if not hasattr(self, '_last_special_check') or current_time - self._last_special_check >= 1.0:
            self.check_special_events()
            self._last_special_check = current_time
    
    def adjust_probabilities_based_on_state(self, energy, hunger, emotion):
        # 基于当前状态动态调整行为概率
        dynamic_probs = self.behavior_probabilities.copy()
        
        # 根据精力和饥饿度调整
        if energy < 30:
            # 精力不足，增加休息概率，减少活动概率
            dynamic_probs["rest"] += 0.3
            dynamic_probs["move"] -= 0.1
            dynamic_probs["play"] -= 0.1
            dynamic_probs["interact"] -= 0.1
        elif hunger < 30:
            # 饥饿，增加寻找食物相关行为
            dynamic_probs["interact"] += 0.2
            dynamic_probs["rest"] -= 0.1
        else:
            # 状态良好，增加活动概率
            dynamic_probs["move"] += 0.1
            dynamic_probs["play"] += 0.1
        
        # 根据情绪调整
        emotion_type, emotion_value = emotion
        if emotion_type == "happy" and emotion_value > 0.5:
            # 很高兴，增加玩耍和互动概率
            dynamic_probs["play"] += 0.2
            dynamic_probs["interact"] += 0.1
        elif emotion_type == "sad" and emotion_value < -0.5:
            # 难过，增加休息和互动概率
            dynamic_probs["rest"] += 0.2
            dynamic_probs["interact"] += 0.1
        elif emotion_type == "excited" and emotion_value > 0.7:
            # 兴奋，增加活动和玩耍概率
            dynamic_probs["move"] += 0.2
            dynamic_probs["play"] += 0.2
        
        # 确保概率总和不超过1
        total = sum(dynamic_probs.values())
        for key in dynamic_probs:
            dynamic_probs[key] = max(0, min(1, dynamic_probs[key] / total))
        
        return dynamic_probs
    
    def check_special_events(self):
        # 检查特殊事件，如用户操作、时间事件等
        current_hour = time.localtime().tm_hour
        
        # 时间相关事件
        if 7 <= current_hour < 9:
            # 早上，可能会打招呼
            if random.random() < 0.05:
                self.parent.dialogue_ui.add_dialogue("ralsei", "早上好！今天看起来是个美好的一天！", "happy")
                self.parent.dialogue_ui.show_dialogue()
        elif 12 <= current_hour < 14:
            # 中午，可能会提到吃饭
            if random.random() < 0.05:
                self.parent.dialogue_ui.add_dialogue("ralsei", "中午了呢，你有没有好好吃饭呀？", "neutral")
                self.parent.dialogue_ui.show_dialogue()
        elif 18 <= current_hour < 20:
            # 晚上，可能会提醒休息
            if random.random() < 0.05:
                self.parent.dialogue_ui.add_dialogue("ralsei", "晚上好！今天过得怎么样呀？", "happy")
                self.parent.dialogue_ui.show_dialogue()
        elif 22 <= current_hour or current_hour < 6:
            # 深夜，可能会提醒睡觉
            if random.random() < 0.05:
                self.parent.dialogue_ui.add_dialogue("ralsei", "已经这么晚了，要注意休息哦！", "concerned")
                self.parent.dialogue_ui.show_dialogue()
    
    def check_action_triggers(self):
        # 检查所有动作的触发条件
        
        # 获取当前状态数据，用于更智能的动作选择
        energy = self.parent.energy_hunger.get_energy()
        hunger = self.parent.energy_hunger.get_hunger()
        current_emotion, emotion_value = self.parent.emotion_system.get_current_emotion()
        current_animation = self.parent.current_animation
        
        # 根据当前状态过滤合适的动作
        # 移动时优先考虑移动相关动作
        if self.state == "move":
            # 移动状态下，只考虑移动相关动作
            move_actions = ["walk_down", "walk_left", "walk_right", "walk_up", "run_down", "run_left", "run_right", "run_up"]
            actions_to_check = [(a, f) for a, f in self.action_triggers.items() if a in move_actions]
        # 休息时优先考虑休息相关动作
        elif self.state == "rest":
            rest_actions = ["idle", "look_up", "pose", "tea"]
            actions_to_check = [(a, f) for a, f in self.action_triggers.items() if a in rest_actions]
        # 互动时优先考虑互动相关动作
        elif self.state == "interact":
            interact_actions = ["laugh", "wave", "hug", "nuzzle", "curtsy"]
            actions_to_check = [(a, f) for a, f in self.action_triggers.items() if a in interact_actions]
        # 玩耍时优先考虑玩耍相关动作
        elif self.state == "play":
            play_actions = ["dance", "sing", "roll"]
            actions_to_check = [(a, f) for a, f in self.action_triggers.items() if a in play_actions]
        # 空闲时考虑所有动作，但排除移动动作
        elif self.state == "idle":
            idle_actions = [a for a, f in self.action_triggers.items() if a not in ["walk_down", "walk_left", "walk_right", "walk_up", "run_down", "run_left", "run_right", "run_up"]]
            actions_to_check = [(a, f) for a, f in self.action_triggers.items() if a in idle_actions]
        # 默认检查所有动作，但按优先级排序
        else:
            actions_to_check = list(self.action_triggers.items())
        
        # 打乱动作顺序，增加随机性
        random.shuffle(actions_to_check)
        
        # 检查触发条件
        for action, trigger_func in actions_to_check:
            # 检查冷却时间
            if action in self.action_cooldowns:
                if time.time() < self.action_cooldowns[action]:
                    continue
            
            # 检查触发条件
            if trigger_func():
                # 额外的逻辑检查，确保动作更合理
                # 1. 情绪匹配：确保动作与当前情绪匹配
                emotion_action_match = {
                    "happy": ["laugh", "dance", "sing", "wave", "hug", "nuzzle"],
                    "sad": ["cry", "cower"],
                    "excited": ["dance", "sing", "laugh"],
                    "tired": ["idle", "look_up", "pose"],
                    "neutral": ["idle", "look_up", "pose", "wave"]
                }
                
                # 检查情绪匹配，如果不匹配则跳过
                if current_emotion in emotion_action_match:
                    if action not in emotion_action_match[current_emotion] and action not in ["idle", "walk_down", "walk_left", "walk_right", "walk_up"]:
                        continue
                
                # 2. 状态匹配：确保动作与当前状态匹配
                if action in ["walk_down", "walk_left", "walk_right", "walk_up", "run_down", "run_left", "run_right", "run_up"] and self.state != "move":
                    # 非移动状态下不应该触发移动动作
                    continue
                
                # 3. 避免动作冲突：确保不重复触发相同动作
                if action == current_animation:
                    continue
                
                # 触发动作
                self.trigger_action(action)
                # 设置冷却时间，根据动作类型调整冷却时间
                if action in ["idle", "walk_down", "walk_left", "walk_right", "walk_up"]:
                    # 基础动作冷却时间较短
                    cooldown = random.uniform(2, 5)
                elif action in ["laugh", "wave", "look_up", "pose"]:
                    # 表情动作冷却时间中等
                    cooldown = random.uniform(5, 10)
                else:
                    # 复杂动作冷却时间较长
                    cooldown = random.uniform(10, 20)
                
                self.action_cooldowns[action] = time.time() + cooldown
                break
    
    def trigger_action(self, action):
        # 触发指定动作
        print(f"触发动作: {action}")
        self.parent.change_animation(action)
    
    def execute_state_action(self):
        # 执行当前状态对应的动作
        if self.state == "move":
            self.move_to_random_location()
        elif self.state == "interact":
            self.interact_with_something()
        elif self.state == "play":
            self.play_something()
        elif self.state == "rest":
            self.rest()
        elif self.state == "idle":
            self.idle()
    
    def move_to_random_location(self):
        # 移动到随机位置，改进运动逻辑，更符合Ralsei的性格
        
        # 获取屏幕几何信息
        screen_geometry = QApplication.desktop().availableGeometry()
        max_x = screen_geometry.width() - 150
        max_y = screen_geometry.height() - 150
        
        # 随机选择目标位置
        target_x = random.randint(50, max_x)
        target_y = random.randint(50, max_y)
        
        # 设置目标位置
        self.parent.target_pos = QPoint(target_x, target_y)
        
        # 随机调整速度，模拟Ralsei有时候走得快有时候走得慢
        # 使用新的速度范围，确保移动更流畅
        self.parent.speed = random.uniform(3.0, 8.0)
    
    def interact_with_something(self):
        # 与某物交互，改进交互逻辑
        
        # 随机选择交互目标
        targets = list(self.interaction_priorities.keys())
        probabilities = list(self.interaction_priorities.values())
        target = random.choices(targets, weights=probabilities, k=1)[0]
        
        if target == "user":
            # 与用户交互
            if self.parent.dialogue_system.should_initiate_conversation():
                message = self.parent.dialogue_system.initiate_conversation()
                self.parent.dialogue_ui.add_dialogue("ralsei", message, "happy")
                self.parent.dialogue_ui.show_dialogue()
        elif target == "folder":
            # 与文件夹交互
            folders = self.parent.desktop_interaction.get_desktop_folders()
            if folders:
                # 随机选择一个文件夹
                folder = random.choice(folders)
                
                # 向文件夹移动
                self.parent.target_pos = QPoint(folder['x'], folder['y'])
                self.parent.is_moving = True
                
                # 显示交互对话
                self.parent.dialogue_ui.add_dialogue("ralsei", f"这是什么文件夹呀？{folder['name']}... 看起来很有趣！", "curious")
                self.parent.dialogue_ui.show_dialogue()
        elif target == "file":
            # 与文件交互
            files = self.parent.desktop_interaction.get_desktop_files()
            if files:
                # 随机选择一个文件
                file = random.choice(files)
                
                # 向文件移动
                self.parent.target_pos = QPoint(file['x'], file['y'])
                self.parent.is_moving = True
                
                # 显示交互对话
                self.parent.dialogue_ui.add_dialogue("ralsei", f"这是什么文件呀？{file['name']}... 我可以看看吗？", "curious")
                self.parent.dialogue_ui.show_dialogue()
        elif target == "app":
            # 与应用程序交互
            self.parent.dialogue_ui.add_dialogue("ralsei", "那个图标是什么呀？看起来很好玩！", "curious")
            self.parent.dialogue_ui.show_dialogue()
    
    def play_something(self):
        # 玩一些东西，改进游戏逻辑
        games = ["hide_and_seek", "puzzle", "dance", "sing", "chase_cursor"]
        game = random.choice(games)
        
        if game == "dance":
            self.parent.change_animation("dance", force=True)
            self.parent.dialogue_ui.add_dialogue("ralsei", "来跳舞吧！转圈圈~ 嘻嘻！", "happy")
            self.parent.dialogue_ui.show_dialogue()
        elif game == "sing":
            self.parent.change_animation("sing", force=True)
            self.parent.dialogue_ui.add_dialogue("ralsei", "啦啦啦~ 唱首歌给你听！", "happy")
            self.parent.dialogue_ui.show_dialogue()
        elif game == "chase_cursor":
            # 追逐鼠标游戏
            self.parent.dialogue_ui.add_dialogue("ralsei", "我来追你的鼠标啦！快动一动！", "excited")
            self.parent.dialogue_ui.show_dialogue()
            # 这里可以添加追逐鼠标的逻辑
        elif game == "hide_and_seek":
            self.parent.dialogue_ui.add_dialogue("ralsei", "我们来玩躲猫猫吧！我先藏起来~", "happy")
            self.parent.dialogue_ui.show_dialogue()
        elif game == "puzzle":
            self.parent.dialogue_ui.add_dialogue("ralsei", "我们来玩猜谜游戏吧！我出个题目给你猜！", "happy")
            self.parent.dialogue_ui.show_dialogue()
    
    def rest(self):
        # 休息
        self.parent.change_animation("idle", force=True)
    
    def idle(self):
        # 空闲状态
        self.parent.change_animation("idle")
    
    def react_to_event(self, event_type, event_data):
        # 对事件做出反应
        if event_type == "user_clicked":
            # 用户点击了Ralsei
            self.parent.dialogue_ui.add_dialogue("ralsei", "哎呀！你吓到我了！", "surprised")
            self.parent.dialogue_ui.show_dialogue()
            # 触发惊讶动作
            self.trigger_action("surprised")
        elif event_type == "file_dragged":
            # 用户拖动了文件
            self.parent.current_animation = "walk_right"  # 追逐文件
        elif event_type == "weather_changed":
            # 天气变化
            weather_response = self.parent.weather_system.get_weather_response()
            self.parent.dialogue_ui.add_dialogue("ralsei", weather_response["dialogue"], weather_response["mood"])
            self.parent.current_animation = weather_response["animation"]
        elif event_type == "ppt_action":
            # PPT操作事件
            action = event_data.get("action")
            ppt_path = event_data.get("path")
            if action and ppt_path:
                result = self.parent.desktop_interaction.ppt_control(action, ppt_path)
                if result:
                    self.parent.dialogue_ui.add_dialogue("ralsei", f"PPT操作 '{action}' 执行成功！", "happy")
                else:
                    self.parent.dialogue_ui.add_dialogue("ralsei", f"PPT操作 '{action}' 执行失败了...", "sad")
                self.parent.dialogue_ui.show_dialogue()
        elif event_type == "excel_action":
            # Excel操作事件
            action = event_data.get("action")
            excel_path = event_data.get("path")
            sheet_name = event_data.get("sheet")
            cell_range = event_data.get("range")
            data = event_data.get("data")
            if action and excel_path:
                result = self.parent.desktop_interaction.excel_control(action, excel_path, sheet_name, cell_range, data)
                if result:
                    self.parent.dialogue_ui.add_dialogue("ralsei", f"Excel操作 '{action}' 执行成功！", "happy")
                else:
                    self.parent.dialogue_ui.add_dialogue("ralsei", f"Excel操作 '{action}' 执行失败了...", "sad")
                self.parent.dialogue_ui.show_dialogue()


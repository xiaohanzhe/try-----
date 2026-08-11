import time
import json
import os

class MemorySystem:
    def __init__(self, parent):
        self.parent = parent
        
        # 记忆存储路径
        self.memory_file = os.path.join(os.path.dirname(__file__), '..', 'memory.json')
        
        # 短期记忆
        self.short_term_memory = []
        self.max_short_term_memory = 100  # 增加短期记忆数量
        
        # 扩展长期记忆
        self.long_term_memory = {
            'user_preferences': {},         # 用户偏好
            'important_dates': {},          # 重要日期
            'interaction_history': [],      # 交互历史
            'favorite_topics': {},          # 最喜欢的主题
            'disliked_topics': {},          # 不喜欢的主题
            'skill_levels': {},             # 技能等级
            'behavior_patterns': {},        # 行为模式
            'emotional_responses': {},      # 情绪反应模式
            'environmental_preferences': {}, # 环境偏好
            'relationship_history': []       # 关系历史
        }
        
        # 经验系统
        self.experience = 0
        self.level = 1
        self.experience_threshold = 100  # 升级所需经验值
        
        # 学习系统
        self.learning_rate = 0.3  # 学习率
        self.memory_strength = {}  # 记忆强度
        
        # 初始化时加载记忆
        self.load_memory()
    
    def add_memory(self, memory_type, content, is_short_term=True):
        """添加记忆，根据隐私设置控制是否存储"""
        # 检查是否启用活动跟踪
        if hasattr(self.parent, 'config_manager') and not self.parent.config_manager.is_activity_tracking_enabled():
            return
            
        memory = {
            'timestamp': time.time(),
            'type': memory_type,
            'content': content
        }
        
        if is_short_term:
            # 添加到短期记忆
            self.short_term_memory.append(memory)
            # 限制短期记忆数量
            if len(self.short_term_memory) > self.max_short_term_memory:
                self.short_term_memory.pop(0)
        else:
            # 添加到长期记忆的交互历史
            self.long_term_memory['interaction_history'].append(memory)
            # 保存长期记忆
            self.save_memory()
    
    def get_recent_memory(self, memory_type=None, limit=10):
        """获取最近的记忆"""
        if memory_type:
            # 过滤特定类型的记忆
            filtered_memory = [m for m in self.short_term_memory if m['type'] == memory_type]
        else:
            filtered_memory = self.short_term_memory
        
        # 返回最近的limit条记忆
        return filtered_memory[-limit:]
    
    def query_memory(self, query_params, memory_type='short_term'):
        """高级记忆查询功能，支持按多种条件检索记忆"""
        """
        支持的查询参数:
        - memory_type: 'short_term' 或 'long_term'
        - memory_types: 记忆类型列表，如 ['user_interaction', 'dialogue']
        - keywords: 关键词列表，如 ['游戏', '音乐']
        - time_range: 时间范围，如 (start_time, end_time)
        - emotion: 相关情感，如 'happy', 'sad'
        - limit: 返回结果数量限制
        """
        memories = self.short_term_memory if memory_type == 'short_term' else self.long_term_memory['interaction_history']
        
        filtered_memories = []
        
        # 应用过滤条件
        for memory in memories:
            match = True
            
            # 按记忆类型过滤
            if 'memory_types' in query_params:
                if memory['type'] not in query_params['memory_types']:
                    match = False
            
            # 按关键词过滤
            if match and 'keywords' in query_params:
                content = memory['content'].lower()
                keyword_match = False
                for keyword in query_params['keywords']:
                    if keyword.lower() in content:
                        keyword_match = True
                        break
                if not keyword_match:
                    match = False
            
            # 按时间范围过滤
            if match and 'time_range' in query_params:
                start_time, end_time = query_params['time_range']
                if not (start_time <= memory['timestamp'] <= end_time):
                    match = False
            
            if match:
                filtered_memories.append(memory)
        
        # 按时间排序，最新的在前
        filtered_memories.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # 应用限制
        if 'limit' in query_params:
            filtered_memories = filtered_memories[:query_params['limit']]
        
        return filtered_memories
    
    def get_associated_memories(self, memory_id, memory_type='short_term'):
        """获取与特定记忆相关的联想记忆"""
        memories = self.short_term_memory if memory_type == 'short_term' else self.long_term_memory['interaction_history']
        
        # 找到目标记忆
        target_memory = None
        for memory in memories:
            if 'id' in memory and memory['id'] == memory_id:
                target_memory = memory
                break
        
        if not target_memory:
            return []
        
        # 提取关键词
        content = target_memory['content'].lower()
        keywords = ['游戏', '音乐', '电影', '书籍', '食物', '天气', '工作', '学习', '蛋糕', '甜点', 'deltarune', 'undertale']
        extracted_keywords = []
        for keyword in keywords:
            if keyword in content:
                extracted_keywords.append(keyword)
        
        if not extracted_keywords:
            return []
        
        # 查找相关记忆
        associated_memories = []
        for memory in memories:
            if memory == target_memory:
                continue
            
            mem_content = memory['content'].lower()
            for keyword in extracted_keywords:
                if keyword in mem_content:
                    associated_memories.append(memory)
                    break
        
        return associated_memories[:5]  # 限制返回5个相关记忆
    
    def learn_user_preference(self, preference_name, preference_value):
        """学习用户偏好"""
        self.long_term_memory['user_preferences'][preference_name] = preference_value
        self.save_memory()
    
    def get_user_preference(self, preference_name, default=None):
        """获取用户偏好"""
        return self.long_term_memory['user_preferences'].get(preference_name, default)
    
    def add_important_date(self, date_name, date_value):
        """添加重要日期"""
        self.long_term_memory['important_dates'][date_name] = date_value
        self.save_memory()
    
    def get_important_date(self, date_name):
        """获取重要日期"""
        return self.long_term_memory['important_dates'].get(date_name, None)
    
    def add_experience(self, amount):
        """增加经验值"""
        self.experience += amount
        # 检查是否升级
        self.check_level_up()
    
    def check_level_up(self):
        """检查是否升级"""
        # 动态升级逻辑：每级所需经验递增
        new_level = 1
        required_experience = 100
        
        while self.experience >= required_experience:
            new_level += 1
            # 每级所需经验增加20%
            required_experience += int(required_experience * 0.2)
        
        if new_level > self.level:
            old_level = self.level
            self.level = new_level
            self.experience_threshold = required_experience
            
            # 升级时学习新技能
            self.learn_new_skill()
            
            # 触发升级事件
            self.parent.pet_ai.trigger_event('level_up', {'new_level': self.level, 'old_level': old_level})
            
            # 保存记忆
            self.save_memory()
    
    def load_memory(self):
        """加载记忆"""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.long_term_memory = data.get('long_term_memory', self.long_term_memory)
                    self.experience = data.get('experience', self.experience)
                    self.level = data.get('level', self.level)
                    print(f"成功加载记忆: {self.memory_file}")
        except Exception as e:
            print(f"加载记忆失败: {e}")
            # 使用默认记忆
            self.long_term_memory = {
                'user_preferences': {},
                'important_dates': {},
                'interaction_history': []
            }
            self.experience = 0
            self.level = 1
    
    def save_memory(self):
        """保存记忆"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            
            data = {
                'long_term_memory': self.long_term_memory,
                'experience': self.experience,
                'level': self.level
            }
            
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存记忆失败: {e}")
    
    def get_experience(self):
        """获取当前经验值"""
        return self.experience
    
    def get_level(self):
        """获取当前等级"""
        return self.level
    
    def update(self):
        """定期更新记忆"""
        # 整理和优化记忆
        self._organize_memories()
        # 提取重要记忆到长期记忆
        self._extract_important_memories()
        # 学习用户偏好
        self._learn_user_preferences()
    
    def _organize_memories(self):
        """整理记忆，去除冗余和不重要的记忆，优化记忆组织"""
        # 统计记忆类型分布
        memory_types = {}
        for memory in self.short_term_memory:
            mem_type = memory['type']
            memory_types[mem_type] = memory_types.get(mem_type, 0) + 1
        
        # 移除频率过低的记忆类型
        for mem_type, count in list(memory_types.items()):
            if count < 2:  # 如果某类记忆出现次数少于2次，视为不重要
                self.short_term_memory = [m for m in self.short_term_memory if m['type'] != mem_type]
        
        # 按时间排序，保留最新的记忆
        self.short_term_memory.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # 限制短期记忆数量，确保性能
        if len(self.short_term_memory) > self.max_short_term_memory:
            self.short_term_memory = self.short_term_memory[:self.max_short_term_memory]
    
    def _extract_important_memories(self):
        """将重要的短期记忆提取到长期记忆"""
        important_types = ['user_preferences', 'important_dates', 'completed_task', 'level_up', 'evolution', 'achievement_unlocked']
        
        for memory in self.short_term_memory:
            if memory['type'] in important_types and memory not in self.long_term_memory['interaction_history']:
                self.long_term_memory['interaction_history'].append(memory)
                # 保存长期记忆
                self.save_memory()
    
    def _learn_user_preferences(self):
        """从交互历史中学习用户偏好，增强学习能力"""
        # 统计用户提到的主题频率
        topic_counts = {}
        
        # 扩展关键词列表
        keywords = ['游戏', '音乐', '电影', '书籍', '食物', '天气', '工作', '学习', '蛋糕', '甜点', 'deltarune', 'undertale', 
                   '动漫', '编程', '旅行', '运动', '宠物', '咖啡', '茶', '阅读', '绘画', '摄影', '编程', '科学', '历史', 
                   '数学', '英语', '日语', '韩语', '烹饪', '健身', '音乐', '舞蹈', '书法', '手工', '游戏开发', '设计', 
                   '动画制作', '视频编辑', '音频制作', '3D建模', '写作', '诗歌', '小说', '散文', '漫画', '插画', '游戏设计']
        
        # 从多种记忆类型中学习
        for memory in self.short_term_memory:
            if memory['type'] in ['user_interaction', 'dialogue', 'search_query', 'file_created', 'file_opened']:
                content = memory['content'].lower()
                for keyword in keywords:
                    if keyword in content:
                        topic_counts[keyword] = topic_counts.get(keyword, 0) + 1
        
        # 将高频主题保存为用户偏好
        for topic, count in topic_counts.items():
            if count >= 2:  # 降低阈值，更容易学习新偏好
                # 考虑记忆强度，更频繁提到的主题权重更高
                current_value = self.long_term_memory['user_preferences'].get(f'interest_{topic}', 0)
                new_value = current_value + (count * self.learning_rate)
                self.learn_user_preference(f'interest_{topic}', new_value)
    
    def get_user_preferences_summary(self):
        """获取用户偏好摘要"""
        preferences = []
        for pref_name, pref_value in self.long_term_memory['user_preferences'].items():
            if pref_name.startswith('interest_'):
                topic = pref_name.replace('interest_', '')
                preferences.append((topic, pref_value))
        
        # 按偏好程度排序
        preferences.sort(key=lambda x: x[1], reverse=True)
        return preferences
    
    def remember_user_behavior(self, behavior_type, duration=0):
        """记录用户行为模式"""
        memory = {
            'timestamp': time.time(),
            'type': 'user_behavior',
            'content': {
                'behavior_type': behavior_type,
                'duration': duration
            }
        }
        self.add_memory('user_behavior', memory, is_short_term=True)
    
    def get_user_behavior_patterns(self):
        """获取用户行为模式"""
        behavior_patterns = {}
        for memory in self.short_term_memory + self.long_term_memory['interaction_history']:
            if memory['type'] == 'user_behavior':
                behavior_type = memory['content']['behavior_type']
                duration = memory['content']['duration']
                behavior_patterns[behavior_type] = {
                    'count': behavior_patterns.get(behavior_type, {}).get('count', 0) + 1,
                    'total_duration': behavior_patterns.get(behavior_type, {}).get('total_duration', 0) + duration
                }
        return behavior_patterns
    
    def learn_new_skill(self):
        """学习新技能"""
        # 可用技能列表，根据等级解锁
        available_skills = {
            2: ['small_talk', 'weather_talk', 'simple_games'],
            3: ['story_telling', 'music_recommendation', 'movie_recommendation'],
            4: ['work_assistance', 'creative_writing', 'problem_solving'],
            5: ['emotional_support', 'advanced_games', 'technical_assistance'],
            6: ['leadership', 'teamwork', 'mentoring'],
            7: ['innovation', 'strategic_thinking', 'resource_management'],
            8: ['telepathy', 'time_management', 'multitasking'],
            9: ['wisdom', 'inspiration', 'enlightenment'],
            10: ['omnipotence', 'omniscience', 'omnipresence']
        }
        
        # 获取当前等级可学习的技能
        level_skills = available_skills.get(self.level, [])
        
        # 过滤掉已学习的技能
        learned_skills = list(self.long_term_memory['skill_levels'].keys())
        new_skills = [skill for skill in level_skills if skill not in learned_skills]
        
        if new_skills:
            # 随机选择一个新技能学习
            import random
            new_skill = random.choice(new_skills)
            self.long_term_memory['skill_levels'][new_skill] = 1
            
            # 保存记忆
            self.save_memory()
            
            print(f"Ralsei学习了新技能: {new_skill}！")
    
    def improve_skill(self, skill_name, amount=1):
        """提升技能等级"""
        if skill_name in self.long_term_memory['skill_levels']:
            self.long_term_memory['skill_levels'][skill_name] += amount
        else:
            self.long_term_memory['skill_levels'][skill_name] = 1
        
        # 保存记忆
        self.save_memory()
    
    def get_skill_level(self, skill_name):
        """获取技能等级"""
        return self.long_term_memory['skill_levels'].get(skill_name, 0)
    
    def has_skill(self, skill_name):
        """检查是否拥有某个技能"""
        return skill_name in self.long_term_memory['skill_levels']
    
    def update_memory_strength(self, memory_type, strength_change):
        """更新记忆强度"""
        current_strength = self.memory_strength.get(memory_type, 50)
        new_strength = max(0, min(100, current_strength + strength_change))
        self.memory_strength[memory_type] = new_strength
    
    def get_memory_strength(self, memory_type):
        """获取记忆强度"""
        return self.memory_strength.get(memory_type, 50)
    
    def learn_from_experience(self, experience_type, outcome):
        """从经验中学习，增强学习能力"""
        # 根据经验结果调整学习
        if outcome == 'success':
            # 成功经验，增强相关技能和记忆强度
            self.update_memory_strength(experience_type, 10)
            if experience_type in self.long_term_memory['skill_levels']:
                self.improve_skill(experience_type, 2)
            # 记录成功经验
            self.add_memory('success_experience', f'{experience_type}: {outcome}', is_short_term=True)
        elif outcome == 'failure':
            # 失败经验，增强学习率和记忆强度
            self.update_memory_strength(experience_type, -5)
            self.learning_rate += 0.05
            # 记录失败经验，便于后续分析
            self.add_memory('failure_experience', f'{experience_type}: {outcome}', is_short_term=True)
        elif outcome == 'neutral':
            # 中性经验，轻微增强记忆强度
            self.update_memory_strength(experience_type, 2)
        
        # 保存记忆
        self.save_memory()
    
    def integrate_knowledge(self):
        """整合知识，从记忆中提取规律和模式"""
        """
        知识整合功能，从记忆中提取有用的规律和模式:
        - 分析用户行为模式
        - 识别情感触发因素
        - 提取有用的知识和经验
        """
        # 分析用户行为模式
        behavior_patterns = {}
        for memory in self.long_term_memory['interaction_history']:
            if memory['type'] == 'user_interaction':
                content = memory['content'].lower()
                # 统计行为模式
                if '早上好' in content or '早安' in content:
                    behavior_patterns['morning_greeting'] = behavior_patterns.get('morning_greeting', 0) + 1
                if '晚上好' in content or '晚安' in content:
                    behavior_patterns['evening_greeting'] = behavior_patterns.get('evening_greeting', 0) + 1
                if '谢谢' in content or '感谢' in content:
                    behavior_patterns['gratitude'] = behavior_patterns.get('gratitude', 0) + 1
        
        # 更新行为模式
        self.long_term_memory['behavior_patterns'] = behavior_patterns
        
        # 分析情感触发因素
        emotional_triggers = {}
        for memory in self.long_term_memory['interaction_history']:
            if 'emotion' in memory:
                emotion = memory['emotion']
                if emotion not in emotional_triggers:
                    emotional_triggers[emotion] = []
                emotional_triggers[emotion].append(memory['content'])
        
        # 更新情感反应模式
        self.long_term_memory['emotional_responses'] = emotional_triggers
        
        # 保存整合后的知识
        self.save_memory()
    
    def get_knowledge_summary(self):
        """获取知识摘要，整合记忆中的关键信息"""
        summary = {
            'user_preferences': self.get_user_preferences_summary(),
            'behavior_patterns': self.long_term_memory['behavior_patterns'],
            'skill_levels': self.long_term_memory['skill_levels'],
            'experience': self.experience,
            'level': self.level
        }
        return summary
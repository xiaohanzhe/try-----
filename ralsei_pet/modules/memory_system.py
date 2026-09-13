import time
import json
import os

try:
    from logger_utils import get_logger
    _log = get_logger(__name__)
except ImportError:  # 模块外独立导入时的降级
    import logging
    _log = logging.getLogger(__name__)

class MemorySystem:
    def __init__(self, parent):
        self.parent = parent
        
        # 记忆存储路径
        self.memory_file = os.path.join(os.path.dirname(__file__), '..', 'memory.json')
        
        # 短期记忆
        self.short_term_memory = []
        self.max_short_term_memory = 100  # 增加短期记忆数量
        self.MAX_LONG_TERM_INTERACTIONS = 500  # 长期记忆交互历史上限
        
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
            # 限制长期记忆交互历史长度
            if len(self.long_term_memory['interaction_history']) > self.MAX_LONG_TERM_INTERACTIONS:
                self.long_term_memory['interaction_history'] = self.long_term_memory['interaction_history'][-self.MAX_LONG_TERM_INTERACTIONS:]
            # 保存长期记忆
            self.save_memory()
    
    def get_recent_memory(self, memory_type=None, limit=10):
        """获取最近的记忆"""
        if memory_type:
            # 过滤特定类型的记忆
            filtered_memory = [m for m in self.short_term_memory
                               if isinstance(m, dict) and m.get('type') == memory_type]
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
            if not isinstance(memory, dict):
                continue
            
            # 按记忆类型过滤
            if 'memory_types' in query_params:
                if memory.get('type') not in query_params['memory_types']:
                    match = False
            
            # 按关键词过滤
            if match and 'keywords' in query_params:
                # 修复：content 可能是 dict（非字符串），直接 .lower() 会 AttributeError
                raw_content = memory.get('content', '')
                content = raw_content.lower() if isinstance(raw_content, str) else str(raw_content)
                keyword_match = False
                for keyword in query_params['keywords']:
                    if keyword.lower() in content:
                        keyword_match = True
                        break
                if not keyword_match:
                    match = False
            
            # 按时间范围过滤
            if match and 'time_range' in query_params:
                time_range = query_params.get('time_range')
                if not isinstance(time_range, (list, tuple)) or len(time_range) != 2:
                    _log.debug("query_memory: 非法的 time_range 格式，跳过时间过滤")
                else:
                    start_time, end_time = time_range
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
        
        # 修复：add_memory 从不写入 'id' 字段，原实现按 id 匹配恒失败 → 恒返回 []。
        # 改为：先按 id 精确匹配；找不到时退化为按 content 文本匹配（调用方可传
        # 记忆内容片段），保证联想检索在现有数据结构下真正可用。
        target_memory = None
        for memory in memories:
            if not isinstance(memory, dict):
                continue
            if memory.get('id') == memory_id:
                target_memory = memory
                break
        if target_memory is None:
            for memory in memories:
                if not isinstance(memory, dict):
                    continue
                raw = memory.get('content', '')
                text = raw.lower() if isinstance(raw, str) else str(raw)
                if memory_id.lower() in text:
                    target_memory = memory
                    break
        if not target_memory:
            return []
        
        # 提取关键词
        raw_content = target_memory.get('content', '')
        content = raw_content.lower() if isinstance(raw_content, str) else str(raw_content)
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
            
            _raw_c = memory.get('content', '')
            mem_content = _raw_c.lower() if isinstance(_raw_c, str) else str(_raw_c)
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
        # 注意：等级上限为 20（与 SocialGrowthSystem.MAX_LEVEL 保持一致，
        # 此处直接使用常量避免循环依赖）。
        MAX_LEVEL = 20
        new_level = 1
        required_experience = 100
        
        while self.experience >= required_experience and new_level < MAX_LEVEL:
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
                    if not isinstance(data, dict):
                        raise ValueError("memory root is not dict")
                    self.long_term_memory = data.get('long_term_memory', self.long_term_memory)
                    exp = data.get('experience', self.experience)
                    lv = data.get('level', self.level)
                    # 修复：手改/损坏的记忆文件可能把数值写成字符串，后续
                    # add_experience/check_level_up 做算术会 TypeError。
                    self.experience = exp if isinstance(exp, (int, float)) else 0
                    self.level = lv if isinstance(lv, (int, float)) and lv >= 1 else 1
                    _log.debug("成功加载记忆: %s", self.memory_file)
                    # 修复：旧版本记忆文件可能缺 skill_levels/behavior_patterns 等键，
                    # 后续 get_knowledge_summary / integrate_knowledge 直接索引会 KeyError。
                    # 加载后用默认结构补全缺失键。
                    _defaults = {
                        'user_preferences': {},
                        'important_dates': {},
                        'interaction_history': [],
                        'favorite_topics': {},
                        'disliked_topics': {},
                        'skill_levels': {},
                        'behavior_patterns': {},
                        'emotional_responses': {},
                        'environmental_preferences': {},
                        'relationship_history': []
                    }
                    if not isinstance(self.long_term_memory, dict):
                        self.long_term_memory = {}
                    _merged = dict(_defaults)
                    _merged.update(self.long_term_memory)
                    self.long_term_memory = _merged
        except Exception as e:
            _log.warning("加载记忆失败: %s", e)
            # 使用默认记忆
            # 修复：损坏/加载失败时兜底结构必须与成功路径一致（全键补全），
            # 否则后续 update()/learn 系列直接索引 skill_levels 等键会 KeyError。
            _defaults = {
                'user_preferences': {},
                'important_dates': {},
                'interaction_history': [],
                'favorite_topics': {},
                'disliked_topics': {},
                'skill_levels': {},
                'behavior_patterns': {},
                'emotional_responses': {},
                'environmental_preferences': {},
                'relationship_history': []
            }
            self.long_term_memory = dict(_defaults)
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
            
            # 修复：原实现直接 open(w) 覆写，写一半崩溃/断电会损坏整个记忆文件
            # （下次加载失败 → 全部记忆丢失）。改为临时文件 + 原子替换。
            import tempfile
            _tmp = self.memory_file + ".tmp"
            with open(_tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(_tmp, self.memory_file)
        except Exception as e:
            _log.warning("保存记忆失败: %s", e)
            try:
                if os.path.exists(self.memory_file + ".tmp"):
                    os.remove(self.memory_file + ".tmp")
            except Exception as e:
                _log.debug("memory_system 防御性异常（已忽略）: %s", e)
    
    def get_experience(self):
        """获取当前经验值"""
        return self.experience
    
    def get_level(self):
        """获取当前等级"""
        return self.level
    
    def update(self):
        """定期更新记忆"""
        # 修复：原实现先 _organize_memories 后 _extract_important_memories，
        # 而 _organize_memories 会删除"出现次数 <2"的记忆类型——level_up /
        # achievement_unlocked / evolution 这类只发生一次的重要记忆每次都被
        # 先删掉，导致长期记忆恒空。顺序调整为：先提取重要记忆，再整理。
        self._extract_important_memories()
        self._organize_memories()
        # 学习用户偏好
        self._learn_user_preferences()
    
    def _organize_memories(self):
        """整理记忆，去除冗余和不重要的记忆，优化记忆组织"""
        # 统计记忆类型分布
        memory_types = {}
        for memory in self.short_term_memory:
            if not isinstance(memory, dict) or 'type' not in memory:
                continue
            mem_type = memory['type']
            memory_types[mem_type] = memory_types.get(mem_type, 0) + 1

        # 移除频率过低的记忆类型（原地修改，避免引用切换）
        # 修复：与 update() 顺序修复配套的兜底——重要类型即使只出现 1 次也保留，
        # 防止"先提取"遗漏时仍被整理逻辑误删。
        _protected_types = {'user_preferences', 'important_dates', 'completed_task',
                            'level_up', 'evolution', 'achievement_unlocked'}
        for mem_type, count in list(memory_types.items()):
            if count < 2 and mem_type not in _protected_types:
                # 如果某类记忆出现次数少于2次，视为不重要
                self.short_term_memory[:] = [m for m in self.short_term_memory
                                             if not (isinstance(m, dict) and m.get('type') == mem_type)]
        
        # 按时间排序，保留最新的记忆
        self.short_term_memory.sort(key=lambda x: x.get('timestamp', 0) if isinstance(x, dict) else 0, reverse=True)
        
        # 限制短期记忆数量，确保性能
        if len(self.short_term_memory) > self.max_short_term_memory:
            self.short_term_memory = self.short_term_memory[:self.max_short_term_memory]
    
    def _extract_important_memories(self):
        """将重要的短期记忆提取到长期记忆"""
        important_types = ['user_preferences', 'important_dates', 'completed_task', 'level_up', 'evolution', 'achievement_unlocked']
        
        for memory in self.short_term_memory:
            if not isinstance(memory, dict) or 'type' not in memory:
                continue
            if memory['type'] in important_types and memory not in self.long_term_memory['interaction_history']:
                self.long_term_memory['interaction_history'].append(memory)
                # 限制长期记忆交互历史长度
                if len(self.long_term_memory['interaction_history']) > self.MAX_LONG_TERM_INTERACTIONS:
                    self.long_term_memory['interaction_history'] = self.long_term_memory['interaction_history'][-self.MAX_LONG_TERM_INTERACTIONS:]
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
            if not isinstance(memory, dict):
                continue
            if memory.get('type') in ['user_interaction', 'dialogue', 'search_query', 'file_created', 'file_opened']:
                raw_content = memory.get('content', '')
                content = raw_content.lower() if isinstance(raw_content, str) else str(raw_content)
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
        # 修复：原实现构造好含 content 的记忆后，又整体作为 content 传给
        # add_memory()（add_memory 会再包一层 {timestamp,type,content}），
        # 导致 get_user_behavior_patterns 里 memory['content']['behavior_type']
        # 必然 KeyError。这里直接传 content 本体，由 add_memory 统一包装。
        self.add_memory('user_behavior', {
            'behavior_type': behavior_type,
            'duration': duration
        }, is_short_term=True)
    
    def get_user_behavior_patterns(self):
        """获取用户行为模式"""
        behavior_patterns = {}
        for memory in self.short_term_memory + self.long_term_memory['interaction_history']:
            if not isinstance(memory, dict) or memory.get('type') != 'user_behavior':
                continue
            content = memory.get('content')
            if not isinstance(content, dict):
                continue
            behavior_type = content.get('behavior_type', 'unknown')
            duration = content.get('duration', 0)
            try:
                duration = float(duration)
            except (TypeError, ValueError):
                duration = 0
            entry = behavior_patterns.setdefault(behavior_type, {'count': 0, 'total_duration': 0.0})
            entry['count'] += 1
            entry['total_duration'] += duration
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
            
            _log.debug("Ralsei学习了新技能: %s！", new_skill)
    
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
            # 成功时适当降低学习率
            self.learning_rate = max(0.1, self.learning_rate - 0.02)
            # 记录成功经验
            self.add_memory('success_experience', f'{experience_type}: {outcome}', is_short_term=True)
        elif outcome == 'failure':
            # 失败经验，增强学习率和记忆强度
            self.update_memory_strength(experience_type, -5)
            self.learning_rate = min(1.0, self.learning_rate + 0.05)
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
        for memory in self.long_term_memory.get('interaction_history', []):
            if not isinstance(memory, dict):
                continue
            if memory.get('type') == 'user_interaction':
                # 修复：content 可能是 dict，直接 .lower() 会 AttributeError
                raw_content = memory.get('content', '')
                content = raw_content.lower() if isinstance(raw_content, str) else str(raw_content)
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
        for memory in self.long_term_memory.get('interaction_history', []):
            if isinstance(memory, dict) and 'emotion' in memory:
                emotion = memory['emotion']
                if emotion not in emotional_triggers:
                    emotional_triggers[emotion] = []
                emotional_triggers[emotion].append(memory.get('content', ''))
        
        # 更新情感反应模式
        self.long_term_memory['emotional_responses'] = emotional_triggers
        
        # 保存整合后的知识
        self.save_memory()
    
    def get_knowledge_summary(self):
        """获取知识摘要，整合记忆中的关键信息"""
        summary = {
            'user_preferences': self.get_user_preferences_summary(),
            'behavior_patterns': self.long_term_memory.get('behavior_patterns', {}),
            'skill_levels': self.long_term_memory.get('skill_levels', {}),
            'experience': self.experience,
            'level': self.level
        }
        return summary
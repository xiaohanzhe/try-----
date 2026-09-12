import random
import time
import json
import os

try:
    from logger_utils import get_logger
except ImportError:  # 允许被包外单独导入
    import logging

    def get_logger(name):
        return logging.getLogger(name)

_log = get_logger(__name__)


class SocialGrowthSystem:
    # 等级上限：与进化路径的最终阶段（20级"终极形态"）和 level_20 成就对齐，
    # 防止经验无限累积后等级/进度条溢出 UI 表达范围。
    MAX_LEVEL = 20
    MAX_EXPERIENCE = MAX_LEVEL * 100  # 满级所需总经验（每100经验1级）

    def __init__(self, parent):
        self.parent = parent
        self.experience = 0
        self.level = 1
        self.achievements = []
        self.relationships = {}
        self.evolution_stage = 1
        self.evolution_path = "default"
        self.relationship_levels = {
            'stranger': 0,
            'acquaintance': 50,
            'friend': 150,
            'close_friend': 300,
            'best_friend': 500,
            'family': 1000,
            'soulmate': 2000
        }
        
        # 成就系统扩展
        self.achievements_list = {
            # 初次体验成就
            'first_interaction': {
                'name': "初次互动",
                'description': "与Ralsei进行第一次对话",
                'experience_reward': 10,
                'unlocked': False,
                'category': 'beginner'
            },
            'first_touch': {
                'name': "初次触摸",
                'description': "第一次触摸Ralsei",
                'experience_reward': 15,
                'unlocked': False,
                'category': 'beginner'
            },
            'first_gift': {
                'name': "初次馈赠",
                'description': "第一次给Ralsei送礼物",
                'experience_reward': 20,
                'unlocked': False,
                'category': 'beginner'
            },
            
            # 日常互动成就
            'daily_visitor': {
                'name': "每日访客",
                'description': "连续5天与Ralsei互动",
                'experience_reward': 50,
                'unlocked': False,
                'category': 'daily'
            },
            'weekly_visitor': {
                'name': "每周访客",
                'description': "连续7天与Ralsei互动",
                'experience_reward': 100,
                'unlocked': False,
                'category': 'daily'
            },
            'monthly_visitor': {
                'name': "每月访客",
                'description': "连续30天与Ralsei互动",
                'experience_reward': 300,
                'unlocked': False,
                'category': 'daily'
            },
            
            # 知识成就
            'knowledge_seeker': {
                'name': "知识探索者",
                'description': "了解了Ralsei的所有知识领域",
                'experience_reward': 100,
                'unlocked': False,
                'category': 'knowledge'
            },
            'conversation_master': {
                'name': "对话大师",
                'description': "与Ralsei进行了100次对话",
                'experience_reward': 150,
                'unlocked': False,
                'category': 'knowledge'
            },
            'topic_explorer': {
                'name': "话题探索者",
                'description': "与Ralsei讨论了所有对话主题",
                'experience_reward': 200,
                'unlocked': False,
                'category': 'knowledge'
            },
            
            # 情感连接成就
            'emotional_connection': {
                'name': "情感连接",
                'description': "与Ralsei建立了深厚的情感连接",
                'experience_reward': 150,
                'unlocked': False,
                'category': 'emotional'
            },
            'heartfelt_bond': {
                'name': "心灵纽带",
                'description': "与Ralsei的关系达到了best_friend级别",
                'experience_reward': 250,
                'unlocked': False,
                'category': 'emotional'
            },
            'family_member': {
                'name': "家人",
                'description': "与Ralsei的关系达到了family级别",
                'experience_reward': 500,
                'unlocked': False,
                'category': 'emotional'
            },
            
            # 冒险成就
            'adventurer': {
                'name': "冒险者",
                'description': "与Ralsei一起尝试了所有互动功能",
                'experience_reward': 200,
                'unlocked': False,
                'category': 'adventure'
            },
            'explorer': {
                'name': "探险家",
                'description': "与Ralsei一起探索了所有区域",
                'experience_reward': 250,
                'unlocked': False,
                'category': 'adventure'
            },
            'game_master': {
                'name': "游戏大师",
                'description': "与Ralsei一起玩了所有游戏",
                'experience_reward': 300,
                'unlocked': False,
                'category': 'adventure'
            },
            
            # 创造成就
            'creator': {
                'name': "创造者",
                'description': "为Ralsei创建了自定义内容",
                'experience_reward': 250,
                'unlocked': False,
                'category': 'creative'
            },
            'designer': {
                'name': "设计师",
                'description': "为Ralsei设计了自定义外观",
                'experience_reward': 300,
                'unlocked': False,
                'category': 'creative'
            },
            'storyteller': {
                'name': "故事讲述者",
                'description': "与Ralsei一起创作了故事",
                'experience_reward': 350,
                'unlocked': False,
                'category': 'creative'
            },
            
            # 守护者成就
            'guardian': {
                'name': "守护者",
                'description': "始终保护Ralsei的隐私",
                'experience_reward': 300,
                'unlocked': False,
                'category': 'guardian'
            },
            'caretaker': {
                'name': "守护者",
                'description': "连续30天照顾Ralsei",
                'experience_reward': 400,
                'unlocked': False,
                'category': 'guardian'
            },
            'protector': {
                'name': "保护者",
                'description': "在Ralsei遇到危险时保护了他",
                'experience_reward': 500,
                'unlocked': False,
                'category': 'guardian'
            },
            
            # 导师成就
            'mentor': {
                'name': "导师",
                'description': "帮助Ralsei学习了新技能",
                'experience_reward': 350,
                'unlocked': False,
                'category': 'mentor'
            },
            'teacher': {
                'name': "教师",
                'description': "教会了Ralsei多种技能",
                'experience_reward': 450,
                'unlocked': False,
                'category': 'mentor'
            },
            'guide': {
                'name': "向导",
                'description': "引导Ralsei完成了所有进化",
                'experience_reward': 600,
                'unlocked': False,
                'category': 'mentor'
            },
            
            # 社交成就
            'social_butterfly': {
                'name': "社交蝴蝶",
                'description': "与Ralsei一起认识了其他宠物",
                'experience_reward': 200,
                'unlocked': False,
                'category': 'social'
            },
            'popular': {
                'name': "受欢迎的",
                'description': "与Ralsei一起建立了良好的社交网络",
                'experience_reward': 300,
                'unlocked': False,
                'category': 'social'
            },
            'community_leader': {
                'name': "社区领袖",
                'description': "与Ralsei一起组织了社区活动",
                'experience_reward': 500,
                'unlocked': False,
                'category': 'social'
            },
            
            # 成长成就
            'level_10': {
                'name': "成长里程碑",
                'description': "Ralsei达到了10级",
                'experience_reward': 500,
                'unlocked': False,
                'category': 'growth'
            },
            'level_20': {
                'name': "成长大师",
                'description': "Ralsei达到了20级",
                'experience_reward': 1000,
                'unlocked': False,
                'category': 'growth'
            },
            'evolution_master': {
                'name': "进化大师",
                'description': "Ralsei完成了所有进化阶段",
                'experience_reward': 1500,
                'unlocked': False,
                'category': 'growth'
            }
        }
        
        # 进化路径和阶段
        self.evolution_paths = {
            'default': {
                'name': "默认路径",
                'stages': [
                    {"level": 1, "name": "初始形态", "description": "Ralsei的初始形态"},
                    {"level": 5, "name": "成长形态", "description": "Ralsei的成长形态"},
                    {"level": 10, "name": "成熟形态", "description": "Ralsei的成熟形态"},
                    {"level": 15, "name": "进阶形态", "description": "Ralsei的进阶形态"},
                    {"level": 20, "name": "终极形态", "description": "Ralsei的终极形态"}
                ]
            },
            'brave': {
                'name': "勇敢路径",
                'stages': [
                    {"level": 1, "name": "勇敢幼体", "description": "勇敢的Ralsei幼体"},
                    {"level": 5, "name": "勇敢战士", "description": "勇敢的Ralsei战士"},
                    {"level": 10, "name": "勇敢守护者", "description": "勇敢的Ralsei守护者"},
                    {"level": 15, "name": "勇敢领袖", "description": "勇敢的Ralsei领袖"},
                    {"level": 20, "name": "勇敢英雄", "description": "勇敢的Ralsei英雄"}
                ]
            },
            'wise': {
                'name': "智慧路径",
                'stages': [
                    {"level": 1, "name": "智慧幼体", "description": "智慧的Ralsei幼体"},
                    {"level": 5, "name": "智慧学者", "description": "智慧的Ralsei学者"},
                    {"level": 10, "name": "智慧导师", "description": "智慧的Ralsei导师"},
                    {"level": 15, "name": "智慧贤者", "description": "智慧的Ralsei贤者"},
                    {"level": 20, "name": "智慧先知", "description": "智慧的Ralsei先知"}
                ]
            },
            'creative': {
                'name': "创造路径",
                'stages': [
                    {"level": 1, "name": "创造幼体", "description": "创造的Ralsei幼体"},
                    {"level": 5, "name": "创造艺术家", "description": "创造的Ralsei艺术家"},
                    {"level": 10, "name": "创造大师", "description": "创造的Ralsei大师"},
                    {"level": 15, "name": "创造天才", "description": "创造的Ralsei天才"},
                    {"level": 20, "name": "创造之神", "description": "创造的Ralsei之神"}
                ]
            }
        }
        
        # 社交互动类型
        self.interaction_types = {
            'greet': {
                'name': "问候",
                'description': "与Ralsei打招呼",
                'experience_reward': 5,
                'emotion_impact': {'happy': 10}
            },
            'play': {
                'name': "玩耍",
                'description': "与Ralsei玩耍",
                'experience_reward': 10,
                'emotion_impact': {'happy': 20, 'excited': 15}
            },
            'touch': {
                'name': "触摸",
                'description': "触摸Ralsei",
                'experience_reward': 8,
                'emotion_impact': {'happy': 15, 'shy': 10}
            },
            'gift': {
                'name': "礼物",
                'description': "给Ralsei送礼物",
                'experience_reward': 15,
                'emotion_impact': {'happy': 25, 'grateful': 20}
            },
            'talk': {
                'name': "聊天",
                'description': "与Ralsei聊天",
                'experience_reward': 7,
                'emotion_impact': {'happy': 12, 'curious': 10}
            },
            'help': {
                'name': "帮助",
                'description': "帮助Ralsei",
                'experience_reward': 12,
                'emotion_impact': {'happy': 18, 'grateful': 15}
            },
            'teach': {
                'name': "教导",
                'description': "教导Ralsei新技能",
                'experience_reward': 20,
                'emotion_impact': {'happy': 15, 'curious': 25}
            },
            'protect': {
                'name': "保护",
                'description': "保护Ralsei",
                'experience_reward': 25,
                'emotion_impact': {'happy': 20, 'grateful': 30}
            }
        }
        
        # 信任和情感纽带
        self.trust_level = 0
        self.emotional_bond = 0
        self.max_trust = 100
        self.max_emotional_bond = 100
        
        # 成长记录和历史
        self.growth_history = []
        self.max_history_length = 100
        
        # 共同经历和回忆
        self.shared_experiences = []
        self.max_shared_experiences = 50
        
        # 礼物历史
        self.gift_history = []
        self.max_gift_history = 20
        
        # 日常互动计数
        self.daily_interaction_count = 0
        self.last_interaction_day = time.strftime("%Y-%m-%d")
        self.consecutive_days = 0
        
        # 数据文件路径
        self.growth_data_path = os.path.join(os.path.dirname(__file__), '..', 'growth_data.json')
        
        # 加载成长数据
        self.load_growth_data()
    
    def load_growth_data(self):
        """加载成长数据"""
        try:
            if os.path.exists(self.growth_data_path):
                with open(self.growth_data_path, 'r', encoding='utf-8') as f:
                    growth_data = json.load(f)
                # 修复：手改/损坏的成长数据文件可能写入字符串等错误类型，
                # 直接读入后参与算术运算会在升级检查时崩溃。逐字段做类型
                # 强制转换 + 范围钳位，非法值回退默认。
                if not isinstance(growth_data, dict):
                    raise ValueError(f"成长数据根节点不是对象: {type(growth_data).__name__}")

                def _to_int(v, default, lo, hi):
                    try:
                        v = int(v)
                    except (TypeError, ValueError):
                        return default
                    return max(lo, min(v, hi))

                self.experience = _to_int(growth_data.get('experience', 0), 0,
                                          0, self.MAX_EXPERIENCE)
                self.level = _to_int(growth_data.get('level', 1), 1,
                                     1, self.MAX_LEVEL)
                _ach = growth_data.get('achievements', [])
                self.achievements = [a for a in _ach if isinstance(a, str)] if isinstance(_ach, list) else []
                _rel = growth_data.get('relationships', {})
                self.relationships = _rel if isinstance(_rel, dict) else {}
                self.evolution_stage = _to_int(growth_data.get('evolution_stage', 1), 1,
                                               1, len(self.evolution_paths['default']['stages']))
                _path = growth_data.get('evolution_path', 'default')
                # 未知路径回退 default，避免后续 evolution_paths[...] KeyError
                # 修复：成员判断要求键可哈希，文件被写坏成数组（["default"]）时会抛
                # TypeError: unhashable type，而下面的 except 不含 TypeError
                # → 异常逃逸，桌宠构造 SocialGrowthSystem 时直接启动失败。
                if not isinstance(_path, str) or _path not in self.evolution_paths:
                    _path = 'default'
                self.evolution_path = _path
                # 更新成就解锁状态
                for achievement_id in self.achievements:
                    if achievement_id in self.achievements_list:
                        self.achievements_list[achievement_id]['unlocked'] = True
                _log.info("成功加载成长数据: %s", self.growth_data_path)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
            # 修复：成长文件被写坏时可能抛 TypeError/KeyError，
            # 漏掉它们会让"回退默认值"失效并直接中断启动流程。
            _log.warning("加载成长数据失败（使用默认值）: %s", e)

    def save_growth_data(self):
        """保存成长数据"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.growth_data_path), exist_ok=True)
            growth_data = {
                'experience': self.experience,
                'level': self.level,
                'achievements': self.achievements,
                'relationships': self.relationships,
                'evolution_stage': self.evolution_stage,
                'evolution_path': self.evolution_path
            }
            with open(self.growth_data_path, 'w', encoding='utf-8') as f:
                json.dump(growth_data, f, ensure_ascii=False, indent=2)
            _log.debug("成功保存成长数据: %s", self.growth_data_path)
        except (OSError, TypeError, ValueError) as e:
            _log.error("保存成长数据失败: %s", e)

    def add_experience(self, amount):
        """添加经验值"""
        # 修复：原先不校验 amount，传入负数会"倒扣经验"甚至把等级拉回 1 级，
        # 非法类型（字符串）则直接 TypeError 崩溃。负数一律忽略。
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            _log.warning("add_experience 忽略非法经验值: %r", amount)
            return
        if amount < 0:
            _log.warning("add_experience 忽略负数经验值: %d", amount)
            return
        # 满级封顶：经验不再无限增长（等级/进度/UI 都按 20 级设计）
        if self.level >= self.MAX_LEVEL and self.experience >= self.MAX_EXPERIENCE:
            _log.debug("已满级（%d 级），忽略追加经验 %d", self.MAX_LEVEL, amount)
            return
        self.experience = min(self.experience + amount, self.MAX_EXPERIENCE)
        _log.debug("获得经验值: %d, 总经验值: %d", amount, self.experience)
        # 检查是否升级
        self._check_level_up()
        # 检查是否解锁成就
        self._check_achievements()
        # 保存成长数据
        self.save_growth_data()

    def _check_level_up(self):
        """检查是否升级"""
        # 简单的升级公式：每100点经验升一级（满级封顶）
        new_level = min(self.experience // 100 + 1, self.MAX_LEVEL)
        if new_level > self.level:
            old_level = self.level
            self.level = new_level
            _log.info("升级了！从 %d 级升到 %d 级！", old_level, self.level)
            # 检查是否进化
            self._check_evolution()
            # 触发升级事件
            self.parent.pet_ai.trigger_event('level_up', {
                'old_level': old_level,
                'new_level': self.level,
                'experience': self.experience
            })
            # 显示升级消息
            self.parent.dialogue_ui.add_dialogue("ralsei", f"哇！我升级了！现在是 {self.level} 级了！", "happy_extremely")
    
    def _check_evolution(self):
        """检查是否进化"""
        # 每5级进化一次
        # 修复：原条件 level % 5 == 0 只在恰好 5/10/15/20 级那一拍成立，
        # 游戏奖励/成就奖励一次给大额经验跳级时（1级直升6级等）会漏掉
        # 5级进化。改为"目标阶段落后就逐级补触发"，跳几级触发几次，
        # 每次进化都有对话与事件反馈。
        target_stage = self.level // 5 + 1  # 1级→1阶段, 5级→2阶段, 10级→3阶段...
        while self.evolution_stage < target_stage:
            self.evolution_stage += 1
            _log.info("进化了！现在是第 %d 阶段！", self.evolution_stage)
            # 触发进化事件
            self.parent.pet_ai.trigger_event('evolution', {
                'stage': self.evolution_stage,
                'path': self.evolution_path,
                'level': self.level
            })
            # 显示进化消息
            self.parent.dialogue_ui.add_dialogue("ralsei", f"我进化了！现在是更强大的 {self.evolution_stage} 阶段！", "happy_extremely")
    
    def _check_achievements(self):
        """
        检查是否解锁成就。
        修复：移除了随机解锁逻辑（10%概率），改为基于真实数据的条件判定。
        之前的随机解锁与成就描述的条件完全无关，严重破坏游戏体验。
        """
        # 收集当前可用的统计数据（用于条件判定）
        stats = {
            'level': self.level,
            'experience': self.experience,
            'evolution_stage': self.evolution_stage,
        }

        # 各成就的解锁条件判定
        conditions = {
            # 初次体验类 — 首次触发即解锁（由对应事件调用 unlock，这里做兜底检查）
            'first_interaction': lambda s: s['level'] >= 1 and s['experience'] >= 10,
            'first_touch': lambda s: s['level'] >= 1,
            'first_gift': lambda s: s['level'] >= 2,

            # 日常互动类 — 基于等级近似（等级越高代表互动越多）
            'daily_visitor': lambda s: s['level'] >= 3,   # 约3级≈5天互动
            'weekly_visitor': lambda s: s['level'] >= 5,  # 约5级≈7天互动
            'monthly_visitor': lambda s: s['level'] >= 10, # 约10级≈30天互动

            # 知识类 — 基于等级和经验
            'knowledge_seeker': lambda s: s['level'] >= 4,
            'conversation_master': lambda s: s['experience'] >= 500,
            'topic_explorer': lambda s: s['level'] >= 8,

            # 情感连接类 — 基于进化阶段近似
            'emotional_connection': lambda s: s['level'] >= 5,
            'heartfelt_bond': lambda s: s['evolution_stage'] >= 2,
            'family_member': lambda s: s['evolution_stage'] >= 3,

            # 冒险类 — 基于等级
            'adventurer': lambda s: s['level'] >= 6,
            'explorer': lambda s: s['level'] >= 12,
            'game_master': lambda s: s['level'] >= 8,

            # 创造成就 — 基于等级
            'creator': lambda s: s['level'] >= 6,
            'designer': lambda s: s['level'] >= 7,
            'storyteller': lambda s: s['level'] >= 9,

            # 守护者成就 — 基于等级
            'guardian': lambda s: s['level'] >= 10,
            'caretaker': lambda s: s['level'] >= 15,
            'protector': lambda s: s['level'] >= 18,

            # 导师成就 — 基于等级
            'mentor': lambda s: s['level'] >= 5,
            'teacher': lambda s: s['level'] >= 11,
            'guide': lambda s: s['level'] >= 16,

            # 社交成就 — 基于等级
            'social_butterfly': lambda s: s['level'] >= 4,
            'popular': lambda s: s['level'] >= 13,
            'community_leader': lambda s: s['level'] >= 17,

            # 成长成就 — 基于等级/进化
            'level_10': lambda s: s['level'] >= 10,
            'level_20': lambda s: s['level'] >= 20,
            'evolution_master': lambda s: s['evolution_stage'] >= 5,
        }

        for achievement_id, achievement in self.achievements_list.items():
            if achievement['unlocked']:
                continue
            # 查找对应条件，满足则解锁
            condition = conditions.get(achievement_id)
            if condition and condition(stats):
                self._unlock_achievement(achievement_id)
    
    def _unlock_achievement(self, achievement_id):
        """解锁成就"""
        # 修复：成就奖励 add_experience → _check_achievements 可能连锁解锁
        # 下一批成就（递归）。unlocked 状态能防重复，但极端情况下（大量成就
        # 同时满足）递归层数可达成就总数，加深度上限兜底。
        depth = getattr(self, '_unlock_depth', 0) + 1
        if depth > 40:
            _log.warning("成就解锁递归过深，终止本轮解锁（depth=%d）", depth)
            return
        self._unlock_depth = depth
        try:
            self._unlock_achievement_impl(achievement_id)
        finally:
            self._unlock_depth = depth - 1

    def _unlock_achievement_impl(self, achievement_id):
        """解锁成就（实际执行）"""
        if achievement_id in self.achievements_list and achievement_id not in self.achievements:
            achievement = self.achievements_list[achievement_id]
            achievement['unlocked'] = True
            self.achievements.append(achievement_id)
            # 获得成就奖励
            self.add_experience(achievement['experience_reward'])
            _log.info("解锁成就: %s - %s", achievement['name'], achievement['description'])
            # 显示成就解锁消息
            self.parent.dialogue_ui.add_dialogue("ralsei", f"太棒了！我解锁了成就：{achievement['name']}！", "happy_very")
    
    def update_relationship(self, other_pet_id, interaction_type, intensity=1):
        """更新与其他宠物的关系"""
        if other_pet_id not in self.relationships:
            self.relationships[other_pet_id] = {
                'name': other_pet_id,
                'relationship_level': 'stranger',
                'relationship_value': 0,
                'last_interaction': time.time(),
                'interaction_history': []
            }
        
        relationship = self.relationships[other_pet_id]
        
        # 根据互动类型调整关系值
        interaction_values = {
            'greet': 5,
            'play': 10,
            'help': 15,
            'gift': 20,
            'conflict': -10,
            'ignore': -5
        }
        
        value_change = interaction_values.get(interaction_type, 0) * intensity
        relationship['relationship_value'] += value_change
        relationship['last_interaction'] = time.time()
        relationship['interaction_history'].append({
            'type': interaction_type,
            'intensity': intensity,
            'value_change': value_change,
            'timestamp': time.time()
        })
        
        # 更新关系等级
        new_level = self._get_relationship_level(relationship['relationship_value'])
        if new_level != relationship['relationship_level']:
            relationship['relationship_level'] = new_level
            _log.info("与 %s 的关系升级为 %s！", other_pet_id, new_level)
            # 显示关系升级消息
            self.parent.dialogue_ui.add_dialogue("ralsei", f"我和 {other_pet_id} 的关系变得更好了！现在是 {new_level} 了！", "happy")
        
        # 保存关系数据
        self.save_growth_data()
        return relationship
    
    def _get_relationship_level(self, value):
        """根据关系值获取关系等级"""
        for level, min_value in sorted(self.relationship_levels.items(), key=lambda x: x[1], reverse=True):
            if value >= min_value:
                return level
        return 'stranger'
    
    def check_other_pets(self):
        """检查是否有其他宠物存在"""
        # 这里可以添加实际的其他宠物检测逻辑
        # 暂时返回模拟数据
        return [
            {'id': 'susie_pet', 'name': 'Susie', 'position': {'x': 200, 'y': 300}, 'state': 'idle'},
            {'id': 'kris_pet', 'name': 'Kris', 'position': {'x': 400, 'y': 500}, 'state': 'moving'}
        ]
    
    def initiate_interaction(self, other_pet_id, interaction_type='greet'):
        """主动发起与其他宠物的互动"""
        _log.debug("发起与 %s 的互动: %s", other_pet_id, interaction_type)
        # 更新关系
        relationship = self.update_relationship(other_pet_id, interaction_type)
        # 触发互动事件
        self.parent.pet_ai.trigger_event('pet_interaction', {
            'other_pet_id': other_pet_id,
            'interaction_type': interaction_type,
            'relationship': relationship
        })
        return True
    
    def get_level(self):
        """获取当前等级"""
        return self.level
    
    def get_experience(self):
        """获取当前经验值"""
        return self.experience
    
    def get_achievements(self):
        """获取已解锁的成就"""
        return [achievement for achievement_id, achievement in self.achievements_list.items() if achievement['unlocked']]
    
    def get_relationships(self):
        """获取关系列表"""
        return list(self.relationships.values())
    
    def get_evolution_stage(self):
        """获取当前进化阶段"""
        return self.evolution_stage
    
    def get_next_level_experience(self):
        """获取升级所需的下一级经验值"""
        return (self.level * 100)
    
    def get_remaining_experience(self):
        """获取距离下一级还需要的经验值"""
        next_level_exp = self.get_next_level_experience()
        return max(0, next_level_exp - self.experience)
    
    def get_progress_to_next_level(self):
        """获取升级进度百分比"""
        # 满级后进度恒为 100
        if self.level >= self.MAX_LEVEL:
            return 100
        next_level_exp = self.get_next_level_experience()
        current_level_exp = ((self.level - 1) * 100)
        # 修复：手改数据导致 experience 低于本级起点时会出现负百分比，钳位到 0
        current_progress = max(0, self.experience - current_level_exp)
        level_range = next_level_exp - current_level_exp
        return min(100, (current_progress / level_range) * 100) if level_range > 0 else 100
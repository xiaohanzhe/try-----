import random
import time
import os
import json
from typing import List, Dict, Any

class EntertainmentSystem:
    def __init__(self, parent):
        self.parent = parent
        
        # 游戏系统
        self.games = {
            'matching_game': {
                'name': '记忆匹配',
                'description': '经典的记忆匹配游戏，翻转卡片找到配对',
                'difficulty': ['easy', 'medium', 'hard'],
                'min_level': 1,
                'experience_reward': [10, 20, 30]
            },
            'puzzle_game': {
                'name': '拼图游戏',
                'description': '将打乱的图片拼回完整',
                'difficulty': ['easy', 'medium', 'hard'],
                'min_level': 5,
                'experience_reward': [15, 25, 35]
            },
            'quiz_game': {
                'name': '知识问答',
                'description': '回答各种知识问题',
                'difficulty': ['easy', 'medium', 'hard'],
                'min_level': 3,
                'experience_reward': [12, 22, 32]
            },
            'adventure_game': {
                'name': '冒险探索',
                'description': '在虚拟世界中进行冒险探索',
                'difficulty': ['medium', 'hard', 'expert'],
                'min_level': 10,
                'experience_reward': [25, 35, 50]
            }
        }
        
        # 创意表达功能
        self.creative_features = {
            'story_writing': {
                'name': '故事创作',
                'description': '与Ralsei一起创作故事',
                'min_level': 7,
                'experience_reward': 20
            },
            'poetry_writing': {
                'name': '诗歌创作',
                'description': '与Ralsei一起创作诗歌',
                'min_level': 5,
                'experience_reward': 15
            },
            'drawing': {
                'name': '绘画创作',
                'description': '与Ralsei一起绘画',
                'min_level': 3,
                'experience_reward': 10
            },
            'music_composition': {
                'name': '音乐创作',
                'description': '与Ralsei一起创作音乐',
                'min_level': 8,
                'experience_reward': 25
            }
        }
        
        # 个性化内容
        self.personalized_content = {
            'custom_stories': {
                'name': '定制故事',
                'description': '生成个性化的故事',
                'min_level': 6,
                'experience_reward': 18
            },
            'custom_music': {
                'name': '定制音乐',
                'description': '生成个性化的音乐',
                'min_level': 9,
                'experience_reward': 28
            },
            'custom_poetry': {
                'name': '定制诗歌',
                'description': '生成个性化的诗歌',
                'min_level': 4,
                'experience_reward': 13
            }
        }
        
        # 笑话和谜语
        self.jokes = [
            "为什么电脑总是很冷？因为它们有太多的风扇！",
            "程序员最喜欢的水果是什么？是香蕉，因为它们不会崩溃！",
            "为什么数学书看起来很伤心？因为它有太多的问题！",
            "什么东西早上四条腿，中午两条腿，晚上三条腿？答案是：人！",
            "为什么猫喜欢坐在电脑上？因为它们喜欢追鼠标！"
        ]
        
        self.riddles = [
            {
                'question': "什么东西越洗越脏？",
                'answer': "水"
            },
            {
                'question': "什么东西有头无脚？",
                'answer': "铅笔"
            },
            {
                'question': "什么东西破了才能用？",
                'answer': "鸡蛋"
            },
            {
                'question': "什么东西只能加不能减？",
                'answer': "年龄"
            },
            {
                'question': "什么东西是你的，但别人用的比你多？",
                'answer': "名字"
            }
        ]
        
        # 故事模板
        self.story_templates = [
            {
                'title': "{name}的冒险",
                'intro': "从前，有一个名叫{name}的{character_type}，住在{place}。有一天，{event}发生了...",
                'middle': "为了解决这个问题，{name}开始了一段冒险。在旅途中，{name}遇到了{friend}，并一起克服了许多困难...",
                'ending': "最终，{name}成功地{achievement}，并从中学到了{lesson}。"
            },
            {
                'title': "神秘的{object}",
                'intro': "在{place}的深处，有一个神秘的{object}。传说中，谁能找到它，就能获得{power}...",
                'middle': "{name}决定去寻找这个神秘的{object}。在旅途中，{name}遇到了各种挑战，包括{challenge}...",
                'ending': "经过一番努力，{name}终于找到了{object}，但{twist}。最终，{name}意识到{truth}。"
            }
        ]
        
        # 最近的娱乐活动记录
        self.recent_activities = []
        self.max_recent_activities = 20
        
        # 游戏成就
        self.game_achievements = {
            'game_master': {
                'name': '游戏大师',
                'description': '完成所有游戏',
                'unlocked': False,
                'reward': 500
            },
            'perfect_score': {
                'name': '满分达人',
                'description': '在任何游戏中获得满分',
                'unlocked': False,
                'reward': 200
            },
            'quick_finish': {
                'name': '快速完成',
                'description': '在最短时间内完成游戏',
                'unlocked': False,
                'reward': 150
            }
        }
        
        # 创意成就
        self.creative_achievements = {
            'storyteller': {
                'name': '故事大王',
                'description': '创作10个故事',
                'unlocked': False,
                'reward': 300
            },
            'poet': {
                'name': '诗人',
                'description': '创作20首诗歌',
                'unlocked': False,
                'reward': 250
            },
            'artist': {
                'name': '艺术家',
                'description': '完成15幅绘画',
                'unlocked': False,
                'reward': 200
            }
        }
        
        # 统计数据
        self.activity_stats = {
            'games_played': 0,
            'stories_created': 0,
            'poems_written': 0,
            'drawings_made': 0,
            'music_composed': 0,
            'jokes_told': 0,
            'riddles_answered': 0
        }
        
        # 数据文件路径
        self.entertainment_data_path = os.path.join(os.path.dirname(__file__), '..', 'entertainment_data.json')
        
        # 加载娱乐数据
        self.load_entertainment_data()
    
    def load_entertainment_data(self):
        """加载娱乐数据"""
        try:
            if os.path.exists(self.entertainment_data_path):
                with open(self.entertainment_data_path, 'r', encoding='utf-8') as f:
                    entertainment_data = json.load(f)
                    self.activity_stats = entertainment_data.get('activity_stats', self.activity_stats)
                    self.recent_activities = entertainment_data.get('recent_activities', self.recent_activities)
                    # 加载成就数据
                    game_achievements = entertainment_data.get('game_achievements', {})
                    for achievement_id, achievement in game_achievements.items():
                        if achievement_id in self.game_achievements:
                            self.game_achievements[achievement_id]['unlocked'] = achievement.get('unlocked', False)
                    creative_achievements = entertainment_data.get('creative_achievements', {})
                    for achievement_id, achievement in creative_achievements.items():
                        if achievement_id in self.creative_achievements:
                            self.creative_achievements[achievement_id]['unlocked'] = achievement.get('unlocked', False)
                print(f"成功加载娱乐数据: {self.entertainment_data_path}")
        except Exception as e:
            print(f"加载娱乐数据失败: {e}")
    
    def save_entertainment_data(self):
        """保存娱乐数据"""
        try:
            entertainment_data = {
                'activity_stats': self.activity_stats,
                'recent_activities': self.recent_activities,
                'game_achievements': self.game_achievements,
                'creative_achievements': self.creative_achievements
            }
            with open(self.entertainment_data_path, 'w', encoding='utf-8') as f:
                json.dump(entertainment_data, f, ensure_ascii=False, indent=2)
            print(f"成功保存娱乐数据: {self.entertainment_data_path}")
        except Exception as e:
            print(f"保存娱乐数据失败: {e}")
    
    def get_available_games(self):
        """获取可用的游戏列表"""
        current_level = self.parent.social_growth_system.get_level()
        available_games = []
        for game_id, game_info in self.games.items():
            if current_level >= game_info['min_level']:
                available_games.append(game_info)
        return available_games
    
    def get_available_creative_features(self):
        """获取可用的创意功能列表"""
        current_level = self.parent.social_growth_system.get_level()
        available_features = []
        for feature_id, feature_info in self.creative_features.items():
            if current_level >= feature_info['min_level']:
                available_features.append(feature_info)
        return available_features
    
    def start_game(self, game_id, difficulty='easy'):
        """开始游戏"""
        if game_id not in self.games:
            return False, "游戏不存在"
        
        game = self.games[game_id]
        current_level = self.parent.social_growth_system.get_level()
        
        if current_level < game['min_level']:
            return False, f"需要{game['min_level']}级才能玩这个游戏"
        
        if difficulty not in game['difficulty']:
            return False, f"无效的难度级别，可选难度：{', '.join(game['difficulty'])}"
        
        # 记录游戏开始
        print(f"开始游戏：{game['name']}，难度：{difficulty}")
        
        # 触发游戏开始事件
        self.parent.pet_ai.trigger_event('game_start', {
            'game_id': game_id,
            'game_name': game['name'],
            'difficulty': difficulty
        })
        
        # 显示游戏开始消息
        self.parent.dialogue_ui.add_dialogue("ralsei", f"让我们开始玩{game['name']}吧！难度：{difficulty}", "excited")
        
        return True, f"开始{game['name']}游戏，难度：{difficulty}"
    
    def end_game(self, game_id, difficulty='easy', score=0, win=False):
        """结束游戏"""
        if game_id not in self.games:
            return False, "游戏不存在"
        
        game = self.games[game_id]
        
        # 计算经验奖励
        difficulty_index = game['difficulty'].index(difficulty)
        base_reward = game['experience_reward'][difficulty_index]
        # 根据是否获胜和分数调整奖励
        if win:
            reward = int(base_reward * 1.5)
            if score >= 90:
                reward = int(reward * 1.2)
        else:
            reward = int(base_reward * 0.5)
        
        # 添加经验值
        self.parent.social_growth_system.add_experience(reward)
        
        # 更新统计数据
        self.activity_stats['games_played'] += 1
        
        # 记录最近活动
        self._add_recent_activity('game', {
            'game_id': game_id,
            'game_name': game['name'],
            'difficulty': difficulty,
            'score': score,
            'win': win,
            'reward': reward,
            'timestamp': time.time()
        })
        
        # 检查游戏成就
        self._check_game_achievements(game_id, difficulty, score, win)
        
        # 保存数据
        self.save_entertainment_data()
        
        # 显示游戏结束消息
        if win:
            self.parent.dialogue_ui.add_dialogue("ralsei", f"太棒了！我们赢了{game['name']}！获得了{reward}经验值！", "happy_very")
        else:
            self.parent.dialogue_ui.add_dialogue("ralsei", f"游戏结束了！虽然我们没有赢，但获得了{reward}经验值！下次加油！", "encouraging")
        
        return True, f"游戏结束，获得{reward}经验值"
    
    def start_creative_activity(self, activity_id):
        """开始创意活动"""
        if activity_id not in self.creative_features:
            return False, "创意活动不存在"
        
        activity = self.creative_features[activity_id]
        current_level = self.parent.social_growth_system.get_level()
        
        if current_level < activity['min_level']:
            return False, f"需要{activity['min_level']}级才能进行这个创意活动"
        
        # 记录活动开始
        print(f"开始创意活动：{activity['name']}")
        
        # 触发创意活动开始事件
        self.parent.pet_ai.trigger_event('creative_activity_start', {
            'activity_id': activity_id,
            'activity_name': activity['name']
        })
        
        # 显示活动开始消息
        self.parent.dialogue_ui.add_dialogue("ralsei", f"让我们开始{activity['name']}吧！我很期待我们的创作！", "excited")
        
        return True, f"开始{activity['name']}活动"
    
    def end_creative_activity(self, activity_id, quality='good'):
        """结束创意活动"""
        if activity_id not in self.creative_features:
            return False, "创意活动不存在"
        
        activity = self.creative_features[activity_id]
        
        # 计算经验奖励
        base_reward = activity['experience_reward']
        # 根据质量调整奖励
        quality_multipliers = {
            'excellent': 1.5,
            'good': 1.2,
            'average': 1.0,
            'poor': 0.5
        }
        multiplier = quality_multipliers.get(quality, 1.0)
        reward = int(base_reward * multiplier)
        
        # 添加经验值
        self.parent.social_growth_system.add_experience(reward)
        
        # 更新统计数据
        if activity_id == 'story_writing':
            self.activity_stats['stories_created'] += 1
        elif activity_id == 'poetry_writing':
            self.activity_stats['poems_written'] += 1
        elif activity_id == 'drawing':
            self.activity_stats['drawings_made'] += 1
        elif activity_id == 'music_composition':
            self.activity_stats['music_composed'] += 1
        
        # 记录最近活动
        self._add_recent_activity('creative', {
            'activity_id': activity_id,
            'activity_name': activity['name'],
            'quality': quality,
            'reward': reward,
            'timestamp': time.time()
        })
        
        # 检查创意成就
        self._check_creative_achievements(activity_id)
        
        # 保存数据
        self.save_entertainment_data()
        
        # 显示活动结束消息
        if quality == 'excellent':
            self.parent.dialogue_ui.add_dialogue("ralsei", f"哇！我们的{activity['name']}创作太棒了！获得了{reward}经验值！", "happy_extremely")
        else:
            self.parent.dialogue_ui.add_dialogue("ralsei", f"我们的{activity['name']}创作完成了！获得了{reward}经验值！", "happy_very")
        
        return True, f"完成{activity['name']}创作，获得{reward}经验值"
    
    def tell_joke(self):
        """讲笑话"""
        joke = random.choice(self.jokes)
        self.activity_stats['jokes_told'] += 1
        self.save_entertainment_data()
        return joke
    
    def get_riddle(self):
        """获取谜语"""
        riddle = random.choice(self.riddles)
        return riddle
    
    def answer_riddle(self, riddle, user_answer):
        """回答谜语"""
        correct = user_answer.strip().lower() == riddle['answer'].strip().lower()
        self.activity_stats['riddles_answered'] += 1
        
        if correct:
            # 获得少量经验值
            self.parent.social_growth_system.add_experience(5)
            self.save_entertainment_data()
            return True, "恭喜！回答正确！"
        else:
            self.save_entertainment_data()
            return False, f"回答错误！正确答案是：{riddle['answer']}"
    
    def generate_story(self, title, character_name, character_type, place, event, friend, achievement, lesson):
        """生成故事"""
        template = random.choice(self.story_templates)
        
        story = {
            'title': template['title'].format(name=character_name),
            'intro': template['intro'].format(
                name=character_name,
                character_type=character_type,
                place=place,
                event=event
            ),
            'middle': template['middle'].format(
                name=character_name,
                friend=friend
            ),
            'ending': template['ending'].format(
                name=character_name,
                achievement=achievement,
                lesson=lesson
            )
        }
        
        return story
    
    def _add_recent_activity(self, activity_type, activity_data):
        """添加最近活动记录"""
        activity = {
            'type': activity_type,
            'data': activity_data,
            'timestamp': time.time()
        }
        self.recent_activities.append(activity)
        if len(self.recent_activities) > self.max_recent_activities:
            self.recent_activities.pop(0)
    
    def _check_game_achievements(self, game_id, difficulty, score, win):
        """检查游戏成就"""
        # 检查完美得分成就
        if score >= 100 and not self.game_achievements['perfect_score']['unlocked']:
            self.game_achievements['perfect_score']['unlocked'] = True
            self.parent.dialogue_ui.add_dialogue("ralsei", "太棒了！我们解锁了'满分达人'成就！", "happy_extremely")
            self.parent.social_growth_system.add_experience(self.game_achievements['perfect_score']['reward'])
        
        # 检查游戏大师成就（这里简化处理，实际需要检查所有游戏是否都玩过）
        if self.activity_stats['games_played'] >= len(self.games) and not self.game_achievements['game_master']['unlocked']:
            self.game_achievements['game_master']['unlocked'] = True
            self.parent.dialogue_ui.add_dialogue("ralsei", "太厉害了！我们解锁了'游戏大师'成就！", "happy_extremely")
            self.parent.social_growth_system.add_experience(self.game_achievements['game_master']['reward'])
    
    def _check_creative_achievements(self, activity_id):
        """检查创意成就"""
        # 检查故事大王成就
        if self.activity_stats['stories_created'] >= 10 and not self.creative_achievements['storyteller']['unlocked']:
            self.creative_achievements['storyteller']['unlocked'] = True
            self.parent.dialogue_ui.add_dialogue("ralsei", "太棒了！我们解锁了'故事大王'成就！", "happy_extremely")
            self.parent.social_growth_system.add_experience(self.creative_achievements['storyteller']['reward'])
        
        # 检查诗人成就
        if self.activity_stats['poems_written'] >= 20 and not self.creative_achievements['poet']['unlocked']:
            self.creative_achievements['poet']['unlocked'] = True
            self.parent.dialogue_ui.add_dialogue("ralsei", "太棒了！我们解锁了'诗人'成就！", "happy_extremely")
            self.parent.social_growth_system.add_experience(self.creative_achievements['poet']['reward'])
        
        # 检查艺术家成就
        if self.activity_stats['drawings_made'] >= 15 and not self.creative_achievements['artist']['unlocked']:
            self.creative_achievements['artist']['unlocked'] = True
            self.parent.dialogue_ui.add_dialogue("ralsei", "太棒了！我们解锁了'艺术家'成就！", "happy_extremely")
            self.parent.social_growth_system.add_experience(self.creative_achievements['artist']['reward'])
    
    def get_activity_stats(self):
        """获取活动统计数据"""
        return self.activity_stats
    
    def get_recent_activities(self):
        """获取最近的娱乐活动"""
        return self.recent_activities
    
    def get_game_achievements(self):
        """获取游戏成就"""
        return self.game_achievements
    
    def get_creative_achievements(self):
        """获取创意成就"""
        return self.creative_achievements
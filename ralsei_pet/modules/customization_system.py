import json
import os

class CustomizationSystem:
    def __init__(self, parent):
        self.parent = parent
        self.config_path = os.path.join(os.path.dirname(__file__), '..', 'customization_config.json')
        self.customization_data = {
            'appearance': {
                'outfit': 'default',
                'accessories': [],
                'color_scheme': 'default',
                'size': 'normal',
                'animation_speed': 1.0,
                'background': 'default',
                'weather_effects': False,
                'lighting_effects': 'default',
                'particle_effects': False,
            },
            'behavior': {
                'personality_traits': {
                    'introvert_extrovert': 30,
                    'optimism_pessimism': 70,
                    'bravery_caution': 50,
                    'curiosity': 80,
                    'loyalty': 90,
                    'patience': 70,
                    'creativity': 85,
                    'empathy': 95,
                    'playfulness': 80,
                    'neatness': 60,
                },
                'active_level': 'medium',  # low, medium, high
                'interaction_frequency': 'medium',  # low, medium, high
                'humor_level': 'medium',  # low, medium, high
                'formality_level': 'low',  # low, medium, high
                'initiative_level': 'low',  # low, medium, high
                'emotional_intensity': 'medium',  # low, medium, high
                'verbosity': 'medium',  # low, medium, high
            },
            'content': {
                'knowledge_areas': ['deltarune', 'undertale', 'general'],
                'interests': ['games', 'music', 'art', 'reading'],
                'conversation_topics': ['daily_life', 'hobbies', 'emotions', 'ideas'],
                'language_style': 'friendly',  # formal, friendly, casual, playful
                'response_length': 'medium',  # short, medium, long
                'creativity_level': 'medium',  # low, medium, high
                'humor_type': 'wholesome',  # dry, slapstick, witty, wholesome
            },
            'privacy': {
                'data_collection': 'minimal',  # minimal, essential, full
                'activity_tracking': True,
                'learning_mode': True,
                'screen_content_analysis': False,
                'voice_analysis': False,
                'location_tracking': False,
            },
            'environment': {
                'home_location': 'bedroom',  # bedroom, living_room, office, kitchen
                'time_of_day_preference': 'day',  # day, night
                'weather_preference': 'sunny',  # sunny, cloudy, rainy, snowy
                'temperature_preference': 'warm',  # cold, cool, warm, hot
            },
            'relationship': {
                'relationship_type': 'friend',  # friend, sibling, parent, mentor, pet
                'nickname': '',
                'anniversary': '',
                'special_connections': [],
            }
        }
        
        # 加载自定义配置
        self.load_config()
    
    def load_config(self):
        """加载自定义配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 合并配置，保留原有配置的默认值
                    self._merge_config(self.customization_data, loaded_config)
                    print(f"成功加载自定义配置: {self.config_path}")
        except Exception as e:
            print(f"加载自定义配置失败: {e}")
    
    def save_config(self):
        """保存自定义配置"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.customization_data, f, ensure_ascii=False, indent=2)
            print(f"成功保存自定义配置: {self.config_path}")
        except Exception as e:
            print(f"保存自定义配置失败: {e}")
    
    def _merge_config(self, base, update):
        """递归合并配置"""
        for key, value in update.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def update_appearance(self, appearance_settings):
        """更新外观设置"""
        self.customization_data['appearance'].update(appearance_settings)
        self.save_config()
        # 应用外观变化
        self.apply_appearance_changes()
    
    def update_behavior(self, behavior_settings):
        """更新行为设置"""
        if 'personality_traits' in behavior_settings:
            # 更新个性特质
            self.customization_data['behavior']['personality_traits'].update(
                behavior_settings['personality_traits']
            )
            # 应用到情绪系统
            for trait, value in behavior_settings['personality_traits'].items():
                self.parent.emotion_system.set_personality_trait(trait, value)
        
        # 更新其他行为设置
        for key, value in behavior_settings.items():
            if key != 'personality_traits':
                self.customization_data['behavior'][key] = value
        
        self.save_config()
    
    def update_content_preferences(self, content_settings):
        """更新内容偏好"""
        self.customization_data['content'].update(content_settings)
        self.save_config()
    
    def update_privacy_settings(self, privacy_settings):
        """更新隐私设置"""
        self.customization_data['privacy'].update(privacy_settings)
        self.save_config()
    
    def apply_appearance_changes(self):
        """应用外观变化"""
        # 这里可以添加实际的外观变化应用逻辑
        # 例如：更换服装、调整大小、改变颜色等
        appearance = self.customization_data['appearance']
        print(f"应用外观变化: {appearance}")
        # 调整动画速度
        animation_speed = appearance['animation_speed']
        # 更新动画定时器速度
        if hasattr(self.parent, 'animation_timer'):
            original_interval = 100  # 默认100ms
            new_interval = max(50, int(original_interval / animation_speed))
            self.parent.animation_timer.setInterval(new_interval)
    
    def get_customization_data(self):
        """获取当前的自定义数据"""
        return self.customization_data
    
    def reset_customization(self):
        """重置自定义设置"""
        self.customization_data = {
            'appearance': {
                'outfit': 'default',
                'accessories': [],
                'color_scheme': 'default',
                'size': 'normal',
                'animation_speed': 1.0,
                'background': 'default',
                'weather_effects': False,
                'lighting_effects': 'default',
                'particle_effects': False,
            },
            'behavior': {
                'personality_traits': {
                    'introvert_extrovert': 30,
                    'optimism_pessimism': 70,
                    'bravery_caution': 50,
                    'curiosity': 80,
                    'loyalty': 90,
                    'patience': 70,
                    'creativity': 85,
                    'empathy': 95,
                    'playfulness': 80,
                    'neatness': 60,
                },
                'active_level': 'medium',
                'interaction_frequency': 'medium',
                'humor_level': 'medium',
                'formality_level': 'low',
                'initiative_level': 'low',
                'emotional_intensity': 'medium',
                'verbosity': 'medium',
            },
            'content': {
                'knowledge_areas': ['deltarune', 'undertale', 'general'],
                'interests': ['games', 'music', 'art', 'reading'],
                'conversation_topics': ['daily_life', 'hobbies', 'emotions', 'ideas'],
                'language_style': 'friendly',
                'response_length': 'medium',
                'creativity_level': 'medium',
                'humor_type': 'wholesome',
            },
            'privacy': {
                'data_collection': 'minimal',
                'activity_tracking': True,
                'learning_mode': True,
                'screen_content_analysis': False,
                'voice_analysis': False,
                'location_tracking': False,
            },
            'environment': {
                'home_location': 'bedroom',
                'time_of_day_preference': 'day',
                'weather_preference': 'sunny',
                'temperature_preference': 'warm',
            },
            'relationship': {
                'relationship_type': 'friend',
                'nickname': '',
                'anniversary': '',
                'special_connections': [],
            }
        }
        self.save_config()
        # 应用重置后的设置
        self.apply_appearance_changes()
        for trait, value in self.customization_data['behavior']['personality_traits'].items():
            self.parent.emotion_system.set_personality_trait(trait, value)
    
    def get_available_outfits(self):
        """获取可用的服装列表"""
        return ['default', 'butler', 'casual', 'sleepy', 'festival']
    
    def get_available_accessories(self):
        """获取可用的配饰列表"""
        return ['glasses', 'hat', 'scarf', 'necklace', 'earrings', 'backpack']
    
    def get_available_color_schemes(self):
        """获取可用的配色方案"""
        return ['default', 'pastel', 'dark', 'vibrant', 'monochrome']
    
    def get_available_sizes(self):
        """获取可用的大小选项"""
        return ['small', 'normal', 'large', 'giant']
    
    def get_available_activity_levels(self):
        """获取可用的活跃程度选项"""
        return ['low', 'medium', 'high']
    
    def get_available_interaction_frequencies(self):
        """获取可用的交互频率选项"""
        return ['low', 'medium', 'high']
    
    def get_available_humor_levels(self):
        """获取可用的幽默程度选项"""
        return ['low', 'medium', 'high']
    
    def get_available_formality_levels(self):
        """获取可用的正式程度选项"""
        return ['low', 'medium', 'high']
    
    def get_available_knowledge_areas(self):
        """获取可用的知识领域选项"""
        return ['deltarune', 'undertale', 'games', 'music', 'art', 'science', 'history', 'technology', 'general']
    
    def get_available_interests(self):
        """获取可用的兴趣爱好选项"""
        return ['games', 'music', 'art', 'reading', 'sports', 'cooking', 'travel', 'technology', 'nature', 'science']
    
    def get_available_conversation_topics(self):
        """获取可用的对话话题选项"""
        return ['daily_life', 'hobbies', 'emotions', 'ideas', 'dreams', 'memories', 'future', 'philosophy', 'current_events', 'creative']
    
    def get_available_privacy_levels(self):
        """获取可用的隐私级别选项"""
        return ['minimal', 'essential', 'full']
    
    def get_available_backgrounds(self):
        """获取可用的背景选项"""
        return ['default', 'forest', 'castle', 'city', 'night_sky', 'beach', 'space', 'garden', 'library', 'cafe']
    
    def get_available_lighting_effects(self):
        """获取可用的光照效果选项"""
        return ['default', 'warm', 'cool', 'bright', 'dim', 'sunset', 'sunrise', 'moonlight', 'neon', 'firelight']
    
    def get_available_personality_traits(self):
        """获取可用的个性特质选项"""
        return ['introvert_extrovert', 'optimism_pessimism', 'bravery_caution', 'curiosity', 'loyalty', 'patience', 'creativity', 'empathy', 'playfulness', 'neatness']
    
    def get_available_language_styles(self):
        """获取可用的语言风格选项"""
        return ['formal', 'friendly', 'casual', 'playful', 'serious', 'humorous']
    
    def get_available_response_lengths(self):
        """获取可用的回复长度选项"""
        return ['short', 'medium', 'long', 'verbose']
    
    def get_available_creativity_levels(self):
        """获取可用的创造力级别选项"""
        return ['low', 'medium', 'high', 'very_high']
    
    def get_available_humor_types(self):
        """获取可用的幽默类型选项"""
        return ['dry', 'slapstick', 'witty', 'wholesome', 'sarcastic', 'absurd']
    
    def get_available_environment_locations(self):
        """获取可用的环境位置选项"""
        return ['bedroom', 'living_room', 'office', 'kitchen', 'garden', 'park', 'library', 'cafe', 'beach', 'forest']
    
    def get_available_time_preferences(self):
        """获取可用的时间偏好选项"""
        return ['day', 'night', 'dawn', 'dusk']
    
    def get_available_weather_preferences(self):
        """获取可用的天气偏好选项"""
        return ['sunny', 'cloudy', 'rainy', 'snowy', 'stormy', 'foggy']
    
    def get_available_temperature_preferences(self):
        """获取可用的温度偏好选项"""
        return ['cold', 'cool', 'warm', 'hot']
    
    def get_available_relationship_types(self):
        """获取可用的关系类型选项"""
        return ['friend', 'sibling', 'parent', 'mentor', 'pet', 'partner', 'teacher', 'student', 'colleague', 'adventurer']
    
    def get_available_initiative_levels(self):
        """获取可用的主动性级别选项"""
        return ['low', 'medium', 'high']
    
    def get_available_emotional_intensities(self):
        """获取可用的情感强度选项"""
        return ['low', 'medium', 'high']
    
    def get_available_verbosity_levels(self):
        """获取可用的话唠程度选项"""
        return ['low', 'medium', 'high']
    
    def update_environment(self, environment_settings):
        """更新环境设置"""
        self.customization_data['environment'].update(environment_settings)
        self.save_config()
    
    def update_relationship(self, relationship_settings):
        """更新关系设置"""
        self.customization_data['relationship'].update(relationship_settings)
        self.save_config()
    
    def apply_appearance_changes(self):
        """应用外观变化"""
        # 这里可以添加实际的外观变化应用逻辑
        # 例如：更换服装、调整大小、改变颜色等
        appearance = self.customization_data['appearance']
        print(f"应用外观变化: {appearance}")
        
        # 调整动画速度
        animation_speed = appearance['animation_speed']
        # 更新动画定时器速度
        if hasattr(self.parent, 'animation_timer'):
            original_interval = 100  # 默认100ms
            new_interval = max(50, int(original_interval / animation_speed))
            self.parent.animation_timer.setInterval(new_interval)
        
        # 应用背景变化
        background = appearance['background']
        # 这里可以添加实际的背景变化逻辑
        
        # 应用光照效果变化
        lighting_effects = appearance['lighting_effects']
        # 这里可以添加实际的光照效果变化逻辑
        
        # 应用粒子效果变化
        particle_effects = appearance['particle_effects']
        # 这里可以添加实际的粒子效果变化逻辑
        
        # 应用天气效果变化
        weather_effects = appearance['weather_effects']
        # 这里可以添加实际的天气效果变化逻辑
    
    def apply_behavior_changes(self):
        """应用行为变化"""
        # 应用个性特质到情绪系统
        for trait, value in self.customization_data['behavior']['personality_traits'].items():
            self.parent.emotion_system.set_personality_trait(trait, value)
        
        # 应用其他行为设置
        behavior = self.customization_data['behavior']
        print(f"应用行为变化: {behavior}")
    
    def apply_content_changes(self):
        """应用内容变化"""
        content = self.customization_data['content']
        print(f"应用内容变化: {content}")
    
    def update_behavior(self, behavior_settings):
        """更新行为设置"""
        if 'personality_traits' in behavior_settings:
            # 更新个性特质
            self.customization_data['behavior']['personality_traits'].update(
                behavior_settings['personality_traits']
            )
            # 应用到情绪系统
            for trait, value in behavior_settings['personality_traits'].items():
                self.parent.emotion_system.set_personality_trait(trait, value)
        
        # 更新其他行为设置
        for key, value in behavior_settings.items():
            if key != 'personality_traits':
                self.customization_data['behavior'][key] = value
        
        self.save_config()
        # 应用行为变化
        self.apply_behavior_changes()
    
    def update_content_preferences(self, content_settings):
        """更新内容偏好"""
        self.customization_data['content'].update(content_settings)
        self.save_config()
        # 应用内容变化
        self.apply_content_changes()
    
    def get_available_outfits(self):
        """获取可用的服装列表"""
        return ['default', 'butler', 'casual', 'sleepy', 'festival', 'wizard', 'warrior', 'chef', 'artist', 'student', 'athlete', 'formal', 'halloween', 'christmas', 'spring', 'summer', 'autumn', 'winter']
    
    def get_available_accessories(self):
        """获取可用的配饰列表"""
        return ['glasses', 'hat', 'scarf', 'necklace', 'earrings', 'backpack', 'umbrella', 'flower', 'wings', 'horns', 'tail', 'gloves', 'boots', 'crown', 'scepter', 'book', 'wand', 'broom', 'camera']
    
    def get_available_color_schemes(self):
        """获取可用的配色方案"""
        return ['default', 'pastel', 'dark', 'vibrant', 'monochrome', 'warm', 'cool', 'sunset', 'ocean', 'forest', 'fire', 'ice', 'rainbow', 'gold', 'silver', 'purple', 'pink', 'blue', 'green', 'red', 'orange', 'yellow']
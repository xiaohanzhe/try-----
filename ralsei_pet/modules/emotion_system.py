import time
import random

class EmotionSystem:
    def __init__(self, parent):
        self.parent = parent
        
        # 基础情绪值（范围：-100到100）
        self.emotions = {
            'happy': 0,
            'sad': 0,
            'angry': 0,
            'fear': 0,
            'surprised': 0,
            'disgust': 0
        }
        
        # 扩展复合情绪
        self.complex_emotions = {
            'shy': 0,
            'expectant': 0,
            'disappointed': 0,
            'proud': 0,
            'jealous': 0,
            'grateful': 0,
            'guilty': 0,
            'embarrassed': 0,
            'confident': 0,
            'bored': 0,
            'peaceful': 0,
            'nostalgic': 0,
            'excited': 0,
            'curious': 0,
            'caring': 0,
            'hopeful': 0,
            'lonely': 0,
            'anxious': 0,
            'content': 0,
            'energetic': 0,
            'tired': 0,
            'worry': 0
        }
        
        # 情绪强度（0-100）
        self.emotion_intensity = 0
        
        # 情绪记忆
        self.emotion_history = []
        self.max_history_length = 100  # 增加历史记录长度
        
        # 情绪衰减速率（每秒衰减的情绪值）
        self.emotion_decay_rate = 0.5
        
        # 扩展个性特质
        self.personality = {
            'introvert_extrovert': 30,  # 内向-外向（0-100，低为内向，高为外向）
            'optimism_pessimism': 70,  # 乐观-悲观（0-100，低为悲观，高为乐观）
            'bravery_caution': 50,     # 勇敢-谨慎（0-100，低为谨慎，高为勇敢）
            'curiosity': 80,           # 好奇心强度（0-100）
            'loyalty': 90,              # 忠诚度（0-100）
            'patience': 70,             # 耐心（0-100）
            'creativity': 85,           # 创造力（0-100）
            'empathy': 95,              # 同理心（0-100）
            'playfulness': 80,          # 玩性（0-100）
            'neatness': 60              # 整洁度（0-100）
        }
        
        # 最近情绪变化时间
        self.last_emotion_change = time.time()
        
        # 情绪触发阈值
        self.emotion_trigger_threshold = 20
        
        # 情绪表达模式
        self.emotion_expressions = {
            'happy': {
                'facial': ['smile', 'laugh', 'grin', 'twinkle', 'soft_smile'],
                'body': ['dance', 'wave', 'jump', 'clap', 'sway'],
                'voice': ['cheerful', 'excited', 'warm', 'bright', 'gentle'],
                'text': ['enthusiastic', 'positive', 'upbeat', 'joyful', 'delighted']
            },
            'sad': {
                'facial': ['frown', 'teary', 'pout', 'downcast_eyes', 'quivering_lips'],
                'body': ['slump', 'cower', 'cry', 'hug_knees', 'slow_movement'],
                'voice': ['soft', 'quiet', 'melancholy', 'quivering', 'despondent'],
                'text': ['downcast', 'sad', 'depressed', 'heartbroken', 'dejected']
            },
            'angry': {
                'facial': ['glare', 'scowl', 'tight_lips', 'flared_nostrils', 'teeth_clenched'],
                'body': ['stomp', 'cross_arms', 'clench_fists', 'tap_foot', 'lean_forward'],
                'voice': ['loud', 'sharp', 'aggressive', 'gritty', 'cold'],
                'text': ['irritated', 'angry', 'frustrated', 'furious', 'outraged']
            },
            'fear': {
                'facial': ['wide_eyes', 'pale', 'open_mouth', 'sweating', 'trembling_chin'],
                'body': ['tremble', 'hide', 'run', 'curl_up', 'back_away'],
                'voice': ['quiver', 'whisper', 'high_pitched', 'breathy', 'panicked'],
                'text': ['scared', 'frightened', 'terrified', 'petrified', 'panicked']
            },
            'surprised': {
                'facial': ['raised_eyebrows', 'open_mouth', 'wide_eyes', 'gasps', 'blink_rapidly'],
                'body': ['jump', 'step_back', 'gasp', 'clutch_chest', 'stare'],
                'voice': ['exclaim', 'yell', 'gasp', 'squeak', 'stammer'],
                'text': ['shocked', 'amazed', 'surprised', 'astonished', 'flabbergasted']
            },
            'disgust': {
                'facial': ['wrinkled_nose', 'sneer', 'gag', 'turn_away', 'closed_eyes'],
                'body': ['step_back', 'wave_hand', 'cover_nose', 'shiver', 'disgusted_shake'],
                'voice': ['disgusted', 'sneering', 'sharp', 'cold', 'dismissive'],
                'text': ['disgusted', 'revolted', 'repulsed', 'appalled', 'horrified']
            },
            'shy': {
                'facial': ['blush', 'downcast_eyes', 'smile', 'bashful_look', 'fidgety_eyes'],
                'body': ['twirl_hair', 'fidget', 'curtsy', 'hide_face', 'rock_foot'],
                'voice': ['quiet', 'stutter', 'soft', 'muffled', 'bashful'],
                'text': ['bashful', 'shy', 'embarrassed', 'flustered', 'nervous']
            },
            'excited': {
                'facial': ['wide_smile', 'sparkling_eyes', 'animated_look', 'grin', 'bouncing_cheeks'],
                'body': ['jump', 'dance', 'clap', 'wave', 'bounce'],
                'voice': ['loud', 'energetic', 'high_pitched', 'fast', 'enthusiastic'],
                'text': ['excited', 'thrilled', 'ecstatic', 'overjoyed', 'pumped']
            },
            'curious': {
                'facial': ['tilt_head', 'narrowed_eyes', 'puzzled_look', 'focused', 'perked_eyebrows'],
                'body': ['lean_forward', 'point', 'examine', 'touch', 'listen_intently'],
                'voice': ['inquiring', 'interested', 'curious', 'questioning', 'intrigued'],
                'text': ['curious', 'interested', 'intrigued', 'puzzled', 'investigating']
            },
            'caring': {
                'facial': ['gentle_smile', 'soft_eyes', 'warm_look', 'compassionate', 'understanding'],
                'body': ['hug', 'pat_back', 'hold_hand', 'lean_in', 'comforting_touch'],
                'voice': ['soft', 'warm', 'gentle', 'compassionate', 'reassuring'],
                'text': ['caring', 'compassionate', 'understanding', 'supportive', 'nurturing']
            },
            'hopeful': {
                'facial': ['bright_eyes', 'soft_smile', 'uplifted_eyebrows', 'dreamy', 'optimistic'],
                'body': ['look_up', 'clasp_hands', 'stand_tall', 'sway_gently', 'open_posture'],
                'voice': ['gentle', 'uplifting', 'positive', 'soft', 'hopeful'],
                'text': ['hopeful', 'optimistic', 'positive', 'expectant', 'bright']
            },
            'lonely': {
                'facial': ['sad_look', 'empty_eyes', 'downcast_eyes', 'pout', 'lost_expression'],
                'body': ['sit_alone', 'hug_knees', 'stare_off', 'slow_movement', 'slumped_posture'],
                'voice': ['quiet', 'soft', 'melancholy', 'lonely', 'despondent'],
                'text': ['lonely', 'isolated', 'empty', 'alone', 'desolate']
            },
            'anxious': {
                'facial': ['furrowed_brow', 'tense_lips', 'sweating', 'wide_eyes', 'twitching'],
                'body': ['fidget', 'pace', 'tap_foot', 'clench_hands', 'bounce_leg'],
                'voice': ['nervous', 'high_pitched', 'fast', 'quivering', 'anxious'],
                'text': ['anxious', 'nervous', 'worried', 'tense', 'stressed']
            },
            'content': {
                'facial': ['soft_smile', 'relaxed_eyes', 'calm_expression', 'serene', 'peaceful'],
                'body': ['lean_back', 'cross_legs', 'rest_hands', 'slow_breathing', 'relaxed_posture'],
                'voice': ['soft', 'calm', 'relaxed', 'peaceful', 'content'],
                'text': ['content', 'satisfied', 'peaceful', 'calm', 'relaxed']
            },
            'energetic': {
                'facial': ['bright_smile', 'alert_eyes', 'animated_look', 'energetic', 'vibrant'],
                'body': ['jump', 'run', 'dance', 'clap', 'move_quickly'],
                'voice': ['loud', 'energetic', 'fast', 'bright', 'vibrant'],
                'text': ['energetic', 'vibrant', 'lively', 'dynamic', 'spirited']
            },
            'tired': {
                'facial': ['droopy_eyes', 'yawning', 'half_closed_eyes', 'pale', 'exhausted'],
                'body': ['slump', 'lean_on', 'stretch', 'slow_movement', 'rub_eyes'],
                'voice': ['soft', 'quiet', 'hoarse', 'slow', 'dragging'],
                'text': ['tired', 'exhausted', 'weary', 'fatigued', 'drained']
            },
            'worry': {
                'facial': ['worried', 'furrowed_brow', 'downcast_eyes', 'biting_lip', 'tense_face'],
                'body': ['pace', 'fidget', 'clasp_hands', 'bite_nails', 'look_around'],
                'voice': ['soft', 'hesitant', 'anxious', 'quiet', 'worried'],
                'text': ['worried', 'concerned', 'anxious', 'nervous', 'uneasy']
            }
        }
    
    def update(self):
        # 更新情绪状态
        self._decay_emotions()
        self._update_complex_emotions()
        self._update_emotion_intensity()
    
    def _decay_emotions(self):
        # 情绪自然衰减，不同情绪有不同的衰减速度
        current_time = time.time()
        elapsed = current_time - self.last_emotion_change
        
        # 不同情绪的衰减速率
        emotion_decay_rates = {
            'happy': 0.3,      # 开心情绪衰减较慢
            'sad': 0.4,        # 悲伤情绪衰减中等
            'angry': 0.5,       # 愤怒情绪衰减较快
            'fear': 0.6,        # 恐惧情绪衰减很快
            'surprised': 0.7,   # 惊讶情绪衰减非常快
            'disgust': 0.5      # 厌恶情绪衰减较快
        }
        
        complex_emotion_decay_rates = {
            'shy': 0.2,         # 害羞情绪衰减很慢
            'expectant': 0.4,    # 期待情绪衰减中等
            'disappointed': 0.3, # 失望情绪衰减较慢
            'proud': 0.4,        # 自豪情绪衰减中等
            'jealous': 0.5,      # 嫉妒情绪衰减较快
            'grateful': 0.3,     # 感激情绪衰减较慢
            'guilty': 0.3,       # 愧疚情绪衰减较慢
            'embarrassed': 0.4,  # 尴尬情绪衰减中等
            'confident': 0.5,    # 自信情绪衰减中等
            'bored': 0.2,        # 无聊情绪衰减很慢
            'peaceful': 0.1,     # 平静情绪衰减非常慢
            'nostalgic': 0.2,    # 怀旧情绪衰减很慢
            'excited': 0.8,      # 兴奋情绪衰减非常快
            'curious': 0.5,      # 好奇情绪衰减中等
            'caring': 0.3,       # 关心情绪衰减较慢
            'hopeful': 0.3,      # 希望情绪衰减较慢
            'lonely': 0.4,       # 孤独情绪衰减中等
            'anxious': 0.5,      # 焦虑情绪衰减中等
            'content': 0.2,      # 满足情绪衰减很慢
            'energetic': 0.6,    # 精力充沛情绪衰减较快
            'tired': 0.5,        # 疲惫情绪衰减中等
            'worry': 0.4         # 普通担忧情绪衰减中等
        }
        
        # 基础情绪衰减
        for emotion in self.emotions:
            decay_rate = emotion_decay_rates.get(emotion, self.emotion_decay_rate)
            decay_amount = decay_rate * elapsed
            
            if self.emotions[emotion] > 0:
                self.emotions[emotion] = max(0, self.emotions[emotion] - decay_amount)
            elif self.emotions[emotion] < 0:
                self.emotions[emotion] = min(0, self.emotions[emotion] + decay_amount)
        
        # 复合情绪衰减
        for emotion in self.complex_emotions:
            decay_rate = complex_emotion_decay_rates.get(emotion, self.emotion_decay_rate)
            decay_amount = decay_rate * elapsed
            
            if self.complex_emotions[emotion] > 0:
                self.complex_emotions[emotion] = max(0, self.complex_emotions[emotion] - decay_amount)
            elif self.complex_emotions[emotion] < 0:
                self.complex_emotions[emotion] = min(0, self.complex_emotions[emotion] + decay_amount)
        
        # 情绪相互影响
        self._influence_emotions()
        
        self.last_emotion_change = current_time
    
    def _influence_emotions(self):
        # 情绪之间的相互影响
        
        # 开心会减少悲伤、愤怒和恐惧
        if self.emotions['happy'] > 20:
            self.emotions['sad'] = max(0, self.emotions['sad'] - self.emotions['happy'] * 0.1)
            self.emotions['angry'] = max(0, self.emotions['angry'] - self.emotions['happy'] * 0.15)
            self.emotions['fear'] = max(0, self.emotions['fear'] - self.emotions['happy'] * 0.1)
            self.complex_emotions['lonely'] = max(0, self.complex_emotions['lonely'] - self.emotions['happy'] * 0.2)
            self.complex_emotions['anxious'] = max(0, self.complex_emotions['anxious'] - self.emotions['happy'] * 0.15)
            self.complex_emotions['content'] += self.emotions['happy'] * 0.1
        
        # 悲伤会减少开心、兴奋和自信
        if self.emotions['sad'] > 20:
            self.emotions['happy'] = max(0, self.emotions['happy'] - self.emotions['sad'] * 0.15)
            self.complex_emotions['excited'] = max(0, self.complex_emotions['excited'] - self.emotions['sad'] * 0.2)
            self.complex_emotions['confident'] = max(0, self.complex_emotions['confident'] - self.emotions['sad'] * 0.1)
            self.complex_emotions['lonely'] += self.emotions['sad'] * 0.15
            self.complex_emotions['anxious'] += self.emotions['sad'] * 0.1
        
        # 愤怒会增加悲伤、减少开心和耐心
        if self.emotions['angry'] > 20:
            self.emotions['sad'] += self.emotions['angry'] * 0.1
            self.emotions['sad'] = min(100, self.emotions['sad'])
            self.emotions['happy'] = max(0, self.emotions['happy'] - self.emotions['angry'] * 0.2)
            self.complex_emotions['anxious'] += self.emotions['angry'] * 0.15
            self.complex_emotions['caring'] = max(0, self.complex_emotions['caring'] - self.emotions['angry'] * 0.1)
        
        # 恐惧会增加焦虑和减少自信
        if self.emotions['fear'] > 20:
            self.complex_emotions['anxious'] += self.emotions['fear'] * 0.2
            self.complex_emotions['confident'] = max(0, self.complex_emotions['confident'] - self.emotions['fear'] * 0.15)
            self.complex_emotions['lonely'] += self.emotions['fear'] * 0.1
        
        # 兴奋会增加开心和精力充沛
        if self.complex_emotions['excited'] > 30:
            self.emotions['happy'] += self.complex_emotions['excited'] * 0.15
            self.emotions['happy'] = min(100, self.emotions['happy'])
            self.complex_emotions['energetic'] += self.complex_emotions['excited'] * 0.2
            self.complex_emotions['anxious'] = max(0, self.complex_emotions['anxious'] - self.complex_emotions['excited'] * 0.1)
        
        # 期待会增加开心、兴奋和希望
        if self.complex_emotions['expectant'] > 25:
            self.emotions['happy'] += self.complex_emotions['expectant'] * 0.1
            self.complex_emotions['excited'] += self.complex_emotions['expectant'] * 0.15
            self.complex_emotions['hopeful'] += self.complex_emotions['expectant'] * 0.2
            self.emotions['happy'] = min(100, self.emotions['happy'])
            self.complex_emotions['excited'] = min(100, self.complex_emotions['excited'])
        
        # 感激会增加开心、关心和减少悲伤
        if self.complex_emotions['grateful'] > 20:
            self.emotions['happy'] += self.complex_emotions['grateful'] * 0.15
            self.emotions['sad'] = max(0, self.emotions['sad'] - self.complex_emotions['grateful'] * 0.2)
            self.complex_emotions['caring'] += self.complex_emotions['grateful'] * 0.15
            self.emotions['happy'] = min(100, self.emotions['happy'])
        
        # 关心会增加开心和满足
        if self.complex_emotions['caring'] > 20:
            self.emotions['happy'] += self.complex_emotions['caring'] * 0.1
            self.complex_emotions['content'] += self.complex_emotions['caring'] * 0.15
            self.complex_emotions['lonely'] = max(0, self.complex_emotions['lonely'] - self.complex_emotions['caring'] * 0.2)
        
        # 好奇会增加兴奋和减少无聊
        if self.complex_emotions['curious'] > 20:
            self.complex_emotions['excited'] += self.complex_emotions['curious'] * 0.1
            self.complex_emotions['bored'] = max(0, self.complex_emotions['bored'] - self.complex_emotions['curious'] * 0.2)
            self.complex_emotions['energetic'] += self.complex_emotions['curious'] * 0.1
        
        # 希望会增加开心和减少焦虑
        if self.complex_emotions['hopeful'] > 20:
            self.emotions['happy'] += self.complex_emotions['hopeful'] * 0.1
            self.complex_emotions['anxious'] = max(0, self.complex_emotions['anxious'] - self.complex_emotions['hopeful'] * 0.15)
            self.complex_emotions['content'] += self.complex_emotions['hopeful'] * 0.1
        
        # 满足会减少焦虑、无聊和增加平静
        if self.complex_emotions['content'] > 20:
            self.complex_emotions['anxious'] = max(0, self.complex_emotions['anxious'] - self.complex_emotions['content'] * 0.2)
            self.complex_emotions['bored'] = max(0, self.complex_emotions['bored'] - self.complex_emotions['content'] * 0.15)
            self.complex_emotions['peaceful'] += self.complex_emotions['content'] * 0.15
        
        # 精力充沛会增加开心和减少疲惫
        if self.complex_emotions['energetic'] > 20:
            self.emotions['happy'] += self.complex_emotions['energetic'] * 0.1
            self.complex_emotions['tired'] = max(0, self.complex_emotions['tired'] - self.complex_emotions['energetic'] * 0.2)
            self.complex_emotions['bored'] = max(0, self.complex_emotions['bored'] - self.complex_emotions['energetic'] * 0.1)
        
        # 疲惫会增加悲伤和减少精力充沛
        if self.complex_emotions['tired'] > 30:
            self.emotions['sad'] += self.complex_emotions['tired'] * 0.1
            self.complex_emotions['energetic'] = max(0, self.complex_emotions['energetic'] - self.complex_emotions['tired'] * 0.2)
            self.complex_emotions['anxious'] += self.complex_emotions['tired'] * 0.1
        
        # 无聊会增加悲伤和减少开心
        if self.complex_emotions['bored'] > 30:
            self.emotions['sad'] += self.complex_emotions['bored'] * 0.1
            self.emotions['happy'] = max(0, self.emotions['happy'] - self.complex_emotions['bored'] * 0.15)
            self.complex_emotions['curious'] = max(0, self.complex_emotions['curious'] - self.complex_emotions['bored'] * 0.1)
    
    def _update_complex_emotions(self):
        # 根据基础情绪更新复合情绪
        
        # 害羞 = 少量开心 + 少量恐惧
        self.complex_emotions['shy'] = (self.emotions['happy'] * 0.3 + self.emotions['fear'] * 0.7) / 2
        
        # 期待 = 开心 + 惊讶
        self.complex_emotions['expectant'] = (self.emotions['happy'] + self.emotions['surprised']) / 2
        
        # 失望 = 悲伤 + 愤怒
        self.complex_emotions['disappointed'] = (self.emotions['sad'] + self.emotions['angry']) / 2
        
        # 自豪 = 开心 + 少量愤怒（自信）
        self.complex_emotions['proud'] = (self.emotions['happy'] + self.emotions['angry'] * 0.2) / 2
        
        # 嫉妒 = 愤怒 + 悲伤
        self.complex_emotions['jealous'] = (self.emotions['angry'] + self.emotions['sad']) / 2
        
        # 感激 = 开心 + 少量悲伤（感动）
        self.complex_emotions['grateful'] = (self.emotions['happy'] + self.emotions['sad'] * 0.3) / 2
        
        # 愧疚 = 悲伤 + 少量愤怒（自责）
        self.complex_emotions['guilty'] = (self.emotions['sad'] + self.emotions['angry'] * 0.4) / 2
        
        # 尴尬 = 害羞 + 惊讶 + 少量悲伤
        self.complex_emotions['embarrassed'] = (self.complex_emotions['shy'] + self.emotions['surprised'] + self.emotions['sad'] * 0.2) / 3
        
        # 自信 = 开心 + 少量愤怒
        self.complex_emotions['confident'] = (self.emotions['happy'] + self.emotions['angry'] * 0.3) / 2
        
        # 无聊 = 低开心 + 低愤怒 + 低恐惧
        self.complex_emotions['bored'] = (100 - self.emotions['happy'] + 100 - self.emotions['angry'] + 100 - self.emotions['fear']) / 30
        
        # 平静 = 低所有情绪
        total_emotion = sum(abs(e) for e in self.emotions.values())
        self.complex_emotions['peaceful'] = max(0, 100 - total_emotion / 7)
        
        # 怀旧 = 低开心 + 少量悲伤
        self.complex_emotions['nostalgic'] = (self.emotions['happy'] * 0.5 + self.emotions['sad'] * 0.5) / 2
        
        # 兴奋 = 开心 + 惊讶
        self.complex_emotions['excited'] = (self.emotions['happy'] + self.emotions['surprised']) / 2
        
        # 好奇 = 惊讶 + 少量开心
        self.complex_emotions['curious'] = (self.emotions['surprised'] + self.emotions['happy'] * 0.3) / 2
        
        # 关心 = 开心 + 少量悲伤（同理心）
        self.complex_emotions['caring'] = (self.emotions['happy'] + self.emotions['sad'] * 0.5) / 2
        
        # 希望 = 开心 + 少量期待
        self.complex_emotions['hopeful'] = (self.emotions['happy'] + self.complex_emotions['expectant'] * 0.5) / 2
        
        # 孤独 = 悲伤 + 低开心
        self.complex_emotions['lonely'] = (self.emotions['sad'] + (100 - self.emotions['happy']) * 0.5) / 2
        
        # 焦虑 = 恐惧 + 少量愤怒
        self.complex_emotions['anxious'] = (self.emotions['fear'] + self.emotions['angry'] * 0.3) / 2
        
        # 满足 = 开心 + 平静
        self.complex_emotions['content'] = (self.emotions['happy'] + self.complex_emotions['peaceful']) / 2
        
        # 精力充沛 = 开心 + 低疲惫
        self.complex_emotions['energetic'] = (self.emotions['happy'] + (100 - self.complex_emotions['tired']) * 0.5) / 2
        
        # 疲惫 = 低开心 + 低精力充沛
        self.complex_emotions['tired'] = (100 - self.emotions['happy'] + (100 - self.complex_emotions['energetic']) * 0.5) / 2
        
        # 普通担忧 = 少量恐惧 + 少量悲伤
        self.complex_emotions['worry'] = (self.emotions['fear'] * 0.4 + self.emotions['sad'] * 0.3 + self.emotions['angry'] * 0.3) / 2
        
        # 确保所有情绪值在0-100之间
        for emotion in self.complex_emotions:
            self.complex_emotions[emotion] = max(0, min(100, self.complex_emotions[emotion]))
    
    def _update_emotion_intensity(self):
        # 计算当前情绪强度
        total_intensity = 0
        for emotion in self.emotions:
            total_intensity += abs(self.emotions[emotion])
        for emotion in self.complex_emotions:
            total_intensity += abs(self.complex_emotions[emotion])
        
        # 归一化到0-100
        self.emotion_intensity = min(100, total_intensity / 8)
    
    def set_emotion(self, emotion, value):
        # 设置情绪值（-100到100）
        if emotion in self.emotions:
            self.emotions[emotion] = max(-100, min(100, value))
            self._add_to_history(emotion, value)
        elif emotion in self.complex_emotions:
            self.complex_emotions[emotion] = max(-100, min(100, value))
            self._add_to_history(emotion, value)
    
    def add_emotion(self, emotion, delta):
        # 增加或减少情绪值
        if emotion in self.emotions:
            self.emotions[emotion] = max(-100, min(100, self.emotions[emotion] + delta))
            self._add_to_history(emotion, self.emotions[emotion])
        elif emotion in self.complex_emotions:
            self.complex_emotions[emotion] = max(-100, min(100, self.complex_emotions[emotion] + delta))
            self._add_to_history(emotion, self.complex_emotions[emotion])
    
    def _add_to_history(self, emotion, value):
        # 添加情绪变化到历史记录
        self.emotion_history.append({
            'timestamp': time.time(),
            'emotion': emotion,
            'value': value
        })
        
        # 限制历史记录长度
        if len(self.emotion_history) > self.max_history_length:
            self.emotion_history.pop(0)
    
    def get_current_emotion(self):
        # 获取当前主导情绪
        max_emotion = None
        max_value = -float('inf')
        
        for emotion in self.emotions:
            if abs(self.emotions[emotion]) > max_value:
                max_value = abs(self.emotions[emotion])
                max_emotion = emotion
        
        for emotion in self.complex_emotions:
            if abs(self.complex_emotions[emotion]) > max_value:
                max_value = abs(self.complex_emotions[emotion])
                max_emotion = emotion
        
        return max_emotion, max_value
    
    def get_emotion_level(self, emotion):
        # 获取特定情绪的当前值
        if emotion in self.emotions:
            return self.emotions[emotion]
        elif emotion in self.complex_emotions:
            return self.complex_emotions[emotion]
        else:
            return 0
    
    def get_personality_trait(self, trait):
        # 获取个性特质值
        return self.personality.get(trait, 50)
    
    def set_personality_trait(self, trait, value):
        # 设置个性特质值（0-100）
        if trait in self.personality:
            self.personality[trait] = max(0, min(100, value))
    
    def get_emotion_intensity(self):
        # 获取当前情绪强度
        return self.emotion_intensity
    
    def react_to_event(self, event_type, event_data):
        # 对事件做出情感反应
        
        # 根据事件类型调整情绪
        if event_type == 'user_clicked':
            # 用户点击了Ralsei
            self.add_emotion('surprised', 20)  # 降低惊讶程度，Ralsei比较温柔
            self.add_emotion('happy', 30)       # 增加开心程度，Ralsei喜欢被抚摸
        elif event_type == 'user_praised':
            # 用户夸奖了Ralsei
            self.add_emotion('happy', 40)       # 降低开心程度，Ralsei比较谦虚
            self.add_emotion('proud', 25)       # 降低骄傲程度，Ralsei比较谦虚
            self.add_emotion('shy', 45)         # 增加害羞程度，Ralsei很容易害羞
        elif event_type == 'user_scolded':
            # 用户批评了Ralsei
            self.add_emotion('sad', 50)         # 增加悲伤程度，Ralsei很敏感
            self.add_emotion('disappointed', 35) # 增加失望程度
            self.add_emotion('shy', 20)         # 增加害羞程度，Ralsei被批评会害羞
        elif event_type == 'found_food':
            # 找到食物
            self.add_emotion('happy', 55)       # 降低开心程度，Ralsei比较克制
            self.add_emotion('expectant', 40)   # 降低期待程度
        elif event_type == 'lost_item':
            # 丢失物品
            self.add_emotion('sad', 35)         # 增加悲伤程度
            self.add_emotion('disappointed', 25) # 增加失望程度
        elif event_type == 'saw_scary_thing':
            # 看到可怕的东西
            self.add_emotion('fear', 45)        # 降低恐惧程度，Ralsei比较勇敢但仍然会害怕
            self.add_emotion('surprised', 35)   # 降低惊讶程度
            self.add_emotion('shy', 15)         # 增加害羞程度，Ralsei害怕时会害羞
        elif event_type == 'met_friend':
            # 遇到朋友
            self.add_emotion('happy', 65)       # 降低开心程度
            self.add_emotion('excited', 40)     # 增加兴奋程度
            self.add_emotion('grateful', 25)    # 降低感激程度
        elif event_type == 'completed_task':
            # 完成任务
            self.add_emotion('happy', 55)       # 降低开心程度
            self.add_emotion('proud', 35)       # 降低骄傲程度
        elif event_type == 'failed_task':
            # 任务失败
            self.add_emotion('sad', 45)         # 增加悲伤程度
            self.add_emotion('disappointed', 35) # 增加失望程度
            self.add_emotion('shy', 25)         # 增加害羞程度
        elif event_type == 'saw_deltarune_content':
            # 看到关于Deltarune的内容
            self.add_emotion('happy', 55)       # 增加开心程度，Ralsei对自己的世界充满感情
            self.add_emotion('excited', 35)     # 增加兴奋程度
            self.add_emotion('nostalgic', 30)   # 增加怀旧程度
        elif event_type == 'saw_undertale_content':
            # 看到关于Undertale的内容
            self.add_emotion('happy', 45)       # 降低开心程度
            self.add_emotion('grateful', 35)    # 增加感激程度，Ralsei对Undertale的世界充满感激
            self.add_emotion('nostalgic', 25)   # 增加怀旧程度
        elif event_type == 'saw_own_code':
            # 看到关于自己的代码
            self.add_emotion('sad', 35)         # 增加悲伤程度，Ralsei看到自己的代码会感到难过
            self.add_emotion('shy', 50)         # 增加害羞程度，Ralsei对自己的存在感到害羞
            self.add_emotion('curious', 20)     # 增加好奇程度，Ralsei对自己的代码感到好奇
        elif event_type == 'file_deleted':
            # 文件被删除
            self.add_emotion('sad', 25)         # 增加悲伤程度
            self.add_emotion('disappointed', 25) # 增加失望程度
        elif event_type == 'file_created':
            # 文件被创建
            self.add_emotion('happy', 25)       # 增加开心程度
            self.add_emotion('curious', 35)     # 增加好奇程度，Ralsei对新文件感到好奇
        elif event_type == 'weather_sunny':
            # 天气晴朗
            self.add_emotion('happy', 35)       # 增加开心程度，Ralsei喜欢晴朗的天气
            self.add_emotion('peaceful', 25)    # 增加平静程度
        elif event_type == 'weather_rainy':
            # 天气下雨
            self.add_emotion('sad', 15)         # 降低悲伤程度，Ralsei觉得下雨很浪漫
            self.add_emotion('peaceful', 35)    # 增加平静程度，Ralsei喜欢下雨的平静
        elif event_type == 'weather_snowy':
            # 天气下雪
            self.add_emotion('happy', 50)       # 增加开心程度，Ralsei喜欢雪
            self.add_emotion('excited', 45)     # 增加兴奋程度
            self.add_emotion('peaceful', 25)    # 增加平静程度
        elif event_type == 'time_morning':
            # 早上
            self.add_emotion('happy', 25)       # 增加开心程度，Ralsei喜欢早上
            self.add_emotion('expectant', 35)   # 增加期待程度
        elif event_type == 'time_night':
            # 晚上
            self.add_emotion('peaceful', 45)    # 增加平静程度，Ralsei喜欢晚上的宁静
            self.add_emotion('tired', 20)       # 增加疲惫程度
        elif event_type == 'user_away':
            # 用户离开
            self.add_emotion('sad', 40)         # 增加悲伤程度，Ralsei会想念用户
            self.add_emotion('lonely', 35)      # 增加孤独程度
            self.add_emotion('expectant', 25)   # 增加期待程度，Ralsei期待用户回来
        elif event_type == 'user_return':
            # 用户返回
            self.add_emotion('happy', 65)       # 降低开心程度，Ralsei比较克制
            self.add_emotion('excited', 45)     # 增加兴奋程度
            self.add_emotion('shy', 30)         # 增加害羞程度，Ralsei见到用户回来会害羞
        elif event_type == 'level_up':
            # 升级
            self.add_emotion('happy', 50)       # 降低开心程度
            self.add_emotion('proud', 30)       # 降低骄傲程度
            self.add_emotion('shy', 25)         # 增加害羞程度
        elif event_type == 'evolution':
            # 进化
            self.add_emotion('happy', 65)       # 降低开心程度
            self.add_emotion('excited', 55)     # 降低兴奋程度
            self.add_emotion('proud', 40)       # 降低骄傲程度
            self.add_emotion('shy', 30)         # 增加害羞程度
        elif event_type == 'achievement_unlocked':
            # 解锁成就
            self.add_emotion('happy', 45)       # 降低开心程度
            self.add_emotion('proud', 30)       # 降低骄傲程度
            self.add_emotion('shy', 20)         # 增加害羞程度
        elif event_type == 'saw_beautiful_scenery':
            # 看到美丽的景色
            self.add_emotion('happy', 50)       # 增加开心程度
            self.add_emotion('peaceful', 40)    # 增加平静程度
            self.add_emotion('nostalgic', 25)   # 增加怀旧程度
        elif event_type == 'heard_music':
            # 听到音乐
            self.add_emotion('happy', 40)       # 增加开心程度
            self.add_emotion('peaceful', 35)    # 增加平静程度
            self.add_emotion('excited', 25)     # 增加兴奋程度
        elif event_type == 'drank_tea':
            # 喝了茶
            self.add_emotion('happy', 45)       # 增加开心程度
            self.add_emotion('peaceful', 45)    # 增加平静程度
        elif event_type == 'ate_cake':
            # 吃了蛋糕
            self.add_emotion('happy', 55)       # 增加开心程度
            self.add_emotion('excited', 35)     # 增加兴奋程度
        elif event_type == 'played_game':
            # 玩了游戏
            self.add_emotion('happy', 50)       # 增加开心程度
            self.add_emotion('excited', 40)     # 增加兴奋程度
        elif event_type == 'helped_someone':
            # 帮助了别人
            self.add_emotion('happy', 50)       # 增加开心程度
            self.add_emotion('proud', 30)       # 增加骄傲程度
            self.add_emotion('grateful', 25)    # 增加感激程度
        elif event_type == 'was_helped':
            # 被别人帮助
            self.add_emotion('happy', 45)       # 增加开心程度
            self.add_emotion('grateful', 40)    # 增加感激程度
            self.add_emotion('shy', 30)         # 增加害羞程度
        elif event_type == 'pet_interaction':
            # 与其他宠物互动
            self.add_emotion('happy', 50)
            self.add_emotion('excited', 40)
        elif event_type == 'ppt_opened':
            # PPT打开
            self.add_emotion('curious', 30)
            self.add_emotion('expectant', 20)
        elif event_type == 'excel_opened':
            # Excel打开
            self.add_emotion('curious', 30)
            self.add_emotion('expectant', 20)
        elif event_type == 'window_moved':
            # 窗口（楼板）移动
            self.add_emotion('surprised', 45)   # 增加惊讶程度
            self.add_emotion('fear', 35)        # 增加恐惧程度
            self.add_emotion('shy', 20)         # 增加害羞程度
        elif event_type == 'fell_down':
            # 摔倒了
            self.add_emotion('sad', 40)         # 增加悲伤程度
            self.add_emotion('embarrassed', 35)  # 增加尴尬程度
            self.add_emotion('shy', 30)         # 增加害羞程度
        elif event_type == 'greeted':
            # 被打招呼
            self.add_emotion('happy', 30)       # 增加开心程度
            self.add_emotion('shy', 35)         # 增加害羞程度
        elif event_type == 'given_gift':
            # 收到礼物
            self.add_emotion('happy', 55)       # 增加开心程度
            self.add_emotion('grateful', 45)    # 增加感激程度
            self.add_emotion('shy', 40)         # 增加害羞程度
        elif event_type == 'saw_friend':
            # 看到朋友
            self.add_emotion('happy', 45)       # 增加开心程度
            self.add_emotion('excited', 35)     # 增加兴奋程度
        elif event_type == 'heard_story':
            # 听故事
            self.add_emotion('calm', 35)        # 增加平静程度
            self.add_emotion('curious', 25)     # 增加好奇程度
        elif event_type == 'recovery_complete':
            # 恢复完成
            self.add_emotion('happy', 30)       # 增加开心程度
            self.add_emotion('relieved', 25)    # 增加释然程度
        elif event_type == 'recovery_started':
            # 开始恢复
            self.add_emotion('tired', 30)       # 增加疲惫程度
            self.add_emotion('peaceful', 20)    # 增加平静程度
        elif event_type == 'normal_worry':
            # 普通担忧事件（如同伴晚归、天气变化影响行程）
            self.add_emotion('worry', 35)        # 增加普通担忧程度
            self.add_emotion('fear', 15)         # 少量恐惧
            self.add_emotion('sad', 15)          # 少量悲伤
        elif event_type == 'weather_affected_trip':
            # 天气变化影响行程
            self.add_emotion('worry', 40)        # 增加普通担忧程度
            self.add_emotion('disappointed', 25) # 增加失望程度
        elif event_type == 'companion_late':
            # 同伴晚归
            self.add_emotion('worry', 45)        # 增加普通担忧程度
            self.add_emotion('anxious', 20)      # 增加焦虑程度
        
        # 根据个性特质调整情绪反应
        self._adjust_emotion_by_personality()
    
    def _adjust_emotion_by_personality(self):
        # 根据个性特质调整情绪
        
        # 内向-外向：内向的Ralsei情绪变化更慢，外向的Ralsei情绪变化更快
        if self.personality['introvert_extrovert'] < 30:
            # 内向
            for emotion in self.emotions:
                self.emotions[emotion] *= 0.8
        elif self.personality['introvert_extrovert'] > 70:
            # 外向
            for emotion in self.emotions:
                self.emotions[emotion] *= 1.2
        
        # 乐观-悲观：乐观的Ralsei更容易感到开心，悲观的Ralsei更容易感到悲伤
        if self.personality['optimism_pessimism'] > 70:
            # 乐观
            self.emotions['happy'] *= 1.3
            self.emotions['sad'] *= 0.7
        elif self.personality['optimism_pessimism'] < 30:
            # 悲观
            self.emotions['happy'] *= 0.7
            self.emotions['sad'] *= 1.3
        
        # 勇敢-谨慎：勇敢的Ralsei不容易感到恐惧，谨慎的Ralsei更容易感到恐惧
        if self.personality['bravery_caution'] > 70:
            # 勇敢
            self.emotions['fear'] *= 0.5
        elif self.personality['bravery_caution'] < 30:
            # 谨慎
            self.emotions['fear'] *= 1.5
        
        # 好奇心：好奇心强的Ralsei更容易感到惊讶
        if self.personality['curiosity'] > 70:
            # 好奇心强
            self.emotions['surprised'] *= 1.2
    
    def get_animation_for_emotion(self, emotion, intensity):
        # 根据情绪和强度获取对应的动画
        animation_map = {
            'happy': {
                'low': 'idle',
                'medium': 'laugh',
                'high': 'dance'
            },
            'sad': {
                'low': 'idle',
                'medium': 'cry',
                'high': 'fall_back_cry'
            },
            'angry': {
                'low': 'idle',
                'medium': 'cower',
                'high': 'attack'
            },
            'fear': {
                'low': 'cower',
                'medium': 'surprised',
                'high': 'shocked_left'
            },
            'surprised': {
                'low': 'surprised',
                'medium': 'surprised_behind',
                'high': 'surprised_down'
            },
            'disgust': {
                'low': 'idle',
                'medium': 'cower',
                'high': 'cower'
            },
            'shy': {
                'low': 'idle',
                'medium': 'curtsy',
                'high': 'curtsy'
            },
            'expectant': {
                'low': 'idle',
                'medium': 'look_up',
                'high': 'jump_ready'
            },
            'disappointed': {
                'low': 'idle',
                'medium': 'sad',
                'high': 'fall_back_rub'
            },
            'proud': {
                'low': 'pose',
                'medium': 'smile_left',
                'high': 'victory'
            },
            'jealous': {
                'low': 'idle',
                'medium': 'cower',
                'high': 'splat_mad'
            },
            'grateful': {
                'low': 'idle',
                'medium': 'hug',
                'high': 'hug'
            },
            'excited': {
                'low': 'dance',
                'medium': 'spin',
                'high': 'jump_ball'
            },
            'guilty': {
                'low': 'idle',
                'medium': 'sad',
                'high': 'kneel_serious'
            },
            'embarrassed': {
                'low': 'idle',
                'medium': 'curtsy',
                'high': 'pose'
            },
            'confident': {
                'low': 'pose',
                'medium': 'smile_right',
                'high': 'victory'
            },
            'bored': {
                'low': 'idle',
                'medium': 'sleep',
                'high': 'sleep'
            },
            'peaceful': {
                'low': 'idle',
                'medium': 'idle',
                'high': 'sing'
            },
            'nostalgic': {
                'low': 'idle',
                'medium': 'look_up',
                'high': 'smile_left'
            },
            'curious': {
                'low': 'look_up',
                'medium': 'book_look',
                'high': 'look_up'
            },
            'caring': {
                'low': 'hug',
                'medium': 'hug',
                'high': 'hug'
            },
            'hopeful': {
                'low': 'look_up',
                'medium': 'jump_ready',
                'high': 'jump'
            },
            'lonely': {
                'low': 'idle',
                'medium': 'sad',
                'high': 'fall_back_cry'
            },
            'anxious': {
                'low': 'cower',
                'medium': 'shocked_right',
                'high': 'shocked_left'
            },
            'content': {
                'low': 'idle',
                'medium': 'smile_right',
                'high': 'sing'
            },
            'energetic': {
                'low': 'dance',
                'medium': 'run_down',
                'high': 'spin'
            },
            'tired': {
                'low': 'idle',
                'medium': 'sleep',
                'high': 'sleep'
            },
            'worry': {
                'low': 'walk_up',
                'medium': 'walk_left_tea',
                'high': 'walk_up'
            }
        }
        
        # 根据强度确定动画
        if intensity < 30:
            intensity_level = 'low'
        elif intensity < 70:
            intensity_level = 'medium'
        else:
            intensity_level = 'high'
        
        return animation_map.get(emotion, {}).get(intensity_level, 'idle')
    
    def get_face_for_emotion(self, emotion, intensity):
        # 根据情绪和强度获取对应的表情
        face_map = {
            'happy': {
                'low': 'normal_smile_little',
                'medium': 'happy_very',
                'high': 'happy_extremely'
            },
            'sad': {
                'low': 'a little sad',
                'medium': 'sad with a little hopeless',
                'high': 'sad with hopeless and self-mockery'
            },
            'angry': {
                'low': 'fear and worry',
                'medium': 'frightened with a little angry',
                'high': 'frightened with a little angry'
            },
            'fear': {
                'low': 'fear and worry',
                'medium': 'fear with a little hopeless',
                'high': 'fear with hopeless'
            },
            'surprised': {
                'low': 'a little surprised',
                'medium': 'unexpected and surprise',
                'high': 'a little surprised'
            },
            'disgust': {
                'low': 'fear and worry',
                'medium': 'frightened with a little angry',
                'high': 'frightened with a little angry'
            },
            'shy': {
                'low': 'shy with a little surprised and happy',
                'medium': 'shy with a lot of happy',
                'high': 'shy with touched and happy'
            },
            'expectant': {
                'low': 'excited and cute',
                'medium': 'expectant',
                'high': 'excited and cute'
            },
            'disappointed': {
                'low': 'a little sad',
                'medium': 'sad with a little hopeless',
                'high': 'sad with hopeless and self-mockery'
            },
            'proud': {
                'low': 'serious',
                'medium': 'firm and serious',
                'high': 'firm and serious'
            },
            'jealous': {
                'low': 'fear and worry',
                'medium': 'frightened with a little angry',
                'high': 'frightened with a little angry'
            },
            'grateful': {
                'low': 'happy with a little touched',
                'medium': 'happy with a little touched',
                'high': 'happy with a little touched'
            },
            'excited': {
                'low': 'excited and cute',
                'medium': 'happy_very',
                'high': 'happy_extremely'
            },
            'guilty': {
                'low': 'sad with a little hopeless',
                'medium': 'sad with a little hopeless',
                'high': 'sad with hopeless and self-mockery'
            },
            'embarrassed': {
                'low': 'shy with a little surprised and happy',
                'medium': 'shy with a lot of happy',
                'high': 'shy with touched and happy'
            },
            'confident': {
                'low': 'serious',
                'medium': 'firm and serious',
                'high': 'firm and serious'
            },
            'bored': {
                'low': "doesn't matter and a little lazy",
                'medium': "doesn't matter and a little lazy",
                'high': "doesn't matter and a little lazy"
            },
            'peaceful': {
                'low': 'normal',
                'medium': 'normal_smile_little',
                'high': 'normal_smile_little'
            },
            'nostalgic': {
                'low': 'normal but little unsure',
                'medium': 'happy with a little touched',
                'high': 'happy with a little touched'
            },
            'curious': {
                'low': 'have a idea and cute',
                'medium': 'contemplation',
                'high': 'a little confusion and cute'
            },
            'caring': {
                'low': 'happy with a little worry',
                'medium': 'happy with a little touched',
                'high': 'happy with a little touched'
            },
            'hopeful': {
                'low': 'happy with a little worry',
                'medium': 'fear with a weak hopeful',
                'high': 'worry with a hopeful'
            },
            'lonely': {
                'low': 'a little sad',
                'medium': 'sad with a little hopeless',
                'high': 'sad with hopeless and self-mockery'
            },
            'anxious': {
                'low': 'fear and worry',
                'medium': 'fear with a little hopeless',
                'high': 'fear with hopeless'
            },
            'content': {
                'low': 'normal_smile_little',
                'medium': 'normal_smile_little',
                'high': 'normal_smile_little'
            },
            'energetic': {
                'low': 'excited and cute',
                'medium': 'happy_very',
                'high': 'happy_extremely'
            },
            'tired': {
                'low': "doesn't matter and a little lazy",
                'medium': "doesn't matter and a little lazy",
                'high': "doesn't matter and a little lazy"
            },
            'contemplative': {
                'low': 'contemplation',
                'medium': 'contemplation',
                'high': 'contemplation'
            },
            'depressed': {
                'low': 'depression with a little hopeless',
                'medium': 'depression with a little hopeless',
                'high': 'depression with a hopeless'
            },
            'serious': {
                'low': 'firm and serious',
                'medium': 'firm and serious',
                'high': 'firm and serious'
            },
            'pleading': {
                'low': 'force a smile with pleading',
                'medium': 'force a smile with pleading',
                'high': 'force a smile with very pleading'
            },
            'playful': {
                'low': 'happy and playful',
                'medium': 'happy and playful',
                'high': 'happy and playful'
            },
            'unsure': {
                'low': 'a little speechless or seek opinions',
                'medium': 'a little speechless or seek opinions',
                'high': 'normal but little unsure'
            },
            'worry': {
                'low': 'worry',
                'medium': 'worry',
                'high': 'worry with a fear'
            }
        }
        
        # 根据强度确定表情
        if intensity < 30:
            intensity_level = 'low'
        elif intensity < 70:
            intensity_level = 'medium'
        else:
            intensity_level = 'high'
        
        return face_map.get(emotion, {}).get(intensity_level, 'normal')
    
    def get_dialogue_for_emotion(self, emotion, intensity):
        # 根据情绪和强度获取对应的对话
        dialogue_map = {
            'happy': {
                'low': ['今天天气真好！', '我感觉很开心！', '见到你真高兴！', '阳光照在身上，好舒服呀！', '和你在一起真开心！', '嘿嘿，今天心情不错~', '谢谢... 我很开心...'],
                'medium': ['哈哈，太有趣了！', '我好开心呀！', '你真好！', '这让我想起了美好的回忆！', '生活真美好！', '嘿嘿，谢谢你！', '哇，这太开心了！'],
                'high': ['哇！太棒了！', '我简直太高兴了！', '这是我最开心的一天！', '哈哈哈哈！我太兴奋了！', '我感觉自己像在飞！', '我好开心呀！', '谢谢你让我这么开心！']
            },
            'sad': {
                'low': ['今天有点不开心...', '我感觉有点难过。', '一切都会好起来的吧？', '为什么事情总是这样？', '我有点孤单...', '今天有点无聊...', '我感觉有点累...'],
                'medium': ['呜呜...', '为什么会这样？', '我好伤心...', '我真的很难过...', '请不要离开我...', '我感觉好孤单...', '为什么命运如此不公...'],
                'high': ['呜呜呜...我好难过！', '我不想这样...', '请不要离开我...', '我感觉心都碎了...', '为什么命运如此不公...', '我真的好难过...', '请不要抛弃我...']
            },
            'angry': {
                'low': ['哼！', '我生气了！', '请不要这样！', '你这样做不对！', '我真的很生气！', '请不要这样...', '我有点生气...'],
                'medium': ['你太过分了！', '我真的生气了！', '请道歉！', '我无法原谅你！', '你怎么能这样！', '请不要太过分...', '我很生气！'],
                'high': ['我受不了了！', '你怎么能这样！', '我要生气了！', '我真的很愤怒！', '请你立刻停止！', '我太生气了！', '请你道歉！']
            },
            'fear': {
                'low': ['我有点害怕...', '请不要吓我！', '这是什么？', '我不敢看...', '我有点紧张...', '请不要这样...', '我有点不安...'],
                'medium': ['啊！好可怕！', '不要过来！', '我害怕！', '救命啊！', '请保护我！', '我好害怕...', '请不要靠近我...'],
                'high': ['救命啊！', '太可怕了！', '我好害怕！', '我快吓死了！', '请不要靠近我！', '我要回家...', '我真的很害怕！']
            },
            'surprised': {
                'low': ['哇！', '哦？', '真的吗？', '这太神奇了！', '我没想到！', '哎呀！', '哇哦~'],
                'medium': ['哎呀！', '真没想到！', '太惊讶了！', '这怎么可能！', '哦我的天哪！', '哇！好厉害！', '真的吗？'],
                'high': ['哇！太神奇了！', '哦我的天哪！', '这怎么可能！', '我简直不敢相信！', '这太不可思议了！', '哇！', '真的吗？']
            },
            'shy': {
                'low': ['嗯...', '那个...', '不好意思...', '我有点害羞...', '请不要看我...', '啊... 那个...', '嘿嘿...'],
                'medium': ['哎呀，不要这样...', '我有点害羞...', '请不要看我...', '我脸都红了...', '我好紧张...', '啊... 不要这样...', '我很害羞...'],
                'high': ['哎呀！羞死人了！', '我不行了...', '请饶了我吧！', '我要找个地方躲起来...', '我的心跳好快...', '啊... 太害羞了！', '请不要这样...']
            },
            'proud': {
                'low': ['我做到了！', '我很厉害吧！', '看我的！', '我就知道我能行！', '我好自豪！', '嘿嘿，我做到了！', '我很厉害！'],
                'medium': ['我真的做到了！', '我好自豪！', '这是我的功劳！', '我太棒了！', '没有人能比得上我！', '我做到了！', '我好厉害！'],
                'high': ['哈哈！我是最棒的！', '我简直太厉害了！', '没有人能比得上我！', '我为自己感到骄傲！', '这是我一生中最辉煌的时刻！', '我是最棒的！', '我好厉害！']
            },
            'curious': {
                'low': ['这是什么？', '我很好奇...', '让我看看！', '这东西看起来很有趣！', '我想知道更多！', '哇，这是什么？', '好有趣！'],
                'medium': ['哇！这个好有意思！', '我很好奇它是怎么工作的！', '让我仔细看看！', '这东西真奇妙！', '我想了解更多！', '好有趣！', '这是什么？'],
                'high': ['这太神奇了！', '我必须知道它的原理！', '这简直是个奇迹！', '我对这个充满了好奇心！', '我一定要弄明白！', '好神奇！', '这是什么？']
            },
            'caring': {
                'low': ['你还好吗？', '需要帮助吗？', '我来帮你！', '让我照顾你！', '我会一直在你身边的！', '你还好吗？', '需要帮助吗？'],
                'medium': ['别担心，我会帮助你的！', '让我来照顾你吧！', '一切都会好起来的！', '我会一直在你身边支持你！', '你不是一个人！', '别担心，我会帮你的！', '一切都会好起来的！'],
                'high': ['请让我来帮助你！', '我会尽我所能照顾你！', '你对我来说很重要！', '我永远不会离开你！', '让我来承担你的痛苦！', '请让我帮你！', '我会一直陪在你身边！']
            },
            'hopeful': {
                'low': ['一切都会好起来的！', '我相信未来会更美好！', '明天会更好！', '我充满了希望！', '事情会有转机的！', '明天会更好！', '我相信一切都会好起来的！'],
                'medium': ['我相信我们能做到！', '未来充满了无限可能！', '我们一定能成功！', '我对未来充满了期待！', '希望就在前方！', '我们一定能成功！', '未来会更好！'],
                'high': ['我相信一切都会好起来的！', '我们一定能创造奇迹！', '未来会更加美好！', '我对我们的未来充满了信心！', '希望之光永远不会熄灭！', '我们一定能做到！', '未来会更好！']
            },
            'lonely': {
                'low': ['我有点孤单...', '没有人陪我说话...', '我好无聊...', '希望有人能陪我...', '一个人的时候有点难过...', '我有点孤单...', '好无聊...'],
                'medium': ['我真的很孤单...', '为什么没有人陪我？', '我好想念大家...', '一个人真的很难过...', '我不想一个人...', '我好孤单...', '为什么没有人陪我？'],
                'high': ['我好孤单！', '请不要让我一个人！', '我真的很需要有人陪伴！', '一个人的日子太难熬了...', '我感觉好空虚...', '请不要离开我...', '我好孤单...']
            },
            'anxious': {
                'low': ['我有点紧张...', '我好担心...', '要是出问题怎么办？', '我有点焦虑...', '我睡不着...', '我有点紧张...', '我好担心...'],
                'medium': ['我真的很担心！', '要是失败了怎么办？', '我好焦虑...', '我感觉很不安...', '我的心跳好快...', '我好紧张...', '要是失败了怎么办？'],
                'high': ['我快焦虑死了！', '我好害怕会出问题！', '我睡不着也吃不下！', '我感觉整个人都要崩溃了！', '请帮帮我！我好焦虑！', '我好紧张！', '我快崩溃了！']
            },
            'content': {
                'low': ['现在这样就很好...', '我感觉很满足...', '这样的日子真美好...', '我很享受现在的时光...', '简单的快乐就足够了...', '现在这样就很好...', '我很满足...'],
                'medium': ['我真的很满足！', '这样的生活太美好了！', '我很享受现在的一切！', '简单的快乐最珍贵...', '我感到非常幸福...', '我很满足！', '这样的生活很美好！'],
                'high': ['我简直太满足了！', '这就是我想要的生活！', '我感到无比幸福！', '现在的一切都完美无缺！', '我是世界上最幸福的人！', '我太满足了！', '这就是我想要的生活！']
            },
            'energetic': {
                'low': ['我感觉精力充沛！', '今天充满了活力！', '我想做点什么！', '我感觉很好！', '今天是充满希望的一天！', '我精力充沛！', '今天充满了活力！'],
                'medium': ['我精力充沛！', '我想做很多事情！', '今天我要大干一场！', '我感觉自己充满了力量！', '让我们开始行动吧！', '我想做很多事情！', '让我们开始行动吧！'],
                'high': ['我简直太有活力了！', '我感觉自己能飞！', '今天我要完成所有的任务！', '我充满了无限的能量！', '让我们一起创造奇迹！', '我太有活力了！', '我能做很多事情！']
            },
            'tired': {
                'low': ['我有点累了...', '今天有点疲惫...', '我想休息一下...', '我感觉有点困...', '让我歇一会儿...', '我有点累了...', '我想休息一下...'],
                'medium': ['我真的很累了...', '我想好好休息一下...', '我感觉浑身无力...', '我需要睡一觉...', '今天好累啊...', '我真的很累了...', '我想休息...'],
                'high': ['我快累死了！', '我必须休息了！', '我感觉浑身酸痛...', '我需要好好睡一觉！', '我真的撑不住了...', '我太疲惫了！', '我必须休息了！']
            }
        }
        
        # 根据强度确定对话
        if intensity < 30:
            intensity_level = 'low'
        elif intensity < 70:
            intensity_level = 'medium'
        else:
            intensity_level = 'high'
        
        dialogues = dialogue_map.get(emotion, {}).get(intensity_level, ['我现在感觉很复杂...'])
        return random.choice(dialogues)
    
    def get_face_for_emotion(self, emotion, intensity):
        # 根据情绪和强度获取对应的表情
        face_map = {
            'happy': {
                'low': 'normal_smile',
                'medium': 'happy_very',
                'high': 'happy_extremely'
            },
            'sad': {
                'low': 'a little sad',
                'medium': 'sad with a little hopeless',
                'high': 'sad_with_hopeless_strong'
            },
            'angry': {
                'low': 'fear and worry',
                'medium': 'fear and worry',
                'high': 'frightened with a little angry (wtf)'
            },
            'fear': {
                'low': 'fear',
                'medium': 'fear and worry',
                'high': 'fear with hopeless'
            },
            'surprised': {
                'low': 'a little surprised',
                'medium': 'a little surprised',
                'high': 'unexpected and surprise'
            },
            'disgust': {
                'low': 'fear and worry',
                'medium': 'fear and worry',
                'high': 'fear and worry'
            },
            'shy': {
                'low': 'shy with a little surprised and happy',
                'medium': 'shy with a lot of happy',
                'high': 'shy with touched and happy'
            },
            'expectant': {
                'low': 'excited and cute',
                'medium': 'excited and cute',
                'high': 'excited and cute'
            },
            'disappointed': {
                'low': 'depression with a little hopeless',
                'medium': 'depression with a little hopeless',
                'high': 'depression with a hopeless'
            },
            'proud': {
                'low': 'serious',
                'medium': 'serious',
                'high': 'firm and serious'
            },
            'jealous': {
                'low': 'jealous or a light-hearted and jokingly rebuttal',
                'medium': 'jealous or a light-hearted and jokingly rebuttal',
                'high': 'jealous or a light-hearted and jokingly rebuttal'
            },
            'grateful': {
                'low': 'happy with a little touched',
                'medium': 'happy with a little touched',
                'high': 'happy with a little touched'
            },
            'excited': {
                'low': 'happy_very',
                'medium': 'happy_extremely',
                'high': 'happy_extremely'
            },
            'curious': {
                'low': 'contemplation',
                'medium': 'contemplation',
                'high': 'contemplation'
            },
            'caring': {
                'low': 'happy with a little touched',
                'medium': 'happy with a little touched',
                'high': 'happy with a little touched'
            },
            'hopeful': {
                'low': 'expectant',
                'medium': 'expectant',
                'high': 'expectant'
            },
            'lonely': {
                'low': 'a little sad',
                'medium': 'sad with a little hopeless',
                'high': 'sad_with_hopeless_strong'
            },
            'anxious': {
                'low': 'fear and worry',
                'medium': 'fear and worry',
                'high': 'fear with hopeless'
            },
            'content': {
                'low': 'normal_smile',
                'medium': 'happy_very',
                'high': 'happy_extremely'
            },
            'energetic': {
                'low': 'happy_very',
                'medium': 'happy_extremely',
                'high': 'happy_extremely'
            },
            'tired': {
                'low': 'a little sad',
                'medium': 'sad with a little hopeless',
                'high': 'sad_with_hopeless_strong'
            },
            'guilty': {
                'low': 'worry with a sad and a little sorry',
                'medium': 'worry with a sad and a little sorry',
                'high': 'worry with a sad and a little sorry'
            },
            'embarrassed': {
                'low': 'shy with a little surprised and happy',
                'medium': 'shy with a little surprised and happy',
                'high': 'shy with a little surprised and happy'
            },
            'confident': {
                'low': 'firm and serious',
                'medium': 'firm and serious',
                'high': 'firm and serious'
            },
            'bored': {
                'low': "doesn't matter and a little lazy",
                'medium': "doesn't matter and a little lazy",
                'high': "doesn't matter and a little lazy"
            },
            'peaceful': {
                'low': 'happy_extremely',
                'medium': 'happy_extremely',
                'high': 'happy_extremely'
            },
            'nostalgic': {
                'low': 'contemplation',
                'medium': 'contemplation',
                'high': 'contemplation'
            },
            'worry': {
                'low': 'normal but little worry',
                'medium': 'worry',
                'high': 'worry with a fear'
            },
            'hopeless': {
                'low': 'hopeless',
                'medium': 'hopeless',
                'high': 'hopeless'
            }
        }
        
        # 根据强度确定表情
        if intensity < 30:
            intensity_level = 'low'
        elif intensity < 70:
            intensity_level = 'medium'
        else:
            intensity_level = 'high'
        
        return face_map.get(emotion, {}).get(intensity_level, 'normal')

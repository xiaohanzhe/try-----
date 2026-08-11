from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QFrame
from PyQt5.QtGui import QPixmap, QFont, QPainter, QBrush, QColor
from PyQt5.QtCore import Qt, QPoint

class DialogueUI(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()
        
    def init_ui(self):
        # 设置窗口属性
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(100, 500, 500, 260)
        self.setWindowOpacity(0.98)
        
        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 创建对话框架
        self.dialogue_frame = QFrame(self)
        self.dialogue_frame.setStyleSheet('''
            QFrame {
                background-color: rgba(255, 248, 240, 0.98);
                border: 3px solid #8B4513;
                border-radius: 20px;
            }
        ''')
        dialogue_layout = QVBoxLayout(self.dialogue_frame)
        dialogue_layout.setContentsMargins(20, 20, 20, 20)
        
        # 创建对话头部（包含表情、名称和最小化按钮）
        header_layout = QHBoxLayout()
        
        # 表情标签
        self.face_label = QLabel(self)
        self.face_label.setFixedSize(100, 100)
        self.face_label.setStyleSheet('border-radius: 50px; border: 4px solid #8B4513; background-color: rgba(255, 255, 255, 0.9);')
        header_layout.addWidget(self.face_label)
        
        # 名称标签
        self.name_label = QLabel("Ralsei", self)
        self.name_label.setFont(QFont("Comic Sans MS", 20, QFont.Bold))
        self.name_label.setStyleSheet('color: #8B4513;')
        header_layout.addWidget(self.name_label, 1, Qt.AlignCenter)
        
        # 添加最小化按钮
        self.minimize_button = QPushButton("_", self)
        self.minimize_button.setFont(QFont("Arial", 18, QFont.Bold))
        self.minimize_button.setFixedSize(35, 35)
        self.minimize_button.setStyleSheet('''
            QPushButton {
                background-color: rgba(139, 69, 19, 0.7);
                color: white;
                border: 2px solid #8B4513;
                border-radius: 17px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: rgba(139, 69, 19, 0.9);
            }
            QPushButton:pressed {
                background-color: rgba(101, 49, 14, 0.9);
            }
        ''')
        self.minimize_button.clicked.connect(self.minimize_dialogue)
        header_layout.addWidget(self.minimize_button, 0, Qt.AlignTop)
        
        dialogue_layout.addLayout(header_layout)
        
        # 创建对话内容
        self.dialogue_content = QTextEdit(self)
        self.dialogue_content.setReadOnly(True)
        self.dialogue_content.setFont(QFont("Comic Sans MS", 14))
        self.dialogue_content.setStyleSheet('''
            QTextEdit {
                background-color: transparent;
                border: none;
                color: #5D4037;
                padding: 15px;
                line-height: 1.6;
            }
        ''')
        self.dialogue_content.setFixedHeight(100)
        dialogue_layout.addWidget(self.dialogue_content)
        
        # 创建输入区域
        input_layout = QHBoxLayout()
        
        self.input_field = QTextEdit(self)
        self.input_field.setFixedHeight(80)
        self.input_field.setFont(QFont("Comic Sans MS", 14))
        self.input_field.setStyleSheet('''
            QTextEdit {
                background-color: rgba(255, 255, 255, 0.95);
                border: 3px solid #8B4513;
                border-radius: 12px;
                padding: 12px;
                color: #5D4037;
            }
            QTextEdit:focus {
                border: 3px solid #6B8E23;
                outline: none;
            }
        ''')
        input_layout.addWidget(self.input_field, 1)
        
        self.send_button = QPushButton("发送", self)
        self.send_button.setFont(QFont("Comic Sans MS", 14, QFont.Bold))
        self.send_button.setStyleSheet('''
            QPushButton {
                background-color: #6B8E23;
                color: white;
                border: 3px solid #556B2F;
                border-radius: 12px;
                padding: 10px 25px;
                margin-left: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #556B2F;
            }
            QPushButton:pressed {
                background-color: #4A5D23;
            }
        ''')
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)
        
        dialogue_layout.addLayout(input_layout)
        
        main_layout.addWidget(self.dialogue_frame)
        
        # 初始化打字机效果
        self.is_typing = False
        self.typing_timer = None
        self.typing_text = ""
        self.typing_index = 0
        
        # 初始化表情字典
        self.face_mapping = {
            "happy": "face_happy_very.png",
            "happy_extremely": "face_happy_extremely.png",
            "happy_very": "face_happy_very.png",
            "normal_smile_little": "face_normal_smile_little.png",
            "normal_unsure": "face_normal but little unsure.png",
            "normal_worry": "face_normal but little worry.png",
            "sad": "face_a little sad.png",
            "sad_hopeless": "face_sad with a little hopeless.png",
            "sad_force_smile": "face_sad but force a smile.png",
            "surprised": "face_a little surprised.png",
            "surprised_strong": "face_unexpected and surprise.png",
            "curious": "face_a little confusion and cute.png",
            "excited": "face_excited and cute.png",
            "shy": "face_shy with a little surprised and happy.png",
            "shy_happy": "face_shy with a lot of happy.png",
            "concerned": "face_worry.png",
            "concerned_fear": "face_worry with a fear.png",
            "laughing": "face_happy_very.png",
            "blushing": "face_shy with a little surprised and happy.png",
            "thinking": "face_contemplation.png",
            "fear": "face_fear.png",
            "fear_firm": "face_fear but firm.png",
            "serious": "face_serious.png",
            "firm": "face_firm and serious.png",
            "pleading": "face_force a smile with pleading.png",
            "tired": "face_depression with a little hopeless.png",
            "neutral": "face_normal.png",
            "confused": "face_a little confusion and cute.png",
            "embarrassed": "face_fear and worry and unsure with a little embarrassing.png",
            "without_glass": "face_without glass.png",
            "playful": "face_happy and playful.png",
        }
        
        # 初始化表情
        self.set_face("normal")
        
        # 最小化相关变量
        self.is_minimized = False
        self.original_size = self.size()
        self.original_pos = self.pos()
        self.minimized_size = (500, 70)  # 最小化后的高度
        
    def set_face(self, face_type):
        # 设置表情，添加错误处理
        face_mapping = {
            # 基础表情
            "normal": "face_normal.png",
            "happy": "face_happy_very.png",
            "happy_extremely": "face_happy_extremely.png",
            "happy_very": "face_happy_very.png",
            "normal_smile_little": "face_normal_smile_little.png",
            "normal_smile": "face_normal_smile_little.png",
            "normal_unsure": "face_normal but little unsure.png",
            "normal but little unsure": "face_normal but little unsure.png",
            "normal_worry": "face_normal but little worry.png",
            "normal but little worry": "face_normal but little worry.png",
            "face_normal": "face_normal.png",
            "face_happy_very": "face_happy_very.png",
            "face_happy_extremely": "face_happy_extremely.png",
            "face_normal_smile_little": "face_normal_smile_little.png",
            "face_normal but little unsure": "face_normal but little unsure.png",
            "face_normal but little worry": "face_normal but little worry.png",
            
            # 开心相关
            "happy with a little touched": "face_happy with a little touched.png",
            "happy_with_touched": "face_happy with a little touched.png",
            "happy with a little worry": "face_happy with a little worry.png",
            "happy_with_worry": "face_happy with a little worry.png",
            "happy and playful": "face_happy and playful.png",
            "grateful": "face_happy with a little touched.png",
            "laughing": "face_happy_very.png",
            "face_happy with a little touched": "face_happy with a little touched.png",
            "face_happy and playful": "face_happy and playful.png",
            "face_happy with a little worry": "face_happy with a little worry.png",
            
            # 悲伤相关
            "a little sad": "face_a little sad.png",
            "sad": "face_a little sad.png",
            "sad with a little hopeless": "face_sad with a little hopeless.png",
            "sad_with_hopeless": "face_sad with a little hopeless.png",
            "sad with hopeless and self-mockery": "face_sad with hopeless and self-mockery.png",
            "sad_with_hopeless_self_mockery": "face_sad with hopeless and self-mockery.png",
            "sad but force a smile": "face_sad but force a smile.png",
            "sad_but_force_smile": "face_sad but force a smile.png",
            "depression with a little hopeless": "face_depression with a little hopeless.png",
            "disappointed": "face_depression with a little hopeless.png",
            "depression with a hopeless": "face_depression with a hopeless.png",
            "depression_hopeless": "face_depression with a hopeless.png",
            "face_a little sad": "face_a little sad.png",
            "face_sad with a little hopeless": "face_sad with a little hopeless.png",
            "face_sad with hopeless and self-mockery": "face_sad with hopeless and self-mockery.png",
            "face_sad but force a smile": "face_sad but force a smile.png",
            "face_depression with a little hopeless": "face_depression with a little hopeless.png",
            "face_depression with a hopeless": "face_depression with a hopeless.png",
            
            # 惊讶相关
            "a little surprised": "face_a little surprised.png",
            "surprised": "face_a little surprised.png",
            "unexpected and surprise": "face_unexpected and surprise.png",
            "unexpected_surprise": "face_unexpected and surprise.png",
            "a little speechless with happy": "face_a little speechless with happy.png",
            "a little speechless": "face_a little speechless with happy.png",
            "face_a little surprised": "face_a little surprised.png",
            "face_unexpected and surprise.png": "face_unexpected and surprise.png",
            "face_a little speechless with happy": "face_a little speechless with happy.png",
            
            # 困惑思考相关
            "a little confusion and cute": "face_a little confusion and cute.png",
            "confused": "face_a little confusion and cute.png",
            "contemplation": "face_contemplation.png",
            "curious": "face_contemplation.png",
            "thoughtful": "face_contemplation.png",
            "have a idea and cute": "face_have a idea and cute.png",
            "have_idea": "face_have a idea and cute.png",
            "a little speechless or seek opinions": "face_a little speechless or seek opinions.png",
            "seek_opinions": "face_a little speechless or seek opinions.png",
            "face_a little confusion and cute": "face_a little confusion and cute.png",
            "face_contemplation": "face_contemplation.png",
            "face_have a idea and cute": "face_have a idea and cute.png",
            "face_a little speechless or seek opinions": "face_a little speechless or seek opinions.png",
            
            # 恐惧相关
            "fear": "face_fear.png",
            "fear and worry": "face_worry with a fear.png",
            "fear_with_worry": "face_worry with a fear.png",
            "fear but firm": "face_fear but firm.png",
            "fear_but_firm": "face_fear but firm.png",
            "fear but firm_speaking": "face_fear but firm_speaking.png",
            "fear with a little hopeless": "face_fear with a little hopeless.png",
            "fear_with_hopeless": "face_fear with a little hopeless.png",
            "fear with a weak hopeful": "face_fear with a weak hopeful.png",
            "fear_with_weak_hopeful": "face_fear with a weak hopeful.png",
            "fear with hopeless": "face_fear with hopeless.png",
            "fear_with_hopeless_strong": "face_fear with hopeless.png",
            "fear and worry and unsure with a little embarrassing": "face_fear and worry and unsure with a little embarrassing.png",
            "embarrassed_fear": "face_fear and worry and unsure with a little embarrassing.png",
            "hopeless": "face_hopeless.png",
            "face_fear": "face_fear.png",
            "face_worry with a fear": "face_worry with a fear.png",
            "face_fear but firm": "face_fear but firm.png",
            "face_fear but firm_speaking": "face_fear but firm_speaking.png",
            "face_fear with a little hopeless": "face_fear with a little hopeless.png",
            "face_fear with a weak hopeful": "face_fear with a weak hopeful.png",
            "face_fear with hopeless": "face_fear with hopeless.png",
            "face_fear and worry and unsure with a little embarrassing": "face_fear and worry and unsure with a little embarrassing.png",
            "face_hopeless": "face_hopeless.png",
            
            # 愤怒厌恶相关
            "frightened with a little angry": "face_frightened with a little angry.png",
            "frightened with a little angry (wtf)": "face_frightened with a little angry.png",
            "angry": "face_frightened with a little angry.png",
            "disgust": "face_frightened with a little angry.png",
            "face_frightened with a little angry": "face_frightened with a little angry.png",
            
            # 害羞相关
            "shy with a little surprised and happy": "face_shy with a little surprised and happy.png",
            "shy": "face_shy with a little surprised and happy.png",
            "shy with a lot of happy": "face_shy with a lot of happy.png",
            "shy_happy": "face_shy with a lot of happy.png",
            "shy with touched and happy": "face_shy with touched and happy.png",
            "shy_touched": "face_shy with touched and happy.png",
            "blushing": "face_shy with a little surprised and happy.png",
            "face_shy with a little surprised and happy": "face_shy with a little surprised and happy.png",
            "face_shy with a lot of happy": "face_shy with a lot of happy.png",
            "face_shy with touched and happy": "face_shy with touched and happy.png",
            
            # 骄傲严肃相关
            "proud": "face_serious.png",
            "serious": "face_serious.png",
            "firm and serious": "face_firm and serious.png",
            "firm_serious": "face_firm and serious.png",
            "face_serious": "face_serious.png",
            "face_firm and serious": "face_firm and serious.png",
            
            # 担忧相关
            "worry": "face_worry.png",
            "worry with a fear": "face_worry with a fear.png",
            "worry_with_fear": "face_worry with a fear.png",
            "worry with a hopeful": "face_worry with a hopeful.png",
            "worry_with_hopeful": "face_worry with a hopeful.png",
            "worry with a hopeless and sad": "face_worry with a hopeless and sad.png",
            "worry_with_hopeless_sad": "face_worry with a hopeless and sad.png",
            "worry with a little sad": "face_worry with a little sad.png",
            "worry_with_little_sad": "face_worry with a little sad.png",
            "worry with a little smile": "face_worry with a little smile.png",
            "worry_with_little_smile": "face_worry with a little smile.png",
            "worry with a sad and a little sorry": "face_worry with a sad and a little sorry.png",
            "worry_with_sad_sorry": "face_worry with a sad and a little sorry.png",
            "smile with a little worry": "face_smile with a little worry.png",
            "concerned": "face_worry.png",
            "face_worry": "face_worry.png",
            "face_worry with a hopeful": "face_worry with a hopeful.png",
            "face_worry with a hopeless and sad": "face_worry with a hopeless and sad.png",
            "face_worry with a little sad": "face_worry with a little sad.png",
            "face_worry with a little smile": "face_worry with a little smile.png",
            "face_worry with a sad and a little sorry": "face_worry with a sad and a little sorry.png",
            "face_smile with a little worry": "face_smile with a little worry.png",
            
            # 兴奋期待相关
            "excited and cute": "face_excited and cute.png",
            "expectant": "face_excited and cute.png",
            "excited": "face_excited and cute.png",
            "face_excited and cute": "face_excited and cute.png",
            
            # 其他表情
            "doesn't matter and a little lazy": "face_doesn't matter and a little lazy.png",
            "doesn't_matter": "face_doesn't matter and a little lazy.png",
            "force a smile with pleading": "face_force a smile with pleading.png",
            "force_smile_pleading": "face_force a smile with pleading.png",
            "force a smile with very pleading": "face_force a smile with very pleading.png",
            "force_smile_very_pleading": "face_force a smile with very pleading.png",
            "without glass": "face_without glass.png",
            "without_glass": "face_without glass.png",
            "face_doesn't matter and a little lazy": "face_doesn't matter and a little lazy.png",
            "face_force a smile with pleading": "face_force a smile with pleading.png",
            "face_force a smile with very pleading": "face_force a smile with very pleading.png",
            "face_without glass": "face_without glass.png",
            
            # 特定表情名称直接映射
            "face_worry": "face_worry.png",
            "face_worry.png": "face_worry.png",
            "normal_smile_little": "face_normal_smile_little.png",
            "smile_with_touched": "face_happy with a little touched.png",
            "smile_with_worry": "face_smile with a little worry.png",
            "neutral": "face_normal.png",
            "neutral_smile": "face_normal_smile_little.png",
            "neutral_unsure": "face_normal but little unsure.png",
            "depressed": "face_depression with a little hopeless.png",
            "depression": "face_depression with a little hopeless.png",
            "contemplative": "face_contemplation.png",
            "contemplation": "face_contemplation.png",
            "pleading": "face_force a smile with pleading.png",
            "playful": "face_happy and playful.png",
            "unsure": "face_normal but little unsure.png",
        }
        
        face_file = face_mapping.get(face_type, "face_normal.png")
        face_path = f"c:/Users/23002/Documents/trae_projects/try/ralsei_face/{face_file}"
        
        try:
            pixmap = QPixmap(face_path)
            if not pixmap.isNull():
                self.face_label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                print(f"警告：无法加载表情图片: {face_path}")
        except Exception as e:
            print(f"加载表情图片时出错: {e}")
            # 使用默认表情
            default_path = "c:/Users/23002/Documents/trae_projects/try/ralsei_face/face_normal.png"
            pixmap = QPixmap(default_path)
            if not pixmap.isNull():
                self.face_label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
    def add_dialogue(self, speaker, message, face_type="normal"):
        # 添加对话内容
        if speaker == "ralsei":
            self.set_face(face_type)
            # 使用打字机效果显示Ralsei的对话
            self.start_typing(message)
        else:
            # 直接显示用户的对话
            self.dialogue_content.append(f"<b>You:</b> {message}")
            # 滚动到底部
            self.dialogue_content.verticalScrollBar().setValue(self.dialogue_content.verticalScrollBar().maximum())
    
    def start_typing(self, text):
        # 开始打字机效果
        from PyQt5.QtCore import QTimer
        
        # 停止之前的打字效果
        if hasattr(self, 'typing_timer') and self.typing_timer:
            self.typing_timer.stop()
        
        self.is_typing = True
        self.typing_text = f"<b>Ralsei:</b> " + text
        self.typing_index = 0
        self.dialogue_content.clear()
        
        # 创建打字机效果的定时器，优化打字速度
        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self.type_next_character)
        # 根据文本长度动态调整打字速度，使长文本打字更快
        base_speed = 30  # 基础速度
        if len(text) > 100:
            base_speed = 20  # 长文本打字更快
        elif len(text) > 50:
            base_speed = 25  # 中长文本打字稍快
        self.typing_timer.start(base_speed)
    
    def type_next_character(self):
        # 打字机效果，每次显示一个字符
        if self.typing_index < len(self.typing_text):
            # 添加一个字符
            # 使用更可靠的方式构建HTML文本
            current_html = f"<html><body>{self.typing_text[:self.typing_index+1]}</body></html>"
            self.dialogue_content.setHtml(current_html)
            self.typing_index += 1
            # 滚动到底部
            self.dialogue_content.verticalScrollBar().setValue(self.dialogue_content.verticalScrollBar().maximum())
        else:
            # 打字完成
            self.is_typing = False
            if hasattr(self, 'typing_timer') and self.typing_timer:
                self.typing_timer.stop()
    
    def stop_typing(self):
        # 立即停止打字效果，显示完整文本
        if self.is_typing:
            self.is_typing = False
            if hasattr(self, 'typing_timer') and self.typing_timer:
                self.typing_timer.stop()
            # 显示完整文本
            self.dialogue_content.setHtml(f"<html><body>{self.typing_text}</body></html>")
            # 滚动到底部
            self.dialogue_content.verticalScrollBar().setValue(self.dialogue_content.verticalScrollBar().maximum())
    
    def handle_chat_commands(self, user_input):
        # 处理聊天指令，通过影响情绪来影响动画，保持情绪和姿势的自主性
        user_input_lower = user_input.lower()
        
        # 指令映射：关键词 -> (情绪影响方法, 成功响应)
        # 这里通过影响情绪来影响动画，而不是直接控制动画，保持情绪和姿势的自主性
        command_mapping = {
            # 抚摸相关指令 - 增加开心和害羞情绪
            "抚摸": (lambda: self.parent.emotion_system.add_emotion("happy", 30), "嘿嘿~ 好舒服呀！"),
            "摸": (lambda: self.parent.emotion_system.add_emotion("happy", 20), "谢谢你的抚摸！"),
            "摸摸": (lambda: self.parent.emotion_system.add_emotion("happy", 25), "真的好舒服呀~"),
            "抚摸我": (lambda: [self.parent.emotion_system.add_emotion("happy", 35), self.parent.emotion_system.add_emotion("shy", 20)], "嘿嘿~ 我很喜欢被抚摸哦！"),
            "摸我": (lambda: [self.parent.emotion_system.add_emotion("happy", 25), self.parent.emotion_system.add_emotion("shy", 15)], "好呀好呀！"),
            
            # 喂食相关指令 - 增加开心和感激情绪
            "喂食": (lambda: [self.parent.emotion_system.add_emotion("happy", 40), self.parent.emotion_system.add_emotion("grateful", 20)], "谢谢你的食物！我现在感觉好多了！"),
            "喂": (lambda: self.parent.emotion_system.add_emotion("happy", 35), "啊呜~ 真好吃！"),
            "给你吃": (lambda: [self.parent.emotion_system.add_emotion("happy", 30), self.parent.emotion_system.add_emotion("grateful", 25)], "太感谢你了！"),
            
            # 玩游戏相关指令 - 增加开心和兴奋情绪
            "玩游戏": (lambda: [self.parent.emotion_system.add_emotion("happy", 35), self.parent.emotion_system.add_emotion("excited", 30)], "好呀！我们来玩游戏吧！"),
            "游戏": (lambda: self.parent.emotion_system.add_emotion("excited", 35), "我最喜欢玩游戏了！"),
            "一起玩": (lambda: [self.parent.emotion_system.add_emotion("happy", 30), self.parent.emotion_system.add_emotion("excited", 25)], "当然可以！"),
            
            # 跳舞相关指令 - 增加兴奋和开心情绪
            "跳舞": (lambda: [self.parent.emotion_system.add_emotion("excited", 40), self.parent.emotion_system.add_emotion("happy", 30)], "你看！我跳得怎么样？"),
            "跳个舞": (lambda: [self.parent.emotion_system.add_emotion("excited", 35), self.parent.emotion_system.add_emotion("happy", 25)], "好呀！我来为你跳舞！"),
            
            # 唱歌相关指令 - 增加开心和期待情绪
            "唱歌": (lambda: [self.parent.emotion_system.add_emotion("happy", 35), self.parent.emotion_system.add_emotion("expectant", 25)], "啦啦啦~ 唱首歌给你听！"),
            "唱首歌": (lambda: [self.parent.emotion_system.add_emotion("happy", 30), self.parent.emotion_system.add_emotion("expectant", 30)], "我来为你唱歌！"),
            
            # 挥手相关指令 - 增加开心和惊讶情绪
            "挥手": (lambda: [self.parent.emotion_system.add_emotion("happy", 25), self.parent.emotion_system.add_emotion("surprised", 20)], "你好呀！"),
            "打招呼": (lambda: self.parent.emotion_system.add_emotion("happy", 20), "嘿嘿！"),
            
            # 拥抱相关指令 - 增加开心和感激情绪
            "拥抱": (lambda: [self.parent.emotion_system.add_emotion("happy", 40), self.parent.emotion_system.add_emotion("grateful", 30)], "谢谢你的拥抱！"),
            "抱一下": (lambda: [self.parent.emotion_system.add_emotion("happy", 35), self.parent.emotion_system.add_emotion("grateful", 25)], "我最喜欢拥抱了！"),
            
            # 大笑相关指令 - 增加开心情绪
            "笑": (lambda: self.parent.emotion_system.add_emotion("happy", 40), "哈哈哈哈！"),
            "大笑": (lambda: self.parent.emotion_system.add_emotion("happy", 50), "太好笑了！"),
            
            # 哭泣相关指令 - 增加悲伤情绪
            "哭": (lambda: self.parent.emotion_system.add_emotion("sad", 35), "呜... 你为什么要让我哭呢？"),
            "难过": (lambda: self.parent.emotion_system.add_emotion("sad", 40), "呜... 我真的很难过..."),
            
            # 喝茶相关指令 - 增加开心和放松情绪
            "喝茶": (lambda: self.parent.emotion_system.add_emotion("happy", 25), "这茶真好喝！"),
            "喝杯茶": (lambda: self.parent.emotion_system.add_emotion("happy", 20), "谢谢你的茶！"),
            
            # 摆姿势相关指令 - 增加骄傲和开心情绪
            "摆姿势": (lambda: [self.parent.emotion_system.add_emotion("proud", 30), self.parent.emotion_system.add_emotion("happy", 25)], "你看我摆的姿势怎么样？"),
            "pose": (lambda: [self.parent.emotion_system.add_emotion("proud", 35), self.parent.emotion_system.add_emotion("happy", 20)], "摆个pose！"),
        }
        
        # 检查是否匹配任何指令
        for keyword, (action, response) in command_mapping.items():
            if keyword in user_input_lower:
                # 执行对应情绪影响
                action()
                return response
        
        # 检查是否匹配部分关键词
        partial_matches = {
            "抚摸": (lambda: self.parent.emotion_system.add_emotion("happy", 25), "嘿嘿~ 好舒服呀！"),
            "摸": (lambda: self.parent.emotion_system.add_emotion("happy", 20), "谢谢你的抚摸！"),
            "喂": (lambda: self.parent.emotion_system.add_emotion("happy", 30), "啊呜~ 真好吃！"),
            "游戏": (lambda: self.parent.emotion_system.add_emotion("excited", 30), "我最喜欢玩游戏了！"),
            "跳舞": (lambda: [self.parent.emotion_system.add_emotion("excited", 35), self.parent.emotion_system.add_emotion("happy", 25)], "你看！我跳得怎么样？"),
            "唱歌": (lambda: [self.parent.emotion_system.add_emotion("happy", 30), self.parent.emotion_system.add_emotion("expectant", 25)], "啦啦啦~ 唱首歌给你听！"),
        }
        
        for keyword, (action, response) in partial_matches.items():
            if keyword in user_input_lower:
                action()
                return response
        
        # 没有匹配的指令
        return None
    
    def handle_file_commands(self, user_input):
        # 处理文件操作指令
        user_input_lower = user_input.lower()
        
        # 检查是否包含文件操作关键词
        if any(keyword in user_input_lower for keyword in ["打开", "修改", "表格", "excel", "对齐", "格子", "超出去"]):
            # 检查是否是请求打开并修改表格的指令
            if "打开" in user_input_lower and "表格" in user_input_lower and ("修改" in user_input_lower or "对齐" in user_input_lower):
                return self.parent.handle_file_operation(user_input)
        
        # 没有匹配的文件操作指令
        return None
    
    def send_message(self):
        # 发送用户消息
        user_input = self.input_field.toPlainText().strip()
        if user_input:
            self.add_dialogue("user", user_input)
            
            # 首先检查是否是聊天指令
            command_response = self.handle_chat_commands(user_input)
            if command_response:
                # 是聊天指令，直接回复
                self.add_dialogue("ralsei", command_response, "happy")
            # 检查是否是游戏输入
            elif self.parent.handle_game_input(user_input):
                # 是游戏输入，已经处理
                pass
            # 检查是否是文件操作指令
            elif self.handle_file_commands(user_input):
                # 是文件操作指令，已经处理
                pass
            else:
                # 不是游戏输入，生成正常回复
                # 获取Ralsei的回复，结合情绪系统
                response = self.parent.dialogue_system.generate_response(user_input, self.parent.emotion_system)
                
                # 根据当前情绪获取表情
                current_emotion, emotion_value = self.parent.emotion_system.get_current_emotion()
                intensity = abs(emotion_value)
                face_type = self.parent.emotion_system.get_face_for_emotion(current_emotion, intensity)
                
                self.add_dialogue("ralsei", response, face_type)
            
            # 清空输入框
            self.input_field.clear()
        
    def show_dialogue(self, message=None):
        # 显示对话框，添加淡入效果
        self.show()
        
        # 如果提供了消息，显示消息
        if message:
            self.add_dialogue("ralsei", message, "happy")
        
        from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
        animation = QPropertyAnimation(self, b"windowOpacity")
        animation.setDuration(500)
        animation.setStartValue(0.0)
        animation.setEndValue(0.95)
        animation.setEasingCurve(QEasingCurve.InOutQuad)
        animation.start()
        
    def hide_dialogue(self):
        # 隐藏对话框，添加淡出效果
        from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
        
        def on_hide_finished():
            self.hide()
        
        animation = QPropertyAnimation(self, b"windowOpacity")
        animation.setDuration(500)
        animation.setStartValue(0.95)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.InOutQuad)
        animation.finished.connect(on_hide_finished)
        animation.start()
        
    def mousePressEvent(self, event):
        # 鼠标按下事件，用于拖动窗口
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        # 鼠标移动事件，用于拖动窗口
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
            
    def minimize_dialogue(self):
        # 最小化/恢复对话框
        self.is_minimized = not self.is_minimized
        
        if self.is_minimized:
            # 最小化状态
            # 保存当前大小和位置
            self.original_size = self.size()
            self.original_pos = self.pos()
            
            # 调整窗口大小
            self.resize(self.minimized_size[0], self.minimized_size[1])
            
            # 隐藏部分UI元素
            self.dialogue_content.hide()
            self.input_field.hide()
            self.send_button.hide()
        else:
            # 恢复正常状态
            # 恢复原始大小和位置
            self.resize(self.original_size)
            self.move(self.original_pos)
            
            # 显示所有UI元素
            self.dialogue_content.show()
            self.input_field.show()
            self.send_button.show()
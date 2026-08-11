import sys
import time
import random
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt5.QtGui import QPainter, QBrush, QColor
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect
import os

# 添加项目根目录到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), 'ralsei_pet'))
sys.path.insert(0, project_root)

# 测试用的简化Ralsei类，专注于摔倒动画测试
class TestRalsei(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_animation()
        self.init_movement()
        self.init_test_window()
        
    def init_ui(self):
        # 创建透明窗口
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(100, 100, 50, 80)
        self.setWindowTitle("Test Ralsei")
        
        # 创建主标签用于显示精灵
        self.sprite_label = QLabel(self)
        self.sprite_label.setGeometry(0, 0, 50, 80)
        self.sprite_label.setAlignment(Qt.AlignCenter)
        self.sprite_label.setStyleSheet("background-color: rgba(255, 0, 0, 100);")
    
    def init_animation(self):
        # 初始化动画相关变量
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(33)  # 30FPS
        
        self.current_animation = "idle"
        self.current_frame = 0
        self.animation_fps = 30
        self.animation_frame_delay = int(1000 / self.animation_fps)
        
        # 摔倒相关变量
        self.is_falling = False
        self.fall_duration = 0.0
        self.max_fall_duration = 3.0
        self.last_update_time = time.time()
    
    def init_movement(self):
        # 初始化移动相关变量
        self.movement_timer = QTimer(self)
        self.movement_timer.timeout.connect(self.update_movement)
        self.movement_timer.start(30)
        
        self.target_pos = QPoint(100, 100)
        self.is_moving = True
        self.speed = 5.0
        self.current_speed_x = 0
        self.current_speed_y = 0
    
    def init_test_window(self):
        # 初始化测试窗口（模拟楼板）
        self.test_window = QMainWindow()
        self.test_window.setWindowTitle("Test Platform")
        self.test_window.setGeometry(200, 200, 300, 200)
        self.test_window.setStyleSheet("background-color: lightblue;")
        
        # 添加标签说明
        label = QLabel("拖动我测试Ralsei摔倒动画", self.test_window)
        label.setGeometry(50, 80, 200, 40)
        label.setAlignment(Qt.AlignCenter)
        
        self.test_window.show()
        
        # 记录初始窗口位置
        self.last_window_pos = self.test_window.pos()
        
        # 定时器检查窗口移动
        self.window_check_timer = QTimer(self)
        self.window_check_timer.timeout.connect(self.check_window_movement)
        self.window_check_timer.start(100)
    
    def update_animation(self):
        # 更新动画
        current_time = time.time()
        if current_time - self.last_update_time > self.animation_frame_delay / 1000:
            self.current_frame = (self.current_frame + 1) % 4
            self.last_update_time = current_time
            
            # 简单的动画显示，用不同颜色表示不同动画
            if self.is_falling:
                self.sprite_label.setStyleSheet("background-color: rgba(255, 165, 0, 150);")
            else:
                if self.current_animation == "idle":
                    self.sprite_label.setStyleSheet("background-color: rgba(0, 255, 0, 100);")
                else:
                    self.sprite_label.setStyleSheet("background-color: rgba(0, 0, 255, 100);")
    
    def update_movement(self):
        # 更新移动
        if self.is_moving and not self.is_falling:
            current_pos = self.pos()
            dx = self.target_pos.x() - current_pos.x()
            dy = self.target_pos.y() - current_pos.y()
            
            distance = ((dx ** 2) + (dy ** 2)) ** 0.5
            
            if distance > 0:
                direction_x = dx / distance
                direction_y = dy / distance
                
                new_x = current_pos.x() + direction_x * self.speed
                new_y = current_pos.y() + direction_y * self.speed
                
                self.move(int(new_x), int(new_y))
                
                # 检查是否到达目标位置
                if distance < self.speed:
                    self.is_moving = False
                    # 随机生成新目标位置
                    self.target_pos = QPoint(
                        random.randint(50, 400),
                        random.randint(50, 300)
                    )
                    self.is_moving = True
    
    def check_window_movement(self):
        # 检查测试窗口是否移动
        current_window_pos = self.test_window.pos()
        
        if current_window_pos != self.last_window_pos:
            # 窗口移动，触发摔倒动画
            self.start_fall()
            self.last_window_pos = current_window_pos
    
    def start_fall(self):
        # 开始摔倒动画
        if self.is_falling:
            return
        
        print("触发摔倒动画！")
        self.is_falling = True
        self.fall_duration = 0.0
        self.fall_start_time = time.time()
        
        # 停止移动
        self.is_moving = False
        
        # 启动摔倒处理定时器
        self.fall_timer = QTimer(self)
        self.fall_timer.timeout.connect(self.handle_fall)
        self.fall_timer.start(30)
    
    def handle_fall(self):
        # 处理摔倒逻辑
        current_time = time.time()
        self.fall_duration = current_time - self.fall_start_time
        
        print(f"摔倒中，已持续 {self.fall_duration:.2f} 秒")
        
        if self.fall_duration >= self.max_fall_duration:
            # 摔倒动画结束
            print("摔倒动画结束，恢复正常")
            self.is_falling = False
            self.fall_timer.stop()
            
            # 恢复移动
            self.is_moving = True

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ralsei = TestRalsei()
    ralsei.show()
    sys.exit(app.exec_())

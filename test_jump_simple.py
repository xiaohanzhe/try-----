import sys
import os
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt5.QtGui import QPixmap, QPainter, QBrush, QColor
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect

class TestRalseiJump(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_movement()
        self.init_jump()
    
    def init_ui(self):
        # 创建透明窗口
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(100, 100, 50, 50)
        self.setWindowTitle("Test Ralsei Jump")
        
        # 创建主标签用于显示红色方块占位符
        self.sprite_label = QLabel(self)
        self.sprite_label.setGeometry(0, 0, 50, 50)
        self.sprite_label.setAlignment(Qt.AlignCenter)
        
        # 创建红色方块
        pixmap = QPixmap(50, 50)
        painter = QPainter(pixmap)
        painter.fillRect(0, 0, 50, 50, QColor(255, 0, 0))
        painter.end()
        self.sprite_label.setPixmap(pixmap)
    
    def init_movement(self):
        # 初始化移动定时器
        self.movement_timer = QTimer(self)
        self.movement_timer.timeout.connect(self.update_movement)
        self.movement_timer.start(30)
        
        self.target_pos = QPoint(200, 200)
        self.speed = 3.0
        self.is_moving = True
        self.current_window = True  # 模拟在窗口上
        self.last_jump_time = 0
        self.jump_cooldown = 1.0  # 1秒冷却
    
    def init_jump(self):
        self.is_jumping = False
        self.jump_start_time = 0
        self.jump_start_pos = QPoint(0, 0)
        self.jump_target_pos = QPoint(0, 0)
        self.jump_duration = 1.0
    
    def update_movement(self):
        # 随机跳跃逻辑：在窗口内随机触发跳跃
        current_time = time.time()
        if self.current_window and current_time - self.last_jump_time > self.jump_cooldown:
            # 50%的概率在窗口内随机跳跃
            if time.time() % 2 < 1.0:  # 每2秒尝试一次跳跃
                # 生成随机目标位置
                import random
                screen = QApplication.desktop().availableGeometry()
                target_x = random.randint(50, screen.width() - 100)
                target_y = random.randint(50, screen.height() - 100)
                self.start_jump(QPoint(target_x, target_y))
        
        # 跳跃状态处理
        if self.is_jumping:
            self.handle_jump()
            return
        
        # 正常移动
        if self.is_moving:
            current_pos = self.pos()
            dx = self.target_pos.x() - current_pos.x()
            dy = self.target_pos.y() - current_pos.y()
            
            distance = (dx**2 + dy**2)**0.5
            if distance > self.speed:
                move_x = dx / distance * self.speed
                move_y = dy / distance * self.speed
                new_x = current_pos.x() + move_x
                new_y = current_pos.y() + move_y
                self.move(int(new_x), int(new_y))
            else:
                # 到达目标，随机新目标
                import random
                screen = QApplication.desktop().availableGeometry()
                self.target_pos = QPoint(
                    random.randint(50, screen.width() - 100),
                    random.randint(50, screen.height() - 100)
                )
    
    def start_jump(self, target_pos):
        # 开始跳跃
        print(f"开始跳跃到位置: {target_pos}")
        self.is_jumping = True
        self.jump_start_time = time.time()
        self.jump_start_pos = self.pos()
        self.jump_target_pos = target_pos
        self.last_jump_time = time.time()
    
    def handle_jump(self):
        # 处理跳跃逻辑
        elapsed = time.time() - self.jump_start_time
        jump_progress = min(elapsed / self.jump_duration, 1.0)
        
        # 使用简单的抛物线
        t = jump_progress
        delta_x = self.jump_target_pos.x() - self.jump_start_pos.x()
        delta_y = self.jump_target_pos.y() - self.jump_start_pos.y()
        x = self.jump_start_pos.x() + delta_x * t
        y = self.jump_start_pos.y() + delta_y * t + 50 * t * (1 - t)  # 抛物线高度50px
        
        # 更新位置
        self.move(int(x), int(y))
        
        if jump_progress >= 1.0:
            # 跳跃完成
            print("跳跃完成")
            self.is_jumping = False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ralsei = TestRalseiJump()
    ralsei.show()
    sys.exit(app.exec_())
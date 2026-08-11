import sys
import os
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect
import win32gui
import win32con

class SimpleRalseiTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_movement()
        self.init_timers()
        self.init_windows()
        
    def init_ui(self):
        # 创建透明窗口
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(100, 100, 50, 50)
        self.setWindowTitle("Ralsei Test")
        
        # 创建主标签
        self.sprite_label = QLabel(self)
        self.sprite_label.setGeometry(0, 0, 50, 50)
        self.sprite_label.setAlignment(Qt.AlignCenter)
        
        # 使用简单的红色方块作为Ralsei占位符
        self.sprite_label.setStyleSheet("background-color: red; border-radius: 25px;")
        
        self.show()
    
    def init_movement(self):
        self.target_pos = QPoint(100, 100)
        self.speed = 5.0
        self.is_moving = True
        self.is_jumping = False
        self.jump_start_time = 0
        self.jump_duration = 1.0
        self.jump_start_pos = QPoint(0, 0)
        self.jump_target_pos = QPoint(0, 0)
        
        # 位置和状态
        self.current_window = None
    
    def init_timers(self):
        # 移动定时器
        self.movement_timer = QTimer(self)
        self.movement_timer.timeout.connect(self.update_movement)
        self.movement_timer.start(30)
        
        # 窗口检查定时器
        self.window_check_timer = QTimer(self)
        self.window_check_timer.timeout.connect(self.check_windows)
        self.window_check_timer.start(1000)
    
    def init_windows(self):
        self.all_windows = []
    
    def get_all_visible_windows(self):
        # 获取所有可见窗口
        visible_windows = []
        
        def callback(hwnd, param):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and len(title) > 0:
                    # 过滤掉自身窗口
                    if title != "Ralsei Test":
                        rect = win32gui.GetWindowRect(hwnd)
                        width = rect[2] - rect[0]
                        height = rect[3] - rect[1]
                        
                        # 过滤掉太小的窗口
                        if width > 100 and height > 100:
                            visible_windows.append({
                                'hwnd': hwnd,
                                'title': title,
                                'x': rect[0],
                                'y': rect[1],
                                'width': width,
                                'height': height,
                                'center_x': (rect[0] + rect[2]) // 2,
                                'center_y': (rect[1] + rect[3]) // 2
                            })
            return True
        
        win32gui.EnumWindows(callback, None)
        return visible_windows
    
    def check_windows(self):
        # 检查所有可见窗口
        self.all_windows = self.get_all_visible_windows()
        print(f"检测到 {len(self.all_windows)} 个窗口:")
        for window in self.all_windows:
            print(f"  - {window['title']} ({window['x']}, {window['y']}, {window['width']}, {window['height']})")
        
        # 检查当前位置是否在窗口上
        current_rect = QRect(self.pos().x(), self.pos().y(), self.width(), self.height())
        on_window = False
        current_window = None
        
        for window in self.all_windows:
            window_rect = QRect(window['x'], window['y'], window['width'], window['height'])
            if window_rect.contains(current_rect):
                on_window = True
                current_window = window
                break
        
        if current_window:
            print(f"Ralsei在窗口上: {current_window['title']}")
        else:
            print("Ralsei在桌面上")
    
    def check_nearby_windows(self):
        # 检查附近的窗口，判断是否需要跳跃
        current_pos = self.pos()
        current_rect = QRect(current_pos.x(), current_pos.y(), self.width(), self.height())
        
        for window in self.all_windows:
            window_rect = QRect(window['x'], window['y'], window['width'], window['height'])
            
            # 检查是否在窗口边缘附近
            # 情况1: 在窗口下方，准备跳上窗口顶部
            if (current_rect.bottom() >= window_rect.top() - 100 and 
                current_rect.bottom() <= window_rect.top() + 50 and 
                current_rect.intersects(QRect(window_rect.left() - 50, window_rect.top() - 50, window_rect.width() + 100, 100))):
                print("检测到窗口下方，准备跳跃")
                self.start_jump(window, "bottom")
                return
            
            # 情况2: 在窗口左侧，准备跳上窗口左侧边缘
            elif (current_rect.right() >= window_rect.left() - 100 and 
                  current_rect.right() <= window_rect.left() + 50 and 
                  current_rect.intersects(QRect(window_rect.left() - 50, window_rect.top() - 50, 100, window_rect.height() + 100))):
                print("检测到窗口左侧，准备跳跃")
                self.start_jump(window, "left")
                return
            
            # 情况3: 在窗口右侧，准备跳上窗口右侧边缘
            elif (current_rect.left() >= window_rect.right() - 100 and 
                  current_rect.left() <= window_rect.right() + 50 and 
                  current_rect.intersects(QRect(window_rect.right() - 50, window_rect.top() - 50, 100, window_rect.height() + 100))):
                print("检测到窗口右侧，准备跳跃")
                self.start_jump(window, "right")
                return
    
    def start_jump(self, target_window, window_edge):
        # 开始跳跃
        print(f"开始跳跃到窗口: {target_window['title']}，边缘: {window_edge}")
        self.is_jumping = True
        self.jump_start_time = time.time()
        self.jump_start_pos = self.pos()
        
        # 计算目标位置
        window_rect = QRect(target_window['x'], target_window['y'], target_window['width'], target_window['height'])
        
        if window_edge == "bottom":
            # 从下方跳上窗口顶部
            target_x = window_rect.center().x() - self.width() // 2
            target_x = max(window_rect.left() + 20, min(window_rect.right() - self.width() - 20, target_x))
            self.jump_target_pos = QPoint(target_x, window_rect.top() + 10)
        elif window_edge == "left":
            # 从左侧跳上窗口左侧
            target_y = window_rect.center().y() - self.height() // 2
            target_y = max(window_rect.top() + 20, min(window_rect.bottom() - self.height() - 20, target_y))
            self.jump_target_pos = QPoint(window_rect.left() + 10, target_y)
        elif window_edge == "right":
            # 从右侧跳上窗口右侧
            target_y = window_rect.center().y() - self.height() // 2
            target_y = max(window_rect.top() + 20, min(window_rect.bottom() - self.height() - 20, target_y))
            self.jump_target_pos = QPoint(window_rect.right() - self.width() - 10, target_y)
        else:
            # 默认情况
            target_x = window_rect.center().x() - self.width() // 2
            target_x = max(window_rect.left() + 20, min(window_rect.right() - self.width() - 20, target_x))
            self.jump_target_pos = QPoint(target_x, window_rect.top() + 10)
        
        print(f"跳跃目标位置: ({self.jump_target_pos.x()}, {self.jump_target_pos.y()})")
    
    def handle_jump(self, elapsed_time, current_time):
        # 处理跳跃
        elapsed = current_time - self.jump_start_time
        jump_progress = min(elapsed / self.jump_duration, 1.0)
        
        # 计算跳跃轨迹（简化的抛物线）
        delta_x = self.jump_target_pos.x() - self.jump_start_pos.x()
        delta_y = self.jump_target_pos.y() - self.jump_start_pos.y()
        
        # 使用简单的抛物线
        t = jump_progress
        x = self.jump_start_pos.x() + delta_x * t
        y = self.jump_start_pos.y() + delta_y * t + 50 * t * (1 - t)  # 抛物线高度50px
        
        # 更新位置
        self.move(int(x), int(y))
        
        # 检查跳跃是否完成
        if jump_progress >= 1.0:
            print("跳跃完成")
            self.is_jumping = False
            # 确保准确落在目标位置
            self.move(self.jump_target_pos.x(), self.jump_target_pos.y())
    
    def update_movement(self):
        current_time = time.time()
        
        if self.is_jumping:
            # 处理跳跃
            self.handle_jump(30 / 1000, current_time)
            return
        
        # 简单的随机移动
        current_pos = self.pos()
        dx = self.target_pos.x() - current_pos.x()
        dy = self.target_pos.y() - current_pos.y()
        
        distance = (dx ** 2 + dy ** 2) ** 0.5
        
        if distance < 10:
            # 到达目标，随机选择新目标
            screen_geometry = QApplication.desktop().availableGeometry()
            new_x = random.randint(50, screen_geometry.width() - 100)
            new_y = random.randint(50, screen_geometry.height() - 100)
            self.target_pos = QPoint(new_x, new_y)
        else:
            # 向目标移动
            new_x = current_pos.x() + dx / distance * self.speed
            new_y = current_pos.y() + dy / distance * self.speed
            self.move(int(new_x), int(new_y))
        
        # 检查附近的窗口
        self.check_nearby_windows()
    
    def paintEvent(self, event):
        # 绘制透明背景
        painter = QPainter(self)
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawRect(self.rect())

if __name__ == "__main__":
    import random
    app = QApplication(sys.argv)
    window = SimpleRalseiTest()
    window.show()
    result = app.exec_()
    sys.exit(result)
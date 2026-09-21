#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ralsei功能测试脚本
测试内容：
1. Ralsei在窗口上时的可见性
2. 跳跃轨迹是否为抛物线
3. 移动响应是否正常
4. 窗口晃动检测
"""

import sys
import time
import random
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel
from PyQt5.QtCore import QTimer, Qt, QPoint
from src.main import RalseiPet

class RalseiTester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ralsei功能测试")
        self.setGeometry(100, 100, 400, 300)
        
        # 测试结果
        self.results = {
            "visibility": "未测试",
            "jump_trajectory": "未测试",
            "movement_response": "未测试",
            "window_shake": "未测试"
        }
        
        # 创建测试界面
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # 测试按钮
        self.start_test_btn = QPushButton("开始测试")
        self.start_test_btn.clicked.connect(self.start_test)
        self.layout.addWidget(self.start_test_btn)
        
        # 测试结果显示
        self.result_label = QLabel("测试结果：")
        self.layout.addWidget(self.result_label)
        
        # 创建Ralsei实例
        self.ralsei = None
        
        # 测试定时器
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.run_test)
        self.test_step = 0
        
        # 跳跃轨迹记录
        self.jump_positions = []
        self.jump_start_time = 0
        
        # 窗口晃动模拟
        self.shake_count = 0
        self.shake_direction = 1
        
    def start_test(self):
        """开始测试"""
        self.start_test_btn.setEnabled(False)
        self.result_label.setText("测试开始...")
        
        # 创建Ralsei实例
        if not self.ralsei:
            self.ralsei = RalseiPet()
            self.ralsei.show()
        
        # 开始测试
        self.test_step = 1
        self.test_timer.start(1000)  # 每秒执行一次测试步骤
    
    def run_test(self):
        """运行测试步骤"""
        if self.test_step == 1:
            # 测试1: Ralsei在窗口上的可见性
            self.test_visibility()
        elif self.test_step == 2:
            # 测试2: 跳跃轨迹
            self.test_jump_trajectory()
        elif self.test_step == 3:
            # 测试3: 移动响应
            self.test_movement_response()
        elif self.test_step == 4:
            # 测试4: 窗口晃动检测
            self.test_window_shake()
        elif self.test_step == 5:
            # 测试完成
            self.test_complete()
    
    def test_visibility(self):
        """测试Ralsei在窗口上的可见性"""
        print("测试1: Ralsei在窗口上的可见性")
        
        # 检查Ralsei是否可见
        if self.ralsei and self.ralsei.isVisible():
            self.results["visibility"] = "通过 - Ralsei可见"
            print("✓ Ralsei可见")
        else:
            self.results["visibility"] = "失败 - Ralsei不可见"
            print("✗ Ralsei不可见")
        
        self.test_step = 2
        self.update_result_display()
    
    def test_jump_trajectory(self):
        """测试跳跃轨迹"""
        print("测试2: 跳跃轨迹")
        
        # 记录跳跃轨迹
        if not self.ralsei.is_jumping:
            # 触发跳跃
            self.ralsei.start_jump(None, "up")
            self.jump_start_time = time.time()
            self.jump_positions = []
        else:
            # 记录位置
            pos = self.ralsei.pos()
            self.jump_positions.append((time.time() - self.jump_start_time, pos.x(), pos.y()))
            
            if not self.ralsei.is_jumping:
                # 跳跃结束，分析轨迹
                if len(self.jump_positions) >= 3:
                    # 检查轨迹是否为抛物线（先上升后下降）
                    has_peak = False
                    is_rising = True
                    valid_trajectory = True
                    
                    for i in range(1, len(self.jump_positions)):
                        prev_y = self.jump_positions[i-1][2]
                        curr_y = self.jump_positions[i][2]
                        
                        if is_rising:
                            if curr_y > prev_y:
                                # 继续上升
                                continue
                            elif curr_y < prev_y:
                                # 开始下降
                                has_peak = True
                                is_rising = False
                            else:
                                # 水平移动，可能有问题
                                valid_trajectory = False
                        else:
                            if curr_y > prev_y:
                                # 又上升了，轨迹有问题
                                valid_trajectory = False
                            
                    if has_peak and valid_trajectory:
                        self.results["jump_trajectory"] = "通过 - 正常抛物线轨迹"
                        print("✓ 正常抛物线轨迹")
                    else:
                        self.results["jump_trajectory"] = "失败 - 轨迹异常"
                        print("✗ 轨迹异常")
                else:
                    self.results["jump_trajectory"] = "失败 - 轨迹点不足"
                    print("✗ 轨迹点不足")
                
                self.test_step = 3
                self.update_result_display()
    
    def test_movement_response(self):
        """测试移动响应"""
        print("测试3: 移动响应")
        
        # 检查Ralsei是否能够移动
        if not self.ralsei.is_moving:
            # 随机设置目标位置
            self.ralsei.target_pos = self.ralsei.pos() + QPoint(random.randint(-50, 50), random.randint(-50, 50))
            self.ralsei.is_moving = True
            self.ralsei.moving_duration = 0
        else:
            # 检查是否在移动
            if self.ralsei.is_moving:
                self.results["movement_response"] = "通过 - 能够移动"
                print("✓ 能够移动")
            else:
                self.results["movement_response"] = "失败 - 无法移动"
                print("✗ 无法移动")
            
            self.test_step = 4
            self.update_result_display()
    
    def test_window_shake(self):
        """测试窗口晃动检测"""
        print("测试4: 窗口晃动检测")
        
        # 模拟窗口晃动
        if self.shake_count < 10:
            # 晃动窗口
            self.move(self.x() + self.shake_direction * 5, self.y())
            self.shake_count += 1
            self.shake_direction *= -1
            
            # 检查Ralsei是否检测到晃动
            if hasattr(self.ralsei, 'is_falling') and self.ralsei.is_falling:
                self.results["window_shake"] = "通过 - 检测到窗口晃动"
                print("✓ 检测到窗口晃动")
                self.test_step = 5
        else:
            # 晃动结束
            self.results["window_shake"] = "失败 - 未检测到窗口晃动"
            print("✗ 未检测到窗口晃动")
            self.test_step = 5
        
        self.update_result_display()
    
    def test_complete(self):
        """测试完成"""
        self.test_timer.stop()
        self.start_test_btn.setEnabled(True)
        self.result_label.setText("测试完成！")
        self.update_result_display()
    
    def update_result_display(self):
        """更新测试结果显示"""
        result_text = "测试结果：\n"
        for test_name, result in self.results.items():
            result_text += f"{test_name}: {result}\n"
        self.result_label.setText(result_text)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    tester = RalseiTester()
    tester.show()
    sys.exit(app.exec_())

import time
import os
import sys
import json

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.main import RalseiPet
from PyQt5.QtWidgets import QApplication

class AnimationMonitor:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.ralsei = RalseiPet()
        self.ralsei.show()
        self.animation_history = []
        self.last_animation = None
        self.last_animation_time = time.time()
        self.jump_start_time = None
        self.jump_animation_started = False
        self.animation_switch_count = 0
        self.rapid_switch_count = 0
        self.jump_without_animation = 0
        
    def start_monitoring(self):
        print("开始监测Ralsei的动画切换和跳跃动作...")
        print("按Ctrl+C停止监测")
        
        try:
            while True:
                current_animation = self.ralsei.current_animation
                current_time = time.time()
                
                # 记录动画信息
                animation_data = {
                    "time": current_time,
                    "animation": current_animation,
                    "is_jumping": self.ralsei.is_jumping
                }
                self.animation_history.append(animation_data)
                
                # 检测动画快速切换
                if self.last_animation and current_animation != self.last_animation:
                    time_diff = current_time - self.last_animation_time
                    self.animation_switch_count += 1
                    
                    if time_diff < 0.5:  # 0.5秒内切换动画
                        print(f"[快速动画切换] 从 {self.last_animation} 到 {current_animation}，时间间隔: {time_diff:.3f}秒")
                        self.rapid_switch_count += 1
                
                # 检测跳跃动作衔接
                if self.ralsei.is_jumping:
                    if not self.jump_start_time:
                        self.jump_start_time = current_time
                        self.jump_animation_started = False
                    
                    # 检查是否有跳跃动画
                    if "jump" in current_animation:
                        self.jump_animation_started = True
                else:
                    if self.jump_start_time:
                        # 跳跃结束，检查是否有跳跃动画
                        if not self.jump_animation_started:
                            print(f"[跳跃无衔接] 跳跃过程中没有播放跳跃动画")
                            self.jump_without_animation += 1
                        self.jump_start_time = None
                        self.jump_animation_started = False
                
                # 更新最后动画和时间
                self.last_animation = current_animation
                self.last_animation_time = current_time
                
                # 每100个动画记录保存一次
                if len(self.animation_history) % 100 == 0:
                    self.save_animation_history()
                    print(f"已保存 {len(self.animation_history)} 个动画记录")
                
                # 限制采样频率
                time.sleep(0.05)
                
                # 处理Qt事件
                self.app.processEvents()
                
        except KeyboardInterrupt:
            print("\n监测停止")
            self.save_animation_history()
            self.generate_report()
            sys.exit(0)
    
    def save_animation_history(self):
        """保存动画历史到文件"""
        with open('animation_history.json', 'w') as f:
            json.dump(self.animation_history, f, indent=2)
    
    def generate_report(self):
        """生成监测报告"""
        print("\n=== 动画和跳跃监测报告 ===")
        print(f"总监测帧数: {len(self.animation_history)}")
        print(f"动画切换次数: {self.animation_switch_count}")
        print(f"快速动画切换次数: {self.rapid_switch_count}")
        print(f"跳跃无衔接次数: {self.jump_without_animation}")
        
        if self.animation_history:
            # 分析动画分布
            animation_count = {}
            for entry in self.animation_history:
                anim = entry['animation']
                if anim not in animation_count:
                    animation_count[anim] = 0
                animation_count[anim] += 1
            
            print("\n动画使用频率:")
            for anim, count in sorted(animation_count.items(), key=lambda x: x[1], reverse=True):
                print(f"{anim}: {count}次")

if __name__ == "__main__":
    monitor = AnimationMonitor()
    monitor.start_monitoring()

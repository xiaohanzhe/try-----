import time
import os
import sys
import json

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.main import RalseiPet
from PyQt5.QtWidgets import QApplication

class CoordinateMonitor:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.ralsei = RalseiPet()
        self.ralsei.show()
        self.coordinates = []
        self.last_pos = None
        self.last_time = time.time()
        self.threshold = 50  # 瞬移阈值（像素）
        self.jitter_threshold = 10  # 抽搐阈值（像素）
        self.jitter_count = 0
        self.teleport_count = 0
        
    def start_monitoring(self):
        print("开始监测Ralsei的坐标变化...")
        print("按Ctrl+C停止监测")
        
        try:
            while True:
                current_pos = self.ralsei.pos()
                current_time = time.time()
                
                # 计算时间差
                time_diff = current_time - self.last_time
                
                # 记录坐标
                coord_data = {
                    "time": current_time,
                    "x": current_pos.x(),
                    "y": current_pos.y(),
                    "time_diff": time_diff
                }
                self.coordinates.append(coord_data)
                
                # 检测瞬移
                if self.last_pos:
                    distance = ((current_pos.x() - self.last_pos.x()) ** 2 + 
                               (current_pos.y() - self.last_pos.y()) ** 2) ** 0.5
                    
                    if distance > self.threshold:
                        print(f"[瞬移检测] 从 ({self.last_pos.x()}, {self.last_pos.y()}) 到 ({current_pos.x()}, {current_pos.y()})，距离: {distance:.2f}px")
                        self.teleport_count += 1
                    
                    # 检测抽搐（短时间内来回移动）
                    if 0 < distance < self.jitter_threshold and time_diff < 0.1:
                        self.jitter_count += 1
                        if self.jitter_count >= 3:
                            print(f"[抽搐检测] 在 ({current_pos.x()}, {current_pos.y()}) 附近出现抽搐")
                            self.jitter_count = 0
                
                # 更新最后位置和时间
                self.last_pos = current_pos
                self.last_time = current_time
                
                # 每100个坐标点保存一次
                if len(self.coordinates) % 100 == 0:
                    self.save_coordinates()
                    print(f"已保存 {len(self.coordinates)} 个坐标点")
                
                # 限制采样频率
                time.sleep(0.05)
                
                # 处理Qt事件
                self.app.processEvents()
                
        except KeyboardInterrupt:
            print("\n监测停止")
            self.save_coordinates()
            self.generate_report()
            sys.exit(0)
    
    def save_coordinates(self):
        """保存坐标数据到文件"""
        with open('coordinates.json', 'w') as f:
            json.dump(self.coordinates, f, indent=2)
    
    def generate_report(self):
        """生成监测报告"""
        print("\n=== 监测报告 ===")
        print(f"总监测点数: {len(self.coordinates)}")
        print(f"瞬移次数: {self.teleport_count}")
        print(f"抽搐次数: {self.jitter_count}")
        
        if self.coordinates:
            # 计算平均移动速度
            total_distance = 0
            total_time = 0
            
            for i in range(1, len(self.coordinates)):
                prev = self.coordinates[i-1]
                curr = self.coordinates[i]
                distance = ((curr['x'] - prev['x']) ** 2 + (curr['y'] - prev['y']) ** 2) ** 0.5
                total_distance += distance
                total_time += curr['time_diff']
            
            if total_time > 0:
                avg_speed = total_distance / total_time
                print(f"平均移动速度: {avg_speed:.2f} px/s")
            
            # 分析坐标变化趋势
            print("\n坐标变化趋势:")
            x_coords = [c['x'] for c in self.coordinates]
            y_coords = [c['y'] for c in self.coordinates]
            
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)
            
            print(f"X坐标范围: {x_min} - {x_max}")
            print(f"Y坐标范围: {y_min} - {y_max}")
            print(f"活动区域: {x_max - x_min}x{y_max - y_min} px")

if __name__ == "__main__":
    monitor = CoordinateMonitor()
    monitor.start_monitoring()

import sys
import os
import traceback

# 添加项目根目录到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
print(f"添加项目根目录: {project_root}")

# 导入必要的模块
try:
    from PyQt5.QtWidgets import QApplication, QLabel
    from PyQt5.QtGui import QPixmap
    from PyQt5.QtCore import Qt, QTimer
    print("PyQt5 导入成功")
except Exception as e:
    print(f"PyQt5 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    from modules.sprite_loader import SpriteLoader
    print("SpriteLoader 导入成功")
except Exception as e:
    print(f"SpriteLoader 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

class RalseiPetSimple:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = QLabel()
        self.window.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.window.setGeometry(100, 100, 200, 200)
        
        # 加载精灵资源
        self.sprite_loader = SpriteLoader()
        self.sprite_loader.load_sprites(debug=True)
        print(f"加载了 {len(self.sprite_loader.sprites)} 个动画组")
        
        # 显示第一个精灵
        if 'idle' in self.sprite_loader.sprites:
            idle_frames = self.sprite_loader.sprites['idle']
            if idle_frames:
                pixmap = idle_frames[0]
                self.window.setPixmap(pixmap)
                # 调整窗口大小以适应精灵
                self.window.resize(pixmap.width(), pixmap.height())
                print("显示 idle 动画")
        
        self.window.show()
        print("窗口显示成功")
    
    def run(self):
        return self.app.exec_()

if __name__ == "__main__":
    print("启动 Ralsei Pet 简化版...")
    try:
        pet = RalseiPetSimple()
        sys.exit(pet.run())
    except Exception as e:
        print(f"程序运行时出错: {e}")
        traceback.print_exc()
        input("按回车键退出...")
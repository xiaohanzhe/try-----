import sys
import os
import traceback

# 添加项目根目录到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), 'ralsei_pet'))
sys.path.insert(0, project_root)
print(f"添加项目根目录: {project_root}")

try:
    # 导入RalseiPet类
    from src.main import RalseiPet
    print("RalseiPet 导入成功")
except Exception as e:
    print(f"RalseiPet 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    print("测试 Ralsei Pet 启动...")
    try:
        # 先创建QApplication实例
        from PyQt5.QtWidgets import QApplication
        qapp = QApplication(sys.argv)
        print("QApplication 创建成功")
        
        # 再创建RalseiPet实例
        app = RalseiPet()
        print("RalseiPet 初始化成功")
        app.show()
        print("窗口显示成功")
        sys.exit(qapp.exec_())
    except Exception as e:
        print(f"程序运行时出错: {e}")
        traceback.print_exc()
        input("按回车键退出...")
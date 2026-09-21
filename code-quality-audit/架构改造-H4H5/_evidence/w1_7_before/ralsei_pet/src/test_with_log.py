import os
import sys

# 重定向输出到文件
log_file = "test_log.txt"
print(f"将输出重定向到: {log_file}")

# 保存原始 stdout
original_stdout = sys.stdout

# 打开日志文件
with open(log_file, 'w') as f:
    # 重定向 stdout
    sys.stdout = f
    
    print("基本测试脚本")
    print("=" * 50)
    
    # 打印Python信息
    print(f"Python版本: {sys.version}")
    print(f"Python路径: {sys.executable}")
    
    # 打印当前工作目录
    print(f"\n当前工作目录: {os.getcwd()}")
    
    # 检查项目目录结构
    print("\n项目目录结构:")
    project_root = os.path.join(os.path.dirname(__file__), '..')
    print(f"项目根目录: {project_root}")
    print(f"项目根目录是否存在: {os.path.exists(project_root)}")
    
    # 检查modules目录
    modules_dir = os.path.join(project_root, 'modules')
    print(f"\n模块目录: {modules_dir}")
    print(f"模块目录是否存在: {os.path.exists(modules_dir)}")
    
    if os.path.exists(modules_dir):
        print("模块目录中的文件:")
        for file in os.listdir(modules_dir):
            print(f"  {file}")
    
    # 检查精灵目录
    sprite_dir = "c:/Users/23002/Documents/trae_projects/try/deltarune_ralsei"
    print(f"\n精灵目录: {sprite_dir}")
    print(f"精灵目录是否存在: {os.path.exists(sprite_dir)}")
    
    if os.path.exists(sprite_dir):
        print("精灵目录中的文件数量:", len(os.listdir(sprite_dir)))
        
        # 检查特定文件
        idle_file = "spr_ralsei_idle_0.png"
        idle_path = os.path.join(sprite_dir, idle_file)
        print(f"\n检查特定文件: {idle_path}")
        print(f"文件是否存在: {os.path.exists(idle_path)}")
    
    # 检查ralsei_face目录
    face_dir = "c:/Users/23002/Documents/trae_projects/try/ralsei_face"
    print(f"\n表情目录: {face_dir}")
    print(f"表情目录是否存在: {os.path.exists(face_dir)}")
    
    if os.path.exists(face_dir):
        print("表情目录中的文件数量:", len(os.listdir(face_dir)))
    
    # 测试PyQt5导入
    print("\n测试PyQt5导入:")
    try:
        import PyQt5
        print(f"成功导入PyQt5, 版本: {PyQt5.__version__}")
        
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtWidgets import QApplication
        print("成功导入PyQt5的核心组件")
        
        # 测试创建QApplication（不显示窗口）
        app = QApplication(sys.argv)
        print("成功创建QApplication实例")
        
        # 测试加载精灵
        print("\n测试加载精灵:")
        if os.path.exists(sprite_dir):
            idle_file = "spr_ralsei_idle_0.png"
            idle_path = os.path.join(sprite_dir, idle_file)
            if os.path.exists(idle_path):
                pixmap = QPixmap(idle_path)
                if not pixmap.isNull():
                    print(f"成功加载精灵: {idle_file}, 大小: {pixmap.width()}x{pixmap.height()}")
                else:
                    print(f"加载精灵失败: {idle_file} (空像素图)")
    except Exception as e:
        print(f"PyQt5导入或使用出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n基本测试完成！")
    
# 恢复原始 stdout
sys.stdout = original_stdout
print(f"测试完成，日志已保存到: {log_file}")

# 显示日志文件内容
print("\n日志文件内容:")
with open(log_file, 'r') as f:
    content = f.read()
    print(content)
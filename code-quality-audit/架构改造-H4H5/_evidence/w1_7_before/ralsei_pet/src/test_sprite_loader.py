import os
import sys

# 添加模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from modules.sprite_loader import SpriteLoader

print("测试精灵加载器")
print("=" * 50)

# 创建精灵加载器实例
sprite_loader = SpriteLoader()

# 测试精灵目录
print(f"精灵目录: {sprite_loader.sprite_dir}")
print(f"精灵目录是否存在: {os.path.exists(sprite_loader.sprite_dir)}")

# 列出精灵目录中的文件
if os.path.exists(sprite_loader.sprite_dir):
    print("\n精灵目录中的文件:")
    files = os.listdir(sprite_loader.sprite_dir)
    print(f"文件数量: {len(files)}")
    print("前10个文件:")
    for file in files[:10]:
        print(f"  {file}")

# 测试加载一个简单的精灵
print("\n测试加载单个精灵:")
test_animation = "idle"
if test_animation in sprite_loader.animation_mapping:
    test_files = sprite_loader.animation_mapping[test_animation]
    print(f"测试动画: {test_animation}")
    print(f"关联文件: {test_files}")
    
    # 尝试加载第一个文件
    if test_files:
        first_file = test_files[0]
        file_path = os.path.join(sprite_loader.sprite_dir, first_file)
        print(f"\n尝试加载文件: {file_path}")
        print(f"文件是否存在: {os.path.exists(file_path)}")
        
        if os.path.exists(file_path):
            try:
                from PyQt5.QtGui import QPixmap
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    print(f"成功加载: {first_file}, 大小: {pixmap.width()}x{pixmap.height()}")
                else:
                    print(f"加载失败: {first_file} (空像素图)")
            except Exception as e:
                print(f"加载文件出错: {first_file}, 错误: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"文件不存在: {first_file}")

print("\n测试完成！")
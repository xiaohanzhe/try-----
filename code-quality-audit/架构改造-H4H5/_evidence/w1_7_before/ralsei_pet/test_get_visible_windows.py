# 测试修改后的get_all_visible_windows函数

# 添加项目根目录到sys.path
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
sys.path.insert(0, project_root)

# 导入DesktopInteraction类
from modules.desktop_interaction import DesktopInteraction

# 创建一个模拟的父对象
class MockParent:
    pass

# 初始化DesktopInteraction
parent = MockParent()
desktop_interaction = DesktopInteraction(parent)

# 测试get_all_visible_windows函数
print("=== 测试修改后的get_all_visible_windows函数 ===")
windows = desktop_interaction.get_all_visible_windows()

print(f"\n共检测到 {len(windows)} 个可见窗口：\n")

for i, window in enumerate(windows, 1):
    print(f"窗口 {i}:")
    print(f"  标题: {window['title']}")
    print(f"  类名: {window['hwnd']}")
    print(f"  位置: ({window['x']}, {window['y']})")
    print(f"  大小: {window['width']}x{window['height']}")
    print(f"  Z序: {window['z_order']}")
    print()

# 检查是否有"设置"窗口
settings_windows = [w for w in windows if "设置" in w['title']]
if settings_windows:
    print(f"警告：检测到 {len(settings_windows)} 个包含'设置'的窗口！")
    for window in settings_windows:
        print(f"  - {window['title']} (位置: ({window['x']}, {window['y']}), 大小: {window['width']}x{window['height']})")
else:
    print("✓ 成功：没有检测到包含'设置'的窗口！")

print("\n=== 测试完成 ===")
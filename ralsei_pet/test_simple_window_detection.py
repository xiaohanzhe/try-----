# 简单测试窗口检测，只检查基本可见性

import win32gui
import win32process
import win32api
import win32con

print("=== 简单窗口检测测试 ===")
print("只检测可见窗口，不进行复杂过滤\n")

# 只检测可见窗口，不进行复杂过滤
def test_simple_window_detection():
    visible_windows = []
    
    def callback(hwnd, param):
        # 只处理可见窗口
        if win32gui.IsWindowVisible(hwnd):
            # 获取窗口标题
            title = win32gui.GetWindowText(hwnd)
            if title:
                # 获取窗口矩形
                rect = win32gui.GetWindowRect(hwnd)
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                
                # 只过滤非常小的窗口
                if width <= 50 or height <= 50:
                    return True
                
                window_info = {
                    'hwnd': hwnd,
                    'title': title,
                    'class_name': win32gui.GetClassName(hwnd),
                    'x': rect[0],
                    'y': rect[1],
                    'width': width,
                    'height': height
                }
                visible_windows.append(window_info)
        return True
    
    # 枚举所有窗口
    win32gui.EnumWindows(callback, None)
    
    return visible_windows

# 运行测试
windows = test_simple_window_detection()

print(f"\n共检测到 {len(windows)} 个可见窗口：\n")

for i, window in enumerate(windows, 1):
    print(f"窗口 {i}:")
    print(f"  标题: {window['title']}")
    print(f"  类名: {window['class_name']}")
    print(f"  位置: ({window['x']}, {window['y']})")
    print(f"  大小: {window['width']}x{window['height']}")
    print()

# 检查是否有我们的软件窗口
our_windows = [w for w in windows if "try" in w['title'] or "Trae" in w['title']]
if our_windows:
    print(f"检测到 {len(our_windows)} 个我们的软件窗口：")
    for window in our_windows:
        print(f"  - {window['title']}")
else:
    print("没有检测到我们的软件窗口！")

# 检查是否有"设置"窗口
settings_windows = [w for w in windows if "设置" in w['title']]
if settings_windows:
    print(f"\n检测到 {len(settings_windows)} 个包含'设置'的窗口：")
    for window in settings_windows:
        print(f"  - {window['title']} (类名: {window['class_name']})")
else:
    print("\n✓ 没有检测到包含'设置'的窗口！")

print("\n=== 测试完成 ===")
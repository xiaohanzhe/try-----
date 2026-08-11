# 测试简化后的窗口检测逻辑

import win32gui
import win32process
import win32api
import win32con

print("=== 测试简化后的窗口检测逻辑 ===")
print("只过滤明显不需要的窗口：设置窗口、系统窗口和非常小的窗口\n")

# 使用简化后的过滤逻辑
def test_get_visible_windows_simplified():
    visible_windows = []
    
    def callback(hwnd, param):
        # 只处理可见窗口
        if win32gui.IsWindowVisible(hwnd):
            # 获取窗口标题
            title = win32gui.GetWindowText(hwnd)
            if title:
                # 获取窗口类名
                class_name = win32gui.GetClassName(hwnd)
                
                # 获取窗口矩形
                rect = win32gui.GetWindowRect(hwnd)
                # 计算窗口大小
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                
                # 简化过滤逻辑，只过滤明显不需要的窗口
                
                # 1. 过滤掉Windows设置应用
                if "设置" in title:
                    return True
                
                # 2. 过滤掉系统窗口类
                system_classes = [
                    "WorkerW", 
                    "Progman", 
                    "Program Manager",
                    "Shell_TrayWnd",
                    "TrayNotifyWnd",
                    "ClockWClass"
                ]
                if class_name in system_classes:
                    return True
                
                # 3. 过滤掉非常小的窗口（可能是系统组件）
                if width <= 100 or height <= 100:
                    return True
                
                # 4. 屏蔽Ralsei相关窗口，避免检测到自身
                if "Ralsei" in title or "ralsei" in title:
                    return True
                
                # 5. 过滤掉屏幕外的窗口
                screen_width = win32api.GetSystemMetrics(0)
                screen_height = win32api.GetSystemMetrics(1)
                if (rect[0] > screen_width or rect[1] > screen_height or 
                    rect[2] < 0 or rect[3] < 0):
                    return True
                
                window_info = {
                    'hwnd': hwnd,
                    'title': title,
                    'class_name': class_name,
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
windows = test_get_visible_windows_simplified()

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
    print(f"\n警告：检测到 {len(settings_windows)} 个包含'设置'的窗口：")
    for window in settings_windows:
        print(f"  - {window['title']}")
else:
    print("\n✓ 成功：没有检测到包含'设置'的窗口！")

print("\n=== 测试完成 ===")
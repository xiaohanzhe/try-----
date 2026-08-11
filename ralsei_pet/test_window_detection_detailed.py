# 详细测试窗口检测逻辑，显示更多窗口信息

import win32gui
import win32process
import win32api
import win32con

print("=== 详细测试窗口检测逻辑 ===")
print("显示所有可见窗口，包括过滤掉的窗口\n")

# 复制get_all_visible_windows函数的逻辑，但不过滤结果，只是记录过滤原因
def test_get_visible_windows_detailed():
    all_windows = []
    filtered_windows = []
    
    def callback(hwnd, param):
        # 只处理可见窗口
        if win32gui.IsWindowVisible(hwnd):
            # 获取窗口标题
            title = win32gui.GetWindowText(hwnd)
            if title:
                # 获取窗口类名
                class_name = win32gui.GetClassName(hwnd)
                
                window_info = {
                    'hwnd': hwnd,
                    'title': title,
                    'class_name': class_name,
                    'filtered': False,
                    'filter_reason': ""
                }
                
                # 获取窗口矩形
                rect = win32gui.GetWindowRect(hwnd)
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                window_info['x'] = rect[0]
                window_info['y'] = rect[1]
                window_info['width'] = width
                window_info['height'] = height
                
                # 检查过滤条件
                # 1. 窗口类过滤
                filtered_classes = [
                    "Windows.UI.Core.CoreWindow",
                    "ApplicationFrameWindow",
                    "WorkerW", 
                    "Progman", 
                    "Program Manager",
                    "Shell_TrayWnd",
                    "TrayNotifyWnd",
                    "ClockWClass",
                    "Qt5152QWindowToolSaveBits",  # Python相关窗口类
                    "Chrome_WidgetWin_1",  # 浏览器组件窗口
                    "Qt51514QWindowIcon",  # 微信等应用窗口
                    "com.tencent.yuanbao-sic"  # 腾讯应用窗口
                ]
                if class_name in filtered_classes:
                    window_info['filtered'] = True
                    window_info['filter_reason'] = f"窗口类 {class_name} 在过滤列表中"
                    filtered_windows.append(window_info)
                    return True
                
                # 2. 标题包含"设置"
                if "设置" in title:
                    window_info['filtered'] = True
                    window_info['filter_reason'] = f"标题包含'设置'"
                    filtered_windows.append(window_info)
                    return True
                
                # 3. 窗口位置检查
                screen_width = win32api.GetSystemMetrics(0)
                screen_height = win32api.GetSystemMetrics(1)
                if (rect[0] > screen_width or rect[1] > screen_height or 
                    rect[2] < 0 or rect[3] < 0):
                    window_info['filtered'] = True
                    window_info['filter_reason'] = f"窗口在屏幕外: ({rect[0]}, {rect[1]}, {rect[2]}, {rect[3]})"
                    filtered_windows.append(window_info)
                    return True
                
                # 4. 窗口大小初步过滤
                if width <= 100 or height <= 100:
                    window_info['filtered'] = True
                    window_info['filter_reason'] = f"窗口太小: {width}x{height}"
                    filtered_windows.append(window_info)
                    return True
                
                # 5. Python窗口标题
                if "Python" in title or "python" in title:
                    window_info['filtered'] = True
                    window_info['filter_reason'] = f"标题包含Python"
                    filtered_windows.append(window_info)
                    return True
                
                # 6. Python窗口类
                python_class_names = ["TKTopLevel", "PyQt5", "Qt5QWindowIcon", "wxWindowClassNR", "GLFW30"]
                if any(python_class in class_name for python_class in python_class_names):
                    window_info['filtered'] = True
                    window_info['filter_reason'] = f"窗口类包含Python相关类名: {class_name}"
                    filtered_windows.append(window_info)
                    return True
                
                # 7. 透明窗口
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                if (ex_style & win32con.WS_EX_LAYERED or 
                    ex_style & win32con.WS_EX_TRANSPARENT):
                    try:
                        if ex_style & win32con.WS_EX_LAYERED:
                            alpha = win32gui.GetLayeredWindowAttributes(hwnd)[3]
                            if alpha < 255:
                                window_info['filtered'] = True
                                window_info['filter_reason'] = f"窗口是透明的，透明度: {alpha}"
                                filtered_windows.append(window_info)
                                return True
                    except Exception as e:
                        window_info['filtered'] = True
                        window_info['filter_reason'] = f"获取窗口透明度失败: {e}"
                        filtered_windows.append(window_info)
                        return True
                
                # 8. Ralsei相关窗口
                if "Ralsei" in title or "ralsei" in title:
                    window_info['filtered'] = True
                    window_info['filter_reason'] = f"标题包含Ralsei"
                    filtered_windows.append(window_info)
                    return True
                
                # 9. 标题栏和系统菜单检查
                has_caption = bool(style & win32con.WS_CAPTION)
                has_sysmenu = bool(style & win32con.WS_SYSMENU)
                if not has_caption or not has_sysmenu:
                    window_info['filtered'] = True
                    window_info['filter_reason'] = f"没有标题栏或系统菜单: has_caption={has_caption}, has_sysmenu={has_sysmenu}"
                    filtered_windows.append(window_info)
                    return True
                
                # 10. 子窗口检查
                parent_hwnd = win32gui.GetParent(hwnd)
                if parent_hwnd != 0:
                    window_info['filtered'] = True
                    window_info['filter_reason'] = f"是子窗口，父窗口句柄: {parent_hwnd}"
                    filtered_windows.append(window_info)
                    return True
                
                # 11. 窗口大小进一步过滤
                if width < 300 or height < 200:
                    window_info['filtered'] = True
                    window_info['filter_reason'] = f"窗口太小: {width}x{height}"
                    filtered_windows.append(window_info)
                    return True
                
                # 如果没有被过滤，添加到结果列表
                all_windows.append(window_info)
        return True
    
    # 枚举所有窗口
    win32gui.EnumWindows(callback, None)
    
    return all_windows, filtered_windows

# 运行测试
visible_windows, filtered_windows = test_get_visible_windows_detailed()

print(f"\n=== 检测结果 ===")
print(f"共检测到 {len(visible_windows) + len(filtered_windows)} 个可见窗口")
print(f"通过过滤: {len(visible_windows)} 个窗口")
print(f"被过滤掉: {len(filtered_windows)} 个窗口\n")

# 显示通过过滤的窗口
if visible_windows:
    print("\n=== 通过过滤的窗口 ===")
    for i, window in enumerate(visible_windows, 1):
        print(f"窗口 {i}:")
        print(f"  标题: {window['title']}")
        print(f"  类名: {window['class_name']}")
        print(f"  位置: ({window['x']}, {window['y']})")
        print(f"  大小: {window['width']}x{window['height']}")
        print()
else:
    print("\n=== 通过过滤的窗口 ===")
    print("没有窗口通过所有过滤条件！")

# 显示被过滤掉的窗口
print(f"\n=== 被过滤掉的窗口 ({len(filtered_windows)} 个) ===")
for i, window in enumerate(filtered_windows, 1):
    print(f"窗口 {i}:")
    print(f"  标题: {window['title']}")
    print(f"  类名: {window['class_name']}")
    print(f"  位置: ({window['x']}, {window['y']})")
    print(f"  大小: {window['width']}x{window['height']}")
    print(f"  过滤原因: {window['filter_reason']}")
    print()

print("=== 测试完成 ===")
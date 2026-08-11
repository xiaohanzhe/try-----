# 测试非透明窗口检测逻辑
import win32gui
import win32con
import win32api

print("=== 测试非透明窗口检测逻辑 ===")
print("只检测非透明的窗口\n")

# 直接测试窗口检测逻辑，只返回非透明窗口
def test_non_transparent_windows():
    visible_windows = []
    transparent_windows = []
    
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
                    "ClockWClass",
                    "Windows.UI.Core.CoreWindow"
                ]
                if class_name in system_classes:
                    return True
                
                # 3. 过滤掉特定的系统窗口标题
                if title == "Windows 输入体验" or title == "wv_1001":
                    return True
                
                # 4. 过滤掉非常小的窗口
                if width <= 100 or height <= 100:
                    return True
                
                # 5. 屏蔽Ralsei相关窗口
                if "Ralsei" in title or "ralsei" in title:
                    return True
                
                # 6. 过滤掉屏幕外的窗口
                screen_width = win32api.GetSystemMetrics(0)
                screen_height = win32api.GetSystemMetrics(1)
                if (rect[0] > screen_width or rect[1] > screen_height or 
                    rect[2] < 0 or rect[3] < 0):
                    return True
                
                # 7. 只检测非透明窗口
                # 获取窗口扩展样式
                ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                # 检查是否是透明窗口
                is_layered = bool(ex_style & win32con.WS_EX_LAYERED)
                is_transparent = bool(ex_style & win32con.WS_EX_TRANSPARENT)
                
                window_info = {
                    'hwnd': hwnd,
                    'title': title,
                    'class_name': class_name,
                    'x': rect[0],
                    'y': rect[1],
                    'width': width,
                    'height': height
                }
                
                if is_transparent:
                    # 完全透明窗口，跳过
                    window_info['transparent_type'] = '完全透明'
                    transparent_windows.append(window_info)
                    return True
                
                if is_layered:
                    # 分层窗口，检查透明度
                    try:
                        # 获取分层窗口属性
                        alpha = win32gui.GetLayeredWindowAttributes(hwnd)[3]
                        if alpha < 255:
                            # 半透明窗口，跳过
                            window_info['transparent_type'] = f'半透明 (alpha={alpha})'
                            transparent_windows.append(window_info)
                            return True
                    except Exception as e:
                        # 无法获取透明度，跳过
                        window_info['transparent_type'] = f'无法获取透明度 ({e})'
                        transparent_windows.append(window_info)
                        return True
                
                # 非透明窗口，添加到结果列表
                visible_windows.append(window_info)
        return True
    
    # 枚举所有窗口
    win32gui.EnumWindows(callback, None)
    
    return visible_windows, transparent_windows

# 运行测试
visible_windows, transparent_windows = test_non_transparent_windows()

print(f"=== 检测结果 ===")
print(f"共检测到 {len(visible_windows)} 个非透明窗口")
print(f"过滤掉 {len(transparent_windows)} 个透明窗口\n")

# 显示非透明窗口
if visible_windows:
    print("=== 非透明窗口列表 ===")
    for i, window in enumerate(visible_windows, 1):
        print(f"窗口 {i}:")
        print(f"  标题: {window['title']}")
        print(f"  类名: {window['class_name']}")
        print(f"  位置: ({window['x']}, {window['y']})")
        print(f"  大小: {window['width']}x{window['height']}")
        print()
else:
    print("没有检测到非透明窗口！")

# 显示透明窗口
if transparent_windows:
    print(f"\n=== 过滤掉的透明窗口列表 ({len(transparent_windows)} 个) ===")
    for i, window in enumerate(transparent_windows[:5], 1):  # 只显示前5个
        print(f"窗口 {i}:")
        print(f"  标题: {window['title']}")
        print(f"  类名: {window['class_name']}")
        print(f"  透明类型: {window['transparent_type']}")
        print()
    
    if len(transparent_windows) > 5:
        print(f"... 还有 {len(transparent_windows) - 5} 个透明窗口被过滤掉")

print("=== 测试完成 ===")

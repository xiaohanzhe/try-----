# 测试更新后的窗口检测逻辑

import win32gui
import win32process
import win32api
import win32con

print("=== 测试更新后的窗口检测逻辑 ===")

# 使用更新后的过滤逻辑
def test_get_visible_windows_updated():
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
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                
                # 过滤掉不需要的窗口类
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
                    "Qt51514QWindowIcon",  # 微信等应用窗口
                    "com.tencent.yuanbao-sic"  # 腾讯应用窗口
                ]
                if class_name in filtered_classes:
                    return True
                
                # 更严格地过滤掉Windows设置应用，不管标题是否完整
                if "设置" in title:
                    return True
                
                # 只过滤特定的Chrome_WidgetWin_1窗口（如搜索栏），而不是所有浏览器窗口
                if class_name == "Chrome_WidgetWin_1":
                    # 过滤掉搜索栏等小型Chrome组件窗口
                    if title == "搜索栏" or (width <= 500 and height <= 100):
                        return True
                
                # 检查窗口位置是否在合理范围内
                screen_width = win32api.GetSystemMetrics(0)
                screen_height = win32api.GetSystemMetrics(1)
                
                # 检查窗口是否完全在屏幕外
                if (rect[0] > screen_width or rect[1] > screen_height or 
                    rect[2] < 0 or rect[3] < 0):
                    return True
                
                # 只处理有一定大小的窗口
                if width <= 100 or height <= 100:
                    return True
                
                # 检查窗口标题是否包含Python
                if "Python" in title or "python" in title:
                    return True
                
                # 检查窗口类名
                python_class_names = ["TKTopLevel", "PyQt5", "Qt5QWindowIcon", "wxWindowClassNR", "GLFW30"]
                if any(python_class in class_name for python_class in python_class_names):
                    return True
                
                # 检查窗口样式
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                
                # 检查是否具有透明相关样式
                if (ex_style & win32con.WS_EX_LAYERED or 
                    ex_style & win32con.WS_EX_TRANSPARENT):
                    try:
                        if ex_style & win32con.WS_EX_LAYERED:
                            alpha = win32gui.GetLayeredWindowAttributes(hwnd)[3]
                            if alpha < 255:
                                return True
                    except Exception:
                        return True
                
                # 屏蔽Ralsei相关窗口
                if "Ralsei" in title or "ralsei" in title:
                    return True
                
                # 检查窗口是否具有标题栏和系统菜单
                has_caption = bool(style & win32con.WS_CAPTION)
                has_sysmenu = bool(style & win32con.WS_SYSMENU)
                
                if not has_caption or not has_sysmenu:
                    return True
                
                # 检查是否为子窗口
                parent_hwnd = win32gui.GetParent(hwnd)
                if parent_hwnd != 0:
                    return True
                
                # 进一步过滤小窗口
                if width < 300 or height < 200:
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
windows = test_get_visible_windows_updated()

print(f"\n共检测到 {len(windows)} 个可见窗口：\n")

for i, window in enumerate(windows, 1):
    print(f"窗口 {i}:")
    print(f"  标题: {window['title']}")
    print(f"  类名: {window['class_name']}")
    print(f"  位置: ({window['x']}, {window['y']})")
    print(f"  大小: {window['width']}x{window['height']}")
    print()

# 检查是否有"设置"窗口
settings_windows = [w for w in windows if "设置" in w['title']]
if settings_windows:
    print(f"警告：检测到 {len(settings_windows)} 个包含'设置'的窗口！")
    for window in settings_windows:
        print(f"  - {window['title']}")
else:
    print("✓ 成功：没有检测到包含'设置'的窗口！")

print("\n=== 测试完成 ===")
import win32gui
import win32process
import win32api
import win32con

print("=== 当前可见窗口检测测试 ===")
print("正在检测所有可见窗口...\n")

visible_windows = []

def callback(hwnd, param):
    # 检查窗口是否可见
    if win32gui.IsWindowVisible(hwnd):
        # 获取窗口标题
        title = win32gui.GetWindowText(hwnd)
        
        # 只有有标题的窗口才会被记录
        if title:
            # 获取窗口类名
            class_name = win32gui.GetClassName(hwnd)
            
            # 获取窗口矩形
            rect = win32gui.GetWindowRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            
            # 获取窗口样式
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            
            # 检查是否有标题栏和系统菜单（通常是主窗口）
            has_caption = bool(style & win32con.WS_CAPTION)
            has_sysmenu = bool(style & win32con.WS_SYSMENU)
            
            # 检查是否是透明窗口
            is_layered = bool(ex_style & win32con.WS_EX_LAYERED)
            is_transparent = bool(ex_style & win32con.WS_EX_TRANSPARENT)
            
            # 获取透明度
            alpha = 255
            if is_layered:
                try:
                    alpha = win32gui.GetLayeredWindowAttributes(hwnd)[3]
                except Exception:
                    pass
            
            # 检查是否是子窗口
            parent_hwnd = win32gui.GetParent(hwnd)
            is_child = parent_hwnd != 0
            
            # 窗口信息
            window_info = {
                'hwnd': hwnd,
                'title': title,
                'class_name': class_name,
                'x': rect[0],
                'y': rect[1],
                'width': width,
                'height': height,
                'has_caption': has_caption,
                'has_sysmenu': has_sysmenu,
                'is_layered': is_layered,
                'is_transparent': is_transparent,
                'alpha': alpha,
                'is_child': is_child
            }
            
            visible_windows.append(window_info)
    return True

# 枚举所有窗口
win32gui.EnumWindows(callback, None)

print(f"共检测到 {len(visible_windows)} 个可见窗口\n")

# 打印所有窗口信息
for i, window in enumerate(visible_windows, 1):
    print(f"窗口 {i}:")
    print(f"  标题: {window['title']}")
    print(f"  类名: {window['class_name']}")
    print(f"  句柄: {window['hwnd']}")
    print(f"  位置: ({window['x']}, {window['y']})")
    print(f"  大小: {window['width']}x{window['height']}")
    print(f"  有标题栏: {'是' if window['has_caption'] else '否'}")
    print(f"  有系统菜单: {'是' if window['has_sysmenu'] else '否'}")
    print(f"  分层窗口: {'是' if window['is_layered'] else '否'}")
    print(f"  透明窗口: {'是' if window['is_transparent'] else '否'}")
    print(f"  透明度: {window['alpha']}")
    print(f"  子窗口: {'是' if window['is_child'] else '否'}")
    print()

# 打印过滤后的窗口（模拟当前代码的过滤逻辑）
print("=== 过滤后的窗口（模拟当前代码） ===")
filtered_windows = []

for window in visible_windows:
    # 过滤掉不需要的窗口类
    filtered_classes = [
        "Windows.UI.Core.CoreWindow",
        "ApplicationFrameWindow",
        "WorkerW", 
        "Progman", 
        "Program Manager",
        "Shell_TrayWnd",
        "TrayNotifyWnd",
        "ClockWClass"
    ]
    if window['class_name'] in filtered_classes:
        continue
    
    # 过滤掉Windows设置应用
    if window['title'] == "设置":
        continue
    
    # 只处理有一定大小的窗口
    if window['width'] > 300 and window['height'] > 200:
        # 检查是否为Python窗口
        if "Python" in window['title'] or "python" in window['title']:
            continue
        
        # 检查窗口类名
        python_class_names = ["TKTopLevel", "PyQt5", "Qt5QWindowIcon", "wxWindowClassNR", "GLFW30"]
        if any(python_class in window['class_name'] for python_class in python_class_names):
            continue
        
        # 检查是否具有透明相关样式
        if window['is_layered'] or window['is_transparent']:
            if window['is_layered'] and window['alpha'] < 255:
                continue
        
        # 屏蔽Ralsei相关窗口
        if "Ralsei" in window['title'] or "ralsei" in window['title']:
            continue
        
        # 检查窗口是否具有WS_CAPTION样式
        if not window['has_caption']:
            continue
        
        # 检查窗口是否有WS_SYSMENU样式
        if not window['has_sysmenu']:
            continue
        
        # 检查是否为子窗口
        if window['is_child']:
            continue
        
        # 进一步过滤小窗口
        if window['width'] < 400 or window['height'] < 300:
            continue
        
        filtered_windows.append(window)

print(f"过滤后剩余 {len(filtered_windows)} 个窗口\n")

for i, window in enumerate(filtered_windows, 1):
    print(f"窗口 {i}:")
    print(f"  标题: {window['title']}")
    print(f"  类名: {window['class_name']}")
    print(f"  位置: ({window['x']}, {window['y']})")
    print(f"  大小: {window['width']}x{window['height']}")
    print()
import win32gui
import win32process
import win32api

# 定义回调函数
class WindowInfo:
    def __init__(self):
        self.windows = []

def callback(hwnd, param):
    # 获取窗口标题
    title = win32gui.GetWindowText(hwnd)
    
    # 只关注标题为"设置"的窗口
    if title == "设置":
        # 获取窗口类名
        class_name = win32gui.GetClassName(hwnd)
        
        # 获取窗口矩形
        rect = win32gui.GetWindowRect(hwnd)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        
        # 获取窗口是否可见
        is_visible = win32gui.IsWindowVisible(hwnd)
        is_enabled = win32gui.IsWindowEnabled(hwnd)
        
        # 获取窗口进程ID
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        # 获取进程名称
        process_name = ""
        try:
            handle = win32api.OpenProcess(win32process.PROCESS_QUERY_INFORMATION | win32process.PROCESS_VM_READ, False, pid)
            if handle:
                process_name = win32process.GetModuleFileNameEx(handle, 0)
                process_name = process_name.split('\\')[-1]
                win32api.CloseHandle(handle)
        except Exception as e:
            process_name = f"Error: {e}"
        
        # 检查窗口是否有父窗口
        parent_hwnd = win32gui.GetParent(hwnd)
        has_parent = parent_hwnd != 0
        
        # 保存窗口信息
        param.windows.append({
            'title': title,
            'hwnd': hwnd,
            'class_name': class_name,
            'rect': rect,
            'width': width,
            'height': height,
            'is_visible': is_visible,
            'is_enabled': is_enabled,
            'pid': pid,
            'process_name': process_name,
            'has_parent': has_parent,
            'parent_hwnd': parent_hwnd
        })
    return True

# 创建窗口信息对象
window_info = WindowInfo()

# 枚举所有窗口
win32gui.EnumWindows(callback, window_info)

# 打印检测到的"设置"窗口详情
print(f"检测到 {len(window_info.windows)} 个标题为'设置'的窗口:")
for i, window in enumerate(window_info.windows):
    print(f"\n窗口 {i+1} 详情:")
    print(f"  标题: '{window['title']}'")
    print(f"  HWND: {window['hwnd']}")
    print(f"  类名: {window['class_name']}")
    print(f"  位置: {window['rect']}")
    print(f"  大小: {window['width']}x{window['height']}")
    print(f"  是否可见: {window['is_visible']}")
    print(f"  是否启用: {window['is_enabled']}")
    print(f"  进程ID: {window['pid']}")
    print(f"  进程名称: {window['process_name']}")
    print(f"  有父窗口: {window['has_parent']}")
    if window['has_parent']:
        print(f"  父窗口HWND: {window['parent_hwnd']}")
        # 获取父窗口标题
        parent_title = win32gui.GetWindowText(window['parent_hwnd'])
        print(f"  父窗口标题: '{parent_title}'")

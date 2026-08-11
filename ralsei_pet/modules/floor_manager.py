import win32gui
import win32con
from PyQt5.QtCore import QRect, QPoint

class FloorManager:
    def __init__(self, parent=None):
        self.parent = parent
        self.floors = []  # 存储所有可见楼层
        self.underlying_windows = []  # 存储所有可见窗口，用于生成楼层
        self.desktop_floor = {
            'type': 'desktop',
            'rect': QRect(0, 0, 0, 0),
            'z_order': 0,
            'platform_height': 0
        }  # 桌面楼层，始终存在
        
    def update_floors(self):
        # 更新所有楼层信息
        self._update_underlying_windows()
        self._generate_floors()
        
    def _update_underlying_windows(self):
        # 更新可见窗口列表
        visible_windows = []
        
        def callback(hwnd, param):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    class_name = win32gui.GetClassName(hwnd)
                    rect = win32gui.GetWindowRect(hwnd)
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    
                    # 过滤掉过小的窗口和系统窗口
                    system_classes = [
                        "WorkerW", "Progman", "Program Manager",
                        "Shell_TrayWnd", "TrayNotifyWnd", "ClockWClass"
                    ]
                    
                    if width > 100 and height > 100 and class_name not in system_classes:
                        # 获取窗口z-order
                        # 使用另一种方式获取z-order，因为win32gui没有GetNextWindow函数
                        z_order = 0
                        hwnd_temp = win32gui.GetWindow(hwnd, win32con.GW_HWNDPREV)
                        while hwnd_temp:
                            z_order += 1
                            hwnd_temp = win32gui.GetWindow(hwnd_temp, win32con.GW_HWNDPREV)
                        
                        window_info = {
                            'hwnd': hwnd,
                            'title': title,
                            'class_name': class_name,
                            'rect': QRect(rect[0], rect[1], width, height),
                            'z_order': z_order
                        }
                        visible_windows.append(window_info)
            return True
        
        try:
            win32gui.EnumWindows(callback, None)
            # 按z_order排序，z_order越小，窗口越靠前（越上层）
            visible_windows.sort(key=lambda x: x['z_order'])
            self.underlying_windows = visible_windows
        except Exception as e:
            print(f"获取可见窗口失败: {e}")
    
    def _generate_floors(self):
        # 根据可见窗口生成楼层
        self.floors = []
        
        # 更新桌面楼层大小
        import win32api
        screen_width = win32api.GetSystemMetrics(0)
        screen_height = win32api.GetSystemMetrics(1)
        self.desktop_floor['rect'] = QRect(0, 0, screen_width, screen_height)
        
        # 从上层到下层处理窗口（z_order从小到大）
        # 只保留那些没有被完全覆盖的窗口作为楼层
        for i, window in enumerate(self.underlying_windows):
            # 检查窗口是否被前面的任何窗口完全覆盖
            is_covered = False
            for j in range(i):
                if self.underlying_windows[j]['rect'].contains(window['rect']):
                    is_covered = True
                    break
            
            if not is_covered:
                # 计算平台高度：桌面为0，每层递增5
                # 楼层越高，z_order越小，platform_height越大
                platform_height = (len(self.underlying_windows) - i) * 5
                
                floor = {
                    'type': 'window',
                    'window': window,
                    'rect': window['rect'],
                    'z_order': window['z_order'],
                    'platform_height': platform_height,
                    'window_hwnd': window['hwnd']
                }
                self.floors.append(floor)
        
        # 确保楼层按照平台高度从低到高排序
        self.floors.sort(key=lambda x: x['platform_height'])
    
    def get_current_floor(self, pos):
        # 获取指定位置所在的楼层
        # 从最高楼层（平台高度最大）到最低楼层检查
        # 确保只返回最上层的、能覆盖该位置的楼层
        all_floors = sorted(self.floors + [self.desktop_floor], key=lambda x: x['platform_height'], reverse=True)
        
        for floor in all_floors:
            if floor['rect'].contains(pos):
                return floor
        
        # 默认返回桌面楼层
        return self.desktop_floor
    
    def get_floors_above(self, current_floor):
        # 获取当前楼层以上的所有楼层
        # 楼层越高，platform_height越大
        above_floors = []
        for floor in self.floors:
            if floor['platform_height'] > current_floor['platform_height']:
                above_floors.append(floor)
        return above_floors
    
    def get_drop_destination(self, pos, current_floor):
        # 获取从当前位置掉落时的目标楼层
        # 遵循重力原则：从当前楼层向下查找第一个能接住的楼层
        # 不能穿透任何实心楼板，只能落到下面第一块能接住的楼板上
        
        # 1. 收集所有楼层（包括桌面），按platform_height从高到低排序
        all_floors = sorted(self.floors + [self.desktop_floor], key=lambda x: x['platform_height'], reverse=True)
        
        # 2. 找到当前楼层的位置
        current_index = -1
        for i, floor in enumerate(all_floors):
            if floor == current_floor:
                current_index = i
                break
        
        # 3. 从当前楼层向下查找第一个能接住的楼层
        for i in range(current_index + 1, len(all_floors)):
            floor = all_floors[i]
            # 检查掉落位置是否在该楼层的范围内
            if floor['rect'].contains(pos):
                # 找到了能接住的楼层
                return floor, pos
        
        # 4. 理论上不会到达这里，因为桌面总是能接住
        return self.desktop_floor, pos
    
    def get_jump_destinations(self, current_floor, current_pos):
        # 获取当前位置可以跳跃到的所有目标位置
        # 遵循跳跃规则：
        # 1. 只能往旁边跳（同一楼层内）
        # 2. 只能垂直向上/向下跳
        # 3. 向上跳：只能跳到更高楼层没被挡住的边缘
        # 4. 向下跳：必须逐级跳下，不能直接穿透楼层
        jump_destinations = []
        
        # 1. 同一楼层内的跳跃（可以往旁边跳）
        jump_destinations.append((current_floor, current_pos))
        
        # 2. 向上跳跃到更高楼层
        # 获取所有更高楼层，按platform_height从低到高排序
        above_floors = sorted(self.get_floors_above(current_floor), 
                             key=lambda x: x['platform_height'])
        
        for floor in above_floors:
            rect = floor['rect']
            
            # 视野限制：ralsei只能看到更高楼层没有被完全挡住的边缘
            # 检查当前位置是否在更高楼层的下方，且该楼层在当前位置上方可见
            # 确保楼层没有被其他更高的楼层完全覆盖
            is_visible = True
            for higher_floor in above_floors:
                if higher_floor['platform_height'] > floor['platform_height']:
                    if higher_floor['rect'].contains(rect):
                        is_visible = False
                        break
            
            if is_visible and (current_pos.x() >= rect.left() and 
                current_pos.x() <= rect.right() and
                current_pos.y() >= rect.bottom()):
                # 可以垂直向上跳到这个楼层的顶部边缘
                jump_pos = QPoint(current_pos.x(), rect.top() + 10)
                jump_destinations.append((floor, jump_pos))
        
        # 3. 向下跳跃到较低楼层
        # 获取所有楼层（包括桌面），按platform_height从高到低排序
        all_floors = sorted(self.floors + [self.desktop_floor], 
                          key=lambda x: x['platform_height'], reverse=True)
        
        # 找到当前楼层在排序后的列表中的位置
        current_index = -1
        for i, floor in enumerate(all_floors):
            if floor == current_floor:
                current_index = i
                break
        
        # 只能向下跳到下一个楼层，不能直接穿透
        if current_index + 1 < len(all_floors):
            next_floor = all_floors[current_index + 1]
            # 检查当前位置是否在下层楼层的正上方
            if (current_pos.x() >= next_floor['rect'].left() and 
                current_pos.x() <= next_floor['rect'].right()):
                # 可以垂直向下跳到下层楼层
                jump_pos = QPoint(current_pos.x(), next_floor['rect'].top() + 10)
                jump_destinations.append((next_floor, jump_pos))
        
        return jump_destinations
    
    def is_floor_valid(self, floor):
        # 检查楼层是否仍然有效
        if floor['type'] == 'desktop':
            return True
        
        # 检查窗口是否仍然存在且可见
        for window in self.underlying_windows:
            if window['hwnd'] == floor['window_hwnd']:
                # 检查窗口位置和大小是否变化
                if (window['rect'].left() == floor['rect'].left() and
                    window['rect'].top() == floor['rect'].top() and
                    window['rect'].width() == floor['rect'].width() and
                    window['rect'].height() == floor['rect'].height()):
                    return True
        return False
    
    def get_all_floors(self):
        # 获取所有可见楼层
        return self.floors + [self.desktop_floor]
    
    def get_floor_by_window(self, window_hwnd):
        # 根据窗口句柄获取对应的楼层
        for floor in self.floors:
            if floor['type'] == 'window' and floor['window']['hwnd'] == window_hwnd:
                return floor
        return None
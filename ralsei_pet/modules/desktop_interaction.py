import os
import win32gui
import win32api
import win32con
import win32com.client
import time
import platform
import random
import shutil
import socket
from PyQt5.QtCore import QTimer, QPoint, QRect

# 按需导入psutil，避免启动时的性能开销
try:
    import psutil
except ImportError:
    psutil = None

class DesktopInteraction:
    def __init__(self, parent):
        self.parent = parent
        self.desktop_elements = []
        self.update_timer = QTimer(self.parent)
        self.update_timer.timeout.connect(self.update_desktop_elements)
        self.update_timer.start(1000)  # 每秒更新一次桌面元素
        
        # 桌面路径
        self.desktop_path = os.path.join(os.environ['USERPROFILE'], 'Desktop')
        
        # 隐私应用列表，包含需要保护的应用关键词
        self.privacy_apps = [
            "微信", "WeChat", "WeChat.exe",
            "QQ", "QQ.exe",
            "钉钉", "DingTalk",
            "企业微信", "WXWork",
            "Outlook", "outlook.exe",
            "邮件", "Mail"
        ]
        
        # 普通应用列表，不需要特殊保护
        self.normal_apps = [
            "浏览器", "Chrome", "Firefox", "Edge",
            "记事本", "Notepad",
            "截图工具", "SnippingTool",
            "画图", "mspaint"
        ]
        
        # 用户明确打开的隐私应用列表
        self.user_opened_privacy_apps = []
        
        # 隐私文件类型列表
        self.privacy_file_types = [
            '.txt', '.md', '.py', '.js',
            '.docx', '.pdf', '.xlsx', '.pptx',
            '.jpg', '.png', '.gif'
        ]
        
        # 系统资源监控相关
        self.last_resource_check = 0
        self.resource_check_interval = 5.0  # 每5秒检查一次系统资源
        
        # 电池状态相关
        self.last_battery_check = 0
        self.battery_check_interval = 30.0  # 每30秒检查一次电池状态
        
        # 网络状态相关
        self.last_network_check = 0
        self.network_check_interval = 10.0  # 每10秒检查一次网络状态
        
        # 定时任务相关
        self.scheduled_tasks = []
        self.init_scheduled_tasks()
        
        # 系统信息
        self.system_info = self.get_system_info()
        
        # 存储信息
        self.storage_info = self.get_storage_info()
        
    def init_scheduled_tasks(self):
        # 初始化定时任务
        self.scheduled_tasks = [
            {
                "name": "每日提醒",
                "type": "daily",
                "time": "09:00",
                "action": "提醒用户开始工作",
                "enabled": True
            },
            {
                "name": "休息提醒",
                "type": "interval",
                "interval": 1800,  # 30分钟
                "action": "提醒用户休息",
                "enabled": True
            },
            {
                "name": "晚间提醒",
                "type": "daily",
                "time": "22:00",
                "action": "提醒用户准备休息",
                "enabled": True
            }
        ]
        
    def update_desktop_elements(self):
        # 更新桌面元素列表，包含文件夹和文件
        # 降低桌面元素更新频率，从每秒改为每10秒
        current_time = time.time()
        
        # 桌面元素更新（每10秒一次）
        if not hasattr(self, 'last_desktop_update') or current_time - self.last_desktop_update > 10.0:
            folders = self.get_desktop_folders()
            files = self.get_desktop_files()
            self.desktop_elements = folders + files
            self.last_desktop_update = current_time
        
        # 检查系统资源
        if current_time - self.last_resource_check > self.resource_check_interval:
            self.check_system_resources()
            self.last_resource_check = current_time
        
        # 检查电池状态
        if current_time - self.last_battery_check > self.battery_check_interval:
            self.check_battery_status()
            self.last_battery_check = current_time
        
        # 检查网络状态
        if current_time - self.last_network_check > self.network_check_interval:
            self.check_network_status()
            self.last_network_check = current_time
        
        # 检查定时任务
        self.check_scheduled_tasks()
    
    def get_system_info(self):
        # 获取系统基本信息
        try:
            system_info = {
                "os": platform.system(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "platform": platform.platform(),
                "python_version": platform.python_version()
            }
            
            if psutil:
                system_info["cpu_count"] = psutil.cpu_count(logical=True)
                system_info["total_memory"] = psutil.virtual_memory().total // (1024 * 1024 * 1024)  # GB
            
            return system_info
        except Exception as e:
            print(f"获取系统信息失败: {e}")
            return {}
    
    def get_storage_info(self):
        # 获取存储信息
        try:
            if not psutil:
                return []
                
            storage_info = []
            partitions = psutil.disk_partitions()
            
            for partition in partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    storage_info.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "total": usage.total // (1024 * 1024 * 1024),  # GB
                        "used": usage.used // (1024 * 1024 * 1024),  # GB
                        "free": usage.free // (1024 * 1024 * 1024),  # GB
                        "percent": usage.percent
                    })
                except Exception as e:
                    print(f"获取存储分区信息失败: {e}")
            
            return storage_info
        except Exception as e:
            print(f"获取存储信息失败: {e}")
            return []
    
    def check_system_resources(self):
        # 检查系统资源使用情况
        try:
            if not psutil:
                return {}
            
            # CPU使用率 - 使用0.01秒间隔以提高性能
            cpu_percent = psutil.cpu_percent(interval=0.01)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 磁盘使用率
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # 进程数量（比获取完整PID列表更高效）
            process_count = len(psutil.pids())
            
            resource_info = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "disk_percent": disk_percent,
                "process_count": process_count
            }
            
            # 只在Windows系统上获取负载平均值
            if platform.system() == "Windows":
                try:
                    load_average = [round(load, 2) for load in psutil.getloadavg()]
                    resource_info["load_average"] = load_average
                except Exception:
                    pass
            
            # 发送系统资源通知（仅当超过阈值时）
            if cpu_percent > 90:
                self.parent.emotion_system.react_to_event("system_high_cpu", resource_info)
            if memory_percent > 90:
                self.parent.emotion_system.react_to_event("system_high_memory", resource_info)
            if disk_percent > 90:
                self.parent.emotion_system.react_to_event("system_low_disk", resource_info)
                
            return resource_info
        except Exception as e:
            print(f"检查系统资源失败: {e}")
            return {}
    
    def check_battery_status(self):
        # 检查电池状态
        try:
            if not psutil:
                return {}
            
            battery = psutil.sensors_battery()
            if battery:
                battery_info = {
                    "percent": battery.percent,
                    "secsleft": battery.secsleft,
                    "plugged": battery.power_plugged
                }
                
                # 发送电池状态通知（仅当电池电量低且未充电时）
                if not battery.power_plugged:
                    if battery.percent < 5:
                        self.parent.emotion_system.react_to_event("system_critical_battery", battery_info)
                    elif battery.percent < 20:
                        self.parent.emotion_system.react_to_event("system_low_battery", battery_info)
                    
                return battery_info
            return {}
        except Exception as e:
            print(f"检查电池状态失败: {e}")
            return {}
    
    def check_network_status(self):
        # 检查网络状态
        try:
            net_stats = {}
            
            # 检查网络连接状态（使用更快的DNS查询）
            is_connected = True
            try:
                # 使用本地DNS服务器或更快的公共DNS
                socket.create_connection(("8.8.8.8", 53), timeout=1)
            except socket.error:
                is_connected = False
            
            net_stats["is_connected"] = is_connected
            
            if psutil and is_connected:
                # 仅在网络连接正常时获取详细统计信息
                net_io = psutil.net_io_counters()
                net_stats.update({
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv
                })
            
            # 发送网络状态通知
            if not is_connected:
                self.parent.emotion_system.react_to_event("system_no_network", net_stats)
                
            return net_stats
        except Exception as e:
            print(f"检查网络状态失败: {e}")
            return {}
    
    def check_scheduled_tasks(self):
        # 检查并执行定时任务
        current_time = time.strftime("%H:%M")
        current_seconds = time.time()
        
        for task in self.scheduled_tasks:
            if not task["enabled"]:
                continue
            
            if task["type"] == "daily":
                if task["time"] == current_time:
                    self.execute_scheduled_task(task)
            elif task["type"] == "interval":
                # 简单的间隔任务实现
                # 实际应用中应使用更精确的定时机制
                pass
    
    def execute_scheduled_task(self, task):
        # 执行定时任务
        print(f"执行定时任务: {task['name']} - {task['action']}")
        # 发送任务执行通知
        self.parent.emotion_system.react_to_event("scheduled_task_executed", task)
        # 生成对话
        if task["name"] == "每日提醒":
            self.parent.dialogue_ui.show_dialogue("早上好！新的一天开始了，加油哦！")
        elif task["name"] == "休息提醒":
            self.parent.dialogue_ui.show_dialogue("工作了一段时间，该休息一下啦！")
        elif task["name"] == "晚间提醒":
            self.parent.dialogue_ui.show_dialogue("已经很晚了，早点休息吧，明天又是美好的一天！")
    
    def add_scheduled_task(self, task):
        # 添加新的定时任务
        self.scheduled_tasks.append(task)
        print(f"添加定时任务: {task['name']}")
    
    def remove_scheduled_task(self, task_name):
        # 删除定时任务
        self.scheduled_tasks = [task for task in self.scheduled_tasks if task["name"] != task_name]
        print(f"删除定时任务: {task_name}")
    
    def enable_scheduled_task(self, task_name, enabled=True):
        # 启用或禁用定时任务
        for task in self.scheduled_tasks:
            if task["name"] == task_name:
                task["enabled"] = enabled
                print(f"{'启用' if enabled else '禁用'}定时任务: {task_name}")
                break
    
    def get_scheduled_tasks(self):
        # 获取所有定时任务
        return self.scheduled_tasks
    
    def get_system_resources(self):
        # 获取当前系统资源状态
        return self.check_system_resources()
    
    def get_battery_status(self):
        # 获取当前电池状态
        return self.check_battery_status()
    
    def get_network_status(self):
        # 获取当前网络状态
        return self.check_network_status()
    
    def get_storage_usage(self):
        # 获取存储使用情况
        return self.get_storage_info()
    

    
    def optimize_system(self):
        # 优化系统性能
        try:
            # 关闭不必要的进程
            # 清理临时文件
            # 优化系统设置
            print("系统优化中...")
            self.parent.emotion_system.react_to_event("system_optimized", {})
            return True
        except Exception as e:
            print(f"系统优化失败: {e}")
            return False
    
    def backup_data(self, backup_path=None):
        # 备份数据
        try:
            if not backup_path:
                backup_path = os.path.join(os.environ['USERPROFILE'], 'RalseiBackup')
            
            # 创建备份目录
            os.makedirs(backup_path, exist_ok=True)
            
            # 备份配置文件
            config_path = os.path.join(self.parent.config_manager.config_dir, 'config.json')
            if os.path.exists(config_path):
                import shutil
                shutil.copy(config_path, backup_path)
                print(f"配置文件已备份到: {backup_path}")
                self.parent.emotion_system.react_to_event("data_backup_successful", {"path": backup_path})
                return True
            return False
        except Exception as e:
            print(f"数据备份失败: {e}")
            self.parent.emotion_system.react_to_event("data_backup_failed", {"error": str(e)})
            return False
    
    def restore_data(self, backup_path):
        # 恢复数据
        try:
            import shutil
            # 恢复配置文件
            backup_config = os.path.join(backup_path, 'config.json')
            if os.path.exists(backup_config):
                shutil.copy(backup_config, self.parent.config_manager.config_path)
                print(f"配置文件已从: {backup_path} 恢复")
                self.parent.emotion_system.react_to_event("data_restore_successful", {"path": backup_path})
                return True
            return False
        except Exception as e:
            print(f"数据恢复失败: {e}")
            self.parent.emotion_system.react_to_event("data_restore_failed", {"error": str(e)})
            return False
    
    def clean_temp_files(self):
        # 清理临时文件
        try:
            temp_path = os.environ['TEMP']
            if os.path.exists(temp_path):
                import shutil
                # 清理临时文件
                for filename in os.listdir(temp_path):
                    file_path = os.path.join(temp_path, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        pass
                print("临时文件已清理")
                self.parent.emotion_system.react_to_event("temp_files_cleaned", {})
                return True
            return False
        except Exception as e:
            print(f"清理临时文件失败: {e}")
            self.parent.emotion_system.react_to_event("temp_files_clean_failed", {"error": str(e)})
            return False
        
    def get_desktop_folders(self):
        # 获取桌面文件夹列表，包含真实位置信息
        folders = []
        
        try:
            # 使用Windows Shell API获取桌面文件夹信息
            shell = win32com.client.Dispatch("Shell.Application")
            desktop = shell.NameSpace(self.desktop_path)
            
            for item in desktop.Items():
                if desktop.GetDetailsOf(item, 15) == "文件夹":  # 15表示文件类型
                    # 获取文件夹路径
                    item_path = os.path.join(self.desktop_path, item.Name)
                    
                    # 获取文件夹的详细信息
                    import random
                    # 模拟位置，后续可扩展为真实位置
                    # 这里使用随机位置作为示例，实际可以通过Windows API获取真实位置
                    folder_info = {
                        'name': item.Name,
                        'path': item_path,
                        'type': 'folder',
                        'x': random.randint(50, 1000),  # 模拟桌面X坐标
                        'y': random.randint(50, 600),  # 模拟桌面Y坐标
                        'width': 80,
                        'height': 80,
                        'size': 0,
                        'modified_date': desktop.GetDetailsOf(item, 3),  # 3表示修改日期
                        'weight': random.uniform(0.5, 2.0),  # 增加重量属性（kg）
                        'material': "paper",  # 材质属性
                        'is_open': False,  # 是否打开状态
                        'temperature': random.uniform(18, 25),  # 温度（°C）
                        'texture': "smooth",  # 表面纹理
                        'is_being_dragged': False,  # 是否正在被拖动
                        'drag_force': 0.0,  # 拖动力度
                    }
                    folders.append(folder_info)
        except Exception as e:
            print(f"获取桌面文件夹失败: {e}")
            # 如果API调用失败，回退到简单的文件夹列表
            for item in os.listdir(self.desktop_path):
                item_path = os.path.join(self.desktop_path, item)
                if os.path.isdir(item_path):
                    import random
                    folder_info = {
                        'name': item,
                        'path': item_path,
                        'type': 'folder',
                        'x': random.randint(50, 1000),  # 模拟桌面X坐标
                        'y': random.randint(50, 600),  # 模拟桌面Y坐标
                        'width': 80,
                        'height': 80,
                        'size': 0,
                        'modified_date': '',
                        'weight': random.uniform(0.5, 2.0),  # 重量（kg）
                        'material': "paper",  # 材质属性
                        'is_open': False,  # 是否打开状态
                        'temperature': random.uniform(18, 25),  # 温度（°C）
                        'texture': "smooth",  # 表面纹理
                        'is_being_dragged': False,  # 是否正在被拖动
                        'drag_force': 0.0,  # 拖动力度
                    }
                    folders.append(folder_info)
        
        return folders
        
    def get_desktop_files(self):
        # 获取桌面文件列表，包含真实位置信息
        files = []
        
        try:
            # 使用Windows Shell API获取桌面文件信息
            shell = win32com.client.Dispatch("Shell.Application")
            desktop = shell.NameSpace(self.desktop_path)
            
            for item in desktop.Items():
                if desktop.GetDetailsOf(item, 15) != "文件夹":  # 不是文件夹就是文件
                    # 获取文件路径
                    item_path = os.path.join(self.desktop_path, item.Name)
                    
                    # 获取文件的详细信息
                    import random
                    file_info = {
                        'name': item.Name,
                        'path': item_path,
                        'type': 'file',
                        'x': random.randint(50, 1000),  # 模拟桌面X坐标
                        'y': random.randint(50, 600),  # 模拟桌面Y坐标
                        'width': 80,
                        'height': 80,
                        'size': desktop.GetDetailsOf(item, 1),  # 1表示文件大小
                        'type_desc': desktop.GetDetailsOf(item, 15),  # 15表示文件类型描述
                        'modified_date': desktop.GetDetailsOf(item, 3),  # 3表示修改日期
                        'weight': random.uniform(0.1, 1.5),  # 重量（kg）
                        'material': random.choice(["paper", "plastic", "metal", "wood"]),  # 材质
                        'temperature': random.uniform(15, 28),  # 温度（°C）
                        'hardness': random.uniform(1, 10),  # 硬度（1-10）
                        'transparency': random.uniform(0, 1),  # 透明度（0-1）
                        'is_fragile': random.random() < 0.3,  # 30%概率易碎
                        'texture': random.choice(["smooth", "rough", "glossy", "matte"]),  # 表面纹理
                        'is_being_dragged': False,  # 是否正在被拖动
                        'drag_force': 0.0,  # 拖动力度
                    }
                    files.append(file_info)
        except Exception as e:
            print(f"获取桌面文件失败: {e}")
            # 如果API调用失败，回退到简单的文件列表
            for item in os.listdir(self.desktop_path):
                item_path = os.path.join(self.desktop_path, item)
                if os.path.isfile(item_path):
                    import random
                    file_info = {
                        'name': item,
                        'path': item_path,
                        'type': 'file',
                        'x': random.randint(50, 1000),  # 模拟桌面X坐标
                        'y': random.randint(50, 600),  # 模拟桌面Y坐标
                        'width': 80,
                        'height': 80,
                        'size': os.path.getsize(item_path),
                        'type_desc': os.path.splitext(item)[1],
                        'modified_date': time.ctime(os.path.getmtime(item_path)),
                        'weight': random.uniform(0.1, 1.5),  # 重量（kg）
                        'material': random.choice(["paper", "plastic", "metal", "wood"]),  # 材质
                        'temperature': random.uniform(15, 28),  # 温度（°C）
                        'hardness': random.uniform(1, 10),  # 硬度（1-10）
                        'transparency': random.uniform(0, 1),  # 透明度（0-1）
                        'is_fragile': random.random() < 0.3,  # 30%概率易碎
                        'texture': random.choice(["smooth", "rough", "glossy", "matte"]),  # 表面纹理
                        'is_being_dragged': False,  # 是否正在被拖动
                        'drag_force': 0.0,  # 拖动力度
                    }
                    files.append(file_info)
        
        return files
        
    def open_file(self, file_path):
        # 打开文件，模拟真实用户操作
        try:
            print(f"正在打开文件: {file_path}")
            os.startfile(file_path)
            return True
        except Exception as e:
            print(f"打开文件失败: {e}")
            return False
        
    def open_folder(self, folder_path):
        # 打开文件夹，模拟真实用户操作
        try:
            print(f"正在打开文件夹: {folder_path}")
            os.startfile(folder_path)
            return True
        except Exception as e:
            print(f"打开文件夹失败: {e}")
            return False
        
    def close_window(self, window_title):
        # 关闭窗口，模拟真实用户操作
        try:
            print(f"正在关闭窗口: {window_title}")
            hwnd = win32gui.FindWindow(None, window_title)
            if hwnd:
                # 先激活窗口
                win32gui.SetForegroundWindow(hwnd)
                # 发送关闭消息
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return True
            return False
        except Exception as e:
            print(f"关闭窗口失败: {e}")
            return False
        
    def get_window_rect(self, window_title):
        # 获取窗口位置和大小
        try:
            hwnd = win32gui.FindWindow(None, window_title)
            if hwnd:
                rect = win32gui.GetWindowRect(hwnd)
                return {
                    'x': rect[0],
                    'y': rect[1],
                    'width': rect[2] - rect[0],
                    'height': rect[3] - rect[1],
                }
        except Exception as e:
            print(f"获取窗口位置失败: {e}")
        return None
        
    def get_all_visible_windows(self):
        # 获取所有可见窗口的信息，根据"建楼"要求实现楼层系统
        visible_windows = []
        
        # 预计算屏幕尺寸，避免在回调中重复调用
        screen_width = win32api.GetSystemMetrics(0)
        screen_height = win32api.GetSystemMetrics(1)
        
        # 预编译系统类名集合，提高查询速度
        system_classes = {
            "WorkerW", "Progman", "Program Manager",
            "Shell_TrayWnd", "TrayNotifyWnd", "ClockWClass",
            "Windows.UI.Core.CoreWindow"  # 过滤掉Windows输入体验等系统窗口
        }
        
        # 预编译隐私应用关键词，提高查询速度
        privacy_keywords = set(app.lower() for app in self.privacy_apps)
        
        def callback(hwnd, param):
            # 快速过滤：只处理可见窗口且不是最小化窗口
            if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return True
            
            # 获取窗口标题（快速操作）
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return True
            
            # 快速过滤：屏蔽Ralsei相关窗口，避免检测到自身
            if "Ralsei" in title or "ralsei" in title:
                return True
            
            # 获取窗口类名（快速操作）
            class_name = win32gui.GetClassName(hwnd)
            
            # 快速过滤：系统窗口类
            if class_name in system_classes:
                return True
            
            # 快速过滤：Windows设置应用
            if "设置" in title:
                return True
            
            # 快速过滤：特定系统窗口标题
            if title in ("Windows 输入体验", "wv_1001"):
                return True
            
            # 检查是否是隐私应用（优化：使用集合快速查询）
            title_lower = title.lower()
            class_lower = class_name.lower()
            is_privacy_app = any(keyword in title_lower or keyword in class_lower for keyword in privacy_keywords)
            
            # 如果是隐私应用，且不在用户明确打开的列表中，则跳过
            if is_privacy_app and hwnd not in self.user_opened_privacy_apps:
                return True
            
            # 获取窗口矩形
            rect = win32gui.GetWindowRect(hwnd)
            
            # 计算窗口大小（避免重复计算）
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            
            # 快速过滤：非常小的窗口（可能是系统组件）
            if width <= 100 or height <= 100:
                return True
            
            # 快速过滤：屏幕外的窗口
            if (rect[0] > screen_width or rect[1] > screen_height or 
                rect[2] < 0 or rect[3] < 0):
                return True
            
            # 只检测非透明窗口（优化：减少不必要的系统调用）
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            
            # 完全透明窗口，跳过
            if ex_style & win32con.WS_EX_TRANSPARENT:
                return True
            
            # 分层窗口，检查透明度
            if ex_style & win32con.WS_EX_LAYERED:
                try:
                    # 获取分层窗口属性
                    alpha = win32gui.GetLayeredWindowAttributes(hwnd)[3]
                    if alpha < 255:
                        # 半透明窗口，跳过
                        return True
                except Exception:
                    # 无法获取透明度，跳过
                    return True
            
            # 构建窗口信息（延迟计算Z序，在枚举后统一处理）
            window_info = {
                'hwnd': hwnd,
                'title': title,
                'x': rect[0],
                'y': rect[1],
                'width': width,
                'height': height,
                'center_x': (rect[0] + rect[2]) / 2,
                'center_y': (rect[1] + rect[3]) / 2,
                'is_privacy': is_privacy_app,
                'is_visible': True,
                'rect': rect
            }
            visible_windows.append(window_info)
            return True
        
        try:
            # 枚举所有窗口
            win32gui.EnumWindows(callback, None)
        except Exception as e:
            print(f"获取所有可见窗口失败: {e}")
        
        # 统一计算Z序和平台高度（优化：减少窗口遍历次数）
        if visible_windows:
            # 使用更高效的Z序计算方法
            hwnd_to_index = {}
            hwnd_temp = win32gui.GetTopWindow(None)
            z_order = 0
            
            while hwnd_temp:
                hwnd_to_index[hwnd_temp] = z_order
                # 使用GetWindow代替GetNextWindow，因为win32gui没有GetNextWindow函数
                hwnd_temp = win32gui.GetWindow(hwnd_temp, win32con.GW_HWNDNEXT)
                z_order += 1
            
            # 为每个窗口设置Z序和平台高度
            for window in visible_windows:
                window['z_order'] = hwnd_to_index.get(window['hwnd'], 0)
                # 根据"建楼"要求：桌面Z坐标为0，窗口层级依次增加5
                window['platform_height'] = window['z_order'] * 5
                # 窗口就是实心楼板，不透明原则：窗口就是实心地板，绝不允许穿透、看穿
                window['can_see_below'] = False
        
        # 按Z序排序，Z序越小，窗口越靠前（越上层）
        visible_windows.sort(key=lambda x: x['z_order'])
        
        return visible_windows
        
    def is_mouse_over_desktop_element(self, mouse_pos):
        # 检查鼠标是否在桌面元素上
        for element in self.desktop_elements:
            element_rect = (element['x'], element['y'], element['x'] + element['width'], element['y'] + element['height'])
            if element_rect[0] <= mouse_pos.x() <= element_rect[2] and element_rect[1] <= mouse_pos.y() <= element_rect[3]:
                return element
        return None
    
    def mark_app_as_opened(self, app_name_or_hwnd):
        # 标记应用为用户明确打开的
        # 可以接受应用名称或窗口句柄
        if isinstance(app_name_or_hwnd, int):
            # 是窗口句柄
            hwnd = app_name_or_hwnd
            if hwnd not in self.user_opened_privacy_apps:
                self.user_opened_privacy_apps.append(hwnd)
                # 获取窗口标题用于日志
                title = win32gui.GetWindowText(hwnd)
                print(f"已标记应用为用户打开: {title} (HWND: {hwnd})")
        else:
            # 是应用名称
            app_name = app_name_or_hwnd
            # 查找对应的窗口句柄
            hwnds = []
            
            def enum_callback(hwnd, param):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    class_name = win32gui.GetClassName(hwnd)
                    if app_name.lower() in title.lower() or app_name.lower() in class_name.lower():
                        hwnds.append(hwnd)
                return True
            
            win32gui.EnumWindows(enum_callback, None)
            
            # 标记所有找到的窗口
            for hwnd in hwnds:
                if hwnd not in self.user_opened_privacy_apps:
                    self.user_opened_privacy_apps.append(hwnd)
                    title = win32gui.GetWindowText(hwnd)
                    print(f"已标记应用为用户打开: {title} (HWND: {hwnd})")
    
    def mark_app_as_closed(self, app_name_or_hwnd):
        # 标记应用为已关闭
        if isinstance(app_name_or_hwnd, int):
            # 是窗口句柄
            hwnd = app_name_or_hwnd
            if hwnd in self.user_opened_privacy_apps:
                self.user_opened_privacy_apps.remove(hwnd)
                print(f"已标记应用为已关闭 (HWND: {hwnd})")
        else:
            # 是应用名称
            app_name = app_name_or_hwnd
            # 查找对应的窗口句柄
            hwnds_to_remove = []
            for hwnd in self.user_opened_privacy_apps:
                title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                if app_name.lower() in title.lower() or app_name.lower() in class_name.lower():
                    hwnds_to_remove.append(hwnd)
            
            # 移除所有匹配的窗口
            for hwnd in hwnds_to_remove:
                if hwnd in self.user_opened_privacy_apps:
                    self.user_opened_privacy_apps.remove(hwnd)
                    print(f"已标记应用为已关闭: {win32gui.GetWindowText(hwnd)} (HWND: {hwnd})")
    
    def is_privacy_app(self, window_title_or_file_path):
        # 检查是否是隐私应用或隐私文件
        if isinstance(window_title_or_file_path, str):
            # 检查是否是隐私文件
            if os.path.isfile(window_title_or_file_path):
                ext = os.path.splitext(window_title_or_file_path)[1].lower()
                return ext in self.privacy_file_types
            # 检查是否是隐私应用标题
            return any(app.lower() in window_title_or_file_path.lower() for app in self.privacy_apps)
        return False
    
    def get_privacy_apps(self):
        # 获取隐私应用列表
        return self.privacy_apps.copy()
    
    def get_user_opened_privacy_apps(self):
        # 获取用户明确打开的隐私应用列表
        return self.user_opened_privacy_apps.copy()
        
    def drag_file(self, file_path, target_pos):
        # 拖拽文件到指定位置，模拟真实拖拽操作
        try:
            print(f"正在拖拽文件: {file_path} 到位置: {target_pos}")
            
            # 获取当前文件目录和目标目录
            current_dir = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            
            # 模拟真实拖拽延迟
            time.sleep(0.5)
            
            # 检查目标位置是否是文件夹
            target_folder = self._get_folder_at_pos(target_pos)
            if target_folder:
                # 拖拽到文件夹中
                new_path = os.path.join(target_folder['path'], filename)
                action = "到文件夹中"
            else:
                # 拖拽到桌面新位置（简化为重命名）
                new_filename = f"moved_{filename}"
                new_path = os.path.join(current_dir, new_filename)
                action = "到新位置"
            
            # 如果文件已存在，添加时间戳
            if os.path.exists(new_path):
                timestamp = int(time.time())
                base_name, ext = os.path.splitext(filename)
                new_filename = f"moved_{timestamp}_{base_name}{ext}"
                if target_folder:
                    new_path = os.path.join(target_folder['path'], new_filename)
                else:
                    new_path = os.path.join(current_dir, new_filename)
            
            # 执行文件移动
            os.rename(file_path, new_path)
            print(f"文件拖拽成功{action}，新路径: {new_path}")
            return True
        except Exception as e:
            print(f"拖拽文件失败: {e}")
            return False
    
    def _get_folder_at_pos(self, pos):
        # 获取指定位置的文件夹
        for element in self.desktop_elements:
            if element['type'] == 'folder':
                element_rect = (element['x'], element['y'], element['x'] + element['width'], element['y'] + element['height'])
                if element_rect[0] <= pos.x() <= element_rect[2] and element_rect[1] <= pos.y() <= element_rect[3]:
                    return element
        return None
    
    def rename_file(self, file_path, new_name):
        # 重命名文件，模拟真实用户操作
        try:
            print(f"正在重命名文件: {file_path} 为: {new_name}")
            
            # 获取当前文件目录
            current_dir = os.path.dirname(file_path)
            
            # 模拟真实重命名延迟
            time.sleep(0.3)
            
            # 构建新路径
            new_path = os.path.join(current_dir, new_name)
            
            # 检查新文件名是否有效
            if not self._is_valid_filename(new_name):
                print(f"无效的文件名: {new_name}")
                return False
            
            # 如果文件已存在，添加时间戳
            if os.path.exists(new_path):
                timestamp = int(time.time())
                base_name, ext = os.path.splitext(new_name)
                new_name = f"{base_name}_{timestamp}{ext}"
                new_path = os.path.join(current_dir, new_name)
            
            # 执行重命名
            os.rename(file_path, new_path)
            print(f"文件重命名成功，新路径: {new_path}")
            return True
        except Exception as e:
            print(f"重命名文件失败: {e}")
            return False
    
    def _is_valid_filename(self, filename):
        # 检查文件名是否有效
        invalid_chars = '<>:"/\\|?*'
        if any(char in filename for char in invalid_chars):
            return False
        if filename in ['.', '..']:
            return False
        return True
    
    def delete_file(self, file_path, confirm=True, send_to_recycle=True, show_animation=True):
        # 删除文件，模拟真实用户操作，支持回收站和动画效果
        try:
            print(f"正在删除文件: {file_path}")
            
            # 模拟真实删除操作流程，更符合真实操作
            time.sleep(0.5)
            
            if confirm:
                # 模拟确认对话框，更智能的确认逻辑
                filename = os.path.basename(file_path)
                print(f"确认删除文件 '{filename}' 吗？ (模拟确认对话框)")
                print(f"此操作将{'将文件移至回收站' if send_to_recycle else '永久删除文件'}")
                time.sleep(0.4)
            
            if send_to_recycle:
                # 移至回收站，使用Windows API
                try:
                    import win32com.shell.shell as shell
                    shell.SHFileOperation((0, shell.FO_DELETE, file_path, None, 
                                          shell.FOF_ALLOWUNDO | shell.FOF_NOCONFIRMATION,
                                          None, None))
                    print(f"文件 '{os.path.basename(file_path)}' 已移至回收站")
                except Exception as e:
                    print(f"移至回收站失败，将尝试永久删除: {e}")
                    # 回退到永久删除
                    os.remove(file_path)
                    print(f"文件 '{os.path.basename(file_path)}' 已永久删除")
            else:
                # 执行永久删除操作
                os.remove(file_path)
                print(f"文件 '{os.path.basename(file_path)}' 已永久删除")
            
            # 模拟删除动画效果
            if show_animation:
                time.sleep(0.3)
            
            return True
        except Exception as e:
            print(f"删除文件失败: {e}")
            return False
    
    def create_folder(self, folder_name, target_path=None, suggest_name=False):
        # 在指定位置创建新文件夹，模拟真实用户操作，支持智能名称推荐
        try:
            # 智能名称推荐
            if suggest_name:
                # 根据当前时间和内容推荐名称
                current_time = time.strftime("%Y%m%d_%H%M%S")
                suggested_names = [
                    f"新建文件夹_{current_time}",
                    f"我的文件夹_{current_time}",
                    f"资料夹_{current_time}",
                    f"工作_{current_time}",
                    f"文档_{current_time}"
                ]
                folder_name = random.choice(suggested_names)
            
            print(f"正在创建文件夹: {folder_name}")
            
            # 模拟真实创建延迟，更符合真实操作
            time.sleep(0.8)
            
            # 检查文件夹名是否有效
            if not self._is_valid_filename(folder_name):
                print(f"无效的文件夹名: {folder_name}")
                return False
            
            # 确定目标路径
            if target_path and os.path.isdir(target_path):
                folder_path = os.path.join(target_path, folder_name)
            else:
                folder_path = os.path.join(self.desktop_path, folder_name)
            
            # 如果文件夹已存在，添加更智能的后缀
            if os.path.exists(folder_path):
                # 尝试添加序号而不是时间戳，更友好
                counter = 1
                base_name = folder_name
                while os.path.exists(folder_path):
                    folder_name = f"{base_name}_{counter}"
                    folder_path = os.path.join(os.path.dirname(folder_path), folder_name)
                    counter += 1
            
            # 执行创建操作
            os.makedirs(folder_path, exist_ok=True)
            print(f"文件夹创建成功，路径: {folder_path}")
            
            # 模拟文件夹创建后的选择和重命名状态
            time.sleep(0.5)
            return folder_path
        except Exception as e:
            print(f"创建文件夹失败: {e}")
            return False
    
    def copy_file(self, source_path, target_dir, auto_organize=False, preserve_metadata=True):
        # 复制文件到目标目录，模拟真实复制操作，支持自动分类和元数据保留
        try:
            print(f"正在复制文件: {source_path} 到: {target_dir}")
            
            # 自动分类功能
            if auto_organize:
                # 根据文件类型自动分类
                file_ext = os.path.splitext(source_path)[1].lower()
                if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    target_dir = os.path.join(target_dir, '图片')
                elif file_ext in ['.txt', '.md', '.doc', '.docx', '.pdf']:
                    target_dir = os.path.join(target_dir, '文档')
                elif file_ext in ['.mp3', '.wav', '.flac', '.m4a']:
                    target_dir = os.path.join(target_dir, '音频')
                elif file_ext in ['.mp4', '.avi', '.mkv', '.mov']:
                    target_dir = os.path.join(target_dir, '视频')
                elif file_ext in ['.py', '.js', '.java', '.cpp', '.c']:
                    target_dir = os.path.join(target_dir, '代码')
                elif file_ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
                    target_dir = os.path.join(target_dir, '压缩文件')
                
                # 确保分类目录存在
                os.makedirs(target_dir, exist_ok=True)
            
            # 模拟真实复制延迟，根据文件大小调整
            try:
                file_size = os.path.getsize(source_path) / (1024 * 1024)  # MB
                # 小文件快速复制，大文件有更长延迟
                delay = min(1.5, max(0.5, file_size * 0.1))
                time.sleep(delay)
            except Exception:
                time.sleep(0.8)
            
            import shutil
            filename = os.path.basename(source_path)
            target_path = os.path.join(target_dir, filename)
            
            # 如果目标文件已存在，添加智能后缀
            if os.path.exists(target_path):
                base_name, ext = os.path.splitext(filename)
                # 先尝试简单的副本标记
                target_path = os.path.join(target_dir, f"{base_name} - 副本{ext}")
                # 如果副本也存在，添加序号
                if os.path.exists(target_path):
                    counter = 1
                    while os.path.exists(target_path):
                        target_path = os.path.join(target_dir, f"{base_name} - 副本{counter}{ext}")
                        counter += 1
            
            # 执行复制操作，保留元数据
            if preserve_metadata:
                shutil.copy2(source_path, target_path)  # 保留元数据
            else:
                shutil.copy(source_path, target_path)   # 只复制内容
            
            print(f"文件复制成功，新路径: {target_path}")
            return True
        except Exception as e:
            print(f"复制文件失败: {e}")
            return False
    
    def cut_file(self, source_path, target_dir, auto_organize=False, preserve_metadata=True, show_progress=False):
        # 剪切文件到目标目录，模拟真实剪切操作，支持自动分类和元数据保留
        try:
            print(f"正在剪切文件: {source_path} 到: {target_dir}")
            
            # 自动分类功能
            if auto_organize:
                # 根据文件类型自动分类
                file_ext = os.path.splitext(source_path)[1].lower()
                if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    target_dir = os.path.join(target_dir, '图片')
                elif file_ext in ['.txt', '.md', '.doc', '.docx', '.pdf']:
                    target_dir = os.path.join(target_dir, '文档')
                elif file_ext in ['.mp3', '.wav', '.flac', '.m4a']:
                    target_dir = os.path.join(target_dir, '音频')
                elif file_ext in ['.mp4', '.avi', '.mkv', '.mov']:
                    target_dir = os.path.join(target_dir, '视频')
                elif file_ext in ['.py', '.js', '.java', '.cpp', '.c']:
                    target_dir = os.path.join(target_dir, '代码')
                elif file_ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
                    target_dir = os.path.join(target_dir, '压缩文件')
                
                # 确保分类目录存在
                os.makedirs(target_dir, exist_ok=True)
            
            # 显示剪切进度
            if show_progress:
                print("正在准备剪切文件...")
            
            # 模拟真实剪切延迟，根据文件大小调整
            try:
                file_size = os.path.getsize(source_path) / (1024 * 1024)  # MB
                # 小文件快速剪切，大文件有更长延迟
                delay = min(1.2, max(0.4, file_size * 0.08))
                time.sleep(delay)
            except Exception:
                time.sleep(0.5)
            
            import shutil
            filename = os.path.basename(source_path)
            target_path = os.path.join(target_dir, filename)
            
            # 如果目标文件已存在，添加智能后缀
            if os.path.exists(target_path):
                base_name, ext = os.path.splitext(filename)
                # 先尝试简单的剪切标记
                target_path = os.path.join(target_dir, f"{base_name} - 剪切{ext}")
                # 如果剪切标记也存在，添加序号
                if os.path.exists(target_path):
                    counter = 1
                    while os.path.exists(target_path):
                        target_path = os.path.join(target_dir, f"{base_name} - 剪切{counter}{ext}")
                        counter += 1
            
            # 执行剪切操作（先复制再删除）
            if preserve_metadata:
                shutil.copy2(source_path, target_path)  # 保留元数据
            else:
                shutil.copy(source_path, target_path)   # 只复制内容
            
            # 显示进度
            if show_progress:
                print("正在删除源文件...")
                time.sleep(0.2)
            
            os.remove(source_path)
            
            print(f"文件剪切成功，新路径: {target_path}")
            return target_path
        except Exception as e:
            print(f"剪切文件失败: {e}")
            return False
    
    def double_click_file(self, file_path):
        # 双击打开文件，模拟真实用户双击操作
        try:
            print(f"正在双击打开文件: {file_path}")
            
            # 模拟真实双击延迟
            time.sleep(0.2)
            
            # 执行打开操作
            os.startfile(file_path)
            print(f"文件打开成功: {file_path}")
            return True
        except Exception as e:
            print(f"打开文件失败: {e}")
            return False
    
    def right_click_file(self, file_path):
        # 右键点击文件，显示上下文菜单，模拟真实右键操作
        try:
            print(f"正在右键点击文件: {file_path}")
            
            # 模拟真实右键延迟
            time.sleep(0.1)
            
            # 显示模拟的右键菜单选项
            print(f"文件右键菜单: {file_path}")
            print("  1. 打开")
            print("  2. 打开方式")
            print("  3. 发送到")
            print("  4. 复制")
            print("  5. 剪切")
            print("  6. 重命名")
            print("  7. 删除")
            print("  8. 属性")
            return True
        except Exception as e:
            print(f"右键点击文件失败: {e}")
            return False
    
    def is_deltarune_related(self, file_path):
        # 检查文件是否与Deltarune或Undertale相关
        try:
            # 获取文件名和扩展名
            file_name = os.path.basename(file_path).lower()
            
            # 相关关键词列表
            related_keywords = [
                "deltarune", "undertale", "ralsei", "kris", "susie", "noelle", 
                "sans", "papyrus", "toriel", "asriel", "flowey", "chara", 
                "undyne", "alphys", "mettaton", "napstablook", "temmie", 
                "frisk", "asgore", "monster kid", "burgerpants", "nice cream guy"
            ]
            
            # 检查文件名是否包含相关关键词
            for keyword in related_keywords:
                if keyword in file_name:
                    return True
            
            # 检查文件扩展名是否为相关类型
            related_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.txt', '.md', '.py', '.js', '.json']
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # 如果是图片或文本文件，可能包含相关内容
            if file_ext in related_extensions:
                try:
                    # 对于文本文件，尝试读取内容检查
                    if file_ext in ['.txt', '.md', '.py', '.js', '.json']:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(1000)  # 只读取前1000个字符，避免读取大文件
                            content_lower = content.lower()
                            for keyword in related_keywords:
                                if keyword in content_lower:
                                    return True
                except Exception:
                    # 无法读取文件内容，返回False
                    pass
            
            return False
        except Exception as e:
            print(f"检查文件是否与Deltarune相关失败: {e}")
            return False
    
    def get_interesting_files(self):
        # 获取所有有趣的文件（与Deltarune或Undertale相关）
        interesting_files = []
        
        # 获取桌面文件
        desktop_files = self.get_desktop_files()
        
        # 过滤出有趣的文件
        for file in desktop_files:
            if self.is_deltarune_related(file['path']):
                interesting_files.append(file)
        
        return interesting_files
    
    # PPT操控功能
    def ppt_control(self, action, ppt_path=None):
        # 控制PowerPoint演示文稿
        try:
            print(f"正在执行PPT操作: {action}")
            
            # 根据文件路径打开PPT
            if ppt_path:
                if not os.path.exists(ppt_path):
                    print(f"PPT文件不存在: {ppt_path}")
                    return False
                
                # 启动PowerPoint
                import win32com.client
                powerpoint = win32com.client.Dispatch("PowerPoint.Application")
                powerpoint.Visible = True
                
                # 打开演示文稿
                presentation = powerpoint.Presentations.Open(ppt_path)
                
                # 执行操作
                result = self._execute_ppt_action(presentation, action)
                
                # 保存并关闭（如果需要）
                if action in ["save", "save_as"]:
                    presentation.Save()
                if action == "close":
                    presentation.Close()
                    powerpoint.Quit()
                
                return result
            else:
                print("请提供PPT文件路径")
                return False
        except Exception as e:
            print(f"PPT操作失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _execute_ppt_action(self, presentation, action):
        # 执行具体的PPT操作
        try:
            if action == "start_slideshow":
                # 开始放映幻灯片
                presentation.SlideShowSettings.Run()
                print("PPT放映已开始")
                return True
            elif action == "next_slide":
                # 切换到下一张幻灯片
                if hasattr(presentation, 'SlideShowWindow') and presentation.SlideShowWindow.View is not None:
                    presentation.SlideShowWindow.View.Next()
                    print("切换到下一张幻灯片")
                    return True
                else:
                    print("当前没有正在放映的幻灯片")
                    return False
            elif action == "previous_slide":
                # 切换到上一张幻灯片
                if hasattr(presentation, 'SlideShowWindow') and presentation.SlideShowWindow.View is not None:
                    presentation.SlideShowWindow.View.Previous()
                    print("切换到上一张幻灯片")
                    return True
                else:
                    print("当前没有正在放映的幻灯片")
                    return False
            elif action == "stop_slideshow":
                # 停止放映幻灯片
                if hasattr(presentation, 'SlideShowWindow'):
                    presentation.SlideShowWindow.View.Exit()
                    print("PPT放映已停止")
                    return True
                else:
                    print("当前没有正在放映的幻灯片")
                    return False
            elif action == "save":
                # 保存演示文稿
                presentation.Save()
                print("PPT已保存")
                return True
            elif action == "close":
                # 关闭演示文稿
                presentation.Close()
                print("PPT已关闭")
                return True
            elif action == "add_slide":
                # 添加新幻灯片
                slide_layout = presentation.SlideMaster.CustomLayouts(1)  # 使用第一个布局
                presentation.Slides.AddSlide(presentation.Slides.Count + 1, slide_layout)
                print("已添加新幻灯片")
                return True
            elif action == "delete_slide":
                # 删除当前幻灯片
                if presentation.Slides.Count > 0:
                    presentation.Slides(presentation.Slides.Count).Delete()
                    print("已删除最后一张幻灯片")
                    return True
                else:
                    print("没有幻灯片可以删除")
                    return False
            elif action == "go_to_slide":
                # 跳转到指定幻灯片
                # 注意：此操作需要在幻灯片放映模式下执行
                if hasattr(presentation, 'SlideShowWindow') and presentation.SlideShowWindow.View is not None:
                    # 默认跳转到第3张幻灯片，可以根据需要修改
                    slide_index = 3
                    if slide_index <= presentation.Slides.Count:
                        presentation.SlideShowWindow.View.GotoSlide(slide_index)
                        print(f"已跳转到幻灯片 {slide_index}")
                        return True
                    else:
                        print(f"幻灯片 {slide_index} 不存在")
                        return False
                else:
                    print("当前没有正在放映的幻灯片")
                    return False
            elif action == "set_slide_time":
                # 设置幻灯片自动切换时间
                for slide in presentation.Slides:
                    slide.SlideShowTransition.AdvanceOnTime = True
                    slide.SlideShowTransition.AdvanceTime = 5  # 5秒自动切换
                print("已设置幻灯片自动切换时间为5秒")
                return True
            elif action == "export_as_pdf":
                # 导出为PDF
                pdf_path = os.path.splitext(presentation.FullName)[0] + ".pdf"
                presentation.ExportAsFixedFormat(pdf_path, 2)  # 2表示PDF格式
                print(f"已将PPT导出为PDF: {pdf_path}")
                return True
            else:
                print(f"不支持的PPT操作: {action}")
                return False
        except Exception as e:
            print(f"执行PPT操作失败: {e}")
            return False
    
    # 表格编辑辅助功能
    def excel_control(self, action, excel_path=None, sheet_name=None, cell_range=None, data=None):
        # 控制Excel表格
        try:
            print(f"正在执行Excel操作: {action}")
            
            if not excel_path:
                print("请提供Excel文件路径")
                return False
            
            if not os.path.exists(excel_path):
                print(f"Excel文件不存在: {excel_path}")
                return False
            
            # 启动Excel
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = True
            
            # 打开工作簿
            workbook = excel.Workbooks.Open(excel_path)
            
            # 执行操作
            result = self._execute_excel_action(workbook, action, sheet_name, cell_range, data)
            
            # 保存并关闭
            if action in ["save", "write_data", "add_sheet", "delete_sheet"]:
                workbook.Save()
            if action == "close":
                workbook.Close()
                excel.Quit()
            
            return result
        except Exception as e:
            print(f"Excel操作失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _execute_excel_action(self, workbook, action, sheet_name=None, cell_range=None, data=None):
        # 执行具体的Excel操作
        try:
            # 获取工作表
            if sheet_name:
                if sheet_name in [sheet.Name for sheet in workbook.Sheets]:
                    sheet = workbook.Sheets(sheet_name)
                else:
                    print(f"工作表不存在: {sheet_name}")
                    return False
            else:
                sheet = workbook.ActiveSheet
            
            if action == "read_data":
                # 读取单元格数据
                if not cell_range:
                    print("请提供单元格范围")
                    return False
                
                range_obj = sheet.Range(cell_range)
                data = range_obj.Value
                print(f"读取到数据: {data}")
                return data
            elif action == "write_data":
                # 写入数据到单元格
                if not cell_range or data is None:
                    print("请提供单元格范围和数据")
                    return False
                
                sheet.Range(cell_range).Value = data
                print(f"已将数据写入单元格: {cell_range}")
                return True
            elif action == "add_sheet":
                # 添加新工作表
                if sheet_name:
                    workbook.Sheets.Add().Name = sheet_name
                    print(f"已添加工作表: {sheet_name}")
                    return True
                else:
                    new_sheet = workbook.Sheets.Add()
                    print(f"已添加新工作表: {new_sheet.Name}")
                    return True
            elif action == "delete_sheet":
                # 删除工作表
                if sheet_name and sheet_name in [s.Name for s in workbook.Sheets]:
                    workbook.Sheets(sheet_name).Delete()
                    print(f"已删除工作表: {sheet_name}")
                    return True
                else:
                    print("请提供有效的工作表名称")
                    return False
            elif action == "auto_fit":
                # 自动调整列宽
                sheet.Cells.EntireColumn.AutoFit()
                print("已自动调整列宽")
                return True
            elif action == "save":
                # 保存工作簿
                workbook.Save()
                print("Excel已保存")
                return True
            elif action == "close":
                # 关闭工作簿
                workbook.Close()
                print("Excel已关闭")
                return True
            elif action == "sum_range":
                # 计算范围总和
                if not cell_range:
                    print("请提供单元格范围")
                    return False
                
                result = sheet.Evaluate(f"SUM({cell_range})")
                print(f"范围 {cell_range} 的总和为: {result}")
                return result
            elif action == "average_range":
                # 计算范围平均值
                if not cell_range:
                    print("请提供单元格范围")
                    return False
                
                result = sheet.Evaluate(f"AVERAGE({cell_range})")
                print(f"范围 {cell_range} 的平均值为: {result}")
                return result
            elif action == "max_range":
                # 计算范围最大值
                if not cell_range:
                    print("请提供单元格范围")
                    return False
                
                result = sheet.Evaluate(f"MAX({cell_range})")
                print(f"范围 {cell_range} 的最大值为: {result}")
                return result
            elif action == "min_range":
                # 计算范围最小值
                if not cell_range:
                    print("请提供单元格范围")
                    return False
                
                result = sheet.Evaluate(f"MIN({cell_range})")
                print(f"范围 {cell_range} 的最小值为: {result}")
                return result
            elif action == "sort_data":
                # 排序数据
                if not cell_range:
                    print("请提供单元格范围")
                    return False
                
                # 默认按第一列升序排序
                range_obj = sheet.Range(cell_range)
                range_obj.Sort(Key1=range_obj.Columns(1), Order1=1)  # Order1=1表示升序
                print(f"已对范围 {cell_range} 按第一列升序排序")
                return True
            elif action == "filter_data":
                # 筛选数据
                if not cell_range:
                    print("请提供单元格范围")
                    return False
                
                sheet.Range(cell_range).AutoFilter()
                print(f"已为范围 {cell_range} 添加筛选器")
                return True
            elif action == "create_chart":
                # 创建图表
                if not cell_range:
                    print("请提供单元格范围")
                    return False
                
                # 获取当前工作表
                chart = workbook.Charts.Add()
                chart.SetSourceData(Source=sheet.Range(cell_range))
                chart.ChartType = -4100  # 柱状图
                chart.Location(Where=1, Name=sheet.Name)  # 嵌入当前工作表
                print(f"已在工作表 {sheet.Name} 中创建柱状图")
                return True
            elif action == "merge_cells":
                # 合并单元格
                if not cell_range:
                    print("请提供单元格范围")
                    return False
                
                sheet.Range(cell_range).Merge()
                print(f"已合并单元格: {cell_range}")
                return True
            elif action == "unmerge_cells":
                # 取消合并单元格
                if not cell_range:
                    print("请提供单元格范围")
                    return False
                
                sheet.Range(cell_range).UnMerge()
                print(f"已取消合并单元格: {cell_range}")
                return True
            elif action == "set_cell_color":
                # 设置单元格颜色
                if not cell_range:
                    print("请提供单元格范围")
                    return False
                
                # 默认设置为浅黄色
                sheet.Range(cell_range).Interior.ColorIndex = 36
                print(f"已设置单元格 {cell_range} 颜色为浅黄色")
                return True
            elif action == "clear_format":
                # 清除单元格格式
                if not cell_range:
                    print("请提供单元格范围")
                    return False
                
                sheet.Range(cell_range).ClearFormats()
                print(f"已清除单元格 {cell_range} 的格式")
                return True
            elif action == "export_as_pdf":
                # 导出为PDF
                pdf_path = os.path.splitext(workbook.FullName)[0] + ".pdf"
                sheet.ExportAsFixedFormat(0, pdf_path)  # 0表示PDF格式
                print(f"已将工作表 {sheet.Name} 导出为PDF: {pdf_path}")
                return True
            else:
                print(f"不支持的Excel操作: {action}")
                return False
        except Exception as e:
            print(f"执行Excel操作失败: {e}")
            return False
        
    def get_file_content_preview(self, file_path, max_lines=5, allow_privacy=False):
        # 获取文件内容预览，支持文本文件
        # 添加隐私文件保护机制
        try:
            # 检查是否是隐私文件
            ext = os.path.splitext(file_path)[1].lower()
            is_privacy_file = ext in self.privacy_file_types
            
            if is_privacy_file and not allow_privacy:
                return f"这是隐私文件，无法预览: {os.path.basename(file_path)}"
            
            if file_path.endswith('.txt') or file_path.endswith('.py') or file_path.endswith('.md'):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    preview = ''.join(lines[:max_lines])
                    if len(lines) > max_lines:
                        preview += f"\n... (共 {len(lines)} 行，显示前 {max_lines} 行)"
                    return preview
            else:
                return f"无法预览此文件类型: {os.path.splitext(file_path)[1]}"
        except Exception as e:
            print(f"获取文件预览失败: {e}")
            return f"预览失败: {str(e)}"
        
    def is_element_nearby(self, element_pos, check_pos, max_distance=100):
        # 检查元素是否在指定位置附近
        dx = abs(element_pos.x() - check_pos.x())
        dy = abs(element_pos.y() - check_pos.y())
        return (dx**2 + dy**2)**0.5 <= max_distance
        
    def get_nearby_elements(self, pos, max_distance=100):
        # 获取指定位置附近的桌面元素，包括窗口和桌面图标
        nearby_elements = []
        
        # 1. 检测附近的窗口元素
        visible_windows = self.get_all_visible_windows()
        for window in visible_windows:
            # 将浮点数转换为整数，QPoint只接受整数参数
            window_center = QPoint(int(window['center_x']), int(window['center_y']))
            distance = ((window_center.x() - pos.x()) ** 2 + (window_center.y() - pos.y()) ** 2) ** 0.5
            if distance <= max_distance:
                # 转换为统一的元素格式
                window_element = {
                    'name': window['title'],
                    'type': 'window',
                    'rect': QRect(window['x'], window['y'], window['width'], window['height']),
                    'distance': distance,
                    'window_info': window
                }
                nearby_elements.append(window_element)
        
        # 2. 检测附近的桌面图标（文件和文件夹）
        for element in self.desktop_elements:
            element_center = QPoint(element['x'] + element['width'] // 2, element['y'] + element['height'] // 2)
            distance = ((element_center.x() - pos.x()) ** 2 + (element_center.y() - pos.y()) ** 2) ** 0.5
            if distance <= max_distance:
                # 转换为统一的元素格式
                desktop_element = {
                    'name': element['name'],
                    'type': element['type'],
                    'rect': QRect(element['x'], element['y'], element['width'], element['height']),
                    'distance': distance,
                    'path': element['path'],
                    'desktop_info': element
                }
                nearby_elements.append(desktop_element)
        
        # 按距离排序，最近的元素排在前面
        nearby_elements.sort(key=lambda x: x['distance'])
        
        return nearby_elements
        
    def identify_file_type(self, file_path):
        # 识别文件类型，用于智能响应
        ext = os.path.splitext(file_path)[1].lower()
        
        file_types = {
            '.txt': '文本文件',
            '.py': 'Python代码文件',
            '.md': 'Markdown文档',
            '.pdf': 'PDF文档',
            '.docx': 'Word文档',
            '.xlsx': 'Excel表格',
            '.pptx': 'PowerPoint演示文稿',
            '.jpg': '图片文件',
            '.png': '图片文件',
            '.gif': '动画图片',
            '.mp4': '视频文件',
            '.mp3': '音频文件',
            '.exe': '可执行文件',
            '.zip': '压缩文件',
        }
        
        return file_types.get(ext, '未知文件类型')
        
    def get_special_file_reaction(self, file_path):
        # 获取对特殊文件的反应
        file_name = os.path.basename(file_path).lower()
        file_type = self.identify_file_type(file_path)
        
        # 检查是否与Deltarune或Undertale相关
        if 'deltarune' in file_name or 'undertale' in file_name or 'ralsei' in file_name:
            return {
                'emotion': 'excited',
                'dialogue': f"哇！这是关于{file_type}！我很感兴趣呢！",
                'action': 'surprised'
            }
        
        # 检查是否是浏览器相关文件
        if 'browser' in file_name or 'chrome' in file_name or 'firefox' in file_name or 'edge' in file_name:
            return {
                'emotion': 'excited',
                'dialogue': f"浏览器！我可以用它来浏览网页吗？",
                'action': 'wave'
            }
        
        # 检查是否是代码文件
        if file_type == 'Python代码文件' or file_name.endswith('.py'):
            # 检查是否是关于Ralsei的代码
            if 'ralsei' in file_name:
                return {
                    'emotion': 'sad',
                    'dialogue': f"这是关于我的代码吗？看起来好复杂... 我有点看不懂...",
                    'action': 'cry'
                }
            else:
                return {
                    'emotion': 'curious',
                    'dialogue': f"这是{file_type}呢！代码看起来好有趣！",
                    'action': 'look_up'
                }
        
        # 检查是否是图片文件
        if file_type == '图片文件':
            if 'cake' in file_name or 'food' in file_name:
                return {
                    'emotion': 'happy',
                    'dialogue': f"哇！这是{file_type}，看起来很好吃的样子！",
                    'action': 'laugh'
                }
            else:
                return {
                    'emotion': 'curious',
                    'dialogue': f"这是{file_type}呢！看起来很有趣！",
                    'action': 'look_up'
                }
        
        # 默认反应
        return {
            'emotion': 'normal',
            'dialogue': f"这是{file_type}呢！",
            'action': 'idle'
        }
    
    def open_browser(self, url="https://www.google.com", new_window=False, position=None, size=None):
        # 打开浏览器并访问指定URL
        try:
            print(f"正在打开浏览器访问: {url}")
            import webbrowser
            
            if new_window:
                # 打开新窗口
                webbrowser.open(url, new=1)
            else:
                # 在当前窗口打开新标签页
                webbrowser.open(url, new=0)
            
            return True
        except Exception as e:
            print(f"打开浏览器失败: {e}")
            return False
    
    def move_window_smoothly(self, window_title, target_x, target_y, duration=1.0):
        # 平滑移动窗口到指定位置
        try:
            hwnd = win32gui.FindWindow(None, window_title)
            if not hwnd:
                return False
            
            # 获取当前窗口位置
            current_rect = win32gui.GetWindowRect(hwnd)
            current_x, current_y = current_rect[0], current_rect[1]
            
            # 计算移动距离
            dx = target_x - current_x
            dy = target_y - current_y
            
            # 计算步数和每步移动距离
            steps = 50
            step_duration = duration / steps
            step_dx = dx / steps
            step_dy = dy / steps
            
            # 执行平滑移动
            for i in range(steps):
                new_x = int(current_x + step_dx * (i + 1))
                new_y = int(current_y + step_dy * (i + 1))
                win32gui.MoveWindow(hwnd, new_x, new_y, current_rect[2]-current_rect[0], current_rect[3]-current_rect[1], True)
                time.sleep(step_duration)
            
            return True
        except Exception as e:
            print(f"平滑移动窗口失败: {e}")
            return False
    
    def resize_window_smoothly(self, window_title, target_width, target_height, duration=1.0):
        # 平滑调整窗口大小
        try:
            hwnd = win32gui.FindWindow(None, window_title)
            if not hwnd:
                return False
            
            # 获取当前窗口位置和大小
            current_rect = win32gui.GetWindowRect(hwnd)
            current_x, current_y = current_rect[0], current_rect[1]
            current_width = current_rect[2] - current_rect[0]
            current_height = current_rect[3] - current_rect[1]
            
            # 计算缩放比例
            scale_x = target_width / current_width
            scale_y = target_height / current_height
            
            # 计算步数和每步缩放比例
            steps = 50
            step_duration = duration / steps
            
            # 执行平滑缩放
            for i in range(steps):
                # 计算当前步骤的缩放比例
                current_scale = (i + 1) / steps
                new_width = int(current_width + (target_width - current_width) * current_scale)
                new_height = int(current_height + (target_height - current_height) * current_scale)
                win32gui.MoveWindow(hwnd, current_x, current_y, new_width, new_height, True)
                time.sleep(step_duration)
            
            return True
        except Exception as e:
            print(f"平滑调整窗口大小失败: {e}")
            return False
    
    def find_window_by_keyword(self, keyword):
        # 根据关键词查找窗口
        found_windows = []
        
        def callback(hwnd, param):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if keyword in title:
                    rect = win32gui.GetWindowRect(hwnd)
                    found_windows.append({
                        'hwnd': hwnd,
                        'title': title,
                        'x': rect[0],
                        'y': rect[1],
                        'width': rect[2] - rect[0],
                        'height': rect[3] - rect[1]
                    })
            return True
        
        win32gui.EnumWindows(callback, None)
        return found_windows
    
    def move_and_resize_bilibili_window(self):
        # 移动并调整B站窗口大小
        import time
        
        # 等待浏览器窗口打开
        time.sleep(2)
        
        # 查找B站窗口
        bilibili_windows = self.find_window_by_keyword("哔哩哔哩")
        if not bilibili_windows:
            # 尝试用其他关键词查找
            bilibili_windows = self.find_window_by_keyword("bilibili")
        if not bilibili_windows:
            # 尝试用B站查找
            bilibili_windows = self.find_window_by_keyword("B站")
        
        if not bilibili_windows:
            print("未找到B站窗口")
            return False
        
        # 选择第一个找到的B站窗口
        bilibili_window = bilibili_windows[0]
        window_title = bilibili_window['title']
        
        # 获取屏幕大小
        screen_width = win32api.GetSystemMetrics(0)
        screen_height = win32api.GetSystemMetrics(1)
        
        # 计算目标位置：屏幕右侧边缘，距离顶部20像素
        target_x = screen_width - 600 - 20  # 600是目标宽度，20是边距
        target_y = 20
        
        # 计算目标大小：适合看视频的大小
        target_width = 600
        target_height = 400
        
        # 平滑移动窗口到目标位置
        self.move_window_smoothly(window_title, target_x, target_y, duration=1.5)
        
        # 平滑调整窗口大小
        self.resize_window_smoothly(window_title, target_width, target_height, duration=1.5)
        
        return True
    
    def search_in_browser(self, query, browser="chrome"):
        # 在浏览器中搜索指定内容
        try:
            print(f"正在搜索: {query}")
            import webbrowser
            # 根据浏览器类型构建搜索URL
            if browser.lower() == "chrome":
                url = f"https://www.google.com/search?q={query}"
            elif browser.lower() == "firefox":
                url = f"https://www.bing.com/search?q={query}"
            elif browser.lower() == "edge":
                url = f"https://www.bing.com/search?q={query}"
            else:
                url = f"https://www.google.com/search?q={query}"
            
            webbrowser.open(url)
            return True
        except Exception as e:
            print(f"搜索失败: {e}")
            return False
    
    def identify_browser_windows(self):
        # 识别当前打开的浏览器窗口
        try:
            windows = self.get_all_visible_windows()
            browser_windows = []
            
            # 浏览器标题关键词
            browser_keywords = ["Chrome", "Firefox", "Edge", "Internet Explorer", "浏览器"]
            
            for window in windows:
                if any(keyword in window['title'] for keyword in browser_keywords):
                    browser_windows.append(window)
            
            return browser_windows
        except Exception as e:
            print(f"识别浏览器窗口失败: {e}")
            return []
    
    def create_new_excel(self, file_name, sheet_name="Sheet1"):
        # 在桌面上创建新的Excel文件
        try:
            print(f"正在创建新的Excel文件: {file_name}")
            
            # 构建完整的文件路径
            excel_path = os.path.join(self.desktop_path, f"{file_name}.xlsx")
            
            # 检查文件是否已存在
            if os.path.exists(excel_path):
                print(f"Excel文件已存在: {excel_path}")
                return excel_path
            
            # 启动Excel
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            
            # 创建新工作簿
            workbook = excel.Workbooks.Add()
            
            # 如果有多个工作表，删除多余的
            while workbook.Sheets.Count > 1:
                workbook.Sheets(2).Delete()
            
            # 重命名工作表
            if sheet_name:
                workbook.Sheets(1).Name = sheet_name
            
            # 保存并关闭
            workbook.SaveAs(excel_path)
            workbook.Close()
            excel.Quit()
            
            print(f"Excel文件创建成功: {excel_path}")
            return excel_path
        except Exception as e:
            print(f"创建Excel文件失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def identify_ppt_windows(self):
        # 识别当前打开的PPT窗口
        try:
            # 直接使用win32gui枚举所有窗口，避免get_all_visible_windows的过滤
            ppt_windows = []
            
            def callback(hwnd, param):
                # 只处理可见窗口
                if win32gui.IsWindowVisible(hwnd):
                    # 获取窗口标题
                    title = win32gui.GetWindowText(hwnd)
                    # 获取窗口类名
                    class_name = win32gui.GetClassName(hwnd)
                    
                    # PPT窗口标题关键词
                    ppt_keywords = ["PowerPoint", "PPT", "演示文稿", "幻灯片放映", "PowerPoint Slide Show"]
                    # PPT窗口类名
                    ppt_class_names = ["PPTFrameClass", "PPTChildWindow", "PPTNotePageFrameClass"]
                    
                    # 检查标题或类名
                    if (title and any(keyword in title for keyword in ppt_keywords)) or \
                       class_name in ppt_class_names:
                        # 获取窗口矩形
                        rect = win32gui.GetWindowRect(hwnd)
                        # 计算窗口大小
                        width = rect[2] - rect[0]
                        height = rect[3] - rect[1]
                        
                        # 只处理有一定大小的窗口
                        if width > 100 and height > 100:
                            window_info = {
                                'hwnd': hwnd,
                                'title': title,
                                'x': rect[0],
                                'y': rect[1],
                                'width': width,
                                'height': height,
                                'center_x': (rect[0] + rect[2]) / 2,
                                'center_y': (rect[1] + rect[3]) / 2,
                            }
                            ppt_windows.append(window_info)
                return True
            
            # 枚举所有窗口
            win32gui.EnumWindows(callback, None)
            return ppt_windows
        except Exception as e:
            print(f"识别PPT窗口失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def identify_excel_windows(self):
        # 识别当前打开的Excel窗口
        try:
            # 直接使用win32gui枚举所有窗口，避免get_all_visible_windows的过滤
            excel_windows = []
            
            def callback(hwnd, param):
                # 只处理可见窗口
                if win32gui.IsWindowVisible(hwnd):
                    # 获取窗口标题
                    title = win32gui.GetWindowText(hwnd)
                    # 获取窗口类名
                    class_name = win32gui.GetClassName(hwnd)
                    
                    # Excel窗口标题关键词
                    excel_keywords = ["Excel", "电子表格", "工作表", "Excel - "]
                    # Excel窗口类名
                    excel_class_names = ["XLMAIN", "Excel7"]
                    
                    # 检查标题或类名
                    if (title and any(keyword in title for keyword in excel_keywords)) or \
                       class_name in excel_class_names:
                        # 获取窗口矩形
                        rect = win32gui.GetWindowRect(hwnd)
                        # 计算窗口大小
                        width = rect[2] - rect[0]
                        height = rect[3] - rect[1]
                        
                        # 只处理有一定大小的窗口
                        if width > 100 and height > 100:
                            window_info = {
                                'hwnd': hwnd,
                                'title': title,
                                'x': rect[0],
                                'y': rect[1],
                                'width': width,
                                'height': height,
                                'center_x': (rect[0] + rect[2]) / 2,
                                'center_y': (rect[1] + rect[3]) / 2,
                            }
                            excel_windows.append(window_info)
                return True
            
            # 枚举所有窗口
            win32gui.EnumWindows(callback, None)
            return excel_windows
        except Exception as e:
            print(f"识别Excel窗口失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def identify_word_windows(self):
        # 识别当前打开的Word窗口
        try:
            # 直接使用win32gui枚举所有窗口，避免get_all_visible_windows的过滤
            word_windows = []
            
            def callback(hwnd, param):
                # 只处理可见窗口
                if win32gui.IsWindowVisible(hwnd):
                    # 获取窗口标题
                    title = win32gui.GetWindowText(hwnd)
                    # 获取窗口类名
                    class_name = win32gui.GetClassName(hwnd)
                    
                    # Word窗口标题关键词
                    word_keywords = ["Word", "文档", "Microsoft Word"]
                    # Word窗口类名
                    word_class_names = ["OpusApp", "Word.Application"]
                    
                    # 检查标题或类名
                    if (title and any(keyword in title for keyword in word_keywords)) or \
                       class_name in word_class_names:
                        # 获取窗口矩形
                        rect = win32gui.GetWindowRect(hwnd)
                        # 计算窗口大小
                        width = rect[2] - rect[0]
                        height = rect[3] - rect[1]
                        
                        # 只处理有一定大小的窗口
                        if width > 100 and height > 100:
                            window_info = {
                                'hwnd': hwnd,
                                'title': title,
                                'x': rect[0],
                                'y': rect[1],
                                'width': width,
                                'height': height,
                                'center_x': (rect[0] + rect[2]) / 2,
                                'center_y': (rect[1] + rect[3]) / 2,
                            }
                            word_windows.append(window_info)
                return True
            
            # 枚举所有窗口
            win32gui.EnumWindows(callback, None)
            return word_windows
        except Exception as e:
            print(f"识别Word窗口失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def check_ppt_files(self):
        # 检查桌面上的PPT文件
        ppt_files = []
        
        # 首先更新桌面元素，确保获取最新的文件列表
        self.update_desktop_elements()
        
        # 遍历所有桌面元素
        for element in self.desktop_elements:
            if element['type'] == 'file':
                # 检查文件扩展名
                if element['name'].lower().endswith('.ppt') or element['name'].lower().endswith('.pptx'):
                    ppt_files.append(element)
        
        # 如果桌面元素中没有找到PPT文件，直接遍历桌面目录
        if not ppt_files:
            try:
                for filename in os.listdir(self.desktop_path):
                    file_path = os.path.join(self.desktop_path, filename)
                    if os.path.isfile(file_path):
                        if filename.lower().endswith('.ppt') or filename.lower().endswith('.pptx'):
                            # 创建文件信息
                            file_info = {
                                'name': filename,
                                'path': file_path,
                                'type': 'file',
                                'x': 200,  # 模拟位置
                                'y': 200,
                                'width': 80,
                                'height': 80,
                                'size': os.path.getsize(file_path),
                                'type_desc': 'PowerPoint演示文稿',
                                'modified_date': time.ctime(os.path.getmtime(file_path)),
                            }
                            ppt_files.append(file_info)
            except Exception as e:
                print(f"直接遍历桌面目录失败: {e}")
        
        return ppt_files
    
    def get_browser_url(self, window_hwnd):
        # 获取指定浏览器窗口的URL（需要更复杂的实现，这里仅返回示例）
        # 实际实现需要使用Windows API或浏览器扩展
        return "https://www.example.com"
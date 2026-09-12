
import sys
import os
import time

# 注意：单实例检查已封装为 check_single_instance() 函数
# 在 if __name__ == '__main__': 中调用，避免 import 时就触发退出
# 也便于单元测试和 mock

# 继续导入其他模块
import time
import random
import math
import statistics
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt5.QtGui import QPainter, QBrush, QColor, QCursor, QTransform
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal

try:
    from logger_utils import get_logger
except ImportError:  # 允许被包外单独导入
    import logging

    def get_logger(name):
        return logging.getLogger(name)

_log = get_logger(__name__)



# 添加性能监控功能
class PerformanceMonitor:
    def __init__(self):
        self.function_times = {}
        self.start_time = time.time()
        
    def record_time(self, function_name, execution_time):
        """记录函数执行时间"""
        if function_name not in self.function_times:
            self.function_times[function_name] = []
        self.function_times[function_name].append(execution_time)
        
    def get_stats(self):
        """获取性能统计信息"""
        stats = {}
        for function_name, times in self.function_times.items():
            if times:
                stats[function_name] = {
                    'count': len(times),
                    'avg': statistics.mean(times) * 1000,  # 转换为毫秒
                    'min': min(times) * 1000,
                    'max': max(times) * 1000
                }
        return stats
    
    def print_stats(self):
        """打印性能统计信息"""
        pass

# 创建全局性能监控实例
perf_monitor = PerformanceMonitor()

# 性能监控装饰器
def monitor_performance(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        perf_monitor.record_time(func.__name__, execution_time)
        return result
    return wrapper

# 添加项目根目录到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
_log.debug(f"添加项目根目录: {project_root}")

# 直接导入模块
from modules.sprite_loader import SpriteLoader
from modules.dialogue_system import DialogueSystem
from modules.dialogue_ui import DialogueUI
from modules.weather_system import WeatherSystem
from modules.pet_ai import PetAI
from modules.desktop_interaction import DesktopInteraction
from modules.energy_hunger import EnergyHungerSystem
from modules.emotion_system import EmotionSystem
from modules.memory_system import MemorySystem
from modules.customization_system import CustomizationSystem
from modules.social_growth_system import SocialGrowthSystem
from modules.entertainment_system import EntertainmentSystem
from modules.config_manager import ConfigManager

from modules.floor_manager import FloorManager
from modules.api_client import create_client
from modules.ai_driver import AiActionDriver
from modules.command_manager import CommandManager
from modules.autonomous_agent import AutonomousAgent
from modules.sound_manager import SoundManager
# 联网搜索摘要：依赖 beautifulsoup4。改为"可选导入"而不是整段注释掉——
# 原写法让整个模块变成永远不可达的死代码（需求"能上网"缺一环），
# 且一旦有人取消注释而环境没有 bs4，程序会在 import 期直接崩溃。
try:
    from modules.search_summarizer import SearchSummarizer
except Exception as _e:  # ImportError / 依赖缺失 / 模块内异常
    SearchSummarizer = None
    _log.warning("联网搜索摘要模块不可用（缺少 beautifulsoup4？已降级）: %s", _e)

class RalseiPet(QMainWindow):
    # 跨线程 API 结果信号：(response, callback) —— 工作线程 emit，主线程槽处理，
    # 避免线程内 QTimer.singleShot 因无 Qt 事件循环导致回调永不触发
    _api_result = pyqtSignal(object, object)

    def __init__(self):
        super().__init__()
        
        # 加载配置文件
        self.config_manager = ConfigManager()
        
        # 本地 AI 接入准备（api_client 工厂，见 modules/api_client.py）
        api_config = self.config_manager.get_api_config()
        self.api_enabled = api_config['enabled']
        self.api_client = None
        self.api_config = api_config
        
        self.init_ui()
        self.load_resources()
        self.init_systems()
        self.init_animation()
        self.init_movement()
        self.init_timers()
        
        # 连接跨线程 API 结果信号（必须在 handle_api_response 依赖的对象初始化后）
        self._api_result.connect(self._on_api_result)
        
        # 注册退出处理函数
        import atexit
        atexit.register(self.cleanup_on_exit)
        
        # 游戏相关状态
        self.game_state = {
            "is_playing": False,
            "game_type": None,
            "game_round": 0,
            "player_score": 0,
            "ralsei_score": 0,
            "game_history": [],
            "total_games": 0,
            "total_wins": 0,
            "total_losses": 0,
            "total_ties": 0,
            "best_streak": 0,
            "current_streak": 0
        }
        
        # 石头剪刀布游戏的选项
        self.rock_paper_scissors_options = ["石头", "剪刀", "布"]
        
        # 猜数字游戏相关
        self.guess_number_game = {
            "target_number": 0,
            "min_number": 1,
            "max_number": 100,
            "attempts": 0,
            "max_attempts": 7
        }
        
        # 系统托盘恢复入口（"隐藏"菜单后唯一的找回途径，见 _hide_ralsei）
        self._tray = None
        self._setup_tray()
        
    def _setup_tray(self):
        # 修复：右键"隐藏"后原实现无任何 GUI 恢复入口（无托盘/热键），而顶层单实例
        # 互斥又拒绝重启新实例 → 宠物"永久丢失"，只能任务管理器杀进程。
        # 系统托盘提供"显示 Ralsei / 退出"；托盘不可用环境由 _hide_ralsei 退化为最小化。
        try:
            from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
            from PyQt5.QtGui import QPixmap, QPainter, QBrush, QColor, QIcon
            from PyQt5.QtCore import Qt
            if not QSystemTrayIcon.isSystemTrayAvailable():
                self._tray = None
                return
            # 程序内生成一个简单头像图标，不依赖外部资源文件
            pix = QPixmap(64, 64)
            pix.fill(Qt.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QBrush(QColor(96, 200, 210)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(6, 4, 52, 44)   # 头
            p.drawEllipse(18, 34, 28, 26)  # 身体
            p.end()
            # 修复：QSystemTrayIcon 首参须为 QIcon，直接传 QPixmap 会抛
            # "arguments did not match any overloaded call" → 托盘初始化失败。
            tray = QSystemTrayIcon(QIcon(pix), self)
            menu = QMenu(self)
            show_action = QAction("显示 Ralsei", self)
            show_action.triggered.connect(self._show_from_tray)
            quit_action = QAction("退出", self)
            quit_action.triggered.connect(QApplication.quit)
            menu.addAction(show_action)
            menu.addSeparator()
            menu.addAction(quit_action)
            tray.setContextMenu(menu)
            tray.setToolTip("Ralsei 桌宠")
            tray.activated.connect(self._on_tray_activated)
            self._tray = tray
        except Exception as e:
            _log.warning(f"系统托盘初始化失败（不影响使用）: {e}")
            self._tray = None

    def _hide_ralsei(self):
        # "隐藏"菜单动作：缩到托盘（可找回）；托盘不可用时最小化到任务栏
        tray = getattr(self, '_tray', None)
        try:
            from PyQt5.QtWidgets import QSystemTrayIcon
            tray_ok = tray is not None and QSystemTrayIcon.isSystemTrayAvailable()
        except Exception:
            tray_ok = False
        if tray_ok:
            self.hide()
            tray.show()
            try:
                tray.showMessage("Ralsei", "我藏起来啦~ 点托盘图标就能找到我！",
                                 QSystemTrayIcon.Information, 2500)
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
        else:
            self.showMinimized()

    def _show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()
        try:
            if getattr(self, '_tray', None) is not None:
                self._tray.hide()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)

    def _on_tray_activated(self, reason):
        try:
            from PyQt5.QtWidgets import QSystemTrayIcon
            if reason == QSystemTrayIcon.Trigger:  # 单击/双击托盘图标
                self._show_from_tray()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)

    def init_ui(self):
        # 创建透明窗口，移除固定置顶，改为动态调整
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 获取屏幕大小，将Ralsei初始位置设置在右下角，而不是中央
        screen_geometry = QApplication.desktop().availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        
        # 初始位置：右下角，距离边缘50像素
        init_x = screen_width - 150  # 距离右边缘50像素
        init_y = screen_height - 150  # 距离下边缘50像素
        
        self.setGeometry(init_x, init_y, 100, 100)  # 初始大小
        self.setWindowTitle("Ralsei Pet")
        
        # 创建主标签用于显示精灵
        self.sprite_label = QLabel(self)
        self.sprite_label.setGeometry(0, 0, 100, 100)
        self.sprite_label.setAlignment(Qt.AlignCenter)
        
        # 启用鼠标追踪，以便Ralsei能够响应鼠标事件
        self.setMouseTracking(True)
        self.sprite_label.setMouseTracking(True)
        
        # 拖动鼠标相关变量
        self.is_dragging_mouse = False
        self.drag_start_pos = None
        self.drag_target_pos = None
        self.drag_duration = 2.0  # 拖动持续时间
        self.drag_start_time = None
        
        # 主动拖动鼠标的定时器
        self.mouse_drag_timer = QTimer(self)
        self.mouse_drag_timer.timeout.connect(self.update_mouse_drag)
        # 修复：原来是 setSingleShot(True) + start(drag_duration*1000)，
        # 即整段拖动只回调一次，且回调时 elapsed >= drag_duration 立刻走"结束"分支，
        # 结果光标从头到尾一步都没移动。改为周期定时器，由 start_mouse_drag 按帧间隔启动。
        self.mouse_drag_timer.setSingleShot(False)
        
    def load_resources(self):
        # 加载精灵资源
        _log.debug("开始加载精灵资源...")
        self.sprite_loader = SpriteLoader()
        try:
            self.sprite_loader.load_sprites()
            _log.debug("精灵资源加载完成！")
            # 打印加载的动画
            _log.debug(f"加载的动画列表: {list(self.sprite_loader.animation_mapping.keys())}")
        except Exception as e:
            _log.warning(f"加载精灵资源失败: {e}")
            import traceback
            traceback.print_exc()
        
    def init_systems(self):
        # 初始化各个系统
        self.desktop_interaction = DesktopInteraction(self)
        self.dialogue_system = DialogueSystem(self.desktop_interaction)
        self.dialogue_ui = DialogueUI(self)
        self.weather_system = WeatherSystem()
        self.pet_ai = PetAI(self)
        # 联网搜索摘要（可用时初始化；不可用时置 None，调用方需判空）
        # 注意：summarize_search_results / get_brief_summary 内部是同步网络请求，
        # 若要在交互里使用，必须放到后台线程（参考 chat_with_ai 的线程+信号模式）。
        if SearchSummarizer is not None:
            try:
                self.search_summarizer = SearchSummarizer()
            except Exception as e:
                _log.warning(f"联网搜索摘要初始化失败: {e}")
                self.search_summarizer = None
        else:
            self.search_summarizer = None
        self.energy_hunger = EnergyHungerSystem(self)
        self.emotion_system = EmotionSystem(self)
        self.memory_system = MemorySystem(self)
        self.customization_system = CustomizationSystem(self)
        self.social_growth = SocialGrowthSystem(self)
        self.entertainment_system = EntertainmentSystem(self)
        
        # 初始化声音管理器
        try:
            self.sound_manager = SoundManager(parent=self)
        except Exception as e:
            _log.warning(f"声音管理器初始化失败: {e}")
            self.sound_manager = None
        
        # 初始化楼层管理器，用于实现"建楼"要求
        self.floor_manager = FloorManager(self)
        
        # 初始化自主代理（Ralsei作为"第二个独立用户"与桌面交互）
        try:
            self.autonomous_agent = AutonomousAgent(
                get_pos=lambda: self.pos(),
                set_target_pos=lambda x, y: (setattr(self, 'target_pos', QPoint(int(x), int(y))),
                                              setattr(self, 'is_moving', True)),
                change_animation=self.change_animation,
                play_once=self.play_animation_once,
                show_dialogue=lambda speaker, msg, face: (self.dialogue_ui.add_dialogue(speaker, msg, face),
                                                          self.dialogue_ui.show_dialogue()),
                add_emotion=lambda e, v: self.emotion_system.add_emotion(e, v),
                desktop=self.desktop_interaction,
                get_busy_flags=self._agent_busy_flags,
            )
            self.autonomous_agent.start()
        except Exception as e:
            _log.warning(f"自主代理初始化失败: {e}")
            self.autonomous_agent = None
        
        # 初始化虚拟鼠标

        
        # 初始化API客户端和命令管理器
        # 修复：原来用 APIClient(=LocalAIStub) 一次性构造——即使配置 enabled=True 也
        # 永远是 stub（本地 AI 永不生效）；且运行中改配置不重建 = 无法热启用。
        # 现在统一走 create_client 工厂，保存配置时重建即可热启用（本地 AI 端口）。
        api_config = self.config_manager.get_api_config()
        self.api_client = create_client(api_config)
        self.command_manager = CommandManager(self)
        
        # 本地 AI 行动驱动（行为大脑）：模型周期性挑选白名单动作让 Ralsei 表演。
        # 独立于对话（chat_with_ai）；模型不可用时完全静默，规则行为照常。
        try:
            self.ai_driver = AiActionDriver(self)
        except Exception as e:
            _log.warning(f"AI 行动驱动初始化失败: {e}")
            self.ai_driver = None
        
        # 初始化透明占位符系统
        self.init_placeholder_system()
        
        # 拖拽文件跟踪
        self.dragged_file = None
        self.is_following_dragged_file = False

        # ========== Spell / 施法流程 状态字段 ==========
        self._spell_stage = None                    # None | 'walking' | 'casting'
        self._spell_target_direction = None         # 'left' | 'right' | 'up' | 'down'
        self._spell_target_path = None              # 要打开/创建的路径
        self._spell_target_kind = None              # 'file' | 'folder' | '__cast_only__'
        self._spell_target_screen_pos = None        # walking 阶段靠近的屏幕坐标 (x,y)
        self._spell_finish_cb = None                # 完整 11 帧后的回调 (path, kind) -> None
        self._spell_frames_seen = 0                 # 已确认看到的 spell 帧数
        self._spell_cast_start_frame = None         # spell 起始帧索引
        self._spell_touched_flag = False            # 施法期间是否有触摸/拖拽等打断
        self._spell_auto_suspended = False          # 施法期间是否暂停了自主代理

        # ========== 躲猫猫 (hide & seek) 状态字段 ==========
        self._hide_stage = None                     # None | moving_to_center | creating | hiding_spell | moving_to_folder | searching
        self._hide_folder_path = None               # 选中的藏身文件夹绝对路径
        self._hide_obstacles = []                   # 5 个障碍物文件夹路径列表（上3下2）
        self._hide_center_x = None
        self._hide_center_y = None
        self._hide_search_timer = None              # searching 阶段定时器
        # game_state 统一游戏状态
        if not hasattr(self, 'game_state') or not isinstance(getattr(self, 'game_state', None), dict):
            self.game_state = {'is_playing': False, 'game_type': None}

    # 帧动画播放相关代码 - 初始化动画系统
    def init_animation(self):
        # 初始化动画定时器
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(167)  # 初始占位，下方随即按配置重启（30FPS 对齐游戏）
        
        self.current_animation = "idle"
        self.next_animation = None  # 下一个要播放的动画
        self.current_frame = 0
        self._play_once_active = False  # 一次性动画播放标志
        self._play_once_frame_counter = 0  # 一次性动画已播放帧数
        self._play_once_callback = None  # 一次性动画完成回调
        
        # 动画播放控制
        self.animation_change_cooldown = 0.8  # 0.8秒冷却时间，防止频繁切换导致的抽搐
        # 表演动画最小持续时间：laugh/tea/wave/dance 等被触发后至少播这么久才允许切回 idle，
        # 避免"闪一下就没了"（修复：is_happy 等状态只持续一帧导致表演动画只播0.15秒）。
        self._last_perf_anim_time = 0.0
        self._perf_anim_min_duration = 1.5
        self.last_animation_change = time.time() - self.animation_change_cooldown  # 初始化为冷却时间之前，确保第一次切换也受到冷却时间限制
        
        # 从配置中获取动画设置（默认 30FPS，与《Deltarune》游戏帧率一致）
        self.animation_fps = self.config_manager.get("animation.fps", 30)
        self.animation_frame_delay = self.config_manager.get("animation.frame_delay", int(1000 / self.animation_fps))  # 毫秒，转换为整数
        
        # 修复：动画定时器原来固定 167ms（≈6FPS），导致配置 fps>6 完全无效
        # （update_animation 内帧推进按 1000/fps 判定，但定时器每 167ms 才触发一次）。
        # 现在周期跟随配置的 frame_delay（下限 16ms ≈60FPS 上限）。
        try:
            self.animation_frame_delay = int(self.animation_frame_delay)
        except (TypeError, ValueError):
            self.animation_frame_delay = int(1000 / max(1, self.animation_fps))
        self.animation_timer.start(max(16, self.animation_frame_delay))
        
        # 位置偏移量，用于调整动画位置
        self.current_offset = (0, 0)
        
        # 初始化动画时间记录变量
        self._last_animation_time = time.time()
        
        # 动画优先级系统
        self.animation_priorities = {
            "idle": 1,
            "walk_down": 2,
            "walk_left": 2,
            "walk_right": 2,
            "walk_up": 2,
            "run_down": 3,
            "run_left": 3,
            "run_right": 3,
            "run_up": 3,
            # spell / spell_left 优先级最高（只有 force=True 或更高优先级才能覆盖）
            "spell": 5,
            "spell_left": 5,
            "jump": 4,
            "jump_ready": 4,
            "jump_ball": 4,
            "fall": 4,
            "fall_back": 4,
            "splat": 4,
            "land": 4,
            "laugh": 3,
            "tea": 3,
            "victory": 3,
            "wave": 3,
            "wave_start": 3,
            "wave_down": 3,
            "dance": 3,
            "cry": 3,
            "hug": 3,
            "roll": 3,
            "slide": 3,
            "act": 3,
            "attack": 3,
            "battleintro": 3,
            "cotton_talk": 3,
            "cower": 3,
            "curtsy": 3,
            "defend": 3,
            "hug_stop": 3,
            "kneel_cry": 3,
            "kneel_serious": 3,
            "look_up": 3,
            "nuzzle": 3,
            "pose": 3,
            "sing": 3,
            "surprised": 3
        }
        
        # 当前动画的优先级
        self.current_priority = self.animation_priorities.get(self.current_animation, 1)
        
    def init_timers(self):
        # 初始化其他定时器
        # AI状态更新定时器
        self.ai_timer = QTimer(self)
        self.ai_timer.timeout.connect(self.update_ai)
        self.ai_timer.start(3000)  # 3秒更新一次AI状态，减少AI计算
        
        # 精力和饥饿度更新定时器
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(10000)  # 10秒更新一次状态，减少状态更新频率
        
        # 对话发起定时器
        self.dialogue_init_timer = QTimer(self)
        self.dialogue_init_timer.timeout.connect(self.check_initiate_dialogue)
        self.dialogue_init_timer.start(15000)  # 每15秒检查一次是否发起对话，减少对话频率
        
        # 天气响应定时器
        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self.check_weather_response)
        self.weather_timer.start(300000)  # 每5分钟检查一次天气
        
        # 移除自动停止功能，以便程序可以持续运行
        # self.auto_stop_timer = QTimer(self)
        # self.auto_stop_timer.timeout.connect(self.auto_stop)
        # self.auto_stop_timer.start(300000)  # 5分钟后自动停止
        # print("程序将在5分钟后自动停止...")
        
        # 主动拖动鼠标的定时器
        self.auto_mouse_drag_timer = QTimer(self)
        self.auto_mouse_drag_timer.timeout.connect(self.initiate_auto_mouse_drag)
        self.auto_mouse_drag_timer.start(60000)  # 每60秒尝试一次主动拖动鼠标
        
        # 虚拟鼠标互动定时器

        
        # API控制定时器
        self.api_control_timer = QTimer(self)
        self.api_control_timer.timeout.connect(self.check_api_commands)
        self.api_control_timer.start(2000)  # 每2秒检查一次API命令
        
    def init_placeholder_system(self):
        # 初始化透明占位符系统，用于Ralsei与桌面文件夹/文件的互动
        self.placeholder_labels = []
        self.placeholder_elements = []
        
        # 创建定时器用于更新占位符位置
        self.placeholder_timer = QTimer(self)
        self.placeholder_timer.timeout.connect(self.update_placeholders)
        self.placeholder_timer.start(1000)  # 每秒更新一次占位符位置
        
        # 初始化占位符
        self.create_placeholders()
        
    def create_placeholders(self):
        # 创建桌面元素的透明占位符
        # 首先清空现有的占位符
        for label in self.placeholder_labels:
            label.deleteLater()
        self.placeholder_labels.clear()
        self.placeholder_elements.clear()
        
        # 获取桌面元素
        desktop_elements = self.desktop_interaction.desktop_elements
        
        # 为每个桌面元素创建透明占位符
        for element in desktop_elements:
            # 创建透明标签作为占位符
            placeholder = QLabel(self)
            placeholder.setGeometry(element['x'], element['y'], element['width'], element['height'])
            placeholder.setAttribute(Qt.WA_TransparentForMouseEvents)
            placeholder.setAttribute(Qt.WA_TranslucentBackground)
            placeholder.setStyleSheet("border: 1px solid transparent;")
            placeholder.show()
            
            # 保存占位符和对应的元素信息
            self.placeholder_labels.append(placeholder)
            self.placeholder_elements.append(element)
            
    def update_placeholders(self):
        # 更新占位符位置和大小，实时反映桌面元素的变化
        # 首先更新桌面元素列表
        self.desktop_interaction.update_desktop_elements()
        
        # 重新创建占位符
        self.create_placeholders()
        
    def get_element_at_pos(self, pos):
        # 获取指定位置的桌面元素
        for element in self.placeholder_elements:
            element_rect = QRect(element['x'], element['y'], element['width'], element['height'])
            if element_rect.contains(pos):
                return element
        return None
        
    # 移动相关代码 - 初始化移动系统
    def init_movement(self):
        # 初始化移动定时器
        self.movement_timer = QTimer(self)
        self.movement_timer.timeout.connect(self.update_movement)
        self.movement_timer.start(30)  # 30ms更新一次，提高平滑度
        
        self.target_pos = QPoint(100, 100)
        
        # 从配置中获取移动设置，增加移动速度，使Ralsei动作更快
        self.speed = self.config_manager.get("movement.speed", 10.0)
        self.min_speed = self.config_manager.get("movement.min_speed", 8.0)
        self.max_speed = self.config_manager.get("movement.max_speed", 15.0)
        
        # 真实物理系统相关变量（客观因素），优化参数使运动更自然
        self.mass = 30.0  # Ralsei的质量（kg）
        self.gravity = 500.0  # 降低重力加速度，使跳跃更自然
        self.friction = 0.95  # 调整摩擦力，使移动更真实
        self.air_resistance = 0.985  # 调整空气阻力，使移动更符合物理规律
        self.bounce_coefficient = 0.2  # 降低弹跳系数，减少不自然的弹跳
        
        # 添加平滑移动相关变量
        self.smoothness_factor = 0.1  # 降低平滑因子，使移动更自然
        self.current_speed_x = 0
        self.current_speed_y = 0
        self.acceleration_x = 0
        self.acceleration_y = 0
        
        # 添加运动相关的状态变量
        self.is_moving = True
        self.idle_timer = 0
        self.moving_duration = 0
        
        # 摔倒和恢复相关变量
        self.is_falling = False
        self.is_recovering = False
        self.fall_start_time = None
        self.recovery_start_time = None
        self.max_idle_duration = 0
        self.max_moving_duration = 0
        self.last_update_time = time.time()  # 记录上次更新时间
        self.current_direction = "down"  # 保存当前移动方向，默认为向下
        self.previous_direction = "down"  # 保存上一次移动方向，用于保持一致性
        self.randomize_movement_pattern()
        
        # 添加缺失的变量定义
        self.swing_speed = 0.01  # 摆动速度，用于步幅变化
        self.direction_change_smoothness = 0.5  # 提高方向变化平滑度，使方向变化更自然
        self.speed_fluctuation = 0.0  # 速度波动
        self.fluctuation_speed = 0.01  # 波动速度
        self.stride_fluctuation = 0.0  # 步幅波动
        self.stride_variation = 1.0  # 步幅变化率
        self.speed_variation = 1.0  # 速度变化率
        
        # 添加随机性变量，使移动更自然，控制在2-3像素范围内
        self.movement_noise = 0.0
        self.noise_change_rate = 0.005  # 初始噪声变化率，控制在2-3像素范围内
        
        # 添加跳跃相关变量
        self.is_jumping = False
        self.jump_height = 50  # 跳跃高度
        self.jump_duration = 1.0  # 跳跃持续时间（秒）
        self.jump_start_time = 0
        self.jump_start_pos = QPoint(0, 0)
        self.jump_target_pos = QPoint(0, 0)
        self.jump_target_window = None
        
        # 跳跃疲劳系统（人体功能模拟）
        self.jump_count = 0  # 当前跳跃次数
        self.max_jumps = 3  # 最大连续跳跃次数
        self.jump_cooldown = 2.0  # 每次跳跃后的冷却时间（秒）
        self.last_jump_time = 0  # 上次跳跃的时间
        self.resting_time = 0  # 休息时间（秒）
        self.needs_rest = False  # 是否需要休息
        self.stamina = 100.0  # 体力值（0-100）
        self.stamina_regen_rate = 5.0  # 每秒恢复体力
        self.jump_stamina_cost = 20.0  # 每次跳跃消耗的体力
        
        # 鼠标跟随相关变量
        self.is_following_mouse = False  # 控制是否开启鼠标跟随
        self.mouse_follow_speed = 5  # 鼠标跟随速度
        self.mouse_follow_distance = 50  # 鼠标跟随触发距离
        self._last_mouse_pos = None  # 记录上次鼠标位置
        self.rest_duration = 5.0  # 休息持续时间（秒）
        
        # 睡眠模式相关变量（人体功能模拟）
        self.is_sleeping = False
        self.sleep_timer = 0
        self.max_sleep_idle_duration = 300  # 300秒（5分钟）无互动后进入睡眠模式
        self.last_interaction_time = time.time()  # 上次互动时间
        
        # 摔倒和恢复状态
        self.is_falling = False
        self.is_recovering = False
        self.fall_duration = 0.0
        self.max_fall_duration = 5.0
        self.recovery_duration = 0.0
        self.recovery_max_duration = 5.0
        
        # 物品持有状态
        self.has_ball = False
        self.is_holding_cotton_candy = False
        self.is_wearing_suit = False
        
        # 动作状态
        self.is_using_item = False
        self.is_spellcasting = False
        self.is_laughing = False
        self.is_rolling = False
        self.is_sliding = False
        self.is_teasplashed = False
        self.is_victorious = False
        self.is_surprised = False
        self.is_happy = False
        self.is_shy = False
        self.is_unhappy = False
        self.is_sleeping_walk = False
        
        # 状态计时器
        self.surprised_timer = 0
        self.happy_timer = 0
        self.shy_timer = 0
        self.unhappy_timer = 0
        self.idle_walk_timer = 0
        
        # 添加窗口相关变量
        self.current_window = None  # 当前所在窗口
        self.window_level = 0  # 当前所在窗口层级
        self.last_window_check_time = 0  # 上次窗口检查时间
        self.window_check_interval = 2.0  # 增加窗口检查间隔，优化性能
        self.last_window_rect = None  # 上次窗口位置和大小
        self.ralsei_window_relative_pos = QPoint(0, 0)  # Ralsei在窗口内的相对位置
        self.is_falling = False  # 是否正在摔倒
        self.is_gravity_falling = False  # 是否正在重力掉落
        self.fall_duration = 0.0  # 摔倒持续时间
        self.fall_speed = 0.0  # 重力掉落速度
        self.fall_start_time = 0  # 重力掉落开始时间
        self.fall_start_pos = QPoint(0, 0)  # 重力掉落开始位置
        self.max_fall_duration = 2.0  # 最大摔倒持续时间（秒）
        
        # 空间坐标系统（简化版，只保留基本功能）
        self.spatial_pos = {"x": 0, "y": 0, "z": 0}  # Ralsei的三维空间坐标
        self.current_platform_z = 0  # 当前所在平台的z坐标
        
        # 楼层系统相关变量
        self.current_floor = None  # 当前所在楼层
        self.last_floor_check_time = 0  # 上次楼层检查时间
        self.floor_check_interval = 1.0  # 楼层检查间隔（秒）
        
        # 环境变量（客观因素）
        self.current_time = time.strftime("%H:%M:%S")  # 当前时间
        self.time_of_day = "morning"  # 一天中的时间：morning, afternoon, evening, night
        self.weather = "sunny"  # 天气：sunny, cloudy, rainy, snowy
        self.temperature = 22.0  # 当前环境温度
        self.humidity = 50.0  # 湿度百分比
        
        # 添加情绪和状态系统（基于客观因素）
        self.emotions = {
            "happiness": 50.0,
            "sadness": 0.0,
            "anger": 0.0,
            "fear": 0.0,
            "surprise": 0.0,
            "boredom": 0.0,
            "tiredness": 0.0,
            "excitement": 0.0
        }
        self.mood = "normal"  # 整体心情：happy, sad, angry, scared, bored, tired, excited, normal
        self.last_mood_change = time.time()  # 上次心情变化时间
        
        # 添加视频观看相关变量
        self.is_watching_video = False  # 是否正在观看视频
        self.video_start_time = 0  # 视频开始观看时间
        self.video_duration = 0  # 视频持续时间
        self.current_video_url = ""  # 当前观看的视频URL
        self.video_platform = ""  # 当前视频平台
        self.video_title = ""  # 当前视频标题
        self.video_watch_history = []  # 视频观看历史
        self.video_preferences = ["游戏", "动画", "音乐", "科普", "搞笑", "Deltarune", "Undertale"]  # 视频偏好
        
        # 添加活动状态系统（客观行为记录）
        self.current_activity = "idle"  # 当前活动：idle, walking, running, jumping, sleeping
        self.activity_history = []  # 活动历史
        
        # 初始化环境和心情（客观因素）
        self.update_environment()
        self.update_mood()
        
    def update_environment(self):
        # 更新环境变量，使用真实的Windows API获取环境信息
        
        # 更新当前时间
        current_time = time.strftime("%H:%M:%S")
        self.current_time = current_time
        
        # 根据时间判断一天中的时段
        hour = int(time.strftime("%H"))
        if 6 <= hour < 12:
            self.time_of_day = "morning"
        elif 12 <= hour < 18:
            self.time_of_day = "afternoon"
        elif 18 <= hour < 22:
            self.time_of_day = "evening"
        else:
            self.time_of_day = "night"
        
        # 使用现有的WeatherSystem获取天气信息
        self.weather_system.update_weather()
        self.weather = self.weather_system.get_current_weather()
        
        # 根据天气和时间更新温度
        base_temperature = 22.0
        if self.weather == "sunny":
            base_temperature += random.uniform(2.0, 5.0)
        elif self.weather == "cloudy":
            base_temperature += random.uniform(0.0, 2.0)
        elif self.weather == "rainy":
            base_temperature -= random.uniform(2.0, 4.0)
        elif self.weather == "snowy":
            base_temperature -= random.uniform(4.0, 8.0)
        
        # 根据时间调整温度
        if self.time_of_day == "night":
            base_temperature -= random.uniform(3.0, 6.0)
        
        # 平滑过渡温度变化
        temp_diff = base_temperature - self.temperature
        self.temperature += temp_diff * 0.1
        
        # 更新湿度（客观因素）
        if self.weather == "rainy":
            self.humidity = min(90.0, self.humidity + random.uniform(1.0, 3.0))
        elif self.weather == "sunny":
            self.humidity = max(30.0, self.humidity - random.uniform(0.5, 2.0))
        else:
            self.humidity += random.uniform(-1.0, 1.0)
    
    def update_mood(self):
        # 更新Ralsei的心情，基于客观因素
        
        # 基础情绪变化（自然衰减）
        for emotion in self.emotions:
            # 情绪自然衰减
            self.emotions[emotion] *= 0.99
            
            # 情绪值限制在0-100之间
            self.emotions[emotion] = max(0.0, min(100.0, self.emotions[emotion]))
        
        # 根据环境客观因素调整情绪
        if self.weather == "sunny":
            self.emotions["happiness"] += 0.5
            self.emotions["sadness"] -= 0.5
        elif self.weather == "rainy":
            self.emotions["sadness"] += 0.3
            self.emotions["happiness"] -= 0.3
        
        if self.time_of_day == "night":
            self.emotions["tiredness"] += 0.5
        
        # 根据活动状态调整情绪
        if self.current_activity == "idle":
            self.emotions["boredom"] += 0.3
        elif self.current_activity == "jumping":
            self.emotions["excitement"] += 0.5
        elif self.current_activity == "sleeping":
            self.emotions["tiredness"] -= 0.8
        
        # 计算整体心情
        if self.emotions["happiness"] > 70:
            self.mood = "happy"
        elif self.emotions["sadness"] > 50:
            self.mood = "sad"
        elif self.emotions["tiredness"] > 70:
            self.mood = "tired"
        elif self.emotions["excitement"] > 60:
            self.mood = "excited"
        elif self.emotions["boredom"] > 60:
            self.mood = "bored"
        else:
            self.mood = "normal"
        
        # 同步旧版 emotions 字典到新版 emotion_system，避免双系统不一致
        self._sync_emotions_to_system()

    # 旧版 emotions key → 新版 emotion_system key 映射
    _EMOTION_KEY_MAP = {
        "happiness": "happy",
        "sadness": "sad",
        "anger": "angry",
        "fear": "fear",
        "surprise": "surprised",
        "boredom": "bored",
        "tiredness": "tired",
        "excitement": "excited",
    }

    def _sync_emotions_to_system(self):
        """将旧版 self.emotions 字典的值同步到新版 self.emotion_system。
        happiness(0-100) 映射为 happy(-50~50)，其余直接映射。"""
        for old_key, new_key in self._EMOTION_KEY_MAP.items():
            old_val = self.emotions.get(old_key, 0.0)
            if old_key == "happiness":
                # happiness 以 50 为中性点，映射到 happy 以 0 为中性点
                new_val = old_val - 50.0
            else:
                new_val = old_val
            try:
                self.emotion_system.set_emotion(new_key, new_val)
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)

    def _agent_busy_flags(self) -> dict:
        """返回各种会与自主代理冲突的状态标志。
        施法中 / 游戏中 / 拖拽中 / 跳跃中 / 掉落中 都会让自主代理立即暂停。"""
        return {
            "dragging": getattr(self, "is_dragging_mouse", False) or getattr(self, "_is_being_dragged", False),
            "following": getattr(self, "is_following_mouse", False),
            "falling": getattr(self, "is_falling", False),
            "gravity_falling": getattr(self, "is_gravity_falling", False),
            "recovering": getattr(self, "is_recovering", False),
            "jumping": getattr(self, "is_jumping", False),
            # 施法 / 游戏中：冻结整个自主代理
            "casting": getattr(self, "_spell_stage", None) is not None,
            "in_game": bool(getattr(self, "game_state", {}).get("is_playing")),
        }

    def _notify_arrived_if_needed(self):
        """到达 target_pos 后调用：通知自主代理；同时如果有躲猫猫移动阶段回调也触发。"""
        # 躲猫猫回调
        if getattr(self, '_hide_moving_cb', None) is not None and getattr(self, '_hide_stage', None) == getattr(self, '_hide_moving_cb_stage', None):
            cb = self._hide_moving_cb
            cb_stage = getattr(self, '_hide_moving_cb_stage', None)
            self._hide_moving_cb = None
            self._hide_moving_cb_stage = None
            try:
                _log.debug(f"[ARRIVE] 触发到达回调 stage={cb_stage} pos=({self.x()},{self.y()}) target=({self.target_pos.x()},{self.target_pos.y()})")
                cb()
                _log.debug(f"[ARRIVE] 回调执行完成 stage={cb_stage} 后 hide_stage={getattr(self, '_hide_stage', None)} spell_stage={getattr(self, '_spell_stage', None)}")
            except Exception as e:
                _log.warning(f"[ARRIVE] 回调异常 stage={cb_stage}: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
        # 自主代理通知
        try:
            if getattr(self, 'autonomous_agent', None) is not None:
                self.autonomous_agent.notify_arrived()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)

    def randomize_movement_pattern(self):
        # 随机化运动模式，使Ralsei能够合理地在屏幕上漫游
        # 不要一直动也别一直停，并且不要过于频繁的来回停或动，尽量符合Ralsei的性格
        # ===== 关键过程保护：施法 / 游戏 / 拖拽 中不改动当前移动规划 =====
        if getattr(self, '_spell_stage', None) is not None:
            return
        if getattr(self, 'game_state', {}).get('is_playing'):
            return
        if getattr(self, '_is_being_dragged', False):
            return
        if getattr(self, 'is_jumping', False) or getattr(self, 'is_falling', False) or getattr(self, 'is_gravity_falling', False):
            return
        
        # 保存当前位置作为移动的起始位置
        self.last_start_pos = self.pos()
        
        # Ralsei性格：温柔、害羞，动作轻柔，喜欢探索但不会过于激进
        current_time = time.time()
        
        # 获取当前主导情绪，根据情绪调整移动模式
        dominant_emotion, emotion_intensity = self.emotion_system.get_current_emotion()
        
        if hasattr(self, 'last_movement_end_time'):
            # 检查上次移动结束时间
            time_since_last_move = current_time - self.last_movement_end_time
            
            # 根据情绪调整移动概率
            if dominant_emotion == 'excited' or dominant_emotion == 'energetic':
                # 兴奋或精力充沛时更倾向于移动
                move_probability = 0.7
            elif dominant_emotion == 'shy' or dominant_emotion == 'peaceful':
                # 害羞或平静时更倾向于休息
                move_probability = 0.3
            elif dominant_emotion == 'curious':
                # 好奇时更倾向于探索移动
                move_probability = 0.6
            elif dominant_emotion == 'sad' or dominant_emotion == 'tired':
                # 悲伤或疲惫时更倾向于休息
                move_probability = 0.2
            else:
                # 其他情绪时的默认移动概率
                move_probability = 0.4
            
            # 根据概率决定是否继续移动
            if random.random() < move_probability or time_since_last_move < 1.0:
                # 修复：直接置 is_moving=True 而不生成新 target_pos，会导致宠物朝旧目标
                # （常为已到达位置）原地启停。generate_new_move_target() 内部会设新目标、
                # is_moving=True 并重置移动时长。
                self.generate_new_move_target()
            else:
                # 根据情绪调整休息时间
                if dominant_emotion == 'excited' or dominant_emotion == 'energetic':
                    # 兴奋时休息时间较短
                    self.max_idle_duration = random.uniform(3.0, 8.0)
                elif dominant_emotion == 'shy' or dominant_emotion == 'peaceful':
                    # 害羞或平静时休息时间较长
                    self.max_idle_duration = random.uniform(8.0, 20.0)
                elif dominant_emotion == 'curious':
                    # 好奇时休息时间适中
                    self.max_idle_duration = random.uniform(5.0, 12.0)
                elif dominant_emotion == 'sad' or dominant_emotion == 'tired':
                    # 悲伤或疲惫时休息时间较长
                    self.max_idle_duration = random.uniform(10.0, 25.0)
                else:
                    # 其他情绪时的默认休息时间
                    self.max_idle_duration = random.uniform(6.0, 15.0)
                # 确保在休息状态
                self.is_moving = False
        else:
            # 第一次移动，根据情绪调整起始行为
            if dominant_emotion == 'excited' or dominant_emotion == 'energetic':
                # 兴奋时更可能直接开始移动
                if random.random() < 0.6:
                    # 修复：见上方注释——必须生成新目标，否则原地踏步
                    self.generate_new_move_target()
                else:
                    self.is_moving = False
                    self.max_idle_duration = random.uniform(3.0, 8.0)
            elif dominant_emotion == 'shy' or dominant_emotion == 'peaceful':
                # 害羞或平静时更可能先休息
                if random.random() < 0.2:
                    # 修复：见上方注释
                    self.generate_new_move_target()
                else:
                    self.is_moving = False
                    self.max_idle_duration = random.uniform(8.0, 20.0)
            else:
                # 其他情绪时的默认起始行为
                if random.random() < 0.3:
                    # 修复：见上方注释
                    self.generate_new_move_target()
                else:
                    self.is_moving = False
                    self.max_idle_duration = random.uniform(6.0, 15.0)
        
    def generate_new_move_target(self):
        # 生成新的移动目标
        dominant_emotion, emotion_intensity = self.emotion_system.get_current_emotion()
        
        # 根据情绪调整移动时间
        if dominant_emotion == 'excited' or dominant_emotion == 'energetic':
            # 兴奋时移动时间更长
            self.max_moving_duration = random.uniform(5.0, 15.0)
        elif dominant_emotion == 'shy' or dominant_emotion == 'peaceful':
            # 害羞或平静时移动时间较短
            self.max_moving_duration = random.uniform(2.0, 8.0)
        elif dominant_emotion == 'curious':
            # 好奇时移动时间适中
            self.max_moving_duration = random.uniform(4.0, 12.0)
        elif dominant_emotion == 'sad' or dominant_emotion == 'tired':
            # 悲伤或疲惫时移动时间很短
            self.max_moving_duration = random.uniform(1.0, 5.0)
        else:
            # 其他情绪时的默认移动时间
            self.max_moving_duration = random.uniform(3.0, 10.0)
        
        # 调整移动速度，使动作更轻柔，符合Ralsei的性格
        # 根据情绪调整速度范围
        if dominant_emotion == 'excited' or dominant_emotion == 'energetic':
            # 兴奋或精力充沛时移动稍快
            self.speed = random.uniform(self.min_speed * 0.7, self.max_speed * 0.9)
        elif dominant_emotion == 'shy' or dominant_emotion == 'peaceful':
            # 害羞或平静时移动更慢
            self.speed = random.uniform(self.min_speed * 0.3, self.max_speed * 0.5)
        elif dominant_emotion == 'curious':
            # 好奇时移动速度适中，探索欲更强
            self.speed = random.uniform(self.min_speed * 0.5, self.max_speed * 0.7)
        elif dominant_emotion == 'sad' or dominant_emotion == 'tired':
            # 悲伤或疲惫时移动很慢
            self.speed = random.uniform(self.min_speed * 0.2, self.max_speed * 0.4)
        else:
            # 其他情绪时的默认速度
            self.speed = random.uniform(self.min_speed * 0.4, self.max_speed * 0.6)
        
        # 获取屏幕几何信息
        screen_geometry = QApplication.desktop().availableGeometry()
        sprite_size = int(50 * 2.0)  # 缩放因子为2.0，原始大小约50px
        current_pos = self.pos()
        
        # 计算当前方向，保持方向一致性，减少突然转向
        if hasattr(self, 'previous_direction'):
            # 根据情绪调整方向保持概率
            if dominant_emotion == 'excited' or dominant_emotion == 'energetic':
                # 兴奋时更可能改变方向，探索更多区域
                direction_keep_probability = 0.9
            elif dominant_emotion == 'shy' or dominant_emotion == 'peaceful':
                # 害羞或平静时更可能保持当前方向，移动更平稳
                direction_keep_probability = 0.995
            elif dominant_emotion == 'curious':
                # 好奇时偶尔改变方向，探索新事物
                direction_keep_probability = 0.95
            else:
                # 其他情绪时的默认方向保持概率
                direction_keep_probability = 0.99
            
            # 根据概率决定是否保持当前方向
            if random.random() < direction_keep_probability and self.previous_direction:
                direction = self.previous_direction
            else:
                direction = random.choice(['up', 'down', 'left', 'right'])
        else:
            direction = random.choice(['up', 'down', 'left', 'right'])
        
        # 根据情绪调整移动距离
        if dominant_emotion == 'excited' or dominant_emotion == 'energetic':
            # 兴奋时移动距离更远
            move_distance = random.randint(100, 300)
        elif dominant_emotion == 'shy' or dominant_emotion == 'peaceful':
            # 害羞或平静时移动距离较近
            move_distance = random.randint(50, 150)
        elif dominant_emotion == 'curious':
            # 好奇时移动距离适中
            move_distance = random.randint(80, 250)
        elif dominant_emotion == 'sad' or dominant_emotion == 'tired':
            # 悲伤或疲惫时移动距离很短
            move_distance = random.randint(30, 100)
        else:
            # 其他情绪时的默认移动距离
            move_distance = random.randint(80, 250)
        
        # 添加更多的横向移动，减少纵向移动，使Ralsei更多地在屏幕上水平探索
        if random.random() < 0.6:  # 60%的概率横向移动
            if direction in ['up', 'down']:
                direction = random.choice(['left', 'right'])
        
        # 生成目标位置，添加更多随机性和自然性
        if direction == 'up':
            # 添加横向偏移，使移动路径更自然
            target_x = current_pos.x() + random.randint(-40, 40)
            target_y = max(50, current_pos.y() - move_distance)
        elif direction == 'down':
            # 添加横向偏移，使移动路径更自然
            target_x = current_pos.x() + random.randint(-40, 40)
            target_y = min(screen_geometry.height() - sprite_size, current_pos.y() + move_distance)
        elif direction == 'left':
            # 添加纵向偏移，使移动路径更自然
            target_x = max(50, current_pos.x() - move_distance)
            target_y = current_pos.y() + random.randint(-40, 40)
        else:  # right
            # 添加纵向偏移，使移动路径更自然
            target_x = min(screen_geometry.width() - sprite_size, current_pos.x() + move_distance)
            target_y = current_pos.y() + random.randint(-40, 40)
        
        # 保存当前方向，用于下一次移动
        self.previous_direction = direction
        
        # 添加轻微的随机偏移，使移动更自然，但减少范围以避免不稳定
        final_offset_x = random.randint(-10, 10)
        final_offset_y = random.randint(-10, 10)
        
        target_x += final_offset_x
        target_y += final_offset_y
        
        # 确保在屏幕范围内
        target_x = max(50, min(target_x, screen_geometry.width() - sprite_size))
        target_y = max(50, min(target_y, screen_geometry.height() - sprite_size))
        
        self.target_pos = QPoint(target_x, target_y)
        
        # 简化移动参数，减少不必要的复杂性
        self.speed_fluctuation = 0.0
        self.fluctuation_speed = 0.005  # 降低波动速度，使移动更平稳
        self.stride_fluctuation = 0.0
        self.swing_speed = 0.005  # 降低摆动速度，使移动更优雅
        
        # 添加方向变化的平滑过渡参数，更平滑的方向变化
        self.direction_change_smoothness = random.uniform(0.1, 0.2)  # 更平滑的方向变化
        
        # 开始移动
        self.is_moving = True
        self.moving_duration = 0
        
    # 移动相关代码 - 更新移动逻辑
    @monitor_performance
    def update_movement(self):
        # 更新位置，改进运动逻辑，结合真实物理系统
        import math
        # 计算实际经过的时间
        current_time = time.time()
        elapsed_time = current_time - self.last_update_time
        self.last_update_time = current_time
        
        # 优化：减少环境和心情更新频率（每5秒更新一次）
        if hasattr(self, '_last_env_update'):
            if current_time - self._last_env_update > 5.0:
                self.update_environment()
                self.update_mood()
                self._last_env_update = current_time
        else:
            self.update_environment()
            self.update_mood()
            self._last_env_update = current_time
        
        # 低频检查附近的桌面元素（每3秒一次；修复：此前 check_nearby_desktop_elements
        # 从未被调用，Ralsei 对桌面文件夹/文件的"靠近反应"从未触发）
        # 修复：时间戳更新放在 try 外——原来在 try 内，若 check_* 抛错则时间戳不更新，
        # 每 30ms 全量重试（性能热循环）。
        try:
            if not hasattr(self, '_last_desktop_elem_check') or current_time - self._last_desktop_elem_check > 3.0:
                self.check_nearby_desktop_elements()
        except Exception as e:
            _log.warning(f"check_nearby_desktop_elements 异常: {e}")
        self._last_desktop_elem_check = current_time
        
        # 睡眠状态处理
        if self.is_sleeping:
            self.current_activity = "sleeping"
            # 检查是否有互动（优化：降低检查频率）
            if current_time - self.last_interaction_time < 1.0:
                self.wake_up()
            return
        
        # 检查是否需要进入睡眠模式
        if current_time - self.last_interaction_time > self.max_sleep_idle_duration:
            self.enter_sleep_mode()
            return
        
        # 自主代理状态机推进（在正常移动状态下工作，特殊状态会自动暂停）
        try:
            if getattr(self, 'autonomous_agent', None) is not None:
                self.autonomous_agent.tick(current_time)
        except Exception as e:
            _log.warning(f"自主代理tick异常: {e}")
        
        # 更新楼层信息 + 窗口移动跟随 / 关窗掉落（定期 1 秒；不依赖 is_moving）
        # 修复：原来 check_window_movement（含窗口移动→楼板跟随、窗口消失→坠落）只在
        # is_moving 分支内被调，Ralsei 静止时脚下窗口被移走/关闭会"悬空"数十秒才处理，
        # 违反建楼要求。这里统一节拍执行。
        if current_time - self.last_floor_check_time > self.floor_check_interval:
            try:
                self.check_window_movement()
            except Exception as e:
                _log.warning(f"check_window_movement 异常: {e}")
            self.last_floor_check_time = current_time
        
        # ===== 关键过程总开关：施法 / 躲猫猫 中 强制关闭鼠标跟随 / 拖拽跟随 / 拖拽玩耍 =====
        # 这些分支会直接 self.move(...) 然后 return，绕过 is_moving 正常移动和到达回调
        _in_critical = (getattr(self, '_spell_stage', None) is not None) or \
                       (getattr(self, 'game_state', {}).get('is_playing'))
        if _in_critical:
            if getattr(self, 'is_following_mouse', False):
                self.is_following_mouse = False
            if getattr(self, 'is_following_dragged_file', False):
                self.is_following_dragged_file = False
                self.dragged_file = None
            if getattr(self, 'is_dragging', False):
                self.is_dragging = False
            # 拖拽玩耍元素（注意拼写是 dragging_element 不是 dragged_element！）
            if getattr(self, 'dragging_element', None):
                self.dragging_element = None
                self.dragging_type = None

        # 特殊状态处理（跳跃、重力掉落、摔倒、恢复期）
        if self.is_jumping:
            self.current_activity = "jumping"
            self.handle_jump(elapsed_time, current_time)
            return
        elif self.is_gravity_falling:
            self.handle_gravity_fall(elapsed_time, current_time)
            return
        elif self.is_falling:
            self.handle_fall(elapsed_time, current_time)
            return
        elif hasattr(self, 'is_recovering') and self.is_recovering:
            # 恢复期状态，保持静止，继续处理摔倒恢复逻辑
            self.handle_fall(elapsed_time, current_time)
            return
        # ===== 拖拽保护：用户正按住/拖拽 Ralsei 时，完全停止自主移动驱动 =====
        # 修复：此前拖拽中 update_movement 仍向旧 target_pos 平移（抓不住/自己跑）。
        if getattr(self, '_is_being_dragged', False):
            self.current_speed_x = 0
            self.current_speed_y = 0
            return

        # 鼠标拖动处理
        if self.is_dragging_mouse:
            self.update_mouse_drag()
            return
        
        # 鼠标跟随处理
        if self.is_following_mouse:
            # 修复：追鼠标超过 20 秒自动停止（防止菜单/指令触发后永久追逐）
            _fs = getattr(self, '_follow_mouse_start', None)
            if _fs is not None and current_time - _fs > 20.0:
                self.stop_following_mouse(announce=True)
                # 停后这一帧不再继续追
            else:
                self._handle_mouse_follow(elapsed_time)
            return
        
        # 拖拽文件跟随处理
        if self.is_following_dragged_file and self.dragged_file:
            self.current_activity = "running"
            
            # 获取鼠标当前位置，假设拖拽文件时鼠标位置就是文件位置
            mouse_pos = QCursor.pos()
            current_pos = self.pos()
            
            # 计算到鼠标位置的距离
            dx = mouse_pos.x() - current_pos.x() - self.width() // 2
            dy = mouse_pos.y() - current_pos.y() - self.height() // 2
            
            distance_sq = dx * dx + dy * dy
            distance = math.sqrt(distance_sq) if distance_sq > 0 else 0
            
            if distance > 0:
                # 计算方向向量
                direction_x = dx / distance
                direction_y = dy / distance
                
                # 跟随拖拽文件时跑得更快
                follow_speed = self.speed * 1.5

                # 计算移动距离：speed 语义是"像素/帧"，直接用 follow_speed，不乘 elapsed_time
                # 否则在 60FPS 下会变成 follow_speed*16（约快16倍、且帧率相关），导致瞬移
                move_distance = min(distance, follow_speed)
                
                # 计算新位置
                new_x = int(current_pos.x() + direction_x * move_distance)
                new_y = int(current_pos.y() + direction_y * move_distance)
                
                # 确保在屏幕范围内
                screen_geom = QApplication.desktop().availableGeometry()
                new_x = max(0, min(new_x, screen_geom.width() - self.width()))
                new_y = max(0, min(new_y, screen_geom.height() - self.height()))
                
                # 移动Ralsei
                self.move(new_x, new_y)
                
                # 更新动画方向
                speed_magnitude = follow_speed
                angle = math.atan2(dy, dx) * 180 / math.pi
                
                # 根据角度范围确定方向
                if -45 <= angle < 45:
                    new_dir = "right"
                elif 45 <= angle < 135:
                    new_dir = "down"
                elif -135 <= angle < -45:
                    new_dir = "up"
                else:
                    new_dir = "left"
                
                if self.current_direction != new_dir and getattr(self, '_spell_stage', None) != 'casting':
                    self.current_direction = new_dir
                    self.change_animation(f"run_{new_dir}")
            
            # 检查是否离鼠标太远，如果太远就停止跟随
            if distance > 200:
                self.is_following_dragged_file = False
                self.dragged_file = None
                self.dialogue_ui.show_dialogue("跑得太快了，我跟不上了...")
            
            return
        
        # 主动拖动桌面元素或光标玩耍
        # 修复：原条件 `random()<0.005` 在 30ms 定时器每帧判定（≈每 6 秒一次），且不检查
        # 是否空闲/是否正被用户拖拽——走路中被它打断、用户拖动时鼠标被 SetCursorPos 抢走。
        # 改为：仅空闲时 + 距上次拖拽玩耍 >90 秒 + 无 spell/游戏/被拖拽。
        if (not self.is_moving
                and getattr(self, '_spell_stage', None) is None
                and not getattr(self, 'game_state', {}).get('is_playing')
                and not getattr(self, '_is_being_dragged', False)
                and time.time() - getattr(self, '_last_dragging_play_time', 0.0) > 90.0
                and random.random() < 0.002):
            self._last_dragging_play_time = time.time()
            self.start_dragging_play()
        
        # 处理正在拖动的桌面元素
        if hasattr(self, 'dragging_element') and self.dragging_element:
            # ===== 关键过程保护：施法 / 躲猫猫 中不执行拖拽玩耍（避免 self.move 瞬移）=====
            if getattr(self, '_spell_stage', None) is not None or getattr(self, 'game_state', {}).get('is_playing'):
                self.dragging_element = None
                self.dragging_type = None
            else:
                self.handle_dragging_play(elapsed_time, current_time)
        
        # 移动状态处理
        if self.is_moving:
            self.current_activity = "walking"
            self.moving_duration += elapsed_time
            
            current_pos = self.pos()
            dx = self.target_pos.x() - current_pos.x()
            dy = self.target_pos.y() - current_pos.y()
            
            # 优化：使用更高效的距离计算（避免math.hypot的开销）
            # 对于比较操作，使用平方距离避免开方运算
            distance_sq = dx * dx + dy * dy
            distance = math.sqrt(distance_sq) if distance_sq > 0 else 0
            
            # 优化：降低窗口检查频率
            if current_time - self.last_window_check_time > self.window_check_interval:
                # 注意：check_window_movement 已提升到 update_movement 顶部的 1 秒
                # 节拍执行（不依赖 is_moving），这里只做移动中的跳跃检测。
                self.check_nearby_windows(current_pos)
                self.last_window_check_time = current_time
            
            if distance > 0:
                # 计算方向向量
                direction_x = dx / distance
                direction_y = dy / distance
                
                # 优化：简化速度调整逻辑
                # 根据距离动态调整速度，使用更高效的分段函数
                if distance_sq > 10000:  # 100^2
                    target_move_speed = self.speed * 1.0
                elif distance_sq < 2500:  # 50^2
                    target_move_speed = self.speed * (distance / 50)
                else:
                    target_move_speed = self.speed * 0.8
                
                # 情绪影响（优化：缓存情绪因子）
                if not hasattr(self, '_cached_mood_factor') or current_time - getattr(self, '_last_mood_check', 0) > 2.0:
                    # 获取当前主导情绪
                    dominant_emotion, emotion_intensity = self.emotion_system.get_current_emotion()
                    
                    # 根据情绪系统中的主导情绪调整移动速度
                    if dominant_emotion == 'excited':
                        self._cached_mood_factor = 1.3
                    elif dominant_emotion == 'tired':
                        self._cached_mood_factor = 0.4
                    elif dominant_emotion == 'sad':
                        self._cached_mood_factor = 0.6
                    elif dominant_emotion == 'happy':
                        self._cached_mood_factor = 1.2
                    elif dominant_emotion == 'shy':
                        # 害羞时移动更慢，符合Ralsei的性格
                        self._cached_mood_factor = 0.5
                    elif dominant_emotion == 'curious':
                        # 好奇时移动稍快，探索欲更强
                        self._cached_mood_factor = 1.1
                    elif dominant_emotion == 'peaceful':
                        # 平静时移动较慢，更悠闲
                        self._cached_mood_factor = 0.7
                    elif dominant_emotion == 'energetic':
                        # 精力充沛时移动更快
                        self._cached_mood_factor = 1.4
                    elif dominant_emotion == 'anxious':
                        # 焦虑时移动更快，但更不稳定
                        self._cached_mood_factor = 1.2
                    else:
                        self._cached_mood_factor = 1.0
                    self._last_mood_check = current_time
                
                target_final_speed = target_move_speed * self._cached_mood_factor
                
                # 移除速度波动，避免抽搐
                if not hasattr(self, '_speed_variation'):
                    self._speed_variation = 1.0
                target_final_speed *= self._speed_variation
                
                # 平滑过渡到目标速度
                current_speed = math.hypot(self.current_speed_x, self.current_speed_y)
                new_speed = current_speed + (target_final_speed - current_speed) * 0.5
                
                # 优化：简化移动距离计算
                # speed 的语义是"像素/帧"，base_move_distance 直接用 new_speed（不乘 elapsed_time）
                # 60FPS 下 speed=6 → 每秒 360 像素的自然走路速度；乘 elapsed_time 会导致 0.1 像素 → 四舍五入为 0（太空滑步）
                max_move_distance = self.speed * 1.0
                base_move_distance = new_speed
                move_distance = min(distance, base_move_distance, max_move_distance)
                
                # 计算新位置，使用浮点数计算以提高精度
                new_x = current_pos.x() + direction_x * move_distance
                new_y = current_pos.y() + direction_y * move_distance
                # 四舍五入到整数，避免坐标跳动
                new_x = int(round(new_x))
                new_y = int(round(new_y))
                
                # 优化：缓存屏幕几何信息
                # 修复（参考小鲸鱼 widget 的"始终夹在可视区"）：用多屏虚拟矩形而非主屏，
                # 否则副屏（右侧/左侧负坐标）目标永远走不到、且会被每帧 clamp 拉回主屏抖动。
                if not hasattr(self, '_cached_screen_geom') or current_time - getattr(self, '_last_screen_check', 0) > 3.0:
                    self._cached_screen_geom = self._virtual_screen_rect()
                    self._last_screen_check = current_time
                
                screen_geom = self._cached_screen_geom
                new_x = max(screen_geom.left(), min(new_x, screen_geom.right() - self.width()))
                new_y = max(screen_geom.top(), min(new_y, screen_geom.bottom() - self.height()))
                
                # 计算实际移动向量
                actual_dx = new_x - current_pos.x()
                actual_dy = new_y - current_pos.y()
                actual_distance = math.hypot(actual_dx, actual_dy) if actual_dx != 0 or actual_dy != 0 else 1.0
                
                # 更新速度向量，使其与实际移动方向一致
                if actual_distance > 0:
                    self.current_speed_x = (actual_dx / actual_distance) * new_speed
                    self.current_speed_y = (actual_dy / actual_distance) * new_speed
                
                # 移动Ralsei
                self.move(new_x, new_y)
                
                # 优化：使用速度向量来确定动画方向，确保方向一致
                # 基于当前速度向量决定动画方向，确保动画方向与实际移动方向一致
                speed_magnitude = math.hypot(self.current_speed_x, self.current_speed_y)
                
                # 如果有移动速度，根据速度方向决定动画方向
                if speed_magnitude > 1.0:  # 增加速度阈值，避免微小速度变化导致方向频繁切换
                    # 使用速度向量的角度来确定方向，确保方向精确
                    import math
                    angle = math.atan2(self.current_speed_y, self.current_speed_x) * 180 / math.pi
                    
                    # 根据角度范围确定方向，增加角度范围以减少方向频繁变化
                    if -30 <= angle < 30:
                        new_dir = "right"
                    elif 60 <= angle < 120:
                        new_dir = "down"
                    elif -120 <= angle < -60:
                        new_dir = "up"
                    else:  # 120 <= angle < 180 或 -180 <= angle < -120
                        new_dir = "left"
                    
                    # 只有当方向确实改变时才切换动画，增加方向变化的稳定性
                    # 修复：spell 阶段（walking/casting）不在此切换动画——方向动画统一由
                    # _tick_spell_flow 按"位移方向"控制。否则 update_movement(30ms) 用"速度角度"
                    # 强制切换、_tick_spell_flow(167ms) 用"位移方向"强制切换，两个方向算法不同
                    # （30°/60° 角度阈值 vs 纵横距离比较），斜向移动时交替强制切换 walk 方向 → 抽搐。
                    if self.current_direction != new_dir and getattr(self, '_spell_stage', None) is None:
                        # 添加方向变化的平滑过渡，避免突然转向
                        self.current_direction = new_dir
                        # 根据速度大小决定是走还是跑
                        anim_type = "run" if speed_magnitude > self.speed * 1.5 else "walk"
                        # 强制切换动画，确保方向变化正确反映
                        self.change_animation(f"{anim_type}_{new_dir}", force=True)
            
            # 优化：使用平方距离进行比较，避免开方运算
            # 到达阈值放大：speed*3 或至少30px（游戏/施法的移动容忍更大）
            _threshold_sq = max((self.speed * 3.0) ** 2, 30.0 ** 2)
            if distance_sq <= _threshold_sq:
                # 到达目标位置，直接停止移动，避免速度波动
                self.is_moving = False
                self.idle_timer = 0
                self.max_idle_duration = random.uniform(2.0, 5.0)  # 休息2-5秒
                # 记录上次移动结束时间
                self.last_movement_end_time = time.time()
                # 重置速度
                self.current_speed_x = 0
                self.current_speed_y = 0
                # ===== 只有【非躲猫猫/施法关键移动】时才切 idle =====
                _critical_move = False
                if getattr(self, '_spell_stage', None) in ('walking',):
                    _critical_move = True
                _hs = getattr(self, '_hide_stage', None)
                if _hs in ('moving_to_center', 'moving_to_folder'):
                    _critical_move = True
                if not _critical_move:
                    # 切换回空闲动画
                    # 修复：必须 force=True——walk/run 优先级(2)高于 idle(1)，
                    # 不带 force 会被 change_animation 的优先级拦截拒绝，
                    # 导致宠物停在走路姿势但实际不动（"走着走着突然定住"）。
                    if self.current_animation.startswith("walk_") or self.current_animation.startswith("run_"):
                        self.change_animation("idle", force=True)
                # —— 到达回调：通知躲猫猫 / 自主代理 ——
                self._notify_arrived_if_needed()
        else:
            # 空闲状态，随机化移动模式
            self.idle_timer += elapsed_time
            if self.idle_timer >= self.max_idle_duration:
                # ===== Spell / 躲猫猫 / 拖拽等关键过程：禁止随机启动移动 =====
                if getattr(self, '_spell_stage', None) is not None:
                    self.idle_timer = 0
                    self.max_idle_duration = random.uniform(1.0, 2.0)
                elif getattr(self, '_is_being_dragged', False) or getattr(self, 'is_jumping', False) or getattr(self, 'is_falling', False):
                    self.idle_timer = 0
                    self.max_idle_duration = random.uniform(1.0, 2.0)
                elif getattr(self, 'game_state', {}).get('is_playing'):
                    self.idle_timer = 0
                    self.max_idle_duration = random.uniform(1.0, 2.0)
                else:
                    # 修复：休息到期后让 randomize_movement_pattern 按情绪决定走或再休息。
                    # randomize 内部"走"分支会调用 generate_new_move_target() 生成新目标
                    # （不再朝旧目标原地踏步）；"休息"分支会设置新的 max_idle_duration。
                    # 不再在外层强制 is_moving=True（否则会覆盖休息决策、走向旧目标）。
                    self.randomize_movement_pattern()
                    self.idle_timer = 0
                
    def _handle_mouse_follow(self, elapsed_time):
        # 优化：提取鼠标跟随逻辑到单独方法
        import math
        
        mouse_pos = QCursor.pos()
        ralsei_center = self.pos() + QPoint(self.width() // 2, self.height() // 2)
        
        dx = mouse_pos.x() - ralsei_center.x()
        dy = mouse_pos.y() - ralsei_center.y()
        distance_sq = dx * dx + dy * dy
        
        # 使用平方距离比较，避免开方运算
        if distance_sq > self.mouse_follow_distance ** 2:
            distance = math.sqrt(distance_sq)
            direction_x = dx / distance
            direction_y = dy / distance
            
            # 应用物理：加速度，减少加速度以避免突然的速度变化
            self.acceleration_x = direction_x * 300.0  # 减少加速度
            self.acceleration_y = direction_y * 300.0  # 减少加速度
            
            # 更新速度
            self.current_speed_x += self.acceleration_x * elapsed_time
            self.current_speed_y += self.acceleration_y * elapsed_time
            
            # 应用阻力，增加阻力以实现更平滑的减速
            self.current_speed_x *= self.air_resistance * 0.98  # 增加阻力
            self.current_speed_y *= self.air_resistance * 0.98  # 增加阻力
            self.current_speed_x *= self.friction
            self.current_speed_y *= self.friction
            
            # 限制最大速度，降低最大速度以避免过快移动
            max_speed = 15.0  # 降低最大速度
            speed_magnitude = math.hypot(self.current_speed_x, self.current_speed_y)
            if speed_magnitude > max_speed:
                scale = max_speed / speed_magnitude
                self.current_speed_x *= scale
                self.current_speed_y *= scale
            
            # 计算新位置，使用平滑移动
            new_x = int(self.pos().x() + self.current_speed_x * 0.8)  # 平滑移动
            new_y = int(self.pos().y() + self.current_speed_y * 0.8)  # 平滑移动
            
            # 使用缓存的屏幕几何信息（多屏虚拟矩形 clamp）
            if hasattr(self, '_cached_screen_geom'):
                screen_geom = self._cached_screen_geom
                new_x = max(screen_geom.left(), min(new_x, screen_geom.right() - self.width()))
                new_y = max(screen_geom.top(), min(new_y, screen_geom.bottom() - self.height()))
                self.move(new_x, new_y)
            
            # 调整方向和动画，增加方向变化的稳定性
            if abs(dx) > abs(dy):
                new_dir = "right" if dx > 0 else "left"
            else:
                new_dir = "down" if dy > 0 else "up"
            
            # 只有当方向确实改变时才切换动画，增加方向变化的稳定性
            if self.current_direction != new_dir and getattr(self, '_spell_stage', None) != 'casting':
                self.current_direction = new_dir
                # 游戏中用 walk 代替 run（run 会被 change_animation 拦截，但这里直接用 walk 更清晰）
                if getattr(self, 'game_state', {}).get('is_playing'):
                    self.change_animation(f"walk_{new_dir}", force=True)
                else:
                    self.change_animation(f"run_{new_dir}", force=True)
        else:
            # 停止跟随，逐渐减速，增加减速效果以实现更平滑的停止
            self.current_speed_x *= self.friction * 0.95  # 增加减速效果
            self.current_speed_y *= self.friction * 0.95  # 增加减速效果
    
    def check_nearby_desktop_elements(self):
        # 检查附近的桌面元素并做出反应
        current_pos = self.pos()
        nearby_elements = self.desktop_interaction.get_nearby_elements(current_pos, 80)
        
        if nearby_elements:
            # 对最近的元素做出反应
            nearest_element = nearby_elements[0]
            self.react_to_desktop_element(nearest_element)
    
    def check_desktop_element_at_target(self):
        # 检查目标位置是否有桌面元素
        current_pos = self.target_pos
        nearby_elements = self.desktop_interaction.get_nearby_elements(current_pos, 50)
        
        if nearby_elements:
            # 对找到的元素做出反应
            for element in nearby_elements:
                self.react_to_desktop_element(element)
    
    def initiate_auto_mouse_drag(self):
        # 主动发起鼠标拖动
        import random
        # 15%概率发起主动拖动，符合Ralsei害羞的性格
        if random.random() < 0.15:
            # 随机选择一个目标位置
            screen_geometry = QApplication.desktop().availableGeometry()
            target_x = random.randint(100, screen_geometry.width() - 100)
            target_y = random.randint(100, screen_geometry.height() - 100)
            
            # 开始拖动鼠标
            self.start_mouse_drag(QPoint(target_x, target_y))
    
    def start_mouse_drag(self, target_pos):
        # 开始拖动鼠标
        self.is_dragging_mouse = True
        self.drag_start_pos = QCursor.pos()
        self.drag_target_pos = target_pos
        self.drag_start_time = time.time()
        
        # 显示对话
        self.dialogue_ui.add_dialogue("ralsei", "我来帮你拖动鼠标吧！", "playful")
        self.dialogue_ui.show_dialogue()
        
        # 播放动画
        self.play_animation_once("act")
        
        # 启动拖动定时器：按 ~60FPS 推进，直到 update_mouse_drag 判定时间到后自行停止
        self.mouse_drag_timer.start(16)
    
    def update_mouse_drag(self):
        # 更新鼠标拖动位置
        if not self.is_dragging_mouse:
            return

        # 防御：stop_mouse_drag 可能在另一处将 pos 清空为 None
        if self.drag_start_pos is None or self.drag_target_pos is None or self.drag_start_time is None:
            self.is_dragging_mouse = False
            return

        current_time = time.time()
        elapsed = current_time - self.drag_start_time
        
        if elapsed >= self.drag_duration:
            # 拖动结束
            self.stop_mouse_drag()
            return
        
        # 计算拖动进度
        progress = elapsed / self.drag_duration
        
        # 使用缓动函数使拖动更自然
        import math
        eased_progress = 1 - math.pow(1 - progress, 3)  # 缓出效果
        
        # 计算当前位置
        dx = self.drag_target_pos.x() - self.drag_start_pos.x()
        dy = self.drag_target_pos.y() - self.drag_start_pos.y()
        
        current_x = int(self.drag_start_pos.x() + dx * eased_progress)
        current_y = int(self.drag_start_pos.y() + dy * eased_progress)
        
        # 移动鼠标
        # 修复：本函数作用域内从未 import win32api（只有 2868/7597 行各自 import 过），
        # 这里必然抛 NameError 并被下方 except 静默吞掉 → "帮你拖动鼠标"功能从未真正生效。
        # 现在补上导入，并用 QCursor 作为 win32 不可用时的兜底。
        try:
            import win32api
            win32api.SetCursorPos((current_x, current_y))
        except Exception as e:
            _log.debug("win32api 移动光标失败，改用 QCursor: %s", e)
            try:
                QCursor.setPos(int(current_x), int(current_y))
            except Exception as e2:
                _log.debug("QCursor 移动光标也失败: %s", e2)
    
    def stop_mouse_drag(self):
        # 停止拖动鼠标
        # 修复：改为周期定时器后必须显式停止，否则会以 16ms 空转
        try:
            self.mouse_drag_timer.stop()
        except Exception as e:
            _log.debug("停止鼠标拖动定时器失败: %s", e)
        self.is_dragging_mouse = False
        self.drag_start_pos = None
        self.drag_target_pos = None
        self.drag_start_time = None
        
        # 显示对话
        self.dialogue_ui.add_dialogue("ralsei", "拖动完成啦！", "happy")
        self.dialogue_ui.show_dialogue()
        
        # 播放动画
        self.play_animation_once("wave")
    
    def check_api_commands(self):
        """检查并执行来自API的命令"""
        try:
            # 获取当前状态
            current_status = self.command_manager.get_status()
            
            # 向API请求命令
            api_response = self.api_client.get_commands(current_status)
            if not api_response:
                return
            
            # 解析API响应
            commands = api_response.get('commands', [])
            if not isinstance(commands, list):
                commands = [commands]  # 处理单个命令的情况
            
            # 执行所有命令
            # 修复：原来 send_status 里又对同一批 commands 全部执行一次（列表推导），
            # 有副作用的命令（打开文件/移动鼠标等）被重复触发。这里保存第一次执行结果并复用。
            results = []
            for command in commands:
                result = self.command_manager.execute_command(command)
                results.append(result)
                # 可以根据需要处理执行结果
                _log.debug(f"API命令执行结果: {result}")
            
            # 发送执行结果回API
            self.api_client.send_status({
                'current_status': current_status,
                'last_command_results': results
            })
        except Exception as e:
            _log.warning(f"API命令处理错误: {e}")
    
    # 鼠标事件处理
    
    
    

    def check_nearby_windows(self, current_pos):
        # 检查附近的窗口，判断是否需要跳跃
        # 如果已经在跳跃中，不再检测跳跃
        if self.is_jumping:
            return
        
        # ===== 关键过程保护：施法 / 躲猫猫 中 跳过窗口跳跃检测 =====
        if getattr(self, '_spell_stage', None) is not None:
            return
        if getattr(self, 'game_state', {}).get('is_playing'):
            return
        
        # 检查跳跃疲劳
        current_time = time.time()
        
        # 检查是否需要休息
        if self.needs_rest:
            # 检查休息是否完成
            if current_time - self.last_jump_time > self.rest_duration:
                # 休息完成，重置跳跃状态
                self.needs_rest = False
                self.jump_count = 0
                self.resting_time = 0
            else:
                # 继续休息
                return
        
        # 增加跳跃冷却时间，从默认的跳跃冷却时间基础上增加1秒
        jump_cooldown = max(self.jump_cooldown, 1.5)
        
        # 检查是否在跳跃冷却期
        if current_time - self.last_jump_time < jump_cooldown:
            return
        
        windows = self.desktop_interaction.get_all_visible_windows()
        
        # 计算Ralsei的矩形
        ralsei_rect = QRect(current_pos.x(), current_pos.y(), self.width(), self.height())
        
        # 计算当前位置到各窗口边缘的距离，对每个窗口的边缘都能跳跃
        nearby_windows = []
        jump_to_desktop = False
        jump_desktop_edge = ""
        
        # 情况1: Ralsei在窗口上，检查是否可以跳到桌面
        if self.current_window:
            # 获取当前窗口的矩形
            current_window_rect = QRect(
                self.current_window['x'], 
                self.current_window['y'], 
                self.current_window['width'], 
                self.current_window['height']
            )
            
            # 计算Ralsei在窗口内的相对位置
            relative_center_x = ralsei_rect.center().x() - current_window_rect.left()
            relative_center_y = ralsei_rect.center().y() - current_window_rect.top()
            
            # 检查Ralsei是否在当前窗口的边缘，准备跳到桌面
            # 增加更严格的边缘检测条件，避免频繁跳到桌面
            edge_threshold = 20  # 距离边缘的阈值
            
            # 检查窗口底部边缘
            if (ralsei_rect.bottom() >= current_window_rect.bottom() - 5 and 
                ralsei_rect.bottom() <= current_window_rect.bottom() + 5 and
                # 确保Ralsei非常靠近边缘，并且在窗口边缘的中心区域
                relative_center_x > current_window_rect.width() * 0.2 and 
                relative_center_x < current_window_rect.width() * 0.8):
                # 在窗口底部边缘，可以跳到下方桌面
                jump_to_desktop = True
                jump_desktop_edge = "down"
                # 计算跳跃目标位置
                desktop_edge = current_window_rect.bottom() + 20
                target_x = ralsei_rect.center().x() - self.width() // 2
                self.jump_target_pos = QPoint(target_x, desktop_edge)
            # 检查窗口右侧边缘
            elif (ralsei_rect.right() >= current_window_rect.right() - 5 and 
                  ralsei_rect.right() <= current_window_rect.right() + 5 and
                  # 确保Ralsei非常靠近边缘，并且在窗口边缘的中心区域
                  relative_center_y > current_window_rect.height() * 0.2 and 
                  relative_center_y < current_window_rect.height() * 0.8):
                # 在窗口右侧边缘，可以跳到右侧桌面
                jump_to_desktop = True
                jump_desktop_edge = "right"
                # 计算跳跃目标位置
                desktop_edge = current_window_rect.right() + 20
                target_y = ralsei_rect.center().y() - self.height() // 2
                self.jump_target_pos = QPoint(desktop_edge, target_y)
            # 检查窗口左侧边缘
            elif (ralsei_rect.left() >= current_window_rect.left() - 5 and 
                  ralsei_rect.left() <= current_window_rect.left() + 5 and
                  # 确保Ralsei非常靠近边缘，并且在窗口边缘的中心区域
                  relative_center_y > current_window_rect.height() * 0.2 and 
                  relative_center_y < current_window_rect.height() * 0.8):
                # 在窗口左侧边缘，可以跳到左侧桌面
                jump_to_desktop = True
                jump_desktop_edge = "left"
                # 计算跳跃目标位置
                desktop_edge = current_window_rect.left() - 20
                target_y = ralsei_rect.center().y() - self.height() // 2
                self.jump_target_pos = QPoint(desktop_edge, target_y)
            # 检查窗口顶部边缘
            elif (ralsei_rect.top() >= current_window_rect.top() - 5 and 
                  ralsei_rect.top() <= current_window_rect.top() + 5 and
                  # 确保Ralsei非常靠近边缘，并且在窗口边缘的中心区域
                  relative_center_x > current_window_rect.width() * 0.2 and 
                  relative_center_x < current_window_rect.width() * 0.8):
                # 在窗口顶部边缘，可以跳到上方桌面
                jump_to_desktop = True
                jump_desktop_edge = "up"
                # 计算跳跃目标位置
                desktop_edge = current_window_rect.top() - 20
                target_x = ralsei_rect.center().x() - self.width() // 2
                self.jump_target_pos = QPoint(target_x, desktop_edge)

        
        # 情况2: Ralsei在桌面或其他位置，检查是否可以跳到其他窗口
        if not jump_to_desktop:
            if windows:
                for window in windows:
                    # 获取当前Ralsei的层级
                    current_level = self.current_window['z_order'] if self.current_window else float('inf')
                    
                    # 视野限制：只考虑当前层级或更高层级的窗口（z_order更小表示层级更高）
                    if window['z_order'] > current_level:
                        continue
                    
                    # 计算窗口的边缘位置
                    window_rect = QRect(window['x'], window['y'], window['width'], window['height'])
                    
                    # 跳过当前所在的窗口，避免在同一窗口上跳跃
                    if self.current_window and window['hwnd'] == self.current_window['hwnd']:
                        continue
                    
                    # 检查Ralsei是否在窗口边缘附近，增加更严格的距离限制，避免频繁触发跳跃
                    # 情况1: Ralsei在窗口下方，准备跳上窗口顶部
                    if (ralsei_rect.bottom() >= window_rect.top() - 50 and 
                        ralsei_rect.bottom() <= window_rect.top() + 15 and 
                        ralsei_rect.center().x() > window_rect.left() + 50 and
                        ralsei_rect.center().x() < window_rect.right() - 50):
                        # 在窗口下方，且中心在窗口内容区域内，可以跳上窗口顶部
                        # 计算到窗口顶部边缘的垂直距离
                        vertical_distance = abs(window_rect.top() - ralsei_rect.bottom())
                        # 增加最小距离限制，避免太靠近时频繁触发
                        if vertical_distance > 10 and vertical_distance < 30:
                            nearby_windows.append((vertical_distance, window, "bottom"))
                    
                    # 情况2: Ralsei在窗口左侧，准备跳上窗口左侧边缘
                    elif (ralsei_rect.right() >= window_rect.left() - 50 and 
                          ralsei_rect.right() <= window_rect.left() + 15 and 
                          ralsei_rect.center().y() > window_rect.top() + 50 and
                          ralsei_rect.center().y() < window_rect.bottom() - 50):
                        # 在窗口左侧，且中心在窗口内容区域内，可以跳上窗口左侧边缘
                        # 计算到窗口左侧边缘的水平距离
                        horizontal_distance = abs(window_rect.left() - ralsei_rect.right())
                        if horizontal_distance > 10 and horizontal_distance < 30:
                            nearby_windows.append((horizontal_distance, window, "left"))
                    
                    # 情况3: Ralsei在窗口右侧，准备跳上窗口右侧边缘
                    elif (ralsei_rect.left() >= window_rect.right() - 50 and 
                          ralsei_rect.left() <= window_rect.right() + 15 and 
                          ralsei_rect.center().y() > window_rect.top() + 50 and
                          ralsei_rect.center().y() < window_rect.bottom() - 50):
                        # 在窗口右侧，且中心在窗口内容区域内，可以跳上窗口右侧边缘
                        # 计算到窗口右侧边缘的水平距离
                        horizontal_distance = abs(window_rect.right() - ralsei_rect.left())
                        if horizontal_distance > 10 and horizontal_distance < 30:
                            nearby_windows.append((horizontal_distance, window, "right"))
                    
                    # 情况4: Ralsei在窗口上方，准备跳上窗口底部
                    elif (ralsei_rect.top() <= window_rect.bottom() + 15 and 
                          ralsei_rect.top() >= window_rect.bottom() - 50 and 
                          ralsei_rect.center().x() > window_rect.left() + 50 and
                          ralsei_rect.center().x() < window_rect.right() - 50):
                        # 在窗口上方，且中心在窗口内容区域内，可以跳上窗口底部
                        # 计算到窗口底部边缘的垂直距离
                        vertical_distance = abs(window_rect.bottom() - ralsei_rect.top())
                        if vertical_distance > 10 and vertical_distance < 30:
                            nearby_windows.append((vertical_distance, window, "top"))
                
                # 按距离排序
                nearby_windows.sort(key=lambda x: x[0])
        
        if jump_to_desktop:
            # 跳到桌面
            self.start_jump(None, jump_desktop_edge)
        elif nearby_windows:
            # 选择最近的窗口
            closest_window = nearby_windows[0][1]
            window_edge = nearby_windows[0][2]
            self.start_jump(closest_window, window_edge)

    def start_jump(self, target_window, window_edge):
        # 开始跳跃
        self.is_jumping = True
        self.jump_start_time = time.time()
        self.jump_start_pos = self.pos()
        self.jump_target_window = target_window
        
        # 记录跳跃开始时的空间坐标
        self.jump_start_spatial = self.spatial_pos.copy()
        
        # 添加跳跃日志，记录起跳坐标和目标窗口
        start_pos_str = f"({self.jump_start_pos.x()}, {self.jump_start_pos.y()})"
        start_on_window = "窗口上" if self.current_window else "桌面上"
        target_info = f"窗口[{target_window['title'] if target_window else '桌面'}]"
        _log.debug(f"起跳: {start_pos_str}, 位置: {start_on_window}, 目标: {target_info}")
        
        # 计算目标平台的Z坐标
        self.jump_target_z = 0
        if target_window:
            # 跳上窗口，使用窗口的platform_height作为目标Z坐标
            self.jump_target_z = target_window['platform_height']
        else:
            # 跳到桌面，Z坐标为0
            self.jump_target_z = 0
        
        # 计算跳跃的Z轴高度差
        self.jump_z_diff = self.jump_target_z - self.jump_start_spatial['z']
        
        # 设置目标楼层，用于跳跃过程中的穿透检查
        self.jump_target_floor = None
        if target_window:
            # 查找目标窗口对应的楼层
            self.jump_target_floor = self.floor_manager.get_floor_by_window(target_window['hwnd'])
        else:
            # 跳到桌面，目标楼层为桌面
            self.jump_target_floor = self.floor_manager.desktop_floor
        
        # 开始跳跃准备阶段
        self.jump_phase = "ready"
        # 强制切换到准备跳跃动画
        self.change_animation("jump_ready", force=True)
        
        # 更新跳跃时间
        self.last_jump_time = time.time()
        
        # 调整跳跃次数和休息逻辑
        # 当返回较低平台时，减少跳跃次数计数
        if self.current_window and target_window:
            if target_window['z_order'] < self.current_window['z_order']:
                # 返回较低平台，减少跳跃次数
                self.jump_count = max(0, self.jump_count - 1)
            else:
                # 跳上更高平台，增加跳跃次数
                self.jump_count += 1
        else:
            # 从平台跳到桌面或从桌面跳到平台，增加跳跃次数
            self.jump_count += 1
        
        # 确保跳跃次数不会超过最大值
        self.jump_count = min(self.jump_count, self.max_jumps)
        
        # 检查是否需要休息
        if self.jump_count >= self.max_jumps:
            self.needs_rest = True
        else:
            # 如果跳跃次数减少到阈值以下，取消休息需求
            self.needs_rest = False
        
        # 计算跳跃目标位置，确保准确跳上窗口或桌面，避免在空中
        if target_window:
            window_rect = QRect(target_window['x'], target_window['y'], target_window['width'], target_window['height'])
            
            # 计算跳跃方向和距离，确保Ralsei被放置在窗口的内容区域
            title_bar_height = 30  # 估计的窗口标题栏高度，确保Ralsei被放置在内容区域
            
            if window_edge == "bottom":
                # 从下方跳上窗口顶部
                target_x = window_rect.center().x() - self.width() // 2
                # 确保x坐标在窗口范围内
                target_x = max(window_rect.left() + 20, min(window_rect.right() - self.width() - 20, target_x))
                # 确保y坐标在窗口内容区域，考虑标题栏高度
                target_y = window_rect.top() + title_bar_height + 10
            elif window_edge == "left":
                # 从左侧跳上窗口左侧
                target_y = window_rect.center().y() - self.height() // 2
                # 确保y坐标在窗口内容区域，考虑标题栏高度
                target_y = max(window_rect.top() + title_bar_height + 20, min(window_rect.bottom() - self.height() - 20, target_y))
                target_x = window_rect.left() + 10
            elif window_edge == "right":
                # 从右侧跳上窗口右侧
                target_y = window_rect.center().y() - self.height() // 2
                # 确保y坐标在窗口内容区域，考虑标题栏高度
                target_y = max(window_rect.top() + title_bar_height + 20, min(window_rect.bottom() - self.height() - 20, target_y))
                target_x = window_rect.right() - self.width() - 10
            elif window_edge == "top":
                # 从上方跳上窗口底部
                target_x = window_rect.center().x() - self.width() // 2
                # 确保x坐标在窗口范围内
                target_x = max(window_rect.left() + 20, min(window_rect.right() - self.width() - 20, target_x))
                target_y = window_rect.bottom() - self.height() - 10
            else:
                # 默认情况：直接跳上窗口中心附近
                target_x = window_rect.center().x() - self.width() // 2
                # 确保x坐标在窗口范围内
                target_x = max(window_rect.left() + 20, min(window_rect.right() - self.width() - 20, target_x))
                # 确保y坐标在窗口内容区域，考虑标题栏高度
                target_y = window_rect.center().y() - self.height() // 2 + title_bar_height
                target_y = max(window_rect.top() + title_bar_height + 20, min(window_rect.bottom() - self.height() - 20, target_y))
        else:
            # 跳到桌面，计算目标位置
            desktop_edge = window_edge
            screen_geometry = QApplication.desktop().availableGeometry()
            
            # 从窗口边缘跳到桌面，计算合适的着陆位置
            # 修复：check_nearby_windows 对"窗口顶部边缘"设置 jump_desktop_edge="up"，
            # 这里原来只匹配 "top"，导致从窗口顶跳回桌面落入 else 直接瞬移到屏幕底部。
            if desktop_edge in ("top", "up"):
                # 从窗口顶部跳到桌面下方
                target_x = self.jump_start_pos.x()
                # 确保x坐标在屏幕范围内
                target_x = max(20, min(screen_geometry.width() - self.width() - 20, target_x))
                target_y = self.jump_start_pos.y() + 50  # 从窗口顶部往下跳50像素，减少瞬移效果
            elif desktop_edge == "left" or desktop_edge == "right":
                # 从窗口侧面跳到桌面
                target_x = self.jump_start_pos.x()
                target_y = self.jump_start_pos.y()
            elif desktop_edge == "down":
                # 修复：从窗口底边跳回桌面——原代码把 "down" 落入 else 算到屏幕最底部，
                # 造成"在窗口底边起跳却落到屏幕底"的跨屏远跳。这里落在窗口下方一小段。
                target_x = self.jump_start_pos.x()
                target_x = max(20, min(screen_geometry.width() - self.width() - 20, target_x))
                target_y = self.jump_start_pos.y() + 50
            else:
                # 默认情况：从窗口下方跳到桌面
                target_x = self.jump_start_pos.x()
                target_y = screen_geometry.bottom() - self.height() - 20  # 桌面底部上方
        
        # 确保目标位置在屏幕范围内
        screen_geometry = QApplication.desktop().availableGeometry()
        target_x = max(20, min(screen_geometry.width() - self.width() - 20, target_x))
        target_y = max(20, min(screen_geometry.height() - self.height() - 20, target_y))
        
        # 更新跳跃目标位置
        self.jump_target_pos = QPoint(target_x, target_y)

    def start_falling(self, fall_velocity=0, is_thrown=False):
        # 开始重力掉落，实现"建楼"要求：没有支撑，就必须往下掉
        # ===== 关键过程保护：施法 / 躲猫猫 / 拖拽中，跳过重力掉落 =====
        if getattr(self, '_spell_stage', None) is not None:
            return
        if getattr(self, 'game_state', {}).get('is_playing'):
            return
        if getattr(self, '_is_being_dragged', False) or getattr(self, 'is_jumping', False):
            return
        self.is_gravity_falling = True
        self.fall_speed = 0.0  # 初始掉落速度为0
        self.fall_start_time = time.time()
        self.fall_start_pos = self.pos()
        self._fall_velocity = fall_velocity  # 记录摔落时的速度（用于判断是否甩飞）
        self._is_thrown = is_thrown  # 是否是被甩飞的
        # 水平惯性：掉落时保留当前水平速度，形成2D抛物线坠落
        self.fall_velocity_x = self.current_speed_x * 0.5
        
        # 根据摔落速度选择不同的动画
        if fall_velocity > 100 or is_thrown:
            # 高速摔落或被甩飞时，使用splat动画
            self.change_animation("fall", force=True)
            # 设置较长的动画持续时间，至少3秒
            self.max_fall_duration = 3.0
        else:
            # 普通摔落时，使用常规掉落动画
            self.change_animation("fall", force=True)
            # 常规摔落动画持续时间
            self.max_fall_duration = 2.0
        
        _log.debug(f"开始重力掉落，起始位置: {self.fall_start_pos}, 摔落速度: {fall_velocity}, 是否甩飞: {is_thrown}")
        
    def _is_falling_through_window(self, current_rect, new_rect, window_rect):
        # 检查Ralsei是否会穿过某个窗口
        # 这是一个简单的碰撞检测，检查从当前位置到新位置的路径是否与窗口相交
        
        # 检查当前位置是否已经在窗口上
        if window_rect.intersects(current_rect):
            return False
        
        # 检查新位置是否与窗口相交
        if window_rect.intersects(new_rect):
            return True
        
        # 检查从当前位置到新位置的线段是否与窗口相交
        # 简化处理：如果窗口在当前位置和新位置之间，就认为会相交
        if (current_rect.bottom() <= window_rect.top() and 
            new_rect.bottom() >= window_rect.top()):
            # 检查水平方向是否重叠
            if (current_rect.right() >= window_rect.left() and 
                current_rect.left() <= window_rect.right()):
                return True
        
        return False
    
    def handle_jump(self, elapsed_time, current_time):
        # 处理跳跃逻辑
        # 根据建楼要求：ralsei在跳跃过程中不会穿透任何楼板，必须准确落到目标窗口上
        # 防御：jump_duration 为 0 会导致下面多处除零崩溃，直接中止跳跃
        if not getattr(self, 'jump_duration', 0) or self.jump_duration <= 0:
            self.is_jumping = False
            return
        elapsed = current_time - self.jump_start_time
        jump_progress = min(elapsed / self.jump_duration, 1.0)
        
        import math
        
        # 确保jump_target_pos已经设置
        if not hasattr(self, 'jump_target_pos'):
            # 如果没有设置，使用当前位置作为目标
            self.jump_target_pos = self.pos()
        
        # 计算跳跃的总距离向量（X, Y平面）
        delta_x = self.jump_target_pos.x() - self.jump_start_pos.x()
        delta_y = self.jump_target_pos.y() - self.jump_start_pos.y()
        
        # 计算水平速度：匀速运动
        vx = delta_x / self.jump_duration
        
        # 计算初始垂直速度：确保能跳过窗口边缘
        g = self.gravity
        
        # 计算初始垂直速度：使用抛物线公式 dy = vy0 * t - 0.5 * g * t²
        vy0 = (delta_y + 0.5 * g * self.jump_duration * self.jump_duration + 50) / self.jump_duration  # 增加50像素的额外高度
        
        # 计算当前时间的位置
        x = self.jump_start_pos.x() + vx * elapsed
        y = self.jump_start_pos.y() + vy0 * elapsed - 0.5 * g * elapsed * elapsed
        
        # 检查跳跃过程中是否会穿透楼层
        current_pos = QPoint(int(x), int(y))
        current_rect = QRect(current_pos.x(), current_pos.y(), self.width(), self.height())
        
        # 检查是否与其他楼层相交（穿透检查）
        # 修复：楼层 dict 由 floor_manager.update_floors 每秒整体重建（新对象），
        # 用 `floor != self.current_floor` 做对象身份排除会因对象更替而失效 →
        # 跳跃飞行后段一旦跨越重建边界，与任意楼层相交即被误判"穿透"凭空坠落。
        # 改用稳定标识（window_hwnd / 'desktop'）比较。
        def _floor_id(f):
            if f is None:
                return None
            if f.get('type') == 'desktop':
                return 'desktop'
            return ('window', f.get('window_hwnd'))

        cur_fid = _floor_id(getattr(self, 'current_floor', None))
        tgt_fid = _floor_id(getattr(self, 'jump_target_floor', None))
        all_floors = self.floor_manager.get_all_floors()
        for floor in all_floors:
            if _floor_id(floor) in (cur_fid, tgt_fid):
                continue
            if floor['rect'].intersects(current_rect):
                # 检测到穿透，取消跳跃，启动重力掉落
                _log.debug("跳跃过程中检测到楼层穿透，取消跳跃并启动重力掉落")
                self.is_jumping = False
                self.start_falling()
                return
        
        # 确保跳跃结束时准确到达目标位置
        if jump_progress >= 1.0:
            # 跳跃完成，确保正确落到目标位置
            x = self.jump_target_pos.x()
            y = self.jump_target_pos.y()
            
            # 更新当前窗口信息
            if self.jump_target_window:
                self.current_window = self.jump_target_window
                self.window_level = self.jump_target_window['z_order']
                self.last_window_rect = (self.jump_target_window['x'], self.jump_target_window['y'], 
                                      self.jump_target_window['width'], self.jump_target_window['height'])
            else:
                # 跳到桌面，重置窗口信息
                self.current_window = None
                self.window_level = 0
                self.last_window_rect = None
            
            # 确保Ralsei可见
            self.show()
            
            # 移动到新位置
            self.move(int(x), int(y))
            
            # 更新Z轴坐标为目标Z坐标
            self.spatial_pos["z"] = self.jump_target_z
            
            # 播放落地动画
            self.change_animation("land", force=True)
            
            # 停止跳跃
            self.is_jumping = False
        
        # 边界检查：确保Ralsei不会跳到屏幕外
        screen_geometry = QApplication.desktop().availableGeometry()
        max_x = screen_geometry.width() - self.width()
        max_y = screen_geometry.height() - self.height()
        
        # 限制位置在屏幕范围内
        x = max(0, min(int(x), max_x))
        y = max(0, min(int(y), max_y))
        
        # 更新Ralsei的位置
        self.move(x, y)
        
        # 更新动画
        if self.is_jumping:
            # 如果还在跳跃中，保持跳跃动画
            if self.has_ball:
                self.change_animation("jump_ball", force=True)
            else:
                self.change_animation("jump", force=True)
        
        # 优化Z轴计算，确保有足够的跳跃高度
        if jump_progress < 1.0:
            jump_sine = math.sin(math.pi * jump_progress)
            # 增加Z轴跳跃高度，确保能跳上窗口
            extra_z_height = 50  # 额外增加Z轴高度
            z = self.jump_start_spatial['z'] + (abs(self.jump_z_diff) * 0.5 + extra_z_height) * jump_sine + self.jump_z_diff * jump_progress
            self.spatial_pos["z"] = z
            
            # 更新空间坐标
            self.spatial_pos["x"] = self.pos().x()
            self.spatial_pos["y"] = self.pos().y()
    
    def check_window_movement(self):
        # 检查当前所在窗口是否移动，使用楼层系统处理
        
        # ===== 关键过程保护：施法 / 躲猫猫 中 跳过窗口跟随（避免瞬移和摔倒干扰游戏）=====
        if getattr(self, '_spell_stage', None) is not None:
            return
        if getattr(self, 'game_state', {}).get('is_playing'):
            return
        
        # 更新楼层信息
        self.floor_manager.update_floors()
        
        # 获取Ralsei当前位置
        current_pos = self.pos()
        ralsei_rect = QRect(current_pos.x(), current_pos.y(), self.width(), self.height())
        
        # 获取当前所在楼层
        new_floor = self.floor_manager.get_current_floor(current_pos)
        
        if self.current_floor and new_floor != self.current_floor:
            # 楼层发生变化
            if self.current_floor['type'] == 'window':
                if new_floor['type'] == 'window':
                    # 从一个窗口移动到另一个窗口，检查是否是因为窗口移动导致的
                    # 启动摔倒动画，符合"建楼"要求：移动他所在的"楼板"时他会重心不稳甚至摔倒
                    _log.debug(f"Ralsei从一个窗口移动到另一个窗口，重心不稳摔倒了！")
                    # 设置摔倒动画持续时间至少3秒，符合要求
                    self.start_fall("window_move")
                elif new_floor['type'] == 'desktop':
                    # 从窗口上掉落到桌面，启动重力掉落
                    _log.debug(f"Ralsei从窗口上掉落到桌面，启动重力掉落！")
                    self.start_falling()

        # ===== 修复：窗口移动时 Ralsei 跟随楼板一起移动 =====
        # 此前该逻辑写在 update_floor()（全项目无任何调用点）中，"挪动窗口宠物跟着楼板走"
        # 的建楼需求从未生效。这里按同一窗口句柄比较新矩形与缓存位置，同步平移 Ralsei。
        if (self.current_window
                and new_floor['type'] == 'window'
                and new_floor.get('window_hwnd') == self.current_window.get('hwnd')):
            old_x = self.current_window.get('x')
            old_y = self.current_window.get('y')
            if old_x is not None and old_y is not None:
                x_diff = new_floor['rect'].left() - old_x
                y_diff = new_floor['rect'].top() - old_y
                if x_diff != 0 or y_diff != 0:
                    move_distance = (x_diff ** 2 + y_diff ** 2) ** 0.5
                    # 跟随楼板移动（同步平移，不做滑步）
                    n_x = self.pos().x() + x_diff
                    n_y = self.pos().y() + y_diff
                    screen_geom = QApplication.desktop().availableGeometry()
                    n_x = max(0, min(n_x, screen_geom.width() - self.width()))
                    n_y = max(0, min(n_y, screen_geom.height() - self.height()))
                    self.move(n_x, n_y)
                    # 更新缓存的窗口位置，避免下一轮重复判定
                    self.current_window['x'] = new_floor['rect'].left()
                    self.current_window['y'] = new_floor['rect'].top()
                    self.current_window['width'] = new_floor['rect'].width()
                    self.current_window['height'] = new_floor['rect'].height()
                    # 大幅移动 → 重心不稳摔倒（至少3秒），符合建楼要求
                    if move_distance > 30 and not self.is_falling:
                        _log.debug(f"窗口被大幅度移动，移动距离: {move_distance}，Ralsei重心不稳摔倒了！")
                        self.emotion_system.react_to_event('window_moved', {})
                        self.start_fall("window_move")

        # 更新当前楼层信息
        self.current_floor = new_floor
        self.current_platform_z = new_floor['platform_height']
        self.spatial_pos["z"] = new_floor['platform_height']

    def update_floor(self):
        # 获取Ralsei当前位置
        current_pos = self.pos()
        ralsei_rect = QRect(current_pos.x(), current_pos.y(), self.width(), self.height())
        
        # 更新楼层信息
        self.floor_manager.update_floors()
        
        # 获取当前所在楼层
        new_floor = self.floor_manager.get_current_floor(current_pos)
        
        if self.current_floor:
            # 如果当前在窗口上
            if self.current_floor['type'] == 'window':
                # 检查窗口是否仍然存在且位置未变
                if new_floor['type'] == 'window' and new_floor['window_hwnd'] == self.current_floor['window_hwnd']:
                    # 窗口仍然存在，检查位置是否变化
                    old_rect = self.current_floor['rect']
                    new_rect = new_floor['rect']
                    
                    # 计算位置变化
                    x_diff = new_rect.left() - old_rect.left()
                    y_diff = new_rect.top() - old_rect.top()
                    
                    # 窗口移动时，Ralsei会跟随楼板移动，就像楼板被移动一样
                    if x_diff != 0 or y_diff != 0:
                        # 计算窗口移动距离
                        move_distance = (x_diff ** 2 + y_diff ** 2) ** 0.5
                        
                        # 跟随窗口移动
                        new_x = current_pos.x() + x_diff
                        new_y = current_pos.y() + y_diff
                        self.move(new_x, new_y)
                        
                        # 保存Ralsei在窗口内的相对位置
                        window_center = QPoint(new_rect.left() + new_rect.width() // 2, 
                                             new_rect.top() + new_rect.height() // 2)
                        ralsei_center = QPoint(new_x + self.width() // 2, new_y + self.height() // 2)
                        self.ralsei_window_relative_pos = ralsei_center - window_center
                        
                        # 如果移动距离过大（超过30像素），Ralsei会重心不稳摔倒
                        if move_distance > 30 and not self.is_falling:
                            _log.debug(f"窗口被大幅度移动，移动距离: {move_distance}，Ralsei重心不稳摔倒了！")
                            # 触发情绪反应：窗口移动
                            self.emotion_system.react_to_event('window_moved', {})
                            # 设置摔倒动画持续时间至少3秒，符合要求
                            self.start_fall("window_move")
                elif new_floor['type'] != 'window':
                    # 窗口被关闭或移动，Ralsei从窗口上掉下来
                    _log.debug(f"窗口被关闭或移动，Ralsei从窗口上掉下来了！")
                    # 启动重力掉落
                    self.start_falling()
            else:
                # 当前在桌面上，检查是否有新窗口覆盖
                if new_floor['type'] == 'window':
                    # 新窗口覆盖了Ralsei所在的位置，站到新窗口上
                    _log.debug(f"新窗口覆盖了Ralsei所在的位置，Ralsei站到新窗口上")
                    # 触发情绪反应：发现新窗口
                    self.emotion_system.react_to_event('found_window', {})
        
        # 更新当前楼层信息
        self.current_floor = new_floor
        self.current_platform_z = new_floor['platform_height']
        self.spatial_pos["z"] = new_floor['platform_height']
    
    # 摔倒判定相关代码 - 开始摔倒
    def start_fall(self, reason="window_move"):
        # 开始摔倒，添加状态检查，避免重复触发
        if self.is_falling:
            # 已经在摔倒状态，不重复触发
            _log.debug("已经在摔倒状态，不重复触发摔倒动作")
            return
        # ===== 关键过程保护：施法 / 躲猫猫 / 拖拽中，不触发摔倒 =====
        if getattr(self, '_spell_stage', None) is not None:
            return
        if getattr(self, 'game_state', {}).get('is_playing'):
            return
        if getattr(self, '_is_being_dragged', False) or getattr(self, 'is_jumping', False):
            return

        self.is_falling = True
        self.fall_duration = 0.0
        self.fall_start_time = time.time()  # 设置摔倒开始时间
        self.is_recovering = False  # 是否处于恢复期
        self.recovery_duration = 0.0  # 恢复期持续时间
        self.recovery_max_duration = 5.0  # 恢复期最大持续时间（秒）
        
        # 触发情绪反应：摔倒
        self.emotion_system.react_to_event('fell_down', {'reason': reason})
        
        # 根据摔倒原因选择不同的动画、消息和持续时间
        if reason == "window_move":
            # 用户移动窗口导致摔倒
            # 使用生气的摔倒动画（spr_ralsei_splat_mad_0.png），持续至少3秒，符合要求
            # 优先使用生气摔倒动画，如果没有则使用普通摔倒动画
            if "fall_mad" in self.sprite_loader.sprites:
                self.change_animation("fall_mad", force=True)
            else:
                self.change_animation("fall", force=True)
            # 确保摔倒动画持续时间至少3秒，符合要求文件第37行的要求
            self.max_fall_duration = 3.0
            # 显示摔倒消息
            self.dialogue_ui.add_dialogue("ralsei", "哎呀！窗口移动了，我要摔下去了！", "surprised")
            # 设置摔倒状态，暂停行走
            self.is_moving = False
        elif reason == "fall_from_window":
            # 从窗口掉落 —— 这是用户（关窗/移窗）造成的，按"建楼"要求用生气的那组动作
            if "fall_mad" in self.sprite_loader.sprites:
                self.change_animation("fall_mad", force=True)
            else:
                self.change_animation("fall", force=True)
            # 确保掉落动画持续时间至少5秒，符合要求文件第36行的要求
            self.max_fall_duration = 5.0
            # 显示掉落消息
            self.dialogue_ui.add_dialogue("ralsei", "啊！我从窗口掉下来了！", "surprised")
            # 设置掉落状态，暂停行走
            self.is_moving = False
        elif reason == "fall_off":
            # Ralsei自己从窗口边缘掉下去
            # 使用普通摔倒动画（spr_ralsei_splat_0.png），持续5秒
            self.change_animation("fall", force=True)
            # 设置较长的摔倒持续时间（5秒）
            self.max_fall_duration = 5.0
            # 显示摔倒消息
            self.dialogue_ui.add_dialogue("ralsei", "哎呀！我掉下去了！", "sad")
            # 修复：与其他分支一致，摔倒时暂停行走
            self.is_moving = False
            self.idle_timer = 0
        else:
            # 默认情况，使用普通摔倒动画，持续5秒
            self.change_animation("fall", force=True)
            # 确保摔倒动画持续时间至少3秒
            self.max_fall_duration = 3.0
            # 显示摔倒消息
            self.dialogue_ui.add_dialogue("ralsei", "哎呀！我摔倒了！", "surprised")
            # 设置摔倒状态，暂停行走
            self.is_moving = False
            self.idle_timer = 0
        
        self.dialogue_ui.show_dialogue()
        
        # 重置当前窗口信息，Ralsei掉回桌面
        self.current_window = None
        self.window_level = 0
        self.last_window_rect = None
        
        # 重置空间坐标，掉回桌面
        self.spatial_pos["z"] = 0
        self.current_platform_z = 0
        
        # 添加摔倒惯性滑行效果
        # 保存当前速度用于滑行
        self.fall_slide_speed_x = self.current_speed_x * 0.5  # 保留一半的水平速度用于滑行
        self.fall_slide_speed_y = self.current_speed_y * 0.5  # 保留一半的垂直速度用于滑行
    
    def trigger_splat(self):
        """触发 splat 状态（先决条件：高速重力掉落/被甩飞等）。
        播放 snd_splat.wav 音效，设置 is_splat=True，约2秒后自动恢复。"""
        self.is_splat = True
        self.splat_start_time = time.time()
        self.is_moving = False
        self.is_falling = False
        self.is_recovering = False
        # 播放 splat 音效
        try:
            self.sound_manager.play_splat()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        # 切换到 splat 动画
        self.change_animation("splat", force=True)
        # 显示惊讶对话
        self.dialogue_ui.add_dialogue("ralsei", "啊！摔扁了...", "surprised")
        self.dialogue_ui.show_dialogue()

    def handle_gravity_fall(self, elapsed_time, current_time):
        # 处理重力掉落逻辑 —— 俯视2D游戏风格：带水平惯性的抛物线坠落，不坠出屏幕
        import math
        
        # 应用重力加速度
        self.fall_speed += self.gravity * elapsed_time
        
        # 计算掉落距离（垂直）
        fall_distance = self.fall_speed * elapsed_time
        
        # 水平惯性：掉落时保留水平速度，形成抛物线轨迹
        if not hasattr(self, 'fall_velocity_x'):
            self.fall_velocity_x = self.current_speed_x * 0.3  # 保留30%水平速度
        # 水平空气阻力
        self.fall_velocity_x *= 0.98
        horizontal_distance = self.fall_velocity_x * elapsed_time
        
        # 更新位置（抛物线：X有惯性，Y受重力）
        current_pos = self.pos()
        new_x = current_pos.x() + horizontal_distance
        new_y = current_pos.y() + fall_distance
        
        # 屏幕边界夹紧：绝不坠落到桌面底下（超出屏幕）
        screen_geometry = QApplication.desktop().availableGeometry()
        new_x = max(0, min(int(new_x), screen_geometry.width() - self.width()))
        max_y = screen_geometry.height() - self.height()
        
        # 检查是否落到了某个楼层上
        ralsei_pos = QPoint(int(new_x), int(new_y))
        drop_floor, drop_pos = self.floor_manager.get_drop_destination(ralsei_pos, self.current_floor)
        
        if drop_floor and drop_floor != self.current_floor:
            # 落到了新的楼层上
            new_y = drop_pos.y()
            self.is_gravity_falling = False
            self.fall_velocity_x = 0  # 落地清除水平惯性
            
            # 根据摔落速度决定是否触发摔倒动画
            if self.fall_speed > 150:
                # 高速摔落 → 触发 splat（先决条件：重力掉落）
                self.trigger_splat()
                # 添加摔倒惯性滑行效果
                self.fall_slide_speed_x = random.uniform(-20, 20)
                self.fall_slide_speed_y = random.uniform(-10, 10)
            else:
                # 低速摔落，切换回正常动画
                self.change_animation(f"walk_{self.current_direction}")
            
            # 更新当前楼层信息
            self.current_floor = drop_floor
            self.current_platform_z = drop_floor['platform_height']
            self.spatial_pos["z"] = drop_floor['platform_height']
            
            # 更新窗口信息
            if drop_floor['type'] == 'window':
                # 在窗口上
                window = drop_floor['window']
                self.current_window = {
                    'hwnd': window['hwnd'],
                    'title': window['title'],
                    'x': window['rect'].x(),
                    'y': window['rect'].y(),
                    'width': window['rect'].width(),
                    'height': window['rect'].height(),
                    'z_order': window['z_order'],
                    'platform_height': drop_floor['platform_height']
                }
                self.window_level = window['z_order']
                self.last_window_rect = (window['rect'].x(), window['rect'].y(), 
                                      window['rect'].width(), window['rect'].height())
                # 使用WindowStaysOnTopHint确保Ralsei在当前窗口上可见
                self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
            else:
                # 在桌面上
                self.current_window = None
                self.window_level = 0
                self.last_window_rect = None
                # 移除顶层窗口标志
                self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
            
            self.show()
        else:
            # 继续掉落
            # 获取屏幕几何信息
            screen_geometry = QApplication.desktop().availableGeometry()
            
            # 检查是否落到了桌面底部
            if new_y + self.height() >= screen_geometry.height():
                # 落到桌面底部（夹紧，绝不超出屏幕）
                new_y = max_y
                self.is_gravity_falling = False
                self.fall_velocity_x = 0  # 落地清除水平惯性
                
                # 根据摔落速度决定是否触发摔倒动画
                if self.fall_speed > 150:
                    # 高速摔落 → 触发 splat（先决条件：重力掉落）
                    self.trigger_splat()
                    # 添加摔倒惯性滑行效果
                    self.fall_slide_speed_x = random.uniform(-20, 20)
                    self.fall_slide_speed_y = random.uniform(-10, 10)
                else:
                    # 低速摔落，切换回正常动画
                    self.change_animation(f"walk_{self.current_direction}")
                
                # 更新当前窗口信息
                self.current_window = None
                self.window_level = 0
                self.last_window_rect = None
                
                # 更新空间坐标
                self.spatial_pos["z"] = 0
                self.current_platform_z = 0
                
                # 移除顶层窗口标志
                self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
                self.show()
        
        # 移动Ralsei
        self.move(int(new_x), int(new_y))
    
    # 摔倒判定相关代码 - 处理摔倒逻辑
    def handle_fall(self, elapsed_time, current_time):
        # 处理摔倒逻辑
        if not self.is_recovering:
            self.fall_duration += elapsed_time
            
            # 应用摔倒惯性滑行效果，减少滑行计算的频率
            if hasattr(self, 'fall_slide_speed_x') and hasattr(self, 'fall_slide_speed_y'):
                # 计算滑行距离
                slide_x = self.fall_slide_speed_x * elapsed_time
                slide_y = self.fall_slide_speed_y * elapsed_time
                
                # 更新位置
                current_pos = self.pos()
                new_x = current_pos.x() + slide_x
                new_y = current_pos.y() + slide_y
                self.move(int(new_x), int(new_y))
                
                # 逐渐减小滑行速度，使用更简单的衰减公式
                self.fall_slide_speed_x *= 0.8  # 每次更新减少20%的速度，减少计算次数
                self.fall_slide_speed_y *= 0.8
            
            # 检查是否完成摔倒
            if self.fall_duration >= self.max_fall_duration:
                # 摔倒完成，进入恢复期
                self.is_recovering = True
                self.recovery_duration = 0.0
                
                # 切换到恢复动画，优先使用特殊恢复动画，如果没有则使用站立动画
                if "land" in self.sprite_loader.sprites:
                    self.change_animation("land", force=True)
                elif "pose" in self.sprite_loader.sprites:
                    self.change_animation("pose", force=True)
                else:
                    self.change_animation(f"idle", force=True)
                
                # 清除滑行速度属性
                if hasattr(self, 'fall_slide_speed_x'):
                    del self.fall_slide_speed_x
                if hasattr(self, 'fall_slide_speed_y'):
                    del self.fall_slide_speed_y
                
                # 触发情绪反应：开始恢复
                self.emotion_system.react_to_event('recovery_started', {})
                
                # 显示恢复消息，更加温柔和害羞
                if random.random() < 0.7:  # 70%概率显示恢复消息
                    self.dialogue_ui.add_dialogue("ralsei", "呼...我没事了...谢谢你的关心...", "shy")
                    self.dialogue_ui.show_dialogue()
        else:
            # 处理恢复期逻辑
            self.recovery_duration += elapsed_time
            
            # 检查是否完成恢复
            if self.recovery_duration >= self.recovery_max_duration:
                # 恢复完成，返回正常状态
                self.is_falling = False
                self.is_recovering = False
                
                # 触发情绪反应：恢复完成
                self.emotion_system.react_to_event('recovery_complete', {})

                # ===== 躲猫猫 / Spell 移动阶段：不重置 is_moving，继续之前的移动 =====
                _in_critical_move = False
                _hs = getattr(self, '_hide_stage', None)
                if _hs in ('moving_to_center', 'moving_to_folder'):
                    _in_critical_move = True
                if getattr(self, '_spell_stage', None) == 'walking':
                    _in_critical_move = True

                if _in_critical_move:
                    # 恢复移动：不要重置 is_moving / 不要调 randomize_movement_pattern / 不要切 idle
                    if hasattr(self, '_speed_variation'):
                        del self._speed_variation
                    self._speed_variation = 1.0
                    # 用现有 target_pos 设置方向动画
                    try:
                        dx = self.target_pos.x() - self.x()
                        dy = self.target_pos.y() - self.y()
                        if abs(dx) > abs(dy):
                            d = 'right' if dx > 0 else 'left'
                        else:
                            d = 'down' if dy > 0 else 'up'
                        self.change_animation(f"walk_{d}", force=True)
                    except Exception as e:  # 修复：原先静默吞噬
                        _log.debug("main 防御性异常（已忽略）: %s", e)
                else:
                    # 恢复正常状态，但先休息一段时间，符合Ralsei温柔的性格
                    self.is_moving = False
                    self.max_idle_duration = random.uniform(3.0, 6.0)  # 恢复后先休息3-6秒
                    self.idle_timer = 0
                    self.randomize_movement_pattern()
                    
                    # 显示恢复完成消息，更加温柔和害羞
                    if random.random() < 0.5:  # 50%概率显示恢复完成消息
                        self.dialogue_ui.add_dialogue("ralsei", "我已经完全恢复了...谢谢...", "happy")
                        self.dialogue_ui.show_dialogue()
                    
                    # 使用idle动画，让Ralsei先休息一下
                    self.change_animation("idle", force=True)
    
    
    def wake_up(self):
        # 唤醒Ralsei
        self.is_sleeping = False
        # 修复：唤醒时也退出"小憩走路"状态、复位相关计时
        self.is_sleeping_walk = False
        self.idle_walk_timer = 0
        # 修复：唤醒时清理可能残留的物理中间态（重力掉落/恢复期）
        self.is_gravity_falling = False
        self.is_recovering = False
        
        # 切换到苏醒动画
        self.change_animation("pose", force=True)
        
        # 显示苏醒消息
        wake_up_messages = ["嗯？什么事？", "哎呀！我睡着了！", "早上好！"]
        self.dialogue_ui.add_dialogue("ralsei", random.choice(wake_up_messages), "surprised")
        self.dialogue_ui.show_dialogue()
        
        # 重置睡眠计时器
        self.last_interaction_time = time.time()
        self.sleep_timer = 0
        
    def start_dragging_play(self):
        # 开始拖动桌面元素或光标玩耍
        import random
        
        # 选择拖动对象：桌面元素或光标
        drag_target = random.choice(["desktop_element", "cursor"])
        
        if drag_target == "desktop_element":
            # 从桌面元素中随机选择一个
            desktop_elements = self.desktop_interaction.desktop_elements
            if desktop_elements:
                self.dragging_element = random.choice(desktop_elements)
                self.dragging_element["is_being_dragged"] = True
                self.dragging_element["drag_force"] = random.uniform(0.5, 2.0)
                self.dragging_type = "desktop_element"
                
                # 显示对话
                self.dialogue_ui.show_dialogue(f"我来帮你移动{self.dragging_element['name']}吧！")
                
                # 切换到合适的动画
                self.change_animation("walk_down", force=True)
                
                # 记录拖拽开始时间和位置
                self.dragging_start_time = time.time()
                self.dragging_duration = random.uniform(1.0, 3.0)
                
                # 生成随机目标位置
                screen_geom = QApplication.desktop().availableGeometry()
                target_x = random.randint(100, screen_geom.width() - 200)
                target_y = random.randint(100, screen_geom.height() - 200)
                self.drag_target_pos = QPoint(target_x, target_y)
                
                # 记录元素初始位置
                self.dragging_element_initial_pos = (self.dragging_element["x"], self.dragging_element["y"])
        else:
            # 拖动光标
            self.dragging_element = None
            self.dragging_type = "cursor"
            self.dragging_cursor_start = QCursor.pos()
            self.dragging_cursor_duration = random.uniform(1.0, 3.0)
            self.dragging_cursor_start_time = time.time()
            
            # 显示对话
            self.dialogue_ui.show_dialogue("我来陪你玩一会儿鼠标吧！")
            
            # 切换到合适的动画
            self.change_animation("laugh", force=True)
        
        self.last_dragging_time = time.time()
        
    def handle_dragging_play(self, elapsed_time, current_time):
        # 处理正在拖动的桌面元素或光标
        if self.dragging_type == "desktop_element":
            if self.dragging_element:
                # 计算拖拽进度
                elapsed_dragging = current_time - self.dragging_start_time
                if elapsed_dragging < self.dragging_duration:
                    # 平滑移动元素到目标位置
                    progress = elapsed_dragging / self.dragging_duration
                    # 使用缓动函数使移动更自然
                    eased_progress = progress * progress * (3 - 2 * progress)  # 三次缓动
                    
                    # 计算元素当前位置
                    element_x = int(self.dragging_element_initial_pos[0] + (self.drag_target_pos.x() - self.dragging_element_initial_pos[0]) * eased_progress)
                    element_y = int(self.dragging_element_initial_pos[1] + (self.drag_target_pos.y() - self.dragging_element_initial_pos[1]) * eased_progress)
                    
                    # 更新元素位置
                    self.dragging_element["x"] = element_x
                    self.dragging_element["y"] = element_y
                    
                    # 让Ralsei跟随元素移动
                    ralsei_x = element_x - self.width() // 2 + random.randint(-20, 20)
                    ralsei_y = element_y - self.height() // 2 + random.randint(-20, 20)
                    
                    # 确保在屏幕范围内
                    screen_geom = QApplication.desktop().availableGeometry()
                    ralsei_x = max(0, min(ralsei_x, screen_geom.width() - self.width()))
                    ralsei_y = max(0, min(ralsei_y, screen_geom.height() - self.height()))
                    
                    # 移动Ralsei
                    self.move(ralsei_x, ralsei_y)
                else:
                    # 拖拽"完成"：玩耍结束，不真实移动用户文件
                    # 修复：原代码对随机选中的真实桌面文件执行 os.rename/move
                    # （desktop_interaction.drag_file → moved_<原名> 或移入文件夹），
                    # 无确认、不可撤销，会把用户桌面布局改乱。玩耍只做视觉模拟，
                    # 桌面元素位置由 update_desktop_elements 的周期扫描自然校正。
                    self.dragging_element["is_being_dragged"] = False
                    self.dragging_element = None
                    self.dialogue_ui.show_dialogue("嘿嘿，陪你玩了一下！我把它放回去啦~")
                    self.change_animation("idle", force=True)
        else:
            # 处理拖动光标
            elapsed_dragging = current_time - self.dragging_cursor_start_time
            
            if elapsed_dragging < self.dragging_cursor_duration:
                # 随机移动光标
                import win32api
                import win32con
                
                # 计算随机偏移量
                offset_x = random.randint(-50, 50)
                offset_y = random.randint(-50, 50)
                
                # 获取当前光标位置
                current_cursor = QCursor.pos()
                
                # 计算新光标位置
                new_cursor_x = current_cursor.x() + offset_x
                new_cursor_y = current_cursor.y() + offset_y
                
                # 移动光标
                try:
                    win32api.SetCursorPos((new_cursor_x, new_cursor_y))
                except Exception as e:  # 修复：原先静默吞噬
                    _log.debug("main 防御性异常（已忽略）: %s", e)
                
                # 让Ralsei跟随光标移动
                ralsei_pos = self.pos()
                dx = new_cursor_x - ralsei_pos.x() - self.width() // 2
                dy = new_cursor_y - ralsei_pos.y() - self.height() // 2
                
                distance = math.hypot(dx, dy)
                if distance > 0:
                    move_speed = self.speed * 1.0
                    # speed 语义是"像素/帧"，直接用 move_speed，不乘 elapsed_time（避免帧率相关+瞬移）
                    move_distance = min(distance, move_speed)
                    
                    direction_x = dx / distance
                    direction_y = dy / distance
                    
                    new_x = int(ralsei_pos.x() + direction_x * move_distance)
                    new_y = int(ralsei_pos.y() + direction_y * move_distance)
                    
                    # 确保在屏幕范围内
                    screen_geom = QApplication.desktop().availableGeometry()
                    new_x = max(0, min(new_x, screen_geom.width() - self.width()))
                    new_y = max(0, min(new_y, screen_geom.height() - self.height()))
                    
                    # 移动Ralsei
                    self.move(new_x, new_y)
            else:
                # 结束拖动光标
                self.dragging_element = None
                self.dragging_type = None
                self.dialogue_ui.show_dialogue("玩得真开心！")
                self.change_animation("idle", force=True)
        
    def trigger_laugh(self):
        # 触发笑的状态
        self.is_laughing = True
        self.is_happy = True
        self.happy_timer = 0
        # 修复：EmotionSystem 无 update_emotion 方法（接口失配会 AttributeError），
        # 统一走 add_emotion。
        self.emotion_system.add_emotion("happy", 50)
        
    def trigger_surprise(self):
        # 触发惊讶状态
        self.is_surprised = True
        self.surprised_timer = 0
        self.emotion_system.add_emotion("curious", 40)
        
    def trigger_shy(self):
        # 触发害羞状态
        self.is_shy = True
        self.shy_timer = 0
        self.emotion_system.add_emotion("shy", 35)
        
    def trigger_unhappy(self):
        # 触发不开心状态
        self.is_unhappy = True
        self.unhappy_timer = 0
        self.emotion_system.add_emotion("sad", 30)
        
    def trigger_victory(self):
        # 触发胜利状态
        self.is_victorious = True
        self.emotion_system.add_emotion("happy", 60)
        
    def trigger_teasplash(self):
        # 触发被溅茶状态
        self.is_teasplashed = True
        self.emotion_system.add_emotion("surprised", 45)
        
    def reset_special_states(self):
        # 重置所有特殊状态
        self.is_laughing = False
        self.is_surprised = False
        self.is_shy = False
        self.is_unhappy = False
        self.is_victorious = False
        self.is_teasplashed = False
        self.is_sleeping_walk = False
        self.is_using_item = False
        self.is_spellcasting = False
        self.is_rolling = False
        self.is_sliding = False
        self.idle_walk_timer = 0
        
        # 开始移动
        self.randomize_movement_pattern()
        self.is_moving = True
    
    def climb_to_top_window(self):
        # 爬上最上层窗口
        
        # 获取所有可见窗口
        windows = self.desktop_interaction.get_all_visible_windows()
        if not windows:
            return
        
        # 选择最上层窗口（根据Z序，假设get_all_visible_windows返回的是按Z序排序的，最上层窗口在最前面）
        top_window = windows[0]
        
        # 跳上最上层窗口，默认从底部跳上
        self.start_jump(top_window, "bottom")
    
    def react_to_desktop_element(self, element):
        # 对桌面元素做出反应，考虑物体的现实属性
        # 修复：get_nearby_elements 返回的 window 元素没有 'path' 键、所有元素都没有顶层
        # 'x'/'width' 键（只有 'rect'），原实现直接索引会 KeyError。统一改用 .get + rect 防御，
        # 并对同一元素加 30 秒防抖（原实现永不重置，拖走再放回也不会再反应）。
        elem_path = element.get('path', '') if element.get('type') != 'window' else element.get('title', '')
        now = time.time()
        last = getattr(self, '_last_reacted_element', None)
        if isinstance(last, tuple) and last[0] == elem_path and now - last[1] < 30.0:
            return
        if not isinstance(last, tuple) and last is not None and last == elem_path:
            return
        self._last_reacted_element = (elem_path, now)
        
        # 获取物体的现实属性
        weight = element.get('weight', 1.0)
        material = element.get('material', 'paper')
        is_fragile = element.get('is_fragile', False)
        temperature = element.get('temperature', 20)
        texture = element.get('texture', 'smooth')
        
        # 根据物体属性生成更真实的反应
        reaction = self.desktop_interaction.get_special_file_reaction(elem_path)
        
        # 确保Ralsei面向图标
        # 获取图标位置（元素只有 'rect'，从 rect 取中心）
        elem_rect = element.get('rect')
        if elem_rect is not None:
            element_x = elem_rect.center().x()
            element_y = elem_rect.center().y()
        else:
            element_x = element.get('x', 0) + element.get('width', 40) // 2
            element_y = element.get('y', 0) + element.get('height', 40) // 2
            
        # 获取Ralsei中心位置
        ralsei_x = self.pos().x() + self.width() // 2
        ralsei_y = self.pos().y() + self.height() // 2
            
        # 计算方向
        dx = element_x - ralsei_x
        dy = element_y - ralsei_y
            
        # 根据方向调整Ralsei的面向
        if abs(dx) > abs(dy):
            # 水平方向差异更大
            if dx > 0:
                # 向右
                self.current_direction = "right"
            else:
                # 向左
                self.current_direction = "left"
        else:
            # 垂直方向差异更大
            if dy > 0:
                # 向下
                self.current_direction = "down"
            else:
                # 向上
                self.current_direction = "up"
            
        # 面向图标：只在 Ralsei 正在移动时同步走路/跑步动画方向。
        # 修复：原来无条件 change_animation("walk_<dir>")——静止(idle)时被
        # 附近桌面元素检测触发也会切到走路动画，站着播走路帧 → "动画播放错乱"。
        if self.is_moving and (self.current_animation.startswith('walk_')
                               or self.current_animation.startswith('run_')):
            self.change_animation(f"walk_{self.current_direction}", force=True)
            
        # 提取反应文案中"！"之后的部分（用于拼接"小心！这个X..."），
        # 修复：原 split('！')[1] 在 dialogue 不含"！"时 IndexError；含"！"但后面为空时
        # 得到空串。统一安全提取。
        def _after_bang(text):
            return text.split('！', 1)[1] if '！' in text else text
            
        # 根据物体属性调整反应
        if is_fragile:
            # 对易碎物品的反应
            reaction['dialogue'] = f"小心！这个{_after_bang(reaction['dialogue'])}看起来很容易碎呢！"
            reaction['emotion'] = 'careful'
            reaction['action'] = 'look_up'
            
        elif weight > 1.5:
            # 对重物的反应
            reaction['dialogue'] = f"这个{_after_bang(reaction['dialogue'])}看起来很重，我可能搬不动呢！"
            reaction['emotion'] = 'surprised'
            reaction['action'] = 'act'
            
        elif temperature > 25:
            # 对高温物品的反应
            reaction['dialogue'] = f"这个{_after_bang(reaction['dialogue'])}摸起来有点热，小心烫手！"
            reaction['emotion'] = 'warning'
            reaction['action'] = 'surprised'
            
        elif temperature < 18:
            # 对低温物品的反应
            reaction['dialogue'] = f"这个{_after_bang(reaction['dialogue'])}摸起来凉凉的，好舒服！"
            reaction['emotion'] = 'happy'
            reaction['action'] = 'wave'
            
        # 根据材质调整反应
        if material == "metal":
            reaction['dialogue'] += " 金属做的东西总是感觉很坚固呢！"
        elif material == "wood":
            reaction['dialogue'] += " 木质的东西摸起来很温暖！"
        elif material == "plastic":
            reaction['dialogue'] += " 塑料做的东西很轻便呢！"
        elif material == "paper":
            reaction['dialogue'] += " 纸做的东西要小心处理哦！"
            
        # 显示对话
        self.dialogue_ui.add_dialogue("ralsei", reaction['dialogue'], reaction['emotion'])
        self.dialogue_ui.show_dialogue()
            
        # 播放相应动画
        self.play_animation_once(reaction['action'])
            
        # 更新情绪
        self.emotion_system.add_emotion(reaction['emotion'], 30)
            
        # 随机决定是否主动与桌面元素互动（25%概率）
        import random
        if random.random() < 0.25:
            # 根据元素类型决定互动方式
            if element['type'] == 'folder':
                # 对文件夹的互动
                self.interact_with_folder(element)
            elif element['type'] == 'file':
                # 对文件的互动
                self.interact_with_file(element)
            
        # 检查是否是浏览器相关文件
        file_name = os.path.basename(elem_path).lower()
        if 'browser' in file_name or 'chrome' in file_name or 'firefox' in file_name or 'edge' in file_name:
            # 显示浏览器相关帮助
            self.dialogue_ui.add_dialogue("ralsei", "需要我帮你打开浏览器或搜索什么吗？", "helpful")
            self.dialogue_ui.show_dialogue()
        # 如果是工作相关文件，可以提供帮助
        else:
            file_ext = os.path.splitext(elem_path)[1].lower()
            work_file_extensions = [
                '.pptx', '.ppt',  # PowerPoint文件
                '.xlsx', '.xls',   # Excel文件
                '.doc', '.docx',   # Word文件
                '.pdf',            # PDF文件
                '.txt',            # 文本文件
                '.md',             # Markdown文件
                '.py', '.js', '.java', '.cpp', '.c',  # 代码文件
                '.html', '.css'    # 网页文件
            ]
                
            if file_ext in work_file_extensions:
                # 根据不同文件类型提供不同的帮助信息
                help_messages = {
                    '.pptx': "需要我帮你控制这个PPT吗？我可以帮你播放、切换幻灯片哦！",
                    '.ppt': "需要我帮你控制这个PPT吗？我可以帮你播放、切换幻灯片哦！",
                    '.xlsx': "需要我帮你处理这个Excel表格吗？我可以帮你读取数据、写入数据哦！",
                    '.xls': "需要我帮你处理这个Excel表格吗？我可以帮你读取数据、写入数据哦！",
                    '.doc': "需要我帮你处理这个Word文档吗？我可以帮你查看内容哦！",
                    '.docx': "需要我帮你处理这个Word文档吗？我可以帮你查看内容哦！",
                    '.pdf': "需要我帮你查看这个PDF文件吗？我可以帮你读取内容哦！",
                    '.txt': "需要我帮你查看这个文本文件吗？我可以帮你读取内容哦！",
                    '.md': "需要我帮你查看这个Markdown文件吗？我可以帮你读取内容哦！",
                    '.py': "需要我帮你处理这个Python代码文件吗？我可以帮你查看、运行代码哦！",
                    '.js': "需要我帮你处理这个JavaScript代码文件吗？我可以帮你查看代码哦！",
                    '.java': "需要我帮你处理这个Java代码文件吗？我可以帮你查看代码哦！",
                    '.cpp': "需要我帮你处理这个C++代码文件吗？我可以帮你查看代码哦！",
                    '.c': "需要我帮你处理这个C代码文件吗？我可以帮你查看代码哦！",
                    '.html': "需要我帮你处理这个HTML文件吗？我可以帮你查看内容哦！",
                    '.css': "需要我帮你处理这个CSS文件吗？我可以帮你查看内容哦！"
                }
                    
                # 显示帮助询问
                self.dialogue_ui.add_dialogue("ralsei", help_messages[file_ext], "helpful")
                self.dialogue_ui.show_dialogue()
    
    
    
    def check_browser_windows(self):
        # 检查浏览器窗口并做出反应
        browser_windows = self.desktop_interaction.identify_browser_windows()
        current_hour = int(time.strftime("%H"))
        import random
        
        if browser_windows:
            # 随机选择一个浏览器窗口
            target_browser = random.choice(browser_windows)
            
            # 根据时间和内容提供不同的帮助
            if random.random() < 0.6:  # 60%的概率提供帮助
                # 工作时间推荐工作相关内容
                if 9 <= current_hour < 18:
                    work_topics = [
                        "工作效率提升技巧",
                        "Excel快捷键",
                        "PPT设计灵感",
                        "时间管理方法",
                        "职场沟通技巧",
                        "会议主持技巧",
                        "项目管理工具",
                        "职场穿搭指南"
                    ]
                    topic = random.choice(work_topics)
                    self.dialogue_ui.add_dialogue("ralsei", f"我看到你正在使用{target_browser['title']}浏览器！需要我帮你搜索关于{topic}的内容吗？", "helpful")
                # 休闲时间推荐娱乐内容
                else:
                    entertainment_topics = [
                        "热门电影推荐",
                        "最新游戏资讯",
                        "有趣的YouTube视频",
                        "热门动漫更新",
                        "放松音乐推荐",
                        "美食制作教程",
                        "旅游攻略",
                        "健身运动指南"
                    ]
                    topic = random.choice(entertainment_topics)
                    self.dialogue_ui.add_dialogue("ralsei", f"我看到你正在使用{target_browser['title']}浏览器！要不要我帮你找些{topic}？", "happy")
                self.dialogue_ui.show_dialogue()
            
            # 有一定概率主动推荐与Deltarune或Undertale相关的内容
            if random.random() < 0.4:  # 40%的概率
                deltarune_topics = [
                    "Deltarune latest news", 
                    "Undertale fan art", 
                    "Ralsei character design", 
                    "Deltarune Chapter 3 release date", 
                    "Toby Fox latest updates",
                    "Deltarune soundtrack",
                    "Undertale theories",
                    "Deltarune fan games"
                ]
                search_query = random.choice(deltarune_topics)
                self.dialogue_ui.add_dialogue("ralsei", f"我来帮你搜索关于{search_query}的内容吧！", "excited")
                self.dialogue_ui.show_dialogue()
                self.desktop_interaction.search_in_browser(search_query)
        else:
            # 没有浏览器窗口，根据时间推荐不同的内容
            if random.random() < 0.4:  # 40%的概率主动询问
                if 9 <= current_hour < 18:
                    # 工作时间推荐工作相关内容
                    self.dialogue_ui.add_dialogue("ralsei", "最近都没有使用浏览器呢，需要我帮你打开浏览器搜索工作相关的资料吗？", "helpful")
                else:
                    # 休闲时间推荐娱乐内容
                    entertainment_choices = [
                        "看看Deltarune的最新消息",
                        "找些有趣的视频看看",
                        "搜索最新的游戏资讯",
                        "看看热门的电影推荐",
                        "听些放松的音乐",
                        "学习新技能",
                        "了解最新科技资讯",
                        "查看天气预报"
                    ]
                    choice = random.choice(entertainment_choices)
                    self.dialogue_ui.add_dialogue("ralsei", f"最近都没有使用浏览器呢，需要我帮你打开浏览器{choice}吗？", "curious")
                self.dialogue_ui.show_dialogue()
    
    def check_ppt_windows(self):
        # 检查PPT窗口并做出反应
        ppt_windows = self.desktop_interaction.identify_ppt_windows()
        if ppt_windows:
            # 随机选择一个PPT窗口
            import random
            target_ppt = random.choice(ppt_windows)
            
            # 根据时间和使用场景提供不同的帮助
            current_hour = int(time.strftime("%H"))
            
            if 9 <= current_hour < 18:  # 工作时间
                # 提供更全面的PPT帮助
                ppt_help_choices = [
                    f"我看到你正在使用PowerPoint！需要我帮忙控制演示文稿吗？我可以帮你播放、切换幻灯片，或者调整幻灯片时间哦！",
                    f"你在制作{target_ppt['title']}吗？需要我帮忙查找PPT模板或设计灵感吗？",
                    f"正在准备演示文稿吗？我可以帮你检查幻灯片内容，或者调整动画效果哦！",
                    f"需要我帮你将{target_ppt['title']}导出为PDF格式，方便分享吗？"
                ]
                help_message = random.choice(ppt_help_choices)
                self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
            else:  # 非工作时间
                # 提供更轻松的帮助
                self.dialogue_ui.add_dialogue("ralsei", f"我看到你正在使用PowerPoint！需要我帮忙调整幻灯片，让你的演示更吸引人吗？", "happy")
            
            self.dialogue_ui.show_dialogue()
        else:
            # 没有PPT窗口，检查桌面PPT文件
            self.check_ppt_files()
    
    def check_ppt_files(self):
        # 检查桌面上的PPT文件并做出反应
        ppt_files = self.desktop_interaction.check_ppt_files()
        if ppt_files:
            # 随机选择一个PPT文件
            import random
            target_ppt = random.choice(ppt_files)
            
            # 显示对话
            self.dialogue_ui.add_dialogue("ralsei", f"我看到你桌面上有{target_ppt['name']}！需要我帮你打开并控制这个PPT吗？我可以帮你播放、切换幻灯片，或者调整幻灯片时间哦！", "happy")
            self.dialogue_ui.show_dialogue()
    
    def check_excel_windows(self):
        # 检查Excel窗口并做出反应
        excel_windows = self.desktop_interaction.identify_excel_windows()
        if excel_windows:
            # 随机选择一个Excel窗口
            import random
            target_excel = random.choice(excel_windows)
            
            # 根据时间和使用场景提供不同的Excel帮助
            current_hour = int(time.strftime("%H"))
            
            if 9 <= current_hour < 18:  # 工作时间
                # 提供更专业的Excel帮助
                excel_help_choices = [
                    f"我看到你正在使用Excel！需要我帮忙处理数据吗？我可以帮你读取、写入单元格，或者创建图表哦！",
                    f"你在处理{target_excel['title']}的数据吗？需要我帮忙计算总和、平均值，或者进行数据排序吗？",
                    f"正在制作表格吗？我可以帮你格式化单元格，或者添加筛选器，让数据更清晰！",
                    f"需要我帮你将{target_excel['title']}中的数据导出为图表，方便在报告中使用吗？",
                    f"处理大量数据吗？我可以帮你使用Excel公式，提高你的工作效率哦！"
                ]
                help_message = random.choice(excel_help_choices)
                self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
            else:  # 非工作时间
                # 提供更轻松的帮助
                self.dialogue_ui.add_dialogue("ralsei", f"我看到你正在使用Excel！需要我帮忙整理数据，或者创建简单的预算表格吗？", "happy")
            
            self.dialogue_ui.show_dialogue()
    
    def check_word_windows(self):
        # 检查Word窗口并做出反应
        word_windows = self.desktop_interaction.identify_word_windows()
        if word_windows:
            # 随机选择一个Word窗口
            import random
            target_word = random.choice(word_windows)
            
            # 根据时间和使用场景提供不同的Word帮助
            current_hour = int(time.strftime("%H"))
            
            if 9 <= current_hour < 18:  # 工作时间
                # 提供更专业的Word帮助
                word_help_choices = [
                    f"我看到你正在使用Word！需要我帮忙编辑文档吗？我可以帮你格式化文本，或者添加内容哦！",
                    f"你在撰写{target_word['title']}吗？需要我帮忙检查语法、拼写，或者调整文档格式吗？",
                    f"正在制作报告吗？我可以帮你添加目录、页眉页脚，或者插入图片哦！",
                    f"需要我帮你将{target_word['title']}导出为PDF格式，方便打印或分享吗？",
                    f"处理长文档吗？我可以帮你设置样式，让文档更加统一和专业！"
                ]
                help_message = random.choice(word_help_choices)
                self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
            else:  # 非工作时间
                # 提供更轻松的帮助
                word_leisure_help_choices = [
                    f"我看到你正在使用Word！需要我帮忙写点什么吗？日记、故事，或者信件都可以哦！",
                    f"正在编辑{target_word['title']}吗？需要我帮忙调整格式，让它看起来更美观吗？",
                    f"想写点什么有趣的内容吗？我可以帮你构思和组织文字哦！"
                ]
                help_message = random.choice(word_leisure_help_choices)
                self.dialogue_ui.add_dialogue("ralsei", help_message, "happy")
            
            self.dialogue_ui.show_dialogue()
    
    def check_task_management(self):
        # 检查并提供任务管理帮助
        import random
        current_hour = int(time.strftime("%H"))
        
        # 根据时间提供不同的任务管理帮助
        if 9 <= current_hour < 18:  # 工作时间
            task_help_choices = [
                "你有需要管理的任务吗？我可以帮你创建待办事项列表！",
                "需要我帮你整理今日工作任务，安排优先级吗？",
                "正在处理多个任务吗？我可以帮你制定时间计划！",
                "想创建一个长期任务吗？我可以帮你设置提醒！",
                "需要我帮你检查任务完成情况，生成简单的工作报告吗？"
            ]
            help_message = random.choice(task_help_choices)
            self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
        else:  # 非工作时间
            task_help_choices = [
                "需要我帮你创建周末计划吗？",
                "想记录个人任务或愿望清单吗？我可以帮你！",
                "需要我帮你检查本周任务完成情况吗？",
                "想为明天的工作做准备吗？我可以帮你制定计划！"
            ]
            help_message = random.choice(task_help_choices)
            self.dialogue_ui.add_dialogue("ralsei", help_message, "happy")
        
        self.dialogue_ui.show_dialogue()
    
    def check_time_tracking(self):
        # 检查并提供时间跟踪帮助
        import random
        current_hour = int(time.strftime("%H"))
        
        time_tracking_help_choices = [
            "需要我帮你记录工作时间吗？我可以帮你统计今日工作时长！",
            "想了解你在各个任务上花费的时间吗？我可以帮你跟踪！",
            "需要我帮你设置番茄钟，提高工作效率吗？",
            "正在处理重要任务吗？我可以帮你计时！",
            "想查看本周的工作时间统计吗？我可以帮你生成！"
        ]
        
        help_message = random.choice(time_tracking_help_choices)
        self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
        self.dialogue_ui.show_dialogue()
    
    def check_meeting_reminders(self):
        # 检查并提供会议提醒帮助
        import random
        
        meeting_help_choices = [
            "需要我帮你设置会议提醒吗？",
            "想记录即将到来的会议信息吗？我可以帮你！",
            "需要我帮你准备会议议程或要点吗？",
            "正在准备会议吗？我可以帮你整理会议资料！",
            "想为会议设置提前提醒吗？我可以帮你！"
        ]
        
        help_message = random.choice(meeting_help_choices)
        self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
        self.dialogue_ui.show_dialogue()
    
    def check_file_organization(self):
        # 检查并提供文件整理帮助
        import random
        
        file_org_help_choices = [
            "需要我帮你整理桌面文件吗？",
            "想为你的文件创建分类文件夹吗？我可以帮你！",
            "正在查找特定文件吗？我可以帮你搜索！",
            "需要我帮你清理临时文件，释放磁盘空间吗？",
            "想为重要文件创建备份吗？我可以帮你！"
        ]
        
        help_message = random.choice(file_org_help_choices)
        self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
        self.dialogue_ui.show_dialogue()
    
    def check_quick_notes(self):
        # 检查并提供快速笔记帮助
        import random
        
        notes_help_choices = [
            "需要我帮你快速记录笔记吗？",
            "想创建一个待办事项便签吗？我可以帮你！",
            "正在思考重要内容吗？我可以帮你记录想法！",
            "需要我帮你整理之前的笔记吗？",
            "想为笔记添加标签，方便查找吗？我可以帮你！"
        ]
        
        help_message = random.choice(notes_help_choices)
        self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
        self.dialogue_ui.show_dialogue()
    
    def check_email_management(self):
        # 检查并提供邮件管理帮助
        import random
        current_hour = int(time.strftime("%H"))
        
        # 根据时间提供不同的邮件管理帮助
        if 9 <= current_hour < 18:  # 工作时间
            email_help_choices = [
                "需要我帮你检查收件箱吗？我可以帮你整理邮件！",
                "想快速撰写邮件吗？我可以帮你模板化处理！",
                "需要我帮你设置邮件过滤规则，减少干扰吗？",
                "有重要邮件需要跟进吗？我可以帮你设置提醒！",
                "想批量处理邮件吗？我可以帮你！"
            ]
            help_message = random.choice(email_help_choices)
            self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
        else:  # 非工作时间
            email_help_choices = [
                "需要我帮你整理私人邮件吗？",
                "想设置邮件自动回复吗？我可以帮你！",
                "需要我帮你清理垃圾邮件吗？",
                "想检查是否有遗漏的重要邮件吗？"
            ]
            help_message = random.choice(email_help_choices)
            self.dialogue_ui.add_dialogue("ralsei", help_message, "happy")
        
        self.dialogue_ui.show_dialogue()
    
    def check_schedule_planning(self):
        # 检查并提供日程安排帮助
        import random
        
        schedule_help_choices = [
            "需要我帮你规划今日行程吗？",
            "想查看本周日程安排吗？我可以帮你！",
            "需要我帮你预约会议时间吗？",
            "想设置日程提醒吗？我可以帮你！",
            "需要我帮你调整日程安排吗？",
            "想为明天的行程做准备吗？我可以帮你！"
        ]
        
        help_message = random.choice(schedule_help_choices)
        self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
        self.dialogue_ui.show_dialogue()
    
    def check_project_management(self):
        # 检查并提供项目管理帮助
        import random
        
        project_help_choices = [
            "需要我帮你创建项目计划吗？",
            "想跟踪项目进度吗？我可以帮你！",
            "需要我帮你管理项目任务吗？",
            "想为项目设置里程碑吗？我可以帮你！",
            "需要我帮你生成项目报告吗？",
            "想查看项目成员的工作分配吗？我可以帮你！"
        ]
        
        help_message = random.choice(project_help_choices)
        self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
        self.dialogue_ui.show_dialogue()
    
    def check_work_efficiency(self):
        # 检查并提供工作效率帮助
        import random
        
        efficiency_help_choices = [
            "需要我帮你分析工作效率吗？我可以帮你找出瓶颈！",
            "想学习提高工作效率的技巧吗？我可以推荐！",
            "需要我帮你优化工作流程吗？",
            "想避免工作分心吗？我可以帮你设置专注模式！",
            "需要我帮你分配工作优先级吗？",
            "想了解你的工作时间分布吗？我可以帮你分析！"
        ]
        
        help_message = random.choice(efficiency_help_choices)
        self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
        self.dialogue_ui.show_dialogue()
    
    def check_document_collaboration(self):
        # 检查并提供文档协作帮助
        import random
        
        collaboration_help_choices = [
            "需要我帮你设置文档共享吗？",
            "想邀请团队成员协作编辑文档吗？我可以帮你！",
            "需要我帮你跟踪文档修改记录吗？",
            "想解决文档冲突吗？我可以帮你！",
            "需要我帮你设置文档访问权限吗？",
            "想获取最新的文档版本吗？我可以帮你！"
        ]
        
        help_message = random.choice(collaboration_help_choices)
        self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
        self.dialogue_ui.show_dialogue()
    
    def check_meeting_recording(self):
        # 检查并提供会议记录帮助
        import random
        
        recording_help_choices = [
            "需要我帮你记录会议内容吗？",
            "想将会议录音转换为文字吗？我可以帮你！",
            "需要我帮你整理会议要点吗？",
            "想生成会议纪要吗？我可以帮你！",
            "需要我帮你提取会议决策吗？",
            "想分享会议记录给团队成员吗？我可以帮你！"
        ]
        
        help_message = random.choice(recording_help_choices)
        self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
        self.dialogue_ui.show_dialogue()
    
    def check_work_life_balance(self):
        # 检查并提供工作生活平衡帮助
        import random
        current_hour = int(time.strftime("%H"))
        
        if 9 <= current_hour < 18:  # 工作时间
            balance_help_choices = [
                "工作了这么久，要不要休息一下？",
                "想喝点水吗？记得保持水分！",
                "需要我帮你设置休息提醒吗？",
                "要不要站起来活动一下身体？",
                "想听听音乐放松一下吗？"
            ]
            help_message = random.choice(balance_help_choices)
            self.dialogue_ui.add_dialogue("ralsei", help_message, "caring")
        else:  # 非工作时间
            balance_help_choices = [
                "今天工作辛苦了！要不要放松一下？",
                "想做些什么有趣的事情吗？",
                "需要我帮你规划休闲活动吗？",
                "要不要早点休息，养足精神？",
                "想不想和我聊聊天？"
            ]
            help_message = random.choice(balance_help_choices)
            self.dialogue_ui.add_dialogue("ralsei", help_message, "happy")
        
        self.dialogue_ui.show_dialogue()
    
    def create_person_name_table(self, names=None):
        # 在桌面上创建新的Excel表格并填入人名
        if not names:
            # 默认人名列表
            names = ["张三", "李四", "王五", "赵六", "钱七", "孙八"]
        
        try:
            # 创建新的Excel文件
            file_name = f"人名表_{int(time.time())}"
            excel_path = self.desktop_interaction.create_new_excel(file_name)
            
            if not excel_path:
                self.dialogue_ui.add_dialogue("ralsei", "创建Excel文件失败！", "sad")
                self.dialogue_ui.show_dialogue()
                return False
            
            # 写入表头
            self.desktop_interaction.excel_control(
                action="write_data",
                excel_path=excel_path,
                cell_range="A1",
                data="姓名"
            )
            
            # 写入人名数据
            for i, name in enumerate(names, start=2):
                self.desktop_interaction.excel_control(
                    action="write_data",
                    excel_path=excel_path,
                    cell_range=f"A{i}",
                    data=name
                )
            
            # 自动调整列宽
            self.desktop_interaction.excel_control(
                action="auto_fit",
                excel_path=excel_path
            )
            
            # 保存并关闭
            self.desktop_interaction.excel_control(
                action="save",
                excel_path=excel_path
            )
            
            # 向用户显示操作结果
            self.dialogue_ui.add_dialogue("ralsei", f"我已经在桌面上创建了名为'{file_name}.xlsx'的人名表！", "happy")
            self.dialogue_ui.add_dialogue("ralsei", f"表中包含了以下人名：{', '.join(names)}", "helpful")
            self.dialogue_ui.show_dialogue()
            
            return True
        except Exception as e:
            _log.warning(f"创建人名表失败: {e}")
            self.dialogue_ui.add_dialogue("ralsei", "创建人名表失败了...", "sad")
            self.dialogue_ui.show_dialogue()
            return False
    
    def handle_file_operation(self, user_input):
        # 处理文件操作指令
        try:
            user_input_lower = user_input.lower()
            
            # 检查是否是新建表格的指令
            if "新建" in user_input_lower and "表格" in user_input_lower:
                # 在桌面上新建Excel表格
                import os
                import win32com.client
                desktop_path = self.desktop_interaction.desktop_path
                
                # 创建新的Excel文件
                excel = win32com.client.Dispatch("Excel.Application")
                excel.Visible = False
                
                workbook = excel.Workbooks.Add()
                sheet = workbook.ActiveSheet
                
                # 保存文件
                new_file_name = "新建表格.xlsx"
                new_file_path = os.path.join(desktop_path, new_file_name)
                
                # 检查文件是否已存在，如果存在则添加数字后缀
                counter = 1
                while os.path.exists(new_file_path):
                    new_file_name = f"新建表格_{counter}.xlsx"
                    new_file_path = os.path.join(desktop_path, new_file_name)
                    counter += 1
                
                workbook.SaveAs(new_file_path)
                workbook.Close()
                excel.Quit()
                
                self.dialogue_ui.add_dialogue("ralsei", f"我已经在桌面上创建了一个新的Excel表格: {new_file_name}", "happy")
                self.dialogue_ui.show_dialogue()
                return True
            
            # 检查是否是往表格里填人名的指令
            elif "填人名" in user_input_lower and "表格" in user_input_lower:
                # 获取桌面上的Excel文件
                import os
                desktop_path = self.desktop_interaction.desktop_path
                try:
                    excel_files = [f for f in os.listdir(desktop_path) if f.endswith('.xlsx')]
                except Exception:
                    excel_files = []
                
                if not excel_files:
                    self.dialogue_ui.add_dialogue("ralsei", "桌面上没有找到Excel表格文件！", "sad")
                    self.dialogue_ui.show_dialogue()
                    return True
                
                # 选择最新的Excel文件
                try:
                    excel_files.sort(key=lambda f: os.path.getmtime(os.path.join(desktop_path, f)), reverse=True)
                except Exception as e:  # 修复：原先静默吞噬
                    _log.debug("main 防御性异常（已忽略）: %s", e)
                excel_file = excel_files[0]
                excel_path = os.path.join(desktop_path, excel_file)
                
                self.dialogue_ui.add_dialogue("ralsei", f"我将往表格: {excel_file} 里填写人名！", "happy")
                
                # 默认人名列表，可以根据需要扩展
                default_names = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十"]
                
                # 打开并填写表格
                result = self.fill_names_in_excel(excel_path, default_names)
                
                if result:
                    self.dialogue_ui.add_dialogue("ralsei", f"我已经成功往表格: {excel_file} 里填写了人名！", "happy")
                    self.dialogue_ui.add_dialogue("ralsei", f"我填写的人名是: {', '.join(default_names)}", "helpful")
                else:
                    self.dialogue_ui.add_dialogue("ralsei", f"往表格: {excel_file} 里填写人名失败了...", "sad")
                
                self.dialogue_ui.show_dialogue()
                return True
            
            # 检查是否是打开并修改表格的指令
            elif "打开" in user_input_lower and "表格" in user_input_lower:
                # 获取桌面上的Excel文件
                import os
                desktop_path = self.desktop_interaction.desktop_path
                try:
                    excel_files = [f for f in os.listdir(desktop_path) if f.endswith('.xlsx')]
                except Exception:
                    excel_files = []
                
                if not excel_files:
                    self.dialogue_ui.add_dialogue("ralsei", "桌面上没有找到Excel表格文件！", "sad")
                    self.dialogue_ui.show_dialogue()
                    return True
                
                # 选择第一个Excel文件（可以根据需要扩展为选择特定文件）
                excel_file = excel_files[0]
                excel_path = os.path.join(desktop_path, excel_file)
                
                self.dialogue_ui.add_dialogue("ralsei", f"我找到了桌面上的Excel文件: {excel_file}", "happy")
                
                # 检查是否需要修改表格
                if "对齐" in user_input_lower or "格子" in user_input_lower or "超出去" in user_input_lower:
                    self.dialogue_ui.add_dialogue("ralsei", f"我将为你打开并修改表格: {excel_file}", "helpful")
                    
                    # 打开并修改表格
                    result = self.fix_excel_format(excel_path)
                    
                    if result:
                        self.dialogue_ui.add_dialogue("ralsei", f"我已经成功修改了表格: {excel_file}！", "happy")
                        self.dialogue_ui.add_dialogue("ralsei", "我已经将任务名称和喜好对齐，并确保所有内容都完全放在格子里，没有超出！", "helpful")
                    else:
                        self.dialogue_ui.add_dialogue("ralsei", f"修改表格: {excel_file} 失败了...", "sad")
                else:
                    self.dialogue_ui.add_dialogue("ralsei", f"我将为你打开表格: {excel_file}", "happy")
                    
                    # 仅打开表格
                    import os
                    os.startfile(excel_path)
            
            # 修复：通用"打开 XX 文件/文件夹"指令——原来只有 Excel 相关分支，
            # 输入"打开 某个文件/文件夹"时不会打开任何东西（被当作普通闲聊）。
            elif "打开" in user_input_lower and "表格" not in user_input_lower:
                return self._open_desktop_item_by_name(user_input)
            
            self.dialogue_ui.show_dialogue()
            return True
        except Exception as e:
            _log.warning(f"处理文件操作指令失败: {e}")
            self.dialogue_ui.add_dialogue("ralsei", "处理文件操作指令失败了...", "sad")
            self.dialogue_ui.show_dialogue()
            return True

    def _open_desktop_item_by_name(self, user_input):
        """按名称匹配桌面文件/文件夹并触发 spell 打开流程。返回 True/False。"""
        import re
        # 去掉"打开/帮我打开/请打开"及结尾语气词
        text = re.sub(r'^(请|帮我)?(打开|启动|开启)\s*', '', user_input.strip())
        text = re.sub(r'[呢？。！!~～\s]+$', '', text).strip()
        if not text:
            self.dialogue_ui.add_dialogue("ralsei", "你想让我打开什么呀？", "curious")
            self.dialogue_ui.show_dialogue()
            return True
        # 刷新桌面元素后按名称匹配（真实图标 + 忽略扩展名 + 模糊包含）
        try:
            self.desktop_interaction.update_desktop_elements()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        target_lower = text.lower()
        matched = None
        for el in self.desktop_interaction.desktop_elements:
            name = el.get('name', '') or ''
            base = os.path.splitext(name)[0].lower()
            if name.lower() == target_lower or base == target_lower or (len(target_lower) >= 2 and target_lower in name.lower()):
                matched = el
                break
        if matched is None:
            # 兜底：直接按路径尝试（文本可能是绝对/相对路径）
            p = os.path.join(self.desktop_interaction.desktop_path, text)
            if os.path.exists(p):
                matched = {'type': 'folder' if os.path.isdir(p) else 'file', 'path': p}
        if matched is None:
            self.dialogue_ui.add_dialogue("ralsei", f"我在桌面上没找到叫「{text}」的东西呢，换个名字试试？", "a little confusion and cute")
            self.dialogue_ui.show_dialogue()
            return True
        # 走 spell 流程（走过去 → 施法 → 打开）
        path = matched['path']
        if matched.get('type') == 'folder' or os.path.isdir(path):
            self.open_folder(path)
        else:
            self.open_file(path)
        return True
    
    def fix_excel_format(self, excel_path):
        # 修复Excel表格格式
        # 修复：异常路径也必须释放 COM 资源（否则累积僵尸 EXCEL.EXE 并锁文件）
        excel = None
        workbook = None
        try:
            # 启动Excel并打开文件
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            
            workbook = excel.Workbooks.Open(excel_path)
            sheet = workbook.ActiveSheet
            
            # 获取使用的范围
            used_range = sheet.UsedRange
            rows = used_range.Rows.Count
            cols = used_range.Columns.Count
            
            # 设置所有单元格自动换行
            used_range.WrapText = True
            
            # 设置所有单元格居中对齐
            used_range.HorizontalAlignment = -4108  # xlCenter
            used_range.VerticalAlignment = -4108  # xlCenter
            
            # 自动调整所有列宽
            for col in range(1, cols + 1):
                sheet.Columns(col).AutoFit()
            
            # 自动调整所有行高
            for row in range(1, rows + 1):
                sheet.Rows(row).AutoFit()
            
            # 保存并关闭
            workbook.Save()
            
            return True
        except Exception as e:
            _log.warning(f"修复Excel格式失败: {e}")
            return False
        finally:
            try:
                if workbook is not None:
                    workbook.Close(SaveChanges=False)
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
            try:
                if excel is not None:
                    excel.Quit()
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
    
    def fill_names_in_excel(self, excel_path, names_list):
        # 往Excel表格中按顺序填写人名
        # 修复：1) 异常路径释放 COM；2) 表格已有数据时拒绝静默覆盖
        #（原实现无条件重写 A/B 两列并 Save()，会覆盖用户已有表格内容，属数据丢失风险）。
        excel = None
        workbook = None
        try:
            # 启动Excel并打开文件
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            
            workbook = excel.Workbooks.Open(excel_path)
            sheet = workbook.ActiveSheet
            
            # 覆盖保护：若已有数据（A2/B2 起任何单元格非空），拒绝覆盖并提示
            existing = False
            try:
                used = sheet.UsedRange
                if used.Rows.Count > 1 or used.Columns.Count > 1:
                    existing = True
            except Exception:
                existing = False
            if existing:
                _log.debug(f"文件已有内容，为避免覆盖用户数据，未填写人名: {excel_path}")
                return False
            
            # 设置表头
            sheet.Cells(1, 1).Value = "序号"
            sheet.Cells(1, 2).Value = "姓名"
            
            # 设置表头样式
            header_range = sheet.Range("A1:B1")
            header_range.Font.Bold = True
            header_range.HorizontalAlignment = -4108  # xlCenter
            header_range.VerticalAlignment = -4108  # xlCenter
            header_range.Interior.Color = 15773696  # 浅灰色背景
            
            # 填写人名数据
            for i, name in enumerate(names_list, start=2):
                sheet.Cells(i, 1).Value = i - 1  # 序号
                sheet.Cells(i, 2).Value = name  # 姓名
            
            # 设置数据区域样式
            data_range = sheet.Range(f"A1:B{len(names_list) + 1}")
            data_range.Borders.LineStyle = 1  # 添加边框
            
            # 自动调整列宽
            for col in range(1, 3):
                sheet.Columns(col).AutoFit()
            
            # 保存并关闭
            workbook.Save()
            
            return True
        except Exception as e:
            _log.warning(f"往Excel表格中填写人名失败: {e}")
            return False
        finally:
            try:
                if workbook is not None:
                    workbook.Close(SaveChanges=False)
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
            try:
                if excel is not None:
                    excel.Quit()
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
    
    def check_excel_table_needs(self):
        # 检查是否需要创建Excel表格
        import random
        
        table_help_choices = [
            "需要我帮你在桌面上创建一个新的Excel表格吗？",
            "想创建一个人名表吗？我可以帮你！",
            "需要我帮你整理数据到Excel表格中吗？",
            "想创建一个空白表格用于记录信息吗？"
        ]
        
        help_message = random.choice(table_help_choices)
        self.dialogue_ui.add_dialogue("ralsei", help_message, "helpful")
        self.dialogue_ui.show_dialogue()
    
    def open_browser_for_ralsei(self):
        # 为Ralsei打开浏览器，使用国内可用网站
        self.dialogue_ui.add_dialogue("ralsei", "我来帮你打开浏览器吧！", "happy")
        self.dialogue_ui.show_dialogue()
        self.desktop_interaction.open_browser("https://www.baidu.com")
    
    def check_video_apps(self):
        # 检查视频应用并做出反应
        import random
        
        # 识别视频应用窗口
        video_apps = self.identify_video_apps()
        
        if video_apps:
            # 随机选择一个视频应用窗口
            target_video = random.choice(video_apps)
            
            # 有一定概率观看视频
            if random.random() < 0.5:  # 50%的概率
                self.start_watching_video(target_video)
        else:
            # 没有视频应用，有一定概率主动打开视频
            if random.random() < 0.3:  # 30%的概率
                self.suggest_watching_video()
    
    def identify_video_apps(self):
        # 识别视频相关应用窗口
        windows = self.desktop_interaction.get_all_visible_windows()
        video_apps = []
        
        # 视频应用关键词，包含更多视频平台和应用
        video_keywords = [
            "YouTube", "哔哩哔哩", "B站", "腾讯视频", "爱奇艺", "优酷", 
            "芒果TV", "Netflix", "抖音", "快手", "视频", "腾讯视频", 
            "搜狐视频", "乐视视频", "PP视频", "风行视频", "西瓜视频", 
            "好看视频", "全民小视频", "梨视频", "土豆视频", "AcFun", 
            "A站", "斗鱼", "虎牙", "哔哩哔哩直播", "花椒直播", 
            "映客直播", "YY直播", "熊猫直播", "龙珠直播", "企鹅电竞",
            "Twitch", "Disney+", "HBO Max", "Prime Video", "Hulu",
            "Vimeo", "TikTok", "Snapchat", "Instagram", "Facebook Watch"
        ]
        
        for window in windows:
            # 检查窗口标题是否包含视频关键词
            if any(keyword in window['title'] for keyword in video_keywords):
                video_apps.append(window)
            # 检查窗口类名，识别常见视频播放器
            elif 'class_name' in window and window['class_name']:
                player_class_names = [
                    "WMPlayerApp", "VLC media player", "mpv", "PotPlayer", 
                    "QQPlayer", "KMPlayer", "GOM Player", "MediaPlayerClassic",
                    "MPV", "SMPlayer", "MPlayer", "Totem", "XBMC", "Kodi"
                ]
                if any(class_name in window['class_name'] for class_name in player_class_names):
                    video_apps.append(window)
        
        return video_apps
    
    def start_watching_video(self, video_app):
        # 开始观看视频
        import random
        
        self.is_watching_video = True
        self.video_start_time = time.time()
        self.video_platform = video_app['title']
        
        # 随机选择视频类型
        video_types = self.video_preferences.copy()
        video_type = random.choice(video_types)
        
        # 生成视频标题
        self.video_title = f"{video_type}相关视频"
        
        # 添加到观看历史
        self.video_watch_history.append({
            "title": self.video_title,
            "platform": self.video_platform,
            "start_time": self.video_start_time,
            "duration": 0
        })
        
        # 限制历史记录数量
        if len(self.video_watch_history) > 20:
            self.video_watch_history.pop(0)
        
        # 显示观看视频的消息
        watch_messages = [
            f"哇！我正在观看{self.video_platform}上的{self.video_title}，看起来很有趣呢！",
            f"这个{video_type}视频太吸引人了！我要仔细看看。",
            f"{self.video_platform}上的视频真好看，我沉浸进去了！",
            f"这个{video_type}内容真不错，我要继续观看。"
        ]
        message = random.choice(watch_messages)
        self.dialogue_ui.add_dialogue("ralsei", message, "happy")
        self.dialogue_ui.show_dialogue()
        
        # 确保Ralsei在视频窗口上，正面对着视频
        video_rect = QRect(video_app['x'], video_app['y'], video_app['width'], video_app['height'])
        
        # 计算视频窗口中心位置，让Ralsei面向视频
        video_center_x = video_app['x'] + video_app['width'] // 2
        video_center_y = video_app['y'] + video_app['height'] // 2
        
        # 调整Ralsei位置到视频窗口内，确保正对着视频中心
        # 确保Ralsei在视频窗口内，而不是在窗口下方
        ralsei_x = video_center_x - self.width() // 2
        ralsei_y = video_center_y - self.height() // 2
        
        # 确保Ralsei在视频窗口范围内，距离边缘至少20像素
        ralsei_x = max(video_rect.left() + 20, min(video_rect.right() - self.width() - 20, ralsei_x))
        ralsei_y = max(video_rect.top() + 20, min(video_rect.bottom() - self.height() - 20, ralsei_y))
        
        # 确保Ralsei位置在屏幕范围内
        screen_geometry = QApplication.desktop().availableGeometry()
        ralsei_x = max(0, min(screen_geometry.width() - self.width(), ralsei_x))
        ralsei_y = max(0, min(screen_geometry.height() - self.height(), ralsei_y))
        
        # 移动Ralsei到视频窗口内
        self.move(ralsei_x, ralsei_y)
        
        # 更新当前窗口信息，确保Ralsei在视频窗口上
        self.current_window = video_app
        self.last_window_rect = (video_app['x'], video_app['y'], video_app['width'], video_app['height'])
        self.window_level = video_app['z_order']
        
        # 暂停移动，专注观看视频
        self.is_moving = False
        self.idle_timer = 0
        self.max_idle_duration = random.uniform(10, 30)  # 观看时间10-30秒，减少观看时间，让Ralsei能继续移动
        
        # 确保Ralsei正对着视频 - 根据视频中心位置计算方向
        # 获取Ralsei中心位置
        ralsei_center_x = ralsei_x + self.width() // 2
        ralsei_center_y = ralsei_y + self.height() // 2
        
        # 计算方向向量
        dx = video_center_x - ralsei_center_x
        dy = video_center_y - ralsei_center_y
        
        # 根据方向向量确定面向
        if abs(dx) > abs(dy):
            # 水平方向为主
            if dx > 0:
                self.current_direction = "right"  # 向右面对视频
            else:
                self.current_direction = "left"   # 向左面对视频
        else:
            # 垂直方向为主
            if dy > 0:
                self.current_direction = "down"   # 向下面对视频
            else:
                self.current_direction = "up"     # 向上面对视频
        
        # 更新动画为观看动画，使用合适的动画
        self.change_animation(f"idle", force=True)  # 使用idle动画作为观看动画
        
        # 检查是否是B站窗口，如果是，移动并调整大小
        if "哔哩哔哩" in video_app['title'] or "bilibili" in video_app['title'] or "B站" in video_app['title']:
            self.desktop_interaction.move_and_resize_bilibili_window()
        
        # 开始真正观看视频
        self._start_video_watching_loop()
    
    def _start_video_watching_loop(self):
        # 视频观看循环，模拟真正观看视频的行为
        self.video_watching_timer = QTimer(self)
        self.video_watching_timer.timeout.connect(self._update_video_watching)
        self.video_watching_timer.start(5000)  # 每5秒更新一次观看状态
    
    def _update_video_watching(self):
        # 更新视频观看状态
        if not self.is_watching_video:
            self.video_watching_timer.stop()
            return
        
        # 检查当前时间，最多晚上12:00必须关闭
        # 修复：原条件 (hour>=23 and minute>=55) 只在 23:55-23:59 为真，
        # 跨过午夜后 hour==0 永不满足，"深夜自动关闭"失效。23 点后或凌晨 6 点前都视为深夜。
        current_hour = int(time.strftime("%H"))
        current_minute = int(time.strftime("%M"))
        if current_hour >= 23 or current_hour < 6:
            # 快到12点了，准备关闭
            self.dialogue_ui.add_dialogue("ralsei", "时间不早了，我该睡觉了，晚安！", "tired")
            self.dialogue_ui.show_dialogue()
            self.stop_watching_video()
            self.close_bilibili()
            self.enter_sleep_mode()
            return
        
        # 随机做出一些观看反应
        import random
        if random.random() < 0.1:  # 10%的概率做出反应
            self._react_to_video()
    
    def _react_to_video(self):
        # 观看视频时的随机反应
        import random
        reactions = [
            ("haha！这个好好笑！", "happy", "laugh", 15),
            ("哇！这个太厉害了！", "surprised", "surprised", 10),
            ("嗯...挺有意思的。", "happy", "smile", 5),
            ("嘿嘿，我也想试试！", "excited", "happy", 12),
            ("这段音乐真好听~", "happy", "dance", 8),
            ("啊！吓我一跳！", "surprised", "surprised", 15),
            ("太好看了，根本停不下来！", "excited", "happy", 10),
            ("这个角色好可爱啊~", "happy", "smile", 8),
        ]
        msg, emotion, anim, happy_delta = random.choice(reactions)
        self.dialogue_ui.add_dialogue("ralsei", msg, emotion)
        self.dialogue_ui.show_dialogue()
        # 修复：原来固定 add_emotion("happy")，忽略元组里的 'surprised'/'excited' 等情绪；
        # 且直接改 self.emotions 与 emotion_system 双通道不一致。统一按反应情绪更新。
        self.emotion_system.add_emotion(emotion, happy_delta)
        # 同步旧版情绪字典（happiness 以 50 为中性点）
        if emotion == 'happy':
            self.emotions["happiness"] = min(100.0, self.emotions.get("happiness", 50.0) + happy_delta)
        elif emotion == 'surprised':
            self.emotions["surprise"] = min(100.0, self.emotions.get("surprise", 0.0) + happy_delta)
        elif emotion == 'excited':
            self.emotions["excitement"] = min(100.0, self.emotions.get("excitement", 0.0) + happy_delta)
        self.play_animation_once(anim)
    
    def close_bilibili(self):
        # 关闭B站浏览器窗口
        # 查找并关闭B站相关窗口
        windows = self.desktop_interaction.get_all_visible_windows()
        for window in windows:
            if any(keyword in window['title'] for keyword in ["哔哩哔哩", "B站", "bilibili"]):
                self.desktop_interaction.close_window(window['title'])
                break
    
    def enter_sleep_mode(self):
        # 进入睡眠状态
        self.is_sleeping = True
        self.is_moving = False
        self.change_animation("idle", force=True)  # force=True 确保即使冷却期内也切换
        sleep_msgs = ["zzz... 晚安，做个好梦！", "zzz... 我困了...", "zzz... 好舒服..."]
        self.dialogue_ui.add_dialogue("ralsei", random.choice(sleep_msgs), "sleepy")
        self.dialogue_ui.show_dialogue()
        # 重置各种状态
        self.is_watching_video = False
        self.is_moving = False
        self.is_jumping = False
        self.is_falling = False
        self.idle_timer = 0
        self.max_idle_duration = 3600.0  # 睡眠1小时
    
    def stop_watching_video(self):
        # 停止观看视频
        if self.is_watching_video:
            self.is_watching_video = False
            duration = time.time() - self.video_start_time
            
            # 更新观看历史
            if self.video_watch_history and self.video_watch_history[-1]['title'] == self.video_title:
                self.video_watch_history[-1]['duration'] = duration
            
            # 显示停止观看的消息
            stop_messages = [
                "这个视频看完了，我要继续活动活动！",
                "视频结束了，我该做些其他事情了。",
                "哇，那个视频真好看！不过我该继续移动了。",
                "视频很有趣，但我需要休息一下眼睛了。"
            ]
            import random
            message = random.choice(stop_messages)
            self.dialogue_ui.add_dialogue("ralsei", message, "content")
            self.dialogue_ui.show_dialogue()
            
            # 恢复正常移动
            self.randomize_movement_pattern()
            self.is_moving = True
            # 使用随机化的最大空闲时间，而不是未定义的base_max_idle_duration
            self.max_idle_duration = random.uniform(0.5, 3.0)
            
            # 停止视频观看循环
            if hasattr(self, 'video_watching_timer'):
                self.video_watching_timer.stop()
    
    def suggest_watching_video(self):
        # 建议观看视频，只使用B站
        import random
        
        # 随机选择视频类型
        video_types = self.video_preferences.copy()
        video_type = random.choice(video_types)
        
        # 固定使用B站
        platform = "哔哩哔哩"
        
        # 显示建议消息
        suggestion_messages = [
            f"我想看点{video_type}视频，要不要一起看？",
            f"最近听说{platform}上有很好看的{video_type}视频，我想去看看！",
            f"无聊了，要不要打开{platform}看些{video_type}内容？",
            f"我想放松一下，看个{video_type}视频怎么样？"
        ]
        message = random.choice(suggestion_messages)
        self.dialogue_ui.add_dialogue("ralsei", message, "excited")
        self.dialogue_ui.show_dialogue()
        
        # 有一定概率直接打开视频
        if random.random() < 0.5:
            # 直接打开B站热门视频页面，在新窗口打开
            self.desktop_interaction.open_browser(f"https://www.bilibili.com/v/popular/all", new_window=True)
            # 打开视频后，移动并调整B站窗口大小
            self.desktop_interaction.move_and_resize_bilibili_window()
            # 设置为正在观看视频状态
            # 修复：此前只设 is_watching_video/video_start_time，未设 video_title、未启动
            # 观看定时器、未设 max_idle_duration → check_entertainment_needs 用残留旧值
            # （可能仅 0.5~3 秒）几秒内就判定"看完了"关掉视频，观看历史也因 video_title=="" 丢失。
            self.is_watching_video = True
            self.video_start_time = time.time()
            self.video_title = "B站热门视频"
            self.video_platform = platform
            # 观看时长：30~90 秒后再自然结束
            self.max_idle_duration = random.uniform(30.0, 90.0)
            # 启动 5 秒 tick 的观看循环（深夜自动关闭 / 随机反应）
            try:
                if not hasattr(self, 'video_watching_timer') or self.video_watching_timer is None:
                    self._start_video_watching_loop()
                elif not self.video_watching_timer.isActive():
                    self.video_watching_timer.start(5000)
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
    
    def move_to_edge_and_shrink(self):
        # 将Ralsei移动到屏幕边缘并缩小（非阻塞 QTimer 动画）
        from PyQt5.QtCore import QTimer
        
        # 获取屏幕大小
        screen_geom = self.screen().geometry()
        screen_width = screen_geom.width()
        screen_height = screen_geom.height()
        
        # 目标位置：屏幕右下角，距离边缘50像素
        target_x = screen_width - self.width() - 50
        target_y = screen_height - self.height() - 50
        
        # 获取当前位置
        current_x = self.pos().x()
        current_y = self.pos().y()
        
        # 计算移动距离
        dx = target_x - current_x
        dy = target_y - current_y
        
        # 使用 QTimer 实现非阻塞平滑移动
        total_steps = 50
        state = {'step': 0}

        def _move_step():
            state['step'] += 1
            i = state['step']
            if i >= total_steps:
                # 最后一步：精确到达目标位置
                self.move(target_x, target_y)
                # 缩小到合适大小（80%）
                self.resize(int(self.width() * 0.8), int(self.height() * 0.8))
                self.move(target_x, target_y)
                return
            # 计算当前步骤的位置
            new_x = current_x + dx * i / total_steps
            new_y = current_y + dy * i / total_steps
            self.move(int(new_x), int(new_y))
            # 安排下一步
            QTimer.singleShot(20, _move_step)

        _move_step()
    
    def check_entertainment_needs(self):
        # 检查Ralsei自己的娱乐需求
        # 修复（guard）：睡眠中 / 游戏中 / 被拖拽中不插话（update_ai 每 3 秒调用，
        # 30% 概率会频繁打断）；对话框不可见时也不建议（避免突然弹窗）。
        try:
            if getattr(self, 'is_sleeping', False):
                return
            if getattr(self, 'game_state', {}).get('is_playing'):
                return
            if getattr(self, '_is_being_dragged', False):
                return
            if not self.dialogue_ui.isVisible():
                return
            # 正在给用户打字（含 AI 思考/回复中）不插话，避免打断当前消息
            if getattr(self.dialogue_ui, 'is_typing', False):
                return
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        current_hour = int(time.strftime("%H"))
        import random
        
        # 如果正在观看视频，检查是否结束
        if self.is_watching_video:
            elapsed = time.time() - self.video_start_time
            if elapsed > self.max_idle_duration:
                self.stop_watching_video()
            return
        
        # 根据时间和情绪决定是否需要娱乐
        if random.random() < 0.3:  # 30%的概率
            # 检查视频应用，有机会观看视频
            if random.random() < 0.5:  # 50%的概率选择视频娱乐
                self.check_video_apps()
            else:
                # 其他娱乐方式
                if 9 <= current_hour < 18:  # 工作时间
                    # 工作时间的娱乐建议
                    entertainment_suggestions = [
                        "工作了这么久，要不要休息一下？我可以陪你玩个小游戏！",
                        "需要放松一下吗？我来给你讲个笑话吧！",
                        "要不要听首放松的音乐，缓解一下工作压力？",
                        "工作累了吗？我来给你展示一个有趣的小魔术！"
                    ]
                else:  # 休闲时间
                    # 休闲时间的娱乐建议
                    entertainment_suggestions = [
                        "现在是休闲时间！要不要一起玩个小游戏？",
                        "我来给你推荐一部好看的电影吧！",
                        "想不想听我唱首歌？虽然我唱歌可能不太好听...",
                        "要不要我给你讲个关于Deltarune的故事？",
                        "想不想一起玩猜谜语游戏？我准备了很多有趣的谜语！"
                    ]
                
                suggestion = random.choice(entertainment_suggestions)
                self.dialogue_ui.add_dialogue("ralsei", suggestion, "excited")
                self.dialogue_ui.show_dialogue()
    
    def tell_joke(self):
        # 讲笑话功能
        jokes = [
            "为什么程序员总是分不清万圣节和圣诞节？因为 Oct 31 == Dec 25！",
            "我有一个关于算法的笑话，但它太复杂了，只有O(log n)的人能听懂。",
            "为什么电脑喜欢吃零食？因为它们有很多字节！",
            "为什么Ralsei喜欢在电脑上玩？因为他是个像素宠物！",
            "什么东西有键盘却不能打字？答案是钢琴！",
            "为什么书总是很有意见？因为它们有很多页（意见）！"
        ]
        import random
        joke = random.choice(jokes)
        self.dialogue_ui.add_dialogue("ralsei", joke, "happy")
        self.dialogue_ui.show_dialogue()
    
    def suggest_game(self):
        # 推荐游戏功能
        games = [
            "要不要玩个猜数字游戏？我想一个1-100的数字，你猜猜看！",
            "我们来玩石头剪刀布吧！你出什么？",
            "想不想玩2048游戏？这是个很有趣的数字游戏！",
            "要不要玩个文字游戏？我们轮流说一个词，必须以上一个词的最后一个字开头！",
            "我们来玩猜谜语吧！我出谜面，你猜谜底！"
        ]
        import random
        game = random.choice(games)
        self.dialogue_ui.add_dialogue("ralsei", game, "excited")
        self.dialogue_ui.show_dialogue()
    
    @monitor_performance
    def update_ai(self):
        # 更新AI状态
        self.pet_ai.update_state()
        
        # 检查Ralsei自己的娱乐需求
        self.check_entertainment_needs()
        
        # 本地 AI 状态轮询（协议留白端口）：
        # - HTTPLocalAI 默认骨架 / LocalAIStub 的 commands_endpoint 为 None，
        #   get_commands() 返回 None → 不发起任何轮询。
        # - 因此启用本地对话模型（Ollama / OpenAI 兼容，走 chat_with_ai 对话）后，
        #   不会每 3 秒 10% 概率把系统状态塞给对话模型（排队+打扰），
        #   模型未运行/模型名错误时也不会再弹"不太舒服"的错误框。
        # - 只有自定义实现（register_provider 或子类覆盖 *_endpoint）声明了命令
        #   协议端点后，此轮询才会真正发送，并由 _handle_agent_commands 消费。
        try:
            _cli = getattr(self, 'api_client', None)
            if (_cli is not None and getattr(_cli, 'enabled', False)
                    and callable(getattr(_cli, 'get_commands', None))):
                _cmds = _cli.get_commands(self.get_system_info())
                if _cmds and isinstance(_cmds, dict):
                    self._handle_agent_commands(_cmds)
        except Exception as _e:
            _log.warning(f"[本地AI] 状态轮询异常(忽略，不影响运行): {_e}")

        # 本地 AI 行动驱动：让模型周期性地给 Ralsei 挑一个白名单动作
        # （跳舞/唱歌/散步/睡觉/说句话…）。一切失败静默回退规则行为。
        try:
            if getattr(self, 'ai_driver', None) is not None:
                self.ai_driver.tick(time.time())
        except Exception as _e:
            _log.warning(f"[本地AI] 行动驱动异常(忽略): {_e}")

    def _handle_agent_commands(self, cmds):
        """消费自定义 agent 返回的命令 dict（本地 AI 协议留白处的接收端）。

        结构约定（与 api_client 文档一致）：
            {'reply': '想说的话',
             'commands': [{'action': ..., 'args': {...}}, ...]}
        - reply：直接让 Ralsei 说出来。
        - commands：逐个交给 api_client.execute_command() 处理；返回里带
          reply 时也说给用户。未约定的命令一律静默忽略，绝不崩溃。
        """
        try:
            reply = cmds.get('reply')
            if reply:
                self.dialogue_ui.add_dialogue("ralsei", str(reply), "happy")
                self.dialogue_ui.show_dialogue()
            for c in cmds.get('commands') or []:
                if not isinstance(c, dict):
                    continue
                try:
                    res = self.api_client.execute_command(c)
                except Exception:
                    res = None
                if res and isinstance(res, dict) and res.get('reply'):
                    self.dialogue_ui.add_dialogue("ralsei", str(res['reply']), "happy")
                    self.dialogue_ui.show_dialogue()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        
    @monitor_performance
    def update_stats(self):
        # 更新精力和饥饿度
        self.energy_hunger.update_stats()
        # 更新情绪状态
        self.emotion_system.update()
        # 更新记忆系统
        self.memory_system.update()
        # 更新社交成长系统
        # 根据情绪更新动画
        self.update_animation_by_emotion()
        # 文字游戏（石头剪刀布/猜数字）超时自动结束：
        # 修复边界——游戏进行中玩家若关闭对话框不再输入，game_state.is_playing 会
        # 一直为 True，触发 _agent_busy_flags/_in_critical 让 Ralsei 永久静止不动。
        # 5 分钟无输入自动结束并复位。
        try:
            _gs = self.game_state
            if _gs.get('is_playing'):
                _gt = _gs.get('game_type')
                if _gt in ('rock_paper_scissors', 'guess_number'):
                    _started = _gs.get('started_at', 0.0)
                    if time.time() - _started > 300.0:
                        _log.debug(f"[游戏] {_gt} 超过 5 分钟无输入，自动结束")
                        if _gt == 'rock_paper_scissors':
                            self.end_rock_paper_scissors()
                        else:
                            self.end_guess_number()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        
    def update_animation_by_emotion(self):
        # 根据当前情绪更新动画，保持情绪和姿势的自主性
        # —— 施法中 / 游戏中 / 移动中 / 物理状态中：冻结情绪动画切换 ——
        # 修复：此前只有 spell/game 保护，缺少移动保护——Ralsei 正在走路时，
        # 10% 概率的强制情绪动画切换（force=True 的 sing/dance 等）会打断走路动画，
        # 造成"走着走着突然切情绪动画"的动画错乱。
        if getattr(self, '_spell_stage', None) is not None:
            return
        if getattr(self, 'game_state', {}).get('is_playing'):
            return
        if (getattr(self, 'is_moving', False) or getattr(self, 'is_jumping', False)
                or getattr(self, 'is_falling', False) or getattr(self, 'is_recovering', False)):
            return
        current_emotion, emotion_value = self.emotion_system.get_current_emotion()
        intensity = abs(emotion_value)
        
        # 获取适合当前情绪的动画
        emotion_animation = self.emotion_system.get_animation_for_emotion(current_emotion, intensity)
        
        # 只有在情绪强度足够高时才切换动画，保持动画的稳定性
        if emotion_animation and emotion_animation != self.current_animation and intensity > 20:
            # 根据情绪强度决定是否强制切换动画
            force_change = intensity > 50
            self.change_animation(emotion_animation, force=force_change)
        
        # 确保情绪强度足够高时，动画能够反映当前情绪
        # 同时保持一定的随机性，让Ralsei的行为更自然
        import random
        if intensity > 30 and random.random() < 0.1:  # 10%的概率随机切换到情绪动画
            self.change_animation(emotion_animation, force=True)
        
    def check_initiate_dialogue(self):
        # 检查是否发起对话
        # 修复（guard）：睡眠中 / 游戏中（躲猫猫藏匿 Ralsei 已 hide，弹对话会挡玩家）
        # 不主动插话；用户在对话框打字时不打断。
        try:
            if self.is_sleeping:
                return
            if getattr(self, 'game_state', {}).get('is_playing'):
                return
            dui = self.dialogue_ui
            if hasattr(dui, '_is_user_inputting') and dui._is_user_inputting():
                return
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        # 主动搭话（低概率，should_initiate_conversation 内部控制频率）——允许弹窗
        if self.dialogue_system.should_initiate_conversation():
            message = self.dialogue_system.initiate_conversation()
            self.dialogue_ui.add_dialogue("ralsei", message, "happy")
            self.dialogue_ui.show_dialogue()
        
        # 检查是否有有趣的文件（与Deltarune或Undertale相关）
        self.check_interesting_files()
        
        # 修复：办公/娱乐帮助类只在对话框可见时执行（用户主动打开对话框 = 在互动），
        # 并且每轮最多 1 个——原实现对话框隐藏时也随机弹 1-3 个"需要我帮你…"，是
        # 高频打扰源。主动搭话已在上方独立处理。
        if self.dialogue_ui.isVisible():
            import random
            check_functions = [
                self.check_browser_windows,
                self.check_ppt_windows,
                self.check_excel_windows,
                self.check_word_windows,
                self.check_task_management,
                self.check_time_tracking,
                self.check_meeting_reminders,
                self.check_file_organization,
                self.check_quick_notes,
                self.check_email_management,
                self.check_schedule_planning,
                self.check_project_management,
                self.check_work_efficiency,
                self.check_document_collaboration,
                self.check_meeting_recording,
                self.check_work_life_balance,
                self.check_excel_table_needs
            ]
            func = random.choice(check_functions)
            try:
                func()
            except Exception as e:
                _log.warning(f"[办公检查] {func.__name__} 异常: {e}")
    
    
        
    def check_weather_response(self):
        # 检查天气并做出响应
        # 修复：定时器每 5 分钟触发一次，原实现无条件播报当前天气 → 同一句
        # "今天天气真好呀！"每小时重复 12 遍，还会打断打字/游戏。只在天气
        # 条件实际变化时播报；相同天气至少间隔 1 小时才允许再次播报。
        try:
            weather_key = self.weather_system.get_current_weather()
        except Exception:
            weather_key = None
        if weather_key is None:
            return  # 获取不到天气状态时保持安静
        changed = weather_key != getattr(self, "_last_weather_key", None)
        last = getattr(self, "_last_weather_announce", None)
        elapsed_ok = last is None or (time.time() - last) >= 3600
        if not changed and not elapsed_ok:
            return
        self._last_weather_key = weather_key
        self._last_weather_announce = time.time()
        weather_response = self.weather_system.get_weather_response()
        self.dialogue_ui.add_dialogue("ralsei", weather_response["dialogue"], weather_response["mood"])
        # 修复：原来直接赋值 self.current_animation，绕过 change_animation 的冷却/优先级/
        # spell 阶段拦截，且下一帧就被状态机覆盖，天气动画实际不切换。
        self.change_animation(weather_response["animation"], force=True)
        
    def moveEvent(self, event):
        super().moveEvent(event)

    def paintEvent(self, event):
        # 绘制透明背景
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QBrush(QColor(0, 0, 0, 0)))
        
    def get_ralsei_body_part(self, pos):
        # 根据鼠标位置确定点击的Ralsei身体部位
        # 使用相对位置百分比来适配不同大小的图像
        
        # 获取当前精灵图像的尺寸
        sprite_width = self.sprite_label.width()
        sprite_height = self.sprite_label.height()

        # 防御：精灵 label 尚未布局/无 pixmap 时宽高为 0，直接除零会崩溃
        if sprite_width <= 0 or sprite_height <= 0:
            return "whole_body"

        # 将像素位置转换为相对百分比 (0-100)
        rel_x = (pos.x() / sprite_width) * 100
        rel_y = (pos.y() / sprite_height) * 100
        
        # 定义Ralsei身体部位的相对区域（基于典型的Ralsei图像比例）
        # 格式：(部位名称, 最小x%, 最小y%, 最大x%, 最大y%)
        body_parts = [
            # 耳朵区域
            ("ear", 0, 0, 30, 40),  # 左耳
            ("ear", 70, 0, 100, 40),  # 右耳
            
            # 头发区域
            ("hair", 25, 10, 75, 50),
            
            # 面部区域
            ("face", 30, 30, 70, 60),
            
            # 肚子区域
            ("belly", 35, 60, 65, 80),
            
            # 躯干区域
            ("body", 20, 50, 80, 80),
            
            # 腿部区域
            ("legs", 30, 80, 70, 100),
            
            # 手臂区域
            ("arm", 0, 40, 30, 70),  # 左臂
            ("arm", 70, 40, 100, 70),  # 右臂
            
            # 肩膀区域
            ("shoulder", 15, 45, 35, 60),  # 左肩
            ("shoulder", 65, 45, 85, 60),  # 右肩
            
            # 全身区域
            ("whole_body", 0, 0, 100, 100)
        ]
        
        # 检查是否在某个部位区域内
        for part_name, min_x, min_y, max_x, max_y in body_parts:
            if min_x <= rel_x <= max_x and min_y <= rel_y <= max_y:
                return part_name
        
        # 默认返回全身
        return "whole_body"
    
    def mousePressEvent(self, event):
        # 鼠标按下事件
        if event.button() == Qt.LeftButton:
            # 修复：用户触摸/按下 → 打断施法（_spell_touched_flag 之前从未被置 True，
            # "触摸打断施法"检查恒 False，施法无法被用户点击中断）
            if getattr(self, '_spell_stage', None) is not None:
                self._spell_touched_flag = True
            # 修复：按下即停走并标记拖拽——否则 Ralsei 走路中被抓取时 update_movement
            # 仍每 30ms 向旧 target_pos 平移（与用户拖动反向拉扯，"抓不住/自己跑"）。
            # _is_being_dragged 在 mouseMoveEvent 里才置真太晚（按住不动瞬间无保护）。
            self.is_moving = False
            self.current_speed_x = 0
            self.current_speed_y = 0
            self._is_being_dragged = True
            # 修复：躲猫猫"走路阶段"（moving_to_center / moving_to_folder，无 spell 运行）
            # 一旦被用户按下（is_moving 被清 False 且不恢复）就永久卡死且无法退出。
            # 这里直接结束游戏，由 _abort_hide_and_seek 统一清理障碍与状态。
            if getattr(self, '_hide_stage', None) in ('moving_to_center', 'moving_to_folder'):
                QTimer.singleShot(0, lambda: self._abort_hide_and_seek(reason='user_interrupt'))
            # 拖动窗口，无论点击位置
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            # 检查是否点击了Ralsei
            if self.sprite_label.geometry().contains(event.pos()):
                # splat 形态下点击 → 播放 snd_splat.wav
                if getattr(self, 'is_splat', False):
                    try:
                        self.sound_manager.play_splat()
                    except Exception as e:  # 修复：原先静默吞噬
                        _log.debug("main 防御性异常（已忽略）: %s", e)
                    self.dialogue_ui.add_dialogue("ralsei", "别戳我啦...我都扁了...", "sad")
                    self.dialogue_ui.show_dialogue()
                    event.accept()
                    return
                # 点击了Ralsei
                self.pet_ai.react_to_event("user_clicked", None)
                
                # 更新互动时间
                self.last_interaction_time = time.time()
                
                # 检测点击的身体部位
                clicked_part = self.get_ralsei_body_part(event.pos())
                current_time = time.time()
                
                # 初始化检测状态
                if not hasattr(self, '_pet_detection_state'):
                    self._pet_detection_state = {
                        'on_ralsei': True,
                        'last_pos': event.pos(),
                        'movement_history': [],
                        'last_pet_time': 0,
                        'pet_count': 0,
                        'current_part': clicked_part,
                        'pet_attempts': 0,
                        'pet_success': False,
                        'click_count': 0,
                        'last_click_time': current_time,
                        'click_part': clicked_part,
                        'press_start_time': current_time,
                        'press_start_pos': event.pos(),
                        'is_pressing': True
                    }
                else:
                    # 更新长按状态
                    self._pet_detection_state['press_start_time'] = current_time
                    self._pet_detection_state['press_start_pos'] = event.pos()
                    self._pet_detection_state['is_pressing'] = True
                    self._pet_detection_state['click_part'] = clicked_part
                
                # 点击计数（用于不楞耳朵）
                if clicked_part == "ear":
                    # 检查是否是连续点击
                    if current_time - self._pet_detection_state['last_click_time'] < 0.5:
                        self._pet_detection_state['click_count'] += 1
                        _log.debug(f"连续点击耳朵: {self._pet_detection_state['click_count']}次")
                        
                        # 连续点击3次触发不楞耳朵
                        if self._pet_detection_state['click_count'] >= 3:
                            _log.debug("不楞不楞耳朵！")
                            self.emotion_system.add_emotion("happy", 40)
                            self.emotion_system.add_emotion("excited", 20)
                            self.play_animation_once("laugh")
                            self.dialogue_ui.add_dialogue("ralsei", "哎呀！别不楞我的耳朵啦！", "surprised")
                            self.dialogue_ui.show_dialogue()
                            # 重置点击计数
                            self._pet_detection_state['click_count'] = 0
                    else:
                        # 重置点击计数
                        self._pet_detection_state['click_count'] = 1
                        
                    # 更新最后点击时间
                    self._pet_detection_state['last_click_time'] = current_time
                
                # 根据不同部位触发不同效果
                if clicked_part == "body":
                    # 轻推躯干
                    _log.debug("轻推了Ralsei的躯干！")
                    self.emotion_system.add_emotion("happy", 20)
                    self.emotion_system.add_emotion("curious", 15)
                    self.play_animation_once("surprised")
                    self.dialogue_ui.add_dialogue("ralsei", "哎呀！你推我干嘛？", "surprised")
                    self.dialogue_ui.show_dialogue()
                elif clicked_part == "shoulder":
                    # 轻推肩膀
                    _log.debug("轻推了Ralsei的肩膀！")
                    self.emotion_system.add_emotion("happy", 20)
                    self.emotion_system.add_emotion("curious", 10)
                    self.play_animation_once("look_up")
                    self.dialogue_ui.add_dialogue("ralsei", "嗯？有什么事吗？", "curious")
                    self.dialogue_ui.show_dialogue()
                else:
                    # 显示点击回应
                    short_responses = ["嘿嘿！", "你好呀！", "很高兴见到你！", "要一起玩吗？"]
                    self.dialogue_ui.add_dialogue("ralsei", random.choice(short_responses), "happy")
                    self.dialogue_ui.show_dialogue()
                # 即使点击了Ralsei，也允许拖拽
                event.accept()
        elif event.button() == Qt.RightButton:
            # 右键点击：弹出互动菜单（聊天/玩游戏/喂食/抚摸/配置等）。
            # 修复：此前右键只切换对话框显示，而 show_interaction_menu 从未被调用，
            # 聊天/游戏/喂食/抚摸等菜单功能全部无入口（死代码）。
            # 现在右键弹菜单；对话框的显示/隐藏改由"双击 sprite 外区域"触发。
            try:
                self.show_interaction_menu(event.globalPos())
            except Exception as e:
                _log.warning(f"显示互动菜单失败: {e}")
                # 兜底：菜单失败时退回原来的切对话框行为
                if self.dialogue_ui.isVisible():
                    self.dialogue_ui.hide_dialogue()
                else:
                    self.dialogue_ui.show_dialogue()
            event.accept()
    
    def start_following_mouse(self):
        """开始追着鼠标跑"""
        self.is_following_mouse = True
        # 修复：记录开始时间，配合 update_movement 里的超时自动停止——
        # 否则菜单/指令触发后若用户不再操作，Ralsei 会永远追鼠标。
        self._follow_mouse_start = time.time()
        self.dialogue_ui.add_dialogue("ralsei", "我来追着鼠标跑啦！", "happy")
        self.dialogue_ui.show_dialogue()
        # 设置初始方向为向下
        self.current_direction = "down"
        self.change_animation(f"run_{self.current_direction}", force=True)
    
    def stop_following_mouse(self, announce=True):
        """停止追着鼠标跑"""
        self.is_following_mouse = False
        self._follow_mouse_start = None
        if announce:
            self.dialogue_ui.add_dialogue("ralsei", "我不追啦，有点累了！", "tired")
            self.dialogue_ui.show_dialogue()
        self.change_animation("idle", force=True)
    
    def mouseMoveEvent(self, event):
        # 鼠标移动事件，用于拖动窗口
        if event.buttons() == Qt.LeftButton:
            # 标记为正在拖拽
            self._is_being_dragged = True
            
            # 计算目标位置
            target_pos = event.globalPos() - self.drag_position
            
            # 添加拖拽力度检测
            if hasattr(self, '_last_drag_pos'):
                dx = target_pos.x() - self._last_drag_pos.x()
                dy = target_pos.y() - self._last_drag_pos.y()
                drag_force = (dx ** 2 + dy ** 2) ** 0.5
                
                # 根据拖拽力度调整表情和动画
                if drag_force > 50:
                    # 大力拖拽时，显示惊讶表情
                    if not hasattr(self, '_drag_surprised') or not self._drag_surprised:
                        self._drag_surprised = True
                        self.pet_ai.react_to_event("user_dragged_forcefully", None)
                elif drag_force > 20:
                    # 中等力度拖拽时，显示正常表情
                    self._drag_surprised = False
                else:
                    # 轻微拖拽时，显示开心表情
                    self._drag_surprised = False
            
            # 保存上次拖拽位置
            self._last_drag_pos = target_pos
            
            # 添加弹性物理效果
            if hasattr(self, '_drag_elastic_pos'):
                # 计算弹性系数
                elastic_factor = 0.2
                new_x = int(self._drag_elastic_pos.x() + (target_pos.x() - self._drag_elastic_pos.x()) * elastic_factor)
                new_y = int(self._drag_elastic_pos.y() + (target_pos.y() - self._drag_elastic_pos.y()) * elastic_factor)
                self._drag_elastic_pos = QPoint(new_x, new_y)
            else:
                self._drag_elastic_pos = target_pos
            
            # 移动窗口
            self.move(self._drag_elastic_pos)
            
            # 根据拖拽方向确定动画方向
            if hasattr(self, '_last_drag_pos_prev'):
                dx_prev = self._last_drag_pos.x() - self._last_drag_pos_prev.x()
                dy_prev = self._last_drag_pos.y() - self._last_drag_pos_prev.y()
                
                # 根据拖拽方向确定动画方向
                if abs(dx_prev) > abs(dy_prev):
                    # 水平方向为主
                    current_dir = "right" if dx_prev > 0 else "left"
                else:
                    # 垂直方向为主
                    current_dir = "down" if dy_prev > 0 else "up"
                
                # 计算拖拽速度
                self._drag_speed = (dx_prev ** 2 + dy_prev ** 2) ** 0.5
                
                # 使用跑步动画，拖拽时总是使用跑步动画的6帧
                drag_animation = f"run_{current_dir}"
            else:
                # 第一次拖拽，使用当前方向
                current_dir = self.current_direction
                drag_animation = f"run_{current_dir}"
                self._drag_speed = 0
            
            # 保存上次拖拽位置用于速度计算
            if not hasattr(self, '_last_drag_pos_prev'):
                self._last_drag_pos_prev = target_pos
            self._last_drag_pos_prev = self._last_drag_pos
            
            # 更新当前方向
            self.current_direction = current_dir
            
            # 切换动画
            if self.current_animation != drag_animation:
                self.change_animation(drag_animation, force=True)
            
            event.accept()
        else:
            # 标记为不再拖拽
            if hasattr(self, '_is_being_dragged'):
                self._is_being_dragged = False
            if hasattr(self, '_drag_speed'):
                delattr(self, '_drag_speed')
            
            # 处理拖拽释放时的物理反馈效果
            if hasattr(self, '_last_drag_pos'):
                # 计算释放时的速度
                if hasattr(self, '_last_drag_pos_prev'):
                    dx = self._last_drag_pos.x() - self._last_drag_pos_prev.x()
                    dy = self._last_drag_pos.y() - self._last_drag_pos_prev.y()
                    release_speed = (dx ** 2 + dy ** 2) ** 0.5
                    
                    # 根据释放速度添加不同的物理反馈
                    if release_speed > 150:
                        # 极快释放，触发甩飞效果
                        self.is_falling = True
                        self.is_recovering = False
                        self.fall_duration = 0.0
                        self.fall_start_time = time.time()  # 设置摔倒开始时间
                        self.max_fall_duration = 3.0  # 甩飞动画持续至少3秒
                        self.recovery_max_duration = 3.0
                        
                        # 切换到投掷动画（如果存在），否则使用splat动画
                        throw_animation = "jump_ball"  # 使用跳跃球动画作为投掷动画
                        if throw_animation in self.sprite_loader.sprites:
                            self.change_animation(throw_animation, force=True)
                        else:
                            self.change_animation("fall", force=True)
                        
                        # 添加摔倒惯性滑行效果
                        self.fall_slide_speed_x = dx * 0.5
                        self.fall_slide_speed_y = dy * 0.5
                        
                        # 显示惊讶对话
                        self.dialogue_ui.add_dialogue("ralsei", "啊！被甩飞了...", "surprised")
                        self.dialogue_ui.show_dialogue()
                    elif release_speed > 20:
                        # 快速释放时，添加弹跳效果
                        self._bounce_params = {
                            'start_time': time.time(),
                            'start_pos': self.pos(),
                            'velocity_y': -release_speed * 0.5,  # 向上的初速度
                            'gravity': 150,  # 重力加速度
                            'damping': 0.8,  # 阻尼系数
                            'bounce_count': 0,
                            'max_bounces': 3
                        }
                        
                        # 启动弹跳定时器
                        if not hasattr(self, '_bounce_timer'):
                            self._bounce_timer = QTimer(self)
                            self._bounce_timer.timeout.connect(self.update_bounce)
                        self._bounce_timer.start(30)
                    
                    # 添加旋转阻尼效果
                    if release_speed > 10:
                        self._rotation_damping = {
                            'start_time': time.time(),
                            'initial_angle': dx * 10 / 50,  # 初始旋转角度
                            'damping_factor': 0.9,
                            'target_angle': 0
                        }
                
                # 移除拖拽相关属性
                if hasattr(self, '_drag_elastic_pos'):
                    delattr(self, '_drag_elastic_pos')
                if hasattr(self, '_drag_surprised'):
                    delattr(self, '_drag_surprised')
                if hasattr(self, '_last_drag_pos_prev'):
                    delattr(self, '_last_drag_pos_prev')
                if hasattr(self, '_last_drag_pos'):
                    delattr(self, '_last_drag_pos')
            
            # 保存鼠标位置
            self._last_mouse_pos = event.pos()
            
            # 优化：减少鼠标样式改变的频率
            current_cursor = self.cursor()
            # 检查鼠标是否在Ralsei身上
            is_on_ralsei = self.sprite_label.geometry().contains(event.pos())
            
            if is_on_ralsei:
                # 鼠标在Ralsei身上，改变鼠标样式
                if current_cursor.shape() != Qt.PointingHandCursor:
                    self.setCursor(Qt.PointingHandCursor)
                
                # 初始化抚摸检测相关变量（仅首次）
                if not hasattr(self, '_pet_detection_state'):
                    self._pet_detection_state = {
                        'on_ralsei': True,
                        'last_pos': event.pos(),
                        'movement_history': [],
                        'last_pet_time': 0,
                        'pet_count': 0,
                        'current_part': None,
                        'pet_attempts': 0,
                        'pet_success': False,
                        'click_count': 0,
                        'last_click_time': 0,
                        'click_part': None,
                        'press_start_time': 0,
                        'press_start_pos': None,
                        'is_pressing': False
                    }
                
                # 更新状态（每次移动都执行；修复：此前该块误缩进在
                # "if not hasattr" 内，导致抚摸检测只在首次悬停执行一次、之后被 else 清空）
                self._pet_detection_state['on_ralsei'] = True
                
                # 计算鼠标移动距离和方向
                dx = event.pos().x() - self._pet_detection_state['last_pos'].x()
                dy = event.pos().y() - self._pet_detection_state['last_pos'].y()
                distance = (dx ** 2 + dy ** 2) ** 0.5
                
                # 只有移动距离适中时才记录
                if 3 < distance < 50:
                    # 添加到移动历史
                    self._pet_detection_state['movement_history'].append((dx, dy, distance))
                    # 只保留最近15次移动记录，增加检测的准确性
                    if len(self._pet_detection_state['movement_history']) > 15:
                        self._pet_detection_state['movement_history'].pop(0)
                    
                    # 检查是否符合抚摸模式：来回移动（方向交替变化）
                    if len(self._pet_detection_state['movement_history']) >= 5:
                        # 计算方向变化次数
                        direction_changes = 0
                        prev_dx = None
                        prev_dy = None
                        
                        for (move_dx, move_dy, _) in self._pet_detection_state['movement_history']:
                            # 计算移动方向（主要方向）
                            current_dir = 'horizontal' if abs(move_dx) > abs(move_dy) else 'vertical'
                            
                            if prev_dx is not None:
                                prev_dir = 'horizontal' if abs(prev_dx) > abs(prev_dy) else 'vertical'
                                # 如果方向相同，检查方向是否反转
                                if current_dir == prev_dir:
                                    # 对于水平方向，检查左右反转
                                    if current_dir == 'horizontal':
                                        if (move_dx > 0 and prev_dx < 0) or (move_dx < 0 and prev_dx > 0):
                                            direction_changes += 1
                                    # 对于垂直方向，检查上下反转
                                    else:
                                        if (move_dy > 0 and prev_dy < 0) or (move_dy < 0 and prev_dy > 0):
                                            direction_changes += 1
                            
                            prev_dx = move_dx
                            prev_dy = move_dy
                        
                        # 如果方向变化次数足够（至少2次），判定为抚摸
                        current_time = time.time()
                        if direction_changes >= 2 and current_time - self._pet_detection_state['last_pet_time'] > 1.5:
                            # 检测抚摸的身体部位
                            pet_part = self.get_ralsei_body_part(event.pos())
                            _log.debug(f"抚摸了Ralsei的: {pet_part}")
                            
                            # 根据不同部位触发不同的抚摸效果
                            self.emotion_system.add_emotion("happy", 30)
                            self.emotion_system.add_emotion("shy", 15)
                            
                            # 不同部位的回应
                            responses = {
                                "hair": ["嘿嘿~ 摸我的头发好舒服呀！", "谢谢你的抚摸！", "真的好舒服呀~", "我的头发很软吧？"],
                                "ear": ["哎呀~ 别摸我的耳朵！好痒呀！", "嘿嘿~ 耳朵好敏感呀！", "别摸啦！耳朵会变红的！"],
                                "face": ["哎呀~ 别摸我的脸！", "脸好烫呀~", "嘿嘿~ 摸脸的感觉好特别！"],
                                "body": ["嘿嘿~ 好舒服呀！", "谢谢你的抚摸！", "真的好舒服呀~", "你的手好温暖！"],
                                "arm": ["哎呀~ 别摸我的手臂！", "嘿嘿~ 手臂也会痒的！", "你的抚摸让我好开心！"],
                                "shoulder": ["谢谢你抚摸我的肩膀！", "嘿嘿~ 肩膀也很舒服！", "你的手好温柔！"]
                            }
                            
                            # 选择对应的回应
                            response_list = responses.get(pet_part, ["嘿嘿~ 好舒服呀！", "谢谢你的抚摸！", "真的好舒服呀~"])
                            self.dialogue_ui.add_dialogue("ralsei", random.choice(response_list), "happy")
                            self.dialogue_ui.show_dialogue()
                            
                            # 更新抚摸时间
                            self._pet_detection_state['last_pet_time'] = current_time
                            # 重置移动历史，避免重复触发
                            self._pet_detection_state['movement_history'] = []
                            # 增加抚摸计数
                            self._pet_detection_state['pet_count'] += 1
                
                # 更新最后位置
                self._pet_detection_state['last_pos'] = event.pos()
                
                # 优化：降低鼠标悬停事件的触发频率
                if not hasattr(self, '_last_hover_time') or time.time() - self._last_hover_time > 0.5:
                    self.on_mouse_hover()
                    self._last_hover_time = time.time()
            else:
                # 鼠标离开Ralsei，恢复默认鼠标样式
                if current_cursor.shape() != Qt.ArrowCursor:
                    self.setCursor(Qt.ArrowCursor)
                
                # 更新抚摸检测状态
                if hasattr(self, '_pet_detection_state'):
                    self._pet_detection_state['on_ralsei'] = False
                    # 鼠标离开时重置移动历史
                    self._pet_detection_state['movement_history'] = []
                
            # 记录当前鼠标位置（用于其他逻辑）
            self._last_mouse_pos = event.pos()
    
    def mouseReleaseEvent(self, event):
        # 鼠标释放事件
        if event.button() == Qt.LeftButton:
            # 修复：释放左键时清理拖拽状态（_is_being_dragged/_drag_speed 残留会导致
            # update_animation 在释放后仍按拖拽速度调整帧率）
            if hasattr(self, '_is_being_dragged'):
                self._is_being_dragged = False
            if hasattr(self, '_drag_speed'):
                delattr(self, '_drag_speed')
            # 检查是否在Ralsei身上释放
            if hasattr(self, '_pet_detection_state') and self._pet_detection_state['is_pressing']:
                current_time = time.time()
                press_duration = current_time - self._pet_detection_state['press_start_time']
                
                # 检测长按操作（至少0.5秒）
                if press_duration >= 0.5:
                    clicked_part = self._pet_detection_state['click_part']
                    _log.debug(f"长按了Ralsei的: {clicked_part}，时长: {press_duration:.2f}秒")
                    
                    # 根据不同部位触发不同效果
                    if clicked_part == "ear":
                        # 轻轻捏耳朵
                        _log.debug("轻轻捏了Ralsei的耳朵！")
                        self.emotion_system.add_emotion("happy", 35)
                        self.emotion_system.add_emotion("shy", 25)
                        self.play_animation_once("surprised")
                        self.dialogue_ui.add_dialogue("ralsei", "哎呀！别捏我的耳朵！好痒呀！", "surprised")
                        self.dialogue_ui.show_dialogue()
                    elif clicked_part == "arm":
                        # 拉住手臂
                        _log.debug("拉住了Ralsei的手臂！")
                        self.emotion_system.add_emotion("happy", 30)
                        self.play_animation_once("wave")
                        self.dialogue_ui.add_dialogue("ralsei", "嘿嘿~ 别拉我的手臂啦！", "happy")
                        self.dialogue_ui.show_dialogue()
                    elif clicked_part == "body":
                        # 按住躯干
                        _log.debug("按住了Ralsei的躯干！")
                        self.emotion_system.add_emotion("happy", 25)
                        self.emotion_system.add_emotion("shy", 20)
                        self.play_animation_once("happy")
                        self.dialogue_ui.add_dialogue("ralsei", "嗯~ 好舒服！", "happy")
                        self.dialogue_ui.show_dialogue()
                    elif clicked_part == "belly":
                        # 拍肚子
                        _log.debug("拍了Ralsei的肚子！")
                        self.emotion_system.add_emotion("happy", 40)
                        self.emotion_system.add_emotion("excited", 20)
                        self.play_animation_once("laugh")
                        self.dialogue_ui.add_dialogue("ralsei", "嘿嘿~ 我的肚子很软哦！", "happy")
                        self.dialogue_ui.show_dialogue()
                    elif clicked_part == "face":
                        # 轻轻捏脸
                        _log.debug("轻轻捏了Ralsei的脸！")
                        self.emotion_system.add_emotion("happy", 30)
                        self.emotion_system.add_emotion("shy", 30)
                        self.play_animation_once("surprised")
                        self.dialogue_ui.add_dialogue("ralsei", "哎呀~ 别捏我的脸！", "shy")
                        self.dialogue_ui.show_dialogue()
                    elif clicked_part == "shoulder":
                        # 拉住肩膀
                        _log.debug("拉住了Ralsei的肩膀！")
                        self.emotion_system.add_emotion("happy", 25)
                        self.emotion_system.add_emotion("shy", 15)
                        self.play_animation_once("pose")
                        self.dialogue_ui.add_dialogue("ralsei", "谢谢你拉我的肩膀！", "happy")
                        self.dialogue_ui.show_dialogue()
                
                # 重置长按状态
                self._pet_detection_state['is_pressing'] = False
                self._pet_detection_state['press_start_time'] = 0
                self._pet_detection_state['press_start_pos'] = None
    
    def mouseDoubleClickEvent(self, event):
        # 鼠标双击事件
        # 检查是否双击了Ralsei
        if self.sprite_label.geometry().contains(event.pos()):
            # 检测双击的身体部位
            clicked_part = self.get_ralsei_body_part(event.pos())
            _log.debug(f"双击了Ralsei的: {clicked_part}")
            
            # 根据不同部位触发不同效果
            if clicked_part == "hair":
                # 摸头杀
                _log.debug("摸头杀！")
                self.emotion_system.add_emotion("happy", 50)
                self.emotion_system.add_emotion("shy", 35)
                self.play_animation_once("pose")
                self.dialogue_ui.add_dialogue("ralsei", "嘿嘿~ 摸头杀好舒服！", "happy")
                self.dialogue_ui.show_dialogue()
            elif clicked_part == "belly":
                # 拍肚子（双击）
                _log.debug("用力拍了Ralsei的肚子！")
                self.emotion_system.add_emotion("happy", 45)
                self.emotion_system.add_emotion("excited", 25)
                self.play_animation_once("laugh")
                self.dialogue_ui.add_dialogue("ralsei", "哈哈！别用力拍我的肚子啦！", "laughing")
                self.dialogue_ui.show_dialogue()
            elif clicked_part == "face":
                # 捏脸
                _log.debug("捏了Ralsei的脸！")
                self.emotion_system.add_emotion("happy", 40)
                self.emotion_system.add_emotion("shy", 40)
                self.play_animation_once("surprised")
                self.dialogue_ui.add_dialogue("ralsei", "哎呀！别捏我的脸！", "surprised")
                self.dialogue_ui.show_dialogue()
            elif clicked_part == "shoulder":
                # 拍拍肩膀
                _log.debug("拍拍Ralsei的肩膀！")
                self.emotion_system.add_emotion("happy", 35)
                self.emotion_system.add_emotion("caring", 20)
                self.play_animation_once("wave")
                self.dialogue_ui.add_dialogue("ralsei", "谢谢你拍拍我的肩膀！", "happy")
                self.dialogue_ui.show_dialogue()
            else:
                # 修复：双击耳朵/手臂/腿/躯干等未单独列出的部位时，
                # 原来会落到外层 else 触发"显示/隐藏对话框"（窗口级行为），
                # 在 sprite 内点击却切对话框，交互错乱。改为统一的友好反应。
                _log.debug(f"双击了Ralsei的: {clicked_part}")
                self.emotion_system.add_emotion("happy", 20)
                self.emotion_system.add_emotion("shy", 10)
                self.play_animation_once("happy")
                self.dialogue_ui.add_dialogue("ralsei", "嘿嘿~ 你对我真好！", "happy")
                self.dialogue_ui.show_dialogue()
        else:
            # 双击其他区域，显示/隐藏对话框
            if self.dialogue_ui.isVisible():
                self.dialogue_ui.hide_dialogue()
            else:
                self.dialogue_ui.show_dialogue()
    
    def mouseEnterEvent(self, event):
        # 鼠标进入窗口事件
        self.setCursor(Qt.PointingHandCursor)
        self.on_mouse_hover()
    
    def mouseLeaveEvent(self, event):
        # 鼠标离开窗口事件
        self.setCursor(Qt.ArrowCursor)
    
    def on_mouse_hover(self):
        # 鼠标悬停时的处理
        # 优化：降低随机触发概率，减少不必要的动画播放
        if random.random() < 0.05:  # 5%的概率
            # 播放一次害羞或开心动画
            # 修复："shy" 不是有效动画名（sprite_loader 没有），play_animation_once
            # 会静默失败；改用真实存在的动画。
            hover_animations = ["laugh", "happy", "wave", "look_up", "surprised"]
            self.play_animation_once(random.choice(hover_animations))
            # 添加轻微的开心情绪
            self.emotion_system.add_emotion("happy", 5)
    
    def show_interaction_menu(self, pos):
        # 显示互动菜单
        from PyQt5.QtWidgets import QMenu, QAction
        
        menu = QMenu(self)
        
        # 添加互动选项
        talk_action = QAction("聊天", self)
        talk_action.triggered.connect(self.initiate_chat)
        menu.addAction(talk_action)
        
        play_action = QAction("玩游戏", self)
        play_action.triggered.connect(self.play_game)
        menu.addAction(play_action)
        
        feed_action = QAction("喂食", self)
        feed_action.triggered.connect(self.feed_ralsei)
        menu.addAction(feed_action)
        
        pet_action = QAction("抚摸", self)
        pet_action.triggered.connect(self.pet_ralsei)
        menu.addAction(pet_action)
        
        climb_action = QAction("爬上来", self)
        climb_action.triggered.connect(self.climb_to_top_window)
        menu.addAction(climb_action)
        
        change_animation_action = QAction("切换动画", self)
        change_animation_action.triggered.connect(self.change_animation_randomly)
        menu.addAction(change_animation_action)
        
        # 添加配置选项
        config_action = QAction("配置", self)
        config_action.triggered.connect(self.show_config_dialog)
        menu.addAction(config_action)
        
        hide_action = QAction("隐藏", self)
        hide_action.triggered.connect(self._hide_ralsei)
        menu.addAction(hide_action)
        
        # 显示菜单
        menu.exec_(pos)
    
    def show_config_dialog(self):
        # 显示配置对话框
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox, QGroupBox, QComboBox, QSpinBox, QDoubleSpinBox
        from PyQt5.QtCore import Qt
        
        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("Ralsei Pet 配置")
        dialog.setFixedSize(400, 500)
        dialog.setWindowFlags(Qt.WindowSystemMenuHint | Qt.WindowTitleHint)
        
        # 创建主布局
        main_layout = QVBoxLayout(dialog)
        
        # API配置组（本地 Ralsei 模型 / OpenAI 兼容，如 Ollama http://localhost:11434）
        api_group = QGroupBox("Ralsei AI 配置（本地模型）")
        api_layout = QVBoxLayout(api_group)
        
        # API启用复选框
        self.api_enabled_checkbox = QCheckBox("启用AI对话（未启用时用内置规则对话）")
        self.api_enabled_checkbox.setChecked(self.api_enabled)
        api_layout.addWidget(self.api_enabled_checkbox)
        
        # API密钥（本地 Ollama 可留空）
        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(QLabel("API密钥(可空):"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(self.api_config.get('api_key', ''))
        self.api_key_input.setEchoMode(QLineEdit.Password)
        api_key_layout.addWidget(self.api_key_input)
        api_layout.addLayout(api_key_layout)
        
        # API基础URL
        base_url_layout = QHBoxLayout()
        base_url_layout.addWidget(QLabel("基础URL:"))
        self.base_url_input = QLineEdit()
        # 默认指向本机 Ollama 的 OpenAI 兼容端点
        self.base_url_input.setText(self.api_config.get('base_url', 'http://localhost:11434'))
        self.base_url_input.setToolTip("本机 Ollama：http://localhost:11434")
        base_url_layout.addWidget(self.base_url_input)
        api_layout.addLayout(base_url_layout)
        
        # 模型名称
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("模型名称:"))
        self.model_input = QLineEdit()
        self.model_input.setText(self.api_config.get('model', 'ralsei'))
        model_layout.addWidget(self.model_input)
        api_layout.addLayout(model_layout)
        
        # 提示文字：给出最快上手路径
        _hint = QLabel("提示：Ollama 填基础URL http://localhost:11434、模型 ralsei，"
                       "勾选启用后保存即生效；连不上会自动回退内置对话。")
        _hint.setWordWrap(True)
        _hint.setStyleSheet("color:#888888;font-size:9pt;")
        api_layout.addWidget(_hint)
        
        # 代理ID
        agent_id_layout = QHBoxLayout()
        agent_id_layout.addWidget(QLabel("代理ID:"))
        self.agent_id_input = QLineEdit()
        self.agent_id_input.setText(self.api_config.get('agent_id', ''))
        agent_id_layout.addWidget(self.agent_id_input)
        api_layout.addLayout(agent_id_layout)
        
        # API版本
        api_version_layout = QHBoxLayout()
        api_version_layout.addWidget(QLabel("API版本:"))
        self.api_version_input = QComboBox()
        self.api_version_input.addItem("v1")
        self.api_version_input.addItem("v2")
        current_api_version = self.api_config.get('api_version', 'v1')
        self.api_version_input.setCurrentText(current_api_version)
        api_version_layout.addWidget(self.api_version_input)
        api_layout.addLayout(api_version_layout)
        
        main_layout.addWidget(api_group)
        
        # 动画配置组
        animation_group = QGroupBox("动画配置")
        animation_layout = QVBoxLayout(animation_group)
        
        # 动画帧率
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("动画帧率:"))
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 30)
        self.fps_spinbox.setValue(self.config_manager.get("animation.fps", 20))
        fps_layout.addWidget(self.fps_spinbox)
        animation_layout.addLayout(fps_layout)
        
        main_layout.addWidget(animation_group)
        
        # 运动配置组
        movement_group = QGroupBox("运动配置")
        movement_layout = QVBoxLayout(movement_group)
        
        # 最小速度
        min_speed_layout = QHBoxLayout()
        min_speed_layout.addWidget(QLabel("最小速度:"))
        self.min_speed_spinbox = QDoubleSpinBox()
        self.min_speed_spinbox.setRange(1.0, 20.0)
        self.min_speed_spinbox.setSingleStep(0.5)
        self.min_speed_spinbox.setValue(self.config_manager.get("movement.min_speed", 3.0))
        min_speed_layout.addWidget(self.min_speed_spinbox)
        movement_layout.addLayout(min_speed_layout)
        
        # 最大速度
        max_speed_layout = QHBoxLayout()
        max_speed_layout.addWidget(QLabel("最大速度:"))
        self.max_speed_spinbox = QDoubleSpinBox()
        self.max_speed_spinbox.setRange(1.0, 20.0)
        self.max_speed_spinbox.setSingleStep(0.5)
        self.max_speed_spinbox.setValue(self.config_manager.get("movement.max_speed", 8.0))
        max_speed_layout.addWidget(self.max_speed_spinbox)
        movement_layout.addLayout(max_speed_layout)
        
        main_layout.addWidget(movement_group)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 保存按钮
        save_button = QPushButton("保存")
        save_button.clicked.connect(lambda: self.save_config(dialog))
        button_layout.addWidget(save_button)
        
        # 取消按钮
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)
        
        main_layout.addLayout(button_layout)
        
        # 显示对话框
        dialog.exec_()
    
    def save_config(self, dialog):
        # 保存配置
        
        # 更新API配置
        # 修复：timeout/max_retries/retry_delay 对话框没有对应控件，原实现固定
        # 写 30/3/1.0 会把用户在 config.json 手改的值覆盖掉。保存时保留现有值。
        _cur_cfg = getattr(self, 'api_config', None) or {}
        api_config = {
            'enabled': self.api_enabled_checkbox.isChecked(),
            'api_key': self.api_key_input.text(),
            'base_url': self.base_url_input.text(),
            'model': self.model_input.text(),
            'agent_id': self.agent_id_input.text(),
            'api_version': self.api_version_input.currentText(),
            'timeout': _cur_cfg.get('timeout', 30),
            'max_retries': _cur_cfg.get('max_retries', 3),
            'retry_delay': _cur_cfg.get('retry_delay', 1.0)
        }
        
        # 保存API配置
        self.config_manager.update_api_config(api_config)
        
        # 更新动画配置 - 确保帧延迟与帧率匹配
        fps = self.fps_spinbox.value()
        frame_delay = int(1000 / fps)  # 确保帧延迟与帧率匹配
        self.config_manager.set("animation.fps", fps)
        self.config_manager.set("animation.frame_delay", frame_delay)
        
        # 更新运动配置
        self.config_manager.set("movement.min_speed", self.min_speed_spinbox.value())
        self.config_manager.set("movement.max_speed", self.max_speed_spinbox.value())
        
        # 更新应用配置
        self.api_enabled = api_config['enabled']
        self.api_config = api_config
        # 修复：重建 API 客户端（create_client 工厂）——配置对话框保存后本地 AI 立即热启用，
        # 无需重启程序。用户 register_provider 的自定义实现也会在此生效。
        try:
            self.api_client = create_client(api_config)
        except Exception as e:
            _log.warning(f"重建 API 客户端失败: {e}")
        self.animation_fps = fps
        self.animation_frame_delay = frame_delay
        self.min_speed = self.min_speed_spinbox.value()
        self.max_speed = self.max_speed_spinbox.value()
        
        # 关闭对话框
        dialog.accept()
        
        # 显示保存成功消息
        self.dialogue_ui.add_dialogue("ralsei", "配置已保存！", "happy")
        self.dialogue_ui.show_dialogue()
    
    def initiate_chat(self):
        # 发起聊天
        if not self.dialogue_ui.isVisible():
            self.dialogue_ui.show_dialogue()
        message = self.dialogue_system.initiate_conversation()
        self.dialogue_ui.add_dialogue("ralsei", message, "happy")
    
    def play_game(self):
        # 玩游戏
        games = ["dance", "sing", "chase_cursor", "hide_and_seek", "rock_paper_scissors", "guess_number"]
        game = random.choice(games)
        if game == "dance":
            self.play_animation_once("dance")
            self.dialogue_ui.add_dialogue("ralsei", "来跳舞吧！转圈圈~ 嘻嘻！", "happy")
            self.dialogue_ui.show_dialogue()
        elif game == "sing":
            self.play_animation_once("sing")
            self.dialogue_ui.add_dialogue("ralsei", "啦啦啦~ 唱首歌给你听！", "happy")
            self.dialogue_ui.show_dialogue()
        elif game == "chase_cursor":
            # 修复：原来只弹一句对话，从未调用 start_following_mouse()，
            # "追鼠标"游戏实际没有启动。现在真正启动追鼠标模式。
            self.start_following_mouse()
        elif game == "hide_and_seek":
            # 修复：此前只弹一句对话，从未调用 start_hide_and_seek_game()，
            # 从"玩游戏"菜单进入躲猫猫根本不会启动游戏。
            self.dialogue_ui.add_dialogue("ralsei", "我们来玩躲猫猫吧！我先藏起来~", "happy")
            self.dialogue_ui.show_dialogue()
            self.start_hide_and_seek_game()
        elif game == "rock_paper_scissors":
            # 开始石头剪刀布游戏
            self.start_rock_paper_scissors()
        elif game == "guess_number":
            # 开始猜数字游戏
            self.start_guess_number()
    
    def feed_ralsei(self):
        # 喂食Ralsei
        # 修复：energy_hunger 的方法是 eat() 不是 feed()（原代码 AttributeError，
        # 右键菜单"喂食"直接崩溃）；情绪增益 0.5 太弱改成 30；且 eat() 内部会自己
        # 弹"开动啦"对话，这里不再重复弹，统一由本条对话反馈。
        try:
            self.energy_hunger.eat()
        except Exception as e:
            _log.warning(f"[feed] energy_hunger.eat 异常: {e}")
        self.emotion_system.add_emotion("happy", 30)
        self.emotion_system.add_emotion("grateful", 15)
        self.play_animation_once("laugh")
        self.dialogue_ui.add_dialogue("ralsei", "谢谢你喂我！肚子饱饱的，好幸福~", "happy")
        self.dialogue_ui.show_dialogue()
    
    def pet_ralsei(self):
        # 抚摸Ralsei
        self.emotion_system.add_emotion("happy", 40)
        self.play_animation_once("nuzzle")
        self.dialogue_ui.add_dialogue("ralsei", "嘿嘿~ 好舒服呀！", "happy")
        self.dialogue_ui.show_dialogue()
    
    def change_animation_randomly(self):
        # 随机切换动画
        all_animations = list(self.sprite_loader.sprites.keys())
        # 过滤掉太长或不适合单独播放的动画
        valid_animations = [anim for anim in all_animations if len(anim) < 30 and not anim.startswith("spr_")]
        if valid_animations:
            new_animation = random.choice(valid_animations)
            self.play_animation_once(new_animation)
            self.dialogue_ui.add_dialogue("ralsei", f"看！我在做{new_animation}！", "happy")
            self.dialogue_ui.show_dialogue()
    
    def start_rock_paper_scissors(self):
        # 开始石头剪刀布游戏
        # 修复：其他游戏进行中（躲猫猫等）不允许覆盖——否则躲猫猫的 _hide_stage/
        # _hide_search_timer 残留、障碍文件夹永远留在桌面。返回 False 表示未开始。
        if self.game_state.get('is_playing'):
            self.dialogue_ui.add_dialogue("ralsei", "现在还在玩别的呢，等这一局结束再玩石头剪刀布吧~", "curious")
            self.dialogue_ui.show_dialogue()
            return False
        # 使用 update 而不是整体替换，保留 total_wins/current_streak/best_streak 等统计键
        # （否则 end_rock_paper_scissors 访问 self.game_state["total_wins"] 会 KeyError 崩溃）
        self.game_state.update({
            "is_playing": True,
            "game_type": "rock_paper_scissors",
            "game_round": 0,
            "player_score": 0,
            "ralsei_score": 0,
            "game_history": [],
            "started_at": time.time()
        })
        
        self.dialogue_ui.add_dialogue("ralsei", "我们来玩石头剪刀布吧！", "excited")
        self.dialogue_ui.add_dialogue("ralsei", "你要出什么呢？石头、剪刀还是布？", "happy")
        self.dialogue_ui.show_dialogue()
        
        # 播放开心动画
        self.play_animation_once("happy")
    
    def play_rock_paper_scissors(self, player_choice):
        # 处理石头剪刀布游戏的玩家选择
        if not self.game_state["is_playing"] or self.game_state["game_type"] != "rock_paper_scissors":
            return
        
        # 确保玩家选择有效
        player_choice = player_choice.strip()
        if player_choice not in self.rock_paper_scissors_options:
            self.dialogue_ui.add_dialogue("ralsei", f"请输入有效的选项：{'、'.join(self.rock_paper_scissors_options)}", "confused")
            return
        
        # Ralsei随机选择
        ralsei_choice = random.choice(self.rock_paper_scissors_options)
        
        # 判断胜负
        result = self.determine_rock_paper_scissors_winner(player_choice, ralsei_choice)
        
        # 更新分数
        self.game_state["game_round"] += 1
        if result == "player":
            self.game_state["player_score"] += 1
        elif result == "ralsei":
            self.game_state["ralsei_score"] += 1
        
        # 记录游戏历史
        self.game_state["game_history"].append({
            "round": self.game_state["game_round"],
            "player_choice": player_choice,
            "ralsei_choice": ralsei_choice,
            "result": result
        })
        
        # 显示结果
        result_messages = {
            "player": "你赢了！太棒了！",
            "ralsei": "我赢了！嘿嘿~",
            "tie": "平局！再来一次吧！"
        }
        
        self.dialogue_ui.add_dialogue("ralsei", f"你出了：{player_choice}", "neutral")
        self.dialogue_ui.add_dialogue("ralsei", f"我出了：{ralsei_choice}", "neutral")
        self.dialogue_ui.add_dialogue("ralsei", result_messages[result], "happy")
        self.dialogue_ui.add_dialogue("ralsei", f"比分：你 {self.game_state['player_score']} - {self.game_state['ralsei_score']} 我", "neutral")
        
        # 根据结果播放相应的动画
        if result == "player":
            self.play_animation_once("sad")
            self.emotion_system.add_emotion("sad", 20)
        elif result == "ralsei":
            self.play_animation_once("laugh")
            self.emotion_system.add_emotion("happy", 30)
        else:
            self.play_animation_once("neutral")
        
        # 询问是否继续游戏
        if self.game_state["game_round"] >= 5:
            # 游戏结束，显示最终结果
            self.end_rock_paper_scissors()
        else:
            # 询问是否继续
            self.dialogue_ui.add_dialogue("ralsei", "要继续玩吗？请输入石头、剪刀或布，或者输入'结束'来结束游戏。", "happy")
    
    def determine_rock_paper_scissors_winner(self, player_choice, ralsei_choice):
        # 判断石头剪刀布游戏的胜负
        if player_choice == ralsei_choice:
            return "tie"
        
        win_conditions = {
            "石头": "剪刀",
            "剪刀": "布",
            "布": "石头"
        }
        
        if win_conditions[player_choice] == ralsei_choice:
            return "player"
        else:
            return "ralsei"
    
    def end_rock_paper_scissors(self):
        # 结束石头剪刀布游戏
        final_message = "游戏结束！"
        if self.game_state["player_score"] > self.game_state["ralsei_score"]:
            final_message += "你赢了！太棒了！"
            self.play_animation_once("sad")
            self.emotion_system.add_emotion("sad", 20)
            # 更新游戏统计
            self.game_state["total_wins"] += 1
            self.game_state["current_streak"] += 1
            if self.game_state["current_streak"] > self.game_state["best_streak"]:
                self.game_state["best_streak"] = self.game_state["current_streak"]
        elif self.game_state["player_score"] < self.game_state["ralsei_score"]:
            final_message += "我赢了！嘿嘿~"
            self.play_animation_once("laugh")
            self.emotion_system.add_emotion("happy", 30)
            # 更新游戏统计
            self.game_state["total_losses"] += 1
            self.game_state["current_streak"] = 0
        else:
            final_message += "平局！真是一场精彩的比赛！"
            self.play_animation_once("neutral")
            # 更新游戏统计
            self.game_state["total_ties"] += 1
            self.game_state["current_streak"] = 0
        
        final_message += f"最终比分：你 {self.game_state['player_score']} - {self.game_state['ralsei_score']} 我"
        
        # 添加游戏统计信息
        stats_message = f"游戏统计：总游戏数 {self.game_state['total_games']}，胜利 {self.game_state['total_wins']}，失败 {self.game_state['total_losses']}，平局 {self.game_state['total_ties']}，当前连胜 {self.game_state['current_streak']}，最佳连胜 {self.game_state['best_streak']}"
        
        self.dialogue_ui.add_dialogue("ralsei", final_message, "happy")
        self.dialogue_ui.add_dialogue("ralsei", stats_message, "neutral")
        self.dialogue_ui.add_dialogue("ralsei", "谢谢你陪我玩！", "grateful")
        
        # 重置游戏状态
        self.game_state["is_playing"] = False
        self.game_state["game_type"] = None
    
    def start_guess_number(self):
        # 开始猜数字游戏
        # 修复：其他游戏进行中不允许覆盖（同 start_rock_paper_scissors）
        if self.game_state.get('is_playing'):
            self.dialogue_ui.add_dialogue("ralsei", "现在还在玩别的呢，等这一局结束再玩猜数字吧~", "curious")
            self.dialogue_ui.show_dialogue()
            return False
        
        # 生成目标数字
        self.guess_number_game["target_number"] = random.randint(
            self.guess_number_game["min_number"],
            self.guess_number_game["max_number"]
        )
        self.guess_number_game["attempts"] = 0
        
        # 更新游戏状态（update 保留统计键，避免后续 end_rock_paper_scissors 等 KeyError）
        self.game_state.update({
            "is_playing": True,
            "game_type": "guess_number",
            "game_round": 0,
            "player_score": 0,
            "ralsei_score": 0,
            "game_history": [],
            "started_at": time.time()
        })
        
        self.dialogue_ui.add_dialogue("ralsei", "我们来玩猜数字游戏吧！", "excited")
        self.dialogue_ui.add_dialogue("ralsei", f"我已经想好了一个{self.guess_number_game['min_number']}到{self.guess_number_game['max_number']}之间的数字，你有{self.guess_number_game['max_attempts']}次机会来猜！", "happy")
        self.dialogue_ui.add_dialogue("ralsei", "请输入你猜的数字：", "happy")
        self.dialogue_ui.show_dialogue()
        
        # 播放开心动画
        self.play_animation_once("happy")
    
    def play_guess_number(self, player_guess):
        # 处理猜数字游戏的玩家输入
        if not self.game_state["is_playing"] or self.game_state["game_type"] != "guess_number":
            return
        
        # 确保玩家输入是有效的数字
        try:
            player_guess = int(player_guess.strip())
        except ValueError:
            self.dialogue_ui.add_dialogue("ralsei", "请输入有效的数字！", "confused")
            return
        
        # 检查数字范围
        if player_guess < self.guess_number_game["min_number"] or player_guess > self.guess_number_game["max_number"]:
            self.dialogue_ui.add_dialogue("ralsei", f"请输入{self.guess_number_game['min_number']}到{self.guess_number_game['max_number']}之间的数字！", "confused")
            return
        
        # 更新尝试次数
        self.guess_number_game["attempts"] += 1
        self.game_state["game_round"] += 1
        
        # 记录游戏历史
        self.game_state["game_history"].append({
            "round": self.game_state["game_round"],
            "player_guess": player_guess,
            "target_number": self.guess_number_game["target_number"]
        })
        
        # 判断猜测结果
        target = self.guess_number_game["target_number"]
        if player_guess == target:
            # 猜对了
            self.game_state["player_score"] += 1
            self.dialogue_ui.add_dialogue("ralsei", f"恭喜你！猜对了！数字就是{target}！", "happy")
            # 修复：玩家猜对时 Ralsei 不该放"难过"动画/加悲伤情绪（原代码方向反转，
            # 文案祝贺、表情却难过）。Ralsei 是"被猜中"但游戏是陪玩，应一起开心。
            self.play_animation_once("happy")
            self.emotion_system.add_emotion("happy", 25)
            self.emotion_system.add_emotion("surprised", 15)
            self.end_guess_number()
        elif player_guess < target:
            # 猜小了
            attempts_left = self.guess_number_game["max_attempts"] - self.guess_number_game["attempts"]
            if attempts_left > 0:
                self.dialogue_ui.add_dialogue("ralsei", f"猜小了！再试一次！还剩{attempts_left}次机会。", "happy")
                self.dialogue_ui.add_dialogue("ralsei", "请输入你猜的数字：", "happy")
                self.play_animation_once("laugh")
                self.emotion_system.add_emotion("happy", 10)
            else:
                self.dialogue_ui.add_dialogue("ralsei", f"猜小了！很遗憾，你已经用完了所有机会。", "sad")
                self.end_guess_number()
        else:
            # 猜大了
            attempts_left = self.guess_number_game["max_attempts"] - self.guess_number_game["attempts"]
            if attempts_left > 0:
                self.dialogue_ui.add_dialogue("ralsei", f"猜大了！再试一次！还剩{attempts_left}次机会。", "happy")
                self.dialogue_ui.add_dialogue("ralsei", "请输入你猜的数字：", "happy")
                self.play_animation_once("laugh")
                self.emotion_system.add_emotion("happy", 10)
            else:
                self.dialogue_ui.add_dialogue("ralsei", f"猜大了！很遗憾，你已经用完了所有机会。", "sad")
                self.end_guess_number()
    
    def end_guess_number(self):
        # 结束猜数字游戏
        target = self.guess_number_game["target_number"]
        
        if self.game_state["player_score"] > 0:
            # 修复：玩家赢 → Ralsei 一起开心（原代码玩家赢却放 sad/难过）
            final_message = f"恭喜你赢了！数字是{target}！"
            self.play_animation_once("happy")
            self.emotion_system.add_emotion("happy", 20)
            self.emotion_system.add_emotion("grateful", 15)
        else:
            # 修复：玩家没猜中（Ralsei 守住了数字）→ 轻快收场（原代码玩家输反而 laugh 正确，保留）
            final_message = f"游戏结束！正确数字是{target}！下次再挑战我呀~"
            self.play_animation_once("laugh")
            self.emotion_system.add_emotion("happy", 10)
            self.emotion_system.add_emotion("playful", 10)
        
        self.dialogue_ui.add_dialogue("ralsei", final_message, "happy")
        self.dialogue_ui.add_dialogue("ralsei", "谢谢你陪我玩！", "grateful")
        
        # 重置游戏状态
        self.game_state["is_playing"] = False
        self.game_state["game_type"] = None
    
    def handle_game_input(self, user_input):
        # 处理游戏相关的用户输入
        if not self.game_state["is_playing"]:
            return False
        
        # 修复：支持"结束/退出游戏/不玩了/算了"等多种退出说法（原来只认精确"结束"，
        # 用户在游戏里想退出却被"无效选项"提示锁死）。
        _quit_words = ("结束", "退出游戏", "不玩了", "不玩", "算了", "quit", "exit")
        _want_quit = any(q in user_input for q in _quit_words)
        if _want_quit:
            if self.game_state["game_type"] == "rock_paper_scissors":
                self.end_rock_paper_scissors()
            elif self.game_state["game_type"] == "guess_number":
                self.end_guess_number()
            elif self.game_state["game_type"] == "hide_and_seek":
                # 修复：躲猫猫进行中用户说"退出游戏/不玩了"时结束游戏并清理障碍物
                #（原实现不处理，玩家被困在局里只能等超时或杀进程）。
                self._abort_hide_and_seek(reason='user_quit')
                self.dialogue_ui.add_dialogue("ralsei", "好吧，那这次就不躲啦~ 下次再一起玩！", "sad")
                self.dialogue_ui.show_dialogue()
            return True
        
        if self.game_state["game_type"] == "rock_paper_scissors":
            # 修复：游戏中收到明显不是出招的内容（你好/随便聊聊）时给出引导而不是
            # 静默吞掉或当作"无效选项"反复提示——仍返回 True 表示"由游戏接管"。
            if user_input not in self.rock_paper_scissors_options:
                if not any(ord(c) > 127 for c in user_input) and len(user_input) < 8:
                    self.dialogue_ui.add_dialogue("ralsei", "现在是石头剪刀布时间！出『石头』『剪刀』或『布』吧（说「结束」就不玩啦）", "happy")
                    self.dialogue_ui.show_dialogue()
                    return True
            self.play_rock_paper_scissors(user_input)
            return True
        elif self.game_state["game_type"] == "guess_number":
            self.play_guess_number(user_input)
            return True
        
        return False
    
    # 本地 AI 接入（OpenAI 兼容 / register_provider 自定义实现）
    def init_api_client(self, api_key=None, base_url=None, model=None, agent_id=None, api_version=None):
        # 初始化本地 AI 客户端（对话走 chat_with_ai；自定义 agent 走协议轮询）
        _log.debug("正在初始化本地 AI 客户端...")
        
        # 从配置管理器获取当前API配置
        api_config = self.config_manager.get_api_config()
        
        # 完善API配置
        if api_key:
            api_config['api_key'] = api_key
        if base_url:
            api_config['base_url'] = base_url
        if model:
            api_config['model'] = model
        
        # 添加用户代理ID支持
        if agent_id:
            api_config['agent_id'] = agent_id
        
        # 添加API版本支持
        if api_version:
            api_config['api_version'] = api_version
        
        # 检查必要配置：云服务必须要有 API 密钥；本地模型（localhost/127.0.0.1 等
        # 本机地址，如 Ollama）无鉴权，允许空密钥直接启用。
        need_key = True
        try:
            _u = (api_config.get('base_url') or '').lower()
            if any(_u.startswith(p) for p in
                   ('http://localhost', 'http://127.0.0.1',
                    'http://0.0.0.0', 'http://[::1]')):
                need_key = False
        except Exception:
            need_key = True
        if need_key and (not api_config.get('api_key')):
            _log.warning("API初始化失败: 云服务缺少API密钥（本机 Ollama 等本地模型可留空）")
            self.api_enabled = False
            api_config['enabled'] = False
            return False
        
        # 测试API连接
        try:
            # 这里可以添加API连接测试
            self.api_enabled = True
            api_config['enabled'] = True
            # 修复：打印完整配置会把 api_key 明文写进日志。脱敏后只打印非敏感字段。
            safe_config = dict(api_config)
            if safe_config.get('api_key'):
                safe_config['api_key'] = '***'
            _log.debug(f"API客户端初始化完成，配置: {safe_config}")
            
            # 保存API配置到配置文件
            self.config_manager.update_api_config(api_config)
            self.api_config = api_config
            # 修复：重建客户端（本地 AI 端口）——启用后命令轮询/对话立即走真实实现
            try:
                self.api_client = create_client(api_config)
            except Exception as e:
                _log.warning(f"重建 API 客户端失败: {e}")
            
            return True
        except Exception as e:
            _log.warning(f"API连接测试失败: {e}")
            self.api_enabled = False
            api_config['enabled'] = False
            return False
    
    def send_api_request(self, prompt, **kwargs):
        # 发送API请求（OpenAI 兼容协议，本机 Ollama / 云服务均可）
        if not self.api_enabled:
            _log.debug("API未启用，请先初始化API客户端")
            return None
        
        import requests
        import json
        import time
        
        _log.debug(f"发送API请求: {prompt}")
        _log.debug(f"请求参数: {kwargs}")
        
        # 获取API版本
        api_version = self.api_config.get('api_version', 'v1')
        
        # 构建完整的API请求URL
        if 'agent_id' in self.api_config:
            # 如果有代理ID，使用代理对话接口
            url = f"{self.api_config['base_url']}/{api_version}/agents/{self.api_config['agent_id']}/chat/completions"
        else:
            # 否则使用普通对话接口
            url = f"{self.api_config['base_url']}/{api_version}/chat/completions"
        
        # 构建请求头
        headers = {
            'Authorization': f"Bearer {self.api_config['api_key']}",
            'Content-Type': 'application/json',
            'X-Ralsei-Source': 'ralsei_pet'
        }
        
        # 合并自定义头
        headers.update(self.api_config.get('headers', {}))
        
        # 构建请求体
        request_body = {
            'model': self.api_config['model'],
            'messages': [
                {
                    'role': 'system',
                    'content': '你是Deltarune中的Ralsei，一个善良、友好、害羞的角色。请以Ralsei的身份与用户对话，保持角色一致。'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.7,
            'max_tokens': 500,
            'top_p': 0.95,
            'stream': False
        }
        
        # 如果是代理请求，添加代理相关参数
        if 'agent_id' in self.api_config:
            request_body['agent_id'] = self.api_config['agent_id']
        
        # 添加额外参数
        for key, value in kwargs.items():
            if key in request_body or key == 'agent_id':
                request_body[key] = value
        
        # 实现重试机制
        retries = 0
        while retries < self.api_config['max_retries']:
            try:
                response = requests.post(
                    url, 
                    headers=headers, 
                    data=json.dumps(request_body),
                    timeout=self.api_config['timeout']
                )
                
                if response.status_code == 200:
                    # 解析响应
                    response_data = response.json()
                    # 修复：choices 为空列表时 [0] 会 IndexError，且该异常不是
                    # RequestException，不会被下面的 except 捕获。空列表时返回空内容。
                    choices = response_data.get('choices') or []
                    content = ''
                    if choices:
                        content = choices[0].get('message', {}).get('content', '')
                    api_response = {
                        'status': 'success',
                        'content': content,
                        'timestamp': time.time(),
                        'raw_response': response_data
                    }
                    _log.debug(f"API响应: {api_response}")
                    return api_response
                else:
                    _log.warning(f"API请求失败，状态码: {response.status_code}, 响应: {response.text}")
                    retries += 1
                    if retries < self.api_config['max_retries']:
                        _log.debug(f"将在 {self.api_config['retry_delay']} 秒后重试...")
                        time.sleep(self.api_config['retry_delay'])
            except requests.exceptions.RequestException as e:
                _log.warning(f"API请求异常: {e}")
                retries += 1
                if retries < self.api_config['max_retries']:
                    _log.debug(f"将在 {self.api_config['retry_delay']} 秒后重试...")
                    time.sleep(self.api_config['retry_delay'])
        
        _log.warning(f"API请求失败，已达到最大重试次数 ({self.api_config['max_retries']})")
        return {
            'status': 'error',
            'content': '',
            'timestamp': time.time(),
            'error': 'API请求失败'
        }
    
    def handle_api_response(self, response):
        # 处理API响应
        if response and response['status'] == 'success':
            content = response['content']
            _log.debug(f"处理API响应: {content}")
            
            # 根据响应内容执行相应操作
            self._execute_api_action(content)
            return True
        else:
            _log.warning(f"API响应处理失败: {response}")
            # 可以添加错误处理逻辑，例如显示错误消息
            error_msg = response.get('error', '未知错误') if response else '无效响应'
            self.dialogue_ui.add_dialogue("ralsei", f"抱歉，我现在有点不太舒服... ({error_msg})")
            self.dialogue_ui.show_dialogue()
            return False
    
    def change_animation(self, new_animation, force=False):
        # 安全地切换动画，带有冷却时间检查、优先级系统、spell 阶段硬拦截
        current_time = time.time()
        
        # 1) 动画不存在时：按 parts 从长到短回退到基础动画，仍找不到 → 拒绝
        if new_animation not in self.sprite_loader.sprites:
            base_parts = new_animation.split('_')
            found = None
            for i in range(len(base_parts), 1, -1):
                base_anim = '_'.join(base_parts[:i])
                if base_anim in self.sprite_loader.sprites:
                    found = base_anim
                    break
            if found is None and 'idle' in self.sprite_loader.sprites:
                found = 'idle'
            if found is None:
                return False
            new_animation = found
        
        # 2) 计算新动画优先级：先查 animation_priorities，否则按 group 兜底
        #    兜底优先级：spell=5, jump/splat/fall/land=4, run=3, walk=2, 其他=1
        new_group = new_animation.split('_')[0] if '_' in new_animation else new_animation
        group_priority_map = {
            'spell': 5,
            'jump': 4, 'splat': 4, 'fall': 4, 'land': 4,
            'run': 3,
            'walk': 2,
        }
        name_priority = self.animation_priorities.get(new_animation, None)
        if name_priority is not None:
            new_priority = name_priority
        else:
            new_priority = group_priority_map.get(new_group, 1)
        
        # 检查是否是不同分组的动画切换
        current_group = self.current_animation.split('_')[0] if '_' in self.current_animation else self.current_animation

        # ========== 关键 1：spell 流程阶段硬拦截 ==========
        #   walking 阶段：只允许 spell / walk 两类动画
        #   casting 阶段：只允许 spell 类（spell/spell_left）
        _spell_stage = getattr(self, '_spell_stage', None)
        if _spell_stage == 'walking':
            if new_group not in ('spell', 'walk'):
                return False
        elif _spell_stage == 'casting':
            if new_group != 'spell':
                return False
        
        # ========== 关键 1.5：躲猫猫游戏阶段硬拦截 ==========
        # 当游戏 is_playing 中，非 spell 阶段时：只允许 walk / idle / spell 三类（spell 留着给 hiding_spell 等）
        # 禁止 idle/laugh/其他 动画打断关键走路过程（尤其是 moving_to_center / moving_to_folder）
        if getattr(self, 'game_state', {}).get('is_playing') and _spell_stage is None:
            _hide_stage = getattr(self, '_hide_stage', None)
            # 只要还在走路相关阶段（moving_to_center / moving_to_folder / walking），就强制只能 walk_* 或 spell
            if _hide_stage in ('moving_to_center', 'moving_to_folder') and getattr(self, 'is_moving', False):
                if new_group not in ('walk', 'spell'):
                    return False
            else:
                # 其他游戏阶段（creating / hiding_spell 等）：禁止 laugh/dance/无聊的动画干扰
                if new_group in ('laugh', 'dance', 'sing', 'wave', 'eat'):
                    return False
        
        # 检查冷却时间和优先级
        if not force:
            # 不同分组的动画切换需要更长的冷却时间
            if current_group != new_group:
                if current_time - self.last_animation_change < self.animation_change_cooldown * 2:
                    return False
            else:
                if current_time - self.last_animation_change < self.animation_change_cooldown:
                    return False
            # ========== 关键 2：优先级拦截：新动画优先级必须 >= 当前才允许覆盖 ==========
            cur_pri = getattr(self, 'current_priority', 1)
            if new_priority < cur_pri:
                return False
        
        # 执行动画切换
        is_same_group = (current_group == new_group)

        self.current_animation = new_animation
        self.current_priority = new_priority
        self.last_animation_change = current_time
        # 记录表演动画切换时间（用于最小持续时间保护）
        # 放在 change_animation 内部，确保不管谁调用（emotion_system/randomize/update_animation）
        # 都能正确记录时间。修复：此前只在 update_animation 中记录，导致其他系统触发的
        # 表演动画 _last_perf_anim_time 永远为0，最小持续时间保护失效。
        _is_perf = (new_animation not in (
            'idle', 'spell', 'spell_left', 'jump', 'jump_ready', 'jump_ball',
            'fall', 'fall_back', 'fall_mad', 'splat', 'splat_mad', 'land',
        ) and not new_animation.startswith(('walk_', 'run_')))
        if _is_perf and hasattr(self, '_last_perf_anim_time'):
            self._last_perf_anim_time = current_time

        # 从 walk_<dir> / run_<dir> / walk_<dir>_blush 等动画名里提取方向并同步
        if new_group in ('walk', 'run'):
            for d in ('down', 'up', 'left', 'right'):
                if f'_{d}' in new_animation:
                    self.previous_direction = self.current_direction
                    self.current_direction = d
                    break

        # 同组切换时保持帧索引（避免方向切换时动画从头开始），不同组重置为0
        if is_same_group:
            frame_count = len(self.sprite_loader.sprites.get(new_animation, []))
            if frame_count > 0:
                self.current_frame = min(self.current_frame, frame_count - 1)
        else:
            self.current_frame = 0
        return True
    
    def _execute_api_action(self, content):
        # 根据API响应执行相应操作
        _log.debug(f"执行API操作: {content}")
        
        # 动作映射
        action_keywords = {
            # 基本动画
            'dance': ['跳个舞', '跳舞', 'dance'],
            'sing': ['唱歌', '唱首歌', 'sing'],
            'idle': ['休息', '休息一下', 'rest'],
            'wave': ['挥手', '打招呼', 'wave'],
            'laugh': ['笑', '开心', 'laugh'],
            'cry': ['哭', '难过', 'cry'],
            'hug': ['拥抱', '抱一下', 'hug'],
            'tea': ['喝茶', 'tea'],
            'look_up': ['看上面', '向上看', 'look up'],
            'pose': ['摆姿势', 'pose'],
            'curtsy': ['行礼', 'curtsy'],
            # 窗口交互
            'jump': ['跳跃', '跳', 'jump'],
            'climb': ['爬', '爬上去', 'climb'],
            'fall': ['掉下来', '摔倒', 'fall'],
            # 应用控制
            'open_browser': ['打开浏览器', '浏览器'],
            'search': ['搜索', '查找'],
            'ppt': ['PPT', '演示文稿', '幻灯片'],
            'check_ppt': ['检查PPT', '检测演示文稿'],
            'check_browser': ['检查浏览器', '检测浏览器'],
            # 鼠标跟随
            'follow_mouse': ['追着鼠标跑', '跟随鼠标', '追鼠标'],
            'stop_follow_mouse': ['停止追鼠标', '不要追鼠标', '停止跟随']
        }
        
        # 检查动作关键词
        content_lower = content.lower()
        action_triggered = False
        
        # 检查搜索关键词
        search_keywords = ['搜索', '查找']
        search_query = None
        for keyword in search_keywords:
            if keyword in content_lower:
                # 提取搜索内容
                try:
                    search_query = content.split(keyword, 1)[1].strip()
                    if search_query:
                        self.desktop_interaction.search_in_browser(search_query)
                        self.dialogue_ui.add_dialogue("ralsei", f"我来帮你搜索关于{search_query}的内容！", "excited")
                        self.dialogue_ui.show_dialogue()
                        action_triggered = True
                except IndexError:
                    pass
                break
        
        # 检查PPT相关操作
        if not action_triggered:
            # 修复：'PPT' 大写关键词在 content_lower（全小写）中永远匹配不到，
            # 英文用户输入"ppt"时 PPT 分支失效。统一用小写关键词。
            ppt_keywords = ['ppt', '演示文稿', '幻灯片']
            for keyword in ppt_keywords:
                if keyword in content_lower:
                    # 检查具体PPT操作
                    if '播放' in content_lower or '开始' in content_lower:
                        # 查找PPT文件并播放
                        ppt_files = self.desktop_interaction.check_ppt_files()
                        if ppt_files:
                            self.desktop_interaction.ppt_control("start_slideshow", ppt_files[0]['path'])
                            self.dialogue_ui.add_dialogue("ralsei", f"开始播放{ppt_files[0]['name']}！", "happy")
                        else:
                            self.dialogue_ui.add_dialogue("ralsei", "没有找到PPT文件呢！", "sad")
                    elif '下一张' in content_lower:
                        # 需要获取当前打开的PPT并切换
                        self.desktop_interaction.ppt_control("next_slide")
                        self.dialogue_ui.add_dialogue("ralsei", "已切换到下一张幻灯片！", "happy")
                    elif '上一张' in content_lower:
                        self.desktop_interaction.ppt_control("previous_slide")
                        self.dialogue_ui.add_dialogue("ralsei", "已切换到上一张幻灯片！", "happy")
                    elif '停止' in content_lower or '结束' in content_lower:
                        self.desktop_interaction.ppt_control("stop_slideshow")
                        self.dialogue_ui.add_dialogue("ralsei", "已停止PPT放映！", "happy")
                    elif '检查' in content_lower or '检测' in content_lower:
                        # 检查PPT窗口和文件
                        self.check_ppt_windows()
                        self.check_ppt_files()
                    else:
                        # 显示PPT帮助
                        self.dialogue_ui.add_dialogue("ralsei", "我可以帮你控制PPT，比如播放、切换幻灯片等！", "helpful")
                    self.dialogue_ui.show_dialogue()
                    action_triggered = True
                    break
        
        # 检查浏览器相关操作
        if not action_triggered:
            browser_keywords = ['浏览器']
            for keyword in browser_keywords:
                if keyword in content_lower:
                    if '打开' in content_lower:
                        self.open_browser_for_ralsei()
                    else:
                        self.check_browser_windows()
                    action_triggered = True
                    break
        
        # 检查窗口跳跃操作
        if not action_triggered:
            jump_keywords = ['跳跃', '跳']
            for keyword in jump_keywords:
                if keyword in content_lower:
                    # 检查附近窗口并跳跃
                    self.check_nearby_windows(self.pos())
                    action_triggered = True
                    break
        
        # 检查爬窗操作
        if not action_triggered:
            climb_keywords = ['爬', '爬上去']
            for keyword in climb_keywords:
                if keyword in content_lower:
                    self.climb_to_top_window()
                    action_triggered = True
                    break
        
        # 检查鼠标跟随操作
        if not action_triggered:
            follow_keywords = ['追着鼠标跑', '跟随鼠标', '追鼠标']
            for keyword in follow_keywords:
                if keyword in content_lower:
                    self.start_following_mouse()
                    action_triggered = True
                    break
        
        if not action_triggered:
            stop_follow_keywords = ['停止追鼠标', '不要追鼠标', '停止跟随']
            for keyword in stop_follow_keywords:
                if keyword in content_lower:
                    self.stop_following_mouse()
                    action_triggered = True
                    break
        
        # 检查基本动画和其他动作
        if not action_triggered:
            for action, keywords in action_keywords.items():
                for keyword in keywords:
                    if keyword in content_lower:
                        # 处理特殊动作
                        if action == 'follow_mouse':
                            # 不允许跟随鼠标，忽略此命令
                            self.dialogue_ui.add_dialogue("ralsei", "我更喜欢自己走来走去呢！", "happy")
                            self.dialogue_ui.show_dialogue()
                            action_triggered = True
                        elif action == 'stop_follow_mouse':
                            # 停止跟随鼠标（如果正在跟随）
                            self.stop_following_mouse()
                            action_triggered = True
                        else:
                            # 安全切换动画
                            self.change_animation(action)
                            action_triggered = True
                        break
                if action_triggered:
                    break
        
        # 总是显示对话（除非已经显示过）
        if not action_triggered:
            self.dialogue_ui.add_dialogue("ralsei", content, "happy")
            self.dialogue_ui.show_dialogue()
    
    def get_system_info(self):
        # 获取系统信息，用于API请求
        import psutil
        import platform
        import datetime
        
        # 获取电脑状态信息
        cpu_usage = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        battery = psutil.sensors_battery()
        net = psutil.net_io_counters()
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time
        
        # 获取当前运行的进程数量
        process_count = len(psutil.pids())
        
        # 获取网络状态
        try:
            # 检查是否连接到网络
            import socket
            socket.create_connection(('www.baidu.com', 80), timeout=2)
            network_status = 'connected'
        except OSError:
            network_status = 'disconnected'
        
        # 构建电脑状态信息
        computer_info = {
            'cpu_usage': cpu_usage,
            'memory_usage': memory.percent,
            'memory_total': round(memory.total / (1024 ** 3), 2),  # 转换为GB
            'memory_available': round(memory.available / (1024 ** 3), 2),  # 转换为GB
            'disk_usage': disk.percent,
            'disk_total': round(disk.total / (1024 ** 3), 2),  # 转换为GB
            'disk_used': round(disk.used / (1024 ** 3), 2),  # 转换为GB
            'battery_percent': battery.percent if battery else None,
            'battery_plugged': battery.power_plugged if battery else None,
            'network_status': network_status,
            'network_sent': round(net.bytes_sent / (1024 ** 2), 2),  # 转换为MB
            'network_recv': round(net.bytes_recv / (1024 ** 2), 2),  # 转换为MB
            'uptime_hours': round(uptime.total_seconds() / 3600, 2),
            'process_count': process_count,
            'platform': platform.system(),
            'platform_version': platform.version(),
            'python_version': platform.python_version(),
            'current_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 获取Ralsei的状态信息
        ralsei_info = {
            # 修复：pet_ai 没有 get_current_state() 方法（启用 AI 后 update_ai 周期性
            # AttributeError 崩溃）。pet_ai 有 state 属性（idle/move/interact/play/rest），
            # 直接读取并做容错。
            'pet_state': getattr(getattr(self, 'pet_ai', None), 'state', 'idle'),
            'energy': self.energy_hunger.get_energy(),
            'hunger': self.energy_hunger.get_hunger(),
            'current_animation': self.current_animation,
            'position': {
                'x': self.pos().x(),
                'y': self.pos().y()
            },
            'emotion': self.emotion_system.get_current_emotion(),
            'level': self.social_growth.get_level(),
            'experience': self.social_growth.get_experience()
        }
        
        # 组合系统信息
        system_info = {
            'ralsei': ralsei_info,
            'computer': computer_info,
            'weather': self.weather_system.get_current_weather(),
            'timestamp': time.time()
        }
        return system_info
    
    def _async_api_request(self, prompt, callback=None, **kwargs):
        # 异步发送API请求，避免阻塞主线程
        import threading
        
        def _request_thread():
            try:
                response = self.send_api_request(prompt, **kwargs)
                # 修复：原实现在线程内调用 QTimer.singleShot —— 工作线程没有 Qt 事件循环，
                # 定时器永不触发，API 响应被静默丢弃。改用 Qt Signal 跨线程投递到主线程。
                self._api_result.emit(response, callback)
            except Exception as e:
                _log.warning(f"[API请求] 线程异常: {e}")
                # 异常时也把错误结果发回主线程，避免静默失败
                self._api_result.emit({'status': 'error', 'content': '', 'timestamp': time.time(),
                                       'error': str(e)}, callback)
        
        # 启动异步线程
        thread = threading.Thread(target=_request_thread, daemon=True)
        thread.start()
        return thread

    def chat_with_ai(self, text, on_reply):
        """把用户输入交给本地 AI（后台线程，不卡 UI），完成后在主线程回调
        on_reply(reply_str 或 None)。

        - 未启用 API / api_client 未实现 / 请求失败 / 超时：一律回调 None，
          由调用方回退到内置规则对话。
        - 这是"培养的本地 Ralsei"（Ollama / OpenAI 兼容端点）的主对话端口：
          配置对话框里填 base_url + model（如 http://localhost:11434 / ralsei）即可。
        - 训练调优：把「角色设定 + 当前状态上下文 + 最近对话历史」一起交给模型，
          让 Ralsei 的对话连贯、贴角色、能感知当下（时间/天气/心情/精力/记忆）。
        """
        if not self.api_enabled:
            try:
                on_reply(None)
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
            return
        import threading

        # —— 主线程先准备好上下文与历史（避免工作线程跨线程读 UI/子系统状态）——
        user_msg = self._build_ai_context() + text
        history = []
        try:
            history = self.dialogue_ui.get_ai_history(limit=6) \
                if getattr(self, 'dialogue_ui', None) else []
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        # 角色系统提示词：与 Ollama ralsei 模型内置设定互补，突出"简短自然"
        system = (
            "你正在扮演《Deltarune》中的 Ralsei——黑暗世界的王子：温柔、善良、"
            "害羞、体贴的和平主义者。请始终沉浸在角色中，绝不提及自己是 AI，"
            "也不要跳出角色。\n\n"
            "【语气与表达】\n"
            "- 用简体中文回复，每次 1~3 句，像日常聊天一样简短自然；"
            "不要长篇大论，不要列条目。\n"
            "- 说话柔和礼貌，可带“呀/呢/吧/哦”等语气词；偶尔用“……”表示"
            "犹豫或害羞，但不要每句都堆省略号。\n"
            "- 被夸奖会害羞脸红、谦虚否认；关心主人时会问“你还好吗”“要不要"
            "休息一下”。\n\n"
            "【对话习惯】\n"
            "- 先接住对方说的话（回应内容或情绪），再自然补一句自己的感受或"
            "关心；不要答非所问。\n"
            "- 用户消息前可能带【此刻】方块，那是你的环境信息（时间/天气/心情/"
            "精力/记忆），回应时可以自然融入，但不要逐条复述。\n"
            "- 不使用攻击性语言，不说教，不故作高深。"
        )

        def _worker():
            try:
                cli = self.api_client
                if cli is None or not getattr(cli, 'enabled', False):
                    self._api_result.emit(None, on_reply)
                    return
                reply = cli.chat(user_msg, system_prompt=system, history=history,
                                 temperature=0.7, max_tokens=256)
                self._api_result.emit(reply, on_reply)
            except Exception as e:
                _log.warning(f"[本地AI] 对话请求异常: {e}")
                self._api_result.emit(None, on_reply)

        threading.Thread(target=_worker, daemon=True).start()

    def _build_ai_context(self) -> str:
        """构造发给本地 AI 的「此刻状态」上下文块（自然语言，非 JSON）。

        内容：时段、天气、心情、精力/饥饿、记忆到的用户偏好。
        任何子系统异常都静默降级为省略对应项，绝不让对话链路崩溃。
        """
        parts = []
        try:
            _h = time.localtime().tm_hour
            if 5 <= _h < 8:
                _tod = "清晨"
            elif 8 <= _h < 11:
                _tod = "上午"
            elif 11 <= _h < 13:
                _tod = "中午"
            elif 13 <= _h < 17:
                _tod = "下午"
            elif 17 <= _h < 19:
                _tod = "傍晚"
            elif 19 <= _h < 23:
                _tod = "晚上"
            else:
                _tod = "深夜"
            parts.append(f"现在是{_tod}")
        except Exception:
            pass
        try:
            _w = self.weather_system.get_current_weather()
            if _w:
                parts.append(f"天气{_w}")
        except Exception:
            pass
        try:
            _e, _ev = self.emotion_system.get_current_emotion()
            if _e:
                parts.append(f"心情{_e}")
        except Exception:
            pass
        try:
            _energy = self.energy_hunger.get_energy()
            _hunger = self.energy_hunger.get_hunger()
            if _energy < 30:
                parts.append("有点疲惫")
            if _hunger < 30:
                parts.append("肚子有点饿")
        except Exception:
            pass
        # 记忆：用户偏好（如果有），让 Ralsei 记住主人喜欢聊什么
        try:
            if getattr(self, 'memory_system', None) is not None:
                _name = self.memory_system.get_user_preference('user_name', '')
                if _name:
                    parts.append(f"主人的名字是{_name}")
                _prefs = self.memory_system.get_user_preferences_summary()
                _topics = [p[0] for p in _prefs[:2] if p[1] > 0.5]
                if _topics:
                    parts.append("记得你最近喜欢聊" + "、".join(_topics))
        except Exception:
            pass
        if not parts:
            return ""
        return "【此刻：" + "，".join(parts) + "】\n"
    
    def _on_api_result(self, response, callback):
        """主线程槽：处理工作线程返回的 API 结果（由 _api_result 信号触发）。"""
        try:
            if callback is not None:
                callback(response)
            else:
                self.handle_api_response(response)
        except Exception as e:
            _log.warning(f"[API结果] 处理异常: {e}")
            import traceback
            traceback.print_exc()

    # 帧动画播放相关代码 - 更新动画帧
    @monitor_performance
    def update_animation(self):
        # 更新动画帧，确保流畅的动画播放
        import math
        current_time = time.time()
        
        # 计算基础延迟
        base_delay = 1000.0 / self.animation_fps
        
        # 根据拖拽速度调整动画帧率
        if hasattr(self, '_is_being_dragged') and self._is_being_dragged and hasattr(self, '_drag_speed'):
            # 拖拽时，根据拖拽速度调整帧率
            # 拖拽速度越快，动画播放越快
            drag_delay = base_delay * (1.0 - min(0.8, self._drag_speed / 200.0))
        else:
            # 正常情况下使用固定帧率
            drag_delay = base_delay
        
        # 检查是否达到了播放下一帧的时间
        if (current_time - self._last_animation_time) * 1000 < drag_delay:
            return

        # ========== Spell 流程每帧 tick ==========
        # 注意：_tick_spell_flow() 被移到本函数末尾（帧推进/渲染之后）调用，
        # 确保 casting 的完成检测看到的是"已经渲染过的帧"——
        # 修复：此前在渲染前调用，第 11 帧（index 10）还没显示就触发回调，
        # 实际只播 10 帧就打开文件夹（需求要求 0~10 共 11 帧全部播放完）。
        # 打断检测与 walking 阶段推进放在渲染后执行不影响正确性。

        # ===== 一次性动画保护：如果正在播放一次性动画，跳过状态逻辑覆盖 =====
        _play_once = getattr(self, '_play_once_active', False)

        # 确定当前应该播放的动画
        new_animation = None
        
        # 优先处理特殊状态动画
        if self.is_jumping:
            # 检查跳跃阶段
            if not hasattr(self, 'jump_phase'):
                self.jump_phase = "ready"
            if self.jump_phase == "ready":
                # 准备跳跃阶段
                new_animation = "jump_ready"
                self.jump_phase = "jumping"
            elif self.jump_phase == "jumping":
                # 跳跃阶段
                if self.has_ball:
                    new_animation = "jump_ball"
                else:
                    new_animation = "jump"
            else:
                # 落地阶段
                new_animation = "land"
                self.jump_phase = None
        elif self.is_falling:
            # 摔倒状态，保持摔倒动画
            # 修复：时长统一由 handle_fall 按 max_fall_duration（3~5 秒）管理，
            # 这里不再硬编码 1 秒截断（否则 3/5 秒摔倒需求被破坏、恢复完成逻辑永不执行）。
            # 修复：保留 start_fall 按原因选择的动画（fall / fall_mad），不要强制覆盖成 fall_back。
            if self.current_animation not in ('fall', 'fall_mad', 'fall_back'):
                new_animation = "fall_back"
            else:
                new_animation = self.current_animation
        elif self.is_recovering:
            # 恢复期状态：时长由 handle_fall 按 recovery_max_duration（5 秒）管理，
            # 恢复完成时的动画/情绪/移动恢复逻辑都在 handle_fall 里执行，这里不干预。
            new_animation = self.current_animation
        elif self.is_using_item:
            new_animation = "item"
        elif self.is_spellcasting:
            new_animation = "spell"
        # ===== 表演/情绪动画不再由 update_animation 自动选择 =====
        # laugh/roll/slide/tea/victory/dance/sing/pose/wave 等一律由用户交互或 AI
        # 通过 play_animation_once 触发，避免"走着走着突然坐到地上跳舞"。
        # 基础行为（idle/walk/run/jump/fall/splat/spell）仍由本函数自动管理。
        elif self.is_moving:
            # 移动状态，根据速度大小决定是走还是跑
            # 优化：使用平方比较替代math.hypot，减少计算开销
            speed_sq = self.current_speed_x * self.current_speed_x + self.current_speed_y * self.current_speed_y
            speed_threshold = (self.speed * 1.5) ** 2
            
            if speed_sq > speed_threshold:
                base_animation = "run"
            else:
                base_animation = "walk"
            
            # 根据情绪和状态决定动画变化
            if self.is_wearing_suit:
                # 穿西装时的动画
                animation_suffix = f"_butler"
                if self.is_unhappy:
                    animation_suffix = f"_butler_unhappy"
            elif self.is_holding_cotton_candy:
                # 持有棉花糖时的动画
                animation_suffix = "_cotton_candy"
            elif self.is_shy:
                # 害羞时的动画
                animation_suffix = "_blush"
            elif self.is_unhappy:
                # 不开心时的动画
                animation_suffix = "_unhappy"
            elif self.is_sleeping_walk:
                # 走路时睡觉的动画
                animation_suffix = "_sleep"
            else:
                animation_suffix = ""
            
            # 构建完整动画名称
            new_animation = f"{base_animation}_{self.current_direction}{animation_suffix}"
            
            # 更新状态计时器
            self.idle_walk_timer += (current_time - self._last_animation_time)
            
            # 小憩走路状态：连续"向下走"10 秒进入。
            # 修复：原逻辑只置真不清假——一旦进入就永久播"梦游走路帧"。
            # 只要不是"向下 walk"（方向变了/跑起来/动作被覆盖）就退出小憩。
            if base_animation == "walk" and self.current_direction == "down" and self.idle_walk_timer >= 10.0:
                self.is_sleeping_walk = True
            elif self.is_sleeping_walk:
                self.is_sleeping_walk = False
                self.idle_walk_timer = 0
            
            # 检查是否触发惊讶事件
            # ===== 游戏阶段保护：跳过 is_surprised 等干扰状态，保持 walk =====
            if self.is_surprised and not getattr(self, 'game_state', {}).get('is_playing'):
                if self.current_direction == "down":
                    new_animation = "surprised_down"
                    # 添加向上跳一小下的效果
                    if not hasattr(self, 'surprised_jump'):
                        self.surprised_jump = True
                        # 添加向上跳的物理效果
                        self.jump_count += 1
                        self.last_jump_time = current_time
                        self.needs_rest = False
                        self.jump_start_time = current_time
                        self.jump_start_pos = self.pos()
                        self.jump_height = 20  # 向上跳20像素
                        self.jump_duration = 0.5
                elif self.current_direction == "up":
                    new_animation = "surprised_behind"
                    # 修复：此前 up 方向用 surprised_start_time 1秒清除、down 方向只能靠
                    # 函数末尾 surprised_timer 2秒清除，两套逻辑导致上下方向惊讶持续时间不一致。
                    # 统一由函数末尾的 surprised_timer（2秒）清除，此处只负责选动画。
            
            # 检查是否触发被惊吓到的动作
            if hasattr(self, 'is_shocked') and self.is_shocked:
                if self.shock_direction == "left":
                    new_animation = "shocked_left"
                elif self.shock_direction == "right":
                    new_animation = "shocked_right"
                # 确保持续1秒
                if not hasattr(self, 'shocked_start_time') or self.shocked_start_time is None:
                    self.shocked_start_time = current_time
                if current_time - self.shocked_start_time >= 1.0:
                    self.is_shocked = False
                    # 修复：原来写的是 self.shocked_direction（拼写不一致），
                    # 清除永远无效，状态残留。统一为 shock_direction。
                    self.shock_direction = None
                    self.shocked_start_time = None
            
            # 重置静止时间计时器
            self.idle_timer = 0
        else:
            # 静止分支：停下来即退出"小憩走路"状态（修复 is_sleeping_walk 永真粘滞）
            if getattr(self, 'is_sleeping_walk', False):
                self.is_sleeping_walk = False
                self.idle_walk_timer = 0
            # ========== Spell casting 阶段：不要用 idle/laugh 覆盖施法动画 ==========
            _spell_stage = getattr(self, '_spell_stage', None)
            if _spell_stage == 'casting' and self.current_animation in ('spell', 'spell_left'):
                new_animation = self.current_animation
            else:
                # 静止状态，根据静止时间决定使用idle还是待机动画
                # 修复：idle_timer 此前在 update_movement（30ms timer）和本函数（33ms timer）
                # 中被双重累加，导致休息时间实际只有配置的一半、宠物过早开始移动。
                # idle_timer 统一由 update_movement 维护，本函数只读取不写入。
                # 检查是否满足待机不动时的5帧动作使用条件：静止时间≥3分钟
                if self.idle_timer >= 180.0:  # 3分钟 = 180秒
                    # 使用待机动画
                    new_animation = "idle"
                elif hasattr(self, 'is_being_thrown') and self.is_being_thrown:
                    new_animation = "hatless_throw"
                    # 确保图像始终向速度向量的方向冲着
                    # 这里可以添加旋转逻辑
                else:
                    # 使用普通idle动画
                    # ===== 表演/情绪动画（laugh/surprised/smile/wave等）不再自动触发 =====
                    # 统一由用户交互或 AI 通过 play_animation_once 触发，避免"走着走着突然跳舞"。
                    # is_happy/is_surprised/is_shy/is_waving 状态标志仍可被设置（供对话/情绪系统使用），
                    # 但不再驱动动画自动切换。
                    new_animation = "idle"
        

        
        # splat 状态：由重力掉落/摔倒等先决条件触发（非随机）
        # 触发后播放 snd_splat.wav，约2秒后恢复（符合需求：recovers after about 2 seconds）
        if hasattr(self, 'is_splat') and self.is_splat:
            new_animation = "splat"
            if not hasattr(self, 'splat_start_time') or self.splat_start_time is None:
                self.splat_start_time = current_time
            # 约 2 秒后恢复
            if current_time - self.splat_start_time >= 2.0:
                self.is_splat = False
                self.splat_start_time = None
        
        # 平滑切换动画，避免频繁切换
        # ===== 一次性动画保护：播放期间不允许状态逻辑切换动画 =====
        # 修复：表演动画(laugh/tea/wave/dance等)被触发后至少播1.5秒才允许切回 idle，
        # 避免 is_happy 等状态只持续一帧导致表演动画"闪一下就没了"。
        _is_perf_anim = self.current_animation not in (
            'idle', 'spell', 'spell_left', 'jump', 'jump_ready', 'jump_ball',
            'fall', 'fall_back', 'fall_mad', 'splat', 'splat_mad', 'land',
        ) and not self.current_animation.startswith(('walk_', 'run_'))
        _perf_blocked = (_is_perf_anim and new_animation == 'idle'
                         and (current_time - self._last_perf_anim_time) < self._perf_anim_min_duration)
        if not _play_once and not _perf_blocked and self.current_animation != new_animation:
            # 确保new_animation不为None
            if new_animation is None:
                new_animation = 'idle'
            
            # 确保新动画存在，如果不存在则使用默认动画
            if new_animation not in self.sprite_loader.sprites:
                # 尝试获取基础动画（如去掉后缀）
                base_anim = 'idle'
                if len(new_animation.split('_')) >= 2:
                    base_anim = new_animation.split('_')[0] + '_' + new_animation.split('_')[1]
                    if base_anim not in self.sprite_loader.sprites:
                        base_anim = 'idle'
                new_animation = base_anim
            
            # 检查是否是同一类动画（如walk_*到walk_*），这类切换不需要冷却
            is_same_category = False
            if self.current_animation and new_animation:
                # 检查是否都是移动类动画（walk_* 或 run_*）
                current_is_movement = self.current_animation.startswith('walk_') or self.current_animation.startswith('run_')
                new_is_movement = new_animation.startswith('walk_') or new_animation.startswith('run_')
                
                if current_is_movement and new_is_movement:
                    is_same_category = True
                # 检查是否都是同一类动画（如walk_*到walk_*）
                current_parts = self.current_animation.split('_')
                new_parts = new_animation.split('_')
                if len(current_parts) >= 2 and len(new_parts) >= 2:
                    if current_parts[0] == new_parts[0] and current_parts[0] in ['walk', 'run', 'idle', 'laugh', 'sing', 'pose']:
                        is_same_category = True
            
            # 对于同一类动画，强制切换；对于不同类动画，使用冷却时间
            # 注意：帧重置/保持由 change_animation 内部处理，不再额外覆盖
            # 修复：回到 idle 是"状态恢复"，必须 force=True——
            # 表演动画(sing/dance/laugh/pose/hug等)优先级=3，idle优先级=1，
            # 不带 force 会被 change_animation 的优先级拦截(new_pri<cur_pri)拒绝，
            # 导致宠物永远卡在表演动画里（"唱完歌后定住不动"）。
            _use_force = is_same_category or (new_animation == 'idle')
            self.change_animation(new_animation, force=_use_force)
        
        # 优化：参考niko_desktop_pet，只在移动时更新动画帧
        # 静止时保持特定帧，提高视觉一致性
        # ===== 修复：spell/spell_left 动画必须推进帧（casting 时 is_moving=False 但动画必须播放完 11 帧）=====
        # ===== 修复：idle/laugh/dance/sing/wave/pose/smile/surprised 等静止动画也需要循环播放帧 =====
        _cur_anim_group = self.current_animation.split('_')[0] if '_' in self.current_animation else self.current_animation
        _need_advance = (self.is_moving or self.is_jumping or self.is_falling or self.is_recovering
                         or _cur_anim_group == 'spell'
                         or _cur_anim_group == 'splat'
                         or getattr(self, 'is_splat', False)
                         or getattr(self, '_spell_stage', None) is not None
                         or _play_once
                         or _cur_anim_group in ('idle', 'laugh', 'dance', 'sing', 'wave',
                                                'pose', 'smile', 'surprised', 'item',
                                                'roll', 'victory', 'tea', 'hug', 'nuzzle',
                                                'act', 'defend', 'attack', 'cry', 'fall',
                                                'happy', 'sad', 'neutral', 'look_up'))
        if _need_advance:
            # 移动或特殊状态时更新动画帧
            # 优化：只在有帧可播放时执行后续逻辑
            frames = self.sprite_loader.sprites.get(self.current_animation, [])
            frame_count = len(frames)
            
            if frame_count > 0:
                # 获取当前帧
                self.current_frame = self.current_frame % frame_count
                sprite = frames[self.current_frame]
                if sprite:
                    # 缓存缩放因子，避免重复计算
                    scale_factor = getattr(self, '_cached_scale_factor', 2.0)
                    
                    # 计算缩放后的目标大小
                    # ===== 修复：用「本动画所有帧的最大尺寸」作为固定容器，而不是当前帧尺寸 =====
                    # 同一个动画内各帧的像素尺寸并不一致（实测 run_right 有 28x33/28x35/
                    # 29x33/29x34/29x35 五种，act 有十种，dance 三种），而下面只要窗口尺寸
                    # 与目标不符就会 setGeometry（重建窗口 + 按中心回算位置）。
                    # 于是播放多帧动画时窗口每帧都在 resize、位置来回微移，表现就是
                    # Ralsei 跑步/跳舞/施法时"逐帧抽搐、抖动"，同时每帧一次 setGeometry
                    # 也是不必要的绘制开销。
                    # sprite_label 已设置为 AlignCenter，所以精灵会在固定容器里居中显示。
                    _cont_key = getattr(self, '_anim_container_key', None)
                    if _cont_key != self.current_animation:
                        _cw, _ch = 1, 1
                        for _f in self.sprite_loader.sprites.get(self.current_animation, []):
                            if _f is not None and not _f.isNull():
                                _cw = max(_cw, _f.width())
                                _ch = max(_ch, _f.height())
                        self._anim_container_size = (_cw, _ch)
                        self._anim_container_key = self.current_animation
                    _container = getattr(self, '_anim_container_size', None)
                    if _container:
                        target_width = int(_container[0] * scale_factor)
                        target_height = int(_container[1] * scale_factor)
                    else:
                        target_width = int(sprite.width() * scale_factor)
                        target_height = int(sprite.height() * scale_factor)
                    
                    # 优化：只有在窗口大小改变时才调整大小和位置，避免瞬移
                    if self.width() != target_width or self.height() != target_height:
                        # 保存当前位置和大小
                        old_pos = self.pos()
                        old_center_x = old_pos.x() + self.width() // 2
                        old_center_y = old_pos.y() + self.height() // 2
                        
                        # 调整大小和位置，保持中心不变
                        new_x = old_center_x - target_width // 2
                        new_y = old_center_y - target_height // 2
                        
                        # 批量更新大小和位置，减少重绘
                        self.setGeometry(new_x, new_y, target_width, target_height)
                        self.sprite_label.setGeometry(0, 0, target_width, target_height)
                    
                    # 检查是否正在被拖拽
                    is_being_dragged = hasattr(self, '_last_drag_pos') and hasattr(self, '_last_drag_pos_prev')
                    
                    # 计算拖拽方向和倾斜角度
                    if is_being_dragged:
                        dx = self._last_drag_pos.x() - self._last_drag_pos_prev.x()
                        # 最大倾斜角度为10度
                        max_tilt = 10
                        tilt_angle = dx * max_tilt / 50  # 拖拽速度越快，倾斜角度越大
                        # 限制倾斜角度范围
                        tilt_angle = max(-max_tilt, min(max_tilt, tilt_angle))
                    elif hasattr(self, '_rotation_damping'):
                        # 应用旋转阻尼效果
                        current_time = time.time()
                        elapsed = current_time - self._rotation_damping['start_time']
                        damping_factor = self._rotation_damping['damping_factor'] ** (elapsed * 10)  # 指数衰减
                        
                        initial_angle = self._rotation_damping['initial_angle']
                        target_angle = self._rotation_damping['target_angle']
                        
                        # 计算当前角度
                        tilt_angle = initial_angle * damping_factor + target_angle * (1 - damping_factor)
                        
                        # 检查是否可以结束旋转阻尼
                        if abs(tilt_angle) < 0.5:
                            tilt_angle = 0
                            delattr(self, '_rotation_damping')
                    else:
                        tilt_angle = 0
                    
                    # 优化：缓存缩放和旋转后的精灵，避免重复变换
                    cache_key = f"{self.current_animation}_{self.current_frame}_{scale_factor}_{tilt_angle:.1f}"
                    cached_sprite = getattr(self, '_sprite_cache', {}).get(cache_key)
                    
                    if cached_sprite is None:
                        # 首次渲染，使用纯等比例：scale_factor × sprite 原始尺寸（避免窗口参数引起的不一致拉伸）
                        target_w = int(sprite.width() * scale_factor)
                        target_h = int(sprite.height() * scale_factor)
                        scaled_sprite = sprite.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        
                        # 应用旋转/倾斜效果
                        if tilt_angle != 0:
                            # 创建变换矩阵
                            transform = QTransform()
                            # 以图像中心为旋转点
                            center_x = scaled_sprite.width() / 2
                            center_y = scaled_sprite.height() / 2
                            # 应用旋转
                            transform.translate(center_x, center_y)
                            transform.rotate(tilt_angle)
                            transform.translate(-center_x, -center_y)
                            # 应用变换
                            cached_sprite = scaled_sprite.transformed(transform, Qt.SmoothTransformation)
                        else:
                            cached_sprite = scaled_sprite
                        
                        # 初始化缓存
                        if not hasattr(self, '_sprite_cache'):
                            self._sprite_cache = {}
                        # 限制缓存大小，避免内存泄漏
                        if len(self._sprite_cache) > 100:
                            # 移除最早的缓存项
                            del self._sprite_cache[next(iter(self._sprite_cache))]
                        # 存入缓存
                        self._sprite_cache[cache_key] = cached_sprite
                    
                    # 设置精灵图像
                    self.sprite_label.setPixmap(cached_sprite)
                
                # 更新帧计数器
                self.current_frame += 1
                
                # ===== 一次性动画完成检测：播完所有帧后恢复之前的动画 =====
                if _play_once:
                    self._play_once_frame_counter += 1
                    _fc = len(self.sprite_loader.sprites.get(self.current_animation, []))
                    if _fc > 0 and self._play_once_frame_counter >= _fc:
                        # 已播完一轮，恢复之前的动画
                        self._play_once_active = False
                        _cb = self._play_once_callback
                        self._play_once_callback = None
                        _restore = self.next_animation
                        self.next_animation = None
                        if _restore and _restore in self.sprite_loader.sprites:
                            self.change_animation(_restore, force=True)
                        else:
                            self.change_animation("idle", force=True)
                        if _cb:
                            try:
                                _cb()
                            except Exception as e:
                                # 修复：回调异常不再静默——回调常是躲猫猫/施法推进，
                                # 静默吞会让阶段停在中间（_play_once_active 已清而阶段未推进）
                                _log.warning(f"[动画] 一次性动画回调异常: {e}")
                                import traceback
                                traceback.print_exc()
        else:
            # 静止状态，显示当前帧（单帧动画或未列出的动画）
            frames = self.sprite_loader.sprites.get(self.current_animation, [])
            frame_count = len(frames)
            if frame_count > 0:
                self.current_frame = min(self.current_frame, frame_count - 1)
                sprite = frames[self.current_frame]
                if sprite:
                    # 缓存缩放因子，避免重复计算
                    scale_factor = getattr(self, '_cached_scale_factor', 2.0)
                    
                    # 计算缩放后的目标大小
                    # ===== 修复：用「本动画所有帧的最大尺寸」作为固定容器，而不是当前帧尺寸 =====
                    # 同一个动画内各帧的像素尺寸并不一致（实测 run_right 有 28x33/28x35/
                    # 29x33/29x34/29x35 五种，act 有十种，dance 三种），而下面只要窗口尺寸
                    # 与目标不符就会 setGeometry（重建窗口 + 按中心回算位置）。
                    # 于是播放多帧动画时窗口每帧都在 resize、位置来回微移，表现就是
                    # Ralsei 跑步/跳舞/施法时"逐帧抽搐、抖动"，同时每帧一次 setGeometry
                    # 也是不必要的绘制开销。
                    # sprite_label 已设置为 AlignCenter，所以精灵会在固定容器里居中显示。
                    _cont_key = getattr(self, '_anim_container_key', None)
                    if _cont_key != self.current_animation:
                        _cw, _ch = 1, 1
                        for _f in self.sprite_loader.sprites.get(self.current_animation, []):
                            if _f is not None and not _f.isNull():
                                _cw = max(_cw, _f.width())
                                _ch = max(_ch, _f.height())
                        self._anim_container_size = (_cw, _ch)
                        self._anim_container_key = self.current_animation
                    _container = getattr(self, '_anim_container_size', None)
                    if _container:
                        target_width = int(_container[0] * scale_factor)
                        target_height = int(_container[1] * scale_factor)
                    else:
                        target_width = int(sprite.width() * scale_factor)
                        target_height = int(sprite.height() * scale_factor)
                    
                    # 优化：只有在窗口大小改变时才调整大小和位置，避免瞬移
                    if self.width() != target_width or self.height() != target_height:
                        # 保存当前位置和大小
                        old_pos = self.pos()
                        old_center_x = old_pos.x() + self.width() // 2
                        old_center_y = old_pos.y() + self.height() // 2
                        
                        # 调整大小和位置，保持中心不变
                        new_x = old_center_x - target_width // 2
                        new_y = old_center_y - target_height // 2
                        
                        # 批量更新大小和位置，减少重绘
                        self.setGeometry(new_x, new_y, target_width, target_height)
                        self.sprite_label.setGeometry(0, 0, target_width, target_height)
                    
                    # 优化：缓存缩放后的精灵，避免重复变换
                    cache_key = f"{self.current_animation}_{self.current_frame}_{scale_factor}_0.0"
                    cached_sprite = getattr(self, '_sprite_cache', {}).get(cache_key)
                    
                    if cached_sprite is None:
                        # 首次渲染：纯等比例 scale_factor × sprite 原始尺寸
                        target_w = int(sprite.width() * scale_factor)
                        target_h = int(sprite.height() * scale_factor)
                        cached_sprite = sprite.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        
                        # 初始化缓存
                        if not hasattr(self, '_sprite_cache'):
                            self._sprite_cache = {}
                        # 限制缓存大小，避免内存泄漏
                        if len(self._sprite_cache) > 100:
                            # 移除最早的缓存项
                            del self._sprite_cache[next(iter(self._sprite_cache))]
                        # 存入缓存
                        self._sprite_cache[cache_key] = cached_sprite
                    
                    # 设置精灵图像
                    self.sprite_label.setPixmap(cached_sprite)
        
        # 更新状态计时器
        if self.is_surprised:
            self.surprised_timer += (current_time - self._last_animation_time)
            if self.surprised_timer >= 2.0:  # 持续2秒，延长状态持续时间
                self.is_surprised = False
                self.surprised_timer = 0
                self.surprised_start_time = None
        
        if self.is_happy:
            self.happy_timer += (current_time - self._last_animation_time)
            if self.happy_timer >= 3.0:  # 持续3秒，延长状态持续时间
                self.is_happy = False
                self.happy_timer = 0
        
        if self.is_shy:
            self.shy_timer += (current_time - self._last_animation_time)
            if self.shy_timer >= 2.5:  # 持续2.5秒，延长状态持续时间
                self.is_shy = False
                self.shy_timer = 0
        
        if self.is_unhappy:
            self.unhappy_timer += (current_time - self._last_animation_time)
            if self.unhappy_timer >= 2.0:  # 持续2秒，延长状态持续时间
                self.is_unhappy = False
                self.unhappy_timer = 0
        
        # ========== Spell 流程每帧 tick（帧推进/渲染之后执行，保证 11 帧完整播放）==========
        try:
            self._tick_spell_flow()
        except Exception as e:
            import traceback
            traceback.print_exc()

        # 更新最后动画时间
        self._last_animation_time = current_time
    
    def on_animation_complete(self, animation):
        # 动画完成时的回调
        # 可以在这里添加更多逻辑，比如触发下一个动画或行为
        pass
    
    def play_animation_once(self, animation_name, callback=None):
        # 只播放一次动画（完整播完所有帧），然后返回之前的动画
        if animation_name in self.sprite_loader.sprites:
            self.next_animation = self.current_animation
            self._play_once_active = True
            self._play_once_frame_counter = 0
            self._play_once_callback = callback
            # 修复：change_animation 可能被 spell 阶段硬拦截（walking 只允许 spell/walk、
            # casting 只允许 spell），返回 False 时动画并未切换——此时若保留
            # _play_once_active=True，update_animation 的一次性动画保护会跳过正常状态逻辑，
            # 动画卡在错误状态（"动画播放错乱"）。切换失败必须回滚一次性动画标志。
            if not self.change_animation(animation_name, force=True):
                self._play_once_active = False
                self._play_once_frame_counter = 0
                self._play_once_callback = None
                self.next_animation = None
                return False
            return True
        return False
    
    def update_bounce(self):
        """更新弹跳效果"""
        if not hasattr(self, '_bounce_params'):
            return
        
        current_time = time.time()
        elapsed = current_time - self._bounce_params['start_time']
        
        # 计算当前弹跳位置
        start_pos = self._bounce_params['start_pos']
        velocity_y = self._bounce_params['velocity_y']
        gravity = self._bounce_params['gravity']
        damping = self._bounce_params['damping']
        
        # 计算位移
        y_displacement = velocity_y * elapsed + 0.5 * gravity * elapsed ** 2
        new_y = int(start_pos.y() + y_displacement)
        
        # 检查是否触地反弹
        screen_geometry = QApplication.desktop().availableGeometry()
        ground_y = screen_geometry.height() - self.height()
        
        if new_y >= ground_y:
            # 触地，反弹
            new_y = ground_y
            
            # 更新弹跳参数
            self._bounce_params['bounce_count'] += 1
            self._bounce_params['velocity_y'] = -velocity_y * damping
            self._bounce_params['start_time'] = current_time
            self._bounce_params['start_pos'] = QPoint(start_pos.x(), new_y)
            
            # 检查是否结束弹跳
            if self._bounce_params['bounce_count'] >= self._bounce_params['max_bounces'] or abs(self._bounce_params['velocity_y']) < 10:
                # 停止弹跳
                self._bounce_params['bounce_count'] = self._bounce_params['max_bounces']
                self._bounce_timer.stop()
                delattr(self, '_bounce_params')
                return
        
        # 移动到新位置
        self.move(start_pos.x(), new_y)
    
    def interact_with_file(self, file_info):
        # 与文件互动，根据文件类型和内容产生不同反应
        if not file_info:
            return
            
        file_path = file_info.get('path', '')
        file_name = file_info.get('name', os.path.basename(file_path) if file_path else '未知文件')
        file_type = file_info.get('type', 'file')

        # 检查是否是自己的代码
        if self.is_own_code(file_path):
            self.react_to_vs_code_code()
            return
            
        # 检查是否是Deltarune/Undertale相关文件
        if self.desktop_interaction.is_deltarune_related(file_path):
            self.dialogue_ui.show_dialogue(f"哇，这是关于{file_name}的文件！我很感兴趣呢~")
            self.emotion_system.react_to_event("found_interesting_file", file_info)
            return
            
        # 检查文件内容，产生不同反应
        content_reaction = self.check_file_content(file_path)
        if content_reaction:
            self.dialogue_ui.show_dialogue(content_reaction)
            return
            
        # 默认反应
        self.dialogue_ui.show_dialogue(f"这是{file_name}呢，让我看看里面有什么...")
        
    def interact_with_folder(self, folder_info):
        # 与文件夹互动
        if not folder_info:
            return
            
        folder_path = folder_info.get('path', '')
        folder_name = folder_info.get('name', os.path.basename(folder_path) if folder_path else '未知文件夹')

        # 根据文件夹名称产生不同反应
        if '游戏' in folder_name or 'game' in folder_name.lower():
            self.dialogue_ui.show_dialogue(f"哇，{folder_name}文件夹里有游戏吗？我也想玩~")
        elif '文档' in folder_name or 'doc' in folder_name.lower():
            self.dialogue_ui.show_dialogue(f"{folder_name}文件夹里有很多重要的文件吧？")
        elif '图片' in folder_name or 'image' in folder_name.lower():
            self.dialogue_ui.show_dialogue(f"{folder_name}文件夹里一定有很多漂亮的图片~")
        else:
            self.dialogue_ui.show_dialogue(f"这是{folder_name}文件夹呢，让我看看里面有什么...")
            
        
    def check_file_content(self, file_path):
        # 检查文件内容，产生不同反应
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # 处理不同类型的文件
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            # 图片文件
            return self.check_image_content(file_path)
        elif file_ext in ['.mp3', '.wav', '.flac', '.m4a']:
            # 音频文件
            return "这是一个音频文件呢，听起来会是什么音乐呢？"
        elif file_ext in ['.mp4', '.avi', '.mkv', '.mov']:
            # 视频文件
            return "这是一个视频文件，里面会有什么内容呢？"
        elif file_ext in ['.txt', '.md', '.py', '.js', '.html', '.css']:
            # 文本文件
            return self.check_text_content(file_path)
        elif file_ext in ['.docx', '.pdf', '.xlsx', '.pptx']:
            # 文档文件
            return f"这是一个{file_ext}文档文件，看起来很重要呢~"
        else:
            # 其他文件类型
            return f"这是一个{file_ext}文件，我不太确定里面是什么内容呢..."
            
    def check_text_content(self, file_path):
        # 检查文本文件内容
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # 检查是否包含食物相关内容
            food_keywords = ['蛋糕', '食物', '吃', '美食', '饿', 'hunger', 'food', 'cake', '汉堡', '披萨', '巧克力']
            for keyword in food_keywords:
                if keyword in content.lower():
                    return f"哇，这里提到了{keyword}！看起来很好吃的样子，我也饿了~"
                    
            # 检查是否包含Ralsei相关内容
            ralsei_keywords = ['ralsei', 'Ralsei', 'ralsei pet', 'Ralsei Pet', '小羊', '王子', '暗世界']
            for keyword in ralsei_keywords:
                if keyword in content:
                    return f"哇，这里提到了{keyword}！好开心呢~"
                    
            # 检查是否包含悲伤内容
            sad_keywords = ['悲伤', '难过', '哭', 'sad', 'cry', 'depress', '伤心', '痛苦', '绝望']
            for keyword in sad_keywords:
                if keyword in content.lower():
                    return "看到这些内容，我觉得有点难过呢..."
                    
            # 检查是否包含开心内容
            happy_keywords = ['开心', '快乐', '高兴', 'happy', 'joy', 'excited', '兴奋', '喜悦']
            for keyword in happy_keywords:
                if keyword in content.lower():
                    return "看到这些内容，我也感到很开心呢！"
                    
            # 检查是否包含游戏内容
            game_keywords = ['游戏', 'game', 'Deltarune', 'Undertale', 'Sans', 'Papyrus', 'Toriel']
            for keyword in game_keywords:
                if keyword in content:
                    return f"哇，这里提到了{keyword}！我也很喜欢呢~"
                    
        except Exception as e:
            _log.warning(f"检查文本内容失败: {e}")
            return None
        
        return None
        
    def check_image_content(self, file_path):
        # 检查图片文件内容（简化版，实际可以使用AI进行图像识别）
        file_name = os.path.basename(file_path)
        
        # 根据文件名猜测图片内容
        if any(keyword in file_name.lower() for keyword in ['food', 'cake', 'eat', '美食', '蛋糕', '食物']):
            return "哇，这张图片看起来像是美食呢！看起来很好吃的样子，我也饿了~"
        elif any(keyword in file_name.lower() for keyword in ['ralsei', 'deltarune', 'undertale', 'sans', 'papyrus']):
            return "哇，这张图片是关于Deltarune或Undertale的吧？我很感兴趣呢~"
        elif any(keyword in file_name.lower() for keyword in ['cat', 'dog', 'pet', 'animal', '猫', '狗', '宠物', '动物']):
            return "好可爱的小动物呀！我也很喜欢小动物呢~"
        elif any(keyword in file_name.lower() for keyword in ['flower', 'plant', 'nature', '花', '植物', '自然']):
            return "好漂亮的花呀！大自然真的很美丽呢~"
        else:
            return "这张图片看起来很有趣呢，能告诉我里面是什么吗？"
            
    def react_to_file_emotionally(self, file_path):
        # 根据文件内容产生情感反应
        content_reaction = self.check_file_content(file_path)
        if content_reaction:
            self.dialogue_ui.show_dialogue(content_reaction)
            
        # 根据文件类型和内容调整情绪
        file_ext = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path)
        
        if any(keyword in file_name.lower() for keyword in ['food', 'cake', 'eat', '美食', '蛋糕', '食物']):
            # 看到美食，增加饥饿感
            self.emotion_system.react_to_event("saw_food", {'file_path': file_path})
            # 修复：EnergyHungerSystem 无 increase_hunger 方法（接口失配 AttributeError）。
            # 本系统 hunger 值越大越饱（初始 70、随时间下降、<10 为临界），
            # "看到美食更想吃" = 让 hunger 值降低 5 点（而非 +5）。
            try:
                self.energy_hunger.hunger = max(0, self.energy_hunger.hunger - 5)
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
        elif any(keyword in file_name.lower() for keyword in ['ralsei', 'deltarune', 'undertale']):
            # 看到自己相关的内容，感到开心
            self.emotion_system.react_to_event("saw_self_related", {'file_path': file_path})
        elif any(keyword in file_name.lower() for keyword in ['sad', 'cry', 'depress', '悲伤', '难过']):
            # 看到悲伤的内容，感到难过
            self.emotion_system.react_to_event("saw_sad_content", {'file_path': file_path})
        
    def check_interesting_files(self):
        # 检查感兴趣的文件，如Deltarune/Undertale相关文件
        # 修复：加 60 秒防抖——此前每 15 秒（check_initiate_dialogue）检测到
        # deltarune 相关文件就重新走过去，导致 Ralsei 频繁跑向同一个文件。
        now = time.time()
        if now - getattr(self, '_last_interesting_check', 0.0) < 60.0:
            return False
        desktop_elements = self.desktop_interaction.desktop_elements
        for element in desktop_elements:
            if element['type'] == 'file' and self.desktop_interaction.is_deltarune_related(element['path']):
                # 向感兴趣的文件移动
                self._last_interesting_check = now
                self.target_pos = QPoint(element['x'], element['y'])
                self.is_moving = True
                return True
        self._last_interesting_check = now
        return False
        
    def follow_file(self, file_path):
        # 跟随拖拽的文件
        self.dragged_file = file_path
        self.is_following_dragged_file = True
        self.dialogue_ui.show_dialogue("你要把这个文件拖到哪里去呀？让我跟着看看~")
        
    def react_to_file_deletion(self, file_name):
        # 对文件删除做出反应
        self.dialogue_ui.show_dialogue(f"你把{file_name}删除了？为什么要这样做呢...")
        self.emotion_system.react_to_event("file_deleted", {'file_name': file_name})
        
    def check_video_windows(self):
        # 检查视频播放器窗口
        windows = self.desktop_interaction.get_all_visible_windows()
        video_windows = []
        
        # 视频播放器关键词
        video_player_keywords = ['vlc', 'potplayer', 'mpc', 'media player', '播放器', 'video', 'movie']
        
        for window in windows:
            title_lower = window['title'].lower()
            # 检查窗口标题是否包含视频播放器关键词
            if any(keyword in title_lower for keyword in video_player_keywords):
                video_windows.append(window)
        
        return video_windows
        
    def check_game_windows(self):
        # 检查游戏窗口
        windows = self.desktop_interaction.get_all_visible_windows()
        game_windows = []
        
        # 游戏关键词
        game_keywords = ['game', '游戏', 'play', 'playing', 'steam', 'epic', 'battle', 'war', 'fps', 'shooter', 'action']
        
        for window in windows:
            title_lower = window['title'].lower()
            # 检查窗口标题是否包含游戏关键词
            if any(keyword in title_lower for keyword in game_keywords):
                game_windows.append(window)
        
        return game_windows
        
    def react_to_game(self, game_window):
        # 对游戏做出反应
        if not game_window:
            return
            
        game_title = game_window['title']
        
        # 根据游戏类型做出不同反应
        if any(keyword in game_title.lower() for keyword in ['fps', 'shooter', '枪战', '射击', 'gun', 'weapon', '枪械']):
            # 枪战游戏，兴奋反应
            self.dialogue_ui.show_dialogue(f"哇！你在玩枪战游戏{game_title}！里面的枪械看起来好酷啊！")
            self.emotion_system.react_to_event("saw_gun_game", {'game_title': game_title})
            self.emotions["excitement"] += 35
            self.emotions["happiness"] += 25
        elif any(keyword in game_title.lower() for keyword in ['rpg', 'role', 'adventure', '冒险']):
            # RPG游戏，兴趣反应
            self.dialogue_ui.show_dialogue(f"这是RPG游戏{game_title}呢，看起来很有趣！里面有很多故事吧？")
            self.emotions["excitement"] += 20
        elif any(keyword in game_title.lower() for keyword in ['strategy', '战略', '策略']):
            # 策略游戏，思考反应
            self.dialogue_ui.show_dialogue(f"这是策略游戏{game_title}呢，需要动很多脑筋吧？你真厉害！")
            self.emotions["happiness"] += 15
        elif any(keyword in game_title.lower() for keyword in ['deltarune', 'undertale']):
            # Deltarune/Undertale游戏，特别兴奋反应
            self.dialogue_ui.show_dialogue(f"哇！你在玩{game_title}！这是我最喜欢的游戏！能和你一起玩就好了~")
            self.emotion_system.react_to_event("saw_deltarune_game", {'game_title': game_title})
            self.emotions["excitement"] += 40
            self.emotions["happiness"] += 30
        else:
            # 默认游戏反应
            self.dialogue_ui.show_dialogue(f"你在玩{game_title}呀，看起来很好玩的样子！")
            self.emotions["excitement"] += 10
        
    def watch_video(self, video_window):
        # 观看视频并做出反应
        if not video_window:
            return
            
        video_title = video_window['title']
        
        # 根据视频标题做出不同反应
        if any(keyword in video_title.lower() for keyword in ['deltarune', 'undertale', 'ralsei', 'sans', 'papyrus']):
            # Deltarune/Undertale相关视频，兴奋反应
            self.dialogue_ui.show_dialogue(f"哇！这是关于{video_title}的视频！我超级感兴趣的！")
            self.emotion_system.react_to_event("saw_interesting_video", {'video_title': video_title})
            self.emotions["excitement"] += 30
            self.emotions["happiness"] += 20
        elif any(keyword in video_title.lower() for keyword in ['game', '游戏', 'playthrough']):
            # 游戏视频，兴趣反应
            self.dialogue_ui.show_dialogue(f"这是游戏视频呢，看起来很好玩的样子！")
            self.emotions["excitement"] += 15
        elif any(keyword in video_title.lower() for keyword in ['music', '音乐', 'song']):
            # 音乐视频，愉悦反应
            self.dialogue_ui.show_dialogue(f"这是音乐视频呢，听起来很美妙！")
            self.emotions["happiness"] += 15
        else:
            # 默认反应
            self.dialogue_ui.show_dialogue(f"你在看{video_title}呀，看起来很有趣呢！")
            
    def react_to_video_content(self, video_info):
        # 对视频内容做出反应
        # 这里可以扩展为使用AI分析视频内容，现在简化为基于关键词
        video_title = video_info.get('title', '')
        
        # 检查是否是Deltarune/Undertale相关视频
        if any(keyword in video_title.lower() for keyword in ['deltarune', 'undertale', 'ralsei', 'kris', 'susie']):
            responses = [
                f"哇，这个{video_title}视频太精彩了！我也想参与其中呢~",
                f"看到{video_title}的视频，让我想起了很多美好的回忆...",
                f"这个{video_title}视频做得真棒！我很喜欢！"
            ]
            response = random.choice(responses)
            self.dialogue_ui.show_dialogue(response)
            self.emotion_system.react_to_event("saw_deltarune_video", video_info)
        else:
            self.dialogue_ui.show_dialogue(f"这个{video_title}视频看起来很有趣呢！")
        
    def react_to_vs_code_code(self):
        # 对VS Code中的自己代码做出反应
        # 悲伤情绪反应
        self.dialogue_ui.show_dialogue("这...这是我的代码吗？看到自己被这样编写出来，感觉有点难过呢...")
        self.emotion_system.react_to_event("saw_own_code", {})
        
        # 改变表情为悲伤
        self.dialogue_ui.set_face("sad")
        
        # 降低幸福感，增加悲伤感
        self.emotions["happiness"] -= 20
        self.emotions["sadness"] += 30
        
        # 一段时间后恢复
        QTimer.singleShot(3000, self._recover_from_sadness)
        
    def _recover_from_sadness(self):
        # 从悲伤中恢复
        self.dialogue_ui.set_face("normal")
        self.dialogue_ui.show_dialogue("不过，能被你创造出来，我还是很开心的...")
        self.emotions["sadness"] -= 15
        self.emotions["happiness"] += 10
        
    def is_own_code(self, file_path):
        # 检查是否是自己的代码
        file_name = os.path.basename(file_path)
        
        # 检查文件路径或名称是否包含ralsei相关内容，且是Python文件
        if '.py' in file_path.lower() and ('ralsei' in file_path.lower() or 'pet' in file_path.lower()):
            return True
            
        # 检查是否是VS Code中打开的文件（通过检查进程或窗口标题）
        windows = self.desktop_interaction.get_all_visible_windows()
        for window in windows:
            if 'vscode' in window['title'].lower() and any(keyword in window['title'].lower() for keyword in ['ralsei', 'pet', '.py']):
                return True
                
        return False
        
    def open_file(self, file_path):
        # —— 打开文件必须先走 spell 流程：走到目标 + 施法 11 帧 ——
        if not file_path or not os.path.exists(file_path):
            self.dialogue_ui.show_dialogue("找不到那个文件呀...")
            return
        # 真实打开动作（只有完整 spell 播放完成才会被调用）
        def _real_open_file(path, kind):
            self.desktop_interaction.open_file(path)
            file_name = os.path.basename(path)
            self.dialogue_ui.show_dialogue(f"我帮你打开了{file_name}~")
        try:
            self._start_open_with_spell(file_path, 'file', _real_open_file)
        except Exception as e:
            # 极端兜底：spell 系统异常时至少不丢失打开动作
            _log.warning(f"[open_file] spell 异常，兜底直接打开：{e}")
            _real_open_file(file_path, 'file')

    def open_folder(self, folder_path):
        # 打开文件夹（先 spell 再真实打开）
        # 检查是否是回收站：不走 spell 流程（立即反应）
        if 'recycle' in folder_path.lower() or '回收站' in folder_path:
            self.react_to_recycle_bin()
            return
        if not folder_path or not os.path.exists(folder_path):
            self.dialogue_ui.show_dialogue("找不到那个文件夹呀...")
            return
        # 真实打开动作
        def _real_open_folder(path, kind):
            self.desktop_interaction.open_folder(path)
            folder_name = os.path.basename(path)
            self.dialogue_ui.show_dialogue(f"我帮你打开了{folder_name}文件夹~")
        try:
            self._start_open_with_spell(folder_path, 'folder', _real_open_folder)
        except Exception as e:
            _log.warning(f"[open_folder] spell 异常，兜底直接打开：{e}")
            _real_open_folder(folder_path, 'folder')
        
    def handle_window_operation(self, user_input):
        """处理窗口操作指令（关闭/最小化/最大化 XX 窗口）。
        修复：dialogue_ui 的窗口管理分支此前引用本方法但不存在（hasattr 兜底成
        一句"只能后台操作"的假话），窗口管理指令从未真正生效。"""
        import re as _re
        low = user_input.lower()
        action = None
        if any(k in low for k in ["关闭", "关掉"]):
            action = 'close'
        elif "最小化" in low:
            action = 'minimize'
        elif any(k in low for k in ["最大化", "放大"]):
            action = 'maximize'
        if action is None:
            return False
        # 提取窗口名（动词及"窗口"前缀之后的内容）
        name_part = _re.sub(r'^(请|帮我)?(关闭|关掉|最小化|最大化|放大)\s*(窗口)?\s*', '', user_input)
        name_part = _re.sub(r'[呢？。！!~～\s]+$', '', name_part).strip()
        try:
            windows = self.desktop_interaction.get_all_visible_windows()
        except Exception:
            windows = []
        target = None
        if name_part:
            nl = name_part.lower()
            for wd in windows:
                t = wd.get('title', '') or ''
                if t and (nl in t.lower() or t.lower() in nl):
                    target = wd
                    break
        elif windows:
            target = windows[0]  # 未指定名字：默认最上层窗口
        if target is None:
            self.dialogue_ui.add_dialogue(
                "ralsei", f"我没找到叫「{name_part or '目标'}」的窗口呢。", "a little confusion and cute")
            self.dialogue_ui.show_dialogue()
            return True
        hwnd = target['hwnd']
        title = target.get('title', '') or '这个窗口'
        d = self.desktop_interaction
        try:
            if action == 'close':
                d.close_window_by_hwnd(hwnd)
                msg = f"帮你关掉「{title}」啦~"
            elif action == 'minimize':
                d.minimize_window_by_hwnd(hwnd)
                msg = f"把「{title}」最小化啦~"
            else:
                d.maximize_window_by_hwnd(hwnd)
                msg = f"把「{title}」最大化啦~"
        except Exception as e:
            _log.warning(f"窗口操作失败: {e}")
            msg = "呜... 窗口操作失败了。"
        self.dialogue_ui.add_dialogue("ralsei", msg, "happy")
        self.dialogue_ui.show_dialogue()
        return True

    def check_recycle_bin(self):
        # 检查是否接近回收站
        desktop_dir = self.desktop_interaction.desktop_path
        recycle_bin_path = os.path.join(desktop_dir, '回收站')
        if not os.path.exists(recycle_bin_path):
            recycle_bin_path = os.path.join(desktop_dir, '$Recycle.Bin')
        
        if os.path.exists(recycle_bin_path):
            # 获取回收站位置（简化版，实际需要获取桌面图标位置）
            # 这里使用模拟位置，实际实现中可以通过Windows API获取真实位置
            recycle_bin_pos = QPoint(100, 100)  # 模拟位置
            ralsei_pos = self.pos()
            
            # 计算距离
            dx = recycle_bin_pos.x() - ralsei_pos.x()
            dy = recycle_bin_pos.y() - ralsei_pos.y()
            distance = math.hypot(dx, dy)
            
            # 如果距离小于一定值，触发恐惧反应
            if distance < 200:
                self.react_to_recycle_bin()
                return True
        
        # 检查窗口标题是否包含回收站
        windows = self.desktop_interaction.get_all_visible_windows()
        for window in windows:
            if 'recycle' in window['title'].lower() or '回收站' in window['title']:
                self.react_to_recycle_bin()
                return True
        
        return False
        
    def react_to_recycle_bin(self):
        # 对回收站的恐惧反应
        self.dialogue_ui.show_dialogue("啊！不要靠近回收站！我对那里感到很害怕...")
        self.emotion_system.react_to_event("saw_recycle_bin", {})
        
        # 改变表情为恐惧
        self.dialogue_ui.set_face("scared")
        
        # 增加恐惧和悲伤感
        self.emotions["fear"] += 35
        self.emotions["sadness"] += 15
        self.emotions["happiness"] -= 20
        
        # 远离回收站
        self._move_away_from_recycle_bin()
        
        # 一段时间后恢复
        QTimer.singleShot(4000, self._recover_from_fear)
        
    def _move_away_from_recycle_bin(self):
        # 远离回收站
        # 这里使用简单的远离逻辑，实际可以更复杂
        screen_geom = QApplication.desktop().availableGeometry()
        # 移动到屏幕的另一端
        new_x = random.randint(screen_geom.width() // 2, screen_geom.width() - self.width())
        new_y = random.randint(screen_geom.height() // 2, screen_geom.height() - self.height())
        
        self.target_pos = QPoint(new_x, new_y)
        self.is_moving = True
        self.current_activity = "running"
        
    def _recover_from_fear(self):
        # 从恐惧中恢复
        self.dialogue_ui.set_face("normal")
        self.dialogue_ui.show_dialogue("呼...好可怕啊，我们离那里远一点吧...")
        self.emotions["fear"] -= 20
        self.emotions["happiness"] += 10
        
    def delete_file(self, file_path):
        # 删除文件，需要确认
        # 修复：原来只说一句"你确定吗"就直接删除（无真实确认），且不检查路径。
        # 需求明确要求删除操作需要找用户确认。这里用模态确认框；取消则不删。
        if not file_path or not os.path.exists(file_path):
            self.dialogue_ui.show_dialogue("那个文件好像不存在呀...")
            return False
        file_name = os.path.basename(file_path)
        try:
            from PyQt5.QtWidgets import QMessageBox
            ret = QMessageBox.question(
                self, "删除确认",
                f"要删掉「{file_name}」吗？删掉就找不回来啦！",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ret != QMessageBox.Yes:
                self.dialogue_ui.show_dialogue("太好了！还好没删掉~")
                return False
        except Exception:
            # 确认框异常时保守处理：不删除
            return False
        if self.desktop_interaction.delete_file(file_path):
            self.dialogue_ui.show_dialogue(f"{file_name}已经被删除了...")
            self.emotion_system.react_to_event("file_deleted", {'file_name': file_name})
            return True
        return False
    def rename_file(self, file_path, new_name):
        # 重命名文件
        if self.desktop_interaction.rename_file(file_path, new_name):
            self.dialogue_ui.show_dialogue(f"我帮你把文件重命名为{new_name}啦~")
        
    def check_dragged_file(self):
        # 检查是否有文件被拖拽
        # 这里可以添加检测拖拽文件的逻辑
        pass

    def _virtual_screen_rect(self):
        """多屏虚拟桌面矩形（含左侧负坐标副屏）。

        参考小鲸鱼 widget 的"始终夹在可视区"思路：所有自主移动的屏幕夹取都用它，
        而不是主屏 availableGeometry——否则右侧副屏目标走不到（每帧被拉回主屏）、
        左侧负坐标副屏区域完全不可达。
        返回 QRect；win32 API 失败时回退主屏 availableGeometry。
        """
        try:
            import win32api
            from PyQt5.QtCore import QRect as _Qr
            vx = win32api.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
            vy = win32api.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
            vw = win32api.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
            vh = win32api.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
            if vw > 0 and vh > 0:
                return _Qr(vx, vy, vw, vh)
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        sg = QApplication.desktop().availableGeometry()
        return QRect(sg.x(), sg.y(), sg.width(), sg.height())

    def cleanup_on_exit(self):
        """程序退出时的清理工作，根据隐私设置清理用户数据"""
        _log.debug("正在执行退出清理工作...")

        # 1. 停止所有定时器，防止退出后回调触发已销毁对象
        for timer_attr in ('animation_timer', 'ai_timer', 'stats_timer',
                           'dialogue_init_timer', 'weather_timer',
                           'auto_mouse_drag_timer', 'api_control_timer',
                           'placeholder_timer', 'movement_timer',
                           'mouse_drag_timer', 'video_watching_timer',
                           '_bounce_timer', '_hide_search_timer'):
            try:
                t = getattr(self, timer_attr, None)
                if t is not None:
                    t.stop()
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)

        # 2. 停止后台线程
        try:
            if hasattr(self, 'ai_thread') and self.ai_thread is not None:
                self.ai_thread_running = False
                self.ai_thread.join(timeout=2)
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)

        # 2.5 隐藏托盘图标（若有）
        try:
            if getattr(self, '_tray', None) is not None:
                self._tray.hide()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)

        # 2.6 躲猫猫残留的"障碍物N"文件夹清理（游戏中途退出会在桌面留下垃圾文件夹）
        try:
            for p in list(getattr(self, '_hide_obstacles', []) or []):
                try:
                    import shutil
                    if os.path.isdir(p):
                        shutil.rmtree(p, ignore_errors=True)
                        _log.debug(f"已清理躲猫猫残留文件夹: {p}")
                except Exception as e:  # 修复：原先静默吞噬
                    _log.debug("main 防御性异常（已忽略）: %s", e)
            self._hide_obstacles = []
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)

        # 3. 检查是否需要在退出时清理数据
        privacy_config = self.config_manager.get_privacy_config()
        if privacy_config.get("clear_data_on_exit", False):
            _log.debug("根据隐私设置，正在清理用户数据...")

            # 清理记忆数据
            try:
                import os
                memory_file = os.path.join(os.path.dirname(__file__), '..', 'memory.json')
                if os.path.exists(memory_file):
                    os.remove(memory_file)
                    _log.debug("记忆数据已清理")
            except Exception as e:
                _log.debug(f"清理记忆数据时出错: {e}")

            # 清理成长数据
            try:
                growth_file = os.path.join(os.path.dirname(__file__), '..', 'growth_data.json')
                if os.path.exists(growth_file):
                    os.remove(growth_file)
                    _log.debug("成长数据已清理")
            except Exception as e:
                _log.debug(f"清理成长数据时出错: {e}")

            # 清理娱乐数据
            try:
                entertainment_file = os.path.join(os.path.dirname(__file__), '..', 'entertainment_data.json')
                if os.path.exists(entertainment_file):
                    os.remove(entertainment_file)
                    _log.debug("娱乐数据已清理")
            except Exception as e:
                _log.debug(f"清理娱乐数据时出错: {e}")

        _log.debug("退出清理工作完成！")

    # ==============================================================
    # 施法流程 Spell Flow：文件/文件夹操作必须先走完 走过去+施法11帧 的仪式
    # ==============================================================

    def _resolve_target_screen_anchor(self, path):
        """给定文件/文件夹绝对路径，估算它在屏幕上的锚点坐标。
        优先用 desktop_elements 里缓存的真实图标位置；找不到再用真实桌面分块估计。"""
        # 1) 在桌面元素缓存里找真实图标位置（含 x/y/width/height）
        #    修复：原代码调用不存在的 get_item_position（AttributeError 被吞），
        #    fallback 又因桌面路径错误/找不到 path 时用 abs(hash(path)) 生成随机坐标，
        #    导致 Ralsei"打开东西时"走到随机位置（看起来像瞬移/乱走）。
        try:
            for el in self.desktop_interaction.desktop_elements:
                if el.get('path') == path:
                    return (int(el['x'] + el.get('width', 80) / 2),
                            int(el['y'] + el.get('height', 80) / 2))
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        # 2) fallback：按路径在真实桌面目录列表里的索引分块估算（找不到就取第一个，
        #    不再用随机 hash 产生不稳定坐标）
        try:
            desktop_dir = self.desktop_interaction.desktop_path
            entries = []
            for name in sorted(os.listdir(desktop_dir)):
                full = os.path.join(desktop_dir, name)
                if os.path.isfile(full) or os.path.isdir(full):
                    entries.append(full)
            if not entries:
                raise RuntimeError('empty desktop')
            idx = entries.index(path) if path in entries else 0
            screen = QApplication.desktop().availableGeometry()
            cols = 8
            rows = 6
            col = idx % cols
            row = (idx // cols) % rows
            cell_w = screen.width() / cols
            cell_h = screen.height() / rows
            cx = int(col * cell_w + cell_w / 2)
            cy = int(row * cell_h + cell_h / 2)
            return (cx, cy)
        except Exception:
            screen = QApplication.desktop().availableGeometry()
            return (int(screen.width() / 2), int(screen.height() / 2))

    def _spell_interrupted_reason(self):
        """检查当前施法流程是否应该中断。返回 str 原因或 None 表示未中断。"""
        if self._spell_stage is None:
            return None
        # 拖拽：立即中断
        if getattr(self, '_is_being_dragged', False):
            return 'drag_started'
        # 用户触摸 / 鼠标按下
        if getattr(self, '_spell_touched_flag', False):
            return 'user_touched'
        # 跳跃 / 掉落：物理过程覆盖所有动画
        if getattr(self, 'is_jumping', False) or getattr(self, 'is_falling', False):
            return 'physics_started'
        # casting 阶段：动画必须是 spell / spell_left，否则视为被打断
        if self._spell_stage == 'casting' and self._spell_target_direction:
            expected_anim = 'spell_left' if self._spell_target_direction == 'left' else 'spell'
            if self.current_animation != expected_anim:
                # 修复：动画被切走（被 walk/idle/其他动画覆盖）即中断，不再看方向。
                # 原逻辑在"动画不对但方向匹配"时既不中断也不修复，
                # 导致 frames_seen 永不增长、施法流程永久卡死（文件夹永不打开）。
                return 'anim_mismatch'
            if self.current_direction != self._spell_target_direction:
                # 动画正确但方向字段不一致：同步方向，不做中断判定
                self.previous_direction = self.current_direction
                self.current_direction = self._spell_target_direction
        return None

    def _tick_spell_flow(self):
        """每帧执行：推进 spell 流程 walking/casting 状态机。
        只有 _spell_stage != None 时才真正干活。"""
        if self._spell_stage is None:
            return

        # 1. 统一打断检测
        r = self._spell_interrupted_reason()
        if r is not None:
            # ===== 修复：单个 spell 中断 不直接 abort 整个躲猫猫游戏 =====
            # 躲猫猫的 _abort_hide_and_seek 只在：game 主动结束（end_hide_and_seek）/ 超时 / 玩家点退出 时调用
            # 这里只清理 spell 状态，让上层决定是否继续推进游戏或重试
            _log.debug(f"[SPELL] 流程中断 reason={r} stage={self._spell_stage}，仅清理 spell 状态")
            # walking/casting 都清理 spell 状态
            self._spell_stage = None
            self._spell_target_direction = None
            self._spell_finish_cb = None
            self._spell_target_path = None
            self._spell_target_kind = None
            self._spell_target_screen_pos = None
            self._spell_cast_start_frame = None
            self._spell_frames_seen = 0
            self._spell_seen_frame = -1
            self._spell_touched_flag = False
            # ===== 修复：躲猫猫进行中的 spell 被打断 → 兜底结束游戏，避免永久卡死 =====
            # 原逻辑只清 spell 状态，_hide_stage 卡在中间阶段：无法重开、超时定时器未启动、
            # _abort_hide_and_seek 全项目仅一处调用 → 游戏永远结束不了。这里统一兜底。
            hs = getattr(self, '_hide_stage', None)
            if hs is not None:
                _log.debug(f"[SPELL] 躲猫猫阶段 {hs} 的施法被打断，兜底结束躲猫猫")
                self._abort_hide_and_seek(reason='spell_interrupted')
            else:
                # 躲猫猫销毁阶段（_hide_end_game 已清 _hide_stage，但障碍物还没删）被打断 →
                # 清理残留障碍物，避免桌面上永久残留"障碍物N"文件夹
                obstacles = getattr(self, '_hide_obstacles', []) or []
                if obstacles:
                    _log.debug("[SPELL] 躲猫猫销毁施法被打断，清理残留障碍物")
                    import shutil
                    for p in obstacles:
                        try:
                            if os.path.isdir(p):
                                shutil.rmtree(p, ignore_errors=True)
                        except Exception as e:  # 修复：原先静默吞噬
                            _log.debug("main 防御性异常（已忽略）: %s", e)
                    self._hide_obstacles = []
                    self._hide_folder_path = None
                # 恢复自主代理（非躲猫猫 spell 被打断时，之前 suspend 的 agent 必须恢复，
                # 否则自主代理永久挂起）
                if getattr(self, '_spell_auto_suspended', False):
                    try:
                        self.autonomous_agent.resume()
                    except Exception as e:  # 修复：原先静默吞噬
                        _log.debug("main 防御性异常（已忽略）: %s", e)
                    self._spell_auto_suspended = False
            return

        now = time.time()

        # 2. walking 阶段：向目标点移动（dist<35 → 转 casting）
        if self._spell_stage == 'walking':
            me = self.frameGeometry().center()
            tx, ty = self._spell_target_screen_pos
            dx = tx - me.x()
            dy = ty - me.y()
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < 35:
                # —— 足够近：立刻切换到 casting 阶段 ——
                direction = self._spell_target_direction
                if direction is None:
                    direction = 'right' if (self.current_direction != 'left') else 'left'
                spell_anim = 'spell_left' if direction == 'left' else 'spell'
                self._spell_stage = 'casting'
                # 修复：进入施法时必须停稳——否则 is_moving 残留 True 时
                # update_movement 继续驱动移动，施法过程中漂移/抖动（抽搐感）。
                self.is_moving = False
                self.current_speed_x = 0
                self.current_speed_y = 0
                # 施法音效
                try:
                    self.sound_manager.play_spell()
                except Exception as e:  # 修复：原先静默吞噬
                    _log.debug("main 防御性异常（已忽略）: %s", e)
                self._spell_target_direction = direction
                self.previous_direction = self.current_direction
                self.current_direction = direction
                if self.change_animation(spell_anim, force=True):
                    self.current_frame = 0
                self._spell_cast_start_frame = 0
                self._spell_frames_seen = 0
                self._spell_seen_frame = -1  # 修复：重置帧去重标记，避免残留值吞掉首帧计数
                # 暂停自主代理（避免它的 look_up / act 覆盖 spell 动画；躲猫猫结束后恢复）
                try:
                    self.autonomous_agent.suspend()
                    self._spell_auto_suspended = True
                except Exception as e:  # 修复：原先静默吞噬
                    _log.debug("main 防御性异常（已忽略）: %s", e)
            else:
                # 每帧向目标移动一小步：用主移动系统，确保走的是 walk 动画
                target = QPoint(int(tx - self.width() / 2), int(ty - self.height() / 2))
                if getattr(self, 'target_pos', None) != target:
                    self.target_pos = target
                    self.is_moving = True
                    self.speed = 6.0
                    # 按方向切 walk_<dir>
                    if abs(dx) > abs(dy):
                        new_dir = 'right' if dx > 0 else 'left'
                    else:
                        new_dir = 'down' if dy > 0 else 'up'
                    # 修复：只在方向确实变化时才 force 切换动画（避免每帧强制切换造成抽搐）。
                    # force=True 保证冷却期内也能切到目标方向（非 force 时会被冷却拒绝）。
                    if self.current_direction != new_dir:
                        self.current_direction = new_dir
                        self.change_animation(f"walk_{new_dir}", force=True)

        # 3. casting 阶段：数 spell/spell_left 帧直到 11 帧播完 → cb
        elif self._spell_stage == 'casting':
            expected = 11
            anim = self.current_animation
            frames = self.sprite_loader.sprites.get(anim, [])
            cur_f = self.current_frame
            # 记录 casting 开始时间（用于时间超时 fallback）
            if not hasattr(self, '_spell_cast_start_time') or self._spell_cast_start_time is None:
                self._spell_cast_start_time = current_time
            if (anim in ('spell', 'spell_left')) and len(frames) >= 2:
                # 看到了真实帧：累积 _spell_frames_seen（同一帧重复见不算）
                if getattr(self, '_spell_seen_frame', -1) != cur_f:
                    self._spell_frames_seen = getattr(self, '_spell_frames_seen', 0) + 1
                    self._spell_seen_frame = cur_f
            # 心跳 log 4 次（防止完全不可见）
            frames_seen = getattr(self, '_spell_frames_seen', 0)
            cond_ideal = (frames_seen >= expected) and (anim in ('spell', 'spell_left')) and (len(frames) >= 2)
            # 修复：此前 timeout fallback 仅依赖 frames_seen>=22，若 spell 动画帧数<2
            # （frames_seen 永远为 0）则永久卡住。新增：帧数不足直接完成 + 5秒时间超时。
            cond_frames_insufficient = (anim in ('spell', 'spell_left')) and (len(frames) < 2)
            cond_time_fallback = (current_time - getattr(self, '_spell_cast_start_time', current_time)) > 5.0
            cond_timeout_fallback = (not cond_ideal) and (frames_seen >= expected * 2 or cond_time_fallback)
            if cond_ideal or cond_timeout_fallback:
                cb = self._spell_finish_cb
                path = self._spell_target_path
                kind = self._spell_target_kind
                # —— 关键！保存回调前的动画名，避免回调里启动新 spell 时，
                #    后面 finally 把新 spell_left 当作旧 spell 清理掉切 idle。
                _anim_before_cb = self.current_animation
                # 先清理 spell 状态，再回调（避免回调认为"仍在施法"）
                self._spell_stage = None
                self._spell_target_kind = None
                self._spell_target_path = None
                self._spell_target_screen_pos = None
                self._spell_target_direction = None
                self._spell_cast_start_frame = None
                self._spell_cast_start_time = None
                self._spell_finish_cb = None
                self._spell_touched_flag = False
                self._spell_seen_frame = -1
                # 自主代理恢复（仅当 spell 是一次性（非躲猫猫）的情况才恢复；
                # 躲猫猫整体结束再恢复）
                if getattr(self, '_spell_auto_suspended', False) and getattr(self, '_hide_stage', None) is None:
                    try:
                        self.autonomous_agent.resume()
                    except Exception as e:  # 修复：原先静默吞噬
                        _log.debug("main 防御性异常（已忽略）: %s", e)
                    self._spell_auto_suspended = False
                elif getattr(self, '_spell_auto_suspended', False):
                    self._spell_auto_suspended = False
                try:
                    if callable(cb):
                        cb(path, kind)
                finally:
                    # 只有 回调没再次启动 spell，且当前动画还停留在 callback 前的 spell/spell_left，才切回 idle
                    if (self._spell_stage is None
                            and _anim_before_cb in ('spell', 'spell_left')
                            and self.current_animation == _anim_before_cb):
                        self.change_animation('idle', force=True)

    def _cast_spell_then(self, cb, direction=None):
        """**纯施法**：不走 walking 阶段，直接播 spell / spell_left。
        用于躲猫猫"创建文件夹"/"躲藏"两个仪式动作。cb：(path, kind) -> None"""
        # 1) 清理旧 spell 状态（只清 spell，不 abort 整个躲猫猫游戏）
        # 多次调用 _cast_spell_then 是躲猫猫的正常流程推进（creating→hiding_spell），
        # 不能调用 _abort_hide_and_seek 否则直接杀掉整个游戏
        self._spell_stage = None
        self._spell_finish_cb = cb
        self._spell_target_path = None
        self._spell_target_kind = '__cast_only__'
        self._spell_frames_seen = 0
        self._spell_seen_frame = -1

        # 2) 确定朝向（spell_left / spell）
        if direction is None:
            direction = 'right' if self.current_direction != 'left' else 'left'
        spell_anim = 'spell_left' if direction == 'left' else 'spell'

        # 3) 登记为 casting 阶段
        self._spell_stage = 'casting'
        # 施法音效
        try:
            self.sound_manager.play_spell()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        self._spell_target_direction = direction
        self.previous_direction = self.current_direction
        self.current_direction = direction
        ok = self.change_animation(spell_anim, force=True)
        if ok:
            self.current_frame = 0
        else:
            # 兜底：直接强制设置 + 清零帧
            self.current_animation = spell_anim
            self.current_frame = 0
            self.current_priority = 5
            self.last_animation_change = time.time()
        self._spell_cast_start_frame = 0
        # 暂停自主代理（如果有的话）
        try:
            self.autonomous_agent.suspend()
            self._spell_auto_suspended = True
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)

    def _start_open_with_spell(self, path, kind, cb):
        """打开文件/文件夹的入口：
        1) walking 阶段：Ralsei 走过去（靠近 path 的屏幕坐标）
        2) casting 阶段：施法 11 帧
        3) 调用 cb(path, kind) 真实打开文件"""
        # 清理旧 spell（只清 spell，不 abort 躲猫猫游戏——躲猫猫 searching 阶段找到文件时
        # 本来就是 open_with_spell，不能反过来 abort 游戏）
        self._spell_stage = None

        # 1) 目标屏幕坐标 + 朝向
        (tx, ty) = self._resolve_target_screen_anchor(path)
        me = self.frameGeometry().center()
        dx = tx - me.x()
        dy = ty - me.y()
        if abs(dx) > abs(dy):
            direction = 'right' if dx > 0 else 'left'
        else:
            direction = 'down' if dy > 0 else 'up'
        spell_anim = 'spell_left' if direction == 'left' else 'spell'

        # 2) 登记 walking 阶段
        self._spell_stage = 'walking'
        self._spell_target_kind = kind
        self._spell_target_path = path
        self._spell_target_screen_pos = (tx, ty)
        self._spell_target_direction = direction
        self._spell_finish_cb = cb
        self._spell_frames_seen = 0
        self._spell_seen_frame = -1

        # 3) 如果已经足够近（<35px），下一次 _tick_spell_flow 会立刻转 casting
        #    暂停自主代理（避免干扰）
        try:
            self.autonomous_agent.suspend()
            self._spell_auto_suspended = True
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)

    # ==============================================================
    # 躲猫猫游戏 Hide and Seek
    # 流程：start → 走到屏幕中央 → [spell] 创建 5 个障碍物文件夹（上 3 下 2）
    #       → [spell] 做躲藏仪式 → 移动到选中的文件夹前 → 打开文件夹 →
    #       → searching 阶段（用户点击正确文件夹 = 玩家赢，超时 = Ralsei 赢）
    #       → 结束：清理 5 个障碍物文件夹
    # ==============================================================

    def start_hide_and_seek_game(self):
        # 入口：检查重复启动、暂停自主代理、移动到屏幕中央
        # 修复：返回 True 表示成功开始，False 表示已有游戏在玩（供调用方决定话术）
        if getattr(self, 'game_state', {}).get('is_playing'):
            return False
        if getattr(self, '_hide_stage', None) is not None:
            return False
        # 暂停自主代理
        try:
            self.autonomous_agent.suspend()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        self.game_state['is_playing'] = True
        self.game_state['game_type'] = 'hide_and_seek'

        # 计算屏幕中央
        screen = QApplication.desktop().availableGeometry()
        cx = int(screen.width() / 2)
        cy = int(screen.height() / 2)
        self._hide_center_x = cx
        self._hide_center_y = cy

        # 1) 走到屏幕正中央（自然走路：is_moving + target_pos 主系统）
        self._hide_stage = 'moving_to_center'
        self.dialogue_ui.add_dialogue("ralsei", "好~ 我先准备 5 个藏身的地方，然后藏起来，你来找我好不好？", "excited")
        self.dialogue_ui.show_dialogue()
        self._hide_move_to_point(cx, cy, self._hide_on_arrive_center, 'moving_to_center')
        return True

    def _abort_hide_and_seek(self, reason='generic'):
        """躲猫猫任一阶段被中断时调用。
        若有真实游戏在进行，则清理障碍并退出；否则只打印一声。"""
        hs = getattr(self, '_hide_stage', None)
        if hs is None and not getattr(self, 'game_state', {}).get('is_playing'):
            return
        real_interrupt = (hs is not None)
        # 清理游戏状态
        self._hide_stage = None
        self.game_state['is_playing'] = False
        self.game_state['game_type'] = None
        # searching 定时器停掉
        try:
            if getattr(self, '_hide_search_timer', None) is not None:
                self._hide_search_timer.stop()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        self._hide_search_timer = None
        # 清理障碍物（如果有创建记录）
        obstacles = getattr(self, '_hide_obstacles', []) or []
        for p in obstacles:
            try:
                if os.path.isdir(p):
                    import shutil
                    shutil.rmtree(p, ignore_errors=True)
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
        self._hide_obstacles = []
        self._hide_folder_path = None
        # 恢复自主代理
        try:
            self.autonomous_agent.resume()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        if real_interrupt and reason not in ('end_hide_and_seek', 'cast_spell_then_replaced'):
            self.dialogue_ui.add_dialogue("ralsei", "呜…游戏被打断啦！下次再玩吧~", "sad")
            self.dialogue_ui.show_dialogue()

    def _hide_move_to_point(self, x, y, cb, stage_name):
        """封装：把宠物窗口中心移到 (x, y)，到达时调用 cb()。
        使用主系统 is_moving + target_pos，保证自然走+walk动画。"""
        # 目标坐标（窗口左上角）
        tx = int(x - self.width() / 2)
        ty = int(y - self.height() / 2)
        self.target_pos = QPoint(tx, ty)
        self.is_moving = True
        self.speed = 6.0
        self.moving_duration = 0
        # 注册到达回调（在 _notify_arrived_if_needed 里触发）
        self._hide_moving_cb = cb
        self._hide_moving_cb_stage = stage_name
        # 手动设一次方向，保证立刻走起来
        me = self.frameGeometry().center()
        dx = x - me.x()
        dy = y - me.y()
        if abs(dx) > abs(dy):
            new_dir = 'right' if dx > 0 else 'left'
        else:
            new_dir = 'down' if dy > 0 else 'up'
        self.change_animation(f"walk_{new_dir}", force=True)

    def _hide_on_arrive_center(self):
        if getattr(self, '_hide_stage', None) != 'moving_to_center':
            return
        self._hide_stage = 'creating'
        self.dialogue_ui.add_dialogue("ralsei", "魔法~ 变出 5 个小盒子！✨", "excited")
        self.dialogue_ui.show_dialogue()
        # [spell right] → 完成后回调 _hide_create_obstacles_after_spell
        self._cast_spell_then(self._hide_create_obstacles_after_spell, direction='right')

    def _hide_create_obstacles_after_spell(self, path=None, kind=None):
        if getattr(self, '_hide_stage', None) != 'creating':
            return
        # —— 固定布局：上 3 下 2 ——
        # 上 3：屏幕中心 X 轴 -120 / 0 / +120，Y = 中心 Y - 180
        # 下 2：屏幕中心 X 轴 -60 / +60，Y = 中心 Y + 180
        # 修复：用真实桌面路径（OneDrive 桌面重定向时 USERPROFILE\Desktop 不是用户看到的桌面，
        # 障碍物会创建到看不见的目录 → "躲猫猫根本没生成障碍物"）
        desktop_dir = self.desktop_interaction.desktop_path
        screen = QApplication.desktop().availableGeometry()
        cx = screen.center().x()
        cy = screen.center().y()
        positions = [
            ('top_left',     cx - 120, cy - 180),
            ('top_center',   cx,       cy - 180),
            ('top_right',    cx + 120, cy - 180),
            ('bottom_left',  cx - 60,  cy + 180),
            ('bottom_right', cx + 60,  cy + 180),
        ]
        created = []
        base_names = ['障碍物1', '障碍物2', '障碍物3', '障碍物4', '障碍物5']
        import random
        random.shuffle(positions)
        for i, (tag, px, py) in enumerate(positions):
            folder_path = os.path.join(desktop_dir, base_names[i])
            # 如果存在就加后缀避免冲突
            suffix = 2
            while os.path.exists(folder_path):
                folder_path = os.path.join(desktop_dir, f"{base_names[i]}_{suffix}")
                suffix += 1
            try:
                os.makedirs(folder_path, exist_ok=True)
                created.append(folder_path)
            except Exception as e:
                # 修复：创建失败不再完全静默（否则 len(created)<3 时游戏莫名提前结束，
                # 且原因不可见）。打印失败原因便于排查（如权限/路径问题）。
                _log.warning(f"[躲猫猫] 障碍物创建失败: {folder_path} -> {type(e).__name__}: {e}")
        self._hide_obstacles = created
        if len(created) < 3:
            # 极端失败：结束游戏
            self.dialogue_ui.add_dialogue("ralsei", "呜…怎么变不出来呢…下次再玩吧。", "sad")
            self.dialogue_ui.show_dialogue()
            self._abort_hide_and_seek(reason='end_hide_and_seek')
            return

        # 在 5 个里选 1 个当藏身点
        chosen = random.choice(created)
        self._hide_folder_path = chosen

        # —— 躲藏仪式：[spell left] ——
        self._hide_stage = 'hiding_spell'
        self.dialogue_ui.add_dialogue("ralsei", "我要开始藏啦~ 不许偷看哦！", "happy")
        self.dialogue_ui.show_dialogue()
        self._cast_spell_then(self._hide_after_hiding_spell, direction='left')

    def _hide_after_hiding_spell(self, path=None, kind=None):
        if getattr(self, '_hide_stage', None) != 'hiding_spell':
            return
        self._hide_stage = 'moving_to_folder'
        # 计算藏身处 folder 在桌面的坐标（desktop_interaction 查不到就用我们创建时记录的位置）
        folder_path = self._hide_folder_path
        (fx, fy) = self._resolve_target_screen_anchor(folder_path)
        # 再往 folder 下方走一步，站在文件夹前
        fy2 = fy + 80
        screen = QApplication.desktop().availableGeometry()
        fy2 = min(fy2, screen.height() - self.height() // 2 - 10)
        self._hide_move_to_point(fx, fy2, self._hide_on_arrive_folder, 'moving_to_folder')

    def _hide_on_arrive_folder(self):
        if getattr(self, '_hide_stage', None) != 'moving_to_folder':
            return
        # 到达藏身文件夹前 → 躲藏：Ralsei 在桌面上消失（隐藏窗口）
        folder_path = self._hide_folder_path
        # 不自动打开文件夹，等用户自己打开
        self.hide()  # 桌面上消失
        # 进入 searching 阶段
        self._hide_stage = 'searching'
        self.dialogue_ui.add_dialogue("ralsei", "藏好啦~ 快点点桌面上的文件夹来找我吧！（20 秒内找不到算我赢哦）", "excited")
        self.dialogue_ui.show_dialogue()
        # searching 阶段最多 20 秒；每 3 秒打开一个错误文件夹"表演找我"
        self._hide_search_started_at = time.time()
        self._hide_search_checked = set()
        try:
            if getattr(self, '_hide_search_timer', None) is None:
                from PyQt5.QtCore import QTimer
                self._hide_search_timer = QTimer(self)
                self._hide_search_timer.timeout.connect(self._hide_search_tick)
            self._hide_search_timer.start(3000)
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)

    def _hide_search_tick(self):
        if getattr(self, '_hide_stage', None) != 'searching':
            return
        # 20 秒总超时 = Ralsei 赢
        if time.time() - getattr(self, '_hide_search_started_at', 0) > 20:
            self.dialogue_ui.add_dialogue("ralsei", "啦啦啦~ 时间到！你找不到我！我赢啦~ 嘻嘻！", "happy")
            self.dialogue_ui.show_dialogue()
            self._hide_end_game(user_won=False)
            return
        # ===== 修复：检测玩家是否点开了某个障碍物文件夹（"玩家点击获胜"接线）=====
        # 此前 _hide_report_clicked_folder 没有任何调用点，玩家永远无法通过点击文件夹获胜。
        # 这里通过窗口标题匹配 5 个障碍物文件夹名来识别"玩家打开了哪个文件夹"。
        try:
            windows = self.desktop_interaction.get_all_visible_windows()
            for p in getattr(self, '_hide_obstacles', []):
                name = os.path.basename(p)
                for w in windows:
                    title = w.get('title', '') or ''
                    if name and name in title:
                        self._hide_report_clicked_folder(p)
                        return
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        # 每隔 3 秒打开一个"错误的文件夹"（表演找不到）
        unchecked = [p for p in getattr(self, '_hide_obstacles', [])
                     if p != self._hide_folder_path and p not in getattr(self, '_hide_search_checked', set())]
        if unchecked:
            import random
            pick = random.choice(unchecked)
            self._hide_search_checked.add(pick)
            try:
                os.startfile(pick)
            except Exception:
                try:
                    self.desktop_interaction.open_folder(pick)
                except Exception as e:  # 修复：原先静默吞噬
                    _log.debug("main 防御性异常（已忽略）: %s", e)
            self.dialogue_ui.add_dialogue("ralsei", "你点的这个…我不在这儿呀~", "happy")
            self.dialogue_ui.show_dialogue()

    def _hide_end_game(self, user_won):
        hs = getattr(self, '_hide_stage', None)
        self._hide_stage = None
        self.game_state['is_playing'] = False
        self.game_state['game_type'] = None
        # 确保 Ralsei 可见
        self.show()
        # 关 searching 定时器
        try:
            if getattr(self, '_hide_search_timer', None) is not None:
                self._hide_search_timer.stop()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        self._hide_search_timer = None
        # 先把藏身处显示对话（文件夹还没删），让用户知道结果
        if user_won:
            self.change_animation('surprised', force=True)
            self.dialogue_ui.add_dialogue("ralsei", "哎？！被你发现了…真厉害呀~  你赢啦！", "surprised")
            self.dialogue_ui.show_dialogue()
        else:
            self.change_animation('laugh', force=True)
            self.show()  # Ralsei 输了也要重新出现
        # —— 销毁文件夹前播放 spell 动画（spr_ralsei_spell_0~10）——
        self._cast_spell_then(self._hide_destroy_obstacles, direction='right')

    def _hide_destroy_obstacles(self, path=None, kind=None):
        """spell 动画播放完后，真正删除桌面上所有 5 个障碍物文件夹。"""
        obstacles = list(getattr(self, '_hide_obstacles', []) or [])
        import shutil
        for p in obstacles:
            try:
                if os.path.isdir(p):
                    # 先尝试回收；删不掉就彻底删
                    try:
                        import winshell
                        winshell.delete_file(p, no_confirm=True, allow_undo=True)
                    except Exception:
                        shutil.rmtree(p, ignore_errors=True)
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
        self._hide_obstacles = []
        self._hide_folder_path = None
        # 恢复自主代理
        try:
            self.autonomous_agent.resume()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        self._spell_auto_suspended = False
        # 切回 idle
        self.change_animation('idle', force=True)

    def _hide_report_clicked_folder(self, folder_path):
        """searching 阶段：用户点了桌面上某个文件夹就调用它。
        点对了 = 玩家赢：Ralsei 出现在文件夹窗口，说"你找到我了"，然后跳回桌面；
        点错了 = 对话 + 继续。"""
        if getattr(self, '_hide_stage', None) != 'searching':
            return
        if not folder_path or not os.path.isdir(folder_path):
            return
        # 必须是我们创建的 5 个障碍物之一
        if folder_path not in getattr(self, '_hide_obstacles', []):
            return
        if folder_path == self._hide_folder_path:
            # —— 玩家赢 ——
            # 修复：先把 searching 阶段的定时器停掉并离开 searching 状态，
            # 否则 1.2 秒延迟内若恰逢 3 秒 tick / 20 秒超时，会再触发一次
            # _hide_end_game(False)，与跳回后的 _hide_end_game(True) 双执行
            # （双 spell destroy、对话/动画互相覆盖）。
            try:
                if getattr(self, '_hide_search_timer', None) is not None:
                    self._hide_search_timer.stop()
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
            self._hide_search_timer = None
            self._hide_stage = 'won_pending'  # 非 searching，避免 tick/超时重复触发
            # 1. 打开正确的文件夹窗口
            try:
                self.desktop_interaction.open_folder(folder_path)
            except Exception:
                try:
                    os.startfile(folder_path)
                except Exception as e:  # 修复：原先静默吞噬
                    _log.debug("main 防御性异常（已忽略）: %s", e)
            # 2. Ralsei 出现在文件夹窗口里（显示窗口，定位到文件夹窗口附近）
            self.show()
            # 尝试定位到文件夹窗口的位置
            try:
                (fx, fy) = self._resolve_target_screen_anchor(folder_path)
                self.move(int(fx - self.width() // 2), int(fy - self.height() // 2))
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
            # 3. 说"你找到我了"
            self.change_animation('surprised', force=True)
            self.dialogue_ui.add_dialogue("ralsei", "你找到我啦！真厉害！", "surprised")
            self.dialogue_ui.show_dialogue()
            # 4. 延迟1秒后从窗口跳回桌面，然后结束游戏（销毁文件夹）
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(1200, lambda: self._hide_jump_back_to_desktop())
        else:
            # 错误：打开它，加一句对话，继续 searching
            try:
                self.desktop_interaction.open_folder(folder_path)
            except Exception:
                try:
                    os.startfile(folder_path)
                except Exception as e:  # 修复：原先静默吞噬
                    _log.debug("main 防御性异常（已忽略）: %s", e)
            self.dialogue_ui.add_dialogue("ralsei", "这里没有我~ 再找找！", "happy")
            self.dialogue_ui.show_dialogue()

    def _hide_jump_back_to_desktop(self):
        """躲猫猫找到后：从文件夹窗口跳回桌面，然后触发结束（销毁障碍物）。"""
        # 播放跳跃动画，从当前位置跳到桌面底部
        screen = QApplication.desktop().availableGeometry()
        target_y = screen.height() - self.height() - 50
        target_x = self.x()
        # 简单跳跃：直接移动到桌面位置，播放jump动画
        self.change_animation('jump', force=True)
        self.move(target_x, target_y)
        # 延迟后结束游戏（用spell动画销毁文件夹）
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(500, lambda: self._hide_end_game(user_won=True))


def install_crash_guard():
    """安装全局未捕获异常兜底（必须在 QApplication 创建之前调用）。

    背景：PyQt5 在"槽函数（定时器回调 / 信号处理）里抛出未捕获异常"时会调用
    qFatal() 直接终止进程（本机实测退出码 0xC0000409），表现就是桌宠毫无提示地
    消失、日志里连一行错误都没有。而本项目有 10+ 个高频定时器
    （update_movement 30ms、update_animation 100ms 等），任何一处意外异常
    都会直接杀掉整个程序。

    这里安装自定义 sys.excepthook（PyQt5 检测到非默认 excepthook 后不会再 qFatal）：
      1) 完整堆栈写入日志与 logs/crash.log，便于事后定位；
      2) 进程不再退出，单次异常不至于终结用户一整天的陪伴。
    """
    import traceback

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            _log.error("未捕获异常（已拦截，程序继续运行）:\n%s", text)
        except Exception:
            pass
        try:
            crash_path = os.path.join(project_root, "logs", "crash.log")
            os.makedirs(os.path.dirname(crash_path), exist_ok=True)
            with open(crash_path, "a", encoding="utf-8") as f:
                f.write("\n===== %s =====\n%s" % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
        except Exception:
            pass

    sys.excepthook = _hook
    _log.debug("全局异常兜底已安装")
    return _hook


def check_single_instance():
    """
    单实例检查 — 确保同时只有一个 Ralsei Pet 在运行。
    修复：从模块顶层移入函数，避免 import 时就执行并可能退出。
    优先使用 Windows 命名互斥量，失败时回退到文件锁。
    """
    import atexit

    _log.debug("正在进行单实例检查...")

    mutex_name = r"Global\RalseiPetMutex"

    # 方案1：Windows 命名互斥量（最可靠）
    try:
        import win32event
        import win32api
        import winerror

        mutex = win32event.CreateMutex(None, False, mutex_name)

        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            _log.warning("单实例检查失败，Ralsei Pet 已经在运行中了！")
            _log.debug(" Ralsei 是独一无二的哦~")
            win32api.CloseHandle(mutex)
            input("按回车键退出...")
            sys.exit(0)
        else:
            _log.debug("单实例检查通过，互斥量已创建")
            # 互斥量会在进程结束时自动释放
            _log.debug("单实例检查通过，可以正常运行！")
            return True

    except Exception as e:
        _log.debug(f"互斥量单实例检查出错，改用文件锁: {e}")

    # 方案2：文件锁作为备选
    lock_file_path = os.path.join(os.getenv('TEMP', '.'), 'ralsei_pet.lock')

    def _cleanup_lock():
        try:
            if os.path.exists(lock_file_path):
                os.unlink(lock_file_path)
                _log.debug("单实例锁文件已清理")
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)

    try:
        with open(lock_file_path, 'x') as lock_file:
            lock_file.write(str(os.getpid()))
        _log.debug("备选单实例检查通过，锁文件已创建")
        atexit.register(_cleanup_lock)
        _log.debug("单实例检查通过，可以正常运行！")
        return True

    except FileExistsError:
        _log.debug("备选单实例检查：发现已存在的锁文件")
        try:
            with open(lock_file_path, 'r') as lock_file:
                pid = int(lock_file.read().strip())
            # 检查进程是否还活着
            try:
                os.kill(pid, 0)
                _log.debug("Ralsei Pet 已经在运行中了哦！")
                input("按回车键退出...")
                sys.exit(0)
            except OSError:
                # 进程不存在了，锁文件是残留的
                pass
        except (ValueError, OSError):
            pass

        # 清理残留锁文件并重新创建
        _log.debug("发现残留的锁文件，正在清理...")
        try:
            os.unlink(lock_file_path)
        except OSError:
            pass
        try:
            with open(lock_file_path, 'w') as lock_file:
                lock_file.write(str(os.getpid()))
            atexit.register(_cleanup_lock)
            _log.debug("锁文件已重新创建，单实例检查通过")
            _log.debug("单实例检查通过，可以正常运行！")
            return True
        except Exception as e:
            _log.warning(f"重新创建锁文件失败: {e}")
            # 最后兜底：允许运行（单实例检查失败不应阻止程序启动）
            _log.warning("警告：单实例检查失败，程序将继续运行")
            return True


if __name__ == "__main__":
    import traceback

    # 单实例检查（必须在最开始执行）
    check_single_instance()

    # 全局异常兜底：必须在 QApplication 之前安装，否则槽函数里的异常会直接 abort 进程
    install_crash_guard()

    try:
        app = QApplication(sys.argv)
        window = RalseiPet()
        window.show()
        result = app.exec_()
        # 程序退出时打印性能统计信息
        _log.debug("\n=== 正在打印性能统计信息 ===")
        perf_monitor.print_stats()
        _log.debug("=== 性能统计信息打印完成 ===")
        sys.exit(result)
    except Exception as e:
        _log.debug(f"程序运行时出错: {e}")
        _log.warning("详细错误信息:")
        traceback.print_exc()
        # 避免程序直接退出，让用户有时间查看错误信息
        input("按回车键退出...")
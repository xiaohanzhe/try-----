
import sys
import os
import time
import functools

# 注意：单实例检查已封装为 check_single_instance() 函数
# 在 if __name__ == '__main__': 中调用，避免 import 时就触发退出
# 也便于单元测试和 mock

# 继续导入其他模块
import random
import math
import statistics
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QMessageBox
from PyQt5.QtGui import (QPainter, QBrush, QColor, QCursor, QTransform,
                         QPixmap, QBitmap, QRegion)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal

try:
    from logger_utils import get_logger
except ImportError:  # 允许被包外单独导入
    import logging

    def get_logger(name):
        return logging.getLogger(name)

_log = get_logger(__name__)

# 抛物线（甩飞）飞行期的状态属性名。接住宠物 / 恢复完成时统一清掉，避免残留让
# update_movement 继续走坠落分支。放在模块级而非类级：便于离屏测试用轻量 stub
# 直接调用 _catch_falling_in_air（详见 verify_round8_fling.py）。
#
# 拆成两个常量是为了满足两种**不同**的清理时机：
#   · _FALL_VELOCITY_ATTRS —— 落地那一刻清（速度/落点标记），**但必须留着
#     _fall_phase**，否则下一帧的 phase 机被重置回 "flying"，又会重新入场；
#   · _FALL_STATE_ATTRS —— 空中被接住 / 恢复完成时清（连阶段字段一起清）。
# 教训（勿回退）：不要在各处内联写属性名元组 —— 新增 `_fall_vy0` 时就漏改了
# 三处内联列表，导致**第二次甩飞沿用上一次的起跳竖直速度**，落点判定用错初速
# → 下甩时误判"要回到起跳高度"→ 一路飞到 2.5s 兜底超时才落地，表现就是
# 用户报的"被甩飞的时候卡在一个动画里不继续"。
_FALL_VELOCITY_ATTRS = (
    'fall_slide_speed_x', 'fall_slide_speed_y',
    '_fall_vx', '_fall_vy', '_fall_launch_y', '_fall_landed',
    '_fall_flight_time', '_fall_vy0',
)
_FALL_STATE_ATTRS = ('_fall_phase', '_fall_phase_start') + _FALL_VELOCITY_ATTRS

# ---------------------------------------------------------------------------
# 「建楼」要求 第36/37行：摔倒的**生气动画必须真的持续**一段时间
#   · 第36行：用户行为导致摔到桌面 → 用生气的那组，**至少 5s**
#   · 第37行：移动他所在的楼板 → 重心不稳摔倒，**至少 3s**
#
# 修复（第十六轮复检发现，第十七轮改）：这两个时长原来只写成
# `self.max_fall_duration = 5.0 / 3.0`，而 `max_fall_duration` 在**全项目只有
# `handle_fall` 会读**；`start_falling()` 偏偏又把 `is_falling` 置 False
# （坠落期间走的是 `handle_gravity_fall`）→ 那句 5.0 是**死参数**，生气动画只在
# 下降途中播了一下，落地就被 `trigger_splat()` 换回普通 `splat`。
# 加上 `handle_fall` 的 splat 阶段时长是**硬编码 1.0s** —— 三处叠加，"至少 5s"
# 从未成立。
#
# 现在把"生气素材 + 最短停留"做成**由起因纯派生**的两个模块级函数：起因在哪里
# 知道（`_fall_reason`），时长就在哪里算（`_fall_splat_hold`），落地结算
# （`trigger_splat` / `handle_fall`）只负责读。默认值 1.0 与改前行为逐字节一致
# （`_fall_reason` 为 None 时即旧行为）。
#
# 为什么放在**模块级**而不是类方法：这两个判定会被多个历史回归套件用轻量桩
# （SimpleNamespace / 手写 stub）驱动 `RalseiPet.handle_fall(stub, ...)` 跑，
# 类方法会让每个桩都得补一个转发方法（第十七轮实测：round6_verify / round8_fling
# 当场 AttributeError 崩在半路）。模块级函数由 main 的全局命名空间解析，
# 桩不需要知道任何事 —— 与 `_fall_splat_hold` 同一条理由。
FALL_MAD_REASONS = ('floor_removed', 'window_move')
FALL_SPLAT_HOLD = {
    'floor_removed': 5.0,     # 要求第36行：用户关窗抽走楼板 → 生气 ≥5s
    'window_move': 3.0,       # 要求第37行：挪动楼板把人掀倒 → 生气 ≥3s
}
FALL_SPLAT_HOLD_DEFAULT = 1.0
# 生气素材（`spr_cutscene_24e_ralsei_splat_mad.png`）。它早就配在 animations.json /
# sprite_loader 里、也进了"特殊动画"白名单，但**全项目零调用** —— 这次接活。
FALL_MAD_ANIMATION = 'splat_mad'


def _fall_splat_hold(pet):
    """这次摔倒的"生气动画最短停留秒数"（无起因 → 1.0，与改前一致）。

    **唯一真源是 `pet._fall_reason`**（在知道起因的地方写一次），此处纯派生 ——
    不再另存一个 `_splat_hold` 实例属性，避免"双真源"（本项目的头号坑）。
    """
    return FALL_SPLAT_HOLD.get(getattr(pet, '_fall_reason', None),
                               FALL_SPLAT_HOLD_DEFAULT)


def _splat_animation_name(pet):
    """落地进入 splat 阶段该播哪个素材（**唯一入口**，两个调用点共用）。

    建楼要求 第36/37行：用户行为造成的摔落（关窗抽走楼板 / 挪楼板）要用
    "生气的那组" —— 即 `splat_mad`（`alias_of=fall_mad`，
    `spr_cutscene_24e_ralsei_splat_mad.png`）。它早就配在 animations.json /
    sprite_loader 里、也进了"特殊动画"白名单，但第十六轮复检前**全项目零调用**：
    `trigger_splat` 恒切普通 `splat`，把坠落途中刚播上的 `fall_mad` 在落地那一瞬
    顶掉 → "生气动画至少 5s"根本不可能成立（复检 G1c）。
    自己走到边缘掉下去 / 被甩飞 → 常规 `splat`（改前行为）。
    """
    if getattr(pet, '_fall_reason', None) in FALL_MAD_REASONS \
            and FALL_MAD_ANIMATION in pet.sprite_loader.sprites:
        return FALL_MAD_ANIMATION
    return "splat"


# ---------------------------------------------------------------------------
# 「建楼」批次 B（第十八轮）：**层高闸门 + 攀爬衔接**
#
# 复检缺口 G3：`check_window_movement` 每拍把 `new_floor = get_current_floor(pos)`
# **直接赋值**，没有任何"层高差必须靠跳"的闸门 —— 宠物站在桌面（1楼）水平走进
# 某个窗口的可见区域，会被**直接提升**到那一层，不跳、不落，只是一个瞬时的层级跳变。
#
# 用户口径（第十八轮原话）：
#   · "走进更低的楼层也是一样，反正只要是楼层高低变换就要通过跳来衔接"；
#   · "下楼的时候别用掉落，也用跳"；
#   · "要预留一定距离哦，别看着和垂直起跳一样"；
#   · "在楼层跨度较低的时候跳，跨度高的时候爬"；
#   · "他也不能一次性跳上跨度很高的楼层，需要用各个方向的攀爬动画去切换高低楼层"；
#   · "那个摔扁的机制需要在层数比较高且掉下来而非主动下来的时候才会触发"。
#
# 于是本轮的规则是：
#   ① 宠物**自己走出来**的楼层高低变换 → 一律走"跳/攀爬"（上楼不再静默提升、
#      下楼不再重力掉落）。被动成因（用户关窗抽走楼板 / 挪楼板 >400px / 甩飞）
#      仍走原来的坠落链路，见 `check_window_movement` 的 要求⑩/⑪ 分支。
#   ② 衔接动作按**跨度**选：`|Δplatform_height| <= CLIMB_SPAN_JUMP_MAX`（一层）
#      用既有 `jump` 家族；跨度更大才用 `climb_*`（"跨度高的时候爬"）。
#   ③ 落点必须**预留水平距离**（`CLIMB_HORIZONTAL_RUN`），避免"垂直起跳"的观感。
#
# 素材（用户指定）：`spr_ralsei_climb_1_*` 朝右 → `climb_right`；
# 朝左由它**水平镜像**得到（`spr_ralsei_climb_left_*`，用户："相反方向的你就给他翻转一下"）；
# `spr_ralsei_climb_0_degrees_*` 朝前 → `climb_front`；没有朝后的（"那样也用不上"）。
# 三组都已登记进 `sprite_loader` 内置表与 `assets/animations.json`（H5 S2 等价契约）。
CLIMB_SPAN_JUMP_MAX = 5          # 跨度 ≤ 5（相邻一层，platform_height 每层 +5）→ 用跳
CLIMB_HORIZONTAL_RUN = 90        # 衔接要预留的水平距离（px，位置坐标口径）
CLIMB_MIN_RESERVE = 24           # 吸附后仍要保留的最小水平位移（否则换方向再试）
CLIMB_LANDING_MAX_TRAVEL = 320   # 落点离宠物超过这个距离就不成立（"只到够得着的那块楼板"）
# 摔扁门槛（要求 第36/37行 + 用户第十八轮口径"层数比较高且掉下来"）：
# 落差 ≥ 两层（platform_height 差 ≥10）才算"层数比较高"。一层（5）掉下去不摔扁。
FALL_SPLAT_MIN_DROP = 10
CLIMB_ANIMATION_NAMES = {
    'right': 'climb_right',
    'left': 'climb_left',
    'front': 'climb_front',
}


def _climb_animation_name(pet, direction):
    """该方向可用的攀爬素材名；素材不在库里则返回 None（调用方回落 `jump` 家族）。

    与 `_splat_animation_name` 同一条理由放在**模块级**：历史回归套件用轻量桩驱动
    产品方法，桩不该为它补一个转发方法。
    """
    name = CLIMB_ANIMATION_NAMES.get(direction) or CLIMB_ANIMATION_NAMES['front']
    sprites = getattr(getattr(pet, 'sprite_loader', None), 'sprites', None) or {}
    return name if name in sprites else None


def _jump_kind_for_span(span):
    """跨度 → 衔接方式。用户口径："在楼层跨度较低的时候跳，跨度高的时候爬"。"""
    try:
        return 'jump' if abs(int(span or 0)) <= CLIMB_SPAN_JUMP_MAX else 'climb'
    except Exception:
        return 'jump'


def _jump_hdir_for(start_pos, target_pos):
    """衔接的横向方向（选攀爬素材用）：横向位移为主 → left/right，否则 front。

    没有朝后的攀爬素材 —— 用户："没有朝后面的因为那样也用不上"。
    """
    if start_pos is None or target_pos is None:
        return 'front'
    try:
        dx = int(target_pos.x()) - int(start_pos.x())
    except Exception:
        return 'front'
    if dx > 4:
        return 'right'
    if dx < -4:
        return 'left'
    return 'front'


def _landing_drop_height(pet, landed_floor):
    """这次坠落是从多高掉下来的（起点楼层 − 落点楼层的 platform_height 差）。

    **夹到 ≥0**：这是"落差"这个物理量，不是有符号坐标差。缺 `_fall_from_height`
    时按 0 起算，若落点楼层比 0 高就会算出负数 —— 负落差本身不会误触发摔扁
    （`>= 门槛` 恒假），但把"落差"交出一个负数是个陷阱：任何按距离用的调用方
    （阈值比较、惯性缩放、音效强度）都会静默算错。这里一次夹干净。
    """
    try:
        from_h = int(getattr(pet, '_fall_from_height', 0) or 0)
        to_h = int((landed_floor or {}).get('platform_height', 0) or 0)
    except Exception:
        return 0
    return max(0, from_h - to_h)


def _should_splat_on_landing(pet, landed_floor):
    """落地是否触发"摔扁"（唯一入口，`handle_gravity_fall` 的两个落点共用）。

    用户口径（第十八轮）："那个摔扁的机制需要在层数比较高且掉下来而非主动下来的
    时候才会触发哦"。

    两个条件缺一不可：
      · **是被动摔下来的**：主动下楼/上楼走的是跳跃-攀爬链路，根本不进坠落状态机，
        所以走到这里的已经不可能是"主动下来"；
      · **层数比较高**：落差 ≥ `FALL_SPLAT_MIN_DROP`（两层）。从一层窗口（ph=5）
        摔到桌面落差只有 5 → 不摔扁，与用户口径一致。
    速度门槛（>150）沿用改前的口径，不引入新的手感变量。
    """
    try:
        if getattr(pet, 'fall_speed', 0.0) <= 150:
            return False
    except Exception:
        return False
    return _landing_drop_height(pet, landed_floor) >= FALL_SPLAT_MIN_DROP

# "特殊动画"的定义（第八轮）。用户要求：
#   "除了走路，跑步，待机这几个动画，其余的都只交给 AI 判断是否播放，别和抽风似的突然一下"；
#   "如果要是播放，那就播完，不要打断，也不要出现边播放边移动这种情况（只针对特殊动画）"。
# 这里列出**非特殊**的动作分组 —— 它们由移动/物理/施法/道具状态机驱动，必须允许被状态随时
# 覆盖（否则摔下去、开始走路时切不动动画，就会"卡在动作里"）：
#   idle / walk_* / run_*        常规移动与待机
#   jump_* / fall* / splat* / land / hatless_throw / slide / roll   物理与摔倒流程
#   spell* / item                施法与道具
# 其余（laugh / dance / sing / wave / curtsy / hug / pose / tea / nuzzle / victory /
# spin / bow / look_up / surprised / cry / sad / happy / act / book_look …）= 特殊动画。
_NON_SPECIAL_ANIM_GROUPS = frozenset({
    'idle', 'walk', 'run',
    'jump', 'fall', 'splat', 'land', 'hatless_throw', 'slide', 'roll',
    'spell', 'item',
})


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
        stats = self.get_stats()
        if not stats:
            _log.info("暂无性能统计数据")
            return
        _log.info("========== 性能统计 ==========")
        for func_name, stat in stats.items():
            _log.info(
                f"函数: {func_name} | 调用次数: {stat['count']} | "
                f"平均耗时: {stat['avg']:.4f} ms | "
                f"最小耗时: {stat['min']:.4f} ms | "
                f"最大耗时: {stat['max']:.4f} ms"
            )
        _log.info("==============================")

# 创建全局性能监控实例
perf_monitor = PerformanceMonitor()

# 性能监控装饰器
def monitor_performance(func):
    @functools.wraps(func)
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

# 修复：把 modules/ 也放进 sys.path。modules/*.py 内部用的是"扁平导入"
# （如 `from logger_utils import get_logger`），只有 modules/ 本身在 sys.path 上
# 才能命中真实模块。此前按 README 记载的 `cd src && python main.py` 启动，会在
# import 期直接 ModuleNotFoundError 崩掉；而回归脚本恰好预置了 modules/，
# 于是掩盖了这一类问题（已纳入第七轮）。
# 用 append 而非 insert：让标准库始终优先，仅当名字无法解析时才落到 modules/。
_modules_dir = os.path.join(project_root, 'modules')
if _modules_dir not in sys.path:
    sys.path.append(_modules_dir)

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
# 小游戏控制器（H4/H5 Wave 1 · W1-3）：石头剪刀布 + 猜数字 7 个方法搬出上帝类。
# 只搬方法不搬状态 —— game_state 等仍在 __init__，控制器通过宿主引用读写。
from modules.games_controller import GamesController
from modules.video_controller import VideoController
from modules.spell_controller import SpellFlowController
from modules.hide_controller import HideAndSeekController
from modules.file_sheet_controller import FileSheetController
# 场景系统控制器：把「原作的世界搬到桌面上」这条需求的地基接上宿主。
# P0 阶段是空壳（只加载索引 + 存状态，不动任何画面）—— 用户要求「留好拓展接口」，
# 所以接口必须先真的在位、能被调、能过 G2，而不是只写在文档里。
from modules.scene_controller import SceneController
# 场景画布（第44轮 P1）：把 SceneController.plan_frame() 的绘制指令**真正画出来**。
# 这是"渲染层"的最后一跳 —— 前面 scene_system/scene_camera/scene_render 都只出数据，
# 没有消费者就是"函数写对了但产品用不上"（本项目最贵的坑，见记忆铁律 §4）。
from modules.scene_canvas import SceneCanvas
# 事件台词（S7）：档位登记 / 提示词构造 / 首句截断 / 罐头去重，都是纯逻辑（无 Qt）
from modules.event_speech import (TIER_AI, EVENT_MAX_CHARS, RecentLinePicker,
                                  build_prompt, guard_reaction, pet_kind, tier_of,
                                  first_sentence, strip_action_parentheticals,
                                  looks_out_of_character, looks_like_assistant_speak)
# 联网搜索摘要：依赖 beautifulsoup4。改为"可选导入"而不是整段注释掉——
# 原写法让整个模块变成永远不可达的死代码（需求"能上网"缺一环），
# 且一旦有人取消注释而环境没有 bs4，程序会在 import 期直接崩溃。
try:
    from modules.search_summarizer import SearchSummarizer
except Exception as _e:  # ImportError / 依赖缺失 / 模块内异常
    SearchSummarizer = None
    _log.warning("联网搜索摘要模块不可用（缺少 beautifulsoup4？已降级）: %s", _e)


# 关系演进（第二十轮）：可选导入 —— 与上面 search_summarizer 同一条纪律。
# 关系模块挂了不该让整个程序起不来，退化成 None（链路里所有取用处都有 None 判断）。
try:
    from modules.relationship import Relationship as _Relationship
except Exception as _e:
    _Relationship = None
    _log.warning("关系演进模块不可用（已降级为无关系态）: %s", _e)


def _make_relationship():
    """造一个关系实例：存盘路径走 data_store（唯一存储入口），取不到就退内存态。

    为什么不在模块里直接 import data_store：data_store 会反向依赖 memory 层，
    而关系模块要在启动早期可用 —— 这是**初始化环**，本项目已踩过 4 次。
    所以路径由**调用方注入**（与 event_speech.py「禁止 import 项目内模块」同源）。
    """
    if _Relationship is None:
        return None
    path = None
    try:
        import data_store
        path = data_store.app_file(RalseiPet.RELATIONSHIP_FILE)
    except Exception as e:
        _log.debug("关系存储路径不可用，改用内存态: %s", e)
    try:
        return _Relationship(path=path)
    except Exception as e:
        _log.warning("关系模块初始化失败（已降级为无关系态）: %s", e)
        return None


class RalseiPet(QMainWindow):
    # 跨线程 API 结果信号：(response, callback) —— 工作线程 emit，主线程槽处理，
    # 避免线程内 QTimer.singleShot 因无 Qt 事件循环导致回调永不触发
    _api_result = pyqtSignal(object, object)

    # 跨线程流式分片信号：(generation, chunk) —— S8 流式输出用。
    # 第一个参数是"世代号"：用户已经问了新问题时，旧请求的尾巴不该再往对话框写字。
    # chunk 为 None 表示"作废已显示的内容"（护栏判退 → 要重采样了）。
    _api_delta = pyqtSignal(object, object)

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
        # 流式分片信号（S8）：工作线程 → 主线程 → 对话框打字机
        self._api_delta.connect(self._on_api_delta)
        self._ai_delta_sink = None    # 当前请求的流式接收方（只在主线程读写）
        self._ai_delta_gen = 0        # 世代号：每次发起新请求 +1
        # 事件台词（S7）：罐头去重器 / 事件世代号 / 上次走 AI 的时刻（频率闸）/
        # "上一个事件还在等 AI" 标记（防叠加请求）
        self._event_line_picker = RecentLinePicker()
        self._event_speak_gen = 0
        self._event_speak_last = None
        self._event_speaking = False
        
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
    
    # ------------------------------------------------------------------
    # 「转发壳 + 宿主 API」口径的转发机制（H4/H5 Wave 1）
    #
    # 被搬进控制器的宿主方法（如 RalseiPet.start_rock_paper_scissors）在这里
    # **不再定义**；`__getattr__` 把找不到的属性转给控制器实例。于是
    # `play_game` / `update_stats` / `dialogue_ui.parent.*` 三处调用点
    # **一个字符都不用改**，拿到的仍是绑定到控制器的同一个方法对象。
    #
    # 为什么需要它（而不是在类里写 7 个 def 转发）：
    #   ① 少写 7 个只有一行的 def，也少 7 处随方法改名而漂移的风险点；
    #   ② **自愈能力**：控制器后续加方法，宿主自动可见 —— 这个项目最贵的坑是
    #      「函数写对了但产品用不上」，集中转发把这类漏接线压到零。
    #
    # 安全边界（三条，缺一不可）：
    #   1. 只转发 `__dict__` 里**真的存在**的控制器实例 —— 用
    #      `self.__dict__.get('games')` 而不是 `self.games`：后者会递归回
    #      `__getattr__`，在 `self.games` 尚未赋值时（`__init__` 早期、或 unpickle
    #      / 拷贝构造）造成无限递归 → RecursionError。
    #   2. `hasattr(ctrl, name)` 而非 `name in dir(ctrl)`：前者才走描述符协议，
    #      `@property` / 动态 `__getattr__` 都能被正确识别。
    #   3. 取不到就抛**原始的** `AttributeError(name)`，保住 `hasattr()`、
    #      `getattr(x, n, default)`、`copy`/`pickle` 探针语句的正常语义
    #      （它们依赖 `__getattr__` 在缺失时抛 AttributeError）。
    #
    # 性能：只有「常规查找全 miss」的属性才会走到这里，热路径（每帧属性访问）
    # 完全不受影响。转发名单按控制器逐个列出，**不用**遍历所有控制器 ——
    # 避免"遍历到某个属性含副作用的控制器"这类隐式耦合。
    #
    # ⚠️ 绝不能用 `hasattr(ctrl, name)` 探测控制器是否"有"这个名字：
    #   控制器自己的 `__getattr__` 会**回落给宿主**（它靠这个读到 game_state）。
    #   于是 `hasattr(ctrl, name)` 会反过来 `getattr(pet, name)`，又回到本函数
    #   → **无限递归**。真机踩过：`randomize_movement_pattern` 里的
    #   `getattr(self, 'game_state', {})` 在 `__init__` 早期（game_state 还没赋值）
    #   按下这条链 → RecursionError 崩在构造期。
    #   所以这里改成**显式方向**：只有"控制器自己类上定义的方法"才转发，
    #   属性/状态名一律不转（那些本就该在宿主上找）。
    # ------------------------------------------------------------------
    #   · 'games'  → GamesController（W1-3）
    #   · 'video'  → VideoController（W1-4）
    #   · 'spell'  → SpellFlowController（W1-1）
    #   · 'hide_seek' → HideAndSeekController（W1-2）
    #   · 'file_sheet' → FileSheetController（W1-6）
    #   · 'scene'  → SceneController（场景系统 P0，非 H4/H5 拆分产物）
    #
    # W1-7（第二十六轮）把 `handle_game_input` 从宿主搬进了 'games'。
    # 它当初被 W1-3 **刻意留下**，理由是它经 `_abort_hide_and_seek` 依赖
    # W1-2（躲猫猫）。W1-2 落地后该依赖由**兄弟控制器白名单**（
    # GamesController.__getattr__ 第 3 条扫描宿主 `_CONTROLLER_ATTRS`）承接，
    # 前提成立，故一并搬入，Wave 1 至此**业务方法全部归位**。
    #
    # ⚠️ 'scene' 与上面五个有一个本质区别：前五个是**搬出来的**（方法原本在宿主，
    # 拆分后仍靠转发壳让老调用点零改动），'scene' 是**新写的**（P1 渲染层的方法
    # 一出生就定义在控制器里，宿主从来没有过）。两者共用同一套转发机制，但
    # "搬"与"新写"决定了校验方式不同 —— 搬出来的要证明**逐字等价**，
    # 新写的要证明**零行为变化**（不切场景时 G2 输出逐字节不动）。
    _CONTROLLER_ATTRS = ('games', 'video', 'spell', 'hide_seek', 'file_sheet', 'scene')

    def __getattr__(self, name):
        # 注意：`__getattr__` 只在常规查找失败时被调用，所以 `self.games` 已存在时
        # `self.games.start_rock_paper_scissors` 走的是正常路径，不进这里。
        for attr in RalseiPet._CONTROLLER_ATTRS:
            ctrl = self.__dict__.get(attr)
            if ctrl is None:
                continue
            # 只看控制器**类**上定义的名字（含 __dict__ 里的方法/静态方法），
            # 不触发控制器实例的 __getattr__ 回落链 —— 这是不递归的关键。
            impl = getattr(type(ctrl), name, None)
            if impl is not None:
                return getattr(ctrl, name)
        raise AttributeError(name)
        
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
        
        # ---- 场景画布（第44轮 P1：把 scene_render 的绘制指令真正画出来）----
        # 为什么是**子控件而不是主窗口自绘**：主窗口的 `paintEvent` 已经承担
        # "填透明"这一条职责（见其 docstring），而场景层要画背景 + 物件 + 边框，
        # 生命周期与尺寸都跟着"当前房间"变 —— 独立控件能自己 resize/update，
        # 不必让主窗口的绘制路径长出分支（那会让 P0「不切场景时零行为变化」
        # 的判据失去意义）。
        # ⚠️ `SceneCanvas.__init__` 末尾 **显式 hide()**：默认不显示。
        #    宿主确认要显示场景（见 `_update_scene_layer`）后才 show —— 这样
        #    桌面场景（无 bg / 无物件）跑起来时画面上**零变化**。
        self.scene_canvas = SceneCanvas(self)
        self.scene_canvas.move(0, 0)
        self._scene_layer_visible = False

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
        # 关系演进（第二十轮）：信任度 = **内部**评估量，绝不对用户显示。
        # 存盘走 data_store（唯一存储入口）→ E 盘优先，取不到退内存态，绝不抛。
        # 为什么由 App 持有而不是放进 persona：persona 是**静态**的（每次读出来一样），
        # 而关系必须随相处**变化** —— 静态提示词写不出"从戒备到朋友"。
        self.relationship = _make_relationship()
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
        
        # 小游戏控制器（W1-3）：持有石头剪刀布 / 猜数字 的游戏逻辑。
        # 注意创建时机 —— 必须在 `init_systems` 里、且**晚于**
        # `dialogue_ui` / `emotion_system` / `sprite_loader` 的初始化，
        # 因为它只借用这些宿主成员（方法体里 `self.dialogue_ui...` 经本类的
        # `__getattr__` 转发到宿主）。
        self.games = GamesController(self)
        # 视频控制器（W1-4）：持有「陪看视频」这条业务线的 8 个方法。
        # 时机同 games —— 在 init_systems 内、晚于 dialogue_ui / desktop_interaction。
        self.video = VideoController(self)
        # 施法流程控制器（W1-1）：持有「施法 (spell)」这条业务线的 4 个方法。
        # 时机同 games/video —— 在 init_systems 内、晚于 dialogue_ui / sprite_loader。
        # ⚠️ 它依赖紧随其后的 `_spell_*` 状态声明区；但控制器任何时候取到的都是
        # 宿主同一份状态（转发壳），故声明先后无实质影响，仅按紧邻放置便于阅读。
        self.spell = SpellFlowController(self)
        # 躲猫猫控制器（W1-2）：持有「躲猫猫 (hide & seek)」这条业务线的 12 个方法。
        # 时机同 games/video/spell —— 在 init_systems 内、晚于 dialogue_ui / desktop_interaction。
        # ⚠️ 依赖紧随其后的 `_hide_*` 状态声明区（含本项新补的 4 个预声明）。
        self.hide_seek = HideAndSeekController(self)
        # 文件 / 表格操作控制器（W1-6）：持有「文件/表格操作」这条业务线的 4 个方法。
        # 时机同前序 —— 在 init_systems 内、晚于 dialogue_ui / desktop_interaction。
        # ⚠️ 本项**不搬任何状态属性**（无 `_fs_*` 之类），故无需任何预声明：
        #    4 个方法全是"读宿主 + 调宿主 API + 用局部变量"，状态劈裂风险为零。
        #    `open_file` / `open_folder` 留在宿主，经宿主 __getattr__ 的 MRO 白名单命中。
        self.file_sheet = FileSheetController(self)
        # 场景系统控制器（场景系统 P0）：把「原作的世界搬到桌面上」接上宿主。
        # ⚠️ 时机同前序 —— 在 init_systems 内、晚于 floor_manager / customization_system。
        #    P0 只读 `assets/scenes/_index.json` + 默认场景，结果存宿主状态字段；
        #    **不注册定时器、不改渲染路径、不碰物理** → 不切场景时零行为变化。
        #    P1 的渲染层需要 floor_manager（地面 y）/ sprite_loader（物件帧），
        #    两者在本行之前都已就绪。
        self.scene = SceneController(self)
        
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
        # ⚠️ 以下 2 个此前**从未在状态声明区出现**（只在方法体里首次赋值）。
        # 它们原本一直是「方法内首赋值 → 自然进宿主 __dict__」，功能正常；
        # 但 W1-1 把施法方法搬进控制器后，控制器的 __setattr__ 转发判据是
        # 「宿主**已拥有**这个名字」—— 未预声明 → 不满足判据 → 首赋值会落到
        # **控制器自己的 __dict__**，状态被劈成两份（详见 W1-4 报告第五节铁律 3）。
        self._spell_seen_frame = -1                 # casting 帧去重标记（同帧重复见不计数）
        self._spell_cast_start_time = None          # casting 起始时刻（5s 时间兜底用）

        # ========== 躲猫猫 (hide & seek) 状态字段 ==========
        self._hide_stage = None                     # None | moving_to_center | creating | hiding_spell | moving_to_folder | searching
        self._hide_folder_path = None               # 选中的藏身文件夹绝对路径
        self._hide_obstacles = []                   # 5 个障碍物文件夹路径列表（上3下2）
        self._hide_center_x = None
        self._hide_center_y = None
        self._hide_search_timer = None              # searching 阶段定时器
        # ⚠️ 以下 4 个此前**从未在状态声明区出现**（只在方法体里首次赋值）。
        # 它们原本一直是「方法内首赋值 → 自然进宿主 __dict__」，功能正常；
        # 但 W1-2 把躲猫猫方法搬进 HideAndSeekController 后，控制器的 __setattr__
        # 转发判据是「宿主**已拥有**这个名字」—— 未预声明 → 不满足判据 → 首赋值会落到
        # **控制器自己的 __dict__** → 状态劈成两份（详见 W1-4 报告第五节铁律 3）。
        # 后果：宿主 `_notify_arrived_if_needed` 读到 `_hide_moving_cb=None`
        # → 到达回调永不触发 → 躲猫猫卡在走路态。
        self._hide_search_started_at = 0            # searching 起始时刻（20s 上限判定用）
        self._hide_search_checked = set()           # 已"表演找过"的文件夹路径集合
        self._hide_moving_cb = None                 # 到达回调（由 _hide_move_to_point 注册）
        self._hide_moving_cb_stage = None           # 该回调对应的 stage 名
        # game_state 在 __init__ 中已完整初始化（含 is_playing/game_type/player_score/best_streak 等 12 个字段）

        # ========== 场景系统 状态字段（P0）==========
        # ⚠️ 这 9 个（**6 个场景 + 3 个路由**）**必须在这里预声明**，
        #    理由与上面 `_spell_*` / `_hide_*` 完全一样：
        #    SceneController 的 `__setattr__` 转发判据是「宿主**已拥有**这个名字」。
        #    未预声明 → 首次赋值会落进**控制器自己的 __dict__** → 状态劈成两份，
        #    而且这种劈裂 G2 **完全看不见**（本项目真踩过两次，见 W1-4 报告铁律 3）。
        # 字段分工（唯一真源都在宿主，控制器不持有任何场景状态）：
        self._scene_index = None                    # load_index() 的结果（含 chapters/scenes/default_scene）
        self._scene_state = None                    # 当前场景的 SceneState（只读视图，换场景 = 换引用）
        self.current_scene = None                   # 当前场景 id（str），如 'desktop'
        self.scene_objects = []                     # 当前场景的可见物件缓存（P1 渲染层消费）
        self._scene_anchors = {}                     # 全局命名锚点表（_anchors.json）
        self._scene_loaded = False                  # 索引是否已尝试加载过（幂等守卫，防重复 IO）
        # ---- 路由层（"什么语境下去哪"）状态 ----
        # 与上面同一条铁律：控制器会用到的名字必须在**宿主**预声明。
        self._scene_routes = None                   # load_routes() 的结果（含 routes/fallback）
        self._routes_loaded = False                 # 路由表是否已尝试加载过（幂等守卫）
        self._scene_route_reason = ''               # 最近一次路由命中给的"为什么走这条路"
        # ---- 相机（第44轮：居中式跟随 + 背景相对运动）状态 ----
        # 同一条铁律：控制器会用到的名字必须在**宿主**预声明。
        self._scene_camera = None                   # Camera 实例（scene_camera.Camera）
        # ★ 房间放大系数（用户 44 轮口径："Ralsei 是人物，房间是场景，要看到所有
        #   属于 Ralsei 的东西，缩放至少要与当前 Ralsei 的大小一致"）。
        #   实测推导（第44轮，两个独立来源交叉验证）：
        #     · 原作 Ralsei 行走精灵 = 21×41 px（`deltarune_ralsei/spr_ralsei_walk_*.png`）
        #     · 原作现实世界 = 320×240 逻辑像素，**×2 输出** = 640×480 屏幕像素
        #     · 产品当前把 Ralsei 画成 21×41 × 2.0 = **42×82 屏幕像素**
        #       （`main.py` 的 `scale_factor = getattr(self,'_cached_scale_factor', 2.0)`
        #        —— 注意 `_cached_scale_factor` **全仓从未被赋值**，实际恒走默认 2.0）
        #   ⇒ 产品人物视觉大小 ≡ 原作人物视觉大小 ⇒ 场景取 **2.0** 才同比例。
        #   ✅ 这条同时满足"至少与 Ralsei 一致"（取等号 = 一致）与
        #      "不必全屏"（640×480 的房间在 1080p 上只占约 1/3 宽）。
        self.scene_scale = 2.0                      # ★ 房间放大系数（= 原作输出倍率）
        self.camera_rect = None                     # 相机矩形缓存（P1 渲染层消费）
        # ---- 渲染层（第44轮 P1：房间几何 + 绘制计划）状态 ----
        self._scene_geometry = {}                   # 房间世界几何表（_room_geometry.json 的 rooms）
        self._geometry_loaded = False               # 几何表是否已尝试加载过（幂等守卫）
        self.scene_plan = []                        # 最近一帧的绘制指令清单（Qt 绘制壳消费）

        # ---- P0 接线：让场景系统真的跑起来（第 38 轮）----
        # 为什么放在这里：状态字段刚声明完、`self.scene` 已构造（上方 L779），
        # 且**早于窗口显示** —— 索引就位后，P1 的渲染层不必再等一次 IO。
        # 为什么**安全**（P0 判据 =「不切场景时零行为变化」）：
        #   `load()` / `load_routes()` 只做「读 JSON + 写宿主状态字段」两件事，
        #   不注册定时器、不改渲染路径、不碰物理、不调任何 Qt API；
        #   写进去的 `current_scene` / `scene_objects` 目前**零消费者**
        #   ⇒ 画面上看不出任何区别。
        # 为什么**拖不垮启动**：两者都是「永不抛」契约（内部 try/except 全兜），
        #   且**幂等**（`_scene_loaded` / `_routes_loaded` 守卫）—— 失败只记日志、
        #   场景系统降级为空态，桌宠照常起来（与 search_summarizer / relationship
        #   同一条纪律：非关键路径的失败不许让桌宠起不来）。
        # ⚠️ 顺序有意义：先 `load()`（索引 + 默认场景 'desktop'）再 `load_routes()`
        #   （路由表）。路由的 `destinations()` 要用索引过滤未登记场景，
        #   反过来的话第一次自省会拿到空清单。
        self.scene.load()          # 索引（1,014 场景）+ 默认场景 desktop
        self.scene.load_routes()   # 路由表（443 条原作连接 + 兜底）；P1 才有人自动调 pick_route
        # ---- 相机接线（第44轮）----
        # 用户对"操控效果"的裁定：「人物走到中间后一直居中然后背景相对运动」
        # —— 这正是原作口径（GMS2 原生相机 camera_set_view_target，见 scene_camera）。
        # `init_camera()` 只做「建 Camera 实例 + 从宿主读放大系数」，
        # **不注册定时器、不改渲染路径**（与 P0「不切场景时零行为变化」同一条纪律）。
        self.scene.init_camera()
        # ---- 渲染层接线（第44轮 P1）----
        # 房间几何表：渲染层要画房间（相机钳制 / 背景铺排 / 物件裁剪）必须知道
        # **房间的世界尺寸**（原作里 6,220×1,920 的大房间也有）—— 产品场景 JSON
        # 里没有 w/h（第 36~40 轮只登记了 bg / original_room_id），所以第 44 轮
        # 从五章普查结果蒸馏出 `_room_geometry.json`（1,251 间，锚点校验 100% 命中）。
        # `load_geometry()` 只做「读 JSON + 写宿主字段」，不注册定时器、不碰 Qt。
        self.scene.load_geometry()

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

        # 空中接住（用户反馈"坠落中没法用鼠标二次抓住，且要有针对当时线速度的减速"）
        # 按下鼠标时把坠落线速度交给这个缓冲窗口，线速度在 _CATCH_BRAKE_SECONDS 内
        # 线性衰减到 0，而不是像撞墙一样瞬间归零。
        self._CATCH_BRAKE_SECONDS = 0.28
        self._catch_brake = None

        # 待机动画开关：只有原地静止满 IDLE_LOOP_MIN_SECONDS 才置真（update_animation
        # 静止分支里按 idle_timer 计算），未满则只显示站立静帧。
        self._idle_loop_active = False

        # "正在发起一次性动画"的短暂标记：用于让 play_animation_once 自己那次
        # change_animation 通过"特殊动画播完为止"这道锁（见 change_animation 关键 1.6）。
        self._play_once_arming = False
        
        # 动画播放控制
        self.animation_change_cooldown = 0.8  # 0.8秒冷却时间，防止频繁切换导致的抽搐
        # 表演动画最小持续时间：laugh/tea/wave/dance 等被触发后至少播这么久才允许切回 idle，
        # 避免"闪一下就没了"（修复：is_happy 等状态只持续一帧导致表演动画只播0.15秒）。
        self._last_perf_anim_time = 0.0
        self._perf_anim_min_duration = 1.5
        self.last_animation_change = time.time() - self.animation_change_cooldown  # 初始化为冷却时间之前，确保第一次切换也受到冷却时间限制
        
        # 从配置中获取动画设置（默认 6FPS：桌宠逐帧播放按 30fps 会显得"快进抽搐"）
        self.animation_fps = self.config_manager.get("animation.fps", 6)
        self.animation_frame_delay = self.config_manager.get("animation.frame_delay", int(1000 / self.animation_fps))  # 毫秒，转换为整数

        # 修复：动画定时器原来固定 167ms（≈6FPS），导致配置 fps>6 完全无效
        # （update_animation 内帧推进按 1000/fps 判定，但定时器每 167ms 才触发一次）。
        # 现在周期跟随配置的 frame_delay。
        try:
            self.animation_frame_delay = int(self.animation_frame_delay)
        except (TypeError, ValueError):
            self.animation_frame_delay = int(1000 / max(1, self.animation_fps))
        # 定时器周期取帧间隔的一半：让"帧推进闸门"（update_animation 里的
        # 1000/fps 判定）成为唯一节拍源。若定时器与闸门同周期，Qt 定时器按整数
        # 毫秒触发（如 fps=6 → 166ms < 166.67ms）会让每一帧都被闸门挡掉一次，
        # 实际降到一半帧率且忽快忽慢。
        self._anim_tick_ms = max(16, int(self.animation_frame_delay * 0.5))
        self.animation_timer.start(self._anim_tick_ms)
        
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
        
        # 对话发起定时器（只做"要不要开口"的轮询；真正的频率闸门在
        # start_autonomous_speech 里，10 分钟最多自主开口 1 次）
        self.dialogue_init_timer = QTimer(self)
        self.dialogue_init_timer.timeout.connect(self.check_initiate_dialogue)
        self.dialogue_init_timer.start(15000)

        # 天气播报定时器已移除（第六轮）：定时播报属于"系统自带台词"，
        # 天气信息仍在 _build_ai_context() 里提供给 AI，由 AI 自行决定要不要提。
        self.weather_timer = None
        
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
        self._last_desktop_elements_sig = None  # 上次桌面元素签名，用于增量更新判断
        
        # 创建定时器用于更新占位符位置
        self.placeholder_timer = QTimer(self)
        self.placeholder_timer.timeout.connect(self.update_placeholders)
        self.placeholder_timer.start(3000)  # 每3秒更新一次占位符位置（C10修复：降低频率避免全量重建）
        
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
        
        # C10修复：计算当前桌面元素签名，仅在元素真正变化时才重建占位符
        # 签名格式：元素数量 + 每个元素的x/y/width/height/name拼接
        desktop_elements = self.desktop_interaction.desktop_elements
        sig_parts = [str(len(desktop_elements))]
        for el in desktop_elements:
            sig_parts.append(f"{el.get('x', 0)},{el.get('y', 0)},{el.get('width', 0)},{el.get('height', 0)},{el.get('name', '')}")
        current_sig = "|".join(sig_parts)
        
        if current_sig == self._last_desktop_elements_sig:
            # 桌面元素未变化，跳过重建，避免不必要的销毁/创建 QLabel
            return
        
        # 元素有变化，才重建占位符
        self._last_desktop_elements_sig = current_sig
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
        # 第三十四轮去重：`fall_start_time` 整体删除（6 处写、AST 证实 0 处读的纯死字段）；
        # `is_falling` / `is_recovering` 改由下方"摔倒和恢复状态"区块统一声明（此处不再重复）。
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
        # ===== 唯一真源（第三十四轮合并去重）=====
        # 此前 `is_falling` 在本函数被赋值 3 次（原 L1100/L1158/L1198）、`is_recovering`/`fall_duration`
        # 各 2 次、`max_fall_duration` 2 次（5.0 被更靠后的 2.0 覆盖）。
        # ⚠️ 去重必须**保持运行时等价**：原代码里最后生效的 max_fall_duration 是 2.0
        #    （后赋值胜），所以这里取 2.0 而不是先出现的 5.0 —— 写 5.0 会静默改变行为。
        self.is_falling = False
        self.is_recovering = False
        self.fall_duration = 0.0
        self.max_fall_duration = 2.0
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
        # 重力掉落专属字段（第三十四轮去重）。
        # 原处还重复声明了 is_falling / fall_duration / fall_start_time / max_fall_duration ——
        # 前三个已在上面"摔倒和恢复状态"区块声明（fall_start_time 已整体删除），
        # 此处 max_fall_duration 的 2.0 会覆盖上面的 5.0，语义混乱；现只保留重力掉落独有的三项。
        self.is_gravity_falling = False  # 是否正在重力掉落
        self.fall_speed = 0.0  # 重力掉落速度
        self.fall_start_pos = QPoint(0, 0)  # 重力掉落开始位置
        
        # 空间坐标系统（简化版，只保留基本功能）
        self.spatial_pos = {"x": 0, "y": 0, "z": 0}  # Ralsei的三维空间坐标
        self.current_platform_z = 0  # 当前所在平台的z坐标
        
        # 楼层系统相关变量
        self.current_floor = None  # 当前所在楼层
        self.last_floor_check_time = 0  # 上次楼层检查时间
        self.floor_check_interval = 2.0  # 楼层检查间隔（秒）
        # 性能：楼层检查会全量枚举窗口（win32 跨进程调用，单次可达几十毫秒），
        # 1s 间隔 + nearby 检查让主线程周期性阻塞、鼠标渲染掉帧；2s 间隔配合
        # get_all_visible_windows 的 2s TTL 缓存，主线程枚举频率降一半以上。
        
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
        # 观看循环定时器（W1-4）：由 VideoController._start_video_watching_loop 创建。
        # 在这里**预声明为 None** 是必须的 —— 控制器的 __setattr__ 只把赋值转发给
        # 宿主「已经拥有」的名字；不预声明的话这个属性会落在控制器上，状态被劈成两份。
        self.video_watching_timer = None
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
        # 注意：emotion_system.update() 已在主循环中调用，包含自己的衰减逻辑，这里不再重复衰减

        # 根据环境客观因素调整情绪（统一走新版 emotion_system）
        if self.weather == "sunny":
            self.emotion_system.add_emotion("happy", 0.5)
            self.emotion_system.add_emotion("sad", -0.5)
        elif self.weather == "rainy":
            self.emotion_system.add_emotion("sad", 0.3)
            self.emotion_system.add_emotion("happy", -0.3)

        if self.time_of_day == "night":
            self.emotion_system.add_emotion("tired", 0.5)

        # 根据活动状态调整情绪
        if self.current_activity == "idle":
            self.emotion_system.add_emotion("bored", 0.3)
        elif self.current_activity == "jumping":
            self.emotion_system.add_emotion("excited", 0.5)
        elif self.current_activity == "sleeping":
            self.emotion_system.add_emotion("tired", -0.8)

        # 计算整体心情（从新版情绪系统获取主导情绪）
        dominant, intensity = self.emotion_system.get_current_emotion()
        if dominant == 'happy' and intensity > 20:
            self.mood = "happy"
        elif dominant == 'sad' and intensity > 15:
            self.mood = "sad"
        elif dominant in ('tired', 'exhausted') and intensity > 25:
            self.mood = "tired"
        elif dominant == 'excited' and intensity > 20:
            self.mood = "excited"
        elif dominant == 'bored' and intensity > 20:
            self.mood = "bored"
        else:
            self.mood = "normal"

        # 将新版 emotion_system 同步到旧版 self.emotions 字典（只读兼容）
        self._sync_system_to_emotions()

    def _sync_system_to_emotions(self):
        """将新版 emotion_system 的值同步到旧版 self.emotions 字典（只读兼容）。
        新版范围 -100~100 → 旧版范围 0-100，happy 特殊处理（加 50 并 clamp）。"""
        try:
            es = self.emotion_system
            self.emotions["happiness"] = max(0.0, min(100.0, es.get_emotion_level("happy") + 50.0))
            self.emotions["sadness"] = max(0.0, min(100.0, es.get_emotion_level("sad")))
            self.emotions["anger"] = max(0.0, min(100.0, es.get_emotion_level("angry")))
            self.emotions["fear"] = max(0.0, min(100.0, es.get_emotion_level("fear")))
            self.emotions["surprise"] = max(0.0, min(100.0, es.get_emotion_level("surprised")))
            self.emotions["boredom"] = max(0.0, min(100.0, es.get_emotion_level("bored")))
            self.emotions["tiredness"] = max(0.0, min(100.0, es.get_emotion_level("tired")))
            self.emotions["excitement"] = max(0.0, min(100.0, es.get_emotion_level("excited")))
        except Exception as e:
            _log.debug("情绪同步失败（已忽略）: %s", e)

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
        # "走过去看看某个图标"到达后的收尾：歪头看一眼（一次性，不循环重播）
        if getattr(self, '_pending_look_at_element', False):
            self._pending_look_at_element = False
            for _anim in ("look_up", "curious", "act"):
                if _anim in self.sprite_loader.sprites:
                    self.play_animation_once(_anim, restore_to="idle")
                    break

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
        
        if getattr(self, 'last_movement_end_time', None) is not None:
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
        
        # 获取屏幕几何信息（瞬移防治：用多显示器虚拟桌面矩形，而不是只认主屏的
        # availableGeometry()——副屏上会被夹到主屏坐标系里，表现为"突然被拽走一大段"）
        screen_geometry = self._virtual_screen_rect()
        _bound_left = screen_geometry.x() + 50
        _bound_top = screen_geometry.y() + 50
        sprite_size = int(50 * 2.0)  # 缩放因子为2.0，原始大小约50px
        current_pos = self.pos()
        
        # 计算当前方向，保持方向一致性，减少突然转向
        if getattr(self, 'previous_direction', None) is not None:
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
            target_y = max(_bound_top, current_pos.y() - move_distance)
        elif direction == 'down':
            # 添加横向偏移，使移动路径更自然
            target_x = current_pos.x() + random.randint(-40, 40)
            target_y = min(screen_geometry.y() + screen_geometry.height() - sprite_size,
                           current_pos.y() + move_distance)
        elif direction == 'left':
            # 添加纵向偏移，使移动路径更自然
            target_x = max(_bound_left, current_pos.x() - move_distance)
            target_y = current_pos.y() + random.randint(-40, 40)
        else:  # right
            # 添加纵向偏移，使移动路径更自然
            target_x = min(screen_geometry.x() + screen_geometry.width() - sprite_size,
                           current_pos.x() + move_distance)
            target_y = current_pos.y() + random.randint(-40, 40)
        
        # 保存当前方向，用于下一次移动
        self.previous_direction = direction
        
        # 添加轻微的随机偏移，使移动更自然，但减少范围以避免不稳定
        final_offset_x = random.randint(-10, 10)
        final_offset_y = random.randint(-10, 10)
        
        target_x += final_offset_x
        target_y += final_offset_y
        
        # 确保在屏幕范围内（虚拟桌面坐标系）
        target_x = max(_bound_left, min(target_x, screen_geometry.x() + screen_geometry.width() - sprite_size))
        target_y = max(_bound_top, min(target_y, screen_geometry.y() + screen_geometry.height() - sprite_size))

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
        
    # ------------------------------------------------------------------
    #  场景渲染层（第44轮 P1）—— 相机跟随 + 绘制指令消费
    # ------------------------------------------------------------------
    #: 渲染层总开关。**默认 False** ⇒ 不切场景时零行为变化（P0 判据）不破。
    #  用户裁定「逐章验收」⇒ 由显式开启（或未来的 UI 开关/配置项）来点亮，
    #  而不是一上来就默认接管画面。这同时让"渲染层引入的回归"可被一刀关掉定位。
    SCENE_LAYER_ENABLED = False

    def _pet_target_rect(self, room_rect=None):
        """宠物在**房间世界坐标**里的包围盒 —— 相机的跟随目标（`camera_set_view_target`）。

        ★★★ 为什么必须做「屏幕 → 房间」的归一化映射（第44轮实测教训）
        --------------------------------------------------------------
        最初版本把**窗口屏幕坐标直接当房间世界坐标**。真机一跑就露馅：
        宠物初始位置在 1920×1080 屏的右下角（≈ `(1770, 930)`），而现实世界房间
        只有 320×240 逻辑（×2 = 640×480 像素）—— 目标坐标比房间**大 5 倍**，
        相机第一次 follow 就被钳到房间右下角，之后无论宠物怎么动都**钉死在那**
        （冒烟测试 E2 报红：两次采样完全相同）。这是"输入量级不真实"的典型
        （记忆铁律：「行为判据必须用真实量级输入」）。

        正确映射 = **把屏幕可用区域按比例压进房间世界矩形**：

            屏幕 x ∈ [0, sw]  →  世界 x ∈ [0, room_w]

        这样：
          · 宠物在屏幕正中 → 世界坐标落在房间正中（相机居中，符合原作观感）；
          · 宠物走到屏幕左/右边缘 → 走到房间左/右边缘（相机贴边钳制，
            正是原作"走到地图边缘人物就偏离中心"的表现）；
          · **量级天然正确**（映射值的值域就是房间尺寸，不会溢出）。

        ⚠️ 这仍是一个**产品口径**（原作里人物在世界里走，这里人物在桌面上走），
           不是原作物理。但它满足用户要的观感：「人物走到中间后一直居中，
           然后背景相对运动」——且量级正确、可验证、无自由度。
           将来要更严格（比如"桌面上走 1 像素 = 房间里走 1 逻辑单位"），
           只需改本方法。

        :param room_rect: 房间世界矩形 `(l, t, r, b)`（逻辑坐标）。`None` → 退回旧口径。
        :return: `(l, t, r, b)`；拿不到位置 → `None`（不伪装成 0）。
        """
        try:
            win = self.pos()               # 窗口左上（屏幕坐标）
            w = max(1, self.width())
            h = max(1, self.height())
            cx = win.x() + w / 2.0         # 窗口中心（屏幕坐标）
            cy = win.y() + h / 2.0
            if not room_rect or len(room_rect) != 4:
                # 房间未知 → 旧口径（屏幕坐标当世界坐标）。
                # 只在"退化房间"（= 相机视口大小）时走这里，仍是安全的：
                # 退化房间的尺寸就是相机尺寸，量级基本吻合。
                return (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)
            rl, rt, rr, rb = (float(room_rect[0]), float(room_rect[1]),
                              float(room_rect[2]), float(room_rect[3]))
            rw = max(1.0, rr - rl)
            rh = max(1.0, rb - rt)
            # 屏幕可用区域（虚拟屏，含副屏；用不到时退回主屏）
            sw, sh = self._virtual_screen_size()
            fx = min(1.0, max(0.0, cx / float(sw))) if sw > 0 else 0.5
            fy = min(1.0, max(0.0, cy / float(sh))) if sh > 0 else 0.5
            # 归一化比例 → 房间世界坐标；目标矩形 = 房间内一小块（= 宠物大小映射）
            kx = rw / float(sw) if sw > 0 else 1.0
            ky = rh / float(sh) if sh > 0 else 1.0
            tw = max(1.0, w * kx)
            th = max(1.0, h * ky)
            tcx = rl + rw * fx
            tcy = rt + rh * fy
            return (tcx - tw / 2.0, tcy - th / 2.0, tcx + tw / 2.0, tcy + th / 2.0)
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return None

    def _virtual_screen_size(self):
        """虚拟屏尺寸 `(w, h)`（多屏合并）。取不到 → 主屏；再取不到 → (1920,1080)。

        ★ 必用虚拟屏（`availableGeometry` 只返主屏）—— 与场景系统的
          `_virtual_screen_rect()` 同一条铁律（记忆 §3 契约①）：宠物能跑到副屏，
          只用主屏尺寸会让副屏上的归一化比例算错（>1 → 又被钳死）。
        """
        try:
            rect = self._virtual_screen_rect()
            if rect and len(rect) == 4 and rect[2] > 0 and rect[3] > 0:
                return (rect[2], rect[3])
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        try:
            g = QApplication.desktop().availableGeometry()
            return (max(1, g.width()), max(1, g.height()))
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return (1920, 1080)

    def _update_scene_layer(self):
        """每帧推进渲染层：相机跟随 → 出绘制指令 → 交给画布。

        **失败一律静默**（渲染层不是关键路径，绝不能拖垮移动/对话主循环 ——
        与 search_summarizer / relationship 同一条纪律）。

        为什么每帧都做而不是只在换场景时做：相机是**跟随**相机，
        宠物每移动一像素画面就该相对移动一像素（原作 30fps 硬跟随，
        见 scene_camera 的零缓动说明）。只在换场景时算 = 画面永远静止。
        """
        if not getattr(self, 'SCENE_LAYER_ENABLED', False):
            return
        try:
            canvas = getattr(self, 'scene_canvas', None)
            scene = getattr(self, 'scene', None)
            if canvas is None or scene is None:
                return
            cam = self.__dict__.get('_scene_camera')
            state = self.__dict__.get('_scene_state')
            if cam is None or state is None:
                self._hide_scene_layer()
                return

            # 1) 相机跟随：房间矩形 + 目标矩形（全逻辑坐标，见 scene_camera.scoped_size）
            rooms = self.__dict__.get('_scene_geometry') or {}
            rid = getattr(state, 'original_room_id', None)
            ch = getattr(state, 'chapter_id', None)
            geo = None
            if isinstance(rid, int) and ch:
                rec = rooms.get('%s:%d' % (ch, rid))
                if isinstance(rec, dict) and isinstance(rec.get('w'), int):
                    geo = rec
            if geo:
                room_rect = (0.0, 0.0, float(geo['w']), float(geo['h']))
            else:
                # 房间未知 → 退化为"一屏一房间"（相机不动，画面照常出）
                sz = cam.scoped_size()
                room_rect = (0.0, 0.0, float(sz[0]), float(sz[1]))
            scene.camera_follow(room_rect, self._pet_target_rect(room_rect))

            # 2) 出指令（sprite_size 让剔除用真实素材尺寸 —— 见 SceneAssetCache）
            #    ★ 动效（第44轮续）：tick 传**毫秒时间戳**，渲染层据此按原作速度
            #      （30fps × GMS2PlaybackSpeed）取 sprite 当前帧。传墙钟时间而
            #      不是帧计数器 —— 理由见 scene_render._anim_frame_index 的长注释
            #      （负载抖动不该改变动画速度）。
            plan = scene.plan_frame(sprite_size=canvas.assets.sprite_size,
                                    tick=int(time.time() * 1000))
            # 3) 交给画布（画布自己 resize + update）。
            #    画布尺寸用 `plan_viewport()`（= 收缩后的小房间尺寸 / 大房间的相机尺寸），
            #    而不是相机原始尺寸 —— 小房间要收缩，否则房间只占中间一块
            #    （与用户「房间放大些」的意图相反，见 scene_render.viewport_size）。
            view = scene.plan_viewport()
            canvas.set_plan(plan, view)

            # 4) 有 bg 或物件才显示画布；纯占位/空 → 隐藏（保持桌面原样）
            if plan and any(it.get('kind') in ('bg', 'obj') for it in plan):
                self._show_scene_layer()
            else:
                self._hide_scene_layer()
        except Exception as e:
            _log.debug("场景渲染层更新失败（本帧跳过）: %s", e)

    def _show_scene_layer(self):
        """显示场景画布（并把它压到精灵之下 —— 场景是背景层）。"""
        try:
            canvas = self.scene_canvas
            if not canvas.isVisible():
                canvas.show()
                self._scene_layer_visible = True
            canvas.lower()   # 背景层：永远在 sprite_label 之下
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)

    def _hide_scene_layer(self):
        """隐藏场景画布（桌面场景 / 场景系统不可用时）。"""
        try:
            canvas = self.scene_canvas
            if canvas.isVisible():
                canvas.hide()
            self._scene_layer_visible = False
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)

    # 移动相关代码 - 更新移动逻辑
    @monitor_performance
    def update_movement(self):
        # 更新位置，改进运动逻辑，结合真实物理系统
        import math
        # 计算实际经过的时间
        current_time = time.time()
        elapsed_time = current_time - self.last_update_time
        self.last_update_time = current_time
        # dt 截断（瞬移防治）：本函数内部会做窗口枚举（check_window_movement →
        # floor_manager.update_floors）、COM 调用等**可能阻塞主线程**的动作，阻塞耗时会被
        # 计入下一个 tick 的 elapsed_time。而位移普遍写成 `速度 × dt`（重力掉落更是
        # `速度 += g*dt` 后再 `× dt`，对 dt 呈二次放大），一旦 dt 变成 1~2 秒，
        # 宠物就会"啪"地跳出去一大段——这就是用户看到的偶发瞬移。
        # 上限 0.1s（约 10FPS 的容差）：正常 tick 30ms 不受影响，异常长 tick 只按 100ms 结算。
        if not isinstance(elapsed_time, (int, float)) or elapsed_time < 0:
            elapsed_time = 0.0
        elif elapsed_time > 0.1:
            elapsed_time = 0.1
        
        # 优化：减少环境和心情更新频率（每5秒更新一次）
        if getattr(self, '_last_env_update', None) is not None:
            if current_time - self._last_env_update > 5.0:
                self.update_environment()
                self.update_mood()
                self._last_env_update = current_time
        else:
            self.update_environment()
            self.update_mood()
            self._last_env_update = current_time

        # ---- 场景渲染层（第44轮 P1）：相机跟随 + 绘制指令消费 ----
        # 挂在这里而不是 update_animation(100ms)：原作相机是 **30fps 硬跟随**
        # （`GMS2FPS = 30`，见 scene_camera 的零缓动说明），本定时器正好 30ms。
        # 挂在动画定时器上会让相机以 10fps 跟随 —— 画面"一跳一跳"，与原作不符。
        # ⚠️ 由 `SCENE_LAYER_ENABLED`（默认 False）总控；关闭时本调用**立即返回**，
        #    P0「不切场景时零行为变化」的判据不受任何影响。
        self._update_scene_layer()
        
        # 低频检查附近的桌面元素（每5秒一次；修复：此前 check_nearby_desktop_elements
        # 从未被调用，Ralsei 对桌面文件夹/文件的"靠近反应"从未触发）
        # 修复：时间戳更新放在 try 外——原来在 try 内，若 check_* 抛错则时间戳不更新，
        # 每 30ms 全量重试（性能热循环）。
        # 性能：get_nearby_elements 内部会全量枚举窗口（现已有缓存），5s 节拍足够，
        # 避免主线程频繁被窗口枚举拖慢。
        # 第三十四轮续修复（F34-1）：时间戳必须**只在真正执行检查后**才推进。
        # 原写法把 `self._last_desktop_elem_check = current_time` 放在 try 之外无条件执行，
        # 于是时间戳每 tick（30ms）都被刷新 ⇒ `current_time - _last_... > 5.0` 除首次外
        # 永远为假 ⇒ check_nearby_desktop_elements 一生只跑一次（"靠近桌面元素做出反应"
        # 实际从不发生，连带 _note_desktop_observation 从不入 AI 事件队列）。
        # 现改为与 `_last_env_update` / `last_floor_check_time` 同一口径：赋值落在 if 块内。
        # 抛错时不推进时间戳（保留原"防热循环"诉求的替代实现：下一次 tick 重试一次即可，
        # 因为节拍判据本身要求距上次成功检查满 5 秒）。
        try:
            if not hasattr(self, '_last_desktop_elem_check') or current_time - self._last_desktop_elem_check > 5.0:
                self.check_nearby_desktop_elements()
                self._last_desktop_elem_check = current_time
        except Exception as e:
            _log.warning(f"check_nearby_desktop_elements 异常: {e}")
        
        # 睡眠状态处理
        if self.is_sleeping:
            self.current_activity = "sleeping"
            # 修复：人被叫醒时不会立刻清醒，应该迷迷糊糊的。
            # 第一次互动：翻身哼哼（groggy），不立刻醒；
            # 5秒内第二次互动：才完全醒来。超过5秒没再互动就继续睡。
            if current_time - self.last_interaction_time < 1.0:
                if not hasattr(self, '_sleep_stir_time'):
                    # 第一次被吵醒：哼哼唧唧翻个身，但还没醒
                    self._sleep_stir_time = current_time
                    self._sleep_stir_count = 1
                    try:
                        self.play_animation_once("look_up")
                    except Exception:
                        pass
                    stir_msgs = ["唔...别吵...", "嗯...再睡五分钟...", "zzz...别闹..."]
                    self.dialogue_ui.add_dialogue("ralsei", random.choice(stir_msgs), "sleepy")
                    self.dialogue_ui.show_dialogue()
                elif (current_time - self._sleep_stir_time < 5.0
                      and getattr(self, '_sleep_stir_count', 0) == 1):
                    # 5秒内第二次被吵：才真正醒来
                    self._sleep_stir_count = 2
                    self.wake_up()
            elif hasattr(self, '_sleep_stir_time') and current_time - self._sleep_stir_time > 5.0:
                # 超过5秒没再被吵，翻个身继续睡
                if hasattr(self, '_sleep_stir_time'):
                    delattr(self, '_sleep_stir_time')
                if hasattr(self, '_sleep_stir_count'):
                    delattr(self, '_sleep_stir_count')
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
                # 渲染层序（"一层压一层"）：宠物插在"所站楼板之上、其余窗口之下"。
                # 与楼层检查同节拍刷新；放在这里而不是 check_window_movement 里面，
                # 是因为 z 序属渲染关注点，且回归套件会直接调 check_window_movement
                # （把副作用塞进去会让那些 stub 突然多出一个不存在的依赖）。
                if not self.is_jumping and not self.is_falling \
                        and not getattr(self, 'is_gravity_falling', False):
                    self._apply_pet_z_order()
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
            # （第六轮已移除"拖拽桌面元素玩耍"的内部状态清理：该行为已改为
            #   "走过去看看某个图标"，不再维护 dragging_element / dragging_type）

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
        # ===== 空中接住的缓冲减速（必须在拖拽保护之前推进）=====
        # 用户要求"要有一个针对他当时线速度的减速效果，而不是撞上一堵墙毫无缓冲"。
        if getattr(self, '_catch_brake', None) is not None:
            try:
                self._tick_catch_brake(elapsed_time)
            except Exception as e:
                _log.warning(f"缓冲减速推进异常: {e}")
                self._catch_brake = None

        # ===== 特殊动画播放期：不移动 =====
        # 用户要求（第八轮）："……不要出现边播放边移动这种情况（注意，只针对特殊动画）"。
        # 放在"拖拽保护/鼠标拖动/跟随"之前：这些分支都会直接 self.move(...) 然后 return，
        # 不拦住就会出现"一边摆手一边平移"。只暂停本 tick 的移动，**不清掉跟随意图**，
        # 动画播完后照常继续跟。（物理/施法/躲猫猫在上面已提前 return，不受影响。）
        if self._special_anim_locked():
            self.current_speed_x = 0
            self.current_speed_y = 0
            self.current_activity = "performing"
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
                # 瞬移防治：改走多显示器虚拟桌面夹紧（原写法把原点钉在 (0,0)、只认主屏）
                new_x, new_y = self._clamp_pos_to_desktop(new_x, new_y)
                
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
        
        # 主动"去看看某个桌面图标"（第六轮改：不再假装搬动用户的文件）
        # 原条件 `random()<0.005` 在 30ms 定时器每帧判定（≈每 6 秒一次），且不检查
        # 是否空闲/是否正被用户拖拽——走路中被它打断、用户拖动时鼠标被 SetCursorPos 抢走。
        # 现在：仅空闲时 + 距上次 >90 秒 + 无 spell/游戏/被拖拽。
        if (not self.is_moving
                and getattr(self, '_spell_stage', None) is None
                and not getattr(self, 'game_state', {}).get('is_playing')
                and not getattr(self, '_is_being_dragged', False)
                and time.time() - getattr(self, '_last_dragging_play_time', 0.0) > 90.0
                and random.random() < 0.002):
            self._last_dragging_play_time = time.time()
            self.start_dragging_play()
        
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
            if getattr(self, '_cached_screen_geom', None) is not None:
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
        # 修复：禁用——Ralsei 不会主动去抢用户的鼠标控制权。
        # 原代码15%概率调用 SetCursorPos 移动用户光标，会打断用户正在做的事，
        # 这是非常冒犯的行为。人不会去抢别人的鼠标，宠物也不该。
        # 保留方法签名避免调用方报错，但内部什么都不做。
        return
    
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
    
    
    

    # ------------------------------------------------------------------
    # 建楼：以 floor_manager 为唯一真源的跳跃规划（第十四轮接线）
    # ------------------------------------------------------------------
    # 为什么要有这一段
    # ----------------
    # 第十三轮把 floor_manager 里的判据全换成了"可见区域"，
    # `get_jump_destinations` / `floor_visible_contains` 都改对了 ——
    # 但**产品一个都没调用**：真正决定跳不跳、跳去哪的还是下面 `check_nearby_windows`
    # 里那套"裸窗口矩形 + 10~30px 贴边"的老启发式。于是两条要求实际没生效：
    #   ① "向上跳只能跳到该窗口**没被挡住**的那部分边缘上" —— 老逻辑不看可见区域；
    #   ② "向下跳必须先到相邻下一层，不能穿透" —— 老逻辑站在窗口上时直接把目标
    #      声明成**桌面**，等于从 3 楼朝 1 楼跳（`handle_jump` 的穿透检查会把它
    #      打断成"取消跳跃 + 自由落体"，观感是硬着陆，不是要求里的"先跳到2楼"）。
    # 这一段的职责就是把这套判定接进产品路径。
    # 第十五轮：`check_nearby_windows` 里那套老启发式**已整体删除**，
    # 楼层系统成为跳跃的唯一入口（详见该函数内的注释）。

    def _floors_for_jump(self):
        """可用的楼层系统；不可用（无可见窗口 / 单测桩）时返回 None。

        第十五轮起调用方不再"回落旧逻辑"—— `check_nearby_windows` 拿到 None
        就什么都不做（floors 空 ⟺ 一个可跳的楼板都没有）。
        """
        fm = getattr(self, 'floor_manager', None)
        if fm is None or not getattr(fm, 'floors', None):
            return None
        return fm

    def _visible_landing(self, fm, floor, pos):
        """把落点收进该楼层的可见区域（薄封装，统一走 floor_manager 的几何）。"""
        try:
            return fm.nearest_visible_point(floor, pos)
        except Exception:
            return None

    def _floor_entry_plan(self, fm, floor, ralsei_rect, cur_floor=None):
        """从宠物当前所在的一侧"进入"某块楼板：返回 (edge, 落点) 或 None。

        把老启发式的四条边（上/下/左/右）保留下来 —— 那是"贴着边才跳"的触感来源，
        宠物只有真的贴到某块楼板边上才会起跳；但**几何全部换成楼层的权威矩形**，
        并且落点必须落在该楼层的**可见区域**里（看不见的部分跳不上去）。
        """
        rect = floor.get('rect')
        if rect is None or rect.width() <= 0 or rect.height() <= 0:
            return None

        # 目标层是桌面（1楼）：桌面是一片无边的大地，"从哪条边进入"没有意义。
        # 规则与旧逻辑同源（"从窗口底边跳回桌面"），但落点改成"当前楼板下沿之下一小段"，
        # 而不是旧代码里会落到屏幕最底的那条分支。
        if floor.get('type') == 'desktop':
            slab = (cur_floor or {}).get('rect')
            if slab is None:
                return None
            gap = ralsei_rect.bottom() - slab.bottom()   # >=0 = 宠物已探出下沿
            if not (-20 <= gap <= 60):
                return None
            land = QPoint(ralsei_rect.center().x(), slab.bottom() + 20)
            land = self._visible_landing(fm, floor, land)
            if land is None:
                return None
            return "down", land

        # 目标楼板横向/纵向的"内容区间"（留 20px 内缩，别贴死角上）
        span_ok_x = (ralsei_rect.center().x() > rect.left() + 20
                     and ralsei_rect.center().x() < rect.right() - 20)
        span_ok_y = (ralsei_rect.center().y() > rect.top() + 20
                     and ralsei_rect.center().y() < rect.bottom() - 20)

        # 宠物在目标楼板的哪一侧（相隔距离用"最近边"衡量，<=60px 才算贴边）
        NEAR = 60
        gap_top = rect.top() - ralsei_rect.bottom()          # >0 = 宠物在楼板上方
        gap_bottom = ralsei_rect.top() - rect.bottom()       # >0 = 宠物在楼板下方
        gap_left = rect.left() - ralsei_rect.right()         # >0 = 宠物在楼板左侧
        gap_right = ralsei_rect.left() - rect.right()        # >0 = 宠物在楼板右侧

        edge, land = None, None
        if -20 <= gap_top <= NEAR and span_ok_x:
            # 从上方进入：站在楼板**上边缘之内**（与 get_drop_destination 落地口径一致）
            edge, land = "bottom", QPoint(ralsei_rect.center().x(), rect.top() + 10)
        elif -20 <= gap_left <= NEAR and span_ok_y:
            edge, land = "left", QPoint(rect.left() + 10, ralsei_rect.center().y())
        elif -20 <= gap_right <= NEAR and span_ok_y:
            edge, land = "right", QPoint(rect.right() - self.width() - 10,
                                        ralsei_rect.center().y())
        elif -20 <= gap_bottom <= NEAR and span_ok_x:
            edge, land = "top", QPoint(ralsei_rect.center().x(),
                                       rect.bottom() - self.height() - 10)
        if edge is None:
            return None

        land = self._visible_landing(fm, floor, land)
        if land is None:
            return None
        # 吸附后如果被推得太远（可见部分离宠物十万八千里），这次跳跃不成立 ——
        # 要求里"只能跳到没被挡住的那部分边缘上"，而不是"跳到同一层的另一个角落"。
        if abs(land.x() - ralsei_rect.center().x()) > 200 \
                or abs(land.y() - ralsei_rect.center().y()) > 200:
            return None
        return edge, land

    def _nearest_floor_jump(self, fm, cur_floor, ralsei_rect):
        """这一拍可执行的楼层跳跃：返回 (目标楼层, edge, 落点) 或 None。

        候选来自 `floor_manager.get_jump_destinations`（唯一真源）：
          · 比当前楼板**更高**的楼层 —— 落点已由楼层侧按可见区域给到；
          · **相邻的下层** —— 逐层，不穿透（要求："必须先跳到2楼"）。
        再按"进入边 + 贴边距离"筛选，取最近的一个。
        """
        cur_pos = ralsei_rect.topLeft()
        try:
            cands = fm.get_jump_destinations(cur_floor, cur_pos)
        except Exception:
            return None
        cur_id = self._floor_identity_key(cur_floor)

        candidates = [f for f, _pos in cands
                      if self._floor_identity_key(f) != cur_id]

        # 向下：**显式**取相邻下一层，而不是从 get_jump_destinations 的结果里"顺便拿"。
        # 原因：那里会按"宠物 x 是否落在该层横向范围内"过滤，而"走到楼板边缘、
        # 半个身子探出去"恰恰就是 x 已经出了范围的那种情形 —— 会被漏掉。
        # 建楼要求明写"向下必须先跳到相邻的下一层"，这条不能靠副作用满足。
        down = fm.adjacent_lower_floor(cur_floor)
        if down is not None and self._floor_identity_key(down) != cur_id:
            known = {self._floor_identity_key(f) for f in candidates}
            if self._floor_identity_key(down) not in known:
                candidates.append(down)

        best = None
        for floor in candidates:
            plan = self._floor_entry_plan(fm, floor, ralsei_rect, cur_floor)
            if plan is None:
                continue
            edge, land = plan
            d = (abs(land.x() - ralsei_rect.center().x())
                 + abs(land.y() - ralsei_rect.center().y()))
            if best is None or d < best[0]:
                best = (d, floor, edge, land)
        if best is None:
            return None
        return best[1], best[2], best[3]

    def _start_floor_jump(self, floor, edge, land):
        """按楼层目标起跳（落点由楼层可见区域给出）。"""
        target_window = None
        if floor.get('type') == 'window':
            w = floor.get('window') or {}
            rect = w.get('rect')
            target_window = {
                'hwnd': w.get('hwnd'),
                'title': w.get('title', ''),
                'x': rect.x() if rect is not None else floor['rect'].x(),
                'y': rect.y() if rect is not None else floor['rect'].y(),
                'width': rect.width() if rect is not None else floor['rect'].width(),
                'height': rect.height() if rect is not None else floor['rect'].height(),
                'z_order': w.get('z_order', 0),
            }
        self.start_jump(target_window, edge, target_floor=floor, target_pos=land)

    # ------------------------------------------------------------------
    # 「建楼」批次 B（第十八轮）：层高闸门 —— "自己走出来的换层必须靠跳/攀爬"
    # ------------------------------------------------------------------
    # 用户口径见 main.py 头部 CLIMB_* 常量那一段。这里只放三块零件：
    #   · _climb_hdir              —— 往哪边让开（决定"预留水平距离"的方向）
    #   · _climb_probe_landing     —— 候选落点吸附进可见区域并校验
    #   · _climb_landing           —— 定落点 + 定爬向
    #   · _start_climb_transition  —— 真的起跳；返回 False = 够不着（调用方兜底）
    # 选择"跳还是爬"不在这里，而在 start_jump（它同时看得到起跳层与目标层，
    # 两条入口共用一份判据，见那里 `_jump_kind_for_span`）。
    def _climb_hdir(self, fm, target_floor):
        """让开的方向：优先沿用宠物当前朝向（走路的延续），否则按目标层的几何。"""
        prev = getattr(self, 'previous_direction', None)
        if prev in ('left', 'right'):
            return 1 if prev == 'right' else -1
        try:
            t_rect = (target_floor or {}).get('rect')
            if t_rect is not None and t_rect.center().x() >= self.pos().x():
                return 1
            if t_rect is not None:
                return -1
        except Exception as e:
            _log.debug("攀爬方向判定失败（默认向右）: %s", e)
        return 1

    def _climb_probe_landing(self, fm, target_floor, probe, cur):
        """把候选落点吸附进目标层的**可见区域**并校验"够不够得着"。

        要求原文："它只能跳到这个浏览器窗口没被其他东西挡住的那部分边缘上。"
        返回 None = 这次候选不成立（看不见 / 被推得太远）。
        """
        try:
            land = fm.nearest_visible_point(target_floor, probe)
            if land is None:
                land = fm.nearest_visible_point(target_floor, cur)
        except Exception as e:
            _log.debug("落点吸附失败（放弃本次衔接）: %s", e)
            return None
        if land is None:
            return None
        try:
            if not fm.floor_visible_contains(target_floor, land):
                return None
        except Exception as e:
            _log.debug("可见区域校验失败（放弃本次衔接）: %s", e)
            return None
        if (abs(land.x() - cur.x()) > CLIMB_LANDING_MAX_TRAVEL
                or abs(land.y() - cur.y()) > CLIMB_LANDING_MAX_TRAVEL):
            return None
        return land

    def _climb_landing(self, fm, target_floor):
        """定落点 + 定爬向。返回 (落点, 方向) 或 (None, None)。

        为什么要"先让开再吸附"（用户第十八轮）：
          "要预留一定距离哦，别看着和垂直起跳一样" —— 直接取正上方/正下方会让
          衔接看着像垂直弹跳；先在水平方向让开 `CLIMB_HORIZONTAL_RUN` 再吸附进可见
          区域，观感就是"斜着爬/跳过去"。吸附有可能把位移吃掉（目标层可见区域刚好
          在那一侧很窄），所以两个方向各试一次，取"位移更大"的那个。
        """
        cur = self.pos()
        primary = self._climb_hdir(fm, target_floor)
        best = None
        for hdir in (primary, -primary):
            probe = QPoint(cur.x() + hdir * CLIMB_HORIZONTAL_RUN, cur.y())
            land = self._climb_probe_landing(fm, target_floor, probe, cur)
            if land is None:
                continue
            dx = abs(land.x() - cur.x())
            key = (dx >= CLIMB_MIN_RESERVE, dx)      # 先要"留够距离"，其次越大越好
            if best is None or key > best[0]:
                best = (key, land)
        if best is None:
            return None, None
        land = best[1]
        return land, _jump_hdir_for(cur, land)

    def _start_climb_transition(self, old_floor, new_floor):
        """层高闸门：把"宠物自己走出来"的高低变换交给跳/攀爬衔接。True = 已起跳。

        用户口径："走进更低的楼层也是一样，反正只要是楼层高低变换就要通过跳来衔接，
        注意，下楼的时候别用掉落，也用跳"—— 所以上下行都走这里，**不走** `start_falling`。

        返回 False = 目标楼板够不着（吸附后被推得太远 / 不可见）→ 由调用方兜底：
        · 上楼够不着 → 保持原楼层（"静默提升"是复检缺口 G3 本身，不能留着当兜底）；
        · 下楼够不着 → 服从重力（要求⑭："脚下没东西了就该直直掉下去"）。

        ---- 为什么**不**把"跨度高"拆成逐层小跳（勿回退，第十八轮实测推理）----
        用户还说过"他也不能一次性跳上跨度很高的楼层……只能相邻"。直觉做法是把一次
        跨层拆成"先跳到隔壁那层、再跳下一层"。**在这套几何下这样做会卡死**：
        楼层名次就是 z 序，宠物之所以会被判到第 N 层，正因为它的位置落在**最前面**
        那块楼板的可见区域里 —— 而那正是"后面的第 N-1、N-2 层被它挡住"的地方，
        中间层在这个位置上**没有可见区域**。于是"逐层"的第一步就会吸附失败
        （`_climb_probe_landing` 的 `floor_visible_contains` 过不去）→ 每一步都
        返回 False → 宠物永远上不去，"静默提升"没了、换成"进不去窗口"，
        比原来更糟。所以这里对跨越采用：**换素材不换落点**
        —— 跨度 > 一层时用 `climb_*` 攀爬动画（`start_jump` 按跨度单点决定），
        落点仍取目标层的可见区域，并用 `CLIMB_LANDING_MAX_TRAVEL` 卡住位移上限，
        从观感上就是"爬上去"而不是"一步蹦到顶层"。
        如果以后要真做逐层攀爬，先解决"中间层被遮挡时怎么落脚"，再动这里。
        """
        fm = getattr(self, 'floor_manager', None)
        if fm is None:
            return False
        land, direction = self._climb_landing(fm, new_floor)
        if land is None:
            return False
        span = ((new_floor.get('platform_height', 0) or 0)
                - (old_floor.get('platform_height', 0) or 0))
        # 起跳：沿用第十/十四轮的楼层跳跃链路（目标楼层 + 由可见区域给出的落点）。
        # "跳还是爬"由 start_jump 按跨度单点决定（它同时看得到起跳层与目标层）。
        self._start_floor_jump(new_floor, 'bottom' if span > 0 else 'top', land)
        _log.debug("层高闸门：%s → %s（跨度 %s，%s，爬向 %s，落点 %s）",
                   old_floor.get('platform_height'), new_floor.get('platform_height'),
                   span, _jump_kind_for_span(span), direction, land)
        return True

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

        # ===== 建楼：跳跃决策**只**由楼层系统回答 =====
        # 判据全部来自 floor_manager：可见区域（"只能跳到没被挡住的那部分边缘"）
        # ＋ 相邻下层（"向下必须先到2楼"）。
        # 第十五轮：原来这里下面是**两条**路 —— 楼层不可用时回落到"裸窗口矩形 +
        # 10~30px 贴边"的老启发式。那条路是第十三轮口径错误的旧路（会跳到被挡住的部分、
        # 站在窗口上时把目标直接声明成桌面 = 穿透），已整体删除。
        # 现在只有一条路：**没有楼层 = 没有可跳的楼板**（floors 空 ⟺ 一个可见窗口都没有），
        # 直接返回。旧启发式在"无楼层"时本来也无对象可枚举，删掉不改变行为。
        ralsei_rect = QRect(current_pos.x(), current_pos.y(), self.width(), self.height())
        fm = self._floors_for_jump()
        if fm is None:
            return
        cur_floor = getattr(self, 'current_floor', None) or fm.desktop_floor
        plan = self._nearest_floor_jump(fm, cur_floor, ralsei_rect)
        if plan is not None:
            self._start_floor_jump(*plan)

    def start_jump(self, target_window, window_edge, target_floor=None, target_pos=None):
        """开始跳跃。

        参数（第十四轮新增后两个）：
          · `target_window` —— 目标**窗口**（裸 dict，沿用历史调用）；跳桌面传 None。
          · `window_edge`   —— 进入目标楼板的那条边（"bottom"/"left"/"right"/"top"/
                               "down"/"up"），只影响落点启发式与日志。
          · `target_floor`  —— **目标楼层**（floor_manager 的权威对象）。给了就用它，
                               不再从裸窗口反查；这是"唯一真源"要求下的正路。
          · `target_pos`    —— **落点**（已经由调用方按可见区域选定）。给了就用它，
                               跳过下面那套"从裸窗口矩形推落点"的启发式。
        """
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
        if target_floor is not None:
            # 楼层系统给出的目标：唯一权威编号（有效楼层名次，最前=最高）
            self.jump_target_z = target_floor.get('platform_height', 0)
        elif target_window:
            # 跳上窗口：用**楼层**的 platform_height 作为目标Z坐标。
            # 修复（第十三轮）：原来读的是裸窗口 dict 的 platform_height —— 那是
            # desktop_interaction 里的第二套编号口径（与 floor_manager 方向相反），
            # 已删除以免两套编号打架；现在唯一权威是楼层（有效楼层名次，最前=最高）。
            _tf = self.floor_manager.get_floor_by_window(target_window['hwnd'])
            self.jump_target_z = _tf['platform_height'] if _tf else 0
        else:
            # 跳到桌面，Z坐标为0
            self.jump_target_z = 0
        
        # 计算跳跃的Z轴高度差
        self.jump_z_diff = self.jump_target_z - self.jump_start_spatial['z']
        
        # 设置目标楼层，用于跳跃过程中的穿透检查
        self.jump_target_floor = None
        if target_floor is not None:
            self.jump_target_floor = target_floor
        elif target_window:
            # 查找目标窗口对应的楼层
            self.jump_target_floor = self.floor_manager.get_floor_by_window(target_window['hwnd'])
        else:
            # 跳到桌面，目标楼层为桌面
            self.jump_target_floor = self.floor_manager.desktop_floor

        # ===== 「建楼」批次 B（第十八轮）：按**跨度**选衔接动画 =====
        # 用户口径："在楼层跨度较低的时候跳，跨度高的时候爬"。
        # 判据只写这一处：本方法同时看得到"起跳前站在哪层"与"要跳到哪层"，而两个入口
        # （`_start_climb_transition` 的层高闸门 / `check_nearby_windows` 的贴边起跳）
        # 都会走到这里 —— 各写一份必然漂移（本项目反复踩的双真源坑）。
        # 用**模块级**函数而不是类方法：历史回归套件用轻量桩驱动 `RalseiPet.start_jump`，
        # 桩上不该再多一个要补转发的方法（第十七轮实测过这个坑）。
        self._jump_anim_override = None
        try:
            _cur_floor = getattr(self, 'current_floor', None)
            _tgt_floor = getattr(self, 'jump_target_floor', None)
            if _cur_floor is not None and _tgt_floor is not None:
                _span = ((_tgt_floor.get('platform_height', 0) or 0)
                         - (_cur_floor.get('platform_height', 0) or 0))
                if _jump_kind_for_span(_span) == 'climb':
                    # 跨度大 → 用攀爬素材（没有素材时 _climb_animation_name 返回 None，
                    # 自动回落下面的 jump 家族，不会切到不存在的动画）
                    self._jump_anim_override = _climb_animation_name(
                        self, _jump_hdir_for(self.jump_start_pos, target_pos))
        except Exception as e:
            _log.debug("跳跃动画选型失败（按 jump 家族处理）: %s", e)

        # 开始跳跃准备阶段
        self.jump_phase = "ready"
        # 强制切换到跳跃动画（跨度大时用攀爬素材替代）
        # 第三十四轮（用户口径）："跳跃这种动画统一用 jump_ball 代替，只有摔下去的时候
        # 用原来的" —— 起跳准备帧也从 `jump_ready` 改为 `jump_ball`，让整个跳跃过程
        # 只有一种素材（此前 ready 帧是 jump_ready、jumping 帧是 jump，两段不一致）。
        # 攀爬素材（`_jump_anim_override`）不受影响：那是"跨度大"这条独立机制的选型。
        self.change_animation(self._jump_anim_override or "jump_ball", force=True)
        
        # 更新跳跃时间
        self.last_jump_time = time.time()
        
        # 调整跳跃次数和休息逻辑
        # 当返回较低平台时，减少跳跃次数计数
        # 修复（第十四轮）：原来用裸窗口的 z_order 比大小，而"两个都是 None
        # （从桌面跳到桌面）"或"裸 dict 口径与楼层口径不一致"时会算错方向。
        # 改以**楼层编号**判方向（唯一真源），没有楼层可比时退回旧的 z_order 判据。
        _cur_floor = getattr(self, 'current_floor', None)
        if target_floor is not None and _cur_floor is not None:
            if target_floor.get('platform_height', 0) < _cur_floor.get('platform_height', 0):
                self.jump_count = max(0, self.jump_count - 1)   # 往下走，减计数
            else:
                self.jump_count += 1                            # 往上走，加计数
        elif self.current_window and target_window:
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
        if target_pos is not None:
            # 落点已由调用方按**目标楼层的可见区域**选定（建楼要求：只能跳到
            # 没被挡住的那部分边缘）。这里只做屏幕夹紧，绝不重新按裸窗口矩形推落点 ——
            # 那正是会落到"看不见的地板"上的老路。
            target_x, target_y = self._clamp_pos_to_desktop(target_pos.x(), target_pos.y())
        elif target_window:
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
            # 瞬移防治：着陆点按"Ralsei 所在的那块屏"算，避免副屏上被拉回主屏坐标
            desktop_edge = window_edge
            screen_geometry = self._current_screen_rect()
            _sg_left = screen_geometry.x() + 20
            _sg_right = screen_geometry.x() + screen_geometry.width() - self.width() - 20

            # 从窗口边缘跳到桌面，计算合适的着陆位置
            # 修复：check_nearby_windows 对"窗口顶部边缘"设置 jump_desktop_edge="up"，
            # 这里原来只匹配 "top"，导致从窗口顶跳回桌面落入 else 直接瞬移到屏幕底部。
            if desktop_edge in ("top", "up"):
                # 从窗口顶部跳到桌面下方
                target_x = self.jump_start_pos.x()
                # 确保x坐标在屏幕范围内
                target_x = max(_sg_left, min(_sg_right, target_x))
                target_y = self.jump_start_pos.y() + 50  # 从窗口顶部往下跳50像素，减少瞬移效果
            elif desktop_edge == "left" or desktop_edge == "right":
                # 从窗口侧面跳到桌面
                target_x = self.jump_start_pos.x()
                target_y = self.jump_start_pos.y()
            elif desktop_edge == "down":
                # 修复：从窗口底边跳回桌面——原代码把 "down" 落入 else 算到屏幕最底部，
                # 造成"在窗口底边起跳却落到屏幕底"的跨屏远跳。这里落在窗口下方一小段。
                target_x = self.jump_start_pos.x()
                target_x = max(_sg_left, min(_sg_right, target_x))
                target_y = self.jump_start_pos.y() + 50
            else:
                # 默认情况：从窗口下方跳到桌面
                target_x = self.jump_start_pos.x()
                target_y = screen_geometry.y() + screen_geometry.height() - self.height() - 20  # 桌面底部上方

        # 确保目标位置在屏幕范围内（虚拟桌面坐标系）
        target_x, target_y = self._clamp_pos_to_desktop(target_x, target_y)
        
        # 更新跳跃目标位置
        self.jump_target_pos = QPoint(target_x, target_y)

    def start_falling(self, fall_velocity=0, is_thrown=False, reason=None):
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
        self.fall_start_pos = self.pos()
        # 修复（状态互斥）：见 start_fall 注释——两种坠落状态同时为真会让
        # handle_fall 的分阶段流程被 handle_gravity_fall 顶掉，宠物卡在动画里。
        self.is_falling = False
        self.is_splat = False
        self._fall_velocity = fall_velocity  # 记录摔落时的速度（用于判断是否甩飞）
        self._is_thrown = is_thrown  # 是否是被甩飞的
        # 第十四轮：记录这次坠落的**起因**。建楼要求第36行：
        #   "摔到桌面上的动画用的还是咱之前那个，但如果是我的行为导致他摔到桌面上的
        #     那就用生气的那个，这两个动画持续至少5s。"
        # 只有"用户把脚下的楼板抽走/关掉窗口"才算用户行为（reason='floor_removed'）；
        # 自己走到边缘掉下去、跳跃被判穿透，都算自己的问题，走常规动画。
        self._fall_reason = reason
        # 批次 B（第十八轮）：记下"从多高掉下来的"。落地时 `_should_splat_on_landing`
        # 用它算落差 —— 用户口径："摔扁只在**层数比较高**且掉下来而非主动下来时触发"。
        try:
            self._fall_from_height = int(
                (getattr(self, 'current_floor', None) or {}).get('platform_height', 0) or 0)
        except Exception:
            self._fall_from_height = 0
        # 第十六轮复检：这里原来写的是 `max_fall_duration` —— 那是**死参数**：全项目
        # 只有 handle_fall 读它，而本函数把 `is_falling` 置 False（坠落期间走
        # handle_gravity_fall）→ 永远读不到，于是"关窗掉下来生气至少 5s"从未生效。
        # 第十七轮定稿：时长不再另存实例属性，由 `_fall_reason` **纯派生**
        # （`_fall_splat_hold`），避免双真源。
        # 水平惯性：掉落时保留当前水平速度，形成2D抛物线坠落
        self.fall_velocity_x = self.current_speed_x * 0.5

        # 根据"起因 / 摔落速度"选择不同的动画
        if reason == 'floor_removed':
            # 用户抽走了脚下的楼板（关窗 / 移窗没跟上）→ 生气的那组，至少 5s
            if "fall_mad" in self.sprite_loader.sprites:
                self.change_animation("fall_mad", force=True)
            else:
                self.change_animation("fall", force=True)
        elif fall_velocity > 100 or is_thrown:
            # 高速摔落或被甩飞时，使用splat动画
            self.change_animation("fall", force=True)
        else:
            # 普通摔落时，使用常规掉落动画
            self.change_animation("fall", force=True)
        
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
            self._jump_anim_override = None
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
        # 楼层身份统一走 _floor_identity_key（稳定标识：窗口 hwnd / 'desktop'），
        # 绝不能用 floor dict 的内容比较——floors 每秒由 update_floors 整体重建。
        cur_fid = self._floor_identity_key(getattr(self, 'current_floor', None))
        tgt_fid = self._floor_identity_key(getattr(self, 'jump_target_floor', None))
        all_floors = self.floor_manager.get_all_floors()
        for floor in all_floors:
            if self._floor_identity_key(floor) in (cur_fid, tgt_fid):
                continue
            if floor['rect'].intersects(current_rect):
                # 检测到穿透，取消跳跃，启动重力掉落
                _log.debug("跳跃过程中检测到楼层穿透，取消跳跃并启动重力掉落")
                self.is_jumping = False
                self._jump_anim_override = None
                self.start_falling()
                return
        
        # 确保跳跃结束时准确到达目标位置
        if jump_progress >= 1.0:
            # 跳跃完成，确保正确落到目标位置
            x = self.jump_target_pos.x()
            y = self.jump_target_pos.y()

            # ===== 落地收口（第十四轮）："落到某一层楼"必须当场结算 =====
            # 原来这里只更新了 `current_window`（历史遗留的裸缓存），**没更新
            # `current_floor`** —— 于是落地后 current_floor 还是起跳前那块楼板，
            # 紧接着 `_apply_pet_z_order` 会按错楼层把宠物插进 Windows z 序
            # （要等下一个 1 秒节拍才纠正），表现为"刚跳上去的一瞬间层级是错的"。
            landed_floor = getattr(self, 'jump_target_floor', None)
            if landed_floor is not None:
                self.current_floor = landed_floor
                self.current_platform_z = landed_floor.get('platform_height', 0)
            # current_window 降级为派生缓存，统一由楼层刷新（与走路/坠落同一条路）
            self._sync_window_cache_from_floor(landed_floor)

            # 确保Ralsei可见
            self.show()

            # 移动到新位置
            self.move(int(x), int(y))

            # 更新Z轴坐标为目标Z坐标
            self.spatial_pos["z"] = self.jump_target_z

            # 落定后立刻按"一层压一层"重排 z 序（show() 之后，理由同 handle_gravity_fall）
            self._apply_pet_z_order()

            # 播放落地动画（一次性：落地/站稳的动作播一遍就够，循环重播会"卡带"）
            self.play_animation_once("land", restore_to="idle")

            # 停止跳跃
            self.is_jumping = False
            # 清掉"跨度大用攀爬素材"的覆盖标记，避免残留到下一次跳跃
            self._jump_anim_override = None
        
        # 边界检查：确保Ralsei不会跳到屏幕外
        # 瞬移防治：原用 availableGeometry()（只认主屏）且把原点钉在 (0,0)，
        # 宠物在副屏时会每帧被拉回主屏。改走多显示器虚拟桌面矩形。
        x, y = self._clamp_pos_to_desktop(x, y)
        
        # 更新Ralsei的位置
        self.move(x, y)
        
        # 更新动画
        if self.is_jumping:
            # 如果还在跳跃中，保持跳跃动画
            # 批次 B：跨度大的衔接用**攀爬素材**（`start_jump` 按跨度单点选定），
            # 这里必须先尊重它 —— 否则每帧都会被 jump_ball 顶掉，等于没切。
            _override = getattr(self, '_jump_anim_override', None)
            if _override:
                self.change_animation(_override, force=True)
            else:
                # 第三十四轮（用户口径）："跳跃这种动画统一用 jump_ball 代替，
                # 只有摔下去的时候用原来的" —— 跳跃一律 jump_ball。
                # 原写法是 `elif self.has_ball: jump_ball / else: jump`，但
                # `has_ball` 全项目只有 L1170 一处赋值（恒为 False），
                # 于是实际**永远走 jump**，jump_ball 这条分支是死的。
                # 现在去掉这个恒假条件，直接走 jump_ball。
                self.change_animation("jump_ball", force=True)
        
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
    
    # ------------------------------------------------------------------
    # 楼层身份 / 楼板跟随（建楼要求：铁律"当前楼层原则"）
    # ------------------------------------------------------------------
    def _sync_window_cache_from_floor(self, floor):
        """把 `self.current_window`（老代码到处在用的裸窗口缓存）对齐到当前楼层。

        为什么必须同步（第十四轮）：建楼之后"当前站在哪"的唯一真源是 `current_floor`，
        而 `self.current_window` 是历史遗留的第二份状态，过去只在**跳跃落地 /
        重力落地**时被写。宠物**用脚走进**一块新楼板时（`check_window_movement` 里
        直接 `current_floor = new_floor`）它不会被更新 ——
        于是 `check_nearby_windows` 读到的"当前窗口"是 None 或过期的那块，
        层级过滤与跳跃方向全部算错（表现为"明明站上窗口了，却还按桌面判"）。
        这里把它降级成**派生缓存**：楼层一动就跟着刷，不再各写一份。
        （第十五轮：另一个"走路换楼板"的入口 `update_floor` 已作为死代码删除，
        本套同步现在只剩 `check_window_movement` 一个入口。）
        """
        if floor is None or floor.get('type') != 'window':
            self.current_window = None
            self.window_level = 0
            self.last_window_rect = None
            return
        w = floor.get('window') or {}
        rect = w.get('rect') or floor.get('rect')
        if rect is None:
            self.current_window = None
            self.window_level = 0
            self.last_window_rect = None
            return
        self.current_window = {
            'hwnd': w.get('hwnd', floor.get('window_hwnd')),
            'title': w.get('title', ''),
            'x': rect.x(),
            'y': rect.y(),
            'width': rect.width(),
            'height': rect.height(),
            'z_order': w.get('z_order', floor.get('z_order', 0)),
            'platform_height': floor.get('platform_height', 0),
        }
        self.window_level = self.current_window['z_order']
        self.last_window_rect = (rect.x(), rect.y(), rect.width(), rect.height())

    @staticmethod
    def _floor_identity_key(floor):
        """楼层的稳定标识：窗口用 hwnd、桌面用固定串。

        绝不能用两份 floor dict 的内容比较来判定"楼层有没有变"：floors 每轮由
        FloorManager.update_floors 整体重建，其中 platform_height 依赖"当前可见
        窗口数量"、z_order 随焦点变化、title 可能变动 —— 同一个窗口重建出来的
        dict 与缓存不等，就会被误判成"换了楼板"→ 直接摔倒。
        """
        if floor is None:
            return None
        if floor.get('type') == 'desktop':
            return 'desktop'
        return ('window', floor.get('window_hwnd'))

    @staticmethod
    def _floor_rect_changed(old_rect, new_rect):
        """楼板矩形是否变化（含尺寸）。任一侧为空按"变了"处理。"""
        if old_rect is None or new_rect is None:
            return True
        return (old_rect.left() != new_rect.left()
                or old_rect.top() != new_rect.top()
                or old_rect.width() != new_rect.width()
                or old_rect.height() != new_rect.height())

    def _follow_floor_move(self, old_floor, moved_floor):
        """楼板（窗口）被人挪走：把宠物按同样位移平移，保持它在楼板上的相对位置。

        对应建楼要求"我挪动窗口 = 我在空中挪动了一块楼板，宠物必须跟着楼板一起
        移动，别给我掉下来"。位移按两级阈值处理：
          · > 400px —— 视为"楼板被瞬间搬走"（最大化/还原/被系统挪走），不跟随，
            改为失足掉落；
          · > 30px  —— 跟随之后重心不稳摔倒（动画 ≥3s，符合要求）。
        """
        old_rect = old_floor.get('rect')
        new_rect = moved_floor.get('rect')
        if old_rect is None or new_rect is None:
            return
        x_diff = new_rect.left() - old_rect.left()
        y_diff = new_rect.top() - old_rect.top()
        if x_diff == 0 and y_diff == 0:
            return
        move_distance = (x_diff ** 2 + y_diff ** 2) ** 0.5

        # 无论是否跟随，都先把缓存的窗口位置刷成最新，避免下一轮重复判定
        if (self.current_window is not None
                and self.current_window.get('hwnd') == moved_floor.get('window_hwnd')):
            self.current_window['x'] = new_rect.left()
            self.current_window['y'] = new_rect.top()
            self.current_window['width'] = new_rect.width()
            self.current_window['height'] = new_rect.height()

        if move_distance > 400:
            _log.debug("窗口被大幅瞬移（%.0fpx），Ralsei 不跟随，改为失足掉落", move_distance)
            self.emotion_system.react_to_event('window_moved', {})
            if not self.is_falling:
                self.start_fall("window_move")
            return

        # 跟随楼板移动（同步平移，不做滑步）
        n_x = self.pos().x() + x_diff
        n_y = self.pos().y() + y_diff
        n_x, n_y = self._clamp_pos_to_desktop(n_x, n_y)
        self.move(int(n_x), int(n_y))

        if move_distance > 30 and not self.is_falling:
            _log.debug("窗口被大幅度移动（%.0fpx），Ralsei 重心不稳摔倒了", move_distance)
            self.emotion_system.react_to_event('window_moved', {})
            self.start_fall("window_move")

    # ------------------------------------------------------------------
    # 空中接住：坠落途中允许鼠标二次抓住 + 线速度缓冲减速
    # ------------------------------------------------------------------
    def _catch_falling_in_air(self):
        """鼠标按下时调用：如果宠物正在坠落，就"接住"它。

        用户反馈："他坠落过程中没办法用鼠标二次抓住他，记得改成能抓住的，并且要有
        一个针对他当时线速度的减速效果，而不是和撞上一堵墙毫无缓冲的感觉。"

        原来 is_falling 时 update_movement 会在拖拽保护**之前**就 handle_fall 并
        return，抛物线仍按旧速度移动宠物、与鼠标拖拽互相拉扯 → 抓不住，且一抓到就
        像撞墙一样瞬间静止。

        现在：结束坠落状态（两种坠落都清），把接住瞬间的线速度装进
        `_catch_brake` 缓冲窗口，由 `_tick_catch_brake` 让宠物按原速度方向再滑一段
        并线性减速到 0，减速结束后才真正 1:1 跟手。
        """
        was_falling = bool(getattr(self, 'is_falling', False)
                           or getattr(self, 'is_gravity_falling', False))
        if not was_falling:
            return False

        # 接住瞬间的线速度（px/s）：甩飞看 _fall_vx/_fall_vy，重力坠落看
        # fall_velocity_x/fall_speed。两者语义都是"每秒像素"。
        if getattr(self, 'is_gravity_falling', False):
            vx = float(getattr(self, 'fall_velocity_x', 0.0) or 0.0)
            vy = float(getattr(self, 'fall_speed', 0.0) or 0.0)
        else:
            vx = float(getattr(self, '_fall_vx', 0.0) or 0.0)
            vy = float(getattr(self, '_fall_vy', 0.0) or 0.0)

        # 结束坠落：两种状态都清，避免残留让 update_movement 继续走坠落分支
        self.is_falling = False
        self.is_gravity_falling = False
        self.is_recovering = False
        self.is_splat = False
        self.fall_velocity_x = 0.0
        self.fall_speed = 0.0
        self.fall_duration = 0.0
        for _a in _FALL_STATE_ATTRS:
            if hasattr(self, _a):
                delattr(self, _a)

        cur = self.pos()
        self._catch_brake = {
            't0': time.time(),
            'vx': vx,
            'vy': vy,
            'dur': float(getattr(self, '_CATCH_BRAKE_SECONDS', 0.28)),
            'x': cur.x(),
            'y': cur.y(),
        }
        _log.debug("在空中接住宠物：线速度 (%.0f, %.0f) px/s 进入 %.2fs 缓冲减速",
                   vx, vy, self._catch_brake['dur'])
        return True

    def _tick_catch_brake(self, elapsed_time):
        """缓冲减速窗口推进：按接住瞬间的线速度继续滑行并线性衰减到 0。

        位移用**速度线性衰减到 0 的积分**解析式，而不是逐帧累加，保证轨迹与帧率无关：
            速度 v(t) = v0 · (1 - t/dur)
            位移 s(t) = ∫v = v0 · t · (1 - t/(2·dur))
        收敛终点在 t=dur 处，总位移 = v0·dur/2（例：700px/s 接住 → 滑行 105px）。

        反例（勿回退）：曾误写 s(t) = v0 · t · (1 - t/dur)，那是**没有积分**的
        速度式乘时间 —— 轨迹成了顶点在 t=dur/2 的抛物线，宠物会先冲出去再**退回原地**。
        """
        cb = getattr(self, '_catch_brake', None)
        if not cb:
            self._catch_brake = None
            return
        elapsed = time.time() - cb['t0']
        if elapsed >= cb['dur']:
            # 缓冲结束：把拖拽锚点重设到"宠物此刻所在处"，否则下一帧鼠标一动
            # 宠物就被拉回光标处、跳一大截。
            try:
                self.drag_position = QCursor.pos() - self.frameGeometry().topLeft()
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
            self._catch_brake = None
            return
        _k = max(0.0, 1.0 - elapsed / (2.0 * cb['dur']))
        nx = cb['x'] + cb['vx'] * _k * elapsed
        ny = cb['y'] + cb['vy'] * _k * elapsed
        nx, ny = self._clamp_pos_to_desktop(int(nx), int(ny))
        self.move(nx, ny)

    def _apply_pet_z_order(self):
        """把宠物窗口按"一层压一层"插进 Windows 的 z 序里。

        用 Windows 原生的 `SetWindowPos(pet, insertAfter=所站楼板窗口, ...)`：
        宠物紧贴在**它正站着的那块楼板之上**，于是任何排在楼板前面的窗口都会
        自然盖住宠物 —— 遮挡不需要我们自己算，系统会算。

        · 站在窗口楼板上 → 插到该窗口之上；
        · 站在桌面上（1楼） → 插到 WorkerW 之后 = 桌面图标之上、所有应用窗口之下。

        修复（第十三轮）：之前这里是 `setWindowFlags(... | Qt.WindowStaysOnTopHint)`，
        把宠物**永久置顶**，于是它永远画在所有窗口之上、遮挡关系完全失效
        （用户原话："他直接走到我的窗口上面了，根本没遮挡关系这类的"）。
        floor_manager 里早就写好了 `get_insert_after_hwnd` / `set_window_behind`
        这对 helper，但**全项目零调用**，是死代码 —— 这里把它接活。

        需要定时重刷的原因：窗口被激活/移动、用户切换前台窗口之后 z 序会变，
        宠物要重新归位（与楼层检查同节拍，1 秒一次）。
        """
        try:
            hwnd = int(self.winId())
        except Exception as e:
            _log.debug("拿不到宠物窗口句柄，跳过 z 序调整: %s", e)
            return False
        if not hwnd:
            return False
        insert_after = self.floor_manager.get_insert_after_hwnd(
            getattr(self, 'current_floor', None))
        return FloorManager.set_window_behind(hwnd, insert_after)

    def check_window_movement(self):
        # 检查当前所在窗口是否移动，使用楼层系统处理
        
        # ===== 关键过程保护：施法 / 躲猫猫 中 跳过窗口跟随（避免瞬移和摔倒干扰游戏）=====
        if getattr(self, '_spell_stage', None) is not None:
            return
        if getattr(self, 'game_state', {}).get('is_playing'):
            return

        # ===== 空中/摔倒/被拖拽中：不做楼层判定 =====
        # 修复（"被甩飞时偶尔卡在一个动画里不继续" + "凭空掉到屏幕最底"）：
        # 本函数在 update_movement 里位于 is_jumping / is_gravity_falling / is_falling
        # 三个分支**之前**，所以摔倒飞行的途中它照样会跑。飞行中宠物会越过
        # "窗口→桌面"的边界 → 触发 start_falling() → is_gravity_falling 与 is_falling
        # 同时为真 → update_movement 优先走重力分支，handle_fall 的 _fall_phase
        # 再也不推进 → 宠物永久卡在 jump_ball 且一路掉到屏幕底。
        # 同理，拖拽中宠物位置由鼠标直接驱动，也不该被楼层跟随/失足打断。
        if (getattr(self, 'is_falling', False)
                or getattr(self, 'is_gravity_falling', False)
                or getattr(self, 'is_jumping', False)
                or getattr(self, '_is_being_dragged', False)):
            return

        # 更新楼层信息
        self.floor_manager.update_floors()

        # 获取Ralsei当前位置
        current_pos = self.pos()
        ralsei_rect = QRect(current_pos.x(), current_pos.y(), self.width(), self.height())
        
        # 获取当前所在楼层
        new_floor = self.floor_manager.get_current_floor(current_pos)
        old_floor = self.current_floor

        # ===== 1) 脚下的"楼板"被搬走？先跟随，而不是直接摔 =====
        # 建楼要求："我挪动窗口 = 我在空中挪动了一块楼板，宠物必须跟着楼板一起移动"。
        # 这里按**窗口句柄**找到那块楼板的最新矩形（哪怕宠物已经被落在后面、
        # get_current_floor 已经找不到它），再按位移决定"跟随"还是"失足"。
        followed = False
        if (old_floor is not None
                and old_floor.get('type') == 'window'
                and not self.is_falling
                and not self.is_jumping):
            moved = self.floor_manager.get_floor_by_window(old_floor.get('window_hwnd'))
            if moved is not None and self._floor_rect_changed(old_floor.get('rect'),
                                                              moved.get('rect')):
                followed = True
                self._follow_floor_move(old_floor, moved)
                current_pos = self.pos()
                new_floor = self.floor_manager.get_current_floor(current_pos)

        # ===== 2) 楼板是否真的换了：用稳定标识比较，绝不用 dict 内容 =====
        # 原写法 `new_floor != self.current_floor` 是拿两份 floor dict 比内容，而
        # floors 每轮由 update_floors 整体重建，platform_height（依赖当前可见窗口数量）
        # 与 z_order（随焦点变化）任一变，都会让"同一个窗口"重建出的 dict 与缓存不等
        # → 被误判成"楼层变化"→ 直接 start_fall("window_move") 摔倒。
        # 这正是用户看到的"看到窗口就摔倒"；同理，窗口被挪走时 get_current_floor
        # 找不到它、误判成"楼板消失"→ 一路掉到屏幕最底。
        if (not followed
                and old_floor is not None
                and self._floor_identity_key(new_floor) != self._floor_identity_key(old_floor)):
            # ===== 2a) "要不要掉"只看**层高比较**（第十六轮修复） =====
            # 原判据是 `old_floor 是窗口 and new_floor 不是窗口` —— 也就是说**只有
            # "下面变成桌面"才会掉**。可要求原文第 30 行给的例子恰恰是另一种情形：
            #   "如果我把窗口B（记事本）关掉，3楼消失，宠物如果原来在上面，
            #     就会掉到2楼（浏览器）上。"
            # 记事本关掉后下方还有浏览器 → `get_current_floor` 立刻把 current_floor
            # 换成浏览器（仍是窗口）→ 整段被跳过：不坠落、不播动画、不生气，
            # 宠物直接"瞬移"到了浏览器那一层（复检第十六轮 G2）。
            # 改成层高比较后，四种情形一次覆盖：
            #   · 走出窗口边缘，下面是桌面（5→0）  → 摔（常规动画）
            #   · 关掉窗口，下面是桌面（5→0）      → 摔（生气，起因=用户）
            #   · 关掉窗口，下面还有窗口（10→5）   → 摔（生气，起因=用户） ← 本次修复
            #   · 被更高的新窗口盖住（5→10）        → 不摔，直接站新板（要求 ⑪）
            old_h = old_floor.get('platform_height', 0) or 0
            new_h = new_floor.get('platform_height', 0) or 0

            # ===== 2b) 层高闸门（第十八轮 · 批次 B，修复检缺口 G3） =====
            # 缺口 G3：这一段原来只有"往低走才处理"，往高走直接落到下面的赋值
            # `self.current_floor = new_floor` —— 宠物站在桌面水平走进某个窗口的
            # 可见区域时被**静默提升**，不跳不落，只是一个瞬时的层级跳变。
            #
            # 用户口径（第十八轮）："走进更低的楼层也是一样，反正只要是楼层高低变换
            # 就要通过跳来衔接，注意，下楼的时候别用掉落，也用跳。"
            # 于是：**宠物自己走出来**的高低变换一律交给跳/攀爬（`_start_climb_transition`），
            # 上楼不再静默提升、下楼不再重力掉落；
            # 而**被动**成因（用户关窗抽走楼板 / 挪楼板 / 甩飞）仍旧走下面的坠落链路 ——
            # 这两条是要求 ⑩/⑪ 明确要的，不能一起改掉。
            #
            # "是不是自己走出来的"判据只有两条，且都用既有属性（历史回归套件的轻量桩
            # 没有 `is_moving` → `getattr` 取到 False → 不会走进闸门，桩继续测被动路径）：
            #   ① 宠物这一拍在走路；
            #   ② 旧楼板还有效（窗口还在）—— 被关掉的是被动，走 要求⑩ 的坠落。
            walk_induced = (new_h != old_h
                            and bool(getattr(self, 'is_moving', False))
                            and self.floor_manager.is_floor_valid(old_floor))
            if walk_induced and self._start_climb_transition(old_floor, new_floor):
                # 已经起跳：本拍不动 current_floor，落地时由 handle_jump 当场结算
                return
            if walk_induced and new_h > old_h:
                # 自己走上去、但上方那块楼板够不着（吸附后被推太远 / 不在可见区域）：
                # **保持原楼层**。"静默提升"正是缺口 G3 本身，不能拿它当兜底。
                _log.debug("层高闸门：够不着 %s 层（%s → %s）→ 保持原楼层",
                           new_h, old_h, new_h)
                return
            # 往下跌 + 够不着攀爬目标（例如走出侧面边缘、下方没有可进入的相邻层）
            # → 落到下面的坠落链路：重力必须赢（要求⑭）。

            if new_h < old_h:
                # 往下跌：脚下那一点已不在旧楼板的可见区域里，而新位置命中的是
                # **更低**的楼层 → 建楼要求第14行"直直掉下去，落到下面第一块能
                # 接住的楼板"。具体落到哪由 handle_gravity_fall 里的
                # `get_drop_destination` 按可见区域结算（已被复检 C3/C3c 锁住）。
                #
                # 起因分流（第十五轮接活 `is_floor_valid`，第十六轮才真正走到它）：
                #   · 窗口还在 → 宠物**自己走到了楼板边缘外** → 常规坠落动画
                #   · 窗口没了 → 用户把楼板抽走（关窗）    → 生气动画 ≥5s
                if self.floor_manager.is_floor_valid(old_floor):
                    _log.debug("宠物走出了楼板边缘（自身行为）→ 常规坠落动画")
                    self.start_falling()
                else:
                    _log.debug("脚下的窗口楼板已消失（用户行为）→ 生气动画 ≥5s")
                    self.start_falling(reason='floor_removed')
            elif new_h > old_h:
                # 更高：按"当前楼层原则"宠物现在直接站在新楼板上，不算楼板被搬走，
                # 不摔 —— 这是建楼要求 ⑪"新窗口盖住旧窗口"要的行为。
                # 走到这里只有一种情况：**不是宠物自己走上去的**（用户新开窗口盖上来），
                # 因为"自己走上去"已被上面的层高闸门接管。
                _log.debug("楼层升高（%s → %s）→ 直接站新板，不摔（要求 ⑪）", old_h, new_h)

        # 更新当前楼层信息
        self.current_floor = new_floor
        self.current_platform_z = new_floor['platform_height']
        self.spatial_pos["z"] = new_floor['platform_height']
        # 派生缓存同步：走路换上楼板时 current_window 也必须跟着换，
        # 否则它是 None/过期值，跳跃判定会按错的楼层算（见 _sync_window_cache_from_floor）
        self._sync_window_cache_from_floor(new_floor)
    
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
        self.is_recovering = False
        self.recovery_duration = 0.0
        # 修复（状态互斥）：is_falling / is_gravity_falling 同时为真时，
        # update_movement 会优先走重力分支（handle_gravity_fall），handle_fall 的
        # 分阶段流程永远不推进 → 宠物卡在摔倒动画里不动。两种"坠落"必须互斥。
        self.is_gravity_falling = False
        # 修复：恢复时间从5秒降到2.5秒。
        # 人摔倒后晕一会就爬起来了，5秒恢复期+3-5秒摔倒=8-10秒趴在地上太久了。
        self.recovery_max_duration = 2.5

        # 第十六轮：把起因记下来（`start_falling` 那边同样处理）。
        # `_fall_reason` 原来只在 `start_falling` 里写，于是 window_move 这条路
        # 到了落地结算时读不到起因 → 生气素材被普通 splat 顶掉（要求第37行的 ≥3s 落空）。
        # 时长/素材都由它派生（`_fall_splat_hold` / `_splat_animation_name`）。
        self._fall_reason = reason

        # 批次 B（第十八轮）：与 `start_falling` 同一口径记下"从多高掉下来的"
        # （起点楼层的 platform_height），保持这个量的语义只有一份。
        try:
            self._fall_from_height = int(
                (getattr(self, 'current_floor', None) or {}).get('platform_height', 0) or 0)
        except Exception:
            self._fall_from_height = 0

        # 触发情绪反应：摔倒
        self.emotion_system.react_to_event('fell_down', {'reason': reason})

        # 第三十四轮：四个分支原本各自写一次 `self.is_moving = False`（4 处重复）。
        # 提为无条件统一赋值——四个分支的值完全一致，且后续无分支再改它。
        # ⚠️ 各分支的 `idle_timer = 0` 只在 fall_off / 默认 两处出现，属真实差异，
        #    不在此处合并（合并会改变 window_move / fall_from_window 的行为）。
        self.is_moving = False

        # 根据摔倒原因选择不同的动画、消息和持续时间
        if reason == "window_move":
            # 用户移动窗口导致摔倒——用户行为造成的，用生气的摔倒动画
            if "fall_mad" in self.sprite_loader.sprites:
                self.change_animation("fall_mad", force=True)
            else:
                self.change_animation("fall", force=True)
            self.max_fall_duration = 3.0
            # 修复：台词匹配生气动画——抱怨用户乱动窗口，而不是单纯惊讶
            self.dialogue_ui.add_dialogue("ralsei", "喂！别乱动窗口呀！我站不稳了...", "surprised")
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
        elif reason == "fall_off":
            # Ralsei自己从窗口边缘掉下去
            # 使用普通摔倒动画（spr_ralsei_splat_0.png），持续5秒
            self.change_animation("fall", force=True)
            # 设置较长的摔倒持续时间（5秒）
            self.max_fall_duration = 5.0
            # 显示摔倒消息
            self.dialogue_ui.add_dialogue("ralsei", "哎呀！我掉下去了！", "sad")
            # 修复：与其他分支一致，摔倒时暂停行走
            self.idle_timer = 0
        else:
            # 默认情况，使用普通摔倒动画，持续5秒
            self.change_animation("fall", force=True)
            # 确保摔倒动画持续时间至少3秒
            self.max_fall_duration = 3.0
            # 显示摔倒消息
            self.dialogue_ui.add_dialogue("ralsei", "哎呀！我摔倒了！", "surprised")
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
        播放 snd_splat.wav 音效，然后走分阶段恢复：摔扁→晕乎揉头→爬起来。"""
        # 修复：不再用 is_splat 独立计时（2秒后直接切idle太突兀）。
        # 改为走 handle_fall 的 _fall_phase 分阶段流程，有完整的爬起过渡。
        self.is_splat = True
        self.splat_start_time = time.time()
        self.is_moving = False
        self.is_falling = True
        # 修复（状态互斥）：唯一调用点（handle_gravity_fall）确实在调用前清过
        # is_gravity_falling，但本方法若被其它路径调用就会出现 is_falling 与
        # is_gravity_falling 同时为真 → update_movement 走重力分支、splat 流程停滞。
        # 在这里显式清一次，把这个隐患从"靠调用方记得清"变成自洽。
        self.is_gravity_falling = False
        self.is_recovering = False
        self.fall_duration = 0.0
        self._fall_phase = "splat"  # 直接从摔扁阶段开始（已经落地了）
        self._fall_phase_start = 0.0
        # `max_fall_duration` 现在只服务"晕乎阶段何时结束"这个**旧**口径
        # （handle_fall: `max(1.0, max_fall_duration - 2.0)` → 1.0s）；
        # 摔扁阶段的最短停留由 `_fall_reason` 纯派生（`_fall_splat_hold`），
        # 两者各有各的口径、不再混用。
        self.max_fall_duration = 3.0
        self.recovery_max_duration = 1.5  # 爬起恢复1.5秒
        # 播放 splat 音效
        try:
            self.sound_manager.play_splat()
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        # 切换到 splat 动画。第十六轮修复：原来恒切普通 `splat`，把坠落途中刚播上的
        # 生气素材（fall_mad）**在落地那一瞬换掉** —— 于是"生气动画至少 5s"根本不可能
        # 成立。现在按起因选（判定收在模块级 `_splat_animation_name`，与 handle_fall 共用）。
        self.change_animation(_splat_animation_name(self), force=True)
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
        # 水平空气阻力（按时间衰减，避免帧率变化时轨迹忽长忽短）
        self.fall_velocity_x *= max(0.0, 1.0 - 0.7 * elapsed_time)
        horizontal_distance = self.fall_velocity_x * elapsed_time
        
        # 更新位置（抛物线：X有惯性，Y受重力）
        current_pos = self.pos()
        new_x = current_pos.x() + horizontal_distance
        new_y = current_pos.y() + fall_distance
        
        # 屏幕边界夹紧：绝不坠落到桌面底下（多显示器：按整块虚拟桌面夹紧）
        # 瞬移防治：原用 availableGeometry()（只认主屏，原点钉在 0,0），
        # 副屏上会横向被拉回主屏 = 瞬移。改用虚拟桌面矩形。
        new_x, _clamped_y = self._clamp_pos_to_desktop(int(new_x), int(new_y))
        max_y = self._desktop_floor_y()
        if int(new_y) > max_y:
            new_y = max_y
        else:
            new_y = _clamped_y
        
        # 检查是否落到了某个楼层上
        ralsei_pos = QPoint(int(new_x), int(new_y))
        drop_floor, drop_pos = self.floor_manager.get_drop_destination(ralsei_pos, self.current_floor)
        
        # 落点判定：同样必须用"楼层稳定标识"比较，不能用 dict 内容（floors 每轮重建，
        # 内容必然不等 → 会把"还在自己脚下的那块楼板"误判成"落到了新楼层"）。
        # 另外把"桌面"排除在"落地"之外：桌面是最底层，只有真的落到屏幕底边（max_y）
        # 才算落地；否则从窗口上开始的坠落会立刻在当前位置"落地"、悬停在半空中。
        landed_floor = None
        if (drop_floor is not None
                and drop_floor.get('type') != 'desktop'
                and self._floor_identity_key(drop_floor)
                != self._floor_identity_key(self.current_floor)):
            landed_floor = drop_floor

        if landed_floor is not None:
            # 落到了新的楼层上（下面沿用 drop_floor 命名，二者此刻是同一块楼板）
            drop_floor = landed_floor
            new_y = drop_pos.y()
            self.is_gravity_falling = False
            self.fall_velocity_x = 0  # 落地清除水平惯性

            # 落点合法性：`get_drop_destination` 只在"宠物位置落在该层**可见区域**里"
            # 时才把这一层交出来（第十三轮的可见区域判定），所以这里不需要再吸附 ——
            # 能落到这一层，就说明脚下确实是一块看得见的地板。
            
            # 根据摔落速度决定落地表现
            if _should_splat_on_landing(self, drop_floor):
                # 高速 + **层数比较高** → 触发 splat（批次 B：低层摔不扁）
                self.trigger_splat()
                # 添加摔倒惯性滑行效果
                self.fall_slide_speed_x = random.uniform(-20, 20)
                self.fall_slide_speed_y = random.uniform(-10, 10)
            elif "land" in self.sprite_loader.sprites:
                # 低速落到**窗口楼层**（不是摔到桌面）：播一次落地动作再站稳。
                # "落到某一层楼"要有落地的交代 —— 原来直接切 idle，看着像平移过去的。
                # 一次性播放（与跳跃落地同一口径），循环重播会"卡带"。
                self.play_animation_once("land", restore_to="idle")
            else:
                # 低速摔落：先站稳(idle)，而不是立刻开始走路
                self.change_animation("idle", force=True)

            # 更新当前楼层信息
            self.current_floor = drop_floor
            self.current_platform_z = drop_floor['platform_height']
            self.spatial_pos["z"] = drop_floor['platform_height']
            # current_window 是派生缓存，统一由楼层刷新（第十四轮：消除双真源。
            # 原来这里有一份手写的裸 dict 构造，和 _sync_window_cache_from_floor
            # 是同一件事的两份实现 —— 正是这个项目反复踩的坑。）
            self._sync_window_cache_from_floor(drop_floor)

            self.show()
            # 落定后按"一层压一层"重排 z 序。
            # 顺序很关键：必须放在 show() **之后** —— show() 有把窗口提到前面的副作用，
            # 先定位再 show 会被它撤销。
            # 修复（第十三轮）：原来这里按"在窗口上/在桌面"分别 setWindowFlags，
            # 在窗口上用 Qt.WindowStaysOnTopHint 强制置顶 → 宠物永远画在所有窗口之上，
            # 遮挡关系完全失效（用户："他直接走到我的窗口上面了，根本没遮挡关系"）。
            self._apply_pet_z_order()
        else:
            # 继续掉落
            # 检查是否落到了桌面底部（多显示器：虚拟桌面底边）
            if new_y >= max_y:
                # 落到桌面底部（夹紧，绝不超出屏幕）
                new_y = max_y
                self.is_gravity_falling = False
                self.fall_velocity_x = 0  # 落地清除水平惯性
                
                # 根据摔落速度决定是否触发摔倒动画
                if _should_splat_on_landing(self, self.floor_manager.desktop_floor):
                    # 高速 + **层数比较高** → 触发 splat（批次 B：掉到桌面也是一样判）
                    self.trigger_splat()
                    # 添加摔倒惯性滑行效果
                    self.fall_slide_speed_x = random.uniform(-20, 20)
                    self.fall_slide_speed_y = random.uniform(-10, 10)
                else:
                    # 低速摔落（或层数不够高）：先站稳(idle)
                    self.change_animation("idle", force=True)
                
                # 修复（坠落循环）：这里原来没有把 current_floor 更新成桌面层，
                # 于是宠物落到屏幕底边后 current_floor 仍是"那块已经离开的窗口楼板"，
                # 下一秒 check_window_movement 又判定"窗口→桌面"= 楼层变化 →
                # 再次 start_falling()，表现为每隔 1 秒凭空"抽一下"的假坠落。
                self.current_floor = self.floor_manager.desktop_floor
                # 派生缓存同步（同一入口，见 _sync_window_cache_from_floor）
                self._sync_window_cache_from_floor(self.floor_manager.desktop_floor)
                
                # 更新空间坐标
                self.spatial_pos["z"] = 0
                self.current_platform_z = 0
                
                # 落回桌面（1楼）→ 按"一层压一层"重排 z 序（插到 WorkerW 之后）
                self.show()
                self._apply_pet_z_order()
        
        # 移动Ralsei
        self.move(int(new_x), int(new_y))
    
    # 摔倒判定相关代码 - 处理摔倒逻辑
    def handle_fall(self, elapsed_time, current_time):
        # 处理摔倒逻辑（分阶段：flying → splat → dazed → recovering）
        if not self.is_recovering:
            self.fall_duration += elapsed_time

            # ===== 飞行阶段：抛物线（俯视 2D 风格）=====
            # 用户反馈"抛物路径按偏俯视 2D 游戏来"。原实现是纯水平/斜向滑行、
            # 速度按 `*= 0.8` 每帧指数衰减（帧率相关、且永远等不到"落地"，
            # 1 秒后原地摔扁 = 空中摔扁，看着像瞬移）。
            # 现在：水平速度带空气阻力线性衰减；竖直方向初速向上、受重力加速；
            # 回到起跳高度（或撞到桌面底边）即判定落地 → 立刻进 splat 阶段。
            # 这两个标志在下面两个分支里赋值，但阶段转换判断要用到，
            # 先给默认值，避免"非飞行阶段"时短路求值以外的情况出现未定义名。
            _timeout = False
            _is_ballistic = hasattr(self, '_fall_vy')

            if getattr(self, '_fall_phase', 'flying') == "flying":
                # 飞行计时（与 fall_duration 解耦：阶段切换以"本阶段已持续时长"为准）
                self._fall_flight_time = getattr(self, '_fall_flight_time', 0.0) + elapsed_time
                if _is_ballistic:
                    _vx0 = getattr(self, '_fall_vx', 0.0)
                    _vy0 = getattr(self, '_fall_vy', 0.0)
                    # 起跳竖直速度只取"飞行第一帧"那一次：self._fall_vy 每帧末尾都会
                    # 被写成当前速度，若每帧重读就会在下降段读到正数，
                    # "初速朝上才用起跳高度落地"的判定随之失效。
                    _vy0_launch = getattr(self, '_fall_vy0', None)
                    if _vy0_launch is None:
                        _vy0_launch = float(_vy0)
                        self._fall_vy0 = _vy0_launch
                    _gy = float(getattr(self, 'gravity', 500.0)) or 500.0
                    _drag = 1.9  # 空气阻力系数(1/s)
                    _vx = float(_vx0) * max(0.0, 1.0 - _drag * elapsed_time)
                    _vy = float(_vy0) + _gy * elapsed_time
                    _cur = self.pos()
                    _nx = int(_cur.x() + _vx * elapsed_time)
                    _ny = int(_cur.y() + _vy * elapsed_time)
                    _launch_y = int(getattr(self, '_fall_launch_y', _cur.y()))
                    _floor_y = self._desktop_floor_y()
                    _nx, _ny = self._clamp_pos_to_desktop(_nx, _ny)
                    # 落地判定：正在下落且回到起跳高度，或已经顶到桌面底边。
                    # 落点直接"吸附"到平面上，避免离散积分多冲出去一帧（几像素的抖动）
                    # 修复（斜抛）：只有**初速朝上**（_vy0 < 0）时才存在"升到最高点再
                    # 落回起跳高度"这一段；水平/向下甩的初速一上来 _vy 就 > 0，
                    # 若仍按"回到起跳高度"判定就会在第 1 帧原地判定落地（摔在松手点），
                    # 斜抛根本飞不起来。此时改为一路落到真正的实心地面。
                    _hit_floor = _ny >= _floor_y
                    _hit_launch = (_vy0_launch < 0 and _vy > 0 and _ny >= _launch_y)
                    if _hit_floor or _hit_launch:
                        self.move(_nx, _floor_y if _hit_floor else _launch_y)
                        self._fall_vx = 0.0
                        self._fall_vy = 0.0
                        self._fall_landed = True
                    else:
                        self._fall_vx = _vx
                        self._fall_vy = _vy
                        self.move(_nx, _ny)
                    # 兜底：万一抛物线永远回不到起跳高度（被夹在屏幕顶等），
                    # 2.5 秒后也必须落地，绝不能空中摔扁。
                    _timeout = self._fall_flight_time >= 2.5
                else:
                    # 自己绊倒/从窗口掉下（start_fall）：保留原来的惯性滑行，
                    # 但滑行时间按"飞行计时"而不是旧的 fall_duration。
                    if hasattr(self, 'fall_slide_speed_x'):
                        _cur = self.pos()
                        _nx = int(_cur.x() + self.fall_slide_speed_x * elapsed_time)
                        _ny = int(_cur.y() + getattr(self, 'fall_slide_speed_y', 0.0) * elapsed_time)
                        _nx, _ny = self._clamp_pos_to_desktop(_nx, _ny)
                        self.move(_nx, _ny)
                        self.fall_slide_speed_x *= max(0.0, 1.0 - 2.0 * elapsed_time)
                        if getattr(self, 'fall_slide_speed_y', None) is not None:
                            self.fall_slide_speed_y *= max(0.0, 1.0 - 2.0 * elapsed_time)

            # 阶段转换（以"本阶段已持续时长"驱动，而不是全局 fall_duration）
            phase = getattr(self, '_fall_phase', 'flying')
            _phase_t = self.fall_duration - getattr(self, '_fall_phase_start', 0.0)
            if phase == "flying" and (getattr(self, '_fall_landed', False)
                                      or _timeout
                                      or (not _is_ballistic and getattr(self, '_fall_flight_time', 0.0) >= 1.0)):
                # 真正落地后 → 摔扁在地上
                self._fall_phase = "splat"
                self._fall_phase_start = self.fall_duration
                self.is_splat = True
                # 第十六轮：这里原来恒切普通 `splat` —— 于是 `start_fall("window_move")`
                # 在坠落途中播的 `fall_mad` 会在落地一瞬被顶掉（要求第37行 ≥3s 落空）。
                # 改用与 trigger_splat 共用的模块级 `_splat_animation_name(pet)`。
                _splat_anim = _splat_animation_name(self)
                if _splat_anim in self.sprite_loader.sprites:
                    self.change_animation(_splat_anim, force=True)
                try:
                    self.sound_manager.play_splat()
                except Exception:
                    pass
                # 清除滑行/抛物线速度与落地标记（注意：**不含** _fall_phase，
                # 它刚被置为 "splat"，下面还要靠它推进阶段机）
                for attr in _FALL_VELOCITY_ATTRS:
                    if hasattr(self, attr):
                        delattr(self, attr)
            elif phase == "splat" and _phase_t >= _fall_splat_hold(self):
                # 摔扁阶段结束 → 晕乎揉头。
                # 第十六轮：**时长改由 `_fall_splat_hold(pet)` 决定**（关窗 ≥5s / 挪楼板
                # ≥3s / 其余 1.0s，与改前逐字节一致）。这里原来硬编码 1.0s —— 那正是
                # "生气动画至少 5s"永远不成立的原因之一（复检 G1）。
                self._fall_phase = "dazed"
                self._fall_phase_start = self.fall_duration
                self.is_splat = False
                if "fall_back_rub" in self.sprite_loader.sprites:
                    self.change_animation("fall_back_rub", force=True)
                elif "fall_back" in self.sprite_loader.sprites:
                    self.change_animation("fall_back", force=True)
                dazed_msgs = ["呜...头好晕...", "诶...我在哪...", "浑身好痛..."]
                self.dialogue_ui.add_dialogue("ralsei", random.choice(dazed_msgs), "sad")
                self.dialogue_ui.show_dialogue()
            elif phase == "dazed" and _phase_t >= max(1.0, self.max_fall_duration - 2.0):
                # 晕乎1.5秒后 → 慢慢爬起来，进入恢复期
                # 注（第十六轮）：`max_fall_duration` 从这里起**只等于"晕乎时长 + 2.0"**
                # 这个旧口径（trigger_splat 固定给 3.0 → 晕乎 1.0s），它不再是
                # "摔扁最短停留"的载体 —— 那个已交给 `_fall_splat_hold(pet)`。
                # 两者分开是为了让"≥5s"只影响**生气动画本身**，不把晕乎/爬起一起拉长。
                self._fall_phase = "recovering"
                self.is_recovering = True
                self.recovery_duration = 0.0
                # 用户要求："站起身这类的动作播一次就好"。
                # 原来用 change_animation 会被动画循环反复重播（爬起来 → 又爬一次）。
                if "land" in self.sprite_loader.sprites:
                    self.play_animation_once("land", restore_to="idle")
                elif "pose" in self.sprite_loader.sprites:
                    self.play_animation_once("pose", restore_to="idle")
                else:
                    self.change_animation("idle", force=True)
                self.emotion_system.react_to_event('recovery_started', {})
                if random.random() < 0.7:
                    self.dialogue_ui.add_dialogue("ralsei", "呼...我没事了...谢谢你的关心...", "shy")
                    self.dialogue_ui.show_dialogue()
            elif phase not in ("flying", "splat", "dazed") and self.fall_duration >= self.max_fall_duration:
                # 兼容旧逻辑（没有_fall_phase时按原流程）
                self.is_recovering = True
                self.recovery_duration = 0.0
                if "land" in self.sprite_loader.sprites:
                    self.play_animation_once("land", restore_to="idle")
                elif "pose" in self.sprite_loader.sprites:
                    self.play_animation_once("pose", restore_to="idle")
                else:
                    self.change_animation("idle", force=True)
                for attr in _FALL_VELOCITY_ATTRS:
                    if hasattr(self, attr):
                        delattr(self, attr)
                self.emotion_system.react_to_event('recovery_started', {})
                if random.random() < 0.7:
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
                for _a in _FALL_STATE_ATTRS:
                    if hasattr(self, _a):
                        delattr(self, _a)
                self.is_splat = False

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
        # 清理睡眠迷糊状态
        for attr in ('_sleep_stir_time', '_sleep_stir_count'):
            if hasattr(self, attr):
                delattr(self, attr)
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
        """"走过去看看某个桌面图标"——不再假装搬动用户的文件。

        第六轮（"人会不会那么做"）：原实现把 Ralsei 内部模型里的图标坐标改成
        "被拖走"的样子，再让 Ralsei 每帧 self.move 追这个假坐标；但真实桌面图标
        根本没动，用户看到的是"对着空气搬东西"，而且追假坐标是一条实打实的瞬移来源。
        现在改成诚实的行为：随便挑一个图标，用正常走路系统走过去，到了歪头看一眼。
        """
        import random
        elements = list(getattr(self.desktop_interaction, 'desktop_elements', None) or [])
        if not elements:
            return
        el = random.choice(elements)
        try:
            tx = int(el.get('x', self.x())) + 60   # 站在图标旁边，不压住它
            ty = int(el.get('y', self.y()))
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return
        tx, ty = self._clamp_pos_to_desktop(tx, ty)
        self.target_pos = QPoint(tx, ty)
        self.is_moving = True
        self.current_activity = "looking_around"
        self._pending_look_at_element = True
        self.last_dragging_time = time.time()
        
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
        # ===== 第八轮：特殊动画不再由规则引擎自行播放，只把观察上报给 AI =====
        # 用户要求："确保所有特殊动画，也就是除了走路、跑步、待机这几个动画，
        # 其余的都只交给 AI 判断是否播放，别和抽风似的突然一下。"
        # 这里原来是 play_animation_once(reaction['action'])，由"凑近桌面元素"
        # （update_movement 每 5 秒一次 check_nearby_desktop_elements）自动触发 ——
        # 宠物会站着毫无来由地突然抬头/比划/惊讶。现在规则系统只当"眼睛"：
        # 把"我凑近了什么、它是什么质地"写进 ai_driver 的事件队列，
        # 要不要做动作、做哪个动作，完全由 AI 决定；AI 未启用时不会有任何表演。
        self._note_desktop_observation(elem_path, element, reaction)
            
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
            # 纯文案修复（零成本）：原句「需要我帮你打开浏览器或搜索什么吗？」是
            # persona 第 40~41 行**明令禁说**的助手腔，但它写死在代码里、persona 管不到，
            # 所以会一直说下去（S7 第二批分类文档 §五 的顺带发现）。
            # 改成"看到浏览器"的纯观察 —— 是 Ralsei 的口吻，也**不再**是工具人说辞。
            self.dialogue_ui.add_dialogue(
                "ralsei", "咦，是浏览器呀……我平时不太敢乱碰里面的东西呢。", "surprised")
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
    
    
    
    # 动画名 → 口语化的"心痒"描述（只作提示，AI 可以不理）
    _URGE_WORDS = {
        'look_up': '抬头看看', 'act': '比划一下', 'surprised': '惊讶一下',
        'wave': '挥挥手', 'pose': '摆个姿势', 'cry': '想哭',
        'happy': '开心一下', 'laugh': '笑一下',
    }

    def _note_desktop_observation(self, elem_path, element, reaction):
        """把"凑近桌面元素"这件事上报给 AI（只上报，不再自行表演特殊动画）。

        第八轮用户要求：特殊动画只能由 AI 判断是否播放。规则系统在这里的角色
        从"演员"降级为"眼睛"——描述事实（看到什么、什么质地、心里有点想怎样），
        由 AI 在下一拍决策时决定要不要回应（say / 小动作 / 什么都不做）。

        AI 未启用时，事件只会静静躺在队列里（上限 6 条），不产生任何可见行为。
        """
        try:
            driver = getattr(self, 'ai_driver', None)
            if driver is None or not callable(getattr(driver, 'note_event', None)):
                return
            name = os.path.basename(elem_path) or str(elem_path or '东西')
            traits = []
            try:
                if element.get('is_fragile'):
                    traits.append('看起来很脆、容易碎')
                _w = element.get('weight')
                if isinstance(_w, (int, float)) and _w > 1.5:
                    traits.append('挺重的')
                _t = element.get('temperature')
                if isinstance(_t, (int, float)):
                    if _t > 25:
                        traits.append('摸起来有点热')
                    elif _t < 18:
                        traits.append('摸起来凉凉的')
                _mat = {'metal': '金属的', 'wood': '木头的',
                        'plastic': '塑料的', 'paper': '纸做的'}.get(
                            element.get('material'))
                if _mat:
                    traits.append(_mat)
            except Exception as e:
                _log.debug("main 防御性异常（已忽略）: %s", e)

            desc = "我凑近了桌面上的「%s」" % name
            if traits:
                desc += "（%s）" % "，".join(traits)
            urge = self._URGE_WORDS.get(str(reaction.get('action') or '').strip())
            if urge:
                desc += "，心里有点想%s" % urge
            driver.note_event(desc, reaction.get('emotion', ''))
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)

    def open_browser_for_ralsei(self):
        # 为Ralsei打开浏览器，使用国内可用网站
        self.dialogue_ui.add_dialogue("ralsei", "我来帮你打开浏览器吧！", "happy")
        self.dialogue_ui.show_dialogue()
        self.desktop_interaction.open_browser("https://www.baidu.com")
    
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
        # 清理睡眠迷糊状态
        for attr in ('_sleep_stir_time', '_sleep_stir_count'):
            if hasattr(self, attr):
                delattr(self, attr)
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
        """已废弃的"情绪自动切换动画"入口 —— 现在什么都不做（保留空实现以便不改调用点）。

        用户要求（第八轮）："确保所有特殊动画，也就是除了走路，跑步，待机这几个动画，
        其余的都只交给 AI 判断是否播放，别和抽风似的突然一下。"

        原实现里有两条**非 AI** 的特殊动画入口：
          · 情绪 → 动画映射（`emotion_system.get_animation_for_emotion`），强度 >20 就切；
          · `random.random() < 0.1` 的 10% 随机 `force=True` 切换。
        两者都会在宠物站着不动时突然切到 dance / sing / curtsy / sleep / hug / victory…
        —— 正是用户说的"抽风似的突然一下"。（强度 >50 时还是 force 硬切，
        会把走路/一次性动画一起打断。）

        现在：情绪照常累计与衰减（`emotion_system` 不依赖本函数），但**不再驱动动画**。
        特殊动画只允许两个来源：
          1) 本地 AI 决策（ai_driver → play_animation_once）；
          2) 用户的显式交互（右键菜单、抚摸/戳一戳等点击事件）。
        本函数保留为空实现，是为了不动 update 循环里的调用点。
        """
        return

    # ==============================================================
    # 自主开口（AI 接管）—— 第六轮
    #   用户要求：删掉"系统里自带的对话"，全权交给 AI；10 分钟内最多主动说 1 次。
    #   已删除的内置台词入口：
    #     · dialogue_system.should_initiate_conversation / initiate_conversation
    #       （模板库随机台词）
    #     · 17 个办公检查 check_browser_windows … check_work_life_balance
    #     · check_excel_table_needs / check_weather_response / check_interesting_files
    #   现在只剩一条通道 start_autonomous_speech()：让本地 AI 生成一句话。
    #   AI 未启用 / 请求失败 / 返回空 → **保持沉默**，绝不回落内置台词。
    # ==============================================================
    AUTONOMOUS_SPEECH_MIN_INTERVAL = 600.0  # 自主开口最小间隔：10 分钟

    # 待机动画（idle 的 5 帧循环）启动门限：必须**原地静止**满这么久才播。
    # 用户要求："待机动画要在原地不动3分钟以上才会播放哦，而不是停止就播"。
    # 单位秒；idle_timer 由 update_movement 维护，移动时清零。
    IDLE_LOOP_MIN_SECONDS = 180.0  # 3 分钟

    def _can_speak_now(self):
        """此刻开口是否"合时宜"（硬条件，与频率无关）。"""
        try:
            if self.is_sleeping:
                return False
            if getattr(self, 'game_state', {}).get('is_playing'):
                return False
            # 正在进行物理/交互过程时插话很突兀
            for attr in ('is_falling', 'is_recovering', 'is_splat',
                         'is_jumping', 'is_gravity_falling',
                         '_is_being_dragged', 'is_following_mouse'):
                if getattr(self, attr, False):
                    return False
            dui = self.dialogue_ui
            if hasattr(dui, '_is_user_inputting') and dui._is_user_inputting():
                return False          # 用户正在打字，绝不打断
            if getattr(dui, '_ai_inflight', False):
                return False          # 已有一个 AI 请求在飞
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return False
        return True

    def _autonomous_speech_allowed(self):
        """自主开口闸门：合时宜 + 距上次自主开口 ≥ 10 分钟 + **不在聊天中途**。"""
        if not self._can_speak_now():
            return False
        # 用户要求（第九轮）："确保那个 10 分钟自动触发一次聊天的机制不会打断
        # 当前进行的聊天。" —— 只要正在聊天（刚有来有回 / 模型还在回 / 用户在
        # 打字 / 静置不超过 150 秒），自主开口就让位。用户主动点"聊天"走的是
        # user_requested 分支，不受这条限制。
        try:
            dui = self.dialogue_ui
            if callable(getattr(dui, 'has_active_conversation', None)) \
                    and dui.has_active_conversation():
                _log.debug("[自主对话] 正在聊天中，本次不插话")
                return False
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        last = getattr(self, '_last_autonomous_speech_time', None)
        interval = float(getattr(self, 'AUTONOMOUS_SPEECH_MIN_INTERVAL', 600.0))
        if last is not None and (time.time() - last) < interval:
            return False
        return True

    def start_autonomous_speech(self, reason="idle", user_requested=False):
        """开口的唯一入口：让 AI 生成一句话。

        - user_requested=False（自主触发）：受 10 分钟闸门限制；
        - user_requested=True（用户主动点"聊天"）：只做合时宜性检查，不计入闸门。
        返回 True 表示已发起，False 表示本次不开口。
        注意：AI 不可用时**什么都不说**——这是刻意设计（用户要求"全权由 AI 接管"）。
        """
        if user_requested:
            if not self._can_speak_now():
                return False
        elif not self._autonomous_speech_allowed():
            return False
        if not getattr(self, 'api_enabled', False) or not hasattr(self, 'chat_with_ai'):
            _log.debug("[自主对话] 未启用本地 AI，保持沉默（不回落内置台词）")
            return False

        # 立即计时：无论 AI 是否返回，都不应该在 10 分钟内再试，避免请求风暴
        if not user_requested:
            self._last_autonomous_speech_time = time.time()
        _log.debug(f"[自主对话] 触发（reason={reason}, user_requested={user_requested}）")

        if user_requested:
            prompt = (
                "（对方主动来找你聊天了，你先开口打个招呼吧。"
                "简短地说一句话即可，只输出这一句话。）"
            )
        else:
            prompt = (
                "（对方有一阵子没说话了。你可以主动开口，简短地说一句话——"
                "问问他好不好、说说你此刻的小心情，或者随口闲聊都行。"
                "只输出这一句话，不要说别的；如果实在没什么想说的，就只回复一个「。」）"
            )

        def _on_reply(reply_text):
            # 先过公共输出护栏：去包裹引号 / 截掉自问自答续写 / 丢弃照抄 persona 示例
            # 的回复 / 超长截断（第十八轮统一到 _clean_ai_reply，与对话链路同一套规则）
            #
            # 防御：这个回调是从工作线程（或测试桩对象）上调过来的，护栏本身出问题
            # 也**绝不能**让异常冒泡到调用方 —— 否则 start_autonomous_speech 里那个
            # 宽 except 会把"已发起"误判成 False（第六轮回归 B2/B3/B7/B8 曾因此全挂）。
            # 取不到护栏就退回最朴素的清洗。
            try:
                # 修复：原先未传 recent → _clean_ai_reply 第 2 步（车轱辘话判定）
                # 整步跳过，自主开口永远不会被判退重采样，与对话链路不一致。
                # 取法与对话链路同源：AI 历史里 role=='assistant' 的文本。
                _rec = []
                try:
                    _dui = getattr(self, 'dialogue_ui', None)
                    _hist = _dui.get_ai_history() if _dui is not None else []
                    _rec = [c for _r, c in _hist if _r == 'assistant']
                except Exception:
                    _rec = []
                text = self._clean_ai_reply(reply_text, recent=_rec) or ""
            except Exception as e:
                _log.debug("main 防御性异常（已忽略）: %s", e)
                try:
                    text = (reply_text or "").strip().strip('"\'“”「」『』《》')
                except Exception:
                    text = ""
            if not text or text in ("。", "…", "。。。", "（保持沉默）"):
                _log.debug("[自主对话] AI 选择沉默或不可用，本次不开口")
                return
            # 只保留第一句，避免模型长篇大论撑爆对话框（保留句末标点）
            for sep in ('\n', '。', '！', '？', '!', '?'):
                if sep in text:
                    head = text.split(sep, 1)[0].strip()
                    if head:
                        text = head + ('' if sep == '\n' else sep)
                    break
            if len(text) > 40:
                text = text[:40]
            if not text:
                return
            # 二次校验：AI 思考期间用户可能已经自己打开了对话/开始打字
            try:
                dui = self.dialogue_ui
                if hasattr(dui, '_is_user_inputting') and dui._is_user_inputting():
                    return
                face = "happy"
                try:
                    current_emotion, emotion_value = self.emotion_system.get_current_emotion()
                    face = self.emotion_system.get_face_for_emotion(
                        current_emotion, abs(emotion_value))
                except Exception:
                    pass
                dui.add_dialogue("ralsei", text, face)
                dui.show_dialogue()
                self.last_interaction_time = time.time()
            except Exception as e:
                _log.warning(f"[自主对话] 显示失败: {e}")

        try:
            self.chat_with_ai(prompt, _on_reply)
            return True
        except Exception as e:
            _log.debug(f"[自主对话] 发起失败，保持沉默: {e}")
            return False

    def check_initiate_dialogue(self):
        """每 15 秒轮询一次"要不要主动开口"。频率控制由
        start_autonomous_speech 的 10 分钟闸门负责（轮询故意留高频，
        以保证"刚好满 10 分钟"能尽快开口，而不是再等一个长周期）。"""
        self.start_autonomous_speech("timer")


    # ------------------------------------------------------------------
    # 事件台词（S7）：社交反应走 AI，短促反应保持罐头
    #
    # 改造前事件台词 100% 写死（`main.py` 131 处 `add_dialogue`），同一句反复出现
    # （连着摸三次都是「嘿嘿~ 好舒服呀！」）—— 这是"没活人味"最直观的来源。
    # 全量清单与「触发来源 × 文本性质」分类见
    # `code-quality-audit/人味改造-2026-09-18/_evidence/event_lines.txt`（可复算）。
    #
    # 档位表在 `modules/event_speech.EVENT_TIERS`（纯逻辑模块，无 Qt）。三档行为：
    #   ① 未登记为 AI 档 / `instant=True` / AI 不可用 → **立刻说罐头**（= 改造前行为）
    #   ② AI 档 → 发请求并**流式**打出来；`EVENT_SPEAK_FIRST_TOKEN_MS` 内连首字都没到
    #      才用罐头兜底（兜底只判"首字"，不判整句 —— 整句由打字机慢慢打）
    #   ③ 已经说过话之后，AI 的迟到回复不再补第二次 —— 一次事件只给一个气泡
    # 为什么"短促反应"必须留在罐头：摔落/甩飞要求 0 延迟，而且它是物理状态机的输出，
    # 交模型只会变慢变差（报告 §5 S7 的原则）。
    #
    # 为什么 AI 档要用**流式**（真机实测逼出来的，见 _evidence/s7_e2e_event.txt）：
    # 整句耗时 1.13~1.65s（中位 1.27s），而**首字** 0.79~0.90s（中位 0.81s）。
    # 不流式的话只有两条路 —— 让主人干等 1.3s 没反应，或把兜底时限放到 2.5s
    # （那已经不是"即时反应"了）。所以：框子先冒出来 + 打出「……」，
    # 首字一到就开始逐字冒字，兜底只负责"连首字都没有"这一种情况。
    # ------------------------------------------------------------------
    # 1200 而不是 900：首字实测最慢 0.90s，900ms 只留 0~60ms 余量 ——
    # 实测 8 次事件里有 1 次正好卡在 0.903s 被误判超时（落回罐头）。
    # 等待期已经在显示「……」（见 speak_event），放宽不会让人觉得"没反应"。
    EVENT_SPEAK_FIRST_TOKEN_MS = 1200     # 首字兜底时限（流式；整句不设限）
    EVENT_SPEAK_MIN_INTERVAL = 2.0        # 两次 AI 档事件的最小间隔（防连戳请求风暴）
    EVENT_SPEAK_MAX_CHARS = EVENT_MAX_CHARS   # 与模块共用同一份长度口径（不写第二份）

    def _event_speech_enabled(self):
        """事件台词是否走 AI（config: `api.event_speech`，**缺省开启**）。

        S7 总开关：关掉即回到"事件台词全部罐头"的改造前行为（改 config 即可，无需回滚代码）。
        """
        if not getattr(self, 'api_enabled', False):
            return False
        try:
            cfg = getattr(self, 'api_config', None) or {}
            if isinstance(cfg, dict) and 'event_speech' in cfg:
                return bool(cfg.get('event_speech'))
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        return True

    def _pick_event_line(self, pool):
        """从罐头池里挑一句**最近没说过**的。

        改造前是 `random.choice(pool)`，而池子常常只有 3~4 句 → 连戳三次很容易撞同一句。
        去重窗口见 `event_speech.RecentLinePicker`。
        """
        try:
            picker = getattr(self, '_event_line_picker', None)
            if picker is not None:
                return picker.pick(pool)
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        try:
            items = [x for x in (pool or []) if isinstance(x, str) and x.strip()]
            return random.choice(items) if items else ""
        except Exception:
            return ""

    def _event_say(self, text, face="happy", streamed=False):
        """事件台词显示的唯一出口（`add_dialogue` + `show_dialogue` 成对，只写一次）。

        `streamed=True` 表示这句话在流式期间**已经逐字显示在前台**了 →
        交给 `dialogue_ui.add_dialogue(..., _streamed=True)` 走"定格"而不是"从头重打"。
        """
        if not text:
            return False
        try:
            dui = getattr(self, 'dialogue_ui', None)
            if dui is None:
                return False
            dui.add_dialogue("ralsei", text, face, _streamed=bool(streamed))
            dui.show_dialogue()
            self.last_interaction_time = time.time()
            return True
        except Exception as e:
            _log.warning(f"[事件台词] 显示失败: {e}")
            return False

    def _event_ai_ready(self, kind, instant=False):
        """这个事件能不能走 AI 档。任一条件不满足 → 走罐头，**绝不阻塞主人**。"""
        if instant or not self._event_speech_enabled():
            return False
        if tier_of(kind) != TIER_AI:
            return False
        dui = getattr(self, 'dialogue_ui', None)
        if dui is None:
            return False
        try:
            # 主人正在自己打字 → 别抢话
            if callable(getattr(dui, '_is_user_inputting', None)) and dui._is_user_inputting():
                return False
            # 主人那条请求还在路上（`_ai_inflight` 是 dialogue_ui 自己的状态位）→ 让路。
            # 这里**不能**用 `_ai_delta_sink` 判"对话在流式"：按 S8 的设计它收尾后
            # **故意不清空**，用它做门 = 开过一次流式之后所有事件永远走罐头
            # （写本套件时自查出来的；D22 就是钉这条的）。
            if getattr(dui, '_ai_inflight', False):
                return False
            # 屏幕上正有东西在流式打（对话的或上一个事件的）→ 别插进去
            if getattr(dui, '_streaming', False):
                return False
            # 等着回复（前台是「……」占位）：事件台词会把它顶掉
            if getattr(dui, 'typing_text', '') == getattr(dui, 'AI_THINKING_PLACEHOLDER', None):
                return False
            # 上一个事件还在等 AI（没到兜底时限）→ 不叠加第二个请求
            if getattr(self, '_event_speaking', False):
                return False
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return False
        # 频率闸：快速连戳不该连发请求（超限就当场说罐头）
        last = getattr(self, '_event_speak_last', None)
        if last is not None and (time.time() - last) < self.EVENT_SPEAK_MIN_INTERVAL:
            return False
        return True

    def speak_event(self, kind, pool=None, face="happy", instant=False):
        """事件台词唯一入口（S7）。三档行为见本节开头。

        **`pool` 的两种语义（2026-09-19 用户决定「所有对话全权交给 AI」后新增）**
        * 传了 `pool=[...]`：保留**内置台词**，AI 不可用/超时/判退时说出来。
          （batch 1/2 的历史调用点都走这条，行为与改造前一致。）
        * **不传（`pool=None`）**：**不给内置台词** —— 说不了就**不说话**，
          宁可安静也不甩一句写死的台词。这是"全权交给 AI"的口径，
          新迁移的台词一律走这条。返回值同样是 `""`（"这次什么都没说"）。
        """
        canned = self._pick_event_line(pool)
        # 有没有"内置台词可用"是后面所有退路的判据（空 = 允许沉默）
        has_canned = bool(canned)

        def _note(text):
            # 说过的话都要进去重窗口 —— 包括**罐头**。只在 AI 分支记的话，
            # "AI 关闭/超时"这条最常走的路径就永远学不到自己刚说过什么，
            # 去重形同虚设（这是写本套件时自查出来的）。
            try:
                self._event_line_picker.note(text)
            except Exception as e:
                _log.debug("main 防御性异常（已忽略）: %s", e)

        if not self._event_ai_ready(kind, instant):
            _note(canned)
            self._event_say(canned, face)
            return canned

        # 世代号：同一时间只认最新的一次事件，旧事件的迟到分片/回复直接丢弃
        self._event_speak_gen = getattr(self, '_event_speak_gen', 0) + 1
        gen = self._event_speak_gen
        self._event_speak_last = time.time()
        self._event_speaking = True
        dui = getattr(self, 'dialogue_ui', None)
        state = {'said': False, 'streaming': False}
        # 判退重采样只用一次（没有内置台词时才有意义，见 `_on_reply`）
        _retried = [False]

        def _fallback():
            """AI 这条走不通时的退路（超时 / 无响应 / 判退 / 发起失败都汇到这里）。

            `has_canned=False`（没给内置台词）时**什么都不说**：这不是漏了兜底，
            是"全权交给 AI"的口径 —— 沉默 > 甩一句写死的台词。
            唯一必做的清理是：若流式已经把半句画到屏幕上，先擦掉再退
            （否则屏幕上留着半句话，比不说更糟）。
            """
            self._event_speaking = False
            if state['said'] or gen != getattr(self, '_event_speak_gen', 0):
                return
            if state['streaming']:
                # 屏幕上已经打着半句 AI 台词 → 先擦掉再换罐头，
                # 否则罐头会接在半句后面像两句话黏一起（S8 的同一坑）
                try:
                    dui.stream_delta(None)
                    state['streaming'] = False
                except Exception as e:
                    _log.debug("main 防御性异常（已忽略）: %s", e)
            if not has_canned:
                return
            state['said'] = True
            _note(canned)
            self._event_say(canned, face)

        def _on_delta(chunk):
            # 主线程（`_api_delta` 信号）。世代号保证旧事件的分片不落到屏幕上。
            if gen != getattr(self, '_event_speak_gen', 0):
                return
            # **已经说过话了 → 迟到的分片一律丢弃**（真机 e2e 抓到的真 bug）。
            # 场景：首字超过兜底时限 → 先说了罐头 → 几百毫秒后模型的字才到。
            # 不丢的话有两个后果，第二个是致命的：
            #   ① 屏幕上会"罐头说完又冒出一句 AI 的话"（同一事件两句话）；
            #   ② `dui.stream_delta` 会把 dialogue_ui 切进流式态（`_streaming=True`），
            #      而这次事件之后**再没有人**去清它（`_on_reply` 因 `state['said']`
            #      提前返回）→ `_event_ai_ready` 的 `_streaming` 检查此后**永远为真**
            #      → 之后所有事件永久退回罐头（静默、无日志）。
            #      这与 D22 钉的 `_ai_delta_sink` 是同一类"永久挡死"，只是入口不同。
            if state['said']:
                return
            try:
                if chunk is None:
                    state['streaming'] = True
                    dui.stream_delta(None)      # 护栏判退 → 擦掉半句再重采样
                    return
                if not isinstance(chunk, str) or not chunk:
                    return
                state['streaming'] = True
                dui.stream_delta(chunk)
            except Exception as e:
                _log.debug("main 防御性异常（已忽略）: %s", e)

        def _on_reply(reply):
            # 回调由 `_api_result` 信号投递 → 主线程（chat_with_ai 的约定）
            self._event_speaking = False
            text = ""
            if reply is not None:
                try:
                    # 先截成一句、再过"出戏闸"（3B 实测会吐「我没有触觉无法感受…」）
                    text = guard_reaction(
                        first_sentence(reply, self.EVENT_SPEAK_MAX_CHARS))
                except Exception as e:
                    _log.debug("main 防御性异常（已忽略）: %s", e)
                    text = ""
            if not text:
                # 没拿到可用句子（AI 沉默 / 无响应 / 被判退）。三条路：
                #   ① 有内置台词 → 说罐头（batch 1/2 的历史口径，行为不变）
                #   ② **没有**内置台词且还没重试过 → 同一提示词再要一次
                #      （temperature 0.85 重采样；**不改提示词**是为了保住 KV 前缀缓存，
                #       改写提示词会让首字从 0.24s 掉回 0.85s 量级）
                #   ③ 没有内置台词且已重试过 → 沉默（`_fallback()` 里 has_canned=False 直接返回）
                if not has_canned and not _retried[0]:
                    _retried[0] = True
                    if state['streaming']:
                        # 上一轮已经把半句画上屏幕了 → 先擦掉再要一次，
                        # 否则新旧两句会黏在一起
                        try:
                            dui.stream_delta(None)
                            state['streaming'] = False
                        except Exception as e:
                            _log.debug("main 防御性异常（已忽略）: %s", e)
                    self._event_speaking = True
                    try:
                        self.chat_with_ai(build_prompt(kind), _on_reply, _on_delta, lean=True)
                    except Exception as e:
                        _log.debug(f"[事件台词] 重采样发起失败: {e}")
                        _fallback()
                    return
                _fallback()
                return
            if state['said'] or gen != getattr(self, '_event_speak_gen', 0):
                return
            state['said'] = True
            _note(text)
            # 流式期间已经打过字了 → 走"定格"；否则从头打字机
            self._event_say(text, face, streamed=state['streaming'])

        # 事件先行"开口"：流式要把字打进对话框，框子得先可见；同时打出「……」
        # （主人戳一下 → 框子立刻冒出来 + 显示 Ralsei 式省略号 → 0.8s 后开始出字，
        #  比"框子空着不动"自然；也让"等着首字"的那段时间有明确观感）。
        # `_ai_thinking_on()` 是对话链路（`send_message`）用的同一个等待态助手：
        # 它会先提交上一条前台消息、停掉自动隐藏，并把占位写进 typing_text ——
        # 占位**不会被并入历史**（`dialogue_ui.add_dialogue` 显式丢弃它）。
        try:
            if dui is not None:
                dui.show_dialogue()
                dui._ai_thinking_on()
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        try:
            # `lean=True` 是 S7 的关键一笔：事件请求只发 persona、不发上下文与历史，
            # 这样 system **一词不变** → 每次事件都命中 Ollama 的 KV 前缀缓存 →
            # 首字从 2.5~3.0s 回到 0.6s 量级，才可能在 1200ms 内出字走 AI。
            # 不加这个词，本批 20 处迁移在生产里**全部**退化成罐头（已实测）。
            self.chat_with_ai(build_prompt(kind), _on_reply, _on_delta, lean=True)
        except Exception as e:
            _log.debug(f"[事件台词] 发起失败，退路处理: {e}")
            _fallback()
            return canned
        # 兜底：**首字**都没到（网络/模型无响应）才说罐头。时限只需覆盖首字。
        # 兜底：**首字**都没到（网络/模型无响应）才算这一轮没戏。时限只需覆盖首字。
        QTimer.singleShot(
            int(self.EVENT_SPEAK_FIRST_TOKEN_MS),
            lambda: None if (state['streaming'] or state['said']) else _fallback())
        return None

    def moveEvent(self, event):
        super().moveEvent(event)

    def paintEvent(self, event):
        # 绘制透明背景
        # 修复：原先无显式 end()，中途抛异常会留下 active painter，
        # Qt 会打印 "QPainter::begin: Painter already active"。
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.fillRect(self.rect(), QBrush(QColor(0, 0, 0, 0)))
        finally:
            painter.end()
        
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
            # 空中接住：坠落途中按下鼠标 = 抓住（含"线速度缓冲减速"，不做撞墙式急停）
            self._catch_falling_in_air()
            # 甩飞判定重做（用户反馈"判定范围太广"）：记录 (时间戳, x, y) 采样序列，
            # 松手时用"最近 120ms 内的真实速度 px/s"判定，而不是"相邻两次事件的像素差"。
            # 旧逻辑把位移当速度用，慢拖一大步也会 >150 被判甩飞；且最后两次采样可能是
            # 一秒前的老数据，用户拖完停住再松手照样飞出去。
            self._drag_samples = []
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
                    self.speak_event("splat_poked", ["别戳我啦...我都扁了..."], "sad", instant=True)
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
                            self.speak_event("ear_ruffle", ["哎呀！别不楞我的耳朵啦！"], "surprised", instant=True)
                            # 重置点击计数
                            self._pet_detection_state['click_count'] = 0
                    else:
                        # 重置点击计数
                        self._pet_detection_state['click_count'] = 1
                        
                    # 更新最后点击时间
                    self._pet_detection_state['last_click_time'] = current_time
                
                # 根据不同部位触发不同效果
                if clicked_part == "body":
                    # 轻点躯干：好奇地歪头看看，而不是质问"你推我干嘛"
                    _log.debug("轻点了Ralsei的躯干！")
                    self.emotion_system.add_emotion("happy", 15)
                    self.emotion_system.add_emotion("curious", 10)
                    self.play_animation_once("look_up")
                    body_responses = ["嗯？怎么啦？", "诶？有什么事吗？", "嘿嘿~ 你戳我啦"]
                    self.speak_event("poke_body", body_responses, "curious")
                elif clicked_part == "shoulder":
                    # 轻推肩膀
                    _log.debug("轻推了Ralsei的肩膀！")
                    self.emotion_system.add_emotion("happy", 20)
                    self.emotion_system.add_emotion("curious", 10)
                    self.play_animation_once("look_up")
                    self.speak_event("poke_shoulder", ["嗯？有什么事吗？"], "curious")
                else:
                    # 显示点击回应
                    short_responses = ["嘿嘿！", "你好呀！", "很高兴见到你！", "要一起玩吗？"]
                    self.speak_event("poke_default", short_responses, "happy")
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
            
            # 保存上次拖拽位置
            self._last_drag_pos = target_pos

            # 甩飞判定/速度判定用采样：时间戳 + 位置（保留最近 30 个足够覆盖 120ms 窗口）
            if not isinstance(getattr(self, '_drag_samples', None), list):
                self._drag_samples = []
            self._drag_samples.append((time.time(), target_pos.x(), target_pos.y()))
            if len(self._drag_samples) > 30:
                del self._drag_samples[:-30]

            # ===== 位置跟踪：1:1 跟随鼠标 =====
            # 第六轮（"动作的触发逻辑完全不对"）：原来每帧只移动与目标间距的 20%
            # （elastic_factor=0.2），被拖起来的东西却"粘不住手、还往回弹"——
            # 人拎起东西时东西是跟着手走的。现在直接跟随。
            self._drag_elastic_pos = target_pos
            self.move(target_pos)

            # ===== 拖拽速度与方向：一律换算成 px/秒 =====
            # 旧实现把"相邻两次事件的像素差"当速度用，速度随鼠标事件频率变化，
            # 于是"慢慢拖一大步"也会被判成猛烈拖拽（惊讶表情乱触发）。
            drag_speed = 0.0            # px/s
            dx_prev = dy_prev = 0.0
            _sp = self._drag_samples
            if len(_sp) >= 2:
                _t0, _x0, _y0 = _sp[-2]
                _t1, _x1, _y1 = _sp[-1]
                _dt = max(1e-3, _t1 - _t0)
                dx_prev = float(_x1 - _x0)
                dy_prev = float(_y1 - _y0)
                drag_speed = ((dx_prev ** 2 + dy_prev ** 2) ** 0.5) / _dt
            self._drag_speed = drag_speed

            # 猛烈拖拽（>1200 px/s）才给"被甩来甩去"的惊讶反应
            if drag_speed > 1200.0:
                if not getattr(self, '_drag_surprised', False):
                    self._drag_surprised = True
                    self.pet_ai.react_to_event("user_dragged_forcefully", None)
            else:
                self._drag_surprised = False

            if abs(dx_prev) > abs(dy_prev):
                current_dir = "right" if dx_prev > 0 else "left"
            else:
                current_dir = "down" if dy_prev > 0 else "up"
            self.current_direction = current_dir

            # ===== 被拎起来时的动画 =====
            # 人在被拎着**挣扎**时腿才乱蹬；被稳稳拎着不动时是安静的。
            # 原来无论动没动都强制 run_*，于是"拎在半空原地跑"，很假。
            if drag_speed > 400.0:
                drag_animation = f"run_{current_dir}"
            else:
                drag_animation = "cower" if "cower" in self.sprite_loader.sprites else "idle"

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
                            self.speak_event(pet_kind(pet_part), response_list, "happy")
                            
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
            # ===== 松手判定（第六轮从 mouseMoveEvent 搬来）=====
            # 原来这段写在 mouseMoveEvent 的"左键已松开"分支里：只有再动一次
            # 鼠标才会被处理。甩出去后手一停就永远不触发；松手后随便挪一下
            # 鼠标又会用过期采样补触发 —— 表现就是"过一会儿自己飞一下"。
            # 松手就该在 mouseReleaseEvent 处理。
            # 处理拖拽释放时的物理反馈效果
            if getattr(self, '_last_drag_pos', None) is not None:
                # ===== 释放速度：单位 px/秒（真实速度，而非"两次事件的像素差"）=====
                # 用户反馈"甩飞判定范围太广"：150 是像素差阈值，慢拖一步就能过。
                # 现在改为真实速度 + 时效性校验：
                #   ① 只取最近 120ms 窗口内的采样算速度；
                #   ② 若最后一次采样距松手超过 0.25s（已停住），速度视为 0 → 轻放。
                release_speed = 0.0   # px/s
                rel_vx = 0.0          # 释放瞬时水平速度 px/s（带符号）
                rel_vy = 0.0          # 释放瞬时竖直速度 px/s（带符号，负=向上）
                dx = 0.0
                dy = 0.0
                _samples = getattr(self, '_drag_samples', None)
                if isinstance(_samples, list) and len(_samples) >= 2:
                    _t_new, _x_new, _y_new = _samples[-1]
                    _idx = len(_samples) - 1
                    while _idx > 0 and (_t_new - _samples[_idx - 1][0]) <= 0.12:
                        _idx -= 1
                    _t_old, _x_old, _y_old = _samples[_idx]
                    _dt = max(1e-3, _t_new - _t_old)
                    if (time.time() - _t_new) <= 0.25:
                        dx = float(_x_new - _x_old)
                        dy = float(_y_new - _y_old)
                        rel_vx = dx / _dt
                        rel_vy = dy / _dt
                        release_speed = (rel_vx ** 2 + rel_vy ** 2) ** 0.5
                    else:
                        # 拖完停住再松手 = 轻放，绝不甩飞
                        release_speed = 0.0
                        rel_vx = rel_vy = 0.0
                        dx = dy = 0.0

                # 甩飞门槛：900 px/s（约"猛地一甩"的力度）。低于此值只是普通放下。
                _FLING_SPEED = 900.0
                # 弹跳门槛：250 px/s（轻甩一下的小跳，不会摔）
                _BOUNCE_SPEED = 250.0

                if release_speed > _FLING_SPEED:
                    # 极快释放，触发甩飞效果
                    # 分阶段：飞行(抛物线) → 摔扁splat → 晕乎揉头 → 爬起恢复
                    self.is_falling = True
                    self.is_recovering = False
                    self.fall_duration = 0.0
                    self._fall_phase = "flying"  # flying → splat → dazed → recovering
                    self._fall_phase_start = 0.0
                    self._fall_flight_time = 0.0
                    self._fall_landed = False
                    self.max_fall_duration = 3.5  # 总摔倒时长（飞行+摔扁+晕乎）
                    self.recovery_max_duration = 2.0
                    # 第十七轮：显式复位**坠落起因**。甩飞是另一套交互（抛物线 + 二次抓），
                    # 不属于建楼要求第36/37行的"我的行为导致他摔到楼板/桌面"。
                    # 不复位的话，上一次"关窗摔落"留下的 `_fall_reason='floor_removed'`
                    # 会让这次甩飞也栽进生气版 splat 并原地待满 5s（动画错了、时长也错了）。
                    # 时长/素材都由 `_fall_reason` 派生，所以只清这一个就够。
                    self._fall_reason = None

                    # 飞行阶段：jump_ball 动画
                    throw_animation = "jump_ball"
                    if throw_animation in self.sprite_loader.sprites:
                        self.change_animation(throw_animation, force=True)
                    else:
                        self.change_animation("fall", force=True)

                    # ===== 斜抛初速：完全由"松手瞬间的速度矢量"决定 =====
                    # 用户反馈："被甩飞时候的那个抛物线是斜抛运动，轨迹要由初速度方向
                    # 和大小决定"。原实现把竖直分量强行掰成向上：
                    #     if _vy > -350.0: _vy = -350.0 - abs(_vy) * 0.5
                    # 于是"横着甩"和"往下甩"都会被改成上抛，方向完全不对。
                    # 现在只做等比缩放 + 整体限幅：
                    #   · 等比缩放 → 保持方向（角度）不变，只改速度大小；
                    #   · 限幅按**矢量和**做 → 不会像逐分量限幅那样把角度掰弯。
                    # 不注入任何额外分量，水平甩就是水平斜抛，下甩就直接往下走。
                    _LAUNCH_SCALE = 0.55
                    _vx = rel_vx * _LAUNCH_SCALE
                    _vy = rel_vy * _LAUNCH_SCALE
                    _v_mag = (_vx ** 2 + _vy ** 2) ** 0.5
                    _MAX_LAUNCH_SPEED = 1600.0
                    if _v_mag > _MAX_LAUNCH_SPEED:
                        _k = _MAX_LAUNCH_SPEED / _v_mag
                        _vx *= _k
                        _vy *= _k
                    self._fall_vx = _vx
                    self._fall_vy = _vy
                    self._fall_launch_y = self.pos().y()
                    # 兼容旧的滑行字段（handle_fall 里已改用 _fall_vx/_fall_vy，
                    # 这里仍写入一份，防止其它分支读旧字段时为空）
                    self.fall_slide_speed_x = _vx
                    self.fall_slide_speed_y = 0.0

                    # 显示惊讶对话
                    self.speak_event("fling", ["哇啊——！"], "surprised", instant=True)
                elif release_speed > _BOUNCE_SPEED:
                    # 快速释放时，添加弹跳效果
                    self._bounce_params = {
                        'start_time': time.time(),
                        'start_pos': self.pos(),
                        'velocity_y': -min(600.0, release_speed * 0.5),  # 向上的初速度(px/s)
                        'gravity': 1800,  # 重力加速度(px/s^2)
                        'damping': 0.55,  # 阻尼系数
                        'bounce_count': 0,
                        'max_bounces': 3
                    }

                    # 启动弹跳定时器
                    if not hasattr(self, '_bounce_timer'):
                        self._bounce_timer = QTimer(self)
                        self._bounce_timer.timeout.connect(self.update_bounce)
                    self._bounce_timer.start(30)

                # 添加旋转阻尼效果
                if release_speed > 120.0:
                    self._rotation_damping = {
                        'start_time': time.time(),
                        'initial_angle': max(-25.0, min(25.0, dx * 0.08)),  # 初始旋转角度
                        'damping_factor': 0.9,
                        'target_angle': 0
                    }
                if isinstance(getattr(self, '_drag_samples', None), list):
                    del self._drag_samples
                
                # 移除拖拽相关属性
                if hasattr(self, '_drag_elastic_pos'):
                    delattr(self, '_drag_elastic_pos')
                if hasattr(self, '_drag_surprised'):
                    delattr(self, '_drag_surprised')
                if hasattr(self, '_last_drag_pos'):
                    delattr(self, '_last_drag_pos')
            # 检查是否在Ralsei身上释放
            if hasattr(self, '_pet_detection_state') and self._pet_detection_state['is_pressing'] and not getattr(self, 'is_falling', False):
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
                        self.speak_event("pinch_ear", ["哎呀！别捏我的耳朵！好痒呀！"], "surprised")
                    elif clicked_part == "arm":
                        # 拉住手臂
                        _log.debug("拉住了Ralsei的手臂！")
                        self.emotion_system.add_emotion("happy", 30)
                        self.play_animation_once("wave")
                        self.speak_event("pull_arm", ["嘿嘿~ 别拉我的手臂啦！"], "happy")
                    elif clicked_part == "body":
                        # 按住躯干
                        _log.debug("按住了Ralsei的躯干！")
                        self.emotion_system.add_emotion("happy", 25)
                        self.emotion_system.add_emotion("shy", 20)
                        self.play_animation_once("happy")
                        self.speak_event("press_body", ["嗯~ 好舒服！"], "happy")
                    elif clicked_part == "belly":
                        # 拍肚子
                        _log.debug("拍了Ralsei的肚子！")
                        self.emotion_system.add_emotion("happy", 40)
                        self.emotion_system.add_emotion("excited", 20)
                        self.play_animation_once("laugh")
                        self.speak_event("pat_belly", ["嘿嘿~ 我的肚子很软哦！"], "happy")
                    elif clicked_part == "face":
                        # 轻轻捏脸
                        _log.debug("轻轻捏了Ralsei的脸！")
                        self.emotion_system.add_emotion("happy", 30)
                        self.emotion_system.add_emotion("shy", 30)
                        self.play_animation_once("surprised")
                        self.speak_event("pinch_face", ["哎呀~ 别捏我的脸！"], "shy")
                    elif clicked_part == "shoulder":
                        # 拉住肩膀
                        _log.debug("拉住了Ralsei的肩膀！")
                        self.emotion_system.add_emotion("happy", 25)
                        self.emotion_system.add_emotion("shy", 15)
                        self.play_animation_once("pose")
                        self.speak_event("pull_shoulder", ["谢谢你拉我的肩膀！"], "happy")
                
                # 重置长按状态
                self._pet_detection_state['is_pressing'] = False
                self._pet_detection_state['press_start_time'] = 0
                self._pet_detection_state['press_start_pos'] = None
    
        # 松手后立刻按"一层压一层"归位一次。
        # 必要性：用户拖动宠物时窗口会被激活 → Windows 把宠物提到同组最前，
        # 不重排的话它就一直浮在所站楼板前面的窗口之上了（遮挡关系失效）。
        # 这里不节流 —— 松手是低频事件，一次 SetWindowPos 可忽略不计。
        try:
            if not self.is_falling and not self.is_jumping:
                self._apply_pet_z_order()
        except Exception as e:
            _log.debug("松手后重排 z 序失败（已忽略）: %s", e)

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
                self.speak_event("double_hair", ["嘿嘿~ 摸头杀好舒服！"], "happy")
            elif clicked_part == "belly":
                # 拍肚子（双击）
                _log.debug("用力拍了Ralsei的肚子！")
                self.emotion_system.add_emotion("happy", 45)
                self.emotion_system.add_emotion("excited", 25)
                self.play_animation_once("laugh")
                self.speak_event("double_belly", ["哈哈！别用力拍我的肚子啦！"], "laughing")
            elif clicked_part == "face":
                # 捏脸
                _log.debug("捏了Ralsei的脸！")
                self.emotion_system.add_emotion("happy", 40)
                self.emotion_system.add_emotion("shy", 40)
                self.play_animation_once("surprised")
                self.speak_event("double_face", ["哎呀！别捏我的脸！"], "surprised")
            elif clicked_part == "shoulder":
                # 拍拍肩膀
                _log.debug("拍拍Ralsei的肩膀！")
                self.emotion_system.add_emotion("happy", 35)
                self.emotion_system.add_emotion("caring", 20)
                self.play_animation_once("wave")
                self.speak_event("double_shoulder", ["谢谢你拍拍我的肩膀！"], "happy")
            else:
                # 修复：双击耳朵/手臂/腿/躯干等未单独列出的部位时，
                # 原来会落到外层 else 触发"显示/隐藏对话框"（窗口级行为），
                # 在 sprite 内点击却切对话框，交互错乱。改为统一的友好反应。
                _log.debug(f"双击了Ralsei的: {clicked_part}")
                self.emotion_system.add_emotion("happy", 20)
                self.emotion_system.add_emotion("shy", 10)
                self.play_animation_once("happy")
                self.speak_event("double_other", ["嘿嘿~ 你对我真好！"], "happy")
        else:
            # 双击其他区域，显示/隐藏对话框
            if self.dialogue_ui.isVisible():
                self.dialogue_ui.hide_dialogue()
            else:
                self.dialogue_ui.show_dialogue()
    
    # 第三十四轮删除：此前的 `mouseEnterEvent` / `mouseLeaveEvent` **不是 Qt 的事件钩子名**
    # （QWidget 的钩子是 `enterEvent` / `leaveEvent`），Qt 从不派发它们 —— 写得再对也永远不执行。
    # 三重实证见 code-quality-audit/第34轮-移动行为基础代码严查/_evidence/03_Qt事件钩子取证.txt。
    # 其唯一实质动作（光标手型切换）已由 `mouseMoveEvent` 里的
    # `setCursor(Qt.PointingHandCursor/ArrowCursor)`（见"检查鼠标是否在Ralsei身上"一段）逐帧覆盖，
    # 故删除不损失任何功能；保留则会误导后来者以为存在悬停钩子。
    def on_mouse_hover(self):
        # 鼠标悬停时的处理
        # 用户要求（第八轮）："所有特殊动画……都只交给 AI 判断是否播放，别和抽风似的突然一下。"
        # 原来这里有一个 `random.random() < 0.01` 的 1% 概率 `play_animation_once("look_up")`
        # —— 属于非 AI 的随机特殊动画（宠物会毫无来由地突然抬头），已删除。
        # 悬停只保留"光标变手型"这类纯 UI 反馈，实际由 `mouseMoveEvent` 逐帧施加。
        return
    
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
        self.api_enabled_checkbox = QCheckBox("启用AI对话（第六轮起：主动开口只走 AI；未启用时回复用内置规则、且从不主动搭话）")
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
        self.fps_spinbox.setValue(self.config_manager.get("animation.fps", 6))
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
        # 第十八轮：options（对话采样参数）同样没有控件，一并按现有值保留 ——
        # 否则用户点一次"保存配置"就会把 temperature 悄悄打回旧行为。
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
            'retry_delay': _cur_cfg.get('retry_delay', 1.0),
            'options': _cur_cfg.get('options', {'temperature': 0.85, 'max_tokens': 256})
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
        # 让新的帧率立即生效：定时器周期需跟随重启（半周期，节拍由帧闸门决定）
        try:
            self._anim_tick_ms = max(16, int(self.animation_frame_delay * 0.5))
            self.animation_timer.start(self._anim_tick_ms)
        except Exception as e:  # 配置保存不能因为定时器重启失败而中断
            _log.debug("main 防御性异常（已忽略）: %s", e)
        self.min_speed = self.min_speed_spinbox.value()
        self.max_speed = self.max_speed_spinbox.value()
        
        # 关闭对话框
        dialog.accept()
        
        # 显示保存成功消息
        self.dialogue_ui.add_dialogue("ralsei", "配置已保存！", "happy")
        self.dialogue_ui.show_dialogue()
    
    def initiate_chat(self):
        # 发起聊天（用户主动点菜单）：开场白同样交给 AI，不再用内置模板台词。
        # 用户主动发起 → 不受 10 分钟自主开口闸门限制。
        if not self.dialogue_ui.isVisible():
            self.dialogue_ui.show_dialogue()
        if not self.start_autonomous_speech("user_chat", user_requested=True):
            _log.debug("[聊天] AI 未启用/此刻不适合开口——对话框已打开，用户可直接输入")
    
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
        self.speak_event("feed", ["谢谢你喂我！肚子饱饱的，好幸福~"], "happy")
    
    def pet_ralsei(self):
        # 抚摸Ralsei
        self.emotion_system.add_emotion("happy", 40)
        self.play_animation_once("nuzzle")
        self.speak_event("pet_menu", ["嘿嘿~ 好舒服呀！"], "happy")
    
    def change_animation_randomly(self):
        # 随机切换动画（用户主动从菜单点的，所以可以活泼一些）
        # 修复：只从适合主动表演的动画中选，不选 splat/fall/shocked 等受伤/摔倒状态。
        # 人不会主动把自己摔扁然后开心地说"看！我在做splat！"
        safe_performance_anims = [
            "dance", "sing", "wave", "bow", "laugh", "look_up", "pose",
            "curtsy", "spin", "hug", "tea", "slide", "roll", "nuzzle",
            "item", "act", "victory",
        ]
        available = [a for a in safe_performance_anims if a in self.sprite_loader.sprites]
        if available:
            new_animation = random.choice(available)
            self.play_animation_once(new_animation)
            self.dialogue_ui.add_dialogue("ralsei", f"看！我会做这个动作~", "happy")
            self.dialogue_ui.show_dialogue()
    
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
    
    @staticmethod
    def _is_special_anim(name):
        """该动画是不是"特殊动画"（见模块级 _NON_SPECIAL_ANIM_GROUPS 的说明）。"""
        if not name:
            return False
        group = name.split('_')[0] if '_' in name else name
        return group not in _NON_SPECIAL_ANIM_GROUPS

    def _special_anim_locked(self):
        """当前是否处于"特殊动画正在播放"的锁定状态。

        锁定条件 = 一次性动画进行中（_play_once_active）**且**当前动画属于特殊类。
        walk/run/idle 与物理/施法动画即便走 play_animation_once 也不锁
        （例如 `play_animation_once("land")` 是摔倒恢复流程，必须能被后续状态接管）。
        """
        return bool(getattr(self, '_play_once_active', False)
                    and self._is_special_anim(self.current_animation))

    def change_animation(self, new_animation, force=False):
        # 安全地切换动画，带有冷却时间检查、优先级系统、spell 阶段硬拦截
        current_time = time.time()
        
        # 1) 动画不存在时：按 parts 从长到短回退到基础动画，仍找不到 → 拒绝
        #    H5 S1：这里是"静默退化"的主要发生地（回退 idle / 直接拒绝切换都不会有任何
        #    反馈）。在此记账 + 告警，行为与改造前完全一致，只是多了一条可见日志。
        if new_animation not in self.sprite_loader.sprites:
            _requested = new_animation
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
                self.sprite_loader.note_animation_miss(_requested, None, 'change_animation')
                return False
            self.sprite_loader.note_animation_miss(_requested, found, 'change_animation')
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
        
        # ========== 关键 1.6：特殊动画"播完为止"，不允许被另一个特殊动画打断 ==========
        # 用户要求（第八轮）："如果要是播放，那就播完，不要打断……（注意，只针对特殊动画）"
        # 只拦"特殊 → 特殊"：目标是 idle/walk/run/jump/fall/splat/land/spell/item 时一律
        # 放行 —— 那些代表状态真的变了（开始走路、摔下去、AI 施法、一次性动画收尾），
        # 拦掉反而会让宠物卡在动作里。
        # `_play_once_arming` 是"正在发起这一次性动画"的短暂标记，用于放行
        # play_animation_once 自己那次 change_animation（否则会把自己锁在门外）。
        if (getattr(self, '_play_once_active', False)
                and not getattr(self, '_play_once_arming', False)
                and new_animation != self.current_animation
                and self._is_special_anim(self.current_animation)
                and self._is_special_anim(new_animation)):
            _log.debug("[动画] 特殊动画 %r 播放中，拒绝被 %r 打断",
                       self.current_animation, new_animation)
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
                        # 检查PPT文件。修复：原来调用的 check_ppt_windows / check_ppt_files
                        # 都是 main 上不存在的方法（AttributeError），而且那两条是"内置台词"
                        # 生成器（第六轮已删）。这里只做事实性回答。
                        try:
                            _ppt = self.desktop_interaction.check_ppt_files()
                        except Exception as e:
                            _log.debug("main 防御性异常（已忽略）: %s", e)
                            _ppt = []
                        self.dialogue_ui.add_dialogue(
                            "ralsei", f"我找了一下，桌面上有 {len(_ppt or [])} 个 PPT 文件。", "curious")
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
                        # 原 check_browser_windows 是"内置台词"生成器（第六轮已删），
                        # 这里改成事实性回答：报出当前检测到的浏览器窗口数量。
                        try:
                            _bw = self.desktop_interaction.identify_browser_windows()
                        except Exception as e:
                            _log.debug("main 防御性异常（已忽略）: %s", e)
                            _bw = []
                        self.dialogue_ui.add_dialogue(
                            "ralsei", f"现在开着 {len(_bw or [])} 个浏览器窗口呢。", "curious")
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

    def chat_with_ai(self, text, on_reply, on_delta=None, lean=False):
        """把用户输入交给本地 AI（后台线程，不卡 UI），完成后在主线程回调
        on_reply(reply_str 或 None)。

        - 未启用 API / api_client 未实现 / 请求失败 / 超时：一律回调 None，
          由调用方回退到内置规则对话。
        - 这是"培养的本地 Ralsei"（Ollama / OpenAI 兼容端点）的主对话端口：
          配置对话框里填 base_url + model（如 http://localhost:11434 / ralsei）即可。
        - 训练调优：把「角色设定 + 当前状态上下文 + 最近对话历史」一起交给模型，
          让 Ralsei 的对话连贯、贴角色、能感知当下（时间/天气/心情/精力/记忆）。
        - **流式（S8）**：传了 `on_delta` 且配置开启 `api.stream` 时，模型每吐一段
          就回调一次（在主线程上），对话框可以"边收边打"，首字延迟从
          "整句生成完"（实测 0.9~6.0s）降到 ~0.23s；`on_delta(None)` 表示
          "把已经显示出去的半句擦掉"（护栏判退后要重采样）。
        - **lean（S7 事件台词专用）**：只发 persona，**不发**上下文/话题锚/记忆召回
          与对话历史。原因不是省 token，是**省 prefill**：Ollama 的 KV 前缀缓存只
          复用"从头逐字相同"的那一段，而上下文尾巴每轮都变（时段/精力/话题/回忆），
          实测让首字从 0.63s 涨到 1.82s（+1.19s），history 再 +0.52s —— 叠加后
          2.5~3.0s，**必超** S7 的 1200ms 首字兜底，事件 AI 等于永远不生效。
          证据：`code-quality-audit/人味改造-2026-09-18/_evidence/probe_prefix_cache.txt`。
          代价：事件回复不再知道"现在几点/刚才在聊什么"—— 事件是 ≤24 字的触觉反应，
          不需要这些；**对话路径（send_message）不传 lean，行为不变**。
        """
        # 载体层状态：记下"主人刚开口"的时刻。主线程写、主线程读（本方法在主线程调用），
        # 供 _build_ai_context 派生"被冷落多久"这类语气 —— 模型自己看不到时钟，
        # 也看不到"主人已经很久没理我"这种**跨轮**事实，这类状态只有 App（载体）持有。
        # 刻意放在 api_enabled 判断**之前**：AI 关着的时候也要记，否则一关开关就"失忆"，
        # 再打开会立刻说"主人很久没跟我说话了"（把开关当成冷落）。
        try:
            self._last_user_chat_ts = time.time()
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        if not self.api_enabled:
            try:
                on_reply(None)
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
            return
        import threading

        # —— 流式接收方登记（只在主线程做，工作线程只读快照）——
        # 世代号：同一时间只允许一个请求往对话框写字。用户在新消息里已经
        # 递增过 dialogue_ui 的 _ai_seq，这里再发一道"分片级"的闸。
        _stream_on = bool(callable(on_delta)) and self._ai_stream_enabled()
        self._ai_delta_gen = getattr(self, '_ai_delta_gen', 0) + 1
        _gen = self._ai_delta_gen
        self._ai_delta_sink = on_delta if _stream_on else None

        # —— 主线程先准备好上下文与历史（避免工作线程跨线程读 UI/子系统状态）——
        # 第十八轮：用户消息保持**纯原话**。【此刻】/话题锚/记忆召回一律挂到 system 尾部。
        # 实测把它们拼在用户消息前面时，模型会把它当成"用户说的那段话"，
        # 甚至直接复述成回答（见 Ralsei对话人味诊断与训练方案_2026-09-18.md §E4-V0）。
        user_msg = text
        history = []
        # lean（事件台词）**不发历史**：历史每轮都在变，同样让前缀缓存失效
        # （实测 +0.52s），而且触点反应本来就不需要"接着上一句说"。
        if not lean:
            try:
                history = self.dialogue_ui.get_ai_history(limit=6) \
                    if getattr(self, 'dialogue_ui', None) else []
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
        # 角色系统提示词：**单一真源 = assets/ralsei_persona.md**（内含"我是谁 /
        # 我现在在哪 / 我怎么说 / 示范"四节）。
        # 为什么必须由 App 发过去：实测 Ollama 会用 messages 里的 system **整体替换**
        # Modelfile 的 SYSTEM（不传 system 时角色设定生效 prompt_eval_count=1237，
        # 传了之后骤降到 41）——也就是说，只把设定写在模型的 Modelfile 里，
        # 在真实应用里**一次都不会生效**。
        system = self._build_persona_prompt()
        # lean（事件台词）：**只发 persona，一个字节都不变** → 每次事件都命中
        # KV 前缀缓存 → 首字回到 0.6s 量级（实测见 docstring 的 probe 出处）。
        # 注意这里连 `_build_ai_context()` 都跳过：它内部会读天气/情绪/记忆，
        # 开销虽小但**每轮结果不同**，挂了就等于把缓存打掉。
        _ctx = "" if lean else self._build_ai_context()
        # 环境信息作为独立小节挂在 system 尾部，而不是塞进用户消息
        if _ctx:
            system = system + "\n\n" + _ctx
        # 对话注意力（第九轮）：把"我们现在在聊什么"交给模型。
        # 用户要求："把那个 AI 整的有些注意力哈，别到时候聊着一个话题呢突然就切换了。"
        # 只把最近的 6 轮原文交给模型，它每轮都要自己猜"该聊什么"，很容易被一句话带跑；
        # 这里补上显式的注意力焦点（当前话题 + 轮数 + 悬置问题），
        # 并明确要求"除非主人自己换话题，否则别跳"。见 modules/conversation_focus.py。
        try:
            _focus = (self.dialogue_ui.get_focus_brief()
                      if getattr(self, 'dialogue_ui', None) is not None else "")
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
            _focus = ""
        if _focus and not lean:
            system = system + "\n\n" + _focus

        # 记忆（第九轮）：由主人这句话联想"零星的记忆片段"，让 Ralsei 自然地想起来。
        # 要求："在需要的时候脑子里会根据一些零星的记忆片段自动重构当时的场景"。
        # 只在真想起东西时才拼进提示词（recall_text 无命中返回空串），不会硬编。
        try:
            _ms = getattr(self, 'memory_system', None)
            # lean：recall_text 会跑记忆图检索（比其它几项都贵），事件也用不上
            _recall = (_ms.recall_text(text, limit=3)
                       if not lean and _ms is not None
                       and callable(getattr(_ms, 'recall_text', None)) else "")
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
            _recall = ""
        if _recall and not lean:
            system = system + "\n\n" + _recall

        # 初始记忆（第二十轮）：世界观**不再常驻 system 前缀**，改成按需召回。
        # 用户口径：「没必要每次让他说话的时候都读取完整的世界观啊，可以按照语言的
        # 关联性去单个读取或是一定范围内读取，就和咱那个记忆系统一样，或是说这个
        # 世界观本就是他自己自带的初始记忆」。
        # 收益有两层，第二层更要紧：
        #   ① 常驻前缀 ~4380 → ~2800 tokens；
        #   ② **保 KV 前缀缓存** —— 世界观原是 system 中部的固定长文本，
        #      它一抽掉，骨架前缀更短且更稳，Ollama 复用的那一段更不容易被打断。
        # lean（事件台词）跳过：事件是 ≤24 字的触觉反应，聊不到"黑暗喷泉"这类话题，
        # 而它每轮都要跑一遍词表匹配 —— 省下的 prefill 比省 token 重要。
        # 失败一律静默：召回不到就当这轮没聊到那边（返回空串），绝不让链路掉线。
        try:
            _wv = ""
            if not lean:
                _wv = getattr(self, '_worldview_recall_text', None)
                if not callable(_wv):
                    from modules import worldview_recall as _wr
                    _wv = _wr.recall_text
                    self._worldview_recall_text = _wv
                _wv = _wv(text, limit=2)
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            _wv = ""
        if _wv:
            system = system + "\n\n" + _wv

        # 关系（第二十轮）：把**当前档位**变成一句话挂进 system。
        # 位置刻意在所有"临时状态"（【此刻】/话题锚/回忆/想起的事）**之前** ——
        # 关系比这些变化得慢得多，放在前缀更靠前的位置，跨轮更容易保持逐字相同，
        # KV 缓存复用得更长（Ollama 只复用"从头逐字相同"的那一段）。
        # lean（事件台词）跳过：事件是 ≤24 字的触觉反应，装不下"态度的差别"，
        # 而且它每轮都要重算 —— 那正是 S7 首字兜底要避开的东西。
        # 记账也放在这里：**只有真发起了一轮对话才算一次相处**（见下）。
        _rel_brief = ""
        try:
            _rel = getattr(self, 'relationship', None)
            if _rel is not None and not lean:
                # 先记账再取 brief：这样"这一轮"的影响立刻体现在语气上，
                # 而不是延迟一轮（用户能感知到的延迟 = "他反应慢半拍"）。
                # 事件类型由轻量规则判定（modules/relationship.classify），
                # 确定性、可回归；判错也只是多涨/少涨一点点，不会走样。
                from modules import relationship as _relmod
                _ev = _relmod.classify(text)
                _old_st, _new_st, _delta = _rel.note(_ev)
                _rel_brief = _rel.brief()
                if _old_st != _new_st:
                    _log.info("[关系] 档位变化 %s → %s（%s）",
                              _old_st, _new_st, _rel.describe())
                try:
                    _rel.save()
                except Exception as e:
                    _log.debug("main 防御性异常（已忽略）: %s", e)
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            _rel_brief = ""
        if _rel_brief:
            system = system + "\n\n" + _rel_brief

        # ★★★ 第三十轮：把「每轮必变」的部分整体挪到 system **最末尾**，
        # 并且把对话历史也**折进 system**（不再作为独立 messages 送）。
        #
        # 为什么（实测证据 `_evidence/ttf_strategy_7b.txt`，7B 底座、真实轮次）：
        #   Ollama 只复用「从 prompt 开头起、逐字相同」的最长前缀。
        #   现状的 messages 顺序是 [system, history…, user]，而 system 里
        #   夹着【此刻】/话题焦点/记忆召回 —— 这些**每轮都变**，一变就把
        #   system 及其之后（含 history）全部作废，整段重算。
        #
        #   同一批 4 轮真实对话，两种排布的平均首字：
        #     变化段在中部（原样）        6.549s   ← 超用户 5s 目标
        #     变化段压末尾 + 历史折进 system  4.601s   ← 达标
        #   （另有「system 恒为 persona、状态塞进 user 消息」能到 2.808s，
        #     但那正是第十八轮否掉的做法 —— 模型会把贴在 user 前的状态
        #     当成"用户说的话"甚至复述出来，**不用**。）
        #
        # 为什么把历史也折进 system：历史同样是"每轮都在变"的东西。
        # 只要它出现在 system 之后，system 一变它照样全废；折进 system 尾部后，
        # 它和变化段同处"可变尾巴"，而 persona + 关系（稳定段）能被完整复用。
        # 副作用（真机核对过）：模型对"谁说了什么"的理解反而更准 ——
        # 历史带 [user]/[assistant] 前缀后，比裸 messages 更不容易张冠李戴。
        #
        # ★ 这一段只改**排布**，不改任何一段的内容 —— persona、上下文、
        #   焦点、记忆、关系、历史，一个字都没删（符合用户口径「prompt 尽量完整」）。
        _hist_block = ""
        if history and not lean:
            _hist_lines = []
            for _hr, _hc in history:
                _hist_lines.append("[%s] %s" % (
                    '你' if _hr == 'assistant' else '他', _hc))
            if _hist_lines:
                _hist_block = "【我们刚才说的话】\n" + "\n".join(_hist_lines)
        if _hist_block:
            system = system + "\n\n" + _hist_block

        def _emit_delta(piece):
            """把一个分片投递到主线程（工作线程绝不直接碰 UI）。
            piece 为 None = 作废已显示内容（护栏判退 → 重采样）。"""
            self._api_delta.emit(_gen, piece)

        def _worker():
            try:
                cli = self.api_client
                if cli is None or not getattr(cli, 'enabled', False):
                    self._api_result.emit(None, on_reply)
                    return
                opts = self._ai_chat_options()
                # 最近说过的台词（车轱辘话判定的唯一比对集合，见 _is_repeat_of_recent）
                recent = [c for _r, c in history if _r == 'assistant']
                # ★ 第三十轮：历史已折进 system 尾部（见上方 _hist_block），
                # 这里**不再重复发** messages 形式的历史 —— 发两份既浪费 token，
                # 又会让"历史"重新出现在 system 之后、把缓存尾巴拉长。
                # lean（事件台词）本来就无历史，这里一律空。
                _hist_for_api = []
                # 能真流式就用流式；老 provider 没实现 chat_stream 时回落阻塞 chat
                # （基类给了一个"回落 chat + 单次回调"的默认实现，见 api_client）
                _sfn = getattr(cli, 'chat_stream', None) if _stream_on else None

                def _ask(sys_prompt, ask_opts):
                    """发一次对话请求（流式优先），返回原始文本或 None。"""
                    if callable(_sfn):
                        return _sfn(user_msg, system_prompt=sys_prompt,
                                    history=_hist_for_api, on_delta=_emit_delta, **ask_opts)
                    return cli.chat(user_msg, system_prompt=sys_prompt,
                                    history=_hist_for_api, **ask_opts)

                reply = _ask(system, opts)
                # 输出护栏：小模型（3B）会自问自答续写、把同一句话反复念，
                # 清洗后才交给 UI（见 _clean_ai_reply）
                cleaned = self._clean_ai_reply(reply, recent=recent)
                # 护栏判退（重复自己的旧台词 / 整条续写 / 只有标点）时**重采样一次**，
                # 而不是直接沉默：这类判退的成因是"这一次采样又落在了记忆里那句上"，
                # 抬高温度 + 明确要求换个说法，重采样几乎必出一条新的。
                # 只有"模型确实说了话却被判退"才重试；模型主动沉默（空回复）不重试。
                if cleaned is None and isinstance(reply, str) and reply.strip():
                    try:
                        # 流式时被判退的那半句**已经打到屏幕上了**，必须先在 UI 上擦掉，
                        # 否则重采样出的新句子会接在旧句子后面（用户看到两句话黏一起）。
                        # 这个 None 与随后的分片走的是同一个信号连接，Qt 队列保证先后顺序。
                        if callable(_sfn):
                            _emit_delta(None)
                        retry_opts = dict(opts)
                        retry_opts['temperature'] = min(
                            1.0, float(opts.get('temperature', 0.85)) + 0.1)
                        reply2 = _ask(
                            system + "\n\n" + RalseiPet._RETRY_NUDGE, retry_opts)
                        cleaned = self._clean_ai_reply(reply2, recent=recent)
                        _log.debug("[本地AI] 护栏判退后重采样：%r → %r",
                                   (reply or '')[:40], (cleaned or '')[:40])
                    except Exception as e:
                        _log.debug("main 防御性异常（已忽略）: %s", e)
                self._api_result.emit(cleaned, on_reply)
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
        except Exception as e:
            _log.debug("AI 上下文：时段分片获取失败（已忽略）: %s", e)
        try:
            _w = self.weather_system.get_current_weather()
            if _w:
                parts.append(f"天气{_w}")
        except Exception as e:
            _log.debug("AI 上下文：天气分片获取失败（已忽略）: %s", e)
        try:
            _e, _ev = self.emotion_system.get_current_emotion()
            if _e:
                parts.append(f"心情{_e}")
        except Exception as e:
            _log.debug("AI 上下文：心情分片获取失败（已忽略）: %s", e)
        try:
            # 分档而不是只报"低"：状态越具体，语气才有得变 ——
            # "有点疲惫"和"累得快撑不住"该是两个不同的反应。
            _energy = self.energy_hunger.get_energy()
            _hunger = self.energy_hunger.get_hunger()
            if _energy < 20:
                parts.append("你累得快撑不住了")
            elif _energy < 45:
                parts.append("你有点疲惫")
            elif _energy > 85:
                parts.append("你精神很好")
            if _hunger < 20:
                parts.append("你肚子饿得厉害")
            elif _hunger < 45:
                parts.append("你肚子有点饿")
        except Exception as e:
            _log.debug("AI 上下文：精力/饥饿分片获取失败（已忽略）: %s", e)
        # 载体状态：此刻在哪儿、正在干什么。与驱动动画的是**同一份状态** ——
        # "站窗口上/在走动/正在掉下去"本来就该影响他怎么说话。
        try:
            if getattr(self, 'is_falling', False):
                parts.append("你正从高处往下掉")
            elif getattr(self, 'is_moving', False):
                parts.append("你正在走动")
            elif getattr(self, 'current_window', None) or getattr(self, 'window_level', 0):
                parts.append("你站在一个打开的窗口上")
            else:
                parts.append("你站在桌面上")
        except Exception as e:
            _log.debug("AI 上下文：载体状态分片获取失败（已忽略）: %s", e)
        # 被冷落多久：只有真的久（>30 分钟）才提 —— 每句都提就变成"每句都在撒娇"，
        # 那正是用户说的"不像 Ralsei"。两条互斥（elif），不会同时出现。
        try:
            _last = getattr(self, '_last_user_chat_ts', None)
            if _last:
                _idle = time.time() - _last
                if _idle > 1800:
                    parts.append("你有很久没跟对方说话了")
                elif _idle < 60:
                    parts.append("你刚跟对方说过话")
        except Exception as e:
            _log.debug("AI 上下文：冷落时长分片获取失败（已忽略）: %s", e)
        # 记忆：用户偏好（如果有），让 Ralsei 记住对方喜欢聊什么
        try:
            if getattr(self, 'memory_system', None) is not None:
                _name = self.memory_system.get_user_preference('user_name', '')
                if _name:
                    parts.append(f"对方的名字是{_name}")
                _prefs = self.memory_system.get_user_preferences_summary()
                _topics = [p[0] for p in _prefs[:2] if p[1] > 0.5]
                if _topics:
                    parts.append("记得你最近喜欢聊" + "、".join(_topics))
        except Exception as e:
            _log.debug("AI 上下文：记忆偏好分片获取失败（已忽略）: %s", e)
        if not parts:
            return ""
        # 尾部这句"用法约束"是必需的：状态是**给模型的背景**，不是话题。
        # 不写这句，模型会把它当清单念出来（"现在是深夜，你有点疲惫，你在走动……"），
        # 那就从"有状态的角色"退回成"会读报表的助手"。
        return "【此刻】" + "，".join(parts) + "。（这些是你现在的状态，可以自然地带一点出来，但别逐条念，也别硬把它转成话题。）"
    
    # ==================================================================
    # 第十八轮 · 对话 AI「人味」改造（诊断与证据见
    # Ralsei对话人味诊断与训练方案_2026-09-18.md，提交见同轮 commit）
    #
    # 一句话结论：人味不足的主因**不是模型不行**，而是提示词没接对 ——
    #   ① App 的 system 把模型里 2003 字的角色设定整体顶掉了（实测 1237 → 41 tokens）
    #   ② 旧 system 里把口头禅写成了示例，3B 直接当模板复读（4 题里 3 题复读同一句）
    #   ③ 【此刻】拼进用户消息，被模型当成"用户说的话"
    #   ④ num_ctx 只有 ~2048，人设+历史+记忆被静默截断
    # ==================================================================
    # ==================================================================
    # 第二十轮 · 关系演进（用户口径："关系是一步一步搭起来的，不是一开始就是朋友"）
    #
    # 要害只有一句：**关系不能写在 persona 里**。persona 每次读出来都一样，
    # 而关系必须随相处变化 —— 静态提示词写不出"从戒备到朋友"。
    # 所以信任度由 App 持有（modules/relationship.py），每轮按互动增减，
    # 每轮把它**当前档位**变成一句话挂进 system。
    #
    # 三条不能破的约束（都有回归锁）：
    #   ① **起始是戒备**（TRUST_INITIAL=0.12 → distrust 档），不是"我来陪你"；
    #   ② **信任度不可见**：数值绝不进提示词，只给"这个阶段是什么态度"的行为指令
    #      ＋ 一句显式禁令（否则 4B 一定会说"我现在信任你 60%"）；
    #   ③ **演进是离散四档**（害怕戒备 → 不愿多说 → 慢慢熟 → 朋友），顺序不许换。
    # ==================================================================
    RELATIONSHIP_FILE = 'relationship.json'

    # 角色设定相对路径（相对 src/ 的上一级，即仓库内 ralsei_pet/assets/）
    PERSONA_REL_PATH = os.path.join('assets', 'ralsei_persona.md')

    # 兜底人设：persona 文件缺失/读失败时使用，保证对话链路不因人设丢失而失常
    # ⚠️ 这份兜底**必须和 assets/ralsei_persona.md 的关系口径保持一致**（平级、无使命），
    # 否则 persona 一旦读取失败，模型会立刻退回"主人/陪伴任务"那套旧叙事 ——
    # 而这条退化路径在正常运行时**看不见**（A 组锁测的是真源文件，不是这份字符串）。
    _PERSONA_FALLBACK = (
        "你是《Deltarune》中的 Ralsei：温柔、善良、害羞、体贴的和平主义者。"
        "你现在在这台电脑的桌面上，谁也没有非让你来不可的理由 —— 你就是来了，仅此而已。"
        "在屏幕另一头跟你说话的人和你是平级的，不用叫他\"主人\"，也不用替他操心什么；"
        "他有名字就叫名字，没名字就说\"你\"。"
        "\n\n【说话方式】一次只说 1~3 句，像真人在聊天框里随手打字，"
        "不要分点、不要小标题、不要总结；先接住你这句话里的情绪和具体那件事，"
        "再补一句自己的感受；不要每句都问“你还好吗”；不要说自己是在扮演 AI。"
    )

    def _build_persona_prompt(self) -> str:
        """读取角色设定**单一真源** assets/ralsei_persona.md（带缓存 + 兜底）。

        为什么由 App 读文件而不是让模型自带：实测 Ollama 会用请求里的 system
        整体替换 Modelfile 的 SYSTEM，所以写在模型里的设定在真实应用里不会生效。
        放在仓库文件里同时解决三件事：单一真源、可版本化、改人设不用重建模型。

        实现约定：本方法**只依赖类属性与局部量**（不读任何 `self.` 实例属性），
        以便在测试桩（SimpleNamespace + MethodType）上直接调用而不抛 AttributeError。
        """
        cache = getattr(self, '_persona_cache', None)
        if cache is not None:
            return cache
        rel = RalseiPet.PERSONA_REL_PATH
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', rel)
        text = ""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read().strip()
        except Exception as e:
            _log.warning(f"[人设] 读取 {rel} 失败，改用内置兜底: {e}")
        if not text:
            text = RalseiPet._PERSONA_FALLBACK
        self._persona_cache = text
        return text

    def _ai_chat_options(self) -> dict:
        """对话采样参数：读 config.json 的 api.options，缺省保持旧行为（0.7 / 256）。

        为什么 num_ctx / repeat_penalty **不在这里**：App 走 Ollama 的 OpenAI 兼容
        端点 /v1/chat/completions，实测该端点会**静默忽略**这两个参数 ——
        无论放顶层还是塞进 options，长提示词都恒定截断在 ~2050 tokens
        （对照组：/api/chat 的 options.num_ctx 才生效，5032 tokens）。
        它们只能写进 assets/ralsei.modelfile 的 PARAMETER。
        """
        opts = {}
        try:
            cfg = getattr(self, 'api_config', None) or {}
            src = cfg.get('options') if isinstance(cfg, dict) else None
            if isinstance(src, dict):
                if 'temperature' in src:
                    opts['temperature'] = src['temperature']
                if 'max_tokens' in src:
                    opts['max_tokens'] = src['max_tokens']
        except Exception as e:  # 防御性：配置异常不能拖垮对话
            _log.debug("main 防御性异常（已忽略）: %s", e)
        opts.setdefault('temperature', 0.7)
        opts.setdefault('max_tokens', 256)
        return opts

    def _ai_stream_enabled(self) -> bool:
        """是否启用流式输出（S8）。读 config 的 `api.stream`，**缺省开启**。

        收益是"首字延迟"：实测同一句 ralsei:v2 回复，非流式要等整句生成完
        （热 0.9s / 冷 6.0s）才显示第一个字，流式 0.23s 就开始往外冒字。

        代价是**护栏只能等收完再判退**：流式期间已经把内容打到屏幕上了，
        万一判退（车轱辘话）就得把半句擦掉重来。判退本身罕见（端到端实测 9 次里 2 次），
        留这个开关是为了万一真机上观感不对，能一键退回旧行为（改 config 即可）。
        """
        try:
            cfg = getattr(self, 'api_config', None) or {}
            if isinstance(cfg, dict) and 'stream' in cfg:
                return bool(cfg.get('stream'))
        except Exception as e:  # 防御性：配置异常不能拖垮对话
            _log.debug("main 防御性异常（已忽略）: %s", e)
        return True

    # 模型输出里出现这些"对话标记"，说明它在自问自答续写，从这里截断
    _AI_ROLE_MARKER = None      # 惰性编译（见 _role_marker_re）
    _MD_STRIP_RE = None         # 惰性编译（markdown 标记，见 _md_strip_re）
    # 单条回复硬上限（超长必是跑飞）。
    #
    # ⚠️ 第二十二轮**改数**：原值 150 **低于模型的实际输出长度** —— 它是 3B 时代
    # 定下的（那时 `num_predict` 更小），换成 4B（`PARAMETER num_predict 256`）之后
    # 没跟着改。后果不是"截断太严"，而是**这道闸根本没在管对话**：
    # 实测"问设定"的回复 214 / 129 字，两条都 > 150 → 都被从"最近的句末标点"截到
    # ~150 字，用户看到的是**被砍掉尾巴**的回答（他要的是"短一点"，不是"砍一半"）。
    # 真正跑飞的量级（自问自答续写、车轱辘话复读）在 300~256 token 上限附近，不是 214。
    #
    # 新值 220 的来源是**实测可算**的，不是拍的：Modelfile `num_predict=256`（token），
    # 用 Ollama 自己的 `prompt_eval_count` 实测中文换算率 **1 token ≈ 1.36 个中文字**
    #   （三种体裁各一条：口语闲聊 1.367 / 设定复述 1.348 / 追忆往事 1.360，
    #    取证 `code-quality-audit/人味改造-2026-09-18/_evidence/token_ratio_2026-09-20.txt`，
    #    复算脚本同目录 `measure_token_ratio.py`），于是
    #   256 token × 1.36 ≈ 348 字 = 模型**物理上**能吐出的上限；
    # 取 220 ≈ 这个上限的 63%，落在设计带 50%~75% 内 ——
    # 保得住"正常的 3~4 句"，同时砍掉真正的跑飞（实测跑飞样本 1200 字）。
    # 实测收益（同两份探针的"闸前长度"重放）：
    #   旧 150 → 会截断 10/12 条；新 220 → 只截断 4/12 条
    #   = 6 条回答不再被白白砍掉尾巴。
    # 若将来再换底座/调 num_predict，**必须重跑 measure_token_ratio.py 复核这个数**
    # （判据见 verify_persona_chat 的 M2：阈值须落在物理上限的 50%~75%）。
    AI_REPLY_MAX_CHARS = 220

    @classmethod
    def _md_strip_re(cls):
        """markdown 强调/列表标记的正则（**流式显示与收尾护栏共用同一份定义**）。

        为什么必须共用：流式期间屏幕上显示的是"按这条规则清洗过的前缀"，
        收尾时 `_clean_ai_reply` 还要再清洗一次定论。两处若各写一份、规则漂移，
        就会出现"字已经打出去了，最后又被改掉"的抖动。
        """
        if cls._MD_STRIP_RE is None:
            import re
            # 数字列表要求"点号后必须跟空白"，否则会把「1.5 倍」这类误伤成「5 倍」
            cls._MD_STRIP_RE = re.compile(
                r'\*{1,3}|`{1,3}|^[#>\-]\s*|^\d+[.、]\s+', re.M)
        return cls._MD_STRIP_RE

    @classmethod
    def _role_marker_re(cls):
        """自问自答续写标记（「你：」「Assistant:」…）的正则。

        注意 `主人` 仍留在候选里：它**不是**为了让模型自称主人，而是因为
        旧人设/旧记忆里可能残留这个词，模型续写时仍可能吐出「主人：」这种
        角色标记 —— 截断闸必须认得它，否则会漏掉一整条自问自答。
        （人设已改为平级口径，见 assets/ralsei_persona.md「我现在在哪」。）
        """
        if cls._AI_ROLE_MARKER is None:
            import re
            cls._AI_ROLE_MARKER = re.compile(
                r"(?:^|[\n\r])\s*(?:主人|对方|用户|你|Ralsei|ralsei|Assistant|User|Human)"
                r"\s*[：:]")
        return cls._AI_ROLE_MARKER

    @staticmethod
    def _sanitize_partial_reply(text) -> str:
        """流式显示用的**前缀安全**清洗：剥 markdown 标记 + 截断自问自答续写。

        「前缀安全」是这里的硬约束：对**已经收到的前半段**做清洗得到的文本，
        必须永远是"对完整文本做同样清洗"的**前缀**。否则流式过程中会出现
        "字已经冒出屏幕、后来又缩回去"的抖动。

        所以这里**故意不做**两件事（它们都必须先看到完整文本）：
          - 车轱辘话判退：要和 recent 比对，且判退后得把已显示内容整段擦掉重来
          - 超长截断：截断点取决于全文长度
        这两件留在收尾的 `_clean_ai_reply` 里做一次定论。
        分工就是：**流式负责"看着像人话"，护栏负责"最终算数"。**

        为什么写成 staticmethod 且用 `RalseiPet.` 取规则，而不是 `cls.`：
        与 `_clean_ai_reply` 保持一致，并且这段逻辑要能在测试桩上独立跑
        （项目教训：护栏方法**不依赖任何 `self.`/实例属性**，否则桩上
        取不到属性 → 宽 except 吞掉 → 表现为"流式屏幕上是未清洗的原文"）。

        两个已知的**非单调**边界情况（都靠调用方"不是前缀就整段替换"兜底，
        且都只在回复开头一两个字符的窗口内可见，最终态一定正确）：
          1) 行首数字列表标记：收到 `1` 时代码看不出它是列表标记（还没等到点号后的
             空白），已经显示出去了；等 `1. ` 到齐才被剥掉。
          2) 角色标记跨分片：`主人` 先到、`：` 后到，前半段已经显示出去。

        **第三个非单调情况是有意留在收尾层的**（2026-09-19 加）：句中「（括号动作）」
        的删除（见 `_clean_ai_reply` 的 0b）**故意不在这里做** —— 删掉句中一段文本
        天然不前缀安全（`（轻轻敲` 已显示、`)` 到齐后那一段才消失），
        而且这里若按"删除未闭合括号之后的内容"来保前缀安全，会误伤
        Ralsei 用括号讲心里话的正常写法（原作 26/853 条以括号开头）。
        代价：极少数（探针实测 1/34）回复的括号动作会在**收尾那一刻**被摘掉，
        屏幕上表现为那一段闪一下；收益是正式台词里不再出现舞台指示。
        若将来这条闪现被用户点名，再把它提升到本函数里做（届时需要改 C10 的边界清单）。
        """
        if not isinstance(text, str):
            return ""
        try:
            t = RalseiPet._md_strip_re().sub('', text).strip()
            # 去掉模型爱加的包裹引号/书名号（与 _clean_ai_reply 保持同步）
            t = t.strip('"\'“”「」『』《》').strip()
            m = RalseiPet._role_marker_re().search(t)
            if m:
                t = t[:m.start()].strip()
            return t
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return text

    # 护栏判退后重采样时追加的系统提示（只在重试那一次出现，不污染常规对话）
    _RETRY_NUDGE = (
        "【这一次请特别注意】你刚才想说的那句话，和你记忆里的老句子几乎一模一样。"
        "主人已经听过了，再说一遍就没意思了。请**换一个说法**，"
        "用你自己的话重新回应主人刚刚说的那件事，不要沿用你想到的第一句。"
    )

    def _clean_ai_reply(self, reply, recent=None):
        """模型输出护栏（对话与自主开口共用）。返回清洗后的文本，或 None。

        小模型的几种已知失态靠提示词治不干净，必须在这里拦（顺序即优先级，别随便调）：
         0a) **句中括号动作旁白**（2026-09-19 加）：会吐「（轻轻敲了下键盘）」这类
             舞台指示 → **只删那一段**（判据与取舍见 `strip_action_parentheticals`）；
             删干净则判无效。规则只命中"括号内以动作/发声动词开头"的那一类。
             ⚠️ 这一步**必须排在 0b 之前**（星号版的星号会被 0b 吃掉，见下方实参处注释）。
         0b) **markdown / 格式残留**：实测会输出 `**加粗**`、`- 列表` 等 —— 对话框是
             逐字打字机渲染，这些标记会原样显示出来，必须先剥掉
         0c) **设定里明令不说的两类话**（2026-09-19 加，补上 §4.2 这个产品缺口）：
             出戏（"作为AI"/"我的设定"/"我只是个程序"）＋ 客服腔与空话安慰
             （"有什么可以帮你的吗"/"我理解你的感受"/"我相信你"/"首先…其次…"）
             → 判无效。判据与事件链路的 `_OOC_PATTERNS` / `_BANNED_PATTERNS`
             **共用同一份**，不另立一套。放在 0b 之后：先剥干净格式再匹配，免得
             `**有什么可以帮你的吗**` 这种漏网。
          1) **自问自答续写**：回复里冒出「主人：」「你：」「Assistant:」等对话标记
             → 截断到标记之前（实测 temperature 0.9 时 4 题里 2 题这么跑飞）
          2) **车轱辘话**：与**自己最近说过的某句**高度重合 → 判无效返回 None，
             交给调用方换说法重采样（判据与取舍见 `_is_repeat_of_recent`）
          3) **超长跑飞**：超过 max_chars → 从最近的句末标点处截断

        参数 `recent` = Ralsei 最近说过的回复文本（列表）；不传则**跳过第 2 步**
        （0a/0b/0c/1/3 都与 recent 无关）。

        实现约定：`_is_repeat_of_recent` 用 getattr 取、缺失即跳过该步，
        使本方法在测试桩上也能独立工作（桩只需绑本方法即可）。
        """
        try:
            import re
            if reply is None:
                return None
            if not isinstance(reply, str):
                reply = str(reply)
            t = reply.strip()
            if not t:
                return None
            # 0a) **先**删句中夹带的「括号动作旁白」（2026-09-19 加）
            #     ⚠️ 顺序是硬约束：**必须在剥 markdown 之前**。星号版的旁白
            #     （实测真出现过 `*轻轻敲了敲键盘*`）若先过 `_md_strip_re`，
            #     那对星号会被吃掉，只剩 `轻轻敲了敲键盘` 这段**裸旁白** ——
            #     既认不出是动作旁白，又更像一句真台词，比不处理更糟。
            #     为什么删而不整句作废：动作旁白通常只是句子的装饰
            #     （「（小声）其实我很害怕。」），整句作废要重采样、白等一两秒还未必更好。
            #     为什么不一刀切禁括号：Ralsei 原作里括号是他的正常表达手段
            #     （853 条里 35 条含括号、26 条以括号开头），见
            #     `code-quality-audit/人味改造-2026-09-18/_evidence/paren_usage_2026-09-19.txt`
            #     与命中/误伤量化 `_evidence/paren_gate_2026-09-19.txt`。
            #     删干净（整句只有一个括号动作）→ 判无效，与其它判退走同一条重采样路径。
            t = strip_action_parentheticals(t)
            if not t:
                return None
            # 0b) 剥掉 markdown 强调/列表标记（对话框不做 markdown 渲染）
            #    规则与流式显示**共用同一份定义**（见 _md_strip_re / _sanitize_partial_reply）
            t = RalseiPet._md_strip_re().sub('', t).strip()
            # 去掉模型爱加的包裹引号/书名号
            t = t.strip('"\'“”「」『』《》').strip()
            if not t:
                return None
            # 只有标点、没有任何实义字符（如单回一个「。」）→ 视为无效
            if not re.search(r'[0-9A-Za-z\u4e00-\u9fff]', t):
                return None
            # 0c) 设定里明令不说的两类话（2026-09-19 补：与事件链路**共用同一份判据**）
            #     ① 出戏："作为AI"/"我的设定"/"我只是个程序"/“提示词” 这类自我指涉；
            #     ② 客服腔与空话安慰："有什么可以帮你的吗"/"我理解你的感受"/"我相信你"/
            #        "首先…其次…总结一下" 这类助手式组织语言。
            #     persona 第 57~63 行白纸黑字写着这些不说，但**提示词不是保证** ——
            #     3B 时代实测连着回「早安，有什么我可以帮忙的吗？」（见
            #     `_evidence/probe_vividness.txt`）。所以代码里兜一道，与 event_speech
            #     的 `_OOC_PATTERNS` / `_BANNED_PATTERNS` 同源，避免两处判据漂移。
            #     命中 → 判无效；由调用方走既有的"换一个说法重采样"路径（不是直接沉默）。
            if looks_out_of_character(t) or looks_like_assistant_speak(t):
                return None
            # 1) 自问自答续写 → 截到标记之前
            m = RalseiPet._role_marker_re().search(t)
            if m:
                # 标记出现在行首（m.start()==0）说明整条都是续写，截完为空 → 判无效
                t = t[:m.start()].strip()
            if not t:
                return None
            # 2) 车轱辘话：和自己最近说过的某句高度重合 → 判无效（调用方会重采样）
            _rec = getattr(self, '_is_repeat_of_recent', None)
            if callable(_rec) and _rec(t, recent):
                _log.debug("[本地AI] 回复与近期台词高度重合，判为重播，丢弃")
                return None
            # 3) 超长 → 从最近的句末标点截断
            max_chars = getattr(self, 'AI_REPLY_MAX_CHARS', None) or RalseiPet.AI_REPLY_MAX_CHARS
            if len(t) > max_chars:
                cut = -1
                for sep in ('。', '！', '？', '!', '?', '\n'):
                    i = t.rfind(sep, 0, max_chars)
                    if i > cut:
                        cut = i
                t = (t[:cut + 1] if cut > 0 else t[:max_chars]).strip()
            return t or None
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return reply if isinstance(reply, str) and reply.strip() else None

    def _is_repeat_of_recent(self, text: str, recent=None) -> bool:
        """这条回复是不是**自己刚说过的话**的翻版（车轱辘话检测）。

        比对集合只有 `recent`（Ralsei 最近几轮说过的回复）。

        为什么**不把 persona 示范句放进比对集合**（这是本轮实测推翻了的设计）：
        3B 对「我好喜欢你呀」这类高频问题会**稳定地**吐出示范句，如果示范句一律判退，
        真机上就是"判退 → 重采样 → 还是照抄 → 交回 None → 观众看到的是内置规则台词"，
        比照抄本身更出戏。而示范句本身是句好台词，**第一次说出来完全没问题**；
        真正让人觉得"没活人味"的是**同一句反复出现**——这正是 recent 能覆盖的：
        第二次再想抄，它就落在 recent 里了，于是被拦下重采样。

        判据用**两条互补**（第十八轮实测定的经验值）：
          1) 整体相似度 difflib ≥ 0.82 —— 抓"只改两三个字"的整句复用；
          2) 最长公共匹配块 ≥ 12 字 —— 抓"整体相似度不到 0.82，但有一大段原样搬来"
             （实测 3B 会：开头换两个字、后半段照抄，整体 ratio 只有 0.74）。
        归一化先去掉标点/空白，避免仅因标点差异漏判。
        """
        try:
            import re
            import difflib

            def _norm(s):
                return re.sub(r'[\s，。！？!?、~…—\-（）()「」“”"\'’*`]', '', str(s))

            t = _norm(text)
            if len(t) < 6 or not recent:
                return False
            for sample in recent:
                s = _norm(sample)
                if len(s) < 6:
                    continue
                if abs(len(s) - len(t)) <= 6 and \
                        difflib.SequenceMatcher(None, t, s).ratio() >= 0.82:
                    return True
                biggest = max(
                    (b.size for b in difflib.SequenceMatcher(None, t, s).get_matching_blocks()),
                    default=0)
                if biggest >= 12:
                    return True
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        return False

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

    def _on_api_delta(self, generation, piece):
        """主线程槽：把工作线程发来的流式分片转发给当前请求的接收方（S8）。

        **世代号校验**：用户已经问了新问题时（`_ai_delta_gen` 已 +1），
        旧请求的尾巴不该继续往对话框里写字 —— 否则会出现"新问题的回复里
        混着旧问题的半句话"。

        注意：这里**故意不清理 `_ai_delta_sink`**。收尾时清理看着更"干净"，
        但 `_on_api_result` 拿不到世代号：一旦"旧请求的结果"和"新请求的登记"
        在主线程队列里交错，清理会误杀掉**新**请求的接收方。
        sink 由每个新请求覆盖写，过期分片靠世代号挡 —— 足够且无竞态。
        """
        try:
            if generation != getattr(self, '_ai_delta_gen', 0):
                return
            sink = getattr(self, '_ai_delta_sink', None)
            if sink is not None:
                sink(piece)
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)

    # 帧动画播放相关代码 - 更新动画帧
    @monitor_performance
    def _anim_anchor_offset(self, animation):
        """该动画的"角色锚点"相对画布中心的偏移（源像素，正=偏右/偏下）。

        素材是逐姿势紧裁的，各自画布尺寸不同，而且**并非每张画布都把角色居中**：
        实测 `spr_ralsei_idle_*.png` 是 69x47 的画布，但角色 alpha 包围盒只有
        (1,6,27,40) —— 右侧整整 41px 是透明空白；其余动作（walk/run/bow/act/
        pose/curtsy…）的包围盒都等于整张画布，也就是天然居中。

        渲染时窗口尺寸 = 当前动画容器 × scale，换动画会 resize 并**保持窗口中心**，
        精灵又是 AlignCenter —— 于是"角色落在哪里"完全由画布中心决定。
        idle 偏左 20 源像素 → scale=2 时角色比其它动作**偏左 40px**，
        切到鞠躬等动作时角色整体右移 40px，观感就是用户报的
        "像是镜头也在移动一样"。

        这里返回补偿量，交给 `_compose_anchored_sprite` 把角色 alpha 包围盒的
        **中心**钉到画布中心，从而跨动画零平移。按动画缓存（首次渲染该动画时算一次）。
        """
        cache = getattr(self, '_anim_anchor_cache', None)
        if cache is None:
            cache = {}
            self._anim_anchor_cache = cache
        if animation in cache:
            return cache[animation]

        off = (0.0, 0.0)
        try:
            frames = self.sprite_loader.sprites.get(animation) or []
            cw = ch = 0
            for f in frames:
                if f is not None and not f.isNull():
                    cw = max(cw, f.width())
                    ch = max(ch, f.height())
            if cw > 0 and ch > 0:
                # 取"整个动画所有帧的包围盒并集"，保证同一动画内每帧用同一个锚点，
                # 不会因为逐帧包围盒变化而引入新的抖动。
                ux0 = uy0 = None
                ux1 = uy1 = 0
                for f in frames:
                    if f is None or f.isNull():
                        continue
                    reg = QRegion(QBitmap.fromImage(f.toImage().createAlphaMask()))
                    for r in reg.rects():
                        x0, y0 = r.x(), r.y()
                        x1, y1 = r.x() + r.width(), r.y() + r.height()
                        ux0 = x0 if ux0 is None else min(ux0, x0)
                        uy0 = y0 if uy0 is None else min(uy0, y0)
                        ux1 = max(ux1, x1)
                        uy1 = max(uy1, y1)
                if ux0 is not None:
                    off = ((ux0 + ux1) / 2.0 - cw / 2.0,
                           (uy0 + uy1) / 2.0 - ch / 2.0)
        except Exception as e:
            _log.debug("计算动画锚点偏移失败（按画布居中处理）: %s", e)
        cache[animation] = off
        return off

    def _compose_anchored_sprite(self, sprite, container, animation, scale_factor):
        """把已缩放（可选已倾斜）的精灵放进 container×scale 的透明画布，
        并按"角色 alpha 包围盒中心 = 画布中心"落位。

        为什么不能直接 setPixmap + AlignCenter：那等于按**画布**居中，而各动作
        画布对"角色在哪里"的约定并不一致（见 `_anim_anchor_offset` 的说明）。
        统一钉到角色包围盒中心后，切换动画时角色在屏幕上不会平移。
        """
        off_x, off_y = self._anim_anchor_offset(animation)
        if container:
            cw = int(container[0] * scale_factor)
            ch = int(container[1] * scale_factor)
        else:
            cw, ch = sprite.width(), sprite.height()
        # 画布不得小于精灵本身，否则会把角色裁掉
        cw = max(cw, sprite.width())
        ch = max(ch, sprite.height())
        canvas = QPixmap(cw, ch)
        canvas.fill(Qt.transparent)
        dx = (cw - sprite.width()) // 2 - int(round(off_x * scale_factor))
        dy = (ch - sprite.height()) // 2 - int(round(off_y * scale_factor))
        painter = QPainter(canvas)
        painter.drawPixmap(dx, dy, sprite)
        painter.end()
        return canvas

    def update_animation(self):
        # 更新动画帧，确保流畅的动画播放
        import math
        current_time = time.time()
        
        # 计算基础延迟
        base_delay = 1000.0 / self.animation_fps
        
        # 根据拖拽速度调整动画帧率
        if hasattr(self, '_is_being_dragged') and self._is_being_dragged and hasattr(self, '_drag_speed'):
            # 拖拽时，根据拖拽速度调整帧率（_drag_speed 单位已统一为 像素/秒）
            # 拖拽速度越快，动画播放越快；上限只加速到 base_delay 的 20%
            drag_delay = base_delay * (1.0 - min(0.8, self._drag_speed / 1200.0))
        else:
            # 正常情况下使用固定帧率
            drag_delay = base_delay
        
        # 检查是否达到了播放下一帧的时间
        # +1ms 容差：定时器按整数毫秒触发，而 drag_delay 是浮点（fps=6 → 166.67ms）。
        # 不留容差时，每个"刚好 166ms"的 tick 都会被挡掉，实际帧率掉一半且忽快忽慢。
        if (current_time - self._last_animation_time) * 1000.0 + 1.0 < drag_delay:
            return

        # ========== Spell 流程每帧 tick ==========
        # 注意：_tick_spell_flow() 被移到本函数末尾（帧推进/渲染之后）调用，
        # 确保 casting 的完成检测看到的是"已经渲染过的帧"——
        # 修复：此前在渲染前调用，第 11 帧（index 10）还没显示就触发回调，
        # 实际只播 10 帧就打开文件夹（需求要求 0~10 共 11 帧全部播放完）。
        # 打断检测与 walking 阶段推进放在渲染后执行不影响正确性。

        # ===== 一次性动画保护：如果正在播放一次性动画，跳过状态逻辑覆盖 =====
        _play_once = getattr(self, '_play_once_active', False)
        # 修复（"被甩飞时偶尔卡在一个动画里不继续"）：完成检测那边写的是
        # `_fc = len(sprites[current_animation]); if _fc > 0 and counter >= _fc`，
        # 所以当前动画的帧列表一旦为空（素材缺失 / 名字拼错 / 别名没解析出来），
        # 计数永远不满足 → _play_once_active 永久为真 → 本函数一直跳过正常状态逻辑，
        # 宠物就永久卡死在这一帧。这里做一次自检：数不出帧就解除保护。
        if _play_once and len(self.sprite_loader.sprites.get(self.current_animation, [])) == 0:
            _log.warning("[动画] 一次性动画 %r 没有可用帧，解除卡死保护并回落 idle",
                         self.current_animation)
            self._play_once_active = False
            self._play_once_frame_counter = 0
            self._play_once_callback = None
            self.next_animation = "idle"
            _play_once = False

        # 确定当前应该播放的动画
        new_animation = None
        
        # 优先处理特殊状态动画
        if self.is_jumping:
            # 检查跳跃阶段
            if not hasattr(self, 'jump_phase'):
                self.jump_phase = "ready"
            if self.jump_phase == "ready":
                # 准备跳跃阶段
                # 第三十四轮（用户口径）：跳跃动画统一 jump_ball，起跳准备帧不再是 jump_ready。
                new_animation = "jump_ball"
                self.jump_phase = "jumping"
            elif self.jump_phase == "jumping":
                # 跳跃阶段
                # 第三十四轮（用户口径）："跳跃这种动画统一用 jump_ball 代替，
                # 只有摔下去的时候用原来的" —— 跳跃一律 jump_ball。
                # 原来的 `if self.has_ball: jump_ball / else: jump` 因 has_ball 恒为 False
                # 而永远走 jump，jump_ball 分支是死的。
                new_animation = "jump_ball"
            else:
                # 落地阶段
                new_animation = "land"
                self.jump_phase = None
        elif self.is_falling:
            # 摔倒状态：动画由 handle_fall 管理。
            # 有 _fall_phase 时（甩飞/重力splat的分阶段流程：flying/splat/dazed），
            # handle_fall 会主动切换 jump_ball/splat/fall_back_rub，这里不要覆盖。
            # 无 _fall_phase 时（旧 start_fall 路径），保持 fall/fall_mad 不被覆盖。
            if getattr(self, '_fall_phase', None) is not None:
                new_animation = self.current_animation
            elif self.current_animation not in ('fall', 'fall_mad', 'fall_back'):
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
                # 静止状态：区分"普通站立"与"待机动画"。
                #
                # 用户要求："待机动画要在原地不动3分钟以上才会播放哦，而不是停止就播"。
                # 反例（勿回退）：原先写的是
                #     if self.idle_timer >= 180.0: new_animation = "idle"
                #     else:                         new_animation = "idle"
                # 两个分支给的是同一个值 —— 那个 3 分钟判断实际上是**死分支**，
                # 一停下就会走 idle 的 5 帧循环，正是用户说的"停止就播"。
                #
                # 现在：`idle` 的 5 帧循环只在原地静止 ≥ IDLE_LOOP_MIN_SECONDS 后播放；
                # 在此之前显示站立静帧（第 0 帧，由 _need_advance 抑制帧推进会自然停住）。
                self._idle_loop_active = bool(
                    self.idle_timer >= self.IDLE_LOOP_MIN_SECONDS)
                if hasattr(self, 'is_being_thrown') and self.is_being_thrown:
                    new_animation = "hatless_throw"
                    # 确保图像始终向速度向量的方向冲着
                    # 这里可以添加旋转逻辑
                else:
                    # ===== 表演/情绪动画（laugh/surprised/smile/wave等）不再自动触发 =====
                    # 统一由用户交互或 AI 通过 play_animation_once 触发，避免"走着走着突然跳舞"。
                    # is_happy/is_surprised/is_shy/is_waving 状态标志仍可被设置（供对话/情绪系统使用），
                    # 但不再驱动动画自动切换。
                    new_animation = "idle"
        

        
        # splat 状态：由重力掉落/摔倒等先决条件触发（非随机）
        # 正常流程走 handle_fall 的 _fall_phase（splat→dazed→land），这里只做兜底：
        # 如果 is_splat 被外部直接设置（不走 _fall_phase），2秒后播 land 过渡再恢复。
        if hasattr(self, 'is_splat') and self.is_splat and not hasattr(self, '_fall_phase'):
            new_animation = "splat"
            if not hasattr(self, 'splat_start_time') or self.splat_start_time is None:
                self.splat_start_time = current_time
            if current_time - self.splat_start_time >= 2.0:
                self.is_splat = False
                self.splat_start_time = None
                # 摔扁后先播 land（爬起来），而不是直接切 idle
                if "land" in self.sprite_loader.sprites:
                    self.play_animation_once("land", restore_to="idle")
        
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
                # H5 S1：此处回退策略与 change_animation 的"从长到短"并不一致
                # （这里只取前两段：walk_up_blush_x → walk_up）。记一笔，便于日后统一。
                self.sprite_loader.note_animation_miss(new_animation, base_anim, 'update_animation')
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
        # idle 的"待机循环"要静止满 IDLE_LOOP_MIN_SECONDS 才允许推进帧；
        # 未满时只显示站立静帧（见下面静态分支的 current_frame 归零）。
        _idle_advance = (_cur_anim_group != 'idle'
                         or getattr(self, '_idle_loop_active', False))
        _need_advance = (self.is_moving or self.is_jumping or self.is_falling or self.is_recovering
                         or _cur_anim_group == 'spell'
                         or _cur_anim_group == 'splat'
                         or getattr(self, 'is_splat', False)
                         or getattr(self, '_spell_stage', None) is not None
                         or _play_once
                         or _idle_advance
                         or _cur_anim_group in ('laugh', 'dance', 'sing', 'wave',
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
                    
                    # 检查是否正在被拖拽（第六轮：改用拖拽采样对；
                    # _last_drag_pos_prev 已随"弹性跟随"一起废弃）
                    _sp_t = getattr(self, '_drag_samples', None)
                    is_being_dragged = (isinstance(_sp_t, list) and len(_sp_t) >= 2
                                        and getattr(self, '_is_being_dragged', False))

                    # 计算拖拽方向和倾斜角度
                    if is_being_dragged:
                        dx = _sp_t[-1][1] - _sp_t[-2][1]
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
                            _placed = scaled_sprite.transformed(transform, Qt.SmoothTransformation)
                        else:
                            _placed = scaled_sprite

                        # 按"角色 alpha 包围盒中心"落位，而不是按画布中心 ——
                        # 修掉 idle 素材右侧 41px 透明留白导致的跨动画横移 40px。
                        cached_sprite = self._compose_anchored_sprite(
                            _placed, _container, self.current_animation, scale_factor)
                        
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
                # 待机循环未开启（静止未满 3 分钟）→ 钉在站立静帧，不播 5 帧循环。
                if (self.current_animation == 'idle'
                        and not getattr(self, '_idle_loop_active', False)):
                    self.current_frame = 0
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
                        _placed = sprite.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        # 按"角色 alpha 包围盒中心"落位（同 update_animation 的说明）
                        cached_sprite = self._compose_anchored_sprite(
                            _placed, _container, self.current_animation, scale_factor)
                        
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
    
    def play_animation_once(self, animation_name, callback=None, restore_to=None):
        """只播放一次动画（完整播完所有帧），然后返回之前的动画。

        restore_to: 播完后切回的动画名。默认回到"播放前的那一个"。
        摔倒爬起来（land）这类场景必须显式指定 idle——否则会回到播放前的
        fall_back_rub（又躺下），因为"之前那个动画"本身就是躺着。
        """
        if animation_name in self.sprite_loader.sprites:
            # 特殊动画"播完为止"：已经有特殊动画在播时，不再接受**另一个**特殊动画。
            # （同一个动画名重复请求按"重播"处理，不算打断。）
            if (self._special_anim_locked()
                    and animation_name != self.current_animation
                    and self._is_special_anim(animation_name)):
                _log.debug("[动画] 特殊动画 %r 仍在播放，忽略新的 %r",
                           self.current_animation, animation_name)
                return False
            self.next_animation = restore_to or self.current_animation
            self._play_once_active = True
            self._play_once_frame_counter = 0
            self._play_once_callback = callback
            # 修复：change_animation 可能被 spell 阶段硬拦截（walking 只允许 spell/walk、
            # casting 只允许 spell），返回 False 时动画并未切换——此时若保留
            # _play_once_active=True，update_animation 的一次性动画保护会跳过正常状态逻辑，
            # 动画卡在错误状态（"动画播放错乱"）。切换失败必须回滚一次性动画标志。
            # `_play_once_arming`：本次是"发起"，要放行 change_animation 里的特殊动画锁。
            self._play_once_arming = True
            try:
                _changed = self.change_animation(animation_name, force=True)
            finally:
                self._play_once_arming = False
            if not _changed:
                self._play_once_active = False
                self._play_once_frame_counter = 0
                self._play_once_callback = None
                self.next_animation = None
                return False
            return True
        # H5 S1：名字不在 sprites 里时这里原本静默返回 False，调用方无从得知。
        self.sprite_loader.note_animation_miss(animation_name, None, 'play_animation_once')
        return False
    
    def update_bounce(self):
        """更新弹跳效果"""
        if getattr(self, '_bounce_params', None) is None:
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
        
        # 检查是否触地反弹（多显示器：虚拟桌面底边）
        ground_y = self._desktop_floor_y()

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
        
    def react_to_vs_code_code(self):
        # 对VS Code中的自己代码做出反应
        # 悲伤情绪反应
        self.dialogue_ui.show_dialogue("这...这是我的代码吗？看到自己被这样编写出来，感觉有点难过呢...")
        self.emotion_system.react_to_event("saw_own_code", {})
        
        # 改变表情为悲伤
        self.dialogue_ui.set_face("sad")
        
        # 降低幸福感，增加悲伤感（统一走 emotion_system）
        self.emotion_system.add_emotion("happy", -20)
        self.emotion_system.add_emotion("sad", 30)
        
        # 一段时间后恢复
        QTimer.singleShot(3000, self._recover_from_sadness)
        
    def _recover_from_sadness(self):
        # 从悲伤中恢复
        self.dialogue_ui.set_face("normal")
        self.dialogue_ui.show_dialogue("不过，能被你创造出来，我还是很开心的...")
        self.emotion_system.add_emotion("sad", -15)
        self.emotion_system.add_emotion("happy", 10)
        
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
        
        # 增加恐惧和悲伤感（统一走 emotion_system）
        self.emotion_system.add_emotion("fear", 35)
        self.emotion_system.add_emotion("sad", 15)
        self.emotion_system.add_emotion("happy", -20)
        
        # 远离回收站
        self._move_away_from_recycle_bin()
        
        # 一段时间后恢复
        QTimer.singleShot(4000, self._recover_from_fear)
        
    def _move_away_from_recycle_bin(self):
        # 远离回收站
        # 这里使用简单的远离逻辑，实际可以更复杂
        # 瞬移防治：在"自己所在的这块屏"里换位置，而不是被拽到主屏
        screen_geom = self._current_screen_rect()
        # 移动到本屏的另一端
        new_x = random.randint(screen_geom.x() + screen_geom.width() // 2,
                               screen_geom.x() + screen_geom.width() - max(1, self.width()))
        new_y = random.randint(screen_geom.y() + screen_geom.height() // 2,
                               screen_geom.y() + screen_geom.height() - max(1, self.height()))
        
        self.target_pos = QPoint(new_x, new_y)
        self.is_moving = True
        self.current_activity = "running"
        
    def _recover_from_fear(self):
        # 从恐惧中恢复
        self.dialogue_ui.set_face("normal")
        self.dialogue_ui.show_dialogue("呼...好可怕啊，我们离那里远一点吧...")
        self.emotion_system.add_emotion("fear", -20)
        self.emotion_system.add_emotion("happy", 10)
        
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

    def _current_screen_rect(self):
        """Ralsei 当前所在的那块显示器的可用区域（QRect）。

        瞬移防治：躲猫猫"中心点"、"远离回收站"、"施法锚点网格"等原先一律用
        `availableGeometry()`（= 主屏）。副屏上的 Ralsei 会被要求横跨整个桌面
        走过去/被直接搬回去，看起来就是瞬移。这里取它自己所在的屏。
        """
        try:
            rect = QApplication.desktop().screenGeometry(self)
            if rect is not None and rect.width() > 0 and rect.height() > 0:
                return rect
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        return QApplication.desktop().availableGeometry()

    def _clamp_pos_to_desktop(self, x, y):
        """把窗口左上角夹紧到"多显示器虚拟桌面"范围，返回 (int x, int y)。

        瞬移防治：原实现普遍写成 `max(0, min(x, 主屏宽 - 窗口宽))` —— 只认主屏、
        且把原点硬钉在 (0,0)。在多显示器上（副屏在主屏左侧/上方时坐标为负，
        或副屏在主屏下方时纵向超出主屏高度）宠物会被强行拉回主屏坐标空间，
        表现就是"跳一下"。统一改走 _virtual_screen_rect()（win32 虚拟桌面矩形）。
        """
        try:
            rect = self._virtual_screen_rect()
            w = max(1, self.width())
            h = max(1, self.height())
            x = max(rect.x(), min(int(x), rect.x() + rect.width() - w))
            y = max(rect.y(), min(int(y), rect.y() + rect.height() - h))
        except Exception as e:  # 夹紧失败时保持原值，绝不因为夹紧而挪窗口
            _log.debug("main 防御性异常（已忽略）: %s", e)
        return int(x), int(y)

    def _desktop_floor_y(self):
        """"地面"的 y 坐标（窗口左上角贴住虚拟桌面底边），用于坠落/弹跳落地判定。"""
        try:
            rect = self._virtual_screen_rect()
            return rect.y() + rect.height() - max(1, self.height())
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return QApplication.desktop().availableGeometry().height() - max(1, self.height())

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

        # 2.55 H5 S1：输出"动画名未命中"汇总（纯日志，不改任何状态）
        try:
            self.sprite_loader.log_animation_miss_summary()
        except Exception as e:  # 观测代码绝不能影响退出流程
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
                # 第九轮：记忆位置可能已迁到设备(E盘)或落在桌面兜底目录，
                # 且新增了片段/关键记忆/日摘要/留档副本 —— 统一交给 reset_all()，
                # 免得只删一个文件、留下一堆"记得一半"的残留。
                _ms = self.memory_system
                if callable(getattr(_ms, 'reset_all', None)):
                    _ms.reset_all()
                else:
                    memory_file = _ms.memory_file
                    if os.path.exists(memory_file):
                        os.remove(memory_file)
                _log.debug("记忆数据已清理")
            except Exception as e:
                _log.debug(f"清理记忆数据时出错: {e}")

            # 清理成长数据
            try:
                growth_file = self.social_growth.growth_data_path
                if os.path.exists(growth_file):
                    os.remove(growth_file)
                    _log.debug("成长数据已清理")
            except Exception as e:
                _log.debug(f"清理成长数据时出错: {e}")

            # 清理娱乐数据
            try:
                entertainment_file = self.entertainment_system.entertainment_data_path
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
            screen = self._current_screen_rect()
            cols = 8
            rows = 6
            col = idx % cols
            row = (idx // cols) % rows
            cell_w = screen.width() / cols
            cell_h = screen.height() / rows
            cx = int(screen.x() + col * cell_w + cell_w / 2)
            cy = int(screen.y() + row * cell_h + cell_h / 2)
            return (cx, cy)
        except Exception:
            screen = self._current_screen_rect()
            return (int(screen.x() + screen.width() / 2), int(screen.y() + screen.height() / 2))


    # ==============================================================
    # 躲猫猫游戏 Hide and Seek
    # 流程：start → 走到屏幕中央 → [spell] 创建 5 个障碍物文件夹（上 3 下 2）
    #       → [spell] 做躲藏仪式 → 移动到选中的文件夹前 → 打开文件夹 →
    #       → searching 阶段（用户点击正确文件夹 = 玩家赢，超时 = Ralsei 赢）
    #       → 结束：清理 5 个障碍物文件夹
    # ==============================================================

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
            # 崩溃日志同样进"最终存储"（E 盘优先，见 data_store）；拿不到才回落程序目录
            try:
                import data_store
                crash_path = data_store.artifact_path(os.path.join("logs", "crash.log"))
            except Exception:
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
    global _single_instance_mutex
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
            QMessageBox.warning(None, "提示", "Ralsei Pet 已经在运行中！")
            sys.exit(0)
        else:
            _log.debug("单实例检查通过，互斥量已创建")
            # 修复：句柄必须保持存活到进程结束。局部变量在函数返回后被 GC
            # 关闭句柄，命名互斥量在最后一个句柄关闭时会被系统销毁，导致第二次
            # 启动可成功创建同名互斥量 → 单实例保护失效（双实例并存）。
            # 存入模块级引用，进程退出时由操作系统自动释放。
            _single_instance_mutex = mutex
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
                QMessageBox.warning(None, "提示", "Ralsei Pet 已经在运行中！")
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

    # 分词引擎：接入 jieba（可选增强；没装/加载失败都会静默回落内置词法，不影响启动）
    try:
        import text_segmenter
        text_segmenter.install()
        _log.info("%s", text_segmenter.describe())
    except Exception as e:
        _log.debug("分词引擎接入失败（继续用内置词法）: %s", e)

    # 数据位置：E 盘在线就把本地中转站里的东西搬进最终存储（离线时它自己会跳过）
    try:
        import data_store
        _log.debug("数据存储: %s", data_store.describe())
        _rep = data_store.migrate_from_staging()
        if _rep.get('moved'):
            _log.info("已把本地中转站数据搬进最终存储: %s", _rep['moved'])
        if _rep.get('errors'):
            _log.debug("数据回迁未完成的部分: %s", _rep['errors'])
    except Exception as e:
        _log.debug("数据回迁检查失败（已忽略）: %s", e)

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
        QMessageBox.warning(None, "错误", f"程序运行时出错: {e}")
        sys.exit(1)
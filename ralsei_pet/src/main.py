
import sys
import os
import time
import functools

# ★ 第67轮修复（既有缺陷，真机取证暴露）：`modules/` 必须**赶在
#   `from logger_utils import get_logger`（下方第 20 行附近）之前**进 sys.path。
#   原顺序把这一步放在第 308 行附近（PyQt 导入之后），对 `logger_utils` 来说**太晚**：
#   import 期必然 ImportError ⇒ 落到兜底的 `logging.getLogger(name)`，而
#   `__name__ == '__main__'` 得到的 logger 名叫 **`__main__`** —— 它**不在 `ralsei_pet`
#   树下、没有任何 handler** ⇒ main.py 自己的日志（灵魂就绪 / NPC 就绪 / 幽灵就绪…）
#   在真实运行里**全部被静默丢弃**，只有 `modules/*` 的日志能落到文件里。
#   取证方式（第67轮）：用 PYTHONPATH 注入 sitecustomize 在 **logging 调用点**打钩，
#   看到 `[DIAG:INFO] __main__ | 幽灵就绪：…` —— 即"日志文件里查无此行"的根因是
#   **日志器接错了地方**，不是幽灵没跑。教训：产物侧（日志文件）看不见，不等于
#   调用侧没发生；判据必须两边都站。
#   这里只提前**路径**，不改任何导入语句、不改日志内容。
_project_root_early = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_modules_dir_early = os.path.join(_project_root_early, 'modules')
for _p_early in (_project_root_early, _modules_dir_early):
    if _p_early not in sys.path:
        sys.path.append(_p_early)

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
    # ★★ 第75轮：**降级路径也必须挂到 ralsei_pet 树下**。
    #   原来这里直接 `logging.getLogger(name)` ⇒ 拿到裸名（`modules.xxx`），
    #   而包内导入（main.py 走 `from modules.x import ...`）恰好会让上面的
    #   `from logger_utils import ...` 失败、必然走本分支 ⇒
    #   这些模块的日志既没有文件 handler（不在 ralsei_pet 树下），
    #   有效级别也退回 WARNING ⇒ **INFO 级日志全部丢失**（实测 25 个模块）。
    #   这正是"程序坏了但日志里查不到"的根因。
    try:
        from modules.logger_utils import adopt_module_logger as _adopt
    except ImportError:
        try:
            from logger_utils import adopt_module_logger as _adopt
        except ImportError:
            import logging as _logging

            def _adopt(_g):
                return _logging.getLogger('ralsei_pet.' + str(_g.get('__name__', '')))

    def get_logger(name=None):
        return _adopt(globals())

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
#   sit / sit_rest               待机（窝着）坐姿 —— 见下方第54轮说明
# 其余（laugh / dance / sing / wave / curtsy / hug / pose / tea / nuzzle / victory /
# spin / bow / look_up / surprised / cry / sad / happy / act / book_look …）= 特殊动画。
#
# ★ 第54轮：`sit` 为什么算"姿态"而不是"表演"
#   `sit`（站→下沉→坐定的 4 帧过渡）与 `sit_rest`（坐定静帧）由**确定性状态机**
#   `_idle_lounge_tick` 驱动：静止满 IDLE_LOUNGE_AFTER_SECONDS 才发生，一天里至多几次。
#   这与 `splat` / `land`（摔倒流程）同类 —— 都是"状态真的变了"的姿态/流程动画，
#   而不是"走着走着突然跳舞"那类表演动画。第8轮契约（特殊动画只由用户/AI 触发、
#   播完为止、播放期不移动）针对的正是后者；把 `sit` 留在特殊类里会与"它由状态机触发"
#   这一事实自相矛盾（同一份表既说它特殊、又允许状态机自动触发它）。
#   注意：`_is_special_anim` 按 `name.split('_')[0]` 取组，所以登记 `'sit'` 即同时覆盖
#   `sit_rest`。过渡期间"播完为止"由 `_play_once_active` 保证，不依赖本表。
_NON_SPECIAL_ANIM_GROUPS = frozenset({
    'idle', 'walk', 'run',
    'jump', 'fall', 'splat', 'land', 'hatless_throw', 'slide', 'roll',
    'spell', 'item', 'sit',
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
from modules.api_client import create_client, WarmKeeper
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
from modules.scene_canvas import SceneCanvas, BubbleOverlay
# ---- 灵魂（SOUL，第55轮）----------------------------------------------------
# 用户口径：「别换鼠标的样子了，改成可移动的那个灵魂图标…鼠标可拖拽灵魂，键盘可操控移动…
#   原先和你说的鼠标附身换成就是这个灵魂的功能…灵魂也可自由出入各个场景，
#   相当于这也是一个有互动的实体」
# 分工：
#   soul_entity  纯逻辑：位置/速度/按键/拖拽/钳制/场景位置簿/门控（零依赖，可离线回归）
#   soul_overlay 绘制：把 state 画成桌面上的那只 48×48 SOUL（独立顶层窗口）
#   src/main.py  组装：热键 / 每帧推进 / 键盘桥 / 与场景和可交互物的接线
# ⚠️ `SoulOverlay` 走**模块引用**（`soul_overlay_mod.SoulOverlay`）而不是直接名字导入：
#    第55轮要同时用到 `load_soul_sprites` 与 `direction_of_qt_key`，
#    三个名字混着导会让"这个函数到底在哪一层"变得说不清。
from modules import soul_entity as soul_entity_mod
from modules import soul_overlay as soul_overlay_mod
from modules.soul_overlay import load_soul_sprites
# ---- 幽灵（GHOST，第67轮）---------------------------------------------------
# 用户口径（第64轮原话）：「我把 chara 改了一下，就用红与黄.apk 里面的幽灵就好，
#   只有决心强的人能看到幽灵（ralsei 是个特例）」；
# 第66轮补裁定：N1 =「用和 kris 等人接触的时间算」、N2 =「定点距离」、
#   N3 =「接线时机你来看就好」（⇒ 本轮接线）。
# 分工（与灵魂同构，三层各管一段）：
#   ghost_system  纯逻辑：距离式 alpha / 上下浮动 / 决心门槛 / 接触时钟（零依赖，可离线回归）
#   ghost_overlay 绘制：把 state 画成桌面上那只定点幽灵（独立顶层窗口，**纯视觉不吃事件**）
#   src/main.py   组装：接触计时（谁在场）/ 每帧推进 / 显示与藏起 / 落盘
# ⚠️ `ghost_overlay` 从 `soul_overlay` **import** `virtual_screen_rect`（唯一实现，
#    契约①：禁用 `availableGeometry()`）；这里只做组装，不重复那 20 行。
from modules import ghost_system as ghost_system_mod
from modules import ghost_overlay as ghost_overlay_mod
# ---- 附身（POSSESSION，第82轮 R5）------------------------------------------
# 用户口径（第76轮需求锁定原话，逐字）：「交互键用Z（对 kris 和 firsk，niko 用
#   可以在征求他们同意的情况下附身（特效用原作的），也就是达到原作操控的功能）」。
# 分工（与灵魂同构，**判定与显示分开**）：
#   possession  纯逻辑：附身状态机（谁能直接附 / 谁要先问 / 方向键归谁 / 3px 步进）
#               —— 零依赖，可离线回归（`check82` 锁它）
#   src/main.py 组装：Z 键入口 / 每帧把方向键转给"当前操控对象" / 征求同意的对话
# ★★ 原作依据（第82轮 UTMT 反取证，物证 `第82轮-灵魂附身R5/_evidence/`）：
#   Z ⇄ `control_check_pressed(0)` → `event_user(0)`（`obj_mainchara_Step_0`）；
#   主角移动 = `obj_time.left/up/right/down` × 3 px/帧；灵魂移动 = 同一组布尔 × `global.sp`。
#   ⇒ 原作里的"操控谁"就是**同一套输入指向不同实体**，"附身"= 换消费方，不是新物理。
# ⚠️ 走**模块引用**（`possession_mod.PossessionState`），与 soul/ghost 同一纪律。
from modules import possession as possession_mod
# ---- 带路（ESCORT，第83轮 R6）---------------------------------------------
# 用户口径（第76轮需求锁定原话，逐字）：「R6 可请求角色带灵魂走」。
# ★ 本轮两条用户裁定（2026-10-03，逐字）：
#   「**新增 G 键**」＋「**完全照原作（直接置位）**」。
# 分工（与 R5 附身**并列但正交**）：
#   escort      纯逻辑：带路状态机（谁能带 / 谁要先问 / 轨迹延迟采样 / 直接置位）
#               —— 零依赖，可离线回归（`check83` 锁它）
#   src/main.py 组装：G 键入口 / 每帧把带路者位置压进轨迹并把灵魂置位 / 征求同意的对话
# ★★ 原作依据 / 以及"原作没有这条"的诚实标注：
#   机制照抄毛毛虫 —— `obj_caterpillarchara` 的 `remx[25]/remy[25]` +
#   `scr_makecaterpillar` 的 `target = 12 + (slot * 12)`（物证 `第46轮/_evidence/`）。
#   ⚠️ 但**方向与原作相反**：原作 `parent = obj_mainchara` 是**主角带路、队友跟随**；
#      R6 是**角色带路、灵魂跟随**；且原作**没有"灵魂"这个可被带领的实体**
#      （`obj_heart` 只在战斗界面）⇒ "灵魂"是本项目实体，R6 整体是**本项目扩展**。
#      ⇒ 注释与报告里**不许**写"原作就是这样"。
# ⚠️ 与 R5 **互斥**：两个状态机若同时"自认为在管主体位置"，会同帧两处写坐标
#    （"同一份规则两处算"是本项目最贵的坑）。裁决见 `init_escort` / `toggle_escort`。
from modules import escort as escort_mod
# ---- 剧情进度标记（PLOT MARK，第85轮 I10）----------------------------------
# 用户口径（第85轮，逐字）：「**别毁，就是已经过完剧情了就好**」。
# ★★ 原作真身（第85轮 UTMT 反编译 Deltarune ch1 逐字）：
#   `obj_npc_susiedark_Create_0`：`if (global.plot >= 30) { instance_destroy(); }`
#   —— 那是**出场门控**（剧情过了某点 ⇒ 该 NPC 不再生成），**不是删存档**。
# ⇒ 本项目**照用户口径收窄**：只记一个"已过完剧情"的标记，
#   **不做** `instance_destroy` 等价物、不删 NPC / 道具 / 存档、**不门控**。
# ★★★ 第86轮用户裁定（逐字）：「**那就别判定死亡，就全部放行就好**」
#   ⇒ 本项目**没有任何出场门控**（既不按进度、也不按生死）—— NPC 一律可出现；
#     第85轮设想的"生死门控"**作废**。此标记与出场**毫无关系**。
# 分工：
#   plot_mark   纯逻辑：标记表（key 归一 / 幂等写入 / 快照）—— 零依赖，可离线回归
#   src/main.py 组装：初始化 / 落盘（走 data_store 唯一入口）
from modules import plot_mark as plot_mark_mod
# 球容器（第50轮）：Ralsei 在光世界**必须被"扭蛋球"罩住**才能存身。
# 分工（三层各管一段，与场景系统同源）：
#   bubble_system  → 规则（谁能进 / 何时脱 / 4 向旋转 / 塑料滤镜参数），零依赖
#   scene_render   → 几何（球画在哪、多大、四层的绘制序）—— 纯数据
#   src/main.py    → 组装（谁在球里 → 交给渲染计划）+ 触发入口（toggle_bubble）
from modules import bubble_system as bubble_system_mod
from modules import scene_render as scene_render_mod
# ---- 道具 / 背包 / S 键菜单（第48轮）----------------------------------------
# 用户口径：「可互动的道具也要做到可以互动；道具效果不可带出当前章节的场景；
#   在其他场景使用非当前场景的道具就显示"一股神秘的力量阻止了你"；
#   游戏里的背包这类的通过 S 键实现的菜单也要应用哦，但，设置不应用」。
# 分工（**判定与显示严格分开**，见各模块 docstring）：
#   item_system   两个袋子 + 垃圾团 + 全部"能不能用"的判定（零依赖纯逻辑）
#   item_menu     状态机：按键 → MenuFrame（零 Qt，可离线回归）
#   item_menu_ui  绘制：MenuFrame → 屏幕面板（复用第44轮原作对话框框体）
#   item_interact 场景 objects → 可交互物（存档点/暗之泉/拾取，含数据缺口登记）
#   global_hotkey 全局热键（★ 只注册带修饰键的组合，绝不劫持裸字母）
from modules import item_system as item_system_mod
from modules import item_menu as item_menu_mod
from modules import item_menu_ui as item_menu_ui_mod
from modules import item_interact as item_interact_mod
from modules import global_hotkey as global_hotkey_mod
from modules import scene_system as scene_system_mod
# 伙伴交互协议（第46轮）：`InteractBus`（= 原作 `global.interact` 全局锁）+
# `Interactable`（= 原作 `myinteract` 三态）。道具/场景可交互物都挂在这套协议上，
# 不另起一套 —— 那会让"对话时能不能点东西"出现两套互相不知道的锁。
from modules import companion as companion_mod
# NPC 分层 / 跟随策略 / 世界门控（第49~50轮，P0~P2 零接线骨架；★ 第55轮**接线**）
# 与 NPC 人设 / 独立记忆 / 跟随决策（★ 第55轮新增，零依赖纯逻辑）。
#
# ⚠️ 为什么用 `import ... as ..._mod` 而不是 `from ... import load_registry`：
#   两个模块都是"多处取用同一个名字"的形状，直接导入具体名字会让
#   **测试桩替换 / 后续改名**都要动多处调用点；模块引用只有一处（本行）。
from modules import npc_system as npc_system_mod
from modules import npc_persona as npc_persona_mod
# NPC 站位 / 游荡 / 编队 / 结对（★ 第56轮新增，零依赖纯逻辑）。
# ★ 与 `npc_system` **刻意分成两个模块**：后者管"能不能进这个世界"（政策），
#   前者管"他在这个世界里怎么走"（运动学）。混在一起会让
#   `verify_npc49` 的零依赖 AST 闸（A 段）面对一个体积翻倍的模块。
from modules import npc_placement as npc_placement_mod
# NPC 「自由生活」策略层（★ 第73轮新增，零依赖纯策略：场景特质 / 熟络度 / 传话 / 自主节拍）。
# ★ 与 `npc_system` 的分工：后者答"**能不能进这个世界**"（许可，第72轮），
#   本模块答"**进去了之后怎么过日子**"（行为）——"对场景有反应 / 循序渐进地熟起来 /
#   把自己知道的说给别人"。再糊回 `npc_system` 会让 49 轮那道零依赖 AST 闸面对一个
#   体积翻倍的模块（与 `npc_placement` 分出去的同一个理由）。
from modules import npc_life as npc_life_mod
# ★★★ 第78轮：NPC 自主生活 · **层1 意图层**（零依赖纯函数：去哪 / 找谁 / 干什么 /
#   生活规划 / 睡哪）。用户口径（逐字）：「他们生活是生活，我和他们只是朋友，而不是
#   主导人…不会因为缺少一个人哪怕是我他们就不生活了」「去哪？找谁？干什么？生活规划
#   这类的事也是由各自的 AI 决定」「不是一到晚上就必须回自己家，也可以选择在朋友那
#   睡觉」「人味，人味，还 tm 是人味」。
#   ★ `decide()` 的签名里**没有** pet/user/player —— 这是 L2 的**结构保证**（见 `check78`）。
from modules import npc_intent as npc_intent_mod
# ★★★ 第79轮：NPC 自主生活 · **层2 驻留层**（零依赖：把「静态归属」升级成
#   「静态归属 + 动态驻留覆盖」）。要解决的头号障碍：`_npc_seed_bodies()` 只在启动与
#   切场景时被调 ⇒「NPC = 当前场景的装饰」⇒ **用户不动，世界就冻住**（与 L2 正相反）。
#   ★ `enabled=False` 时 `step()` 零副作用 ⇒ 产品默认关时行为与第78轮逐字相同。
from modules import npc_roam as npc_roam_mod
# ★★★ 第81轮：NPC 自主生活 · **层4 存档**（零依赖：只 import 标准库，路径由调用方注入）。
#   要解决的问题：层1/2/3 的状态**只在内存** —— 桌宠一重启，`RoamState` 清空、
#   `Plan` 丢失 ⇒ NPC「昨天睡在朋友家」这件事第二天就不记得了，
#   `choose_sleep_scene(last_sleep=...)` 的降权永远拿不到值（形同虚设）。
#   ★ 本模块**不 import `data_store`**（初始化环，本项目栽过 4 次）——
#     路径由 `_npc_plan_file()` 这个调用方注入（与 `_ghost_state_path()` 同规）。
from modules import npc_plan_store as npc_plan_store_mod
# 事件台词（S7）：档位登记 / 提示词构造 / 首句截断 / 罐头去重，都是纯逻辑（无 Qt）
from modules.event_speech import (TIER_AI, EVENT_MAX_CHARS, RecentLinePicker,
                                  build_prompt, guard_reaction, pet_kind, tier_of,
                                  first_sentence, strip_action_parentheticals,
                                  looks_out_of_character, looks_like_assistant_speak)
# ★★ 宠物手势判定（第75轮 B3）：**唯一真源**。
# 改造前 `mousePressEvent` / `mouseMoveEvent` / `mouseReleaseEvent` /
# `mouseDoubleClickEvent` 各写了一份"部位识别 + 手势识别"（含 `get_ralsei_body_part`
# 与 `_pet_detection_state` 状态机，约 666 行），与 `modules/pet_interaction.py`
# 功能重叠。第75轮统一到模块：主窗口只负责
#   ① 把 `event.pos()` 转成"相对精灵的像素" 交给 tracker；
#   ② 拿回 `PetEvent` 后按 `(body_part, gesture)` 查表执行（情绪/动画/台词）。
# 那一份手写判定**已删除** —— 不要再写第三份。
from modules.pet_interaction import (PetInteractionTracker, PetEvent, BodyPart,
                                     Gesture, kind_for, RESPONSE_SPEC,
                                     STROKE_EMOTIONS, STROKE_POOL,
                                     STROKE_POOL_OTHER)
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


# ---------------------------------------------------------------- 预热（B8）
def prewarm_order(ids, team=(), here=()):
    """★ 第74轮（B8）：NPC 预热顺序 —— **主角团 → 当前场景在场的 → 其余全部**。

    用户口径原话：「开场先检测周围有哪些 NPC，优先给他们预热，或是在启动程序的
    时候就预热，没有什么常聊这类的，尽量全预热」＋「**先预热主角团**」。
    ⇒ 刻意**不挑**"常聊的 2~3 人"（那是我的旧建议，用户否了）：就按这三档排队，
      用户一开口就让路（见 `RalseiPet._prewarm_should_yield`）。

    纯函数（只排序、不碰 App、不碰网络）⇒ 可单独断言，不受真机/模型影响。

    :param ids:  候选 id（进来什么顺序都不影响结果）
    :param team: 主角团 id。真源 = `_placement.json` 的 `groups[id=party].members`；
                 团内按**给定顺序**（= 队伍顺序 kris → susie → ralsei）
    :param here: 当前场景在场的 id。真源 = `npc_bodies`（见 `_npc_life_ids`）
    """
    team_index = {}
    for i, n in enumerate(team or ()):
        if isinstance(n, str) and n and n not in team_index:
            team_index[n] = i
    here_set = set(h for h in (here or ()) if isinstance(h, str) and h)

    def _key(n):
        i = team_index.get(n)
        if i is not None:
            return (0, i, n)        # ① 主角团（最先）
        if n in here_set:
            return (1, 0, n)        # ② 当前场景在场的
        return (2, 0, n)            # ③ 其余全部（"尽量全预热"）

    return sorted((n for n in (ids or ()) if isinstance(n, str) and n), key=_key)


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
        # 保温看门狗（第58轮）：把 keep_alive 立到"模型载入实例"上，见 _sync_warm_keeper。
        # 先置 None —— 下面 init_systems() 里拿到真 client 之后再按配置启起来。
        self._warm_keeper = None
        #: 启动预热只做一次（QTimer 迟到触发/重复调用都不该重复发包）
        self._prewarm_started = False
        
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
        self._ai_delta_gen = 0        # 请求世代号：每次发起新请求 +1（分片身份）
        # ★ 第74轮（B9）：**槽世代** —— 只有"带流式接收方"的请求才会推进它。
        #   后台请求（事件台词 / 跟随决策 / 自主发言）不带 on_delta，以前会把自己
        #   （None）覆盖进 sink 槽、并顺带把世代号 +1，导致前台正在流式的那条请求
        #   后续分片全被判过期丢弃（第58轮实测 42 次里 17 次"零分片"）。
        self._ai_delta_sink_gen = 0
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
        
    def _make_tray_icon(self):
        """托盘图标：优先用真素材 `spr_ralsei_idle_0.png`，拿不到再退回程序内画的圆头。

        ★ 为什么不再只用"程序内画的圆头"（第51轮用户口径）：
          用户原话「让他后台运行的时候有个图标，我可以方便关掉他」——
          托盘存在的意义是**一眼认出这是 Ralsei**，所以优先用原作素材。
          但素材可能缺失（`deltarune_ralsei/` 是可选目录）⇒ 必须保留纯绘制兜底，
          否则托盘会整体初始化失败，退化到"任务管理器才能杀"的更差状态。
        """
        from PyQt5.QtGui import QPixmap, QPainter, QBrush, QColor, QIcon
        from PyQt5.QtCore import Qt
        try:
            loader = getattr(self, 'sprite_loader', None)
            base = getattr(loader, 'sprite_dir', None)
            if base:
                cand = os.path.join(base, 'spr_ralsei_idle_0.png')
                if os.path.isfile(cand):
                    pm = QPixmap(cand)
                    if not pm.isNull():
                        return QIcon(pm.scaled(64, 64, Qt.KeepAspectRatio,
                                               Qt.SmoothTransformation))
        except Exception as e:
            _log.debug("托盘图标读素材失败，退回绘制图标: %s", e)
        pix = QPixmap(64, 64)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(96, 200, 210)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(6, 4, 52, 44)   # 头
        p.drawEllipse(18, 34, 28, 26)  # 身体
        p.end()
        return QIcon(pix)

    def _setup_tray(self):
        # 历史修复：右键"隐藏"后原实现无任何 GUI 恢复入口（无托盘/热键），而顶层单实例
        # 互斥又拒绝重启新实例 → 宠物"永久丢失"，只能任务管理器杀进程。
        #
        # ★★ 第51轮修复（用户口径：「加一个托盘图标，后台运行的时候有个图标，
        #    我可以方便关掉他」）：**图标建好却从没 `show()` 过** ——
        #    `tray.show()` 原先只在 `_hide_ralsei()` 里调用，于是"没隐藏过"的用户
        #    在整个会话里**根本看不到托盘图标**，菜单里的"退出"也就无从点起。
        #    现在：建好即常驻显示；显隐由菜单项控制，**不再**随"显示 Ralsei"一起消失
        #    （图标消失=用户又失去唯一的退出入口，那是同一个坑的另一种形态）。
        try:
            from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
            if not QSystemTrayIcon.isSystemTrayAvailable():
                self._tray = None
                return
            tray = QSystemTrayIcon(self._make_tray_icon(), self)
            menu = QMenu(self)
            show_action = QAction("显示 Ralsei", self)
            show_action.triggered.connect(self._show_from_tray)
            hide_action = QAction("隐藏 Ralsei", self)
            hide_action.triggered.connect(self._hide_ralsei)
            quit_action = QAction("退出 Ralsei", self)
            quit_action.triggered.connect(self._quit_from_tray)
            menu.addAction(show_action)
            menu.addAction(hide_action)
            menu.addSeparator()
            menu.addAction(quit_action)
            tray.setContextMenu(menu)
            tray.setToolTip("Ralsei 桌宠（右键可退出）")
            tray.activated.connect(self._on_tray_activated)
            tray.show()                      # ★ 常驻显示（第51轮修复点）
            self._tray = tray
            # ★ 首次启动弹一次气泡：Windows 11 默认把**新注册**的托盘图标收进
            #   "隐藏的图标"溢出区（系统行为，程序无法直接改）—— 不提示的话
            #   用户还是会以为"没有图标、关不掉"。气泡同时会让系统把图标
            #   临时显示在可见区，是这条提示之外的实际收益。
            #   只弹一次（config 落盘），避免每次开机都打扰。
            try:
                if not self.config_manager.get('ui.tray_hint_shown', False):
                    tray.showMessage(
                        "Ralsei",
                        "我到托盘里待着啦～ 右键这个图标可以退出我",
                        QSystemTrayIcon.Information, 6000)
                    self.config_manager.set('ui.tray_hint_shown', True)
            except Exception as e:
                _log.debug("托盘首次提示失败（不影响使用）: %s", e)
        except Exception as e:
            _log.warning(f"系统托盘初始化失败（不影响使用）: {e}")
            self._tray = None

    def _quit_from_tray(self):
        """托盘"退出"：走与菜单退出同一条清理路径，再退 Qt 事件循环。

        ★ 为什么不能只 `QApplication.quit()`（原实现）：那样会跳过
          `cleanup_on_exit()`，托盘图标/全局热键/常驻线程都留着残留，
          用户下次启动可能被单实例互斥挡住（"明明关了却起不来"）。
        """
        try:
            self.cleanup_on_exit()
        except Exception as e:
            _log.warning("托盘退出时清理异常（仍继续退出）: %s", e)
        tray = getattr(self, '_tray', None)
        if tray is not None:
            try:
                tray.hide()
            except Exception as e:
                _log.debug("main 防御性异常（已忽略）: %s", e)
        QApplication.quit()

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
        """把宠物从托盘/最小化状态恢复出来。

        ⚠️ 第51轮：**不再**顺手 `self._tray.hide()`。原写法把托盘图标当成
        "隐藏态指示器"，恢复后就把唯一的退出入口一起抹掉 —— 与"常驻图标"的口径冲突。
        """
        self.show()
        try:
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        try:
            from PyQt5.QtWidgets import QSystemTrayIcon
            # 单击=显示（Windows 上 Trigger 即单击）；中键/双击=在显隐之间切换
            if reason == QSystemTrayIcon.Trigger:
                self._show_from_tray()
            elif reason == QSystemTrayIcon.DoubleClick:
                if self.isVisible():
                    self._hide_ralsei()
                else:
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

        # ---- 球容器前层（第50轮）：★ 必须**盖在 sprite_label 之上** ----
        # 球的绘制序是 `back → 角色 → front → top`；角色是 `sprite_label` 画的，
        # 若把 front/top 也画进 `scene_canvas`（在角色**之下**），球壳会被角色盖住
        # ⇒ 看着像"角色站在球前面"，与用户要的「ralsei是在球里面」相反。
        # 所以前层要有**自己的控件**（见 `BubbleOverlay`），并在每帧 `raise_()`。
        self.bubble_overlay = BubbleOverlay(self)
        self.bubble_overlay.move(0, 0)

        # 创建主标签用于显示精灵
        self.sprite_label = QLabel(self)
        self.sprite_label.setGeometry(0, 0, 100, 100)
        self.sprite_label.setAlignment(Qt.AlignCenter)
        
        # 启用鼠标追踪，以便Ralsei能够响应鼠标事件
        self.setMouseTracking(True)
        self.sprite_label.setMouseTracking(True)

        # ★★ 宠物手势判定器（第75轮 B3）：模块 = 唯一真源。
        # tracker 接收"相对精灵左上角的像素坐标"，返回 PetEvent。
        # 精灵图像每次换帧都会变（大小可能不同），故在 `_sync_pet_tracker_sprite`
        # 里跟着 `sprite_label` 的当前 pixmap 更新。
        self._pet_tracker = PetInteractionTracker()

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

        # 保温（第58轮）：client 一到位就按配置把看门狗启起来。
        # 为什么放在 create_client **紧后面**：配置保存/连接测试那两处也会重建 client
        # （main.py 的 create_client 一共三个调用点），三处都必须同步 —— 否则会出现
        # "看门狗还握着旧 base_url 在发请求"这种最难看的问题。
        self._sync_warm_keeper()
        # 启动预热（startup.prewarm，默认 false）：用 singleShot 推到事件循环起来之后，
        # 不阻塞 __init__。见 _prewarm_ai_cache。
        try:
            if bool(self.config_manager.get('startup.prewarm', False)):
                QTimer.singleShot(1500, self._prewarm_ai_cache)
        except Exception as e:  # 预热是可选优化，绝不能拖垮启动
            _log.debug("main 防御性异常（已忽略）: %s", e)
        
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
        # ---- 自主寻路（第45轮："语境说去教堂 → 自己走过去"）状态 ----
        # 同一条铁律：控制器会用到的名字必须在**宿主**预声明。
        self._scene_aliases = None                  # load_aliases() 的结果（中文目的地→英文关键词）
        self._scene_room_graph = None               # load_room_graph() 的结果（原作 782 条边）
        self._pathfind_loaded = False               # 寻路数据是否已尝试加载过（幂等守卫）
        self._scene_chapter_id = None               # 当前章 id（寻路②消歧用，从 SceneState 投影）
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

        # ---- 道具 / 背包 / S 键菜单 接线（第48轮）----
        # 为什么放在**最后**：道具域（明/暗世界）要从"当前场景"推出来，而
        # `current_scene` / `_scene_state` 刚刚在上面几行才被写进去；放在前面会拿到 None。
        self.init_item_systems()

        # ---- 灵魂（SOUL）接线（第55轮）----
        # 为什么排在**最末**：灵魂要往 `_scene_switch_hooks` 里**追加**一个钩子，
        # 而那个列表是 `init_item_systems()` 里以 `self._scene_switch_hooks = [...]`
        # **整体赋值**出来的 —— 提前追加会被覆盖掉。
        # （"一个列表被整体赋值"是本项目状态劈裂的老坑，见 W1-4 报告铁律 3。）
        self.init_soul()

        # ---- NPC 人设 / 独立记忆 / 跟随决策 接线（第55轮）----
        # 为什么排在**灵魂之后**（即整条链的最末）：
        #   NPC 层也要往 `_scene_switch_hooks` 里追加一个钩子，而那个列表是
        #   `init_item_systems()` 里**整体赋值**出来的 ⇒ 任何"提前追加"都会被覆盖。
        #   灵魂已经是"追加型"的先例，这里跟着它排（顺序只看这一条依赖）。
        self.init_npc_systems()

        # ---- 幽灵（第67轮）----
        # 为什么排在**最末**：幽灵要从 `self.npc_bodies` 读"谁在场"（接触计时的数据源），
        # 而那份身体表是 `init_npc_systems()` 里播下的 ⇒ 提前建会拿到空表。
        # ⚠️ 幽灵**不**往 `_scene_switch_hooks` 里追加东西（它是**定点**的，
        #    "换场景就换位置"恰好是它不该有的行为）⇒ 没有那条例外的顺序依赖。
        self.init_ghost()

        # ---- 附身（POSSESSION，第82轮 R5）----
        # 为什么排在**最后**：附身要从 `npc_system` 的登记表收集"谁可附身"，
        # 而那份表是 `init_npc_systems()` 里建起来的 ⇒ 提前建会拿到空表
        # （若拿到空表，Z 键会永远报"登记表里没有可附身目标"—— 本项目最贵的坑形态）。
        # ⚠️ 附身**不**往 `_scene_switch_hooks` 里追加东西（附身是**会话内**状态，
        #    换场景时该解除而不是"跟着搬"）。
        self.init_possession()

        # ---- 带路（ESCORT，第83轮 R6）----
        # 为什么排在附身**之后**：R6 要复用 R5 的 `ConsentState`（同一份同意表，
        # 用户裁定「Niko 需先征求同意」对两者都成立），且两者**互斥**
        # ⇒ 必须等 `self.possession` 就绪后再建，才能把互斥裁决写在一处。
        # ⚠️ 带路同样**不**往 `_scene_switch_hooks` 追加东西（会话内状态；
        #    换场景时角色不在同一场景了，该解除）。
        self.init_escort()

        # ---- 剧情进度标记（PLOT MARK，第85轮 I10）----
        # 为什么排在**最后**：它要读 `data_store`（持久化入口，在更早就绪），
        # 且与附身/带路无依赖 —— 放最后只是"越晚建越不会拖累前面的初始化"。
        # ★★★ 它**只记一个 True，不做任何销毁**（用户口径「别毁」）。
        self.init_plot_mark()

    # ==================================================================
    #  灵魂（SOUL，第55轮）—— 可拖拽 / 可键盘操控 / 可自由出入各场景
    # ==================================================================
    #: 灵魂总开关。与 `SCENE_LAYER_ENABLED` 同一形状：渲染/交互出问题时可一刀关掉定位。
    #: ⚠️ 保留它本身（不是死代码）：`False` 时 `init_soul()` 直接返回、
    #:    `self.soul = None`，所有入口都退化成"什么都没发生"。
    SOUL_ENABLED = True

    def init_soul(self):
        """建灵魂：素材 → 状态 → 独立顶层窗口 → 场景位置簿 → 场景切换钩子。

        用户口径（第55轮原话）：「鼠标可拖拽灵魂，键盘可操控移动…灵魂也可自由出入
        各个场景，相当于这也是一个有互动的实体」。

        失败语义：**只降级、不抛出**（与道具/关系/搜索同一条纪律；灵魂坏了桌宠照常跑），
        且 `self.soul is None` 时所有入口（热键 / 键盘 / 交互选目标）都**直接返回**，
        不会半死不活地"点得动但没反应"。
        """
        # 先全部预声明成 None/空 —— 中途任何一步失败，宿主也不缺属性
        # （本项目踩过"状态只在成功路径上创建"的坑：失败后别处 getattr 就炸）。
        self.soul = None
        self.soul_bookmarks = None
        self._soul_scene_id = None

        if not getattr(self, 'SOUL_ENABLED', True):
            _log.info('灵魂总开关 SOUL_ENABLED=False ⇒ 不建灵魂（用它定位问题）')
            return

        try:
            state = soul_entity_mod.SoulState()
            self.soul_bookmarks = soul_entity_mod.SoulBookmarks()
            # ★ parent=None：灵魂是**独立顶层窗口**，不隶属宠物窗口 ——
            #   宠物换房间 / 开菜单 / 缩进托盘时灵魂都留在原地，
            #   这才是用户要的「自由出入各个场景」。
            self.soul = soul_overlay_mod.SoulOverlay(
                None,
                sprites=load_soul_sprites(),
                state=state,
                on_clicked=self._soul_on_clicked,
                on_drag_end=self._soul_on_drag_end,
                on_hide=self.hide_soul,
            )
            self._soul_respawn()      # 出生点 = 宠物窗口中心 + 原作 scr_moveheart 的 (10,40)
            self._soul_scene_id = getattr(self, 'current_scene', None)
            if self.soul.show_soul():
                _log.info('灵魂就绪：%s；%s',
                          self.soul.state.describe(), self.soul_bookmarks.describe())
        except Exception:
            _log.exception('灵魂初始化失败（灵魂功能不可用，宠物照常运行）')
            self.soul = None
            return

        # 场景切换钩子：**追加**而不是整体赋值 —— `_scene_switch_hooks` 是
        # `init_item_systems()` 赋值出来的列表，整体赋值会把道具的钩子挤掉。
        try:
            hooks = self.__dict__.get('_scene_switch_hooks')
            if isinstance(hooks, list):
                if self._on_scene_switched_soul not in hooks:
                    hooks.append(self._on_scene_switched_soul)
            else:
                self._scene_switch_hooks = [self._on_scene_switched_soul]
        except Exception:
            _log.exception('灵魂场景切换钩子注册失败（换场景时灵魂不记位置）')

    def _soul_respawn(self):
        """把灵魂放到"宠物 + 原作偏移"。宠物位置不可用 ⇒ 屏幕中心（**不静默**）。"""
        soul = getattr(self, 'soul', None)
        if soul is None:
            return False
        try:
            cx = self.x() + self.width() / 2.0
            cy = self.y() + self.height() / 2.0
        except Exception:
            b = soul.screen_bounds() or (0.0, 0.0, 1920.0, 1080.0)
            cx = (b[0] + b[2]) / 2.0
            cy = (b[1] + b[3]) / 2.0
            _log.info('灵魂出生点退回屏幕中心（宠物窗口位置不可用）')
        try:
            x, y = soul_entity_mod.spawn_point(cx, cy, soul.state.scale)
            soul.state.x = x
            soul.state.y = y
            b = soul.screen_bounds()
            if b:
                soul.state.clamp_to(b)
                if self.soul_bookmarks is not None:
                    self.soul_bookmarks.set_screen(b[2] - b[0], b[3] - b[1])
            soul.apply_state_pos()
            return True
        except Exception:
            _log.exception('灵魂出生点设置失败（忽略）')
            return False

    # ---------------------------------------------------------------- 显示 / 收起
    def toggle_soul(self):
        """显示/收起灵魂。**全局热键与右键都走这里**（单一入口，与 `toggle_item_menu`
        同一条纪律：同一个动作两处实现迟早分叉）。"""
        soul = getattr(self, 'soul', None)
        if soul is None:
            _log.info('灵魂请求被忽略：灵魂未就绪（SOUL_ENABLED=%s）',
                      getattr(self, 'SOUL_ENABLED', None))
            return False
        try:
            if soul.isVisible():
                return self.hide_soul()
            return self.show_soul()
        except Exception:
            _log.exception('切换灵魂显示失败')
            return False

    def show_soul(self):
        """显示灵魂（叫回来的入口；右键收起后靠这个或热键再叫出来）。"""
        soul = getattr(self, 'soul', None)
        if soul is None:
            return False
        try:
            ok = bool(soul.show_soul(activate=True))
            if ok:
                self._soul_scene_id = getattr(self, 'current_scene', None)
            return ok
        except Exception:
            _log.exception('显示灵魂失败')
            return False

    def hide_soul(self):
        """收起灵魂。★ 收起前**记一次位置** —— 否则"收起再叫出来"会回到出生点，
        对用户来说是"它忘了我把它放哪了"。"""
        soul = getattr(self, 'soul', None)
        if soul is None:
            return False
        try:
            self._soul_bookmark_save()
            return bool(soul.hide_soul())
        except Exception:
            _log.exception('收起灵魂失败')
            return False

    # ---------------------------------------------------------------- 每帧推进
    def _soul_tick(self, dt):
        """每帧推进灵魂（挂在 30ms 的 `update_movement` 上）。

        ★ 为什么挂在 `update_movement` 而**不自己开一个 QTimer**：
          本项目已有一个 30ms 定时器（正好等于原作 `GMS2FPS = 30`，与
          `soul_overlay.SOUL_TICK_MS = 33` 对齐），再开一个只会多一条
          "两个节拍器互不同步"的隐患 —— 而灵魂的 `clamp_to` / 拖拽判定
          都要求"位置变化与窗口移动在同一拍里"。
        ★ 调用点必须在 `update_movement` 的**所有早退分支之前**（睡眠 / 施法 /
          躲猫猫 / 拖拽保护 / 特殊动画都会 return）：灵魂是独立实体，
          宠物睡着时它照样该能动。
        """
        soul = getattr(self, 'soul', None)
        if soul is None:
            return False
        try:
            if not soul.isVisible():
                return False
            return bool(soul.tick(dt))
        except Exception as e:
            _log.debug('灵魂推进异常（本帧跳过）: %s', e)
            return False

    def _soul_visible(self):
        soul = getattr(self, 'soul', None)
        try:
            return bool(soul is not None and soul.isVisible())
        except Exception:
            return False

    # ---------------------------------------------------------------- 灵魂的回调
    def _soul_on_clicked(self):
        """灵魂被**单击**（按住没怎么动）⇒ 原作的"被碰到"表现 = 受击闪烁。

        ★ 刻意**不**说话：宠物说话要走事件台词通道（S7），把它挂到"点了灵魂"上
          会让用户随手一点就触发一次 AI 请求 —— 那是本项目最忌讳的"平时乱开口"。
          受击闪烁同时也是灵魂**唯一**有帧动画的时刻（照抄原作：常态定格第 0 帧）。
        """
        soul = getattr(self, 'soul', None)
        if soul is None:
            return
        try:
            soul.state.hit()
            soul.update()
            _log.info('灵魂被点击（原地）⇒ 受击闪烁：%s', soul.state.describe())
        except Exception as e:
            _log.debug('灵魂点击回应失败（忽略）: %s', e)

    def _soul_on_drag_end(self):
        """灵魂被拖动结束 ⇒ 记一次位置。"""
        soul = getattr(self, 'soul', None)
        if soul is None:
            return
        try:
            _log.info('灵魂被拖到 %s', soul.state.describe())
            self._soul_bookmark_save()
        except Exception as e:
            _log.debug('灵魂拖拽收尾失败（忽略）: %s', e)

    # ---------------------------------------------------------------- 场景位置簿
    def _soul_bookmark_save(self):
        """把灵魂当前位置记到**当前场景**名下（归一化比例，抗分辨率/插拔屏变化）。"""
        soul = getattr(self, 'soul', None)
        bm = getattr(self, 'soul_bookmarks', None)
        if soul is None or bm is None:
            return False
        sid = self.__dict__.get('_soul_scene_id')
        if not isinstance(sid, str) or not sid:
            return False
        try:
            b = soul.screen_bounds()
            if not b:
                return False
            # 存**相对虚拟屏左上角**的比例：多屏并存时虚拟屏原点可能不是 (0,0)
            # （副屏在主屏左侧时为负值），只除宽高会把位置算歪。
            bm.set_screen(b[2] - b[0], b[3] - b[1])
            return bool(bm.save(sid, soul.state.x - b[0], soul.state.y - b[1]))
        except Exception as e:
            _log.debug('灵魂位置记录失败（忽略）: %s', e)
            return False

    def _soul_bookmark_restore(self, scene_id):
        """把灵魂放到 `scene_id` 上次的位置；没记过 ⇒ 按"宠物 + 原作偏移"重新出生。"""
        soul = getattr(self, 'soul', None)
        if soul is None:
            return False
        self._soul_scene_id = scene_id
        bm = getattr(self, 'soul_bookmarks', None)
        pos = bm.resolve(scene_id) if bm is not None else None
        if pos is None:
            _log.info('灵魂第一次到场景 %s ⇒ 按"宠物 + 原作偏移"出生', scene_id)
            return self._soul_respawn()
        try:
            b = soul.screen_bounds() or (0.0, 0.0, 0.0, 0.0)
            soul.state.x = float(pos[0]) + b[0]
            soul.state.y = float(pos[1]) + b[1]
            if b:
                soul.state.clamp_to(b)
            soul.apply_state_pos()
            soul.update()
            _log.info('灵魂回到场景 %s 的原位置 (%.0f, %.0f)',
                      scene_id, soul.state.x, soul.state.y)
            return True
        except Exception:
            _log.exception('灵魂位置还原失败（改按出生点重放）')
            return self._soul_respawn()

    def _on_scene_switched_soul(self, scene_id, scene):
        """★ 场景切换钩子：「灵魂自由出入各场景」的落地 —— 先记旧场景的位置，
        再恢复新场景的位置。

        由 `SceneController._fire_switch_hooks()` 调（钩子抛异常会被它吞掉并记日志，
        不影响切换本身，所以这里不必再包一层 try —— 与 `_on_scene_switched_items` 同）。
        """
        if getattr(self, 'soul', None) is None:
            return
        try:
            self._soul_bookmark_save()          # 旧场景（`_soul_scene_id` 此刻还没更新）
            self._soul_bookmark_restore(scene_id)
        except Exception:
            _log.exception('灵魂场景位置簿更新失败（忽略）')

    # ---------------------------------------------------------------- 键盘桥
    def _soul_press(self, direction):
        """把方向键转给灵魂。返回"这次是不是一次新的按下"（自动重复为 False）。"""
        soul = getattr(self, 'soul', None)
        if soul is None:
            return False
        try:
            return bool(soul.press_dir(direction))
        except Exception:
            return False

    def _soul_release(self, direction):
        soul = getattr(self, 'soul', None)
        if soul is None:
            return False
        try:
            return bool(soul.release_dir(direction))
        except Exception:
            return False

    # ---------------------------------------------------------------- 交互选目标
    @staticmethod
    def _soul_prop_index(key):
        """可交互物的 key → `objects` 下标。

        key 规则由 `item_interact.build_props` 定义：
          `<scene_id>#<下标>`（拾取物再加 `@<item_id>` 后缀）。
        认不出返回 `None`（**不猜**）。这条规则是**跨模块契约** ——
        那边改了这里必须跟着改，回归锁 `check55` 用真实 key 做正/负控制。
        """
        if not isinstance(key, str):
            return None
        parts = key.rsplit('#', 1)
        if len(parts) != 2:
            return None
        num = parts[1].split('@', 1)[0]
        if not num.isdigit():
            return None
        return int(num)

    def _soul_room_rect(self):
        """当前房间的世界矩形 `(0, 0, w, h)`（**逻辑坐标**）；不知道 ⇒ `None`。

        与 `_update_scene_layer` 里那段**同源同判据**（`_scene_geometry['章节:房间id']`），
        刻意抄同一套 key 规则而不是新写一套：两处对"当前是哪个房间"的理解一旦分叉，
        灵魂的交互目标就会和画面上的房间不是同一个。
        """
        try:
            rooms = self.__dict__.get('_scene_geometry') or {}
            state = self.__dict__.get('_scene_state')
            rid = getattr(state, 'original_room_id', None)
            ch = getattr(state, 'chapter_id', None)
            if isinstance(rid, int) and ch:
                rec = rooms.get('%s:%d' % (ch, rid))
                if isinstance(rec, dict) and isinstance(rec.get('w'), int):
                    return (0.0, 0.0, float(rec['w']), float(rec['h']))
        except Exception as e:
            _log.debug('main 防御性异常（已忽略）: %s', e)
        return None

    def _soul_pick_prop(self, props):
        """按**灵魂到各可交互物的距离**选一件。返回 `(prop, 说明)`；选不出 `(None, 说明)`。

        ★ 坐标从哪来（第55轮实证，不是估的）
        ------------------------------------
        两套坐标都落在**同一套逻辑房间坐标**里，可直接比距离：
          · 灵魂 → 房间：`soul_entity.screen_to_room(灵魂中心, room_rect, 虚拟屏尺寸)`
            （= `_pet_target_rect` 的逆映射；`room_rect` 来自 `_scene_geometry`）；
          · 物件 → 房间：`objects[i]['pos']`（`build_props` 的 key 让下标可逆）。
        实证：`ch1.castle_town.castle_outskirts` 房间 `w=640, h=480`，
        而 `obj_doorA` 的 `pos=[630, 280]` —— 量级吻合，是同一空间。

        ★★ 为什么取 `_scene_state.objects` 而**不是** `scene_objects`
        ------------------------------------------------------------
        `scene_objects`（"当前可见物件缓存"）**全仓没有任何人填过它** ——
        `SceneController.switch()` 里显式 `pet.scene_objects = []`，
        而唯一会填它的 `resolve_objects(screen_rect)` **零调用**（第38轮留下的
        "接口先立、消费者后到"，到第55轮仍无人消费）。
        若用 `scene_objects`，本方法会**永远**走"没有一件带坐标"的退路 ——
        这就是本项目最贵的坑：「函数写对了但产品用不上」。
        `_scene_state.objects` 则正是 `build_props` 消费的那一份、**同一顺序**，
        所以"key 里的下标 → objects 下标"是**恒成立**的（不是碰巧）。
        ⚠️ 不混用两者：`resolve_objects` 返回的是**变换后且可能被裁剪**的列表，
        下标与本列表不对应，混用会选错物件。

        ★ 三条「不伪造」
        -----------------
        1. 算不出灵魂的房间坐标（无房间几何 / 无屏幕尺寸）⇒ 返回 `(None, 原因)`，
           由调用方退回"登记顺序第一个"并**把原因写进日志**；
        2. 某件可交互物没有坐标（key 对不上 objects）⇒ 它**不参与比较**，
           绝不拿 (0,0) 顶替 —— 那会让"房间左上角"凭空多出一个候选
           （本项目最难看的那种假结果）；
        3. 一件候选都没有 ⇒ 同上退回，并如实说明。

        ★ 为什么**不**传"够不着就别选"（`max_dist`）：离得远时的正确表现是
          "走过去交互"，而不是"按 E 没反应"。所以永远取最近的那件。
        """
        soul = getattr(self, 'soul', None)
        if soul is None or not self._soul_visible():
            return (None, '灵魂未显示 ⇒ 无从比较位置')
        state = self.__dict__.get('_scene_state')
        objs = getattr(state, 'objects', None)
        if not isinstance(objs, (list, tuple)) or not objs:
            return (None, '拿不到当前场景的 objects（无场景 / 空场景）')
        pt = soul_entity_mod.screen_to_room(
            soul.state.center()[0], soul.state.center()[1],
            self._soul_room_rect(), self._virtual_screen_size())
        if pt is None:
            return (None, '算不出灵魂的房间坐标（无房间几何 / 屏幕尺寸）')
        targets = []
        for p in props:
            i = self._soul_prop_index(getattr(p, 'key', None))
            if i is None or i >= len(objs):
                continue
            o = objs[i]
            pos = o.get('pos') if isinstance(o, dict) else None
            if not (isinstance(pos, (list, tuple)) and len(pos) == 2):
                continue
            targets.append((getattr(p, 'key', None), pos[0], pos[1]))
        if not targets:
            return (None, '本场景没有一件可交互物带坐标')
        key, dist = soul_entity_mod.pick_nearest(pt, targets)
        if key is None:
            return (None, '最近判定失败（候选为空 / 坐标非法）')
        for p in props:
            if getattr(p, 'key', None) == key:
                return (p, '按灵魂位置选最近那件（距离 %.0f 逻辑单位）' % dist)
        return (None, '最近的那件对不上可交互物（key 失配）')

    # ==================================================================
    #  附身（POSSESSION，第82轮 R5）—— Z 键把操控权从灵魂切到某个角色
    # ==================================================================
    # 用户口径（第76轮需求锁定原话，逐字）
    #   「交互键用Z（对 kris 和 firsk，niko 用可以在征求他们同意的情况下附身
    #     （特效用原作的），也就是达到原作操控的功能）」
    #
    # ★★★ 原作依据（第82轮 UTMT 反编译取证，物证 `第82轮-灵魂附身R5/_evidence/`）
    # ------------------------------------------------------------------
    # | 事实 | 出处（逐字） |
    # |---|---|
    # | 确认键 Z ⇄ `control_check_pressed(0)` | `obj_mainchara_Step_0` |
    # | 交互出口 = `event_user(0)` | 同上（= `obj_mainchara_Other_12`） |
    # | 交互做的事 | `obj_mainchara_Other_12`：`if (global.interact==0 && global.flag[17]==0)
    #   { snd_play(snd_squeak); global.interact=5; global.menuno=0; control_clear(2); }` |
    # | 主角移动 = `obj_time.*` 布尔 × **3 px/帧** | `obj_mainchara_Step_0` |
    # | 灵魂移动 = **同一组** `obj_time.*` 布尔 × `global.sp` | `obj_heart_Step_0` |
    # ⇒ **原作里"操控谁"是同一套输入（`obj_time` 四个布尔）指向不同实体**，
    #   区别只在速度。所以"附身"在本项目里的正确形状 = **换方向键的消费方**，
    #   **不是新造一套附身物理**（没有加速度、没有跟随、没有光效）。
    #
    # ★ 与原作**不同的两处**（必须记住，不许冒充原作）
    # ------------------------------------------------
    # 1. **"征求同意"是本项目扩展**：原作只有 Kris 一人可操控，不存在"问对方能不能附身"。
    #    用户口径把它加进来 ⇒ `possession.ConsentState` 显式建模（三态：未决/同意/拒绝）。
    # 2. **特效只用原作已有的**：用户说"特效用原作的" ⇒ 只有 `snd_squeak` 音效
    #    + 灵魂收起/角色接管这两个**原作里真实发生过的**表现，
    #    **不新造**原作没有的粒子/闪光/拖影。
    # ==================================================================

    #: 附身总开关（与 `SOUL_ENABLED` / `GHOST_ENABLED` 同形）。
    #: `False` ⇒ `init_possession()` 建完空壳就返回，Z 键退化成"什么都没发生"。
    #: ⚠️ 保留它本身**不是死代码**：这是"附身出问题"时的一刀定位开关。
    POSSESSION_ENABLED = True

    def init_possession(self):
        """建附身状态机 + 收集可附身目标。

        失败语义与灵魂 / 幽灵同规：**只降级、不抛出**（附身坏了桌宠照常跑），
        且 `self.possession is None` 时 Z 键入口直接返回，不会半死不活。
        """
        # 先全部预声明成 None/空 —— 中途任何一步失败，宿主也不缺属性
        # （本项目踩过"状态只在成功路径上创建"的坑：失败后别处 getattr 就炸）。
        self.possession = None
        self._possession_targets = {}

        if not getattr(self, 'POSSESSION_ENABLED', True):
            _log.info('附身总开关 POSSESSION_ENABLED=False ⇒ 不建附身（用它定位问题）')
            return

        try:
            self.possession = possession_mod.PossessionState()
            # ★ 第85轮 I2：把**当前场景的明暗世界**喂给附身状态机（决定基准速度 3 / 4）。
            #   判不出来 ⇒ None ⇒ `drive` 回落到 `HERO_SPEED_PX`（第82轮行为，不猜）。
            self._possession_sync_world()
            # 从 NPC 登记表收集可附身目标（谁能附身只有 `POSSESSION_KINDS` 一处定义）。
            # ★ 登记表在真机里是 `npc_system.NpcRegistry` **对象**（不是 dict/list）——
            #   `build_targets` 已按 duck typing 吃 `.all()`，这里只负责拿到它。
            #   取不到 ⇒ 传 None ⇒ 空表（Z 键会如实报"没有可附身目标"，不会假成功）。
            reg = getattr(self, 'npc_registry', None)
            targets = possession_mod.build_targets(reg, scene_of=self._npc_scene_of)
            self._possession_targets = {t.npc_id: t for t in targets}
            _log.info('附身就绪：可附身目标 %d 个（%s）；%s',
                      len(self._possession_targets),
                      '、'.join(sorted(self._possession_targets)) or '无',
                      self.possession.describe())
        except Exception:
            _log.exception('附身初始化失败（附身功能不可用，宠物照常运行）')
            self.possession = None
            return

    def _possession_sync_world(self):
        """★ 第85轮 I2：把当前场景的明/暗世界同步给附身状态机。

        速度表要的那个"世界"从**唯一一处**取：`scene_system.world_of_scene()`
        （与道具系统 `main.py` 4154 行、场景渲染同一来源）。**不在这里另算一份**
        —— "同一份规则两处算"是本项目最贵的坑。

        取不到（场景系统未就绪 / 该场景世界未判定）⇒ 传 `None` ⇒ 状态机把速度
        回落到 `HERO_SPEED_PX`（第82轮既有行为）。**不猜成光世界**。
        """
        poss = getattr(self, 'possession', None)
        if poss is None:
            return None
        try:
            scene = self.__dict__.get('current_scene')
            world = scene_system_mod.world_of_scene(scene) if scene else None
            return poss.set_world(world)
        except Exception as e:
            _log.debug('附身世界同步失败（速度回落常量）: %s', e)
            return None

    def _npc_scene_of(self, npc_id):
        """某个 NPC 当前在哪（供"附身要求同场景"校验）。

        ★ 复用既有的 `_npc_scene_roster` 逻辑（层2 驻留覆盖优先、回落 `book.scene_of`）——
          不另写一套"当前在哪"，否则两处对"他在不在这个场景"的理解会分叉
          （本项目"同一份规则两处算"是最贵的坑）。
        取不到 ⇒ 返回 `None`（= 不校验，**不拿未知当"不同"**）。
        """
        try:
            roster = self._npc_scene_roster()
            if isinstance(roster, dict):
                for sid, ids in roster.items():
                    if npc_id in (ids or ()):
                        return sid
            return None
        except Exception:
            return None

    def _possession_target_at(self):
        """选一个"当前可附身的目标"（本场景的、离灵魂最近的）。

        判定序（**顺序即优先级**）：
          1. 没有附身系统 / 没有目标 ⇒ `(None, 原因)`；
          2. **只取与当前场景一致**的目标（scene 为 None 的也纳入，见 `request` 注释）；
          3. 多个 ⇒ 按灵魂位置取最近（复用 `soul_entity.pick_nearest`，与 E 键同一套）。
        """
        poss = getattr(self, 'possession', None)
        if poss is None:
            return (None, '附身系统未就绪')
        targets = list((self.__dict__.get('_possession_targets') or {}).values())
        if not targets:
            return (None, '登记表里没有可附身目标')
        cur = self.__dict__.get('current_scene')
        cands = [t for t in targets
                 if t.scene is None or cur is None or t.scene == cur]
        if not cands:
            return (None, '当前场景没有可附身角色（他们在别处）')
        # 按灵魂位置取最近（灵魂不可见 / 无坐标 ⇒ 退回第一个，并如实说明）。
        soul = getattr(self, 'soul', None)
        if soul is not None and self._soul_visible():
            try:
                pt = soul_entity_mod.screen_to_room(
                    soul.state.center()[0], soul.state.center()[1],
                    self._soul_room_rect(), self._virtual_screen_size())
            except Exception:
                pt = None
            if pt is not None:
                # 用目标所在场景的 marker 位置不好拿 ⇒ 退回"按 npc_id 顺序"，
                # ★ 因为本地图没有"NPC 在房间里的坐标"这个量（真有的话该走
                #   `npc_placement`），这里**如实退回**并说明，不伪造距离。
                key, dist = soul_entity_mod.pick_nearest(
                    pt, [(t.npc_id, 0.0, 0.0) for t in cands])
                if key is not None:
                    for t in cands:
                        if t.npc_id == key:
                            return (t, '按登记顺序选第一件（NPC 房间坐标未纳入比较）')
        return (cands[0], '按登记顺序选第一件')

    def toggle_possession(self):
        """★ R5 的主入口（Z 键）：附身 / 解除。

        返回 True 表示"这次按 Z 确实做了件事"（附身成功 / 发起征求 / 解除），
        False 表示"什么都没发生"（没有目标 / 被拒 / 系统未就绪）。

        ★ 为什么"再按一次 Z 解除"而不是"另一个键解除"：用户口径是"交互键用 Z"，
          而解除附身就是同一个交互的逆操作 —— 原作用 `control_check_pressed(0)`
          既做交互也做取消（`global.interact` 那一套），所以一个键两态是**原作形状**。
        """
        poss = getattr(self, 'possession', None)
        if poss is None:
            _log.info('附身请求被忽略：附身系统未就绪（POSSESSION_ENABLED=%s）',
                      getattr(self, 'POSSESSION_ENABLED', None))
            return False
        try:
            # ★★ 第85轮 I5：确认键输入的**缓冲窗口**（原作 `onebuffer = 5`）。
            #   对话刚结束的 5 帧内，确认键**不生效**（防"阅读没完就误触下一段"）。
            #   ⚠️ 只在**发起**时判；**解除附身不吃缓冲**（解除是"安全方向"的动作，
            #     原作的缓冲是防误触**新交互**，不是防脱离）。
            if not poss.is_possessing and not poss.is_asking:
                if not poss.accept_confirm():
                    _log.info('交互键被输入缓冲吞掉（剩余 %d 帧）', poss.confirm_buffer())
                    return False
            # 已在附身 / 正在征求 ⇒ 这一下 Z = 解除 / 取消。
            if poss.is_possessing or poss.is_asking:
                was = poss.describe()
                poss.stop('再按 Z 解除')
                self._possession_sync_soul_visibility()
                _log.info('附身解除（%s）', was)
                return True
            target, why = self._possession_target_at()
            if target is None:
                _log.info('附身：没有可附身目标（%s）', why)
                return False
            scene = self.__dict__.get('current_scene')
            mode = poss.request(target, scene=scene)
            if mode == possession_mod.MODE_ASKING:
                self._possession_ask_consent(target)
                return True
            if mode == possession_mod.MODE_POSSESSED:
                self._possession_on_begin(target)
                return True
            _log.info('附身未成立：%s（%s）', poss.describe(), why)
            return False
        except Exception:
            _log.exception('附身切换异常（已忽略，宠物照常运行）')
            return False

    def _possession_on_begin(self, target):
        """附身成立 ⇒ 收起灵魂（**操控权已转移**）+ 原作 `snd_squeak` 音效 + `control_clear(2)`。"""
        try:
            # ★ 第83轮 R6 互斥（对偶裁决）：附身接管 ⇒ 先解除带路。
            #   两处裁决必须成对（`toggle_escort` 里是"带路接管先解除附身"），
            #   否则会出现"角色既被附身又在带路" = 同一帧两处写坐标。
            esc = getattr(self, 'escort', None)
            if esc is not None and esc.active:
                was = esc.describe()
                esc.stop('被附身接管')
                _log.info('附身接管：先解除带路（%s）', was)
            # ★★ 原作 `control_clear(2)`（第84轮取证补齐）：
            #   `obj_mainchara_Other_12`：`snd_play(snd_squeak); global.interact=5;
            #                              global.menuno=0; control_clear(2);`
            #   —— 附身那一下要**清掉所有已按下的旧键**，否则"按住方向键时按 Z"
            #      会把灵魂残留的按键直接喂给刚接管的角色 ⇒ 角色自己跑起来。
            #   ★ 与 `PossessionState._begin()` 里的 `self._pressed.clear()` **不是同一件事**：
            #     那边清的是"归属新主人的那份账"，这边清的是**旧主人（灵魂）**的账。
            #     两处都必要（少一处就漏一边），但**不许把两处合并**（合并后一侧恒空）。
            # ⚠️ API 事实（第84轮实测钉死，别再凭印象写）：
            #   `self.soul` 的类型是 **`SoulOverlay`**，它的方法表里
            #   **没有 `clear_keys`**，只有 **`release_all()`**（内部转调 `self.state.clear_keys()`）。
            #   ⇒ 这里**必须**用 `soul.release_all()`；写成 `soul.clear_keys()` 会
            #     AttributeError 被下面的 except 吞掉 ⇒ 「补了 control_clear(2)」**其实没补**。
            #   （初版正是这么写错的，已由 check84 D 段 AST 判据钉住。）
            soul = getattr(self, 'soul', None)
            if soul is not None:
                try:
                    soul.release_all()
                except Exception:
                    _log.debug('附身时清灵魂按键失败（忽略）')
            # ★ 灵魂收起而不是隐藏控件：附身期间方向键归角色，灵魂留着会"两边都在动"。
            #   解除时 `_possession_sync_soul_visibility()` 会把它叫回来。
            self.hide_soul()
            # ★ 特效只用原作已有的：`obj_mainchara_Other_12` 里交互成功播 `snd_squeak`。
            self._possession_play_squeak()
            _log.info('附身成立：%s', target)
        except Exception:
            _log.exception('附身成立后的收尾失败（忽略）')

    def _possession_ask_consent(self, target):
        """对需要同意的角色发起"征求同意"——走**既有的对话通道**。

        ★ 第84轮口径「所有人附身都要经过同意」⇒ **本方法现在是附身的常规路径**
          （不再是 Niko 专用分支）；台词取 `target.name`，不写死名字。

        ★ 为什么走对话气泡而不自造一个弹窗：本项目"说话"只有一条出口
          （`dialogue_ui.add_dialogue`），另开一条迟早分叉（同 `_item_menu_message`）。
        ★ 为什么这也算"特效照原作"：原作里交互的**唯一可见反馈**就是
          `snd_squeak` + 文字/对话，这里照此办理。
        """
        try:
            name = target.name
            self._item_menu_message(
                '* 我（雷尔赛）看向 %s：「……可以让我来一下吗？」' % name)
            self._possession_play_squeak()
        except Exception:
            _log.exception('征求同意提示失败（忽略）')

    def _possession_play_squeak(self):
        """播原作的 `snd_squeak`（交互成功音）。找不到素材 ⇒ 静默跳过（**不假报**）。

        ★ 为什么单独抽一个方法：音效系统（`sound_manager`）的播放接口在本项目里
          有多条路径，抽出来便于回归锁只断言"它被调了"，不绑死某一条播放实现。
        """
        try:
            sm = getattr(self, 'sound_manager', None)
            if sm is None:
                return False
            for meth in ('play_sfx', 'play_sound', 'play_effect'):
                fn = getattr(sm, meth, None)
                if callable(fn):
                    try:
                        fn('snd_squeak')
                        return True
                    except Exception:
                        continue
            return False
        except Exception as e:
            _log.debug('snd_squeak 播放失败（忽略）: %s', e)
            return False

    def _possession_sync_soul_visibility(self):
        """按附身状态同步灵魂可见性（解除附身 ⇒ 把灵魂叫回来）。"""
        try:
            poss = getattr(self, 'possession', None)
            if poss is None:
                return
            if not poss.is_possessing and not poss.is_asking:
                # 解除后把灵魂放回当前场景位置（若之前是显示的）。
                soul = getattr(self, 'soul', None)
                if soul is not None and not soul.isVisible():
                    self.show_soul()
        except Exception:
            _log.exception('灵魂可见性同步失败（忽略）')

    def _possession_tick(self, dt):
        """每帧推进附身（挂在 `update_movement` 的 30ms 节拍上，与灵魂同源）。"""
        poss = getattr(self, 'possession', None)
        if poss is None:
            return False
        try:
            if not poss.is_possessing:
                return False
            # ★★ 第85轮 I4：**派发全局闸**（原作 `global.interact`）。
            #   整段移动代码在原作里裹在 `if (global.interact == 0)` 里 ⇒ 闸非 0 时
            #   被附身角色**整帧不动**。这里每帧刷新一次（闸是"当前状态"不是"事件"）。
            #   ⚠️ 取值只映射本项目**真实存在**的两种"锁输入"情形，不编档位：
            #      · 菜单打开 ⇒ `INTERACT_MENU`（原作菜单键分支就是 `global.interact = 5`）；
            #      · 否则     ⇒ `INTERACT_FREE`（对话中走 `onebuffer` 那条 I5 路径，
            #                    本项目没有"对话锁定主角"这一步 —— 它只在 Z 交互那一刻）。
            poss.set_interact(self._interact_level())
            moved = poss.drive(dt)
            # 钳进当前房间（没有房间几何 ⇒ 不钳，**不猜边界**）。
            rect = self._soul_room_rect()
            if rect is not None:
                poss.clamp_to(rect)
            return moved != (0.0, 0.0)
        except Exception as e:
            _log.debug('附身推进异常（本帧跳过）: %s', e)
            return False

    def _interact_level(self):
        """★ 第85轮 I4：当前 `global.interact` 等价档位（**唯一一处算**）。

        只映射本项目**真实存在**的两种"锁输入"情形：

        | 情形 | 返回值 | 原作出处 |
        |---|---|---|
        | `S` 菜单打开 | `INTERACT_MENU`(5) | `obj_mainchara_Step_0` 菜单键分支 `global.interact = 5;` |
        | 常态 | `INTERACT_FREE`(0) | 同上，`if (global.interact == 0)` 的"开"档 |

        ⚠️ **诚实标注**：原作还有一个 `1`（对话中，`obj_interactablesolid_Other_10`），
          但本项目**没有"对话期间锁住主角整段移动"这一步**（对话是气泡，不接管方向键），
          所以**不编这一档** —— 编了就是"看着做了，其实没对应物"。
          "对话刚结束的 5 帧不吃确认键"那条另有实现（I5，`onebuffer`）。
        """
        try:
            ui = getattr(self, 'item_menu_ui', None)
            if ui is not None and ui.is_open():
                return possession_mod.INTERACT_MENU
        except Exception:
            pass
        return possession_mod.INTERACT_FREE

    # ==================================================================
    #  剧情进度标记（PLOT MARK，第85轮 I10）—— **只记录，不销毁**
    # ==================================================================
    # ★★★ 用户口径（第85轮，逐字）：「**别毁，就是已经过完剧情了就好**」
    #
    # 原作依据（第85轮 UTMT 反编译 Deltarune ch1，逐字）：
    #   `obj_npc_susiedark_Create_0`：`if (global.plot >= 30) { instance_destroy(); }`
    #   —— 那是**出场门控**（剧情过了某点 ⇒ 该 NPC 不再生成），**不是删存档**。
    # ⇒ 本项目**照用户口径收窄**：只落一个"已过完剧情"的标记，
    #   **不做**任何 `instance_destroy` 等价物、不删 NPC / 道具 / 存档、**不门控**。
    # ★★★ 第86轮用户裁定：「**那就别判定死亡，就全部放行就好**」⇒ **没有**出场门控。
    #   标记先只落盘，能不能读、要不要用，等用户看过再裁（见报告"待裁定"）。

    #: 剧情标记总开关（与 `POSSESSION_ENABLED` / `ESCORT_ENABLED` 同形）。
    PLOT_MARK_ENABLED = True

    def init_plot_mark(self):
        """建剧情标记表（**只读 + 只写一个 True**，永不销毁任何东西）。

        失败语义与其它子系统同规：**只降级、不抛出**（标记坏了桌宠照常跑）。
        """
        self._plot_marks = {}
        if not getattr(self, 'PLOT_MARK_ENABLED', True):
            _log.info('剧情标记总开关 PLOT_MARK_ENABLED=False ⇒ 不记标记')
            return
        try:
            # ★ 复用 `data_store`（第35轮起"数据只走一个入口"的硬规矩）读持久化的标记。
            store = getattr(self, 'data_store', None)
            if store is not None and hasattr(store, 'get'):
                self._plot_marks = plot_mark_mod.load_dict(
                    store.get('plot_marks'))[0]
            _log.info('剧情标记就绪：已记录 %d 条（%s）',
                      len(self._plot_marks),
                      '、'.join(plot_mark_mod.done_keys(self._plot_marks)) or '无')
        except Exception:
            _log.exception('剧情标记初始化失败（标记功能不可用，宠物照常运行）')
            self._plot_marks = {}

    def mark_plot_done(self, what, note=None):
        """★ **只记录**"`what` 已过完"（用户口径「别毁，就是已经过完剧情了就好」）。

        本方法**只做两件事**：① 在内存表里写一个 `True`；② 尝试落盘。
        **没有任何"销毁"分支** —— 这是刻意的（原作那句 `instance_destroy()` 在本项目
        **被用户口径明确否决**，见模块头）。

        :return: 是否**新增**了一条（重复标记返回 False，但表状态不变）。
        """
        try:
            before = len(self._plot_marks or {})
            self._plot_marks = plot_mark_mod.mark_done(
                self._plot_marks or {}, what, note=note)
            added = len(self._plot_marks) > before
            if added:
                self._plot_marks_save()
                _log.info('剧情标记：已过完「%s」%s', what,
                          '（%s）' % note if note else '')
            return added
        except Exception:
            _log.exception('剧情标记写入失败（忽略，不影响其它功能）')
            return False

    def is_plot_done(self, what):
        """`what` 是否已过完（**只读**）。"""
        try:
            return plot_mark_mod.is_done(self._plot_marks or {}, what)
        except Exception:
            return False

    def _plot_marks_save(self):
        """把标记表落盘（走 `data_store` 唯一入口；失败**只记日志**，不抛出）。"""
        try:
            store = getattr(self, 'data_store', None)
            if store is not None and hasattr(store, 'set'):
                store.set('plot_marks', plot_mark_mod.as_dict(self._plot_marks))
            else:
                _log.debug('剧情标记：无 data_store ⇒ 仅存内存')
        except Exception:
            _log.exception('剧情标记落盘失败（保留内存态）')

    # ==================================================================
    #  带路（ESCORT，第83轮 R6）—— G 键请求某个角色带着灵魂走
    # ==================================================================
    # 用户口径（第76轮需求锁定原话，逐字）：「R6 可请求角色带灵魂走」。
    # ★ 本轮两条用户裁定（2026-10-03，逐字）：
    #   「**新增 G 键**」（与 Z=R5 附身完全分开）＋「**完全照原作（直接置位）**」。
    # ★★ 原作依据 / 诚实标注（见 `modules/escort.py` 模块头）：
    #   机制照抄毛毛虫（`obj_caterpillarchara` 的 25 帧历史 + `target = 12+slot*12`），
    #   ⚠️ 但**方向与原作相反**（原作主角带路队友跟随；R6 角色带路灵魂跟随），
    #   且原作**没有"灵魂"这个可被带领的实体** ⇒ R6 整体是**本项目扩展**。
    # ⚠️ 与 R5 **互斥**：见 `toggle_escort` 与 `_possession_on_begin` 的对偶裁决。

    #: 带路总开关（与 `POSSESSION_ENABLED` / `SOUL_ENABLED` 同形）。
    #: `False` ⇒ `init_escort()` 建完空壳就返回，G 键退化成"什么都没发生"。
    #: ⚠️ 保留它本身**不是死代码**：这是"带路出问题"时的一刀定位开关。
    ESCORT_ENABLED = True

    def init_escort(self):
        """建带路状态机 + 复用 R5 的同意表。

        失败语义与灵魂 / 幽灵 / 附身同规：**只降级、不抛出**（带路坏了桌宠照常跑），
        且 `self.escort is None` 时 G 键入口直接返回，不会半死不活。
        """
        self.escort = None
        self._escort_targets = {}
        if not getattr(self, 'ESCORT_ENABLED', True):
            _log.info('带路总开关 ESCORT_ENABLED=False ⇒ 不带路（用它定位问题）')
            return
        try:
            # ★★ 复用 R5 的同意表（**同一份**，不另建 —— "同一份规则两处算"是最贵的坑）。
            #   `possession` 已在 `init_possession()` 里建好；顺序保证见 init_npc_systems。
            poss = getattr(self, 'possession', None)
            consent = getattr(poss, 'consent', None) if poss is not None else None
            self.escort = escort_mod.EscortState(leader_id=None, consent=consent)
            self._escort_targets = dict(getattr(self, '_possession_targets', None) or {})
            _log.info('带路就绪：可请求带路目标 %d 个（%s）；同意表%s',
                      len(self._escort_targets),
                      '、'.join(sorted(self._escort_targets)) or '无',
                      '复用 R5' if consent is not None else '独立兜底')
        except Exception:
            _log.exception('带路初始化失败（带路功能不可用，宠物照常运行）')
            self.escort = None

    def _escort_target_at(self):
        """选一个"当前可请求带路的目标"（本场景的）。

        ★ 复用 R5 的同一套选择逻辑（`_possession_target_at` 的候选集）——
          不另写一份"谁在场"，否则两处对"他在不在这个场景"的理解会分叉。
          与 R5 的唯一区别：R5 会为"取最近"做灵魂位置比较，这里**如实退回登记顺序**
          （NPC 房间坐标未纳入比较，同 R5 的说明）。
        """
        esc = getattr(self, 'escort', None)
        if esc is None:
            return (None, '带路系统未就绪')
        targets = list((self.__dict__.get('_escort_targets') or {}).values())
        if not targets:
            return (None, '登记表里没有可带路目标')
        cur = self.__dict__.get('current_scene')
        cands = [t for t in targets
                 if getattr(t, 'scene', None) is None or cur is None
                 or t.scene == cur]
        if not cands:
            return (None, '当前场景没有可带路角色（他们在别处）')
        return (cands[0], '按登记顺序选第一件（NPC 房间坐标未纳入比较）')

    def toggle_escort(self):
        """★ R6 的主入口（G 键）：请求带路 / 结束带路。

        返回 True 表示"这次按 G 确实做了件事"（发起请求 / 开始带路 / 结束），
        False 表示"什么都没发生"（没有目标 / 被拒 / 系统未就绪）。

        ★★ 与 R5 的**互斥裁决**（写在入口，一处即可）：
          · 若正在**附身**中 ⇒ 先 `stop` 附身（附身时角色归用户操控，
            "同一个角色既被操控又带路"是同帧两处写坐标的经典事故）；
          · 再按 G ⇒ 结束带路。
        """
        esc = getattr(self, 'escort', None)
        if esc is None:
            _log.info('带路请求被忽略：带路系统未就绪（ESCORT_ENABLED=%s）',
                      getattr(self, 'ESCORT_ENABLED', None))
            return False
        try:
            # ---- 互斥：附身优先被解除（G 是"要用带路"，所以让位的是附身）----
            poss = getattr(self, 'possession', None)
            if poss is not None and (poss.is_possessing or poss.is_asking):
                was = poss.describe()
                poss.stop('被带路请求接管')
                self._possession_sync_soul_visibility()
                _log.info('带路接管：先解除附身（%s）', was)

            # ---- 已在带路/征求 ⇒ 这一下 G = 结束 / 取消 ----
            if esc.active:
                was = esc.describe()
                esc.stop('再按 G 结束')
                _log.info('带路结束（%s）', was)
                return True

            target, why = self._escort_target_at()
            if target is None:
                _log.info('带路：没有可请求目标（%s）', why)
                return False
            # 带路者必须与灵魂同场景（复用 R5 的场景来源，不另算）。
            scene = self.__dict__.get('current_scene')
            leader_scene = self._npc_scene_of(target.npc_id)
            # ★ 分类从 R5 的**唯一真源**取（`POSSESSION_KINDS`），不另建表。
            kind = possession_mod.kind_of(target.npc_id)
            if kind == possession_mod.KIND_FORBIDDEN:
                _log.info('带路：%s 不可带路', target.npc_id)
                return False
            mode = esc.request(target.npc_id, kind=kind, scene=scene,
                               leader_scene=leader_scene)
            if mode == escort_mod.ESCORT_ASKING:
                self._escort_ask_consent(target)
                return True
            if mode == escort_mod.ESCORT_LEADING:
                self._escort_on_begin(target)
                return True
            _log.info('带路未成立：%s（%s）', esc.describe(), why)
            return False
        except Exception:
            _log.exception('带路切换异常（已忽略，宠物照常运行）')
            return False

    def _escort_on_begin(self, target):
        """带路成立 ⇒ 把轨迹初值设成"带路者当前位置"，并让灵魂可见。"""
        try:
            soul = getattr(self, 'soul', None)
            if soul is not None and not self._soul_visible():
                self.show_soul()
            # ★ 轨迹初值 = 带路者当前位置（照抄原作 `remx[i]` 的初值）
            #   ⇒ 必须**填满**而不是清空，否则前 12 帧灵魂会被从 (0,0) 拽过来。
            #   带路者房间坐标本项目没有 ⇒ 用**灵魂当前房间坐标**做初值
            #   （等价于"带路者就站在灵魂这里"），并如实说明：轨迹会随
            #   带路者真实位置逐帧覆盖，初值只影响最前面的 lag 帧。
            x, y = self._escort_leader_seed_xy()
            esc = self.escort
            esc.reset_trace(x, y)
            self._escort_play_squeak()
            _log.info('带路成立：%s（轨迹初值 %.1f,%.1f）', target, x, y)
        except Exception:
            _log.exception('带路成立后的收尾失败（忽略）')

    def _escort_leader_seed_xy(self):
        """带路者轨迹的初值坐标（逻辑房间坐标）。

        ★ 优先用**灵魂当前所在**的房间坐标：本项目没有"NPC 在房间里的坐标"
          这个量（同 R5 的如实说明）⇒ 用灵魂位置当"带路者此刻就在你旁边"，
          是最不撒谎的初值。取不到 ⇒ `(0.0, 0.0)`，并让调用方照常填满
          （填满保证不会穿屏；(0,0) 顶多让头 12 帧的灵魂位置不准，随后被真值覆盖）。
        """
        try:
            soul = getattr(self, 'soul', None)
            if soul is not None:
                pt = soul_entity_mod.screen_to_room(
                    soul.state.center()[0], soul.state.center()[1],
                    self._soul_room_rect(), self._virtual_screen_size())
                if pt is not None:
                    return (float(pt[0]), float(pt[1]))
        except Exception:
            pass
        return (0.0, 0.0)

    def _escort_ask_consent(self, target):
        """对需要同意的角色发起"征求同意"——走**既有的对话通道**。

        ★ 与 R5 的自造弹窗纪律一致：本项目"说话"只有一条出口
          （`dialogue_ui.add_dialogue` 的薄封装 `_item_menu_message`），
          另开一条迟早分叉。
        """
        try:
            self._item_menu_message(
                '* 我（雷尔赛）看向 %s：「……可以带我一起去吗？」' % target.name)
            self._escort_play_squeak()
        except Exception:
            _log.exception('带路征求同意提示失败（忽略）')

    def _escort_play_squeak(self):
        """播原作的 `snd_squeak`（交互成功音）。找不到素材 ⇒ 静默跳过（**不假报**）。

        ★ 与 R5 同款：抽成独立方法，回归锁只断言"它被调了"，
          不绑死某一条播放实现。
        """
        try:
            sm = getattr(self, 'sound_manager', None)
            if sm is None:
                return False
            for meth in ('play_sfx', 'play_sound', 'play_effect'):
                fn = getattr(sm, meth, None)
                if callable(fn):
                    try:
                        fn('snd_squeak')
                        return True
                    except Exception:
                        continue
            return False
        except Exception as e:
            _log.debug('snd_squeak 播放失败（忽略）: %s', e)
            return False

    def _escort_tick(self, dt):
        """每帧推进带路（挂在 `update_movement` 的 30ms 节拍上，与灵魂同源）。

        返回 True 表示本帧**灵魂位置被带路改变**。

        ★ 用户裁定「完全照原作（直接置位）」⇒ 这里就是直接置位：
          灵魂位置 = 带路者轨迹里「滞后 12 帧」那一点（`escort.step`）。
        ⚠️ 带路者位置的**真值来源**：本项目没有"NPC 的房间坐标"这个量
          （同 R5 如实说明）⇒ 本帧的带路者位置取**灵魂当前位置**再做一步
          位移（即：灵魂跟着"自己上一帧的位置"走，等于**原地不动**）。
          这显然不是"带路"。
          ⇒ 因此本 tick **只做"如果调用方喂了带路者位置，就推进"**，
            带路者位置的注入留给 P3（`npc_roam` 有 NPC 位置时）。
            **本轮如实登记：带路位置源未接线**，见 `WIRING` 与报告。
        """
        esc = getattr(self, 'escort', None)
        if esc is None:
            return False
        try:
            if not esc.needs_step():
                return False
            # ★ 带路者位置：优先问 NPC 生活层要（若它在位），否则如实返回 None
            #   （即本轮不推进）—— **不拿灵魂位置冒充带路者**（那会变成原地打转）。
            lx, ly = self._escort_leader_xy(esc.leader_id)
            if lx is None:
                return False
            pt = esc.step(lx, ly)
            if pt is None:
                return False
            self._escort_apply_soul_xy(pt[0], pt[1])
            return True
        except Exception as e:
            _log.debug('带路推进异常（本帧跳过）: %s', e)
            return False

    #: ★★ 诚实登记：带路者位置的来源在**本轮未接线**（见报告 §遗留）。
    #:    结构：`{'wired': bool, 'source': str, 'not_yet': [说明...]}`
    #: 为什么要有这个字典：本项目纪律 —— "函数写对了 ≠ 产品用上了"，
    #: 而"未接线"必须能被一眼看到，不能靠读代码猜。
    ESCORT_WIRING = {
        'wired': False,
        'source': 'npc_roam/npc_placement（NPC 房间坐标）',
        'not_yet': [
            '带路者房间坐标：本项目当前没有"N PC 在房间里的坐标"这个量',
            'npc_roam 有场景级位置但未暴露逐帧房间坐标',
            '⇒ G 键可发起/结束带路、状态机与轨迹采样已就绪，但位置源待 P3 接入',
        ],
    }

    def _escort_leader_xy(self, leader_id):
        """问 NPC 生活层要带路者的**房间坐标**。拿不到 ⇒ `(None, None)`（不猜）。

        ★ 与 `_npc_scene_of` 同一条纪律：**取不到就是取不到**，
          绝不用灵魂位置/屏幕坐标冒充（那会产生"灵魂原地打转"这种假带路）。
        """
        if not leader_id:
            return (None, None)
        try:
            provider = getattr(self, '_npc_room_xy_of', None)
            if callable(provider):
                xy = provider(leader_id)
                if isinstance(xy, (list, tuple)) and len(xy) == 2:
                    return (float(xy[0]), float(xy[1]))
        except Exception as e:
            _log.debug('取带路者坐标失败（%s）: %s', leader_id, e)
        return (None, None)

    def _escort_apply_soul_xy(self, x, y):
        """把灵魂搬到**逻辑房间坐标** `(x, y)`（**本轮唯一写灵魂位置的地方**）。

        ★ 灵魂的位置真值在 `soul.state.x/y`，且那对坐标是**屏幕坐标**
          （`SoulOverlay.apply_state_pos` 直接 `self.move(x, y)`）——
          所以这里必须先把房间坐标**逆映射**回屏幕坐标。
        ★ 逆映射与 `_screen_point_to_room_rect` **同口径**（同一套归一化，
          见 `_room_point_to_screen`）：两处各写一遍迟早分叉。
        """
        try:
            soul = getattr(self, 'soul', None)
            if soul is None:
                return False
            sp = self._room_point_to_screen(x, y)
            if sp is None:
                return False
            state = getattr(soul, 'state', None)
            if state is None:
                return False
            state.x, state.y = float(sp[0]), float(sp[1])
            # ★ 走既有的位置同步（灵魂位置的**唯一写窗口路径**）——
            #   不新造一条"直接 move"，否则就绕过了它的"位置没变就不动"优化。
            soul.apply_state_pos()
            return True
        except Exception as e:
            _log.debug('带路置位灵魂失败: %s', e)
            return False

    def _room_point_to_screen(self, rx, ry):
        """逻辑房间坐标 `(rx, ry)` → **屏幕坐标**（`_screen_point_to_room_rect` 的逆）。

        ★★ 为什么必须有它（而且必须放这儿）：第76轮把"屏幕→房间"的公式抽成了
        `_screen_point_to_room_rect` 作为单一真源，但**它没有逆映射**。
        R6 需要"把房间坐标写回屏幕"，若在外面另写一套换算 ⇒ 两套公式迟早分叉
        （本项目最贵的坑）。所以逆映射**紧贴正映射**，用同一组变量名与同一套
        夹取规则，可被 A/B 判据锚住（正→逆→正 应当回到原值）。

        口径与原公式对齐：
          正：`fx = clamp(cx / sw)`，`tcx = rl + rw * fx`，返回中心 = `tcx`
          逆：`fx = (rx - rl) / rw`，`cx = fx * sw`
        `room_rect` 为 `None` ⇒ 退回"屏幕坐标即房间坐标"（与正映射的退回分支对称）。
        """
        try:
            rx = float(rx)
            ry = float(ry)
        except (TypeError, ValueError):
            return None
        if not (math.isfinite(rx) and math.isfinite(ry)):
            return None
        room_rect = self._soul_room_rect()
        sw, sh = self._virtual_screen_size()
        if not room_rect or len(room_rect) != 4:
            return (rx, ry)
        rl, rt, rr, rb = (float(room_rect[0]), float(room_rect[1]),
                          float(room_rect[2]), float(room_rect[3]))
        rw = max(1.0, rr - rl)
        rh = max(1.0, rb - rt)
        fx = min(1.0, max(0.0, (rx - rl) / rw))
        fy = min(1.0, max(0.0, (ry - rt) / rh))
        return (fx * float(sw) if sw > 0 else 0.0,
                fy * float(sh) if sh > 0 else 0.0)

    # ==================================================================
    #  幽灵（GHOST，第67轮）—— 定点幽灵：走近才清晰，决心强才看得清
    # ==================================================================
    # 用户口径（第64轮原话，逐字）
    #   *「我把 chara 改了一下，就用红与黄.apk 里面的幽灵就好，
    #     只有决心强的人能看到幽灵（ralsei 是个特例）」
    # 第66轮补裁定
    #   N1「从上轮 N1 开始，用和 kris 等人接触的时间算吧」⇒ **决心 = 接触时长**
    #      （★ 用户改了口径：此前我建议的是"Ralsei↔用户信任度"，`relationship.py`
    #       里**没有"与 NPC 接触时长"这个量**，所以这条只能新建。）
    #   N2「N2 定点距离」                                ⇒ 照抄原作**定点距离式** alpha
    #   N3「`sprites/ghost/` 接线时机你来看就好」          ⇒ 我定：**本轮就接线**
    #
    # 为什么是"逐字照抄"而不是"看着差不多"
    # ----------------------------------
    # 距离式 alpha（`10/(dist+1)` 封顶 0.9）/ 上下浮动那四行 / 亮暗档 0.9·0.6
    # **全部有原文出处**（第64轮反编译物证 `_evidence/gml64/`）。`ghost_system` 的
    # docstring 里挂着"值 → 原文出处"对照表，回归锁 `check67` 的 D 段逐条回原文验。
    #
    # ★★ 与原作**方向相反**的一处，必须记住
    # --------------------------------
    # **两只**定点幽灵都带**"杀戮 / LV"方向**的销毁门槛：
    #   · Chara（`obj_ghostint2.Create_0`）：`obj_mainchara.kill == 1` ⇒ `instance_destroy()`
    #   · Clover（`obj_ghostint.Create_0`）：再加 `global.flag[7] == 1 || scr_murderlv() >= 12`
    # ⇒ 原作轴是「**杀过人 / LV 高 ⇒ 幽灵消失**」，而用户要的是「**决心强 ⇒ 看得见**」。
    # 两者方向相反 ⇒ 处置：**机制形状照抄、轴换成用户口径**，并在报告里如实
    # 标注为**本项目扩展**（记忆 §9：用户口径优先于我的技术判断）。
    # ⚠️ 首版这里曾写「Chara 的幽灵在 Create 里**没有任何门槛**」—— **那是假事实**
    #    （凭印象写的）。第67轮逐条回 `_evidence/gml64/` 原文时被自己的判据逮到并改正。
    # ==================================================================

    #: 幽灵总开关（与 `SOUL_ENABLED` / `NPC_ENABLED` / `SCENE_LAYER_ENABLED` 同形）。
    #: `False` ⇒ `init_ghost()` 建完空壳就返回，所有入口退化成"什么都没发生"。
    #: ⚠️ 保留它本身**不是死代码**：这是"幽灵出问题"时的一刀定位开关。
    GHOST_ENABLED = True

    #: 接触时长落盘文件（走 `data_store` 唯一存储入口，与 `RELATIONSHIP_FILE` 同规）。
    GHOST_FILE = 'ghost_state.json'

    #: 幽灵相对桌宠中心的**出生偏移**（屏幕像素）。
    #: ★ 为什么是 96 而不是 0：`dist < 100` 才会显形（照抄 `Step_1`），取 96 正好落在
    #:   "刚好看得见的边缘" —— 用户第一眼看到的就是那只**几乎透明的**幽灵，把宠物
    #:   拖近它会变亮、拖远会淡出，机制**一眼可见**（贴脸出生反而看不出"距离式"）。
    #: ⚠️ 只决定**出生**位置：定点模式下之后它**定点不动**（"定点"的定义见
    #:   `ghost_system`）；跟飘模式下只决定**第一帧之前**它待在哪。
    GHOST_SPAWN_OFFSET = (96.0, -6.0)

    #: ★★ 第74轮 B5：产品用**哪只幽灵**（取自原作的两只，机制不同）。
    #:   用户裁定原话（逐字）：「**B5 幽灵停走式 alpha | 接，按原作 | 照抄：
    #:   站住显形 / 走动淡出**」。
    #:   * `MODE_FIXED`  —— `obj_ghostint2`：**定点**，alpha 只认"到固定点的距离"；
    #:   * `MODE_FOLLOW` —— `obj_ghostbuds`：**跟飘**，贴着主角走，alpha 认"走没走"
    #:     （站住升到封顶、走动每帧 -0.05）。
    #:   ★ 为什么倾向 `MODE_FOLLOW`：桌宠是**会满地跑**的实体，而"定点幽灵"要用户
    #:     把宠物**拖到那个固定点旁边**才看得见 —— 机制在，但**看不见**。跟飘那只
    #:     贴在宠物身上，"站住显形 / 走动淡出"是**一眼可见**的行为，也更像原作的
    #:     城堡镇（Ralsei 走到哪，他们跟到哪）。
    #:   ⚠️ **定点通路一行未删**：`MODE_FIXED` 仍在 `ghost_system` 里被回归锁 B/C 段
    #:     整段守着（C41 还额外钉住"模块默认仍是 FIXED"）—— 想换回去只改这一行。
    GHOST_MODE = ghost_system_mod.MODE_FOLLOW

    #: 接触时长多久落一次盘（秒）。★ 别每帧写：那是 30 次/秒的小文件 IO。
    #: 另有退出兜底（`cleanup_on_exit`），所以 30s 丢不了多少。
    GHOST_SAVE_EVERY = 30.0

    def init_ghost(self):
        """建幽灵：素材 → 状态（含接触时钟）→ 独立顶层窗口 → 出生点。

        失败语义与灵魂 / 道具 / NPC 同规：**只降级、不抛出**（幽灵坏了桌宠照常跑），
        且 `self.ghost is None` 时 `_ghost_tick()` 直接返回、所有入口退化成
        "什么都没发生"，不会半死不活地"看得见窗口但不动"。
        """
        # 先全部预声明成 None/空 —— 中途任何一步失败，宿主也不缺属性
        # （本项目踩过"状态只在成功路径上创建"的坑：失败后别处 getattr 就炸）。
        self.ghost = None
        self.ghost_state = None
        self.ghost_contact = None
        self._ghost_path = None
        self._ghost_last_save = 0.0

        if not getattr(self, 'GHOST_ENABLED', True):
            _log.info('幽灵总开关 GHOST_ENABLED=False ⇒ 不建幽灵（用它定位问题）')
            return

        try:
            state = ghost_system_mod.GhostState(
                home_x=0.0, home_y=0.0, contact_seconds=0.0,
                # ★ 「Ralsei 是个特例」：**看的人就是 Ralsei 本人**（桌宠就是他）
                #   ⇒ 走"不靠决心也至少看得见暗档"那条通路。
                #   ⚠️ `ralsei_special=False` 那条路不是摆设：回归锁用它做**对照控制**
                #      （同输入、只翻这一个开关 ⇒ 输出必须不同），否则"特例"无法被测到。
                ralsei_special=ghost_system_mod.RALSEI_SPECIAL,
                # ★ B5：产品用哪只幽灵（定点距离式 / 跟飘停走式）由 `GHOST_MODE` 定。
                #   ⚠️ 这里**必须显式传**，不能靠模块默认 —— `ghost_system` 的默认是
                #      `MODE_FIXED`（为了不改动回归锁守着的定点通路），靠默认就等于
                #      "`GHOST_MODE` 这个常量是死的"（本项目最贵的坑）。
                mode=RalseiPet.GHOST_MODE)
            # ★ parent=None：与灵魂同一个决策 —— 幽灵站在**桌面**上，而宠物窗口只有
            #   ~42×82 屏幕像素，子控件会被裁剪，"定点站在桌面某处"根本无从表达。
            self.ghost = ghost_overlay_mod.GhostOverlay(
                None,
                sprites=ghost_overlay_mod.load_ghost_sprites(),
                state=state,
            )
            self.ghost_state = state
            self.ghost_contact = state.contact
            # ---- 接触时长：读回上次的累计（读不到就是 0，**不编造**）----
            self._ghost_path = self._ghost_state_path()
            self._ghost_load()
            # ★ 出生点：宠物中心 + `GHOST_SPAWN_OFFSET`，就在 96px 上
            #   （`alpha = 10/(96+1) ≈ 0.103`，刚好看得见的边缘）。
            #  ⚠️ 第67轮真机取证的一段弯路，记在这里免得后人再走一遍：
            #     外部用 Win32 `GetWindowRect` 量这个窗口时，若探针**不是 DPI-aware**，
            #     坐标会被**按缩放宽高比缩小**（本机 150% ⇒ ÷1.5）。曾因此把
            #     "窗口在 (2515,1393) 44×58"误读成"幽灵跑到了 (1677,927) 29×39"，
            #     进而误判"出生点差了 1000px ⇒ 幽灵永不显形"，白改了一版延迟定点。
            #     真相：**这笔账本来就算得对**（`幽灵帧` 诊断实测
            #     `距离=96.19 want=True vis=True`）。⇒ 量桌宠要先声明 DPI 感知。
            self._ghost_respawn()
            # ★ 开局**不** `show()`：`wants_show()` 由**距离**决定，出生点就在 96px 上
            #   （刚好看得见的边缘），第一帧 tick 之后自然会亮起来；
            #   在这里提前 show 只会在宠物还没定位时先闪一个空窗口。
            _log.info('幽灵就绪：%s', self.ghost_state.describe())
        except Exception:
            _log.exception('幽灵初始化失败（幽灵功能不可用，宠物照常运行）')
            self.ghost = None
            self.ghost_state = None
            self.ghost_contact = None

    # ---------------------------------------------------------------- 落盘
    def _ghost_state_path(self):
        """接触时长的落盘路径（`data_store` 唯一入口；取不到 ⇒ `None` = 退内存态）。

        ⚠️ 与 `_make_relationship()` 同一条纪律：**不在底层模块里 import data_store**
           （它会反向依赖 memory 层，构成初始化环 —— 本项目栽过 4 次），
           路径一律由**调用方注入**，这里只当那个调用方。
        """
        try:
            import data_store
            return data_store.app_file(RalseiPet.GHOST_FILE)
        except Exception as e:
            _log.debug('幽灵接触时长落盘路径不可用（退内存态）: %s', e)
            return None

    def _ghost_load(self):
        """把上次的接触时长读回来。读不到 / 文件损坏 ⇒ **保持现值**（不抛、不清零）。"""
        clock = getattr(self, 'ghost_contact', None)
        path = getattr(self, '_ghost_path', None)
        if clock is None or not path:
            return False
        try:
            import io
            import json
            import os
            if not os.path.isfile(path):
                return False
            with io.open(path, encoding='utf-8') as fh:
                d = json.load(fh)
            clock.load(d)
            _log.info('幽灵：接触时长已读回 %s', clock.describe())
            return True
        except Exception as e:
            _log.warning('幽灵接触时长读取失败（按 0 起算）: %s', e)
            return False

    def _ghost_save(self, force=False):
        """把接触时长写回盘。★ 由 `_ghost_tick()` 按 `GHOST_SAVE_EVERY` 节流调。

        **绝不因为"记不上时间"影响宠物运行** ⇒ 失败只记日志。
        """
        clock = getattr(self, 'ghost_contact', None)
        path = getattr(self, '_ghost_path', None)
        if clock is None or not path:
            return False
        now = time.time()
        last = getattr(self, '_ghost_last_save', 0.0)
        if not force and (now - last) < getattr(self, 'GHOST_SAVE_EVERY', 30.0):
            return False
        self._ghost_last_save = now
        try:
            return bool(clock.save_to(path))
        except Exception as e:
            _log.debug('幽灵接触时长落盘失败（已忽略）: %s', e)
            return False

    # ---------------------------------------------------------------- 出生点
    def _ghost_respawn(self):
        """把幽灵放到"宠物中心 + `GHOST_SPAWN_OFFSET`"；宠物位置不可用 ⇒ 屏幕中心。"""
        gh = getattr(self, 'ghost', None)
        st = getattr(self, 'ghost_state', None)
        if gh is None or st is None:
            return False
        try:
            cx = float(self.x()) + self.width() / 2.0
            cy = float(self.y()) + self.height() / 2.0
        except Exception:
            b = gh.screen_bounds() or (0.0, 0.0, 1920.0, 1080.0)
            cx = (b[0] + b[2]) / 2.0
            cy = (b[1] + b[3]) / 2.0
            _log.info('幽灵出生点退回屏幕中心（宠物窗口位置不可用）')
        try:
            dx, dy = RalseiPet.GHOST_SPAWN_OFFSET
            st.respawn(cx + dx, cy + dy)
            # ★ 钳制交给 `apply_state_pos()`：它按**虚拟屏并集**钳锚点（契约①），
            #   否则"出生点落在屏幕外 ⇒ 距离式永久为 0 ⇒ 用户以为功能坏了"。
            gh.apply_state_pos()
            _log.info('幽灵定点在 %s', st.describe())
            return True
        except Exception:
            _log.exception('幽灵出生点设置失败（忽略）')
            return False

    def ghost_respawn(self, x, y):
        """**外部**改定点位置（留给将来的"把幽灵搬到别处"/多只幽灵用）。

        ⚠️ 本轮**没有**任何热键 / 菜单调它 —— 它是"接口真的在位"的那部分
           （用户要求「留好拓展接口」），不是"写了就算接线"（本项目最贵的坑）。
        """
        st = getattr(self, 'ghost_state', None)
        if st is None:
            return False
        try:
            st.respawn(x, y)
            gh = getattr(self, 'ghost', None)
            if gh is not None:
                gh.apply_state_pos()
            return True
        except Exception:
            _log.exception('幽灵重新定点失败')
            return False

    # ---------------------------------------------------------------- 显示 / 藏起
    def ghost_visible(self):
        """幽灵窗口现在是不是**可见**（不是"该不该可见" —— 那个是 `wants_show`）。"""
        gh = getattr(self, 'ghost', None)
        try:
            return bool(gh is not None and gh.isVisible())
        except Exception:
            return False

    def show_ghost(self):
        """显示幽灵（外部入口）。**绝不置顶**（建楼契约建立在正常 z 序上）。"""
        gh = getattr(self, 'ghost', None)
        if gh is None:
            return False
        try:
            return bool(gh.show_ghost())
        except Exception:
            _log.exception('显示幽灵失败')
            return False

    def hide_ghost(self):
        gh = getattr(self, 'ghost', None)
        if gh is None:
            return False
        try:
            return bool(gh.hide_ghost())
        except Exception:
            _log.exception('藏起幽灵失败')
            return False

    # ---------------------------------------------------------------- 每帧推进
    def _ghost_contact_now(self):
        """当前**是否处于接触状态** —— 判据 = 「在场的人里有 Kris 等人」。

        ★ 数据源用 `self.npc_bodies`（`{npc_id: Body}`，**只在当前场景**）：
          它已经同时覆盖两种场景（房间 = 站位表居民、桌面 = 已跟随的人），
          而且它**已经过世界门控** —— 这里再自己算一遍"谁该在场"就会造出
          第二份真相（本项目最贵的坑）。
        ★ 拿不到 ⇒ `False`（**不接触**）。宁可少涨决心，也不凭空涨：
          "决心"是这条线唯一的输入，它按错的方向涨就是功能整条走歪。
        """
        try:
            bodies = getattr(self, 'npc_bodies', None)
            if not bodies:
                return False
            return bool(ghost_system_mod.contact_from_npcs(list(bodies.keys())))
        except Exception:
            return False

    def _ghost_moving_now(self):
        """★ B5：宠物这一帧**走没走** —— 跟飘幽灵（`obj_ghostbuds`）的唯一输入。

        ★ 为什么用 `getattr` 而不是 `self.is_moving`：这个属性**不在 `__init__`
          里预声明**（首次赋值散落在若干分支上，见 `randomize_movement_pattern`
          等）。极早期调用时直接取会 `AttributeError`，而它又在 `_ghost_tick`
          的 `try` 里 —— 一旦抛出，整帧幽灵推进都会被跳过、还只留一条 DEBUG。
          ⇒ 拿不到就按 `False`（**站住**）算：保守方向是"宁可让它显形"，
            因为"该亮的时候不亮"用户会以为功能坏了，"该淡的时候亮着"只是多看一眼。
        ★ 为什么不用"实际位移 > 阈值"来判：那会引入第二份真相 —— 项目里
          `is_moving` 已经是"宠物走没走"的既有答案（走 / 停 / 休息都由它表达），
          这里再自己算一次位移，两处早晚会不一致（本项目最贵的坑）。
        """
        try:
            return bool(getattr(self, 'is_moving', False))
        except Exception:
            return False

    def _ghost_tick(self, dt):
        """每帧推进幽灵（挂在 30ms 的 `update_movement` 上）。

        ★ 为什么挂在 `update_movement` 而**不自己开 QTimer**：与灵魂同一条理由 ——
          本项目已有一个 30ms 定时器（正好等于原作 `GMS2FPS = 30`，与
          `ghost_overlay.GHOST_TICK_MS = 33` 对齐）。再开一个只会多一条
          "两个节拍器互不同步"的隐患。
        ★ 调用点必须在 `update_movement` 的**所有早退分支之前**（睡眠 / 施法 /
          躲猫猫 / 拖拽保护 / 特殊动画都会 return）：幽灵是独立实体，
          宠物睡着 / 被拖走时它照样该按距离（定点）或按停走（跟飘）显淡。
        """
        gh = getattr(self, 'ghost', None)
        st = getattr(self, 'ghost_state', None)
        if gh is None or st is None:
            return False
        try:
            contact = self._ghost_contact_now()
            # ★ B5：「宠物走没走」= 跟飘模式（`obj_ghostbuds`）的**唯一输入**。
            #   ⚠️ 必须走 `getattr` 兜底：`is_moving` **不在 `__init__` 里预声明**
            #      （首次赋值出现在别处的分支上），直接 `self.is_moving` 在极早期
            #      调用时会 `AttributeError`。拿不到就按"站住"算（保守：宁可让它显形）。
            moving = self._ghost_moving_now()
            # 宠物**中心**坐标 —— 定点模式下距离式 alpha 是"中心到中心"、与锚点同一个点；
            # 跟飘模式下这就是"要贴到谁身上"。两处用的是**同一个点**（少一层心智负担）。
            try:
                px = float(self.x()) + self.width() / 2.0
                py = float(self.y()) + self.height() / 2.0
            except Exception:
                px = py = None
            gh.tick(dt, pet_x=px, pet_y=py, contact=contact, moving=moving)
            # ★ 窗口开 / 停由 `wants_show`（alpha 非零）决定：alpha 掉到 0 就该收掉，
            #   否则会在屏幕上留一个"看不见但吃焦点"的空窗口（幽灵不吃鼠标事件，
            #   所以危害小于灵魂，但白白多一个顶层窗口仍然是错的）。
            #   ⚠️ 两种模式下"alpha 掉到 0"的**原因不同**：定点 = 走远了，
            #   跟飘 = 一直在走。判据本身**不依赖原因**（这正是 `wants_show` 的价值）。
            want = bool(gh.wants_show())
            if want and not gh.isVisible():
                gh.show_ghost()
            elif not want and gh.isVisible():
                gh.hide_ghost()
            # 诊断（DEBUG 级，平时不输出）：把"这一帧凭什么显示/不显示"打出来。
            # ★ B5：带上 `模式=` 与 `走=` —— 跟飘那只是"站住显形 / 走动淡出"，
            #   光看 alpha 分不清"没显形"是因为走远了还是因为在走，有这两个字段才判得出。
            try:
                _log.debug('幽灵帧：模式=%s alpha=%.4f 距离=%.2f 走=%s want=%s vis=%s '
                           'geo=%s 锚=(%.1f,%.1f)',
                           st.mode, float(st.alpha),
                           st.distance_to(px, py) if px is not None else -1.0,
                           'Y' if moving else 'N', want, gh.isVisible(),
                           gh.geometry().getRect(), st.x, st.y)
            except Exception:
                pass
            self._ghost_save()
            return True
        except Exception as e:
            _log.debug('幽灵推进异常（本帧跳过）: %s', e)
            return False

    # ==================================================================
    #  NPC 人设 / 独立记忆 / 跟随决策（第55轮）
    # ==================================================================
    # 用户口径（第55轮原话，逐字要点）
    #   *「我会给你每个人的设定（deepseek生成的），**你给装上就好**」
    #   *「具体会不会主动跟随我觉得**可以给 AI 决策**」
    #   *「4B 貌似没办法支撑起来这些角色的灵魂，所以，给他们也升级成 7B 吧」
    #   *「★★ 每个人都需要分每个人的记忆，不要搞混了，整的和有葫芦娃那个
    #      千里眼顺风耳似的那就离谱了」
    #
    # ★★ 本轮交付的**边界**（先说清楚，免得把"接口就位"说成"已经能用了"）
    #   NPC 的**实例坐标**目前拿不到 —— `obj_herokris` / `obj_herosusie` 这类实例在
    #   `assets/scenes/*` 里**零命中**（第55轮实测，只有第49轮取证里的 id 常量）。
    #   所以"把 NPC 画进场景、让他在地图上走动"这一步**做不了**，要等重跑 UTMT 补采实例。
    #   本轮做的是**它下面那一层**，而且每一件事都有唯一出口：
    #     · 谁能说话、说什么   → `npc_system_prompt()` / `npc_speak()`
    #     · 他记得什么         → `npc_memory`（一角色一份，物理分开）
    #     · 他会不会跟         → `npc_follow_decide()`（**AI 决策**）
    #   上层的"把人画出来"接上之后，直接调这三个出口即可，不必再改这里。
    # ==================================================================

    #: NPC 系统总开关（与 `SOUL_ENABLED` / `SCENE_LAYER_ENABLED` 同形）。
    #: `False` ⇒ `init_npc_systems()` 建完空壳就返回，所有入口退化成"什么都没发生"。
    #: ⚠️ 保留它本身不是死代码：这是"NPC 说话出问题"时的一刀定位开关。
    NPC_ENABLED = True

    #: NPC **自由生活**（第73轮）总开关 —— 与 `NPC_ENABLED` **分成两个**：
    #: 前者管"NPC 系统在不在"，这个管"他们会不会**自己过日子**"。
    #: 为什么要分：用户可能想留着 NPC 说话/跟随，但不想让他们**未经发起就开口**
    #: （自主开口会占 CPU-only 单并发的模型；见 `_npc_life_gate`）。
    NPC_LIFE_ENABLED = True

    #: 自主闲聊的节拍（秒）。★ 比"用户对话"松得多 —— 自发闲聊是背景音，不该抢注意力。
    NPC_LIFE_MIN_GAP = 45.0

    #: 一轮（一个场景）里最多让 NPC 自己说起几句。
    NPC_LIFE_MAX_TURNS = 2

    #: ★ 第86轮：**主线 NPC** 自主开口的最小间隔（秒）—— 与 `NPC_LIFE_MIN_GAP` **分开**。
    #:   为什么另立一个：纯 NPC 说的是内置池（零成本，45s 一次很自然）；主线 NPC 每句都要
    #:   走 7B（纯 CPU，秒级~十几秒），且**只有一个模型实例** ⇒ 必须比纯 NPC 松得多，
    #:   否则一个场景里的两个主线 NPC 会互相刷屏、把用户对话的口粮挤光。
    #:   ⚠️ 这是**本项目取值**（原作用的是固定脚本对话，没有"自主开口"这回事）。
    NPC_MAIN_TALK_GAP = 180.0

    #: 一次场景切换里最多问**几个** NPC"跟不跟"。
    #: 为什么是 1：每问一次就是一次**真实推理**（7B 纯 CPU）⇒ 问的人越多，换场景越卡。
    #: 取 1 = "换一次场景问最近说过话的那一个"，观感上够用且不会成倍放大延迟。
    NPC_FOLLOW_ASK_PER_SWITCH = 1

    #: ⭐⭐ 第79轮：NPC **自主移动**（层2）—— 与 `NPC_LIFE_ENABLED` **再分一个**。
    #:   前者管「他们会不会自己开口」，这个管「他们会不会**自己挪窝**」（离开当前场景，
    #:   去朋友家 / 去喜欢的地方 / 去没去过的地方）。
    #:
    #:   ★★★ **默认 True（第79轮收尾按用户裁决打开）**。
    #:     用户原话（逐字）：「废除，**默认打开**」——即：旧口径（NPC 只是当前场景的装饰、
    #:     用户不动世界就冻住）**废除**，改为「他们有自己的位置、自己过日子」。
    #:
    #:   ⚠️ 打开后会发生的事（如实告知，免得"怎么突然变了"）：
    #:     · NPC 会**自己离开当前场景**（去朋友家/喜欢的地方/没去过的地方）；
    #:     · 他们的位置**独立于你的位置、独立于切场景**（30 秒一拍）；
    #:     · 你不动，他们照样在过日子（这正是用户口径要的）。
    #:
    #:   用户口径（逐字，第77轮）：
    #:     「**不会因为缺少一个人哪怕是我他们就不生活了**」
    #:     「去哪？找谁？干什么？生活规划这类的事也是由**各自的 AI 决定**」
    #:
    #:   ★ 关掉它（改成 False）⇒ `npc_roam.step()` 零副作用 ⇒ 行为回到第78轮（零回归开关）。
    #:   ★★★ 第80轮**按用户裁决改成默认 True**（用户原话逐字：「**废除，默认打开**」）。
    NPC_AUTONOMOUS_MOVE = True

    #: 自主移动的**推进节拍**（秒）—— 生活决策不需要每帧算。
    #: ★ 30s 一次：既不会「一帧换一次房」，也不会「半天不动」（驻留期本身是分钟级）。
    NPC_AUTONOMOUS_TICK = 30.0

    #: ★★★ 第81轮（层4 存档）：生活档案的**落盘节流**（秒）。
    #: ★ 120s：驻留期本身是分钟级（`MIN_DWELL_SECONDS` 也是分钟级），120s 足够
    #:   把"世界变了"及时写下去；同时避免每拍都写盘（E 盘 exFAT，无谓写会磨损）。
    #: ★ 只在 `_npc_roam_tick` **真发生变化**（有人挪窝 / 驻留到期）时才考虑写盘。
    #: ★ 退出时另有一次 `force=True` 的兜底落盘（见 `_npc_plan_save(force=True)`）。
    NPC_PLAN_SAVE_EVERY = 120.0

    def init_npc_systems(self):
        """建 NPC 服务层：注册表 + 人设 + 一角色一份记忆 + 跟随板 + 别名表。

        失败语义与道具 / 搜索 / 关系同规：**任何一步失败都只降级、不抛出**
        （非关键路径不许让桌宠起不来）。降级后果写进日志，且所有字段先预声明成
        空值 —— 中途失败宿主也不缺属性（本项目踩过"状态只在成功路径上创建"的坑）。
        """
        # 先预声明 —— 中途任何一步失败也不能让别处的 getattr 炸
        self.npc_registry = None
        self.npc_personas = {}
        self.npc_memory = None
        self.npc_followers = None
        self._npc_aliases = {}
        self._npc_invited = []          # 说上过话的 NPC（换场景时才有资格被问"跟不跟"）
        self._npc_follow_pending = []   # 纯 NPC 的"想跟但等你点头"
        self._npc_talking = None        # 最近一次在跟谁说话
        self._npc_last_decision = None  # 最近一次跟随决策 (npc_id, choice, source)
        # ---- 第56轮：站位 / 游荡 / 编队（与说话、跟随**正交**的三件事）----
        #: `npc_placement.PlacementBook`（34 条站位 + 1 条编队 + 9 条结对 + 桌面白名单）。
        self.npc_placement = None
        #: `{npc_id: npc_placement.Body}` —— **只在"当前场景"里**，切场景就重建。
        self.npc_bodies = {}
        #: `npc_placement.PartyRig`（主角团三人，leader=kris，lag=[0,12,24]）。
        self.npc_rig = None
        #: 编队采样主角轨迹用的环形缓冲（`Trail`，25 帧）。
        self.npc_trail = None
        #: 已按哪个场景播下过身体（避免每帧重复重建）。
        self._npc_bodies_scene = None
        #: 上一帧各 body 的位置快照，用于"是否真的动了"（给将来渲染层省重绘）。
        self._npc_bodies_moved = []
        # ---- 第73轮：自由生活（场景反应 / 熟络度 / 传话 / 自主节拍）----
        #: `npc_life.Bonds` —— NPC 两两之间的熟络度（per-pair、对称、渐增）。
        #: 用 `seed_lookup` 从**注册表 + 同名组**推初值（同 AU 0.55 / 同作品 0.30 / 陌生 0）。
        self.npc_bonds = None
        #: 跨世界契约（`assets/npc/_crossworld.json`）；读不到 ⇒ `{}`（降级，不抛）。
        self.npc_crossworld = {}
        #: 「同一角色的不同 AU 版本」配对集合（`set[frozenset]`，只含 `au_family_members`）。
        self._npc_au_pairs = set()
        # ---- 第79轮：自主移动（层1 意图 + 层2 驻留）----
        #: `npc_roam.RoamState` —— **驻留覆盖表**（只存"偏离了静态归属"的人）。
        #: ★ 关掉开关时恒为空表 ⇒ `_npc_scene_roster` 全走 `_placement.json`
        #:   ⇒ 行为与第78轮**逐字相同**（零回归的结构保证）。
        self.npc_roam = None
        #: 上一次自主移动推进的时刻（秒）—— 节拍用 `NPC_AUTONOMOUS_TICK`，不必每帧算。
        self._npc_roam_last_tick = 0.0
        # ---- ★★★ 第81轮：层4 存档（生活档案落盘）----
        #: `npc_plan_store.Book` —— **驻留表 + 每人的规划**（层1/2/3 的状态收进一本书）。
        #: ★ 先预声明成**空书**（而不是 `None`）：`plan_of()` 会"没有就建一个"，
        #:   所以即便下面落盘路径取不到、即便 `npc_roam` 建失败，本字段仍可用
        #:   ⇒ 调用方（`_npc_roam_decide` / `_npc_roam_sleep`）不必到处写 `if None`。
        #:   ★★ 这是"状态只在成功路径上创建"那个坑的**正面写法**（见本函数抬头）。
        self.npc_plan_book = npc_plan_store_mod.Book()
        #: 生活档案的绝对落盘路径（`data_store` 算出来的；取不到 ⇒ `None` = 退内存态）。
        self._npc_plan_path = None
        #: 上次落盘时刻（秒）—— 落盘按 `NPC_PLAN_SAVE_EVERY` 节流，不是每拍都写盘。
        self._npc_plan_last_save = 0.0
        #: `npc_life.LifeLoop` —— 自主开口的节拍（不并发 / 不自我对话 / 失败必解锁 / 反活锁）。
        self.npc_life = None
        #: `{npc_id: set[int]}` —— 该 NPC 的内置对话池已经说过哪几句（纯 NPC 用）。
        self._npc_line_used = {}
        #: 上一次"自由生活"节拍累计到的时间（`LifeLoop` 之外再兜一层限流）。
        self._npc_life_last = 0.0
        #: 自主开口是否因模型忙/用户在说话而被跳过（诊断用，一次性日志去重）。
        self._npc_life_skipped = 0
        #: ★ 第86轮：上一次**主线 NPC** 自主开口的时间（与纯 NPC 分开限流，见 `NPC_MAIN_TALK_GAP`）。
        self._npc_main_last = 0.0

        if not RalseiPet.NPC_ENABLED:
            _log.info('NPC 系统已关闭（NPC_ENABLED=False）⇒ NPC 不说话、不跟随')
            return

        root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
        try:
            self.npc_registry = npc_system_mod.load_registry(root)
        except Exception:
            _log.exception('NPC 注册表加载失败（NPC 相关功能整体降级为不可用）')
            return
        try:
            self.npc_personas = npc_persona_mod.load_personas(root) or {}
        except Exception:
            _log.exception('NPC 人设装载失败（NPC 一律不开口；注册表与跟随规则仍在）')
            self.npc_personas = {}

        # ---- 记忆落盘目录：交给 `data_store`（唯一存储入口）算，取不到就退内存态 ----
        # ⚠️ 这里**不把 data_store 提到模块顶部**：它会反向依赖 memory 层，
        #    顶部 import 会做出一条初始化环（本项目栽过 4 次，见第12轮回归锁）。
        # ⚠️ `data_root()` 返回的是 **`(路径, 'vault'|'staging')` 元组**，不是字符串 ——
        #    直接拿去拼路径会得到一个叫 "(E:\\..., 'vault')" 的怪目录。
        mem_dir = None
        try:
            import data_store
            _dr = data_store.data_root(create=True)
            _path = _dr[0] if isinstance(_dr, tuple) else _dr
            mem_dir = npc_persona_mod.memory_root(_path)
        except Exception as e:
            _log.warning('NPC 记忆落盘目录取不到 ⇒ 退内存态（不写盘）: %s', e)
        try:
            self.npc_memory = npc_persona_mod.MiniMemory(root=mem_dir)
        except Exception:
            _log.exception('NPC 独立记忆建立失败（NPC 一律不开口）')
            self.npc_memory = None
        if self.npc_memory is not None and mem_dir:
            for _nid in self.npc_registry.ids():
                try:
                    _n = self.npc_memory.load(_nid)   # 一角色一文件；读不到就是空
                    if _n:
                        _log.debug('NPC %s 读回记忆 %d 条', _nid, _n)
                except Exception as e:
                    _log.debug('NPC %s 记忆读回异常（已忽略）: %s', _nid, e)

        try:
            self.npc_followers = npc_system_mod.FollowerBoard(self.npc_registry)
        except Exception:
            _log.exception('跟随板建立失败（跟随决策降级为不可用）')
            self.npc_followers = None

        # ---- 第56轮：站位表（原作站位 + 游荡 + 编队 + 结对 + 桌面白名单）----
        # 读不到 ⇒ 空簿（`EMPTY_BOOK` 形状恒定）⇒ `npc_bodies` 恒空 ⇒ 本功能整体静默降级，
        # 别的入口（说话 / 跟随 / 道具）**一点不受影响**。
        try:
            self.npc_placement = npc_placement_mod.load_placement(root)
        except Exception:
            _log.exception('NPC 站位表加载失败（站位与游荡降级为不可用）')
            self.npc_placement = None
        # ★ 数据镜像自查：`_placement.json` 的 `desktop.allowed` 必须与
        #   `npc_system.DESKTOP_ALLOWED_IDS` 逐字一致。不一致 = 有人只改了一处，
        #   结果是"能站在桌面"和"能跟你上桌面"给出两个答案 —— 这种矛盾必须吵出来，
        #   不能静默取其中一个（第45轮"多解闸"教训）。
        if self.npc_placement is not None:
            _mirror = tuple(self.npc_placement.desktop_allowed_ids)
            if _mirror and _mirror != tuple(npc_system_mod.DESKTOP_ALLOWED_IDS):
                _log.warning('桌面白名单两处不一致：_placement.json=%s / 代码=%s'
                             '（以代码为准）', _mirror,
                             tuple(npc_system_mod.DESKTOP_ALLOWED_IDS))
        # 建编队（不依赖当前场景；anchor 是**当前主控角色**，见 `_npc_anchor_id()`）。
        try:
            if self.npc_placement is not None:
                self.npc_trail = npc_placement_mod.Trail()
                self.npc_rig = self.npc_placement.rig('party')
        except Exception as e:
            _log.warning('NPC 编队建立失败（主角团不结伴走）: %s', e)
            self.npc_rig = None

        # ---- 第73轮：自由生活（读跨世界契约 → 熟络度初值 → 自主节拍）----
        # 全链降级：契约读不到 ⇒ `au_pairs` 空、`Bonds` 仍可用（初值一律"陌生"）。
        # ★ `Bonds` / `LifeLoop` 的构造**不读文件**（零依赖纯策略），所以这里不会失败；
        #   真正可能失败的是契约读取，失败也只是"少了 AU 加速"，不是"整块没了"。
        try:
            self.npc_crossworld = npc_system_mod.load_crossworld(root) or {}
            self._npc_au_pairs = npc_system_mod.au_twin_pairs(self.npc_crossworld)
            self.npc_bonds = npc_life_mod.Bonds(seed_lookup=self._npc_seed_lookup)
        except Exception:
            _log.exception('自由生活：契约/熟络度建立失败（退化为"一律陌生"）')
            self.npc_crossworld = {}
            self._npc_au_pairs = set()
            self.npc_bonds = None
        try:
            # ★ `gate` = 让路闸：用户正在说话 / 模型在忙 / 总开关关 ⇒ 不自主开口。
            #   `LifeLoop` 把它当成纯函数问，**不推进轮转**（不是 NPC 的错）。
            self.npc_life = npc_life_mod.LifeLoop(
                min_gap=RalseiPet.NPC_LIFE_MIN_GAP,
                max_turns=RalseiPet.NPC_LIFE_MAX_TURNS,
                gate=self._npc_life_gate)
        except Exception:
            _log.exception('自由生活：节拍器建立失败（NPC 不自主开口）')
            self.npc_life = None
        self._npc_line_used = {}

        # ---- ★★★ 第79轮：自主移动 · 层2 驻留表 ----
        # ★ 关掉开关时 `RoamState(enabled=False)` 恒为空表，`step()` 零副作用
        #   ⇒ 后续 `_npc_scene_roster` 读它只会拿到 `None` ⇒ 全走站位表
        #   ⇒ 行为与第78轮**逐字相同**（零回归，见 `check79` B 段）。
        try:
            self.npc_roam = npc_roam_mod.RoamState(
                enabled=bool(RalseiPet.NPC_AUTONOMOUS_MOVE))
            if self.npc_roam.enabled:
                _log.info('NPC 自主移动：**开**（驻留层已启用；他们会有自己的位置）')
            else:
                _log.info('NPC 自主移动：关（默认；NPC 仍只在站位表里"原地生活"）')
        except Exception:
            _log.exception('自主移动：驻留表建立失败（退化为"全体回站位表"）')
            self.npc_roam = None

        # ---- ★★★ 第81轮：层4 存档 —— 把层1/2/3 的状态读回内存 ----
        # ★ 顺序很重要：**先有 `self.npc_roam`（上一段建的）**，再把书里那份驻留表
        #   灌回去 —— 反过来会让"读回来的驻留表"被随后新建的空表覆盖（静默丢档）。
        # ★ 全部失败都只降级：文件不存在 / 读坏了 ⇒ 空书（`load()` 绝不抛）；
        #   路径取不到（`data_store` 不可用）⇒ 退内存态（本拍照常过日子，只是不落盘）。
        self._npc_plan_path = self._npc_plan_file()
        try:
            self.npc_plan_book = npc_plan_store_mod.load(self._npc_plan_path)
        except Exception as e:
            _log.debug('生活档案读取异常（退空书）: %s', e)
            self.npc_plan_book = npc_plan_store_mod.Book()
        # ★★ 驻留表灌回：书里那份才是"重启前的世界"。**只在两边都在时必须做**；
        #   `RoamState.from_dict` 的 `enabled` 由 `Book` 保留 ⇒ 不会把"开关关了"
        #   的人偷偷打开（书里那份的 `enabled` 忠实于写盘时）。
        _roam_from_book = getattr(self.npc_plan_book, 'roam', None)
        if _roam_from_book is not None:
            self.npc_roam = _roam_from_book
        elif self.npc_roam is not None:
            # 书里没有驻留表（首次运行 / 版本不符）⇒ 把**新建的**空表放进书，
            # 这样本拍结束时落盘会把它一起写下去（口径一致：书里永远有当前 roam）。
            self.npc_plan_book.roam = self.npc_roam
        _n_plans = len(getattr(self.npc_plan_book, 'plans', {}) or {})
        # ★ 驻留人数走 `len(RoamState)`（`__len__` = 覆盖表条数）—— **不另查一次**；
        #   `RoamState` 是唯一真源（它的 `snapshot()` 也要遍历 `_by_id`，这里只要个数）。
        _n_res = len(self.npc_roam) if self.npc_roam is not None else 0
        _log.info('NPC 生活档案：%s（规划 %d 人 / 驻留 %d 人）',
                  self._npc_plan_path or '内存态-不落盘', _n_plans, _n_res)

        # ---- 别名表：id / 英文名 / 中文名 三个都收（点名两层都认）----
        try:
            self._npc_aliases = npc_persona_mod.address_aliases(
                [(n.id, n.name, n.name_cn) for n in self.npc_registry.all()])
        except Exception as e:
            _log.warning('NPC 别名表建立失败（@点名不可用）: %s', e)
            self._npc_aliases = {}

        # ---- 场景切换钩子：按新场景清掉"进不来"的跟随者 ----
        try:
            hooks = getattr(self, '_scene_switch_hooks', None)
            if isinstance(hooks, list):
                hooks.append(self._on_scene_switched_npc)
            else:
                _log.warning('场景切换钩子列表不存在 ⇒ NPC 跟随不随场景变化')
        except Exception as e:
            _log.warning('NPC 场景钩子挂载失败: %s', e)

        _log.info('NPC 系统就绪：登记 %d 个（主线 %d / 纯 NPC %d）；人设 %d 份；'
                  '点名别名 %d 条；记忆落盘=%s',
                  len(self.npc_registry), len(self.npc_registry.main_npcs()),
                  len(self.npc_registry.plain_npcs()), len(self.npc_personas),
                  len(self._npc_aliases), mem_dir or '内存态')
        if self.npc_placement is not None:
            _log.info('NPC 站位：%s', self.npc_placement.describe())
        # ★ 开局就播一次身体 —— 启动场景是 `desktop`（`SceneController.load()` 定的），
        #   而 `_scene_switch_hooks` 只在**发生切换**时触发 ⇒ 不主动播一次就永远没人站位。
        try:
            self._npc_seed_bodies(self._npc_scene_id())
        except Exception as e:
            _log.warning('NPC 站位初始化失败（开局无站位）: %s', e)

    # ---------------------------------------------------------------- 点名
    def _npc_scene_id(self):
        """当前场景 id（取不到 ⇒ `None`，不编一个）。"""
        sid = getattr(self.__dict__.get('_scene_state'), 'scene_id', None)
        return sid if isinstance(sid, str) and sid else None

    def npc_address(self, text):
        """`'@苏西 你好'` → `('susie', '你好')`；不是点名 / 认不出 → `None`。

        纯转发（解析逻辑全在 `npc_persona.parse_address`，这边只补异常兜底）——
        规则只留一份真源，判据才好写。
        """
        if not isinstance(text, str):
            return None
        try:
            return npc_persona_mod.parse_address(text, self._npc_aliases)
        except Exception as e:
            _log.debug('点名解析异常（已忽略）: %s', e)
            return None

    def npc_label(self, npc_id):
        """对话里显示的名字（优先中文名）。没登记 ⇒ 原样回传 id。"""
        npc = self.npc_registry.get(npc_id) if self.npc_registry else None
        if npc is None:
            return '' if npc_id is None else str(npc_id)
        return npc_persona_mod.speaker_label(npc.name, npc.name_cn) or npc.name

    def npc_persona_of(self, npc_id):
        """该 NPC 的人设全文；没有 ⇒ `None`（**不返回空串**，空串会被当成"有但空"）。"""
        t = (self.npc_personas or {}).get(npc_id)
        return t if isinstance(t, str) and t.strip() else None

    # ---------------------------------------------------------------- 系统提示词
    def _build_npc_context(self, npc_id=None):
        """NPC 的「此刻」块 —— ★ **只放共有的世界状态**（时段 / 天气 / 在哪）。

        为什么不复用 `_build_ai_context()`（Ralsei 那一份）：
          那一份里有"你累得快撑不住了""你站在一个打开的窗口上""你有很久没跟对方
          说话了"—— 这些描述的是**桌宠本体**。混进 NPC 的提示词，下一句就会听到
          苏西说"我站在一个打开的窗口上"。
          用户最怕的"葫芦娃千里眼顺风耳"，串的正是这种**别人的私人体感**，
          所以这里宁可少给，也不给不属于他的状态。
        """
        parts = []
        try:
            _h = time.localtime().tm_hour
            if 5 <= _h < 8:
                _tod = '清晨'
            elif 8 <= _h < 11:
                _tod = '上午'
            elif 11 <= _h < 13:
                _tod = '中午'
            elif 13 <= _h < 17:
                _tod = '下午'
            elif 17 <= _h < 19:
                _tod = '傍晚'
            elif 19 <= _h < 23:
                _tod = '晚上'
            else:
                _tod = '深夜'
            parts.append('现在是%s' % _tod)
        except Exception as e:
            _log.debug('NPC 上下文：时段分片失败（已忽略）: %s', e)
        try:
            _w = self.weather_system.get_current_weather()
            if _w:
                parts.append('天气%s' % _w)
        except Exception as e:
            _log.debug('NPC 上下文：天气分片失败（已忽略）: %s', e)
        if not parts:
            return ''
        return ('【此刻】' + '，'.join(parts)
                + '。（这是当下的环境，可以自然地带一点出来，但别逐条念。）')

    def npc_system_prompt(self, npc_id):
        """某个 NPC 的 system prompt —— **唯一出口**。

        装不了（没登记 / 没装人设）⇒ 返回 `''`，调用方据此**拒绝这次对话**。
        为什么是"拒绝"而不是"退回 Ralsei 的人设"：那正是用户最怕的那种串味
        （拿别人的身份说话，还看不出来）。宁可这一句没有回应。
        """
        npc = self.npc_registry.get(npc_id) if self.npc_registry else None
        if npc is None:
            return ''
        persona = self.npc_persona_of(npc_id)
        if not persona:
            return ''
        entries = []
        try:
            if self.npc_memory is not None:
                entries = self.npc_memory.history(npc_id)   # ★ 只取他自己的
        except Exception as e:
            _log.debug('NPC %s 记忆读取异常（按无记忆处理）: %s', npc_id, e)
        return npc_persona_mod.build_system_prompt(
            npc.name, persona, entries, npc_id, self._build_npc_context(npc_id),
            life=self._npc_life_blocks(npc_id))

    def _npc_model(self, npc_id):
        """这个 NPC 该用哪个 Ollama 句柄 —— `None` = **跟随 App 配置**。

        ★ 为什么要有这个函数（而不是让调用方直接读 `npc.model`）：
          注册表里的 `model` 字段曾经**只登记、没人读** —— 于是"主线 NPC 用 4B"
          这句话在代码里根本不成立（实际跑的是 `config.json` 的 `api.model`）。
          把"读它"收成一个出口，以后换名字/加回落只需改这一处。
        ★ 为什么现在注册表里全是 `None`：`config.json` 里那个模型就是
          `ralsei:v4` = `qwen2.5:7b-instruct-q4_K_M` ⇒ **NPC 拿到的本来就是 7B**。
          再建一个 `ralsei-npc:7b` 只会让 Ollama 在 Ralsei 与 NPC 之间**各常驻一份
          4.7GB 权重**（同名不同句柄不会共享实例），纯亏 —— 用户那句
          「如果这非常吃性能那就慎重」正是这个意思。
          真需要单独给 NPC 换模型：把它填成 Ollama 里**真实存在**的句柄即可，
          接线已就绪（`api_client._chat_payload` 收 `model=` 覆盖）。
        """
        try:
            npc = self.npc_registry.get(npc_id) if self.npc_registry else None
            val = getattr(npc, 'model', None) if npc is not None else None
        except Exception as e:
            _log.debug('NPC %s 模型句柄解析异常（按不覆盖处理）: %s', npc_id, e)
            return None
        return val if isinstance(val, str) and val.strip() else None

    # ---------------------------------------------------------------- 说话
    def npc_speak(self, npc_id, text, on_reply, on_delta=None):
        """★ NPC 说话的唯一出口 —— 「@某人 内容」最终走到这里。

        返回 `True` = 请求已发出；`False` = **明确拒绝**（并已回调 `on_reply(None)`）。
        拒绝的四种情形：NPC 系统没建起来 / id 没登记 / 这个人还没装人设
        （用户没给设定的人**不许**开口 —— 更不许借别人的设定开口）/ 模型不可用。

        ★ 顺序讲究：**"对方说的这句"先记进他的记忆，再去拦"模型不可用"**。
          理由是本项目那条"宁可多留一句，也不静默丢信息"—— 模型可能只是临时没起来，
          而"你对他说过这句话"是个事实，不该因为回复拿不到就一起丢掉
          （下一轮模型起来时，他是能看见你说过的这句的）。
        """
        if self.npc_registry is None or self.npc_memory is None:
            on_reply(None)
            return False
        npc = self.npc_registry.get(npc_id)
        if npc is None:
            _log.info('点名了未登记的 NPC %r ⇒ 不当成任何一个角色回话', npc_id)
            on_reply(None)
            return False
        if not self.npc_persona_of(npc_id):
            _log.info('NPC %s 还没装设定 ⇒ 不开口（不许借别人的人设）', npc_id)
            on_reply(None)
            return False
        # 对方说的这句进**他自己**的记忆（不是 Ralsei 的，也不是别的 NPC 的）
        try:
            self.npc_memory.remember(npc_id, text, who='player',
                                     scene=self._npc_scene_id())
        except Exception as e:
            _log.debug('NPC %s 记忆写入异常（已忽略）: %s', npc_id, e)
        # ---- 第73轮：他**转告**同场的另一位（★ 显式、带署名，不共享容器）----
        # ★ 语义：B 记下的是"**A 说过这句话**"（`who=A`），不是"我知道了这件事"。
        #   这正是用户那句「怪物之间**没有身份标识**，所以**那需要自己判断**」的落地：
        #   信息**带着来源走**，但不带"他是哪个世界的"。
        # ★ 只在**真的有人在场**时才传（`_npc_life_ids` 的判据只有一处 = `npc_bodies`）。
        try:
            _others = [n for n in self._npc_life_ids() if n != npc_id]
            if _others:
                npc_life_mod.transmit(self.npc_memory, npc_id, _others[0])
                if self.npc_bonds is not None:
                    self.npc_bonds.meet(npc_id, _others[0])
        except Exception as e:
            _log.debug('NPC 传话异常（已忽略）: %s', e)
        self._npc_talking = npc_id
        if npc_id not in self._npc_invited:
            self._npc_invited.append(npc_id)
        # 模型不可用 ⇒ **明确拒绝**（返回 False），而不是"发了一个不会回来的请求"。
        # 为什么非要在这一步拦：`chat_with_ai` 在 API 关闭时也会回调 None，
        # 那样调用方拿到的 `True` 会让人以为"请求已经发出去了"（本项目最烦的假信号）。
        if not self._npc_ai_available():
            _log.info('本地模型不可用 ⇒ NPC %s 这一句不说话（但你说的这句已经记下了）', npc_id)
            on_reply(None)
            return False
        try:
            self.chat_with_ai(text, on_reply, on_delta, speaker=npc_id,
                              model=self._npc_model(npc_id))
        except Exception:
            _log.exception('NPC %s 对话发起异常', npc_id)
            on_reply(None)
            return False
        return True

    # ---------------------------------------------------------------- 跟随（AI 决策）
    def _npc_follow_policy(self, npc):
        """分层策略字面量（主线 = autonomous / 纯 NPC = consent）。取不到 ⇒ `''`。"""
        try:
            return npc_system_mod.follow_policy(npc)
        except Exception:
            return ''

    def _npc_apply_follow(self, npc_id, choice):
        """把决策落到 `FollowerBoard`（+ 日志）。返回落定后的状态字符串。"""
        board = self.npc_followers
        if board is None:
            return ''
        try:
            if choice in (npc_persona_mod.FOLLOW_FOLLOW, npc_persona_mod.FOLLOW_RALLY):
                st = board.request(npc_id)
                if st == npc_system_mod.FOLLOW_PENDING:
                    # 纯 NPC 想跟：按第49轮口径要**主角点头** ⇒ 挂起等许可
                    if npc_id not in self._npc_follow_pending:
                        self._npc_follow_pending.append(npc_id)
                    _log.info('NPC %s 想跟上来，但纯 NPC 需要你同意（暂挂起）', npc_id)
                else:
                    if npc_id in self._npc_follow_pending:
                        self._npc_follow_pending.remove(npc_id)
                return st
            board.stop(npc_id)
            if npc_id in self._npc_follow_pending:
                self._npc_follow_pending.remove(npc_id)
            return npc_system_mod.FOLLOW_IDLE
        except Exception as e:
            _log.debug('NPC %s 跟随状态落定异常（已忽略）: %s', npc_id, e)
            return ''

    def npc_follow_approve(self, npc_id, approved=True):
        """主角对「纯 NPC 的跟随请求」表态（跟随规则的出口，供菜单/对话调用）。"""
        board = self.npc_followers
        if board is None:
            return False
        try:
            ok = bool(board.respond(npc_id, bool(approved)))
        except Exception as e:
            _log.debug('NPC %s 跟随许可异常（已忽略）: %s', npc_id, e)
            return False
        if npc_id in self._npc_follow_pending:
            self._npc_follow_pending.remove(npc_id)
        _log.info('NPC %s 跟随请求：%s', npc_id, '同意' if approved else '拒绝')
        return ok

    def npc_follow_decide(self, npc_id, dist=None, on_result=None):
        """让 **NPC 自己**决定跟不跟 —— ★ 用户口径「可以给 AI 决策」。

        判定链（**完全复用 `npc_persona.decide_follow`，这里不重写一遍规则**）：
          · AI 说了合法的一个词（`follow`/`stay`/`rally`/`leave`）⇒ 用它（`source='ai'`）；
          · AI 没表态 / 乱说 / 模型不可用 ⇒ 落回 `npc_system` 的分层策略：
            主线（`autonomous`）按距离自主判，纯 NPC（`consent`）不主动跟。

        ★ 为什么"模型不可用"也算"没表态"而不是"报错"：
          跟随决策是**可降级**的 —— 模型没起来时按分层策略走，桌面照样能用；
          反之若在这儿抛错，会顺着场景切换把整条切换链带崩。

        返回 `True` = 已发起（结果走 `on_result(choice, source)` 或日志）。
        """
        if self.npc_registry is None or self.npc_followers is None:
            return False
        npc = self.npc_registry.get(npc_id)
        if npc is None:
            return False
        policy = self._npc_follow_policy(npc)
        world = self._current_world()
        far = getattr(companion_mod, 'FOLLOW_FAR_THRESHOLD', 160.0)
        persona = self.npc_persona_of(npc_id)

        def _finish(ai_reply=None):
            ai_choice = npc_persona_mod.parse_follow_choice(ai_reply) \
                if isinstance(ai_reply, str) else None
            choice, source = npc_persona_mod.decide_follow(
                ai_choice, policy=policy, dist=dist, far_threshold=far, world=world)
            st = self._npc_apply_follow(npc_id, choice)
            self._npc_last_decision = (npc_id, choice, source)
            _log.info('跟随决策 %s：%s（模型回 %r ⇒ 跟随板状态 %s）',
                      npc_id, npc_persona_mod.decision_reason(choice, source),
                      ai_reply, st or 'n/a')
            if callable(on_result):
                try:
                    on_result(choice, source)
                except Exception as e:
                    _log.debug('跟随决策回调异常（已忽略）: %s', e)
            return (choice, source)

        # 模型不可用 ⇒ 直接按策略落定（不发明一次假请求）
        if not self._npc_ai_available() or not persona:
            _finish(None)
            return True
        system = npc_persona_mod.build_follow_system(
            npc.name, persona, dist=dist, world=world)
        try:
            self.chat_with_ai('现在决定：跟，还是不跟？', _finish, None,
                              lean=True, speaker=npc_id, system_override=system,
                              remember=False, model=self._npc_model(npc_id))
        except Exception:
            _log.exception('跟随决策请求发起失败（按策略落定）')
            _finish(None)
        return True

    def _npc_ai_available(self):
        """本地模型能不能用（与对话链路同一条判据，不另立一个）。"""
        try:
            cli = getattr(self, 'api_client', None)
            return bool(getattr(self, 'api_enabled', False)
                        and cli is not None and getattr(cli, 'enabled', False))
        except Exception:
            return False

    def _on_scene_switched_npc(self, scene_id, scene):
        """★ 场景切换钩子：① 清掉"进不来"的跟随者；② 问一个 NPC"跟不跟"；
        ③ **按新场景重建站位与游荡**（★ 第56轮新增）。

        由 `SceneController._fire_switch_hooks()` 调（钩子抛异常会被它吞掉并记日志）。
        顺序有意义：**先清理再决策、最后布局** —— 反过来的话，
        ①刚被"清掉又决定要跟"的人会在下一个不合法场景里再被清一次（日志里两次矛盾记录）；
        ②布局若排在清理前，会把"刚被判定进不来的人"也画进新场景。
        """
        board = self.npc_followers
        if board is None or self.npc_registry is None:
            return
        world = self._current_world()
        # `carried` = 谁被装进球里。**只用现成状态查询**（`BubbleField.__contains__`），
        # 不去调 `toggle_bubble` —— 那是"改状态"的入口，在这里调会把球开开关关。
        carried = self._npc_carried_ids()
        try:
            kicked = board.tick(world, scene_id=scene_id, carried_ids=carried)
        except Exception as e:
            _log.debug('跟随板清理异常（已忽略）: %s', e)
            kicked = []
        if kicked:
            # ★ 如实说"他没跟来"，而不是让用户以为人还在
            _log.info('这些 NPC 跟不进 %s（%s 世界）⇒ 停在原地：%s',
                      scene_id, world, '、'.join(kicked))
            self._npc_menu_message('* %s 没法跟你进这里，先在原地等着了。'
                                   % '、'.join(self.npc_label(k) for k in kicked))
            # ★ 第56轮：被踢出的人**不可能**出现在新场景里"站着不动"——
            #   他会落在旧场景继续游荡（身体是**按场景重建**的，见 `_npc_seed_bodies`）。
        # ①·5 重建站位与游荡，并**同时**用世界门控筛一遍（桌面白名单在这里生效）
        try:
            self._npc_seed_bodies(scene_id)
        except Exception as e:
            _log.debug('切换后重建站位异常（已忽略）: %s', e)
        # ② 只问"最近说过话的那一个"（每次问都是一次真实推理，见常量注释）
        n = 0
        for nid in reversed(self._npc_invited):
            if n >= RalseiPet.NPC_FOLLOW_ASK_PER_SWITCH:
                break
            if board.is_following(nid):
                continue
            self.npc_follow_decide(nid, dist=None)
            n += 1

    # ==================================================================
    #  站位 / 游荡 / 结伴（★ 第56轮）
    # ==================================================================
    #  用户口径（逐字）
    #    「对于那些npc参考原作给他们设定的初始在城堡镇里的位置再加一些自己游荡的
    #      特性，就像是，主角团会总凑在一起，其他npc一部分也会有相互经常互动的
    #      情节，参考原作，其次，只有主角团最多加个lancer能来电脑桌面，其余的不能」
    #
    #  四件事落在四个地方（**别把它们混成一个函数**）：
    #    · 初始位置 + 游荡 + 结对的数据   → `assets/npc/_placement.json`（可审计）
    #    · 运动学（三个模式 / 编队 / 结对）→ `modules/npc_placement.py`（零依赖）
    #    · 桌面白名单（"能不能上桌面"）    → `npc_system.world_gate`（政策）
    #    · **每帧把谁摆在哪**（本节三个方法）→ 宿主接线
    #
    #  ⚠️ 现在**只算位置**，还没有把 NPC 画出来：
    #     渲染要 34 个 NPC × 四向的精灵帧，而 `assets/sprites/` 里**一个 NPC 帧都没有**
    #     （第49轮只导出了扭蛋球 + 四个可进球角色，见 `spr49_log.txt`）。
    #     ⇒ 本节的产物是 `self.npc_bodies`（`{id: Body}`，含 x/y/facing），
    #       下一轮导精灵后，渲染层直接读它即可，**不必再改这里**。

    #: 桌面上的主角团站位（相对桌宠中心，单位 = 屏幕像素）。
    #: ★ 为什么**不复用** `_placement.json` 的城堡镇坐标：桌面不是房间，
    #:   没有 1000×1000 的房间盒，硬套会把人摆到屏幕外（这一点在关卡里有对照：
    #:   `ralsei` 的城堡卧室是 1000×1000，而桌面只有 ~1920×1080 的图标区）。
    DESKTOP_PARTY_OFFSETS = (0.0, -44.0, 44.0)

    def _npc_carried_ids(self):
        """谁正被装进球里（**只查状态**，不改状态 —— 见 `_on_scene_switched_npc`）。"""
        try:
            fld = self._ensure_bubble_field()
            return ['ralsei'] if (fld is not None and 'ralsei' in fld) else []
        except Exception:
            return []

    def _npc_anchor_id(self):
        """编队的**锚**是谁 —— 桌面 = 桌宠本身（Ralsei）；房间 = 编队 leader。

        ★ 刻意**不写死** `'kris'`：原作里主控恒为 Kris（`scr_makecaterpillar`
          把主角 `char_id` 放进 `char_id`、队友按 slot 落后 12/24 帧），
          所以房间里 leader 就是他；但**桌面上主控是 Ralsei 本人**。
          把"谁在带队"收成一个函数，将来换主控不必改三处。
        """
        if self._npc_scene_id() == npc_system_mod.DESKTOP_SCENE:
            return 'ralsei'
        rig = getattr(self, 'npc_rig', None)
        leader = getattr(rig, 'leader', None) if rig is not None else None
        return leader or 'kris'

    def _npc_anchor_pos(self):
        """锚的当前位置。桌面 = 桌宠窗口中心（屏幕坐标）；房间 = leader 身体的位置。"""
        if self._npc_bodies_scene == npc_system_mod.DESKTOP_SCENE:
            try:
                return (float(self.x()) + self.width() / 2.0,
                        float(self.y()) + self.height() / 2.0)
            except Exception:
                return (0.0, 0.0)
        b = (self.npc_bodies or {}).get(self._npc_anchor_id())
        return b.pos if b is not None else (0.0, 0.0)

    def _npc_scene_roster(self, scene_id):
        """**房间场景**里该有谁：站位表的居民 ∩ 注册表 ∩ 世界门控。

        ★ 两道筛子都不能省：
          · **注册表** —— 站位表里有、注册表里没有的人**不凭空造**
            （否则会出现一个说话走 `npc_system_prompt` 却查不到人设的幽灵）。
          · **世界门控** —— 让"他站在这一间"和"他能不能进这一间"给出**同一个答案**
            （同一条判据两处算两份，正是本项目最贵的坑）。

        ★★★ 第79轮（层2）：**驻留表优先**。
          "他在哪"由两处共同决定，**优先级明确**：
            ① `npc_roam.resident_of(nid)` —— 有值 ⇒ 他自主挪到了这儿（覆盖）；
            ② 没有 ⇒ 回落到 `book.scene_of(nid)`（**静态归属**，真源仍是 `_placement.json`）。
          ★ 为什么是"覆盖"而不是"复制一份默认值"：见 `npc_roam` 抬头 ——
            默认值的真源只有一个，本层只回答"有谁**不在**他该在的地方"。
          ★ 关掉开关（默认）⇒ `resident_of()` 恒 `None` ⇒ 与第78轮**逐字相同**。
        """
        book = getattr(self, 'npc_placement', None)
        if book is None or self.npc_registry is None:
            return []
        world = self._current_world()
        carried = self._npc_carried_ids()
        roam = getattr(self, 'npc_roam', None)
        out = []
        for nid in book.ids():
            # ---- ① 驻留覆盖（层2）：有值就用它，否则回落静态归属 ----
            here = None
            if roam is not None:
                here = roam.resident_of(nid)
            if here is None:
                here = book.scene_of(nid)
            if here != scene_id:
                continue
            npc = self.npc_registry.get(nid)
            if npc is None:
                _log.debug('站位表有 %s 但注册表没有 ⇒ 不造人', nid)
                continue
            g = npc_system_mod.world_gate(npc, world, scene_id=scene_id,
                                          carried=nid in carried)
            if not g.ok:
                _log.debug('站位跳过 %s：%s（%s）', nid, g.reason, g.detail)
                continue
            out.append(nid)
        return out

    def _npc_desktop_roster(self):
        """**桌面上**该在的人：白名单 ∩ 正在跟随（桌宠本人除外）。

        ★ 判据**只有一处** = `world_gate`（它读 `npc_system.DESKTOP_ALLOWED_IDS`）。
          ⚠️ 这里**刻意不**再查一遍 `_placement.json` 的 `desktop.allowed`：
            同一份规则两处算，就会出现"改了代码那边不生效 / 改了 JSON 那边不生效"
            的两个真相（本项目最贵的坑）。数据那边只作**人类可读的留痕**，
            由 `check56` 断言两边逐字相等、并在 `init_npc_systems` 里记 warning 兜底。

        ★ 为什么必须叠加"正在跟随"：用户说「只有主角团最多加个 lancer **能来**电脑
          桌面」—— "能来"是**许可**，不是"默认就站在你桌上"。桌宠本人（Ralsei）
          本来就住在桌面（`BEDTIME_HOME_SCENE = 'desktop'`），所以他不进这份名单
          （**他就是锚**）。
        """
        if self.npc_placement is None or self.npc_registry is None:
            return []
        board = getattr(self, 'npc_followers', None)
        world = self._current_world()
        out = []
        for nid in npc_system_mod.DESKTOP_ALLOWED_IDS:
            if nid == 'ralsei':
                continue
            npc = self.npc_registry.get(nid)
            if npc is None:
                continue
            g = npc_system_mod.world_gate(
                npc, world, scene_id=npc_system_mod.DESKTOP_SCENE)
            if not g.ok:
                _log.debug('桌面站位跳过 %s：%s', nid, g.reason)
                continue
            if board is None or not board.is_following(nid):
                continue                    # 「能来」≠「已经来了」
            out.append(nid)
        return out

    def _npc_build_desktop_bodies(self, ids):
        """把桌面上该在的人摆到桌宠身边（**屏幕坐标**，站立）。"""
        ax, ay = self._npc_anchor_pos()
        out = {}
        for i, nid in enumerate(ids):
            off = self.DESKTOP_PARTY_OFFSETS[(i + 1) % len(self.DESKTOP_PARTY_OFFSETS)]
            out[nid] = npc_placement_mod.Body(
                nid, scene=npc_system_mod.DESKTOP_SCENE, x=ax + off, y=ay,
                facing=npc_placement_mod.FACE_DOWN,
                mode=npc_placement_mod.MODE_STAND)
        return out

    def _npc_seed_bodies(self, scene_id=None):
        """按场景重建身体，返回建立了几个。

        两种场景、两套空间（**别混**）：
          · **房间** —— 位置来自 `_placement.json`（房间世界坐标），锚 = 编队 leader；
          · **桌面** —— 位置由**桌宠本体**推（屏幕坐标），锚 = Ralsei。
        ★ 两条路径都过 `world_gate` ⇒ 桌面白名单在两条路径上都生效
          （这就是"同一份判据只算一次"的落地）。
        """
        scene_id = scene_id or self._npc_scene_id()
        self._npc_bodies_scene = scene_id
        self.npc_bodies = {}
        self._npc_bodies_moved = []
        book = getattr(self, 'npc_placement', None)
        if book is None:
            return 0
        try:
            if scene_id == npc_system_mod.DESKTOP_SCENE:
                self.npc_bodies = self._npc_build_desktop_bodies(
                    self._npc_desktop_roster())
            else:
                self.npc_bodies = book.initial_bodies(
                    self._npc_scene_roster(scene_id))
        except Exception as e:
            _log.warning('站位初始化失败（%s ⇒ 本场景无 NPC 身体）: %s', scene_id, e)
            self.npc_bodies = {}
        # 轨迹清零：编队采样的是"主角走过的路"，换场景后旧轨迹会把队友
        # 拉到上一个房间的位置上（第46轮 caterpillar 的同类坑）。
        if self.npc_trail is not None:
            try:
                self.npc_trail.reset(*self._npc_anchor_pos())
            except Exception:
                pass
        return len(self.npc_bodies)

    def npc_placement_tick(self, dt):
        """每帧推进：**游荡**（stand/patrol/pace）+ **结对**（approach/face）。

        挂在 `update_movement`（30ms，= 原作 `GMS2FPS = 30`）上，
        dt 复用已钳到 0.1s 的 `elapsed_time`（与 `npc_placement.MAX_DT` 同口径）。
        ★ 为什么**不**在这里做编队的 `place()`：编队的锚是**主角本人的实时位置**，
          它由渲染层（或主控更新）提供；本函数只保证"身体各自在游荡"。
        """
        bodies = getattr(self, 'npc_bodies', None)
        if not bodies:
            return []
        moved = []
        try:
            moved = npc_placement_mod.step_bodies(bodies, dt)
        except Exception as e:
            _log.debug('NPC 游荡推进异常（本帧跳过）: %s', e)
            return []
        # ---- 结对：同一场景内才生效（`BOND_SAME_SCENE_ONLY`）----
        book = getattr(self, 'npc_placement', None)
        if book is not None and len(bodies) > 1:
            try:
                for bond in book.bonds:
                    ba, bb = bodies.get(bond.a), bodies.get(bond.b)
                    if ba is None or bb is None:
                        continue          # 两人不同场景 / 有人不在场 ⇒ 本帧不凑
                    r = bond.resolve(ba.pos, bb.pos, dt,
                                     speed=npc_placement_mod.BOND_APPROACH_SPEED,
                                     box=ba.box or bb.box)
                    if r['moved']:
                        ba.x, ba.y = r['a']
                        bb.x, bb.y = r['b']
                        moved.extend([bond.a, bond.b])
                    ba.facing, bb.facing = r['facing_a'], r['facing_b']
            except Exception as e:
                _log.debug('NPC 结对推进异常（本帧跳过）: %s', e)
        self._npc_bodies_moved = sorted(set(moved))
        return self._npc_bodies_moved

    # ==================================================================
    #  NPC 自由生活（第73轮）
    #  ------------------------------------------------------------------
    #  用户口径（逐字）：
    #    「我希望他们是**生活在这**而不是我走到哪他们加载到哪……
    #      我希望他们是**能对场景有反应**的，比如 sans 来到 oneshot 会吐槽，
    #      这地方真黑之类的话……之后不同世界的人一开始也不认识，所以他们也是
    #      **循序渐进的熟悉起来**，当然，**面对不同版本的自己熟悉的会更快**」
    #
    #  交付边界（★ 先说清楚，免得把"接口就位"说成"已经能用了"）：
    #    ✅ 已接线：场景反应（进 prompt）/ 熟络度（同场共处上涨 + 进 prompt）/
    #               传话（说完一句就告诉同场的另一位）/ 纯 NPC 自主开口（零模型）
    #    ⏳ 未接线（如实登记 `not_yet`）：**主线 NPC 自主开口** —— 那需要把"无用户发起的
    #       生成"接进现有异步回调链，且必须与用户请求排队（CPU-only 单并发），留给下一轮。
    # ==================================================================

    def _npc_production_of(self, npc_id):
        """作品前缀（`ut`/`hy`/`ot`/`os`/`dr`）。★ 判据只有一处 = `npc_system.production_of`。"""
        try:
            return npc_system_mod.production_of(npc_id)
        except Exception:
            return ''

    def _npc_seed_lookup(self, a, b):
        """两人**初见**时的熟络度初值 —— 落用户那句「面对不同版本的自己熟悉的会更快」。

        · 同一角色的不同 AU 版本（`ut_sans` ↔ `ot_sans`）→ `SEED_SAME_AU_TWIN` 0.55
        · 同一作品内的人                                  → `SEED_SAME_PRODUCTION` 0.30
        · 跨作品陌生人                                    → `SEED_STRANGER` 0.0

        ★★ 为什么 AU 判定读的是**契约**（`_crossworld.json#twin_groups`）而不是在这里
          再配一次对：契约里已经写死了"谁是另一个版本的我 / 谁只是同名" ——
          Toriel 组 3 人里**只有** `ut_toriel`/`ot_toriel` 是 AU，`toriel`（Deltarune）
          只是同名。在这里重配一次就会有两个真相，而且很容易把"同名"错当成"另一个我"，
          白送 0.55 的起手熟络度（正是用户那句话被读歪的地方）。
        """
        try:
            if frozenset((a, b)) in self._npc_au_pairs:
                return npc_life_mod.SEED_SAME_AU_TWIN
            pa, pb = self._npc_production_of(a), self._npc_production_of(b)
            if pa and pa == pb:
                return npc_life_mod.SEED_SAME_PRODUCTION
        except Exception:
            pass
        return npc_life_mod.SEED_STRANGER

    def _npc_life_gate(self):
        """「现在允不允许 NPC 自己开口」—— 一句话：**先让路给用户**。

        ★ 为什么必须有这道闸：模型是 **CPU-only、单实例、`NUM_PARALLEL=1`**
          （第57轮实测「并发 = 排队」）。NPC 自发闲聊若跟用户对话抢队，
          用户就得等几十秒。⇒ 只要"正在跟用户说话 / 模型忙 / 宠物在施法·躲猫猫·拖拽"
          一律不自主开口。
        ★ 返回 `False` **不推进轮转**（`LifeLoop` 的语义）：被让路的是这一次机会，
          不是这个人 —— 下一拍还是他。
        """
        if not RalseiPet.NPC_LIFE_ENABLED:
            return False
        if getattr(self, '_npc_talking', None):
            return False
        if getattr(self, '_ai_inflight', 0):
            return False
        if getattr(self, '_event_speaking', False):
            return False
        if getattr(self, '_busy', False):
            return False
        if getattr(self, 'is_sleeping', False) or getattr(self, 'is_dragging', False):
            return False
        return True

    def _npc_life_ids(self):
        """此刻在场的人。★ 判据**只有一处** = `self.npc_bodies`（已过世界门控 + 站位表）。

        ⚠️ 这里**刻意不**再查一遍 `_npc_scene_roster()`：那会变成"同一份规则两处算"
          （本项目最贵的坑）—— `npc_bodies` 就是 `_npc_scene_roster` 播下来的结果。
        """
        bodies = getattr(self, 'npc_bodies', None)
        if not bodies:
            return []
        return sorted(nid for nid in bodies.keys() if isinstance(nid, str) and nid)

    def _npc_plain_ids(self, ids):
        """把在场的人筛成**纯 NPC**（走内置对话池、零模型成本）。

        ★ 第86轮起：主线 NPC **也能**自发开口（走 7B，见 `_npc_main_ids`），
          所以这里不再是"唯一能开口的一类"，而是"**零成本那一类**"。
          但节拍器仍**先**给纯 NPC 机会（免费），轮空时才轮到主线（要花模型）。
        """
        reg = self.npc_registry
        if reg is None:
            return []
        out = []
        for nid in ids:
            try:
                npc = reg.get(nid)
                if npc is not None and npc.tier == npc_system_mod.NpcTier.PLAIN \
                        and reg.lines_of(nid):
                    out.append(nid)
            except Exception:
                continue
        return out

    def _npc_main_ids(self, ids):
        """把在场的人筛成**主线 NPC**（走 7B 生成，第86轮接入自主开口）。

        ★ 三条准入（**缺一不选**，宁可留白也不选一个发不出声的人）：
          ① 不是 `PLAIN` 档（纯 NPC 走内置池，见 `_npc_plain_ids`）；
          ② **装了人设**（`npc_persona_of`）—— 没设定的人不许开口，更不许借别人的；
          ③ 模型可用（`_npc_ai_available`）—— 没模型时选了也会一路 `abort` 拖死生活线。
        """
        reg = self.npc_registry
        if reg is None:
            return []
        try:
            if not self._npc_ai_available():
                return []
        except Exception:
            return []
        out = []
        for nid in ids:
            try:
                npc = reg.get(nid)
                if npc is None or npc.tier == npc_system_mod.NpcTier.PLAIN:
                    continue
                if not self.npc_persona_of(nid):
                    continue
                out.append(nid)
            except Exception:
                continue
        return out

    def _npc_say_line(self, npc_id, text):
        """让某个 NPC 用**自己的身份**说一句（走全项目唯一的气泡出口）。

        ⚠️ 走 `dialogue_ui.add_dialogue(<npc_id>, ...)` 而不是 `_item_menu_message()`：
          后者的说话人**写死是 ralsei**，NPC 的闲聊挂上去会变成"雷尔赛在替苏西说话"
          ——正是用户最怕的串味。这里第一条参数就是说话人 id。
        """
        if not text:
            return False
        try:
            self.dialogue_ui.add_dialogue(npc_id, text, 'normal')
            self.dialogue_ui.show_dialogue()
            return True
        except Exception as e:
            _log.debug('NPC %s 自主台词显示异常（已忽略）: %s', npc_id, e)
            return False

    def _npc_scene_text(self):
        """推断场景特质用的文本 = **当前场景 id**（+ 站位表里的场景内部名）。

        ★ 为什么是"id + 内部名"这两处：`npc_life` 不读文件（零依赖），它要的只是
          **一段文本**；"这段文本从哪来"是宿主的事。id 里带着 `dark_world` / `castle_town`
          / `cyber_city` 这些真信息，够用了。
        """
        parts = []
        try:
            sid = self._npc_scene_id()
            if isinstance(sid, str) and sid:
                parts.append(sid)
        except Exception:
            pass
        try:
            book = getattr(self, 'npc_placement', None)
            if book is not None:
                raw = getattr(book, 'room_raw', None)
                if isinstance(raw, str) and raw:
                    parts.append(raw)
        except Exception:
            pass
        return ' '.join(parts)

    def _npc_life_blocks(self, npc_id):
        """NPC 的「自由生活」三块提示 —— ★ **只加"他此刻能看见的"，不加"他是谁"**。

        ① 【你周围】= 场景特质（用户那句"能对场景有反应"的落地）。
        ② 【此刻这里还有谁】= 在场其他人 + **粗方位**（第86轮 B6 的在场者感知）。
        ③ 【你认识谁】= 熟络到一定程度的**显示名**，带一句"多熟"。

        ★★ **绝不注入**的东西（用户口径「怪物们之间**没有身份标识**说你是哪个世界观的，
          所以那需要自己判断」）：对方的**作品归属 / 版本 / npc id / 人设**——
          `_crossworld.json#identity_blind.not_injected` 已把这条列死。这里只给
          "他叫什么、大概在哪个方位、你跟他熟到什么程度"，**怎么判断来人是谁，是 NPC 自己的事**。
        """
        out = []
        try:
            traits = npc_life_mod.scene_traits(self._npc_scene_text())
            hint = npc_life_mod.trait_hint(traits)
            if hint:
                out.append(hint)
        except Exception as e:
            _log.debug('场景特质分片失败（已忽略）: %s', e)
        # ---- ② 在场者感知（★ 第86轮；位置真源 = npc_bodies 的屏幕中心）----
        try:
            others = [n for n in self._npc_life_ids() if n != npc_id]
            if others:
                pos = self._npc_relative_positions(npc_id, others)
                ph = npc_life_mod.presence_hint(
                    npc_id, others, positions=pos,
                    label_of=self._npc_display_label)
                if ph:
                    out.append(ph)
        except Exception as e:
            _log.debug('在场者感知分片失败（已忽略）: %s', e)
        try:
            if self.npc_bonds is not None:
                known = self.npc_bonds.known(npc_id)
                if known:
                    names = [self._npc_display_label(nid) for nid in known[:6]]
                    names = [n for n in names if n]
                    if names:
                        out.append('【你认识谁】你已经比较熟的有：' + '、'.join(names)
                                   + '。（熟不熟看相处，不看别的 —— 对方是哪里来的、'
                                     '是哪个版本，你并不知道，也别去猜。）')
        except Exception as e:
            _log.debug('熟络度分片失败（已忽略）: %s', e)
        return '\n\n'.join(out)

    def _npc_display_label(self, npc_id):
        """NPC 的**显示名**（中文名优先）。取不到 ⇒ `''`（**不猜、不退回 id**）。

        ★ 为什么**不**退回 id：id 里带着 `ut_` / `ch1.` / 作品前缀，等于把
          "他是哪部作品的"直接泄给模型 —— 正是 `identity_blind.not_injected` 要挡的。
        """
        reg = self.npc_registry
        if reg is None:
            return ''
        try:
            npc = reg.get(npc_id)
        except Exception:
            return ''
        if npc is None:
            return ''
        try:
            return npc_persona_mod.speaker_label(
                getattr(npc, 'name', None), getattr(npc, 'name_cn', None)) or ''
        except Exception:
            return ''

    def _npc_relative_positions(self, npc_id, others):
        """`{other_id: (dx, dy)}` —— 各人**相对 `npc_id`** 的偏移（屏幕坐标）。

        ★ 真源 = `self.npc_bodies[<id>]` 的屏幕中心；拿不到就**跳过那个人**
          （`presence_hint` 在无位置时**不编方位**，而不是猜）。
        ★ 单位是像素、**仅供分档**（`where_of` 会粗化）—— 不给模型精确坐标。
        """
        out = {}
        base = self._npc_body_center(npc_id)
        if base is None:
            return out
        for oid in others:
            c = self._npc_body_center(oid)
            if c is None:
                continue
            out[oid] = (c[0] - base[0], c[1] - base[1])
        return out

    def _npc_body_center(self, npc_id):
        """某个 NPC 身体的**屏幕中心** `(x, y)`；拿不到 ⇒ `None`（不猜）。"""
        bodies = getattr(self, 'npc_bodies', None)
        if not bodies:
            return None
        try:
            b = bodies.get(npc_id)
        except Exception:
            return None
        if b is None:
            return None
        c = getattr(b, 'center', None)
        if callable(c):
            try:
                v = c()
                if isinstance(v, (tuple, list)) and len(v) >= 2:
                    return (float(v[0]), float(v[1]))
            except Exception:
                pass
        r = getattr(b, 'rect', None)
        if r is not None:
            try:
                cc = r.center()
                return (float(cc.x()), float(cc.y()))
            except Exception:
                pass
        return None

    def _npc_life_tick(self, dt):
        """第73/86轮：NPC「自由生活」每帧推进。→ 本帧真正开了口的 NPC id 列表。

        挂在与 `npc_placement_tick` **同一处**（`update_movement` 的早退分支之前）：
        他们是独立实体，宠物睡着 / 施法 / 躲猫猫时照样该过日子。

        本函数做三件事，**前两件不花一分钱**：

          1. **熟络度**：在场两两之间缓慢上涨（纯算）。★ 涨幅按 dt 折算成"满速 30fps 的
             等价帧数"，所以挂 10fps 还是 30fps 定时器，涨得一样快（不然换定时器就会
             悄悄改变数值 —— 那是"同一份规则被两处算"的另一种模样）。
          2. **纯 NPC 自主开口**：从**内置对话池**取一句（**零模型成本**，用户第49轮口径
             「纯 npc……就用 4~10 句内置对话就好」），记进他自己的记忆，再**传话**给同场
             另一位（带署名）。说过的句子不重复，一圈说完自动开新圈。
          3. **主线 NPC 自主开口（★ 第86轮接入）**：纯 NPC 轮空时才轮到主线；
             走 `npc_speak` 的**同一条 7B 路径**（不是另起一条），完全靠 system 里的
             【你周围】/【此刻这里还有谁】/【你认识谁】做判断 —— **没有硬编码优先级、
             没有固定台词**（用户口径："继续当前话题 / 转向新来的人 / 主动搭话"由模型定）。

        ★★ 让路闸（`_npc_life_gate`）两支**共用**：用户一开口 / 模型忙 / 宠物在施法，
          两支都停手 —— 保证"NPC 闲聊绝不跟用户抢那唯一的模型实例"。
        """
        if not RalseiPet.NPC_LIFE_ENABLED:
            return []
        ids = self._npc_life_ids()
        if len(ids) < npc_life_mod.MIN_TALKERS:
            return []
        # ---- 1) 熟络度：同处一室，缓慢上涨 ----
        if self.npc_bonds is not None:
            try:
                frames = max(0.0, min(float(dt), 0.1)) * 30.0     # 等价 30fps 帧数
            except Exception:
                frames = 0.0
            if frames > 0:
                for k in range(len(ids)):
                    for m in range(k + 1, len(ids)):
                        try:
                            self.npc_bonds.tick(ids[k], ids[m],
                                                amount=npc_life_mod.GAIN_PER_TICK * frames)
                        except Exception:
                            pass
        # ---- 2) 自主开口节拍 ----
        loop = self.npc_life
        if loop is None:
            return []
        # 换场景 ⇒ 重新开一轮（不然 `max_turns` 用完就再也不开口了）。
        try:
            sid = self._npc_scene_id()
        except Exception:
            sid = None
        if getattr(self, '_npc_life_scene', None) != sid:
            self._npc_life_scene = sid
            loop.reset(keep_turns=False)
        try:
            now = time.monotonic()
        except Exception:
            return []
        # ---- 2a) 先给**纯 NPC**机会（零成本）----
        plain = self._npc_plain_ids(ids)
        if len(plain) >= npc_life_mod.MIN_TALKERS:
            speaker = loop.tick(now, plain)
            if speaker is not None:
                return self._npc_life_speak_plain(loop, speaker, ids, now)
        # ---- 2b) 轮到**主线 NPC**（要花模型）★ 第86轮新增 ----
        return self._npc_life_speak_main(loop, ids, now)

    def _npc_life_speak_plain(self, loop, speaker, ids, now):
        """纯 NPC 开口：内置池取一句 + 落记忆 + 传话 + 显示。**零模型成本**。"""
        try:
            lines = self.npc_registry.lines_of(speaker)
        except Exception:
            lines = []
        used = self._npc_line_used.get(speaker)
        text, used_new = npc_life_mod.pick_line(lines, used)
        if not text:
            # 池子空 —— 不该发生（`_npc_plain_ids` 已保证非空），如实解锁并记账
            loop.abort(now)
            return []
        self._npc_line_used[speaker] = used_new
        # ---- 落他自己的记忆（★ `who` 是他自己：这是"他自己说的"，不是用户说的）----
        try:
            if self.npc_memory is not None:
                self.npc_memory.remember(speaker, text, who=speaker)
        except Exception as e:
            _log.debug('NPC %s 自主台词落记忆异常（已忽略）: %s', speaker, e)
        # ---- 传话给同场的另一位（★ 显式、带署名；不违反"一角色一份物理分开"）----
        others = [n for n in ids if n != speaker]
        if others and self.npc_memory is not None:
            try:
                npc_life_mod.transmit(self.npc_memory, speaker, others[0])
            except Exception as e:
                _log.debug('传话 %s → %s 异常（已忽略）: %s', speaker, others[0], e)
            if self.npc_bonds is not None:
                try:
                    self.npc_bonds.meet(speaker, others[0])
                except Exception:
                    pass
        # ---- 显示 + 收束 ----
        self._npc_say_line(speaker, text)
        loop.finish(now, speaker)
        return [speaker]

    def _npc_life_speak_main(self, loop, ids, now):
        """主线 NPC 自主开口（第86轮）：走 `npc_speak` 的**同一条 7B 路径**。

        ★★★ 三条纪律（每一条都有对应的回归判据，`check86`）：

          ① **不另起一条生成路径**：句子的产生完全复用 `npc_speak()`（= `@某人` 那条），
             所以"人设护栏 / 历史 / 让路 / 模型闸"全部**同一处生效** ——
             否则就是"同一份规则两处算"。
          ② **失败必解锁 + 反活锁**：任何拒绝（模型不可用 / 人设缺失 / 发起异常）
             都必须 `loop.abort(now)`，否则节拍器会永久卡在 busy（第73轮那条不变量）。
          ③ **发出去了才 `finish`**：`npc_speak` 返回 `False` = **明确拒绝**（它已回调
             `on_reply(None)`）⇒ 不能当成"说过话了"，要 `abort`。

        ★ 节流：主线开口的**间隔**比纯 NPC 长得多（7B 一次 ≈ 秒级到十几秒），
          用 `_npc_main_last` 单独限流，避免"两个主线 NPC 互相刷屏把模型占满"。
        """
        mains = self._npc_main_ids(ids)
        if len(mains) < npc_life_mod.MIN_TALKERS:
            return []
        # ★ 主线专属限流（与纯 NPC 的 min_gap 分开，见 docstring）
        last = getattr(self, '_npc_main_last', 0.0)
        gap = getattr(RalseiPet, 'NPC_MAIN_TALK_GAP', 45.0)
        if last and (now - last) < gap:
            return []
        speaker = loop.tick(now, mains)
        if speaker is None:
            return []
        sent = False
        _text = ''

        def _on_reply(r):
            # ★ 只落"他真的说了什么"这件事 —— 生成失败（None）时**不记空话**。
            nonlocal _text
            if isinstance(r, str) and r.strip():
                _text = r.strip()

        try:
            sent = self.npc_speak(speaker, '', _on_reply)
        except Exception as e:
            _log.debug('NPC %s 自主开口发起异常（已忽略）: %s', speaker, e)
            sent = False
        if not sent:
            # 明确拒绝（模型不可用 / 人设缺失…）⇒ **必须解锁**，否则节拍器卡死。
            loop.abort(now)
            return []
        self._npc_main_last = now
        others = [n for n in ids if n != speaker]
        if others and self.npc_memory is not None:
            try:
                npc_life_mod.transmit(self.npc_memory, speaker, others[0])
            except Exception as e:
                _log.debug('传话 %s → %s 异常（已忽略）: %s', speaker, others[0], e)
            if self.npc_bonds is not None:
                try:
                    self.npc_bonds.meet(speaker, others[0])
                except Exception:
                    pass
        loop.finish(now, speaker)
        return [speaker]

    # ==================================================================
    #  NPC 自主移动（★ 第79轮 · 层2 驻留层接线）
    #  ------------------------------------------------------------------
    #  用户口径（逐字，第77轮）：
    #    「他们生活是生活，我和他们只是朋友，而不是主导人，也就是**不会因为缺少
    #      一个人哪怕是我他们就不生活了**」「**去哪？找谁？干什么？生活规划**这类
    #      的事也是由**各自的 AI 决定**」
    #
    #  ★★★ 为什么必须独立于"场景切换"：
    #    此前 `_npc_seed_bodies()` **只在启动（`:2182`）与切场景（`:2513`）时**被调
    #    ⇒ NPC 是"当前场景的装饰"，**用户不动，世界就冻住** —— 与用户口径正相反。
    #    本函数挂在 30s 节拍上（`NPC_AUTONOMOUS_TICK`），**与宠物位置、场景切换都无关**。
    #
    #  ★ 两个开关各管一半（别混）：
    #    · `NPC_LIFE_ENABLED`   —— 管"他们会不会自己**开口**"（第73轮）；
    #    · `NPC_AUTONOMOUS_MOVE` —— 管"他们会不会自己**挪窝**"（第79轮建；
    #      第80轮**按用户裁决默认 True**）。
    # ==================================================================

    def _npc_roam_tick(self, now=None):
        """推进"自主移动"一节拍（默认 30s）。→ `{'decided', 'expired', 'moved'}`。

        ★★ 三件必须同时成立，缺一不可：
          ① `NPC_AUTONOMOUS_MOVE` 开（第80轮起**默认开**；关 ⇒ 本函数立刻返回，零副作用）；
          ② `npc_roam` 就位（建失败 ⇒ 退化为"全体回站位表"，只记 debug）；
          ③ 距上次推进 ≥ `NPC_AUTONOMOUS_TICK`（生活决策不需要每帧算）。

        ★ 决策**由各自的 AI 定**（L3）：`decide_fn` 把 `npc_intent.decide()` 包一层 ——
          本模块（`npc_roam`）**不 import** `npc_intent`（零依赖纪律），决策是**注入**的。
        ★ 就寝（层3）同理注入 `sleep_fn=self._npc_roam_sleep`（真源
          `npc_intent.choose_sleep_scene`，**取代**旧常量 `BEDTIME_HOME_SCENE`）。
        """
        if not RalseiPet.NPC_AUTONOMOUS_MOVE:
            return {'decided': [], 'expired': [], 'moved': []}
        roam = getattr(self, 'npc_roam', None)
        if roam is None or not roam.enabled:
            return {'decided': [], 'expired': [], 'moved': []}
        if now is None:
            now = time.time()
        try:
            now = float(now)
        except (TypeError, ValueError):
            return {'decided': [], 'expired': [], 'moved': []}
        # ---- 节拍：不到点不推（30s 一次）----
        last = getattr(self, '_npc_roam_last_tick', 0.0) or 0.0
        try:
            if now - float(last) < RalseiPet.NPC_AUTONOMOUS_TICK:
                return {'decided': [], 'expired': [], 'moved': []}
        except (TypeError, ValueError):
            pass
        self._npc_roam_last_tick = now

        book = getattr(self, 'npc_placement', None)
        if book is None:
            return {'decided': [], 'expired': [], 'moved': []}
        try:
            reach = self._npc_roam_reachable()
            out = npc_roam_mod.step(
                roam, now,
                roster=book.ids(),
                decide_fn=self._npc_roam_decide,
                traits_of=self._npc_roam_traits,
                familiar_of=self._npc_roam_familiar,
                home_of=lambda nid: book.scene_of(nid),
                reachable_of=lambda nid: reach,
                friends_of=self._npc_roam_friends,
                sleep_fn=self._npc_roam_sleep,
            )
        except Exception as e:
            _log.debug('NPC 自主移动推进异常（本节拍跳过）: %s', e)
            return {'decided': [], 'expired': [], 'moved': []}
        # ---- 有人换了地方 ⇒ **必须重建身体**（否则"人到了、画还在旧场景"）----
        moved = out.get('moved') or []
        expired = out.get('expired') or []
        if moved or expired:
            try:
                # ★ 重建的是**当前场景**的身体：驻留变化会改变"当前场景该有谁"。
                self._npc_seed_bodies(self._npc_scene_id())
            except Exception as e:
                _log.debug('自主移动后重建站位异常（已忽略）: %s', e)
            for nid, dest in moved:
                _log.info('NPC %s 自己挪到了 %s', nid, dest)
        # ---- ★★★ 第81轮（层4 存档）：本拍若真发生变化 ⇒ 把生活档案落盘 ----
        # ★ 只在 `moved`/`expired` **非空**时写：世界没动就没必要写盘
        #   （E 盘是 exFAT，无谓写会磨损；写盘本身还有节流）。
        # ★ 落盘失败**只记 debug**，绝不影响桌宠运行（与 `_ghost_save` 同规）。
        if moved or expired:
            self._npc_plan_save()
        return out

    # ---------------------------------------------------------------- 层4 存档
    def _npc_plan_file(self):
        """生活档案的落盘路径（`data_store` 唯一入口；取不到 ⇒ `None` = 退内存态）。

        ⚠️ 与 `_make_relationship()` / `_ghost_state_path()` 同一条纪律：
          **不在底层模块里 import data_store**（初始化环，本项目栽过 4 次），
          路径一律由**调用方注入**，这里只当那个调用方。
        """
        try:
            import data_store
            return data_store.app_file(npc_plan_store_mod.FILENAME)
        except Exception as e:
            _log.debug('生活档案落盘路径不可用（退内存态）: %s', e)
            return None

    def _npc_plan_save(self, force=False):
        """把生活档案（驻留表 + 每人规划）写回盘。→ `bool`。**绝不抛**。

        ★ 节流：默认 `NPC_PLAN_SAVE_EVERY` 秒内最多写一次（`force=True` 绕过）
          —— 与 `_ghost_save` 同一形状，避免"每拍都写盘"。
        ★ `Book.to_dict()` 已对 `history` 做二次兜底（`MAX_HISTORY`），
          不会因为外部塞进来一本超大的书把 E 盘写爆。
        """
        book = getattr(self, 'npc_plan_book', None)
        path = getattr(self, '_npc_plan_path', None)
        if book is None or not path:
            return False
        now = time.time()
        last = getattr(self, '_npc_plan_last_save', 0.0) or 0.0
        if not force and (now - last) < RalseiPet.NPC_PLAN_SAVE_EVERY:
            return False
        # ★ 落盘前**把当前 `roam` 同步进书**：`_npc_roam_tick` 推的是 `self.npc_roam`，
        #   书里那份可能还是启动时灌进去的 ⇒ 不同步就会"改了世界却存了旧的"。
        roam = getattr(self, 'npc_roam', None)
        if roam is not None:
            book.roam = roam
        try:
            ok = bool(npc_plan_store_mod.save(path, book))
        except Exception as e:
            _log.debug('生活档案落盘失败（已忽略）: %s', e)
            ok = False
        if ok:
            self._npc_plan_last_save = now
        return ok

    def _npc_roam_reachable(self):
        """他"能去哪"—— **单一真源** = `scene_controller.reachable_destinations()`。

        ★ 为什么不当场重算一份：可达性本来就由门/寻路决定，那边已有唯一实现
          （第76轮 R0 建的）；这里再算一份就是"同一份规则两处算"。
        """
        sc = getattr(self, 'scene', None)
        if sc is None or not hasattr(sc, 'reachable_destinations'):
            return []
        try:
            return [d.get('scene_id') for d in sc.reachable_destinations(limit=64)
                    if isinstance(d, dict) and d.get('scene_id')]
        except Exception:
            return []

    def _npc_roam_traits(self, npc_id):
        """该 NPC 所在场景的**特质**（喂 `npc_intent.decide` 的 `traits`）。

        ★ 单一真源 = `npc_life.scene_traits`（第73轮建的）；取不到 ⇒ `None`（**不猜**）。
        """
        try:
            sid = self._npc_roam_scene_of(npc_id)
            if not sid:
                return None
            f = getattr(npc_life_mod, 'scene_traits', None)
            if f is None:
                return None
            return list(f(sid) or ())
        except Exception:
            return None

    def _npc_roam_familiar(self, npc_id):
        """他与"我"（当前主控角色）的熟络度？—— 这里给 **0.0**（不编）。

        ★ 为什么不用 `npc_bonds`：`Bonds` 是 **NPC↔NPC 两两**的熟络度，
          没有"NPC↔用户/主角"这一维（第73轮口径：那是"他自己的记忆"，不是数值）。
          ⇒ 如实给 0.0（让 `decide` 的"熟人加成"不生效），**不编造**一个数。
        """
        return 0.0

    def _npc_roam_friends(self, npc_id):
        """他"认识谁、那些人住哪" → `[(id, familiar, scene_id), ...]`。

        ★ 与 `decide()` 的 `friends`（`[(id, familiar)]`）**多一个元素**：睡觉需要**地点**
          （`npc_intent.choose_sleep_scene` 的口径）。
        ★ 熟人越熟越可能被找上门；"他住哪"取**静态归属**（`_placement.json`）——
          不取驻留表（不然会追着一个"刚好出门了"的人满地图跑）。
        """
        out = []
        try:
            bonds = getattr(self, 'npc_bonds', None)
            book = getattr(self, 'npc_placement', None)
            reg = self.npc_registry
            if reg is None:
                return []
            for other in reg.all():
                oid = getattr(other, 'id', None)
                if not oid or oid == npc_id:
                    continue
                fam = 0.0
                if bonds is not None:
                    try:
                        fam = float(bonds.familiarity(npc_id, oid) or 0.0)
                    except Exception:
                        fam = 0.0
                if fam <= 0.0:
                    continue
                scene = book.scene_of(oid) if book is not None else None
                if not scene:
                    continue
                out.append((oid, fam, scene))
        except Exception:
            return []
        return out

    def _npc_roam_scene_of(self, npc_id):
        """他现在在哪（**驻留优先，回落静态归属** —— 与 `_npc_scene_roster` 同一口径）。"""
        roam = getattr(self, 'npc_roam', None)
        here = roam.resident_of(npc_id) if roam is not None else None
        if here:
            return here
        book = getattr(self, 'npc_placement', None)
        return book.scene_of(npc_id) if book is not None else None

    def _npc_roam_decide(self, npc_id, now, *, traits=None, familiar=0.0,
                         home=None, reachable=None, friends=None):
        """**询问他自己的 AI**：这一拍去哪（← 用户口径 L3）。

        ★ 决策真源 = `npc_intent.decide()`（层1）；这里只负责**把宿主的事实喂进去**：
          - `home`      = 他的静态归属（`_placement.json`）；
          - `reachable` = `scene_controller.reachable_destinations()`；
          - `friends`   = `npc_bonds` 里熟络度 > 0 的人 + 他们住哪。

        ★★ 第81轮（层4）：`last` 不再硬编码 `None` —— 改从**生活档案**里取他上一次的
          意图（`Plan.intent`），并把本次结果 `note()` 回书里。这是 L5「人味」的核心
          一环：**"上次去了哪"会影响这次去哪**（`decide` 的 `last` 入参）。
          在层4 之前这个值永远是 `None` ⇒ 决策是**无记忆**的。

        ★★ 注意签名里**没有** pet/user/player —— 与 `npc_roam.step` 的纪律一致（L2）。
        """
        book = getattr(self, 'npc_plan_book', None)
        plan = None
        last_intent = None
        if book is not None:
            try:
                plan = book.plan_of(npc_id)
                last_intent = getattr(plan, 'intent', None)
            except Exception as e:
                _log.debug('生活档案取规划异常（本拍按无记忆决策）: %s', e)
                plan = None
                last_intent = None
        it = npc_intent_mod.decide(
            npc_id, now,
            traits=traits, familiar=familiar, home=home,
            reachable=reachable,
            friends=[(i, f) for i, f, _s in (friends or ())],
            favorites=None,
            last=last_intent,
        )
        # ★ 记回档案：`note()` 自带 history 有界（keep=12），不会无限长。
        if plan is not None:
            try:
                plan.note(it)
            except Exception as e:
                _log.debug('生活档案记规划异常（已忽略）: %s', e)
        return it

    def _npc_roam_sleep(self, npc_id, now, *, home=None, friends=None,
                        reachable=None, last_sleep=None):
        """**今晚睡哪**（层3 就寝决策器，注入给 `npc_roam.step(sleep_fn=...)`）。

        ★★ 与旧口径的分工（**用户裁决 ③「废除」**）：
          - `BEDTIME_HOME_SCENE = 'desktop'`（常量） —— 服务的是**桌宠本人**
            （`go_to_bed()` 读它；他住在桌面）。**NPC 完全不适用**，旧口径已废弃。
          - **本函数** —— 逐 NPC 算「今晚睡哪」，真源 = `npc_intent.choose_sleep_scene`
            （L4：**不硬性回家**，熟人够熟就可能**睡朋友家**）。

        ★ `friends` 这里已经在 `_npc_roam_friends` 里带了**第三个元素（他住哪）**，
          正是 `choose_sleep_scene` 需要的形状 —— 不再转换（避免两处算同一份规则）。

        ★★ 第81轮（层4）：`last_sleep` 若调用方没给（**现状：`npc_roam.step` 不给**），
          就从**生活档案**里取他昨晚睡哪 —— 这才让"连睡同一处 ×0.6 降权"真正拿到值。
          决策出了结果 ⇒ 立刻 `note_sleep()` 记回档案（本拍落盘时一并写下去）。
        """
        book = getattr(self, 'npc_plan_book', None)
        if last_sleep is None and book is not None:
            try:
                last_sleep = book.last_sleep_of(npc_id)
            except Exception as e:
                _log.debug('生活档案取 last_sleep 异常（本拍按无记忆）: %s', e)
                last_sleep = None
        try:
            scene, why = npc_intent_mod.choose_sleep_scene(
                npc_id, now, home=home, friends=friends,
                reachable=reachable, last_sleep=last_sleep)
        except Exception as e:
            _log.debug('NPC 就寝决策异常（本拍不作决策）: %s', e)
            return None, 'error'
        # ★ 记住"今晚睡哪"（供**下一次**决策降权）。只在真出了地点时记 —— `None` 是
        #   "哪儿也去不了"，不是"睡在空处"，记进去会污染降权（那是另一个事实）。
        if scene and book is not None and why not in ('nowhere', 'error'):
            try:
                book.note_sleep(npc_id, scene)
            except Exception as e:
                _log.debug('生活档案记就寝异常（已忽略）: %s', e)
        return scene, why

    def _npc_menu_message(self, text):
        """往用户能看见的地方说一句（复用道具菜单那条通道；没有就只记日志）。

        ⚠️ 为什么复用这条通道而不是自己造一个：本项目已经有"宠物能对用户说一句
           轻量提示"的成例（`_item_menu_message`），再造一个就会出现两套提示
           互相盖住（第48轮踩过）。没有它时**降级为纯日志**，不抛。
        """
        if not text:
            return False
        try:
            fn = getattr(self, '_item_menu_message', None)
            if callable(fn):
                return bool(fn(text))
        except Exception as e:
            _log.debug('NPC 提示显示异常（已忽略）: %s', e)
        _log.info('NPC：%s', text)
        return False

    # ==================================================================
    #  道具 / 背包 / S 键菜单（第48轮）
    # ==================================================================
    def init_item_systems(self):
        """建道具目录 + 两个袋子 + S 键菜单，并把"场景切换"接上道具域。

        失败语义：**任何一步失败都只降级、不抛出**（与 search_summarizer /
        relationship 同一条纪律：非关键路径不许让桌宠起不来）。
        降级后果写进日志，且 `self.inventory is None` 时所有入口方法都**直接返回**，
        不会半死不活地"点得动但没反应"。

        接线清单（少一项就等于没做，本项目最贵的坑）：
          1. 道具表（`assets/items/`）         → `self.item_catalog`
          2. 两个袋子 + 垃圾团 + 当前域         → `self.inventory`
          3. S 键菜单状态机 + 浮层 UI           → `self.item_menu` / `self.item_menu_ui`
          4. **场景切换钩子**（切场景 ⇒ 道具域跟着换 ⇒ 回光世界时暗道具变垃圾）
          5. **全局热键**（Ctrl+Alt+S；裸 S 走窗口焦点，见 keyPressEvent）
          6. 当前场景的**可交互物**（存档点 / 暗之泉 / …）
        """
        # 先全部预声明成 None/空 —— 中途任何一步失败，宿主也不缺属性
        # （本项目踩过"状态只在成功路径上创建"的坑：失败后别处 getattr 就炸）。
        self.item_catalog = None
        self.inventory = None
        self.item_menu = None
        self.item_menu_ui = None
        self.item_props = []            # 当前场景的可交互物
        self.interact_bus = None
        self._scene_switch_hooks = []
        self._item_hotkey_done = ()
        self._item_hotkey_bad = ()
        self._item_last_frame = None
        self._item_menu_toggle_at = 0.0     #: 开关去抖用（见 toggle_item_menu）

        try:
            self.item_catalog = item_system_mod.load_catalog(item_system_mod.assets_dir())
            scene = self.__dict__.get('_scene_state')
            chapter = getattr(scene, 'chapter_id', None) or 'ch1'
            # ⚠️ 启动兜底：**这一步不是判据**。判据永远来自 `_worlds.json`
            #    （`scene_system.world_of_scene`）；只有在"连当前场景都还没有"时
            #    才需要一个初值，取暗世界并**记一条日志**，不静默。
            world = scene_system_mod.world_of_scene(scene) or item_system_mod.WORLD_DARK
            if scene_system_mod.world_of_scene(scene) is None:
                _log.info('启动时判不出明/暗世界（无当前场景）⇒ 道具域初值取暗世界（仅初值）')
            room_id = getattr(scene, 'original_room_id', None)
            sid = getattr(scene, 'scene_id', None)

            self.interact_bus = companion_mod.default_bus()
            self.inventory = item_system_mod.Inventory(
                self.item_catalog, chapter, world, sid, room_id)
            self.item_menu = item_menu_mod.build(self.inventory)
            self.item_menu_ui = item_menu_ui_mod.ItemMenuUI(
                self,
                menu=self.item_menu,
                on_message=self._item_menu_message,
                anchor=self._item_menu_anchor,
                # ★ 屏幕矩形必须用宿主的 `_virtual_screen_rect()`（契约①：
                #   `availableGeometry()` 只返主屏，多屏会算错）。
                screen_rect=self._virtual_screen_rect,
            )
            # 4) 场景切换钩子 —— `SceneController.switch()` 里会调它。
            self._scene_switch_hooks = [self._on_scene_switched_items]
            # 6) 当前场景的可交互物（首次）
            self._rebuild_item_props()
        except Exception:
            _log.exception('道具系统初始化失败（S 键菜单与道具将不可用，宠物照常运行）')
            return

        # 5) 全局热键。**务必带修饰键** —— 注册裸 's' 会系统级劫持 S 键，
        #    让用户在任何程序里都打不出那个字母（见 global_hotkey 的说明）。
        try:
            done, bad = global_hotkey_mod.install(self, {
                global_hotkey_mod.HOTKEY_DEFAULT_MENU: self.toggle_item_menu,
                global_hotkey_mod.HOTKEY_DEFAULT_INTERACT: self.interact_scene_prop,
                # ★ 第55轮：灵魂（SOUL）显示 / 收起。
                # ❗**必须挤在同一次 install() 里**，不能另起一次调用：
                #   `install()` 把新建的 `HotkeyFilter` 存进**单一引用槽**
                #   `widget._ralsei_hotkey_filter`，第二次调用会用新过滤器覆盖它，
                #   而旧过滤器**仍安装在 QApplication 上** ⇒ 被 GC 掉之后
                #   事件还会往它身上派发（悬空指针）。这是"不许调两次"的 API，
                #   不是代码风格问题。
                global_hotkey_mod.HOTKEY_DEFAULT_SOUL: self.toggle_soul,
            })
            self._item_hotkey_done, self._item_hotkey_bad = tuple(done), tuple(bad)
            if bad:
                _log.warning('全局热键未装上：%s ⇒ 仍可用"宠物窗口有焦点时按 S / E"', bad)
        except Exception:
            _log.exception('全局热键安装异常（已降级为窗口级 S / E 键）')

        _log.info('道具系统就绪：%s；可交互物 %d 个；热键=%s',
                  self.inventory.describe(), len(self.item_props),
                  self._item_hotkey_done)

    # ---------------------------------------------------------------- 域
    def _on_scene_switched_items(self, scene_id, scene):
        """★ 场景切换钩子：换域 ⇒ 回光世界时把暗世界道具变成垃圾团里的东西。

        由 `SceneController._fire_switch_hooks()` 调（钩子抛异常会被它吞掉并记日志，
        不影响切换本身，所以这里不必再包一层 try）。
        """
        if self.inventory is None:
            return
        chapter = getattr(scene, 'chapter_id', None) or self.inventory.chapter
        world = scene_system_mod.world_of_scene(scene)
        room_id = getattr(scene, 'original_room_id', None)
        if world is None:
            # ★ 判不出世界 ⇒ **保持不变**，而不是猜一个。
            #   猜错的代价是把玩家的道具冤枉地变成垃圾（不可逆，见 JUNK_IS_PERMANENT）。
            _log.warning('场景 %s 判不出明/暗世界 ⇒ 道具域保持不变（当前=%s）',
                         scene_id, self.inventory.world)
            world = self.inventory.world
        moved = self.inventory.enter(chapter, world, scene_id, room_id)
        if moved:
            # 用户口径的可观察点：回光世界时明确告诉他"东西变成垃圾团里的了"。
            self._item_menu_message('* 暗世界的东西在光下一件件散开了……变成垃圾团里的东西：%s'
                                    % '、'.join(moved))
        self._rebuild_item_props()
        self._refresh_item_menu()

    def _rebuild_item_props(self):
        """按当前场景重建可交互物（存档点 / 暗之泉 / 拾取）。

        ⚠️ 数据现状（第48轮实测，如实登记）：场景 objects 来自第44轮生成器，
        它只收录**有 sprite 的实例**，且第42轮普查只覆盖 146 个对象类 ⇒
        `obj_readable` / 宝箱 / 拾取 这些类**一件都没进数据**。
        `item_interact.PROP_CLASSES` 把这些类标注成 `in_data=False + gap`，
        `build_props()` 遇到它们会**跳过而不是造假可交互物**。数据补齐后不用改代码。
        """
        self.item_props = []
        if self.inventory is None:
            return
        scene = self.__dict__.get('_scene_state')
        if scene is None:
            return
        try:
            # ★ 第76轮 R0-2：把路由表交给 build_props —— 门（`obj_doorA~F`）
            #   靠它查出"通向哪"才会被建成可交互物。表不可用 ⇒ 门不建
            #   （其余可交互物**零行为变化**）。
            routes = None
            try:
                if self.scene is not None:
                    self.scene.load_routes()
                    routes = self.__dict__.get('_scene_routes')
            except Exception:
                _log.exception('路由表加载失败（门不可推，其余照常）')
            self.item_props = item_interact_mod.build_props(
                scene,
                self.inventory.chapter,
                self.inventory.world,
                present=self._item_prop_present,
                heal_all=self._item_heal_all,
                on_enter=self._item_enter_scene,
                inventory=self.inventory,
                bus=self.interact_bus,
                routes=routes,
            )
        except Exception:
            _log.exception('可交互物构建失败（本场景没有可交互物，不影响其它功能）')

    def _refresh_item_menu(self):
        """让已开着的菜单立刻反映新状态（换场景后道具列表可能变了/菜单该关掉）。"""
        if self.item_menu is None or self.item_menu_ui is None:
            return
        try:
            if self.item_menu_ui.is_open():
                self.item_menu_ui.show_frame(self.item_menu.frame())
        except Exception:
            _log.exception('菜单刷新失败（忽略）')

    # ---------------------------------------------------------------- 入口
    def toggle_item_menu(self):
        """开/关 S 键菜单。**全局热键与窗口按键都走这里**（单一入口）。

        为什么单一入口：热键回调和 Qt 事件是两条线程/两条路径，各写一份"开菜单"
        迟早会分叉（本项目踩过"同一个动作两处实现"的坑）。

        ★ 去抖（`item_menu.TOGGLE_DEBOUNCE_SEC`）：热键回调实测可能被投递两次，
        而"开关"是取反 —— 重复一次等于**没开**，界面上表现为"按了没反应"。
        """
        if self.item_menu_ui is None:
            _log.info('菜单请求被忽略：道具系统未就绪')
            return False
        try:
            now = time.monotonic()
            last = self.__dict__.get('_item_menu_toggle_at', 0.0)
            if now - last < item_menu_mod.TOGGLE_DEBOUNCE_SEC:
                _log.info('菜单开关去抖：距上次 %.3fs（< %.2fs），忽略本次',
                          now - last, item_menu_mod.TOGGLE_DEBOUNCE_SEC)
                return False
            self._item_menu_toggle_at = now
            self.item_menu_ui.handle_key('menu')
            return True
        except Exception:
            _log.exception('开关菜单失败')
            return False

    def item_menu_key(self, name):
        """把一次按键交给菜单（窗口有焦点时由 `keyPressEvent` 转发）。"""
        if self.item_menu_ui is None or not self.item_menu_ui.is_open():
            return False
        try:
            self.item_menu_ui.handle_key(name)
            return True
        except Exception:
            _log.exception('菜单按键处理失败（已忽略）')
            return False

    def _item_menu_message(self, text):
        """菜单要弹一句话 —— 借对话气泡（与全项目其它"说话"同一出口）。"""
        try:
            self.dialogue_ui.add_dialogue('ralsei', text, 'normal')
            self.dialogue_ui.show_dialogue()
        except Exception:
            _log.exception('菜单文案弹出失败：%s', text)

    def _item_menu_anchor(self):
        """宠物窗口的屏幕矩形（全局坐标）—— 菜单据此摆位。"""
        return (self.x(), self.y(), self.width(), self.height())

    # ---------------------------------------------------------------- 可交互物回调
    def _item_prop_present(self, text, actor=None):
        """可交互物要说话（存档点/告示/拾取提示）——同样走对话气泡。"""
        self._item_menu_message(text)
        return text

    def _item_heal_all(self):
        """★ 存档点"全队回满 HP"。

        ⚠️ 本产品**没有**队伍 HP 模型（第48轮实测：全仓无 maxhp/party HP）。
        所以这里**如实返回 False**，而不是假装回血成功 ——
        `item_interact.SavePointProp.on_interact` 只把"回血失败"记日志，
        台词照出（台词才是用户能看见的东西）。等有了队伍数值再在这里接上。
        """
        _log.info('存档点回血：本产品当前无队伍 HP 模型 ⇒ 未执行（如实返回 False）')
        return False

    def _item_enter_scene(self, scene_id):
        """暗之泉"进泉"——切到目标场景。返回是否真的切成功（**不假装成功**）。"""
        if not scene_id:
            return False
        try:
            return bool(self.scene.switch(scene_id))
        except Exception:
            _log.exception('暗之泉切场景失败：%s', scene_id)
            return False

    def interact_scene_prop(self):
        """与当前场景的可交互物交互（对应原作的 `scr_interact()`）。

        ★ 第55轮改动：**按灵魂的位置选目标**（用户口径「灵魂…相当于这也是一个
        有互动的实体」）。

        在此之前这里是"老实按场景登记顺序取第一个"，理由是本产品**没有**"宠物站在
        房间哪个位置"这个信息。★ 那个理由现在**不成立**了 —— 灵魂有屏幕坐标，
        而"屏幕 → 房间世界坐标"的映射早就存在（`_pet_target_rect` 的逆 =
        `soul_entity.screen_to_room`），物件坐标也一直在数据里（`objects[].pos`，
        与 `room_rect` 同一套逻辑坐标，已实证）。

        选不出时**退回"登记顺序第一个"并记日志**（不是静默退回）——
        宁可"位置算不出时按老规矩来"，也不要"算不出就当没有可交互物"。

        范围内没有可交互物 ⇒ 返回 False（**不静默**：日志会说是哪一步没成）。
        """
        props = getattr(self, 'item_props', None) or []
        if not props:
            _log.info('交互请求：当前场景 %s 没有可交互物',
                      getattr(self, 'current_scene', None))
            return False
        target, why = self._soul_pick_prop(props)
        if target is None:
            target = props[0]
            why = '%s ⇒ 退回登记顺序第一个' % why
        ok = bool(target.interact())
        _log.info('交互 ⇒ %s（本场景共 %d 件可交互物；%s）：%s',
                  target.describe(), len(props), why,
                  '发生了' if ok else '什么也没发生')
        return ok

    # ---------------------------------------------------------------- 场景走动（R0-1）
    def travel_to_scene(self, target):
        """★ 第76轮 R0-1：「走到某个场景去」的**用户可见入口**（右键菜单 / 聊天）。

        这是本项目的"最贵坑"收口 —— 第45轮把 ①②③（意图→定位→寻路）写好了，
        但 `follow_route` **零调用**，于是"能看懂世界、不能走动"。本方法就是
        那个缺失的调用方。

        ★ 三条纪律（与 `scene_controller.travel_to` 同源，此处只做**宿主侧**的事）：
          1. 一切换都走 `scene.switch()`（内部校验场景登记在案）—— **不绕门禁**；
          2. 失败**如实说**，用 AI 回复通道告诉用户"去不了、为什么"，
             绝不静默、也绝不伪造"到了"；
          3. 成功只报事实（到了哪个场景、走了几跳），不编造沿途细节。

        :return: 是否真的换了场景。
        """
        try:
            if getattr(self, 'scene', None) is None:
                _log.info('走动请求被忽略：场景系统未就绪')
                return False
            before = self.__dict__.get('current_scene')
            rv = self.scene.travel_to(target)
            sid = (rv or {}).get('scene_id')
            if (rv or {}).get('ok') and sid and sid != before:
                _log.info('走动 ⇒ %s（route=%s，%d 跳）',
                          sid, rv.get('route'), rv.get('hops') or 0)
                # ★ 第85轮 I2：换了场景 ⇒ 重算明/暗世界（速度基准 3 / 4）。
                #   挂在**用户可见的换场景入口**上，与 `_update_scene_layer` 读的是
                #   同一处 `current_scene`（不一致会"人在暗世界、速度还是光世界"）。
                self._possession_sync_world()
                return True
            if (rv or {}).get('ok'):
                # 已经在目标场景 / 目标就是当前场景 ⇒ 不算失败，但不是"换了"。
                _log.info('走动：目标 %s 已是当前场景（未搬动）', sid)
                return False
            why = (rv or {}).get('error') or '原因不明'
            _log.info('走动失败：%s ⇒ %s', target, why)
            self._travel_feedback_fail(target, rv or {})
            return False
        except Exception:
            _log.exception('走动处理异常（已忽略，宠物照常运行）')
            return False

    def _travel_feedback_fail(self, target, rv):
        """走动失败时**明确告诉用户**（不静默）。

        ★ 为什么走对话气泡而不是状态栏：本项目的"说话"只有一条出口
          （`dialogue_ui.add_dialogue`），另开一条迟早分叉（同 `_item_menu_message`）。
        ★ 为什么带上候选：多解时用户需要知道"你说的是哪一个" ——
          这正是 `resolve_target` 不肯替人决定的理由。
        """
        try:
            if rv.get('ambiguous'):
                cands = rv.get('candidates') or []
                names = '、'.join((c.get('name') or c.get('scene_id') or '?')
                                  for c in cands[:5])
                text = '* 有好几个地方都叫「%s」：%s……你想去哪一个？' % (target, names)
            else:
                text = '* 我不知道怎么去「%s」。（%s）' % (target, rv.get('error') or '')
            self._item_menu_message(text)
        except Exception:
            _log.exception('走动失败提示弹出失败（已忽略）')

    # ---------------------------------------------------------------- 键盘
    def keyPressEvent(self, event):                       # noqa: N802 (Qt 命名)
        """窗口级键盘入口 —— ★ **裸 `S` 开菜单、方向键操控灵魂，都从这里进来**。

        为什么不是全局热键注册裸 `S`：`RegisterHotKey` 不带修饰键时是**系统级抢占**，
        注册了裸 `S`，用户在任何程序里都打不出那个字母。所以裸 `S` 只在
        宠物窗口有焦点时生效（正好等同"游戏里按 S"的手感），
        而无焦点的场景由 `Ctrl+Alt+S`（见 `global_hotkey.HOTKEY_DEFAULT_MENU`）覆盖。

        ★ 第55轮追加：**方向键 = 操控灵魂**（用户口径「键盘可操控移动」）。
          为什么是方向键而不是 WASD：`S` 已经是菜单键，`W/A/D` 将来也可能被占
          —— "一个键两个意思"是本项目反复踩过的坑；而方向键在本项目里
          **零占用**（`global_hotkey.vk_for_letter` 只认字母/数字，方向键压根
          注册不了全局热键，所以不存在冲突）。
          ⚠️ 方向键仍然**只在本窗口（或灵魂窗口）有焦点时**生效 ——
          `RegisterHotKey` 不带修饰键 = 系统级抢占，全局"按住方向键移动"
          需要 low-level keyboard hook，本轮**不做**，如实写进报告。

        ⚠️ 改动面仍守最小：`S` / `E` / `Z` / 方向键 / 菜单开着，才 accept，
        其余一律 `event.ignore()` 交回默认处理（等于原行为）。

        ★★ 第82轮 R5 追加：**`Z` = 交互 / 附身**（用户口径「交互键用Z」），
          以及**方向键的归属改为"看当前操控对象"**：
            · 未附身 ⇒ 方向键归**灵魂**（第55轮既有行为，零回归）；
            · 已附身 ⇒ 方向键归**被附身角色**（`possession.press`）。
          这正是原作形状：原作主角与灵魂读的是**同一组** `obj_time.*` 布尔
          （`obj_mainchara_Step_0` / `obj_heart_Step_0`），"操控谁"只切换消费方。
        """
        try:
            from PyQt5.QtCore import Qt as _Qt
            key = event.key()
            ui = getattr(self, 'item_menu_ui', None)
            menu_open = bool(ui is not None and ui.is_open())
            # ★ 方向键的归属：**附身优先**（已附身 ⇒ 归角色），否则归灵魂。
            #   两者互斥（附身时灵魂已收起），所以不会"两边都在动"。
            #   菜单开着时归菜单（菜单是"模态浮层"，此刻用户意图明确在菜单里）。
            if not menu_open:
                # ★★ 第85轮 I1：**Shift = 跑**（原作 `button2_h()` = `run`）。
                #   只发给附身状态机 —— 原作跑键是**主角**的属性（`runtimer`/`wspeed`
                #   都长在 `obj_mainchara` 上），灵魂没有跑动这回事
                #   （`obj_heart` 只有 `global.sp`）。所以未附身时 Shift **不接管**
                #   （`event.ignore()` 交回默认处理，等于原行为，零回归）。
                # ★ 键值：`Key_Shift`(0x01000020) 是**左** Shift，右 Shift 是
                #   0x01000021（Qt 无具名常量）。两个都认，否则"按右 Shift 不跑"。
                _SHIFT_KEYS = (_Qt.Key_Shift, 0x01000021)
                if key in _SHIFT_KEYS:
                    poss_r = getattr(self, 'possession', None)
                    if poss_r is not None and poss_r.is_possessing:
                        poss_r.set_running(True)
                        event.accept()
                        return
                d = soul_overlay_mod.direction_of_qt_key(key)
                if d is not None:
                    poss = getattr(self, 'possession', None)
                    if poss is not None and poss.is_possessing:
                        poss.press(d)
                        event.accept()
                        return
                    if self._soul_visible():
                        self._soul_press(d)
                    # ⚠️ accept **不看** `_soul_press` 的返回值：自动重复的按下
                    #    返回 False（`state.press` 对同一键幂等），但事件照样要吃掉，
                    #    否则方向键会漏回主窗口的默认处理。
                    event.accept()
                    return
            if menu_open:
                name = item_menu_ui_mod.key_name_for_qt(key)
                if name is not None:
                    self.item_menu_key(name)
                    event.accept()
                    return
                if key == _Qt.Key_S:
                    self.toggle_item_menu()
                    event.accept()
                    return
                event.ignore()
                return
            if key == _Qt.Key_S:
                self.toggle_item_menu()
                event.accept()
                return
            if key == _Qt.Key_E:
                # 与场景可交互物交互（原作的 `scr_interact()`，见 `interact_scene_prop`）。
                self.interact_scene_prop()
                event.accept()
                return
            if key == _Qt.Key_Z:
                # ★ 第82轮 R5：Z = 交互 / 附身（用户口径「交互键用Z」）。
                #   原作出处：`obj_mainchara_Step_0` 的 `control_check_pressed(0)`
                #   → `event_user(0)`（= `obj_mainchara_Other_12` 那段交互出口）。
                self.toggle_possession()
                event.accept()
                return
            if key == _Qt.Key_G:
                # ★ 第83轮 R6：G = 请求角色带灵魂走（用户裁定「新增 G 键」）。
                #   与 Z **完全分开**：Z 是附身（方向键归角色），
                #   G 是带路（方向键仍归灵魂，角色带着灵魂走）—— 两条独立分支。
                self.toggle_escort()
                event.accept()
                return
        except Exception:
            _log.exception('keyPressEvent 处理异常（已忽略，不拖垮主窗口）')
        event.ignore()

    def keyReleaseEvent(self, event):                     # noqa: N802 (Qt 命名)
        """方向键松开 ⇒ 放开**当前操控对象**的那个方向（灵魂 or 被附身角色）。

        ⚠️ 为什么必须实现它（第55轮）：灵魂是"按键即满速、松键即停"
        —— 照抄原作 `obj_heart` Step 里 `px/py` 每帧从 0 重新赋值，
        没有任何残速。一旦收不到 release，那个方向就**永不停止**。
        （第二道防线在 `SoulOverlay.focusOutEvent`：灵魂窗口失焦时放开所有键。）

        ★ 第82轮 R5：同样要放开**被附身角色**的键 —— 与 `keyPressEvent` 对称，
          否则附身时松手角色会一直朝那个方向走（同一类 bug，换了个实体）。
        """
        try:
            # ★ 第85轮 I1：**松开 Shift ⇒ 停止跑动**（原作的 `else { run = 0; }`）。
            #   与 `keyPressEvent` 对称 —— 漏了这条，"按住 Shift 跑"就会永不减速
            #   （同一类"永不停止"bug，`keyReleaseEvent` 的 docstring 里已写过两次）。
            from PyQt5.QtCore import Qt as _QtR
            _SHIFT_KEYS_R = (_QtR.Key_Shift, 0x01000021)   # 左 / 右 Shift
            if event.key() in _SHIFT_KEYS_R:
                poss_r = getattr(self, 'possession', None)
                if poss_r is not None and poss_r.is_possessing:
                    poss_r.set_running(False)
                    event.accept()
                    return
            d = soul_overlay_mod.direction_of_qt_key(event.key())
            if d is not None:
                poss = getattr(self, 'possession', None)
                if poss is not None and poss.is_possessing:
                    poss.release_key(d)
                    event.accept()
                    return
                if self._soul_visible():
                    self._soul_release(d)
                    event.accept()
                    return
        except Exception:
            _log.exception('keyReleaseEvent 处理异常（已忽略）')
        event.ignore()

    def focusOutEvent(self, event):                       # noqa: N802 (Qt 命名)
        """宠物窗口失焦 ⇒ 放开灵魂按住的键。

        `SoulOverlay` 自己有 `focusOutEvent`，但"按住方向键的同时 Alt-Tab 切走"时
        按键事件是送给**宠物窗口**的 ⇒ 那道防线盖不到这里。
        不做这件事的后果很具体：灵魂会一直朝那个方向飞，直到用户回来再点它一次。
        （与 `SoulOverlay.focusOutEvent` 同一条道理，两处都要有。）
        """
        try:
            soul = getattr(self, 'soul', None)
            if soul is not None and soul.state.pressed():
                _log.info('宠物窗口失焦 ⇒ 放开灵魂按住的键 %s',
                          ','.join(soul.state.pressed()))
                # ★ API 事实（第84轮实测钉死，勿凭印象改）：
                #   `self.soul` 是 **`SoulOverlay`**，它**确实有** `release_all()`
                #   （内部转调 `self.state.clear_keys()`，但**外面套了 `except: return 0`**
                #     —— 静默吞异常）。所以原写法 `soul.release_all()` **能跑、不是 bug**。
                #   这里改走 `soul.state.clear_keys()` 的理由只有两条：
                #     ① 语义直指"清 `SoulState` 里按住的键"，少一层转调；
                #     ② 不经过那个静默 `except`，真出问题会冒到下面的 `_log.exception`。
                #   ⇒ 这是**等价改写**，不是修 bug（初版误判为 AttributeError，已纠正）。
                soul.state.clear_keys()
        except Exception:
            _log.exception('focusOutEvent 处理异常（已忽略）')
        # ★ 第82轮 R5：失焦时同样要放开**被附身角色**按住的键（同一类"永不停止"bug）。
        try:
            poss = getattr(self, 'possession', None)
            if poss is not None and poss.is_possessing and poss.pressed():
                _log.info('宠物窗口失焦 ⇒ 放开被附身角色按住的键 %s',
                          ','.join(poss.pressed()))
                poss.release_all()
        except Exception:
            _log.exception('focusOutEvent（附身）处理异常（已忽略）')
        try:
            super(RalseiPet, self).focusOutEvent(event)
        except Exception as e:
            _log.debug('main 防御性异常（已忽略）: %s', e)

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
        # ★★ 第54轮 P0 修复（第53轮彻查发现）：
        #   `config_manager.get()` **只做 dict 遍历、不做任何校验**（同文件里的
        #   `validate_config()` 有 fps 校验但是**零调用**），所以手改
        #   `E:\RalseiMemory\config.json` 把 fps 写成 0 / 负数 / 字符串时，
        #   下一行的默认参数 `int(1000 / self.animation_fps)` 会**先于一切**
        #   抛 ZeroDivisionError（或 TypeError），程序**直接起不来**。
        #   处置：在**使用点**先钳位（非正数/非法 → 6；>120 → 120，与
        #   `validate_config` 的口径一致）。合法值**原样保留**（含 6.5 这类小数），
        #   不改变既有行为。
        _fps_raw = self.config_manager.get("animation.fps", 6)
        if isinstance(_fps_raw, bool) or not isinstance(_fps_raw, (int, float)) or _fps_raw <= 0:
            _log.warning("animation.fps = %r 非法（须为正数），回退为 6", _fps_raw)
            _fps_raw = 6
        elif _fps_raw > 120:
            _log.warning("animation.fps = %r 过大（>120），钳到 120", _fps_raw)
            _fps_raw = 120
        self.animation_fps = _fps_raw
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

        # ★★ 第52轮：待机（窝着）状态 —— 字段集中声明（scene_p0 的"9 字段预声明"同一纪律：
        #    属性必须在这里出现，别靠 getattr 兜底，否则"没接线"会伪装成"运行时正常"）。
        #    进入条件 = 距上次**用户互动**满 IDLE_LOUNGE_AFTER_SECONDS（默认 10 分钟）；
        #    进入后：关掉随机漫游 → 走到"任务栏（快捷栏）上沿"待着 → 切待机动画。
        self._lounge_since = None            # 进入待机状态的时刻；None = 未在待机
        self._lounge_perch = None            # 窝点 QPoint（屏幕坐标，窗口左上角落点）
        self._lounge_walking = False         # 正在走向窝点（这一趟不算"用户造成的移动"）
        self._lounge_interaction_ref = None  # 进入待机时的 last_interaction_time 基线

        # ★★ 第52轮：就寝状态
        self._bedtime_fired_date = None      # 已就寝的日期（'YYYY-MM-DD'）；每晚只触发一次
        self._bedtime_sleep = False          # 当前这次睡眠是不是"就寝睡"（决定早上自动醒）
        self._last_bedtime_check = 0.0       # 判定节拍时间戳（避免每 30ms 都算日期）
        
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
            # ★ 第51轮：整体上调（+0.15~0.2），理由同 `generate_new_move_target` 的距离注释
            #   —— 实测"完全静止"占了 70% 时长，动静比例失衡到观感上像没在动。
            #   保留各情绪的相对排序（兴奋最活跃 / 疲惫最安静）。
            if dominant_emotion == 'excited' or dominant_emotion == 'energetic':
                # 兴奋或精力充沛时更倾向于移动
                move_probability = 0.85
            elif dominant_emotion == 'shy' or dominant_emotion == 'peaceful':
                # 害羞或平静时更倾向于休息（第51轮：0.3 -> 0.5）
                move_probability = 0.5
            elif dominant_emotion == 'curious':
                # 好奇时更倾向于探索移动
                move_probability = 0.7
            elif dominant_emotion == 'sad' or dominant_emotion == 'tired':
                # 悲伤或疲惫时更倾向于休息（第51轮：0.2 -> 0.35）
                move_probability = 0.35
            else:
                # 其他情绪时的默认移动概率
                move_probability = 0.55
            
            # 根据概率决定是否继续移动
            if random.random() < move_probability or time_since_last_move < 1.0:
                # 修复：直接置 is_moving=True 而不生成新 target_pos，会导致宠物朝旧目标
                # （常为已到达位置）原地启停。generate_new_move_target() 内部会设新目标、
                # is_moving=True 并重置移动时长。
                self.generate_new_move_target()
            else:
                # 根据情绪调整休息时间
                # ★ 第51轮整体缩短（最长档 25s -> 12s）：实测**最长静息 33.5s**
                #   （= 连续两次长休息叠加），而"待机动画"要静止满 180s 才播 ⇒
                #   这几十秒里画面上**一格都不动**，是"像卡住了"的主要来源。
                if dominant_emotion == 'excited' or dominant_emotion == 'energetic':
                    # 兴奋时休息时间较短
                    self.max_idle_duration = random.uniform(2.0, 5.0)
                elif dominant_emotion == 'shy' or dominant_emotion == 'peaceful':
                    # 害羞或平静时休息时间较长（第51轮：8~20 -> 4~10）
                    self.max_idle_duration = random.uniform(4.0, 10.0)
                elif dominant_emotion == 'curious':
                    # 好奇时休息时间适中
                    self.max_idle_duration = random.uniform(3.0, 7.0)
                elif dominant_emotion == 'sad' or dominant_emotion == 'tired':
                    # 悲伤或疲惫时休息时间较长（第51轮：10~25 -> 5~12，仍为最长档）
                    self.max_idle_duration = random.uniform(5.0, 12.0)
                else:
                    # 其他情绪时的默认休息时间
                    self.max_idle_duration = random.uniform(4.0, 9.0)
                # 确保在休息状态
                self.is_moving = False
        else:
            # 第一次移动，根据情绪调整起始行为（★ 第51轮：概率与休息时长与上面同步收紧）
            if dominant_emotion == 'excited' or dominant_emotion == 'energetic':
                # 兴奋时更可能直接开始移动
                if random.random() < 0.75:
                    # 修复：见上方注释——必须生成新目标，否则原地踏步
                    self.generate_new_move_target()
                else:
                    self.is_moving = False
                    self.max_idle_duration = random.uniform(2.0, 5.0)
            elif dominant_emotion == 'shy' or dominant_emotion == 'peaceful':
                # 害羞或平静时更可能先休息（第51轮：0.2 -> 0.45）
                if random.random() < 0.45:
                    # 修复：见上方注释
                    self.generate_new_move_target()
                else:
                    self.is_moving = False
                    self.max_idle_duration = random.uniform(4.0, 10.0)
            else:
                # 其他情绪时的默认起始行为
                if random.random() < 0.5:
                    # 修复：见上方注释
                    self.generate_new_move_target()
                else:
                    self.is_moving = False
                    self.max_idle_duration = random.uniform(4.0, 9.0)
        
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
        # ★★ 第51轮按真机实测上调（用户口径：「他现在光有那个移动的动画，没有实际移动」）：
        #   实测 240s 内 35 段行走、**单段位移中位数仅 49.5px** —— Ralsei 自身才 38px 宽，
        #   即"走一次只挪 1.3 个身位"；在 2560px 宽的屏上肉眼几乎分辨不出位置变化，
        #   观感就是"动画在播、人没动"。原值（30~150）量级过小，这里统一放大到
        #   **最小 120px（≈3 个身位，肉眼可辨）**，并保留各情绪的相对远近关系。
        #   ⚠️ 不动 `IDLE_LOOP_MIN_SECONDS`（180s）——那是用户明确要求，不得回退。
        if dominant_emotion == 'excited' or dominant_emotion == 'energetic':
            # 兴奋时移动距离更远
            move_distance = random.randint(180, 420)
        elif dominant_emotion == 'shy' or dominant_emotion == 'peaceful':
            # 害羞或平静时移动距离较近（第51轮：50~150 -> 150~340）
            move_distance = random.randint(150, 340)
        elif dominant_emotion == 'curious':
            # 好奇时移动距离适中
            move_distance = random.randint(160, 380)
        elif dominant_emotion == 'sad' or dominant_emotion == 'tired':
            # 悲伤或疲惫时移动距离很短（第51轮：30~100 -> 120~280，仍为最短档）
            move_distance = random.randint(120, 280)
        else:
            # 其他情绪时的默认移动距离
            move_distance = random.randint(150, 360)
        
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
    #: 渲染层总开关。★ 第50轮按用户裁定改为 **True**（18 项原话：「怎么和原作
    #  效果贴近怎么来」）—— 原作里房间就是**画出来**的，关着反而不像原作。
    #  P0「不切场景时零行为变化」的判据仍成立：桌面场景（无 bg / 无物件）时
    #  `_update_scene_layer` 走收尾的 `_hide_scene_layer()` 分支，画面零变化。
    #  ⚠️ 保留这个开关本身：渲染出问题时可一刀关掉定位（不是死代码）。
    SCENE_LAYER_ENABLED = True

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
            # ★ 第76轮：公式抽到 `_screen_point_to_room_rect`，与灵魂锚点
            #   （`_camera_target_rect`）**共用同一真源** —— 两处各写一遍迟早分叉。
            return self._screen_point_to_room_rect(cx, cy, room_rect, (w, h))
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

    # ------------------------------------------------------------------
    #  ★★ 第76轮 R4 · 视角跟随的锚点 = 灵魂（用户口径）
    # ------------------------------------------------------------------
    #  用户原话（逐字）：
    #    「视角永远跟着灵魂所在地走，也就是灵魂在桌面，就显示桌面场景，在哪就显示哪」
    #    「那个跟随视角指的是**灵魂所在场景就是我屏幕显示的**哦」
    #
    #  ⇒ 锚点从「宠物」改成「灵魂」。此前 `camera_follow` 吃的是
    #    `_pet_target_rect()`（宠物窗口中心）—— 那是第44轮的默认（当时还没有
    #    可操控的灵魂实体，第55轮才建出来），与用户口径**不符**。
    #
    #  ★★ 这里要同时管两件事，缺一不可：
    #    (a) **坐标**：相机跟谁走（本方法提供矩形）；
    #    (b) **场景**：屏幕显示哪个场景 —— 灵魂所在的场景就是屏幕显示的场景。
    #        (b) 由 `_soul_scene_id` 承载：灵魂换场景时 `switch()` 会被调
    #        （第55轮的场景钩子 + 本轮 R0 的 travel_to / 推门都会走到那儿）。
    #
    #  ★ 为什么不直接把 `_pet_target_rect` 改掉：它还被 `_active_bubbles`
    #    （球容器位置）用着 —— 球的语义是「罩住**角色**」，与"视角跟谁"是两件事。
    #    两处分头演化正是本项目反复踩的坑 ⇒ 新加一个方法，让**调用方各取所需**。

    def _camera_target_rect(self, room_rect=None):
        """相机的跟随目标矩形（房间世界坐标）。

        ★ 优先**灵魂**（用户口径「视角永远跟着灵魂所在地走」）；
          灵魂不可用（未显示 / 未建 / 算不出）⇒ 退回 `_pet_target_rect()`（宠物）。

        ★ 退回是**静默降级但不静默失败**：日志记 debug（低频、可查），
          因为"灵魂没开"是合法状态（`SOUL_ENABLED=False` 或用户点了收起），
          不是错误 —— 报 warning 会把正常状态刷成噪声。

        坐标口径与 `_pet_target_rect` **完全一致**（屏幕 → 房间的归一化映射），
        所以两者可直接互换，不会出现"换个锚点量级就错"的问题。
        """
        try:
            if self._soul_visible():
                soul = getattr(self, 'soul', None)
                cx, cy = soul.state.center()
                # ★★ 注意 `state.size` 是 **property**（元组），不是方法 ——
                #   写成 `size()` 会抛 TypeError，而本方法整体在 try 里 ⇒
                #   会被静默吞掉、退回宠物锚点 ⇒ R4 **看起来绿但根本没生效**。
                #   这是第76轮真机验证亲手抓到的一处（离线套件当时是假绿，
                #   因为 check_r4_76 的 B 段桩把 size 造成了方法）。
                return self._screen_point_to_room_rect(cx, cy, room_rect,
                                                       soul.state.size)
        except Exception as e:
            _log.debug('视角锚点取灵魂失败（退回宠物）: %s', e)
        return self._pet_target_rect(room_rect)

    def _screen_point_to_room_rect(self, cx, cy, room_rect, size_px):
        """屏幕点 `(cx, cy)` + 像素尺寸 → 房间世界矩形。与 `_pet_target_rect` 同口径。

        ★ 抽出来是为了**单一真源**：`_pet_target_rect` 与灵魂锚点必须用同一套
          归一化（屏幕可用区域按比例压进房间世界矩形）。两处各写一遍 =
          迟早分叉（本项目最贵的坑），所以这里把公式抽成一个函数，两处都调它。
        """
        w = max(1.0, float(size_px[0]))
        h = max(1.0, float(size_px[1]))
        if not room_rect or len(room_rect) != 4:
            return (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)
        rl, rt, rr, rb = (float(room_rect[0]), float(room_rect[1]),
                          float(room_rect[2]), float(room_rect[3]))
        rw = max(1.0, rr - rl)
        rh = max(1.0, rb - rt)
        sw, sh = self._virtual_screen_size()
        fx = min(1.0, max(0.0, cx / float(sw))) if sw > 0 else 0.5
        fy = min(1.0, max(0.0, cy / float(sh))) if sh > 0 else 0.5
        kx = rw / float(sw) if sw > 0 else 1.0
        ky = rh / float(sh) if sh > 0 else 1.0
        # ★ 目标矩形的**外观尺寸**沿用宠物尺寸口径再按比例换算 ——
        #   相机只关心"目标在哪、多大"，灵魂比宠物小不影响跟随观感。
        try:
            base_w = max(1.0, float(self.width()))
            base_h = max(1.0, float(self.height()))
        except Exception:
            base_w, base_h = w, h
        tw = max(1.0, base_w * kx)
        th = max(1.0, base_h * ky)
        tcx = rl + rw * fx
        tcy = rt + rh * fy
        return (tcx - tw / 2.0, tcy - th / 2.0, tcx + tw / 2.0, tcy + th / 2.0)

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
            scene.camera_follow(room_rect, self._camera_target_rect(room_rect))

            # 2) 出指令（sprite_size 让剔除用真实素材尺寸 —— 见 SceneAssetCache）
            #    ★ 动效（第44轮续）：tick 传**毫秒时间戳**，渲染层据此按原作速度
            #      （30fps × GMS2PlaybackSpeed）取 sprite 当前帧。传墙钟时间而
            #      不是帧计数器 —— 理由见 scene_render._anim_frame_index 的长注释
            #      （负载抖动不该改变动画速度）。
            # 2.5) 球容器（第50轮）：世界一变就先用**规则**收一次
            #      （回暗世界 ⇒ 自动脱下球，符合"效果不带出章节"的同类口径）。
            world_now = self._current_world()
            if self.__dict__.get('_bubble_world') != world_now:
                fld = self._ensure_bubble_field()
                if fld is not None:
                    dropped = fld.transfer_world(world_now)
                    if dropped:
                        _log.info('回到暗世界，自动脱下扭蛋球：%s', dropped)
                self._bubble_world = world_now

            plan = scene.plan_frame(sprite_size=canvas.assets.sprite_size,
                                    tick=int(time.time() * 1000),
                                    bubbles=self._active_bubbles(room_rect))
            # 3) 交给画布（画布自己 resize + update）。
            #    画布尺寸用 `plan_viewport()`（= 收缩后的小房间尺寸 / 大房间的相机尺寸），
            #    而不是相机原始尺寸 —— 小房间要收缩，否则房间只占中间一块
            #    （与用户「房间放大些」的意图相反，见 scene_render.viewport_size）。
            view = scene.plan_viewport()
            # ★ 第50轮：球的前层（含"塑料滤镜"）必须叠在**角色之上** ⇒ 分流给
            #   overlay 控件；后层留在画布（在角色之下）。合起来即原作 Draw_0 的序。
            behind, front = scene_render_mod.split_bubble_layers(plan)
            canvas.set_plan(behind, view)
            self._update_bubble_overlay(front, view)

            # 4) 有 bg / 物件 才显示画布；纯占位/空 → 隐藏（保持桌面原样）
            if behind and any(it.get('kind') in ('bg', 'obj') for it in behind):
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

    # ------------------------------------------------------------------
    #  球容器（第50轮）—— 「Ralsei 在光世界必须被扭蛋球罩住」
    # ------------------------------------------------------------------
    def _ensure_bubble_field(self):
        """惰性建 `BubbleField`（避免在 `__init__` 里新增构造期依赖）。"""
        fld = self.__dict__.get('_bubble_field')
        if fld is None:
            try:
                fld = bubble_system_mod.BubbleField()
            except Exception as e:
                _log.warning('扭蛋球字段初始化失败（球不可用，其余功能照常）: %s', e)
                fld = None
            self._bubble_field = fld
        return fld

    def _current_world(self):
        """当前场景的明 / 暗世界（判据来自 `_worlds.json`；判不出 → `'dark'`）。

        ⚠️ `'dark'` 只是**兜底初值**（与第48轮道具域同口径，且记日志不静默）：
           判不出时取暗世界 —— 而球只在光世界被需要 ⇒ 判不出时**不显示球**
           是更保守的一侧。
        """
        try:
            scene = self.__dict__.get('_scene_state')
            if scene is not None:
                w = scene_system_mod.world_of_scene(scene)
                if w in ('light', 'dark'):
                    return w
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        return 'dark'

    def _active_bubbles(self, room_rect):
        """组装「谁被装在扭蛋球里」（★ 第50轮）—— `plan_frame(bubbles=)` 的入参。

        没有球在场 → `[]`（老调用方**零行为变化**）。

        ★ 坐标口径（与 `_pet_target_rect` 同一套"屏幕 → 房间世界"归一化）：
          球心 = 角色在房间世界里的位置 ⇒ 角色恒在球心 ⇒ **不穿模**。
        ★ 球的**缩放**由角色显示像素反推（`scene_render.fit_scale`），
          而不是硬用原作的 1.55 —— 后者在小角色上会让角色顶出球外。
        """
        fld = self._ensure_bubble_field()
        if fld is None or len(fld) == 0:
            return []
        rect = self._pet_target_rect(room_rect)
        if not rect or len(rect) != 4:
            return []
        cx = (float(rect[0]) + float(rect[2])) / 2.0
        cy = (float(rect[1]) + float(rect[3])) / 2.0
        try:
            lw = max(1, int(self.sprite_label.width()))
            lh = max(1, int(self.sprite_label.height()))
        except Exception:
            lw = lh = 1
        out = []
        for cid in fld.holders():
            b = fld.get(cid)
            if b is None:
                continue
            try:
                b.tick(1)          # 推进"出现/消失"的 alpha 与旋转缓动
            except Exception as e:
                _log.debug("球 %s 推进失败（已忽略）: %s", cid, e)
            try:
                scale = scene_render_mod.fit_scale(lw, lh)
            except Exception:
                scale = 1.0
            try:
                flt = b.filters()
            except Exception:
                flt = None
            out.append({
                'char': cid,
                'ball_xy': (cx, cy),
                'char_xy': (cx, cy),
                'scale': scale,
                'angle': getattr(b, 'angle', 0.0),
                'alpha': getattr(b, 'alpha', 1.0),
                'char_size': (lw, lh),
                'char_sprite': None,   # 角色像素由 `sprite_label` 画，本层只带滤镜
                'char_frame': 0,
                'filter': flt,
            })
        return out

    def _update_bubble_overlay(self, front_plan, view):
        """把球的前层（含"塑料滤镜"）画到**角色之上**（★ 第50轮）。"""
        ov = self.__dict__.get('bubble_overlay')
        if ov is None:
            return
        try:
            if front_plan:
                ov.set_plan(front_plan, view)
                if not ov.isVisible():
                    ov.show()
                ov.raise_()   # 保证在 `sprite_label` 之上（否则球壳被角色盖住）
            elif ov.isVisible():
                ov.hide()
        except Exception as e:
            _log.debug("球前层更新失败（本帧跳过）: %s", e)

    def toggle_bubble(self, char_id=None, on=None):
        """套上 / 脱下扭蛋球（★ 第50轮的**交互入口**，供菜单 / 对话 / 热键调用）。

        * `char_id` 缺省 = `'ralsei'`（用户口径里唯一"必须靠球"的角色）。
        * `on=None` ⇒ 反转当前状态；`on=True/False` ⇒ 显式指定。
        * 「可以随时脱下来（除了 lancer）」与"Ralsei 在光世界不能脱"这两条由
          `bubble_system` 判定，本方法**只转发**（不重复实现规则 —— 否则规则
          会长出第二份真源）。
        * 拿不到球字段 / 操作被规则拒绝 ⇒ 返回 False（**不抛**）。
        """
        fld = self._ensure_bubble_field()
        if fld is None:
            return False
        cid = char_id or 'ralsei'
        try:
            cur = cid in fld
            want = (not cur) if on is None else bool(on)
            world = self._current_world()
            if want:
                return fld.equip(cid, by='kris', world=world) is not None
            return fld.unequip(cid, world=world)
        except Exception as e:
            _log.warning('切换扭蛋球失败（%s）: %s', cid, e)
            return False

    # 移动相关代码 - 更新移动逻辑
    @monitor_performance
    def update_movement(self):
        # 更新位置，改进运动逻辑，结合真实物理系统
        import math
        # 计算实际经过的时间
        current_time = time.time()
        elapsed_time = current_time - self.last_update_time
        raw_elapsed = elapsed_time          # ★ 截断前的真实间隔（计时器用，见下）
        self.last_update_time = current_time
        # dt 截断（瞬移防治）：本函数内部会做窗口枚举（check_window_movement →
        # floor_manager.update_floors）、COM 调用等**可能阻塞主线程**的动作，阻塞耗时会被
        # 计入下一个 tick 的 elapsed_time。而位移普遍写成 `速度 × dt`（重力掉落更是
        # `速度 += g*dt` 后再 `× dt`，对 dt 呈二次放大），一旦 dt 变成 1~2 秒，
        # 宠物就会"啪"地跳出去一大段——这就是用户看到的偶发瞬移。
        # 上限 0.1s（约 10FPS 的容差）：正常 tick 30ms 不受影响，异常长 tick 只按 100ms 结算。
        # ⚠️ 本截断**只作用于位移**（下面所有 `速度 × elapsed_time` 的算式）。
        if not isinstance(elapsed_time, (int, float)) or elapsed_time < 0:
            elapsed_time = 0.0
        elif elapsed_time > 0.1:
            elapsed_time = 0.1

        # ★★ 第51轮新增：**状态机计时器用未截断的真实经过时间**（上限 2s 防呆）。
        #
        # 为什么必须和上面的 `elapsed_time` 分开（真机实测催生）：
        #   0.1s 截断是给**位移**用的（防瞬移，理由见上），但 `idle_timer` /
        #   `moving_duration` 是**状态机节拍**，不是位移量 —— 它们只需要"过了多久"。
        #   一旦主线程被阻塞（真机实测见过 **6.68s** 的一次：窗口枚举 / 首次
        #   `psutil.getloadavg()` 在 Windows 上要初始化计数器，单次就 1.1s），
        #   紧接着的每一 tick 都只结算 0.1s ⇒ **内部时钟最慢被拉长 10 倍**：
        #   `max_idle_duration = 15s` 的现实等待变成约 150s。
        #   用户看到的现象就是：「光有那个移动的动画，没有实际移动」——
        #   他其实在按自己的节拍走，只是那个节拍被 dt 截断偷走了 90% 的时间。
        #   （实测：被阻塞的会话 55s 只走 2 段；干净会话 55s 走 **12** 段、均速 56px/s。）
        # 上限取 2.0s 而不是不设限：真挂起 30s 时不该一口气把 30s 全算成"休息已结束"
        # （那会退化成"一醒来就立刻暴走"）。2s 足以盖住实测到的最坏阻塞。
        try:
            timer_dt = min(max(float(raw_elapsed), 0.0), 2.0)
        except Exception:
            timer_dt = float(elapsed_time)

        # ---- 灵魂（SOUL，第55轮）：每帧推进 ----
        # ★ 位置必须在**所有早退分支之前**（睡眠 / 施法 / 躲猫猫 / 拖拽保护 /
        #   特殊动画都会 return）：灵魂是独立实体，宠物睡着时它照样该能动。
        # dt 复用上面的 `elapsed_time`（已钳 0.1s，与 `soul_entity.MAX_DT` 同口径，
        # 双重保险 —— 那边的钳制是给"别处调用本模块"用的）。
        self._soul_tick(elapsed_time)

        # ---- 附身（POSSESSION，第82轮 R5）：每帧推进 ----
        # ★ 紧挨灵魂：附身是"方向键消费方的切换"，与灵魂**互斥**（附身时灵魂已收起），
        #   放在一起读起来就是"这两个在争同一组按键"。
        # ★ 同样在所有早退分支之前：被附身的角色不该看宠物睡没睡。
        self._possession_tick(elapsed_time)

        # ---- 带路（ESCORT，第83轮 R6）：每帧推进 ----
        # ★ 紧挨附身：两者都在"重新分配主体位置/操控权"，且**互斥**
        #   （附身时角色归用户操控；带路时角色带灵魂走）。
        # ★ 同样在所有早退分支之前：带路是独立实体的位置，宠物睡没睡不影响。
        # ⚠️ 带路者位置源本轮**未接线** ⇒ 无坐标时它安静返回 False
        #   （见 `ESCORT_WIRING`，不假报"带路中")。
        self._escort_tick(elapsed_time)

        # ---- NPC 站位 / 游荡 / 结伴（第56轮）：每帧推进 ----
        # ★ 与灵魂同一位置（`update_movement` 的**所有早退分支之前**）：NPC 是独立实体，
        #   宠物睡着 / 施法 / 躲猫猫时他们照样该在城堡镇里晃。
        # ★ 为什么挂在 30ms 定时器上而不是动画定时器（100ms）：原作的游荡速度是
        #   **px/帧**（`GMS2FPS = 30`），挂在 10fps 上会让 NPC 走成"一跳一跳"。
        # dt 复用已钳到 0.1s 的 `elapsed_time`（`npc_placement.MAX_DT` 同口径，双保险）。
        self.npc_placement_tick(elapsed_time)

        # ---- 幽灵（第67轮）：每帧推进 ----
        # ★ 与灵魂 / NPC 同一位置（`update_movement` 的**所有早退分支之前**）：
        #   幽灵是独立实体，宠物睡着 / 施法 / 被拖着时它照样该按距离显淡。
        # ★ 同时喂**接触计时**：它读 `self.npc_bodies`（当前场景在场的人，已过世界门控），
        #   判据只有一处，不在这里重算"谁该在场"。
        self._ghost_tick(elapsed_time)

        # ---- NPC「自由生活」（第73轮）：每帧推进 ----
        # ★ 与灵魂 / 站位 / 幽灵同一位置（`update_movement` 的**所有早退分支之前**）：
        #   他们过日子不该看宠物睡没睡。dt 同口径（已钳 0.1s）。
        # ★ 本函数内部**自己**再判一次 `NPC_LIFE_ENABLED` 与"在场 ≥2 人"，
        #   所以这里不重复判（同一份规则不许两处算）。
        self._npc_life_tick(elapsed_time)

        # ---- ★★★ NPC「自主移动」（第79轮 · 层2）：**按自己的节拍**推进 ----
        # ★ 为什么**不**复用上面的 `elapsed_time`：那不是"过了多久"，是"这一帧的位移量"
        #   （已钳 0.1s）。生活决策的节拍是**墙钟**（`NPC_AUTONOMOUS_TICK = 30s`），
        #   与帧率/阻塞无关 —— 用 dt 累加会让"被阻塞时世界反而走得更慢"（第51轮踩过）。
        # ★ 为什么挂在这里而不是动画定时器：与灵魂/站位/幽灵/自由生活同一处
        #   （`update_movement` 的**所有早退分支之前**）—— 他们过日子不该看宠物睡没睡。
        # ★ 关掉开关（默认）时本函数**立刻返回**，零副作用（零回归）。
        self._npc_roam_tick(current_time)

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
        
        # ★★ 第52轮：就寝判定。**必须排在"睡眠状态处理"之前** ——
        #   白天的 5 分钟小憩（`max_sleep_idle_duration`）几乎必然覆盖 23:00；
        #   就寝要做的是把那场小憩**升级**成"就寝睡"（并回房间），不是被它挡掉。
        #   节流在 `_bedtime_tick` 内部（BEDTIME_CHECK_INTERVAL=5s），这里每 tick 调是安全的。
        self._bedtime_tick(current_time)

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
                    # ★★ 第52轮：`唔...别吵...` 三句内置台词**已迁到事件通道**
                    #   （用户口径「把他内置的对话去掉」「聊天系统全权由7B接管」）。
                    try:
                        self.speak_event("sleep_stir", None, "sleepy")
                    except Exception as e:
                        _log.debug("main 防御性异常（已忽略）: %s", e)
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
            self.moving_duration += timer_dt   # ★ 计时器口径，见 update_movement 顶部说明
            
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
            self.idle_timer += timer_dt        # ★ 计时器口径，见 update_movement 顶部说明
            # ★★ 第52轮：待机（窝着）状态**优先于**随机漫游 ——
            #    进入待机后必须关掉 `randomize_movement_pattern`，否则刚走到
            #    任务栏上沿就又被随机漫游赶走（"待不住"）。
            #    注意：待机期间不再靠 `idle_timer` 记门限（它会被随机漫游清零，
            #    见 IDLE_LOUNGE_AFTER_SECONDS 的说明），门限走"距上次用户互动"。
            _lounging = self._idle_lounge_tick(current_time)
            if _lounging:
                if not self.is_moving:
                    self.idle_timer = 0
            elif self.idle_timer >= self.max_idle_duration:
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
        """「我来帮你移动」—— ★ 第55轮：**被移动的对象从系统光标换成了灵魂**。

        用户口径（逐字）：「别换鼠标的样子了，改成可移动的那个灵魂图标…
        原先和你说的**鼠标附身换成就是这个灵魂的功能**」。

        状态机（`is_dragging_mouse` / `drag_start_pos` / `drag_target_pos` /
        缓动 / `drag_duration`）**原样保留**，只把输出端从
        `win32api.SetCursorPos`（真搬动用户的鼠标指针）改成**推动那团红色 SOUL**。
        理由不只是"用户要求"：搬动别人的鼠标指针会打断用户正在做的事，
        而推动一个宠物自己的小窗口完全无害 —— 同一个"我来帮你"的表达，
        换个无害的落点就成立了。
        """
        if getattr(self, 'soul', None) is None:
            _log.info('"帮你移动"请求被忽略：灵魂未就绪（SOUL_ENABLED=%s）',
                      getattr(self, 'SOUL_ENABLED', None))
            return False
        self.is_dragging_mouse = True
        # 起点 = 灵魂**当前**位置（原来是 `QCursor.pos()`）。
        self.drag_start_pos = QPoint(int(self.soul.state.x), int(self.soul.state.y))
        self.drag_target_pos = target_pos
        self.drag_start_time = time.time()

        # 显示对话
        self.dialogue_ui.add_dialogue("ralsei", "我来帮你把灵魂推过去吧！", "playful")
        self.dialogue_ui.show_dialogue()

        # 播放动画
        self.play_animation_once("act")

        # 启动拖动定时器：按 ~60FPS 推进，直到 update_mouse_drag 判定时间到后自行停止
        self.mouse_drag_timer.start(16)
        return True

    def update_mouse_drag(self):
        """把灵魂缓动推往 `drag_target_pos`（**不再**移动用户的系统光标）。

        ★ 第55轮的改动（用户口径见 `start_mouse_drag`）：
          原实现 `win32api.SetCursorPos(...)` / `QCursor.setPos(...)` ——
          真的搬动用户光标。现在这两行**已下线**，同一个缓动只作用于灵魂。
          区别是可观察的：用户的鼠标指针**一动不动**。
        """
        # 更新灵魂的拖动位置
        if not self.is_dragging_mouse:
            return

        soul = getattr(self, 'soul', None)
        if soul is None:
            self.is_dragging_mouse = False
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

        # 推动**灵魂**（钳制交给灵魂自己：`clamp_to` 用的是虚拟屏并集，
        # 与宠物窗口不同 —— 灵魂能横跨到副屏去）。
        try:
            soul.state.x = float(current_x)
            soul.state.y = float(current_y)
            b = soul.screen_bounds()
            if b:
                soul.state.clamp_to(b)
            soul.apply_state_pos()
            soul.update()
        except Exception as e:
            _log.debug('推动灵魂失败（本帧跳过）: %s', e)

    def stop_mouse_drag(self):
        # 停止推动灵魂
        # 修复：改为周期定时器后必须显式停止，否则会以 16ms 空转
        try:
            self.mouse_drag_timer.stop()
        except Exception as e:
            _log.debug("停止鼠标拖动定时器失败: %s", e)
        self.is_dragging_mouse = False
        self.drag_start_pos = None
        self.drag_target_pos = None
        self.drag_start_time = None

        # ★ 推完把位置记进场景位置簿（否则换一圈场景回来它会忘了自己在哪）
        self._soul_bookmark_save()

        # 显示对话
        self.dialogue_ui.add_dialogue("ralsei", "推到位啦！", "happy")
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
        # ★ 第52轮：就寝睡结束（早上自动醒 / 被叫醒都算）
        self._bedtime_sleep = False
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
        
        # ★★ 第52轮：`嗯？什么事？` 三句内置台词**已迁到事件通道**（同 `enter_sleep_mode`，
        #   用户口径「把他内置的对话去掉」「聊天系统全权由7B接管」）。
        try:
            self.speak_event("wake_up", None, "surprised")
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        
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
            
        # ★★ 第51轮：**删除「与文件夹 / 文件交互」功能**（用户口径逐字：
        #    「并且去掉那个与文件夹交互的功能吧，感觉过于鸡肋了」）。
        #
        #    原实现：`random.random() < 0.25` 时按元素类型调
        #    `interact_with_folder()` / `interact_with_file()`，而那两个方法体里
        #    只有一串**按文件夹名硬编码的固定台词**
        #    （"哇，XX文件夹里有游戏吗？我也想玩~"、"XX文件夹里有很多重要的文件吧？" …）
        #    —— 既没有真实能力（"鸡肋"），又把罐头句子和 AI 生成的话混在同一个
        #    对话框里（用户："看不出哪句是他自己说的"）。整个删掉。
        #
        #    连带删除下面"看到浏览器文件就说一句固定观察"的分支 —— 它同样是硬编码
        #    台词，属用户「把他内置的对话去掉」的范围。
        #
        #    **保留**：上面已执行的 `_note_desktop_observation()`（把"我凑近了什么、
        #    它是什么质地"上报给 AI，第八轮的成果）与情绪累积 —— 那是**状态**，
        #    不是台词；AI 想说什么由它自己决定。
        # 如果是工作相关文件，可以提供帮助
        # ★ 第51轮起由 `SHOW_FILE_HELP_HINTS`（默认 False）总控 —— 用户要求
        #   「把他内置的对话去掉」。原来的 `else:` 改成开关判断，结构不变。
        if self.SHOW_FILE_HELP_HINTS:
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
    
    
    
    #: ★★ 第51轮：按文件扩展名给"助手腔提示"的总开关（**默认关**）。
    #:
    #: 用户口径逐字：「把他内置的对话去掉！！！！…记住，**聊天系统全权由7B接管**，
    #: 别放内置对话了，太木讷了」。
    #: 关掉的是 `check_nearby_desktop_elements()` 里 `if file_ext in
    #: work_file_extensions` 那一整段 —— 16 条按扩展名写死的助手腔提示
    #: （"需要我帮你控制这个PPT吗？我可以帮你播放、切换幻灯片哦！"）。它们同时
    #: 踩了两条线：
    #:   ① persona 明令禁说的**助手腔**；
    #:   ② 与 AI 生成的句子混在同一个对话框里 ⇒ 用户"看不出哪句是他自己说的"。
    #:
    #: 为什么用**开关**而不是直接删掉那段：`check_nearby_desktop_elements()` 里
    #: 的 if/else 是**配对的**，本轮第一次改动只删了 `if` 分支、留下了悬空的
    #: `else:`，直接造成 `SyntaxError`（由 `ast.parse` 自检抓到）。改用开关 =
    #: 结构零变动、行为已停用、原文可回溯。
    SHOW_FILE_HELP_HINTS = False

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
    
    # ==============================================================
    # ★★ 第52轮：就寝（回房间睡觉）—— 常量与口径见 BEDTIME_* 区块
    # ==============================================================
    def _bedtime_target_time(self, date_obj):
        """当晚的就寝时刻（datetime）：23:00 ± BEDTIME_JITTER_MINUTES。

        用**日期做种**（`random.Random(YYYYMMDD)`）：同一天里反复调用得到同一个
        时刻，不同天不同 —— 既有"±10 分钟"的随机感，又不会在同一晚抖动。
        """
        import datetime as _dt
        seed = int(date_obj.strftime('%Y%m%d'))
        rnd = random.Random(seed)
        jitter = rnd.randint(-int(self.BEDTIME_JITTER_MINUTES),
                             int(self.BEDTIME_JITTER_MINUTES))
        base = _dt.datetime(date_obj.year, date_obj.month, date_obj.day,
                            int(self.BEDTIME_HOUR), 0, 0)
        return base + _dt.timedelta(minutes=jitter)

    def _bedtime_busy(self):
        """「有事」的判定 —— 逐条对应用户原话「除非有事（冒险，和我聊天等）」。

        ⚠️ **不含 `is_sleeping`**：白天的 5 分钟小憩（`max_sleep_idle_duration`）
        几乎必然覆盖 23:00，如果这里把"正在睡"当忙碌，就寝永远不会发生。
        就寝要做的是把小憩**升级**成就寝睡（见 `go_to_bed`），不是被它挡掉。
        """
        if getattr(self, 'game_state', {}).get('is_playing'):
            return True                       # 冒险 / 小游戏
        for attr in ('is_falling', 'is_recovering', 'is_splat', 'is_jumping',
                     'is_gravity_falling', '_is_being_dragged',
                     'is_following_mouse', 'is_watching_video'):
            if getattr(self, attr, False):
                return True
        if getattr(self, '_spell_stage', None) is not None:
            return True
        if getattr(self, '_hide_stage', None) is not None:
            return True
        dui = getattr(self, 'dialogue_ui', None)
        if dui is not None:
            try:
                if callable(getattr(dui, 'has_active_conversation', None)) \
                        and dui.has_active_conversation():
                    return True               # 正在聊天（有来有回 / 刚说完没静下来）
            except Exception as e:
                _log.debug("main 防御性异常（已忽略）: %s", e)
            try:
                if callable(getattr(dui, '_is_user_inputting', None)) \
                        and dui._is_user_inputting():
                    return True               # 用户正在打字
            except Exception as e:
                _log.debug("main 防御性异常（已忽略）: %s", e)
            if getattr(dui, '_ai_inflight', False):
                return True                   # 模型回复在途
        return False

    def go_to_bed(self):
        """回房间 + 就寝。返回 True 表示这一晚的就寝动作已执行。

        ★ 本函数服务**桌宠本人**（他住 `BEDTIME_HOME_SCENE` = 桌面）。
          NPC 的就寝是另一条路（`_npc_roam_sleep`，逐人决策）—— 见常量处声明。

        · 场景切换复用既有 `self.scene.switch()`（不新开通道、不绕过世界门控）；
        · 落点复用待机窝点（屏幕底部 · 快捷栏上沿）——"回房间"在视觉上就是
          走到屏幕下方他的位置躺下；
        · 已经在睡（白天小憩）⇒ 只**升级**成"就寝睡"，不重放一次入睡台词。
        """
        self._exit_idle_lounge("就寝")
        home = getattr(self, 'BEDTIME_HOME_SCENE', 'desktop')
        try:
            if getattr(self, 'current_scene', None) != home:
                ok = bool(self.scene.switch(home))
                _log.info("[就寝] 回房间 %s -> %s（%s）", getattr(self, 'current_scene', None),
                          home, "成功" if ok else "切换未成功，仍就地就寝")
        except Exception as e:
            _log.warning("[就寝] 回房间失败（忽略，就地就寝）: %s", e)
        # 走到窝点（快捷栏上沿）再睡
        try:
            perch = self._lounge_perch_point()
            if perch is not None:
                self.move(perch)
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        if getattr(self, 'is_sleeping', False):
            # 已经是小憩睡 ⇒ 只升级标记，不重放入睡台词
            self._bedtime_sleep = True
            _log.info("[就寝] 由小憩升级为就寝睡")
        else:
            self.enter_sleep_mode(bedtime=True)
        return True

    def _bedtime_tick(self, now=None):
        """就寝判定（节流 BEDTIME_CHECK_INTERVAL 秒调一次）。返回 True = 本次执行了就寝。"""
        try:
            if not getattr(self, 'BEDTIME_ENABLED', True):
                return False
            now_ts = time.time() if now is None else float(now)
            # 节流：窗口 ±10 分钟，5 秒一次足够
            if now_ts - float(getattr(self, '_last_bedtime_check', 0.0)) \
                    < float(getattr(self, 'BEDTIME_CHECK_INTERVAL', 5.0)):
                return False
            self._last_bedtime_check = now_ts

            import datetime as _dt
            dt_now = _dt.datetime.fromtimestamp(now_ts)

            # ---- ① 早上自动醒（**只**对"就寝睡"生效；小憩不自动醒）----
            if getattr(self, '_bedtime_sleep', False) and getattr(self, 'is_sleeping', False) \
                    and dt_now.hour >= int(self.BEDTIME_WAKE_HOUR):
                _log.info("[就寝] 早上 %02d 点，自动醒来", dt_now.hour)
                self.wake_up()
                return False

            # ---- ② 到点就寝（每晚一次）----
            today = dt_now.strftime('%Y-%m-%d')
            if getattr(self, '_bedtime_fired_date', None) == today:
                return False
            date_obj = dt_now.date()
            target = self._bedtime_target_time(date_obj)
            window_end = target + _dt.timedelta(minutes=int(self.BEDTIME_JITTER_MINUTES))
            if dt_now < target:
                return False                      # 还没到点
            if dt_now > window_end:
                # 窗口已过（多半是"有事"占满了，或程序那时没运行）
                # ⇒ 记一笔今晚不再尝试，**不做"半夜补睡"**
                self._bedtime_fired_date = today
                _log.info("[就寝] 今晚（%s）窗口 %s~%s 已过，不再补睡",
                          today, target.strftime('%H:%M'), window_end.strftime('%H:%M'))
                return False
            if self._bedtime_busy():
                _log.debug("[就寝] 到点但「有事」（冒险/聊天中），本次推迟")
                return False                      # 窗口内继续等，不标记 fired
            self._bedtime_fired_date = today
            _log.info("[就寝] 到点（目标 %s），回房间睡觉", target.strftime('%H:%M'))
            return bool(self.go_to_bed())
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return False

    def enter_sleep_mode(self, bedtime=False):
        # 进入睡眠状态
        self.is_sleeping = True
        self.is_moving = False
        # ★ 第52轮：睡觉优先于"待机窝着"（别一边睡着一边还惦记着窝点）
        self._exit_idle_lounge("进入睡眠")
        # ★ 第52轮：区分"就寝睡"与"小憩睡" —— 只有就寝睡才会在早上
        #   `BEDTIME_WAKE_HOUR` 自动醒（见 `_bedtime_tick`）。
        self._bedtime_sleep = bool(bedtime)
        # 清理睡眠迷糊状态
        for attr in ('_sleep_stir_time', '_sleep_stir_count'):
            if hasattr(self, attr):
                delattr(self, attr)
        self.change_animation("idle", force=True)  # force=True 确保即使冷却期内也切换
        # ★★ 第52轮：`zzz... 晚安，做个好梦！` 三句内置台词**已迁到事件通道**。
        #   用户口径逐字：「还有把他内置的对话去掉！！！！」／
        #   「记住，聊天系统全权由7B接管，别放内置对话了，太木讷了」。
        #   `pool=None` = 不给内置台词（AI 不可用就安静地睡，而不是甩一句写死的 zzz）。
        #   ⚠️ 本模块**不能**用 `_log_()`（那是 hide_controller 的私有方法），
        #   本文件用的是模块级 `_log`。
        try:
            self.speak_event("sleep_enter", None, "sleepy")
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
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
    IDLE_LOOP_MIN_SECONDS = 600.0  # ★ 第51轮：10 分钟（用户口径「他待机只会在静止超过10分钟后触发」）

    # ==============================================================
    # ★★ 第52轮：「待机（窝着）」状态
    #   用户口径逐字：
    #     「他这一直站着不动是什么情况，像贴图似的，而且就算静止不动那也要来屏幕底下
    #       那个快捷栏上面待着吧，就偶尔聊几句天这样的感觉」
    #
    #   ❗先修**根因**（不然上面那句"待机只会在静止超过10分钟后触发"是句空话）：
    #     判据 `_idle_loop_active = idle_timer >= IDLE_LOOP_MIN_SECONDS` 在真机上
    #     **恒为假** —— `update_movement` 的空闲分支只要休息满 `max_idle_duration`
    #     就会调 `randomize_movement_pattern()` 并把 `idle_timer` 清零
    #     （见 2936~2954 行），而 `max_idle_duration` 被随机成 **2~12 秒**
    #     （见 `randomize_movement_pattern`）。⇒ `idle_timer` 最多涨到 ~12s，
    #     **永远够不到 600s** ⇒ "待机动画"结构性地从未播放过，宠物永远定格在
    #     最初那一帧站姿 —— 这正是用户看到的"像贴图似的"。
    #     （第51轮曾据此把休息时长从 25s 缩到 12s，方向是反的：休息越短、
    #       `idle_timer` 被清零得越勤，门限越不可能达成。）
    #
    #   ⇒ 判据改用「**距上次用户互动**已满多久」——这个量不会被自主漫游清零；
    #     并在进入待机后**关掉随机漫游**（否则刚坐下就又被赶走）。
    #
    #   进入后做什么：
    #     ① 走到「屏幕底部 · 任务栏（快捷栏）上沿之上」待着（用户原话）；
    #     ② 切到待机动画（idle 的 5 帧循环）；
    #     ③ "偶尔聊几句"沿用既有通道 `start_autonomous_speech`（10 分钟一次），
    #        **不新开第二条说话通道**；
    #     ④ 一有用户互动（或睡眠/游戏/拖拽等忙碌状态）立刻退出待机。
    # ==============================================================
    IDLE_LOUNGE_ENABLED = True
    IDLE_LOUNGE_AFTER_SECONDS = 600.0    # 与 IDLE_LOOP_MIN_SECONDS 同口径（10 分钟）
    IDLE_LOUNGE_PERCH_X_RATIO = 0.72     # 窝点横向位置：所在屏的 72% 处（偏右，不压桌面图标区）

    # ==============================================================
    # ★★ 第52轮：就寝（回房间睡觉）
    #   用户口径逐字：
    #     「在晚上的时候他会自己回到自己的房间里除非有事（冒险，和我聊天等），
    #       要他就会在晚上11点左右（也就是上下10分钟）的时候回去睡觉」
    #
    #   口径拆解（逐句对应）：
    #     · "晚上11点左右（上下10分钟）" ⇒ 触发窗口 = 23:00 ± `BEDTIME_JITTER_MINUTES`。
    #       每晚的落点**随机但当日稳定**（用日期做种）：否则天天同一秒回房，
    #       机械得像定时器崩了；日期内稳定是为了"同一晚多次 tick 不会算出不同时刻"。
    #     · "除非有事（冒险，和我聊天等）" ⇒ 窗口内只要处于忙碌状态就**推迟**
    #       （`_bedtime_busy()`：游戏/冒险、正在聊天/用户在打字、物理过程、拖拽…）。
    #       窗口过完还没空 ⇒ **当晚就不睡了**，不做"半夜补睡"（那是另一种吓人）。
    #     · "回到自己的房间里" ⇒ 走既有 `self.scene.switch()` 回 `BEDTIME_HOME_SCENE`。
    #       ★ 本项目的桌宠"家"就是**桌面**（`_index.json` 的 `default_scene`）。
    #         要改成某个城堡房间（如 `ch2.ralsei_room.dw_ralsei_castle_2f`）只改这一个
    #         常量——但**未经用户确认不擅自选**（已在第52轮报告里列为待裁定）。
    #       ★★★ 第80轮：**这一段只管桌宠本人**。NPC 的就寝走**逐人决策**
    #         （`npc_intent.choose_sleep_scene` → `main._npc_roam_sleep`），
    #         与本常量**无关** —— 旧的「NPC 也回 `BEDTIME_HOME_SCENE`」口径已废弃。
    #     · 早上 `BEDTIME_WAKE_HOUR` 自动醒；**只对"就寝睡"生效**，
    #       白天的 5 分钟小憩不自动醒（那样会变成"刚躺下就起来"）。
    # ==============================================================
    BEDTIME_ENABLED = True
    BEDTIME_HOUR = 23
    BEDTIME_JITTER_MINUTES = 10          # 23:00 ± 10 分钟
    BEDTIME_WAKE_HOUR = 7
    BEDTIME_HOME_SCENE = 'desktop'       # "他的房间"（本项目的家＝桌面）
    #: ★★★ 旧口径废弃声明（第80轮，用户裁决 ③「**废除**」）：
    #:   本常量**只服务桌宠本人**（`go_to_bed()` 读它；他住在桌面 = `_index.json`
    #:   的 `default_scene`）。
    #:   **NPC 完全不适用** —— NPC 的「今晚睡哪」是**逐人决策**，真源 =
    #:   `npc_intent.choose_sleep_scene()`（L4：不硬性回家，熟人够熟可睡朋友家），
    #:   经 `main._npc_roam_sleep` 注入 `npc_roam.step(sleep_fn=...)`。
    #:   ⇒ 别再往这里加 NPC 相关分支；改 NPC 就寝请改 `choose_sleep_scene`。
    BEDTIME_CHECK_INTERVAL = 5.0         # 判定节拍（秒）；窗口 ±10 分钟，5s 精度绰绰有余

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
            # 等着回复（还在等首字）：事件台词会把它顶掉。
            # ★★ 第75轮改判据：原来靠"前台是「……」占位串"来判断，
            #    但用户裁定关掉思考占位 ⇒ 占位串不再出现 ⇒ 该判据**会恒假**
            #    （等回复时事件台词就能插进来，把对话框顶掉）。
            #    正解 = `dialogue_ui._ai_pending`（显式状态位，与显示内容解耦）。
            #    兼容：老版本没有这个属性时，退回原来的占位串判据。
            if getattr(dui, '_ai_pending', None) is None:
                if getattr(dui, 'typing_text', '') == getattr(
                        dui, 'AI_THINKING_PLACEHOLDER', None):
                    return False
            elif dui._ai_pending:
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
        
    # ========================================================================
    # ★★ 宠物手势接线（第75轮 B3）—— 三件套：同步精灵 / 坐标换算 / 事件分派
    # ========================================================================
    #
    # 为什么需要"坐标换算"这一层：
    #   `pet_interaction` 收到的是**相对精灵左上角的像素**（它会用它去除以
    #   精灵宽高得到百分比，也会去查 alpha 遮罩）。而 Qt 给到事件回调的
    #   `event.pos()` 是**相对窗口**的。`sprite_label` 的 geometry 是
    #   `(0, 0, 100, 100)`，但 pixmap 是按角色 alpha 包围盒**居中锚定**的
    #   （见 `_compose_anchored_sprite`），所以不能简单用 `event.pos()`。
    #
    # 真源的一致性：
    #   改造前 `get_ralsei_body_part` 用的是
    #     `rel = pos / sprite_label.size() * 100`
    #   即"相对 label 的百分比"。本层同样换算到相对 label 的像素 ——
    #   与模块内 `classify()` 的 `x / self._width * 100` 复合后**完全等价**。

    def _sync_pet_tracker_sprite(self):
        """把当前精灵帧交给 tracker（重建 alpha 遮罩 + 尺寸）。

        ★ 调用时机：每次 `sprite_label.setPixmap(...)` 之后。
          不刷新的话，换动画后 tracker 仍按**上一帧的尺寸**算百分比，
          部位识别会在动画切换后整体偏移（改造前用 `sprite_label.size()`
          每次现算，所以没这个问题 —— 这是接线时**唯一必须补**的一环）。
        """
        try:
            pm = self.sprite_label.pixmap()
            if pm is None or pm.isNull():
                self._pet_tracker.set_sprite(None)
            else:
                self._pet_tracker.set_sprite(pm)
        except Exception as e:
            _log.debug("同步手势精灵失败（已忽略）: %s", e)

    def _pet_rel_pos(self, pos):
        """窗口坐标 → 相对精灵的像素坐标；不在精灵矩形内返回 None。"""
        try:
            geo = self.sprite_label.geometry()
            if not geo.contains(pos):
                return None
            return (float(pos.x() - geo.x()), float(pos.y() - geo.y()))
        except Exception:
            return None

    def _apply_pet_response(self, kind):
        """按 `kind` 查 `RESPONSE_SPEC` 执行情绪 / 动画 / 台词（第75轮 B3）。"""
        spec = RESPONSE_SPEC.get(kind)
        if spec is None:
            return
        emotions, anim, face, pool = spec
        try:
            for name, val in emotions:
                self.emotion_system.add_emotion(name, val)
            if anim:
                self.play_animation_once(anim)
            self.speak_event(kind, pool, face)
        except Exception as e:
            _log.debug("宠物回应执行失败（已忽略）: %s", e)

    def _dispatch_pet_event(self, ev):
        """`PetEvent` → 执行层。返回 True 表示"这个事件已被处理"。"""
        if ev is None:
            return False
        if ev.gesture == Gesture.STROKE:
            # 抚摸：情绪是**所有部位共用**的，台词按部位取
            try:
                for name, val in STROKE_EMOTIONS:
                    self.emotion_system.add_emotion(name, val)
            except Exception as e:
                _log.debug("抚摸情绪失败（已忽略）: %s", e)
            kind = kind_for(ev.body_part, ev.gesture)
            pet_name = kind[4:] if (kind or "").startswith("pet_") else "other"
            pool = STROKE_POOL.get(pet_name, STROKE_POOL_OTHER)
            self.speak_event(kind or "pet_other", pool, "happy")
            return True
        kind = kind_for(ev.body_part, ev.gesture)
        if kind is None:
            return False
        self._apply_pet_response(kind)
        return True

    def get_ralsei_body_part(self, pos):
        """窗口坐标处的身体部位名（字符串）。**已委托给 tracker**（第75轮 B3）。

        ★ 改造前这里有 12 条区域的手写表 + 百分比换算（约 58 行），与
          `pet_interaction._REGIONS_PERCENT` 是**同一条规则的第三份拷贝**
          （第一份在模块、第二份在本文件）——两份区域表一旦不同步
          （改造前就有：本文件是 `belly`/`body`/`legs`，模块是 `torso`/`leg`，
          且阈值 25/10/75/50 vs 22/5/78/42 不同），"点击哪里"取决于走哪条路径。
          现统一走 `BodyRegionMapper.classify()`。

        ★ 本函数**保留为薄委托**而不是删除：它被 `mousePressEvent` 等处当
          "局部名"用过，且改造前返回的是**字符串**（`"ear"`），而模块返回
          `BodyPart` 枚举 ⇒ 这里做一次 `.value` 转换，保持调用方无需改动。

        ⚠️ 语义差异（**已登记，不是 bug**）：改造前本函数**不看 alpha 遮罩**
          （只要落在矩形里就算命中）；现在模块会先查 alpha —— 点在角色图
          **透明像素**上（如两耳之间的空隙）不再算"点在身上"。这正是
          `pet_interaction` 存在的价值（"只将鼠标落在非透明区域的事件视为
          在宠物身上"），但会让"点在空白处"从 `whole_body` 变成"未命中"。
        """
        rel = self._pet_rel_pos(pos)
        if rel is None:
            return BodyPart.WHOLE_BODY.value
        return self._pet_tracker.region.classify(rel[0], rel[1]).value

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

                # ★★ 手势判定交给 tracker（第75轮 B3）。
                # 注意 `handle_press` 只记录"按下了哪里"、**不产生事件** ——
                # 事件（PUSH / PINCH / PULL）在 `mouseReleaseEvent` 里由时长与
                # 位移区分后一次性返回。这样"点一下"不会在按下瞬间就说话，
                # 也给"按住拖着走"留出了不误触的余地。
                rel = self._pet_rel_pos(event.pos())
                if rel is not None:
                    self._pet_tracker.handle_press(rel)
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

                # ★★ 抚摸 / 拖拽中的按下移动，一律交给 tracker（第75轮 B3）。
                # 改造前这里有一整套手写的"移动历史 + 方向反转计数 + 冷却"抚摸
                # 检测（约 100 行，含 15 条 history、changes>=2、1.5s 冷却），
                # 与 `pet_interaction._StrokeDetector`（30 条 history、
                # changes>=3、1.5s 冷却）是**同一条规则的第三份拷贝**。
                # 现统一走模块，并让 `_dispatch_pet_event` 执行。
                rel = self._pet_rel_pos(event.pos())
                if rel is not None:
                    ev = self._pet_tracker.handle_move(rel)
                    if ev is not None:
                        self._dispatch_pet_event(ev)

                # 优化：降低鼠标悬停事件的触发频率
                if not hasattr(self, '_last_hover_time') or time.time() - self._last_hover_time > 0.5:
                    self.on_mouse_hover()
                    self._last_hover_time = time.time()
            else:
                # 鼠标离开Ralsei，恢复默认鼠标样式
                if current_cursor.shape() != Qt.ArrowCursor:
                    self.setCursor(Qt.ArrowCursor)

                # ★ 离开精灵 ⇒ 也要告诉 tracker（它会复位抚摸检测器）。
                # 改造前是靠 `_pet_detection_state['on_ralsei']=False` + 清空
                # movement_history 达到同样效果。这里传"精灵外的坐标"即可让
                # `handle_move` 走 `is_on_pet=False` 分支并复位。
                self._pet_tracker.handle_move((-1.0, -1.0))

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
            # ★★ 手势结算交给 tracker（第75轮 B3）。
            # `handle_release` 会按"按下时长 + 期间是否移动"返回：
            #   时长 ≥ 0.5s 且移动过 → PULL；时长 ≥ 0.5s 未移动 → PINCH；
            #   未达时长 → PUSH / PAT / FLICK（连击）之一。
            # 改造前这里是一段 60 行的 `if press_duration >= 0.5:` + 6 个部位分支，
            # 与 `mousePressEvent` 里的单击分支、`pet_interaction.GestureTracker`
            # 三处各写一遍同一件事。现由模块统一判定，本函数只负责"执行"。
            #
            # ⚠️ 坠落 / 甩飞中不结算手势（改造前的同一保护：`not is_falling`）——
            #    否则"空中接住后再松手"会被当成一次点击。
            if not getattr(self, 'is_falling', False):
                rel = self._pet_rel_pos(event.pos())
                if rel is not None:
                    ev = self._pet_tracker.handle_release(rel)
                    self._dispatch_pet_event(ev)
                else:
                    # 在精灵外松手：仍然要清掉按下态（否则下一次按下会被
                    # 当成"同一次长按的延续"，改造前靠 `_pet_detection_state`
                    # 的 is_pressing 复位做到，这里等价处理）。
                    self._pet_tracker.gesture.is_pressing = False
    
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
            # ★★ 双击（PAT）交给 tracker（第75轮 B3）。
            # 改造前这里是一段 40 行的 `if clicked_part == "hair" … else
            # double_other`，与 `RESPONSE_SPEC` 里的 `double_*` 四项逐字重复。
            #
            # ⚠️ 双击的**判定**仍由 Qt 自己给（`mouseDoubleClickEvent`），
            #    不必让 `GestureTracker` 去猜 —— 但 tracker 的"连击计数"
            #    也会在两次单击后返回 FLICK/PAT。为避免**同一组双击被处理两遍**
            #    （一次来自这里、一次来自 release 的连击计数），这里只做
            #    "按部位取 `double_*` kind 并执行"，**不**走 tracker 的手势机。
            #    ⇒ 双击语义的**唯一入口 = 本函数**，单击/长按/抚摸的唯一入口
            #      = release/move。两者互不重叠。
            rel = self._pet_rel_pos(event.pos())
            part = BodyPart.WHOLE_BODY
            if rel is not None:
                part = self._pet_tracker.region.classify(rel[0], rel[1])
            kind = kind_for(part, Gesture.PAT)
            _log.debug("双击了Ralsei的: %s", part.value)
            if kind:
                self._apply_pet_response(kind)
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

        # ★ 第76轮 R0-1：去别的场景（用户口径「一句话入口 + 能走能切」）。
        #   菜单里给的是**当前章内可达目的地**（数据来自 scene_controller，
        #   解析口径与"一句话入口"共用同一条 `resolve_destination`，不新造一套）。
        try:
            dests = self.scene.reachable_destinations(limit=20)
        except Exception:
            dests = []
        if dests:
            go_menu = menu.addMenu("去…")
            for rec in dests:
                act = QAction(rec.get('label') or rec.get('scene_id'), self)
                act.triggered.connect(
                    lambda _checked=False, sid=rec.get('scene_id'): self.travel_to_scene(sid))
                go_menu.addAction(act)
            back_action = QAction("回桌面", self)
            back_action.triggered.connect(lambda: self.travel_to_scene('desktop'))
            go_menu.addAction(back_action)
        
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
        # 第58轮：client 换了就必须同步保温看门狗（它握着 client 引用；
        # 不同步 = 旧看门狗继续对着旧 base_url 发请求）。
        self._sync_warm_keeper()
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
        # ★★ 第52轮：`hide_and_seek` **从"随机挑一个"的名单里移除**。
        # 用户口径逐字：「他捉迷藏只是用户提出来才能玩而且必须是在桌面上」。
        # 原实现是"点一次『玩游戏』随机抽"，抽到躲猫猫就会满地变出障碍物文件夹 ——
        # 那属于"没提也玩"。现在只有两条**明确提出**的路进来：
        #   ① 主人在输入框里说「躲猫猫 / 捉迷藏」（dialogue_ui 的 _HARD_CMDS）；
        #   ② 主人在输入框里说「玩躲猫猫」这类指令（command_manager）。
        # 两道门之外，hide_controller.start_hide_and_seek_game 还有"必须在桌面"的闸。
        games = ["dance", "sing", "chase_cursor", "rock_paper_scissors", "guess_number"]
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
        # ★ 第52轮：原 `elif game == "hide_and_seek":` 整段已删除 ——
        #   `games` 名单里不再含躲猫猫，这个分支永远走不到；留着就是死代码。
        #   （历史说明：那一段原本修过"只弹对话不启动"的 bug，现在由
        #     "明确提出才玩"的新口径取代，弹的那句内置台词也一并去掉。）
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
            # 第58轮：同"保存配置"那处 —— client 一换就得同步保温看门狗。
            self._sync_warm_keeper()
            
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

    def chat_with_ai(self, text, on_reply, on_delta=None, lean=False,
                     speaker=None, system_override=None, remember=True,
                     model=None):
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
        - ★ **`speaker`（第55轮）**：这一轮开口的是谁。
          `None` / `'ralsei'` ⇒ 老路径，**一个字节都不变**（人设、上下文、话题锚、
          记忆召回、关系、历史、护栏比对集合全部照旧）。
          传了别的 id ⇒ NPC 路径：system 只由 `npc_system_prompt()` 装配
          （人设 + 他自己的记忆 + 共有的环境），**且回复只写进他自己的记忆**。
          ★ 为什么 NPC 路径连"关系档位 / 世界观召回 / 话题锚"都跳过：
            这些状态全都归属 **Ralsei 本人**（信任度是对主人的、话题锚是这一场对话的）。
            给 NPC 挂上去，就会听到"苏西"用自己的口吻讲出 Ralsei 和主人的关系 ——
            那正是用户说的「葫芦娃千里眼顺风耳」。
        - ★ **`system_override`（第55轮）**：直接指定 system（用于"跟随决策"这种
          一问一答、不值得跑整套装配的场合）。给了它就**跳过全部装配**。
        - ★ **`remember`（第55轮）**：NPC 路径下"要不要把这一问一答记进他自己的记忆"。
          跟随决策是**内部问句**（"跟不跟？"不是台词），它必须显式传 `False`：
            ① 把"follow"这种单词记成他说过的话，下一次拼 prompt 会显得莫名其妙；
            ② 更要命的是护栏的"车轱辘话"判定会拿它当历史 —— 同一个决策词被问两次时
               第二次会被判成"重复自己"直接判退，决策就**静默退回分层策略**了。
        - ★ **`model`（第55轮）**：**按请求**覆盖 Ollama 模型名。
          `None` / 空串 ⇒ 不覆盖，用 `config.json` 的 `api.model`（**Ralsei 与 NPC
          共用同一个**）—— 也就是说 NPC 拿到的本就是 7B（`ralsei:v4` = qwen2.5:7b）。
          为什么保留这个口子：`assets/npc/_registry.json` 每条 NPC 都有自己的 `model`，
          不接线的字段就是"登记了没人读"的假账（见 `api_client._chat_payload` 的注释）。
          当前注册表里该字段**故意全为 `None`**：不额外常驻第二份 7B 权重，
          真需要单独换模型时填一个 Ollama 里真实存在的句柄即可。
        """
        # ★ 第55轮：这一轮是不是 NPC 在说话（`''` 与 `'ralsei'` 都算老路径）
        _npc_id = speaker if (isinstance(speaker, str) and speaker
                              and speaker != 'ralsei') else None
        _is_npc = _npc_id is not None
        _sys_fixed = _is_npc or (system_override is not None)
        # NPC 回复要在**主线程**里落进他自己的记忆（工作线程绝不碰共享状态）
        if _is_npc and remember:
            _npc_reply_cb = on_reply

            def on_reply(_resp, _npc_id=_npc_id, _cb=_npc_reply_cb):  # noqa: F811
                """★ NPC 的回复先落进**他自己**的记忆，再交给上层显示。

                为什么在这里（而不是工作线程里）：`MiniMemory` 不是线程安全的，
                而这条回调经 Qt 队列投递、**在主线程**执行；工作线程只负责推理。
                """
                try:
                    if isinstance(_resp, str) and _resp.strip() \
                            and self.npc_memory is not None:
                        self.npc_memory.remember(
                            _npc_id, _resp, who=_npc_id, scene=self._npc_scene_id())
                        self.npc_memory.save(_npc_id)
                except Exception as e:
                    _log.debug('NPC %s 记忆落盘异常（已忽略）: %s', _npc_id, e)
                if _cb is not None:
                    _cb(_resp)

        # 载体层状态：记下"主人刚开口"的时刻。主线程写、主线程读（本方法在主线程调用），
        # 供 _build_ai_context 派生"被冷落多久"这类语气 —— 模型自己看不到时钟，
        # 也看不到"主人已经很久没理我"这种**跨轮**事实，这类状态只有 App（载体）持有。
        # 刻意放在 api_enabled 判断**之前**：AI 关着的时候也要记，否则一关开关就"失忆"，
        # 再打开会立刻说"主人很久没跟我说话了"（把开关当成冷落）。
        # ★ 第55轮：**只对 Ralsei 记**。它是"主人和 Ralsei 之间"的事实，
        #   跟 NPC 聊两句不该让 Ralsei 觉得"刚才跟你聊过"（状态层面的串味）。
        if not _is_npc:
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
        # ★ 第74轮（B9）：**只有带接收方的请求才占槽**（连"槽世代"一起推进）。
        #   无 on_delta 的后台请求以前会把槽覆盖成 None —— 前台的分片就再也写不出来。
        if _stream_on:
            self._ai_delta_sink = on_delta
            self._ai_delta_sink_gen = _gen

        # —— 主线程先准备好上下文与历史（避免工作线程跨线程读 UI/子系统状态）——
        # 第十八轮：用户消息保持**纯原话**。【此刻】/话题锚/记忆召回一律挂到 system 尾部。
        # 实测把它们拼在用户消息前面时，模型会把它当成"用户说的那段话"，
        # 甚至直接复述成回答（见 Ralsei对话人味诊断与训练方案_2026-09-18.md §E4-V0）。
        user_msg = text
        history = []
        # lean（事件台词）**不发历史**：历史每轮都在变，同样让前缀缓存失效
        # （实测 +0.52s），而且触点反应本来就不需要"接着上一句说"。
        # ★ 第55轮：`_sys_fixed`（NPC / 自定义 system）也不发 ——
        #   NPC 的历史已由 `npc_system_prompt()` 折进他自己的 system，
        #   而 `dialogue_ui` 的历史是 **Ralsei 的**，取来就是把别人的记忆喂给他。
        if not lean and not _sys_fixed:
            try:
                history = self.dialogue_ui.get_ai_history(limit=6) \
                    if getattr(self, 'dialogue_ui', None) else []
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("main 防御性异常（已忽略）: %s", e)
        # NPC 路径的护栏比对集合 = **他自己**说过的话（不是 Ralsei 的历史）。
        # 在主线程先取快照：`MiniMemory` 非线程安全，工作线程只读这份快照。
        _npc_recent = []
        if _is_npc:
            try:
                _npc_recent = [it.get('text') for it in
                               self.npc_memory.history(_npc_id, limit=12)
                               if isinstance(it, dict) and it.get('who') == _npc_id]
            except Exception as e:
                _log.debug("main 防御性异常（已忽略）: %s", e)
        # 角色系统提示词：**单一真源 = assets/ralsei_persona.md**（内含"我是谁 /
        # 我现在在哪 / 我怎么说 / 示范"四节）。
        # 为什么必须由 App 发过去：实测 Ollama 会用 messages 里的 system **整体替换**
        # Modelfile 的 SYSTEM（不传 system 时角色设定生效 prompt_eval_count=1237，
        # 传了之后骤降到 41）——也就是说，只把设定写在模型的 Modelfile 里，
        # 在真实应用里**一次都不会生效**。
        # ★ 第55轮：`_sys_fixed` 时 system 由别处给定，这里**不覆盖**。
        if _sys_fixed:
            if system_override is not None:
                system = str(system_override)
            else:
                system = self.npc_system_prompt(_npc_id)
                if not system:
                    # 没登记 / 没装设定 ⇒ **明确沉默**。
                    # 不许退回 Ralsei 的人设：那会让"苏西"用雷尔赛的口吻说话，
                    # 而用户看不出这是降级（正是最该防的那种假象）。
                    _log.info('NPC %s 没有 system（未登记或没装设定）⇒ 这一句不说话', _npc_id)
                    on_reply(None)
                    return
        else:
            system = self._build_persona_prompt()
        # lean（事件台词）：**只发 persona，一个字节都不变** → 每次事件都命中
        # KV 前缀缓存 → 首字回到 0.6s 量级（实测见 docstring 的 probe 出处）。
        # 注意这里连 `_build_ai_context()` 都跳过：它内部会读天气/情绪/记忆，
        # 开销虽小但**每轮结果不同**，挂了就等于把缓存打掉。
        _ctx = "" if (lean or _sys_fixed) else self._build_ai_context()
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
        if _focus and not lean and not _sys_fixed:
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
        if _recall and not lean and not _sys_fixed:
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
            if not lean and not _sys_fixed:
                _wv = getattr(self, '_worldview_recall_text', None)
                if not callable(_wv):
                    from modules import worldview_recall as _wr
                    _wv = _wr.recall_text
                    self._worldview_recall_text = _wv
                _wv = _wv(text, limit=2)
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            _wv = ""
        if _wv and not _sys_fixed:
            system = system + "\n\n" + _wv

        # 关系（第二十轮）：把**当前档位**变成一句话挂进 system。
        # 位置刻意在所有"临时状态"（【此刻】/话题锚/回忆/想起的事）**之前** ——
        # 关系比这些变化得慢得多，放在前缀更靠前的位置，跨轮更容易保持逐字相同，
        # KV 缓存复用得更长（Ollama 只复用"从头逐字相同"的那一段）。
        # lean（事件台词）跳过：事件是 ≤24 字的触觉反应，装不下"态度的差别"，
        # 而且它每轮都要重算 —— 那正是 S7 首字兜底要避开的东西。
        # 记账也放在这里：**只有真发起了一轮对话才算一次相处**（见下）。
        _rel_brief = ""
        _nerv_brief = ""
        try:
            _rel = getattr(self, 'relationship', None)
            if _rel is not None and not lean and not _sys_fixed:
                # 先记账再取 brief：这样"这一轮"的影响立刻体现在语气上，
                # 而不是延迟一轮（用户能感知到的延迟 = "他反应慢半拍"）。
                # 事件类型由轻量规则判定（modules/relationship.classify），
                # 确定性、可回归；判错也只是多涨/少涨一点点，不会走样。
                from modules import relationship as _relmod
                _ev = _relmod.classify(text)
                _old_st, _new_st, _delta = _rel.note(_ev)
                # ★ B4（第75轮）：关系段之后追加**当下状态段**（紧张度）。
                #   用户口径「结巴…这有点不好」⇒ 减少但不许到 0；人设原文
                #   「越紧张越明显，平常聊天基本不结巴」⇒ 结巴由**紧张度**驱动。
                #   ⚠️ 两段**分开追加**而不是并进 `brief()`：它们变化节奏不同 ——
                #     关系档位很慢、紧张度逐轮跳动。KV 前缀复用只认"从头逐字相同"，
                #     把易变段并进稳定段会把整段关系前缀一起作废（第30轮的教训）。
                #   ⚠️ `_ev` 必须传进去：紧张度 = 档位基线 + 本轮事件瞬时影响，
                #      "被凶了会慌"这条正是由此落地（见 `_EVENT_NERVOUSNESS`）。
                _rel_brief = _rel.brief()
                _nerv_brief = _rel.nervous_brief(_ev)
                if _old_st != _new_st:
                    _log.info("[关系] 档位变化 %s → %s（%s）",
                              _old_st, _new_st, _rel.describe())
                try:
                    _log.debug("[关系] 紧张度=%.3f（事件=%s）",
                               _rel.nervousness(_ev), _ev)
                except Exception:
                    pass
                try:
                    _rel.save()
                except Exception as e:
                    _log.debug("main 防御性异常（已忽略）: %s", e)
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            _rel_brief = ""
            _nerv_brief = ""
        if _rel_brief:
            system = system + "\n\n" + _rel_brief
        # ★ B4：当下状态段紧跟在关系段之后（同一处追加点，少一层心智负担）。
        if _nerv_brief:
            system = system + "\n\n" + _nerv_brief

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
        if history and not lean and not _sys_fixed:
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
                # ★ 第55轮：按请求覆盖模型名（NPC 自己的 `model` 字段真被读到这里）。
                #   只在**给了非空字符串**时才塞进 opts —— 否则键都不出现，
                #   `api_client._chat_payload` 走"不覆盖"分支，老路径逐字不变。
                if isinstance(model, str) and model.strip():
                    opts['model'] = model
                # 最近说过的台词（车轱辘话判定的唯一比对集合，见 _is_repeat_of_recent）
                # ★ 第55轮：NPC 路径取**他自己**说过的话（`_npc_recent`，主线程取的快照）——
                #   拿 Ralsei 的历史来判，等于用别人的话去"抓"他的重复。
                recent = (list(_npc_recent) if _is_npc
                          else [c for _r, c in history if _r == 'assistant'])
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
        # ★★ 场景分片（第75轮补）：**"我现在在哪"**。
        #
        # 为什么必须补：产品的核心口径是"把原作的世界搬到桌面上，桌面也是一个场景"
        # （第 42~50 轮已把 1,014 个原作场景接进来）。可 `_build_ai_context()`
        # 里**从来没有"我在哪"** —— AI 只知道"站在桌面上"，不知道桌面上开着的是
        # 城堡镇还是黑暗世界。于是用户说"咱要不去城堡镇吧"，AI 只能当成抽象愿望，
        # 回一句"不要放弃，继续努力"这种通用鼓励。
        #
        # ★ `SceneState.describe()` 是第 36 轮就写好的**唯一入口**（注释原文：
        #   "给 AI 上下文注入用的唯一入口"），但一直没有消费者 —— 这里把它接上，
        #   **不自己拼场景名**（规则只留一份真源）。
        # ★ 取空串/取不到 ⇒ **整段省略**（`describe()` 的契约），不注入
        #   "我在某个地方"这种废话。
        try:
            _scene = self.__dict__.get('_scene_state')
            _where = _scene.describe() if _scene is not None else ''
            if _where:
                if _where == '桌面':
                    parts.append("你在桌面上")
                else:
                    parts.append(f"你此刻在{_where}")
        except Exception as e:
            _log.debug("AI 上下文：场景分片获取失败（已忽略）: %s", e)
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

    #: ★★★ 第81轮（层4 存档）：NPC「生活档案」落盘文件（走 `data_store` 唯一存储入口，
    #:   与 `RELATIONSHIP_FILE` / `GHOST_FILE` 同规）。
    #:   装的东西 = 三份**此前只在内存**的状态：
    #:     · `npc_roam.RoamState` 的驻留覆盖表（"他此刻偏离了自己家"）；
    #:     · 每人的 `npc_intent.Plan`（今日意图 / 最近 12 条历史 / **昨晚睡哪**）。
    #:   ★★ 为什么必须有它：`choose_sleep_scene(last_sleep=...)` 的"连睡同一处 ×0.6
    #:      降权"在层4 之前**永远拿不到值**（`last_sleep` 恒 `None`）⇒ 降权形同虚设；
    #:      NPC 一重启就把"昨天睡在朋友家"忘干净。
    #:   ★ 真源文件名在 `npc_plan_store.FILENAME`（这里**不**复制一份，避免两处算）。
    #:     本常量只是给 host 侧一个"这套存档叫什么"的锚点（与 `GHOST_FILE` 同形），
    #:     `npc_plan_store.FILENAME` 与它**必须一致**（`check81` 会断言）。
    NPC_LIFE_FILE = 'npc_life.json'

    # 角色设定相对路径（相对 src/ 的上一级，即仓库内 ralsei_pet/assets/）
    PERSONA_REL_PATH = os.path.join('assets', 'ralsei_persona.md')

    # 兜底人设：persona 文件缺失/读失败时使用，保证对话链路不因人设丢失而失常
    # ⚠️ 这份兜底**必须和 assets/ralsei_persona.md 的关系口径保持一致**（在哪 / 平级 / 无使命），
    # 否则 persona 一旦读取失败，模型会立刻退回"主人/陪伴任务"那套旧叙事 ——
    # 而这条退化路径在正常运行时**看不见**（A 组锁测的是真源文件，不是这份字符串）。
    #
    # ★★ 第75轮同步：真源「我现在在哪」节已按用户裁定重写为
    #    「我住在黑暗世界，桌面是那扇窗」。兜底若还留着"你现在在这台电脑的桌面上"，
    #    就正好落在用户抱怨的那句「咱要不去城堡镇吧 → 不要放弃继续努力」的病根上
    #    （AI 不知道自己住在哪 ⇒ 把地名当抽象愿望）。**这份兜底也一起对齐。**
    # ⚠️ 注意：J1 判据（verify_persona_chat.py）钉的就是这份字符串，改的时候
    #    「不用叫他」/「仅此而已」/「平级」三个锚必须仍在，否则 J1 会连带报红。
    _PERSONA_FALLBACK = (
        "你是《Deltarune》中的 Ralsei：温柔、善良、害羞、体贴的和平主义者。"
        "你住在黑暗世界里（城堡、喷泉、那片没有星星的夜空），"
        "你现在待的地方是屏幕这一头的\"窗\"（对方的桌面）—— 你随时可以带他看看你那边。"
        "谁也没有非让你来不可的理由 —— 你就是来了，仅此而已。"
        "在屏幕另一头跟你说话的人是真实世界的人、不是 Kris，和你平级的，"
        "不用叫他\"主人\"，也不用替他操心什么；他有名字就叫名字，没名字就说\"你\"。"
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
        端点 /v1/chat/completions，实测该端点会**静默忽略**这两个参数 —— 无论放
        顶层还是塞进 options 都一样。所以只能写进 assets/ralsei_v4.modelfile 的
        PARAMETER（也只有那样才在换底座时不会被漏掉）。

        ⚠️ 第58轮更正：这里原先接着写"长提示词都恒定截断在 ~2050 tokens"，
        **对 Ollama 0.34.4 已经不成立**。同一段人设（3604 字）：兼容端点报
        `usage.prompt_tokens=2371`、原生端点报 `prompt_eval_count=2371`，
        **逐字相等、没有任何截断**；且兼容端点还会回
        `prompt_tokens_details.cached_tokens`（实测 2370）⇒ 说明
        num_ctx=8192 这条 PARAMETER 在兼容端点上**也生效了**。
        证据：code-quality-audit/第58轮-模型常驻与预热/_evidence/compat_truncation.json
        ⇒ 要判"到底喂进去多少 token"，直接读 `usage.prompt_tokens`，
        别再靠推断：把一个过期的数字当常量，会把"其实没被砍"误判成"反正会被砍"。
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

    # ---------------- 保温 / 预热（第58轮） ----------------
    def _sync_warm_keeper(self):
        """按配置启停保温看门狗（`api.keep_warm` / `api.keep_alive` / `api.keep_warm_poll`）。

        ★ 为什么必须"client 重建后立刻再调一次"：`self.api_client` 是**运行时快照**
          （见 api_client.py 文件头第 1 条注释）；配置一改就换了个新对象，
          旧看门狗还握着旧的 —— 又一处「函数写对了 ≠ 产品用上了」。
          所以 main.py 里 `create_client` 的**三个**调用点后面都跟了本方法。

        用**鸭子类型**而不是 isinstance：用户可以用 register_provider 注册自己的实现，
        只要实现了 loaded_models() / ensure_keep_alive() 这两个方法就自动获得保温能力
        （没实现就安静地不保温、绝不报错 —— 协议留白是 api_client 的既有约定）。
        """
        try:
            old = getattr(self, '_warm_keeper', None)
            if old is not None:
                old.stop()
            self._warm_keeper = None
            cfg = getattr(self, 'api_config', None)
            if not isinstance(cfg, dict) or not cfg.get('enabled'):
                return
            if not cfg.get('keep_warm', True):
                return
            ka = cfg.get('keep_alive', '')
            if ka is None or ka == 0 or (isinstance(ka, str) and not ka.strip()):
                return          # 留空/0 = 明确表示"不设"，回到 Ollama 默认 5 分钟
            cli = getattr(self, 'api_client', None)
            if cli is None or not hasattr(cli, 'loaded_models') \
                    or not hasattr(cli, 'ensure_keep_alive'):
                return
            self._warm_keeper = WarmKeeper(cli, keep_alive=ka,
                                           interval=cfg.get('keep_warm_poll', 30))
            self._warm_keeper.start()
            _log.info('保温看门狗已启动：keep_alive=%s（只在模型"新载入"时设一次）', ka)
        except Exception as e:   # 保温是优化，绝不能拖垮配置保存/启动
            _log.debug("main 防御性异常（已忽略）: %s", e)

    def _prewarm_ai_cache(self):
        """启动预热（`startup.prewarm`，默认 false）。

        口径与事件台词那条路径**完全一致**：只发 persona，一个字节都不变
        （见 chat_with_ai 里 lean=True 的注释）—— 这样预热命中的前缀与真实对话
        是**同一段字节**，用户第一句话就直接吃缓存。

        实测代价（第58轮）：人设 2371 token 冷 prefill 55.8s（23.5 ms/token），
        热 0.149s（快 375 倍）。这个开关买的就是把"用户开口先等一分钟"
        换成"启动时后台付掉"。

        超时用 `startup.prewarm_timeout`（默认 180s）而**不是**对话的 timeout：
        冷 prefill 远超 30s，拿对话预算去发预热会被自己的客户端判成超时（假失败）
        —— 为此本轮顺便给 `chat()` 加了按请求超时（见 api_client.py）。
        """
        if getattr(self, '_prewarm_started', False):
            return
        self._prewarm_started = True
        try:
            if not bool(self.config_manager.get('startup.prewarm', False)):
                return
            cli = getattr(self, 'api_client', None)
            if cli is None or not getattr(cli, 'enabled', False):
                return
            timeout = float(self.config_manager.get(
                'startup.prewarm_timeout', 180) or 180)
        except Exception as e:   # 配置异常 ⇒ 静默不预热，绝不弹错
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return

        def _worker():
            try:
                system = self._build_persona_prompt()
                opts = self._ai_chat_options()
                # 只发 persona、只要 1 个 token：目的是让 prefill 进缓存，不是要内容。
                t0 = time.time()
                cli.chat('嗯。', system_prompt=system,
                         temperature=opts.get('temperature', 0.7),
                         max_tokens=1, timeout=timeout)
                _log.info('启动预热已发出，用时 %.1fs（此后同一段 persona 前缀应命中缓存）',
                          time.time() - t0)
            except Exception as e:
                _log.info('启动预热失败（忽略，不影响使用）: %s', e)
            # ★ 第74轮（B8）：Ralsei 之后接着预热 NPC（**主角团 → 同场 → 其余**）。
            #   开关与范围各自独立：`startup.prewarm_npc` / `startup.prewarm_scope`。
            try:
                if bool(self.config_manager.get('startup.prewarm_npc', False)):
                    _scope = self.config_manager.get('startup.prewarm_scope', 'all') or 'all'
                    self._prewarm_npc_caches(cli, timeout, _scope)
            except Exception as e:
                _log.debug('NPC 预热异常（忽略）: %s', e)

        threading.Thread(target=_worker, name='AiPrewarm', daemon=True).start()

    # ---- ★ 第74轮（B8）：NPC 预热（主角团优先，尽量全）----
    def _prewarm_team_ids(self):
        """主角团 id。真源 = `_placement.json` 的 `groups[id=party].members`。

        ★ 不在这里另抄一份名单 —— 抄了就是**两个真相**（改一处漏一处）。
        取不到（数据缺/桩环境）⇒ 返回空表，预热退化成"同场优先"，不编造。
        """
        try:
            book = getattr(self, 'npc_placement', None)
            rig = book.rig('party') if book is not None else None
            members = [m for m in (getattr(rig, 'members', None) or ())
                       if isinstance(m, str) and m]
            if members:
                return members
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        return []

    def _prewarm_should_yield(self):
        """预热要不要让路（= 用户此刻正在说话 / 等在回复 / 有事件台词在说）。

        ★ 判据只用**对话状态位**，**绝不**用 `_ai_delta_sink`：它收尾刻意不清空
          （见 `_on_api_delta` 的说明），拿它当门会**永久为真** —— 这正是 D22 钉的那类坑。
        """
        try:
            dui = getattr(self, 'dialogue_ui', None)
            if dui is not None:
                if getattr(dui, '_ai_inflight', False):
                    return True
                if getattr(dui, '_streaming', False):
                    return True
            if getattr(self, '_event_speaking', False):
                return True
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        return False

    def _prewarm_npc_caches(self, cli, timeout, scope='all'):
        """★ 第74轮（B8）：一次一个 NPC 地预热（**串行 + 让路**），返回预热成功数。

        为什么"一次一个"而不是并发：Ollama 纯 CPU + `NUM_PARALLEL=1` ⇒ 并发只是
        **排队**（第57轮实测 `wall ≈ Σ(prefill+decode)`）；而且并发会让"让路"彻底失效 ——
        一次只发一个，用户开口时最多多付**当前这一个**的 prefill。

        ★ 如实标注物理上限：已经发出去的那个 HTTP 请求**无法中止**（`cli.chat` 是阻塞的）
          ⇒ "让路"的粒度 = 单个 NPC，而不是"立刻停"。这不是没做，是做不到。
        """
        try:
            ids = [n for n in (self.npc_personas or {}) if self.npc_persona_of(n)]
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return 0
        try:
            here = self._npc_life_ids()
        except Exception:
            here = []
        if scope == 'same_scene':
            _here = set(here)
            ids = [n for n in ids if n in _here]
        order = prewarm_order(ids, team=self._prewarm_team_ids(), here=here)
        if not order:
            _log.info('NPC 预热：没有可预热的对象（人设/场景为空）')
            return 0
        try:
            opts = self._ai_chat_options()
        except Exception:
            opts = {}
        t0 = time.time()
        done = skipped = 0
        for nid in order:
            if self._prewarm_should_yield():
                _log.info('NPC 预热让路：你开始说话了，剩余 %d 个不再预热',
                          len(order) - done - skipped)
                break
            try:
                system = self.npc_system_prompt(nid)
            except Exception as e:
                _log.debug('NPC %s 预热取 prompt 失败（跳过）: %s', nid, e)
                skipped += 1
                continue
            if not system:
                skipped += 1          # 没装人设 ⇒ 不预热（不许借别人的设定开口）
                continue
            try:
                # 与真实对话是**同一段 system**（`npc_system_prompt` 是唯一出口）⇒
                # 预热命中的前缀就是用户开口时要用的那一段。只要 1 个 token：目的是 prefill。
                cli.chat('嗯。', system_prompt=system,
                         temperature=opts.get('temperature', 0.7),
                         max_tokens=1, timeout=timeout)
                done += 1
            except Exception as e:
                _log.info('NPC %s 预热失败（忽略，不影响使用）: %s', nid, e)
        _log.info('NPC 预热结束：%d/%d 个（跳过无设定 %d），用时 %.1fs',
                  done, len(order), skipped, time.time() - t0)
        return done

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

        **世代号校验（第74轮 B9 收窄）**：比对的是 `_ai_delta_sink_gen`（"槽世代"），
        只有**带流式接收方**的请求才会推进它。这样：
        * 用户问了新问题（新请求带 sink）→ 槽世代 +1 → 旧请求的尾巴被丢弃，
          不会出现"新问题的回复里混着旧问题的半句话"（原设计意图不变）；
        * 后台请求（事件台词 / 跟随决策 / 自主发言，**不带** sink）→ 不推进槽世代
          → 前台正在流式的分片继续照写。这正是第58轮"17/42 次零分片"的修复点：
          以前比对的是"最后一次请求的世代"，后台请求一发就把前台的分片全判过期。

        注意：这里**故意不清理 `_ai_delta_sink`**。收尾时清理看着更"干净"，
        但 `_on_api_result` 拿不到世代号：一旦"旧请求的结果"和"新请求的登记"
        在主线程队列里交错，清理会误杀掉**新**请求的接收方。
        sink 由每个带接收方的新请求覆盖写，过期分片靠槽世代挡 —— 足够且无竞态。
        """
        try:
            if generation != getattr(self, '_ai_delta_sink_gen', 0):
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
                # ★★ 第52轮：待机（窝着）状态**也算**待机动画的激活条件。
                #    为什么必须加这一项：`idle_timer >= IDLE_LOOP_MIN_SECONDS` 在真机上
                #    **恒为假**（随机漫游每次把 idle_timer 清零，而 max_idle_duration
                #    只有 2~12s，永远涨不到 600s —— 完整推导见常量区
                #    IDLE_LOUNGE_AFTER_SECONDS 的注释），所以只靠右边那一项，
                #    "待机动画"结构性地从未播放过。
                self._idle_loop_active = bool(
                    self._lounge_since is not None
                    or self.idle_timer >= self.IDLE_LOOP_MIN_SECONDS)
                if hasattr(self, 'is_being_thrown') and self.is_being_thrown:
                    new_animation = "hatless_throw"
                    # 确保图像始终向速度向量的方向冲着
                    # 这里可以添加旋转逻辑
                else:
                    # ===== 表演/情绪动画（laugh/surprised/smile/wave等）不再自动触发 =====
                    # 统一由用户交互或 AI 通过 play_animation_once 触发，避免"走着走着突然跳舞"。
                    # is_happy/is_surprised/is_shy/is_waving 状态标志仍可被设置（供对话/情绪系统使用），
                    # 但不再驱动动画自动切换。
                    #
                    # ★★ 第54轮：待机（窝着）时**不再是站着循环 idle**，改为保持"坐下"静帧
                    #   —— 原作 CH1 纸牌城堡电梯场景的 `spr_ralsei_sit`。用户第52轮问
                    #   "待机动画换成哪一组"、第54轮明确指认的就是这一组。
                    #   "站 → 坐"的过渡由 `_idle_lounge_tick` 走到窝点时用
                    #   `play_animation_once("sit")` 播一次，这里只负责"坐定后保持"。
                    #
                    # ★★ 第54轮复检修正：判据从 `_idle_loop_active` 收紧为 `_lounge_since`。
                    #   原来用 `_idle_loop_active`（= 窝着 **或** idle_timer>=600）会把
                    #   "只是原地静止满 10 分钟、并未进入窝着状态"那一支也变成坐姿 ——
                    #   等于把第52轮的"待机动画 = idle 5 帧循环"整条删掉了
                    #   （round8 E1.3 断言的正是这条：静止 700s 后帧必须会推进）。
                    #   实测该断言当时是靠"跨组切换冷却 1.6s 恰好挡住 sit_rest"才侥幸为绿的
                    #   （假绿）。现在只认真正的窝着标志 `_lounge_since`：
                    #     窝着 → sit_rest（坐定静帧，不再站着循环）；
                    #     仅静止满 10 分钟 → idle（第52轮原语义，5 帧循环照旧）。
                    if getattr(self, '_lounge_since', None) is not None \
                            and 'sit_rest' in self.sprite_loader.sprites:
                        new_animation = "sit_rest"
                    else:
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
                    # ★ 第75轮 B3：换帧后同步手势判定器的精灵尺寸 / alpha 遮罩
                    self._sync_pet_tracker_sprite()
                
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
                    # ★ 第75轮 B3：换帧后同步手势判定器的精灵尺寸 / alpha 遮罩
                    self._sync_pet_tracker_sprite()
        
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
    
    # ★★ 第51轮：`interact_with_file` / `interact_with_folder` **已删除**。
    #
    # 用户口径逐字：「并且去掉那个与文件夹交互的功能吧，感觉过于鸡肋了」。
    # 被删掉的原实现（见本仓库 2026-09-26 及更早的提交）只有"按文件名 / 文件夹名
    # 硬编码一串固定台词"，例如：
    #     if '游戏' in folder_name:  "哇，{folder_name}文件夹里有游戏吗？我也想玩~"
    #     elif '文档' in folder_name: "{folder_name}文件夹里有很多重要的文件吧？"
    # 既没有真实能力（用户说的"鸡肋"），又把罐头句子混进 AI 对话流里
    # （用户：「看不出哪句是他自己说的」）。
    #
    # 调用点已从 `check_nearby_desktop_elements()` 一并删除（那里有长注释）。
    # 保留这两个**空壳**而不是彻底移除符号：桌面元素感知链路（`desktop_elements` /
    # 双击回调）将来若要复用这两个名字，不必再做一次全仓搜索；同时避免任何
    # 尚未发现的动态调用变成 AttributeError（本项目踩过"删了看着没用的方法"）。
    def interact_with_file(self, file_info):
        """已停用（第51轮）。保留签名，静默返回。"""
        return

    def interact_with_folder(self, folder_info):
        """已停用（第51轮）。保留签名，静默返回。"""
        return

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

    # ==============================================================
    # ★ 第52轮：任务栏（快捷栏）上沿 —— "静止时到快捷栏上面待着"的落点基准
    #
    #   ⚠️ 为什么不能用 `_virtual_screen_rect()` / `_desktop_floor_y()`：
    #      那两个量都是**整块屏幕**（含任务栏覆盖的那一条）。窗口"贴屏幕底边"
    #      会被任务栏盖住下半截 —— 用户看到的就是"人沉到快捷栏底下去了"。
    #      要"在快捷栏**上面**待着"，就必须用**工作区**（work area = 屏幕减去任务栏）。
    #
    #   取法（与 Qt 原生口径同源，按 Ralsei **当前所在的那块屏**取，不写死主屏）：
    #      ① `QDesktopWidget.availableGeometry(self)` —— Qt 给的"可用区域"，
    #         Windows 上就是 SPI_GETWORKAREA（已扣掉任务栏）；
    #      ② 失败则退 `_virtual_screen_rect()`（最坏情况 = 老行为，绝不崩）。
    # ==============================================================
    def _work_area_rect(self):
        """Ralsei 当前所在显示器的**工作区**矩形（QRect，已扣掉任务栏/快捷栏）。

        退化时退回 `_virtual_screen_rect()`（= 旧行为），保证调用方永远拿到一个矩形。
        """
        try:
            desk = QApplication.desktop()
            if desk is not None:
                wa = desk.availableGeometry(self) if self is not None \
                    else desk.availableGeometry()
                if wa is not None and wa.width() > 0 and wa.height() > 0:
                    return wa
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        return self._virtual_screen_rect()

    def _taskbar_top_y(self):
        """任务栏（快捷栏）上沿的 y 坐标（窗口左上角贴工作区底边时的 y）。

        = 工作区底边 − 窗口高。宠物站在这个 y 上时，脚正好压在任务栏上沿之上。
        """
        try:
            wa = self._work_area_rect()
            return wa.y() + wa.height() - max(1, self.height())
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return self._desktop_floor_y()

    def _lounge_perch_point(self):
        """待机窝点（QPoint）：屏幕底部 · 任务栏上沿之上 · 偏右三分之一处。

        横向取所在屏宽度的 `IDLE_LOUNGE_PERCH_X_RATIO` 比例处，避免和桌面图标
        左列/中间的应用窗口打架；再走 `_clamp_pos_to_desktop()` 夹回虚拟桌面内。
        任何一步失败 → 返回 None（调用方**不许就近凑**，直接不进入待机即可）。
        """
        try:
            ratio = float(getattr(self, 'IDLE_LOUNGE_PERCH_X_RATIO', 0.72))
            wa = self._work_area_rect()
            x = int(wa.x() + wa.width() * ratio)
            y = int(self._taskbar_top_y())
            x, y = self._clamp_pos_to_desktop(x, y)
            return QPoint(int(x), int(y))
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return None

    # ---- 待机（窝着）状态的进入 / 退出 -------------------------------------
    def _idle_lounge_busy(self):
        """"现在**不该**进入（或该退出）待机"的忙碌状态集合。

        与 `_can_speak_now()` 的"合时宜"口径对齐：睡眠/游戏/物理过程/拖拽/施法/
        跟鼠标/躲猫猫，一律不待机。宁可待机晚一点触发，也不要在这些过程中把宠物
        从半空中拽到任务栏去。
        """
        for attr in ('is_sleeping', 'is_falling', 'is_recovering', 'is_splat',
                     'is_jumping', 'is_gravity_falling', '_is_being_dragged',
                     'is_following_mouse', 'is_watching_video'):
            if getattr(self, attr, False):
                return True
        if getattr(self, 'game_state', {}).get('is_playing'):
            return True
        if getattr(self, '_spell_stage', None) is not None:
            return True
        if getattr(self, '_hide_stage', None) is not None:
            return True
        return False

    def _enter_idle_lounge(self, now=None):
        """进入待机状态：选窝点 → 走过去 → 清掉随机漫游。

        返回 True 表示已进入。
        """
        if not getattr(self, 'IDLE_LOUNGE_ENABLED', True):
            return False
        perch = self._lounge_perch_point()
        if perch is None:
            return False            # 算不出窝点（几何异常）⇒ 不进入，绝不就近凑
        now = time.time() if now is None else now
        self._lounge_since = now
        self._lounge_perch = perch
        self._lounge_interaction_ref = getattr(self, 'last_interaction_time', None)
        # 走向窝点：复用既有"目标点 + is_moving"通道（不新开移动实现）。
        self.target_pos = QPoint(perch)
        self.is_moving = True
        self._lounge_walking = True
        self.idle_timer = 0
        _log.debug("[待机] 进入待机状态，窝点=(%d, %d)", perch.x(), perch.y())
        return True

    def _exit_idle_lounge(self, reason=""):
        """退出待机状态（回到平常的自主漫游）。幂等。"""
        if self._lounge_since is None and self._lounge_perch is None:
            return False
        self._lounge_since = None
        self._lounge_perch = None
        self._lounge_walking = False
        self._lounge_interaction_ref = None
        _log.debug("[待机] 退出待机状态 reason=%s", reason or "-")
        return True

    def _idle_lounge_tick(self, current_time):
        """待机状态机（每 tick 调一次，由 update_movement 空闲分支驱动）。

        规则：
          · 未待机 + 距上次互动 ≥ 门限 + 不忙 → 进入；
          · 已待机 + 有互动（`last_interaction_time` 变了）/ 变忙 → 退出；
          · 已待机期间**不许**随机漫游（调用方据此跳过 randomize）。
        返回 True = 本 tick 处于待机（调用方应跳过随机漫游）。
        """
        try:
            if not getattr(self, 'IDLE_LOUNGE_ENABLED', True):
                return False
            if self._lounge_since is not None:
                # 退出条件 1：用户互动过（时间戳变了）
                ref = self._lounge_interaction_ref
                cur = getattr(self, 'last_interaction_time', None)
                if ref is not None and cur is not None and cur != ref:
                    self._exit_idle_lounge("用户互动")
                    return False
                # 退出条件 2：进入忙碌状态
                if self._idle_lounge_busy():
                    self._exit_idle_lounge("忙碌状态")
                    return False
                # 还在待机：到窝点就停住别动（走的过程由 update_movement 的目标点驱动）
                if self._lounge_walking and not self.is_moving:
                    self._lounge_walking = False
                    # ★ 第54轮：**刚到窝点这一拍**补一次"坐下"过渡（原作 CH1 电梯里的
                    #   `spr_ralsei_sit`：0=站 → 1=下沉 → 2=坐定）。
                    #   放在"到达"而不是"出发"是必须的：走路期间 `play_animation_once`
                    #   会压掉 `walk_*` 动画（"特殊动画播放期间不允许状态逻辑切换动画"），
                    #   那样会变成**坐着滑行**到窝点。
                    if 'sit' in self.sprite_loader.sprites:
                        self.play_animation_once("sit", restore_to="sit_rest")
                return True
            # 未待机 → 判断是否该进入
            if self._idle_lounge_busy():
                return False
            last = getattr(self, 'last_interaction_time', None)
            if last is None:
                return False
            gap = float(getattr(self, 'IDLE_LOUNGE_AFTER_SECONDS', 600.0))
            if (current_time - last) < gap:
                return False
            return bool(self._enter_idle_lounge(current_time))
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
            return False

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

        # 2.1 ★ 第58轮：停保温看门狗。它是守护线程，但**会真的发 HTTP 请求** ——
        #     不停掉的话，退出那一刻还可能对着正要关闭的网络再发一次。
        #     ⚠️ stop() **不会去卸载模型**：保温只负责"让它别过期"，
        #     过期后由 Ollama 自己回收（用户口径：不硬性占资源）。
        try:
            keeper = getattr(self, '_warm_keeper', None)
            if keeper is not None:
                keeper.stop()
                self._warm_keeper = None
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)

        # 2.5 隐藏托盘图标（若有）
        try:
            if getattr(self, '_tray', None) is not None:
                self._tray.hide()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)

        # 2.53 ★ 第55轮：收起灵魂窗口。
        # ⚠️ 灵魂是 **parent=None 的独立顶层窗口**，不会随主窗口一起销毁 ——
        #    不显式收掉的话，宠物退出后桌面上会留一块 48×48 的红方块。
        #    （这是"独立窗口"的代价，必须在这里还上。）
        try:
            soul = getattr(self, 'soul', None)
            if soul is not None:
                soul.hide_soul()
                soul.close()
            # ★ 第67轮补：收完**置 None** —— 本函数有**两个**调用点（托盘/退出路径
            #   显式调一次 + `atexit` 再调一次），第二次会打在已经析构的窗口上，
            #   抛 `RuntimeError: wrapped C/C++ object ... has been deleted`
            #   并刷出一整片 traceback（真机实测）。置 None 后第二遍自然跳过，
            #   同时**不动**其余步骤 —— 那些步骤刻意保留"再跑一次"的兜底语义。
            self.soul = None
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("main 防御性异常（已忽略）: %s", e)

        # 2.54 ★ 第55轮：把每个 NPC 的独立记忆各写回**他自己的文件**。
        # ⚠️ 为什么在退出时还要再写一遍（对话后已经写过）：NPC 记忆是"一角色一文件"
        #    的物理隔离结构，这里做的是**收尾兜底** —— 万一某次落盘被占位/被拒，
        #    退出时还有一次机会。失败只记日志（绝不拖住退出流程）。
        try:
            mem = getattr(self, 'npc_memory', None)
            if mem is not None:
                n = mem.save_all()
                if n:
                    _log.debug('NPC 独立记忆已落盘 %d 份（%s）', n, mem.describe())
        except Exception as e:  # 观测代码绝不能影响退出流程
            _log.debug("main 防御性异常（已忽略）: %s", e)

        # 2.55 ★ 第67轮：幽灵收尾 —— ①把接触时长**强制**写一次盘（平时是按
        #      `GHOST_SAVE_EVERY` 节流的，退出时那一次可能还没到点）；
        #      ②收掉幽灵窗口。
        # ⚠️ 与灵魂同一个代价：幽灵是 **parent=None 的独立顶层窗口**，不会随主窗口
        #    一起销毁 —— 不显式收掉的话，宠物退出后桌面上会留一块 44×58 的空窗口。
        try:
            gh = getattr(self, 'ghost', None)
            if gh is not None:
                self._ghost_save(force=True)
                gh.hide_ghost()
                gh.close()
            self.ghost = None          # 同上：二次收尾直接跳过（见 2.53 的说明）
        except Exception as e:  # 观测代码绝不能影响退出流程
            _log.debug("main 防御性异常（已忽略）: %s", e)

        # 2.56 ★★★ 第81轮（层4 存档）：把 NPC 生活档案（驻留表 + 每人规划）**强制**
        #      写一次盘 —— 平时是按 `NPC_PLAN_SAVE_EVERY`（120s）节流的，退出时那一次
        #      可能还没到点；`force=True` 保证"关掉桌宠前发生的最后一件事"不丢。
        #      失败只记日志（绝不让"存不上档"拖住退出）。
        try:
            self._npc_plan_save(force=True)
        except Exception as e:  # 观测代码绝不能影响退出流程
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
# -*- coding: utf-8 -*-
"""H4 · 闸门 G3 —— **属性归属表**（只读扫描，不改任何被审查文件）。

方案依据：`架构改造排期方案_H4-H5_2026-09-13.md` §3 G3 / §5.2 / §5.3。
方案的开工条件是原话："**没有这张表不许进入 Wave 1**"。
G3 判据原文：
    438 个 self 属性落成一张表，按「窗口几何 / 物理 / 动画 / 情绪 / 会话 / 子系统引用」分区；
    106 个跨方法写入属性**逐条定归属**。

为什么需要它（方案 §2 的原话）：
    拆分的瓶颈不是代码量，而是那批被多方法读写的 `self` 属性。
    不做属性归属表就动手，结果一定是新模块之间互相 import 或大量回调 RalseiPet。

本脚本回答三个问题
------------------
1. **有哪些属性**：全集 + 读/写次数 + **写入它的方法集合**（按方法数，不是按出现次数）。
2. **归谁**：按分区规则落到「待拆模块 / 子系统引用 / 核心留宿主 / 未归类」，**未归类显式列出**
   （不静默倒进 core）。
3. **接口在哪**（真正有用的那一问）：某模块要独占的属性里，**有多少还被模块外的方法碰** ——
   这些就是搬到新模块时必须显式设计的东西（构造参数 / `pyqtSignal` / 回调），
   也是"新模块不得不反向 import main"的唯一诱因。

★ v2 修正（2026-09-16）
    v1 把 `self.foo()` 里作为 `func` 的那个 `Attribute` 节点也当成"属性读"记账，
    于是 `change_animation`(28)/`pos`(23)/`height`(19)/`move`/`show`/`winId` 等方法名与 Qt 内置
    全被灌进属性全集，基数虚高、`UNCLASSIFIED` 段几乎被方法名塞满，表不可用。
    v2 起：`self.foo()` 记 **call**，不算 load；**只被调用、从未被赋值**的名字判为方法/Qt 内置，
    整条移出属性表并**单独成段列出**（禁止静默丢弃）。新增 X5/X6/X7 三条自检锁住这个行为。

产物（都写进本目录 `_evidence/`，**不覆盖既有的 `main_class_profile.txt`** —— 那是改造前的冻结基线）：
    attribute_ownership.json  机器可读全量
    attribute_ownership.txt   人读表格

自检（防止"看起来有表、其实漏了一批"）：
    X1 每个属性恰好落进一个分区，且分区属性数之和 == 属性全集大小；
    X2 写入方法集合是"真方法"，且写入方法数 ≤ 该属性的写出现次数；
    X3 `setattr(self, 'x', ...)` / `getattr(self, 'x')` 这类字符串形式也被计入（否则会漏一批）；
    X4 方法分区覆盖率显式打印（未覆盖的方法数不许悄悄算进 core）；
    X5 被判为"方法/Qt 调用"的名字，写次数必须为 0（出现任何一次赋值就是误判）；
    X6 X5 集合与属性表**交集为空**（不许既在表里又在排除段里）；
    X7 排除段与属性表之和 == 原始 `self.<name>` 名集（不许凭空少东西）。

用法：& C:\\Python311\\python.exe scan_attribute_ownership.py
"""
import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
OUT_DIR = os.path.join(HERE, '_evidence')

# ------------------------------------------------------------------ 分区规则
# 每个分区： (显示名, 目标模块, 属性名匹配规则)
# 规则按**顺序**匹配，第一条命中的生效 —— 所以"具体的"放前面、"宽泛的"放后面。
# 规则是 (kind, value)：
#   ('exact', '名字') / ('prefix', '前缀') / ('suffix', '后缀') / ('contains', '子串')
#
# 归属目标取值：
#   'W1-1'..'W1-6' / 'W2-1' / 'W3-1'..'W3-3'  = 方案 §5.2 里的待拆模块
#   'SUBSYS'  = 注入的子系统引用（本来就不属于宿主状态，拆分时是最容易的一批）
#   'CORE'    = 确认留在 RalseiPet 的状态（窗口几何/情绪/会话/配置 UI/托盘/环境…）
#   'UNCLASSIFIED' = 没有规则命中 → **显式列出**，由人决定（禁止静默归 core）
PARTITIONS = [
    # ---- W1-1 施法流程 SpellFlowController ----
    ('W1-1 施法流程', 'W1-1', [
        ('prefix', '_spell'), ('prefix', 'spell'), ('contains', 'spell'),
    ]),
    # ---- W1-2 躲猫猫 HideAndSeekController ----
    ('W1-2 躲猫猫', 'W1-2', [
        ('prefix', '_hide'), ('prefix', 'hide'), ('contains', 'hide_seek'),
        ('contains', 'hiding'),
    ]),
    # ---- W1-3 游戏 GamesController ----
    ('W1-3 游戏', 'W1-3', [
        ('exact', 'game_state'), ('contains', 'guess_number'), ('prefix', '_rps'),
        ('prefix', 'rps'), ('contains', 'rock_paper'),
    ]),
    # ---- W1-4 视频观看 VideoWatchController ----
    ('W1-4 视频观看', 'W1-4', [
        ('prefix', '_video'), ('prefix', 'video'), ('contains', 'watching_video'),
        ('prefix', '_watch'), ('exact', 'is_watching_video'),
        ('exact', 'current_video_url'),
    ]),
    # ---- W1-5 办公应用检测 OfficeAppDetector ----
    ('W1-5 办公检测', 'W1-5', [
        ('prefix', '_office'), ('prefix', 'office'), ('contains', 'ppt_app'),
        ('contains', 'bilibili'),
    ]),
    # ---- W1-6 文件/表格操作 ----
    ('W1-6 文件表格', 'W1-6', [
        ('contains', 'excel'), ('contains', 'name_table'), ('prefix', '_file_op'),
        ('contains', 'spreadsheet'),
    ]),
    # ---- W2-1 鼠标交互 MouseInteractionController ----
    # 方案 §5.2 原话："牵动 12 个拖拽类属性" —— 这里把那 12 个显式点名，不靠前缀撞。
    ('W2-1 鼠标交互', 'W2-1', [
        ('exact', 'is_dragging'), ('exact', 'is_clicking'), ('exact', 'is_pressed'),
        ('prefix', 'drag'), ('prefix', '_drag'), ('prefix', 'mouse_'),
        ('prefix', '_mouse'), ('prefix', 'click'), ('prefix', '_click'),
        ('contains', 'body_part'), ('contains', 'press_pos'), ('contains', 'release_pos'),
        ('exact', 'has_ball'), ('exact', '_is_thrown'),
        ('exact', 'is_dragging_mouse'), ('exact', 'is_following_mouse'),
        ('exact', 'is_following_dragged_file'), ('exact', '_is_being_dragged'),
        ('exact', '_catch_brake'), ('exact', '_CATCH_BRAKE_SECONDS'),
        ('exact', 'last_dragging_time'), ('exact', '_last_dragging_play_time'),
        ('exact', '_last_drag_pos'), ('exact', 'auto_mouse_drag_timer'),
        ('exact', '_last_mouse_pos'),
    ]),
    # ---- W3-1 动画 AnimationController ----
    ('W3-1 动画', 'W3-1', [
        ('exact', 'current_animation'), ('prefix', 'animation_'), ('prefix', '_anim'),
        ('contains', 'sprite'), ('prefix', 'frame'), ('exact', 'fps'),
        ('contains', 'special_anim'), ('prefix', 'emotion_animation'),
        ('exact', 'current_frame'), ('exact', 'next_animation'), ('exact', 'current_offset'),
        ('exact', 'last_animation_change'), ('exact', '_last_animation_time'),
        ('exact', '_idle_loop_active'), ('exact', '_perf_anim_min_duration'),
        ('exact', '_last_perf_anim_time'),
        ('exact', '_play_once_active'), ('exact', '_play_once_callback'),
        ('exact', '_play_once_frame_counter'), ('exact', '_play_once_arming'),
    ]),
    # ---- W3-2 移动 MovementController ----
    ('W3-2 移动', 'W3-2', [
        ('exact', 'is_moving'), ('prefix', 'move_'), ('prefix', '_move'),
        ('exact', 'direction'), ('exact', 'previous_direction'), ('exact', 'speed'),
        ('prefix', 'target_'), ('prefix', 'walk_'), ('contains', 'movement_pattern'),
        ('prefix', 'velocity'), ('contains', 'random_seed'),
        # 桌面移动/idle 巡航状态（hot 清单里的那一批，逐条点名）
        ('exact', 'current_speed_x'), ('exact', 'current_speed_y'),
        ('exact', 'acceleration_x'), ('exact', 'acceleration_y'),
        ('exact', 'current_direction'), ('exact', 'speed_fluctuation'),
        ('exact', 'idle_timer'), ('exact', 'idle_walk_timer'),
        ('exact', 'max_idle_duration'), ('exact', 'current_activity'),
        ('exact', 'activity_history'), ('exact', 'moving_duration'),
        ('exact', 'max_moving_duration'), ('exact', 'last_movement_end_time'),
        ('exact', 'is_sleeping_walk'), ('exact', '_speed_variation'),
        ('exact', 'speed_variation'), ('exact', 'movement_noise'),
        ('exact', 'noise_change_rate'), ('exact', 'smoothness_factor'),
        ('exact', 'direction_change_smoothness'), ('exact', 'fluctuation_speed'),
        ('exact', 'stride_fluctuation'), ('exact', 'stride_variation'),
        ('exact', 'swing_speed'), ('exact', 'mass'), ('exact', 'air_resistance'),
        ('exact', 'friction'), ('exact', '_rotation_damping'),
        ('exact', 'max_speed'), ('exact', 'min_speed'),
        ('exact', 'stamina'), ('exact', 'stamina_regen_rate'),
        ('exact', '_follow_mouse_start'), ('exact', 'movement_timer'),
        ('exact', 'last_start_pos'), ('exact', 'is_rolling'), ('exact', 'is_sliding'),
        ('exact', 'last_window_rect'), ('exact', 'last_floor_check_time'),
        ('exact', 'floor_check_interval'), ('exact', 'last_window_check_time'),
        ('exact', 'window_check_interval'),
    ]),
    # ---- W3-3 物理 PhysicsController ----
    ('W3-3 物理', 'W3-3', [
        ('exact', 'is_jumping'), ('prefix', 'jump'), ('prefix', '_jump'),
        ('prefix', 'fall'), ('prefix', '_fall'), ('contains', 'falling'),
        ('prefix', 'current_floor'), ('prefix', 'current_window'),
        ('contains', 'platform_height'), ('contains', 'platform_z'),
        ('exact', 'floor_manager'), ('exact', 'gravity'), ('contains', 'bounce'),
        # 落地后的状态机（splat → recover → rest → sleep），逐条点名
        ('exact', 'is_splat'), ('exact', 'splat_start_time'),
        ('exact', 'is_recovering'), ('exact', 'recovery_duration'),
        ('exact', 'recovery_max_duration'), ('exact', 'recovery_start_time'),
        ('exact', 'needs_rest'), ('exact', 'rest_duration'), ('exact', 'resting_time'),
        ('exact', 'is_sleeping'), ('exact', 'sleep_timer'),
        ('exact', '_sleep_stir_count'), ('exact', '_sleep_stir_time'),
        ('exact', 'max_sleep_idle_duration'),
        ('exact', 'current_platform_z'), ('exact', 'window_level'),
        ('exact', 'max_fall_duration'), ('exact', 'max_jumps'),
    ]),
    # ---- 注入的子系统引用（不是宿主状态，拆分时最省事）----
    ('子系统引用', 'SUBSYS', [
        ('exact', 'sprite_loader'), ('exact', 'ai_driver'), ('exact', 'emotion_system'),
        ('exact', 'memory_system'), ('exact', 'dialogue_ui'), ('exact', 'memory_store'),
        ('exact', 'desktop_interaction'), ('exact', 'command_manager'),
        ('exact', 'growth_system'), ('exact', 'tts_manager'), ('exact', 'task_manager'),
        ('exact', 'voice_manager'), ('exact', 'entertainment_system'), ('exact', 'timer'),
        ('exact', 'animation_timer'), ('exact', 'move_timer'), ('exact', 'floor_timer'),
        ('exact', 'update_timer'), ('exact', 'sound_manager'), ('exact', 'config_manager'),
        ('exact', 'weather_system'), ('exact', 'customization_system'),
        ('exact', 'social_growth'), ('exact', 'pet_ai'), ('exact', 'autonomous_agent'),
        ('exact', 'search_summarizer'), ('exact', 'dialogue_system'),
        ('exact', 'api_client'), ('exact', '_tray'),
    ]),
    # ---- CORE：确认留在宿主（未列入任何 Wave）----
    ('CORE 窗口几何', 'CORE', [
        ('exact', 'spatial_pos'), ('exact', 'current_offset'),
        ('exact', 'ralsei_window_relative_pos'), ('exact', '_cached_screen_geom'),
        ('exact', '_cached_scale_factor'), ('exact', '_last_screen_check'),
    ]),
    ('CORE 情绪与状态', 'CORE', [
        ('exact', 'mood'), ('exact', 'emotions'), ('exact', 'is_happy'),
        ('exact', 'is_shy'), ('exact', 'is_unhappy'), ('exact', 'is_surprised'),
        ('exact', 'is_laughing'), ('exact', 'is_teasplashed'), ('exact', 'is_victorious'),
        ('exact', 'is_shocked'), ('exact', 'is_wearing_suit'),
        ('exact', 'is_holding_cotton_candy'), ('exact', 'is_using_item'),
        ('exact', 'happy_timer'), ('exact', 'shy_timer'), ('exact', 'unhappy_timer'),
        ('exact', 'surprised_timer'), ('exact', 'shocked_start_time'),
        ('exact', 'surprised_start_time'), ('exact', 'surprised_jump'),
        ('exact', 'last_mood_change'), ('exact', '_last_mood_check'),
        ('exact', '_cached_mood_factor'), ('exact', 'shock_direction'),
        ('exact', 'energy_hunger'), ('exact', 'current_priority'),
    ]),
    ('CORE 会话/AI', 'CORE', [
        ('exact', 'api_enabled'), ('exact', 'api_config'), ('exact', 'api_control_timer'),
        ('exact', '_api_result'), ('exact', 'ai_timer'), ('exact', '_agent_busy_flags'),
        ('exact', '_autonomous_speech_allowed'), ('exact', '_last_autonomous_speech_time'),
        ('exact', '_URGE_WORDS'), ('exact', 'AUTONOMOUS_SPEECH_MIN_INTERVAL'),
        ('exact', 'IDLE_LOOP_MIN_SECONDS'),
        ('exact', 'last_interaction_time'), ('exact', '_last_reacted_element'),
        ('exact', '_pending_look_at_element'), ('exact', '_last_desktop_elements_sig'),
        ('exact', '_last_desktop_elem_check'), ('exact', '_last_env_update'),
        ('exact', '_pet_detection_state'), ('exact', '_can_speak_now'),
        ('exact', '_last_hover_time'), ('exact', 'dialogue_init_timer'),
    ]),
    ('CORE 配置 UI', 'CORE', [
        ('suffix', '_input'), ('suffix', '_spinbox'), ('suffix', '_checkbox'),
        ('prefix', 'placeholder_'),
    ]),
    ('CORE 托盘/进程', 'CORE', [
        ('exact', 'ai_thread'), ('exact', 'ai_thread_running'),
        ('exact', 'stats_timer'), ('exact', 'last_update_time'),
        ('exact', 'last_jump_time'),
    ]),
    ('CORE 环境', 'CORE', [
        ('exact', 'weather'), ('exact', 'temperature'), ('exact', 'humidity'),
        ('exact', 'time_of_day'), ('exact', 'weather_timer'),
        ('exact', 'current_time'),
    ]),
    # ---- 只读不写 = 悬空读；在归属表里必须单独可见，不能混进正常属性 ----
    ('CORE 未赋值（悬空读，交 G1）', 'CORE', [
        ('exact', 'is_being_thrown'),
    ]),
]

# 方法 → 待拆模块（方案 §5.2 点名的方法 + 命名规则）。未命中 = 留在 RalseiPet。
METHOD_RULES = [
    ('W1-1', [('prefix', '_spell'), ('prefix', '_tick_spell'), ('exact', 'start_spell'),
              ('contains', 'spell')]),
    ('W1-2', [('contains', 'hide'), ('contains', 'seek'), ('contains', 'hiding')]),
    ('W1-3', [('contains', 'game'), ('contains', 'guess'), ('contains', 'rps'),
              ('contains', 'rock_paper'), ('contains', 'play_'), ('prefix', '_play')]),
    ('W1-4', [('contains', 'video'), ('contains', 'watching'), ('prefix', '_watch')]),
    ('W1-5', [('prefix', 'check_'), ('contains', 'office'), ('contains', 'ppt_app')]),
    ('W1-6', [('contains', 'excel'), ('contains', 'name_table'), ('prefix', 'create_person')]),
    ('W2-1', [('contains', 'Mouse'), ('contains', 'mouse'), ('prefix', 'get_ralsei_body'),
              ('contains', 'drag'), ('contains', 'click'), ('contains', 'doubleClick')]),
    ('W3-1', [('contains', 'animation'), ('prefix', '_anim'), ('contains', 'sprite'),
              ('contains', 'frame')]),
    ('W3-2', [('contains', 'movement'), ('contains', 'move_target'), ('prefix', 'init_move'),
              ('contains', 'randomize_movement'), ('contains', 'walk')]),
    ('W3-3', [('contains', 'jump'), ('contains', 'fall'), ('contains', 'gravity'),
              ('contains', 'window_movement'), ('contains', 'floor_property'),
              ('contains', 'spell_tick')]),
]


def _rule_hit(name, rules):
    for kind, val in rules:
        if kind == 'exact' and name == val:
            return True
        if kind == 'prefix' and name.startswith(val):
            return True
        if kind == 'suffix' and name.endswith(val):
            return True
        if kind == 'contains' and val in name:
            return True
    return False


def classify(name, partitions):
    for disp, target, rules in partitions:
        if _rule_hit(name, rules):
            return disp, target
    return 'UNCLASSIFIED（未归类）', 'UNCLASSIFIED'


def method_module(name):
    for mod, rules in METHOD_RULES:
        if _rule_hit(name, rules):
            return mod
    return 'RalseiPet（留在宿主）'


# ------------------------------------------------------------------ 解析
src = open(MAIN, encoding='utf-8').read()
tree = ast.parse(src)
pet = None
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'RalseiPet':
        pet = node
        break
assert pet is not None, 'RalseiPet not found'

methods = {}
for node in pet.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        end = max(getattr(n, 'lineno', node.lineno) for n in ast.walk(node))
        methods[node.name] = {'node': node, 'start': node.lineno, 'end': end,
                              'lines': end - node.lineno + 1}

# 属性所属的类属性（`x = None` 这种类体声明）—— 它们是"初始值声明"，不是耦合点
class_attrs = set()
for node in pet.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name):
                class_attrs.add(t.id)

# 属性（property）方法：读 `self.foo` 有可能命中它，需单独标注
prop_names = set()
for name, info in methods.items():
    for dec in info['node'].decorator_list:
        d = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(d, ast.Name) and d.id == 'property':
            prop_names.add(name)
        if isinstance(d, ast.Attribute) and d.attr == 'setter':
            prop_names.add(d.value.id if isinstance(d.value, ast.Name) else '?')

attr = {}
n_setattr = 0
n_getattr = 0
n_call = 0          # self.foo() 形式的调用点总数
raw_names = set()   # 原始出现的 self.<name> 名集（含方法名），用于 X7


def touch(name, method, kind, lineno):
    d = attr.setdefault(name, {'loads': 0, 'stores': 0, 'calls': 0, 'readers': set(),
                               'writers': set(), 'callers': set(), 'lines': []})
    if kind == 'w':
        d['stores'] += 1
        d['writers'].add(method)
    elif kind == 'c':
        d['calls'] += 1
        d['callers'].add(method)
    else:
        d['loads'] += 1
        d['readers'].add(method)
    d['lines'].append((method, lineno, kind))
    raw_names.add(name)


for mname, info in methods.items():
    # 先收集"作为调用目标"的 Attribute 节点（self.foo() 里的 foo），
    # 否则 ast.walk 会把它当普通读取再记一次 → 方法名污染属性表（v1 的 bug）。
    call_nodes = set()
    for node in ast.walk(info['node']):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
            call_nodes.add(id(node.func))
    for node in ast.walk(info['node']):
        # self.x
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == 'self'):
            if id(node) in call_nodes:
                n_call += 1
                touch(node.attr, mname, 'c', node.lineno)
            else:
                touch(node.attr, mname,
                      'w' if isinstance(node.ctx, ast.Store) else 'r', node.lineno)
        # setattr(self, 'x', ...) / getattr(self, 'x')
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in ('setattr', 'getattr') and len(node.args) >= 2:
            a0, a1 = node.args[0], node.args[1]
            if isinstance(a0, ast.Name) and a0.id == 'self' \
                    and isinstance(a1, ast.Constant) and isinstance(a1.value, str):
                is_store = node.func.id == 'setattr'
                if is_store:
                    n_setattr += 1
                else:
                    n_getattr += 1
                touch(a1.value, mname, 'w' if is_store else 'r', node.lineno)

# ---- 方法 / Qt 内置（只被调用、从未被赋值）从属性表里剔除，单独成段 ----
call_only = [a for a in attr
             if attr[a]['stores'] == 0
             and (attr[a]['calls'] > 0 or a in methods)]
# 剔除前先快照，否则调用计数随属性表一起丢掉（排除段就没法打印了）
call_only_info = {a: dict(attr[a]) for a in call_only}
for a in call_only:
    del attr[a]

# ------------------------------------------------------------------ 汇总
for a, d in attr.items():
    disp, target = classify(a, PARTITIONS)
    d['partition'] = disp
    d['owner'] = target
    d['n_methods_writing'] = len(d['writers'])
    d['n_methods_reading'] = len(d['readers'])
    d['writers'] = sorted(d['writers'])
    d['readers'] = sorted(d['readers'])
    d['callers'] = sorted(d['callers'])
    d['is_class_attr'] = a in class_attrs
    d['is_property'] = a in prop_names

    # 跨模块触碰：写它的方法里有多少"不属于它自己的模块"
    writers_mods = {method_module(m) for m in d['writers']}
    outside = sorted(m for m in writers_mods if m != target)
    d['writer_modules'] = sorted(writers_mods)
    d['writers_outside_owner'] = outside
    d['needs_interface'] = bool(outside) and target not in ('SUBSYS', 'CORE', 'UNCLASSIFIED')

all_attrs = sorted(attr, key=lambda a: (-attr[a]['stores'], -attr[a]['loads'], a))
tot = len(all_attrs)
# 两种口径都算：方案 §2 的 106 是"被 ≥3 处写入"(出现次数)，本表同时给"写入方法数 ≥3"(真耦合点)
hot_occ = [a for a in all_attrs if attr[a]['stores'] >= 3]
hot_meth = [a for a in all_attrs if attr[a]['n_methods_writing'] >= 3]
hot = [a for a in all_attrs if a in set(hot_occ) | set(hot_meth)]

by_part = {}
for a in all_attrs:
    by_part.setdefault(attr[a]['partition'], []).append(a)

# 自检
checks = []
x1 = sum(len(v) for v in by_part.values()) == tot
checks.append(('X1 每个属性恰好一个分区、分区之和 == 全集（%d）' % tot, x1))
x2 = all(attr[a]['n_methods_writing'] <= attr[a]['stores'] for a in all_attrs)
checks.append(('X2 写入方法数 ≤ 写出现次数（恒成立）', x2))
x3 = n_setattr + n_getattr > 0
checks.append(("X3 字符串形式 setattr/getattr 已计入（setattr=%d getattr=%d）"
               % (n_setattr, n_getattr), x3))
meth_mods = {}
for m in methods:
    meth_mods.setdefault(method_module(m), []).append(m)
x4 = sum(len(v) for v in meth_mods.values()) == len(methods)
checks.append(('X4 方法分区之和 == 方法总数（%d）' % len(methods), x4))
x5 = all(call_only_info[a]['stores'] == 0 for a in call_only)
checks.append(('X5 判为"方法/Qt 调用"的名字写次数必须为 0（%d 个）' % len(call_only), x5))
x6 = not (set(call_only) & set(all_attrs))
checks.append(('X6 排除段与属性表交集为空', x6))
x7 = len(call_only) + tot == len(raw_names)
checks.append(('X7 排除段 + 属性表 == 原始 self.<name> 名集（%d + %d == %d）'
               % (len(call_only), tot, len(raw_names)), x7))

# ------------------------------------------------------------------ 产出
rep = []


def emit(s=''):
    rep.append(s)


emit('=' * 78)
emit('H4 · G3 属性归属表（只读扫描）  %s' % os.path.basename(MAIN))
emit('=' * 78)
emit('RalseiPet：起始行 %d / 直接方法 %d 个 / 方法体 %d 行 / main.py 共 %d 行'
     % (pet.lineno, len(methods), sum(m['lines'] for m in methods.values()),
        len(src.splitlines())))
emit('self 属性名全集：%d 个（Store 过 %d 个；类体声明 %d 个；property %d 个）'
     % (tot, len([a for a in all_attrs if attr[a]['stores']]),
        len([a for a in all_attrs if attr[a]['is_class_attr']]), len(prop_names)))
emit('另：self.foo() 调用位（方法 / Qt 内置，非属性）%d 个名字 / %d 个调用点 —— 见文末专段'
     % (len(call_only), n_call))
emit()
emit('--- 自检 ---')
for name, ok in checks:
    emit('[%s] %s' % ('PASS' if ok else 'FAIL', name))
emit()
emit('--- 分区分布 ---')
emit('%-26s %6s %6s' % ('分区', '属性数', '其中写≥3方法'))
for p in sorted(by_part, key=lambda k: -len(by_part[k])):
    n_hot = len([a for a in by_part[p] if attr[a]['n_methods_writing'] >= 3])
    emit('%-26s %6d %6d' % (p, len(by_part[p]), n_hot))
emit()
emit('--- 跨方法共享可变状态（真耦合点）---')
emit('写方法数≥3：%d 个    写出现次数≥3：%d 个    并集：%d 个'
     % (len(hot_meth), len(hot_occ), len(hot)))
emit('%-34s %5s %5s %5s %s' % ('attr', '写法', '写法', '读法', '归属'))
for a in hot:
    d = attr[a]
    emit('%-34s %5d %5d %5d %s'
         % (a, d['stores'], d['n_methods_writing'], d['n_methods_reading'], d['partition']))
emit()
emit('--- 需要显式接口的属性（本模块要独占，但**模块外**的方法也在写它）：%d 个 ---'
     % len([a for a in all_attrs if attr[a]['needs_interface']]))
emit('%-30s %-16s %s' % ('attr', '归属', '模块外的写方法'))
for a in all_attrs:
    d = attr[a]
    if not d['needs_interface']:
        continue
    emit('%-30s %-16s %s' % (a, d['owner'], ', '.join(d['writers_outside_owner'])[:80]))
emit()
emit('--- 读而从未写 / 写而从未读（死参数、悬空读候选，交 G1 处置）---')
never_w = [a for a in all_attrs if attr[a]['stores'] == 0]
never_r = [a for a in all_attrs if attr[a]['loads'] == 0 and attr[a]['stores'] > 0]
const_only = [a for a in never_w if attr[a]['is_class_attr']]
dangling = [a for a in never_w if not attr[a]['is_class_attr']]
emit('从无赋值：%d 个 —— 其中类体常量 %d 个（合法，读常量）；**真悬空读 %d 个**'
     % (len(never_w), len(const_only), len(dangling)))
for a in never_w:
    d = attr[a]
    emit('   %-34s 读方法=%d 分区=%-24s %s'
         % (a, d['n_methods_reading'], d['partition'],
            '类体常量' if d['is_class_attr'] else '**悬空读（读一个从未赋值的属性）**'))
emit('赋过值但从无读取（死参数候选）：%d 个' % len(never_r))
for a in never_r:
    d = attr[a]
    emit('   %-34s 写方法=%d 分区=%s' % (a, d['n_methods_writing'], d['partition']))
emit()
emit('--- 未归类属性（**显式列出，禁止静默归 core**）：%d 个 ---'
     % len(by_part.get('UNCLASSIFIED（未归类）', [])))
for a in by_part.get('UNCLASSIFIED（未归类）', []):
    d = attr[a]
    emit('   %-34s 写法=%d 读法=%d' % (a, d['n_methods_writing'], d['n_methods_reading']))
emit()
emit('--- 方法 → 待拆模块（覆盖率显式打印）---')
for mod in sorted(meth_mods, key=lambda k: -len(meth_mods[k])):
    emit('%-22s %3d 个方法' % (mod, len(meth_mods[mod])))
emit()
emit('--- 排除段：self.foo() 调用位（方法 / Qt 内置），不是状态，**不得进属性表** ---')
emit('%-38s %5s %5s %s' % ('name', '调用', '读取', '说明'))
_call_tbl = [(a, call_only_info[a]['calls'], call_only_info[a]['loads'],
              'RalseiPet 方法' if a in methods else 'Qt/继承方法') for a in call_only]
for a, c, l, note in sorted(_call_tbl, key=lambda t: (-t[1], t[0])):
    emit('%-38s %5d %5d %s' % (a, c, l, note))

OUT = '\n'.join(rep) + '\n'
os.makedirs(OUT_DIR, exist_ok=True)
with open(os.path.join(OUT_DIR, 'attribute_ownership.txt'), 'w',
          encoding='utf-8', newline='\n') as fh:
    fh.write(OUT)
with open(os.path.join(OUT_DIR, 'attribute_ownership.json'), 'w',
          encoding='utf-8', newline='\n') as fh:
    json.dump({
        'source': MAIN,
        'schema': 2,
        'main_lines': len(src.splitlines()),
        'class_start_line': pet.lineno,
        'n_methods': len(methods),
        'n_attrs': tot,
        'n_call_only': len(call_only),
        'n_call_sites': n_call,
        'hot_by_writers': hot_meth,
        'hot_by_stores': hot_occ,
        'hot_union': hot,
        'needs_interface': [a for a in all_attrs if attr[a]['needs_interface']],
        'unclassified': by_part.get('UNCLASSIFIED（未归类）', []),
        'never_written': never_w,
        'never_read': never_r,
        'self_checks': [{'name': n, 'ok': bool(ok)} for n, ok in checks],
        'partitions': {p: sorted(v) for p, v in by_part.items()},
        'methods_by_module': {k: sorted(v) for k, v in meth_mods.items()},
        'call_only': sorted(call_only),
        'call_only_detail': {a: {
            'calls': call_only_info[a]['calls'],
            'loads': call_only_info[a]['loads'],
            'is_own_method': a in methods,
        } for a in call_only},
        'attrs': {a: {k: (sorted(v) if isinstance(v, set) else v)
                      for k, v in attr[a].items()} for a in all_attrs},
    }, fh, ensure_ascii=False, indent=1)
    fh.write('\n')

print(OUT)
print('[ok] 产物：%s' % OUT_DIR)
sys.exit(0 if all(ok for _, ok in checks) else 1)

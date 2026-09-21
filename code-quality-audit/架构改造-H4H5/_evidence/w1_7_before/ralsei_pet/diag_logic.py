"""单元测试：不启动GUI，纯逻辑模拟spell流程关键状态。
检查以下问题：
1. _cast_spell_then 后 _spell_interrupted_reason 是否立刻返回 facing_mismatch
2. _start_open_with_spell walking 阶段是否被 idle 随机移动打断
"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

# 在QApp之前禁用单实例检查（通过临时修改__main__里的mutex）
import PyQt5.QtWidgets
from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)

# ---- Mock 环境变量以减少依赖加载失败 ----
from unittest.mock import MagicMock

# 先加载sprite_loader并mock素材，避免实际图片加载
import modules.sprite_loader as sl_module
orig_scan = sl_module.SpriteLoader.scan_and_group_assets
def mock_scan(self, *a, **kw):
    # 返回最小的动画映射：spell, spell_left, walk_right, walk_left, idle
    empty_frames = {anim: [MagicMock(size=lambda: (100,100))] for anim in [
        'spell', 'spell_left', 'walk_right', 'walk_left', 'walk_down', 'walk_up',
        'run_right', 'run_left', 'run_down', 'run_up', 'idle',
        'jump_ready', 'jump', 'jump_ball', 'land', 'fall', 'splat', 'fall_back',
        'pose', 'laugh', 'item', 'roll', 'slide', 'tea', 'victory',
        'surprised_down', 'surprised_behind', 'surprised',
        'shocked_left', 'shocked_right',
        'smile_left', 'smile_right', 'wave_start', 'wave_down',
        'hatless_throw',
    ]}
    self.sprites = empty_frames
    self.animation_offsets = {k:(0,0) for k in empty_frames}
    self.animation_priorities = {'idle':1, 'walk':2, 'run':3, 'jump':4, 'spell':5, 'splat':6}
sl_module.SpriteLoader.scan_and_group_assets = mock_scan

# Mock sound_manager / desktop_interaction 等外部依赖
import modules.desktop_interaction as di_module
di_module.DesktopInteraction = MagicMock

from src.main import RalseiPet

# Mock掉需要真实Win32/音频的部分
class MinimalPet(RalseiPet):
    def __init__(self):
        # 跳过父类init_ui里部分真实资源依赖，直接调RalseiPet.__init__
        import unittest.mock as mock
        self._sound_mock = MagicMock()
        self._di_mock = MagicMock()
        # 先构造
        super().__init__()
    def cleanup_on_exit(self):
        pass

print("=== TEST 1: _cast_spell_then + facing_mismatch ===")
try:
    pet = MinimalPet()
    pet.current_direction = 'down'  # 初始朝下
    print(f"初始: current_direction={pet.current_direction}, _spell_stage={pet._spell_stage}")
    # 触发躲猫猫会走到中央，这里直接测_cast_spell_then
    result = {'called': False}
    def cb():
        result['called'] = True
    pet._cast_spell_then(cb, direction='right')
    print(f"_cast_spell_then(right) 后: current_direction={pet.current_direction}, _spell_stage={pet._spell_stage}")
    reason = pet._spell_interrupted_reason()
    print(f"_spell_interrupted_reason 返回: {reason}")
    if reason == 'facing_mismatch':
        print("FAIL: 立刻 facing_mismatch 打断！")
    elif reason is None:
        print("PASS: 未被 facing_mismatch 打断")
    else:
        print(f"WARN: 其他原因: {reason}")
except Exception as e:
    import traceback; traceback.print_exc()

print("\n=== TEST 2: spell casting 阶段帧计数 ===")
try:
    # 模拟动画播放推进（update_animation里current_frame每帧+1，_tick_spell_flow里_frames_seen每帧+1）
    for i in range(13):
        pet._tick_spell_flow()
        print(f"tick {i}: stage={pet._spell_stage}, frames_seen={pet._spell_frames_seen}, cb_called={result['called']}, cur_anim={pet.current_animation}")
    print(f"最终 callback called: {result['called']}")
except Exception as e:
    import traceback; traceback.print_exc()

print("\n=== TEST 3: _start_open_with_spell walking -> casting ===")
try:
    pet2 = MinimalPet()
    # 放在离目标35px以内，直接进入casting
    pet2.move(400, 400)
    result2 = {'called': False}
    def cb2(path, kind):
        result2['called'] = True
        print(f"  cb2({path}, {kind})")
    # 把目标放角色正右侧，距离35px以内
    my_cx = pet2.frameGeometry().center().x()
    my_cy = pet2.frameGeometry().center().y()
    import unittest.mock as mock
    pet2._resolve_target_screen_anchor = lambda p: (my_cx + 10, my_cy)  # 10px距离
    pet2._start_open_with_spell('C:/test.txt', 'file', cb2)
    print(f"start_open后: stage={pet2._spell_stage}, dir={pet2._spell_target_direction}, auto_sus={pet2._spell_auto_suspended}")
    pet2._tick_spell_flow()  # walking tick: dist<35 → casting
    print(f"tick1后: stage={pet2._spell_stage}, cur_dir={pet2.current_direction}, anim={pet2.current_animation}, interrupt={pet2._spell_interrupted_reason()}")
    for i in range(13):
        pet2._tick_spell_flow()
    print(f"最终: stage={pet2._spell_stage}, cb_called={result2['called']}, auto_sus={pet2._spell_auto_suspended}")
except Exception as e:
    import traceback; traceback.print_exc()

print("\n=== TEST 4: update_movement空闲分支spell期间不随机移动 ===")
try:
    pet3 = MinimalPet()
    pet3._spell_stage = 'walking'
    pet3.is_moving = False
    pet3.idle_timer = 9999  # 超过max_idle_duration
    t_before = time.time()
    pet3.last_update_time = t_before - 0.1
    pet3.last_window_check_time = t_before  # 跳过窗口检查
    pet3.update_movement()
    print(f"spell期间idle_timer超阈值后: is_moving={pet3.is_moving}")
    if pet3.is_moving:
        print("FAIL: spell阶段被随机移动启动了")
    else:
        print("PASS: spell阶段没有随机移动")
except Exception as e:
    import traceback; traceback.print_exc()

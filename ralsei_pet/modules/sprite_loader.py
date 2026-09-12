import os
import re
import time
from collections import defaultdict
from PyQt5.QtGui import QPixmap, QColor, QPainter

try:
    from logger_utils import get_logger
    _log = get_logger(__name__)
except ImportError:  # 模块外独立导入时的降级
    import logging
    _log = logging.getLogger(__name__)

class SpriteLoader:
    def __init__(self):
        self.sprites = {}
        self.frame_counts = {}
        # 动态计算素材路径：相对于本文件向上两级（modules → ralsei_pet → 项目根）
        _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        self.sprite_dir = os.path.join(_project_root, "deltarune_ralsei")
        self.face_dir = os.path.join(_project_root, "ralsei_face")
        
        # 添加图像缓存，避免重复加载
        self.image_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_limit = 1000  # 缓存限制
        
        # 定义动画与文件的映射关系
        self.animation_mapping = {
            # 基础动作
            "idle": ["spr_ralsei_idle_0.png", "spr_ralsei_idle_1.png", "spr_ralsei_idle_2.png", "spr_ralsei_idle_3.png", "spr_ralsei_idle_4.png"],
            
            # 行走动画（不同情绪）
            "walk_down": ["spr_ralsei_walk_down_0.png", "spr_ralsei_walk_down_1.png", "spr_ralsei_walk_down_2.png", "spr_ralsei_walk_down_3.png"],
            "walk_down_unhappy": ["spr_ralsei_walk_down_unhappy_0.png", "spr_ralsei_walk_down_unhappy_1.png", "spr_ralsei_walk_down_unhappy_2.png", "spr_ralsei_walk_down_unhappy_3.png"],
            "walk_down_blush": ["spr_ralsei_walk_down_blush_0.png", "spr_ralsei_walk_down_blush_1.png", "spr_ralsei_walk_down_blush_2.png", "spr_ralsei_walk_down_blush_3.png"],
            "walk_left": ["spr_ralsei_walk_left_0.png", "spr_ralsei_walk_left_1.png", "spr_ralsei_walk_left_2.png", "spr_ralsei_walk_left_3.png"],
            "walk_left_unhappy": ["spr_ralsei_walk_left_unhappy_0.png", "spr_ralsei_walk_left_unhappy_1.png", "spr_ralsei_walk_left_unhappy_2.png", "spr_ralsei_walk_left_unhappy_3.png"],
            "walk_left_blush": ["spr_ralsei_walk_left_blush_0.png", "spr_ralsei_walk_left_blush_1.png", "spr_ralsei_walk_left_blush_2.png", "spr_ralsei_walk_left_blush_3.png"],
            "walk_right": ["spr_ralsei_walk_right_0.png", "spr_ralsei_walk_right_1.png", "spr_ralsei_walk_right_2.png", "spr_ralsei_walk_right_3.png"],
            "walk_right_unhappy": ["spr_ralsei_walk_right_unhappy_0.png", "spr_ralsei_walk_right_unhappy_1.png", "spr_ralsei_walk_right_unhappy_2.png", "spr_ralsei_walk_right_unhappy_3.png"],
            "walk_right_blush": ["spr_ralsei_walk_right_blush_0.png", "spr_ralsei_walk_right_blush_1.png", "spr_ralsei_walk_right_blush_2.png", "spr_ralsei_walk_right_blush_3.png"],
            "walk_up": ["spr_ralsei_walk_up_0.png", "spr_ralsei_walk_up_1.png", "spr_ralsei_walk_up_2.png", "spr_ralsei_walk_up_3.png"],
            # 注意：walk_up_blush / walk_up_unhappy 的帧文件在素材目录中不存在（1106 个 PNG 实测缺失），
            # 若保留 mapping 会加载"?"灰块占位帧。朝上走时脸红/不开心退化为普通 walk_up（无素材可用）。
            # 移除这两行可让 change_animation 走前缀回退（walk_up_blush → walk_up）。
            
            # 跑步动画
            "run_down": ["spr_ralsei_run_down_0.png", "spr_ralsei_run_down_1.png", "spr_ralsei_run_down_2.png", "spr_ralsei_run_down_3.png", "spr_ralsei_run_down_4.png", "spr_ralsei_run_down_5.png"],
            "run_left": ["spr_ralsei_run_left_0.png", "spr_ralsei_run_left_1.png", "spr_ralsei_run_left_2.png", "spr_ralsei_run_left_3.png", "spr_ralsei_run_left_4.png", "spr_ralsei_run_left_5.png"],
            "run_right": ["spr_ralsei_run_right_0.png", "spr_ralsei_run_right_1.png", "spr_ralsei_run_right_2.png", "spr_ralsei_run_right_3.png", "spr_ralsei_run_right_4.png", "spr_ralsei_run_right_5.png"],
            "run_up": ["spr_ralsei_run_up_0.png", "spr_ralsei_run_up_1.png", "spr_ralsei_run_up_2.png", "spr_ralsei_run_up_3.png", "spr_ralsei_run_up_4.png", "spr_ralsei_run_up_5.png"],
            
            # 表情和情绪动画
            "laugh": ["spr_ralsei_laugh_0.png", "spr_ralsei_laugh_1.png"],
            "cry": ["spr_ralsei_cry_loop_0.png", "spr_ralsei_cry_loop_1.png"],
            "cry_start": ["spr_ralsei_cry_start_0.png"],
            "cry_reverse": ["spr_ralsei_cry_reverse_0.png"],
            "surprised": ["spr_ralsei_surprised_down_0.png"],
            "surprised_down": ["spr_ralsei_down_surprised2.png"],
            "surprised_behind": ["spr_ralsei_shocked_behind.png"],
            "shocked_left": ["spr_ralsei_shocked_left_landed_0.png", "spr_ralsei_shocked_left_landed_1.png"],
            "shocked_right": ["spr_ralsei_shocked_right_landed_0.png", "spr_ralsei_shocked_right_landed_1.png"],
            "curtsy": ["spr_ralsei_curtsy_0.png", "spr_ralsei_curtsy_1.png", "spr_ralsei_curtsy_2.png"],
            "pose": ["spr_ralsei_pose_0.png"],
            "smile_left": ["spr_ralsei_smile_up_0.png"],
            "smile_right": ["spr_ralsei_smile_up_right_0.png"],
            "shocked_subtle_left": ["spr_ralsei_shocked_subtle_left_0.png"],
            "shocked_subtle_right": ["spr_ralsei_shocked_subtle_right_0.png"],
            "tea_surprised": ["spr_tea_party_ralsei_surprised_0.png"],
            
            # 动作动画
            "jump_ready": ["spr_ralsei_jump_up_ready_0.png"],
            "jump": ["spr_ralsei_jump_up_0.png", "spr_ralsei_jump_up_1.png", "spr_ralsei_jump_up_2.png"],
            "jump_ball": ["spr_ralsei_jump_ball_0.png", "spr_ralsei_jump_ball_1.png", "spr_ralsei_jump_ball_2.png", "spr_ralsei_jump_ball_3.png"],
            "fall": ["spr_ralsei_fall_back_0.png"],
            "land": ["spr_teacup_ralsei_land_0.png", "spr_teacup_ralsei_land_1.png", "spr_teacup_ralsei_land_2.png"],
            "slide": ["spr_ralsei_slide_0.png", "spr_ralsei_slide_1.png", "spr_ralsei_slide_2.png"],
            "roll": ["spr_ralsei_roll_0.png", "spr_ralsei_roll_1.png", "spr_ralsei_roll_2.png", "spr_ralsei_roll_3.png", "spr_ralsei_roll_4.png", "spr_ralsei_roll_5.png", "spr_ralsei_roll_6.png", "spr_ralsei_roll_7.png", "spr_ralsei_roll_8.png", "spr_ralsei_roll_9.png", "spr_ralsei_roll_10.png"],
            "dance": ["spr_ralsei_dance_0.png", "spr_ralsei_dance_1.png", "spr_ralsei_dance_2.png", "spr_ralsei_dance_3.png", "spr_ralsei_dance_4.png", "spr_ralsei_dance_5.png", "spr_ralsei_dance_6.png", "spr_ralsei_dance_7.png"],
            "spin": ["spr_ralsei_battleintro_0.png"],
            "bow": ["spr_ralsei_act_0.png"],
            "sing": ["spr_ralsei_sing_0.png"],
            "hug": ["spr_ralsei_hug_hatless_0.png", "spr_ralsei_hug_hatless_1.png", "spr_ralsei_hug_hatless_2.png", "spr_ralsei_hug_hatless_3.png"],
            "hug_stop": ["spr_ralsei_hug_stop_hatless_0.png", "spr_ralsei_hug_stop_hatless_1.png", "spr_ralsei_hug_stop_hatless_2.png", "spr_ralsei_hug_stop_hatless_3.png"],
            "cower": ["spr_ralsei_cower_arms_0.png"],
            "look_up": ["spr_ralsei_look_up_0.png", "spr_ralsei_look_up_1.png", "spr_ralsei_look_up_2.png", "spr_ralsei_look_up_3.png"],
            "nuzzle": ["spr_ralsei_nuzzle_0.png", "spr_ralsei_nuzzle_1.png", "spr_ralsei_nuzzle_2.png", "spr_ralsei_nuzzle_3.png", "spr_ralsei_nuzzle_4.png", "spr_ralsei_nuzzle_5.png"],
            "nuzzle1": ["spr_ralsei_nuzzle1_0.png"],
            "item": ["spr_ralsei_item_0.png", "spr_ralsei_item_1.png", "spr_ralsei_item_2.png", "spr_ralsei_item_3.png", "spr_ralsei_item_4.png", "spr_ralsei_item_5.png", "spr_ralsei_item_6.png"],
            "darkchurch_sit_happy": ["spr_ralsei_darkchurch_sit_happy_0.png"],
            "darkchurch_sit_sad": ["spr_ralsei_darkchurch_sit_sad_0.png"],
            "susie_throw_ready": ["spr_susieb_throwralseiready.png"],
            
            # 互动动画
            "wave_start": ["spr_ralsei_wave_start_0.png", "spr_ralsei_wave_start_1.png", "spr_ralsei_wave_start_2.png"],
            "wave": ["spr_ralsei_wave_down_0.png"],
            "wave_down": ["spr_ralsei_wave_down_0.png", "spr_ralsei_wave_down_1.png", "spr_ralsei_wave_down_2.png", "spr_ralsei_wave_down_3.png"],
            "victory": ["spr_ralsei_victory_0.png", "spr_ralsei_victory_1.png", "spr_ralsei_victory_2.png", "spr_ralsei_victory_3.png", "spr_ralsei_victory_4.png", "spr_ralsei_victory_5.png", "spr_ralsei_victory_6.png", "spr_ralsei_victory_7.png", "spr_ralsei_victory_8.png", "spr_ralsei_victory_9.png", "spr_ralsei_victory_10.png", "spr_ralsei_victory_11.png", "spr_ralsei_victory_12.png", "spr_ralsei_victory_13.png", "spr_ralsei_victory_14.png", "spr_ralsei_victory_15.png", "spr_ralsei_victory_16.png", "spr_ralsei_victory_17.png", "spr_ralsei_victory_18.png", "spr_ralsei_victory_19.png", "spr_ralsei_victory_20.png"],
            "act": ["spr_ralsei_act_0.png", "spr_ralsei_act_1.png", "spr_ralsei_act_2.png", "spr_ralsei_act_3.png", "spr_ralsei_act_4.png", "spr_ralsei_act_5.png", "spr_ralsei_act_6.png", "spr_ralsei_act_7.png", "spr_ralsei_act_8.png", "spr_ralsei_act_9.png", "spr_ralsei_act_10.png", "spr_ralsei_act_11.png", "spr_ralsei_act_12.png"],
            "spell": ["spr_ralsei_spell_0.png", "spr_ralsei_spell_1.png", "spr_ralsei_spell_2.png", "spr_ralsei_spell_3.png", "spr_ralsei_spell_4.png", "spr_ralsei_spell_5.png", "spr_ralsei_spell_6.png", "spr_ralsei_spell_7.png", "spr_ralsei_spell_8.png", "spr_ralsei_spell_9.png", "spr_ralsei_spell_10.png"],
            "spell_left": ["spr_ralsei_spell_left_0.png", "spr_ralsei_spell_left_1.png", "spr_ralsei_spell_left_2.png", "spr_ralsei_spell_left_3.png", "spr_ralsei_spell_left_4.png", "spr_ralsei_spell_left_5.png", "spr_ralsei_spell_left_6.png", "spr_ralsei_spell_left_7.png", "spr_ralsei_spell_left_8.png", "spr_ralsei_spell_left_9.png", "spr_ralsei_spell_left_10.png"],
            "battleintro": ["spr_ralsei_battleintro_0.png", "spr_ralsei_battleintro_1.png", "spr_ralsei_battleintro_2.png", "spr_ralsei_battleintro_3.png", "spr_ralsei_battleintro_4.png", "spr_ralsei_battleintro_5.png", "spr_ralsei_battleintro_6.png", "spr_ralsei_battleintro_7.png", "spr_ralsei_battleintro_8.png", "spr_ralsei_battleintro_9.png", "spr_ralsei_battleintro_10.png"],
            "defeat": ["spr_ralsei_defeat.png"],
            
            # 特殊状态动画
            "sleep": ["spr_ralsei_walk_down_sleep_0.png"],
            "tea": ["spr_ralsei_tea_0.png", "spr_ralsei_tea_1.png", "spr_ralsei_tea_2.png"],
            "teacup_land": ["spr_teacup_ralsei_land_0.png"],
            "hatless_throw": ["spr_ralsei_hatless_throw.png"],
            "splat": ["spr_cutscene_10_ralsei_splat.png"],
            # 修复：main.py 一直按"fall_mad 存在才播放生气摔倒动画"来判断
            # （start_fall 的 window_move / fall_from_window 分支），但这两个键从未在
            # 这里配置过 → 判断恒为假，需求"用户行为导致的摔倒要用生气那个动作"
            # 从未生效。素材 spr_cutscene_24e_ralsei_splat_mad.png 本来就在素材包里。
            "splat_mad": ["spr_cutscene_24e_ralsei_splat_mad.png"],
            "fall_mad": ["spr_cutscene_24e_ralsei_splat_mad.png"],
            "stool": ["spr_cutscene_10_ralsei_stool.png"],
            
            # 吃糖和茶会动画
            "cotton_candy_left": ["spr_cutscene_15_ralsei_cotton_candy_left_0.png", "spr_cutscene_15_ralsei_cotton_candy_left_1.png", "spr_cutscene_15_ralsei_cotton_candy_left_2.png", "spr_cutscene_15_ralsei_cotton_candy_left_3.png"],
            "cotton_candy_right": ["spr_cutscene_15_ralsei_cotton_candy_right_0.png", "spr_cutscene_15_ralsei_cotton_candy_right_1.png", "spr_cutscene_15_ralsei_cotton_candy_right_2.png", "spr_cutscene_15_ralsei_cotton_candy_right_3.png"],
            "cotton_surprise": ["spr_cutscene_15_ralsei_cotton_candy_surprise_0.png", "spr_cutscene_15_ralsei_cotton_candy_surprise_1.png", "spr_cutscene_15_ralsei_cotton_candy_surprise_2.png", "spr_cutscene_15_ralsei_cotton_candy_surprise_3.png"],
            "cotton_talk": ["spr_ralsei_cotton_talk_0.png", "spr_ralsei_cotton_talk_1.png"],
            "throw_ball": ["spr_cutscene_15_ralsei_throw_ball_0.png", "spr_cutscene_15_ralsei_throw_ball_1.png", "spr_cutscene_15_ralsei_throw_ball_2.png", "spr_cutscene_15_ralsei_throw_ball_3.png", "spr_cutscene_15_ralsei_throw_ball_4.png"],
            "walk_tea_up": ["spr_ralsei_walk_up_tea_0.png", "spr_ralsei_walk_up_tea_1.png", "spr_ralsei_walk_up_tea_2.png", "spr_ralsei_walk_up_tea_3.png"],
            "walk_tea_down": ["spr_ralsei_walk_down_tea_0.png", "spr_ralsei_walk_down_tea_1.png", "spr_ralsei_walk_down_tea_2.png", "spr_ralsei_walk_down_tea_3.png"],
            "walk_tea_left": ["spr_ralsei_walk_left_tea_0.png", "spr_ralsei_walk_left_tea_1.png", "spr_ralsei_walk_left_tea_2.png", "spr_ralsei_walk_left_tea_3.png"],
            "walk_tea_right": ["spr_ralsei_walk_right_tea_0.png", "spr_ralsei_walk_right_tea_1.png", "spr_ralsei_walk_right_tea_2.png", "spr_ralsei_walk_right_tea_3.png"],
            "tea_sip": ["spr_tea_party_ralsei_sip_0.png"],
            "tea_put_down": ["spr_tea_party_ralsei_put_down_0.png"],
            "tea_reach": ["spr_tea_party_ralsei_reach_0.png"],
            "tea_pour": ["spr_tea_party_ralsei_pour_0.png"],
            "tea_smile": ["spr_tea_party_ralsei_cake_smile_0.png"],
            "cake_eat": ["spr_tea_party_ralsei_cake_eat_0.png"],
            
            # 西装动画
            "walk_down_butler": ["spr_cutscene_20_ralsei_walk_down_butler_0.png", "spr_cutscene_20_ralsei_walk_down_butler_1.png", "spr_cutscene_20_ralsei_walk_down_butler_2.png", "spr_cutscene_20_ralsei_walk_down_butler_3.png"],
            "walk_down_butler_unhappy": ["spr_cutscene_20_ralsei_walk_down_butler_unhappy_0.png", "spr_cutscene_20_ralsei_walk_down_butler_unhappy_1.png", "spr_cutscene_20_ralsei_walk_down_butler_unhappy_2.png", "spr_cutscene_20_ralsei_walk_down_butler_unhappy_3.png"],
            "walk_left_butler": ["spr_cutscene_20_ralsei_walk_left_butler_0.png", "spr_cutscene_20_ralsei_walk_left_butler_1.png", "spr_cutscene_20_ralsei_walk_left_butler_2.png", "spr_cutscene_20_ralsei_walk_left_butler_3.png"],
            "walk_left_butler_unhappy": ["spr_cutscene_20_ralsei_walk_left_butler_unhappy_0.png", "spr_cutscene_20_ralsei_walk_left_butler_unhappy_1.png", "spr_cutscene_20_ralsei_walk_left_butler_unhappy_2.png", "spr_cutscene_20_ralsei_walk_left_butler_unhappy_3.png"],
            "walk_right_butler": ["spr_cutscene_20_ralsei_walk_right_butler_0.png", "spr_cutscene_20_ralsei_walk_right_butler_1.png", "spr_cutscene_20_ralsei_walk_right_butler_2.png", "spr_cutscene_20_ralsei_walk_right_butler_3.png"],
            "walk_right_butler_unhappy": ["spr_cutscene_20_ralsei_walk_right_butler_unhappy_0.png", "spr_cutscene_20_ralsei_walk_right_butler_unhappy_1.png", "spr_cutscene_20_ralsei_walk_right_butler_unhappy_2.png", "spr_cutscene_20_ralsei_walk_right_butler_unhappy_3.png"],
            "walk_up_butler": ["spr_cutscene_20_ralsei_walk_up_butler_0.png", "spr_cutscene_20_ralsei_walk_up_butler_1.png", "spr_cutscene_20_ralsei_walk_up_butler_2.png", "spr_cutscene_20_ralsei_walk_up_butler_3.png"],
            # walk_up_butler_unhappy 帧文件缺失，移除以免灰块；不开心朝上走回退 walk_up_butler
            
            # 眼镜相关动画
            "glasses_1": ["spr_cutscene_ex1_ralsei_glasses_1_0.png"],
            "glasses_2": ["spr_cutscene_ex1_ralsei_glasses_2_0.png"],
            
            # 地上状态动画
            "fall_back": ["spr_ralsei_fall_back_0.png", "spr_ralsei_fall_back_1.png", "spr_ralsei_fall_back_2.png", "spr_ralsei_fall_back_3.png", "spr_ralsei_fall_back_4.png"],
            "fall_back_cry": ["spr_ralsei_fall_back_cry_0.png", "spr_ralsei_fall_back_cry_1.png"],
            "fall_back_rub": ["spr_ralsei_fall_back_rub_0.png", "spr_ralsei_fall_back_rub_1.png"],
            "fall_back_wince": ["spr_ralsei_fall_back_wince_0.png"],
            "fall_back_expressions": ["spr_ralsei_fall_back_expressions_0.png", "spr_ralsei_fall_back_expressions_1.png", "spr_ralsei_fall_back_expressions_2.png", "spr_ralsei_fall_back_expressions_3.png", "spr_ralsei_fall_back_expressions_4.png"],
            "kneel_cry": ["spr_ralsei_kneel_cry_0.png", "spr_ralsei_kneel_cry_1.png"],
            "kneel_serious": ["spr_ralsei_kneel_serious_0.png"],

            # 情绪动画别名（复用现有素材：happy→laugh、neutral→idle、sad→站着哭泣前准备）
            # 修复：此前代码大量 play_animation_once("sad"/"happy"/"neutral") 以及
            # emotion_system 的 'sad' 动画映射在 sprite_loader 中不存在，全部静默退化为 idle。
            "happy": ["spr_ralsei_laugh_0.png", "spr_ralsei_laugh_1.png"],
            "neutral": ["spr_ralsei_idle_0.png", "spr_ralsei_idle_1.png", "spr_ralsei_idle_2.png", "spr_ralsei_idle_3.png", "spr_ralsei_idle_4.png"],
            "sad": ["spr_ralsei_cry_start_0.png"],

            # 毛线球动画
            "yarn_1": ["spr_ralseib_yarn_1.png"],
            "yarn_2": ["spr_ralseib_yarn_2.png"],
            
            # 其他动画
            "attack": ["spr_ralsei_attack_0.png", "spr_ralsei_attack_1.png", "spr_ralsei_attack_2.png", "spr_ralsei_attack_3.png", "spr_ralsei_attack_4.png", "spr_ralsei_attack_5.png", "spr_ralsei_attack_6.png"],
            "defend": ["spr_ralsei_defend_0.png", "spr_ralsei_defend_1.png", "spr_ralsei_defend_2.png", "spr_ralsei_defend_3.png", "spr_ralsei_defend_4.png", "spr_ralsei_defend_5.png", "spr_ralsei_defend_6.png", "spr_ralsei_defend_7.png"],
            "book_look": ["spr_ralsei_book_look_0.png", "spr_ralsei_book_look_1.png", "spr_ralsei_book_look_2.png", "spr_ralsei_book_look_3.png", "spr_ralsei_book_look_4.png", "spr_ralsei_book_look_5.png", "spr_ralsei_book_look_6.png", "spr_ralsei_book_look_7.png", "spr_ralsei_book_look_8.png", "spr_ralsei_book_look_9.png", "spr_ralsei_book_look_10.png", "spr_ralsei_book_look_11.png", "spr_ralsei_book_look_12.png", "spr_ralsei_book_look_13.png", "spr_ralsei_book_look_14.png", "spr_ralsei_book_look_15.png"],
            "button_press": ["spr_ralsei_button_press_0.png", "spr_ralsei_button_press_1.png", "spr_ralsei_button_press_2.png"],
        }
        
        # 位置偏移配置 - 用于调整不在中心的动画
        # 位置偏移配置 - 用于调整不在中心的动画
        # 修复：原先 100+ 个条目全部是 (0, 0)，与 get_position_offset() 的
        # .get(animation, (0, 0)) 默认值完全冗余（纯死数据，新动画还得记得来这补一条
        # 全零占位）。现在默认偏移由 .get() 兜底，字典仅存放【非零】的特例偏移，
        # 需要时用 set_position_offset() 或直接在此追加，例如：
        #   "jump": (0, -10),
        self.position_offset = {}
        
        # 自动扫描和分组的动画
        self.auto_scanned_animations = {}
        
        # 帧加载失败时的占位图像大小
        self.placeholder_size = (50, 80)

        # 表情素材名缓存（懒加载，供 has_face() 校验，避免每次 os.listdir）
        self._face_names = None

        # 所有精灵帧的最大包围盒（在 load_sprites 结束时填充）。
        # main.py 用它作为固定容器尺寸，让窗口大小永不因精灵而异而 setGeometry。
        self.frame_container_size = None  # (w, h)
        
    def scan_and_group_assets(self):
        """扫描素材文件夹并按前缀分组，支持多种文件命名格式"""
        if not os.path.exists(self.sprite_dir):
            _log.warning("素材文件夹 %s 不存在", self.sprite_dir)
            return
        
        # 使用defaultdict来存储前缀和对应的帧信息
        prefix_groups = defaultdict(list)
        
        # 获取文件夹中的所有png文件
        all_png_files = []
        for filename in os.listdir(self.sprite_dir):
            if filename.endswith(".png"):
                all_png_files.append(filename)
        
        _log.debug("找到 %d 个PNG文件", len(all_png_files))
        
        # 尝试多种命名格式来匹配文件
        for filename in all_png_files:
            # 格式1: prefix_0.png
            match1 = re.match(r'^(.*?)_([0-9]+)\.png$', filename)
            # 格式2: prefix0.png
            match2 = re.match(r'^(.*?)([0-9]+)\.png$', filename)
            # 格式3: prefix.png (单帧)
            match3 = re.match(r'^(.*?)\.png$', filename)
            
            if match1:
                prefix = match1.group(1)
                frame_number = int(match1.group(2))
                prefix_groups[prefix].append((frame_number, filename))
            elif match2 and not re.search(r'[0-9]+$', match2.group(1)):  # 避免重复匹配
                prefix = match2.group(1)
                frame_number = int(match2.group(2))
                prefix_groups[prefix].append((frame_number, filename))
            elif match3:
                prefix = match3.group(1)
                frame_number = 0  # 单帧文件视为第0帧
                prefix_groups[prefix].append((frame_number, filename))
        
        # 对每个前缀组内的帧按帧号排序
        for prefix, frames in prefix_groups.items():
            # 按帧号排序
            sorted_frames = sorted(frames, key=lambda x: x[0])
            # 只保留文件名
            self.auto_scanned_animations[prefix] = [frame_info[1] for frame_info in sorted_frames]
        
        # 按前缀名排序
        self.auto_scanned_animations = dict(sorted(self.auto_scanned_animations.items()))
        
        _log.debug("成功分组 %d 个动画组", len(self.auto_scanned_animations))
    
    def create_placeholder_image(self, size=None):
        """创建占位图像"""
        if size is None:
            size = self.placeholder_size
        
        placeholder = QPixmap(size[0], size[1])
        placeholder.fill(QColor(200, 200, 200, 200))
        
        # 在占位图像上绘制一个问号
        painter = QPainter(placeholder)
        painter.setPen(QColor(100, 100, 100))
        font = painter.font()
        font.setPointSize(36)
        painter.setFont(font)
        painter.drawText(placeholder.rect(), 1, "?")
        painter.end()
        
        return placeholder
    
    def load_frame(self, filename):
        """加载单个帧，参考niko_desktop_pet优化：支持多种文件命名格式"""
        # 检查缓存中是否已经有该文件
        if filename in self.image_cache:
            self.cache_hits += 1
            # 真正的LRU：命中时先删除再插入，把项移到末尾（表示最近使用）
            pixmap = self.image_cache.pop(filename)
            self.image_cache[filename] = pixmap
            return pixmap
        
        self.cache_misses += 1
        
        # 参考niko_desktop_pet，支持多种文件命名格式
        file_candidates = [
            filename,  # 优先：原始文件名
            filename.replace('.png', '.jpg'),  # 次选：jpg格式
            filename.replace('.jpg', '.png'),  # 次选：png格式
        ]
        
        pixmap = None
        loaded_ok = False

        # 尝试加载所有候选文件
        for candidate in file_candidates:
            path = os.path.join(self.sprite_dir, candidate)
            if os.path.exists(path):
                try:
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        loaded_ok = True
                        break  # 成功加载，退出循环
                except Exception as e:
                    _log.debug("加载帧 %s 失败: %s", path, e)

        if not loaded_ok:
            # 文件缺失：返回占位图但不缓存，避免后续补上真实文件后仍显示占位图
            pixmap = self.create_placeholder_image()
            return pixmap

        # 仅缓存真实加载成功的图像，支持 LRU 策略
        if len(self.image_cache) >= self.cache_limit:
            # 简单的LRU策略：移除最早添加的项
            oldest_key = next(iter(self.image_cache))
            del self.image_cache[oldest_key]

        self.image_cache[filename] = pixmap
        return pixmap
    
    def load_sprites(self, debug=False):
        """加载所有精灵，支持调试模式"""
        if debug:
            _log.debug("开始加载精灵，精灵目录: %s", self.sprite_dir)
            _log.debug("精灵目录是否存在: %s", os.path.exists(self.sprite_dir))
        
        # 记录加载开始时间
        start_time = time.time()
        
        # 先扫描并分组动画
        self.scan_and_group_assets()
        
        # 合并手动定义的动画映射和自动扫描的动画
        # 注意：自动扫描的动画只在手动映射中不存在时才添加
        all_animations = self.animation_mapping.copy()
        for animation_name, files in self.auto_scanned_animations.items():
            if animation_name not in all_animations:
                all_animations[animation_name] = files
        
        # 确保关键动画（如idle、walk）有足够的帧
        required_animations = ["idle", "walk_down", "walk_left", "walk_right", "walk_up"]
        
        # 预创建所有动画列表，避免重复分配内存
        for animation in all_animations:
            self.sprites[animation] = []
        
        # 批量加载所有帧
        for animation, files in all_animations.items():
            if debug:
                _log.debug("加载动画: %s", animation)
            
            # 预分配帧列表空间
            frames = []
            frames_reserved = [None] * len(files)
            
            # 加载所有帧
            for i, file in enumerate(files):
                frame = self.load_frame(file)
                if frame:
                    frames_reserved[i] = frame
            
            # 移除None值（如果有）
            self.sprites[animation] = [frame for frame in frames_reserved if frame is not None]
            self.frame_counts[animation] = len(self.sprites[animation])
            
            # 确保关键动画至少有1帧
            if animation in required_animations and self.frame_counts[animation] == 0:
                if debug:
                    _log.warning("关键动画 %s 没有加载到任何帧，创建默认帧", animation)
                # 创建默认的占位帧
                default_frame = self.create_placeholder_image((50, 80))
                self.sprites[animation] = [default_frame]
                self.frame_counts[animation] = 1

        # 计算"核心角色动作"的最大包围盒，给 UI 层做"固定容器尺寸"。
        # 只统计真正的角色动作（walk/run/idle/jump 等），排除 gameshow/plush/道具等大图。
        core_prefixes = (
            'spr_ralsei_idle',
            'spr_ralsei_walk',
            'spr_ralsei_run',
            'spr_ralsei_jump',
            'spr_ralsei_fall',
            'spr_ralsei_land',
            'spr_ralsei_laugh',
            'spr_ralsei_cry',
            'spr_ralsei_victory',
            'spr_ralsei_wave',
            'spr_ralsei_look_up',
            'spr_ralsei_smile',
            'spr_ralsei_surprised',
            'spr_ralsei_shocked',
            'spr_ralsei_dance',
            'spr_ralsei_sing',
            'spr_ralsei_hug',
            'spr_ralsei_act',
            'spr_ralsei_pose',
            'spr_ralsei_tea',
            'spr_ralsei_roll',
            'spr_ralsei_slide',
            'spr_ralsei_spell',
            'spr_ralsei_attack',
            'spr_ralsei_battleintro',
            'spr_ralsei_cower',
            'spr_ralsei_defend',
            'spr_ralsei_kneel',
            'spr_ralsei_nuzzle',
            'spr_ralsei_cotton',
            'spr_ralsei_book',
            'spr_ralsei_button',
            'spr_ralsei_throw',
            'spr_ralsei_hatless',
            'spr_ralsei_curtsy',
            'spr_ralsei_defeat',
            'spr_ralsei_bow',
            'spr_ralsei_spin',
            'spr_teacup_ralsei',
            'spr_cutscene_10_ralsei',
            'spr_cutscene_15_ralsei_cotton',
            'spr_cutscene_20_ralsei_walk',
            'spr_cutscene_27_ralsei',
            'spr_cutscene_ex1_ralsei',
            'spr_cutscene_20_ralsei_walk',
            'spr_susieb_throwralsei',
        )
        max_h = 0
        max_w = 0
        # Phase 1: 先拿所有核心帧的真实高度上限 max_h（spell 类也参与高度统计，因为它与 idle 高度接近）
        for animation_name, frames in self.sprites.items():
            name_lower = animation_name.lower() if isinstance(animation_name, str) else ''
            is_core = any(name_lower.startswith(p.lower()) for p in core_prefixes)
            if animation_name not in self.animation_mapping and not is_core:
                continue
            for f in frames:
                if f is not None and not f.isNull():
                    if f.height() > max_h:
                        max_h = f.height()
        # Phase 2: 以统一目标高度 target_h = max_h * 0.95 为准，
        # 对所有非 spell 核心帧做"保持长宽比缩到 target_h"的预计算，
        # 然后取"缩放后最大宽度"作为容器宽度——这样永远不会出现某帧宽度超容器
        # 而回退到 scaledToWidth（那会破坏高度一致，视觉上各状态大小不一）。
        target_h = max(1, int(max_h * 0.95)) if max_h > 0 else 50
        max_scaled_w = 0
        for animation_name, frames in self.sprites.items():
            name_lower = animation_name.lower() if isinstance(animation_name, str) else ''
            is_core = any(name_lower.startswith(p.lower()) for p in core_prefixes)
            if animation_name not in self.animation_mapping and not is_core:
                continue
            is_spell = name_lower.startswith('spr_ralsei_spell') or animation_name in ('spell', 'spell_left')
            # spell/spell_left 单独按实际宽度超界时保留原高度（特效溢出），
            # 不参与 Phase 2 的宽度统计——它们的施法特效允许超出容器边界居中绘制。
            if is_spell:
                continue
            for f in frames:
                if f is not None and not f.isNull():
                    fh = f.height()
                    if fh <= 0:
                        continue
                    ratio = target_h / float(fh)
                    sw = max(1, int(f.width() * ratio))
                    if sw > max_scaled_w:
                        max_scaled_w = sw
        # 兜底：至少要有非 0 的尺寸
        if max_scaled_w <= 0:
            max_scaled_w = 50
        if max_h <= 0:
            max_h = 80
        self.frame_container_size = (max_scaled_w, max_h)
        
        # 记录加载结束时间
        end_time = time.time()
        
        if debug:
            _log.debug("所有精灵加载完成！")
            _log.debug("=== 加载总结 ===")
            total_frames = sum(self.frame_counts.values())
            _log.debug("总计加载 %d 个动画，%d 帧", len(self.sprites), total_frames)
            _log.debug("加载耗时: %.2f 秒", end_time - start_time)
            _total_cache = self.cache_hits + self.cache_misses
            if _total_cache > 0:
                _log.debug("缓存命中率: %.1f%%", self.cache_hits / _total_cache * 100)
            else:
                _log.debug("缓存未使用")

            # 检查关键动画是否都已加载
            missing_animations = [anim for anim in required_animations if anim not in self.sprites or self.frame_counts[anim] == 0]
            if missing_animations:
                _log.warning("以下关键动画缺失或没有帧: %s", missing_animations)
            else:
                _log.debug("所有关键动画已成功加载！")
            
    def get_sprite(self, animation, frame, loop=True):
        """获取指定动画和帧的精灵，支持循环模式"""
        if animation not in self.sprites:
            return None
        
        frames = self.sprites[animation]
        frame_count = len(frames)
        if frame_count == 0:
            return None
        
        # 自动循环处理
        if loop:
            frame = frame % frame_count
        else:
            # 边界检查
            frame = max(0, min(frame, frame_count - 1))
        
        # 确保帧索引有效
        if 0 <= frame < frame_count:
            return frames[frame]
        else:
            return frames[0]
        
    def get_frame_count(self, animation):
        """获取动画的帧数量"""
        return self.frame_counts.get(animation, 0)
        
    def has_face(self, face_name):
        """检查表情素材是否存在（face_name 不含 .png 后缀）。
        供 UI 层做"缺图回退"，避免渲染灰色"?"占位头像。"""
        if not face_name:
            return False
        if self._face_names is None:
            try:
                self._face_names = {
                    f[:-4].lower() for f in os.listdir(self.face_dir)
                    if f.lower().endswith('.png')
                }
            except OSError as e:
                _log.debug("枚举表情素材失败（已忽略）: %s", e)
                self._face_names = set()
        return face_name.lower() in self._face_names

    def get_face(self, face_name):
        """获取表情图片"""
        # 检查缓存
        face_key = f"face_{face_name}"
        if face_key in self.image_cache:
            # 真正的LRU：命中时移到末尾
            pixmap = self.image_cache.pop(face_key)
            self.image_cache[face_key] = pixmap
            return pixmap

        file_path = os.path.join(self.face_dir, face_name + ".png")
        pixmap = None
        loaded_ok = False

        if os.path.exists(file_path):
            try:
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    loaded_ok = True
                else:
                    pixmap = None
            except Exception as e:
                _log.debug("sprite_loader 防御性异常（已忽略）: %s", e)

        if not loaded_ok:
            # 表情文件缺失：返回占位图但不缓存，与 load_frame 行为一致
            return self.create_placeholder_image((30, 30))

        # 缓存真实加载成功的表情，使用与 load_frame 一致的 LRU 策略
        if len(self.image_cache) >= self.cache_limit:
            oldest_key = next(iter(self.image_cache))
            del self.image_cache[oldest_key]

        self.image_cache[face_key] = pixmap
        return pixmap
        
    def get_position_offset(self, animation):
        """获取特定动画的位置偏移量"""
        return self.position_offset.get(animation, (0, 0))
        
    def set_position_offset(self, animation, offset_x, offset_y):
        """设置特定动画的位置偏移量"""
        self.position_offset[animation] = (offset_x, offset_y)
        
    def get_all_animations(self, include_empty=False):
        """获取所有可用动画名称列表，支持是否包含空动画"""
        if include_empty:
            return list(self.sprites.keys())
        return [anim for anim in self.sprites.keys() if self.frame_counts[anim] > 0]
    
    def get_cache_stats(self):
        """获取缓存统计信息"""
        return {
            "cache_size": len(self.image_cache),
            "cache_limit": self.cache_limit,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": self.cache_hits / (self.cache_hits + self.cache_misses) * 100 if (self.cache_hits + self.cache_misses) > 0 else 0
        }
    
    def clear_cache(self, clear_sprites=False):
        """清理缓存，可选是否同时清理精灵"""
        self.image_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        
        if clear_sprites:
            self.sprites.clear()
            self.frame_counts.clear()
            self.auto_scanned_animations.clear()
    
    def add_animation(self, animation_name, frame_files):
        """动态添加新动画"""
        if not isinstance(frame_files, list):
            return False
        
        # 加载新动画的所有帧
        frames = []
        for file in frame_files:
            frame = self.load_frame(file)
            if frame:
                frames.append(frame)
        
        # 更新动画数据
        self.sprites[animation_name] = frames
        self.frame_counts[animation_name] = len(frames)
        
        # 如果该动画没有帧，创建一个默认帧
        if len(frames) == 0:
            default_frame = self.create_placeholder_image()
            self.sprites[animation_name] = [default_frame]
            self.frame_counts[animation_name] = 1
        
        return True
    
    def get_animation_files(self, animation_name):
        """获取指定动画的帧文件列表"""
        if animation_name in self.animation_mapping:
            return self.animation_mapping[animation_name]
        elif animation_name in self.auto_scanned_animations:
            return self.auto_scanned_animations[animation_name]
        return []
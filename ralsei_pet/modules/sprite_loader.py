import os
import json
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

# H5 S1 自检用的结构性词表。
# 动画名里的"方向词/动作类型"是 f-string 动态拼接出来的（walk_{dir}、run_{dir}、
# walk_tea_{dir} 等），静态扫描看不到。这里只用于【诊断日志】，不参与任何加载/回退决策。
_DIRECTION_TOKENS = ('down', 'up', 'left', 'right')
_ANIM_TYPE_TOKENS = ('walk', 'run')

# ================== H5 S2：动画表外部化（JSON 优先，内置兜底）==================
# 目标结构见 `架构改造排期方案_H4-H5_2026-09-13.md` §4.1：
#   {schema_version, meta:{...}, groups:{名:{frames, loop?, offset?, alias_of?, legacy?}}}
# 三条硬约束：
#   1. 加载失败**绝不**让程序起不来——一律回落内置表（本文件内那张原表，原样保留）；
#   2. JSON 还原出的 dict 必须与内置表**深度相等**（由 verify_s2_animations_json.py 断言）；
#   3. 名字集合与语义不变，只是来源从代码变成文件。
ENV_ANIMATIONS_JSON = 'RALSEI_ANIMATIONS_JSON'
ANIMATIONS_JSON_SUBPATH = ('ralsei_pet', 'assets', 'animations.json')
SUPPORTED_SCHEMA_VERSIONS = (1,)
_GROUP_KNOWN_KEYS = ('frames', 'loop', 'offset', 'alias_of', 'legacy', 'comment')


def _project_root():
    """项目根：<根>/ralsei_pet/modules/sprite_loader.py → 向上两级。"""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


class SpriteLoader:
    def __init__(self):
        self.sprites = {}
        self.frame_counts = {}
        # 动态计算素材路径：相对于本文件向上两级（modules → ralsei_pet → 项目根）
        _root = _project_root()
        self.sprite_dir = os.path.join(_root, "deltarune_ralsei")
        self.face_dir = os.path.join(_root, "ralsei_face")
        
        # 添加图像缓存，避免重复加载
        self.image_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_limit = 1000  # 缓存限制
        
        # 定义动画与文件的映射关系
        # H5 S2：本字典从此是**兜底表**（原表原样保留，不删不改），
        # 实际生效的表由 _load_animation_config() 决定：assets/animations.json 优先，
        # 读不到 / 校验不过 → 回落本表。见下方 H5 S2 段落。
        _builtin_animation_mapping = {
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

        # ================= H5 S1：动画名未命中自检（纯观测，零行为变更）=================
        # 背景：mapping 里"缺了某个动画名"是静默的——调用方拿不到任何反馈（回退 idle、
        # 拒绝切换或返回 None）。而 walk_{dir}/run_{dir} 这类名字由 f-string 在运行时拼出，
        # 静态扫描不可能发现配置缺失。所以先把"未命中"变成一条可见的 WARNING + 计数，
        # 让它成为后续配置化改造（S2/S3）的输入清单与验收依据。
        self.animation_misses = {}   # {请求名: {'count', 'where': set, 'resolved': set}}
        self._miss_reported = set()  # 同一请求名只告警一次，避免每帧刷屏

        # ================= H5 S2：动画表外部化（JSON 优先，内置兜底）=================
        # 放在 __init__ 末尾：_load_animation_config() 会写 position_offset、
        # 读 sprite_dir，必须等这些字段都初始化完再执行。
        # animation_config_source ∈ {'json', 'builtin'}，供自检与回归断言使用。
        self.legacy_animations = set()
        self.animation_config_source = 'builtin'
        self.animation_mapping, self.animation_config_source = \
            self._load_animation_config(_builtin_animation_mapping)

    # ================== H5 S2：动画表加载与校验 ==================
    @staticmethod
    def _resolve_animations_json_path():
        """JSON 配置的查找顺序：环境变量覆盖 → <项目根>/ralsei_pet/assets/animations.json。

        环境变量是为了让验证脚本能在**不影响真实配置**的前提下指向临时文件。
        """
        override = os.environ.get(ENV_ANIMATIONS_JSON)
        if override:
            return os.path.abspath(override)
        return os.path.join(_project_root(), *ANIMATIONS_JSON_SUBPATH)

    def _load_animation_config(self, builtin):
        """加载动画表。**永不抛异常**：任何失败都回落内置表，保证程序起得来。

        返回值：(mapping, source)。source ∈ {'json', 'builtin'}。
        铁律：JSON 还原出来的 dict 必须与内置表**深度相等**——
        这条由 `verify_s2_animations_json.py` 机器断言，不靠人工核对。
        """
        path = self._resolve_animations_json_path()
        try:
            with open(path, encoding='utf-8') as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            _log.info("[anim-config] 未找到 %s → 使用内置动画表（%d 组）", path, len(builtin))
            return self._copy_mapping(builtin), 'builtin'
        except Exception as e:
            _log.error("[anim-config] 读取 %s 失败 → 回落内置动画表：%s", path, e)
            return self._copy_mapping(builtin), 'builtin'

        try:
            mapping = self._validate_animation_config(raw)
        except Exception as e:
            _log.error("[anim-config] %s 校验不通过 → 回落内置动画表：%s", path, e)
            return self._copy_mapping(builtin), 'builtin'

        self._report_animation_config(mapping, path, raw.get('schema_version'))
        return mapping, 'json'

    @staticmethod
    def _copy_mapping(mapping):
        """浅拷贝外层 + 拷贝帧列表：调用方修改不会污染内置表。"""
        return {name: list(frames) for name, frames in mapping.items()}

    def _validate_animation_config(self, raw):
        """结构校验 + 归一化成 {动画名: [帧文件名]}。校验不过就抛异常（由调用方回落）。"""
        if not isinstance(raw, dict):
            raise ValueError('顶层不是 JSON 对象')
        version = raw.get('schema_version')
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError('schema_version=%r 不受支持（支持 %s）'
                             % (version, list(SUPPORTED_SCHEMA_VERSIONS)))
        groups = raw.get('groups')
        if not isinstance(groups, dict) or not groups:
            raise ValueError('groups 缺失或为空')

        mapping = {}
        legacy = set()
        for name, spec in groups.items():
            if not isinstance(name, str) or not name or name != name.strip():
                raise ValueError('动画名非法: %r' % (name,))
            if not isinstance(spec, dict):
                raise ValueError('%s 的配置不是对象' % name)

            frames = spec.get('frames', [])
            if not isinstance(frames, list) or not all(isinstance(f, str) for f in frames):
                raise ValueError('%s.frames 不是字符串列表' % name)
            if 'loop' in spec and not isinstance(spec['loop'], bool):
                raise ValueError('%s.loop 不是布尔值' % name)
            offset = spec.get('offset', [0, 0])
            if not (isinstance(offset, list) and len(offset) == 2
                    and all(isinstance(v, int) and not isinstance(v, bool) for v in offset)):
                raise ValueError('%s.offset 不是 [int, int]' % name)
            alias_of = spec.get('alias_of')
            if alias_of is not None and not isinstance(alias_of, str):
                raise ValueError('%s.alias_of 不是字符串' % name)
            if 'legacy' in spec and not isinstance(spec['legacy'], bool):
                raise ValueError('%s.legacy 不是布尔值' % name)
            comment = spec.get('comment')
            if comment is not None and not (
                    isinstance(comment, str)
                    or (isinstance(comment, list) and all(isinstance(c, str) for c in comment))):
                raise ValueError('%s.comment 不是字符串或字符串列表' % name)

            unknown = sorted(k for k in spec if k not in _GROUP_KNOWN_KEYS)
            if unknown:
                _log.warning('[anim-config] %s 含未知字段 %s（已忽略）', name, unknown)

            mapping[name] = list(frames)
            if spec.get('legacy') is True:
                legacy.add(name)
            if any(offset):
                # 与内置表的 position_offset 同语义：只登记非零特例偏移。
                self.position_offset[name] = (offset[0], offset[1])

        # 别名第二遍解析（允许 alias_of 前向引用）
        for name, spec in groups.items():
            target = spec.get('alias_of')
            if not target:
                continue
            if target not in mapping:
                raise ValueError('%s.alias_of 指向不存在的动画 %r' % (name, target))
            alias_frames = list(mapping[target])
            if mapping[name] and mapping[name] != alias_frames:
                raise ValueError('%s 与 alias_of(%s) 的帧不一致' % (name, target))
            mapping[name] = alias_frames

        self.legacy_animations = legacy
        return mapping

    def _report_animation_config(self, mapping, path, schema_version):
        """加载成功后的自检报告：组数、别名、legacy、以及**引用缺失的帧文件**。

        缺帧只告警不拒绝——内置表历史上也允许缺帧（缺帧会被 load_sprites 跳过），
        若在此处直接拒绝反而会引入"以前能起、现在起不来"的新故障。
        """
        missing_total, missing_groups, samples = 0, [], []
        for name, frames in mapping.items():
            miss = [f for f in frames
                    if not os.path.exists(os.path.join(self.sprite_dir, f))]
            if miss:
                missing_total += len(miss)
                missing_groups.append(name)
                if len(samples) < 8:
                    samples.append('%s/%s' % (name, miss[0]))
        if missing_total:
            _log.warning('[anim-config] %s 引用了 %d 个磁盘上不存在的帧（涉及 %d 组）：%s%s',
                         os.path.basename(path), missing_total, len(missing_groups),
                         '、'.join(samples),
                         ' …' if len(missing_groups) > len(samples) else '')
        _log.info('[anim-config] 已从 %s 加载 %d 组动画（legacy %d 组，schema=%s）',
                  os.path.basename(path), len(mapping), len(self.legacy_animations),
                  schema_version)

    def get_animation_config_report(self):
        """动画表来源与差异清单，供启动自检 / 回归断言读取。"""
        path = self._resolve_animations_json_path()
        missing = {}
        for name, frames in self.animation_mapping.items():
            miss = [f for f in frames
                    if not os.path.exists(os.path.join(self.sprite_dir, f))]
            if miss:
                missing[name] = miss
        return {
            'source': self.animation_config_source,
            'path': path,
            'path_exists': os.path.exists(path),
            'groups': len(self.animation_mapping),
            'legacy_groups': sorted(self.legacy_animations),
            'missing_frames': missing,
            'missing_frame_total': sum(len(v) for v in missing.values()),
        }

    def get_unconfigured_asset_report(self):
        """补漏报告：自动扫描到、但**配置表里没有**的素材前缀。

        这是把 `scan_and_group_assets` 从"自动接管配置"降级为"只报告差异"的第一步。
        注意：本方法**只读不接管**——`load_sprites` 目前仍会把自动扫描结果并入
        `sprites`（见该方法的说明：那 380 组里有一部分命中 `core_prefixes`，
        参与 frame_container_size 的包围盒计算，直接停用会改变容器尺寸）。
        """
        auto = self.auto_scanned_animations or {}
        return sorted(name for name in auto if name not in self.animation_mapping)

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
            # 修复：dance2.png 与 dance_2.png 会被解析成同一帧号，原实现全部
            # 保留 → 动画出现重复帧；且同帧号顺序依赖 os.listdir（不稳定）。
            # 现在按 (帧号, 文件名) 稳定排序后按帧号去重，只保留每帧第一个。
            sorted_frames = sorted(frames, key=lambda x: (x[0], x[1]))
            seen_frames = set()
            deduped = []
            for frame_number, filename in sorted_frames:
                if frame_number in seen_frames:
                    _log.debug("动画 %s 帧号 %d 重复，忽略 %s", prefix, frame_number, filename)
                    continue
                seen_frames.add(frame_number)
                deduped.append(filename)
            # 只保留文件名
            self.auto_scanned_animations[prefix] = deduped
        
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
    
    def load_frame(self, filename, placeholder_on_missing=True):
        """加载单个帧，参考niko_desktop_pet优化：支持多种文件命名格式。

        修复：原实现缺图时一律返回灰色"?"占位图，而调用方以
        `if frame:` 判断（QPixmap 对象恒真），导致素材缺失时占位帧
        混进动画序列，Ralsei 动画中周期性闪出灰块。现在调用方可传
        placeholder_on_missing=False 让缺帧返回 None（由调用方决定
        跳过或兜底），保证正常动画序列里永不出现占位帧。
        """
        # 检查缓存中是否已经有该文件
        if filename in self.image_cache:
            self.cache_hits += 1
            # 真正的LRU：命中时先删除再插入，把项移到末尾（表示最近使用）
            pixmap = self.image_cache.pop(filename)
            self.image_cache[filename] = pixmap
            return pixmap
        
        self.cache_misses += 1
        
        # 参考niko_desktop_pet，支持多种文件命名格式
        # 修复：.png→.jpg 与 .jpg→.png 在特定文件名下会生成重复候选，
        # 白白多做一次磁盘探测；用有序去重保留语义。
        file_candidates = list(dict.fromkeys([
            filename,  # 优先：原始文件名
            filename.replace('.png', '.jpg'),  # 次选：jpg格式
            filename.replace('.jpg', '.png'),  # 次选：png格式
        ]))
        
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
            # 文件缺失：不缓存（避免后续补上真实文件后仍显示占位图）；
            # 是否返回占位图由调用方决定。
            if placeholder_on_missing:
                return self.create_placeholder_image()
            return None

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
        # H5 S2 备注：方案 §4.1 希望把 scan_and_group_assets 降级为"补漏报告器"
        # （只输出"磁盘有、配置无"的清单，不自动接管）。但实测那 380 组里有相当一部分
        # 命中下方 core_prefixes（组名就是文件前缀，如 spr_ralsei_idle），
        # 会参与 frame_container_size 的包围盒统计——直接停用会改变窗口容器尺寸，
        # 属于用户可见的视觉变更，不能藏在"配置化"里做。
        # 因此本轮只新增 get_unconfigured_asset_report()（只读报告），
        # 是否停用并入留待单独一步 + 单独度量（见 verify_s2_animations_json.py 的 G 组）。
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
            
            # 加载所有帧（修复：缺帧返回 None 并跳过，不把占位帧混入动画；
            # 仅当整个关键动画无帧时才由下方兜底逻辑创建占位帧）
            for i, file in enumerate(files):
                frame = self.load_frame(file, placeholder_on_missing=False)
                if frame is not None:
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
            
    # ================== H5 S1：动画名未命中自检 ==================
    @staticmethod
    def diagnose_dynamic_name(name):
        """对 f-string 拼接出来的动画名做结构性校验。

        返回问题描述字符串；结构正常返回 None。**只用于日志提示**，
        不参与加载、回退或任何行为决策。
        """
        if not isinstance(name, str) or not name:
            return '动画名为空或非字符串'
        parts = name.split('_')
        if parts[0] in _ANIM_TYPE_TOKENS or name.startswith('walk_tea'):
            dirs = [p for p in parts if p in _DIRECTION_TOKENS]
            if not dirs:
                return '缺少方向词（应为 %s 之一）' % '/'.join(_DIRECTION_TOKENS)
            if len(dirs) > 1:
                return '出现多个方向词: %s' % dirs
            digits = [p for p in parts[1:] if p.isdigit()]
            if digits:
                return '动画名里混入帧号: %s' % digits
        return None

    def note_animation_miss(self, requested, resolved=None, where='unknown'):
        """记录一次"请求的动画名不存在"。

        重复调用只累加计数；同名只告警一次（避免 update_animation 每帧刷屏）。
        返回 resolved，方便调用方一行内完成"记账 + 继续原逻辑"。
        """
        rec = self.animation_misses.get(requested)
        if rec is None:
            rec = {'count': 0, 'where': set(), 'resolved': set()}
            self.animation_misses[requested] = rec
        rec['count'] += 1
        rec['where'].add(where)
        rec['resolved'].add('<None>' if resolved is None else str(resolved))

        if requested not in self._miss_reported:
            self._miss_reported.add(requested)
            hint = self.diagnose_dynamic_name(requested)
            _log.warning(
                "[anim-miss] 动画名不存在: %r → 回退 %r (来源: %s)%s",
                requested,
                '<拒绝切换/返回 None>' if resolved is None else resolved,
                where,
                (' ；疑似拼接参数非法：' + hint) if hint else '',
            )
        return resolved

    def get_animation_miss_report(self):
        """未命中统计，按次数降序：[(请求名, 次数, [来源], [回退目标])]"""
        report = [
            (name, rec['count'], sorted(rec['where']), sorted(rec['resolved']))
            for name, rec in self.animation_misses.items()
        ]
        report.sort(key=lambda item: (-item[1], item[0]))
        return report

    def log_animation_miss_summary(self):
        """输出未命中汇总。无未命中时只留一行 INFO，便于回归时断言。"""
        report = self.get_animation_miss_report()
        if not report:
            _log.info("[anim-miss] 本轮运行未出现未命中的动画名（已加载 %d 组）",
                      len(self.sprites))
            return 0
        _log.warning("[anim-miss] 本轮共 %d 个动画名未命中，合计 %d 次：",
                     len(report), sum(item[1] for item in report))
        for name, count, where, resolved in report:
            _log.warning("  - %-30s x%-4d 来源=%s 回退=%s",
                         name, count, ','.join(where), ','.join(resolved))
        return len(report)

    def get_sprite(self, animation, frame, loop=True):
        """获取指定动画和帧的精灵，支持循环模式"""
        if animation not in self.sprites:
            self.note_animation_miss(animation, None, 'SpriteLoader.get_sprite')
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
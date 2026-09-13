# -*- coding: utf-8 -*-
"""修复 main.py 第三轮：splat恢复过渡/窗口摔倒台词矛盾/恢复时间过长/低速落地切走路"""

path = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src\main.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ========== 修复16: trigger_splat 恢复缺少爬起过渡 ==========
# 原代码：trigger_splat 设置 is_splat=True，update_animation 2秒后设 is_splat=False，
# 动画直接从 splat(摔扁) 切到 idle(站好)，没有"慢慢爬起来"的过程。
# 修复：trigger_splat 改为走分阶段摔倒流程（复用 _fall_phase）：
#   splat(2s) → dazed揉头(1s) → land爬起恢复(1.5s) → idle
old = '''    def trigger_splat(self):
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
        self.dialogue_ui.show_dialogue()'''
new = '''    def trigger_splat(self):
        """触发 splat 状态（先决条件：高速重力掉落/被甩飞等）。
        播放 snd_splat.wav 音效，然后走分阶段恢复：摔扁→晕乎揉头→爬起来。"""
        # 修复：不再用 is_splat 独立计时（2秒后直接切idle太突兀）。
        # 改为走 handle_fall 的 _fall_phase 分阶段流程，有完整的爬起过渡。
        self.is_splat = True
        self.splat_start_time = time.time()
        self.is_moving = False
        self.is_falling = True
        self.is_recovering = False
        self.fall_duration = 0.0
        self.fall_start_time = time.time()
        self._fall_phase = "splat"  # 直接从摔扁阶段开始（已经落地了）
        self.max_fall_duration = 3.0  # splat(2s) + dazed(1s)
        self.recovery_max_duration = 1.5  # 爬起恢复1.5秒
        # 播放 splat 音效
        try:
            self.sound_manager.play_splat()
        except Exception as e:
            _log.debug("main 防御性异常（已忽略）: %s", e)
        # 切换到 splat 动画
        self.change_animation("splat", force=True)
        # 显示惊讶对话
        self.dialogue_ui.add_dialogue("ralsei", "啊！摔扁了...", "surprised")
        self.dialogue_ui.show_dialogue()'''
assert old in content, "修复16 old not found"
content = content.replace(old, new)

# ========== 修复17: update_animation 中 splat 独立计时与新流程冲突 ==========
# 原代码：is_splat 时强制 new_animation="splat"，2秒后 is_splat=False。
# 现在 trigger_splat 走 _fall_phase 流程，is_splat 由 handle_fall 管理。
# 但如果有其他地方直接设 is_splat=True（如旧代码路径），这里仍需兜底。
# 修改：is_splat 超时后不直接切idle，而是播 land 动画过渡一下。
old = '''        # splat 状态：由重力掉落/摔倒等先决条件触发（非随机）
        # 触发后播放 snd_splat.wav，约2秒后恢复（符合需求：recovers after about 2 seconds）
        if hasattr(self, 'is_splat') and self.is_splat:
            new_animation = "splat"
            if not hasattr(self, 'splat_start_time') or self.splat_start_time is None:
                self.splat_start_time = current_time
            # 约 2 秒后恢复
            if current_time - self.splat_start_time >= 2.0:
                self.is_splat = False
                self.splat_start_time = None'''
new = '''        # splat 状态：由重力掉落/摔倒等先决条件触发（非随机）
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
                    self.play_animation_once("land")'''
assert old in content, "修复17 old not found"
content = content.replace(old, new)

# ========== 修复18: start_fall 窗口移动摔倒台词与动画情绪矛盾 ==========
# 原代码：window_move 用 fall_mad（生气摔扁）动画，台词却是"惊讶"语气。
# 修复：台词改为带点生气/抱怨的语气，匹配生气动画。
old = '''        if reason == "window_move":
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
            self.is_moving = False'''
new = '''        if reason == "window_move":
            # 用户移动窗口导致摔倒——用户行为造成的，用生气的摔倒动画
            if "fall_mad" in self.sprite_loader.sprites:
                self.change_animation("fall_mad", force=True)
            else:
                self.change_animation("fall", force=True)
            self.max_fall_duration = 3.0
            # 修复：台词匹配生气动画——抱怨用户乱动窗口，而不是单纯惊讶
            self.dialogue_ui.add_dialogue("ralsei", "喂！别乱动窗口呀！我站不稳了...", "surprised")
            self.is_moving = False'''
assert old in content, "修复18 old not found"
content = content.replace(old, new)

# ========== 修复19: start_fall 恢复时间过长 ==========
# 原代码：recovery_max_duration = 5.0 秒，加上摔倒3-5秒，总共8-10秒趴在地上。
# 修复：恢复时间改为2.5秒，更符合"摔倒→晕一会→爬起来"的自然节奏。
old = '''        self.is_falling = True
        self.fall_duration = 0.0
        self.fall_start_time = time.time()  # 设置摔倒开始时间
        self.is_recovering = False  # 是否处于恢复期
        self.recovery_duration = 0.0  # 恢复期持续时间
        self.recovery_max_duration = 5.0  # 恢复期最大持续时间（秒）'''
new = '''        self.is_falling = True
        self.fall_duration = 0.0
        self.fall_start_time = time.time()
        self.is_recovering = False
        self.recovery_duration = 0.0
        # 修复：恢复时间从5秒降到2.5秒。
        # 人摔倒后晕一会就爬起来了，5秒恢复期+3-5秒摔倒=8-10秒趴在地上太久了。
        self.recovery_max_duration = 2.5'''
assert old in content, "修复19 old not found"
content = content.replace(old, new)

# ========== 修复20: 低速重力掉落落地后直接切走路动画 ==========
# 原代码：handle_gravity_fall 低速落地时 change_animation(f"walk_{direction}")。
# 问题：刚落地应该先站稳(idle)，不是立刻开始走。
old = '''            else:
                # 低速摔落，切换回正常动画
                self.change_animation(f"walk_{self.current_direction}")
            
            # 更新当前楼层信息
            self.current_floor = drop_floor'''
new = '''            else:
                # 低速摔落：先站稳(idle)，而不是立刻开始走路
                self.change_animation("idle", force=True)

            # 更新当前楼层信息
            self.current_floor = drop_floor'''
assert old in content, "修复20 old not found"
content = content.replace(old, new)

# 同样修复桌面底部落地的低速分支
old = '''                else:
                    # 低速摔落，切换回正常动画
                    self.change_animation(f"walk_{self.current_direction}")'''
new = '''                else:
                    # 低速摔落：先站稳(idle)
                    self.change_animation("idle", force=True)'''
assert old in content, "修复20b old not found"
content = content.replace(old, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('main.py 修复16-20完成: splat爬起过渡/窗口摔倒台词/恢复时间/低速落地')

# -*- coding: utf-8 -*-
"""修复 update_animation 中 is_falling 分支覆盖分阶段摔倒动画的问题"""

path = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src\main.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''        elif self.is_falling:
            # 摔倒状态，保持摔倒动画
            # 修复：时长统一由 handle_fall 按 max_fall_duration（3~5 秒）管理，
            # 这里不再硬编码 1 秒截断（否则 3/5 秒摔倒需求被破坏、恢复完成逻辑永不执行）。
            # 修复：保留 start_fall 按原因选择的动画（fall / fall_mad），不要强制覆盖成 fall_back。
            if self.current_animation not in ('fall', 'fall_mad', 'fall_back'):
                new_animation = "fall_back"
            else:
                new_animation = self.current_animation'''
new = '''        elif self.is_falling:
            # 摔倒状态：动画由 handle_fall 管理。
            # 有 _fall_phase 时（甩飞/重力splat的分阶段流程：flying/splat/dazed），
            # handle_fall 会主动切换 jump_ball/splat/fall_back_rub，这里不要覆盖。
            # 无 _fall_phase 时（旧 start_fall 路径），保持 fall/fall_mad 不被覆盖。
            if hasattr(self, '_fall_phase'):
                new_animation = self.current_animation
            elif self.current_animation not in ('fall', 'fall_mad', 'fall_back'):
                new_animation = "fall_back"
            else:
                new_animation = self.current_animation'''
assert old in content, "修复21 old not found"
content = content.replace(old, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('main.py 修复21完成: is_falling分支不再覆盖分阶段摔倒动画')

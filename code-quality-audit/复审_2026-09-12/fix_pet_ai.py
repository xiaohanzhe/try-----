# -*- coding: utf-8 -*-
"""pet_ai.py 修复（第4区块）：
1) trigger_event 庆祝动画被白名单拦截（升级/进化/游戏开始跳不起来）
2) react_to_event 缺 user_dragged_forcefully 分支 + 未知事件静默 + 无顶层保护"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\pet_ai.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

def patch(old, new):
    global src
    assert old in src, f"NOT FOUND:\n{old[:200]}"
    assert src.count(old) == 1, f"NOT UNIQUE:\n{old[:200]}"
    src = src.replace(old, new, 1)

# ---- 1) trigger_event：jump/victory/dance 被 _BASIC_ANIM_WHITELIST 拦截，
#      升级/进化/游戏开始永远跳不起来。这些是明确的庆祝事件，直接 force 播放
#      一次（与 ai_driver 的 play_animation_once 语义一致），不再走白名单。 ----
patch(
"""        if event_type == 'game_start':
            game_name = event_data.get('game_name', '游戏')
            self.parent.dialogue_ui.add_dialogue("ralsei", f"好耶！一起来玩{game_name}吧！", "happy")
            self.parent.dialogue_ui.show_dialogue()
            self.trigger_action("jump")
        elif event_type == 'creative_activity_start':
            activity_name = event_data.get('activity_name', '创意活动')
            self.parent.dialogue_ui.add_dialogue("ralsei", f"哇，{activity_name}！我来帮忙～", "happy")
            self.parent.dialogue_ui.show_dialogue()
        elif event_type == 'level_up':
            new_level = event_data.get('new_level', 0)
            self.parent.dialogue_ui.add_dialogue("ralsei", f"升级啦！现在是等级 {new_level}～", "happy")
            self.parent.dialogue_ui.show_dialogue()
            self.trigger_action("victory")
        elif event_type == 'evolution':
            stage = event_data.get('stage', 1)
            self.parent.dialogue_ui.add_dialogue("ralsei", f"进化了呢！现在是第 {stage} 阶段！", "happy")
            self.parent.dialogue_ui.show_dialogue()
            self.trigger_action("dance")""",
"""        if event_type == 'game_start':
            game_name = event_data.get('game_name', '游戏')
            self.parent.dialogue_ui.add_dialogue("ralsei", f"好耶！一起来玩{game_name}吧！", "happy")
            self.parent.dialogue_ui.show_dialogue()
            self.parent.change_animation("jump", force=True)
        elif event_type == 'creative_activity_start':
            activity_name = event_data.get('activity_name', '创意活动')
            self.parent.dialogue_ui.add_dialogue("ralsei", f"哇，{activity_name}！我来帮忙～", "happy")
            self.parent.dialogue_ui.show_dialogue()
            self.parent.change_animation("wave", force=True)
        elif event_type == 'level_up':
            new_level = event_data.get('new_level', 0)
            self.parent.dialogue_ui.add_dialogue("ralsei", f"升级啦！现在是等级 {new_level}～", "happy")
            self.parent.dialogue_ui.show_dialogue()
            # 修复：trigger_action("victory") 被表演动画白名单拦截（永远不触发），
            # 升级庆祝需要立刻可见，改用 force 播放一次。
            self.parent.change_animation("dance", force=True)
        elif event_type == 'evolution':
            stage = event_data.get('stage', 1)
            self.parent.dialogue_ui.add_dialogue("ralsei", f"进化了呢！现在是第 {stage} 阶段！", "happy")
            self.parent.dialogue_ui.show_dialogue()
            self.parent.change_animation("dance", force=True)""")

# ---- 2) react_to_event：加 user_dragged_forcefully 分支 + 未知事件日志 +
#      顶层 try 保护（此方法被 main 鼠标事件与模块链路调用，异常不应冒泡）。 ----
patch(
"""    def react_to_event(self, event_type, event_data):
        # 对事件做出反应
        if event_type == "user_clicked":""",
"""    def react_to_event(self, event_type, event_data):
        # 对事件做出反应
        # 修复：顶层保护——本方法被 main 鼠标事件/各模块直接调用，
        # 任一分支抛异常都会冒泡（鼠标事件处理中甚至可能打断 Qt 事件循环）。
        try:
            return self._react_to_event_impl(event_type, event_data)
        except Exception as e:
            _log.debug("pet_ai react_to_event 防御性异常（已忽略）: %s", e)
            return None

    def _react_to_event_impl(self, event_type, event_data):
        # 对事件做出反应
        if event_type == "user_clicked":""")

patch(
"""        elif event_type == "excel_action":
            # Excel操作事件
            action = event_data.get("action")
            excel_path = event_data.get("path")
            sheet_name = event_data.get("sheet")
            cell_range = event_data.get("range")
            data = event_data.get("data")
            if action and excel_path:
                result = self.parent.desktop_interaction.excel_control(action, excel_path, sheet_name, cell_range, data)
                if result:
                    self.parent.dialogue_ui.add_dialogue("ralsei", f"Excel操作 '{action}' 执行成功！", "happy")
                else:
                    self.parent.dialogue_ui.add_dialogue("ralsei", f"Excel操作 '{action}' 执行失败了...", "sad")
                self.parent.dialogue_ui.show_dialogue()""",
"""        elif event_type == "excel_action":
            # Excel操作事件
            action = event_data.get("action")
            excel_path = event_data.get("path")
            sheet_name = event_data.get("sheet")
            cell_range = event_data.get("range")
            data = event_data.get("data")
            if action and excel_path:
                result = self.parent.desktop_interaction.excel_control(action, excel_path, sheet_name, cell_range, data)
                if result:
                    self.parent.dialogue_ui.add_dialogue("ralsei", f"Excel操作 '{action}' 执行成功！", "happy")
                else:
                    self.parent.dialogue_ui.add_dialogue("ralsei", f"Excel操作 '{action}' 执行失败了...", "sad")
                self.parent.dialogue_ui.show_dialogue()
        elif event_type == "user_dragged_forcefully":
            # 修复：此前 main.py 已触发该事件但这里无分支 → 静默无反应。
            # 被甩飞时给一点惊吓+委屈情绪（动画由 main 处理，这里不抢）。
            try:
                self.parent.emotion_system.add_emotion("surprised", 15)
            except Exception:
                pass
        else:
            # 修复：未知事件不再静默——留一条 debug 便于日后补分支，
            # 也避免"已触发但无反应"的问题再次变成黑盒。
            _log.debug("react_to_event 收到未处理事件类型: %s", event_type)""")

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("pet_ai.py patched OK")

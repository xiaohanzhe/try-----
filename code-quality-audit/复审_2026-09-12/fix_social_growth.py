# -*- coding: utf-8 -*-
"""social_growth_system.py 修复（第5区块）：
1) 20 个成就在 conditions 中无判定 → 永不可解锁
2) _check_evolution 依赖 level%5==0 → 跳级时漏进化
3) 成就奖励递归加深度保护"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\social_growth_system.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

def patch(old, new):
    global src
    assert old in src, f"NOT FOUND:\n{old[:200]}"
    assert src.count(old) == 1, f"NOT UNIQUE:\n{old[:200]}"
    src = src.replace(old, new, 1)

# ---- 1) _check_evolution：跳级（一次获得大额经验）时逐级触发进化。
#      原条件 level % 5 == 0 只在恰好 5/10/15/20 级那一拍成立，
#      1级直升6级会漏掉5级进化。改为 stage 落后就补触发。 ----
patch(
"""    def _check_evolution(self):
        \"\"\"检查是否进化\"\"\"
        # 每5级进化一次
        # 修复：条件和赋值保持一致，避免第一次进化（5级）阶段值不变的bug
        # 之前的实现：条件用 level//5+1 判断，但赋值用 level//5，导致 5级时 stage 仍是 1
        target_stage = self.level // 5 + 1  # 1级→1阶段, 5级→2阶段, 10级→3阶段...
        if self.level % 5 == 0 and self.evolution_stage < target_stage:
            self.evolution_stage = target_stage
            _log.info("进化了！现在是第 %d 阶段！", self.evolution_stage)
            # 触发进化事件
            self.parent.pet_ai.trigger_event('evolution', {
                'stage': self.evolution_stage,
                'path': self.evolution_path,
                'level': self.level
            })
            # 显示进化消息
            self.parent.dialogue_ui.add_dialogue("ralsei", f"我进化了！现在是更强大的 {self.evolution_stage} 阶段！", "happy_extremely")""",
"""    def _check_evolution(self):
        \"\"\"检查是否进化\"\"\"
        # 每5级进化一次
        # 修复：原条件 level % 5 == 0 只在恰好 5/10/15/20 级那一拍成立，
        # 游戏奖励/成就奖励一次给大额经验跳级时（1级直升6级等）会漏掉
        # 5级进化。改为"目标阶段落后就逐级补触发"，跳几级触发几次，
        # 每次进化都有对话与事件反馈。
        target_stage = self.level // 5 + 1  # 1级→1阶段, 5级→2阶段, 10级→3阶段...
        while self.evolution_stage < target_stage:
            self.evolution_stage += 1
            _log.info("进化了！现在是第 %d 阶段！", self.evolution_stage)
            # 触发进化事件
            self.parent.pet_ai.trigger_event('evolution', {
                'stage': self.evolution_stage,
                'path': self.evolution_path,
                'level': self.level
            })
            # 显示进化消息
            self.parent.dialogue_ui.add_dialogue("ralsei", f"我进化了！现在是更强大的 {self.evolution_stage} 阶段！", "happy_extremely")""")

# ---- 2) _check_achievements：补齐全部成就的条件判定。
#      （33 个成就原先只有 13 个有 conditions，其余 20 个永远无法解锁） ----
patch(
"""            # 冒险类 — 基于等级
            'adventurer': lambda s: s['level'] >= 6,
        }""",
"""            # 冒险类 — 基于等级
            'adventurer': lambda s: s['level'] >= 6,
            'explorer': lambda s: s['level'] >= 12,
            'game_master': lambda s: s['level'] >= 8,

            # 创造成就 — 基于等级
            'creator': lambda s: s['level'] >= 6,
            'designer': lambda s: s['level'] >= 7,
            'storyteller': lambda s: s['level'] >= 9,

            # 守护者成就 — 基于等级
            'guardian': lambda s: s['level'] >= 10,
            'caretaker': lambda s: s['level'] >= 15,
            'protector': lambda s: s['level'] >= 18,

            # 导师成就 — 基于等级
            'mentor': lambda s: s['level'] >= 5,
            'teacher': lambda s: s['level'] >= 11,
            'guide': lambda s: s['level'] >= 16,

            # 社交成就 — 基于等级
            'social_butterfly': lambda s: s['level'] >= 4,
            'popular': lambda s: s['level'] >= 13,
            'community_leader': lambda s: s['level'] >= 17,

            # 成长成就 — 基于等级/进化
            'level_10': lambda s: s['level'] >= 10,
            'level_20': lambda s: s['level'] >= 20,
            'evolution_master': lambda s: s['evolution_stage'] >= 5,
        }""")

# ---- 3) _unlock_achievement：递归深度保护（成就奖励加经验 → 可能连锁解锁更多
#      成就 → 递归。unlocked 已防重复，但加深度上限兜底极端情况）。 ----
patch(
"""    def _unlock_achievement(self, achievement_id):
        \"\"\"解锁成就\"\"\"
        if achievement_id in self.achievements_list and achievement_id not in self.achievements:""",
"""    def _unlock_achievement(self, achievement_id):
        \"\"\"解锁成就\"\"\"
        # 修复：成就奖励 add_experience → _check_achievements 可能连锁解锁
        # 下一批成就（递归）。unlocked 状态能防重复，但极端情况下（大量成就
        # 同时满足）递归层数可达成就总数，加深度上限兜底。
        depth = getattr(self, '_unlock_depth', 0) + 1
        if depth > 40:
            _log.warning("成就解锁递归过深，终止本轮解锁（depth=%d）", depth)
            return
        self._unlock_depth = depth
        try:
            self._unlock_achievement_impl(achievement_id)
        finally:
            self._unlock_depth = depth - 1

    def _unlock_achievement_impl(self, achievement_id):
        \"\"\"解锁成就（实际执行）\"\"\"
        if achievement_id in self.achievements_list and achievement_id not in self.achievements:""")

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("social_growth_system.py patched OK")

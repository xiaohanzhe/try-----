# -*- coding: utf-8 -*-
"""entertainment_system.py 修复（第5区块）：原子写 + difficulty 防御"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\entertainment_system.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

def patch(old, new):
    global src
    assert old in src, f"NOT FOUND:\n{old[:200]}"
    assert src.count(old) == 1, f"NOT UNIQUE:\n{old[:200]}"
    src = src.replace(old, new, 1)

# ---- 1) save_entertainment_data 原子写（与 customization_system 同款修复） ----
patch(
"""    def save_entertainment_data(self):
        \"\"\"保存娱乐数据\"\"\"
        try:
            entertainment_data = {
                'activity_stats': self.activity_stats,
                'recent_activities': self.recent_activities,
                'game_achievements': self.game_achievements,
                'creative_achievements': self.creative_achievements
            }
            with open(self.entertainment_data_path, 'w', encoding='utf-8') as f:
                json.dump(entertainment_data, f, ensure_ascii=False, indent=2)
            _log.debug("成功保存娱乐数据: %s", self.entertainment_data_path)
        except Exception as e:
            _log.warning("保存娱乐数据失败: %s", e)""",
"""    def save_entertainment_data(self):
        \"\"\"保存娱乐数据\"\"\"
        try:
            entertainment_data = {
                'activity_stats': self.activity_stats,
                'recent_activities': self.recent_activities,
                'game_achievements': self.game_achievements,
                'creative_achievements': self.creative_achievements
            }
            # 修复：临时文件 + os.replace 原子替换，避免写入中途崩溃留下损坏
            # JSON（下次加载失败 → 游戏/创作成就全部丢失）。
            tmp_path = self.entertainment_data_path + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(entertainment_data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.entertainment_data_path)
            _log.debug("成功保存娱乐数据: %s", self.entertainment_data_path)
        except Exception as e:
            _log.warning("保存娱乐数据失败: %s", e)
            try:
                if os.path.exists(self.entertainment_data_path + ".tmp"):
                    os.remove(self.entertainment_data_path + ".tmp")
            except Exception:
                pass""")

# ---- 2) end_game：difficulty 防御（调用方可能传未校验难度 → ValueError 崩溃） ----
patch(
"""        # 计算经验奖励
        difficulty_index = game['difficulty'].index(difficulty)
        base_reward = game['experience_reward'][difficulty_index]""",
"""        # 计算经验奖励
        # 修复：start_game 校验过难度，但 end_game 可被直接调用（外部/测试），
        # 传非法难度时 game['difficulty'].index(difficulty) 抛 ValueError 让
        # 整次结算崩溃。非法难度按最低难度（easy）兜底。
        try:
            difficulty_index = game['difficulty'].index(difficulty)
        except ValueError:
            difficulty_index = 0
        base_reward = game['experience_reward'][difficulty_index]""")

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("entertainment_system.py patched OK")

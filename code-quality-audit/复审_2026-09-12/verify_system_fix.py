# -*- coding: utf-8 -*-
"""第5区块修复验证：social_growth / customization / entertainment"""
import os
import sys
import tempfile
import json

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet", "modules"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)


class FakePetAI:
    def __init__(self):
        self.events = []
    def trigger_event(self, etype, data=None):
        self.events.append((etype, data or {}))


class FakeDUI:
    def __init__(self):
        self.msgs = []
    def add_dialogue(self, *a, **k):
        self.msgs.append(a)
    def show_dialogue(self, *a, **k):
        pass


class FakeSocialGrowth:
    def __init__(self):
        self.level = 1
        self.calls = []
    def get_level(self):
        return self.level
    def add_experience(self, n):
        self.calls.append(n)


class FakeParent:
    def __init__(self):
        self.pet_ai = FakePetAI()
        self.dialogue_ui = FakeDUI()
        self.social_growth = FakeSocialGrowth()
        self.emotion_system = sys.modules.get("emotion_system") or None


def test_evolution_jump_levels():
    from social_growth_system import SocialGrowthSystem
    p = FakeParent()
    s = SocialGrowthSystem(p)
    # 隔离：数据路径改到临时目录
    tmp = tempfile.mkdtemp()
    s.growth_data_path = os.path.join(tmp, "growth.json")
    # 模拟跳级后的状态：一次大额经验让 level 直接从 1 → 20（5的倍数检查拍不中）
    s.experience = 1900
    s.level = 20
    s.evolution_stage = 1
    s.achievements = []
    s._check_evolution()
    # 1级进化阶段 → 20级目标 5 阶段：应逐级触发 2/3/4/5 四次进化
    ev = [e for e in p.pet_ai.events if e[0] == "evolution"]
    assert len(ev) == 4, f"跳级应逐级触发4次进化，实际 {len(ev)}: {p.pet_ai.events}"
    assert s.evolution_stage == 5, s.evolution_stage
    print(f"[PASS] 跳级(1→20)逐级进化4次: {[e[1].get('stage') for e in ev]}")


def test_all_achievements_have_conditions():
    from social_growth_system import SocialGrowthSystem
    p = FakeParent()
    s = SocialGrowthSystem(p)
    tmp = tempfile.mkdtemp()
    s.growth_data_path = os.path.join(tmp, "growth.json")
    s.achievements = []
    # 20 级 + 5 阶段 → 全部等级/进化类成就应可解锁
    s.level = 20
    s.experience = 1900
    s.evolution_stage = 5
    s._check_achievements()
    unlocked = set(s.achievements)
    for aid in ("level_10", "level_20", "evolution_master", "explorer",
                "game_master", "creator", "mentor", "guardian", "caretaker",
                "protector", "teacher", "guide", "social_butterfly", "popular",
                "community_leader", "designer", "storyteller"):
        assert aid in unlocked, f"成就 {aid} 未解锁: {sorted(unlocked)}"
    print(f"[PASS] 补齐的成就全部可解锁（共 {len(unlocked)} 个）")


def test_customization_atomic_save_and_bad_load():
    from customization_system import CustomizationSystem
    p = FakeParent()
    c = CustomizationSystem(p)
    tmp = tempfile.mkdtemp()
    c.config_path = os.path.join(tmp, "custom.json")
    c.customization_data["appearance"]["outfit"] = "wizard"
    c.save_config()
    # 文件完整可读
    with open(c.config_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["appearance"]["outfit"] == "wizard", data
    # 无残留 .tmp
    assert not os.path.exists(c.config_path + ".tmp")
    # 损坏配置（列表）加载不崩、默认保留
    with open(c.config_path, "w", encoding="utf-8") as f:
        f.write('["broken"]')
    c2 = CustomizationSystem(p)
    c2.config_path = c.config_path
    c2.load_config()
    assert c2.customization_data["appearance"]["outfit"] == "default"
    print("[PASS] 原子写无残留 + 损坏配置安全回退")


def test_entertainment_bad_difficulty():
    from entertainment_system import EntertainmentSystem
    p = FakeParent()
    e = EntertainmentSystem(p)
    tmp = tempfile.mkdtemp()
    e.entertainment_data_path = os.path.join(tmp, "ent.json")
    ok, msg = e.end_game("matching_game", difficulty="impossible", score=50, win=False)
    assert ok is True, (ok, msg)
    assert "经验值" in msg, msg
    print("[PASS] 非法难度兜底不崩溃:", msg)


if __name__ == "__main__":
    test_evolution_jump_levels()
    test_all_achievements_have_conditions()
    test_customization_atomic_save_and_bad_load()
    test_entertainment_bad_difficulty()
    print("\n全部通过 ✔")

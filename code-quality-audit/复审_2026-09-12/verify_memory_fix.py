# -*- coding: utf-8 -*-
"""memory_system.py 修复验证（第1区块）—— 所有实例的 memory_file 隔离到临时目录"""
import os
import sys
import tempfile

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet", "modules"))

from memory_system import MemorySystem


class FakeConfig:
    def is_activity_tracking_enabled(self):
        return True


class FakeParent:
    config_manager = FakeConfig()

    class pet_ai:
        @staticmethod
        def trigger_event(*a, **k):
            pass


def _isolated_ms():
    """构造并隔离：绝不读写真实 memory.json"""
    ms = MemorySystem(FakeParent())
    ms.memory_file = os.path.join(tempfile.mkdtemp(), "memory_test.json")
    return ms


def test_update_preserves_important_memory():
    ms = _isolated_ms()
    ms.short_term_memory = [
        {'timestamp': 3, 'type': 'level_up', 'content': '升到2级'},
        {'timestamp': 2, 'type': 'dialogue', 'content': '闲聊一句'},
        {'timestamp': 1, 'type': 'dialogue', 'content': '又闲聊一句'},
    ]
    ms.update()
    # level_up 必须进入长期记忆，且不被整理逻辑删除
    types_in_long = [m.get('type') for m in ms.long_term_memory['interaction_history']]
    assert 'level_up' in types_in_long, f"level_up 丢失: {types_in_long}"
    print("[PASS] update() 后 level_up 重要记忆进入长期记忆")


def test_organize_keeps_single_important():
    ms = _isolated_ms()
    ms.short_term_memory = [
        {'timestamp': 5, 'type': 'achievement_unlocked', 'content': '解锁成就'},
        {'timestamp': 4, 'type': 'dialogue', 'content': 'A'},
    ]
    ms._organize_memories()
    types = [m.get('type') for m in ms.short_term_memory]
    assert 'achievement_unlocked' in types, f"重要记忆被整理误删: {types}"
    print("[PASS] 整理后 achievement_unlocked 保留")


def test_remember_behavior_no_keyerror():
    ms = _isolated_ms()
    ms.remember_user_behavior('typing', 12)
    patterns = ms.get_user_behavior_patterns()
    assert patterns.get('typing', {}).get('count') == 1, patterns
    assert patterns['typing']['total_duration'] == 12, patterns
    print("[PASS] remember_user_behavior 无双重包装，模式统计正确:", patterns)


def test_associated_memories_content_match():
    ms = _isolated_ms()
    ms.short_term_memory = [
        {'timestamp': 1, 'type': 'dialogue', 'content': '我喜欢玩 Deltarune'},
        {'timestamp': 2, 'type': 'dialogue', 'content': 'Deltarune 的音乐很好听'},
        {'timestamp': 3, 'type': 'dialogue', 'content': '今天天气不错'},
    ]
    assoc = ms.get_associated_memories('deltarune')
    assert len(assoc) >= 1, "联想记忆应能按内容匹配"
    print("[PASS] get_associated_memories 按内容联想:", [m['content'] for m in assoc])


def test_load_memory_type_guard():
    # 构造一个 experience 为字符串的损坏记忆文件
    tmp = tempfile.mkdtemp()
    mem_file = os.path.join(tmp, "memory.json")
    with open(mem_file, "w", encoding="utf-8") as f:
        f.write('{"experience": "abc", "level": "3", "long_term_memory": {}}')
    ms = MemorySystem.__new__(MemorySystem)
    ms.parent = FakeParent()
    ms.memory_file = mem_file
    ms.long_term_memory = {
        'user_preferences': {}, 'important_dates': {}, 'interaction_history': [],
        'favorite_topics': {}, 'disliked_topics': {}, 'skill_levels': {},
        'behavior_patterns': {}, 'emotional_responses': {},
        'environmental_preferences': {}, 'relationship_history': []}
    ms.experience = 0
    ms.level = 1
    ms.max_short_term_memory = 100
    ms.short_term_memory = []
    ms.memory_strength = {}
    ms.learning_rate = 0.3
    ms.load_memory()
    assert ms.experience == 0 and ms.level == 1, (ms.experience, ms.level)
    print("[PASS] 损坏数值类型安全回退:", ms.experience, ms.level)


if __name__ == "__main__":
    test_update_preserves_important_memory()
    test_organize_keeps_single_important()
    test_remember_behavior_no_keyerror()
    test_associated_memories_content_match()
    test_load_memory_type_guard()
    print("\n全部通过 ✔")

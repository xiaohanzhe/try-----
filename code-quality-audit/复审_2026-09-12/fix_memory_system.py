# -*- coding: utf-8 -*-
"""memory_system.py 区块修复（审查第1区块）"""
import io

P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\memory_system.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

def patch(old, new):
    global src
    assert old in src, f"NOT FOUND:\n{old[:200]}"
    assert src.count(old) == 1, f"NOT UNIQUE:\n{old[:200]}"
    src = src.replace(old, new, 1)

# 1) update() 顺序：先提取重要记忆，再整理（避免一次性重要记忆被先删）
patch(
"""    def update(self):
        \"\"\"定期更新记忆\"\"\"
        # 整理和优化记忆
        self._organize_memories()
        # 提取重要记忆到长期记忆
        self._extract_important_memories()
        # 学习用户偏好
        self._learn_user_preferences()""",
"""    def update(self):
        \"\"\"定期更新记忆\"\"\"
        # 修复：原实现先 _organize_memories 后 _extract_important_memories，
        # 而 _organize_memories 会删除"出现次数 <2"的记忆类型——level_up /
        # achievement_unlocked / evolution 这类只发生一次的重要记忆每次都被
        # 先删掉，导致长期记忆恒空。顺序调整为：先提取重要记忆，再整理。
        self._extract_important_memories()
        self._organize_memories()
        # 学习用户偏好
        self._learn_user_preferences()""")

# 2) _organize_memories：删除低频率类型时跳过重要类型（双保险）
patch(
"""        # 移除频率过低的记忆类型（原地修改，避免引用切换）
        for mem_type, count in list(memory_types.items()):
            if count < 2:  # 如果某类记忆出现次数少于2次，视为不重要
                self.short_term_memory[:] = [m for m in self.short_term_memory
                                             if not (isinstance(m, dict) and m.get('type') == mem_type)]""",
"""        # 移除频率过低的记忆类型（原地修改，避免引用切换）
        # 修复：与 update() 顺序修复配套的兜底——重要类型即使只出现 1 次也保留，
        # 防止"先提取"遗漏时仍被整理逻辑误删。
        _protected_types = {'user_preferences', 'important_dates', 'completed_task',
                            'level_up', 'evolution', 'achievement_unlocked'}
        for mem_type, count in list(memory_types.items()):
            if count < 2 and mem_type not in _protected_types:
                # 如果某类记忆出现次数少于2次，视为不重要
                self.short_term_memory[:] = [m for m in self.short_term_memory
                                             if not (isinstance(m, dict) and m.get('type') == mem_type)]""")

# 3) _learn_user_preferences：content 可能是 dict（user_behavior），加类型防御
patch(
"""        # 从多种记忆类型中学习
        for memory in self.short_term_memory:
            if memory['type'] in ['user_interaction', 'dialogue', 'search_query', 'file_created', 'file_opened']:
                content = memory['content'].lower()""",
"""        # 从多种记忆类型中学习
        for memory in self.short_term_memory:
            if not isinstance(memory, dict):
                continue
            if memory.get('type') in ['user_interaction', 'dialogue', 'search_query', 'file_created', 'file_opened']:
                raw_content = memory.get('content', '')
                content = raw_content.lower() if isinstance(raw_content, str) else str(raw_content)""")

# 4) remember_user_behavior：去双重包装（原实现 add_memory 再包一层，导致
#    get_user_behavior_patterns 里 memory['content']['behavior_type'] 必然 KeyError）
patch(
"""    def remember_user_behavior(self, behavior_type, duration=0):
        \"\"\"记录用户行为模式\"\"\"
        memory = {
            'timestamp': time.time(),
            'type': 'user_behavior',
            'content': {
                'behavior_type': behavior_type,
                'duration': duration
            }
        }
        self.add_memory('user_behavior', memory, is_short_term=True)""",
"""    def remember_user_behavior(self, behavior_type, duration=0):
        \"\"\"记录用户行为模式\"\"\"
        # 修复：原实现构造好含 content 的记忆后，又整体作为 content 传给
        # add_memory()（add_memory 会再包一层 {timestamp,type,content}），
        # 导致 get_user_behavior_patterns 里 memory['content']['behavior_type']
        # 必然 KeyError。这里直接传 content 本体，由 add_memory 统一包装。
        self.add_memory('user_behavior', {
            'behavior_type': behavior_type,
            'duration': duration
        }, is_short_term=True)""")

# 5) get_user_behavior_patterns：元素类型防御
patch(
"""    def get_user_behavior_patterns(self):
        \"\"\"获取用户行为模式\"\"\"
        behavior_patterns = {}
        for memory in self.short_term_memory + self.long_term_memory['interaction_history']:
            if memory['type'] == 'user_behavior':
                behavior_type = memory['content']['behavior_type']
                duration = memory['content']['duration']
                behavior_patterns[behavior_type] = {
                    'count': behavior_patterns.get(behavior_type, {}).get('count', 0) + 1,
                    'total_duration': behavior_patterns.get(behavior_type, {}).get('total_duration', 0) + duration
                }
        return behavior_patterns""",
"""    def get_user_behavior_patterns(self):
        \"\"\"获取用户行为模式\"\"\"
        behavior_patterns = {}
        for memory in self.short_term_memory + self.long_term_memory['interaction_history']:
            if not isinstance(memory, dict) or memory.get('type') != 'user_behavior':
                continue
            content = memory.get('content')
            if not isinstance(content, dict):
                continue
            behavior_type = content.get('behavior_type', 'unknown')
            duration = content.get('duration', 0)
            try:
                duration = float(duration)
            except (TypeError, ValueError):
                duration = 0
            entry = behavior_patterns.setdefault(behavior_type, {'count': 0, 'total_duration': 0.0})
            entry['count'] += 1
            entry['total_duration'] += duration
        return behavior_patterns""")

# 6) get_associated_memories：id 字段从不写入导致恒返回空 + content 类型防御。
#    改为：先按 id 精确匹配，找不到则按 content 关键词（含 memory_id 文本）匹配。
patch(
"""    def get_associated_memories(self, memory_id, memory_type='short_term'):
        \"\"\"获取与特定记忆相关的联想记忆\"\"\"
        memories = self.short_term_memory if memory_type == 'short_term' else self.long_term_memory['interaction_history']
        
        # 找到目标记忆
        target_memory = None
        for memory in memories:
            if 'id' in memory and memory['id'] == memory_id:
                target_memory = memory
                break
        
        if not target_memory:
            return []
        
        # 提取关键词
        content = target_memory['content'].lower()""",
"""    def get_associated_memories(self, memory_id, memory_type='short_term'):
        \"\"\"获取与特定记忆相关的联想记忆\"\"\"
        memories = self.short_term_memory if memory_type == 'short_term' else self.long_term_memory['interaction_history']
        
        # 修复：add_memory 从不写入 'id' 字段，原实现按 id 匹配恒失败 → 恒返回 []。
        # 改为：先按 id 精确匹配；找不到时退化为按 content 文本匹配（调用方可传
        # 记忆内容片段），保证联想检索在现有数据结构下真正可用。
        target_memory = None
        for memory in memories:
            if not isinstance(memory, dict):
                continue
            if memory.get('id') == memory_id:
                target_memory = memory
                break
        if target_memory is None:
            for memory in memories:
                if not isinstance(memory, dict):
                    continue
                raw = memory.get('content', '')
                text = raw.lower() if isinstance(raw, str) else str(raw)
                if memory_id.lower() in text:
                    target_memory = memory
                    break
        if not target_memory:
            return []
        
        # 提取关键词
        raw_content = target_memory.get('content', '')
        content = raw_content.lower() if isinstance(raw_content, str) else str(raw_content)""")

# 7) load_memory：experience/level 类型校验（手改/损坏 JSON 可能为字符串）
patch(
"""                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.long_term_memory = data.get('long_term_memory', self.long_term_memory)
                    self.experience = data.get('experience', self.experience)
                    self.level = data.get('level', self.level)""",
"""                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        raise ValueError("memory root is not dict")
                    self.long_term_memory = data.get('long_term_memory', self.long_term_memory)
                    exp = data.get('experience', self.experience)
                    lv = data.get('level', self.level)
                    # 修复：手改/损坏的记忆文件可能把数值写成字符串，后续
                    # add_experience/check_level_up 做算术会 TypeError。
                    self.experience = exp if isinstance(exp, (int, float)) else 0
                    self.level = lv if isinstance(lv, (int, float)) and lv >= 1 else 1""")

# 8) get_user_behavior_patterns 之外：get_recent_memory 过滤时 m 可能非 dict
patch(
"""        if memory_type:
            # 过滤特定类型的记忆
            filtered_memory = [m for m in self.short_term_memory if m['type'] == memory_type]
        else:
            filtered_memory = self.short_term_memory""",
"""        if memory_type:
            # 过滤特定类型的记忆
            filtered_memory = [m for m in self.short_term_memory
                               if isinstance(m, dict) and m.get('type') == memory_type]
        else:
            filtered_memory = self.short_term_memory""")

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("memory_system.py patched OK")

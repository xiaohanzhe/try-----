import time
import json
import os
import threading

try:
    from logger_utils import get_logger
    _log = get_logger(__name__)
except ImportError:  # 模块外独立导入时的降级
    import logging
    _log = logging.getLogger(__name__)

try:
    from memory_graph import MemoryGraph, RecallBudget
except ImportError:  # 允许被包外单独导入
    import os as _os
    import sys as _sys
    _sys.path.append(_os.path.dirname(_os.path.abspath(__file__)))
    try:
        from memory_graph import MemoryGraph, RecallBudget
    except ImportError:      # 极端降级：图模块缺失时退化为"只有直接命中"
        MemoryGraph = RecallBudget = None

class MemorySystem:
    # ---------------------------------------------------------------- 参数
    # 拟人记忆的所有可调阈值集中在这里（改行为只改这里，不必翻方法体）。
    SCHEMA = 2
    MAX_FRAGMENTS = 240            # 日常小片段上限：超了先忘最弱的
    MAX_KEYS = 300                 # 关键记忆上限（关键记忆几乎不会被忘，这里是兜底）
    MAX_DIGEST_DAYS = 60           # 保留最近 60 天的"日摘要"
    MAX_ASSOC_KEYS = 400           # 联想图词条上限
    ASSOC_PER_KEY = 12             # 每个词最多保留多少个联想邻居
    FRAGMENT_TEXT_MAX = 160        # 单条片段正文上限（控制文件体积）
    FORGET_STRENGTH_FLOOR = 0.08   # 强度低于此值的片段才允许被忘掉
    DIGEST_AFTER_DAYS = 2          # 超过 2 天的日子压缩成"日摘要"
    KEEP_FULL_DAYS = 1.0           # 最近 1 天内不压缩、不遗忘
    RECALL_REINFORCE = 0.25        # 被想起一次，可回忆度提升的比例
    DEDUP_WINDOW = 2 * 3600.0      # 2 小时内重复出现的话 → 记"又说了一次"而不是新片段
    SAVE_THROTTLE = 2.0            # 自动落盘节流（秒），避免高频磁盘写

    # ---- 第十轮：关联图 / 检索管线 / 反馈与指标的参数 ----
    RECALL_BUDGET = dict(max_hops=3, max_nodes=64, max_edges_per_node=8,
                         max_paths=160, max_candidates=12, max_ms=120.0,
                         max_llm_calls=0, min_path_score=0.02)
    PPR_ITERS = 6                  # PPR 迭代次数（有界子图上很便宜）
    PPR_ALPHA = 0.15               # 重启概率：人也会"拉回最初的话题"
    PPR_MIX = 0.35                 # PPR 分与路径分的融合权重
    FEEDBACK_LR = 0.35             # 反馈学习率（边权）
    CONSOLIDATE_INTERVAL = 1800.0  # 离线巩固最小间隔（秒）
    MIN_PAGE_W = 0.30              # 节点权下限（把 hub 挡在路径外）
    RECALL_LOG_MAX = 8             # 保留最近几次召回的上下文（供反馈回填）
    MAX_VIA = 3                    # 一条回忆最多展示几个"联想到的中间词"
    PATH_GAIN = 1.0                # 路径分→关键词分的放大系数（1.0 表示直接命中仍占优）
    DIRECT_GAIN = 1.0              # 直接命中（cue 词本身）的基准分
    USED_SCORE_BONUS = 1.15        # 被用过一次的关键词，下次略微提权（反馈的即时体现）
    RERANK_OVERLAP = 0.6           # 重排去重：关键词 Jaccard 重叠 ≥ 此值视为"说的是同一件事"
    RERANK_MAX_PER_DAY = 3         # 重排去重：同一天最多留几条（防一次性刷屏；默认不卡死 limit=3）

    def __init__(self, parent):
        self.parent = parent

        # ---- 记忆存储位置（第九轮）----
        # 用户要求："记忆就储存在肖翰哲（E)里面就好（如果没检测到该设备那就临时存储
        # 在桌面上的 memory 文件夹里，等下次检测到这个设备接入后再把东西放进去，
        # 同时把桌面上的多余的记忆清除）"。位置决策与搬运都在 modules/memory_store.py。
        try:
            import memory_store
        except ImportError:  # 允许被包外单独导入
            import os as _os
            import sys as _sys
            _sys.path.append(_os.path.dirname(_os.path.abspath(__file__)))
            import memory_store
        self._store = memory_store
        self.memory_dir, self._on_device, self._device_dir = \
            memory_store.default_memory_dir()
        # 刚插上设备：先把桌面兜底目录里的记忆搬进来（搬完才加载）
        if self._on_device:
            try:
                _mv = memory_store.migrate_from_fallback(self.memory_dir)
                if _mv.get('moved'):
                    _log.info("记忆已从桌面搬入设备目录: %s", _mv)
            except Exception as e:
                _log.warning("记忆搬运失败（继续使用当前目录）: %s", e)
        self.memory_file = memory_store.memory_file_in(self.memory_dir)
        # 旧版位置（本项目目录下的 memory.json）：新位置没有记忆时从这里继承，
        # 保证升级后"不失忆"。旧文件不删（它不在桌面，不会被"清理桌面记忆"波及）。
        # `RALSEI_LEGACY_MEMORY` 可指向别处（自检/迁移他机记忆时用）。
        self._legacy_file = os.environ.get('RALSEI_LEGACY_MEMORY') or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'memory.json')

        # 短期记忆
        self.short_term_memory = []
        self.max_short_term_memory = 100  # 增加短期记忆数量
        self.MAX_LONG_TERM_INTERACTIONS = 500  # 长期记忆交互历史上限
        
        # 扩展长期记忆
        self.long_term_memory = {
            'user_preferences': {},         # 用户偏好
            'important_dates': {},          # 重要日期
            'interaction_history': [],      # 交互历史
            'favorite_topics': {},          # 最喜欢的主题
            'disliked_topics': {},          # 不喜欢的主题
            'skill_levels': {},             # 技能等级
            'behavior_patterns': {},        # 行为模式
            'emotional_responses': {},      # 情绪反应模式
            'environmental_preferences': {}, # 环境偏好
            'relationship_history': []       # 关系历史
        }
        
        # 经验系统
        self.experience = 0
        self.level = 1
        self.experience_threshold = 100  # 升级所需经验值
        
        # 学习系统
        self.learning_rate = 0.3  # 学习率
        self.memory_strength = {}  # 记忆强度

        # ---- 拟人记忆层（第九轮）----
        # 人不是把所有对话逐字存着，而是：① 少量"关键记忆"长期清晰；② 大量"日常
        # 小片段"模糊易忘；③ 忘记时留下"那天大概聊了什么"的印象（日摘要）；
        # ④ 被重新提起时又会清晰起来（复习强化）；⑤ 靠零星片段能重构当时的场景。
        self.fragments = []        # 日常小片段（episodic）
        self.keys = []             # 关键记忆（永不主动遗忘）
        self.digests = {}          # 'YYYY-MM-DD' -> 那天的印象摘要
        # 关联图（第十轮）：分层边 + hub 惩罚 + PPR + 路径打分。
        # `self.assoc` 是**属性**，始终指向图里的边字典，落盘格式即 `{词: {邻词: 边记录}}`。
        self._graph = MemoryGraph() if MemoryGraph is not None else None
        # 召回评估（噪声率/有用率/成功率）与反馈闭环
        self.recall_stats = {'queries': 0, 'items': 0, 'used': 0,
                             'success_queries': 0, 'llm_calls': 0,
                             'by_tier_total': {}, 'by_tier_used': {},
                             'by_hop_total': {}}
        self.recall_metrics = {}
        self._recall_log = {}      # token -> 该次召回的路径/关键词（供反馈回填）
        self._recall_seq = 1
        self._last_consolidate = 0.0
        self._verifier = None      # 可选的 LLM 验证器（默认不接）
        self._lock = threading.RLock()   # 召回反馈可能来自后台线程
        self._next_id = 1
        self._index = {}           # 词 -> [片段下标]（内存索引，避免每次全表扫描）
        self._last_save_ts = 0.0

        # 初始化时加载记忆
        self.load_memory()

    # ------------------------------------------------------- assoc 属性代理
    # 图是唯一真相源；`assoc` 只是它的边字典视图。做成属性可避免"图内部
    # 换了字典对象、外部还指着旧引用"这类同步 bug（第十轮踩过）。
    @property
    def assoc(self):
        return self._graph.edges if self._graph is not None else {}

    @assoc.setter
    def assoc(self, value):
        self._graph = MemoryGraph(value) if MemoryGraph is not None else None

    def add_memory(self, memory_type, content, is_short_term=True):
        """添加记忆，根据隐私设置控制是否存储"""
        # 检查是否启用活动跟踪
        # 修复（B8）：原来只 hasattr 判存在，config_manager 被置 None 时 →
        # None.is_activity_tracking_enabled() → AttributeError（本方法外层无 try）。
        _cm = getattr(self.parent, 'config_manager', None)
        if _cm is not None:
            try:
                if not _cm.is_activity_tracking_enabled():
                    return
            except Exception as e:
                _log.debug("memory_system 隐私开关读取失败（按允许处理）: %s", e)

        memory = {
            'timestamp': time.time(),
            'type': memory_type,
            'content': content
        }
        
        if is_short_term:
            # 添加到短期记忆
            self.short_term_memory.append(memory)
            # 限制短期记忆数量
            if len(self.short_term_memory) > self.max_short_term_memory:
                self.short_term_memory.pop(0)
            # 第九轮：同一条短期记忆也落一份"日常小片段"，喂给拟人记忆层
            # （这样历史调用点不必改，片段层照样能积累）
            try:
                _text = content if isinstance(content, str) else \
                    ' '.join(str(v) for v in content.values()) \
                    if isinstance(content, dict) else str(content)
                self.add_fragment(_text, who='system', kind=memory_type)
            except Exception as e:
                _log.debug("memory_system 片段登记失败（已忽略）: %s", e)
        else:
            # 添加到长期记忆的交互历史
            self.long_term_memory['interaction_history'].append(memory)
            # 限制长期记忆交互历史长度
            if len(self.long_term_memory['interaction_history']) > self.MAX_LONG_TERM_INTERACTIONS:
                self.long_term_memory['interaction_history'] = self.long_term_memory['interaction_history'][-self.MAX_LONG_TERM_INTERACTIONS:]
            # 保存长期记忆
            self.save_memory()
    
    def get_recent_memory(self, memory_type=None, limit=10):
        """获取最近的记忆"""
        if memory_type:
            # 过滤特定类型的记忆
            filtered_memory = [m for m in self.short_term_memory
                               if isinstance(m, dict) and m.get('type') == memory_type]
        else:
            filtered_memory = self.short_term_memory
        
        # 返回最近的limit条记忆
        return filtered_memory[-limit:]
    
    def query_memory(self, query_params, memory_type='short_term'):
        """高级记忆查询功能，支持按多种条件检索记忆"""
        """
        支持的查询参数:
        - memory_type: 'short_term' 或 'long_term'
        - memory_types: 记忆类型列表，如 ['user_interaction', 'dialogue']
        - keywords: 关键词列表，如 ['游戏', '音乐']
        - time_range: 时间范围，如 (start_time, end_time)
        - emotion: 相关情感，如 'happy', 'sad'
        - limit: 返回结果数量限制
        """
        memories = self.short_term_memory if memory_type == 'short_term' else self.long_term_memory['interaction_history']
        
        filtered_memories = []
        
        # 应用过滤条件
        for memory in memories:
            match = True
            if not isinstance(memory, dict):
                continue
            
            # 按记忆类型过滤
            if 'memory_types' in query_params:
                if memory.get('type') not in query_params['memory_types']:
                    match = False
            
            # 按关键词过滤
            if match and 'keywords' in query_params:
                # 修复：content 可能是 dict（非字符串），直接 .lower() 会 AttributeError
                raw_content = memory.get('content', '')
                content = raw_content.lower() if isinstance(raw_content, str) else str(raw_content)
                keyword_match = False
                for keyword in query_params['keywords']:
                    if keyword.lower() in content:
                        keyword_match = True
                        break
                if not keyword_match:
                    match = False
            
            # 按时间范围过滤
            if match and 'time_range' in query_params:
                time_range = query_params.get('time_range')
                if not isinstance(time_range, (list, tuple)) or len(time_range) != 2:
                    _log.debug("query_memory: 非法的 time_range 格式，跳过时间过滤")
                else:
                    start_time, end_time = time_range
                    if not (start_time <= memory['timestamp'] <= end_time):
                        match = False
            
            if match:
                filtered_memories.append(memory)
        
        # 按时间排序，最新的在前
        filtered_memories.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # 应用限制
        if 'limit' in query_params:
            filtered_memories = filtered_memories[:query_params['limit']]
        
        return filtered_memories
    
    def get_associated_memories(self, memory_id, memory_type='short_term'):
        """获取与特定记忆相关的联想记忆"""
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
        content = raw_content.lower() if isinstance(raw_content, str) else str(raw_content)
        keywords = ['游戏', '音乐', '电影', '书籍', '食物', '天气', '工作', '学习', '蛋糕', '甜点', 'deltarune', 'undertale']
        extracted_keywords = []
        for keyword in keywords:
            if keyword in content:
                extracted_keywords.append(keyword)
        
        if not extracted_keywords:
            return []
        
        # 查找相关记忆
        associated_memories = []
        for memory in memories:
            if memory == target_memory:
                continue
            
            _raw_c = memory.get('content', '')
            mem_content = _raw_c.lower() if isinstance(_raw_c, str) else str(_raw_c)
            for keyword in extracted_keywords:
                if keyword in mem_content:
                    associated_memories.append(memory)
                    break
        
        return associated_memories[:5]  # 限制返回5个相关记忆
    
    def learn_user_preference(self, preference_name, preference_value):
        """学习用户偏好"""
        self.long_term_memory['user_preferences'][preference_name] = preference_value
        self.save_memory()
    
    def get_user_preference(self, preference_name, default=None):
        """获取用户偏好"""
        return self.long_term_memory['user_preferences'].get(preference_name, default)
    
    def add_important_date(self, date_name, date_value):
        """添加重要日期"""
        self.long_term_memory['important_dates'][date_name] = date_value
        self.save_memory()
    
    def get_important_date(self, date_name):
        """获取重要日期"""
        return self.long_term_memory['important_dates'].get(date_name, None)
    
    def add_experience(self, amount):
        """增加经验值"""
        self.experience += amount
        # 检查是否升级
        self.check_level_up()
    
    def check_level_up(self):
        """检查是否升级"""
        # 动态升级逻辑：每级所需经验递增
        # 注意：等级上限为 20（与 SocialGrowthSystem.MAX_LEVEL 保持一致，
        # 此处直接使用常量避免循环依赖）。
        MAX_LEVEL = 20
        new_level = 1
        required_experience = 100
        
        while self.experience >= required_experience and new_level < MAX_LEVEL:
            new_level += 1
            # 每级所需经验增加20%
            required_experience += int(required_experience * 0.2)
        
        if new_level > self.level:
            old_level = self.level
            self.level = new_level
            self.experience_threshold = required_experience
            
            # 升级时学习新技能
            self.learn_new_skill()
            
            # 触发升级事件
            self.parent.pet_ai.trigger_event('level_up', {'new_level': self.level, 'old_level': old_level})
            
            # 保存记忆
            self.save_memory()
    
    # 长期记忆的默认结构（成功/失败两条路径共用，避免按键不一致）
    _LT_DEFAULTS = {
        'user_preferences': {},
        'important_dates': {},
        'interaction_history': [],
        'favorite_topics': {},
        'disliked_topics': {},
        'skill_levels': {},
        'behavior_patterns': {},
        'emotional_responses': {},
        'environmental_preferences': {},
        'relationship_history': []
    }

    @staticmethod
    def _read_json_file(path):
        try:
            if not os.path.exists(path):
                return None
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except Exception as e:
            _log.warning("读取记忆文件失败 %s: %s", path, e)
            return None

    def load_memory(self):
        """加载记忆。

        位置优先级：当前工作文件 → 项目内旧版 `ralsei_pet/memory.json`（升级不失忆）。
        任一来源解析失败都退化为"空记忆"，绝不阻塞启动。
        """
        data = self._read_json_file(getattr(self, 'memory_file', ''))
        _src = getattr(self, 'memory_file', '')
        if data is None:
            _legacy = getattr(self, '_legacy_file', None)
            data = self._read_json_file(_legacy) if _legacy else None
            if data is not None:
                _src = _legacy
                _log.info("新位置无记忆，已从旧版 memory.json 继承: %s", _legacy)

        if data is None:
            # 首次运行/新设备上还没有记忆文件 —— 这是正常情况，不是错误。
            _log.debug("尚无记忆文件，按空记忆启动：%s", _src)
            self._apply_defaults()
            self._build_index()
            return

        try:
            self._apply_loaded(data)
            _log.debug("成功加载记忆: %s", _src)
        except Exception as e:
            _log.warning("加载记忆失败: %s", e)
            self._apply_defaults()
        self._build_index()

    def _apply_defaults(self):
        """空记忆/加载失败时的兜底结构。

        修复：损坏/加载失败时兜底结构必须与成功路径一致（全键补全），
        否则后续 update()/learn 系列直接索引 skill_levels 等键会 KeyError。
        """
        self.long_term_memory = dict(self._LT_DEFAULTS)
        self.experience = 0
        self.level = 1
        self.fragments = list(getattr(self, 'fragments', []) or [])
        self.keys = list(getattr(self, 'keys', []) or [])
        self.digests = dict(getattr(self, 'digests', {}) or {})
        self.assoc = dict(getattr(self, 'assoc', {}) or {})
        self._next_id = int(getattr(self, '_next_id', 1) or 1)

    def _apply_loaded(self, data):
        """把磁盘数据灌进内存（逐字段校验，坏的字段当没有）。"""
        self.long_term_memory = data.get('long_term_memory', {})
        exp = data.get('experience', 0)
        lv = data.get('level', 1)
        # 修复：手改/损坏的记忆文件可能把数值写成字符串，后续
        # add_experience/check_level_up 做算术会 TypeError。
        self.experience = exp if isinstance(exp, (int, float)) else 0
        self.level = lv if isinstance(lv, (int, float)) and lv >= 1 else 1
        _lr = data.get('learning_rate', self.learning_rate)
        self.learning_rate = _lr if isinstance(_lr, (int, float)) else 0.3
        _ms = data.get('memory_strength', {})
        self.memory_strength = _ms if isinstance(_ms, dict) else {}

        # 修复：旧版本记忆文件可能缺 skill_levels/behavior_patterns 等键，
        # 后续 get_knowledge_summary / integrate_knowledge 直接索引会 KeyError。
        if not isinstance(self.long_term_memory, dict):
            self.long_term_memory = {}
        _merged = dict(self._LT_DEFAULTS)
        _merged.update(self.long_term_memory)
        self.long_term_memory = _merged

        # ---- 拟人记忆层 ----
        self.fragments = [f for f in (data.get('fragments') or [])
                          if isinstance(f, dict) and 'text' in f]
        self.keys = [k for k in (data.get('keys') or [])
                     if isinstance(k, dict) and 'text' in k]
        _dg = data.get('digests') or {}
        self.digests = {str(k): str(v) for k, v in _dg.items()} if isinstance(_dg, dict) else {}
        _as = data.get('assoc') or {}
        self.assoc = {str(k): dict(v) for k, v in _as.items()
                      if isinstance(v, dict)} if isinstance(_as, dict) else {}
        # 第十轮：恢复图的检索参数与召回指标（属性 setter 已重建了一个新图，
        # 所以这里必须在 setter 之后再写 weak_penalty，否则会被新图清零）
        _g = data.get('graph') or {}
        if self._graph is not None and isinstance(_g, dict):
            _wp = _g.get('weak_penalty')
            if isinstance(_wp, (int, float)):
                self._graph.weak_penalty = max(0.0, min(0.8, float(_wp)))
        _rs = data.get('recall_stats')
        if isinstance(_rs, dict):
            for _k in ('queries', 'items', 'used', 'success_queries', 'llm_calls'):
                _v = _rs.get(_k)
                if isinstance(_v, (int, float)):
                    self.recall_stats[_k] = int(_v)
            for _k in ('by_tier_total', 'by_tier_used', 'by_hop_total'):
                _v = _rs.get(_k)
                if isinstance(_v, dict):
                    self.recall_stats[_k] = {str(k): int(n) for k, n in _v.items()
                                             if isinstance(n, (int, float))}
        _nid = data.get('next_id', 1)
        self._next_id = int(_nid) if isinstance(_nid, (int, float)) and _nid >= 1 else 1
        # next_id 兜底：旧文件可能没记，取现有最大 id + 1
        try:
            _mx = max([int(f.get('id') or 0) for f in self.fragments] +
                      [int(k.get('id') or 0) for k in self.keys] + [0])
            if _mx >= self._next_id:
                self._next_id = _mx + 1
        except Exception:
            pass
    
    def save_memory(self):
        """保存记忆"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            
            data = {
                'schema': self.SCHEMA,
                'saved_at': time.time(),
                'long_term_memory': self.long_term_memory,
                'experience': self.experience,
                'level': self.level,
                # 修复（B4）：learning_rate / memory_strength 原先不落盘，重启即丢
                'learning_rate': self.learning_rate,
                'memory_strength': self.memory_strength,
                # 拟人记忆层（第九轮）
                'fragments': self.fragments,
                'keys': self.keys,
                'digests': self.digests,
                'assoc': self.assoc,
                'next_id': self._next_id,
                # 第十轮：图的检索参数（弱边压制量是"学"出来的，重启不能丢）
                # 与召回质量指标（有用率/成功率——不落盘就没法跨会话评估）
                'graph': {'weak_penalty': round(float(
                    getattr(self._graph, 'weak_penalty', 0.0) or 0.0), 4)},
                'recall_stats': self.recall_stats,
                # 只记"存在设备上还是桌面兜底"，不落绝对路径（隐私/可移植）
                'storage_kind': 'device' if self._on_device else 'desktop',
            }
            
            # 修复：原实现直接 open(w) 覆写，写一半崩溃/断电会损坏整个记忆文件
            # （下次加载失败 → 全部记忆丢失）。改为临时文件 + 原子替换。
            _tmp = self.memory_file + ".tmp"
            with open(_tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(_tmp, self.memory_file)
            self._last_save_ts = time.time()
        except Exception as e:
            _log.warning("保存记忆失败: %s", e)
            try:
                if os.path.exists(self.memory_file + ".tmp"):
                    os.remove(self.memory_file + ".tmp")
            except Exception as e:
                _log.debug("memory_system 防御性异常（已忽略）: %s", e)

    def autosave(self, force=False):
        """节流落盘：高频的片段登记不必每次都写盘（性能），但要保证不丢。

        距上次落盘不足 `SAVE_THROTTLE` 秒时跳过；`force=True` 强制写。
        """
        try:
            if force or (time.time() - float(self._last_save_ts or 0.0)) >= self.SAVE_THROTTLE:
                self.save_memory()
                return True
        except Exception as e:
            _log.debug("memory_system 自动保存失败（已忽略）: %s", e)
        return False

    def reset_all(self):
        """清空全部记忆（隐私设置"退出时清理数据"用），含新记忆层与留档副本。"""
        self.short_term_memory = []
        self.fragments = []
        self.keys = []
        self.digests = {}
        self.assoc = {}
        self._index = {}
        self._next_id = 1
        # 第十轮：召回记账与日志也一并清空（隐私清理要彻底，不留"读过什么"的痕迹）
        self.recall_stats = {'queries': 0, 'items': 0, 'used': 0,
                             'success_queries': 0, 'llm_calls': 0,
                             'by_tier_total': {}, 'by_tier_used': {},
                             'by_hop_total': {}}
        self.recall_metrics = {}
        self._recall_log = {}
        self._last_consolidate = 0.0
        if self._graph is not None:
            self._graph.weak_penalty = 0.0
        self.experience = 0
        self.level = 1
        self.memory_strength = {}
        for f in (self.memory_file,
                  self.memory_file + '.tmp',
                  os.path.join(self.memory_dir, getattr(self._store, 'ROLLBACK_FILENAME',
                                                        'memory.old.json'))):
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception as e:
                _log.warning("清理记忆文件失败 %s: %s", f, e)
    
    def get_experience(self):
        """获取当前经验值"""
        return self.experience
    
    def get_level(self):
        """获取当前等级"""
        return self.level
    
    def update(self):
        """定期更新记忆"""
        # 修复：原实现先 _organize_memories 后 _extract_important_memories，
        # 而 _organize_memories 会删除"出现次数 <2"的记忆类型——level_up /
        # achievement_unlocked / evolution 这类只发生一次的重要记忆每次都被
        # 先删掉，导致长期记忆恒空。顺序调整为：先提取重要记忆，再整理。
        self._extract_important_memories()
        self._organize_memories()
        # 学习用户偏好
        self._learn_user_preferences()
        # 遗忘与压缩（第九轮）：像人一样，不重要的细节会淡忘、留下来的变成"印象"。
        # 关键记忆与最近 24 小时的内容受保护，不会被忘掉（"确保不失忆"）。
        try:
            self.forget_cycle()
        except Exception as e:
            _log.debug("memory_system 遗忘周期异常（已忽略）: %s", e)
        # 设备插拔：上次只能存桌面兜底，这次设备回来了 → 把记忆搬进设备并清掉桌面副本
        try:
            self.maybe_relocate_storage()
        except Exception as e:
            _log.debug("memory_system 存储迁移检查异常（已忽略）: %s", e)
        # 离线巩固（第十轮）：图会随对话越连越乱，需要定期"睡觉时整理"——
        # 边老化、按反馈升降级、剪枝、从日摘要跨天补边、并按有用率微调弱边权重。
        # 按 CONSOLIDATE_INTERVAL 节流（默认半小时），不在每次 update 都跑。
        try:
            if (time.time() - float(getattr(self, '_last_consolidate', 0.0) or 0.0)
                    ) >= self.CONSOLIDATE_INTERVAL:
                self.consolidate()
        except Exception as e:
            _log.debug("memory_system 离线巩固异常（已忽略）: %s", e)
    
    def _organize_memories(self):
        """整理记忆，去除冗余和不重要的记忆，优化记忆组织"""
        # 统计记忆类型分布
        memory_types = {}
        for memory in self.short_term_memory:
            if not isinstance(memory, dict) or 'type' not in memory:
                continue
            mem_type = memory['type']
            memory_types[mem_type] = memory_types.get(mem_type, 0) + 1

        # 移除频率过低的记忆类型（原地修改，避免引用切换）
        # 修复：与 update() 顺序修复配套的兜底——重要类型即使只出现 1 次也保留，
        # 防止"先提取"遗漏时仍被整理逻辑误删。
        _protected_types = {'user_preferences', 'important_dates', 'completed_task',
                            'level_up', 'evolution', 'achievement_unlocked'}
        for mem_type, count in list(memory_types.items()):
            if count < 2 and mem_type not in _protected_types:
                # 如果某类记忆出现次数少于2次，视为不重要
                self.short_term_memory[:] = [m for m in self.short_term_memory
                                             if not (isinstance(m, dict) and m.get('type') == mem_type)]
        
        # 按时间排序，保留最新的记忆
        self.short_term_memory.sort(key=lambda x: x.get('timestamp', 0) if isinstance(x, dict) else 0, reverse=True)
        
        # 限制短期记忆数量，确保性能
        if len(self.short_term_memory) > self.max_short_term_memory:
            self.short_term_memory = self.short_term_memory[:self.max_short_term_memory]
    
    def _extract_important_memories(self):
        """将重要的短期记忆提取到长期记忆"""
        important_types = ['user_preferences', 'important_dates', 'completed_task', 'level_up', 'evolution', 'achievement_unlocked']
        
        for memory in self.short_term_memory:
            if not isinstance(memory, dict) or 'type' not in memory:
                continue
            if memory['type'] in important_types and memory not in self.long_term_memory['interaction_history']:
                self.long_term_memory['interaction_history'].append(memory)
                # 限制长期记忆交互历史长度
                if len(self.long_term_memory['interaction_history']) > self.MAX_LONG_TERM_INTERACTIONS:
                    self.long_term_memory['interaction_history'] = self.long_term_memory['interaction_history'][-self.MAX_LONG_TERM_INTERACTIONS:]
                # 保存长期记忆
                self.save_memory()
    
    def _learn_user_preferences(self):
        """从交互历史中学习用户偏好，增强学习能力"""
        # 统计用户提到的主题频率
        topic_counts = {}
        
        # 扩展关键词列表
        keywords = ['游戏', '音乐', '电影', '书籍', '食物', '天气', '工作', '学习', '蛋糕', '甜点', 'deltarune', 'undertale', 
                   '动漫', '编程', '旅行', '运动', '宠物', '咖啡', '茶', '阅读', '绘画', '摄影', '编程', '科学', '历史', 
                   '数学', '英语', '日语', '韩语', '烹饪', '健身', '音乐', '舞蹈', '书法', '手工', '游戏开发', '设计', 
                   '动画制作', '视频编辑', '音频制作', '3D建模', '写作', '诗歌', '小说', '散文', '漫画', '插画', '游戏设计']
        
        # 从多种记忆类型中学习
        for memory in self.short_term_memory:
            if not isinstance(memory, dict):
                continue
            if memory.get('type') in ['user_interaction', 'dialogue', 'search_query', 'file_created', 'file_opened']:
                raw_content = memory.get('content', '')
                content = raw_content.lower() if isinstance(raw_content, str) else str(raw_content)
                for keyword in keywords:
                    if keyword in content:
                        topic_counts[keyword] = topic_counts.get(keyword, 0) + 1
        
        # 将高频主题保存为用户偏好
        for topic, count in topic_counts.items():
            if count >= 2:  # 降低阈值，更容易学习新偏好
                # 考虑记忆强度，更频繁提到的主题权重更高
                current_value = self.long_term_memory['user_preferences'].get(f'interest_{topic}', 0)
                new_value = current_value + (count * self.learning_rate)
                self.learn_user_preference(f'interest_{topic}', new_value)
    
    def get_user_preferences_summary(self):
        """获取用户偏好摘要"""
        preferences = []
        for pref_name, pref_value in self.long_term_memory['user_preferences'].items():
            if pref_name.startswith('interest_'):
                topic = pref_name.replace('interest_', '')
                preferences.append((topic, pref_value))
        
        # 按偏好程度排序
        preferences.sort(key=lambda x: x[1], reverse=True)
        return preferences
    
    def remember_user_behavior(self, behavior_type, duration=0):
        """记录用户行为模式"""
        # 修复：原实现构造好含 content 的记忆后，又整体作为 content 传给
        # add_memory()（add_memory 会再包一层 {timestamp,type,content}），
        # 导致 get_user_behavior_patterns 里 memory['content']['behavior_type']
        # 必然 KeyError。这里直接传 content 本体，由 add_memory 统一包装。
        self.add_memory('user_behavior', {
            'behavior_type': behavior_type,
            'duration': duration
        }, is_short_term=True)
    
    def get_user_behavior_patterns(self):
        """获取用户行为模式"""
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
        return behavior_patterns
    
    def learn_new_skill(self):
        """学习新技能"""
        # 可用技能列表，根据等级解锁
        available_skills = {
            2: ['small_talk', 'weather_talk', 'simple_games'],
            3: ['story_telling', 'music_recommendation', 'movie_recommendation'],
            4: ['work_assistance', 'creative_writing', 'problem_solving'],
            5: ['emotional_support', 'advanced_games', 'technical_assistance'],
            6: ['leadership', 'teamwork', 'mentoring'],
            7: ['innovation', 'strategic_thinking', 'resource_management'],
            8: ['telepathy', 'time_management', 'multitasking'],
            9: ['wisdom', 'inspiration', 'enlightenment'],
            10: ['omnipotence', 'omniscience', 'omnipresence']
        }
        
        # 获取当前等级可学习的技能
        level_skills = available_skills.get(self.level, [])
        
        # 过滤掉已学习的技能
        learned_skills = list(self.long_term_memory['skill_levels'].keys())
        new_skills = [skill for skill in level_skills if skill not in learned_skills]
        
        if new_skills:
            # 随机选择一个新技能学习
            import random
            new_skill = random.choice(new_skills)
            self.long_term_memory['skill_levels'][new_skill] = 1
            
            # 保存记忆
            self.save_memory()
            
            _log.debug("Ralsei学习了新技能: %s！", new_skill)
    
    def improve_skill(self, skill_name, amount=1):
        """提升技能等级"""
        if skill_name in self.long_term_memory['skill_levels']:
            self.long_term_memory['skill_levels'][skill_name] += amount
        else:
            self.long_term_memory['skill_levels'][skill_name] = 1
        
        # 保存记忆
        self.save_memory()
    
    def get_skill_level(self, skill_name):
        """获取技能等级"""
        return self.long_term_memory['skill_levels'].get(skill_name, 0)
    
    def has_skill(self, skill_name):
        """检查是否拥有某个技能"""
        return skill_name in self.long_term_memory['skill_levels']
    
    def update_memory_strength(self, memory_type, strength_change):
        """更新记忆强度"""
        current_strength = self.memory_strength.get(memory_type, 50)
        new_strength = max(0, min(100, current_strength + strength_change))
        self.memory_strength[memory_type] = new_strength
    
    def get_memory_strength(self, memory_type):
        """获取记忆强度"""
        return self.memory_strength.get(memory_type, 50)
    
    def learn_from_experience(self, experience_type, outcome):
        """从经验中学习，增强学习能力"""
        # 根据经验结果调整学习
        if outcome == 'success':
            # 成功经验，增强相关技能和记忆强度
            self.update_memory_strength(experience_type, 10)
            if experience_type in self.long_term_memory['skill_levels']:
                self.improve_skill(experience_type, 2)
            # 成功时适当降低学习率
            self.learning_rate = max(0.1, self.learning_rate - 0.02)
            # 记录成功经验
            self.add_memory('success_experience', f'{experience_type}: {outcome}', is_short_term=True)
        elif outcome == 'failure':
            # 失败经验，增强学习率和记忆强度
            self.update_memory_strength(experience_type, -5)
            self.learning_rate = min(1.0, self.learning_rate + 0.05)
            # 记录失败经验，便于后续分析
            self.add_memory('failure_experience', f'{experience_type}: {outcome}', is_short_term=True)
        elif outcome == 'neutral':
            # 中性经验，轻微增强记忆强度
            self.update_memory_strength(experience_type, 2)
        
        # 保存记忆
        self.save_memory()
    
    def integrate_knowledge(self):
        """整合知识，从记忆中提取规律和模式"""
        """
        知识整合功能，从记忆中提取有用的规律和模式:
        - 分析用户行为模式
        - 识别情感触发因素
        - 提取有用的知识和经验
        """
        # 分析用户行为模式
        behavior_patterns = {}
        for memory in self.long_term_memory.get('interaction_history', []):
            if not isinstance(memory, dict):
                continue
            if memory.get('type') == 'user_interaction':
                # 修复：content 可能是 dict，直接 .lower() 会 AttributeError
                raw_content = memory.get('content', '')
                content = raw_content.lower() if isinstance(raw_content, str) else str(raw_content)
                # 统计行为模式
                if '早上好' in content or '早安' in content:
                    behavior_patterns['morning_greeting'] = behavior_patterns.get('morning_greeting', 0) + 1
                if '晚上好' in content or '晚安' in content:
                    behavior_patterns['evening_greeting'] = behavior_patterns.get('evening_greeting', 0) + 1
                if '谢谢' in content or '感谢' in content:
                    behavior_patterns['gratitude'] = behavior_patterns.get('gratitude', 0) + 1
        
        # 更新行为模式
        self.long_term_memory['behavior_patterns'] = behavior_patterns
        
        # 分析情感触发因素
        emotional_triggers = {}
        for memory in self.long_term_memory.get('interaction_history', []):
            if isinstance(memory, dict) and 'emotion' in memory:
                emotion = memory['emotion']
                if emotion not in emotional_triggers:
                    emotional_triggers[emotion] = []
                emotional_triggers[emotion].append(memory.get('content', ''))
        
        # 更新情感反应模式
        self.long_term_memory['emotional_responses'] = emotional_triggers
        
        # 保存整合后的知识
        self.save_memory()
    
    def get_knowledge_summary(self):
        """获取知识摘要，整合记忆中的关键信息"""
        summary = {
            'user_preferences': self.get_user_preferences_summary(),
            'behavior_patterns': self.long_term_memory.get('behavior_patterns', {}),
            'skill_levels': self.long_term_memory.get('skill_levels', {}),
            'experience': self.experience,
            'level': self.level
        }
        return summary

    # ==================================================================
    # 拟人记忆层（第九轮）
    # ==================================================================
    # 用户要求："让他的记忆系统就像是人一样，有选择性的记住关键，和日常的小片段，
    # 就像是人一样，在需要的时候脑子里会根据一些零星的记忆片段自动重构当时的场景，
    # 还有，遗忘机制也很重要，要不然内存爆满了就……确保不失忆的前提下将性能拉高。"
    #
    # 对应人的四种能力：
    #   ① 选择性记忆 —— add_fragment（大量日常小片段） + remember_key（少量关键记忆）
    #   ② 重构场景   —— recall / recall_text / reconstruct_scene（由零星片段拼出画面）
    #   ③ 遗忘       —— forget_cycle（强度衰减 → 日摘要压缩 → 上限裁剪；关键记忆免疫）
    #   ④ 复习强化   —— recall 命中即增强（人想起来的事会更牢固，这是"不失忆"的关键）
    #
    # 性能：召回走内存倒排索引（词 → 片段下标），不扫全表；落盘走节流 + 原子替换。
    # ------------------------------------------------------------------

    PROTECTED_KINDS = ('level_up', 'evolution', 'achievement_unlocked',
                       'completed_task', 'important_dates', 'user_preferences')

    @staticmethod
    def _day_of(ts):
        try:
            return time.strftime('%Y-%m-%d', time.localtime(float(ts)))
        except Exception:
            return ''

    @staticmethod
    def _tod_of(ts):
        """一天中的时段——回忆里人是说"那天傍晚…"而不是"17:42"。"""
        try:
            h = time.localtime(float(ts)).tm_hour
        except Exception:
            return ''
        if 5 <= h < 8:
            return '清晨'
        if 8 <= h < 11:
            return '上午'
        if 11 <= h < 13:
            return '中午'
        if 13 <= h < 17:
            return '下午'
        if 17 <= h < 19:
            return '傍晚'
        if 19 <= h < 23:
            return '晚上'
        return '深夜'

    @staticmethod
    def _freshness(ts, now=None):
        """把时间差说成人话：刚刚 / 今天 / 昨天 / 3 天前 / 上个月。"""
        try:
            dt = max(0.0, float(now if now is not None else time.time()) - float(ts))
        except Exception:
            return ''
        if dt < 300:
            return '刚刚'
        if dt < 86400:
            return '今天'
        days = int(dt // 86400)
        if days == 1:
            return '昨天'
        if days < 30:
            return '%d 天前' % days
        months = days // 30
        if months < 12:
            return '%d 个月前' % months
        return '很久以前'

    @staticmethod
    def _kw_of(text, limit=6):
        """抽话题关键词。复用第九轮的话题锚词法（同一套词法 -> 话题与记忆能对上）。"""
        _cf = None
        try:
            import conversation_focus as _cf
        except ImportError:
            try:
                import os as _os
                import sys as _sys
                _sys.path.append(_os.path.dirname(_os.path.abspath(__file__)))
                import conversation_focus as _cf
            except ImportError:
                _cf = None
        if _cf is not None:
            try:
                return list(_cf.extract_keywords(text))[:limit]
            except Exception:
                pass
        # 退化实现：按非文字符切开，取长度 ≥2 的片段
        try:
            import re as _re
            parts = _re.split(r'[^\w\u4e00-\u9fff]+', str(text))
            out = []
            for p in parts:
                if len(p) >= 2 and p not in out:
                    out.append(p)
            return out[:limit]
        except Exception:
            return []

    @staticmethod
    def _salience(kind, who, text, kw, emotion=None):
        """显著性 0~1：决定"这条值得记多久"。

        人的规律：主人说的话比自己随口一句记得牢；带情绪的经历最难忘；
        信息量大的（关键词多、说得长）比"嗯嗯"值得记。
        """
        base = {'dialogue': 0.45, 'observation': 0.35, 'user_behavior': 0.5,
                'success_experience': 0.7, 'failure_experience': 0.65}.get(str(kind), 0.4)
        if who == 'user':
            base += 0.15
        elif who == 'ralsei':
            base -= 0.10
        if emotion in ('happy', 'love', 'excited', 'surprised'):
            base += 0.12
        elif emotion in ('sad', 'angry', 'fear', 'anxious', 'tired'):
            base += 0.18
        base += min(0.15, 0.03 * len(kw or []))
        n = len(str(text or ''))
        if n <= 4:
            base -= 0.12
        elif n >= 60:
            base += 0.05
        return round(max(0.05, min(1.0, base)), 4)

    # ------------------------------------------------------------ 索引
    def _build_index(self):
        self._index = {}
        for i, f in enumerate(self.fragments):
            self._index_add(f, i)
        # hub 惩罚的依据：文档频率表由倒排索引直接得到（词出现在多少条片段里）
        if self._graph is not None:
            self._graph.refresh_df(self._index, len(self.fragments))

    def _index_add(self, frag, idx):
        for k in (frag.get('kw') or []):
            self._index.setdefault(k, []).append(idx)

    # ------------------------------------------------------------ 写入
    def add_fragment(self, text, who='user', kind='dialogue',
                     emotion=None, importance=None, now=None):
        """记一条"日常小片段"（人记得最多的就是这种东西）。返回片段或 None。

        · 太短（<2 字）不算片段；过长会截断（控制文件体积）。
        · 2 小时内重复出现同样的话 → 只当作"又听了一遍"（rehearsals+1 并强化），
          不新增片段 —— 否则他说的口头禅会把记忆撑爆。
        """
        try:
            s = str(text or '').strip()
            if len(s) < 2:
                return None
            if len(s) > self.FRAGMENT_TEXT_MAX:
                s = s[:self.FRAGMENT_TEXT_MAX - 1] + '…'
            now = float(now if now is not None else time.time())
            kw = self._kw_of(s)
            sal = (float(importance) if isinstance(importance, (int, float))
                   else self._salience(kind, who, s, kw, emotion))
            sal = max(0.05, min(1.0, sal))
            norm = ''.join(ch for ch in s if not ch.isspace())

            for f in reversed(self.fragments[-40:]):
                try:
                    if now - float(f.get('t', 0)) > self.DEDUP_WINDOW:
                        break
                except Exception:
                    continue
                if f.get('norm') == norm:
                    self._reinforce(f, now, 1.0)
                    self.add_assoc(kw)
                    self.autosave()
                    return f

            frag = {
                'id': self._next_id, 't': now, 'day': self._day_of(now),
                'who': who, 'kind': kind, 'text': s, 'kw': kw, 'emotion': emotion,
                'salience': sal,
                # 初始可回忆度：越显著越清晰
                'strength': round(0.35 + 0.55 * sal, 4),
                'rehearsals': 1, 'hits': 0, 'seen': now, 'norm': norm,
            }
            self._next_id += 1
            self.fragments.append(frag)
            self._index_add(frag, len(self.fragments) - 1)
            self.add_assoc(kw)
            if len(self.fragments) > self.MAX_FRAGMENTS:
                self.forget_cycle(now=now)
            self.autosave()
            return frag
        except Exception as e:
            _log.debug("memory_system 片段写入失败（已忽略）: %s", e)
            return None

    def remember_key(self, kind, text, importance=0.85, **meta):
        """记一条"关键记忆"（升级/成就/重要日子/主人说的重要事）。

        关键记忆**不参与遗忘**——这是"确保不失忆"的底线。
        """
        try:
            s = str(text or '').strip()
            if not s:
                return None
            now = time.time()
            sig = (str(kind), s[:48])
            for k in self.keys:
                if (str(k.get('kind')), str(k.get('text'))[:48]) == sig:
                    k['count'] = int(k.get('count', 1)) + 1
                    k['last_at'] = now
                    self.autosave()
                    return k
            rec = {
                'id': self._next_id, 't': now, 'kind': str(kind),
                'text': s[:self.FRAGMENT_TEXT_MAX], 'count': 1, 'last_at': now,
                'salience': round(max(0.5, min(1.0, float(importance or 0.85))), 4),
                'meta': dict(meta) if meta else {},
            }
            self._next_id += 1
            self.keys.append(rec)
            if len(self.keys) > self.MAX_KEYS:
                self.keys.sort(key=lambda k: (float(k.get('salience', 0.5)),
                                              float(k.get('last_at', 0))), reverse=True)
                self.keys = self.keys[:self.MAX_KEYS]
            self.autosave()
            return rec
        except Exception as e:
            _log.debug("memory_system 关键记忆写入失败（已忽略）: %s", e)
            return None

    def add_assoc(self, kw, now=None):
        """更新关联图：同一句话里出现过的词互为邻居（人脑靠共现建立联想）。

        第十轮起交给 `memory_graph.MemoryGraph`：边带**分层/反馈/时间**，
        并受"每点邻居上限 + 节点数上限"约束。
        """
        try:
            if self._graph is None:
                return
            self._graph.add_cooccurrence(kw, now=now)
        except Exception as e:
            _log.debug("memory_system 联想图更新失败（已忽略）: %s", e)

    def _reinforce(self, frag, now, factor=1.0):
        """复习强化：可回忆度向 1 靠拢（想起来一次就更牢固）。"""
        try:
            f0 = max(0.0, min(1.0, float(frag.get('strength', 0.4))))
            f1 = f0 + self.RECALL_REINFORCE * factor * (1.0 - f0) + 0.05 * factor
            frag['strength'] = round(max(0.0, min(1.0, f1)), 4)
            frag['rehearsals'] = int(frag.get('rehearsals', 0)) + 1
            frag['seen'] = float(now)
        except Exception as e:
            _log.debug("memory_system 强化失败（已忽略）: %s", e)

    # ------------------------------------------------------------ 召回
    def recall(self, cue, limit=3, reinforce=True, now=None):
        """由一句话（cue）想起若干零星的记忆片段。返回按相关度排序的列表。

        第十轮把它升级成**受控多跳检索管线**（用户提的设计），每一环都可独立降级：
          ② 受控扩散：`memory_graph` 里做分层边 + hub 惩罚 + 每跳 tier 下限
             → **路径打分**（不是只看相似度）+ PPR；
          ③ 融合：直接命中 / 多跳联想 / 关键记忆 / 日摘要；
          ④ 过滤：路径早剪（图内）+ 关键词分下限 + **重排去重**（MMR 式）；
          ⑤ 预算：`RecallBudget` 卡死跳数/节点/路径/耗时，任何一环都不会失控。
        被想起来的片段会强化（复习效应），并把"这次是怎么想到的"记进 `_recall_log`
        —— 那是 `recall_feedback()`（反馈学习边权）的另一半。
        """
        out = []
        token = None
        try:
            now = float(now if now is not None else time.time())
            cue_kw = self._kw_of(cue, limit=8)
            if not cue_kw:
                # 没有线索：像人发呆一样，给出最近的印象
                for f in reversed(self.fragments[-limit:]):
                    out.append(self._digest_item(f, 0.1, now))
                return out

            budget = RecallBudget(**self.RECALL_BUDGET) if RecallBudget else None
            graph = self._graph
            _floor = float(getattr(budget, 'min_path_score', 0.02) or 0.02)
            # 图的入口要 `{词: 权重}`；这里显式建字典（曾经传 list 被静默吞成"多跳全废"）
            seed_map = {k: float(self.DIRECT_GAIN) for k in cue_kw}

            # ---- ② 受控多跳：路径分 + PPR（都只在有界子图上跑）----
            kw_direct = dict(seed_map)
            kw_assoc, kw_meta = {}, {}
            all_paths = []
            if graph is not None and budget is not None and self.assoc:
                try:
                    budget.start()
                    all_paths = graph.paths(seed_map, budget,
                                            min_node_w=self.MIN_PAGE_W)
                except Exception as e:
                    _log.debug("memory_system 路径枚举降级: %s", e)
                # hub 惩罚落点：到处都出现的词（"游戏/那个"）不配当联想的落点
                for p in all_paths:
                    nodes = p.get('nodes') or []
                    if len(nodes) < 2:
                        continue
                    tgt = nodes[-1]
                    try:
                        if graph.node_weight(tgt) < self.MIN_PAGE_W:
                            continue
                    except Exception:
                        pass
                    s = float(p.get('score') or 0.0) * self.PATH_GAIN
                    if s > kw_assoc.get(tgt, 0.0):
                        kw_assoc[tgt] = s
                        kw_meta[tgt] = {'hop': int(p.get('hops') or 1),
                                        'tier': p.get('tier'),
                                        'via': nodes[1:-1][-self.MAX_VIA:]}
                try:
                    ppr = graph.ppr(seed_map, budget, iters=self.PPR_ITERS,
                                    alpha=self.PPR_ALPHA)
                except Exception as e:
                    ppr = {}
                    _log.debug("memory_system PPR 降级: %s", e)
                if ppr:
                    pmax = max(ppr.values()) or 1.0
                    # PPR 只做**加权**，不做**放行**：一个词能不能进候选，永远取决于
                    # 它有没有一条过得了路径分门槛的路径（"路径过滤保可信"）。
                    # 曾经这里用加法把 PPR 分直接加进关键词分 —— 结果被路径过滤剪掉的
                    # 词，又被 hub 通过 PPR 硬塞了回来（自检 R2c 抓到：中间是 hub 时，
                    # 两跳路径分只有 0.0125 < 0.02 本该被剪，却因 PPR 约 0.05 复活）。
                    for _d in (kw_direct, kw_assoc):
                        for _k in list(_d.keys()):
                            _d[_k] = _d[_k] * (1.0 + self.PPR_MIX *
                                               (float(ppr.get(_k) or 0.0) / pmax))
            # ④ 关键词级过滤：联想强度低于路径阈值的直接不要（防"顺带一提"混进来）
            for k in [k for k, v in kw_assoc.items() if v < _floor]:
                kw_assoc.pop(k, None)
                kw_meta.pop(k, None)

            # ---- ③ 融合成片段分 ----
            frag_src = {}   # idx -> 最强来源（直接命中优先于联想）
            for k, w in kw_direct.items():
                for idx in self._index.get(k, ()):
                    if 0 <= idx < len(self.fragments):
                        cur = frag_src.get(idx)
                        if cur is None or (1, w) > (cur['direct'], cur['w']):
                            frag_src[idx] = {'w': w, 'kw': k, 'direct': 1,
                                             'meta': kw_meta.get(k, {})}
            for k, w in kw_assoc.items():
                for idx in self._index.get(k, ()):
                    if 0 <= idx < len(self.fragments):
                        cur = frag_src.get(idx)
                        if cur is None or (0, w) > (cur['direct'], cur['w']):
                            frag_src[idx] = {'w': w, 'kw': k, 'direct': 0,
                                             'meta': kw_meta.get(k, {})}

            ranked = []
            for idx, src in frag_src.items():
                f = self.fragments[idx]
                st = float(f.get('strength', 0.4))
                sal = float(f.get('salience', 0.4))
                try:
                    age = max(0.0, now - float(f.get('t', now)))
                except Exception:
                    age = 0.0
                rec = 1.0 / (1.0 + age / 86400.0)
                score = (src['w'] * (0.35 + 0.65 * st) * (0.60 + 0.60 * sal)
                         * (0.70 + 0.50 * rec))
                ranked.append((score, idx, src))
            ranked.sort(key=lambda x: -x[0])

            # 关键记忆优先（人对重要的事印象更深）
            key_hits = []
            _probe = list(cue_kw) + list(kw_assoc)
            for k in self.keys:
                t = str(k.get('text') or '')
                for kw in _probe:
                    if kw and kw in t:
                        key_hits.append(k)
                        break
            for k in sorted(key_hits, key=lambda k: -float(k.get('last_at', 0)))[:2]:
                out.append({
                    'kind': k.get('kind'), 'who': 'key', 'text': k.get('text'),
                    'when': self._freshness(k.get('t'), now),
                    'day': self._day_of(k.get('t')), 'tod': self._tod_of(k.get('t')),
                    'score': 1.0, 'is_key': True,
                })

            for score, idx, src in ranked:
                f = self.fragments[idx]
                meta = src['meta'] or {}
                out.append(self._digest_item(
                    f, score, now, via=meta.get('via'), tier=meta.get('tier'),
                    hop=meta.get('hop'), direct=bool(src['direct']),
                    match_kw=src['kw']))
                if reinforce:
                    self._reinforce(f, now, 0.6)

            # 片段不够时补日摘要（"我记得那天大概聊过…"）
            if len(out) < limit:
                for day in sorted(self.digests.keys(), reverse=True):
                    if len(out) >= limit:
                        break
                    d = str(self.digests.get(day) or '')
                    if any(kw in d for kw in _probe):
                        out.append({'kind': 'digest', 'who': 'self', 'text': d,
                                    'when': day, 'day': day, 'tod': '', 'score': 0.3,
                                    'is_digest': True})

            # ④ 重排去重降冗余（MMR 式：说的是同一件事的只留一条；同日限 N 条）
            from memory_graph import MemoryGraph as _MG
            out = (_MG.rerank(out, limit=limit, overlap_threshold=self.RERANK_OVERLAP,
                              max_per_day=self.RERANK_MAX_PER_DAY)
                   if _MG is not None else out[:limit])

            # ⑤ LLM 验证挡无关（**可选、默认关闭**，且必须由预算给出额度）
            # 默认 max_llm_calls=0 → 这一整块永不执行：离线优先、零额外开销。
            # 只有调用方显式 `set_verifier()` 且把预算调成正数，才会真的去问模型。
            if (self._verifier is not None and budget is not None
                    and int(getattr(budget, 'max_llm_calls', 0) or 0) > 0
                    and int(self.recall_stats.get('llm_calls') or 0)
                        < int(budget.max_llm_calls)):
                try:
                    _kept = self._verifier(list(out), cue, budget)
                    if isinstance(_kept, (list, tuple)):
                        out = list(_kept)
                    self.recall_stats['llm_calls'] = \
                        int(self.recall_stats.get('llm_calls') or 0) + 1
                except Exception as e:
                    _log.debug("memory_system LLM 验证降级（保留原结果）: %s", e)

            # ---- ⑤ 记账：这次召回用了哪些边/多少跳/什么层（供反馈与指标）----
            token = self._recall_seq
            self._recall_seq += 1
            for it in out:
                it['recall_token'] = token
            self._note_recall(token, cue_kw, all_paths, out, kw_assoc, now)
            if reinforce and out:
                self.autosave()
        except Exception as e:
            _log.debug("memory_system 召回失败（已忽略）: %s", e)
        return out[:limit]

    # ------------------------------------------------------- 召回记账与反馈
    def _note_recall(self, token, cue_kw, paths, items, kw_assoc, now):
        """记录一次召回（指标 + 供反馈回填的路径），并截断日志长度。"""
        try:
            with self._lock:
                by_tier, by_hop = {}, {}
                for it in items:
                    t = it.get('tier') or 'direct'
                    by_tier[t] = by_tier.get(t, 0) + 1
                    self.recall_stats['by_tier_total'][t] = \
                        self.recall_stats['by_tier_total'].get(t, 0) + 1
                    h = it.get('hop')
                    if h is not None:
                        by_hop[h] = by_hop.get(h, 0) + 1
                        self.recall_stats['by_hop_total'][h] = \
                            self.recall_stats['by_hop_total'].get(h, 0) + 1
                self.recall_stats['queries'] += 1
                self.recall_stats['items'] += len(items)
                self._recall_log[token] = {
                    'ts': now, 'cue_kw': list(cue_kw), 'paths': paths[:40],
                    'assoc_kw': list(kw_assoc), 'items': [
                        {'match_kw': it.get('match_kw'),
                         'tier': it.get('tier') or 'direct',
                         'hop': it.get('hop'),
                         'text': str(it.get('text') or '')[:40]} for it in items],
                }
                if len(self._recall_log) > self.RECALL_LOG_MAX:
                    for old in sorted(self._recall_log.keys())[:-self.RECALL_LOG_MAX]:
                        self._recall_log.pop(old, None)
        except Exception as e:
            _log.debug("memory_system 召回记账失败（已忽略）: %s", e)

    def recall_feedback(self, token, success=True, used=1, lr=None):
        """回填一次召回的反馈（**反馈学习边权**）。

        调用时机：那次回忆在对话里真的被用上/被主人接住了 → 成功；被无视/答偏 → 失败。
        正反馈沿"被用过的路径"加边权（tanh 压缩，防单次抖动），负反馈减半；
        同时累计有用率/成功率，供 `consolidate`/`tune` 反哺检索参数。
        """
        stat = None
        try:
            with self._lock:
                stat = self._recall_log.pop(token, None)
                if stat is None:
                    return {'ok': False, 'reason': 'unknown_token'}
                used = max(0, int(used))
                if used:
                    self.recall_stats['used'] += used
                    for it in stat.get('items') or []:
                        t = it.get('tier') or 'direct'
                        self.recall_stats['by_tier_used'][t] = \
                            self.recall_stats['by_tier_used'].get(t, 0) + 1
                if success:
                    self.recall_stats['success_queries'] += 1
            touched = 0
            if self._graph is not None and stat.get('paths'):
                touched = self._graph.feedback(
                    stat['paths'], bool(success),
                    lr=self.FEEDBACK_LR if lr is None else float(lr))
            self.recall_metrics = self.recall_report()
            self.autosave()
            return {'ok': True, 'touched': touched}
        except Exception as e:
            _log.debug("memory_system 召回反馈失败（已忽略）: %s", e)
            return {'ok': False, 'reason': str(e)}

    def set_verifier(self, fn):
        """注入可选的"LLM 验证器"（挡无关的回忆）。

        `fn(items, cue, budget) -> 过滤后的 items`。**默认不注入**：记忆检索要
        离线可用、零额外开销；而一旦注入，是否真的调用还受 `RecallBudget.max_llm_calls`
        限制（预算为 0 时永不调用，见 `recall` 的 ⑤ 段）。传 None 可摘掉。
        """
        self._verifier = fn if callable(fn) else None
        return self._verifier is not None

    def recall_report(self):
        """召回质量评估：噪声率 / 有用率 / 成功率（按层、按跳分桶）。"""
        s = self.recall_stats
        q = max(1, int(s.get('queries') or 0))
        items = int(s.get('items') or 0)
        used = int(s.get('used') or 0)
        tiers = {}
        for t in set(list((s.get('by_tier_total') or {}).keys()) +
                     list((s.get('by_tier_used') or {}).keys())):
            tot = int((s.get('by_tier_total') or {}).get(t) or 0)
            u = int((s.get('by_tier_used') or {}).get(t) or 0)
            tiers[t] = {'total': tot, 'used': u,
                        'useful_rate': round(u / float(tot), 4) if tot else None}
        return {
            'queries': int(s.get('queries') or 0),
            'items': items, 'used': used,
            'noise_rate': round(1.0 - used / float(items), 4) if items else 0.0,
            'useful_rate': round(used / float(items), 4) if items else 0.0,
            'success_rate': round(int(s.get('success_queries') or 0) / float(q), 4),
            'by_tier': tiers,
            'by_hop_total': dict(s.get('by_hop_total') or {}),
            'weak_penalty': round(float(getattr(self._graph, 'weak_penalty', 0.0) or 0.0), 4),
        }

    def consolidate(self, now=None, budget=None):
        """离线巩固（**离线巩固**）：把日摘要/关键记忆里的词团喂回图，再让图自己
        老化/升降级/剪枝，最后按指标微调检索参数。由 `update()` 按间隔触发。
        """
        stats = {}
        try:
            now = float(now if now is not None else time.time())
            extra = []
            # 从日摘要里提炼词团（让"很久以前聊过的东西"也长出新联想）
            for day in sorted(self.digests.keys(), reverse=True)[:30]:
                kws = self._kw_of(str(self.digests.get(day) or ''), limit=5)
                if len(kws) >= 2:
                    extra.append((kws, 1))
            # 关键记忆里的词团（权重 2：重要的事，允许长到中/强边）
            for k in self.keys[-40:]:
                kws = self._kw_of(str(k.get('text') or ''), limit=4)
                if len(kws) >= 2:
                    extra.append((kws, 2))
            if self._graph is not None:
                stats = self._graph.consolidate(now=now,
                                                extra_cooccurrence=extra,
                                                budget=budget)
                stats['tune'] = self._graph.tune(self.recall_metrics or {})
            self._last_consolidate = now
            self._build_index()
        except Exception as e:
            _log.debug("memory_system 离线巩固异常（已忽略）: %s", e)
        return stats

    def _digest_item(self, frag, score, now, via=None, tier=None, hop=None,
                     direct=None, match_kw=None):
        it = {
            'kind': frag.get('kind'), 'who': frag.get('who'),
            'text': frag.get('text'),
            'when': self._freshness(frag.get('t'), now),
            'day': frag.get('day'), 'tod': self._tod_of(frag.get('t')),
            'kw': list(frag.get('kw') or []),
            'score': round(float(score), 4),
        }
        if via:
            it['via'] = list(via)[:self.MAX_VIA]
        if tier:
            it['tier'] = tier
        if hop is not None:
            it['hop'] = int(hop)
        if direct is not None:
            it['direct'] = bool(direct)
        if match_kw:
            it['match_kw'] = match_kw
        return it

    def recall_text(self, cue, limit=3):
        """给模型看的"想起片段"中文块（本模块影响对话的出口之一）。

        只在真的想起东西时返回内容，否则返回空串 —— 不能为了显得记性好就硬编。
        """
        try:
            items = self.recall(cue, limit=limit)
        except Exception as e:
            _log.debug("memory_system 召回失败（已忽略）: %s", e)
            return ""
        if not items:
            return ""
        lines = ["【零星的回忆（可以自然提一句，别生硬复述）】"]
        for it in items:
            # 第二十轮：`who` 从「主人」改为「你」—— 用户与 Ralsei 是**平级**关系，
            # 不许再让他管对方叫"主人"。这里直接落进发给模型的提示词，
            # 所以是**会真正生效**的一处（不像注释），必须和 persona 口径一致。
            # 兼容：存储里 who 仍是 'user'（历史数据不改写，只改展示标签）。
            who = '你' if it.get('who') == 'user' else (
                '（重要的事）' if it.get('is_key') else '我')
            when = str(it.get('when') or '')
            tod = str(it.get('tod') or '')
            stamp = (when + ('的' + tod if tod else '')).strip()
            body = str(it.get('text') or '')
            # 第十轮：把"怎么想到的"也带上（多跳联想的中间词）——这个信息对模型有
            # 实际价值：它知道这不是顺口胡说，而是"从 A 想到 B 想到 C"，可以说得更自然。
            via = [str(v) for v in (it.get('via') or []) if v]
            hint = ('（由%s联想到的）' % '、'.join(via[:self.MAX_VIA])) if via else ''
            if it.get('is_digest'):
                lines.append("· %s 的印象：%s" % (stamp or '那天', body))
            else:
                lines.append("· %s，%s说过「%s」%s" % (stamp or '以前', who, body, hint))
        return "\n".join(lines)

    def reconstruct_scene(self, cue, limit=6):
        """根据零星片段"重构当时的场景"：聚到同一天，拼成一小段叙述。"""
        try:
            items = self.recall(cue, limit=limit, reinforce=False)
        except Exception:
            return ""
        items = [i for i in items if not i.get('is_digest')]
        if not items:
            return ""
        by_day = {}
        for it in items:
            by_day.setdefault(str(it.get('day') or ''), []).append(it)
        day, group = max(by_day.items(),
                         key=lambda kv: sum(float(i.get('score') or 0) for i in kv[1]))
        if not day:
            return ""
        topics, said = [], []
        for it in group[:4]:
            t = str(it.get('text') or '')
            if it.get('who') == 'user' and t and t not in said:
                said.append(t)
        for it in group:
            for k in self._kw_of(str(it.get('text') or ''), limit=3):
                if k not in topics:
                    topics.append(k)
        tod = str(group[0].get('tod') or '')
        head = "那大概是 %s%s，我们正聊着%s。" % (
            day, ('的' + tod if tod else ''), '、'.join(topics[:3]) or '些家常')
        if said:
            head += "我记得你说过「%s」。" % said[0]
        return head

    # ------------------------------------------------------------ 遗忘
    def forget_cycle(self, now=None):
        """遗忘与压缩：衰减 → 日摘要 → 裁剪。返回统计（便于自检/留痕）。

        三条保护（对应"确保不失忆"）：
          · 关键记忆（self.keys / PROTECTED_KINDS）永不删；
          · 最近 `KEEP_FULL_DAYS` 天的片段不压不删；
          · 删除前先把那天的"印象"写进日摘要（细节忘了，梗概留下）。
        """
        stats = {'fragments_before': len(self.fragments), 'forgotten': 0,
                 'digests_new': 0, 'fragments_after': 0, 'keys': len(self.keys)}
        try:
            import math
            now = float(now if now is not None else time.time())
            today = self._day_of(now)

            # ① 强度衰减（艾宾浩斯式）：显著度高 → 遗忘慢
            for f in self.fragments:
                try:
                    st = float(f.get('strength', 0.4))
                    sal = float(f.get('salience', 0.4))
                    last = float(f.get('seen') or f.get('t') or now)
                    dt = max(0.0, now - last)
                    tau = 86400.0 * (2.0 + 6.0 * sal)
                    f['strength'] = round(max(0.0, st * math.exp(-dt / tau)), 4)
                except Exception:
                    continue

            # ② 把"已经变老、又还没记摘要"的日子压成日摘要
            by_day = {}
            for f in self.fragments:
                by_day.setdefault(str(f.get('day') or ''), []).append(f)
            for day, frags in by_day.items():
                if not day or day == today or day in self.digests:
                    continue
                newest = max(float(f.get('t', 0)) for f in frags)
                if (now - newest) < self.DIGEST_AFTER_DAYS * 86400.0:
                    continue
                self.digests[day] = self._make_digest(frags)
                stats['digests_new'] += 1

            # ③ 遗忘：只忘"又弱又老又不关键"的
            kept = []
            for f in self.fragments:
                try:
                    age = now - float(f.get('t', now))
                except Exception:
                    age = 0.0
                protected = (age < self.KEEP_FULL_DAYS * 86400.0
                             or str(f.get('kind')) in self.PROTECTED_KINDS)
                if not protected and float(f.get('strength', 0.0)) < self.FORGET_STRENGTH_FLOOR:
                    stats['forgotten'] += 1
                    continue
                kept.append(f)

            # ④ 硬上限兜底：还不够就按"强度×显著度"留最强的
            if len(kept) > self.MAX_FRAGMENTS:
                kept.sort(key=lambda f: (float(f.get('strength', 0)) *
                                         (0.5 + float(f.get('salience', 0))),
                                         float(f.get('t', 0))), reverse=True)
                stats['forgotten'] += len(kept) - self.MAX_FRAGMENTS
                kept = kept[:self.MAX_FRAGMENTS]

            self.fragments = kept
            stats['fragments_after'] = len(self.fragments)

            # ⑤ 日摘要/联想图/关键记忆的体量控制
            if len(self.digests) > self.MAX_DIGEST_DAYS:
                for day in sorted(self.digests.keys())[:-self.MAX_DIGEST_DAYS]:
                    self.digests.pop(day, None)
            # 联想图体量：第十轮起边记录是 dict（带 tier/fb/last），不能再按
            # `int(v)` 排序（那会对 dict 取 int → TypeError，把后面的重建索引也一起带崩）。
            # 交给图自己按"边权之和"裁剪。
            if self._graph is not None:
                self._graph.cap_keys(self.MAX_ASSOC_KEYS)
            if len(self.keys) > self.MAX_KEYS:
                self.keys.sort(key=lambda k: (float(k.get('salience', 0.5)),
                                              float(k.get('last_at', 0))), reverse=True)
                self.keys = self.keys[:self.MAX_KEYS]

            self._build_index()
            stats['keys'] = len(self.keys)
            if stats['forgotten'] or stats['digests_new']:
                self.autosave()
        except Exception as e:
            _log.warning("遗忘周期异常（跳过本轮）: %s", e)
        return stats

    def _make_digest(self, frags):
        """把一天的片段压成一句"印象"：那天聊了什么 + 最难忘的一句。"""
        try:
            from collections import Counter
            cnt = Counter()
            for f in frags:
                for k in (f.get('kw') or []):
                    cnt[k] += 1
            topics = [k for k, _c in cnt.most_common(6)]
            best = max(frags, key=lambda f: float(f.get('salience', 0) or 0))
            snippet = str(best.get('text') or '')[:40]
            tod = self._tod_of(best.get('t'))
            parts = []
            if topics:
                parts.append('聊过' + '、'.join(topics))
            if snippet:
                parts.append('印象最深的是「%s」' % snippet)
            body = '；'.join(parts) or '有过一段没什么内容的闲聊'
            return (tod + '：' + body) if tod else body
        except Exception as e:
            _log.debug("memory_system 日摘要生成失败（已忽略）: %s", e)
            return ''

    # ------------------------------------------------------------ 存储迁移
    def maybe_relocate_storage(self):
        """设备插拔检查：当前存在桌面兜底、而设备已接入 → 搬进设备并清桌面副本。

        对应要求："等下次检测到这个设备接入后再把东西放进去，同时把桌面上的多余的
        记忆清除"。搬运动作本身由 memory_store 负责（先写成功再删源）。
        """
        if getattr(self, '_on_device', False):
            return {'moved': False, 'reason': '已在设备上'}
        try:
            dev = self._store.find_device_dir(create=True)
        except Exception as e:
            return {'moved': False, 'reason': '设备探测失败: %s' % e}
        if not dev:
            return {'moved': False, 'reason': '设备未接入'}
        # 先确保桌面上这份是最新的，再搬
        self.save_memory()
        mv = self._store.migrate_from_fallback(dev)
        self.memory_dir = dev
        self._on_device = True
        self._device_dir = dev
        self.memory_file = self._store.memory_file_in(dev)
        if not os.path.exists(self.memory_file):
            # 设备侧没有文件（搬运没成功）→ 把内存里的现状写过去，至少不丢
            self.save_memory()
        _log.info("记忆存储已迁移到设备目录: %s", mv)
        return mv

    def get_memory_stats(self):
        """记忆体量/位置自检（给日志与验证脚本用）。"""
        try:
            size = os.path.getsize(self.memory_file) if os.path.exists(self.memory_file) else 0
        except Exception:
            size = 0
        strengths = [float(f.get('strength') or 0) for f in self.fragments]
        return {
            'dir': self.memory_dir,
            'on_device': bool(getattr(self, '_on_device', False)),
            'file': self.memory_file,
            'file_bytes': size,
            'fragments': len(self.fragments),
            'keys': len(self.keys),
            'digests': len(self.digests),
            'assoc_keys': len(self.assoc),
            'short_term': len(self.short_term_memory),
            'interaction_history': len(self.long_term_memory.get('interaction_history') or []),
            'avg_strength': round(sum(strengths) / len(strengths), 4) if strengths else 0.0,
            'index_keys': len(self._index),
            # 第十轮：图与召回质量（噪声率/有用率/成功率）
            'graph': (self._graph.stats() if self._graph is not None else {}),
            'recall': self.recall_report(),
            'recall_log': len(self._recall_log),
        }
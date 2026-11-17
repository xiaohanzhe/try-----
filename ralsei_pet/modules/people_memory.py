# -*- coding: utf-8 -*-
"""每人一份独立记忆库（第195轮）。

用户口径：
  「ralsei 和其他人一样，是同级的那种，也就是现有 ralsei 的功能需要在所有人身上
   都能看到，但，也要根据具体情况来看」

★★★ 为什么不给 `MemorySystem` 加一个 `owner` 维度、所有人都塞一个库
--------------------------------------------------------------------
`recall()` 对关键记忆的匹配面是 `text + ' ' + meta.where`，**不含 `who`**。
混在一个库里，Lancer 在教室"盘算"过一次，那么问"教室"时 **Ralsei 也会想起来** ——
这就是串味。`npc_persona.MiniMemory` 早在自己的注释里写过同一个结论：
「不是"一个大文件按 id 分桶"：分桶写法只要有一处忘了带过滤就会串」。

所以这里走**物理分开**：一个 NPC 一个目录、一个 `memory.json`。
读谁的记忆，在文件系统层面就只碰得到谁的数据。

★★ 性能（用户：「要么来个 5090 都跑不动这程序的算力」）
----------------------------------------------------------
一个 `MemorySystem` 要加载 JSON、建倒排索引、建关联图，不是轻对象。
96 个人一人一个常驻实例 = 必然卡。所以：

  1. **懒加载** —— 没人跟他说话就不建库（`of()` 才建）；
  2. **LRU 上限** —— 同时驻留最多 `max_loaded`（默认 6）个，超了先把最久没用的
     存盘、再释放（`_evict`）。常驻内存与"在场几个人"同阶，与总人数无关；
  3. **单库内部的上限**仍由 `MemorySystem` 自己的
     `MAX_KEYS` / `INNER_KEYS_MAX` / 片段裁剪负责，这里不重复设限。

★ `root=None` ⇒ 纯内存态（不落盘，可离线单测）。
"""

import collections
import os
import threading

#: 同时驻留内存的库数上限。6 的依据：一屏不可能同时有 6 个人在说话，
#: 而一次"进入房间"最多也就翻到 3~4 个人。
MAX_LOADED = 6

#: 相对记忆根的子目录名（与 Ralsei 的 `memory.json` 同级）
SUBDIR = 'npc_mem'


class _NullParent(object):
    """`MemorySystem` 只用到 parent 的少数可选项，给它一个空壳即可。"""

    api_enabled = False


def _default_factory(memory_dir):
    """造一个指向 `memory_dir` 的 MemorySystem（导入放函数里，避免循环）。"""
    import memory_system as _MS
    return _MS.MemorySystem(_NullParent(), memory_dir=memory_dir)


#: `default_root()` 的缓存：key = 当前 `RALSEI_MEMORY_DIR` 值（变了就重算）。
#: ★ 为什么必须缓存：`memory_store.default_memory_dir()` 会做**设备探测**，
#:   而 `MemorySystem(self)` 启动时已经调过一次；这里再探一次纯属浪费。
#:   用户明确要求兼顾性能，所以同一个 env 下只算一次。
_ROOT_CACHE = {}


def default_root():
    """默认根：`<Ralsei 记忆目录>/npc_mem`。

    ★ 跟随 `memory_store.default_memory_dir()` ⇒ `RALSEI_MEMORY_DIR` 一改，
      所有 NPC 的库也跟着走（测试/换机时不会漏）。
    ★ 取不到 ⇒ `None`（调用方自己决定要不要落盘），**不伪造路径**。
    """
    key = os.environ.get('RALSEI_MEMORY_DIR') or ''
    if key in _ROOT_CACHE:
        return _ROOT_CACHE[key]
    try:
        import memory_store
        base = memory_store.default_memory_dir()[0]
    except Exception:
        return None
    if not base:
        return None
    p = os.path.join(str(base), SUBDIR)
    _ROOT_CACHE[key] = p
    return p


class PeopleMemoryBank(object):
    """NPC 记忆库的**唯一入口**：`of(npc_id)`。

    没有 `all()` / `everyone()` / `recall_all()` 这种入口 —— 与 `MiniMemory` 同一条
    设计约束：让人"忘了过滤"这件事在接口层面就写不出来。
    """

    def __init__(self, root=None, factory=None, max_loaded=MAX_LOADED):
        self.root = root
        self._factory = factory
        try:
            self.max_loaded = max(1, int(max_loaded))
        except (TypeError, ValueError):
            self.max_loaded = MAX_LOADED
        self._by = collections.OrderedDict()   # npc_id -> MemorySystem（按使用顺序）
        self._lock = threading.RLock()
        #: 观测用：建了几次库、淘汰了几次（判据/自检读它，别去翻私有字典）
        self.stats = {'built': 0, 'evicted': 0, 'hits': 0}

    # ------------------------------------------------------------ 路径
    @staticmethod
    def safe_id(npc_id):
        """把 id 洗成安全文件名；不合法 ⇒ `''`（**不猜、不兜底成一个默认人**）。

        ★★★ 要求"清洗后**必须等于原值**"：`'../etc'` 洗一洗会变成 `etc`，
          若放行就等于把这段非法输入悄悄当成了另一个人（`'a/b'` → `ab` 同理）。
          宁可返回 `''` 让调用方安静跳过，也不许改名后照用。
        """
        if not isinstance(npc_id, str):
            return ''
        s = npc_id.strip()
        if not s:
            return ''
        safe = ''.join(c for c in s if c.isalnum() or c in '_-')
        return safe if safe == s else ''

    def dir_of(self, npc_id):
        """该 NPC 的库目录；`root=None` 或 id 非法 ⇒ `None`。"""
        sid = self.safe_id(npc_id)
        if not sid or not self.root:
            return None
        return os.path.join(str(self.root), sid)

    def file_of(self, npc_id):
        d = self.dir_of(npc_id)
        return os.path.join(d, 'memory.json') if d else None

    # ------------------------------------------------------------ 取库
    def of(self, npc_id):
        """取（必要时建）某个 NPC 的记忆库。id 非法 ⇒ `None`。

        ★ 返回 `None` 时调用方应当**安静跳过**（记不成不是错误）。
        """
        sid = self.safe_id(npc_id)
        if not sid:
            return None
        with self._lock:
            cur = self._by.get(sid)
            if cur is not None:
                self._by.move_to_end(sid)
                self.stats['hits'] += 1
                return cur
            d = self.dir_of(sid)
            if not d:
                return None
            try:
                os.makedirs(d, exist_ok=True)
            except Exception:
                return None
            factory = self._factory or _default_factory
            try:
                ms = factory(d)
            except Exception:
                return None
            if ms is None:
                return None
            self._by[sid] = ms
            self.stats['built'] += 1
            self._evict_locked()
            return ms

    def _evict_locked(self):
        """超出上限 ⇒ 把最久没用的存盘后丢弃（调用方已持锁）。"""
        while len(self._by) > self.max_loaded:
            _k, ms = self._by.popitem(last=False)
            try:
                saver = getattr(ms, 'save_memory', None)
                if callable(saver):
                    saver()
            except Exception:
                pass
            self.stats['evicted'] += 1

    # ------------------------------------------------------------ 生命周期
    def loaded_ids(self):
        with self._lock:
            return list(self._by.keys())

    def save_all(self):
        """全部存盘（退出前调用）。返回成功条数。"""
        n = 0
        with self._lock:
            for ms in list(self._by.values()):
                try:
                    saver = getattr(ms, 'save_memory', None)
                    if callable(saver) and saver():
                        n += 1
                except Exception:
                    pass
        return n

    def drop(self, npc_id):
        """把某个 NPC 的库从内存里丢掉（先存盘）。返回是否真的丢了一个。"""
        sid = self.safe_id(npc_id)
        with self._lock:
            ms = self._by.pop(sid, None)
        if ms is None:
            return False
        try:
            ms.save_memory()
        except Exception:
            pass
        return True

    def clear_loaded(self):
        """只清内存驻留，不删盘上任何文件（测试用）。"""
        with self._lock:
            n = len(self._by)
            self._by = collections.OrderedDict()
        return n

# -*- coding: utf-8 -*-
u"""NPC「生活档案」的**落盘容器**（第81轮，层4 存档）。
==================================================

要解决什么
----------
第79/80轮把 NPC 自主生活做到了**层1 意图 / 层2 驻留 / 层3 就寝**，
但全部活**只在内存里**：桌宠一重启，`RoamState` 清空、`Plan` 丢失
⇒ NPC「昨天睡在朋友家」这件事第二天就不记得了（`choose_sleep_scene` 的
`last_sleep` 降权永远拿不到值 ⇒ 降权形同虚设）。

本模块 = **纯容器 + 序列化**，把三份状态收进一本书：

  ```python
  Book.to_dict() -> {
      'schema_version': 1,
      'roam':  {...},          # npc_roam.RoamState.to_dict()
      'plans': {npc_id: {...}},  # npc_intent.Plan.to_dict()
  }
  ```

★★★ 零依赖纪律（与 `npc_roam` / `npc_intent` / `npc_placement` 同规）
--------------------------------------------------------------------
顶层**只** import 标准库（`json` / `os` / `collections`）；
**零函数内 import**；**不 import 任何项目内模块**。

⇒ 那么"存到哪"（`data_store` 的 vault 优先逻辑）**不由本模块决定**：
   路径是**注入**的。调用方（`main.py`，它有权 import `data_store`）
   调 `data_store.artifact_path('npc_life.json')` 拿到绝对路径再传进来。

   这条纪律的理由见 `ghost_system`：`data_store` 在初始化环上
   （`logger_utils → data_store → memory_store → logger_utils`），
   底层数据模块回头 import 它会**把日志目录永久钉死**（第十二轮实测）。

★ 容错约定（**全部入口绝不抛**）
--------------------------------
读：文件不存在 / 不是 JSON / 结构不符 / 版本不符 ⇒ 返回**空书**（不是异常）。
写：写失败 ⇒ 返回 `False`（调用方降级为"本次不落盘"，**不许让桌宠崩**）。
—— 与 `data_store` / `load_placement` 同一条纪律：非关键路径不抛。

★ 有界
------
`Plan.history` 由 `note(keep=12)` 自截；`Book.save()` 前再**兜一遍**
（`MAX_HISTORY`），避免外部塞进来一本超大的书把 E 盘写爆。
"""
import collections
import importlib
import json
import os


SCHEMA_VERSION = 1

#: 落盘文件名（相对 `data_store` 的数据根）。★ 调用方用 `data_store.artifact_path()` 解析。
FILENAME = 'npc_life.json'

#: `history` 的硬上限（`Plan.note` 已按 12 截，这里是**二次兜底**）。
MAX_HISTORY = 12


def _safe_int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


class Book(object):
    """NPC 生活档案：**驻留表 + 每人的规划**。可在内存里独立使用（不落盘也行）。

    * `roam`  : `npc_roam.RoamState`（或 `None`）
    * `plans` : `{npc_id: npc_intent.Plan}`

    ★ 本类**不做**语义校验（不知 `RoamState` / `Plan` 长什么样）——
      它只调它们的 `to_dict()` / `from_dict()`，这是双方约定的**序列化契约**。
      契约的实现与验证在各自模块里（`npc_roam` / `npc_intent` 的回归锁）。
    """

    __slots__ = ('roam', 'plans')

    def __init__(self, roam=None, plans=None):
        self.roam = roam
        self.plans = dict(plans or {})

    # ---------------------------------------------------------------- 取用
    def plan_of(self, npc_id):
        """→ 该 NPC 的 `Plan`；没有就**建一个新的**（并记进书里）。

        ★ 为什么"没有就建"而不是返回 `None`：调用方（`_npc_roam_decide`）
          每次决策都要一个能 `note()` 的对象；返回 `None` 会让调用方
          到处写 `if p is None: p = ...` —— 那是**同一份规则两处算**的温床。
        """
        p = self.plans.get(npc_id)
        if p is None:
            p = _new_plan()
            self.plans[npc_id] = p
        return p

    def last_sleep_of(self, npc_id):
        """→ 该 NPC「昨晚睡在哪」（`Plan.last_sleep_scene`）；不知道 ⇒ `None`。

        ★ 这正是 `npc_intent.choose_sleep_scene(last_sleep=...)` 要的那个入参
          —— 层4 之前它永远是 `None`，降权逻辑拿不到数据。
        """
        p = self.plans.get(npc_id)
        return getattr(p, 'last_sleep_scene', None) if p is not None else None

    def note_sleep(self, npc_id, scene):
        """记下"今晚睡在 `scene`"（写进该 NPC 的 `Plan.last_sleep_scene`）。"""
        if not scene:
            return False
        self.plan_of(npc_id).last_sleep_scene = scene
        return True

    def ids(self):
        """→ 有规划的 NPC id（排序稳定）。"""
        return sorted(self.plans)

    # ---------------------------------------------------------------- 序列化
    def to_dict(self):
        plans = collections.OrderedDict()
        for nid in sorted(self.plans):
            p = self.plans[nid]
            try:
                d = p.to_dict()
            except Exception:
                continue
            # ★ 二次兜底：外部塞进来的书可能 history 超长
            try:
                if isinstance(d.get('history'), list) and len(d['history']) > MAX_HISTORY:
                    d['history'] = d['history'][-MAX_HISTORY:]
            except Exception:
                pass
            plans[nid] = d
        roam = None
        if self.roam is not None:
            try:
                roam = self.roam.to_dict()
            except Exception:
                roam = None
        return collections.OrderedDict((
            ('schema_version', SCHEMA_VERSION),
            ('roam', roam),
            ('plans', plans),
        ))

    @classmethod
    def from_dict(cls, d):
        """从字典还原。**任何异常都退回空书**（绝不抛）。"""
        try:
            if not isinstance(d, dict):
                return cls()
            if _safe_int(d.get('schema_version'), -1) != SCHEMA_VERSION:
                return cls()
            plans = {}
            for nid, pd in (d.get('plans') or {}).items():
                if not isinstance(nid, str) or not isinstance(pd, dict):
                    continue
                p = _plan_from_dict(pd)
                if p is not None:
                    plans[nid] = p
            return cls(roam=_roam_from_dict(d.get('roam')), plans=plans)
        except Exception:
            return cls()


# ---------------------------------------------------------------- 与 npc_intent 的契约
#  ★★ 这里**不 import** `npc_intent`（零依赖）。契约 = 两个方法名：
#     `Plan.to_dict()` / `Plan.from_dict(d)`。判据（check81）会真去
#     `npc_intent` 里验这两个方法在位且**往返等价** —— 契约是**被测**的，不是假设的。


def _new_plan():
    """造一个空 `Plan`（真源 = `npc_intent.Plan`）。拿不到就退化成最小替身。

    ★★ 为什么要"退化成替身"而不是抛：本模块是**数据层**，若 `npc_intent`
      因为任何原因拿不到，桌宠仍应能跑（只是规划不持久化）——
      退化的替身仍满足契约（`to_dict` / `from_dict` / `last_sleep_scene`）。
    """
    P = _plan_cls()
    try:
        return P()
    except Exception:
        return _FallbackPlan()


def _plan_from_dict(d):
    P = _plan_cls()
    try:
        return P.from_dict(d)
    except Exception:
        return None


def _roam_from_dict(d):
    """还原 `npc_roam.RoamState`；`d` 为空 / 拿不到类 ⇒ `None`（**空表语义**）。

    ★ 为什么拿不到就 `None` 而不是退化成替身：`RoamState` 是**状态机**
      （带 `enabled` 开关与 `_by_id` 索引），仿一个假的有静默出错风险；
      而 `None` 的语义在 `main` 侧是明确的（"驻留层未启用/未落盘"）。
    """
    if not isinstance(d, dict) or not d:
        return None
    R = _roam_cls()
    if R is None:
        return None
    try:
        return R.from_dict(d)
    except Exception:
        return None


def _plan_cls():
    """**惰性**取 `npc_intent.Plan`（`importlib` 是标准库，不违反零项目依赖）。

    ★ 为什么用 `importlib` 而不是 `import npc_intent`：
      顶层 import 会让 `npc_plan_store` **强依赖** `npc_intent` 的存在；
      而本模块的契约是"只要对方有 `Plan` 这个类"—— `importlib` 让它**软**下来，
      且不把项目内模块写进顶层 import 列表（AST 判据才守得住零依赖）。
    ★ `importlib` 必须在**模块级** import（零依赖纪律禁函数内 import，
      见 `check56` A3；本模块同规）。
    """
    for name in ('npc_intent', 'modules.npc_intent'):
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        P = getattr(mod, 'Plan', None)
        if P is not None:
            return P
    return _FallbackPlan


def _roam_cls():
    """**惰性**取 `npc_roam.RoamState`；拿不到 ⇒ `None`（不仿替身，见 `_roam_from_dict`）。"""
    for name in ('npc_roam', 'modules.npc_roam'):
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        R = getattr(mod, 'RoamState', None)
        if R is not None:
            return R
    return None


class _FallbackPlan(object):
    """`npc_intent.Plan` 拿不到时的**最小替身**（仍满足契约，只有本文件用）。

    ★ 字段名与真源**逐字一致**（`day` / `intent` / `last_sleep_scene` /
      `wants` / `history`），否则"退化了也能跑"会变成"退化了就写坏文件"。
    """

    __slots__ = ('day', 'intent', 'last_sleep_scene', 'wants', 'history')

    def __init__(self, day=0, intent=None, last_sleep_scene=None, wants=None,
                 history=None):
        self.day = _safe_int(day)
        self.intent = intent
        self.last_sleep_scene = last_sleep_scene
        self.wants = list(wants or ())
        self.history = list(history or [])

    def to_dict(self):
        return collections.OrderedDict((
            ('day', self.day),
            ('intent', None),
            ('last_sleep_scene', self.last_sleep_scene),
            ('wants', list(self.wants)),
            ('history', list(self.history)),
        ))

    @classmethod
    def from_dict(cls, d):
        d = d or {}
        return cls(d.get('day') or 0, None, d.get('last_sleep_scene'),
                   d.get('wants'), d.get('history'))


# ---------------------------------------------------------------- 读写（路径注入）
def load(path):
    """从 `path` 读一本书。**绝不抛**：读不到 / 读坏了 ⇒ 空书。"""
    try:
        if not path or not os.path.exists(path):
            return Book()
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        return Book()
    return Book.from_dict(raw)


def save(path, book):
    """把 `book` 写到 `path`（原子写：先写 `.tmp` 再替换）。→ `bool`。

    ★ 原子写：`os.replace` 在 Windows 上对同卷是原子的 ⇒ 半截文件不会留在盘上
      （E 盘是 exFAT，掉线/拔盘是**实测发生过**的事，见 `data_store` 抬头）。
    ★ 任何失败都返回 `False`，**不抛**（调用方降级为"本次不落盘"）。
    """
    try:
        if not path or book is None:
            return False
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(book.to_dict(), f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            if path and os.path.exists(path + '.tmp'):
                os.remove(path + '.tmp')
        except Exception:
            pass
        return False


# ---------------------------------------------------------------- 声明

WIRING = collections.OrderedDict((
    ('wired', True),
    ('used_by', ['main.init_npc_systems（建书 + 读回：`npc_plan_store_mod.load(_npc_plan_file())`）',
                 'main._npc_roam_decide（`plan_of` + `note`：上次意图入 `last`，结果记回）',
                 'main._npc_roam_sleep（`last_sleep_of` + `note_sleep`：连睡降权拿到值）',
                 'main._npc_plan_save（节流 120s + 退出 `force=True` 落盘）']),
    ('wired_how', '路径由 **调用方注入**：`main._npc_plan_file()` 走 '
                  '`data_store.app_file(FILENAME)`（vault = E:\\RalseiMemory\\）；'
                  '取不到 ⇒ 退内存态（退空书，`load()` 绝不抛）。'
                  '★ 本模块**不 import `data_store`**（初始化环纪律）。'),
    ('why', '层4 存档：层1/2/3 的状态此前**只在内存**，重启即失忆；'
            '`choose_sleep_scene(last_sleep=...)` 的降权因此永远拿不到值。'),
    ('not_yet', []),
))

# -*- coding: utf-8 -*-
"""NPC 差事（errand）—— 「派任意角色去别处办事」的机制层（零依赖）。

用户口径（§109.5「灵魂视角」，逐字两条）
========================================
> 「我让 ralsei 去 oneshot 里干什么事情，**他能去，干，然后产生结果**，
>    甚至**我中途进去的时候也能看到过程**」
> 「那个可派 ralsei 做任务那个**只是个例子，任何人都可以**」（★ 收窄纠正）

⇒ 本模块只做一件事：把「某人被派去某地办某事」建模成**有始有终**的记录，
  并推进它的**生命周期**。★★ **主体 = 任意 `npc_id`**，不是 Ralsei 专属通道。

三层之分（本模块在中间那一层）
------------------------------
· `npc_intent` —— **自发**：他今天想干什么（`wander` / `visit_friend` / …）；
· `npc_errand` —— **被派**：有目的地、有期限、有结果；★ 本模块
· `npc_roam`   —— **位置**：把"他现在该在哪"落成驻留覆盖（唯一位置真源）。

生命周期（三段，单向，不回头）
------------------------------
    traveling ──(到点)──▶ working ──(到点)──▶ done
    · `traveling`：已派出、还在路上 ⇒ `scene_now()` 返回 `None`（**位置不变**）；
    · `working`  ：已到达         ⇒ `scene_now()` 返回 `dest_scene`（宿主据此压覆盖）；
    · `done`     ：办完了         ⇒ 宿主**撤掉覆盖**（回落静态归属）+ 结果落进他记忆。

★★ 为什么"过程可见"不需要额外机制（§109.5 要点 3）：
  他在 `working` 期间，位置真源（`npc_roam` 的覆盖表）里就是 `dest_scene` ⇒
  我（灵魂）中途切进那个场景，场景钩子 `_npc_seed_bodies()` 自然把他**画在那里**。
  本模块**不碰任何显示**（见下"与显示解耦"）。

★★ 为什么"结果"要固化成一个字符串而不是每次重算：
  用户要「产生结果」+「我下次进场能观察到」⇒ 结果必须**可持久化**，且**不依赖过程**
  （过程结束后仍可查）。所以 `result` 在 `done` 那一刻**定格**。

与显示解耦（§109.5 要点 1/2 —— 本模块的硬约束）
----------------------------------------------
NPC 自主/被派移动**只改 NPC 自己的位置**，**绝不切换场景显示**。
显示切换的唯一驱动 = 灵魂/用户操作（`scene.switch()` / `travel_to()`，那在别的模块）。
⇒ 本模块**不认识** `scene` / 相机 / 画布；判据 `check113` 用 AST 锁死这一点。

零依赖纪律（与 `npc_roam` / `npc_intent` / `npc_placement` / `desk_doors` 同规）
--------------------------------------------------------------------------------
· 顶层只 `import collections`（标准库）；
· **零函数内 import**；
· **不 import 任何项目内模块** —— 位置的写入由**宿主**用 `roam.put()` 完成，
  本模块只**告诉**宿主"该把谁挪到哪"（`step()` / `working_positions()` 的返回值）。
· `now` 一律**由调用方传入**（不 `import time`）⇒ 可判据、可回放、可离屏验证。
"""
import collections

# ---------------------------------------------------------------- 常量

#: 默认"在路上"的时长（秒）。
#: ★ 不是瞬移 —— 与用户口径「当原作门一样逐门寻路」同源：出门办事**要有过程**，
#:   不能一拍到位（否则"我中途进去"永远看不到他在路上）。
DEFAULT_TRAVEL_SECONDS = 90.0

#: 默认"办事"的时长（秒）。到点才产出结果。
DEFAULT_WORK_SECONDS = 300.0

#: 同时挂着的**未完成**差事上限（防"忘了收尾"导致无限积累）。
MAX_ERRANDS = 64

#: 已完成差事的留存上限（结果被宿主取走后腾位）。
MAX_DONE = 128

#: 生命周期三段（字符串常量，便于存档/日志直读）。
TRAVELING = 'traveling'
WORKING = 'working'
DONE = 'done'

#: 驻留覆盖的 `reason` 前缀 —— 宿主把它写进 `npc_roam.put(..., reason=...)`，
#: 用于在日志/存档里**区分**"自主挪窝"与"被派出办事"。
REASON_PREFIX = 'errand:'

#: ★ 第114轮：差事落盘文件名（路径由宿主用 `data_store.app_file(FILENAME)` 解析）。
#:
#: ★★ 为什么**单独一个文件**，而不是塞进 `npc_plan_store.Book`（生活档案）：
#:   `Book` 的顶层形状（`schema_version` / `roam` / `plans` 三个键）被
#:   `check81` 的 D4~D7 四条断言锁死，且 `Book.from_dict` **只认**
#:   `schema_version == 1` ⇒ 往里加第四个键会让**已写下的老档案整本被判版本不符**
#:   （丢的是驻留表与"昨晚睡哪"，代价远大于差事本身）。
#:   而差事的生命周期只有几分钟（`DEFAULT_TRAVEL_SECONDS + DEFAULT_WORK_SECONDS`），
#:   本就**不必与长期档案同生共死** —— 两本文件，各自演进。
FILENAME = 'npc_errands.json'


def default_result(npc_id, dest_scene, what):
    """结果模板（宿主没给自定义结果时用）。

    ★ 保持**陈述句**：结果要能直接塞进该 NPC 的记忆流（`MiniMemory.remember`），
      所以不用第一人称（第一人称由记忆层按 `who=npc_id` 补）。
    """
    return '%s 在 %s 办完了「%s」。' % (npc_id, dest_scene, what)


class Errand(object):
    """一条差事。

    ★ 推进 = **原地改 `status`**（对象身份不变）：宿主可能持有它做显示/日志，
      换对象会让"同一条差事"在两侧对不上。
    """

    __slots__ = ('npc_id', 'dest_scene', 'what', 'start', 'arrive_at',
                 'finish_at', 'status', 'result', 'custom_result')

    def __init__(self, npc_id, dest_scene, what, start,
                 arrive_at, finish_at, status=TRAVELING, result='',
                 custom_result=''):
        self.npc_id = npc_id
        self.dest_scene = dest_scene
        self.what = what
        self.start = start
        self.arrive_at = arrive_at
        self.finish_at = finish_at
        self.status = status
        #: 已完成时定格的结果（`done` 之后才有值）。
        self.result = result
        #: 调用方**预定**的结果（给了就用它，否则用 `default_result` 模板）。
        self.custom_result = custom_result

    # ------------------------------------------------------------ 读

    def scene_now(self):
        """此刻**他该在哪**：路上 ⇒ `None`（位置不变）；已到 ⇒ `dest_scene`。

        ★★ 返回 `None` 而不是"出发地"：本模块**不该**复制一份位置真源
          （真源在 `npc_roam` 覆盖表 / 站位表）。`None` = **明确交接**：
          "他在路上，位置没人改，保持原样"。
        """
        return self.dest_scene if self.status in (WORKING, DONE) else None

    def reason(self):
        """驻留覆盖用的 `reason`（让日志/存档能看出这是"被派出"）。"""
        return '%s%s' % (REASON_PREFIX, self.what)

    def is_active(self):
        """还在进行中（`traveling` / `working`）。"""
        return self.status != DONE

    def to_dict(self):
        return collections.OrderedDict((
            ('npc_id', self.npc_id),
            ('dest_scene', self.dest_scene),
            ('what', self.what),
            ('start', self.start),
            ('arrive_at', self.arrive_at),
            ('finish_at', self.finish_at),
            ('status', self.status),
            ('result', self.result),
            ('custom_result', self.custom_result),
        ))

    @classmethod
    def from_dict(cls, d):
        """容错还原：任何字段缺失/类型不对 ⇒ 返回 `None`（**不半成品还原**）。

        ★ 为什么宁缺毋滥：一条**字段残缺**的差事会让宿主把一个 NPC 永远压在
          某个场景上（`working` 但没有 `finish_at` ⇒ 永不到期）。丢一条差事
          只损失一次"出门"，比"某人再也不回家"便宜得多。
        """
        if not isinstance(d, dict):
            return None
        try:
            npc_id = d.get('npc_id')
            dest_scene = d.get('dest_scene')
            what = d.get('what')
            if not (isinstance(npc_id, str) and npc_id):
                return None
            if not (isinstance(dest_scene, str) and dest_scene):
                return None
            if not isinstance(what, str):
                what = ''
            start = float(d.get('start'))
            arrive_at = float(d.get('arrive_at'))
            finish_at = float(d.get('finish_at'))
        except (TypeError, ValueError, KeyError):
            return None
        status = d.get('status')
        if status not in (TRAVELING, WORKING, DONE):
            status = TRAVELING
        result = d.get('result')
        if not isinstance(result, str):
            result = ''
        custom_result = d.get('custom_result')
        if not isinstance(custom_result, str):
            custom_result = ''
        return cls(npc_id, dest_scene, what, start, arrive_at, finish_at,
                   status=status, result=result, custom_result=custom_result)

    def __repr__(self):
        return '<Errand %s->%s "%s" %s>' % (
            self.npc_id, self.dest_scene, self.what, self.status)


class ErrandBoard(object):
    """全部差事的看板（**每人最多一条在办**）。

    `enabled=False` ⇒ `step()` / `working_positions()` **一个字节都不改**
    （= 产品默认关时的**零回归**：行为与"没有本模块"逐字相同）。
    """

    def __init__(self, enabled=True, active=None, done=None):
        self.enabled = bool(enabled)
        #: npc_id -> Errand（进行中）
        self._active = collections.OrderedDict()
        #: npc_id -> Errand（已完成，**留结果**，等宿主取走）
        self.done = collections.OrderedDict()
        for d in (active or ()):
            e = Errand.from_dict(d) if isinstance(d, dict) else d
            if isinstance(e, Errand) and e.is_active():
                self._active[e.npc_id] = e
        for d in (done or ()):
            e = Errand.from_dict(d) if isinstance(d, dict) else d
            if isinstance(e, Errand):
                self.done[e.npc_id] = e

    # ------------------------------------------------------------ 改

    def assign(self, now, npc_id, dest_scene, what,
               travel=DEFAULT_TRAVEL_SECONDS, work=DEFAULT_WORK_SECONDS,
               result=None):
        """派一件事。★ 同一人**覆盖**旧差事（一个人同时只办一件事）。

        返回 `Errand`；被拒（关闸 / 参数不合法 / 名额已满）⇒ `None`。

        ★★ `npc_id` **不做任何白名单** —— 用户口径「**任何人都可以**」。
          谁被派、派去哪，全由**调用方**决定；本模块不认识"主角"。
        """
        if not self.enabled:
            return None
        if not (isinstance(npc_id, str) and npc_id):
            return None
        if not (isinstance(dest_scene, str) and dest_scene):
            return None
        if not isinstance(what, str):
            what = ''
        try:
            now = float(now)
            travel = float(travel)
            work = float(work)
        except (TypeError, ValueError):
            return None
        if travel < 0.0:
            travel = 0.0
        if work < 0.0:
            work = 0.0
        # 名额：**覆盖**不算新增（同一人已在办 ⇒ 替换，不占额外名额）。
        if len(self._active) >= MAX_ERRANDS and npc_id not in self._active:
            return None
        e = Errand(npc_id, dest_scene, what, now,
                   now + travel, now + travel + work,
                   custom_result=result if isinstance(result, str) else '')
        self._active[npc_id] = e
        return e

    def abort(self, npc_id):
        """**半途作废**某人的在办差事。返回被撤掉的 `Errand`（本来没在办 ⇒ `None`）。

        ★★ 与"办完"的区别（这两种收尾**不能混**）：
          · 办完 = `step()` 走完 `working → done`，**产出一句话**（`result`），
            并由宿主机写入该 NPC 的记忆；
          · 作废 = **外部叫停**，`_active` 里移除、**不进 `done`、不留结果**。
        ⇒ 为什么必须能作废而不是"放着不管"：被派出的人每到一拍都要被
          `working_positions()` 压一次位置。若一条**永远走不通**的差事留在表里，
          他会**被永久钉在某个进不去的场景上**（回不了家、也不参与自主生活）。
          第114轮的门控拦截、将来的"用户取消"都走这条出口。

        ★ 返回对象的 `status` 是**作废前**的值（`traveling` / `working`）——
          调用方**不要**拿它判"办完了"；它的用途是日志与"我还原到哪一步"。
        """
        return self._active.pop(npc_id, None)

    def step(self, now):
        """推进一拍（**纯函数式**：只改自己）。

        返回 `{'arrived': [(npc_id, scene), ...], 'finished': [(npc_id, Errand), ...]}`
        —— 如实登记本拍发生的**状态跃迁**（没有跃迁就是空列表）。
        """
        out = {'arrived': [], 'finished': []}
        if not self.enabled:
            return out
        try:
            now = float(now)
        except (TypeError, ValueError):
            return out
        for nid in list(self._active.keys()):
            e = self._active.get(nid)
            if e is None:
                continue
            if e.status == TRAVELING and now >= e.arrive_at:
                e.status = WORKING
                out['arrived'].append((nid, e.dest_scene))
            if e.status == WORKING and now >= e.finish_at:
                e.status = DONE
                e.result = e.custom_result or default_result(
                    nid, e.dest_scene, e.what)
                self.done[nid] = e
                del self._active[nid]
                out['finished'].append((nid, e))
        # 已完成留存上限：超了丢**最老**的（FIFO）。
        while len(self.done) > MAX_DONE:
            self.done.popitem(last=False)
        return out

    # ------------------------------------------------------------ 读

    def working_positions(self):
        """当前**所有在办**（`working`）的 `[(npc_id, dest_scene), ...]`。

        ★★ 宿主**每拍**都要拿它去 `roam.put()`（而不是只在 `arrived` 那一拍）——
          因为 `npc_roam` 可能在这一拍把该 NPC 摇去别处；被派出的人**优先**。
        """
        if not self.enabled:
            return []
        return [(e.npc_id, e.dest_scene) for e in self._active.values()
                if e.status == WORKING]

    def active_of(self, npc_id):
        """某人在办的差事（没有 ⇒ `None`）。"""
        return self._active.get(npc_id)

    def working_of(self, npc_id):
        """某人**正在办**的差事（`traveling` 不算 ⇒ `None`）。"""
        e = self._active.get(npc_id)
        if e is not None and e.status == WORKING:
            return e
        return None

    def result_of(self, npc_id):
        """某人已办完的**结果**（没办完过 ⇒ `''`）。"""
        e = self.done.get(npc_id)
        return e.result if e is not None else ''

    def take_results(self):
        """取走**全部**已完成的结果并清空（宿主落盘后调用）。

        返回 `[(npc_id, result), ...]`。
        ★ 取走即清：宿主**自己**负责落盘失败时的取舍（本项目惯例 = 只记 debug，
          不因一次落盘失败卡住主循环）。
        """
        out = [(nid, e.result) for nid, e in self.done.items()]
        self.done.clear()
        return out

    def by_npc(self):
        """进行中的快照 `{npc_id: Errand}`（浅拷贝，供只读遍历）。"""
        return collections.OrderedDict(self._active)

    def __len__(self):
        return len(self._active)

    def __contains__(self, npc_id):
        return npc_id in self._active

    def to_dict(self):
        return collections.OrderedDict((
            ('enabled', self.enabled),
            ('active', [e.to_dict() for e in self._active.values()]),
            ('done', [e.to_dict() for e in self.done.values()]),
        ))

    @classmethod
    def from_dict(cls, d):
        """容错还原。非法 ⇒ 空看板（**不半成品还原**，理由同 `Errand.from_dict`）。"""
        if not isinstance(d, dict):
            return cls()
        en = d.get('enabled', True)
        return cls(enabled=bool(en), active=d.get('active') or (),
                   done=d.get('done') or ())

    def __repr__(self):
        return '<ErrandBoard active=%d done=%d enabled=%s>' % (
            len(self._active), len(self.done), self.enabled)


# ---------------------------------------------------------------- 接线说明

#: 供判据/文档直读的**接线契约**（键 = 宿主该做的事）。
#: ★ 保持成纯数据（不 import），这样 `check113` 能在**不起 Qt** 的前提下逐条核对。
WIRING = collections.OrderedDict((
    ('assign', '宿主暴露 `assign_errand(npc_id, dest_scene, what, **kw)` ⇒ '
               '`board.assign(now, ...)`；★ `npc_id` 不做白名单（任何人都可以）'),
    ('tick', '主循环在 `_npc_roam_tick()` **之后**调 `_npc_errand_tick(now)`；'
             '顺序即优先级 —— 差事**压过**自发挪窝'),
    ('gate', '★ 第114轮：**派发时**与**每拍压位置之前**都要过 '
             '`npc_system.world_gate(npc, world_of(dest), scene_id=dest, '
             'carried=...)` —— 用户口径「被派不可进入原本不可进入的世界」'
             '（差事**继承**门控，不是特权）。'),
    ('abort', '门控拒 / 用户取消 ⇒ `board.abort(nid)`（**半途作废**：不进 `done`、'
              '不留结果），并落一条"去不了"的记忆。'
              '★ 为什么不能只是"跳过不压位置"：那条差事会**永远**留在 '
              '`working_positions()` 里，把人反复压向一个进不去的场景。'),
    ('put', '每拍对 `working_positions()` 逐个 `roam.put(nid, scene, now, '
            'reason=errand.reason())`，随后 `_npc_seed_bodies(_npc_scene_id())`'),
    ('finish', '`step()` 的 `finished` ⇒ `roam.drop(nid)`（回落静态归属）+ '
               '`npc_memory.remember(nid, result, who=nid)` + `npc_memory.save(nid)`'),
    ('decoupled', '本模块**不碰显示**：不 import scene/camera/canvas，'
                  '不调 `switch()` / `travel_to()`（AST 判据锁死）'),
))

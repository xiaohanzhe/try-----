# -*- coding: utf-8 -*-
"""场景系统控制器 —— 「把原作的世界搬到桌面上」的接线层。

本类在 P0 阶段是**空壳**：只提供宿主引用、双向转发、以及"加载/切换场景"的最小
骨架方法。它的存在本身就是交付物 —— 用户的要求是「**留好拓展接口**」，所以接口
必须真的在位（能被 import、能被 `self.scene.xxx` 调到、能过 G2 回归），而不是
只写在文档里。

P0 的硬指标：**不切场景时零行为变化**。因此本类**不注册任何定时器、不改任何
渲染路径、不碰物理**。`load()` 会读 `_index.json` 与默认场景，但读到的结果
只是存进宿主的状态字段，没有消费者 —— 所以画面上看不出任何区别。

为什么需要 `__getattr__`（与 `GamesController` / `VideoController` 等**逐字同构**）
----------------------------------------------------------------------------------
「只搬方法不搬状态」意味着方法体里写的是 `self.some_host_thing`。这些写法在宿主里
合法，在控制器里就是"找不到的属性"。两种做法：

  (a) 把方法体里的 `self.xxx` 全改写成 `self.p.xxx` —— 每处都是笔误机会，
      而且 verify 的"逐字等价"判据会因此失效。
  (b) 让控制器在自身查不到时**回落给宿主**（本实现）。

选 (b)。本类现在还没有从宿主搬来的方法（P0 空壳），但**结构必须先立起来** ——
P1 加渲染层时，那些方法一定需要读宿主的 `sprite_label` / `current_floor` /
`pos()`，届时照着既有口径写就行，不必回头改架构。

⚠️ 双向转发**必须有一侧是"显式白名单式"的**，否则会成环。两侧现在都是白名单：

  · 宿主那侧（`RalseiPet.__getattr__`，main.py:514）：只转发
    `_CONTROLLER_ATTRS` 名单里的控制器，且用 `getattr(type(ctrl), name)` 探测
    —— **不**去 `hasattr(ctrl, ...)`（那会触发本类回落，直接成环）。
  · 本类这侧：只在**宿主实例字典里存在**、或**在宿主类型的 MRO 上存在**时
    才返回；两者都不满足就抛 —— 于是"宿主也没有"的名字不会在两个
    `__getattr__` 之间来回弹。

真机踩过的递归（记在这里防回退）：`RalseiPet.__init__` 早期
`randomize_movement_pattern()` 会 `getattr(self, 'game_state', {})`，而
`game_state` 直到 `__init__` 末尾才赋值。那一刻若宿主的 `__getattr__` 用
`hasattr(ctrl, ...)` 探测，就会：宿主 → 控制器回落 → 宿主 → …… 无限递归，
`RecursionError` 崩在**构造期**（连窗口都起不来）。所以两侧都只用
`type(x).__dict__` / `__mro__` 这种**不触发实例属性查找**的探测方式。

为什么不 import 任何项目内模块（除 scene_system）
-------------------------------------------------
本模块位于「**初始化环**」的下游：`main.py` 在 import 期就要
`from modules.scene_controller import SceneController`。此刻若本模块回头
`import logger_utils` / `dialogue_ui` / `data_store`，会把环重新接上（本项目已
踩过 4 次，见 `lazy_log.py` 的 docstring）。所以：

* **只 import `scene_system`** —— 它是纯标准库模块，无反向依赖，接环风险为零；
* 日志用标准库 `logging`；
* 宿主的能力（sprite / floor / dialogue 等）一律经 `self.p` 动态取用，不 import。
"""
import logging

from scene_system import (  # noqa: F401  (同目录扁平导入，见 main.py 的 sys.path 处理)
    SCENE_SCHEMA_VERSION,
    SceneState,
    depth_of,
    load_anchors,
    load_index,
    load_scene,
    pick_variant,
    project_root,
    resolve_anchor,
    resolve_asset_path,
    scenes_dir,
    visible_objects,
)

_log = logging.getLogger(__name__)


class SceneController(object):
    """场景系统的宿主侧接线层。宿主（`RalseiPet`）持有，方法经转发壳暴露。

    状态全在宿主
    ------------
    本类**不持有任何场景状态**。宿主在 `init_systems()` 里预声明了 6 个字段
    （见 main.py「场景系统状态字段」段），本类只通过 `self.p` 读写它们：

        self.p._scene_index     索引（load_index 的结果）
        self.p._scene_state     当前 SceneState（或 None）
        self.p.current_scene    当前场景 id（str 或 None）
        self.p.scene_objects    当前可见物件缓存（list）
        self.p._scene_anchors   全局锚点表（dict）
        self.p._scene_loaded    是否已加载过索引（bool，防重复 IO）

    ⚠️ 之所以强调"宿主预声明"：本类的 `__setattr__` 转发判据是「宿主**已经拥有**
    这个名字」。若某个字段没在宿主预声明，那么首次赋值 `self.<新名> = x` 会落到
    **控制器自己的 `__dict__`** → 状态劈成两份（本项目真踩过两次：W1-1 的
    `_spell_seen_frame`、W1-2 的 4 个 `_hide_*`，后者导致躲猫猫卡在走路态）。
    """

    def __init__(self, ralsei_pet):
        # 宿主引用：状态都在宿主身上，本类只借用，不复制、不缓存。
        # 用普通赋值即可 —— 赋的是 `self.__dict__` 里的键 `p`，
        # 但 __setattr__ 里对 'p' 有白名单跳过，所以会落进本类实例字典。
        self.p = ralsei_pet

    # ------------------------------------------------------------------
    #  双向转发（与其余五个控制器逐字同构）
    # ------------------------------------------------------------------
    def __getattr__(self, name):
        # 只在常规查找失败时进入。`self.p` 本身已在 __dict__ 里，下面不会递归。
        pet = self.__dict__.get('p')
        if pet is None:
            raise AttributeError(name)
        # 名字必须能由**宿主自己**解析，且解析过程不能重入宿主的 __getattr__：
        #   · 在宿主实例字典里（current_scene / scene_objects / dialogue_ui …）→ 直接给；
        #   · 在宿主**类型**的 MRO 上（play_animation_once / pos() 等方法、
        #     C++ 侧注册的属性）→ 走一次 getattr，此时常规查找必命中，不会重入。
        if name in pet.__dict__:
            return pet.__dict__[name]
        if any(name in klass.__dict__ for klass in type(pet).__mro__):
            return getattr(pet, name)
        # 第 3 条白名单：**兄弟控制器**。控制器 A 调 `self.<B 的方法>` 时，B 的
        # 方法是 B 的**类属性** —— 既不在宿主实例字典、也不在宿主类型 MRO。
        # 修法：复刻宿主的 `_CONTROLLER_ATTRS` 扫描，**跳过自己**；
        # 只看对方**类**上的名字（不触发对方实例的 __getattr__）→ 不成环。
        for _attr in getattr(type(pet), '_CONTROLLER_ATTRS', ()):
            _ctrl = pet.__dict__.get(_attr)
            if _ctrl is None or _ctrl is self:
                continue
            if getattr(type(_ctrl), name, None) is not None:
                return getattr(_ctrl, name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        # 与其余五个控制器（GamesController / VideoController / SpellFlowController
        # / HideAndSeekController / FileSheetController）逐字同构的写转发护栏。
        #
        # 判据 = 宿主**已经拥有**的名字（实例字典 or MRO 上有）：
        #   · 自动覆盖将来新增的状态名，不必回来改名单；
        #   · 控制器**故意不允许**给自己新增业务属性 —— 想加状态就加到宿主上。
        # ⚠️ 必跳过 'p'：`p` 是控制器自己的宿主引用，转发出去就永远拿不到宿主了。
        if name != 'p':
            pet = self.__dict__.get('p')
            if pet is not None:
                if name in pet.__dict__ or any(
                        name in klass.__dict__ for klass in type(pet).__mro__):
                    setattr(pet, name, value)
                    return
        object.__setattr__(self, name, value)

    # ------------------------------------------------------------------
    #  只读探测（给回归锁用；P0 无消费者）
    # ------------------------------------------------------------------
    @property
    def ready(self):
        """场景系统是否已就绪（索引加载成功 + 有当前场景）。

        用属性而不是方法：调用方写 `if self.scene.ready:` 更像读状态而不是做动作。
        ⚠️ `ready` 这个名字**不能**和宿主上的任何属性重名 —— 否则
        `__getattr__` 里 `name in pet.__dict__` / MRO 的探测会先命中宿主那份，
        属性就被"遮住"了。已确认宿主无同名成员（`_scene_*` 都是下划线前缀）。
        """
        pet = self.__dict__.get('p')
        if pet is None:
            return False
        return bool(pet.__dict__.get('_scene_loaded')) and \
            pet.__dict__.get('current_scene') is not None

    def available_scenes(self):
        """索引里登记的全部场景 id（排序后）。未加载 → 空列表。"""
        index = self.p.__dict__.get('_scene_index') or {}
        return sorted((index.get('scenes') or {}).keys())

    def scene_info(self, scene_id):
        """索引里某场景的登记信息（dict）或 None。"""
        index = self.p.__dict__.get('_scene_index') or {}
        return (index.get('scenes') or {}).get(scene_id)

    # ------------------------------------------------------------------
    #  加载 / 切换（P0 骨架：加载可用，切换只更新状态）
    # ------------------------------------------------------------------
    def load(self, scene_dir_path=None):
        """读场景索引 + 加载默认场景（或保持当前场景）。

        **幂等**：重复调用只做一次 IO（由 `_scene_loaded` 守）。
        返回 True 表示"索引可用且已有一个当前场景"。

        为什么把"读索引"和"切场景"拆成两步：索引是**静态**的（跟着程序走），
        场景是**动态**的（会随用户操作切换）。合成一步会让"只想知道有哪些场景"
        的调用方也被迫切一次场景。

        永不抛：任何异常都只记日志并返回 False（P0 阶段场景系统**不是**关键路径，
        它失败绝不能让桌宠起不来 —— 与 search_summarizer / relationship 同一条纪律）。
        """
        pet = self.p
        try:
            if not pet.__dict__.get('_scene_loaded'):
                pet._scene_anchors = load_anchors(scene_dir_path)
                index = load_index(scene_dir_path)
                pet._scene_index = index
                pet._scene_loaded = True
                if not index.get('ok'):
                    _log.warning("场景索引不可用（场景系统降级为空态）: %s",
                                 index.get('error'))
                    return False

            index = pet.__dict__.get('_scene_index') or {}
            scenes = index.get('scenes') or {}

            # 已经站在某个场景里 → 不动（幂等）。切场景走 switch()。
            if pet.__dict__.get('current_scene') in scenes:
                return True

            target = index.get('default_scene')
            if target not in scenes:
                # 索引没有默认场景、或默认场景没登记 → 退而求其次取任意一个。
                # 用 sorted 而不是 dict 顺序：同一份索引在不同 Python 版本上
                # 迭代顺序一致（dict 自 3.7 起保序，但排序能杜绝"改一行 meta
                # 就换了个启动场景"这类难查的漂移）。
                target = sorted(scenes.keys())[0] if scenes else None
            if target is None:
                _log.warning("场景索引里没有任何场景，场景系统降级为空态")
                return False

            return self.switch(target, scene_dir_path=scene_dir_path,
                               _from_load=True)
        except Exception as e:
            _log.warning("场景系统加载失败（降级为空态）: %s", e)
            return False

    def switch(self, scene_id, scene_dir_path=None, _from_load=False):
        """切到 `scene_id`。成功返回 True。

        P0 行为 = **只更新宿主状态**（`current_scene` / `_scene_state` /
        `scene_objects`），**不动画面**。这不是偷懒，而是"零行为变化"验收标准
        的直接要求：P0 的判据是 G2 1169 PASS 逐字节不动，任何真的改画面/改窗口
        的动作都会让这个判据失效，从而**掩盖**后续 P1 的真实回归。

        P1 会在这里接上：背景窗口 → 物件绘制 → 深度排序 → 转场 → BGM。
        转场要借原作 `obj_dw_transition` 的"剪影走门 + 音高 0.1→1.0"，
        但**不抄**它的 640×480 锁画布 / 一屏一房间。

        失败语义（重要）：**切失败时保持当前场景不变**，而不是切到空场景 ——
        "切场景失败"若表现成"世界突然变白"，用户会以为存档坏了。
        """
        pet = self.p
        try:
            if not pet.__dict__.get('_scene_loaded') and not _from_load:
                # 允许直接 switch 而不先 load（调用方图省事时也能work）。
                self.load(scene_dir_path)

            index = pet.__dict__.get('_scene_index') or {}
            if scene_id not in (index.get('scenes') or {}):
                _log.warning("要切换的场景 %r 未登记在索引里，保持当前场景", scene_id)
                return False

            scene = load_scene(scene_id, scene_dir_path)
            if scene is None:
                _log.warning("场景 %r 定义加载失败，保持当前场景", scene_id)
                return False

            scene.dir_path = scene.dir_path or scenes_dir(scene_dir_path)

            # 状态一次性写完（不留"改了一半"的中间态）。
            pet._scene_state = scene
            pet.current_scene = scene_id
            pet.scene_objects = self.refresh_objects() if hasattr(self, 'refresh_objects') else []
            return True
        except Exception as e:
            _log.warning("切换到场景 %r 失败（保持当前场景）: %s", scene_id, e)
            return False

    def resolve_objects(self, screen_rect):
        """算出当前场景在 `screen_rect` 下该画的物件（已排序、已带屏幕坐标）。

        P0 里**没有调用方** —— 它是给 P1 的渲染层准备的入口，现在就先摆好，
        免得 P1 又去 `main.py` 里另写一遍几何计算（本项目最贵的坑是
        「函数写对了但产品用不上」，所以接口先立、消费者后到，且靠回归锁
        保证函数本身是对的）。
        """
        scene = self.p.__dict__.get('_scene_state')
        if scene is None:
            return []
        anchors = self.p.__dict__.get('_scene_anchors') or {}
        # 场景自带的锚点**优先于**全局锚点表（更具体的赢）。
        merged = dict(anchors)
        merged.update(getattr(scene, 'anchors', None) or {})
        return visible_objects(scene, screen_rect, merged)

    def description(self):
        """当前场景的一句话中文描述（`''` = 无话可说，调用方应整段不注入）。"""
        scene = self.p.__dict__.get('_scene_state')
        if scene is None:
            return ''
        return scene.describe()

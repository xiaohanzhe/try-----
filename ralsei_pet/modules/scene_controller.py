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
import json
import logging
import os

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
import scene_routing  # 同为纯标准库模块，接环风险为零（见 scene_routing 的零依赖纪律）
import scene_camera   # 同上：纯标准库，无反向依赖（第44轮相机）
import scene_render   # 同上：纯标准库（第44轮渲染层 —— 只出"绘制指令"，不画）
import scene_pathfind  # 同上：纯标准库（第45轮自主寻路 —— 语境→目的地→路径）

_log = logging.getLogger(__name__)


class SceneController(object):
    """场景系统的宿主侧接线层。宿主（`RalseiPet`）持有，方法经转发壳暴露。

    状态全在宿主
    ------------
    本类**不持有任何场景状态**。宿主在 `init_systems()` 里预声明了 **9** 个字段
    （**6 个场景 + 3 个路由 + 4 个寻路**，见 main.py「场景系统 状态字段」段），本类只通过
    `self.p` 读写它们：

        self.p._scene_index         索引（load_index 的结果）
        self.p._scene_state         当前 SceneState（或 None）
        self.p.current_scene        当前场景 id（str 或 None）
        self.p.scene_objects        当前可见物件缓存（list；由 resolve_objects 填）
        self.p._scene_anchors       全局锚点表（dict）
        self.p._scene_loaded        是否已加载过索引（bool，防重复 IO）
        self.p._scene_routes        路由表（load_routes 的结果）
        self.p._routes_loaded       路由表是否已加载过（bool，幂等守卫）
        self.p._scene_route_reason  最近一次路由命中的理由（str）
        self.p._scene_aliases       ★第45轮 目的地别名表（load_aliases 的结果）
        self.p._scene_room_graph    ★第45轮 原作房间图（load_room_graph 的结果）
        self.p._pathfind_loaded     ★第45轮 寻路数据是否已加载（bool，幂等守卫）
        self.p._scene_chapter_id    ★第45轮 当前章 id（消歧用；从 SceneState 投影）

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

    # ------------------------------------------------------------------
    #  相机（第44轮）
    # ------------------------------------------------------------------
    def init_camera(self, camera_size=None, border=None, scale=None):
        """建相机实例 + 从宿主读放大系数。**幂等**、**永不抛**。

        用户对操控的裁定：「人物走到中间后一直居中然后背景相对运动」
        ⇒ 用 `scene_camera.Camera`（居中式跟随，非视差）。

        为什么单独一个方法而不是塞进 `load()`：`load()` 是 P0 契约
        （「不切场景时零行为变化」），相机虽然也不注册定时器，
        但它是**渲染层的前置件**，放在独立方法里更容易在回归里单独断言
        "它到底有没有被调用"（防"模块写了没人用"复演 —— 本项目最贵的坑）。

        **不注册定时器、不改渲染路径、不调任何 Qt API** —— 与 P0 同一条纪律。
        """
        pet = self.p
        try:
            cam = pet.__dict__.get('_scene_camera')
            if cam is None:
                if camera_size is None:
                    camera_size = scene_camera.DEFAULT_CAMERA_SIZE
                if border is None:
                    border = scene_camera.DEFAULT_BORDER
                if scale is None:
                    scale = pet.__dict__.get('scene_scale', 1.0)
                cam = scene_camera.Camera(camera_size, border, scale)
                pet._scene_camera = cam
            else:
                # 已存在 → 只同步一次可能被外部改过的 scale（幂等）
                if scale is not None:
                    cam.set_scale(scale)
            pet.camera_rect = cam.rect
            return cam
        except Exception as e:
            _log.warning("相机初始化失败（渲染层降级为无相机）: %s", e)
            return None

    def camera_follow(self, room_rect, target_rect):
        """让相机跟随目标并写回 `pet.camera_rect`。没相机 → `None`（不伪装）。

        P1 渲染层每帧调它；P0 期零消费者。
        """
        pet = self.p
        cam = pet.__dict__.get('_scene_camera')
        if cam is None:
            return None
        try:
            rect = cam.follow(room_rect, target_rect)
            pet.camera_rect = rect
            return rect
        except Exception as e:
            _log.warning("相机跟随失败: %s", e)
            return None

    # ------------------------------------------------------------------
    #  渲染层（第44轮 P1）—— 只出"绘制指令"，一笔都不画
    # ------------------------------------------------------------------
    def load_geometry(self, scene_dir_path=None):
        """读 `_room_geometry.json` → 房间世界几何表。**幂等**、**永不抛**。

        为什么独立于 `load()`：房间几何是**渲染层专属数据**（相机钳制/背景铺排/
        物件裁剪）。索引（`load()`）失败 = 没有场景可去；几何失败 = 场景都在、
        只是"房间多大不知道"，渲染退化为"一屏一房间"。两者的失败面不重叠，
        合在一起会让后者拖垮前者。

        返回 `{rooms: {...}, error: str|None}` 形状（与 `load_index` 同一约定：
        **永远返回同一种 dict**，调用方不必防 None）。
        """
        pet = self.p
        result = {'rooms': {}, 'error': None}
        try:
            if not pet.__dict__.get('_geometry_loaded'):
                path = os.path.join(scene_dir_path or scenes_dir(), '_room_geometry.json')
                raw = None
                try:
                    with open(path, 'r', encoding='utf-8') as fh:
                        raw = json.load(fh)
                except Exception:
                    raw = None
                if isinstance(raw, dict) and isinstance(raw.get('rooms'), dict):
                    rooms = {}
                    for k, v in raw['rooms'].items():
                        if isinstance(v, dict) and isinstance(v.get('w'), int) \
                                and isinstance(v.get('h'), int):
                            rooms[k] = v
                    result['rooms'] = rooms
                else:
                    result['error'] = '_room_geometry.json 不存在或格式不符'
                    _log.warning("房间几何表不可用（渲染退化为'一屏一房间'）: %s",
                                 result['error'])
                pet._scene_geometry = result['rooms']
                pet._geometry_loaded = True
            else:
                result['rooms'] = pet.__dict__.get('_scene_geometry') or {}
            return result
        except Exception as e:
            _log.warning("房间几何表加载失败（渲染退化）: %s", e)
            result['error'] = str(e)
            return result

    def plan_frame(self, tick=0, sprite_size=None):
        """产出这一帧的绘制指令清单（**纯数据**，由 Qt 壳去画）。

        返回 `[]` 的四种情况（都**不是错误**，是"这一刻没东西可画"）：
        场景未加载 / 相机未 follow / 几何表读不到（此时相机退化为视口大小，
        仍会画占位）/ `scene_render.plan_frame` 内部判定无交集。

        ⚠️ **不在这里调 Qt**：本方法只算几何。真正的 `QPainter` 调用在
        `main.py` 的绘制壳里 —— 这样本方法能被回归锁逐条断言（第 44 轮
        实测离屏渲染在沙箱里不稳定，所以"能断言计划"比"能截屏"更可靠）。
        """
        pet = self.p
        scene = pet.__dict__.get('_scene_state')
        cam = pet.__dict__.get('_scene_camera')
        geo = pet.__dict__.get('_scene_geometry') or {}
        try:
            return scene_render.plan_frame(scene, cam, geo, tick=tick,
                                          sprite_size=sprite_size)
        except Exception as e:
            _log.warning("渲染计划生成失败（本帧不画）: %s", e)
            return []

    def plan_viewport(self):
        """这一帧的**画布像素尺寸** `(w, h)` —— Qt 壳按它 `resize()` 自身。

        与 `plan_frame()` 分开（不是它的一部分）：画布尺寸是**容器属性**，
        指令是**内容**。分开的两个好处：
          · `render_summary()` 的计数不会把画布算成一条指令（否则回归锁要写特例）；
          · "尺寸算错"和"内容算错"在回归里可分别断言。

        收缩语义见 `scene_render.viewport_size()`：小房间收缩到房间像素、
        大房间用相机像素（两轴独立）。
        """
        pet = self.p
        scene = pet.__dict__.get('_scene_state')
        cam = pet.__dict__.get('_scene_camera')
        geo = pet.__dict__.get('_scene_geometry') or {}
        try:
            return scene_render.plan_viewport(scene, cam, geo)
        except Exception as e:
            _log.warning("画布尺寸计算失败（退化为相机尺寸）: %s", e)
            if cam is not None:
                return (int(cam.size[0]), int(cam.size[1]))
            return (0, 0)

    def render_summary(self, tick=0):
        """当前帧绘制计划的一行中文摘要（自省/日志用）。"""
        return scene_render.plan_summary(self.plan_frame(tick=tick))

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
            scenes = index.get('scenes') or {}
            if scene_id not in scenes:
                _log.warning("要切换的场景 %r 未登记在索引里，保持当前场景", scene_id)
                return False

            # ★ 把**登记行**一起交给数据层：场景数据有两个来源（独立文件 / 区域分片），
            #   数据层要靠 entry 里的 chapter_id/area_id 才知道去读哪一片。
            #   不给它的话，926 个"住在分片里"的场景会全部加载失败。
            scene = load_scene(scene_id, scene_dir_path, entry=scenes.get(scene_id))
            if scene is None:
                _log.warning("场景 %r 定义加载失败，保持当前场景", scene_id)
                return False

            scene.dir_path = scene.dir_path or scenes_dir(scene_dir_path)

            # 状态一次性写完（不留"改了一半"的中间态）。
            pet._scene_state = scene
            pet.current_scene = scene_id
            # ★第45轮：把当前**章**也投影成宿主状态 —— 寻路的②（目的地定位）
            #   要拿它消歧（"去医院"时人在 ch1，绝不该被送到 ch5 的花园医院）。
            #   从 SceneState 取（它有 chapter_id），取不到给 None（不伪造）。
            _ch = getattr(scene, 'chapter_id', None)
            pet._scene_chapter_id = _ch if isinstance(_ch, str) and _ch else None
            # `scene_objects` = "当前可见物件缓存"。**这里不能现算** —— 算它必须有
            # screen_rect（入口是 `resolve_objects(screen_rect)`），而切场景时拿不到。
            # ⇒ 显式清空，避免把上一个场景的物件残影留给渲染层。
            # ⚠️ 旧写法是 `self.refresh_objects() if hasattr(self, 'refresh_objects') else []`：
            #    `refresh_objects` **全仓没有任何定义** ⇒ `hasattr` 恒假 ⇒ 永远走 `[]`
            #    —— 形如"在刷新"，实则空转（第 38 轮复检删除）。
            #    P1 的渲染层请直接调 `resolve_objects(screen_rect)` 来填这个字段。
            pet.scene_objects = []
            # ★ 第48轮：切场景后**通知宿主的钩子**（道具域切换 / 可交互物重建）。
            #   为什么不在这里直接调道具系统：本文件的 import 面被
            #   `verify_scene_p0` 的 A6 白名单锁着（只准标准库 + 零依赖数据层），
            #   加一个业务 import 会把那条闸打红。所以走**鸭子类型的回调**：
            #   宿主往 `_scene_switch_hooks` 里塞函数，本方法只负责叫它们。
            #   ⚠️ 宿主没挂钩子时（列表为空）这里是**零行为** —— 这是刻意的：
            #      P0 的"不切场景时零行为变化"判据不能被这行破坏。
            self._fire_switch_hooks(scene_id, scene)
            return True
        except Exception as e:
            _log.warning("切换到场景 %r 失败（保持当前场景）: %s", scene_id, e)
            return False

    def _fire_switch_hooks(self, scene_id, scene):
        """把"切完了"这件事通知宿主。**任何钩子抛异常都不许影响切换结果**。

        钩子签名：`hook(scene_id, scene)`；返回值忽略（只看副作用）。
        逐个 try 是为了"一个钩子坏掉不影响其它钩子"——本项目多次踩过
        "一个可选组件把主路径拖垮"。
        """
        hooks = self.p.__dict__.get('_scene_switch_hooks') or ()
        for hook in list(hooks):
            try:
                hook(scene_id, scene)
            except Exception:
                _log.exception('场景切换钩子 %r 抛异常（已吞掉，切换本身已成功）', hook)

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

    # ------------------------------------------------------------------
    #  路由（"什么语境下去哪"）—— 数据在 assets/scenes/_routes.json
    # ------------------------------------------------------------------
    def load_routes(self, scene_dir_path=None):
        """读路由表（**幂等**，由 `_routes_loaded` 守）。返回 True 表示可用。

        与 `load()` 分开是因为两者的失败**互不影响**：索引没读上 = 没有任何
        场景可去（整个场景系统降级）；路由表没读上 = 场景都在、只是"没有
        自动走的理由"（用户手动切场景照常可用）。合成一个会让后者拖垮前者。
        """
        pet = self.p
        try:
            if not pet.__dict__.get('_routes_loaded'):
                routes = scene_routing.load_routes(scene_dir_path)
                pet._scene_routes = routes
                pet._routes_loaded = True
                if not routes.get('ok'):
                    _log.warning("路由表不可用（自动换场景降级为不换）: %s",
                                 routes.get('error'))
                    return False
            return bool((pet.__dict__.get('_scene_routes') or {}).get('ok'))
        except Exception as e:
            _log.warning("路由表加载失败（自动换场景降级为不换）: %s", e)
            return False

    def context_snapshot(self, extra=None):
        """打包**当前语境**，交给 `scene_routing.match()` 判定该不该换场景。

        这是"路由层"与"宿主"之间**唯一**的数据接口 —— 路由模块不认识桌宠，
        它只吃这个 dict（见 `scene_routing._match_one` 认的键）。

        已填的键：

          · `scene_id` / `area_id` / `chapter_id` —— 从当前 SceneState 取
            （没有当前场景时一律 `None`，规则里写 `when_scene` 就不会命中）。
          · `mood` —— 宠物心情。**从 `emotion_system` 投影**，取不到就是
            `None`（**不伪造一个 'neutral'** —— 那会让"我不知道心情"静默地
            匹配上 `when_mood: neutral` 的规则，是设计律 1 的变体）。
          · `keywords` —— 语境关键词集合。**取不到就是空集合**，同理。

        `extra` 里的键**覆盖**上面推导出来的值（调用方明确知道语境时以它为准）。

        ⚠️ 全部字段都做了"取不到给 None"处理，**本方法永不抛**：路由是锦上添花，
        它失败绝不能让对话/移动这些主路径崩掉。
        """
        ctx = {
            'scene_id': None,
            'area_id': None,
            'chapter_id': None,
            'mood': None,
            'event': None,
            'keywords': set(),
        }
        try:
            scene = self.p.__dict__.get('_scene_state')
            if scene is not None:
                ctx['scene_id'] = getattr(scene, 'scene_id', None)
                ctx['area_id'] = getattr(scene, 'area_id', None)
                ctx['chapter_id'] = getattr(scene, 'chapter_id', None)

            # 心情：emotion_system 的 API 面在不同轮次有变动，这里用**鸭子类型**
            # 探测（有 current_mood 属性或 get_mood() 方法都接受），探测不到就
            # 保持 None —— 不去猜、不去造。
            emo = self.p.__dict__.get('emotion_system')
            if emo is not None:
                mood = getattr(emo, 'current_mood', None)
                if mood is None:
                    getter = getattr(emo, 'get_mood', None)
                    if callable(getter):
                        try:
                            mood = getter()
                        except Exception:
                            mood = None
                if isinstance(mood, str) and mood:
                    ctx['mood'] = mood
        except Exception as e:
            _log.debug("语境打包（读取场景/心情）失败，用默认空语境: %s", e)

        if isinstance(extra, dict):
            for key, value in extra.items():
                if value is not None:
                    ctx[key] = value
        return ctx

    def pick_route(self, extra=None, scene_dir_path=None):
        """判定**当前语境该走哪条路**。返回命中的 route（dict）或 `None`。

        返回 `None` = 「没有任何理由换场景」—— 调用方应原地不动，
        **不要**拿它去 switch（`switch(None)` 会失败并把日志刷满 warning）。

        P0 阶段本方法**没有自动调用方**（不注册定时器、不在事件里挂钩），
        这是"零行为变化"验收的要求。P1 才由 ai_driver / 事件链路调用它。
        """
        try:
            if not self.load_routes(scene_dir_path):
                return None
            routes = self.p.__dict__.get('_scene_routes') or {}
            return scene_routing.match(routes, self.context_snapshot(extra))
        except Exception as e:
            _log.warning("路由判定失败（不换场景）: %s", e)
            return None

    def follow_route(self, extra=None, scene_dir_path=None):
        """判定 + 执行：有路走就切过去。返回切过去的 `scene_id` 或 `None`。

        语义（重要）：**已经站在目标场景里时返回 None**。否则每次调用都会
        "切到自己"，日志被刷满、且 P1 接上转场动画后会**原地重播转场**。
        这个判断放在这里而不是 `switch()` 里 —— `switch()` 显式切到当前场景
        应该仍然算一次调用（用户点 UI 里"回到桌面"时转场该播）。

        目标场景**未登记**时（比如路由表写了 but _index 里没有）→ 保持原地，
        返回 None 并把原因记进日志。切到一个不存在的场景会走 `switch()` 的
        失败分支，那里会 warning，但调用方拿到的是 False、看不出"是路由表写错
        了还是场景文件坏了"——所以这里先自己筛一道。
        """
        route = self.pick_route(extra, scene_dir_path)
        target = scene_routing.route_target(route)
        if not target:
            return None
        if target == self.p.__dict__.get('current_scene'):
            return None
        index = self.p.__dict__.get('_scene_index') or {}
        if target not in (index.get('scenes') or {}):
            _log.warning("路由指向的场景 %r 未登记在索引里（保持当前场景）", target)
            return None
        # 理由暂存进宿主：P1 的 AI 注入与转场文案都要用它（见 scene_routing
        # 的 route_reason 文档）。P0 没有消费者，但**先落状态**，免得 P1 又
        # 回头改这里（"函数写对了但产品用不上"的反面：先把数据备好）。
        self.p._scene_route_reason = scene_routing.route_reason(route)
        return target if self.switch(target, scene_dir_path) else None

    def destinations(self):
        """当前**可达**的场景清单（已过滤掉未登记的）。给 AI 的"我能去哪"。"""
        try:
            if not self.load_routes():
                return []
            routes = self.p.__dict__.get('_scene_routes') or {}
            return scene_routing.destinations(
                routes, self.p.__dict__.get('_scene_index'))
        except Exception as e:
            _log.warning("可达场景枚举失败: %s", e)
            return []

    def destinations_text(self):
        """可达场景的中文清单（`''` = 没有 → 调用方应**整段不注入**）。"""
        try:
            if not self.load_routes():
                return ''
            routes = self.p.__dict__.get('_scene_routes') or {}
            return scene_routing.describe_destinations(
                routes, self.p.__dict__.get('_scene_index'))
        except Exception as e:
            _log.warning("可达场景描述生成失败: %s", e)
            return ''

    # -----------------------------------------------------------------
    #  第45轮 · 自主寻路（"语境说去教堂 → 自己走过去"）
    #
    #  ★ 这三个方法**全部只读**：加载数据 + 算计划，**不 switch、不起定时器**。
    #    与第 38 轮路由层"零行为变化"是同一条纪律 —— 计划算出来了，
    #    但"要不要真的走"由 P1 的 AI 决策链决定（用户口径见第45轮报告 §6）。
    # -----------------------------------------------------------------

    def load_pathfind_data(self, scene_dir_path=None):
        """加载寻路所需的三份数据（别名表 / 房间图）。**幂等**，返回是否可用。

        ⚠️ 为什么单独一个方法而不是塞进 `load_routes()`：三份数据用途不同、
        失败后果也不同 —— 别名表缺失只让 ② 退化（纯场景名匹配），
        房间图缺失只让 ③ 退化（只能走一步）。**分开加载 = 分开降级**。
        """
        pet = self.p
        try:
            if not pet.__dict__.get('_pathfind_loaded'):
                pet._scene_aliases = scene_pathfind.load_aliases(scene_dir_path)
                pet._scene_room_graph = scene_pathfind.load_room_graph()
                pet._pathfind_loaded = True
                if not pet._scene_aliases.get('ok'):
                    _log.info("别名表不可用（目的地匹配退化为纯场景名）: %s",
                              pet._scene_aliases.get('error'))
                if not pet._scene_room_graph.get('ok'):
                    _log.info("房间图不可用（多跳寻路退化为直连）: %s",
                              pet._scene_room_graph.get('error'))
        except Exception as e:
            _log.warning("寻路数据加载失败（寻路不可用）: %s", e)
            return False
        return bool(pet.__dict__.get('_scene_room_graph', {}).get('ok'))

    def resolve_destination(self, target):
        """② 语义定位：把『教堂』这类词翻成一个/一组场景（**只读**）。

        返回 `scene_pathfind.resolve_target()` 的结果。多解时 `ambiguous=True`
        且 `scene_id=None` —— 调用方（或 AI）需要自己选（**不替用户决定**）。
        """
        try:
            if not self.load_pathfind_data():
                # 房间图不可用不影响②，这里**不 return** —— 别名表可能仍可用。
                pass
            aliases = (self.p.__dict__.get('_scene_aliases') or {}).get('entries') or {}
            chapter = self.p.__dict__.get('_scene_chapter_id')
            return scene_pathfind.resolve_target(
                target, self.p.__dict__.get('_scene_index'), aliases,
                current_chapter=chapter)
        except Exception as e:
            _log.warning("目的地定位失败: %s", e)
            return {'ok': False, 'scene_id': None, 'candidates': [],
                    'ambiguous': False, 'error': str(e)}

    def plan_route_to(self, target):
        """①②③ 串起来：从**当前场景**出发，规划去 `target` 的路线（**只读**）。

        返回 `scene_pathfind.plan_from_text()` 的结果形状（见其 docstring）。
        走不到 → `ok=False` + `error`（**如实报告，不就近凑**）。
        """
        try:
            self.load_pathfind_data()
            pet = self.p
            aliases = (pet.__dict__.get('_scene_aliases') or {}).get('entries') or {}
            graph = pet.__dict__.get('_scene_room_graph') or {}
            return scene_pathfind.plan_from_text(
                target, pet.__dict__.get('_scene_index'), graph, aliases,
                current_scene_id=pet.__dict__.get('current_scene'))
        except Exception as e:
            _log.warning("路线规划失败: %s", e)
            return {'ok': False, 'goal': None, 'scene_id': None, 'ambiguous': False,
                    'candidates': [], 'path': [], 'steps': [], 'hops': 0,
                    'error': str(e)}

    def plan_route_text(self, target):
        """把路线计划拼成给 AI 看的自然语言（`''` = 不可用 → 整段不注入）。"""
        try:
            return scene_pathfind.describe_plan(self.plan_route_to(target))
        except Exception as e:
            _log.warning("路线描述生成失败: %s", e)
            return ''

    def route_reason(self):
        """最近一次路由命中给出的理由（`''` = 没有）。"""
        return self.p.__dict__.get('_scene_route_reason') or ''

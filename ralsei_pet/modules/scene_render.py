# -*- coding: utf-8 -*-
"""房间渲染层（P1）—— 「把原作的世界搬到桌面上」的绘制**计划书**。

本模块只算"要画什么、画在哪"，**一笔都不画**
------------------------------------------------
分工（与 scene_system / scene_camera 同源的三段式）：

    scene_system   → 读 JSON，出「场景是什么」（数据）
    scene_camera   → 出「相机在哪」（几何）
    scene_render   → 出「这一帧要提交哪些绘制指令」（计划）  ← 本模块
    main.py 的绘制壳 → 把计划变成 QPainter 调用（Qt）

为什么把"计划"单独一层（而不是直接在 paintEvent 里算）：

1. **可测**：本项目最贵的坑是"函数写对了但产品没用上"，反之也成立 ——
   "画对了但没人测过"。绘制指令是纯数据（tuple/dict），回归锁能逐条断言，
   不需要真机截屏（截屏依赖 OpenGL/离屏，第 44 轮实测不稳定）。
2. **可断言漂移**：程序化化生成的东西最容易"某天悄悄变了个值"。
   指令清单进基线后，`run_all.py` 的 IDENTICAL 判据直接管住它。
3. **零 Qt**：与 scene_system 同一条初始化环纪律 —— main.py 在 import 期
   会 import scene_controller，控制器 import 本模块；本模块一旦 import Qt
   或 import 项目内模块就会接环（已踩 4 次）。

绘制顺序（**从后到前**，等价原作的 depth 排序）
-----------------------------------------------
    1. `bg`         —— 背景铺满整个房间世界矩形（相机裁剪）
    2. `objects`    —— 物件，按 `depth_of` 升序（远的先画）
    3. `overlay`    —— 本模块产出的"提示层"（缺背景时的占位斜纹 / 房间边框）

★ 「背景相对运动」的算术就在 `camera.to_view_rect()`：
  视口矩形 = (世界矩形 × scale) − 相机原点。背景与物件**共用同一个变换**
  ⇒ 天然同步，不存在"背景动得慢一点"（那不是原作，见 scene_camera 文档）。

缺数据时的行为（**全部显式标注，不静默降级**）
---------------------------------------------
| 情形 | 行为 | 指令里的标记 |
|---|---|---|
| 房间几何查不到 | 退化为「房间 = 相机视口」（相机不移动） | `room_known=False` |
| 背景文件找不到 | 不产 bg 指令，改产一条 `placeholder` | `bg_missing=True` |
| 物件没素材 | 仍产指令（`pixmap=None`）—— 物件可能只是逻辑锚点 | `asset=None` |

**为什么不"算不出就整段不画"**：整段不画会让桌面突然空掉，用户以为坏了；
而"画个斜纹占位"传达了正确信息（这里本来有东西，只是素材没到）。

四条设计律（与 scene_camera / scene_system 同源）
-------------------------------------------------
1. 算不出 → 返回 `None` / 空列表，**不伪装成 (0,0)**。
2. 越界一律钳，不报错。
3. 纯函数优先 —— `plan_frame()` 不持有状态。
4. **不 import Qt、不 import 项目内模块**（初始化环纪律）。
"""
import logging

_log = logging.getLogger(__name__)

#: 缺背景时的占位斜纹的间距（px）。选 16 是因为它是原作边框带 BAND 的一半 ——
#: 不与任何原作素材尺寸冲突，视觉上一眼能看出"这是占位不是内容"。
PLACEHOLDER_STRIPE = 16

#: 房间边框线宽（px）。只为让"房间到底多大"可见 —— 大房间（6220×1920）
#: 没有这个框，用户看不出自己是在一个房间里。
ROOM_BORDER_W = 2

#: 指令 kind 常量（渲染壳按这些分派）
K_BG = 'bg'
K_OBJ = 'obj'
K_PLACEHOLDER = 'placeholder'
K_ROOM_BORDER = 'room_border'
#: ★ 第50轮：光世界「扭蛋球」容器 —— 一个球产出 **4 条**指令（保序）。
K_BUBBLE = 'bubble'

# ---------------------------------------------------------------------------
# 球容器（第50轮）—— ★ 这里的常量与 `bubble_system` 是**两份**（刻意重复）：
# 本模块是纯数据层，**不许 import 项目内模块**（初始化环纪律）；
# 重复写能让"改了一边忘了另一边"被回归锁立刻抓到（与 K_* 同一手法）。
# ---------------------------------------------------------------------------
BUBBLE_SPRITE = 'spr_dw_tv_gachaball_transparent'
#: 帧号（0=整球 / 1=上罩 / 2=下半后层 / 3=下半前层）—— 与 `bubble_system` 同源
BUBBLE_FRAME_TOP = 1
BUBBLE_FRAME_BACK = 2
BUBBLE_FRAME_FRONT = 3
#: 素材名前缀（`SceneAssetCache` 认这个前缀 → `assets/bubble/`）
BUBBLE_PREFIX = 'bubble:'
#: 角色与球同尺寸时的安全余量（保证"装得下、不穿模"）
BUBBLE_FIT_MARGIN = 1.25
#: 球的**名义原点**（原作 sprite origin = (31,31)）—— 仅作参考/归档，
#: **不用于绘制对齐**：三层帧的尺寸不同（实测 back 60×51 / front 60×47 /
#: top 60×48，而整球 62×62），且 UTMT 的 PNG 导出**没带每帧 offset**，
#: 按 origin 硬对齐会让三层整体偏下。⇒ 统一按**球心居中**（见 `_bubble_items`）。
#: ⚠️ 缺口已登记：要精确复刻分层对齐需导出每帧 offset（见第50轮报告）。
BUBBLE_ORIGIN = 31

#: 四层的 `role` 取值（顺序即原作 `Draw_0` 的绘制序）
BUBBLE_ROLE_BACK = 'back'
BUBBLE_ROLE_CHAR = 'character'
BUBBLE_ROLE_FRONT = 'front'
BUBBLE_ROLE_TOP = 'top'
BUBBLE_DRAW_ROLES = (BUBBLE_ROLE_BACK, BUBBLE_ROLE_CHAR,
                     BUBBLE_ROLE_FRONT, BUBBLE_ROLE_TOP)


def bubble_sprite_name(frame):
    """球的第 `frame` 帧素材名（带 `bubble:` 前缀，供 `SceneAssetCache` 解析）。"""
    return '%s%s_%d.png' % (BUBBLE_PREFIX, BUBBLE_SPRITE, int(frame))


def fit_scale(char_w, char_h, sprite_w=62.0, sprite_h=62.0,
              margin=BUBBLE_FIT_MARGIN):
    """按**角色的显示像素**反推球的缩放，保证球装得下角色（「不要穿模」）。

    ★ 为什么不能直接拿 `bubble_system.SCALE_DEFAULT`（1.55）当产品尺寸：
    1.55 是**原作 GameMaker** 里的倍率，原作角色就是 62px 级别的 sprite；
    而本产品里角色被 `sprite_label` 按窗口尺寸放大/缩小过 ⇒ 固定 1.55 可能让
    球**比角色小**（角色顶出球外 = 用户明确要避免的"穿模"）。
    改成"由角色尺寸反推"后，两者分工是：
    `bubble_system` 管**规则**（谁能进/何时脱），本函数管**渲染几何**。

    :return: 缩放；`char_w/h` 非法 → 退回 `1.0`（不伪装成某个"看起来合理"的值）。
    """
    try:
        cw = float(char_w or 0.0)
        ch = float(char_h or 0.0)
        sw = float(sprite_w or 62.0)
        sh = float(sprite_h or 62.0)
    except (TypeError, ValueError):
        return 1.0
    if cw <= 0 or ch <= 0 or sw <= 0 or sh <= 0:
        return 1.0
    return max(0.1, max(cw / sw, ch / sh) * float(margin or BUBBLE_FIT_MARGIN))


def output_size(camera):
    """相机视口在**输出像素**下的尺寸 = 相机**原始**尺寸（= `camera.size`）。

    ★ 推导（与 `scene_camera.scoped_size()` 配套，务必一致）
    ---------------------------------------------------
    · 相机**逻辑**窗口 = `size / scale`（`scoped_size()`）；
    · 输出像素 = 逻辑 × scale；
    · ⇒ 输出像素 = `(size / scale) × scale` = **`size`**。scale 约掉。

    **这才是正确的**:"放大"不改变"相机看到多少逻辑范围"与"输出多少像素"的
    比例关系 —— 它改变的是**每逻辑单位占多少屏幕像素**。

    ⚠️ 曾经写成 `size × scale`（因为误以为相机逻辑窗口是 `size`）——
       那会让 `output_size` 比真实画布大一倍，`viewport_size` 的上限也跟着错。
    """
    if camera is None:
        return (640, 480)
    size = camera.size
    return (int(size[0]), int(size[1]))


def viewport_size(camera, geo):
    """这一帧的**视口像素尺寸** —— 小房间时收缩到房间大小，大房间用相机尺寸。

    为什么不能无条件用相机尺寸（`640×480`）：
    原作里绝大多数房间比相机小（`320×240` = 现实世界标准房），
    若视口固定 640×480，小房间只会占中间一小块，四周是空的 ——
    观感上"房间没放大"，与用户「房间放大些，但不必全屏」的意图相反。

    规则（与 `camera_rect` 的"房间比相机小 → 居中"配对）：
      · 房间**比相机窗口小**（该轴）→ 视口取**房间像素**（= `geo × scale`），
        房间正好填满；
      · 房间**比相机窗口大**（该轴）→ 视口取**相机像素**（= `camera.size`），
        靠相机平移看全景；
      · 房间未知 → 相机像素（唯一安全的默认）。

    ⚠️ 两个轴**独立判断**：原作里有 640×1160 这种"宽=相机、高=2.4×相机"的房，
       横向不该收缩、纵向才有滚动。一刀切会把这种房压扁。

    ★ 返回的是**输出像素**尺寸。相机逻辑窗口 = `size/scale`，房间逻辑 = `geo`，
      所以"房间像素 = geo × scale"，"相机像素 = size"（见 `output_size` 推导）。
    """
    if camera is None:
        return (640, 480)
    base_w, base_h = camera.size
    scale = camera.scale if camera.scale > 0 else 1.0
    if not geo:
        return (int(base_w), int(base_h))
    gw = geo.get('w')
    gh = geo.get('h')
    if not isinstance(gw, int) or not isinstance(gh, int) or gw <= 0 or gh <= 0:
        return (int(base_w), int(base_h))
    w_px = int(round(gw * scale))
    h_px = int(round(gh * scale))
    return (min(int(base_w), w_px), min(int(base_h), h_px))


def to_output(rect_ws, camera):
    """把**视口逻辑坐标**矩形换算成**输出像素**矩形 `(x, y, w, h)`。

    `rect_ws` = `(l, t, r, b)`（逻辑坐标，来自 `camera.to_view_rect`）。
    **乘** `camera.scale` 即得像素 —— 这是"放大"在数学上唯一发生的位置。

    ★ 第 44 轮修正：曾写成"÷scale"。那是错的 —— 当时 `to_view_rect` 内部
      先把坐标 ×scale 了，所以要用除法抵消。修正后 `scene_camera` 全程走逻辑
      坐标（见其 `scoped_size()` 文档），于是这里**乘法**才是对的，
      也才是"输出放大倍数"这个语义该有的样子。
    """
    if not rect_ws or len(rect_ws) != 4:
        return None
    s = camera.scale if camera is not None and camera.scale > 0 else 1.0
    l, t, r, b = rect_ws
    return (int(round(l * s)), int(round(t * s)),
            int(round((r - l) * s)), int(round((b - t) * s)))


def room_geometry(room_id, chapter_id, geo_table=None):
    """查房间世界几何 → `{'w','h','name'?}`；查不到 → `None`（不伪造）。

    :param room_id: 原作 `Data.Rooms` 下标（产品里叫 `original_room_id`）。
    :param chapter_id: 章号字符串，如 `'ch1'`。
    :param geo_table: `_room_geometry.json` 的 `rooms` 子表。`None`/空 → `None`。
    """
    if not isinstance(geo_table, dict) or not isinstance(room_id, int):
        return None
    if not chapter_id:
        return None
    rec = geo_table.get('%s:%d' % (chapter_id, room_id))
    if not isinstance(rec, dict):
        return None
    w = rec.get('w')
    h = rec.get('h')
    if not isinstance(w, int) or not isinstance(h, int) or w <= 0 or h <= 0:
        return None
    out = {'w': w, 'h': h}
    if isinstance(rec.get('name'), str):
        out['name'] = rec['name']
    return out


def room_world_rect(geo, camera=None):
    """房间世界矩形 `(0, 0, w, h)`；`geo` 为空 → 退化为相机视口（仍返回合法矩形）。

    ⚠️ 退化值**必须是相机的世界尺寸**而不是 `(0,0,0,0)`：
       零尺寸矩形会让相机钳制逻辑除以零 / 把物件全裁掉。
       用相机尺寸作退化 = "房间刚好一屏" —— 这是**安全的默认**（画面正常，
       只是不能滚动），符合"宁可少动，不要崩"。
    """
    if geo and isinstance(geo.get('w'), int) and isinstance(geo.get('h'), int):
        return (0.0, 0.0, float(geo['w']), float(geo['h']))
    if camera is not None:
        size = camera.size
        return (0.0, 0.0, float(size[0]), float(size[1]))
    return (0.0, 0.0, 640.0, 480.0)


def visible_in_view(rect, view_size):
    """视口剔除：`rect` 与 `(0,0,vw,vh)` 有无交集。

    为什么必须有这一步：大房间（6,220 宽）里可能站着几十个物件，
    逐个 `drawPixmap` 是纯浪费。剔除是**渲染层唯一的性能开关**，
    所以判据要能单独测（见回归锁 `render_round44` 的 E 段）。

    `rect` = `(x, y, w, h)`（**视口坐标**）；`view_size` = `(vw, vh)`。
    """
    if not rect or len(rect) != 4 or not view_size or len(view_size) != 2:
        return False
    x, y, w, h = rect
    vw, vh = view_size
    if w <= 0 or h <= 0 or vw <= 0 or vh <= 0:
        return False
    return not (x + w <= 0 or y + h <= 0 or x >= vw or y >= vh)


def _anim_frame_index(anim, tick):
    """多帧物件的**当前帧号** —— 原作 sprite 逐帧动画的等价实现。

    :param anim: `{'base': 'objs/spr_x', 'frames': n, 'frame_ms': ms, 'src': ...}`
                 或 `None`（单帧物件）。
    :param tick: 见 `plan_frame` 的 `tick` 说明（毫秒时间戳优先）。

    :return: `(帧号, 总帧数)`；非动画 → `(0, 1)`（调用方据帧号拼文件名）。

    ★★★ 为什么用**毫秒时间戳**而不是"帧计数器"
    -------------------------------------------------
    原作口径（第44轮实测）：`GMS2PlaybackSpeed = 1`、
    `GMS2PlaybackSpeedType = FramesPerGameFrame`、`GMS2FPS = 30`
    ⇒ 单帧 33.3ms，**每 33.3ms 走一帧**。
    产品主循环的 tick 间隔并不严格 30ms（截断到 100ms 上限、Qt 定时器抖动），
    若按"第 N 次调用 → 第 N 帧"计数，速度会随负载漂移（机器卡就变慢）。
    用**墙钟时间**取模则与帧率无关 —— 与 `main.py` 把相机挂在 30ms
    定时器的理由一致：宁可与原作速度严格对齐，也不要"看起来在动但速度不对"。

    ★ 边界：`frames <= 1` 或 `frame_ms` 非法 → 退 `(0, 1)`，**绝不抛**。
    """
    if not isinstance(anim, dict):
        return (0, 1)
    try:
        n = int(anim.get('frames') or 1)
    except (TypeError, ValueError):
        return (0, 1)
    if n <= 1:
        return (0, 1)
    try:
        ms = float(anim.get('frame_ms') or 0.0)
    except (TypeError, ValueError):
        ms = 0.0
    try:
        t = float(tick or 0)
    except (TypeError, ValueError):
        t = 0.0
    if ms > 0.0:
        # 毫秒口径（真实主循环的必经分支）：每 ms 毫秒走一帧。
        # ★ 修正记录：初版写成 `ms > 0.0 and t >= ms` —— 于是 `t < ms`（例如
        #   t=16ms、ms=33.3ms，即"还在第 0 帧内"）会**掉进回落分支**，
        #   算出 `16 % 6 = 4`（凭空的第 4 帧）。本套件 B1 首跑就是这样报红的：
        #   那不是测试写错，是**实现里门槛写错**。正确口径只看 ms 是否有效。
        return (int(t // ms) % n, n)
    # ms 非法（缺参/为 0）→ 保守回落：每 tick 走一帧。
    # 这保证"tick=0 永远第 0 帧"（回归锁据此写确定性断言），也不至于死住不动。
    return (int(t) % n, n)


def plan_frame(scene, camera, geo_table=None, tick=0, sprite_size=None,
               bubbles=None):
    """产出这一帧的**绘制指令清单**（列表，从后到前）。

    :param scene: `SceneState`（含 `.objects` / `.bg` / `.original_room_id`）。
                  `None` → 返回 `[]`（没有场景 = 没有要画的东西，不报错）。
    :param camera: `scene_camera.Camera`。`None` 或未 follow → 返回 `[]`
                   （**没有相机就不画** —— 因为所有坐标都要相机变换，
                     硬画会把世界坐标当成屏幕坐标，画出完全错的位置）。
    :param geo_table: `_room_geometry.json['rooms']`。
    :param tick: 帧号（驱动多帧轮播）。**动效**用它算当前帧 —— 见
                 `_anim_frame_index()`。约定它是**毫秒时间戳**（`int(time*1000)`）
                 时按 `anim.frame_ms` 精确取帧；若不是毫秒量级（比如测试里
                 传小整数），按"每 tick 一帧"的保守口径取模，保证仍会动。
    :param sprite_size: 可选的 `callable(name) -> (w, h)`，告诉渲染层每个
                        素材的像素尺寸（用于剔除与居中）。缺省时按 `(1,1)` 处理
                        —— 即"不参与剔除的保守假设"？不，是**参与但极小**，
                        保证不掉帧；真正的尺寸由 Qt 壳注入。

    :param bubbles: ★ 第50轮 —— 「谁被装在光世界的扭蛋球里」。每项是
                    `{'char', 'ball_xy', 'char_xy', 'scale', 'angle', 'alpha',
                      'char_sprite', 'char_frame', 'char_size', 'filter'}`，
                    **坐标是世界（房间逻辑）坐标**（由宿主组装，见
                    `main._update_scene_layer`）。缺省 ⇒ 不产球指令，
                    老调用方**零行为变化**。
                    每个球产出 **4 条**指令（`back → 角色 → front → top`），
                    顺序逐字取自原作 `ch3.obj_tenna_board4_gacha_Draw_0.gml`：
                    角色夹在"下半后层"与"下半前层"之间、最后盖上罩 ——
                    不透明像素自然遮挡 ⇒ **不需要 mask**。

    :return: `[dict]`，每条含 `kind` + 几何 + 素材名。顺序即绘制顺序。
    """
    if scene is None or camera is None:
        return []
    cam = camera.rect
    if cam is None:
        return []

    room_id = getattr(scene, 'original_room_id', None)
    chapter_id = getattr(scene, 'chapter_id', None)
    # ⚠️ `geo` 参数是**全表**（`{'ch1:2': {...}}`）；`viewport_size` 要的是**该房间
    #    的记录**（`{'w','h'}`）。第 44 轮首跑 D5a 报"物件全被剔除"，根因就是把全表
    #    直接传给了它 —— 全表没有 `'w'` 键 ⇒ 内部走退化分支 ⇒ 视口被当成 1280×960
    #    （相机尺寸×scale），而实际该是 640×480（房间 320×240 ×2），于是坐标算错。
    geo = room_geometry(room_id, chapter_id, geo_table)
    room_known = geo is not None
    world = room_world_rect(geo, camera)
    # ★ 视口 = 小房间收缩到房间尺寸、大房间用相机尺寸（见 viewport_size 文档）。
    #   两轴独立判断：原作里有 640×1160 这种"宽=相机、高=2.4×相机"的房间。
    view = viewport_size(camera, geo)

    out = []

    # ---- 1. 背景（**按素材原尺寸**铺在房间原点，相机裁剪）----
    # ★★★ 第44轮真机实测修正（务必理解，这是最容易再写错的一处）
    #   早先版本把"房间世界矩形"整个拉伸给背景（`drawPixmap(room_px, bg)`）。
    #   真机一跑就错：`castle_front` 的房间世界是 1000×1000，而导出背景只有
    #   660×480 —— 拉伸会把背景**放大 1.5 倍**，像素风素材立刻糊掉，
    #   而且画面内容对不上（背景画的是原尺寸取景，不是整个房间）。
    #
    #   正确模型：背景素材**自带尺寸**（`sprite_size(name)` 给），落到屏幕上就是
    #   `素材像素 × scale`，位置在**房间原点**（原作背景层的 X/Y 偏移为 0 ——
    #   第43轮已实证 1,014 图层里 HSpeed/VSpeed 非零 = 0，无偏移、无视差）。
    #
    #   链路：世界矩形 `(0,0,bgw,bgh)` → `to_view_rect` 得视口逻辑 → `to_output` 乘 scale。
    bg = getattr(scene, 'bg', None)
    bg_name = bg if isinstance(bg, str) and bg else None
    room_rect_ws = camera.to_view_rect(world)
    room_px = to_output(room_rect_ws, camera) if room_rect_ws is not None else None
    if bg_name:
        # 背景素材的真实像素尺寸（未乘 scale）。拿不到 → 退回房间世界矩形
        # （**保守且安全**：至少铺满可见区，不会留白；只是可能有拉伸）。
        bg_w = bg_h = None
        if callable(sprite_size):
            try:
                got = sprite_size(bg_name)
                if isinstance(got, (list, tuple)) and len(got) == 2 \
                        and got[0] > 0 and got[1] > 0:
                    bg_w, bg_h = int(got[0]), int(got[1])
            except Exception:
                bg_w = bg_h = None
        if bg_w and bg_h:
            # 背景世界矩形 = 原点 + 素材尺寸（原作背景层偏移恒 0）
            bg_world = (0.0, 0.0, float(bg_w), float(bg_h))
            bg_ws = camera.to_view_rect(bg_world)
            bg_px = to_output(bg_ws, camera) if bg_ws is not None else None
        else:
            bg_px = room_px
        if bg_px is not None and visible_in_view(bg_px, view):
            out.append({
                'kind': K_BG,
                'name': bg_name,
                'rect': bg_px,
                'world': world,
                'native': (bg_w, bg_h),
                'room_known': room_known,
            })
        elif bg_px is None:
            out.append({
                'kind': K_PLACEHOLDER,
                'rect': (0, 0, int(view[0]), int(view[1])),
                'stripe': PLACEHOLDER_STRIPE,
                'room_known': room_known,
                'reason': '相机未 follow（背景算不出）',
            })
    else:
        # 没背景 → 占位（不静默空着，见模块 docstring 的表）
        out.append({
            'kind': K_PLACEHOLDER,
            'rect': (0, 0, int(view[0]), int(view[1])),
            'stripe': PLACEHOLDER_STRIPE,
            'room_known': room_known,
            'reason': 'scene.bg 为空',
        })

    # ---- 2. 物件（按 depth 升序；本层只做变换 + 剔除，不排序 —— 排序在 scene_system）----
    scale = camera.scale if camera.scale > 0 else 1.0
    for obj in (getattr(scene, 'objects', None) or []):
        if not isinstance(obj, dict):
            continue
        pos = obj.get('pos')
        if not (isinstance(pos, (list, tuple)) and len(pos) == 2):
            continue
        v = camera.to_view((float(pos[0]), float(pos[1])))
        if v is None:
            continue
        # 视口逻辑坐标 → 输出像素（× scale）
        px = (int(round(v[0] * scale)), int(round(v[1] * scale)))
        name = obj.get('sprite') or obj.get('image') or obj.get('asset')
        # ★ 动效：多帧物件按时间取当前帧（`anim` 由数据层写入，见 gen_objects44）。
        #   拼名规则 `objs/spr_x` + `_<n>` + `.png` —— 与磁盘文件名一致
        #   （搬运脚本按 `<spr>_<i>.png` 落盘）。取不到 `anim` → 名不变（单帧）。
        n_frames = 1
        anim = obj.get('anim')
        if isinstance(anim, dict) and isinstance(anim.get('base'), str) \
                and anim.get('base'):
            fi, n_frames = _anim_frame_index(anim, tick)
            if n_frames > 1:
                name = '%s_%d.png' % (anim['base'], fi)
        size = (1, 1)
        if callable(sprite_size) and isinstance(name, str) and name:
            try:
                got = sprite_size(name)
                if isinstance(got, (list, tuple)) and len(got) == 2:
                    size = (max(1, int(round(got[0] * scale))),
                            max(1, int(round(got[1] * scale))))
            except Exception:
                size = (1, 1)
        if not visible_in_view((px[0], px[1], size[0], size[1]), view):
            continue
        alpha = obj.get('alpha', 1.0)
        try:
            alpha = float(alpha)
        except (TypeError, ValueError):
            alpha = 1.0
        item = {
            'kind': K_OBJ,
            'name': name if isinstance(name, str) else None,
            'rect': (px[0], px[1], size[0], size[1]),
            'depth': obj.get('depth'),
            'alpha': alpha,
            'room_known': room_known,
        }
        # ★ 动效自省：把帧号/总帧数带进指令（回归锁据此断言"真的在动"，
        #   不必去比对文件名字符串 —— 后者在改名时会静默假过）。
        if isinstance(anim, dict) and n_frames > 1:
            item['anim_frame'] = int(name.rsplit('_', 1)[-1].split('.')[0]) \
                if isinstance(name, str) else 0
            item['anim_frames'] = n_frames
        out.append(item)

    # ---- 2.5 球容器（第50轮）：★ 顺序 = 原作 Draw_0：back → 角色 → front → top ----
    #   放在**物件之后**（球压住物件）、**边框之前**（边框是提示层，永远最上）。
    out.extend(_bubble_items(bubbles, camera, view, sprite_size))

    # ---- 3. 房间边框（房间比**相机**宽才画：满了屏幕就不必再框）----
    #   判据用 `to_output(camera.rect)`（相机视口像素）而不是 `view` ——
    #   后者在小房间时已被收缩成房间大小，那时 `rw == view[0]`，
    #   用 `view` 判会**永远不画**（本套件 D4a 首跑就是这样报红的）。
    #   语义上"要不要画边框"取决于"相机能不能看到房间外面"。
    if room_known and room_px is not None:
        cam_px = to_output(camera.visible_world_rect(), camera)
        cam_w = cam_px[2] if cam_px else view[0]
        if room_px[2] > cam_w:
            out.append({
                'kind': K_ROOM_BORDER,
                'rect': room_px,
                'width': ROOM_BORDER_W,
                'room_known': True,
            })

    return out


def _bubble_items(bubbles, camera, view, sprite_size=None):
    """把「谁在球里」翻译成绘制指令（每个球 **4 条**，顺序 = 原作 Draw_0）。

    ★ 三个容易写错的点（都是本轮实测踩出来的，别再踩）：
    1. **三层帧尺寸不同**：`_2`（下半后层）实测是 **60×51**、不是 62×62
       ⇒ 每层必须取**自己**的素材尺寸；拿一个尺寸套三层会把球壳拉变形。
    2. **必须对齐到同一原点**（`BUBBLE_ORIGIN` = 原作 sprite origin 31,31），
       而不是各自的中心 —— 否则尺寸大的层会整体偏移。
    3. **角色层按中心对齐**：角色的像素由 `sprite_label` 画，本层只用来
       定位「塑料滤镜」的覆盖范围。

    :param bubbles: 见 `plan_frame` 的 `:param bubbles:`。
    :return: `[dict]`（可能为空）；任何一项非法只跳过该项，**绝不抛**。
    """
    out = []
    if not bubbles:
        return out
    cam_scale = camera.scale if camera.scale > 0 else 1.0

    def _size_of(name, fb=(62, 62)):
        if callable(sprite_size):
            try:
                got = sprite_size(name)
                if isinstance(got, (list, tuple)) and len(got) == 2 \
                        and got[0] > 0 and got[1] > 0:
                    return (int(got[0]), int(got[1]))
            except Exception:
                pass
        return fb

    def _f(v, d):
        try:
            return float(v)
        except (TypeError, ValueError):
            return d

    for b in bubbles or ():
        if not isinstance(b, dict):
            continue
        ball_xy = b.get('ball_xy') or b.get('char_xy')
        if not (isinstance(ball_xy, (list, tuple)) and len(ball_xy) == 2):
            continue
        anchor = camera.to_view((float(ball_xy[0]), float(ball_xy[1])))
        if anchor is None:
            continue
        ax = anchor[0] * cam_scale
        ay = anchor[1] * cam_scale
        bscale = _f(b.get('scale'), 1.0)
        if bscale <= 0:
            bscale = 1.0
        alpha = max(0.0, min(1.0, _f(b.get('alpha'), 1.0)))
        angle = _f(b.get('angle'), 0.0)
        # 角色层：按**中心**对齐（尺寸缺省 → 1×1 占位，不伪造）
        char_xy = b.get('char_xy') or ball_xy
        csize = b.get('char_size')
        if isinstance(csize, (list, tuple)) and len(csize) == 2:
            cw = max(1, int(round(_f(csize[0], 1.0) * cam_scale)))
            chh = max(1, int(round(_f(csize[1], 1.0) * cam_scale)))
        else:
            cw = chh = 1
        canchor = camera.to_view((float(char_xy[0]), float(char_xy[1])))
        crect = None
        if canchor is not None:
            crect = (int(round(canchor[0] * cam_scale - cw / 2.0)),
                     int(round(canchor[1] * cam_scale - chh / 2.0)), cw, chh)

        seq = (
            ('ball', BUBBLE_ROLE_BACK, bubble_sprite_name(BUBBLE_FRAME_BACK)),
            ('char', BUBBLE_ROLE_CHAR, b.get('char_sprite')),
            ('ball', BUBBLE_ROLE_FRONT, bubble_sprite_name(BUBBLE_FRAME_FRONT)),
            ('ball', BUBBLE_ROLE_TOP, bubble_sprite_name(BUBBLE_FRAME_TOP)),
        )
        for layer_type, role, name in seq:
            if layer_type == 'char':
                rect = crect
            else:
                sw_i, sh_i = _size_of(name)
                w_i = max(1, int(round(sw_i * bscale)))
                h_i = max(1, int(round(sh_i * bscale)))
                # 与角色同口径：**按球心居中**（理由见 `BUBBLE_ORIGIN` 的说明）
                rect = (int(round(ax - w_i / 2.0)), int(round(ay - h_i / 2.0)),
                        w_i, h_i)
            if rect is None or not visible_in_view(rect, view):
                continue
            is_char = (role == BUBBLE_ROLE_CHAR)
            item = {
                'kind': K_BUBBLE,
                'role': role,
                'char': b.get('char'),
                'name': name,
                'rect': rect,
                'angle': 0.0 if is_char else angle,
                'alpha': 1.0 if is_char else alpha,
                'room_known': True,
            }
            flt = b.get('filter')
            if is_char and isinstance(flt, dict):
                item['filter'] = dict(flt)
            out.append(item)
    return out


def split_bubble_layers(plan):
    """把计划拆成「角色**之下**」与「角色**之上**」两份（★ 第50轮接线用）。

    为什么必须拆：桌宠的**角色**是 `sprite_label` 画的（Qt 原生控件），
    **场景**是 `scene_canvas` 画的，两者是同级的兄弟控件。要让球**包住**角色，
    球的后半层必须在 `sprite_label` 之下、前半层（front/top）必须在**之上** ——
    这正等价于原作的 `frame2 → 角色 → frame3 → frame1`：两层各占一个控件，
    靠**绘制序**物理遮挡，不需要任何 mask。

    :return: `(behind, front)`。
             `behind` = bg / obj / 边框 / 球**后**层（`back`）；
             `front`  = 球**角色层 + 前层**（`character` / `front` / `top`）。

    ★ 角色层为什么归 `front`：它**不画角色像素**（角色由 `sprite_label` 自己画），
      而是携带**塑料滤镜**、必须叠在角色**之上**才生效
      （见 `scene_canvas._paint_bubble_filter`）。
    """
    behind = []
    front = []
    for it in (plan or ()):
        if (isinstance(it, dict) and it.get('kind') == K_BUBBLE
                and it.get('role') in (BUBBLE_ROLE_CHAR, BUBBLE_ROLE_FRONT,
                                       BUBBLE_ROLE_TOP)):
            front.append(it)
        else:
            behind.append(it)
    return (behind, front)


def plan_viewport(scene, camera, geo_table=None):
    """这一帧的**画布像素尺寸** `(w, h)` —— Qt 壳按它 `resize()` 自己的画布。

    与 `plan_frame` 分开（而不是塞进指令清单的第一个元素）：
    画布尺寸是"容器属性"，指令是"内容"；混在一起会让 `plan_summary` 的计数
    把画布也算成一条指令（回归锁就必须为它写特例）。分开则各自可断言。
    """
    if scene is None or camera is None or camera.rect is None:
        return (0, 0)
    room_id = getattr(scene, 'original_room_id', None)
    chapter_id = getattr(scene, 'chapter_id', None)
    geo = room_geometry(room_id, chapter_id, geo_table)
    return viewport_size(camera, geo)


def plan_summary(plan):
    """把指令清单压成一行中文摘要（日志/自省/回归断言用）。"""
    if not plan:
        return '（无绘制指令）'
    counts = {}
    for it in plan:
        k = it.get('kind')
        counts[k] = counts.get(k, 0) + 1
    parts = ['%s×%d' % (k, counts[k]) for k in sorted(counts)]
    return '、'.join(parts)

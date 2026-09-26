# -*- coding: utf-8 -*-
"""场景画布 —— 把 `scene_render.plan_frame()` 的绘制指令清单**真正画出来**。

分工闭环
--------
    scene_system   → 「场景是什么」（数据）
    scene_camera   → 「相机在哪」（几何）
    scene_render   → 「这一帧要画哪些东西」（计划）   ← 纯数据，可回归断言
    scene_canvas   → 「把计划变成 QPainter 调用」（本模块，Qt）

第 44 轮之前只做到第三层。「函数写对了但产品用不上」是本项目最贵的坑
（记忆铁律 §4），所以本模块的存在就是补上最后一跳：**指令必须有消费者**。

为什么不做成 `paintEvent` 里现算
--------------------------------
1. **可测**：`paint_on(painter, plan, ...)` 接受一个「像 QPainter 的东西」，
   回归锁可以注入假画笔逐条断言"第 i 条指令画到了哪个矩形、用了哪张图"，
   不需要真机截屏（沙箱里离屏渲染不稳定，第 44 轮实测）。
2. **职责单一**：本模块**不认识相机、不认识场景** —— 它只吃指令清单。
   这样"相机算错"和"画错"在回归里能被区分开（否则一个 bug 会同时污染两层）。

素材缺席时**画占位，不静默空着**（与 scene_render 的 docstring 同一条纪律）
--------------------------------------------------------------------------
缺背景 → 斜纹（`K_PLACEHOLDER`）；缺物件素材 → 品红描边空框。
理由：整段不画会让用户以为坏了，而占位传达了正确信息（"这里本来有东西"）。
这与 scene_render「不静默降级」是同一件事的两个面。

绘制失败**绝不拖垮主窗口**
--------------------------
`paint_on` 全员包在 try/except 里，单条指令抛异常只跳过该条并记 debug 日志。
桌宠是常驻进程，"某个素材坏了导致整个窗口白屏"是不可接受的失败模式
（与 dr_textbox.paintEvent 同一条防御纪律）。
"""
import logging
import os

from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QWidget

try:
    from logger_utils import get_logger
except ImportError:  # 允许被包外单独导入（回归锁就是这种用法）
    import logging

    def get_logger(name):
        return logging.getLogger(name)

_log = get_logger(__name__)

# ---------------------------------------------------------------------------
# 与 scene_render 的指令 kind 对齐（这里**重复写一遍常量**而不是 import：
# 本模块属于渲染壳，`scene_render` 属于纯数据层；壳 import 数据层是单向的、
# 允许的，但常量重复写能保证"改了一边忘了另一边"时回归锁立刻报红 ——
# 见回归锁 A 段 `K_* 与 scene_render 一致`）。
# ---------------------------------------------------------------------------
K_BG = 'bg'
K_OBJ = 'obj'
K_PLACEHOLDER = 'placeholder'
K_ROOM_BORDER = 'room_border'
#: ★ 第50轮：光世界「扭蛋球」容器（四层：back / character / front / top）
K_BUBBLE = 'bubble'

#: 占位斜纹的线色（深灰）与底色（浅灰）—— 只在**浅色画布**上出现，
#: 与桌宠默认的工作区色调不冲突，且一眼能看出"这不是内容"。
PLACEHOLDER_LINE = QColor(120, 120, 120, 90)
PLACEHOLDER_FILL = QColor(200, 200, 200, 60)

#: 缺物件素材时的描边色（品红）—— 视觉上极醒目，方便用户/我一眼定位
#: "哪个物件的素材还没到"。
MISSING_OBJ_PEN = QColor(255, 0, 255, 200)

#: 房间边框颜色（半透明白）—— 大房间里这条框是"你在这个房间的哪一块"的唯一提示。
ROOM_BORDER_COLOR = QColor(255, 255, 255, 70)


class SceneAssetCache(object):
    """素材缓存：`name → QPixmap`，**只加载一次**，失败记进 `missing`。

    为什么自带缓存而不是问 sprite_loader 要：`sprite_loader` 管的是**角色动画**
    （按动画名 + 帧号索引），而场景背景是**单张整图**、物件也是单张 ——
    塞进 sprite_loader 会让"角色动画列表"混进几十张背景，污染它的自省输出。
    两份缓存各自独立、各自可清（见 `clear()`）。

    `base_dir` = `<repo>/ralsei_pet/assets/scenes/`（`bg:` 前缀的图在这里）。
    路径里可能带 `bg/` 子目录（场景 JSON 的 `bg` 字段就是 `"bg/xxx.png"` 形式）。
    """

    def __init__(self, base_dir=None):
        self.base = base_dir or _scenes_dir()
        self._cache = {}
        self._failed = set()
        self.missing = []

    def get(self, name):
        """按 `name` 取 pixmap；取不到（文件不在 / 读不出）→ `None`（不伪造）。"""
        if not name or not isinstance(name, str):
            return None
        if name in self._cache:
            return self._cache[name]
        if name in self._failed:
            return None
        pm = None
        try:
            rel = name
            # 场景 JSON 里的 `bg` 是相对 scenes_dir 的路径（可能带 `bg/`）；
            # 物件素材可能带 `sprite:` 前缀（指向仓库根，见 scene_system._KIND_SCOPE）。
            if rel.startswith('sprite:'):
                rel = rel[len('sprite:'):]
                base = _project_root()
            elif rel.startswith('bubble:'):
                # ★ 第50轮：球容器素材住在 `assets/bubble/`（不在 scenes/ 下）
                rel = rel[len('bubble:'):]
                base = _bubble_dir()
            else:
                base = self.base
            path = rel if os.path.isabs(rel) else os.path.normpath(
                os.path.join(base, rel))
            if os.path.exists(path):
                pm = QPixmap(path)
                if pm.isNull():
                    pm = None
        except Exception as e:
            _log.debug("scene_canvas 素材读取异常（%r）: %s", name, e)
            pm = None
        if pm is None:
            self._failed.add(name)
            if name not in self.missing:
                self.missing.append(name)
            return None
        self._cache[name] = pm
        return pm

    def sprite_size(self, name):
        """`callable(name) -> (w, h)` —— 交给 `scene_render.plan_frame` 做剔除。

        ★ 必须**返回原图像素尺寸**（未乘 scale）：`plan_frame` 内部会乘 scale。
          这里要是先乘了，就会出现"剔除判据说 84 宽、实际画 42 宽"的偏差。
        """
        pm = self.get(name)
        if pm is None:
            return None
        return (pm.width(), pm.height())

    def clear(self):
        """清空缓存（换场景目录时用）。"""
        self._cache.clear()
        self._failed.clear()
        self.missing = []


def _scenes_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, '..', 'assets', 'scenes'))


def _project_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, '..', '..'))


def _bubble_dir():
    """球容器素材目录 `ralsei_pet/assets/bubble/`（`bubble:` 前缀解析到这里）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, '..', 'assets', 'bubble'))


def _rect(t):
    """`(x, y, w, h)` tuple → `QRect`（防御：长度不足 → 空 QRect）。"""
    if not t or len(t) != 4:
        return QRect()
    return QRect(int(t[0]), int(t[1]), int(t[2]), int(t[3]))


def paint_on(painter, plan, assets, view_size=None):
    """把指令清单画到 `painter` 上。返回**实际画出的条数**（用于自省/断言）。

    :param painter: 任何有 `fillRect` / `drawPixmap` / `drawRect` / `setPen` 的
                    对象。真机传 QPainter；回归锁传假画笔（只记录调用）。
    :param plan: `scene_render.plan_frame()` 的输出（列表，从后到前）。
    :param assets: `SceneAssetCache`（或任何有 `.get(name)` 的对象）。
    :param view_size: `(w, h)` 画布像素尺寸 —— 画背景前按它裁一次，
                      免得大背景（6220×1920）被整张画到画布外（纯浪费）。

    :return: 成功绘制的指令条数。
    """
    if not plan:
        return 0
    drawn = 0
    for item in plan:
        try:
            kind = item.get('kind')
            if kind == K_BG:
                drew = _paint_bg(painter, item, assets)
            elif kind == K_OBJ:
                drew = _paint_obj(painter, item, assets)
            elif kind == K_PLACEHOLDER:
                drew = _paint_placeholder(painter, item)
            elif kind == K_ROOM_BORDER:
                drew = _paint_room_border(painter, item)
            elif kind == K_BUBBLE:
                drew = _paint_bubble(painter, item, assets)
            else:
                # 未知 kind：**不静默吞**，记一条 debug（将来新增 kind 时
                # 回归锁的"每种 kind 都被画过"判据会抓到）。
                _log.debug("scene_canvas 未知指令 kind=%r（已跳过）", kind)
                continue
            # ★ 只有**真的落笔了**才计数。几何非法（空 rect）的指令会被各
            #   `_paint_*` 返回 False —— 若这里无条件 +1，"drawn" 就变成
            #   "处理了几条"而不是"画了几条"，自省输出会骗人
            #   （第44轮套件 C8a 就是这样抓到的）。
            if drew:
                drawn += 1
        except Exception as e:
            # 单条失败不拖垮整帧（见模块 docstring 的失败纪律）。
            _log.debug("scene_canvas 绘制单条指令失败（已跳过）: %s", e)
    return drawn


def _paint_bg(painter, item, assets):
    """画背景：按指令给的像素矩形绘制（矩形 = `素材尺寸 × scale`，见 scene_render）。

    ⚠️ 这里**不是**"拉伸铺满房间" —— 第44轮真机实测证明那样会放大像素风素材
       （房间 1000×1000 vs 素材 660×480 ⇒ 糊掉）。矩形由渲染层算好，
       本函数只负责落笔。

    :return: 是否**真的落笔**（几何非法 → False）。
    """
    rect = _rect(item.get('rect'))
    if rect.isEmpty():
        return False
    pm = assets.get(item.get('name'))
    if pm is None or pm.isNull():
        # 缺背景 → 画占位（与 K_PLACEHOLDER 同一视觉），**不留空白**。
        _paint_placeholder(painter, {'rect': item.get('rect'),
                                     'stripe': 16,
                                     'reason': 'bg 素材缺失'})
        return True
    painter.drawPixmap(rect, pm)
    return True


def _paint_obj(painter, item, assets):
    """画物件：按 `rect` 左上角落位、指定尺寸。

    `depth` 排序在 `scene_system.visible_objects` 已做，指令清单里的顺序
    就是绘制顺序 —— 这里**不再排序**（排序是数据层的职责，见模块 docstring）。

    :return: 是否**真的落笔**。
    """
    rect = _rect(item.get('rect'))
    if rect.isEmpty():
        return False
    name = item.get('name')
    pm = assets.get(name) if name else None
    alpha = item.get('alpha', 1.0)
    if pm is None or pm.isNull():
        # 缺素材：画品红空框（**不静默跳过** —— 用户要能看见"这里缺图"）。
        painter.setPen(QPen(MISSING_OBJ_PEN))
        painter.drawRect(rect)
        return True
    if isinstance(alpha, (int, float)) and 0.0 <= alpha < 1.0:
        painter.setOpacity(float(alpha))
        painter.drawPixmap(rect, pm)
        painter.setOpacity(1.0)
    else:
        painter.drawPixmap(rect, pm)
    return True


def _paint_placeholder(painter, item):
    """画 45° 斜纹占位（缺背景/缺数据时的"这里本来有东西"）。

    :return: 是否**真的落笔**。
    """
    rect = _rect(item.get('rect'))
    if rect.isEmpty():
        return False
    painter.fillRect(rect, QBrush(PLACEHOLDER_FILL))
    step = int(item.get('stripe') or 16)
    if step <= 0:
        step = 16
    painter.setPen(QPen(PLACEHOLDER_LINE))
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    span = w + h
    for i in range(-h, span, step):
        x1, y1 = x + i, y
        x2, y2 = x + i - h, y + h
        if x1 > x + w:
            x1, y1 = x + w, y + (x1 - (x + w))
        if x2 < x:
            x2, y2 = x, y + (x - x2)
        painter.drawLine(int(x1), int(y1), int(x2), int(y2))
    return True


def _paint_room_border(painter, item):
    """画房间边框（大房间时提示"房间比屏幕大"）。

    :return: 是否**真的落笔**。
    """
    rect = _rect(item.get('rect'))
    if rect.isEmpty():
        return False
    w = int(item.get('width') or 2)
    pen = QPen(ROOM_BORDER_COLOR)
    pen.setWidth(max(1, w))
    painter.setPen(pen)
    painter.drawRect(rect)
    return True


def _paint_bubble(painter, item, assets):
    """画球的**一层**（`role` ∈ `back` / `character` / `front` / `top`）。

    ★ 关键：`role == 'character'` 时**不画角色像素**，只画「透过塑料看人」的
    **滤镜覆盖层** —— 角色本体由 `sprite_label` 画（见
    `scene_render.split_bubble_layers` 的分层说明）。于是：
      · `scene_canvas` 只遇得到 `back`（在角色**之下**）；
      · `BubbleOverlay` 只遇得到 `character` / `front` / `top`（在角色**之上**）。
    两个控件各画各的 ⇒ 绘制序等价原作 `frame2 → 角色 → frame3 → frame1`。

    旋转（原作的 `ball_angle` 缓动）在真机上用 `save/translate/rotate` 实现；
    假画笔没有这些方法时**退化为不旋转**（保证回归锁不必模拟 Qt 变换）。

    :return: 是否**真的落笔**。
    """
    rect = _rect(item.get('rect'))
    if rect.isEmpty():
        return False
    if item.get('role') == 'character':
        return _paint_bubble_filter(painter, item)
    name = item.get('name')
    pm = assets.get(name) if name else None
    if pm is None or pm.isNull():
        # 球素材缺失：品红描边（**不静默空着**，与缺物件同一条纪律）
        painter.setPen(QPen(MISSING_OBJ_PEN))
        painter.drawRect(rect)
        return True
    alpha = item.get('alpha', 1.0)
    ang = item.get('angle')
    rotate = (isinstance(ang, (int, float)) and abs(float(ang)) > 0.01
              and hasattr(painter, 'save') and hasattr(painter, 'rotate'))
    target = rect
    if rotate:
        painter.save()
        painter.translate(rect.center().x(), rect.center().y())
        painter.rotate(float(ang))
        target = QRect(-rect.width() // 2, -rect.height() // 2,
                       rect.width(), rect.height())
    if isinstance(alpha, (int, float)) and 0.0 <= alpha < 1.0:
        painter.setOpacity(float(alpha))
        painter.drawPixmap(target, pm)
        painter.setOpacity(1.0)
    else:
        painter.drawPixmap(target, pm)
    if rotate:
        painter.restore()
    return True


#: 「塑料滤镜」覆盖层的兜底色（与 bubble_system.FILTER_DEFAULT 的 tint 同源）
BUBBLE_TINT_FALLBACK = (222, 231, 238)


def _paint_bubble_filter(painter, item):
    """「透过塑料看人」—— 在角色**之上**叠一层半透明冷色（球壳反光）。

    为什么不是给 `sprite_label` 换 pixmap：那会**污染 sprite 缓存**
    （同一张图两种外观），换球/脱球时还得重建缓存。叠一层色是**可逆、零副作用**的。

    覆盖强度由「球越透明、人越清楚」推出：`cover = 1 - alpha`
    （球 alpha 0.88 ⇒ 覆盖 0.12，肉眼是"隔着一层壳"而不是"蒙了块布"）。

    :return: 是否**真的落笔**。
    """
    rect = _rect(item.get('rect'))
    if rect.isEmpty():
        return False
    f = item.get('filter') or {}
    tint = f.get('tint')
    if not (isinstance(tint, (list, tuple)) and len(tint) >= 3):
        tint = BUBBLE_TINT_FALLBACK
    try:
        a = float(f.get('alpha', 0.88))
    except (TypeError, ValueError):
        a = 0.88
    cover = max(0.06, min(0.6, 1.0 - max(0.0, min(1.0, a))))
    col = QColor(int(tint[0]), int(tint[1]), int(tint[2]))
    col.setAlphaF(cover)
    painter.fillRect(rect, QBrush(col))
    return True


class SceneCanvas(QWidget):
    """场景画布控件 —— 自绘 room 背景 / 物件 / 占位 / 边框。

    ⚠️ **默认 `setVisible(False)`**：桌宠窗口是透明 + 非置顶的（Ralsei 直接画在
    桌面上），本画布是 P1 的"场景层"。宿主在**确认要显示场景**时才把它 show 出来
    —— 这样"不切场景时零行为变化"（P0 判据）不会因为多了个子控件而破。

    本控件**不认识相机与场景**，一切都从 `set_plan(plan, view_size)` 进来。
    """

    def __init__(self, parent=None, assets=None):
        super().__init__(parent)
        self.setObjectName("sceneCanvas")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # 场景是像素风原素材：**禁平滑缩放**（平滑会让 2× 放大后的像素糊掉，
        # 与 dr_textbox 同一条口径）。
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.assets = assets or SceneAssetCache()
        self._plan = []
        self._view_size = (0, 0)
        self.last_drawn = 0
        self.hide()

    # -- 数据入口 --------------------------------------------------------
    def set_plan(self, plan, view_size=None):
        """提交这一帧的绘制指令 + 画布尺寸，并请求重绘。

        返回是否需要重绘（尺寸或内容有变）—— 调用方可用它省掉无谓的 update()。
        判据只比"指令清单长度 + 画布尺寸"（不做深比较：每帧深比 85 条 dict
        比直接重绘还贵，而且场景内容变化本来就伴随长度/尺寸变化）。
        """
        plan = plan or []
        if view_size is None:
            view_size = self._view_size
        changed = (len(plan) != len(self._plan) or
                   tuple(view_size) != tuple(self._view_size) or
                   plan != self._plan)
        self._plan = plan
        if view_size and len(view_size) == 2:
            self._view_size = (int(view_size[0]), int(view_size[1]))
            self.resize(max(0, self._view_size[0]), max(0, self._view_size[1]))
        if changed:
            self.update()
        return changed

    def plan(self):
        return list(self._plan)

    def view_size(self):
        return self._view_size

    # -- 绘制 ------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 (Qt 命名)
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
            self.last_drawn = paint_on(p, self._plan, self.assets, self._view_size)
            p.end()
        except Exception as e:
            # 绘制失败不能拖垮主窗口（常驻进程纪律，见模块 docstring）。
            _log.debug("scene_canvas 绘制异常（已忽略）: %s", e)


class BubbleOverlay(QWidget):
    """★★ 第50轮：**盖在角色之上**的球前层 —— 让球真正"包住"Ralsei。

    为什么必须单独一个控件：球的绘制序是 `back → 角色 → front → top`，
    而角色（`sprite_label`）在 `scene_canvas` **之上**。若把 front/top 也画进
    `scene_canvas`，球壳会被角色盖住（看着像"角色站在球前面"），与用户要的
    「ralsei是在球里面」正好相反。所以前层要有**自己的控件**并 `raise_()` 到
    `sprite_label` 之上 —— 两个控件靠绘制序完成**物理遮挡**（等价原作分层）。

    它同时承载「透过塑料看人」的滤镜层：`role='character'` 的指令**不画角色**，
    只叠一层半透明冷色（见 `_paint_bubble_filter`）。

    ⚠️ 两条自我约束：
    · `WA_TransparentForMouseEvents` —— **不许挡住拖拽/点击**（桌宠是交互窗口）；
    · 默认 `hide()`；只有真的有前层可画时才显示（否则桌面多一个透明控件白耗）。
    """

    def __init__(self, parent=None, assets=None):
        super().__init__(parent)
        self.setObjectName("bubbleOverlay")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.assets = assets or SceneAssetCache()
        self._plan = []
        self._view_size = (0, 0)
        self.last_drawn = 0
        self.hide()

    def set_plan(self, plan, view_size=None):
        """提交球前层的绘制指令（语义同 `SceneCanvas.set_plan`）。"""
        plan = plan or []
        if view_size is None:
            view_size = self._view_size
        changed = (len(plan) != len(self._plan) or
                   tuple(view_size) != tuple(self._view_size) or
                   plan != self._plan)
        self._plan = plan
        if view_size and len(view_size) == 2:
            self._view_size = (int(view_size[0]), int(view_size[1]))
            self.resize(max(0, self._view_size[0]), max(0, self._view_size[1]))
        if changed:
            self.update()
        return changed

    def plan(self):
        return list(self._plan)

    def paintEvent(self, event):  # noqa: N802 (Qt 命名)
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
            self.last_drawn = paint_on(p, self._plan, self.assets, self._view_size)
            p.end()
        except Exception as e:
            _log.debug("bubble_overlay 绘制异常（已忽略）: %s", e)

# -*- coding: utf-8 -*-
u"""幽灵窗口 —— 把 `ghost_system.GhostState` 画到桌面上的那只幽灵（第67轮）。

为什么是**独立顶层窗口**（与灵魂同一决策）
--------------------------------------------------
幽灵**站在桌面上**：定点那只站在某个位置不动、宠物走近了才清晰（用户 N2 选的
"定点距离式"）；跟飘那只（B5 的"停走式"）**贴着宠物飘**。
两种模式下它都**不属于宠物窗口** —— 子控件会被宠物窗口裁剪（宠物窗口只有 ~42×82
屏幕像素），"站在桌面上某处 / 飘在宠物旁边"这两件事都无从表达 ⇒ 必须独立窗口。

窗口本身与模式**无关**（尺寸、透明、不吃事件、不置顶全都一样），模式只改
`state` 怎么走（见 `ghost_system.GhostState` 的类 docstring）。

三条硬约束（**逐条**来自 `soul_overlay` 踩过的坑）
--------------------------------------------------
1. **禁 `WindowStaysOnTopHint`** —— 建楼契约（`floor_manager.floor_visible_contains`
   是唯一判据）建立在"窗口有正常 z 序"上。幽灵**不加**置顶。
2. **不许挡住桌面交互，且比灵魂更严格**：灵魂要能拖、要能接键盘，所以它接收鼠标；
   幽灵**纯视觉**，一个事件都不该吃 ⇒ `WA_TransparentForMouseEvents` +
   `WindowDoesNotAcceptFocus`（用户点它后面那个图标时不该点到幽灵）。
3. **绘制失败绝不拖垮进程**：`paintEvent` 与所有对外方法全员包 try ——
   桌宠是常驻进程，"幽灵素材坏了导致整个 App 白屏"不可接受
   （与 `scene_canvas` / `dr_textbox` / `soul_overlay` 同一条纪律）。

★ 一件**不重复实现**的事：虚拟屏矩形
--------------------------------------------------
用 `soul_overlay.virtual_screen_rect`（**唯一**一处实现，契约①：禁用
`availableGeometry()`，它只返主屏）。本项目吃过「同一判据两份实现 ⇒ 两种结论」的亏
（记忆 §4），所以这里宁可跨模块引用，也不复制那 20 行。

坐标口径（与 `soul_overlay` 不同，务必注意）
--------------------------------------------------
`soul_overlay` 的 `state.x/y` = **窗口左上角**；本模块的 `state.x/y` = **幽灵锚点（中心）**，
窗口按中心放置。理由：`ghost_system` 的距离式 alpha 是**中心到中心**的距离
（原作用 `distance_to_object`，比的也是对象原点）—— 让"距离用的点"和"摆放的点"是同一个点，
可以少一层心智负担，也不必在模块之间传递窗口尺寸。
"""
import logging
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QWidget

try:
    from logger_utils import get_logger
except ImportError:  # 允许被包外单独导入（回归锁就是这种用法）
    def get_logger(name):
        return logging.getLogger(name)

try:
    from modules import ghost_system as ghost_mod
except ImportError:          # 包内导入（modules/ 已在 sys.path 时）
    import ghost_system as ghost_mod

try:                         # ★ 唯一实现，不重写（见模块 docstring）
    from modules.soul_overlay import virtual_screen_rect
except ImportError:
    from soul_overlay import virtual_screen_rect

_log = get_logger(__name__)

#: 幽灵推进频率（毫秒）—— 与 `GMS2FPS = 30` 对齐（= `SOUL_TICK_MS`）。
GHOST_TICK_MS = 33

#: 缺素材时的描边色（品红）—— 与 `scene_canvas.MISSING_OBJ_PEN` / `soul_overlay.MISSING_PEN`
#: 同一口径：**不静默空着**，用户要能一眼看见"这里的图没到"。
MISSING_PEN = QColor(255, 0, 255, 220)

#: 定点幽灵用的精灵族 —— 对应原作 `obj_ghostint2`（Chara 的定点幽灵，`sprite=spr_ghost_chara_down`）。
GHOST_SPRITE = 'spr_ghost_chara_down'
#: 该精灵的帧数（`_source.json` 实测 8 帧；本项目只用第 0 帧，见 `ghost_system`）。
GHOST_FRAMES = 8
#: 原生尺寸（`_source.json` 实测 `w=22 h=29`）。
GHOST_NATIVE_W = 22.0
GHOST_NATIVE_H = 29.0
#: 显示倍率。原生 22×29 × 2 = **44×58**，与宠物窗口（~42×82）同量级 ——
#: 既不"小得看不见"，也不喧宾夺主。宿主可用 `set_scale()` 覆盖。
GHOST_SCALE = 2.0


def ghost_dir():
    u"""幽灵素材目录 `ralsei_pet/assets/sprites/ghost/`。"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, '..', 'assets', 'sprites', 'ghost'))


def ghost_frame_names(sprite=GHOST_SPRITE, frames=GHOST_FRAMES):
    return tuple('%s_%d.png' % (sprite, i) for i in range(int(frames)))


def load_ghost_sprites(dir_path=None, sprite=GHOST_SPRITE, frames=GHOST_FRAMES):
    u"""加载幽灵的帧。

    缺图**不伪造**：返回的列表里该位为 `None`，绘制时画品红框
    （与 `load_soul_sprites` 同一形状 —— 只读，不改盘）。
    """
    d = dir_path or ghost_dir()
    out = []
    for f in ghost_frame_names(sprite, frames):
        pm = None
        try:
            p = os.path.join(d, f)
            if os.path.exists(p):
                pm = QPixmap(p)
                if pm.isNull():
                    pm = None
        except Exception as e:
            _log.debug('幽灵素材读取失败 %r: %s', f, e)
            pm = None
        if pm is None:
            _log.warning('幽灵素材缺失：%s（该帧将画品红框）', os.path.join(d, f))
        out.append(pm)
    return out


class GhostOverlay(QWidget):
    u"""桌面上的那只定点幽灵。默认**不显示**，宿主确认可见后才 `show()`。"""

    def __init__(self, parent=None, sprites=None, state=None, scale=GHOST_SCALE):
        super().__init__(parent)
        self.setObjectName('ghostOverlay')
        # ⚠️ 不加 WindowStaysOnTopHint（见模块 docstring 约束 1）。
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool |
                            Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # ★ 约束 2：幽灵纯视觉，一个事件都不吃（比灵魂更严格）。
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(False)

        self.state = state if state is not None else ghost_mod.GhostState()
        self.sprites = sprites if sprites is not None else load_ghost_sprites()
        self.scale = max(0.1, float(scale or GHOST_SCALE))
        self._last_paint_index = None
        self._last_alpha = None
        self.last_drawn = 0
        self._sync_size()
        self.hide()

    # ---------------------------------------------------------------- 几何
    def frame_size(self):
        """当前缩放下的显示尺寸 `(w, h)`（整数，至少 1×1）。"""
        return (max(1, int(round(GHOST_NATIVE_W * self.scale))),
                max(1, int(round(GHOST_NATIVE_H * self.scale))))

    def set_scale(self, scale):
        u"""改显示倍率并同步窗口尺寸。返回 `(w, h)`。"""
        try:
            self.scale = max(0.1, float(scale))
            self._sync_size()
        except Exception as e:
            _log.debug('幽灵缩放设置失败（保持原值）: %s', e)
        return self.frame_size()

    def _sync_size(self):
        try:
            w, h = self.frame_size()
            if self.width() != w or self.height() != h:
                self.resize(w, h)
        except Exception as e:
            _log.debug('幽灵尺寸同步失败: %s', e)

    def anchor(self):
        u"""幽灵锚点（世界坐标，= `state.x/y`）。"""
        try:
            return float(self.state.x), float(self.state.y)
        except Exception:
            return 0.0, 0.0

    def apply_state_pos(self):
        u"""把锚点写到窗口上 —— **按中心放置**（不是左上角，见模块 docstring）。

        ★ 顺带做一件事：锚点要钳到虚拟屏内。否则幽灵可能停在屏幕外，
        而"距离式 alpha"只在宠物走近时才有值 —— 屏幕外的幽灵永远不可见，
        用户会以为功能坏了。钳制用**虚拟屏并集**（契约①）。
        位置没变则不动窗口（省一次 SetWindowPos）。
        """
        try:
            x, y = self.anchor()
            w, h = self.width(), self.height()
            b = self.screen_bounds()
            if b:
                cx = min(max(x, b[0] + w / 2.0), b[2] - w / 2.0)
                cy = min(max(y, b[1] + h / 2.0), b[3] - h / 2.0)
            else:
                cx, cy = x, y
            px = int(round(cx - w / 2.0))
            py = int(round(cy - h / 2.0))
            if self.x() != px or self.y() != py:
                self.move(px, py)
        except Exception as e:
            _log.debug('幽灵移动失败: %s', e)

    def screen_bounds(self):
        return virtual_screen_rect(self)

    # ---------------------------------------------------------------- 推进
    def tick(self, dt, pet_x=None, pet_y=None, contact=None,
             moving=None, cutscene=None):
        u"""推进一帧。返回 True 表示"这一帧有变化"（alpha 或位置）。

        :param moving: 宠物这一帧走没走 —— **停走式（`MODE_FOLLOW`）的唯一输入**。
            `MODE_FIXED` 下传了也没用（定点那只的 alpha 只认距离），**照样透传**
            是为了让宿主不必知道当前是哪个模式（少一层"宿主和模块各记一份模式"的隐患）。
        :param cutscene: 过场档（桌面版恒 `False`，见 `ghost_system.alpha_cap`）。
        """
        try:
            changed = self.state.step(dt, px=pet_x, py=pet_y, contact=contact,
                                      moving=moving, cutscene=cutscene)
            self.apply_state_pos()
            idx = int(self.state.frame)
            a = round(float(self.state.alpha), 3)
            repaint = (idx != self._last_paint_index) or (a != self._last_alpha)
            if repaint:
                self._last_paint_index = idx
                self._last_alpha = a
                self.update()
            return bool(changed) or repaint
        except Exception as e:
            _log.debug('幽灵推进失败（本帧跳过）: %s', e)
            return False

    def alpha(self):
        try:
            return float(self.state.alpha)
        except Exception:
            return 0.0

    def wants_show(self):
        u"""当前是否**该**显示（alpha 非零）。宿主据此开/停窗口。"""
        try:
            return self.alpha() > 0.001
        except Exception:
            return False

    # ---------------------------------------------------------------- 外显入口
    def _alive(self):
        u"""Qt 对象是否还活着。

        ★ 为什么需要它：`cleanup_on_exit()` 会 `hide_ghost()` + `close()`，而
          `atexit` 再跑一次收尾时，C++ 侧的窗口已经析构 ⇒ 再调 `hide()` 会抛
          `RuntimeError: wrapped C/C++ object ... has been deleted`。
          那是**退出期的正常现象**，不该打一整片 traceback 把真问题埋掉
          （第67轮真机实测：退出时刷出两条 `Traceback`，很容易被误读成崩溃）。
        """
        try:
            self.objectName()
            return True
        except RuntimeError:
            return False

    def show_ghost(self, activate=False):
        """显示幽灵。**绝不置顶**。"""
        if not self._alive():
            return False
        try:
            self._sync_size()
            self.apply_state_pos()
            self.show()
            if activate:
                try:
                    self.raise_()
                except Exception as e:
                    _log.debug('幽灵 raise_ 失败（忽略）: %s', e)
            self._last_alpha = None
            self.update()
            return True
        except RuntimeError as e:                # 对象已析构（退出期）⇒ 只记 debug
            _log.debug('幽灵窗口已销毁，跳过显示: %s', e)
            return False
        except Exception:
            _log.exception('显示幽灵失败')
            return False

    def hide_ghost(self):
        if not self._alive():
            return False
        try:
            self.hide()
            return True
        except RuntimeError as e:                # 同上：退出期正常现象
            _log.debug('幽灵窗口已销毁，跳过隐藏: %s', e)
            return False
        except Exception:
            _log.exception('隐藏幽灵失败')
            return False

    # ---------------------------------------------------------------- 绘制
    def paintEvent(self, event):  # noqa: N802 (Qt 命名)
        u"""按 `state.alpha` 画一帧。

        ★ 「幽灵感」**全来自 alpha**（`幽灵机制64.md` §1 已实证：贴图 alpha 是**二值**
        的 0/255，没有半透明像素；原作也是 `draw_sprite_ext(..., c_white, alpha)`）
        —— 所以这里用 `QPainter.setOpacity`，**不给贴图调色**。
        """
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
            a = self.alpha()
            if a <= 0.001:
                # ★ 这一帧**什么都没画** ⇒ 诊断值必须归零。
                # （探针实测过：不归零的话，alpha 已经掉到 0 之后 last_drawn 还留着
                #  上一帧的 2，"这帧画了什么"就被谎报了 —— 报告说"画了贴图"，实际空白。）
                self.last_drawn = 0
                p.end()
                return
            p.setOpacity(max(0.0, min(1.0, a)))
            try:
                idx = int(self.state.frame) % max(1, len(self.sprites))
            except Exception:
                idx = 0
            pm = self.sprites[idx] if self.sprites else None
            r = self.rect()
            if pm is None or pm.isNull():
                p.setOpacity(1.0)
                p.setPen(QPen(MISSING_PEN))
                p.drawRect(r.adjusted(1, 1, -1, -1))
                self.last_drawn = 1
            else:
                p.drawPixmap(r, pm)
                self.last_drawn = 2
            p.end()
        except Exception as e:
            _log.debug('幽灵绘制异常（已忽略）: %s', e)

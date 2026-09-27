# -*- coding: utf-8 -*-
"""灵魂窗口 —— 把 `soul_entity.SoulState` 画到桌面上的那只红色 SOUL（第55轮）。

为什么是**独立顶层窗口**（而不是主窗口的子控件）
------------------------------------------------
用户口径是「**灵魂也可自由出入各个场景**，相当于这也是一个有互动的实体」。
子控件会被主窗口裁剪（第55轮实测：主窗口 ≈ 42×82 屏幕像素，
而场景画布是 640×480 —— 见报告 §3），灵魂一旦做成子控件，
就会被压成窗口里的一小块，既走不出宠物那点地方，也谈不上"自由出入"。
独立窗口则天然**不隶属任何场景**：宠物换房间、开菜单、缩到托盘，
灵魂都在原地（这正是"自由出入"的产品表达）。

三条硬约束（都来自本项目踩过的坑）
----------------------------------
1. **禁 `WindowStaysOnTopHint`** —— 建楼契约（`floor_manager.floor_visible_contains`
   是唯一判据）建立在"窗口有正常 z 序"上；一个恒置顶的窗口会破坏"被前面的窗口压住"
   这一条。灵魂因此**不加**置顶，靠用户点击自然抬升。
2. **不许挡住桌面交互**：灵魂只有 48×48，且**只在被抓住时**接收鼠标；
   其余时刻它不吞任何事件（本身就没有可拖动区域之外的东西）。
3. **绘制失败绝不拖垮进程**：`paintEvent` / 所有槽函数全员包 try ——
   桌宠是常驻进程，"灵魂素材坏了导致整个 App 白屏"是不可接受的失败模式
   （与 `scene_canvas` / `dr_textbox` 同一条纪律）。

键盘只在**本窗口有焦点时**生效（与主窗口的裸 `S` 同一条口径）
------------------------------------------------------------
`global_hotkey` 的模块 docstring 已经把理由写死了：`RegisterHotKey` 不带修饰键
= **系统级抢占**。所以方向键**只**在灵魂窗口（或宠物窗口）有焦点时响应
—— 用户在别的程序里按方向键不受任何影响。
（`global_hotkey.vk_for_letter` 只认字母/数字，压根无法注册 `ctrl+alt+←`；
  要全局"按住移动"得装 low-level keyboard hook，本轮**不做**，如实写进报告。）
"""
import logging
import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QWidget

try:
    from logger_utils import get_logger
except ImportError:  # 允许被包外单独导入（回归锁就是这种用法）
    def get_logger(name):
        return logging.getLogger(name)

try:
    from modules import soul_entity as soul_mod
except ImportError:          # 包内导入（modules/ 已在 sys.path 时）
    import soul_entity as soul_mod

_log = get_logger(__name__)

#: 灵魂推进频率（毫秒）—— 与原作 `GMS2FPS = 30` 对齐。
SOUL_TICK_MS = 33

#: 缺素材时的描边色（品红）—— 与 `scene_canvas.MISSING_OBJ_PEN` 同一口径：
#: **不静默空着**，用户要能一眼看见"这里的图没到"。
MISSING_PEN = QColor(255, 0, 255, 220)

#: `Qt.Key_*` → `soul_entity` 的方向名。**只映射方向键**（理由见模块 docstring）。
_QT_KEY_DIRS = None


def _qt_key_dirs():
    global _QT_KEY_DIRS
    if _QT_KEY_DIRS is None:
        _QT_KEY_DIRS = {
            Qt.Key_Left: 'left', Qt.Key_Right: 'right',
            Qt.Key_Up: 'up', Qt.Key_Down: 'down',
        }
    return _QT_KEY_DIRS


def direction_of_qt_key(qt_key):
    """`Qt.Key_*` → `'left'/...`；不是方向键返回 `None`。"""
    return _qt_key_dirs().get(qt_key)


def soul_dir():
    """灵魂素材目录 `ralsei_pet/assets/soul/`。"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, '..', 'assets', 'soul'))


def load_soul_sprites(dir_path=None, names=None):
    """加载灵魂的帧（照原作顺序：`spr_heart_0` = 常态，`spr_heart_1` = 受击帧）。

    缺图**不伪造**：返回的列表里该位为 `None`，绘制时画品红框。
    """
    d = dir_path or soul_dir()
    frames = list(names or ('spr_heart_0.png', 'spr_heart_1.png'))
    out = []
    for f in frames:
        pm = None
        try:
            p = os.path.join(d, f)
            if os.path.exists(p):
                pm = QPixmap(p)
                if pm.isNull():
                    pm = None
        except Exception as e:
            _log.debug('灵魂素材读取失败 %r: %s', f, e)
            pm = None
        if pm is None:
            _log.warning('灵魂素材缺失：%s（该帧将画品红框）', os.path.join(d, f))
        out.append(pm)
    return out


def virtual_screen_rect(widget=None):
    """虚拟屏矩形 `(l, t, r, b)`（多屏合计）。

    ⚠️ 必须用 `QApplication.screens()` 求并集，**不能**用 `availableGeometry()`
    —— 后者只返主屏，副屏上的灵魂会被"钳"回主屏（本项目第0号契约，见记忆 §3①）。
    """
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            return None
        union = None
        for screen in app.screens():
            g = screen.geometry()
            union = g if union is None else union.united(g)
        if union is None:
            return None
        return (float(union.left()), float(union.top()),
                float(union.right()), float(union.bottom()))
    except Exception as e:
        _log.debug('虚拟屏矩形计算失败: %s', e)
        return None


class SoulOverlay(QWidget):
    """桌面上的那只 SOUL。默认**不显示**，宿主确认启用后才 `show()`。"""

    def __init__(self, parent=None, sprites=None, state=None,
                 on_clicked=None, on_drag_end=None, on_hide=None):
        super().__init__(parent)
        self.setObjectName('soulOverlay')
        # ⚠️ 不加 WindowStaysOnTopHint（见模块 docstring 约束 1）。
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # 灵魂要能拖、要能接键盘 ⇒ 必须可交互、可获焦。
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(False)

        self.state = state if state is not None else soul_mod.SoulState()
        self.sprites = sprites if sprites is not None else load_soul_sprites()
        self.on_clicked = on_clicked
        self.on_drag_end = on_drag_end
        self.on_hide = on_hide

        self._last_paint_index = None
        self.last_drawn = 0
        self._sync_size()
        self.hide()

    # ---------------------------------------------------------------- 几何
    def _sync_size(self):
        try:
            w, h = self.state.size
            if self.width() != w or self.height() != h:
                self.resize(max(1, w), max(1, h))
        except Exception as e:
            _log.debug('灵魂尺寸同步失败: %s', e)

    def apply_state_pos(self):
        """把 `state` 的位置写到窗口上。位置没变则不动窗口（省一次 SetWindowPos）。"""
        try:
            x, y = int(round(self.state.x)), int(round(self.state.y))
            if self.x() != x or self.y() != y:
                self.move(x, y)
        except Exception as e:
            _log.debug('灵魂移动失败: %s', e)

    def screen_bounds(self):
        return virtual_screen_rect(self)

    # ---------------------------------------------------------------- 推进
    def tick(self, dt):
        """推进一帧。返回 True 表示"状态变了"（位置/帧号）。"""
        try:
            moved = self.state.step(dt)
            self.state.tick_blink(dt)
            b = self.screen_bounds()
            if b:
                self.state.clamp_to(b)
            self.apply_state_pos()
            idx = self.state.image_index()
            repaint = (idx != self._last_paint_index)
            if repaint:
                self._last_paint_index = idx
                self.update()
            return bool(moved[0] or moved[1]) or repaint
        except Exception as e:
            _log.debug('灵魂推进失败（本帧跳过）: %s', e)
            return False

    def needs_tick(self):
        """是否需要继续按帧推进（宿主据此开/停定时器）。"""
        try:
            return self.state.needs_tick()
        except Exception:
            return False

    # ---------------------------------------------------------------- 鼠标
    def mousePressEvent(self, event):  # noqa: N802 (Qt 命名)
        try:
            if event.button() == Qt.LeftButton:
                p = event.globalPos()
                self.state.begin_drag(p.x(), p.y())
                # 抓住它 = 用户想操作它 ⇒ 给它焦点，方向键随即可用。
                try:
                    self.activateWindow()
                    self.setFocus(Qt.MouseFocusReason)
                except Exception as e:
                    _log.debug('灵魂取焦失败（忽略）: %s', e)
                self.update()
                event.accept()
                return
            if event.button() == Qt.RightButton:
                # 右键 = 收起（托盘菜单可以再叫出来）——比"再找一个入口"直观。
                if callable(self.on_hide):
                    try:
                        self.on_hide()
                    except Exception as e:
                        _log.debug('灵魂收起回调异常: %s', e)
                event.accept()
                return
        except Exception:
            _log.exception('灵魂按下处理异常（已忽略）')
        event.ignore()

    def mouseMoveEvent(self, event):  # noqa: N802 (Qt 命名)
        try:
            if not self.state.is_dragging:
                event.ignore()
                return
            p = event.globalPos()
            self.state.drag_to(p.x(), p.y())
            b = self.screen_bounds()
            if b:
                self.state.clamp_to(b)
            self.apply_state_pos()
            event.accept()
        except Exception:
            _log.exception('灵魂拖拽处理异常（已忽略）')

    def mouseReleaseEvent(self, event):  # noqa: N802 (Qt 命名)
        try:
            if event.button() != Qt.LeftButton or not self.state.is_dragging:
                event.ignore()
                return
            was_click = self.state.end_drag()
            self.apply_state_pos()
            self.update()
            if was_click and callable(self.on_clicked):
                self.on_clicked()
            elif callable(self.on_drag_end):
                self.on_drag_end()
            event.accept()
        except Exception:
            _log.exception('灵魂松开处理异常（已忽略）')

    # ---------------------------------------------------------------- 键盘
    def keyPressEvent(self, event):  # noqa: N802 (Qt 命名)
        """方向键 = 移动灵魂。

        ⚠️ `isAutoRepeat` 必须吃掉：Qt 在按住时会重复投递 press，
        而 `state.press` 对同一个键幂等 ⇒ 不影响正确性，但每次都会触发一次
        `event.accept()` 与一次 update 请求（无谓开销）。早退更干净。
        """
        try:
            if event.isAutoRepeat():
                event.accept()
                return
            d = direction_of_qt_key(event.key())
            if d is not None:
                self.state.press(d)
                event.accept()
                return
            if event.key() == Qt.Key_Escape:
                # Esc = 放开所有按键（"手滑卡住一直飞"的紧急出口）。
                self.state.clear_keys()
                event.accept()
                return
        except Exception:
            _log.exception('灵魂按键处理异常（已忽略）')
        event.ignore()

    def keyReleaseEvent(self, event):  # noqa: N802 (Qt 命名)
        try:
            if event.isAutoRepeat():
                event.ignore()
                return
            d = direction_of_qt_key(event.key())
            if d is not None:
                self.state.release(d)
                event.accept()
                return
        except Exception:
            _log.exception('灵魂松键处理异常（已忽略）')
        event.ignore()

    def focusOutEvent(self, event):  # noqa: N802 (Qt 命名)
        """失焦 ⇒ **放开所有键**。

        不做这件事的后果很具体：按住 → 切窗口（keyRelease 送到别的进程）
        ⇒ 灵魂永远朝那个方向飞，直到用户重新点它。这是本项目"按下/松开"
        类状态的通用教训（与 `mousePressEvent` 里 `_is_being_dragged`
        必须立刻置真同一个道理）。
        """
        try:
            if self.state.pressed():
                _log.info('灵魂失焦 ⇒ 放开按住的键 %s', ','.join(self.state.pressed()))
            self.state.clear_keys()
        except Exception:
            _log.exception('灵魂失焦处理异常（已忽略）')
        event.accept()

    # ---------------------------------------------------------------- 外显入口
    def press_dir(self, d):
        """供宿主（宠物窗口有焦点时）转发方向键。"""
        try:
            return bool(self.state.press(d))
        except Exception:
            return False

    def release_dir(self, d):
        try:
            return bool(self.state.release(d))
        except Exception:
            return False

    def release_all(self):
        try:
            return self.state.clear_keys()
        except Exception:
            return 0

    def show_soul(self, activate=False):
        """显示灵魂（并按需把它抬到前台）。**绝不置顶**。"""
        try:
            self._sync_size()
            self.show()
            self.apply_state_pos()
            if activate:
                try:
                    self.raise_()
                except Exception as e:
                    _log.debug('灵魂 raise_ 失败（忽略）: %s', e)
            self.update()
            return True
        except Exception:
            _log.exception('显示灵魂失败')
            return False

    def hide_soul(self):
        try:
            self.release_all()
            self.hide()
            return True
        except Exception:
            _log.exception('隐藏灵魂失败')
            return False

    # ---------------------------------------------------------------- 绘制
    def paintEvent(self, event):  # noqa: N802 (Qt 命名)
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
            idx = 0
            try:
                idx = int(self.state.image_index()) % max(1, len(self.sprites))
            except Exception:
                idx = 0
            pm = self.sprites[idx] if self.sprites else None
            r = self.rect()
            if pm is None or pm.isNull():
                p.setPen(QPen(MISSING_PEN))
                p.drawRect(r.adjusted(1, 1, -1, -1))
                self.last_drawn = 1
            else:
                p.drawPixmap(r, pm)
                self.last_drawn = 2
            p.end()
        except Exception as e:
            _log.debug('灵魂绘制异常（已忽略）: %s', e)

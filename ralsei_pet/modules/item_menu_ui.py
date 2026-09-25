# -*- coding: utf-8 -*-
"""S 键菜单的 Qt 外壳 —— 只画 `item_menu.MenuFrame` 给它的东西，不做任何判定。

分层（为什么切成两半）
----------------------
    item_menu.py    纯状态机：按键 → `MenuFrame`（零 Qt，可离线回归）
    item_menu_ui.py 纯绘制：`MenuFrame` → 屏幕上的一块面板（零判定）

判据与显示分开之后，离线套件可以断言"该给出的文案给了没"，
而不用起一个真窗口；UI 这边则不可能"自己发明一条规则"。

外观
----
面板**复用第44轮复刻的原作对话框框体** `modules/dr_textbox.DrTextboxFrame`
（纯黑内芯 + 32px 白边框 + 8 帧动画角，逐行对应反编译的 `scr_darkbox()`）。
理由：Deltarune 场内菜单本来就是这个黑框白边的家族，
用现成件比自己画一套更像原作，也少一份要维护的素材。

★ 光标列为什么不拼进正文
------------------------
原作用 `"> "` / `"  "` 前缀（`scr_84_draw_menu`）。若把前缀拼进一个文本标签，
**换字体就会错位**（原作的 fnt_main 与我们回落用的微软雅黑不是同一套度量）。
所以这里每一行拆成两列：定宽光标列 + 文本列 ⇒ 对齐与字体无关。

★ 置顶的取舍（**要改就改这里一个常量**）
----------------------------------------
`dialogue_ui` 的对话框是 `FramelessWindowHint | WindowStaysOnTopHint | Tool`
（第44轮就这样，已过审）。本面板跟它同族、同样是"临时浮层"，故沿用同一套标志。
⚠️ 仓库契约 §4.9 的「禁 `WindowStaysOnTopHint`」针对的是**建楼/宠物本体**
（不许把 Ralsei 钉在最前面），不是临时浮层 —— 两者别混。
若哪天真想让面板跟着宠物一起被别的窗口盖住，把 `PANEL_ALWAYS_ON_TOP` 改 False 即可。
"""
import logging
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPainter
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QVBoxLayout, QWidget)

import dr_textbox

try:
    from dialogue_ui import _load_ralsei_font      # 项目根像素字体（普通字体.ttf）
except Exception:                                   # pragma: no cover - 兜底
    _load_ralsei_font = None

_log = logging.getLogger(__name__)

#: 面板宽度（像素）。菜单最长的一行（"顶尖蛋糕（垃圾）"）在这个宽度里放得下。
PANEL_BASE_WIDTH = 330
#: 面板与宠物窗口的间距。
PANEL_MARGIN = 16
#: 光标列宽度 —— 定宽是"换字体不错位"的关键。
CURSOR_COL_W = 20
#: 正文字号。与原作 fnt_main（em=12）同量级。
BODY_POINT = 11
#: 标题字号。
TITLE_POINT = 12

#: ★ 见模块 docstring 的"置顶的取舍"。
PANEL_ALWAYS_ON_TOP = True

#: Qt 按键 → `item_menu` 的规范键名。**不含字母 S**（S 是全局热键，见 item_menu）。
_QT_KEY_MAP = {
    Qt.Key_Up: 'up', Qt.Key_Down: 'down', Qt.Key_Left: 'left', Qt.Key_Right: 'right',
    Qt.Key_W: 'up', Qt.Key_A: 'left', Qt.Key_D: 'right',
    Qt.Key_Return: 'confirm', Qt.Key_Enter: 'confirm', Qt.Key_Space: 'confirm',
    Qt.Key_Z: 'confirm',
    Qt.Key_Escape: 'cancel', Qt.Key_X: 'cancel', Qt.Key_Backspace: 'cancel',
}


def key_name_for_qt(key):
    """Qt 按键码 → `item_menu` 的规范键名；不认识返回 `None`（**不猜**）。

    给宿主用（主窗口的 `keyPressEvent` 转发按键时调它）——
    这样"哪个 Qt 键对应哪个动作"**只有一份定义**，宿主不必自己维护一张表。
    """
    return _QT_KEY_MAP.get(key)


def _as_rect4(value):
    """把矩形统一成 `(x, y, w, h)` 四元组；**认不出返回 None**。

    ★ 为什么必须兼容两种形状：宿主的 `_virtual_screen_rect()` 返回的是
    **`QRect`**（`x()/y()/width()/height()` 是方法），而回归测试里注入的是**元组**。
    第48轮实测踩过：离线探针喂元组全绿，真机喂 QRect 直接
    `TypeError: 'QRect' object is not subscriptable` ⇒ 菜单开不出来。
    （教训：假探针与真实契约必须一致，否则"测过了"是假的。）
    """
    if value is None:
        return None
    if isinstance(value, (tuple, list)) and len(value) >= 4:
        try:
            return tuple(int(v) for v in value[:4])
        except Exception:
            return None
    for names in (('x', 'y', 'width', 'height'), ('left', 'top', 'width', 'height')):
        try:
            return tuple(int(getattr(value, n)()) for n in names)
        except Exception:
            continue
    return None


def _font(point, bold=False):
    """拿项目像素字体；拿不到就退到系统字体（**如实退回，不假装**）。"""
    if _load_ralsei_font is not None:
        try:
            fam = _load_ralsei_font()
        except Exception:
            fam = None
        f = QFont(fam if fam else '微软雅黑', point)
        f.setBold(bool(bold))
        if fam:
            f.setStyleStrategy(QFont.NoAntialias)
        return f
    f = QFont('微软雅黑', point)
    f.setBold(bool(bold))
    return f


class ItemMenuUI(QWidget):
    """菜单浮层。宿主只调两个方法：`show_frame(frame)` 与 `handle_key(name)`。

    参数
    ----
    parent : QWidget | None
        只作所有权用（**不是**布局父级：本控件会把自己变成顶层窗口，
        否则 100×100 的主窗口会把菜单裁掉）。
    menu : item_menu.ItemMenu | None
        `handle_key()` 转发给它。
    on_message : callable(str) | None
        需要"弹一句话"时调用（宿主接到 `dialogue_ui`）。
        `None` ⇒ 只记日志（**不静默**：日志里能看到"这条文案本该弹出来"）。
    anchor : callable() -> (x, y, w, h) | None
        宠物窗口的屏幕矩形，用于把面板摆在宠物旁边。
    screen_rect : callable() -> (x, y, w, h) | None
        ★ 屏幕矩形**必须由宿主注入**：仓库契约①「`availableGeometry()` 只返主屏」，
        多屏下会算错，宿主的 `_virtual_screen_rect()` 才是唯一正确来源。
        没注入 ⇒ 退化成"不钳制"（只记警告）。
    """

    def __init__(self, parent=None, menu=None, on_message=None, anchor=None,
                 screen_rect=None):
        super(ItemMenuUI, self).__init__(parent)
        flags = Qt.FramelessWindowHint | Qt.Tool
        if PANEL_ALWAYS_ON_TOP:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle('Ralsei 菜单')

        self.menu = menu
        self.on_message = on_message
        self.anchor = anchor
        self.screen_rect = screen_rect

        self._last_msg = None
        self._rows = []          # [(marker_label, text_label)]
        self._build()

    # ------------------------------------------------------------------ 构建
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._frame = dr_textbox.DrTextboxFrame(self)
        outer.addWidget(self._frame)

        pad = dr_textbox.CONTENT_INSET
        col = QVBoxLayout(self._frame)
        col.setContentsMargins(pad, pad, pad, pad)
        col.setSpacing(4)

        self._title = QLabel('', self._frame)
        self._title.setFont(_font(TITLE_POINT, bold=True))
        self._title.setStyleSheet('color: #ffffff; background: transparent;')
        col.addWidget(self._title)

        # 行区：每帧重建（行数最多 12，重建很便宜；换来的是"光标列与文本列独立"）
        self._rows_box = QVBoxLayout()
        self._rows_box.setContentsMargins(0, 0, 0, 0)
        self._rows_box.setSpacing(1)
        col.addLayout(self._rows_box)

        self._hint = QLabel('', self._frame)
        self._hint.setFont(_font(BODY_POINT - 1))
        self._hint.setStyleSheet('color: #b9b9b9; background: transparent;')
        col.addWidget(self._hint)

        self.resize(PANEL_BASE_WIDTH, 120)
        self.hide()

    # ------------------------------------------------------------------ 渲染
    def _clear_rows(self):
        while self._rows_box.count():
            item = self._rows_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._rows = []

    def _add_row(self, marker, text):
        row = QWidget(self._frame)
        row.setAttribute(Qt.WA_TranslucentBackground)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        mk = QLabel(marker, row)
        mk.setFont(_font(BODY_POINT, bold=True))
        mk.setFixedWidth(CURSOR_COL_W)
        mk.setStyleSheet('color: #ffffff; background: transparent;')
        tx = QLabel(text, row)
        tx.setFont(_font(BODY_POINT))
        tx.setStyleSheet('color: #ffffff; background: transparent;')
        h.addWidget(mk)
        h.addWidget(tx, 1)
        self._rows_box.addWidget(row)
        self._rows.append((mk, tx))

    def show_frame(self, frame):
        """把一帧画出来。`frame.closed` ⇒ 收起来。返回是否仍可见。"""
        if frame is None:
            return self.isVisible()
        if frame.closed:
            self.hide()
            return False

        self._title.setText(frame.title or '')
        self._clear_rows()
        for i, line in enumerate(frame.lines or []):
            # ★ 前缀按 `item_menu` 给的成品行拆两列：前 2 字符是光标位。
            marker, text = line[:2], line[2:]
            self._add_row(marker, text)
        self._hint.setText(frame.hint or '')
        self._refit()
        self._place()

        if frame.message and frame.message != self._last_msg:
            self._last_msg = frame.message
            if self.on_message is not None:
                try:
                    self.on_message(frame.message)
                except Exception:
                    _log.exception('菜单文案推送失败（文案=%r）', frame.message)
            else:
                _log.info('菜单文案（未接 on_message，未能弹出）：%s', frame.message)
        if not frame.message:
            self._last_msg = None
        # 每帧重置消息去重键由调用方决定；这里用"内容变化"判重即可。

        if not self.isVisible():
            self.show()
        self.raise_()
        return True

    # ------------------------------------------------------------------ 交互
    def handle_key(self, name):
        """把一次按键交给状态机，并立刻把结果画出来。"""
        if self.menu is None:
            return False
        frame = self.menu.key(name)
        self.show_frame(frame)
        return True

    def keyPressEvent(self, event):                      # noqa: N802 (Qt 命名)
        name = _QT_KEY_MAP.get(event.key())
        if name is None:
            event.ignore()                               # ★ 不认识的键**原样放过**
            return
        self.handle_key(name)
        event.accept()

    def is_open(self):
        return bool(self.isVisible())

    def close_panel(self):
        if self.menu is not None:
            frame = self.menu.close()
            self.show_frame(frame)
        else:
            self.hide()

    # ------------------------------------------------------------------ 几何
    def _refit(self):
        """按内容调整尺寸（宽度固定，高度随行数）。"""
        self._frame.layout().activate()
        h = self.sizeHint().height()
        h = max(h, dr_textbox.BAND * 2 + 8)
        self.resize(PANEL_BASE_WIDTH, h)

    def _place(self):
        """摆到宠物旁边，并钳制在屏幕内（屏幕矩形由宿主注入，见契约①）。

        ⚠️ `anchor()` / `screen_rect()` 的返回值形状**两种都吃**（元组 / QRect）——
        见 `_as_rect4` 的说明（真机 QRect ⇒ 曾经崩在这里）。
        """
        r = None
        if self.anchor is not None:
            try:
                r = _as_rect4(self.anchor())
            except Exception:
                _log.exception('anchor() 取宠物矩形失败（不摆位，按默认位置显示）')
        if r is None:
            return
        ax, ay, aw, ah = r
        x = ax + aw + PANEL_MARGIN
        y = ay - self.height() // 2
        scr = None
        if self.screen_rect is not None:
            try:
                scr = _as_rect4(self.screen_rect())
            except Exception:
                _log.exception('screen_rect() 失败（不做钳制）')
        if scr:
            sx, sy, sw, sh = scr
            if x + self.width() > sx + sw:
                x = ax - PANEL_MARGIN - self.width()   # 右边放不下 ⇒ 摆左边
            x = max(sx, min(x, sx + sw - self.width()))
            y = max(sy, min(y, sy + sh - self.height()))
        self.move(x, y)

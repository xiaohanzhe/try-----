# -*- coding: utf-8 -*-
u"""dr_choice.py —— **三角符文风格的选择框**（第118轮）。

用户口径（逐字，10-19）
----------------------
「你要按照**三角符文的那选择**来啊，**不是干巴巴的弹窗**」

背景：第111轮「Niko 的家」彩蛋用 `QMessageBox` 做三连确认 —— 那是**系统弹窗**
（标题栏 + 问号图标 + 系统按钮），与这个产品"把原作搬到桌面上"的整体调性冲突。
原作里做选择的样子是：**一块黑色对话框** + 选项逐行排列 + 一只**红色灵魂**停在你
选中的那行左边，方向键上下移动、确认键落定。

本模块就把那个样子做出来：
  · 框体 = `dr_textbox.paint_dark_box_scaled()`（**同一份**原作框体几何，
    角上的宝石会以 30fps 逐帧闪 —— 这就是原作框的"活"的那部分）；
  · 光标 = `assets/soul/spr_heart_0.png`（原作 `spr_heart`，与桌面灵魂同一个素材）；
  · 键位 = ↑/↓（W/S 不接，`S` 是菜单键）、Enter / 空格 / Z 确认、Esc / X 取消；
  · 鼠标 = 左键选行、双击确认（不抢键盘习惯，只是补一条更顺手的路）。

★ 零项目内依赖（只依赖 `dr_textbox`，而它本身就是纯绘制层）：
  这样它可以被任何需要"原作式选择"的地方复用（将来 NPC 对话选项也用同一份）。
★ **禁 `WindowStaysOnTopHint`**（本项目铁律，第13轮 `E1` 守着它）：
  选择框是模态对话框，`exec_()` 期间本来就压在上面，不需要抢 z 序。
"""
import os

from PyQt5 import QtCore, QtGui, QtWidgets

try:
    from logger_utils import get_logger
    _log = get_logger(__name__)
except Exception:                                                # noqa: BLE001
    import logging
    _log = logging.getLogger(__name__)

try:
    from . import dr_textbox as _box
except (ImportError, ValueError):                                # 独立脚本导入
    import dr_textbox as _box                                     # type: ignore

#: 行高（未缩放，逻辑像素）与左右内边距 —— 与原作框的文字内缩同源。
LINE_H = 34
PAD_X = 30
PAD_Y = 22

#: 心形光标相对文字基线的垂直微调（视觉居中）。
HEART_DY = 2


def _assets_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'assets')


_SPRITES = None


def heart_pixmap():
    u"""红心光标（Soul）贴图；取不到 ⇒ `None`（如实降级成"用文字箭头"）。"""
    global _SPRITES
    if _SPRITES is None:
        p = os.path.join(_assets_dir(), 'soul', 'spr_heart_0.png')
        _SPRITES = QtGui.QPixmap(p) if os.path.isfile(p) else QtGui.QPixmap()
    return _SPRITES if not _SPRITES.isNull() else None


class DrChoiceBox(QtWidgets.QDialog):
    u"""一块原作式选择框：`options` 逐行、灵魂停在你选的那行。

    ★ `exec_()` 返回时：`self.picked` = 选中下标（取消 ⇒ `cancel_index`，
      没给 `cancel_index` 则返回 -1）。
    """

    def __init__(self, parent=None, options=None, scale=1.0, default_index=0,
                 cancel_index=None, prompt=None):
        super(DrChoiceBox, self).__init__(parent)
        self._opts = [str(o) for o in (options or [])]
        self._scale = max(0.5, min(3.0, float(scale or 1.0)))
        self.picked = -1
        self._cancel_index = cancel_index
        self._prompt = prompt
        self._tick = 0
        n = max(1, len(self._opts))
        self._sel = max(0, min(n - 1, int(default_index)))

        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.FramelessWindowHint
                            | QtCore.Qt.NoDropShadowWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        # ---- 几何（未缩放 W/H 交给 paint_dark_box_scaled 按 scale 放大）----
        fm = QtGui.QFontMetrics(self._font())
        w = max([fm.width(t) for t in self._opts] + [220]) + PAD_X * 2 + int(34 * self._scale)
        h = LINE_H * n + PAD_Y * 2
        if self._prompt:
            h += LINE_H
        self._w0, self._h0 = int(w), int(h)
        self.resize(int(round(self._w0 * self._scale)), int(round(self._h0 * self._scale)))
        self._place(parent)

        # 宝石逐帧（原作 30fps；`jewel_frame` 每 10 tick 换一帧）
        self._tm = QtCore.QTimer(self)
        self._tm.timeout.connect(self._on_tick)
        self._tm.start(33)

    # ---------------------------------------------------------------- 外观
    def _font(self, bold=False):
        f = QtGui.QFont('微软雅黑')
        f.setPixelSize(max(10, int(round(15 * self._scale))))
        f.setBold(bool(bold))
        return f

    def _place(self, parent):
        u"""摆位：**贴屏幕底部偏上**（原作选择框就在对话区上方），水平居中。

        ★ 拿不到屏幕 ⇒ 居中到 parent 上方；都没有 ⇒ 屏幕正中（宁可难看也不崩）。
        """
        try:
            if parent is not None and hasattr(parent, 'ui_scale'):
                pass
            scr = QtWidgets.QApplication.primaryScreen()
            g = scr.availableGeometry() if scr is not None else None
            w, h = self.width(), self.height()
            if g is not None:
                x = g.center().x() - w // 2
                y = g.bottom() - h - int(120 * self._scale)
                self.move(max(g.left(), x), max(g.top(), y))
                return
        except Exception as e:                                   # noqa: BLE001
            _log.debug('dr_choice 摆位失败（改居中）: %s', e)
        try:
            if parent is not None:
                c = parent.frameGeometry().center()
                self.move(c.x() - self.width() // 2, c.y() - self.height() // 2 - 80)
        except Exception:                                        # noqa: BLE001
            pass

    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        try:
            p.setRenderHint(QtGui.QPainter.Antialiasing, True)
            s = self._scale
            w, h = self.width(), self.height()
            # ★ 原作框体（宝石动画同一份真源）
            _box.paint_dark_box_scaled(p, 0, 0, w, h, _box.jewel_frame(self._tick), s)
            f = self._font()
            p.setFont(f)
            fm = QtGui.QFontMetrics(f)
            line_h = int(round(LINE_H * s))
            y = int(round(PAD_Y * s))
            if self._prompt:
                p.setPen(QtGui.QColor(215, 215, 215))
                p.drawText(int(round((PAD_X - 10) * s)), y + fm.ascent() + 4, self._prompt)
                y += line_h
            hx = int(round(14 * s))
            heart = heart_pixmap()
            hsize = max(8, int(round(16 * s)))
            for i, text in enumerate(self._opts):
                sel = (i == self._sel)
                base = y + i * line_h + fm.ascent() + int(round(4 * s))
                tx = int(round((PAD_X + 22) * s))
                if sel:
                    p.setPen(QtGui.QColor(255, 255, 255))
                    f2 = self._font(bold=True)
                    p.setFont(f2)
                else:
                    p.setPen(QtGui.QColor(150, 150, 150))
                    p.setFont(f)
                p.drawText(tx, base, text)
                if sel:
                    p.setFont(f)
                    if heart is not None:
                        p.drawPixmap(hx, base - fm.ascent() - int(round(HEART_DY * s)),
                                     heart.scaled(hsize, hsize, QtCore.Qt.KeepAspectRatio,
                                                  QtCore.Qt.SmoothTransformation))
                    else:                                        # 兜底：文字光标
                        p.setPen(QtGui.QColor(255, 60, 60))
                        p.drawText(hx, base, u'♥')
        finally:
            p.end()

    # ---------------------------------------------------------------- 交互
    def _on_tick(self):
        self._tick += 1
        self.update()

    def keyPressEvent(self, ev):
        k = ev.key()
        n = len(self._opts)
        if k in (QtCore.Qt.Key_Up,):
            self._sel = (self._sel - 1) % n
            self.update()
            ev.accept()
            return
        if k in (QtCore.Qt.Key_Down,):
            self._sel = (self._sel + 1) % n
            self.update()
            ev.accept()
            return
        if k in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Space,
                 QtCore.Qt.Key_Z):
            self.picked = self._sel
            self.accept()
            return
        if k in (QtCore.Qt.Key_Escape, QtCore.Qt.Key_X):
            self.picked = (self._cancel_index if self._cancel_index is not None else -1)
            self.reject()
            return
        ev.ignore()

    def mousePressEvent(self, ev):
        try:
            s = self._scale
            line_h = int(round(LINE_H * s))
            y = int(round(PAD_Y * s))
            if self._prompt:
                y += line_h
            i = int((ev.pos().y() - y) // max(1, line_h))
            if 0 <= i < len(self._opts):
                self._sel = i
                self.update()
                ev.accept()
                return
        except Exception:                                        # noqa: BLE001
            pass
        super(DrChoiceBox, self).mousePressEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        self.picked = self._sel
        self.accept()


def choose(parent, options, scale=1.0, default_index=0, cancel_index=None,
           prompt=None):
    u"""弹一块原作式选择框，返回**选中下标**。

    :param cancel_index: 按 Esc/X 时返回什么（不给 ⇒ `-1`）。
    :returns: 下标；异常/空选项 ⇒ `cancel_index`（保守：等于"没选确定"）。
    ★ 任何异常都**不**退回系统弹窗（用户明确否掉了"干巴巴的弹窗"）；
      只记日志并返回取消值 —— 调用方按"没选确定"处理。
    """
    if not options:
        return (cancel_index if cancel_index is not None else -1)
    try:
        dlg = DrChoiceBox(parent, options, scale=scale, default_index=default_index,
                          cancel_index=cancel_index, prompt=prompt)
        dlg.exec_()
        return dlg.picked
    except Exception as e:                                       # noqa: BLE001
        _log.exception('dr_choice 选择框不可用（按"取消"处理）: %s', e)
        return (cancel_index if cancel_index is not None else -1)

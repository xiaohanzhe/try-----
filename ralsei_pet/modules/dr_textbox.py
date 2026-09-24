"""原作 Deltarune 对话框（textbox）渲染 —— 按反编译源码逐行复刻。

依据（第 44 轮反编译 chapter1_windows/data.win，源码见
`code-quality-audit/第44轮-原作对话框复刻/_evidence/gml_GlobalScript_scr_darkbox.gml`）：

    function scr_darkbox(arg0, arg1, arg2, arg3)      // (x1, y1, x2, y2)
    {
        cur_jewel += 1;
        textbox_width  = arg2 - arg0 - 63;            // 63 = 2*32 - 1
        textbox_height = arg3 - arg1 - 63;
        if (textbox_width > 0) {
            draw_sprite_stretched(spr_textbox_top, 0, arg0 + 32, arg1, textbox_width, 32);
            draw_sprite_ext(spr_textbox_top, 0, arg0 + 32, arg3 + 1, textbox_width, -2, 0, c_white, 1);
        }
        if (textbox_height > 0) {
            draw_sprite_ext(spr_textbox_left, 0, arg2 + 1, arg1 + 32, -2, textbox_height, 0, c_white, 1);
            draw_sprite_ext(spr_textbox_left, 0, arg0, arg1 + 32, 2, textbox_height, 0, c_white, 1);
        }
        draw_sprite_ext(spr_textbox_topleft, cur_jewel / 10, arg0, arg1, 2, 2, 0, c_white, 1);
        draw_sprite_ext(spr_textbox_topleft, cur_jewel / 10, arg2 + 1, arg1, -2, 2, 0, c_white, 1);
        draw_sprite_ext(spr_textbox_topleft, cur_jewel / 10, arg0, arg3 + 1, 2, -2, 0, c_white, 1);
        draw_sprite_ext(spr_textbox_topleft, cur_jewel / 10, arg2 + 1, arg3 + 1, -2, -2, 0, c_white, 1);
    }
    // ★ 原文这里还包着一层 `if (global.flag[8] == 0) { 上面那 4 行动画 } else { 同样 4 行但帧号写死 0 }`
    //   ⇒ flag[8] != 0 时四角**静止在第 0 帧**。桌宠没有 flag 体系，用
    //   `DrTextboxFrame.set_animation_enabled()` 表达同一语义（默认开 = flag[8]==0）。
}

配套参数（`obj_dialoguer` + `scr_texttype` typer=5 + `scr_textsetup`）：
    · 字体 `fnt_main`（8bitoperator JVE, em=12）、颜色 c_white、`draw_text_shadow`（黑影 +1,+1 再白字）
    · `rate = 1` ⇒ 打字机约 1 字符/帧 @30fps ≈ 33 ms/字
    · hspace=8 / vspace=18 / charline=33 / special=0
    · 文字相对框左上的内缩 = 34 px（= 32 边框 + 2）：`obj_dialoguer_Other_10` 里
      `xx = 19*f + view_x`、`yy = 20*f + view_y`，writer 建在 `xx + 10*f`；
      框左边界 = `xxx + 32 - 8` 且 xxx == view_x ⇒ 相对占位差 32+2 = 34。
    · 黑底：`scr_dbox` 用 `draw_rectangle` 各内缩 14 px（与边框图案的黑色段落对齐）——
      推导：框矩形 = (xxx+32-8, yyy+10-8)..(xxx+608+8, yyy+160+8)，
      黑矩形 = (xxx+38, yyy+16)..(xxx+602, yyy+154) ⇒ 四条边各差 14。
    · 打字音：`scr_textsound()` 里空格与标点（`& " " ^ ! . ? , : / \ | *`）静音。
"""

import os

from PyQt5.QtCore import Qt, QRect, QTimer
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtWidgets import QWidget

try:
    from logger_utils import get_logger
except ImportError:  # 允许被包外单独导入
    import logging

    def get_logger(name):
        return logging.getLogger(name)

_log = get_logger(__name__)

# ---------------------------------------------------------------------------
# 原作常量（全部来自反编译实测，勿凭感觉改）
# ---------------------------------------------------------------------------
BAND = 32                  # 边框带厚度 = 2 帧缩放 × 16px 精灵
STRETCH_GAP = 63           # 原作减数：2 * 32 - 1
CORNER_SIZE = 32           # 角块实绘尺寸 = 16px 精灵 × 2
BLACK_INSET = 14           # 黑底相对框矩形各内缩
CORNER_FRAMES = 8          # spr_textbox_topleft 共 8 帧
JEWEL_TICKS_PER_FRAME = 10  # 帧号 = cur_jewel / 10 ⇒ 每 10 帧换一帧
ENGINE_FPS = 30            # data.win GeneralInfo.GMS2FPS
TYPE_INTERVAL_MS = round(1000.0 / ENGINE_FPS)   # 33 ms/字（rate = 1）
CONTENT_INSET = BAND + 2   # 文字相对框左上内缩（原作实测 34）

ASSET_SUBPATH = os.path.join('assets', 'ui', 'textbox')
CORNER_FMT = 'spr_textbox_topleft_%d.png'
TOP_NAME = 'spr_textbox_top_0.png'
LEFT_NAME = 'spr_textbox_left_0.png'


def jewel_frame(tick):
    """cur_jewel / 10 的等价：每 JEWEL_TICKS_PER_FRAME 帧前进一帧，8 帧循环。"""
    return (int(tick) // JEWEL_TICKS_PER_FRAME) % CORNER_FRAMES


def textbox_metrics(x1, y1, x2, y2):
    """等价原作的 textbox_width / textbox_height（含下限 0 钳制）。"""
    w = (x2 - x1) - STRETCH_GAP
    h = (y2 - y1) - STRETCH_GAP
    return (w if w > 0 else 0), (h if h > 0 else 0)


def assets_dir():
    """对话框素材目录：<repo>/ralsei_pet/assets/ui/textbox。"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, '..', ASSET_SUBPATH)


class TextboxSprites(object):
    """素材容器：一次性加载 + 预翻转（原作靠负 scale 翻转，这里预生成等价图）。"""

    def __init__(self, base_dir=None):
        self.base = base_dir or assets_dir()
        self._corner = []
        self._corner_h = []
        self._corner_v = []
        self._corner_hv = []
        self._top = None
        self._top_v = None
        self._left = None
        self._left_h = None
        self.loaded = False
        self.missing = []

    # -- 内部：加载 ------------------------------------------------------
    def _pm(self, name):
        p = os.path.join(self.base, name)
        if not os.path.exists(p):
            self.missing.append(name)
            return None
        pm = QPixmap(p)
        if pm.isNull():
            self.missing.append(name)
            return None
        pm.setDevicePixelRatio(1.0)   # 像素图按 1:1 绘制，禁平滑缩放
        return pm

    def load(self):
        if self.loaded:
            return self
        for i in range(CORNER_FRAMES):
            pm = self._pm(CORNER_FMT % i)
            if pm is None:
                pm = QPixmap(CORNER_SIZE // 2, CORNER_SIZE // 2)
                pm.fill(Qt.transparent)
            self._corner.append(pm)
            img = pm.toImage()
            self._corner_h.append(QPixmap.fromImage(img.mirrored(True, False)))
            self._corner_v.append(QPixmap.fromImage(img.mirrored(False, True)))
            self._corner_hv.append(QPixmap.fromImage(img.mirrored(True, True)))
        self._top = self._pm(TOP_NAME) or QPixmap(1, 16)
        self._left = self._pm(LEFT_NAME) or QPixmap(16, 1)
        img_t = self._top.toImage()
        img_l = self._left.toImage()
        self._top_v = QPixmap.fromImage(img_t.mirrored(False, True))
        self._left_h = QPixmap.fromImage(img_l.mirrored(True, False))
        self.loaded = True
        if self.missing:
            _log.warning("dr_textbox 缺少素材: %s", self.missing)
        return self

    # -- 取值 -----------------------------------------------------------
    def corner(self, frame, hflip=False, vflip=False):
        self.load()
        f = int(frame) % CORNER_FRAMES
        if hflip and vflip:
            return self._corner_hv[f]
        if hflip:
            return self._corner_h[f]
        if vflip:
            return self._corner_v[f]
        return self._corner[f]

    def top(self, vflip=False):
        self.load()
        return self._top_v if vflip else self._top

    def left(self, hflip=False):
        self.load()
        return self._left_h if hflip else self._left


_SPRITES = None


def default_sprites():
    global _SPRITES
    if _SPRITES is None:
        _SPRITES = TextboxSprites().load()
    return _SPRITES


# ---------------------------------------------------------------------------
# 绘制：等价 scr_darkbox
# ---------------------------------------------------------------------------
def darkbox_blits(x1, y1, x2, y2, frame):
    """返回 [(kind, rect_args, which)] —— 纯几何，供测试与绘制共用。

    kind = 'fill'（黑底）| 'top' | 'top_v' | 'left' | 'left_h' | 'corner'
    which = corner 的 (hflip, vflip)
    """
    w, h = textbox_metrics(x1, y1, x2, y2)
    out = [('fill', (x1 + BLACK_INSET, y1 + BLACK_INSET,
                     (x2 - x1) - 2 * BLACK_INSET, (y2 - y1) - 2 * BLACK_INSET))]
    if w > 0:
        out.append(('top', (x1 + BAND, y1, w, BAND)))
        out.append(('top_v', (x1 + BAND, y2 + 1 - BAND, w, BAND)))
    if h > 0:
        out.append(('left_h', (x2 + 1 - BAND, y1 + BAND, BAND, h)))
        out.append(('left', (x1, y1 + BAND, BAND, h)))
    out.append(('corner', (x1, y1, CORNER_SIZE, CORNER_SIZE), (False, False)))
    out.append(('corner', (x2 + 1 - CORNER_SIZE, y1, CORNER_SIZE, CORNER_SIZE), (True, False)))
    out.append(('corner', (x1, y2 + 1 - CORNER_SIZE, CORNER_SIZE, CORNER_SIZE), (False, True)))
    out.append(('corner', (x2 + 1 - CORNER_SIZE, y2 + 1 - CORNER_SIZE,
                           CORNER_SIZE, CORNER_SIZE), (True, True)))
    return out


def paint_dark_box(painter, x1, y1, x2, y2, frame, sprites=None):
    """等价 scr_darkbox：黑底 + 上下 top / 左右 left / 四角 topleft[frame]。

    只使用 painter.fillRect / painter.drawPixmap 两个原语，便于测试注入假画笔。
    """
    sp = sprites or default_sprites()
    painter.fillRect(QRect(int(x1 + BLACK_INSET), int(y1 + BLACK_INSET),
                           int((x2 - x1) - 2 * BLACK_INSET),
                           int((y2 - y1) - 2 * BLACK_INSET)), QColor(0, 0, 0))
    for item in darkbox_blits(x1, y1, x2, y2, frame):
        kind = item[0]
        r = item[1]
        rect = QRect(int(r[0]), int(r[1]), int(r[2]), int(r[3]))
        if kind == 'fill':
            continue
        if kind == 'top':
            pm = sp.top(False)
        elif kind == 'top_v':
            pm = sp.top(True)
        elif kind == 'left':
            pm = sp.left(False)
        elif kind == 'left_h':
            pm = sp.left(True)
        else:
            hf, vf = item[2]
            pm = sp.corner(frame, hf, vf)
        painter.drawPixmap(rect, pm)


class DrTextboxFrame(QWidget):
    """自绘原作对话框：黑底 + 32px 白边框 + 8 帧动画角。

    只负责"画框"；内容布局由调用方按 CONTENT_INSET 内缩摆放。
    """

    CONTENT_INSET = CONTENT_INSET

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("drTextbox")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._tick = 0
        self._frame = 0
        self._sprites = None
        self._timer = QTimer(self)
        self._timer.setInterval(TYPE_INTERVAL_MS)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    # -- 动画 -----------------------------------------------------------
    def _advance(self):
        self._tick += 1
        f = jewel_frame(self._tick)
        if f != self._frame:
            self._frame = f
            self.update()

    def current_frame(self):
        return self._frame

    def set_animation_enabled(self, enabled):
        """等价原作 `scr_darkbox` 里的 `global.flag[8]` 门控。

        原作：`global.flag[8] == 0` → 四角取 `cur_jewel/10`（动画）；
        非 0 → 四角固定取第 0 帧（静止）。桌宠没有 flag 体系，改用本开关表示
        "停止角饰动画"；**默认开启**（与 flag[8]==0 一致）。
        隐藏时由 hideEvent 自动停表 —— 对话框大部分时间是不可见的（20s 自动
        隐藏），停表省掉 33ms×N 的空转重绘。
        """
        if enabled:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    def animation_enabled(self):
        return self._timer.isActive()

    # -- 生命周期：不可见时不必空转 --------------------------------------
    def hideEvent(self, event):  # noqa: N802
        self.set_animation_enabled(False)
        super().hideEvent(event)

    def showEvent(self, event):  # noqa: N802
        self.set_animation_enabled(True)
        super().showEvent(event)

    # -- 绘制 -----------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802 (Qt 命名)
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
            paint_dark_box(p, 0, 0, self.width(), self.height(),
                           self._frame, self._sprites)
            p.end()
        except Exception as e:  # 防御性：绘制失败不能拖垮主窗口
            _log.debug("dr_textbox 绘制异常（已忽略）: %s", e)

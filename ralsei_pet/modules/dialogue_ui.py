"""Ralsei 对话框 UI — Deltarune 风格。

外部 API（main.py 调用的）保持不变：
    add_dialogue(speaker, message, face_type="normal")
    show_dialogue(message=None)
    hide_dialogue()
    send_message()
    stop_typing()
    handle_chat_commands(user_input) -> str|None
    handle_file_commands(user_input) -> str|None
"""
import os

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QTextEdit, QPushButton, QFrame, QSizePolicy,
                             QApplication, QGraphicsDropShadowEffect)
from PyQt5.QtGui import QFont, QColor, QFontDatabase
from PyQt5.QtCore import Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve, QRect

try:
    from logger_utils import get_logger
except ImportError:  # 允许被包外单独导入
    import logging

    def get_logger(name):
        return logging.getLogger(name)

try:
    from conversation_focus import ConversationFocus
except ImportError:  # 允许被包外单独导入（如单测直接跑本文件）
    import os as _os
    import sys as _sys
    _sys.path.append(_os.path.dirname(_os.path.abspath(__file__)))
    try:
        from conversation_focus import ConversationFocus
    except ImportError:
        ConversationFocus = None

try:
    import dr_textbox as _drbox
except ImportError:  # 允许被包外单独导入（如单测直接跑本文件）
    import os as _os2
    import sys as _sys2
    _sys2.path.append(_os2.path.dirname(_os2.path.abspath(__file__)))
    import dr_textbox as _drbox

_log = get_logger(__name__)


# ---------------------------------------------------------------------------
# 加载项目根目录下的"普通字体.ttf"，作为 Ralsei 说话字体（全局注册一次）
# ---------------------------------------------------------------------------
_FONT_FAMILY = None
def _load_ralsei_font():
    global _FONT_FAMILY
    if _FONT_FAMILY is not None:
        return _FONT_FAMILY
    try:
        _root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..'))
        path = os.path.join(_root, '普通字体.ttf')
        if os.path.exists(path):
            fid = QFontDatabase.addApplicationFont(path)
            if fid != -1:
                families = QFontDatabase.applicationFontFamilies(fid)
                if families:
                    _FONT_FAMILY = families[0]
    except Exception as e:  # 修复：原先静默吞噬
        _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
    return _FONT_FAMILY


# 像素字体是否关闭抗锯齿：原作 fnt_main 是位图字体（8bitoperator JVE），
# 关掉 AA 才有同等锐利感。置 False 可回退到平滑渲染（对照用）。
_PIXEL_NOAA = True


def _ralsei_font(point_size, bold=False):
    """对话框用字体：优先项目根的像素字体（`普通字体.ttf` = FZXS12）。"""
    fam = _load_ralsei_font()
    f = QFont(fam if fam else "微软雅黑", point_size)
    f.setBold(bool(bold))
    if fam and _PIXEL_NOAA:
        f.setStyleStrategy(QFont.NoAntialias)
    else:
        f.setStyleStrategy(QFont.PreferAntialias)
    return f


# 原作 scr_textsound() 的规则：这些字符**不**播打字音（空格与标点）。
# 原文逐个 if 列出 12 个：`&` `" "` `^` `!` `.` `?` `,` `:` `/` `\` `|` `*`
# （`\` 在源码里写作 `"\\"`）。中文正文用的是全角标点，故一并补上。
_TEXT_SOUND_SKIP = frozenset(
    " &^!?.,:/\|*"                     # 原作 ASCII 表（12 个，含 ?）
    "　，。！？：；、…—～·「」『』（）《》〈〉“”‘’"  # 全角/中文标点
)


def _should_play_text_sound(ch):
    """等价 scr_textsound 的 play 判定：空格与标点静音。"""
    if not ch:
        return False
    return ch not in _TEXT_SOUND_SKIP


# ---------------------------------------------------------------------------
# 表情类型 → 素材文件名（不含 .png）。全部走 sprite_loader.get_face() 加载。
# ---------------------------------------------------------------------------
_FACE_MAP = {
    # 兜底
    "normal": "face_normal",
    "neutral": "face_normal",
    # 开心
    "happy": "face_happy_very",
    "happy_extremely": "face_happy_extremely",
    "happy_very": "face_happy_very",
    "laughing": "face_happy_very",
    "playful": "face_happy and playful",
    # 感动 / 关心 / 感激
    "caring": "face_shy with touched and happy",
    "grateful": "face_shy with touched and happy",
    "touched": "face_shy with touched and happy",
    # 满足 / 平静
    "content": "face_normal_smile_little",
    "peaceful": "face_normal_smile_little",
    "calm": "face_normal_smile_little",
    "sleepy": "face_normal_smile_little",
    # 乐于助人（友好微笑）
    "helpful": "face_happy_very",
    # 微笑
    "normal_smile_little": "face_normal_smile_little",
    "normal_smile": "face_normal_smile_little",
    # 鼓励（游戏失败等场景的安抚微笑）。
    # 修复：此前无此键，_resolve_face_name 兜底拼成不存在的 face_encouraging，
    # 头像渲染成灰色"?"占位图（entertainment_system 游戏失败分支触发）。
    "encouraging": "face_normal_smile_little",
    # 惊讶
    "surprised": "face_a little surprised",
    "surprised_strong": "face_unexpected and surprise",
    # 害羞
    "shy": "face_shy with a little surprised and happy",
    "shy_happy": "face_shy with a lot of happy",
    "blushing": "face_shy with a little surprised and happy",
    # 思考
    "curious": "face_a little confusion and cute",
    "thinking": "face_contemplation",
    "confused": "face_a little confusion and cute",
    # 担忧
    "concerned": "face_worry",
    "concerned_fear": "face_worry with a fear",
    "worry": "face_worry",
    "worried": "face_worry",
    # 兴奋
    "excited": "face_excited and cute",
    # 悲伤
    "sad": "face_a little sad",
    "a little sad": "face_a little sad",
    "unhappy": "face_a little sad",
    "sad_hopeless": "face_sad with a little hopeless",
    "sad_force_smile": "face_sad but force a smile",
    "depressed": "face_depression with a little hopeless",
    # 恐惧
    "fear": "face_fear",
    "scared": "face_fear",
    "afraid": "face_fear",
    "fear_firm": "face_fear but firm",
    # 生气
    "angry": "face_frightened with a little angry",
    # 严肃
    "serious": "face_serious",
    "firm": "face_firm and serious",
    # 疲惫
    "tired": "face_depression with a little hopeless",
}


def _resolve_face_name(face_type):
    """把各种输入（带 .png、完整路径、表情关键字）统一解析成素材名。"""
    if not face_type:
        return "face_normal"
    # 如果是文件名（含 .png），去掉后缀直接用
    if isinstance(face_type, str) and face_type.endswith(".png"):
        return os.path.splitext(os.path.basename(face_type))[0]
    # 已经带 face_ 前缀，直接用
    if isinstance(face_type, str) and face_type.startswith("face_"):
        return face_type
    # 查表
    if face_type in _FACE_MAP:
        return _FACE_MAP[face_type]
    # 兜底：emotion_system 返回的不带 face_ 前缀的素材名，补上前缀
    return "face_" + face_type


class DialogueUI(QWidget):
    # 本地 AI 思考占位文本（Ralsei 式的省略号 + 思考表情，不暴露"在调模型"，
    # 让等待回复显得像普通的停顿组织语言；识别它以避免被当作正式回复写进历史）
    AI_THINKING_PLACEHOLDER = "……"

    # 自动隐藏：每次对话活动后等这么久没有任何新动静，就把对话框淡出收起。
    # 用户要求（第九轮）："对话框在 20s 内不输入会自动消失哦，但一旦鼠标点
    # 在输入栏上那就不能消失"。所以 20 秒是"无输入"的窗口，而"输入栏被点住/
    # 光标停在输入栏上/模型正在思考"都属于**有动静**，一律不隐藏。
    AUTO_HIDE_MS = 20000
    # 输入栏被鼠标压住时的复查间隔（压着就一直延后，松开后重新计时）
    AUTO_HIDE_RECHECK_MS = 1000

    # 什么算"正在聊天"：最近一次对话活动（用户输入/模型回复）在这个窗口内。
    # 10 分钟自主开口闸门用它来避免"聊到一半突然插一句自己的话题"。
    ACTIVE_CONVERSATION_SECONDS = 150.0

    # ------------------------------------------------------------------
    # 原作对话框几何（第 44 轮，反编译实证，细则见 modules/dr_textbox.py）
    #   BOX_INSET = 34px —— 原作里文字相对框左上角的内缩（32 边框 + 2）
    #   BASE_WIDTH/MIN_BOX_HEIGHT —— 为容纳 32px 边框带而放大的基准尺寸
    # ------------------------------------------------------------------
    BOX_INSET = _drbox.CONTENT_INSET
    BASE_WIDTH = 620
    MIN_BOX_HEIGHT = 220

    # ------------------------------------------------------------------
    # 第十八轮 · 关键词指令的命中规则分两类
    #
    # 旧实现一律 `kw in raw` 纯子串匹配，于是：
    #   "我快哭了"          → 被「哭」截胡 → "呜... 为什么要让我哭嘛..."
    #   "我做的游戏上线了"  → 被「游戏」截胡 → "我最喜欢玩游戏了！想玩什么呢？"
    #   "我状态不太好"      → 被「状态」截胡 → 播报情绪/精力/饥饿
    # 用户感受就是"很死板"。诊断见 Ralsei对话人味诊断与训练方案_2026-09-18.md §E6。
    #
    # 拆法：
    #   · **_HARD_CMDS**（下表所列）：真正驱动状态机/动作的指令，保持子串命中 ——
    #     用户说"你去睡觉吧"也得能退出去睡觉。这些**不能**交给 AI，否则动作不会发生。
    #   · 其余（天气/状态/精力/游戏/跳舞/唱歌/哭/喝茶…）：只是"说一句罐头话"，
    #     收紧为**指令式命中**（见 _is_command_phrase），否则放行给 AI 自由回答。
    #     放行后 AI 依然答得上 —— `_build_ai_context()` 已经把时段/天气/心情/
    #     精力/饥饿都注进 system 了。
    _HARD_CMDS = frozenset({
        "你去睡觉吧", "睡觉", "休眠", "暂停", "醒醒", "醒来",
        "喂食", "喂我", "吃东西", "抚摸", "摸摸头", "摸我",
        "石头剪刀布", "猜数字", "猜一个数", "躲猫猫", "捉迷藏",
    })

    # 软指令允许"多出来的字"数量：去掉关键词后剩下的字（忽略空白与标点）
    # 不超过这个数，才算"这是一句指令"而不是"聊天里顺带提到了这个词"。
    #   天气 → "" ✓            查看天气 → "查看" ✓
    #   今天天气真好 → "今天真好" ✗（放行给 AI）
    #   我快哭了（vs「哭」）→ "我快了" ✗（放行给 AI）
    CMD_EXTRA_ALLOWANCE = 2

    @classmethod
    def _is_command_phrase(cls, raw, kw, max_extra=None):
        """软闲聊关键词的收紧命中：只有"指令式"提及才算命中。"""
        if kw not in raw:
            return False
        try:
            import re
            if max_extra is None:
                max_extra = cls.CMD_EXTRA_ALLOWANCE
            rest = raw.replace(kw, "", 1)
            rest = re.sub(r'[\s，。！？!?,\.~、；;：:\-—…（）()]+', '', rest)
            return len(rest) <= max_extra
        except Exception as e:  # 防御性：判不出来就按"不命中"处理，放行给 AI
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
            return False

    # ------------------------------------------------------------------ init
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self._build_ui()
        self._init_state()
        self.set_face("normal")

    def _build_ui(self):
        # 无边框 + 置顶 + 工具窗口（不占任务栏）
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.0)  # 初始完全透明，显示时淡入
        self.resize(self.BASE_WIDTH, self.MIN_BOX_HEIGHT)

        # —— 主容器：原作 Deltarune 对话框（自绘，见 modules/dr_textbox.py）——
        # 不再用样式表画框：纯黑内芯 / 32px 白边框 / 8 帧动画角 全部由
        # DrTextboxFrame.paintEvent 绘制，逐行对应反编译的 scr_darkbox()。
        self._frame = _drbox.DrTextboxFrame(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._frame)

        # 拖动支持：主容器 frame 占满整个窗口，鼠标基本都落在它上面。
        # 安装事件过滤器，把 frame 上的鼠标事件转发给对话框的拖动逻辑，
        # 否则点击 frame 区域时事件只落在子控件上，对话框"移不动"。
        self._frame.installEventFilter(self)

        # —— 闪烁光标 ▼：独立覆盖层，不参与正文文档布局 ——
        # 原先 "▼" 是拼进正文 HTML 的一个内联字符：它占的宽度会参与换行计算，
        # 于是每 530ms 一次闪烁都可能让最后一行多/少占一行，文档高度来回跳，
        # 再由 _recalc_size_to_content 同步 setFixedHeight + resize → 整框高度抖动，
        # 正文看起来"一上一下地抖"。改成独立 QLabel 后，闪烁只切换它的可见性，
        # 完全不触碰正文文档，抖动从根上消失（也顺带让滚动条不再被闪烁重置）。
        self._cursor_label = QLabel("▼", self._frame)
        self._cursor_label.setFont(_ralsei_font(11))
        self._cursor_label.setStyleSheet(
            "QLabel { color: #ffffff; background: transparent; }")
        self._cursor_label.setAlignment(Qt.AlignCenter)
        self._cursor_label.setFixedSize(14, 14)
        self._cursor_label.hide()

        inner = QHBoxLayout(self._frame)
        # 内容整体内缩 BOX_INSET(34px)：避开原作那圈 32px 边框带
        inner.setContentsMargins(self.BOX_INSET, self.BOX_INSET,
                                 self.BOX_INSET, self.BOX_INSET)
        inner.setSpacing(14)

        # —— 左侧：Ralsei 头像（原作的"表情框"：方角 2px 白边，无圆角/无底色）——
        self.face_label = QLabel(self)
        self.face_label.setFixedSize(84, 84)
        self.face_label.setAlignment(Qt.AlignCenter)
        self.face_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: 2px solid #ffffff;
            }
        """)
        inner.addWidget(self.face_label, 0, Qt.AlignTop)

        # —— 右侧：名称 + 对话正文 + 输入框 ——
        right_col = QVBoxLayout()
        right_col.setSpacing(4)

        self.name_label = QLabel("RALSEI", self)
        self.name_label.setFont(_ralsei_font(12, bold=True))
        self.name_label.setStyleSheet("color: #ffffff; letter-spacing: 2px; "
                                      "background: transparent;")
        right_col.addWidget(self.name_label)

        self.dialogue_content = QTextEdit(self)
        self.dialogue_content.setReadOnly(True)
        self.dialogue_content.setFrameShape(QFrame.NoFrame)
        self.dialogue_content.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 内容过高才开滚动条；大多数情况完全展开（随消息增长而变大）
        self.dialogue_content.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.dialogue_content.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Minimum)
        # Ralsei 说话字体：项目根像素字体 `普通字体.ttf`（FZXS12，含中文）
        self.dialogue_content.setFont(_ralsei_font(13))
        self.dialogue_content.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
                color: #ffffff;
                padding: 2px 0 6px 0;
            }
        """)
        # 等价原作的 draw_text_shadow()：白字 + 右下 1px 纯黑投影
        try:
            _shadow = QGraphicsDropShadowEffect(self.dialogue_content)
            _shadow.setBlurRadius(0)
            _shadow.setOffset(1, 1)
            _shadow.setColor(QColor(0, 0, 0))
            self.dialogue_content.setGraphicsEffect(_shadow)
        except Exception as e:  # 防御性：投影失败不影响正文
            _log.debug("dialogue_ui 文字投影未启用: %s", e)
        # 初始最小高度（约 3 行），之后随内容动态变化
        self.dialogue_content.setMinimumHeight(72)
        # 保存初始固定宽度，供 recalc 使用
        self._base_width = self.BASE_WIDTH
        self._min_dialogue_h = 72
        self._max_dialogue_h = 380  # 上限防止占满全屏
        right_col.addWidget(self.dialogue_content, 1)

        # —— 输入区域（默认折叠，用户交互时展开）——
        self._input_bar = QFrame(self)
        self._input_bar.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: 2px solid #ffffff;
            }
        """)
        input_layout = QHBoxLayout(self._input_bar)
        input_layout.setContentsMargins(8, 6, 8, 6)
        input_layout.setSpacing(8)

        self.input_field = QTextEdit(self)
        self.input_field.setFixedHeight(48)
        self.input_field.setFrameShape(QFrame.NoFrame)
        self.input_field.setFont(_ralsei_font(11))
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: #ffffff;
                border: none;
                padding: 6px 8px;
            }
        """)
        input_layout.addWidget(self.input_field, 1)

        self.send_button = QPushButton("SEND", self)
        self.send_button.setFixedSize(72, 48)
        self.send_button.setFont(_ralsei_font(9, bold=True))
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #000000;
                border: none;
            }
            QPushButton:hover { background-color: #cccccc; }
            QPushButton:pressed { background-color: #aaaaaa; }
        """)
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button, 0)

        right_col.addWidget(self._input_bar)
        self._input_bar.hide()
        self._recalc_size_to_content()  # 默认折叠

        inner.addLayout(right_col, 1)

    def _init_state(self):
        # 历史消息HTML缓冲：所有已经显示完的消息（用户输入+已打完的Ralsei回复）
        # 格式：每条是一段HTML（<span style=...>），拼接后用 setHtml 整体渲染
        self._history_html = ""
        # 打字机
        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self._type_next_char)
        self.typing_text = ""
        self.typing_index = 0
        self.is_typing = False
        # 流式输出（S8）：为 True 表示"这条消息还在路上，当前打完的只是已收到的部分"。
        # 打字机打到队列末尾时，靠它区分"整句打完了"与"打完的只是暂时收到的一段"。
        self._streaming = False
        self._stream_raw = ""        # 流式收到的原始文本（未清洗），供前缀比对

        # 本地 AI 对话状态：显式初始化（此前仅靠 getattr 默认值兜底，字段语义不清晰）
        self._ai_inflight = False   # 上一个本地 AI 请求是否仍在等待回复
        self._ai_seq = 0            # 请求序号：新消息递增，作废迟到的旧回复
        # 最近几轮对话历史（供本地 AI 做上下文），只保留真正的对话轮次
        self._ai_history = []
        self._ai_history_max = 8

        # 对话注意力 / 话题锚（第九轮）：让模型知道"我们现在在聊什么"，
        # 避免聊着一个话题突然切换。见 conversation_focus.py。
        self.focus = ConversationFocus() if ConversationFocus is not None else None
        # 最近一次对话活动时间（用户输入 / Ralsei 回复）——"是否正在聊天"的判据，
        # 同时给自主开口闸门用（别打断进行中的聊天）。
        self._last_activity = 0.0

        # Deltarune 闪烁光标
        self._cursor_visible = True
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._blink_cursor)
        self._cursor_timer.start(530)

        # 滚动条：用户正在拖动时，自动跟随（滚到底）不与用户抢位置
        self._scrollbar_dragging = False
        self._last_scroll_max = -1
        try:
            _sb = self.dialogue_content.verticalScrollBar()
            _sb.sliderPressed.connect(
                lambda: setattr(self, '_scrollbar_dragging', True))
            _sb.sliderReleased.connect(
                lambda: setattr(self, '_scrollbar_dragging', False))
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 滚动条信号连接失败: %s", e)

        # 自动隐藏：20 秒无输入后淡出；输入/聚焦/鼠标压住输入栏时由 _try_auto_hide 暂缓
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._try_auto_hide)
        # 输入框每敲一个字都重新开始 20 秒倒计时（避免"打着字突然消失"）
        try:
            self.input_field.textChanged.connect(self._schedule_auto_hide)
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 输入框信号连接失败: %s", e)

        # 淡入淡出动画引用（防止被 GC）
        self._fade_anim = None

        # 拖动 & 最小化：用户拖过后对话框保持用户放置位置，不再被 follow_timer 拉回
        self.drag_position = QPoint()
        self._is_dragging = False
        self._user_moved = False

        # 位置跟随定时器：对话框可见时持续贴在 ralsei 上方
        self._follow_timer = QTimer(self)
        self._follow_timer.timeout.connect(self._position_above_ralsei)
        self._follow_timer.start(100)  # 10 帧/秒更新位置

        # 回车发送：统一拦截入口（单一判定函数）
        self.input_field.installEventFilter(self)
        # 全局 X 键跳过对话：装在 QApplication 上，eventFilter 统一判定
        try:
            app = QApplication.instance()
            if app is not None and not getattr(self, '_app_filter_installed', False):
                app.installEventFilter(self)
                self._app_filter_installed = True
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)

    # ------------------------------------------------------------------ face
    def set_face(self, face_type):
        name = _resolve_face_name(face_type)
        loader = self.parent.sprite_loader
        # 兜底：解析出的素材名若不存在（新增/拼错的表情键、emotion_system 返回
        # 未覆盖的键），退回 face_normal，避免渲染出灰色"?"占位头像。
        try:
            if hasattr(loader, 'has_face') and not loader.has_face(name):
                _log.debug("表情素材缺失，回退 normal: %r -> %r", face_type, name)
                name = "face_normal"
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        pixmap = loader.get_face(name)
        if pixmap and not pixmap.isNull():
            self.face_label.setPixmap(
                pixmap.scaled(78, 78, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # ---------------------------------------------------------------- typing
    def add_dialogue(self, speaker, message, face_type="normal", _streamed=False):
        # 修复：消息类型防护 + HTML 转义。
        # (1) 延迟回复(lambda)求值失败时会返回函数对象/None，直接 len()/拼接会
        #     TypeError 把 send_message 链路打断（用户消息已回显却无回复）；
        # (2) 用户输入原样拼进 setHtml 会成为 HTML 注入，破坏排版。
        import html as _html
        if message is None:
            message = ""
        elif not isinstance(message, str):
            try:
                message = str(message)
            except Exception:
                message = ""
        # 修复：不要把整条消息先 escape 再交给打字机。
        # 打字机是按字符切片渲染的（_refresh_display 里 typing_text[:idx]），
        # 对"已转义的整串"切片会在逐字显示过程中闪出 &am / &lt / &quot 之类的实体残片。
        # 现在保留原文用于逐字显示，只在真正拼进 HTML 的那一刻转义。
        safe_message = _html.escape(message)
        # 前台若是 AI 思考占位文本，先丢弃它（无论新消息还是真实回复到达），
        # 占位只是"等待"提示，绝不能并入历史或当成正式消息。
        if self.typing_text == self.AI_THINKING_PLACEHOLDER:
            self.typing_text = ""
            self.typing_index = 0
            self.is_typing = False
        # 记录对话轮次（供本地 AI 上下文用）：占位/空消息不入历史
        if message.strip():
            self._push_ai_history(speaker, message)
            # 对话注意力：把这一轮交给话题锚，并刷新"刚有过对话活动"时间戳
            self._note_focus(speaker, message)
            # 记忆（第九轮）：把这一轮作为"日常小片段"喂给拟人记忆系统
            self._note_memory(speaker, message)
        if speaker == "ralsei":
            self.set_face(face_type)
            if _streamed:
                # 流式（S8）：这段回复在流式期间**已经逐字显示在前台**了，所以
                #   ① 不能走 `_start_typing`（会从第 0 字重打一遍，视觉上闪一下再重来）；
                #   ② 不能走 `_commit_previous_ralsei_into_history`
                #      （它会把前台 typing_text 当成"上一条"提交，可它其实就是本条）。
                self._finalize_stream(message)
            else:
                # 先打断前一条打字机（补完剩余内容，非打字时noop安全）
                self.stop_typing()
                # 把上一条 Ralsei 完整并入历史，然后再开新的打字机，防止消息覆盖
                self._commit_previous_ralsei_into_history()
                self._start_typing(message)   # 传原文，渲染时才转义（见 _refresh_display）
        else:
            # 用户说的话：先打断打字机，再把上一条Ralsei并入历史，然后追加用户消息
            self.stop_typing()
            self._commit_previous_ralsei_into_history()
            self._history_html += (
                f'<div style="color:#9aa0aa;font-size:10pt;line-height:1.45;'
                f'margin:2px 0 4px 0;">▸ YOU: {safe_message}</div>')
            self.typing_text = ""   # 前台清空：最新的一条是用户消息
            self._refresh_display()

    # -------------------------------------------------------- display helper

    def _push_ai_history(self, speaker, message):
        """把一轮对话写进本地 AI 的上下文缓冲（只保留最近 N 轮）。"""
        try:
            _role = "assistant" if speaker == "ralsei" else "user"
            _msg = str(message).strip()
            if not _msg:
                return
            self._ai_history.append((_role, _msg))
            if len(self._ai_history) > self._ai_history_max:
                del self._ai_history[:len(self._ai_history) - self._ai_history_max]
        except Exception as e:
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)

    # -------------------------------------------------------- conversation focus
    def _note_focus(self, speaker, message):
        """把这一轮喂给话题锚，并刷新活动时间戳（失败绝不影响对话）。"""
        import time as _time
        self._last_activity = _time.time()
        if self.focus is None:
            return
        try:
            if speaker == "ralsei":
                self.focus.note_assistant(message)
            else:
                # 用户在说话 → 说明上一个"悬置问题"已被回应
                self.focus.clear_pending()
                self.focus.note_user(message)
        except Exception as e:
            _log.debug("dialogue_ui 话题锚异常（已忽略）: %s", e)

    def get_focus_brief(self):
        """给本地 AI 的"注意力焦点"提示词（没有话题时返回空串）。"""
        try:
            if self.focus is None:
                return ""
            return self.focus.brief()
        except Exception:
            return ""

    def _note_memory(self, speaker, message):
        """把这一轮记成"日常小片段"（第九轮：拟人记忆）。

        只管登记，不管存储位置与遗忘 —— 那是 memory_system 的事。
        失败绝不影响对话。
        """
        try:
            ms = getattr(self.parent, 'memory_system', None)
            if ms is None or not callable(getattr(ms, 'add_fragment', None)):
                return
            ms.add_fragment(message, who=('ralsei' if speaker == 'ralsei' else 'user'),
                            kind='dialogue')
        except Exception as e:
            _log.debug("dialogue_ui 记忆登记异常（已忽略）: %s", e)

    def has_active_conversation(self, window=None):
        """此刻是否"正在聊天"：最近有对话活动，或模型正在思考，或正在打字。

        自主开口闸门（10 分钟一次）用它来避免**打断进行中的聊天**：
        用户刚才还在说话、Ralsei 还在等回复，这时插一句自己的话非常突兀。
        """
        try:
            import time as _time
            if self._ai_inflight:
                return True
            if self.is_typing:
                return True
            if getattr(self, '_is_user_inputting', lambda: False)():
                return True
            w = self.ACTIVE_CONVERSATION_SECONDS if window is None else float(window)
            return (_time.time() - float(self._last_activity or 0.0)) < w
        except Exception:
            return False

    def get_ai_history(self, limit: int = 8):
        """返回最近几轮对话历史 [(role, content), ...]，供本地 AI 参考。"""
        try:
            return list(self._ai_history[-limit:])
        except Exception:
            return []

    def _commit_previous_ralsei_into_history(self):
        """如果前台还有一条 Ralsei 消息（typing_text 非空），把它完整并入历史。"""
        import html as _html
        if self.typing_text:
            # 立刻补完当前打字机进度，用完整文本写入历史
            # 修复：typing_text 现在是「原文」，入历史前必须转义，否则 "<" 等会被当成标签
            full_text = _html.escape(self.typing_text)
            if self.is_typing:
                self.is_typing = False
                self.typing_timer.stop()
            self._history_html += (
                f'<div style="color:#ffffff;line-height:1.45;">{full_text}</div>')
            self.typing_text = ""
            self.typing_index = 0

    def _refresh_display(self):
        """统一渲染：历史消息 + 前台当前消息（若存在）。
        闪烁光标是独立覆盖层（见 _cursor_label），这里只负责正文本身。"""
        import html as _html
        html = self._history_html
        if self.typing_text:
            # 有前台 Ralsei 消息：当前显示到 index
            show_idx = (self.typing_index
                        if self.is_typing else len(self.typing_text))
            # 先按字符切片、再转义：保证逐字显示过程中不会出现 &amp; 这类实体残片
            current_shown = _html.escape(self.typing_text[:show_idx])
            html += (f'<div style="color:#ffffff;line-height:1.45;">'
                     f'{current_shown}</div>')

        # —— 滚动位置保护 ——
        # setHtml 会重建文档并把滚动条重置回顶部。先记住用户当前视图位置与"是否贴在
        # 底部"，重建后再恢复：用户向上翻看历史时不会被弹回底部，新消息到来时又能
        # 自动跟随到底（修"对话框没办法下拉/翻不上去"）。
        sb = None
        prev_val = 0
        was_at_bottom = True
        try:
            sb = self.dialogue_content.verticalScrollBar()
            prev_val = sb.value()
            was_at_bottom = prev_val >= sb.maximum() - 4
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 读取滚动位置失败: %s", e)
            sb = None

        self.dialogue_content.setHtml(html)

        if sb is not None:
            try:
                if getattr(self, '_scrollbar_dragging', False) or not was_at_bottom:
                    # 用户正在翻/已翻上去：原样保留他的视图位置
                    sb.setValue(min(prev_val, sb.maximum()))
                else:
                    # 本来就贴在底部：跟随新内容滚到底
                    sb.setValue(sb.maximum())
                self._last_scroll_max = sb.maximum()
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("dialogue_ui 恢复滚动位置失败: %s", e)

        # 光标覆盖层显隐（只切可见性，不重建文档）——抖动修复的关键
        self._update_cursor_overlay()

        # ============================================================
        # 动态高度：只在内容高度真正变化时才 resize（避免每帧 resize 导致文字抖动）
        # 拖拽中完全不 resize（避免拖不动）
        # ============================================================
        if not getattr(self, '_is_dragging', False):
            self._recalc_size_to_content_lazy()

    def _update_cursor_overlay(self):
        """依据"是否有前台消息"决定 ▼ 覆盖层显隐；闪烁相位由 _cursor_visible 自持。"""
        try:
            lbl = getattr(self, '_cursor_label', None)
            if lbl is None:
                return
            has_fg = bool(getattr(self, 'typing_text', ""))
            lbl.setVisible(has_fg and self._cursor_visible)
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)

    def _position_cursor_overlay(self):
        """把 ▼ 覆盖层贴到对话框右下角内侧（原作的位置），完全避开正文区域。"""
        try:
            lbl = getattr(self, '_cursor_label', None)
            if lbl is None:
                return
            # 原作里 ▼ 贴在框内右下；这里留出 32px 边框带 + 2px 余量
            margin_r = self.BOX_INSET - 18
            margin_b = self.BOX_INSET - 18
            # 用 self 的尺寸（窗口==frame，outer 布局 0 边距）：resizeEvent 触发时
            # self 的几何已更新，而子控件 frame 可能还没同步，故取 self 更稳。
            lbl.move(max(0, self.width() - margin_r - lbl.width()),
                     max(0, self.height() - margin_b - lbl.height()))
            lbl.raise_()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)

    def resizeEvent(self, event):
        # 窗口尺寸变化时把 ▼ 覆盖层重新贴到右下角
        try:
            self._position_cursor_overlay()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        super().resizeEvent(event)

    def _recalc_size_to_content_lazy(self):
        """惰性重算：只在文档高度真正变化时才执行 resize/move。
        避免每帧 resize 导致文字抖动 + 对话框不可拖动。"""
        try:
            doc = self.dialogue_content.document()
            doc.setTextWidth(self.dialogue_content.viewport().width())
            content_h = int(doc.size().height())
            # 和上次记录的高度比较，没变就不 resize
            last_h = getattr(self, '_last_content_h', -1)
            if content_h == last_h:
                return
            self._last_content_h = content_h
            # 高度变了，才真正执行 resize
            self._recalc_size_to_content()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)

    def _get_screen_rect(self):
        """统一取屏幕可用区域 (left, top, right, bottom)，优先Win32虚拟屏再Qt。"""
        try:
            import win32api
            vx = win32api.GetSystemMetrics(76)
            vy = win32api.GetSystemMetrics(77)
            vw = win32api.GetSystemMetrics(78)
            vh = win32api.GetSystemMetrics(79)
            return (vx, vy, vx + vw, vy + vh)
        except Exception:
            from PyQt5.QtWidgets import QApplication
            screen = QApplication.desktop().availableGeometry()
            return (screen.left(), screen.top(), screen.right(), screen.bottom())

    def _clamp_to_screen(self, geom):
        """把 QRect 夹到屏幕可见区域内，保证至少 80x60 可见。"""
        sl, st, sr, sb = self._get_screen_rect()
        x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()
        # 先夹右边界
        if x + w > sr:
            x = sr - w
        # 再夹左边界
        if x < sl:
            x = sl
        # 夹下边界
        if y + h > sb:
            y = sb - h
        # 夹上边界
        if y < st:
            y = st
        # 最后兜底：宽/高超过屏幕时至少露一个角
        if w > sr - sl:
            x = sl
        if h > sb - st:
            y = st
        from PyQt5.QtCore import QRect
        return QRect(x, y, w, h)

    def _recalc_size_to_content(self):
        """根据 dialogue_content 文档实际高度，
        重新设置 dialogue_content 高度 + 整个对话框尺寸。
        带屏幕边界 clamp，任何情况下都不允许掉出屏幕外。
        """
        try:
            # QTextEdit 的 document 有真实像素高度（setHtml 之后就有值）
            doc = self.dialogue_content.document()
            doc.setTextWidth(self.dialogue_content.viewport().width())
            content_h = int(doc.size().height())
            # 夹在最小/最大之间，超出时 QTextEdit 会显示滚动条（VerticalScrollBarAsNeeded）
            clamped_h = max(self._min_dialogue_h, min(content_h + 8, self._max_dialogue_h))
            self.dialogue_content.setFixedHeight(clamped_h)

            # —— 根据输入框是否可见 + 内容高度，计算整个窗口的目标高度 ——
            frame_v_pad = 2 * self.BOX_INSET   # 原作框四周各 34px 内缩
            name_label_h = 18
            right_spacing = 4
            face_h = 84
            body_h = name_label_h + right_spacing + clamped_h
            if self._input_bar.isVisible():
                body_h += right_spacing + self._input_bar.sizeHint().height()
            right_col_h = max(face_h, body_h)
            target_h = frame_v_pad + right_col_h
            target_h = max(target_h, self.MIN_BOX_HEIGHT)
            target_w = self._base_width

            old_geom = self.geometry()
            # —— 计算目标几何：先按原策略算 (x,y)，再统一 screen-clamp ——
            from PyQt5.QtCore import QRect
            if getattr(self, '_user_moved', False):
                # 用户拖过：底边对齐，向上扩展
                new_x = old_geom.x()
                new_y = old_geom.y() + old_geom.height() - target_h
                target = QRect(new_x, new_y, target_w, target_h)
            else:
                # 未拖过：目标宽高先set，之后 _position_above_ralsei 会重新定位
                target = QRect(old_geom.x(), old_geom.y(), target_w, target_h)

            # 关键：如果算出来的 rect 掉出屏幕 → 强制 clamp
            safe = self._clamp_to_screen(target)
            # 如果 clamp 结果和原计算不一样（=真的出屏了），说明用户拖到屏幕边缘或屏幕
            # 已经 resize 了，此时清掉 _user_moved 并贴回默认底部位置（防止永久"卡出界"）
            if safe != target:
                if safe.x() != target.x() or safe.y() != target.y():
                    self._user_moved = False
            self.resize(safe.width(), safe.height())
            if getattr(self, '_user_moved', False):
                self.move(safe.x(), safe.y())
            elif self.isVisible():
                # 没拖过 + 当前可见 → 重新贴回屏幕底部居中
                self._position_above_ralsei()
                # 贴完再 clamp 一次兜底，防止 _position_above_ralsei 算错
                after = self.frameGeometry()
                safe_after = self._clamp_to_screen(after)
                if safe_after != after:
                    self.move(safe_after.x(), safe_after.y())
                    self.resize(safe_after.width(), safe_after.height())
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)

    def _start_typing(self, text):
        # 新消息：取消之前的自动隐藏
        self._auto_hide_timer.stop()
        self.typing_timer.stop()
        self._streaming = False      # 非流式路径：整句已经在手上了
        self._stream_raw = ""
        self.typing_text = text
        self.typing_index = 0
        self.is_typing = True
        # 速度：默认 35ms/字，长文本 22ms/字
        speed = 35 if len(text) <= 60 else 22
        self.typing_timer.start(speed)
        # 立刻显示第0帧（只显示光标，历史+空当前）
        self._refresh_display()

    def _type_next_char(self):
        if self.typing_index < len(self.typing_text):
            ch = self.typing_text[self.typing_index]
            self.typing_index += 1
            self._refresh_display()
            # 打字声：每打一个字一声，但**空格与标点静音** —— 等价原作
            # scr_textsound() 里 getchar == " "/"!"/"."/","/... 时 play = 0 的判定。
            try:
                if _should_play_text_sound(ch):
                    sm = getattr(self.parent, 'sound_manager', None)
                    if sm is not None:
                        sm.play_typewriter()
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        else:
            # 流式（S8）还连着：这一批字打完了，但整条消息**还没收完** ——
            # 不能停表、也不能安排自动隐藏，否则"边收边打"会在第一个分片后就收摊。
            if getattr(self, '_streaming', False):
                self._refresh_display()
                return
            # 打字完成：停止计时，但不把消息并入历史（直到下一条消息到来）
            # 这样最后一条消息后能继续闪烁光标
            self.is_typing = False
            self.typing_timer.stop()
            self.typing_index = len(self.typing_text)
            self._refresh_display()
            # 打字完成 → 安排自动隐藏（输入中时延后）
            self._schedule_auto_hide()

    def stop_typing(self):
        """立即打完当前Ralsei消息（外部X键/点击打断用）。未在打字时noop。"""
        # 流式标记**无条件**清掉：用户已经要求"立刻显示全文"，就不能再让后续分片
        # 追加到这个已定格的文本后面（否则新分片会接在句尾继续往外冒字）。
        self._streaming = False
        self._stream_raw = ""
        if not self.is_typing:
            return
        # 把打字进度跳到末尾（补完剩余文字）
        self.is_typing = False
        self.typing_timer.stop()
        self.typing_index = len(self.typing_text)
        self._refresh_display()
        # 手动打断打字 → 安排自动隐藏（输入中时延后）
        self._schedule_auto_hide()

    # --------------------------------------------- 流式输出（S8）：边收边打

    def stream_delta(self, chunk):
        """接收本地 AI 的一段增量文本（**主线程**调用，来源见 main.py `_api_delta`）。

        - **首块到达**：把「……」思考占位换成真正的回复，打字机随即开动
          —— 首字延迟从"整句生成完"（实测热 0.9s / 冷 6.0s）降到 ~0.23s；
        - **后续块**：追加到待打队列尾部。打字机本来就是按
          `typing_text[:typing_index]` 逐字推进的，追加后它会自然往下继续打，
          **不需要重启** —— 所以视觉上是"字连续冒出来"，而不是"一段一段跳"；
        - `chunk is None`：**作废已显示的半句**（护栏判退 → 要重采样，
          旧句不能留在屏幕上，否则新句会接在旧句后面，像两句黏一起）。

        这里只做**前缀安全**的轻清洗（剥 markdown、截自问自答），保证屏幕不闪
        `**` / `主人：` 这类残渣；判退与截断的定论仍在收尾的 `_clean_ai_reply`。
        """
        if chunk is None:
            self._stream_reset()
            return
        if not isinstance(chunk, str) or not chunk:
            return
        try:
            if not getattr(self, '_streaming', False):
                self._stream_begin()
            self._stream_raw = (getattr(self, '_stream_raw', '') or '') + chunk
            clean = self._sanitize_stream(self._stream_raw)
            shown = self.typing_text or ''
            if clean.startswith(shown):
                # 正常情况：清洗结果 = "已显示内容 + 新增的字"，原地追加即可
                self.typing_text = shown + clean[len(shown):]
            else:
                # 极端情况（如 `主人：` 跨分片到达，前半段「主人」已经显示了）：
                # 前缀假设被打破 → 整段替换。宁可闪一下，也不能让屏幕留下错位内容。
                self.typing_text = clean
                self.typing_index = min(self.typing_index, len(clean))
            if not self.typing_timer.isActive():
                self.typing_timer.start(35 if len(self.typing_text) <= 60 else 22)
            self._refresh_display()
        except Exception as e:
            _log.debug("dialogue_ui 流式追加异常（已忽略）: %s", e)

    def _sanitize_stream(self, raw):
        """调 RalseiPet 上的共用清洗；取不到就原样返回（绝不因取不到而丢字）。"""
        try:
            fn = getattr(self.parent, '_sanitize_partial_reply', None)
            if callable(fn):
                return fn(raw)
        except Exception as e:
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        return raw

    def _stream_begin(self):
        """首块到达：从"思考占位"切进"正在流式打字"。"""
        try:
            self._auto_hide_timer.stop()
        except Exception as e:
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        # 思考占位只是"等待"提示，绝不能并进历史（与 add_dialogue 同款处理）
        if self.typing_text == self.AI_THINKING_PLACEHOLDER:
            self.typing_text = ""
            self.typing_index = 0
            self.is_typing = False
        self.stop_typing()
        self._commit_previous_ralsei_into_history()
        self._streaming = True
        self._stream_raw = ""
        self.typing_text = ""
        self.typing_index = 0
        self.is_typing = True
        self.typing_timer.start(35)
        self._refresh_display()

    def _stream_reset(self):
        """把流式期间已经显示出去的内容擦掉，回到"……"等待态。

        护栏判退（车轱辘话）时要重采样一次，判退的那半句必须先消失 ——
        否则新句会接在旧句后面，看起来像两句话黏在一起。
        """
        self._streaming = False
        self._stream_raw = ""
        try:
            self.typing_timer.stop()
        except Exception as e:
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        self.is_typing = False
        # 重采样还要再花 1~2 秒，恢复"思考中"的观感比留一片空白自然
        self.typing_text = self.AI_THINKING_PLACEHOLDER
        self.typing_index = len(self.typing_text)
        try:
            self.set_face("thinking")
        except Exception as e:
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        self._refresh_display()

    def _finalize_stream(self, final_text):
        """收尾：把最终文本定格到前台（由 `add_dialogue(..., _streamed=True)` 调用）。

        流式期间显示的是"清洗过的增量"，收尾时 `_clean_ai_reply` 可能还做了更狠的
        处理（超长截断、去包裹引号）。于是两种情况：
          - **一致** → 不打断打字机，让它自然把最后几个字打完（视觉最连续）
          - **不一致** → 直接定格成最终文本，避免"打完了又突然改字"
        """
        self._streaming = False
        self._stream_raw = ""
        shown = self.typing_text or ''
        if shown == final_text:
            if not self.is_typing:
                # 打字机已经停了（例如用户点击打断了）→ 手动补一次收尾
                self._schedule_auto_hide()
            return
        try:
            self.typing_timer.stop()
        except Exception as e:
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        self.is_typing = False
        self.typing_text = final_text
        self.typing_index = len(final_text)
        self._refresh_display()
        self._schedule_auto_hide()

    # ----------------------------------------------------- auto-hide helpers

    @staticmethod
    def _should_send_on_enter(event):
        """单一判定：仅当按下 Enter/Return 且未按住 Shift/Ctrl 时，才发送消息。"""
        from PyQt5.QtCore import Qt
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier):
                return False
            return True
        return False

    def _is_user_inputting(self):
        """用户是否正在输入：输入框有焦点 或 输入框有内容。"""
        try:
            if self.input_field.hasFocus():
                return True
            if self.input_field.toPlainText().strip():
                return True
        except Exception:
            return False
        return False

    def _mouse_on_input(self, global_pos=None):
        """鼠标是不是正压在输入栏上（按用户的说法：这种时候**不允许**消失）。

        用光标全局坐标判断而不是 `underMouse()`：后者在鼠标悬停于输入栏的
        **子控件**（发送按钮、输入框边缘）时为 False，会漏判。
        `global_pos` 只是给测试留的注入点，正常调用不传。
        """
        try:
            bar = getattr(self, '_input_bar', None)
            if bar is None or not bar.isVisible():
                return False
            if global_pos is None:
                from PyQt5.QtGui import QCursor
                global_pos = QCursor.pos()
            return bar.rect().contains(bar.mapFromGlobal(global_pos))
        except Exception:
            return False

    def _auto_hide_blocked(self):
        """当前是否不允许自动隐藏（"有动静"的三种情形）。"""
        if self._is_user_inputting():
            return True          # 光标在输入框 / 已经打了字
        if self._mouse_on_input():
            return True          # 鼠标压在输入栏上
        if getattr(self, '_ai_inflight', False):
            return True          # 模型正在思考，等它回完再谈隐藏
        return False

    def _schedule_auto_hide(self, *_args):
        """触发一次倒计时检查（AUTO_HIDE_MS = 20 秒无输入才隐藏）。

        注意带 `*_args`：它同时被 `input_field.textChanged` 连过来，
        那时会带一个字符串参数，不接住会 TypeError。
        """
        try:
            self._auto_hide_timer.start(int(self.AUTO_HIDE_MS))
        except Exception as e:
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)

    def _try_auto_hide(self):
        """_auto_hide_timer 到点：有动静就 1 秒后再查，否则淡出隐藏。"""
        if self._auto_hide_blocked():
            self._auto_hide_timer.start(int(self.AUTO_HIDE_RECHECK_MS))
            return
        self.hide_dialogue()

    def eventFilter(self, obj, event):
        """统一拦截：输入框回车发送 / Shift+Enter 换行；全局 X 键跳过打字。
        X 键跳过仅在"正在打字 且 输入框未聚焦"时触发，避免影响用户在输入框里打字。
        另外转发主容器 frame 上的鼠标事件给对话框自身，实现"点哪都能拖动"。"""
        # 主容器 frame 的鼠标事件 → 转发给对话框拖动逻辑（避免事件被子控件吞掉）
        if obj is self._frame:
            if event.type() == event.MouseButtonPress:
                self.mousePressEvent(event)
                return True
            elif event.type() == event.MouseMove:
                self.mouseMoveEvent(event)
                return True
            elif event.type() == event.MouseButtonRelease:
                self.mouseReleaseEvent(event)
                return True
        if event.type() == event.KeyPress:
            # 全局 X 键跳过对话（不打字音效，直接显示完整文本）
            if event.key() == Qt.Key_X and self.is_typing and not self._is_user_inputting():
                self.stop_typing()
                return True
            # 输入框：回车发送 / Shift+Enter 换行
            if obj is self.input_field and self._should_send_on_enter(event):
                self.send_message()
                return True
        return super().eventFilter(obj, event)

    def _blink_cursor(self):
        self._cursor_visible = not self._cursor_visible
        # 只切换独立覆盖层的显隐：不再 setHtml → 不再引起正文重排/高度抖动/滚动重置
        self._update_cursor_overlay()

    # ------------------------------------------------------------------ show
    def show_dialogue(self, message=None, face_type=None):
        # 不再每次重置位置：用户拖过后保持用户放置位置
        # 仅在未被拖过时定位到屏幕正下方居中
        if message:
            # 如果未指定表情，尝试使用当前情绪对应的表情
            if face_type is None:
                try:
                    current_emotion, emotion_value = \
                        self.parent.emotion_system.get_current_emotion()
                    intensity = abs(emotion_value)
                    face_type = self.parent.emotion_system.get_face_for_emotion(
                        current_emotion, intensity)
                except Exception:
                    face_type = "normal"
            self.add_dialogue("ralsei", message, face_type)
        self.show()
        # show 之后再定位：_position_above_ralsei 在不可见时会提前 return，
        # 必须在 show() 之后调用，否则对话框会在旧位置闪一下再被 follow_timer 拉回
        self._position_above_ralsei()
        # 取消之前的自动隐藏（重新 show 时不立即消失），并重新起一次 20 秒倒计时
        # （第九轮：无输入 20s 就收起；打字过程中 _start_typing 还会再重置一次，
        #  所以真正开始计时的时刻是"这句话打完/显示完"之后）
        self._auto_hide_timer.stop()
        self._schedule_auto_hide()
        # 修复：淡入前停掉并断开旧动画——hide 时创建的 fade-out 把 finished→self.hide
        # 挂在旧动画对象上，若淡出未结束就 show，旧回调会在淡入完成后把刚显示的窗口
        # 再次隐藏（对话框"弹出后立即消失"）。
        #
        # 修复（打字机）：这里原来还无条件调用 stop_typing()，而 stop_typing 的语义是
        # "立刻把当前这句话补完"。main.py 里 150+ 处写法都是
        #     add_dialogue(...)  # 启动打字机
        #     show_dialogue()    # ← 立刻把它补完
        # 于是逐字打字效果 100% 失效：台词瞬间整段出现、打字音效 play_typewriter 从不播放。
        # show_dialogue 只负责"把窗口显示出来"，不应该打断正在进行的打字；
        # 真正需要打断的场景（隐藏对话框、新消息到来）已分别在 hide_dialogue / add_dialogue 处理。
        _old = getattr(self, '_fade_anim', None)
        if _old is not None:
            try:
                _old.stop()
                _old.finished.disconnect()
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        # 淡入（存到 self._fade_anim 防止被 GC）
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(320)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(0.98)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.start()

    def hide_dialogue(self):
        self._auto_hide_timer.stop()
        # 修复：隐藏时停打字机 + 断开旧动画（见 show_dialogue 注释）
        try:
            self.stop_typing()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        _old = getattr(self, '_fade_anim', None)
        if _old is not None:
            try:
                _old.stop()
                _old.finished.disconnect()
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        # 淡出（存到 self._fade_anim 防止被 GC）
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(260)
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.InQuad)
        self._fade_anim.finished.connect(self.hide)
        self._fade_anim.start()

    def _position_above_ralsei(self):
        """对话框定位：用户拖过后保持用户位置，否则定位到屏幕正下方居中。"""
        # 用户拖过一次后永远不再自动定位，保持用户放的位置（不管可见与否）
        if getattr(self, '_user_moved', False):
            return
        # 不可见时不做 move，防止隐藏期间把几何改回屏幕底部导致下次显示"被重置"
        if not self.isVisible():
            return
        try:
            dw = self.width()
            dh = self.height()

            # 获取屏幕可用区域
            try:
                import win32api
                vx = win32api.GetSystemMetrics(76)
                vy = win32api.GetSystemMetrics(77)
                vw = win32api.GetSystemMetrics(78)
                vh = win32api.GetSystemMetrics(79)
                left, top, right, bottom = vx, vy, vx + vw, vy + vh
            except Exception:
                from PyQt5.QtWidgets import QApplication
                screen = QApplication.desktop().availableGeometry()
                left, top, right, bottom = screen.left(), screen.top(), screen.right(), screen.bottom()

            # 水平居中，垂直贴底
            center_x = (left + right) // 2 - dw // 2
            bottom_y = bottom - dh - 4
            # 修复：_follow_timer 每 100ms 调用本函数，位置没变时不要重复 move
            # （重复 move 会持续触发窗口移动事件，浪费 CPU 且可能引起轻微抖动）
            if (center_x, bottom_y) != getattr(self, '_last_anchor_pos', None):
                self._last_anchor_pos = (center_x, bottom_y)
                self.move(center_x, bottom_y)
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)

    # ---------------------------------------------------------------- input
    def send_message(self):
        user_input = self.input_field.toPlainText().strip()
        if not user_input:
            return
        self.input_field.clear()

        # —— "训练"钩子：从对话里记住主人的名字/喜好（显式自述，非被动追踪）——
        self._learn_from_user_input(user_input)

        # —— 若上一个本地 AI 对话仍在思考：作废它（seq 递增 + inflight 复位）。
        #    用户已输入新消息，旧模型的迟到回复不应再显示，避免乱序/串话。
        #    （思考占位文本随后会被 add_dialogue("user") 的占位拦截丢弃，不入历史）
        if getattr(self, '_ai_inflight', False):
            self._ai_seq = getattr(self, '_ai_seq', 0) + 1
            self._ai_inflight = False

        # —— 用户消息回显：把自己说的话显示在对话框里（灰色 YOU 前缀），不经过打字机
        self.add_dialogue("user", user_input, "normal")

        self._input_bar.hide()
        self._recalc_size_to_content()

        # 先检查聊天指令
        cmd = self.handle_chat_commands(user_input)
        if cmd:
            reply, face = cmd
            self.add_dialogue("ralsei", reply, face)
            return

        # 游戏输入
        if self.parent.handle_game_input(user_input):
            return

        # 文件操作
        if self.handle_file_commands(user_input):
            return

        # 正常对话
        # 修复/扩展：API 启用（本地 Ollama Ralsei / OpenAI 兼容）时优先把这句话交给
        # 本地模型回答（更贴角色）；请求失败/未启用则回退内置规则 dialogue_system。
        def _rule_reply():
            response = self.parent.dialogue_system.generate_response(
                user_input, self.parent.emotion_system)
            try:
                current_emotion, emotion_value = \
                    self.parent.emotion_system.get_current_emotion()
                intensity = abs(emotion_value)
                face_type = self.parent.emotion_system.get_face_for_emotion(
                    current_emotion, intensity)
            except Exception:
                face_type = "normal"
            self.add_dialogue("ralsei", response, face_type)

        use_ai = (getattr(self.parent, 'api_enabled', False)
                  and hasattr(self.parent, 'chat_with_ai'))
        if use_ai:
            # 本地模型推理通常要几秒：先显示"…"占位，回复到了再打字机显示。
            # 并发保护：每次发起请求 seq+1，回调里校验 seq，过期请求直接丢弃。
            self._ai_seq = getattr(self, '_ai_seq', 0) + 1
            req_seq = self._ai_seq
            self._ai_inflight = True
            try:
                self._ai_thinking_on()
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)

            def _on_ai_reply(reply_text):
                if req_seq != getattr(self, '_ai_seq', 0):
                    return  # 已被更新的请求作废，忽略迟到回复
                self._ai_inflight = False
                # 流式（S8）期间前台**已经显示着**这条回复了 —— 这时不能调
                # `_ai_thinking_off`（它会把 typing_text 清空，于是已显示的内容
                # 一闪而逝、再从第 0 字重打一遍）。非流式路径照旧，先把"……"收掉。
                streamed = bool(getattr(self, '_streaming', False))
                if not streamed:
                    try:
                        self._ai_thinking_off()
                    except Exception as e:  # 修复：原先静默吞噬
                        _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
                if reply_text:
                    try:
                        current_emotion, emotion_value = \
                            self.parent.emotion_system.get_current_emotion()
                        face_type = self.parent.emotion_system.get_face_for_emotion(
                            current_emotion, abs(emotion_value))
                    except Exception:
                        face_type = "normal"
                    # _streamed=streamed：流式走"定格"，非流式走"从头打字机"
                    self.add_dialogue("ralsei", reply_text, face_type,
                                      _streamed=streamed)
                    # 模型推理可能耗时较长，等待期间对话框也许已被自动隐藏：
                    # 回复到达时若不可见则重新显示并贴回宠物上方。
                    if not self.isVisible():
                        try:
                            self.show()
                            self._position_above_ralsei()
                        except Exception as e:  # 修复：原先静默吞噬
                            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
                else:
                    # 模型不可用（或流式被判退、重采样也没救回来）→ 回退规则对话。
                    # 流式路径下屏幕上还留着被判退的半句，必须先擦干净再接规则台词。
                    if streamed:
                        try:
                            self._stream_reset()
                        except Exception as e:  # 修复：原先静默吞噬
                            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
                    _rule_reply()

            # 流式（S8）：把分片交给打字机。这个回调在**主线程**被调用
            # （工作线程发出 → main.py 用 _api_delta 信号排到主线程再转发），
            # 所以这里直接碰 UI 是安全的。世代号校验沿用 req_seq：
            # 用户已经问了新问题时，旧请求的分片不该再往对话框里写字。
            def _on_ai_delta(chunk):
                if req_seq != getattr(self, '_ai_seq', 0):
                    return  # 已被更新的请求作废，忽略迟到分片
                self.stream_delta(chunk)

            try:
                self.parent.chat_with_ai(user_input, _on_ai_reply, _on_ai_delta)
                return
            except Exception as e:
                _log.debug(f"[本地AI] 调用失败，回退规则对话: {e}")
                self._ai_inflight = False
                try:
                    self._ai_thinking_off()
                except Exception as e:  # 修复：原先静默吞噬
                    _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        _rule_reply()

    def _learn_from_user_input(self, user_input):
        """从对话中学习主人的信息（显式自述才记，不做被动追踪）。

        - “我叫/我是 XX” → 记住名字（user_name）
        - “我喜欢/我很喜欢 XX” → 记住兴趣（interest_XX，累计权重）
        - “我讨厌/我不喜欢 XX” → 记住反感（dislike_XX）
        记忆写入 memory.json，之后本地 AI 的上下文会带上这些偏好，
        让 Ralsei 越聊越了解主人（这是"训练"最朴素的形式）。
        """
        try:
            parent = self.parent
            ms = getattr(parent, 'memory_system', None)
            if ms is None or not callable(getattr(ms, 'learn_user_preference', None)):
                return
            import re as _re
            s = str(user_input).strip()
            if not s:
                return
            # 名字：我(叫|是)XX（1~8 个中文字符或字母数字）
            m = _re.search(r'我(?:叫|是)([\u4e00-\u9fa5A-Za-z0-9]{1,8})', s)
            if m:
                _name = m.group(1).strip()
                if _name and _name not in ('Ralsei', 'ralsei'):
                    ms.learn_user_preference('user_name', _name)
            # 喜欢：我(很/特别/超)?喜欢XX
            m = _re.search(r'我(?:很|特别|超|最)?喜欢([\u4e00-\u9fa5A-Za-z0-9]{1,12})', s)
            if m:
                _topic = m.group(1).strip()
                if _topic and not _topic.endswith(('吗', '呢', '呀', '吧')):
                    _cur = 0.0
                    try:
                        _cur = float(ms.get_user_preference(f'interest_{_topic}', 0.0))
                    except (TypeError, ValueError):
                        _cur = 0.0
                    ms.learn_user_preference(f'interest_{_topic}', _cur + 1.0)
            # 讨厌：我(不|很)?(喜欢|讨厌|反感)XX
            m = _re.search(r'我(?:不|很)?(?:喜欢|讨厌|反感)([\u4e00-\u9fa5A-Za-z0-9]{1,12})', s)
            if m:
                _topic = m.group(1).strip()
                if _topic and not _topic.endswith(('吗', '呢', '呀', '吧')):
                    _cur = 0.0
                    try:
                        _cur = float(ms.get_user_preference(f'dislike_{_topic}', 0.0))
                    except (TypeError, ValueError):
                        _cur = 0.0
                    ms.learn_user_preference(f'dislike_{_topic}', _cur + 1.0)
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)

    # ---------------- 本地 AI 思考占位（等待回复时像在停顿组织语言） ----------------
    def _ai_thinking_on(self):
        # 思考期间取消自动隐藏：本地模型推理常需数秒~十几秒，
        # 不能让对话框在等待回复时自己淡出。
        try:
            self._auto_hide_timer.stop()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        try:
            self.stop_typing()
            self._commit_previous_ralsei_into_history()
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        # 显示 Ralsei 式省略号 + 思考表情（不写"正在想怎么回答你"这类暴露文字）
        self._streaming = False      # 新一轮请求开始：清掉上一轮的流式状态
        self._stream_raw = ""
        self.typing_text = self.AI_THINKING_PLACEHOLDER
        self.typing_index = len(self.typing_text)
        self.is_typing = False
        try:
            self.set_face("thinking")
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
        self._refresh_display()

    def _ai_thinking_off(self):
        self._streaming = False
        self._stream_raw = ""
        self.typing_text = ""
        self.typing_index = 0
        self.is_typing = False
        # 表情留给下一条 add_dialogue 按情绪设置（这里不抢）
        self._refresh_display()

    def mousePressEvent(self, event):
        # 记录拖动起点（点击展开输入框延迟到 mouseReleaseEvent 的单击判定——
        # 修复：原来一按鼠标就展开输入框并重算窗口大小，拖动时窗口尺寸变化、
        # 位置被重算，导致对话框"拖不动"）
        if event.button() == Qt.LeftButton:
            # 点一下对话框 = 有动静：20 秒自动隐藏倒计时重新开始
            # （只重置"隐藏倒计时"，不动 _last_activity —— 后者表示"真的在聊天"，
            #   供 10 分钟自主开口闸门判断有没有打断进行中的对话）
            self._schedule_auto_hide()
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            self._is_dragging = False
            # 记录按下时的全局坐标，用于在 mouseMoveEvent 中判断是否真正移动了足够距离
            self._drag_press_global = event.globalPos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.drag_position.isNull():
            # 只有真正移动超过 3 像素才标记为拖拽（区分单击 vs 拖动）
            # 否则点击时的轻微抖动会被误判为拖拽，导致 click-to-skip-typing 失效
            press = getattr(self, '_drag_press_global', None)
            if press is not None:
                moved = (event.globalPos() - press).manhattanLength()
                if moved < 3:
                    return  # 移动量不足，仍视为点击，不进入拖拽
            self._is_dragging = True
            # 【修复】clamp 到屏幕边界，防止拖出屏幕
            new_pos = event.globalPos() - self.drag_position
            clamped = self._clamp_to_screen(
                QRect(new_pos.x(), new_pos.y(), self.width(), self.height()))
            self.move(clamped.x(), clamped.y())
            event.accept()

    def mouseReleaseEvent(self, event):
        was_dragging = self._is_dragging
        self._is_dragging = False
        self.drag_position = QPoint()
        # 清掉按下起点，避免残留坐标影响下一次交互判定
        self._drag_press_global = None
        # 用户拖过一次就记住：之后 _follow_timer 不再强制定位到正下方
        if was_dragging:
            self._user_moved = True
        # 单击（没拖动）→ 展开输入框让用户说话；若正在打字则跳过打字显示完整文本
        if not was_dragging:
            if not self.is_typing and not self._input_bar.isVisible():
                self._input_bar.show()
                self._recalc_size_to_content()
                self.input_field.setFocus()
            elif self.is_typing:
                self.stop_typing()
        event.accept() if was_dragging else super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # 双击 → 切换输入框显示
        if self._input_bar.isVisible():
            self._input_bar.hide()
            self._recalc_size_to_content()
        else:
            self._input_bar.show()
            self._recalc_size_to_content()
            self.input_field.setFocus()

    # ------------------------------------------------------------- commands
    def handle_chat_commands(self, user_input):
        """返回 (reply, face_type)，让调用方统一 add_dialogue。没命中返回 None。"""
        low = user_input.lower().strip()
        raw = user_input.strip()

        # ===== 修复：游戏进行中，退出指令不能被闲聊指令截获 =====
        # 本方法在 send_message 里先于 handle_game_input 执行，而下面有一组
        # ("游戏", ...) 关键词指令。于是正在玩石头剪刀布/猜数字时输入"退出游戏"，
        # 会命中"游戏"关键词并直接 return，返回一句与游戏状态矛盾的闲聊
        # （"我最喜欢玩游戏了！想玩什么呢？"），游戏永远退不出去。
        # 这里把退出类指令放行给游戏状态机处理。
        try:
            _playing = bool(getattr(self.parent, 'game_state', {}).get('is_playing'))
        except Exception:
            _playing = False
        if _playing and any(w in raw for w in ("退出游戏", "结束游戏", "退出", "不玩了", "不玩", "算了")):
            return None

        # —— 工具函数：获取当前状态信息 ——
        def _get_status_text():
            try:
                e_sys = self.parent.emotion_system
                # 修复：主对象属性名是 energy_hunger，不是 energy_hunger_system——
                # 原代码永远取到 None，状态查询从不显示精力/饥饿。
                eh_sys = getattr(self.parent, 'energy_hunger', None)
                cur_emo, emo_val = e_sys.get_current_emotion()
                parts = [f"当前情绪：{cur_emo}（强度 {int(abs(emo_val))}）"]
                if eh_sys is not None:
                    parts.append(f"精力：{int(eh_sys.energy)}/100")
                    parts.append(f"饥饿：{int(eh_sys.hunger)}/100")
                w_sys = getattr(self.parent, 'weather_system', None)
                if w_sys is not None:
                    w = w_sys.get_current_weather()
                    parts.append(f"天气：{w}")
                return "  ".join(parts)
            except Exception:
                return "暂时读不到状态..."

        # —— 按优先级排序的指令表：更精确的关键词放前面 ——
        cmds = [
            # ———————— 系统控制 ————————
            ("你去睡觉吧", (lambda: [
                self.parent.enter_sleep_mode(),
                self.parent.emotion_system.add_emotion("sleepy", 40)],
                "嗯... 好困，我去睡一会儿，zZZ...", "sleepy")),
            ("睡觉", (lambda: [
                self.parent.enter_sleep_mode(),
                self.parent.emotion_system.add_emotion("sleepy", 40)],
                "嗯... 好困，我去睡一会儿，zZZ...", "sleepy")),
            ("休眠", (lambda: [
                self.parent.enter_sleep_mode(),
                self.parent.emotion_system.add_emotion("sleepy", 40)],
                "好的~ 我休息一下，有事叫我！", "sleepy")),
            ("暂停", (lambda: [
                self.parent.enter_sleep_mode(),
                self.parent.emotion_system.add_emotion("calm", 30)],
                "好的，我先暂停活动~", "peaceful")),
            ("醒醒", (lambda: [
                self.parent.wake_up() if hasattr(self.parent, 'wake_up') else None,
                self.parent.emotion_system.add_emotion("happy", 30)],
                "啊~ 睡醒了！精神满满！", "happy")),
            ("醒来", (lambda: [
                self.parent.wake_up() if hasattr(self.parent, 'wake_up') else None,
                self.parent.emotion_system.add_emotion("happy", 30)],
                "啊~ 睡醒了！精神满满！", "happy")),

            # ———————— 状态与天气（reply是延迟求值lambda，第三个face参数作备用会被覆盖）————————
            ("查看天气", (
                lambda: self.parent.emotion_system.add_emotion("curious", 20),
                (lambda: (
                    "今天是" + getattr(self.parent.weather_system, 'get_current_weather',
                                        lambda: "sunny")() + "呀！"
                    + getattr(self.parent.weather_system, 'get_weather_response',
                              lambda: {'dialogue': ''})()['dialogue'],
                    "curious")),
                "curious")),
            ("天气怎么样", (
                lambda: self.parent.emotion_system.add_emotion("curious", 20),
                (lambda: (
                    "今天是" + getattr(self.parent.weather_system, 'get_current_weather',
                                        lambda: "sunny")() + "！"
                    + getattr(self.parent.weather_system, 'get_weather_response',
                              lambda: {'dialogue': ''})()['dialogue'],
                    "curious")),
                "curious")),
            ("天气", (
                lambda: self.parent.emotion_system.add_emotion("curious", 20),
                (lambda: (
                    "今天是" + getattr(self.parent.weather_system, 'get_current_weather',
                                        lambda: "sunny")() + "！"
                    + getattr(self.parent.weather_system, 'get_weather_response',
                              lambda: {'dialogue': ''})()['dialogue'],
                    "curious")),
                "curious")),
            ("状态", (
                lambda: self.parent.emotion_system.add_emotion("curious", 10),
                (lambda: (_get_status_text(), "curious")),
                "curious")),
            ("你现在怎么样", (
                lambda: self.parent.emotion_system.add_emotion("curious", 10),
                (lambda: (_get_status_text(), "peaceful")),
                "peaceful")),
            ("精力", (
                lambda: self.parent.emotion_system.add_emotion("curious", 10),
                (lambda: (_get_status_text(), "curious")),
                "curious")),
            ("饿了吗", (
                lambda: self.parent.emotion_system.add_emotion("curious", 10),
                (lambda: (_get_status_text(), "curious")),
                "curious")),

            # ———————— 互动动作（原版保留，放在后面避免上面的被误匹配）————————
            ("喂食", (lambda: self.parent.emotion_system.add_emotion("happy", 35),
                    "啊呜~ 真好吃！谢谢你~", "happy")),
            ("喂我", (lambda: self.parent.emotion_system.add_emotion("happy", 35),
                    "啊呜~ 真好吃！谢谢你~", "happy")),
            ("吃东西", (lambda: self.parent.emotion_system.add_emotion("happy", 35),
                    "啊呜~ 真好吃！", "happy")),
            ("抚摸", (lambda: self.parent.emotion_system.add_emotion("happy", 30),
                      "嘿嘿~ 好舒服呀！", "happy")),
            ("摸摸头", (lambda: [
                self.parent.emotion_system.add_emotion("happy", 25),
                self.parent.emotion_system.add_emotion("shy", 15)],
                "好呀好呀~ 最喜欢被摸头了！", "shy")),
            ("摸我", (lambda: [
                self.parent.emotion_system.add_emotion("happy", 25),
                self.parent.emotion_system.add_emotion("shy", 15)],
                "好呀好呀！", "shy")),
            ("游戏", (lambda: self.parent.emotion_system.add_emotion("excited", 35),
                      "我最喜欢玩游戏了！想玩什么呢？", "happy")),
            ("跳舞", (lambda: [
                self.parent.emotion_system.add_emotion("excited", 40),
                self.parent.emotion_system.add_emotion("happy", 30)],
                "你看！我跳得怎么样？✨", "happy")),
            ("唱歌", (lambda: [
                self.parent.emotion_system.add_emotion("happy", 35),
                self.parent.emotion_system.add_emotion("expectant", 25)],
                "啦啦啦~ 唱首歌给你听！", "happy")),
            ("挥手", (lambda: [
                self.parent.emotion_system.add_emotion("happy", 25),
                self.parent.emotion_system.add_emotion("surprised", 20)],
                "你好呀！好久不见~", "happy")),
            ("拥抱", (lambda: [
                self.parent.emotion_system.add_emotion("happy", 40),
                self.parent.emotion_system.add_emotion("grateful", 30)],
                "谢谢你的拥抱！好温暖~", "happy")),
            ("抱抱", (lambda: [
                self.parent.emotion_system.add_emotion("happy", 40),
                self.parent.emotion_system.add_emotion("grateful", 30)],
                "来抱抱！", "happy")),
            ("笑一个", (lambda: self.parent.emotion_system.add_emotion("happy", 40),
                    "哈哈哈哈！今天真的好开心！", "happy")),
            ("哭", (lambda: self.parent.emotion_system.add_emotion("sad", 35),
                    "呜... 为什么要让我哭嘛...", "sad")),
            ("喝茶", (lambda: self.parent.emotion_system.add_emotion("happy", 25),
                      "这茶真好喝！暖暖的~", "happy")),
            ("pose", (lambda: [
                self.parent.emotion_system.add_emotion("proud", 30),
                self.parent.emotion_system.add_emotion("happy", 25)],
                "你看我摆的姿势怎么样？很帅气吧！", "serious")),

            # —— 石头剪刀布 / 猜数字触发（修复：原指令表没有入口，聊天说
            #    "玩石头剪刀布/猜数字"只会得到一句随机闲聊，游戏从不开始）——
            ("石头剪刀布", (lambda: [
                self.parent.emotion_system.add_emotion("excited", 35),
                self.parent.start_rock_paper_scissors()],
                "好呀~ 来玩石头剪刀布！你要出什么？石头、剪刀还是布？", "happy")),
            ("猜数字", (lambda: [
                self.parent.emotion_system.add_emotion("excited", 35),
                self.parent.start_guess_number()],
                "好呀~ 来玩猜数字！我 1-100 想好了一个数字，你来猜~", "happy")),
            ("猜一个数", (lambda: [
                self.parent.emotion_system.add_emotion("excited", 35),
                self.parent.start_guess_number()],
                "好呀~ 来玩猜数字！我 1-100 想好了一个数字，你来猜~", "happy")),

            # —— 躲猫猫游戏触发（修复：已在其他游戏中时不误说"开始藏"）——
            ("躲猫猫", (lambda: [
                self.parent.emotion_system.add_emotion("excited", 40),
                self.parent.emotion_system.add_emotion("happy", 30),
                self.parent.start_hide_and_seek_game()],
                (lambda: (
                    "我们已经开始躲猫猫啦，快来找我~", "happy")
                    if getattr(self.parent, '_hide_stage', None) is not None
                    else ("现在还在玩别的呢，等这局结束再躲猫猫吧~", "curious")),
                "happy")),
            ("捉迷藏", (lambda: [
                self.parent.emotion_system.add_emotion("excited", 40),
                self.parent.emotion_system.add_emotion("happy", 30),
                self.parent.start_hide_and_seek_game()],
                (lambda: (
                    "我们已经开始捉迷藏啦，快来找我~", "happy")
                    if getattr(self.parent, '_hide_stage', None) is not None
                    else ("现在还在玩别的呢，等这局结束再捉迷藏吧~", "curious")),
                "happy")),
        ]

        for kw, (action, reply, face) in cmds:
            # 第十八轮：按关键词归属选命中规则（硬指令=子串；软闲聊=指令式），
            # 避免"我快哭了""我做的游戏上线了"这类正经话被罐头台词截胡。
            hit = (kw in raw) if kw in self._HARD_CMDS \
                else self._is_command_phrase(raw, kw)
            if hit:
                try:
                    result = action()
                except Exception as _e:
                    import traceback
                    _log.debug(f"[dialogue_cmd] 关键词 '{kw}' 触发 action 失败: {_e}")
                    traceback.print_exc()
                    result = None
                # reply/face 支持延迟求值（lambda返回 (reply, face)），方便读实时状态
                if callable(reply):
                    try:
                        reply, face = reply()
                    except Exception as _e2:
                        # 修复：求值失败时 reply 仍是可调用对象，会显示成
                        # "<function ...>" 文本。回退为一句兜底话。
                        _log.debug(f"[dialogue_cmd] reply 求值失败: {_e2}")
                        reply = "诶... 我刚才没反应过来，再说一次好吗？"
                        face = "curious"
                return (reply, face)
        return None

    def handle_file_commands(self, user_input):
        raw = user_input.strip()
        low = raw.lower()

        # —— 打开文件/文件夹：交给 main.py 的统一流程（施法→打开）——
        if "打开" in raw:
            # 尝试匹配"打开 XX"（不管是文件还是文件夹，都走施法流程）
            # 具体解析交给 main.py.handle_file_operation 做正则匹配
            result = self.parent.handle_file_operation(raw)
            if result:
                return True

        # —— 新建文件夹 ——
        if any(k in raw for k in ["新建文件夹", "创建文件夹", "新建目录"]):
            try:
                import os
                import datetime
                # 修复：用真实桌面路径（OneDrive 重定向兼容）
                desktop = self.parent.desktop_interaction.desktop_path
                name = f"新建文件夹_{datetime.datetime.now().strftime('%H%M%S')}"
                new_dir = os.path.join(desktop, name)
                os.makedirs(new_dir, exist_ok=True)
                self.parent.emotion_system.add_emotion("happy", 25)
                self.add_dialogue("ralsei", f"好啦！已经在桌面新建了「{name}」文件夹~", "happy")
                return True
            except Exception as e:
                self.add_dialogue("ralsei", f"呜... 新建文件夹失败了：{e}", "sad")
                return True

        # —— 删除文件/文件夹（需要用户明确说"删除XX"，并弹确认框）——
        if any(k in raw for k in ["删除", "删掉", "移除"]) and "回收站" not in low:
            # 修复：原来把整句用户文本直接传给 main.delete_file（它按文件路径处理），
            # 永远解析不到目标 → 只得到"不太确定"的模糊提示，删除功能实际不可用。
            # 现在先解析"删除 XX"里的目标名，按名匹配桌面文件再交给 delete_file（带确认框）。
            import re as _re
            target = _re.sub(r'^(请|帮我)?(删除|删掉|移除)\s*', '', raw)
            target = _re.sub(r'[呢？。！!~～\s]+$', '', target).strip()
            matched_path = None
            if target:
                try:
                    self.parent.desktop_interaction.update_desktop_elements()
                    tl = target.lower()
                    for el in self.parent.desktop_interaction.desktop_elements:
                        if el.get('type') != 'file':
                            continue
                        name = el.get('name', '') or ''
                        base = os.path.splitext(name)[0].lower()
                        if name.lower() == tl or base == tl or (len(tl) >= 2 and tl in name.lower()):
                            matched_path = el['path']
                            break
                except Exception as e:  # 修复：原先静默吞噬
                    _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
            if matched_path and hasattr(self.parent, 'delete_file') and callable(self.parent.delete_file):
                try:
                    self.parent.delete_file(matched_path)
                    return True
                except Exception as e:  # 修复：原先静默吞噬
                    _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
            # 没解析到明确目标：友好提示（不误删）
            self.add_dialogue("ralsei",
                "这个... 我不太确定具体要删哪个文件。能说得更具体一点吗？",
                "curious")
            return True

        # —— 列出桌面文件/看看有什么 ——
        if any(k in raw for k in ["桌面有什么", "看桌面", "有什么文件", "桌面上的东西"]):
            try:
                import os
                # 修复：用真实桌面路径（OneDrive 重定向兼容）
                desktop = self.parent.desktop_interaction.desktop_path
                names = [n for n in os.listdir(desktop) if not n.startswith(".")][:20]
                if not names:
                    self.add_dialogue("ralsei", "桌面上好像干干净净的呢~", "peaceful")
                else:
                    preview = "、".join(names[:10])
                    extra = f" 等{len(names)}项" if len(names) > 10 else ""
                    self.parent.emotion_system.add_emotion("curious", 15)
                    self.add_dialogue("ralsei", f"我看到：{preview}{extra}。要我帮你打开哪个吗？", "curious")
                return True
            except Exception:
                return False

        # —— 窗口管理 ——
        if any(k in raw for k in ["关闭窗口", "关掉窗口", "最小化", "最大化"]):
            if hasattr(self.parent, 'handle_window_operation'):
                try:
                    res = self.parent.handle_window_operation(raw)
                    if res is not None:
                        return True
                except Exception as e:  # 修复：原先静默吞噬
                    _log.debug("dialogue_ui 防御性异常（已忽略）: %s", e)
            self.add_dialogue("ralsei", "好的！不过我只能用后台方式操作当前可见的窗口哦。", "serious")
            return True

        return None

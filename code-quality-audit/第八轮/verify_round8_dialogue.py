# -*- coding: utf-8 -*-
"""第八轮 · 对话 UI 硬伤修复验证（Task #10）

对应用户报的两个问题：
  1) 对话框底部 ▼ 一闪一闪 → 文字一上一下地抖 → 看不清
  2) 对话框没办法下拉（历史翻不上去 / 视图每 530ms 被弹回顶部）

根因（第七轮静态复查 + 本轮离线实测确认）：
  ▼ 原本是拼进正文 HTML 的一个内联字符。它占的宽度参与换行计算，所以每 530ms
  一次闪烁都可能让最后一行多占/少占一行 → 文档高度变化 → _recalc_size_to_content
  同步 setFixedHeight + resize → 整框高度抖动；同时闪烁走的是 setHtml 全量重建，
  重建会把滚动条复位到顶部，于是视图每 530ms 被弹回顶部一次（既抖又"下拉不了"）。

修复：
  - ▼ 改为 _frame 上的独立 QLabel 覆盖层（贴右下角，完全避开正文区），
    闪烁只切它的可见性，不再触碰正文文档；
  - _refresh_display 前记录滚动位置与"是否贴底"，setHtml 后恢复：贴底才跟随，
    用户翻上去就原地不动；
  - 用户拖动滚动条（sliderPressed）期间不抢位置。

第 44 轮备注：对话框外框已从"圆角样式表框"换成**原作风格的方角自绘框**
（`modules/dr_textbox.py` 复刻原作 `scr_darkbox()`）。因此 T4.5 那
"覆盖层不被圆角切掉"的判据前提（`border-radius`）已不存在，判据升级为
等价的"4 个角都落在黑底可见区内"（内缩 `dr_textbox.BLACK_INSET`），
语义仍是"▼ 不被框的边缘装饰压住/切掉"。

本脚本在 offscreen Qt 下把渲染管线真跑一遍，用「文档高度/滚动值是否随闪烁变化」
作为抖动的量化判据。全部断言均不需人工看屏幕。
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
for _p in (os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if _p not in sys.path:
        sys.path.append(_p)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, detail))
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  <- " + str(detail)) if detail else ""))


# --------------------------------------------------------------------- harness
class FakeLoader:
    def has_face(self, name):
        return False

    def get_face(self, name):
        return None


class FakeEmotion:
    def get_current_emotion(self):
        return ("normal", 0)

    def get_face_for_emotion(self, _emotion, _intensity):
        return "normal"


def build_ui():
    from PyQt5.QtWidgets import QApplication, QWidget

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    class FakeParent(QWidget):
        """DialogueUI(parent) 要求 parent 是 QWidget；同时提供它读取的系统属性。"""

        def __init__(self):
            super().__init__()
            self.sprite_loader = FakeLoader()
            self.emotion_system = FakeEmotion()
            self.sound_manager = None

    from dialogue_ui import DialogueUI
    ui = DialogueUI(FakeParent())
    ui.resize(540, 320)
    ui.show()
    for _ in range(6):
        app.processEvents()
    # 测试期间不要真的自动隐藏
    try:
        ui._auto_hide_timer.stop()
    except Exception:
        pass
    return app, ui


def visible_inset_of(ui):
    """框的"可见黑底区"相对矩形边缘的内缩量。

    第 44 轮起对话框改成**原作风格的方角框**（`modules/dr_textbox.py` 自绘的
    `scr_darkbox()` 复刻：外圈 8px 透明 + 4px 白线 + 黑芯），样式表里的
    `border-radius` 已整体移除。于是"被圆角切掉"这一前提对象消失，
    判据必须升级成等价口径 —— 见 t4 末尾。

    单一真源是 `dr_textbox.BLACK_INSET`（=14，源自原作 `scr_dbox` 的
    `draw_rectangle(xxx+38, yyy+16, ...)` 相对框矩形各内缩 14px）。
    取不到时回落到同名常量，保证套件在极端环境下仍可执行。
    """
    try:
        import dr_textbox as _drb
        return int(_drb.BLACK_INSET)
    except Exception:
        return 14


# ------------------------------------------------------------------------ tests
def t1_blink_does_not_jitter(app, ui):
    """核心：闪烁不再改变文档高度 / 控件高度 / 窗口高度。"""
    ui.add_dialogue("ralsei", "这是一段用来验证闪烁是否会导致抖动的长文本。" * 8)
    ui.stop_typing()
    for _ in range(4):
        app.processEvents()

    doc_h = []
    widget_h = []
    win_h = []
    for _ in range(6):
        ui._blink_cursor()
        app.processEvents()
        doc_h.append(round(ui.dialogue_content.document().size().height(), 3))
        widget_h.append(ui.dialogue_content.height())
        win_h.append(ui.height())

    check("T1.1 闪烁不再改变文档高度（文字不抖）",
          len(set(doc_h)) == 1, "doc_h=%s" % doc_h)
    check("T1.2 闪烁不再改变正文控件高度",
          len(set(widget_h)) == 1, "widget_h=%s" % widget_h)
    check("T1.3 闪烁不再改变整框高度",
          len(set(win_h)) == 1, "win_h=%s" % win_h)


def t2_blink_never_rebuilds_document(app, ui):
    """结构判据：_blink_cursor 不再调用 _refresh_display（=不再 setHtml）。"""
    calls = {"n": 0}
    original = ui._refresh_display

    def counting():
        calls["n"] += 1
        return original()

    ui._refresh_display = counting
    try:
        for _ in range(4):
            ui._blink_cursor()
        n_blink = calls["n"]
        ui._refresh_display()           # 对照：走被替换后的版本，应该会 +1
        n_after_refresh = calls["n"]
    finally:
        ui._refresh_display = original

    check("T2.1 闪烁不再触发 setHtml 全量重建",
          n_blink == 0, "blink 引发的刷新次数=%d" % n_blink)
    check("T2.2 对照：正常刷新仍会重建（计数有效）",
          n_after_refresh == 1, "refresh 引发的刷新次数=%d" % n_after_refresh)


def t3_cursor_out_of_document(app, ui):
    """▼ 必须彻底移出正文文本，否则宽度会继续参与换行。"""
    ui._cursor_visible = True
    ui._update_cursor_overlay()
    app.processEvents()
    plain = ui.dialogue_content.toPlainText()
    html = ui.dialogue_content.toHtml()
    check("T3.1 ▼ 不出现在正文纯文本里", "▼" not in plain)
    check("T3.2 ▼ 不出现在正文 HTML 里", "▼" not in html)
    check("T3.3 独立覆盖层存在且文字为 ▼",
          getattr(ui, "_cursor_label", None) is not None
          and ui._cursor_label.text() == "▼")


def t4_cursor_overlay_toggles_and_fits(app, ui):
    """覆盖层随闪烁切显隐；位置在右下角、避开正文、且仍在圆角框内。"""
    ui.typing_text = "有前台消息"
    ui.is_typing = False
    ui._cursor_visible = True
    ui._update_cursor_overlay()
    vis_a = not ui._cursor_label.isHidden()
    ui._blink_cursor()
    vis_b = not ui._cursor_label.isHidden()
    ui._blink_cursor()
    vis_c = not ui._cursor_label.isHidden()
    check("T4.1 覆盖层随闪烁切换显隐（True→False→True）",
          (vis_a, vis_b, vis_c) == (True, False, True),
          "%s" % ((vis_a, vis_b, vis_c),))

    # 无前台消息时必须隐藏（避免空框上挂个 ▼）
    ui.typing_text = ""
    ui._update_cursor_overlay()
    check("T4.2 无前台消息时覆盖层隐藏", ui._cursor_label.isHidden())

    # 几何：右下角、避开正文、在框内
    ui.typing_text = "有前台消息"
    ui._cursor_visible = True
    ui._update_cursor_overlay()
    ui.resize(540, 320)
    ui._position_cursor_overlay()
    app.processEvents()

    lbl = ui._cursor_label
    # 正文可绘制区的真实右边界 = QTextEdit 的 viewport 右边界（已扣掉内边距/滚动条），
    # 这是"文字最多画到哪"的硬边界，用它判定是否压字最可靠。
    vp = ui.dialogue_content.viewport()
    vp_right = vp.mapTo(ui, vp.rect().topRight()).x()
    g = lbl.geometry()

    check("T4.3 覆盖层不压正文（与正文可绘制区留出间隙）",
          g.x() - vp_right >= 4,
          "lbl.x=%d, 正文视口右边界=%d, 间隙=%d px" % (g.x(), vp_right, g.x() - vp_right))
    check("T4.4 覆盖层不越出对话框",
          g.right() <= ui.width() - 1 and g.bottom() <= ui.height() - 1,
          "lbl=%s win=%s" % (g, ui.size()))

    # 【第 44 轮升级】原标题「覆盖层未被圆角切掉」。对话框已改成原作方角框
    # （`dr_textbox.DrTextboxFrame`，样式表 border-radius 全清），方角不存在裁切，
    # 但**边框带仍在**（32px：外圈 8px 透明 + 4px 白线 + 黑芯）⇒ 等价的新口径是：
    # ▼ 的 4 个角必须全部落在框的**可见黑底区**内（各边内缩 BLACK_INSET），
    # 既不被白线/四角宝石装饰压住，也不越出框。
    # 鉴别力：把 `_position_cursor_overlay` 的 margin 改成 0 或负数 → 立刻报红。
    inset = visible_inset_of(ui)
    vis = (inset, inset, ui.width() - inset, ui.height() - inset)
    corners = [(g.left(), g.top()), (g.right(), g.top()),
               (g.left(), g.bottom()), (g.right(), g.bottom())]
    outside = [c for c in corners
               if not (vis[0] <= c[0] <= vis[2] and vis[1] <= c[1] <= vis[3])]
    check("T4.5 覆盖层未被方角边框带切掉（4 角都在黑底可见区内）",
          not outside, "可见区=%s 越界角=%s inset=%d" % (vis, outside, inset))


def t5_scroll_position_is_preserved(app, ui):
    """核心：上翻历史后，刷新/闪烁都不能把视图弹回顶部。"""
    ui.typing_text = ""
    ui.is_typing = False
    ui._history_html = "".join(
        '<div style="color:#ffffff;line-height:1.45;">'
        '第 %02d 行历史消息，用于把文档撑高以验证滚动行为。</div>' % i
        for i in range(60))
    ui._refresh_display()
    for _ in range(3):
        app.processEvents()

    sb = ui.dialogue_content.verticalScrollBar()
    check("T5.1 内容超限后出现滚动条（确实可滚动）",
          sb.maximum() > 0, "max=%d h=%d" % (sb.maximum(), ui.dialogue_content.height()))

    # (a) 用户翻到顶部
    sb.setValue(0)
    ui._refresh_display()
    app.processEvents()
    check("T5.2 翻到顶部后刷新，视图不被弹回底部",
          sb.value() == 0, "value=%d max=%d" % (sb.value(), sb.maximum()))

    # (b) 闪烁也不能动滚动位置（旧实现在这里每 530ms 复位到顶）
    vals = []
    for _ in range(5):
        ui._blink_cursor()
        app.processEvents()
        vals.append(sb.value())
    check("T5.3 闪烁完全不动滚动位置",
          set(vals) == {0}, "values=%s" % vals)

    # (c) 用户拖住滚动条时，刷新不抢位置
    ui._scrollbar_dragging = True
    sb.setValue(3)
    ui._refresh_display()
    app.processEvents()
    check("T5.4 拖动滚动条期间刷新不抢位置",
          sb.value() == 3, "value=%d" % sb.value())
    ui._scrollbar_dragging = False


def t6_follows_bottom_when_at_bottom(app, ui):
    """对照：本来就贴在底部时，新内容必须自动跟随到底。"""
    sb = ui.dialogue_content.verticalScrollBar()
    sb.setValue(sb.maximum())
    old_max = sb.maximum()

    ui._history_html += ('<div style="color:#ffffff;line-height:1.45;">'
                         '新追加的一行，用来验证自动跟随到底。</div>')
    ui._refresh_display()
    for _ in range(3):
        app.processEvents()

    check("T6.1 贴底时新内容自动跟随到底",
          sb.value() == sb.maximum() and sb.maximum() >= old_max,
          "value=%d max=%d (old_max=%d)" % (sb.value(), sb.maximum(), old_max))


def t7_no_duplicate_cursor_in_history(app, ui):
    """历史 HTML 里也不应残留 ▼（避免存档/多轮拼接把光标写进历史）。"""
    ui.add_dialogue("user", "你好")
    ui.add_dialogue("ralsei", "你好呀，我是 Ralsei。")
    ui.stop_typing()
    for _ in range(3):
        app.processEvents()
    check("T7.1 历史缓冲不含 ▼", "▼" not in ui._history_html)
    check("T7.2 正文纯文本不含 ▼", "▼" not in ui.dialogue_content.toPlainText())


def main():
    app, ui = build_ui()
    try:
        t1_blink_does_not_jitter(app, ui)
        t2_blink_never_rebuilds_document(app, ui)
        t3_cursor_out_of_document(app, ui)
        t4_cursor_overlay_toggles_and_fits(app, ui)
        t5_scroll_position_is_preserved(app, ui)
        t6_follows_bottom_when_at_bottom(app, ui)
        t7_no_duplicate_cursor_in_history(app, ui)
    finally:
        try:
            ui.hide()
            ui.deleteLater()
        except Exception:
            pass

    total = len(RESULTS)
    passed = sum(1 for ok, _n, _d in RESULTS if ok)
    print("-" * 68)
    print("第八轮对话 UI 验证：%d/%d PASS, %d FAIL" % (passed, total, total - passed))
    for ok, name, detail in RESULTS:
        if not ok:
            print("  FAIL: %s  %s" % (name, detail))
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())

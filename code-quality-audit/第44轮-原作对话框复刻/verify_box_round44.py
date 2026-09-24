# -*- coding: utf-8 -*-
"""第 44 轮回归锁：**原作 Deltarune 对话框复刻不许静默漂移**。

用户口径（第 44 轮唯一新指令）
------------------------------
    「对了，对话框改成和原作风格一样的，最好就是原作的对话框」

守的是什么
----------
对话框外框从"圆角样式表框（`QFrame#drFrame` + border-radius:18px + 半透明黑）"
换成**原作 `scr_darkbox()` 的 9-slice 复刻**（`modules/dr_textbox.py`：
32px 边框带 + 32×32 八帧动画角 + 纯黑内芯），字体换成项目根的像素字体
（`普通字体.ttf` = FZXS12）、打字音按原作 `scr_textsound()` 跳标点。

本套件的核心不是"我写的常量等于我写的常量"（那是恒真判据），而是
**让产品常量必须能从原作反编译源码里被反推出来**：

  A 段 —— 从 `_evidence/gml/*.gml`（UTMT `dump` 出来的真源码）解析出
          63 / 32 / 10 / 14 / 8 帧 / 静音字符表，逐条与 `dr_textbox` 及
          `dialogue_ui` 的常量对齐。源码被换掉、常量被手改，都会报红。

配套：
  C/D 段 —— 纯函数语义（`jewel_frame` / `textbox_metrics` / `darkbox_blits` 几何）
  E 段 —— 素材结构（尺寸 / 8 帧互不相同 / 剖面像素：外圈透明→白线→黑芯）
  F 段 —— 产品接线（框架替换生效 / 无 border-radius / 打字音判据真被调用 /
          隐藏即停表 / 光标仍在黑底可见区内）
  G 段 —— 恒真判据自查

**不联网、不调 Ollama、不需要显示器**（Qt 走 offscreen）。
鉴别力已体检：把 `dr_textbox.BAND` 改成 31 → A2/B 段立刻报红；
把 `_TEXT_SOUND_SKIP` 里的 `?` 删掉 → A8 立刻报红；
把 `_position_cursor_overlay` 的 margin 设成 0 → F7 立刻报红。
"""
import ast
import hashlib
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
for _p in (MODS, os.path.join(ROOT, 'ralsei_pet', 'src')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import dr_textbox as drb                      # noqa: E402
import dialogue_ui as dui                     # noqa: E402

GML_DIR = os.path.join(HERE, '_evidence', 'gml')
TB_DIR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'ui', 'textbox')
DUI_SRC = os.path.join(MODS, 'dialogue_ui.py')

PASS = 0
FAIL = 0
FAILED = []


def check(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('[PASS] %s    %s' % (name, detail))
    else:
        FAIL += 1
        FAILED.append(name)
        print('[FAIL] %s    %s' % (name, detail))


def read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


SRC_BOX = read(os.path.join(GML_DIR, 'gml_GlobalScript_scr_darkbox.gml'))
SRC_DBOX = read(os.path.join(GML_DIR, 'gml_GlobalScript_scr_dbox.gml'))
SRC_SND = read(os.path.join(GML_DIR, 'gml_GlobalScript_scr_textsound.gml'))
SRC_OTHER10 = read(os.path.join(GML_DIR, 'gml_Object_obj_dialoguer_Other_10.gml'))
DUI_TEXT = read(DUI_SRC)

print('=' * 72)
print('第 44 轮：原作对话框复刻')
print('=' * 72)

# ===========================================================================
# A. 原作源码 → 产品常量（反推，不是自证）
# ===========================================================================
_m = re.search(r'textbox_width\s*=\s*arg2\s*-\s*arg0\s*-\s*(\d+)', SRC_BOX)
_a2 = int(_m.group(1)) if _m else -1
check('A1 边框带长度差 63 是你从原作源码反推出来的（不是自己写的）',
      _a2 == 63 and drb.STRETCH_GAP == _a2,
      'gml arg2-arg0-%d ；产品 STRETCH_GAP=%d' % (_a2, drb.STRETCH_GAP))

_m = re.search(r'draw_sprite_stretched\(spr_textbox_top,\s*0,\s*arg0\s*\+\s*(\d+),'
               r'\s*arg1,\s*textbox_width,\s*(\d+)\)', SRC_BOX)
_band = int(_m.group(1)) if _m else -1
_bh = int(_m.group(2)) if _m else -1
check('A2 边框带厚度 = 上带 x 偏移 = 实绘高（原作同一数字）',
      _band == 32 and _bh == 32 and drb.BAND == _band and drb.CORNER_SIZE == _band,
      'gml x+%d / h=%d ；产品 BAND=%d CORNER_SIZE=%d'
      % (_band, _bh, drb.BAND, drb.CORNER_SIZE))

_m = re.search(r'cur_jewel\s*/\s*(\d+)', SRC_BOX)
_jt = int(_m.group(1)) if _m else -1
check('A3 角帧切换步长 = cur_jewel/10（原作）',
      _jt == 10 and drb.JEWEL_TICKS_PER_FRAME == _jt,
      'gml /%d ；产品 JEWEL_TICKS_PER_FRAME=%d' % (_jt, drb.JEWEL_TICKS_PER_FRAME))

# 原作对负宽/负高显式钳到 0（两处 if ... < 0 → = 0）
clamps = re.findall(r'if \((textbox_\w+) < 0\)\s*\{\s*\1 = 0;', SRC_BOX)
check('A4 原作把负宽/负高显式钳到 0，产品 textbox_metrics 同语义',
      set(clamps) == {'textbox_width', 'textbox_height'}
      and drb.textbox_metrics(0, 0, 1, 1) == (0, 0),
      'gml 钳制=%s ；产品 textbox_metrics(0,0,1,1)=%s'
      % (sorted(set(clamps)), drb.textbox_metrics(0, 0, 1, 1)))

# 名字带逗号，避免 'spr_textbox_top' 误命中 'spr_textbox_topleft'
c_top = SRC_BOX.count('spr_textbox_top,')
c_left = SRC_BOX.count('spr_textbox_left,')
c_tl = SRC_BOX.count('spr_textbox_topleft,')
check('A5 上/下共 2 次 top、左/右共 2 次 left、四角 4 次 topleft',
      c_top == 2 and c_left == 2 and c_tl == 8,   # 原文有 flag[8] 两分支 ⇒ 各 4×2
      'count top=%d left=%d topleft=%d（topleft 因 flag[8] 双分支为 8）'
      % (c_top, c_left, c_tl))
check('A5b 角块帧数 = 素材文件帧数 = 8',
      drb.CORNER_FRAMES == 8
      and len([f for f in os.listdir(TB_DIR)
               if re.match(r'spr_textbox_topleft_\d+\.png$', f)]) == 8,
      'CORNER_FRAMES=%d' % drb.CORNER_FRAMES)

# 黑底内缩 14：从 scr_dbox 的框矩形与黑矩形四条边之差反推
_mr = re.search(r'draw_rectangle\(xxx \+ (\d+), yyy \+ (\d+), xxx \+ (\d+),'
                r' yyy \+ (\d+), false\)', SRC_DBOX)
_mb = re.search(r'scr_darkbox\(\(xxx \+ (\d+)\) - 8, \(yyy \+ (\d+)\) - 8,'
                r' xxx \+ (\d+) \+ 8, yyy \+ (\d+) \+ 8\)', SRC_DBOX)
if _mr and _mb:
    bx1, by1, bx2, by2 = (int(_mr.group(i)) for i in (1, 2, 3, 4))
    fx1, fy1, fx2, fy2 = (int(_mb.group(i)) for i in (1, 2, 3, 4))
    fx1 -= 8
    fy1 -= 8
    fx2 += 8
    fy2 += 8
    ins = (bx1 - fx1, by1 - fy1, fx2 - bx2, fy2 - by2)
else:
    ins = (-1, -1, -1, -1)
check('A6 黑底相对框各内缩 14px（由原作的框矩形/黑矩形反推）',
      ins == (14, 14, 14, 14) and drb.BLACK_INSET == 14,
      'gml 四条边差=%s ；产品 BLACK_INSET=%d' % (list(ins), drb.BLACK_INSET))

check('A7 文字内缩 = 边框带 + 2 = 34（原作 32 边框 + 2 余量）',
      drb.CONTENT_INSET == drb.BAND + 2 == 34 and dui.DialogueUI.BOX_INSET == 34,
      'CONTENT_INSET=%d BOX_INSET=%d'
      % (drb.CONTENT_INSET, dui.DialogueUI.BOX_INSET))

check('A7b obj_dialoguer_Other_10 的框内坐标 19 / 20 / 10 仍在（口径来源）',
      ('(19 * f)' in SRC_OTHER10 and '(20 * f)' in SRC_OTHER10
       and '(10 * f)' in SRC_OTHER10),
      'gml 含 19*f / 20*f / 10*f')

# 打字音静音表：原作逐个 if 列出的字符，产品表必须**全覆盖**
_found = set(re.findall(r'getchar == "([^"]*)"', SRC_SND))
_found = {(chr(92) if v == '\\\\' else v) for v in _found}
_missing = sorted(_found - set(dui._TEXT_SOUND_SKIP))
check('A8 原作 scr_textsound 的静音字符表被产品全覆盖（含 ?）',
      len(_found) >= 12 and not _missing,
      'gml 命中 %d 个=%s ；缺=%s' % (len(_found), sorted(_found), _missing))

check('A9 打字机速率 rate=1 ⇒ 30fps 下 33ms/字',
      drb.ENGINE_FPS == 30 and drb.TYPE_INTERVAL_MS == 33,
      'ENGINE_FPS=%d TYPE_INTERVAL_MS=%d' % (drb.ENGINE_FPS, drb.TYPE_INTERVAL_MS))

# ===========================================================================
# B. 常量逐条（防只改 A 段口径不改实现）
# ===========================================================================
for nm, want in (('BAND', 32), ('STRETCH_GAP', 63), ('CORNER_SIZE', 32),
                 ('BLACK_INSET', 14), ('CORNER_FRAMES', 8),
                 ('JEWEL_TICKS_PER_FRAME', 10), ('ENGINE_FPS', 30),
                 ('TYPE_INTERVAL_MS', 33), ('CONTENT_INSET', 34)):
    got = getattr(drb, nm)
    check('B %s == %d' % (nm, want), got == want, '实际=%s' % got)

# ===========================================================================
# C. 纯函数语义
# ===========================================================================
check('C1 jewel_frame 边界：0..9→0 / 10..19→1 / 79→7 / 80→0',
      [drb.jewel_frame(t) for t in (0, 9, 10, 19, 20, 79, 80, 100)] ==
      [0, 0, 1, 1, 2, 7, 0, 2],
      '实际=%s' % [drb.jewel_frame(t) for t in (0, 9, 10, 19, 20, 79, 80, 100)])
check('C2 jewel_frame 周期 = JEWEL_TICKS_PER_FRAME * CORNER_FRAMES = 80',
      all(drb.jewel_frame(t) == drb.jewel_frame(t + 80) for t in range(80)),
      '逐个 tick 比 tick+80')
check('C3 textbox_metrics 正常：宽/高各 = 边长 - 63',
      drb.textbox_metrics(100, 50, 700, 250) == (537, 137),
      '实际=%s' % (drb.textbox_metrics(100, 50, 700, 250),))
check('C4 负控制：边长不足 63 时返回 0，不许出现负数',
      drb.textbox_metrics(0, 0, 10, 10) == (0, 0),
      '实际=%s' % (drb.textbox_metrics(0, 0, 10, 10),))

# ===========================================================================
# D. darkbox_blits 几何 —— 逐条对应原作的 draw 调用
# ===========================================================================
X1, Y1, X2, Y2 = 100, 60, 700, 260
BL = drb.darkbox_blits(X1, Y1, X2, Y2, 3)
kind = {}
for it in BL:
    if it[0] == 'corner':
        kind.setdefault('corner', []).append((it[1], it[2]))
    else:
        kind[it[0]] = it[1]
W, H = drb.textbox_metrics(X1, Y1, X2, Y2)

check('D1 黑底矩形 = 框各内缩 14',
      kind.get('fill') == (X1 + 14, Y1 + 14, (X2 - X1) - 28, (Y2 - Y1) - 28),
      'fill=%s' % (kind.get('fill'),))
check('D2 上带 = (x1+32, y1, W, 32)',
      kind.get('top') == (X1 + 32, Y1, W, 32), 'top=%s' % (kind.get('top'),))
check('D3 下带 = 从 y2+1 向上铺 32（等价原作 yscale=-2）',
      kind.get('top_v') == (X1 + 32, Y2 + 1 - 32, W, 32),
      'top_v=%s' % (kind.get('top_v'),))
check('D4 左带 = (x1, y1+32, 32, H)',
      kind.get('left') == (X1, Y1 + 32, 32, H), 'left=%s' % (kind.get('left'),))
check('D5 右带 = 从 x2+1 向左铺 32（等价原作 xscale=-2）',
      kind.get('left_h') == (X2 + 1 - 32, Y1 + 32, 32, H),
      'left_h=%s' % (kind.get('left_h'),))
check('D6 四角 32×32 且翻转标志 = 左上(0,0)/右上(1,0)/左下(0,1)/右下(1,1)',
      kind.get('corner') == [
          ((X1, Y1, 32, 32), (False, False)),
          ((X2 + 1 - 32, Y1, 32, 32), (True, False)),
          ((X1, Y2 + 1 - 32, 32, 32), (False, True)),
          ((X2 + 1 - 32, Y2 + 1 - 32, 32, 32), (True, True))],
      'corner=%s' % (kind.get('corner'),))
check('D7 四条带不越过框：带末端都不超 x2+1 / y2+1',
      kind['top'][0] + kind['top'][2] <= X2 + 1
      and kind['top_v'][1] + kind['top_v'][3] <= Y2 + 1
      and kind['left'][1] + kind['left'][3] <= Y2 + 1
      and kind['left_h'][0] + kind['left_h'][2] <= X2 + 1,
      'top右=%d top_v下=%d left下=%d left_h右=%d'
      % (kind['top'][0] + kind['top'][2], kind['top_v'][1] + kind['top_v'][3],
         kind['left'][1] + kind['left'][3],
         kind['left_h'][0] + kind['left_h'][2]))
# 负控制：极扁/极窄框不出带（原作 if (textbox_width > 0)）
BL2 = drb.darkbox_blits(0, 0, 40, 40, 0)
k2 = [it[0] for it in BL2 if it[0] != 'corner']
check('D8 负控制：边长 ≤63 时只出黑底+四角，不出上下左右带',
      k2 == ['fill'], '实际 kinds=%s' % k2)

# ===========================================================================
# E. 素材结构（防止拿别的图冒充）
# ===========================================================================
names = sorted(os.listdir(TB_DIR))
check('E1 素材目录条目齐全（8 角帧 + 上/左剖条 + README）',
      len(names) == 11
      and 'README.txt' in names
      and 'spr_textbox_top_0.png' in names
      and 'spr_textbox_left_0.png' in names,
      '共 %d 项: %s' % (len(names), names))

from PyQt5.QtGui import QImage                    # noqa: E402
from PyQt5.QtWidgets import QApplication, QWidget  # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv)

_corner_sizes, _hashes = set(), set()
for i in range(8):
    im = QImage(os.path.join(TB_DIR, 'spr_textbox_topleft_%d.png' % i))
    _corner_sizes.add((im.width(), im.height()))
    _hashes.add(hashlib.sha256(
        bytes(im.constBits().asstring(im.byteCount()))).hexdigest())
check('E2 8 张角帧全部 16×16',
      _corner_sizes == {(16, 16)}, '尺寸集合=%s' % sorted(_corner_sizes))
# 原作素材的**真实签名**：8 帧里只有 5 种不同图案（0/4 相同、1/7 相同、
# 2/3/5/6 相同）。所以判据是"≥2 种 ⇒ 确实是动画"，并把实际种数记下来，
# 既不会因为"只有 5 种"误报，也能在素材被整批换掉时报警。
check('E3 角帧确实是动画（≥2 种图案），且为原作素材签名 5 种',
      2 <= len(_hashes) <= 8, '去重后图案数=%d（原作素材本身只含 5 种）'
      % len(_hashes))
check('E3b 角帧图案种数 == 原作素材签名（5）', len(_hashes) == 5,
      '去重后图案数=%d' % len(_hashes))

_im_t = QImage(os.path.join(TB_DIR, 'spr_textbox_top_0.png'))
_im_l = QImage(os.path.join(TB_DIR, 'spr_textbox_left_0.png'))
check('E4 上/下剖条 1×16、左/右剖条 16×1（原作靠负 scale 翻转复用的单条）',
      (_im_t.width(), _im_t.height()) == (1, 16)
      and (_im_l.width(), _im_l.height()) == (16, 1),
      'top=%dx%d left=%dx%d' % (_im_t.width(), _im_t.height(),
                                _im_l.width(), _im_l.height()))


def _rows(im):
    out = []
    for y in range(im.height()):
        c = im.pixelColor(0, y)
        out.append((c.red(), c.green(), c.blue(), c.alpha()))
    return out


_r = _rows(_im_t)
check('E5 上剖条剖面：外 4px 透明 → 2px 纯白 → 1px 过渡 → 9px 纯黑',
      all(_r[i][3] == 0 for i in range(4))
      and all(_r[i] == (255, 255, 255, 255) for i in (4, 5))
      and all(_r[i] == (0, 0, 0, 255) for i in range(7, 16)),
      '剖面=%s' % _r)

_sp = drb.TextboxSprites().load()
check('E6 TextboxSprites 加载零缺失，且预翻转图与源图同尺寸',
      _sp.missing == []
      and _sp.corner(0, True, False).width() == 16
      and _sp.top(True).height() == 16
      and _sp.left(True).width() == 16,
      'missing=%s' % _sp.missing)

# ===========================================================================
# F. 产品接线
# ===========================================================================
check('F1 dialogue_ui.BOX_INSET 直取 dr_textbox.CONTENT_INSET（单一真源）',
      dui.DialogueUI.BOX_INSET is drb.CONTENT_INSET
      or dui.DialogueUI.BOX_INSET == drb.CONTENT_INSET,
      'BOX_INSET=%s CONTENT_INSET=%s'
      % (dui.DialogueUI.BOX_INSET, drb.CONTENT_INSET))

check('F2 圆角样式表框已彻底退役（无 border-radius / 无 #drFrame 选择器）',
      'border-radius' not in DUI_TEXT and '#drFrame' not in DUI_TEXT,
      'border-radius 出现 %d 次，drFrame 出现 %d 次'
      % (DUI_TEXT.count('border-radius'), DUI_TEXT.count('#drFrame')))

check('F3 主容器改由 dr_textbox 绘制（源码直引 DrTextboxFrame）',
      '_drbox.DrTextboxFrame(' in DUI_TEXT and '_drbox.CONTENT_INSET' in DUI_TEXT,
      '引用点=%d' % DUI_TEXT.count('_drbox.'))

class _FakeLoader(object):
    def has_face(self, n):
        return False

    def get_face(self, n):
        return None


class _FakeParent(QWidget):
    """只满足 DialogueUI 构造期需求（set_face 走 sprite_loader）。

    必须是真 QWidget —— `DialogueUI.__init__` 会 `super().__init__(parent)`。
    """

    def __init__(self):
        super().__init__()
        self.sprite_loader = _FakeLoader()


try:
    _p = _FakeParent()
    _dlg = dui.DialogueUI(_p)
    _is_frame = isinstance(_dlg._frame, drb.DrTextboxFrame)
except Exception as e:            # noqa: BLE001
    _is_frame = False
    print('  [诊断] DialogueUI 构造失败：%r' % (e,))
check('F4 DialogueUI 的 _frame 实际就是 DrTextboxFrame 实例（接线真的生效）',
      _is_frame, 'isinstance=%s' % _is_frame)

# 隐藏即停表 / 显示即恢复（等价 flag[8] 门控 + 省掉不可见时的空转）
_tf = drb.DrTextboxFrame()
_tf.set_animation_enabled(True)
_tf.show()
_app.processEvents()
_on = _tf.animation_enabled()
_tf.hide()
_app.processEvents()
_hid = _tf.animation_enabled()
_tf.show()
_app.processEvents()
_shown = _tf.animation_enabled()
_tf.close()
check('F5 框隐藏时角饰定时器停止、显示时恢复',
      _on is True and _hid is False and _shown is True,
      '初始=%s 隐藏后=%s 显示后=%s' % (_on, _hid, _shown))

# 打字音判据正/负控制（等价 scr_textsound）
_yes = [c for c in ('a', 'A', '5', '中', 'あ') if dui._should_play_text_sound(c)]
_no = [c for c in (' ', '&', '^', '!', '.', '?', ',', ':', '/', chr(92), '|',
                   '*', '。', '，', '？', '！', '…') if dui._should_play_text_sound(c)]
check('F6 打字音：字母/数字/汉字发声，空格与 12 个原作标点 + 全角标点全部静音',
      len(_yes) == 5 and not _no and not dui._should_play_text_sound(''),
      '发声=%s ；误发声=%s' % (_yes, _no))

# 判据真被调用（AST：防止"函数写对了但没人用"）
_tree = ast.parse(DUI_TEXT)
_called = []
for node in ast.walk(_tree):
    if isinstance(node, ast.FunctionDef) and node.name == '_type_next_char':
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == '_should_play_text_sound'):
                _called.append(ast.dump(sub.func))
check('F7 _type_next_char 里真调用了 _should_play_text_sound（接线而非死码）',
      bool(_called), '命中 %d 次' % len(_called))

# 光标仍落在黑底可见区内（产品默认尺寸，而不是测试强设的尺寸）
try:
    _dlg.resize(dui.DialogueUI.BASE_WIDTH, dui.DialogueUI.MIN_BOX_HEIGHT)
    _dlg.typing_text = '前台消息'
    _dlg._cursor_visible = True
    _dlg._update_cursor_overlay()
    _dlg._position_cursor_overlay()
    _app.processEvents()
    _g = _dlg._cursor_label.geometry()
    _ins = drb.BLACK_INSET
    _vis = (_ins, _ins, _dlg.width() - _ins, _dlg.height() - _ins)
    _out = [c for c in ((_g.left(), _g.top()), (_g.right(), _g.top()),
                        (_g.left(), _g.bottom()), (_g.right(), _g.bottom()))
            if not (_vis[0] <= c[0] <= _vis[2] and _vis[1] <= c[1] <= _vis[3])]
except Exception as e:            # noqa: BLE001
    _out, _vis, _g = ['<构造异常>'], None, None
    print('  [诊断] 光标定位异常：%r' % (e,))
check('F8 默认尺寸下 ▼ 的 4 角都在黑底可见区内（不被边框带压住）',
      _out == [], '可见区=%s 光标=%s 越界=%s' % (_vis, _g, _out))

# ===========================================================================
# G. 恒真判据自查
# ===========================================================================
_src_self = read(os.path.abspath(__file__))
_suspect = re.findall(r'check\(\s*[\'"][^\'"]*[\'"]\s*,\s*(?:True|1)\s*[,)]',
                      _src_self)
check('G1 本套件内不存在 check(..., True) 形态的恒真判据',
      not _suspect, '可疑=%s' % _suspect)
check('G2 断言总数 ≥ 40（覆盖面没被偷工）', PASS + FAIL >= 40,
      '实际 %d 条' % (PASS + FAIL))

# ---------------------------------------------------------------------------
print('-' * 72)
print('第 44 轮原作对话框复刻验证：%d/%d PASS, %d FAIL'
      % (PASS, PASS + FAIL, FAIL))
if FAILED:
    for n in FAILED:
        print('  FAIL: %s' % n)
    sys.exit(1)
sys.exit(0)

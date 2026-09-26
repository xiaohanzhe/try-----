# -*- coding: utf-8 -*-
"""第52轮 · 对话框「一轮一轮」+ 输入框常驻 · 行为级验证

用户口径逐字（本套件守的就是这两句）：
  「别整这种对话框，就一轮一轮的而不是一次性全放出来，，你现在对话框就像是原作
    把一章节的全部对话都放了进来，而事实上原作一次只放一轮对话，所以你要贴合原作哦，
    还有，预留出来输入框」

守什么
------
A. **单轮显示**（`DialogueUI.SINGLE_TURN_MODE`）
   屏幕上只存在"当前这一轮"；新一轮到来时上一轮整块让位（原作的翻页，不是往下堆）。
   ⚠️ 只改**显示层**：喂给 7B 的上下文缓冲 `_ai_history` **不许被清**——
      否则就成了"为了好看把记忆删了"，那是另一种 bug（H3 专门守这条）。

B. **输入栏常驻**（`DialogueUI.ALWAYS_SHOW_INPUT_BAR`）
   不再"单击才展开"；且窗口高度必须真把输入栏算进去，否则它会被挤没。
   注意 `isVisible()` 在"对话框自身未 show"时对子控件恒为 False，
   所以高度判据必须走**策略**（`_input_bar_reserved()`），不能问 `isVisible()`（H5 守这条）。

为什么每组判据都成对
--------------------
本项目已有 10 次"错在判据侧"的教训（见 memory §4）：
  · 判据**过宽** ⇒ 恒真，看着在守其实没守；
  · 判据**过窄** ⇒ 误报。
所以本套件所有关键判据都**成对**：
  · H1（正） ↔ H2（把开关关掉，历史必须真的开始堆积 = A ≠ B）
  · A2b（真源码，判据须说"受约束"） ↔ A5b（合成的旧写法，同一条判据须说"不受约束"）
  · H4b（跨轮让位） ↔ H4c（阈值调大后不再让位 = 阈值真在起作用）

Qt 拆卸（★ 别乱动）
-------------------
本套件会真建 3 个 `DialogueUI`（各自带一个 `FakeParent` QWidget）共用一个
`QApplication`。若直接 `sys.exit()`，Python 解释器退出期会按不定序回收模块
全局 ⇒ PyQt 先析构 QApplication、后析构子控件 ⇒ **SIGSEGV（退出码 139 /
0xC0000005）**。产物已全部 flush，属于"只在收尾炸"，不是产品缺陷 —— 但它会
把套件退出码污染成崩溃码，让 `run_all.py` 的"退出码"这一路判据失去意义。
⇒ 收尾**显式按序拆**（hide → setParent(None) → deleteLater → processEvents
→ gc），再 `flush + os._exit(code)`。

不联网、不调 Ollama、不实例化主程序；需要 offscreen Qt（会真建 DialogueUI）。
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
for _p in (os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if _p not in sys.path:
        sys.path.append(_p)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

DIALOGUE_PY = os.path.join(PET, 'modules', 'dialogue_ui.py')

RESULTS = []

# 真建起来的控件，收尾时要显式按序拆（见模块 docstring「Qt 拆卸」）
_CREATED_UIS = []


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, detail))
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  <- " + str(detail)) if detail else ""))


# ------------------------------------------------------------------ 源码读取
def _read_src():
    with open(DIALOGUE_PY, 'r', encoding='utf-8') as fh:
        return fh.read()


SRC = _read_src()

# ------------------------------------------------- A0. 语法先过（结构类改动必查）
try:
    TREE = ast.parse(SRC)
    _syntax_ok, _syntax_err = True, ""
except SyntaxError as e:
    TREE = None
    _syntax_ok, _syntax_err = False, "%s (line %s)" % (e.msg, e.lineno)
check("A0 dialogue_ui.py 可编译（ast.parse）", _syntax_ok, _syntax_err)


def _find_func(tree, name):
    if tree is None:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _class_const(tree, name):
    """取 `class DialogueUI` 的类级常量值；取不到返回 `_MISSING`。"""
    if tree is None:
        return _MISSING
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'DialogueUI':
            for st in node.body:
                if isinstance(st, ast.Assign) and len(st.targets) == 1:
                    t = st.targets[0]
                    if isinstance(t, ast.Name) and t.id == name:
                        try:
                            return ast.literal_eval(st.value)
                        except Exception:
                            return _MISSING
    return _MISSING


class _Missing(object):
    def __repr__(self):
        return '<MISSING>'


_MISSING = _Missing()

# ------------------------------- A1. 两个契约常量存在且为 True（恒真判据自查）
_stm = _class_const(TREE, 'SINGLE_TURN_MODE')
_asb = _class_const(TREE, 'ALWAYS_SHOW_INPUT_BAR')
_ph = _class_const(TREE, 'INPUT_PLACEHOLDER')
# 先自证"判据引用的名字真的取到了"——名字打错会让下面所有断言变成恒真
check("A1a 契约常量 SINGLE_TURN_MODE 取得到且为 True",
      _stm is True, "取到 %r" % (_stm,))
check("A1b 契约常量 ALWAYS_SHOW_INPUT_BAR 取得到且为 True",
      _asb is True, "取到 %r" % (_asb,))
check("A1c 输入框占位提示是字符串且非空",
      isinstance(_ph, str) and len(_ph.strip()) > 4, "取到 %r" % (_ph,))
_tg = _class_const(TREE, 'TURN_GAP_SECONDS')
check("A1d 「同一拍」阈值 TURN_GAP_SECONDS 是正数且 <10s",
      isinstance(_tg, float) and 0.0 < _tg < 10.0, "取到 %r" % (_tg,))

# ------------------------------------------- A2. 单轮"让位"逻辑真写在产品代码里
# 判据用 AST，不用字符串子串 —— `'第一句' in 源码` 那种会被我自己的注释/dotstring 误伤
# （第52轮真踩过：断言罐头台词已删，结果匹配到新写的 docstring）。
_add = _find_func(TREE, 'add_dialogue')
_commit = _find_func(TREE, '_commit_previous_ralsei_into_history')


def _is_self_history_target(t):
    return (isinstance(t, ast.Attribute) and t.attr == '_history_html'
            and isinstance(t.value, ast.Name) and t.value.id == 'self')


def _assigns_to_self_history(node):
    """节点子树里有没有写 `self._history_html`（`=` 与 `+=` 都要认）。

    ★ 判据自纠（第52轮）：第一版只认 `ast.Assign`，于是把产品里的
      `self._history_html += (...)`（AugAssign）漏掉 ⇒ A2b 误报。
      这正是 memory §4「判据过窄 = 会误报」的又一例。
    """
    hits = 0
    for n in ast.walk(node):
        if isinstance(n, ast.Assign) and any(_is_self_history_target(t) for t in n.targets):
            hits += 1
        elif isinstance(n, ast.AugAssign) and _is_self_history_target(n.target):
            hits += 1
    return hits


_a2_reset = _assigns_to_self_history(_add) if _add is not None else 0
check("A2a add_dialogue 里存在 `self._history_html = <...>`（新一轮重置）",
      _a2_reset >= 1, "找到 %d 处" % _a2_reset)

# `_maybe_break_turn` 是"跨轮让位"的唯一实现，两条约束都要在源码里看得见
_break = _find_func(TREE, '_maybe_break_turn')
_seq = None
_i_gap = _i_focus = -1
_a2b_guard = False
_a2b_reset = 0
if _break is not None:
    try:
        _bt = ast.unparse(_break)
    except Exception:
        _bt = ''
    _a2b_guard = ('SINGLE_TURN_MODE' in _bt) and ('TURN_GAP_SECONDS' in _bt)
    _a2b_reset = _assigns_to_self_history(_break)
check("A2b `_maybe_break_turn` 同时受 SINGLE_TURN_MODE 与 TURN_GAP_SECONDS 约束且真的清历史",
      _a2b_guard and _a2b_reset >= 1,
      "受约束=%s 清历史=%d 处" % (_a2b_guard, _a2b_reset))

# ★★ 调用顺序：必须在 `_commit_previous_ralsei_into_history()` **之后** ——
#    在它前面清，刚清完那一句又会被 commit 追加回来，等于没清（静默失效）。
_a2c_ok = False
if _add is not None:
    _seq = [getattr(getattr(n, 'func', None), 'attr', None)
            for n in ast.walk(_add) if isinstance(n, ast.Call)]
    if '_commit_previous_ralsei_into_history' in _seq and '_maybe_break_turn' in _seq:
        _a2c_ok = (_seq.index('_commit_previous_ralsei_into_history')
                   < _seq.index('_maybe_break_turn'))
check("A2c add_dialogue 里 `_maybe_break_turn` 排在 commit **之后**（顺序反了就静默失效）",
      _a2c_ok, "调用序=%s" % (_seq if _add is not None else None))

# ★ 间隔必须在 `_note_focus()` 之前取（它会把 _last_activity 刷成现在）
_a2d_ok = False
if _add is not None:
    _src = ast.unparse(_add)
    _i_gap = _src.find('_current_turn_gap')
    _i_focus = _src.find('_note_focus')
    _a2d_ok = (-1 < _i_gap < _i_focus)
check("A2d `_current_turn_gap()` 在 `_note_focus()` 之前调用（否则间隔恒为 0）",
      _a2d_ok, "idx(gap)=%d idx(focus)=%d" % (_i_gap, _i_focus))


# ------------------------------------- A3. 输入栏高度必须走"策略"而不是 isVisible()
_recalc = _find_func(TREE, '_recalc_size_to_content')
_a3_uses_helper = False
_a3_uses_visible = False
if _recalc is not None:
    for n in ast.walk(_recalc):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr == '_input_bar_reserved':
                _a3_uses_helper = True
        # ★ 只认 `self._input_bar.isVisible()`；`self.isVisible()`（窗口自身可见性）
        #   是另一件事，第一版一律当命中 ⇒ A3a 误报。
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'isVisible'
                and isinstance(n.func.value, ast.Attribute)
                and n.func.value.attr == '_input_bar'):
            _a3_uses_visible = True
check("A3a 高度计算改用 `_input_bar_reserved()`（不问 isVisible）",
      _a3_uses_helper and not _a3_uses_visible,
      "helper=%s isVisible=%s" % (_a3_uses_helper, _a3_uses_visible))


# ------------------------------- A4. `_input_bar_reserved` 在常驻模式下恒为 True
class _FakeBar(object):
    def isVisible(self):
        return False

    def sizeHint(self):
        return None


class _FakeSelf(object):
    ALWAYS_SHOW_INPUT_BAR = True
    _input_bar = _FakeBar()


_reserved_fn = None
if TREE is not None:
    for node in ast.walk(TREE):
        if isinstance(node, ast.ClassDef) and node.name == 'DialogueUI':
            for st in node.body:
                if isinstance(st, ast.FunctionDef) and st.name == '_input_bar_reserved':
                    _reserved_fn = st
if _reserved_fn is not None:
    _mod = ast.Module(body=[ast.ClassDef(
        name='Probe', bases=[], keywords=[], decorator_list=[],
        body=[_reserved_fn])], type_ignores=[])
    _ns = {}
    exec(compile(ast.fix_missing_locations(_mod), '<probe>', 'exec'), _ns)
    _probe = _ns['Probe']()
    _probe.ALWAYS_SHOW_INPUT_BAR = True
    _probe._input_bar = _FakeBar()
    _r_on = bool(_probe._input_bar_reserved())
    _probe.ALWAYS_SHOW_INPUT_BAR = False
    _r_off = bool(_probe._input_bar_reserved())   # 子控件 isVisible()=False ⇒ 应为 False
    check("A4 `_input_bar_reserved()` 按策略回答：常驻 True / 折叠 False（含 A≠B）",
          _r_on is True and _r_off is False, "常驻=%s 折叠=%s" % (_r_on, _r_off))
else:
    check("A4 `_input_bar_reserved()` 按策略回答：常驻 True / 折叠 False（含 A≠B）",
          False, "方法没找到")


# ---------------- A5. 判据鉴别力体检：把**旧写法**喂给同一条判据，必须报"没守卫"
def _bare_hide_unguarded(src):
    """返回 `send_message` 里**没有**被 ALWAYS_SHOW_INPUT_BAR 守护的 `_input_bar.hide()` 数量。"""
    try:
        t = ast.parse(src)
    except SyntaxError:
        return -1
    fn = _find_func(t, 'send_message')
    if fn is None:
        return -1
    par = {}
    for n in ast.walk(fn):
        for c in ast.iter_child_nodes(n):
            par[c] = n
    bad = 0
    for n in ast.walk(fn):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'hide'):
            continue
        v = n.func.value
        if not (isinstance(v, ast.Attribute) and v.attr == '_input_bar'):
            continue
        cur, guarded = n, False
        while cur is not None:
            if isinstance(cur, ast.If):
                try:
                    if 'ALWAYS_SHOW_INPUT_BAR' in ast.unparse(cur.test):
                        guarded = True
                        break
                except Exception:
                    pass
            cur = par.get(cur)
        if not guarded:
            bad += 1
    return bad


_OLD_SHAPE = (
    "class X:\n"
    "    def send_message(self):\n"
    "        self.add_dialogue('user', 'x')\n"
    "        self._input_bar.hide()\n"
    "        self._recalc_size_to_content()\n"
)
_bad_new = _bare_hide_unguarded(SRC)
_bad_old = _bare_hide_unguarded(_OLD_SHAPE)
check("A5a 真源码：send_message 里不存在【裸调】_input_bar.hide()",
      _bad_new == 0, "裸调 %d 处" % _bad_new)
check("A5b 判据鉴别力：合成的旧写法必须被同一条判据抓出（A≠B 反向控制）",
      _bad_old == 1, "旧写法裸调 %d 处（期望 1）" % _bad_old)


# ---------------- A6. 双击不再收起输入栏（结构级：常驻分支提前 return，走不到 hide）
_dc = _find_func(TREE, 'mouseDoubleClickEvent')
_a6_ok = False
if _dc is not None and _dc.body:
    first = _dc.body[0]
    if isinstance(first, ast.If):
        try:
            _t = ast.unparse(first.test)
        except Exception:
            _t = ''
        _has_ret = any(isinstance(s, ast.Return) for s in first.body)
        _a6_ok = ('ALWAYS_SHOW_INPUT_BAR' in _t) and _has_ret
check("A6 双击处理：常驻模式下先 return，绝不会走到收起分支",
      _a6_ok, "首语句=%s" % (type(_dc.body[0]).__name__ if _dc else 'None'))


# ============================================================================
#                          行为级（真跑 DialogueUI）
# ============================================================================
class FakeLoader(object):
    def has_face(self, name):
        return False

    def get_face(self, name):
        return None


class FakeEmotion(object):
    def get_current_emotion(self):
        return ("normal", 0)

    def get_face_for_emotion(self, _e, _i):
        return "normal"


def build_ui(cls=None):
    from PyQt5.QtWidgets import QApplication, QWidget
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    class FakeParent(QWidget):
        def __init__(self):
            super().__init__()
            self.sprite_loader = FakeLoader()
            self.emotion_system = FakeEmotion()
            self.sound_manager = None

    if cls is None:
        from dialogue_ui import DialogueUI as cls
    ui = cls(FakeParent())
    ui.show()
    for _ in range(4):
        app.processEvents()
    try:
        ui._auto_hide_timer.stop()   # 别让 20s 自动隐藏在测试中途把框收掉
    except Exception:
        pass
    _CREATED_UIS.append(ui)
    return app, ui


try:
    APP, UI = build_ui()
    _BUILT = True
except Exception as _e:
    import traceback
    APP = UI = None
    _BUILT = False
    print(traceback.format_exc())
    check("B0 DialogueUI 能在 offscreen Qt 下真建起来", False, repr(_e))

ROUND1, ROUND2, ROUND3 = "第一句_甲", "第二句_乙", "第三句_丙"


def _three_rounds(ui):
    """连着聊三轮，每轮 = 用户一句 + Ralsei 回一句。"""
    for u, r in ((ROUND1, "回一"), (ROUND2, "回二"), (ROUND3, "回三")):
        ui.add_dialogue("user", u)
        ui.add_dialogue("ralsei", r)
        ui.stop_typing()
    # 收尾：把最后一条也定格，前台不留半句
    ui.stop_typing()
    for _ in range(3):
        APP.processEvents()


if _BUILT:
    _three_rounds(UI)
    hist = UI._history_html or ''
    _old_in = [w for w in (ROUND1, ROUND2, "回一", "回二") if w in hist]
    check("H1 单轮显示：三轮聊完，屏上只剩最后一句（旧的整块让位）",
          (ROUND3 in hist) and not _old_in,
          "命中旧内容=%r" % (_old_in,))

    # ---- H2 反向控制：把开关关掉，同样三轮 → 历史**必须**开始堆积（A ≠ B）
    APP2, UI2 = build_ui()
    UI2.SINGLE_TURN_MODE = False          # 实例级覆盖，不动产品常量
    _three_rounds(UI2)
    hist2 = UI2._history_html or ''
    _kept2 = [w for w in (ROUND1, ROUND2, ROUND3) if w in hist2]
    check("H2 反向控制：关掉单轮模式后历史确实堆积（证明 H1 有鉴别力，A≠B）",
          len(_kept2) == 3, "旧写法保留 %r" % (_kept2,))
    check("H2b A/B 差异立得住：单轮 %d 条 vs 累积 %d 条"
          % (1, len(_kept2)), (ROUND3 in hist) and len(_kept2) == 3)

    # ---- H3 ★ 上下文不许被顺带清掉（显示层 ≠ 记忆层）
    ctx = UI.get_ai_history(limit=16)
    _ctx_words = {m for _r, m in ctx}
    _need = {ROUND1, ROUND2, ROUND3, "回一", "回二", "回三"}
    _miss = sorted(_need - _ctx_words)
    check("H3 ★显示只留一轮，但喂给 7B 的上下文仍保留全部 6 条（没把记忆删了）",
          not _miss, "缺=%r 实得=%d 条" % (_miss, len(ctx)))

    # ---- H4 ★同一拍里的连续几句**一句都不许丢**（游戏结算+统计+道谢就是这种）
    #
    # ★ 设计自纠（第52轮）：第一版把"上一句一律丢弃"，于是
    #   `结算 → 统计 → 道谢` 三连只剩最后一句 —— **静默丢信息**，
    #   正是本项目最忌讳的那类 bug。改成"只在**跨轮**时让位"。
    import time as _t
    APP3, UI3 = build_ui()
    UI3.add_dialogue("ralsei", "独白甲")
    UI3.stop_typing()
    UI3.add_dialogue("ralsei", "独白乙")
    UI3.stop_typing()
    for _ in range(3):
        APP3.processEvents()
    _h3 = UI3._history_html or ''
    check("H4 ★同一拍的连续两句都在（不丢信息）：甲入历史 + 乙在前台",
          ("独白甲" in _h3) and ("独白乙" in (UI3.typing_text or '')),
          "hist=%r typing=%r" % (_h3[:60], (UI3.typing_text or '')[:20]))

    # ---- H4b 隔了一会儿的独立开口 → 新一轮，旧的整块让位（跨轮才让）
    APP6, UI6 = build_ui()
    UI6.add_dialogue("ralsei", "上一拍甲")
    UI6.stop_typing()
    UI6._last_activity = _t.time() - 9.0          # 注入"隔了 9 秒"（> 阈值 1.5s）
    UI6.add_dialogue("ralsei", "新一拍乙")
    UI6.stop_typing()
    for _ in range(3):
        APP6.processEvents()
    _h6 = UI6._history_html or ''
    check("H4b 跨轮（间隔 > TURN_GAP_SECONDS）→ 上一拍整块让位",
          ("上一拍甲" not in _h6) and ("新一拍乙" in (UI6.typing_text or '')),
          "hist=%r typing=%r" % (_h6[:60], (UI6.typing_text or '')[:20]))

    # ---- H4c 反控制：把阈值调到极大 → 同样的"隔 9 秒"就必须**不再**让位
    APP7, UI7 = build_ui()
    UI7.TURN_GAP_SECONDS = 999.0
    UI7.add_dialogue("ralsei", "上一拍甲")
    UI7.stop_typing()
    UI7._last_activity = _t.time() - 9.0
    UI7.add_dialogue("ralsei", "新一拍乙")
    UI7.stop_typing()
    for _ in range(3):
        APP7.processEvents()
    _h7 = UI7._history_html or ''
    check("H4c 反控制：阈值调大后同一组输入不再让位（证明 H4b 是阈值在起作用）",
          "上一拍甲" in _h7,
          "hist=%r" % (_h7[:60],))

    # ---- H5 ★ 输入栏常驻且高度真被算进去（A/B，两个**独立**控件）
    #
    # ★ 夹具自纠（第52轮）：第一版在**同一个**控件上把 ALWAYS_SHOW_INPUT_BAR 翻成 False
    #   再量高度 —— QLayout 的 SetDefaultConstraint 已把窗口 minimumSize 钉在
    #   "含输入栏"的布局最小高上，而运行时 setattr 不会让布局重新 activate，
    #   于是 resize(更矮) 被 Qt 顶回原值 ⇒ 差 0 ⇒ **报了个假问题**（判据没问题、夹具坏了）。
    #   改成：两个独立控件各按自己的策略构造，并且**记录 `resize` 的请求值**，
    #   直接量"产品算出来的目标高度"而不是"Qt 最终给的几何"。
    _LONG = "这是一段用来把对话正文撑到高度上限的长文本。" * 10

    def _requested_height(ui, app):
        """跑一次 _recalc_size_to_content，返回它**请求**的窗口高度（末次 resize）。"""
        seen = []
        orig = ui.resize

        def _spy(w, h):
            seen.append((w, h))
            return orig(w, h)

        ui.resize = _spy
        try:
            ui._recalc_size_to_content()
        finally:
            ui.resize = orig
        for _ in range(2):
            app.processEvents()
        return (seen[-1][1] if seen else -1), len(seen)

    from dialogue_ui import DialogueUI as _DUI
    _FoldUI = type('FoldUI', (_DUI,), {'ALWAYS_SHOW_INPUT_BAR': False})

    APP4, UI4 = build_ui()
    _reserved = UI4._input_bar_reserved()
    UI4.add_dialogue("ralsei", _LONG)
    UI4.stop_typing()
    for _ in range(3):
        APP4.processEvents()
    h_with, _n_with = _requested_height(UI4, APP4)
    _bar_hint = UI4._input_bar.sizeHint().height()
    _doc_with = UI4.dialogue_content.height()

    APP5, UI5 = build_ui(_FoldUI)
    _reserved_fold = UI5._input_bar_reserved()
    UI5.add_dialogue("ralsei", _LONG)
    UI5.stop_typing()
    for _ in range(3):
        APP5.processEvents()
    h_without, _n_without = _requested_height(UI5, APP5)
    _doc_without = UI5.dialogue_content.height()

    check("H5a 输入栏常驻：常驻实例 `_input_bar_reserved()`=True / 折叠实例=False",
          _reserved is True and _reserved_fold is False,
          "常驻=%s 折叠=%s" % (_reserved, _reserved_fold))
    _delta = h_with - h_without
    check("H5b ★目标高度真的含输入栏：常驻 %dpx − 折叠 %dpx = %d（输入栏 sizeHint=%d）"
          % (h_with, h_without, _delta, _bar_hint),
          _delta >= 40 and (_doc_with == _doc_without),
          "差=%d | 两边的正文高 %d vs %d | resize 次数 %d/%d"
          % (_delta, _doc_with, _doc_without, _n_with, _n_without))

    # ---- H6 双击不会把常驻输入栏收掉（行为级）
    try:
        UI4.mouseDoubleClickEvent(None)   # 常驻分支不碰 event，传 None 安全
        _h6_ok = bool(UI4._input_bar_reserved())
        _h6_err = ""
    except Exception as _e:
        _h6_ok, _h6_err = False, repr(_e)
    check("H6 双击后输入栏仍按常驻占位（不会被收起）", _h6_ok, _h6_err)

    # ---- H7 占位提示真的挂上了
    _ph_live = ''
    try:
        _ph_live = UI4.input_field.placeholderText()
    except Exception as _e:
        _ph_live = "ERR:%r" % (_e,)
    check("H7 输入框占位提示已设置", bool(_ph_live.strip()) and _ph_live == _ph,
          "实得=%r" % (_ph_live,))
else:
    for _n in ("H1", "H2", "H2b", "H3", "H4", "H5a", "H5b", "H6", "H7"):
        check("%s （跳过：UI 没建起来）" % _n, False, "前置失败")

# ------------------------------------------------------------------ summary
_n_pass = sum(1 for ok, _n, _d in RESULTS if ok)
_n_fail = len(RESULTS) - _n_pass
print("-" * 68)
print("合计：PASS=%d FAIL=%d" % (_n_pass, _n_fail))
for ok, _n, _d in RESULTS:
    if not ok:
        print("  FAIL: %s  %s" % (_n, _d))
print("=== 结论 = %s ===" % ("PASS" if _n_fail == 0 else "FAIL"))


def _teardown_qt():
    """显式按序拆掉本套件真建起来的 Qt 对象。

    为什么必须做：见模块 docstring「Qt 拆卸」。顺序 = 先 hide（断掉可见性依赖）
    → 再从父到子 setParent(None)（解除所有权链）→ deleteLater（交给事件循环）
    → 泵几次事件 → gc。缺任何一步都可能让 PyQt 在解释器退出期按错序析构。
    """
    import gc
    for _ui in list(_CREATED_UIS):
        try:
            _ui.hide()
        except Exception:
            pass
    for _ui in list(_CREATED_UIS):
        try:
            _par = _ui.parent()
        except Exception:
            _par = None
        try:
            _ui.setParent(None)
        except Exception:
            pass
        try:
            if _par is not None:
                _par.setParent(None)
                _par.deleteLater()
        except Exception:
            pass
        try:
            _ui.deleteLater()
        except Exception:
            pass
    try:
        for _ in range(3):
            APP.processEvents()
    except Exception:
        pass
    _CREATED_UIS[:] = []
    gc.collect()


sys.stdout.flush()
sys.stderr.flush()
_teardown_qt()
sys.stdout.flush()

# ★ 为什么收尾用 os._exit 而不是 sys.exit：
#   `sys.exit()` 会顺带触发解释器正常收尾（模块全局按不定序回收）。即便上面已经
#   deleteLater，Python 侧仍持有 DialogueUI 的引用，而被回收的一刻 Qt 的
#   C++ 对象可能已经析构 ⇒ 实测仍会 SIGSEGV（退出码 139）。
#   `os._exit()` 直接终止进程、**跳过**解释器收尾，退出码因此确定。
#   这不构成"掩盖真崩溃"：所有断言行与结论行都已 flush 到 stdout；
#   若套件在中途崩溃，根本走不到这一行，崩溃码照样会露出来（run_all.py 判据不变）。
os._exit(0 if _n_fail == 0 else 1)

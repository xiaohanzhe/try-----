# -*- coding: utf-8 -*-
u"""第192轮 · 翻页队列（一框一条 · 按原作翻页）。

## 这一轮要证明的事

用户口径（第190轮续二已定，第192轮执行）：

  `原作不就是一句话一个框吗，按原作`
  `有些没有表情的那就用旁白`

⇒ 读法：**一框一条**。框里只摆**当前这一条**，多条排队；旁白与台词**各占一页**。

## 为什么不是"把 `_history_html` 改成当前页"

那是第一版想法，被三条既有判据直接否掉：

· `check52a` 的 **A2a / A2b** 是**静态 AST** 判据 —— 要求 `add_dialogue` /
  `_maybe_break_turn` 里看得见 `self._history_html = ...`；
· `e2e_narr190` 是**运行期**按 `_history_html` 切片对账的。

⇒ 改成双轨：`_history_html` 仍然是"全部已完成消息的拼接"（**存了什么不变**），
另加 `_pages` + `_page_idx` 决定**画哪一页**。这一轮改的只有一件事：画哪一页。

## 三个"看起来对、其实会坏"的坑（都写成了判据）

1. **历史区不能提前写。** 打字中的那一句虽占一页（要能被翻到），但**不能提前进
   `_history_html`** —— "历史 = 已完成的消息"是第52轮不变式
   （`dialog_turn52` H4b 断言跨轮让位后 `hist == ''`）。
   ⇒ `_hist_synced` 计数 + `_sync_typing_page_into_history()`，**只在 commit 时**补。
   C2 / C4 / C5 / C6 钉这条。
2. **旁白会被前台永久顶掉。** 渲染规则本是"前台独占"，若 Ralsei 分支先
   `_start_typing` 再 push 旁白，旁白就永远看不见。
   ⇒ `_typing_page` + `_typing_own_page()` 三分支，且旁白必须排在
   `_start_typing` **之前**（否则台词页下标更小 ⇒ 视觉上"先说话后做动作"）。
   D2 / D3 / F1~F5 钉这条。
3. **绝不跳页。** 新页到达时把游标设成末页，"同一拍三连"就会跳过中间那句。
   ⇒ `advance_page()` 一次只 `+1`；`_push_page` / `_arm_page_timer` 都**不许**
   碰 `_page_idx`。B1 / B3 / B4 钉这条。

## 触发方式（三处，缺一就"能翻但翻不动"）

· 单击（`mouseReleaseEvent`，优先级在"聚焦输入框"**之前**、`stop_typing` 之后）
· 输入框为空时回车（原来 `send_message` 开头就 `return`，等于 no-op）
· 打字结束后静置 `PAGE_DWELL_MS`

★ **`Z` 键不用** —— 与 R5 附身抢同一个键。A6 钉这条。

## 分段

A 常量与状态 6 · B 绝不跳页 4 · C 双轨制 6 · D 一框一条 5 ·
E 三触发点 5 · F 三分支渲染 5 · G 回归保护 4 · H 自检 3 = **38 条**

不联网、不调 Ollama、不实例化主程序（F 段真建 `DialogueUI`，用 `FakeParent`）；
需要 offscreen Qt。
"""
import ast
import hashlib
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

PET = os.path.join(REPO, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
DU_PY = os.path.join(MODS, 'dialogue_ui.py')

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# ★ F 段真建 DialogueUI ⇒ 模块目录必须进 sys.path（漏了就是
#   `ModuleNotFoundError: No module named 'dialogue_ui'`）
for _p in (os.path.join(PET, 'src'), MODS):
    if _p not in sys.path:
        sys.path.append(_p)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, detail))
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  <- " + str(detail)) if detail else ""))


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


DU_SRC = _read(DU_PY)
DU_TREE = ast.parse(DU_SRC)


# ---------------------------------------------------------------- AST 小工具
def _func(tree, name):
    """模块里名为 name 的函数/方法节点（第一个）。"""
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def _is_self_attr(node, attr=None):
    if not (isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == 'self'):
        return False
    return (attr is None) or (node.attr == attr)


def _self_writes(node):
    """函数体里被**写**的 `self.<attr>` 名集合（Assign / AugAssign / AnnAssign）。"""
    out = set()
    if node is None:
        return out
    for n in ast.walk(node):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if _is_self_attr(t):
                    out.add(t.attr)
                elif isinstance(t, (ast.Tuple, ast.List)):
                    for e in t.elts:
                        if _is_self_attr(e):
                            out.add(e.attr)
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
            if _is_self_attr(n.target):
                out.add(n.target.attr)
    return out


def _self_idx_aug(fn, attr):
    """函数体里对 `self.<attr>` 的 AugAssign 列表 -> [(op, value_node)]。"""
    res = []
    if fn is None:
        return res
    for n in ast.walk(fn):
        if isinstance(n, ast.AugAssign) and _is_self_attr(n.target, attr):
            res.append((n.op, n.value))
    return res


def _self_idx_plain(fn, attr):
    """函数体里对 `self.<attr>` 的普通赋值（Assign/AnnAssign）目标列表。"""
    res = []
    if fn is None:
        return res
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if _is_self_attr(t, attr):
                    res.append(t)
        elif isinstance(n, ast.AnnAssign) and _is_self_attr(n.target, attr):
            res.append(n.target)
    return res


def _calls(node, attr):
    """子树里 `xxx.<attr>(...)` 的调用节点列表。"""
    res = []
    if node is None:
        return res
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == attr:
            res.append(n)
    return res


def _calls_lines(node, attr):
    return [getattr(c, 'lineno', -1) for c in _calls(node, attr)]


def _class_const(tree, cls_name, const_name):
    """取 `class <cls_name>` 的类级常量值；取不到返回 _MISSING。

    ★ 必须取**真实值**而不是判名字在不在 —— 名字打错/值被改成 0 都要红。
    """
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == cls_name:
            for st in n.body:
                tgt = None
                if isinstance(st, ast.Assign) and len(st.targets) == 1:
                    tgt = st.targets[0]
                elif isinstance(st, ast.AnnAssign):
                    tgt = st.target
                if isinstance(tgt, ast.Name) and tgt.id == const_name:
                    try:
                        return ast.literal_eval(st.value)
                    except Exception:  # noqa: BLE001
                        return _MISSING
    return _MISSING


_MISSING = object()


# ============================================================ A 常量与状态
# ★ 第一版写成 `DU_TREE is not None` —— 那是**恒真**（parse 失败脚本早崩了，
#   根本走不到这一行）。改成"类与方法都真的在"，删掉任何一个方法就会红。
_QUEUE_METHODS = ('_push_page', '_sync_typing_page_into_history', '_reset_pages',
                  '_arm_page_timer', '_page_dwell_fire', '_begin_typing_at_page',
                  'advance_page', 'current_page_html', '_typing_own_page')
_have_cls = any(isinstance(n, ast.ClassDef) and n.name == 'DialogueUI'
                for n in ast.walk(DU_TREE))
_miss_meth = [m for m in _QUEUE_METHODS if _func(DU_TREE, m) is None]
check(u'A1 `class DialogueUI` 存在且 9 个翻页方法全部找得到',
      _have_cls and not _miss_meth,
      u'类=%s 缺方法=%r（共 %d 行）' % (_have_cls, _miss_meth, len(DU_SRC.splitlines())))

_dwell = _class_const(DU_TREE, 'DialogueUI', 'PAGE_DWELL_MS')
check(u'A2 `PAGE_DWELL_MS` 是类级常量且 == 2000（约 2 秒静置才翻页）',
      _dwell == 2000,
      u'实得 %r' % (_dwell,))

_init = _func(DU_TREE, '_init_state')
_init_w = _self_writes(_init)
_need_state = {'_pages', '_page_idx', '_typing_page', '_hist_synced'}
_miss_state = sorted(_need_state - _init_w)
check(u'A3 `_init_state` 把四个队列状态都初始化（少一个 ⇒ 首次翻页 AttributeError 被吞）',
      not _miss_state,
      u'缺=%r' % (_miss_state,))

_timer_single = [_calls(_init, 'setSingleShot')]
# ★ 第一版把 `_init_state` 里**所有** setSingleShot 都收进来 ⇒ 实参 `[True, True]`
#   （`_auto_hide_timer` 也是 singleShot），判据与"翻页计时"脱钩、且数量一变就红。
#   必须精确到接收者是 `self._page_timer` 的那一个。
_ss_args = []
for _c in _calls(_init, 'setSingleShot'):
    if not _is_self_attr(getattr(_c.func, 'value', None), '_page_timer'):
        continue
    for _a in _c.args:
        try:
            _ss_args.append(ast.literal_eval(_a))
        except Exception:  # noqa: BLE001
            _ss_args.append(repr(_a))
check(u'A4 `_page_timer` 是 singleShot（连发会一轮翻好几页）',
      _ss_args == [True],
      u'setSingleShot 实参=%r' % (_ss_args,))

_pdt = _func(DU_TREE, '_page_dwell_fire')
_pdt_calls_adv = bool(_calls(_pdt, 'advance_page'))
check(u'A5 `_page_dwell_fire` 的唯一动作就是 `advance_page()`（计时到点不另开逻辑）',
      _pdt is not None and _pdt_calls_adv and len(_calls(_pdt, 'advance_page')) == 1,
      u'调 advance_page %d 次' % len(_calls(_pdt, 'advance_page') or []))

# A6 ★ Z 键：与 R5 附身抢同一个键 ⇒ 对话层一个都不许绑
_z_hits = []
for _n in ast.walk(DU_TREE):
    if isinstance(_n, ast.Attribute) and _n.attr in ('Key_Z',):
        _z_hits.append(getattr(_n, 'lineno', -1))
    elif isinstance(_n, ast.Constant) and isinstance(_n.value, str) and _n.value == 'Z':
        _z_hits.append(getattr(_n, 'lineno', -1))
check(u'A6 对话层不绑 `Z` 键（用户口径：Z 归 R5 附身，翻页用单击/空回车/静置）',
      not _z_hits,
      u'命中行号=%r' % (_z_hits,))


# ============================================================ B 绝不跳页
_adv = _func(DU_TREE, 'advance_page')
_adv_aug = _self_idx_aug(_adv, '_page_idx')
_adv_plain = _self_idx_plain(_adv, '_page_idx')
_aug_ok = (len(_adv_aug) == 1
           and isinstance(_adv_aug[0][0], ast.Add)
           and isinstance(_adv_aug[0][1], ast.Constant)
           and _adv_aug[0][1].value == 1)
check(u'B1 `advance_page` 对 `_page_idx` 只有 `+= 1` 一种写法（绝不跳页）',
      _aug_ok and not _adv_plain,
      u'AugAssign=%r 普通赋值=%d 处' % (
          [(type(o).__name__, getattr(v, 'value', '?')) for o, v in _adv_aug],
          len(_adv_plain)))

_gte = []
for _n in ast.walk(_adv or ast.parse('')) if _adv is not None else []:
    if isinstance(_n, ast.Compare) and _is_self_attr(_n.left, '_page_idx'):
        for _o in _n.ops:
            if isinstance(_o, (ast.GtE, ast.Gt)):
                _gte.append(getattr(_n, 'lineno', -1))
check(u'B2 `advance_page` 有"已到末页就返回 False"的封顶判断（否则越界取值）',
      bool(_gte),
      u'比较节点行号=%r' % (_gte,))

_push = _func(DU_TREE, '_push_page')
_push_w = _self_writes(_push)
# ★ 第一版写 `_is_self_attr(n.func, 'append')` —— 那是**把 receiver 判反了**：
#   `n.func` 是 `self._pages.append` 这个整体，它的 `.value` 是 `self._pages`，
#   而 `_is_self_attr` 要求 `.value` 是 `Name('self')` ⇒ 恒 False（C1 假红）。
#   `self._pages.append(...)` 这种"追加"不是赋值，`_self_writes` 抓不到，必须单独判。
_push_append = [getattr(n, 'lineno', -1) for n in ast.walk(_push)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == 'append'
                and _is_self_attr(n.func.value, '_pages')]
check(u'B3 `_push_page` **不碰** `_page_idx`（新页到达时游标必须原地不动）',
      '_page_idx' not in _push_w,
      u'写了=%r' % (sorted(_push_w),))

_arm = _func(DU_TREE, '_arm_page_timer')
_arm_w = _self_writes(_arm)
check(u'B4 `_arm_page_timer` **不碰** `_page_idx`（它只负责起计时）',
      '_page_idx' not in _arm_w,
      u'写了=%r' % (sorted(_arm_w),))


# ============================================================ C 双轨制
_push_has_pages = bool(_push_append)
check(u'C1 `_push_page` 同时写 `_pages` 与 `_history_html`（双轨同源）',
      '_history_html' in _push_w and _push_has_pages,
      u'写=%r · `_pages.append` 行号=%r' % (sorted(_push_w), _push_append))

_st = _func(DU_TREE, '_start_typing')
_st_w = _self_writes(_st)
check(u'C2 ★★★ `_start_typing` **不写** `_history_html`（写了 H4b 立刻破：历史 = 已完成的消息）',
      '_history_html' not in _st_w,
      u'写了=%r' % (sorted(_st_w),))

_sync = _func(DU_TREE, '_sync_typing_page_into_history')
_sync_w = _self_writes(_sync)
check(u'C3 `_sync_typing_page_into_history` 同时推进 `_history_html` 与 `_hist_synced`',
      '_history_html' in _sync_w and '_hist_synced' in _sync_w,
      u'写了=%r' % (sorted(_sync_w),))

# C4 ★ 调用者必须只有 commit —— 别的地方补同步 = 提前进历史
_sync_callers = []
for _n in ast.walk(DU_TREE):
    if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for _c in _calls(_n, '_sync_typing_page_into_history'):
            _sync_callers.append(_n.name)
check(u'C4 ★★ `_sync_typing_page_into_history` 的调用者**只有** `_commit_previous_ralsei_into_history`',
      _sync_callers == ['_commit_previous_ralsei_into_history'],
      u'调用者=%r' % (_sync_callers,))


# ------------------------------------------------------------ C5/C6 行为级
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


_CREATED = []


def build_ui():
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

    from dialogue_ui import DialogueUI as cls
    ui = cls(FakeParent())
    ui.show()
    for _ in range(4):
        app.processEvents()
    try:
        ui._auto_hide_timer.stop()      # 别让 20s 自动隐藏在测试中途收框
    except Exception:  # noqa: BLE001
        pass
    try:
        ui._page_timer.stop()           # 手动驱动：不让真计时在断言之间偷偷翻页
    except Exception:  # noqa: BLE001
        pass
    _CREATED.append(ui)
    return app, ui


def _quiet(ui):
    """停掉翻页计时。

    ★ 必须成对地用：`add_narration` / `_push_page` / `_start_typing` 都会
      `_arm_page_timer()`（这是产品行为，不能改），而判据之间要的是"游标别自己动"。
      不叫停的话，2 秒静置一到，真计时器就会在两条断言之间**替我翻一页** ——
      D3/D4 那类"读游标"的判据会随机器快慢飘。
    """
    try:
        ui._page_timer.stop()
    except Exception:  # noqa: BLE001
        pass


def _frame_text(ui):
    """前台真正画出来的**纯文本**。

    ★ 第一版读 `ui._frame.text()` —— `_frame` 是 `DrTextboxFrame`（外框），正文
      在 `dialogue_content`（QTextEdit）里，而且走的是 `setHtml` ⇒ 必须用
      `toPlainText()` 才拿到"用户看得见的字"（实测读 `_frame` 恒空 ⇒ F4/F5 假红）。
    """
    w = getattr(ui, 'dialogue_content', None)
    if w is not None:
        try:
            return w.toPlainText() or ''
        except Exception:  # noqa: BLE001
            pass
    for _attr in ('_frame',):
        w = getattr(ui, _attr, None)
        f = getattr(w, 'text', None)
        if callable(f):
            try:
                return f() or ''
            except Exception:  # noqa: BLE001
                pass
    return ''


_BUILT = True
try:
    APP, UI_LEDGER = build_ui()
except Exception as _e:  # noqa: BLE001
    import traceback
    APP = UI_LEDGER = None
    _BUILT = False
    print(traceback.format_exc())
    check(u'C5 打字期间 `_history_html` 里**没有**这一句（历史只收已完成的）', False, repr(_e))
    check(u'C6 commit 之后才补进历史，且 `_hist_synced` 追上', False, repr(_e))

if _BUILT:
    UI_LEDGER.add_dialogue("ralsei", u"甲句_未完成")
    _hist_typing = UI_LEDGER._history_html or ''
    _synced_typing = int(getattr(UI_LEDGER, '_hist_synced', -1))
    check(u'C5 ★★★ 打字期间 `_history_html` 里**没有**这一句（历史只收已完成的）',
          (u"甲句_未完成" not in _hist_typing) and _synced_typing == 0,
          u'hist=%r synced=%d pages=%d'
          % (_hist_typing[:40], _synced_typing, len(UI_LEDGER._pages or [])))

    # 下一条到达 ⇒ 先 commit 上一条（这才是同步时机）
    UI_LEDGER.stop_typing()
    UI_LEDGER.add_dialogue("ralsei", u"乙句_进行中")
    _hist_after = UI_LEDGER._history_html or ''
    check(u'C6 ★★ commit 之后才补进历史，且 `_hist_synced` 追上',
          (u"甲句_未完成" in _hist_after)
          and (u"乙句_进行中" not in _hist_after)
          and int(getattr(UI_LEDGER, '_hist_synced', 0)) >= 1,
          u'hist=%r synced=%d' % (_hist_after[:60],
                                  int(getattr(UI_LEDGER, '_hist_synced', -1))))


# ============================================================ D 一框一条
if _BUILT:
    APP_D, UID = build_ui()
    UID.add_narration(u"旁白甲")
    UID.add_narration(u"旁白乙")
    _quiet(UID)
    _pages_d = list(UID._pages or [])
    check(u'D1 两条旁白 ⇒ **两页**（不是拼成一页）',
          len(_pages_d) == 2 and (u"旁白甲" in _pages_d[0])
          and (u"旁白乙" in _pages_d[1]),
          u'页数=%d' % len(_pages_d))

    UID._start_typing(u"台词丙")
    _quiet(UID)
    _pages_d2 = list(UID._pages or [])
    check(u'D2 旁白 + 台词 ⇒ 台词是**最后一页**（自己是独立一页，不并入旁白页）',
          len(_pages_d2) == 3 and (u"台词丙" in _pages_d2[-1])
          and (u"旁白乙" in _pages_d2[1]),
          u'页数=%d 末页含台词=%s'
          % (len(_pages_d2), (u"台词丙" in _pages_d2[-1]) if _pages_d2 else 'n/a'))
    check(u'D3 ★★ 旁白页下标 < 台词页下标（动作先于说话）',
          int(UID._typing_page) == 2 and int(UID._page_idx) == 0,
          u'typing_page=%d page_idx=%d'
          % (int(UID._typing_page), int(UID._page_idx)))

    # ★ 变异 M13/M14 抓出来的：这两条**不能直接拿 `_pages[下标]` 比**。
    #   判据要能在"产品把钳制去掉"时打出 [FAIL]，而不是自己先 IndexError 崩掉
    #   （崩了 = 一条 [FAIL] 都打不出来 = 什么都没证明，第178轮 M3 同款病）。
    _pg_d = list(UID._pages or [])
    UID._page_idx = 1
    _d4 = UID.current_page_html() if len(_pg_d) > 1 else None
    check(u'D4 `current_page_html()` 是"画哪一页"的**唯一出口**（返回 `_pages[游标]`）',
          len(_pg_d) > 1 and _d4 == _pg_d[1],
          u'页数=%d 命中=%s' % (len(_pg_d), _d4 == (_pg_d[1] if len(_pg_d) > 1 else None)))

    UID._page_idx = 99
    try:
        _d5 = UID.current_page_html()
    except Exception as _e5:  # noqa: BLE001
        _d5 = None
        _d5_err = repr(_e5)
    else:
        _d5_err = u''
    check(u'D5 游标越界钳到末页（`_page_idx` 被外部写坏也不崩、不空屏）',
          bool(_pg_d) and _d5 == _pg_d[-1],
          u'钳后==末页:%s %s' % (_d5 == (_pg_d[-1] if _pg_d else None), _d5_err))
else:
    for _n in (u'D1 两条旁白 ⇒ **两页**（不是拼成一页）',
               u'D2 旁白 + 台词 ⇒ 台词是**最后一页**（自己是独立一页，不并入旁白页）',
               u'D3 ★★ 旁白页下标 < 台词页下标（动作先于说话）',
               u'D4 `current_page_html()` 是"画哪一页"的**唯一出口**（返回 `_pages[游标]`）',
               u'D5 游标越界钳到末页（`_page_idx` 被外部写坏也不崩、不空屏）'):
        check(_n, False, u'DialogueUI 没建起来')


# ============================================================ E 三触发点
_mrel = _func(DU_TREE, 'mouseReleaseEvent')
_mrel_adv = _calls_lines(_mrel, 'advance_page')
_mrel_stop = _calls_lines(_mrel, 'stop_typing')
check(u'E1 单击 = 翻页：`mouseReleaseEvent` 里真的调 `advance_page()`',
      len(_mrel_adv) == 1,
      u'调用行号=%r' % (_mrel_adv,))

check(u'E2 ★ 单击优先级：`stop_typing()` 排在 `advance_page()` **之前**（打字中先跳过，不抢翻页）',
      bool(_mrel_stop) and bool(_mrel_adv) and min(_mrel_stop) < min(_mrel_adv),
      u'stop=%r advance=%r' % (_mrel_stop, _mrel_adv))

_ef = _func(DU_TREE, 'eventFilter')
_ef_adv = _calls_lines(_ef, 'advance_page')
_ef_stop = _calls_lines(_ef, 'stop_typing')
_ef_empty = []
for _n in ast.walk(_ef or ast.parse('')):
    if isinstance(_n, ast.Call) and _is_self_attr(_n.func, '_should_send_on_enter'):
        _ef_empty.append(getattr(_n, 'lineno', -1))
check(u'E3 输入框**为空**时回车 = 翻页（原来 `send_message` 开头就 return，是 no-op）',
      len(_ef_adv) == 1 and bool(_ef_empty),
      u'advance=%r 回车闸=%r' % (_ef_adv, _ef_empty))
check(u'E4 空回车同样先判打字再翻页（与单击同一口径，不出现两套行为）',
      bool(_ef_stop) and bool(_ef_adv) and min(_ef_stop) < min(_ef_adv),
      u'stop=%r advance=%r' % (_ef_stop, _ef_adv))

_hide = _func(DU_TREE, 'hide_dialogue')
# ★ 第一版判 `_calls(_hide, 'stop')` —— 那是**过宽**：`hide_dialogue` 里本来就有
#   `_auto_hide_timer.stop()`，把 `_page_timer.stop()` 整个删掉照样绿。
#   必须精确到"接收者是 `self._page_timer`、方法是 stop"。
_hide_timer_stop = [getattr(c, 'lineno', -1) for c in _calls(_hide, 'stop')
                    if _is_self_attr(getattr(c.func, 'value', None), '_page_timer')]
check(u'E5 `hide_dialogue` 停的是**翻页**计时（`self._page_timer.stop()`，不是顺手停别的计时器）',
      bool(_hide_timer_stop),
      u'命中行号=%r' % (_hide_timer_stop,))


# ============================================================ F 三分支渲染
_top = _func(DU_TREE, '_typing_own_page')
# ★ 第一版要求"存在 left 是 `self._page_idx` 的 Compare" —— 那是**过窄**：
#   产品写的是 `int(self._page_idx) < int(self._typing_page)`，left 是 `int(...)`
#   这个 Call，`_is_self_attr` 直接 False ⇒ 假红。改成"比较节点子树里同时出现
#   两个 self 属性"，既不看外层表达式怎么写，也仍然钉住"比的是这两个量"。
_top_cmp = []
for _n in ast.walk(_top or ast.parse('')):
    if not isinstance(_n, ast.Compare):
        continue
    _attrs = {m.attr for m in ast.walk(_n) if _is_self_attr(m)}
    if '_page_idx' in _attrs and '_typing_page' in _attrs:
        _top_cmp.append(getattr(_n, 'lineno', -1))
_top_src_ok = bool(_top_cmp) and any(
    isinstance(n, ast.If) for n in ast.walk(_top or ast.parse('')))
check(u'F1 `_typing_own_page()` 判的是"游标是否还没走到打字页"（不是别的东西）',
      _top_src_ok, u'比较节点行号=%r' % (_top_cmp,))

if _BUILT:
    APP_F, UIF = build_ui()
    check(u'F2 后台没占页 ⇒ 三分支走"老路径"（`_typing_page < 0`，与第192轮之前完全一致）',
          UIF._typing_own_page() is False and UIF._typing_page == -1,
          u'typing_page=%d' % int(UIF._typing_page))

    UIF.add_narration(u"旁白甲")
    UIF._start_typing(u"台词乙")
    _quiet(UIF)
    check(u'F3 占了页但还没轮到 ⇒ True（前台先不画，让旁白看得见）',
          UIF._typing_own_page() is True,
          u'typing_page=%d idx=%d'
          % (int(UIF._typing_page), int(UIF._page_idx)))

    _txt_pre = _frame_text(UIF)
    check(u'F4 ★★★ 旁白不会被前台顶掉：翻到旁白页时框里看得见旁白、看不见台词',
          (u"旁白甲" in _txt_pre) and (u"台词乙" not in _txt_pre),
          u'框内=%r' % (_txt_pre[:80],))

    UIF.advance_page()
    _was_typing = bool(UIF.is_typing)
    UIF.stop_typing()
    _txt_post = _frame_text(UIF)
    check(u'F5 ★★ 翻到台词页 ⇒ 一框一条：只剩台词，旁白不再同时出现',
          (u"台词乙" in _txt_post) and (u"旁白甲" not in _txt_post),
          u'打字已开=%s 框内=%r' % (_was_typing, _txt_post[:80]))
else:
    for _n in (u'F2 后台没占页 ⇒ 三分支走"老路径"（`_typing_page < 0`，与第192轮之前完全一致）',
               u'F3 占了页但还没轮到 ⇒ True（前台先不画，让旁白看得见）',
               u'F4 ★★★ 旁白不会被前台顶掉：翻到旁白页时框里看得见旁白、看不见台词',
               u'F5 ★★ 翻到台词页 ⇒ 一框一条：只剩台词，旁白不再同时出现'):
        check(_n, False, u'DialogueUI 没建起来')


# ============================================================ G 回归保护
_reset = _func(DU_TREE, '_reset_pages')
_reset_w = _self_writes(_reset)
check(u'G1 `_reset_pages` **不动** `_history_html`（那句留在调用点，A2a/A2b 盯着它）',
      '_history_html' not in _reset_w,
      u'写了=%r' % (sorted(_reset_w),))

check(u'G2 `_reset_pages` 清 `_page_idx` / `_typing_page` / `_hist_synced`（游标不清会指到旧页）',
      {'_page_idx', '_typing_page', '_hist_synced'} <= _reset_w,
      u'缺=%r' % (sorted({'_page_idx', '_typing_page', '_hist_synced'} - _reset_w),))

_reset_callers = []
for _n in ast.walk(DU_TREE):
    if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for _c in _calls(_n, '_reset_pages'):
            _reset_callers.append(_n.name)
check(u'G3 四个"清历史"的跟随点都跟着清了页游标（少一处 = 框清了但游标还指着旧页）',
      len(_reset_callers) >= 4,
      u'调用点 %d 个：%r' % (len(_reset_callers), sorted(set(_reset_callers))))

_adv_begin = _calls_lines(_adv, '_begin_typing_at_page')
check(u'G4 `advance_page` 走到打字页时**才**开打（`_begin_typing_at_page`）',
      len(_adv_begin) == 1,
      u'调用行号=%r' % (_adv_begin,))


# ============================================================ H 自检
_names = [n for _ok, n, _d in RESULTS]
check(u'H1 判据名无重复（防复制粘贴漏改名 ⇒ 两条判据挤在一个名字下）',
      len(_names) == len(set(_names)),
      u'共 %d 条 / 去重后 %d 条' % (len(_names), len(set(_names))))

# ★ 第一版写成 `('E:' not in DU_SRC[:0])` —— 切片是空串 ⇒ **恒真**，等于没写
#   （记忆里"恒真判据比不写还危险"）。改成真的扫本文件自己的 import。
_self_tree = ast.parse(_read(os.path.abspath(__file__)))
_NET_MODS = ('socket', 'requests', 'urllib', 'http', 'ftplib')
_bad_imp = []
for _n in ast.walk(_self_tree):
    if isinstance(_n, ast.Import):
        for _al in _n.names:
            if _al.name.split('.')[0] in _NET_MODS:
                _bad_imp.append(_al.name)
    elif isinstance(_n, ast.ImportFrom) and _n.module:
        if _n.module.split('.')[0] in _NET_MODS:
            _bad_imp.append(_n.module)
check(u'H2 零网络 / 零外部盘：本套件不 import 任何网络模块',
      not _bad_imp,
      u'命中=%r' % (_bad_imp,))

_sha = hashlib.sha1(DU_SRC.encode('utf-8')).hexdigest()
check(u'H3 记下被测源码 sha1（换轮次后可比对"到底改没改"）',
      len(_sha) == 40,
      u'dialogue_ui.py sha1=%s' % _sha[:16])

# ---------------------------------------------------------------- 汇总
_FAIL = [r for r in RESULTS if not r[0]]
print(u'')
print(u'合计：PASS=%d FAIL=%d  共 %d 条' % (len(RESULTS) - len(_FAIL), len(_FAIL),
                                          len(RESULTS)))
if _FAIL:
    print(u'【失败明细】')
    for _ok, _n, _d in _FAIL:
        print(u'  - %s  <- %s' % (_n, _d))

# 清场：Qt 对象按不定序析构会 SIGSEGV，先显式收掉
for _u in _CREATED:
    try:
        _u.hide()
        _u.deleteLater()
    except Exception:  # noqa: BLE001
        pass
if APP is not None:
    for _ in range(3):
        APP.processEvents()

sys.exit(0 if not _FAIL else 1)

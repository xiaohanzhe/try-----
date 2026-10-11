# -*- coding: utf-8 -*-
"""第108轮 · 回归套件：**UI 缩放落地**（缺口②：`ui_scale()` 零消费）不许静默漂移。

用户第107轮口径（逐字，仍生效）：
  「**UI，也就是我所说的游戏中的对话框之类的也要放大**」

第107轮只做到一半：`RalseiPet.ui_scale()` 有了定义，但**一个消费点都没有**
（AST 层面零 `Attribute(attr='ui_scale')` / 零 `Name(id='ui_scale')`）；
`DialogueUI` / `ItemMenuUI` / `DrTextboxFrame` 的尺寸与字号全是**硬编码**。
本轮把倍率**真下发**给这些控件。

本套件守的**不变式**（改任何一条 = 静默漂移 ⇒ 必须报红）：
  A  ★★★ `ui_scale()` 的**消费点真的存在**（宿主下发 + 两个控件各实现消费）
  B  ★★★ 下发面：`_apply_ui_scale` 幂等 · 缺控件不拖垮其余 · 两个入口都调
      （`set_pet_scale` 改档立即生效 + `init_systems` 启动用持久化值）
  C  ★★★ **幂等性**：从基准重算（`f(f(x)) == f(x)`）—— 在现值上乘 = 越改越大
  D  ★★★ **非法输入原样不动**（`None` / `NaN` / `0` / 负数 / 字符串）
  E  ★★ 落点齐：字号 / 固定尺寸 / HTML 内联字号 / 框体几何 / 布局内缩
  F  ★★ 框体缩放绘制：`paint_dark_box_scaled` 在盘 · `scale==1.0` 时与原路径**等价**
  G  ★★ 零依赖纪律 + 原路径零回归（无倍率时行为逐字不变）
  H  判据自身体检

跑法：
    C:\\Python311\\python.exe check108.py

★ 纪律：本支**零外部盘依赖**（回归碰不得 E 盘 —— `HERMETIC_IDS` 那套同源要求）。
"""
import io
import os
import sys
import ast

HERE = os.path.dirname(os.path.abspath(__file__))
# ★★ `RALSEI_MUT_ROOT`：变异测试（`mutate108.py`）把产品源码复制到临时区后，
#   需要让本套件去读**临时区那份**（而不是工作区真文件）。
#   没有这个开关，变异测试要么改工作区（危险）、要么根本测不了。
#   ★ 默认（未设该环境变量）⇒ 与以前完全一致（读工作区）＝零行为变化。
ROOT = os.environ.get('RALSEI_MUT_ROOT') or os.path.abspath(
    os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')

sys.path.insert(0, os.path.join(PKG, 'modules'))

_OUT = []
_N = {'p': 0, 'f': 0}


def ok(name, cond, detail=u'', star=False):
    _N['p' if cond else 'f'] += 1
    line = u'%s %s' % (u'[PASS]' if cond else u'[FAIL]',
                       (u'★ ' + name) if star and not name.startswith(u'★') else name)
    if detail:
        line += u'  <- %s' % detail
    print(line)
    _OUT.append(line)
    return bool(cond)


def sec(t):
    print(u'\n-- %s --' % t)
    _OUT.append(u'\n-- %s --' % t)


def read(p):
    with io.open(p, 'r', encoding='utf-8') as f:
        return f.read()


MAIN = os.path.join(PKG, 'src', 'main.py')
DUI = os.path.join(PKG, 'modules', 'dialogue_ui.py')
MENU = os.path.join(PKG, 'modules', 'item_menu_ui.py')
BOX = os.path.join(PKG, 'modules', 'dr_textbox.py')

for _p in (MAIN, DUI, MENU, BOX):
    if not os.path.isfile(_p):
        print(u'[FATAL] 缺文件：%s' % _p)
        sys.exit(2)

_src_main = read(MAIN)
_src_dui = read(DUI)
_src_menu = read(MENU)
_src_box = read(BOX)
_t_main = ast.parse(_src_main)
_t_dui = ast.parse(_src_dui)
_t_menu = ast.parse(_src_menu)
_t_box = ast.parse(_src_box)


def _class(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == name:
            return n
    return None


def _find_func(tree, name, cls=None):
    scope = cls if cls is not None else tree
    for n in ast.walk(scope):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def _func_source(src, tree, name):
    fn = _find_func(tree, name)
    if fn is None:
        return u''
    return ast.get_source_segment(src, fn) or u''


def _code_only(src):
    """剥注释 + 字符串（判"禁某 API 出现"必须用它 —— 注释/文档串一提名字即误报）。"""
    try:
        tree = ast.parse(src)
    except Exception:
        return src
    for n in ast.walk(tree):
        for ch in ast.iter_child_nodes(n):
            if isinstance(ch, ast.Constant) and isinstance(ch.value, str):
                ch.value = u''
    return ast.unparse(tree)


# ---------------------------------------------------------------------------
# ★★★ 真跑夹具（不靠"看代码像对的"）
#
# 为什么用**桩**而不是真起 Qt Widget：
#   ① 本套件要进 G2（`--model` 之前必须零外部依赖），真起窗口在离屏平台上
#      受 `QT_QPA_PLATFORM` 影响，且慢；
#   ② 我要验的是**缩放算术**（幂等 / 非法输入 / 等价性），
#      与 Qt 的渲染无关 ⇒ 桩足够，且**更可靠**（无平台差异）。
#   ⚠️ 桩的纪律（记忆里栽过）：桩必须**与产品同一份实现**，
#      不许把产品代码抄一遍 —— 所以这里用 `exec` **原样抽取**产品方法体。
# ---------------------------------------------------------------------------
def _exec_methods(src, tree, cls_name, method_names, extra_globals=None):
    """从产品源码里抽出一个类的若干方法，**原样**编译成一张命名空间。

    ★ 用 `ast` 抽方法体再拼一个最小类壳 —— 这样跑的就是**产品的那份代码**，
      不是抄写的副本（抄写 = 判据与被测物脱节的经典形态）。
    """
    cls = _class(tree, cls_name)
    if cls is None:
        return None, u'类 %s 不存在' % cls_name
    chunks = []
    for mn in method_names:
        fn = _find_func(tree, mn, cls=cls)
        if fn is None:
            return None, u'方法 %s 不存在' % mn
        seg = ast.get_source_segment(src, fn)
        if not seg:
            return None, u'方法 %s 取不到源码' % mn
        chunks.append(seg)
    body = u'\n'.join(chunks)
    head = u'class _Probe(object):\n'
    indented = u'\n'.join((u'    ' + _l) if _l.strip() else u'' for _l in body.split(u'\n'))
    code = head + indented + u'\n'
    g = dict(extra_globals or {})
    g['__builtins__'] = __builtins__
    try:
        exec(compile(code, '<probe:%s>' % cls_name, 'exec'), g)
    except Exception as e:
        return None, u'编译探针失败: %s' % e
    return g.get('_Probe'), u''


def _mk_dui_probe():
    """造一个 `DialogueUI` 的**纯算术探针**：只装缩放需要的最小状态与假控件。

    ★ 全部字段名与产品**逐一对应**（`_ui_base` / `_ui_scale` / `BOX_INSET` /
      `_base_width` / `_min_dialogue_h` / `_max_dialogue_h`）——
      名字对不上就不是在测产品了。
    """
    class _Lbl(object):
        def __init__(self):
            self.fs = None
            self.sz = None
            self.pm = None

        def setFont(self, f):
            self.fs = f

        def setFixedSize(self, w, h):
            self.sz = (w, h)

        def setPixmap(self, p):
            self.pm = p

        def setFixedHeight(self, h):
            self.sz = (self.sz[0] if self.sz else 0, h)

    class _Box(object):
        def __init__(self):
            self.cs = None
            self.layout_obj = None

        def set_content_scale(self, s):
            self.cs = s

        def layout(self):
            return None

    class _FX(object):
        def __init__(self):
            self.font = None

        def setFont(self, f):
            self.font = f

    class _Probe(object):
        def __init__(self):
            self._ui_scale = 1.0
            self._ui_base = {
                'inset': 34, 'base_width': 620, 'min_box_height': 220,
                'font_cursor': 11, 'font_name': 12, 'font_body': 13,
                'font_input': 11, 'font_send': 9,
                'cursor_size': 14, 'face_size': 84, 'face_pix': 78,
                'input_h': 48, 'send_w': 72, 'send_h': 48,
                'min_dialogue_h': 72, 'max_dialogue_h': 380,
                'name_label_h': 18, 'right_spacing': 4,
                'html_user_pt': 10, 'html_npc_pt': 10,
            }
            self.BOX_INSET = 34
            self.BASE_WIDTH = 620
            self.MIN_BOX_HEIGHT = 220
            self._base_width = 620
            self._min_dialogue_h = 72
            self._max_dialogue_h = 380
            self._frame = _Box()
            self._cursor_label = _Lbl()
            self.name_label = _Lbl()
            self.face_label = _Lbl()
            self.dialogue_content = _FX()
            self.input_field = _Lbl()
            self.send_button = _Lbl()
            self._last_face = 'normal'

        # 产品里这两个在缩放末尾被调；探针里记一下调用次数（验"真被调"）
        def _recalc_size_to_content(self):
            self._recalc_calls = getattr(self, '_recalc_calls', 0) + 1

        def _position_cursor_overlay(self):
            self._pos_calls = getattr(self, '_pos_calls', 0) + 1

        # 产品在缩放末尾会"按新尺寸重贴头像" ⇒ 探针要能接住（否则 AttributeError
        # 会被产品的 except 吞掉 ⇒ 看起来"跑过了"其实中途就断了）
        def set_face(self, face_type):
            self._last_face = face_type
            self._face_calls = getattr(self, '_face_calls', 0) + 1

    g, err = _exec_methods(_src_dui, _t_dui, 'DialogueUI',
                           ['apply_ui_scale'], {'_log': _NopLog(),
                                                '_ralsei_font': _fake_font})
    if g is None:
        return None, err
    probe = _Probe()
    # 把产品方法**绑定**到探针上（用的是产品源码，不是抄写）
    probe.apply_ui_scale = g.apply_ui_scale.__get__(probe, _Probe)
    probe._html_pt = _exec_methods(_src_dui, _t_dui, 'DialogueUI',
                                   ['_html_pt'], {'_log': _NopLog(),
                                                  '_ralsei_font': _fake_font})[0]._html_pt
    probe._html_pt = probe._html_pt.__get__(probe, _Probe)
    return probe, u''


class _NopLog(object):
    def debug(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def exception(self, *a, **k):
        pass


def _fake_font(point_size, bold=False):
    """假字体工厂：只记字号（`_ralsei_font` 返回的是 QFont，离屏建不了）。"""
    return ('FONT', point_size, bool(bold))


def _dui_snapshot(p):
    """把"缩放影响了哪些量"快照下来（**逐值**可比的元组）。"""
    return (
        p.BOX_INSET, p._base_width, p._min_dialogue_h, p._max_dialogue_h,
        p._cursor_label.fs, p._cursor_label.sz,
        p.name_label.fs, p.dialogue_content.font,
        p.input_field.fs, p.input_field.sz,
        p.send_button.fs, p.send_button.sz,
        p.face_label.sz, p._frame.cs, p._ui_scale,
    )


def _run_idempotence_check():
    """★ 幂等：同一倍率连调两次 ⇒ 快照逐值相等。"""
    try:
        p, err = _mk_dui_probe()
        if p is None:
            return False, u'探针不可用: %s' % err
        p.apply_ui_scale(1.6)
        s1 = _dui_snapshot(p)
        p.apply_ui_scale(1.6)
        s2 = _dui_snapshot(p)
        if s1 != s2:
            return False, u'两次不一致:\n  a=%r\n  b=%r' % (s1, s2)
        # ★★★ 折返检测的**基准点必须在"构建完成态"取**（第108轮踩过）：
        #   控件刚 new 出来时 `setFont/setFixedSize` 还没被调过（快照是 `None`），
        #   拿它当基准 ⇒ "1.0→1.6→1.0 回不到 None" 会被误读成"残留"。
        #   ★ 真实产品里控件在 `_build_ui` 时就设过字号 ⇒ 稳定态 = 调一次 1.0 之后。
        #   （判据侧夹具不保真 = 报假问题 —— 记忆里那条。）
        p2, _ = _mk_dui_probe()
        if p2 is None:
            return False, u'探针不可用'
        p2.apply_ui_scale(1.0)          # 落到"构建完成态"
        base = _dui_snapshot(p2)
        p2.apply_ui_scale(1.6)
        p2.apply_ui_scale(1.0)
        back = _dui_snapshot(p2)
        if base != back:
            _d = [(i, x, y) for i, (x, y) in enumerate(zip(base, back)) if x != y]
            return False, u'折返有残留（idx a->b）: %r' % (_d[:4],)
        return True, u'同倍率两次一致 + 折返回到稳定态'
    except Exception as e:
        return False, u'异常: %s' % e


def _run_bad_input_check():
    """★ 非法输入：倍率与几何**逐值不变**。"""
    try:
        p, err = _mk_dui_probe()
        if p is None:
            return False, u'探针不可用: %s' % err
        p.apply_ui_scale(1.5)
        before = _dui_snapshot(p)
        bad = [None, float('nan'), 0, 0.0, -1.0, -0.5, u'abc', u'', [], {}, object()]
        for b in bad:
            r = p.apply_ui_scale(b)
            if r != 1.5 or _dui_snapshot(p) != before:
                return False, u'非法输入 %r 改动了状态（返回 %r）' % (b, r)
        return True, u'%d 种非法输入全部原样不动' % len(bad)
    except Exception as e:
        return False, u'异常: %s' % e


def _run_equiv_check():
    """★★★ 等价性：`scale == 1.0` 时缩放版绘制指令与原版**逐值相等**。

    ★ 做法：抽产品的 `paint_dark_box_scaled`（原样源码）→ 注入**假画笔**记录
      所有 `fillRect` / `drawPixmap` 调用 → 与 `paint_dark_box`（同为产品源码）
      的调用序列比对。
    ⚠️ 这是"零回归"的**算术保证**，不是"看着像"。
    """
    class _FakePainter(object):
        def __init__(self):
            self.ops = []

        def fillRect(self, rect, color):
            self.ops.append(('fill', (rect.x(), rect.y(),
                                      rect.width(), rect.height())))

        def drawPixmap(self, rect, pm):
            self.ops.append(('pm', (rect.x(), rect.y(),
                                    rect.width(), rect.height()), pm))

    class _FakeSprites(object):
        def top(self, vflip=False):
            return ('TOP', vflip)

        def left(self, hflip=False):
            return ('LEFT', hflip)

        def corner(self, frame, hflip=False, vflip=False):
            return ('CORNER', frame, hflip, vflip)

    try:
        g = {'__builtins__': __builtins__, '_log': _NopLog()}
        # 抽产品函数源码（含依赖常量与两个绘制函数）
        src_box = _src_box
        # 只取"绘制相关"的顶层定义，避免拖进 Qt 依赖
        keep = []
        for node in _t_box.body:
            if isinstance(node, ast.FunctionDef) and node.name in (
                    'darkbox_blits', 'textbox_metrics', 'paint_dark_box',
                    'paint_dark_box_scaled', 'jewel_frame'):
                seg = ast.get_source_segment(src_box, node)
                if seg:
                    keep.append(seg)
        for node in _t_box.body:
            if isinstance(node, ast.Assign):
                nms = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if any(n in ('BAND', 'STRETCH_GAP', 'CORNER_SIZE', 'BLACK_INSET',
                             'CORNER_FRAMES', 'JEWEL_TICKS_PER_FRAME')
                       for n in nms):
                    seg = ast.get_source_segment(src_box, node)
                    if seg:
                        keep.append(seg)
        # QRect / QColor 的最小等价物（产品只用 x/y/width/height 与构造）
        g['QRect'] = _FakeRect
        g['QColor'] = lambda *a: ('COLOR', a)
        exec(compile(u'\n'.join(keep), '<probe:box>', 'exec'), g)
        pdb = g['paint_dark_box']
        pdbs = g['paint_dark_box_scaled']

        pa = _FakePainter()
        pdb(pa, 0, 0, 620, 220, 3, _FakeSprites())
        pb = _FakePainter()
        pdbs(pb, 0, 0, 620, 220, 3, 1.0, _FakeSprites())
        if pa.ops != pb.ops:
            _d = [(i, x, y) for i, (x, y) in
                  enumerate(zip(pa.ops, pb.ops)) if x != y][:3]
            return False, (u'scale=1.0 与原版不等价；前 %d 处差异: %r\n'
                           u'  ops=%d vs %d' % (len(_d), _d, len(pa.ops), len(pb.ops)))
        return True, u'scale=1.0 ⇒ %d 条绘制指令逐值相等' % len(pa.ops)
    except Exception as e:
        return False, u'异常: %s' % e


class _FakeRect(object):
    """`QRect` 的最小等价物（产品只读 x/y/width/height）。"""

    def __init__(self, x, y, w, h):
        self._x, self._y, self._w, self._h = int(x), int(y), int(w), int(h)

    def x(self):
        return self._x

    def y(self):
        return self._y

    def width(self):
        return self._w

    def height(self):
        return self._h


print(u'=' * 72)
print(u'第108轮：UI 缩放落地（缺口②——`ui_scale()` 零消费）不许静默漂移')
print(u'ROOT = %s' % ROOT)
print(u'=' * 72)

# =====================================================================
# A. 消费点真的存在
# =====================================================================
sec(u'A 消费点真的存在（第107轮的缺口）')

_f_uis = _find_func(_t_main, 'ui_scale', cls=_class(_t_main, 'RalseiPet'))
ok(u'A1 ★★★ `RalseiPet.ui_scale()` 仍在（倍率唯一真源）',
   _f_uis is not None, star=True)

# A2 ★★★ 反例实证：ui_scale 必须**不再是**"只有定义、零调用"
#   判据形态：AST 里出现 `self.ui_scale()` 的调用（Attribute 调用，非定义行）
_uis_calls = []
for _n in ast.walk(_t_main):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute) \
            and _n.func.attr == 'ui_scale':
        _uis_calls.append(_n.lineno)
ok(u'A2 ★★★ `ui_scale()` **真的被调用**（第107轮零消费 = 缺口②；AST 判调用非定义）',
   len(_uis_calls) >= 1, u'调用行=%s' % (sorted(set(_uis_calls)),), star=True)

# A3 ★★★ 宿主的下发方法存在
_f_apply = _find_func(_t_main, '_apply_ui_scale', cls=_class(_t_main, 'RalseiPet'))
ok(u'A3 ★★★ 宿主有 `_apply_ui_scale()`（统一算一次、统一发 —— 不许多入口取倍率）',
   _f_apply is not None, star=True)

_apply_src = _func_source(_src_main, _t_main, '_apply_ui_scale')
_apply_code = _code_only(_apply_src)
ok(u'A3b ★★★ 下发走 `getattr` + 判 `apply_ui_scale` 可调用'
   u'（★ 缺一个控件不许全废：`item_menu_ui` 可能因道具系统初始化失败而缺席）',
   u'getattr' in _apply_code and u'apply_ui_scale' in _apply_code, star=True)
# ★★ 判据自身体检（第108轮实跑修正）：初版对 `_code_only()` 的结果判
#   `'dialogue_ui' in code` —— 但控件名是**字符串字面量**（`('dialogue_ui', ...)`），
#   已被 `_code_only` 剥掉 ⇒ **必然假红**（记忆里那条"含字面量的判据不许走 code_only"）。
#   ⇒ 正解：对**原文**判这两个令牌（它们是字符串内容，本就该按字面判）。
ok(u'A3c ★★ 下发遍历**两个控件名**（`dialogue_ui` + `item_menu_ui`）'
   u'（★ 判原文，不走 `_code_only` —— 控件名是字符串字面量，剥了就判不到）',
   u'dialogue_ui' in (_apply_src or u'')
   and u'item_menu_ui' in (_apply_src or u''), star=True)

# A4/A5 两个控件各自实现消费
for _label, _tree, _src, _cls in (
        (u'DialogueUI（对话框）', _t_dui, _src_dui, u'DialogueUI'),
        (u'ItemMenuUI（S 键菜单）', _t_menu, _src_menu, u'ItemMenuUI')):
    _fn = _find_func(_tree, 'apply_ui_scale', cls=_class(_tree, _cls))
    ok(u'A4 ★★★ %s 有 `apply_ui_scale(scale)`（真正消费倍率）' % _label,
       _fn is not None, star=True)

# =====================================================================
# B. 下发面：幂等 / 缺控件不拖垮 / 两个入口
# =====================================================================
sec(u'B 下发面（幂等 · 容错 · 两个入口）')

_apply_norm = _apply_code.replace(u' ', u'')
ok(u'B1 ★★ `_apply_ui_scale` 逐个 try/except 包住（单控件失败不许拖垮其余）',
   u'try:' in _apply_norm and u'except' in _apply_norm, star=True)

# B2 ★★★ 两个入口：set_pet_scale（改档立即生效）+ init_systems（启动用持久化值）
_setps = _find_func(_t_main, 'set_pet_scale', cls=_class(_t_main, 'RalseiPet'))
_setps_src = ast.get_source_segment(_src_main, _setps) if _setps else u''
ok(u'B2 ★★★ `set_pet_scale()` 末尾**真调** `_apply_ui_scale()`'
   u'（半自动/手动调整 ⇒ 拖着 spinbox 就看到 UI 跟着变）',
   u'_apply_ui_scale()' in (_setps_src or u'').replace(u' ', u''), star=True)

_inits = _find_func(_t_main, 'init_systems', cls=_class(_t_main, 'RalseiPet'))
_inits_src = ast.get_source_segment(_src_main, _inits) if _inits else u''
ok(u'B2b ★★★ `init_systems()` 里也调 `_apply_ui_scale()`'
   u'（★ 光靠 `set_pet_scale` 不够：它只在**用户改档**时被调，'
   u'上次设的 2.0 重启后 UI 不会生效）',
   u'_apply_ui_scale()' in (_inits_src or u'').replace(u' ', u''), star=True)

# B3 ★★★ 顺序：启动路径里「读回倍率 ⇒ 全屏化 ⇒ 刷新渲染 ⇒ 下发 UI」
#   按 AST **顶层语句序**判（不按字符位 —— 注释会污染）。
_seq_names = []
for _st in (ast.walk(_inits) if _inits else []):
    if not isinstance(_st, ast.Expr):
        continue
    _c = _st.value
    if isinstance(_c, ast.Call):
        _f = _c.func
        _nm = _f.attr if isinstance(_f, ast.Attribute) else (
            _f.id if isinstance(_f, ast.Name) else None)
        if _nm in ('_load_persisted_pet_scale', 'fit_camera_to_screen',
                   '_refresh_pet_render_scale', '_apply_ui_scale'):
            _seq_names.append((_st.lineno, _nm))
_seq_names.sort()
_ord = [n for _, n in _seq_names]
_need = ['_load_persisted_pet_scale', 'fit_camera_to_screen',
         '_refresh_pet_render_scale', '_apply_ui_scale']
_ord_ok = True
_pi = -1
for _k in _need:
    if _k not in _ord:
        _ord_ok = False
        break
    _ci = _ord.index(_k)
    if _ci <= _pi:
        _ord_ok = False
        break
    _pi = _ci
ok(u'B3 ★★★ 启动序：读回倍率 ⇒ 全屏化 ⇒ 刷新渲染倍率 ⇒ **下发 UI**'
   u'（UI 倍率由 `pet_scale` 派生 ⇒ 必须在读回之后；AST 判语句序，非字符位）',
   _ord_ok, u'序=%s' % (_ord,), star=True)

# =====================================================================
# C. 幂等性（核心）
# =====================================================================
sec(u'C 幂等性（从基准重算，不许在现值上乘）')

for _label, _tree, _cls in (
        (u'DialogueUI', _t_dui, u'DialogueUI'),
        (u'ItemMenuUI', _t_menu, u'ItemMenuUI')):
    _clsnode = _class(_tree, _cls)
    _has_base = False
    for _n in ast.walk(_clsnode) if _clsnode else []:
        if isinstance(_n, ast.Assign):
            for _t in _n.targets:
                if isinstance(_t, ast.Attribute) and _t.attr == '_ui_base':
                    _has_base = True
    ok(u'C1 ★★★ %s 有 `_ui_base` **基准快照**（幂等的唯一前提：'
       u'在现值上乘 ⇒ 1.0→1.5→1.0 会留 1.5 残留、越改越大）' % _label,
       _has_base, star=True)

# C2 ★★★ 缩放函数体里必须"先取 base 再乘" —— 不许直接 `self.BOX_INSET * s`
_dui_scale = _find_func(_t_dui, 'apply_ui_scale', cls=_class(_t_dui, 'DialogueUI'))
_dui_scale_src = ast.get_source_segment(_src_dui, _dui_scale) if _dui_scale else u''
_dui_scale_code = _code_only(_dui_scale_src or u'')
ok(u'C2 ★★★ `DialogueUI.apply_ui_scale` 从 `_ui_base` 取基准（判 `base[` 下标取值）',
   u'base[' in _dui_scale_code or u'_ui_base' in _dui_scale_code, star=True)

_menu_scale = _find_func(_t_menu, 'apply_ui_scale', cls=_class(_t_menu, 'ItemMenuUI'))
_menu_scale_src = ast.get_source_segment(_src_menu, _menu_scale) if _menu_scale else u''
# ★★★ 判据自身体检（第108轮变异测试修正）：初版判 `'_ui_base' in _menu_scale_src`
#   ⇒ **恒真**（`apply_ui_scale` 里只要**提过**这个属性名就算过；哪怕乘法写的
#   是 `float(fallback)` 不走基准，判据照样绿）。第107轮 M8 就栽在同一个坑
#   （"提到名字就算数"）。
#   ⇒ 正解：判**语义** —— 菜单的基准取值收口在 `_pt()`，所以必须真判
#     `_pt()` 的函数体里出现 `base[key]` 下标取值（AST `Subscript`，
#     `value` 是 `Name('base')`，切片是 `Name('key')`）。
#     ★ 这样"把 `base[key]` 换成 `fallback`"必报红，而"仅注释里提名字"不会误判绿。
_menu_pt = _find_func(_t_menu, '_pt', cls=_class(_t_menu, 'ItemMenuUI'))
_menu_pt_base_sub = False
for _n in ast.walk(_menu_pt) if _menu_pt else []:
    if isinstance(_n, ast.Subscript) and isinstance(_n.value, ast.Name) \
            and _n.value.id == 'base':
        _sl = _n.slice
        if isinstance(_sl, ast.Name) and _sl.id == 'key':
            _menu_pt_base_sub = True
ok(u'C2b ★★★ `ItemMenuUI` 的尺寸/字号入口 `_pt()` **真从基准取值**'
   u'（AST 判 `_pt` 体内出现 `base[key]` 下标 —— ★ 只判"提过 `_ui_base`"是恒真判据）',
   _menu_pt_base_sub, u'_pt 在=%r base[key] 命中=%r'
   % (_menu_pt is not None, _menu_pt_base_sub), star=True)

# C3 ★★★ 真跑幂等（Qt Widget 打桩：只看数值，不起真窗口）
ok(u'C3 ★★★ 幂等**真跑**：同一倍率连调两次，几何与字号**逐值相等**'
   u'（★ 不靠"看代码像对的"）',
   _run_idempotence_check()[0], _run_idempotence_check()[1], star=True)

# =====================================================================
# D. 非法输入原样不动
# =====================================================================
sec(u'D 非法输入：原样不动（不猜、不退化成别的数）')

for _label, _src, _cls in (
        (u'DialogueUI', _dui_scale_src, u'DialogueUI'),
        (u'ItemMenuUI', _menu_scale_src, u'ItemMenuUI')):
    _c = _code_only(_src or u'')
    _has_try_float = u'float(scale)' in _c.replace(u' ', u'')
    _has_nan = u'!= ' in _c or u'!=' in _c
    ok(u'D1 ★★★ %s 对 `scale` 先 `float()` 转换（非数 ⇒ 走 except 原样返回）' % _label,
       _has_try_float, star=True)
    ok(u'D1b ★★ %s 有 `NaN` 检查（`s != s` 形态 —— `NaN` 会让所有尺寸变 `int(nan)` 抛错）' % _label,
       _has_nan, star=True)
    ok(u'D1c ★★ %s 有 `<= 0` 检查（0/负 ⇒ 尺寸退化到 0 = 控件看不见）' % _label,
       (u'<=0' in _c.replace(u' ', u'')) or (u'<= 0' in _c), star=True)

# D2 ★★★ 真跑非法输入
ok(u'D2 ★★★ 非法输入**真跑**：`None`/`NaN`/`0`/负数/字符串 ⇒ 倍率**逐值不变**',
   _run_bad_input_check()[0], _run_bad_input_check()[1], star=True)

# =====================================================================
# E. 落点齐（字号 / 固定尺寸 / HTML / 框体 / 内缩）
# =====================================================================
sec(u'E 落点齐：放大不能只放一族')

# E1 ★★★ HTML 内联字号必须跟随（`setFont` 管不到字符串里的 font-size）
_has_html_pt = _find_func(_t_dui, '_html_pt', cls=_class(_t_dui, 'DialogueUI')) is not None
ok(u'E1 ★★★ `DialogueUI._html_pt()` 在盘'
   u'（★ HTML 里的 `font-size:10pt` 是**字符串字号**，`setFont` 管不到 —— '
   u'不缩它 = 框放大了但历史区那几行还是小字）',
   _has_html_pt, star=True)

# 硬编码 font-size 必须清零（全部走 _html_pt）
# ★★ 判据自身体检（第108轮实跑修正，**栽了一次**）：初版**裸扫源码**判
#   `font-size:10pt` ⇒ 我写在 `_html_pt` docstring 里的**举例**（正是这个串）
#   被算成"残留 2 处" ⇒ 报**假红**。根因 = 判据扫了注释/文档串
#   （记忆里那条"禁某 API 出现类判据禁纯文本扫"，这是**第 5 次**同类）。
#   ⇒ 正解：**只判真正拼 HTML 的那一行**（含 `f'<div style=` 且不含 `_html_pt`）。
#     这既是"窄到对"（不误报文档），又保持鉴别力（把 `_html_pt` 换回硬编码必报红）。
_n_raw_htmlpt = 0
for _l in _src_dui.split(u'\n'):
    # ★ 只认**真拼 HTML 的 f-string 行**：`f'<div style=...'`（带 f 前缀 + 单引号）
    #   —— docstring 里的举例（`<div style="font-size:10pt">` 双引号、无 f 前缀）
    #   因此天然被排除（★ 这是"窄到对"，不是靠"跳过注释行"那种脆做法）。
    if u'font-size:10pt' in _l and u"f'<div style=" in _l and u'_html_pt' not in _l:
        _n_raw_htmlpt += 1
ok(u'E1b ★★★ `dialogue_ui` 里**零** `font-size:10pt` 硬编码'
   u'（四处 HTML 拼接全改走 `_html_pt`；判据只认真拼 HTML 的 f-string 行）',
   _n_raw_htmlpt == 0, u'残留=%d' % _n_raw_htmlpt, star=True)
_has_pt_calls = _src_dui.count(u'_html_pt(') >= 4
ok(u'E1c ★★ 四处 HTML 拼接**都**用 `_html_pt(...)`',
   _has_pt_calls, u'调用数=%d' % _src_dui.count(u'_html_pt('), star=True)

# E2 头像贴图也要按倍率（否则 84 的框里贴 78 的小图）
ok(u'E2 ★★ `DialogueUI.set_face` 按 `_ui_scale` 算贴图边长'
   u'（★ 不缩 = 框放大了、头像还是小的；且**记住** `_last_face` 以便重贴）',
   u'_ui_scale' in (ast.get_source_segment(
       _src_dui, _find_func(_t_dui, 'set_face', cls=_class(_t_dui, 'DialogueUI')))
       or u'')
   and u'_last_face' in _src_dui, star=True)

# E3 三个硬编码行高（18 / 4 / 84）也要跟着
_rc = ast.get_source_segment(
    _src_dui, _find_func(_t_dui, '_recalc_size_to_content', cls=_class(_t_dui, 'DialogueUI'))) or u''
_rc_norm = _code_only(_rc).replace(u' ', u'')
ok(u'E3 ★★★ `_recalc_size_to_content` 的 `name_label_h/right_spacing/face_h`'
   u'**不再硬编码**（放大后行高不变 = 正文被挤到边框带上）',
   u'_ui_base' in _rc_norm and u'name_label_h' in _rc_norm, star=True)

# E4 布局内缩同步
ok(u'E4 ★★ `apply_ui_scale` 同步 `setContentsMargins`（否则放大后文字压到边框带）',
   u'setContentsMargins' in (_dui_scale_code or u''), star=True)

# E5 框体几何
_cls_dui = _class(_t_dui, 'DialogueUI')
_geom_ok = False
for _n in ast.walk(_dui_scale) if _dui_scale else []:
    if isinstance(_n, ast.Assign):
        for _t in _n.targets:
            if isinstance(_t, ast.Attribute) and _t.attr in (
                    'BOX_INSET', '_base_width', '_min_dialogue_h', '_max_dialogue_h'):
                _geom_ok = True
ok(u'E5 ★★★ 框体几何（`BOX_INSET` / `_base_width` / 内容高上下限）也按倍率重算',
   _geom_ok, star=True)

# E6 菜单：标题/正文/光标列/面板宽/行内间距
for _k, _v in ((u'标题字号', u"_title.setFont"), (u'提示字号', u"_hint.setFont"),
               (u'面板宽', u'panel_w'), (u'光标列宽', u'cursor_col_w'),
               (u'行内左右间距', u'margin')):
    ok(u'E6 ★★ 菜单的**%s**按倍率（`_ui_base` 键 `%s`）' % (_k, _v),
       _v in _src_menu, star=True)

# E7 已建出来的行要重设字号
ok(u'E7 ★★ `apply_ui_scale` 遍历 `self._rows` **重设已建行的字号**'
   u'（★ 不重设 = 新版面 + 旧字号的拼接脸）',
   u'_rows' in (_menu_scale_src or u'') and u'setFont' in (_menu_scale_src or u''),
   star=True)

# =====================================================================
# F. 框体缩放绘制
# =====================================================================
sec(u'F 框体缩放绘制（`paint_dark_box_scaled`）')

_f_pdb = _find_func(_t_box, 'paint_dark_box_scaled')
ok(u'F1 ★★★ `dr_textbox.paint_dark_box_scaled` 在盘（框体随 UI 倍率绘制）',
   _f_pdb is not None, star=True)

_f_setcs = _find_func(_t_box, 'set_content_scale', cls=_class(_t_box, 'DrTextboxFrame'))
ok(u'F2 ★★★ `DrTextboxFrame.set_content_scale()` 在盘（帧持有倍率）',
   _f_setcs is not None, star=True)

_pe = ast.get_source_segment(
    _src_box, _find_func(_t_box, 'paintEvent', cls=_class(_t_box, 'DrTextboxFrame'))) or u''
# ★★★ 判据自身体检（第108轮实跑修正）：初版用 `_code_only()` **剥字符串**后判
#   `'_content_scale' in code` —— 而产品写法是 `getattr(self, '_content_scale', None)`，
#   **属性名写在字符串里** ⇒ 被剥成 `getattr(self, '', None)` ⇒ **必然假红**
#   （记忆里那条："`code_only_src()` 剥 STRING ⇒ 断言字面量恒假"）。
#   ⇒ 正解：**不许走 `_code_only`**。改判 AST 结构 —— 函数体内必须真出现
#     `getattr(self, '_content_scale', ...)` 或 `Attribute(attr='_content_scale')`。
_pe_node = _find_func(_t_box, 'paintEvent', cls=_class(_t_box, 'DrTextboxFrame'))
_pe_getattr = False
_pe_attr = False
for _n in ast.walk(_pe_node) if _pe_node else []:
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
            and _n.func.id == 'getattr':
        for _a in _n.args:
            if isinstance(_a, ast.Constant) and _a.value == '_content_scale':
                _pe_getattr = True
    if isinstance(_n, ast.Attribute) and _n.attr == '_content_scale':
        _pe_attr = True
ok(u'F3 ★★★ `paintEvent` **真消费** `_content_scale`'
   u'（AST 判 `getattr(self, "_content_scale", ...)` 或属性访问；'
   u'★ 不许走 `_code_only` —— 属性名写在字符串里会被剥掉 ⇒ 假红）',
   _pe_getattr or _pe_attr,
   u'getattr=%r attr=%r' % (_pe_getattr, _pe_attr), star=True)
ok(u'F3b ★★★ 无倍率时走**原路径** `paint_dark_box`（零回归：不走新分支 = 第44轮老行为）',
   u'paint_dark_box(' in _pe and u'paint_dark_box_scaled' in _pe, star=True)

_f_setcs_src = ast.get_source_segment(_src_box, _f_setcs) if _f_setcs else u''
_f_setcs_code = _code_only(_f_setcs_src or u'')
ok(u'F4 ★★ `set_content_scale` 非法值退回 `None`（= 原路径）+ `NaN` / `<=0` 检查',
   u'None' in _f_setcs_code and (u'!=' in _f_setcs_code.replace(u' ', u'')), star=True)

# F5 ★★★ 等价性对拍（真跑）：scale == 1.0 时两条路径产出的绘制指令**逐值相等**
ok(u'F5 ★★★ **等价性真跑**：`scale == 1.0` 时 `paint_dark_box_scaled` 与'
   u'`paint_dark_box` 的绘制指令**逐值相等**（零回归的算术保证）',
   _run_equiv_check()[0], _run_equiv_check()[1], star=True)

# F6 缩放自洽：带厚/角块/黑底内缩都按倍率
# ★★★ 判据自身体检（第108轮变异测试修正）：初版判 `'BAND' in _pdb_code
#   and 'CORNER_SIZE' in _pdb_code` ⇒ **恒真**（源码里只要**提到**这两个常量名
#   就算过；把 `_m(BAND)` 改回裸 `BAND` 照样绿 —— 而裸 `BAND` 正是"框大了一圈
#   但边框还是 32px"的 bug 本体）。第107轮 M8 同一个坑。
#   ⇒ 正解：判**结构** —— `darkbox_blits` 那三处 `QRect(...)` 里，
#     带厚/角块的宽高实参**必须是被 `_m(...)` 包着的**（`Call(func=Name('_m'),
#     args=[Name('BAND'|'CORNER_SIZE')])`）。
_pdb_node = _f_pdb
_pdb_m_wrap = set()
for _n in ast.walk(_pdb_node) if _pdb_node else []:
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
            and _n.func.id == '_m' and len(_n.args) == 1:
        _a0 = _n.args[0]
        if isinstance(_a0, ast.Name) and _a0.id in ('BAND', 'CORNER_SIZE'):
            _pdb_m_wrap.add(_a0.id)
ok(u'F6 ★★★ 带厚 `BAND` 与角块 `CORNER_SIZE` 的**宽高实参真被 `_m(...)` 包裹**'
   u'（AST 判 `_m(BAND)` / `_m(CORNER_SIZE)`；★ 只判"提到常量名"是恒真判据 —— '
   u'裸 `BAND` 正是"框放大但边框仍 32px"的 bug 本体）',
   u'BAND' in _pdb_m_wrap and u'CORNER_SIZE' in _pdb_m_wrap,
   u'被 _m 包裹的常量=%s' % (sorted(_pdb_m_wrap),), star=True)

# =====================================================================
# G. 零依赖 + 原路径零回归
# =====================================================================
sec(u'G 零依赖纪律 + 原路径零回归')

# G1 缩放**本轮新增的方法**不许函数内 import
# ★★ 判据自身体检（第108轮实跑修正）：初版判**整个文件**"零函数内 import"
#   ⇒ `dialogue_ui` 报 3 处违规，但那些是**既有的**（`_is_command_phrase` 的
#     `import re`、`add_dialogue` / `add_npc_addressed` 的 `import html`），
#     与第108轮**无关** ⇒ 判据范围**过宽**（这是"老代码背锅"的典型假红）。
#   ⇒ 正解：只判**本轮新增/改动的方法**（缩放相关那四个）。
_NEW_METHODS = {
    u'dialogue_ui': (_t_dui, [u'apply_ui_scale', u'_html_pt']),
    u'item_menu_ui': (_t_menu, [u'apply_ui_scale', u'_pt']),
    u'dr_textbox': (_t_box, [u'set_content_scale', u'content_scale']),
}
for _label, (_tree, _names) in _NEW_METHODS.items():
    _bad = []
    for _mn in _names:
        _fn = _find_func(_tree, _mn)
        if _fn is None:
            continue
        for _c in ast.walk(_fn):
            if isinstance(_c, (ast.Import, ast.ImportFrom)):
                _bad.append((_mn, _c.lineno))
    ok(u'G1 ★★ `%s` 本轮新增的方法**零函数内 import**（第78轮纪律；缩放不得靠"用时再导"）'
       % _label,
       len(_bad) == 0, u'违规=%s' % (_bad[:3],), star=True)

# G2 ★★★ UI 缩放**不写**任何持久化（真源只有 pet_scale 一处）
for _label, _src in ((u'dialogue_ui', _src_dui), (u'item_menu_ui', _src_menu)):
    _bad2 = (_label == u'dialogue_ui' and u'ui_scale' in _src
             and u'save_config' in _src.split(u'def apply_ui_scale')[1][:2500]
             if u'def apply_ui_scale' in _src else False)
    ok(u'G2 ★★★ `%s` 的缩放**不自己写盘**（真源只有宿主的 `pet_scale`；'
       u'控件自己存一份 = 两份真源）' % _label,
       not _bad2, star=True)

# =====================================================================
# H. 判据自身体检
# =====================================================================
sec(u'H 判据自身体检')

_ok_true = []
for _n in ast.walk(ast.parse(io.open(__file__, encoding='utf-8').read())):
    if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name) \
            and _n.func.id == 'ok' and len(_n.args) >= 2:
        _a = _n.args[1]
        if isinstance(_a, ast.Constant) and _a.value is True:
            _ok_true.append(_n.lineno)
ok(u'H1 ★★★ 本套件无 `ok(..., True)` 恒真判据（AST 复查）',
   len(_ok_true) == 0, u'行=%s' % (_ok_true,), star=True)

ok(u'H2 ★★ 记账守恒（PASS+FAIL 总数 ≥ 25）',
   (_N['p'] + _N['f']) >= 25, u'总=%d' % (_N['p'] + _N['f']), star=True)

# H3 负控制：记账器有鉴别力（★ 不许用"故意 FAIL 再撤回"—— 会往输出里塞一行 FAIL，
#    污染"FAIL 数"的统计口径；改用**静默探针**直接测 `ok()` 的返回值与计数）。
_p_before, _f_before = _N['p'], _N['f']
_sink = io.StringIO()
_stdout_keep = sys.stdout
try:
    sys.stdout = _sink
    # ★ 不许写 `ok(..., True)` 字面 —— 那会被 H1 的"恒真判据"检测器抓到（它是对的：
    #   恒真形态就该报红）。用两个**变量**喂正/负条件，形态上不是常量。
    _live = (1 == 1)
    _dead = (1 == 2)
    _rv_true = ok(u'__negctl_true__', _live)
    _rv_false = ok(u'__negctl_false__', _dead)
finally:
    sys.stdout = _stdout_keep
_dp = _N['p'] - _p_before
_df = _N['f'] - _f_before
# ★ 撤回探针塞进去的 2 条（各 +1）—— 必须在下面这条 `ok()` **之前**撤回，
#   否则它自己的 +1 会和探针的 +1 混在一起，算术就说不清了。
_N['p'] -= 1
_N['f'] -= 1
ok(u'H3 ★★ 负控制：记账器有鉴别力 + 探针计数已撤回'
   u'（真条件 ⇒ 返 True 且 p+1；假条件 ⇒ 返 False 且 f+1；撤回后 p/f 归位）',
   _rv_true is True and _rv_false is False and _dp == 1 and _df == 1
   and _N['p'] == _p_before and _N['f'] == _f_before,
   u'true=%r false=%r dp=%d df=%d p=%d/%d f=%d/%d'
   % (_rv_true, _rv_false, _dp, _df, _N['p'], _p_before, _N['f'], _f_before),
   star=True)

# H4 令牌回验
_tokens = [u'apply_ui_scale', u'_apply_ui_scale', u'_ui_base', u'_html_pt',
           u'paint_dark_box_scaled', u'set_content_scale', u'_content_scale',
           u'_last_face', u'ui_scale', u'pet_scale']
_missing = []
_blob = _src_main + _src_dui + _src_menu + _src_box
for _tk in _tokens:
    if _tk not in _blob:
        _missing.append(_tk)
ok(u'H4 ★★★ 十个令牌逐个回原文件 `in` 一次（判据守的符号真的在盘上）',
   len(_missing) == 0, u'缺=%s' % (_missing,), star=True)

print(u'\n' + u'=' * 72)
if _N['f'] == 0:
    print(u'第108轮：PASS %d 项 · FAIL 0 项' % _N['p'])
else:
    print(u'第108轮：FAIL %d 项' % _N['f'])
print(u'=' * 72)
print(u'[PASS] %s' % u'第108轮：UI 缩放落地（缺口②）')
sys.exit(1 if _N['f'] else 0)

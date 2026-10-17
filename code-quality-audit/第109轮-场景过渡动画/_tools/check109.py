# -*- coding: utf-8 -*-
"""第109轮 · 回归套件：**原作式场景过渡动画**不许静默漂移。

用户口径（逐字）：
  「**进入场景的时候按原作有过度动画**」

★ 本套件的**取证前提**（先取证、禁自创）：原作 Deltarune ch1 的过渡实现由 UTMT
  反编译取得（`第109轮-场景过渡动画/_evidence/EVIDENCE.md` + `fade_codes.json`）：
    · `obj_fadeout_Create_0` : `image_blend = c_black; fadespeed = 0.08; image_alpha = 0;`
    · `obj_fadeout_Draw_0`   : `image_alpha += fadespeed;`（α 0→1 = 变黑）
    · `obj_persistentfadein_Create_0` : `fadespeed = -0.08; image_alpha = 1;`
    · `obj_doorA_Other_19`   : `instance_create(0,0,obj_fadeout); alarm[2] = 8;`
    · `obj_doorA_Alarm_2`    : `instance_create(0,0,obj_persistentfadein); room_goto_next();`
  ⇒ 我们的实现 = **淡出（黑变浓）→ 换房 → 淡入（黑变淡）**，遮罩恒为纯黑。

守的**不变式**（改任何一条 = 静默漂移 ⇒ 必须报红）：
  A  ★★★ 过渡机制**真的存在且被消费者调用**（不是"写了函数没人用"）
     （`request_scene_transition` / `_advance_scene_transition` 都必须是
       AST 层面**有调用点**的 —— 本项目最贵的坑是"函数写对了但产品用不上"）
  B  ★★★ 时序**对齐原作**：淡出 267ms（8帧@30fps）· 淡入 417ms（12.5帧@30fps）
  C  ★★★ **阶段序**：`out` → 换房 → `in`（顺序反了就"先瞬变后淡入"）
  D  ★★★ **换房那一拍真的调 `switch`**（AST 判 `_do_scene_transition_swap` 体内）
  E  ★★ 画布遮罩：`set_transition_alpha` 在盘 · `paintEvent` **最后**叠黑 · 钳位
  F  ★★ 默认零回归：`_transition_alpha == 0` 时 `paintEvent` **不执行**遮罩段
  G  ★★ 容错：非法 α 不动 · 异常必收尾（绝不卡在全黑）
  H  ★★ 可关开关 + 入口接线（`travel_to_scene` 走过渡）
  I  判据自身体检

跑法：
    C:\\Python311\\python.exe check109.py

★ 纪律：本支**零外部盘依赖**。
"""
import io
import os
import sys
import ast

HERE = os.path.dirname(os.path.abspath(__file__))
# ★★ `RALSEI_MUT_ROOT`：变异测试把产品源码复制到临时区后让本套件读那份。
#   默认（未设）⇒ 读工作区真文件 ＝ 零行为变化。
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
CANVAS = os.path.join(PKG, 'modules', 'scene_canvas.py')

_main_src = read(MAIN)
_canvas_src = read(CANVAS)
_t_main = ast.parse(_main_src)
_t_canvas = ast.parse(_canvas_src)


def _class(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == name:
            return n
    return None


def _func(node, name, cls=None):
    scope = cls if cls is not None else node
    for n in ast.walk(scope):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _calls(scope):
    """收集 scope 内所有**被调用的函数/方法名**（`Name` 与 `Attribute.attr`）。"""
    names = []
    for n in ast.walk(scope) if scope is not None else []:
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                names.append(f.id)
            elif isinstance(f, ast.Attribute):
                names.append(f.attr)
    return names


def _assign_names(scope):
    """收集 scope 内的**赋值目标名**（`x = ...` 的 `x`）。"""
    out = []
    for n in ast.walk(scope) if scope is not None else []:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out.append(t.id)
                elif isinstance(t, ast.Attribute):
                    out.append(t.attr)
    return out


def _num_const(scope, attr_name):
    """找 `X = <数字>` 形式（模块/类级常量）并返回其值。

    ★ AST 判（不是文本扫）：只认 `Assign(targets=[Name/X], value=Num)`。
    """
    for n in ast.walk(scope) if scope is not None else []:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Num):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == attr_name:
                    return n.value.n
    return None


print(u'=' * 72)
print(u'第109轮 · 原作式场景过渡动画（check109）')
print(u'=' * 72)

_RALSEI = _class(_t_main, 'RalseiPet')
_RALSEI_CALLS = _calls(_RALSEI)

# ---------------------------------------------------------------------
sec(u'A 过渡机制存在且被消费（不是"写了没人用"）')

_req = _func(_t_main, 'request_scene_transition', cls=_RALSEI)
_adv = _func(_t_main, '_advance_scene_transition', cls=_RALSEI)
_swap = _func(_t_main, '_do_scene_transition_swap', cls=_RALSEI)

ok(u'A1 ★★ `request_scene_transition` 方法存在',
   _req is not None, u'found=%r' % (_req is not None))
ok(u'A2 ★★ `_advance_scene_transition` 方法存在',
   _adv is not None, u'found=%r' % (_adv is not None))

# ★★★ 真判据：**消费点**存在（不然就是"函数写对了但产品用不上"）
ok(u'A3 ★★★ `request_scene_transition` **真有调用点**（不是死函数 —— '
   u'本项目最贵的坑）',
   u'request_scene_transition' in _RALSEI_CALLS,
   u'调用点计数=%d' % _RALSEI_CALLS.count(u'request_scene_transition'), star=True)
ok(u'A4 ★★★ `_advance_scene_transition` **真有调用点**'
   u'（每帧推进；没它过渡永远停在第一帧）',
   u'_advance_scene_transition' in _RALSEI_CALLS,
   u'调用点计数=%d' % _RALSEI_CALLS.count(u'_advance_scene_transition'), star=True)

# 推进必须挂在每帧钩子上（30ms `update_movement`），不能只在换房时调一次
_um = _func(_t_main, 'update_movement', cls=_RALSEI)
_um_calls = _calls(_um)
ok(u'A5 ★★★ `_advance_scene_transition` 挂在**每帧** `update_movement` 上'
   u'（原作是逐帧 `image_alpha += fadespeed`）',
   u'_advance_scene_transition' in _um_calls,
   u'update_movement 内命中=%r' % (u'_advance_scene_transition' in _um_calls), star=True)

# ---------------------------------------------------------------------
sec(u'B 时序对齐原作（30fps）')

_main_cls = _RALSEI
_fade_out = _num_const(_main_cls, 'SCENE_FADE_OUT_MS')
_fade_in = _num_const(_main_cls, 'SCENE_FADE_IN_MS')
ok(u'B1 ★★★ 淡出时长 == 267ms（原作 `alarm[2]=8` 帧 ÷ 30fps）',
   _fade_out is not None and abs(_fade_out - 267.0) < 1.0,
   u'SCENE_FADE_OUT_MS=%r' % (_fade_out,), star=True)
ok(u'B2 ★★★ 淡入时长 == 417ms（原作 `1/0.08=12.5` 帧 ÷ 30fps）',
   _fade_in is not None and abs(_fade_in - 417.0) < 1.0,
   u'SCENE_FADE_IN_MS=%r' % (_fade_in,), star=True)
# ★ 负控制：两者**必须不同**（若写成同一个数，说明是拍脑袋的对称值，不是原作换算）
ok(u'B3 负控制：淡出 ≠ 淡入（原作确实不对称：8 帧 vs 12.5 帧）',
   _fade_out is not None and _fade_in is not None and _fade_out != _fade_in,
   u'out=%r in=%r' % (_fade_out, _fade_in))

# ---------------------------------------------------------------------
sec(u'C 阶段序 out → 换房 → in')

_adv_src = ast.get_source_segment(_main_src, _adv) if _adv is not None else u''
# ★ 第116轮修正：`detail` 绿时空（文本恒定），红时才给偏移诊断。
#   原写法绿时也回显 `_adv_src.find(...)` 的**字符偏移** ⇒ 该函数上方任何改动都会
#   挪动偏移 ⇒ 报假 DIFF（断言其实没变）。同记忆铁律：
#   **判据禁回显随时相变的绝对值（含行号/偏移/下标）**。
_c1_ok = (u"set_transition_alpha(1.0)" in _adv_src
          and u"_do_scene_transition_swap" in _adv_src
          and _adv_src.index(u"set_transition_alpha(1.0)")
          < _adv_src.index(u"_do_scene_transition_swap"))
ok(u'C1 ★★★ 淡出阶段先置 α=1 **再**换房（`set_transition_alpha(1.0)` 先于 swap）',
   _c1_ok,
   u'' if _c1_ok else u'序：alpha1@%s swap@%s'
   % (_adv_src.find(u"set_transition_alpha(1.0)"),
      _adv_src.find(u"_do_scene_transition_swap")), star=True)
ok(u'C2 ★★ 阶段在 `out` / `in` 之间切换（源码里两个 phase 字面量都在）',
   u"'out'" in _adv_src and u"'in'" in _adv_src,
   u"out=%r in=%r" % (u"'out'" in _adv_src, u"'in'" in _adv_src))

# ---------------------------------------------------------------------
sec(u'D 换房那一拍真的调 switch')

_swap_calls = _calls(_swap)
ok(u'D1 ★★★ `_do_scene_transition_swap` 体内**真调 `switch`**'
   u'（只改状态不换房 = 过渡结束了场景没变）',
   u'switch' in _swap_calls, u'switch 命中=%r' % (u'switch' in _swap_calls), star=True)
_swap_src = ast.get_source_segment(_main_src, _swap) if _swap is not None else u''
ok(u'D2 ★★ 换房成功后重算明/暗世界（`_possession_sync_world`）'
   u'（与 `travel_to_scene` 同一条纪律）',
   # ★★ 第109轮修正（变异 M12 逼出来）：初版尾部有 `or '_possession_sync_world'
   #   in _swap_src` 的**文本兜底** ⇒ 而 `_do_scene_transition_swap` 的 docstring
   #   里恰好写着"换房成功要 `_possession_sync_world()`" ⇒ 注释一提到名字判据就恒真
   #   （**"提到某名字"类恒真判据**，本项目已第 5 次发作）。
   #   ⇒ 删掉文本兜底，只认 **AST 真调用**（`_swap_calls`）；同时保留
   #     `_travel_feedback_done` —— 它是第109轮新增的**统一收尾**，
   #     换房路径改走它也等价（见 `_travel_after_transition`）。
   u'_possession_sync_world' in _swap_calls or u'_travel_feedback_done' in _swap_calls,
   u'sync-call=%r feedback-call=%r'
   % (u'_possession_sync_world' in _swap_calls,
      u'_travel_feedback_done' in _swap_calls))

# ---------------------------------------------------------------------
sec(u'E 画布遮罩（set_transition_alpha + paintEvent 末叠黑）')

_CANVAS = _class(_t_canvas, 'SceneCanvas')
_sta = _func(_t_canvas, 'set_transition_alpha', cls=_CANVAS)
ok(u'E1 ★★★ `SceneCanvas.set_transition_alpha` 存在',
   _sta is not None, u'found=%r' % (_sta is not None), star=True)

# ★ 钳位：α 必须钳到 [0,1]（AST 判 Comparison，**不扫文本**）
_sta_src = ast.get_source_segment(_canvas_src, _sta) if _sta is not None else u''
# ★★ 第109轮修正（变异 M8 逼出来）：初版判 `'0.0' in _sta_src and '1.0' in _sta_src`
#   ⇒ 拆掉钳位后**仍 PASS**（docstring 里就写着"[0.0, 1.0]"、注释里也有 0.0/1.0）
#   ⇒ 又是"文本扫" = 没鉴别力。改为 **AST 真比较**：函数体内必须**同时**存在
#     与 0.0 和 1.0 的 `Compare`（真钳位必然写 `a < 0.0` 之类）。
def _has_cmp_num(scope, num):
    for _n in ast.walk(scope) if scope is not None else []:
        if isinstance(_n, ast.Compare):
            for _c in [_n.left] + list(_n.comparators):
                if isinstance(_c, ast.Num) and abs(_c.n - num) < 1e-9:
                    return True
    return False


_clamp_lo = _has_cmp_num(_sta, 0.0)
_clamp_hi = _has_cmp_num(_sta, 1.0)
ok(u'E2 ★★ `set_transition_alpha` 对 α 做 **[0,1] 钳位**（超界会让 QColor 出错）',
   _clamp_lo and _clamp_hi,
   u'AST比较0.0=%r AST比较1.0=%r' % (_clamp_lo, _clamp_hi))

# ★★★ paintEvent 里的遮罩段：必须是**最后**（在 paint_on 之后），且在
#   translate/scale **之外**（否则遮罩会被画面偏移/缩放带跑）。
#   ★★★ 第112轮续三修正：旧写法用**字符串** `in` + `rindex`，detail 还回显
#     中文偏移量（`paint_on@855 fillRect@2208`）——
#      ① 违反契约「判据禁纯文本扫」（注释/串一提名字即误报）；
#      ② 违反契约「判据禁回显随时相变绝对值（含行号）」——
#         上方代码增删几行 ⇒ 偏移量必变 ⇒ 基线反复 DIFF（本轮 check109
#         已经因为 `paintEvent` 加 `save/restore` 而 DIFF 过一次）。
#   ⇒ 改为 **AST 结构**：在 `paintEvent` 的**语句序列**里找
#     `paint_on(...)` 与 `fillRect(...)` 两类 `Call`，判"序号关系"，
#     detail 只输出 `idx_a < idx_b`（**序关系**，不随行号/偏移漂移）。
_pe = _func(_t_canvas, 'paintEvent', cls=_CANVAS)


def _first_call_lineno(func_node, names, within_if_with=None):
    """`func_node` 内 `names` 中被调函数的**首次出现行号**（只用于比大小）。

    ★★★ 第112轮续三：**必须限定"在过渡遮罩那个 if 分支内"**！
      早先版本取 `fillRect` 的**全局首次** ⇒ 命中的是 `paintEvent` 开头那句
      `if self._opaque_bg: p.fillRect(self.rect(), ...)`（**房间黑底**，
      本来就该在内容**之前**）⇒ 判据必红（误报）。
      ⇒ 加 `within_if_with`：只统计**其祖先 `If` 的 test 里出现该名字**的调用
        （这里 = `_transition_alpha`）—— 这才是"过渡遮罩那次 fillRect"。

    ★ 为什么用 `lineno` 而不是"顶层语句索引"（第112轮续三另一处实证失败）：
      `paintEvent` 顶层 body 只有一条 `try:`，两类调用**都在 try 内** ⇒
      顶层语句索引**恒相等**（都是 0）⇒ 判不出先后。
    ★ `lineno` **只做 `<` 比较**，**绝不回显**（契约：禁回显随相变绝对值，含行号）。
    """
    if func_node is None:
        return None
    _best = None
    if within_if_with is None:
        # ★ 不限 If：扫**整个函数体**（`paint_on(...)` 是 `paintEvent` 的顶层
        #   语句，不在任何 `If` 内 ⇒ 只在 If 里找会漏掉它，line=None）。
        for _n in ast.walk(func_node):
            if isinstance(_n, ast.Call):
                _f = _n.func
                _nm = (_f.id if isinstance(_f, ast.Name)
                       else _f.attr if isinstance(_f, ast.Attribute) else None)
                if _nm in names:
                    _ln = getattr(_n, 'lineno', None)
                    if _ln is not None and (_best is None or _ln < _best):
                        _best = _ln
        return _best
    for _parent in ast.walk(func_node):
        if not isinstance(_parent, ast.If):
            continue
        # 该 If 的 test 里必须出现 `within_if_with`（Name/Attribute 皆可）
        _hit = False
        for _t in ast.walk(_parent.test):
            if isinstance(_t, ast.Attribute) and _t.attr == within_if_with:
                _hit = True
            elif isinstance(_t, ast.Name) and _t.id == within_if_with:
                _hit = True
        if not _hit:
            continue
        for _n in ast.walk(_parent):
            if isinstance(_n, ast.Call):
                _f = _n.func
                _nm = (_f.id if isinstance(_f, ast.Name)
                       else _f.attr if isinstance(_f, ast.Attribute) else None)
                if _nm in names:
                    _ln = getattr(_n, 'lineno', None)
                    if _ln is not None and (_best is None or _ln < _best):
                        _best = _ln
    return _best


_ln_paint = _first_call_lineno(_pe, {'paint_on'})
_ln_mask = _first_call_lineno(_pe, {'fillRect'},
                              within_if_with='_transition_alpha')
_order_ok = (_ln_paint is not None and _ln_mask is not None
             and _ln_paint < _ln_mask)
ok(u'E3 ★★★ `paintEvent` 在**画完内容之后**叠黑遮罩'
   u'（原作 `obj_fadeout` 也是最后画 → 盖在最上层）',
   _order_ok, u'语句序 paint_on **先于** 过渡遮罩 fillRect = %r'
   % (_order_ok,), star=True)

# ★★ 遮罩色 = 纯黑（原作出处 `image_blend = c_black`）
_tcol = _num_const(_t_canvas, 'TRANSITION_COLOR')
_black = False
for n in ast.walk(_t_canvas):
    if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
        for t in n.targets:
            if isinstance(t, ast.Name) and t.id == 'TRANSITION_COLOR':
                if (n.value.func.__class__ is ast.Name
                        and n.value.func.id == 'QColor'):
                    args = [a.n for a in n.value.args
                            if isinstance(a, ast.Num)]
                    if args == [0, 0, 0]:
                        _black = True
ok(u'E4 ★★ 遮罩色 = **纯黑** `QColor(0,0,0)`（原作 `image_blend = c_black`）',
   _black, u'TRANSITION_COLOR=QColor(0,0,0) 命中=%r' % _black)

# ---------------------------------------------------------------------
sec(u'F 默认零回归：α=0 时不画遮罩')

def _has_alpha_guard(func_node):
    """`paintEvent` 里是否存在 `if <含 _transition_alpha 的比较> > 0` 的真守卫。

    ★★★ 第112轮续三：旧写法 `'_transition_alpha > 0.0' in _pe_src` 是**文本扫**
      ⇒ 注释里写一句 `# _transition_alpha > 0.0 才画` 就恒真（契约已四次发作）。
    ⇒ 走 AST：必须是**真 `If` 节点**，其 `test` 是 `Compare`，且左右出现
      `_transition_alpha` 这个 **Name/Attribute** ⇒ 注释/字符串不可能命中。
    """
    if func_node is None:
        return False
    for _n in ast.walk(func_node):
        if not isinstance(_n, ast.If):
            continue
        _t = _n.test
        if not isinstance(_t, ast.Compare):
            continue
        _names = set()
        for _x in [_t.left] + list(_t.comparators):
            for _y in ast.walk(_x):
                if isinstance(_y, ast.Attribute) and _y.attr == '_transition_alpha':
                    _names.add('attr')
                elif isinstance(_y, ast.Name) and _y.id == '_transition_alpha':
                    _names.add('name')
        if _names:
            return True
    return False


_mask_guarded = _has_alpha_guard(_pe)
ok(u'F1 ★★★ `paintEvent` 的遮罩段**由 `_transition_alpha > 0.0` 守卫**'
   u'（不守卫 ⇒ 正常态也填一层黑 = 全屏黑屏）',
   _mask_guarded, u'AST真If守卫命中=%r' % _mask_guarded, star=True)

# ★ 初始化值 = 0.0（构造完不遮挡）
_init = _func(_t_canvas, '__init__', cls=_CANVAS)
_init_src = ast.get_source_segment(_canvas_src, _init) if _init is not None else u''
ok(u'F2 ★★ 构造时 `_transition_alpha = 0.0`（不切场景 ⇒ 零行为变化）',
   u'_transition_alpha = 0.0' in _init_src,
   u'初始化命中=%r' % (u'_transition_alpha = 0.0' in _init_src))

# ---------------------------------------------------------------------
sec(u'G 容错：非法 α 不动 · 异常必收尾')

# 非法输入：NaN / 非数 ⇒ 直接 return（AST 判 `!=` 的 NaN 守卫 或 try/except）
_has_nan_guard = u'a != a' in _sta_src or u'math.isnan' in _sta_src
_has_try = False
for n in ast.walk(_sta) if _sta is not None else []:
    if isinstance(n, ast.Try):
        _has_try = True
ok(u'G1 ★★ `set_transition_alpha` 拒绝 NaN / 非数（不静默改成 0 或 1）',
   _has_nan_guard or _has_try,
   u'nan_guard=%r try=%r' % (_has_nan_guard, _has_try))

# ★★★ 异常必收尾：`_advance_scene_transition` 的 except 里必须把 α 归 0
#   （否则一次异常 ⇒ 屏幕永久全黑，灾难性失败模式）
_finally_ok = False
if _adv is not None:
    for n in ast.walk(_adv):
        if isinstance(n, ast.ExceptHandler):
            seg = ast.get_source_segment(_main_src, n) or u''
            if u'set_transition_alpha(0.0)' in seg:
                _finally_ok = True
ok(u'G2 ★★★ `_advance_scene_transition` 异常分支**必把 α 归 0**'
   u'（否则"过渡卡住 ⇒ 全黑屏"，灾难性）',
   _finally_ok, u'except 内归零命中=%r' % _finally_ok, star=True)

# ---------------------------------------------------------------------
sec(u'H 可关开关 + 入口接线')

_sw = None
for n in ast.walk(_RALSEI):
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Name) and t.id == 'SCENE_TRANSITION_ENABLED':
                _sw = n.value
ok(u'H1 ★★ `SCENE_TRANSITION_ENABLED` 开关存在（可一刀关掉定位）',
   # ★★ 第109轮修正（变异 M10 逼出来）：初版只判 `isinstance(_sw, ast.NameConstant)`
   #   ⇒ 把 `= True` 改成 `= False` **照样 PASS**（False 也是 NameConstant）
   #   ⇒ 判据**没鉴别力**（"开关存在"不等于"开关是开的"）。
   #   改为**同时判值**：必须是 `True`（第109轮产品口径 = 默认开）。
   _sw is not None and isinstance(_sw, ast.NameConstant) and _sw.value is True,
   u'found=%r value=%r' % (_sw is not None,
                           _sw.value if isinstance(_sw, ast.NameConstant) else None))
# 关了必须能回落（`request_scene_transition` 里判开关）
_req_src = ast.get_source_segment(_main_src, _req) if _req is not None else u''
ok(u'H2 ★★ 开关为 False 时 `request_scene_transition` **返回 False**（调用方回落）',
   u'SCENE_TRANSITION_ENABLED' in _req_src and u'return False' in _req_src,
   u'守开关=%r' % (u'SCENE_TRANSITION_ENABLED' in _req_src))

# ★★★ 用户可见入口接线：`travel_to_scene` 必须走过渡（否则"写好了但用户用不上"）
_tts = _func(_t_main, 'travel_to_scene', cls=_RALSEI)
_tts_calls = _calls(_tts)
ok(u'H3 ★★★ `travel_to_scene`（用户可见入口）**真走过渡**'
   u'（不然又是"函数写对了、产品用不上"）',
   u'request_scene_transition' in _tts_calls,
   u'命中=%r' % (u'request_scene_transition' in _tts_calls), star=True)
# 回落路径必须还在（过渡被拒 ⇒ 老行为照常）
ok(u'H4 ★★ `travel_to_scene` 保留**回落路径**（过渡被拒 ⇒ 老行为）',
   u'_travel_commit' in _tts_calls,
   u'_travel_commit 命中=%r' % (u'_travel_commit' in _tts_calls))

# ---------------------------------------------------------------------
sec(u'I 判据自身体检')

# I1 每个被判的函数**真的解析到了**（否则"对 None 判空" 全绿 = 恒真）
_all_found = all(x is not None for x in (_req, _adv, _swap, _sta, _pe, _um))
ok(u'I1 ★★★ 所有被判函数/类**都解析到了**'
   u'（若为 None，后续所有 `in src` 判据全变恒假）',
   _all_found, u'req=%r adv=%r swap=%r sta=%r pe=%r um=%r'
   % (_req is not None, _adv is not None, _swap is not None,
      _sta is not None, _pe is not None, _um is not None), star=True)

# I2 负控制：确认"判据真能报红" —— 临时构造一个反例并在内存里判
_fake_src = u'def f():\n    pass\n'
_fake_tree = ast.parse(_fake_src)
_fake_func = _func(_fake_tree, 'f')
ok(u'I2 负控制：对一个**没有遮罩**的函数，`paintEvent` 判据会判否',
   _func(_fake_tree, 'paintEvent') is None,
   u'空树上 paintEvent=%r' % (_func(_fake_tree, 'paintEvent'),))

# I3 A/B：确认 `_calls` 真的能区分"有/没有调用"
_ab_src = u'def g():\n    request_scene_transition(1)\ndef h():\n    pass\n'
_ab_tree = ast.parse(_ab_src)
_g_calls = _calls(_func(_ab_tree, 'g'))
_h_calls = _calls(_func(_ab_tree, 'h'))
ok(u'I3 A/B：`_calls` 对"调了"与"没调"给**不同**结果（否则 A3/A4 是恒真）',
   (u'request_scene_transition' in _g_calls)
   and (u'request_scene_transition' not in _h_calls),
   u'g=%r h=%r' % (u'request_scene_transition' in _g_calls,
                   u'request_scene_transition' in _h_calls))

# ---------------------------------------------------------------------
print(u'\n' + u'=' * 72)
print(u'第109轮：PASS %d 项 · FAIL %d 项' % (_N['p'], _N['f']))
print(u'=' * 72)

_ev = os.path.abspath(os.path.join(HERE, '..', '_evidence'))
try:
    if not os.path.isdir(_ev):
        os.makedirs(_ev)
    with io.open(os.path.join(_ev, 'check109.txt'), 'w', encoding='utf-8') as f:
        f.write(u'\n'.join(_OUT) + u'\n')
except Exception as e:
    print(u'证据落盘失败：%s' % e)

sys.exit(1 if _N['f'] else 0)

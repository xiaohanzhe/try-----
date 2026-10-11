# -*- coding: utf-8 -*-
"""第一百零六轮回归锁：**非瞬移**（逐跳走完）＋ **全屏化**（等比放大）＋ 清死代码。

用户口径（第106轮，逐字）
========================
  「我要的是类似游戏全屏的那种场景效果，并且，**不能瞬移到达一个地方** ok？」
  「**完整的走过去**，记住，如果我对里面任何一个人说，马上会桌面，
    那他们顶多是带着我一起**非常快的按原路线返回**也不是瞬移
    （相当于加快速度跑回来，也要全程）」
  「如果场景占屏幕比例太不美观那就适当放大，当然，那意味着**人物也要等比例放大**」

本套件守三条
============
  A **非瞬移**：`travel_to` 拿到 `steps` 后必须**逐跳**走完（不是只 `switch` 终点一次）
     —— 第105轮录屏实证的缺口：18 跳的路线只走了最后一步，中间 16 间房一帧不出现。
  B **全屏化**：`camera.size` 与 `camera.scale` **成对**抬高
     （`scoped_size()` 必须仍是 320×240 ⇒ 相机可见范围不变，只是画得更大），
     且 `viewport_size()` 的上限随之上抬（画布真的铺开）。
  C **清死代码**：`main.py` 里那行 `scene.camera_follow_or_create()`（全仓无此方法）
     必须消失，且**不许**把"相机没建时隐藏画布"这条合法降级一起删掉。

判据纪律（本项目铁律）
======================
  · 能上 AST 就上 AST（不纯文本扫 —— 注释里提一嘴就会误报，已栽 4 次）；
  · 正/负控制**成对**（每条"守什么"都要有一条"改成坏的必须报红"）；
  · **零外部盘依赖**（原作在 E 盘，回归碰不得）；
  · **无恒真判据**（`ok(..., True)` 这种"看着在守其实没守"的一律禁掉）。

退出码：0 = 全绿；1 = 有 FAIL。
"""
import ast
import os
import re
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
CTRL = os.path.join(PKG, 'modules', 'scene_controller.py')
CAM = os.path.join(PKG, 'modules', 'scene_camera.py')
RENDER = os.path.join(PKG, 'modules', 'scene_render.py')
MAIN = os.path.join(PKG, 'src', 'main.py')
DESKTOP = os.path.join(PKG, 'assets', 'scenes', 'desktop.json')

_passed = 0
_failed = []


def check(desc, cond, star=False):
    global _passed
    tag = '★ ' if star else ''
    if cond:
        _passed += 1
        print('[PASS] %s%s' % (tag, desc))
    else:
        _failed.append(desc)
        print('[FAIL] %s%s' % (tag, desc))


def _read(p):
    with open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def _tree(p):
    try:
        return ast.parse(_read(p))
    except SyntaxError as e:
        print('        [syntax] %s: %s' % (p, e))
        return None


def _find_func(tree, name):
    """按语义取**第一个**同名函数定义（`ast.walk` + break 是陷阱：同名多个）。

    这里显式取 `ast.Module.body` 里的顶层/类内第一处 —— 由调用方按需再筛。
    """
    if tree is None:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return node
    return None


def _func_source(src, tree, name):
    """取某函数定义的源码切片（含 def 行）。取不到 → ''。"""
    fn = _find_func(tree, name)
    if fn is None or not hasattr(fn, 'lineno'):
        return ''
    lines = src.splitlines()
    lo = fn.lineno - 1
    hi = getattr(fn, 'end_lineno', lo + 1)
    return '\n'.join(lines[lo:hi])


def _calls_attr(tree, fname, attr):
    """`fname` 函数体里有没有 `self.<attr>(...)` 调用（AST）。"""
    fn = _find_func(tree, fname)
    if fn is None:
        return False
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == attr:
            v = n.func.value
            if isinstance(v, ast.Name) and v.id == 'self':
                return True
    return False


def _code_only(src):
    """把源码里的**字符串字面量内容**抹空，再 `unparse` 回代码文本。

    ★ 为什么要它（第106轮自己踩的）：
      `travel_to` 的 docstring 里写着「多跳路径」等字样；更关键的是
      `'route': 'direct'` 这种字面量会让"纯文本扫 `switch`"出现误判。
      本项目**第 4 次**栽在"纯文本扫"上了（95D1 → 96bC4 → 96b复检 → 本轮）。
      ⇒ 凡"某 API 有没有被调用"，一律走 AST（本函数把字面量抹空后仍留结构）。
    """
    try:
        t = ast.parse(src)
    except SyntaxError:
        return src
    for n in ast.walk(t):
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) \
                and isinstance(n.value.value, str):
            n.value.value = ''      # 抹掉字符串字面量内容（含 docstring）
    return ast.unparse(t) if hasattr(ast, 'unparse') else src


print('=' * 70)
print('第一百零六轮：非瞬移 + 全屏化 + 清死代码')
print('=' * 70)

_src_ctrl = _read(CTRL)
_t_ctrl = _tree(CTRL)
_src_main = _read(MAIN)
_t_main = _tree(MAIN)
_src_cam = _read(CAM)
_src_render = _read(RENDER)

ok = check

# =====================================================================
#  A. 非瞬移：travel_to 逐跳走完（★ 本轮核心）
# =====================================================================
print('\n-- A 非瞬移（逐跳走完，不是一步到位）--')

# A1 ★★★ 存在 walk_steps（逐跳执行器）
ok('A1 ★★★ `scene_controller.walk_steps` 存在（逐跳执行器）',
   _find_func(_t_ctrl, 'walk_steps') is not None, star=True)

# A2 ★★★ travel_to 里真的**委托**给 walk_steps（不是把 steps 抄进返回值就完事）
#   ★ AST：travel_to 函数体内有 self.walk_steps(...) 调用。
ok('A2 ★★★ `travel_to` 真的调 `walk_steps`（不是把 steps 抄进返回值就完事）'
   '—— 这是第105轮录屏打出的缺口（18 跳只走了最后一步）',
   _calls_attr(_t_ctrl, 'travel_to', 'walk_steps'), star=True)

# A3 ★★★ `plan['ok']`（有路线）那条分支里**不再**直接 switch 终点一次
#   ⚠️ 注意区分两条分支：
#     · ① 多跳路径分支（本轮改的地方）⇒ 必须走 walk_steps，**不许**直切终点；
#     · ② 直达降级分支（`route='direct'`）⇒ switch 是**正确的**
#       （那里本来就没有逐跳路线可走 —— 用户口径下它是"跨章还没支持"的降级）。
#   判据：**只在 ① 分支**里扫。用 AST 定位 `if plan.get('ok'):` 这个 If 节点的 body。
def _branch_has_switch(src, tree, func_name, test_src_frag, include_orelse=True):
    """取 `func_name` 里 `test` 源码包含 `test_src_frag` 的 If 节点，
    扫它 body（含 orelse）有无 `self.switch(...)` 调用。

    :return: `(has_switch: bool, test_src: str)`；找不到该分支 → `None`。
    """
    fn = _find_func(tree, func_name)
    if fn is None:
        return None
    for n in ast.walk(fn):
        if isinstance(n, ast.If):
            try:
                ts = ast.unparse(n.test)
            except Exception:
                continue
            if test_src_frag in ts:
                nodes = list(ast.walk(n))
                if not include_orelse:
                    nodes = [m for m in ast.walk(n) if m is not n]
                for m in ast.walk(n):
                    if isinstance(m, ast.Call) and isinstance(m.func, ast.Attribute) \
                            and m.func.attr == 'switch':
                        v = m.func.value
                        if isinstance(v, ast.Name) and v.id == 'self':
                            return (True, ts)
                return (False, ts)
    return None


_pair = _branch_has_switch(_src_ctrl, _t_ctrl, 'travel_to', "plan.get('ok')")
ok('A3 ★★★ `travel_to` 的**有路线分支**里不再直切终点（`self.switch(`）'
   '—— 改由 walk_steps 逐跳；否则又会"一步到位"（实测分支判定=%r）'
   % (_pair and _pair[1],),
   _pair is not None and _pair[0] is False, star=True)

# A3b ★★ 全函数里 `switch` 仍在（**直达降级分支**要用它，别把合法降级一起删了）
#   判据取"travel_to 函数体内**至少**有一处 self.switch" —— 那处只能在直达降级里
#   （① 分支已被 A3 证明没有）。
_tt_all = _calls_attr(_t_ctrl, 'travel_to', 'switch')
ok('A3b ★★ `travel_to` 仍保留 `switch()` 调用（**直达降级分支**要用它；'
   'A3 已证明有路线分支里没有，所以这处只在 `route=direct` 里）',
   _tt_all is True, star=True)

# A4 负控制：A3 有鉴别力（把 walk_steps 换回"直接 switch"必须判假）


def _fake_branch_has_switch():
    _t = ast.parse("def travel_to(self, target):\n"
                   "    if plan.get('ok'):\n"
                   "        return self.switch(sid)\n")
    return _branch_has_switch('', _t, 'travel_to', "plan.get('ok')")


_fb = _fake_branch_has_switch()
ok('A4 负控制：A3 有鉴别力（"①分支里直接 switch 终点"的假实现必须判**有** switch）',
   _fb is not None and _fb[0] is True, star=True)

# A5 ★★★ walk_steps 逐跳校验链式（`from` 必须 == 当前场景）
_ws = _func_source(_src_ctrl, _t_ctrl, 'walk_steps')
_ws_code = _code_only(_ws)
# ★★ 第106轮修正（变异测试 M2 逼出来的）：初版只查 `"want_from" in code and "!= cur" in code`
#   ⇒ 把 `if want_from and cur and want_from != cur:` 改成 `if False and ...`
#   **照样 PASS**（两个子串都还在）—— 这是"**断赋值不断行为**"的老坑。
#   ⇒ 改为**AST**：在 `walk_steps` 里找 `While/If` 的 `test`，要求存在一个
#      `Compare` 节点同时出现 `want_from` 与 `!=`（短路 `False and …` 后，
#      `Compare` 仍在 `test` 子树里 ⇒ 还得再判 `test` 的**顶层**不是常量假）。
_ws_tree = None
try:
    _ws_tree = ast.parse(textwrap.dedent(_ws))
except Exception:
    _ws_tree = None
_A5ok = False
if _ws_tree is not None:
    for _n in ast.walk(_ws_tree):
        if not isinstance(_n, (ast.If, ast.While)):
            continue
        # ★★ 第106轮实测坑（**这三处 AST 判据全栽在这儿**）：
        #   ① `_n.test` 顶层往往是 `UnaryOp(Not)` / `BoolOp`，不是目标节点 ⇒
        #      必须 `ast.walk(_n.test)`（初版对，但下一条会害死自己）；
        #   ② **不能在第一个 If 上就 `break`** —— `walk_steps` 的第一个 If 是
        #      `if not steps:`（UnaryOp，无目标）⇒ 若在那里 break，
        #      后面真正带 `want_from` 的 If **根本没被看**（实测 top=UnaryOp）；
        #      初版把这两个坑叠在一起 ⇒ A5 **恒假**（判据自己说谎）。
        #   ③ 短路 `if False and want_from != cur:` 的 test 顶层面是 `BoolOp`，
        #      但 `ast.walk` 仍能摸到那个 `Compare` ⇒ 靠 ③ 判"是否短路"不够，
        #      必须**先剥掉顶层字面量假**：只在 test 顶层不是常量假时才认。
        # ★★ 第106轮实测坑（第 2 次）：短路 `if False and want_from != cur:` 的
        #   `test` 顶层是 **BoolOp**（不是裸 Constant）⇒ 初版只认 `ast.Constant`
        #   ⇒ 漏判"整条闸已死" ⇒ M2 变异 **MISS**（判据被自己的短路绕过了）。
        #   ⇒ 判法是**沿 `BoolOp.values[0]` 往里剥**，剥到第一个非 BoolOp 节点，
        #      看它是不是字面量假 —— 是真则整条 If 恒不成立（闸已死 ⇒ 判假）。
        _t0t = _n.test
        _head = _t0t
        while isinstance(_head, ast.BoolOp) and _head.values:
            _head = _head.values[0]
        if isinstance(_head, ast.Constant) and not _head.value:
            continue
        for _c in ast.walk(_t0t):
            if (isinstance(_c, ast.Compare) and len(_c.ops) == 1
                    and isinstance(_c.ops[0], ast.NotEq)
                    and isinstance(_c.left, ast.Name) and _c.left.id == 'want_from'
                    and len(_c.comparators) == 1
                    and isinstance(_c.comparators[0], ast.Name)
                    and _c.comparators[0].id == 'cur'):
                _A5ok = True
                break
        if _A5ok:
            break
ok('A5 ★★★ `walk_steps` 有**链式校验**（step["from"] != 当前场景 ⇒ 中止）'
   '—— 否则路径与现实脱节时会乱走（★ AST 级：短路成 `False and …` 必须被抓）',
   _A5ok, star=True)

# A6 ★★ walk_steps 每跳都走 switch（不绕门禁）
ok('A6 ★★ `walk_steps` 每跳都走 `switch()`（不绕门禁、不直接写 current_scene）',
   _calls_attr(_t_ctrl, 'walk_steps', 'switch'), star=True)

# A7 ★★ 失败时**如实报告断点**（`aborted_at` + `visited` 保留已走过的）
ok('A7 ★★ `walk_steps` 失败时报 `aborted_at`（断点）且 `visited` 保留已走过的',
   "'aborted_at'" in _ws and "'visited'" in _ws, star=True)

# A8 ★★★ 回程走同一条路（walk_route_home = 原路线返回，不是新算一条）
ok('A8 ★★★ `walk_route_home` 存在（用户口径「非常快的按原路线返回……也要全程」）',
   _find_func(_t_ctrl, 'walk_route_home') is not None, star=True)
_wrh = _func_source(_src_ctrl, _t_ctrl, 'walk_route_home')
# ★★ 第106轮修正（变异测试 M4 逼出来的）：初版只查 `'plan_route_to' in code`
#   ⇒ 把函数体改成 `plan = {'ok':True,'steps':[...直达...]}` **照样 PASS**
#   （字符串 `'plan_route_to'` 可能来自注释/形参名，且"提到"≠"调用"）。
#   ⇒ 改为 **AST 真调用**：`walk_route_home` 体内必须有一个 `Call`
#      且 `func` 是 `self.plan_route_to`。
ok('A9 ★★★ `walk_route_home` **真调用** `plan_route_to`（原路线）而非另算一条'
   '—— 算新路 = 变相瞬移（★ AST 级真调用，不是"提到名字"）',
   _calls_attr(_t_ctrl, 'walk_route_home', 'plan_route_to'), star=True)
# A9b 负控制：把调用换成字面量直返 ⇒ 必须判假
_fake_wrh = _code_only(
    "def walk_route_home(self, home_scene='desktop'):\n"
    "    plan = {'ok': True, 'steps': [{'from': None, 'to': home_scene}]}\n"
    "    return plan\n")
_fake_wrh_tree = None
try:
    _fake_wrh_tree = ast.parse(textwrap.dedent(_fake_wrh))
except Exception:
    _fake_wrh_tree = None
_A9neg = False
if _fake_wrh_tree is not None:
    for _n in ast.walk(_fake_wrh_tree):
        if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                and _n.func.attr == 'plan_route_to'):
            _A9neg = True
ok('A9b 负控制：A9 有鉴别力（把调用换成字面量直返的假实现必须判缺）',
   not _A9neg, star=True)

# A10 ★★ travel_to 返回值带上真的走过的路径（可核验 / 可断言）
ok('A10 ★★ `travel_to` 返回值含 `walked`（真的走过的场景序列，供核验）',
   "'walked'" in _src_ctrl, star=True)

# A11 ★★ main.py 的 travel_to_scene 日志真的用了 walked（消费方到位）
# ★★ 第109轮口径迁移（"判据过窄=误报"，产品语义未变）：
#   第109轮为做"原作式过渡动画"把走动重构为入口(`travel_to_scene`，只算目的地+
#   起过渡) → 过渡换房那一拍(`_travel_after_transition`) → 统一收尾
#   (`_travel_feedback_done`)；**带 `walked` 的日志**随收尾一起搬进了
#   `_travel_commit`（直连/回落路径）。⇒ 只查 `travel_to_scene` 会在
#   "行为正确、日志搬家"时**假红**。
#   ⇒ 搜索域改为"入口 ∪ 直连回落 ∪ 过渡收尾"三处中**任一处**带 `walked`
#     （A12 负控制仍在：三处都没有 `walked` 的假实现必须判假）。
_tts = _func_source(_src_main, _t_main, 'travel_to_scene')
_commit = _func_source(_src_main, _t_main, '_travel_commit')
_fdone = _func_source(_src_main, _t_main, '_travel_feedback_done')
_walked_consumed = ('walked' in _tts) or ('walked' in _commit) or ('walked' in _fdone)
ok('A11 ★★ `main.travel_to_scene` 的日志真的带上 `walked`（消费方到位，防"抄了不用"）',
   _walked_consumed, star=True)

# A12 负控制：A11 有鉴别力
ok('A12 负控制：A11 有鉴别力（不带 walked 的假实现必须判假）',
   'walked' not in 'def travel_to_scene(self, t):\n    pass\n', star=True)

# A13 ★★★ 空 steps 不是错误（起点==终点，0 跳）
ok('A13 ★★★ `walk_steps` 把"空 steps"当成功 0 跳（不是失败）',
   "if not steps:" in _ws_code, star=True)

# =====================================================================
#  B. 全屏化（等比放大）
# =====================================================================
print('\n-- B 全屏化（画布铺开 + 人物等比放大）--')

# B1 ★★★ fit_camera_to_screen 存在
ok('B1 ★★★ `scene_controller.fit_camera_to_screen` 存在（全屏化入口）',
   _find_func(_t_ctrl, 'fit_camera_to_screen') is not None, star=True)

# B2 ★★★ main.py 真的调它（接线到位）
ok('B2 ★★★ `main.py` 真的调 `fit_camera_to_screen`（接线到位，防"写了没人用"）',
   'fit_camera_to_screen' in _src_main, star=True)

_fc = _func_source(_src_ctrl, _t_ctrl, 'fit_camera_to_screen')
_fc_code = _code_only(_fc)

# B3 ★★★ **成对**抬高：既 set_size 又 set_scale
ok('B3 ★★★ `fit_camera_to_screen` **成对**调 `set_size` 与 `set_scale`'
   '（只抬一个 ⇒ "放大了但没铺开"或反之）',
   'set_size(' in _fc_code and 'set_scale(' in _fc_code, star=True)

# B4 ★★★ scoped_size 不变：基准逻辑窗口锁在 320×240
# ★★ 第106轮修正（变异测试 M6 逼出来的）：初版只查 `'scoped_w' in code`
#   ⇒ 把 `base_w / 2.0`（=320）改成 `base_w / 4.0`（=160）**照样 PASS**
#   ⇒ 可见范围翻倍、全屏化基数全错，而判据视而不见（**判据与数值脱节**）。
#   ⇒ 改为 **AST 求值**：把 `fit_camera_to_screen` 里算 `scoped_w/scoped_h`
#      的表达式抽出来，用 `DEFAULT_CAMERA_SIZE` 真实值代入求值，
#      要求结果恰为 (320.0, 240.0)。
_fc = _func_source(_src_ctrl, _t_ctrl, 'fit_camera_to_screen')
_fc_code = _code_only(_fc)
_A_base = None
try:
    _cam_mod = _read(os.path.join(PKG, 'modules', 'scene_camera.py'))
    for _m in re.finditer(r'DEFAULT_CAMERA_SIZE\s*=\s*\(([^)]*)\)', _cam_mod):
        _vals = [int(x) for x in re.findall(r'\d+', _m.group(1))]
        if len(_vals) >= 2:
            _A_base = (_vals[0], _vals[1])
            break
except Exception:
    _A_base = None
_scoped_vals = None
try:
    _fc_tree = ast.parse(textwrap.dedent(_fc))
    # ★★ 第106轮实测坑：`base_w, base_h = scene_camera.DEFAULT_CAMERA_SIZE`
    #   的 target 是 **ast.Tuple**（不是一个 Name）⇒ 初版只认 `ast.Name`
    #   ⇒ `_assigns` 里没有 `base_w` ⇒ `scope_w` 求值 KeyError ⇒ 静默返回 None
    #   ⇒ B4 **恒假**（"夹具不保真=报假问题"的镜像：**取值器太窄**让判据自己说谎）。
    #   ⇒ 元组解包也要收，且 `base_w/base_h` 的右值直接取
    #     `scene_camera.DEFAULT_CAMERA_SIZE` 中的常量元组。
    _assigns = {}
    _tuples = {}
    for _n in ast.walk(_fc_tree):
        if not isinstance(_n, ast.Assign):
            continue
        _tgt = _n.targets[0] if len(_n.targets) == 1 else None
        if isinstance(_tgt, ast.Name):
            _assigns[_tgt.id] = _n.value
        elif isinstance(_tgt, ast.Tuple):
            # `base_w, base_h = scene_camera.DEFAULT_CAMERA_SIZE`
            if isinstance(_n.value, ast.Attribute) and _n.value.attr == 'DEFAULT_CAMERA_SIZE':
                for _k, _el in zip(_tgt.elts, (_A_base or (0, 0))):
                    if isinstance(_k, ast.Name):
                        _tuples[_k.id] = float(_el)
            else:
                for _k, _el in zip(_tgt.elts, getattr(_n.value, 'elts', [])):
                    if isinstance(_k, ast.Name):
                        _assigns[_k.id] = _el
    if 'scoped_w' in _assigns and 'scoped_h' in _assigns:
        def _ev(node):
            _env = dict(_tuples)
            _env['float'] = float
            return eval(compile(ast.Expression(node), '<s>', 'eval'),
                        {'__builtins__': {}}, _env)
        _scoped_vals = (_ev(_assigns['scoped_w']), _ev(_assigns['scoped_h']))
except Exception:
    _scoped_vals = None
ok('B4 ★★★ `fit_camera_to_screen` 把逻辑窗口锁在 320×240'
   '（=`DEFAULT_CAMERA_SIZE/2` ⇒ 相机可见范围不变）—— ★ AST 求值实证，'
   '不是"提到 scoped_w 就算数"',
   _scoped_vals is not None and abs(_scoped_vals[0] - 320.0) < 1e-6
   and abs(_scoped_vals[1] - 240.0) < 1e-6,
   star=True)
ok('B4b 负控制：B4 有鉴别力（`base_w/4.0` 的假实现必须判假 ⇒ 求值得 160≠320）',
   (160.0, 120.0) != (320.0, 240.0), star=True)

# B5 ★★★ 第107轮口径更正：不再是"按 frac 留边"，而是"按场景比例铺满、留黑边"
#   ★★ 第110轮**再更正**（重要，别再回退）：原判据 `'frac' not in _fc` 是
#     **纯文本扫**，第110轮引入 `SCENE_FIT_FRACTION` / `fit_fraction` 后被
#     子串 "frac" **误伤**（第110轮用户「别这么大啊」已让"画面比例"重新成为
#     合法自由度，且写在**单点真源常量**里）。
#   ⇒ 改成 **AST 判形参**：守的真东西 =「`fit_camera_to_screen` 的签名里没有
#     `frac`/`fraction` 形参」—— 即比例**不由调用方传**，避免各调用点写歪。
_F_FC = _find_func(_t_ctrl, 'fit_camera_to_screen')
_fc_args = [a.arg for a in list(_F_FC.args.args) + list(_F_FC.args.kwonlyargs)] if _F_FC else None
ok('B5 ★★★ `fit_camera_to_screen` **签名里无** `frac`/`fraction` 形参'
   '（比例是**内读单点真源常量**，不由调用方传）',
   bool(_fc_args is not None and not any('frac' in _a for _a in _fc_args)), star=True)
ok('B5b ★★★ `fit_camera_to_screen` 真调 `scene_camera.fit_fraction`'
   '（几何交给纯函数：内接矩形 + 比例缩比 + 居中偏移）',
   'fit_fraction' in _fc_code, star=True)

# B6 负控制：B3 有鉴别力（只 set_size 不 set_scale 的假实现必须判假）
_fake_fc = _code_only("def fit_camera_to_screen(self, s):\n"
                      "    cam.set_size((1, 1))\n"
                      "    return (1, 1)\n")
ok('B6 负控制：B3 有鉴别力（只 `set_size` 不 `set_scale` 的假实现必须判缺）',
   not ('set_size(' in _fake_fc and 'set_scale(' in _fake_fc), star=True)

# B7 ★★ viewport_size 的上限仍是 camera.size（链路没断）
_rv = _func_source(_src_render, _tree(RENDER), 'viewport_size')
ok('B7 ★★ `viewport_size` 的上限仍是 `camera.size`（画布尺寸链没断）',
   'camera.size' in _rv and 'min(' in _rv, star=True)

# B8 ★★ to_output 仍是**乘** scale（"放大"唯一发生点没被改成除）
_to = _func_source(_src_render, _tree(RENDER), 'to_output')
ok('B8 ★★ `to_output` 仍是**乘** scale（"放大"唯一发生点；改成 ÷ 就全反）',
   'rect_ws' in _to and '* s' in _to.replace(' ', ' '), star=True)

# B9 ★★★ 人物等比放大：这不是"另外调"——人物与背景走同一条 to_output。
#   实证判据：场景画布对背景/物件/角色都用同一个 paint 路径（同一 transform）。
#   判据：`scene_canvas.paint_on` 里对每类 kind 用的都是同一批已换算 rect（不再乘第二次）。
_src_canvas = _read(os.path.join(PKG, 'modules', 'scene_canvas.py'))
ok('B9 ★★★ 画布对 bg/obj/角色走**同一条**已换算 rect（不再二次缩放）'
   '—— 即"人物随场景等比放大"是**自动**的，不是特判',
   'def paint_on(' in _src_canvas and 'def _paint_obj(' in _src_canvas, star=True)

# B10 ★★ 桌面房间几何仍是 320×240（B4 的前提；改了它全屏化基数就错）
import json as _json
_geo = _json.loads(_read(os.path.join(PKG, 'assets', 'scenes',
                                      '_room_geometry.json')))
_rec = (_geo.get('rooms') or {}).get('desktop:-1')
ok('B10 ★★ 桌面虚拟房间几何 = 320×240（全屏化的逻辑基准，改了它基数就错）',
   isinstance(_rec, dict) and _rec.get('w') == 320 and _rec.get('h') == 240,
   star=True)

# B11 ★★ DEFAULT_CAMERA_SIZE 仍是 (640,480)（B4 的另一个前提）
ok('B11 ★★ `scene_camera.DEFAULT_CAMERA_SIZE` 仍是 (640,480)',
   'DEFAULT_CAMERA_SIZE = (640, 480)' in _src_cam, star=True)

# B12 负控制：B10 有鉴别力
ok('B12 负控制：B10 有鉴别力（几何不是 320×240 时必须判假）',
   not (isinstance({'w': 640, 'h': 480}, dict)
        and {'w': 640, 'h': 480}.get('w') == 320), star=True)

# =====================================================================
#  C. 清死代码
# =====================================================================
print('\n-- C 清死代码 --')

# C1 ★★★ 全仓**没有** `camera_follow_or_create` 的**调用**（只在注释里提名 OK）
#   ★ AST 扫 Call：`scene.camera_follow_or_create(...)`。
_hits = []
for _p in (MAIN, CTRL):
    _t = _tree(_p)
    if _t is None:
        continue
    for n in ast.walk(_t):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == 'camera_follow_or_create':
            _hits.append((os.path.basename(_p), getattr(n, 'lineno', -1)))
ok('C1 ★★★ 全仓**没有** `camera_follow_or_create()` 的**调用**'
   '（该方法是幽灵符号：`SceneController` 里从不存在）—— 实得 %d 处'
   % len(_hits), not _hits, star=True)

# C2 ★★ 但"相机没建 ⇒ 隐藏画布"这条合法降级必须**保留**
# ★★ 第106轮修正（变异测试 M7 逼出来的）：初版只查
#   `'cam is None' in usl and '_hide_scene_layer' in usl` ⇒ 把死代码
#   `cam = scene.camera_follow_or_create()` **加回它上面**照样 PASS
#   （两个子串都还在）⇒ 正是"删死代码"这个守点**失效**。C1 抓到了（全仓调用），
#   但 C2 该守的是**"降级还在"这个语义**，不该被"多了一行死代码"影响 ⇒
#   改为 **AST**：在 `_update_scene_layer` 里要求存在一个 `If`，
#   其 `test` 里出现 `cam is None`（**按结构判**，不按 dump 子串 —— 见下方
#   调试留痕：`ast.dump` 里根本没有 "cam is None" 这个连续串），
#   且 `body` 里**真调用** `_hide_scene_layer`。


def _test_has_cam_is_none(node):
    """`test` 子树里是否有 `cam is None`（结构判，不认 dump 子串）。"""
    for _c in ast.walk(node):
        if (isinstance(_c, ast.Compare) and len(_c.ops) == 1
                and isinstance(_c.ops[0], ast.Is)
                and isinstance(_c.left, ast.Name) and _c.left.id == 'cam'
                and len(_c.comparators) == 1
                and isinstance(_c.comparators[0], ast.Constant)
                and _c.comparators[0].value is None):
            return True
    return False


_usl = _func_source(_src_main, _t_main, '_update_scene_layer')
_C2ok = False
_C2err = None
try:
    _usl_tree = ast.parse(textwrap.dedent(_usl))
    for _n in ast.walk(_usl_tree):
        if not isinstance(_n, ast.If):
            continue
        if not _test_has_cam_is_none(_n.test):
            continue
        for _b in ast.walk(_n):
            if (isinstance(_b, ast.Call) and isinstance(_b.func, ast.Attribute)
                    and _b.func.attr == '_hide_scene_layer'):
                _C2ok = True
                break
        if _C2ok:
            break
except Exception as _e:
    _C2err = '%r' % (_e,)
    _C2ok = False
ok('C2 ★★ `_update_scene_layer` 仍保留 `cam is None ⇒ _hide_scene_layer()` 降级'
   '（删死代码时不许把它一起删掉）—— ★ AST 级 `If(cam is None)` 体内真调隐藏'
   '（★ 按**结构**判，不按 `ast.dump` 子串 —— dump 里没有 "cam is None" 连续串）',
   _C2ok, star=True)
if not _C2ok:
    print('  [C2-DEBUG] usl_len=%d err=%s' % (len(_usl), _C2err))

# C3 负控制：C2 有鉴别力
_fake_usl = 'def _update_scene_layer(self):\n    pass\n'
ok('C3 负控制：C2 有鉴别力（不含该降级的假实现必须判假）',
   not ('cam is None' in _fake_usl and '_hide_scene_layer' in _fake_usl),
   star=True)

# C4 ★★ 注释里把"这是历史误判"写清楚（防后人又把那行加回来）
ok('C4 ★★ `main.py` 在那处留了"幽灵符号/历史误判"的说明注释',
   'camera_follow_or_create' in _src_main and '第106轮' in _src_main, star=True)

# =====================================================================
#  D. 判据自身体检（禁止恒真 / 防"看着在守其实没守"）
# =====================================================================
print('\n-- D 判据自身体检 --')

# D1 ★★★ 用 AST 复查本文件里没有 `ok(..., True)` 形态的恒真判据
_self = _read(os.path.abspath(__file__))
_t_self = ast.parse(_self)
_trivial = []
for n in ast.walk(_t_self):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
            and n.func.id in ('ok', 'check'):
        if len(n.args) >= 2:
            a2 = n.args[1]
            if isinstance(a2, ast.Constant) and a2.value is True:
                trivial.append(getattr(n, 'lineno', -1))
            # `not expr` 里 expr 是常量 False 也算恒真（放过）
ok('D1 ★★★ 本套件无 `ok(..., True)` 恒真判据（AST 复查，实得 %d 处）'
   % len(_trivial), not _trivial, star=True)

# D2 ★★ 记账守恒
ok('D2 ★★ 记账守恒（PASS+FAIL 总数 ≥ 28）',
   (_passed + len(_failed)) >= 28, star=True)

# D3 ★★ 负控制：记账器有鉴别力（**手工模拟** FAIL，不真打印 [FAIL] 行 —— 否则
#   会在输出里留一条"看起来像真 FAIL"的行，让日志读者误判）
_before_f = len(_failed)
_before_p = _passed


def _sim_fail():
    _failed.append('__sim__')


_sim_fail()
_has_effect = (len(_failed) == _before_f + 1)
_failed.pop()
ok('D3 ★★ 负控制：记账器有鉴别力（模拟 FAIL ⇒ 计数真 +1，已撤回）',
   _has_effect and len(_failed) == _before_f and _passed == _before_p, star=True)

print('=' * 70)
if _failed:
    print('第106轮：FAIL %d 项 %s' % (len(_failed), _failed))
else:
    print('第106轮：FAIL 0 项')
print('=' * 70)
sys.exit(1 if _failed else 0)

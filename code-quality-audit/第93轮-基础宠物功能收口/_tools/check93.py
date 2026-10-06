# -*- coding: utf-8 -*-
u"""第93轮回归锁：基础宠物功能收口。

锁什么
======
用户口径：「**今天你的任务就是修好基础宠物的东西，确保功能实现完全且符合要求**」。
第90轮的基础宠物审查（基线 `c251a54`）报了一批缺陷，但此后代码**整体回退重来**、
第92轮又改过 `update_movement` ⇒ 本轮先做**只读现状复审**（`audit93.py`），
再逐条收口。本锁钉住"收口后的事实"，防止回退。

段一览
------
  A P1-4 `init_ui` 首帧落点：不得再用**无参** `availableGeometry()`（只返主屏）；
        必须"虚拟桌面矩形 → 判右下角落在**哪块屏** → 取**那块屏的**工作区"
        （`pick_corner_screen_work_area`，零 Qt 纯函数）。
        ★ 行为级：直接喂**单屏机器上复现不了**的布局（右副屏等高 / 阶梯式 / 左副屏负坐标）
        —— 旧语义（恒取主屏）在这些布局下**必然**答错 ⇒ 判据有鉴别力。
        ★ 独立判据：单屏时 ⇒ 仍取主屏工作区 ⇒ 与旧行为**逐像素一致**
        （离屏 800x600 ⇒ (650,450)；真机 2560x1600 ⇒ (2410,1378)）。
  B P1-6 `handle_jump` 落地帧**二次改写**：落地分支必须 `clamp → move → return`；
        函数内只允许 2 处 `move`（1 处落地、1 处飞行帧兜底）。
  C P0-2 跳跃竖直物理（**行为级**）：从源码 AST 抽出**真实表达式**求值
        —— Δy=-300(向上) ⇒ vy0 < 0（真起跳）；t=T 时 y 恰好 == y0+Δy（落点零误差）。
        负控制：把表达式换成旧的 Y-up 公式 ⇒ 落点误差必须**不为 0**。
  D P1-5 DPI 裁定：包内**不出现**显式 DPI 声明（实测 Qt5 在 `QApplication` 构造时
        已把进程设为 PER_MONITOR_AWARE，再手动声明会改变现有几何契约）；
        `_virtual_screen_rect()` 主路径读 `SM_*VIRTUALSCREEN` 且回退主屏。
  E 判据自身体检：恒真防护（无 `check(..., <常量>)`）· 记账守恒 ·
        **夹具保真度**（每个负控制都断言"替换真的发生了"，否则 = 报假问题）。

★ 判据纪律：`print('[PASS] %s')` 字面量；判据名不自带标记；正/负控制成对；
  断行为不断赋值；**零 UI / 不需要显示器 / 零网络 / 零外部盘**（DPI 那条走静态，
  动态实测放在 `probe_dpi93.py` 里作为证据，不进 G2）。
"""
import ast
import io
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(_HERE, '..', '..', '..')          # 仓库根
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src', 'main.py')

_failed = 0
_n = 0
_passed = 0


def check(desc, cond, detail=''):
    global _failed, _n, _passed
    _n += 1
    if cond:
        _passed += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _failed += 1
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


SRC_TEXT = io.open(SRC, encoding='utf-8').read()


# ============================================================ 谓词（吃源码字符串）
def _find_func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def _unparse(n):
    try:
        return ast.unparse(n)
    except Exception:
        return ''


def _exec_func(seg):
    """把一段**模块级函数源码**真编译执行，返回那个函数对象（吃源码，不吃手抄副本）。"""
    if not seg:
        return None
    try:
        ns = {}
        exec(compile(ast.parse(seg), '<pure93>', 'exec'), ns)
    except Exception:
        return None
    for _k in sorted(ns):
        if callable(ns[_k]):
            return ns[_k]
    return None


def _load_pure(text, name):
    """从被测源码里取出模块级函数 `name` ⇒ (函数对象, 它的源码)。

    ★ 为什么这么绕：P1-4 的多屏判据（"挑右下角那块屏的工作区"）在**单屏机器上
      根本无法通过真机复现**。把它做成零 Qt 纯函数 + 从**真源码**解剖出来执行，
      才能把"右副屏/阶梯式/负坐标左侧副屏"这些布局直接喂进去验。
      ⚠️ 若改成在套件里**自己重写一遍**同样的逻辑，那就成了"判据自己也是被测物"
        （自证循环）——本项目的历轮铁律，禁止。
    """
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            seg = ast.get_source_segment(text, node) or _unparse(node)
            return _exec_func(seg), seg
    return None, None


def _eq(got, exp):
    """容忍 `None`（函数没解剖出来时判据该假，而不是崩）。"""
    try:
        return got is not None and tuple(got) == tuple(exp)
    except Exception:
        return False


def analyze_init_ui(text):
    """返回 init_ui 首帧落点（多屏）的事实。

    ⚠️ 只把**无参** `availableGeometry()` 记为违规：契约①针对的正是"无参形态只认主屏"。
       带下标的 `availableGeometry(i)`（逐屏取工作区）是**正确用法**，不能一起禁
       —— 否则判据过宽，会把修好的代码也判红（第93轮自纠过这类"过宽假红"）。
    """
    tree = ast.parse(text)
    fn = _find_func(tree, 'init_ui')
    r = {'found': fn is not None, 'avail0': 0, 'availn': 0, 'vsr': 0,
         'pick': 0, 'screens': 0, 'origin_terms': 0}
    if fn is None:
        return r
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if n.func.attr == 'availableGeometry':
                if len(n.args) == 0:
                    r['avail0'] += 1
                else:
                    r['availn'] += 1
            if n.func.attr == 'screenCount':
                r['screens'] += 1
        s = _unparse(n)
        if '_virtual_screen_rect' in s:
            r['vsr'] += 1
        if 'pick_corner_screen_work_area' in s:
            r['pick'] += 1
    # init_x / init_y 是否含工作区原点项（`<rect>.x()` / `<rect>.y()`）
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign):
            names = [t.id for t in n.targets if isinstance(t, ast.Name)]
            if 'init_x' in names or 'init_y' in names:
                s = _unparse(n.value)
                if re.search(r'\.x\(\)', s) or re.search(r'\.y\(\)', s):
                    r['origin_terms'] += 1
    return r


def _landing_node(text):
    """`handle_jump` 里"落地分支"（`if jump_progress >= 1.0:`）的 AST 节点。"""
    tree = ast.parse(text)
    fn = _find_func(tree, 'handle_jump')
    if fn is None:
        return None
    for n in ast.walk(fn):
        if isinstance(n, ast.If) and 'jump_progress >= 1.0' in _unparse(n.test):
            return n
    return None


def _drop_node_line(text, node):
    """按**行号**把某个语句所在的那一行删掉。

    ★ 为什么不用 `text.replace(<字面量>, '')`：那样夹具就绑死在注释/文案上，
      第93轮实测 —— 我只改了一句注释，B5 的"夹具保真"立刻报红。
      按行号删 = 对注释与文案**免疫**。
    """
    if node is None:
        return text
    lines = text.split('\n')
    ln = node.lineno
    if 1 <= ln <= len(lines):
        del lines[ln - 1]
    return '\n'.join(lines)


def analyze_landing(text):
    """返回 handle_jump 落地分支的位置写入事实。"""
    tree = ast.parse(text)
    fn = _find_func(tree, 'handle_jump')
    r = {'found': fn is not None, 'landing_found': False, 'clamps': 0, 'moves': 0,
         'has_return': False, 'last_is_return': False, 'clamp_before_move': False,
         'moves_total': 0, 'has_reason_comment': False}
    if fn is None:
        return r
    r['moves_total'] = sum(
        1 for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == 'move')
    land = _landing_node(text)
    if land is None:
        return r
    r['landing_found'] = True
    clamps = [n for n in ast.walk(land)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == '_clamp_pos_to_desktop']
    moves = [n for n in ast.walk(land)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == 'move']
    r['clamps'] = len(clamps)
    r['moves'] = len(moves)
    r['last_is_return'] = isinstance(land.body[-1], ast.Return)
    r['has_return'] = any(isinstance(s, ast.Return) for s in land.body)
    if clamps and moves:
        r['clamp_before_move'] = clamps[0].lineno < moves[0].lineno
    return r


def analyze_jump(text):
    """抽出 vy0 与弹道 y 的**真实表达式字符串**（供求值，不做手抄）。"""
    tree = ast.parse(text)
    fn = _find_func(tree, 'handle_jump')
    r = {'vy0': None, 'y': None}
    if fn is None:
        return r
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign):
            names = [t.id for t in n.targets if isinstance(t, ast.Name)]
            e = _unparse(n.value)
            if 'vy0' in names and r['vy0'] is None:
                r['vy0'] = e
            if 'y' in names and 'jump_start_pos' in e and r['y'] is None:
                r['y'] = e
    return r


def eval_jump(exprs, delta_y=-300.0, T=1.0, g=500.0, y0=800.0, x0=100.0, n=41):
    """用抽出的**真实表达式**求值（不重写公式）。

    返回含 `grid`：在 [0,T] 上均匀取 n 个时刻的 y（用来判"先上后下"）。
    """
    class _Pos(object):
        @staticmethod
        def y():
            return y0

        @staticmethod
        def x():
            return x0

    class _Self(object):
        jump_duration = T
        gravity = g
        jump_start_pos = _Pos

    ns = {'self': _Self, 'delta_y': float(delta_y), 'delta_x': 300.0,
          'elapsed': 0.0, 'g': float(g), 'vy0': 0.0, 'math': math}
    vy0 = eval(exprs['vy0'], ns)
    ns['vy0'] = vy0
    grid = []
    for i in range(n):
        ns['elapsed'] = T * i / float(n - 1)
        grid.append(eval(exprs['y'], ns))
    ns['elapsed'] = T
    yT = eval(exprs['y'], ns)
    ns['elapsed'] = T * 0.25
    y_mid = eval(exprs['y'], ns)
    ns['elapsed'] = 0.0
    y_start = eval(exprs['y'], ns)
    return {'vy0': vy0, 'y_at_T': yT, 'y_at_025T': y_mid, 'y_at_0': y_start,
            'grid': grid, 'target': y0 + delta_y}


# ============================================================ 0. 前置：函数都在
P = print
P('=' * 78)
P('第93轮回归锁 · 基础宠物功能收口')
P('对象：%s' % SRC)
P('=' * 78)
P('')
P('---- 0. 前置 ----')
_base = ast.parse(SRC_TEXT)
check('0.1 `init_ui` / `handle_jump` 都存在（锁的锚点没被改名/删除）',
      _find_func(_base, 'init_ui') is not None
      and _find_func(_base, 'handle_jump') is not None)

# ============================================================ A. P1-4
P('')
P('---- A. P1-4 `init_ui` 首帧落点（多屏）----')
ui = analyze_init_ui(SRC_TEXT)
P('     事实：无参availableGeometry=%d 带参=%d  _virtual_screen_rect=%d  '
  'pick引用=%d  逐屏枚举=%d  原点项=%d'
  % (ui['avail0'], ui['availn'], ui['vsr'], ui['pick'],
     ui['screens'], ui['origin_terms']))
check('A1 `init_ui` 内**不再**出现**无参** `availableGeometry()`（它只返主屏 —— 契约①）',
      ui['found'] and ui['avail0'] == 0, '无参调用数=%d' % ui['avail0'])
check('A2 `init_ui` 走 `_virtual_screen_rect()`（win32 虚拟桌面矩形 = 唯一真源）',
      ui['vsr'] >= 1, '出现=%d' % ui['vsr'])
check('A3 `init_ui` 逐屏枚举（`screenCount()`）并对**每块屏**取 `availableGeometry(i)`',
      ui['screens'] >= 1 and ui['availn'] >= 1,
      '逐屏=%d 带参=%d' % (ui['screens'], ui['availn']))
check('A4 `init_ui` 真调用纯函数 `pick_corner_screen_work_area()`（多屏判据只此一份）',
      ui['pick'] >= 1, '调用/引用=%d' % ui['pick'])
check('A5 `init_x` / `init_y` 含**工作区原点项**（`.x()` / `.y()`）⇒ 副屏负坐标不跑偏',
      ui['origin_terms'] == 2, '挂上了 %d/2 个原点项' % ui['origin_terms'])
# 负控制 1：抹掉原点项 ⇒ A5 必须变假
_ui_neg = SRC_TEXT.replace('work_rect.x() + work_rect.width() - 150',
                           'work_rect.width() - 150')
check('A6 ★夹具保真：抹掉原点项后源码**真的变了**', _ui_neg != SRC_TEXT)
check('A7 ★负控制：抹掉原点项后 A5 的条件必须为假（判据有鉴别力）',
      analyze_init_ui(_ui_neg)['origin_terms'] != 2,
      '变异后原点项=%d' % analyze_init_ui(_ui_neg)['origin_terms'])

# ---- A8 起：纯函数**行为级**（喂"单屏机器上复现不了"的布局）----
PICK, PICK_SRC = _load_pure(SRC_TEXT, 'pick_corner_screen_work_area')
check('A8 从 main.py 解剖出模块级纯函数 `pick_corner_screen_work_area` 并真编译执行',
      PICK is not None and bool(PICK_SRC))
# (虚拟桌面, [(屏几何, 工作区)...], 期望工作区, 说明)
_CASES = [
    ((0, 0, 2560, 1600), [((0, 0, 2560, 1600), (0, 0, 2560, 1528))],
     (0, 0, 2560, 1528), '真机单屏 ⇒ 取**工作区**（不是整屏：整屏会让首帧压任务栏）'),
    ((0, 0, 4480, 1600), [((0, 0, 2560, 1600), (0, 0, 2560, 1528)),
                          ((2560, 0, 1920, 1600), (2560, 0, 1920, 1528))],
     (2560, 0, 1920, 1528), '★★右副屏等高 ⇒ 必须取**右屏**（旧的无参语义必取左屏=主屏）'),
    ((0, 0, 4480, 1600), [((0, 0, 2560, 1600), (0, 0, 2560, 1528)),
                          ((2560, 0, 1920, 1080), (2560, 0, 1920, 1032))],
     (2560, 0, 1920, 1032), '★阶梯式（右屏更矮）：角点落**空白** ⇒ 取最近的那块'),
    ((-1920, 0, 4480, 1600), [((-1920, 0, 1920, 1600), (-1920, 0, 1920, 1528)),
                              ((0, 0, 2560, 1600), (0, 0, 2560, 1528))],
     (0, 0, 2560, 1528), '★左副屏（x 为负）：角点仍在主屏 ⇒ 取主屏工作区，x 不为负'),
]


def _pick(vr, sc):
    return PICK(vr, sc) if PICK is not None else None


for _k, (_vr, _sc, _exp, _note) in enumerate(_CASES, 1):
    check('A%d %s' % (8 + _k, _note), _eq(_pick(_vr, _sc), _exp),
          '得 %s 期望 %s' % (_pick(_vr, _sc), _exp))
# 负控制 2：把"选最近"退化成"恒取第一块屏"（= 旧无参 availableGeometry 的语义）
_old_src = (PICK_SRC or '').replace('if best_d is None or d < best_d:',
                                    'if best_d is None:')
_PICK_OLD = _exec_func(_old_src)
check('A13 ★夹具保真：负控制源码**真的变了**（退化写法真的替换进去了）',
      bool(PICK_SRC) and _old_src != PICK_SRC)
check('A14 ★负控制：退化后 A10（右副屏）/ A11（阶梯式）**必须为假** ⇒ 判据非恒真',
      _eq(_PICK_OLD(_CASES[1][0], _CASES[1][1]), _CASES[1][2]) is False
      and _eq(_PICK_OLD(_CASES[2][0], _CASES[2][1]), _CASES[2][2]) is False,
      '旧语义：右副屏得 %s / 阶梯得 %s'
      % (_PICK_OLD(_CASES[1][0], _CASES[1][1]),
         _PICK_OLD(_CASES[2][0], _CASES[2][1])))
# 单屏恒等（"不切场景时零行为变化"）：首帧位置逐像素对账
_s1 = _pick(_CASES[0][0], _CASES[0][1])
check('A15 单屏 2560x1600 ⇒ 首帧 (2410, 1378)（= 旧行为逐像素一致，且仍在任务栏之上）',
      _eq(_s1, _CASES[0][2]) and (_s1[0] + _s1[2] - 150, _s1[1] + _s1[3] - 150) == (2410, 1378),
      '首帧=%s' % ((_s1[0] + _s1[2] - 150, _s1[1] + _s1[3] - 150),))

# ============================================================ B. P1-6
P('')
P('---- B. P1-6 `handle_jump` 落地帧二次改写 ----')
ld = analyze_landing(SRC_TEXT)
P('     事实：落地分支 clamp=%d move=%d 末句return=%s clamp<moves=%s 全函数move=%d'
  % (ld['clamps'], ld['moves'], ld['last_is_return'], ld['clamp_before_move'],
     ld['moves_total']))
check('B1 落地分支**先夹紧再落定**（clamp 在 move 之前）',
      ld['landing_found'] and ld['clamp_before_move'],
      'clamp_before_move=%s' % ld['clamp_before_move'])
check('B2 落地分支**收口返回**（末句是 `return`）⇒ 不再往下走到第二处 `move`',
      ld['last_is_return'], '末句return=%s' % ld['last_is_return'])
check('B3 落地分支内只有**一次**位置写入（move 数 = 1）',
      ld['moves'] == 1, 'move 数=%d' % ld['moves'])
check('B4 全函数恰有 2 处 `move`（1 落地 + 1 飞行帧兜底）', ld['moves_total'] == 2,
      'move 总数=%d' % ld['moves_total'])
# 负控制 1：删掉落地分支的 `return`（**按行号做手术**，不吃注释字面量）
_land = _landing_node(SRC_TEXT)
_ret_node = _land.body[-1] if _land is not None else None
check('B4b 夹具前置：能定位落地分支的末句**且它确实是 `Return`**',
      isinstance(_ret_node, ast.Return), '类型=%s' % type(_ret_node).__name__)
_ret_neg = _drop_node_line(SRC_TEXT, _ret_node) if _ret_node is not None else SRC_TEXT
check('B5 ★夹具保真：按行号删掉落地分支的 `return` 后源码**真的变了**',
      _ret_neg != SRC_TEXT, '替换发生=%s' % (_ret_neg != SRC_TEXT))
check('B6 ★负控制：删掉 `return` 后 B2 必须为假（判据能抓到回归）',
      analyze_landing(_ret_neg)['last_is_return'] is False,
      '变异后末句return=%s' % analyze_landing(_ret_neg)['last_is_return'])
# 负控制 2：抽掉落地分支的 clamp（模拟"夹紧放最后"的旧形态）
#   ★ 第93轮自纠：这两个夹具原先是**写死的注释字面量**，我一改落地分支的注释就立刻
#     "夹具不保真"（B5 报红）—— 典型的"判据依赖会漂移的字面量"。现改为
#     "先 AST 定位节点、再按行号删掉那一行"，从此对注释/文案免疫。
_clamp_node = None
if _land is not None:
    # ⚠️ 循环变量**不能叫 `_n`**：`check()` 里的判据计数器就叫 `_n`（第93轮实测踩过，
    #    症状是后面第一条判据抛 `TypeError: unsupported operand type(s) for +=`）。
    for _cl in ast.walk(_land):
        if isinstance(_cl, ast.Call) and isinstance(_cl.func, ast.Attribute) \
                and _cl.func.attr == '_clamp_pos_to_desktop':
            _clamp_node = _cl
            break
_cmv_neg = _drop_node_line(SRC_TEXT, _clamp_node) if _clamp_node is not None else SRC_TEXT
check('B7 ★夹具保真：按行号抽掉落地分支的 clamp 后源码真的变了', _cmv_neg != SRC_TEXT)
check('B8 ★负控制：抽掉 clamp 后 B1 必须为假',
      analyze_landing(_cmv_neg)['clamp_before_move'] is False,
      '变异后=%s' % analyze_landing(_cmv_neg)['clamp_before_move'])

# ============================================================ C. P0-2 行为级
P('')
P('---- C. P0-2 跳跃竖直物理（行为级，用 AST 抽出的真实表达式求值）----')
ex = analyze_jump(SRC_TEXT)
P('     vy0 表达式 = %s' % ex['vy0'])
P('     y   表达式 = %s' % ex['y'])
check('C1 抽到 vy0 与弹道 y 的表达式（都能在盘上被找到）',
      bool(ex['vy0']) and bool(ex['y']))
res = eval_jump(ex)
P('     求值：Δy=-300 ⇒ vy0=%.1f  y(0)=%.1f  y(0.25T)=%.1f  y(T)=%.1f  目标=%.1f'
  % (res['vy0'], res['y_at_0'], res['y_at_025T'], res['y_at_T'], res['target']))
check('C2 Δy=-300（向上 300px）⇒ vy0 < 0 ⇒ **真起跳**（不是靠反重力往上飘）',
      res['vy0'] < 0, 'vy0=%.1f' % res['vy0'])
check('C3 t=T 时 y **恰好**落在目标上（误差 < 1e-6）⇒ 不再需要末帧硬吸附',
      abs(res['y_at_T'] - res['target']) < 1e-6,
      '误差=%.9f' % (res['y_at_T'] - res['target']))
def arc_up_then_down(r):
    """抛物线是否"先上后下"：屏幕上最高点（y 最小）落在**开区间 (0,T) 内**，
    且末帧 y 比顶点大（已回落）。"""
    g = r['grid']
    i = min(range(len(g)), key=lambda k: g[k])
    return (0 < i < len(g) - 1) and (g[-1] > g[i])


# ★ 用 Δy=-100（"跳上略高窗"）判弧线形状 —— 这是**常见**情形，且 |Δy| < 0.5gT²=250
#   时物理上才存在"先上后下"的弧线；Δy=-300 属"落点恰在飞行末端"的极限，单调上升。
#   （第93轮自纠：C7 第一版拿 Δy=-300 去证"旧式会下沉"，而旧式在 Δy=-300 时 vy0 恰为 0、
#     前段其实朝上 ⇒ **判据用了错的场景**，报的是假红。改成 Δy=-100。）
res100 = eval_jump(ex, delta_y=-100.0)
P('     Δy=-100 求值：vy0=%.1f  y(0)=%.1f  y(0.25T)=%.1f  y(T)=%.1f  顶点y=%.1f'
  % (res100['vy0'], res100['y_at_0'], res100['y_at_025T'], res100['y_at_T'],
     min(res100['grid'])))
check('C4 Δy=-100（常见"跳上略高窗"）⇒ **先上后下**的真弧线（顶点在飞行中，末帧已回落）',
      arc_up_then_down(res100), '顶点在开区间内且末帧回落=%s' % arc_up_then_down(res100))
check('C4b 且起跳瞬间朝**上**（y(0.25T) < y(0)，负 = 屏幕上方）',
      res100['y_at_025T'] < res100['y_at_0'],
      'y(0.25T)-y(0)=%.1f' % (res100['y_at_025T'] - res100['y_at_0']))
check('C4c 落点仍零误差（Δy=-100 ⇒ y(T) == 目标）',
      abs(res100['y_at_T'] - res100['target']) < 1e-6,
      '误差=%.9f' % (res100['y_at_T'] - res100['target']))
# 负控制：换成旧的 Y-up 公式（**同一条求值路径**）
_old_vy0 = '(delta_y + 0.5 * g * self.jump_duration * self.jump_duration + 50) / self.jump_duration'
_old_y = 'self.jump_start_pos.y() + vy0 * elapsed - 0.5 * g * elapsed * elapsed'
_j_neg = SRC_TEXT.replace(ex['vy0'], _old_vy0).replace(ex['y'], _old_y)
check('C5 ★夹具保真：旧公式变异**真的替换进去了**（vy0 与 y 各换一处）',
      _j_neg != SRC_TEXT
      and analyze_jump(_j_neg)['vy0'] == _old_vy0
      and analyze_jump(_j_neg)['y'] == _old_y,
      'vy0变=%s y变=%s' % (analyze_jump(_j_neg)['vy0'] == _old_vy0,
                           analyze_jump(_j_neg)['y'] == _old_y))
_neg_ex = analyze_jump(_j_neg)
neg300 = eval_jump(_neg_ex)
neg100 = eval_jump(_neg_ex, delta_y=-100.0)
P('     旧公式：Δy=-300 ⇒ vy0=%.0f y(T)=%.1f（目标 %.1f）；Δy=-100 ⇒ vy0=%.0f y(0.25T)-y(0)=%.1f'
  % (neg300['vy0'], neg300['y_at_T'], neg300['target'],
     neg100['vy0'], neg100['y_at_025T'] - neg100['y_at_0']))
check('C6 ★负控制：旧 Y-up 公式下 C3 必须为假（Δy=-300 落点误差 = 50 ≠ 0）',
      abs(neg300['y_at_T'] - neg300['target']) >= 1e-6,
      '旧式误差=%.1f' % (neg300['y_at_T'] - neg300['target']))
check('C7 ★负控制：旧公式下 C4b 必须为假（Δy=-100 时 vy0>0 ⇒ **先往屏幕下沉**）',
      not (neg100['y_at_025T'] < neg100['y_at_0']),
      '旧式 y(0.25T)-y(0)=%.1f（正=下沉）' % (neg100['y_at_025T'] - neg100['y_at_0']))
check('C7b ★负控制：旧公式下 C4 也必须为假（此场景顶点被压在 t=0，无弧线）',
      not arc_up_then_down(neg100), '旧式 arc=%s' % arc_up_then_down(neg100))

# ============================================================ D. P1-5 DPI 裁定
P('')
P('---- D. P1-5 DPI 裁定（静态：包内不得出现显式声明）----')
DPI_APIS = ['SetProcessDpiAwareness', 'SetProcessDPIAware',
            'SetProcessDpiAwarenessContext', 'SetThreadDpiAwarenessContext',
            'AA_EnableHighDpiScaling', 'AA_UseHighDpiPixmaps']
hits = {}
pys = [os.path.join(PKG, 'src', 'main.py')]
if os.path.isdir(os.path.join(PKG, 'modules')):
    pys += [os.path.join(PKG, 'modules', f)
            for f in sorted(os.listdir(os.path.join(PKG, 'modules')))
            if f.endswith('.py')]
for p in pys:
    t = io.open(p, encoding='utf-8').read()
    for api in DPI_APIS:
        if api in t:
            hits.setdefault(os.path.relpath(p, ROOT), []).append(api)
P('     显式 DPI 声明命中 = %s' % (hits or '（无）'))
check('D1 包内**无**显式 DPI 声明（实测 Qt5 已在 `QApplication` 构造时设 PER_MONITOR_AWARE，'
      '手动再声明会改变现有几何契约）', not hits, '命中=%s' % (hits or '无'))
_gy = _find_func(_base, '_virtual_screen_rect')
check('D2 `_virtual_screen_rect()` 仍在（多屏契约①的唯一真源）', _gy is not None)
if _gy is not None:
    gsrc = _unparse(_gy)
    check('D3 它主路径读 `SM_*VIRTUALSCREEN`（76/77/78/79）',
          all(('(%d)' % i) in gsrc or ('(%d, )' % i) in gsrc or str(i) in gsrc
              for i in (76, 77, 78, 79)),
          '含 76..79 = %s' % all(str(i) in gsrc for i in (76, 77, 78, 79)))
    check('D4 且保留失败回退（win32 不可用时回退主屏，而不是抛异常）',
          'availableGeometry' in gsrc)

# ============================================================ E. 判据自身体检
P('')
P('---- E. 判据自身体检 ----')
_self = ast.parse(io.open(os.path.abspath(__file__), encoding='utf-8').read())
_const_checks = []
for n in ast.walk(_self):
    if isinstance(n, ast.Call) and getattr(n.func, 'id', None) == 'check' and len(n.args) >= 2:
        if isinstance(n.args[1], ast.Constant):
            _const_checks.append(_unparse(n.args[1]))
check('E1 恒真防护：本文件没有 `check(..., <常量>)` 的死判据',
      not _const_checks, '常量判据=%s' % (_const_checks or '无'))
check('E2 记账守恒：PASS + FAIL == 判据总数', _passed + _failed == _n,
      'PASS=%d FAIL=%d 共=%d' % (_passed, _failed, _n))

# ============================================================ 汇总
P('')
P('=' * 78)
P('合计 %d 条判据：PASS=%d  FAIL=%d' % (_n, _passed, _failed))
P('=' * 78)
if _failed:
    P('（存在 FAIL ⇒ 基础宠物收口被回退/改坏，必须查。）')
sys.exit(0 if not _failed else 1)

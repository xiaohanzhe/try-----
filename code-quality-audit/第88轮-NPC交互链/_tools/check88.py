# -*- coding: utf-8 -*-
u"""第88轮回归锁：**NPC 交互链**（原作「Z → 射线检测 → 触发交互」的等价物）。

用户口径（逐字，承接）
--------------------
* 「原作里该有的可以交互的东西也要有哦，也就是和原作内的效果一样」（第46轮）
* 「把原作的世界搬到桌面上…桌面也是一个场景」（第38轮）
* 「一切根据原作」（第38轮）
* 本轮触发：第84轮清单把 I3/I6/I9 列为**既有实现缺口**（"该有的都得有"）。

本轮做的事（第84轮清单里的三个缺口）
--------------------------------
① **I6 射线四段矩形** —— `npc_interact.ray_rect()`：照抄原作
   `obj_mainchara_Step_0` 的四个 `collision_rectangle`，**四段形状各不相同**；
② **I3 被交互者转向主角** —— `face_actor()` + `main._npc_face_actor()`；
③ **I9 待机朝向回落**的一半 —— 交互后 NPC 转向主角（完整 I9 需要渲染层，
   本轮**如实标注未做**）；
④ 取代旧实现「点对点最近距离」：现在**背对着人按交互键不会选中他**。

原作依据（第84轮 UTMT 反编译取证，物证 `第84轮-原作互动技能取证/_evidence/dr_code.json`）
----------------------------------------------------------------------------------------
```
obj_mainchara_Step_0:
  if (button1_p()) {
    d = global.darkzone + 1;
    if (global.facing == 1) collision_rectangle(x+sw/2, y+6d+sh/2,
                                                x+sw+13d, y+sh, obj_interactable,...);
    if (global.facing == 3) collision_rectangle(x+sw/2, y+6d+sh/2,
                                                x-13d,    y+sh, obj_interactable,...);
    if (global.facing == 0) collision_rectangle(x+4d,   y+28d,
                                                x+sw-4d,  y+sh+15d, obj_interactable,...);
    if (global.facing == 2) collision_rectangle(x+3d,   y+sh-5d,
                                                x+sw-5d,  y+5d, obj_interactable,...);
    if (interactedobject != -4) {
        with (interactedobject) { facing = 3; }        // ★ 被交互者转向主角
        with (interactedobject) { scr_interact(); }
    }
  }
scr_interact() = { myinteract = 1; event_user(0); }
```

段一览
------
  A ★★★ 射线几何：**四段逐值等于原作**（A/B 锚点法，把原作式子独立算一遍）
  B ★★ 射线几何：形状差异真的在（四段互不相同 + 暗世界加长 + 上下段非"前方方块"）
  C ★★★ 命中：按**朝向**选（背对着不命中）+ 最近优先 + 平手确定性
  D ★★ 转向（I3）：被交互者看向主角；与 `npc_placement._facing_between` **等价**
  E ★★★ **接线**（`main.py`）：Z 键分流 / 射线函数真被调 / 复用 `npc_speak` / 转向真写 body
  F ★★ 旧行为不回归（负控制：桌面场景不射线；坐标取不到不猜）
  G 判据自身体检（记账守恒 + 负控制成对 + 被测文件在盘）

★ 判据纪律：`print('[PASS] %s')` 字面量；判据名里不自带标记；
  正/负控制成对；**断行为不断赋值**（关键判据真调产品函数）；
  ★★ **判据本身也是被测物**（第62~70 轮反复栽在判据侧）⇒ 每条都配负控制。
★ 零网络 / 零 UI / 不需要显示器 / 零外部盘。
"""
import ast
import io
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
if PKG not in sys.path:
    sys.path.insert(0, PKG)

from modules import npc_interact as NI        # noqa: E402
from modules import npc_placement as NP       # noqa: E402

MAIN = os.path.join(PKG, 'src', 'main.py')
MODULE = os.path.join(PKG, 'modules', 'npc_interact.py')

_failed = []
_n_pass = [0]
_n_fail = [0]
_n_lines = [0]          # ★ 真实打印的判据行数（`[PASS]`/`[FAIL]` 开头）


def check(desc, cond, star=False):
    mark = ' ★' if star else ''
    if cond:
        print('[PASS]%s %s' % (mark, desc))
        _n_pass[0] += 1
    else:
        print('[FAIL]%s %s' % (mark, desc))
        _n_fail[0] += 1
        _failed.append(desc)
    _n_lines[0] += 1


def _read(path):
    try:
        with io.open(path, 'r', encoding='utf-8') as fh:
            return fh.read()
    except Exception:
        return ''


def _ast(path):
    try:
        return ast.parse(_read(path))
    except Exception:
        return None


# ================================================================ 锚点：原作式子独立算
# ★★★ A/B 锚点法（第43.7 教训：反汇编/解析器必须先过 A/B 锚点）。
#   "提取成功" ≠ "提取正确" ⇒ 这里把原作的四个式子**独立重算一遍**（用左上角口径），
#   再与产品函数（中心口径）比。两个口径的换算写在测试里、不依赖产品实现。
_SW = 24.0      # 原作 sprite_width（Ralsei 小体型量级）
_SH = 32.0      # 原作 sprite_height
_HW = _SW / 2.0
_HH = _SH / 2.0
# 主角左上角 (60, 80) ⇒ 中心 (72, 96)
_LX, _LY = 60.0, 80.0
_CX, _CY = _LX + _HW, _LY + _HH


def _original_rect(facing, d):
    u"""把原作 `obj_mainchara_Step_0` 的式子**逐字**算一遍（左上角口径）。

    ★ 返回归一化后的 `(x1, y1, x2, y2)`（`collision_rectangle` 内部会摆正，
      这里显式归一以便与产品直接比）。
    """
    x, y, sw, sh = _LX, _LY, _SW, _SH
    if facing == 'right':
        r = (x + sw / 2.0, y + 6 * d + sh / 2.0, x + sw + 13 * d, y + sh)
    elif facing == 'left':
        r = (x + sw / 2.0, y + 6 * d + sh / 2.0, x - 13 * d, y + sh)
    elif facing == 'down':
        r = (x + 4 * d, y + 28 * d, (x + sw) - 4 * d, y + sh + 15 * d)
    elif facing == 'up':
        r = (x + 3 * d, (y + sh) - 5 * d, (x + sw) - 5 * d, y + 5 * d)
    else:
        return None
    a, b, c, e = r
    return (min(a, c), min(b, e), max(a, c), max(b, e))


# ================================================================ A. 射线几何 vs 原作
# ★★★ 用同一尺寸（half_w/half_h 按 _SW/_SH 给）⇒ 产品与原作应当**逐值相等**。
_geo_bad = []
for _dz, _d in ((NI.DARKZONE_LIGHT, 1), (NI.DARKZONE_DARK, 2)):
    for _f in ('right', 'left', 'down', 'up'):
        _got = NI.ray_rect(_CX, _CY, _f, _dz, half_w=_HW, half_h=_HH)
        _exp = _original_rect(_f, _d)
        # 容差 1e-6（浮点）；四元组逐值比
        _ok = (_got is not None and len(_got) == 4
               and all(abs(_got[i] - _exp[i]) < 1e-6 for i in range(4)))
        if not _ok:
            _geo_bad.append('%s/d=%d: got=%r exp=%r' % (_f, _d, _got, _exp))
check('A1 ★★★ 射线四段 × 明暗两世界，**逐值等于**原作式子（8 组）',
      not _geo_bad, star=True)
if _geo_bad:
    for _b in _geo_bad[:4]:
        print('        %s' % _b)

# A2 正控制：故意错一个系数 ⇒ 上面的比对应报红（证明 A1 有鉴别力）
_cx_bad = NI.ray_rect(_CX, _CY, 'down', NI.DARKZONE_LIGHT,
                      half_w=_HW, half_h=_HH)
_exp_down = _original_rect('down', 1)
check('A2 负控制：A1 的比对有鉴别力（把 down 段 y1 加 1 就必须不相等）',
      _cx_bad is not None
      and abs((_cx_bad[1] + 1.0) - _exp_down[1]) >= 1e-6, star=True)

# A3 未知朝向 ⇒ None（不猜）
check('A3 朝向非法 ⇒ None（不猜）',
      NI.ray_rect(_CX, _CY, 'northeast', 0) is None
      and NI.ray_rect(_CX, _CY, None, 0) is None)

# A4 暗世界射线**更长**（d=2 vs d=1）
_r_light = NI.ray_rect(_CX, _CY, 'right', NI.DARKZONE_LIGHT, half_w=_HW, half_h=_HH)
_r_dark = NI.ray_rect(_CX, _CY, 'right', NI.DARKZONE_DARK, half_w=_HW, half_h=_HH)
check('A4 ★ 暗世界射线的**延伸端**比光世界更远（原作 `d = darkzone + 1`）',
      _r_dark[2] > _r_light[2] and _r_dark[3] == _r_light[3], star=True)

# ================================================================ B. 四段形状差异
_shapes = {}
for _f in ('right', 'left', 'down', 'up'):
    _shapes[_f] = NI.ray_rect(_CX, _CY, _f, NI.DARKZONE_LIGHT, half_w=_HW, half_h=_HH)
check('B1 ★★ 四段矩形**互不相同**（不是"角色前方一个方块"）',
      len(set(_shapes.values())) == 4, star=True)

# B2 上/下段**不是**左右那种"细长横条"：上下段的**宽**比左右段的**长**小一个量级
_w_right = _shapes['right'][2] - _shapes['right'][0]      # 右段"长"（横向延伸）
_h_right = _shapes['right'][3] - _shapes['right'][1]      # 右段"高"
_w_down = _shapes['down'][2] - _shapes['down'][0]         # 下段宽
_h_down = _shapes['down'][3] - _shapes['down'][1]         # 下段高（纵向延伸）
check('B2 ★ 上下段是"横向窄、纵向延伸"，左右段是"纵向窄、横向延伸"',
      _h_down > _w_down and _w_right > _h_right, star=True)

# B3 负控制：若把上下段也写成"前方方块"（宽高相等）⇒ B2 必红
_fake_down = (_CX - 12, _CY + 12, _CX + 12, _CY + 36)     # 宽 24 高 24 = 方块
check('B3 负控制：B2 有鉴别力（方形射线应当不满足"纵向延伸"）',
      not ((_fake_down[3] - _fake_down[1]) > (_fake_down[2] - _fake_down[0])), star=True)

# ================================================================ C. 命中
_npc_right = {'x': _CX + 30, 'y': _CY, 'hw': 10, 'hh': 16}
_hit_right = NI.resolve((_CX, _CY), 'right', {'n': _npc_right})
_hit_left = NI.resolve((_CX, _CY), 'left', {'n': _npc_right})
check('C1 ★★★ 面朝右侧 ⇒ 命中右侧的人（命中最近）',
      _hit_right['target'] == 'n' and _hit_right['reason'] == 'hit', star=True)
check('C2 ★★★ **背对着他不命中**（旧实现"点对点最近"会误选）',
      _hit_left['target'] is None and _hit_left['reason'] == 'no_target', star=True)

# C3 最近优先
_cands = {'far': {'x': _CX + 60, 'y': _CY, 'hw': 8, 'hh': 16},
          'near': {'x': _CX + 26, 'y': _CY, 'hw': 8, 'hh': 16}}
check('C3 ★★ 同向多个 ⇒ 取**盒中心最近**的那个',
      NI.resolve((_CX, _CY), 'right', _cands)['target'] == 'near', star=True)

# C4 平手时取 key 字典序最小（确定性）
_tie = {'bbb': {'x': _CX + 30, 'y': _CY, 'hw': 10, 'hh': 16},
        'aaa': {'x': _CX + 30, 'y': _CY, 'hw': 10, 'hh': 16}}
check('C4 ★ 平手时结果**确定**（取 key 字典序最小，不随机）',
      NI.resolve((_CX, _CY), 'right', _tie)['target'] == 'aaa', star=True)

# C5 负控制：没有任何候选 ⇒ no_target（不猜一个）
check('C5 负控制：候选为空 ⇒ `no_target`（绝不硬选一个）',
      NI.resolve((_CX, _CY), 'right', {})['reason'] == 'no_target'
      and NI.resolve((_CX, _CY), 'right', {})['target'] is None, star=True)

# C6 非法输入的分因诊断
check('C6 非法输入给出**分因**（朝向坏 / 坐标坏 各是各的 reason）',
      NI.resolve((_CX, _CY), 'zzz', _cands)['reason'] == 'no_facing'
      and NI.resolve('abc', 'right', _cands)['reason'] == 'bad_actor_xy', star=True)

# C7 形状约定：4 元组 = 矩形（不是"中心+半宽"）—— 首版踩过这个坑
check('C7 ★★ `_box_of` 形状约定：4 元组=矩形、2 元组=点、字典=中心+半宽',
      NI._box_of((108, 90, 130, 116)) == (108.0, 90.0, 130.0, 116.0)
      and NI._box_of((5, 7)) == (5.0, 7.0, 5.0, 7.0)
      and NI._box_of({'x': 100, 'y': 100, 'hw': 10, 'hh': 20})
      == (90.0, 80.0, 110.0, 120.0), star=True)

# C8 负控制：逆序矩形被归一化（否则 `rect_intersects` 恒假、命中全失效）
check('C8 ★ 逆序矩形被归一化（x1>x2 会摆正）',
      NI._box_of((130, 116, 108, 90)) == (108.0, 90.0, 130.0, 116.0), star=True)

# ================================================================ D. 转向（I3）
# ★★★ 与 `npc_placement._facing_between` 的**等价性**（同一份规则两处算 = 最贵的坑）
#    ★ 逐例全比（含 `None`）：两边口径必须**逐位一致**，不许留"只有一侧知道的宽容带"。
#      `(0,0)` 与 `(1e-12,0)` 都在表里 —— 后者正是首版踩到的退化阈值分歧。
_pairs = [(5, 0), (-5, 0), (0, 5), (0, -5), (5, 3), (3, 5), (-5, 3), (3, -5),
          (0, 0), (1e-12, 0)]
_mismatch = []
for _dx, _dy in _pairs:
    _a = NI.facing_toward(0.0, 0.0, _dx, _dy)
    try:
        _b = NP._facing_between(_dx, _dy)
    except Exception:
        _b = None
    if _a != _b:
        _mismatch.append((_dx, _dy, _a, _b))
check('D1 ★★★ `facing_toward` 与 `npc_placement._facing_between` **逐例等价**'
      '（同一份规则不许两处算）',
      not _mismatch, star=True)
if _mismatch:
    for _m in _mismatch[:4]:
        print('        %r' % (_m,))

# D2 转向方向正确（被交互者看向主角）
check('D2 ★★ 主角在人左侧 ⇒ 那人朝左；主角在人上方 ⇒ 那人朝上',
      NI.face_actor(0.0, 0.0, 100.0, 0.0) == 'left'
      and NI.face_actor(0.0, 0.0, 0.0, 100.0) == 'up', star=True)

# D3 负控制：两人重合 ⇒ None（不编一个方向）
check('D3 负控制：两人重合 ⇒ None（不编方向）',
      NI.face_actor(50.0, 50.0, 50.0, 50.0) is None, star=True)

# D4 负控制：D2 有鉴别力（反向调用必不等于）
check('D4 负控制：`face_actor` 有鉴别力（反着调用结果不同）',
      NI.face_actor(0.0, 0.0, 100.0, 0.0) != NI.face_actor(100.0, 0.0, 0.0, 0.0),
      star=True)

# ================================================================ E. 接线（main.py）
_src = _read(MAIN)
_tree = _ast(MAIN)
check('E1 被测文件在盘（main.py / npc_interact.py）',
      os.path.isfile(MAIN) and os.path.isfile(MODULE)
      and _tree is not None, star=True)

# E2 引入模块
check('E2 ★★ main.py 引入 `npc_interact`（模块引用 `npc_interact_mod`）',
      'import npc_interact as npc_interact_mod' in _src, star=True)

# E3 新增方法都在
_need_defs = ['_npc_interact_actor_room_xy', '_npc_interact_facing',
              '_npc_interact_darkzone', '_npc_interact_candidates',
              '_npc_interact_pick', '_npc_interact_pick_prop',
              '_npc_face_actor', '_npc_interact_speak']
_funcs = set()
if _tree is not None:
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.FunctionDef):
            _funcs.add(_n.name)
_missing = [d for d in _need_defs if d not in _funcs]
check('E3 ★★ 射线交互的 8 个方法**全部定义**', not _missing, star=True)
if _missing:
    print('        缺: %r' % (_missing,))

# E4 ★★★ 真调用：`interact_scene_prop` 体内**真的调**了 `_npc_interact_pick`
_isp = None
for _n in ast.walk(_tree or ast.Module(body=[], type_ignores=[])):
    if isinstance(_n, ast.FunctionDef) and _n.name == 'interact_scene_prop':
        _isp = _n
        break
_called = set()
if _isp is not None:
    for _n in ast.walk(_isp):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
            _called.add(_n.func.attr)
check('E4 ★★★ `interact_scene_prop` **真调**射线选人/选物（不是写了没用）',
      '_npc_interact_pick' in _called and '_npc_interact_pick_prop' in _called,
      star=True)

# E5 ★★★ Z 键分流：**真结构判据**（AST，不是"三个子串在文件里出现过"）
#   ★ 首版只查 3 个子串 ⇒ `M6` 变异（把 `else:` 分支也换成 `toggle_possession()`）
#     **照样 PASS** —— 因为 `self.interact_scene_prop()` 在别处（E 键处理器）也有，
#     子串判据分不清"在哪个分支里"。这正是"判据过窄 = 会误报"的老坑。
#   ⇒ 改成：在 `keyPressEvent` 里找到 `Key_Z` 的 if，**断言那个 if 的 `else` 体
#     真调了 `interact_scene_prop`**，且 if 体真调了 `toggle_possession`。
def _has_attr(body, want):
    for s in body:
        for c in ast.walk(s):
            if (isinstance(c, ast.Call)
                    and isinstance(c.func, ast.Attribute)
                    and c.func.attr == want):
                return True
    return False


def _z_branch_ok(tree):
    """真结构判据：`Key_Z` 分支里必须有一个 `if/else`，
    **if 体调 `toggle_possession`（附身态交回）、else 体调 `interact_scene_prop`（未附身交互）**。

    ★ 形状随实际接线（第88轮）：`Key_Z` 的那个 if **没有 else**，body 里先 `poss_z = ...`
      再套一层 `if ...: toggle / else: interact`。所以要在 `Key_Z` 的 body 里**再找嵌套 if**，
      不能要求 `Key_Z` 那个 if 自己带 orelse（首版就是这么写错的 ⇒ 真文件上直接判假）。
    """
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef) or fn.name != 'keyPressEvent':
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.If):
                continue
            if 'Key_Z' not in ast.dump(node.test):
                continue
            # 在 `Key_Z` 分支体里找嵌套 if/else：body=toggle、orelse=interact
            for inner in ast.walk(node):
                if not isinstance(inner, ast.If) or not inner.orelse:
                    continue
                if (_has_attr(inner.body, 'toggle_possession')
                        and _has_attr(inner.orelse, 'interact_scene_prop')):
                    return True
    return False


_z_ok = _z_branch_ok(_tree) if _tree is not None else False
check('E5 ★★★ Z 键**分流**（AST：Z 的 if 体=交回灵魂、else 体=场景交互）',
      _z_ok, star=True)

# E5b 负控制：E5 有鉴别力（嵌套 if 的 else 体也换成 toggle ⇒ 必须判假）
_z_fake = ast.parse(
    'def keyPressEvent(self, e):\n'
    '    if key == _Qt.Key_Z:\n'
    '        poss_z = getattr(self, "possession", None)\n'
    '        if poss_z is not None and poss_z.is_possessing:\n'
    '            self.toggle_possession()\n'
    '        else:\n'
    '            self.toggle_possession()\n'
    '    if key == _Qt.Key_E:\n'
    '        self.interact_scene_prop()\n')
check('E5b 负控制：E5 有鉴别力（两分支都 toggle ⇒ 必须判假）',
      _z_branch_ok(_z_fake) is False, star=True)

# E5c 正控制：E5 的匹配器在**正确形状**上必须判真（防"改严了变成恒假"）
_z_good = ast.parse(
    'def keyPressEvent(self, e):\n'
    '    if key == _Qt.Key_Z:\n'
    '        poss_z = getattr(self, "possession", None)\n'
    '        if poss_z is not None and poss_z.is_possessing:\n'
    '            self.toggle_possession()\n'
    '        else:\n'
    '            self.interact_scene_prop()\n')
check('E5c 正控制：E5 的匹配器在正确形状上判真（不是恒假）',
      _z_branch_ok(_z_good) is True, star=True)

# E6 ★★★ 被交互说话**复用** `npc_speak`（不另起生成路径）
_speak = None
for _n in ast.walk(_tree or ast.Module(body=[], type_ignores=[])):
    if isinstance(_n, ast.FunctionDef) and _n.name == '_npc_interact_speak':
        _speak = _n
        break
_speak_calls = set()
if _speak is not None:
    for _n in ast.walk(_speak):
        if isinstance(_n, ast.Call):
            if isinstance(_n.func, ast.Attribute):
                _speak_calls.add(_n.func.attr)
check('E6 ★★★ 被交互 NPC 说话走 `npc_speak`（唯一生成路径，不另起一条）',
      'npc_speak' in _speak_calls, star=True)

# E7 ★★ 说话展示走 `_npc_say_line`（唯一气泡出口，说话人 = npc_id）
check('E7 ★★ 回话展示走 `_npc_say_line`（不写死成 ralsei 替他说）',
      '_npc_say_line' in _src and '_npc_show_line' not in _src, star=True)

# E8 ★★★ 转向真写 body.facing（断行为不断赋值：真建 Body 试）
_b = NP.Body('probe', scene='x', x=100.0, y=100.0, facing='down')
_b.facing = NI.face_actor(0.0, 0.0, 100.0, 0.0)     # 主角在原点 ⇒ 应朝 left
check('E8 ★★ `Body.facing` 可被写成转向结果（runtime 属性，非只读）',
      _b.facing == 'left', star=True)

# E9 朝向记忆字段在 keyPressEvent 里被更新
check('E9 ★★ `_interact_facing` 在方向键按下时被更新（持久朝向语义）',
      '_interact_facing = d' in _src
      and 'self._interact_facing = npc_interact_mod.FACE_DOWN' in _src,
      star=True)

# E10 ★★ 明暗世界判据与第85轮速度表**同一来源**（world_of_scene）
_dz_fn = None
for _n in ast.walk(_tree or ast.Module(body=[], type_ignores=[])):
    if isinstance(_n, ast.FunctionDef) and _n.name == '_npc_interact_darkzone':
        _dz_fn = _n
        break
_dz_calls = set()
if _dz_fn is not None:
    for _n in ast.walk(_dz_fn):
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
            _dz_calls.add(_n.func.attr)
check('E10 ★★ 明暗世界走 `scene_system.world_of_scene`（与速度表同源，不另判一遍）',
      'world_of_scene' in _dz_calls, star=True)

# ================================================================ F. 旧行为不回归
# F1 桌面场景不做射线（`_npc_interact_pick` 首行就挡）
check('F1 ★ 桌面/无场景 ⇒ 不射线交互（`DESKTOP_SCENE` 被挡）',
      'npc_system_mod.DESKTOP_SCENE' in _src
      and 'if getattr(self, \'current_scene\', None) in (None, npc_system_mod.DESKTOP_SCENE)'
      in _src.replace('"', "'"), star=True)

# F2 ★★ 旧降级链**保留**（射线不中 ⇒ 灵魂最近 ⇒ 登记顺序，逐级不静默）
check('F2 ★★ 旧降级链保留（射线不中仍能退回 `_soul_pick_prop`）',
      '_soul_pick_prop' in _src, star=True)

# F3 零依赖：npc_interact 顶层只 import 标准库
_mod_tree = _ast(MODULE)
_top_imps = []
if _mod_tree is not None:
    for _n in _mod_tree.body:
        if isinstance(_n, ast.Import):
            _top_imps += [a.name.split('.')[0] for a in _n.names]
        elif isinstance(_n, ast.ImportFrom):
            _top_imps.append((_n.module or '').split('.')[0])
check('F3 ★★ `npc_interact` 顶层只 import 标准库（零项目依赖）',
      set(_top_imps) <= {'logging', 'math', 'collections'}, star=True)
if set(_top_imps) - {'logging', 'math', 'collections'}:
    print('        %r' % (_top_imps,))

# F4 负控制：函数体内**零 import**（初始化环的经典成因）
_fn_imps = []
for _fn in [n for n in ast.walk(_mod_tree or ast.Module(body=[], type_ignores=[]))
            if isinstance(n, ast.FunctionDef)]:
    for _sub in _fn.body:
        for _x in ast.walk(_sub):
            if isinstance(_x, (ast.Import, ast.ImportFrom)):
                _fn_imps.append(_fn.name)
check('F4 ★★ 函数体内**零 import**（防初始化环）', not _fn_imps, star=True)

# F5 负控制：F3/F4 有鉴别力（假源码必须被抓）
_fake = 'def f():\n    import os\n    return os\n'
_ft = ast.parse(_fake)
_bad = []
for _fn in [n for n in ast.walk(_ft) if isinstance(n, ast.FunctionDef)]:
    for _x in ast.walk(_fn):
        if isinstance(_x, (ast.Import, ast.ImportFrom)):
            _bad.append(_fn.name)
check('F5 负控制：F4 有鉴别力（含函数内 import 的假源码必须被抓）',
      _bad == ['f'], star=True)

# ================================================================ G. 判据自身体检
check('G1 ★ 射线几何：上下段的起点**不在**中心横行上（这是照抄原作的关键差异）',
      NI.ray_rect(_CX, _CY, 'down', 0, half_w=_HW, half_h=_HH)[1] > _CY
      and NI.ray_rect(_CX, _CY, 'up', 0, half_w=_HW, half_h=_HH)[3] < _CY + _SH,
      star=True)

# G2 ★★ 记账守恒（**真判据**：计数器必须等于真实打印的判据行数）
#    ★ 首版这里写成了 `check('...', True)` —— 恒真占位，本项目最忌的写法
#      （第64轮 `W22` 就是这么栽的）。现在比的是 `_n_lines`（每次 `check` 真加一）
#      与 `_n_pass + _n_fail` 的**恒等**，且总数要够（防"少打印几条也算过"）。
check('G2 ★★ 记账守恒（每个 check 都记了账，且总数 ≥ 30）',
      _n_lines[0] == _n_pass[0] + _n_fail[0] and _n_lines[0] >= 30, star=True)

# G3 负控制：G2 的记账器有鉴别力（**手工模拟**一次 FAIL，不真打印 [FAIL] 行
#    —— 那会被 `run_all.py` 的行解析误算成本套件有失败）
_before_f = _n_fail[0]
_before_len = len(_failed)


def _sim_fail():
    _n_fail[0] += 1
    _failed.append('__sim__')


_sim_fail()
_has_effect = (_n_fail[0] == _before_f + 1 and len(_failed) == _before_len + 1)
# 撤回模拟（★ 不撤回会把退出码判红 —— 一个"负控制污染计数"的坑）
_n_fail[0] -= 1
_failed.pop()
check('G3 ★★ 负控制：记账器有鉴别力（模拟 FAIL ⇒ 计数真 +1，已撤回）',
      _has_effect and _n_fail[0] == _before_f and len(_failed) == _before_len,
      star=True)

print('=' * 70)
print('第88轮：FAIL %d 项 %s' % (len(_failed), _failed if _failed else ''))
print('=' * 70)
sys.exit(0 if not _failed else 1)

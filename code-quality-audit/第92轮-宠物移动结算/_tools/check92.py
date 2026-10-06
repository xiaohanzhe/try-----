# -*- coding: utf-8 -*-
u"""第92轮回归锁：**宠物"走不动/站桩"**的位移结算缺陷。

背景（全部来自本轮真机取证，不是推测）
--------------------------------------
用户原话：「**他在这里站桩呢？？？**」（第90轮）／「**他现在光有那个移动的动画，
没有实际移动**」（第51轮，同一症状）。

本轮用**进程内自省探针**（劫持实例属性 `pet.move`，数每一次移动尝试的真实 delta）
取到硬证据 —— 178.3s / **5047 次 `move()` 调用里 4890 次（91.9%）位移为 0**，
平均位移 **3.9 px/s**，而 `duty(is_moving)=94.9%`（**一直在"走"**）。
即：动画在播、位置不动。三段成因（每段都能独立把宠物钉死）：

  D1 取整丢位移且**不结转**（`int(round(pos + 位移))`）
     · `speed` 的量纲是 **px/帧**，移动定时器 30ms/帧 ⇒ 每帧位移常低于 1px；
       不足 0.5px 时取整为 0，且下一帧仍从 `current_pos` **重新算同一个值**
       ⇒ 位移恒 0，而 `is_moving` 仍为 True、`walk_*` 照播。
  D2 近距减速**没有下限**（`speed * (distance / 50)`）
     · distance < 25px 时目标速度被压到 0.5px/帧以下 ⇒ 同上取整为 0；
       而"到达"阈值只有 `max(speed*3, 30)=30px` ⇒ **永远差最后几步**。
       实测有一段 **165s 只挪 179px**，全程播走路动画。
  D3 速度被系数压出配置区间（`speed = uniform(min_speed*0.2, max_speed*0.4)` …）
     · 配置 `movement.min_speed=3.0`，乘 0.3 ⇒ 实测抽到 **0.91px/帧（=30px/s）**；
       再乘情绪因子 0.4 ⇒ 0.36px/帧 ⇒ 与 D1/D2 叠加后每帧位移恰为 0。

段一览
------
  A ★★★ 位移必须**结转小数余量**（AST：`int(round(… + self._subpixel_x))` 形态、
        余量有界 · 独立重算的**鉴别力自证**：旧公式在实测参数下 300 帧走 0px，
        新公式走出 >100px）
  B ★★ 近距减速必须有下限（AST：`max(...)` 且下限 ≥ 1.0 · 旧式在该距离下位移为 0 的负控制）
  C ★★★ 速度取位必须落在配置区间内（AST：不许再出现 `min_speed/max_speed × 系数` 形态 ·
        **行为级**：真调 `RalseiPet.generate_new_move_target`（轻量桩）× 8 情绪 × 30 次，
        断言 `min_speed <= speed <= max_speed` 恒成立 + 情绪排序 + 旧系数会违反的负控制）
  D ★★ 余量归零时机（到达 / 换目标）· 全文件无第二份"不结转"的旧写法 ·
        `self.speed` 仍**不**参与跳跃/坠落物理（证明本轮提速不污染另一条线）
  E 判据自身体检（恒真防护：正/负重算必须可区分 · 记账守恒 · 记账口非 no-op）

★ 判据纪律：`print('[PASS] %s')` 字面量；判据名不自带标记；正/负控制成对；
  断行为不断赋值；A/B/C/D 走 AST 或真实调用；零网络 / 零 UI / 不需要显示器 / 零外部盘。
"""
import ast
import os
import random
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PyQt5.QtCore import QPoint, QRect     # noqa: E402

from main import RalseiPet                 # noqa: E402

MAIN = os.path.join(PKG, 'src', 'main.py')
CFG = os.path.join(PKG, 'config.json')

# ★ 变异测试接缝（`mutate92.py` 用）：**必须同时**给出 `CHECK92_MUTATION_HARNESS=1`
#   与 `CHECK92_MAIN=<变异副本>` 才生效 —— 免得正常回归被一个遗留环境变量悄悄改了被测物。
if os.environ.get('CHECK92_MUTATION_HARNESS') == '1' and os.environ.get('CHECK92_MAIN'):
    MAIN = os.environ['CHECK92_MAIN']

_failed = []
_n_pass = 0
_n_fail = 0
_n_calls = 0
_marks = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail, _n_calls
    _n_calls += 1
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def mark(title):
    global _marks
    _marks += 1
    print('---- [判据点 %d] %s ----' % (_marks, title))


with open(MAIN, encoding='utf-8') as _fh:
    SRC = _fh.read()
TREE = ast.parse(SRC)


def _fn(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _attrs(node):
    """收集子树里所有 `X.attr` 的属性名。"""
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def _dotted(node):
    """把 `self.a.b` 还原成字符串 'self.a.b'（非 dotted 返回 None）。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return base + '.' + node.attr if base else None
    return None


def _num(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = _num(node.operand)
        return -v if v is not None else None
    return None


def _assigns_with_attr(fn, attr):
    """`fn` 内所有 `self.<attr> = …` 的 (Assign, 右值) 列表。"""
    out = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and len(n.targets) == 1:
            t = n.targets[0]
            if isinstance(t, ast.Attribute) and t.attr == attr:
                out.append(n)
    return out


UM = _fn(TREE, 'update_movement')
GNMT = _fn(TREE, 'generate_new_move_target')
IM = _fn(TREE, 'init_movement')
HJ = _fn(TREE, 'handle_jump')


# ============================================================ A. 位移结转
mark('A 位移必须结转小数余量（"走不动"的直接元凶）')

check('A0 被测函数都在盘上（update_movement / generate_new_move_target / '
      'init_movement / handle_jump）',
      all(f is not None for f in (UM, GNMT, IM, HJ)))

# A1 预声明（不许靠 getattr 兜底）
_a1 = []
for _attr in ('_subpixel_x', '_subpixel_y'):
    hits = _assigns_with_attr(IM, _attr) if IM is not None else []
    _a1.append(any(_num(h.value) == 0.0 for h in hits))
check('A1 `init_movement` 显式预声明 `_subpixel_x/_subpixel_y = 0.0`（不走 getattr 兜底）',
      all(_a1), 'x=%s y=%s' % (_a1[0], _a1[1]))


def _resolve(fn, node):
    """一步名字解析：`node` 是 Name 就换成它在 `fn` 内的定义式（取最后一次赋值）。

    ★ 为什么要它：修复后的写法是
        `_raw_x = current_pos.x() + … + self._subpixel_x`
        `new_x  = int(round(_raw_x))`
      取整参数是一个 **Name**，直接对 `int(round(ARG))` 的 ARG 取属性会得到空集 ——
      第一版判据就是这么误报的（判据侧缺陷，不是产品缺陷）。判据必须跟一步。
    """
    if not isinstance(node, ast.Name):
        return node
    found = None
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id == node.id:
            found = n.value
    return found if found is not None else node


def _round_assign(fn, varname):
    """找 `new_x = int(round(<EXPR>))` 形态，返回 EXPR（未解析名字）。"""
    for n in ast.walk(fn):
        if not (isinstance(n, ast.Assign) and len(n.targets) == 1):
            continue
        t = n.targets[0]
        if not (isinstance(t, ast.Name) and t.id == varname):
            continue
        v = n.value
        if (isinstance(v, ast.Call) and isinstance(v.func, ast.Name)
                and v.func.id == 'int' and len(v.args) == 1
                and isinstance(v.args[0], ast.Call)
                and isinstance(v.args[0].func, ast.Name)
                and v.args[0].func.id == 'round'
                and len(v.args[0].args) == 1):
            return v.args[0].args[0]
    return None


_ex_x = _round_assign(UM, 'new_x') if UM is not None else None
_ex_y = _round_assign(UM, 'new_y') if UM is not None else None

_ax = _attrs(_resolve(UM, _ex_x)) if _ex_x is not None else set()
_ay = _attrs(_resolve(UM, _ex_y)) if _ex_y is not None else set()
check('A2 `new_x` 的取整参数里含 `self._subpixel_x`（位移在取整前把余量加回去）',
      _ex_x is not None and '_subpixel_x' in _ax, 'attrs=%s' % sorted(_ax))
check('A3 `new_y` 的取整参数里含 `self._subpixel_y`',
      _ex_y is not None and '_subpixel_y' in _ay, 'attrs=%s' % sorted(_ay))

# A4/A5 结转赋值必须有界（否则余量会越攒越大、反向把宠物拽回去）
_carry_x = _assigns_with_attr(UM, '_subpixel_x') if UM is not None else []
_carry_x = [a for a in _carry_x if not (isinstance(a.value, ast.Constant)
                                        and _num(a.value) == 0.0)]
check('A4 `update_movement` 里有 `self._subpixel_x = <带界表达式>` 的结转赋值',
      len(_carry_x) >= 1, 'n=%d' % len(_carry_x))
_bounded = False
if _carry_x:
    _v = _carry_x[0].value
    _bounded = isinstance(_v, ast.IfExp) and isinstance(_v.test, ast.Compare) \
        and len(_v.test.ops) == 2      # 链式比较 = 双边有界
check('A5 结转表达式是**双边有界**的 `IfExp(Compare)`（防余量累积失控）',
      _bounded,
      'kind=%s' % (type(_carry_x[0].value).__name__ if _carry_x else 'None'))

# ★★ A4b（变异测试 `M2` 逼出来的补强）：A4/A5 只查了"形状"，于是一个
#    `_carry_x = 0.0`（= 名义上还在结转、实际恒 0）的变异**能蒙混过关**。
#    判据必须落到语义上：被写进 `_subpixel_x` 的那个名字，必须**真的**定义为
#    "取整残差"（`X - new_x` 形态的减法），而不是常量。
_carry_target_names = set()
if _carry_x and isinstance(_carry_x[0].value, ast.IfExp):
    _carry_target_names = {n.id for n in ast.walk(_carry_x[0].value.body)
                           if isinstance(n, ast.Name)}
_resid = False
if _carry_target_names:
    for _n in ast.walk(UM):
        if isinstance(_n, ast.Assign) and len(_n.targets) == 1 \
                and isinstance(_n.targets[0], ast.Name) \
                and _n.targets[0].id in _carry_target_names:
            _v = _n.value
            if isinstance(_v, ast.BinOp) and isinstance(_v.op, ast.Sub) \
                    and any(isinstance(_x, ast.Name) and _x.id in ('new_x', 'new_y')
                            for _x in ast.walk(_v)):
                _resid = True
check('A4b ★ 结转值真的是"取整残差"（`_raw - new_x` 形态），不是常量 0',
      _resid, 'carry_names=%s' % sorted(_carry_target_names))

# A5b 有界判据的行为鉴别力：把源码里的 IfExp **执行**一次，越界必须被清零
_guard_ok = False
if _carry_x:
    try:
        _code = compile(ast.Expression(_carry_x[0].value), '<carry>', 'eval')
        _in_band = eval(_code, {'_carry_x': 0.3})          # noqa: S307 - 判据自证
        _out_band = eval(_code, {'_carry_x': 5.8})         # noqa: S307 - 判据自证
        _guard_ok = (abs(_in_band - 0.3) < 1e-9) and (_out_band == 0.0)
    except Exception:
        _guard_ok = False
check('A5b 边界真的生效（源码表达式执行：0.3 → 0.3，5.8 → 0.0）', _guard_ok)

# A6/A7 ★★★ 鉴别力自证：旧/新公式**独立重算**，在实测参数下必须可分
#   实测参数：speed=0.91px/帧（第51轮真机抽到的值）· 情绪因子 0.4（tired）
#             · 目标 200px 外（远离"近距减速区"）
_SPEED_MEASURED = 0.91
_MOOD_MEASURED = 0.4
_STEP = _SPEED_MEASURED * _MOOD_MEASURED        # 0.364 px/帧
_FRAMES = 300
_DIST = 200.0


def _replay(carry):
    """按 update_movement 的算式重放 N 帧，返回总位移（px）。"""
    pos = 1000
    sub = 0.0
    for _ in range(_FRAMES):
        move_distance = min(_DIST, _STEP, _SPEED_MEASURED)
        x = pos + (-1.0) * move_distance + (sub if carry else 0.0)
        new_x = int(round(x))
        sub = (x - new_x) if (-1.0 < (x - new_x) < 1.0) else 0.0
        pos = new_x
    return 1000 - pos


_old_px = _replay(carry=False)
_new_px = _replay(carry=True)
check('A6 ★鉴别力：**旧公式**（不结转）在实测参数下 %d 帧位移恒为 0'
      % _FRAMES, _old_px == 0, 'old=%dpx' % _old_px)
check('A7 ★鉴别力：**新公式**（结转）同参数下必须走出可见位移（≥100px）',
      _new_px >= 100, 'new=%dpx' % _new_px)
check('A8 A6/A7 成对可分（两者结果不同，判据不是恒真）',
      _old_px != _new_px)


# ============================================================ B. 近距减速下限
mark('B 近距减速必须有下限（否则永远差最后几步）')

_ramp = None
for n in ast.walk(UM) if UM is not None else []:
    if isinstance(n, ast.Assign) and len(n.targets) == 1:
        t = n.targets[0]
        if isinstance(t, ast.Name) and t.id == 'target_move_speed':
            if isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) \
                    and n.value.func.id == 'max':
                _ramp = n.value
check('B1 近距减速分支改成了 `max(<比例式>, <下限>)` 形态',
      _ramp is not None and len(_ramp.args) == 2,
      'args=%d' % (len(_ramp.args) if _ramp else -1))

_floor = _num(_ramp.args[1]) if (_ramp and len(_ramp.args) == 2) else None
check('B2 下限是**数值常量且 ≥ 1.0 px/帧**（≈33px/s，保证最后一段一定走完）',
      _floor is not None and _floor >= 1.0, 'floor=%s' % _floor)

_prop_ok = False
if _ramp and len(_ramp.args) == 2:
    _a = _ramp.args[0]
    _prop_ok = ('speed' in _attrs(_a)) and ('distance' in {n.id for n in ast.walk(_a)
                                                          if isinstance(n, ast.Name)})
check('B3 比例关系没被丢掉（max 第一参数仍含 `self.speed` 与 `distance`）', _prop_ok)


def _old_ramp_step(distance, speed=_SPEED_MEASURED, mood=1.0):
    """旧式（无下限）在该距离下的一帧位移（px，取整后）。

    ⚠️ 必须带上**实测的情绪因子**（0.4）——第一版判据漏了它，在 40px 处算出 -1（即
       1px/帧），于是误判"旧式也会动"。真机就是 speed×mood 这个乘积掉到 0.5 以下。
    """
    return int(round(0.0 - min(distance, speed * (distance / 50.0) * mood, speed)))


def _new_ramp_step(distance, speed=_SPEED_MEASURED, mood=1.0, second_floor=True):
    """新式在该距离下的一帧位移（px，取整后）—— 按**修后管线**重算：

        第一道下限：`target_move_speed = max(speed*(d/50), 1.0)`
        情绪因子：  `target_final = target_move_speed * mood`
        第二道下限：`target_final = max(target_final, 1.0)`   ← 本轮的第二个修复
        实际位移：  `min(distance, target_final, self.speed)`（稳定态）

    `second_floor=False` ⇒ 模拟"只有第一道下限"（鉴别力负控制）。
    """
    _tm = max(speed * (distance / 50.0), 1.0)
    _tf = _tm * mood
    if second_floor:
        _tf = max(_tf, 1.0)
    return int(round(0.0 - min(distance, _tf, speed)))


check('B4 ★鉴别力：旧式在 20px 处（实测参数）每帧位移取整后为 0（=永远到不了）',
      _old_ramp_step(20.0, mood=_MOOD_MEASURED) == 0,
      'old_step@20px=%d' % _old_ramp_step(20.0, mood=_MOOD_MEASURED))
check('B5 ★鉴别力：旧式在 40px 处（实测参数）**同样**为 0 —— 影响面不止 20px',
      _old_ramp_step(40.0, mood=_MOOD_MEASURED) == 0,
      'old_step@40px=%d' % _old_ramp_step(40.0, mood=_MOOD_MEASURED))
# ⚠️ 重算返回的是**带方向**的位移（向左为负）⇒ 必须取绝对值判"走了多少 px"。
check('B6 正控制：新式在 40px 处（含情绪因子）每帧位移绝对值 ≥1px —— 下限不被情绪因子吃掉',
      abs(_new_ramp_step(40.0, mood=_MOOD_MEASURED)) >= 1,
      'new_step@40px=%d' % _new_ramp_step(40.0, mood=_MOOD_MEASURED))
check('B6b ★鉴别力：**拆掉第二道下限**（只有第一道）时同场景仍为 0 ⇒ 第二个修复不可省',
      _new_ramp_step(40.0, mood=_MOOD_MEASURED, second_floor=False) == 0,
      'no2nd@40px=%d' % _new_ramp_step(40.0, mood=_MOOD_MEASURED, second_floor=False))

# B7 ★★ 第二道下限：情绪因子是在第一道下限**之后**乘的，必须在它之后再夹一次。
#   真机教训：只夹 `target_move_speed` 时，`1.0 × 0.4 = 0.4px/帧` 又会掉到 0.5 以下。
_final_floor = None
for _n in (ast.walk(UM) if UM is not None else []):
    if isinstance(_n, ast.Assign) and len(_n.targets) == 1:
        _t = _n.targets[0]
        if isinstance(_t, ast.Name) and _t.id == 'target_final_speed' \
                and isinstance(_n.value, ast.Call) \
                and getattr(_n.value.func, 'id', '') == 'max':
            _fl = _num(_n.value.args[-1]) if _n.value.args else None
            if _fl is not None and _fl >= 1.0:
                _final_floor = _fl
check('B7 ★★ `target_final_speed` 在**情绪因子之后**再夹一道 ≥1.0 的下限',
      _final_floor is not None, 'floor=%s' % _final_floor)
check('B8 情绪因子真的参与运算（免得 B7 守的是一个恒等于常量的表达式）',
      UM is not None and any(
          isinstance(_n, ast.BinOp) and 'mood_factor' in str(ast.dump(_n))
          for _n in ast.walk(UM)))


# ============================================================ C. 速度量级
mark('C 速度必须落在配置区间内（取位，不再乘系数）')

_bad_mult = []
for n in (ast.walk(GNMT) if GNMT is not None else []):
    if isinstance(n, ast.Assign) and len(n.targets) == 1:
        t = n.targets[0]
        if isinstance(t, ast.Attribute) and t.attr == 'speed':
            for m in ast.walk(n.value):
                if isinstance(m, ast.BinOp) and isinstance(m.op, ast.Mult):
                    if _dotted(m.left) in ('self.min_speed', 'self.max_speed') \
                            or _dotted(m.right) in ('self.min_speed', 'self.max_speed'):
                        _bad_mult.append(_dotted(m.left) or _dotted(m.right))
check('C1 `generate_new_move_target` 里不再出现 `min_speed/max_speed × 系数` 的速度赋值',
      not _bad_mult, 'found=%s' % sorted(set(_bad_mult)))

_pos_tbl = None
for n in ast.walk(GNMT) if GNMT is not None else []:
    if isinstance(n, ast.Assign) and len(n.targets) == 1:
        t = n.targets[0]
        if isinstance(t, ast.Name) and t.id == '_speed_pos' and isinstance(n.value, ast.Dict):
            _pos_tbl = n.value
_pairs_ok = False
if _pos_tbl is not None:
    _pairs_ok = True
    for _v in _pos_tbl.values:
        if not (isinstance(_v, ast.Tuple) and len(_v.elts) == 2):
            _pairs_ok = False
            break
        _lo, _hi = _num(_v.elts[0]), _num(_v.elts[1])
        if _lo is None or _hi is None or not (0.0 <= _lo < _hi <= 1.0):
            _pairs_ok = False
            break
_emo_keys = set()
if _pos_tbl is not None:
    _emo_keys = {k.value for k in _pos_tbl.keys if isinstance(k, ast.Constant)}
check('C2 情绪→取位表存在且每项是 `(lo, hi)` 且 `0 ≤ lo < hi ≤ 1`',
      _pairs_ok, 'keys=%d' % len(_emo_keys))
check('C3 取位表覆盖 8 种情绪（含最慢的 tired 与最快的 excited）',
      _emo_keys >= {'excited', 'energetic', 'curious', 'happy',
                    'peaceful', 'shy', 'sad', 'tired'},
      'missing=%s' % sorted({'excited', 'energetic', 'curious', 'happy',
                             'peaceful', 'shy', 'sad', 'tired'} - _emo_keys))

# C4 ★★★ 行为级：真调产品的 generate_new_move_target（轻量桩）
CFG_MIN, CFG_MAX = 3.0, 8.0
try:
    import json as _json
    with open(CFG, encoding='utf-8') as _fh:
        _cfg = _json.load(_fh)
    CFG_MIN = float(_cfg['movement']['min_speed'])
    CFG_MAX = float(_cfg['movement']['max_speed'])
except Exception:
    pass


class _EmotionStub(object):
    def __init__(self):
        self.value = ('peaceful', 1.0)

    def get_current_emotion(self):
        return self.value


class _Stub(object):
    """借用**产品**的未绑定函数（真代码、假 self）。"""

    generate_new_move_target = RalseiPet.generate_new_move_target

    def __init__(self):
        self.emotion_system = _EmotionStub()
        self.min_speed = CFG_MIN
        self.max_speed = CFG_MAX
        self.speed = CFG_MIN
        self.pos_xy = (1280, 800)
        self.target_pos = QPoint(0, 0)
        self.previous_direction = 'right'
        self.max_moving_duration = 0.0

    def pos(self):
        return QPoint(*self.pos_xy)

    def _virtual_screen_rect(self):
        return QRect(0, 0, 2560, 1600)


_EMOS = ['excited', 'energetic', 'curious', 'happy',
         'peaceful', 'shy', 'sad', 'tired']
_N_EACH = 30
_samples = {}
_oor = []
for _e in _EMOS:
    _vals = []
    for _i in range(_N_EACH):
        _s = _Stub()
        _s.emotion_system.value = (_e, 1.0)
        _s.generate_new_move_target()
        _vals.append(float(_s.speed))
        if not (CFG_MIN <= _s.speed <= CFG_MAX):
            _oor.append((_e, _s.speed))
    _samples[_e] = _vals

check('C4 ★★★ 行为级：8 情绪 × %d 次真调 `generate_new_move_target`，'
      '`speed` 必须恒在配置区间 [%.1f, %.1f] 内' % (_N_EACH, CFG_MIN, CFG_MAX),
      not _oor, 'out_of_range=%s' % _oor[:4])

_mean = {k: sum(v) / len(v) for k, v in _samples.items()}
check('C5 情绪排序保住：excited 均值 > tired 均值（"兴奋快 / 疲惫慢"不许被抹平）',
      _mean['excited'] > _mean['tired'],
      'excited=%.2f tired=%.2f' % (_mean['excited'], _mean['tired']))
check('C6 每个情绪都真的在动（均值 ≥ 2.5px/帧 ≈ 83px/s，肉眼可辨）',
      all(v >= 2.5 for v in _mean.values()),
      'min_mean=%.2f' % min(_mean.values()))


def _old_speed_sample(emotion):
    """独立重算**旧**系数（0.2~0.9×）在配置区间下会抽到的速度。"""
    lo, hi = {
        'excited': (0.7, 0.9), 'energetic': (0.7, 0.9), 'curious': (0.5, 0.7),
        'shy': (0.3, 0.5), 'peaceful': (0.3, 0.5), 'sad': (0.2, 0.4),
        'tired': (0.2, 0.4),
    }.get(emotion, (0.4, 0.6))
    return random.uniform(CFG_MIN * lo, CFG_MAX * hi)


_old_oor = [e for e in _EMOS
            if any(not (CFG_MIN <= _old_speed_sample(e) <= CFG_MAX) for _ in range(50))]
check('C7 ★鉴别力：旧系数独立重算**必然**违反区间不变量（证明 C4 不是恒真）',
      len(_old_oor) > 0, 'old_violating_emotions=%s' % _old_oor)


# ============================================================ D. 一致性与边界
mark('D 归零时机 / 无第二份真相 / 不污染跳跃物理')

_arrive_zero = []
if UM is not None:
    for n in ast.walk(UM):
        if isinstance(n, ast.Assign) and len(n.targets) == 1:
            t = n.targets[0]
            if isinstance(t, ast.Attribute) and t.attr in ('current_speed_x', 'current_speed_y'):
                _arrive_zero.append(n.lineno)
_sub_zero_lines = sorted(
    n.lineno for n in ast.walk(UM or ast.parse('pass'))
    if isinstance(n, ast.Assign) and len(n.targets) == 1
    and isinstance(n.targets[0], ast.Attribute) and n.targets[0].attr == '_subpixel_x'
    and _num(n.value) == 0.0)
# ⚠️ 输出只打"计数 + 布尔"，**不打行号** —— 行号会随任何一次上方插行而漂移，
#    会让本套件每轮报假 DIFF（第79轮就是这么陈旧的）。判据本身用行号做**内部**比较即可。
check('D1 到达（重置速度）处同时清了 `_subpixel_x`（下一段从干净状态起步）',
      any(abs(l - z) <= 4 for l in _arrive_zero for z in _sub_zero_lines),
      'reset=%d zero=%d adjacent=%s'
      % (len(_arrive_zero), len(_sub_zero_lines),
         bool(any(abs(l - z) <= 4 for l in _arrive_zero for z in _sub_zero_lines))))

_gnmt_zero = sorted(
    n.lineno for n in ast.walk(GNMT or ast.parse('pass'))
    if isinstance(n, ast.Assign) and len(n.targets) == 1
    and isinstance(n.targets[0], ast.Attribute) and n.targets[0].attr == '_subpixel_x'
    and _num(n.value) == 0.0)
_gnmt_moving = sorted(
    n.lineno for n in ast.walk(GNMT or ast.parse('pass'))
    if isinstance(n, ast.Assign) and len(n.targets) == 1
    and isinstance(n.targets[0], ast.Attribute) and n.targets[0].attr == 'is_moving')
check('D2 换目标（`is_moving = True`）处同时清了 `_subpixel_x`',
      bool(_gnmt_zero) and bool(_gnmt_moving)
      and any(abs(z - m) <= 6 for z in _gnmt_zero for m in _gnmt_moving),
      'zero_pts=%d moving_pts=%d adjacent=%s'
      % (len(_gnmt_zero), len(_gnmt_moving),
         bool(_gnmt_zero and _gnmt_moving
              and any(abs(z - m) <= 6 for z in _gnmt_zero for m in _gnmt_moving))))

# D3 全文件不许再有"不结转"的旧写法（`int(round(位移))` 且该位移里没有 _subpixel）
#     ⚠️ 判据必须跟一步名字解析（`new_x = int(round(_raw_x))` 的参数是 Name），
#        否则会把修好的那处也判成 legacy —— 第一版就是这么误报的。
_legacy = []
_n_round_sites = 0
for n in ast.walk(TREE):
    if isinstance(n, ast.Assign) and len(n.targets) == 1:
        t = n.targets[0]
        if isinstance(t, ast.Name) and t.id in ('new_x', 'new_y'):
            v = n.value
            if (isinstance(v, ast.Call) and isinstance(v.func, ast.Name)
                    and v.func.id == 'int' and v.args
                    and isinstance(v.args[0], ast.Call)
                    and getattr(v.args[0].func, 'id', '') == 'round'):
                _n_round_sites += 1
                _owner = None
                for _cand in ast.walk(TREE):
                    if isinstance(_cand, ast.FunctionDef):
                        for _st in ast.walk(_cand):
                            if _st is n:
                                _owner = _cand
                                break
                    if _owner is not None:
                        break
                _resolved = _resolve(_owner, v.args[0].args[0]) if _owner else v.args[0].args[0]
                if not any(a.startswith('_subpixel') for a in _attrs(_resolved)):
                    _legacy.append(n.lineno)
check('D3 全文件不存在第二份"取整不结转"的位移写法（避免只修一处）',
      not _legacy, 'round_sites=%d legacy_count=%d' % (_n_round_sites, len(_legacy)))
check('D3b 取整位移点真的存在（≥1 处），否则 D3 会因"一个都没扫到"而假绿',
      _n_round_sites >= 1, 'round_sites=%d' % _n_round_sites)

check('D4 `self.speed` 仍**不**参与跳跃物理（`handle_jump` 内无 `self.speed`）',
      HJ is not None and 'speed' not in _attrs(HJ))


# ============================================================ E. 判据自身体检
mark('E 判据自身体检')

check('E1 被测文件在盘（main.py / config.json）',
      all(os.path.isfile(p) for p in (MAIN, CFG)))
check('E2 判据点全部执行到位（标记打印点 == 5）', _marks == 5, 'marks=%d' % _marks)
check('E3 ★恒真防护：A6/A7 的重放桩**能**区分结转与否'
      '（同参数同帧数，结果必须不同）', _old_px != _new_px,
      'old=%d new=%d' % (_old_px, _new_px))
check('E4 ★恒真防护：C4 的桩**真**走到了产品函数（`speed` 被写过、且区间内）',
      all(len(v) == _N_EACH for v in _samples.values()) and not _oor,
      'n_emotions=%d' % len(_samples))

_probe_calls = _n_calls
_probe_marks = _marks


def _noop_probe():
    mark('E5 空判据探针')
    return None


_noop_probe()
check('E5 记账口不是 no-op（打了标记点但没走 check ⇒ 独立计数器不涨）',
      _n_calls == _probe_calls and _marks == _probe_marks + 1,
      'calls=%d(+0) marks=%d(+1)' % (_n_calls, _marks))
check('E6 记账守恒（独立计数器 CALLS == PASS + FAIL）',
      _n_calls == _n_pass + _n_fail,
      'calls=%d pass=%d fail=%d' % (_n_calls, _n_pass, _n_fail))
check('E7 守恒判据有鉴别力（把漏记那一步计进总数 ⇒ 等式不再成立）',
      (_n_calls + 1) != (_n_pass + _n_fail),
      'calls+1=%d vs pass+fail=%d' % (_n_calls + 1, _n_pass + _n_fail))

print('=' * 70)
print('第92轮：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print('失败项：')
    for _d in _failed:
        print('  - %s' % _d)
print('=' * 70)
sys.exit(0 if not _failed else 1)

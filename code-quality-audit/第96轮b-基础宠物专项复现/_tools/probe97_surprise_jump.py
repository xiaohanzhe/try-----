# -*- coding: utf-8 -*-
"""probe97_surprise_jump.py —— 第96轮b 候选1 行为级复现：
「惊讶把全局 jump_height/jump_duration 改掉且永不还原 ⇒ 此后每次真跳跃都变矮变短」

判据设计（正/负控制成对）：
  1. 读产品真源码，静态确认 jump_height/jump_duration 的**全部**写入点
     ⇒ 除初始化与惊吓分支外，**零**还原点。
  2. 行为级：把**真源码**的 `handle_jump` 解剖进轻量桩，喂同一组 (起点,终点)，
     分别用「污染前 (50,1.0)」与「污染后 (20,0.5)」两组参数跑，比较轨迹。
     · 必须 A≠B（否则说明参数根本没被 jump 物理消费 ⇒ 假设证伪）
     · 且污染后最高点必须**更低**、腾空时间必须**更短**
  3. 负控制：**手工把参数改回 (50,1.0)** ⇒ 轨迹必须回到污染前形态。
"""
import ast
import io
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

PASS = [0]
FAIL = [0]


def check(name, ok, note=''):
    if ok:
        PASS[0] += 1
        print('[PASS] %s%s' % (name, ('  —— ' + note) if note else ''))
    else:
        FAIL[0] += 1
        print('[FAIL] %s%s' % (name, ('  —— ' + note) if note else ''))


src = io.open(MAIN, encoding='utf-8', newline='').read()
lines = src.split('\n')

print('=' * 78)
print('# 候选1 行为级复现：惊讶污染全局跳跃参数')
print('=' * 78)

# ---------- 1. 静态：全部**真写入点**（AST，非正则） ----------
# ★★★ 第96轮b 教训：首版用 `'jump_duration' in l and '=' in l` 当"写入点"，
#   把 `==`、`<=`、`getattr(self,'jump_duration',0)`、以及 `jump_duration = 1.0`
#   出现在**注释里**的都被算进来 ⇒ A2/A4/A5 三条全假红。
#   这是"判据过宽 = 误报"的又一次实例（与 95 轮 D1 同类）。
#   正确做法：走 AST，只认 `ast.Assign`/`ast.AugAssign` 且目标是
#   `self.<name>` 形式的**真赋值**。
_tree_all = ast.parse(src)
WRITES = {'jump_height': [], 'jump_duration': []}
for _node in ast.walk(_tree_all):
    _tgt = None
    if isinstance(_node, ast.Assign):
        _tgt = _node.targets
    elif isinstance(_node, ast.AugAssign):
        _tgt = [_node.target]
    if not _tgt:
        continue
    for _t in _tgt:
        if (isinstance(_t, ast.Attribute) and isinstance(_t.value, ast.Name)
                and _t.value.id == 'self' and _t.attr in WRITES):
            WRITES[_t.attr].append(_node.lineno)
for _k in WRITES:
    WRITES[_k].sort()

w_h = WRITES['jump_height']
w_d = WRITES['jump_duration']
print('\n=== A 静态写入点（AST 真赋值） ===')
print('  jump_height 写入点行号:', w_h)
print('  jump_duration 写入点行号:', w_d)

check('A1 ★★★ jump_height 全项目恰 2 个真写入点（初始化 + 惊吓）',
      len(w_h) == 2, '实测 %d 个 @ %s' % (len(w_h), w_h))
check('A2 ★★★ jump_duration 全项目恰 2 个真写入点（初始化 + 惊吓）',
      len(w_d) == 2, '实测 %d 个 @ %s' % (len(w_d), w_d))

# 惊吓分支内确实写了 20 / 0.5
#   ★★ 判据修正（首版过宽/过脆）：原来按**硬编码行号**切片 `lines[13466:13487]`，
#     而我本轮改了 main.py（插了注释）⇒ 行号漂移 ⇒ 切片取空 ⇒ A3 假红。
#     这正是记忆里的"判据里禁回显随时相变的绝对值（行号/日期）"教训。
#     ⇒ 改为**按 is_surprised 分支定位**：找到 `if self.is_surprised ...` 那个 If 节点，
#       取其源码段来查。
# ★★ 第96轮b A3 判据二次修正（`break` 取第一个 ⇒ 取错节点 ⇒ 假红）：
#   全项目有**两个** `is_surprised` 分支：
#     · 13501-13516 `if self.is_surprised and (not getattr(...).get('is_playing'))`  ← **真惊吓分支**
#     · 13981-13986 `if self.is_surprised`                                        ← 另一处（不含赋值）
#   `ast.walk` 顺序不保证，首版 `break` 抓到谁全凭运气 ⇒ 实测抓到 13981 ⇒ A3 假红。
#   ✅ 正确判据：**挑"包含写入点"的那个 If 节点**（语义上就是"写 20/0.5 的那个分支"）。
_h_write = set(w_h) | set(w_d)          # 13135 / 13514
_sur_node = None
for _nd in ast.walk(_tree_all):
    if isinstance(_nd, ast.If) and 'is_surprised' in ast.dump(_nd.test):
        if any(_nd.lineno <= _ln <= _nd.end_lineno for _ln in _h_write):
            _sur_node = _nd
            break
sur = ''
if _sur_node is not None:
    sur = '\n'.join(lines[_sur_node.lineno - 1: _sur_node.end_lineno])
check('A3 ★★ 惊吓分支把 jump_height 改成 20 且 jump_duration 改成 0.5',
      'self.jump_height = 20' in sur and 'self.jump_duration = 0.5' in sur,
      '分支行范围=%s' % (('%d-%d' % (_sur_node.lineno, _sur_node.end_lineno))
                        if _sur_node else '未找到'))

# 还原点 = 写入点里**值等于初值**的（AST 取值）
RESTORE = {}
for _k in ('jump_height', 'jump_duration'):
    RESTORE[_k] = []
for _node in ast.walk(_tree_all):
    if isinstance(_node, ast.Assign):
        for _t in _node.targets:
            if (isinstance(_t, ast.Attribute) and isinstance(_t.value, ast.Name)
                    and _t.value.id == 'self' and _t.attr in RESTORE):
                if isinstance(_node.value, ast.Constant):
                    RESTORE[_t.attr].append((_node.lineno, _node.value.value))
print('  还原候选（值 == 初值 的赋值点）:')
for _k in RESTORE:
    print('    %s: %s' % (_k, RESTORE[_k]))

# ★★ 判据修正（首版把"初始化那次赋值"也算进"还原点"⇒ 恒红）：
#   真正的语义是「**除初始化之外**，没有任何一处把它写回初值」。
#   初始化点 = 全项目**第一个**写入点（行号最小的那个）。
_init_h = w_h[0] if w_h else None
_init_d = w_d[0] if w_d else None
_h_restore = [(ln, v) for ln, v in RESTORE['jump_height']
              if v == 50 and ln != _init_h]
_d_restore = [(ln, v) for ln, v in RESTORE['jump_duration']
              if v == 1.0 and ln != _init_d]
print('  ★ 除初始化(%s/%s)之外的"还原点": height=%s duration=%s'
      % (_init_h, _init_d, _h_restore, _d_restore))

check('A4 ★★★ 除初始化外，全项目**没有任何**把 jump_height 写回 50 的语句',
      len(_h_restore) == 0, '还原点: %s' % _h_restore)
check('A5 ★★★ 除初始化外，全项目**没有任何**把 jump_duration 写回 1.0 的语句',
      len(_d_restore) == 0, '还原点: %s' % _d_restore)

# ---------- 2. 行为级：解剖真 handle_jump ----------
print('\n=== B 行为级：解剖真 handle_jump ===')
tree = ast.parse(src)
hj = None
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'handle_jump':
        hj = node
        break
check('B0 能定位到 handle_jump（真源码，非凭印象）', hj is not None)

# ★★ 第96轮b 判据修正（首版 `ast.parse(dedent(body_src))` 抛 IndentationError）：
#   根因：`handle_jump` 是**类方法**，`lines[hj.lineno-1]` 取到的 `def` 行自带 4 空格缩进，
#   而函数体更深 ⇒ `textwrap.dedent` 只削到"公共最小缩进"（= body 的 8 空格），
#   `def` 行仍留 4 空格 ⇒ 顶层 `ast.parse` 报 `unexpected indent`。
#   ✅ 正确做法：**别去解析整段**，直接用 AST 已给出的行号，
#     从**函数体第一条语句**（hj.body[0].lineno）切到 `hj.end_lineno`，
#     这段天然是"最深公共缩进"的纯函数体，dedent 后必合法。
_fh_start = hj.body[0].lineno                 # 1-based，函数体第一条语句
body_lines = lines[_fh_start - 1: hj.end_lineno]
body_only = textwrap.dedent('\n'.join(body_lines))
# 重新缩进成合法函数体
body_only = textwrap.indent(body_only, '    ')
_argnames = [a.arg for a in hj.args.args]
print('  handle_jump 形参:', _argnames)
print('  handle_jump 源码行 %d~%d（%d 行）'
      % (hj.lineno, hj.end_lineno, hj.end_lineno - hj.lineno + 1))
print('  handle_jump 函数体首行:', body_only.split('\n')[0].strip()[:80])
check('B0b ★★ handle_jump 形参 = (self, elapsed_time, current_time)',
      _argnames == ['self', 'elapsed_time', 'current_time'], '实测: %s' % _argnames)

# ★★ 第96轮b 判据三次修正（首版两点都错）：
#   ① 首版定义了一大段 STUB 字符串又 `exec` 进 ns，但下面立刻用**同名 Python 类**
#      重新定义了 `Stub` / `run`（后者覆盖前者）⇒ 那段 STUB 是**死代码**；
#   ② 挂载时写 `def handle_jump(self):` —— 真签名是 **3 参**
#      `(self, elapsed_time, current_time)` ⇒ 一调用必 TypeError（被 `except` 吞成
#      "抛异常"行，轨迹恒空 ⇒ B1/B2/B3 全假红）。
#   ✅ 现在按**真三参签名**重写 def 头。

_probe = {}
exec(compile('def handle_jump(self, elapsed_time, current_time):\n' + body_only,
             '<hj>', 'exec'), {}, _probe)
hj_fn = _probe['handle_jump']

# ★★ 第96轮b 判据四次修正（桩属性不全 ⇒ 物理核之前就 AttributeError）：
#   `handle_jump` 的真实依赖面（AST 实测）远不止跳跃参数：
#     gravity / QPoint / QRect / floor_manager / _floor_identity_key /
#     _clamp_pos_to_desktop / _sync_window_cache_from_floor / show /
#     _apply_pet_z_order / play_animation_once / change_animation / spatial_pos …
#   桩必须**逐项配齐**，否则在 L8229 `g = self.gravity` 就崩（轨迹恒空）。
#   ✅ 原则：能"返回无害值"的一律给 no-op；只有 `move()` 是**观察面**，必须真记录。


class _PT(object):
    """QPoint 只需要 .x()/.y()。"""

    def __init__(self, x, y):
        self._x, self._y = int(x), int(y)

    def x(self):
        return self._x

    def y(self):
        return self._y


class _Rect(object):
    """QRect 只需要 .intersects()。"""

    def __init__(self, x, y, w, h):
        self._x, self._y, self._w, self._h = x, y, w, h

    def intersects(self, other):
        return not (self._x + self._w <= other._x
                    or other._x + other._w <= self._x
                    or self._y + self._h <= other._y
                    or other._y + other._h <= self._y)


def QPoint(x, y):
    return _PT(x, y)


def QRect(x, y, w, h):
    return _Rect(x, y, w, h)


class _FloorMgr(object):
    """无楼层 ⇒ 穿透检查 `for floor in all_floors` 空转（到达物理核之后）"""

    def get_all_floors(self):
        return []


class Stub(object):
    def __init__(self, jh, jd, sx, sy, tx, ty):
        # —— 跳跃参数（**被测物**：桩必须原样承接，不许归一化）——
        self.jump_height = jh
        self.jump_duration = jd
        self.jump_start_pos = _PT(sx, sy)
        self.jump_target_pos = _PT(tx, ty)
        self.jump_progress = 0.0
        self.jump_start_time = 0.0
        self.jump_target_floor = None
        self.jump_target_z = 0.0
        self.jump_z_diff = 0.0
        self.jump_start_spatial = {'x': sx, 'y': sy, 'z': 0.0}
        # —— 物理常数：50 与 main.py 类属性一致 ——
        self.gravity = 50.0
        # —— 状态位 ——
        self.is_jumping = True
        self.is_falling = False
        self._jump_anim_override = None
        self.current_floor = None
        self.current_platform_z = 0
        self.spatial_pos = {'x': sx, 'y': sy, 'z': 0.0}
        self.floor_manager = _FloorMgr()
        # —— 观察面：只有 move() 记录轨迹 ——
        self._jx, self._jy = sx, sy
        self._t = 0.0
        self.MOVES = []
        self.end_jump_called = False
        self.anims = []

    # ---- 观察面 ----
    def move(self, x, y=None):
        if y is None:
            x, y = x.x(), x.y()
        self._jx, self._jy = int(x), int(y)
        self.MOVES.append((int(x), int(y)))

    # ---- 查询面 ----
    def x(self):
        return self._jx

    def y(self):
        return self._jy

    def pos(self):
        return _PT(self._jx, self._jy)

    def width(self):
        return 46

    def height(self):
        return 82

    def time(self):
        return self._t

    # ---- no-op 副作用面（不参与判据，只为让真源码跑通）----
    def show(self):
        pass

    def end_jump(self):
        self.end_jump_called = True

    def start_falling(self):
        self.is_falling = True
        self.is_jumping = False

    def change_animation(self, name, force=False):
        self.anims.append(name)

    def play_animation_once(self, name, restore_to=None):
        self.anims.append(name)

    def _apply_pet_z_order(self):
        pass

    def _sync_window_cache_from_floor(self, floor):
        pass

    def _clamp_pos_to_desktop(self, x, y):
        return x, y

    def _floor_identity_key(self, floor):
        return None if floor is None else id(floor)


Stub.handle_jump = hj_fn
# 真函数体里引用了模块级的 QPoint / QRect（`import math` 在函数内自带）
hj_fn.__globals__['QPoint'] = QPoint
hj_fn.__globals__['QRect'] = QRect


def run(jh, jd, sx, sy, tx, ty, dt=1.0 / 30.0):
    st = Stub(jh, jd, sx, sy, tx, ty)
    guard = 0
    while st.is_jumping and st._t < 5.0 and guard < 1000:
        st._t += dt
        guard += 1
        st.handle_jump(dt, st._t)
    ys = [p[1] for p in st.MOVES]
    return st, ys


SX, SY = 1000, 800
TX, TY = 1200, 600

st_a, ys_a = run(50, 1.0, SX, SY, TX, TY)
st_b, ys_b = run(20, 0.5, SX, SY, TX, TY)
st_c, ys_c = run(50, 1.0, SX, SY, TX, TY)

print('\n  污染前 (jh=50, jd=1.0): 位移点 %d  最高 y=%.1f  最低 y=%.1f'
      % (len(ys_a), min(ys_a) if ys_a else -1, max(ys_a) if ys_a else -1))
print('  污染后 (jh=20, jd=0.5): 位移点 %d  最高 y=%.1f  最低 y=%.1f'
      % (len(ys_b), min(ys_b) if ys_b else -1, max(ys_b) if ys_b else -1))

check('B1 ★★★ 参数真的被 jump 物理消费（污染前后轨迹不同）',
      ys_a != ys_b, '相同 ⇒ 假设证伪')
if ys_a and ys_b:
    # ★★ 第96轮b 判据五次修正（B2 首版语义写错 ⇒ 假红）：
    #   首版判"污染后最高点更低（min(y) 更大）" —— 但本桩把**终点 y 精确落在
    #   jump_target_pos**（T=1.0s 之内弹道还没到顶点，最高点就是落点 600）⇒
    #   两组参数的 min(y) 都 = 600 ⇒ 恒假红。
    #   ✅ 真正的可观察差异是**弹道形状**：同一 (起,终) 下，`jump_duration` 越短，
    #      `vy0` 越陡 ⇒ **飞行前段上升越快**（同 t 时刻 y 更小）。用"中途采样点"判。
    _mid_a = ys_a[len(ys_a) // 3] if len(ys_a) >= 3 else None
    _mid_b = ys_b[len(ys_b) // 3] if len(ys_b) >= 3 else None
    check('B2 ★★★ 污染后「上升更陡」（同进度处 y 更小，弹道形状真的变了）',
          _mid_a is not None and _mid_b is not None and _mid_b < _mid_a,
          '1/3 处 y：污染前 %s vs 污染后 %s' % (_mid_a, _mid_b))
    check('B3 ★★ 污染后腾空帧数更少（跳得更短）',
          len(ys_b) < len(ys_a),
          '污染前 %d 帧 vs 污染后 %d 帧' % (len(ys_a), len(ys_b)))
else:
    check('B2 污染后上升更陡', False, '轨迹为空')
    check('B3 污染后腾空更短', False, '轨迹为空')

check('B4 负控制：手工还原 (50,1.0) ⇒ 轨迹与污染前逐值一致（证明是参数在起作用）',
      ys_c == ys_a, '还原后 %d 帧 vs 污染前 %d 帧' % (len(ys_c), len(ys_a)))

# ---------- 3. ★★★ 决定性判据：jump_height 到底有没有被"读" ----------
# 上面的 A/B 只证明"写点存在 + duration 被消费"。真正决定"污染是否有害"的是：
#   `jump_height` 是否为**死变量**（写了但全项目从不读）。
# 判据设计：AST 扫**所有读取点**（Load 上下文），命中必须为 0（除赋值外）。
print('\n=== C 决定性命中：jump_height 的死活 ===')
_reads = []
for _n in ast.walk(_tree_all):
    if isinstance(_n, ast.Attribute) and isinstance(_n.value, ast.Name) \
            and _n.value.id == 'self' and _n.attr == 'jump_height' \
            and isinstance(_n.ctx, ast.Load):
        _reads.append(_n.lineno)
print('  jump_height 被"读"的 AST 位置: %s' % _reads)
check('C1 ★★★ jump_height 是**死变量**（全项目零读取 ⇒ 写它不影响任何行为）',
      len(_reads) == 0, '读取点: %s' % _reads)

# 反过来验证 duration 是**活变量**（同一手法，必须 > 0 ⇒ 证明本判据有鉴别力）
_reads_d = []
for _n in ast.walk(_tree_all):
    if isinstance(_n, ast.Attribute) and isinstance(_n.value, ast.Name) \
            and _n.value.id == 'self' and _n.attr == 'jump_duration' \
            and isinstance(_n.ctx, ast.Load):
        _reads_d.append(_n.lineno)
print('  jump_duration 被"读"的 AST 位置: %s' % _reads_d)
check('C2 ★★★ 负控制：jump_duration 是**活变量**（有读取点 ⇒ 判据有鉴别力）',
      len(_reads_d) > 0, '读取点: %s' % _reads_d)

# ★★ 第96轮b 判据六次修正（C3 首版写成 `check(..., True)` ⇒ 恒真判据，
#   被本轮复检 ④ 逮住 —— 正是"恒真判据比不写还危险"那条铁律）。
#   ✅ 改成**真有鉴别力的关系判据**：在同一物理核里，
#      `jump_height` 必须是**死变量**（零读）、`jump_duration` 必须是**活变量**（有读）
#      —— 这个"一死一活"的**反差**才是本轮结论的支点，且任一侧翻面都会报红。
check('C3 ★★★ 物理核里 jump_height(死) 与 jump_duration(活) 呈反差（结论支点）',
      (len(_reads) == 0) and (len(_reads_d) > 0),
      'height 读点 %d 个 / duration 读点 %d 个'
      % (len(_reads), len(_reads_d)))

print('\n' + '=' * 78)
print('合计  PASS=%d  FAIL=%d' % (PASS[0], FAIL[0]))
print('=' * 78)
sys.exit(1 if FAIL[0] else 0)

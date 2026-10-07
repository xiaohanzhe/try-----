# -*- coding: utf-8 -*-
u"""第95轮回归锁：`is_sleeping_walk` 的动画后缀只允许拼在 `down` 方向。

锁什么
======
第95轮的运行期 recon（`_recon/pet_run1_stdout.txt`）在真机日志里捞到两条：

    20:50:06 [anim-miss] 动画名不存在: 'walk_right_sleep' → 回退 'walk_right' (来源: update_animation)
    20:51:47 [anim-miss] 动画名不存在: 'walk_left_sleep'  → 回退 'walk_left'  (来源: update_animation)

根因（读源码，不是猜）：`animations.json` 的 115 组动画里，小憩走路**只有 `walk_down_sleep`**
（素材也只画了 `spr_ralsei_walk_down_sleep_*`）。而 `update_animation` 里

    elif self.is_sleeping_walk:            # ← 后缀选择（本函数**上游**）
        animation_suffix = "_sleep"
    ...
    if base_animation == "walk" and self.current_direction == "down" and idle_walk_timer >= 10.0:
        self.is_sleeping_walk = True       # ← 状态置真/置假在**下游**
    elif self.is_sleeping_walk:
        self.is_sleeping_walk = False

⇒ 方向刚由 `down` 变开的**那一拍**，后缀选择仍读到旧的 `True`，拼出
`walk_{left,right,up}_sleep` ⇒ 命中不到 ⇒ 静默回退 + 一条 `[anim-miss]` 告警。
第91轮修过同一缺陷类（当时只补了 `down` 的登记），本轮的 left/right/up 是**同类没收完**。

修法（`main.py`，一处）：
    elif self.is_sleeping_walk and self.current_direction == "down":

段一览
------
  A 体积口径（速查本记忆文件的"注入上限"必须按**原始字符数（含 CRLF）**判）
    A1 `recheck95mem.py` 的 `read()` 走 `newline=''`（AST 查 `io.open` 的关键字）
    A2 速查本 `MEMORY.md` 的 js_len（字节忠实）≤ 10000
    A3/A4 真口径已写进两侧（详版 §95 / 速查本页眉）
  B `_sleep` 后缀只出现在 `down`（**行为级**：解剖真源码 exec + 桩 sprite_loader）
    B1~B4 四个方向 × (is_sleeping_walk=True) ⇒ **零未命中**，且请求名分别是
          `walk_right` / `walk_left` / `walk_up` / `walk_down_sleep`
    B5 负控制（**生成式变异**：把 ` and self.current_direction == "down"` 从源码段里剥掉）
          ⇒ right 场景必须**报出** `walk_right_sleep` 未命中 ⇒ 证明 B1~B4 有鉴别力
    B6 锚点：B4 的 `down` 场景仍请求 `walk_down_sleep`（修复没有把功能一起关掉）
  C 注册表 / 素材一致性（静态）
    C1 `animations.json` 登记了 `walk_down_sleep`
    C2 未登记 `walk_left_sleep` / `walk_right_sleep` / `walk_up_sleep`
    C3 磁盘上只有 `spr_ralsei_walk_down_sleep_*.png`
    C4 全仓 `_sleep` 后缀拼接点唯一
  E 走路朝向的角度分档（**行为级**：解剖 `update_movement` 的分档链）
    E0 能抽出"按 angle 选方向"的 if 链
    E1 ★★ [-180,180) **逐整数度**与 `abs(dx)>abs(dy)` 口径一致（无缝隙、无错档）
    E2 ★★★ 真机 recon 实锤角度 40.9° 必须判 `right`（修前判 `left`）
    E3 角度带边界就位（±44/46 · 134/136）
    E4/E5 负控制：换回修复前的 `-30/60/120` 缝隙档 ⇒ E1/E2 必须翻面
  D 判据自身体检（变异保真 · 桩保真 · 恒真防护）
  F 桌面图标矩形（**真缺陷**：`LVM_GETITEMRECT` 的 `lParam` 是**传入传出**参数）
    F0/F1 方法可抽出 · `LVIR_BOUNDS` 常量 == 0（Windows SDK 值）
    F2/F3 预写 `LVIR_BOUNDS` 存在，且先于 `SendMessageW`（顺序即正确性）
    F4/F4b 循环体内**每次**把预置值重投给 `remote_rect`，且先于该次 Send
    F5 `remote_seed` 缓冲区也释放（不泄漏）
    F6/F7 两条负控制（改 `0` / 抹掉全部 `LVIR_BOUNDS`）
    ★ 真缺陷背景：不预写 ⇒ 63 个图标只量出 **10 个不同位置**（x 只覆盖两列）
      ⇒ `_pick_target` 就近选 30 个 ⇒ 宠物被吸进左上角小方块**再也出不来**
      （真机 120s 录制：目标 x 只在 17..1263、y 只在 2..130）。

★ 本套件**零 UI / 不需要显示器 / 零网络 / 零外部盘**：只读源码 + 解剖执行纯逻辑。
"""
import ast
import io
import json
import os
import re
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
# ★ 变异测试钩子：允许把被测源码指到**临时副本**上，产品文件全程只读。
MAIN_PY = (os.environ.get('CHECK95_MAIN')
           or os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'))
SPRITE_PY = os.path.join(ROOT, 'ralsei_pet', 'modules', 'sprite_loader.py')
ANIM_JSON = os.path.join(ROOT, 'ralsei_pet', 'assets', 'animations.json')
SPRITE_DIR = os.path.join(ROOT, 'deltarune_ralsei')
MEM_MD = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
DET_MD = os.path.join(ROOT, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')
RECHECK95 = os.path.join(HERE, 'recheck95mem.py')

_n = _passed = _failed = 0


def check(desc, cond, detail=''):
    global _n, _passed, _failed
    _n += 1
    if cond:
        _passed += 1
        print('[PASS] %s' % desc)
    else:
        _failed += 1
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def P(s=''):
    print(s)


def _rd(p):
    """★ 字节忠实读（`newline=''`）—— 本轮的教训本体：文本模式会吞掉 CRLF。"""
    return io.open(p, encoding='utf-8', newline='').read()


MAIN_TEXT = _rd(MAIN_PY)
SPRITE_TEXT = _rd(SPRITE_PY)


# ============================================================ 桩（必须保真）
class _Zero(object):
    """"读不到就当 0/False"的万用桩：让解剖出来的真源码能跑通。

    ⚠️ 只用于**不被判据观察**的边角属性。凡影响观察量的（`sprite_loader` /
    `change_animation` / 场景状态）一律**显式赋值**，否则就是"夹具不保真 = 报假问题"。
    """

    def __bool__(self):
        return False

    def __call__(self, *a, **k):
        return _Zero()

    def __mul__(self, o):
        return 0
    __rmul__ = __mul__

    def __add__(self, o):
        return 0
    __radd__ = __add__

    def __sub__(self, o):
        return 0

    def __rsub__(self, o):
        return 0

    def __gt__(self, o):
        return False

    def __lt__(self, o):
        return False

    def __ge__(self, o):
        return False

    def __le__(self, o):
        return False

    def __eq__(self, o):
        return False

    def __ne__(self, o):
        return True

    def __hash__(self):
        return 0

    def __getitem__(self, k):
        return 0

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0

    def __index__(self):
        return 0

    def __rtruediv__(self, o):
        return 0

    def __truediv__(self, o):
        return 0

    def __getattr__(self, n):
        return _Zero()


class _Reg(object):
    """`sprite_loader` 桩：**只**复刻本判据观察得到的两件事 —— 名字在不在、有没有未命中。"""

    def __init__(self, names):
        # 帧用 `_Zero()` 而不是字符串：渲染段会对帧调 `.isNull()` 等 QPixmap 方法，
        # 喂字符串会在**与本案无关**的渲染段炸掉（第一版就是这么崩的）。
        self.sprites = dict((n, [_Zero(), _Zero()]) for n in names)
        self.misses = []

    def note_animation_miss(self, requested, resolved=None, where=''):
        self.misses.append((requested, resolved, where))
        return resolved

    def get_frames(self, name):
        return self.sprites.get(name, [])


def _anim_group_names():
    """真源：`animations.json` 的 `groups`（真 loader 也读它）。"""
    j = json.loads(_rd(ANIM_JSON))
    return set(j.get('groups', {}).keys())


def _legacy_names():
    """真源：`sprite_loader.py` 里那个"含 `sleep` 键"的内置字典的字面量键。

    ★ 只认**含 `sleep` 键**的那个 Dict（用 AST 找），不搞全文件正则 ——
      正则会把注释/别处的字符串一起吸进来 ⇒ 注册表被吹大 ⇒ 判据失真。
    """
    tree = ast.parse(SPRITE_TEXT)
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            ks = [k.value for k in n.keys
                  if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            if 'sleep' in ks:
                return set(ks)
    return set()


REG_NAMES = _anim_group_names() | _legacy_names()


# ============================================================ 解剖真源码
def _method_src(text, cls_name, meth_name):
    tree = ast.parse(text)
    for n in tree.body:
        if isinstance(n, ast.ClassDef) and n.name == cls_name:
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name == meth_name:
                    return ast.get_source_segment(text, m), m
    return None, None


def _exec_method(seg, extra_ns=None):
    """把一段**真源码**编译进空类并返回那个类（吃源码，不吃手抄副本）。

    ★ 为什么要绕：判据若在本套件里手抄一遍同样的条件，就成"判据也是被测物"的自证循环。
    """
    if not seg:
        return None
    ns = dict(extra_ns or {})
    ded = textwrap.dedent(seg)
    body = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in ded.split('\n'))
    try:
        exec(compile(ast.parse('class _S:\n' + body), '<pure95>', 'exec'), ns)
    except Exception as e:  # pragma: no cover
        print('     [解剖失败] %r' % (e,))
        return None
    S = ns.get('_S')
    if S is not None:
        S.__getattr__ = lambda self, name: _Zero()
    return S


_LOG_STUB = type('_L', (), {'debug': lambda *a, **k: None,
                            'info': lambda *a, **k: None,
                            'warning': lambda *a, **k: None})()


def _lf(text):
    """统一到 LF。

    ★★ 踩过的坑：本仓 `main.py` 是 **CRLF**，而锚点常量若用 `\\n` 写就**永不匹配**
      ⇒ 变异体等于原文 ⇒ "变异保真"判据报红。
      所有文本锚点一律走本函数**统一换行**后再比对，杜绝这一族失配。
    """
    return text.replace('\r\n', '\n')


class _T(object):
    """替 `time` 模块：只喂 `time()`（真源码读的"当前时间"）。

    ★ 为什么必须是真数值：`update_animation` 用
      `self.idle_walk_timer += (time.time() - self._last_animation_time)`
      推进"连续下走"计时器。给桩/0 都会让增量恒为 0（见 `run_case` 的注释），
      于是"小憩走路"永远触发不了 —— 那是**夹具不保真**，会让负控制假红。

    ★★ 第95轮补（同一个实例同时当 `time` 模块与 `self.time`，**只留一个时钟**）：
      真源码里"取当前时间"走**两条路** ——
        · 方法开头的 `current_time = time.time()`（模块名 `time`）
        · 中间若干处 `self.time.time()`（实例属性 `self.time`）
      先前只注 `_T` 不注 `time` ⇒ B 段直接 `NameError`。
      两处必须是**同一个实例**，否则两个时钟各走各的，增量算出来是假的。
    """

    def __init__(self, now):
        self._now = float(now)

    def time(self):
        return self._now


def _rollback_src():
    """真源：`main.py` 里 `change_animation` 的**回退链**（那 6 行），拿去做交叉校验。

    ★★ 注意：这条**不是本套件的主观察量**。`update_animation` 自己还有**第二条**
      回退链（13598~13608，取"前两段"），`walk_right_sleep` 在调用
      `change_animation` 之前就被它折成 `walk_right` 了 ⇒ 主观察量改用
      `reg.misses` 里 `where == 'update_animation'` 的记账（见 `run_case`）。
      本函数留着做 B0c 的**交叉校验**：两条回退链对 `walk_right_sleep` 的结论
      必须一致（都折回 `walk_right`），否则说明我对代码的理解出了偏差。
    """
    text = MAIN_TEXT
    if '    def change_animation(self, new_animation, force=False):' not in text:
        return None
    # ★ 坑：本仓 `main.py` 是 **CRLF**，`split('\n')` 后每行尾巴还挂着一个 `\r`。
    #   统一先转 LF 再切，杜绝这一族失误。
    lines = _lf(text).split('\n')
    try:
        i = next(k for k, l in enumerate(lines)
                 if l.strip().startswith('if new_animation not in self.sprite_loader.sprites:'))
        j = next(k for k in range(i + 1, min(i + 60, len(lines)))
                 if 'new_animation = found' in lines[k])
    except StopIteration:
        return None
    kept = [l for l in lines[i:j + 1] if 'note_animation_miss' not in l]
    return '\n'.join(kept)


def _rollback_fn():
    """把回退链编译成 `f(registry_names, requested) -> 最终名 or None`。

    `None` = 真产品代码走到"找不到任何可回退项 ⇒ 直接拒绝切换"（= 素材缺得离谱）。
    注意 `'idle' in sprites` 那步：真实注册表里 `idle` 一定在，所以只要名字**起头**
    能对上任何已登记项就不会返 None；返 None 才说明拼出来的名字彻底不存在。
    """
    src = _rollback_src()
    if not src:
        return None
    lines = src.split('\n')
    base = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    flat = [(l[base:] if l.strip() else '') for l in lines]
    body = '\n'.join(('    ' + l) if l.strip() else '' for l in flat)
    # ★ 真源码里引用了 `self.sprite_loader.sprites` ⇒ 必须给它一个 `self`。
    #   于是签名是 `f(sprites, new_animation)`：内部把 `self` 造成一个只有
    #   `sprite_loader.sprites` 的薄壳，其余一律不提供（免得判据偷偷依赖别的属性）。
    code = ('def _f(sprites, new_animation):\n'
            '    self = type("_Sl", (), {"sprite_loader":\n'
            '        type("_S", (), {"sprites": sprites})()})()\n'
            + body + '\n    return new_animation\n')
    ns = {}
    try:
        exec(compile(code, '<roll95>', 'exec'), ns)
    except Exception as e:  # pragma: no cover
        print('     [回退链解剖失败] %r' % (e,))
        return None
    return ns.get('_f')


def run_case(direction, sleeping_walk, timer, main_text=None, dt=0.0):
    """跑一次真 `update_animation`，返回 `(请求名, 未命中列表)`。

    `dt` = 本帧时间增量（喂给解剖体的 `time.time()` 与 `_last_animation_time` 之差）。
    默认 0 ⇒ `idle_walk_timer` 不推进，于是"小憩走路"不会由计时器自行置真，
    判据喂进来的 `sleeping_walk` 完全由被测源码的状态机决定命运（夹具可控）。

    桩只喂"本判据观察得到"的东西：`sprite_loader`（名字存在性 + 未命中记账）、
    `current_animation`（真值必须是已登记的字符串，否则 `startswith/split` 语义不同）、
    以及 `change_animation` 的记账。
    """
    text = MAIN_TEXT if main_text is None else main_text
    seg, _ = _method_src(text, 'RalseiPet', 'update_animation')
    # ★★ 第95轮补（夹具保真，踩过两次的坑）：注入名必须**同时**含 `time`
    #   与 `_T`。真源码里两处都在用：
    #     · 方法开头 `current_time = time.time()` —— 走模块名 `time`
    #     · `self.idle_walk_timer` 的增量基准 `self._last_animation_time`
    #   只注 `_T` ⇒ `NameError: name 'time' is not defined`（本轮实测崩在 B 段）。
    #   `_T` 自带 `time()`，因此**同一个实例**同时充当 `time` 模块与 `_T`，
    #   保证"取当前时间"这条路径只有一份真值（不出现两个时钟）。
    _clock = _T(float(dt))
    S = _exec_method(seg, {'_log': _LOG_STUB, 'math': __import__('math'),
                           'random': __import__('random'),
                           'time': _clock, '_T': _clock})
    if S is None:
        return None, None
    reg = _Reg(REG_NAMES)
    o = S()
    o.sprite_loader = reg
    o.current_animation = 'walk_down'
    o.current_frame = 0
    o.is_moving = True
    o.is_sleeping = False
    o.is_sleeping_walk = bool(sleeping_walk)
    o.current_direction = direction
    o.current_speed_x = 0.1
    o.current_speed_y = 0.0
    o.speed = 10
    o.idle_walk_timer = float(timer)
    o.is_wearing_suit = False
    o.is_holding_cotton_candy = False
    o.is_shy = False
    o.is_unhappy = False
    o._last_perf_anim_time = 0.0
    # ★★ 第95轮补（**夹具保真**，本段记录一个踩过的坑）：
    #   ① `_last_animation_time` 与 `time.time()` 都必须给**真数值**，否则
    #      `idle_walk_timer += (当前时间 - 上次时间)` 的增量为 0 —— 桩不设
    #      `_last_animation_time` 时回落到 `_Zero`，`0 - _Zero = 0`。
    #   ② 但"让自增真正发生"**并不总是对**：见 `_strip_order` 的注释 ——
    #      B6 的变异体（把顺序倒回修复前）在**正增量**下会被"清假分支"当场抹平，
    #      于是负控制假红。⇒ 这里把增量**暴露成参数**，由调用方按变异种类选：
    #        · 测"守卫" 的变异 → `dt=0`（自增无害，让守卫成为唯一拦路者）
    #        · 测"顺序" 的变异 → `dt=9.0`（让"倒回旧顺序"真的能读到陈旧 True）
    o._last_animation_time = 0.0
    o.time = _clock
    # ★★★ 观察量接线（第 4 版，终于对了 —— 前 3 版都测错了对象，务必读完）：
    #
    #   `change_animation` 收到的名字**不是**上游拼出来的名字！`update_animation`
    #   在拼接点（13464）之后还有**第二条回退链**（13598~13608）：
    #       if new_animation not in self.sprite_loader.sprites:
    #           base_anim = 前两段（walk_right_sleep → walk_right）
    #           self.sprite_loader.note_animation_miss(new_animation, base_anim, 'update_animation')
    #           new_animation = base_anim
    #   ⇒ `walk_right_sleep` 在**调用 `change_animation` 之前**就被折成 `walk_right` 了。
    #   这解释了真机日志里那个 `(来源: update_animation)` 从哪来 —— 就是 13607 这行。
    #
    #   ⇒ 正确的观察量 = **这条回退链有没有被触发**（它一旦触发，就说明上游真的
    #     拼出了一个不存在的名字）。它由**产品源码**决定是否触发、并传入**真参数**；
    #     我的桩只提供 `note_animation_miss` 这个接口来收下这三个真值。
    #     （前一版把"名字在不在"交给我的名单判 ⇒ 测的是夹具；这一版交给产品代码判。）
    #
    #   ⚠️ 另注意 13592 `if ... and self.current_animation != new_animation:` ——
    #      只有"新名字 ≠ 当前名字"才进回退链。夹具设 `current_animation='walk_down'`，
    #      而本段观察的都是 `walk_{right,left,up}_sleep` 或 `walk_down_sleep`，
    #      都不等于它 ⇒ 回退链一定进得去（不需要额外调夹具）。
    req = []
    o.change_animation = lambda name, *a, **k: (req.append(name), True)[1]
    o.update_animation()
    # 只认 `来源 == update_animation` 的记账（排掉别处可能产生的同源噪声）。
    _miss_fn = [m for m in reg.misses if m[2] == 'update_animation']
    if _miss_fn:
        # 回退链触发过 ⇒ 上游确实拼出了不存在的名字（真值就在记账里）。
        raw = _miss_fn[0][0]
        final = _miss_fn[0][1]
    elif req:
        raw = final = req[0]
    else:
        # 本帧被 `drag_delay` 挡掉（提前 return）或走到别的分支 ⇒ 无观察值。
        return None, None, reg.misses
    return raw, final, reg.misses


# 真回退链（解剖自产品源码）——留作交叉校验，不必参与主观察量。
_RB = _rollback_fn()


NO_GUARD = ' and self.current_direction == "down"'


def _strip_guard(text):
    """**生成式**负控制：把本轮加的那半截条件从源码里抠掉（不落盘、不动产品文件）。"""
    return _lf(text).replace(
        'elif self.is_sleeping_walk and self.current_direction == "down":',
        'elif self.is_sleeping_walk:')


_ORDER_BLOCK_LF = (
    '            # 小憩走路状态：连续"向下走"10 秒进入。\n'
    '            # 修复（本就有的那条）：原逻辑只置真不清假——一旦进入就永久播"梦游走路帧"。\n'
    '            # 只要不是"向下 walk"（方向变了/跑起来/动作被覆盖）就退出小憩。\n'
    '            if base_animation == "walk" and self.current_direction == "down" and self.idle_walk_timer >= 10.0:\n'
    '                self.is_sleeping_walk = True\n'
    '            elif self.is_sleeping_walk:\n'
    '                self.is_sleeping_walk = False\n'
    '                self.idle_walk_timer = 0\n'
)
_INC_LF = ('            self.idle_walk_timer += '
           '(current_time - self._last_animation_time)\n\n')
_ANCHOR_LF = '            # 检查是否触发惊讶事件\n'


def _strip_order(text):
    """**生成式**负控制：把计时器自增 + `is_sleeping_walk` 置位块**移回拼接点之后**。

    这正是修复前的顺序。为什么必须用"移动"而不是"删除"：判据要测的是
    **顺序**（先算再读 vs 先读再算），删掉它就变成"功能被关了"，测错了对象。
    ★ 若将来重排了这段代码（缩进/注释变化），本函数会**静默失配** ⇒
      另有 B5 断言 `_mut_o != MAIN_TEXT` 兜住（失配即报红，不会假装通过）。
    """
    t = _lf(text)
    if _ORDER_BLOCK_LF not in t or _INC_LF not in t or _ANCHOR_LF not in t:
        return text                       # 失配 ⇒ 交给 B5 的"变异保真"报红
    t = t.replace(_INC_LF, '', 1).replace(_ORDER_BLOCK_LF, '', 1)
    t = t.replace(_ANCHOR_LF, _INC_LF + _ORDER_BLOCK_LF + '\n' + _ANCHOR_LF, 1)
    return t


# ============================================================ A. 体积口径
P('=' * 78)
P('A. 体积口径（注入上限按**原始字符数（含 CRLF）**判）')
P('=' * 78)

_t = ast.parse(_rd(RECHECK95))
_read_uses_newline = False
for n in ast.walk(_t):
    if isinstance(n, ast.FunctionDef) and n.name == 'read':
        for c in ast.walk(n):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
                    and c.func.attr == 'open':
                for kw in c.keywords:
                    if kw.arg == 'newline':
                        _read_uses_newline = True
check('A1 `recheck95mem.py` 的体积读数走 `newline=\'\'`（字节忠实）',
      _read_uses_newline, '未在 read() 的 io.open(...) 里找到 newline 关键字')

_mem = _rd(MEM_MD)
_js = sum(2 if ord(c) > 0xFFFF else 1 for c in _mem)
check('A2 速查本 `MEMORY.md` js_len ≤ 10000（含 CRLF 的真口径）',
      0 < _js <= 10000, 'js_len=%d  chars=%d  余量=%+d' % (_js, len(_mem), 10000 - _js))
check('A3 详版已登记真口径（`newline=\'\'`）', "newline=''" in _rd(DET_MD))
check('A4 速查本页眉已写清真口径（`newline=\'\'`）', "newline=''" in _mem)

# ============================================================ B. 行为级
P('')
P('=' * 78)
P('B. `_sleep` 后缀只允许出现在 `down`（解剖真源码执行）')
P('=' * 78)

_seg, _node = _method_src(MAIN_TEXT, 'RalseiPet', 'update_animation')
check('B0 `update_animation` 可从真源码抽出', bool(_seg),
      '法名/类名变了？')
check('B0b `update_animation` 内的**第二条回退链**可从真源码抽出（B 段观察量的真源）',
      _RB is not None, '解剖失败 —— B 段整段失去鉴别力，必须修')
check('B0c 夹具保真：真回退链能识别"不存在的名字"（`walk_right_sleep` ⇒ `walk_right`）',
      _RB is not None and _RB(REG_NAMES, 'walk_right_sleep') == 'walk_right'
      and _RB(REG_NAMES, 'walk_right') == 'walk_right',
      'sleep 名 ⇒ %r ；真名 ⇒ %r'
      % (_RB(REG_NAMES, 'walk_right_sleep') if _RB else None,
         _RB(REG_NAMES, 'walk_right') if _RB else None))

CASES = [
    ('right', 'walk_right'),
    ('left', 'walk_left'),
    ('up', 'walk_up'),
    ('down', 'walk_down_sleep'),
]
for _d, _want in CASES:
    _timer = 999.0 if _d == 'down' else 0.0
    _raw, _fin, _miss = run_case(_d, True, _timer)
    if _d == 'down':
        # ★ 正控：down + 计时器过 10s ⇒ 必须真的拼出（且回退链认可）`walk_down_sleep`。
        #   否则就是"修复把功能一起关掉了"，而这在 B3/B4 里**看不出来**。
        check('B1 `down` + 连续下走（timer>=10）⇒ 上游拼出 `%s`，且回退链**不动**它'
              % _want, _raw == _want and _fin == _want,
              '上游=%r 落地=%r' % (_raw, _fin))
        check('B2 `down` 场景零未命中（`is_sleeping_walk` 不留假账）',
              _miss == [], '未命中 = %r' % (_miss,))
    else:
        check('B3 `%s` + is_sleeping_walk ⇒ **上游就不该拼出** `%s_sleep`'
              % (_d, _d), _raw == _want, '上游实际拼出 = %r' % (_raw,))
        check('B4 `%s` 场景：回退链无须干预 + 零未命中（不再产生 [anim-miss] 噪声）'
              % _d, _fin == _want and _miss == [],
              '落地=%r 未命中=%r' % (_fin, _miss))

# ---- 负控制（★★★ 本套件最难写对的一段，记下三代失败与最终口径）----
#
# ★★★ 核心洞察（用两代失败的负控制换来，务必读懂再动）：
#   第95轮对 `is_sleeping_walk` 其实上了**两道防线**：
#     防线①「顺序」：计时器自增 + 置位/清假发生在**后缀选择之前** ⇒ 方向变开的那拍
#        `elif self.is_sleeping_walk:` 当场清假，后续拼接读到的是 False；
#     防线②「`down` 守卫」：`elif self.is_sleeping_walk and self.current_direction == "down":`
#        ⇒ 即便标志残留 True，非 down 也拼不出 `_sleep`。
#   ⇒ **任一单拆都不会漏**：
#     · 只拆①（倒回旧顺序，守卫留着）⇒ 读到陈旧 True 但被守卫拦住 ⇒ 仍是 `walk_right`；
#     · 只拆②（抠守卫，顺序留着）⇒ 清假在拼接之前 ⇒ 仍是 `walk_right`；
#     · **两道同拆** ⇒ 才复现"拼出 `walk_right_sleep`"的原始缺陷。
#   前三代负控制都只拆了一道 ⇒ 天然看不到差异 ⇒ 假绿/假红。
#   本段因此用"**两道同拆**"的变异体，并额外各留一条"单拆不对"的**边界**判据，
#   把"两道防线各管一段"这件事本身也钉住（防止将来有人删掉其中一道还以为没差）。
_mut_g = _strip_guard(MAIN_TEXT)                      # 只拆②（守卫）
_mut_o = _strip_order(MAIN_TEXT)                      # 只拆①（顺序）
_mut_go = _strip_guard(_mut_o)                        # ① ② 同拆
check('B5 变异保真：三种变异体都确实改了源码，且互不相同',
      _mut_g != MAIN_TEXT and _mut_o != MAIN_TEXT and _mut_go != MAIN_TEXT
      and len({_mut_g, _mut_o, _mut_go}) == 3,
      'g=%s o=%s go=%s' % (_mut_g != MAIN_TEXT, _mut_o != MAIN_TEXT,
                           _mut_go != MAIN_TEXT))

# 工况：`right` 方向 + 陈旧 `is_sleeping_walk=True` + dt=9
#   （dt=9 让 `idle_walk_timer` 跨过 10s 门槛附近，且让"清假"这一拍真的发生；
#    计时器门槛本身不影响本组观察量 —— 拼接只看标志与方向。）
# ★★ 变量命名避坑：全局判据计数器叫 `_n`，本段**绝不能**再用 `_n` 当局部名，
#   否则 `check()` 里的 `global _n; _n += 1` 会撞上被覆盖成 tuple 的同名变量
#   ⇒ `TypeError: can only concatenate tuple (not "int") to tuple`（本轮实测踩到）。
_r_go = run_case('right', True, 0.0, main_text=_mut_go, dt=9.0)   # 两道同拆
_r_g = run_case('right', True, 0.0, main_text=_mut_g, dt=9.0)     # 只拆守卫
_r_o = run_case('right', True, 0.0, main_text=_mut_o, dt=9.0)     # 只拆顺序
_r_n = run_case('right', True, 0.0, dt=9.0)                       # 正体（两道都在）

check('B6 ★★★ 负控制·核心：两道防线**同拆** ⇒ 上游必须拼出 `walk_right_sleep`'
      '（不复现 ⇒ 说明正体那两道防线里有一道本来就是多余的，本判据失去意义）',
      _r_go[0] == 'walk_right_sleep', '两道同拆后上游 = %r' % (_r_go[0],))
check('B6b 负控制·闭合：同拆变异体的 `walk_right_sleep` 必须被真回退链折回 `walk_right`'
      '（这条接上真机 recon 里那条 `[anim-miss]` 日志的同一路径）',
      _r_go[1] == 'walk_right', '同拆后落地 = %r' % (_r_go[1],))
check('B7 ★★ 边界：**只拆守卫**（顺序留着）⇒ 上游仍必须是 `walk_right`'
      '（证明"顺序"这道防线独立成立，不是靠守卫兜底）',
      _r_g[0] == 'walk_right', '只拆守卫后上游 = %r' % (_r_g[0],))
check('B8 ★★ 边界：**只拆顺序**（守卫留着）⇒ 上游仍必须是 `walk_right`'
      '（证明"守卫"这道防线独立成立，不是靠顺序兜底）',
      _r_o[0] == 'walk_right', '只拆顺序后上游 = %r' % (_r_o[0],))
check('B9 恒真防护：正体与"两道同拆"必须**不同**，且正体必须干净',
      _r_n[0] == 'walk_right' and _r_go[0] != _r_n[0]
      and _r_go[1] == _r_n[1] == 'walk_right',
      '正体上游=%r 正体落地=%r 同拆上游=%r 同拆落地=%r'
      % (_r_n[0], _r_n[1], _r_go[0], _r_go[1]))

# ============================================================ C. 注册表/素材
P('')
P('=' * 78)
P('C. 注册表 / 素材一致性（静态）')
P('=' * 78)
check('C1 `animations.json` 登记了 `walk_down_sleep`', 'walk_down_sleep' in _anim_group_names())
_missing_dirs = [d for d in ('walk_left_sleep', 'walk_right_sleep', 'walk_up_sleep')
                 if d in REG_NAMES]
check('C2 三个方向的小憩走路**未**登记（与"素材没画"一致）',
      not _missing_dirs, '竟然登记了 = %s' % _missing_dirs)
_pngs = set(os.listdir(SPRITE_DIR)) if os.path.isdir(SPRITE_DIR) else set()
check('C3 磁盘上只有 `down` 的小憩走路素材',
      ('spr_ralsei_walk_down_sleep_0.png' in _pngs)
      and not any(('walk_%s_sleep' % d) in ' '.join(_pngs)
                  for d in ('left', 'right', 'up')),
      'down=%s  其它方向=%s'
      % ('spr_ralsei_walk_down_sleep_0.png' in _pngs,
         [p for p in _pngs if '_sleep' in p and 'walk_down' not in p]))
_n_sleep_suffix = len(re.findall(r'animation_suffix = "_sleep"', MAIN_TEXT))
check('C4 全仓 `main.py` 里 `_sleep` 后缀拼接点唯一', _n_sleep_suffix == 1,
      '出现 %d 次' % _n_sleep_suffix)

# ============================================================ E. 走路朝向分档
P('')
P('=' * 78)
P('E. 走路朝向的角度分档必须无缝隙，且与 `abs(dx)>abs(dy)` 口径**逐度一致**')
P('=' * 78)


def _angle_chains(text):
    """`update_movement` 内**所有**"按 angle 选方向"的 if 链（只取链头，不含 elif 续接）。

    ★★ 为什么要"全部"：`update_movement` 里其实有**两条** angle 分档 ——
      L7057 那段"跟随被拖拽文件"用的是正确的对称档，L7247 那段"正常走路"用的是
      带缝隙的档。首版只按"跨度最大"挑一条 ⇒ **可能挑中正确的那条**，
      于是修复前的源码也能全绿（A/B 实测暴露：A 侧 25 PASS，E 段一条没红）。
      这就是速查本 §4 的「**判据过宽/不确定 = 误报的对偶**」。
    """
    seg, _ = _method_src(text, 'RalseiPet', 'update_movement')
    if not seg:
        return []
    ded = textwrap.dedent(seg)
    tree = ast.parse(ded)
    ifs = [n for n in ast.walk(tree) if isinstance(n, ast.If)]
    cont = set()
    for n in ifs:
        for o in n.orelse:
            if isinstance(o, ast.If):
                cont.add(id(o))
    out, seen = [], set()
    for n in ifs:
        if id(n) in cont:
            continue
        test_src = ast.get_source_segment(ded, n.test) or ''
        src = ast.get_source_segment(ded, n) or ''
        if 'angle' not in test_src or 'new_dir' not in src:
            continue
        key = (n.lineno, n.col_offset)
        if key in seen:
            continue
        seen.add(key)
        out.append(src)
    out.sort(key=lambda s: len(s), reverse=True)
    return out


def _angle_fn(chain):
    """把 if 链包成纯函数 `f(angle) -> new_dir`（吃源码，不吃手抄副本）。

    ★★ 坑：`ast.get_source_segment` 会**削掉首行缩进、却保留后续行的绝对缩进**
      ⇒ 若直接给整块统一加 4 格，第二行起（原 24 格）与首行（现 4 格）对不上，
      `IndentationError`。必须先按"**后续行的最小缩进**"把整块压平再统一加。
      （`_exec_method` 侥幸没炸是因为函数体的块缩进只要"比 def 更深"即可。）
    """
    if not chain:
        return None
    lines = chain.split('\n')
    rest = [l for l in lines[1:] if l.strip()]
    base = min((len(l) - len(l.lstrip()) for l in rest), default=0)
    flat = [lines[0].strip()] + [(l[base:] if l.strip() else '') for l in lines[1:]]
    body = '\n'.join(('    ' + l) if l.strip() else '' for l in flat)
    src = 'def _f(angle):\n    new_dir = None\n' + body + '\n    return new_dir\n'
    ns = {}
    try:
        exec(compile(src, '<dir95>', 'exec'), ns)
    except Exception as e:  # pragma: no cover
        print('     [分档解剖失败] %r' % (e,))
        return None
    return ns.get('_f')


def _expect_abs(a):
    """本文件其余四处同款的 `abs(dx) > abs(dy)` 口径给出的期望方向。

    ★ 正 45 度线上 `|dx| == |dy|` ⇒ 两个方向并列，返回 None（由 `ADJ` 放宽）。
    """
    m = __import__('math')
    dx = m.cos(m.radians(a))
    dy = m.sin(m.radians(a))
    if abs(abs(dx) - abs(dy)) <= 1e-9:
        return None
    if abs(dx) > abs(dy):
        return 'right' if dx > 0 else 'left'
    return 'down' if dy > 0 else 'up'


ADJ = {45: ('right', 'down'), 135: ('down', 'left'),
       -135: ('up', 'left'), -45: ('right', 'up')}


def _scan(fn):
    """[-180, 180) 逐整数度比对；返回 (错例, 检查数)。"""
    bad = []
    for a in range(-180, 180):
        got = fn(float(a))
        exp = _expect_abs(a)
        if exp is None:
            if got not in ADJ.get(a, ()):
                bad.append((a, got, 'tie'))
        elif got != exp:
            bad.append((a, got, exp))
    return bad, 180


_CHAINS = _angle_chains(MAIN_TEXT)
_FNS = [_angle_fn(c) for c in _CHAINS]
check('E0 `update_movement` 内能抽出 "按 angle 选方向" 的分档链（≥1）',
      len(_CHAINS) >= 1 and all(f is not None for f in _FNS),
      '抽出 %d 条' % len(_CHAINS))
print('     抽出 %d 条（人可复核首行）：' % len(_CHAINS))
for _i, _c in enumerate(_CHAINS):
    print('       [%d] %s' % (_i, _c.split('\n')[0].strip()))

if _FNS and all(f is not None for f in _FNS):
    _per = [_scan(f) for f in _FNS]
    _nb = [len(b) for b, _ in _per]
    check('E1 ★★★ **每一条**分档链都必须与 `abs(dx)>abs(dy)` 口径**逐度一致**'
          '（360 整数度 × 全部链条）',
          all(n == 0 for n in _nb),
          '各链错度数 = %s ；首条错例 %s' % (_nb, _per[0][0][:4]))
    check('E2 ★★★ 真机 recon 实锤角度 40.9°（目标 (1877,1196) · 起点 x=594 一路 +x）'
          '在**每一条**链上都必须判 `right`',
          all(f(40.9) == 'right' for f in _FNS),
          '各链 40.9° = %s' % [f(40.9) for f in _FNS])
    _f0 = _FNS[_CHAINS.index(max(_CHAINS, key=len))] if _CHAINS else None
    check('E3 角度带边界就位（44/46 · 134/136 · -44/-46）',
          _f0(44.0) == 'right' and _f0(46.0) == 'down'
          and _f0(134.0) == 'down' and _f0(136.0) == 'left'
          and _f0(-44.0) == 'right' and _f0(-46.0) == 'up',
          '44=%r 46=%r 134=%r 136=%r -44=%r -46=%r'
          % (_f0(44.0), _f0(46.0), _f0(134.0), _f0(136.0),
             _f0(-44.0), _f0(-46.0)))

    # ---- 负控制：把分档换回第95轮修复前的 `-30/60/120` 缝隙档（生成式，不动产品文件）----
    _tgt = next((c for c in _CHAINS if '-45 <= angle < 45' in c), _CHAINS[0])
    _old_chain = (_tgt.replace('-45 <= angle < 45', '-30 <= angle < 30')
                  .replace('45 <= angle < 135', '60 <= angle < 120')
                  .replace('-135 <= angle < -45', '-120 <= angle < -60'))
    check('E4 负控制·夹具保真：把所选链换回修复前的 `-30/60/120` 后源码确实变了',
          _old_chain != _tgt)
    _old_fn = _angle_fn(_old_chain)
    _old_bad = _scan(_old_fn)[0] if _old_fn is not None else []
    check('E5 负控制：旧缝隙档**必须**在 40.9° 判 `left`，且逐度比对必须报错'
          '（证明 E1/E2 有鉴别力）',
          _old_fn is not None and _old_fn(40.9) == 'left' and len(_old_bad) > 0,
          '旧档 40.9° = %r ；逐度错 %d 个'
          % (_old_fn(40.9) if _old_fn else None, len(_old_bad)))

# ============================================================ D. 判据自身体检
P('')
P('=' * 78)
P('D. 判据自身体检')
P('=' * 78)

check('D1 桩保真：注册表里 `walk_right` 在、`walk_right_sleep` 不在',
      ('walk_right' in REG_NAMES) and ('walk_right_sleep' not in REG_NAMES),
      '注册表 %d 项' % len(REG_NAMES))
check('D2 桩保真：注册表规模与 `animations.json` 组数同量级',
      len(REG_NAMES) >= len(_anim_group_names()) >= 100,
      'REG=%d  groups=%d' % (len(REG_NAMES), len(_anim_group_names())))
# ★★ 第95轮修（**恒真判据**）：D3 原来写 `check(..., True)` —— 本意是"no-op 显式打印"，
#   但它**没有任何鉴别力**，且会被本仓库的"恒真防护"（`check93` E1 那种自检）报红。
#   改成**真判据**：四方向的「上游名 → 落地名」必须满足**成对关系** ——
#     · `right/left/up`：上游 == 落地（守卫 + 顺序两道防线生效 ⇒ 压根不拼 `_sleep`）；
#     · `down`        ：上游 == `walk_down_sleep` == 落地（功能没被顺手关掉）。
#   这样"打印"与"断言"合一：既留了人可复核的实况，又真的在守行为。
_r_right = run_case('right', True, 0.0)
_r_left = run_case('left', True, 0.0)
_r_up = run_case('up', True, 0.0)
_r_down = run_case('down', True, 999.0)
check('D3 ★★ 四方向「上游名 → 落地名」成对关系正确（非 no-op：'
      'right/left/up 上游==落地且**不含** `_sleep`；down 保留 `walk_down_sleep`）',
      _r_right[0] == _r_right[1] == 'walk_right'
      and _r_left[0] == _r_left[1] == 'walk_left'
      and _r_up[0] == _r_up[1] == 'walk_up'
      and _r_down[0] == _r_down[1] == 'walk_down_sleep')
P('     right=%r→%r  left=%r→%r  up=%r→%r  down=%r→%r'
  % (_r_right[0], _r_right[1], _r_left[0], _r_left[1],
     _r_up[0], _r_up[1], _r_down[0], _r_down[1]))

# ============================================================ F. 桌面图标矩形
# ★★★ 第95轮真缺陷：`LVM_GETITEMRECT` 的 `lParam` 是**传入传出**参数 ——
#   调用方必须先在远程缓冲区里预置 `LVIR_*`（这里要包围盒 = `LVIR_BOUNDS` = 0），
#   控件再按该模式把矩形**写回同一块内存**。原实现分配完远程内存**从不预写**，
#   控件读到残留值 ⇒ **63 个图标只量出 10 个不同位置**（x 只覆盖两列）
#   ⇒ `AutonomousAgent._pick_target` 就近选 30 个 ⇒ 宠物被吸进左上角小方块出不来的真凶。
#   真机实测对照（同一秒、同一进程，仅此一处变量）：
#     不预写：唯一坐标 10/63，x∈[0,115]
#     预写 0：唯一坐标 63/63，x∈[0,690]，且与 `LVM_GETITEMPOSITION` 逐项一致
P('')
P('=' * 78)
P('F. 桌面图标矩形（`LVM_GETITEMRECT` 的 `LVIR_BOUNDS` 预写）')
P('=' * 78)

DESKTOP_PY = os.path.join(ROOT, 'ralsei_pet', 'modules', 'desktop_interaction.py')
with io.open(DESKTOP_PY, encoding='utf-8', newline='') as _fh:
    DESK_TEXT = _fh.read()


def _desktop_method_src(name):
    """从 `desktop_interaction.py` 里抽出某个顶层类方法（含所有嵌套块）。"""
    try:
        tree = ast.parse(DESK_TEXT)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(DESK_TEXT, node)
    return None


_F_SRC = _desktop_method_src('get_desktop_icon_rects')
if _F_SRC is None:
    # 方法名可能不同 ⇒ 退化为"任一含 LVM_GETITEMRECT 的方法"
    for node in ast.walk(ast.parse(DESK_TEXT)):
        if isinstance(node, ast.FunctionDef):
            seg = ast.get_source_segment(DESK_TEXT, node) or ''
            if 'LVM_GETITEMRECT' in seg:
                _F_SRC = seg
                break

check('F0 能从 `desktop_interaction.py` 抽出使用 `LVM_GETITEMRECT` 的方法',
      bool(_F_SRC and 'LVM_GETITEMRECT' in _F_SRC))

# ---- F1 常量就位：`LVIR_BOUNDS` 必须存在且 == 0（Win32 官方值，不是随手编的）
check('F1 `LVIR_BOUNDS` 常量存在且 == 0（Windows SDK 值）',
      re.search(r'^LVIR_BOUNDS\s*=\s*0\s*$', DESK_TEXT, re.M) is not None,
      '命中 %d 次' % len(re.findall(r'^LVIR_BOUNDS\s*=\s*0\s*$', DESK_TEXT, re.M)))

if _F_SRC:
    _F_LF = _lf(_F_SRC)
    # ---- F2 ★★★ 核心：调用 `SendMessageW(..., LVM_GETITEMRECT, ...)` 之前，
    #      必须先有把 `LVIR_BOUNDS` 写进远程缓冲的动作（`seed.left = LVIR_BOUNDS`
    #      + `WriteProcessMemory(..., remote_rect, ...)`）。
    #      判据形态：AST 找 `SendMessageW` 调用行号，找"预写 LVIR_BOUNDS"的
    #      `WriteProcessMemory` 调用行号，要求前者**晚于**后者。
    _seed_assign = re.search(r'\.left\s*=\s*LVIR_BOUNDS', _F_LF)
    _writes = list(re.finditer(r'WriteProcessMemory', _F_LF))
    _send = list(re.finditer(r'SendMessageW\s*\(\s*\S+\s*,\s*LVM_GETITEMRECT', _F_LF))
    check('F2 ★★★ 预写 `LVIR_BOUNDS` 的动作存在（`seed.left = LVIR_BOUNDS`）',
          _seed_assign is not None)
    check('F3 ★★★ 预写发生在 `SendMessageW(LVM_GETITEMRECT)` **之前**（顺序即正确性）',
          bool(_seed_assign and _writes and _send
               and min(m.start() for m in _writes) < _send[0].start()),
          '预写@%s Send@%s'
          % (min([m.start() for m in _writes]) if _writes else None,
             _send[0].start() if _send else None))
    # ---- F4 ★★ 循环体内每次都要把预置值**重投**给 `remote_rect`
    #      （控件会回写 `remote_rect` ⇒ 只写一次会从第二个图标起失效）。
    #      ★ 判据修正（首版写错、实测抓出）：预写模板 `seed.left = LVIR_BOUNDS`
    #        在循环**外**造（这没问题），真正要在循环**体内**的是
    #        `WriteProcessMemory(..., remote_rect, ..., byref(local_rect), ...)`。
    _loop = re.search(r'for\s+i\s+in\s+range\(\s*count\s*\)\s*:', _F_LF)
    _body = _F_LF[_loop.start():] if _loop else ''
    _reinject = re.search(r'WriteProcessMemory\(\s*\n?[^\n]*remote_rect[^\n]*\n?[^\n]*local_rect',
                          _body)
    check('F4 ★★ 循环体内每次把预置值重投给 `remote_rect`（`WriteProcessMemory(…remote_rect…local_rect…)`）',
          bool(_loop and _reinject),
          '循环内命中=%s' % bool(_reinject))
    # ---- F4b ★★ 投给 `remote_rect` 的动作必须在 `SendMessageW` **之前**
    _send_in_body = re.search(r'SendMessageW', _body)
    check('F4b ★★ 重投发生在该次 `SendMessageW` 之前（顺序即正确性）',
          bool(_reinject and _send_in_body
               and _reinject.start() < _send_in_body.start()),
          '重投@%s Send@%s'
          % (_reinject.start() if _reinject else None,
             _send_in_body.start() if _send_in_body else None))
    # ---- F5 ★★ 缓冲区释放成对（`remote_seed` 也要 `VirtualFreeEx`，否则句柄泄漏）
    check('F5 ★★ `remote_seed` 缓冲区也走 `VirtualFreeEx`（不泄漏）',
          ('remote_seed' in _F_LF
           and re.search(r'VirtualFreeEx\([^)]*remote_seed', _F_LF) is not None))
    # ---- F6 ★★ 负控制（生成式变异）：把 `seed.left = LVIR_BOUNDS` 改成 `0`
    #      ⇒ 常量判据必须翻面（证明 F2 真有鉴别力，不是恒真）
    _mut = _F_LF.replace('seed.left = LVIR_BOUNDS', 'seed.left = 0', 1)
    check('F6 负控制：把 `seed.left = LVIR_BOUNDS` 改成 `0` ⇒ 预写判据必须翻面',
          re.search(r'\.left\s*=\s*LVIR_BOUNDS', _mut) is None,
          '变异体长度 %d（原文 %d）' % (len(_mut), len(_F_LF)))
    # ---- F7 ★★★ 负控制（语义级）：把方法段里**全部** `LVIR_BOUNDS` 抹掉
    #      ⇒ "预写 LVIR_BOUNDS"这条路彻底消失（原文必须含、抹后必须不含）。
    #      ★ 判据修正（首版只删 1 处 ⇒ 常量定义仍在 ⇒ 抠后仍含 ⇒ 假红）。
    _stripped = _F_LF.replace('LVIR_BOUNDS', 'X_LVIR_REMOVED')
    check('F7 ★★★ 抹掉全部 `LVIR_BOUNDS` 后源码确实不再含它（证明 F2/F3 指向的就是这条路径）',
          ('LVIR_BOUNDS' not in _stripped) and ('LVIR_BOUNDS' in _F_LF),
          '原含=%s 抹后含=%s' % ('LVIR_BOUNDS' in _F_LF, 'LVIR_BOUNDS' in _stripped))

P('')
P('=' * 78)
P('合计 %d 条判据  PASS=%d  FAIL=%d' % (_n, _passed, _failed))
P('=' * 78)
sys.exit(1 if _failed else 0)

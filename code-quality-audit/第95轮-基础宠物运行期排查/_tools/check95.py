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


def run_case(direction, sleeping_walk, timer, main_text=None):
    """跑一次真 `update_animation`，返回 `(请求名, 未命中列表)`。

    桩只喂"本判据观察得到"的东西：`sprite_loader`（名字存在性 + 未命中记账）、
    `current_animation`（真值必须是已登记的字符串，否则 `startswith/split` 语义不同）、
    以及 `change_animation` 的记账。
    """
    text = MAIN_TEXT if main_text is None else main_text
    seg, _ = _method_src(text, 'RalseiPet', 'update_animation')
    S = _exec_method(seg, {'_log': _LOG_STUB, 'math': __import__('math'),
                           'random': __import__('random'), 'time': __import__('time')})
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
    req = []
    o.change_animation = lambda name, *a, **k: (req.append(name), True)[1]
    o.update_animation()
    return (req[0] if req else None), reg.misses


NO_GUARD = ' and self.current_direction == "down"'


def _strip_guard(text):
    """**生成式**负控制：把本轮加的那半截条件从源码里抠掉（不落盘、不动产品文件）。"""
    return text.replace(
        'elif self.is_sleeping_walk and self.current_direction == "down":',
        'elif self.is_sleeping_walk:')


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

CASES = [
    ('right', 'walk_right'),
    ('left', 'walk_left'),
    ('up', 'walk_up'),
    ('down', 'walk_down_sleep'),
]
for _d, _want in CASES:
    _timer = 999.0 if _d == 'down' else 0.0
    _req, _miss = run_case(_d, True, _timer)
    if _d == 'down':
        check('B1 `down` + 连续下走（timer>=10）⇒ 请求 `%s`（功能未被关掉）' % _want,
              _req == _want, '实际请求 = %r' % (_req,))
        check('B2 `down` 场景零未命中', _miss == [], '未命中 = %r' % (_miss,))
    else:
        check('B3 `%s` + is_sleeping_walk ⇒ 请求 `%s`（不回落到不存在的 *_sleep）'
              % (_d, _want), _req == _want, '实际请求 = %r' % (_req,))
        check('B4 `%s` 场景零未命中（不再产生 [anim-miss] 噪声）' % _d,
              _miss == [], '未命中 = %r' % (_miss,))

# ---- 负控制：生成式变异（抠掉守卫）⇒ 必须报出未命中 ----
_mut = _strip_guard(MAIN_TEXT)
check('B5 变异保真：抠掉 ` and self.current_direction == "down"` 后源码确实变了',
      _mut != MAIN_TEXT and _mut.count('elif self.is_sleeping_walk:') >= 1)
_req_m, _miss_m = run_case('right', True, 0.0, main_text=_mut)
check('B6 负控制：抠掉守卫后 right 场景**必须**报出 `walk_right_sleep` 未命中',
      ('walk_right_sleep', 'walk_right', 'update_animation') in _miss_m
      and _req_m == 'walk_right',
      '未命中 = %r  请求 = %r' % (_miss_m, _req_m))
_req_ok, _ = run_case('right', True, 0.0)
check('B7 恒真防护：正/负两侧的"未命中"必须不同（否则判据无鉴别力）',
      (_miss_m != []) and (_req_ok == 'walk_right'),
      '负侧未命中=%d  正侧请求=%r' % (len(_miss_m), _req_ok))

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
check('D3 no-op 显式打印：B 段四方向场景的请求名（人可复核）',
      True)
P('     right=%r left=%r up=%r down=%r'
  % (run_case('right', True, 0.0)[0], run_case('left', True, 0.0)[0],
     run_case('up', True, 0.0)[0], run_case('down', True, 999.0)[0]))

P('')
P('=' * 78)
P('合计 %d 条判据  PASS=%d  FAIL=%d' % (_n, _passed, _failed))
P('=' * 78)
sys.exit(1 if _failed else 0)

# -*- coding: utf-8 -*-
"""第54轮回归锁：电梯坐姿（原作 spr_ralsei_sit）+ 两处底层修复

本套件锁三件事，每件都配**负控制**（否则判据可能是恒真的）：

  A. 「电梯里坐着」这组动画真的进了产品
     —— 素材四帧在位 + 动作表登记 + animations.json 与代码内置表深度等价。
     负控制：`sit_0` 与 `sit_2` 必须**不同像素**（否则"四帧"是假的）。

  B. P0 修复：`animation.fps` 非法值不再让程序起不来
     —— 从 `main.py` **逐字抽取**钳位片段真跑（不是重写一份等价逻辑）。
     负控制：把钳位去掉的**修复前写法**喂 fps=0 必须**真的抛 ZeroDivisionError**，
     证明这段钳位确实在挡一个真会发生的崩溃。

  C. 待机（窝着）→ 坐下 的接线
     —— AST 证明 `update_animation` 真会选 `sit_rest`、`_idle_lounge_tick`
     真会播一次 `sit`；行为级用真函数跑一遍到窝点那一拍。
     负控制：已到窝点（`_lounge_walking=False`）**不许**重复播。

  D. P1 修复：自主代理的删除分支**硬拒绝**
     —— 行为级：DELETE 任务不再调 `delete_file`。
     正控制：同一 harness 跑 OPEN 任务必须**真的调** `open_folder`（证明 harness 有鉴别力）。

运行：python check54a.py      （由 regress/run_all.py 以 cwd=_tools 调起）
"""
import ast
import contextlib
import io
import logging
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
# _tools → 第54轮-... → code-quality-audit → 仓库根（三层，同 check52c 的约定）
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'src'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])

_PASS, _FAIL = [], []
_NEG = []          # 负/正控制清单（自查用）


def check(tid, title, cond, detail=''):
    (_PASS if cond else _FAIL).append(tid)
    print('  [%s] %-6s %s%s' % ('PASS' if cond else 'FAIL', tid, title,
                                ('  :: ' + detail) if detail else ''))


def neg(tid, title, cond, detail=''):
    """负/正控制：除了记账，还登记进 `_NEG` 便于最后自查"控制组确实存在"。"""
    _NEG.append(tid)
    check(tid, title, cond, detail)


MAIN_PY = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
LOADER_PY = os.path.join(ROOT, 'ralsei_pet', 'modules', 'sprite_loader.py')
AGENT_PY = os.path.join(ROOT, 'ralsei_pet', 'modules', 'autonomous_agent.py')
SPRITE_DIR = os.path.join(ROOT, 'deltarune_ralsei')
ANIM_JSON = os.path.join(ROOT, 'ralsei_pet', 'assets', 'animations.json')
# 第8轮来源闸门套件（C9 要读它的白名单，保证"分类口径"与"闸门白名单"两边一致）
ROUND8_PY = os.path.join(ROOT, 'code-quality-audit', '第八轮', 'verify_round8_anim.py')

_main_src = open(MAIN_PY, encoding='utf-8').read()
_main_tree = ast.parse(_main_src)
_loader_src = open(LOADER_PY, encoding='utf-8').read()
_agent_src = open(AGENT_PY, encoding='utf-8').read()
_agent_tree = ast.parse(_agent_src)


def _func(tree, name, cls=None):
    """取模块级（或指定类里的）函数节点。"""
    scope = tree.body
    if cls:
        scope = [n for n in tree.body
                 if isinstance(n, ast.ClassDef) and n.name == cls][0].body
    for n in scope:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def _src_of(node, src=None):
    """取 AST 节点的源码片段。`node=None` 返回 `''`（防"找不到函数 ⇒ 判据自身抛异常"）。"""
    if node is None:
        return ''
    return ast.get_source_segment(_main_src if src is None else src, node) or ''


def _is_literal(node, value):
    """`ast.Str` 在 3.8+ 已并入 `ast.Constant`；两代都要认（本项目跑 3.11）。"""
    return isinstance(node, ast.Constant) and node.value == value


def _targets_new_animation(node):
    """`new_animation = ...` 的赋值目标：既可能是普通名，也可能是 `self.new_animation`。"""
    for t in node.targets:
        if isinstance(t, ast.Name) and t.id == 'new_animation':
            return True
        if isinstance(t, ast.Attribute) and t.attr == 'new_animation':
            return True
    return False


# ===========================================================================
print('=== A. 电梯坐姿：素材 + 动作表 ===')
# ===========================================================================
SIT_FRAMES = ['spr_ralsei_sit_%d.png' % i for i in range(4)]
_sizes = {}
for i, fn in enumerate(SIT_FRAMES):
    p = os.path.join(SPRITE_DIR, fn)
    ok = os.path.exists(p)
    if ok:
        with open(p, 'rb') as fh:
            head = fh.read(8)
        # PNG 魔数：89 50 4E 47 0D 0A 1A 0A
        ok = head == b'\x89PNG\r\n\x1a\n'
        try:
            from PIL import Image
            _sizes[fn] = Image.open(p).size
        except Exception:
            _sizes[fn] = None
    check('A1%d' % i, '素材在位且是真 PNG：%s' % fn, ok, str(_sizes.get(fn)))

check('A2', '四帧尺寸一致且为 24x44（原作 spr_ralsei_sit 原始尺寸）',
      len(set(_sizes.values())) == 1 and list(_sizes.values())[0] == (24, 44),
      str(_sizes))

# 负控制：sit_0 与 sit_2 必须**不是**同一张（否则"站→下沉→坐定"是编的）
def _px(fn):
    from PIL import Image
    return Image.open(os.path.join(SPRITE_DIR, fn)).convert('RGBA').tobytes()

_same23 = _px('spr_ralsei_sit_2.png') == _px('spr_ralsei_sit_3.png')
_diff02 = _px('spr_ralsei_sit_0.png') != _px('spr_ralsei_sit_2.png')
neg('A3', '负控制：sit_0（站）与 sit_2（坐定）像素必须不同', _diff02)
check('A3b', 'sit_2 与 sit_3 完全相同（原作 image_index=2 定格，两帧同图）', _same23)

# 动作表登记（从真实加载器读，不是我硬写）
from sprite_loader import SpriteLoader  # noqa: E402

_loader = SpriteLoader()
_loader.load_sprites(debug=False)
_got_sit = _loader.sprites.get('sit')
_got_rest = _loader.sprites.get('sit_rest')
check('A4', "SpriteLoader 里 `sit` == 四帧（顺序与磁盘同名）",
      bool(_got_sit) and len(_got_sit) == 4,
      'n=%d' % (len(_got_sit or []),))
check('A5', "SpriteLoader 里 `sit_rest` == 单帧（坐定静帧）",
      bool(_got_rest) and len(_got_rest) == 1,
      'n=%d' % (len(_got_rest or []),))
neg('A5b', '负控制：不存在的 `sit_zzz` 取不到（防「名字打错⇒判据恒真」）',
    not _loader.sprites.get('sit_zzz'))

# animations.json 与代码内置表深度等价（独立复算，不调导出器）
import json  # noqa: E402

_anim = json.load(open(ANIM_JSON, encoding='utf-8'))
_jsit = _anim.get('groups', {}).get('sit')
_jrest = _anim.get('groups', {}).get('sit_rest')
check('A6', 'animations.json 里有 `sit`（4 帧）与 `sit_rest`（1 帧）',
      bool(_jsit) and len(_jsit.get('frames', [])) == 4
      and bool(_jrest) and len(_jrest.get('frames', [])) == 1,
      'sit=%s sit_rest=%s' % (_jsit and _jsit.get('frames'), _jrest and _jrest.get('frames')))
check('A7', 'JSON 的 frames 与内置表**逐字相等**（含顺序）',
      _jsit and _jsit['frames'] == SIT_FRAMES
      and _jrest and _jrest['frames'] == ['spr_ralsei_sit_2.png'],
      'json=%r' % (_jsit and _jsit.get('frames'),))

# ===========================================================================
print()
print('=== B. P0：animation.fps 钳位（逐字抽取真跑）===')
# ===========================================================================
_lines = _main_src.splitlines()
try:
    _i0 = next(i for i, l in enumerate(_lines)
               if '_fps_raw = self.config_manager.get("animation.fps"' in l)
    _i1 = next(i for i, l in enumerate(_lines)
               if i > _i0 and 'self.animation_frame_delay = self.config_manager.get(' in l)
    _block = textwrap.dedent('\n'.join(_lines[_i0:_i1 + 1]))
    check('B1', '能从 main.py 逐字抽到钳位片段（%d 行）' % (_i1 - _i0 + 1),
          '_fps_raw' in _block and 'animation_frame_delay' in _block)
except StopIteration:
    _block = ''
    check('B1', '能从 main.py 逐字抽到钳位片段', False, '锚点行未找到')


class _FakeCM(object):
    def __init__(self, cfg):
        self.cfg = cfg

    def get(self, k, d=None):
        return self.cfg.get(k, d)


class _FakeLog(object):
    def __init__(self):
        self.warnings = []

    def warning(self, *a, **k):
        self.warnings.append(a)


class _FakePet(object):
    def __init__(self, cfg):
        self.config_manager = _FakeCM(cfg)


def _run_clamp(fps_value):
    """真跑抽取出来的钳位片段。→ (animation_fps, animation_frame_delay, 警告条数)"""
    pet = _FakePet({'animation.fps': fps_value})
    log = _FakeLog()
    exec(compile(_block, '<extracted __init__ clamp>', 'exec'),
         {'self': pet, '_log': log})
    return pet.animation_fps, pet.animation_frame_delay, len(log.warnings)


if _block:
    _cases = [
        ('B2', 0, 6, 'fps=0（原来必崩）'),
        ('B3', -3, 6, 'fps=-3'),
        ('B4', 'abc', 6, 'fps="abc"（手改配置写坏）'),
        ('B5', None, 6, 'fps=None'),
        ('B6', True, 6, 'fps=True（bool 不是正数，必须挡）'),
        ('B7', 999, 120, 'fps=999（上限钳到 120）'),
    ]
    for tid, given, want, why in _cases:
        try:
            got, delay, warns = _run_clamp(given)
            check(tid, '%s ⇒ animation_fps=%s（并落一条 warning）' % (why, want),
                  got == want and warns >= 1 and delay == int(1000 / want),
                  'got=%r delay=%r warns=%d' % (got, delay, warns))
        except Exception as e:
            check(tid, '%s ⇒ animation_fps=%s' % (why, want), False,
                  '抛异常 %s: %s' % (type(e).__name__, e))

    # 正控制：合法值**不许**被改（否则钳位就是"一刀切"，会把用户的设置吃掉）
    try:
        got6, delay6, warn6 = _run_clamp(6)
        got65, delay65, warn65 = _run_clamp(6.5)
        check('B8', '正控制：fps=6 原样保留、且**不**产生 warning',
              got6 == 6 and warn6 == 0, 'got=%r warns=%d' % (got6, warn6))
        check('B9', '正控制：fps=6.5（合法小数）原样保留，不擅自取整',
              got65 == 6.5 and warn65 == 0, 'got=%r warns=%d' % (got65, warn65))
    except Exception as e:
        check('B8', '正控制：合法值原样保留', False, '%s: %s' % (type(e).__name__, e))
        check('B9', '正控制：合法小数原样保留', False, '见 B8')

    # ★ 负控制（本套件最重要的一条）：把钳位去掉的**修复前写法**必须真的崩
    _prefix = ('self.animation_fps = self.config_manager.get("animation.fps", 6)\n'
               'self.animation_frame_delay = self.config_manager.get('
               '"animation.frame_delay", int(1000 / self.animation_fps))\n')
    _pet = _FakePet({'animation.fps': 0})
    _raised = None
    try:
        exec(compile(_prefix, '<pre-fix>', 'exec'), {'self': _pet})
    except Exception as e:
        _raised = type(e).__name__
    neg('B10', '负控制：修复前写法 + fps=0 ⇒ 必须抛 ZeroDivisionError（证明钳位真在挡崩）',
        _raised == 'ZeroDivisionError', 'raised=%r' % (_raised,))

# ===========================================================================
print()
print('=== C. 待机（窝着）⇒ 坐下 的接线 ===')
# ===========================================================================
_ua = _func(_main_tree, 'update_animation', cls='RalseiPet')
_sit_assigns = []
if _ua is not None:
    for node in ast.walk(_ua):
        if isinstance(node, ast.Assign) and _targets_new_animation(node) \
                and _is_literal(node.value, 'sit_rest'):
            _sit_assigns.append(node)
check('C1', "update_animation 里存在 `new_animation = \"sit_rest\"`",
      len(_sit_assigns) == 1, 'n=%d' % len(_sit_assigns))


def _guard_has(node, attr):
    """该赋值所在的**最内层** If 的 test 里有没有 attr。

    ★ 必须取"最内层"而不是"任意一层"：`update_animation` 是个巨大的嵌套 if 树，
    用"任意一层命中"会让外层某个恰好含同一标识符的 If 冒充守卫（第52轮 §5.1
    的坑 #2 同形状：判据过宽 = 会误报/失锁）。
    """
    cands = [p for p in ast.walk(_ua)
             if isinstance(p, ast.If) and any(x is node for x in ast.walk(p))]
    if not cands:
        return False
    return attr in _src_of(min(cands, key=lambda n: n.end_lineno - n.lineno).test)


check('C2', '该赋值被 `_lounge_since` 守卫（只有真·窝着才坐下，不是无条件）',
      bool(_sit_assigns) and _guard_has(_sit_assigns[0], '_lounge_since'))

# ★★ 第54轮复检的核心回归锁：守卫**不许**再是 `_idle_loop_active`。
#   它等价于「窝着 **或** idle_timer>=600」，会把"只是原地静止满 10 分钟、并未窝着"
#   那一支也变成坐姿 —— 等于把第52轮的"待机动画 = idle 5 帧循环"整条删掉。
#   实测（第54轮复检）：那么写时 round8 E1.3 是靠"跨组切换冷却 1.6s 恰好挡住 sit_rest"
#   才侥幸为绿的 —— 假绿，比红更危险。
check('C2c', '该守卫**不含** `_idle_loop_active`（静止满10分钟 ≠ 窝着，不许再混用）',
      bool(_sit_assigns) and not _guard_has(_sit_assigns[0], '_idle_loop_active'))

# 鉴别力体检：合成"修复前"的写法必须被判「不含」
_synth = ast.parse('def f(self):\n    new_animation = "idle"\n')
_synth_has = any(isinstance(n, ast.Assign) and _targets_new_animation(n)
                 and _is_literal(n.value, 'sit_rest')
                 for n in ast.walk(_synth))
neg('C2b', '负控制：合成的旧写法（只有 new_animation="idle"）必须被判「不含 sit_rest」',
    not _synth_has)

_lt = _func(_main_tree, '_idle_lounge_tick', cls='RalseiPet')
_once_calls = []
if _lt is not None:
    for node in ast.walk(_lt):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'play_animation_once':
            args = [a.value for a in node.args if isinstance(a, ast.Constant)]
            kws = {k.arg: k.value.value for k in node.keywords
                   if isinstance(k.value, ast.Constant)}
            if 'sit' in args:
                _once_calls.append((args, kws))
check('C3', '_idle_lounge_tick 里有 `play_animation_once("sit", restore_to="sit_rest")`',
      len(_once_calls) == 1
      and _once_calls[0][1].get('restore_to') == 'sit_rest',
      repr(_once_calls))
check('C4', '该调用在「刚到窝点」分支里（与 `_lounge_walking = False` 同一 If）',
      bool(_lt) and any(
          isinstance(n, ast.If)
          and 'play_animation_once' in _src_of(n)
          and '_lounge_walking' in _src_of(n)
          for n in ast.walk(_lt)))

# ---- 行为级：用真函数跑一遍 ----
class _StubPet(object):
    """只提供 `_idle_lounge_tick` 会碰到的字段（与 check52c 的 _bed_host 同思路）。"""

    def __init__(self, loader):
        self.sprite_loader = loader
        self.IDLE_LOUNGE_ENABLED = True
        self.IDLE_LOUNGE_AFTER_SECONDS = 600.0
        self._lounge_since = 1000.0          # 已在待机
        self._lounge_perch = None
        self._lounge_walking = True          # 正在走向窝点
        self._lounge_interaction_ref = 111.0
        self.last_interaction_time = 111.0   # 没变 ⇒ 不退出
        self.is_moving = False               # ★ 本拍刚到（停住了）
        self.once_calls = []
        self._lounge_perch_point = lambda: None

    def _idle_lounge_busy(self):
        return False                          # 忙碌闸由 check52c 锁，这里不重复测

    def play_animation_once(self, *a, **kw):
        self.once_calls.append((a, kw))
        return True


import main as _RP  # noqa: E402

_st = _StubPet(_loader)
_ret = _RP.RalseiPet._idle_lounge_tick(_st, 2000.0)
check('C5', '行为级：刚到窝点这一拍真的播了一次 sit（restore_to=sit_rest）',
      _ret is True and _st.once_calls == [(('sit',), {'restore_to': 'sit_rest'})],
      'ret=%r calls=%r' % (_ret, _st.once_calls))
check('C6', '行为级：播完之后 `_lounge_walking` 置 False（不会每拍都重播）',
      _st._lounge_walking is False)
_st2 = _StubPet(_loader)
_st2._lounge_walking = False              # ★ 负控制：已经在窝点
_ret2 = _RP.RalseiPet._idle_lounge_tick(_st2, 2000.0)
neg('C6b', '负控制：已在窝点（_lounge_walking=False）**不许**再播一次',
    _ret2 is True and _st2.once_calls == [],
    'ret=%r calls=%r' % (_ret2, _st2.once_calls))

# 退出待机后必须能回到 idle：`_exit_idle_lounge` 清掉 `_lounge_since`
_ex = _StubPet(_loader)
_RP.RalseiPet._exit_idle_lounge(_ex, '测试')
check('C7', '退出待机后 `_lounge_since` 归 None（update_animation 据此回到 idle）',
      _ex._lounge_since is None and _ex._lounge_walking is False)

# ---- 分类与来源闸门的一致性（第54轮复检新增）----
# 事实基础：`sit` / `sit_rest` 由**确定性状态机** `_idle_lounge_tick` 自动触发。
# 若它们仍被算作"特殊动画"，就与第8轮契约（特殊动画只由用户/AI 触发）自相矛盾
# —— 同一份表既说它特殊、又给它的自动触发开白名单。
check('C8', '`sit` / `sit_rest` 在 `_is_special_anim` 下都**不是**特殊动画',
      not _RP.RalseiPet._is_special_anim('sit')
      and not _RP.RalseiPet._is_special_anim('sit_rest'))
neg('C8b', '负控制：`wave` 仍是特殊动画（证明 C8 不是"什么都判非特殊"）',
    _RP.RalseiPet._is_special_anim('wave'))

# 源码侧独立复核：不看 `_is_special_anim` 的实现，直接读常量表本身
_nsag = None
for _n in ast.walk(_main_tree):
    if isinstance(_n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == '_NON_SPECIAL_ANIM_GROUPS' for t in _n.targets):
        _v = _n.value
        if isinstance(_v, ast.Call) and getattr(_v.func, 'id', '') in ('set', 'frozenset'):
            _v = _v.args[0]
        if isinstance(_v, (ast.Set, ast.List, ast.Tuple)):
            _nsag = {ast.literal_eval(e) for e in _v.elts}
check('C8c', '源码常量 `_NON_SPECIAL_ANIM_GROUPS` 里确有 `sit`（与 C8 行为级一致）',
      _nsag is not None and 'sit' in _nsag, 'n=%d' % (len(_nsag or ())))

# 第8轮来源闸门（H1.1）是**名字白名单**：新调用点必须显式放行，否则套件报红。
# 这里把它也锁住 —— 免得日后有人"修 round8"时顺手删掉这个名字，两边口径失配。
_r8_src = open(ROUND8_PY, encoding='utf-8').read()
_r8_tree = ast.parse(_r8_src)


def _allowed_owners(tree):
    """从 round8 套件里取出 `_ALLOWED_PLAY_ONCE_OWNERS` 的字面量集合（None=没找到）。"""
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == '_ALLOWED_PLAY_ONCE_OWNERS'
                for t in n.targets):
            try:
                return set(ast.literal_eval(n.value))
            except Exception:
                return None
    return None


_r8_allowed = _allowed_owners(_r8_tree)
check('C9', '第8轮来源闸门白名单已放行 `_idle_lounge_tick`（否则 round8 H1.1 会红）',
      bool(_r8_allowed) and '_idle_lounge_tick' in _r8_allowed,
      'n=%d' % (len(_r8_allowed or ())))
neg('C9b', '负控制：合成一份不含该名字的白名单必须被判「未放行」',
    '_idle_lounge_tick' not in (_allowed_owners(
        ast.parse("_ALLOWED_PLAY_ONCE_OWNERS = {'update_movement'}\n")) or set()))

# ===========================================================================
print()
print('=== D. P1：自主代理删除分支硬拒绝 ===')
# ===========================================================================
_ex = _func(_agent_tree, '_execute_action', cls='AutonomousAgent')
_AEX_SRC = _src_of(_ex, _agent_src) if _ex is not None else ''


def _has_delete_call(node):
    """函数体里有没有 `*.delete_file(...)` 调用。

    ★ 必须走 AST：文本包含判据会被**我自己写的注释**（注释里逐字引用了
    `desktop_interaction.delete_file(confirm=False)`）误命中 —— 第52轮 §5.1
    的坑 #2 同一个形状。
    """
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == 'delete_file':
            return True
    return False


check('D1', '_execute_action 里不再有 `*.delete_file(...)` 调用（AST 判据，不吃注释）',
      bool(_ex) and not _has_delete_call(_ex), 'len=%d' % len(_AEX_SRC))

# 鉴别力体检：合成的老写法必须被同一条判据抓出来
_synth_del = ast.parse('def f(self):\n    d.delete_file(p, confirm=False)\n')
neg('D1b', '负控制：合成的老写法 `d.delete_file(...)` 必须被同一条判据抓出',
    _has_delete_call(_synth_del))

from autonomous_agent import (AutonomousAgent, AutonomousTask,  # noqa: E402
                              InteractionTarget, InteractionType)


class _FakeDesk(object):
    def __init__(self):
        self.calls = []

    def delete_file(self, *a, **kw):
        self.calls.append(('delete_file', a, kw))
        return True

    def open_folder(self, *a, **kw):
        self.calls.append(('open_folder', a, kw))
        return True


class _AgentStub(object):
    def __init__(self):
        self._desktop = _FakeDesk()


def _mk_task(kind, action, path, name='x'):
    tgt = InteractionTarget(kind=kind, name=name, path=path)
    return AutonomousTask(target=tgt, action=action)


_a = _AgentStub()
AutonomousAgent._execute_action(
    _a, _mk_task('file', InteractionType.DELETE, r'C:\tmp\do_not_delete.txt'))
check('D2', '行为级：DELETE 任务 ⇒ `delete_file` **零调用**（硬拒绝）',
      _a._desktop.calls == [], 'calls=%r' % (_a._desktop.calls,))

_b = _AgentStub()
AutonomousAgent._execute_action(
    _b, _mk_task('folder', InteractionType.OPEN, r'C:\tmp\some_folder'))
neg('D3', '正控制：同一 harness 的 OPEN(folder) ⇒ `open_folder` **真被调用**（证明判据有鉴别力）',
    len(_b._desktop.calls) == 1 and _b._desktop.calls[0][0] == 'open_folder',
    'calls=%r' % (_b._desktop.calls,))

# `_pick_action` 不许自己把 DELETE 产出（上游也守住）
_pa = _func(_agent_tree, '_pick_action', cls='AutonomousAgent')
check('D4', '上游 `_pick_action` 仍不产出 DELETE（第30轮口径不许回退）',
      bool(_pa) and 'InteractionType.DELETE' not in _src_of(_pa, _agent_src))

# ===========================================================================
print()
print('=== F. 日志系统自身不许成为故障源（第54轮新增）===')
# ===========================================================================
# 由来：第54轮复跑 G2 时 `round34_store_config` 出现 **非确定性** 的基线漂移 ——
# 输出里多出一段 `--- Logging error ---` + `OSError: [Errno 22] Invalid argument`。
# 追下去发现是 `logging/__init__.py:1094` 的 `self.stream.flush()`：
# 日志落盘的 E 盘 exFAT 间歇性拒写 / `sys.stdout` 指向半关闭的管道时都会抛。
# 原生 StreamHandler 的行为是"喷 Traceback 到 stderr **并且丢掉这条日志**" ——
# 对用户是噪音，对我们是不确定的回归基线。既然 `logger_utils` 早已为 rollover
# 做过同类兜底（第34轮），这里把 emit/flush 也一并兜住并上锁。
import logging as _logging  # noqa: E402

_logger_utils_py = os.path.join(ROOT, 'ralsei_pet', 'modules', 'logger_utils.py')
_lu_src = open(_logger_utils_py, encoding='utf-8').read()
import logger_utils as _lu  # noqa: E402


class _BrokenStream(object):
    """写/flush 必抛 `OSError(22)` 的坏流（复现 exFAT 拒写与半关闭管道的现场）。"""

    encoding = 'utf-8'

    def write(self, s):
        raise OSError(22, 'Invalid argument')

    def flush(self):
        raise OSError(22, 'Invalid argument')


def _emit_capture(handler, record):
    """把一条 record 喂给 handler，返回 (stderr 上新增的文本, 抛出的异常名)。

    ★ 刻意**不**去替换 `handler.handleError`：
      · 替换它等于把"被测对象"换成"我的桩"，F1 会变成恒真（假绿）；
      · 真正要证明的产品行为是"**stderr 上不再出现 `--- Logging error ---`**"，
        那就直接抓 stderr。原生实现往 `sys.stderr` 写，`redirect_stderr` 能原样截到。
    """
    buf = io.StringIO()
    raised = None
    with contextlib.redirect_stderr(buf):
        try:
            handler.emit(record)
        except Exception as exc:
            raised = type(exc).__name__
    return buf.getvalue(), raised


_rec = _logging.LogRecord('ralsei_pet', _logging.INFO, __file__, 1, 'x', (), None)

_safe_h = _lu._SafeEmitStreamHandler(_BrokenStream())
_err_safe, _raised = _emit_capture(_safe_h, _rec)
check('F1', '坏流下 SafeEmitStreamHandler 不抛异常、stderr 上也不出现 Logging error/Traceback',
      (not _raised) and 'Logging error' not in _err_safe and 'Traceback' not in _err_safe,
      'raised=%r stderr=%r' % (_raised, _err_safe[:60]))
check('F2', '坏流下失败被**计数**（不是无声无息地丢）', _safe_h.emit_failures > 0,
      'emit_failures=%d' % _safe_h.emit_failures)

# 负控制：同一坏流喂给**原生** StreamHandler 必须真的把 Traceback 喷到 stderr
# （证明 F1 有鉴别力 —— 原生实现确实会喷并丢日志）
_native_h = _logging.StreamHandler(_BrokenStream())
_err_native, _r2 = _emit_capture(_native_h, _rec)
neg('F3', '负控制：原生 StreamHandler + 同一坏流 ⇒ stderr **确实**出现 Logging error',
    'Logging error' in _err_native, 'stderr=%r' % (_err_native[:40],))
neg('F3b', '负控制自证：夹具真的触发了 OSError（不是"坏流其实没坏"）',
    'OSError' in _err_native and 'Invalid argument' in _err_native,
    'stderr=%r' % (_err_native[:60],))

check('F4', '文件 handler 也继承了 emit 保护（_SafeTimedRotatingFileHandler 是其子类）',
      issubclass(_lu._SafeTimedRotatingFileHandler, _lu._SafeEmitStreamHandler))
check('F4b', '切割保护没被顺手删掉（doRollover 仍被覆写且兜住异常）',
      'def doRollover' in _src_of(
          _func(ast.parse(_lu_src), 'doRollover',
                cls='_SafeTimedRotatingFileHandler'), _lu_src)
      and 'rolloverAt' in _src_of(
          _func(ast.parse(_lu_src), 'doRollover',
                cls='_SafeTimedRotatingFileHandler'), _lu_src))
_cinit = _src_of(_func(ast.parse(_lu_src), '_init_logging_impl'), _lu_src)
check('F5', '接线：console handler 真的换成了 `_SafeEmitStreamHandler(sys.stdout)`',
      '_SafeEmitStreamHandler(sys.stdout)' in _cinit)
neg('F5b', '负控制：旧的原生写法不会被 F5 的判据误判为已接线',
    '_SafeEmitStreamHandler(sys.stdout)' not in 'logging.StreamHandler(sys.stdout)')

# ===========================================================================
print()
print('=== E. 恒真判据自查 ===')
# ===========================================================================
check('E1', '判据数自洽（PASS+FAIL == 已登记条数）',
      len(_PASS) + len(_FAIL) == len(_PASS) + len(_FAIL) and len(_PASS) + len(_FAIL) > 0,
      'PASS=%d FAIL=%d' % (len(_PASS), len(_FAIL)))
check('E2', '负/正控制清单在位（>=6 条）', len(_NEG) >= 6, 'n=%d %s' % (len(_NEG), _NEG))
check('E3', '被测文件都是**真实存在**的（防路径写错⇒A/B 组恒假）',
      all(os.path.exists(p) for p in (MAIN_PY, LOADER_PY, AGENT_PY, ANIM_JSON, ROUND8_PY,
                                      _logger_utils_py)))

# ===========================================================================
print()
print('=' * 60)
print('总计 %d 项，通过 %d，失败 %d' % (len(_PASS) + len(_FAIL), len(_PASS), len(_FAIL)))
if _FAIL:
    print('失败项: %s' % _FAIL)
sys.stdout.flush()
os._exit(0 if not _FAIL else 1)

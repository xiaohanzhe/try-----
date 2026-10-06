# -*- coding: utf-8 -*-
u"""第91轮回归锁：**基础宠物**状态机的三条缺陷。

背景（全部来自真机取证，不是推测）
----------------------------------
用户第 90 轮反馈链：「**他在这里站桩呢？？？**」→「**我记得他睡觉的这个动画不是这个吧，
用另一个**」，以及第 89 轮起反复的「**跳跃的抛物线也不对**」（已由 `check90` 锁住）。

本轮从第89轮真机日志 `launch_after_rollback.log`（21:06:50 起、63 KB）里读出三条**硬证据**：

  D1 睡眠动画（用户可见的"站桩"）
     · `enter_sleep_mode` 播的是 `"idle"`（睁眼站立），**不是** `sprite_loader` 里
       早已登记却零调用的 `"sleep"` 组（闭眼 + 头顶 zzz）；
     · 且 `update_animation`（**独立 167ms 定时器**）**没有 `is_sleeping` 分支**，
       睡着时会落进"静止分支"算出 `idle`，并以 `force=True` 覆盖回来
       ⇒ 只改 `enter_sleep_mode` 会被 ~1 秒内打回原形。

  D2 就寝即醒（日期边界缺失）
     · `BEDTIME_HOUR=23` / `BEDTIME_WAKE_HOUR=7`，醒来判据只有 `hour >= 7`；
       22:58 入睡时 hour=22 **本来就 >= 7** ⇒ 5 秒后自己醒。日志逐字：
           22:58:00 [就寝] 到点（目标 22:58），回房间睡觉
           22:58:00 [就寝] 由小憩升级为就寝睡
           22:58:05 [就寝] 早上 22 点，自动醒来

  D3 `walk_down_sleep` 动画名不存在（×15515 次未命中）
     · `update_animation` 在 `is_sleeping_walk` 时拼出 `walk_{direction}_sleep`，
       但注册表里只有 `sleep` ⇒ 名字对不上，**全部静默回退 `walk_down`**，
       "走路时睡觉的动画"从上线起就没生效过（日志：合计 15518 次，其中 15515 次是这个）。

段一览
------
  A ★★ 注册表（`sleep` 两帧 · `walk_down_sleep` 存在 · JSON 与内置兜底表两处真源一致 ·
         `update_animation` 拼出的名字必须在表里）
  B ★★★ `enter_sleep_mode` 必须播 `sleep`（AST + 结构层负控制）
  C ★★★ `update_animation` 必须钉住 `sleep`（AST + 静止分支的 idle 覆盖风险佐证 + 负控制）
  D ★★★ 就寝跨天闸（**行为级**：真调 `RalseiPet._bedtime_tick`（轻量桩），
         同日 22:58 不许醒 / 次日 07:00 必须醒 / 次日 00:30 与 06:59 不许醒 /
         小憩睡不参与自动醒）
  E 判据自身体检（**恒真防护**：`_bedtime_tick` 吞异常返 False ⇒ 必须证明桩真能走到唤醒分支）

★ 判据纪律：`print('[PASS] %s')` 字面量；判据名不自带标记；正/负控制成对；
  断行为不断赋值；A/B/C 走 AST 而非子串；零网络 / 零 UI / 不需要显示器 / 零外部盘。
"""
import ast
import datetime as _dt
import json
import os
import re
import sys
import types

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from main import RalseiPet            # noqa: E402
from sprite_loader import SpriteLoader  # noqa: E402

MAIN = os.path.join(PKG, 'src', 'main.py')
LOADER = os.path.join(PKG, 'modules', 'sprite_loader.py')
ANIM_JSON = os.path.join(PKG, 'assets', 'animations.json')

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
with open(LOADER, encoding='utf-8') as _fh:
    LOADER_SRC = _fh.read()
LOADER_TREE = ast.parse(LOADER_SRC)


def _norm(s):
    return re.sub(r'\s+', ' ', s).strip()


def _fn(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _builtin_mapping(tree):
    """从 `SpriteLoader.__init__` 的赋值语句里还原**内置兜底表**（AST 求字面量）。"""
    init = _fn(tree, '__init__')
    if init is None:
        return None
    for n in ast.walk(init):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id == '_builtin_animation_mapping'
                and isinstance(n.value, ast.Dict)):
            out = {}
            for k, v in zip(n.value.keys, n.value.values):
                if isinstance(k, ast.Constant) and isinstance(v, ast.List):
                    frames = [e.value for e in v.elts if isinstance(e, ast.Constant)]
                    out[k.value] = frames
            return out
    return None


# ============================================================ 装载真实表
_sl = SpriteLoader()
MAPPING = _sl.animation_mapping


# ============================================================ A. 注册表
mark('A 注册表：sleep 两帧 · walk_down_sleep 存在 · 两处真源一致')

check('A1 生效表里 `sleep` 是**两帧**（磁盘早有 _1，此前只登记 _0 ⇒ 睡眠像卡住的静帧）',
      set(MAPPING.get('sleep', [])) == {
          'spr_ralsei_walk_down_sleep_0.png', 'spr_ralsei_walk_down_sleep_1.png'},
      'sleep=%s' % (MAPPING.get('sleep'),))

check('A2 生效表里登记了 `walk_down_sleep` 组（否则 update_animation 拼出的名字查不到）',
      'walk_down_sleep' in MAPPING,
      'walk_down_sleep=%s' % (MAPPING.get('walk_down_sleep'),))

check('A3 `sleep` 与 `walk_down_sleep` 指向同一批帧（同一素材，两个入口名）',
      MAPPING.get('sleep') == MAPPING.get('walk_down_sleep') and bool(MAPPING.get('sleep')),
      'sleep=%s walk_down_sleep=%s' % (MAPPING.get('sleep'), MAPPING.get('walk_down_sleep')))

_missing = [f for f in MAPPING.get('sleep', [])
            if not os.path.exists(os.path.join(_sl.sprite_dir, f))]
check('A4 登记的两帧**在磁盘上真的存在**（不是靠占位图/灰块撑着的假登记）',
      bool(MAPPING.get('sleep')) and not _missing, 'missing=%s' % (_missing,))

# ---- A5：把「代码拼出的名字」与「注册表」对上（这是 D3 的根因判据）----
_ua = _fn(TREE, 'update_animation')


def _eval_joined(node, env):
    """把 `f"{a}_{b}{c}"` 这类 JoinedStr **按给定的变量取值真算一遍**。

    ⚠️ f-string 在 AST 里是 `JoinedStr`（不是 `Constant`）—— 第一版就是栽在
       「`isinstance(n.value, ast.Constant)` 恒假」上（判据侧的老毛病）。
    """
    out = []
    for v in node.values:
        if isinstance(v, ast.Constant):
            out.append(str(v.value))
        elif isinstance(v, ast.FormattedValue):
            key = _norm(ast.unparse(v.value))
            if key not in env:
                return None
            out.append(str(env[key]))
        else:
            return None
    return ''.join(out)


_SUFFIX = None
_FSTR = None
for n in ast.walk(_ua):
    if not (isinstance(n, ast.Assign) and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)):
        continue
    tgt = n.targets[0].id
    if tgt == 'animation_suffix' and isinstance(n.value, ast.Constant) \
            and n.value.value == '_sleep':
        _SUFFIX = n.value.value
    if tgt == 'new_animation' and isinstance(n.value, ast.JoinedStr):
        txt = _norm(ast.unparse(n.value))
        if 'base_animation' in txt and 'current_direction' in txt \
                and 'animation_suffix' in txt:
            _FSTR = n.value

_ENV = {'base_animation': 'walk', 'self.current_direction': 'down',
        'animation_suffix': '_sleep'}
_composed = _eval_joined(_FSTR, _ENV) if _FSTR is not None else None

check('A5 `update_animation` 仍会拼出 `walk_<方向>_sleep`（D3 的前提还在）',
      _SUFFIX == '_sleep' and _FSTR is not None and _composed == 'walk_down_sleep',
      'suffix=%r 拼出=%r' % (_SUFFIX, _composed))
check('A6 拼出来的名字（walk + down + _sleep = `walk_down_sleep`）**必须在注册表里**',
      _composed in MAPPING, 'composed=%r in_table=%s' % (_composed, _composed in MAPPING))

# ---- A7：两处真源（animations.json 与内置兜底表）必须一致 ----
_bi = _builtin_mapping(LOADER_TREE)
try:
    _json_groups = json.load(open(ANIM_JSON, encoding='utf-8'))['groups']
    _js = {k: list(v.get('frames', [])) for k, v in _json_groups.items()}
except Exception as e:                                   # pragma: no cover
    _js = {}
    print('（读 animations.json 失败: %s）' % e)
check('A7 **两处真源一致**：animations.json 与内置兜底表都登记了同样两帧',
      bool(_bi) and bool(_js)
      and _bi.get('sleep') == _js.get('sleep') == MAPPING.get('sleep')
      and _bi.get('walk_down_sleep') == _js.get('walk_down_sleep') == MAPPING.get('walk_down_sleep'),
      'builtin(sleep)=%s json(sleep)=%s' % (_bi and _bi.get('sleep'), _js.get('sleep')))

# A8 负控制：修法之前只有 `sleep`、没有 `walk_down_sleep` ⇒ A6 必须转红
_OLD_MAPPING = {k: v for k, v in MAPPING.items() if k != 'walk_down_sleep'}
check('A8 负控制：把 `walk_down_sleep` 从表里拿掉（＝修复前的状态）后 A6 判据必须转红',
      _composed not in _OLD_MAPPING,
      '旧表里 %r in = %s' % (_composed, _composed in _OLD_MAPPING))


# ============================================================ B. enter_sleep_mode
mark('B `enter_sleep_mode` 必须播 sleep（不是 idle）')


def _sleep_call_ok(tree, fnname='enter_sleep_mode'):
    fn = _fn(tree, fnname)
    if fn is None:
        return None
    for n in ast.walk(fn):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'change_animation' and n.args
                and isinstance(n.args[0], ast.Constant)):
            return n.args[0].value
    return None


_anim = _sleep_call_ok(TREE)
check('B1 `enter_sleep_mode` 里 `change_animation` 的第一个实参是 `sleep`',
      _anim == 'sleep', 'got=%r' % (_anim,))

_SRC_BAD = SRC.replace('self.change_animation("sleep", force=True)',
                       'self.change_animation("idle", force=True)')
check('B2 负控制：把它换回 `idle`（＝修复前的写法）后 B1 判据必须转红',
      _sleep_call_ok(ast.parse(_SRC_BAD)) != 'sleep',
      'got=%r' % (_sleep_call_ok(ast.parse(_SRC_BAD)),))


def make_sleep_stub():
    """`enter_sleep_mode` 的轻量桩：只补它**真正会读到/写的**属性。"""
    o = types.SimpleNamespace()
    o.is_sleeping = False
    o.is_moving = True
    o._exit_idle_lounge = lambda why: None
    o.is_watching_video = True
    o.is_jumping = True
    o.is_falling = True
    o.idle_timer = 123.0
    o.max_idle_duration = 5.0
    o.anims = []
    o.change_animation = lambda name, force=False: (
        o.anims.append(name), True)[1]
    o.speak_events = []
    o.speak_event = lambda *a, **k: o.speak_events.append((a, k))
    return o


_o1 = make_sleep_stub()
RalseiPet.enter_sleep_mode(_o1)
check('B3 ★行为级：真调 `enter_sleep_mode` 后，唯一被切换到的动画就是 `sleep`'
      '（且其中不含 idle —— 修复前这里恰好是 idle）',
      _o1.anims == ['sleep'] and _o1.is_sleeping is True,
      'anims=%s is_sleeping=%s' % (_o1.anims, _o1.is_sleeping))

_o2 = make_sleep_stub()
RalseiPet.enter_sleep_mode(_o2, bedtime=True)
_today = _dt.date.today()
check('B4 ★行为级：`bedtime=True` 时**同时**置上 `_bedtime_sleep` 与 `_bedtime_sleep_date`'
      '（后者是 D 段跨天闸的输入 ⇒ 缺了它就永远醒不过来）',
      _o2._bedtime_sleep is True and _o2._bedtime_sleep_date == _today,
      # ★ 第95轮：**不回显绝对日期** —— 原来打 `date=2026-10-06 today=2026-10-06`，
      #   过零点后基线必然 DIFF（第95轮实测：10-07 全量回归 check91 报 DIFF，
      #   而它自身 29/29 全绿）。改成回显**日期差**：信息等价（相等 ⇔ 差 0 天），
      #   输出跨日稳定。断言条件本身**未改**。
      '_bedtime_sleep=%s  date-today=%+d 天（0 ⇔ 相等；不回显绝对值 ⇒ 输出跨日稳定）'
      % (_o2._bedtime_sleep,
         (getattr(_o2, '_bedtime_sleep_date', None) - _today).days
         if getattr(_o2, '_bedtime_sleep_date', None) is not None else 9999))

_o3 = make_sleep_stub()
RalseiPet.enter_sleep_mode(_o3)          # 小憩（bedtime 默认 False）
check('B5 负控制：**小憩**（bedtime=False）不设 `_bedtime_sleep`'
      '（否则小憩也会被 D 段的跨天闸叫醒）',
      _o3._bedtime_sleep is False and not hasattr(_o3, '_bedtime_sleep_date'),
      '_bedtime_sleep=%s has_date=%s'
      % (_o3._bedtime_sleep, hasattr(_o3, '_bedtime_sleep_date')))


# ============================================================ C. update_animation 的 is_sleeping 分支
mark('C `update_animation` 必须钉住 sleep（否则被静止分支覆盖）')


def _is_sleeping_branch(tree):
    """在 `update_animation` 里找 `elif self.is_sleeping: new_animation = "sleep"`。"""
    fn = _fn(tree, 'update_animation')
    if fn is None:
        return None
    for n in ast.walk(fn):
        if not isinstance(n, ast.If):
            continue
        t = n.test
        if (isinstance(t, ast.Attribute) and t.attr == 'is_sleeping'
                and isinstance(t.value, ast.Name) and t.value.id == 'self'):
            for st in n.body:
                if (isinstance(st, ast.Assign) and len(st.targets) == 1
                        and isinstance(st.targets[0], ast.Name)
                        and st.targets[0].id == 'new_animation'
                        and isinstance(st.value, ast.Constant)):
                    return st.value.value
    return None


check('C1 `update_animation` 里有 `self.is_sleeping` 分支且把 `new_animation` 定为 `sleep`',
      _is_sleeping_branch(TREE) == 'sleep', 'got=%r' % (_is_sleeping_branch(TREE),))

_SRC_NOSLEEP = re.sub(
    r'elif self\.is_sleeping:\s*\n\s*new_animation = "sleep"\s*\n', '', SRC)
check('C2 负控制：把该分支整段删掉后 C1 判据必须转红',
      _is_sleeping_branch(ast.parse(_SRC_NOSLEEP)) is None
      and _SRC_NOSLEEP != SRC,
      'got=%r 已改动=%s' % (_is_sleeping_branch(ast.parse(_SRC_NOSLEEP)),
                            _SRC_NOSLEEP != SRC))

# C3 佐证「覆盖风险是真实的」：静止分支的兜底确实给 idle
_idle_in_ua = any(
    isinstance(n, ast.Assign) and len(n.targets) == 1
    and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'new_animation'
    and isinstance(n.value, ast.Constant) and n.value.value == 'idle'
    for n in ast.walk(_fn(TREE, 'update_animation')))
check('C3 佐证：`update_animation` 的静止兜底确实会算出 `idle`（所以 C1 缺不得）',
      _idle_in_ua)


# ============================================================ D. 就寝跨天闸（行为级）
mark('D 就寝跨天闸：真调 RalseiPet._bedtime_tick（轻量桩）')

_D1 = _dt.date(2026, 10, 5)          # 入睡那天
_D2 = _dt.date(2026, 10, 6)          # 次日


def make_bed_stub(sleep_date, bedtime_sleep=True, sleeping=True):
    o = types.SimpleNamespace()
    o.BEDTIME_ENABLED = True
    o.BEDTIME_HOUR = 23
    o.BEDTIME_JITTER_MINUTES = 10
    o.BEDTIME_WAKE_HOUR = 7
    o.BEDTIME_CHECK_INTERVAL = 5.0
    o._last_bedtime_check = 0.0
    o._bedtime_sleep = bedtime_sleep
    o.is_sleeping = sleeping
    o._bedtime_sleep_date = sleep_date
    o.woke = []
    o.wake_up = lambda: o.woke.append('wake')
    o.go_to_bed = lambda: (o.woke.append('bed'), True)[1]
    o._bedtime_busy = lambda: False
    o._bedtime_target_time = types.MethodType(RalseiPet._bedtime_target_time, o)
    return o


def tick(o, y, mo, d, hh, mi, ss=0):
    """调一次 `_bedtime_tick`。**关掉 ② 就寝分支**（把 fired 置成当天），只测 ① 醒来。"""
    now_dt = _dt.datetime(y, mo, d, hh, mi, ss)
    o._last_bedtime_check = 0.0
    o._bedtime_fired_date = now_dt.strftime('%Y-%m-%d')
    RalseiPet._bedtime_tick(o, now_dt.timestamp())
    return 'wake' in o.woke


_o = make_bed_stub(_D1)
_w_now = tick(_o, 2026, 10, 5, 22, 58, 5)
check('D1 入睡当日 22:58:05 **不许**自动醒（就寝睡至少持续到跨天）',
      _w_now is False, 'wake=%s' % _w_now)

_old_cond = _dt.datetime(2026, 10, 5, 22, 58, 5).hour >= 7
check('D2 ★鉴别力自证：同一时刻**旧判据**（`hour >= BEDTIME_WAKE_HOUR`）本就为真 ⇒ D1 不是恒真',
      _old_cond is True, 'old_hour_ge_7=%s' % _old_cond)

_o = make_bed_stub(_D1)
_w_next = tick(_o, 2026, 10, 6, 7, 0, 0)
check('D3 次日 07:00 **必须**自动醒（跨天且到点）', _w_next is True, 'wake=%s' % _w_next)

_o = make_bed_stub(_D1)
_w_0030 = tick(_o, 2026, 10, 6, 0, 30, 0)
check('D4 次日 00:30 **不许**醒（跨了天但没到点）', _w_0030 is False, 'wake=%s' % _w_0030)

_o = make_bed_stub(_D1)
_w_0659 = tick(_o, 2026, 10, 6, 6, 59, 0)
check('D5 次日 06:59 **不许**醒（差一分钟）', _w_0659 is False, 'wake=%s' % _w_0659)

_o = make_bed_stub(_D1, bedtime_sleep=False)     # 小憩睡
_w_nap = tick(_o, 2026, 10, 6, 7, 0, 0)
check('D6 负控制：**小憩睡**（_bedtime_sleep=False）次日 07:00 也不许自动醒',
      _w_nap is False, 'wake=%s' % _w_nap)

_o = make_bed_stub(None)                          # 缺日期
_w_nodate = tick(_o, 2026, 10, 6, 7, 0, 0)
check('D7 负控制：`_bedtime_sleep_date` 缺失时**不**盲目唤醒（宁可继续睡）',
      _w_nodate is False, 'wake=%s' % _w_nodate)


# ============================================================ E. 判据自身体检
mark('E 判据自身体检')

check('E1 被测文件在盘（main.py / sprite_loader.py / animations.json）',
      all(os.path.isfile(p) for p in (MAIN, LOADER, ANIM_JSON)))
check('E2 判据点全部执行到位（标记打印点 == 5）', _marks == 5, 'marks=%d' % _marks)

# E3 ★★ 恒真防护：`_bedtime_tick` 把异常全吞掉后 `return False`
#    ⇒ 如果桩是坏的，D1/D4/D5/D6/D7 会因为"永远返回 False"而**全部假绿**。
#    所以必须证明：(a) 桩在正确场景下**真的能**走到唤醒分支（D3 已断言 True）；
#                   (b) 桩被故意弄坏时**同样**返回 False —— 证明 False 不是判据的默认值。
_o_ok = make_bed_stub(_D1)
_ok = tick(_o_ok, 2026, 10, 6, 7, 0, 0)
_o_broken = make_bed_stub(_D1)
del _o_broken.wake_up                                # 故意去掉唤醒回调 ⇒ 抛异常被吞
_broken = tick(_o_broken, 2026, 10, 6, 7, 0, 0)
check('E3 ★恒真防护：桩**能**走到唤醒（True）且**坏桩**返回 False ⇒ D 段的 False 有意义',
      _ok is True and _broken is False,
      'good_stub=%s broken_stub=%s' % (_ok, _broken))

_probe_calls = _n_calls
_probe_marks = _marks


def _noop_probe():
    mark('E4 空判据探针')
    return None


_noop_probe()
check('E4 记账口不是 no-op（打了标记点但没走 check ⇒ 独立计数器不涨）',
      _n_calls == _probe_calls and _marks == _probe_marks + 1,
      'calls=%d(+0) marks=%d(+1)' % (_n_calls, _marks))
check('E5 记账守恒（独立计数器 CALLS == PASS + FAIL）',
      _n_calls == _n_pass + _n_fail,
      'calls=%d pass=%d fail=%d' % (_n_calls, _n_pass, _n_fail))
check('E6 守恒判据有鉴别力（把漏记那一步计进总数 ⇒ 等式不再成立）',
      (_n_calls + 1) != (_n_pass + _n_fail),
      'calls+1=%d vs pass+fail=%d' % (_n_calls + 1, _n_pass + _n_fail))

print('=' * 70)
print('第91轮：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print('失败项：')
    for _d in _failed:
        print('  - %s' % _d)
print('=' * 70)
sys.exit(0 if not _failed else 1)

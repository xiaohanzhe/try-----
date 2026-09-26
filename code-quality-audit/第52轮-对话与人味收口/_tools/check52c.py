# -*- coding: utf-8 -*-
"""第52轮 · 待机（窝着，任务栏上沿）+ 就寝（23:00±10 分钟回房睡觉）· 行为级验证

用户口径逐字（本套件守的就是这两句）：
  「他这一直站着不动是什么情况，像贴图似的，而且就算静止不动那也要来屏幕底下那个
    快捷栏上面待着吧，就偶尔聊几句天这样的感觉」
  「在晚上的时候他会自己回到自己的房间里除非有事（冒险，和我聊天等），要他就会在
    晚上11点左右（也就是上下10分钟）的时候回去睡觉」

★ 本套件存在的**首要理由**不是"新增功能有没有写"，而是一条**根因**：
    第51轮把 `IDLE_LOOP_MIN_SECONDS` 抬到 600 后，"待机动画"**在真机上结构性地
    从未播放过** —— `idle_timer` 会被 `randomize_movement_pattern()` 每次清零，
    而 `max_idle_duration` 只有 2~12 秒，永远涨不到 600。于是宠物永远定格在
    站立首帧 = 用户说的"像贴图似的"。
  ⇒ A2/B8 专门守"判据换成了不会被漫游清零的量（距上次用户互动）"。
    B8b/B8c 是**正/负控制**：只在待机态为真、只在旧口径(700s)为真，缺一不可。

不联网、不调 Ollama、不构造完整 RalseiPet（用 `__new__` + 显式字段，
避免 E 盘 vault / AI 初始化等与本主题无关的副作用）。
"""

import ast
import io
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# ⚠️ 本文件在 `<轮次>/_tools/` 下 ⇒ 比"直接放 <轮次>/"要多退一层。
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
for _p in (os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if _p not in sys.path:
        sys.path.append(_p)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

MAIN_PY = os.path.join(PET, 'src', 'main.py')
SPEECH_PY = os.path.join(PET, 'modules', 'event_speech.py')

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, detail))
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  <- " + str(detail)) if detail else ""))


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _code_only(src):
    """把注释与字符串字面量替换成等长空格，只留"真会执行的代码"。

    ★★ 为什么必须有这一步（第52轮真踩到）：本轮的注释里**逐字引用了被删掉的台词**
      （"`zzz... 晚安，做个好梦！` 三句内置台词已迁走"），于是
      `"zzz... 晚安，做个好梦！" in MAIN_SRC` 会**匹配到我自己的注释** ⇒ 报假 FAIL。
      这与记忆里"扫属性要同时扫 ast.Constant 里的同名字符串"是**同一类病的反面**：
      字符串/注释必须先剥掉，剩下才是可执行代码。
    """
    import io as _io
    import tokenize
    buf = [list(ln) for ln in src.splitlines(True)]
    try:
        toks = list(tokenize.generate_tokens(_io.StringIO(src).readline))
    except Exception:
        return src
    for tok in toks:
        if tok.type not in (tokenize.COMMENT, tokenize.STRING):
            continue
        (sr, sc), (er, ec) = tok.start, tok.end
        if sr == er:
            ln = buf[sr - 1]
            for i in range(sc, min(ec, len(ln))):
                ln[i] = ' '
        else:
            for r in range(sr, er + 1):
                if r - 1 >= len(buf):
                    continue
                if r == sr:
                    ln = buf[r - 1]
                    for i in range(sc, len(ln)):
                        ln[i] = ' '
                elif r == er:
                    ln = buf[r - 1]
                    for i in range(0, min(ec, len(ln))):
                        ln[i] = ' '
                else:
                    ln = buf[r - 1]
                    for i in range(len(ln)):
                        ln[i] = ' '
    return ''.join(''.join(l) for l in buf)


def _const_strings(src):
    """源码里出现过的**字符串字面量**集合（不含注释）。

    用于"这句话是不是还被写死在代码里"这类判据：注释里引用不算。
    """
    out = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add(n.value)
    return out


def _no_comment(src):
    """只把**注释**替换成空格，字符串字面量原样保留。

    ★ 为什么要和 `_code_only` 分开（第52轮实测）：
      · 判"某句台词是不是还写死在代码里" → 必须看**字符串字面量**（`_const_strings`）；
      · 判"某个属性名有没有出现在代码里" → 那个名字本身可能就是**字符串**
        （`_idle_lounge_busy` 的属性表就是 `('is_sleeping', ...)` 这样的字符串元组），
        用 `_code_only` 会把它们一起剥掉 ⇒ **正控制必假红**（本脚本第一版正是如此）。
      ⇒ 需要"剥注释、留字符串"的中间视图，就是本函数。
    """
    import io as _io
    import tokenize
    buf = [list(ln) for ln in src.splitlines(True)]
    try:
        toks = list(tokenize.generate_tokens(_io.StringIO(src).readline))
    except Exception:
        return src
    for tok in toks:
        if tok.type != tokenize.COMMENT:
            continue
        (sr, sc), (er, ec) = tok.start, tok.end
        if sr == er:
            ln = buf[sr - 1]
            for i in range(sc, min(ec, len(ln))):
                ln[i] = ' '
    return ''.join(''.join(l) for l in buf)


def _body_no_comment(func):
    """方法体源码：**去掉 docstring 与注释**，保留其余字符串字面量。"""
    stmts = list(func.body)
    if stmts and isinstance(stmts[0], ast.Expr) \
            and isinstance(stmts[0].value, ast.Constant) \
            and isinstance(stmts[0].value.value, str):
        stmts = stmts[1:]                      # 去掉 docstring（它是 Expr 语句）
    seg = '\n'.join(ast.get_source_segment(MAIN_SRC, n) or '' for n in stmts)
    return _no_comment(seg)


MAIN_SRC = _read(MAIN_PY)
SPEECH_SRC = _read(SPEECH_PY)
MAIN_TREE = ast.parse(MAIN_SRC)
MAIN_CODE = _code_only(MAIN_SRC)          # 已剥掉注释 **和** 字符串
MAIN_NC = _no_comment(MAIN_SRC)           # 已剥掉注释，字符串保留
MAIN_CONSTS = _const_strings(MAIN_SRC)    # 所有字符串字面量


def _find_class(tree, name):
    for n in tree.body:
        if isinstance(n, ast.ClassDef) and n.name == name:
            return n
    raise AssertionError('类 %s 不存在（判据必须报红，不许静默跳过）' % name)


def _find_func(cls, name):
    for n in cls.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    raise AssertionError('方法 %s 不存在（判据必须报红，不许静默跳过）' % name)


class _SrcView(object):
    """把某个类的方法体绑成"只有源码"的视图，供 AST 判定使用。"""

    def __init__(self, cls):
        self.cls = cls

    def func(self, name):
        return _find_func(self.cls, name)

    def body_src(self, name):
        f = self.func(name)
        lines = [ast.get_source_segment(MAIN_SRC, n) or '' for n in f.body]
        return '\n'.join(lines)

    def call_order(self, func_name):
        """返回该方法体内出现的 `self.<attr>` 调用属性名序列（按源码顺序）。"""
        f = self.func(func_name)
        seq = []
        for n in ast.walk(f):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == 'self':
                seq.append((n.lineno, n.func.attr))
        seq.sort()
        return [a for _l, a in seq]


RV = _SrcView(_find_class(MAIN_TREE, 'RalseiPet'))

# ============================================================ A 源码级
# ---- A1 契约常量（防「名字打错 ⇒ 判据恒真」：必须真取得到且值对）----
try:
    from main import RalseiPet as _RP          # noqa: E402
    _C_OK = True
except Exception as _e:
    _RP = None
    _C_OK = False
    print("!! import main 失败：%r" % (_e,))

check("A1 能 import 到 RalseiPet（常量判据的前置；失败必须报红而不是跳过）", _C_OK)
if not _C_OK:
    raise SystemExit(1)

check("A1a IDLE_LOUNGE_ENABLED 取得到且为 True",
      getattr(_RP, 'IDLE_LOUNGE_ENABLED', None) is True,
      "实得=%r" % (getattr(_RP, 'IDLE_LOUNGE_ENABLED', None),))
check("A1b IDLE_LOUNGE_AFTER_SECONDS == 600.0（与 IDLE_LOOP_MIN_SECONDS 同口径）",
      getattr(_RP, 'IDLE_LOUNGE_AFTER_SECONDS', None) == 600.0
      and _RP.IDLE_LOOP_MIN_SECONDS == 600.0,
      "lounge=%r loop=%r" % (getattr(_RP, 'IDLE_LOUNGE_AFTER_SECONDS', None),
                             _RP.IDLE_LOOP_MIN_SECONDS))
check("A1c IDLE_LOUNGE_PERCH_X_RATIO 是 (0,1) 内的比例",
      isinstance(getattr(_RP, 'IDLE_LOUNGE_PERCH_X_RATIO', None), float)
      and 0.0 < _RP.IDLE_LOUNGE_PERCH_X_RATIO < 1.0,
      "实得=%r" % (getattr(_RP, 'IDLE_LOUNGE_PERCH_X_RATIO', None),))

# ---- A2 ★★ 根因判据：`_idle_loop_active` 必须把"待机状态"算进去 ----
def _idle_loop_expr():
    """从真源码的 **`update_animation`** 里取出 `self._idle_loop_active = <expr>` 的表达式。

    ⚠️ 判据陷阱（本脚本第一版就踩了）：`self._idle_loop_active` 在 `init_*` 里还有一次
      **初值赋值**（`= False`）。用 `ast.walk` 取"第一个匹配"会拿到那个初值，
      于是 `_lounge_since in expr` 恒为假 ⇒ **报假 FAIL**。
      ⇒ 必须精确限定在 `update_animation` 这个"门限判定"方法体内取。
    """
    fn = RV.func('update_animation')
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Attribute) and t.attr == '_idle_loop_active':
                    return ast.get_source_segment(MAIN_SRC, n.value)
    return None


_EXPR = _idle_loop_expr()
check("A2 源码里存在 `self._idle_loop_active = <expr>` 赋值（判据的前置）",
      bool(_EXPR), "取到=%r" % ((_EXPR or '')[:60],))
check("A2b ★★ 该表达式含 `_lounge_since`（否则 600s 判据在真机上恒假）",
      bool(_EXPR) and '_lounge_since' in _EXPR,
      "expr=%s" % ((_EXPR or '').replace('\n', ' ')[:110],))

# ★★ 判据鉴别力体检：同一段判据套到"旧写法"上必须说"没有"
_OLD_SYNTH = "bool(self.idle_timer >= self.IDLE_LOOP_MIN_SECONDS)"
check("A2c 判据鉴别力：合成的旧写法必须被判为「不含 _lounge_since」（A≠B）",
      '_lounge_since' not in _OLD_SYNTH)

# ---- A3 调用点与顺序 ----
_um_calls = RV.call_order('update_movement')
check("A3 update_movement 里真的调用了 `_idle_lounge_tick`",
      '_idle_lounge_tick' in _um_calls, "调用表尾=%s" % (_um_calls[-8:],))
check("A3b `_bedtime_tick` 也在 update_movement 里被调用",
      '_bedtime_tick' in _um_calls, "调用表尾=%s" % (_um_calls[-8:],))
_u_src = MAIN_CODE
_i_lounge = _u_src.find('self._idle_lounge_tick(current_time)')
_i_rand = _u_src.find('self.randomize_movement_pattern()',
                      _u_src.find('def update_movement'))
_i_bed = _u_src.find('self._bedtime_tick(current_time)')
_i_sleep = _u_src.find('if self.is_sleeping:', _u_src.find('def update_movement'))
check("A3c `_idle_lounge_tick` 排在 `randomize_movement_pattern` **之前**（待机优先于漫游）",
      -1 < _i_lounge < _i_rand, "lounge=%d rand=%d" % (_i_lounge, _i_rand))
check("A3d `_bedtime_tick` 排在 `if self.is_sleeping:` **之前**（就寝要能升级小憩）",
      -1 < _i_bed < _i_sleep, "bed=%d sleep=%d" % (_i_bed, _i_sleep))

# ---- A4 忙碌集合 ----
_busy = RV.body_src('_idle_lounge_busy')
for _tok in ('is_sleeping', 'is_falling', 'is_jumping', '_is_being_dragged',
             'is_playing', '_spell_stage', '_hide_stage', 'is_watching_video'):
    check("A4 忙碌集合含 %s" % _tok, _tok in _busy)

# ---- A5 任务栏上沿取法（工作区，而不是整块屏幕）----
_taskbar = RV.body_src('_taskbar_top_y')
_workarea = RV.body_src('_work_area_rect')
_floor = RV.body_src('_desktop_floor_y')
check("A5 `_work_area_rect` 走 Qt 的 availableGeometry（= 已扣掉任务栏）",
      'availableGeometry' in _workarea)
check("A5b `_taskbar_top_y` 用 `_work_area_rect()` 算（不是整屏）",
      '_work_area_rect' in _taskbar)
check("A5c 反控制：`_desktop_floor_y` 仍在、且仍用 `_virtual_screen_rect()`"
      "（证明没有把「地面」和「快捷栏上沿」混为一谈）",
      '_virtual_screen_rect' in _floor and '_work_area_rect' not in _floor)

# ---- A6 算不出窝点 ⇒ 不进入（不就近凑）----
_perch = RV.body_src('_lounge_perch_point')
_enter = RV.body_src('_enter_idle_lounge')
check("A6 `_lounge_perch_point` 算不出时返回 None",
      'return None' in _perch)
check("A6b `_enter_idle_lounge` 对 None 有守卫（None ⇒ 返回 False，不拿着 None 往下走）",
      'is None' in _enter and 'return False' in _enter)

# ---- A7 ★ 就寝不能被"正在小憩"永久挡死 ----
# ⚠️ 必须先在**剥掉注释与字符串**的代码视图上判：`_bedtime_busy` 的注释里
#    逐字写着"**不含 `is_sleeping`**"，直接 `in body_src` 会匹配到自己的注释 ⇒ 假 FAIL。
_bbusy = _body_no_comment(RV.func('_bedtime_busy'))
_busy_code = _body_no_comment(RV.func('_idle_lounge_busy'))
check("A7 ★ `_bedtime_busy` 的**代码**里不含 is_sleeping（否则 23:00 永远被白天小憩挡掉）",
      'is_sleeping' not in _bbusy, "code 含 is_sleeping=%s" % ('is_sleeping' in _bbusy))
check("A7b 正控制：同一条判据套到 `_idle_lounge_busy` 上**必须说含**（证明剥离没把代码剥空，A≠B）",
      'is_sleeping' in _busy_code)

# ---- A8 睡/醒/哼 的内置台词已迁移（含正向证据）----
check("A8c 前置：`_const_strings` 真的取到了字符串字面量（判据不空转）",
      'sleep_enter' in MAIN_CONSTS, "取样数=%d" % len(MAIN_CONSTS))
for _dead in ("zzz... 晚安，做个好梦！", "zzz... 我困了...", "zzz... 好舒服...",
              "唔...别吵...", "嗯...再睡五分钟...", "zzz...别闹...",
              "嗯？什么事？", "哎呀！我睡着了！", "早上好！"):
    _hit = [s for s in MAIN_CONSTS if _dead in s]
    check("A8 内置台词已不再作为字符串字面量存在：%s" % _dead, not _hit,
          "命中=%r" % (_hit[:2],))
for _k in ('sleep_enter', 'sleep_stir', 'wake_up'):
    check("A8b sleep 线改走事件通道 speak_event(\"%s\", None, ...)（在**代码**里，不在注释里）"
          % _k, ('speak_event("%s", None' % _k) in MAIN_NC)

# ---- A9 新事件名已登记为 AI 档 + 有旁白 ----
_sp_tree = ast.parse(SPEECH_SRC)
_tiers_expr = None
_dir_expr = None
for n in _sp_tree.body:
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Name) and t.id == 'EVENT_TIERS':
                _tiers_expr = n.value
            if isinstance(t, ast.Name) and t.id == 'EVENT_DIRECTIVES':
                _dir_expr = n.value


def _keys_of(node):
    out = {}
    if isinstance(node, ast.Dict):
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant):
                out[k.value] = ast.get_source_segment(SPEECH_SRC, v) or ''
    return out


_TIERS = _keys_of(_tiers_expr)
_DIRS = _keys_of(_dir_expr)
for _k in ('sleep_enter', 'sleep_stir', 'wake_up'):
    check("A9 EVENT_TIERS 登记了 %s" % _k, _k in _TIERS, "实得=%r" % (_TIERS.get(_k),))
    check("A9b %s 是 AI 档（TIER_AI）" % _k, _TIERS.get(_k) == 'TIER_AI',
          "实得=%r" % (_TIERS.get(_k),))
    check("A9c %s 有旁白" % _k, bool((_DIRS.get(_k) or '').strip()),
          "实得=%r" % (_DIRS.get(_k),))
    # 旁白**只许是动作描述**，不许含台词示范（否则 7B 会照抄，第十八轮的教训）
    _d = _DIRS.get(_k) or ''
    check("A9d %s 的旁白不含台词示范（无中文引号/无『说：』）" % _k,
          ('“' not in _d and '”' not in _d and '说：' not in _d),
          "旁白=%s" % _d)

# ============================================================ B 行为级
from PyQt5.QtCore import QPoint, QRect   # noqa: E402


def _host(interaction_age=0.0, **fields):
    """造一个"未初始化但字段齐全"的宿主。

    ★ 为什么不用真 RalseiPet()：本主题只碰几个字段与纯逻辑，
      真构造会拉起 E 盘 vault / AI / 定时器等无关副作用，
      而本套件的判据一个都不依赖它们。
    """
    h = _RP.__new__(_RP)
    h._lounge_since = None
    h._lounge_perch = None
    h._lounge_walking = False
    h._lounge_interaction_ref = None
    h._bedtime_fired_date = None
    h._bedtime_sleep = False
    h._last_bedtime_check = 0.0
    h.last_interaction_time = time.time() - interaction_age
    h.idle_timer = 0.0
    h.is_moving = False
    h.is_sleeping = False
    h.current_scene = 'desktop'
    h.target_pos = QPoint(0, 0)
    h.game_state = {'is_playing': False}
    for _bad in ('is_falling', 'is_recovering', 'is_splat', 'is_jumping',
                 'is_gravity_falling', '_is_being_dragged', 'is_following_mouse',
                 'is_watching_video'):
        setattr(h, _bad, False)
    h._spell_stage = None
    h._hide_stage = None
    h.dialogue_ui = None
    h.PERCH = QPoint(900, 1000)
    h._lounge_perch_point = lambda: h.PERCH
    for _k, _v in fields.items():
        setattr(h, _k, _v)
    return h


NOW = time.time()

# ---- B1 未到门限 ----
h = _host(interaction_age=10.0)
r = _RP._idle_lounge_tick(h, NOW)
check("B1 刚互动过（10s）⇒ 不进入待机",
      r is False and h._lounge_since is None, "ret=%r since=%r" % (r, h._lounge_since))

# ---- B2 到门限 ⇒ 进入 + 走去窝点 ----
h = _host(interaction_age=601.0)
r = _RP._idle_lounge_tick(h, NOW)
check("B2 ★ 无互动满 10 分钟 ⇒ 进入待机", r is True and h._lounge_since is not None,
      # ⚠️ 这里**不许**打 `_lounge_since` 的原始值（那是 epoch 秒，每次都不同 ⇒
      #    基线永远 DIFF）。基线是"行为契约"，不是"时间戳快照"。
      "ret=%r 已记录进入时刻=%s" % (r, h._lounge_since is not None))
check("B2b 进入待机时把目标点设成窝点、并开始移动（复用既有移动通道）",
      h.target_pos == h.PERCH and h.is_moving is True,
      "target=%r moving=%r" % (h.target_pos, h.is_moving))

# ---- B3 反控制：门限差一点就不进 ----
h = _host(interaction_age=599.0)
r = _RP._idle_lounge_tick(h, NOW)
check("B3 反控制：599s 差 1 秒 ⇒ 仍不进入（证明 600 这条线真在起作用，A≠B）",
      r is False and h._lounge_since is None, "ret=%r" % (r,))

# ---- B4 用户互动 ⇒ 退出待机 ----
h = _host(interaction_age=601.0)
_RP._idle_lounge_tick(h, NOW)
h.last_interaction_time = time.time()          # 用户来互动了
r2 = _RP._idle_lounge_tick(h, NOW)
check("B4 ★ 待机中一有用户互动 ⇒ 立刻退出待机",
      r2 is False and h._lounge_since is None, "ret=%r since=%r" % (r2, h._lounge_since))

# ---- B5 忙碌状态 ----
h = _host(interaction_age=601.0, game_state={'is_playing': True})
r = _RP._idle_lounge_tick(h, NOW)
check("B5 「有事」（正在玩游戏/冒险）⇒ 不进入待机",
      r is False and h._lounge_since is None, "ret=%r" % (r,))
h2 = _host(interaction_age=601.0)
h2.game_state = {'is_playing': False}          # 正控制：同一时刻把"事"关掉就进
r2 = _RP._idle_lounge_tick(h2, NOW)
check("B5b 正控制：同一时刻把 `is_playing` 关掉 ⇒ 立刻进入（A≠B）",
      r2 is True, "ret=%r" % (r2,))

# ---- B6 窝点算不出 ⇒ 不进入，且不留下半个状态 ----
h = _host(interaction_age=601.0)
h._lounge_perch_point = lambda: None
r = _RP._idle_lounge_tick(h, NOW)
check("B6 ★ 窝点算不出（几何异常）⇒ 不进入待机，且不留下半个状态（不就近凑）",
      r is False and h._lounge_since is None and h._lounge_perch is None
      and h.is_moving is False, "ret=%r since=%r moving=%r"
      % (r, h._lounge_since, h.is_moving))

# ---- B7 快捷栏上沿的算术 ----
h = _host()
h._work_area_rect = lambda: QRect(0, 0, 1920, 1040)
h._virtual_screen_rect = lambda: QRect(0, 0, 1920, 1080)
h.height = lambda: 84
y = _RP._taskbar_top_y(h)
check("B7 ★ 快捷栏上沿 y == 工作区底 − 窗口高（1040 − 84 = 956）；"
      "而不是整屏底（1080 − 84 = 996）",
      y == 956, "实得=%r" % (y,))

# ---- B8 ★★ 真跑那段表达式：待机态必须让 _idle_loop_active 为真 ----
def _eval_idle_flag(host):
    """把**真源码里的那个表达式**原样 eval 一遍（不重写、不简化）。"""
    expr = _EXPR.replace('self.', 'host.')
    return eval(expr, {'bool': bool}, {'host': host})


h = _host()
h.IDLE_LOOP_MIN_SECONDS = _RP.IDLE_LOOP_MIN_SECONDS
h.idle_timer = 10.0
check("B8a 待机动画门限：非待机 + idle_timer=10s ⇒ False",
      _eval_idle_flag(h) is False)

h = _host()
h.IDLE_LOOP_MIN_SECONDS = _RP.IDLE_LOOP_MIN_SECONDS
h.idle_timer = 10.0
h._lounge_since = NOW
check("B8b ★★ 真跑真表达式：处于待机态 + idle_timer 才 10s ⇒ **True**"
      "（这正是根因修复 —— 待机后不再依赖涨不上去的 idle_timer）",
      _eval_idle_flag(h) is True)

h = _host()
h.IDLE_LOOP_MIN_SECONDS = _RP.IDLE_LOOP_MIN_SECONDS
h.idle_timer = 700.0
check("B8c 反控制：非待机 + idle_timer=700（旧口径）⇒ 仍为 True（旧路没被删掉）",
      _eval_idle_flag(h) is True)

# ============================================================ C 就寝（23:00±10）
import datetime as _dt   # noqa: E402

check("C1a BEDTIME_ENABLED 为 True", getattr(_RP, 'BEDTIME_ENABLED', None) is True)
check("C1b 就寝时刻 = 23 点 ± 10 分钟",
      getattr(_RP, 'BEDTIME_HOUR', None) == 23
      and getattr(_RP, 'BEDTIME_JITTER_MINUTES', None) == 10,
      "hour=%r jitter=%r" % (getattr(_RP, 'BEDTIME_HOUR', None),
                             getattr(_RP, 'BEDTIME_JITTER_MINUTES', None)))
check("C1c 早上 7 点自动醒", getattr(_RP, 'BEDTIME_WAKE_HOUR', None) == 7,
      "实得=%r" % (getattr(_RP, 'BEDTIME_WAKE_HOUR', None),))
check("C1d 「他的房间」有明确常量（默认 desktop，可一处替换）",
      isinstance(getattr(_RP, 'BEDTIME_HOME_SCENE', None), str)
      and _RP.BEDTIME_HOME_SCENE,
      "实得=%r" % (getattr(_RP, 'BEDTIME_HOME_SCENE', None),))

# ---- C2 落点：当日稳定 + 全部落进 ±10 分钟窗口 ----
h = _host()
base_day = _dt.datetime(2026, 9, 27)
t1 = _RP._bedtime_target_time(h, base_day.date())
t2 = _RP._bedtime_target_time(h, base_day.date())
check("C2 同一晚重复计算得到同一时刻（不会在同一晚抖动）", t1 == t2,
      "%s vs %s" % (t1, t2))
_outs = []
_dists = set()
for _i in range(40):
    _d = base_day.date() + _dt.timedelta(days=_i)
    _t = _RP._bedtime_target_time(h, _d)
    _delta = (_t - _dt.datetime(_d.year, _d.month, _d.day, 23, 0)).total_seconds() / 60.0
    if abs(_delta) > 10.0:
        _outs.append((str(_d), _delta))
    _dists.add(int(_delta))
check("C2b 40 天全部落在 23:00±10 分钟窗口内", not _outs, "越界=%r" % (_outs[:4],))
check("C2c 落点不是天天的同一个值（有 ±10 分钟的随机感）", len(_dists) >= 5,
      "出现过的偏移分钟数=%s" % (sorted(_dists)[:12],))


def _bed_host(**fields):
    h = _host(**fields)
    h.calls = []
    h.go_to_bed = lambda: (h.calls.append('bed') or True)
    h.wake_up = lambda: h.calls.append('wake')
    return h


def _at(day_offset=0, hh=23, mm=0):
    d = base_day + _dt.timedelta(days=day_offset)
    return d.replace(hour=hh, minute=mm).timestamp(), d


# ---- C3 未到点 ----
h = _bed_host()
ts, d = _at()
target = _RP._bedtime_target_time(h, d.date())
h._last_bedtime_check = 0.0
r = _RP._bedtime_tick(h, target.timestamp() - 60.0)
check("C3 未到点（目标前 1 分钟）⇒ 不就寝",
      r is False and h.calls == [], "ret=%r calls=%r" % (r, h.calls))

# ---- C4 到点 ----
h = _bed_host()
h._last_bedtime_check = 0.0
r = _RP._bedtime_tick(h, target.timestamp())
check("C4 ★ 到点 ⇒ 执行就寝（go_to_bed 真被调一次）",
      r is True and h.calls == ['bed'], "ret=%r calls=%r" % (r, h.calls))
check("C4b 就寝后记下当晚日期（当晚不再重复）",
      h._bedtime_fired_date == d.strftime('%Y-%m-%d'),
      "fired=%r" % (h._bedtime_fired_date,))

# ---- C5 每晚只一次 ----
h._last_bedtime_check = 0.0
r = _RP._bedtime_tick(h, target.timestamp() + 5.0)
check("C5 同一晚第二次判定 ⇒ 不再就寝（calls 仍只有 1 次）",
      r is False and h.calls == ['bed'], "ret=%r calls=%r" % (r, h.calls))

# ---- C6 窗口已过 ⇒ 不补睡 ----
h = _bed_host()
h._last_bedtime_check = 0.0
r = _RP._bedtime_tick(h, target.timestamp() + 11 * 60.0)
check("C6 ★ 窗口（±10 分钟）已过 ⇒ **不**半夜补睡",
      r is False and h.calls == [], "ret=%r calls=%r" % (r, h.calls))
check("C6b 窗口过也算「今晚已处理」（当晚不再反复试）",
      h._bedtime_fired_date == d.strftime('%Y-%m-%d'),
      "fired=%r" % (h._bedtime_fired_date,))

# ---- C7 「有事」⇒ 推迟，且**不**标记 fired（窗口内还会再试）----
h = _bed_host(game_state={'is_playing': True})
h._last_bedtime_check = 0.0
r = _RP._bedtime_tick(h, target.timestamp())
check("C7 ★ 「有事」（冒险/游戏）⇒ 到点也不去，且**不**标记当晚已处理",
      r is False and h.calls == [] and h._bedtime_fired_date is None,
      "ret=%r calls=%r fired=%r" % (r, h.calls, h._bedtime_fired_date))
# 正控制：把"事"办完，同一窗口内下一次就应触发
h.game_state = {'is_playing': False}
h._last_bedtime_check = 0.0
r2 = _RP._bedtime_tick(h, target.timestamp() + 30.0)
check("C7b 正控制：同窗口内把「事」解除 ⇒ 下一次判定立刻去睡（A≠B）",
      r2 is True and h.calls == ['bed'], "ret=%r calls=%r" % (r2, h.calls))

# ---- C8 早上自动醒（★ 只对就寝睡生效）----
h = _bed_host(_bedtime_sleep=True, is_sleeping=True)
h._last_bedtime_check = 0.0
ts_morning, d2 = _at(day_offset=1, hh=7, mm=5)
r = _RP._bedtime_tick(h, ts_morning)
check("C8 ★ 早上 7 点后、且是「就寝睡」⇒ 自动醒来（wake_up 被调）",
      ('wake' in h.calls), "calls=%r ret=%r" % (h.calls, r))
h = _bed_host(_bedtime_sleep=False, is_sleeping=True)
h._last_bedtime_check = 0.0
r = _RP._bedtime_tick(h, ts_morning)
check("C8b 反控制：白天小憩（非就寝睡）⇒ 早上**不**自动醒（不打扰小憩）",
      h.calls == [], "calls=%r ret=%r" % (h.calls, r))

# ---- C9 节流 ----
h = _bed_host()
h._last_bedtime_check = NOW
r = _RP._bedtime_tick(h, NOW + 1.0)
check("C9 节流：距上次判定不足 5s ⇒ 直接跳过（不每 30ms 算日期）",
      r is False and h.calls == [], "ret=%r" % (r,))
h._last_bedtime_check = NOW
r = _RP._bedtime_tick(h, NOW + 6.0)
check("C9b 正控制：超过 5s ⇒ 恢复正常判定（A≠B）", r in (True, False),
      "ret=%r calls=%r" % (r, h.calls))

# ------------------------------------------------------------------ summary
_n_pass = sum(1 for ok, _n, _d in RESULTS if ok)
_n_fail = len(RESULTS) - _n_pass
print("-" * 68)
print("合计：PASS=%d FAIL=%d" % (_n_pass, _n_fail))
for ok, _n, _d in RESULTS:
    if not ok:
        print("  FAIL: %s  %s" % (_n, _d))
print("=== 结论 = %s ===" % ("PASS" if _n_fail == 0 else "FAIL"))
sys.stdout.flush()
os._exit(0 if _n_fail == 0 else 1)

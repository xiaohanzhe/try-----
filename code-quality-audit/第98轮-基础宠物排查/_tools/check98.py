# -*- coding: utf-8 -*-
u"""第98轮回归锁：三处「用户视角可感知」的修复不许静默回退。

用户第98轮口径（原话）：
  「剩下的你决定，反正就是先把基础桌宠修好再说其他的，尤其是之前咱提到过的
    什么**抛物线**，什么**内置对话**等等东西，记住，追一定要**看录像而不是只读
    后台输出**，要不然你没办法发现用户视角下看到的bug」

⇒ 本轮三组修复全部**先真机录像 + 逐帧看画面取证**，再动代码：

【A 段】滑步：`update_animation` 的 `_use_force` 必须把 `walk_*`/`run_*` 也算"状态"
    根因：原式 `_use_force = is_same_category or new_animation in ('idle','sleep')`
      ⇒ `idle → walk_right` 属"跨组"且新动画非 `idle` ⇒ `force=False`
      ⇒ 被 `change_animation` 的**跨组冷却 ×2**（`animation_change_cooldown=0.8` ⇒ 1.6s）拦下
      ⇒ 宠物**保持站立姿势原地平移**最多 1.6 秒（用户视角 = "滑步/站着飘"）。
    修 = `_use_force` 增加 `or new_animation.startswith(('walk_', 'run_'))`。
    真机证据（`第98轮-基础宠物排查/_evidence/`）：
      · 修复前 `run_natural/rec97_anim.txt`：产品自己的 reject 日志 **14 条**
        `REJECT 'walk_*' (cur='idle') kw={'force': False}`；
        同期 CSV 里"**同容器尺寸** + 持续位移 + `idle`"的段 **2 段**
        （f116-f118 1.00s / f542-f545 1.37s，抽帧确认为站姿平移）。
      · 修复后 `run_natural_postfix/rec97_anim.txt`：同型 reject **0 条**、持续段 **0 段**。
    ★ 判据防坑：片段必须**同容器尺寸**才算滑步 —— `walk_`(38x80) → `idle`(138x94)
      的容器重定心会让窗口左上角必然位移 `(-(138-38)/2, -(94-80)/2) = (-50,-7)`，
      **可见宠物并不动**（`_compose_anchored_sprite` 把 alpha 中心钉在画布中心）。

【B 段】内置对话收口：摔落家族不许再直写 `dialogue_ui`
    `start_fall` / `trigger_splat` / `handle_fall` 的台词原来直写
    `self.dialogue_ui.add_dialogue(...)`（+ `show_dialogue()`），**绕过台词唯一入口**
    `speak_event`（→`_event_say`）⇒ 绕过 `_pick_event_line` 的去重与 AI 档位判定。
    修 = 9 处改走 `self.speak_event("fall", [...], face, instant=True)`
      （`instant=True` 保持"立刻说"，台词与表情逐字不变 ⇒ 观感不变，只回到唯一入口）。
    ★ 判据防坑：**必须先剥注释**再断言"不含 `dialogue_ui`" —— `start_fall` 的
      **原文**里有 2 处 `dialogue_ui`（全在注释里），纯文本扫描会**假红**。
      （同型坑已三次发作：95D1 → 96bC4 → 96b复检⑤。）

【C 段】重力坠落必须播坠落动画（不许被 `idle` 顶掉）
    `update_animation` 的 `if/elif` 链处理了 is_jumping / is_falling / is_recovering /
    is_using_item / is_spellcasting / is_sleeping / is_moving，**唯独漏了
    `is_gravity_falling`** ⇒ 落到最后的 `else` 算出 `idle`；而 `idle` 在 force 集合里
    ⇒ `force=True` **绕过优先级闸**（`fall`=4 > `idle`=1）⇒ 坠落动画 ~167ms 内被顶成站姿。
    用户视角 = "**从窗口上掉下来时保持站姿往下滑**"。
    真机证据：`run_natural_postfix/rec97_frames.csv` f228-f234
      `is_gravity_falling=True` 而 `anim='idle'`（y 15→1506，跨 3.5s）；
      `_tools/montage98.py` 抽帧拼图确认为**站姿下坠**。
    修 = `update_animation` 增加 `elif self.is_gravity_falling:` 分支，**保持当前动画**
      （坠落动画的唯一维护者是 `start_falling` 那一次切换，`handle_gravity_fall` 只管位移）。
    ★★ 但**还有第二条根因**（同注入 A/B 才逼出来）：`force=True` 会**绕过优先级闸**，
      `update_animation` 拦不住别人。`pet_ai` 的"关键过程"守卫
      （`_skip_if_critical` L222 / `trigger_action` L545）写的是
      `is_jumping or is_falling`，**漏了 `is_gravity_falling`** ⇒ 坠落期间状态机照跑，
      `state=="rest"` 就 `rest()` → `change_animation("idle", force=True)` ⇒ 顶掉坠落动画。
      修 = 两处守卫都补 `is_gravity_falling`（与第94轮补 `is_sleeping` 同一位置同一理由）。
      ⚠️ 未改 `spell_controller.py:264` 的同型条件：`start_falling` 在
      `_spell_stage is not None` 时直接 return ⇒ **两者互斥**，加了是死代码。

段一览
------
  A `_use_force` 纳入移动状态
    A1 前置锚点：`update_animation` 真源码可抽到、`_use_force` 赋值可定位
    A2 ★★★ 源码级：`_use_force` 表达式含 `startswith(('walk_', 'run_'))`
    A3 ★★★ 行为级：**按产品自己的表达式求值** walk→True / laugh→False / idle→True
    A4 ★★★ 行为级：真 `change_animation` —— 冷却内 `force=False` 被拒、`force=True` 通过
    A5 ★★★ 行为级：`force=True` 确实**绕过优先级闸**（`idle`(1) 能顶掉 `fall`(4)）
    A6 负控制（恢复式变异）：内存里去掉 `walk_/run_` 那半段 ⇒ A3 必须翻面为 False
  B 摔落家族台词收口到 `speak_event`
    B1 ★★★ `start_fall`/`trigger_splat`/`handle_fall`（**剥注释后**）不含 `dialogue_ui`
    B1b 三个函数（剥注释后）都确实含 `speak_event`（不是"把台词整个删掉"）
    B2 ★★★ 行为级：真跑 `start_fall(stub,'window_move')` ⇒ 台词来自 `speak_event`
        （`kind='fall'`, `instant=True`），**直写 `dialogue_ui` 调用数 = 0**
    B3 负控制：把一处改回直写 `dialogue_ui` ⇒ B1 必须翻面
  C 重力坠落不许被 `idle` 顶掉
    C1 前置锚点：`update_animation` 的 if/elif 链可达（能定位到 `is_jumping` 链根）
    C2 ★★★ 链上存在 `self.is_gravity_falling` 支（且不在最后那个 else 里）
    C3 负控制：链上把该支改名 ⇒ C2 必须翻面
    C4 ★★★ 第二条根因：`pet_ai` 的 `_skip_if_critical`/`trigger_action`（**剥注释后**）
        也含 `is_gravity_falling`
    C4b 两函数仍保留 `is_jumping`/`is_falling`（不是替换掉）
    C5 ★★★ 行为级：真 `_skip_if_critical`（桩 parent）重力坠落 ⇒ True、常态 ⇒ False
    C6 负控制：去掉该标志 ⇒ C4 必须翻面
  D 判据自身体检
    D1 恒真防护：本文件判据里没有 `check(..., True)` 形态
    D2 成功标记打印点唯一（供 G2 计数）
    D3 被测文件在盘
    D4 ★★ 剥注释链自证（合成样本：注释里的 token 必须被 `ast.unparse` 去掉）
    D5 ★★★ 成功标记字面量只能是打印模板（防 G2 计数**自匹配**）

★ 本套件零网络 / 零外部盘；Qt 走 offscreen（G2 注入 QT_QPA_PLATFORM）。
"""
import ast
import copy
import io
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
MAIN_PY = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
PET_DIR = os.path.join(ROOT, 'ralsei_pet')
SELF_PY = os.path.abspath(__file__)

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
    return io.open(p, encoding='utf-8', newline='').read()


MAIN_TEXT = _rd(MAIN_PY)
MAIN_TREE = ast.parse(MAIN_TEXT)


def _find_func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _func_code(name, tree=None):
    """按名字取函数的**规范化源码**：`ast.unparse(函数节点)`。

    一步到位：去注释 / 保留字符串字面量 / 顶格（不依赖文本切片缩进）。
    """
    node = _find_func(tree if tree is not None else MAIN_TREE, name)
    if node is None:
        return ''
    try:
        return ast.unparse(node)
    except Exception:
        return ''


def _norm(s):
    """归一化：去空白 + 统一引号，用于"某调用形态是否出现"。"""
    return re.sub(r'\s+', '', s or '').replace('"', "'")


def _assign_rhs(func_name, target_name, tree=None):
    """取函数内 `target = <expr>` 的 (源码串, AST 节点)。"""
    node = _find_func(tree if tree is not None else MAIN_TREE, func_name)
    if node is None:
        return None, None
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assign):
            for t in sub.targets:
                if isinstance(t, ast.Name) and t.id == target_name:
                    return ast.unparse(sub.value), sub.value
    return None, None


def _eval_expr_src(expr_src, **names):
    """用**产品自己的表达式源码**求值（不是我在测试里重写一份）。"""
    return eval(expr_src, dict(names))  # noqa: S307 - 被测对象就是产品自己的一行表达式


def _chain_tests(func_name, root_test_token):
    """在函数里找"if/elif 链"的测试串列表（链根 = 首个测试含 `root_test_token`）。

    返回 (tests, has_else_yielding_idle)；找不到返回 (None, None)。
    """
    fn = _find_func(MAIN_TREE, func_name)
    if fn is None:
        return None, None
    best = None
    for sub in ast.walk(fn):
        if isinstance(sub, ast.If):
            try:
                first = ast.unparse(sub.test)
            except Exception:
                continue
            if root_test_token in first:
                # 取"最长"的那条链（真正的主链）
                if best is None or _chain_len(sub) > _chain_len(best):
                    best = sub
    if best is None:
        return None, None
    tests, tail = _walk_chain(best)
    has_else_idle = False
    if tail is not None:
        try:
            has_else_idle = "new_animation = 'idle'" in ast.unparse(
                ast.Module(body=tail, type_ignores=[]))
        except Exception:
            has_else_idle = 'idle' in ast.unparse(ast.Module(body=tail, type_ignores=[]))
    return tests, has_else_idle


def _walk_chain(ifnode):
    tests = []
    cur = ifnode
    while isinstance(cur, ast.If):
        tests.append(ast.unparse(cur.test))
        if len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
            cur = cur.orelse[0]
        else:
            return tests, cur.orelse if cur.orelse else None
    return tests, None


def _chain_len(ifnode):
    n, cur = 0, ifnode
    while isinstance(cur, ast.If):
        n += 1
        if len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
            cur = cur.orelse[0]
        else:
            break
    return n


P('=' * 78)
P(u'# 第98轮回归锁：滑步(_use_force) + 台词收口(speak_event) + 重力坠落不被 idle 顶掉')
P('=' * 78)

_UA_CODE = _func_code('update_animation')
_UA_NORM = _norm(_UA_CODE)

# ============================================================ A 前置锚点
P('')
P('--- A 前置锚点')
_rhs_src, _rhs_node = _assign_rhs('update_animation', '_use_force')
check('A1 update_animation 真源码 / `_use_force` 赋值都能定位（非凭印象）',
      bool(_UA_CODE) and bool(_rhs_src),
      'code_len=%d rhs=%r' % (len(_UA_CODE), _rhs_src))

# ============================================================ A2 源码级
P('')
P('--- A2 `_use_force` 纳入 walk_*/run_*（源码级，剥注释）')
_a2_need = "startswith(('walk_','run_'))"
check("A2 `_use_force` 表达式含 `startswith(('walk_', 'run_'))`",
      _norm(_rhs_src or '').find(_a2_need) >= 0,
      'rhs=%r' % (_rhs_src,))

# ============================================================ A3 行为级（表达式求值）
P('')
P('--- A3 行为级：按产品自己的表达式求值')
_a3 = {}
if _rhs_src:
    for _an in ('walk_right', 'run_left', 'idle', 'laugh'):
        try:
            _a3[_an] = _eval_expr_src(_rhs_src, is_same_category=False,
                                      new_animation=_an)
        except Exception as _e:
            _a3[_an] = 'ERR:%s' % _e
check('A3 表达式求值：idle→walk_right 时 force=True（滑步修复的核心）',
      _a3.get('walk_right') is True,
      '值=%r（表达式=%s）' % (_a3.get('walk_right'), _rhs_src))
check('A3b 表达式求值：idle→run_left 时 force=True',
      _a3.get('run_left') is True, '值=%r' % (_a3.get('run_left'),))
check('A3c 表达式求值：idle→idle 时 force=True（既有语义未回退）',
      _a3.get('idle') is True, '值=%r' % (_a3.get('idle'),))
check('A3d 表达式求值：idle→laugh 时仍为 force=False（没变成"无脑全 force"）',
      _a3.get('laugh') is False, '值=%r' % (_a3.get('laugh'),))

# 表达式必须被真正**消费**（防"抽到一个没人用的死变量"）
_consumed = False
_ua_fn = _find_func(MAIN_TREE, 'update_animation')
if _ua_fn is not None:
    for sub in ast.walk(_ua_fn):
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == 'change_animation'):
            for kw in sub.keywords:
                if (kw.arg == 'force' and isinstance(kw.value, ast.Name)
                        and kw.value.id == '_use_force'):
                    _consumed = True
check('A3e `_use_force` 确实作为 `change_animation(..., force=_use_force)` 被消费',
      _consumed, '未找到 force=_use_force 调用')

# ============================================================ A4/A5 真 change_animation
P('')
P('--- A4/A5 行为级：真 `change_animation`（桩 self，真实方法体）')
from PyQt5.QtWidgets import QApplication  # noqa: E402
import time as _time  # noqa: E402

_app = QApplication.instance() or QApplication([])
sys.path.insert(0, os.path.join(PET_DIR, 'modules'))
sys.path.insert(0, os.path.join(PET_DIR, 'src'))

_RalseiPet = None
try:
    from main import RalseiPet as _RalseiPet  # noqa: E402
except Exception as _e:  # pragma: no cover
    P('  （import main 失败：%s）' % _e)


class _AnimStub:
    """`change_animation` 需要的**最小**属性面（无 Qt 依赖）。"""

    def __init__(self, cur, last_change, cooldown=0.8, pri=1,
                 sprites=('idle', 'walk_right', 'run_left', 'fall', 'fall_mad',
                          'laugh')):
        self.sprite_loader = types.SimpleNamespace(
            sprites={k: [object()] for k in sprites},
            note_animation_miss=lambda *a, **k: None)
        self.animation_priorities = {}
        self.current_animation = cur
        self.current_priority = pri
        self.last_animation_change = last_change
        self.animation_change_cooldown = cooldown
        self.current_frame = 0
        self.current_direction = 'down'
        self.previous_direction = 'down'
        self.game_state = {}


if _RalseiPet is not None:
    _now = _time.time()

    # A4a：冷却内 + force=False → 必须被拒（这正是滑步的成因）
    _s1 = _AnimStub('idle', _now)
    _r1 = _RalseiPet.change_animation(_s1, 'walk_right', force=False)
    check('A4a 冷却内 idle→walk_right(force=False) 被拒 ⇒ 复现滑步成因',
          _r1 is False and _s1.current_animation == 'idle',
          'ret=%r cur=%r' % (_r1, _s1.current_animation))

    # A4b：同一状态下 force=True → 必须通过
    _s2 = _AnimStub('idle', _now)
    _r2 = _RalseiPet.change_animation(_s2, 'walk_right', force=True)
    check('A4b 同一状态 idle→walk_right(force=True) 通过 ⇒ 修复有效',
          _r2 is True and _s2.current_animation == 'walk_right',
          'ret=%r cur=%r' % (_r2, _s2.current_animation))

    # A4c：冷却已过（>2×cooldown）时 force=False 也能过 ⇒ 说明原缺陷是"间歇"的
    _s3 = _AnimStub('idle', _now - 2.0)
    _r3 = _RalseiPet.change_animation(_s3, 'walk_right', force=False)
    check('A4c 冷却已过（>1.6s）时 force=False 也能通过（原缺陷间歇性）',
          _r3 is True, 'ret=%r' % (_r3,))

    # A5：force=True 绕过优先级闸 —— idle(1) 能顶掉 fall(4)
    _s4 = _AnimStub('fall', _now, pri=4)
    _r4f = _RalseiPet.change_animation(_s4, 'idle', force=False)
    _s5 = _AnimStub('fall', _now, pri=4)
    _r5 = _RalseiPet.change_animation(_s5, 'idle', force=True)
    check('A5 优先级闸只在 force=False 时生效：idle 带 force 能顶掉 fall'
          '（→ 重力坠落被站姿顶掉的机理）',
          _r4f is False and _r5 is True and _s5.current_animation == 'idle',
          'force=False ret=%r / force=True ret=%r cur=%r'
          % (_r4f, _r5, _s5.current_animation))
else:
    for _d in ('A4a 冷却内 idle→walk_right(force=False) 被拒 ⇒ 复现滑步成因',
               'A4b 同一状态 idle→walk_right(force=True) 通过 ⇒ 修复有效',
               'A4c 冷却已过（>1.6s）时 force=False 也能通过（原缺陷间歇性）',
               'A5 优先级闸只在 force=False 时生效：idle 带 force 能顶掉 fall'
               '（→ 重力坠落被站姿顶掉的机理）'):
        check(_d, False, 'import main 失败，跳过')

# ============================================================ A6 负控制
P('')
P('--- A6 负控制（恢复式变异）：去掉 walk_/run_ 那半段 ⇒ A3 必须翻面')
_a6_ok = False
_a6_detail = 'rhs 不是 BoolOp(Or)，无法做恢复式变异'
try:
    if isinstance(_rhs_node, ast.BoolOp) and len(_rhs_node.values) >= 2:
        _mut = ast.Expression(body=ast.BoolOp(
            op=ast.Or(), values=[copy.deepcopy(v) for v in _rhs_node.values[:-1]]))
        _mut_src = ast.unparse(_mut.body)
        _mut_val = _eval_expr_src(_mut_src, is_same_category=False,
                                  new_animation='walk_right')
        _a6_ok = (_mut_val is False)
        _a6_detail = '变异后表达式=%s ⇒ walk_right=%r' % (_mut_src, _mut_val)
except Exception as _e:
    _a6_detail = 'ERR %s' % _e
check('A6 负控制：去掉 walk_/run_ 支后 walk_right 求值为 False ⇒ A3 非恒真',
      _a6_ok, _a6_detail)

# ============================================================ B1 源码级
P('')
P('--- B1 摔落家族台词不再直写 dialogue_ui（源码级，**剥注释**）')
_FAMILY = ('start_fall', 'trigger_splat', 'handle_fall')
_b1_bad = []
_b1_no_speak = []
for _fn in _FAMILY:
    _c = _norm(_func_code(_fn))
    if 'dialogue_ui' in _c:
        _b1_bad.append(_fn)
    if 'speak_event' not in _c:
        _b1_no_speak.append(_fn)
check('B1 start_fall/trigger_splat/handle_fall（剥注释后）都不含 dialogue_ui',
      not _b1_bad, '仍含:%s' % (_b1_bad,))
check('B1b 三个函数（剥注释后）都确实含 speak_event（不是把台词整个删掉）',
      not _b1_no_speak, '缺 speak_event:%s' % (_b1_no_speak,))

# ============================================================ B2 行为级
P('')
P('--- B2 行为级：真跑 start_fall，台词只从 speak_event 出去')


class _FallStub:
    """`start_fall` 需要的**最小**属性面 + 两个记账器（直写 vs 唯一入口）。"""

    def __init__(self, sprites=('fall', 'fall_mad', 'idle')):
        self.is_falling = False
        self.game_state = {}
        self.sprite_loader = types.SimpleNamespace(
            sprites={k: [object()] for k in sprites})
        self.events = []
        self.emotion_system = types.SimpleNamespace(
            react_to_event=lambda e, d: self.events.append(e))
        self.anim_calls = []
        self.dui_calls = []
        self.speak_calls = []
        self.dialogue_ui = types.SimpleNamespace(
            add_dialogue=lambda *a, **k: self.dui_calls.append(('add', a, k)),
            show_dialogue=lambda *a, **k: self.dui_calls.append(('show', a, k)))
        self.spatial_pos = {'x': 0, 'y': 0, 'z': 0}
        self.current_speed_x = 10.0
        self.current_speed_y = 0.0

    def change_animation(self, name, force=False):
        self.anim_calls.append((name, force))
        return True

    def speak_event(self, kind, pool=None, face="happy", instant=False):
        self.speak_calls.append((kind, pool, face, instant))
        return "x"


if _RalseiPet is not None:
    _fs = _FallStub()
    _exc = None
    try:
        _RalseiPet.start_fall(_fs, 'window_move')
    except Exception as _e:
        _exc = '%s: %s' % (type(_e).__name__, _e)
    check('B2 真跑 start_fall 不抛异常（桩面够用）',
          _exc is None, '异常=%s' % _exc)
    check('B2b 台词来自 speak_event（kind=fall / instant=True）',
          len(_fs.speak_calls) == 1
          and _fs.speak_calls[0][0] == 'fall'
          and _fs.speak_calls[0][3] is True,
          'speak_calls=%r' % (_fs.speak_calls,))
    check('B2c 直写 dialogue_ui 的调用数 = 0（不再分叉）',
          len(_fs.dui_calls) == 0, 'dui_calls=%r' % (_fs.dui_calls,))
else:
    for _d in ('B2 真跑 start_fall 不抛异常（桩面够用）',
               'B2b 台词来自 speak_event（kind=fall / instant=True）',
               'B2c 直写 dialogue_ui 的调用数 = 0（不再分叉）'):
        check(_d, False, 'import main 失败，跳过')

# ============================================================ B3 负控制
P('')
P('--- B3 负控制：把一处改回直写 dialogue_ui ⇒ B1 必须翻面')
_b3_flip = False
_b3_detail = ''
try:
    _hit = u'self.speak_event("fall", ["\u54ce\u5440\uff01\u6211\u6454\u5012\u4e86\uff01"], "surprised", instant=True)'
    if _hit in MAIN_TEXT:
        _mut_text = MAIN_TEXT.replace(
            _hit,
            u'self.dialogue_ui.add_dialogue("ralsei", "\u54ce\u5440\uff01\u6211\u6454\u5012\u4e86\uff01", "surprised")',
            1)
        _mut_tree = ast.parse(_mut_text)
        _c_mut = _norm(_func_code('start_fall', _mut_tree))
        _b3_flip = ('dialogue_ui' in _c_mut)
        _b3_detail = '变异后 start_fall 含 dialogue_ui=%s' % ('dialogue_ui' in _c_mut)
    else:
        _b3_detail = '锚点串未找到（源码已被改动？）'
except Exception as _e:
    _b3_detail = 'ERR %s' % _e
check('B3 负控制（恢复式变异）：改回直写 dialogue_ui 后 B1 判据翻面',
      _b3_flip, _b3_detail)

# ============================================================ C 重力坠落
P('')
P('--- C 重力坠落：update_animation 必须有 is_gravity_falling 支')
_tests, _has_else_idle = _chain_tests('update_animation', 'is_jumping')
check('C1 定位到 update_animation 的 if/elif 链（链根含 is_jumping）',
      bool(_tests),
      'tests=%s' % (_tests,))
_c2 = bool(_tests) and any(
    t.strip() == 'self.is_gravity_falling' for t in _tests)
check('C2 ★★★ 链上存在 `self.is_gravity_falling` 支（且不在最后的 else 里）',
      _c2,
      'tests=%s' % (_tests,))
check('C2b 该链确实以"算出 idle"的 else 收尾（→ 缺这一支就会落成 idle）',
      bool(_has_else_idle), 'has_else_idle=%r' % (_has_else_idle,))

# ---- C3 负控制：把该支改名 ⇒ C2 必须翻面
#   ⚠️ 锚点必须带**分支体**才能唯一：`main.py` 里 `update_movement`（本轮之前就有）
#      也有一处 `elif self.is_gravity_falling:`（体是 `handle_gravity_fall(...)`），
#      只按"分支头"替换会改错地方 ⇒ 负控制**假绿**（本套件首轮真踩）。
#   ⚠️ 锚点还必须**CRLF 感知**：`MAIN_TEXT` 是 `newline=''` 读入的（字节忠实），
#      行间是 `\r\n`；直接写含 `\n` 的锚点会**匹配不到**（本套件第二轮真踩）。
_c3_flip = False
_c3_detail = ''
_C3_ANCHOR_LF = ('elif self.is_gravity_falling:\n'
                 '            new_animation = self.current_animation')
_C3_ANCHOR = (_C3_ANCHOR_LF.replace('\n', '\r\n')
              if '\r\n' in MAIN_TEXT else _C3_ANCHOR_LF)
_C3_REPL_LF = ('elif self.is_sleeping:\n'
               '            new_animation = self.current_animation')
_C3_REPL = (_C3_REPL_LF.replace('\n', '\r\n')
            if '\r\n' in MAIN_TEXT else _C3_REPL_LF)
try:
    _mut2 = MAIN_TEXT.replace(_C3_ANCHOR, _C3_REPL, 1)
    if _mut2 != MAIN_TEXT:
        _mut_tree2 = ast.parse(_mut2)
        _fn2 = _find_func(_mut_tree2, 'update_animation')
        _found = None
        if _fn2 is not None:
            for sub in ast.walk(_fn2):
                if isinstance(sub, ast.If):
                    tests2, _ = _walk_chain(sub)
                    if any(t.strip() == 'self.is_jumping' for t in tests2):
                        _found = any(t.strip() == 'self.is_gravity_falling'
                                     for t in tests2)
                        break
        _c3_flip = (_found is False)
        _c3_detail = '变异后仍能找到该支=%r' % (_found,)
    else:
        _c3_detail = '锚点（分支头+分支体）未找到'
except Exception as _e:
    _c3_detail = 'ERR %s' % _e
check('C3 负控制（恢复式变异）：把该支改名后 C2 判据翻面', _c3_flip, _c3_detail)

# ============================================================ C4 第二条根因
P('')
P('--- C4 `pet_ai` 的"关键过程"守卫也必须含 is_gravity_falling')
#   为什么还有第二条根因：`update_animation` 补了支之后，坠落期间**仍有**别的调用
#   以 `force=True` 把动画改成 idle —— `force=True` 绕过优先级闸，`update_animation`
#   拦不住。真机 `run_inj_gfall_after` 唯一残留段 f156-f161（fall 2 帧 → idle 4 帧）；
#   同期 `rec97_anim.txt` 有 `REJECT 'idle' (cur='fall') kw={}`（**无 force** 版被拒）
#   ⇒ 说明 pet_ai 在坠落期照样轮询状态机，`state=="rest"` 时走
#   `rest()` → `change_animation("idle", force=True)`。
#   `pet_ai` 自己的 docstring 写的就是"跳跃中/**掉落中**"，只是判据漏了重力坠落。
PET_AI_PY = os.path.join(PET_DIR, 'modules', 'pet_ai.py')
_pa_text = _rd(PET_AI_PY)
_pa_tree = ast.parse(_pa_text)

_c4_bad = [_fn for _fn in ('_skip_if_critical', 'trigger_action')
           if 'is_gravity_falling' not in _norm(_func_code(_fn, _pa_tree))]
check('C4 pet_ai `_skip_if_critical` / `trigger_action`（剥注释后）都含 is_gravity_falling',
      not _c4_bad, '缺:%s' % (_c4_bad,))

_c4b_bad = [_fn for _fn in ('_skip_if_critical', 'trigger_action')
            if 'is_falling' not in _norm(_func_code(_fn, _pa_tree))
            or 'is_jumping' not in _norm(_func_code(_fn, _pa_tree))]
check('C4b 两个函数仍保留 is_jumping / is_falling（不是把它替换成新标志）',
      not _c4b_bad, '缺:%s' % (_c4b_bad,))

# ---- C5 行为级：真 `_skip_if_critical`（桩 parent）
_PetAI = None
try:
    from pet_ai import PetAI as _PetAI  # noqa: E402
except Exception as _e:  # pragma: no cover
    P('  （import pet_ai 失败：%s）' % _e)


def _pa_stub(**flags):
    base = dict(_spell_stage=None, game_state={}, _is_being_dragged=False,
                is_jumping=False, is_falling=False, is_gravity_falling=False,
                is_sleeping=False)
    base.update(flags)
    return types.SimpleNamespace(parent=types.SimpleNamespace(**base))


if _PetAI is not None:
    _skip_g = _PetAI._skip_if_critical(_pa_stub(is_gravity_falling=True), True)
    _skip_j = _PetAI._skip_if_critical(_pa_stub(is_jumping=True), True)
    _skip_n = _PetAI._skip_if_critical(_pa_stub(), True)
    check('C5 行为级 `_skip_if_critical`：重力坠落 ⇒ True（AI 冻结）；常态 ⇒ False',
          _skip_g is True and _skip_n is False,
          'gfall=%r jumping=%r normal=%r' % (_skip_g, _skip_j, _skip_n))
else:
    check('C5 行为级 `_skip_if_critical`：重力坠落 ⇒ True（AI 冻结）；常态 ⇒ False',
          False, 'import pet_ai 失败，跳过')

# ---- C6 负控制：去掉该标志 ⇒ C4 判据翻面
#   ⚠️ 替换串必须**保留 `or`**：锚点本身含行首的 `or `，若只替成 `False` 会变成
#      `(A or B False))` ⇒ `ast.parse` 直接 `invalid syntax`（本套件首版真踩）。
_c6_flip = False
_c6_detail = ''
_C6_ANCHOR = "or getattr(self.parent, 'is_gravity_falling', False)"
try:
    if _C6_ANCHOR in _pa_text:
        _mut3_tree = ast.parse(_pa_text.replace(_C6_ANCHOR, 'or False'))
        _c6_code = _norm(_func_code('_skip_if_critical', _mut3_tree))
        _c6_flip = ('is_gravity_falling' not in _c6_code)
        _c6_detail = ('变异后仍含 is_gravity_falling=%s'
                      % ('is_gravity_falling' in _c6_code))
    else:
        _c6_detail = '锚点 %r 未找到' % _C6_ANCHOR
except Exception as _e:
    _c6_detail = 'ERR %s' % _e
check('C6 负控制（恢复式变异）：去掉该标志后 C4 判据翻面', _c6_flip, _c6_detail)

# ============================================================ E 鞠躬动画自身位移
P('')
P('--- E 鞠躬/特殊动画的"自身位移"：锚点必须逐帧按"角色本体"算')
#   用户口径：「想必你也看到了他在鞠躬那个动画的时候会自身位移，你看看怎么修」
#   旧口径 = "整动画**并集** alpha 包围盒"的**常量**偏移 ⇒ `act` 第 3~6 帧含
#     身体之外的**粉色爱心**，并集被撑宽 ⇒ 常量偏移把**身体整体**推走
#     （离线逐帧复算：本体中心左跳 20 屏幕px / 下跳 5px；115 组里 26 组跳动 >1px）。
#   新口径 = **逐帧最大 8-连通块**（角色本体）包围盒中心钉画布中心。
#     A/B：旧 26 组可见（峰 26px）→ 新 0 组 / 最大残余 0.0px。
_E_ALL = _find_func(MAIN_TREE, '_anim_anchor_offsets')
_E_ONE = _find_func(MAIN_TREE, '_anim_anchor_offset')
check('E1 `_anim_anchor_offsets`（逐帧表）与 `_anim_anchor_offset`（取第 i 帧）都存在',
      _E_ALL is not None and _E_ONE is not None,
      'all=%r one=%r' % (_E_ALL is not None, _E_ONE is not None))

_E_ARGS = [a.arg for a in _E_ONE.args.args] if _E_ONE is not None else []
check('E2 `_anim_anchor_offset` 接受 `frame_index`（能指定"第几帧"）',
      'frame_index' in _E_ARGS, 'args=%s' % (_E_ARGS,))

_E_LOOP = bool(_E_ALL) and any(isinstance(n, (ast.For, ast.While))
                               for n in ast.walk(_E_ALL))
_E_APP = bool(_E_ALL) and any(
    isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    and n.func.attr == 'append' for n in ast.walk(_E_ALL))
check('E3 `_anim_anchor_offsets` 确实**逐帧**算（循环 + append 收集每帧偏移）',
      _E_LOOP and _E_APP, 'loop=%r append=%r' % (_E_LOOP, _E_APP))

_E_CALLS = [n for n in ast.walk(MAIN_TREE)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == '_compose_anchored_sprite']
_E_FARG = [ast.unparse(n.args[4]) if len(n.args) >= 5 else '<缺>'
           for n in _E_CALLS]
check('E4 两个渲染分支都传 `self.current_frame`（不传 ⇒ 恒取第 0 帧 ⇒ 逐帧锚点失效）',
      len(_E_CALLS) >= 2 and all(a == 'self.current_frame' for a in _E_FARG),
      'calls=%d args=%s' % (len(_E_CALLS), _E_FARG))

# ---- E5/E6 行为级：真调产品的 `_anim_anchor_offsets`，本体中心用**独立**实现算
#   不变量（不依赖各帧尺寸是否一致）：
#     产品口径 `off_i = 本体中心_i − 帧中心_i` ⇒ `本体中心_i − off_i − 帧中心_i == 0`
#     逐帧都必须为 0；旧口径（整动画并集常量偏移）则必然不为 0。
_E_DEV_NEW = _E_DEV_OLD = None
_E_MSG = ''
try:
    import json as _json
    import numpy as _np
    import cv2 as _cv2
    from PyQt5.QtGui import QPixmap as _QPixmap
    from PyQt5.QtWidgets import QApplication as _QApp
    _qapp = _QApp.instance() or _QApp([])
    _genes = _json.load(io.open(
        os.path.join(PET_DIR, 'assets', 'animations.json'),
        encoding='utf-8'))['groups']
    _SPDIR = os.path.join(ROOT, 'deltarune_ralsei')

    def _frames_of(_n):
        _cur, _seen = _n, set()
        for _ in range(5):
            _g = _genes.get(_cur)
            if not _g:
                return []
            if _g.get('alias_of'):
                _cur = _g['alias_of']
                if _cur in _seen:
                    return []
                _seen.add(_cur)
                continue
            return list(_g.get('frames') or [])
        return []

    _ANIM_E = 'act'
    _E_FL = [f for f in _frames_of(_ANIM_E)
             if os.path.exists(os.path.join(_SPDIR, f))]
    if not _E_FL:
        raise RuntimeError('找不到 %s 的帧文件' % _ANIM_E)
    _srcdir = os.path.join(PET_DIR, 'src')
    if _srcdir not in sys.path:
        sys.path.insert(0, _srcdir)
    from main import RalseiPet as _RP
    _pet2 = _RP.__new__(_RP)
    _pet2.sprite_loader = types.SimpleNamespace(
        sprites={_ANIM_E: [_QPixmap(os.path.join(_SPDIR, f)) for f in _E_FL]})
    if hasattr(_pet2, '_anim_anchor_cache'):
        del _pet2._anim_anchor_cache
    _offs_new = list(_RP._anim_anchor_offsets(_pet2, _ANIM_E))

    # 独立实现（cv2 8-连通块最大块 = 角色本体），不参与产品的算法
    _E_BB = []
    _E_WH = []
    for _f in _E_FL:
        _buf = _np.fromfile(os.path.join(_SPDIR, _f), dtype=_np.uint8)
        _im = _cv2.imdecode(_buf, _cv2.IMREAD_UNCHANGED)
        if _im is None or _im.ndim < 3 or _im.shape[2] < 4:
            _E_BB.append(None)
            _E_WH.append((0, 0))
            continue
        _nlab, _lab, _st, _ = _cv2.connectedComponentsWithStats(
            (_im[:, :, 3] > 0).astype(_np.uint8), 8)
        _E_WH.append((_im.shape[1], _im.shape[0]))
        if _nlab <= 1:
            _E_BB.append(None)
            continue
        _k = int(_np.argmax(_st[1:, _cv2.CC_STAT_AREA])) + 1
        _E_BB.append((_st[_k, _cv2.CC_STAT_LEFT], _st[_k, _cv2.CC_STAT_TOP],
                      _st[_k, _cv2.CC_STAT_WIDTH], _st[_k, _cv2.CC_STAT_HEIGHT]))

    def _dev(offs):
        """逐帧 `|本体中心 − off − 帧中心|` 的最大值（新口径必须 ≈0）。"""
        mx = my = 0.0
        for _i, _bb in enumerate(_E_BB):
            if _bb is None or _i >= len(offs):
                continue
            _cx = _bb[0] + _bb[2] / 2.0
            _cy = _bb[1] + _bb[3] / 2.0
            _w, _h = _E_WH[_i]
            mx = max(mx, abs(_cx - offs[_i][0] - _w / 2.0))
            my = max(my, abs(_cy - offs[_i][1] - _h / 2.0))
        return (mx, my)

    _E_DEV_NEW = _dev(_offs_new)
    # 旧口径（负控制）：整动画**并集** alpha 包围盒 → 常量偏移
    _ux0 = _uy0 = 10 ** 9
    _ux1 = _uy1 = 0
    for _bb in _E_BB:
        if _bb is None:
            continue
        _ux0 = min(_ux0, _bb[0])
        _uy0 = min(_uy0, _bb[1])
        _ux1 = max(_ux1, _bb[0] + _bb[2])
        _uy1 = max(_uy1, _bb[1] + _bb[3])
    if _ux1 > _ux0:
        _E_DEV_OLD = _dev([((_ux0 + _ux1) / 2.0, (_uy0 + _uy1) / 2.0)] * len(_E_BB))
except Exception as _e:
    _E_MSG = 'ERR %s: %s' % (type(_e).__name__, _e)

check('E5 ★★★ 行为级（真调产品 `_anim_anchor_offsets`）：`act` 逐帧"本体中心 − 偏移 '
      '− 帧中心"必须 ≈0 ⇒ 鞠躬时身体不再被推走',
      _E_DEV_NEW is not None and _E_DEV_NEW[0] <= 1.0 and _E_DEV_NEW[1] <= 1.0,
      'dev=%s %s' % (_E_DEV_NEW, _E_MSG))
check('E6 ★★ 负控制（夹具分辨力）：换回"整动画并集常量偏移"（旧口径）后残差必须 >1px '
      '—— 否则 E5 只是恒真',
      _E_DEV_OLD is not None and max(_E_DEV_OLD) > 1.0,
      'dev_old=%s' % (_E_DEV_OLD,))

# ============================================================ F 原地踏步
P('')
P('--- F 原地踏步：目标不可达时必须放弃，不能"腿在迈、位置不动"')
#   用户口径：「他还有原地踏步的问题，你自己看看」
#   两条根因（均已实锤）：
#     根因 A：`generate_new_move_target` 的"安全区"用**硬编码** `sprite_size = int(50*2.0)`，
#       而 `update_movement` 的夹紧用**当前窗口尺寸** ⇒ 右边界允许 `right()−100`，
#       比真实可行界 `right()−138` 外扩 38px，恰好 **> 到达阈值 30px** ⇒ 数学上够不着。
#       真机证据：`run_natural_postfix` 实测 `target x=2460`。
#     根因 B：`autonomous_agent._enter_walking()` 把目标算成"桌面元素中心 ± 60~80px"，
#       经 `set_target_pos` 回调**直接**写 `target_pos`，完全绕过 `_clamp_pos_to_desktop`
#       ⇒ 元素贴边时越界。真机证据：`target = (-23, 243)`。
#   修 = ① 安全区改用动态窗口尺寸；② 回调补夹紧；③ `update_movement` 加
#        "连续 60 帧位移<0.5px ⇒ 放弃目标"的兜底。
#   ⚠️ `_norm()` **会删掉所有空白** ⇒ 判据里的字面量也必须写成无空格形式
#      （首版写成 `max(100, self.width(), self.height())` ⇒ 恒假 ⇒ F1 **假红**。
#       又一次"判据也是被测物"：我扫的是归一化后的串，却拿原始串去比）。
#   ⚠️ 循环变量**不能用 `_n`** —— 那是本文件的**全局计数器**，模块级 `for _n in ...`
#      会把它换成 AST 节点 ⇒ `check()` 里 `_n += 1` 直接 `TypeError`
#      （本条已在记忆里写过，本次仍踩：改叫 `_fnode`）。
_F_GNMT_SRC = _norm(_func_code('generate_new_move_target', MAIN_TREE)) \
    if _find_func(MAIN_TREE, 'generate_new_move_target') else ''
_F_UM = _find_func(MAIN_TREE, 'update_movement')
check('F1 选目标的安全区用**动态窗口尺寸**（不再是硬编码 `int(50 * 2.0)`）',
      'max(100,self.width(),self.height())' in _F_GNMT_SRC
      and '50*2.0' not in _F_GNMT_SRC,
      'hit=%r anti_hit=%r' % ('max(100,self.width(),self.height())' in _F_GNMT_SRC,
                              '50*2.0' in _F_GNMT_SRC))

_F_I_STUCK = _F_I_THR = None
if _F_UM is not None:
    for _fnode in ast.walk(_F_UM):
        if isinstance(_fnode, ast.If) and \
                '_no_progress_frames' in ast.unparse(_fnode.test):
            if _F_I_STUCK is None:
                _F_I_STUCK = _fnode.lineno
        if isinstance(_fnode, ast.Assign):
            for _t in _fnode.targets:
                if isinstance(_t, ast.Name) and _t.id == '_threshold_sq':
                    _F_I_THR = _fnode.lineno
check('F2 ★★★ "目标不可达"兜底存在，且**排在**到达判定 `_threshold_sq` **之前**'
      '（排在后面 ⇒ 先被判"已到达"，兜底永不生效）',
      _F_I_STUCK is not None and _F_I_THR is not None and _F_I_STUCK < _F_I_THR,
      'stuck@%s threshold_sq@%s' % (_F_I_STUCK, _F_I_THR))

_F_KW = None
for _fnode in ast.walk(MAIN_TREE):
    if isinstance(_fnode, ast.Call):
        for _k in _fnode.keywords:
            if _k.arg == 'set_target_pos':
                _F_KW = _k.value
check('F3 `set_target_pos` 回调内部做了 `_clamp_pos_to_desktop`（根因 B：模块回调'
      '直接写越界坐标、绕过夹紧）',
      _F_KW is not None and '_clamp_pos_to_desktop' in ast.unparse(_F_KW),
      'kw=%s' % (ast.unparse(_F_KW)[:130] if _F_KW is not None else None))

_F_TEST = None
if _F_UM is not None:
    for _fnode in ast.walk(_F_UM):
        if isinstance(_fnode, ast.If) and \
                '_no_progress_frames' in ast.unparse(_fnode.test):
            _F_TEST = ast.unparse(_fnode.test)
            break
_F_LO = _F_HI = None
_F_EXPR_ERR = ''
if _F_TEST:
    try:
        _s59 = types.SimpleNamespace(_no_progress_frames=59)
        _F_LO = eval(_F_TEST, {'getattr': getattr}, {'self': _s59})
        _s59._no_progress_frames = 60
        _F_HI = eval(_F_TEST, {'getattr': getattr}, {'self': _s59})
    except Exception as _e:
        _F_EXPR_ERR = 'ERR %s' % _e
check('F4 ★★★ 行为级（按产品自己的表达式求值）：59 帧 ⇒ 不放弃；60 帧 ⇒ 放弃'
      '（正/负控制成对，防恒真）',
      _F_LO is False and _F_HI is True,
      'expr=%r lo=%r hi=%r %s' % (_F_TEST, _F_LO, _F_HI, _F_EXPR_ERR))

_F_BODY_OK = False
if _F_UM is not None:
    for _fnode in ast.walk(_F_UM):
        if isinstance(_fnode, ast.If) and \
                '_no_progress_frames' in ast.unparse(_fnode.test):
            _body = ast.unparse(_fnode)
            _F_BODY_OK = ('is_moving = False' in _body) and ("'idle'" in _body
                                                            or '"idle"' in _body)
            break
check('F5 兜底分支确实"放弃目标"（`is_moving = False` + 切回 idle），'
      '不是只清个计数器',
      _F_BODY_OK)


def _static_runs(ys, tol=1.0):
    u'''把"位置几乎不变"的连续帧切成段（与 `analyze98_stepinplace.py` v2 同口径）。

    ★ 本函数存在的唯一理由（写进判据里，防以后又改回"整段跨度"）：
      v1 用"整段跨度 ≤3px"判 ⇒ 段内只要夹过**一帧**移动，跨度就被撑大
      ⇒ `run_far_before` f24-f49（**12.5s 完全不动**）被 f11-f109 整段淹没 ⇒ **漏报**。
      ⇒ 判据也得被验：下面 F6 用合成样本盯住这一点。
    '''
    runs, cur = [], [0]
    for i in range(1, len(ys)):
        if abs(ys[i] - ys[i - 1]) <= tol:
            cur.append(i)
        else:
            runs.append(cur)
            cur = [i]
    runs.append(cur)
    return runs


_F_SYN = [0, 0, 0, 0, 0, 9, 0, 0, 0, 0, 0]
_F_RUNS = _static_runs(_F_SYN)
check('F6 ★★ 判据自检：静止段不会被"段内夹一帧移动"淹没'
      '（合成样本 `[0]*5+[9]+[0]*5` ⇒ 必须切成两段；v1 会把它们当一段）',
      len(_F_RUNS) >= 2 and max(len(r) for r in _F_RUNS) <= 6,
      'runs=%s' % ([len(r) for r in _F_RUNS],))

# ============================================================ G 偏俯视落点
P('')
P('--- G 坠落落点 = "脚下的平面"（**偏俯视**），不是"屏幕最底边"（侧视）')
#   用户口径：「他下坠也不是直接下坠到屏幕底下啊，而且不是关掉窗口一瞬间就摔扁，
#     你总得摔到桌面上才能扁吧，是那种**偏俯视**2D游戏似的效果，不是侧视2D」
#     （补充澄清：「**是偏俯视不是俯视**」）。
#   改前：`max_y = self._desktop_floor_y()`（屏底）+ `if landed_floor is not None`
#     ⇒ **当帧立刻**落地（dy=0）⇒ 真机实测落点 `wy+wh == 1600 == 屏高`（**沉到任务栏下**），
#     逐帧单点 dy **94~98px**（用户感知 = "一眨眼就摔扁"）。
#   改后：落点 = 起点 y + `_fall_projection_px`（落差/5 × 32px，限幅 [32,320]），
#     且"落在哪块平面"与"掉多远"**同源**（缓存 `_fall_land_floor`）。
check('G1 存在模块级 `_fall_projection_px`（偏俯视落点的唯一出处）',
      _find_func(MAIN_TREE, '_fall_projection_px') is not None)

_G_GF_SRC = _norm(_func_code('handle_gravity_fall', MAIN_TREE))
check('G2 ★★★ `handle_gravity_fall` 的落点上限改由**偏俯视投影**决定'
      '（`max_y = int(self._fall_land_y)`），不再是 `_desktop_floor_y()`（屏底）',
      'max_y=int(self._fall_land_y)' in _G_GF_SRC
      and '_fall_projection_px' in _G_GF_SRC,
      'has_land_y=%r has_proj=%r' % ('max_y=int(self._fall_land_y)' in _G_GF_SRC,
                                     '_fall_projection_px' in _G_GF_SRC))

_G_IF_TEST = None
_gf = _find_func(MAIN_TREE, 'handle_gravity_fall')
if _gf is not None:
    for _gn in ast.walk(_gf):
        if isinstance(_gn, ast.If):
            _gt = ast.unparse(_gn.test)
            if 'new_y' in _gt and 'max_y' in _gt:
                _G_IF_TEST = _gt
                break
check('G3 ★★★ 落地条件是"**到达落点**"（`new_y >= max_y`），不再是'
      '"下方有楼板当帧落地"（`landed_floor is not None`）',
      _G_IF_TEST is not None and 'landed_floor' not in _G_IF_TEST,
      'test=%r' % (_G_IF_TEST,))

# ---- G4/G5 行为级：真调产品的 `_fall_projection_px`
_G_CASES = None
_G_MSG = ''
try:
    import sys as _sys_g
    _M = _sys_g.modules.get('main')
    if _M is None or not hasattr(_M, '_fall_projection_px'):
        raise RuntimeError('main 模块未加载（E5 可能先失败了）')
    _proj = _M._fall_projection_px
    _G_CASES = []
    for _frm, _to in ((10, 0), (0, 0), (20, 0), (100, 0), (10, 5)):
        _pp = types.SimpleNamespace(_fall_from_height=_frm)
        _G_CASES.append(((_frm, _to), _proj(_pp, {'platform_height': _to})))
except Exception as _e:
    _G_MSG = 'ERR %s: %s' % (type(_e).__name__, _e)
_G_D = dict(_G_CASES) if _G_CASES else {}
check('G4 ★★★ 行为级（真调产品 `_fall_projection_px`）：落差 2 层 ⇒ 64px；'
      '落差 0 ⇒ 兜底 32px（**可见下坠**，不是"原地不动"）；极高落差 ⇒ 封顶 320px',
      _G_D.get((10, 0)) == 64 and _G_D.get((0, 0)) == 32
      and _G_D.get((100, 0)) == 320 and _G_D.get((10, 5)) == 32,
      'cases=%s %s' % (_G_CASES, _G_MSG))
check('G5 ★★ 负控制（防恒真）：该函数**不是常量**（3 档落差给出 3 个不同值）'
      '—— 否则"偏俯视"会退化成"固定位移"，负控制无从分辨',
      len(set(_G_D.values())) >= 3 if _G_D else False,
      'values=%s' % (sorted(set(_G_D.values())) if _G_D else None,))

_G_ATTR_SRC = ''
for _gn in MAIN_TREE.body:
    if isinstance(_gn, ast.Assign) and any(
            isinstance(_t, ast.Name) and _t.id == '_FALL_VELOCITY_ATTRS'
            for _t in _gn.targets):
        _G_ATTR_SRC = ast.unparse(_gn)
        break
check('G6 落点缓存 `_fall_land_y` / `_fall_land_floor` 已纳入"**落地即清**"的属性表'
      '（漏了 ⇒ 下一次坠落沿用上一次的落点）',
      '_fall_land_y' in _G_ATTR_SRC and '_fall_land_floor' in _G_ATTR_SRC,
      'attrs~=%s' % (_G_ATTR_SRC[:150],))

# ============================================================ D 判据自身体检
P('')
P('--- D 判据自身体检')
_self_src = _rd(SELF_PY)
_self_tree = ast.parse(_self_src)

_trivial = 0
for node in ast.walk(_self_tree):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == 'check' and len(node.args) >= 2):
        if isinstance(node.args[1], ast.Constant) and node.args[1].value is True:
            _trivial += 1
check('D1 恒真防护：本套件判据里没有 check(..., True) 形态',
      _trivial == 0, 'trivial_checks=%d' % _trivial)

_mark = 0
for _node in ast.walk(_self_tree):
    if (isinstance(_node, ast.Call) and isinstance(_node.func, ast.Name)
            and _node.func.id == 'print' and _node.args):
        _a0 = _node.args[0]
        if (isinstance(_a0, ast.BinOp) and isinstance(_a0.op, ast.Mod)
                and isinstance(_a0.left, ast.Constant)
                and _a0.left.value == '[PASS] %s'):
            _mark += 1
check('D2 成功标记的打印点只出现 1 次（供 G2 计数）',
      _mark == 1, 'count=%d' % _mark)

check('D3 被测文件在盘', os.path.exists(MAIN_PY), MAIN_PY)

# D4 剥注释链自证（合成样本，不依赖产品注释会不会被以后改掉）
_DEMO = ('def f():\n'
         '    # \u6ce8\u91ca\u91cc\u6709 UNIQUE_TOKEN_XYZ\n'
         '    x = 1\n'
         '    return x\n')
_demo_code = ast.unparse(ast.parse(_DEMO))
check('D4 剥注释链自证：注释里的 token 必须被去掉（合成样本）',
      'UNIQUE_TOKEN_XYZ' in _DEMO and 'UNIQUE_TOKEN_XYZ' not in _demo_code,
      'demo_code=%r' % _demo_code)

# D5 防 G2 计数自匹配（过滤器与被比较值都**拆写**，否则本行自己就被扫成 bad）
_MARK = '[PA' + 'SS]'
_TMPL = _MARK + ' %s'
_bad_mark_lits = []
for _n3 in ast.walk(_self_tree):
    if (isinstance(_n3, ast.Constant) and isinstance(_n3.value, str)
            and _MARK in _n3.value and _n3.value != _TMPL):
        _bad_mark_lits.append(_n3.value)
check('D5 成功标记字面量只能是打印模板（防 G2 计数自匹配）',
      not _bad_mark_lits, 'bad=%r' % (_bad_mark_lits,))

# ---------------------------------------------------------------- 汇总
P('')
P('=' * 78)
P(u'第98轮回归锁：PASS=%d FAIL=%d 合计=%d' % (_passed, _failed, _n))
P('=' * 78)

sys.exit(1 if _failed else 0)

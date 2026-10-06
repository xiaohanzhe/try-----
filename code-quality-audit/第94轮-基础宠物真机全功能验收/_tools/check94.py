# -*- coding: utf-8 -*-
u"""第94轮回归锁：基础宠物真机全功能验收 → 三个真 bug 的修复事实。

锁什么
======
用户口径：「**现在所有其他的模块先不用管，主要就是基础模块（基础宠物）修复**」。

本轮先做**真机全功能验收**（`_tools/probe94_full.py`：移动/睡眠/跳跃/拖拽/甩飞/托盘，
复刻 `main.py` 的 `RalseiPet() + show()` 真启动路径），真机上抓到 3 个真 signal，
逐条定根因、修复，并在此钉住事实：

  A `pet_ai` 在**睡眠期间**照常触发 AI 动作 —— `_skip_if_critical()` 与
    `trigger_action()` 的守卫列表里有 施法/游戏/拖拽/跳跃/掉落，**唯独漏了
    `is_sleeping`** ⇒ `change_animation('idle')` 把 `sleep` 顶掉。
    真机实测 t=+6.2s 被顶掉（`_evidence/probe94_sleep.txt` ③ 段调用栈实锤：
    `pet_ai.py:231 update_state ← _update_state_impl ← check_action_triggers ← trigger_action`）。
    症状 = 用户口径里的「**睡着了却站着不动**」。
  B `update_animation` 想切回 `sleep` 时用的是
    `_use_force = is_same_category or (new_animation == 'idle')`
    ⇒ `sleep` 拿到 `force=False`，被"跨组冷却 ×2"挡住 ⇒ 一旦被顶掉就**无法自愈**
    （实测：顶掉后 `change_animation('sleep', force=False)` 连续被拒）。
    改为把 `sleep` 也当"状态恢复"（与 `idle` 同一条理由）。
  C 拖拽期间窗口尺寸会变（`idle` 容器 69x47 → 窗口 138x94；`cower` 25x29 → 50x58；
    `walk_*` 19x40 → 38x80 —— 因为 `idle`/`defend`/`victory`/`spell` 用的是**原作
    战斗立绘**、`walk_*`/`run_*` 是行走图），渲染路径 `setGeometry` 按**中心**回算
    ⇒ 破坏拖拽期唯一的不变量"窗口左上角 = 鼠标 − drag_position" ⇒ 下一个
    `mouseMoveEvent` 按**旧** `drag_position` 拽回 ⇒ 宠物先窜后弹（实测约 44/18px，
    `_evidence/probe94_drag2.txt` 逐步对账）。改为尺寸变化时**同步平移 `drag_position`**，
    使后续鼠标事件不再回拽 ⇒ 角色中心逐步精确前进（修后 center 偏差 = 0px）。

★ 顺带**否定**了一条假设（留痕，免得日后重复怀疑）：
  "窗口的透明留白会吞掉桌面点击" —— 实测**不成立**。`_evidence/probe94_hittest.txt`
  在**最坏情形 `idle` 138x94** 下，窗口内 4 个 `alpha==0` 采样点全部**不命中宠物**
  （`WindowFromPoint` 返回下层窗口），只有非零 alpha 才算命中
  ⇒ Qt 的 `WA_TranslucentBackground`（`WS_EX_LAYERED`）走 **alpha 逐像素命中**。
  故不设任何相关锁（无缺陷可守）。

★ 另一条**判定为"设计取舍、非缺陷"**（免得日后误改）：
  拖拽中窗口尺寸变化后，**抓取偏移会漂移** —— 左上角不再恒等于"鼠标 − 初始
  `drag_position`"，但**角色中心始终精确钉在鼠标上**（修后单步偏差 0px）。
  "保中心"与"保抓取偏移"在窗口尺寸变化时**必然不能同时成立**，
  而"角色在屏幕上不跳"才是用户看得见的那条 ⇒ 取保中心。

段一览
------
  A `pet_ai` 睡眠守卫：A1 `_skip_if_critical` 含 `is_sleeping` 提前返回 ·
    A2 `trigger_action` 同样含 · A3 **行为级**（真源码解剖 exec + 桩 parent，
    断言睡眠时**不调用** `change_animation`）· A4/A5 **行为级** `trigger_action` ·
    A6/A7 负控制（抠掉守卫 ⇒ 行为级断言必须翻面 + 夹具保真）
  B 睡眠自愈（`main`）：B1 AST 抽出**真实表达式** · B1b 唯一赋值 + 真被 `force=`
    消费 · B2 求值（`(False,'sleep')⇒True`；`(False,'idle')⇒True`；
    `(False,'walk_down')⇒False` —— 有鉴别力）·
    B3/B4 负控制（换掉 `'sleep'` ⇒ 必须翻面 + 夹具保真）·
    B5 第91轮那条 `elif self.is_sleeping: new_animation = "sleep"` 不许回退
    ★ 本段首版 4 红，病根在**判据侧**：`_use_force` 是**局部变量**（`ast.Name`），
      首版只认 `self._use_force`（`ast.Attribute`）⇒ 恒不匹配。即本项目铁律
      「**判据过窄 = 误报**」。现收双形态 + B1b 补严格性。
  C 拖拽锚点同步（`main`）：C1 AST 计数（`drag_position = QPoint(` == 2、
    `setGeometry(new_x, new_y, …)` == 2 —— **两个同构渲染分支都要修**，只修一处
    = 改一处漏一处）· C2 同步必须落在其守卫 `If` 的行范围内 ·
    C3 顺序：同步必须在 `setGeometry` **之前** · C4/C5 负控制（对调 ⇒ 翻面 + 保真）·
    C6 `QPoint` 已导入 · C7 负控制（抠掉 `_is_being_dragged` ⇒ 计数必须翻面）
  D 判据自身体检（恒真防护 · 记账守恒）

★ 本套件**零 UI / 不需要显示器 / 零网络 / 零外部盘**：只读源码 + 解剖执行纯逻辑。
  真机动态实测在 `_tools/probe94_*.py`（当证据，不进 G2）。
"""
import ast
import io
import os
import re
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
# ★ 变异测试钩子（第94轮）：允许把被测源码指到**临时副本**上，产品文件全程只读。
#   见 `_tools/mutate94.py` —— 「一条判据只有在『破坏它就会红』时才叫守卫」。
MAIN_PY = (os.environ.get('CHECK94_MAIN')
           or os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'))
PET_AI_PY = (os.environ.get('CHECK94_PET_AI')
             or os.path.join(ROOT, 'ralsei_pet', 'modules', 'pet_ai.py'))

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


MAIN_TEXT = io.open(MAIN_PY, encoding='utf-8').read()
PET_TEXT = io.open(PET_AI_PY, encoding='utf-8').read()


# ============================================================ 通用解剖工具
def _unparse(node):
    try:
        return ast.unparse(node)
    except Exception:
        return ''


def _method_src(text, cls_name, meth_name):
    """从**真源码**里取某个类方法的源码段 + AST 节点。

    ⚠️ `ast.get_source_segment` 给的段**带类内缩进**，直接 `ast.parse` 会
       `IndentationError` ⇒ 所有再解析处一律先 `textwrap.dedent`。
    """
    tree = ast.parse(text)
    for n in tree.body:
        if isinstance(n, ast.ClassDef) and n.name == cls_name:
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name == meth_name:
                    return (ast.get_source_segment(text, m) or _unparse(m)), m
    return None, None


def _exec_method(seg, extra_ns):
    """把一段方法源码编译进一个空类并返回那个类（吃**源码**，不吃手抄副本）。

    ★ 为什么要这么绕：这两个守卫的语义（"睡眠时整个 AI 冻结"）在**离屏套件里
      既没有 Qt 主循环、也没有真 parent**，只有把**真源码**解剖出来喂桩对象，
      才能"断行为不断赋值"。若在本套件里自己重写一遍同样的判断，
      那就成了"判据也是被测物"（自证循环）—— 本项目历轮铁律，禁止。
    """
    if not seg:
        return None
    ns = dict(extra_ns)
    ded = textwrap.dedent(seg)
    body = '\n'.join(('    ' + ln) if ln.strip() else '' for ln in ded.split('\n'))
    try:
        exec(compile(ast.parse('class _S:\n' + body), '<pure94>', 'exec'), ns)
    except Exception as e:  # pragma: no cover
        print('     [解剖失败] %r' % (e,))
        return None
    return ns.get('_S')


class _Parent(object):
    """轻量 parent 桩：属性随便加；`change_animation` 记账。"""

    def __init__(self, **kw):
        self.calls = []
        self.__dict__.update(kw)

    def change_animation(self, name, *a, **kw):
        self.calls.append(name)
        return True


_CLEAR = dict(_spell_stage=None, game_state={}, _is_being_dragged=False,
              is_jumping=False, is_falling=False)
_LOG_STUB = type('_L', (), {'debug': lambda *a, **k: None})()


# ============================================================ A. pet_ai 睡眠守卫
P('')
P('---- A. `pet_ai` 睡眠守卫（第94轮修复 A）----')

_a_seg, _a_node = _method_src(PET_TEXT, 'PetAI', '_skip_if_critical')
_t_seg, _t_node = _method_src(PET_TEXT, 'PetAI', 'trigger_action')
_a_src = _a_seg or ''
_t_src = _t_seg or ''


def _has_sleep_guard(src):
    """谓词：存在 `if getattr(self.parent, 'is_sleeping', False): return ...` 形态的守卫。"""
    if not src:
        return False
    try:
        tree = ast.parse(textwrap.dedent(src))
    except Exception:
        return False
    for n in ast.walk(tree):
        if isinstance(n, ast.If):
            t = _unparse(n.test)
            if 'is_sleeping' in t and 'self.parent' in t:
                for st in n.body:
                    if isinstance(st, ast.Return):
                        return True
    return False


def _strip_sleep_guard(src):
    """变异：把 `is_sleeping` 守卫整段删掉（用于负控制）。"""
    if not src:
        return src
    try:
        tree = ast.parse(textwrap.dedent(src))
    except Exception:
        return src
    lines = textwrap.dedent(src).split('\n')
    kill = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.If) and 'is_sleeping' in _unparse(n.test):
            for ln in range(n.lineno - 1, n.end_lineno):
                kill.add(ln)
    return '\n'.join(ln for i, ln in enumerate(lines) if i not in kill)


check(u'A1 `_skip_if_critical()` 有 `is_sleeping` **提前返回**守卫'
      u'（原来只守 施法/游戏/拖拽/跳跃/掉落）', _has_sleep_guard(_a_src),
      u'段落 %d 字符' % len(_a_src))
check(u'A2 `trigger_action()` 也有同一守卫（它可被直接调用，不能只靠上层拦）',
      _has_sleep_guard(_t_src), u'段落 %d 字符' % len(_t_src))

# ---- A3 行为级：`_skip_if_critical` 真源码解剖 + 桩 parent，喂"睡/醒" ----
_S_A = _exec_method(_a_seg, {})
_ok_skip = False
if _S_A is not None:
    try:
        _s = _S_A()
        _s.parent = _Parent(is_sleeping=True, **_CLEAR)
        _r_sleeping = _s._skip_if_critical()
        _s.parent.is_sleeping = False
        _r_awake = _s._skip_if_critical()
        _ok_skip = (_r_sleeping is True and _r_awake is False)
        P('     行为级：is_sleeping=True -> %r ; False -> %r' % (_r_sleeping, _r_awake))
    except Exception as e:  # pragma: no cover
        P('     行为级执行异常：%r' % (e,))
check(u'A3 **行为级**（真源码解剖执行）：睡眠时 `_skip_if_critical()` 判 True、'
      u'清醒时判 False（正/负成对）', _ok_skip)

# ---- A4 行为级：`trigger_action` 在睡眠时不得改动画（"睡着却站着"的直接成因）----
_S_T = _exec_method(_t_seg, {'_log': _LOG_STUB})
_ok_trig = False
if _S_T is not None:
    try:
        _s2 = _S_T()
        _p2 = _Parent(is_sleeping=True, **_CLEAR)
        _s2.parent = _p2
        _s2.trigger_action('idle')
        _n_sleep = len(_p2.calls)
        _p2.is_sleeping = False
        _s2.trigger_action('idle')
        _n_awake = len(_p2.calls)
        _ok_trig = (_n_sleep == 0 and _n_awake == 1 and _p2.calls == ['idle'])
        P('     行为级：睡眠时 change_animation 调用 %d 次；清醒时共 %d 次 %r'
          % (_n_sleep, _n_awake, _p2.calls))
    except Exception as e:  # pragma: no cover
        P('     行为级执行异常：%r' % (e,))
check(u'A4 **行为级**：睡眠时 `trigger_action(\'idle\')` **不**改动画；清醒时才改',
      _ok_trig)

# ---- A5/A6 负控制：抠掉守卫 ⇒ A3/A4 必须翻面 ----
_mut_a = _strip_sleep_guard(_a_src)
_mut_t = _strip_sleep_guard(_t_src)
check(u'A5 负控制·夹具保真：抠掉守卫后源码确实变了',
      bool(_a_src) and (_mut_a != _a_src) and (_mut_t != _t_src),
      u'len %d->%d / %d->%d' % (len(_a_src), len(_mut_a), len(_t_src), len(_mut_t)))
_S_M = _exec_method(_mut_a, {})
_S_M2 = _exec_method(_mut_t, {'_log': _LOG_STUB})
_mut_flip = False
if _S_M is not None and _S_M2 is not None:
    try:
        _m = _S_M()
        _m.parent = _Parent(is_sleeping=True, **_CLEAR)
        _flip1 = (_m._skip_if_critical() is not True)
        _m2 = _S_M2()
        _pm = _Parent(is_sleeping=True, **_CLEAR)
        _m2.parent = _pm
        _m2.trigger_action('idle')
        _flip2 = (len(_pm.calls) != 0)
        _mut_flip = bool(_flip1 and _flip2)
        P('     变异后：_skip_if_critical()=%r ; trigger_action 改动画 %d 次'
          % (_m._skip_if_critical(), len(_pm.calls)))
    except Exception as e:  # pragma: no cover
        P('     变异执行异常：%r' % (e,))
check(u'A6 负控制：抠掉守卫后 A3/A4 两条行为级判据**必须翻面**（证明它们不是恒真）',
      _mut_flip)


# ============================================================ B. 睡眠自愈（force）
P('')
P('---- B. 睡眠自愈：`sleep` 也必须 `force=True`（第94轮修复 B）----')

_b_expr = None
_b_line = None
_b_assigns = []
_, _u_node = _method_src(MAIN_TEXT, 'RalseiPet', 'update_animation')
if _u_node is not None:
    for n in ast.walk(_u_node):
        # ★ 判据侧踩坑留痕（本套件首版就栽在这里，全 B 段 4 红）：
        #   `_use_force` 在真源码里是**局部变量**（`ast.Name`），不是属性
        #   （`self._use_force` / `ast.Attribute`）。首版只认 Attribute ⇒ 恒不匹配
        #   ⇒ 报"抽不到真实表达式"。这就是本项目铁律里的「**判据过窄 = 误报**」。
        #   故这里两种形态都收；再用 B1b 的"唯一赋值 + 被 force= 消费"补回严格性。
        if isinstance(n, ast.Assign) and any(
                (isinstance(t, ast.Attribute) and t.attr == '_use_force')
                or (isinstance(t, ast.Name) and t.id == '_use_force')
                for t in n.targets):
            _b_assigns.append(n)
    _b_assigns.sort(key=lambda x: x.lineno)
    if _b_assigns:
        _b_expr = ast.get_source_segment(MAIN_TEXT, _b_assigns[0].value)
        # ★★ 第95轮：**不回显绝对行号**。原写法打 `main.py:13610`，只要在它上方
        #   插入/删除任何行（第95轮正是在 `update_animation` 里加了守卫+注释 9 行），
        #   基线就必然 DIFF（第95轮全量回归实测：check94 只因行号变化报 DIFF）。
        #   回显"表达式本身"信息等价（表达式才是身份），且对无关编辑稳定。
        #   断言条件**一字未改**。
P(u'     抽出表达式 = %r' % (_b_expr,))

_b_use = bool(re.search(r'change_animation\(\s*new_animation\s*,\s*force=_use_force\s*\)',
                        MAIN_TEXT))
check(u'B1b `_use_force` 在 `update_animation` 内**唯一赋值**、且真被 '
      u'`change_animation(..., force=_use_force)` 消费（防"抽到一个没人用的死变量"）',
      len(_b_assigns) == 1 and _b_use,
      u'赋值处数=%d 被消费=%r' % (len(_b_assigns), _b_use))   # ★ 第95轮：不回显行号


def _ev(expr, is_same_category, new_animation):
    if not expr:
        return None
    try:
        return bool(eval(expr, {'__builtins__': {}},
                         {'is_same_category': is_same_category,
                          'new_animation': new_animation}))
    except Exception:
        return None


check(u'B1 能抽出 `_use_force` 的真实表达式（AST，不是手抄）', bool(_b_expr),
      'expr=%r' % (_b_expr,))
_ok_b = False
if _b_expr:
    _r = (_ev(_b_expr, False, 'sleep'), _ev(_b_expr, False, 'idle'),
          _ev(_b_expr, False, 'walk_down'), _ev(_b_expr, True, 'walk_down'))
    _ok_b = (_r[0] is True and _r[1] is True and _r[2] is False and _r[3] is True)
    P(u'     求值 (is_same_category, new_animation) → force：'
      u'(False,sleep)=%r (False,idle)=%r (False,walk_down)=%r (True,walk_down)=%r' % _r)
check(u'B2 求值：`sleep` 与 `idle` 都必须 force=True；`walk_down` 必须**不** force'
      u'（负控制：判据有鉴别力）', _ok_b)

_mut_expr = (_b_expr or '').replace(u"'sleep'", u"'sleep__x'")
check(u'B3 负控制·夹具保真：把表达式里的 `\'sleep\'` 换掉后确实变了',
      bool(_b_expr) and _mut_expr != _b_expr, 'mut=%r' % (_mut_expr,))
check(u'B4 负控制：换掉 `\'sleep\'` 后 `(False,"sleep")` 必须翻成 False',
      bool(_b_expr) and _ev(_mut_expr, False, 'sleep') is False,
      u'翻面后=%r' % (_ev(_mut_expr, False, 'sleep') if _b_expr else None,))

_b5 = False
if _u_node is not None:
    # ⚠️ 循环变量**不能叫 `_n`** —— 它是本文件的全局计数器（`check()` 里 `_n += 1`），
    #    被 `ast.walk` 的节点覆盖后会炸 `TypeError: unsupported operand for +=: 'Load'`。
    for _nd5 in ast.walk(_u_node):
        if isinstance(_nd5, ast.If) and 'is_sleeping' in _unparse(_nd5.test):
            for _st5 in _nd5.body:
                if (isinstance(_st5, ast.Assign)
                        and any(getattr(t, 'id', None) == 'new_animation' for t in _st5.targets)
                        and 'sleep' in _unparse(_st5.value)):
                    _b5 = True
# ★★ 判据恒真坑（第94轮变异测试实测抓到的）：
#   本条首版写成"全文件正则找 `elif self.is_sleeping:` + `new_animation = \"sleep\"`"，
#   结果把 L9775 那条**注释**（里面正好抄了这个片段）也算了进去 ⇒ 真代码被删掉后
#   判据**照样为真**（`mutate94` 的 M5 变异实测 FAIL=0）。恒真判据比不写还危险：
#   它看着在守"睡眠动画能被选中"，其实什么都没守。
#   ⇒ 改为 **AST 定位 + 限定在 `update_animation` 函数体内**，注释天然不会进 AST。
check(u'B5 第91轮那条 `elif self.is_sleeping: new_animation = "sleep"` 未被回退'
      u'（否则睡眠动画根本不会被选中，B 无从谈起）', _b5)


# ============================================================ C. 拖拽锚点同步
P('')
P('---- C. 拖拽期间同步 `drag_position`（第94轮修复 C）----')


def _c_facts(text):
    """AST 抽事实：`setGeometry(new_x, new_y, …)` 位置 / 被"正在拖拽"守卫包住的
    `drag_position = QPoint(...)` 同步块。

    ★ 守卫必须**同时**含 `_is_being_dragged` 与 `drag_position`（即 `is not None` 那半句）——
      只写前者会让"非拖拽时也改写抓取偏移"，只写后者等于没有拖拽条件。
    """
    tree = ast.parse(text)
    sgs, syncs = [], []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            t = _unparse(n)
            if t.startswith('self.setGeometry(') and 'target_width' in t and 'target_height' in t:
                sgs.append(n)
        if isinstance(n, ast.If):
            t = _unparse(n.test)
            if '_is_being_dragged' not in t or 'drag_position' not in t:
                continue
            for st in ast.walk(n):
                if isinstance(st, ast.Assign) and any(
                        isinstance(x, ast.Attribute) and x.attr == 'drag_position'
                        for x in st.targets) and 'QPoint' in _unparse(st.value):
                    syncs.append((n, st))
    return sorted(sgs, key=lambda x: x.lineno), sorted(syncs, key=lambda x: x[1].lineno)


_C_SG, _C_SYNC = _c_facts(MAIN_TEXT)
P(u'     setGeometry(…target_width…) = %d 处；被"拖拽中"守卫包住的 `drag_position` '
  u'同步 = %d 处' % (len(_C_SG), len(_C_SYNC)))
check(u'C1 两个**同构渲染分支**都要有同步（计数都必须是 2 —— 只修一处 = 改一处漏一处）',
      len(_C_SG) == 2 and len(_C_SYNC) == 2,
      u'setGeometry=%d sync=%d' % (len(_C_SG), len(_C_SYNC)))
check(u'C2 同步语句必须落在其守卫 `If` 的**行范围内**（不能在守卫块外面）',
      len(_C_SYNC) == 2 and all(n.lineno <= st.lineno <= n.end_lineno
                                for n, st in _C_SYNC))
_ok_order = (len(_C_SG) == len(_C_SYNC) == 2 and
             all(s[1].lineno < g.lineno for s, g in zip(_C_SYNC, _C_SG)))
P(u'     偏移：sync-setGeometry = %r（负数 = 同步在前，即 C3 期望）'
  % ([s[1].lineno - g.lineno for s, g in zip(_C_SYNC, _C_SG)],))
check(u'C3 顺序：同步必须在 `setGeometry` **之前**（放后面就等于没修）', _ok_order)

# ---- C4/C5 负控制：把两段对调 ⇒ C3 必须翻面 ----
_lines = MAIN_TEXT.split('\n')
_swapped = None
if len(_C_SYNC) == 2 and len(_C_SG) == 2:
    _s, _g = _C_SYNC[0], _C_SG[0]
    _a_lo, _a_hi = _s[0].lineno - 1, _s[0].end_lineno      # if 块
    _b_lo, _b_hi = _g.lineno - 1, _g.end_lineno            # setGeometry 语句
    _swapped = '\n'.join(_lines[:_a_lo] + _lines[_b_lo:_b_hi] + _lines[_a_hi:_b_lo]
                         + _lines[_a_lo:_a_hi] + _lines[_b_hi:])
check(u'C4 负控制·夹具保真：对调后源码确实变了',
      _swapped is not None and _swapped != MAIN_TEXT)
_sw_ok = False
if _swapped is not None:
    try:
        _sg2, _sy2 = _c_facts(_swapped)
        _sw_ok = (len(_sg2) == 2 and len(_sy2) == 2 and
                  not all(s[1].lineno < g.lineno for s, g in zip(_sy2, _sg2)))
        P('     对调后：sync-setGeometry = %r（正数 = 顺序已翻面）'
          % ([s[1].lineno - g.lineno for s, g in zip(_sy2, _sg2)],))
    except Exception as e:  # pragma: no cover
        P('     对调后解析异常：%r' % (e,))
check(u'C5 负控制：把两段对调后 C3 的**顺序判据必须翻面**（证明它不是恒真）', _sw_ok)

check(u'C6 同步用到 `QPoint` ⇒ 必须已导入（否则运行时 NameError，只在拖拽时爆）',
      bool(re.search(r'^from PyQt5\.QtCore import[^\n]*\bQPoint\b', MAIN_TEXT, re.M)))

# ---- C7 负控制：抠掉守卫里的 `_is_being_dragged` ⇒ 同步计数必须翻面 ----
_mut_c = MAIN_TEXT.replace(u"getattr(self, '_is_being_dragged', False)",
                           u"getattr(self, '__dragged_x', False)")
_c_fid = (_mut_c != MAIN_TEXT)
_sg3, _sy3 = _c_facts(_mut_c)
P(u'     抠掉守卫后：sync=%d 处（原 %d 处）' % (len(_sy3), len(_C_SYNC)))
check(u'C7 负控制：抠掉守卫里的 `_is_being_dragged` 后，同步计数必须从 2 掉到 0'
      u'（夹具保真 + 判据翻面）',
      _c_fid and len(_sy3) == 0 and len(_C_SYNC) == 2)


# ============================================================ D. 判据自身体检
P('')
P('---- D. 判据自身体检 ----')
_self = ast.parse(io.open(os.path.abspath(__file__), encoding='utf-8').read())
_const_checks = []
for n in ast.walk(_self):
    if isinstance(n, ast.Call) and getattr(n.func, 'id', None) == 'check' and len(n.args) >= 2:
        if isinstance(n.args[1], ast.Constant):
            _const_checks.append(_unparse(n.args[1]))
check(u'D1 恒真防护：本文件没有 `check(..., <常量>)` 的死判据',
      not _const_checks, u'常量判据=%s' % (_const_checks or u'无'))
check(u'D2 记账守恒：PASS + FAIL == 判据总数', _passed + _failed == _n,
      u'PASS=%d FAIL=%d 共=%d' % (_passed, _failed, _n))

P('')
P(u'=' * 78)
P(u'合计 %d 条判据：PASS=%d  FAIL=%d' % (_n, _passed, _failed))
P(u'=' * 78)
if _failed:
    P(u'（存在 FAIL ⇒ 基础宠物的睡眠/拖拽修复被回退或改坏，必须查。）')
sys.exit(0 if not _failed else 1)

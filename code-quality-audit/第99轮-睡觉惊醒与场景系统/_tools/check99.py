# -*- coding: utf-8 -*-
u"""第99轮回归锁：**睡觉后惊醒**不许静默回退。

用户口径（原文）
----------------
「**先从睡觉后惊醒做**」—— 即第96b轮登记的用户计划项「**睡着点醒播惊吓动画**」。
（★ 注意口径是"播**惊吓动画**"，不是"物理上跳起来"——见下方"已知未实现项"。）

本轮落的 6 件事
---------------
1. **接线**：`update_movement` 的睡眠两拍里，第二拍原来只 `wake_up()`
   （播 `pose` + 派 `wake_up` 事件 = "被温柔叫醒"），**没有任何"惊"**。
   ⇒ 改为 `wake_up()` 之后追加 `trigger_surprise()`。
   ★ **顺序不能倒**：`is_sleeping` 分支在 `update_animation` 的 if/elif 链里排在
   `is_surprised` **之前**，不先醒来就永远播不到惊喜（第91轮的同一坑）。
2. **立刻落画面**（`trigger_surprise` 自己切）：只置标志不够 —— `<pose> → surprised_*`
   是**跨组**切换（冷却 0.8×2 = **1.6s**），而惊讶只持续 **2.0s**；
   且第54轮契约写明"表演/情绪动画不由静止分支自动驱动" ⇒ 必须本函数自己切。
3. **不硬拆第8轮契约**（"特殊动画播完为止"）：睡着被点第一下时，
   `play_animation_once("look_up")` 把 `_play_once_active` 置 True，于是
   `change_animation` 那条"特殊→特殊不许打断"的守卫会把 `surprised_down` 一并拦下。
   ⇒ 改为把一次性的**回归目标**（`next_animation`）改成惊吓脸，等它播完自然落地。
   （`look_up` 只有 4 帧，惊讶窗口 2.0s ⇒ 脸一定来得及露。）
4. **还原点**（第96b轮"接线前置①"的落地）：`is_surprised` 分支把
   `jump_height` / `jump_duration` 写死成 `20` / `0.5` 且**永不还原**
   ⇒ 惊讶过一次就把之后**所有**跳跃变成"矮而快"。改为先存原值、清除时还原。
5. **一次性标志复位**（真缺陷）：原实现是 `if not hasattr(self, 'surprised_jump')`
   ⇒ 设上之后**永不删除**（`reset_special_states` 也没清它）
   ⇒ **惊讶只会跳一次**，第二次只剩表情、不再跳。
6. ★★★ **"两拍"塌成"一拍"**（真缺陷；**真机录像抓到的**，`check99` 首版的 C2 是**假绿**）：
   第二拍原来只判"5 秒内"+"已迷糊过一次"，**没判"又发生了一次互动"**，而它整个嵌在
   `if current_time - self.last_interaction_time < 1.0:` 里 ⇒ **同一次**互动后的 1 秒内
   每个 tick 都满足外层条件 ⇒ 第一拍（tick#1）之后**下一个 tick（50~100ms）**
   立刻走第二拍 ⇒ 碰一下就直接惊醒，"第一次只翻身哼哼"**从未生效**。
   修 = 补 `and self.last_interaction_time > self._sleep_stir_time`（必须是一次**新的**互动）。
   取证：真机录像 f35(t=11.02s, 仍 `sleep`) → f36(t=11.27s, 已 `sleeping=False`&`spr=True`)；
   决定性仿真 `_tools` 同目录的推导见报告 §99。

已知未实现项（A8/A9 两条**绊线**锁着，别把它读成"已实现"）
----------------------------------------------------------
`is_surprised` 的"跳一下"块（`update_animation`）**嵌在 `elif self.is_moving:` 的 body 里**
⇒ 站着/睡着的宠物被吓到**只会变脸、不会跳**（`jump_count` 也不会涨）。
而且该块**从不置 `is_jumping`** ⇒ 即便可达，`handle_jump` 的抛物线物理也不会跑
（`jump_height` 在第96b轮已被证为**死变量**：2 写 0 读）。
⇒ 本轮交付的是用户口径里的"**播惊吓动画**"；物理跳是**遗留**，已登记，不在本轮伪造。

判据纪律
--------
`print('[PASS] %s')` 字面量；判据名不自带标记；正/负控制成对；断行为不断赋值；
A 段走 **AST**（不吃注释里的字面量、不受 EOL 影响）；B/C 段**真起 `RalseiPet()`** 驱动；
★★ C 段必须按**真机定时器节奏**驱动（连续多 tick）—— 首版每个动作只驱动**一次**，
于是"第二拍要等下一次互动"这条恰好看不出来（**夹具不保真 = 假绿**，本轮实证）。
零网络（AI 不可用即走既有回退）；不需要显示器（offscreen）；零外部盘。
"""
import ast
import os
import re
import sys
import time
import traceback

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

MAIN = os.path.join(PKG, 'src', 'main.py')

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


# ★ 文本模式（默认 universal newlines）⇒ CRLF 归一为 LF：`SRC.replace('\n...')` 才能命中。
#   ★ 只用于**改字**与 AST；事实核对一律走 AST（行号/字面量都由 AST 给）。
with open(MAIN, encoding='utf-8') as _fh:
    SRC = _fh.read()
TREE = ast.parse(SRC)


def _func(name, tree=None):
    for n in ast.walk(tree if tree is not None else TREE):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _src_of(name, tree=None):
    """函数节点的**规范化源码**（`ast.unparse`）。★ 走 AST 不吃注释/文档串。"""
    fn = _func(name, tree)
    return ast.unparse(fn) if fn is not None else ''


def _has(text, needle):
    return needle in text


def _stir_if(tree, want_count):
    """取"**直接**包含 `self._sleep_stir_count = <want_count>` 那一句"的 If 节点。

    ★ 教训（本轮首跑）：`ast.walk` 命中的**第一个**含该赋值的 If 是**最外层**的
      `if self.is_sleeping:`（它的 body 里只有 `return`）⇒ 拿它去判"第二拍做了什么"
      会得到 `after=return`，判据报假红。必须按"**直接**包含"（identity）定位。
    :return: `(赋值节点, 包着它的 If 节点)`；定位不到 → `(None, None)`
    """
    fn = _func('update_movement', tree)
    if fn is None:
        return None, None
    node = None
    for n in ast.walk(fn):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Attribute)
                and n.targets[0].attr == '_sleep_stir_count'
                and isinstance(n.value, ast.Constant)
                and n.value.value == want_count):
            node = n
            break
    if node is None:
        return None, None
    for n in ast.walk(fn):
        if isinstance(n, ast.If) and any(s is node for s in n.body):
            return node, n
    return node, None


def _stir_if_body(tree, want_count):
    """`(赋值节点, 该 If 的 body)`。"""
    node, ifn = _stir_if(tree, want_count)
    return node, (list(ifn.body) if ifn is not None else None)


def _after_txt(node, body):
    """同层里排在 `node` 之后的语句（`ast.unparse` 串接）。"""
    if body is None:
        return ''
    return ' | '.join(ast.unparse(s) for s in body
                      if getattr(s, 'lineno', -1) > node.lineno)


# ============================================================ A. 源码级（AST）
mark('A 源码级：惊醒接线 / 还原点 / 一次性标志复位')

_TS = _src_of('trigger_surprise')
_RJ = _src_of('_restore_surprised_jump')
_UA = _src_of('update_animation')
_RS = _src_of('reset_special_states')
_UM = _src_of('update_movement')

check('A0 五个方法都真取到了（防「取不到 ⇒ `not in` 恒真」）',
      all(bool(x) for x in (_TS, _RJ, _UA, _RS, _UM)),
      'lens=%s' % [len(x) for x in (_TS, _RJ, _UA, _RS, _UM)])

check('A1 `trigger_surprise` 里**显式**把惊吓落到画面'
      '（`change_animation(_target, force=True)`）且方向只分 down / up'
      '（left/right 无惊喜素材 ⇒ 不猜）',
      _has(_TS, 'change_animation(_target, force=True)')
      and "'down': 'surprised_down'" in _TS
      and "'up': 'surprised_behind'" in _TS,
      'has_call=%s' % _has(_TS, 'change_animation(_target, force=True)'))

check('A1b ★不硬拆第8轮契约：正有"一次性特殊动画"在播时，改为把'
      '`next_animation` 换成惊吓脸（而不是硬切）',
      _has(_TS, '_play_once_active') and _has(_TS, "self.next_animation = _target")
      and _has(_TS, '_is_special_anim(self.current_animation)'),
      'deferred=%s' % _has(_TS, 'self.next_animation = _target'))

check('A2 `update_animation` 的惊讶分支**先存还原点**（`_surprised_saved_jump`）'
      '再改 `jump_height` / `jump_duration`',
      '_surprised_saved_jump' in _UA
      and 'jump_height' in _UA and 'jump_duration' in _UA
      and _UA.index('_surprised_saved_jump') < _UA.index('jump_height = 20'),
      'saved_before_write=%s'
      % ('_surprised_saved_jump' in _UA
         and _UA.index('_surprised_saved_jump') < _UA.index('jump_height = 20')))

check('A3 `_restore_surprised_jump` 三件事都做：**还原** `jump_height` /'
      ' `jump_duration` + 删掉还原点 + **删掉**一次性标志 `surprised_jump`',
      _has(_RJ, 'self.jump_height = _saved[0]')
      and _has(_RJ, 'self.jump_duration = _saved[1]')
      and _has(_RJ, 'del self._surprised_saved_jump')
      and "'surprised_jump'" in _RJ and _has(_RJ, 'del self.surprised_jump'),
      'del_flag=%s' % _has(_RJ, 'del self.surprised_jump'))

check('A4 惊讶状态**清除处**必须调用 `_restore_surprised_jump`（否则还原点永不生效）',
      '_restore_surprised_jump' in _UA and 'is_surprised = False' in _UA,
      'called=%s' % ('_restore_surprised_jump' in _UA))

check('A5 `reset_special_states` 也必须复位（它已清 `is_surprised`，'
      '若不复位则还原点/标志跨过这次 reset 留下来）',
      '_restore_surprised_jump' in _RS, 'rs_head=%s' % _RS[:60])

# ★ A6：睡眠第二拍的接线 —— 用**语句序列**判（内层 If 的 body），不认注释
_n_wake, _n_body = _stir_if_body(TREE, 2)
_after = _after_txt(_n_wake, _n_body) if _n_wake is not None else ''
check('A6 睡眠**第二拍**（`_sleep_stir_count = 2` 之后）必须既 `wake_up()` '
      '又 `trigger_surprise()`（这才是"惊醒"）',
      'self.wake_up()' in _after and 'self.trigger_surprise()' in _after,
      'after=%s' % _after[:160])

check('A6b ★顺序不许倒：`wake_up()` 必须**排在** `trigger_surprise()` 之前'
      '（`is_sleeping` 分支在 `update_animation` 里排在 `is_surprised` 之前，'
      '不先醒来就永远播不到惊喜）',
      _after.find('self.wake_up()') != -1
      and _after.find('self.wake_up()') < _after.find('self.trigger_surprise()'),
      'order_ok=%s' % (_after.find('self.wake_up()') != -1
                       and _after.find('self.wake_up()')
                       < _after.find('self.trigger_surprise()')))

# --- A7 恢复式变异负控制：逐个抠掉 ⇒ A6/A6b 的判据必须报红 ---
_MUT = re.sub(r'self\.wake_up\(\)\s*\n\s*self\.trigger_surprise\(\)',
              'self.wake_up()', SRC, count=1)
check('A7a 夹具保真：变异真的改了字（`_MUT != SRC`）', _MUT != SRC,
      'changed=%s' % (_MUT != SRC))
_m_wake, _m_body = _stir_if_body(ast.parse(_MUT), 2)
_m_after = _after_txt(_m_wake, _m_body) if _m_wake is not None else ''
check('A7b ★变异负控制：抠掉第二拍的 `trigger_surprise()` ⇒ A6 的判据必须**不成立**'
      '（证明 A6 有鉴别力，不是恒真）',
      _m_after != _after and 'self.trigger_surprise()' not in _m_after,
      'mutated_after=%s' % _m_after[:120])

_MUT2 = re.sub(r'self\.wake_up\(\)\s*\n\s*self\.trigger_surprise\(\)',
               'self.trigger_surprise()', SRC, count=1)
_m2_wake, _m2_body = _stir_if_body(ast.parse(_MUT2), 2)
_m2_after = _after_txt(_m2_wake, _m2_body) if _m2_wake is not None else ''
_m2_order_ok = (_m2_after.find('self.wake_up()') != -1
                and _m2_after.find('self.wake_up()')
                < _m2_after.find('self.trigger_surprise()'))
check('A7c ★变异负控制（顺序）：把两者对调 ⇒ A6b 的"顺序"判据必须**不成立**'
      '（证明 A6b 有鉴别力）',
      not _m2_order_ok, 'swapped_after=%s order_ok=%s' % (_m2_after[:120], _m2_order_ok))

# ★ A6c：第二拍的条件必须**要求一次新的互动**（否则"两拍"会塌成"一拍"）
_, _stir2_if = _stir_if(TREE, 2)
_stir2_test = ast.unparse(_stir2_if.test) if _stir2_if is not None else ''
check('A6c ★★★ 第二拍的触发条件必须含"**必须是一次新的互动**"'
      '（`self.last_interaction_time > self._sleep_stir_time`）—— '
      '否则同一次互动后的每个 tick 都满足外层 `< 1.0` ⇒ 第一拍的下一个 tick 就走第二拍，'
      '"第一次只翻身哼哼"形同虚设（真机录像实测：0.25s 内从 sleep 到 spr=True）',
      'self.last_interaction_time > self._sleep_stir_time' in _stir2_test,
      'test=%s' % _stir2_test[:200])
# 负控制：把这个条件从源码里抠掉 ⇒ 同一判据必须不成立（证明它有鉴别力）
_mut3 = SRC.replace('                      and self.last_interaction_time'
                    ' > self._sleep_stir_time):\n', '                      ):\n', 1)
_, _stir2_mut_if = _stir_if(ast.parse(_mut3), 2)
_stir2_mut_test = (ast.unparse(_stir2_mut_if.test)
                   if _stir2_mut_if is not None else '')
check('A6d ★变异负控制：抠掉"新互动"那一项 ⇒ A6c 的判据必须**不成立**'
      '（证明 A6c 不是恒真；且夹具保真 `_mut3 != SRC`）',
      _mut3 != SRC
      and 'self.last_interaction_time > self._sleep_stir_time'
      not in _stir2_mut_test,
      'changed=%s mut_test=%s' % (_mut3 != SRC, _stir2_mut_test[:140]))

# --- A8/A9 ★★ 登记（绊线）：把"已知未实现"锁成可被推翻的事实，别读成"已实现" ---
# ★ 教训（本轮首跑又踩一次）：`ast.walk` 是 **BFS** ⇒ 找"`is_surprised` 那个 If"时
#   它会先命中函数**顶层**的清除块（`if self.is_surprised: ... is_surprised = False`），
#   而不是嵌在 `is_moving` 里的**写参**块 ⇒ 必须①在 `_moving_if` **子树内**找，
#   ②用 `'surprised_down' in unparse(node)` 认准是"写参块"。
_UA_FN = _func('update_animation')
_moving_if = None
for _nd in ast.walk(_UA_FN):
    if (isinstance(_nd, ast.If)
            and ast.unparse(_nd.test).strip() == 'self.is_moving'):
        _moving_if = _nd
        break
_surprise_if = None
if _moving_if is not None:
    for _nd in ast.walk(_moving_if):
        if (isinstance(_nd, ast.If)
                and ast.unparse(_nd.test).startswith('self.is_surprised')
                and 'surprised_down' in ast.unparse(_nd)):
            _surprise_if = _nd
            break
_surprise_body = (' | '.join(ast.unparse(s) for s in _surprise_if.body)
                  if _surprise_if is not None else '')
check('A8 ★★登记（绊线）：惊讶的"跳一下"块**仍嵌在 `elif self.is_moving:` 的子树里** '
      '⇒ 站着/睡着的宠物被吓到**只会变脸、不会跳**。'
      '★ 本条是**绊线**：谁把它外提（或真正实现跳），这条会报红 ⇒ 必须重评 B 段与遗留池。',
      _surprise_if is not None, 'found_in_is_moving=%s' % (_surprise_if is not None))
check('A9 ★★登记（绊线）：该跳块**从不置 `is_jumping`** ⇒ 即便可达也只是记账'
      '（`jump_count += 1`），`handle_jump` 的抛物线物理不会跑'
      '（`jump_height` 第96b轮已证为死变量）。'
      '★ 绊线同上。',
      bool(_surprise_body) and 'is_jumping' not in _surprise_body,
      'body_has_is_jumping=%s' % ('is_jumping' in _surprise_body))


# ============================================================ B. 行为级：惊讶三部曲
mark('B 行为级：真起 RalseiPet()，驱动惊讶（落画面 / 还原点 / 再跳）')

try:
    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    _qapp_ok = True
except Exception as e:
    _qapp_ok = False
    _qapp_err = repr(e)

check('B0a QApplication 就绪', _qapp_ok, '' if _qapp_ok else _qapp_err)

pet = None
if _qapp_ok:
    try:
        import main as M
        # ★★★ 第99轮（基线封闭性）：**先关掉 NPC 自主移动，再构造宠物**。
        #   起因（实测，本套件首跑就 DIFF）：构造期会打印
        #     `NPC 生活档案：<path>（规划 34 人 / 驻留 N 人）`
        #   而 `N` 是 `len(npc_roam.RoamState)`（从 `npc_life.json` 读回）——
        #   **同一进程内 3 次构造分别读到 0 / 32 / 34**：第 1 只建完就开始自主节拍、
        #   写盘；第 2/3 只读到刚写下的表。而 `npc_intent.decide()` 的随机种子是
        #     `seed_for(id, salt) ^ int(jitter(id, now, salt, 0, 1 << 30))`，`now` =
        #   **真实绝对秒** ⇒ 任何两次运行的"这一拍谁挪到了哪"都不同（产品**设计意图**，
        #   不是缺陷；`run_all.py` 的 `_NPC_ROAM_NOISE` 注释里有第95轮的决定性实验：
        #   加隔离盘仍 32/33/34 ⇒ 漂移源是**时钟**）。
        #   ⇒ 本轮测的是"惊讶/睡眠状态机"，**与 NPC 自主生活无关**：
        #     关掉它 ⇒ 驻留表恒空、日志恒 `驻留 0 人`，基线才封闭（否则 `--update`
        #     也稳不住，就是第98轮 `check89` 那个"恒假红"的同一形态）。
        #   ★ 这是**夹具隔离**，不是"为了让判据变绿而改被测物"：`NPC_AUTONOMOUS_MOVE`
        #     的默认值（True）由 `check79 W2` 守，本套件的 A8/A9 与 B/C 段全不涉及它。
        M.RalseiPet.NPC_AUTONOMOUS_MOVE = False
        pet = M.RalseiPet()
        check('B0b `RalseiPet()` 真构造成功', True)
    except Exception:
        check('B0b `RalseiPet()` 真构造成功', False, traceback.format_exc()[:400])

if pet is not None:
    pet.BEDTIME_ENABLED = False          # 隔离：不让人物真的去就寝
    pet.current_direction = 'down'
    pet.change_animation('idle', force=True)
    pet.is_surprised = False
    # ★ 显式把基线设成"与惊讶写死值不同"，这样"没改"与"改了"可区分（A/B 先断言 A≠B）。
    pet.jump_duration = 1.25
    pet.jump_height = 55.0
    _jd_before = pet.jump_duration
    _jh_before = pet.jump_height
    check('B0c 夹具基线可与惊讶写死值区分（`jump_duration` ≠ 0.5 / `jump_height` ≠ 20）',
          abs(_jd_before - 0.5) > 1e-9 and abs(_jh_before - 20.0) > 1e-9,
          'jd=%s jh=%s' % (_jd_before, _jh_before))

    pet.trigger_surprise()
    check('B1 惊讶**立刻**落到画面（无一次性动画在播 ⇒ 直接 `force=True` 切，'
          '不等下一 tick、绕开 1.6s 跨组冷却）',
          pet.is_surprised is True and pet.current_animation == 'surprised_down',
          'anim=%r surprised=%s' % (pet.current_animation, pet.is_surprised))

    # 驱动一个 tick（把 `_last_animation_time` 回退 0.2s ⇒ 过帧门控但不触发 2s 清除）
    # ★ 该跳块只在 `is_moving` 时可达（见 A8 登记）⇒ 显式置 True 才驱动得到它。
    pet.is_moving = True
    pet._last_animation_time = time.time() - 0.2
    pet.update_animation()
    check('B2 惊讶分支落地了"跳一下"的写参且**存下了还原点**'
          '（★ 需 `is_moving=True` 才进得去 —— 见 A8 登记）',
          abs(pet.jump_duration - 0.5) < 1e-9
          and hasattr(pet, '_surprised_saved_jump')
          and pet._surprised_saved_jump[1] == _jd_before,
          'jd=%s saved=%s' % (pet.jump_duration,
                              getattr(pet, '_surprised_saved_jump', None)))

    # 模拟"过了 2.1 秒" ⇒ 惊讶清除 ⇒ 必须还原
    pet._last_animation_time = time.time() - 2.1
    pet.update_animation()
    _restored = (pet.is_surprised is False
                 and abs(pet.jump_duration - _jd_before) < 1e-9
                 and abs(pet.jump_height - _jh_before) < 1e-9
                 and not hasattr(pet, 'surprised_jump')
                 and not hasattr(pet, '_surprised_saved_jump'))
    check('B3 ★★ 惊讶结束 ⇒ **还原**跳跃参数 + **删掉**一次性标志'
          '（否则一次惊讶永久污染之后所有跳跃）',
          _restored,
          'jd=%s jh=%s flag=%s saved=%s'
          % (pet.jump_duration, pet.jump_height,
             hasattr(pet, 'surprised_jump'),
             hasattr(pet, '_surprised_saved_jump')))

    _jc = pet.jump_count
    pet.trigger_surprise()
    pet._last_animation_time = time.time() - 0.2
    pet.update_animation()
    check('B4 ★ 第二次惊讶**仍会跳**（原实现 `surprised_jump` 永不删除 ⇒ 只跳一次）',
          pet.jump_count > _jc, 'jump_count %d -> %d' % (_jc, pet.jump_count))

    # 负控制：抠掉还原点 ⇒ 参数停在 0.5（证明 B3 不是"恰好就没改"）
    pet._last_animation_time = time.time() - 2.1
    pet.update_animation()                       # 先正常清一次
    pet.trigger_surprise()
    pet._last_animation_time = time.time() - 0.2
    pet.update_animation()
    _stuck = pet.jump_duration
    if hasattr(pet, '_surprised_saved_jump'):
        del pet._surprised_saved_jump            # ★ 模拟未修版本
    pet._last_animation_time = time.time() - 2.1
    pet.update_animation()
    check('B5 ★负控制：把还原点抠掉后惊讶结束 ⇒ `jump_duration` **停在 0.5**'
          '（证明 B3 的"还原"不是恒真）',
          abs(_stuck - 0.5) < 1e-9 and abs(pet.jump_duration - 0.5) < 1e-9,
          'stuck=%s after=%s' % (_stuck, pet.jump_duration))
    pet.is_moving = False


# ============================================================ C. 行为级：睡眠两拍 ⇒ 惊醒
mark('C 行为级：睡着 → 被点两下 → **惊醒**')

if pet is not None:
    pet._restore_surprised_jump()
    pet.is_surprised = False
    pet.is_sleeping = False
    pet.enter_sleep_mode()
    check('C1 `enter_sleep_mode()` ⇒ 睡着（且播的是 `sleep` 不是 `idle`）',
          pet.is_sleeping is True and pet.current_animation == 'sleep',
          'sleeping=%s anim=%r' % (pet.is_sleeping, pet.current_animation))

    # ★★★ 真机节奏：产品用定时器每 ~50~100ms 调一次 `update_movement`。
    #   首版每个动作只调**一次** ⇒ "第二拍必须等下一次互动"这条恰好看不出来
    #   （**夹具不保真 = 假绿**，本轮真机录像实证）⇒ 本段一律按"连续多 tick"驱动。
    def _ticks(n=12):
        for _ in range(n):
            pet.update_movement()

    # ---- 第一拍：被碰一下 ⇒ 只迷糊，不醒（★ 连续多 tick 也不许醒）----
    pet.last_interaction_time = time.time()
    _ticks(12)
    check('C2 ★★ 第一拍（被碰一下）：连续 12 个 tick 之后仍然**只迷糊不醒**'
          '（`_sleep_stir_count == 1` 且 `is_sleeping` 仍 True 且 `is_surprised` False）',
          getattr(pet, '_sleep_stir_count', None) == 1
          and pet.is_sleeping is True and pet.is_surprised is False,
          'count=%s sleeping=%s spr=%s anim=%r'
          % (getattr(pet, '_sleep_stir_count', None), pet.is_sleeping,
             pet.is_surprised, pet.current_animation))

    # ---- C2b ★负控制：**同一次**互动再连驱一段 tick（不产生新互动）⇒ 依旧不醒 ----
    #   这正是第99轮真机录像抓到的缺陷形态：旧实现在第一拍之后的**下一个 tick**
    #   就走第二拍（"两拍"塌成"一拍"）。这条判据专门守它不许回退。
    _ticks(24)
    check('C2b ★负控制：**不产生新互动**、再连驱 24 个 tick ⇒ 仍然不醒不受惊'
          '（旧实现在这里必然变红：`probe99i.py` tick#2 即 `sleeping=False spr=True`）',
          pet.is_sleeping is True and pet.is_surprised is False
          and getattr(pet, '_sleep_stir_count', None) == 1,
          'sleeping=%s spr=%s stir=%s'
          % (pet.is_sleeping, pet.is_surprised,
             getattr(pet, '_sleep_stir_count', None)))

    # ---- 第二拍：**一次新的互动** ⇒ **惊醒** ----
    pet.last_interaction_time = time.time()
    _ticks(12)
    check('C3a ★★★ 第二拍（新互动）⇒ **醒了**（`is_sleeping=False`）**且受惊**'
          '（`is_surprised=True`）',
          pet.is_sleeping is False and pet.is_surprised is True,
          'sleeping=%s surprised=%s anim=%r'
          % (pet.is_sleeping, pet.is_surprised, pet.current_animation))

    # ★ C3b：惊吓脸**真会播到**。第二拍时第一拍的 `look_up`（4 帧）还在播，
    #   且第8轮契约不许打断 ⇒ 惊吓脸是"排到它播完之后"落地的。
    #   这里驱动**真实产品代码**（`update_animation` 的一次性动画完成分支）把它走完。
    _advanced = False
    for _i in range(400):
        pet._last_animation_time = time.time() - 0.2
        pet.update_animation()
        if not getattr(pet, '_play_once_active', False):
            _advanced = True
            break
    check('C3b ★★★ 惊吓脸**真会播到**：第一拍的 `look_up` 播完后 ⇒ 画面 = `surprised_down`'
          '（第8轮"播完为止"契约没被拆，靠 `next_animation` 排队落地）',
          _advanced and pet.current_animation == 'surprised_down',
          'advanced=%s anim=%r frames=%d'
          % (_advanced, pet.current_animation, _i + 1))

    # ---- 负控制 1：只走第一拍，不发第二拍 ⇒ 不该有任何"惊" ----
    pet2 = None
    try:
        pet2 = M.RalseiPet()
        pet2.BEDTIME_ENABLED = False
        pet2.enter_sleep_mode()
        pet2.last_interaction_time = time.time()
        for _k in range(12):                 # ★ 真机节奏：连续多 tick，不是一次
            pet2.update_movement()
        check('C4 ★负控制：只碰一下（不发第二拍）⇒ `is_surprised` 仍为 False'
              '（证明 C3a 的"惊"来自接线，不是默认值）',
              pet2.is_sleeping is True and pet2.is_surprised is False,
              'sleeping=%s surprised=%s' % (pet2.is_sleeping, pet2.is_surprised))
    except Exception:
        check('C4 ★负控制：只碰一下（不发第二拍）⇒ `is_surprised` 仍为 False', False,
              traceback.format_exc()[:300])

    # ---- 负控制 2：把"排队落地"的回归目标拿掉 ⇒ 惊吓脸**不会**出现 ----
    pet3 = None
    try:
        pet3 = M.RalseiPet()
        pet3.BEDTIME_ENABLED = False
        pet3.enter_sleep_mode()
        pet3.last_interaction_time = time.time()
        for _k in range(12):
            pet3.update_movement()
        pet3.last_interaction_time = time.time()
        for _k in range(12):
            pet3.update_movement()
        pet3.next_animation = None            # ★ 模拟"A1b 那条排队没写"
        for _j in range(400):
            pet3._last_animation_time = time.time() - 0.2
            pet3.update_animation()
            if not getattr(pet3, '_play_once_active', False):
                break
        check('C5 ★负控制：把"排队落地"的回归目标拿掉后⇒ 一次性动画播完回到 '
              '`idle`（**不是** `surprised_down`）⇒ 证明 C3b 不是恒真',
              pet3.is_surprised is True and pet3.current_animation != 'surprised_down',
              'surprised=%s anim=%r' % (pet3.is_surprised, pet3.current_animation))
    except Exception:
        check('C5 ★负控制：把"排队落地"的回归目标拿掉后 ⇒ 画面不是 `surprised_down`',
              False, traceback.format_exc()[:300])


# ============================================================ D. 判据自身体检
mark('D 判据自身体检')

check('D1 被测文件在盘（main.py）', os.path.isfile(MAIN))
check('D2 判据点全部执行到位（标记打印点 == 4）', _marks == 4, 'marks=%d' % _marks)

_probe_calls = _n_calls
_probe_marks = _marks


def _noop_probe():
    mark('D3 空判据探针')
    return None


_noop_probe()
check('D3 记账口不是 no-op（打标记点但没走 check ⇒ 独立计数器不涨）',
      _n_calls == _probe_calls and _marks == _probe_marks + 1,
      'calls=%d(+0) marks=%d(+1)' % (_n_calls, _marks))
check('D4 记账守恒（独立计数器 CALLS == PASS + FAIL）',
      _n_calls == _n_pass + _n_fail,
      'calls=%d pass=%d fail=%d' % (_n_calls, _n_pass, _n_fail))
check('D5 守恒判据有鉴别力（漏记那一步计进总数 ⇒ 等式不再成立）',
      (_n_calls + 1) != (_n_pass + _n_fail),
      'calls+1=%d vs pass+fail=%d' % (_n_calls + 1, _n_pass + _n_fail))

print('=' * 70)
print('第99轮（睡觉后惊醒）：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print('失败项：')
    for _d in _failed:
        print('  - %s' % _d)
print('=' * 70)
sys.exit(0 if not _failed else 1)

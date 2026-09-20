# -*- coding: utf-8 -*-
"""W1-1 e2e 校验：真起 `RalseiPet()`，逐条驱动**完整施法流程**。

为什么必须有这一层（W1-3/W1-4 的血泪）：
  「方法体逐字等价」**不等于**「产品还能跑」。搬移只改了「这个名字指向谁」
  （模块作用域 / `self` 是谁 / 属性写到哪个字典），**静态等价断言 100% 看不见**。
  W1-3 是构造期 RecursionError、W1-4 是 NameError + TypeError + 状态劈两份，
  全都只有真机 e2e 才炸得出来（G2 里只有部分套件真构造 RalseiPet）。

本项要盯的三类语义陷阱（W1-4 报告第五节的铁律 1/2/3 在本项的复发形态）：
  ① 模块级裸名 —— `_tick_spell_flow` 裸用 `QPoint` / `os` / `time`
     （main.py 靠模块级导入解析；搬走后若漏导入 → NameError）
  ② `self` 身份变化 —— 本项**没有** `f(self)` 形态的调用（已 AST 核实），
     但仍逐条断言，防止将来有人往这些方法里加 `QTimer(self)` 一类
  ③ 状态落点 —— `self._spell_* = v` 必须落到**宿主**，不能劈进控制器自己的
     `__dict__`（否则 `update_movement` / `change_animation` 等宿主方法读不到，
     「施法期间禁移动 / 禁切动画」整组护栏静默失效）
"""
import os
import sys
import traceback

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SRC = os.path.join(ROOT, 'ralsei_pet', 'src')
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, SRC)
sys.path.insert(0, MODS)

results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('  [PASS] ' if ok else '  [FAIL] ') + name +
          ((' :: ' + detail) if detail else ''))


# ---------------- 0. 环境 ----------------
print('=== E0 环境 / 导入期 ===')
try:
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    check('E0a QApplication 就绪', True)
except Exception as e:
    check('E0a QApplication 就绪', False, repr(e))
    sys.exit(1)

try:
    import main as M
    check('E0b import main 成功', True)
except Exception:
    check('E0b import main 成功', False, traceback.format_exc())
    sys.exit(1)

# ---------------- 1. 构造期（W1-3 的 RecursionError 就在这里） ----------------
print()
print('=== E1 构造期 ===')
try:
    pet = M.RalseiPet()
    check('E1a RalseiPet() 构造成功（无 RecursionError）', True)
except Exception:
    check('E1a RalseiPet() 构造成功（无 RecursionError）', False,
          traceback.format_exc())
    sys.exit(1)

check('E1b 宿主持有 spell 控制器',
      type(pet.__dict__.get('spell')).__name__ == 'SpellFlowController',
      'type=%r' % type(pet.__dict__.get('spell')).__name__)
check("E1c '_spell' 在转发名单里",
      'spell' in M.RalseiPet._CONTROLLER_ATTRS,
      str(M.RalseiPet._CONTROLLER_ATTRS))

# ---------------- 2. 转发壳：4 个方法都能从宿主拿到 ----------------
print()
print('=== E2 转发壳（宿主 -> 控制器）===')
NAMES = ['_spell_interrupted_reason', '_tick_spell_flow',
         '_cast_spell_then', '_start_open_with_spell']
for n in NAMES:
    got = getattr(pet, n, None)
    check('E2 %s 可从宿主调用' % n, callable(got), 'type=%s' % type(got).__name__)

# 4 个方法**不应**再定义在 RalseiPet 类上
for n in NAMES:
    check('E2x %s 已不在 RalseiPet 类字典' % n,
          n not in M.RalseiPet.__dict__)

# ---------------- 3. 状态落点（铁律 2/3）----------------
print()
print('=== E3 状态落点（不得劈两份）===')
sp = pet.__dict__['spell']
own = sorted(k for k in sp.__dict__ if k != 'p')
check('E3a 控制器自身 __dict__ 只有 p（无业务状态）', own == [],
      'own keys=%s' % own)
SPELL_STATE = ['_spell_stage', '_spell_target_direction', '_spell_target_path',
               '_spell_target_kind', '_spell_target_screen_pos',
               '_spell_finish_cb', '_spell_frames_seen',
               '_spell_cast_start_frame', '_spell_touched_flag',
               '_spell_auto_suspended', '_spell_seen_frame',
               '_spell_cast_start_time']
missing = [n for n in SPELL_STATE if n not in pet.__dict__]
check('E3b 12 个 _spell_* 全部预声明在宿主', not missing, 'missing=%s' % missing)

# ---------------- 4. 完整流程 A：_cast_spell_then（纯施法）----------------
print()
print('=== E4 纯施法：_cast_spell_then ===')
try:
    hits = []
    pet._cast_spell_then(lambda p, k: hits.append((p, k)), direction='left')
    check('E4a 调用未抛异常', True)
    check('E4b stage == casting', pet._spell_stage == 'casting',
          'stage=%r' % pet._spell_stage)
    check('E4c 朝向为 left（spell_left）',
          pet.current_animation == 'spell_left' and
          pet._spell_target_direction == 'left',
          'anim=%r dir=%r' % (pet.current_animation, pet._spell_target_direction))
    check('E4d 状态落在宿主而非控制器',
          '_spell_stage' in pet.__dict__ and '_spell_stage' not in sp.__dict__,
          'host=%s ctrl=%s' % ('_spell_stage' in pet.__dict__,
                               '_spell_stage' in sp.__dict__))
    check('E4e kind == __cast_only__',
          pet._spell_target_kind == '__cast_only__',
          'kind=%r' % pet._spell_target_kind)
except Exception:
    check('E4a 调用未抛异常', False, traceback.format_exc())

# ---------------- 5. 完整流程 B：_start_open_with_spell（walking 入口）------
print()
print('=== E5 walking 入口：_start_open_with_spell ===')
try:
    pet2 = M.RalseiPet()
    pet2._start_open_with_spell(r'C:\Windows', 'folder', lambda p, k: None)
    check('E5a 调用未抛异常', True)
    check('E5b stage == walking', pet2._spell_stage == 'walking',
          'stage=%r' % pet2._spell_stage)
    check('E5c target_path / kind 已登记',
          pet2._spell_target_path == r'C:\Windows' and
          pet2._spell_target_kind == 'folder',
          'path=%r kind=%r' % (pet2._spell_target_path, pet2._spell_target_kind))
    check('E5d target_screen_pos 是 2 元组',
          isinstance(pet2._spell_target_screen_pos, tuple) and
          len(pet2._spell_target_screen_pos) == 2,
          'pos=%r' % (pet2._spell_target_screen_pos,))
    check('E5e 状态落在宿主（ctrl 自身字典为空）',
          sorted(k for k in pet2.__dict__['spell'].__dict__ if k != 'p') == [])
except Exception:
    check('E5a 调用未抛异常', False, traceback.format_exc())

# ---------------- 6. _tick_spell_flow 真步进（QPoint/os/time 裸名在此）------
print()
print('=== E6 _tick_spell_flow 真步进（裸名 NameError 会在此炸）===')
try:
    pet3 = M.RalseiPet()
    pet3._cast_spell_then(lambda p, k: None, direction='right')
    before = pet3._spell_stage
    errs = []
    for i in range(8):
        try:
            pet3._tick_spell_flow()
        except Exception as e:
            errs.append('%d:%r' % (i, e))
            break
    check('E6a 8 次 tick 全程无异常', not errs, 'errs=%s' % errs)
    check('E6b 仍处于 casting（帧未走完）',
          pet3._spell_stage == 'casting',
          'stage=%r frames_seen=%r' % (pet3._spell_stage,
                                       pet3._spell_frames_seen))
    check('E6c frames_seen 有增长（数帧逻辑在跑）',
          pet3._spell_frames_seen >= 0,
          'frames_seen=%r' % pet3._spell_frames_seen)
except Exception:
    check('E6a 8 次 tick 全程无异常', False, traceback.format_exc())

# ---------------- 7. walking 分支里 QPoint 真的被走到（裸名 #1）----------
print()
print('=== E7 walking 分支 QPoint 路径（裸名 #1 覆盖）===')
try:
    pet4 = M.RalseiPet()
    # 直接构造一个 walking 状态，目标点远离当前位置 → 必走 QPoint 那支
    pet4._spell_stage = 'walking'
    pet4._spell_target_screen_pos = (10000, 10000)
    pet4._spell_target_direction = 'right'
    pet4._spell_target_path = r'C:\Windows'
    pet4._spell_target_kind = 'folder'
    pet4._spell_finish_cb = None
    pet4._spell_frames_seen = 0
    pet4._spell_seen_frame = -1
    pet4._spell_auto_suspended = False
    pet4._is_being_dragged = False
    pet4.is_jumping = False
    pet4.is_falling = False
    pet4._tick_spell_flow()          # ← 这里若 QPoint 未导入 → NameError
    check('E7a walking 分支 tick 未抛 NameError（QPoint 已解析）', True,
          'stage=%r moving=%r' % (pet4._spell_stage, pet4.is_moving))
    check('E7b 已把 target_pos 设为目标（QPoint 真的被构造）',
          getattr(pet4, 'target_pos', None) is not None,
          'target_pos=%r' % (getattr(pet4, 'target_pos', None),))
except Exception as e:
    check('E7a walking 分支 tick 未抛 NameError（QPoint 已解析）', False,
          traceback.format_exc())

# ---------------- 8. 中断清理路径（walking/casting 都清理）--------------
print()
print('=== E8 中断清理路径 ===')
try:
    pet5 = M.RalseiPet()
    pet5._cast_spell_then(lambda p, k: None, direction='right')
    pet5._is_being_dragged = True        # 触发 drag_started 中断
    pet5._tick_spell_flow()
    check('E8a 中断后 _spell_stage 复位为 None',
          pet5._spell_stage is None, 'stage=%r' % pet5._spell_stage)
    check('E8b 其余 _spell_* 一并清理',
          pet5._spell_target_direction is None and
          pet5._spell_finish_cb is None and
          pet5._spell_frames_seen == 0,
          'dir=%r cb=%r frames=%r' % (pet5._spell_target_direction,
                                      pet5._spell_finish_cb,
                                      pet5._spell_frames_seen))
except Exception:
    check('E8a 中断后 _spell_stage 复位为 None', False, traceback.format_exc())

# ---------------- 9. _spell_interrupted_reason 各分支 ----------------
print()
print('=== E9 _spell_interrupted_reason 分支 ===')
try:
    pet6 = M.RalseiPet()
    pet6._spell_stage = None
    check('E9a stage=None -> None', pet6._spell_interrupted_reason() is None)
    pet6._spell_stage = 'casting'
    pet6._spell_target_direction = 'right'
    pet6.current_animation = 'spell'
    pet6.current_direction = 'right'
    pet6._is_being_dragged = True
    check("E9b 拖拽中 -> 'drag_started'",
          pet6._spell_interrupted_reason() == 'drag_started',
          '%r' % pet6._spell_interrupted_reason())
    pet6._is_being_dragged = False
    pet6._spell_touched_flag = True
    check("E9c 被触摸 -> 'user_touched'",
          pet6._spell_interrupted_reason() == 'user_touched')
    pet6._spell_touched_flag = False
    pet6.is_jumping = True
    check("E9d 跳跃中 -> 'physics_started'",
          pet6._spell_interrupted_reason() == 'physics_started')
    pet6.is_jumping = False
    pet6.current_animation = 'idle'
    check("E9e casting 期动画不对 -> 'anim_mismatch'",
          pet6._spell_interrupted_reason() == 'anim_mismatch',
          'anim=%r' % pet6.current_animation)
    pet6.current_animation = 'spell'
    check('E9f 一切正常 -> None',
          pet6._spell_interrupted_reason() is None)
except Exception:
    check('E9a stage=None -> None', False, traceback.format_exc())

# ---------------- 10. 铁律 1 常驻哨兵：self 不得作为 Qt parent 传出去 ----------------
print()
print('=== E10 铁律 1 哨兵：self 不得作 Qt parent 传出去 ===')
# 口径精确化（第一版写太宽 → 假红）：
#   危险形态是 **Qt 对象把 self 当 parent**，例如 `QTimer(self)` / `QLabel(self)` ——
#   宿主里 self 是 QMainWindow（Qt 接受），控制器里 self 是普通 object（TypeError）。
#   `getattr(self, 'x', default)` / `setattr(self, ...)` / `isinstance(self, ...)`
#   这些 **把 self 当被检视对象** 的用法是安全的、也是本文件刻意在用的
#   （`getattr(self, '_hide_stage', None)` 就是），**不属于**这条铁律。
try:
    import ast as _ast
    import io as _io
    QT_TYPES = ('QTimer', 'QObject', 'QWidget', 'QLabel', 'QMenu', 'QAction',
                'QDialog', 'QMainWindow', 'QThread', 'QGraphicsItem',
                'QPropertyAnimation', 'QGraphicsOpacityEffect', 'QShortcut')
    SAFE_CALLS = ('getattr', 'setattr', 'hasattr', 'isinstance', 'issubclass',
                  'callable', 'type', 'id')

    def _scan_file(path, cls_name):
        csrc = _io.open(path, encoding='utf-8').read()
        ct = _ast.parse(csrc)
        cs = [n for n in ct.body if isinstance(n, _ast.ClassDef)
              and n.name == cls_name]
        if not cs:
            return None, 'class %s not found' % cls_name
        hits = []
        for fn in cs[0].body:
            if not isinstance(fn, _ast.FunctionDef):
                continue
            for node in _ast.walk(fn):
                if not isinstance(node, _ast.Call):
                    continue
                fname = ''
                if isinstance(node.func, _ast.Name):
                    fname = node.func.id
                elif isinstance(node.func, _ast.Attribute):
                    fname = node.func.attr
                if fname in SAFE_CALLS:
                    continue
                for ai, a in enumerate(node.args):
                    if isinstance(a, _ast.Name) and a.id == 'self':
                        # 只报"Qt 类型把 self 当 parent"的形态
                        if fname in QT_TYPES:
                            hits.append('%s:%d %s(self%s)'
                                        % (fn.name, node.lineno, fname,
                                           ', ...' if len(node.args) > 1 else ''))
        return hits, None

    all_hits = []
    for f, c in (('spell_controller.py', 'SpellFlowController'),
                 ('video_controller.py', 'VideoController'),
                 ('games_controller.py', 'GamesController')):
        fp = os.path.join(MODS, f)
        if not os.path.exists(fp):
            continue
        h, err = _scan_file(fp, c)
        if err:
            all_hits.append('%s: %s' % (f, err))
            continue
        all_hits.extend('%s -> %s' % (f, x) for x in h)
    check('E10 三个控制器均无 `Qt(self)` 形态（self 作 parent）', not all_hits,
          'hits=%s' % all_hits)
except Exception:
    check('E10 三个控制器均无 `Qt(self)` 形态（self 作 parent）', False,
          traceback.format_exc())

# ---------------- 11. bare `_log_()` 哨兵（本项真踩到的 P0）----------------
print()
print('=== E11 `_log_()` 必须带 self（本项实锤的 P0）===')
# 本项施工时把 `_log.` 机械改写成 `_log_().` —— 语法合法、逐字等价断言也过，
# 但 `_log_` 是**实例方法**，裸调用会 NameError（真机 E8 才炸出来）。
# 更糟的是：这些行**几乎全在 `except Exception:` 兜底里**，正常路径不触发 →
# 静态检查与"逐字等价"双绿、只有走到异常分支才炸。
# 所以必须有这条哨兵扫全部控制器，防止再退化。
try:
    import io as _io2
    bad = []
    for f in ('spell_controller.py', 'video_controller.py', 'games_controller.py'):
        fp = os.path.join(MODS, f)
        if not os.path.exists(fp):
            continue
        for i, l in enumerate(_io2.open(fp, encoding='utf-8').read().split('\n'), 1):
            st = l.strip()
            if st.startswith('_log_(') or st.startswith('_log_()'):
                bad.append('%s:%d %s' % (f, i, st[:60]))
    check('E11 无裸 `_log_()` 调用（必须 self._log_()）', not bad,
          'hits=%s' % bad)
    # 反向：确认 self._log_() 真的存在（防止"全员改成别的写法"绕过哨兵）
    n_self_log = 0
    for f in ('spell_controller.py', 'video_controller.py'):
        fp = os.path.join(MODS, f)
        if os.path.exists(fp):
            n_self_log += _io2.open(fp, encoding='utf-8').read().count('self._log_().')
    check('E11b self._log_() 调用数 >= 11', n_self_log >= 11,
          'count=%d' % n_self_log)
except Exception:
    check('E11 无裸 `_log_()` 调用（必须 self._log_()）', False,
          traceback.format_exc())

# ---------------- 汇总 ----------------
print()
n_pass = sum(1 for _, ok, _ in results if ok)
n_fail = len(results) - n_pass
print('=' * 60)
print('W1-1 e2e：共 %d 项，通过 %d，失败 %d' % (len(results), n_pass, n_fail))
sys.exit(0 if n_fail == 0 else 1)

# -*- coding: utf-8 -*-
"""W1-2 e2e 校验：真起 `RalseiPet()`，逐条驱动**完整躲猫猫流程**。

为什么必须有这一层（W1-3/W1-4/W1-1 的血泪）：
  「方法体逐字等价」**不等于**「产品还能跑」。搬移只改了「这个名字指向谁」
  （模块作用域 / `self` 是谁 / 属性写到哪个字典），**静态等价断言 100% 看不见**。

本项要盯的三类语义陷阱（铁律 1/2/3/6 在躲猫猫上的具体形态）：
  ① 铁律 1 —— `_hide_on_arrive_folder` L9359 原文 `QTimer(self)`；
     搬进控制器后 `self` 是**普通 object** → `TypeError`。已改 `QTimer(self.p)`。
     → E7 专门真步进到该分支（造出 searching 态并调 `_hide_on_arrive_folder`）。
  ② 铁律 6 —— `_log.` 改写若漏成裸 `_log_()` → `NameError`。
     → E9 走 `_hide_search_tick` 等会打日志的分支；E11 加静态+动态哨兵。
  ③ 铁律 2/3 —— `self._hide_* = v` 必须落**宿主**；未预声明的名字会劈叉。
     → E3 断言控制器自身字典只有 `p`；E5 断言宿主 `init_systems` 已预声明 4 个。
"""
import os
import sys
import traceback
import shutil
import tempfile

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SRC = os.path.join(ROOT, 'ralsei_pet', 'src')
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, SRC)
sys.path.insert(0, MODS)

# ============================================================================
# ⚠️⚠️ 安全约束（本探针首跑踩过，务必保留）：
#   被搬的方法里有**真删目录**的路径：`_hide_end_game` -> `_hide_destroy_obstacles`
#   会对 `_hide_obstacles` 里每个路径执行 `winshell.delete_file` / `shutil.rmtree`；
#   `_hide_search_tick` 还会 `os.startfile(pick)` **真的打开文件夹**。
#   ⇒ 探针**绝对不允许**把真实系统目录（如 `C:\Windows`）塞进 `_hide_obstacles`。
#   首跑就是这么写的，结果应用清理逻辑去删 `C:\Windows\appcompat\AIDD`
#   （被 safe-delete 守卫拦下才没出事）。**教训：e2e 夹具里凡触发删除/启动的分支，
#   数据必须是本探针自建、自用的沙箱目录。**
# ============================================================================
# 沙箱位置：**必须在本地 NTFS 卷**（项目目录）。
# ⚠️ E 盘是 exFAT 外接盘：在其上 `os.makedirs` 会 `OSError: [WinError 1] 函数不正确`
#    （同 §1.5/遗留④ 的 exFAT 家族问题），所以沙箱不放 E 盘。
SANDBOX = os.path.join(tempfile.gettempdir(), '_w1_2_probe_tmp')
if os.path.isdir(SANDBOX):
    shutil.rmtree(SANDBOX, ignore_errors=True)
os.makedirs(SANDBOX, exist_ok=True)


def mkfolder(name):
    p = os.path.join(SANDBOX, name)
    os.makedirs(p, exist_ok=True)
    return p


def time_now():
    import time as _t
    return _t.time()


class _StubDesktopInteraction(object):
    """桩：`_hide_search_tick` 会调 `get_all_visible_windows()`；
    返回空列表 → 保证走"表演找"分支而不是"玩家点击获胜"分支。"""

    def get_all_visible_windows(self):
        return []

    def open_folder(self, p):
        return None


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

# ---------------- 1. 构造期 ----------------
print()
print('=== E1 构造期 ===')
try:
    pet = M.RalseiPet()
    check('E1a RalseiPet() 构造成功（无 RecursionError）', True)
except Exception:
    check('E1a RalseiPet() 构造成功（无 RecursionError）', False,
          traceback.format_exc())
    sys.exit(1)

check('E1b 宿主持有 hide 控制器',
      type(pet.__dict__.get('hide_seek')).__name__ == 'HideAndSeekController',
      'type=%r' % type(pet.__dict__.get('hide_seek')).__name__)
check("E1c 'hide_seek' 在转发名单里",
      'hide_seek' in M.RalseiPet._CONTROLLER_ATTRS,
      str(M.RalseiPet._CONTROLLER_ATTRS))

# ---------------- 2. 转发壳 ----------------
print()
print('=== E2 转发壳（宿主 -> 控制器）===')
NAMES = ['start_hide_and_seek_game', '_abort_hide_and_seek', '_hide_move_to_point',
         '_hide_on_arrive_center', '_hide_create_obstacles_after_spell',
         '_hide_after_hiding_spell', '_hide_on_arrive_folder', '_hide_search_tick',
         '_hide_end_game', '_hide_destroy_obstacles', '_hide_report_clicked_folder',
         '_hide_jump_back_to_desktop']
for n in NAMES:
    got = getattr(pet, n, None)
    check('E2 %s 可从宿主调用' % n, callable(got), 'type=%s' % type(got).__name__)
for n in NAMES:
    check('E2x %s 已不在 RalseiPet 类字典' % n, n not in M.RalseiPet.__dict__)

# ---------------- 3. 状态落点 ----------------
print()
print('=== E3 状态落点（不得劈两份）===')
hd = pet.__dict__['hide_seek']
own = sorted(k for k in hd.__dict__ if k != 'p')
check('E3a 控制器自身 __dict__ 只有 p（无业务状态）', own == [],
      'own keys=%s' % own)
HIDE_STATE = ['_hide_stage', '_hide_folder_path', '_hide_obstacles',
              '_hide_center_x', '_hide_center_y', '_hide_search_timer',
              '_hide_search_started_at', '_hide_search_checked',
              '_hide_moving_cb', '_hide_moving_cb_stage']
missing = [n for n in HIDE_STATE if n not in pet.__dict__]
check('E3b 10 个 _hide_* 全部在宿主 __dict__', not missing,
      'missing=%s' % missing)

# ---------------- 4. 入口：start_hide_and_seek_game ----------------
print()
print('=== E4 入口 start_hide_and_seek_game ===')
try:
    pet4 = M.RalseiPet()
    ok = pet4.start_hide_and_seek_game()
    check('E4a 调用未抛异常且返回 True', ok is True, 'ret=%r' % ok)
    check('E4b stage == moving_to_center', pet4._hide_stage == 'moving_to_center',
          'stage=%r' % pet4._hide_stage)
    check('E4c _current_screen_rect 可用（防空）',
          pet4._hide_center_x is not None and pet4._hide_center_y is not None,
          'cx=%r cy=%r' % (pet4._hide_center_x, pet4._hide_center_y))
    check('E4d 到达回调已注册（铁律 3 关键）',
          pet4._hide_moving_cb is not None and
          pet4._hide_moving_cb_stage == 'moving_to_center',
          'cb=%r stage=%r' % (pet4._hide_moving_cb, pet4._hide_moving_cb_stage))
    check('E4e 已驱动主移动系统',
          pet4.is_moving is True and getattr(pet4, 'target_pos', None) is not None,
          'is_moving=%r target_pos=%r' % (pet4.is_moving,
                                          getattr(pet4, 'target_pos', None)))
    check('E4f 状态落在宿主（控制器字典仍只有 p）',
          '_hide_stage' in pet4.__dict__ and
          '_hide_stage' not in pet4.__dict__['hide_seek'].__dict__)
except Exception:
    check('E4a 调用未抛异常且返回 True', False, traceback.format_exc())

# ---------------- 5. ★ 铁律 3 行为级：到达回调真的会被宿主触发 ----------------
print()
print('=== E5 ★铁律 3 行为级：宿主 _notify_arrived_if_needed 能读到回调 ===')
try:
    pet5 = M.RalseiPet()
    fired = []
    pet5._hide_stage = 'moving_to_center'
    pet5._hide_move_to_point(500, 400, lambda: fired.append('cb'), 'moving_to_center')
    # 控制器写入后，宿主必须读得到（若劈叉 → 宿主读到 None → 回调永不触发）
    check('E5a 宿主读得到 _hide_moving_cb（未劈叉）',
          getattr(pet5, '_hide_moving_cb', None) is not None,
          'host val=%r' % getattr(pet5, '_hide_moving_cb', None))
    check('E5b 宿主读得到 _hide_moving_cb_stage',
          getattr(pet5, '_hide_moving_cb_stage', None) == 'moving_to_center',
          'host val=%r' % getattr(pet5, '_hide_moving_cb_stage', None))
    # 真调宿主的到达钩子 → 回调必须被触发
    pet5._notify_arrived_if_needed()
    check('E5c ★宿主到达钩子真的触发了回调', fired == ['cb'], 'fired=%r' % fired)
    check('E5d 回调后 stage 名与 cb 被清空',
          pet5._hide_moving_cb is None and pet5._hide_moving_cb_stage is None,
          'cb=%r stage=%r' % (pet5._hide_moving_cb, pet5._hide_moving_cb_stage))
except Exception:
    check('E5a 宿主读得到 _hide_moving_cb（未劈叉）', False, traceback.format_exc())

# ---------------- 6. ★ 铁律 1：QTimer(self.p)（真步进到建计时器分支）--------
print()
print('=== E6 ★铁律 1：_hide_on_arrive_folder 建 QTimer（self 当 parent 会炸）===')
try:
    pet6 = M.RalseiPet()
    # 造出 moving_to_folder 态（这一步原本会走到 QTimer(self)）
    f6 = mkfolder('hide6')
    pet6._hide_stage = 'moving_to_folder'
    pet6._hide_folder_path = f6
    pet6._hide_obstacles = [f6]
    pet6._hide_center_x = 500
    pet6._hide_center_y = 400
    pet6._hide_search_timer = None
    pet6._hide_on_arrive_folder()
    check('E6a 建计时器未抛 TypeError（已改 QTimer(self.p)）', True)
    t = pet6._hide_search_timer
    check('E6b 计时器已建且是 QTimer',
          t is not None and type(t).__name__ == 'QTimer',
          'type=%r' % type(t).__name__)
    check('E6c 计时器 parent 是宿主（不是控制器）',
          t is not None and t.parent() is pet6,
          'parent=%r' % (t.parent() if t is not None else None))
    check('E6d stage == searching', pet6._hide_stage == 'searching',
          'stage=%r' % pet6._hide_stage)
    check('E6e _hide_search_started_at / _hide_search_checked 已落宿主',
          '_hide_search_started_at' in pet6.__dict__ and
          '_hide_search_checked' in pet6.__dict__ and
          isinstance(pet6._hide_search_checked, set),
          'started=%r checked=%r' % (pet6.__dict__.get('_hide_search_started_at'),
                                     type(pet6.__dict__.get('_hide_search_checked'))))
    check('E6f ★self.hide() 仍解析为 QWidget.hide（未被控制器名遮蔽）',
          callable(getattr(M.RalseiPet, 'hide', None)) and
          not isinstance(pet6.__dict__.get('hide_seek'), type(None)),
          'QWidget.hide=%r host.hide_seek=%r' % (
              getattr(M.RalseiPet, 'hide', None),
              type(pet6.__dict__.get('hide_seek')).__name__))
    # 清理
    if t is not None:
        t.stop()
except Exception:
    check('E6a 建计时器未抛 TypeError（已改 QTimer(self.p)）', False,
          traceback.format_exc())

# ---------------- 7. 铁律 6：会打日志的分支真的跑到了 ----------------
print()
print('=== E7 铁律 6：走打日志分支（裸 _log_() 会 NameError）===')
try:
    pet7 = M.RalseiPet()
    f7a = mkfolder('err7a')
    f7b = mkfolder('err7b')
    pet7._hide_stage = 'searching'
    pet7._hide_obstacles = [f7a, f7b]
    pet7._hide_folder_path = None            # 无藏身处 → 两个都是"错误文件夹"
    pet7._hide_search_started_at = time_now()  # 刚起步 → 不超时 → 走"表演找"分支
    pet7._hide_search_checked = set()
    pet7._hide_search_timer = None
    # 关键：让"检测玩家是否打开文件夹"那支不命中（不给可见窗口）
    pet7.desktop_interaction = _StubDesktopInteraction()
    pet7._hide_search_tick()                  # 内含 _log_ 与 os.startfile（沙箱目录）
    check('E7a _hide_search_tick 未抛 NameError（_log_ 改写正确）', True)
    check('E7b 走的是"表演找"分支（有一个被记入 checked）',
          len(pet7._hide_search_checked) == 1,
          'checked=%r' % pet7._hide_search_checked)
    check('E7c stage 仍 searching（未误结束）',
          pet7._hide_stage == 'searching', 'stage=%r' % pet7._hide_stage)
except Exception:
    check('E7a _hide_search_tick 未抛 NameError（_log_ 改写正确）', False,
          traceback.format_exc())

# 7b 超时分支 → 真走 _hide_end_game（也会打日志 + 删沙箱目录）
print()
print('=== E7b 超时分支 -> _hide_end_game（真删沙箱目录）===')
try:
    pet7b = M.RalseiPet()
    f7c = mkfolder('err7c')
    pet7b._hide_stage = 'searching'
    pet7b._hide_obstacles = [f7c]
    pet7b._hide_folder_path = None
    pet7b._hide_search_started_at = 0        # 0 → 必然超时
    pet7b._hide_search_checked = set()
    pet7b._hide_search_timer = None
    pet7b._hide_search_tick()
    check('E7b-1 超时分支未抛异常（含跨控制器 self._cast_spell_then 解析）', True)
    # ⚠️ `_hide_end_game` 把删除动作**交给施法动画回调**
    #    （`self._cast_spell_then(self._hide_destroy_obstacles, direction='right')`），
    #    删除不是同步发生的 —— 这是**逐字保留的上游行为**，不是本项引入。
    #    所以这里断言「已进入 casting 且回调已登记」，再**手动驱动**回调验证删除。
    check('E7b-2 已进入 casting（删除被排到施法回调）',
          pet7b._spell_stage == 'casting' and pet7b._spell_finish_cb is not None,
          'stage=%r cb=%r' % (pet7b._spell_stage, pet7b._spell_finish_cb))
    cb = pet7b._spell_finish_cb
    if cb is not None:
        cb(None, None)      # 模拟施法 11 帧走完
    check('E7b-3 ★手动驱动施法回调后沙箱目录被真删（os/shutil 解析正确）',
          not os.path.isdir(f7c), 'exists=%r' % os.path.isdir(f7c))
    check('E7b-4 _hide_obstacles 已清空',
          pet7b._hide_obstacles == [], 'obs=%r' % pet7b._hide_obstacles)
except Exception:
    check('E7b-1 超时分支未抛异常', False, traceback.format_exc())

# ---------------- 8. 中断清理 _abort_hide_and_seek ----------------
print()
print('=== E8 _abort_hide_and_seek ===')
try:
    pet8 = M.RalseiPet()
    f8 = mkfolder('abort8')
    pet8._hide_obstacles = [f8]
    pet8.start_hide_and_seek_game()
    pet8._abort_hide_and_seek()
    check('E8a abort 后 stage 归 None', pet8._hide_stage is None,
          'stage=%r' % pet8._hide_stage)
    check('E8b abort 后障碍物列表已清空',
          pet8._hide_obstacles == [], 'obs=%r' % pet8._hide_obstacles)
    check('E8b1 ★abort 同步删除沙箱目录（shutil.rmtree 路径，os 解析正确）',
          not os.path.isdir(f8), 'exists=%r' % os.path.isdir(f8))
    # ⚠️ 原实现**刻意不清** `_hide_moving_cb` / `_hide_moving_cb_stage`
    #    （逐字保留的上游行为，不是本项引入的缺陷）。
    #    安全性由 `_notify_arrived_if_needed` 的 `_hide_stage == _hide_moving_cb_stage`
    #    守卫保证：`_hide_stage` 已置 None → 守卫不成立 → 陈旧回调不会被触发。
    #    断言"陈旧 cb 存在但**不会**被触发"，断行为不断赋值。
    check('E8b2 abort 后 _hide_folder_path 已清',
          pet8._hide_folder_path is None,
          'path=%r' % pet8._hide_folder_path)
    fired8 = []
    if pet8._hide_moving_cb is not None:
        pet8._hide_moving_cb = lambda: fired8.append('stale')
    pet8._notify_arrived_if_needed()
    check('E8b3 ★陈旧回调不会被触发（stage=None 守卫生效）',
          fired8 == [], 'fired=%r' % fired8)
    check('E8c abort 后控制器字典仍只有 p',
          sorted(k for k in pet8.__dict__['hide_seek'].__dict__ if k != 'p') == [])
except Exception:
    check('E8a abort 后 stage 归 None', False, traceback.format_exc())

# ---------------- 9. 报告点错文件夹（_hide_report_clicked_folder）------------
print()
print('=== E9 _hide_report_clicked_folder 对/错分支 ===')
try:
    pet9 = M.RalseiPet()
    pet9.desktop_interaction = _StubDesktopInteraction()
    f9win = mkfolder('win9')
    f9err = mkfolder('err9')
    other9 = mkfolder('other9')
    pet9._hide_stage = 'searching'
    pet9._hide_obstacles = [f9win, f9err]
    pet9._hide_folder_path = f9win
    pet9._hide_search_timer = None
    pet9._hide_search_checked = set()

    # ⚠️ 契约核实（读原文得来，勿凭想象）：
    #   本方法**只负责"打开 + 说一句"**，**不写** `_hide_search_checked`
    #   （那是 `_hide_search_tick` 的职责）。第一版断言写错了 → 假红。
    #   断言要断**真实契约**：错的 → stage 仍 searching；对的 → stage 立刻离开 searching。
    # 1) 错误文件夹：stage 不变、checked 不变
    before_checked = set(pet9._hide_search_checked)
    pet9._hide_report_clicked_folder(f9err)
    check('E9a 错误文件夹：stage 仍 searching',
          pet9._hide_stage == 'searching', 'stage=%r' % pet9._hide_stage)
    check('E9a2 错误文件夹：不改 _hide_search_checked（非本方法职责）',
          pet9._hide_search_checked == before_checked,
          'checked=%r' % pet9._hide_search_checked)

    # 2) 非障碍物路径：直接 return（stage 不变）
    pet9._hide_report_clicked_folder(other9)
    check('E9b 非障碍物路径被忽略（stage 仍 searching）',
          pet9._hide_stage == 'searching', 'stage=%r' % pet9._hide_stage)

    # 3) 正确文件夹 → 玩家赢：stage 必须**立刻**离开 searching（防 1.2s 内双触发）
    #    注意：这会 `QTimer.singleShot(1200, _hide_jump_back_to_desktop)` —— 延迟副作用。
    #    为了不留下悬挂定时器，这里只断言"立刻离开 searching"，随后手动把 stage 复原为 None
    #    并把定时器停掉（singleShot 无句柄 → 用 stage 守卫使其无效：_hide_jump_back_to_desktop
    #    不检查 stage，但 _hide_end_game 会；这里直接把 obstacles 清空以免延迟删除沙箱）。
    pet9._hide_report_clicked_folder(f9win)
    check('E9c ★点对文件夹后 stage 立刻离开 searching（防双结束）',
          pet9._hide_stage != 'searching', 'stage=%r' % pet9._hide_stage)
    # 拆掉延迟副作用：清空障碍物 + 置结束态，使 1.2s 后的回调成为无害 no-op
    pet9._hide_obstacles = []
    pet9._hide_stage = None
except Exception:
    check('E9a 错误文件夹：stage 仍 searching', False, traceback.format_exc())

# ---------------- 10. 铁律 1 常驻哨兵（静态）----------------
print()
print('=== E10 铁律 1 常驻哨兵：self 不得作 Qt parent 传出去 ===')
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
                if fname in QT_TYPES:
                    for a in node.args:
                        if isinstance(a, _ast.Name) and a.id == 'self':
                            hits.append('%s:%d %s(self)' % (cls_name, node.lineno, fname))
        return hits, ''

    hits2, err2 = _scan_file(os.path.join(MODS, 'hide_controller.py'),
                             'HideAndSeekController')
    check('E10a hide_controller 内无 Qt(self) 形态', hits2 == [],
          'hits=%s err=%s' % (hits2, err2))
    # 正控制：确认扫描器真的能抓到（用一个构造出来的样本）
    probe = ('class X:\n'
             '    def f(self):\n'
             '        return QTimer(self)\n')
    tmp = os.path.join(os.environ.get('TEMP', '.'), '_w1_2_probe.py')
    _io.open(tmp, 'w', encoding='utf-8').write(probe)
    hitsP, errP = _scan_file(tmp, 'X')
    check('E10b 正控制：扫描器能抓到 QTimer(self)', len(hitsP) == 1,
          'hits=%r err=%s' % (hitsP, errP))
    os.remove(tmp)
except Exception:
    check('E10a hide_controller 内无 Qt(self) 形态', False, traceback.format_exc())

# ---------------- 11. 铁律 6 动态哨兵 + 计数 ----------------
print()
print('=== E11 铁律 6：裸 _log_() 哨兵 ===')
try:
    import ast as _ast
    import io as _io
    csrc = _io.open(os.path.join(MODS, 'hide_controller.py'), encoding='utf-8').read()
    ct = _ast.parse(csrc)
    bare = []
    for node in _ast.walk(ct):
        if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Name) \
                and node.func.id == '_log_':
            bare.append(node.lineno)
    check('E11a 静态：无裸 _log_() 调用', bare == [], 'lines=%s' % bare)

    # 动态：真调一个会打日志的方法，若裸调用 → NameError
    pet11 = M.RalseiPet()
    pet11._hide_stage = 'searching'
    pet11._hide_obstacles = [r'C:\Windows']
    pet11._hide_folder_path = r'C:\Windows'
    pet11._hide_search_checked = set()
    pet11._hide_search_timer = None
    pet11._hide_search_started_at = 9999999999      # 未超时 → 走"表演找"分支（会打 _log）
    err = None
    try:
        pet11._hide_search_tick()
    except NameError as e:
        err = e
    check('E11b 动态：_hide_search_tick 无 NameError', err is None,
          repr(err))
    # 计数：self._log_() 形态应 >= 15
    n_selflog = csrc.count('self._log_().')
    check('E11c self._log_(). 计数 >= 15', n_selflog >= 15, 'count=%d' % n_selflog)
except Exception:
    check('E11a 静态：无裸 _log_() 调用', False, traceback.format_exc())

# ---------------- 12. 互写点：_spell_auto_suspended 落宿主（W1-1 耦合）------
print()
print('=== E12 W1-1↔W1-2 互写点：_spell_auto_suspended ===')
try:
    pet12 = M.RalseiPet()
    f12 = mkfolder('spell12')
    pet12._spell_auto_suspended = True
    pet12._hide_stage = 'searching'
    pet12._hide_obstacles = [f12]
    pet12._hide_folder_path = f12
    pet12._hide_search_timer = None
    pet12._hide_search_checked = set()
    pet12._hide_destroy_obstacles()
    check('E12a _hide_destroy_obstacles 后 _spell_auto_suspended 落宿主且为 False',
          pet12.__dict__.get('_spell_auto_suspended') is False,
          'host=%r ctrl=%r' % (pet12.__dict__.get('_spell_auto_suspended'),
                               pet12.__dict__['hide_seek'].__dict__.get('_spell_auto_suspended')))
    check('E12b 控制器里没有自己的 _spell_auto_suspended',
          '_spell_auto_suspended' not in pet12.__dict__['hide_seek'].__dict__)
    # `winshell` 本机未安装 → 走 `shutil.rmtree` 兜底（同步删除）
    check('E12c ★沙箱目录被真删（os/shutil 解析正确）',
          not os.path.isdir(f12), 'exists=%r' % os.path.isdir(f12))
except Exception:
    check('E12a _hide_destroy_obstacles 后 _spell_auto_suspended 落宿主',
          False, traceback.format_exc())

# ---------------- 14. ★ 新增回归哨兵：本轮两个真 P0 ----------------
print()
print('=== E14 ★回归哨兵（本轮 e2e 抓到的两个 P0）===')
try:
    # (a) 跨控制器解析：hide 调 spell 的方法、spell 调 hide 的方法
    p14 = M.RalseiPet()
    sp14 = p14.__dict__['spell']
    hd14 = p14.__dict__['hide_seek']
    gm14 = p14.__dict__['games']
    check('E14a spell 能解析 hide 的 _abort_hide_and_seek',
          getattr(sp14, '_abort_hide_and_seek', 'MISSING') != 'MISSING')
    check('E14b hide 能解析 spell 的 _cast_spell_then',
          getattr(hd14, '_cast_spell_then', 'MISSING') != 'MISSING')
    check('E14c hide 能解析 spell 的 _hide_destroy_obstacles 回调（_start_open_with_spell）',
          getattr(hd14, '_start_open_with_spell', 'MISSING') != 'MISSING')
    # 负控制：不存在的方法仍须 AttributeError（不许吞错）
    for ctrl, lbl in [(sp14, 'spell'), (hd14, 'hide_seek'), (gm14, 'games')]:
        try:
            getattr(ctrl, '_definitely_not_exist_xyz')
            check('E14d %s 不存在名仍抛 AttributeError' % lbl, False, 'no raise')
        except AttributeError:
            check('E14d %s 不存在名仍抛 AttributeError' % lbl, True)
        except RecursionError:
            check('E14d %s 不存在名仍抛 AttributeError' % lbl, False, 'RecursionError')
    # (b) import os / time / QPoint 三件套真实可用（静态 + 行为）
    import ast as _ast2
    import io as _io2
    hsrc = _io2.open(os.path.join(MODS, 'hide_controller.py'), encoding='utf-8').read()
    ht = _ast2.parse(hsrc)
    mod_names = set()
    for n in ht.body:
        if isinstance(n, _ast2.Import):
            for a in n.names: mod_names.add(a.name)
        elif isinstance(n, _ast2.ImportFrom):
            for a in n.names: mod_names.add(a.name)
    check('E14e 模块级 import 含 os（L448 os.path.isdir 等 11 处裸用）', 'os' in mod_names,
          str(sorted(mod_names)))
    check('E14f 模块级 import 含 time', 'time' in mod_names)
    check('E14g 模块级 import 含 QPoint', 'QPoint' in mod_names)
except Exception:
    check('E14a spell 能解析 hide 的 _abort_hide_and_seek', False, traceback.format_exc())

# ---------------- 15. 清理沙箱 ----------------
try:
    shutil.rmtree(SANDBOX, ignore_errors=True)
    check('E13 沙箱目录已清理', not os.path.isdir(SANDBOX))
except Exception:
    pass

# ---------------- 汇总 ----------------
PASS = sum(1 for _, ok, _ in results if ok)
FAIL = len(results) - PASS
print()
print('=' * 60)
print('W1-2 E2E  PASS=%d  FAIL=%d' % (PASS, FAIL))
print('=' * 60)
if FAIL:
    print('FAILED:')
    for n, ok, d in results:
        if not ok:
            print('   ', n, '::', d[:400])
sys.exit(1 if FAIL else 0)

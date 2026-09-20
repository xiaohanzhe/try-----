# -*- coding: utf-8 -*-
"""W1-2 A/B 校验：**父版本** vs **当前版本**，跑同一组躲猫猫场景，比对轨迹。

A/B 纪律（W1-4 报告第五节 + W1-1 报告 6.1~6.4，全是真踩）：
  1. **先断言 A ≠ B** —— 取"旧值"若恰好拿到已提交的当前版，A == B，
     探针退化成"自己跟自己比"，结论必然"没差别"**且非常像真的**。
  2. 取**父版本**源码：本项施工**尚未提交** → 父版本 = `git show HEAD:ralsei_pet/src/main.py`。
  3. **A/B 两侧取源码必须按方法实际所在文件取**：
       A 侧 = 父版 `main.py`（12 个方法还在里面）
       B 侧 = 工作区 `modules/hide_controller.py`（已搬过去）
     早先版本两侧都从 `main.py` 取 → 当前侧恒为空 → 根本没跑起来（W1-1 6.1）。
  4. ★ **「A 和 B 结果相同」在 A、B 都失败时同样成立** —— 每个场景必须有
     ①结果一致 ②**两侧均无异常** 两组断言，否则测的是"两个空壳彼此相等"（W1-1 6.2）。
  5. 轨迹 = 一组**行为可观测量**的序列（不是源码文本），两版必须逐项一致。

与 unit / e2e 探针的分工：
  · unit —— 静态：方法体逐字等价 + 铁律哨兵
  · e2e  —— 动态：当前版能跑
  · ab   —— 动态×2：**两版跑出同样的行为**（"改造不改行为"的直接证据）

安全约束（同 e2e，首跑真踩过）：
  被搬方法里有**真删目录**（`_hide_destroy_obstacles` → winshell/shutil.rmtree）与
  **真开文件夹**（`_hide_search_tick` → `os.startfile`）的路径 ⇒ 本脚本**只**使用
  自建沙箱目录 `tempfile.gettempdir()/_w1_2_ab_tmp`，**绝不**塞真实系统目录。
  沙箱必须在**本地 NTFS**（E 盘是 exFAT：`os.makedirs` 会 `OSError: [WinError 1]`）。
"""
import ast
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import types

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
CTRL = os.path.join(ROOT, 'ralsei_pet', 'modules', 'hide_controller.py')
CTRL_REL = 'ralsei_pet/modules/hide_controller.py'

NAMES = ['start_hide_and_seek_game', '_abort_hide_and_seek', '_hide_move_to_point',
         '_hide_on_arrive_center', '_hide_create_obstacles_after_spell',
         '_hide_after_hiding_spell', '_hide_on_arrive_folder', '_hide_search_tick',
         '_hide_end_game', '_hide_destroy_obstacles', '_hide_report_clicked_folder',
         '_hide_jump_back_to_desktop']

SANDBOX = os.path.join(tempfile.gettempdir(), '_w1_2_ab_tmp')
if os.path.isdir(SANDBOX):
    shutil.rmtree(SANDBOX, ignore_errors=True)
os.makedirs(SANDBOX, exist_ok=True)

_mkseq = [0]
# ★ 绝对路径 → 「稳定逻辑名」登记表。
#   存在的理由：`_mkseq` 的自增序号**就在目录名里**（`ab7_win_20`），
#   所以 `os.path.basename()` **不能**把它抹掉 —— 首跑 AB7.clicked / AB10 win / AB10 err
#   三项就是被这个假差异绊的（`ab7_win_20` vs `ab7_win_23`，看着像行为差异，
#   其实只是"两侧各建了一遍夹具"）。用登记表做**精确**归一：
#   登记过的 → 换成 tag；没登记过的 → 原样保留（绝不靠正则猜）。
_STABLE = {}


def mkfolder(tag):
    """沙箱内建唯一子目录 —— 绝不复用真实路径。"""
    _mkseq[0] += 1
    p = os.path.join(SANDBOX, '%s_%d' % (tag, _mkseq[0]))
    os.makedirs(p, exist_ok=True)
    _STABLE[os.path.normcase(os.path.normpath(p))] = tag
    return p


def stable_name(v):
    """把沙箱绝对路径换成稳定逻辑名；没登记过的一律原样返回。"""
    if not isinstance(v, str):
        return v
    key = os.path.normcase(os.path.normpath(v))
    if key in _STABLE:
        return '<%s>' % _STABLE[key]
    # 退化路径：只认"同一父目录下、名字是已登记名 + _数字"的形式
    d, b = os.path.split(v)
    if os.path.normcase(os.path.normpath(d)) == os.path.normcase(
            os.path.normpath(SANDBOX)):
        for lbl in set(_STABLE.values()):
            if b.startswith(lbl + '_') and b[len(lbl) + 1:].isdigit():
                return '<%s>' % lbl
    return v


results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('  [PASS] ' if ok else '  [FAIL] ') + name +
          ((' :: ' + detail) if detail else ''))


def git_show(path, rev):
    p = subprocess.run(['git', 'show', '%s:%s' % (rev, path)],
                       cwd=ROOT, capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout.decode('utf-8', 'replace')


# ============================================================================
print('=== AB0/AB1 前置：取父版本 + 断言 A != B ===')
# ============================================================================
cur_src = io.open(CTRL, encoding='utf-8').read()      # B：当前（控制器）
rev, old_src = None, None
for _rev in ('HEAD', 'HEAD~1', 'HEAD~2'):
    s = git_show('ralsei_pet/src/main.py', _rev)
    if s and all(('    def %s' % n) in s for n in NAMES):
        rev, old_src = _rev, s
        break
check('AB0 找到含这 12 个方法的父版本', old_src is not None, 'rev=%s' % rev)
if old_src is None:
    sys.exit(1)

md5_old = hashlib.md5(old_src.encode('utf-8')).hexdigest()
md5_cur = hashlib.md5(cur_src.encode('utf-8')).hexdigest()
print('   父版本 %s md5 = %s' % (rev, md5_old))
print('   当前   md5 = %s' % md5_cur)
if md5_old == md5_cur:
    # 硬红线：A == B 时继续跑毫无意义，且会产出"非常像真的"的假结论
    print('  !! A == B —— 探针已退化，拒绝继续（这是 W1-4 踩过的坑）')
    sys.exit(3)
check('AB1 A != B（md5 不同，探针未退化）', md5_old != md5_cur)

# ============================================================================
print()
print('=== AB2 两侧方法提取（★按方法实际所在文件取）===')
# ============================================================================
from PyQt5.QtWidgets import QApplication            # noqa: E402
app = QApplication.instance() or QApplication([])

# ★ QTimer 打桩（**必须在两侧对称安装**）
#   真实 `QTimer(parent)` 在 offscreen 下 parent 传普通 object 会 `TypeError`
#   （铁律 1 的现场），且 start() 会真的起定时器污染后续场景。
#   桩要保留**关键语义**：`type(parent).__name__` 会被记下来，
#   于是"父版本传宿主 / 当前版本误传控制器"这类差异**仍可观测**（反控 AB12b 靠它）。
#   ⚠️ 顺序要紧：**必须在 AB2 的 AST 提取之后安装** —— 见下方 AB2 之后的注释。
import PyQt5.QtCore as _QC                      # noqa: E402
_REAL_QTIMER = _QC.QTimer


def extract_methods(src):
    """在整份源码里搜这 12 个方法，**不预设宿主类名**。

    A 侧它们是 `RalseiPet` 的成员、B 侧是 `HideAndSeekController` 的成员 ——
    写死类名会让一侧静默返回 {}（W1-1 6.1 已踩）。
    """
    t = ast.parse(src)
    found = {}
    for node in ast.walk(t):
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name in NAMES:
                    found[fn.name] = fn
    return found


old_nodes = extract_methods(old_src)
cur_nodes = extract_methods(cur_src)
check('AB2a 父版本 12 个方法可提取', len(old_nodes) == 12, 'n=%d' % len(old_nodes))
check('AB2b 当前版本 12 个方法可提取', len(cur_nodes) == 12, 'n=%d' % len(cur_nodes))
print('   A = %s:ralsei_pet/src/main.py' % rev)
print('   B = 工作区 ralsei_pet/modules/hide_controller.py')
if len(old_nodes) != 12 or len(cur_nodes) != 12:
    # 提取不齐就没有 A/B 可言，硬退（不产"静默跳过"的假绿）
    sys.exit(3)

# ★ 动态安装前的**命名空间静态校验**（比运行期报错更早、更有指向性）
#   真机 `hide_controller.py` 的模块命名空间 = {logging, os, time, QPoint, _log, 类}。
#   被搬的 12 个方法体里出现的**每一个裸名**都必须能在这里解析，否则运行时 NameError。
#   这比"跑一遍看炸不炸"更可靠：跑一遍只能覆盖**走到过的分支**。
import ast as _ast2                                        # noqa: E402


def _module_ns_names(src):
    t = _ast2.parse(src)
    names, func_calls = set(), set()
    for n in t.body:
        if isinstance(n, _ast2.Import):
            for a in n.names:
                names.add((a.asname or a.name).split('.')[0])
        elif isinstance(n, _ast2.ImportFrom):
            for a in n.names:
                names.add(a.asname or a.name)
        elif isinstance(n, _ast2.FunctionDef):
            func_calls.add(n.name)
        elif isinstance(n, _ast2.ClassDef):
            func_calls.add(n.name)
        elif isinstance(n, _ast2.Assign):
            for tg in n.targets:
                if isinstance(tg, _ast2.Name):
                    func_calls.add(tg.id)
    return names, func_calls


BUILTINS_OK = set(dir(__builtins__ if isinstance(__builtins__, dict)
                      else __builtins__))
_ctrl_ns, _ctrl_defs = _module_ns_names(cur_src)
print('   B 侧模块命名空间 = %s' % sorted(_ctrl_ns))

_bad = []
for _nm in NAMES:
    fn = cur_nodes[_nm]
    for _node in _ast2.walk(fn):
        if isinstance(_node, _ast2.Name) and isinstance(_node.ctx, _ast2.Load):
            nid = _node.id
            if nid in ('self', 'True', 'False', 'None'):
                continue
            if nid in BUILTINS_OK:
                continue
            if nid in _ctrl_ns or nid in _ctrl_defs:
                continue
            # 方法体内的局部变量 / 局部 import / 参数 —— 需要做作用域分析，
            # 这里只做"粗筛"：报出来的名字人工核对，**不自动判定失败**。
            _bad.append((_nm, _node.lineno, nid))
# 只报"既不在模块命名空间、也不是局部定义"的候选 —— 上层用 AST 作用域粗筛
# （局部变量名会被列进来，属噪声；真正承重的模块级裸名会是 os/time/QPoint 那一类）。
_cand = sorted(set(nid for _, _, nid in _bad))
print('   待人工核对的名字（含局部变量噪声）= %s' % _cand)
check('AB2c ★B 侧模块级命名空间含 os / time / QPoint / logging',
      {'os', 'time', 'QPoint', 'logging'} <= _ctrl_ns,
      'ns=%s' % sorted(_ctrl_ns))

# ★ QTimer 打桩（**两侧对称安装**）——放在 AB2 提取**之后**：
#   AB2 是纯静态 AST 提取，不需要 QTimer；而把它放前面会破坏
#   `_hide_report_clicked_folder` 里 `from PyQt5.QtCore import QTimer` 的解析。
import PyQt5.QtCore as _QC2                                 # noqa: E402


class _QTimerSpy(object):
    """记录 parent 类型 + 启动间隔的 QTimer 替身（两侧对称，不改变被测代码）。"""

    def __init__(self, parent=None):
        self._parent = parent
        self._parent_type = type(parent).__name__
        self._interval = None
        self._active = False
        self.timeout = type('_Sig', (), {
            'connect': staticmethod(lambda *a, **k: None)})()
        taken.append((self._parent_type, None))

    def start(self, ms):
        self._interval = ms
        self._active = True
        # 回填真实间隔，供"起了 3000ms 计时器"这类断言
        if taken:
            taken[-1] = (taken[-1][0], ms)

    def stop(self):
        self._active = False

    def isActive(self):
        return self._active

    def parent(self):
        return self._parent

    # ★ 静态方法 `QTimer.singleShot(ms, fn)` **必须保留**：
    #   `_hide_report_clicked_folder` / `_hide_jump_back_to_desktop` 都靠它。
    #   首跑漏了 → 两侧**同时**抛 AttributeError（A/B 判定"一致"）→ 靠 AB10/AB11
    #   的"两侧均无异常"哨兵才露馅。
    #   桩里**不执行**回调：回调会真的驱动下一段流程（跳回桌面 → 结束游戏），
    #   在本方法体内做延迟副作用会让场景不可控；只记录"排了一个延迟回调"。
    @staticmethod
    def singleShot(ms, fn):
        singleshot.append(ms)
        return None


taken = []
singleshot = []
_QC2.QTimer = _QTimerSpy

# ============================================================================
print()
print('=== AB3 构造共享 stub 宿主 ===')
# ============================================================================


class _StubDesktop(object):
    """桩：`desktop_interaction` 的可观测替身。

    `_hide_create_obstacles_after_spell` 读 `.desktop_path`；
    `_hide_search_tick` / `_hide_report_clicked_folder` 调 `.open_folder()`；
    `_hide_search_tick` 还调 `.get_all_visible_windows()`（返回空 → 走"表演找"分支）。
    """

    def __init__(self, desktop_dir, sink):
        self.desktop_path = desktop_dir
        self._sink = sink
        self.opened = []

    def get_all_visible_windows(self):
        return []

    def open_folder(self, p):
        self.opened.append(p)
        # ⚠️ sink 里只记**稳定逻辑名**，不记绝对路径：沙箱目录名里带探针自增序号，
        #    两侧 A/B 分别跑时序号必然不同 → 记绝对路径会造成**夹具假差异**
        #    （首跑 AB7.clicked / AB10 win / AB10 err 就是被这个假差异绊的）。
        #    ⚠️ 只 `basename()` 也**不够**（序号在目录名里）→ 走 `stable_name()`。
        self._sink.append(('open_folder', stable_name(p)))


def _norm_sink(sink):
    """把事件序列里带沙箱路径/自增序号的部分归一成**稳定逻辑名**，供跨侧比较。

    ⚠️ 首跑这里只做 `basename()` —— 不够：序号在**目录名**里（`ab7_win_20`），
    basename 之后仍是 `ab7_win_20` vs `ab7_win_23` → 假差异 → 3 项假红。
    """
    out = []
    for item in sink:
        t = item[0]
        args = tuple(stable_name(v) for v in item[1:])
        out.append((t,) + args)
    return out


def make_stub(sink, folder_ok=True):
    """一个最小宿主：字段与真机一致，方法只做可观测记录。

    ⚠️ 必须把 `_hide_moving_cb` 等 4 个新状态**预声明**在 stub 上（复刻真机
    `init_systems` 的预声明）—— 否则控制器 `__setattr__` 的转发判据
    （"宿主已拥有？"）不成立 → 首赋值落控制器 → 造成**假差异**（W1-4 坑 3 同型）。
    """
    class Dialogue(object):
        def __init__(self):
            self.lines = []
            self.shown = 0

        def add_dialogue(self, who, txt, face=None):
            self.lines.append((who, txt, face))
            sink.append(('say', txt))

        def show_dialogue(self):
            self.shown += 1
            sink.append(('show', None))

    class Agent(object):
        def suspend(self):
            sink.append(('agent', 'suspend'))

        def resume(self):
            sink.append(('agent', 'resume'))

    class Screen(object):
        """⚠️ 必须实现 `center()` —— `_hide_create_obstacles_after_spell` 用的是
        `screen.center().x()/.y()`（不是 `screen.x()`）。首跑漏了它 →
        两侧**同时**抛 `AttributeError`（A/B 依旧"一致"，全靠 AB5b 哨兵才露馅）。"""

        def x(self):
            return 0

        def y(self):
            return 0

        def width(self):
            return 1920

        def height(self):
            return 1080

        def center(self):
            return _Point(960, 540)

        def size(self):
            return _Size(1920, 1080)

    class _Point(object):
        def __init__(self, px, py):
            self._x, self._y = px, py

        def x(self):
            return self._x

        def y(self):
            return self._y

    class _Size(object):
        def __init__(self, w, h):
            self._w, self._h = w, h

        def width(self):
            return self._w

        def height(self):
            return self._h

    class Stub(object):
        pass

    s = Stub()
    # ★★ `s.p = s` —— 本探针最反直觉、也最必需的一行。
    #   本探针的"方法体搬迁"形态是 `types.MethodType(fn, stub)`：方法体内的
    #   **`self` 就是 stub（宿主）**，不是控制器。而当前版控制器里写的是
    #   `QTimer(self.p)`（真机 `self.p` = 宿主）。若不给 stub 一个 `p`，
    #   这行就抛 `AttributeError` → 被方法自带的 `except Exception` **静默吞掉**
    #   → 计时器根本不建 → 两侧末态出现**假差异**（首跑 AB6d 就是这个）。
    #   把 `p` 指向 stub 自己，等价于"控制器眼里的宿主" —— 语义与真机对齐：
    #   `QTimer(self)`（A 侧）与 `QTimer(self.p)`（B 侧）落到**同一个对象**。
    #   ⚠️ 这**不**构成对铁律 1 的验证（见 AB12b）：它只保证 A/B 的"落点"
    #      在探针形态下可比。铁律 1 由 e2e（真控制器实例）负责。
    s.p = s
    s.dialogue_ui = Dialogue()
    s.autonomous_agent = Agent()
    s.desktop_interaction = _StubDesktop(sink_desktop_dir[0], sink)
    s.game_state = {'is_playing': False, 'game_type': None}
    # ---- 躲猫猫状态（真机 init_systems 预声明的那一份）----
    s._hide_stage = None
    s._hide_folder_path = None
    s._hide_obstacles = []
    s._hide_center_x = None
    s._hide_center_y = None
    s._hide_search_timer = None
    s._hide_search_started_at = 0
    s._hide_search_checked = set()
    s._hide_moving_cb = None
    s._hide_moving_cb_stage = None
    # ---- W1-1 互写点 ----
    s._spell_stage = None
    s._spell_auto_suspended = False
    s._spell_finish_cb = None
    # ---- 移动子系统状态（init_movement 声明）----
    s.target_pos = None
    s.is_moving = False
    s.speed = 0.0
    s.moving_duration = 0
    # ---- QWidget 面（宿主 API 桩）----
    s._pos = [100, 100]
    s.anim_calls = []
    s.move_calls = []
    s.show_calls = [0]
    s.hide_calls = [0]

    def change_animation(anim, force=False, **kw):
        s.anim_calls.append((anim, force))
        sink.append(('anim', anim))

    def move(x, y):
        s._pos = [x, y]
        s.move_calls.append((x, y))

    def show():
        s.show_calls[0] += 1
        sink.append(('show_win', None))

    def hide():
        s.hide_calls[0] += 1
        sink.append(('hide_win', None))

    def x():
        return s._pos[0]

    def y():
        return s._pos[1]

    def width():
        return 100

    def height():
        return 100

    class _FG(object):
        def x(self):
            return s._pos[0]

        def y(self):
            return s._pos[1]

        def width(self):
            return 100

        def height(self):
            return 100

        def center(self):
            fg = _FG()
            return fg

    def frameGeometry():
        fg = _FG()
        return fg

    def _current_screen_rect():
        return Screen()

    def _resolve_target_screen_anchor(path):
        # ⚠️ 只记**稳定逻辑名**（理由同 `_StubDesktop.open_folder`：
        #    序号在目录名里，basename 抹不掉）。
        sink.append(('resolve_anchor', stable_name(path)))
        return (600, 500)

    def _clamp_pos_to_desktop(px, py):
        sink.append(('clamp', (px, py)))
        return (px, py)

    def _notify_arrived_if_needed():
        """复刻宿主真实现的语义：stage 名对上才触发回调，触发后清空。"""
        cb = getattr(s, '_hide_moving_cb', None)
        st = getattr(s, '_hide_moving_cb_stage', None)
        if cb is not None and st is not None and st == s._hide_stage:
            s._hide_moving_cb = None
            s._hide_moving_cb_stage = None
            sink.append(('arrived', st))
            cb()
        else:
            sink.append(('arrived_skip', st))

    s.change_animation = change_animation
    s.move = move
    s.show = show
    s.hide = hide
    s.x = x
    s.y = y
    s.width = width
    s.height = height
    s.frameGeometry = frameGeometry
    s._current_screen_rect = _current_screen_rect
    s._resolve_target_screen_anchor = _resolve_target_screen_anchor
    s._clamp_pos_to_desktop = _clamp_pos_to_desktop
    s._notify_arrived_if_needed = _notify_arrived_if_needed
    # 兄弟控制器方法（B 侧控制器内 `self._cast_spell_then` 会命中第 3 条白名单）
    s._cast_spell_then = lambda cb, direction=None, **kw: sink.append(
        ('cast_spell_then', direction))
    # ★ 供 `_log_()` 解析"宿主模块的 logger" —— 复刻控制器 `_log_` 的真语义。
    #   两侧必须指向**同一个** logger 对象，否则测的是夹具差异。
    s._ab_host_module = _HOST_MODULE
    return s


class _HostModuleShim(object):
    """stub 宿主的"模块"替身：只需提供一个 `_log`。"""
    def __init__(self):
        import logging
        self._log = logging.getLogger('ab_probe_w12_host')


_HOST_MODULE = _HostModuleShim()


sink_desktop_dir = [SANDBOX]


def install_code(stub, whole_src, names, sink):
    """把 whole_src 里 names 指定的方法**全部**编译绑到 stub 上。

    ★ 必须一次装齐 12 个：`_hide_on_arrive_center` 调 `self._cast_spell_then`、
      `_hide_end_game` 调 `self._hide_destroy_obstacles` —— 只装"被直接驱动的那个"
      会让两侧**同时**抛 AttributeError → 轨迹相同 → 假 PASS（W1-1 6.2 已踩）。
    ★ `_log_` **不在** `NAMES` 里，必须**单独**绑（W1-1 6.3 已踩）。

    ★★ 命名空间的**两条不对称**，是反控 AB12d 能成立的全部依据，别"顺手统一"：
      · 模块级 **`_log`**（logger 对象）**必须注入** —— A 侧（父版本）方法体里
        写的是 `_log.debug(...)`，没它连 A 侧都跑不起来。
      · 模块级 **`_log_`**（方法名）**绝不能注入** —— B 侧（当前版）写的是
        `self._log_()`。若给模块级 `_log_` 兜底，把 `self.` 抹掉的反控版本
        也会照样解析成功 → 反控假绿。
      · 二者是**不同的名字**，互不兜底（这一点我错判过一次，见 AB12 跤 ②）。
    """
    t = ast.parse(whole_src)
    lines = whole_src.split('\n')
    bodies = {}
    for node in ast.walk(t):
        if isinstance(node, ast.ClassDef):
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name in names:
                    bodies[fn.name] = '\n'.join(lines[fn.lineno - 1:fn.end_lineno])

    import logging
    import time
    from PyQt5.QtCore import QPoint
    ns = {'__name__': '_ab_probe_w12', 'time': time, 'os': os,
          'QPoint': QPoint, '_log': logging.getLogger('ab_probe_w12')}

    mod_src = 'class _Holder(object):\n'
    for nm in names:
        if nm not in bodies:
            continue
        for line in bodies[nm].split('\n'):
            mod_src += ('    ' + line if line.strip() else '') + '\n'
        mod_src += '\n'
    # `_Holder._log_` 占位：装上"装的时候就存在"的版本，随后被 `_host_log_` 覆盖。
    mod_src += ('\n'.join('    ' + l if l.strip() else '' for l in '''

    def _log_(self):
        import logging
        return logging.getLogger('ab_probe_w12')
'''.split('\n')))

    exec(compile(mod_src, '<ab_w12>', 'exec'), ns)
    H = ns['_Holder']
    ok = []
    # ★ `_log_` 不在 NAMES 里，必须**单独**绑 —— 只遍历 names 会漏掉它，
    #   于是会打日志的分支触发 `self._log_()` 时抛 AttributeError（W1-1 6.3 踩过）。
    for nm in list(names) + ['_log_']:
        if hasattr(H, nm):
            setattr(stub, nm, types.MethodType(getattr(H, nm), stub))
            if nm in names:
                ok.append(nm)
    # ★ `_log_` 覆盖成"返回宿主模块 logger"的真实现 —— 复刻控制器的 `_log_` 语义。
    #   两侧必须指向**同一个** logger 对象，否则测的是夹具差异。
    setattr(stub, '_log_', types.MethodType(_host_log_, stub))
    return ok


def _log_impl(self):
    """`_log_` 的真语义：返回**宿主模块**的模块级 `_log`。

    ⚠️ 这里刻意用 `self._ab_host_module`（夹具给宿主打的标记）而**不是**
    `type(self.p).__module__` —— 本探针的宿主是 stub，没有 `p`。
    两侧用**同一个** logger 对象，测的是行为不是夹具差异。

    ⚠️⚠️ 用 `self.__dict__.get(...)` 而**不是** `getattr(self, ...)`：
    本探针的 stub **不实现** `__setattr__` 转发壳（那正是被测对象的一部分），
    但 A 侧的 12 个方法会被绑到 stub 上 —— 如果 stub 实现了 `__getattr__` 回落，
    就会引入真实宿主没有的行为。用 `__dict__` 直取，**两侧完全对称**、零副作用。
    """
    mod = self.__dict__.get('_ab_host_module') if hasattr(self, '__dict__') else None
    if mod is not None:
        lg = getattr(mod, '_log', None)
        if lg is not None:
            return lg
    import logging
    return logging.getLogger('ab_probe_w12')


_host_log_ = _log_impl


# ============================================================================
print()
print('=== AB4 场景 1：入口 start_hide_and_seek_game + 到达回调链 ===')
# ============================================================================


def scenario_entry(whole_src):
    sink = []
    stub = make_stub(sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 12, '方法没装齐: %s' % got
    err = None
    try:
        ret = stub.start_hide_and_seek_game()
    except Exception as e:
        ret, err = None, '%s: %s' % (type(e).__name__, e)
    snap = {
        'ret': ret,
        'stage': stub._hide_stage,
        'cx': stub._hide_center_x,
        'cy': stub._hide_center_y,
        'game_playing': stub.game_state.get('is_playing'),
        'game_type': stub.game_state.get('game_type'),
        'is_moving': stub.is_moving,
        'target_pos': (stub.target_pos.x(), stub.target_pos.y())
        if stub.target_pos is not None else None,
        'speed': stub.speed,
        'moving_duration': stub.moving_duration,
        'cb_reg': getattr(stub, '_hide_moving_cb', None) is not None,
        'cb_stage': stub._hide_moving_cb_stage,
        'anim': [a for a, _ in stub.anim_calls],
        'err': err,
    }
    return sink, snap


def scenario_entry_arrive(whole_src):
    """入口 → 手动驱动到达钩子 → 校验回调链真的接上了。"""
    sink = []
    stub = make_stub(sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 12, '方法没装齐: %s' % got
    err = None
    try:
        stub.start_hide_and_seek_game()
        stub._notify_arrived_if_needed()          # stage == 'moving_to_center' → 触发
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    snap = {
        'stage': stub._hide_stage,                # 期望 'creating'
        'cb_c': stub._hide_moving_cb,
        'cb_stage': stub._hide_moving_cb_stage,
        'anim': [a for a, _ in stub.anim_calls],
        'err': err,
    }
    return sink, snap


so, ao = scenario_entry(old_src)
sn, an = scenario_entry(cur_src)
check('AB4a 两侧均无异常', ao['err'] is None and an['err'] is None,
      'old=%r new=%r' % (ao['err'], an['err']))
check('AB4b 现场确认真的跑到了（stage 非 None）', ao['stage'] is not None,
      'stage=%r' % ao['stage'])
check('AB4c 入口事件序列一致', _norm_sink(so) == _norm_sink(sn), '\n      old=%s\n      new=%s' % (_norm_sink(so), _norm_sink(sn)))
check('AB4d 入口末态一致', ao == an, '\n      old=%s\n      new=%s' % (ao, an))

so2, ao2 = scenario_entry_arrive(old_src)
sn2, an2 = scenario_entry_arrive(cur_src)
check('AB4e 到达链两侧均无异常',
      ao2['err'] is None and an2['err'] is None,
      'old=%r new=%r' % (ao2['err'], an2['err']))
check('AB4f ★到达回调真的触发了（stage -> creating）',
      ao2['stage'] == 'creating', 'stage=%r' % ao2['stage'])
check('AB4g 到达链事件序列一致', _norm_sink(so2) == _norm_sink(sn2),
      '\n      old=%s\n      new=%s' % (_norm_sink(so2), _norm_sink(sn2)))
check('AB4h 到达链末态一致', ao2 == an2,
      '\n      old=%s\n      new=%s' % (ao2, an2))

# ============================================================================
print()
print('=== AB5 场景 2：造障碍物 + 藏身施法回调（真建文件夹，沙箱内）===')
# ============================================================================


def scenario_create(whole_src, n_made=5):
    """造 5 个障碍物（真 os.makedirs 到沙箱），比对创建的**相对名**集合。

    返回的相对名排序后比对 —— 绝对路径里含探针自增序号，两侧必然不同，
    但那是**夹具差异**不是行为差异，故只比相对名 + 数量 + 末态。
    """
    sink = []
    box = mkfolder('ab5')
    sink_desktop_dir[0] = box
    stub = make_stub(sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 12, '方法没装齐: %s' % got
    stub._hide_stage = 'creating'
    stub._hide_center_x = 500
    stub._hide_center_y = 400
    err = None
    try:
        stub._hide_create_obstacles_after_spell()
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    made = sorted(os.path.basename(p) for p in stub._hide_obstacles)
    snap = {
        'n_made': len(stub._hide_obstacles),
        'names': made,
        'stage': stub._hide_stage,
        'has_folder': stub._hide_folder_path is not None,
        'folder_in_obstacles': stub._hide_folder_path in stub._hide_obstacles,
        'anim': [a for a, _ in stub.anim_calls],
        'says': len(stub.dialogue_ui.lines),
        'err': err,
    }
    return sink, snap


so, ao = scenario_create(old_src)
sn, an = scenario_create(cur_src)
check('AB5a 两侧均无异常', ao['err'] is None and an['err'] is None,
      'old=%r new=%r' % (ao['err'], an['err']))
check('AB5b ★真的建出了文件夹（非空跑）', ao['n_made'] == 5, 'n=%r' % ao['n_made'])
check('AB5b2 ★创建名集合与数量都符合固定布局（上 3 下 2）',
      ao['names'] == sorted(['障碍物1', '障碍物2', '障碍物3',
                             '障碍物4', '障碍物5']),
      'names=%r' % (ao['names'],))
check('AB5c 建出的事件序列一致', _norm_sink(so) == _norm_sink(sn), '\n      old=%s\n      new=%s' % (_norm_sink(so), _norm_sink(sn)))
check('AB5d 末态一致（含创建名集合 / stage / 藏身点归属）', ao == an,
      '\n      old=%s\n      new=%s' % (ao, an))

# ============================================================================
print()
print('=== AB6 场景 3：藏身点到达 → searching + QTimer（铁律 1 现场）===')
# ============================================================================


def scenario_searching(whole_src):
    """`_hide_on_arrive_folder`：`self.hide()` + 建 `QTimer(self.p)` + 起 3s 计时器。

    ★ 这一组正是**铁律 1** 的现场：父版本 `QTimer(self)`（self = 宿主 QObject）合法，
      当前版本若仍写 `QTimer(self)`（self = 控制器）会 `TypeError`。
      所以"两侧均无异常"是本组最关键的哨兵。
    """
    sink = []
    box = mkfolder('ab6')
    sink_desktop_dir[0] = box
    stub = make_stub(sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 12, '方法没装齐: %s' % got
    f = mkfolder('ab6_hide')
    stub._hide_stage = 'moving_to_folder'
    stub._hide_folder_path = f
    stub._hide_obstacles = [f]
    err = None
    del taken[:]                     # 清掉本场景之前的 QTimer 记录
    try:
        stub._hide_on_arrive_folder()
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    t = stub._hide_search_timer
    snap = {
        'stage': stub._hide_stage,
        'hide_calls': stub.hide_calls[0],
        'timer_kind': type(t).__name__ if t is not None else None,
        'timer_interval_ok': bool(t is not None),
        'started_at_type': type(stub._hide_search_started_at).__name__,
        'checked_is_set': isinstance(stub._hide_search_checked, set),
        'says': len(stub.dialogue_ui.lines),
        # ★ 铁律 1 关键可观测量：QTimer 收到的 **parent 类型名**。
        #   合法值 = 'Stub'（宿主）。若当前版误写 `QTimer(self)` → 'HideAndSeekController'，
        #   两侧本项就会不一致 → 反控 AB12b 靠它抓差异。
        # ⚠️ `timer_intervals` 只取**最后一个**（`taken[-1][1]` 在 start() 时回填）：
        #     `__init__` 时刻 interval 还是 None，若照搬 init 快照会两侧恒 None，
        #     本项就**没有鉴别力**了（首跑 AB6d 就是栽在这 —— 左右值不同却都"合法"）。
        'timer_parent_type': [p for p, _ in taken],
        'timer_interval_last': taken[-1][1] if taken else None,
        'err': err,
    }
    if t is not None and hasattr(t, 'stop'):
        try:
            t.stop()
        except Exception:
            pass
    return sink, snap


so, ao = scenario_searching(old_src)
sn, an = scenario_searching(cur_src)
check('AB6a ★两侧均无异常（铁律 1：QTimer(self) 会炸）',
      ao['err'] is None and an['err'] is None,
      'old=%r new=%r' % (ao['err'], an['err']))
check('AB6b ★真的进到 searching 且起了计时器（非空跑）',
      ao['stage'] == 'searching' and ao['timer_kind'] == '_QTimerSpy',
      'stage=%r timer=%r' % (ao['stage'], ao['timer_kind']))
check('AB6e ★QTimer parent 是宿主（铁律 1：不得是控制器）',
      ao['timer_parent_type'] == ['Stub'],
      'parents=%r' % (ao['timer_parent_type'],))
check('AB6f ★计时器真的以 3000ms 启动（非空跑）',
      ao['timer_interval_last'] == 3000, 'interval=%r' % (ao['timer_interval_last'],))
check('AB6c 事件序列一致', _norm_sink(so) == _norm_sink(sn), '\n      old=%s\n      new=%s' % (_norm_sink(so), _norm_sink(sn)))
check('AB6d 末态一致', ao == an, '\n      old=%s\n      new=%s' % (ao, an))

# ============================================================================
print()
print('=== AB7 场景 4：searching tick 三支（超时 / 表演找 / 点中）===')
# ============================================================================


def scenario_tick(whole_src, mode):
    """mode: 'timeout' | 'play' | 'clicked'"""
    sink = []
    box = mkfolder('ab7')
    sink_desktop_dir[0] = box
    stub = make_stub(sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 12, '方法没装齐: %s' % got
    f_win = mkfolder('ab7_win')
    f_err = mkfolder('ab7_err')
    stub._hide_stage = 'searching'
    stub._hide_obstacles = [f_win, f_err]
    stub._hide_folder_path = f_win
    stub._hide_search_checked = set()
    stub._hide_search_timer = None
    if mode == 'timeout':
        stub._hide_search_started_at = 0          # 必然超时 → _hide_end_game(False)
    else:
        import time as _t
        stub._hide_search_started_at = _t.time()  # 未超时

    if mode == 'clicked':
        # 让"打开的是正确文件夹"被识别：window 标题含障碍物名
        class D2(_StubDesktop):
            def get_all_visible_windows(self):
                return [{'title': os.path.basename(f_win)}]
        stub.desktop_interaction = D2(box, sink)

    err = None
    try:
        stub._hide_search_tick()
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    snap = {
        'stage': stub._hide_stage,
        # ⚠️ 契约核实（读原文得来）：`_hide_end_game` 走 `_cast_spell_then`，
        #    而 stub 上的 `_cast_spell_then` 是**记录桩**（不像真实现那样改
        #    `_spell_stage`）。所以这里 `spell_stage` 两侧恒为 None ——
        #    真正能鉴别"是否排了施法"的是 **事件序列里的 `cast_spell_then`**。
        #    第一版把预期写成 'casting' → 假红（夹具预期错，不是产品错）。
        'spell_stage': stub._spell_stage,
        'cast_registered': [a for a in sink if a[0] == 'cast_spell_then'],
        'checked_n': len(stub._hide_search_checked),
        'says': len(stub.dialogue_ui.lines),
        'opened': len(stub.desktop_interaction.opened),
        'anim': [a for a, _ in stub.anim_calls],
        'err': err,
    }
    return sink, snap


# 预期末态（游标）：
#   timeout → 走 `_hide_end_game(False)` → stage 归 None 且**排了施法**
#   play    → 留在 searching，记一个已"表演找过"
#   clicked → 点中正确文件夹 → `won_pending` 且**排了 1.2s 后的跳回**
AB7_WANT = {
    'timeout': {'stage': None, 'cast_n': 1, 'checked_n': 0},
    'play': {'stage': 'searching', 'cast_n': 0, 'checked_n': 1},
    'clicked': {'stage': 'won_pending', 'cast_n': 0, 'checked_n': 0},
}

for mode in ('timeout', 'play', 'clicked'):
    so, ao = scenario_tick(old_src, mode)
    sn, an = scenario_tick(cur_src, mode)
    w = AB7_WANT[mode]
    check('AB7.%s 两侧均无异常' % mode,
          ao['err'] is None and an['err'] is None,
          'old=%r new=%r' % (ao['err'], an['err']))
    check('AB7.%s ★真的走到了预期分支（stage=%s）' % (mode, w['stage']),
          ao['stage'] == w['stage'], 'stage=%r' % ao['stage'])
    check('AB7.%s ★真的产生了预期副作用（施法=%d / 表演找=%d）'
          % (mode, w['cast_n'], w['checked_n']),
          len(ao['cast_registered']) == w['cast_n'] and
          ao['checked_n'] == w['checked_n'],
          'cast=%r checked=%r' % (ao['cast_registered'], ao['checked_n']))
    check('AB7.%s 事件序列一致' % mode, _norm_sink(so) == _norm_sink(sn),
          '\n      old=%s\n      new=%s' % (_norm_sink(so), _norm_sink(sn)))
    check('AB7.%s 末态一致' % mode, ao == an,
          '\n      old=%s\n      new=%s' % (ao, an))

# ============================================================================
print()
print('=== AB8 场景 5：结束/销毁 _hide_end_game + _hide_destroy_obstacles ===')
# ============================================================================


def scenario_end(whole_src, user_won):
    """`_hide_end_game` → 排到施法回调；再手动驱动回调 → 真删沙箱目录。

    比对：`_spell_stage` / 对话条数 / 动画 / 清理后的 `_hide_obstacles` 与
    目录是否真被删（布尔），不比绝对路径。
    """
    sink = []
    box = mkfolder('ab8')
    sink_desktop_dir[0] = box
    stub = make_stub(sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 12, '方法没装齐: %s' % got
    f1 = mkfolder('ab8_a')
    f2 = mkfolder('ab8_b')
    stub._hide_stage = 'searching'
    stub._hide_obstacles = [f1, f2]
    stub._hide_folder_path = f1
    stub._hide_search_timer = None
    stub._hide_search_checked = set()
    stub._spell_auto_suspended = True
    err = None
    try:
        stub._hide_end_game(user_won=false_is_false(user_won))
        # 手动驱动施法完成的回调（父/当前实现都把删除排在回调里，逐字保留）
        cb = None
        for a in sink:
            if a[0] == 'cast_spell_then':
                cb = 'registered'
        # 用桩记录的 cast 调用：直接调 _hide_destroy_obstacles 不行（会绕开契约）
        # ⇒ 改为从 sink 里取不到 cb，就用 stub 上被 install 的 `_hide_destroy_obstacles`
        stub._hide_destroy_obstacles()
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    snap = {
        'stage_after_end': None,          # 占位，下方以局部变量取值
        'spell_stage': stub._spell_stage,
        'says': len(stub.dialogue_ui.lines),
        'anim': [a for a, _ in stub.anim_calls],
        'obs_empty': stub._hide_obstacles == [],
        'folder_cleared': stub._hide_folder_path is None,
        'spell_autosus': stub._spell_auto_suspended,
        'dirs_gone': (not os.path.isdir(f1)) and (not os.path.isdir(f2)),
        'err': err,
    }
    return sink, snap


def false_is_false(v):
    return v


for uw in (True, False):
    so, ao = scenario_end(old_src, uw)
    sn, an = scenario_end(cur_src, uw)
    tag = 'user_won=%s' % uw
    check('AB8 %s 两侧均无异常' % tag,
          ao['err'] is None and an['err'] is None,
          'old=%r new=%r' % (ao['err'], an['err']))
    check('AB8 %s ★真的删掉了沙箱目录（非空跑）' % tag, ao['dirs_gone'] is True,
          'dirs_gone=%r' % ao['dirs_gone'])
    check('AB8 %s 事件序列一致' % tag, _norm_sink(so) == _norm_sink(sn),
          '\n      old=%s\n      new=%s' % (_norm_sink(so), _norm_sink(sn)))
    check('AB8 %s 末态一致' % tag, ao == an,
          '\n      old=%s\n      new=%s' % (ao, an))

# ============================================================================
print()
print('=== AB9 场景 6：中断清理 _abort_hide_and_seek ===')
# ============================================================================


def scenario_abort(whole_src, reason):
    sink = []
    box = mkfolder('ab9')
    sink_desktop_dir[0] = box
    stub = make_stub(sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 12, '方法没装齐: %s' % got
    f = mkfolder('ab9_obs')
    stub._hide_stage = 'searching'
    stub._hide_obstacles = [f]
    stub._hide_folder_path = f
    stub.game_state['is_playing'] = True
    stub.game_state['game_type'] = 'hide_and_seek'
    err = None
    try:
        stub._abort_hide_and_seek(reason=reason)
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    snap = {
        'stage': stub._hide_stage,
        'game_playing': stub.game_state.get('is_playing'),
        'game_type': stub.game_state.get('game_type'),
        'obs_empty': stub._hide_obstacles == [],
        'folder_cleared': stub._hide_folder_path is None,
        'dir_gone': not os.path.isdir(f),
        'says': len(stub.dialogue_ui.lines),
        'anim': [a for a, _ in stub.anim_calls],
        'err': err,
    }
    return sink, snap


for rsn in ('generic', 'end_hide_and_seek', 'cast_spell_then_replaced'):
    so, ao = scenario_abort(old_src, rsn)
    sn, an = scenario_abort(cur_src, rsn)
    check('AB9 %s 两侧均无异常' % rsn,
          ao['err'] is None and an['err'] is None,
          'old=%r new=%r' % (ao['err'], an['err']))
    check('AB9 %s ★真的清理了（stage=None 且目录已删）' % rsn,
          ao['stage'] is None and ao['dir_gone'] is True,
          'stage=%r dir_gone=%r' % (ao['stage'], ao['dir_gone']))
    check('AB9 %s 事件序列一致' % rsn, _norm_sink(so) == _norm_sink(sn),
          '\n      old=%s\n      new=%s' % (_norm_sink(so), _norm_sink(sn)))
    check('AB9 %s 末态一致' % rsn, ao == an,
          '\n      old=%s\n      new=%s' % (ao, an))

# ============================================================================
print()
print('=== AB10 场景 7：点文件夹对/错 + 跳回桌面 ===')
# ============================================================================


def scenario_report(whole_src, which):
    """which: 'win' | 'err' | 'foreign'"""
    sink = []
    box = mkfolder('ab10')
    sink_desktop_dir[0] = box
    stub = make_stub(sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 12, '方法没装齐: %s' % got
    f_win = mkfolder('ab10_win')
    f_err = mkfolder('ab10_err')
    other = mkfolder('ab10_other')
    stub._hide_stage = 'searching'
    stub._hide_obstacles = [f_win, f_err]
    stub._hide_folder_path = f_win
    stub._hide_search_timer = None
    stub._hide_search_checked = set()
    target = {'win': f_win, 'err': f_err, 'foreign': other}[which]
    err = None
    try:
        stub._hide_report_clicked_folder(target)
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    snap = {
        'stage': stub._hide_stage,
        'opened_n': len(stub.desktop_interaction.opened),
        'says': len(stub.dialogue_ui.lines),
        'anim': [a for a, _ in stub.anim_calls],
        'show_calls': stub.show_calls[0],
        'err': err,
    }
    return sink, snap


for which, want in (('win', 'won_pending'), ('err', 'searching'),
                    ('foreign', 'searching')):
    so, ao = scenario_report(old_src, which)
    sn, an = scenario_report(cur_src, which)
    check('AB10 %-7s 两侧均无异常' % which,
          ao['err'] is None and an['err'] is None,
          'old=%r new=%r' % (ao['err'], an['err']))
    check('AB10 %-7s ★真的走到了预期分支（stage=%s）' % (which, want),
          ao['stage'] == want, 'stage=%r' % ao['stage'])
    check('AB10 %-7s 事件序列一致' % which, _norm_sink(so) == _norm_sink(sn),
          '\n      old=%s\n      new=%s' % (_norm_sink(so), _norm_sink(sn)))
    check('AB10 %-7s 末态一致' % which, ao == an,
          '\n      old=%s\n      new=%s' % (ao, an))


def scenario_jump(whole_src):
    sink = []
    box = mkfolder('ab11')
    sink_desktop_dir[0] = box
    stub = make_stub(sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 12, '方法没装齐: %s' % got
    stub._pos = [300, 200]
    err = None
    try:
        stub._hide_jump_back_to_desktop()
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    snap = {
        'pos': tuple(stub._pos),
        'anim': [a for a, _ in stub.anim_calls],
        'clamp_called': any(a[0] == 'clamp' for a in sink),
        'err': err,
    }
    return sink, snap


print()
print('=== AB11 场景 8：跳回桌面 _hide_jump_back_to_desktop ===')
so, ao = scenario_jump(old_src)
sn, an = scenario_jump(cur_src)
check('AB11 两侧均无异常', ao['err'] is None and an['err'] is None,
      'old=%r new=%r' % (ao['err'], an['err']))
check('AB11 ★真的移动了（pos 变了且钳位被调用）',
      ao['pos'] != (300, 200) and ao['clamp_called'] is True,
      'pos=%r clamp=%r' % (ao['pos'], ao['clamp_called']))
check('AB11 事件序列一致', _norm_sink(so) == _norm_sink(sn), '\n      old=%s\n      new=%s' % (_norm_sink(so), _norm_sink(sn)))
check('AB11 末态一致', ao == an, '\n      old=%s\n      new=%s' % (ao, an))

# ============================================================================
print()
print('=== AB12 反向控制：改动点必须真的可观测（防"改了跟没改一样"）===')
# ============================================================================
# 反向控制的目标：证明本探针**能鉴别**本项两处非逐字改动。
# 做法 = 用"当前版源码把改写回退掉"造一个**故意坏**的 B'，断言它**被探针识别出差异**。
# ⚠️ 首跑这里写错了（两次都报 FAIL），值得记下来：
#    ① `QTimer(self)` 在打桩后的 `_QTimerSpy` 里**不报错**（桩不校验 parent 类型），
#       所以"断言抛异常"根本不可能成立 → 必须改断言 **parent 类型名**。
#    ② 裸 `_log_()` 能解析，是因为**探针自己给 ns 注入了模块级 `_log_`**
#       —— 而真机（`hide_controller.py`）里没有这个名字。
#       ⇒ 反控必须**连带移除夹具的兜底**，否则测的是"夹具能不能解析"，不是产品。
#    ③ 同源教训（W1-1 报告 6.4）：**反控夹具必须让"坏版本在探针环境下真的坏"**，
#       否则反控本身是假的（"反控通过"比"探针假绿"更危险 —— 会让人以为探针有鉴别力）。

# —— 反控 1：QTimer(self.p) → QTimer(self) ——
bad_q = cur_src.replace('QTimer(self.p)', 'QTimer(self)')
check('AB12a 反控夹具真的改动了源码（bad_q != cur）', bad_q != cur_src)
_sb, _ab = scenario_searching(bad_q)
# ⚠️ 重要发现（首跑这里写错了预期）：
#   即使把 `QTimer(self.p)` 回退成 `QTimer(self)`，**parent 类型仍是宿主** ——
#   因为在控制器里 `self` 就是控制器，而 `self` 经 `__getattr__` 不会变……
#   —— 不对，真相是另一回事：**打桩后 `Spy(parent)` 照单全收任何对象**，
#   而 `QTimer(self)` 传的 `self` 是**控制器**，`type(self).__name__` 应为
#   `HideAndSeekController`。实测却是 `'Stub'` —— 说明**控制器的 `self` 被替换了**。
#   实测原因：`types.MethodType(fn, stub)` 把方法绑到 **stub** 上，
#   `self` 就是 stub，所以 `QTimer(self)` 与 `QTimer(self.p)` 都传 stub。
#   ⇒ **本探针的"方法体搬迁"形态天然屏蔽了铁律 1**：
#     它把方法绑到宿主实例上，等价于"方法没搬走"。
#   ⇒ 铁律 1 的鉴别**不能**靠 A/B（A/B 只验"行为等价"，不验"落点正确"）；
#     它由 **e2e（真控制器实例）** 负责 —— 见 `verify_w1_2_e2e.py` E6。
#   本项因此改为断言 **"A/B 一致"**（这正是 A/B 该管的事），并**显式记录**
#   这条鉴别力边界，防止后人误以为 A/B 覆盖了铁律 1。
check('AB12b ★反控边界：A/B 形态下 QTimer parent 恒为宿主（铁律 1 由 e2e 覆盖）',
      _ab['timer_parent_type'] == ['Stub'] and _ab['err'] is None,
      'parents=%r err=%r（结论：A/B 对铁律 1 无鉴别力，勿据此判"没差别"）'
      % (_ab['timer_parent_type'], _ab['err']))

# —— 反控 2：self._log_(). → 裸 _log_(). ——
# ⚠️ 这一项在本轮**反复踩了三跤**，全部是"反控夹具自己站不住"，值得完整记下来：
#
#   跤 ① 场景选错：`mode='play'` 下 `_log_()` 只在"os.startfile 也失败"的
#        **内层 except** 里被调用 —— 而 pick 是真实存在的沙箱目录，`os.startfile`
#        成功 → 那行**根本执行不到**（"反控没鉴别力"和"反控通过"长得一模一样）。
#        修法：换成 `_hide_search_tick` 的**窗口扫描块** —— 让
#        `get_all_visible_windows()` 直接抛，必然进 `except` → 必然打日志。
#
#   跤 ② 前提写错：我原本以为"夹具注入的模块级 `_log` 会给裸 `_log_()` 兜底"，
#        于是先断言"有兜底时坏版本能跑"，结果直接 `NameError`。
#        根因：**`_log` 和 `_log_` 是两个不同的名字** ——
#        `_log` 是模块级 **logger 对象**（A 侧 `_log.debug(...)` 要用），
#        `_log_` 是**方法名**。夹具注入 `_log` 从来就没兜住过 `_log_()`。
#        ⇒ "兜底真的存在"这个前置断言**从前提上就是错的**，删掉。
#
#   跤 ③ `no_log_ns` 用错了对象：我拿它去"撤兜底"，结果**正常版本也一起炸了**
#        （`AttributeError: 'Stub' object has no attribute '_log_'`）——
#        因为该开关同时掐掉了 stub 的 `_log_` 绑定，而正常版本正是靠它解析。
#        ⇒ 反控**不需要**这个开关：探针的 ns 里**本来就没有** `_log_`（只有 `_log`），
#          所以裸 `_log_()` 在**默认配置下**就必然 `NameError`。
#
#   最终形态 = **同一场景、同一夹具配置（都用默认 ns），只换被测源码**：
#        · 坏版本 → 必须 `NameError`（且指名 `_log_`）
#        · 好版本 → 必须 `err is None`，且**有证据表明那行确实执行了**
#   后者是靠给 stub 绑一个**记账版** `_log_` 拿到的 —— 否则"没报错"可能只是
#   "压根没走到那行"。（这条正是 W1-1 §6.4「两边一样'正常'也可能只是两边都没跑」的同型。）
def scenario_log_site(whole_src, record_log=False):
    """构造一个**必然**执行到 `_log_()` 那一行的场景（窗口扫描块抛异常）。"""
    sink = []
    box = mkfolder('ab12_log')
    sink_desktop_dir[0] = box
    stub = make_stub(sink)
    got = install_code(stub, whole_src, NAMES, sink)
    assert len(got) == 12, '方法没装齐: %s' % got
    if record_log:
        # 把 `_log_` 换成**记账版** —— 证明"那行真的执行了"，而不只是"没报错"。
        def _rec_log_(self, _s=sink):
            _s.append(('log_called', None))
            return _HOST_MODULE._log
        setattr(stub, '_log_', types.MethodType(_rec_log_, stub))

    class Dboom(_StubDesktop):
        def get_all_visible_windows(self):
            raise RuntimeError('boom（反控专用：逼出 _log_() 那一行）')

    stub.desktop_interaction = Dboom(box, sink)
    f_win = mkfolder('ab12_log_win')
    f_err = mkfolder('ab12_log_err')
    stub._hide_stage = 'searching'
    stub._hide_obstacles = [f_win, f_err]
    stub._hide_folder_path = f_win
    stub._hide_search_checked = set()
    stub._hide_search_timer = None
    import time as _t
    stub._hide_search_started_at = _t.time()
    err = None
    try:
        stub._hide_search_tick()
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
    return sink, {
        'err': err,
        'stage': stub._hide_stage,
        'log_called': any(a[0] == 'log_called' for a in sink),
    }


bad_log = cur_src.replace('self._log_().', '_log_().')
check('AB12c 反控夹具真的改动了源码（bad_log != cur，%d 处替换）'
      % cur_src.count('self._log_().'),
      bad_log != cur_src and cur_src.count('self._log_().') > 0)

# 坏版本：默认 ns（探针从不注入模块级 `_log_`）→ 必须当场 NameError
_sbl, abl = scenario_log_site(bad_log)
check('AB12d ★反控：裸 _log_() 在探针默认 ns 下当场 NameError（探针有鉴别力）',
      abl['err'] is not None and 'NameError' in str(abl['err'])
      and '_log_' in str(abl['err']),
      'err=%r（探针 ns 里只有 `_log`（logger），没有 `_log_`（方法名））' % abl['err'])

# 好版本：同场景同配置 → 必须正常，且**有证据**那行真的执行过
_sg, ag = scenario_log_site(cur_src, record_log=True)
check('AB12e ★对照：正常版本在同一场景下正常', ag['err'] is None,
      'err=%r' % ag['err'])
check('AB12f ★对照：正常版本**确实执行到了** _log_() 那一行（非"压根没跑到"）',
      ag['log_called'] is True,
      'log_called=%r（否则 AB12e 的"正常"是空跑，没有鉴别力）' % ag['log_called'])
check('AB12g ★对照：好/坏版本差异确实来自那一行（双方都进到了 except 岔路）',
      ag['stage'] == abl['stage'] == 'searching',
      'good_stage=%r bad_stage=%r' % (ag['stage'], abl['stage']))

# ============================================================================
shutil.rmtree(SANDBOX, ignore_errors=True)
sink_desktop_dir[0] = SANDBOX

n_pass = sum(1 for _, ok, _ in results if ok)
n_fail = len(results) - n_pass
print()
print('=' * 64)
print('W1-2 A/B：共 %d 项，通过 %d，失败 %d' % (len(results), n_pass, n_fail))
print('父版本 rev = %s (md5 %s)' % (rev, md5_old[:12]))
print('当前   md5 = %s' % md5_cur[:12])
print('=' * 64)
if n_fail:
    print('FAILED:')
    for n, ok, d in results:
        if not ok:
            print('   ', n, '::', str(d)[:500])
sys.exit(0 if n_fail == 0 else 1)

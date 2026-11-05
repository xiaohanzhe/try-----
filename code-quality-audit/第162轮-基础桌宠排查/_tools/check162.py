# -*- coding: utf-8 -*-
u"""第162轮回归锁：**基础桌宠的四条"看得见"**。

## 为什么有这一轮

用户说「我记得咱的基础桌宠还有一些问题，你抽空看看」，没列举。第162轮先量了一遍
（`report162.md`），四条是真偏差，其余正常（崩溃 0 / 拖拽 1:1 / 甩飞可回收 /
右键 9 项全接线 / 透明区穿透 / 退出清理）。四条各自的原话与数据：

| # | 现象 | 本轮实测（改前） |
|---|------|------------------|
| ① | 换动画时人物上下沉浮（按**窗口中心**缩放） | `100x100 → 229x156` 脚底 **+28px**；`63x133 ↔ 229x156` 每次 **±11~13px**，30 秒 33 次 |
| ② | 落到最底会沉到任务栏后面（"地面"用**整屏底**，含任务栏 72px） | 同一条甩飞路径：改前 bottom=**1599**、改后 **1528**（= 任务栏上沿） |
| ③ | 记忆写盘失败**不回落**，只打一条 WARNING | E 盘实测 `OSError(22,'函数不正确')`；`save_memory` 异常分支只 `_log.warning` |
| ④ | 托盘被 Win11 折叠时没有第二条退出路径 | 右键菜单 9 项里没有"退出" |

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | `anchored_resize_xy` 的**行为**：水平保中心、垂直保底边；负坐标也对；★ 负控制：老口径（保中心）算出来的数**必须不同** |
| B | 接线：两处尺寸变化**都**走这个纯函数；老变量 `old_center_y` 在 AST 上**一处都不许有**；拖拽补偿同步改成新口径 |
| C | 地面：`_desktop_ground_y` = 工作区底、失败才回落整屏底；三处落点都改用它、**都不许**再用 `_desktop_floor_y`；甩飞那条**逐帧重算**（不许躲在"只算一次"的缓存里） |
| D | 记忆回落：主路径写不进去 ⇒ 换中转站写成功且 `memory_file` 切过去；两条都写不进去 ⇒ 返 False 不抛；★ 负控制：主路径能写时**不许**切 |
| E | 右键菜单多出"退出 Ralsei"，且走**同一条**清理路径（`_quit_from_tray`） |
| F | 自检：判据名字面量 · 只用 `check()` · 产品文件无 BOM 全 LF · 零外部盘 |

★ 为什么 ①③ 用**纯函数/直接调**而不是"起窗口看它跳不跳"：
  起窗口那条路每一帧都掺着随机漫游，量出来的 Δ 里混着走路位移（第162轮实测：
  误把"保中心"的 11px 与走路 3px 混在一起）。纯函数喂数字，判据才只考一件事。
"""
import ast
import io
import os
import re
import sys
import shutil
import tempfile

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
MEM = os.path.join(PET, 'modules', 'memory_system.py')

_n_pass = 0
_n_fail = 0
_failed = []


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def mark(title):
    print('---- %s ----' % (title,))


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def _blank_comments(src):
    """把注释换成等长空白（保留行号），判"源码里有某写法"时用它，别让注释误报。"""
    out = []
    in_str = None
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        if in_str:
            out.append(ch)
            if ch == '\\' and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = ch
            out.append(ch)
            i += 1
            continue
        if ch == '#':
            while i < n and src[i] != '\n':
                out.append(' ')
                i += 1
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


SRC = _read(MAIN)
SRC_NC = _blank_comments(SRC)
TREE = ast.parse(SRC)


def _func(name, tree=None):
    """按名字找函数 —— **包括类里的方法**（`ast.walk` 而不是只看模块体）。"""
    for node in ast.walk(tree or TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


# ================================================ A. 锚点纯函数
mark(u'A. 尺寸变化：水平保中心、垂直保底边')

# 先把被测函数取出来（模块级纯函数 —— 不起 Qt、不建窗口）
sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, os.path.join(PET, 'modules'))
import main as MAIN_MOD  # noqa: E402

RESIZE = getattr(MAIN_MOD, 'anchored_resize_xy', None)
check(u'A1 `anchored_resize_xy` 是模块级函数（能脱离窗口单测）',
      callable(RESIZE))

if callable(RESIZE):
    # A2 水平：100 宽、x=100 的窗口放大到 200 宽 ⇒ 左边界左移 50（中心 150 不动）
    x2, y2 = RESIZE(100, 300, 100, 100, 200, 100)
    check(u'A2 变宽时**中心**不动（水平）', x2 == 50 and (x2 + 100) == 150,
          u'x=%r（中心=%r）' % (x2, x2 + 100))
    # A3 垂直：h 100 → 200 且 y=300（底边 400）⇒ 新 y=200，底边仍是 400
    x3, y3 = RESIZE(100, 300, 100, 100, 100, 200)
    check(u'A3 变高时**底边（脚底）**不动', y3 == 200 and (y3 + 200) == 400,
          u'y=%r（底边=%r）' % (y3, y3 + 200))
    # A4 本轮真实的那一对：133 ↔ 156（差 23）⇒ 底边必须一分不动
    _, ya = RESIZE(2400, 1395, 63, 133, 229, 156)
    _, yb = RESIZE(2400, 1372, 229, 156, 63, 133)
    check(u'A4 真实尺寸对 63x133 ↔ 229x156：来回换，底边都保持',
          ya + 156 == 1395 + 133 and yb + 133 == 1372 + 156,
          u'去=%r 回=%r' % (ya + 156, yb + 133))
    # A5 副屏负坐标（多屏在左/上时 x,y 为负）
    x5, y5 = RESIZE(-800, -300, 60, 100, 120, 160)
    check(u'A5 副屏负坐标同样成立', x5 == -830 and (y5 + 160) == -200,
          u'(%r,%r) 底边=%r' % (x5, y5, y5 + 160))

    # A6 ★ 负控制：老口径（保中心）算出来的**必须不同** —— 先证明判据有鉴别力。
    #    老写法：new_y = (y + old_h//2) - new_h//2
    old_y = (1395 + 133 // 2) - 156 // 2
    check(u'A6 负控制：老口径（保中心）给出的 y 与新口径不同（判据有鉴别力）',
          old_y != ya, u'老=%r 新=%r' % (old_y, ya))

# ================================================ B. 接线
mark(u'B. 两处尺寸变化都走纯函数，老写法一处不留')

_fn_resize = _func('anchored_resize_xy')
check(u'B1 `anchored_resize_xy` 定义在模块级（不在类里）', _fn_resize is not None)

_n_calls = len([n for n in ast.walk(TREE)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == 'anchored_resize_xy'])
check(u'B2 两处尺寸变化都调用它（恰好 2 处）', _n_calls == 2, u'n=%d' % (_n_calls,))

_names = set()
for n in ast.walk(TREE):
    if isinstance(n, ast.Name):
        _names.add(n.id)
    elif isinstance(n, ast.Attribute):
        _names.add(n.attr)
check(u'B3 老变量 `old_center_y` 一处都不剩（AST 查名字，不扫字符串）',
      'old_center_y' not in _names)

# 拖拽补偿：改前是 `+ target_height // 2 - self.height() // 2`，
# 保底边之后必须换成 `+ target_height - self.height()`，否则拖拽中会"回拽"。
_old_comp = len(re.findall(r'target_height\s*//\s*2\s*-\s*self\.height\(\)\s*//\s*2', SRC_NC))
_new_comp = len(re.findall(r'\+\s*target_height\s*-\s*self\.height\(\)', SRC_NC))
check(u'B4 拖拽补偿同步改成"整高差"（旧写法 0 处、新写法 2 处）',
      _old_comp == 0 and _new_comp == 2, u'旧=%d 新=%d' % (_old_comp, _new_comp))

# ================================================ C. 地面
mark(u'C. 落到桌面 = 任务栏上沿，不是整屏底')


class _GroundHost(object):
    """只有两个量的小宿主：工作区底 / 整屏底。用来单独考 `_desktop_ground_y`。"""

    def __init__(self, work_top=None, floor=None, boom=False):
        self._work = work_top
        self._floor = floor
        self._boom = boom

    def _taskbar_top_y(self):
        if self._boom:
            raise RuntimeError('工作区取不到')
        return self._work

    def _desktop_floor_y(self):
        return self._floor


GROUND = getattr(MAIN_MOD.RalseiPet, '_desktop_ground_y', None)
check(u'C1 `RalseiPet._desktop_ground_y` 在位', callable(GROUND))

if callable(GROUND):
    v = GROUND(_GroundHost(work_top=1372, floor=1444))
    check(u'C2 取的是**工作区底**（1372），不是整屏底（1444）', v == 1372, u'v=%r' % (v,))
    # ★ 负控制：把工作区底设成与整屏底不同，两者必须区分得开
    v2 = GROUND(_GroundHost(work_top=1000, floor=1444))
    check(u'C3 负控制：换一个工作区底，返回值跟着变（不是恒等于某个常量）',
          v2 == 1000 and v2 != v, u'v2=%r' % (v2,))
    v3 = GROUND(_GroundHost(boom=True, floor=1444))
    check(u'C4 工作区取不到时**回落整屏底**且不抛', v3 == 1444, u'v3=%r' % (v3,))

# 三处落点：甩飞落点 / 重力落地 / 弹跳触地 ⇒ 都必须走 `_desktop_ground_y`
_ground_calls = len([n for n in ast.walk(TREE)
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and n.func.attr == '_desktop_ground_y'])

# `_desktop_floor_y` 只允许剩下**两处回落**：`_desktop_ground_y` 自己、
# 以及 `_taskbar_top_y` 的兜底。落点函数里一处都不许有。
_owner = {}
for _fn in [x for x in ast.walk(TREE) if isinstance(x, ast.FunctionDef)]:
    for _sub in ast.walk(_fn):
        _owner.setdefault(id(_sub), _fn.name)
_floor_owners = []
for n in ast.walk(TREE):
    if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == '_desktop_floor_y'):
        _floor_owners.append(_owner.get(id(n), '?'))
check(u'C5 三处落点都调 `_desktop_ground_y`', _ground_calls >= 3, u'n=%d' % (_ground_calls,))
check(u'C6 `_desktop_floor_y` 只剩两处**回落**（`_desktop_ground_y` / `_taskbar_top_y`），落点里没有',
      sorted(_floor_owners) == ['_desktop_ground_y', '_taskbar_top_y'],
      u'owners=%r' % (_floor_owners,))

# 甩飞那条必须**逐帧重算**：判据 = `_fall_land_y = self._desktop_ground_y()` 必须落在
# `if getattr(self, '_is_thrown', False):` 体内，而**不在** `if not hasattr(..., '_fall_land_y')` 体内。
_thrown_ok = False
_cache_guarded = False
_parent = {}
for _node in ast.walk(TREE):
    for _child in ast.iter_child_nodes(_node):
        _parent[id(_child)] = _node
for _node in ast.walk(TREE):
    if not isinstance(_node, ast.If):
        continue
    _test = ast.dump(_node.test)
    if "'_is_thrown'" in _test:
        for _st in ast.walk(_node):
            if (isinstance(_st, ast.Assign)
                    and any(isinstance(t, ast.Attribute) and t.attr == '_fall_land_y'
                            for t in _st.targets)
                    and '_desktop_ground_y' in ast.dump(_st)):
                _thrown_ok = True
    if "'_fall_land_y'" in _test and 'hasattr' in ast.dump(_node.test):
        for _st in ast.walk(_node):
            if (isinstance(_st, ast.Assign)
                    and any(isinstance(t, ast.Attribute) and t.attr == '_fall_land_y'
                            for t in _st.targets)
                    and '_desktop_ground_y' in ast.dump(_st)):
                _cache_guarded = True
check(u'C7 甩飞落点**逐帧重算**（在 `_is_thrown` 分支里，不在"只算一次"的缓存里）',
      _thrown_ok and not _cache_guarded,
      u'thrown=%r cached=%r' % (_thrown_ok, _cache_guarded))

# ================================================ D. 记忆写盘回落
mark(u'D. 记忆：主落点写不进去就换中转站，不再静默丢')

# ★★ 临时根用**固定名**，不用 `mkdtemp` 的随机后缀：产品在写失败时会把异常文本
#   （含完整路径）打进 WARNING，随机目录名 ⇒ 每次跑输出都不同 ⇒ 无故 DIFF。
#   这正是第138/146轮那条「判据输出不许含时相量」的同一个坑，本轮自己又踩了一次。
_TMP = os.path.join(tempfile.gettempdir(), 'check162_work')
shutil.rmtree(_TMP, ignore_errors=True)
os.makedirs(_TMP, exist_ok=True)
_OLD_ENV = os.environ.get('RALSEI_DATA_DIR')
os.environ['RALSEI_DATA_DIR'] = _TMP
try:
    # ★★★ 必须**先**把设备探测打掉：`MemorySystem.__init__` 自己会调
    #   `memory_store.default_memory_dir()`，那里设备优先 ⇒ 在真机上会直接写
    #   用户的金库（第162轮实测：本套件第一版把 `E:\RalseiMemory\memory.json`
    #   从 39KB 写成了 72KB）。回归不许碰外部盘，这条是硬闸。
    import memory_store as _MSTORE
    _MSTORE.find_device_dir = lambda create=True: None
    import memory_system as MS  # noqa: E402

    def _fresh():
        m = MS.MemorySystem(None)
        m.memory_file = os.path.join(_TMP, 'main', 'memory.json')
        m.memory_dir = os.path.dirname(m.memory_file)
        m._on_device = True
        return m

    # D1 正常写
    m1 = _fresh()
    ok1 = m1.save_memory()
    check(u'D1 主落点可写时：写成功、文件在、路径不变',
          ok1 is True and os.path.exists(m1.memory_file)
          and m1.memory_file.endswith(os.path.join('main', 'memory.json')),
          u'ret=%r tail=%r' % (ok1, os.path.relpath(m1.memory_file, _TMP)))

    # D2 主落点不可写：把 `main` 造成一个**文件**（makedirs 必失败）
    m2 = _fresh()
    _blocker = os.path.join(_TMP, 'blocked')
    with io.open(_blocker, 'w', encoding='utf-8') as _f:
        _f.write(u'占位')
    m2.memory_file = os.path.join(_blocker, 'memory.json')
    m2.memory_dir = os.path.dirname(m2.memory_file)
    ok2 = m2.save_memory()
    _alt = os.path.join(_TMP, 'memory.json')
    check(u'D2 主落点写不进去 ⇒ 回落到中转站并写成',
          ok2 is True and os.path.exists(_alt),
          u'ret=%r alt_exists=%r' % (ok2, os.path.exists(_alt)))
    check(u'D3 回落之后 `memory_file` 真的**切过去**了（否则下次又从坏盘读、又忘）',
          os.path.abspath(m2.memory_file) == os.path.abspath(_alt) and m2._on_device is False,
          u'rel=%r on_device=%r' % (os.path.relpath(m2.memory_file, _TMP), m2._on_device))

    # D4 负控制：主落点能写时**不许**切路径（防止"总是回落"把金库旁路掉）
    m4 = _fresh()
    m4.save_memory()
    check(u'D4 负控制：主落点正常时不切路径',
          os.path.abspath(m4.memory_file).startswith(os.path.abspath(os.path.join(_TMP, 'main'))),
          u'rel=%r' % (os.path.relpath(m4.memory_file, _TMP),))

    # D5 两条都写不进去 ⇒ 返 False、不抛（唯一出口是"如实报告没写成"）
    m5 = _fresh()
    _bad = os.path.join(_TMP, 'badbase')
    with io.open(_bad, 'w', encoding='utf-8') as _f:
        _f.write(u'占位')
    m5.memory_file = os.path.join(_blocker, 'memory.json')
    m5.memory_dir = os.path.dirname(m5.memory_file)
    os.environ['RALSEI_DATA_DIR'] = _bad
    try:
        ok5 = m5.save_memory()
    except Exception as _e:
        ok5 = 'raised:%r' % (_e,)
    finally:
        os.environ['RALSEI_DATA_DIR'] = _TMP
    check(u'D5 两条路都写不进去 ⇒ 返回 False 且不抛', ok5 is False, u'ret=%r' % (ok5,))
finally:
    if _OLD_ENV is None:
        os.environ.pop('RALSEI_DATA_DIR', None)
    else:
        os.environ['RALSEI_DATA_DIR'] = _OLD_ENV
    shutil.rmtree(_TMP, ignore_errors=True)

# ================================================ E. 右键菜单"退出"
mark(u'E. 右键菜单多出"退出"，且复用同一条清理路径')

_menu = _func('show_interaction_menu')
_menu_src = ast.dump(_menu) if _menu else ''
# ★ 只认**用户看得见的那个字面量**：第一版写成 `'退出 Ralsei' in dump or 'quit_action' in dump`，
#   把菜单项改名成"走啦"照样绿（"提到某名字=恒真"，第108/138轮同族）。
check(u'E1 菜单里有 "退出 Ralsei" 这个**显示文案**',
      u'退出 Ralsei' in (_menu_src or ''))
check(u'E2 它连到 `_quit_from_tray`（不是另写一份退出逻辑）',
      '_quit_from_tray' in (_menu_src or ''))
_quit = _func('_quit_from_tray')
_quit_dump = ast.dump(_quit) if _quit else ''
check(u'E3 `_quit_from_tray` 里真的先 `cleanup_on_exit()` 再 quit',
      'cleanup_on_exit' in _quit_dump and 'quit' in _quit_dump)

# ================================================ F. 自检
mark(u'F. 自检')
_SELF = _read(os.path.abspath(__file__))
_descs = re.findall(r"check\(\s*u?'([^']*)'", _SELF)
check(u'F1 判据名都是**非空字面量**（不许用计数拼进判据名）',
      len(_descs) >= 16 and all(d.strip() for d in _descs), u'n=%d' % (len(_descs),))
_ok_calls = [n for n in ast.walk(ast.parse(_SELF))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'ok']
check(u'F2 只用 `check()` 不用 `ok()`（两套 harness 混用会漏查恒真）',
      not _ok_calls, u'ok() 调用 %d 处' % (len(_ok_calls),))
for _p in (MAIN, MEM):
    _raw = open(_p, 'rb').read()
    _bare_lf = _raw.count(b'\n') - _raw.count(b'\r\n')
    # ★ 这两个文件在仓库里本来就是 CRLF（第162轮 `probe162_live` 实测
    #   main.py LF=0 / CRLF=18955）。判据不该要求"全 LF"——那是把**别的文件**的
    #   口径搬过来（第160轮「判据别绑写法」同族）。真正要守的是：
    #   无 BOM + 行尾**统一**（混行才是编辑器乱改的证据）。
    check(u'F3 %s 无 BOM、行尾统一（不许混行）' % os.path.basename(_p),
          not _raw.startswith(b'\xef\xbb\xbf') and not (_bare_lf and _raw.count(b'\r\n')),
          u'BOM=%r 裸LF=%d' % (_raw.startswith(b'\xef\xbb\xbf'), _bare_lf))
check(u'F4 判据零外部盘（不许依赖 E:/D:，回归必须能在干净机器上跑）',
      not re.search(r"['\"](?:E|D):[\\/]", _SELF))

print(u'\n合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
sys.exit(1 if _n_fail else 0)

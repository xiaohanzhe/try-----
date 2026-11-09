# -*- coding: utf-8 -*-
u"""第179轮判据：**"站在谁上面"优先于 Y 排序**（修第178轮的自伤）。

背景（事实链，不是推断）
----------------------
第178轮把 z 序锚点改成"按屏幕 Y 排序"：窗口**下沿 > 宠物脚底** ⇒ 窗口在前 ⇒ 挡住宠物。

漏掉的一格：**它自己站着的那块板**。
`get_current_floor` 判"站在哪块楼板"用的是 `floor_visible_contains(pos)`
= `rect.contains(宠物的点)` ⇒ 宠物**站在窗口矩形内部**
（`main.py` 的落点也被夹在 `window_rect.top()+标题栏+20 … bottom()-h-20`）。
既然站在矩形**内部**，那块窗口的"下沿"必然**大于**宠物脚底
⇒ 172/178 那套纯 Y 规则会把宠物插到**自己所站的窗口之后** ⇒ 被该窗口盖住、**直接看不见**。

复现（本轮实测，见报告 §2）：
    A = rect(100,500,800,400)，宠物 pos.y=700、身高 100 ⇒ foot=800
    pick_insert_after_by_foot_y(800, [A]) -> (0xAA, {'reason':'behind','bottom':900})
    ⇒ 锚点 0xAA 正是它自己站的板 ⇒ 宠物被藏在 A 后面。

所以本轮把优先级定死：
  ① **站在窗口楼板上 ⇒ 无条件插到那块窗口之前**（= 第13轮的老口径，可见性不可违反）；
  ② 站在桌面（或所站窗口刚好被关掉）⇒ 才按屏幕 Y 排序。
  "走到窗口背后即被挡住"真正发生的场景本来就是**桌面**那一条。

★★ 判据的重心：要能区分"两种口径"而不是"函数被调用了"
------------------------------------------------------
同一个 `foot_y`、同一份楼层表，只改 `floor` 参数：
    · 站在桌面    → 锚点是**最近的前挡者**（更靠下的那块板）；
    · 站在 A 上   → 锚点是 **A**。
两者**必须不同**（`D1`），否则说明"站在谁上面"根本没参与判定 —— 这正是 178 的病。

不构造真机、零外部盘、零网络；`win32gui` 打桩，用完还原。

用法：python check179.py
"""
import ast
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(REPO, 'ralsei_pet')
FM_P = os.path.join(PKG, 'modules', 'floor_manager.py')
MAIN_P = os.path.join(PKG, 'src', 'main.py')
SELF = os.path.abspath(__file__)

for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PyQt5.QtCore import QRect                     # noqa: E402
from modules import floor_manager as FM            # noqa: E402

CHECK_FLOOR = 20

_n = {'p': 0, 'f': 0}
_bad = []


def check(desc, cond, extra=u''):
    if cond:
        _n['p'] += 1
        print('[PASS] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        _n['f'] += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))


def head(t):
    print('')
    print('=' * 70)
    print(t)
    print('=' * 70)


def _tree(p):
    return ast.parse(io.open(p, encoding='utf-8').read())


def _func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


FM_TREE = _tree(FM_P)
MAIN_TREE = _tree(MAIN_P)

#: A = 所站楼板（rect y 500..900）；B = 另一块窗口，下沿 850（比 A 更"近"）
A_HWND = 0xAA
B_HWND = 0xBB
RECT_A = QRect(100, 500, 800, 400)      # 下沿 900
RECT_B = QRect(900, 500, 300, 350)      # 下沿 850
FOOT = 800                              # 宠物脚底（站在 A 里：pos.y=700 + 身高 100）


class _W32(object):
    u"""`win32gui` 最小替身：只认声明的有效句柄，记下 SetWindowPos 的实参。"""

    def __init__(self, valid=()):
        self.valid = set(valid)
        self.sp = []

    def IsWindow(self, h):
        return h in self.valid

    def SetWindowPos(self, hwnd, insert, x, y, cx, cy, flags):
        self.sp.append((hwnd, insert))
        return True

    def FindWindow(self, *a):
        return 0

    def FindWindowEx(self, *a):
        return 0

    def EnumWindows(self, *a):
        return True

    def IsWindowVisible(self, h):
        return False


def _mk_fm():
    fm = FM.FloorManager()
    fm.underlying_windows = [
        {'hwnd': A_HWND, 'rect': RECT_A, 'z_order': 1},
        {'hwnd': B_HWND, 'rect': RECT_B, 'z_order': 2},
    ]
    fm.floors = [
        {'type': 'window', 'window': {'hwnd': A_HWND}, 'rect': RECT_A,
         'visible_rects': [RECT_A], 'visible_area': RECT_A.width() * RECT_A.height(),
         'z_order': 1, 'platform_height': 10, 'window_hwnd': A_HWND},
        {'type': 'window', 'window': {'hwnd': B_HWND}, 'rect': RECT_B,
         'visible_rects': [RECT_B], 'visible_area': RECT_B.width() * RECT_B.height(),
         'z_order': 2, 'platform_height': 5, 'window_hwnd': B_HWND},
    ]
    return fm


DESKTOP = {'type': 'desktop'}
ON_A = {'type': 'window', 'window_hwnd': A_HWND}

_real = FM.win32gui
#: ★ 宠物自己的句柄（0x1234/0x2345）也必须在 valid 里 —— `set_window_behind`
#:   第一步就校验 target，不合法直接 return False（第一版漏了 ⇒ C0/C1/C2 假红）。
_stub = _W32(valid=(A_HWND, B_HWND, 0x1234, 0x2345))
FM.win32gui = _stub
try:
    # -------------------------------------------------------------------
    head(u'A 段  三条路径（站在楼板 / 站在桌面 / 楼板被关掉）')

    _fm = _mk_fm()
    _a_on = _fm.get_insert_after_hwnd(ON_A, foot_y=FOOT)
    check(u'A1 ★★★ 站在 A 上（A 下沿 900 > 脚底 800）⇒ 锚点必须是 **A**'
          u'（第178轮这里是"插到 A 之后"= 被自己站的板挡住）',
          _a_on == A_HWND, u'anchor=%r reason=%r' % (_a_on, _fm._last_z_pick.get('reason')))

    check(u'A2 同一脚底、同一份楼层表，**只改 floor**：站桌面 ⇒ 取最近前挡者 B'
          u'（B 下沿 850 < A 的 900）',
          _fm.get_insert_after_hwnd(DESKTOP, foot_y=FOOT) == B_HWND,
          u'anchor=%r reason=%r' % (_fm.get_insert_after_hwnd(DESKTOP, foot_y=FOOT),
                                    _fm._last_z_pick.get('reason')))

    check(u'A3 ★★ 两种路径的锚点**必须不同**（都等于 A 的话，说明"站在谁上面"没参与判定 '
          u'⇒ 就是 178 的病）',
          _a_on != _fm.get_insert_after_hwnd(DESKTOP, foot_y=FOOT),
          u'站A=%r 站桌面=%r' % (_a_on, _fm.get_insert_after_hwnd(DESKTOP, foot_y=FOOT)))

    check(u'A4 站在桌面上、脚底低过所有窗口下沿 ⇒ `HWND_TOP`（宠物最近，画在最前）',
          _fm.get_insert_after_hwnd(DESKTOP, foot_y=950) == FM.HWND_TOP,
          u'anchor=%r' % (_fm.get_insert_after_hwnd(DESKTOP, foot_y=950),))

    #: 所站窗口的句柄已失效（用户刚好把它关了）
    _fm2 = _mk_fm()
    _dead = {'type': 'window', 'window_hwnd': 0xDEAD}
    _a_dead = _fm2.get_insert_after_hwnd(_dead, foot_y=FOOT)
    check(u'A5 所站窗口句柄失效 ⇒ **不许**把野句柄交出去，改走 Y 规则',
          _a_dead != 0xDEAD and _a_dead == B_HWND,
          u'anchor=%r reason=%r' % (_a_dead, _fm2._last_z_pick.get('reason')))

    _fm3 = _mk_fm()
    check(u'A6 `floor=None` + 给了 `foot_y` ⇒ 也走 Y 规则（不是一路回退到 WorkerW）',
          _fm3.get_insert_after_hwnd(None, foot_y=FOOT) == B_HWND,
          u'anchor=%r reason=%r' % (_fm3.get_insert_after_hwnd(None, foot_y=FOOT),
                                    _fm3._last_z_pick.get('reason')))

    # -------------------------------------------------------------------
    head(u'B 段  顺序与向后兼容（AST）')

    _gi = _func(FM_TREE, 'get_insert_after_hwnd')
    _lines = {}
    if _gi is not None:
        for n in ast.walk(_gi):
            if isinstance(n, ast.Return) and isinstance(n.value, ast.Name) \
                    and n.value.id == '_stand':
                _lines['stand_ret'] = getattr(n, 'lineno', -1)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                    and n.func.id == 'pick_insert_after_by_foot_y':
                _lines['pick'] = getattr(n, 'lineno', -1)
    check(u'B1 ★ "站在楼板"那条 return 在 Y 规则调用**之前**（顺序即优先级）',
          'stand_ret' in _lines and 'pick' in _lines
          and _lines['stand_ret'] < _lines['pick'],
          u'行号=%r' % (_lines,))

    _has_iswin = False
    if _gi is not None:
        src = ast.dump(_gi)
        _has_iswin = ('IsWindow' in src) and ('_stand' in src)
    check(u'B2 站楼板分支带 `IsWindow` 校验（失效句柄不许直接返回）', _has_iswin)

    _doc = ast.get_docstring(_gi) or u''
    check(u'B3 docstring 里记着第179轮这条修正（防有人删了它又退回 178 的口径）',
          u'第179轮' in _doc and u'站在谁上面' in _doc)

    _zord = _func(MAIN_TREE, '_apply_pet_z_order')
    _ok_kw = False
    if _zord is not None:
        for n in ast.walk(_zord):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                    and n.func.attr == 'get_insert_after_hwnd':
                if any(k.arg == 'foot_y' for k in n.keywords):
                    _ok_kw = True
    check(u'B4 `_apply_pet_z_order` 仍然把 `foot_y=` 传下去（178 的接线没被这轮弄断）', _ok_kw)

    _fm4 = _mk_fm()
    check(u'B5 硬性向后兼容：**不传 `foot_y`** ⇒ 老口径（插到所站楼板 A 之上）',
          _fm4.get_insert_after_hwnd(ON_A) == A_HWND,
          u'anchor=%r reason=%r' % (_fm4.get_insert_after_hwnd(ON_A),
                                    _fm4._last_z_pick.get('reason')))

    # -------------------------------------------------------------------
    head(u'C 段  端到端（桩证明真正下发的 SetWindowPos 实参）')

    _stub.sp = []
    _fm5 = _mk_fm()
    _get = _fm5.get_insert_after_hwnd(ON_A, foot_y=FOOT)
    _ok = FM.FloorManager.set_window_behind(0x1234, _get)
    check(u'C0 夹具自检：桩确实收到了一次 `SetWindowPos`（否则下面那条是空转）',
          _ok is True and len(_stub.sp) == 1, u'calls=%r' % (_stub.sp,))
    check(u'C1 站在 A 上 ⇒ 真正下发的 `hWndInsertAfter` 是 **A**（宠物画在 A 之前，看得见）',
          _stub.sp and _stub.sp[0][1] == A_HWND and _stub.sp[0][0] == 0x1234,
          u'calls=%r' % (_stub.sp,))

    _stub.sp = []
    _fm6 = _mk_fm()
    FM.FloorManager.set_window_behind(0x2345, _fm6.get_insert_after_hwnd(DESKTOP, foot_y=950))
    check(u'C2 站桌面且低过所有窗口 ⇒ 真正下发的是 `HWND_TOP`（0），不是 BOTTOM（1）',
          _stub.sp and _stub.sp[0][1] == FM.HWND_TOP,
          u'calls=%r' % (_stub.sp,))

    # -------------------------------------------------------------------
    head(u'D 段  鉴别力与防御')

    _fm7 = _mk_fm()
    _same_floor_other_foot = _fm7.get_insert_after_hwnd(ON_A, foot_y=100)
    check(u'D1 站在 A 上时，脚底高低**不改变**锚点（可见性优先于 Y，脚底 100 也是 A）',
          _same_floor_other_foot == A_HWND,
          u'anchor=%r' % (_same_floor_other_foot,))

    _fm8 = _mk_fm()
    _fm8.underlying_windows = []
    check(u'D2 窗口表为空 ⇒ 回退老逻辑（站在 A 上仍是 A），不许顶到最前',
          _fm8.get_insert_after_hwnd(ON_A, foot_y=FOOT) == A_HWND,
          u'anchor=%r reason=%r' % (_fm8.get_insert_after_hwnd(ON_A, foot_y=FOOT),
                                    _fm8._last_z_pick.get('reason')))

    check(u'D3 `_last_z_pick` 有明确的 reason 字段（取证用，不参与判定）',
          _fm.get_insert_after_hwnd(ON_A, foot_y=FOOT) == A_HWND
          and _fm._last_z_pick.get('reason') == 'standing_floor',
          u'reason=%r' % (_fm._last_z_pick.get('reason'),))

    # -------------------------------------------------------------------
    head(u'E 段  文件与自检（判据也是被测物）')

    _b = io.open(FM_P, 'rb').read()
    check(u'E1 `floor_manager.py` 无 BOM、UTF-8 可解码、AST 可解析',
          not _b.startswith(b'\xef\xbb\xbf') and _b.decode('utf-8') is not None
          and FM_TREE is not None)

    _checks = [n for n in ast.walk(_tree(SELF))
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == 'check']
    _const_true = [getattr(c, 'lineno', -1) for c in _checks
                   if len(c.args) > 1 and isinstance(c.args[1], ast.Constant)
                   and bool(c.args[1].value)]
    check(u'E2 ★★★ 全部 %d 条 `check(...)` 的第二参**都不是**常量真' % len(_checks),
          len(_checks) > 0 and not _const_true, u'恒真行号=%r' % (_const_true[:5],))

    _ok_defs = [n for n in ast.walk(_tree(SELF))
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == 'ok']
    check(u'E3 单一 harness：本文件只定义 `check(desc, cond, extra)`', not _ok_defs)

    check(u'E4 判据条数下限：AST 数出 >= %d 条（防有人整段删掉）' % CHECK_FLOOR,
          len(_checks) >= CHECK_FLOOR)

    _self_src = io.open(SELF, encoding='utf-8').read()
    _pat = [('E' + ':' + '\\'), ('h' + 'ttp' + '://')]
    _hit = [p for p in _pat if p in _self_src]
    check(u'E5 零外部盘 / 零网络（★ 令牌用拼接构造，避免扫描器扫到自己）', not _hit,
          u'命中=%r' % (_hit,))

    _tok = ['Ralsei' + 'Pet(', 'import ' + 'main']
    _hit2 = [t for t in _tok if t in _self_src]
    check(u'E6 不构造桌面真机、不 import 主程序', not _hit2, u'命中=%r' % (_hit2,))
finally:
    FM.win32gui = _real

print('')
print('=' * 70)
print(u'合计：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
print('=' * 70)
sys.exit(0 if _n['f'] == 0 else 1)

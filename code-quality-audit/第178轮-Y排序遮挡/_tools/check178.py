# -*- coding: utf-8 -*-
u"""第178轮判据：「遮挡 = 按屏幕 Y 排序」落地（第164轮用户裁定 `BBA` 第三项）。

背景
----
第164轮用户裁定了三条 2.5D 空间规则（回 `BBA`），其中第三条是
**「遮挡 = 按屏幕 Y 排序（走到窗口"背后"即被挡住）」**。
前两条（可站矩形 = DWM 扩展边框 / 走出边缘 = 掉下去）当轮就成立，
第三条一直登记为 **❌ 未实现** —— 产品里是"宠物插到它所站的楼板之上"，
谁挡谁由**窗口自己的 z 序**决定，与宠物站在屏幕什么高度无关。

本轮把它改成按 Y 判：
  · 宠物脚底 Y 越大 = 离观众越近；
  · 窗口的远近由它的**下沿**代表（`top + height`，半开口径）；
  · 窗口下沿 > 脚底 Y ⇒ 窗口在前面 ⇒ 它挡住宠物；
  · 一个前挡者都没有 ⇒ 宠物插到 `HWND_TOP`（非置顶带最前）。

★★★ 本轮判据的重心（为什么不能只断言"函数被调用了"）
--------------------------------------------------
"改成按 Y 排序"这件事，最容易写出**看起来测了、其实什么都没测**的判据：
拿真实窗口表跑一遍，只要锚点不是 0 就算过 —— 可锚点是哪个窗口、为什么是它，
完全没被约束。所以重心压在**纯函数的行为差异**上：

  ① **排列语义**（A 段）：喂合成窗口表，直接断言"谁该当前挡者"。
     其中 A7「输入顺序无关」杀掉"取列表第一个"，A6「脚底挪 20px 必须翻面」
     杀掉"永远返回同一个"，A13「脚底 = 下沿 - 1 仍算前挡」杀掉把下沿算成
     `QRect.bottom()`（差 1px）的实现。
     ★ 合成表的 `z_order` **故意与下沿反着排**：否则"按 Y"与"按 z 序"给出同一答案，
       A3/A5 就成了恒真判据（第一版正是这样，实测后才改）。
  ② **接线正确**（B 段）：AST 判"foot_y 真的被传进去"、"候选真的是 floors"、
     "窗口表空时真的回退"，以及"167 的置顶闸还在"。
  ③ **语义陷阱**（D 段）：`HWND_TOP == 0` 是**假值**，而老代码写的是
     `insert = hwnd_after or HWND_BOTTOM` ⇒ 传 `HWND_TOP` 会被静默翻成
     `HWND_BOTTOM`（"插到最前"变成"插到最底"）。这条不靠肉眼，靠桩捕获
     `SetWindowPos` 的第 2 个实参。

不需要显示器、不构造桌面真机、零外部盘、零网络。
`win32gui` 在 C/D 段用**桩**替换（并在用完后还原），桩自己也先证明"确实被调用"。

用法：python check178.py
"""
import ast
import io
import json
import os
import random
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
from modules.floor_manager import (                # noqa: E402
    FloorManager, pick_insert_after_by_foot_y)

CHECK_FLOOR = 35

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


def _calls(node, fname):
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id == fname:
                out.append(n)
            elif isinstance(f, ast.Attribute) and f.attr == fname:
                out.append(n)
    return out


def _attrs(node):
    return set(n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute))


FM_TREE = _tree(FM_P)
MAIN_TREE = _tree(MAIN_P)
PICK = pick_insert_after_by_foot_y

#: 合成窗口表：下沿 400 / 700 / 1080。
#: ★★★ 注意 `z_order` 是**故意与下沿反着排**的（下沿越小的反而越靠后）——
#:   这样"按 Y 排"与"按 z 序排"会给出**不同**答案，判据才有鉴别力。
#:   第一版把两者排成同向，A3/A5 两条**根本区分不出**两种实现（本轮实测踩过）。
W3 = [
    {'hwnd': 0x11, 'rect': QRect(0, 100, 800, 300), 'z_order': 3},     # 下沿 400
    {'hwnd': 0x22, 'rect': QRect(100, 500, 400, 200), 'z_order': 2},   # 下沿 700
    {'hwnd': 0x33, 'rect': (0, 750, 1920, 1080), 'z_order': 1},        # 下沿 1080
]

# ---------------------------------------------------------------------------
head(u'A 段  纯函数：排列语义（遮挡 = 按屏幕 Y 排序）')

_a, _i = PICK(500, [])
check(u'A1 没有窗口 ⇒ `HWND_TOP`（宠物最近，画在最前；不是 WorkerW、不是 BOTTOM）',
      _a == FM.HWND_TOP and _i.get('reason') == 'frontmost',
      u'anchor=%r reason=%s' % (_a, _i.get('reason')))

_a, _i = PICK(1080, W3)
check(u'A2 所有窗口下沿都在脚底**之上**（脚底在屏幕最底）⇒ `HWND_TOP`',
      _a == FM.HWND_TOP, u'anchor=%r' % (_a,))

_a, _i = PICK(200, W3)
check(u'A3 三个窗口全在脚底下方 ⇒ 取下沿**最小**的（最近的前挡者）= 400 那扇',
      _a == 0x11 and _i.get('bottom') == 400,
      u'anchor=%r bottom=%r n_front=%r' % (_a, _i.get('bottom'), _i.get('n_front')))

_a, _i = PICK(400, W3)
check(u'A4 脚底正好=某窗口下沿 ⇒ 齐平算"在宠物后面"，该窗口不挡它（取 700 那扇）',
      _a == 0x22 and _i.get('bottom') == 700,
      u'anchor=%r bottom=%r' % (_a, _i.get('bottom')))

_a, _i = PICK(690, W3)
check(u'A5 脚底 690 ⇒ 前挡者是 700/1080 ⇒ 取 700',
      _a == 0x22, u'anchor=%r' % (_a,))
_a2, _i2 = PICK(710, W3)
check(u'A6 脚底 710 ⇒ 700 那扇落到身后 ⇒ 只剩 1080 当前挡者（**翻面**）',
      _a2 == 0x33 and _a2 != _a,
      u'690→%r 710→%r' % (_a, _a2))

_anchor_set = set()
_rng = random.Random(20261109)
for _k in range(24):
    _w = list(W3)
    _rng.shuffle(_w)
    _anchor_set.add(PICK(400 + (_k % 7) * 50, _w)[0])
check(u'A7 ★★ 输入顺序无关：打乱 24 次、7 种脚底高度，锚点集合只由 (脚底, 下沿) 决定'
      u'（偷偷按 z 序排的实现会在这里抖）',
      _anchor_set == set([PICK(400, W3)[0], PICK(450, W3)[0], PICK(500, W3)[0],
                          PICK(550, W3)[0], PICK(600, W3)[0], PICK(650, W3)[0],
                          PICK(700, W3)[0]]),
      u'集合=%r' % (sorted(_anchor_set),))

_q = PICK(500, [{'hwnd': 7, 'rect': QRect(0, 300, 100, 300)}])[0]   # 下沿 600
_t = PICK(500, [{'hwnd': 7, 'rect': (0, 300, 100, 600)}])[0]        # 下沿 600
check(u'A8 两种矩形形态（`QRect` / 半开四元组）结果一致 —— 下沿口径统一为 `top+height`',
      _q == 7 and _t == 7 and _q == _t, u'QRect=%r tuple=%r' % (_q, _t))

check(u'A9 `window_hwnd` 键名（`floors` 的写法）与 `hwnd` 等价',
      PICK(500, [{'window_hwnd': 9, 'rect': (0, 300, 10, 600)}])[0] == 9)

check(u'A10 无效句柄（0 / None / 字符串）不进候选 ⇒ 只剩合法的那扇',
      PICK(500, [{'hwnd': 0, 'rect': (0, 100, 10, 400)},
                 {'hwnd': None, 'rect': (0, 100, 10, 500)},
                 {'hwnd': u'123', 'rect': (0, 100, 10, 600)},
                 {'hwnd': 44, 'rect': (0, 100, 10, 700)}])[0] == 44)

#: ★★★ 1px 边界：下沿用**半开口径** `top + height`。若有人图省事写成
#:   `QRect.bottom()`（= top + height - 1），脚底 = 下沿 - 1 这一格就会被误判成
#:   "窗口在后面" ⇒ 宠物在最该被挡的那一像素上反而跑到前面去。
check(u'A11 ★ 1px 边界：脚底 = 下沿 - 1 仍算"窗口在前"（下沿必须是 `top+height`，'
      u'不是 `QRect.bottom()`）',
      PICK(599, [{'hwnd': 61, 'rect': QRect(0, 300, 100, 300)}])[0] == 61
      and PICK(600, [{'hwnd': 61, 'rect': QRect(0, 300, 100, 300)}])[0] == FM.HWND_TOP,
      u'599→%r 600→%r' % (PICK(599, [{'hwnd': 61, 'rect': QRect(0, 300, 100, 300)}])[0],
                          PICK(600, [{'hwnd': 61, 'rect': QRect(0, 300, 100, 300)}])[0]))

_a, _i = PICK(500, [{'hwnd': 51, 'rect': (0, 0, 10, 800), 'z_order': 5},
                    {'hwnd': 52, 'rect': (0, 0, 10, 800), 'z_order': 2}])
check(u'A12 下沿并列 ⇒ 取 z 序更前（`z_order` 更小）的那扇当锚点，宠物落在两者之后',
      _a == 52 and _i.get('n_front') == 2, u'anchor=%r' % (_a,))

_a, _i = PICK(None, W3)
check(u'A13 `foot_y=None` ⇒ 返回 `None`（不是 `HWND_TOP`）—— 让调用方走回退，不许猜',
      _a is None and _i.get('reason') == 'no_foot_y', u'anchor=%r' % (_a,))

# ---------------------------------------------------------------------------
head(u'B 段  接线：foot_y 真的被传下去、候选真的是 floors')

_gi = _func(FM_TREE, 'get_insert_after_hwnd')
_ok_sig = False
if _gi is not None:
    _args = [a.arg for a in _gi.args.args]
    _defs = _gi.args.defaults
    _ok_sig = 'foot_y' in _args
    if _ok_sig:
        _idx = _args.index('foot_y') - (len(_args) - len(_defs))
        _d = _defs[_idx] if 0 <= _idx < len(_defs) else None
        _ok_sig = isinstance(_d, ast.Constant) and _d.value is None
check(u'B1 `get_insert_after_hwnd` 签名含 `foot_y` 且默认 `None`（不给就保持老行为）',
      _ok_sig, u'形参=%r' % (_args if _gi else None,))

_ck = _calls(_gi, 'pick_insert_after_by_foot_y') if _gi is not None else []
check(u'B2 函数体里真的**调用**了 `pick_insert_after_by_foot_y`（不是只 import）',
      len(_ck) == 1, u'调用点=%d' % len(_ck))

_ok_floors = False
if len(_ck) == 1 and len(_ck[0].args) >= 2:
    _src2 = _ck[0].args[1]
    _ok_floors = (isinstance(_src2, ast.Attribute) and _src2.attr == 'floors')
check(u'B3 ★ 候选用的是 `self.floors`（**只含成立的楼层**），不是 `underlying_windows` 全量',
      _ok_floors, u'第二实参=%s' % (ast.dump(_ck[0].args[1])[:60] if len(_ck) == 1 and len(_ck[0].args) >= 2 else u'—'))

_guard = False
if _gi is not None:
    for n in ast.walk(_gi):
        if isinstance(n, ast.If):
            names = set()
            for x in ast.walk(n.test):
                if isinstance(x, ast.Attribute):
                    names.add(x.attr)
            if 'underlying_windows' in names:
                _guard = True
                break
check(u'B4 ★ 窗口表为空时有**回退闸**（`self.underlying_windows` 作条件）—— '
      u'否则启动第一拍会把宠物顶到最前', _guard)

_zord = _func(MAIN_TREE, '_apply_pet_z_order')
_ok_kw = False
if _zord is not None:
    for c in _calls(_zord, 'get_insert_after_hwnd'):
        if any(k.arg == 'foot_y' for k in c.keywords):
            _ok_kw = True
check(u'B5 `_apply_pet_z_order` 真的以关键字 `foot_y=` 把脚底传下去', _ok_kw)

_ok_foot = False
if _zord is not None:
    for n in ast.walk(_zord):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'foot_y':
            v = n.value
            if isinstance(v, ast.BinOp) and isinstance(v.op, ast.Add):
                has_pos = ('pos' in _attrs(v.left)) or ('y' in _attrs(v.left))
                has_h = 'height' in _attrs(v.right)
                _ok_foot = has_pos and has_h
check(u'B6 `foot_y` 由 `pos().y() + height()` 得到（脚底 = 窗口下沿，第163轮口径）',
      _ok_foot)

_topmost_gate = False
if _zord is not None:
    for n in ast.walk(_zord):
        if not isinstance(n, ast.If):
            continue
        #: ★ 闸是这样写的：`if getattr(self, '_scene_topmost_on', False): return False`
        #:   ⇒ 名字是**字符串字面量**（`getattr` 的参数），不是 `ast.Attribute`。
        #:   第一版只查 Attribute ⇒ 恒假 ⇒ 判据自己报假红（本轮实测）。
        _names = set()
        for x in ast.walk(n.test):
            if isinstance(x, ast.Attribute):
                _names.add(x.attr)
            elif isinstance(x, ast.Constant) and isinstance(x.value, str):
                _names.add(x.value)
        if '_scene_topmost_on' in _names and any(
                isinstance(x, ast.Return) for x in ast.walk(n)):
            _topmost_gate = True
            break
check(u'B7 ★ 第167轮那条闸还在：场景层置顶期间**直接 return**，不许把宠物插回普通层',
      _topmost_gate)

_fm_src = io.open(FM_P, encoding='utf-8').read()


def _set_window_behind_node():
    for n in ast.walk(FM_TREE):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == 'set_window_behind':
            return n
    return None


_swb = _set_window_behind_node()
#: ★ 这条不能拿文本搜：`or` 那个写法**就写在修好后的注释里**（解释为什么改），
#:   文本一搜必然命中自己（"扫描器扫到自己"的老坑）。改成 AST 判真实的代码。
_or_fallback = []
if _swb is not None:
    for n in ast.walk(_swb):
        if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or):
            for v in n.values:
                if isinstance(v, ast.Name) and v.id == 'HWND_BOTTOM':
                    _or_fallback.append(getattr(n, 'lineno', -1))
_has_none_guard = False
if _swb is not None:
    for n in ast.walk(_swb):
        if isinstance(n, ast.IfExp) and isinstance(n.body, ast.Name) \
                and n.body.id == 'HWND_BOTTOM':
            _has_none_guard = True
check(u'B8 `set_window_behind` 的代码里**不再**出现 `X or HWND_BOTTOM`，'
      u'且改成显式 `is None` 判断（`HWND_TOP == 0` 是假值，会被静默翻成 BOTTOM）',
      not _or_fallback and _has_none_guard,
      u'or 行号=%r 显式 None 判断=%r' % (_or_fallback, _has_none_guard))

# ---------------------------------------------------------------------------
head(u'C 段  真对象行为（win32gui 打桩，不碰真实窗口）')


class _W32(object):
    u"""`win32gui` 的最小替身：只记调用、只认"我声明的有效句柄"。"""

    def __init__(self, valid=()):
        self.valid = set(valid)
        self.sp = []
        self.touched = 0

    def IsWindow(self, h):
        self.touched += 1
        return h in self.valid

    def SetWindowPos(self, hwnd, insert, x, y, cx, cy, flags):
        self.sp.append((hwnd, insert, flags))
        return True

    #: `find_desktop_workerw_hwnd` 会用到下面这些；返回"找不到"即可
    def FindWindow(self, *a):
        return 0

    def FindWindowEx(self, *a):
        return 0

    def EnumWindows(self, *a):
        return True

    def IsWindowVisible(self, h):
        return False


_real_w32 = FM.win32gui
_stub = _W32(valid=(0x11, 0x22, 0x33, 0x99))
FM.win32gui = _stub
try:
    _fm = FloorManager()
    _fm.underlying_windows = [
        {'hwnd': 0x11, 'rect': QRect(0, 100, 800, 300), 'z_order': 1},
        {'hwnd': 0x22, 'rect': QRect(100, 500, 400, 200), 'z_order': 2},
        {'hwnd': 0x33, 'rect': QRect(0, 750, 1920, 330), 'z_order': 3},
    ]
    _fm.floors = [
        {'type': 'window', 'window_hwnd': 0x11,
         'rect': QRect(0, 100, 800, 300), 'z_order': 1},
        #: 0x22 在 floors 里（下沿 700）；0x33 **故意不在**（= 被完全压住、"暂时不存在"）
        {'type': 'window', 'window_hwnd': 0x22,
         'rect': QRect(100, 500, 400, 200), 'z_order': 2},
    ]
    _got = _fm.get_insert_after_hwnd(None, foot_y=500)
    check(u'C1 站在 0x22 之后（脚底 500、0x22 下沿 700）⇒ 锚点 = 0x22',
          _got == 0x22, u'anchor=%r info=%r' % (_got, _fm._last_z_pick))

    _got = _fm.get_insert_after_hwnd(None, foot_y=800)
    check(u'C2 ★ 0x33 只在 `underlying_windows`、不在 `floors` ⇒ **不许**当遮挡者'
          u'（被压住的窗口"暂时不存在"，不能"被一个看不见的窗口挡住"）',
          _got == FM.HWND_TOP,
          u'anchor=%r info=%r' % (_got, _fm._last_z_pick))

    _fm.underlying_windows = []
    _got = _fm.get_insert_after_hwnd({'type': 'desktop'}, foot_y=500)
    check(u'C3 窗口表为空（还没跑过 `update_floors`）⇒ **回退老逻辑**，落到 WorkerW/BOTTOM',
          _got not in (FM.HWND_TOP,) and _got in (FM.HWND_BOTTOM, 0),
          u'anchor=%r reason=%r' % (_got, _fm._last_z_pick.get('reason')))

    _fm.underlying_windows = [
        {'hwnd': 0x99, 'rect': QRect(0, 0, 100, 100), 'z_order': 1}]
    _got = _fm.get_insert_after_hwnd({'type': 'window', 'window_hwnd': 0x99})
    check(u'C4 不传 `foot_y` ⇒ 老口径（插到所站楼板之上）= 0x99（第十三轮 F1/F2 靠它）',
          _got == 0x99, u'anchor=%r' % (_got,))

    # ---------------- D 段：`HWND_TOP == 0` 的语义陷阱 ----------------
    head(u'D 段  `set_window_behind` 的 `HWND_TOP` 陷阱（本轮修的真 bug）')

    _stub.sp = []
    _r = FloorManager.set_window_behind(0x11, FM.HWND_TOP)
    check(u'D0 夹具自检：桩确实收到了 `SetWindowPos` 调用（否则下面几条全是空转）',
          _r is True and len(_stub.sp) == 1, u'calls=%r' % (_stub.sp,))

    _ins = _stub.sp[0][1] if _stub.sp else None
    check(u'D1 ★★★ 传 `HWND_TOP` ⇒ 第 2 个实参必须是 **0**（改前是 `1` = BOTTOM，语义正好反过来）',
          _ins == FM.HWND_TOP,
          u'insert=%r（HWND_TOP=%r / HWND_BOTTOM=%r）' % (_ins, FM.HWND_TOP, FM.HWND_BOTTOM))

    _stub.sp = []
    FloorManager.set_window_behind(0x11, None)
    check(u'D2 传 `None` ⇒ 仍然回落 `HWND_BOTTOM`（老行为一字不变）',
          _stub.sp and _stub.sp[0][1] == FM.HWND_BOTTOM,
          u'insert=%r' % (_stub.sp[0][1] if _stub.sp else None,))

    _stub.sp = []
    FloorManager.set_window_behind(0x11, 0x22)
    check(u'D3 传有效句柄 ⇒ 原样交给 `SetWindowPos`',
          _stub.sp and _stub.sp[0][1] == 0x22,
          u'insert=%r' % (_stub.sp[0][1] if _stub.sp else None,))

    _stub.sp = []
    FloorManager.set_window_behind(0x11, 0x77)      # 0x77 不在 valid 里
    check(u'D4 传失效句柄（窗口刚被关掉）⇒ 回落 `HWND_BOTTOM`，绝不把野句柄交出去',
          _stub.sp and _stub.sp[0][1] == FM.HWND_BOTTOM,
          u'insert=%r' % (_stub.sp[0][1] if _stub.sp else None,))

    _stub.sp = []
    _r = FloorManager.set_window_behind(0x00, 0x11)
    check(u'D5 目标句柄无效 ⇒ 返回 `False` 且**一次都不调用** `SetWindowPos`',
          _r is False and not _stub.sp, u'ret=%r calls=%d' % (_r, len(_stub.sp)))
finally:
    FM.win32gui = _real_w32

# ---------------------------------------------------------------------------
head(u'E 段  文件与自检（判据也是被测物）')

for _p, _label in ((FM_P, 'floor_manager.py'), (MAIN_P, 'main.py')):
    _b = io.open(_p, 'rb').read()
    try:
        _dec = _b.decode('utf-8')
        _ok = not _b.startswith(b'\xef\xbb\xbf')
    except Exception:
        _ok = False
    check(u'E1 %s 无 BOM、UTF-8 可解码、AST 可解析' % _label,
          _ok and _tree(_p) is not None)

_checks = [n for n in ast.walk(_tree(SELF))
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
           and n.func.id == 'check']
_const_true = [getattr(c, 'lineno', -1) for c in _checks
               if len(c.args) > 1 and isinstance(c.args[1], ast.Constant)
               and bool(c.args[1].value)]
check(u'E2 ★★★ 全部 %d 条 `check(...)` 的第二参**都不是**常量真（恒真判据比不写还危险）'
      % len(_checks),
      len(_checks) > 0 and not _const_true, u'恒真行号=%r' % (_const_true[:5],))

_ok_defs = [n for n in ast.walk(_tree(SELF))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == 'ok']
check(u'E3 单一 harness：本文件只定义 `check(desc, cond, extra)`，没有第二套 `ok(...)`',
      not _ok_defs)

check(u'E4 判据条数下限：AST 数出 >= %d 条（防有人整段删掉）' % CHECK_FLOOR,
      len(_checks) >= CHECK_FLOOR)

_self_src = io.open(SELF, encoding='utf-8').read()
_pat = [('E' + ':' + '\\'), ('h' + 'ttp' + '://'), ('h' + 'ttps' + '://')]
_hit = [p for p in _pat if p in _self_src]
check(u'E5 零外部盘 / 零网络：源码里不出现 E 盘路径或 URL'
      u'（★ 令牌用拼接构造，避免扫描器扫到自己）',
      not _hit, u'命中=%r' % (_hit,))

_tok = ['Ralsei' + 'Pet(', 'import ' + 'main']
_hit2 = [t for t in _tok if t in _self_src]
check(u'E6 不构造真机、不 import 主程序（本轮只碰 z 序判定，不需要显示器）',
      not _hit2, u'命中=%r' % (_hit2,))

print('')
print('=' * 70)
print(u'合计：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
print('=' * 70)
sys.exit(0 if _n['f'] == 0 else 1)

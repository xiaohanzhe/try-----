# -*- coding: utf-8 -*-
"""第十六轮复检：「建楼」要求逐条对账（用户指令："复检一下到底实没实现那些要求，
没有的话那就把它也加到计划里就好"）。

对账对象是项目根目录那份 `"建楼"要求` 文档（37 行）：13 条功能要求 + 3 条铁律
+ 2 条动画要求（第 36/37 行）。

本套件的定位是 **只读复检**：不改任何产品代码，只回答"到底实没实现"。
因此有两类断言：

  [OK]  —— 要求确实已实现（行为级优先，源码级其次）。
  [GAP] —— 要求**没有**实现。这类断言**故意断言当前的缺陷行为**，并在名字里写明
           "修复后本检查必须翻转"。这样缺口一旦被修，套件会红，逼着人来更新它
           —— 与第十三轮 C6b / 第十四轮 G5b 同一套路，避免"缺口被悄悄修掉"
           或者反过来"缺口被当成已实现"。

分组
----
  A ①②③⑫  世界构建：楼层生成 / 最高层 / 被盖住即不存在 / 一层压一层
  B ④⑤⑥⑦   视野与跳跃：可见区域 / 只旁跳或垂直跳 / 上跳落点 / 下跳逐层
  C ⑧⑩⑪    重力与动态：走出边缘坠落 / 关窗坠落 / 新窗盖旧窗
  D ⑨        挪动窗口 → 跟随
  E ⑬⑭      两条动画要求
  F GAP     复检新发现的缺口（不在上一轮报告的对账表里）

不需要真窗口（真 FloorManager + 合成窗口表 + 两个最小桩）。
必须用 C:\\Python311\\python.exe 运行（PyQt5/win32 在系统 Python 里）。

⚠ 历史快照（第十七轮加注）
-------------------------
本脚本断言的是**第十六轮复检当时**的代码状态，其中 G1 / G1b / G1c / G2 等
[GAP] 断言**故意断言当时的缺陷**。第十七轮修掉了这些缺陷，所以：
    · 修复后再跑本脚本，那几条 GAP 断言**必然翻转成 FAIL —— 这是设计如此，不是回归**；
    · 因此本脚本**不在 G2 回归套件清单里**（`regress/run_all.py` 未收录），
      只作为"修复前"的取证留档。
    · "修复后必须成立"的行为由 `第十七轮/verify_round17_build_fall.py` 锁住（已进 G2）。
"""
import ast
import io
import inspect
import json
import os
import sys
import textwrap
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
for _p in (os.path.join(PET, 'src'), MODS):
    if _p not in sys.path:
        sys.path.append(_p)

from PyQt5.QtCore import QPoint, QRect                      # noqa: E402
from PyQt5.QtWidgets import QApplication                    # noqa: E402

_app = QApplication.instance() or QApplication([])

import floor_manager as FM                                   # noqa: E402
from main import RalseiPet                                   # noqa: E402

PASS, FAIL = [], []


def ok(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('[PASS] ' if cond else '[FAIL] ') + name +
          ('' if cond else '   <<< ' + str(detail)))


def section(title):
    print('')
    print('=== %s ===' % title)


# ---------------------------------------------------------------- 源码工具
MAIN_PY = os.path.join(PET, 'src', 'main.py')
FM_PY = os.path.join(MODS, 'floor_manager.py')
MAIN_TEXT = io.open(MAIN_PY, encoding='utf-8').read()
FM_TEXT = io.open(FM_PY, encoding='utf-8').read()

_DROP = (tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
         tokenize.INDENT, tokenize.DEDENT)


def code_only_src(src):
    """剥掉注释/字符串后的 token 串联（空白先抹平）——`"字面量" in 源码` 会误命中。"""
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in _DROP:
                continue
            out.append(tok.string)
    except Exception:
        return ''
    return ' '.join(out)


def code_no_comment(src):
    """只剥注释、**保留字符串字面量** —— 找字符串 needle 必须走这个。"""
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                continue
            out.append(tok.string)
    except Exception:
        return ''
    return ' '.join(out)


import re as _re                                              # noqa: E402


def flat(s):
    return _re.sub(r'\s+', '', s or '')


def has_flat(hay, needle):
    return flat(needle) in flat(hay)


def _fn_source(name, text=MAIN_TEXT):
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return textwrap.dedent(ast.get_source_segment(text, node) or '')
    return None


def method_code(name, text=MAIN_TEXT):
    """函数**体**的 code-only 文本（限定函数体内，避免命中别处同名串）。"""
    seg = _fn_source(name, text)
    return None if seg is None else code_only_src(seg)


def method_lit(name, text=MAIN_TEXT):
    """函数**体**的"只剥注释"文本（保留字符串字面量）。"""
    seg = _fn_source(name, text)
    return None if seg is None else code_no_comment(seg)


def attr_consumers(attr, text=MAIN_TEXT):
    """哪些函数**读取**了 `self.<attr>`（只统计 Load，不含赋值）。"""
    tree = ast.parse(text)
    out = set()
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        for n in ast.walk(fn):
            if (isinstance(n, ast.Attribute) and n.attr == attr
                    and isinstance(n.ctx, ast.Load)):
                out.add(fn.name)
    return out


def anim_call_args(text=MAIN_TEXT):
    """所有 `change_animation("x")` / `play_animation_once("x")` 的字面量实参。"""
    tree = ast.parse(text)
    names = ('change_animation', 'play_animation_once')
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and n.args:
            f = n.func
            fname = getattr(f, 'attr', None) or getattr(f, 'id', None)
            if fname in names and isinstance(n.args[0], ast.Constant) \
                    and isinstance(n.args[0].value, str):
                out.add(n.args[0].value)
    return out


MAIN_CODE = code_only_src(MAIN_TEXT)
FM_CODE = code_only_src(FM_TEXT)

SCREEN = QRect(0, 0, 1920, 1080)
PET_W = PET_H = 110


# ---------------------------------------------------------------- 桩
def mk_window(hwnd, x, y, w, h, z, title='w'):
    return {'hwnd': hwnd, 'title': title, 'class_name': 'C',
            'rect': QRect(x, y, w, h), 'z_order': z}


def fm_real(windows):
    """真 FloorManager，只跑 `_generate_floors`（合成窗口表，不碰真机）。"""
    fm = FM.FloorManager(parent=None)
    fm.underlying_windows = list(windows)
    fm.desktop_floor['rect'] = QRect(SCREEN)
    fm._generate_floors()
    return fm


class StaticFM(FM.FloorManager):
    """update_floors 只重算楼层 —— 不碰 desktop_interaction（也就不会覆盖我的桌面矩形）。"""

    def update_floors(self):
        self._generate_floors()


def fm_static(windows):
    fm = StaticFM(parent=None)
    fm.underlying_windows = list(windows)
    fm.desktop_floor['rect'] = QRect(SCREEN)
    fm._generate_floors()
    return fm


def win_floor(hwnd, x, y, w, h, ph=10, z=5):
    rect = QRect(x, y, w, h)
    return {'type': 'window',
            'window': {'hwnd': hwnd, 'title': 't', 'class_name': 'C',
                       'rect': rect, 'z_order': z},
            'rect': rect, 'z_order': z, 'platform_height': ph,
            'window_hwnd': hwnd}


class FakeFloorManager:
    """`check_window_movement` 的最小楼层表（矩形判定 + is_floor_valid）。"""

    def __init__(self, floors):
        self.floors = list(floors)
        self.desktop_floor = {'type': 'desktop', 'rect': QRect(SCREEN),
                              'z_order': 0, 'platform_height': 0}

    def update_floors(self):
        pass

    def _all(self):
        return sorted(self.floors + [self.desktop_floor],
                      key=lambda f: f['platform_height'], reverse=True)

    def get_current_floor(self, pos):
        for f in self._all():
            if f['rect'].contains(pos):
                return f
        return self.desktop_floor

    def get_floor_by_window(self, hwnd):
        for f in self.floors:
            if f.get('window_hwnd') == hwnd:
                return f
        return None

    def is_floor_valid(self, floor):
        self.valid_calls = getattr(self, 'valid_calls', 0) + 1
        if (floor or {}).get('type') == 'desktop':
            return True
        hwnd = (floor or {}).get('window_hwnd')
        return any(f.get('window_hwnd') == hwnd for f in self.floors)


class MoveStub:
    """驱动真实 `check_window_movement` 的最小表面。"""

    def __init__(self, fm, x, y):
        self.floor_manager = fm
        self._x, self._y = int(x), int(y)
        self._spell_stage = None
        self.game_state = {'is_playing': False}
        self.is_falling = False
        self.is_jumping = False
        self.is_gravity_falling = False
        self._is_being_dragged = False
        self.current_floor = fm.get_current_floor(QPoint(self._x, self._y))
        self.current_window = None
        self.current_platform_z = 0
        self.spatial_pos = {'x': self._x, 'y': self._y, 'z': 0}
        self.calls = []
        self.emotion_system = type('E', (), {'react_to_event': lambda s, e, d: None})()

    def pos(self):
        return QPoint(self._x, self._y)

    def width(self):
        return PET_W

    def height(self):
        return PET_H

    def move(self, x, y):
        self._x, self._y = int(x), int(y)

    def _clamp_pos_to_desktop(self, x, y):
        return (max(SCREEN.left(), min(int(x), SCREEN.right() - PET_W)),
                max(SCREEN.top(), min(int(y), SCREEN.bottom() - PET_H)))

    def _sync_window_cache_from_floor(self, floor):
        return RalseiPet._sync_window_cache_from_floor(self, floor)

    def _apply_pet_z_order(self):
        return False

    def _visible_landing(self, fm, floor, pos):
        return RalseiPet._visible_landing(self, fm, floor, pos)

    def _floor_entry_plan(self, fm, floor, ralsei_rect, cur_floor=None):
        return RalseiPet._floor_entry_plan(self, fm, floor, ralsei_rect, cur_floor)

    def start_fall(self, reason="window_move"):
        if self.is_falling:
            return
        self.calls.append(('start_fall', reason))
        self.is_falling = True

    def start_falling(self, fall_velocity=0, is_thrown=False, reason=None):
        self.calls.append(('start_falling', reason))
        self.is_gravity_falling = True

    _floor_identity_key = staticmethod(RalseiPet._floor_identity_key)
    _floor_rect_changed = staticmethod(RalseiPet._floor_rect_changed)

    def _follow_floor_move(self, old, moved):
        return RalseiPet._follow_floor_move(self, old, moved)

    check_window_movement = RalseiPet.check_window_movement


def fell_calls(pet):
    return [c for c in pet.calls if c[0] in ('start_fall', 'start_falling')]


# ============================================================ A 世界构建
section('A ①②③⑫ 世界构建：楼层生成 / 最高层 / 被盖住即不存在 / 一层压一层')

# 参照文档第 20~26 行的例子：窗口A（大浏览器，靠后）+ 窗口B（小记事本，在前）
A_WIN = mk_window(1010, 100, 100, 1000, 800, 1, 'A_浏览器')
B_WIN = mk_window(1011, 600, 500, 300, 200, 0, 'B_记事本')
fm_ab = fm_real([A_WIN, B_WIN])
A_FLOOR = fm_ab.get_floor_by_window(1010)
B_FLOOR = fm_ab.get_floor_by_window(1011)

ok('A1 ① 每个可见窗口都生成一层楼板，且楼板矩形与窗口矩形完全一致',
   len(fm_ab.floors) == 2
   and A_FLOOR is not None and B_FLOOR is not None
   and A_FLOOR['rect'] == A_WIN['rect'] and B_FLOOR['rect'] == B_WIN['rect'],
   [(f['window_hwnd'], str(f['rect'])) for f in fm_ab.floors])

ok('A2 ② 最前面的窗口 = 最高层（B 在前 → platform_height 更高，桌面恒 0）',
   B_FLOOR['platform_height'] > A_FLOOR['platform_height'] > 0
   and fm_ab.desktop_floor['platform_height'] == 0,
   (B_FLOOR['platform_height'], A_FLOOR['platform_height']))

# ③ 被完全盖住 → 暂时不存在；且它不再遮挡更低的窗口
_back = mk_window(1020, 100, 100, 400, 400, 1)
_front = mk_window(1021, 50, 50, 600, 600, 0)
fm_full = fm_real([_back, _front])
ok('A3 ③ 被前面窗口完全盖住的窗口不成楼层（"暂时不存在"）',
   fm_full.get_floor_by_window(1020) is None
   and fm_full.get_floor_by_window(1021) is not None,
   [f['window_hwnd'] for f in fm_full.floors])

# 判别式构造：`_back` 被 `_front` 压到只剩 1200px²(<1600) → 它自己不成楼层。
# `_low` 面积恰好 1600px²，且**只**与 `_back` 重叠 1200px²、与 `_front` 完全不重叠：
#   · 若"被压下去的窗口"仍被当成遮挡者 → `_low` 可见 400 < 1600 → 不成楼层（错）；
#   · 正确实现只把**成立的楼层**当遮挡者 → `_low` 可见 1600 → 是楼层。
_press_back = mk_window(1031, 100, 100, 400, 400, 1)
_press_front = mk_window(1032, 100, 100, 397, 400, 0)
_low = mk_window(1030, 497, 100, 4, 400, 3)        # 面积 1600；x 497..500
fm_full2 = fm_real([_press_back, _press_front, _low])
ok('A3b ③ 被压下去的窗口**不再遮挡**更低的窗口（正确实现只把成立的楼层当遮挡者）',
   fm_full2.get_floor_by_window(1031) is None
   and fm_full2.get_floor_by_window(1030) is not None,
   [(f['window_hwnd'], f.get('visible_area')) for f in fm_full2.floors])

ok('A3c ③ 只被**部分**遮住（可见面积够大）→ 仍然是楼层',
   B_FLOOR is not None and B_FLOOR.get('visible_area', 0) > FM.MIN_FLOOR_VISIBLE_AREA,
   B_FLOOR.get('visible_area') if B_FLOOR else None)

ok('A4 ⑫ 一层压一层：_apply_pet_z_order 走"插到所站楼板之上"（不是强制置顶）',
   has_flat(method_code('_apply_pet_z_order'), 'get_insert_after_hwnd')
   and has_flat(method_code('_apply_pet_z_order'), 'set_window_behind')
   and hasattr(FM.FloorManager, 'set_window_behind')
   and hasattr(FM.FloorManager, 'get_insert_after_hwnd'), None)
ok('A4b ⑫ 曾经让遮挡彻底失效的 WindowStaysOnTopHint 已不在 main.py',
   'WindowStaysOnTopHint' not in MAIN_CODE, None)

# ============================================================ B 视野与跳跃
section('B ④⑤⑥⑦ 视野限制 / 只旁跳或垂直跳 / 上跳落点 / 下跳逐层')

ok('B1 ④ 站在被遮挡的部分不算数（floor_visible_contains 只认可见区域）',
   FM.FloorManager.floor_visible_contains(A_FLOOR, QPoint(700, 600)) is False
   and FM.FloorManager.floor_visible_contains(A_FLOOR, QPoint(200, 200)) is True,
   None)

# ⑥ 向上跳：落点必须落在目标层的可见区域里
_pet_fl = MoveStub(fm_ab, 700, 705)                 # 贴在 B 的下边缘下方
_plan = RalseiPet._floor_entry_plan(_pet_fl, fm_ab, B_FLOOR,
                                   QRect(700, 705, PET_W, PET_H),
                                   A_FLOOR)
ok('B2 ⑥ 向上跳的落点被吸附进目标层可见区域',
   _plan is not None and _plan[0] == 'top'
   and FM.FloorManager.floor_visible_contains(B_FLOOR, _plan[1]) is True, _plan)
ok('B2b ⑥ 落点被推得太远（可见部分离宠物 >200px）就放弃这次跳跃',
   has_flat(method_code('_floor_entry_plan'), '> 200'), None)
ok('B2c ⑥ 落点一律过 nearest_visible_point（唯一吸附入口）',
   has_flat(method_code('_floor_entry_plan'), '_visible_landing'),
   None)

# ⑦ 向下跳：只能相邻下一层
ok('B3 ⑦ adjacent_lower_floor(B) == A（相邻下一层），不是桌面',
   FM.FloorManager.adjacent_lower_floor(fm_ab, B_FLOOR) is not None
   and FM.FloorManager._floor_identity(fm_ab.adjacent_lower_floor(B_FLOOR)) == 1010,
   FM.FloorManager._floor_identity(fm_ab.adjacent_lower_floor(B_FLOOR)))
ok('B3b ⑦ adjacent_lower_floor(A) == 桌面；桌面下面没有楼板 → None',
   FM.FloorManager._floor_identity(fm_ab.adjacent_lower_floor(A_FLOOR)) == 'desktop'
   and FM.FloorManager.adjacent_lower_floor(fm_ab, fm_ab.desktop_floor) is None, None)
ok('B3c ⑦ 跳跃规划**显式**并入相邻下层（不靠 get_jump_destinations 的副作用）',
   has_flat(method_code('_nearest_floor_jump'), 'adjacent_lower_floor'), None)
ok('B3d ⑦ 落点必须落在该层可见区域内（get_jump_destinations 已改判可见区域）',
   has_flat(code_only_src(_fn_source('get_jump_destinations', FM_TEXT)),
            'floor_visible_contains'), None)

ok('B4 ⑤ 侧向移动 = 走路（不经过跳跃入口）：跳跃候选显式排除当前楼板',
   has_flat(method_code('_nearest_floor_jump'), 'cur_id'), None)

# ============================================================ C 重力与动态
section('C ⑧⑩⑪ 走出边缘坠落 / 关窗坠落 / 新窗盖旧窗')

# ⑧ 宠物自己走出楼板边缘（下面没有别的窗口）→ 常规坠落
_fm_c1 = FakeFloorManager([win_floor(901, 300, 300, 800, 600)])
_pet_c1 = MoveStub(_fm_c1, 1200, 500)
_pet_c1.current_floor = _fm_c1.get_floor_by_window(901)
_pet_c1.calls = []
RalseiPet.check_window_movement(_pet_c1)
ok('C1 ⑧ 自己走出楼板边缘（下面只有桌面）→ start_falling()，且不带"用户行为"起因',
   ('start_falling', None) in _pet_c1.calls
   and not any(c == ('start_falling', 'floor_removed') for c in _pet_c1.calls),
   _pet_c1.calls)

# ⑩ 用户关窗（下面只有桌面）→ 生气动画
_fm_c2 = FakeFloorManager([win_floor(902, 300, 300, 800, 600)])
_pet_c2 = MoveStub(_fm_c2, 500, 500)
_pet_c2.current_floor = _fm_c2.get_floor_by_window(902)
_fm_c2.floors = []
_pet_c2.calls = []
RalseiPet.check_window_movement(_pet_c2)
ok("C2 ⑩ 用户关掉脚下窗口（下面只有桌面）→ start_falling(reason='floor_removed')",
   ('start_falling', 'floor_removed') in _pet_c2.calls, _pet_c2.calls)

# ⑧b 坠落落点：下面第一块"能接住"的楼板（可见区域）
_pet_drop = MoveStub(fm_ab, 700, 600)
_dst, _pos = fm_ab.get_drop_destination(QPoint(700, 600), B_FLOOR)
ok('C3 ⑧ 坠落落点 = 先按可见区域找"下面第一块能接住的"，逐层不跳层',
   _dst is not None and _dst.get('type') == 'desktop',      # 该 x 处 A 被 B 盖住 → 只能落到桌面
   _dst.get('type') if _dst else None)
_dst2, _ = fm_ab.get_drop_destination(QPoint(200, 200), A_FLOOR)
ok('C3b ⑧ 走 A 的可见部分掉下去 → 落到桌面（A 已是脚下楼板则被跳过）',
   _dst2 is not None and _dst2.get('type') == 'desktop', _dst2.get('type'))

# ⑪ 新窗口盖住旧窗口 → 旧板失效、宠物直接站新板（不算被搬走、不摔）
_fm_c3 = StaticFM(parent=None)
_fm_c3.underlying_windows = [A_WIN, B_WIN]
_fm_c3.desktop_floor['rect'] = QRect(SCREEN)
_fm_c3._generate_floors()
_pet_c3 = MoveStub(_fm_c3, 700, 600)              # 该点被 B 盖住
_pet_c3.current_floor = _fm_c3.get_floor_by_window(1010)   # 上一拍站在 A 上
_pet_c3.calls = []
RalseiPet.check_window_movement(_pet_c3)
ok('C4 ⑪ 被新窗口盖住 → current_floor 重判为新窗口（B），且不摔',
   FM.FloorManager._floor_identity(_pet_c3.current_floor) == 1011
   and not fell_calls(_pet_c3), (FM.FloorManager._floor_identity(_pet_c3.current_floor),
                                 _pet_c3.calls))

# ============================================================ D 挪动窗口
section('D ⑨ 挪动窗口 → 宠物跟着楼板一起移动')

_old = win_floor(1100, 300, 300, 800, 600)
_moved = win_floor(1100, 340, 300, 800, 600)      # 右移 40px
_fm_d1 = FakeFloorManager([_moved])
_pet_d1 = MoveStub(_fm_d1, 500, 500)
_pet_d1.current_floor = _old                      # 缓存里还是上一拍的矩形
_pet_d1.calls = []
RalseiPet.check_window_movement(_pet_d1)
ok('D1 ⑨ 窗口平移 40px → 宠物跟着平移同样的位移',
   _pet_d1._x == 540 and _pet_d1._y == 500, (_pet_d1._x, _pet_d1._y))
ok("D1b ⑨ 位移 >30px → 重心不稳摔倒（window_move ≥3s，要求第 37 行）",
   ('start_fall', 'window_move') in _pet_d1.calls, _pet_d1.calls)

_old2 = win_floor(1101, 300, 300, 800, 600)
_moved2 = win_floor(1101, 310, 300, 800, 600)     # 右移 10px
_fm_d2 = FakeFloorManager([_moved2])
_pet_d2 = MoveStub(_fm_d2, 500, 500)
_pet_d2.current_floor = _old2
_pet_d2.calls = []
RalseiPet.check_window_movement(_pet_d2)
ok('D2 ⑨ 小幅平移 10px → 还是跟着走，且**不摔**（"别给我掉下来"）',
   _pet_d2._x == 510 and not fell_calls(_pet_d2), (_pet_d2._x, _pet_d2.calls))

# ============================================================ E 两条动画要求
section('E ⑬⑭ 两条动画要求（生气 ≥5s / 挪楼板摔倒 ≥3s）')

_consumers = attr_consumers('max_fall_duration')
# 注意：`fall_mad` / `"splat"` 是**字符串字面量** → 必须用 method_lit（只剥注释）
ok('E1 ⑭ 挪楼板摔倒：start_fall(window_move) 选 fall_mad 且 max_fall_duration = 3.0',
   has_flat(method_lit('start_fall'), 'fall_mad')
   and has_flat(method_lit('start_fall'), 'max_fall_duration = 3.0'), None)
ok('E1b ⑭ 这个 3.0 是**真的被消费**的（handle_fall 会读它）',
   'handle_fall' in _consumers, sorted(_consumers))

ok("E2 ⑬ 关窗坠落：start_falling(reason='floor_removed') 选 fall_mad 且写 max_fall_duration = 5.0",
   has_flat(method_lit('start_falling'), 'fall_mad')
   and has_flat(method_lit('start_falling'), 'max_fall_duration = 5.0'), None)

# ============================================================ F GAP
section('F GAP — 复检新发现的缺口（修复后本组断言必须翻转）')

# ---- G1（⑬）"生气动画至少 5s"实际不成立 -----------------------------------
ok('G1[GAP] max_fall_duration 在**全项目**只被 handle_fall 读取 → start_falling 写的 5.0 是死参数',
   _consumers == {'handle_fall'}, sorted(_consumers))
ok('G1b[GAP] start_falling 把 is_falling 置 False → handle_fall（唯一读 max_fall_duration 的地方）不跑',
   has_flat(method_code('start_falling'), 'self.is_falling = False'), None)
ok('G1c[GAP] 关窗坠落落地后动画被 trigger_splat 顶成普通 splat（splat_mad 从未被播过）',
   'splat_mad' not in anim_call_args()
   and 'splat_mad' in io.open(os.path.join(PET, 'assets', 'animations.json'),
                              encoding='utf-8').read(),
   sorted(a for a in anim_call_args() if 'splat' in a))

# ---- G2（⑧/⑩）"关掉上层窗口、下方还有窗口"→ 不坠落 ------------------------
_fmA = FakeFloorManager([win_floor(1200, 100, 100, 1000, 800, ph=5),
                         win_floor(1201, 600, 500, 300, 200, ph=10)])
_pet_g2 = MoveStub(_fmA, 700, 600)
_pet_g2.current_floor = _fmA.get_floor_by_window(1201)     # 站在记事本(B)上
_fmA.floors = [_fmA.get_floor_by_window(1200)]             # 用户把记事本关掉，浏览器(A)还在
_fmA.valid_calls = 0
_pet_g2.calls = []
RalseiPet.check_window_movement(_pet_g2)
ok('G2[GAP] 关掉上层窗口、下方还有另一窗口 → **不坠落**（直接换成下层，无动画）'
   '  ← 要求原文第 30 行正是这个例子',
   not fell_calls(_pet_g2)
   and FM.FloorManager._floor_identity(_pet_g2.current_floor) == 1200,
   _pet_g2.calls + ['now=%s' % FM.FloorManager._floor_identity(_pet_g2.current_floor)])
ok('G2b[GAP] 因为坠落分支的门是 new_floor.type != "window" → 起因分流(is_floor_valid)根本没被问',
   getattr(_fmA, 'valid_calls', 0) == 0
   and has_flat(method_lit('check_window_movement'),
                "if old_floor.get('type') == 'window' and new_floor.get('type') != 'window':"),
   getattr(_fmA, 'valid_calls', 0))

# 但落点几何本身是好的：真 FloorManager 上，"记事本已关、浏览器还在"时
# 从记事本的高度往下掉 → `get_drop_destination` 会给出**浏览器**。
# 所以 G2 缺的是**调用点**，不是落点计算。
_fm_g2c = fm_static([mk_window(1200, 100, 100, 1000, 800, 1),
                     mk_window(1201, 600, 500, 300, 200, 0)])
_stale_b = win_floor(1201, 600, 500, 300, 200, ph=10)      # 缓存里那块已经关掉的楼板
_fm_g2c.underlying_windows = [mk_window(1200, 100, 100, 1000, 800, 1)]
_fm_g2c._generate_floors()
_dst_g2c, _ = _fm_g2c.get_drop_destination(QPoint(700, 600), _stale_b)
ok('G2c[GAP] 但"下面的窗口"作为落点是**算得出来的** → 缺的是调用点，不是落点几何',
   FM.FloorManager._floor_identity(_dst_g2c) == 1200,
   FM.FloorManager._floor_identity(_dst_g2c))

# ---- G3（④/⑤）走路可以直接"走进"更高楼层的可见区域并被提升 ----------------
_fm_g3 = fm_static([A_WIN, B_WIN])
_pet_g3 = MoveStub(_fm_g3, 700, 600)
_pet_g3.current_floor = _fm_g3.desktop_floor        # 上一拍站在 1 楼（桌面）
_pet_g3.spatial_pos['z'] = 0
_pet_g3.calls = []
RalseiPet.check_window_movement(_pet_g3)
ok('G3[GAP] 站在桌面(1楼)上水平走进窗口B的可见区域 → 被直接提升到 B，'
   ' 无跳跃、不坠落（要求 ⑤：上/下必须靠"跳"）',
   FM.FloorManager._floor_identity(_pet_g3.current_floor) == 1011
   and not fell_calls(_pet_g3), _pet_g3.calls)
ok('G3b[GAP] 随机走路目标完全不看窗口/楼层（没有任何避让或"必须先跳"的闸门）',
   (method_code('generate_new_move_target') or '').find('window') < 0
   and (method_code('generate_new_move_target') or '').find('floor') < 0, None)

# ---- G4（⑨）位移 >400px 时"不跟随、改掉落"（与"必须跟着"的字面冲突，属有意偏差）
_fm_g4 = FakeFloorManager([win_floor(1300, 900, 300, 800, 600)])
_pet_g4 = MoveStub(_fm_g4, 1000, 500)
_pet_g4.current_floor = win_floor(1300, 300, 300, 800, 600)   # 上一拍矩形（左移 600px）
_pet_g4.calls = []
RalseiPet.check_window_movement(_pet_g4)
ok('G4[GAP/偏差] 窗口瞬时位移 >400px → 宠物**不跟随**、原地失足掉落'
   '（要求 ⑨ 写的是"必须跟着楼板一起移动"；这是为最大化/还原留的有意偏差）',
   ('start_fall', 'window_move') in _pet_g4.calls
   and _pet_g4._x == 1000
   and has_flat(method_code('_follow_floor_move'), '> 400'),
   (_pet_g4._x, _pet_g4.calls))

# ---- G5 `climb_to_top_window` 仍走裸窗口路径 -------------------------------
ok('G5[GAP] climb_to_top_window 仍用裸窗口直跳（不经楼层 → 可能落到被遮挡部分）',
   has_flat(method_code('climb_to_top_window'), 'get_all_visible_windows')
   and has_flat(method_lit('climb_to_top_window'), 'start_jump(top_window, "bottom")')
   and 'target_floor' not in (method_code('climb_to_top_window') or ''), None)

# ---- G6（⑭）生气素材实际只播约 1s（随后被普通 splat 顶掉） -----------------
ok('G6[GAP] handle_fall 的"摔扁"阶段切的是普通 splat → 生气素材只存活在飞行段(≈1s)',
   has_flat(method_lit('handle_fall'), 'change_animation("splat"')
   and 'splat_mad' not in anim_call_args()
   and has_flat(method_lit('handle_fall'), '_fall_flight_time')
   and has_flat(method_code('handle_fall'), '>= 1.0'), None)

# ---- G7（①③）可见面积阈值：只被遮住一部分但不足 1600px² → 直接不存在 ------
_tiny_back = mk_window(1400, 100, 100, 300, 100, 1)
_tiny_front = mk_window(1401, 100, 100, 290, 100, 0)
fm_tiny = fm_real([_tiny_back, _tiny_front])
ok('G7[GAP/偏差] 可见面积 1000px²(<1600) 的窗口直接不成楼层'
   '（要求 ③ 只写"被**完全**盖住"才不存在）',
   fm_tiny.get_floor_by_window(1400) is None
   and fm_tiny.get_floor_by_window(1401) is not None, None)
_big_back = mk_window(1410, 100, 100, 300, 100, 1)
_big_front = mk_window(1411, 100, 100, 200, 100, 0)
fm_big = fm_real([_big_back, _big_front])
ok('G7b[GAP/偏差] 可见面积 10000px²(>1600) → 仍是楼层（阈值效应得到对照）',
   fm_big.get_floor_by_window(1410) is not None, None)

# ============================================================ 汇总
print('')
print('=' * 64)
print('复检结果：PASS=%d  FAIL=%d' % (len(PASS), len(FAIL)))
_gaps = [n for n in PASS + FAIL if '[GAP' in n]
print('其中"缺口"断言（断言的是**当前缺陷**，修好后必须翻转）：%d 条' % len(_gaps))
for g in _gaps:
    print('   · ' + g)
if FAIL:
    print('')
    print('失败项：')
    for f in FAIL:
        print('   ! ' + f)
print('=' * 64)
sys.exit(1 if FAIL else 0)

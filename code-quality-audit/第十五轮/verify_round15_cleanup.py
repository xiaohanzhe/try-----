# -*- coding: utf-8 -*-
"""第十五轮验证：「建楼」死代码清干净 + 一个被错判的坠落起因。

背景（两件事凑成一轮）
----------------------
1) **死代码积压**。第十三/十四轮把"建楼"的判据接进产品后，留下三堆没人调用的实现：
     · `main.py::update_floor`        —— 第五轮 F3 就点名的"全项目无调用点 + 与
       `check_window_movement` 逐行重复且已漂移"的副本；H4/H5 计划 G1 的优先清理项。
     · `main.py::check_nearby_windows` 尾部的"裸窗口矩形 + 10~30px 贴边"老启发式
       —— 第十三轮把口径改成"可见区域"之后，它是**口径错误的旧路**
       （会跳到被挡住的部分；站在窗口上时把目标直接声明成桌面 = 穿透）。
     · `floor_manager.py::find_support_below`（`get_drop_destination` 的重复实现）
       与 `is_on_floor_edge`（无任何消费者）。
   三者都是"改了没人调用"这个项目最贵的坑的另一面 —— **没改也没人调用的**。

2) **一个被错判的坠落起因**（真 bug）。`check_window_movement` 里，脚下窗口楼板
   "没了"时一律按 `reason='floor_removed'`（**用户行为**）处理 → 生气动画 ≥5s。
   但 `get_current_floor` 判到"不在窗口上了"有两种成因：
     · 宠物**自己走到了楼板边缘之外**（窗口还开着）→ 建楼要求是"就直直掉下去，
       落到下面第一块能接住的楼板"，**这不算用户的行为**，不该生气；
     · 用户**把窗口关了**（楼板被抽走）→ 这才是"我的行为"，用生气动画。
   判据早写好了（`floor_manager.is_floor_valid`：楼板引用的窗口还在不在），
   但它**全项目零调用**（第五轮的死引用清单里就有它）→ 这里把它接活。

分组
----
  A 死代码确实清了（源码级 + 行为级）
  B 跳跃只剩一条入口（楼层不可用时不再回落裸矩形）
  C "自己走出去" vs "用户抽走楼板"（起因分流 + `is_floor_valid` 被真正调用）
  D floor_manager 的权威路径未被误删

本套件不需要真窗口（合成窗口表 + 真 FloorManager / FakeFloorManager）。
必须用 C:\\Python311\\python.exe 运行。
"""
import ast
import io
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
    """剥掉注释/字符串后的 token 串联（空白先抹平）——`"字面量" in 源码` 会误命中，
    所以源码级断言一律走这里。见 MEMORY「验证脚本教训」。"""
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in _DROP:
                continue
            out.append(tok.string)
    except Exception:
        return ''
    return ' '.join(out)


import re as _re                                              # noqa: E402


def flat(s):
    return _re.sub(r'\s+', '', s)


def has_flat(hay, needle):
    """hay 已是 code-only 串（token 间有空格）→ 两侧都抹白再比。"""
    return flat(needle) in flat(hay or '')


def method_code(name, text=MAIN_TEXT):
    """取某个方法**体**的 code-only 文本（限定在函数体内，避免命中别处同名串）。"""
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            seg = ast.get_source_segment(text, node)
            return code_only_src(textwrap.dedent(seg or ''))
    return None


MAIN_CODE = code_only_src(MAIN_TEXT)
FM_CODE = code_only_src(FM_TEXT)

# ============================================================ A 死代码确实清了
section('A 死代码确实清了（建楼遗留的三堆）')

ok('A1 update_floor 已删除（第五轮 F3 点名的"零调用 + 漂移副本"）',
   method_code('update_floor') is None
   and not hasattr(RalseiPet, 'update_floor'),
   'still exists' if hasattr(RalseiPet, 'update_floor') else None)
ok('A1b 唯一入口 check_window_movement 仍在（不是把功能一起删了）',
   method_code('check_window_movement') is not None
   and 'defcheck_window_movement(' in flat(MAIN_CODE), None)

ok('A2 floor_manager 不再有 find_support_below（get_drop_destination 的重复实现）',
   not hasattr(FM.FloorManager, 'find_support_below')
   and 'deffind_support_below(' not in flat(FM_CODE), None)
ok('A2b floor_manager 不再有 is_on_floor_edge（无消费者）',
   not hasattr(FM.FloorManager, 'is_on_floor_edge')
   and 'defis_on_floor_edge(' not in flat(FM_CODE), None)

_dup = [n for n in ('find_support_below', 'is_on_floor_edge', 'update_floor')
        if flat('def%s(' % n) in flat(MAIN_CODE) or flat('def%s(' % n) in flat(FM_CODE)]
ok('A3 三个死实体在 main / floor_manager 源码里都已不存在', not _dup, _dup)

# check_nearby_windows 函数体内不该再出现裸窗口枚举（老启发式的唯一入口）
_cnw = method_code('check_nearby_windows')
ok('A4 check_nearby_windows 体内已无 desktop_interaction / get_all_visible_windows',
   _cnw is not None
   and 'desktop_interaction' not in _cnw
   and 'get_all_visible_windows' not in _cnw, None)
ok('A4b check_nearby_windows 体内已无老启发式的特征量（jump_desktop_edge / edge_threshold）',
   _cnw is not None
   and 'jump_desktop_edge' not in _cnw
   and 'edge_threshold' not in _cnw, None)
ok('A4c 老落点反推的 title_bar_height 只剩 start_jump 一处（climb_to_top_window 那条路还在用）',
   flat(MAIN_CODE).count('title_bar_height') > 0
   and 'title_bar_height' not in _cnw, None)

# 行为级：删除后方法仍可调用（不是留了个半截函数）
import inspect                                                # noqa: E402
ok('A5 check_nearby_windows 仍可正常取到（签名未变）',
   str(inspect.signature(RalseiPet.check_nearby_windows)) == '(self, current_pos)',
   str(inspect.signature(RalseiPet.check_nearby_windows)))
ok('A5b start_jump 的裸窗口回落分支**保留**（climb_to_top_window / 命令行仍在用，不能误删）',
   has_flat(method_code('start_jump'), 'if target_pos is not None:')
   and 'title_bar_height' in method_code('start_jump'), None)

# ============================================================ B 单一入口
section('B 跳跃只剩一条入口（楼层不可用时不再回落裸矩形）')

SCREEN = QRect(0, 0, 1920, 1080)
PET_W = PET_H = 110


def mk_window(hwnd, x, y, w, h, z, title='w'):
    return {'hwnd': hwnd, 'title': title, 'class_name': 'C',
            'rect': QRect(x, y, w, h), 'z_order': z}


def fm_with(windows):
    fm = FM.FloorManager(parent=None)
    fm.underlying_windows = list(windows)
    fm.desktop_floor['rect'] = QRect(SCREEN)
    fm._generate_floors()
    return fm


class JumpStub:
    """驱动真实 `check_nearby_windows` 的最小表面。

    **故意不提供 `desktop_interaction`** —— 一旦代码偷偷回落到裸窗口启发式，
    它第一步就要枚举窗口 → AttributeError。这是本轮最强的防复发闸门。
    """

    def __init__(self, fm, x, y):
        self.floor_manager = fm
        self._x, self._y = int(x), int(y)
        self.is_jumping = False
        self._spell_stage = None
        self.game_state = {'is_playing': False}
        self.needs_rest = False
        self.last_jump_time = 0.0
        self.jump_cooldown = 1.5
        self.jump_count = 0
        self.resting_time = 0
        self.rest_duration = 5.0
        self.calls = []
        self.plans = None          # None → 这一拍没有可执行的跳跃

    def pos(self):
        return QPoint(self._x, self._y)

    def width(self):
        return PET_W

    def height(self):
        return PET_H

    _floor_identity_key = staticmethod(RalseiPet._floor_identity_key)

    def _floors_for_jump(self):
        return RalseiPet._floors_for_jump(self)

    def _visible_landing(self, fm, floor, pos):
        return RalseiPet._visible_landing(self, fm, floor, pos)

    def _floor_entry_plan(self, fm, floor, ralsei_rect, cur_floor=None):
        return RalseiPet._floor_entry_plan(self, fm, floor, ralsei_rect, cur_floor)

    def _nearest_floor_jump(self, fm, cur_floor, ralsei_rect):
        self.calls.append(('plan', cur_floor.get('type')))
        return self.plans

    def _start_floor_jump(self, floor, edge, land):
        self.calls.append(('start', floor.get('type') if floor else None, edge))

    # 真实现：这一拍的路由就是它
    check_nearby_windows = RalseiPet.check_nearby_windows


_fm_b = fm_with([mk_window(801, 300, 300, 800, 600, 0)])
_pet_b = JumpStub(_fm_b, 500, 500)
_pet_b.plans = None                    # 本拍没有任何可执行的跳跃
_pet_b.calls = []
RalseiPet.check_nearby_windows(_pet_b, _pet_b.pos())
ok('B1 楼层可用 → 走楼层规划（_nearest_floor_jump 被调用）',
   any(c[0] == 'plan' for c in _pet_b.calls), _pet_b.calls)
ok('B1b 楼层可用但本拍无可执行跳跃 → 不起跳、不抛异常',
   not any(c[0] == 'start' for c in _pet_b.calls), _pet_b.calls)

_fm_empty = FM.FloorManager(parent=None)
_fm_empty.underlying_windows = []
_fm_empty.desktop_floor['rect'] = QRect(SCREEN)
_fm_empty.floors = []
_pet_empty = JumpStub(_fm_empty, 500, 500)
_pet_empty.calls = []
try:
    RalseiPet.check_nearby_windows(_pet_empty, _pet_empty.pos())
    _err = None
except Exception as e:                                        # pragma: no cover
    _err = repr(e)
ok('B2 楼层不可用（无可见窗口）→ 直接返回：不查桌面窗口、不抛（老路径已删）',
   _err is None and not _pet_empty.calls, 'err=%s calls=%s' % (_err, _pet_empty.calls))

# 有可执行跳跃时必须真的起跳（证明不是"永远不跳"）
_fm_b2 = fm_with([mk_window(802, 300, 300, 800, 600, 0)])
_pet_b2 = JumpStub(_fm_b2, 500, 900)
_pet_b2.plans = (_fm_b2.get_floor_by_window(802), 'bottom', QPoint(700, 310))
_pet_b2.calls = []
RalseiPet.check_nearby_windows(_pet_b2, _pet_b2.pos())
ok('B3 有可执行跳跃时确实起跳（_start_floor_jump 被调用）',
   any(c[0] == 'start' for c in _pet_b2.calls), _pet_b2.calls)

# ============================================================ C 坠落起因分流
section('C "自己走出楼板" vs "用户抽走楼板"（起因分流）')


class FakeFloorManager:
    """check_window_movement 的最小楼层表。`is_floor_valid` = "窗口还在不在"。"""

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


def win_floor(hwnd, x, y, w, h, ph=10, z=5):
    rect = QRect(x, y, w, h)
    return {'type': 'window',
            'window': {'hwnd': hwnd, 'title': 't', 'class_name': 'C',
                       'rect': rect, 'z_order': z},
            'rect': rect, 'z_order': z, 'platform_height': ph, 'window_hwnd': hwnd}


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

    def _visible_landing(self, fm, floor, pos):
        return RalseiPet._visible_landing(self, fm, floor, pos)

    def _floor_entry_plan(self, fm, floor, ralsei_rect, cur_floor=None):
        return RalseiPet._floor_entry_plan(self, fm, floor, ralsei_rect, cur_floor)

    def _apply_pet_z_order(self):
        return False

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


# --- C1/C2：宠物自己走出楼板边缘（窗口还开着）→ 常规坠落动画
_a = win_floor(901, 300, 300, 800, 600)          # right = 1100，bottom = 900
_fm_c1 = FakeFloorManager([win_floor(901, 300, 300, 800, 600)])
_pet_c1 = MoveStub(_fm_c1, 1200, 500)            # 已经走到窗口右边之外
_pet_c1.current_floor = _a                       # 上一拍还站在它上面
_pet_c1.calls = []
RalseiPet.check_window_movement(_pet_c1)
ok('C1 自己走出楼板边缘（窗口还在）→ start_falling() 不带"用户行为"起因',
   ('start_falling', None) in _pet_c1.calls, _pet_c1.calls)
ok('C1b 不会误用 floor_removed（否则会播生气动画，与要求相反）',
   not any(c == ('start_falling', 'floor_removed') for c in _pet_c1.calls), _pet_c1.calls)

# --- C3/C4：用户关掉窗口 → 生气动画
_fm_c2 = FakeFloorManager([win_floor(902, 300, 300, 800, 600)])
_pet_c2 = MoveStub(_fm_c2, 500, 500)
_pet_c2.current_floor = _fm_c2.get_floor_by_window(902)
_fm_c2.floors = []                               # 窗口被关掉
_pet_c2.calls = []
RalseiPet.check_window_movement(_pet_c2)
ok('C3 窗口被关掉（楼板被抽走）→ start_falling(reason=\'floor_removed\')',
   ('start_falling', 'floor_removed') in _pet_c2.calls, _pet_c2.calls)

# --- C5：判别用的 is_floor_valid 必须真的被调到（不是"写了没人用"）
ok('C5 is_floor_valid 在 check_window_movement 里被真正调用（判别一次成因）',
   getattr(_fm_c1, 'valid_calls', 0) >= 1 and getattr(_fm_c2, 'valid_calls', 0) >= 1,
   'c1=%s c2=%s' % (getattr(_fm_c1, 'valid_calls', 0), getattr(_fm_c2, 'valid_calls', 0)))
ok('C5b 源码级：判别分支就在 check_window_movement 体内',
   'is_floor_valid' in (method_code('check_window_movement') or ''), None)

# --- C6：is_floor_valid 的语义（存在 / 不存在 / 桌面）
_fm_c3 = FakeFloorManager([win_floor(903, 0, 0, 100, 100)])
ok('C6 is_floor_valid：窗口还在 → True',
   _fm_c3.is_floor_valid(_fm_c3.get_floor_by_window(903)) is True, None)
ok('C6b is_floor_valid：窗口不在了 → False',
   _fm_c3.is_floor_valid(win_floor(999, 0, 0, 100, 100)) is False, None)
ok('C6c is_floor_valid：桌面层恒为 True',
   _fm_c3.is_floor_valid(_fm_c3.desktop_floor) is True, None)

# --- C7：跳跃几何没被这轮清理动到（真算一条"进入边"出来）
_fm_c4 = fm_with([mk_window(904, 300, 300, 800, 600, 0)])
_pet_c4 = JumpStub(_fm_c4, 500, 200)
_cur = _fm_c4.get_floor_by_window(904)
_plan = RalseiPet._floor_entry_plan(_pet_c4, _fm_c4, _cur,
                                    QRect(500, 200, PET_W, PET_H),
                                    _fm_c4.desktop_floor)
ok('C7 贴边进入规划仍可用（上方贴边 → 产出 edge=\'bottom\' + 可见落点）',
   _plan is not None and _plan[0] == 'bottom' and _plan[1] is not None,
   _plan)
ok('C7b 落点确实落在该层可见区域内',
   _plan is not None and FM.FloorManager.floor_visible_contains(_cur, _plan[1]) is True,
   _plan[1] if _plan else None)

# ============================================================ D 权威路径未误删
section('D floor_manager 的权威路径未被误删')

ok('D1 get_drop_destination 仍在（下落落点唯一真源）',
   'defget_drop_destination(' in flat(FM_CODE), None)
ok('D2 adjacent_lower_floor / nearest_visible_point 仍在（第十四轮新增契约）',
   'defadjacent_lower_floor(' in flat(FM_CODE)
   and 'defnearest_visible_point(' in flat(FM_CODE), None)
ok('D3 floor_visible_contains / visible_subrects 仍在（可见区域唯一判据）',
   'deffloor_visible_contains(' in flat(FM_CODE)
   and 'defvisible_subrects(' in flat(FM_CODE), None)
ok('D4 第十四轮新增的 6 个跳跃规划方法都还在',
   all('def%s(' % n in flat(MAIN_CODE) for n in
       ('_floors_for_jump', '_visible_landing', '_floor_entry_plan',
        '_nearest_floor_jump', '_start_floor_jump', '_sync_window_cache_from_floor')),
   [n for n in ('_floors_for_jump', '_visible_landing', '_floor_entry_plan',
                '_nearest_floor_jump', '_start_floor_jump', '_sync_window_cache_from_floor')
    if 'def%s(' % n not in flat(MAIN_CODE)])

_fm_d = fm_with([mk_window(905, 300, 100, 800, 400, 0),      # 上：y 100~500
                 mk_window(906, 300, 600, 800, 400, 1)])     # 下：y 600~1000
_dest, _dpos = _fm_d.get_drop_destination(QPoint(700, 700),
                                          _fm_d.get_floor_by_window(905))
ok('D5 get_drop_destination 行为仍按可见区域（下方那块看得见 → 被它接住）',
   _dest.get('window_hwnd') == 906 and _dpos == QPoint(700, 700),
   (_dest.get('window_hwnd'), _dpos))
_dest2, _ = _fm_d.get_drop_destination(QPoint(1200, 700),
                                       _fm_d.get_floor_by_window(905))
ok('D5b 下方没有任何可见楼板 → 落到桌面（不许悬空、也不许跨层抢接）',
   _dest2.get('type') == 'desktop', _dest2.get('type'))


def main():
    total = len(PASS) + len(FAIL)
    print('-' * 68)
    print('第十五轮建楼清理验证：%d/%d PASS, %d FAIL' % (len(PASS), total, len(FAIL)))
    for _n in FAIL:
        print('  FAIL: %s' % _n)
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())

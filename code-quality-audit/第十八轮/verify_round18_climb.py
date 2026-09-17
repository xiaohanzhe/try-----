# -*- coding: utf-8 -*-
"""第十八轮验证：「建楼」缺口计划 · 批次 B —— **层高闸门 + 攀爬衔接**（G3）。

背景
----
第十六轮只读复检列出 G3：`check_window_movement` 每拍把
`new_floor = get_current_floor(pos)` **直接赋值**，没有任何"层高差必须靠跳"的闸门 ——
宠物站在桌面（1楼）水平走进某个窗口的可见区域，会被**静默提升**到那一层：
不跳、不落、不摔，只是一个瞬时的层级跳变（并连带把 z 序抬上去）。

用户拍板（第十八轮原话，决定了本轮的语义）
------------------------------------------
  · "选1"（按字面收紧）→ 楼层层高变换必须靠跳来衔接；
  · "走进更低的楼层也是一样，反正只要是楼层高低变换就要通过跳来衔接"；
  · "注意，下楼的时候别用掉落，也用跳"；
  · "要预留一定距离哦，别看着和垂直起跳一样"；
  · "在楼层跨度较低的时候跳，跨度高的时候爬"；
  · "他也不能一次性跳上跨度很高的楼层，需要用各个方向的攀爬动画去切换高低楼层"；
  · "那个摔扁的机制需要在层数比较高且掉下来而非主动下来的时候才会触发哦"。

素材（用户指定，已由本轮登记进两张表）
--------------------------------------
  spr_ralsei_climb_1_*        → `climb_right`（朝右）
  spr_ralsei_climb_left_*     → `climb_left` = 上面那组的**水平镜像**（用户："相反方向的你
                                 就给他翻转一下就好"；由 `make_climb_left.py` 一次性生成）
  spr_ralsei_climb_0_degrees_* → `climb_front`（朝前）；没有朝后的（"那样也用不上"）

分组
----
  A 上楼：走进更高楼层 → **起跳**而不是被静默提升（并预留水平距离）
  B 跨度高：跨度 > 一层 → 用**攀爬素材**（跨度低才用 jump 家族）
  C 下楼：走进更低楼层 → **跳**而不是重力掉落（用户："下楼别用掉落"）
  D 被动成因不被误伤：关窗 / 新窗口盖住旧窗口（要求 ⑩/⑪）仍走原来的链路
  E 闸门兜底：起跳不可行时，上楼**不提升**、下楼**服从重力**
  F 摔扁门槛：只在"落差 ≥ 两层"时触发（用户："层数比较高且掉下来"）
  G 素材与登记：三组在两张表里、镜像素材真的落盘、缺素材时回落 jump 家族
  H 源码级：闸门与"跳还是爬"的选择都只有一处

本套件用**真 FloorManager 的几何**（visible_subrects / nearest_visible_point /
floor_visible_contains），只把 `update_floors`（会 Win32 枚举真窗口）冻结成空操作 ——
否则断言会随"跑测试这台机器上开着什么窗口"漂移。
必须用 C:\\Python311\\python.exe 运行。
"""
import io
import json
import os
import re as _re
import sys
import textwrap
import tokenize
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
for _p in (os.path.join(PET, 'src'), MODS):
    if _p not in sys.path:
        sys.path.append(_p)

from PyQt5.QtCore import QPoint, QRect                      # noqa: E402
from PyQt5.QtGui import QImage                              # noqa: E402
from PyQt5.QtWidgets import QApplication                    # noqa: E402

_app = QApplication.instance() or QApplication([])

import floor_manager as FM                                   # noqa: E402
from main import (RalseiPet, CLIMB_HORIZONTAL_RUN,           # noqa: E402
                  CLIMB_MIN_RESERVE, CLIMB_SPAN_JUMP_MAX,
                  FALL_SPLAT_MIN_DROP, FALL_SPLAT_HOLD,
                  _climb_animation_name, _jump_kind_for_span, _jump_hdir_for,
                  _landing_drop_height, _should_splat_on_landing)

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
MAIN_TEXT = io.open(MAIN_PY, encoding='utf-8').read()

_DROP = (tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE,
         tokenize.INDENT, tokenize.DEDENT)
_DROP_COMMENT = (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                 tokenize.INDENT, tokenize.DEDENT)


def _tokens(src, drop):
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in drop:
                continue
            out.append(tok.string)
    except Exception:
        return ''
    return ' '.join(out)


def flat(s):
    return _re.sub(r'\s+', '', s or '')


def has_flat(hay, needle):
    return flat(needle) in flat(hay)


def _method_raw(name, text=MAIN_TEXT):
    import ast
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return textwrap.dedent(ast.get_source_segment(text, node) or '')
    return None


def func_code(name):
    """方法体的"剥注释+字符串"文本（序列敏感断言用）。"""
    return _tokens(_method_raw(name), _DROP)


def func_lit(name):
    """方法体的"只剥注释"文本（找字符串字面量 needle 用 —— 见 MEMORY 验证脚本教训）。"""
    return _tokens(_method_raw(name), _DROP_COMMENT)


# ---------------------------------------------------------------- 环境与桩
SCREEN = QRect(0, 0, 1920, 1080)
PET_W, PET_H = 136, 71


class StaticFM(FM.FloorManager):
    """真 FloorManager 的几何 + **冻结**的楼层表。

    `update_floors()` 会走 Win32 枚举真实窗口 → 回归里必须冻结成空操作，
    否则断言随"测试机上开着什么窗口"漂移。其余几何（visible_subrects /
    nearest_visible_point / floor_visible_contains / adjacent_lower_floor）
    全是真实现 —— 本套件要验的正是它们与闸门的接线。
    """

    def __init__(self, windows):
        super().__init__(parent=None)
        self.underlying_windows = list(windows)
        self.desktop_floor['rect'] = QRect(SCREEN)
        self._generate_floors()

    def update_floors(self):
        pass


def mk_window(hwnd, x, y, w, h, z, title='w'):
    return {'hwnd': hwnd, 'title': title, 'class_name': 'C',
            'rect': QRect(x, y, w, h), 'z_order': z}


def floor_of(fm, hwnd):
    f = fm.get_floor_by_window(hwnd)
    assert f is not None, 'hwnd %r 没成为楼层（合成几何写错了？）' % hwnd
    return f


def in_visible(floor, pos):
    return FM.FloorManager.floor_visible_contains(floor, pos)


SPRITES = {'climb_right': 1, 'climb_left': 1, 'climb_front': 1,
           'jump': 1, 'jump_ready': 1, 'jump_ball': 1, 'land': 1, 'idle': 1,
           'fall': 1, 'splat': 1, 'splat_mad': 1}


class MoveStub:
    """驱动真 `check_window_movement` + 真楼层几何的最小表面。

    `is_moving=True` 是"宠物自己走过去"的信号（闸门的入口条件）——
    它是**既有属性**，不需要为闸门新增任何属性（历史轻量桩没有它 → 不进闸门）。
    """

    def __init__(self, fm, x, y, current_floor=None, is_moving=True,
                 direction='right', sprites=None):
        self.floor_manager = fm
        self._x, self._y = int(x), int(y)
        self._spell_stage = None
        self.game_state = {'is_playing': False}
        self.is_falling = False
        self.is_gravity_falling = False
        self.is_jumping = False
        self._is_being_dragged = False
        self.is_moving = is_moving
        self.previous_direction = direction
        self.current_floor = current_floor if current_floor is not None \
            else fm.get_current_floor(QPoint(self._x, self._y))
        self.current_window = None
        self.window_level = 0
        self.last_window_rect = None
        self.current_platform_z = (self.current_floor or {}).get('platform_height', 0)
        self.spatial_pos = {'x': self._x, 'y': self._y, 'z': self.current_platform_z}
        # 跳跃状态机
        self.jump_count = 0
        self.max_jumps = 3
        self.jump_cooldown = 0.0
        self.last_jump_time = 0.0
        self.needs_rest = False
        self.rest_duration = 1.0
        self.resting_time = 0
        self.jump_duration = 1.0
        self.has_ball = False
        self.gravity = 900.0
        self.anim_calls = []
        self.calls = []
        self.sprite_loader = types.SimpleNamespace(
            sprites=dict(SPRITES if sprites is None else sprites))
        self.emotion_system = types.SimpleNamespace(react_to_event=lambda e, d: None)

    # --- 位置/尺寸 ---
    def pos(self):
        return QPoint(self._x, self._y)

    def width(self):
        return PET_W

    def height(self):
        return PET_H

    def move(self, x, y):
        self._x, self._y = int(x), int(y)

    def show(self):
        pass

    def _clamp_pos_to_desktop(self, x, y):
        return (max(SCREEN.left(), min(int(x), SCREEN.right() - PET_W)),
                max(SCREEN.top(), min(int(y), SCREEN.bottom() - PET_H)))

    def change_animation(self, name, *a, **k):
        self.anim_calls.append(name)

    def play_animation_once(self, name, restore_to=None, **k):
        self.anim_calls.append(('once', name))

    def _apply_pet_z_order(self):
        return False

    # --- 被动成因的观察点（闸门若误接管，这两个就会被调用）---
    def start_falling(self, fall_velocity=0, is_thrown=False, reason=None):
        self.calls.append(('start_falling', reason))
        self.is_gravity_falling = True

    def start_fall(self, reason="window_move"):
        self.calls.append(('start_fall', reason))
        self.is_falling = True

    # --- 真方法绑定 ---
    _floor_identity_key = staticmethod(RalseiPet._floor_identity_key)
    _floor_rect_changed = staticmethod(RalseiPet._floor_rect_changed)

    def _sync_window_cache_from_floor(self, floor):
        return RalseiPet._sync_window_cache_from_floor(self, floor)

    def _follow_floor_move(self, old, moved):
        return RalseiPet._follow_floor_move(self, old, moved)

    def _climb_hdir(self, fm, tf):
        return RalseiPet._climb_hdir(self, fm, tf)

    def _climb_probe_landing(self, fm, tf, probe, cur):
        return RalseiPet._climb_probe_landing(self, fm, tf, probe, cur)

    def _climb_landing(self, fm, tf):
        return RalseiPet._climb_landing(self, fm, tf)

    def _start_climb_transition(self, old_floor, new_floor):
        return RalseiPet._start_climb_transition(self, old_floor, new_floor)

    def _start_floor_jump(self, floor, edge, land):
        return RalseiPet._start_floor_jump(self, floor, edge, land)

    def start_jump(self, target_window, window_edge, target_floor=None, target_pos=None):
        return RalseiPet.start_jump(self, target_window, window_edge,
                                    target_floor=target_floor, target_pos=target_pos)

    check_window_movement = RalseiPet.check_window_movement

    # --- 断言辅助 ---
    def jumped(self):
        return bool(self.is_jumping)

    def fell(self):
        return [c for c in self.calls if c[0] in ('start_falling', 'start_fall')]


def run(stub):
    stub.calls = []
    stub.anim_calls = []
    RalseiPet.check_window_movement(stub)
    return stub


# ============================================================ A 上楼：起跳，不是静默提升
section('A 上楼：走进更高楼层 → **起跳**而不是被静默提升（G3 本体）')

_w201 = mk_window(201, 200, 200, 1200, 700, 1)          # 唯一窗口 → 楼 2（ph=5）
_fm_a = StaticFM([_w201])
_f201 = floor_of(_fm_a, 201)
_pet_a = MoveStub(_fm_a, 500, 500, current_floor=_fm_a.desktop_floor,
                  is_moving=True, direction='right')
run(_pet_a)
ok('A1 走上更高楼板 → 真的起跳（is_jumping=True）',
   _pet_a.jumped() is True, 'is_jumping=%r calls=%r' % (_pet_a.is_jumping, _pet_a.calls))
ok('A2 **没有静默提升**：current_floor 仍是桌面（缺口 G3：改前这里会被直接赋值成 201 那层）',
   _pet_a.current_floor is _fm_a.desktop_floor,
   'current_floor=%r' % (_pet_a.current_floor,))
ok('A3 跳跃目标 = 那块窗口的**楼层**（不是裸窗口/桌面）',
   _pet_a.jump_target_floor is _f201,
   'target=%r' % (_pet_a.jump_target_floor,))
ok('A4 落点落在目标层的**可见区域**内',
   in_visible(_f201, _pet_a.jump_target_pos),
   'land=%s visible=%s' % (_pet_a.jump_target_pos, _f201.get('visible_rects')))
ok('A5 落点与宠物**预留了水平距离**（用户："别看着和垂直起跳一样"）',
   abs(_pet_a.jump_target_pos.x() - 500) >= CLIMB_MIN_RESERVE,
   'dx=%s（要求 ≥%s）' % (abs(_pet_a.jump_target_pos.x() - 500), CLIMB_MIN_RESERVE))
ok('A6 本拍**没有**触发任何坠落（起跳与坠落互斥）',
   not _pet_a.fell(), _pet_a.calls)

# ============================================================ B 跨度高 → 攀爬素材
section('B 跨度高：跨度 > 一层 → 用攀爬素材（用户："跨度低跳、跨度高爬"）')

_w203 = mk_window(203, 1200, 100, 600, 800, 2)          # 靠后 → ph=5
_w204 = mk_window(204, 200, 100, 800, 800, 1)           # 最前 → ph=10
_fm_b = StaticFM([_w203, _w204])
_f204 = floor_of(_fm_b, 204)
ok('B0 前置：合成几何给出 ph=10 的目标层（跨度 10 > %s → 该用"爬"）'
   % CLIMB_SPAN_JUMP_MAX,
   _f204.get('platform_height') == 10, _f204.get('platform_height'))
_pet_b = MoveStub(_fm_b, 400, 400, current_floor=_fm_b.desktop_floor,
                  is_moving=True, direction='right')
run(_pet_b)
ok('B1 跨度 10 → 起跳第一帧就用**攀爬素材** climb_right（不是 jump_ready）',
   _pet_b.anim_calls[:1] == ['climb_right'],
   'anims=%r override=%r' % (_pet_b.anim_calls[:3],
                             getattr(_pet_b, '_jump_anim_override', None)))
ok('B2 覆盖标记被记住（handle_jump 每帧据此保持攀爬素材，而不是被 jump 顶掉）',
   getattr(_pet_b, '_jump_anim_override', None) == 'climb_right',
   getattr(_pet_b, '_jump_anim_override', None))
ok('B3 跨度低（≤一层）→ 仍用 jump 家族（不能把所有跳跃都换成爬）',
   _jump_kind_for_span(CLIMB_SPAN_JUMP_MAX) == 'jump'
   and _jump_kind_for_span(0) == 'jump'
   and _jump_kind_for_span(-5) == 'jump',
   (_jump_kind_for_span(CLIMB_SPAN_JUMP_MAX), _jump_kind_for_span(-5)))
ok('B4 跨度高（>一层）→ 判为 climb（上、下两个方向都算）',
   _jump_kind_for_span(CLIMB_SPAN_JUMP_MAX + 5) == 'climb'
   and _jump_kind_for_span(-(CLIMB_SPAN_JUMP_MAX + 5)) == 'climb',
   (_jump_kind_for_span(10), _jump_kind_for_span(-10)))
ok('B5 爬向选型：横向为主 → left/right；无横向位移 → front（没有朝后的素材）',
   _jump_hdir_for(QPoint(0, 0), QPoint(80, 0)) == 'right'
   and _jump_hdir_for(QPoint(0, 0), QPoint(-80, 0)) == 'left'
   and _jump_hdir_for(QPoint(0, 0), QPoint(0, 80)) == 'front'
   and _jump_hdir_for(QPoint(0, 0), QPoint(2, 0)) == 'front',
   (_jump_hdir_for(QPoint(0, 0), QPoint(80, 0)),
    _jump_hdir_for(QPoint(0, 0), QPoint(0, 80))))

# ============================================================ C 下楼：跳，不是掉
section('C 下楼：走进更低楼层 → **跳**而不是重力掉落（用户："下楼别用掉落，也用跳"）')

_w205 = mk_window(205, 100, 100, 1600, 900, 2)          # 靠后 → ph=5
_w206 = mk_window(206, 300, 200, 1000, 600, 1)          # 最前 → ph=10，压住 205 中部
_fm_c = StaticFM([_w205, _w206])
_f205 = floor_of(_fm_c, 205)
_f206 = floor_of(_fm_c, 206)
# 宠物在 205 的**可见**区域里（右侧条带，不被 206 压住）→ get_current_floor 命中 205
_pet_c = MoveStub(_fm_c, 1400, 500, current_floor=_f206,
                  is_moving=True, direction='right')
ok('C0 前置：宠物站位命中 ph=5 的更低楼层、出发层是 ph=10',
   _fm_c.get_current_floor(QPoint(1400, 500)).get('platform_height') == 5
   and _f206.get('platform_height') == 10,
   (_fm_c.get_current_floor(QPoint(1400, 500)).get('platform_height'),
    _f206.get('platform_height')))
run(_pet_c)
ok('C1 走进更低楼层 → **起跳**（is_jumping=True）',
   _pet_c.jumped() is True, 'jumping=%r calls=%r' % (_pet_c.is_jumping, _pet_c.calls))
ok('C2 **没有**走重力掉落（用户口径：主动下楼不用掉落）',
   not _pet_c.fell(), _pet_c.calls)
ok('C3 目标是那块更低的楼板（ph 5），且落点在它的可见区域里',
   _pet_c.jump_target_floor is _f205
   and in_visible(_f205, _pet_c.jump_target_pos),
   'target=%r land=%s' % ((_pet_c.jump_target_floor or {}).get('window_hwnd'),
                          _pet_c.jump_target_pos))
ok('C4 下落方向被正确识别为"往下"（jump_target_z 更低）',
   _pet_c.jump_target_z < _pet_c.jump_start_spatial['z'],
   (_pet_c.jump_target_z, _pet_c.jump_start_spatial.get('z')))
ok('C5 下楼也预留水平距离',
   abs(_pet_c.jump_target_pos.x() - 1400) >= CLIMB_MIN_RESERVE,
   'dx=%s' % abs(_pet_c.jump_target_pos.x() - 1400))

# ============================================================ D 被动成因不被误伤
section('D 被动成因不被误伤：关窗（要求⑩）/ 新窗口盖住旧窗口（要求⑪）')

# D1/D2：关窗 = 旧楼板失效 → 闸门**不许**接管（无论宠物是否在走路）
for _moving in (False, True):
    _w209 = mk_window(209, 200, 200, 1200, 700, 1)
    _fm_d = StaticFM([_w209])
    _f209 = floor_of(_fm_d, 209)
    _pet_d = MoveStub(_fm_d, 500, 500, current_floor=_f209, is_moving=_moving)
    _fm_d.underlying_windows = []       # 用户关掉了窗口
    _fm_d.floors = []
    run(_pet_d)
    ok('D%s 关窗（旧楼板失效，is_moving=%s）→ 仍是 start_falling(reason='
       '"floor_removed")，闸门不接管' % (1 if not _moving else 2, _moving),
       ('start_falling', 'floor_removed') in _pet_d.calls and not _pet_d.jumped(),
       _pet_d.calls)

# D3：要求⑪ —— 新窗口盖住旧窗口（宠物没走路）→ 直接站新板，不跳不掉
_w210 = mk_window(210, 100, 100, 1200, 800, 2)
_fm_d3 = StaticFM([_w210])
_f210 = floor_of(_fm_d3, 210)
_pet_d3 = MoveStub(_fm_d3, 500, 500, current_floor=_f210, is_moving=False)
_fm_d3.underlying_windows = [_w210, mk_window(211, 200, 200, 1000, 600, 1)]
_fm_d3._generate_floors()
_f211 = floor_of(_fm_d3, 211)
run(_pet_d3)
ok('D3 被更高的新窗口盖住（要求⑪，宠物没走路）→ 不跳不掉，直接站新板',
   (not _pet_d3.jumped()) and (not _pet_d3.fell())
   and _pet_d3.current_floor is _f211,
   'jumping=%r calls=%r floor=%r' % (_pet_d3.is_jumping, _pet_d3.calls,
                                     (_pet_d3.current_floor or {}).get('window_hwnd')))

# ============================================================ E 闸门兜底
section('E 闸门兜底：起跳不可行时，上楼**不提升**、下楼**服从重力**')

# E1：上楼但衔接够不着 → 保持原楼层（"静默提升"不能当兜底）
_w212 = mk_window(212, 200, 200, 1200, 700, 1)
_fm_e1 = StaticFM([_w212])
_pet_e1 = MoveStub(_fm_e1, 500, 500, current_floor=_fm_e1.desktop_floor,
                   is_moving=True)
_pet_e1._start_climb_transition = lambda old, new: False     # 模拟"够不着"
run(_pet_e1)
ok('E1 上楼衔接不可行 → **保持原楼层**、不起跳（不能退回"静默提升"）',
   _pet_e1.current_floor is _fm_e1.desktop_floor
   and not _pet_e1.jumped() and not _pet_e1.fell(),
   'floor=%r jumping=%r calls=%r' % (_pet_e1.current_floor, _pet_e1.is_jumping,
                                     _pet_e1.calls))

# E2：下楼且衔接够不着 → 服从重力（要求⑭："脚下没东西了就该直直掉下去"）
_w213 = mk_window(213, 100, 100, 1600, 900, 2)
_w214 = mk_window(214, 300, 200, 1000, 600, 1)
_fm_e2 = StaticFM([_w213, _w214])
_f214 = floor_of(_fm_e2, 214)
_pet_e2 = MoveStub(_fm_e2, 1400, 500, current_floor=_f214, is_moving=True)
_pet_e2._start_climb_transition = lambda old, new: False
run(_pet_e2)
ok('E2 下楼衔接不可行 → 走重力掉落（不带"用户行为"起因）',
   ('start_falling', None) in _pet_e2.calls
   and not any(c == ('start_falling', 'floor_removed') for c in _pet_e2.calls),
   _pet_e2.calls)

# ============================================================ F 摔扁门槛
section('F 摔扁门槛：只在"层数比较高"时触发（用户第十八轮口径）')


class SplatPet:
    """`_should_splat_on_landing` 的最小表面。"""

    def __init__(self, from_h, speed):
        self.current_floor = {'platform_height': from_h}
        self._fall_from_height = from_h
        self.fall_speed = speed


_desk = {'type': 'desktop', 'platform_height': 0}


def mk_floor(h):
    return {'type': 'window', 'platform_height': h}


ok('F1 落差一层（5）+ 高速 → **不**摔扁（"层数比较高"不成立）',
   _should_splat_on_landing(SplatPet(5, 300), _desk) is False,
   _landing_drop_height(SplatPet(5, 300), _desk))
ok('F2 落差两层（10）+ 高速 → 摔扁（门槛 = %s）' % FALL_SPLAT_MIN_DROP,
   _should_splat_on_landing(SplatPet(10, 300), _desk) is True,
   _landing_drop_height(SplatPet(10, 300), _desk))
ok('F3 落点**不是桌面**（25 → 10，落差两层）→ 也摔扁（不只"掉到桌面"才算）',
   _should_splat_on_landing(SplatPet(25, 300), mk_floor(10)) is True,
   _landing_drop_height(SplatPet(25, 300), mk_floor(10)))
ok('F4 速度不够（≤150）→ 不摔扁（沿用改前口径，不引入新手感变量）',
   _should_splat_on_landing(SplatPet(15, 100), _desk) is False,
   _should_splat_on_landing(SplatPet(15, 100), _desk))
ok('F5 落差为 0（同一层"落地"）→ 不摔扁',
   _should_splat_on_landing(SplatPet(0, 300), _desk) is False,
   _landing_drop_height(SplatPet(0, 300), _desk))
ok('F6 缺 `_fall_from_height` 时按 0 处理（防御：不因缺属性抛异常）',
   _landing_drop_height(types.SimpleNamespace(), mk_floor(10)) == 0,
   _landing_drop_height(types.SimpleNamespace(), mk_floor(10)))
ok('F7 落差**夹到 ≥0**（落点比起点还高时不能交出负的"落差"）',
   _landing_drop_height(types.SimpleNamespace(), mk_floor(50)) == 0,
   _landing_drop_height(types.SimpleNamespace(), mk_floor(50)))

# ============================================================ G 素材与登记
section('G 素材与登记（用户指定的三组攀爬素材）')

JSON_PATH = os.path.join(PET, 'assets', 'animations.json')
with io.open(JSON_PATH, encoding='utf-8') as _fh:
    _doc = json.load(_fh)
_groups = _doc['groups']
for _name, _expect in (('climb_right', 'spr_ralsei_climb_1_0.png'),
                       ('climb_left', 'spr_ralsei_climb_left_0.png'),
                       ('climb_front', 'spr_ralsei_climb_0_degrees_0.png')):
    _fr = _groups.get(_name, {}).get('frames') or []
    ok('G 动画组 %s 已登记且首帧 = %s（%d 帧）' % (_name, _expect, len(_fr)),
       bool(_fr) and _fr[0] == _expect, _fr)

_SPRITE_DIR = os.path.join(ROOT, 'deltarune_ralsei')
# 注意：这里必须**先展平再筛**。写成 `[n for n in (f() for n in n) if ...]`
# 会让内层 `for n in n` 引用一个尚未绑定的 n（NameError: name 'n' is not defined），
# 而且报错点落在列表推导里，traceback 只指向行号、看不出是"手滑多打了一层"。
_CLIMB_FRAMES = [n for _g in ('climb_right', 'climb_left', 'climb_front')
                 for n in (_groups.get(_g, {}).get('frames') or [])]
_missing = [n for n in _CLIMB_FRAMES
            if not os.path.exists(os.path.join(_SPRITE_DIR, n))]
ok('G4 三组用到的素材**全部在磁盘上**（含 5 张镜像生成的 climb_left）',
   not _missing, '缺失=%s' % (_missing[:6],))
ok('G5 climb_left 的帧与 climb_right 的帧**不是同一批文件**（镜像必须真落盘，'
   '不能靠 alias_of 顶替）',
   set(_groups['climb_left']['frames']) != set(_groups['climb_right']['frames']), None)

# 桩的形状必须与产品一致：`_climb_animation_name` 读的是
# `pet.sprite_loader.sprites`（**嵌套**）。这里原来写成扁平的
# `SimpleNamespace(sprites=...)` → 函数取到 `sprites=None` → **恒返回 None**。
# 后果不只是 G6 红：G7（"素材不在库 → None"）会**假绿** —— 它在桩形状错的
# 情况下必然通过，等于没测。配对的正/负控制（G6 正、G7 负）正是用来抓这种事的：
# 只留负控制，这种"测试自己坏了"的状态可以一直绿下去。
_loader = types.SimpleNamespace(sprite_loader=types.SimpleNamespace(sprites=dict(SPRITES)))
_G6_L, _G6_F = (_climb_animation_name(_loader, 'left'),
                _climb_animation_name(_loader, 'front'))
ok('G6 素材在库 → 返回对应爬向的素材名',
   _G6_L == 'climb_left' and _G6_F == 'climb_front',
   'left=%r front=%r sprite_keys=%s' % (
       _G6_L, _G6_F, sorted(_loader.sprite_loader.sprites)[:8]))
ok('G7 素材**不在库**（旧素材包）→ 返回 None，调用方回落 jump 家族（不切灰块）',
   _climb_animation_name(types.SimpleNamespace(
       sprite_loader=types.SimpleNamespace(sprites={'jump': 1, 'jump_ready': 1})),
       'right') is None
   and _climb_animation_name(types.SimpleNamespace(
       sprite_loader=types.SimpleNamespace(sprites={})), 'right') is None, None)
ok('G8 未知方向 → 退到 front（不抛 KeyError）',
   _climb_animation_name(_loader, 'up') == 'climb_front',
   'up=%r' % (_climb_animation_name(_loader, 'up'),))
ok('G9 完全**没有** sprite_loader 属性 → 也不抛异常（返回 None 回落 jump）',
   _climb_animation_name(types.SimpleNamespace(), 'right') is None, None)


def _mirror_sample_bad(a, b):
    """b 与 a 的水平镜像关系有多少个采样点不符（-1 = 尺寸不同）。"""
    w, h = a.width(), a.height()
    if (b.width(), b.height()) != (w, h):
        return -1
    bad = 0
    for xi in range(5):
        x = min(w - 1, int(xi * (w - 1) / 4))
        for yi in range(5):
            y = min(h - 1, int(yi * (h - 1) / 4))
            if b.pixel(x, y) != a.pixel(w - 1 - x, y):
                bad += 1
    return bad


# G10：把"朝左 = 朝右的镜像"从"生成脚本里的一次性检查"升级成**回归锁**。
# 只断言"左右两组文件名不同"（G5）**不够** —— 把源图**原样复制**过去也满足 G5，
# 而那正是唯一要防的事（没镜像）。所以这里逐像素断言镜像关系：
# 采 5x5 个点比较 `left(x,y) == right(w-1-x, y)`。
_R_FRAMES = _groups['climb_right']['frames']
_L_FRAMES = _groups['climb_left']['frames']
_bad_pairs = []
for _i, (_pr, _pl) in enumerate(zip(_R_FRAMES, _L_FRAMES)):
    _a = QImage(os.path.join(_SPRITE_DIR, _pr))
    _b = QImage(os.path.join(_SPRITE_DIR, _pl))
    if _a.isNull() or _b.isNull() or _mirror_sample_bad(_a, _b) != 0:
        _bad_pairs.append(_i)
ok('G10 climb_left 每帧都是 climb_right 对应帧的**严格水平镜像**'
   '（逐像素采样；"原样复制"会被这条抓住）',
   len(_R_FRAMES) == len(_L_FRAMES) and not _bad_pairs,
   '帧数 %d/%d 不符点帧=%s' % (len(_R_FRAMES), len(_L_FRAMES), _bad_pairs))
# G10 自检：把拿到的图**故意翻转两次**（等于原图）应当**不**满足镜像关系 ——
# 除非图像左右对称。取一张左右明显不对称的（否则这条自检本身没鉴别力）。
_a0 = QImage(os.path.join(_SPRITE_DIR, _R_FRAMES[0]))
_DBL = _a0.mirrored(True, False).mirrored(True, False)
ok('G10b 自检：该判据对"未镜像的同一张图"必须报不符（否则它是恒真的假绿）',
   _mirror_sample_bad(_a0, _DBL) != 0 or _a0.width() < 3,
   '不符点数=%s' % (_mirror_sample_bad(_a0, _DBL),))

# ============================================================ H 源码级
section('H 源码级：闸门与"跳还是爬"各只有一处')

# X0 自检：两个源码视图的语义差别必须成立，否则下面 H 组全是"假绿/假红"。
# 这是第八轮"验证脚本教训"的固化 —— 自查工具本身也要有断言。
_TOOL_SRC = "y = getattr(self, 'zzz', None)  # 注释 aaa"
ok('X0 源码视图自检：func_code 剥字符串字面量 / func_lit 保留；两者都剥注释',
   (not has_flat(_tokens(_TOOL_SRC, _DROP), "'zzz'"))
   and has_flat(_tokens(_TOOL_SRC, _DROP_COMMENT), "'zzz'")
   and (not has_flat(_tokens(_TOOL_SRC, _DROP), 'aaa'))
   and (not has_flat(_tokens(_TOOL_SRC, _DROP_COMMENT), 'aaa')), None)

_cwm = func_code('check_window_movement')
ok('H1 `check_window_movement` 里真的调了层高闸门 `_start_climb_transition`',
   has_flat(_cwm, '_start_climb_transition(old_floor,new_floor)'), None)
ok('H2 闸门的入口条件用了既有属性 `is_moving`（不为闸门新增状态）',
   has_flat(func_lit('check_window_movement'), "getattr(self,'is_moving',False)"), None)
ok('H3 闸门对"上楼够不着"的处理是**保持原楼层**（return 而不是赋值提升）',
   has_flat(_cwm, 'ifwalk_inducedandnew_h>old_h:'), None)
ok('H4 "跳还是爬"只在 start_jump 里选一次（两条入口共用，不各写一份）',
   has_flat(func_code('start_jump'), '_jump_kind_for_span(_span)')
   and has_flat(func_lit('start_jump'), '_climb_animation_name'),
   None)
# H5 落进过"验证脚本教训"的坑，记录口径：`func_code` 会把**字符串字面量**一起剥掉，
# 而 `getattr(self,'_jump_anim_override',None)` 的 needle 里恰恰有一个字符串字面量
# （属性名 `'_jump_anim_override'`）→ 剥完变成 `getattr(self,,None)`，**永远搜不到**
# → 假 FAIL。所以"含字符串字面量的 needle 一律走 func_lit（只剥注释）"，
# 再用一个**不含任何字符串**的 needle 在 func_code 上补一刀，两边互证。
ok('H5 `handle_jump` 尊重 `_jump_anim_override`（否则每帧被 jump 顶掉 = 白切）',
   has_flat(func_lit('handle_jump'), "getattr(self,'_jump_anim_override',None)")
   and has_flat(func_code('handle_jump'),
                'if_override:self.change_animation(_override,force=True)'),
   None)
ok('H6 摔扁判定收敛成唯一入口 `_should_splat_on_landing`（不再有裸的 fall_speed > 150）',
   has_flat(func_code('handle_gravity_fall'), '_should_splat_on_landing(')
   and not has_flat(func_code('handle_gravity_fall'), 'ifself.fall_speed>150:'),
   None)
ok('H7 起跳楼层与目标楼层都能在 `start_jump` 里看到（单点选型的前提）',
   has_flat(func_lit('start_jump'), "getattr(self,'jump_target_floor',None)")
   and has_flat(func_lit('start_jump'), "getattr(self,'current_floor',None)"),
   None)
ok('H8 `_start_climb_transition` 只走楼层跳跃链路（不碰 start_falling）',
   not has_flat(func_code('_start_climb_transition'), 'start_falling('), None)
ok('H9 第十二轮起的"生气动画时长"契约没被本轮动过',
   FALL_SPLAT_HOLD.get('floor_removed') == 5.0
   and FALL_SPLAT_HOLD.get('window_move') == 3.0, None)

# ============================================================ I 设计前提
section('I 设计前提：为什么"跨层拆成逐层小跳"在这套几何下不可行（勿回退的依据）')

# `_start_climb_transition` 的 docstring 写了"不把跨层拆成逐层小跳"的理由：楼层名次
# 就是 z 序，宠物会被判到第 N 层，正因为它的位置落在**最前面**那块楼板的可见区域里
# —— 而那正是后面的低层被挡住的地方，低层在该位置**没有可见区域** → 逐层的第一步
# 就无处落脚 → 每步都 False → 宠物永远上不去（"进不去窗口"，比改前更糟）。
# 这条断言把该前提钉住：谁动了几何/名次/可见区域口径，这里先红，提醒回头读注释。
_w220 = mk_window(220, 100, 100, 1400, 900, 2)   # 后面那层（名次较低）
_w221 = mk_window(221, 300, 200, 800, 500, 1)    # 前面那层（名次较高，且盖住 _w220 的一块）
_fm_i = StaticFM([_w220, _w221])
_f220 = floor_of(_fm_i, 220)
_f221 = floor_of(_fm_i, 221)
_pos_i = QPoint(_f221['rect'].center().x(), _f221['rect'].top() + 10)
ok('I1 站在前层可见区域里的位置，**同一位置的下层没有可见区域**'
   '（逐层小跳的第一步将无处落脚）',
   in_visible(_f221, _pos_i) and not in_visible(_f220, _pos_i),
   'pos=%s 前层可见=%s 下层可见=%s' % (_pos_i, in_visible(_f221, _pos_i),
                                       in_visible(_f220, _pos_i)))
ok('I2 两层名次确实不同（本断言的前提：前层更高）',
   (_f221.get('platform_height', 0) or 0) > (_f220.get('platform_height', 0) or 0),
   '%s vs %s' % (_f221.get('platform_height'), _f220.get('platform_height')))

# ---------------------------------------------------------------- 汇总
print('')
print('=' * 60)
print('第十八轮（批次 B）：PASS=%d FAIL=%d' % (len(PASS), len(FAIL)))
for _f in FAIL:
    print('  [FAIL] ' + _f)
print('=' * 60)
sys.exit(1 if FAIL else 0)

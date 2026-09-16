# -*- coding: utf-8 -*-
"""第十四轮验证：「建楼」的**上下动**（跨楼层移动）——把可见区域判据接进产品路径。

为什么要单开这一轮
------------------
第十三轮把 `floor_manager` 里的判据全换成了"可见区域"（`visible_subrects` /
`floor_visible_contains` / `get_jump_destinations` / `find_support_below`），
套件 C 段也确实在测这些函数 —— **但产品代码一个都没调用**：

  · 真正决定"跳不跳、跳去哪"的是 `main.py::check_nearby_windows`，
    它用的是**裸窗口矩形**（`window['x'/'y'/'width'/'height']`）+ 10~30px 贴边启发式；
  · `check_window_movement` / `update_floor` 只更新 `current_floor`，从不更新
    `self.current_window` —— 而 `check_nearby_windows` 读的偏偏是 `current_window`。
    （"当前站在哪"于是有两份状态，两份还不一致。）

结果就是两条"建楼"要求**在真机上根本没生效**：
  ① "向上跳：只能跳到这个窗口**没被其他东西挡住**的那部分边缘上"
     —— 老逻辑不看可见区域，能跳到被盖住的部分；
  ② "向下跳：如果它站在3楼，想回桌面（1楼），必须先跳到2楼……
     不能直接从3楼穿透2楼跳到1楼"
     —— 老逻辑站在窗口上时把目标**直接声明成桌面**，等于朝 1 楼跳；
     `handle_jump` 的穿透检查会把它打断成"取消跳跃 + 自由落体"（硬着陆）。

本轮做的事（见报告 §三）
------------------------
  · `main.py` 新增 `_floors_for_jump` / `_visible_landing` / `_floor_entry_plan` /
    `_nearest_floor_jump` / `_start_floor_jump` / `_sync_window_cache_from_floor`；
  · `check_nearby_windows`：楼层系统可用时**只**由楼层回答跳不跳（不回落裸矩形）；
  · `start_jump` 增加 `target_floor` / `target_pos`（落点由可见区域给定，不再反推）；
  · `floor_manager` 新增 `adjacent_lower_floor` / `nearest_visible_point`。

分组
----
  A 接线（防"改了没人调用"复演：行为级证明产品真走了楼层判定）
  B 向上跳的落点必须在**可见区域**内
  C 向下跳只能到**相邻下一层**（禁穿透）
  D `current_window` 与 `current_floor` 单真源同步
  E floor_manager 新增契约（相邻层 / 可见吸附）
  F 源码级不变量（不该再出现的旧写法）

本套件不需要真窗口（全用合成窗口表 + 真 FloorManager），结果确定可复现。
必须用 C:\\Python311\\python.exe 运行。
"""
import io
import os
import sys
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


def code_only(path):
    out = []
    try:
        with io.open(path, 'rb') as fh:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type in (tokenize.COMMENT, tokenize.STRING):
                    continue
                out.append(tok.string)
    except Exception:
        return ''
    return ' '.join(out)


def flat(src):
    import re
    return re.sub(r'\s+', '', src)


def has(src, needle):
    return flat(needle) in flat(src)


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


def floor_of(fm, hwnd):
    f = fm.get_floor_by_window(hwnd)
    assert f is not None, 'hwnd %r 没成为楼层（合成几何写错了？）' % hwnd
    return f


def in_visible(floor, pos):
    return FM.FloorManager.floor_visible_contains(floor, pos)


class PetStub:
    """只装 `check_nearby_windows` → 楼层规划 → `start_jump` 这条链真正用到的属性。

    刻意**不提供** `desktop_interaction`：楼层可用时这条路不该再去枚举裸窗口表，
    缺属性本身就能把"偷偷回落旧逻辑"变成 AttributeError（见 A2）。
    """

    def __init__(self, fm, x, y, current_floor=None):
        self.floor_manager = fm
        self._x, self._y = int(x), int(y)
        self._spell_stage = None
        self.game_state = {'is_playing': False}
        self.is_jumping = False
        self.is_falling = False
        self.is_gravity_falling = False
        self.current_floor = current_floor if current_floor is not None \
            else fm.get_current_floor(QPoint(self._x, self._y))
        self.current_window = None
        self.window_level = 0
        self.last_window_rect = None
        self.current_platform_z = 0
        self.spatial_pos = {'x': self._x, 'y': self._y, 'z': 0}
        # 跳跃状态机所需
        self.jump_count = 0
        self.max_jumps = 3
        self.jump_cooldown = 0.0
        self.last_jump_time = 0.0
        self.needs_rest = False
        self.rest_duration = 1.0
        self.resting_time = 0
        self.jump_duration = 1.0
        self.anim_calls = []
        # 真方法绑定（静态方法在本类上是普通函数，直接挂）
        self._floor_identity_key = RalseiPet._floor_identity_key
        self._sync_window_cache_from_floor = (
            lambda floor: RalseiPet._sync_window_cache_from_floor(self, floor))

    def pos(self):
        return QPoint(self._x, self._y)

    def width(self):
        return PET_W

    def height(self):
        return PET_H

    def move(self, x, y):
        self._x, self._y = int(x), int(y)

    def change_animation(self, name, *a, **k):
        self.anim_calls.append(name)

    def _clamp_pos_to_desktop(self, x, y):
        x = max(SCREEN.left(), min(int(x), SCREEN.right() - PET_W))
        y = max(SCREEN.top(), min(int(y), SCREEN.bottom() - PET_H))
        return x, y

    # 实例方法（非 static）必须用 MethodType 语义绑到本 stub 上
    def _floors_for_jump(self):
        return RalseiPet._floors_for_jump(self)

    def _visible_landing(self, fm, floor, pos):
        return RalseiPet._visible_landing(self, fm, floor, pos)

    def _floor_entry_plan(self, fm, floor, ralsei_rect, cur_floor=None):
        return RalseiPet._floor_entry_plan(self, fm, floor, ralsei_rect, cur_floor)

    def _nearest_floor_jump(self, fm, cur_floor, ralsei_rect):
        return RalseiPet._nearest_floor_jump(self, fm, cur_floor, ralsei_rect)

    def _start_floor_jump(self, floor, edge, land):
        return RalseiPet._start_floor_jump(self, floor, edge, land)

    def check_nearby_windows(self, current_pos):
        return RalseiPet.check_nearby_windows(self, current_pos)

    def start_jump(self, target_window, window_edge, target_floor=None, target_pos=None):
        return RalseiPet.start_jump(self, target_window, window_edge,
                                    target_floor=target_floor, target_pos=target_pos)


def drive(pet):
    """走产品路径：这一拍的产品决策（等价于 update_movement 里的调用）。"""
    pet.check_nearby_windows(pet.pos())


# ============================================================ A 接线
section('A 接线：产品真的走楼层判定（防"改了没人调用"复演）')

_main_py = os.path.join(PET, 'src', 'main.py')
_main_src = code_only(_main_py)

ok('A1 新增了楼层跳跃规划器（定义存在）',
   all(has(_main_src, n) for n in ('_floors_for_jump', '_floor_entry_plan',
                                   '_nearest_floor_jump', '_start_floor_jump')),
   [n for n in ('_floors_for_jump', '_floor_entry_plan', '_nearest_floor_jump',
                '_start_floor_jump') if not has(_main_src, n)])

# 行为级：宠物在窗口下方贴边 → 产品路径必须真的起跳，且目标楼层是那块窗口的**楼层**
_w = mk_window(101, 300, 100, 600, 400, 0)
_fm = fm_with([_w])
_f101 = floor_of(_fm, 101)
_pet = PetStub(_fm, 505, 505, current_floor=_fm.desktop_floor)
drive(_pet)
ok('A2 贴边起跳由楼层判定触发（is_jumping=True）', _pet.is_jumping is True,
   'is_jumping=%r anims=%r' % (_pet.is_jumping, _pet.anim_calls))
ok('A2b 目标楼层 = 那块窗口的楼层（而不是"桌面"）',
   _pet.jump_target_floor is _f101,
   'target=%r' % (_pet.jump_target_floor,))
ok('A2c 未回落旧逻辑（楼层可用时不再枚举裸窗口表 —— stub 根本没这个属性）',
   not hasattr(_pet, 'desktop_interaction'), None)

# ============================================================ B 向上跳的落点可见性
section('B 向上跳：落点只能落在目标层的**可见区域**')

ok('B1 无遮挡时跳到窗口：落点在可见区域内',
   bool(_pet.jump_target_pos) and in_visible(_f101, _pet.jump_target_pos),
   'land=%s visible=%s' % (_pet.jump_target_pos, _f101.get('visible_rects')))

# 遮挡：一块更高的窗口压住目标层右下角 → 落点必须被吸附回可见区域
_c = mk_window(102, 500, 300, 400, 200, 0)      # 最前
_w2 = mk_window(103, 300, 100, 600, 400, 1)
_fm2 = fm_with([_c, _w2])
_f103 = floor_of(_fm2, 103)
_pet2 = PetStub(_fm2, 505, 505, current_floor=_fm2.desktop_floor)
drive(_pet2)
ok('B2 起跳后落点必然落在**所跳目标层**的可见区域内',
   _pet2.is_jumping is True
   and in_visible(_pet2.jump_target_floor, _pet2.jump_target_pos),
   'jumping=%r target=%r land=%s' % (
       _pet2.is_jumping, (_pet2.jump_target_floor or {}).get('window_hwnd'),
       getattr(_pet2, 'jump_target_pos', None)))
ok('B2b 跳到的是"更高的可见悬崖边"（102 最前，优先于被它压着的 103）',
   _pet2.jump_target_floor.get('window_hwnd') == 102,
   (_pet2.jump_target_floor or {}).get('window_hwnd'))

# 直接单测"被遮处 → 吸附进可见区域"（产品路径里那一步的判据）
_naive_land = QPoint(559, 379)          # 与"未吸附"的朴素落点重合：它落在 102 的覆盖范围内
_plan2 = _pet2._floor_entry_plan(_fm2, _f103, QRect(505, 505, PET_W, PET_H),
                                 _fm2.desktop_floor)
ok('B2c 对**被压住**的目标层 103：落点被吸附进它的可见区域（不再落在看不见的地板上）',
   _plan2 is not None
   and in_visible(_f103, _plan2[1])
   and _plan2[1] != QPoint(559, 379),
   'plan=%s visible_rects=%s' % (_plan2, _f103.get('visible_rects')))

# 目标层顶部整条被压住 → 不允许从"看不见的边缘"进入
_c2 = mk_window(111, 300, 100, 600, 60, 0)
_w3 = mk_window(112, 300, 100, 600, 400, 1)
_fm3 = fm_with([_c2, _w3])
_f112 = floor_of(_fm3, 112)
_pet3 = PetStub(_fm3, 700, 900, current_floor=_fm3.desktop_floor)
drive(_pet3)
ok('B3 目标层顶部被完全盖住时，不产生"从顶部进入"的跳跃',
   _pet3.is_jumping is False
   or in_visible(_f112, _pet3.jump_target_pos),
   'jumping=%r land=%s' % (_pet3.is_jumping,
                           getattr(_pet3, 'jump_target_pos', None)))

# ============================================================ C 向下跳逐层
section('C 向下跳：只能落到**相邻下一层**，不得穿透')

# 3 层：B(最前,10) / A(5) / 桌面(0)。宠物站在 B 上，靠近 A 的顶边 → 只能去 A
_b = mk_window(201, 100, 200, 800, 400, 0)
_a = mk_window(202, 100, 620, 800, 400, 1)
_fm4 = fm_with([_b, _a])
_f201 = floor_of(_fm4, 201)
_f202 = floor_of(_fm4, 202)
ok('C0 合成几何成立：B 比 A 高一层（名次相邻）',
   _f201['platform_height'] - _f202['platform_height'] == 5,
   (_f201['platform_height'], _f202['platform_height']))

_pet4 = PetStub(_fm4, 400, 500, current_floor=_f201)
drive(_pet4)
ok('C1 从 3 楼下跳：目标是**相邻的 2 楼**，不是 1 楼（桌面）',
   _pet4.is_jumping is True
   and _pet4.jump_target_floor is _f202,
   'jumping=%r target=%r' % (_pet4.is_jumping,
                             (_pet4.jump_target_floor or {}).get('window_hwnd')))
ok('C2 落点在该层可见区域内',
   in_visible(_f202, _pet4.jump_target_pos),
   'land=%s' % (_pet4.jump_target_pos,))

# 只有一层窗口时，相邻下层就是桌面 → 允许跳回桌面（这是合法的一层）
_fm5 = fm_with([mk_window(301, 100, 200, 800, 400, 0)])
_f301 = floor_of(_fm5, 301)
_pet5 = PetStub(_fm5, 400, 480, current_floor=_f301)
drive(_pet5)
ok('C3 相邻下层就是桌面时：目标 = 桌面（桌面恒为最底层）',
   _pet5.is_jumping is True
   and _pet5.jump_target_floor.get('type') == 'desktop',
   'jumping=%r target=%r' % (_pet5.is_jumping,
                             (_pet5.jump_target_floor or {}).get('type')))

ok('C4 跳向桌面的落点在当前楼板**下方**（不是原地/上方）',
   _pet5.jump_target_pos.y() > _f301['rect'].bottom(),
   'land_y=%s slab_bottom=%s' % (_pet5.jump_target_pos.y(), _f301['rect'].bottom()))

# ============================================================ D 单真源同步
section('D current_window 与 current_floor 单真源')

_pet6 = PetStub(_fm4, 400, 300, current_floor=_f201)
_pet6._sync_window_cache_from_floor(_f201)
ok('D1 站上窗口楼层 → current_window 同步为该窗口',
   _pet6.current_window and _pet6.current_window.get('hwnd') == 201,
   _pet6.current_window)
ok('D2 回到桌面层 → current_window 清空',
   (_pet6._sync_window_cache_from_floor(_fm4.desktop_floor),
    _pet6.current_window is None)[1], _pet6.current_window)

ok('D3 check_window_movement 里真的调了同步器（走路换楼板也要同步）',
   has(_main_src, '_sync_window_cache_from_floor(new_floor)'), None)
ok('D4 同步器是"1 处定义 + ≥2 处调用"（两个换楼板的入口都接上了）',
   _main_src.count('_sync_window_cache_from_floor') >= 3,
   _main_src.count('_sync_window_cache_from_floor'))

# 楼层系统不可用时（无窗口 / 单测桩）必须整体回落旧逻辑，不能因新代码崩掉
_pet_empty = PetStub(fm_with([]), 10, 10)
ok('D5 楼层表为空时 _floors_for_jump 返回 None（产品据此整体回落旧逻辑）',
   RalseiPet._floors_for_jump(_pet_empty) is None, None)

# ============================================================ E floor_manager 新契约
section('E floor_manager 新增契约（相邻层 / 可见吸附）')

ok('E1 adjacent_lower_floor：3楼 → 2楼（不是直接到 1楼）',
   _fm4.adjacent_lower_floor(_f201) is _f202,
   (_fm4.adjacent_lower_floor(_f201) or {}).get('window_hwnd'))
ok('E2 adjacent_lower_floor：2楼 → 桌面',
   _fm4.adjacent_lower_floor(_f202).get('type') == 'desktop',
   _fm4.adjacent_lower_floor(_f202))
ok('E3 adjacent_lower_floor：桌面 → None（最底层没有下一层）',
   _fm4.adjacent_lower_floor(_fm4.desktop_floor) is None,
   _fm4.adjacent_lower_floor(_fm4.desktop_floor))

ok('E4 nearest_visible_point：可见区内原样返回',
   _fm4.nearest_visible_point(_f202, QPoint(400, 700)) == QPoint(400, 700),
   _fm4.nearest_visible_point(_f202, QPoint(400, 700)))
ok('E5 nearest_visible_point：桌面层整片可见（原样返回）',
   _fm4.nearest_visible_point(_fm4.desktop_floor, QPoint(5, 5)) == QPoint(5, 5),
   _fm4.nearest_visible_point(_fm4.desktop_floor, QPoint(5, 5)))

# 被遮处的点必须被吸附到可见子矩形内
_p = _fm2.nearest_visible_point(_f103, QPoint(560, 379))
ok('E6 nearest_visible_point：被遮住点被吸附进可见区域',
   _p is not None and in_visible(_f103, _p) and _p != QPoint(560, 379),
   'snapped=%s visible_rects=%s' % (_p, _f103.get('visible_rects')))

# ============================================================ F 源码级不变量
section('F 源码级不变量')

ok('F1 start_jump 支持 target_floor / target_pos（落点由可见区域给定）',
   has(_main_src, 'def start_jump(self, target_window, window_edge, target_floor=None, target_pos=None)'),
   None)
ok('F2 楼层可用时 check_nearby_windows 走 _nearest_floor_jump',
   has(_main_src, '_nearest_floor_jump(fm, cur_floor, ralsei_rect)'), None)
ok('F3 落点不再由"裸窗口矩形 + title_bar_height"反推（给了 target_pos 就直接用）',
   has(_main_src, 'if target_pos is not None:'), None)

# ---- 汇总（G2 需要这一行固定格式）
print('')
print('=' * 68)
print('第十四轮·上下动：PASS=%d FAIL=%d' % (len(PASS), len(FAIL)))
if FAIL:
    for f in FAIL:
        print('  FAILED: %s' % f)
print('=' * 68)
sys.exit(1 if FAIL else 0)

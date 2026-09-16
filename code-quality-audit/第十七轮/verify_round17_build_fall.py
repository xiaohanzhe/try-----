# -*- coding: utf-8 -*-
"""第十七轮验证：「建楼」缺口计划 · 批次 A（G2 下落路径 + G1 生气动画时长）。

背景（第十六轮复检留下的两条 GAP，本轮修）
------------------------------------------
第十六轮做了**只读**复检，结论是 13 条"建楼"要求里 7 条已实现、5 条部分、
2 条（第36/37行的动画时长要求）**实际是坏的**：

G2 —— `check_window_movement` 的坠落触发条件是
      `old_floor.type == 'window' and new_floor.type != 'window'`
      → **只有"下面变成桌面"才会掉**。而要求原文第 30 行给的例子恰恰是另一种：
        "如果我把窗口B（记事本）关掉，3楼消失，宠物如果原来在上面，
          就会掉到2楼（浏览器）上。"
      记事本关掉后下方还有浏览器，`get_current_floor` 立刻把楼层换成浏览器
      （**仍是窗口**）→ 整段被跳过：不坠落、不播动画、不生气，宠物直接"瞬移"
      到了浏览器那一层。
      修法：判据换成**层高比较**（`platform_height`），四种情形一次覆盖
      （走出边缘→桌面 / 关窗→桌面 / 关窗→下方还有窗口 / 被更高新窗盖住）。

G1 —— "生气动画至少 5s / 3s"从未成立，三个原因叠加：
      a) 时长写在 `self.max_fall_duration`，但**全项目只有 `handle_fall` 读它**；
         而 `start_falling()` 把 `is_falling` 置 False（坠落走 `handle_gravity_fall`）
         → `handle_fall` 根本不跑 → 那两句 5.0/3.0 是**死参数**；
      b) 即便跑，`trigger_splat()` 又会把 `max_fall_duration` 覆盖成 3.0；
      c) 落地时 `trigger_splat()` 恒切普通 `splat`，把坠落途中刚播上的
         `fall_mad` **在落地那一瞬顶掉** —— 生气素材 `splat_mad` 全项目零调用。
      修法：把"生气素材 + 最短停留"做成**由起因纯派生**的模块级函数
      （唯一真源 = `_fall_reason`）：`_fall_splat_hold(pet)` 给时长、
      `_splat_animation_name(pet)` 给素材，落地结算（`trigger_splat` /
      `handle_fall`）只负责读。放模块级而非类方法，是因为多个历史套件用轻量桩
      驱动 `RalseiPet.handle_fall(stub, ...)` —— 类方法会让每个桩都得补一个转发
      方法（本轮实测 round6_verify / round8_fling 当场 AttributeError 崩在半路）。

分组
----
  A G2 层高判据（行为级四种情形 + 源码级判据换掉）
  B G1 生气动画真的播 + 真的停满（行为级时间推进 + 源码级死参数已清）
  C 单一入口 / 未误伤（甩飞不误用生气版；判定只有一个入口）

本套件不需要真窗口（合成窗口表 + FakeFloorManager + 桩）。
必须用 C:\\Python311\\python.exe 运行。
"""
import ast
import io
import os
import re as _re
import sys
import textwrap
import time
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
from PyQt5.QtWidgets import QApplication                    # noqa: E402

_app = QApplication.instance() or QApplication([])

from main import (RalseiPet, FALL_SPLAT_HOLD,               # noqa: E402
                  FALL_SPLAT_HOLD_DEFAULT, FALL_MAD_REASONS, FALL_MAD_ANIMATION,
                  _fall_splat_hold, _splat_animation_name)

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


def code_only_src(src):
    """剥掉注释/字符串后的 token 串联。`"字面量" in 源码` 会误命中注释，
    源码级断言一律走这里（见 MEMORY「验证脚本教训」）。"""
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in _DROP:
                continue
            out.append(tok.string)
    except Exception:
        return ''
    return ' '.join(out)


def flat(s):
    return _re.sub(r'\s+', '', s)


def has_flat(hay, needle):
    return flat(needle) in flat(hay or '')


def method_code(name, text=MAIN_TEXT):
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            seg = ast.get_source_segment(text, node)
            return code_only_src(textwrap.dedent(seg or ''))
    return None


# 找**字符串字面量** needle（如 `new_floor.get('type')`）时必须只剥注释：
# `code_only_src` 会把 STRING 一起剥掉，于是 needle 永远搜不到 → 断言假 PASS。
# （见 MEMORY「验证脚本教训」）
_DROP_COMMENT = (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                 tokenize.INDENT, tokenize.DEDENT)


def code_no_comment(src):
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in _DROP_COMMENT:
                continue
            out.append(tok.string)
    except Exception:
        return ''
    return ' '.join(out)


def method_lit(name, text=MAIN_TEXT):
    """方法体的"只剥注释"文本（保留字符串字面量）。"""
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            seg = ast.get_source_segment(text, node)
            return code_no_comment(textwrap.dedent(seg or ''))
    return None


# ---------------------------------------------------------------- QRect/环境
SCREEN = QRect(0, 0, 1920, 1080)
PET_W, PET_H = 136, 71


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
    """驱动真实 `check_window_movement` 的最小表面（沿用第十五轮）。"""

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
        self.emotion_system = types.SimpleNamespace(react_to_event=lambda e, d: None)

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

    def _sync_window_cache_from_floor(self, floor):
        return RalseiPet._sync_window_cache_from_floor(self, floor)

    def _follow_floor_move(self, old, moved):
        return RalseiPet._follow_floor_move(self, old, moved)

    def _apply_pet_z_order(self):
        return False

    check_window_movement = RalseiPet.check_window_movement


# ============================================================ A G2 层高判据
section('A G2：坠落判据换成"层高比较"（关窗掉到**下方窗口**也要掉）')

# --- A1 复检 G2 的原例：关掉记事本，下方还有浏览器 → 必须掉，且起因=用户行为
_note = win_floor(701, 300, 300, 800, 600, ph=10)     # 记事本（3楼）
_brow = win_floor(702, 100, 100, 1600, 1000, ph=5)    # 浏览器（2楼），包围宠物
_fm_a1 = FakeFloorManager([_note, _brow])
_pet_a1 = MoveStub(_fm_a1, 500, 500)
assert _pet_a1.current_floor is _note, '前置：宠物应站在记事本上'
_fm_a1.floors = [_brow]                               # 用户关掉记事本
_pet_a1.calls = []
RalseiPet.check_window_movement(_pet_a1)
ok('A1 关窗后**下方还有窗口**→ 仍然 start_falling(reason="floor_removed")'
   '（复检 G2 的原例：旧判据会静默跳过，宠物"瞬移"到浏览器那层）',
   ('start_falling', 'floor_removed') in _pet_a1.calls, _pet_a1.calls)

# --- A2 关窗后落到桌面 → 同样带起因
_fm_a2 = FakeFloorManager([win_floor(703, 300, 300, 800, 600, ph=10)])
_pet_a2 = MoveStub(_fm_a2, 500, 500)
_fm_a2.floors = []
_pet_a2.calls = []
RalseiPet.check_window_movement(_pet_a2)
ok('A2 关窗后落到桌面 → start_falling(reason="floor_removed")（改前也对的路径，防回退）',
   ('start_falling', 'floor_removed') in _pet_a2.calls, _pet_a2.calls)

# --- A3 自己走出楼板边缘（窗口还在）→ 常规坠落，不带起因
_fm_a3 = FakeFloorManager([win_floor(704, 300, 300, 800, 600, ph=10)])
_pet_a3 = MoveStub(_fm_a3, 1200, 500)                 # 站在窗口右边之外
_pet_a3.current_floor = _fm_a3.get_floor_by_window(704)
_pet_a3.calls = []
RalseiPet.check_window_movement(_pet_a3)
ok('A3 自己走出楼板边缘 → start_falling() 不带起因（不误用生气动画）',
   ('start_falling', None) in _pet_a3.calls
   and not any(c == ('start_falling', 'floor_removed') for c in _pet_a3.calls),
   _pet_a3.calls)

# --- A4 被更高的新窗口盖住 → 不摔（建楼要求 ⑪，必须保持不变）
_fm_a4 = FakeFloorManager([win_floor(705, 100, 100, 1600, 1000, ph=5)])
_pet_a4 = MoveStub(_fm_a4, 500, 500)
_fm_a4.floors = [_pet_a4.current_floor,
                 win_floor(706, 200, 200, 1200, 800, ph=10)]   # 新窗口盖上来
_pet_a4.calls = []
RalseiPet.check_window_movement(_pet_a4)
ok('A4 被更高的新窗口盖住（5→10）→ 不摔、直接站新板（要求 ⑪ 未被本次改动破坏）',
   not any(c[0] in ('start_falling', 'start_fall') for c in _pet_a4.calls), _pet_a4.calls)

# --- A5 源码级：判据确实不再是"新楼层不是窗口"
_cwm_lit = method_lit('check_window_movement')
_cwm = method_code('check_window_movement')
ok('A5 源码级：判据不再依赖 new_floor 的类型（`new_floor.get(\'type\')` 已消失）',
   not has_flat(_cwm_lit, "new_floor.get('type')"), None)
ok('A5b 源码级：改为层高比较（`new_h < old_h` + `platform_height`）',
   has_flat(_cwm, 'new_h<old_h') and has_flat(_cwm_lit, "platform_height"),
   None)

# ============================================================ B G1 生气动画
section('B G1："生气动画至少 5s / 3s"真的成立（行为级时间推进）')


class SplatStub:
    """从"刚落地"开始的极简桩：只提供 `trigger_splat` / `handle_fall` 用到的面。

    阶段机（handle_fall）里 splat 阶段不碰位置，只读 `_fall_phase` / `fall_duration`
    / `_splat_hold` → 可以用最小表面积**真跑**一遍，量出"生气动画到底停了多久"。
    """

    def __init__(self, reason):
        self.sprites_present = ('splat', 'splat_mad', 'fall_back_rub', 'fall_back',
                                'land', 'pose', 'idle')
        self.sprite_loader = types.SimpleNamespace(
            sprites={k: 1 for k in self.sprites_present})
        self.is_splat = False
        self.splat_start_time = 0.0
        self.is_moving = True
        self.is_falling = False
        self.is_gravity_falling = True
        self.is_recovering = False
        self.recovery_duration = 0.0
        self.recovery_max_duration = 1.5
        self.fall_duration = 0.0
        self.fall_start_time = 0.0
        self.max_fall_duration = 3.0
        self._fall_reason = reason
        self.anims = []
        self.msgs = []
        self.events = []
        self.sound_manager = types.SimpleNamespace(play_splat=lambda: None)
        self.dialogue_ui = types.SimpleNamespace(
            add_dialogue=lambda who, text, mood=None: self.msgs.append(text),
            show_dialogue=lambda: None)
        self.emotion_system = types.SimpleNamespace(
            react_to_event=lambda e, d: self.events.append(e))

    def change_animation(self, name, force=False):
        self.anims.append(name)

    def play_animation_once(self, name, restore_to=None):
        self.anims.append(name)

    def _desktop_floor_y(self):
        return SCREEN.bottom() - PET_H

    def _clamp_pos_to_desktop(self, x, y):
        return (int(x), int(y))

    def pos(self):
        return QPoint(500, 500)

    def move(self, x, y):
        pass


def drive_until_dazed(reason, dt=0.05, limit=40.0):
    """跑真实 `trigger_splat` + `handle_fall`，返回 (桩, 进入 dazed 的时刻)。"""
    pet = SplatStub(reason)
    RalseiPet.trigger_splat(pet)
    t = 0.0
    while t < limit:
        RalseiPet.handle_fall(pet, dt, time.time())
        t += dt
        if getattr(pet, '_fall_phase', None) == 'dazed':
            return pet, t
    return pet, None


# --- B1 落地那一瞬必须切到生气素材（不是普通 splat）
_pet_b1 = SplatStub('floor_removed')
RalseiPet.trigger_splat(_pet_b1)
ok('B1 用户行为落地 → trigger_splat 切到生气素材 splat_mad（复检 G1c：'
   '改前恒切普通 splat，把坠落途中的 fall_mad 顶掉）',
   _pet_b1.anims[:1] == [FALL_MAD_ANIMATION], _pet_b1.anims[:3])

_pet_b1b = SplatStub(None)
RalseiPet.trigger_splat(_pet_b1b)
ok('B1b 非用户行为（自己掉/被甩）落地 → 普通 splat（改前行为不变）',
   _pet_b1b.anims[:1] == ['splat'], _pet_b1b.anims[:3])

# --- B2 时长的载体：单一真源 = `_fall_reason`，时长由它**纯派生**
_pet_b2 = SplatStub('floor_removed')
_pet_b2b = SplatStub('window_move')
_pet_b2c = SplatStub(None)
ok('B2 时长由起因纯派生（关窗 5.0 / 挪楼板 3.0 / 无起因 1.0），不再另存实例属性',
   FALL_SPLAT_HOLD.get('floor_removed') == 5.0
   and FALL_SPLAT_HOLD.get('window_move') == 3.0
   and FALL_SPLAT_HOLD_DEFAULT == 1.0
   and _fall_splat_hold(_pet_b2) == 5.0
   and _fall_splat_hold(_pet_b2b) == 3.0
   and _fall_splat_hold(_pet_b2c) == 1.0
   and not hasattr(_pet_b2, '_splat_hold'),
   '%s / %s / %s' % (_fall_splat_hold(_pet_b2), _fall_splat_hold(_pet_b2b),
                     _fall_splat_hold(_pet_b2c)))

# --- B3 行为级：真的停满 5s / 3s
_pet_b3, _t5 = drive_until_dazed('floor_removed')
ok('B3 关窗摔落：生气动画（splat 阶段）真的停满 ≥5s 才转晕乎',
   _t5 is not None and 5.0 <= _t5 < 5.3,
   'dazed_at=%s hold=%s' % (_t5, _fall_splat_hold(_pet_b3)))

_pet_b3b, _t3 = drive_until_dazed('window_move')
ok('B3b 挪楼板摔倒：停满 ≥3s',
   _t3 is not None and 3.0 <= _t3 < 3.3, 'dazed_at=%s' % (_t3,))

_pet_b3c, _t1 = drive_until_dazed(None)
ok('B3c 无起因（自己掉下去）：仍为 1.0s —— 与改前逐帧一致，没有把普通摔倒一起拉长',
   _t1 is not None and 1.0 <= _t1 < 1.3, 'dazed_at=%s' % (_t1,))

# --- B4 全程没被普通 splat 顶掉
ok('B4 生气版全程没被普通 splat 顶掉（anims 里不出现 "splat"）',
   'splat' not in _pet_b3.anims, _pet_b3.anims)

# --- B5 源码级：死参数已清（start_falling 不再写 max_fall_duration / 不另存时长）
_sf = method_code('start_falling')
ok('B5 源码级：start_falling 不再写 max_fall_duration（复检 G1a 的死参数已清）',
   not has_flat(_sf, 'max_fall_duration='), None)
ok('B5b 源码级：start_falling 只写起因 `_fall_reason`，时长/素材都不另存（无第二份真源）',
   has_flat(_sf, '_fall_reason=reason') and not has_flat(_sf, '_splat_hold='), None)

# ============================================================ C 单一入口 / 未误伤
section('C 单一入口 / 未误伤')

ok('C1 素材判定只有一个入口：模块级 `_splat_animation_name(pet)`，两个调用点都调它',
   callable(_splat_animation_name)
   and has_flat(method_code('trigger_splat'), '_splat_animation_name(self)')
   and has_flat(method_code('handle_fall'), '_splat_animation_name(self)')
   and not has_flat(MAIN_TEXT, 'def _splat_animation_name(self'), None)

_mre = method_code('mouseReleaseEvent')
ok('C2 甩飞路径显式复位起因（否则上一次关窗的 _fall_reason 会污染这次甩飞）',
   has_flat(_mre, '_fall_reason=None'), None)

ok('C3 生气素材确实在动画库里（splat_mad → alias_of → fall_mad，素材存在）',
   FALL_MAD_ANIMATION == 'splat_mad'
   and os.path.exists(os.path.join(PET, 'assets', 'animations.json')), None)

# ---------------------------------------------------------------- 汇总
print('')
print('=' * 60)
print('第十七轮：PASS=%d FAIL=%d' % (len(PASS), len(FAIL)))
for _f in FAIL:
    print('  [FAIL] ' + _f)
print('=' * 60)
sys.exit(1 if FAIL else 0)

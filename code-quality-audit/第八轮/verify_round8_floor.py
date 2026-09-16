# -*- coding: utf-8 -*-
"""第八轮 · 建楼楼层判定修复验证（Task #11）

对应用户报的两个问题：
  1) "摔倒别看到窗口就摔倒，判定不对" —— 只是站在窗口上也会莫名其妙摔倒
  2) "坠落偶尔一下就掉到屏幕最底下，没有触发条件也会" —— 凭空掉到屏幕底

根因（静态复查 + 离线复现确认）：
  `check_window_movement` 用 `new_floor != self.current_floor` 比较**两份 floor dict
  的内容**来决定"楼层有没有变"。而 floors 每轮由 FloorManager.update_floors 整体重建，
  其中 platform_height 依赖"当前可见窗口数量"、z_order 随焦点变化 → 同一个窗口重建出的
  dict 与缓存必然不等 → 被误判成"换了楼板"→ 直接 start_fall("window_move") 摔倒。
  同一条误判链还会走成"窗口→桌面"→ start_falling() → 一路掉到屏幕最底。
  另外 handle_gravity_fall 落到屏幕底边后没有把 current_floor 更新成桌面层，
  导致下一秒又被判定为"窗口→桌面"的楼层变化，凭空重复触发一次假坠落。

修复：改用稳定标识（窗口 hwnd / 'desktop'）判定楼层身份；窗口被挪走时按位移
（>30px 跟随+摔倒 / >400px 失足掉落）处理；落地后同步 current_floor。

本脚本用 stub 直接驱动真实的 check_window_movement / handle_gravity_fall，
不需要真窗口、不需要人工看屏幕。
"""
import os
import sys
import time
import types

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PET = os.path.join(BASE, 'ralsei_pet')
for _p in (os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if _p not in sys.path:
        sys.path.append(_p)

from PyQt5.QtCore import QPoint, QRect  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])

from main import RalseiPet  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, detail))
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  <- " + str(detail)) if detail else ""))


SCREEN = QRect(0, 0, 1920, 1080)


def win_floor(hwnd, x, y, w, h, platform_height=10, z_order=5, title="t"):
    rect = QRect(x, y, w, h)
    return {
        'type': 'window',
        'window': {'hwnd': hwnd, 'title': title, 'class_name': 'C',
                   'rect': rect, 'z_order': z_order},
        'rect': rect,
        'z_order': z_order,
        'platform_height': platform_height,
        'window_hwnd': hwnd,
    }


def desktop_floor():
    return {'type': 'desktop', 'rect': QRect(SCREEN), 'z_order': 0,
            'platform_height': 0}


class FakeFloorManager:
    def __init__(self, floors):
        self.floors = list(floors)
        self.desktop_floor = desktop_floor()

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

    def get_all_floors(self):
        return self.floors + [self.desktop_floor]

    def get_floor_by_window(self, hwnd):
        for f in self.floors:
            if f.get('window_hwnd') == hwnd:
                return f
        return None

    def get_drop_destination(self, pos, current_floor):
        """与 FloorManager.get_drop_destination 同语义（按稳定标识定位当前楼层）。"""
        all_floors = self._all()
        cur = None
        cur_hwnd = (current_floor or {}).get('window_hwnd')
        for i, f in enumerate(all_floors):
            if f.get('type') == 'desktop':
                if (current_floor or {}).get('type') == 'desktop':
                    cur = i
                    break
            elif f.get('window_hwnd') == cur_hwnd:
                cur = i
                break
        start = 0 if cur is None else cur + 1
        for f in all_floors[start:]:
            if f['rect'].contains(pos):
                return f, pos
        return self.desktop_floor, pos


class PetStub:
    """只装 check_window_movement / _follow_floor_move / handle_gravity_fall 真正用到的属性。"""

    def __init__(self, fm, x, y):
        self.floor_manager = fm
        self._x, self._y = int(x), int(y)
        self._w, self._h = 110, 110
        self._spell_stage = None
        self.game_state = {'is_playing': False}
        self.is_falling = False
        self.is_jumping = False
        self.is_gravity_falling = False
        self.current_floor = fm.get_current_floor(QPoint(self._x, self._y))
        self.current_window = None
        self.current_platform_z = 0
        self.spatial_pos = {'x': self._x, 'y': self._y, 'z': 0}
        # 记录型副作用
        self.calls = []
        self.emotion_calls = []
        self.emotion_system = types.SimpleNamespace(
            react_to_event=lambda ev, d: self.emotion_calls.append(ev))
        # 真方法绑定（StaticMethod 在本类上是普通函数，直接挂上去即可）
        self._floor_identity_key = RalseiPet._floor_identity_key
        self._floor_rect_changed = RalseiPet._floor_rect_changed
        self._follow_floor_move = (
            lambda old, moved: RalseiPet._follow_floor_move(self, old, moved))

    # --- 几何 ---
    def pos(self):
        return QPoint(self._x, self._y)

    def width(self):
        return self._w

    def height(self):
        return self._h

    def move(self, x, y):
        self._x, self._y = int(x), int(y)

    def _clamp_pos_to_desktop(self, x, y):
        x = max(SCREEN.left(), min(int(x), SCREEN.right() - self._w))
        y = max(SCREEN.top(), min(int(y), SCREEN.bottom() - self._h))
        return x, y

    def _desktop_floor_y(self):
        return SCREEN.bottom() - self._h

    # --- 两个目标动作的替身（只记录，不真动）---
    def start_fall(self, reason="window_move"):
        if getattr(self, 'is_falling', False):
            return
        self.calls.append(('start_fall', reason))
        self.is_falling = True

    def start_falling(self, fall_velocity=0, is_thrown=False):
        self.calls.append(('start_falling', fall_velocity))
        self.is_gravity_falling = True
        self.fall_speed = 0.0
        self.fall_velocity_x = 0.0

    # handle_gravity_fall 需要
    def change_animation(self, *a, **k):
        pass

    def setWindowFlags(self, *a, **k):
        pass

    def show(self):
        pass

    # 第十三轮新增：落地后按"一层压一层"重排窗口 z 序（把宠物插到所站楼板之上）。
    # 本套件只关心"摔/不摔/掉到哪"，z 序与判定无关 → 这里空实现。
    # （教训：stub 必须跟得上真实方法表面，否则生产代码一加调用就 AttributeError。）
    def _apply_pet_z_order(self):
        return False

    def trigger_splat(self):
        self.calls.append(('splat', None))

    gravity = 900.0


def run_cwm(pet):
    RalseiPet.check_window_movement(pet)
    return pet.calls


# ------------------------------------------------------------------------ tests
def t1_rebuilt_same_window_no_splat():
    """核心：同一个窗口被重建（platform_height / z_order / title 变了）→ 不能摔倒。"""
    a = win_floor(1001, 300, 300, 800, 600, platform_height=10, z_order=5, title="旧标题")
    fm = FakeFloorManager([a])
    pet = PetStub(fm, 500, 500)
    pet.current_floor = a                      # 宠物就站在这块楼板上

    # 下一秒整体重建：同一个 hwnd / 同一个矩形，但 platform_height、z_order、标题都变了
    a2 = win_floor(1001, 300, 300, 800, 600, platform_height=25, z_order=9, title="新标题")
    fm.floors = [a2]

    calls = run_cwm(pet)
    check("W1.1 同一窗口重建 dict（高度/层序/标题变化）不再触发摔倒",
          not any(c[0] in ('start_fall', 'start_falling') for c in calls), "calls=%s" % calls)
    check("W1.2 当前楼层被刷新为最新那份 dict（无身份漂移）",
          pet.current_floor is a2 and pet.current_floor['platform_height'] == 25,
          "ph=%s" % pet.current_floor.get('platform_height'))


def t2_window_still_no_action():
    """窗口完全没动 → 不应有任何动作。"""
    a = win_floor(1002, 300, 300, 800, 600)
    fm = FakeFloorManager([a])
    pet = PetStub(fm, 500, 500)
    pet.current_floor = a
    fm.floors = [win_floor(1002, 300, 300, 800, 600)]   # 新对象、同几何
    calls = run_cwm(pet)
    check("W2 窗口未移动时零副作用（不摔不落不跟）", calls == [], "calls=%s" % calls)


def t3_follow_small_move_and_splat():
    """窗口被挪动 60px → 宠物跟着平移，并且重心不稳摔倒（≥3s 动画走 start_fall）。"""
    a = win_floor(1003, 300, 300, 800, 600)
    fm = FakeFloorManager([a])
    pet = PetStub(fm, 500, 500)
    pet.current_floor = a
    pet.current_window = {'hwnd': 1003, 'x': 300, 'y': 300, 'width': 800, 'height': 600}
    fm.floors = [win_floor(1003, 360, 300, 800, 600)]   # dx = +60

    calls = run_cwm(pet)
    check("W3.1 窗口平移 60px：宠物跟着走（x +60）",
          (pet._x, pet._y) == (560, 500), "pos=(%d,%d)" % (pet._x, pet._y))
    check("W3.2 同时判定重心不稳 → start_fall('window_move')",
          ('start_fall', 'window_move') in calls, "calls=%s" % calls)
    check("W3.3 触发 window_moved 情绪事件",
          'window_moved' in pet.emotion_calls, "emotion=%s" % pet.emotion_calls)


def t4_follow_below_splat_threshold():
    """窗口只挪 10px（<30px）→ 跟随但不摔。"""
    a = win_floor(1004, 300, 300, 800, 600)
    fm = FakeFloorManager([a])
    pet = PetStub(fm, 500, 500)
    pet.current_floor = a
    fm.floors = [win_floor(1004, 310, 300, 800, 600)]   # dx = +10
    calls = run_cwm(pet)
    check("W4 小幅挪动（10px）只跟随、不摔",
          (pet._x, pet._y) == (510, 500) and calls == [],
          "pos=(%d,%d) calls=%s" % (pet._x, pet._y, calls))


def t5_huge_jump_no_follow_and_fall():
    """窗口被瞬间搬走 800px（如最大化/还原）→ 不跟随，改为失足掉落。"""
    a = win_floor(1005, 300, 300, 800, 600)
    fm = FakeFloorManager([a])
    pet = PetStub(fm, 500, 500)
    pet.current_floor = a
    fm.floors = [win_floor(1005, 1100, 300, 800, 600)]   # dx = +800
    calls = run_cwm(pet)
    check("W5.1 大幅瞬移时宠物不跟着瞬移（位置不变）",
          (pet._x, pet._y) == (500, 500), "pos=(%d,%d)" % (pet._x, pet._y))
    check("W5.2 改为失足掉落 start_fall('window_move')",
          ('start_fall', 'window_move') in calls, "calls=%s" % calls)


def t6_window_closed_start_falling():
    """窗口被关闭（枚举里没有它了）→ 立刻重力掉落（建楼要求）。"""
    a = win_floor(1006, 300, 300, 800, 600)
    fm = FakeFloorManager([a])
    pet = PetStub(fm, 500, 500)
    pet.current_floor = a
    fm.floors = []                       # 楼板被抽走
    calls = run_cwm(pet)
    check("W6 窗口关闭 → start_falling()（往下掉）",
          ('start_falling', 0) in calls, "calls=%s" % calls)


def t7_covered_by_other_window_no_fall():
    """被更高的新窗口盖住 → 按"当前楼层原则"直接站到新楼板上，不摔不落。"""
    a = win_floor(1007, 300, 300, 800, 600, platform_height=10)
    b = win_floor(1008, 400, 400, 600, 400, platform_height=20)
    fm = FakeFloorManager([a, b])
    pet = PetStub(fm, 500, 500)          # (500,500) 同时落在 a 与 b 内，b 更高
    pet.current_floor = a                # 之前站在 a 上
    calls = run_cwm(pet)
    check("W7.1 被新窗口盖住后接管为新楼层，不摔不落",
          calls == [] and pet.current_floor.get('window_hwnd') == 1008,
          "calls=%s now=%s" % (calls, pet.current_floor.get('window_hwnd')))


def t8_gravity_fall_reaches_bottom_and_syncs_floor():
    """核心：坠落到屏幕底边后必须把 current_floor 同步成桌面层，否则每秒反复假坠落。"""
    a = win_floor(1009, 300, 200, 800, 600)
    fm = FakeFloorManager([a])

    pet = PetStub(fm, 500, 200)          # 从窗口上开始掉
    pet.current_floor = a
    pet.is_gravity_falling = True
    pet.fall_speed = 0.0
    pet.fall_velocity_x = 0.0

    ys = []
    for _ in range(400):
        RalseiPet.handle_gravity_fall(pet, 0.033, time.time())
        ys.append(pet._y)
        if not pet.is_gravity_falling:
            break

    check("W8.1 坠落不再在当前位置'悬停落地'（确实一路往下掉）",
          len(ys) > 5 and ys[-1] == pet._desktop_floor_y(),
          "frames=%d final_y=%s floor_y=%s" % (len(ys), ys[-1], pet._desktop_floor_y()))
    check("W8.2 落到底边后 current_floor 同步为桌面层（消除每秒假坠落）",
          pet.current_floor.get('type') == 'desktop',
          "type=%s" % pet.current_floor.get('type'))

    # 再跑一次 check_window_movement：不应再因为"窗口→桌面"凭空触发一次坠落
    pet.calls = []
    pet.is_falling = False
    fm.floors = [a]
    run_cwm(pet)
    check("W8.3 落地后下一秒不再凭空重复触发坠落",
          not any(c[0] in ('start_fall', 'start_falling') for c in pet.calls),
          "calls=%s" % pet.calls)


def _dict_style_floor_compares(src):
    """用 AST 找出"拿整个 floor dict 做 ==/!= 比较"的代码（注释不算）。

    只算**直接操作数**：`self.current_floor` 或裸名 `*_floor`。
    像 `self.current_floor['window_hwnd'] == other['window_hwnd']` 这种
    "取字段比较"是正常的身份判定，不算。
    """
    import ast
    hits = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
            continue
        for operand in [node.left] + list(node.comparators):
            if isinstance(operand, ast.Attribute) and operand.attr == 'current_floor':
                hits.append('self.current_floor (line %d)' % node.lineno)
            elif isinstance(operand, ast.Name) and operand.id.endswith('floor'):
                hits.append('%s (line %d)' % (operand.id, node.lineno))
    return hits


def t9_no_dict_compare_left():
    """源码级不变量：楼层"是否变化"的判定不能再出现 dict 内容比较。"""
    src = open(os.path.join(PET, 'src', 'main.py'), encoding='utf-8').read()
    bad = _dict_style_floor_compares(src)
    check("W9.1 main.py 中已无 floor dict 内容比较式楼层判定（AST 判定，注释不算）",
          not bad, "残留=%s" % bad)
    check("W9.2 已引入稳定标识比较工具 _floor_identity_key",
          callable(getattr(RalseiPet, '_floor_identity_key', None))
          and callable(getattr(RalseiPet, '_floor_rect_changed', None))
          and callable(getattr(RalseiPet, '_follow_floor_move', None)))


def main():
    t1_rebuilt_same_window_no_splat()
    t2_window_still_no_action()
    t3_follow_small_move_and_splat()
    t4_follow_below_splat_threshold()
    t5_huge_jump_no_follow_and_fall()
    t6_window_closed_start_falling()
    t7_covered_by_other_window_no_fall()
    t8_gravity_fall_reaches_bottom_and_syncs_floor()
    t9_no_dict_compare_left()

    total = len(RESULTS)
    passed = sum(1 for ok, _n, _d in RESULTS if ok)
    print("-" * 68)
    print("第八轮建楼楼层判定验证：%d/%d PASS, %d FAIL" % (passed, total, total - passed))
    for ok, name, detail in RESULTS:
        if not ok:
            print("  FAIL: %s  %s" % (name, detail))
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())

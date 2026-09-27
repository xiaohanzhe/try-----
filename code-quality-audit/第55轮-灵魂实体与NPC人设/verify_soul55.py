# -*- coding: utf-8 -*-
"""第55轮 · 灵魂（SOUL）接线回归锁 —— 真机把 RalseiPet 起起来逐项验。

由来（★ 必须记住的教训）
------------------------
本套件原先是临时探针（`E:\\Download\\_tmp\\probe55_wire.py`，用后即删）。
第55轮把它**蒸馏进仓库**，原因是记忆里那条铁律：

    ★★ 回归套件**不许依赖**"用后即删"的临时区／外部盘
       （第44轮 `routes_order44` 的 C 段曾因 E 盘掉线静默退化成 SKIP）。

所以这里只允许依赖**仓库内**的东西（`ralsei_pet/assets/…`）+ `%TEMP%`。
`RALSEI_MEMORY_DIR` 用 `setdefault`：`run_all.py` 的 hermetic 环境优先级更高
（它给的是一个每轮全新的 `mkdtemp`，基线才封闭）。

验什么（五条接线，逐条都有负控制）
--------------------------------
  1. 建起来 + 可见 + 尺寸 / 出生点（勿信"套件绿"，第54轮教训）
  2. 键盘操控（按下即动、松开即停、对角线两轴各满速、dt 钳制、非方向键不吃）
  3. 显隐与场景位置簿（换场景记旧位置 / 回去还原 —— "自由出入各场景"）
  4. 交互选目标（★ **用真实数据**：`ch1.card_castle.cc_fountain` 有两个暗之泉，
     先断言"两次选择不同"，否则"恒取第一个"也会过）
  5. 鼠标附身 → 灵魂（`update_mouse_drag` 只推灵魂，不再动用户的光标）
  6. 三个全局热键都被尝试过 + `cleanup_on_exit` 收掉灵魂窗口

判据修正记录（第55轮实测，**留在这里防止后人重踩**）
--------------------------------------------------
  · K0：原先还断言 `tick(0.1) is False`，报红后查明是**判据过窄** —— `SoulOverlay.tick`
    的返回值语义是"这一帧有没有变化"，首次 tick 时 `_last_paint_index` 还是 `None`
    ⇒ 帧号 `None→0` 算一次变化，返回 True 是**对的**。真正要守的是"位置不变"。
  · H1/H2：`global_hotkey.parse_hotkey` 的规范名主键是**大写**（`main.upper()`），
    按小写比对会恒假 ⇒ 改成"小写归一后比对"（宽式，不重复踩"判据过窄"）。
"""
import os
import sys
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))          # 仓库根 = `try - 副本`
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, os.path.join(PET, 'modules'))

# ⚠️ `setdefault`（不是直接赋值）：run_all 的 hermetic 环境优先，基线才封闭。
_tmp = os.path.join(tempfile.gettempdir(), 'ralsei_soul55')
os.makedirs(_tmp, exist_ok=True)
os.environ.setdefault('RALSEI_MEMORY_DIR', _tmp)

from PyQt5.QtCore import QEvent, QPoint, Qt          # noqa: E402
from PyQt5.QtGui import QKeyEvent                     # noqa: E402
from PyQt5.QtWidgets import QApplication              # noqa: E402
import main as M                                      # noqa: E402

FAILS = []
N = [0]


def check(name, cond, extra=''):
    N[0] += 1
    if cond:
        print('[PASS] %s %s' % (name, extra))
    else:
        print('[FAIL] %s %s' % (name, extra))
        FAILS.append(name)


def almost(a, b, tol=0.51):
    return abs(float(a) - float(b)) <= tol


app = QApplication.instance() or QApplication([])
pet = M.RalseiPet()
for a in ('animation_timer', 'ai_timer', 'stats_timer', 'dialogue_init_timer',
          'auto_mouse_drag_timer', 'api_control_timer', 'placeholder_timer',
          'movement_timer', 'mouse_drag_timer', '_bounce_timer',
          '_hide_search_timer'):
    t = getattr(pet, a, None)
    try:
        if t is not None:
            t.stop()
    except Exception:
        pass

soul = pet.soul
W, H = soul.state.size
SCR = pet.soul.screen_bounds()
print('== 环境 ==')
print('  虚拟屏 rect =', SCR)
print('  宠物窗口 =', (pet.x(), pet.y(), pet.width(), pet.height()))
print('  灵魂 size =', (W, H), 'scale =', soul.state.scale,
      'speed =', soul.state.speed_per_sec, 'px/s')
print('  SOUL px/s 期望 = 4*30*3 =', 4 * 30 * 3)

# ---------------------------------------------------------------- 1. 建起来
check('S1 灵魂已建且可见', soul is not None and soul.isVisible())
check('S2 尺寸 = 16*3 = 48x48', (W, H) == (48, 48), str((W, H)))
check('S3 满速 = 原作 4px/帧 * 30fps * 3 倍',
      almost(soul.state.speed_per_sec, 360.0), '%.1f' % soul.state.speed_per_sec)
check('S4 独立顶层窗口（parent 为空）', soul.parent() is None,
      repr(soul.parent()))
check('S5 未加置顶标记',
      not bool(soul.windowFlags() & Qt.WindowStaysOnTopHint),
      hex(int(soul.windowFlags())))

# ---------------------------------------------------------------- 2. 出生点
exp_x = pet.x() + pet.width() / 2.0 + 10 * soul.state.scale
exp_y = pet.y() + pet.height() / 2.0 + 40 * soul.state.scale
if SCR:
    cx_lo, cy_lo = SCR[0], SCR[1]
    cx_hi = max(SCR[0], SCR[2] - W)
    cy_hi = max(SCR[1], SCR[3] - H)
    exp_x = min(max(exp_x, cx_lo), cx_hi)
    exp_y = min(max(exp_y, cy_lo), cy_hi)
check('S6 出生点 = 宠物中心 + 原作 (10,40)*scale（已钳进虚拟屏）',
      almost(soul.state.x, exp_x) and almost(soul.state.y, exp_y),
      '实际 (%.0f,%.0f) 期望 (%.0f,%.0f)' % (soul.state.x, soul.state.y, exp_x, exp_y))


def press(k):
    pet.keyPressEvent(QKeyEvent(QEvent.KeyPress, k, Qt.NoModifier))


def release(k):
    pet.keyReleaseEvent(QKeyEvent(QEvent.KeyRelease, k, Qt.NoModifier))


def tick(dt):
    return pet._soul_tick(dt)


# ---------------------------------------------------------------- 3. 键盘
soul.state.x, soul.state.y = 400.0, 300.0
soul.apply_state_pos()
base_x, base_y = soul.state.x, soul.state.y
tick(0.1)
check('K0 负控制：没按键时推进 0.1s 位置不变（松键即停的反面）',
      (soul.state.x, soul.state.y) == (base_x, base_y),
      '(%s,%s)' % (soul.state.x, soul.state.y))
# ⚠️ 判据修正记录：本项原先还断言 `tick(...) is False`，报红后查明是**判据过窄**——
#    `SoulOverlay.tick` 的返回值语义是"这一帧有没有变化"，而首次 tick 时
#    `_last_paint_index` 还是 None ⇒ 帧号从 None→0 算一次变化，返回 True 是**对的**。
#    真正要守的行为是"位置不变"，所以只断言位置。

press(Qt.Key_Left)
check('K1 按下 ← 后按键集合 = (left,)', soul.state.pressed() == ('left',),
      str(soul.state.pressed()))
tick(0.1)
check('K2 按 ← 推进 0.1s 位移 = -36px（4*30*3*0.1）',
      almost(soul.state.x, base_x - 36.0) and almost(soul.state.y, base_y),
      '位移 (%.1f, %.1f)' % (soul.state.x - base_x, soul.state.y - base_y))
release(Qt.Key_Left)
check('K3 松开 ← 后按键集合为空', soul.state.pressed() == (),
      str(soul.state.pressed()))
bx2, by2 = soul.state.x, soul.state.y
tick(0.1)
check('K4 松开后推进不动（松键即停，无残速）',
      (soul.state.x, soul.state.y) == (bx2, by2))

# 对角线：分轴独立、不归一化 ⇒ 两轴各满速
press(Qt.Key_Left)
press(Qt.Key_Up)
bx3, by3 = soul.state.x, soul.state.y
tick(0.1)
dx, dy = soul.state.x - bx3, soul.state.y - by3
check('K5 对角线两轴各满速（√2 倍，照抄原作分轴赋值）',
      almost(dx, -36.0) and almost(dy, -36.0),
      '(%.1f, %.1f)' % (dx, dy))
release(Qt.Key_Left)
release(Qt.Key_Up)

# dt 钳制
soul.state.clear_keys()
press(Qt.Key_Right)
bx4 = soul.state.x
tick(5.0)          # 假掉帧 5 秒
check('K6 dt=5.0s 只按 MAX_DT(0.1s) 结算 ⇒ 位移 36px（不瞬移）',
      almost(soul.state.x - bx4, 36.0), '位移 %.1f' % (soul.state.x - bx4))
release(Qt.Key_Right)
soul.state.clear_keys()

# 非方向键不被吃
ev = QKeyEvent(QEvent.KeyPress, Qt.Key_F5, Qt.NoModifier)
pet.keyPressEvent(ev)
check('K7 负控制：F5 不被灵魂吃掉（isAccepted=False）',
      not ev.isAccepted(), 'accepted=%s' % ev.isAccepted())

# 失焦放开按键
press(Qt.Key_Left)
press(Qt.Key_Down)
n = len(soul.state.pressed())
pet.focusOutEvent(QEvent(QEvent.FocusOut))
check('K8 宠物窗口失焦 ⇒ 放开所有按住的键', n == 2 and soul.state.pressed() == (),
      '失焦前 %d 个，失焦后 %s' % (n, soul.state.pressed()))

# ---------------------------------------------------------------- 4. 显示/收起
check('T1 收起灵魂 → 不可见且按键清空',
      pet.toggle_soul() is True and not soul.isVisible()
      and soul.state.pressed() == ())
check('T2 再切换 → 重新可见', pet.toggle_soul() is True and soul.isVisible())
soul.state.x, soul.state.y = 500.0, 400.0
soul.apply_state_pos()
pet.hide_soul()
check('T3 收起时仍会记一次位置（叫回来不回到出生点）',
      pet.toggle_soul() is True and soul.isVisible())
check('T4 收起前的 (500,400) 被记住并按场景还原',
      almost(soul.state.x, 500.0) and almost(soul.state.y, 400.0),
      '(%.0f,%.0f)' % (soul.state.x, soul.state.y))

# ---------------------------------------------------------------- 5. 场景位置簿
hooks = pet.__dict__.get('_scene_switch_hooks') or []
check('B1 场景切换钩子里有灵魂钩子（且没挤掉道具钩子）',
      pet._on_scene_switched_soul in hooks and len(hooks) >= 2,
      '%d 个钩子' % len(hooks))
old_scene = pet.current_scene
old_pos = (soul.state.x, soul.state.y)
check('B2 换场景到 ch1.card_castle.cc_fountain',
      pet.scene.switch('ch1.card_castle.cc_fountain') is True,
      '当前=%s' % pet.current_scene)
check('B3 灵魂在新场景按"宠物+偏移"出生（新场景无记录）',
      (soul.state.x, soul.state.y) != old_pos, str((soul.state.x, soul.state.y)))
new_pos = (soul.state.x, soul.state.y)
check('B4 换回旧场景', pet.scene.switch(old_scene) is True,
      '当前=%s' % pet.current_scene)
check('B5 回到旧场景 ⇒ 位置还原（"自由出入各场景"）',
      almost(soul.state.x, old_pos[0]) and almost(soul.state.y, old_pos[1]),
      '现在 (%.0f,%.0f) 原为 (%.0f,%.0f)' % (soul.state.x, soul.state.y,
                                             old_pos[0], old_pos[1]))
check('B6 位置簿里两个场景都记下了',
      pet.soul_bookmarks is not None and len(pet.soul_bookmarks) >= 2,
      pet.soul_bookmarks.describe() if pet.soul_bookmarks else 'None')
check('B7 换回新场景 ⇒ 回到 B3 那次的位置',
      pet.scene.switch('ch1.card_castle.cc_fountain') is True
      and almost(soul.state.x, new_pos[0]) and almost(soul.state.y, new_pos[1]),
      '(%.0f,%.0f) 期望 (%.0f,%.0f)' % (soul.state.x, soul.state.y,
                                        new_pos[0], new_pos[1]))

# ---------------------------------------------------------------- 6. 交互选目标（真实数据）
print('== 场景 ch1.card_castle.cc_fountain ==')
print('  可交互物 =', [(p.key, p.describe()) for p in pet.item_props])
room = pet._soul_room_rect()
sw, sh = pet._virtual_screen_size()
print('  room_rect =', room, '虚拟屏 =', (sw, sh))
check('P0 该场景建出 2 件可交互物（两个暗之泉）', len(pet.item_props) == 2,
      '%d 件' % len(pet.item_props))

objs = pet._scene_state.objects
pos0 = tuple(objs[0]['pos'])
pos1 = tuple(objs[1]['pos'])


def place_at_room(wx, wy):
    rl, rt, rr, rb = room
    sx = (wx - rl) / (rr - rl) * sw
    sy = (wy - rt) / (rb - rt) * sh
    soul.state.x = sx - W / 2.0
    soul.state.y = sy - H / 2.0
    soul.apply_state_pos()


def pick_name():
    chosen, why = pet._soul_pick_prop(pet.item_props)
    return (getattr(chosen, 'key', None), why)


place_at_room(*pos0)
k0, why0 = pick_name()
print('  灵魂置于 %s ⇒ %s（%s）' % (pos0, k0, why0))
place_at_room(*pos1)
k1, why1 = pick_name()
print('  灵魂置于 %s ⇒ %s（%s）' % (pos1, k1, why1))
exp0 = 'ch1.card_castle.cc_fountain#0'
exp1 = 'ch1.card_castle.cc_fountain#1'
check('P1 灵魂在 0 号泉旁 ⇒ 选 0 号（不是永远取第一个）', k0 == exp0, str(k0))
check('P2 灵魂在 1 号泉旁 ⇒ 选 1 号', k1 == exp1, str(k1))
check('P3 两次选择**不同**（先断言 A ≠ B，否则"恒取第一个"也会过）',
      k0 is not None and k1 is not None and k0 != k1, '%s vs %s' % (k0, k1))

# 负控制：灵魂收起 ⇒ 选不出（退回第一个 + 说明原因）
soul.hide()
chosen, why = pet._soul_pick_prop(pet.item_props)
check('P4 负控制：灵魂收起时选不出（返回 None + 原因）',
      chosen is None and bool(why), str(why))
soul.show_soul()
# 负控制：物件列表为空
chosen, why = pet._soul_pick_prop([])
check('P5 负控制：可交互物为空时选不出', chosen is None and bool(why), str(why))

# key 下标解析：正/负控制
check('P6 key→下标 正控制',
      pet._soul_prop_index('ch1.a#3') == 3
      and pet._soul_prop_index('ch1.a#0@item1') == 0)
check('P7 key→下标 负控制（不猜、不抛）',
      pet._soul_prop_index('ch1.a') is None
      and pet._soul_prop_index('ch1.a#x') is None
      and pet._soul_prop_index(None) is None
      and pet._soul_prop_index(123) is None)

# 真调一次 interact_scene_prop：不抛 + 返回 bool
place_at_room(*pos1)
try:
    r = pet.interact_scene_prop()
    check('P8 interact_scene_prop 返回 bool 且不抛', isinstance(r, bool),
          'returned %r' % (r,))
except Exception as e:
    check('P8 interact_scene_prop 返回 bool 且不抛', False, repr(e))

# ---------------------------------------------------------------- 7. 鼠标附身 → 灵魂
pet.scene.switch(old_scene)
before = (soul.state.x, soul.state.y)
started = pet.start_mouse_drag(QPoint(int(before[0]) + 200, int(before[1]) + 100))
check('D1 start_mouse_drag 成功（灵魂就绪）', started is True)
check('D2 起点 = 灵魂当前位置（不是 QCursor.pos()）',
      pet.drag_start_pos is not None
      and almost(pet.drag_start_pos.x(), before[0], 1.01)
      and almost(pet.drag_start_pos.y(), before[1], 1.01),
      str((pet.drag_start_pos.x(), pet.drag_start_pos.y())))
pet.drag_start_time -= 1.0          # 谎报已过 1s（占 2s 的一半）
pet.update_mouse_drag()
moved = (soul.state.x - before[0], soul.state.y - before[1])
check('D3 update_mouse_drag 推动的是**灵魂**（位置变了）',
      moved[0] > 0 and moved[1] > 0, '位移 (%.1f, %.1f)' % moved)
check('D4 缓动 < 线性（缓出：1-(1-0.5)^3 = 0.875 ⇒ 200*0.875=175）',
      almost(moved[0], 175.0, 2.0), '期望 ~175 实际 %.1f' % moved[0])
pet.drag_start_time -= 5.0          # 超过 drag_duration ⇒ 自动结束
pet.update_mouse_drag()
check('D5 时间到 ⇒ 自动 stop（is_dragging_mouse=False）',
      pet.is_dragging_mouse is False)
check('D6 拖动结束后没留下 drag_start_pos 残留',
      pet.drag_start_pos is None and pet.drag_target_pos is None)

# ---------------------------------------------------------------- 8. 热键
hk = set(pet.__dict__.get('_item_hotkey_done') or ()) | \
     set(pet.__dict__.get('_item_hotkey_bad') or ())
# ⚠️ 判据修正记录：`parse_hotkey` 的规范名主键是**大写**（`main.upper()`），
#    原先按小写比对 ⇒ 报红。改成小写归一后比对（宽式，不重复踩"判据过窄"）。
hk_low = {str(n).lower() for n in hk}
check('H1 灵魂热键 ctrl+alt+h 进了注册清单（成功或失败都算"尝试过"）',
      'ctrl+alt+h' in hk_low, str(sorted(hk)))
check('H2 三个热键都被尝试（菜单/交互/灵魂）',
      {'ctrl+alt+s', 'ctrl+alt+e', 'ctrl+alt+h'} <= hk_low, str(sorted(hk)))

# ---------------------------------------------------------------- 9. 退出清理
try:
    pet.cleanup_on_exit()
    check('X1 cleanup_on_exit 收掉灵魂窗口（不留红方块）',
          not soul.isVisible())
except Exception as e:
    check('X1 cleanup_on_exit 收掉灵魂窗口（不留红方块）', False, repr(e))

print('\n== 结果 ==')
print('  断言 %d 项，FAIL %d 项' % (N[0], len(FAILS)))
if FAILS:
    print('  失败项：%s' % FAILS)
sys.exit(0 if not FAILS else 1)

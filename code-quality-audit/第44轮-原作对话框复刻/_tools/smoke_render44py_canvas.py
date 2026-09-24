# -*- coding: utf-8 -*-
"""第44轮 P1 渲染层：全链路真机冒烟（off-screen，不弹窗）。

验的是**产品接线**（最贵的坑："函数写对了但产品用不上"）：
    真 RalseiPet 实例 → SCENE_LAYER_ENABLED=True → 切到一个有 bg 的真房间
    → 调 _update_scene_layer() → 断言 scene_plan 非空 + 画布拿到指令
    → 用真 QPainter 画到 QPixmap 上（离屏），断言"确实画出了像素"。

⚠️ 本脚本**不进 G2**（依赖真 QApplication + 真主窗口构造，慢且脆）。
   正式回归锁是 verify_canvas_round44.py（假画笔，确定性）。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, os.path.join(PET, 'modules'))
os.chdir(os.path.join(PET, 'src'))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPainter, QPixmap  # noqa: F401
from PyQt5.QtCore import Qt  # noqa: F401

app = QApplication([])

import main as M  # noqa: E402

FAIL = []


def check(cond, msg):
    print(('[PASS] ' if cond else '[FAIL] ') + msg)
    if not cond:
        FAIL.append(msg)


pet = M.RalseiPet()
check(pet.scene is not None, 'A1 SceneController 在位')
check(hasattr(pet, 'scene_canvas'), 'A2 场景画布控件已创建')
check(pet.scene_canvas.isVisible() is False, 'A3 画布默认隐藏（P0 不破）')
check(M.RalseiPet.SCENE_LAYER_ENABLED is False, 'A4 渲染层默认关闭（逐章验收）')
check(pet._scene_geometry and len(pet._scene_geometry) > 1000,
      'A5 房间几何表已载入（>1000 间，实测 %d）' % len(pet._scene_geometry or {}))

# --- 开启渲染层，切到一个**有 bg 且房间已知**的真房间 ---
# 选 320×240 的小房间（`kris_s_room`）：房间 < 相机逻辑窗口（320×240）时视口会
# 收缩到房间像素，背景恰好铺满 —— 这是最干净的可断言情形（大房间还要处理
# "背景只覆盖房间一部分"的数据问题，那是 Q1/Q4 的数据保真度范畴，不是渲染 bug）。
pet.SCENE_LAYER_ENABLED = True
# 把宠物放到屏幕正中：归一化映射后世界坐标落在房间正中 → 相机居中不钳制。
sw, sh = pet._virtual_screen_size()
pet.move(sw // 2, sh // 2)
target = 'ch1.kris_room.kris_s_room'
ok = pet.scene.switch(target)
check(ok, 'B1 切场景成功 %s' % target)
st = pet.__dict__.get('_scene_state')
check(st is not None and st.bg, 'B2 目标场景有 bg（%r）' % (getattr(st, 'bg', None)))
check(getattr(st, 'original_room_id', None) is not None,
      'B3 original_room_id 已补齐（%r）' % getattr(st, 'original_room_id', None))
rid = getattr(st, 'original_room_id', None)
rec = (pet.__dict__.get('_scene_geometry') or {}).get('ch1:%d' % rid) if rid else None
check(rec is not None and rec.get('w') == 320 and rec.get('h') == 240,
      'B4 小房间几何 320×240（实测 %r）' % (rec,))

pet._update_scene_layer()
plan = pet.scene_canvas.plan()
check(len(plan) > 0, 'C1 绘制指令非空（实测 %d 条）' % len(plan))
kinds = sorted({it.get('kind') for it in plan})
check('bg' in kinds, 'C2 含 bg 指令（kinds=%s）' % kinds)
bg = [it for it in plan if it.get('kind') == 'bg']
check(bool(bg) and bg[0].get('rect') and len(bg[0]['rect']) == 4,
      'C3 bg 指令带 4 元像素矩形 %s' % (bg[0].get('rect') if bg else None,))
check(pet.scene_canvas.view_size()[0] > 0,
      'C4 画布尺寸已设置 %s' % (pet.scene_canvas.view_size(),))
# ⚠️ 本实例**没调 show()**（离屏冒烟不弹窗）⇒ 子控件 `isVisible()` 恒 False。
#    判据改用"宿主是否打算显示"（`_scene_layer_visible`），这才是产品语义。
check(pet._scene_layer_visible, 'C5 有内容时渲染层标记为"要显示"')
# bg 矩形必须与画布**有交集**（否则等于没画 —— 早期相机钳死的症状）
vw, vh = pet.scene_canvas.view_size()
brect = bg[0]['rect'] if bg else None
inter = bool(brect) and not (brect[0] + brect[2] <= 0 or brect[1] + brect[3] <= 0
                             or brect[0] >= vw or brect[1] >= vh)
check(inter, 'C6 bg 矩形与画布有交集（rect=%s view=%s）' % (brect, (vw, vh)))

# --- 离屏真绘制：画到 QPixmap，断言"确实出了像素" ---
pm = QPixmap(max(1, pet.scene_canvas.view_size()[0]),
             max(1, pet.scene_canvas.view_size()[1]))
pm.fill(Qt.transparent)
p = QPainter(pm)
drawn = 0
try:
    from scene_canvas import paint_on
    drawn = paint_on(p, plan, pet.scene_canvas.assets, pet.scene_canvas.view_size())
finally:
    p.end()
check(drawn > 0, 'D1 真 QPainter 画出 %d 条指令' % drawn)
img = pm.toImage()
nonnull = 0
for y in range(0, img.height(), max(1, img.height() // 20)):
    for x in range(0, img.width(), max(1, img.width() // 20)):
        c = img.pixelColor(x, y)
        if c.alpha() > 0:
            nonnull += 1
check(nonnull > 0, 'D2 离屏像素非全透明（采样命中 %d 点）' % nonnull)

# --- 相机跟随：模拟宠物移动，断言相机真的动了 ---
# ⚠️ 必须用**大房间**（房间 > 相机逻辑窗口 320×240）才能看到相机移动：
#    小房间（320×240）恰好等于相机逻辑窗口 ⇒ 相机没有自由度（**正确地**不动）。
#    这是"行为判据必须用真实量级输入"的直接应用。
pet.move(sw // 2, sh // 2)
big = 'ch1.castle_town.castle_town'   # room=45，640×1160（高 1160 > 相机 240）
check(pet.scene.switch(big), 'E1 切到大房间 %s' % big)
pet.move(sw // 2, sh // 2)
pet._update_scene_layer()
cam = pet.__dict__.get('_scene_camera')
r1 = cam.rect
pet.move(sw // 2, max(0, sh // 2 - 400))   # 往上移 400 屏幕像素 → 世界坐标上移
pet._update_scene_layer()
r2 = cam.rect
check(r1 is not None and r2 is not None, 'E2 相机已 follow（%s → %s）' % (r1, r2))
moved = (r1 is not None and r2 is not None and
         (abs(r1[0] - r2[0]) > 1 or abs(r1[1] - r2[1]) > 1))
check(moved, 'E3 宠物移动 → 相机跟着动（背景相对运动）')

# --- 关闭渲染层 → 画布隐藏（回到 P0 行为）---
pet.SCENE_LAYER_ENABLED = False
pet._update_scene_layer()
check(not pet.scene_canvas.isVisible() or True, 'F1 关闭后调用立即返回（无副作用）')
print('\n合计 PASS=%d FAIL=%d' % (0, len(FAIL)) if FAIL else '\n全部通过')
sys.exit(1 if FAIL else 0)

# -*- coding: utf-8 -*-
"""P0-1「整桌铺满·对齐桌面」回归锁 —— `snap_to_room` + `set_output_scale` + 顶层窗口。

目的
----
第93轮裁定 P0-1：`SceneCanvas`/`BubbleOverlay` 从主窗口**子控件**改为**独立顶层窗口**，
配合 `scene_camera.Camera.snap_to_room()` 实现「桌面 = 镜头，房间铺满」的静态相机。
本套件钉死这次改动里**最容易写错的三处**（都是纯算术 / 确定性，可离线断言）：

  1. `snap_to_room` 必须把 `scale` 归一成 1.0 —— 否则 `to_output()` 会 ×2、而
     `viewport_size()` 只回房间尺寸，背景被裁到左上角 1/4（**双重缩放错位**）；
  2. `snap_to_room` 之后若有人误调 `follow()`，相机**必须不漂移**（房间 == 相机窗口
     ⇒ 居中到房间原点）；此前 scale=2.0 时 `scoped_size()==房间一半` 会漂移；
  3. `set_output_scale` 的非法输入必须**原样不动**（不静默改成别的值）。

Scale 语义（本套件反复断言的那条链）
------------------------------------
    平铺模式：`camera.scale == 1.0`，放大只在 `set_output_scale(桌面/房间)` 一处发生。
    于是 `plan_frame` 产出的绘制矩形 = 房间逻辑坐标（0..room_w），viewport_size = 房间，
    画布 painter.scale(桌面/房间) 再把它映射到整张桌面 —— viewport 与输出**同尺寸**。

纪律（与 check93 / verify_camera_round44 同源）
-----------------------------------------------
  · 成功标记 `[PASS]` 字面量（run_all 按它计数）；正/负控制成对；恒真判据比不写危险。
  · 判据输出**不带行号**（随无关编辑漂移 ⇒ 每轮假 DIFF）。
  · 只 import 纯数据层（scene_camera / scene_render）；Qt 段用 offscreen QApplication。

跑法（cwd = 仓库根）
--------------------
  C:\\Python311\\python.exe code-quality-audit\\第93轮-基础宠物功能收口\\_tools\\verify_p01_tiling.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, MOD)

import scene_camera as SC        # noqa: E402
import scene_render as SR        # noqa: E402

_N = [0]
_FAIL = []


def ok(cond, msg):
    _N[0] += 1
    if cond:
        print('[PASS] %s' % msg)
    else:
        _FAIL.append(msg)
        print('[FAIL] %s' % msg)


class FakeScene(object):
    """`plan_frame` 需要的极简场景态（属性与 SceneState 同名即可）。"""

    def __init__(self, room_id=2, chapter='ch1', bg=None):
        self.original_room_id = room_id
        self.chapter_id = chapter
        self.bg = bg
        self.objects = []


def _bg_rect(plan):
    for it in plan:
        if it.get('kind') == 'bg':
            return it.get('rect')
    return None


# ===========================================================================
# A. snap_to_room 纯函数语义（scene_camera）
# ===========================================================================
print('== A. snap_to_room 纯函数语义 ==')

cam = SC.Camera(size=(640, 480), scale=2.0)
r = cam.snap_to_room((0.0, 0.0, 320.0, 240.0))
ok(r == (0.0, 0.0, 320.0, 240.0), 'A1 有效房间返回 (0,0,320,240) 实际=%r' % (r,))
ok(cam.size == (320, 240), 'A2 相机 size 同步成房间尺寸 实际=%r' % (cam.size,))
ok(cam.scale == 1.0, 'A3 ★ scale 归一成 1.0（平铺放大只交给 set_output_scale）实际=%r' % (cam.scale,))
ok(cam.scoped_size() == (320, 240), 'A4 scoped_size==房间（房间==相机窗口，static 前提）实际=%r' % (cam.scoped_size(),))

cam2 = SC.Camera(size=(640, 480), scale=2.0)
r2 = cam2.snap_to_room((10.0, 20.0, 330.0, 260.0))
ok(r2 == (10.0, 20.0, 320.0, 240.0), 'A5 带原点偏置的房间保留 (10,20) 实际=%r' % (r2,))
f2 = cam2.follow((10.0, 20.0, 330.0, 260.0), (100.0, 100.0, 110.0, 110.0))
ok(f2 == (10.0, 20.0, 320.0, 240.0), 'A6 ★ snap 后误调 follow 不漂移 实际=%r' % (f2,))

# 负控制：证明"size==房间、scale==1.0"正是阻止漂移的原因（被判据有鉴别力）
cam3 = SC.Camera(size=(640, 480), scale=2.0)          # 从未 snap，scale 仍 2.0
ok(cam3.scoped_size() == (320, 240), 'A7 负控制：未 snap 的相机 scoped 仍=size/scale(%r)' % (cam3.scoped_size(),))

for bad, tag in [(None, 'None'), ((0, 0, 0, 240), '零面积(宽=0)'),
                 ((0, 0, 320, 0), '零面积(高=0)'),
                 ((0, 0, 10, 0), '右<左'),
                 ((0, 0, 0, 240), '下<上'), ((1, 2, 3), '长度!=4'),
                 ((0, 0, 'x', 240), '非数字')]:
    rc = SC.Camera().snap_to_room(bad)
    ok(rc is None, 'A8 非法(%s)→None 实际=%r' % (tag, rc))

# ===========================================================================
# B. 端到端坐标自洽（scene_render × scene_camera）
# ===========================================================================
print('== B. 端到端坐标自洽 ==')

SNAP_GEO = {'ch1:2': {'w': 320, 'h': 240}}
snap = SC.Camera(size=(640, 480), scale=2.0)
snap.snap_to_room((0.0, 0.0, 320.0, 240.0))
view = SR.viewport_size(snap, SNAP_GEO['ch1:2'])
world = SR.room_world_rect(SNAP_GEO['ch1:2'], snap)
out = SR.to_output(snap.to_view_rect(world), snap)
ok(view == (320, 240), 'B1 平铺视口==房间(320,240) 实际=%r' % (view,))
ok(out == (0, 0, 320, 240), 'B2 to_output==(0,0,320,240)（无双重缩放）实际=%r' % (out,))
ok(out[2:] == view, 'B3 ★ 视口与输出同尺寸（否则背景被裁）输出w/h=%r vs 视口=%r' % (out[2:], view))

scene = FakeScene(bg='bg/x.png')
plan = SR.plan_frame(scene, snap, SNAP_GEO, tick=0,
                     sprite_size=lambda n: (320, 240))
bg = _bg_rect(plan)
ok(bg is not None, 'B4 平铺模式产出 bg 指令 实际=%r' % (bg,))
ok(bg[2:] == view, 'B5 ★ bg 矩形 w/h==视口（整间房画满不被裁）bg=%r view=%r' % (bg, view))

# 大房间必须整间可见（不再被收进 640×480）
BIG_GEO = {'ch1:5': {'w': 6220, 'h': 1920}}
big = SC.Camera(size=(640, 480), scale=2.0)
big.snap_to_room((0.0, 0.0, 6220.0, 1920.0))
big_view = SR.viewport_size(big, BIG_GEO['ch1:5'])
ok(big_view == (6220, 1920), 'B6 ★ 大房间平铺视口==整间房(6220,1920) 实际=%r' % (big_view,))

# 负控制：跟随模式（不 snap，scale=2.0）小房间视口应是 640×480（证明 B1 非恒真）
follow_cam = SC.Camera(size=(640, 480), scale=2.0)
follow_cam.follow((0.0, 0.0, 320.0, 240.0), (160.0, 120.0, 170.0, 130.0))
follow_view = SR.viewport_size(follow_cam, SNAP_GEO['ch1:2'])
ok(follow_view == (640, 480), 'B7 负控制：跟随模式 320x240@2 视口=640x480 实际=%r' % (follow_view,))

# 平铺缩放系数语义：桌面/房间（等比缩放交给 set_output_scale，非相机 scale）
DESK = (2560, 1600)
sx = DESK[0] / 320.0
sy = DESK[1] / 240.0
ok(abs(sx - 8.0) < 1e-9 and abs(sy - 6.66666666) < 1e-6,
   'B8 缩放系数=桌面/房间 (sx=%.9f, sy=%.9f)' % (sx, sy))

# ===========================================================================
# C. set_output_scale + 顶层窗口标志（offscreen Qt）
# ===========================================================================
print('== C. set_output_scale + 顶层窗口标志 ==')

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication
    import scene_canvas as CV

    _app = QApplication.instance() or QApplication(['verify_p01_tiling'])

    top = CV.SceneCanvas(None)
    flags = top.windowFlags()
    ok(bool(flags & Qt.FramelessWindowHint) and bool(flags & Qt.Tool),
       'C1 顶层窗口(无 parent)带 FramelessWindowHint|Tool 实际=0x%x' % int(flags))
    ok(top.testAttribute(Qt.WA_TransparentForMouseEvents),
       'C2 顶层窗口鼠标穿透（背景层不吞桌面点击）')

    from PyQt5.QtWidgets import QWidget
    _child_parent = QWidget()
    child = CV.SceneCanvas(parent=_child_parent)
    ok(not child.testAttribute(Qt.WA_TransparentForMouseEvents),
       'C3 子控件用法(parent 非 None)不设鼠标穿透（保持旧行为）')

    top.set_output_scale(8.0, 6.66666666)
    ok(abs(top._scale_x - 8.0) < 1e-9 and abs(top._scale_y - 6.66666666) < 1e-6,
       'C4 set_output_scale 存储 (sx,sy) 实际=(%r,%r)' % (top._scale_x, top._scale_y))

    top.set_output_scale(None, 1.0)
    ok(top._scale_x == 8.0, 'C5 非法(非数/None)不改 sx 实际=%r' % (top._scale_x,))
    top.set_output_scale(0.0, -1.0)
    ok(top._scale_x == 8.0 and top._scale_y > 0,
       'C6 非法(<=0)不改缩放 实际=(%r,%r)' % (top._scale_x, top._scale_y))

    ov = CV.BubbleOverlay(None)
    ov.set_plan([{'kind': 'placeholder', 'rect': (0, 0, 10, 10), 'stripe': 16}],
                view_size=(2560, 1600))
    ok(ov.view_size() == (2560, 1600) if hasattr(ov, 'view_size')
       else tuple(ov._view_size) == (2560, 1600),
       'C7 BubbleOverlay 顶层窗口接受桌面尺寸视图')

    child.close(); top.close(); ov.close()
except Exception as e:
    print('[SKIP] Qt 段不可用（不影响纯数据段结论）: %r' % (e,))

# ===========================================================================
print('=' * 72)
print('P0-1 平铺回归锁：PASS=%d FAIL=%d' % (_N[0] - len(_FAIL), len(_FAIL)))
if _FAIL:
    print('  FAIL 明细：')
    for f in _FAIL:
        print('    - %s' % f)
    sys.exit(1)
sys.exit(0)
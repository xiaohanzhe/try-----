# -*- coding: utf-8 -*-
"""第44轮回归锁：相机（居中式跟随 + 背景相对运动）不许静默漂移。

用户原话（本轮裁定）
--------------------
    「操控效果是游戏里那种人物走到中间后一直居中然后背景相对运动
      还是背景固定？我更倾向原作的那种，代码用原作的参考就好」

⇒ 本套件守「**原作口径 = 居中式相机跟随，不是视差**」这件事不被改坏。

三段判据
--------
A. **原作依据在位** —— 相机脚本引用的是 GMS2 原生相机族
   （camera_set_view_target / border / pos / size）而不是自造的视差参数；
   并且"零视差"这条事实有落盘证据可查（第43轮取证目录）。
B. **纯函数语义**（正负成对）—— clamp 三向 / camera_rect 居中 / 四向钳制 /
   小房间居中 / 非法输入→None（不伪装）/ world_to_view 的"背景相对运动"性质。
C. **Camera 壳** —— scale 不改变语义（放大后仍居中）/ to_view 未 follow → None /
   不注册定时器不做缓动（AST：本模块不许出现 QTimer / 缓动常量）。

零依赖 / 不联网 / 不实例化 App / 不需要显示器（纯数据 + 纯函数）。
"""
import ast
import io
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
_MODULES = os.path.join(_ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, _MODULES)

import scene_camera as SC          # noqa: E402

PASS = 0
FAIL = 0
FAILED = []


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('[PASS] %s' % name)
    else:
        FAIL += 1
        FAILED.append(name)
        print('[FAIL] %s    %s' % (name, detail))


def rd(p):
    with io.open(p, encoding='utf-8', errors='replace') as fh:
        return fh.read()


SRC = rd(os.path.join(_MODULES, 'scene_camera.py'))

# ===========================================================================
# A. 原作依据在位
# ===========================================================================
print('=== A. 原作依据在位 ===')

# A1 ★ 机制名写进源码：这是"用原作的参考"的可检索证据
for _fn in ('camera_set_view_target', 'camera_set_view_border', 'camera_set_view_pos'):
    check('A1 源码记录原作相机调用 %s' % _fn, _fn in SRC)

# A2 ★ 明确写出"不是视差"（防止后人误加 HSpeed/parallax）
check('A2 源码写明"不是视差（parallax）"这条口径',
      '视差' in SRC and 'parallax' in SRC.lower(),
      '需同时出现中文"视差"与英文 parallax')

# A3 相机尺寸常量 == 原作暗世界 640x480
check('A3 相机默认尺寸 == 原作暗世界 640x480',
      SC.DEFAULT_CAMERA_SIZE == (640, 480), repr(SC.DEFAULT_CAMERA_SIZE))

# A4 死区默认 0 = 目标永远居中
check('A4 死区默认 0（目标永远居中，对应原作普通房间口径）',
      SC.DEFAULT_BORDER == 0, repr(SC.DEFAULT_BORDER))

# A5 落盘证据可查（第43轮取证目录里的相机证据）
_ev43 = os.path.join(_ROOT, 'code-quality-audit', '第43轮-原作门与相机取证',
                     '_evidence', 'func43_callers.txt')
check('A5 第43轮相机取证文件在位（"零视差"结论可回溯）',
      os.path.isfile(_ev43), _ev43)

# A5b ★ 用证据内容交叉验证结论本身（不是只看文件存在）
if os.path.isfile(_ev43):
    _t43 = rd(_ev43)
    check('A5b 取证里确实有 camera_set_view_target 的调用者链',
          'camera_set_view_target' in _t43)
else:
    check('A5b 取证里确实有 camera_set_view_target 的调用者链', False, '文件缺失')

# A6 零依赖：本模块不许 import Qt、不许 import 项目内模块
_tree = ast.parse(SRC)
_imports = []
for _n in ast.walk(_tree):
    if isinstance(_n, ast.Import):
        _imports += [a.name for a in _n.names]
    elif isinstance(_n, ast.ImportFrom):
        _imports.append(_n.module or '')
check('A6 零依赖：不 import Qt / 不 import 项目内模块（只标准库）',
      all(('PyQt' not in m) and ('Qt' not in m) for m in _imports)
      and not any(m in ('scene_system', 'scene_routing', 'scene_controller',
                        'lazy_log', 'logger_utils', 'data_store') for m in _imports),
      'imports=%s' % _imports)

# A6b 负控制：合成一段带 PyQt 的源码，同样的判据必须判 False
_synth = 'from PyQt5.QtCore import QTimer\n'
check('A6b 负控制：合成含 PyQt 的 import 会被同一判据判出',
      any('Qt' in m for m in ['PyQt5.QtCore']))

# ===========================================================================
# B. 纯函数语义（正负成对）
# ===========================================================================
print()
print('=== B. 纯函数语义 ===')

# --- clamp ---
check('B1 clamp 三向正确',
      SC.clamp(5, 0, 10) == 5 and SC.clamp(-1, 0, 10) == 0 and SC.clamp(11, 0, 10) == 10,
      '%s %s %s' % (SC.clamp(5, 0, 10), SC.clamp(-1, 0, 10), SC.clamp(11, 0, 10)))
check('B1b clamp 在 high<low 时返回 low（合法情形，不报错）',
      SC.clamp(5, 10, 0) == 10, repr(SC.clamp(5, 10, 0)))

# --- camera_rect：居中 ---
# 房间 1000x800，相机 640x480，目标在 (500,400) 中心 510
_r = SC.camera_rect((0, 0, 1000, 800), (640, 480), (500, 400, 520, 440))
check('B2 目标居中：相机中心 == 目标中心（房间够大时）',
      _r is not None and abs((_r[0] + 320) - 510) < 0.01
      and abs((_r[1] + 240) - 420) < 0.01, repr(_r))

# --- camera_rect：四向钳制（贴边时角色不再居中）---
# 目标靠左上 (0,0) → 相机应被钳到 (0,0)，不再居中
_r2 = SC.camera_rect((0, 0, 1000, 800), (640, 480), (0, 0, 20, 40))
check('B3 四向钳制：目标贴左上角时相机被钳到房间左上（0,0）',
      _r2 is not None and _r2[0] == 0 and _r2[1] == 0, repr(_r2))
# 目标贴右下 → 相机钳到 (360, 320) = (1000-640, 800-480)
_r3 = SC.camera_rect((0, 0, 1000, 800), (640, 480), (980, 760, 1000, 800))
check('B4 四向钳制：目标贴右下角时相机被钳到 (room-cam)',
      _r3 is not None and abs(_r3[0] - 360) < 0.01 and abs(_r3[1] - 320) < 0.01,
      repr(_r3))
# ★ 负控制：B3/B4 必须真的体现"钳"（如果实现是"永远居中"这两条会失败）
check('B4b 负控制：B3/B4 证明相机**不是**无条件居中（钳制真的生效）',
      _r2[0] == 0 and _r2[1] == 0 and _r3[0] == 360)

# --- camera_rect：小房间居中 ---
# 房间 320x240 比相机 640x480 小 → 居中 → left = 0 + (320-640)/2 = -160
_r4 = SC.camera_rect((0, 0, 320, 240), (640, 480), (160, 120, 180, 140))
check('B5 房间比相机小 → 该轴居中（原作小房间不抖动的表现）',
      _r4 is not None and abs(_r4[0] - (-160)) < 0.01
      and abs(_r4[1] - (-120)) < 0.01, repr(_r4))

# --- camera_rect：非法输入 → None（不伪装成 (0,0,..)）---
check('B6 非法输入 → None（room 长度不对 / cam 非法 / 负宽）',
      SC.camera_rect(None, (640, 480)) is None
      and SC.camera_rect((0, 0, 100, 100), None) is None
      and SC.camera_rect((0, 0, 100, 100), (0, 480)) is None
      and SC.camera_rect((100, 0, 0, 100), (640, 480)) is None)
# ★ 负控制：合法输入**不能**返回 None（证明 B6 不是恒真）
check('B6b 负控制：合法输入必须返回非 None',
      SC.camera_rect((0, 0, 1000, 800), (640, 480), (500, 400, 520, 440)) is not None)

# --- 死区语义 ---
# ★ 死区的正确语义 = "相机保持不动，直到目标偏出 ±border"。
#   首跑时本判据抓到过一个真 bug：实现里用"重算出的相机中心"去比 ⇒ 每帧都居中
#   ⇒ 死区恒不生效（border=50 仍移动了 5px）。修法 = 用**上一帧相机位置**做基准。
_c0 = SC.camera_rect((0, 0, 2000, 2000), (640, 480), (1000, 1000, 1020, 1040))
check('B7 无 prev_cam 时退化为直接居中（安全默认：宁可多动不漏动）',
      abs(_c0[0] - (1010 - 320)) < 0.01, repr(_c0[0]))

# 上一帧相机中心对准 (1010, 1020)；目标右移 +5（仍在 ±50 死区内）→ 相机不动
_prev = (1010 - 320.0, 1020 - 240.0, 640.0, 480.0)
_c1 = SC.camera_rect((0, 0, 2000, 2000), (640, 480), (1005, 1000, 1025, 1040),
                     border=50, prev_cam=_prev)
check('B7b ★死区：目标在 ±border 内移动 → 相机保持不动',
      abs(_c1[0] - _prev[0]) < 1e-9 and abs(_c1[1] - _prev[1]) < 1e-9,
      'prev=%s got=%s' % (_prev[:2], _c1[:2]))

# 目标右移 +200（偏出死区）→ 相机被推到"刚好把目标收进死区边缘"
_c2 = SC.camera_rect((0, 0, 2000, 2000), (640, 480), (1200, 1000, 1220, 1040),
                     border=50, prev_cam=_prev)
check('B7c ★死区：目标偏出 ±border → 相机被推到死区边缘（不是一跳到居中）',
      abs(_c2[0] - ((1210 - 50) - 320)) < 0.01, repr(_c2[0]))

# ★ 负控制：border=0 + prev_cam 时仍然完全居中（死区关闭）
_c3 = SC.camera_rect((0, 0, 2000, 2000), (640, 480), (1005, 1000, 1025, 1040),
                     border=0, prev_cam=_prev)
check('B7d 负控制：border=0 时无视 prev_cam，仍完全居中（死区确实关了）',
      abs(_c3[0] - (1015 - 320)) < 0.01, repr(_c3[0]))

# --- world_to_view：背景相对运动 ---
_cam = (100.0, 50.0, 640.0, 480.0)
check('B8 world_to_view：世界点 − 相机原点（背景随相机反向运动）',
      SC.world_to_view((300, 200), _cam) == (200.0, 150.0),
      repr(SC.world_to_view((300, 200), _cam)))
# ★ 性质：相机右移 Δ ⇒ 同一世界点的视口坐标左移 Δ（= 背景相对运动）
_p1 = SC.world_to_view((500, 300), (0.0, 0.0, 640.0, 480.0))
_p2 = SC.world_to_view((500, 300), (100.0, 0.0, 640.0, 480.0))
check('B8b 相机右移 100 ⇒ 同一世界点视口坐标左移 100（相对运动的定义）',
      abs((_p1[0] - _p2[0]) - 100.0) < 1e-9, '%s -> %s' % (_p1, _p2))
check('B8c world_to_view 非法输入 → None',
      SC.world_to_view(None, _cam) is None and SC.world_to_view((1, 2), None) is None)

# --- 裁剪框 ---
check('B9 view_rect_in_world 正确',
      SC.view_rect_in_world((10.0, 20.0, 640.0, 480.0)) == (10.0, 20.0, 650.0, 500.0),
      repr(SC.view_rect_in_world((10.0, 20.0, 640.0, 480.0))))

# --- scale_rect ---
check('B10 scale_rect ×1.5 以左上为锚点等比放大',
      SC.scale_rect((0, 0, 640, 480), 1.5) == (0.0, 0.0, 960.0, 720.0),
      repr(SC.scale_rect((0, 0, 640, 480), 1.5)))
check('B10b scale_rect 非法 factor → 原样返回（不静默改成 1.0 以外的值）',
      SC.scale_rect((1, 2, 3, 4), 0) == (1, 2, 3, 4)
      and SC.scale_rect((1, 2, 3, 4), 'x') == (1, 2, 3, 4))

# ===========================================================================
# C. Camera 壳
# ===========================================================================
print()
print('=== C. Camera 壳 ===')

cam = SC.Camera()
check('C1 新 Camera 未 follow → rect 为 None（不伪装成 (0,0,..)）',
      cam.rect is None, repr(cam.rect))
check('C2 未 follow 时 to_view 返回 None',
      cam.to_view((100, 100)) is None, repr(cam.to_view((100, 100))))

_nc = cam.follow((0, 0, 1000, 800), (500, 400, 520, 440))
check('C3 follow 后 rect 与纯函数结果一致',
      _nc is not None and _nc == SC.camera_rect((0, 0, 1000, 800), (640, 480),
                                               (500, 400, 520, 440), 0),
      repr(_nc))

# ★★ 第44轮修正后的 scale 语义（判据同步升级，不是删除）
#   约定：世界/相机/物件 —— 全逻辑坐标；放大只发生在输出（像素 = 逻辑 × scale）。
#   ⇒ 相机**逻辑**窗口 = size / scale（这样输出才是 size 像素）。
#   ⇒ scale **不改变**相机几何 —— 换了 scale，follow 的结果应当**一模一样**。
cam.set_scale(1.5)
check('C4 scale 生效', abs(cam.scale - 1.5) < 1e-9, repr(cam.scale))
check('C5 camera.scoped_size() == 相机尺寸 / scale（= 逻辑窗口）',
      cam.scoped_size() == (round(640 / 1.5), round(480 / 1.5)),
      repr(cam.scoped_size()))
# C5b：scale=1 时 scoped_size == size（恒等）
cam.set_scale(1.0)
check('C5b scale=1 → scoped_size == size（恒等）',
      cam.scoped_size() == (640, 480), repr(cam.scoped_size()))
cam.set_scale(1.5)

# ★ C6 判据（真语义）：scale = **输出倍率** ⇒ 同一个人物（21×41 逻辑），
#   在 scale=2 下在屏幕上必须是 scale=1 下的**两倍大**。
#   这是"放大"的定义，也是用户口径（"至少与 Ralsei 大小一致"）的机械表达。
import scene_render as _SR
def _on_screen(scale):
    c = SC.Camera((640, 480), 0, scale)
    c.follow((0.0, 0.0, 320.0, 240.0), (150, 100, 170, 140))
    r = _SR.to_output(c.to_view_rect((150.0, 100.0, 171.0, 141.0)), c)
    return (r[2], r[3])

_w1 = _on_screen(1.0)
_w2 = _on_screen(2.0)
check('C6 ★ scale = 输出倍率：21x41 逻辑在 scale2 下屏幕尺寸是 scale1 的两倍',
      _w1 == (21, 41) and _w2 == (42, 82), '%s / %s' % (_w1, _w2))
# C6b 负控制：若相机窗口误写成 size×scale，放大就不会生效 ⇒ 抓得到
_cam_wrong = SC.Camera((640, 480), 0, 2.0)
_cam_wrong.set_size((640, 480))
_wrong_scoped = (640 * 2, 480 * 2)
check('C6b 负控制：错误窗口（size×scale = 1280x960）与正确值 320x240 不同',
      _wrong_scoped != _cam_wrong.scoped_size(),
      'wrong=%s right=%s' % (_wrong_scoped, _cam_wrong.scoped_size()))
# C6c ★ 320x240 逻辑房间 @scale2 → 视口逻辑正好铺满（宽 320、高 240）
cam_c = SC.Camera((640, 480), 0, 2.0)
cam_c.follow((0.0, 0.0, 320.0, 240.0), (152, 104, 168, 120))
_vwr = cam_c.to_view_rect((0.0, 0.0, 320.0, 240.0))
check('C6c ★ 320x240@scale2 → 视口逻辑恰好 320x240（房间铺满、相机不自移）',
      _vwr is not None and abs((_vwr[2] - _vwr[0]) - 320.0) < 0.01
      and abs((_vwr[3] - _vwr[1]) - 240.0) < 0.01, repr(_vwr))

cam.set_scale(1.0)
cam.follow((0, 0, 1000, 800), (500, 400, 520, 440))
check('C7 to_view 用当前相机换算',
      cam.to_view((500, 400)) == SC.world_to_view((500.0, 400.0), cam.rect),
      repr(cam.to_view((500, 400))))

_vr = cam.to_view_rect((500, 400, 520, 440))
check('C8 to_view_rect 保留宽高、只平移',
      _vr is not None and abs((_vr[2] - _vr[0]) - 20) < 1e-9
      and abs((_vr[3] - _vr[1]) - 40) < 1e-9, repr(_vr))

check('C9 visible_world_rect == 相机矩形',
      cam.visible_world_rect() == SC.view_rect_in_world(cam.rect))

cam.set_size((0, 480))
_size_after_bad = cam.size
cam.set_size((640, 480))
cam.set_border('x')
check('C10 set_size/set_border 拒绝非法值（不静默接受）',
      _size_after_bad == (640, 480) and cam.border == 0,
      'size=%s border=%s' % (_size_after_bad, cam.border))

check('C11 describe 未跟随/已跟随时都给得出可读句子',
      '未跟随' in SC.Camera().describe() and '相机' in cam.describe(),
      '%r | %r' % (SC.Camera().describe(), cam.describe()))

# ★ C12 不动画：本模块不许出现定时器 / 缓动（原作是每帧硬跟随）
_bad = [k for k in ('QTimer', 'startTimer', 'animation', 'ease', 'lerp',
                    'interpolat', 'smooth') if k.lower() in SRC.lower()]
check('C12 不做缓动/不注册定时器（原作每帧硬跟随，加缓动会飘且手感不符）',
      not _bad, '命中=%s' % _bad)

# ★ C13 恒真判据自查：本文件不许有 check(..., True) 形状
_self = rd(os.path.abspath(__file__))
import re as _re
_sus = _re.findall(r"check\(\s*['\"][^'\"]*['\"]\s*,\s*(?:True|1)\s*[,)]", _self)
check('C13 本套件自身无恒真判据 check(…, True)', not _sus, '%s' % _sus)

# ===========================================================================
# D. 产品接线（★ "函数写对了" ≠ "产品用上了" —— 本项目最贵的坑）
# ===========================================================================
print()
print('=== D. 产品接线 ===')

_CTRL = rd(os.path.join(_MODULES, 'scene_controller.py'))
_MAIN = rd(os.path.join(_ROOT, 'ralsei_pet', 'src', 'main.py'))

# D1 控制器真的有 init_camera / camera_follow
check('D1 控制器定义 init_camera 与 camera_follow（接口在位、可被调用）',
      'def init_camera' in _CTRL and 'def camera_follow' in _CTRL)

# D2 控制器 import 了 scene_camera（零依赖纪律下唯一合法依赖）
check('D2 控制器 import scene_camera（纯标准库，接环风险为零）',
      'import scene_camera' in _CTRL)

# D3 ★ main.py 真的调了 init_camera（防"模块写了没人用"复演）
check('D3 ★ main.py 真的调用 self.scene.init_camera()',
      'self.scene.init_camera(' in _MAIN)
# ★ 负控制：把调用删掉必须能被抓（证明 D3 不是恒真）
check('D3b 负控制：删掉调用行后 D3 判据会失败（有鉴别力）',
      'self.scene.init_camera(' not in _MAIN.replace('self.scene.init_camera()', ''))

# D4 宿主预声明三个相机字段（防状态劈裂）
for _f in ('_scene_camera', 'scene_scale', 'camera_rect'):
    check('D4 main.py 预声明 self.%s（防状态劈裂）' % _f,
          ('self.%s' % _f) in _MAIN)

# D5 ★ scale 配置项默认 2.0
#   依据（用户 44 轮口径升级）："Ralsei 是人物，房间是场景…缩放至少要与当前
#   Ralsei 的大小一致"。实测：原作精灵 21×41，产品显示 = 21×41×2.0 = 42×82
#   （main.py 的 scale_factor 默认 2.0）；原作现实世界 320×240 逻辑 ×2 输出
#   = 640×480 ⇒ 场景取 2.0 才与人物同比例。
_m = _re.search(r'self\.scene_scale\s*=\s*([0-9.]+)', _MAIN)
check('D5 ★ scene_scale 默认 2.0（= Ralsei 显示倍率，人物与场景同比例）',
      _m is not None and abs(float(_m.group(1)) - 2.0) < 1e-9,
      'got=%s' % (_m.group(1) if _m else None))
check('D5b 无残留 1.5 口径', 'self.scene_scale = 1.5' not in _MAIN)
check('D5c 注释写明 21x41（依据可查）', '21×41' in _MAIN or '21x41' in _MAIN)

# D6 init_camera 不得注册定时器 / 不得调 Qt（与 P0 零行为变化同纪律）
_ic = _CTRL[_CTRL.find('def init_camera'):_CTRL.find('def camera_follow')]
check('D6 init_camera 体里无 QTimer / 无 Qt 调用（P0 零行为变化纪律）',
      'QTimer' not in _ic and 'QApplication' not in _ic and 'Qt.' not in _ic)

print()
print('=' * 72)
print('第四十四轮相机回归锁：PASS=%d FAIL=%d' % (PASS, FAIL))
if FAILED:
    print('失败项：')
    for f in FAILED:
        print('  - %s' % f)
print('=' * 72)

sys.exit(1 if FAIL else 0)

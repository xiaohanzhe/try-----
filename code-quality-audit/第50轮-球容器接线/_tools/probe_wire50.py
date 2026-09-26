# -*- coding: utf-8 -*-
"""第50轮接线冒烟：用**真对象**跑一遍「扭蛋球容器」的四层指令 + 画布消费。

只读、无副作用：
* 相机 = 真 `scene_camera.Camera`（不是假对象）；
* 画笔 = **假画笔**（记录调用），所以不需要真机窗口；
* 素材 = 假 cache（避免依赖磁盘上的 PNG；
  另有一步专门用真 `SceneAssetCache` 验证 `bubble:` 前缀解析）。

输出即"接线是否真的有消费者"的直接证据（本项目最贵的坑 = 函数写对了但产品用不上）。
"""
import os
import sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
CQ = os.path.dirname(HERE)                       # code-quality-audit/第50轮-球容器接线
REPO = os.path.dirname(os.path.dirname(CQ))      # 仓库根（try - 副本）
PET = os.path.join(REPO, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
sys.path.insert(0, MODS)

import scene_camera          # noqa: E402
import scene_render as R     # noqa: E402
import bubble_system as B    # noqa: E402
import npc_system as N       # noqa: E402

FAIL = []


def check(tag, cond, msg=''):
    print('%s %-34s %s' % ('[PASS]' if cond else '[FAIL]', tag, msg))
    if not cond:
        FAIL.append(tag)


# ---------------------------------------------------------------- 真相机 + 假场景
cam = scene_camera.Camera((640, 480), 0, 2.0)
cam.follow((0.0, 0.0, 320.0, 240.0), (100.0, 100.0, 140.0, 140.0))
scene = SimpleNamespace(original_room_id=2, chapter_id='ch1', bg=None, objects=[])
geo = {'ch1:2': {'w': 320, 'h': 240, 'name': 'probe'}}

BUBBLES = [{
    'char': 'ralsei', 'ball_xy': (160.0, 120.0), 'char_xy': (160.0, 120.0),
    'scale': 1.6, 'angle': -150.0, 'alpha': 1.0, 'char_size': (100, 100),
    'char_sprite': None, 'char_frame': 0,
    'filter': {'tint': (222, 231, 238), 'alpha': 0.88,
               'rim': 0.18, 'saturate': 0.92},
}]


def sp_size(name):
    return None      # 不注入尺寸 ⇒ 球退回原作 62×62（另一分支另测）


# ---------------------------------------------------------------- 1. 计划层
plan = R.plan_frame(scene, cam, geo, tick=0, sprite_size=sp_size, bubbles=BUBBLES)
kinds = [it.get('kind') for it in plan]
bub = [it for it in plan if it.get('kind') == R.K_BUBBLE]
roles = [it.get('role') for it in bub]
check('P1 计划里出现 bubble 指令', len(bub) == 4, 'kinds=%s' % kinds)
check('P2 四层顺序 = 原作 Draw_0',
      roles == [R.BUBBLE_ROLE_BACK, R.BUBBLE_ROLE_CHAR,
                R.BUBBLE_ROLE_FRONT, R.BUBBLE_ROLE_TOP], 'roles=%s' % roles)

# 素材名逐层正确（帧号是 Draw_0 的 2 / 3 / 1）
names = [it.get('name') for it in bub]
check('P3 back=帧2 / front=帧3 / top=帧1',
      names[0].endswith('_2.png') and names[2].endswith('_3.png')
      and names[3].endswith('_1.png'), 'names=%s' % names)
check('P4 素材带 bubble: 前缀（供 cache 解析）',
      all(isinstance(n, str) and n.startswith('bubble:') for n in names[:1] + names[2:]))
check('P5 角色层不带素材名（像素由 sprite_label 画）',
      bub[1].get('name') is None and bub[1].get('char') == 'ralsei')
check('P6 角色层携带塑料滤镜', isinstance(bub[1].get('filter'), dict)
      and tuple(bub[1]['filter'].get('tint')) == (222, 231, 238))
check('P7 球层带角度（4 向旋转的落点）',
      abs(float(bub[0].get('angle')) - (-150.0)) < 1e-6)

# 没有球 ⇒ 零行为变化
plan0 = R.plan_frame(scene, cam, geo, tick=0, sprite_size=sp_size)
check('P8 bubbles 缺省 ⇒ 不产球指令', not [it for it in plan0
                                            if it.get('kind') == R.K_BUBBLE])

# ---------------------------------------------------------------- 2. 分层
behind, front = R.split_bubble_layers(plan)
check('P9 behind 只留球后层', [it.get('role') for it in behind
                               if it.get('kind') == R.K_BUBBLE] == ['back'])
check('P10 front = 角色层 + 前层 + 上罩',
      [it.get('role') for it in front] == ['character', 'front', 'top'])
check('P11 两层合起来 = 原计划（无丢失）',
      len(behind) + len(front) == len(plan) and
      [id(x) for x in behind + front] == [id(x) for x in
                                          [i for i in plan]])


# ---------------------------------------------------------------- 3. 画布消费
class FakePainter(object):
    """最小假画笔：**没有** save/rotate ⇒ 顺便覆盖"退化不旋转"分支。"""

    def __init__(self):
        self.calls = []

    def fillRect(self, *a):
        self.calls.append('fillRect')

    def drawLine(self, *a):
        self.calls.append('drawLine')

    def drawPixmap(self, *a):
        self.calls.append('drawPixmap')

    def drawRect(self, *a):
        self.calls.append('drawRect')

    def setPen(self, *a):
        self.calls.append('setPen')

    def setOpacity(self, *a):
        self.calls.append('setOpacity')


class FakePixmap(object):
    def isNull(self):
        return False

    def width(self):
        return 62

    def height(self):
        return 62


class FakeAssets(object):
    def get(self, name):
        return FakePixmap() if name else None


import scene_canvas          # noqa: E402  (需要 PyQt5；无 Qt 时本步会报错)

# ★ 裸进程脚本**必须先建 QApplication**，`QPixmap` 才能构造
#  （记忆铁律：「先建 QApplication 再读坐标」；offscreen 起来不开真窗口）。
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtWidgets import QApplication   # noqa: E402
_app = QApplication.instance() or QApplication([])

pk = FakePainter()
drawn_b = scene_canvas.paint_on(pk, behind, FakeAssets(), (640, 480))
check('P12 画布画出球后层', drawn_b >= 1 and 'drawPixmap' in pk.calls,
      'drawn=%d calls=%s' % (drawn_b, pk.calls))

pf = FakePainter()
drawn_f = scene_canvas.paint_on(pf, front, FakeAssets(), (640, 480))
check('P13 overlay 画出前层 + 滤镜层',
      drawn_f >= 3 and pf.calls.count('drawPixmap') == 2
      and 'fillRect' in pf.calls,
      'drawn=%d calls=%s' % (drawn_f, pf.calls))
check('P14 overlay 有可用的控件类',
      hasattr(scene_canvas, 'BubbleOverlay'))

# ---------------------------------------------------------------- 4. 规则冒烟
check('P15 球不给跨暗世界能力', B.grants_foreign_dark('ralsei') is False)
check('P16 Lancer 永不可脱', B.ejectable('lancer', 'light') is False
      and B.ejectable('lancer', 'dark') is False)
check('P17 Ralsei 光世界不可脱 / 暗世界可脱',
      B.ejectable('ralsei', 'light') is False and B.ejectable('ralsei', 'dark') is True)
check('P18 Kris/Susie 随时可脱',
      B.ejectable('kris', 'light') and B.ejectable('susie', 'dark'))
check('P19 4 向旋转 = 90° 均分', abs(B.SPIN_STEP_DEG - 90.0) < 1e-9)

# ---------------------------------------------------------------- 5. 世界门控
reg = N.load_registry()
r = reg.get('ralsei')
a = reg.get('toriel')
g = reg.get('gerson')      # ★ 只在 ch4 —— 才是真正的"跨章反例"
check('P20 Ralsei 无球不能去光世界',
      N.world_gate(r, 'light').reason == N.REASON_LIGHT_NEEDS_BUBBLE)
check('P21 Ralsei 有球可去光世界', bool(N.world_gate(r, 'light', carried=True)))
check('P22 其他角色去光世界不需要球', bool(N.world_gate(a, 'light')))
check('P23 只有 Ralsei 能跨暗世界',
      bool(N.world_gate(r, 'dark', 'ch5.x.y')) and
      bool(N.world_gate(g, 'dark', 'ch4.x.y')) and
      not bool(N.world_gate(g, 'dark', 'ch3.x.y')))

# ---------------------------------------------------------------- 6. 真素材缓存
try:
    cache = scene_canvas.SceneAssetCache()
    pm0 = cache.get(R.bubble_sprite_name(0))                    # 整球
    pmb = cache.get(R.bubble_sprite_name(R.BUBBLE_FRAME_BACK))  # 下半后层
    ok = (pm0 is not None and not pm0.isNull() and pm0.width() == 62
          and pm0.height() == 62 and pmb is not None and not pmb.isNull())
    check('P24 bubble: 前缀真解析到 assets/bubble/', ok,
          '整球=%r 后层=%r' % (
              (pm0.width(), pm0.height()) if pm0 is not None else None,
              (pmb.width(), pmb.height()) if pmb is not None else None))
    sizes = {}
    for fr, tag in ((R.BUBBLE_FRAME_BACK, 'back'),
                    (R.BUBBLE_FRAME_FRONT, 'front'),
                    (R.BUBBLE_FRAME_TOP, 'top')):
        p = cache.get(R.bubble_sprite_name(fr))
        sizes[tag] = (p.width(), p.height()) if p is not None else None
    check('P25 三层帧尺寸不同（是事实，不是猜测）',
          len(set(v for v in sizes.values() if v)) >= 2, 'sizes=%r' % sizes)
    # 用**真素材尺寸**再出一版计划：三层的 (w,h) 必须**各异**（钉住"各取自己尺寸"）
    plan2 = R.plan_frame(scene, cam, geo, tick=0, sprite_size=cache.sprite_size,
                         bubbles=BUBBLES)
    ball_items = [it for it in plan2
                  if it.get('kind') == R.K_BUBBLE and it.get('role') != 'character']
    dims = [(it['rect'][2], it['rect'][3]) for it in ball_items]
    check('P26 真素材下三层尺寸各异（各取自己尺寸）',
          len(set(dims)) >= 2, 'dims=%r' % dims)
    ys = [it['rect'][1] + it['rect'][3] / 2.0 for it in ball_items]
    check('P27 三层按同一球心居中', max(ys) - min(ys) <= 1.0, 'centers_y=%r' % ys)
except Exception as e:
    check('P24 bubble: 前缀真解析到 assets/bubble/', False, repr(e))

print('-' * 72)
print('冒烟：FAIL=%d %s' % (len(FAIL), FAIL if FAIL else ''))
sys.exit(1 if FAIL else 0)

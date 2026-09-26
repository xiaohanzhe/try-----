# -*- coding: utf-8 -*-
"""第44轮 · 场景画布（Qt 绘制壳）回归锁 —— `scene_canvas` + 接线。

为什么**不真机截屏**：沙箱里离屏渲染不稳定（第44轮实测 D2 类判据在
不同会话下时好时坏），而"画面对不对"里真正稳定的部分是**绘制指令的消费**：
每条指令有没有被派发到对应的原语、缺素材有没有走占位、异常有没有兜住。
本套件用**假画笔 + 假素材**把这些逐条钉死 —— 确定性、毫秒级、零 Qt 依赖
（只需 PyQt5 可 import；不需要 QApplication —— 见 A1 的说明）。

判据分五段：
  A 常量与 scene_render 对齐（drift 检测） + 模块纪律（零项目内反向依赖）
  B 素材缓存 SceneAssetCache（命中/未命中/精确尺寸/不重复 IO）
  C 绘制分派 paint_on（每种 kind 一条 + 未知 kind 不静默）
  D 缺素材 → 占位（不静默空着） + 异常兜底（单条失败不拖垮整帧）
  E 产品接线（main.py 真调 + 预声明 + 默认关闭 + 相机驱动真实量级）

★ 铁律：
  · 成功标记必须 `[PASS]` 字面量（`run_all.py:425` 按它计数）。
  · 正/负控制成对；恒真判据比不写还危险。
  · 行为判据必须用**真实量级输入**（640×480 / 660×480 / 320×240 都是真实值）。
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, MOD)

import scene_canvas as C            # noqa: E402
import scene_render as SR          # noqa: E402

_N = [0]
_FAIL = []


def ok(cond, msg):
    _N[0] += 1
    if cond:
        print('[PASS] %s' % msg)
    else:
        _FAIL.append(msg)
        print('[FAIL] %s' % msg)


def _read(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


# ===========================================================================
# 假件（确定性，不用真 Qt 对象）
# ===========================================================================
class FakePainter(object):
    """只记录调用序列 —— 有原始 QPainter 的四个方法就够了。"""

    def __init__(self, fail_on=None):
        self.calls = []
        self._fail_on = fail_on
        self._count = 0

    def _maybe_fail(self, name):
        if self._fail_on is not None:
            self._count += 1
            if self._count == self._fail_on:
                raise RuntimeError('fake painter 故意报错（第 %d 次调用）' % name)

    def fillRect(self, *a):
        self._maybe_fail('fillRect')
        self.calls.append(('fillRect',))

    def drawPixmap(self, *a):
        self._maybe_fail('drawPixmap')
        self.calls.append(('drawPixmap',))

    def drawRect(self, r):
        self._maybe_fail('drawRect')
        self.calls.append(('drawRect', r.x(), r.y(), r.width(), r.height()))

    def drawLine(self, x1, y1, x2, y2):
        self.calls.append(('drawLine',))

    def setPen(self, p):
        self.calls.append(('setPen',))

    def setOpacity(self, o):
        self.calls.append(('setOpacity', o))


class FakePixmap(object):
    def __init__(self, w, h):
        self._w, self._h = w, h

    def width(self):
        return self._w

    def height(self):
        return self._h

    def isNull(self):
        return False


class FakeAssets(object):
    """按名字表给尺寸；表外 → `None`（= 文件不存在）。"""

    def __init__(self, table):
        self.table = dict(table)
        self.lookups = []

    def get(self, name):
        self.lookups.append(name)
        if name in self.table:
            return FakePixmap(*self.table[name])
        return None

    def sprite_size(self, name):
        got = self.get(name)
        if got is None:
            return None
        return (got.width(), got.height())


# ===========================================================================
# A 常量对齐 + 模块纪律
# ===========================================================================
def sec_a():
    print('== A 常量对齐 + 模块纪律 ==')
    # A1 kind 常量必须与 scene_render 一字不差（改了一边忘另一边 → 立刻报红）
    ok(C.K_BG == SR.K_BG, 'A1a K_BG 与 scene_render 一致（%s）' % C.K_BG)
    ok(C.K_OBJ == SR.K_OBJ, 'A1b K_OBJ 一致')
    ok(C.K_PLACEHOLDER == SR.K_PLACEHOLDER, 'A1c K_PLACEHOLDER 一致')
    ok(C.K_ROOM_BORDER == SR.K_ROOM_BORDER, 'A1d K_ROOM_BORDER 一致')
    # ★ A1e 画布**不该**自带间距常量 —— 间距是**指令携带的**（`item['stripe']`），
    #   画布只是消费者。重复定义会让"改 scene_render 忘了改画布"变成静默不一致。
    ok(not hasattr(C, 'PLACEHOLDER_STRIPE'),
       'A1e 画布不自带 PLACEHOLDER_STRIPE（间距随指令走，不重复定义）')

    # A2 模块纪律：不 import 任何项目内模块（除 logger_utils 的 try 兜底）
    src = _read(os.path.join(MOD, 'scene_canvas.py'))
    tree = ast.parse(src)
    proj_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            proj_imports += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                proj_imports.append(node.module)
    banned = [n for n in proj_imports
              if n.split('.')[0] in ('scene_system', 'scene_controller',
                                     'scene_camera', 'scene_render',
                                     'sprite_loader', 'data_store',
                                     'dialogue_ui', 'main')]
    ok(not banned, 'A2 不 import 项目内反向依赖模块（实际越界=%s）' % banned)
    # 反过来：scene_render 必须**不**认识 scene_canvas（单向依赖）。
    # ⚠️ 判据修正（第50轮）：首版是 `'scene_canvas' not in rsrc` 的**裸子串扫描** ——
    #   连**文档字符串里提到**模块名都会误报（第50轮给 `split_bubble_layers` 写注释
    #   指向消费方就撞上了）。真正的风险是 **import 反向依赖** ⇒ 改用 AST 看 import；
    #   模块级"零依赖"另由 render_round44 的 AST 判据（顶层 import ⊆ {logging}）看住。
    rsrc = _read(os.path.join(MOD, 'scene_render.py'))
    rimports = []
    for _n in ast.walk(ast.parse(rsrc)):
        if isinstance(_n, ast.Import):
            rimports += [a.name for a in _n.names]
        elif isinstance(_n, ast.ImportFrom):
            if _n.module:
                rimports.append(_n.module)
    rcin = [n for n in rimports if n.split('.')[0] == 'scene_canvas']
    ok(not rcin, 'A3 scene_render 不 import scene_canvas（依赖单向；实际=%s）' % rcin)

    # A4 绘制失败纪律写在模块里（可被复查）
    ok('except Exception' in src, 'A4a 有异常兜底')
    ok('不静默' in src or '占位' in src, 'A4b 声明"缺素材画占位不静默"')

    # A5 场景画布类默认隐藏（P0 判据不破）—— 负控制：必须有 hide() 调用
    ok('self.hide()' in src, 'A5 SceneCanvas.__init__ 显式 hide()（默认不显示）')


# ===========================================================================
# B 素材缓存
# ===========================================================================
def sec_b():
    print('== B 素材缓存 SceneAssetCache ==')

    # B1 用假 pixmap 类替掉 QPixmap，避免依赖真 Qt 资源
    cache = C.SceneAssetCache(base_dir=os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes'))
    real_pixmap = C.QPixmap

    class _FakePM(object):
        def __init__(self, path):
            self.path = path
            self._null = not os.path.exists(path)

        def isNull(self):
            return self._null

        def width(self):
            return 660

        def height(self):
            return 480

    C.QPixmap = _FakePM
    try:
        bg = 'bg/ch1_castle_town_castle_front.png'
        p1 = cache.get(bg)
        ok(p1 is not None, 'B1 真实存在的背景能取到（%s）' % bg)
        p2 = cache.get(bg)
        ok(p1 is p2, 'B2 二次取 → 命中缓存（同一对象）')
        miss = cache.get('bg/__definitely_missing__.png')
        ok(miss is None, 'B3 不存在的文件 → None（不伪造）')
        ok('bg/__definitely_missing__.png' in cache.missing,
           'B4 未命中的名字记进 missing')
        ok(cache.get(None) is None, 'B5 name=None → None（不崩）')
        ok(cache.get('') is None, 'B6 name="" → None')
        # B7 sprite_size 返回**原始尺寸**（未乘 scale）—— 见其 docstring
        sz = cache.sprite_size(bg)
        ok(sz == (660, 480), 'B7 sprite_size 返回原始像素（未乘 scale）实际=%s' % (sz,))
        ok(cache.sprite_size('bg/__nope__.png') is None, 'B8 缺素材 sprite_size → None')
        cache.clear()
        ok(cache.missing == [], 'B9 clear() 清空 missing')
    finally:
        C.QPixmap = real_pixmap


# ===========================================================================
# C 绘制分派
# ===========================================================================
def sec_c():
    print('== C 绘制分派 paint_on ==')
    assets = FakeAssets({
        'bg/a.png': (660, 480),
        'spr/x.png': (21, 41),
    })

    # C1 空计划 → 0 条
    ok(C.paint_on(FakePainter(), [], assets) == 0, 'C1 空计划 → 画 0 条')

    # C2 bg：命中素材 → drawPixmap
    p = FakePainter()
    n = C.paint_on(p, [{'kind': 'bg', 'name': 'bg/a.png',
                        'rect': (0, 0, 1320, 960)}], assets)
    ok(n == 1, 'C2a bg 指令被画出（返回 1）实际=%d' % n)
    ok(('drawPixmap',) in p.calls, 'C2b bg → drawPixmap')

    # C3 obj：命中素材 → drawPixmap；带 alpha<1 → setOpacity 成对
    p = FakePainter()
    C.paint_on(p, [{'kind': 'obj', 'name': 'spr/x.png',
                    'rect': (10, 20, 42, 82), 'alpha': 1.0}], assets)
    ok(('drawPixmap',) in p.calls, 'C3a obj 命中素材 → drawPixmap')
    p = FakePainter()
    C.paint_on(p, [{'kind': 'obj', 'name': 'spr/x.png',
                    'rect': (10, 20, 42, 82), 'alpha': 0.5}], assets)
    ops = [c for c in p.calls if c[0] == 'setOpacity']
    ok(len(ops) == 2 and ops[0][1] == 0.5 and ops[1][1] == 1.0,
       'C3b alpha=0.5 → setOpacity(0.5) 后复位 1.0（成对）实际=%s' % ops)

    # C4 placeholder → fillRect + >=1 条 drawLine（斜纹）
    p = FakePainter()
    C.paint_on(p, [{'kind': 'placeholder', 'rect': (0, 0, 640, 480),
                    'stripe': 16}], assets)
    ok(('fillRect',) in p.calls, 'C4a placeholder → fillRect 底色')
    ok(sum(1 for c in p.calls if c[0] == 'drawLine') > 0, 'C4b placeholder → 斜纹线')

    # C5 room_border → setPen + drawRect，且矩形与指令一致
    p = FakePainter()
    C.paint_on(p, [{'kind': 'room_border', 'rect': (0, 0, 2000, 2000),
                    'width': 2}], assets)
    rcs = [c for c in p.calls if c[0] == 'drawRect']
    ok(len(rcs) == 1 and rcs[0][1:] == (0, 0, 2000, 2000),
       'C5 room_border → drawRect 与指令矩形一致 实际=%s' % (rcs,))

    # C6 混合计划：条数 + 顺序（bg 在 obj 之前 = 从后到前）
    p = FakePainter()
    n = C.paint_on(p, [
        {'kind': 'bg', 'name': 'bg/a.png', 'rect': (0, 0, 1320, 960)},
        {'kind': 'obj', 'name': 'spr/x.png', 'rect': (0, 0, 42, 82)},
        {'kind': 'room_border', 'rect': (0, 0, 2000, 2000), 'width': 2},
    ], assets)
    ok(n == 3, 'C6a 三条指令全画出（实际 %d）' % n)
    pix_idx = [i for i, c in enumerate(p.calls) if c[0] == 'drawPixmap']
    ok(len(pix_idx) == 2 and pix_idx[0] < pix_idx[1],
       'C6b bg 先于 obj（从后到前的顺序）实际=%s' % pix_idx)

    # C7 未知 kind → 不计入 drawn（不静默当成功）
    p = FakePainter()
    n = C.paint_on(p, [{'kind': 'no_such_kind', 'rect': (0, 0, 1, 1)}], assets)
    ok(n == 0, 'C7 未知 kind → drawn=0（不当成功）实际=%d' % n)

    # C8 坏指令（无 rect）→ 不崩、不计入
    p = FakePainter()
    n = C.paint_on(p, [{'kind': 'bg', 'name': 'bg/a.png'}], assets)
    ok(n == 0, 'C8a 缺 rect 的 bg → 不画（实际 %d）' % n)
    n = C.paint_on(p, [None, 'junk', 123], assets)
    ok(n == 0, 'C8b 非 dict 元素 → 不崩（实际 %d）' % n)


# ===========================================================================
# D 缺素材 → 占位 + 异常兜底
# ===========================================================================
def sec_d():
    print('== D 缺素材占位 + 异常兜底 ==')
    empty = FakeAssets({})   # 什么都取不到

    # D1 缺背景 → 走 placeholder 视觉（fillRect + 斜纹），**不是**空白
    p = FakePainter()
    n = C.paint_on(p, [{'kind': 'bg', 'name': 'bg/nope.png',
                        'rect': (0, 0, 640, 480)}], empty)
    ok(n == 1, 'D1a 缺背景仍算"画了"（返回 1，因为画了占位）实际=%d' % n)
    ok(('fillRect',) in p.calls, 'D1b 缺背景 → fillRect 占位')
    ok(('drawPixmap',) not in p.calls, 'D1c 缺背景 → **不**调 drawPixmap')

    # D2 缺物件素材 → 品红空框（drawRect），不静默跳过
    p = FakePainter()
    n = C.paint_on(p, [{'kind': 'obj', 'name': 'spr/nope.png',
                        'rect': (10, 20, 42, 82)}], empty)
    ok(n == 1, 'D2a 缺物件素材仍算"画了"（返回 1）实际=%d' % n)
    rcs = [c for c in p.calls if c[0] == 'drawRect']
    ok(len(rcs) == 1 and rcs[0][1:] == (10, 20, 42, 82),
       'D2b 缺物件 → drawRect 描边同矩形 实际=%s' % (rcs,))

    # D3 物件无 name（纯逻辑锚点）→ 也画描边框（不静默）
    p = FakePainter()
    n = C.paint_on(p, [{'kind': 'obj', 'name': None, 'rect': (0, 0, 1, 1)}], empty)
    ok(n == 1, 'D3 无 name 的物件 → 仍画描边框（%d）' % n)

    # D4 单条抛异常 → 不拖垮整帧（前后两条照常画）
    plan = [
        {'kind': 'bg', 'name': 'bg/a.png', 'rect': (0, 0, 1320, 960)},
        {'kind': 'obj', 'name': 'spr/x.png', 'rect': (0, 0, 42, 82)},
        {'kind': 'room_border', 'rect': (0, 0, 2000, 2000), 'width': 2},
    ]
    assets = FakeAssets({'bg/a.png': (660, 480), 'spr/x.png': (21, 41)})
    # 在 obj 的 drawPixmap 上抛（第 2 次 drawPixmap）
    p = FakePainter(fail_on=None)

    class _Boom(FakePainter):
        def drawPixmap(self, *a):
            self.cursor = getattr(self, 'cursor', 0) + 1
            if self.cursor == 2:
                raise RuntimeError('故意：第 2 次 drawPixmap 报错')
            self.calls.append(('drawPixmap',))

    pb = _Boom()
    n = C.paint_on(pb, plan, assets)
    ok(n == 2, 'D4a 单条异常 → 其余仍画出（返回 2，实际 %d）' % n)
    ok(any(c[0] == 'drawRect' for c in pb.calls),
       'D4b 异常之后的那条（room_border）仍被画')

    # D5 全部抛 → 返回 0 但**不抛到调用方**（常驻进程纪律）
    class _AllBoom(FakePainter):
        def fillRect(self, *a):
            raise RuntimeError('boom')

        def drawPixmap(self, *a):
            raise RuntimeError('boom')

        def drawRect(self, r):
            raise RuntimeError('boom')

    try:
        n = C.paint_on(_AllBoom(), plan, assets)
        ok(n == 0, 'D5 全部抛 → 返回 0 且不抛出（实际 %d）' % n)
    except Exception as e:
        ok(False, 'D5 全部抛 → 不该抛出（实际抛了 %r）' % e)


# ===========================================================================
# E 产品接线
# ===========================================================================
def sec_e():
    print('== E 产品接线 ==')
    main = _read(os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'))
    ctl = _read(os.path.join(MOD, 'scene_controller.py'))
    canvas = _read(os.path.join(MOD, 'scene_canvas.py'))

    # E1 main.py 真的 import 并创建画布
    ok('from modules.scene_canvas import SceneCanvas' in main,
       'E1a main.py import SceneCanvas')
    ok('self.scene_canvas = SceneCanvas(self)' in main,
       'E1b main.py 创建画布实例')

    # E2 ★ main.py 真的驱动相机 + 消费计划（"函数写对了但产品没用上"的反面）
    ok('def _update_scene_layer(' in main, 'E2a main.py 定义 _update_scene_layer')
    ok('self._update_scene_layer()' in main, 'E2b 该函数**被调用**（不是死代码）')
    ok('scene.camera_follow(' in main, 'E2c main.py 调 camera_follow（相机真的被驱动）')
    ok('scene.plan_frame(' in main, 'E2d main.py 调 plan_frame（真的出指令）')
    ok('canvas.set_plan(' in main, 'E2e main.py 把指令交给画布（真的被消费）')
    ok('scene.plan_viewport()' in main, 'E2f main.py 用 plan_viewport 定画布尺寸')

    # E3 控制器补了 plan_viewport（画布尺寸入口）
    ok('def plan_viewport(' in ctl, 'E3 控制器定义 plan_viewport')

    # E4 场景层总开关（口径变更：第44轮 P0 期默认 **False**；
    #    第50轮用户第18项「怎么和原作效果贴近怎么来」⇒ 改 **True**（贴近原作）。
    #    「不切场景时零行为变化」的 P0 判据改由 scene_p0 的"无定时器/仅 follow_route 调 switch"
    #    等结构判据看住，不再靠"总开关关着"。
    ok('SCENE_LAYER_ENABLED = True' in main,
       'E4a 渲染层默认开启（SCENE_LAYER_ENABLED = True，第50轮口径贴近原作）')
    ok('_scene_layer_visible' in main, 'E4b 预声明 _scene_layer_visible')

    # E5 相机映射必须做"屏幕→房间"归一化（第44轮真机实测修正）
    ok('_pet_target_rect' in main, 'E5a 定义 _pet_target_rect')
    ok('_virtual_screen_size' in main, 'E5b 定义 _virtual_screen_size（副屏安全）')
    ok('fx = min(1.0, max(0.0' in main or '归一化' in main,
       'E5c 目标坐标做了归一化（防"目标比房间大 5 倍被钳死"复演）')

    # E6 渲染壳不注册定时器（与 P0 同纪律）
    ok('QTimer' not in canvas, 'E6 画布不注册 QTimer（不自转）')

    # E7 断言条数自查
    ok(_N[0] > 45, 'E7 断言条数 > 45（实际 %d）' % _N[0])


def main():
    print('第44轮 场景画布回归锁（%s）' % os.path.basename(__file__))
    sec_a()
    sec_b()
    sec_c()
    sec_d()
    sec_e()
    print()
    if _FAIL:
        print('[FAIL] 共 %d 条失败（断言 %d）' % (len(_FAIL), _N[0]))
        for f in _FAIL:
            print('   - ' + f)
        return 1
    print('场景画布回归锁：%d/%d 全绿' % (_N[0], _N[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
